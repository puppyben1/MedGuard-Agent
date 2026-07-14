"""Groq LLM wrappers with rate-limit-aware token budget tracking."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from langchain_groq import ChatGroq

from pharmagent.config import settings
from pharmagent.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class TokenBudgetTracker:
    """Track daily request counts against Groq free-tier limits."""

    router_limit: int = settings.router_rpd_limit
    generator_limit: int = settings.generator_rpd_limit
    _router_count: int = field(default=0, repr=False)
    _generator_count: int = field(default=0, repr=False)
    _day_start: float = field(default_factory=time.time, repr=False)

    def _maybe_reset(self) -> None:
        if time.time() - self._day_start > 86_400:
            self._router_count = 0
            self._generator_count = 0
            self._day_start = time.time()

    def record_router_call(self) -> None:
        self._maybe_reset()
        self._router_count += 1
        usage_pct = self._router_count / self.router_limit * 100
        if usage_pct >= 80:
            logger.warning(
                "router_budget_warning",
                used=self._router_count,
                limit=self.router_limit,
                pct=round(usage_pct, 1),
            )

    def record_generator_call(self) -> None:
        self._maybe_reset()
        self._generator_count += 1
        usage_pct = self._generator_count / self.generator_limit * 100
        if usage_pct >= 80:
            logger.warning(
                "generator_budget_warning",
                used=self._generator_count,
                limit=self.generator_limit,
                pct=round(usage_pct, 1),
            )

    @property
    def generator_budget_remaining(self) -> int:
        self._maybe_reset()
        return max(0, self.generator_limit - self._generator_count)

    @property
    def router_budget_remaining(self) -> int:
        self._maybe_reset()
        return max(0, self.router_limit - self._router_count)


budget_tracker = TokenBudgetTracker()


def get_router_llm() -> ChatGroq:
    """Llama 3.1 8B — for routing, grading, and rewriting."""
    return ChatGroq(
        model=settings.router_model,
        api_key=settings.groq_api_key,
        temperature=0,
    )


def get_generator_llm() -> ChatGroq:
    """Llama 3.3 70B — for synthesis generation."""
    if budget_tracker.generator_budget_remaining == 0:
        logger.warning("generator_budget_exhausted_falling_back_to_router_model")
        return get_router_llm()
    return ChatGroq(
        model=settings.generator_model,
        api_key=settings.groq_api_key,
        temperature=0.1,
    )
