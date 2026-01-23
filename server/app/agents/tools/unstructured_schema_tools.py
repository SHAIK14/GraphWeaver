"""
Tools for Unstructured Schema Proposal Agents.

These tools support:
1. NER Agent - Tools for proposing and managing entity types
2. Fact Extraction Agent - Tools for proposing relationship triples

Key difference from structured schema tools:
- Structured tools work with CSV columns → direct mapping
- Unstructured tools work with text → need NER + fact extraction
"""

from typing import Any
from langchain_core.tools import tool

# =============================================================================
# SHARED CONTEXT TOOLS
# =============================================================================

@tool
def get_approved_user_goal(state: dict) -> str:
    """
    Retrieve the user's approved goal for the knowledge graph.

    Why we need this:
    - The goal guides what entities and facts are relevant
    - Example: If goal is "track supplier quality", we focus on
      Reviewer, Product, QualityIssue entities rather than generic ones

    Returns:
        str: The approved user goal, or empty string if not set
    """
    return state.get("approved_user_goal", "")


@tool
def get_approved_files(state: dict) -> list[str]:
    """
    Retrieve the list of approved files for processing.

    Why we need this:
    - Agent needs to know which files to sample/analyze
    - For unstructured data, these are markdown/text files

    Returns:
        list[str]: List of approved file paths
    """
    return state.get("approved_files", [])


@tool
def sample_file(state: dict, file_path: str, num_lines: int = 50) -> str:
    """
    Read a sample of lines from a file to understand its content.

    Args:
        state: Current graph state
        file_path: Path to the file to sample
        num_lines: Number of lines to read (default 50)

    Why we need this:
    - Agent can't read entire files (too much context)
    - Sampling gives a representative view of content
    - For reviews, 50 lines might show 2-3 complete reviews

    Returns:
        str: Sample content from the file
    """
    try:
        with open(file_path, 'r') as f:
            lines = []
            for i, line in enumerate(f):
                if i >= num_lines:
                    break
                lines.append(line)
            return ''.join(lines)
    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


# =============================================================================
# NER AGENT TOOLS - Entity Type Management
# =============================================================================

@tool
def get_well_known_types(state: dict) -> list[str]:
    """
    Get existing node labels from the approved construction plan.

    Why we need this:
    - Bridges structured schema (Lesson 6) with unstructured (Lesson 7)
    - If "Supplier" already exists, NER should use it, not create "Vendor"
    - Prevents duplicate entity types with different names

    Example:
        If construction_plan has nodes: [Supplier, Part, Factory]
        NER agent should reuse these before proposing new ones

    Returns:
        list[str]: List of existing node labels (entity types)
    """
    construction_plan = state.get("approved_construction_plan", {})
    nodes = construction_plan.get("nodes", [])
    return [node.get("label", "") for node in nodes if node.get("label")]


@tool
def set_proposed_entities(state: dict, entities: list[dict]) -> str:
    """
    Set the complete list of proposed entity types.

    Args:
        state: Current graph state
        entities: List of entity dicts, each with:
            - name: Entity type name (e.g., "Reviewer", "QualityIssue")
            - source: "well_known" or "discovered"
            - description: Why this entity is relevant

    Why we need this:
    - NER agent proposes entity TYPES, not instances
    - "Reviewer" is a type; "electrical_engineer_patel" is an instance
    - This stores the proposed schema for user approval

    Example input:
        [
            {"name": "Reviewer", "source": "discovered",
             "description": "People who write product reviews"},
            {"name": "Product", "source": "well_known",
             "description": "Items being reviewed (maps to Part)"}
        ]

    Returns:
        str: Confirmation message
    """
    state["proposed_entities"] = entities
    return f"Set {len(entities)} proposed entity types"


@tool
def get_proposed_entities(state: dict) -> list[dict]:
    """
    Retrieve the current list of proposed entity types.

    Why we need this:
    - Agent needs to review what's been proposed
    - Present to user for approval
    - Check before adding duplicates

    Returns:
        list[dict]: List of proposed entity type definitions
    """
    return state.get("proposed_entities", [])


