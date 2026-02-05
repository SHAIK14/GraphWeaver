"""
GraphRAG Query Service - Hybrid Vector + Graph Search

Combines vector similarity search with graph traversal to answer questions.

Query Flow:
1. User question → Vector embedding
2. Vector search → Find relevant text chunks
3. Graph traversal → Gather connected entities and domain nodes
4. LLM synthesis → Generate final answer
"""

import re
import logging
from typing import Dict, Any, List

from app.services.embedding_service import generate_query_embedding
from app.services.vector_index_service import vector_search
from app.services.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)

_KB_PREFIX_RE = re.compile(r"^kb_[a-f0-9]+_")


def _strip_kb_prefix(text: str) -> str:
    """Remove internal kb_<id>_ prefix so labels aren't exposed to the user."""
    return _KB_PREFIX_RE.sub("", text)


def gather_chunk_context(chunk_ids: List[str], kb_id: str | None = None) -> Dict[str, Any]:
    """
    Gather graph context around chunks using KB-prefixed labels.

    For each chunk, traverse relationships to find:
    - Entities mentioned (via KB-prefixed MENTIONS)
    - Domain nodes connected (via KB-prefixed CORRESPONDS_TO)
    - Relationships between domain nodes

    Args:
        chunk_ids: List of Chunk IDs from vector search
        kb_id: Knowledge base identifier for label prefixing

    Returns:
        {
            "chunks": [...],
            "entities": [...],
            "domain_nodes": [...],
            "relationships": [...]
        }
    """
    logger.info(f"[GRAPHRAG] Gathering context for {len(chunk_ids)} chunks (KB: {kb_id})")

    # Use KB-prefixed labels for traversal
    chunk_label = f"{kb_id}_Chunk" if kb_id else "Chunk"
    entity_label = f"{kb_id}_Entity" if kb_id else "Entity"
    mentions_type = f"{kb_id}_MENTIONS" if kb_id else "MENTIONS"
    corresponds_type = f"{kb_id}_CORRESPONDS_TO" if kb_id else "CORRESPONDS_TO"

    context_query = f"""
    MATCH (c:`{chunk_label}`)
    WHERE c.id IN $chunk_ids

    WITH collect(DISTINCT {{
        id: c.id,
        text: c.text,
        source: c.source
    }}) as chunks

    // Get KB-prefixed entities mentioned in chunks
    OPTIONAL MATCH (c2:`{chunk_label}`)-[:`{mentions_type}`]->(e:`{entity_label}`)
    WHERE c2.id IN $chunk_ids
    WITH chunks, collect(DISTINCT {{
        name: e.name,
        type: e.type
    }}) as entities

    // Get domain nodes via KB-prefixed CORRESPONDS_TO
    OPTIONAL MATCH (c3:`{chunk_label}`)-[:`{mentions_type}`]->(e2:`{entity_label}`)-[:`{corresponds_type}`]->(d)
    WHERE c3.id IN $chunk_ids
    WITH chunks, entities, collect(DISTINCT {{
        label: labels(d)[0],
        name: d.name,
        properties: properties(d)
    }}) as domain_nodes

    // Get relationships between domain nodes
    OPTIONAL MATCH (c4:`{chunk_label}`)-[:`{mentions_type}`]->(e3:`{entity_label}`)-[:`{corresponds_type}`]->(d1)-[r]->(d2)
    WHERE c4.id IN $chunk_ids
    WITH chunks, entities, domain_nodes, collect(DISTINCT {{
        from: d1.name,
        type: type(r),
        to: d2.name
    }}) as relationships

    RETURN chunks, entities, domain_nodes, relationships
    """

    result = neo4j_client.send_query(context_query, {"chunk_ids": chunk_ids})

    if result.get("status") == "error":
        logger.error(f"[GRAPHRAG] Failed to gather context: {result.get('error_message')}")
        return {
            "chunks": [],
            "entities": [],
            "domain_nodes": [],
            "relationships": []
        }

    context = result.get("query_result", [{}])[0]

    logger.info(f"[GRAPHRAG] Context gathered: {len(context.get('chunks', []))} chunks, "
                f"{len(context.get('entities', []))} entities, "
                f"{len(context.get('domain_nodes', []))} domain nodes")

    return context


