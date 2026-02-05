"""
Knowledge Base Service - Manages KB metadata in Supabase.

Handles:
- Creating new KB entries after graph build
- Loading user's KBs for QUERY flow
- Updating KB metadata
- Deleting KBs
"""

import logging
from typing import List, Dict, Any, Optional
from app.services.supabase_client import supabase_client, get_user_client
from app.services.neo4j_client import neo4j_client


def _get_client(token: Optional[str] = None):
    """Return a user-scoped client (respects RLS) when token is available, else service client."""
    return get_user_client(token) if token else supabase_client.get_client()

logger = logging.getLogger(__name__)


def create_kb(
    kb_id: str,
    owner_id: str,
    name: str,
    description: Optional[str],
    schema: Dict[str, Any],
    token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new knowledge base entry in Supabase.

    Args:
        kb_id: Unique KB identifier (kb_a3f2c8e9)
        owner_id: User ID (UUID from Supabase Auth)
        name: User-friendly name
        description: Optional description
        schema: Full schema with nodes and relationships
        token: User JWT for RLS-scoped access

    Returns:
        Created KB record or error dict
    """
    try:
        client = _get_client(token)

        result = client.table('knowledge_bases').insert({
            'id': kb_id,
            'owner_id': owner_id,
            'name': name,
            'description': description,
            'schema': schema
        }).execute()

        logger.info(f"[KB_SERVICE] ✓ Created KB: {kb_id} ({name}) for user {owner_id}")
        return {"status": "success", "kb": result.data[0]}

    except Exception as e:
        logger.error(f"[KB_SERVICE] ❌ Failed to create KB: {e}")
        return {"status": "error", "error": str(e)}


def get_user_kbs(owner_id: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get all knowledge bases for a user.

    Args:
        owner_id: User ID
        token: User JWT for RLS-scoped access

    Returns:
        List of KB records (empty list if none)
    """
    try:
        client = _get_client(token)

        result = client.table('knowledge_bases') \
            .select('*') \
            .eq('owner_id', owner_id) \
            .order('created_at', desc=True) \
            .execute()

        kbs = result.data or []
        logger.info(f"[KB_SERVICE] Found {len(kbs)} KBs for user {owner_id}")
        return kbs

    except Exception as e:
        logger.error(f"[KB_SERVICE] ❌ Failed to get user KBs: {e}")
        return []


def get_kb_by_id(kb_id: str, owner_id: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get a specific knowledge base by ID (with owner verification).

    Args:
        kb_id: KB identifier
        owner_id: User ID (for RLS)
        token: User JWT for RLS-scoped access

    Returns:
        KB record or None if not found/not authorized
    """
    try:
        client = _get_client(token)

        result = client.table('knowledge_bases') \
            .select('*') \
            .eq('id', kb_id) \
            .eq('owner_id', owner_id) \
            .single() \
            .execute()

        if result.data:
            logger.info(f"[KB_SERVICE] ✓ Loaded KB: {kb_id}")
            return result.data
        else:
            logger.warning(f"[KB_SERVICE] KB not found: {kb_id}")
            return None

    except Exception as e:
        logger.error(f"[KB_SERVICE] ❌ Failed to get KB {kb_id}: {e}")
        return None


def update_kb_schema(kb_id: str, owner_id: str, schema: Dict[str, Any], token: Optional[str] = None) -> Dict[str, Any]:
    """
    Update KB schema (for EXTEND flow).

    Args:
        kb_id: KB identifier
        owner_id: User ID (for RLS)
        schema: Updated schema
        token: User JWT for RLS-scoped access

    Returns:
        Success/error dict
    """
    try:
        client = _get_client(token)

        result = client.table('knowledge_bases') \
            .update({'schema': schema}) \
            .eq('id', kb_id) \
            .eq('owner_id', owner_id) \
            .execute()

        logger.info(f"[KB_SERVICE] ✓ Updated schema for KB: {kb_id}")
        return {"status": "success"}

    except Exception as e:
        logger.error(f"[KB_SERVICE] ❌ Failed to update KB schema: {e}")
        return {"status": "error", "error": str(e)}


def delete_kb(kb_id: str, owner_id: str, token: Optional[str] = None) -> Dict[str, Any]:
    """
    Delete a knowledge base — Neo4j graph data first, then Supabase metadata.

    Args:
        kb_id: KB identifier
        owner_id: User ID (for RLS)
        token: User JWT for RLS-scoped access

    Returns:
        Success/error dict
    """
    try:
        # 1. Remove all nodes (and their relationships) tagged with this kb_id
        detach_result = neo4j_client.send_query(
            "MATCH (n {kb_id: $kb_id}) DETACH DELETE n",
            {"kb_id": kb_id}
        )
        if detach_result["status"] == "error":
            logger.error(f"[KB_SERVICE] ❌ Neo4j DETACH DELETE failed for {kb_id}: {detach_result['error_message']}")
            return {"status": "error", "error": f"Neo4j cleanup failed: {detach_result['error_message']}"}
        logger.info(f"[KB_SERVICE] ✓ Removed Neo4j nodes for KB: {kb_id}")

        # 2. Drop the per-KB vector index (DDL — cannot be parameterised)
        index_name = f"{kb_id}_chunk_embeddings"
        drop_result = neo4j_client.send_query(f"DROP INDEX {index_name} IF EXISTS")
        if drop_result["status"] == "error":
            logger.warning(f"[KB_SERVICE] Vector index drop failed for {index_name}: {drop_result['error_message']}")
            # Non-fatal — index may not exist; continue with metadata delete

        # 3. Delete KB metadata from Supabase
        client = _get_client(token)
        client.table('knowledge_bases') \
            .delete() \
            .eq('id', kb_id) \
            .eq('owner_id', owner_id) \
            .execute()

        logger.info(f"[KB_SERVICE] ✓ Deleted KB: {kb_id}")
        return {"status": "success"}

    except Exception as e:
        logger.error(f"[KB_SERVICE] ❌ Failed to delete KB: {e}")
        return {"status": "error", "error": str(e)}
