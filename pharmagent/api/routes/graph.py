"""Live Neo4j graph query routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from pharmagent.adr.neo4j_graph import (
    Neo4jConfigurationError,
    drug_side_effects,
    expand_graph,
    neo4j_status,
    query_neo4j,
)
from pharmagent.adr.schemas import (
    DrugSideEffectsRequest,
    GraphExpandRequest,
    Neo4jQueryRequest,
    Neo4jQueryResponse,
    Neo4jStatus,
)

router = APIRouter()


@router.get("/graph/status", response_model=Neo4jStatus)
def get_graph_status() -> Neo4jStatus:
    return neo4j_status()


@router.post("/graph/query", response_model=Neo4jQueryResponse)
def graph_query(req: Neo4jQueryRequest) -> Neo4jQueryResponse:
    try:
        return query_neo4j(req)
    except (Neo4jConfigurationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Neo4j 查询失败：{exc}") from exc


@router.post("/graph/expand", response_model=Neo4jQueryResponse)
def graph_expand(req: GraphExpandRequest) -> Neo4jQueryResponse:
    try:
        return expand_graph(req)
    except (Neo4jConfigurationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Neo4j 扩展查询失败：{exc}") from exc


@router.post("/graph/drug-side-effects", response_model=Neo4jQueryResponse)
def graph_drug_side_effects(req: DrugSideEffectsRequest) -> Neo4jQueryResponse:
    try:
        return drug_side_effects(req)
    except (Neo4jConfigurationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Neo4j 药物副作用查询失败：{exc}") from exc
