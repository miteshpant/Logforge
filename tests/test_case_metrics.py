"""
SLA metrics and the SOC overview (Phase 2), plus the audit export.

case_metrics(cases, now) reports, per severity, mean and median time to
acknowledge and to resolve (merged cases excluded), open cases by status,
ageing of open cases, analyst load, alerts per case, and SLA breaches against
per-severity targets (acknowledge: critical 15 min, high 1 h, medium 4 h,
low 24 h; resolve: critical 4 h, high 24 h, medium 3 d, low 7 d).
"""

import csv
import io
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from case_metrics import SLA_TARGETS, case_metrics, events_to_csv
from cases import new_case

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


def case(severity="high", created=timedelta(hours=-10), ack=None, resolved=None, status="new", assignee=None,
         alerts=1, merged_into=""):
    c, _ = new_case("acme", "x", "system", NOW + created, severity=severity)
    return replace(c, status=status, assignee=assignee, alert_ids=[f"a{i}" for i in range(alerts)],
                   acknowledged_at=NOW + created + ack if ack is not None else None,
                   resolved_at=NOW + created + resolved if resolved is not None else None,
                   merged_into=merged_into)


CASES = [
    case("critical", ack=timedelta(minutes=10), resolved=timedelta(hours=2), status="resolved", alerts=4),
    case("critical", ack=timedelta(minutes=30), resolved=timedelta(hours=6), status="false_positive", alerts=2),
    case("high", created=timedelta(hours=-3), ack=timedelta(minutes=20), status="investigating", assignee="bob"),
    case("high", created=timedelta(minutes=-30), status="new"),
    case("medium", created=timedelta(days=-8), status="new", assignee="bob", alerts=3),
    case("low", ack=timedelta(minutes=1), resolved=timedelta(minutes=5), status="resolved", merged_into="x"),
]


@pytest.fixture
def report():
    return case_metrics(CASES, NOW)


def test_time_to_acknowledge_and_resolve_per_severity(report):
    critical = report["by_severity"]["critical"]
    assert critical["cases"] == 2
    assert critical["mtta_minutes"] == {"mean": 20.0, "median": 20.0, "count": 2}
    assert critical["mttr_minutes"] == {"mean": 240.0, "median": 240.0, "count": 2}
    assert report["by_severity"]["high"]["mtta_minutes"]["count"] == 1
    assert report["by_severity"]["low"]["cases"] == 0  # merged cases don't count


def test_open_cases_ageing_and_load(report):
    assert report["open_by_status"] == {"new": 2, "investigating": 1, "contained": 0}
    assert report["open_total"] == 3
    assert report["ageing"] == {"<1h": 1, "1-4h": 1, "4-24h": 0, "1-7d": 0, ">7d": 1}
    assert report["analyst_load"] == {"bob": 2, "unassigned": 1}


def test_alerts_per_case(report):
    assert report["alerts"] == 11 and report["alerts_per_case"] == round(11 / 5, 2)


def test_sla_breaches(report):
    breaches = report["sla_breaches"]
    # critical #2 acknowledged after 30 min (> 15) and resolved after 6 h (> 4 h)
    assert breaches["acknowledge"]["critical"] == 1 and breaches["resolve"]["critical"] == 1
    # the unacknowledged high case is 30 min old (< 1 h): not yet breached;
    # the medium case is 8 days old and unacknowledged: breached on both
    assert breaches["acknowledge"]["high"] == 0
    assert breaches["acknowledge"]["medium"] == 1 and breaches["resolve"]["medium"] == 1
    assert SLA_TARGETS["acknowledge"]["critical"] == timedelta(minutes=15)


def test_empty():
    report = case_metrics([], NOW)
    assert report["open_total"] == 0 and report["alerts_per_case"] == 0.0
    assert report["by_severity"]["high"]["mtta_minutes"] == {"mean": None, "median": None, "count": 0}


def test_events_to_csv():
    events = [{"ts": "2026-11-18T09:00:00+00:00", "case_id": "c1", "actor": "alice", "kind": "comment",
               "id": "e1", "data": {"text": "hi, \"there\"", "mentions": []}}]
    rows = list(csv.reader(io.StringIO(events_to_csv(events))))
    assert rows[0] == ["ts", "case_id", "event_id", "actor", "kind", "data"]
    assert rows[1][:5] == ["2026-11-18T09:00:00+00:00", "c1", "e1", "alice", "comment"]
    assert rows[1][5] == '{"text": "hi, \\"there\\"", "mentions": []}'


# --- API -----------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    import routers.cases_api as cases_api
    from authn_authz_middleware import get_current_user

    calls = {}

    class Service:
        async def metrics(self, tenant_id, days):
            calls["metrics"] = (tenant_id, days)
            return case_metrics(CASES, NOW)

        async def audit(self, tenant_id, start, end, limit):
            calls["audit"] = (tenant_id, start, end, limit)
            return [{"ts": "2026-11-18T09:00:00+00:00", "case_id": "c1", "id": "e1", "actor": "alice",
                     "kind": "created", "data": {"title": "x"}}]

    monkeypatch.setattr(cases_api, "_case_service", lambda: Service())
    app = FastAPI()
    app.include_router(cases_api.router)
    app.dependency_overrides[get_current_user] = lambda: type("U", (), {"id": "u1"})()
    c = TestClient(app)
    c.calls = calls
    return c


H = {"X-Customer-ID": "acme"}


def test_metrics_endpoint(client):
    body = client.get("/v1/security/cases/metrics?days=7", headers=H).json()
    assert body["open_total"] == 3 and client.calls["metrics"] == ("acme", 7)


def test_audit_export_json_and_csv(client):
    body = client.get("/v1/security/cases/audit/export?start=2026-11-17T00:00:00Z&end=2026-11-19T00:00:00Z",
                      headers=H).json()
    assert body["events"][0]["kind"] == "created" and body["count"] == 1
    tenant, start, end, limit = client.calls["audit"]
    assert tenant == "acme" and (end - start) == timedelta(days=2)
    response = client.get("/v1/security/cases/audit/export?format=csv", headers=H)
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert response.text.splitlines()[0] == "ts,case_id,event_id,actor,kind,data"


def test_audit_export_range_is_bounded(client):
    response = client.get("/v1/security/cases/audit/export?start=2025-01-01T00:00:00Z&end=2026-11-19T00:00:00Z",
                          headers=H)
    assert response.status_code == 400 and "366 days" in response.json()["detail"]
