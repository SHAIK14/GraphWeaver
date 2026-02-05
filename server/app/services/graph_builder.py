"""
Graph Builder Service - Constructs Neo4j knowledge graph from approved schema.

This service bridges the gap between the simple proposed_schema format
and the actual Neo4j graph construction using Cypher queries.

Key differences from old server:
- Works with FileData objects (in-memory) instead of CSV files on disk
- Takes simplified schema format (just labels + properties)
- Auto-detects unique keys from column names
- Generates Cypher queries dynamically

Flow:
1. Parse CSV content from FileData.content strings
2. Create uniqueness constraints (prevent duplicate nodes)
3. Import nodes using UNWIND + MERGE (batch operation)
4. Import relationships by matching existing nodes
"""

import csv
import io
import logging
from typing import List, Dict, Any, Optional

from app.services.neo4j_client import neo4j_client
from app.core.state import FileData

logger = logging.getLogger(__name__)


# =============================================================================
# HELPER: CSV PARSING
# =============================================================================

def parse_csv_content(file_data: FileData) -> List[Dict[str, str]]:
    """
    Parse CSV content string into list of dictionaries.

    Args:
        file_data: FileData object with CSV content string

    Returns:
        List of row dictionaries: [{"col1": "val1", "col2": "val2"}, ...]

    Example:
        file_data.content = "id,name\n1,Alice\n2,Bob"
        → [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]
    """
    logger.info(f"[PARSE_CSV] File: {file_data.name}")
    logger.info(f"[PARSE_CSV] Content length: {len(file_data.content) if file_data.content else 0}")
    logger.info(f"[PARSE_CSV] Content preview: {file_data.content[:200] if file_data.content else 'EMPTY'}")

    rows = []
    try:
        # Use StringIO to treat string as file-like object
        csv_file = io.StringIO(file_data.content)
        reader = csv.DictReader(csv_file)

        for row in reader:
            # Convert to regular dict and strip whitespace
            clean_row = {k.strip(): v.strip() for k, v in row.items()}
            rows.append(clean_row)

        logger.info(f"[PARSE_CSV] ✓ Parsed {len(rows)} rows from {file_data.name}")
        rows = cast_row_types(rows)
        return rows

    except Exception as e:
        logger.error(f"[PARSE_CSV] ❌ Error parsing {file_data.name}: {e}")
        return []


def _detect_column_types(rows: List[Dict[str, str]]) -> Dict[str, str]:
    """
    Infer the best type for every column by scanning all values.

    Returns a dict mapping column name → one of 'int', 'float', 'bool', 'str'.
    A column is typed as int/float/bool only if EVERY non-empty value in that
    column is a valid instance of that type.  Falls back to 'str' otherwise.
    """
    if not rows:
        return {}

    col_types: Dict[str, str] = {}
    for col in rows[0].keys():
        could_be_int = True
        could_be_float = True
        could_be_bool = True
        has_value = False

        for row in rows:
            v = (row.get(col) or "").strip()
            if not v:
                continue
            has_value = True

            if could_be_bool and v.lower() not in ("true", "false"):
                could_be_bool = False
            if could_be_int:
                try:
                    int(v)
                except ValueError:
                    could_be_int = False
            if could_be_float:
                try:
                    float(v)
                except ValueError:
                    could_be_float = False

        if not has_value:
            col_types[col] = "str"
        elif could_be_bool:
            col_types[col] = "bool"
        elif could_be_int:
            col_types[col] = "int"
        elif could_be_float:
            col_types[col] = "float"
        else:
            col_types[col] = "str"

    return col_types


