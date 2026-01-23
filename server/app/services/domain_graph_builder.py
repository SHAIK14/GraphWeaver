"""
Domain Graph Construction Service.



This service builds the domain graph from CSV files using the approved construction plan.
NO AGENT REQUIRED - this is purely rule-based execution of Cypher queries.

The construction plan from  (Schema Proposal) contains all the information
needed to import nodes and relationships into Neo4j.

Functions:
- create_uniqueness_constraint: Prevents duplicate nodes
- load_nodes_from_csv: Batch imports nodes from CSV
- import_nodes: Orchestrates node import (constraint + load)
- import_relationships: Creates edges between existing nodes
- construct_domain_graph: Main function that builds the complete graph
"""

from typing import Any, Dict, List
from app.services.neo4j_client import get_neo4j_client, tool_success, tool_error


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_uniqueness_constraint(
    label: str,
    unique_property_key: str,
) -> Dict[str, Any]:
    """
    Creates a uniqueness constraint for a node label and property key.

    Why we need this:
    - Prevents duplicate nodes with the same label and property value
    - Improves performance of MERGE operations during import
    - Ensures data integrity in the graph

    Args:
        label: The node label (e.g., "Supplier", "Part")
        unique_property_key: The property that must be unique (e.g., "supplier_id")

    Returns:
        Dict with status key ('success' or 'error')

    Example:
        create_uniqueness_constraint("Supplier", "supplier_id")
        # Creates: CONSTRAINT Supplier_supplier_id_constraint
    """
    client = get_neo4j_client()

    # Build constraint name from label and property
    constraint_name = f"{label}_{unique_property_key}_constraint"

    # Note: Neo4j doesn't support parameterization for DDL statements
    # So we use f-string formatting (safe here since values come from our code)
    query = f"""
    CREATE CONSTRAINT `{constraint_name}` IF NOT EXISTS
    FOR (n:`{label}`)
    REQUIRE n.`{unique_property_key}` IS UNIQUE
    """

    result = client.send_query(query)
    return result


def load_nodes_from_csv(
    source_file: str,
    label: str,
    unique_column_name: str,
    properties: List[str],
) -> Dict[str, Any]:
    """
    Batch loading of nodes from a CSV file into Neo4j.

    How it works:
    1. LOAD CSV reads the file from Neo4j's import directory
    2. MERGE creates node if it doesn't exist (based on unique column)
    3. FOREACH sets all additional properties
    4. IN TRANSACTIONS OF 1000 ROWS batches for performance

    Args:
        source_file: CSV filename (must be in Neo4j's import directory)
        label: Node label to create (e.g., "Supplier")
        unique_column_name: Column used to identify unique nodes
        properties: List of additional columns to import as properties

    Returns:
        Dict with status and query result

    Example:
        load_nodes_from_csv(
            "suppliers.csv",
            "Supplier",
            "supplier_id",
            ["name", "city", "country"]
        )
    """
    client = get_neo4j_client()

    # Build the Cypher query for batch node import
    # Using MERGE to avoid duplicates based on unique column
    query = f"""
    LOAD CSV WITH HEADERS FROM "file:///" + $source_file AS row
    CALL (row) {{
        MERGE (n:`{label}` {{ `{unique_column_name}`: row[$unique_column_name] }})
        FOREACH (k IN $properties | SET n[k] = row[k])
    }} IN TRANSACTIONS OF 1000 ROWS
    """

    result = client.send_query(query, {
        "source_file": source_file,
        "unique_column_name": unique_column_name,
        "properties": properties
    })

    return result


