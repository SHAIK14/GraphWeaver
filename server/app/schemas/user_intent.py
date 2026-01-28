

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """
    Request model for chat endpoint.
    
    This is what the user sends to the API.
    """
    message: str = Field(
        ...,
        description="The user's message",
        min_length=1,
        examples=["I want a bill of materials graph"]
    )
    
    session_id: str = Field(
        ...,
        description="Unique session identifier for conversation continuity",
        min_length=1,
        examples=["user_abc123"]
    )


class ChatResponse(BaseModel):
    """
    Response model for chat endpoint.
    
    This is what the API returns to the user.
    """
    message: str = Field(
        ...,
        description="The agent's response message"
    )
    
    session_id: str = Field(
        ...,
        description="The session ID (echoed back)"
    )
    
    perceived_user_goal: Optional[Dict[str, str]] = Field(
        None,
        description="The perceived user goal (if set)"
    )
    
    approved_user_goal: Optional[Dict[str, str]] = Field(
        None,
        description="The approved user goal (if set)"
    )

    current_phase: str = Field(
        default="user_intent",
        description="Current workflow phase"
    )

    status: str = Field(
        default="success",
        description="Status of the request"
    )


class SessionStateResponse(BaseModel):
    """
    Response model for getting session state.
    
    Used to inspect the current state of a conversation.
    """
    session_id: str
    
    messages_count: int = Field(
        ...,
        description="Number of messages in the conversation"
    )
    
    perceived_user_goal: Optional[Dict[str, str]] = None
    
    approved_user_goal: Optional[Dict[str, str]] = None
    
    exists: bool = Field(
        ...,
        description="Whether the session exists"
    )
