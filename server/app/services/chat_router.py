"""
Chat Router - Routes messages to the correct agent based on current phase.

Key design: Router owns ALL phase transitions and checkpoint logic.
Agents are pure data producers — they return results, router decides what to do.

State merge pattern: Each handler extracts only the keys an agent needs,
invokes the agent, then merges the result back into the full session dict.
This prevents session fields from being lost across agent boundaries.
"""

from typing import Dict, Any
import logging
from langchain_core.messages import HumanMessage, AIMessage

from app.agents.graphs.user_intent_graph import user_intent_graph
from app.agents.graphs.file_suggestion_graph import file_suggestion_graph
from app.agents.graphs.schema_proposal_graph import schema_proposal_graph
from app.agents.graphs.unstructured_schema_graph import ner_schema_graph, fact_schema_graph
from app.services.checkpoint_handler import classify_user_intent
from app.services.graph_query_service import query_graph, query_domain_direct

logger = logging.getLogger(__name__)


def _merge_agent_result(session: Dict[str, Any], result: Dict[str, Any], keys: list) -> None:
    """Merge specific keys from agent result back into session, always merge messages."""
    session["messages"] = result["messages"]
    for key in keys:
        if key in result:
            session[key] = result[key]


def route_to_agent(session: Dict[str, Any], message: str) -> Dict[str, Any]:
    """Route message to correct agent based on current_phase."""
    phase = session.get("current_phase", "user_intent")
    logger.info(f"[chat_router] Routing to phase: {phase}")

    if phase == "user_intent":
        return handle_user_intent_phase(session, message)
    elif phase == "file_suggestion":
        return handle_file_suggestion_phase(session, message)
    elif phase == "schema_proposal":
        return handle_schema_proposal_phase(session, message)
    elif phase == "unstructured_schema":
        return handle_unstructured_schema_phase(session, message)
    elif phase == "graph_construction":
        return handle_graph_construction_phase(session, message)
    elif phase == "query":
        return handle_query_phase(session, message)
    else:
        raise ValueError(f"Unknown phase: {phase}")


# =============================================================================
# PHASE HANDLERS
# =============================================================================

def handle_user_intent_phase(session: Dict[str, Any], message: str) -> Dict[str, Any]:
    """
    Handle user_intent phase.

    Agent job: clarify goal, call set_perceived_user_goal (and optionally approve)
    Router job: detect approval, force transition if agent missed it
    """
    logger.info("[chat_router] Handling user_intent phase")

    session["messages"].append(HumanMessage(content=message))

    # Prepare agent input — only the keys UserIntentState needs
    agent_input = {
        "messages": session["messages"],
        "perceived_user_goal": session.get("perceived_user_goal"),
        "approved_user_goal": session.get("approved_user_goal"),
    }

    result = user_intent_graph.invoke(agent_input)

    # Merge agent output back into session
    _merge_agent_result(session, result, ["perceived_user_goal", "approved_user_goal"])

    # --- Router fallback: if agent didn't approve but user clearly did ---
    if not session.get("approved_user_goal") and session.get("perceived_user_goal"):
        intent = classify_user_intent(message)
        if intent == "approve":
            logger.info("[chat_router] Router forcing goal approval (agent missed approve tool call)")
            session["approved_user_goal"] = session["perceived_user_goal"]

    # Deterministic transition
    if session.get("approved_user_goal"):
        logger.info("[chat_router] Goal approved, transitioning to file_suggestion")
        session["current_phase"] = "file_suggestion"

    return session


def handle_file_suggestion_phase(session: Dict[str, Any], message: str) -> Dict[str, Any]:
    """
    Handle file_suggestion phase.

    Agent job: list files, sample them, call set_suggested_files
    Router job: detect suggested_files, set checkpoint for user approval
    """
    logger.info("[chat_router] Handling file_suggestion phase")

    session["messages"].append(HumanMessage(content=message))

    # Prepare agent input — only the keys FileSuggestionState needs
    agent_input = {
        "messages": session["messages"],
        "approved_user_goal": session.get("approved_user_goal"),
        "all_available_files": session.get("all_available_files"),
        "suggested_files": session.get("suggested_files"),
        "approved_files": session.get("approved_files"),
    }

    result = file_suggestion_graph.invoke(agent_input)

    # Merge agent output back into session
    _merge_agent_result(session, result, [
        "all_available_files", "suggested_files", "approved_files"
    ])

    # --- Router sets checkpoint if files were suggested ---
    if session.get("suggested_files") and not session.get("approved_files"):
        logger.info("[chat_router] Files suggested, setting checkpoint")
        session["checkpoint"] = "files_approval"
        session["awaiting_user_action"] = True
        session["proposed_files"] = session["suggested_files"]
        session["proposed_data"] = {
            "files": session["suggested_files"],
            "all_files": session.get("all_available_files", [])
        }
        session["actions"] = {
            "approve": "Proceed with these files",
            "modify": "Let me change the files",
            "cancel": "Start over"
        }

    # Safety: if agent somehow approved files, transition
    elif session.get("approved_files"):
        logger.info("[chat_router] Files approved, transitioning to schema_proposal")
        session["current_phase"] = "schema_proposal"
        session["checkpoint"] = None
        session["awaiting_user_action"] = False

    return session


