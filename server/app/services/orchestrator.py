from typing import Dict, Any
from app.core.enums import FlowType, Phase
from app.core.state import SessionState
from app.services.state_store import state_store
from app.services.intent_classifier import classify_intent


async def orchestrate(
    session_id: str,
    user_id: str,
    message: str,
) -> Dict[str, Any]:

    state = await state_store.load(session_id)
    if not state:
        flow_type = await classify_intent(message)
        
        state = await state_store.create(session_id, user_id, flow_type)
        
    if state.phase == Phase.INTENT:
        state = await handle_intent_phase(state, message)
    elif state.phase == Phase.FILES:
        state = await handle_files_phase(state, message)
    elif state.phase == Phase.SCHEMA:
        state = await handle_schema_phase(state, message)
    elif state.phase == Phase.BUILD:
        state = await handle_build_phase(state, message)
    elif state.phase == Phase.QUERY:
        state = await handle_query_phase(state, message)
    else :
        raise ValueError(f"Unknown phase: {state.phase}")
        
    await state_store.save(state)
    
    
    response = {
        "message": state.messages[-1].content if state.messages else "",
        "session_id": state.session_id,
        "phase": state.phase.value,
        "checkpoint": state.checkpoint.model_dump() if state.checkpoint else None,
        "metadata": {
            "flow_type": state.flow_type.value,
        }
    }
    return response




async def handle_intent_phase(state: SessionState, message: str) -> SessionState:
    """Handle INTENT phase - clarify user's goal."""
    # TODO: Implement intent agent
    return state


async def handle_files_phase(state: SessionState, message: str) -> SessionState:
    """Handle FILES phase - suggest and approve files."""
    # TODO: Implement files agent
    return state


async def handle_schema_phase(state: SessionState, message: str) -> SessionState:
    """Handle SCHEMA phase - design graph structure."""
    # TODO: Implement schema agent
    return state


async def handle_build_phase(state: SessionState, message: str) -> SessionState:
    """Handle BUILD phase - construct graph."""
    # TODO: Implement graph construction
    return state


async def handle_query_phase(state: SessionState, message: str) -> SessionState:
    """Handle QUERY phase - answer questions."""
    # TODO: Implement query agent
    return state