@tool
def approve_proposed_entities(state: dict) -> str:
    """
    Finalize the proposed entities as approved.

    Why we need this:
    - Moves entities from "proposed" to "approved" status
    - Approved entities can be used by Fact Extraction agent
    - Creates audit trail of what was approved

    Returns:
        str: Confirmation with count of approved entities
    """
    proposed = state.get("proposed_entities", [])
    state["approved_entities"] = proposed
    return f"Approved {len(proposed)} entity types"


# =============================================================================
# FACT EXTRACTION AGENT TOOLS - Relationship Triple Management
# =============================================================================

@tool
def get_approved_entities(state: dict) -> list[dict]:
    """
    Get the approved entity types for fact extraction.

    Why we need this:
    - Fact agent can ONLY use approved entities as subjects/objects
    - Ensures facts reference valid entity types
    - Example: Can propose (Reviewer, wrote, Review) only if
      Reviewer and Review are approved entities

    Returns:
        list[dict]: List of approved entity definitions
    """
    return state.get("approved_entities", [])


@tool
def add_proposed_fact(
    state: dict,
    subject_type: str,
    predicate: str,
    object_type: str,
    description: str = ""
) -> str:
    """
    Add a single proposed fact type (relationship triple).

    Args:
        state: Current graph state
        subject_type: Entity type for subject (must be approved)
        predicate: Relationship verb (e.g., "wrote", "mentions", "has")
        object_type: Entity type for object (must be approved)
        description: Optional explanation of this relationship

    Why we need this:
    - Facts are triplets: (Subject, Predicate, Object)
    - This is NOT a specific fact like "Patel wrote Review1"
    - This is a FACT TYPE like "Reviewer wrote Review"
    - Guides the extraction agent on what relationships to find

    Example:
        add_proposed_fact(
            subject_type="Reviewer",
            predicate="rates",
            object_type="Product",
            description="Reviewer gives a rating to a product"
        )

    Returns:
        str: Confirmation or error message
    """
    # Validate subject and object are approved entities
    approved = state.get("approved_entities", [])
    approved_names = [e.get("name", "") for e in approved]

    if subject_type not in approved_names:
        return f"Error: '{subject_type}' is not an approved entity type"
    if object_type not in approved_names:
        return f"Error: '{object_type}' is not an approved entity type"

    # Initialize facts list if needed
    if "proposed_facts" not in state:
        state["proposed_facts"] = []

    fact = {
        "subject_type": subject_type,
        "predicate": predicate,
        "object_type": object_type,
        "description": description
    }

    state["proposed_facts"].append(fact)
    return f"Added fact type: ({subject_type})-[{predicate}]->({object_type})"


@tool
def get_proposed_facts(state: dict) -> list[dict]:
    """
    Retrieve all proposed fact types.

    Why we need this:
    - Review what relationships have been proposed
    - Present to user for approval
    - Check for duplicates before adding

    Returns:
        list[dict]: List of proposed fact type definitions
    """
    return state.get("proposed_facts", [])


@tool
def approve_proposed_facts(state: dict) -> str:
    """
    Finalize the proposed facts as approved.

    Why we need this:
    - Moves facts from "proposed" to "approved" status
    - Approved facts define the relationship schema
    - These will guide actual extraction from text

    Returns:
        str: Confirmation with count of approved facts
    """
    proposed = state.get("proposed_facts", [])
    state["approved_facts"] = proposed
    return f"Approved {len(proposed)} fact types"


# =============================================================================
# TOOL COLLECTIONS FOR AGENTS
# =============================================================================

# Tools available to NER Agent
NER_AGENT_TOOLS = [
    get_approved_user_goal,
    get_approved_files,
    sample_file,
    get_well_known_types,
    set_proposed_entities,
    get_proposed_entities,
    approve_proposed_entities,
]

# Tools available to Fact Extraction Agent
FACT_AGENT_TOOLS = [
    get_approved_user_goal,
    get_approved_files,
    sample_file,
    get_approved_entities,
    add_proposed_fact,
    get_proposed_facts,
    approve_proposed_facts,
]
