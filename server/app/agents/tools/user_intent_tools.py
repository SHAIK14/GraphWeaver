from langchain_core.tools import tool

PERCEIVED_USER_GOAL = "perceived_user_goal"
APPROVED_USER_GOAL = "approved_user_goal"


@tool
def set_perceived_user_goal(kind_of_graph: str, graph_description: str) -> str:
    """Sets the perceived user's goal, including the kind of graph and its description.

    This tool should be called when the agent believes it understands what the user wants.

    Args:
        kind_of_graph: 2-3 word definition of the kind of graph (e.g., "BOM graph", "social network")
        graph_description: A single paragraph describing the graph's purpose and intent

    Returns:
        Confirmation message
    """
    return f"Perceived goal set: {kind_of_graph} - {graph_description}"


@tool
def approve_perceived_user_goal() -> str:
    """Approves the perceived user goal and promotes it to the official approved goal.

    This tool should ONLY be called after the user explicitly approves the goal.

    Returns:
        Confirmation message
    """
    return "Goal has been approved and saved"
