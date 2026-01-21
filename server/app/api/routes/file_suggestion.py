from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, List
from langchain_core.messages import HumanMessage

from app.agents.graphs.file_suggestion_graph import file_suggestion_graph

router = APIRouter(prefix="/api/file-suggestion", tags=["file-suggestion"])

# In-memory session storage (use Redis in production)
sessions: Dict[str, dict] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str
    # Optional: pass approved_user_goal from previous agent
    approved_user_goal: Optional[dict] = None


class ChatResponse(BaseModel):
    message: str
    session_id: str
    approved_user_goal: Optional[dict] = None
    all_available_files: Optional[List[str]] = None
    suggested_files: Optional[List[str]] = None
    approved_files: Optional[List[str]] = None
    status: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session_id = request.session_id

    # Get or create session state
    if session_id not in sessions:
        sessions[session_id] = {
            "messages": [],
            "approved_user_goal": request.approved_user_goal,  # From previous agent
            "all_available_files": None,
            "suggested_files": None,
            "approved_files": None,
        }
    
    # If approved_user_goal passed in request, update it
    if request.approved_user_goal:
        sessions[session_id]["approved_user_goal"] = request.approved_user_goal

    state = sessions[session_id]
    state["messages"].append(HumanMessage(content=request.message))

    # Invoke the graph
    result = file_suggestion_graph.invoke(state)

    # Update session
    sessions[session_id] = result

    # Extract last AI message
    last_message = ""
    for msg in reversed(result["messages"]):
        if hasattr(msg, "content") and msg.content and not hasattr(msg, "tool_call_id"):
            last_message = msg.content
            break

    return ChatResponse(
        message=last_message,
        session_id=session_id,
        approved_user_goal=result.get("approved_user_goal"),
        all_available_files=result.get("all_available_files"),
        suggested_files=result.get("suggested_files"),
        approved_files=result.get("approved_files"),
        status="success",
    )
