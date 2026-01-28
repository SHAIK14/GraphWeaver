"""
API Routes for Unstructured Schema Proposal.

Endpoints:
- POST /chat - Send messages to NER or Fact agent
- POST /approve-entities - Approve proposed entities, transition to Fact stage
- POST /approve-facts - Approve proposed facts, complete workflow
- GET /session/{session_id} - Get current session state
- DELETE /session/{session_id} - Clear session

The workflow has TWO stages:
1. NER Stage: Propose entity types → user approves
2. Fact Stage: Propose relationship triples → user approves
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from langchain_core.messages import HumanMessage

from app.agents.graphs.unstructured_schema_graph import ner_schema_graph, fact_schema_graph
from app.core.session_manager import get_session, save_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/unstructured-schema", tags=["unstructured-schema"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    session_id: str
    message: str
    # No longer needed - will load from Redis
    # approved_user_goal: Optional[str] = None
    # approved_files: Optional[list[str]] = None
    # approved_construction_plan: Optional[dict] = None


class ApproveEntitiesRequest(BaseModel):
    """Request to approve proposed entities."""
    session_id: str


class ApproveFactsRequest(BaseModel):
    """Request to approve proposed facts."""
    session_id: str


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    session_id: str
    stage: str
    response: str
    proposed_entities: Optional[list[dict]] = None
    approved_entities: Optional[list[dict]] = None
    proposed_facts: Optional[list[dict]] = None
    approved_facts: Optional[list[dict]] = None
    current_phase: str = "unstructured_schema"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_or_create_session_state(session_id: str) -> dict:
    """
    Get existing session from Redis or create new one.

    Initial state includes:
    - stage: "ner" (start with entity recognition)
    - messages: empty (conversation history)
    - Context from previous agents loaded from Redis
    """
    # Load from Redis
    session_state = get_session(session_id)

    if not session_state:
        session_state = {
            "messages": [],
            "stage": "ner",
            "approved_user_goal": "",
            "approved_files": [],
            "approved_construction_plan": {},
            "proposed_entities": [],
            "approved_entities": [],
            "proposed_facts": [],
            "approved_facts": [],
            "current_phase": "unstructured_schema"
        }
        save_session(session_id, session_state)

    return session_state


def extract_response_text(state: dict) -> str:
    """Extract the assistant's response text from messages."""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content:
            # Skip tool messages
            if not hasattr(msg, "tool_call_id"):
                return msg.content
    return "No response generated"


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message to the current stage's agent.

    Stage "ner": Message goes to NER agent
    Stage "fact": Message goes to Fact agent

    The agent will:
    1. Process the message
    2. Optionally call tools
    3. Return a response (possibly with proposals)
    """
    # Load session from Redis (includes context from previous agents!)
    state = get_or_create_session_state(request.session_id)

    logger.info(f"[unstructured_schema] Session {request.session_id} - Stage: {state['stage']}")
    logger.info(f"[unstructured_schema] Session {request.session_id} - Files: {state.get('approved_files')}")

    # Add user message
    state["messages"].append(HumanMessage(content=request.message))

    # Determine which graph to run based on stage (like course uses two agents)
    if state["stage"] == "ner":
        # Run NER graph
        result = ner_schema_graph.invoke(state)
    elif state["stage"] == "fact":
        # Run Fact graph (initialized with NER end state including approved_entities)
        result = fact_schema_graph.invoke(state)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown stage: {state['stage']}")

    # Save updated session to Redis
    save_session(request.session_id, result)

    logger.info(f"[unstructured_schema] Session {request.session_id} - Proposed entities: {len(result.get('proposed_entities', []))}")
    logger.info(f"[unstructured_schema] Session {request.session_id} - Proposed facts: {len(result.get('proposed_facts', []))}")

    # Determine next phase
    current_phase = "unstructured_schema"
    if result.get("approved_facts"):
        current_phase = "graph_construction"

    return ChatResponse(
        session_id=request.session_id,
        stage=result.get("stage", "ner"),
        response=extract_response_text(result),
        proposed_entities=result.get("proposed_entities"),
        approved_entities=result.get("approved_entities"),
        proposed_facts=result.get("proposed_facts"),
        approved_facts=result.get("approved_facts"),
        current_phase=current_phase
    )


@router.post("/approve-entities", response_model=ChatResponse)
async def approve_entities(request: ApproveEntitiesRequest):
    """
    Approve the proposed entities and transition to Fact stage.

    This:
    1. Copies proposed_entities to approved_entities
    2. Changes stage from "ner" to "fact"
    3. Agent can now propose facts using approved entities
    """
    # Load from Redis
    state = get_session(request.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check we have entities to approve
    if not state.get("proposed_entities"):
        raise HTTPException(
            status_code=400,
            detail="No proposed entities to approve. Run NER agent first."
        )

    # Approve entities
    state["approved_entities"] = state["proposed_entities"].copy()
    state["stage"] = "fact"

    # Add system message about transition
    state["messages"].append(
        HumanMessage(content="I approve the proposed entities. Please proceed with fact extraction.")
    )

    # Save back to Redis
    save_session(request.session_id, state)

    logger.info(f"[unstructured_schema] Session {request.session_id} - Approved {len(state['approved_entities'])} entities, moving to fact stage")

    return ChatResponse(
        session_id=request.session_id,
        stage=state["stage"],
        response=f"Approved {len(state['approved_entities'])} entity types. Transitioning to Fact extraction stage.",
        proposed_entities=state.get("proposed_entities"),
        approved_entities=state.get("approved_entities"),
        proposed_facts=state.get("proposed_facts"),
        approved_facts=state.get("approved_facts"),
    )


@router.post("/approve-facts", response_model=ChatResponse)
async def approve_facts(request: ApproveFactsRequest):
    """
    Approve the proposed facts and complete the workflow.

    This:
    1. Copies proposed_facts to approved_facts
    2. Marks workflow as complete
    """
    # Load from Redis
    state = get_session(request.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check we have facts to approve
    if not state.get("proposed_facts"):
        raise HTTPException(
            status_code=400,
            detail="No proposed facts to approve. Run Fact agent first."
        )

    # Approve facts
    state["approved_facts"] = state["proposed_facts"].copy()
    state["stage"] = "complete"

    # Save back to Redis
    save_session(request.session_id, state)

    logger.info(f"[unstructured_schema] Session {request.session_id} - Approved {len(state['approved_facts'])} facts, workflow complete")

    return ChatResponse(
        session_id=request.session_id,
        stage=state["stage"],
        response=f"Approved {len(state['approved_facts'])} fact types. Unstructured schema proposal complete!",
        proposed_entities=state.get("proposed_entities"),
        approved_entities=state.get("approved_entities"),
        proposed_facts=state.get("proposed_facts"),
        approved_facts=state.get("approved_facts"),
        current_phase="graph_construction"
    )


@router.get("/session/{session_id}")
async def get_session_endpoint(session_id: str):
    """
    Get the current state of a session.

    Useful for checking:
    - Current stage (ner/fact/complete)
    - Proposed and approved entities/facts
    - Conversation history
    """
    # Load from Redis
    state = get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "stage": state.get("stage"),
        "approved_user_goal": state.get("approved_user_goal"),
        "approved_files": state.get("approved_files"),
        "proposed_entities": state.get("proposed_entities"),
        "approved_entities": state.get("approved_entities"),
        "proposed_facts": state.get("proposed_facts"),
        "approved_facts": state.get("approved_facts"),
        "message_count": len(state.get("messages", [])),
    }


@router.delete("/session/{session_id}")
async def delete_session_endpoint(session_id: str):
    """
    Clear a session and all its state.

    Use this to start fresh.
    """
    from app.core.session_manager import delete_session

    # Load from Redis
    state = get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete from Redis
    delete_session(session_id)
    logger.info(f"[unstructured_schema] Session {session_id} deleted")

    return {"message": f"Session {session_id} deleted"}
