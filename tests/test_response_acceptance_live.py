"""
Phase 13 acceptance, against ClickHouse: a high-severity alert starts a
playbook that posts to Slack and opens a Jira ticket linked to the alert's
case; resolving the ticket in Jira (a signed webhook) resolves the case.

Real stores, case service, dispatcher and webhook route; only Slack and Jira
are mocked (httpx.MockTransport). Needs ClickHouse with migrations up to 030
(LOGFORGE_TEST_CLICKHOUSE); skipped otherwise, unless LOGFORGE_REQUIRE_CLICKHOUSE.
"""

import asyncio
import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from test_logql_pipeline_live import _client

PLAYBOOK = """
name: Brute force response
trigger:
  on: alert
  when: alert.severity in ["high", "critical"]
steps:
  - id: notify
    action: {integration: SOC Slack, inputs: {text: "Alert: {{ alert.title }} ({{ alert.severity }})"}}
  - id: ticket
    action: {integration: Jira, inputs: {summary: "{{ alert.title }}", description: "Case {{ case.id }}"}}
    link_case: true
"""


@pytest.fixture(scope="module")
def client():
    client = _client()
    if client is None:
        if os.getenv("LOGFORGE_REQUIRE_CLICKHOUSE"):
            pytest.fail("ClickHouse is required but not reachable")
        pytest.skip("ClickHouse not reachable (set LOGFORGE_TEST_CLICKHOUSE)")
    if not client.query("EXISTS TABLE case_tickets_mt").result_rows[0][0]:
        if os.getenv("LOGFORGE_REQUIRE_CLICKHOUSE"):
            pytest.fail("migration 030 is not applied")
        pytest.skip("migration 030 is not applied")
    return client


class Alerts:
    """The alert lookups CaseService makes, over security_events_mt."""

    def __init__(self, client):
        self.client = client
        self.verdicts = []

    async def get(self, tenant_id, alert_id):
        rows = self.client.query("SELECT * FROM security_events_mt WHERE customer_id = {t:String} AND id = {i:String}",
                                 parameters={"t": tenant_id, "i": alert_id}).named_results()
        return next(iter(rows), None)

    async def set_verdict(self, tenant_id, alert_id, verdict, actor, notes):
        self.verdicts.append((alert_id, verdict))


class Remote:
    """Slack and Jira, as far as the playbook and the sync see them."""

    def __init__(self):
        self.slack, self.jira = [], []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "hooks.slack.test":
            self.slack.append(json.loads(request.content))
            return httpx.Response(200, text="ok")
        if request.url.host == "jira.test":
            self.jira.append((request.method, request.url.path, json.loads(request.content or b"{}")))
            if request.method == "POST" and request.url.path == "/rest/api/2/issue":
                return httpx.Response(201, json={"id": "10001", "key": "SEC-101"})
            return httpx.Response(204)
        return httpx.Response(404)


