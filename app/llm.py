"""The one place that talks to Claude: typed, structured requests with usage accounting."""

from __future__ import annotations

import os
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from .models import Usage

T = TypeVar("T", bound=BaseModel)

MODEL = os.environ.get("MELODI_MODEL", "claude-opus-5-5")
# Each step is a short, well-specified judgement call, so low effort keeps a mix to a few seconds.
EFFORT = os.environ.get("MELODI_EFFORT", "low")

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
    response = client().beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_format=schema,
        output_config={"effort": EFFORT},
        # If a safety classifier declines, the API retries on a suitable model within the same call.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    usage.model = response.model
    usage.input_tokens += response.usage.input_tokens
    usage.output_tokens += response.usage.output_tokens
    usage.llm_calls += 1
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise LLMRefused(f"Claude did not return a plan (stop_reason={response.stop_reason})")
    return response.parsed_output
