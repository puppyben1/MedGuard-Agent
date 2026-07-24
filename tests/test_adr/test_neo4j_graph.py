from __future__ import annotations

import pytest

from pharmagent.adr.neo4j_graph import (
    Neo4jConfigurationError,
    drug_side_effects,
    query_neo4j,
)
from pharmagent.adr.schemas import DrugSideEffectsRequest, Neo4jQueryRequest
from pharmagent.runtime_config import Neo4jRuntimeConfig, RuntimeConfig


class FakeNode:
    def __init__(self, element_id: str, labels: list[str], props: dict):
        self.element_id = element_id
        self.labels = labels
        self._props = props

    def items(self):
        return self._props.items()


class FakeRelationship:
    def __init__(self, source: FakeNode, target: FakeNode, rel_type: str, props: dict):
        self.start_node = source
        self.end_node = target
        self.type = rel_type
        self._props = props

    def items(self):
        return self._props.items()


class FakeRecord(dict):
    pass


class FakeSession:
    def __init__(self):
        self.cypher = ""
        self.parameters = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def run(self, cypher, parameters=None):
        self.cypher = cypher
        self.parameters = parameters or {}
        drug = FakeNode("d1", ["Drug"], {"cid": "CID1", "name": "warfarin"})
        side_effect = FakeNode("s1", ["SideEffect", "MedDRATerm"], {"cui": "C001", "term": "Bleeding"})
        rel = FakeRelationship(drug, side_effect, "HAS_SIDE_EFFECT", {"frequency": 0.21})
        return [FakeRecord({"d": drug, "r": rel, "s": side_effect, "drug_name": "warfarin"})]


class FakeDriver:
    def __init__(self):
        self.session_obj = FakeSession()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def session(self, database=None):
        return self.session_obj


def test_drug_side_effects_converts_neo4j_nodes(monkeypatch):
    monkeypatch.setattr(
        "pharmagent.adr.neo4j_graph.load_runtime_config",
        lambda: RuntimeConfig(neo4j=Neo4jRuntimeConfig(password="secret")),
    )

    response = drug_side_effects(
        DrugSideEffectsRequest(drug="warfarin", limit=5),
        driver_factory=lambda *_args, **_kwargs: FakeDriver(),
    )

    assert response.source_type == "neo4j_live"
    assert response.nodes[0].labels == ["Drug"]
    assert response.relationships[0].type == "HAS_SIDE_EFFECT"
    assert response.rows[0]["drug_name"] == "warfarin"


def test_query_neo4j_rejects_write_cypher(monkeypatch):
    monkeypatch.setattr(
        "pharmagent.adr.neo4j_graph.load_runtime_config",
        lambda: RuntimeConfig(neo4j=Neo4jRuntimeConfig(password="secret")),
    )

    with pytest.raises(ValueError):
        query_neo4j(Neo4jQueryRequest(cypher="MATCH (n) DELETE n"))


def test_query_neo4j_requires_password(monkeypatch):
    monkeypatch.setattr(
        "pharmagent.adr.neo4j_graph.load_runtime_config",
        lambda: RuntimeConfig(neo4j=Neo4jRuntimeConfig(password="")),
    )

    with pytest.raises(Neo4jConfigurationError):
        query_neo4j(Neo4jQueryRequest(cypher="MATCH (n) RETURN n"))
