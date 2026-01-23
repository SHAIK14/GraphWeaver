"""
LangGraph Workflow for Unstructured Schema Proposal.

This graph implements a TWO-STAGE workflow:
1. NER Agent → proposes entity types from text
2. Fact Agent → proposes relationship triples using approved entities

Unlike Lesson 6's critic loop, this is a SEQUENTIAL pipeline:
NER Agent → User Approval → Fact Agent → User Approval

The workflow pauses for user approval between stages.
"""

from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from app.core.config import get_settings
from app.agents.prompts.unstructured_schema_prompts import (
    NER_AGENT_INSTRUCTION,
    FACT_AGENT_INSTRUCTION,
)
from app.agents.tools.unstructured_schema_tools import (
    NER_AGENT_TOOLS,
    FACT_AGENT_TOOLS,
)


# =============================================================================
# STATE DEFINITION
# =============================================================================

class UnstructuredSchemaState(TypedDict):
    """
    State for the unstructured schema proposal workflow.

    Key fields:
    - messages: Conversation history (auto-appended)
    - stage: Current stage ("ner" or "fact")
    - approved_user_goal: User's goal for the graph
    - approved_files: Files to analyze
    - approved_construction_plan: From Lesson 6 (for well-known types)
    - proposed_entities: NER agent's proposals
    - approved_entities: User-approved entity types
    - proposed_facts: Fact agent's proposals
    - approved_facts: User-approved fact types
    """
    messages: Annotated[list, add_messages]
    stage: str  # "ner" or "fact"
    approved_user_goal: str
    approved_files: list[str]
    approved_construction_plan: dict
    proposed_entities: list[dict]
    approved_entities: list[dict]
    proposed_facts: list[dict]
    approved_facts: list[dict]


# =============================================================================
# NER AGENT NODE
# =============================================================================

def ner_agent_node(state: UnstructuredSchemaState) -> dict:
    """
    NER Agent: Identifies entity types from unstructured text.

    This agent:
    1. Reads sample files
    2. Identifies well-known entities (from existing schema)
    3. Discovers new entity types
    4. Proposes entity types for user approval
    """
    settings = get_settings()
    model = ChatOpenAI(
        model=settings.openai_model_name,
        api_key=settings.openai_api_key,
        temperature=0,
    )
    model_with_tools = model.bind_tools(NER_AGENT_TOOLS)

    # Build messages with system instruction
    messages = [
        {"role": "system", "content": NER_AGENT_INSTRUCTION}
    ] + state["messages"]

    response = model_with_tools.invoke(messages)
    return {"messages": [response]}


def execute_ner_tools(state: UnstructuredSchemaState) -> dict:
    """
    Execute tool calls from NER agent and update state.

    Handles tools INLINE to properly capture state updates.
    """
    last_message = state["messages"][-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"messages": []}

    tool_messages = []
    state_updates = {}

    # Track proposed entities across multiple tool calls
    current_proposed_entities = list(state.get("proposed_entities") or [])

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]

        result = None

        # Handle each tool inline (like schema_proposal_graph does)
        if tool_name == "get_approved_user_goal":
            goal = state.get("approved_user_goal", "")
            result = {"status": "success", "approved_user_goal": goal}

        elif tool_name == "get_approved_files":
            files = state.get("approved_files", [])
            result = {"status": "success", "approved_files": files}

        elif tool_name == "sample_file":
            # Handle file reading inline
            file_path = tool_args.get("file_path", "")
            num_lines = tool_args.get("num_lines", 50)
            try:
                with open(file_path, 'r') as f:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= num_lines:
                            break
                        lines.append(line)
                    content = ''.join(lines)
                    result = {"status": "success", "content": content}
            except FileNotFoundError:
                result = {"status": "error", "error_message": f"File not found: {file_path}"}
            except Exception as e:
                result = {"status": "error", "error_message": f"Error reading file: {str(e)}"}

        elif tool_name == "get_well_known_types":
            construction_plan = state.get("approved_construction_plan", {})
            nodes = construction_plan.get("nodes", [])
            labels = [node.get("label", "") for node in nodes if node.get("label")]
            result = {"status": "success", "well_known_types": labels}

        elif tool_name == "set_proposed_entities":
            # CRITICAL: Get entities directly from tool_args
            entities = tool_args.get("entities", [])
            current_proposed_entities = entities
            state_updates["proposed_entities"] = entities
            result = {"status": "success", "message": f"Set {len(entities)} proposed entity types"}

        elif tool_name == "get_proposed_entities":
            result = {"status": "success", "proposed_entities": current_proposed_entities}

        elif tool_name == "approve_proposed_entities":
            # Copy proposed to approved
            state_updates["approved_entities"] = current_proposed_entities
            result = {"status": "success", "message": f"Approved {len(current_proposed_entities)} entity types"}

        else:
            result = {"status": "error", "error_message": f"Unknown tool: {tool_name}"}

        tool_messages.append(
            ToolMessage(content=str(result), tool_call_id=tool_id)
        )

    return {"messages": tool_messages, **state_updates}


