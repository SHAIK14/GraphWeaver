from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model_name: str = Field("gpt-4o-mini", env="OPENAI_MODEL_NAME")

    neo4j_uri: str = Field(..., env="NEO4J_URI")
    neo4j_username: str = Field(..., env="NEO4J_USERNAME")
    neo4j_password: str = Field(..., env="NEO4J_PASSWORD")

    data_import_dir: str = Field(default="./data", env="DATA_IMPORT_DIR")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()