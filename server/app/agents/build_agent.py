import logging
from typing import AsyncGenerator
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.state import SessionState, Message, Checkpoint
from app.core.enums import Phase, MessageRole, CheckpointType
from app.agents.prompts.build_prompts import (
    BUILD_AGENT_SYSTEM_PROMPT,
    BUILD_AGENT_AWAITING_FILES_HINT,
    BUILD_AGENT_SCHEMA_ANALYSIS_HINT
)


logger = logging.getLogger(__name__)


def _filename_to_label(filename: str) -> str:
    """
    Convert a CSV/JSON/XLSX filename to a clean singular node label.

    Rules:
    - Strip extension
    - Singularize (factories→Factory, suppliers→Supplier)
    - Replace underscores/hyphens with spaces
    - Title-case each word BUT preserve all-caps segments (IDs, acronyms)
      e.g. "tradebook-KE8209-EQ" → "Tradebook KE8209 EQ"
           "suppliers"          → "Supplier"
           "supply_chain"       → "Supply Chain"
    """
    base = filename.replace('.csv', '').replace('.json', '').replace('.xlsx', '')

    # Singularize on the base (before splitting on separators)
    # Only singularize if it looks like a simple plural word (no hyphens/digits)
    # For compound names like "tradebook-KE8209-EQ" skip singularization
    if '-' not in base and not any(c.isdigit() for c in base):
        if base.endswith('ies'):
            base = base[:-3] + 'y'
        elif base.endswith('sses'):
            base = base[:-2]
        elif base.endswith('ses'):
            base = base[:-1]
        elif base.endswith('s') and not base.endswith('ss'):
            base = base[:-1]

    # Split on underscores and hyphens, title-case each word but preserve
    # segments that are all-uppercase or contain digits (acronyms / IDs)
    import re
    parts = re.split(r'[_\-]', base)
    label_parts = []
    for part in parts:
        if not part:
            continue
        # If the part is all-alpha and all-lowercase or all-uppercase with len<=3,
        # just capitalize first letter. If it's mixed or contains digits, keep as-is
        # unless it's all lowercase (then capitalize first letter only).
        if part.isupper() or any(c.isdigit() for c in part):
            # Preserve: KE8209, EQ, NSE, etc.
            label_parts.append(part)
        else:
            # Normal word: capitalize first letter only, preserve rest
            label_parts.append(part[0].upper() + part[1:])

    return ' '.join(label_parts)


