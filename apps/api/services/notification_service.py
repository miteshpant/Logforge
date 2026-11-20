"""
Notification Delivery Service (LF-035)

Real alert notification delivery for every supported channel type:

- **webhook**   – generic HTTP POST with JSON body, optional custom headers and
                  an HMAC-SHA256 signature over the raw body so receivers can
                  verify authenticity.
- **slack**     – incoming-webhook delivery with Block Kit formatting.
- **email**     – SMTP (stdlib smtplib run in a worker thread), configured via
                  LOGFORGE_SMTP_* environment variables.
- **pagerduty** – Events API v2 (`trigger`), with a stable dedup_key per
                  (rule, alert) so retries never double-page.
- **teams / discord** – incoming-webhook style JSON posts.

Design rules (no-mock policy):
- A notification is only ever reported as sent when the provider confirmed it.
- Unconfigured channels (e.g. SMTP host missing) fail loudly with a clear
  error, they are never silently skipped or faked.
- Every delivery attempt cycle is recorded in `alert_notifications_mt`
  (status 'sent' or 'failed', attempt count, error message) so the trail is
  auditable and failures are visible via the API.

Automatic delivery for triggered alerts runs as an outbox-style dispatcher:
alert instances are written to `alert_instances_mt` by the alert processor /
engine; the dispatcher polls for recent instances that have no delivery record
for a configured channel yet and delivers exactly once per
(alert, channel) pair. The dispatcher is gated behind
`LOGFORGE_NOTIFICATIONS_ENABLED` (default: off) because a misconfigured loop
can page a real on-call rotation. Explicit channel *tests* are always real
deliveries regardless of the gate - the user asked for them.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import os
import random
import smtplib
import ssl
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import structlog

from utils.query_resilience import CircuitBreaker, CircuitBreakerConfig

logger = structlog.get_logger(__name__)

NOTIFICATIONS_TABLE = "alert_notifications_mt"
ALERT_INSTANCES_TABLE = "alert_instances_mt"
ALERT_RULES_TABLE = "alert_rules_mt"
NOTIFICATION_CHANNELS_TABLE = "notification_channels_mt"

# The alert_notifications_mt.notification_type enum only knows these four
# values. teams/discord deliveries are webhook-style posts and are recorded as
# 'webhook' (the schema enum cannot represent them without a migration).
_RECORDABLE_TYPES = {"email", "slack", "webhook", "pagerduty"}

# Config keys whose values are secrets: encrypted at rest, masked in API
# responses, never logged.
SENSITIVE_CONFIG_KEYS = {
    "url",
    "webhook_url",
    "routing_key",
    "integration_key",
    "token",
    "bot_token",
    "signing_secret",
    "password",
    "smtp_password",
    "headers",
}

MASK_PLACEHOLDER = "••••••••"
_ENC_PREFIX = "enc:v1:"


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def notifications_enabled() -> bool:
    """Automatic (rule-triggered) delivery gate. Default OFF per LF-035."""
    return _env_flag("LOGFORGE_NOTIFICATIONS_ENABLED", "false")


# ---------------------------------------------------------------------------
# Secret handling (encryption at rest + masking for API responses)
# ---------------------------------------------------------------------------

class SecretVault:
    """Fernet encryption for channel credentials stored in ClickHouse.

    The key is derived from LOGFORGE_SECRET_KEY. Without it a deterministic
    development fallback is used so local stacks keep working, with a loud
    warning - production deployments must set LOGFORGE_SECRET_KEY.
    """

    _warned = False

    def __init__(self):
        secret = os.getenv("LOGFORGE_SECRET_KEY", "")
        if not secret:
            secret = "logforge-dev-secret-key-set-LOGFORGE_SECRET_KEY"
            if not SecretVault._warned:
                logger.warning(
                    "LOGFORGE_SECRET_KEY is not set - channel credentials are "
                    "encrypted with a development fallback key. Set "
                    "LOGFORGE_SECRET_KEY in production."
                )
                SecretVault._warned = True
        digest = hashlib.sha256(secret.encode("utf-8")).digest()
        from cryptography.fernet import Fernet

        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, value: str) -> str:
        return _ENC_PREFIX + self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        """Decrypt an `enc:v1:` value; plaintext passes through unchanged."""
        if not isinstance(value, str) or not value.startswith(_ENC_PREFIX):
            return value
        from cryptography.fernet import InvalidToken

        try:
            return self._fernet.decrypt(value[len(_ENC_PREFIX):].encode("ascii")).decode("utf-8")
        except InvalidToken:
            raise ValueError(
                "Stored channel credential could not be decrypted "
                "(LOGFORGE_SECRET_KEY changed since it was saved)"
            )

    @staticmethod
    def is_encrypted(value: Any) -> bool:
        return isinstance(value, str) and value.startswith(_ENC_PREFIX)


_vault: Optional[SecretVault] = None


def get_secret_vault() -> SecretVault:
    global _vault
    if _vault is None:
        _vault = SecretVault()
    return _vault


def encrypt_channel_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Encrypt sensitive values in a channel config before persisting."""
    vault = get_secret_vault()
    out: Dict[str, Any] = {}
    for key, value in (config or {}).items():
        if key in SENSITIVE_CONFIG_KEYS and value not in (None, ""):
            raw = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            out[key] = vault.encrypt(raw) if not SecretVault.is_encrypted(raw) else raw
        else:
            out[key] = value
    return out


