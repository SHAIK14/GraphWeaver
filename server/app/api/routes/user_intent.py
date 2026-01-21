"""
User Intent Agent API Routes.
Handles HTTP endpoints for the User Intent Agent.
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage

from app.schemas.user_intent import ChatRequest, ChatResponse, SessionStateResponse
from app.agents.graphs.user_intent_graph import user_intent_graph

# Create router with prefix and tags
router = APIRouter(
    prefix="/api/user-intent",
    tags=["User Intent Agent"]
)

# In-memory session storage (⚠️ Not for production!)
# In production, use Redis, PostgreSQL, or proper session management
sessions: Dict[str, Dict[str, Any]] = {}


def get_or_create_session(session_id: str) -> Dict[str, Any]:
    """
    Retrieves an existing session or creates a new one.
    
    Args:
        session_id: Unique session identifier
    
    Returns:
        Session state dictionary
    """
    if session_id not in sessions:
        # Initialize new session with empty state
        sessions[session_id] = {
            "messages": [],
            "perceived_user_goal": None,
            "approved_user_goal": None
        }
    
    return sessions[session_id]


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
        # Get or create session
        session_state = get_or_create_session(request.session_id)
        
        # Add user message to state
        session_state["messages"].append(
            HumanMessage(content=request.message)
        )
        
        # Invoke the agent graph
        result = user_intent_graph.invoke(session_state)
        
        # Update session with result
        sessions[request.session_id] = result
        
        # Extract the last AI message
        last_message = result["messages"][-1]
        ai_response = last_message.content if hasattr(last_message, "content") else str(last_message)
        
        # Build and return response
        return ChatResponse(
            message=ai_response,
            session_id=request.session_id,
            perceived_user_goal=result.get("perceived_user_goal"),
            approved_user_goal=result.get("approved_user_goal"),
            status="success"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing message: {str(e)}"
        )


@router.get("/session/{session_id}", response_model=SessionStateResponse)
async def get_session(session_id: str) -> SessionStateResponse:
    """
    Retrieves the current state of a session.
    
    Useful for debugging or checking conversation status.
    
    Args:
        session_id: Session identifier
    
    Returns:
        SessionStateResponse with current session state
    """
    if session_id not in sessions:
        return SessionStateResponse(
            session_id=session_id,
            messages_count=0,
            perceived_user_goal=None,
            approved_user_goal=None,
            exists=False
        )
    
    session = sessions[session_id]
    
    return SessionStateResponse(
        session_id=session_id,
        messages_count=len(session["messages"]),
        perceived_user_goal=session.get("perceived_user_goal"),
        approved_user_goal=session.get("approved_user_goal"),
        exists=True
    )


@router.delete("/session/{session_id}")
async def delete_session(session_id: str) -> Dict[str, str]:
    """
    Deletes a session.
    
    Useful for starting a new conversation or clearing memory.
    
    Args:
        session_id: Session identifier
    
    Returns:
        Confirmation message
    """
    if session_id in sessions:
        del sessions[session_id]
        return {"message": f"Session {session_id} deleted successfully"}
    
    raise HTTPException(
        status_code=404,
        detail=f"Session {session_id} not found"
    )
