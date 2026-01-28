"""
Checkpoint Handler - Handles user responses at checkpoints.

Checkpoints are decision points where the system pauses and waits for user input:
- files_approval: User approves/modifies selected files
- schema_approval: User approves/modifies schema design
- build_approval: User confirms graph construction

This module interprets user's intent and updates session accordingly.
"""

from typing import Dict, Any
import logging
from langchain_core.messages import AIMessage, HumanMessage

import asyncio
import concurrent.futures
from pathlib import Path

from app.services.domain_graph_builder import construct_domain_graph, get_graph_stats
from app.services.lexical_graph_builder import build_lexical_graph
from app.services.subject_graph_builder import build_subject_graph, resolve_entities
from app.services.graph_query_service import create_vector_index
from app.core.config import get_settings

logger = logging.getLogger(__name__)


# =============================================================================
# INTENT CLASSIFICATION
# =============================================================================

def classify_user_intent(message: str) -> str:
    """
    Classify user's intent from their message at a checkpoint.

    Returns:
        "approve" - User wants to proceed
        "modify" - User wants to change something
        "cancel" - User wants to go back/cancel
        "unclear" - Can't determine intent
    """
    message_lower = message.lower().strip()

    # Approval keywords
    approval_keywords = [
        "yes", "approve", "looks good", "perfect", "continue", "proceed",
        "go ahead", "build it", "do it", "ok", "okay", "correct", "right",
        "good", "great", "fine", "sure", "yep", "yeah", "y", "👍"
    ]

    # Modification keywords
    modification_keywords = [
        "wait", "hold", "change", "modify", "edit", "remove", "add",
        "don't use", "not", "except", "instead", "different", "other"
    ]

    # Cancellation keywords
    cancellation_keywords = [
        "cancel", "stop", "no", "nope", "back", "reset", "start over",
        "nevermind", "never mind", "forget it"
    ]

    # Check for exact matches or keywords
    if message_lower in approval_keywords or any(kw in message_lower for kw in approval_keywords):
        return "approve"

    if any(kw in message_lower for kw in cancellation_keywords):
        return "cancel"

    if any(kw in message_lower for kw in modification_keywords):
        return "modify"

    return "unclear"


# =============================================================================
# CHECKPOINT HANDLERS
# =============================================================================

def handle_checkpoint_response(session: Dict[str, Any], message: str) -> Dict[str, Any]:
    """
    Route checkpoint response to appropriate handler.

    Args:
        session: Current session state
        message: User's response

    Returns:
        Updated session state
    """
    checkpoint = session.get("checkpoint")

    logger.info(f"[checkpoint_handler] Handling response at {checkpoint}: {message[:50]}...")

    if checkpoint == "files_approval":
        return handle_files_approval(session, message)

    elif checkpoint == "schema_approval":
        return handle_schema_approval(session, message)

    elif checkpoint == "entities_approval":
        return handle_entities_approval(session, message)

    elif checkpoint == "facts_approval":
        return handle_facts_approval(session, message)

    elif checkpoint == "build_approval":
        return handle_build_approval(session, message)

    else:
        logger.error(f"[checkpoint_handler] Unknown checkpoint: {checkpoint}")
        session["messages"].append(
            AIMessage(content=f"Error: Unknown checkpoint state. Please restart.")
        )
        return session


