"""
Graph Query Service - The "RAG" in GraphRAG.

This service combines:
1. Vector search (semantic similarity on chunk embeddings)
2. Graph traversal (follow relationships to find connected context)
3. LLM generation (answer questions using retrieved context)

The power of GraphRAG: Instead of just retrieving similar chunks,
we can also traverse the graph to find related entities and their connections.
"""

from typing import Any, Dict, List, Optional
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate

from app.services.neo4j_client import get_neo4j_client, tool_success, tool_error
from app.core.config import get_settings


# =============================================================================
# VECTOR SEARCH
# =============================================================================

def create_vector_index() -> Dict[str, Any]:
    """
    Create a vector index on Chunk embeddings for semantic search.

    This enables fast similarity search using cosine distance.
    Only needs to be run once per database.
    """
    client = get_neo4j_client()

    query = """
    CREATE VECTOR INDEX chunk_embeddings IF NOT EXISTS
    FOR (c:Chunk) ON c.embedding
    OPTIONS {indexConfig: {
        `vector.dimensions`: 1536,
        `vector.similarity_function`: 'cosine'
    }}
    """

    result = client.send_query(query)

    if result.get("status") == "error":
        return tool_error(f"Failed to create vector index: {result.get('error_message')}")

    return tool_success("index_created", {"message": "Vector index created successfully"})


