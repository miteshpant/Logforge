"""
Ticket sync (Phase 13): a case and its Jira or GitHub ticket follow each
other. Webhooks (signed) or polling bring the ticket's state in; case
changes are pushed out.
"""

import asyncio
import hashlib
import hmac
import json
import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from integrations import sync  # noqa: E402


# -- reading ticket states -----------------------------------------------------------

def test_jira_and_github_webhooks_are_read():
    jira = {"webhookEvent": "jira:issue_updated", "issue": {"key": "SEC-42", "fields": {"status": {
        "name": "Done", "statusCategory": {"key": "done"}}}}}
    assert sync.from_webhook("jira_issue", jira) == ("SEC-42", "closed")
    jira["issue"]["fields"]["status"] = {"name": "In Progress", "statusCategory": {"key": "indeterminate"}}
    assert sync.from_webhook("jira_issue", jira) == ("SEC-42", "open")
    gh = {"action": "closed", "issue": {"number": 7, "state": "closed"}, "repository": {"full_name": "acme/secops"}}
    assert sync.from_webhook("github_issue", gh) == ("acme/secops#7", "closed")
    gh = {"action": "reopened", "issue": {"number": 7, "state": "open"}, "repository": {"full_name": "acme/secops"}}
    assert sync.from_webhook("github_issue", gh) == ("acme/secops#7", "open")
    assert sync.from_webhook("github_issue", {"zen": "ping"}) is None


@pytest.mark.parametrize("link, ticket_state, case_status, expected", [
    # the ticket moved
    ({"ticket_status": "open", "case_status": "investigating"}, "closed", "investigating", "close_case"),
    ({"ticket_status": "closed", "case_status": "resolved"}, "open", "resolved", "reopen_case"),
    # the case moved
    ({"ticket_status": "open", "case_status": "investigating"}, "open", "resolved", "close_ticket"),
    ({"ticket_status": "closed", "case_status": "resolved"}, "closed", "investigating", "reopen_ticket"),
    # nothing to do, or already in step
    ({"ticket_status": "open", "case_status": "new"}, "open", "investigating", None),
    ({"ticket_status": "open", "case_status": "investigating"}, "closed", "resolved", None),
    ({"ticket_status": "open", "case_status": "investigating"}, "closed", "false_positive", None),
])
def test_what_to_do(link, ticket_state, case_status, expected):
    assert sync.decide(link, ticket_state, case_status) == expected


def test_when_both_moved_the_ticket_wins():
    # closed in Jira and reopened in Logforge since the last sync: follow the ticket
    assert sync.decide({"ticket_status": "open", "case_status": "resolved"}, "closed", "investigating") == "close_case"


# -- webhook authentication ---------------------------------------------------------

def test_webhook_signatures():
    body = b'{"a": 1}'
    good = "sha256=" + hmac.new(b"hooksecret", body, hashlib.sha256).hexdigest()
    assert sync.verify({"x-hub-signature-256": good}, {}, body, "hooksecret")
    assert sync.verify({}, {"token": "hooksecret"}, body, "hooksecret")
    assert not sync.verify({"x-hub-signature-256": "sha256=00"}, {}, body, "hooksecret")
    assert not sync.verify({}, {"token": "nope"}, body, "hooksecret")
    assert not sync.verify({}, {}, body, "hooksecret")
    assert not sync.verify({"x-hub-signature-256": good}, {}, body, "")  # no secret configured: refuse


# -- remote calls -----------------------------------------------------------------

JIRA = {"kind": "jira_issue", "config": {"base_url": "https://jira.test", "email": "b@x.test", "project": "SEC"},
        "secrets": {"api_token": "t"}}
GITHUB = {"kind": "github_issue", "config": {"repo": "acme/secops", "base_url": "https://api.github.test"},
          "secrets": {"token": "g"}}


def call(fn, *args, responder):
    requests = []

    def handle(request):
        requests.append(request)
        return responder(request)

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            return await fn(*args, http=http)

    return asyncio.run(go()), requests


@pytest.fixture(autouse=True)
def allow(monkeypatch):
    monkeypatch.setenv("LOGFORGE_ALLOW_PRIVATE_INTEGRATIONS", "true")


def test_jira_status_and_closing_through_a_done_transition():
    def jira(request):
        if request.method == "GET" and request.url.path.endswith("/transitions"):
            return httpx.Response(200, json={"transitions": [
                {"id": "11", "to": {"statusCategory": {"key": "indeterminate"}}},
                {"id": "31", "to": {"statusCategory": {"key": "done"}}}]})
        if request.method == "GET":
            return httpx.Response(200, json={"fields": {"status": {"statusCategory": {"key": "new"}}}})
        return httpx.Response(204)

    state, _ = call(sync.remote_state, JIRA, "SEC-42", responder=jira)
    assert state == "open"
    ok, reqs = call(sync.set_remote, JIRA, "SEC-42", "closed", "Resolved in Logforge", responder=jira)
    assert ok and json.loads(reqs[-1].content)["transition"] == {"id": "31"}