def import_nodes(node_construction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Import nodes as defined by a node construction rule.

    This function orchestrates the node import process:
    1. First creates a uniqueness constraint (for data integrity)
    2. Then loads nodes from the CSV file

    Args:
        node_construction: A node construction rule from the construction plan
            {
                "construction_type": "node",
                "source_file": "suppliers.csv",
                "label": "Supplier",
                "unique_column_name": "supplier_id",
                "properties": ["name", "city", "country"]
            }

    Returns:
        Dict with status and result
    """
    # Step 1: Create uniqueness constraint
    constraint_result = create_uniqueness_constraint(
        node_construction["label"],
        node_construction["unique_column_name"]
    )

    if constraint_result.get("status") == "error":
        return constraint_result

    # Step 2: Load nodes from CSV
    load_result = load_nodes_from_csv(
        node_construction["source_file"],
        node_construction["label"],
        node_construction["unique_column_name"],
        node_construction["properties"]
    )

    return load_result


def import_relationships(relationship_construction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Import relationships as defined by a relationship construction rule.

    How it works:
    1. LOAD CSV reads the source file
    2. MATCH finds the source node (from_node)
    3. MATCH finds the target node (to_node)
    4. MERGE creates the relationship between them
    5. FOREACH sets relationship properties

    IMPORTANT: Nodes must exist before relationships can be created.
    That's why construct_domain_graph imports nodes first.

    Args:
        relationship_construction: A relationship construction rule
            {
                "construction_type": "relationship",
                "source_file": "part_supplier_mapping.csv",
                "relationship_type": "SUPPLIED_BY",
                "from_node_label": "Part",
                "from_node_column": "part_id",
                "to_node_label": "Supplier",
                "to_node_column": "supplier_id",
                "properties": ["lead_time_days", "unit_cost"]
            }

    Returns:
        Dict with status and result
    """
    client = get_neo4j_client()

    from_node_column = relationship_construction["from_node_column"]
    to_node_column = relationship_construction["to_node_column"]
    from_node_label = relationship_construction["from_node_label"]
    to_node_label = relationship_construction["to_node_label"]
    relationship_type = relationship_construction["relationship_type"]

    # Build the Cypher query for relationship import
    query = f"""
    LOAD CSV WITH HEADERS FROM "file:///" + $source_file AS row
    CALL (row) {{
        MATCH (from_node:`{from_node_label}` {{ `{from_node_column}`: row[$from_node_column] }})
        MATCH (to_node:`{to_node_label}` {{ `{to_node_column}`: row[$to_node_column] }})
        MERGE (from_node)-[r:`{relationship_type}`]->(to_node)
        FOREACH (k IN $properties | SET r[k] = row[k])
    }} IN TRANSACTIONS OF 1000 ROWS
    """

    result = client.send_query(query, {
        "source_file": relationship_construction["source_file"],
        "from_node_column": from_node_column,
        "to_node_column": to_node_column,
        "properties": relationship_construction.get("properties", [])
    })

    return result


# =============================================================================
# MAIN CONSTRUCTION FUNCTION
# =============================================================================

def construct_domain_graph(construction_plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construct a domain graph according to a construction plan.

    This is the main orchestration function that builds the entire knowledge graph.
    It processes the construction plan in two phases:

    Phase 1 - Node Construction:
        Import all nodes first to ensure they exist before creating relationships.
        For each node rule: create constraint → load from CSV

    Phase 2 - Relationship Construction:
        Create relationships between existing nodes.
        For each relationship rule: match nodes → create relationship

    Args:
        construction_plan: The approved construction plan from Lesson 6
            {
                "Part": {"construction_type": "node", ...},
                "Supplier": {"construction_type": "node", ...},
                "SUPPLIED_BY": {"construction_type": "relationship", ...}
            }

    Returns:
        Dict with status, counts, and any errors

    Example:
        result = construct_domain_graph(approved_construction_plan)
        # Returns: {"status": "success", "nodes_imported": 3, "relationships_imported": 2}
    """
    results = {
        "nodes_imported": [],
        "relationships_imported": [],
        "errors": []
    }

    # Phase 1: Import all nodes first
    node_constructions = [
        (name, rule) for name, rule in construction_plan.items()
        if rule.get("construction_type") == "node"
    ]

    for name, node_construction in node_constructions:
        result = import_nodes(node_construction)
        if result.get("status") == "error":
            results["errors"].append({
                "name": name,
                "type": "node",
                "error": result.get("error_message")
            })
        else:
            results["nodes_imported"].append(name)

    # Phase 2: Import all relationships
    relationship_constructions = [
        (name, rule) for name, rule in construction_plan.items()
        if rule.get("construction_type") == "relationship"
    ]

    for name, relationship_construction in relationship_constructions:
        result = import_relationships(relationship_construction)
        if result.get("status") == "error":
            results["errors"].append({
                "name": name,
                "type": "relationship",
                "error": result.get("error_message")
            })
        else:
            results["relationships_imported"].append(name)

    # Build final response
    if results["errors"]:
        return {
            "status": "partial" if results["nodes_imported"] or results["relationships_imported"] else "error",
            "message": f"Imported {len(results['nodes_imported'])} node types and {len(results['relationships_imported'])} relationship types with {len(results['errors'])} errors",
            "nodes_imported": results["nodes_imported"],
            "relationships_imported": results["relationships_imported"],
            "errors": results["errors"]
        }

    return tool_success("construction_result", {
        "message": f"Successfully imported {len(results['nodes_imported'])} node types and {len(results['relationships_imported'])} relationship types",
        "nodes_imported": results["nodes_imported"],
        "relationships_imported": results["relationships_imported"]
    })


# =============================================================================
# INSPECTION FUNCTIONS
# =============================================================================

def get_graph_stats() -> Dict[str, Any]:
    """
    Get statistics about the current graph.

    Returns counts of nodes and relationships by type.
    """
    client = get_neo4j_client()

    # Get node counts by label
    node_query = """
    CALL db.labels() YIELD label
    CALL (label) {
        MATCH (n) WHERE label IN labels(n)
        RETURN count(n) AS count
    }
    RETURN label, count
    """

    # Get relationship counts by type
    rel_query = """
    CALL db.relationshipTypes() YIELD relationshipType
    CALL (relationshipType) {
        MATCH ()-[r]->() WHERE type(r) = relationshipType
        RETURN count(r) AS count
    }
    RETURN relationshipType, count
    """

    node_result = client.send_query(node_query)
    rel_result = client.send_query(rel_query)

    return {
        "status": "success",
        "nodes": node_result.get("query_result", []),
        "relationships": rel_result.get("query_result", [])
    }


def clear_graph() -> Dict[str, Any]:
    """
    Clear all nodes and relationships from the graph.

    WARNING: This is destructive! Use with caution.
    """
    client = get_neo4j_client()

    # Delete all nodes and relationships
    query = "MATCH (n) DETACH DELETE n"
    result = client.send_query(query)

    return tool_success("clear_result", "Graph cleared successfully")


# =============================================================================
# DIRECT DATA IMPORT (No CSV files needed - for testing)
# =============================================================================

def insert_sample_data() -> Dict[str, Any]:
    """
    Insert sample supplier/part data directly via Cypher.

    Use this for testing when CSV import is not available.
    This creates a small sample graph matching the course data structure.
    """
    client = get_neo4j_client()

    # Sample data matching course structure
    queries = [
        # Create Suppliers
        """
        UNWIND [
            {supplier_id: 'SUP001', name: 'Acme Electronics', specialty: 'Circuit Boards', city: 'San Jose', country: 'USA'},
            {supplier_id: 'SUP002', name: 'Global Steel', specialty: 'Metal Frames', city: 'Pittsburgh', country: 'USA'},
            {supplier_id: 'SUP003', name: 'PowerTech', specialty: 'Power Supplies', city: 'Shenzhen', country: 'China'}
        ] AS supplier
        MERGE (s:Supplier {supplier_id: supplier.supplier_id})
        SET s.name = supplier.name,
            s.specialty = supplier.specialty,
            s.city = supplier.city,
            s.country = supplier.country
        """,

        # Create Products
        """
        UNWIND [
            {product_id: 'PROD001', product_name: 'Industrial Robot Arm', price: '15000', description: 'Heavy-duty robotic arm for manufacturing'},
            {product_id: 'PROD002', product_name: 'Smart Sensor Array', price: '2500', description: 'Multi-sensor monitoring system'}
        ] AS product
        MERGE (p:Product {product_id: product.product_id})
        SET p.product_name = product.product_name,
            p.price = product.price,
            p.description = product.description
        """,

        # Create Assemblies
        """
        UNWIND [
            {assembly_id: 'ASM001', assembly_name: 'Control Unit', quantity: '1', product_id: 'PROD001'},
            {assembly_id: 'ASM002', assembly_name: 'Motor Assembly', quantity: '2', product_id: 'PROD001'},
            {assembly_id: 'ASM003', assembly_name: 'Sensor Module', quantity: '4', product_id: 'PROD002'}
        ] AS assembly
        MERGE (a:Assembly {assembly_id: assembly.assembly_id})
        SET a.assembly_name = assembly.assembly_name,
            a.quantity = assembly.quantity,
            a.product_id = assembly.product_id
        """,

        # Create Parts
        """
        UNWIND [
            {part_id: 'PRT001', part_name: 'Main Circuit Board', quantity: '1', assembly_id: 'ASM001'},
            {part_id: 'PRT002', part_name: 'Power Regulator', quantity: '2', assembly_id: 'ASM001'},
            {part_id: 'PRT003', part_name: 'Steel Frame', quantity: '1', assembly_id: 'ASM002'},
            {part_id: 'PRT004', part_name: 'Servo Motor', quantity: '3', assembly_id: 'ASM002'},
            {part_id: 'PRT005', part_name: 'Sensor Chip', quantity: '8', assembly_id: 'ASM003'}
        ] AS part
        MERGE (p:Part {part_id: part.part_id})
        SET p.part_name = part.part_name,
            p.quantity = part.quantity,
            p.assembly_id = part.assembly_id
        """,

        # Create Product -> Assembly relationships (Contains)
        """
        MATCH (p:Product), (a:Assembly)
        WHERE a.product_id = p.product_id
        MERGE (p)-[r:Contains]->(a)
        SET r.quantity = a.quantity
        """,

        # Create Part -> Assembly relationships (Is_Part_Of)
        """
        MATCH (part:Part), (a:Assembly)
        WHERE part.assembly_id = a.assembly_id
        MERGE (part)-[r:Is_Part_Of]->(a)
        SET r.quantity = part.quantity
        """,

        # Create Part -> Supplier relationships (Supplied_By)
        """
        UNWIND [
            {part_id: 'PRT001', supplier_id: 'SUP001', lead_time_days: '14', unit_cost: '250'},
            {part_id: 'PRT002', supplier_id: 'SUP003', lead_time_days: '21', unit_cost: '45'},
            {part_id: 'PRT003', supplier_id: 'SUP002', lead_time_days: '7', unit_cost: '180'},
            {part_id: 'PRT004', supplier_id: 'SUP001', lead_time_days: '30', unit_cost: '520'},
            {part_id: 'PRT005', supplier_id: 'SUP001', lead_time_days: '10', unit_cost: '35'}
        ] AS mapping
        MATCH (part:Part {part_id: mapping.part_id})
        MATCH (s:Supplier {supplier_id: mapping.supplier_id})
        MERGE (part)-[r:Supplied_By]->(s)
        SET r.lead_time_days = mapping.lead_time_days,
            r.unit_cost = mapping.unit_cost
        """
    ]

    errors = []
    for i, query in enumerate(queries):
        result = client.send_query(query)
        if result.get("status") == "error":
            errors.append(f"Query {i+1}: {result.get('error_message')}")

    if errors:
        return tool_error(f"Some queries failed: {errors}")

    return tool_success("insert_result", {
        "message": "Sample data inserted successfully",
        "nodes_created": ["Supplier (3)", "Product (2)", "Assembly (3)", "Part (5)"],
        "relationships_created": ["Contains (3)", "Is_Part_Of (5)", "Supplied_By (5)"]
    })