def vector_search(query_text: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Find chunks semantically similar to the query.

    Args:
        query_text: The user's question
        top_k: Number of similar chunks to retrieve

    Returns:
        List of chunks with their similarity scores
    """
    settings = get_settings()
    client = get_neo4j_client()

    # Generate embedding for the query
    embedder = OpenAIEmbeddings(api_key=settings.openai_api_key)
    query_embedding = embedder.embed_query(query_text)

    # Search for similar chunks using vector index
    search_query = """
    CALL db.index.vector.queryNodes('chunk_embeddings', $top_k, $query_embedding)
    YIELD node, score
    RETURN node.id as chunk_id,
           node.text as text,
           node.source as source,
           score
    ORDER BY score DESC
    """

    result = client.send_query(search_query, {
        "top_k": top_k,
        "query_embedding": query_embedding
    })

    if result.get("status") == "error":
        return []

    return result.get("query_result", [])


# =============================================================================
# GRAPH TRAVERSAL - The GraphRAG Magic
# =============================================================================

def get_connected_context(chunk_ids: List[str]) -> Dict[str, Any]:
    """
    Traverse the graph to find entities and domain nodes connected to chunks.

    This is what makes GraphRAG powerful:
    - Find entities mentioned in the chunks
    - Follow CORRESPONDS_TO to get domain graph context
    - Return structured knowledge alongside text chunks

    Args:
        chunk_ids: List of chunk IDs from vector search

    Returns:
        Dict with entities and their domain graph connections
    """
    client = get_neo4j_client()

    # Find entities connected to these chunks and their domain graph links
    query = """
    UNWIND $chunk_ids AS chunk_id
    MATCH (c:Chunk {id: chunk_id})
    OPTIONAL MATCH (e:Entity)-[:HAS_ENTITY]->(c)
    OPTIONAL MATCH (e)-[:CORRESPONDS_TO]->(d)
    RETURN DISTINCT
        e.name as entity_name,
        e.type as entity_type,
        labels(d)[0] as domain_label,
        CASE
            WHEN d:Supplier THEN d.name
            WHEN d:Part THEN d.part_name
            WHEN d:Product THEN d.product_name
            WHEN d:Assembly THEN d.assembly_name
            ELSE null
        END as domain_name
    """

    result = client.send_query(query, {"chunk_ids": chunk_ids})

    if result.get("status") == "error":
        return {"entities": [], "domain_nodes": []}

    records = result.get("query_result", [])

    # Separate entities and domain connections
    entities = []
    domain_nodes = []

    for record in records:
        if record.get("entity_name"):
            entities.append({
                "name": record["entity_name"],
                "type": record["entity_type"]
            })
        if record.get("domain_name"):
            domain_nodes.append({
                "name": record["domain_name"],
                "label": record["domain_label"]
            })

    # Deduplicate
    entities = list({e["name"]: e for e in entities}.values())
    domain_nodes = list({d["name"]: d for d in domain_nodes}.values())

    return {
        "entities": entities,
        "domain_nodes": domain_nodes
    }


def get_domain_graph_context(entity_names: List[str]) -> List[Dict[str, Any]]:
    """
    Get additional context from domain graph for resolved entities.

    For example, if "Acme Electronics" is mentioned, we can retrieve:
    - What parts they supply
    - Lead times and costs
    - Related products

    Args:
        entity_names: Names of entities to get context for

    Returns:
        List of context facts from the domain graph
    """
    client = get_neo4j_client()

    # Get supplier relationships
    supplier_query = """
    UNWIND $names AS name
    MATCH (s:Supplier {name: name})<-[:Supplied_By]-(p:Part)
    RETURN s.name as supplier,
           collect(p.part_name) as parts_supplied,
           'supplies parts' as relationship
    """

    result = client.send_query(supplier_query, {"names": entity_names})

    facts = []
    if result.get("status") == "success":
        for record in result.get("query_result", []):
            if record.get("parts_supplied"):
                facts.append({
                    "subject": record["supplier"],
                    "relationship": "supplies",
                    "objects": record["parts_supplied"]
                })

    # Get product structure
    product_query = """
    UNWIND $names AS name
    MATCH (p:Product {product_name: name})-[:Contains]->(a:Assembly)
    RETURN p.product_name as product,
           collect(a.assembly_name) as assemblies
    """

    result = client.send_query(product_query, {"names": entity_names})

    if result.get("status") == "success":
        for record in result.get("query_result", []):
            if record.get("assemblies"):
                facts.append({
                    "subject": record["product"],
                    "relationship": "contains",
                    "objects": record["assemblies"]
                })

    return facts


# =============================================================================
# LLM GENERATION
# =============================================================================

GRAPHRAG_PROMPT = """You are a helpful assistant that answers questions using the provided context.

## Retrieved Text Chunks (from documents):
{chunks}

## Entities Mentioned:
{entities}

## Structured Knowledge from Graph:
{graph_facts}

## Question:
{question}

Instructions:
1. Answer based on the provided context
2. Reference specific entities and relationships when relevant
3. If the context doesn't contain enough information, say so
4. Be concise but complete

Answer:"""


def generate_answer(
    question: str,
    chunks: List[Dict[str, Any]],
    entities: List[Dict[str, Any]],
    graph_facts: List[Dict[str, Any]]
) -> str:
    """
    Generate an answer using LLM with retrieved context.

    Args:
        question: User's question
        chunks: Retrieved text chunks from vector search
        entities: Extracted entities from chunks
        graph_facts: Structured facts from domain graph

    Returns:
        Generated answer string
    """
    settings = get_settings()

    llm = ChatOpenAI(
        model=settings.openai_model_name,
        api_key=settings.openai_api_key,
        temperature=0.3
    )

    # Format chunks
    chunks_text = "\n\n".join([
        f"[Chunk {i+1}] {chunk.get('text', '')}"
        for i, chunk in enumerate(chunks)
    ])

    # Format entities
    entities_text = ", ".join([
        f"{e['name']} ({e['type']})"
        for e in entities
    ]) if entities else "No specific entities identified"

    # Format graph facts
    facts_text = "\n".join([
        f"- {fact['subject']} {fact['relationship']} {', '.join(fact['objects'])}"
        for fact in graph_facts
    ]) if graph_facts else "No additional structured knowledge available"

    prompt = ChatPromptTemplate.from_template(GRAPHRAG_PROMPT)
    chain = prompt | llm

    response = chain.invoke({
        "chunks": chunks_text,
        "entities": entities_text,
        "graph_facts": facts_text,
        "question": question
    })

    return response.content


# =============================================================================
# MAIN QUERY FUNCTION
# =============================================================================

def query_graph(question: str, top_k: int = 3) -> Dict[str, Any]:
    """
    Main GraphRAG query function.

    Combines:
    1. Vector search to find relevant chunks
    2. Graph traversal to find connected entities and domain knowledge
    3. LLM generation to answer the question

    Args:
        question: User's question
        top_k: Number of chunks to retrieve

    Returns:
        Dict with answer and supporting evidence

    Example:
        result = query_graph("Who supplies the Servo Motor?")
        # Returns: {"answer": "Acme Electronics supplies the Servo Motor...", ...}
    """
    # Step 1: Vector search for relevant chunks
    chunks = vector_search(question, top_k)

    if not chunks:
        return tool_error("No relevant chunks found. Make sure the vector index exists.")

    chunk_ids = [c["chunk_id"] for c in chunks]

    # Step 2: Get connected entities from subject graph
    connected = get_connected_context(chunk_ids)
    entities = connected["entities"]
    domain_nodes = connected["domain_nodes"]

    # Step 3: Get structured facts from domain graph
    entity_names = [e["name"] for e in entities]
    domain_names = [d["name"] for d in domain_nodes]
    all_names = list(set(entity_names + domain_names))

    graph_facts = get_domain_graph_context(all_names)

    # Step 4: Generate answer using LLM
    answer = generate_answer(question, chunks, entities, graph_facts)

    return tool_success("query_result", {
        "answer": answer,
        "chunks_used": len(chunks),
        "entities_found": entities,
        "graph_facts": graph_facts,
        "sources": [c.get("source") for c in chunks]
    })
