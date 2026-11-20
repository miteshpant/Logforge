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

import contextvars
import json
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
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


_REDACT: "contextvars.ContextVar[frozenset]" = contextvars.ContextVar("logforge_ai_redact", default=frozenset())


def current_redact_fields() -> frozenset:
    """The redacted fields of the AI session this request runs in (empty outside one)."""
    return _REDACT.get()


@contextmanager
def redacting(fields):
    import field_masking

    token = _REDACT.set(field_masking.normalise_fields(fields))
    try:
        yield
    finally:
        _REDACT.reset(token)


def _redact_fields(tenant_fields: list[str]) -> list[str]:
    """The tenant's redaction fields plus those the asker's custom roles mask: tool
    output is redacted before the model sees it, so an answer can't repeat them."""
    import field_masking

    return sorted(set(tenant_fields or []) | set(field_masking.current()))


def permission_check(roles: list[dict[str, Any]], tenant_id: str):
    from authn_authz_middleware import check_permission

    def allowed(permission: str) -> bool:
        try:
            return check_permission(roles, permission, tenant_id)
        except ValueError:
            return False

    return allowed


async def _rule_based(question: str, tenant_id: str, roles: list[dict[str, Any]]) -> dict[str, Any]:
    from services.nlq_processor import get_nlq_processor

    result = await get_nlq_processor().process_question(question, tenant_id,
                                                        allowed=permission_check(roles, tenant_id))
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

class LocalRateCounter:
    """Sliding one-minute window in this process only."""

    def __init__(self) -> None:
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    async def hit(self, tenant_id: str, per_minute: int, now: float) -> bool:
        window = self._requests[tenant_id]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= per_minute:
            return False
        window.append(now)
        return True


class RedisRateCounter:
    """One counter per tenant and minute in Redis, shared by every API replica.
    If Redis fails, this process counts on its own until it's back (a warning is
    logged), so AI keeps working with a per-replica limit instead of none."""

    def __init__(self, client) -> None:
        self.client = client
        self.local = LocalRateCounter()

    async def hit(self, tenant_id: str, per_minute: int, now: float) -> bool:
        key = f"ai:rate:{tenant_id}:{int(now // 60)}"
        try:
            count = int(await self.client.incr(key))
            if count == 1:
                await self.client.expire(key, 120)
            return count <= per_minute
        except Exception as e:
            logger.warning("AI rate limit store unavailable; counting in this process", error=str(e))
            return await self.local.hit(tenant_id, per_minute, now)


_rate_counter: Any = None


def reset_rate_limits() -> None:
    """Tests: count in this process, from zero."""
    global _rate_counter
    _rate_counter = LocalRateCounter()


async def _get_rate_counter():
    global _rate_counter
    if _rate_counter is None:
        try:
            from events.management.cache.redis_manager import get_raw_client

            client = await get_raw_client()
            if client is None:
                raise ConnectionError("Redis not reachable")
            _rate_counter = RedisRateCounter(client)
        except Exception as e:
            logger.warning("Redis unavailable; AI rate limits are per process", error=str(e))
            _rate_counter = LocalRateCounter()
    return _rate_counter


async def check_rate(counter, tenant_id: str, per_minute: int, now: float | None = None) -> None:
    """Fixed one-minute windows when shared (a burst can straddle two), sliding when local."""
    if not await counter.hit(tenant_id, per_minute, time.time() if now is None else now):
        raise LimitExceeded(f"AI rate limit reached ({per_minute} requests per minute); try again shortly")


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

@dataclass
class AISession:
    """One AI request: the provider, redaction, audit and limits. Features call
    `chat` (one audited model call) or pass `audit` / `before_call` to the
    orchestrator."""

    request_id: str
    tenant_id: str
    user_id: str
    roles: list[dict[str, Any]]
    feature: str
    provider: Any
    provider_settings: ProviderSettings
    redactor: Redactor
    limits: dict[str, Any]
    config: AIConfig
    audit: Any
    before_call: Any

    def provider_info(self) -> dict[str, Any]:
        return {"name": self.provider_settings.name, "model": getattr(self.provider, "model", self.provider_settings.model),
                "external": bool(self.provider_settings.external),
                "label": self.provider_settings.label or self.provider_settings.name}

    async def chat(self, messages: list, tools: list | None = None, max_tokens: int | None = None):
        """One model call: content must already be redacted. Audits the prompt and the response."""
        await self.audit("prompt", {"messages": [{"role": m.role, "content": m.content} for m in messages]})
        await self.before_call()
        result = await self.provider.chat(messages, tools or [], max_tokens=max_tokens or self.config.max_tokens)
        await self.audit("response", {"text": result.text, "stop_reason": result.stop_reason}, result.usage)
        return result


