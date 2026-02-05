"""
Query Agent - Answers questions about the knowledge graph
"""

import logging
from typing import AsyncGenerator
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.state import SessionState, Message
from app.core.enums import MessageRole
from app.agents.prompts.query_prompts import (
    QUERY_AGENT_SYSTEM_PROMPT,
    CYPHER_GENERATION_PROMPT,
)
from app.services.neo4j_client import neo4j_client
from app.services.graphrag_query_service import graphrag_query, format_context_for_llm

logger = logging.getLogger(__name__)


def format_cypher_results(rows: list[dict]) -> str:
    """Format Neo4j query result rows as readable text for the LLM prompt."""
    if not rows:
        return "(no results)"
    output = []
    for i, row in enumerate(rows, 1):
        props = ", ".join(f"{k}: {v}" for k, v in row.items() if v is not None)
        output.append(f"{i}. {props}")
    return "\n".join(output)


_BLOCKED_CYPHER_KEYWORDS = {"DELETE", "REMOVE", "SET", "CREATE", "MERGE", "DROP", "ALTER"}


def is_cypher_safe(cypher: str) -> bool:
    """
    Check that LLM-generated Cypher is read-only before executing against Neo4j.

    Allows: MATCH ... RETURN, CALL db.index.vector.queryNodes(...)
    Blocks: anything containing DELETE, REMOVE, SET, CREATE, MERGE, DROP, ALTER
    """
    stripped = cypher.strip()
    upper = stripped.upper()

    # Must start with MATCH or the allowed CALL
    if not (upper.startswith("MATCH") or upper.startswith("CALL DB.INDEX.VECTOR.QUERYNODES")):
        logger.warning(f"[QUERY_AGENT] Cypher blocked — does not start with MATCH or allowed CALL: {stripped[:120]}")
        return False

    # Tokenise on whitespace and punctuation boundaries, check for blocked words
    import re
    tokens = set(re.findall(r"[A-Z_]+", upper))
    blocked = tokens & _BLOCKED_CYPHER_KEYWORDS
    if blocked:
        logger.warning(f"[QUERY_AGENT] Cypher blocked — contains {blocked}: {stripped[:120]}")
        return False

    return True


async def stream_query_agent(
    session_state: SessionState,
    user_message: str,
) -> AsyncGenerator[str, None]:
    """
    Stream query agent response tokens.

    Pre-processing (GraphRAG vector search + Cypher structured query) runs first
    as blocking calls — these are fast network round-trips to Neo4j / vector store.
    Then the final synthesis LLM call streams tokens via llm.astream().

    Session state is updated in place — caller must save after iterating.
    """
    logger.info(f"[QUERY_AGENT] Starting stream - Question: {user_message}")

    schema = session_state.approved_schema or session_state.proposed_schema
    if not schema:
        msg = "I don't have information about the graph structure yet. Please build the graph first."
        yield msg
        session_state.messages.append(Message(role=MessageRole.USER, content=user_message))
        session_state.messages.append(Message(role=MessageRole.ASSISTANT, content=msg))
        return

    kb_id = session_state.knowledge_base_id
    logger.info(f"[QUERY_AGENT] KB ID: {kb_id}")

    graph_stats = get_graph_stats(kb_id)

    nodes = schema.get("nodes", [])
    relationships = schema.get("relationships", [])

    # Format node types with KB-prefixed labels wrapped in backticks
    node_types_text = "\n".join([
        f"  • `{kb_id}_{node['label']}`: {', '.join(node.get('properties', []))}"
        for node in nodes
    ]) if nodes else "  (No node types defined)"

    # Format relationship types with KB-prefixed labels and types, all backtick-quoted
    relationship_types_text = "\n".join([
        f"  • (`{kb_id}_{rel['from']}`)-[:`{kb_id}_{rel['type']}`]->(`{kb_id}_{rel['to']}`)"
        for rel in relationships
    ]) if relationships else "  (No relationships defined)"

    system_prompt = QUERY_AGENT_SYSTEM_PROMPT.format(
        node_types=node_types_text,
        relationship_types=relationship_types_text
    )

    # Add graph stats if available
    if graph_stats:
        system_prompt += f"\n\n## Current Graph Stats\n"
        system_prompt += f"- Total nodes: {graph_stats.get('total_nodes', 0)}\n"
        system_prompt += f"- Total relationships: {graph_stats.get('total_relationships', 0)}\n"

    # --- Pre-processing: GraphRAG vector + graph search ---
    try:
        graphrag_result = graphrag_query(user_message, kb_id=kb_id, top_k=5)

        if graphrag_result and graphrag_result.get("status") == "success":
            context = graphrag_result.get("context", {})

            if context and (context.get("chunks") or context.get("entities") or context.get("domain_nodes")):
                formatted_context = format_context_for_llm(context)
                system_prompt += f"\n\n## GraphRAG Context (Retrieved via vector + graph search)\n\n{formatted_context}"
                logger.info(f"[QUERY_AGENT] ✓ GraphRAG context added: "
                           f"{len(context.get('chunks', []))} chunks, "
                           f"{len(context.get('entities', []))} entities, "
                           f"{len(context.get('domain_nodes', []))} domain nodes")
            else:
                logger.info("[QUERY_AGENT] No GraphRAG context found (empty results - CSV-only mode)")
        else:
            error_msg = graphrag_result.get('error_message') if graphrag_result else "No result returned"
            logger.info(f"[QUERY_AGENT] GraphRAG skipped: {error_msg} - Using CSV data only")
    except Exception as e:
        logger.info(f"[QUERY_AGENT] GraphRAG not available: {str(e)} - Using CSV data only")

    # --- Pre-processing: Cypher query for structured data ---
    try:
        cypher = generate_cypher_query(user_message, schema, kb_id=kb_id)

        if not is_cypher_safe(cypher):
            logger.warning("[QUERY_AGENT] Skipping unsafe Cypher — falling back to GraphRAG context only")
        else:
            cypher_result = neo4j_client.send_query(cypher)

            if cypher_result.get("status") == "success" and cypher_result.get("query_result"):
                rows = cypher_result["query_result"]
                formatted_rows = format_cypher_results(rows)
                system_prompt += f"\n\n## Structured Query Results (from Neo4j)\n\n{formatted_rows}"
                logger.info(f"[QUERY_AGENT] ✓ Cypher returned {len(rows)} rows")
            else:
                if cypher_result.get("status") == "error":
                    logger.warning(f"[QUERY_AGENT] Cypher execution error: {cypher_result.get('error_message')}")
                else:
                    logger.info("[QUERY_AGENT] Cypher query returned no results")
    except Exception as e:
        logger.warning(f"[QUERY_AGENT] Cypher query failed: {e}")

    # --- Build message history ---
    langchain_messages = []
    for msg in session_state.messages:
        if msg.role == MessageRole.USER:
            langchain_messages.append(HumanMessage(content=msg.content))
        elif msg.role == MessageRole.ASSISTANT:
            langchain_messages.append(AIMessage(content=msg.content))
    langchain_messages.append(HumanMessage(content=user_message))

    messages = [SystemMessage(content=system_prompt)] + langchain_messages

    # --- Stream the final synthesis ---
    llm = ChatOpenAI(
        model=settings.openai_model_name,
        api_key=settings.openai_api_key,
        temperature=0.3
    )

    full_response = ""
    async for chunk in llm.astream(messages):
        token = chunk.content
        if token:
            full_response += token
            yield token

    logger.info(f"[QUERY_AGENT] Stream complete: {full_response[:100]}...")

    # Update session state (caller saves)
    session_state.messages.append(Message(role=MessageRole.USER, content=user_message))
    session_state.messages.append(Message(role=MessageRole.ASSISTANT, content=full_response))


