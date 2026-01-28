"""
Session Manager - Unified session storage using Upstash Redis

This replaces the isolated `sessions = {}` dicts in each agent.
All agents can now read/write to the same session data.

Features:
- 24-hour TTL (auto-expire old sessions)
- JSON serialization (store complex Python objects)
- Async-compatible
"""

import json
from typing import Any, Dict, Optional
from datetime import timedelta

from upstash_redis import Redis
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from app.core.config import get_settings

# Global Redis client (initialized once)
_redis_client: Optional[Redis] = None


def get_redis_client() -> Redis:
    """Get or create Redis client (singleton pattern)"""
    global _redis_client

    if _redis_client is None:
        settings = get_settings()
        _redis_client = Redis(
            url=settings.upstash_redis_rest_url,
            token=settings.upstash_redis_rest_token
        )

    return _redis_client


# Session TTL (24 hours)
SESSION_TTL = timedelta(hours=24)


def get_session_key(session_id: str) -> str:
    """Convert session_id to Redis key"""
    return f"session:{session_id}"


def get_session(session_id: str) -> Dict[str, Any]:
    """
    Load session data from Redis

    Returns:
        Dict with session state, or empty dict if not found
    """
    redis = get_redis_client()
    key = get_session_key(session_id)

    # Get JSON string from Redis
    data = redis.get(key)

    if data is None:
        # New session - return empty state
        return {}

    # Parse JSON string to dict
    session_data = json.loads(data)

    # Convert message dicts back to LangChain messages
    if "messages" in session_data and session_data["messages"]:
        converted_messages = []
        for msg_dict in session_data["messages"]:
            msg_type = msg_dict.get("type", "HumanMessage")
            content = msg_dict.get("content", "")
            additional_kwargs = msg_dict.get("additional_kwargs", {})

            if msg_type == "HumanMessage":
                converted_messages.append(
                    HumanMessage(
                        content=content,
                        additional_kwargs=additional_kwargs
                    )
                )
            elif msg_type == "AIMessage":
                # Restore AIMessage with tool_calls (critical for OpenAI API)
                ai_msg = AIMessage(
                    content=content,
                    additional_kwargs=additional_kwargs
                )
                # Restore tool_calls if present
                if "tool_calls" in msg_dict and msg_dict["tool_calls"]:
                    ai_msg.tool_calls = msg_dict["tool_calls"]
                converted_messages.append(ai_msg)
            elif msg_type == "ToolMessage":
                # Restore ToolMessage with tool_call_id (links to parent AIMessage)
                tool_msg = ToolMessage(
                    content=content,
                    tool_call_id=msg_dict.get("tool_call_id", ""),
                    additional_kwargs=additional_kwargs
                )
                # Restore name if present
                if "name" in msg_dict and msg_dict["name"]:
                    tool_msg.name = msg_dict["name"]
                converted_messages.append(tool_msg)
            else:
                # Fallback to HumanMessage
                converted_messages.append(HumanMessage(content=content))

        session_data["messages"] = converted_messages

    return session_data


def save_session(session_id: str, session_data: Dict[str, Any]) -> None:
    """
    Save session data to Redis with 24-hour TTL

    Args:
        session_id: Unique session identifier
        session_data: Dict containing session state
    """
    redis = get_redis_client()
    key = get_session_key(session_id)

    # Convert LangChain messages to serializable format
    serializable_data = session_data.copy()
    if "messages" in serializable_data and serializable_data["messages"]:
        # Convert LangChain messages to dicts
        serializable_messages = []
        for msg in serializable_data["messages"]:
            msg_dict = {
                "type": msg.__class__.__name__,
                "content": msg.content,
                "additional_kwargs": getattr(msg, "additional_kwargs", {}),
            }

            # Preserve tool_calls for AIMessage (critical for OpenAI API)
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls

            # Preserve tool_call_id for ToolMessage (links to parent AIMessage)
            if hasattr(msg, "tool_call_id") and msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id

            # Preserve name field if present
            if hasattr(msg, "name") and msg.name:
                msg_dict["name"] = msg.name

            serializable_messages.append(msg_dict)

        serializable_data["messages"] = serializable_messages

    # Convert dict to JSON string
    data_json = json.dumps(serializable_data)

    # Save to Redis with TTL
    redis.set(key, data_json, ex=int(SESSION_TTL.total_seconds()))


def update_session(session_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update session with new fields (merge with existing data)

    Args:
        session_id: Unique session identifier
        updates: Dict of fields to update/add

    Returns:
        Updated session data
    """
    # Load current session
    session_data = get_session(session_id)

    # Merge updates
    session_data.update(updates)

    # Save back to Redis
    save_session(session_id, session_data)

    return session_data


def delete_session(session_id: str) -> None:
    """Delete session from Redis"""
    redis = get_redis_client()
    key = get_session_key(session_id)
    redis.delete(key)


def list_all_sessions() -> list[str]:
    """
    List all active session IDs (for debugging)

    Returns:
        List of session_id strings
    """
    redis = get_redis_client()

    # Find all keys matching "session:*"
    keys = redis.keys("session:*")

    # Extract session_id from "session:session-123456789"
    return [key.replace("session:", "") for key in keys]
