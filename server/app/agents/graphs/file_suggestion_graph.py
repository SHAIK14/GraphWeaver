import logging
from typing import Annotated, TypedDict, Sequence, List
from langchain_core.messages import BaseMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from app.core.config import get_settings
from app.agents.prompts.file_suggestion_prompts import COMPLETE_SYSTEM_PROMPT
from app.agents.tools.file_suggestion_tools import (
    get_approved_user_goal,
    list_available_files,
    sample_file,
    set_suggested_files,
    get_suggested_files,
    ALL_AVAILABLE_FILES,
)

# Setup debug logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class FileSuggestionState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    # Input from previous agent (User Intent Agent)
    approved_user_goal: dict | None
    # This agent's state fields
    all_available_files: List[str] | None
    suggested_files: List[str] | None
    approved_files: List[str] | None


def should_continue(state: FileSuggestionState) -> str:
    """Route based on whether the last message has tool calls."""
    last_message = state["messages"][-1]

    has_tool_calls = hasattr(last_message, "tool_calls") and last_message.tool_calls
    logger.debug(f"[ROUTER] Last message type: {type(last_message).__name__}")
    logger.debug(f"[ROUTER] Has tool_calls: {has_tool_calls}")

    if has_tool_calls:
        logger.debug(f"[ROUTER] Tool calls found: {[tc['name'] for tc in last_message.tool_calls]}")
        return "tool"

    logger.debug("[ROUTER] No tool calls, ending")
    return "end"


def call_llm_node(state: FileSuggestionState) -> dict:
    """Call the LLM with tools bound."""
    logger.debug("=" * 50)
    logger.debug("[LLM NODE] Entering call_llm_node")
    logger.debug(f"[LLM NODE] approved_user_goal: {state.get('approved_user_goal')}")
    logger.debug(f"[LLM NODE] all_available_files: {state.get('all_available_files')}")
    logger.debug(f"[LLM NODE] suggested_files: {state.get('suggested_files')}")
    logger.debug(f"[LLM NODE] approved_files: {state.get('approved_files')}")
    logger.debug(f"[LLM NODE] Number of messages: {len(state['messages'])}")

    settings = get_settings()
    model = ChatOpenAI(
        model=settings.openai_model_name,
        api_key=settings.openai_api_key,
        temperature=0,
    )

    # Agent tools: produce data only, no approve actions
    tools = [
        get_approved_user_goal,
        list_available_files,
        sample_file,
        set_suggested_files,
        get_suggested_files,
    ]

    # If files already suggested, no tools needed (agent done)
    if state.get("suggested_files") is not None:
        logger.debug("[LLM NODE] Files already suggested, not binding tools")
        model_with_tools = model
    else:
        model_with_tools = model.bind_tools(tools, tool_choice="required")

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
        logger.debug(f"[LLM NODE] Tool calls: {[tc['name'] for tc in response.tool_calls]}")

    logger.debug("[LLM NODE] Exiting call_llm_node")
    logger.debug("=" * 50)

    return {"messages": [response]}


def execute_tools_node(state: FileSuggestionState) -> dict:
    """
    Custom tool node that:
    1. Executes tool calls from the last AI message
    2. Updates state based on which tool was called
    3. Returns both messages and state updates
    """
    logger.debug("=" * 50)
    logger.debug("[TOOL NODE] Entering execute_tools_node")

    last_message = state["messages"][-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.debug("[TOOL NODE] No tool calls found, returning empty")
        return {}

    logger.debug(f"[TOOL NODE] Processing {len(last_message.tool_calls)} tool call(s)")

    tool_messages = []
    state_updates = {}

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]

        logger.debug(f"[TOOL NODE] Executing tool: {tool_name}")
        logger.debug(f"[TOOL NODE] Tool args: {tool_args}")

        # Handle each tool
        if tool_name == "get_approved_user_goal":
            # Read from state
            goal = state.get("approved_user_goal")
            if goal is None:
                result = "ERROR: No approved user goal found. Cannot proceed without a goal."
            else:
                result = f"SUCCESS: approved_user_goal = {goal}"
            logger.debug(f"[TOOL NODE] get_approved_user_goal: {goal}")

        elif tool_name == "list_available_files":
            # Actually call the tool to get file list
            tool_result = list_available_files.invoke({})
            if tool_result.get("status") == "success":
                files = tool_result.get(ALL_AVAILABLE_FILES, [])
                state_updates["all_available_files"] = files
                result = f"SUCCESS: Found {len(files)} files: {files}"
            else:
                result = f"ERROR: {tool_result.get('error_message', 'Unknown error')}"
            logger.debug(f"[TOOL NODE] list_available_files result: {result}")

        elif tool_name == "sample_file":
            # Actually call the tool to sample file
            file_path = tool_args.get("file_path")
            tool_result = sample_file.invoke({"file_path": file_path})
            if tool_result.get("status") == "success":
                content = tool_result.get("content", "")
                result = f"SUCCESS: File content:\n{content}"
            else:
                result = f"ERROR: {tool_result.get('error_message', 'Unknown error')}"
            logger.debug(f"[TOOL NODE] sample_file for {file_path}")

        elif tool_name == "set_suggested_files":
            # Extract file list and save to state
            file_list = tool_args.get("file_list", [])
            state_updates["suggested_files"] = file_list
            result = f"SUCCESS: suggested_files set to {file_list}"
            logger.debug(f"[TOOL NODE] set_suggested_files: {file_list}")

        elif tool_name == "get_suggested_files":
            # Read from state
            suggested = state.get("suggested_files")
            if suggested is None:
                result = "ERROR: No suggested files set yet. Use set_suggested_files first."
            else:
                result = f"SUCCESS: suggested_files = {suggested}"
            logger.debug(f"[TOOL NODE] get_suggested_files: {suggested}")

        else:
            result = f"ERROR: Unknown tool {tool_name}"
            logger.debug(f"[TOOL NODE] Unknown tool: {tool_name}")

        tool_messages.append(
            ToolMessage(content=result, tool_call_id=tool_id)
        )

    logger.debug(f"[TOOL NODE] State updates: {state_updates}")
    logger.debug(f"[TOOL NODE] Tool messages: {len(tool_messages)}")
    logger.debug("[TOOL NODE] Exiting execute_tools_node")
    logger.debug("=" * 50)

    return {
        "messages": tool_messages,
        **state_updates
    }


def create_file_suggestion_graph():
    """Build and compile the file suggestion graph."""
    logger.debug("[GRAPH] Creating file suggestion graph")

    workflow = StateGraph(FileSuggestionState)

    # Add nodes
    workflow.add_node("agent", call_llm_node)
    workflow.add_node("tool", execute_tools_node)

    # Set entry point
    workflow.set_entry_point("agent")

    # Add edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tool": "tool", "end": END}
    )
    workflow.add_edge("tool", "agent")

    logger.debug("[GRAPH] Graph compiled successfully")
    return workflow.compile()


# Create the graph instance
file_suggestion_graph = create_file_suggestion_graph()
