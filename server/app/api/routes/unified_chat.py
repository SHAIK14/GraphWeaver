"""
Unified Chat Endpoint - Single entry point for all user interactions.

This endpoint replaces the need for frontend to call multiple agent endpoints.
It routes messages to the correct agent based on session state and handles checkpoints.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from app.core.session_manager import get_session, save_session
from app.services.chat_router import route_to_agent
from app.services.checkpoint_handler import handle_checkpoint_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["unified-chat"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class ChatRequest(BaseModel):
    """Request body for unified chat endpoint."""
    session_id: str
    message: str
    action: Optional[str] = None  # Optional: explicit action from button click


class ChatResponse(BaseModel):
    """Response from unified chat endpoint."""
    session_id: str
    message: str
    current_phase: str
    checkpoint: Optional[str] = None
    awaiting_user_action: bool = False
    proposed_data: Optional[Dict[str, Any]] = None
    actions: Optional[Dict[str, str]] = None
    graph_built: bool = False


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_or_create_session(session_id: str) -> Dict[str, Any]:
    """
    Get existing session or create new one with default state.

    Initial state includes:
    - current_phase: "user_intent" (start from the beginning)
    - checkpoint: None (no checkpoint active)
    - awaiting_user_action: False
    - messages: empty list
    """
    session = get_session(session_id)

    if not session:
        session = {
            "messages": [],
            "current_phase": "user_intent",
            "checkpoint": None,
            "awaiting_user_action": False,

            # User Intent phase
            "perceived_user_goal": None,
            "approved_user_goal": None,

            # File Suggestion phase
            "all_available_files": None,
            "proposed_files": None,
            "approved_files": None,

            # Schema Proposal phase
            "proposed_construction_plan": None,
            "approved_construction_plan": None,

            # Graph Construction phase
            "graph_built": False,
            "graph_stats": None,
        }
        save_session(session_id, session)
        logger.info(f"[unified_chat] Created new session: {session_id}")

    return session


def build_response(session: Dict[str, Any]) -> ChatResponse:
    """
    Build ChatResponse from session state.

    Extracts the last AI message and current state information.
    """
    # Extract last AI message
    messages = session.get("messages", [])
    last_message = ""
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content:
            # Skip tool messages
            if not hasattr(msg, "tool_call_id"):
                last_message = msg.content
                break

    # Build response
    return ChatResponse(
        session_id=session.get("session_id", ""),
        message=last_message or "Processing...",
        current_phase=session.get("current_phase", "user_intent"),
        checkpoint=session.get("checkpoint"),
        awaiting_user_action=session.get("awaiting_user_action", False),
        proposed_data=session.get("proposed_data"),
        actions=session.get("actions"),
        graph_built=session.get("graph_built", False),
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/", response_model=ChatResponse)
async def unified_chat(request: ChatRequest) -> ChatResponse:
    """
    Unified chat endpoint - routes to correct agent based on session state.

    This is the ONLY endpoint frontend needs to call for all interactions.

    Flow:
    1. Load session from Redis
    2. Check if at checkpoint (awaiting user action)
       - Yes: Handle checkpoint response (approve/modify/cancel)
       - No: Route to current phase's agent
    3. Save updated session to Redis
    4. Return response with checkpoint info (if applicable)

    Args:
        request: ChatRequest with session_id and message

    Returns:
        ChatResponse with message, phase, checkpoint status

    Example:
        POST /api/chat
        {
          "session_id": "abc123",
          "message": "I want to build a supply chain graph"
        }

        Response:
        {
          "message": "I understand you want to build a supply chain graph...",
          "current_phase": "user_intent",
          "checkpoint": null,
          "awaiting_user_action": false
        }
    """
    try:
        # Load or create session
        session = get_or_create_session(request.session_id)
        session["session_id"] = request.session_id  # Ensure session_id is in state

        logger.info(
            f"[unified_chat] Session {request.session_id} - "
            f"Phase: {session.get('current_phase')}, "
            f"Checkpoint: {session.get('checkpoint')}, "
            f"Message: {request.message[:50]}..."
        )

        phase_before = session.get("current_phase")

        # Route based on whether we're at a checkpoint
        if session.get("awaiting_user_action"):
            logger.info(f"[unified_chat] Handling checkpoint response at {session.get('checkpoint')}")
            result = handle_checkpoint_response(session, request.message)
        else:
            logger.info(f"[unified_chat] Routing to agent for phase {session.get('current_phase')}")
            result = route_to_agent(session, request.message)

        # Auto-continue: if phase changed and we're not waiting for user, invoke next agent immediately.
        # This ensures checkpoint approval → next agent runs in one request instead of requiring a dummy message.
        phase_after = result.get("current_phase")
        if (phase_after != phase_before
                and not result.get("awaiting_user_action")
                and phase_after != "query"):
            logger.info(f"[unified_chat] Auto-continuing from {phase_before} → {phase_after}")
            result = route_to_agent(result, "continue")

        # Save updated session
        save_session(request.session_id, result)

        logger.info(
            f"[unified_chat] Session {request.session_id} completed - "
            f"New phase: {result.get('current_phase')}, "
            f"Checkpoint: {result.get('checkpoint')}"
        )

        # Build and return response
        return build_response(result)

    except Exception as e:
        logger.error(f"[unified_chat] Error processing message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing message: {str(e)}"
        )


@router.get("/session/{session_id}")
async def get_session_state(session_id: str):
    """
    Get current session state (for debugging/monitoring).

    Returns:
        Dict with session state including phase, checkpoint, and data
    """
    session = get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "current_phase": session.get("current_phase"),
        "checkpoint": session.get("checkpoint"),
        "awaiting_user_action": session.get("awaiting_user_action"),
        "approved_user_goal": session.get("approved_user_goal"),
        "approved_files": session.get("approved_files"),
        "approved_construction_plan": session.get("approved_construction_plan") is not None,
        "graph_built": session.get("graph_built", False),
        "message_count": len(session.get("messages", [])),
    }


@router.delete("/session/{session_id}")
async def delete_session_endpoint(session_id: str):
    """
    Delete session and reset state.

    Use this to start a new conversation from scratch.
    """
    from app.core.session_manager import delete_session

    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    delete_session(session_id)
    logger.info(f"[unified_chat] Session {session_id} deleted")

    return {"message": f"Session {session_id} deleted successfully"}
