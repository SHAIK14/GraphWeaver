

from enum import Enum


class Phase(str, Enum):
    """
    Phases in the BUILD/EXTEND workflow.
    
    BUILD flow: INTENT → FILES → SCHEMA → BUILD → QUERY
    QUERY flow: QUERY only (skip to end)
    EXTEND flow: FILES → SCHEMA → BUILD → QUERY
    
    Inherits from str so it serializes as string in JSON/Redis.
    """
    INTENT = "intent"      # Clarify user's goal
    FILES = "files"        # Select data files
    SCHEMA = "schema"      # Design structure
    BUILD = "build"        # Execute build
    QUERY = "query"        # Q&A mode
    
    def __str__(self) -> str:
        """Return the value when converted to string."""
        return self.value


class FlowType(str, Enum):
    """
    Type of workflow the user is in.
    
    Determines which phases to go through:
    - BUILD: Full workflow (intent → files → schema → build → query)
    - QUERY: Direct to query (existing KB)
    - EXTEND: Add to existing KB (files → schema → build → query)
    """
    BUILD = "build"        # Create new knowledge base
    QUERY = "query"        # Search existing KB
    EXTEND = "extend"      # Add to existing KB
    
    def __str__(self) -> str:
        return self.value


class CheckpointType(str, Enum):
    """
    Types of checkpoints (user approval points).
    
    Each checkpoint pauses execution and waits for user confirmation.
    User can: approve, modify, or cancel.
    """
    GOAL_APPROVAL = "goal_approval"          # After intent agent
    FILES_APPROVAL = "files_approval"        # After file suggestion
    SCHEMA_APPROVAL = "schema_approval"      # After schema design
    BUILD_CONFIRMATION = "build_confirmation"  # Before executing build
    
    def __str__(self) -> str:
        return self.value


class MessageRole(str, Enum):
    """
    Role of message in conversation.
    
    Used for message history tracking.
    Matches OpenAI/LangChain message types.
    """
    USER = "user"              # Human message
    ASSISTANT = "assistant"    # AI response
    SYSTEM = "system"          # System prompt
    TOOL = "tool"              # Tool execution result
    
    def __str__(self) -> str:
        return self.value


# Helper functions for phase transitions

def get_next_phase(current_phase: Phase, flow_type: FlowType) -> Phase | None:
    """
    Get the next phase in the workflow.
    
    Args:
        current_phase: Current phase
        flow_type: Type of workflow
    
    Returns:
        Next phase, or None if at end of flow
    
    Examples:
        >>> get_next_phase(Phase.INTENT, FlowType.BUILD)
        Phase.FILES
        
        >>> get_next_phase(Phase.QUERY, FlowType.QUERY)
        None  # Already at end
    """
    if flow_type == FlowType.BUILD:
        # BUILD: INTENT → FILES → SCHEMA → BUILD → QUERY
        transitions = {
            Phase.INTENT: Phase.FILES,
            Phase.FILES: Phase.SCHEMA,
            Phase.SCHEMA: Phase.BUILD,
            Phase.BUILD: Phase.QUERY,
            Phase.QUERY: None  # End of flow
        }
    elif flow_type == FlowType.EXTEND:
        # EXTEND: FILES → SCHEMA → BUILD → QUERY (skip INTENT)
        transitions = {
            Phase.FILES: Phase.SCHEMA,
            Phase.SCHEMA: Phase.BUILD,
            Phase.BUILD: Phase.QUERY,
            Phase.QUERY: None
        }
    else:  # FlowType.QUERY
        # QUERY: Stay in QUERY phase
        transitions = {
            Phase.QUERY: None  # Already querying, no transition
        }
    
    return transitions.get(current_phase)


def get_initial_phase(flow_type: FlowType) -> Phase:
    """
    Get the starting phase for a flow type.
    
    Args:
        flow_type: Type of workflow
    
    Returns:
        Initial phase for this flow
    
    Examples:
        >>> get_initial_phase(FlowType.BUILD)
        Phase.INTENT
        
        >>> get_initial_phase(FlowType.QUERY)
        Phase.QUERY
    """
    return {
        FlowType.BUILD: Phase.INTENT,
        FlowType.QUERY: Phase.QUERY,
        FlowType.EXTEND: Phase.FILES  # Skip INTENT for extend
    }[flow_type]


def get_checkpoint_for_phase(phase: Phase) -> CheckpointType | None:
    """
    Get the checkpoint type for a phase (if any).
    
    Not all phases have checkpoints.
    BUILD phase doesn't pause (it just executes).
    
    Args:
        phase: Current phase
    
    Returns:
        Checkpoint type, or None if no checkpoint
    
    Examples:
        >>> get_checkpoint_for_phase(Phase.INTENT)
        CheckpointType.GOAL_APPROVAL
        
        >>> get_checkpoint_for_phase(Phase.BUILD)
        None  # No checkpoint, just executes
    """
    return {
        Phase.INTENT: CheckpointType.GOAL_APPROVAL,
        Phase.FILES: CheckpointType.FILES_APPROVAL,
        Phase.SCHEMA: CheckpointType.SCHEMA_APPROVAL,
        Phase.BUILD: None,  # No checkpoint, executes immediately
        Phase.QUERY: None   # No checkpoint, continuous Q&A
    }.get(phase)
