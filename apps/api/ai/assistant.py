"""
The AI assistant service (Phase 8): decides whether AI may be used for a
tenant, runs a grounded answer with audit, budget and rate limit, and falls
back to the rule-based NLQ when AI is off.

AI is used only when all of these hold, checked on every request:
  1. the deployment enables it (config/ai.yml `enabled`, and
     LOGFORGE_AI_ENABLED is not false),
  2. the tenant has opted in and chosen a provider,
  3. that provider is still offered by the deployment.
Otherwise `answer()` returns the rule-based result with `mode: rule_based`
and the reason.
"""

from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

import structlog

from .orchestrator import ask
from .providers import (
    AIConfig,
    ProviderConfigError,
    ProviderError,
    ProviderSettings,
    build_provider,
    load_ai_config,
)
from .redaction import Redactor
from .tools import ToolContext

logger = structlog.get_logger(__name__)

MAX_REDACT_FIELDS = 100
REASONS = {
    "global_off": "AI is switched off for this deployment",
    "no_provider": "this deployment has no AI provider configured",
    "tenant_off": "AI is not enabled for this tenant (Settings -> AI)",
    "provider_missing": "the provider this tenant chose is no longer offered",
}


class AIUnavailable(Exception):
    def __init__(self, code: str):
        super().__init__(REASONS[code])
        self.code = code


class LimitExceeded(Exception):
    """A budget or rate limit was reached (HTTP 429)."""


class SettingsError(ValueError):
    pass


# -- seams (patched in tests) ----------------------------------------------------------

def load_config() -> AIConfig:
    return load_ai_config()


def _settings_store():
    from .store import SettingsStore

    return SettingsStore()


def _audit_store():
    from .store import AuditStore

    return AuditStore()


def _build_provider(settings: ProviderSettings):
    return build_provider(settings)


async def _rule_based(question: str, tenant_id: str) -> dict[str, Any]:
    from services.nlq_processor import get_nlq_processor

    result = await get_nlq_processor().process_question(question, tenant_id)
    return {"text": result.answer, "generated_sql": result.generated_sql, "suggestions": result.suggestions,
            "results": result.results, "confidence": result.confidence}


# -- settings ----------------------------------------------------------------------------

DEFAULT_SETTINGS = {"enabled": False, "provider": None, "redact_fields": [], "monthly_token_budget": None,
                    "requests_per_minute": None}


def validate_settings(raw: dict[str, Any], config: AIConfig) -> dict[str, Any]:
    settings = {**DEFAULT_SETTINGS, **{k: v for k, v in raw.items() if k in DEFAULT_SETTINGS}}
    if settings["enabled"]:
        if not settings["provider"]:
            raise SettingsError("choose a provider to enable AI")
    if settings["provider"] and settings["provider"] not in config.providers:
        raise SettingsError(f"unknown provider {settings['provider']!r}; this deployment offers: "
                            f"{', '.join(config.providers) or 'none'}")
    fields = settings["redact_fields"] or []
    if not isinstance(fields, list) or len(fields) > MAX_REDACT_FIELDS or not all(
            isinstance(f, str) and 0 < len(f) <= 200 for f in fields):
        raise SettingsError(f"redact_fields: at most {MAX_REDACT_FIELDS} field names")
    settings["redact_fields"] = sorted(set(f.strip() for f in fields if f.strip()))
    for name in ("monthly_token_budget", "requests_per_minute"):
        value = settings[name]
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            raise SettingsError(f"{name} must be a non-negative integer")
    return settings


def effective(settings: dict[str, Any], config: AIConfig) -> dict[str, Any]:
    """Tenant limits may lower the deployment's, never raise them."""
    def lower(name: str, default: int) -> int:
        value = settings.get(name)
        return default if value is None else min(int(value), default)

    return {"monthly_token_budget": lower("monthly_token_budget", config.monthly_token_budget),
            "requests_per_minute": lower("requests_per_minute", config.requests_per_minute),
            "max_tool_calls": config.max_tool_calls,
            "redact_fields": sorted(set(config.redact_fields) | set(settings.get("redact_fields") or []))}


async def get_settings(tenant_id: str) -> dict[str, Any]:
    return {**DEFAULT_SETTINGS, **(await _settings_store().get(tenant_id) or {})}


async def save_settings(tenant_id: str, raw: dict[str, Any], actor: str) -> dict[str, Any]:
    config = load_config()
    settings = validate_settings(raw, config)
    await _settings_store().save(tenant_id, settings, actor)
    return settings


def resolve(settings: dict[str, Any], config: AIConfig) -> ProviderSettings:
    if not config.enabled:
        raise AIUnavailable("global_off")
    if not config.providers:
        raise AIUnavailable("no_provider")
    if not settings.get("enabled") or not settings.get("provider"):
        raise AIUnavailable("tenant_off")
    provider = config.providers.get(settings["provider"])
    if provider is None:
        raise AIUnavailable("provider_missing")
    return provider


