"""
Actions (Phase 13): what a playbook step or a test from Settings →
Integrations does with an integration.

Each kind declares the configuration and secrets an integration needs and
the inputs a step gives it. Inputs are templates (integrations/templates.py),
rendered against the alert, case and run. Every action returns an
ActionResult; a failing service is a result, not an exception.

Outbound requests go only to public addresses unless the deployment sets
LOGFORGE_ALLOW_PRIVATE_INTEGRATIONS=true (internal Jira, a lab): otherwise a
tenant could point an integration at the cloud metadata service or the
cluster's own ClickHouse.

Containment kinds (disabling a user, blocking an address) act on systems
outside Logforge; a playbook may run one only after a person approves it.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import os
import socket
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from . import templates

TIMEOUT = float(os.getenv("LOGFORGE_ACTION_TIMEOUT_SECONDS", "15"))
PD_SEVERITY = {"critical": "critical", "high": "error", "medium": "warning", "low": "info", "info": "info"}


class ActionError(ValueError):
    pass


@dataclass
class ActionResult:
    ok: bool
    status: Optional[int] = None
    output: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "status": self.status, "output": self.output, "error": self.error}


Runner = Callable[[Dict[str, Any], Dict[str, str], Dict[str, Any], httpx.AsyncClient], Awaitable[ActionResult]]


@dataclass(frozen=True)
class Kind:
    name: str
    label: str
    config: Tuple[str, ...]
    secrets: Tuple[str, ...]
    inputs: Tuple[str, ...]
    run: Runner
    containment: bool = False
    ticket: bool = False  # creates a ticket that can be synced with a case


# -- outbound checks ------------------------------------------------------------

def _allow_private() -> bool:
    return os.getenv("LOGFORGE_ALLOW_PRIVATE_INTEGRATIONS", "false").lower() in ("1", "true", "yes", "on")


def check_url(url: str) -> str:
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ActionError(f"not an http(s) URL: {url!r}")
    if _allow_private():
        return url
    host = parsed.hostname
    if host == "localhost" or host.endswith(".localhost"):
        raise ActionError("integrations may not call this host (local)")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            addresses = [ipaddress.ip_address(a[4][0]) for a in socket.getaddrinfo(host, None)]
        except OSError:
            addresses = []  # unresolvable here: the request itself will fail
    for address in addresses:
        if (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved
                or address.is_multicast or address.is_unspecified):
            raise ActionError(f"integrations may not call private or local addresses ({address}); set "
                              "LOGFORGE_ALLOW_PRIVATE_INTEGRATIONS=true to allow internal services")
    return url


async def _send(http: httpx.AsyncClient, method: str, url: str, **kw) -> Tuple[Optional[httpx.Response], str]:
    check_url(url)
    try:
        response = await http.request(method, url, timeout=TIMEOUT, **kw)
    except httpx.HTTPError as e:
        return None, f"{type(e).__name__}: {e}"
    if response.status_code >= 300:
        return response, f"HTTP {response.status_code}: {response.text[:200]}"
    return response, ""


def _result(response: Optional[httpx.Response], error: str, output: Optional[Dict[str, Any]] = None) -> ActionResult:
    return ActionResult(ok=not error, status=response.status_code if response is not None else None,
                        output=output or {}, error=error)


# -- kinds ----------------------------------------------------------------------

async def _webhook(config, secrets, inputs, http):
    body = json.dumps(inputs.get("body", {}), default=str).encode()
    headers = {"Content-Type": "application/json", "User-Agent": "Logforge-Actions/1.0",
               **{str(k): str(v) for k, v in (config.get("headers") or {}).items()}}
    if secrets.get("signing_secret"):
        digest = hmac.new(secrets["signing_secret"].encode(), body, hashlib.sha256).hexdigest()
        headers["X-Logforge-Signature"] = f"sha256={digest}"
    response, error = await _send(http, str(config.get("method", "POST")).upper(), config["url"],
                                  content=body, headers=headers)
    return _result(response, error)


async def _slack(config, secrets, inputs, http):
    payload: Dict[str, Any] = {"text": inputs.get("text", "")}
    if inputs.get("blocks"):
        payload["blocks"] = inputs["blocks"]
    response, error = await _send(http, "POST", secrets["webhook_url"], json=payload)
    return _result(response, error)


async def _teams(config, secrets, inputs, http):
    payload = {"type": "message", "attachments": [{
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {"type": "AdaptiveCard", "version": "1.4",
                    "body": [{"type": "TextBlock", "wrap": True, "text": inputs.get("text", "")}]}}]}
    response, error = await _send(http, "POST", secrets["webhook_url"], json=payload)
    return _result(response, error)


async def _pagerduty(config, secrets, inputs, http):
    base = config.get("base_url", "https://events.pagerduty.com").rstrip("/")
    severity = PD_SEVERITY.get(str(inputs.get("severity", "warning")).lower(), "warning")
    payload = {"routing_key": secrets["routing_key"], "event_action": inputs.get("event_action", "trigger"),
               "payload": {"summary": inputs.get("summary", "")[:1024], "source": inputs.get("source", "logforge"),
                           "severity": severity}}
    if inputs.get("dedup_key"):
        payload["dedup_key"] = inputs["dedup_key"]
    response, error = await _send(http, "POST", f"{base}/v2/enqueue", json=payload)
    output = {}
    if response is not None and not error:
        output = {"dedup_key": response.json().get("dedup_key", payload.get("dedup_key"))}
    return _result(response, error, output)


async def _opsgenie(config, secrets, inputs, http):
    base = config.get("base_url", "https://api.opsgenie.com").rstrip("/")
    payload = {"message": inputs.get("message", "")[:130], "description": inputs.get("description", ""),
               "priority": inputs.get("priority", "P3"), "alias": inputs.get("alias") or None,
               "tags": inputs.get("tags") or []}
    response, error = await _send(http, "POST", f"{base}/v2/alerts", json={k: v for k, v in payload.items() if v},
                                  headers={"Authorization": f"GenieKey {secrets['api_key']}"})
    output = {"request_id": response.json().get("requestId")} if response is not None and not error else {}
    return _result(response, error, output)


async def _email(config, secrets, inputs, http):
    import asyncio
    import smtplib
    from email.message import EmailMessage

    recipients = inputs.get("to") or config.get("to") or []
    if isinstance(recipients, str):
        recipients = [r.strip() for r in recipients.split(",") if r.strip()]
    if not recipients:
        return ActionResult(False, error="no recipients")
    msg = EmailMessage()
    msg["Subject"] = inputs.get("subject", "Logforge")
    msg["From"] = config.get("from_address") or os.getenv("LOGFORGE_SMTP_FROM", "logforge@localhost")
    msg["To"] = ", ".join(recipients)
    msg.set_content(inputs.get("body", ""))

    def send():
        host = config.get("smtp_host") or os.getenv("LOGFORGE_SMTP_HOST", "")
        if not host:
            raise RuntimeError("SMTP is not configured (smtp_host, or LOGFORGE_SMTP_HOST)")
        with smtplib.SMTP(host, int(config.get("smtp_port") or os.getenv("LOGFORGE_SMTP_PORT", "587")),
                          timeout=TIMEOUT) as smtp:
            if str(config.get("starttls", "true")).lower() != "false":
                smtp.starttls()
            if config.get("username") and secrets.get("password"):
                smtp.login(config["username"], secrets["password"])
            smtp.send_message(msg)

    try:
        await asyncio.to_thread(send)
        return ActionResult(True, output={"recipients": recipients})
    except Exception as e:
        return ActionResult(False, error=f"{type(e).__name__}: {e}")


def _jira_auth(config, secrets) -> Dict[str, str]:
    token = base64.b64encode(f"{config['email']}:{secrets['api_token']}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Accept": "application/json"}


async def _jira_issue(config, secrets, inputs, http):
    base = config["base_url"].rstrip("/")
    fields = {"project": {"key": config["project"]}, "summary": inputs.get("summary", "")[:250],
              "description": inputs.get("description", ""),
              "issuetype": {"name": inputs.get("issue_type") or config.get("issue_type", "Task")}}
    if inputs.get("labels"):
        fields["labels"] = inputs["labels"]
    response, error = await _send(http, "POST", f"{base}/rest/api/2/issue", json={"fields": fields},
                                  headers=_jira_auth(config, secrets))
    output = {}
    if response is not None and not error:
        key = response.json().get("key")
        output = {"ticket": key, "url": f"{base}/browse/{key}", "system": "jira"}
    return _result(response, error, output)


def _github_headers(secrets) -> Dict[str, str]:
    return {"Authorization": f"Bearer {secrets['token']}", "Accept": "application/vnd.github+json"}


async def _github_issue(config, secrets, inputs, http):
    base = config.get("base_url", "https://api.github.com").rstrip("/")
    payload = {"title": inputs.get("title", "")[:250], "body": inputs.get("body", ""),
               "labels": inputs.get("labels") or []}
    response, error = await _send(http, "POST", f"{base}/repos/{config['repo']}/issues", json=payload,
                                  headers=_github_headers(secrets))
    output = {}
    if response is not None and not error:
        data = response.json()
        output = {"ticket": f"{config['repo']}#{data.get('number')}", "number": data.get("number"),
                  "url": data.get("html_url"), "system": "github"}
    return _result(response, error, output)


async def _containment_webhook(config, secrets, inputs, http):
    """Ask an external system (an IdP automation, a firewall's API, a SOAR) to
    contain: {"action": "disable_user"|"block_ip", "target": ..., "reason": ...}."""
    action = inputs.get("action", "")
    if action not in ("disable_user", "block_ip", "isolate_host"):
        return ActionResult(False, error="action must be disable_user, block_ip or isolate_host")
    if not inputs.get("target"):
        return ActionResult(False, error="no target")
    return await _webhook(config, secrets, {"body": {"action": action, "target": inputs["target"],
                                                     "reason": inputs.get("reason", ""),
                                                     "requested_by": inputs.get("requested_by", "")}}, http)


KINDS: Dict[str, Kind] = {k.name: k for k in [
    Kind("webhook", "Webhook", ("url",), (), ("body",), _webhook),
    Kind("slack", "Slack", (), ("webhook_url",), ("text", "blocks"), _slack),
    Kind("teams", "Microsoft Teams", (), ("webhook_url",), ("text",), _teams),
    Kind("pagerduty", "PagerDuty", (), ("routing_key",), ("summary", "severity", "dedup_key", "event_action"),
         _pagerduty),
    Kind("opsgenie", "Opsgenie", (), ("api_key",), ("message", "description", "priority", "alias", "tags"),
         _opsgenie),
    Kind("email", "Email", (), (), ("to", "subject", "body"), _email),
    Kind("jira_issue", "Jira", ("base_url", "email", "project"), ("api_token",),
         ("summary", "description", "issue_type", "labels"), _jira_issue, ticket=True),
    Kind("github_issue", "GitHub Issues", ("repo",), ("token",), ("title", "body", "labels"), _github_issue,
         ticket=True),
    Kind("containment_webhook", "Containment (via your automation)", ("url",), (),
         ("action", "target", "reason"), _containment_webhook, containment=True),
]}
SECRET_KEYS = {"signing_secret", "password"}  # optional secrets some kinds take


def validate(kind: str, config: Dict[str, Any], secrets: Dict[str, str]) -> Kind:
    spec = KINDS.get(kind)
    if spec is None:
        raise ActionError(f"unknown kind {kind!r} (kinds: {', '.join(KINDS)})")
    missing = [k for k in spec.config if not config.get(k)] + [k for k in spec.secrets if not secrets.get(k)]
    if missing:
        raise ActionError(f"{spec.label} needs: {', '.join(missing)}")
    for key in ("url", "base_url"):
        if config.get(key):
            check_url(config[key])
    return spec


async def run(kind: str, config: Dict[str, Any], secrets: Dict[str, str], inputs: Dict[str, Any],
              ctx: Dict[str, Any], http: Optional[httpx.AsyncClient] = None, render: bool = True) -> ActionResult:
    """Render the inputs against the context and run the action. Playbooks
    pass render=False: their inputs are already rendered, and rendering again
    would treat `{{ }}` in alert data (attacker-controlled log text) as a
    template."""
    try:
        spec = validate(kind, config, secrets)
        rendered = templates.render_tree(inputs or {}, ctx) if render else (inputs or {})
    except (ActionError, templates.TemplateError) as e:
        return ActionResult(False, error=str(e))
    if http is not None:
        return await _guard(spec, config, secrets, rendered, http)
    async with httpx.AsyncClient(follow_redirects=False) as client:
        return await _guard(spec, config, secrets, rendered, client)


async def _guard(spec: Kind, config, secrets, inputs, http) -> ActionResult:
    try:
        return await spec.run(config, secrets, inputs, http)
    except ActionError as e:
        return ActionResult(False, error=str(e))
    except Exception as e:  # a bug in one action must not take down a playbook run
        return ActionResult(False, error=f"{type(e).__name__}: {e}")


def describe() -> List[Dict[str, Any]]:
    return [{"kind": k.name, "label": k.label, "config": list(k.config), "secrets": list(k.secrets),
             "inputs": list(k.inputs), "containment": k.containment, "ticket": k.ticket} for k in KINDS.values()]