def decrypt_channel_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Decrypt sensitive values for actual delivery. Never expose via API."""
    vault = get_secret_vault()
    out: Dict[str, Any] = {}
    for key, value in (config or {}).items():
        if SecretVault.is_encrypted(value):
            decrypted = vault.decrypt(value)
            if key == "headers":
                try:
                    decrypted = json.loads(decrypted)
                except (TypeError, json.JSONDecodeError):
                    pass
            out[key] = decrypted
        else:
            out[key] = value
    return out


def mask_channel_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Masked view of a channel config for API responses.

    Secrets are replaced with a hint (never the value): URLs keep their host so
    the user can tell channels apart, everything else becomes a placeholder.
    """
    masked: Dict[str, Any] = {}
    for key, value in (config or {}).items():
        if key not in SENSITIVE_CONFIG_KEYS:
            masked[key] = value
            continue
        if value in (None, ""):
            masked[key] = value
            continue
        if SecretVault.is_encrypted(value):
            try:
                value = get_secret_vault().decrypt(value)
            except ValueError:
                masked[key] = MASK_PLACEHOLDER
                continue
        if key in {"url", "webhook_url"} and isinstance(value, str):
            try:
                from urllib.parse import urlparse

                parsed = urlparse(value)
                masked[key] = f"{parsed.scheme}://{parsed.netloc}/{MASK_PLACEHOLDER}"
            except Exception:
                masked[key] = MASK_PLACEHOLDER
        else:
            masked[key] = MASK_PLACEHOLDER
    return masked


def merge_config_preserving_secrets(
    existing_config: Dict[str, Any], incoming_config: Dict[str, Any]
) -> Dict[str, Any]:
    """Merge a config update over the stored config.

    A UI that received a masked config may echo the mask back on save; masked
    values must never overwrite the real stored secret.
    """
    merged = dict(existing_config or {})
    for key, value in (incoming_config or {}).items():
        if isinstance(value, str) and (MASK_PLACEHOLDER in value):
            continue  # masked echo - keep the stored secret
        merged[key] = value
    return merged


# ---------------------------------------------------------------------------
# Delivery result
# ---------------------------------------------------------------------------

@dataclass
class DeliveryResult:
    """The true outcome of a delivery attempt cycle - never fabricated."""

    success: bool
    channel_id: str
    channel_type: str
    attempts: int = 0
    status_code: Optional[int] = None
    error: Optional[str] = None
    duration_ms: int = 0
    delivered_at: Optional[datetime] = None
    dedup_key: Optional[str] = None
    response_snippet: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "channel_id": self.channel_id,
            "channel_type": self.channel_type,
            "attempts": self.attempts,
            "status_code": self.status_code,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "dedup_key": self.dedup_key,
        }


