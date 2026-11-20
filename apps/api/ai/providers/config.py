"""
Deployment AI configuration (config/ai.yml): the global switch, the
providers this deployment offers, and defaults for tenants. Tenants choose
among these providers and must opt in (ai/settings.py); nothing is enabled
by default.

`LOGFORGE_AI_ENABLED=false` switches AI off whatever the file says; the
environment cannot switch it on. API keys are never in the file: each
provider names the environment variable that holds its key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .base import ProviderConfigError

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "ai.yml"
KINDS = ("openai_compatible", "anthropic", "ollama")
DEFAULT_REDACT_FIELDS = ["password", "passwd", "secret", "token", "api_key", "apikey", "authorization",
                         "cookie", "set-cookie", "session", "private_key", "credit_card", "ssn"]


@dataclass(frozen=True)
class ProviderSettings:
    name: str
    kind: str
    model: str
    base_url: str | None = None
    api_key_env: str | None = None
    external: bool = True
    label: str = ""
    options: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "model": self.model, "external": self.external,
                "label": self.label or self.name}


@dataclass(frozen=True)
class AIConfig:
    enabled: bool = False
    providers: dict[str, ProviderSettings] = field(default_factory=dict)
    audit_retention_days: int = 90
    monthly_token_budget: int = 2_000_000
    requests_per_minute: int = 20
    max_tool_calls: int = 8
    max_tokens: int = 4096
    max_request_tokens: int = 200_000
    redact_fields: list[str] = field(default_factory=lambda: list(DEFAULT_REDACT_FIELDS))


def _provider(name: str, raw: dict[str, Any]) -> ProviderSettings:
    if not isinstance(raw, dict):
        raise ProviderConfigError(f"providers.{name}: must be a mapping")
    kind = raw.get("kind")
    if kind not in KINDS:
        raise ProviderConfigError(f"providers.{name}: kind must be one of {', '.join(KINDS)}")
    model = raw.get("model")
    if not model:
        raise ProviderConfigError(f"providers.{name}: model is required")
    if kind in ("openai_compatible", "ollama") and not raw.get("base_url"):
        raise ProviderConfigError(f"providers.{name}: base_url is required for {kind}")
    known = {"kind", "model", "base_url", "api_key_env", "external", "label"}
    return ProviderSettings(name=name, kind=kind, model=str(model), base_url=raw.get("base_url"),
                            api_key_env=raw.get("api_key_env"),
                            external=bool(raw.get("external", kind != "ollama")), label=str(raw.get("label", "")),
                            options={k: v for k, v in raw.items() if k not in known})


def load_ai_config(path: Path | None = None) -> AIConfig:
    path = Path(path or os.getenv("LOGFORGE_AI_CONFIG") or CONFIG_PATH)
    raw = yaml.safe_load(path.read_text()) if path.exists() else {}
    raw = raw or {}
    providers = {str(name): _provider(str(name), value) for name, value in (raw.get("providers") or {}).items()}
    defaults = raw.get("defaults") or {}
    enabled = bool(raw.get("enabled", False))
    if os.getenv("LOGFORGE_AI_ENABLED", "").strip().lower() in ("0", "false", "no", "off"):
        enabled = False
    return AIConfig(
        enabled=enabled, providers=providers,
        audit_retention_days=int(raw.get("audit_retention_days", 90)),
        monthly_token_budget=int(defaults.get("monthly_token_budget", 2_000_000)),
        requests_per_minute=int(defaults.get("requests_per_minute", 20)),
        max_tool_calls=int(defaults.get("max_tool_calls", 8)),
        max_tokens=int(defaults.get("max_tokens", 4096)),
        max_request_tokens=int(defaults.get("max_request_tokens", 200_000)),
        redact_fields=list(raw.get("redact_fields") or DEFAULT_REDACT_FIELDS))


def build_provider(settings: ProviderSettings, transport: Any = None):
    """Instantiate a provider. Fails if its API key variable is named but unset."""
    api_key = None
    if settings.api_key_env:
        api_key = os.getenv(settings.api_key_env)
        if not api_key:
            raise ProviderConfigError(f"{settings.name}: environment variable {settings.api_key_env} is not set")
    opts = dict(settings.options)
    if settings.kind == "anthropic":
        from .anthropic_provider import AnthropicProvider

        if not api_key:
            raise ProviderConfigError(f"{settings.name}: anthropic needs api_key_env")
        return AnthropicProvider(name=settings.name, api_key=api_key, model=settings.model,
                                 base_url=settings.base_url, external=settings.external,
                                 effort=opts.get("effort"), fallbacks=bool(opts.get("fallbacks", True)),
                                 transport=transport)
    if settings.kind == "openai_compatible":
        from .openai_compatible import OpenAICompatibleProvider

        return OpenAICompatibleProvider(name=settings.name, base_url=settings.base_url, model=settings.model,
                                        api_key=api_key, external=settings.external, transport=transport)
    from .ollama import OllamaProvider

    return OllamaProvider(name=settings.name, base_url=settings.base_url, model=settings.model,
                          external=settings.external, transport=transport)
