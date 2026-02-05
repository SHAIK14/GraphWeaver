from langchain_core.tools import tool
from typing import Dict, Any, List

@tool
def request_more_files() -> Dict[str, Any]:
    """
    Tell user we need more files to proceed.
    Use this when user has a goal but no files uploaded yet.
    """
    return {
        "status": "awaiting_files",
        "message": "Please upload or paste your data files"
    }

@tool
def propose_schema(
    nodes: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Propose graph schema based on analyzed files.

    Args:
        nodes: List of node types with properties
            Example: [{"label": "Supplier", "properties": ["name", "email"]}]
        relationships: List of relationship types
            Example: [{"type": "SUPPLIES", "from": "Supplier", "to": "Product"}]
    """
    return {
        "status": "schema_proposed",
        "nodes": nodes,
        "relationships": relationships
    }

@tool
def approve_schema() -> Dict[str, Any]:
    """
    User approves the proposed schema.
    Call this when user says "approve", "looks good", "yes proceed", etc.
    This transitions to BUILD phase where the graph will be constructed.
    """
    return {
        "status": "schema_approved",
        "message": "Schema approved! Ready to build the knowledge graph."
    }
