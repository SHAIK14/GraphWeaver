"""
Entity Resolution Service - Match text entities to domain nodes

Bridges the gap between:
- Entity nodes (extracted from text via NER)
- Domain nodes (imported from structured CSV data)

Example: Entity("Acme Corp") → Supplier(name="Acme Corporation")
"""

import logging
from typing import List, Dict, Any, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """
    Normalize text for matching.

    - Lowercase
    - Remove common suffixes (Inc, Corp, Ltd, etc.)
    - Strip whitespace

    Example:
        "Acme Corporation Inc." → "acme corporation"
        "Steel Frame Part" → "steel frame part"
    """
    text = text.lower().strip()

    # Remove common business suffixes
    suffixes = [
        ' inc', ' inc.', ' corp', ' corp.', ' corporation',
        ' ltd', ' ltd.', ' llc', ' limited',
        ' co', ' co.', ' company'
    ]

    for suffix in suffixes:
        if text.endswith(suffix):
            text = text[:-len(suffix)].strip()

    return text


def fuzzy_match_score(text1: str, text2: str) -> float:
    """
    Calculate similarity score between two strings.

    Args:
        text1, text2: Strings to compare

    Returns:
        Score from 0.0 (no match) to 1.0 (exact match)

    Example:
        fuzzy_match_score("Acme Corp", "Acme Corporation") → 0.85
        fuzzy_match_score("Steel Frame", "Steel Frames") → 0.95
    """
    # Normalize both texts
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)

    # Exact match after normalization
    if norm1 == norm2:
        return 1.0

    # Fuzzy match using SequenceMatcher
    return SequenceMatcher(None, norm1, norm2).ratio()


def find_best_match(
    entity_text: str,
    candidates: List[Dict[str, Any]],
    threshold: float = 0.85
) -> Tuple[str, str, float]:
    """
    Find best matching domain node for an entity.

    Args:
        entity_text: Text from Entity node
        candidates: List of domain nodes with 'label' and 'name' keys
        threshold: Minimum score to consider a match (0.85 = 85% similar)

    Returns:
        (matched_label, matched_name, score) or (None, None, 0.0)

    Example:
        entity_text = "Acme Corp"
        candidates = [
            {"label": "Supplier", "name": "Acme Corporation"},
            {"label": "Supplier", "name": "Beta Industries"}
        ]
        → ("Supplier", "Acme Corporation", 0.92)
    """
    best_match = None
    best_score = 0.0
    best_label = None

    for candidate in candidates:
        candidate_name = candidate.get("name", "")
        candidate_label = candidate.get("label", "")

        if not candidate_name:
            continue

        score = fuzzy_match_score(entity_text, candidate_name)

        if score > best_score:
            best_score = score
            best_match = candidate_name
            best_label = candidate_label

    # Only return if score meets threshold
    if best_score >= threshold:
        return (best_label, best_match, best_score)

    return (None, None, 0.0)


def resolve_entities(
    entities: List[Dict[str, Any]],
    domain_nodes: List[Dict[str, Any]],
    threshold: float = 0.85
) -> List[Dict[str, Any]]:
    """
    Match all entities to domain nodes.

    Args:
        entities: List of Entity nodes [{"name": "...", "type": "..."}]
        domain_nodes: List of domain nodes [{"label": "Supplier", "name": "..."}]
        threshold: Matching threshold (default 0.85)

    Returns:
        List of matches:
        [
            {
                "entity_name": "Acme Corp",
                "entity_type": "ORGANIZATION",
                "domain_label": "Supplier",
                "domain_name": "Acme Corporation",
                "score": 0.92
            },
            ...
        ]
    """
    logger.info(f"[ENTITY_RESOLUTION] Resolving {len(entities)} entities against {len(domain_nodes)} domain nodes")

    matches = []

    for entity in entities:
        entity_name = entity.get("name", "")
        entity_type = entity.get("type", "")

        if not entity_name:
            continue

        # Find best matching domain node
        label, name, score = find_best_match(entity_name, domain_nodes, threshold)

        if label and name:
            matches.append({
                "entity_name": entity_name,
                "entity_type": entity_type,
                "domain_label": label,
                "domain_name": name,
                "score": score
            })
            logger.debug(f"[ENTITY_RESOLUTION] Matched: {entity_name} → {label}({name}) [score: {score:.2f}]")

    logger.info(f"[ENTITY_RESOLUTION] ✓ Found {len(matches)} matches (threshold: {threshold})")

    return matches


def filter_by_entity_type(
    entities: List[Dict[str, Any]],
    entity_types: List[str]
) -> List[Dict[str, Any]]:
    """
    Filter entities by type (ORGANIZATION, PRODUCT, etc.).

    Useful for targeted matching:
    - ORGANIZATION entities → Supplier/Factory nodes
    - PRODUCT entities → Part nodes

    Args:
        entities: List of Entity nodes
        entity_types: Types to keep (e.g., ["ORGANIZATION", "PRODUCT"])

    Returns:
        Filtered list of entities
    """
    return [e for e in entities if e.get("type") in entity_types]


def suggest_threshold(sample_matches: List[Tuple[str, str]]) -> float:
    """
    Suggest optimal threshold based on sample matches.

    Useful for tuning: run this on a sample, inspect scores,
    then adjust threshold accordingly.

    Args:
        sample_matches: [(entity_text, domain_name), ...]

    Returns:
        Suggested threshold value
    """
    if not sample_matches:
        return 0.85

    scores = [fuzzy_match_score(e, d) for e, d in sample_matches]
    avg_score = sum(scores) / len(scores)

    # Suggest threshold slightly below average
    suggested = max(0.70, avg_score - 0.10)

    logger.info(f"[ENTITY_RESOLUTION] Suggested threshold: {suggested:.2f} (avg score: {avg_score:.2f})")

    return suggested
