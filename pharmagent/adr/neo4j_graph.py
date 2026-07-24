"""Neo4j live graph queries for SIDER/MedDRA data."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pharmagent.adr.schemas import (
    DrugSideEffectsRequest,
    GraphExpandRequest,
    Neo4jNode,
    Neo4jQueryRequest,
    Neo4jQueryResponse,
    Neo4jRelationship,
    Neo4jStatus,
)
from pharmagent.runtime_config import load_runtime_config


class Neo4jConfigurationError(RuntimeError):
    """Raised when Neo4j is not configured or the driver is unavailable."""


def neo4j_status(driver_factory: Callable[..., Any] | None = None) -> Neo4jStatus:
    config = load_runtime_config().neo4j
    configured = bool(config.uri and config.username and config.password)
    if not configured:
        return Neo4jStatus(
            configured=False,
            connected=False,
            uri=config.uri,
            database=config.database,
            error="Neo4j password 未配置；请先在系统配置页配置真实 Neo4j 连接。",
        )

    try:
        with _driver(driver_factory) as driver:
            with driver.session(database=config.database) as session:
                result = session.run(
                    "MATCH (n) WITH count(n) AS nodes MATCH ()-[r]->() "
                    "RETURN nodes, count(r) AS relationships"
                ).single()
                return Neo4jStatus(
                    configured=True,
                    connected=True,
                    uri=config.uri,
                    database=config.database,
                    node_count=int(result["nodes"]) if result else 0,
                    relationship_count=int(result["relationships"]) if result else 0,
                )
    except Exception as exc:  # noqa: BLE001
        return Neo4jStatus(
            configured=True,
            connected=False,
            uri=config.uri,
            database=config.database,
            error=str(exc),
        )


def query_neo4j(
    req: Neo4jQueryRequest,
    driver_factory: Callable[..., Any] | None = None,
) -> Neo4jQueryResponse:
    _validate_readonly_cypher(req.cypher)
    cypher = f"{req.cypher.rstrip()} LIMIT $medguard_limit"
    return _run_query(cypher, {**req.parameters, "medguard_limit": _limit(req.limit)}, driver_factory)


def drug_side_effects(
    req: DrugSideEffectsRequest,
    driver_factory: Callable[..., Any] | None = None,
) -> Neo4jQueryResponse:
    drug = req.drug.strip()
    if not drug:
        raise ValueError("drug 不能为空")
    cypher = """
MATCH (d:Drug)-[r:HAS_SIDE_EFFECT]->(s)
WHERE toLower(d.name) CONTAINS toLower($drug) OR toLower(d.cid) = toLower($drug)
RETURN d, r, s, d.name AS drug_name, s.term AS side_effect, r.frequency AS frequency
ORDER BY coalesce(r.frequency, 0) DESC
LIMIT $medguard_limit
"""
    return _run_query(cypher, {"drug": drug, "medguard_limit": _limit(req.limit)}, driver_factory)


def expand_graph(
    req: GraphExpandRequest,
    driver_factory: Callable[..., Any] | None = None,
) -> Neo4jQueryResponse:
    node_id = req.node_id.strip()
    if not node_id:
        raise ValueError("node_id 不能为空")
    depth = max(1, min(req.depth, 2))
    rel_filter = ""
    params: dict[str, str | int | float | bool | None | list[str]] = {
        "node_id": node_id,
        "medguard_limit": _limit(req.limit),
    }
    if req.relationship_types:
        rel_filter = "WHERE type(r) IN $relationship_types"
        params["relationship_types"] = req.relationship_types
    cypher = f"""
MATCH (start)
WHERE elementId(start) = $node_id OR start.cid = $node_id OR start.cui = $node_id
MATCH path=(start)-[r*1..{depth}]-(neighbor)
UNWIND relationships(path) AS rel
WITH start, neighbor, rel
{rel_filter}
RETURN start, rel, neighbor
LIMIT $medguard_limit
"""
    return _run_query(cypher, params, driver_factory)


def _run_query(
    cypher: str,
    parameters: dict[str, Any],
    driver_factory: Callable[..., Any] | None,
) -> Neo4jQueryResponse:
    config = load_runtime_config().neo4j
    if not config.password:
        raise Neo4jConfigurationError("Neo4j password 未配置；不会回退到 demo 图谱。")

    nodes: dict[str, Neo4jNode] = {}
    relationships: dict[str, Neo4jRelationship] = {}
    rows: list[dict[str, object]] = []
    with _driver(driver_factory) as driver:
        with driver.session(database=config.database) as session:
            for record in session.run(cypher, parameters):
                row = {}
                for key, value in record.items():
                    converted = _convert_value(value, nodes, relationships)
                    row[key] = converted
                rows.append(row)
    return Neo4jQueryResponse(
        cypher=cypher,
        rows=rows,
        nodes=list(nodes.values()),
        relationships=list(relationships.values()),
    )


def _driver(driver_factory: Callable[..., Any] | None = None):
    config = load_runtime_config().neo4j
    if driver_factory is not None:
        return driver_factory(config.uri, auth=(config.username, config.password))
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise Neo4jConfigurationError("未安装 neo4j Python driver，请安装依赖后再连接真实图数据库。") from exc
    return GraphDatabase.driver(config.uri, auth=(config.username, config.password))


def _validate_readonly_cypher(cypher: str) -> None:
    text = cypher.strip()
    if not text:
        raise ValueError("cypher 不能为空")
    lowered = text.lower()
    if not lowered.startswith(("match", "with", "return", "call db.", "call apoc.meta.")):
        raise ValueError("仅允许只读 Cypher 查询。")
    blocked = (" create ", " merge ", " delete ", " detach ", " set ", " remove ", " drop ", " load csv")
    padded = f" {lowered} "
    if any(token in padded for token in blocked):
        raise ValueError("仅允许只读 Cypher 查询，禁止写入或导入语句。")


def _convert_value(
    value: Any,
    nodes: dict[str, Neo4jNode],
    relationships: dict[str, Neo4jRelationship],
) -> object:
    if isinstance(value, list):
        return [_convert_value(item, nodes, relationships) for item in value]
    if isinstance(value, dict):
        return {str(key): _convert_value(item, nodes, relationships) for key, item in value.items()}
    labels = getattr(value, "labels", None)
    if labels is not None and hasattr(value, "items"):
        node = _node_from_neo4j(value)
        nodes[node.id] = node
        return node.model_dump()
    rel_type = getattr(value, "type", None)
    if rel_type is not None and hasattr(value, "items"):
        rel = _relationship_from_neo4j(value)
        relationships[f"{rel.source}->{rel.type}->{rel.target}"] = rel
        return rel.model_dump()
    if hasattr(value, "nodes") and hasattr(value, "relationships"):
        return {
            "nodes": [_convert_value(item, nodes, relationships) for item in value.nodes],
            "relationships": [_convert_value(item, nodes, relationships) for item in value.relationships],
        }
    return value


def _node_from_neo4j(value: Any) -> Neo4jNode:
    props = dict(value.items())
    node_id = str(getattr(value, "element_id", None) or props.get("cid") or props.get("cui") or id(value))
    return Neo4jNode(id=node_id, labels=sorted(str(label) for label in value.labels), properties=props)


def _relationship_from_neo4j(value: Any) -> Neo4jRelationship:
    props = dict(value.items())
    source = str(getattr(getattr(value, "start_node", None), "element_id", ""))
    target = str(getattr(getattr(value, "end_node", None), "element_id", ""))
    return Neo4jRelationship(source=source, target=target, type=str(value.type), properties=props)


def _limit(value: int) -> int:
    return max(1, min(value, 200))