def cast_row_types(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Cast all values in every row from strings to their detected native types.

    Numeric columns become int/float so Neo4j SUM/AVG/comparisons work.
    Boolean columns (true/false) become native booleans.
    Everything else stays as str.
    """
    if not rows:
        return rows

    col_types = _detect_column_types(rows)
    logger.info(f"[PARSE_CSV] Detected column types: {col_types}")

    cast_rows: List[Dict[str, Any]] = []
    for row in rows:
        cast_row: Dict[str, Any] = {}
        for col, val in row.items():
            v = (val or "").strip()
            if not v:
                cast_row[col] = None
                continue
            t = col_types.get(col, "str")
            if t == "bool":
                cast_row[col] = v.lower() == "true"
            elif t == "int":
                cast_row[col] = int(v)
            elif t == "float":
                cast_row[col] = float(v)
            else:
                cast_row[col] = v
        cast_rows.append(cast_row)

    return cast_rows




def detect_unique_key(properties: List[str], label: str) -> str:
    """
    Detect which property should be used as the unique identifier.

    This is a critical business logic decision that affects:
    - Data integrity (MERGE uses this to prevent duplicates)
    - Query performance (constraint creates index)
    - Relationship matching (must reference the same key)

    Common patterns:
    - Exact match: "id", "supplier_id", "part_id"
    - Suffix match: ends with "_id"
    - Label match: "supplier" + "_id" for Supplier nodes
    - Fallback: first column if no ID found

    TODO: Implement the unique key detection logic below.
    Consider these trade-offs:
    1. Strict matching (only "id" or "{label}_id") - safer but might miss valid keys
    2. Loose matching (any column with "id") - flexible but might pick wrong column
    3. Position-based (first column) - simple but assumes data structure

    Args:
        properties: List of column names from the CSV
        label: Node label (e.g., "Supplier")

    Returns:
        The property name to use as unique key

    Example:
        properties = ["supplier_id", "name", "location"]
        label = "Supplier"
        → Should return "supplier_id"

        properties = ["id", "title", "author"]
        label = "Book"
        → Should return "id"
    """

    # TODO: YOUR IMPLEMENTATION HERE (5-10 lines)
    # Hint: Check for exact matches first, then patterns, then fallback

    label_lower = label.lower()

    # Strategy 1: Look for exact "{label}_id" match
    expected_key = f"{label_lower}_id"
    if expected_key in properties:
        return expected_key

    # Strategy 2: Look for just "id"
    if "id" in properties:
        return "id"

    # Strategy 3: Look for any column ending with "_id"
    for prop in properties:
        if prop.endswith("_id"):
            return prop

    # Strategy 4: Fallback to first column
    logger.warning(f"[GRAPH_BUILDER] No ID column found for {label}, using first column: {properties[0]}")
    return properties[0]




def create_constraint(label: str, unique_key: str) -> Dict[str, Any]:
    """
    Create uniqueness constraint for a node label.

    Constraints ensure:
    - No duplicate nodes with same unique_key value
    - MERGE operations are fast (automatic index)
    - Data integrity is maintained

    Args:
        label: Node label (e.g., "Supplier")
        unique_key: Property that must be unique (e.g., "supplier_id")

    Returns:
        {"status": "success"} or {"status": "error", "error_message": "..."}
    """
    constraint_name = f"{label}_{unique_key}_constraint"

    # Note: Cypher DDL doesn't support parameterization
    query = f"""
    CREATE CONSTRAINT `{constraint_name}` IF NOT EXISTS
    FOR (n:`{label}`)
    REQUIRE n.`{unique_key}` IS UNIQUE
    """

    logger.info(f"[GRAPH_BUILDER] Creating constraint: {constraint_name}")
    result = neo4j_client.send_query(query)

    if result["status"] == "error":
        logger.error(f"[GRAPH_BUILDER] Constraint creation failed: {result.get('error_message')}")

    return result


def create_all_constraints(kb_id: str, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create constraints for all node types with KB label prefixing.

    Args:
        kb_id: Knowledge base identifier for label prefixing
        nodes: List of node definitions from proposed_schema

    Returns:
        {"status": "success", "constraints_created": 3} or error
    """
    created = 0
    errors = []

    for node in nodes:
        label = f"{kb_id}_{node['label']}"
        properties = node.get("properties", [])

        if not properties:
            logger.warning(f"[GRAPH_BUILDER] Skipping {label} - no properties")
            continue

        # Detect which property should be unique (uses original label for heuristic)
        unique_key = detect_unique_key(properties, node["label"])

        result = create_constraint(label, unique_key)
        if result["status"] == "success":
            created += 1
        else:
            errors.append(f"{label}: {result.get('error_message')}")

    if errors:
        return {
            "status": "partial",
            "constraints_created": created,
            "errors": errors
        }

    return {
        "status": "success",
        "constraints_created": created
    }




def import_node_type(
    kb_id: str,
    node_def: Dict[str, Any],
    file_data: FileData
) -> Dict[str, Any]:
    """
    Import all nodes of one type from a CSV file with KB label prefixing.

    Uses UNWIND + MERGE pattern for efficient batch import.

    Args:
        kb_id: Knowledge base identifier for label prefixing
        node_def: Node definition from schema: {"label": "Supplier", "properties": [...]}
        file_data: FileData object containing the CSV data

    Returns:
        {"status": "success", "nodes_created": 50} or error
    """
    label = f"{kb_id}_{node_def['label']}"
    properties = node_def.get("properties", [])

    logger.info(f"[IMPORT_NODES] Starting import for {label} from {file_data.name}")

    if not properties:
        return {
            "status": "error",
            "error_message": f"No properties defined for {label}"
        }

    # Parse CSV content
    rows = parse_csv_content(file_data)
    if not rows:
        return {
            "status": "error",
            "error_message": f"No data rows found in {file_data.name}"
        }

    # Detect unique key (use original unprefixed label for heuristic)
    unique_key = detect_unique_key(properties, node_def["label"])

    # Build SET clause for all properties
    set_clauses = [f"n.`{prop}` = row['{prop}']" for prop in properties if prop in rows[0]]
    set_clause = ", ".join(set_clauses) if set_clauses else "n._imported = true"

    # Generate Cypher query with KB-prefixed label
    query = f"""
    UNWIND $rows AS row
    MERGE (n:`{label}` {{`{unique_key}`: row['{unique_key}']}})
    SET {set_clause}, n.kb_id = '{kb_id}'
    """

    logger.info(f"[GRAPH_BUILDER] Importing {len(rows)} {label} nodes from {file_data.name}")

    result = neo4j_client.send_query(query, {"rows": rows})

    if result["status"] == "success":
        return {
            "status": "success",
            "nodes_created": len(rows),
            "label": label
        }
    else:
        return result


def import_all_nodes(
    kb_id: str,
    nodes: List[Dict[str, Any]],
    files: List[FileData]
) -> Dict[str, Any]:
    """
    Import all node types from their corresponding files with KB label prefixing.

    Matches nodes to files by name heuristic:
    - "Supplier" node → looks for "supplier.csv" or "suppliers.csv"
    - "Part" node → looks for "part.csv" or "parts.csv"

    Args:
        kb_id: Knowledge base identifier for label prefixing
        nodes: List of node definitions from schema
        files: List of FileData objects

    Returns:
        {"status": "success", "nodes_imported": [...], "total_nodes": 250}
    """
    imported = []
    total_nodes = 0
    errors = []

    for node in nodes:
        label = node["label"]

        # Find matching file by original (unprefixed) label name
        file_data = find_file_for_node(label, files)
        if not file_data:
            errors.append(f"{label}: No matching file found")
            logger.warning(f"[GRAPH_BUILDER] No file found for node type: {label}")
            continue

        # Import nodes with KB prefix
        result = import_node_type(kb_id, node, file_data)

        if result["status"] == "success":
            count = result["nodes_created"]
            imported.append({"label": label, "count": count})
            total_nodes += count
            logger.info(f"[GRAPH_BUILDER] ✓ Imported {count} {label} nodes")
        else:
            errors.append(f"{label}: {result.get('error_message')}")

    return {
        "status": "success" if not errors else "partial",
        "nodes_imported": imported,
        "total_nodes": total_nodes,
        "errors": errors
    }


def find_file_for_node(label: str, files: List[FileData]) -> Optional[FileData]:
    """
    Find the file that corresponds to a node type.

    Matching logic:
    - "Supplier" matches "suppliers.csv", "supplier.csv", "Suppliers.csv"
    - "Factory" matches "factories.csv", "factory.csv"
    - "Supply Chain" matches "supply_chain.csv"
    - Case-insensitive, handles irregular plurals

    Args:
        label: Node label (e.g., "Supplier", "Factory", "Supply Chain")
        files: List of available files

    Returns:
        Matching FileData or None
    """
    # Normalize label: lowercase, replace spaces with underscores
    label_normalized = label.lower().replace(' ', '_')

    # Generate plural variations
    plurals = []

    # Regular plural: add 's'
    plurals.append(label_normalized + 's')

    # Irregular plurals
    if label_normalized.endswith('y'):
        # factory → factories, supply → supplies
        plurals.append(label_normalized[:-1] + 'ies')
    if label_normalized.endswith('s'):
        # process → processes
        plurals.append(label_normalized + 'es')

    for file_data in files:
        # Normalize filename: lowercase, remove extension
        file_name_lower = file_data.name.lower().replace('.csv', '').replace('.json', '').replace('.xlsx', '')

        # Try exact match
        if file_name_lower == label_normalized:
            return file_data

        # Try plural variations
        for plural in plurals:
            if file_name_lower == plural:
                return file_data

        # Try stripping ALL separators (underscores, hyphens, spaces) from both sides
        # Handles: label "Tradebook KE8209 EQ" → "tradebookke8209eq"
        #          file  "tradebook-KE8209-EQ"  → "tradebookke8209eq"
        file_name_no_sep = file_name_lower.replace('_', '').replace('-', '')
        label_no_sep = label_normalized.replace('_', '').replace('-', '')

        if file_name_no_sep == label_no_sep:
            return file_data

    return None




def import_relationship_type(
    kb_id: str,
    rel_def: Dict[str, Any],
    files: List[FileData]
) -> Dict[str, Any]:
    """
    Create relationships between existing nodes with KB label/type prefixing.

    Relationships are inferred from foreign key columns in the CSV data.
    Example: If Part has "supplier_id" column, create (kb_xxx_Supplier)-[:kb_xxx_SUPPLIES]->(kb_xxx_Part)

    Args:
        kb_id: Knowledge base identifier for label/type prefixing
        rel_def: Relationship definition:
            {
                "type": "SUPPLIES",
                "from": "Supplier",
                "to": "Part",
                "via_column": "supplier_id"
            }
        files: List of FileData objects

    Returns:
        {"status": "success", "relationships_created": 200}
    """
    rel_type = f"{kb_id}_{rel_def['type']}"
    from_label = f"{kb_id}_{rel_def['from']}"
    to_label = f"{kb_id}_{rel_def['to']}"
    via_column = rel_def.get("via_column")

    if not via_column:
        return {
            "status": "error",
            "error_message": f"No via_column specified for {rel_type}"
        }

    # Find the file using original (unprefixed) label
    to_file = find_file_for_node(rel_def["to"], files)
    if not to_file:
        return {
            "status": "error",
            "error_message": f"No file found for {rel_def['to']} nodes"
        }

    # Parse data
    rows = parse_csv_content(to_file)
    if not rows:
        return {
            "status": "error",
            "error_message": f"No data in {to_file.name}"
        }

    # Detect unique keys (use original unprefixed label for heuristic)
    from_key = via_column  # The foreign key column
    to_key = detect_unique_key(list(rows[0].keys()), rel_def["to"])

    # Build relationship data
    rel_rows = []
    for row in rows:
        if via_column in row and to_key in row:
            rel_rows.append({
                "from_id": row[via_column],
                "to_id": row[to_key]
            })

    if not rel_rows:
        logger.warning(f"[GRAPH_BUILDER] No relationships to create for {rel_type}")
        return {"status": "success", "relationships_created": 0}

    # Generate Cypher
    query = f"""
    UNWIND $rows AS row
    MATCH (from_node:`{from_label}` {{`{via_column}`: row['from_id']}})
    MATCH (to_node:`{to_label}` {{`{to_key}`: row['to_id']}})
    MERGE (from_node)-[r:`{rel_type}`]->(to_node)
    """

    logger.info(f"[GRAPH_BUILDER] Creating {len(rel_rows)} {rel_type} relationships")

    result = neo4j_client.send_query(query, {"rows": rel_rows})

    if result["status"] == "success":
        return {
            "status": "success",
            "relationships_created": len(rel_rows),
            "type": rel_type
        }
    else:
        return result


def import_all_relationships(
    kb_id: str,
    relationships: List[Dict[str, Any]],
    files: List[FileData]
) -> Dict[str, Any]:
    """
    Import all relationship types with KB label/type prefixing.

    Args:
        kb_id: Knowledge base identifier for label/type prefixing
        relationships: List of relationship definitions from schema
        files: List of FileData objects

    Returns:
        {"status": "success", "relationships_imported": [...], "total_relationships": 500}
    """
    imported = []
    total_rels = 0
    errors = []

    for rel in relationships:
        rel_type = rel["type"]

        result = import_relationship_type(kb_id, rel, files)

        if result["status"] == "success":
            count = result.get("relationships_created", 0)
            imported.append({"type": rel_type, "count": count})
            total_rels += count
            logger.info(f"[GRAPH_BUILDER] ✓ Created {count} {rel_type} relationships")
        else:
            errors.append(f"{rel_type}: {result.get('error_message')}")

    return {
        "status": "success" if not errors else "partial",
        "relationships_imported": imported,
        "total_relationships": total_rels,
        "errors": errors
    }




def build_lexical_graph(kb_id: str, files: List[FileData]) -> Dict[str, Any]:
    """
    Build lexical graph from unstructured files (PDFs, text documents) with KB isolation.

    Creates KB-prefixed Chunk nodes with embeddings for semantic search.

    Args:
        kb_id: Knowledge base identifier for label prefixing
        files: List of FileData objects (only PDF/text files processed)

    Returns:
        {
            "status": "success",
            "chunks_created": 150,
            "files_processed": 2
        }
    """
    from app.services.embedding_service import generate_embeddings
    from app.services.vector_index_service import create_vector_index

    logger.info("[LEXICAL_GRAPH] ========== Building lexical graph ==========")

    # Filter unstructured files (have chunks)
    unstructured_files = [f for f in files if f.chunks and len(f.chunks) > 0]

    if not unstructured_files:
        logger.info("[LEXICAL_GRAPH] No unstructured files to process")
        return {
            "status": "success",
            "chunks_created": 0,
            "files_processed": 0
        }

    logger.info(f"[LEXICAL_GRAPH] Processing {len(unstructured_files)} unstructured files")

    # Collect all chunks with metadata
    all_chunk_data = []
    for file_data in unstructured_files:
        for idx, chunk_text in enumerate(file_data.chunks):
            all_chunk_data.append({
                "text": chunk_text,
                "source": file_data.name,
                "chunk_index": idx,
                "file_id": file_data.id
            })

    total_chunks = len(all_chunk_data)
    logger.info(f"[LEXICAL_GRAPH] Total chunks to embed: {total_chunks}")

    # Generate embeddings for all chunks
    try:
        chunk_texts = [c["text"] for c in all_chunk_data]
        embeddings = generate_embeddings(chunk_texts)

        # Add embeddings to chunk data
        for i, chunk_data in enumerate(all_chunk_data):
            chunk_data["embedding"] = embeddings[i]
            chunk_data["id"] = f"{chunk_data['file_id']}_chunk_{chunk_data['chunk_index']}"

    except Exception as e:
        logger.error(f"[LEXICAL_GRAPH] Embedding generation failed: {e}")
        return {
            "status": "error",
            "error_message": f"Embedding generation failed: {str(e)}"
        }

    # Create KB-specific vector index (idempotent)
    index_result = create_vector_index(kb_id)
    if index_result["status"] == "error":
        return index_result

    # Import Chunk nodes into Neo4j with KB-prefixed label
    chunk_label = f"{kb_id}_Chunk"
    query = f"""
    UNWIND $chunks AS chunk
    MERGE (c:{chunk_label} {{id: chunk.id}})
    SET c.text = chunk.text,
        c.source = chunk.source,
        c.chunk_index = chunk.chunk_index,
        c.file_id = chunk.file_id,
        c.embedding = chunk.embedding,
        c.kb_id = '{kb_id}'
    """

    result = neo4j_client.send_query(query, {"chunks": all_chunk_data})

    if result["status"] == "error":
        logger.error(f"[LEXICAL_GRAPH] Failed to import chunks: {result.get('error_message')}")
        return result

    logger.info(f"[LEXICAL_GRAPH] ✓ Created {total_chunks} Chunk nodes with embeddings")
    logger.info("[LEXICAL_GRAPH] ========== Lexical graph complete ==========")

    return {
        "status": "success",
        "chunks_created": total_chunks,
        "files_processed": len(unstructured_files)
    }


def build_subject_graph(kb_id: str, files: List[FileData]) -> Dict[str, Any]:
    """
    Phase 5: Build subject graph using NER with KB isolation.

    Extracts entities from KB-prefixed Chunk nodes and creates:
    - KB-prefixed Entity nodes
    - KB-prefixed MENTIONS relationships (Chunk → Entity)

    Args:
        kb_id: Knowledge base identifier for label prefixing
        files: List of FileData objects (must have chunks)

    Returns:
        {
            "status": "success",
            "entities_created": 42,
            "mentions_created": 89,
            "chunks_processed": 50
        }
    """
    from app.services.entity_extraction_service import extract_entities_batch

    logger.info(f"[GRAPH_BUILDER] Building subject graph (NER) for KB: {kb_id}")

    # Query KB-prefixed Chunk nodes
    chunk_label = f"{kb_id}_Chunk"
    query_chunks = f"""
    MATCH (c:{chunk_label})
    RETURN c.id as id, c.text as text
    """

    result = neo4j_client.send_query(query_chunks)

    if result.get("status") == "error":
        logger.error(f"[GRAPH_BUILDER] Failed to query chunks: {result.get('error_message')}")
        return result

    chunks = result.get("query_result", [])

    if not chunks or len(chunks) == 0:
        logger.info("[GRAPH_BUILDER] No chunks found for NER")
        return {
            "status": "success",
            "entities_created": 0,
            "mentions_created": 0,
            "chunks_processed": 0
        }

    logger.info(f"[GRAPH_BUILDER] Found {len(chunks)} chunks for entity extraction")

    # Extract entities from chunks
    extraction_result = extract_entities_batch(chunks, max_chunks=50)

    if extraction_result.get("status") == "error":
        return extraction_result

    entities = extraction_result.get("entities", [])
    logger.info(f"[GRAPH_BUILDER] Extracted {len(entities)} unique entities")

    if len(entities) == 0:
        return {
            "status": "success",
            "entities_created": 0,
            "mentions_created": 0,
            "chunks_processed": extraction_result.get("chunks_processed", 0)
        }

    # Import entities to Neo4j with KB-prefixed labels
    entity_label = f"{kb_id}_Entity"
    mentions_type = f"{kb_id}_MENTIONS"
    import_query = f"""
    UNWIND $entities as entity

    // Create KB-prefixed Entity node
    MERGE (e:{entity_label} {{name: entity.entity_text}})
    ON CREATE SET
        e.type = entity.entity_type,
        e.kb_id = '{kb_id}',
        e.created_at = timestamp()

    // Create KB-prefixed MENTIONS relationships to chunks
    WITH e, entity
    UNWIND entity.chunk_ids as chunk_id
    MATCH (c:{chunk_label} {{id: chunk_id}})
    MERGE (c)-[:{mentions_type}]->(e)

    RETURN count(DISTINCT e) as entities_created,
           count(*) as mentions_created
    """

    import_result = neo4j_client.send_query(import_query, {"entities": entities})

    if import_result.get("status") == "error":
        logger.error(f"[GRAPH_BUILDER] Failed to import entities: {import_result.get('error_message')}")
        return import_result

    summary = import_result.get("query_result", [{}])[0]

    logger.info(f"[GRAPH_BUILDER] ✓ Created {summary.get('entities_created', 0)} Entity nodes")
    logger.info(f"[GRAPH_BUILDER] ✓ Created {summary.get('mentions_created', 0)} MENTIONS relationships")

    return {
        "status": "success",
        "entities_created": summary.get("entities_created", 0),
        "mentions_created": summary.get("mentions_created", 0),
        "chunks_processed": extraction_result.get("chunks_processed", 0)
    }


def build_entity_resolution(kb_id: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 6: Entity Resolution with KB isolation - Match text entities to domain nodes.

    Creates KB-prefixed CORRESPONDS_TO relationships between Entity and domain nodes.

    Example:
        kb_xxx_Entity("Acme Corp") -[kb_xxx_CORRESPONDS_TO]-> kb_xxx_Supplier(name="Acme Corporation")

    Args:
        kb_id: Knowledge base identifier for label prefixing
        schema: Graph schema with node labels

    Returns:
        {
            "status": "success",
            "matches_found": 12,
            "correspondences_created": 12
        }
    """
    from app.services.entity_resolution_service import resolve_entities

    logger.info(f"[GRAPH_BUILDER] Building entity resolution for KB: {kb_id}")

    entity_label = f"{kb_id}_Entity"

    # Query KB-prefixed Entity nodes
    query_entities = f"""
    MATCH (e:{entity_label})
    RETURN e.name as name, e.type as type
    """

    entity_result = neo4j_client.send_query(query_entities)

    if entity_result.get("status") == "error":
        logger.error(f"[GRAPH_BUILDER] Failed to query entities: {entity_result.get('error_message')}")
        return entity_result

    entities = entity_result.get("query_result", [])

    if not entities or len(entities) == 0:
        logger.info("[GRAPH_BUILDER] No entities found for resolution")
        return {
            "status": "success",
            "matches_found": 0,
            "correspondences_created": 0
        }

    logger.info(f"[GRAPH_BUILDER] Found {len(entities)} Entity nodes")

    # Query all domain nodes (Supplier, Part, Factory, etc.)
    # Get node labels from schema
    node_labels = [node["label"] for node in schema.get("nodes", [])]

    if not node_labels:
        logger.info("[GRAPH_BUILDER] No domain node labels in schema")
        return {
            "status": "success",
            "matches_found": 0,
            "correspondences_created": 0
        }

    # Build query to get all KB-prefixed domain nodes
    label_clauses = " UNION ".join([
        f"MATCH (n:{kb_id}_{label}) RETURN '{label}' as label, n.name as name"
        for label in node_labels
    ])

    domain_result = neo4j_client.send_query(label_clauses)

    if domain_result.get("status") == "error":
        logger.error(f"[GRAPH_BUILDER] Failed to query domain nodes: {domain_result.get('error_message')}")
        return domain_result

    domain_nodes = domain_result.get("query_result", [])
    logger.info(f"[GRAPH_BUILDER] Found {len(domain_nodes)} domain nodes")

    if not domain_nodes:
        logger.info("[GRAPH_BUILDER] No domain nodes to match against")
        return {
            "status": "success",
            "matches_found": 0,
            "correspondences_created": 0
        }

    # Perform entity resolution
    matches = resolve_entities(entities, domain_nodes, threshold=0.85)

    if not matches or len(matches) == 0:
        logger.info("[GRAPH_BUILDER] No matches found above threshold")
        return {
            "status": "success",
            "matches_found": 0,
            "correspondences_created": 0
        }

    logger.info(f"[GRAPH_BUILDER] Found {len(matches)} entity-domain matches")

    # Create CORRESPONDS_TO relationships in Neo4j
    # Group matches by domain label for efficient querying
    matches_by_label = {}
    for match in matches:
        label = match["domain_label"]
        if label not in matches_by_label:
            matches_by_label[label] = []
        matches_by_label[label].append(match)

    total_correspondences = 0

    # Create relationships for each label group (with KB prefixes)
    corresponds_type = f"{kb_id}_CORRESPONDS_TO"
    for label, label_matches in matches_by_label.items():
        prefixed_label = f"{kb_id}_{label}"
        create_query = f"""
        UNWIND $matches as match

        MATCH (e:{entity_label} {{name: match.entity_name}})
        MATCH (d:{prefixed_label} {{name: match.domain_name}})

        MERGE (e)-[r:{corresponds_type}]->(d)
        ON CREATE SET r.confidence = match.score

        RETURN count(*) as correspondences_created
        """

        create_result = neo4j_client.send_query(create_query, {"matches": label_matches})

        if create_result.get("status") == "error":
            logger.error(f"[GRAPH_BUILDER] Failed to create correspondences for {label}: {create_result.get('error_message')}")
            continue

        count = create_result.get("query_result", [{}])[0].get("correspondences_created", 0)
        total_correspondences += count

    logger.info(f"[GRAPH_BUILDER] ✓ Created {total_correspondences} CORRESPONDS_TO relationships")

    return {
        "status": "success",
        "matches_found": len(matches),
        "correspondences_created": total_correspondences
    }


def build_graph(
    kb_id: str,
    schema: Dict[str, Any],
    files: List[FileData]
) -> Dict[str, Any]:
    """
    Main function to build the complete knowledge graph with KB isolation.

    Multi-phase process:
    1. Create uniqueness constraints (ensures data integrity)
    2. Import all nodes (creates vertices)
    3. Import all relationships (creates edges)
    4. Build lexical graph (chunk text, create embeddings)
    5. Build subject graph (extract entities via NER)
    6. Build entity resolution (match entities to domain nodes)

    Args:
        kb_id: Knowledge base identifier for label prefixing (e.g., "kb_a3f2c8e9")
        schema: The approved schema from proposed_schema:
            {
                "nodes": [{"label": "Supplier", "properties": [...]}, ...],
                "relationships": [{"type": "SUPPLIES", "from": "Supplier", ...}, ...]
            }
        files: List of FileData objects with CSV content

    Returns:
        {
            "status": "success",
            "nodes_imported": [{"label": "Supplier", "count": 50}, ...],
            "relationships_imported": [{"type": "SUPPLIES", "count": 200}, ...],
            "total_nodes": 750,
            "total_relationships": 700,
            "chunks_created": 89,
            "entities_created": 42
        }
    """
    logger.info(f"[GRAPH_BUILDER] ========== Starting graph construction for KB: {kb_id} ==========")

    nodes = schema.get("nodes", [])
    relationships = schema.get("relationships", [])

    # Phase 1: Create constraints (with KB prefix)
    logger.info("[GRAPH_BUILDER] Phase 1: Creating constraints")
    constraint_result = create_all_constraints(kb_id, nodes)
    if constraint_result["status"] == "error":
        return constraint_result

    logger.info(f"[GRAPH_BUILDER] ✓ Created {constraint_result['constraints_created']} constraints")

    # Phase 2: Import nodes (with KB prefix)
    logger.info("[GRAPH_BUILDER] Phase 2: Importing nodes")
    node_result = import_all_nodes(kb_id, nodes, files)
    if node_result["status"] == "error":
        return node_result

    logger.info(f"[GRAPH_BUILDER] ✓ Imported {node_result['total_nodes']} total nodes")

    # Phase 3: Import relationships (with KB prefix)
    logger.info("[GRAPH_BUILDER] Phase 3: Creating relationships")
    rel_result = import_all_relationships(kb_id, relationships, files)

    logger.info(f"[GRAPH_BUILDER] ✓ Created {rel_result['total_relationships']} total relationships")

    # Phase 4: Build lexical graph (if PDF/text files exist)
    logger.info("[GRAPH_BUILDER] Phase 4: Building lexical graph")
    lexical_result = build_lexical_graph(kb_id, files)

    if lexical_result.get("chunks_created", 0) > 0:
        logger.info(f"[GRAPH_BUILDER] ✓ Created {lexical_result['chunks_created']} Chunk nodes")
    else:
        logger.info("[GRAPH_BUILDER] No unstructured files to process")

    # Phase 5: Build subject graph (NER on chunks)
    logger.info("[GRAPH_BUILDER] Phase 5: Building subject graph (NER)")
    subject_result = build_subject_graph(kb_id, files)

    if subject_result.get("entities_created", 0) > 0:
        logger.info(f"[GRAPH_BUILDER] ✓ Created {subject_result['entities_created']} Entity nodes")
        logger.info(f"[GRAPH_BUILDER] ✓ Created {subject_result['mentions_created']} MENTIONS relationships")
    else:
        logger.info("[GRAPH_BUILDER] No entities extracted (no chunks to process)")

    # Phase 6: Entity resolution (match entities to domain nodes)
    logger.info("[GRAPH_BUILDER] Phase 6: Building entity resolution")
    resolution_result = build_entity_resolution(kb_id, schema)

    if resolution_result.get("correspondences_created", 0) > 0:
        logger.info(f"[GRAPH_BUILDER] ✓ Created {resolution_result['correspondences_created']} CORRESPONDS_TO relationships")
        logger.info(f"[GRAPH_BUILDER] ✓ Matched {resolution_result['matches_found']} entities to domain nodes")
    else:
        logger.info("[GRAPH_BUILDER] No entity matches found (threshold not met)")

    # Combine results
    all_errors = []
    if node_result.get("errors"):
        all_errors.extend(node_result["errors"])
    if rel_result.get("errors"):
        all_errors.extend(rel_result["errors"])
    if lexical_result.get("status") == "error":
        all_errors.append(f"Lexical: {lexical_result.get('error_message')}")
    if subject_result.get("status") == "error":
        all_errors.append(f"Subject: {subject_result.get('error_message')}")
    if resolution_result.get("status") == "error":
        all_errors.append(f"Resolution: {resolution_result.get('error_message')}")

    final_result = {
        "status": "success" if not all_errors else "partial",
        "nodes_imported": node_result["nodes_imported"],
        "relationships_imported": rel_result["relationships_imported"],
        "total_nodes": node_result["total_nodes"],
        "total_relationships": rel_result["total_relationships"],
        "chunks_created": lexical_result.get("chunks_created", 0),
        "lexical_files": lexical_result.get("files_processed", 0),
        "entities_created": subject_result.get("entities_created", 0),
        "mentions_created": subject_result.get("mentions_created", 0),
        "correspondences_created": resolution_result.get("correspondences_created", 0),
        "entity_matches": resolution_result.get("matches_found", 0)
    }

    if all_errors:
        final_result["errors"] = all_errors

    logger.info("[GRAPH_BUILDER] ========== Graph construction complete ==========")

    return final_result
