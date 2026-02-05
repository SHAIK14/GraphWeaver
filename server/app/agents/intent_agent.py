
from typing import TypedDict, Annotated,Sequence
from langchain_core.messages import BaseMessage , SystemMessage, HumanMessage , AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages


from app.agents.prompts.intent_prompts import INTENT_SYSTEM_PROMPT
from app.agents.tools.intent_tools import set_perceived_goal, approve_goal
from app.core.state import SessionState, Message, Checkpoint
from app.core.enums import Phase, MessageRole, CheckpointType
from app.core.config import settings



class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    perceived_goal: dict | None
    approved_goal: dict | None
    file_count: int
    files_summary: str
    

def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]

    # If there are tool calls, execute them first
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # No tool calls means conversation is done
    return "end"

def call_model(state: AgentState) -> AgentState:

    llm = ChatOpenAI(
        model = settings.openai_model_name,
        api_key = settings.openai_api_key,
          temperature = 0.0,
    )
    llm_with_tools = llm.bind_tools([set_perceived_goal, approve_goal])

    # Inject file context into system prompt
    file_count = state.get("file_count", 0)
    files_summary = state.get("files_summary", "")

    if file_count > 0:
        file_context = f"\n\n**FILES ALREADY UPLOADED: {file_count}**\n{files_summary}\n"
    else:
        file_context = ""

    system_prompt = INTENT_SYSTEM_PROMPT + file_context

    messages =[SystemMessage(content=system_prompt)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

tool_node = ToolNode([set_perceived_goal, approve_goal])

workflow = StateGraph(AgentState)

workflow.add_node("agent",call_model)
workflow.add_node("tools",tool_node)

workflow.set_entry_point("agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        "end": END
    }
)

workflow.add_edge("tools", "agent")

graph = workflow.compile()
    
async def run_intent_agent(session_state: SessionState , user_message: str) -> tuple[str, SessionState]:
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"[INTENT_AGENT] Starting - Current phase: {session_state.phase}")
    logger.info(f"[INTENT_AGENT] User message: {user_message}")

    langchain_messages = []
    for msg in session_state.messages:
        if msg.role == MessageRole.USER:
            langchain_messages.append(HumanMessage(content=msg.content))
        elif msg.role == MessageRole.ASSISTANT:
            langchain_messages.append(AIMessage(content=msg.content))

    langchain_messages.append(HumanMessage(content=user_message))

    # Prepare file context
    file_count = len(session_state.files)
    if file_count > 0:
        files_summary = "\n".join([
            f"  • {f.name} ({f.type}): "
            f"{f.raw_count or 'N/A'} rows, "
            f"columns: {', '.join(f.columns) if f.columns else 'N/A'}"
            for f in session_state.files
        ])
    else:
        files_summary = ""

    result = await graph.ainvoke({
        "messages": langchain_messages,
        "perceived_goal": None,
        "approved_goal": None,
        "file_count": file_count,
        "files_summary": files_summary,
    })

    last_message = result["messages"][-1]
    response  = last_message.content if hasattr(last_message, "content") else str(last_message)

    session_state.messages.append(Message(role=MessageRole.USER, content=user_message))
    session_state.messages.append(Message(role=MessageRole.ASSISTANT, content=response))

    # Parse tool calls and update session state
    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tool_call in msg.tool_calls:
                if tool_call['name'] == 'approve_goal':
                    # User approved - move to FILES phase
                    session_state.goal_approved = True
                    session_state.checkpoint = None
                    session_state.phase = Phase.FILES
                    logger.info(f"[INTENT_AGENT] ✓ User approved goal, moved to FILES phase")

    # CODE-DRIVEN: Auto-infer goal and move to FILES phase (no checkpoint needed)
    if not session_state.user_goal and file_count > 0:
        # Agent analyzed files, infer goal from response
        if "supply chain" in response.lower() or "supplier" in response.lower():
            session_state.user_goal = "Supply Chain: Track suppliers, parts, and shipments"
        elif "team" in response.lower() or "people" in response.lower():
            session_state.user_goal = "Team Organization: Track people and projects"
        else:
            # Generic extraction from files
            file_types = [f.name.replace('.csv', '').replace('.json', '') for f in session_state.files[:3]]
            session_state.user_goal = f"Data Organization: Track {', '.join(file_types)}"

        # No checkpoint - auto-approve and move to FILES
        session_state.goal_approved = True
        session_state.phase = Phase.FILES
        logger.info(f"[INTENT_AGENT] ✓ Auto-inferred goal and moved to FILES: {session_state.user_goal}")

    logger.info(f"[INTENT_AGENT] Finished - Final phase: {session_state.phase}, Goal approved: {session_state.goal_approved}")
    return response, session_state
            
    

    
    
        
    
    

    
    