"""
AI assistant API (Phase 8): grounded answers with citations, tenant AI
settings, usage and the AI audit log. See ai/assistant.py for when AI is
used; with AI off, /ask returns the rule-based answer.

Permissions (checked here with the caller's roles, and by the middleware):
  GET /status, GET /usage, POST /ask    ai:read
  GET /settings, GET /audit             settings:read   (tenant admin)
  PUT /settings                         settings:write  (tenant admin)
"""

from __future__ import annotations

from typing import Any

from ai import assistant
from ai.providers import ProviderError
from authn_authz_middleware import check_permission
from error_handling import internal_error
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from tenant_dependencies import MiddlewareTenant

router = APIRouter(prefix="/v1/ai", tags=["ai-assistant"])


class AskBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)


class SettingsBody(BaseModel):
    enabled: bool = False
    provider: str | None = Field(None, max_length=100)
    redact_fields: list[str] = Field(default_factory=list)
    monthly_token_budget: int | None = Field(None, ge=0)
    requests_per_minute: int | None = Field(None, ge=0)


def _require(request: Request, tenant_id: str, permission: str) -> None:
    roles = getattr(request.state, "roles", None) or []
    if not check_permission(roles, permission, tenant_id):
        raise HTTPException(status_code=403, detail=f"Insufficient permissions: needs {permission}")


def _user_id(request: Request) -> str:
    user = getattr(request.state, "user", None)
    return str(getattr(user, "id", "") or "")


@router.get("/status")
async def ai_status(request: Request, customer_id: str = MiddlewareTenant) -> dict[str, Any]:
    """Whether AI answers are on for this tenant, the provider, and whether it is external."""
    _require(request, customer_id, "ai:read:tenant")
    try:
        return await assistant.status(customer_id)
    except Exception as e:
        raise internal_error(e, "Failed to read AI status", customer_id=customer_id)


@router.get("/settings")
async def get_ai_settings(request: Request, customer_id: str = MiddlewareTenant) -> dict[str, Any]:
    _require(request, customer_id, "settings:read:tenant")
    try:
        config = assistant.load_config()
        settings = await assistant.get_settings(customer_id)
        return {"settings": settings, "effective": assistant.effective(settings, config),
                "status": await assistant.status(customer_id)}
    except Exception as e:
        raise internal_error(e, "Failed to read AI settings", customer_id=customer_id)


@router.put("/settings")
async def put_ai_settings(body: SettingsBody, request: Request, customer_id: str = MiddlewareTenant) -> dict[str, Any]:
    """Opt in or out, choose a provider, add redacted fields, lower budgets."""
    _require(request, customer_id, "settings:write:tenant")
    try:
        actor = getattr(getattr(request.state, "user", None), "email", None) or _user_id(request)
        settings = await assistant.save_settings(customer_id, body.model_dump(), str(actor))
    except assistant.SettingsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise internal_error(e, "Failed to save AI settings", customer_id=customer_id)
    config = assistant.load_config()
    return {"settings": settings, "effective": assistant.effective(settings, config),
            "status": await assistant.status(customer_id)}


@router.post("/ask")
async def ai_ask(body: AskBody, request: Request, customer_id: str = MiddlewareTenant) -> dict[str, Any]:
    """A grounded answer: the model looks things up with read-only tools (as you), and cites what it used.
    With AI off for this tenant or deployment, the rule-based answer (`mode: rule_based`) and why."""
    _require(request, customer_id, "ai:read:tenant")
    roles = getattr(request.state, "roles", None) or []
    try:
        return await assistant.answer(body.question, tenant_id=customer_id, user_id=_user_id(request), roles=roles)
    except assistant.LimitExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=f"The AI provider failed: {e}")
    except Exception as e:
        raise internal_error(e, "AI request failed", customer_id=customer_id)


@router.get("/usage")
async def ai_usage(request: Request, customer_id: str = MiddlewareTenant) -> dict[str, Any]:
    _require(request, customer_id, "ai:read:tenant")
    try:
        return await assistant.usage(customer_id)
    except Exception as e:
        raise internal_error(e, "Failed to read AI usage", customer_id=customer_id)


@router.get("/audit")
async def ai_audit(request: Request, request_id: str | None = Query(None, max_length=64),
                   limit: int = Query(200, ge=1, le=1000), customer_id: str = MiddlewareTenant) -> dict[str, Any]:
    """Every prompt, tool call, tool result and response, as sent to the provider (after redaction)."""
    _require(request, customer_id, "settings:read:tenant")
    try:
        rows = await assistant._audit_store().list(customer_id, request_id=request_id, limit=limit)
    except Exception as e:
        raise internal_error(e, "Failed to read the AI audit log", customer_id=customer_id)
    return {"entries": assistant.public_audit(rows)}
