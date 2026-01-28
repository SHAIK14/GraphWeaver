"""
Schema Proposal Graph - Multi-Agent Workflow with Critic Pattern

This graph implements a refinement loop where:
1. Schema Proposal Agent proposes construction rules
2. Schema Critic Agent reviews and provides feedback
3. If feedback says "valid" -> exit loop
4. If feedback says "retry" -> loop back to proposal agent with feedback

The workflow uses LangGraph's conditional edges to implement the loop.
"""

import logging
from typing import Annotated, TypedDict, Sequence, List
from langchain_core.messages import BaseMessage, ToolMessage, AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from app.core.config import get_settings
from app.agents.prompts.schema_proposal_prompts import (
    PROPOSAL_AGENT_INSTRUCTION,
    CRITIC_AGENT_INSTRUCTION,
)
from app.agents.tools.schema_proposal_tools import (
    # Context tools
    get_approved_user_goal,
    get_approved_files,
    # File inspection tools
    sample_file,
    search_file,
    # Construction tools
    propose_node_construction,
    propose_relationship_construction,
    remove_node_construction,
    remove_relationship_construction,
    get_proposed_construction_plan,
    approve_proposed_construction_plan,
    # Constants
    APPROVED_USER_GOAL,
    APPROVED_FILES,
    PROPOSED_CONSTRUCTION_PLAN,
    APPROVED_CONSTRUCTION_PLAN,
    FEEDBACK,
    NODE_CONSTRUCTION,
    RELATIONSHIP_CONSTRUCTION,
    # Tool collections
    PROPOSAL_AGENT_TOOLS,
    CRITIC_AGENT_TOOLS,
)

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)