class NotificationService:
    """Provider implementations + retry/backoff + outbox dispatcher."""

    def __init__(self):
        self._db = None  # lazy - constructing DatabaseLayer opens a connection
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._in_flight: set = set()
        self._dispatcher_task: Optional[asyncio.Task] = None
        self._running = False

        self.max_attempts = int(os.getenv("LOGFORGE_NOTIFY_MAX_ATTEMPTS", "3"))
        self.timeout_seconds = float(os.getenv("LOGFORGE_NOTIFY_TIMEOUT_SECONDS", "10"))
        self.poll_seconds = float(os.getenv("LOGFORGE_NOTIFY_POLL_SECONDS", "5"))
        self.lookback_minutes = int(os.getenv("LOGFORGE_NOTIFY_LOOKBACK_MINUTES", "60"))

    @property
    def db(self):
        if self._db is None:
            from database_layer import DatabaseLayer

            self._db = DatabaseLayer("AlertService", "alert-service-key-dev")
        return self._db

    def _breaker(self, channel_id: str) -> CircuitBreaker:
        if channel_id not in self._breakers:
            self._breakers[channel_id] = CircuitBreaker(
                f"notify-{channel_id}",
                CircuitBreakerConfig(failure_threshold=5, timeout_seconds=120.0),
            )
        return self._breakers[channel_id]

    # ------------------------------------------------------------------
    # Public delivery API
    # ------------------------------------------------------------------

    async def send_to_channel(
        self,
        channel: Dict[str, Any],
        payload: Dict[str, Any],
        event_type: str = "alert.triggered",
        max_attempts: Optional[int] = None,
    ) -> DeliveryResult:
        """Deliver `payload` through `channel` with retries and backoff.

        `channel` is a row from notification_channels_mt (config may hold
        encrypted values). Returns the genuine provider outcome.
        """
        channel_id = channel.get("id") or channel.get("channel_id") or "unknown"
        channel_type = (channel.get("channel_type") or channel.get("type") or "").lower()
        attempts_allowed = max_attempts or self.max_attempts

        started = datetime.now(timezone.utc)
        result = DeliveryResult(success=False, channel_id=channel_id, channel_type=channel_type)

        raw_config = channel.get("config", {})
        if isinstance(raw_config, str):
            try:
                raw_config = json.loads(raw_config)
            except json.JSONDecodeError:
                result.error = "Channel config is not valid JSON"
                return result
        try:
            config = decrypt_channel_config(raw_config)
        except ValueError as e:
            result.error = str(e)
            return result

        breaker = self._breaker(channel_id)
        if breaker.is_open and not await breaker._should_allow_request():
            result.error = (
                f"Circuit breaker open for channel {channel_id} after repeated "
                "delivery failures; retry later"
            )
            result.attempts = 0
            return result

        last_error: Optional[str] = None
        for attempt in range(1, attempts_allowed + 1):
            result.attempts = attempt
            try:
                ok, status_code, error, snippet, dedup_key = await self._deliver_once(
                    channel_type, config, payload, event_type
                )
                result.status_code = status_code
                result.response_snippet = snippet
                result.dedup_key = dedup_key
                if ok:
                    result.success = True
                    result.error = None
                    result.delivered_at = datetime.now(timezone.utc)
                    await breaker.record_success()
                    break
                last_error = error or f"Provider returned status {status_code}"
                # Non-retryable client errors: bad config will not fix itself.
                if status_code is not None and 400 <= status_code < 500 and status_code != 429:
                    break
            except asyncio.TimeoutError:
                last_error = f"Delivery timed out after {self.timeout_seconds}s"
            except aiohttp.ClientError as e:
                last_error = f"HTTP client error: {e}"
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"

            if attempt < attempts_allowed:
                # Exponential backoff with jitter: 1s, 2s, 4s... +-30%
                delay = (2 ** (attempt - 1)) * (1 + random.uniform(-0.3, 0.3))
                await asyncio.sleep(delay)

        if not result.success:
            result.error = last_error or "Delivery failed"
            await breaker.record_failure()

        result.duration_ms = int(
            (datetime.now(timezone.utc) - started).total_seconds() * 1000
        )
        return result

    async def _deliver_once(
        self,
        channel_type: str,
        config: Dict[str, Any],
        payload: Dict[str, Any],
        event_type: str,
    ) -> Tuple[bool, Optional[int], Optional[str], Optional[str], Optional[str]]:
        """One provider attempt. Returns (ok, status, error, snippet, dedup_key)."""
        if channel_type == "webhook":
            ok, status, error, snippet = await self._deliver_webhook(config, payload, event_type)
            return ok, status, error, snippet, None
        if channel_type == "slack":
            ok, status, error, snippet = await self._deliver_slack(config, payload)
            return ok, status, error, snippet, None
        if channel_type == "email":
            ok, error = await self._deliver_email(config, payload)
            return ok, None, error, None, None
        if channel_type == "pagerduty":
            return await self._deliver_pagerduty(config, payload)
        if channel_type == "discord":
            ok, status, error, snippet = await self._deliver_discord(config, payload)
            return ok, status, error, snippet, None
        if channel_type == "teams":
            ok, status, error, snippet = await self._deliver_teams(config, payload)
            return ok, status, error, snippet, None
        return False, None, f"Unsupported channel type: {channel_type}", None, None

    # ------------------------------------------------------------------
    # Providers
    # ------------------------------------------------------------------

    async def _http_post(
        self,
        url: str,
        body: bytes,
        headers: Dict[str, str],
        method: str = "POST",
    ) -> Tuple[int, str]:
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(method, url, data=body, headers=headers) as resp:
                text = await resp.text()
                return resp.status, text[:500]

    async def _deliver_webhook(
        self, config: Dict[str, Any], payload: Dict[str, Any], event_type: str
    ) -> Tuple[bool, Optional[int], Optional[str], Optional[str]]:
        url = config.get("url")
        if not url:
            return False, None, "Webhook channel has no 'url' configured", None

        body = json.dumps(payload, default=str).encode("utf-8")
        delivery_id = str(uuid.uuid4())
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "LogForge-Alerts/1.0",
            "X-LogForge-Event": event_type,
            "X-LogForge-Delivery": delivery_id,
        }

        custom_headers = config.get("headers") or {}
        if isinstance(custom_headers, str):
            try:
                custom_headers = json.loads(custom_headers)
            except json.JSONDecodeError:
                custom_headers = {}
        for k, v in custom_headers.items():
            headers[str(k)] = str(v)

        signing_secret = config.get("signing_secret")
        if signing_secret:
            signature = hmac.new(
                str(signing_secret).encode("utf-8"), body, hashlib.sha256
            ).hexdigest()
            headers["X-LogForge-Signature"] = f"sha256={signature}"

        method = str(config.get("method", "POST")).upper()
        status, text = await self._http_post(url, body, headers, method)
        if 200 <= status < 300:
            return True, status, None, text
        return False, status, f"Webhook endpoint returned HTTP {status}: {text[:200]}", text

    async def _deliver_slack(
        self, config: Dict[str, Any], payload: Dict[str, Any]
    ) -> Tuple[bool, Optional[int], Optional[str], Optional[str]]:
        webhook_url = config.get("webhook_url") or config.get("url")
        if not webhook_url:
            return False, None, "Slack channel has no 'webhook_url' configured", None

        severity = str(payload.get("severity", "info")).lower()
        severity_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🔵",
            "info": "⚪",
        }.get(severity, "⚪")

        fields = [
            {"type": "mrkdwn", "text": f"*Severity:*\n{severity.upper()}"},
            {"type": "mrkdwn", "text": f"*Status:*\n{payload.get('status', 'active')}"},
        ]
        if payload.get("rule_name"):
            fields.append({"type": "mrkdwn", "text": f"*Rule:*\n{payload['rule_name']}"})
        if payload.get("triggered_at"):
            fields.append(
                {"type": "mrkdwn", "text": f"*Triggered:*\n{payload['triggered_at']}"}
            )

        slack_body = {
            "text": f"{severity_emoji} LogForge alert: {payload.get('title') or payload.get('rule_name', 'Alert')}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{severity_emoji} {payload.get('title') or payload.get('rule_name', 'LogForge Alert')}"[:150],
                        "emoji": True,
                    },
                },
                {"type": "section", "fields": fields[:10]},
            ],
        }
        if payload.get("description"):
            slack_body["blocks"].append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": str(payload["description"])[:2900]},
                }
            )
        context_bits = []
        if payload.get("alert_id"):
            context_bits.append(f"Alert `{payload['alert_id']}`")
        if payload.get("rule_id"):
            context_bits.append(f"Rule `{payload['rule_id']}`")
        if context_bits:
            slack_body["blocks"].append(
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": " · ".join(context_bits)}],
                }
            )

        body = json.dumps(slack_body).encode("utf-8")
        status, text = await self._http_post(
            webhook_url, body, {"Content-Type": "application/json"}
        )
        # Slack incoming webhooks answer 200 with body "ok" on success.
        if status == 200:
            return True, status, None, text
        return False, status, f"Slack webhook returned HTTP {status}: {text[:200]}", text

    async def _deliver_email(
        self, config: Dict[str, Any], payload: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        recipients = config.get("recipients") or []
        if isinstance(recipients, str):
            recipients = [r.strip() for r in recipients.split(",") if r.strip()]
        if not recipients:
            return False, "Email channel has no 'recipients' configured"

        smtp_host = config.get("smtp_host") or os.getenv("LOGFORGE_SMTP_HOST", "")
        if not smtp_host:
            return False, (
                "SMTP is not configured: set LOGFORGE_SMTP_HOST (and optionally "
                "LOGFORGE_SMTP_PORT/USERNAME/PASSWORD/FROM) or provide smtp_host "
                "in the channel config"
            )
        smtp_port = int(config.get("smtp_port") or os.getenv("LOGFORGE_SMTP_PORT", "587"))
        smtp_user = config.get("smtp_username") or os.getenv("LOGFORGE_SMTP_USERNAME", "")
        smtp_password = config.get("smtp_password") or os.getenv("LOGFORGE_SMTP_PASSWORD", "")
        use_starttls = _env_flag("LOGFORGE_SMTP_STARTTLS", "true")
        from_address = (
            config.get("from_address")
            or os.getenv("LOGFORGE_SMTP_FROM", "")
            or smtp_user
            or "alerts@logforge.local"
        )

        severity = str(payload.get("severity", "info")).upper()
        subject = f"[LogForge {severity}] {payload.get('title') or payload.get('rule_name', 'Alert')}"

        text_lines = [
            f"Alert: {payload.get('title') or payload.get('rule_name', 'Alert')}",
            f"Severity: {severity}",
            f"Status: {payload.get('status', 'active')}",
            f"Triggered at: {payload.get('triggered_at', '')}",
            "",
            str(payload.get("description", "")),
            "",
            f"Alert ID: {payload.get('alert_id', '')}",
            f"Rule ID: {payload.get('rule_id', '')}",
        ]
        # A scheduled search report carries its rows as CSV: send it as a file.
        report_csv = payload.get("csv")
        message = MIMEMultipart("mixed" if report_csv else "alternative")
        message["Subject"] = subject
        message["From"] = from_address
        message["To"] = ", ".join(recipients)
        message.attach(MIMEText("\n".join(text_lines), "plain"))
        if isinstance(report_csv, str) and report_csv:
            attachment = MIMEText(report_csv, "csv", "utf-8")
            attachment.add_header("Content-Disposition", "attachment", filename="report.csv")
            message.attach(attachment)

        def _send_sync() -> None:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=self.timeout_seconds) as server:
                if use_starttls:
                    server.starttls(context=ssl.create_default_context())
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                refused = server.sendmail(from_address, recipients, message.as_string())
                if refused:
                    raise smtplib.SMTPRecipientsRefused(refused)

        try:
            await asyncio.to_thread(_send_sync)
            return True, None
        except (smtplib.SMTPException, OSError) as e:
            return False, f"SMTP delivery failed: {e}"

    async def _deliver_pagerduty(
        self, config: Dict[str, Any], payload: Dict[str, Any]
    ) -> Tuple[bool, Optional[int], Optional[str], Optional[str], Optional[str]]:
        routing_key = config.get("routing_key") or config.get("integration_key")
        if not routing_key:
            return False, None, "PagerDuty channel has no 'routing_key' configured", None, None

        severity_map = {
            "critical": "critical",
            "high": "error",
            "medium": "warning",
            "low": "info",
            "info": "info",
        }
        dedup_key = (
            f"logforge-{payload.get('rule_id', 'norule')}-{payload.get('alert_id', uuid.uuid4())}"
        )
        pd_body = {
            "routing_key": str(routing_key),
            "event_action": "trigger",
            "dedup_key": dedup_key,
            "payload": {
                "summary": (
                    f"{payload.get('title') or payload.get('rule_name', 'LogForge alert')}"
                )[:1024],
                "source": payload.get("source", "logforge"),
                "severity": severity_map.get(
                    str(payload.get("severity", "info")).lower(), "info"
                ),
                "timestamp": payload.get("triggered_at"),
                "custom_details": {
                    "alert_id": payload.get("alert_id"),
                    "rule_id": payload.get("rule_id"),
                    "description": payload.get("description"),
                    "customer_id": payload.get("customer_id"),
                },
            },
        }
        body = json.dumps(pd_body, default=str).encode("utf-8")
        status, text = await self._http_post(
            "https://events.pagerduty.com/v2/enqueue",
            body,
            {"Content-Type": "application/json"},
        )
        if status == 202:
            return True, status, None, text, dedup_key
        return (
            False,
            status,
            f"PagerDuty Events API returned HTTP {status}: {text[:200]}",
            text,
            dedup_key,
        )

    async def _deliver_discord(
        self, config: Dict[str, Any], payload: Dict[str, Any]
    ) -> Tuple[bool, Optional[int], Optional[str], Optional[str]]:
        webhook_url = config.get("webhook_url") or config.get("url")
        if not webhook_url:
            return False, None, "Discord channel has no 'webhook_url' configured", None
        severity = str(payload.get("severity", "info")).upper()
        content = (
            f"**LogForge {severity}**: {payload.get('title') or payload.get('rule_name', 'Alert')}\n"
            f"{payload.get('description', '')}\n"
            f"Alert `{payload.get('alert_id', '')}` · Rule `{payload.get('rule_id', '')}`"
        )
        body = json.dumps({"content": content[:1900]}).encode("utf-8")
        status, text = await self._http_post(
            webhook_url, body, {"Content-Type": "application/json"}
        )
        if 200 <= status < 300:
            return True, status, None, text
        return False, status, f"Discord webhook returned HTTP {status}: {text[:200]}", text

    async def _deliver_teams(
        self, config: Dict[str, Any], payload: Dict[str, Any]
    ) -> Tuple[bool, Optional[int], Optional[str], Optional[str]]:
        webhook_url = config.get("webhook_url") or config.get("url")
        if not webhook_url:
            return False, None, "Teams channel has no 'webhook_url' configured", None
        severity = str(payload.get("severity", "info")).upper()
        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": {"CRITICAL": "d73a49", "HIGH": "e36209", "MEDIUM": "dbab09"}.get(
                severity, "0366d6"
            ),
            "summary": f"LogForge {severity} alert",
            "title": f"LogForge {severity}: {payload.get('title') or payload.get('rule_name', 'Alert')}",
            "text": str(payload.get("description", "")),
            "sections": [
                {
                    "facts": [
                        {"name": "Alert ID", "value": str(payload.get("alert_id", ""))},
                        {"name": "Rule", "value": str(payload.get("rule_name", ""))},
                        {"name": "Triggered", "value": str(payload.get("triggered_at", ""))},
                    ]
                }
            ],
        }
        body = json.dumps(card).encode("utf-8")
        status, text = await self._http_post(
            webhook_url, body, {"Content-Type": "application/json"}
        )
        if 200 <= status < 300:
            return True, status, None, text
        return False, status, f"Teams webhook returned HTTP {status}: {text[:200]}", text

    # ------------------------------------------------------------------
    # Audit trail (alert_notifications_mt)
    # ------------------------------------------------------------------

    async def record_delivery(
        self,
        customer_id: str,
        alert_event_id: str,
        channel_id: str,
        channel_type: str,
        result: DeliveryResult,
    ) -> None:
        """Persist the true outcome of a delivery attempt cycle."""
        notification_type = channel_type if channel_type in _RECORDABLE_TYPES else "webhook"
        try:
            await self.db.execute_query(
                f"""
                INSERT INTO {NOTIFICATIONS_TABLE} (
                    id, alert_event_id, channel_id, notification_type, status,
                    sent_at, delivery_attempts, error_message, customer_id, created_at
                ) VALUES (
                    %(id)s, %(alert_event_id)s, %(channel_id)s, %(notification_type)s,
                    %(status)s, %(sent_at)s, %(delivery_attempts)s, %(error_message)s,
                    %(customer_id)s, %(created_at)s
                )
                """,
                {
                    "id": str(uuid.uuid4()),
                    "alert_event_id": alert_event_id,
                    "channel_id": channel_id,
                    "notification_type": notification_type,
                    "status": "sent" if result.success else "failed",
                    "sent_at": result.delivered_at,
                    "delivery_attempts": result.attempts,
                    "error_message": result.error,
                    "customer_id": customer_id,
                    "created_at": datetime.now(timezone.utc),
                },
            )
        except Exception as e:
            # The delivery result stands either way; a failed audit write must
            # be loud because it also drives outbox dedup.
            logger.error(
                f"Failed to record notification delivery for alert {alert_event_id} "
                f"channel {channel_id}: {e}"
            )

    async def get_notification_stats(self, customer_id: str) -> Dict[str, int]:
        """Real sent/failed counters from the audit table - not fabricated."""
        rows = await self.db.fetch_all(
            f"""
            SELECT status, count() AS cnt
            FROM {NOTIFICATIONS_TABLE}
            WHERE customer_id = %(customer_id)s
            GROUP BY status
            """,
            {"customer_id": customer_id},
        )
        stats = {"sent": 0, "failed": 0, "pending": 0, "delivered": 0}
        for row in rows:
            stats[str(row["status"])] = int(row["cnt"])
        return {
            "notifications_sent": stats["sent"] + stats["delivered"],
            "notifications_failed": stats["failed"],
        }

    async def list_notifications(
        self, customer_id: str, alert_event_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Delivery audit trail for a tenant (optionally one alert)."""
        where = ["customer_id = %(customer_id)s"]
        params: Dict[str, Any] = {"customer_id": customer_id, "limit": int(limit)}
        if alert_event_id:
            where.append("alert_event_id = %(alert_event_id)s")
            params["alert_event_id"] = alert_event_id
        return await self.db.fetch_all(
            f"""
            SELECT id, alert_event_id, channel_id, notification_type, status,
                   sent_at, delivery_attempts, error_message, created_at
            FROM {NOTIFICATIONS_TABLE}
            WHERE {' AND '.join(where)}
            ORDER BY created_at DESC
            LIMIT %(limit)s
            """,
            params,
        )

    # ------------------------------------------------------------------
    # Outbox dispatcher: alert instance -> channel deliveries
    # ------------------------------------------------------------------

    async def start_dispatcher(self) -> None:
        """Start the background dispatcher (no-op unless the gate is on)."""
        if self._dispatcher_task is not None:
            return
        if not notifications_enabled():
            logger.info(
                "Alert notification dispatcher disabled "
                "(set LOGFORGE_NOTIFICATIONS_ENABLED=true to enable delivery)"
            )
            return
        self._running = True
        self._dispatcher_task = asyncio.create_task(self._dispatch_loop())
        logger.info(
            f"Alert notification dispatcher started "
            f"(poll={self.poll_seconds}s, lookback={self.lookback_minutes}m, "
            f"max_attempts={self.max_attempts})"
        )

    async def stop_dispatcher(self) -> None:
        self._running = False
        if self._dispatcher_task is not None:
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except (asyncio.CancelledError, Exception):
                pass
            self._dispatcher_task = None

    async def _dispatch_loop(self) -> None:
        while self._running:
            try:
                await self._dispatch_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Notification dispatch cycle failed: {e}")
            await asyncio.sleep(self.poll_seconds)

    async def _dispatch_cycle(self) -> None:
        """Deliver pending (alert, channel) pairs exactly once."""
        instances = await self.db.fetch_all(
            f"""
            SELECT
                ai.id AS alert_id,
                ai.rule_id AS rule_id,
                ai.customer_id AS customer_id,
                ai.triggered_at AS triggered_at,
                ai.trigger_data AS trigger_data,
                ar.name AS rule_name,
                ar.description AS rule_description,
                ar.severity AS severity,
                ar.notification_channels AS notification_channels
            FROM {ALERT_INSTANCES_TABLE} ai
            INNER JOIN {ALERT_RULES_TABLE} ar
                ON ai.rule_id = ar.id AND ai.customer_id = ar.customer_id
            WHERE ai.triggered_at > now64(3) - INTERVAL %(lookback)s MINUTE
              AND notEmpty(ar.notification_channels)
            ORDER BY ai.triggered_at DESC
            LIMIT 200
            """,
            {"lookback": self.lookback_minutes},
        )
        if not instances:
            return

        alert_ids = [row["alert_id"] for row in instances]
        id_params = {f"aid_{i}": v for i, v in enumerate(alert_ids)}
        placeholders = ", ".join(f"%(aid_{i})s" for i in range(len(alert_ids)))
        delivered_rows = await self.db.fetch_all(
            f"""
            SELECT DISTINCT alert_event_id, channel_id
            FROM {NOTIFICATIONS_TABLE}
            WHERE alert_event_id IN ({placeholders})
            """,
            id_params,
        )
        already = {(r["alert_event_id"], r["channel_id"]) for r in delivered_rows}

        channels_by_customer: Dict[str, Dict[str, Dict[str, Any]]] = {}

        for instance in instances:
            customer_id = instance["customer_id"]
            raw_channels = instance.get("notification_channels") or []
            if isinstance(raw_channels, str):
                try:
                    raw_channels = json.loads(raw_channels)
                except json.JSONDecodeError:
                    raw_channels = []

            if customer_id not in channels_by_customer:
                rows = await self.db.fetch_all(
                    f"""
                    SELECT id, name, channel_type, config, is_enabled
                    FROM {NOTIFICATION_CHANNELS_TABLE}
                    WHERE customer_id = %(customer_id)s
                    """,
                    {"customer_id": customer_id},
                )
                channels_by_customer[customer_id] = {row["id"]: row for row in rows}

            for channel_id in raw_channels:
                pair = (instance["alert_id"], channel_id)
                if pair in already or pair in self._in_flight:
                    continue

                channel = channels_by_customer[customer_id].get(channel_id)
                if channel is None:
                    # Record the failure once so the gap is visible, then stop
                    # retrying a channel that does not exist.
                    missing = DeliveryResult(
                        success=False,
                        channel_id=channel_id,
                        channel_type="webhook",
                        attempts=0,
                        error=f"Notification channel {channel_id} not found",
                    )
                    await self.record_delivery(
                        customer_id, instance["alert_id"], channel_id, "webhook", missing
                    )
                    continue
                if not bool(channel.get("is_enabled", 0)):
                    continue  # user disabled the channel - do not deliver

                self._in_flight.add(pair)
                try:
                    payload = self._build_alert_payload(instance)
                    result = await self.send_to_channel(
                        channel, payload, event_type="alert.triggered"
                    )
                    await self.record_delivery(
                        customer_id,
                        instance["alert_id"],
                        channel_id,
                        str(channel.get("channel_type", "webhook")),
                        result,
                    )
                    if result.success:
                        logger.info(
                            f"Alert {instance['alert_id']} delivered via "
                            f"{channel.get('channel_type')} channel {channel_id} "
                            f"({result.attempts} attempt(s))"
                        )
                    else:
                        logger.error(
                            f"Alert {instance['alert_id']} delivery FAILED via "
                            f"{channel.get('channel_type')} channel {channel_id} "
                            f"after {result.attempts} attempt(s): {result.error}"
                        )
                finally:
                    self._in_flight.discard(pair)

    def _build_alert_payload(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        trigger_data: Dict[str, Any] = {}
        raw = instance.get("trigger_data")
        if isinstance(raw, str) and raw:
            try:
                trigger_data = json.loads(raw)
            except json.JSONDecodeError:
                trigger_data = {"raw": raw[:1000]}
        elif isinstance(raw, dict):
            trigger_data = raw

        triggered_at = instance.get("triggered_at")
        if hasattr(triggered_at, "isoformat"):
            triggered_at = triggered_at.isoformat()

        condition = trigger_data.get("condition_evaluation") or {}
        summary = condition.get("human_readable") if isinstance(condition, dict) else None

        return {
            "event": "alert.triggered",
            "alert_id": instance["alert_id"],
            "rule_id": instance["rule_id"],
            "rule_name": instance.get("rule_name", ""),
            "title": instance.get("rule_name", "LogForge Alert"),
            "description": instance.get("rule_description", "") or summary or "",
            "severity": str(instance.get("severity", "medium")),
            "status": "active",
            "customer_id": instance["customer_id"],
            "triggered_at": triggered_at,
            "condition": summary,
            "matched_log_count": trigger_data.get("log_count")
            or trigger_data.get("matching_logs_count"),
            "source": "logforge",
        }

    # ------------------------------------------------------------------
    # Channel test (always a real delivery - explicit user action)
    # ------------------------------------------------------------------

    async def test_channel(
        self, channel: Dict[str, Any], customer_id: str
    ) -> DeliveryResult:
        """Send a genuine test notification through a channel and record it."""
        now = datetime.now(timezone.utc)
        payload = {
            "event": "test",
            "alert_id": f"test-{uuid.uuid4()}",
            "rule_id": "channel-test",
            "rule_name": "LogForge channel test",
            "title": f"Test notification for channel '{channel.get('name', '')}'",
            "description": (
                "This is a test notification from LogForge. If you can read "
                "this, the channel is configured correctly."
            ),
            "severity": "info",
            "status": "test",
            "customer_id": customer_id,
            "triggered_at": now.isoformat(),
            "source": "logforge",
        }
        result = await self.send_to_channel(
            channel, payload, event_type="test", max_attempts=1
        )
        channel_id = channel.get("id") or channel.get("channel_id") or "unknown"
        await self.record_delivery(
            customer_id,
            payload["alert_id"],
            channel_id,
            str(channel.get("channel_type") or channel.get("type") or "webhook"),
            result,
        )
        return result


# Singleton accessor (mirrors the lazy-construction pattern used elsewhere)
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
