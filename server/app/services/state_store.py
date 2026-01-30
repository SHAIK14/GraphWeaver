
from typing import Optional
from datetime import datetime

from upstash_redis import Redis
from app.core.config import settings
from app.core.state import SessionState
from app.core.enums import Phase,FlowType,get_initial_phase



class StateStore:
    def __init__(self):
        
        self.redis = Redis(
            url = settings.upstash_redis_rest_url,
            token = settings.upstash_redis_rest_token
        )
        self.ttl = settings.session_ttl_hours * 3600
        
    def _key(self, session_id : str ) -> str:
        
        return f"session:{session_id}"
    
    async def create(
        self,
        session_id : str,
        user_id : str,
        flow_type : FlowType,
    ) -> SessionState:
        
        initial_phase = get_initial_phase(flow_type)
        
        state  = SessionState(
            session_id =  session_id,
            user_id = user_id,
            flow_type = flow_type,
            phase = initial_phase)
        
        await  self.save(state)
        return state
    
    async def save(self, state : SessionState) :
        state.updated_at = datetime.now()
        
        self.redis.setex(
            self._key(state.session_id),
            self.ttl,
            state.model_dump_json()
        )
        
    async def load(self, session_id : str) -> Optional[SessionState]:
        
        data = self.redis.get(self._key(session_id))
        
        if data :
            return SessionState.model_validate_json(data)
        return None
    
    async def update (self , session_id : str ,  **updates) -> Optional[SessionState]:
        
        state = await self.load(session_id)
        if not state:
            return None
        
        for key ,value in updates.items():
            if hasattr(state, key):
                setattr(state, key,value)
                
        await self.save(state)
        return state
    
    async def delete(self, session_id : str) :
         self.redis.delete(self._key(session_id))
        
    async def exists(self, session_id : str) -> bool:
        return bool( self.redis.exists(self._key(session_id)))
    
    
state_store = StateStore()
        
        