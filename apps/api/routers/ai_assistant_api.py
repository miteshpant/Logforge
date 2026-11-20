"""
AI assistant API (Phase 8): grounded answers with citations, tenant AI
settings, usage and the AI audit log. See ai/assistant.py for when AI is
used; with AI off, /ask returns the rule-based answer.

Permissions (checked here with the caller's roles, and by the middleware):
  GET /status, GET /usage, POST /ask    ai:read
  POST /nl2query                        ai:read and logs:read
  POST /copilot/plan, /copilot/run     ai:read; searches run with the caller's own permissions
  POST /rule-draft, /rule-draft/enable ai:read and security:write; enabling re-runs the gate and a backtest
  POST /explain                         ai:read and logs:read
  POST /pipeline-draft                  ai:read and logs:write (who may edit pipelines)
  POST /triage                          ai:read; the evidence is read with
                                        the caller's own permissions
  GET /settings, GET /audit             settings:read   (tenant admin)
  PUT /settings                         settings:write  (tenant admin)
"""

from __future__ import annotations

import json
from typing import Any, Literal

from ai import assistant
from ai.providers import ProviderError
from authn_authz_middleware import check_permission
from error_handling import internal_error
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from tenant_dependencies import MiddlewareTenant

router = APIRouter(prefix="/v1/ai", tags=["ai-assistant"])


class AskBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)


class QuestionBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class TriageBody(BaseModel):
    kind: Literal["alert", "case"]
    id: str = Field(..., min_length=1, max_length=128)


class PipelineDraftBody(BaseModel):
    samples: list[str] = Field(..., min_length=1, max_length=50)
    service: str = Field("sample", min_length=1, max_length=200)


class ExplainBody(BaseModel):
    event: dict[str, Any] = Field(..., description="The event as the Log Explorer shows it")

    @field_validator("event")
    @classmethod
    def _bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, default=str)) > 32_000:
            raise ValueError("event is too large (32 KB at most)")
        return value


class CopilotBody(BaseModel):
    subject: dict[str, Any] = Field(..., description='{"kind": "case"|"alert", "id": ...} or '
                                                     '{"kind": "entity", "type": "src_ip"|"dst_ip"|"user"|"hostname", '
                                                     '"value": ..., "at": "<ISO time>"}')
    steps: list[dict[str, Any]] = Field(default_factory=list, max_length=8,
                                        description="The steps to run, as planned or edited by the analyst")


class RuleDraftBody(BaseModel):
    description: str = Field(..., min_length=3, max_length=2000)
    samples: list[Any] = Field(..., min_length=1, max_length=20, description="Attack events: JSON objects or raw lines")
    technique: str | None = Field(None, max_length=20, description="ATT&CK technique, e.g. T1003.001")
    known_good: Any = Field(None, description="One event the rule must not fire on")
    level: str = Field("medium", pattern="^(low|medium|high|critical)$")


class RuleEnableBody(BaseModel):
    yaml: str = Field(..., min_length=10, max_length=50_000)
    samples: list[Any] = Field(default_factory=list, max_length=20)
    known_good: Any = None
    backtest_days: int = Field(7, ge=1, le=30)
    max_alerts_per_day: float = Field(50, ge=0)


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


async def _catalogue(tenant_id: str) -> dict[str, Any]:
    """The tenant's field catalogue over the last 24 hours (Phase 5)."""
    from routers.fields_api import field_catalogue

    return await field_catalogue(window="24h", service=None, sample=2000, customer_id=tenant_id, user=None)


