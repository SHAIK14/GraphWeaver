from typing import AsyncGenerator
import json
from app.core.enums import Phase, MessageRole
from app.core.state import Message
from app.services.state_store import state_store
from app.services.intent_classifier import classify_intent


# =============================================================================
# SSE Event Helpers
# =============================================================================

def sse_event(event_type: str, data: dict) -> str:
    """Format data as SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


# =============================================================================
# Streaming Orchestrator
# =============================================================================

async def orchestrate_stream(
    session_id: str,
    user_id: str,
    message: str,
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

        if not state:
            yield sse_event("thinking", {"content": "Analyzing your request..."})
            flow_type = await classify_intent(message)
            state = await state_store.create(session_id, user_id, flow_type)

        logger.info(f"[ORCHESTRATOR] Session {session_id} - Current phase: {state.phase}")

        # Route to phase handler
        if state.phase == Phase.INTENT:
            logger.info(f"[ORCHESTRATOR] Routing to INTENT phase handler")
            async for event in handle_intent_stream(state, message):
                yield event

        elif state.phase == Phase.FILES:
            logger.info(f"[ORCHESTRATOR] Routing to FILES phase handler")
            async for event in handle_files_stream(state, message):
                yield event

        elif state.phase == Phase.SCHEMA:
            logger.info(f"[ORCHESTRATOR] Routing to SCHEMA phase handler")
            async for event in handle_schema_stream(state, message):
                yield event

        elif state.phase == Phase.BUILD:
            logger.info(f"[ORCHESTRATOR] Routing to BUILD phase handler")
            async for event in handle_build_stream(state, message):
                yield event

        elif state.phase == Phase.QUERY:
            logger.info(f"[ORCHESTRATOR] Routing to QUERY phase handler")
            async for event in handle_query_stream(state, message):
                yield event
        else:
            raise ValueError(f"Unknown phase: {state.phase}")

        # Reload state after processing
        state = await state_store.load(session_id)
        logger.info(f"[ORCHESTRATOR] After processing - Phase: {state.phase}, Goal approved: {state.goal_approved}")

        # Send completion event
        completion_data = {
            "message": state.messages[-1].content if state.messages else "",
            "session_id": state.session_id,
            "phase": state.phase.value,
            "checkpoint": state.checkpoint.model_dump() if state.checkpoint else None,
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
    """FILES phase - streaming placeholder."""
    yield sse_event("thinking", {"content": "Scanning available files..."})

    # TODO: Implement actual files agent
    response_text = "Files phase - to be implemented"

    for word in response_text.split():
        yield sse_event("token", {"delta": word + " "})

    state.messages.append(Message(
        role=MessageRole.ASSISTANT,
        content=response_text
    ))
    await state_store.save(state)


async def handle_schema_stream(state, message: str) -> AsyncGenerator[str, None]:
    """SCHEMA phase - streaming placeholder."""
    yield sse_event("thinking", {"content": "Designing graph schema..."})

    # TODO: Implement actual schema agent
    response_text = "Schema phase - to be implemented"

    for word in response_text.split():
        yield sse_event("token", {"delta": word + " "})

    state.messages.append(Message(
        role=MessageRole.ASSISTANT,
        content=response_text
    ))
    await state_store.save(state)


async def handle_build_stream(state, message: str) -> AsyncGenerator[str, None]:
    """BUILD phase - streaming placeholder."""
    yield sse_event("thinking", {"content": "Constructing knowledge graph..."})

    # TODO: Implement actual graph construction
    response_text = "Build phase - to be implemented"

    for word in response_text.split():
        yield sse_event("token", {"delta": word + " "})

    state.messages.append(Message(
        role=MessageRole.ASSISTANT,
        content=response_text
    ))
    await state_store.save(state)


async def handle_query_stream(state, message: str) -> AsyncGenerator[str, None]:
    """QUERY phase - streaming placeholder."""
    yield sse_event("thinking", {"content": "Searching knowledge base..."})

    # TODO: Implement actual query agent
    response_text = "Query phase - to be implemented"

    for word in response_text.split():
        yield sse_event("token", {"delta": word + " "})

    state.messages.append(Message(
        role=MessageRole.ASSISTANT,
        content=response_text
    ))
    await state_store.save(state)
