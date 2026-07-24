"""Runtime API configuration saved outside git for demo and deployment use."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

CONFIG_PATH = Path("data/runtime/api_config.json")


class LLMRuntimeConfig(BaseModel):
    provider: Literal["groq", "openai_compatible"] = "openai_compatible"
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    router_model: str = "deepseek-chat"
    generator_model: str = "deepseek-chat"


class OpenFDARuntimeConfig(BaseModel):
    api_key: str = ""
    strict_real_data: bool = False


class Neo4jRuntimeConfig(BaseModel):
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = ""
    database: str = "neo4j"


class RAGRuntimeConfig(BaseModel):
    side_effect_zip_path: str = "data/incoming/adr_data.zip"
    require_real_sources: bool = True


class RuntimeConfig(BaseModel):
    llm: LLMRuntimeConfig = Field(default_factory=LLMRuntimeConfig)
    openfda: OpenFDARuntimeConfig = Field(default_factory=OpenFDARuntimeConfig)
    neo4j: Neo4jRuntimeConfig = Field(default_factory=Neo4jRuntimeConfig)
    rag: RAGRuntimeConfig = Field(default_factory=RAGRuntimeConfig)


class RuntimeConfigStatus(BaseModel):
    llm_provider: str
    llm_base_url: str
    router_model: str
    generator_model: str
    has_llm_api_key: bool
    has_openfda_api_key: bool
    strict_real_data: bool
    neo4j_uri: str
    neo4j_username: str
    neo4j_database: str
    has_neo4j_password: bool
    side_effect_zip_path: str
    side_effect_zip_available: bool
    require_real_sources: bool


class RuntimeConfigUpdate(BaseModel):
    llm_provider: Literal["groq", "openai_compatible"] | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    router_model: str | None = None
    generator_model: str | None = None
    openfda_api_key: str | None = None
    strict_real_data: bool | None = None
    neo4j_uri: str | None = None
    neo4j_username: str | None = None
    neo4j_password: str | None = None
    neo4j_database: str | None = None
    side_effect_zip_path: str | None = None
    require_real_sources: bool | None = None


def load_runtime_config() -> RuntimeConfig:
    if not CONFIG_PATH.exists():
        return RuntimeConfig()
    try:
        return RuntimeConfig.model_validate_json(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return RuntimeConfig()


def save_runtime_config(update: RuntimeConfigUpdate) -> RuntimeConfig:
    config = load_runtime_config()
    if update.llm_provider is not None:
        config.llm.provider = update.llm_provider
    if update.llm_api_key:
        config.llm.api_key = update.llm_api_key
    if update.llm_base_url is not None:
        config.llm.base_url = update.llm_base_url
    if update.router_model is not None:
        config.llm.router_model = update.router_model
    if update.generator_model is not None:
        config.llm.generator_model = update.generator_model
    if update.openfda_api_key:
        config.openfda.api_key = update.openfda_api_key
    if update.strict_real_data is not None:
        config.openfda.strict_real_data = update.strict_real_data
    if update.neo4j_uri is not None:
        config.neo4j.uri = update.neo4j_uri
    if update.neo4j_username is not None:
        config.neo4j.username = update.neo4j_username
    if update.neo4j_password:
        config.neo4j.password = update.neo4j_password
    if update.neo4j_database is not None:
        config.neo4j.database = update.neo4j_database
    if update.side_effect_zip_path is not None:
        config.rag.side_effect_zip_path = update.side_effect_zip_path
    if update.require_real_sources is not None:
        config.rag.require_real_sources = update.require_real_sources

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return config


def runtime_status(config: RuntimeConfig | None = None) -> RuntimeConfigStatus:
    config = config or load_runtime_config()
    return RuntimeConfigStatus(
        llm_provider=config.llm.provider,
        llm_base_url=config.llm.base_url,
        router_model=config.llm.router_model,
        generator_model=config.llm.generator_model,
        has_llm_api_key=bool(config.llm.api_key),
        has_openfda_api_key=bool(config.openfda.api_key),
        strict_real_data=config.openfda.strict_real_data,
        neo4j_uri=config.neo4j.uri,
        neo4j_username=config.neo4j.username,
        neo4j_database=config.neo4j.database,
        has_neo4j_password=bool(config.neo4j.password),
        side_effect_zip_path=config.rag.side_effect_zip_path,
        side_effect_zip_available=Path(config.rag.side_effect_zip_path).exists(),
        require_real_sources=config.rag.require_real_sources,
    )
