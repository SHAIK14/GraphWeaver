"""
Subject Graph Builder Service.

This service extracts named entities from chunks using an LLM and creates
the Subject Graph layer in Neo4j.

The Subject Graph bridges unstructured text (Lexical Graph) with structured
data (Domain Graph) through Entity Resolution.

Flow:
1. Fetch Chunk nodes from Neo4j
2. For each chunk, use LLM to extract entities
3. Create Entity nodes with type and name
4. Link Entity -> Chunk via HAS_ENTITY relationship
"""

from typing import Any, Dict, List
import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.services.neo4j_client import get_neo4j_client, tool_success, tool_error
from app.core.config import get_settings


# =============================================================================
# ENTITY EXTRACTION PROMPT
# =============================================================================

ENTITY_EXTRACTION_PROMPT = """You are an entity extraction expert. Extract all named entities from the following text chunk.

For each entity, identify:
1. name: The exact text of the entity as it appears
2. type: One of [COMPANY, PRODUCT, PART, ASSEMBLY, LOCATION, PERSON]

Text chunk:
{chunk_text}

Return a JSON array of entities. Example format:
[
    {{"name": "Acme Electronics", "type": "COMPANY"}},
    {{"name": "Industrial Robot Arm", "type": "PRODUCT"}},
    {{"name": "Servo Motor", "type": "PART"}}
]

Only return the JSON array, no other text. If no entities found, return [].
"""




def get_chunks_from_neo4j(source_file: str = None) -> List[Dict[str, Any]]:
    """
    Fetch chunk nodes from Neo4j.

    Args:
        source_file: Optional filter by source file name

    Returns:
        List of chunk dictionaries with id, text, index, source
    """
    client = get_neo4j_client()

    if source_file:
        query = """
        MATCH (c:Chunk)
        WHERE c.source = $source_file
        RETURN c.id as id, c.text as text, c.index as index, c.source as source
        ORDER BY c.index
        """
        result = client.send_query(query, {"source_file": source_file})
    else:
        query = """
        MATCH (c:Chunk)
        RETURN c.id as id, c.text as text, c.index as index, c.source as source
        ORDER BY c.source, c.index
        """
        result = client.send_query(query)

    if result.get("status") == "error":
        return []

    return result.get("query_result", [])


def extract_entities_from_chunk(chunk_text: str) -> List[Dict[str, str]]:
    """
    Use LLM to extract named entities from a text chunk.

    Args:
        chunk_text: The text content of the chunk

    Returns:
        List of entity dictionaries with 'name' and 'type' keys

    Example:
        entities = extract_entities_from_chunk("Acme Electronics supplies circuit boards...")
        # Returns: [{"name": "Acme Electronics", "type": "COMPANY"}, ...]
    """
    settings = get_settings()

    llm = ChatOpenAI(
        model=settings.openai_model_name,
        api_key=settings.openai_api_key,
        temperature=0  # Deterministic for consistent extraction
    )

    prompt = ChatPromptTemplate.from_template(ENTITY_EXTRACTION_PROMPT)
    chain = prompt | llm

    response = chain.invoke({"chunk_text": chunk_text})

    # Parse the JSON response
    # LLM sometimes wraps JSON in markdown code blocks, so we need to clean it
    content = response.content.strip()

    # Remove markdown code block if present
    if content.startswith("```"):
        # Remove ```json or ``` at start
        lines = content.split("\n")
        # Skip first line (```json) and last line (```)
        content = "\n".join(lines[1:-1]) if len(lines) > 2 else ""

    try:
        entities = json.loads(content)
        # Validate structure
        validated = []
        for entity in entities:
            if isinstance(entity, dict) and "name" in entity and "type" in entity:
                validated.append({
                    "name": entity["name"],
                    "type": entity["type"].upper()
                })
        return validated
    except json.JSONDecodeError:
        # If LLM returns malformed JSON, return empty list
        return []


