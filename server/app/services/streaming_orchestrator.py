from typing import AsyncGenerator
import json
from datetime import datetime
from app.core.enums import Phase, FlowType, MessageRole
from app.core.state import Message
from app.services.state_store import state_store
from app.services.intent_classifier import classify_intent
from app.services.file_parser import detect_data_in_message


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that converts datetime to ISO format string."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def sse_event(event_type: str, data: dict) -> str:
    """Format data as SSE event with datetime serialization."""
    return f"event: {event_type}\ndata: {json.dumps(data, cls=DateTimeEncoder)}\n\n"




async def orchestrate_stream(
    session_id: str,
    user_id: str,
    message: str,
    token: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Streaming orchestrator - yields SSE events as processing happens.

    Events:
    - thinking: Status updates
    - token: Response text streaming
    - complete: Final result with session state
    - error: Error occurred
    """

    import logging
    logger = logging.getLogger(__name__)

    try:
        # Load or create session
        state = await state_store.load(session_id)

        if state:
            logger.info(f"[ORCHESTRATOR] Loaded EXISTING session {session_id} — flow={state.flow_type.value}, phase={state.phase.value}, kb={state.knowledge_base_id}")
        else:
            logger.info(f"[ORCHESTRATOR] NEW session {session_id} — classifying intent for: \"{message}\"")

        if not state:
            yield sse_event("thinking", {"content": "Analyzing your request..."})
            flow_type = await classify_intent(message)
            logger.info(f"[ORCHESTRATOR] Classification result: {flow_type.value}")
            state = await state_store.create(session_id, user_id, flow_type)

            # QUERY flow: load KB from Supabase before routing to query handler
            if flow_type.value == "query":
                from app.services.kb_service import get_user_kbs
                kbs = get_user_kbs(user_id, token=token)

                if len(kbs) == 0:
                    # No KBs — offer to create one
                    response_text = "You don't have any knowledge bases yet. Would you like to create one? I can help you organize your data into a searchable knowledge base."
                    for word in response_text.split():
                        yield sse_event("token", {"delta": word + " "})
                    state.messages.append(Message(role=MessageRole.ASSISTANT, content=response_text))
                    await state_store.save(state)
                    yield sse_event("complete", {
                        "message": response_text, "session_id": session_id,
                        "phase": state.phase.value, "checkpoint": None,
                        "metadata": {"flow_type": state.flow_type.value}
                    })
                    return

                elif len(kbs) == 1:
                    # Single KB — auto-select
                    kb = kbs[0]
                    state.knowledge_base_id = kb["id"]
                    state.knowledge_base_name = kb["name"]
                    state.approved_schema = kb["schema"]
                    await state_store.save(state)
                    logger.info(f"[ORCHESTRATOR] Auto-selected KB: {kb['id']} ({kb['name']})")

                else:
                    # Multiple KBs — ask user to pick
                    kb_list = "\n".join([f"  {i+1}. {kb['name']}" for i, kb in enumerate(kbs)])
                    response_text = f"You have multiple knowledge bases. Which one would you like to query?\n\n{kb_list}\n\nReply with the number or name."
                    for word in response_text.split():
                        yield sse_event("token", {"delta": word + " "})
                    state.messages.append(Message(role=MessageRole.ASSISTANT, content=response_text))
                    state.pending_kb_options = [{"id": kb["id"], "name": kb["name"]} for kb in kbs]
                    await state_store.save(state)
                    yield sse_event("complete", {
                        "message": response_text, "session_id": session_id,
                        "phase": state.phase.value, "checkpoint": None,
                        "metadata": {"flow_type": state.flow_type.value}
                    })
                    return

            # EXTEND flow: load existing KB to extend before routing to FILES handler
            if flow_type.value == "extend":
                from app.services.kb_service import get_user_kbs as _get_kbs_extend
                kbs = _get_kbs_extend(user_id, token=token)

                if len(kbs) == 0:
                    # No KBs to extend — redirect to BUILD
                    state.flow_type = FlowType.BUILD
                    state.phase = Phase.INTENT
                    await state_store.save(state)
                    logger.info("[ORCHESTRATOR] EXTEND requested but no KBs exist — redirected to BUILD")

                elif len(kbs) == 1:
                    kb = kbs[0]
                    state.knowledge_base_id = kb["id"]
                    state.knowledge_base_name = kb["name"]
                    state.approved_schema = kb["schema"]
                    state.user_goal = f"Extend {kb['name']}"
                    await state_store.save(state)
                    logger.info(f"[ORCHESTRATOR] EXTEND: auto-selected KB: {kb['id']} ({kb['name']})")

                else:
                    kb_list = "\n".join([f"  {i+1}. {kb['name']}" for i, kb in enumerate(kbs)])
                    response_text = f"Which knowledge base would you like to add data to?\n\n{kb_list}\n\nReply with the number or name."
                    for word in response_text.split():
                        yield sse_event("token", {"delta": word + " "})
                    state.messages.append(Message(role=MessageRole.ASSISTANT, content=response_text))
                    state.pending_kb_options = [{"id": kb["id"], "name": kb["name"]} for kb in kbs]
                    await state_store.save(state)
                    yield sse_event("complete", {
                        "message": response_text, "session_id": session_id,
                        "phase": state.phase.value, "checkpoint": None,
                        "metadata": {"flow_type": state.flow_type.value}
                    })
                    return

        # Handle pending KB selection (user chose from multi-KB list)
        if state.pending_kb_options and not state.knowledge_base_id:
            from app.services.kb_service import get_kb_by_id
            selected_kb = None
            msg_lower = message.strip().lower()

            for i, kb_opt in enumerate(state.pending_kb_options):
                if msg_lower == str(i + 1) or msg_lower == kb_opt["name"].lower():
                    selected_kb = kb_opt
                    break

            if selected_kb:
                kb_data = get_kb_by_id(selected_kb["id"], state.user_id, token=token)
                if kb_data:
                    state.knowledge_base_id = kb_data["id"]
                    state.knowledge_base_name = kb_data["name"]
                    state.approved_schema = kb_data["schema"]
                    state.pending_kb_options = None
                    state.messages.append(Message(role=MessageRole.USER, content=message))
                    if state.flow_type == FlowType.EXTEND:
                        state.user_goal = f"Extend {kb_data['name']}"
                        message = f"I selected {kb_data['name']}. I want to add more data to it."
                    else:
                        message = f"I selected {kb_data['name']}. Please help me query it."
                    await state_store.save(state)
                    logger.info(f"[ORCHESTRATOR] User selected KB: {kb_data['id']} ({kb_data['name']})")

        logger.info(f"[ORCHESTRATOR] Session {session_id} - Current phase: {state.phase}")

        # Detect if message contains pasted CSV/JSON data
        detected_file = detect_data_in_message(message)
        if detected_file:
            state.files.append(detected_file)
            await state_store.save(state)
            logger.info(f"[ORCHESTRATOR] Detected pasted {detected_file.type} data - added to session.files")

        # Auto-continuation loop: process phases until we hit a checkpoint or QUERY
        max_iterations = 5  # Safety limit
        iteration = 0
        continue_message = message  # First iteration uses user message, then "continue"

        while iteration < max_iterations:
            iteration += 1
            phase_before = state.phase
            logger.info(f"[ORCHESTRATOR] Iteration {iteration} - Phase: {phase_before}")

            # Route to phase handler
            if state.phase == Phase.INTENT:
                logger.info(f"[ORCHESTRATOR] Routing to INTENT phase handler")
                async for event in handle_intent_stream(state, continue_message):
                    yield event

            elif state.phase == Phase.FILES:
                logger.info(f"[ORCHESTRATOR] Routing to FILES phase handler")
                async for event in handle_files_stream(state, continue_message):
                    yield event

            elif state.phase == Phase.SCHEMA:
                logger.info(f"[ORCHESTRATOR] Routing to SCHEMA phase handler")
                async for event in handle_schema_stream(state, continue_message):
                    yield event

            elif state.phase == Phase.BUILD:
                logger.info(f"[ORCHESTRATOR] Routing to BUILD phase handler")
                async for event in handle_build_stream(state, continue_message, token=token):
                    yield event

            elif state.phase == Phase.QUERY:
                logger.info(f"[ORCHESTRATOR] Routing to QUERY phase handler")
                async for event in handle_query_stream(state, continue_message):
                    yield event
                # Reload state before breaking (QUERY is terminal)
                state = await state_store.load(session_id)
                break  # QUERY is terminal phase

            else:
                raise ValueError(f"Unknown phase: {state.phase}")

            # Reload state after processing
            state = await state_store.load(session_id)
            phase_after = state.phase
            has_checkpoint = state.checkpoint is not None

            logger.info(f"[ORCHESTRATOR] After iteration {iteration} - Phase: {phase_after}, Checkpoint: {has_checkpoint}")

            # Check if we should auto-continue
            if phase_after != phase_before and not has_checkpoint and phase_after != Phase.QUERY:
                logger.info(f"[ORCHESTRATOR] ✓ Auto-continuing: {phase_before} → {phase_after}")
                continue_message = "continue"  # Subsequent iterations use generic message
                continue  # Next iteration

            else:
                # Stop: either no phase change, or hit a checkpoint, or reached QUERY
                logger.info(f"[ORCHESTRATOR] Stopping auto-continuation (phase_changed={phase_after != phase_before}, has_checkpoint={has_checkpoint})")
                break

        # Send completion event
        completion_data = {
            "message": state.messages[-1].content if state.messages else "",
            "session_id": state.session_id,
            "phase": state.phase.value,
            "checkpoint": state.checkpoint.model_dump(mode='json') if state.checkpoint else None,
            "metadata": {
                "flow_type": state.flow_type.value,
            }
        }
        logger.info(f"[ORCHESTRATOR] Sending complete event - Phase: {completion_data['phase']}")
        yield sse_event("complete", completion_data)

    except Exception as e:
        logger.error(f"[ORCHESTRATOR] Error: {str(e)}")
        yield sse_event("error", {"message": str(e)})


# =============================================================================
# Phase Handlers - Streaming Versions
# =============================================================================

async def handle_intent_stream(state, message: str) -> AsyncGenerator[str, None]:
    """INTENT phase - run intent agent with streaming."""
    yield sse_event("thinking", {"content": "Understanding your intent..."})

    # Import here to avoid circular dependency
    from app.agents.intent_agent import run_intent_agent

    # Run intent agent
    response_text, updated_state = await run_intent_agent(state, message)

    # Stream response token by token
    for word in response_text.split():
        yield sse_event("token", {"delta": word + " "})

    # Save updated state
    await state_store.save(updated_state)


async def handle_files_stream(state, message: str) -> AsyncGenerator[str, None]:
    """FILES phase - use build agent to request/analyze files."""
    yield sse_event("thinking", {"content": "Analyzing data requirements..."})

    from app.agents.build_agent import stream_build_agent

    async for token in stream_build_agent(state, message):
        yield sse_event("token", {"delta": token})

    await state_store.save(state)


async def handle_schema_stream(state, message: str) -> AsyncGenerator[str, None]:
    """SCHEMA phase - use build agent to propose/refine schema."""
    yield sse_event("thinking", {"content": "Designing graph schema..."})

    from app.agents.build_agent import stream_build_agent

    async for token in stream_build_agent(state, message):
        yield sse_event("token", {"delta": token})

    await state_store.save(state)


async def handle_build_stream(state, message: str, token: str | None = None) -> AsyncGenerator[str, None]:
    """BUILD phase - construct graph from approved schema."""
    import logging
    logger = logging.getLogger(__name__)

    logger.info("[BUILD_STREAM] Starting graph construction")

    # Get approved schema and files
    schema = state.proposed_schema
    files = state.files

    # Validate inputs
    if not schema:
        response_text = "Error: No schema found. Please go back to schema design phase."
        for word in response_text.split():
            yield sse_event("token", {"delta": word + " "})

        state.messages.append(Message(
            role=MessageRole.ASSISTANT,
            content=response_text
        ))
        await state_store.save(state)
        return

    if not files or len(files) == 0:
        response_text = "Error: No files found. Please upload data files first."
        for word in response_text.split():
            yield sse_event("token", {"delta": word + " "})

        state.messages.append(Message(
            role=MessageRole.ASSISTANT,
            content=response_text
        ))
        await state_store.save(state)
        return

    # Show what we're building
    node_count = len(schema.get("nodes", []))
    rel_count = len(schema.get("relationships", []))

    yield sse_event("thinking", {
        "content": f"Building graph with {node_count} node types and {rel_count} relationship types..."
    })

    # Import graph builder service
    from app.services.graph_builder import build_graph

    # Phase 1: Creating constraints
    yield sse_event("thinking", {"content": "Creating uniqueness constraints..."})

    # Phase 2 & 3: Import nodes and relationships
    node_labels = [node["label"] for node in schema.get("nodes", [])]
    for i, label in enumerate(node_labels, 1):
        yield sse_event("thinking", {
            "content": f"Importing {label} nodes ({i}/{node_count})..."
        })

    # Reuse existing KB ID for EXTEND, generate new for BUILD
    extending = state.knowledge_base_id is not None
    if extending:
        kb_id = state.knowledge_base_id
        kb_name = state.knowledge_base_name or "My Knowledge Base"
        logger.info(f"[BUILD_STREAM] Extending existing KB: {kb_id} ({kb_name})")
    else:
        import uuid
        kb_id = f"kb_{uuid.uuid4().hex[:12]}"
        kb_name = state.user_goal or "My Knowledge Base"
        logger.info(f"[BUILD_STREAM] Generated KB ID: {kb_id}, name: {kb_name}")

    # Execute graph construction with KB isolation
    try:
        result = build_graph(kb_id, schema, files)

        if result["status"] in ["success", "partial"]:
            # Show relationship creation progress
            rel_types = result.get("relationships_imported", [])
            for i, rel in enumerate(rel_types, 1):
                rel_type = rel["type"]
                count = rel["count"]
                yield sse_event("thinking", {
                    "content": f"Creating {rel_type} relationships ({count} links)..."
                })

            # Build success message
            total_nodes = result.get("total_nodes", 0)
            total_rels = result.get("total_relationships", 0)
            nodes_imported = result.get("nodes_imported", [])

            # Create detailed breakdown
            node_summary = ", ".join([f"{n['count']} {n['label']}" for n in nodes_imported[:3]])
            if len(nodes_imported) > 3:
                node_summary += f", and {len(nodes_imported) - 3} more types"

            if extending:
                response_text = (
                    f"✓ Knowledge base \"{kb_name}\" extended! "
                    f"Added {total_nodes} nodes ({node_summary}) "
                    f"and {total_rels} relationships. "
                    f"Your knowledge base is updated and ready to explore!"
                )
            else:
                response_text = (
                    f"✓ Knowledge base \"{kb_name}\" built successfully! "
                    f"Created {total_nodes} nodes ({node_summary}) "
                    f"and {total_rels} relationships across {node_count} node types. "
                    f"Your data is now connected and ready to explore!"
                )

            # Check for partial errors
            if result["status"] == "partial" and result.get("errors"):
                error_summary = "; ".join(result["errors"][:2])
                response_text += f"\n\nNote: Some issues occurred: {error_summary}"

            logger.info(f"[BUILD_STREAM] ✓ Graph built: {total_nodes} nodes, {total_rels} relationships")

            # Mark graph as built and move to QUERY phase
            state.graph_built = True
            state.phase = Phase.QUERY
            state.approved_schema = schema
            state.build_status = "success"
            state.knowledge_base_id = kb_id
            state.knowledge_base_name = kb_name

            # Persist KB metadata to Supabase (create new or update existing)
            try:
                if extending:
                    from app.services.kb_service import update_kb_schema
                    kb_result = update_kb_schema(kb_id, state.user_id, schema, token=token)
                else:
                    from app.services.kb_service import create_kb
                    kb_result = create_kb(
                        kb_id=kb_id,
                        owner_id=state.user_id,
                        name=kb_name,
                        description=state.user_goal,
                        schema=schema,
                        token=token
                    )
                if kb_result["status"] == "success":
                    logger.info(f"[BUILD_STREAM] ✓ KB {'updated' if extending else 'saved'} in Supabase: {kb_id}")
                else:
                    logger.warning(f"[BUILD_STREAM] KB {'update' if extending else 'save'} failed: {kb_result.get('error')}")
            except Exception as kb_err:
                logger.warning(f"[BUILD_STREAM] KB Supabase operation failed: {kb_err}")
                # Non-fatal — graph is built, KB just won't persist across sessions yet

        else:
            # Build failed
            error_msg = result.get("error_message", "Unknown error")
            response_text = f"Graph construction failed: {error_msg}"
            state.build_status = "failed"
            logger.error(f"[BUILD_STREAM] Graph construction failed: {error_msg}")

    except Exception as e:
        response_text = f"Error during graph construction: {str(e)}"
        state.build_status = "failed"
        logger.error(f"[BUILD_STREAM] Exception: {str(e)}", exc_info=True)

    # Stream response to user
    for word in response_text.split():
        yield sse_event("token", {"delta": word + " "})

    # Save message and state
    state.messages.append(Message(
        role=MessageRole.ASSISTANT,
        content=response_text
    ))

    await state_store.save(state)
    logger.info(f"[BUILD_STREAM] Final phase: {state.phase}, Graph built: {state.graph_built}")


async def handle_query_stream(state, message: str) -> AsyncGenerator[str, None]:
    """QUERY phase - answer questions about the knowledge graph."""
    yield sse_event("thinking", {"content": "Searching knowledge graph..."})

    from app.agents.query_agent import stream_query_agent

    async for token in stream_query_agent(state, message):
        yield sse_event("token", {"delta": token})

    await state_store.save(state)