def handle_schema_proposal_phase(session: Dict[str, Any], message: str) -> Dict[str, Any]:
    """
    Handle schema_proposal phase.

    Agent job: analyze files, design schema via proposal+critic loop
    Router job: detect proposed_construction_plan, set checkpoint
    """
    logger.info("[chat_router] Handling schema_proposal phase")

    session["messages"].append(HumanMessage(content=message))

    # Prepare agent input — only the keys SchemaProposalState needs
    agent_input = {
        "messages": session["messages"],
        "approved_user_goal": session.get("approved_user_goal"),
        "approved_files": session.get("approved_files"),
        "proposed_construction_plan": session.get("proposed_construction_plan"),
        "approved_construction_plan": session.get("approved_construction_plan"),
        "feedback": session.get("feedback", ""),
        "current_agent": session.get("current_agent", "proposal"),
        "iteration_count": session.get("iteration_count", 0),
    }

    result = schema_proposal_graph.invoke(agent_input)

    # Merge agent output back into session
    _merge_agent_result(session, result, [
        "proposed_construction_plan", "approved_construction_plan",
        "feedback", "current_agent", "iteration_count"
    ])

    # --- Router sets checkpoint if schema was proposed ---
    if session.get("proposed_construction_plan") and not session.get("approved_construction_plan"):
        logger.info("[chat_router] Schema proposed, setting checkpoint")
        session["checkpoint"] = "schema_approval"
        session["awaiting_user_action"] = True
        session["proposed_data"] = {
            "construction_plan": session["proposed_construction_plan"]
        }
        session["actions"] = {
            "approve": "Build the graph",
            "modify": "Change the schema",
            "preview": "Show me a sample",
            "cancel": "Go back to files"
        }

    # Safety: if agent somehow approved, transition
    elif session.get("approved_construction_plan"):
        logger.info("[chat_router] Schema approved, transitioning to graph_construction")
        session["current_phase"] = "graph_construction"
        session["checkpoint"] = None
        session["awaiting_user_action"] = False

    return session


def handle_unstructured_schema_phase(session: Dict[str, Any], message: str) -> Dict[str, Any]:
    """
    Handle unstructured_schema phase — NER and Fact extraction from text files.

    Two-stage flow:
    - Stage "ner": Extract entity types from text
    - Stage "fact": Extract relationship triples using approved entities

    Router sets checkpoints for user approval between stages.
    """
    stage = session.get("unstructured_stage", "ner")
    logger.info(f"[chat_router] Handling unstructured_schema phase, stage: {stage}")

    session["messages"].append(HumanMessage(content=message))

    # Only pass unstructured files to this agent
    all_files = session.get("approved_files", [])
    unstructured_files = [f for f in all_files if f.lower().endswith(('.md', '.txt'))]

    # Prepare agent input — only the keys UnstructuredSchemaState needs
    agent_input = {
        "messages": session["messages"],
        "stage": stage,
        "approved_user_goal": session.get("approved_user_goal", ""),
        "approved_files": unstructured_files,
        "approved_construction_plan": session.get("approved_construction_plan", {}),
        "proposed_entities": session.get("proposed_entities", []),
        "approved_entities": session.get("approved_entities", []),
        "proposed_facts": session.get("proposed_facts", []),
        "approved_facts": session.get("approved_facts", []),
    }

    # Invoke appropriate stage graph
    if stage == "ner":
        result = ner_schema_graph.invoke(agent_input)
    else:
        result = fact_schema_graph.invoke(agent_input)

    # Merge results back into session
    _merge_agent_result(session, result, [
        "proposed_entities", "approved_entities",
        "proposed_facts", "approved_facts", "stage"
    ])
    # Preserve unstructured_stage from session (not overwritten by agent)
    if "stage" in result:
        session["unstructured_stage"] = result["stage"]

    # --- Router checkpoint logic ---
    if stage == "ner":
        if session.get("proposed_entities") and not session.get("approved_entities"):
            logger.info("[chat_router] Entities proposed, setting checkpoint")
            session["checkpoint"] = "entities_approval"
            session["awaiting_user_action"] = True
            session["proposed_data"] = {"entities": session["proposed_entities"]}
            session["actions"] = {
                "approve": "Approve these entities",
                "modify": "Change entities",
                "cancel": "Go back"
            }

    elif stage == "fact":
        if session.get("proposed_facts") and not session.get("approved_facts"):
            logger.info("[chat_router] Facts proposed, setting checkpoint")
            session["checkpoint"] = "facts_approval"
            session["awaiting_user_action"] = True
            session["proposed_data"] = {"facts": session["proposed_facts"]}
            session["actions"] = {
                "approve": "Approve these facts",
                "modify": "Change facts",
                "cancel": "Go back to entities"
            }
        elif session.get("approved_facts"):
            # Facts approved → transition to graph_construction
            logger.info("[chat_router] Facts approved, transitioning to graph_construction")
            session["current_phase"] = "graph_construction"
            session["checkpoint"] = None
            session["awaiting_user_action"] = False

    return session


