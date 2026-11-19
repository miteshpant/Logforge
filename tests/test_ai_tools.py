"""
Grounding tools (Phase 8): models see tenant data only through read-only
tools, and each tool call is authorised as the HTTP request it stands for
(`run_query` as POST /v1/query/logql, `get_alert` as a security read, ...),
with the caller's own roles and tenant. A tool's output names what it
used (refs), which the orchestrator turns into citations.
"""

import asyncio

import pytest
from ai import tools
from ai.tools import ToolContext, ToolError
from fastapi import HTTPException

ADMIN = [{"tenant_id": "acme", "role": "tenant_admin"}]
ANALYST = [{"tenant_id": "acme", "role": "security_analyst"}]
VIEWER = [{"tenant_id": "acme", "role": "viewer"}]
OTHER_TENANT_ADMIN = [{"tenant_id": "globex", "role": "tenant_admin"}]


def ctx(roles=ADMIN, tenant="acme"):
    return ToolContext(tenant_id=tenant, user_id="u1", roles=roles)


def run(coro):
    return asyncio.run(coro)


def test_the_tool_list_is_read_only_and_described():
    specs = {s.name: s for s in tools.tool_specs()}
    assert set(specs) == {"run_query", "get_alert", "get_case", "lookup_indicator"}
    for spec in specs.values():
        assert spec.description and spec.input_schema["type"] == "object"
    for tool in tools.TOOLS.values():
        assert tool.endpoint[0] in ("GET", "POST")
        assert not tool.endpoint[1].startswith(("/v1/ai", "/v1/admin"))


def test_run_query_runs_for_the_callers_tenant_and_cites_rows(monkeypatch):
    calls = []

    async def fake_logql(body, customer_id):
        calls.append((body, customer_id))
        return {"logs": [{"ts": f"2026-11-19T10:00:0{i}", "service": "auth", "host": "web-1", "level": "warn",
                          "msg": f"failed login {i}"} for i in range(80)],
                "total_count": 80, "time_range": {"start_time": "a", "end_time": "b"}}

    monkeypatch.setattr(tools, "_logql", fake_logql)
    out = run(tools.execute("run_query", {"query": 'service = "auth" | limit 100', "since": "24h"}, ctx()))
    assert calls == [({"query": 'service = "auth" | limit 100', "since": "24h"}, "acme")]
    assert len(out.data["rows"]) == tools.MAX_ROWS and out.data["truncated"] is True
    assert out.data["total_count"] == 80
    # the result as a whole, and each event row, can be cited
    assert out.refs[0].kind == "query" and out.data["ref"] == 0
    assert out.data["rows"][0]["ref"] == 1 and out.refs[1].kind == "event"
    assert out.refs[1].key == {"ts": "2026-11-19T10:00:00", "service": "auth", "host": "web-1"}
    assert "/observability/logs?" in out.refs[0].link and "/observability/logs?" in out.refs[1].link


def test_aggregate_rows_cite_the_query_only(monkeypatch):
    async def fake_logql(body, customer_id):
        return {"logs": [{"service": "auth", "n": 3}], "result_type": "table", "total_count": 1}

    monkeypatch.setattr(tools, "_logql", fake_logql)
    out = run(tools.execute("run_query", {"query": "| stats count() as n by service"}, ctx()))
    assert [r.kind for r in out.refs] == ["query"] and "ref" not in out.data["rows"][0]


def test_tools_are_authorised_like_their_endpoints(monkeypatch):
    async def fake_logql(body, customer_id):
        raise AssertionError("must not run")

    monkeypatch.setattr(tools, "_logql", fake_logql)
    # an analyst can't POST /v1/query/logql, so the model can't either on their behalf
    with pytest.raises(ToolError, match="queries:write:tenant"):
        run(tools.execute("run_query", {"query": "error"}, ctx(ANALYST)))
    with pytest.raises(ToolError, match="security:read:tenant"):
        run(tools.execute("get_alert", {"alert_id": "a1"}, ctx(VIEWER)))
    # roles for another tenant grant nothing here
    with pytest.raises(ToolError, match="not permitted"):
        run(tools.execute("get_case", {"case_id": "c1"}, ctx(OTHER_TENANT_ADMIN)))


def test_arguments_are_checked(monkeypatch):
    with pytest.raises(ToolError, match="unknown tool"):
        run(tools.execute("delete_everything", {}, ctx()))
    with pytest.raises(ToolError, match="query"):
        run(tools.execute("run_query", {}, ctx()))
    with pytest.raises(ToolError, match="since"):
        run(tools.execute("run_query", {"query": "x", "since": "forever"}, ctx()))
    with pytest.raises(ToolError, match="unexpected"):
        run(tools.execute("get_alert", {"alert_id": "a", "sql": "DROP"}, ctx()))


def test_query_errors_come_back_as_tool_errors(monkeypatch):
    async def bad(body, customer_id):
        raise HTTPException(status_code=400, detail="unknown command `evl`")

    monkeypatch.setattr(tools, "_logql", bad)
    with pytest.raises(ToolError, match="unknown command"):
        run(tools.execute("run_query", {"query": "| evl x = 1"}, ctx()))


def test_alerts_cases_and_indicators(monkeypatch):
    seen = {}

    async def fake_alert(alert_id, tenant_id):
        seen["alert"] = (alert_id, tenant_id)
        if alert_id != "a1":
            return None
        return {"id": "a1", "rule_id": "linux-sudo-root-shell", "title": "Root shell", "severity": "high",
                "created_at": "2026-11-19T10:00:00", "raw_log_data": {"normalized_log": {"msg": "sudo -i"}}}

    async def fake_case(case_id, tenant_id):
        seen["case"] = (case_id, tenant_id)
        return {"case": {"id": "c1", "title": "Brute force on web-1", "status": "open"},
                "alerts": [{"id": "a1", "title": "Root shell"}, {"id": "a2", "title": "Failed logins"}],
                "timeline": [{"kind": "note", "text": "looking"}]}

    async def fake_indicators(value, tenant_id):
        seen["intel"] = (value, tenant_id)
        return [{"indicator_type": "ip", "value": "203.0.113.50", "threat_type": "bruteforce", "confidence": 80,
                 "source": "feed:x", "seen_7d": 12}]

    monkeypatch.setattr(tools, "_alert", fake_alert)
    monkeypatch.setattr(tools, "_case", fake_case)
    monkeypatch.setattr(tools, "_indicators", fake_indicators)

    alert = run(tools.execute("get_alert", {"alert_id": "a1"}, ctx(ANALYST)))
    assert seen["alert"] == ("a1", "acme") and alert.refs[0].kind == "alert" and alert.data["ref"] == 0
    with pytest.raises(ToolError, match="not found"):
        run(tools.execute("get_alert", {"alert_id": "zzz"}, ctx()))

    case = run(tools.execute("get_case", {"case_id": "c1"}, ctx(ANALYST)))
    assert seen["case"] == ("c1", "acme")
    assert [r.kind for r in case.refs] == ["case", "alert", "alert"]
    assert case.refs[0].link == "/security/cases/c1"
    assert case.data["alerts"][1]["ref"] == 2

    intel = run(tools.execute("lookup_indicator", {"value": "203.0.113.50"}, ctx(ANALYST)))
    assert seen["intel"] == ("203.0.113.50", "acme")
    assert intel.refs[0].kind == "indicator" and intel.data["matches"][0]["ref"] == 0
