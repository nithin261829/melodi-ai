"""Melodi AI HTTP API."""

from __future__ import annotations

import hmac
import os

import anthropic
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException

load_dotenv()

from . import llm  # noqa: E402  (reads MELODI_MODEL / MELODI_EFFORT after .env is loaded)
from .models import PlanRequest, PlanResponse  # noqa: E402
from .planner import plan  # noqa: E402

app = FastAPI(title="Melodi AI", version="0.1.0")

APP_TOKEN = os.environ.get("MELODI_APP_TOKEN", "")


def require_app_token(x_melodi_token: str = Header(default="")) -> None:
    """When MELODI_APP_TOKEN is set, only the Melo app (which knows it) can spend the API budget."""
    if APP_TOKEN and not hmac.compare_digest(x_melodi_token, APP_TOKEN):
        raise HTTPException(status_code=401, detail="Missing or wrong X-Melodi-Token")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": llm.MODEL}


@app.post("/v1/plan", response_model=PlanResponse, dependencies=[Depends(require_app_token)])
def create_plan(request: PlanRequest) -> PlanResponse:
    try:
        return plan(request)
    except llm.LLMRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except llm.LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except anthropic.AuthenticationError as e:
        raise HTTPException(status_code=500, detail="Server is missing a valid ANTHROPIC_API_KEY") from e
    except anthropic.RateLimitError as e:
        raise HTTPException(status_code=503, detail="AI is busy, try again in a moment") from e
    except anthropic.APIConnectionError as e:
        raise HTTPException(status_code=503, detail="Could not reach the AI service") from e