def get_graph_stats(kb_id: str | None = None) -> dict:
    """Get statistics about the graph, filtered by KB if provided."""
    try:
        if kb_id:
            node_query = "MATCH (n {kb_id: $kb_id}) RETURN count(n) as total"
            node_result = neo4j_client.send_query(node_query, {"kb_id": kb_id})
        else:
            node_query = "MATCH (n) RETURN count(n) as total"
            node_result = neo4j_client.send_query(node_query)

        total_nodes = 0
        if node_result.get("status") == "success" and node_result.get("query_result"):
            total_nodes = node_result["query_result"][0].get("total", 0)

        if kb_id:
            rel_query = "MATCH (a {kb_id: $kb_id})-[r]->(b {kb_id: $kb_id}) RETURN count(r) as total"
            rel_result = neo4j_client.send_query(rel_query, {"kb_id": kb_id})
        else:
            rel_query = "MATCH ()-[r]->() RETURN count(r) as total"
            rel_result = neo4j_client.send_query(rel_query)

        total_rels = 0
        if rel_result.get("status") == "success" and rel_result.get("query_result"):
            total_rels = rel_result["query_result"][0].get("total", 0)

        return {
            "total_nodes": total_nodes,
            "total_relationships": total_rels
        }
    except Exception as e:
        logger.error(f"[QUERY_AGENT] Error getting graph stats: {e}")
        return {}


def generate_cypher_query(question: str, schema: dict, kb_id: str | None = None) -> str:
    """
    Generate a Cypher query from natural language question.

    Args:
        question: User's natural language question
        schema: Graph schema with nodes and relationships
        kb_id: Knowledge base identifier for label prefixing

    Returns:
        Generated Cypher query string
    """
    nodes = schema.get("nodes", [])
    relationships = schema.get("relationships", [])

    # Format schema with KB-prefixed labels wrapped in backticks (required for labels with spaces)
    prefix = f"{kb_id}_" if kb_id else ""
    node_types_text = "\n".join([
        f"  • `{prefix}{node['label']}`: {', '.join(node.get('properties', []))}"
        for node in nodes
    ])

    relationship_types_text = "\n".join([
        f"  • (`{prefix}{rel['from']}`)-[:`{prefix}{rel['type']}`]->(`{prefix}{rel['to']}`)"
        for rel in relationships
    ])

    llm = ChatOpenAI(
        model=settings.openai_model_name,
        api_key=settings.openai_api_key,
        temperature=0
    )

    prompt_text = CYPHER_GENERATION_PROMPT.format(
        node_types=node_types_text,
        relationship_types=relationship_types_text,
        question=question
    )

    response = llm.invoke([HumanMessage(content=prompt_text)])
    cypher = response.content.strip()

    # Clean up the response (remove markdown if present)
    if cypher.startswith("```"):
        lines = cypher.split("\n")
        cypher = "\n".join(lines[1:-1]) if len(lines) > 2 else cypher

    logger.info(f"[QUERY_AGENT] Generated Cypher: {cypher}")
    return cypher
