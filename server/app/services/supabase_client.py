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


def get_user_client(token: str) -> Client:
    """Create a Supabase client scoped to the user's JWT (respects RLS policies).

    supabase-py create_client expects an API key (anon/service_role), not a JWT.
    RLS enforcement requires the PostgREST Authorization header to carry the user's JWT.
    """
    client = create_client(settings.supabase_url, settings.supabase_key)
    client.postgrest.session.headers["authorization"] = f"Bearer {token}"
    return client