# =============================================================================
# FACT AGENT NODE
# =============================================================================

def fact_agent_node(state: UnstructuredSchemaState) -> dict:
    """
    Fact Extraction Agent: Proposes relationship triples.

    This agent:
    1. Uses approved entity types as constraints
    2. Samples files to find relationships
    3. Proposes fact types like (Reviewer, rates, Product)
    """
    settings = get_settings()
    model = ChatOpenAI(
        model=settings.openai_model_name,
        api_key=settings.openai_api_key,
        temperature=0,
    )
    model_with_tools = model.bind_tools(FACT_AGENT_TOOLS)

    # Build messages with system instruction
    messages = [
        {"role": "system", "content": FACT_AGENT_INSTRUCTION}
    ] + state["messages"]

    response = model_with_tools.invoke(messages)
    return {"messages": [response]}


def execute_fact_tools(state: UnstructuredSchemaState) -> dict:
    """
    Execute tool calls from Fact agent and update state.

    Handles tools INLINE to properly capture state updates.
    """
    last_message = state["messages"][-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"messages": []}

    tool_messages = []
    state_updates = {}

    # Track proposed facts across multiple tool calls
    current_proposed_facts = list(state.get("proposed_facts") or [])
    approved_entities = state.get("approved_entities") or []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]

        result = None

        # Handle each tool inline
        if tool_name == "get_approved_user_goal":
            goal = state.get("approved_user_goal", "")
            result = {"status": "success", "approved_user_goal": goal}

        elif tool_name == "get_approved_files":
            files = state.get("approved_files", [])
            result = {"status": "success", "approved_files": files}

        elif tool_name == "sample_file":
            # Handle file reading inline
            file_path = tool_args.get("file_path", "")
            num_lines = tool_args.get("num_lines", 50)
            try:
                with open(file_path, 'r') as f:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= num_lines:
                            break
                        lines.append(line)
                    content = ''.join(lines)
                    result = {"status": "success", "content": content}
            except FileNotFoundError:
                result = {"status": "error", "error_message": f"File not found: {file_path}"}
            except Exception as e:
                result = {"status": "error", "error_message": f"Error reading file: {str(e)}"}

        elif tool_name == "get_approved_entities":
            result = {"status": "success", "approved_entities": approved_entities}

        elif tool_name == "add_proposed_fact":
            # CRITICAL: Get fact details directly from tool_args
            subject_type = tool_args.get("subject_type", "")
            predicate = tool_args.get("predicate", "")
            object_type = tool_args.get("object_type", "")
            description = tool_args.get("description", "")

            # Validate against approved entities
            approved_names = [e.get("name", "") if isinstance(e, dict) else e for e in approved_entities]

            if subject_type not in approved_names:
                result = {"status": "error", "error_message": f"'{subject_type}' is not an approved entity type"}
            elif object_type not in approved_names:
                result = {"status": "error", "error_message": f"'{object_type}' is not an approved entity type"}
            else:
                fact = {
                    "subject_type": subject_type,
                    "predicate": predicate,
                    "object_type": object_type,
                    "description": description
                }
                current_proposed_facts.append(fact)
                state_updates["proposed_facts"] = current_proposed_facts
                result = {"status": "success", "message": f"Added fact: ({subject_type})-[{predicate}]->({object_type})"}

        elif tool_name == "get_proposed_facts":
            result = {"status": "success", "proposed_facts": current_proposed_facts}

        elif tool_name == "approve_proposed_facts":
            state_updates["approved_facts"] = current_proposed_facts
            result = {"status": "success", "message": f"Approved {len(current_proposed_facts)} fact types"}

        else:
            result = {"status": "error", "error_message": f"Unknown tool: {tool_name}"}

        tool_messages.append(
            ToolMessage(content=str(result), tool_call_id=tool_id)
        )

    return {"messages": tool_messages, **state_updates}