@router.post("/nl2query")
async def ai_nl2query(body: QuestionBody, request: Request, customer_id: str = MiddlewareTenant) -> dict[str, Any]:
    """Draft a LogforgeQL query for a question, explained, for the user to run or edit. The model sees the
    tenant's field names and redacted example values, never log data. With AI off, a rule-based draft."""
    from ai.nl2query import rule_based, translate

    _require(request, customer_id, "ai:read:tenant")
    _require(request, customer_id, "logs:read:tenant")
    roles = getattr(request.state, "roles", None) or []
    try:
        catalogue = await _catalogue(customer_id)
    except HTTPException:
        raise
    except Exception as e:
        raise internal_error(e, "Failed to read the field catalogue", customer_id=customer_id)
    try:
        async with assistant.ai_session(tenant_id=customer_id, user_id=_user_id(request), roles=roles,
                                        feature="nl2query") as session:
            draft = await translate(body.question, session.provider, catalogue=catalogue, redactor=session.redactor,
                                    session=session)
            return {**draft.to_public(), "provider": session.provider_info(), "request_id": session.request_id}
    except assistant.AIUnavailable as e:
        return {**rule_based(body.question, catalogue).to_public(), "reason_code": e.code, "reason": str(e),
                "provider": None}
    except assistant.LimitExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=f"The AI provider failed: {e}")
    except Exception as e:
        raise internal_error(e, "AI query drafting failed", customer_id=customer_id)


@router.post("/triage")
async def ai_triage(body: TriageBody, request: Request, customer_id: str = MiddlewareTenant) -> dict[str, Any]:
    """A triage summary of an alert or case: what happened, ATT&CK context, entities, related activity and
    next steps, each sentence citing its evidence. The evidence is read as the caller; with AI off, or if the
    model's answer has nothing cited, the summary is built from the evidence by template."""
    from ai.tools import ToolContext
    from ai.triage import gather, template, write

    _require(request, customer_id, "ai:read:tenant")
    roles = getattr(request.state, "roles", None) or []
    ctx = ToolContext(tenant_id=customer_id, user_id=_user_id(request), roles=roles)
    try:
        bundle = await gather(body.kind, body.id, ctx)
    except LookupError:
        raise HTTPException(status_code=404, detail=f"{body.kind} {body.id} not found")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise internal_error(e, "Failed to gather the triage evidence", customer_id=customer_id)
    try:
        async with assistant.ai_session(tenant_id=customer_id, user_id=_user_id(request), roles=roles,
                                        feature="triage") as session:
            summary = await write(bundle, session.provider, redactor=session.redactor, session=session)
            return {**summary, "provider": session.provider_info(), "request_id": session.request_id}
    except assistant.AIUnavailable as e:
        return {**template(bundle), "reason_code": e.code, "reason": str(e), "provider": None}
    except assistant.LimitExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=f"The AI provider failed: {e}")
    except Exception as e:
        raise internal_error(e, "AI triage failed", customer_id=customer_id)


@router.post("/pipeline-draft")
async def ai_pipeline_draft(body: PipelineDraftBody, request: Request,
                            customer_id: str = MiddlewareTenant) -> dict[str, Any]:
    """Draft an ingest pipeline that parses the sample lines, checked by simulation (how many lines parsed,
    the fields extracted, the failures). Nothing is saved. The model sees the samples, redacted; with AI off,
    or if it parses fewer lines, the heuristic draft."""
    from ai.pipeline_draft import draft, heuristic

    _require(request, customer_id, "ai:read:tenant")
    _require(request, customer_id, "logs:write:tenant")
    roles = getattr(request.state, "roles", None) or []
    try:
        async with assistant.ai_session(tenant_id=customer_id, user_id=_user_id(request), roles=roles,
                                        feature="pipeline_draft") as session:
            out = await draft(body.samples, session.provider, redactor=session.redactor, session=session,
                              service=body.service)
            return {**out.to_public(), "provider": session.provider_info(), "request_id": session.request_id}
    except assistant.AIUnavailable as e:
        return {**heuristic(body.samples, body.service).to_public(), "reason_code": e.code, "reason": str(e),
                "provider": None}
    except assistant.LimitExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=f"The AI provider failed: {e}")
    except Exception as e:
        raise internal_error(e, "AI pipeline drafting failed", customer_id=customer_id)


