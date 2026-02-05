"""
Entity Extraction Service - Named Entity Recognition using GPT-4

Extracts entities (Person, Organization, Location, Product, etc.) from text chunks.
Creates Subject Graph nodes and MENTIONS relationships.
"""

import logging
import json
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


ENTITY_EXTRACTION_PROMPT = """You are an expert entity extraction system. Extract ALL meaningful entities from the text.

Entity types to extract:
- PERSON: People, names
- ORGANIZATION: Companies, suppliers, manufacturers, teams
- LOCATION: Cities, countries, factories, addresses
- PRODUCT: Parts, components, products, materials
- METRIC: Quality scores, ratings, measurements, KPIs
- DATE: Dates, time periods
- OTHER: Any other significant entities

Return JSON array of entities:
[
    {"text": "Acme Corp", "type": "ORGANIZATION"},
    {"text": "Steel Frame", "type": "PRODUCT"},
    {"text": "quality issues", "type": "METRIC"}
]

Extract entities from this text:
{text}

Return ONLY the JSON array, no explanation."""


def extract_entities_from_chunk(text: str, model: str = "gpt-4o-mini") -> List[Dict[str, str]]:
    """
    Extract entities from a single text chunk using GPT-4.

    Args:
        text: Text chunk to analyze
        model: OpenAI model to use (gpt-4o-mini for cost efficiency)

    Returns:
        List of entities: [{"text": "entity", "type": "ORGANIZATION"}, ...]

    Example:
        chunk = "Acme Corp supplies steel frames with quality issues"
        entities = extract_entities_from_chunk(chunk)
        # [{"text": "Acme Corp", "type": "ORGANIZATION"},
        #  {"text": "steel frames", "type": "PRODUCT"},
        #  {"text": "quality issues", "type": "METRIC"}]
    """
    try:
        llm = ChatOpenAI(
            model=model,
            temperature=0,
            api_key=settings.openai_api_key
        )

        messages = [
            SystemMessage(content="You are an expert entity extraction system."),
            HumanMessage(content=ENTITY_EXTRACTION_PROMPT.format(text=text))
        ]

        response = llm.invoke(messages)
        content = response.content.strip()

        # Parse JSON response
        # Handle markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        entities = json.loads(content)

        # Validate structure
        if not isinstance(entities, list):
            logger.warning("[NER] Response not a list, returning empty")
            return []

        # Filter valid entities
        valid_entities = []
        for entity in entities:
            if isinstance(entity, dict) and "text" in entity and "type" in entity:
                # Normalize entity text (lowercase for matching)
                entity["text"] = entity["text"].strip()
                entity["type"] = entity["type"].upper()
                valid_entities.append(entity)

        logger.info(f"[NER] Extracted {len(valid_entities)} entities from chunk")
        return valid_entities

    except json.JSONDecodeError as e:
        logger.error(f"[NER] JSON parse error: {e}")
        return []
    except Exception as e:
        logger.error(f"[NER] Error extracting entities: {e}")
        return []


def extract_entities_batch(chunks: List[Dict[str, Any]], max_chunks: int = 50) -> Dict[str, Any]:
    """
    Extract entities from multiple chunks (batch processing).

    Args:
        chunks: List of chunk dicts with 'id' and 'text' keys
        max_chunks: Process at most this many chunks (cost control)

    Returns:
        {
            "status": "success",
            "entities": [{"entity_text": "...", "entity_type": "...", "chunk_ids": [...]}],
            "entity_count": 42,
            "chunks_processed": 50
        }

    Example:
        chunks = [
            {"id": "chunk_1", "text": "Acme Corp supplies steel"},
            {"id": "chunk_2", "text": "Acme Corp has quality issues"}
        ]
        result = extract_entities_batch(chunks)
        # Consolidates "Acme Corp" from both chunks into single entity
    """
    logger.info(f"[NER] Starting batch entity extraction for {len(chunks)} chunks")

    # Limit processing for cost control
    chunks_to_process = chunks[:max_chunks]
    all_entities = {}  # {entity_text: {"type": "...", "chunk_ids": [...]}}

    for i, chunk in enumerate(chunks_to_process):
        chunk_id = chunk.get("id")
        chunk_text = chunk.get("text", "")

        if not chunk_text:
            continue

        # Extract entities from this chunk
        entities = extract_entities_from_chunk(chunk_text)

        # Consolidate entities (group by text)
        for entity in entities:
            entity_text = entity["text"].lower()  # Normalize for matching
            entity_type = entity["type"]

            if entity_text not in all_entities:
                all_entities[entity_text] = {
                    "text": entity["text"],  # Keep original casing
                    "type": entity_type,
                    "chunk_ids": []
                }

            # Add chunk reference
            if chunk_id not in all_entities[entity_text]["chunk_ids"]:
                all_entities[entity_text]["chunk_ids"].append(chunk_id)

        if (i + 1) % 10 == 0:
            logger.info(f"[NER] Processed {i + 1}/{len(chunks_to_process)} chunks")

    # Convert to list format
    entity_list = []
    for entity_key, entity_data in all_entities.items():
        entity_list.append({
            "entity_text": entity_data["text"],
            "entity_type": entity_data["type"],
            "chunk_ids": entity_data["chunk_ids"]
        })

    logger.info(f"[NER] ✓ Extracted {len(entity_list)} unique entities from {len(chunks_to_process)} chunks")

    return {
        "status": "success",
        "entities": entity_list,
        "entity_count": len(entity_list),
        "chunks_processed": len(chunks_to_process)
    }
