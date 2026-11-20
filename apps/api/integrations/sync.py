"""
Ticket sync (Phase 13): a case and the Jira or GitHub ticket a playbook
created for it follow each other.

- The ticket's state comes in by webhook (POST /v1/hooks/{tenant}/{integration},
  signed with the integration's webhook_secret) or by polling.
- Case changes go out: resolving the case closes the ticket (Jira: a
  transition into the "done" category; GitHub: state closed), reopening it
  reopens the ticket.

Each link records the ticket's and the case's state at the last sync, so
only what moved since then is acted on, and an update doesn't echo back.
When both moved, the ticket wins: whoever closed it there was working the
issue.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any, Dict, Mapping, Optional, Tuple

import httpx

from . import actions

CLOSED_CASE = ("resolved", "false_positive")


def _case_open(status: str) -> bool:
    return status not in CLOSED_CASE


# -- reading ticket states -------------------------------------------------------------

def _jira_state(issue: Mapping[str, Any]) -> str:
    status = ((issue.get("fields") or {}).get("status") or {})
    category = (status.get("statusCategory") or {}).get("key", "")
    return "closed" if category == "done" else "open"


def from_webhook(kind: str, payload: Mapping[str, Any]) -> Optional[Tuple[str, str]]:
    """(ticket, "open"|"closed") from a webhook body, or None if it isn't about an issue."""
    if kind == "jira_issue":
        issue = payload.get("issue") or {}
        return (issue["key"], _jira_state(issue)) if issue.get("key") else None
    if kind == "github_issue":
        issue, repo = payload.get("issue") or {}, (payload.get("repository") or {}).get("full_name")
        if not issue.get("number") or not repo:
            return None
        return f"{repo}#{issue['number']}", ("closed" if issue.get("state") == "closed" else "open")
    return None


def decide(link: Mapping[str, Any], ticket_state: str, case_status: str) -> Optional[str]:
    """close_case | reopen_case | close_ticket | reopen_ticket | None."""
    ticket_moved = ticket_state != link.get("ticket_status")
    case_moved = _case_open(case_status) != _case_open(link.get("case_status") or "new")
    ticket_closed, case_closed = ticket_state == "closed", not _case_open(case_status)
    if ticket_closed == case_closed:
        return None
    if ticket_moved:
        return "close_case" if ticket_closed else "reopen_case"
    if case_moved:
        return "close_ticket" if case_closed else "reopen_ticket"
    return None


# -- webhook authentication ------------------------------------------------------------

def verify(headers: Mapping[str, str], query: Mapping[str, str], body: bytes, secret: str) -> bool:
    """A GitHub-style HMAC signature (X-Hub-Signature-256), or ?token= for systems that can't sign."""
    if not secret:
        return False
    signature = {k.lower(): v for k, v in headers.items()}.get("x-hub-signature-256", "")
    if signature:
        expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    token = query.get("token", "")
    return bool(token) and hmac.compare_digest(token, secret)


# -- remote calls ------------------------------------------------------------------------

def _jira(integration):
    cfg, secrets = integration["config"], integration.get("secrets") or {}
    return cfg["base_url"].rstrip("/"), actions._jira_auth(cfg, secrets)


def _github(integration, ticket: str):
    cfg = integration["config"]
    repo, number = ticket.rsplit("#", 1)
    base = cfg.get("base_url", "https://api.github.com").rstrip("/")
    return f"{base}/repos/{repo}/issues/{number}", actions._github_headers(integration.get("secrets") or {})


async def remote_state(integration: Dict[str, Any], ticket: str, http: httpx.AsyncClient) -> Optional[str]:
    if integration["kind"] == "jira_issue":
        base, headers = _jira(integration)
        response, error = await actions._send(http, "GET", f"{base}/rest/api/2/issue/{ticket}?fields=status",
                                              headers=headers)
        return None if error else _jira_state(response.json())
    if integration["kind"] == "github_issue":
        url, headers = _github(integration, ticket)
        response, error = await actions._send(http, "GET", url, headers=headers)
        return None if error else ("closed" if response.json().get("state") == "closed" else "open")
    return None


async def set_remote(integration: Dict[str, Any], ticket: str, state: str, comment: str,
                     http: httpx.AsyncClient) -> bool:
    if integration["kind"] == "jira_issue":
        base, headers = _jira(integration)
        response, error = await actions._send(http, "GET", f"{base}/rest/api/2/issue/{ticket}/transitions",
                                              headers=headers)
        if error:
            return False
        want = "done" if state == "closed" else ("new", "indeterminate")
        options = [t for t in response.json().get("transitions", [])
                   if ((t.get("to") or {}).get("statusCategory") or {}).get("key") in
                   ((want,) if isinstance(want, str) else want)]
        if not options:
            return False
        body: Dict[str, Any] = {"transition": {"id": options[0]["id"]}}
        if comment:
            body["update"] = {"comment": [{"add": {"body": comment}}]}
        _, error = await actions._send(http, "POST", f"{base}/rest/api/2/issue/{ticket}/transitions",
                                       json=body, headers=headers)
        return not error
    if integration["kind"] == "github_issue":
        url, headers = _github(integration, ticket)
        _, error = await actions._send(http, "PATCH", url, json={"state": state}, headers=headers)
        if not error and comment:
            await actions._send(http, "POST", f"{url}/comments", json={"body": comment}, headers=headers)
        return not error
    return False
