import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, List
from langchain_core.messages import HumanMessage

from app.agents.graphs.file_suggestion_graph import file_suggestion_graph
from app.core.session_manager import get_session, save_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/file-suggestion", tags=["file-suggestion"])


class ChatRequest(BaseModel):
    message: str
    session_id: str
    # No longer needed - will load from Redis
    # approved_user_goal: Optional[dict] = None


class ChatResponse(BaseModel):
    message: str
    session_id: str
    approved_user_goal: Optional[dict] = None
    all_available_files: Optional[List[str]] = None
    suggested_files: Optional[List[str]] = None
    approved_files: Optional[List[str]] = None
    current_phase: str = "file_suggestion"
    status: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session_id = request.session_id

    # Load session from Redis (includes approved_user_goal from previous agent!)
    state = get_session(session_id)

    # Initialize if new session
    if not state:
        state = {
            "messages": [],
            "approved_user_goal": None,
            "all_available_files": None,
            "suggested_files": None,
            "approved_files": None,
            "current_phase": "file_suggestion"
        }

    logger.info(f"[file_suggestion] Session {session_id} - User goal: {state.get('approved_user_goal')}")

    # Add user message
    state["messages"].append(HumanMessage(content=request.message))

    # Invoke the graph
    result = file_suggestion_graph.invoke(state)

    # Save updated session to Redis
    save_session(session_id, result)

    logger.info(f"[file_suggestion] Session {session_id} - Approved files: {result.get('approved_files')}")

    # Extract last AI message
    last_message = ""
    for msg in reversed(result["messages"]):
        if hasattr(msg, "content") and msg.content and not hasattr(msg, "tool_call_id"):
            last_message = msg.content
            break

    # Determine next phase
    current_phase = "file_suggestion"
    if result.get("approved_files"):
        current_phase = "schema_proposal"  # or file_type_detection

    return ChatResponse(
        message=last_message,
        session_id=session_id,
        approved_user_goal=result.get("approved_user_goal"),
        all_available_files=result.get("all_available_files"),
        suggested_files=result.get("suggested_files"),
        approved_files=result.get("approved_files"),
        current_phase=current_phase,
        status="success",
    )
