"""
Tools for the Schema Proposal Agent.

These tools allow the agent to:
1. Retrieve context from previous agents (user goal, approved files)
2. Search and sample files to understand their structure
3. Propose node and relationship constructions
4. Manage the construction plan (get, remove, approve)

Note: The actual state updates happen in the graph's execute_tools_node function.
      These tools return data that signals what state changes should occur.
"""

from pathlib import Path
from itertools import islice
from typing import Dict, Any, List
from langchain_core.tools import tool

from app.core.config import get_settings




# Keys from previous agents
APPROVED_USER_GOAL = "approved_user_goal"
APPROVED_FILES = "approved_files"

# Keys for this agent
PROPOSED_CONSTRUCTION_PLAN = "proposed_construction_plan"
APPROVED_CONSTRUCTION_PLAN = "approved_construction_plan"
FEEDBACK = "feedback"

# Tool result keys
NODE_CONSTRUCTION = "node_construction"
RELATIONSHIP_CONSTRUCTION = "relationship_construction"
SEARCH_RESULTS = "search_results"


# =============================================================================
# CONTEXT RETRIEVAL TOOLS (Read from previous agents)
# =============================================================================

@tool
def get_approved_user_goal() -> Dict[str, Any]:
    """
    Retrieves the user's approved goal from the previous agent.

    The goal contains:
    - kind_of_graph: Short description (e.g., "supply chain analysis")
    - graph_description: Detailed explanation of what the user wants

    Returns:
        dict: Contains 'status' and either the goal or an error message
    """
    # Note: Actual value is injected by execute_tools_node from state
    return {"status": "success", "message": "Goal will be retrieved from state"}


@tool
def get_approved_files() -> Dict[str, Any]:
    """
    Retrieves the list of approved files from the previous agent.

    These are the files that should be transformed into the knowledge graph.

    Returns:
        dict: Contains 'status' and list of approved file names
    """
    # Note: Actual value is injected by execute_tools_node from state
    return {"status": "success", "message": "Approved files will be retrieved from state"}




@tool
def sample_file(file_path: str) -> Dict[str, Any]:
    """
    Reads the first 100 lines of a file to understand its structure.

    Use this to see column headers and sample data before proposing
    how to construct nodes or relationships from the file.

    Args:
        file_path: Path to file, relative to import directory (e.g., "suppliers.csv")

    Returns:
        dict: Contains 'status' and either 'content' or 'error_message'
    """
    # Security: reject absolute paths
    if Path(file_path).is_absolute():
        return {"status": "error", "error_message": "File path must be relative to import directory"}

    settings = get_settings()
    import_dir = Path(settings.data_import_dir)
    full_path = import_dir / file_path

    if not full_path.exists():
        return {"status": "error", "error_message": f"File not found: {file_path}"}

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            lines = list(islice(f, 100))
            content = ''.join(lines)
            return {"status": "success", "content": content}
    except Exception as e:
        return {"status": "error", "error_message": f"Error reading file: {e}"}


@tool
def search_file(file_path: str, query: str) -> Dict[str, Any]:
    """
    Searches a file for lines containing the given query string.

    Use this to verify if a column contains unique values by searching
    for duplicate values. Case insensitive search.

    Args:
        file_path: Path to file, relative to import directory
        query: The string to search for

    Returns:
        dict: Contains 'status' and either 'search_results' or 'error_message'
              search_results includes 'matching_lines' and 'metadata'
    """
    # Security: reject absolute paths
    if Path(file_path).is_absolute():
        return {"status": "error", "error_message": "File path must be relative to import directory"}

    settings = get_settings()
    import_dir = Path(settings.data_import_dir)
    full_path = import_dir / file_path

    if not full_path.exists():
        return {"status": "error", "error_message": f"File not found: {file_path}"}

    if not full_path.is_file():
        return {"status": "error", "error_message": f"Path is not a file: {file_path}"}

    # Handle empty query
    if not query:
        return {
            "status": "success",
            SEARCH_RESULTS: {
                "metadata": {"path": file_path, "query": query, "lines_found": 0},
                "matching_lines": []
            }
        }

    matching_lines = []
    search_query = query.lower()

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                if search_query in line.lower():
                    matching_lines.append({
                        "line_number": i,
                        "content": line.strip()
                    })
    except Exception as e:
        return {"status": "error", "error_message": f"Error searching file {file_path}: {e}"}

    return {
        "status": "success",
        SEARCH_RESULTS: {
            "metadata": {
                "path": file_path,
                "query": query,
                "lines_found": len(matching_lines)
            },
            "matching_lines": matching_lines
        }
    }


# =============================================================================
# CONSTRUCTION PROPOSAL TOOLS
# =============================================================================

@tool
def propose_node_construction(
    approved_file: str,
    proposed_label: str,
    unique_column_name: str,
    proposed_properties: List[str]
) -> Dict[str, Any]:
    """
    Proposes how to construct nodes from an approved file.

    Call this when a file represents entities (like suppliers, products, etc.)
    that should become nodes in the knowledge graph.

    Args:
        approved_file: The file to construct nodes from (e.g., "suppliers.csv")
        proposed_label: The Neo4j node label (e.g., "Supplier")
        unique_column_name: Column that uniquely identifies each node (e.g., "supplier_id")
        proposed_properties: List of columns to import as node properties

    Returns:
        dict: Contains 'status' and either 'node_construction' or 'error_message'

    Example:
        propose_node_construction(
            approved_file="suppliers.csv",
            proposed_label="Supplier",
            unique_column_name="supplier_id",
            proposed_properties=["name", "location", "reliability_score"]
        )
    """
    # Validate the file exists and has the unique column
    settings = get_settings()
    import_dir = Path(settings.data_import_dir)
    full_path = import_dir / approved_file

    if not full_path.exists():
        return {"status": "error", "error_message": f"File not found: {approved_file}"}

    # Check if unique column exists in file
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            header = f.readline().lower()
            if unique_column_name.lower() not in header:
                return {
                    "status": "error",
                    "error_message": f"Column '{unique_column_name}' not found in {approved_file}. Check the file headers."
                }
    except Exception as e:
        return {"status": "error", "error_message": f"Error reading file: {e}"}

    # Create the construction rule
    node_construction = {
        "construction_type": "node",
        "source_file": approved_file,
        "label": proposed_label,
        "unique_column_name": unique_column_name,
        "properties": proposed_properties
    }

    return {"status": "success", NODE_CONSTRUCTION: node_construction, "label": proposed_label}