@asynccontextmanager
async def ai_session(*, tenant_id: str, user_id: str, roles: list[dict[str, Any]], feature: str):
    """Raises AIUnavailable when AI is off for this tenant (callers fall back),
    LimitExceeded over a budget or rate limit, ProviderError when the provider
    can't be built. Audit rows are written as the request goes and on exit."""
    config = load_config()
    settings = await get_settings(tenant_id)
    provider_settings = resolve(settings, config)
    limits = effective(settings, config)
    audit_store = _audit_store()
    now = datetime.now(timezone.utc)
    used = (await audit_store.usage(tenant_id, _month_start(now)))["tokens"]
    if used >= limits["monthly_token_budget"]:
        raise LimitExceeded(f"this tenant's monthly AI token budget ({limits['monthly_token_budget']:,}) is used up")
    await check_rate(await _get_rate_counter(), tenant_id, max(limits["requests_per_minute"], 0))
    try:
        provider = _build_provider(provider_settings)
    except ProviderConfigError as e:
        logger.error("AI provider misconfigured", provider=provider_settings.name, error=str(e))
        raise ProviderError(f"{provider_settings.name}: the provider is not configured correctly") from None

    request_id = str(uuid.uuid4())
    pending: list[dict[str, Any]] = []
    spent = {"tokens": 0, "seq": 0}

    async def audit(kind: str, content: Any, usage_=None) -> None:
        tokens_in = usage_.input_tokens if usage_ else 0
        tokens_out = usage_.output_tokens if usage_ else 0
        spent["tokens"] += tokens_in + tokens_out
        pending.append({"tenant_id": tenant_id, "request_id": request_id, "seq": spent["seq"],
                        "ts": datetime.now(timezone.utc), "user_id": user_id, "feature": feature, "kind": kind,
                        "provider": provider_settings.name,
                        "model": getattr(provider, "model", provider_settings.model),
                        "external": int(provider_settings.external),
                        "content": content if isinstance(content, str) else json.dumps(content, default=str),
                        "input_tokens": tokens_in, "output_tokens": tokens_out})
        spent["seq"] += 1

    async def flush() -> None:
        if pending:
            batch = list(pending)
            pending.clear()
            await audit_store.record(batch)

    async def before_call() -> None:
        # Write what this request has used so far, then re-read the month's
        # usage: concurrent requests see each other's spend at every model
        # call, not only once they finish.
        await flush()
        if spent["tokens"] >= config.max_request_tokens:
            raise LimitExceeded(f"this request used its {config.max_request_tokens:,} tokens per request")
        month = (await audit_store.usage(tenant_id, _month_start(now)))["tokens"]
        if max(month, used + spent["tokens"]) >= limits["monthly_token_budget"]:
            raise LimitExceeded("this tenant's monthly AI token budget ran out during the request")

    redact_token = _REDACT.set(frozenset(_redact_fields(limits["redact_fields"])))
    session = AISession(request_id=request_id, tenant_id=tenant_id, user_id=user_id, roles=roles, feature=feature,
                        provider=provider, provider_settings=provider_settings,
                        redactor=Redactor(_redact_fields(limits["redact_fields"])), limits=limits, config=config,
                        audit=audit, before_call=before_call)
    try:
        yield session
    except (ProviderError, LimitExceeded) as e:
        await audit("error", {"error": str(e)})
        raise
    except BaseException as e:  # including cancellation: the request still gets an error row
        await audit("error", {"error": type(e).__name__})
        raise
    finally:
        _REDACT.reset(redact_token)
        try:
            await flush()
        except Exception as e:  # don't hide the request's own error; the rows are lost, so say so loudly
            logger.error("Could not write AI audit rows", tenant_id=tenant_id, request_id=request_id, error=str(e))
        try:
            if hasattr(audit_store, "apply_retention"):
                await audit_store.apply_retention(config.audit_retention_days)
        except Exception as e:  # retention is maintenance
            logger.warning("Could not apply AI audit retention", error=str(e))


async def answer(question: str, *, tenant_id: str, user_id: str, roles: list[dict[str, Any]],
                 feature: str = "ask") -> dict[str, Any]:
    try:
        async with ai_session(tenant_id=tenant_id, user_id=user_id, roles=roles, feature=feature) as session:
            ctx = ToolContext(tenant_id=tenant_id, user_id=user_id, roles=roles)
            result = await ask(question, provider=session.provider, ctx=ctx, redactor=session.redactor,
                               audit=session.audit, max_tool_calls=session.limits["max_tool_calls"],
                               max_tokens=session.config.max_tokens, before_call=session.before_call,
                               label=session.provider_info()["label"])
            return {**result.to_public(), "request_id": session.request_id}
    except AIUnavailable as e:
        # The rule-based NLQ checks the permission each kind of question needs
        # (logs, alerts, security events) and refuses under a data scope.
        fallback = await _rule_based(question, tenant_id, roles)
        return {"mode": "rule_based", "reason_code": e.code, "reason": str(e), "citations": [], "grounded": False,
                "flags": ["rule_based"], "provider": None, **fallback}


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
