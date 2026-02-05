"""
Embedding Service - Generate vector embeddings for text chunks

Uses OpenAI's text-embedding-3-small model (1536 dimensions).
These embeddings enable semantic similarity search.
"""

import logging
from typing import List
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings

logger = logging.getLogger(__name__)


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a list of text chunks.

    Args:
        texts: List of text strings to embed

    Returns:
        List of embedding vectors (each vector is 1536 floats)

    Example:
        chunks = ["Acme Corp supplies steel", "Quality is excellent"]
        embeddings = generate_embeddings(chunks)
        # Returns: [[0.123, -0.456, ...], [0.789, -0.234, ...]]

    Why embeddings?
    - Enables semantic search (find similar meaning, not just keywords)
    - "defective part" will match "broken component" even without shared words
    """
    if not texts or len(texts) == 0:
        return []

    try:
        # Initialize OpenAI embeddings
        embedder = OpenAIEmbeddings(
            model="text-embedding-3-small",  # 1536 dimensions, fast and cheap
            api_key=settings.openai_api_key
        )

        # Generate embeddings (batch processing)
        embeddings = embedder.embed_documents(texts)

        logger.info(f"[EMBEDDINGS] Generated {len(embeddings)} embeddings")
        return embeddings

    except Exception as e:
        logger.error(f"[EMBEDDINGS] Error generating embeddings: {e}")
        raise


def generate_query_embedding(query: str) -> List[float]:
    """
    Generate embedding for a single query string.

    Args:
        query: User's search query

    Returns:
        Single embedding vector (1536 floats)

    Example:
        query = "Which suppliers have quality issues?"
        embedding = generate_query_embedding(query)
        # Use this to find similar chunks via vector search
    """
    try:
        embedder = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=settings.openai_api_key
        )

        embedding = embedder.embed_query(query)
        logger.info(f"[EMBEDDINGS] Generated query embedding")
        return embedding

    except Exception as e:
        logger.error(f"[EMBEDDINGS] Error generating query embedding: {e}")
        raise
