from datetime import datetime

from typing import Optional,List,Dict,Any
from pydantic import BaseModel,Field
from app.core.enums import Phase,FlowType,CheckpointType,MessageRole
import uuid


class Message(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    

    

class Checkpoint(BaseModel):
    
    type: CheckpointType
    data: Dict[str, Any]
    prompt:str
    created_at: datetime = Field(default_factory=datetime.now)
class FileData(BaseModel):
    id : str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: str
    source: str
    content: str  # Actual file content (CSV text, JSON text, PDF text)
    storage_url: Optional[str] = None  # Supabase storage URL (if uploaded)
    size: int = 0
    parsed : bool = False
    parse_error : Optional[str] = None
    raw_count : Optional[int] = None
    columns : Optional[List[str]] = None
    preview : Optional[str] = None
    chunks : Optional[List[str]] = None  # Text chunks (for PDF/unstructured files)
    added_at: datetime = Field(default_factory=datetime.now) 
class SessionState(BaseModel):
    
    session_id: str
    user_id : str
    flow_type: FlowType
    phase: Phase
    knowledge_base_id: Optional[str] = None
    knowledge_base_name: Optional[str] = None

    messages : List[Message] = Field(default_factory=list)
    
    checkpoint :Optional[Checkpoint] = None
    
    user_goal : Optional[str] = None
    goal_approved : bool = False
    
    files : List[FileData] = Field(default_factory=list)
    
    proposed_schema : Optional[Dict[str, Any]] = None

    schema_iteration: int = 0

    schema_approved: bool = False

    approved_schema : Optional[Dict[str, Any]] = None
    
    build_status : Optional[str] = None

    graph_built: bool = False

    pending_kb_options: Optional[List[Dict[str, Any]]] = None  # Multi-KB selection state

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    


   
    
    