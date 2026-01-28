"""
API Routes for Schema Proposal Agent

Endpoints:
- POST /api/schema-proposal/chat - Send messages to the schema proposal workflow
- GET /api/schema-proposal/session/{session_id} - Get session state
- DELETE /api/schema-proposal/session/{session_id} - Clear session
"""

import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from app.agents.graphs.schema_proposal_graph import schema_proposal_graph
from app.core.session_manager import get_session, save_session

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/schema-proposal", tags=["schema-proposal"])


class SchemaProposalRequest(BaseModel):
    """Request to send a message to the schema proposal agent."""
    message: str = Field(..., min_length=1, description="User's message")
    session_id: str = Field(..., description="Unique session identifier")
    # Input from previous agents (required on first message)
    # No longer needed - will load from Redis
    # approved_user_goal: Optional[Dict[str, Any]] = Field(
    #     None, description="User goal from Intent Agent"
    # )
    # approved_files: Optional[List[str]] = Field(
    #     None, description="Approved files from File Suggestion Agent"
    # )


class SchemaProposalResponse(BaseModel):
    """Response from the schema proposal agent."""
    message: str = Field(..., description="Agent's response")
    session_id: str
    # State from this agent
    proposed_construction_plan: Optional[Dict[str, Any]] = None
    approved_construction_plan: Optional[Dict[str, Any]] = None
    feedback: Optional[str] = None
    iteration_count: int = 0
    current_agent: Optional[str] = None
    # Pass-through from previous agents
    approved_user_goal: Optional[Dict[str, Any]] = None
    approved_files: Optional[List[str]] = None
    current_phase: str = "schema_proposal"
    status: str = "success"


class SessionStateResponse(BaseModel):
    """Response for session state query."""
    session_id: str
    exists: bool
    messages_count: int = 0
    proposed_construction_plan: Optional[Dict[str, Any]] = None
    approved_construction_plan: Optional[Dict[str, Any]] = None
    feedback: Optional[str] = None
    iteration_count: int = 0


# =============================================================================
# SESSION MANAGEMENT (Redis)
# =============================================================================

def get_or_create_session_state(session_id: str) -> Dict[str, Any]:
    """Get existing session from Redis or create a new one."""
    # Load from Redis
    session_state = get_session(session_id)

    if not session_state:
        logger.info(f"Creating new session: {session_id}")
        session_state = {
            "messages": [],
            "approved_user_goal": None,
            "approved_files": None,
            "proposed_construction_plan": None,
            "approved_construction_plan": None,
            "feedback": "",
            "current_agent": "proposal",
            "current_phase": "schema_proposal",
            "iteration_count": 0
        }
        save_session(session_id, session_state)

    return session_state


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("/chat", response_model=SchemaProposalResponse)
async def chat(request: SchemaProposalRequest):
    """
    Send a message to the schema proposal workflow.

    The workflow will:
    1. Analyze approved files to propose a construction plan
    2. Have the critic review the plan
    3. Iterate until the plan is valid or max iterations reached

    First message should include approved_user_goal and approved_files
    from previous agents.
    """
    logger.info(f"Chat request - Session: {request.session_id}")
    logger.debug(f"Message: {request.message}")

    try:
        # Load session from Redis
        session = get_or_create_session_state(request.session_id)

        logger.info(f"[schema_proposal] Session {request.session_id} - User goal: {session.get('approved_user_goal')}")
        logger.info(f"[schema_proposal] Session {request.session_id} - Files: {session.get('approved_files')}")

        # Validate we have required inputs (should come from previous agents via Redis)
        if not session.get("approved_user_goal"):
            raise HTTPException(
                status_code=400,
                detail="approved_user_goal is required. Run User Intent Agent first."
            )
        if not session.get("approved_files"):
            raise HTTPException(
                status_code=400,
                detail="approved_files is required. Run File Suggestion Agent first."
            )

        # Add user message to session
        session["messages"].append(HumanMessage(content=request.message))

        # Invoke the graph
        logger.debug("Invoking schema proposal graph")
        result = schema_proposal_graph.invoke(session)

        # Save updated session to Redis
        save_session(request.session_id, result)

        logger.info(f"[schema_proposal] Session {request.session_id} - Approved plan: {result.get('approved_construction_plan') is not None}")

        # Extract last AI message for response
        last_ai_message = ""
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                last_ai_message = msg.content
                break

        logger.debug(f"Response: {last_ai_message[:100]}...")

        # Determine next phase
        current_phase = "schema_proposal"
        if result.get("approved_construction_plan"):
            current_phase = "graph_construction"

        return SchemaProposalResponse(
            message=last_ai_message,
            session_id=request.session_id,
            proposed_construction_plan=result.get("proposed_construction_plan"),
            approved_construction_plan=result.get("approved_construction_plan"),
            feedback=result.get("feedback", ""),
            iteration_count=result.get("iteration_count", 0),
            current_agent=result.get("current_agent", ""),
            approved_user_goal=result.get("approved_user_goal"),
            approved_files=result.get("approved_files"),
            current_phase=current_phase,
            status="success"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}", response_model=SessionStateResponse)
async def get_session_endpoint(session_id: str):
    """Get the current state of a session."""
    # Load from Redis
    session = get_session(session_id)

    if not session:
        return SessionStateResponse(
            session_id=session_id,
            exists=False
        )

    return SessionStateResponse(
        session_id=session_id,
        exists=True,
        messages_count=len(session.get("messages", [])),
        proposed_construction_plan=session.get("proposed_construction_plan"),
        approved_construction_plan=session.get("approved_construction_plan"),
        feedback=session.get("feedback"),
        iteration_count=session.get("iteration_count", 0)
    )


@router.delete("/session/{session_id}")
async def delete_session_endpoint(session_id: str):
    """Clear a session."""
    from app.core.session_manager import delete_session

    # Load from Redis
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete from Redis
    delete_session(session_id)
    logger.info(f"Deleted session: {session_id}")

    return {"message": f"Session {session_id} deleted", "status": "success"}


@router.post("/approve")
async def approve_construction_plan(session_id: str):
    """
    Approve the current proposed construction plan.

    Call this after reviewing the plan and deciding it's ready.
    """
    # Load from Redis
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.get("proposed_construction_plan"):
        raise HTTPException(
            status_code=400,
            detail="No proposed construction plan to approve"
        )

    # Copy proposed to approved
    session["approved_construction_plan"] = session["proposed_construction_plan"]

    # Save back to Redis
    save_session(session_id, session)

    logger.info(f"Approved construction plan for session: {session_id}")

    return {
        "message": "Construction plan approved",
        "approved_construction_plan": session["approved_construction_plan"],
        "status": "success"
    }