def test_alert_to_slack_and_jira_and_back(client, monkeypatch):
    host, port = client.url.split("//")[1].split("/")[0].rsplit(":", 1) if hasattr(client, "url") else ("", "")
    if os.getenv("LOGFORGE_TEST_CLICKHOUSE"):
        host, port = os.environ["LOGFORGE_TEST_CLICKHOUSE"].rsplit(":", 1)
    monkeypatch.setenv("CLICKHOUSE_HOST", host or "localhost")
    monkeypatch.setenv("CLICKHOUSE_PORT", port or "8124")
    monkeypatch.setenv("LOGFORGE_ALLOW_PRIVATE_INTEGRATIONS", "true")

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import routers.integrations_api as integrations_api
    from integrations.store import IntegrationStore
    from integrations.tickets import TicketStore
    from playbooks import service
    from playbooks.store import PlaybookStore
    from services.case_service import CaseService

    tenant = f"response-live-{uuid.uuid4().hex[:8]}"
    alert_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).replace(microsecond=0)
    client.insert("security_events_mt", [[
        alert_id, "alert", "ssh_brute_force", "high", "new", "SSH brute force from 203.0.113.7", "",
        json.dumps({"src_ip": "203.0.113.7", "host": "web-1", "user": "root"}), "{}", ["T1110"], [], [],
        now - timedelta(minutes=2), now - timedelta(minutes=2), tenant]],
        column_names=["id", "event_type", "rule_id", "severity", "status", "title", "description", "raw_log_data",
                      "enrichment_data", "mitre_techniques", "investigation_notes", "artifacts", "created_at",
                      "updated_at", "customer_id"])
    alerts = Alerts(client)
    cases = CaseService(alerts=alerts)
    case = asyncio.run(cases.create(tenant, "analyst", "SSH brute force on web-1", alert_ids=[alert_id]))

    integrations = IntegrationStore(client)
    integrations.save(tenant, {"name": "SOC Slack", "kind": "slack", "config": {}},
                      {"webhook_url": "https://hooks.slack.test/services/T0/B0/x"}, "admin")
    jira = integrations.save(tenant, {"name": "Jira", "kind": "jira_issue", "config": {
        "base_url": "https://jira.test", "email": "bot@acme.test", "project": "SEC"}},
        {"api_token": "jira-token", "webhook_secret": "hook-secret"}, "admin")
    PlaybookStore(client).save(tenant, "Brute force response", PLAYBOOK, True, "admin")

    remote = Remote()

    async def run_dispatch():
        async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as http:
            return await service.dispatch(client, runner=service.build_runner(client, http=http), tenants=[tenant])

    report = asyncio.run(run_dispatch())
    assert report["started"] == 1 and not report["errors"], report

    # Slack got the alert; Jira got an issue mentioning the case; the ticket is linked to the case
    assert remote.slack == [{"text": "Alert: SSH brute force from 203.0.113.7 (high)"}]
    created = [body for method, path, body in remote.jira if method == "POST" and path == "/rest/api/2/issue"]
    assert created[0]["fields"]["project"] == {"key": "SEC"} and case.id in created[0]["fields"]["description"]
    links = TicketStore(client).for_case(tenant, case.id)
    assert [(l["ticket"], l["system"], l["ticket_status"]) for l in links] == [("SEC-101", "jira", "open")]
    run = PlaybookStore(client).list_runs(tenant)[0]
    assert run.status == "succeeded"

    # a second tick doesn't start it again
    assert asyncio.run(run_dispatch())["started"] == 0

    # the ticket is resolved in Jira: a signed webhook resolves the case
    monkeypatch.setattr(integrations_api, "_store", lambda: IntegrationStore(client))
    monkeypatch.setattr(integrations_api, "_cases", lambda: cases)
    monkeypatch.setattr(integrations_api, "_http", lambda: httpx.AsyncClient(transport=httpx.MockTransport(remote)))
    app = FastAPI()
    app.include_router(integrations_api.hooks_router)
    body = json.dumps({"webhookEvent": "jira:issue_updated", "issue": {"key": "SEC-101", "fields": {
        "status": {"name": "Done", "statusCategory": {"key": "done"}}}}}).encode()
    signature = "sha256=" + hmac.new(b"hook-secret", body, hashlib.sha256).hexdigest()
    r = TestClient(app).post(f"/v1/hooks/{tenant}/{jira['id']}", content=body,
                             headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"})
    assert r.status_code == 202, r.text
    assert r.json()["synced"] == [{"case_id": case.id, "ticket": "SEC-101", "action": "close_case"}]
    after = asyncio.run(cases.get(tenant, case.id))
    assert after.status == "resolved"
    assert alerts.verdicts == [(alert_id, "resolved")]
    link = TicketStore(client).for_case(tenant, case.id)[0]
    assert (link["ticket_status"], link["case_status"]) == ("closed", "resolved")


def test_report_and_schedules_against_clickhouse(client, monkeypatch):
    if os.getenv("LOGFORGE_TEST_CLICKHOUSE"):
        host, port = os.environ["LOGFORGE_TEST_CLICKHOUSE"].rsplit(":", 1)
        monkeypatch.setenv("CLICKHOUSE_HOST", host)
        monkeypatch.setenv("CLICKHOUSE_PORT", port)
    import reports
    import routers.reports_api as module

    async def coverage(tenant):
        return {"techniques": [], "summary": {"total_techniques": 0, "covered_techniques": 0}}

    monkeypatch.setattr(module, "_client", lambda: client)
    monkeypatch.setattr(module, "_coverage", coverage)
    tenant = f"reports-live-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    client.insert("security_events_mt", [[uuid.uuid4().hex, "alert", "r1", sev, "new", "t", "", "{}", "{}", [], [], [],
                                          now - timedelta(hours=1), now - timedelta(hours=1), tenant]
                                         for sev in ("high", "high", "low")],
                  column_names=["id", "event_type", "rule_id", "severity", "status", "title", "description",
                                "raw_log_data", "enrichment_data", "mitre_techniques", "investigation_notes",
                                "artifacts", "created_at", "updated_at", "customer_id"])
    report = reports.build(asyncio.run(module.gather(tenant, now - timedelta(days=7), now + timedelta(minutes=1))))
    assert dict(report["sections"][1]["rows"]) == {"critical": 0, "high": 2, "medium": 0, "low": 1}
    assert reports.to_pdf(report).startswith(b"%PDF")

    schedule = {"id": "s1", "name": "Weekly\tSOC", "every": "weekly", "hour": 7, "format": "pdf",
                "integration_id": "i1", "recipients": ["a@acme.test"], "enabled": True,
                "last_error": "SMTP said:\n550 no"}
    module._save(tenant, schedule, "admin")
    saved = module._schedules(tenant)
    assert [(s["name"], s["recipients"], s["last_error"]) for s in saved] == \
        [("Weekly\tSOC", ["a@acme.test"], "SMTP said:\n550 no")]
    module._save(tenant, saved[0], "admin", deleted=True)
    assert module._schedules(tenant) == []
