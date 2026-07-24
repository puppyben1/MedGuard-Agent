"""LLM wrappers with rate-limit-aware token budget tracking.

Primary provider is Groq (Llama 3.x). When GROQ_API_KEY is empty, falls back
to any OpenAI-compatible endpoint (DeepSeek by default) configured via
DEEPSEEK_API_KEY / DEEPSEEK_API_BASE. This lets the agent run with国产模型
without code changes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from langchain_groq import ChatGroq

from pharmagent.config import settings
from pharmagent.logging_config import get_logger
from pharmagent.runtime_config import load_runtime_config

logger = get_logger(__name__)


def _use_deepseek() -> bool:
    """True when Groq key is absent but DeepSeek key is configured."""
    runtime = load_runtime_config()
    if runtime.llm.api_key:
        return runtime.llm.provider == "openai_compatible"
    return not settings.groq_api_key and bool(settings.deepseek_api_key)


def _deepseek_chat(model: str, temperature: float) -> Any:
    """Build a ChatOpenAI client pointed at the DeepSeek-compatible endpoint."""
    from langchain_openai import ChatOpenAI
    runtime = load_runtime_config()
    api_key = runtime.llm.api_key or settings.deepseek_api_key
    base_url = runtime.llm.base_url or settings.deepseek_api_base

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
    )


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


def get_router_llm() -> Any:
    """Router/grader/rewriter LLM.

    Uses Groq (Llama 3.1 8B) when GROQ_API_KEY is set, otherwise falls back
    to DeepSeek (deepseek-chat) via the OpenAI-compatible interface.
    """
    if _use_deepseek():
        runtime = load_runtime_config()
        return _deepseek_chat(runtime.llm.router_model or settings.deepseek_router_model, 0)
    runtime = load_runtime_config()
    groq_key = runtime.llm.api_key if runtime.llm.provider == "groq" and runtime.llm.api_key else settings.groq_api_key
    router_model = runtime.llm.router_model if runtime.llm.provider == "groq" and runtime.llm.router_model else settings.router_model
    return ChatGroq(
        model=router_model,
        api_key=groq_key,
        temperature=0,
    )


def get_generator_llm() -> Any:
    """Synthesis LLM.

    Uses Groq (Llama 3.3 70B) when GROQ_API_KEY is set, otherwise falls back
    to DeepSeek (deepseek-chat) via the OpenAI-compatible interface.
    """
    if _use_deepseek():
        runtime = load_runtime_config()
        return _deepseek_chat(runtime.llm.generator_model or settings.deepseek_generator_model, 0.1)
    if budget_tracker.generator_budget_remaining == 0:
        logger.warning("generator_budget_exhausted_falling_back_to_router_model")
        return get_router_llm()
    runtime = load_runtime_config()
    groq_key = runtime.llm.api_key if runtime.llm.provider == "groq" and runtime.llm.api_key else settings.groq_api_key
    generator_model = runtime.llm.generator_model if runtime.llm.provider == "groq" and runtime.llm.generator_model else settings.generator_model
    return ChatGroq(
        model=generator_model,
        api_key=groq_key,
        temperature=0.1,
    )
