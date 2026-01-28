"""
User Intent Agent API Routes.
Handles HTTP endpoints for the User Intent Agent.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage

from app.schemas.user_intent import ChatRequest, ChatResponse, SessionStateResponse
from app.agents.graphs.user_intent_graph import user_intent_graph
from app.core.session_manager import get_session, save_session

# Setup logging
logger = logging.getLogger(__name__)

# Create router with prefix and tags
router = APIRouter(
    prefix="/api/user-intent",
    tags=["User Intent Agent"]
)


def get_or_create_session(session_id: str) -> Dict[str, Any]:
    """
    Retrieves an existing session or creates a new one.

    Args:
        session_id: Unique session identifier

    Returns:
        Session state dictionary
    """
    # Load from Redis
    session_state = get_session(session_id)

    # If empty, initialize with default state
    if not session_state:
        session_state = {
            "messages": [],
            "perceived_user_goal": None,
            "approved_user_goal": None,
            "current_phase": "user_intent"
        }
        save_session(session_id, session_state)

    return session_state


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Chat endpoint for the User Intent Agent.
    
    Handles user messages, invokes the agent graph, and returns responses.
    
    Args:
        request: ChatRequest containing user message and session ID
    
    Returns:
        ChatResponse with agent's reply and updated state
    
    Raises:
        HTTPException: If graph invocation fails
    """
    try:
        # Get or create session from Redis
        session_state = get_or_create_session(request.session_id)

        logger.info(f"[user_intent] Session {request.session_id} - Processing message: {request.message[:50]}...")

        # Add user message to state
        session_state["messages"].append(
            HumanMessage(content=request.message)
        )

        # Invoke the agent graph
        result = user_intent_graph.invoke(session_state)

        # Update session in Redis
        save_session(request.session_id, result)

        logger.info(f"[user_intent] Session {request.session_id} - Approved goal: {result.get('approved_user_goal')}")

        # Extract the last AI message
        last_message = result["messages"][-1]
        ai_response = last_message.content if hasattr(last_message, "content") else str(last_message)

        # Determine next phase
        current_phase = "user_intent"
        if result.get("approved_user_goal"):
            current_phase = "file_suggestion"

        # Build and return response
        return ChatResponse(
            message=ai_response,
            session_id=request.session_id,
            perceived_user_goal=result.get("perceived_user_goal"),
            approved_user_goal=result.get("approved_user_goal"),
            current_phase=current_phase,
            status="success"
        )

    except Exception as e:
        logger.error(f"[user_intent] Error processing message: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing message: {str(e)}"
        )


@router.get("/session/{session_id}", response_model=SessionStateResponse)
async def get_session_state(session_id: str) -> SessionStateResponse:
    """
    Retrieves the current state of a session.

    Useful for debugging or checking conversation status.

    Args:
        session_id: Session identifier

    Returns:
        SessionStateResponse with current session state
    """
    # Load from Redis
    session = get_session(session_id)

    if not session:
        return SessionStateResponse(
            session_id=session_id,
            messages_count=0,
            perceived_user_goal=None,
            approved_user_goal=None,
            exists=False
        )

    return SessionStateResponse(
        session_id=session_id,
        messages_count=len(session.get("messages", [])),
        perceived_user_goal=session.get("perceived_user_goal"),
        approved_user_goal=session.get("approved_user_goal"),
        exists=True
    )


@router.delete("/session/{session_id}")
async def delete_session_endpoint(session_id: str) -> Dict[str, str]:
    """
    Deletes a session.

    Useful for starting a new conversation or clearing memory.

    Args:
        session_id: Session identifier

    Returns:
        Confirmation message
    """
    from app.core.session_manager import delete_session

    # Check if session exists
    session = get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )

    # Delete from Redis
    delete_session(session_id)
    logger.info(f"[user_intent] Session {session_id} deleted")

    return {"message": f"Session {session_id} deleted successfully"}