@router.post("/explain")
async def ai_explain(body: ExplainBody, request: Request, customer_id: str = MiddlewareTenant) -> dict[str, Any]:
    """Explain one event: what it is, what its fields mean, why it matters (the shipped detection rules it
    matches, threat intelligence for its addresses) and follow-up queries, every sentence cited. With AI off,
    or if the model's answer has nothing cited, the explanation is built from the reference by template."""
    from ai.explain import gather, template, write
    from ai.tools import ToolContext

    _require(request, customer_id, "ai:read:tenant")
    _require(request, customer_id, "logs:read:tenant")
    roles = getattr(request.state, "roles", None) or []
    try:
        bundle = await gather(body.event, ToolContext(tenant_id=customer_id, user_id=_user_id(request), roles=roles))
    except Exception as e:
        raise internal_error(e, "Failed to gather the event's evidence", customer_id=customer_id)
    try:
        async with assistant.ai_session(tenant_id=customer_id, user_id=_user_id(request), roles=roles,
                                        feature="explain") as session:
            out = await write(bundle, session.provider, redactor=session.redactor, session=session)
            return {**out, "provider": session.provider_info(), "request_id": session.request_id}
    except assistant.AIUnavailable as e:
        return {**template(bundle), "reason_code": e.code, "reason": str(e), "provider": None}
    except assistant.LimitExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=f"The AI provider failed: {e}")
    except Exception as e:
        raise internal_error(e, "AI event explanation failed", customer_id=customer_id)


async def _copilot_context(body: CopilotBody, request: Request, customer_id: str):
    from ai.copilot import gather_context
    from ai.tools import ToolContext

    roles = getattr(request.state, "roles", None) or []
    ctx = ToolContext(tenant_id=customer_id, user_id=_user_id(request), roles=roles)
    try:
        return ctx, await gather_context(body.subject, ctx)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except LookupError:
        raise HTTPException(status_code=404, detail=f"{body.subject.get('kind')} {body.subject.get('id')} not found")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/copilot/plan")
async def ai_copilot_plan(body: CopilotBody, request: Request, customer_id: str = MiddlewareTenant) -> dict[str, Any]:
    """The read-only searches the copilot proposes for a case, alert or entity. Nothing runs: the analyst
    reviews, edits or drops steps, then calls /copilot/run."""
    from ai.copilot import plan

    _require(request, customer_id, "ai:read:tenant")
    _, context = await _copilot_context(body, request, customer_id)
    return {"subject": context.subject, "anchor": context.anchor.isoformat(), "entities": context.entities,
            "steps": [s.to_public() for s in plan(context)]}


@router.post("/copilot/run")
async def ai_copilot_run(body: CopilotBody, request: Request, customer_id: str = MiddlewareTenant) -> dict[str, Any]:
    """Run the approved steps as the caller: a cited timeline, root-cause candidates, hypotheses and proposed
    next steps. With AI on, the model writes the hypotheses; nothing it cites is outside what was fetched."""
    from ai.copilot import run, validate_steps, write

    _require(request, customer_id, "ai:read:tenant")
    ctx, context = await _copilot_context(body, request, customer_id)
    try:
        steps = validate_steps(body.steps)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    try:
        result = await run(context, steps, ctx)
    except Exception as e:
        raise internal_error(e, "The investigation searches failed", customer_id=customer_id)
    roles = getattr(request.state, "roles", None) or []
    try:
        async with assistant.ai_session(tenant_id=customer_id, user_id=_user_id(request), roles=roles,
                                        feature="copilot") as session:
            out = await write(result, context, session.provider, redactor=session.redactor, session=session)
            return {**out, "provider": session.provider_info(), "request_id": session.request_id}
    except assistant.AIUnavailable as e:
        return {**result, "reason_code": e.code, "reason": str(e), "provider": None}
    except assistant.LimitExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=f"The AI provider failed: {e}")
    except Exception as e:
        raise internal_error(e, "The copilot failed", customer_id=customer_id)


@router.post("/rule-draft")
async def ai_rule_draft(body: RuleDraftBody, request: Request, customer_id: str = MiddlewareTenant) -> dict[str, Any]:
    """Draft a Sigma rule and its fixtures for a behaviour. The draft passes only if the fixture gate accepts
    it, it fires on every attack sample and not on the known-good one (two attempts at most). Nothing is
    saved: enable a passing draft with /rule-draft/enable."""
    from ai.rule_draft import draft, heuristic

    _require(request, customer_id, "ai:read:tenant")
    _require(request, customer_id, "security:write:tenant")
    roles = getattr(request.state, "roles", None) or []
    kwargs = {"technique": body.technique, "known_good": body.known_good, "level": body.level}
    try:
        async with assistant.ai_session(tenant_id=customer_id, user_id=_user_id(request), roles=roles,
                                        feature="rule_draft") as session:
            out = await draft(body.description, body.samples, session.provider, redactor=session.redactor,
                              session=session, **kwargs)
            return {**out.to_public(), "provider": session.provider_info(), "request_id": session.request_id}
    except assistant.AIUnavailable as e:
        return {**heuristic(body.description, body.samples, **kwargs).to_public(), "reason_code": e.code,
                "reason": str(e), "provider": None}
    except assistant.LimitExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=f"The AI provider failed: {e}")
    except Exception as e:
        raise internal_error(e, "Rule drafting failed", customer_id=customer_id)


