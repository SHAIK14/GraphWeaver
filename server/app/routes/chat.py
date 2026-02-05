from typing import Optional
import uuid
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.models.user import User
from app.services.streaming_orchestrator import orchestrate_stream

router = APIRouter(
    prefix="/api",
    tags=["chat"],
)

class chat_request(BaseModel):
    message: str
    session_id: Optional[str] = None


@router.post("/chat")
async def chat_endpoint(
    request: chat_request,
    user: User = Depends(get_current_user),
):
    """
    Streaming chat endpoint using SSE (Server-Sent Events).

    Events emitted:
    - thinking: Status updates ("Analyzing files...")
    - token: Response text streaming word by word
    - complete: Final result with session state
    - error: Error occurred
    """
    session_id = request.session_id or str(uuid.uuid4())

    return StreamingResponse(
        orchestrate_stream(
            session_id=session_id,
            user_id=user.id,
            message=request.message,
            token=user.token,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