def test_github_status_and_closing():
    def gh(request):
        if request.method == "GET":
            return httpx.Response(200, json={"state": "closed"})
        assert json.loads(request.content)["state"] == "closed"
        return httpx.Response(200, json={})

    state, _ = call(sync.remote_state, GITHUB, "acme/secops#7", responder=gh)
    assert state == "closed"
    ok, reqs = call(sync.set_remote, GITHUB, "acme/secops#7", "closed", "", responder=gh)
    assert ok and reqs[-1].url.path == "/repos/acme/secops/issues/7" and reqs[-1].method == "PATCH"


# -- reconciling a linked case and ticket ------------------------------------------

class Case:
    def __init__(self, status):
        self.status = status


class Cases:
    def __init__(self, status):
        self.case = Case(status)
        self.actions = []

    async def get(self, tenant, case_id):
        return self.case

    async def act(self, tenant, case_id, action, actor, **kw):
        self.actions.append((action, actor, kw))
        self.case = Case(kw["status"])
        return self.case


class Tickets:
    def __init__(self):
        self.links = []

    def link(self, tenant, case_id, ticket, ticket_status, case_status):
        self.links.append((case_id, ticket["ticket"], ticket_status, case_status))


LINK = {"tenant_id": "acme", "case_id": "c1", "ticket": "SEC-42", "url": "u", "system": "jira",
        "integration": "i2", "ticket_status": "open", "case_status": "investigating"}


def test_a_closed_ticket_resolves_the_case_and_records_both_states():
    from integrations.sync_service import reconcile

    cases, tickets = Cases("investigating"), Tickets()

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500))) as http:
            return await reconcile(tickets, cases, JIRA, LINK, "closed", http)

    assert asyncio.run(go()) == "close_case"
    assert cases.actions == [("set_status", "ticket-sync", {"status": "resolved",
                                                            "reason": "Closed in jira: SEC-42"})]
    assert tickets.links == [("c1", "SEC-42", "closed", "resolved")]


def test_a_resolved_case_closes_the_ticket():
    from integrations.sync_service import reconcile

    cases, tickets = Cases("resolved"), Tickets()

    def jira(request):
        if request.url.path.endswith("/transitions") and request.method == "GET":
            return httpx.Response(200, json={"transitions": [{"id": "31", "to": {"statusCategory": {"key": "done"}}}]})
        return httpx.Response(204)

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(jira)) as http:
            return await reconcile(tickets, cases, JIRA, LINK, "open", http)

    assert asyncio.run(go()) == "close_ticket"
    assert cases.actions == [] and tickets.links == [("c1", "SEC-42", "closed", "resolved")]


@pytest.fixture
def hooks(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import routers.integrations_api as module

    class Store:
        client = None

        def get(self, tenant, iid, with_secrets=False):
            if (tenant, iid) != ("acme", "i2"):
                return None
            return {**JIRA, "id": "i2", "secrets": {**JIRA["secrets"], "webhook_secret": "hooksecret"}}

    calls = []

    async def fake_on_webhook(client, cases, tenant, integration, payload, http):
        calls.append((tenant, payload["issue"]["key"]))
        return [{"case_id": "c1", "ticket": "SEC-42", "action": "close_case"}]

    monkeypatch.setattr(module, "_store", lambda: Store())
    monkeypatch.setattr(module, "_cases", lambda: None)
    monkeypatch.setattr("integrations.sync_service.on_webhook", fake_on_webhook)
    app = FastAPI()
    app.include_router(module.hooks_router)
    client = TestClient(app)
    client.calls = calls
    return client


def test_the_webhook_route_needs_the_secret(hooks):
    body = json.dumps({"issue": {"key": "SEC-42", "fields": {"status": {"statusCategory": {"key": "done"}}}}}).encode()
    sig = "sha256=" + hmac.new(b"hooksecret", body, hashlib.sha256).hexdigest()
    assert hooks.post("/v1/hooks/acme/i2", content=body).status_code == 401
    assert hooks.post("/v1/hooks/acme/i2", content=body, headers={"X-Hub-Signature-256": "sha256=bad"}
                      ).status_code == 401
    assert hooks.post("/v1/hooks/acme/nope", content=body, headers={"X-Hub-Signature-256": sig}).status_code == 401
    ok = hooks.post("/v1/hooks/acme/i2", content=body, headers={"X-Hub-Signature-256": sig})
    assert ok.status_code == 202 and ok.json()["synced"][0]["action"] == "close_case"
    assert hooks.post("/v1/hooks/acme/i2?token=hooksecret", content=body).status_code == 202
    assert hooks.calls == [("acme", "SEC-42"), ("acme", "SEC-42")]


def test_hooks_are_public_to_the_middleware_and_nothing_else_is():
    from authn_authz_middleware import UnifiedAuthMiddleware

    mw = UnifiedAuthMiddleware.__new__(UnifiedAuthMiddleware)
    mw.public_endpoints = ["/health"]
    assert mw._is_public_endpoint("/v1/hooks/acme/i2")
    assert not mw._is_public_endpoint("/v1/integrations")
