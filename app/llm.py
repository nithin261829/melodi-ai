"""The one place that talks to Claude: typed, structured requests with usage accounting."""

from __future__ import annotations

import os
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from .models import Usage

T = TypeVar("T", bound=BaseModel)

# Each step is a short, well-specified judgement over small prompts (~2-4K tokens), which Haiku
# handles at a fraction of Opus's cost and latency. Override with MELODI_MODEL to compare.
MODEL = os.environ.get("MELODI_MODEL", "claude-haiku-5-5")
EFFORT = os.environ.get("MELODI_EFFORT", "low")

# Models that accept server-side refusal fallbacks (`fallbacks: "default"`); Haiku 5.5 does not.
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}

_client: anthropic.Anthropic | None = None


class LLMRefused(RuntimeError):
    pass


class LLMNotConfigured(RuntimeError):
    pass


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
            raise LLMNotConfigured("Set ANTHROPIC_API_KEY in melodi-ai/.env")
        _client = anthropic.Anthropic()
    return _client


def ask(system: str, prompt: str, schema: type[T], usage: Usage) -> T:
    """Sends one request and returns Claude's answer parsed into `schema`."""
    # If a safety classifier declines, supported models retry on a suitable model within the same call.
    fallback = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"} if MODEL in FALLBACK_MODELS else {}
    response = client().beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_format=schema,
        output_config={"effort": EFFORT},
        **fallback,
    )
    usage.model = response.model
    usage.input_tokens += response.usage.input_tokens
    usage.output_tokens += response.usage.output_tokens
    usage.llm_calls += 1
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise LLMRefused(f"Claude did not return a plan (stop_reason={response.stop_reason})")
    return response.parsed_output
