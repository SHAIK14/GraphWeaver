from datetime import datetime

from typing import Optional,List,Dict,Any
from pydantic import BaseModel,Field
from app.core.enums import Phase,FlowType,CheckpointType,MessageRole


class Message(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    

    

class Checkpoint(BaseModel):
    
    type: CheckpointType
    data: Dict[str, Any]
    prompt:str
    created_at: datetime = Field(default_factory=datetime.now)
    
class SessionState(BaseModel):
    
    session_id: str
    user_id : str
    flow_type: FlowType
    phase: Phase
    knowledge_base_id: Optional[str] = None
    
    messages : List[Message] = Field(default_factory=list)
    
    checkpoint :Optional[Checkpoint] = None
    
    user_goal : Optional[str] = None
    goal_approved : bool = False
    
    suggested_files : Optional[List[str]] = None
    approved_files : Optional[List[str]] = None
    
    proposed_schema : Optional[Dict[str, Any]] = None
    
    schema_iteration: int = 0
    
    approved_schema : Optional[Dict[str, Any]] = None
    
    build_status : Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    

   
    
    