# Create test file: server/test_config.py
from app.core.config import settings

print("✅ Config loaded!")
print(f"OpenAI Model: {settings.openai_model_name}")
print(f"Neo4j URI: {settings.neo4j_uri}")
print(f"Sessions Dir: {settings.sessions_dir}")
