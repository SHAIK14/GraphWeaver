
from typing import TypedDict, Annotated,Sequence
from langchain_core.messages import BaseMessage , SystemMessage, HumanMessage , AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages


from app.agents.prompts.intent_prompts import INTENT_SYSTEM_PROMPT
from app.agents.tools.intent_tools import set_perceived_goal, approve_goal
from app.core.state import SessionState ,Message
from app.core.enums import Phase, MessageRole
from app.core.config import settings



class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    perceived_goal: dict | None
    approved_goal: dict | None
    

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
    
    messages =[SystemMessage(content=INTENT_SYSTEM_PROMPT)] + state["messages"]
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

    result = await graph.ainvoke({
        "messages": langchain_messages,
        "perceived_goal": None,
        "approved_goal": None,
    })

    last_message = result["messages"][-1]
    response  = last_message.content if hasattr(last_message, "content") else str(last_message)

    session_state.messages.append(Message(role=MessageRole.USER, content=user_message))
    session_state.messages.append(Message(role=MessageRole.ASSISTANT, content=response))

    # Parse tool calls and update session state
    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tool_call in msg.tool_calls:
                if tool_call['name'] == 'set_perceived_goal':
                    category = tool_call['args']['category']
                    description = tool_call['args']['description']
                    session_state.user_goal = f"{category}: {description}"
                    logger.info(f"[INTENT_AGENT] ✓ set_perceived_goal called: {session_state.user_goal}")
                elif tool_call['name'] == 'approve_goal':
                    session_state.goal_approved = True
                    session_state.phase = Phase.FILES
                    logger.info(f"[INTENT_AGENT] ✓ approve_goal called - Phase changed to: {session_state.phase}")

    logger.info(f"[INTENT_AGENT] Finished - Final phase: {session_state.phase}, Goal approved: {session_state.goal_approved}")
    return response, session_state
            
    

    
    
        
    
    

    
    