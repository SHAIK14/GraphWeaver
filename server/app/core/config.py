

from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    env: str = Field(default="development")
    debug: bool = Field(default=True)
    
    # OpenAI
    openai_api_key: str = Field(...) 
    openai_model_name: str = Field(...)  
    
    # Supabase
    supabase_url: str = Field(...)
    supabase_key: str = Field(...)
    supabase_service_key: str = Field(...)
    supabase_jwt_secret: str = Field(...)  # JWT secret for verifying tokens
    
    # Upstash Redis
    upstash_redis_rest_url: str = Field(...)
    upstash_redis_rest_token: str = Field(...)
    session_ttl_hours: int = Field(default=24)
    
    # Neo4j
    neo4j_uri: str = Field(...)
    neo4j_username: str = Field(...)
    neo4j_password: str = Field(...)
    neo4j_database: str = Field(default="neo4j")  # Optional with default
    
    # JWT
    jwt_secret: str = Field(...)  
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiration_hours: int = Field(default=24)
    


    

    embedding_model: str = Field(default="text-embedding-3-small")
    embedding_dimensions: int = Field(default=1536)
    
   
    
    # Pydantic config
    model_config = SettingsConfigDict(
        env_file=".env",  # Load from .env
        env_file_encoding="utf-8",
        case_sensitive=False,  # OPENAI_API_KEY = openai_api_key
        extra="ignore"  # Ignore unknown vars in .env
    )


# Singleton instance - import this everywhere
settings = Settings()
