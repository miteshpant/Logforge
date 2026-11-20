"""
Saved and scheduled searches (Phase 6).

A saved search is a LogforgeQL query with a name. Given `every`, it runs on a
schedule over the last `window`. Each run is recorded. It can:

* alert: when the result meets a condition (row count, or a numeric field in
  any row), write an alert instance and deliver it to notification channels,
  at most once per `throttle_minutes`;
* report: send the result (a table, and a CSV) to notification channels,
  every run or only when the alert fires.

API, under /v1/query/searches (queries read / write): list, create, get,
update, delete, POST /{id}/run (run now; a dry run by default) and
GET /{id}/runs.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import saved_searches as ss
from saved_searches import SavedSearch, SearchValidationError

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
BRUTE = {"name": "Brute force", "query": '| where attrs.outcome = "failure" | stats count() as failures by src_ip '
                                          '| where failures > 20',
         "every": "15m", "window": "1h",
         "alert": {"condition": {"kind": "rows", "op": "gt", "value": 0}, "severity": "high",
                   "channels": ["ch-slack"], "throttle_minutes": 60},
         "report": {"channels": ["ch-mail"], "when": "alert"}}


def test_a_definition_is_validated_and_normalised():
    s = SavedSearch.from_dict(BRUTE)
    assert s.id == "brute_force" and s.every_seconds == 900 and s.window_seconds == 3600 and s.enabled
    plain = SavedSearch.from_dict({"name": "errors", "query": "error | stats count()"})
    assert plain.every is None and plain.alert is None and plain.window == "24h"


@pytest.mark.parametrize("change, message", [
    ({"query": ""}, "query"),
    ({"every": "1m"}, "at least 5m"),
    ({"every": "30d"}, "at most 7d"),
    ({"window": "90d"}, "at most 31d"),
    ({"every": "soon"}, "duration"),
    ({"alert": {"condition": {"kind": "rows", "op": "about", "value": 1}}}, "op"),
    ({"alert": {"condition": {"kind": "field", "op": "gt", "value": 1}}}, "field"),
    ({"alert": {"condition": {"kind": "rows", "op": "gt", "value": "x"}}}, "number"),
    ({"alert": {"condition": {"kind": "rows", "op": "gt", "value": 1}, "severity": "spicy"}}, "severity"),
    ({"report": {"channels": [], "when": "always"}}, "channel"),
    ({"report": {"channels": ["c"], "when": "sometimes"}}, "when"),
    ({"name": ""}, "name"),
])
def test_bad_definitions_are_explained(change, message):
    with pytest.raises(SearchValidationError, match=message):
        SavedSearch.from_dict({**BRUTE, **change})


@pytest.mark.parametrize("condition, rows, fired, value", [
    ({"kind": "rows", "op": "gt", "value": 0}, [{"n": 1}], True, 1),
    ({"kind": "rows", "op": "gt", "value": 0}, [], False, 0),
    ({"kind": "rows", "op": "eq", "value": 0}, [], True, 0),  # absence
    ({"kind": "field", "field": "n", "op": "gte", "value": 10}, [{"n": 3}, {"n": 12}], True, 12),
    ({"kind": "field", "field": "n", "op": "gte", "value": 10}, [{"n": 3}, {"n": None}], False, 3),
    ({"kind": "field", "field": "n", "op": "lt", "value": 1}, [{"n": "0.5"}], True, 0.5),
])
def test_conditions(condition, rows, fired, value):
    assert ss.evaluate(ss.Condition.from_dict(condition), rows) == (fired, value)


def test_due_times():
    s = SavedSearch.from_dict(BRUTE)
    assert ss.is_due(s, None, NOW)
    assert not ss.is_due(s, NOW - timedelta(minutes=10), NOW)
    assert ss.is_due(s, NOW - timedelta(minutes=15), NOW)
    assert not ss.is_due(SavedSearch.from_dict({"name": "x", "query": "error"}), None, NOW)  # not scheduled
    assert not ss.is_due(SavedSearch.from_dict({**BRUTE, "enabled": False}), None, NOW)


class FakeStore:
    def __init__(self):
        self.searches, self.runs = {}, []

    async def list(self, tenant_id):
        return [s for (t, _), s in sorted(self.searches.items()) if t == tenant_id]

    async def get(self, tenant_id, search_id):
        return self.searches.get((tenant_id, search_id))

    async def save(self, tenant_id, search, actor):
        old = self.searches.get((tenant_id, search.id))
        search.version = (old.version + 1) if old else 1
        search.updated_by = actor
        self.searches[(tenant_id, search.id)] = search
        return search

    async def delete(self, tenant_id, search_id, actor):
        self.searches.pop((tenant_id, search_id))

    async def scheduled(self):
        return [(t, s) for (t, _), s in sorted(self.searches.items()) if s.every and s.enabled]

    async def record_run(self, tenant_id, run):
        self.runs.append((tenant_id, run))

    async def last_runs(self, tenant_id, search_id=None, limit=1):
        found = [r for t, r in reversed(self.runs) if t == tenant_id and (search_id is None or r.search_id == search_id)]
        return found[:limit]

    async def last_fired(self, tenant_id, search_id):
        fired = [r.run_at for t, r in self.runs if t == tenant_id and r.search_id == search_id and r.alerted]
        return max(fired) if fired else None


class Sinks:
    def __init__(self, rows=None, fail=False):
        self.rows = rows if rows is not None else [{"src_ip": "203.0.113.9", "failures": 42}]
        self.fail = fail
        self.queries, self.alerts, self.sent = [], [], []

    async def execute(self, query, tenant_id, start, end):
        self.queries.append((query, tenant_id, start, end))
        if self.fail:
            raise RuntimeError("Code: 241. Memory limit exceeded")
        return {"rows": self.rows, "columns": list(self.rows[0]) if self.rows else [], "result_type": "table",
                "truncated": False}

    async def alert(self, tenant_id, search, run, result):
        self.alerts.append((tenant_id, search.id, run.value))
        return "alert-1"

    async def send(self, tenant_id, channel_id, payload, event_type):
        self.sent.append((tenant_id, channel_id, event_type, payload))


def runner(store, sinks):
    return ss.Runner(store=store, execute=sinks.execute, alert=sinks.alert, send=sinks.send)


def test_a_due_search_runs_over_its_window_alerts_and_reports():
    store, sinks = FakeStore(), Sinks()
    asyncio.run(store.save("acme", SavedSearch.from_dict(BRUTE), "dana"))
    runs = asyncio.run(runner(store, sinks).run_due(NOW))
    assert len(runs) == 1 and runs[0].fired and runs[0].rows == 1 and runs[0].status == "ok"
    query, tenant, start, end = sinks.queries[0]
    assert tenant == "acme" and end == NOW and end - start == timedelta(hours=1)
    assert sinks.alerts == [("acme", "brute_force", 1)]
    kinds = [(c, e) for _, c, e, _ in sinks.sent]
    assert kinds == [("ch-slack", "search.alert"), ("ch-mail", "search.report")]
    report = sinks.sent[1][3]
    assert report["rows"] == [{"src_ip": "203.0.113.9", "failures": 42}]
    assert report["csv"].splitlines() == ["src_ip,failures", "203.0.113.9,42"]
    assert "Brute force" in report["title"] and report["window"]["end"] == NOW.isoformat()
    # recorded, and not due again until 15 minutes later
    assert len(store.runs) == 1
    assert asyncio.run(runner(store, sinks).run_due(NOW + timedelta(minutes=5))) == []


def test_throttle_suppresses_repeat_alerts_but_still_records_runs():
    store, sinks = FakeStore(), Sinks()
    asyncio.run(store.save("acme", SavedSearch.from_dict(BRUTE), "dana"))
    r = runner(store, sinks)
    asyncio.run(r.run_due(NOW))
    second = asyncio.run(r.run_due(NOW + timedelta(minutes=15)))
    assert second[0].fired and second[0].throttled and len(sinks.alerts) == 1
    assert len(store.runs) == 2
    third = asyncio.run(r.run_due(NOW + timedelta(minutes=61)))
    assert not third[0].throttled and len(sinks.alerts) == 2


def test_quiet_runs_do_not_alert_and_reports_can_go_every_run():
    store, sinks = FakeStore(), Sinks(rows=[])
    asyncio.run(store.save("acme", SavedSearch.from_dict({**BRUTE, "report": {"channels": ["ch-mail"],
                                                                                  "when": "always"}}), "dana"))
    runs = asyncio.run(runner(store, sinks).run_due(NOW))
    assert not runs[0].fired and sinks.alerts == []
    assert [(c, e) for _, c, e, _ in sinks.sent] == [("ch-mail", "search.report")]


def test_a_failed_run_is_recorded_and_never_treated_as_no_results():
    store, sinks = FakeStore(), Sinks(fail=True)
    absence = {**BRUTE, "alert": {"condition": {"kind": "rows", "op": "eq", "value": 0}, "channels": ["ch"]}}
    asyncio.run(store.save("acme", SavedSearch.from_dict(absence), "dana"))
    runs = asyncio.run(runner(store, sinks).run_due(NOW))
    assert runs[0].status == "error" and not runs[0].fired and sinks.alerts == [] and sinks.sent == []
    assert "Memory limit" not in runs[0].error  # database text stays in the logs


def test_one_tenants_searches_are_capped_per_cycle(monkeypatch):
    monkeypatch.setattr(ss, "MAX_RUNS_PER_TENANT_PER_CYCLE", 2)
    store, sinks = FakeStore(), Sinks()
    for i in range(4):
        asyncio.run(store.save("acme", SavedSearch.from_dict({**BRUTE, "name": f"s{i}"}), "dana"))
    asyncio.run(store.save("other", SavedSearch.from_dict(BRUTE), "olga"))
    runs = asyncio.run(runner(store, sinks).run_due(NOW))
    assert sorted(t for t, *_ in [(q[1],) for q in sinks.queries]) == ["acme", "acme", "other"]
    assert len(runs) == 3


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

H = {"X-Customer-ID": "acme"}


@pytest.fixture
def api(monkeypatch):
    import routers.searches_api as searches_api
    from authn_authz_middleware import get_current_user

    store, sinks = FakeStore(), Sinks()
    validated = []

    async def validate(tenant_id, query):
        validated.append(query)
        if "nonsense" in query:
            raise SearchValidationError("Unknown stage: 'nonsense'")

    monkeypatch.setattr(searches_api, "_store", lambda: store)
    monkeypatch.setattr(searches_api, "_runner", lambda: runner(store, sinks))
    monkeypatch.setattr(searches_api, "_validate_query", validate)
    app = FastAPI()
    app.include_router(searches_api.router)
    app.dependency_overrides[get_current_user] = lambda: type("U", (), {"id": "u1", "email": "dana@acme.example"})()
    client = TestClient(app)
    client.store, client.sinks, client.validated = store, sinks, validated
    return client


def test_crud(api):
    r = api.post("/v1/query/searches", headers=H, json=BRUTE)
    assert r.status_code == 201, r.text
    assert r.json()["id"] == "brute_force" and r.json()["version"] == 1 and api.validated == [BRUTE["query"]]
    assert api.post("/v1/query/searches", headers=H, json=BRUTE).status_code == 409
    listed = api.get("/v1/query/searches", headers=H).json()["searches"]
    assert [s["id"] for s in listed] == ["brute_force"] and listed[0]["last_run"] is None
    r = api.put("/v1/query/searches/brute_force", headers=H, json={**BRUTE, "every": "1h"})
    assert r.json()["every"] == "1h" and r.json()["version"] == 2
    assert api.put("/v1/query/searches/nope", headers=H, json=BRUTE).status_code == 404
    assert api.delete("/v1/query/searches/brute_force", headers=H).status_code == 204
    assert api.get("/v1/query/searches/brute_force", headers=H).status_code == 404


def test_invalid_queries_and_definitions_are_400s(api):
    assert api.post("/v1/query/searches", headers=H, json={**BRUTE, "query": "| nonsense"}).status_code == 400
    assert api.post("/v1/query/searches", headers=H, json={**BRUTE, "every": "1m"}).status_code == 400


def test_run_now_is_a_dry_run_unless_asked(api):
    api.post("/v1/query/searches", headers=H, json=BRUTE)
    r = api.post("/v1/query/searches/brute_force/run", headers=H)
    assert r.status_code == 200 and r.json()["run"]["fired"] is True
    assert r.json()["result"]["rows"] == [{"src_ip": "203.0.113.9", "failures": 42}]
    assert api.sinks.alerts == [] and api.sinks.sent == [] and api.store.runs == []
    r = api.post("/v1/query/searches/brute_force/run?dry_run=false", headers=H)
    assert api.sinks.alerts and len(api.store.runs) == 1
    runs = api.get("/v1/query/searches/brute_force/runs", headers=H).json()["runs"]
    assert len(runs) == 1 and runs[0]["trigger"] == "manual" and runs[0]["fired"] is True
    assert api.get("/v1/query/searches", headers=H).json()["searches"][0]["last_run"]["fired"] is True


def test_email_reports_attach_the_csv(monkeypatch):
    """The email channel only sent a text body; a scheduled report's rows go as report.csv."""
    import email
    import smtplib

    from services.notification_service import NotificationService

    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self, context=None):
            pass

        def sendmail(self, sender, recipients, text):
            sent.append(text)
            return {}

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setenv("LOGFORGE_SMTP_HOST", "smtp.example")
    service = NotificationService.__new__(NotificationService)
    service.timeout_seconds = 5
    ok, error = asyncio.run(service._deliver_email(
        {"recipients": ["soc@example.com"]},
        {"title": "Search report: errors", "description": "3 rows", "csv": "a,b\n1,2\n"}))
    assert ok, error
    message = email.message_from_string(sent[0])
    parts = {p.get_filename(): p.get_payload(decode=True) for p in message.walk() if p.get_filename()}
    assert parts == {"report.csv": b"a,b\n1,2\n"}
    assert "3 rows" in sent[0]