def graphrag_query(question: str, kb_id: str | None = None, top_k: int = 5) -> Dict[str, Any]:
    """
    Execute GraphRAG query: vector search + graph traversal with KB isolation.

    Args:
        question: User's natural language question
        kb_id: Knowledge base identifier for isolated search
        top_k: Number of similar chunks to retrieve

    Returns:
        {
            "status": "success",
            "question": "Which suppliers have quality issues?",
            "context": {
                "chunks": [...],
                "entities": [...],
                "domain_nodes": [...],
                "relationships": [...]
            }
        }
    """
    logger.info(f"[GRAPHRAG] Executing query: '{question}' (KB: {kb_id})")

    # Step 1: Generate embedding for question
    try:
        query_embedding = generate_query_embedding(question)
    except Exception as e:
        logger.error(f"[GRAPHRAG] Failed to generate query embedding: {e}")
        return {
            "status": "error",
            "error_message": f"Failed to generate embedding: {str(e)}"
        }

    # Step 2: Vector search using KB-specific index
    search_result = vector_search(query_embedding, kb_id=kb_id, top_k=top_k)

    if search_result.get("status") == "error":
        logger.error(f"[GRAPHRAG] Vector search failed: {search_result.get('error_message')}")
        return search_result

    chunks = search_result.get("chunks", [])

    if not chunks or len(chunks) == 0:
        logger.info("[GRAPHRAG] No similar chunks found")
        return {
            "status": "success",
            "question": question,
            "context": {
                "chunks": [],
                "entities": [],
                "domain_nodes": [],
                "relationships": []
            }
        }

    logger.info(f"[GRAPHRAG] Found {len(chunks)} similar chunks")

    # Step 3: Gather graph context with KB-prefixed traversal
    chunk_ids = [chunk["chunk_id"] for chunk in chunks]
    context = gather_chunk_context(chunk_ids, kb_id=kb_id)

    # Add chunks from vector search (with scores)
    context["chunks"] = chunks

    logger.info(f"[GRAPHRAG] ✓ Query complete")

    return {
        "status": "success",
        "question": question,
        "context": context
    }


def format_context_for_llm(context: Dict[str, Any]) -> str:
    """
    Format GraphRAG context into readable text for LLM.

    Args:
        context: Result from graphrag_query()

    Returns:
        Formatted string with all context

    Example output:
        === Relevant Text ===
        1. "Acme Corp has quality issues with steel frames..." (score: 0.92)

        === Entities Mentioned ===
        - Acme Corp (ORGANIZATION)
        - Steel Frame (PRODUCT)

        === Connected Data ===
        - Supplier: Acme Corporation (location: USA)
        - Part: Steel Frame (material: steel)

        === Relationships ===
        - Acme Corporation -SUPPLIES-> Steel Frame
    """
    chunks = context.get("chunks", [])
    entities = context.get("entities", [])
    domain_nodes = context.get("domain_nodes", [])
    relationships = context.get("relationships", [])

    output = []

    # Text chunks
    if chunks:
        output.append("=== Relevant Text ===")
        for i, chunk in enumerate(chunks, 1):
            text = chunk.get("text", "")
            score = chunk.get("score", 0.0)
            source = chunk.get("source", "unknown")
            output.append(f"{i}. \"{text}\" (score: {score:.2f}, source: {source})")
        output.append("")

    # Entities
    if entities:
        output.append("=== Entities Mentioned ===")
        for entity in entities:
            name = entity.get("name", "")
            etype = entity.get("type", "")
            output.append(f"- {name} ({etype})")
        output.append("")

    # Domain nodes
    if domain_nodes:
        output.append("=== Connected Data ===")
        for node in domain_nodes:
            label = _strip_kb_prefix(node.get("label", ""))
            name = node.get("name", "")
            props = node.get("properties", {})
            # Format properties (skip 'name' since it's already shown)
            prop_strs = [f"{k}: {v}" for k, v in props.items() if k != "name" and v is not None]
            prop_str = f" ({', '.join(prop_strs)})" if prop_strs else ""
            output.append(f"- {label}: {name}{prop_str}")
        output.append("")

    # Relationships
    if relationships:
        output.append("=== Relationships ===")
        for rel in relationships:
            from_node = rel.get("from", "")
            rel_type = _strip_kb_prefix(rel.get("type", ""))
            to_node = rel.get("to", "")
            output.append(f"- {from_node} -{rel_type}-> {to_node}")
        output.append("")

    return "\n".join(output)