def handle_files_approval(session: Dict[str, Any], message: str) -> Dict[str, Any]:
    """
    Handle user response at files_approval checkpoint.

    User can:
    - Approve: Proceed with suggested files
    - Modify: Change file selection
    - Cancel: Go back to goal definition
    """
    intent = classify_user_intent(message)

    logger.info(f"[checkpoint_handler] Files approval intent: {intent}")

    if intent == "approve":
        # User approved files - route based on file types
        session["approved_files"] = session.get("proposed_files", [])
        session["checkpoint"] = None
        session["awaiting_user_action"] = False

        # Detect structured vs unstructured files
        structured = [f for f in session["approved_files"] if f.lower().endswith(('.csv', '.tsv'))]
        unstructured = [f for f in session["approved_files"] if f.lower().endswith(('.md', '.txt'))]

        if structured:
            # Has CSV files — go to schema_proposal (will chain to unstructured_schema after if needed)
            session["current_phase"] = "schema_proposal"
            response = f"Designing schema for {len(structured)} structured file(s). This will take a moment..."
        else:
            # Only unstructured files — skip schema_proposal, go directly to unstructured_schema
            session["current_phase"] = "unstructured_schema"
            session["unstructured_stage"] = "ner"
            response = f"Extracting entities from {len(unstructured)} text file(s)..."

        session["messages"].append(HumanMessage(content=message))
        session["messages"].append(AIMessage(content=response))

        logger.info(f"[checkpoint_handler] Files approved: {session['approved_files']} (structured={len(structured)}, unstructured={len(unstructured)})")

    elif intent == "modify":
        # User wants to modify file selection
        session["awaiting_user_action"] = True  # Still waiting

        response = """I can help you modify the file selection. You can:

• Type "remove [filename]" to exclude a file
• Type "add [filename]" to include a different file
• Type "show all files" to see all available files
• Upload new files if needed

What would you like to change?"""

        session["messages"].append(HumanMessage(content=message))
        session["messages"].append(AIMessage(content=response))

        logger.info("[checkpoint_handler] User requested file modification")

    elif intent == "cancel":
        # User wants to cancel - go back to user intent
        session["current_phase"] = "user_intent"
        session["checkpoint"] = None
        session["awaiting_user_action"] = False
        session["proposed_files"] = None
        session["approved_files"] = None

        response = "No problem! Let's start over. What kind of graph would you like to build?"

        session["messages"].append(HumanMessage(content=message))
        session["messages"].append(AIMessage(content=response))

        logger.info("[checkpoint_handler] User cancelled file approval")

    else:
        # Unclear intent - ask for clarification
        response = """I'm not sure what you'd like to do. Would you like to:

• **Approve** these files and continue?
• **Modify** the file selection?
• **Cancel** and start over?

Please let me know!"""

        session["messages"].append(HumanMessage(content=message))
        session["messages"].append(AIMessage(content=response))

        logger.info("[checkpoint_handler] Unclear intent, asking for clarification")

    return session


def handle_schema_approval(session: Dict[str, Any], message: str) -> Dict[str, Any]:
    """
    Handle user response at schema_approval checkpoint.

    User can:
    - Approve: Proceed to build graph
    - Modify: Request schema changes
    - Preview: See sample of what graph will look like
    - Cancel: Go back to file selection
    """
    intent = classify_user_intent(message)
    message_lower = message.lower()

    logger.info(f"[checkpoint_handler] Schema approval intent: {intent}")

    # Check for preview request
    if "preview" in message_lower or "sample" in message_lower or "example" in message_lower:
        response = """Here's a preview of your graph structure:

**Sample Nodes:**
```
(:Supplier {id: "S001", name: "Acme Supply", location: "NYC"})
(:Part {id: "P001", name: "Steel Plate", category: "Materials"})
(:Factory {id: "F001", name: "Factory A", location: "CA"})
```

**Sample Relationships:**
```
(:Part {id: "P001"})-[:SUPPLIED_BY]->(:Supplier {id: "S001"})
(:Part {id: "P001"})-[:SHIPPED_TO]->(:Factory {id: "F001"})
```

Does this look correct?"""

        session["messages"].append(HumanMessage(content=message))
        session["messages"].append(AIMessage(content=response))

        logger.info("[checkpoint_handler] Showing schema preview")

    elif intent == "approve":
        # User approved schema - check if we also need unstructured processing
        session["approved_construction_plan"] = session.get("proposed_construction_plan", {})
        session["checkpoint"] = None
        session["awaiting_user_action"] = False

        # If there are text files, route to unstructured_schema before build
        unstructured = [f for f in session.get("approved_files", []) if f.lower().endswith(('.md', '.txt'))]
        if unstructured:
            session["current_phase"] = "unstructured_schema"
            session["unstructured_stage"] = "ner"
            response = f"Schema approved! Now extracting entities from {len(unstructured)} text file(s)..."
        else:
            session["current_phase"] = "graph_construction"
            response = "Perfect! Moving to graph construction..."

        session["messages"].append(HumanMessage(content=message))
        session["messages"].append(AIMessage(content=response))

        logger.info("[checkpoint_handler] Schema approved")

    elif intent == "modify":
        # User wants to modify schema
        session["awaiting_user_action"] = True  # Still waiting

        response = """What would you like to change in the schema?

You can request:
• "Change [NodeType] to [NewName]"
• "Add relationship between [A] and [B]"
• "Remove [NodeType]"
• "Add property [PropertyName] to [NodeType]"

What modification do you need?"""

        session["messages"].append(HumanMessage(content=message))
        session["messages"].append(AIMessage(content=response))

        logger.info("[checkpoint_handler] User requested schema modification")

    elif intent == "cancel":
        # User wants to go back to file selection
        session["current_phase"] = "file_suggestion"
        session["checkpoint"] = None
        session["awaiting_user_action"] = False
        session["proposed_construction_plan"] = None

        response = "Going back to file selection. Would you like to choose different files?"

        session["messages"].append(HumanMessage(content=message))
        session["messages"].append(AIMessage(content=response))

        logger.info("[checkpoint_handler] User cancelled schema approval")

    else:
        # Unclear intent
        response = """I'm not sure what you'd like to do. Would you like to:

• **Approve** this schema and build the graph?
• **Modify** the schema design?
• **Preview** a sample of what the graph will look like?
• **Cancel** and go back to file selection?

Please let me know!"""

        session["messages"].append(HumanMessage(content=message))
        session["messages"].append(AIMessage(content=response))

        logger.info("[checkpoint_handler] Unclear intent at schema approval")

    return session