def test_alerts_without_a_rule_keep_their_own_severity_and_name():
    """A saved-search alert has no alert rule. The alert list LEFT JOINs rules,
    and ClickHouse fills an unmatched Enum with its first value, so every such
    alert (and any alert whose rule was deleted) was listed as severity low."""
    import json as _json

    from dao.alert_dao import AlertDAO

    class DB:
        async def fetch_one(self, query, params):
            return {"total": 1}

        async def fetch_all(self, query, params):
            return [{"id": "a1", "rule_id": "search:brute_force", "rule_severity": "low", "rule_name": "",
                     "trigger_data": _json.dumps({"title": "Search alert: Brute force", "severity": "high",
                                                  "search_name": "Brute force"})}]

    dao = AlertDAO.__new__(AlertDAO)
    dao.db = DB()
    alert = asyncio.run(dao.list_alert_instances("acme"))["alerts"][0]
    assert alert["severity"] == "high" and alert["rule_name"] == "Brute force"


def test_stored_run_times_are_utc_so_the_scheduler_can_compare_them():
    """The database returns naive datetimes. last_runs passed them on as is, so
    after a search's first run every scheduler tick failed comparing them with
    an aware `now` ("can't subtract offset-naive and offset-aware datetimes"),
    and no scheduled search ran again."""
    from datetime import datetime, timezone

    from saved_searches import SearchStore, is_due

    naive = datetime(2026, 11, 19, 16, 42, 30)

    class DB:
        async def fetch_all(self, query, params):
            return [{"search_id": "s1", "run_at": naive, "window_start": naive, "window_end": naive,
                     "trigger": "schedule", "status": "ok", "rows": 0, "fired": 0, "alerted": 0, "throttled": 0,
                     "value": None, "duration_ms": 1.0, "error": "", "alert_id": ""}]

    run = asyncio.run(SearchStore(DB()).last_runs("acme", "s1"))[0]
    assert run.run_at.tzinfo is not None and run.run_at.replace(tzinfo=None) == naive
    assert run.window_start.tzinfo is not None
    search = SavedSearch.from_dict(BRUTE)  # every 15 minutes
    assert is_due(search, run.run_at, datetime(2026, 11, 19, 17, 0, tzinfo=timezone.utc))
    assert not is_due(search, run.run_at, datetime(2026, 11, 19, 16, 50, tzinfo=timezone.utc))
