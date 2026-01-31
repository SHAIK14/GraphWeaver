from typing import Any, Dict, Optional
from neo4j import GraphDatabase, Result
from neo4j.graph import Node, Relationship, Path
import neo4j.time

from app.core.config import settings


def to_python(value: Any) -> Any:
    """
    Convert Neo4j types to Python native types.
    
    Neo4j returns special types (Node, Relationship, DateTime)
    that aren't JSON serializable. This converts them.
    """
    if isinstance(value, dict):
        return {k: to_python(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [to_python(v) for v in value]
    elif isinstance(value, Node):
        # Node → {id, labels, properties}
        return {
            "id": value.element_id,
            "labels": list(value.labels),
            "properties": to_python(dict(value)),
        }
    elif isinstance(value, Relationship):
        # Relationship → {id, type, start, end, properties}
        return {
            "id": value.element_id,
            "type": value.type,
            "start_node": value.start_node.element_id,
            "end_node": value.end_node.element_id,
            "properties": to_python(dict(value)),
        }
    elif isinstance(value, Path):
        # Path → {nodes: [...], relationships: [...]}
        return {
            "nodes": [to_python(node) for node in value.nodes],
            "relationships": [to_python(rel) for rel in value.relationships],
        }
    elif isinstance(value, neo4j.time.DateTime):
        return value.iso_format()
    elif isinstance(value, (neo4j.time.Date, neo4j.time.Time, neo4j.time.Duration)):
        return str(value)
    else:
        return value


class Neo4jClient:
    """
    Simple Neo4j client for executing Cypher queries.
    
    Agents write their own Cypher queries and use send_query().
    """
    
    def __init__(self):
        # Create driver with connection pooling
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password)
        )
        self.database = settings.neo4j_database
    
    def close(self):
        """Close driver and all connections."""
        self.driver.close()
    
    def send_query(
        self,
        cypher_query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute Cypher query and return results.
        
        Args:
            cypher_query: Cypher query string
            parameters: Query parameters (prevents injection)
        
        Returns:
            {
                "status": "success",
                "query_result": [...results...]
            }
            OR
            {
                "status": "error",
                "error_message": "..."
            }
        
        Example:
            result = client.send_query(
                "MATCH (n:Person {name: $name}) RETURN n",
                {"name": "Alice"}
            )
            if result["status"] == "success":
                records = result["query_result"]
        """
        session = self.driver.session(database=self.database)
        try:
            # Execute query
            result = session.run(cypher_query, parameters or {})
            
            # Convert to eager result (fetches all data)
            eager = result.to_eager_result()
            
            # Convert Neo4j types to Python types
            records = [to_python(record.data()) for record in eager.records]
            
            return {
                "status": "success",
                "query_result": records
            }
        
        except Exception as e:
            return {
                "status": "error",
                "error_message": str(e)
            }
        
        finally:
            session.close()


# Singleton instance
neo4j_client = Neo4jClient()