def handle_entities_approval(session: Dict[str, Any], message: str) -> Dict[str, Any]:
    """
    Handle user response at entities_approval checkpoint (unstructured schema NER stage).

    User can:
    - Approve: Accept proposed entities, move to fact extraction
    - Modify: Request entity changes
    - Cancel: Go back
    """
    intent = classify_user_intent(message)

    logger.info(f"[checkpoint_handler] Entities approval intent: {intent}")

    if intent == "approve":
        session["approved_entities"] = session.get("proposed_entities", [])
        session["unstructured_stage"] = "fact"
        session["checkpoint"] = None
        session["awaiting_user_action"] = False

        response = f"Approved {len(session['approved_entities'])} entity types. Now extracting relationship facts..."

    elif intent == "modify":
        session["awaiting_user_action"] = True
        response = """What would you like to change about the entities?

You can:
• "Remove [EntityType]" to drop an entity type
• "Add [EntityType]" to include a new one
• Describe changes in natural language

What modification do you need?"""

    elif intent == "cancel":
        session["current_phase"] = "file_suggestion"
        session["checkpoint"] = None
        session["awaiting_user_action"] = False
        session["proposed_entities"] = []
        response = "Going back to file selection. Would you like to choose different files?"

    else:
        response = """Would you like to:

• **Approve** these entity types and continue?
• **Modify** the entity list?
• **Cancel** and go back?

Please let me know!"""

    session["messages"].append(HumanMessage(content=message))
    session["messages"].append(AIMessage(content=response))

    return session


def handle_facts_approval(session: Dict[str, Any], message: str) -> Dict[str, Any]:
    """
    Handle user response at facts_approval checkpoint (unstructured schema Fact stage).

    User can:
    - Approve: Accept proposed facts, move to graph construction
    - Modify: Request fact changes
    - Cancel: Go back to entity review
    """
    intent = classify_user_intent(message)

    logger.info(f"[checkpoint_handler] Facts approval intent: {intent}")

    if intent == "approve":
        session["approved_facts"] = session.get("proposed_facts", [])
        session["current_phase"] = "graph_construction"
        session["checkpoint"] = None
        session["awaiting_user_action"] = False

        response = f"Approved {len(session['approved_facts'])} fact types. Moving to graph construction..."

    elif intent == "modify":
        session["awaiting_user_action"] = True
        response = """What would you like to change about the facts?

You can:
• "Remove [FactType]" to drop a fact triple
• "Add [Subject]-[Relation]->[Object]" to add a new one
• Describe changes in natural language

What modification do you need?"""

    elif intent == "cancel":
        session["unstructured_stage"] = "ner"
        session["checkpoint"] = None
        session["awaiting_user_action"] = False
        response = "Going back to entity review. You can modify or re-approve the entities."

    else:
        response = """Would you like to:

• **Approve** these facts and build the graph?
• **Modify** the fact triples?
• **Cancel** and go back to entities?

Please let me know!"""

    session["messages"].append(HumanMessage(content=message))
    session["messages"].append(AIMessage(content=response))

    return session


