"""
API Routes for Domain Graph Construction.



Endpoints:
- POST /construct - Build domain graph from construction plan
- GET /stats - Get graph statistics (node/relationship counts)
- DELETE /clear - Clear the entire graph (use with caution!)

Unlike other agents, this is NOT an LLM-based agent.
It's a rule-based executor that follows the approved construction plan.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from app.services.domain_graph_builder import (
    construct_domain_graph,
    get_graph_stats,
    clear_graph,
    insert_sample_data,
)
from app.services.lexical_graph_builder import build_lexical_graph

from app.services.subject_graph_builder import build_subject_graph, resolve_entities
from app.services.graph_query_service import create_vector_index, query_graph


router = APIRouter(prefix="/api/graph-construction", tags=["graph-construction"])



class NodeConstructionRule(BaseModel):
    """Schema for a node construction rule."""
    construction_type: str = "node"
    source_file: str
    label: str
    unique_column_name: str
    properties: List[str]


class RelationshipConstructionRule(BaseModel):
    """Schema for a relationship construction rule."""
    construction_type: str = "relationship"
    source_file: str
    relationship_type: str
    from_node_label: str
    from_node_column: str
    to_node_label: str
    to_node_column: str
    properties: List[str] = []


class ConstructRequest(BaseModel):
    """
    Request body for construct endpoint.

    The construction_plan is a dictionary where:
    - Keys are names (e.g., "Supplier", "Part", "SUPPLIED_BY")
    - Values are either NodeConstructionRule or RelationshipConstructionRule
    """
    construction_plan: Dict[str, Any]


class ConstructResponse(BaseModel):
    """Response from construct endpoint."""
    status: str
    message: str
    nodes_imported: List[str]
    relationships_imported: List[str]
    errors: Optional[List[Dict[str, Any]]] = None


class StatsResponse(BaseModel):
    """Response from stats endpoint."""
    status: str
    nodes: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    
class LexicalGraphRequest(BaseModel):
    """Request body for lexical graph construction."""
    file_path: str

class SubjectGraphRequest(BaseModel):
    """Request body for subject graph construction."""
    source_file: Optional[str] = None  # Optional filter by source file

class QueryRequest(BaseModel):
    """Request body for GraphRAG query."""
    question: str
    top_k: int = 3  # Number of chunks to retrieve



@router.post("/construct", response_model=ConstructResponse)
async def construct(request: ConstructRequest):
    """
    Construct the domain graph from the approved construction plan.

    This endpoint:
    1. Receives the construction plan (from Lesson 6 Schema Proposal)
    2. Imports all nodes first (with uniqueness constraints)
    3. Then imports all relationships

    Example construction_plan:
    {
        "Supplier": {
            "construction_type": "node",
            "source_file": "suppliers.csv",
            "label": "Supplier",
            "unique_column_name": "supplier_id",
            "properties": ["name", "city", "country"]
        },
        "SUPPLIED_BY": {
            "construction_type": "relationship",
            "source_file": "part_supplier_mapping.csv",
            "relationship_type": "SUPPLIED_BY",
            "from_node_label": "Part",
            "from_node_column": "part_id",
            "to_node_label": "Supplier",
            "to_node_column": "supplier_id",
            "properties": ["lead_time_days"]
        }
    }

    IMPORTANT: CSV files must be in Neo4j's import directory.
    """
    if not request.construction_plan:
        raise HTTPException(
            status_code=400,
            detail="construction_plan cannot be empty"
        )

    result = construct_domain_graph(request.construction_plan)

    # Handle the response based on status
    if result.get("status") == "error":
        raise HTTPException(
            status_code=500,
            detail=result.get("errors", "Unknown error during construction")
        )

    # Extract from nested structure if success
    if result.get("status") == "success":
        construction_result = result.get("construction_result", {})
        return ConstructResponse(
            status="success",
            message=construction_result.get("message", "Construction complete"),
            nodes_imported=construction_result.get("nodes_imported", []),
            relationships_imported=construction_result.get("relationships_imported", [])
        )

    # Partial success or error with details
    return ConstructResponse(
        status=result.get("status", "unknown"),
        message=result.get("message", ""),
        nodes_imported=result.get("nodes_imported", []),
        relationships_imported=result.get("relationships_imported", []),
        errors=result.get("errors")
    )


@router.get("/stats", response_model=StatsResponse)
async def stats():
    """
    Get statistics about the current knowledge graph.

    Returns:
    - Node counts by label
    - Relationship counts by type

    Useful for verifying that the graph was constructed correctly.
    """
    result = get_graph_stats()

    if result.get("status") == "error":
        raise HTTPException(
            status_code=500,
            detail=result.get("error_message", "Failed to get graph stats")
        )

    return StatsResponse(
        status="success",
        nodes=result.get("nodes", []),
        relationships=result.get("relationships", [])
    )


@router.delete("/clear")
async def clear():
    """
    Clear the entire knowledge graph.

    WARNING: This is destructive and cannot be undone!
    Use with caution - primarily for development/testing.

    Returns:
        Confirmation message
    """
    result = clear_graph()

    if result.get("status") == "error":
        raise HTTPException(
            status_code=500,
            detail=result.get("error_message", "Failed to clear graph")
        )

    return {
        "status": "success",
        "message": "Graph cleared successfully"
    }


@router.get("/health")
async def health():
    """
    Health check for graph construction service.

    Verifies Neo4j connection is working.
    """
    try:
        result = get_graph_stats()
        return {
            "status": "healthy",
            "neo4j_connected": result.get("status") == "success"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "neo4j_connected": False,
            "error": str(e)
        }


@router.post("/sample-data")
async def load_sample_data():
    """
    Insert sample data directly into Neo4j (no CSV files needed).

    Use this for testing when CSV import is disabled or files aren't available.
    Creates a small sample graph with:
    - 3 Suppliers
    - 2 Products
    - 3 Assemblies
    - 5 Parts
    - Relationships: Contains, Is_Part_Of, Supplied_By
    """
    result = insert_sample_data()

    if result.get("status") == "error":
        raise HTTPException(
            status_code=500,
            detail=result.get("error_message", "Failed to insert sample data")
        )

    return result.get("insert_result", result)




@router.post("/lexical")
async def build_lexical(request: LexicalGraphRequest):
    """
    Build lexical graph from a markdown file.

    This endpoint:
    1. Reads the file
    2. Chunks the text (500 chars, 100 overlap)
    3. Creates embeddings via OpenAI
    4. Stores chunks in Neo4j with NEXT_CHUNK relationships

    Args:
        file_path: Path to the markdown file to process

    Returns:
        Summary of chunks created

    Example:
        POST /api/graph-construction/lexical
        {"file_path": "/data/reviews/product_review.md"}
    """
    result = await build_lexical_graph(request.file_path)  # await the async function

    if result.get("status") == "error":
        raise HTTPException(
            status_code=500,
            detail=result.get("error_message", "Failed to build lexical graph")
        )

    return result

@router.post("/subject")
async def build_subject(request: SubjectGraphRequest):
    """
    Build subject graph by extracting entities from chunks.
    
    Uses LLM to extract named entities (companies, products, parts, etc.)
    and stores them as Entity nodes linked to Chunks via HAS_ENTITY.
    """
    result = build_subject_graph(request.source_file)
    
    if result.get("status") == "error":
        raise HTTPException(
            status_code=500,
            detail=result.get("error_message", "Failed to build subject graph")
        )
    
    return result


@router.post("/resolve-entities")
async def resolve():
    """
    Perform entity resolution: match extracted entities to domain graph nodes.
    
    Uses Jaro-Winkler fuzzy matching to connect Subject Graph entities
    to Domain Graph nodes via CORRESPONDS_TO relationships.
    """
    result = resolve_entities()
    
    if result.get("status") == "error":
        raise HTTPException(
            status_code=500,
            detail=result.get("error_message", "Failed to resolve entities")
        )
    
    return result

@router.post("/create-vector-index")
async def create_index():
    """
    Create vector index on Chunk embeddings for semantic search.
    
    Must be called once before querying.
    """
    result = create_vector_index()
    
    if result.get("status") == "error":
        raise HTTPException(
            status_code=500,
            detail=result.get("error_message", "Failed to create vector index")
        )
    
    return result


@router.post("/query")
async def query(request: QueryRequest):
    """
    Query the GraphRAG system with a natural language question.
    
    Combines vector search + graph traversal + LLM generation.
    """
    result = query_graph(request.question, request.top_k)
    
    if result.get("status") == "error":
        raise HTTPException(
            status_code=500,
            detail=result.get("error_message", "Query failed")
        )
    
    return result
