from supabase import create_client, Client
from app.core.config import settings

class SupabaseClient:
    
    def __init__(self) :
        self.client = create_client(
            settings.supabase_url,
            settings.supabase_service_key
        )
        
    def get_client(self) -> Client:
        return self.client
   

supabase_client = SupabaseClient()