def handle_graph_construction_phase(session: Dict[str, Any], message: str) -> Dict[str, Any]:
    """Handle graph_construction phase — show build summary, set checkpoint."""
    logger.info("[chat_router] Handling graph_construction phase")

    session["messages"].append(HumanMessage(content=message))

    if not session.get("awaiting_user_action"):
        construction_plan = session.get("approved_construction_plan", {})
        node_types = [k for k, v in construction_plan.items() if v.get("construction_type") == "node"]
        rel_types = [k for k, v in construction_plan.items() if v.get("construction_type") == "relationship"]

        session["checkpoint"] = "build_approval"
        session["awaiting_user_action"] = True
        session["proposed_data"] = {
            "node_types": len(node_types),
            "relationship_types": len(rel_types),
        }
        session["actions"] = {
            "approve": "Build the graph",
            "cancel": "Not yet"
        }

        # Detect file types for summary
        all_files = session.get('approved_files', [])
        structured_files = [f for f in all_files if f.lower().endswith(('.csv', '.tsv'))]
        unstructured_files = [f for f in all_files if f.lower().endswith(('.md', '.txt'))]

        summary_lines = ["Ready to build your graph:", ""]
        if node_types or rel_types:
            summary_lines.append(f"**Structured (from CSV):**")
            summary_lines.append(f"• Node types: {len(node_types)} ({', '.join(node_types)})")
            summary_lines.append(f"• Relationship types: {len(rel_types)} ({', '.join(rel_types)})")
            summary_lines.append(f"• Source files: {', '.join(structured_files)}")
            summary_lines.append("")
        if unstructured_files:
            summary_lines.append(f"**Unstructured (text extraction):**")
            summary_lines.append(f"• Files: {', '.join(unstructured_files)}")
            if session.get("approved_entities"):
                summary_lines.append(f"• Entity types: {len(session['approved_entities'])}")
            summary_lines.append("")
        summary_lines.append("Proceed with graph construction?")
        summary = "\n".join(summary_lines)

        session["messages"].append(AIMessage(content=summary))

    return session


def handle_query_phase(session: Dict[str, Any], message: str) -> Dict[str, Any]:
    """Handle query phase — Q&A about the built graph via GraphRAG with domain fallback."""
    logger.info("[chat_router] Handling query phase")

    session["messages"].append(HumanMessage(content=message))

    try:
        # Try full GraphRAG pipeline first (requires lexical graph + vector index)
        result = query_graph(message)

        if result.get("status") == "success":
            answer = result.get("query_result", {}).get("answer", "No answer generated.")
            session["messages"].append(AIMessage(content=answer))
        else:
            # No chunks found — fall back to direct domain graph query
            logger.info("[chat_router] GraphRAG returned no results, falling back to domain query")
            result = query_domain_direct(message)
            answer = result.get("query_result", {}).get("answer", "I couldn't find relevant information.")
            session["messages"].append(AIMessage(content=answer))

    except Exception as e:
        logger.info(f"[chat_router] GraphRAG pipeline failed ({e}), trying domain query fallback")
        try:
            result = query_domain_direct(message)
            answer = result.get("query_result", {}).get("answer", "I couldn't answer that question.")
            session["messages"].append(AIMessage(content=answer))
        except Exception as e2:
            logger.error(f"[chat_router] Fallback query also failed: {e2}")
            session["messages"].append(
                AIMessage(content="I couldn't process your query. Please try rephrasing your question.")
            )

    return session
