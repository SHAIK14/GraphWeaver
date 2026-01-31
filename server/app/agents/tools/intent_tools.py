from langchain_core.tools import tool


@tool
def set_perceived_goal(category: str, description: str) -> str:
    """
    Record the perceived user goal.
    
    Call this when you understand what the user wants to organize.
    
    Args:
        category: Short 2-3 word label (e.g., "Supply Chain", "Team Network")
        description: What they want to accomplish (e.g., "Track supplier relationships")
    
    Returns:
        Confirmation message
    """
    return f"✓ Got it:{category}:{description}"


@tool
def approve_goal() ->str:
    """
    Approve the goal and move to next phase.
    
    ONLY call this after user explicitly confirms the goal is correct.
    This transitions to file selection.
    
    Returns:
        Confirmation message
    """
    return "✓ Goal approved. Moving to file selection."