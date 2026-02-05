import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage,HumanMessage
from app.core.config import settings
from app.core.enums import FlowType

logger = logging.getLogger(__name__)


model = ChatOpenAI(
   api_key=settings.openai_api_key,
     model=settings.openai_model_name,
     temperature=0.0,
)

async def classify_intent(message: str) -> FlowType:
    """
    Classify user's intent into one of three flows.
    
    Args:
        message: User's first message
    
    Returns:
        FlowType.BUILD - Create new knowledge base
        FlowType.QUERY - Search existing knowledge base  
        FlowType.EXTEND - Add to existing knowledge base
    
    Examples:
        "Help me organize supplier data" → BUILD
        "What suppliers do I have?" → QUERY
        "Add product data to my KB" → EXTEND
    """
    
    system_prompt = """You are an intent classifier for a knowledge base system.

Classify the user's message into ONE of these categories:

1. BUILD - User wants to CREATE a new knowledge base from files
   Examples:
   - "Help me organize my data"
   - "Build a graph from my CSV files"
   - "I want to create a knowledge base"
   - "Analyze my supplier data"

2. QUERY - User wants to SEARCH/QUERY an existing knowledge base
   Examples:
   - "What suppliers do I have?"
   - "Show me all products"
   - "Find information about..."
   - "Tell me about..."

3. EXTEND - User wants to ADD data to an existing knowledge base
   Examples:
   - "Add product data to my supplier KB"
   - "Update my knowledge base with..."
   - "Include these new files"
   - "Merge this data with my existing graph"

Respond with ONLY one word: BUILD, QUERY, or EXTEND"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=message)
    ]

    response = await model.ainvoke(messages)

    classification = response.content.strip().upper()

    flow_map = {
        "BUILD": FlowType.BUILD,
        "QUERY": FlowType.QUERY,
        "EXTEND": FlowType.EXTEND,
    }
    mapped = flow_map.get(classification, FlowType.BUILD)
    logger.info(f"[INTENT_CLASSIFIER] Input: \"{message}\" → Raw LLM: \"{response.content.strip()}\" → Mapped: {mapped.value}" + (f" (fallback from \"{classification}\")" if classification not in flow_map else ""))
    return mapped
    

  