async def status(tenant_id: str) -> dict[str, Any]:
    config = load_config()
    settings = await get_settings(tenant_id)
    out: dict[str, Any] = {"global_enabled": config.enabled,
                           "providers": [p.public() for p in config.providers.values()] if config.enabled else [],
                           "tenant_enabled": bool(settings.get("enabled")), "active": False, "provider": None}
    try:
        provider = resolve(settings, config)
        out.update(active=True, provider=provider.public(), reason_code=None, reason=None)
    except AIUnavailable as e:
        out.update(reason_code=e.code, reason=str(e))
    return out


# -- limits ----------------------------------------------------------------------------

_requests: dict[str, deque[float]] = defaultdict(deque)


def reset_rate_limits() -> None:
    _requests.clear()


def _rate_limit(tenant_id: str, per_minute: int, now: float | None = None) -> None:
    """Per-process sliding window (each API replica counts on its own)."""
    now = now or time.monotonic()
    window = _requests[tenant_id]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= per_minute:
        raise LimitExceeded(f"AI rate limit reached ({per_minute} requests per minute); try again shortly")
    window.append(now)


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def usage(tenant_id: str) -> dict[str, Any]:
    config = load_config()
    settings = await get_settings(tenant_id)
    now = datetime.now(timezone.utc)
    used = await _audit_store().usage(tenant_id, _month_start(now))
    limits = effective(settings, config)
    return {**used, "since": _month_start(now).isoformat(), "monthly_token_budget": limits["monthly_token_budget"],
            "requests_per_minute": limits["requests_per_minute"]}


# -- answering --------------------------------------------------------------------------

async def answer(question: str, *, tenant_id: str, user_id: str, roles: list[dict[str, Any]],
                 feature: str = "ask") -> dict[str, Any]:
    config = load_config()
    settings = await get_settings(tenant_id)
    try:
        provider_settings = resolve(settings, config)
    except AIUnavailable as e:
        fallback = await _rule_based(question, tenant_id)
        return {"mode": "rule_based", "reason_code": e.code, "reason": str(e), "citations": [], "grounded": False,
                "flags": ["rule_based"], "provider": None, **fallback}

    limits = effective(settings, config)
    audit_store = _audit_store()
    now = datetime.now(timezone.utc)
    used = (await audit_store.usage(tenant_id, _month_start(now)))["tokens"]
    if used >= limits["monthly_token_budget"]:
        raise LimitExceeded(f"this tenant's monthly AI token budget ({limits['monthly_token_budget']:,}) is used up")
    _rate_limit(tenant_id, max(limits["requests_per_minute"], 0))
    try:
        provider = _build_provider(provider_settings)
    except ProviderConfigError as e:
        logger.error("AI provider misconfigured", provider=provider_settings.name, error=str(e))
        raise ProviderError(f"{provider_settings.name}: the provider is not configured correctly") from None

    request_id = str(uuid.uuid4())
    rows: list[dict[str, Any]] = []
    spent = {"tokens": 0}

    async def audit(kind: str, content: Any, usage_=None) -> None:
        tokens_in = usage_.input_tokens if usage_ else 0
        tokens_out = usage_.output_tokens if usage_ else 0
        spent["tokens"] += tokens_in + tokens_out
        rows.append({"tenant_id": tenant_id, "request_id": request_id, "seq": len(rows),
                     "ts": datetime.now(timezone.utc), "user_id": user_id, "feature": feature, "kind": kind,
                     "provider": provider_settings.name, "model": getattr(provider, "model", provider_settings.model),
                     "external": int(provider_settings.external),
                     "content": content if isinstance(content, str) else json.dumps(content, default=str),
                     "input_tokens": tokens_in, "output_tokens": tokens_out})

    async def before_call() -> None:
        if used + spent["tokens"] >= limits["monthly_token_budget"]:
            raise LimitExceeded("this tenant's monthly AI token budget ran out during the request")

    ctx = ToolContext(tenant_id=tenant_id, user_id=user_id, roles=roles)
    try:
        result = await ask(question, provider=provider, ctx=ctx, redactor=Redactor(limits["redact_fields"]),
                           audit=audit, max_tool_calls=limits["max_tool_calls"], max_tokens=config.max_tokens,
                           before_call=before_call, label=provider_settings.label or provider_settings.name)
    except (ProviderError, LimitExceeded) as e:
        await audit("error", {"error": str(e)})
        raise
    except Exception as e:
        await audit("error", {"error": type(e).__name__})
        raise
    finally:
        try:
            await audit_store.apply_retention(config.audit_retention_days) if hasattr(
                audit_store, "apply_retention") else None
        except Exception as e:  # retention is maintenance; the audit rows must still be written
            logger.warning("Could not apply AI audit retention", error=str(e))
        await audit_store.record(rows)
    return {**result.to_public(), "request_id": request_id}


def public_audit(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        item = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in r.items() if k != "tenant_id"}
        try:
            item["content"] = json.loads(item["content"])
        except (TypeError, ValueError):
            pass
        out.append(item)
    return out


__all__: tuple[str, ...] = (
    "AIUnavailable",
    "LimitExceeded",
    "SettingsError",
    "answer",
    "effective",
    "get_settings",
    "public_audit",
    "save_settings",
    "status",
    "usage",
)