class SchemaProposalState(TypedDict):
    """
    State for the Schema Proposal workflow.

    Attributes:
        messages: Conversation history (accumulates via add_messages)
        approved_user_goal: From User Intent Agent (input)
        approved_files: From File Suggestion Agent (input)
        proposed_construction_plan: Current schema proposal (dict of rules)
        approved_construction_plan: Final approved schema (output)
        feedback: Critic's feedback (empty string or bullet points)
        current_agent: Which agent is currently active
        iteration_count: How many times we've looped
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    approved_user_goal: dict | None
    approved_files: List[str] | None
    proposed_construction_plan: dict | None
    approved_construction_plan: dict | None
    feedback: str
    current_agent: str
    iteration_count: int




def should_continue_proposal(state: SchemaProposalState) -> str:
    """
    Route after the proposal agent runs.

    If the agent made tool calls -> go to tool node
    Otherwise -> go to critic agent
    """
    last_message = state["messages"][-1]
    has_tool_calls = hasattr(last_message, "tool_calls") and last_message.tool_calls

    logger.debug(f"[PROPOSAL ROUTER] Has tool calls: {has_tool_calls}")

    if has_tool_calls:
        return "proposal_tool"
    else:
        # No more tool calls, time for critic to review
        return "critic"


def should_continue_critic(state: SchemaProposalState) -> str:
    """
    Route after the critic agent runs.

    If the agent made tool calls -> go to critic's tool node
    Otherwise -> check the feedback
    """
    last_message = state["messages"][-1]
    has_tool_calls = hasattr(last_message, "tool_calls") and last_message.tool_calls

    logger.debug(f"[CRITIC ROUTER] Has tool calls: {has_tool_calls}")

    if has_tool_calls:
        return "critic_tool"
    else:
        # No more tool calls, check the feedback
        return "check_feedback"


def check_feedback_and_route(state: SchemaProposalState) -> str:
    """
    Check the critic's feedback and decide whether to loop or exit.

    If feedback contains "valid" -> end the loop
    If feedback contains "retry" or anything else -> loop back to proposal
    Also check iteration limit to prevent infinite loops.
    """
    feedback = state.get("feedback", "")
    iteration_count = state.get("iteration_count", 0)
    max_iterations = 3  # Prevent infinite loops

    logger.debug(f"[FEEDBACK CHECK] Feedback: {feedback[:100]}...")
    logger.debug(f"[FEEDBACK CHECK] Iteration: {iteration_count}/{max_iterations}")

    # Check iteration limit
    if iteration_count >= max_iterations:
        logger.debug("[FEEDBACK CHECK] Max iterations reached, exiting")
        return "end"

    # Only loop back if critic explicitly says "retry" — otherwise treat as valid.
    # This prevents wasted iterations when critic doesn't follow the exact one-word protocol.
    if "retry" in feedback.lower():
        logger.debug("[FEEDBACK CHECK] Critic requested retry, looping back")
        return "proposal"
    else:
        logger.debug("[FEEDBACK CHECK] No retry requested, exiting loop")
        return "end"




def proposal_agent_node(state: SchemaProposalState) -> dict:
    """
    The Schema Proposal Agent.

    This agent:
    1. Reads the user goal and approved files
    2. Analyzes each file to determine node vs relationship
    3. Proposes construction rules
    4. Considers feedback if this is a retry
    """
    logger.debug("=" * 60)
    logger.debug("[PROPOSAL AGENT] Entering proposal_agent_node")
    logger.debug(f"[PROPOSAL AGENT] Iteration: {state.get('iteration_count', 0)}")
    logger.debug(f"[PROPOSAL AGENT] Feedback: {state.get('feedback', 'None')[:100]}")

    settings = get_settings()
    model = ChatOpenAI(
        model=settings.openai_model_name,
        api_key=settings.openai_api_key,
        temperature=0,
    )

    # Bind proposal tools
    model_with_tools = model.bind_tools(PROPOSAL_AGENT_TOOLS)

    # Build prompt with feedback placeholder
    feedback = state.get("feedback", "")
    instruction_with_feedback = PROPOSAL_AGENT_INSTRUCTION.format(feedback=feedback)

    prompt = ChatPromptTemplate.from_messages([
        ("system", instruction_with_feedback),
        MessagesPlaceholder(variable_name="messages"),
    ])

    chain = prompt | model_with_tools
    response = chain.invoke({"messages": state["messages"]})

    logger.debug(f"[PROPOSAL AGENT] Response: {str(response.content)[:200]}...")
    logger.debug(f"[PROPOSAL AGENT] Has tool calls: {hasattr(response, 'tool_calls') and bool(response.tool_calls)}")

    return {
        "messages": [response],
        "current_agent": "proposal"
    }


def critic_agent_node(state: SchemaProposalState) -> dict:
    """
    The Schema Critic Agent.

    This agent:
    1. Reviews the proposed construction plan
    2. Validates uniqueness of identifiers
    3. Checks for missing relationships
    4. Responds with either "valid" or "retry" + feedback
    """
    logger.debug("=" * 60)
    logger.debug("[CRITIC AGENT] Entering critic_agent_node")

    settings = get_settings()
    model = ChatOpenAI(
        model=settings.openai_model_name,
        api_key=settings.openai_api_key,
        temperature=0,
    )

    # Bind critic tools (read-only)
    model_with_tools = model.bind_tools(CRITIC_AGENT_TOOLS)

    prompt = ChatPromptTemplate.from_messages([
        ("system", CRITIC_AGENT_INSTRUCTION),
        MessagesPlaceholder(variable_name="messages"),
    ])

    chain = prompt | model_with_tools
    response = chain.invoke({"messages": state["messages"]})

    logger.debug(f"[CRITIC AGENT] Response: {str(response.content)[:200]}...")

    return {
        "messages": [response],
        "current_agent": "critic"
    }


def extract_feedback_node(state: SchemaProposalState) -> dict:
    """
    Extract the critic's feedback from the last message.

    The critic should respond with either:
    - "valid" if the schema is good
    - "retry" followed by bullet points of issues

    This node extracts that feedback and increments the iteration counter.
    """
    logger.debug("[EXTRACT FEEDBACK] Processing critic's response")

    # Find the last AI message (the critic's response)
    feedback = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            feedback = msg.content
            break

    logger.debug(f"[EXTRACT FEEDBACK] Extracted: {feedback[:100]}...")

    return {
        "feedback": feedback,
        "iteration_count": state.get("iteration_count", 0) + 1
    }


# =============================================================================
# TOOL EXECUTION NODES
# =============================================================================

def execute_proposal_tools(state: SchemaProposalState) -> dict:
    """
    Execute tools called by the Proposal Agent.

    Handles:
    - get_approved_user_goal: Returns goal from state
    - get_approved_files: Returns files from state
    - sample_file: Reads file content
    - search_file: Searches file for patterns
    - propose_node_construction: Adds node rule to plan
    - propose_relationship_construction: Adds relationship rule to plan
    - remove_node_construction: Removes node rule from plan
    - remove_relationship_construction: Removes relationship rule from plan
    - get_proposed_construction_plan: Returns current plan
    """
    logger.debug("[PROPOSAL TOOLS] Executing proposal agent tools")

    last_message = state["messages"][-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {}

    tool_messages = []
    state_updates = {}

    # Get current construction plan
    current_plan = state.get("proposed_construction_plan") or {}

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]

        logger.debug(f"[PROPOSAL TOOLS] Executing: {tool_name}")
        logger.debug(f"[PROPOSAL TOOLS] Args: {tool_args}")

        result = None

        # Context retrieval tools
        if tool_name == "get_approved_user_goal":
            goal = state.get("approved_user_goal")
            if goal:
                result = {"status": "success", APPROVED_USER_GOAL: goal}
            else:
                result = {"status": "error", "error_message": "No approved user goal found"}

        elif tool_name == "get_approved_files":
            files = state.get("approved_files")
            if files:
                result = {"status": "success", APPROVED_FILES: files}
            else:
                result = {"status": "error", "error_message": "No approved files found"}

        # File inspection tools
        elif tool_name == "sample_file":
            result = sample_file.invoke(tool_args)

        elif tool_name == "search_file":
            result = search_file.invoke(tool_args)

        # Construction proposal tools
        elif tool_name == "propose_node_construction":
            result = propose_node_construction.invoke(tool_args)
            if result.get("status") == "success" and NODE_CONSTRUCTION in result:
                label = result.get("label")
                current_plan[label] = result[NODE_CONSTRUCTION]
                state_updates["proposed_construction_plan"] = current_plan
                logger.debug(f"[PROPOSAL TOOLS] Added node construction: {label}")

        elif tool_name == "propose_relationship_construction":
            result = propose_relationship_construction.invoke(tool_args)
            if result.get("status") == "success" and RELATIONSHIP_CONSTRUCTION in result:
                rel_type = result.get("relationship_type")
                current_plan[rel_type] = result[RELATIONSHIP_CONSTRUCTION]
                state_updates["proposed_construction_plan"] = current_plan
                logger.debug(f"[PROPOSAL TOOLS] Added relationship construction: {rel_type}")

        elif tool_name == "remove_node_construction":
            label = tool_args.get("node_label")
            if label in current_plan:
                del current_plan[label]
                state_updates["proposed_construction_plan"] = current_plan
            result = {"status": "success", "node_construction_removed": label}

        elif tool_name == "remove_relationship_construction":
            rel_type = tool_args.get("relationship_type")
            if rel_type in current_plan:
                del current_plan[rel_type]
                state_updates["proposed_construction_plan"] = current_plan
            result = {"status": "success", "relationship_construction_removed": rel_type}

        elif tool_name == "get_proposed_construction_plan":
            result = {
                "status": "success",
                PROPOSED_CONSTRUCTION_PLAN: current_plan
            }

        else:
            result = {"status": "error", "error_message": f"Unknown tool: {tool_name}"}

        tool_messages.append(
            ToolMessage(content=str(result), tool_call_id=tool_id)
        )

    logger.debug(f"[PROPOSAL TOOLS] State updates: {list(state_updates.keys())}")

    return {
        "messages": tool_messages,
        **state_updates
    }


def execute_critic_tools(state: SchemaProposalState) -> dict:
    """
    Execute tools called by the Critic Agent.

    The critic has read-only tools - it cannot modify the construction plan.
    """
    logger.debug("[CRITIC TOOLS] Executing critic agent tools")

    last_message = state["messages"][-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {}

    tool_messages = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]

        logger.debug(f"[CRITIC TOOLS] Executing: {tool_name}")

        result = None

        if tool_name == "get_approved_user_goal":
            goal = state.get("approved_user_goal")
            if goal:
                result = {"status": "success", APPROVED_USER_GOAL: goal}
            else:
                result = {"status": "error", "error_message": "No approved user goal found"}

        elif tool_name == "get_approved_files":
            files = state.get("approved_files")
            if files:
                result = {"status": "success", APPROVED_FILES: files}
            else:
                result = {"status": "error", "error_message": "No approved files found"}

        elif tool_name == "sample_file":
            result = sample_file.invoke(tool_args)

        elif tool_name == "search_file":
            result = search_file.invoke(tool_args)

        elif tool_name == "get_proposed_construction_plan":
            current_plan = state.get("proposed_construction_plan") or {}
            result = {
                "status": "success",
                PROPOSED_CONSTRUCTION_PLAN: current_plan
            }

        else:
            result = {"status": "error", "error_message": f"Unknown tool: {tool_name}"}

        tool_messages.append(
            ToolMessage(content=str(result), tool_call_id=tool_id)
        )

    return {"messages": tool_messages}


# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================

def create_schema_proposal_graph():
    """
    Build and compile the Schema Proposal graph with critic loop.

    Graph structure:
                          ┌─────────────┐
                          │   START     │
                          └──────┬──────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
             ┌──────│   proposal_agent       │◄─────────────┐
             │      └────────────┬───────────┘              │
             │                   │                          │
             │         has tool calls?                      │
             │           │              │                   │
             │          YES            NO                   │
             │           │              │                   │
             │           ▼              ▼                   │
             │   ┌──────────────┐  ┌──────────────┐         │
             │   │proposal_tool │  │ critic_agent │         │
             │   └──────┬───────┘  └──────┬───────┘         │
             │          │                 │                 │
             │          └────►────────────┤                 │
             │                            │                 │
             │                  has tool calls?             │
             │                    │              │          │
             │                   YES            NO          │
             │                    │              │          │
             │                    ▼              ▼          │
             │            ┌──────────────┐ ┌───────────────┐│
             │            │ critic_tool  │ │extract_feedbk ││
             │            └──────┬───────┘ └───────┬───────┘│
             │                   │                 │        │
             │                   └────►───────────►│        │
             │                                     │        │
             │                            feedback="valid"? │
             │                              │           │   │
             │                             YES         NO   │
             │                              │           │   │
             │                              ▼           └───┘
             │                         ┌─────────┐
             │                         │   END   │
             │                         └─────────┘
             │
             └──────────────────────────────────────────────┘
    """
    logger.debug("[GRAPH] Creating schema proposal graph")

    workflow = StateGraph(SchemaProposalState)

    # Add all nodes
    workflow.add_node("proposal", proposal_agent_node)
    workflow.add_node("proposal_tool", execute_proposal_tools)
    workflow.add_node("critic", critic_agent_node)
    workflow.add_node("critic_tool", execute_critic_tools)
    workflow.add_node("extract_feedback", extract_feedback_node)

    # Set entry point
    workflow.set_entry_point("proposal")

    # Proposal agent routing
    workflow.add_conditional_edges(
        "proposal",
        should_continue_proposal,
        {
            "proposal_tool": "proposal_tool",
            "critic": "critic"
        }
    )

    # After proposal tools, go back to proposal agent
    workflow.add_edge("proposal_tool", "proposal")

    # Critic agent routing
    workflow.add_conditional_edges(
        "critic",
        should_continue_critic,
        {
            "critic_tool": "critic_tool",
            "check_feedback": "extract_feedback"
        }
    )

    # After critic tools, go back to critic agent
    workflow.add_edge("critic_tool", "critic")

    # After extracting feedback, decide to loop or end
    workflow.add_conditional_edges(
        "extract_feedback",
        check_feedback_and_route,
        {
            "proposal": "proposal",  # Loop back with feedback
            "end": END
        }
    )

    logger.debug("[GRAPH] Schema proposal graph compiled successfully")
    return workflow.compile()


# Create the graph instance
schema_proposal_graph = create_schema_proposal_graph()
