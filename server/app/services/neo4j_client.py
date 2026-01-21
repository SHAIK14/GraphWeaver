import atexit
from functools import lru_cache
from typing import Any, Dict, Optional

from neo4j import GraphDatabase, Result
from neo4j.graph import Node, Relationship, Path
import neo4j.time

from app.core.config import get_settings


def tool_success(key: str, result: Any) -> Dict[str, Any]:
    return {
        "status": "success",
        key: result,
    }


def tool_error(message: str) -> Dict[str, Any]:
    return {
        "status": "error",
        "error_message": message,
    }


def to_python(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: to_python(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [to_python(v) for v in value]
    elif isinstance(value, Node):
        return {
            "id": value.id,
            "labels": list(value.labels),
            "properties": to_python(dict(value)),
        }
    elif isinstance(value, Relationship):
        return {
            "id": value.id,
            "type": value.type,
            "start_node": value.start_node.id,
            "end_node": value.end_node.id,
            "properties": to_python(dict(value)),
        }
    elif isinstance(value, Path):
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


def result_to_app(result: Result) -> Dict[str, Any]:
    eager = result.to_eager_result()
    records = [to_python(record.data()) for record in eager.records]
    return tool_success("query_result", records)


class Neo4jClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._database_name = getattr(settings, "neo4j_database", settings.neo4j_username)
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )

    def close(self) -> None:
        self._driver.close()

    def send_query(
        self,
        cypher_query: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        session = self._driver.session()
        try:
            result = session.run(
                cypher_query,
                parameters or {},
                database_=self._database_name,
            )
            return result_to_app(result)
        except Exception as exc:
            return tool_error(str(exc))
        finally:
            session.close()


@lru_cache(maxsize=1)
def get_neo4j_client() -> Neo4jClient:
    client = Neo4jClient()
    atexit.register(client.close)
    return client