@tool
def propose_relationship_construction(
    approved_file: str,
    proposed_relationship_type: str,
    from_node_label: str,
    from_node_column: str,
    to_node_label: str,
    to_node_column: str,
    proposed_properties: List[str]
) -> Dict[str, Any]:
    """
    Proposes how to construct relationships from an approved file.

    Call this when:
    1. A file represents connections between entities (full relationship)
    2. A node file has foreign keys to other nodes (reference relationship)

    Args:
        approved_file: The file to construct relationships from
        proposed_relationship_type: The Neo4j relationship type (e.g., "SUPPLIES")
        from_node_label: Label of the source node (e.g., "Supplier")
        from_node_column: Column in file that references source node
        to_node_label: Label of the target node (e.g., "Part")
        to_node_column: Column in file that references target node
        proposed_properties: List of columns to import as relationship properties

    Returns:
        dict: Contains 'status' and either 'relationship_construction' or 'error_message'

    Example (reference relationship in parts.csv):
        propose_relationship_construction(
            approved_file="parts.csv",
            proposed_relationship_type="SUPPLIED_BY",
            from_node_label="Part",
            from_node_column="part_id",
            to_node_label="Supplier",
            to_node_column="supplier_id",
            proposed_properties=[]
        )
    """
    # Validate the file exists
    settings = get_settings()
    import_dir = Path(settings.data_import_dir)
    full_path = import_dir / approved_file

    if not full_path.exists():
        return {"status": "error", "error_message": f"File not found: {approved_file}"}

    # Check if both columns exist in file
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            header = f.readline().lower()

            if from_node_column.lower() not in header:
                return {
                    "status": "error",
                    "error_message": f"Column '{from_node_column}' not found in {approved_file}. Check the file headers."
                }

            if to_node_column.lower() not in header:
                return {
                    "status": "error",
                    "error_message": f"Column '{to_node_column}' not found in {approved_file}. Check the file headers."
                }
    except Exception as e:
        return {"status": "error", "error_message": f"Error reading file: {e}"}

    # Create the construction rule
    relationship_construction = {
        "construction_type": "relationship",
        "source_file": approved_file,
        "relationship_type": proposed_relationship_type,
        "from_node_label": from_node_label,
        "from_node_column": from_node_column,
        "to_node_label": to_node_label,
        "to_node_column": to_node_column,
        "properties": proposed_properties
    }

    return {
        "status": "success",
        RELATIONSHIP_CONSTRUCTION: relationship_construction,
        "relationship_type": proposed_relationship_type
    }


# =============================================================================
# CONSTRUCTION PLAN MANAGEMENT TOOLS
# =============================================================================

@tool
def get_proposed_construction_plan() -> Dict[str, Any]:
    """
    Gets the current proposed construction plan.

    The plan is a dictionary where:
    - Keys are node labels or relationship types
    - Values are construction rules (node or relationship)

    Use this to review the current plan before presenting to user.

    Returns:
        dict: The current construction plan (may be empty)
    """
    # Note: Actual value is injected by execute_tools_node from state
    return {"status": "success", "message": "Construction plan will be retrieved from state"}


@tool
def remove_node_construction(node_label: str) -> Dict[str, Any]:
    """
    Removes a node construction from the proposed plan.

    Use this when the critic finds problems with a node construction
    and you need to remove it before proposing a corrected version.

    Args:
        node_label: The label of the node construction to remove

    Returns:
        dict: Confirmation of removal
    """
    return {"status": "success", "node_construction_removed": node_label}


@tool
def remove_relationship_construction(relationship_type: str) -> Dict[str, Any]:
    """
    Removes a relationship construction from the proposed plan.

    Use this when the critic finds problems with a relationship construction
    and you need to remove it before proposing a corrected version.

    Args:
        relationship_type: The type of the relationship to remove

    Returns:
        dict: Confirmation of removal
    """
    return {"status": "success", "relationship_construction_removed": relationship_type}


@tool
def approve_proposed_construction_plan() -> Dict[str, Any]:
    """
    Approves the proposed construction plan.

    Only call this after the user explicitly approves the schema.
    This copies the proposed plan to 'approved_construction_plan'.

    Returns:
        dict: Confirmation of approval
    """
    return {"status": "success", "message": "Construction plan approved"}




# Tools for the Schema Proposal Agent (can read and write)
PROPOSAL_AGENT_TOOLS = [
    get_approved_user_goal,
    get_approved_files,
    sample_file,
    search_file,
    propose_node_construction,
    propose_relationship_construction,
    remove_node_construction,
    remove_relationship_construction,
    get_proposed_construction_plan,
]

# Tools for the Schema Critic Agent (read-only, cannot modify plan)
CRITIC_AGENT_TOOLS = [
    get_approved_user_goal,
    get_approved_files,
    sample_file,
    search_file,
    get_proposed_construction_plan,
]

# Tools for the Coordinator Agent (manages user interaction)
COORDINATOR_TOOLS = [
    get_proposed_construction_plan,
    approve_proposed_construction_plan,
]