# =============================================================================
# ROUTING LOGIC
# =============================================================================

def check_ner_tools(state: UnstructuredSchemaState) -> Literal["execute_ner", "wait_ner_approval"]:
    """
    Route NER agent: execute tools or wait for user approval.

    If agent made tool calls → execute them
    If no tool calls → agent is presenting results, wait for approval
    """
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "execute_ner"
    return "wait_ner_approval"


def check_fact_tools(state: UnstructuredSchemaState) -> Literal["execute_fact", "wait_fact_approval"]:
    """
    Route Fact agent: execute tools or wait for user approval.
    """
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "execute_fact"
    return "wait_fact_approval"


def route_after_approval(state: UnstructuredSchemaState) -> Literal["ner_agent", "fact_agent", "end"]:
    """
    Route based on current stage and what's been approved.

    Flow:
    1. If no approved entities → run NER agent
    2. If entities approved but no facts → run Fact agent
    3. If facts approved → end
    """
    stage = state.get("stage", "ner")

    if stage == "ner":
        # Check if entities have been approved
        if state.get("approved_entities"):
            return "fact_agent"
        return "ner_agent"
    elif stage == "fact":
        # Check if facts have been approved
        if state.get("approved_facts"):
            return "end"
        return "fact_agent"

    return "ner_agent"


# =============================================================================
# GRAPH CONSTRUCTION - TWO SEPARATE GRAPHS
# =============================================================================

def create_ner_graph():
    """
    Build the NER Agent graph.

    This graph handles entity type recognition from unstructured text.
    Entry point: ner_agent
    """
    workflow = StateGraph(UnstructuredSchemaState)

    # Add nodes
    workflow.add_node("ner_agent", ner_agent_node)
    workflow.add_node("execute_ner", execute_ner_tools)

    # Set entry point
    workflow.set_entry_point("ner_agent")

    # NER agent routing
    workflow.add_conditional_edges(
        "ner_agent",
        check_ner_tools,
        {
            "execute_ner": "execute_ner",
            "wait_ner_approval": END,  # Pause for user approval
        }
    )

    # After executing NER tools, go back to NER agent
    workflow.add_edge("execute_ner", "ner_agent")

    return workflow.compile()


def create_fact_graph():
    """
    Build the Fact Extraction Agent graph.

    This graph handles relationship triple extraction.
    Entry point: fact_agent
    Requires: approved_entities in state (from NER stage)
    """
    workflow = StateGraph(UnstructuredSchemaState)

    # Add nodes
    workflow.add_node("fact_agent", fact_agent_node)
    workflow.add_node("execute_fact", execute_fact_tools)

    # Set entry point
    workflow.set_entry_point("fact_agent")

    # Fact agent routing
    workflow.add_conditional_edges(
        "fact_agent",
        check_fact_tools,
        {
            "execute_fact": "execute_fact",
            "wait_fact_approval": END,  # Pause for user approval
        }
    )

    # After executing Fact tools, go back to Fact agent
    workflow.add_edge("execute_fact", "fact_agent")

    return workflow.compile()


# Create TWO separate compiled graphs (like the course does with two agents)
ner_schema_graph = create_ner_graph()
fact_schema_graph = create_fact_graph()