def store_entities_in_neo4j(chunk_id: str, entities: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Store extracted entities in Neo4j and link them to the source chunk.

    Creates:
    - Entity nodes with name and type properties
    - HAS_ENTITY relationships from Entity to Chunk

    Args:
        chunk_id: The ID of the source chunk
        entities: List of entity dictionaries with 'name' and 'type'

    Returns:
        Dict with status and count of entities stored
    """
    if not entities:
        return tool_success("entities_stored", {"count": 0, "chunk_id": chunk_id})

    client = get_neo4j_client()

    # Create entities and link to chunk
    # Using MERGE to avoid duplicates (same entity can appear in multiple chunks)
    query = """
    MATCH (c:Chunk {id: $chunk_id})
    UNWIND $entities AS entity
    MERGE (e:Entity {name: entity.name, type: entity.type})
    MERGE (e)-[:HAS_ENTITY]->(c)
    RETURN count(e) as entity_count
    """

    result = client.send_query(query, {"chunk_id": chunk_id, "entities": entities})

    if result.get("status") == "error":
        return tool_error(f"Failed to store entities: {result.get('error_message')}")

    return tool_success("entities_stored", {
        "count": len(entities),
        "chunk_id": chunk_id,
        "entities": [e["name"] for e in entities]
    })




def build_subject_graph(source_file: str = None) -> Dict[str, Any]:
    """
    Main orchestrator: Build subject graph by extracting entities from all chunks.

    This function:
    1. Fetches all chunks (optionally filtered by source file)
    2. For each chunk, extracts entities using LLM
    3. Stores entities in Neo4j with HAS_ENTITY relationships

    Args:
        source_file: Optional - only process chunks from this file

    Returns:
        Dict with status and summary of entities extracted

    Example:
        result = build_subject_graph("product_review.md")
        # Returns: {"status": "success", "total_entities": 15, ...}
    """
    # Step 1: Get chunks
    chunks = get_chunks_from_neo4j(source_file)

    if not chunks:
        return tool_error("No chunks found to process")

    # Step 2 & 3: Extract and store entities for each chunk
    total_entities = 0
    processed_chunks = 0
    all_entities = []
    errors = []

    for chunk in chunks:
        chunk_id = chunk.get("id")
        chunk_text = chunk.get("text", "")

        if not chunk_text:
            continue

        # Extract entities using LLM
        entities = extract_entities_from_chunk(chunk_text)

        # Store in Neo4j
        store_result = store_entities_in_neo4j(chunk_id, entities)

        if store_result.get("status") == "error":
            errors.append({"chunk_id": chunk_id, "error": store_result.get("error_message")})
        else:
            total_entities += len(entities)
            processed_chunks += 1
            all_entities.extend(entities)

    # Deduplicate entity names for summary
    unique_entities = list({e["name"]: e for e in all_entities}.values())

    if errors:
        return {
            "status": "partial",
            "message": f"Processed {processed_chunks} chunks with {len(errors)} errors",
            "total_entities": total_entities,
            "unique_entities": len(unique_entities),
            "entities": unique_entities,
            "errors": errors
        }

    return tool_success("subject_graph_built", {
        "message": f"Extracted {total_entities} entities from {processed_chunks} chunks",
        "total_entities": total_entities,
        "unique_entities": len(unique_entities),
        "processed_chunks": processed_chunks,
        "entities": unique_entities
    })




def get_domain_node_names() -> Dict[str, List[str]]:
    """
    Get all node names from the Domain Graph for entity resolution.

    Returns:
        Dict mapping label to list of names, e.g.:
        {"Supplier": ["Acme Electronics", "Global Steel"], "Part": ["Servo Motor", ...]}
    """
    client = get_neo4j_client()

    # Get suppliers
    suppliers_query = "MATCH (s:Supplier) RETURN s.name as name"
    suppliers_result = client.send_query(suppliers_query)

    # Get parts
    parts_query = "MATCH (p:Part) RETURN p.part_name as name"
    parts_result = client.send_query(parts_query)

    # Get products
    products_query = "MATCH (p:Product) RETURN p.product_name as name"
    products_result = client.send_query(products_query)

    # Get assemblies
    assemblies_query = "MATCH (a:Assembly) RETURN a.assembly_name as name"
    assemblies_result = client.send_query(assemblies_query)

    return {
        "Supplier": [r["name"] for r in suppliers_result.get("query_result", []) if r.get("name")],
        "Part": [r["name"] for r in parts_result.get("query_result", []) if r.get("name")],
        "Product": [r["name"] for r in products_result.get("query_result", []) if r.get("name")],
        "Assembly": [r["name"] for r in assemblies_result.get("query_result", []) if r.get("name")]
    }


def jaro_winkler_similarity(s1: str, s2: str) -> float:
    """
    Calculate Jaro-Winkler similarity between two strings.

    This is a fuzzy matching algorithm that gives higher scores to strings
    that match from the beginning (good for names).

    Returns:
        Float between 0 and 1, where 1 is an exact match
    """
    # Simple implementation - in production use jellyfish or rapidfuzz library
    s1_lower = s1.lower()
    s2_lower = s2.lower()

    if s1_lower == s2_lower:
        return 1.0

    len1, len2 = len(s1_lower), len(s2_lower)
    if len1 == 0 or len2 == 0:
        return 0.0

    # Match window
    match_distance = max(len1, len2) // 2 - 1
    if match_distance < 0:
        match_distance = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2
    matches = 0
    transpositions = 0

    # Find matches
    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)

        for j in range(start, end):
            if s2_matches[j] or s1_lower[i] != s2_lower[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    # Count transpositions
    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1_lower[i] != s2_lower[k]:
            transpositions += 1
        k += 1

    jaro = (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3

    # Winkler modification - boost for common prefix
    prefix = 0
    for i in range(min(len1, len2, 4)):
        if s1_lower[i] == s2_lower[i]:
            prefix += 1
        else:
            break

    return jaro + prefix * 0.1 * (1 - jaro)


def resolve_entities(threshold: float = 0.85) -> Dict[str, Any]:
    """
    Perform entity resolution: match Subject Graph entities to Domain Graph nodes.

    Uses Jaro-Winkler similarity for fuzzy matching. Creates CORRESPONDS_TO
    relationships between matching Entity and Domain nodes.

    Args:
        threshold: Minimum similarity score to create a match (default 0.85)

    Returns:
        Dict with status and list of resolved matches
    """
    client = get_neo4j_client()

    # Get all entities from Subject Graph
    entities_query = "MATCH (e:Entity) RETURN e.name as name, e.type as type"
    entities_result = client.send_query(entities_query)

    if entities_result.get("status") == "error":
        return tool_error(f"Failed to fetch entities: {entities_result.get('error_message')}")

    entities = entities_result.get("query_result", [])

    # Get domain node names
    domain_names = get_domain_node_names()

    # Perform matching
    matches = []

    for entity in entities:
        entity_name = entity.get("name", "")
        entity_type = entity.get("type", "")

        best_match = None
        best_score = 0
        best_label = None

        # Check against each domain label
        for label, names in domain_names.items():
            for domain_name in names:
                score = jaro_winkler_similarity(entity_name, domain_name)
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = domain_name
                    best_label = label

        if best_match:
            matches.append({
                "entity_name": entity_name,
                "entity_type": entity_type,
                "domain_name": best_match,
                "domain_label": best_label,
                "similarity": round(best_score, 3)
            })

    # Create CORRESPONDS_TO relationships for matches
    for match in matches:
        # Dynamic label matching based on domain_label
        if match["domain_label"] == "Supplier":
            query = """
            MATCH (e:Entity {name: $entity_name})
            MATCH (d:Supplier {name: $domain_name})
            MERGE (e)-[r:CORRESPONDS_TO]->(d)
            SET r.similarity = $similarity
            """
        elif match["domain_label"] == "Part":
            query = """
            MATCH (e:Entity {name: $entity_name})
            MATCH (d:Part {part_name: $domain_name})
            MERGE (e)-[r:CORRESPONDS_TO]->(d)
            SET r.similarity = $similarity
            """
        elif match["domain_label"] == "Product":
            query = """
            MATCH (e:Entity {name: $entity_name})
            MATCH (d:Product {product_name: $domain_name})
            MERGE (e)-[r:CORRESPONDS_TO]->(d)
            SET r.similarity = $similarity
            """
        elif match["domain_label"] == "Assembly":
            query = """
            MATCH (e:Entity {name: $entity_name})
            MATCH (d:Assembly {assembly_name: $domain_name})
            MERGE (e)-[r:CORRESPONDS_TO]->(d)
            SET r.similarity = $similarity
            """
        else:
            continue

        client.send_query(query, {
            "entity_name": match["entity_name"],
            "domain_name": match["domain_name"],
            "similarity": match["similarity"]
        })

    return tool_success("entity_resolution_complete", {
        "message": f"Resolved {len(matches)} entities to domain graph",
        "matches_count": len(matches),
        "matches": matches
    })