class _RuleStore:
    """Where enabled drafts go: the tenant's rules (sigma_rules_mt), with a backtest over its stored logs."""

    async def reserved_ids(self, tenant_id: str) -> list[str]:
        from routers.security_api import _dac_rows

        managed, others = await _dac_rows(tenant_id)
        return [r["id"] for r in managed + others]

    async def backtest(self, tenant_id: str, rule_id: str, rules: list[dict[str, Any]], days: int) -> dict[str, Any]:
        from datetime import datetime, timedelta, timezone

        from backtest import run_backtest
        from routers.security_api import _backtest_db

        end = datetime.now(timezone.utc)
        return await run_backtest(_backtest_db(), rules, rule_id, tenant_id, end - timedelta(days=days), end,
                                  max_events=500_000, sample_limit=5)

    async def apply(self, tenant_id: str, plan: dict[str, Any]) -> dict[str, int]:
        from detection_as_code import apply_sync
        from routers.security_api import _invalidate_rules, _rules_db

        counts = await apply_sync(_rules_db(), tenant_id, plan)
        await _invalidate_rules(tenant_id)
        return counts


def _rule_store() -> _RuleStore:
    return _RuleStore()


@router.post("/rule-draft/enable")
async def ai_rule_draft_enable(body: RuleEnableBody, request: Request,
                               customer_id: str = MiddlewareTenant) -> dict[str, Any]:
    """Enable a drafted rule. Everything is checked again here, whatever the client says: the fixture gate,
    the samples (if given), and a backtest over the tenant's stored logs (at most max_alerts_per_day). A rule
    that fails any of them is refused (409) and nothing is written."""
    import yaml as _yaml

    from ai.rule_draft import verify
    from detection_as_code import DetectionAsCodeError, plan_sync

    _require(request, customer_id, "ai:read:tenant")
    _require(request, customer_id, "security:write:tenant")
    try:
        rule = _yaml.safe_load(body.yaml)
    except _yaml.YAMLError as e:
        raise HTTPException(status_code=422, detail=f"invalid YAML: {e}")
    if not isinstance(rule, dict) or not str(rule.get("id") or "").startswith("ai_"):
        raise HTTPException(status_code=422, detail="not a drafted rule (drafted rule ids start with ai_)")
    reason = verify(rule, body.samples, body.known_good) if body.samples else verify(rule, [], None)
    if reason:
        raise HTTPException(status_code=409, detail=f"not enabled: {reason}")
    store = _rule_store()

    async def backtest(rule_id, rules):
        return await store.backtest(customer_id, rule_id, rules, body.backtest_days)

    try:
        plan = await plan_sync(customer_id, _yaml.safe_dump(rule, sort_keys=False), [],
                               backtest=backtest, backtest_days=body.backtest_days,
                               max_alerts_per_day=body.max_alerts_per_day,
                               reserved_ids=await store.reserved_ids(customer_id))
    except DetectionAsCodeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise internal_error(e, "The rule's backtest failed", customer_id=customer_id)
    summary = {rid: {k: v for k, v in result.items() if k not in ("alerts",)} for rid, result in plan["backtest"].items()}
    if plan["status"] != "ok":
        raise HTTPException(status_code=409, detail="not enabled: " + "; ".join(r["reason"] for r in plan["rejected"]))
    for row in plan["create"]:
        row["created_by"] = "ai-draft"
    counts = await store.apply(customer_id, plan)
    return {"enabled": True, "rule_id": rule["id"], "created": counts.get("created", 0), "backtest": summary}
