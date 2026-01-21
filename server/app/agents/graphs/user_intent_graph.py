import logging
from typing import Annotated, TypedDict, Sequence
from langchain_core.messages import BaseMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from app.core.config import get_settings
from app.agents.prompts.user_intent_prompts import COMPLETE_SYSTEM_PROMPT
from app.agents.tools.user_intent_tools import (
    set_perceived_user_goal,
    approve_perceived_user_goal,
    PERCEIVED_USER_GOAL,
    APPROVED_USER_GOAL
)

# Setup debug logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add console handler if not already present
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class UserIntentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    perceived_user_goal: dict | None
    approved_user_goal: dict | None


def should_continue(state: UserIntentState) -> str:
    """Route based on whether the last message has tool calls."""
    last_message = state["messages"][-1]

    has_tool_calls = hasattr(last_message, "tool_calls") and last_message.tool_calls
    logger.debug(f"[ROUTER] Last message type: {type(last_message).__name__}")
    logger.debug(f"[ROUTER] Has tool_calls: {has_tool_calls}")

    if has_tool_calls:
        logger.debug(f"[ROUTER] Tool calls found: {last_message.tool_calls}")
        return "tool"

    logger.debug("[ROUTER] No tool calls, ending")
    return "end"


def call_llm_node(state: UserIntentState) -> dict:
    """Call the LLM with tools bound."""
    logger.debug("=" * 50)
    logger.debug("[LLM NODE] Entering call_llm_node")
    logger.debug(f"[LLM NODE] Current state keys: {list(state.keys())}")
    logger.debug(f"[LLM NODE] perceived_user_goal: {state.get('perceived_user_goal')}")
    logger.debug(f"[LLM NODE] approved_user_goal: {state.get('approved_user_goal')}")
    logger.debug(f"[LLM NODE] Number of messages: {len(state['messages'])}")

    # Log the last few messages for context
    for i, msg in enumerate(state["messages"][-3:]):
        logger.debug(f"[LLM NODE] Message[-{len(state['messages'][-3:])-i}]: {type(msg).__name__} - {str(msg.content)[:100]}...")

    settings = get_settings()
    model = ChatOpenAI(
        model=settings.openai_model_name,
        api_key=settings.openai_api_key,
        temperature=0,
    )

    # Bind tools to model - gpt-4o handles tool calling naturally
    tools = [set_perceived_user_goal, approve_perceived_user_goal]

    if state.get("approved_user_goal") is not None:
        # Goal already approved - no tools needed
        logger.debug("[LLM NODE] Goal already approved, not binding tools")
        model_with_tools = model
    else:
        # Let gpt-4o decide when to call tools naturally
        model_with_tools = model.bind_tools(tools)

    logger.debug(f"[LLM NODE] Model: {settings.openai_model_name}")
    logger.debug(f"[LLM NODE] Tools bound: {[t.name for t in tools]}")

    prompt = ChatPromptTemplate.from_messages([
        ("system", COMPLETE_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="messages"),
    ])

    chain = prompt | model_with_tools
    response = chain.invoke({"messages": state["messages"]})

    logger.debug(f"[LLM NODE] Response type: {type(response).__name__}")
    logger.debug(f"[LLM NODE] Response content: {str(response.content)[:200]}...")
    logger.debug(f"[LLM NODE] Response has tool_calls: {hasattr(response, 'tool_calls') and bool(response.tool_calls)}")

    if hasattr(response, "tool_calls") and response.tool_calls:
        logger.debug(f"[LLM NODE] Tool calls in response: {response.tool_calls}")

    logger.debug("[LLM NODE] Exiting call_llm_node")
    logger.debug("=" * 50)

    return {"messages": [response]}


def execute_tools_node(state: UserIntentState) -> dict:
    """
    Custom tool node that:
    1. Executes tool calls from the last AI message
    2. Updates state based on which tool was called
    3. Returns both messages and state updates

    This replaces the prebuilt ToolNode to enable state updates.
    """
    logger.debug("=" * 50)
    logger.debug("[TOOL NODE] Entering execute_tools_node")

    last_message = state["messages"][-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.debug("[TOOL NODE] No tool calls found, returning empty")
        return {}

    logger.debug(f"[TOOL NODE] Processing {len(last_message.tool_calls)} tool call(s)")

    # Prepare return values
    tool_messages = []
    state_updates = {}

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]

        logger.debug(f"[TOOL NODE] Executing tool: {tool_name}")
        logger.debug(f"[TOOL NODE] Tool args: {tool_args}")
        logger.debug(f"[TOOL NODE] Tool ID: {tool_id}")

        if tool_name == "set_perceived_user_goal":
            # Extract the goal data from tool arguments
            user_goal_data = {
                "kind_of_graph": tool_args.get("kind_of_graph"),
                "graph_description": tool_args.get("graph_description")
            }

            # Update state
            state_updates["perceived_user_goal"] = user_goal_data

            # Create success message (mimicking course's tool_success)
            result = f"SUCCESS: {PERCEIVED_USER_GOAL} set to {user_goal_data}"
            logger.debug(f"[TOOL NODE] set_perceived_user_goal SUCCESS: {user_goal_data}")

        elif tool_name == "approve_perceived_user_goal":
            # Check if perceived goal exists
            current_perceived = state.get("perceived_user_goal")

            if current_perceived is None:
                # Error case - mimicking course's tool_error
                result = "ERROR: perceived_user_goal not set. Set perceived user goal first, or ask clarifying questions if you are unsure."
                logger.debug("[TOOL NODE] approve_perceived_user_goal FAILED: no perceived goal set")
            else:
                # Approve by copying perceived to approved
                state_updates["approved_user_goal"] = current_perceived
                result = f"SUCCESS: {APPROVED_USER_GOAL} set to {current_perceived}"
                logger.debug(f"[TOOL NODE] approve_perceived_user_goal SUCCESS: {current_perceived}")

        else:
            result = f"ERROR: Unknown tool {tool_name}"
            logger.debug(f"[TOOL NODE] Unknown tool: {tool_name}")

        # Create ToolMessage for the conversation
        tool_messages.append(
            ToolMessage(content=result, tool_call_id=tool_id)
        )

    logger.debug(f"[TOOL NODE] State updates: {state_updates}")
    logger.debug(f"[TOOL NODE] Tool messages: {len(tool_messages)}")
    logger.debug("[TOOL NODE] Exiting execute_tools_node")
    logger.debug("=" * 50)

    # Return both messages and any state updates
    return {
        "messages": tool_messages,
        **state_updates
    }


def create_user_intent_graph():
    """Build and compile the user intent graph."""
    logger.debug("[GRAPH] Creating user intent graph")

    workflow = StateGraph(UserIntentState)

    # Add nodes
    workflow.add_node("agent", call_llm_node)
    workflow.add_node("tool", execute_tools_node)  # Custom tool node instead of ToolNode

    # Set entry point
    workflow.set_entry_point("agent")

    # Add edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tool": "tool", "end": END}
    )
    workflow.add_edge("tool", "agent")  # After tool execution, go back to agent

    logger.debug("[GRAPH] Graph compiled successfully")
    return workflow.compile()


# Create the graph instance
user_intent_graph = create_user_intent_graph()
