"""FastAPI application entry point for MedGuard-Agent.

Run with:
    uvicorn pharmagent.api.main:app --reload --port 8000

Exposes:
    GET  /api/health           — health check + budget status
    POST /api/prescription     — prescription review (case text → report)
    POST /api/qa               — drug safety QA (question → assessment)
    GET  /api/examples         — example cases / queries
    GET  /api/adr/examples     — ADR demo cases
    POST /api/adr/analyze      — end-to-end ADR analysis
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pharmagent.api.routes import adr, examples, prescription, qa
from pharmagent.logging_config import setup_logging

setup_logging("INFO")

app = FastAPI(
    title="MedGuard-Agent API",
    description="面向临床处方审查的医学智能体 — 证据约束的后端 API",
    version="0.3.0",
)

# CORS: allow the Vite dev server (5173) and any localhost origin during dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    """Health check + remaining LLM budget."""
    from pharmagent.agent.llm import budget_tracker

    return {
        "status": "ok",
        "generator_budget_remaining": budget_tracker.generator_budget_remaining,
        "router_budget_remaining": budget_tracker.router_budget_remaining,
    }


app.include_router(prescription.router, prefix="/api", tags=["prescription"])
app.include_router(qa.router, prefix="/api", tags=["qa"])
app.include_router(examples.router, prefix="/api", tags=["examples"])
app.include_router(adr.router, prefix="/api", tags=["adr"])
