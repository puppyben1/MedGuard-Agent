"""Centralized configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Groq
    groq_api_key: str = ""
    router_model: str = "llama-3.1-8b-instant"
    generator_model: str = "llama-3.3-70b-versatile"

    # Rate limits (requests per day)
    router_rpd_limit: int = 14_400
    generator_rpd_limit: int = 1_000

    # DeepSeek / OpenAI-compatible provider (used when GROQ_API_KEY is empty).
    # DeepSeek is OpenAI-compatible; set base_url to point at any compatible endpoint.
    deepseek_api_key: str = ""
    deepseek_api_base: str = "https://api.deepseek.com"
    deepseek_router_model: str = "deepseek-chat"
    deepseek_generator_model: str = "deepseek-chat"

    # ChromaDB
    chroma_persist_dir: str = "./data/chromadb"

    # BM25
    bm25_persist_dir: str = "./data/bm25"

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"

    # Retrieval
    hybrid_search_top_k: int = 20
    rerank_top_k: int = 10
    rrf_k: int = 60
    min_relevant_docs: int = 3
    max_rewrite_retries: int = 2

    # Grading
    faithfulness_threshold: float = 0.85

    # Langfuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"

    # openFDA
    openfda_api_key: str = ""


settings = Settings()
