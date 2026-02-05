"""
Vector Index Service - Manage Neo4j vector indexes for semantic search

Creates and manages vector indexes on Chunk node embeddings.
"""

import logging
from typing import Dict, Any

from app.services.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)


def create_vector_index(kb_id: str | None = None) -> Dict[str, Any]:
    """
    Create a vector index on KB-prefixed Chunk.embedding for fast similarity search.

    Each KB gets its own vector index: {kb_id}_chunk_embeddings
    Dimension: 1536 (matches text-embedding-3-small)

    Args:
        kb_id: Knowledge base identifier. If None, creates legacy unprefixed index.

    Returns:
        {"status": "success"} or error dict
    """
    chunk_label = f"{kb_id}_Chunk" if kb_id else "Chunk"
    index_name = f"{kb_id}_chunk_embeddings" if kb_id else "chunk_embeddings"

    logger.info(f"[VECTOR_INDEX] Creating vector index '{index_name}' on {chunk_label}")

    query = f"""
    CREATE VECTOR INDEX {index_name} IF NOT EXISTS
    FOR (c:{chunk_label}) ON c.embedding
    OPTIONS {{
        indexConfig: {{
            `vector.dimensions`: 1536,
            `vector.similarity_function`: 'cosine'
        }}
    }}
    """

    result = neo4j_client.send_query(query)

    if result.get("status") == "error":
        logger.error(f"[VECTOR_INDEX] Failed to create index: {result.get('error_message')}")
        return result

    logger.info(f"[VECTOR_INDEX] ✓ Vector index '{index_name}' created")
    return {"status": "success", "index_name": index_name}


def vector_search(query_embedding: list[float], kb_id: str | None = None, top_k: int = 5) -> Dict[str, Any]:
    """
    Search for chunks similar to the query embedding within a specific KB.

    Args:
        query_embedding: Vector embedding of user's query (1536 floats)
        kb_id: Knowledge base identifier. Uses KB-specific vector index if provided.
        top_k: Number of similar chunks to return

    Returns:
        {
            "status": "success",
            "chunks": [
                {"chunk_id": "...", "text": "...", "score": 0.95},
                ...
            ]
        }
    """
    index_name = f"{kb_id}_chunk_embeddings" if kb_id else "chunk_embeddings"
    logger.info(f"[VECTOR_INDEX] Searching index '{index_name}' for top {top_k} chunks")

    # Check if index exists first
    if not check_vector_index_exists(kb_id):
        logger.info(f"[VECTOR_INDEX] Vector index '{index_name}' doesn't exist - no text files processed yet")
        return {
            "status": "success",
            "chunks": [],
            "count": 0
        }

    # Use Neo4j's vector search procedure with KB-specific index
    query = f"""
    CALL db.index.vector.queryNodes('{index_name}', $top_k, $query_embedding)
    YIELD node, score
    RETURN node.id as chunk_id,
           node.text as text,
           node.source as source,
           score
    ORDER BY score DESC
    LIMIT $top_k
    """

    result = neo4j_client.send_query(query, {
        "top_k": top_k,
        "query_embedding": query_embedding
    })

    if result.get("status") == "error":
        logger.error(f"[VECTOR_INDEX] Search failed: {result.get('error_message')}")
        return {
            "status": "success",
            "chunks": [],
            "count": 0
        }

    chunks = result.get("query_result", [])
    logger.info(f"[VECTOR_INDEX] Found {len(chunks)} similar chunks")

    return {
        "status": "success",
        "chunks": chunks,
        "count": len(chunks)
    }


def check_vector_index_exists(kb_id: str | None = None) -> bool:
    """
    Check if the KB-specific vector index exists.

    Args:
        kb_id: Knowledge base identifier. Checks for KB-specific index if provided.

    Returns:
        True if index exists, False otherwise
    """
    index_name = f"{kb_id}_chunk_embeddings" if kb_id else "chunk_embeddings"

    query = """
    SHOW INDEXES
    YIELD name, type
    WHERE name = $index_name AND type = 'VECTOR'
    RETURN count(*) as count
    """

    result = neo4j_client.send_query(query, {"index_name": index_name})

    if result.get("status") == "success":
        count = result.get("query_result", [{}])[0].get("count", 0)
        exists = count > 0
        logger.info(f"[VECTOR_INDEX] Index '{index_name}' exists: {exists}")
        return exists

    return False
