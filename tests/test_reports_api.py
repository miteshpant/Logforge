"""
Reports API (Phase 13): coverage as an ATT&CK Navigator layer, the SOC
report as JSON, CSV or PDF, and scheduled sends with the report attached.
"""

import asyncio
import base64
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))
sys.path.insert(0, os.path.dirname(__file__))

from test_reports import COVERAGE, INPUTS  # noqa: E402


@pytest.fixture
def api(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import routers.reports_api as module
    from tenant_dependencies import get_middleware_tenant_id

    async def coverage(tenant):
        return COVERAGE

    async def gather(tenant, start, end):
        return dict(INPUTS, tenant=tenant, start=start, end=end)

    monkeypatch.setattr(module, "_coverage", coverage)
    monkeypatch.setattr(module, "gather", gather)
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[get_middleware_tenant_id] = lambda: "acme"
    return TestClient(app)


def test_navigator_export(api):
    r = api.get("/v1/reports/attack-navigator")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert {t["techniqueID"] for t in r.json()["techniques"]} == {"T1110", "T1003.001", "T1059", "T1566"}


def test_soc_report_formats(api):
    j = api.get("/v1/reports/soc?days=30").json()
    assert j["sections"][0]["title"] == "Summary" and j["period"]["days"] == 30
    c = api.get("/v1/reports/soc?days=7&format=csv")
    assert c.headers["content-type"].startswith("text/csv") and "# Case response" in c.text
    p = api.get("/v1/reports/soc?format=pdf")
    assert p.headers["content-type"] == "application/pdf" and p.content.startswith(b"%PDF-1.4")
    assert api.get("/v1/reports/soc?format=docx").status_code == 422


def test_a_scheduled_send_attaches_the_report_and_records_it(monkeypatch):
    import routers.reports_api as module
    from integrations import actions

    async def gather(tenant, start, end):
        return dict(INPUTS, tenant=tenant, start=start, end=end)

    class Store:
        def __init__(self, client):
            pass

        def get(self, tenant, iid, with_secrets=False):
            return {"id": iid, "kind": "email", "config": {"host": "smtp.test"}, "secrets": {}}

    sent, saved = [], []

    async def run(kind, config, secrets, inputs, ctx, http=None, render=True):
        sent.append((kind, inputs, render))
        return actions.ActionResult(True, status=250)

    monkeypatch.setattr(module, "gather", gather)
    monkeypatch.setattr(module, "_client", lambda: None)
    monkeypatch.setattr(module, "_save", lambda tenant, s, user, deleted=False: saved.append(s))
    monkeypatch.setattr("integrations.store.IntegrationStore", Store)
    monkeypatch.setattr(actions, "run", run)
    schedule = {"id": "s1", "name": "Weekly SOC", "every": "weekly", "hour": 7, "format": "pdf",
                "integration_id": "i1", "recipients": ["ciso@acme.test"], "enabled": True}
    now = datetime(2026, 11, 23, 7, 30, tzinfo=timezone.utc)
    result = asyncio.run(module.send("acme", schedule, now))
    assert result["ok"]
    kind, inputs, render = sent[0]
    assert kind == "email" and render is False and inputs["to"] == ["ciso@acme.test"]
    attachment = inputs["attachments"][0]
    assert attachment["content_type"] == "application/pdf"
    assert base64.b64decode(attachment["content_b64"]).startswith(b"%PDF")
    assert saved[0]["last_sent"] == now and saved[0]["last_error"] == ""


def test_email_carries_attachments(monkeypatch):
    from integrations import actions

    captured = {}

    class SMTP:
        def __init__(self, host, port, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            pass

        def login(self, u, p):
            pass

        def send_message(self, msg):
            captured["msg"] = msg

    monkeypatch.setattr("smtplib.SMTP", SMTP)
    monkeypatch.setenv("LOGFORGE_ALLOW_PRIVATE_INTEGRATIONS", "true")
    inputs = {"to": ["a@x.test"], "subject": "s", "body": "b", "attachments": [
        {"filename": "r.csv", "content_type": "text/csv", "content_b64": base64.b64encode(b"a,b\n").decode()}]}
    r = asyncio.run(actions.run("email", {"smtp_host": "smtp.test", "smtp_port": 587, "from": "lf@x.test"}, {}, inputs, {},
                                render=False))
    assert r.ok, r.error
    parts = list(captured["msg"].iter_attachments())
    assert parts[0].get_filename() == "r.csv" and parts[0].get_content() == "a,b\n"


def test_permissions():
    from authn_authz_middleware import get_endpoint_permission as perm

    assert perm("/v1/reports/soc", "GET") == "security:read:tenant"
    assert perm("/v1/reports/attack-navigator", "GET") == "security:read:tenant"
    assert perm("/v1/reports/schedules", "GET") == "settings:read:tenant"
    assert perm("/v1/reports/schedules", "POST") == "settings:write:tenant"


def test_coverage_comes_from_the_security_service(monkeypatch):
    # _coverage is replaced in the other tests; this one exercises its real import
    import routers.reports_api as module
    import routers.security_api as security_api

    class Service:
        async def get_mitre_coverage(self, tenant):
            return {"tenant": tenant, **COVERAGE}

    monkeypatch.setattr(security_api, "get_security_service", lambda: Service())
    assert asyncio.run(module._coverage("acme"))["tenant"] == "acme"