def handle_build_approval(session: Dict[str, Any], message: str) -> Dict[str, Any]:
    """
    Handle user response at build_approval checkpoint.

    This is the final confirmation before actually building the graph.

    User can:
    - Approve: Build the graph
    - Cancel: Don't build yet
    """
    intent = classify_user_intent(message)

    logger.info(f"[checkpoint_handler] Build approval intent: {intent}")

    if intent == "approve":
        # User approved - actually build the graph
        session["checkpoint"] = None
        session["awaiting_user_action"] = False

        construction_plan = session.get("approved_construction_plan", {})

        try:
            build_result = construct_domain_graph(construction_plan)

            if build_result.get("status") in ("success", "partial"):
                # Also build unstructured pipeline if text files exist
                unstructured_files = [f for f in session.get("approved_files", []) if f.lower().endswith(('.md', '.txt'))]
                if unstructured_files:
                    logger.info(f"[checkpoint_handler] Building unstructured pipeline for {unstructured_files}")
                    settings = get_settings()
                    import_dir = Path(settings.data_import_dir)

                    for text_file in unstructured_files:
                        file_path = str(import_dir / text_file)
                        # build_lexical_graph is async — run in separate thread
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                            future = executor.submit(asyncio.run, build_lexical_graph(file_path))
                            lexical_result = future.result()
                        if lexical_result.get("status") == "error":
                            logger.warning(f"[checkpoint_handler] Lexical graph failed for {text_file}: {lexical_result.get('error_message')}")
                            continue
                        logger.info(f"[checkpoint_handler] Lexical graph built for {text_file}")

                    # Extract entities from chunks
                    subject_result = build_subject_graph()
                    logger.info(f"[checkpoint_handler] Subject graph result: {subject_result.get('status')}")

                    # Link entities to domain graph nodes
                    resolve_result = resolve_entities()
                    logger.info(f"[checkpoint_handler] Entity resolution result: {resolve_result.get('status')}")

                    # Create vector index for semantic search
                    vector_result = create_vector_index()
                    logger.info(f"[checkpoint_handler] Vector index result: {vector_result.get('status')}")

                # Fetch actual graph statistics (after everything is built)
                stats_result = get_graph_stats()
                nodes_info = stats_result.get("nodes", []) if stats_result.get("status") == "success" else []
                rels_info = stats_result.get("relationships", []) if stats_result.get("status") == "success" else []

                total_nodes = sum(r.get("count", 0) for r in nodes_info)
                total_rels = sum(r.get("count", 0) for r in rels_info)

                session["graph_built"] = True
                session["graph_stats"] = {
                    "nodes_created": total_nodes,
                    "relationships_created": total_rels
                }
                session["current_phase"] = "query"

                response_lines = [
                    "✅ Graph built successfully!",
                    "",
                    "**Statistics:**",
                    f"• Total nodes: {total_nodes}",
                    f"• Total relationships: {total_rels}",
                ]

                if nodes_info:
                    node_types_str = ", ".join(f"{r.get('label', '?')} ({r.get('count', 0)})" for r in nodes_info)
                    response_lines.append(f"• Node types: {node_types_str}")
                if rels_info:
                    rel_types_str = ", ".join(f"{r.get('relationshipType', '?')} ({r.get('count', 0)})" for r in rels_info)
                    response_lines.append(f"• Relationship types: {rel_types_str}")

                response_lines.extend([
                    "",
                    "Your knowledge graph is ready! Ask questions about your data.",
                    "",
                    "Try asking:",
                    '• "What suppliers are in the graph?"',
                    '• "Show me the relationships between parts and suppliers"',
                    '• "What products contain which assemblies?"',
                    "",
                    "What would you like to know?"
                ])

                response = "\n".join(response_lines)

                if build_result.get("status") == "partial":
                    errors = build_result.get("errors", [])
                    error_summary = "; ".join(f"{e['name']}: {e['error']}" for e in errors)
                    response += f"\n\n⚠️ Some items had errors: {error_summary}"

            else:
                # Build failed
                error_msg = build_result.get("message", "Unknown error during graph construction")
                session["graph_built"] = False
                session["current_phase"] = "graph_construction"
                session["awaiting_user_action"] = False
                response = f"❌ Graph build failed: {error_msg}\n\nWould you like to try again or modify the schema?"

        except Exception as e:
            logger.error(f"[checkpoint_handler] Graph build exception: {e}")
            session["graph_built"] = False
            session["current_phase"] = "graph_construction"
            session["awaiting_user_action"] = False
            response = f"❌ Graph build error: {str(e)}\n\nWould you like to try again or modify the schema?"

        session["messages"].append(HumanMessage(content=message))
        session["messages"].append(AIMessage(content=response))

        logger.info("[checkpoint_handler] Graph build completed")

    elif intent == "cancel":
        # User doesn't want to build yet
        session["checkpoint"] = None
        session["awaiting_user_action"] = False
        session["current_phase"] = "schema_proposal"

        response = "No problem! I won't build the graph yet. Would you like to review or modify the schema?"

        session["messages"].append(HumanMessage(content=message))
        session["messages"].append(AIMessage(content=response))

        logger.info("[checkpoint_handler] User cancelled graph build")

    else:
        # Unclear intent
        response = """Would you like to proceed with building the graph?

• Type **"yes"** to build the graph
• Type **"no"** or **"cancel"** to go back

This will create the graph in your Neo4j database."""

        session["messages"].append(HumanMessage(content=message))
        session["messages"].append(AIMessage(content=response))

        logger.info("[checkpoint_handler] Unclear intent at build approval")

    return session