async def stream_build_agent(
    session_state: SessionState,
    user_message: str,
) -> AsyncGenerator[str, None]:
    """
    Stream build agent response tokens.

    Handles FILES and SCHEMA phases. The LLM response streams token-by-token,
    then post-processing runs (schema approval check, auto-schema fallback).

    Session state is updated in place — caller must save after iterating.
    """
    logger.info(f"[BUILD_AGENT] Starting stream - Phase: {session_state.phase}, Files: {len(session_state.files)}")

    file_count = len(session_state.files)

    # Prepare files summary
    if session_state.files:
        summary_lines = []
        for f in session_state.files:
            kind = "tabular" if f.columns else "unstructured"
            line = (
                f"  • {f.name} ({f.type}, {kind}): "
                f"{f.raw_count or 'N/A'} rows, "
                f"columns: {', '.join(f.columns) if f.columns else 'N/A'}"
            )
            if f.preview:
                line += f"\n    Preview: {f.preview[:100]}..."
            summary_lines.append(line)
        files_summary = "\n".join(summary_lines)
    else:
        files_summary = "  (No files uploaded yet)"

    # Build system prompt
    system_prompt = BUILD_AGENT_SYSTEM_PROMPT.format(
        goal=session_state.user_goal or "organize your data",
        file_count=file_count,
        files_summary=files_summary,
        phase=session_state.phase.value
    )

    # Add phase-specific hints
    if file_count == 0:
        system_prompt += "\n\n" + BUILD_AGENT_AWAITING_FILES_HINT.format(
            goal=session_state.user_goal or "organize your data"
        )
    else:
        system_prompt += "\n\n" + BUILD_AGENT_SCHEMA_ANALYSIS_HINT.format(
            file_count=file_count
        )

    # Build message history
    langchain_messages = []
    for msg in session_state.messages:
        if msg.role == MessageRole.USER:
            langchain_messages.append(HumanMessage(content=msg.content))
        elif msg.role == MessageRole.ASSISTANT:
            langchain_messages.append(AIMessage(content=msg.content))
    langchain_messages.append(HumanMessage(content=user_message))

    messages = [SystemMessage(content=system_prompt)] + langchain_messages

    llm = ChatOpenAI(
        model=settings.openai_model_name,
        api_key=settings.openai_api_key,
        temperature=0.7
    )

    # Stream LLM response
    logger.info(f"[BUILD_AGENT] Streaming LLM response with {file_count} files")
    full_response = ""
    async for chunk in llm.astream(messages):
        token = chunk.content
        if token:
            full_response += token
            yield token

    logger.info(f"[BUILD_AGENT] Stream complete: {full_response[:100]}...")

    # --- Post-processing: update session state ---
    session_state.messages.append(Message(role=MessageRole.USER, content=user_message))
    session_state.messages.append(Message(role=MessageRole.ASSISTANT, content=full_response))

    # CODE-DRIVEN: Handle schema approval
    if session_state.phase == Phase.SCHEMA:
        msg_lower = user_message.lower().strip()
        has_missing_files = (
            session_state.checkpoint and
            session_state.checkpoint.data and
            session_state.checkpoint.data.get("missing_files")
        )

        if has_missing_files and msg_lower in ("skip", "proceed", "skip it", "no thanks", "without"):
            # User chose to skip missing files — clear the warning and approve as-is
            logger.info("[BUILD_AGENT] User skipped missing files, approving schema as-is")
            session_state.schema_approved = True
            session_state.checkpoint = None
            session_state.phase = Phase.BUILD
            logger.info("[BUILD_AGENT] → Moved to BUILD phase (missing files skipped)")

        elif not has_missing_files and msg_lower in [
            "approve", "yes", "looks good", "proceed", "build it", "correct",
            "sounds good", "ok", "okay", "sure", "go ahead", "yep", "fine",
            "perfect", "great", "do it", "let's go", "lets go", "yes please",
            "approve it", "good", "confirmed", "confirm", "lgtm",
        ]:
            logger.info("[BUILD_AGENT] User approved schema")
            session_state.schema_approved = True
            session_state.checkpoint = None
            session_state.phase = Phase.BUILD
            logger.info("[BUILD_AGENT] → Moved to BUILD phase")

    # CODE-DRIVEN FALLBACK: If in FILES phase with files but no schema proposed, auto-generate
    if (session_state.phase == Phase.FILES and
        file_count > 0 and
        not session_state.proposed_schema and
        not session_state.checkpoint):

        logger.warning("[BUILD_AGENT] ⚠️  Agent didn't propose schema - auto-generating from files")

        # Only tabular files (csv/json/xlsx with columns) become node types.
        # PDFs, txt, md are unstructured — handled by the lexical graph, not the domain schema.
        tabular_files = [f for f in session_state.files if f.columns and f.type in ("csv", "json", "xlsx")]

        # Auto-generate simple schema from file names
        nodes = []
        for file in tabular_files:
            label = _filename_to_label(file.name)
            properties = file.columns if file.columns else []
            nodes.append({
                "label": label,
                "properties": properties,
                "description": f"{label} from {file.name}"
            })


        relationships = []


        label_to_key = {}
        for node in nodes:
            label_lower = node["label"].lower()
            found = False
            # Strategy 1: exact {label}_id or id
            for prop in node["properties"]:
                if prop.lower() == f"{label_lower}_id" or prop.lower() == "id":
                    label_to_key[label_lower] = prop
                    found = True
                    break
            # Strategy 2: first column ending in _id (matches detect_unique_key fallback)
            if not found:
                for prop in node["properties"]:
                    if prop.endswith('_id'):
                        label_to_key[label_lower] = prop
                        break

        # For each tabular file, look for foreign key columns
        for file in tabular_files:
            to_label = _filename_to_label(file.name)
            # Own key for this file — skip it, it's the PK not a FK
            file_own_key = label_to_key.get(_filename_to_label(file.name).lower(), "").lower()

            # Check each column for foreign keys
            if file.columns:
                for col in file.columns:
                    # Foreign key pattern: ends with _id, but not this file's own PK
                    if col.endswith('_id') and col.lower() != file_own_key:
                        # Extract the referenced entity name
                        # supplier_id → supplier, factory_id → factory
                        fk_entity = col.replace('_id', '')

                        # Find matching node label
                        for node in nodes:
                            node_label_lower = node["label"].lower().replace(' ', '_')
                            if node_label_lower == fk_entity:
                                # Create relationship
                                # Naming convention: SUPPLIES, SHIPS_TO, CONTAINS
                                rel_name = fk_entity.upper()

                                # Use more semantic names for common patterns
                                if fk_entity == "supplier":
                                    rel_type = "SUPPLIES"
                                elif fk_entity == "factory":
                                    rel_type = "SHIPS_TO"
                                elif fk_entity == "part":
                                    rel_type = "CONTAINS"
                                else:
                                    rel_type = f"HAS_{rel_name.upper()}"

                                relationships.append({
                                    "type": rel_type,
                                    "from": node["label"],  # The referenced entity
                                    "to": to_label,         # The entity with the foreign key
                                    "via_column": col
                                })
                                logger.info(f"[BUILD_AGENT] Inferred relationship: ({node['label']})-[:{rel_type}]->({to_label}) via {col}")
                                break

        # --- Critic validation: check for missing files referenced by FKs ---
        # Build set of each node's OWN key so we don't treat it as a foreign key
        # e.g. trade_id in tradebook is the row's own ID, not a reference to a "Trade" table
        own_keys_per_file = {}
        for file in tabular_files:
            file_label = _filename_to_label(file.name).lower()  # match label_to_key format (spaces, not underscores)
            own_keys_per_file[file.name] = label_to_key.get(file_label, "")

        existing_node_keys = {n["label"].lower().replace(' ', '_') for n in nodes}
        missing_references = []
        for file in tabular_files:
            own_key = own_keys_per_file.get(file.name, "").lower()
            if file.columns:
                for col in file.columns:
                    if col.endswith('_id') and col.lower() != own_key:
                        fk_entity = col.replace('_id', '')
                        if fk_entity not in existing_node_keys:
                            missing_references.append({
                                "fk_column": col,
                                "referenced_entity": fk_entity,
                                "in_file": file.name
                            })

        if missing_references:
            # Don't auto-approve — ask user for the missing files
            missing_names = list({m["referenced_entity"] for m in missing_references})
            missing_str = ", ".join(f"{n}.csv" for n in missing_names)
            logger.info(f"[BUILD_AGENT] Missing files for FK references: {missing_names}")

            session_state.proposed_schema = {"nodes": nodes, "relationships": relationships}
            session_state.checkpoint = Checkpoint(
                type=CheckpointType.SCHEMA_APPROVAL,
                data={"nodes": nodes, "relationships": relationships, "missing_files": missing_references},
                prompt=(
                    f"I found references to {missing_str} in your data but those files aren't uploaded. "
                    f"Upload them to connect the data, or say 'skip' to proceed without those connections."
                )
            )
            session_state.phase = Phase.SCHEMA
            logger.info(f"[BUILD_AGENT] → Checkpoint: waiting for missing files or skip")

        elif len(nodes) == 1 and len(relationships) == 0:
            # Single file, no connections possible — warn before approving
            node_label = nodes[0]["label"]
            logger.info(f"[BUILD_AGENT] Single-file warning: {node_label}, no relationships")

            session_state.proposed_schema = {"nodes": nodes, "relationships": relationships}
            session_state.checkpoint = Checkpoint(
                type=CheckpointType.SCHEMA_APPROVAL,
                data={"nodes": nodes, "relationships": relationships},
                prompt=(
                    f"This is a single table ({node_label}) with no connections to other data. "
                    f"You can upload more files to create connections, or say 'proceed' to build as-is."
                )
            )
            session_state.phase = Phase.SCHEMA
            logger.info(f"[BUILD_AGENT] → Checkpoint: single-file warning shown")

        else:
            # Normal path: schema looks complete, propose for approval
            session_state.proposed_schema = {"nodes": nodes, "relationships": relationships}
            session_state.checkpoint = Checkpoint(
                type=CheckpointType.SCHEMA_APPROVAL,
                data={"nodes": nodes, "relationships": relationships},
                prompt="Ready to build with this structure?"
            )
            session_state.phase = Phase.SCHEMA

        logger.info(f"[BUILD_AGENT] ✓ Auto-generated schema: {len(nodes)} nodes, {len(relationships)} relationships")

    logger.info(f"[BUILD_AGENT] Completed - Final phase: {session_state.phase}")
