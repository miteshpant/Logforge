"""
Dashboards from queries (Phase 6).

A widget whose query_definition is {"logql": "..."} is a query panel: the
query runs over the dashboard's time range, with the dashboard's variables
bound as values (never pasted into the query text), and its result is
shaped for the widget type.

Variables are stored with the dashboard:

    {"name": "service", "label": "Service", "type": "query",
     "query": "| stats count() by service", "default": "*", "include_all": true}
    {"name": "env", "type": "custom", "values": ["prod", "staging"], "default": "prod"}
    {"name": "user", "type": "text", "default": ""}

"*" is All: a condition comparing with an All variable is true for every
row, so `where service = $service` shows every service.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import dashboard_queries as dq
import logql_pipeline as lp
from dashboard_queries import VariableError

END = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
START = END - timedelta(hours=24)
VARS = [{"name": "service", "type": "query", "query": "| stats count() by service", "default": "*",
         "include_all": True},
        {"name": "env", "type": "custom", "values": ["prod", "staging"], "default": "prod"},
        {"name": "user", "type": "text", "default": ""}]


def test_variable_definitions_are_validated():
    defs = dq.validate_variables(VARS)
    assert [v["name"] for v in defs] == ["service", "env", "user"] and defs[0]["label"] == "service"


@pytest.mark.parametrize("bad, message", [
    ([{"name": "bad name", "type": "text"}], "name"),
    ([{"name": "a", "type": "magic"}], "type"),
    ([{"name": "a", "type": "custom", "values": []}], "values"),
    ([{"name": "a", "type": "custom", "values": ["x"], "default": "y"}], "default"),
    ([{"name": "a", "type": "query"}], "query"),
    ([{"name": "a", "type": "text"}, {"name": "a", "type": "text"}], "twice"),
    ([{"name": "a", "type": "custom", "values": ["x"], "default": "*"}], "include_all"),
])
def test_bad_variables_are_explained(bad, message):
    with pytest.raises(VariableError, match=message):
        dq.validate_variables(bad)


def test_values_come_from_the_request_or_the_default():
    defs = dq.validate_variables(VARS)
    assert dq.resolve(defs, {}) == {"service": lp.ALL, "env": "prod", "user": ""}
    assert dq.resolve(defs, {"service": "api", "env": "staging", "user": "root"}) == \
        {"service": "api", "env": "staging", "user": "root"}
    with pytest.raises(VariableError, match="env must be one of"):
        dq.resolve(defs, {"env": "dev"})
    with pytest.raises(VariableError, match="All"):
        dq.resolve(defs, {"env": "*"})


def test_all_makes_comparisons_true_and_values_stay_bound():
    q = lp.compile_pipeline('| where service = $service and level in $levels | stats count() as n',
                            customer_id="acme", start=START, end=END,
                            variables={"service": lp.ALL, "levels": lp.ALL})
    assert "(1 AND 1)" in q.sql
    q = lp.compile_pipeline('| where service = $service | stats count() as n', customer_id="acme", start=START,
                            end=END, variables={"service": "api') OR 1=1 --"})
    assert "OR 1=1" not in q.sql and "api') OR 1=1 --" in q.params.values()
    with pytest.raises(lp.PipelineError, match="All"):
        lp.compile_pipeline("| eval x = upper($service)", customer_id="acme", start=START, end=END,
                            variables={"service": lp.ALL})


ROWS_TABLE = {"columns": ["service", "n"], "rows": [{"service": "api", "n": 5}, {"service": "web", "n": 3}],
              "result_type": "table", "truncated": False}
ROWS_TIME = {"columns": ["_time", "service", "count"], "result_type": "timechart", "truncated": False,
             "rows": [{"_time": "t1", "service": "api", "count": 1}, {"_time": "t1", "service": "web", "count": 2},
                      {"_time": "t2", "service": "api", "count": 3}]}


def test_results_are_shaped_for_each_widget_type():
    assert dq.shape("table", ROWS_TABLE)["columns"] == ["service", "n"]
    stat = dq.shape("metric", {"columns": ["n"], "rows": [{"n": 1234.5}], "result_type": "table"})
    assert stat["value"] == 1234.5 and stat["formatted_value"] == "1,234.5" and stat["label"] == "n"
    assert dq.shape("metric", {"columns": ["n"], "rows": [], "result_type": "table"})["value"] is None
    bar = dq.shape("bar_chart", ROWS_TABLE)
    assert bar["labels"] == ["api", "web"] and bar["series"] == [{"name": "n", "data": [5, 3]}]
    line = dq.shape("line_chart", ROWS_TIME)
    assert line["labels"] == ["t1", "t2"]
    assert line["series"] == [{"name": "api", "data": [1, 3]}, {"name": "web", "data": [2, 0]}]
    for shaped in (bar, line, stat):
        assert shaped["result"]["columns"]  # the raw result is always there


def test_a_query_panel_runs_with_the_dashboards_window_and_variables(monkeypatch):
    calls = []

    async def execute(query, tenant, start, end, variables):
        calls.append((query, tenant, start, end, variables))
        return ROWS_TABLE

    monkeypatch.setattr(dq, "_execute", execute)
    widget = {"id": "w1", "type": "bar_chart", "query_definition": {"logql": "| where env = $env | stats count() as n by service"}}
    data = asyncio.run(dq.panel_data(widget, "acme", START, END, {"env": "prod", "service": lp.ALL}))
    assert calls == [(widget["query_definition"]["logql"], "acme", START, END, {"env": "prod", "service": lp.ALL})]
    assert data["labels"] == ["api", "web"]


def test_panel_errors_are_reported_on_the_panel(monkeypatch):
    from fastapi import HTTPException

    async def bad(*a):
        raise HTTPException(status_code=400, detail="Unknown stage: 'x'")

    async def broken(*a):
        raise RuntimeError("Code: 60. Table logforge.secret_table doesn't exist")

    widget = {"id": "w1", "type": "table", "query_definition": {"logql": "| x"}}
    monkeypatch.setattr(dq, "_execute", bad)
    assert asyncio.run(dq.panel_data(widget, "acme", START, END, {})) == {"error": "Unknown stage: 'x'"}
    monkeypatch.setattr(dq, "_execute", broken)
    error = asyncio.run(dq.panel_data(widget, "acme", START, END, {}))["error"]
    assert "secret_table" not in error


def test_query_variable_options(monkeypatch):
    async def execute(query, tenant, start, end, variables):
        return {"columns": ["service", "count"], "rows": [{"service": "web", "count": 1}, {"service": "api", "count": 9},
                                                           {"service": None, "count": 1}], "result_type": "table"}

    monkeypatch.setattr(dq, "_execute", execute)
    defs = dq.validate_variables(VARS)
    options = asyncio.run(dq.options(defs, "acme", START, END))
    assert options == {"service": ["*", "api", "web"], "env": ["prod", "staging"], "user": []}


# ---------------------------------------------------------------------------
# Router: variables are stored with the dashboard, data takes var-<name>
# ---------------------------------------------------------------------------

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

H = {"X-Customer-ID": "acme"}


class FakeService:
    def __init__(self):
        self.dashboards, self.widgets, self.data_calls = {}, {}, []

    async def create_dashboard(self, data):
        self.dashboards["d1"] = {**data, "id": "d1", "widgets": []}
        return {"status": "created", "dashboard_id": "d1"}

    async def update_dashboard(self, dashboard_id, customer_id, data):
        self.dashboards[dashboard_id].update(data)
        return {"status": "updated", "dashboard_id": dashboard_id}

    async def get_dashboard(self, dashboard_id, customer_id):
        d = self.dashboards.get(dashboard_id)
        return {**d, "widgets": list(self.widgets.values())} if d else None

    async def create_widget(self, data):
        self.widgets["w1"] = {**data, "id": "w1"}
        return {"status": "created", "widget_id": "w1"}

    async def update_widget(self, widget_id, customer_id, data):
        self.widgets[widget_id].update(data)
        return {"status": "updated"}

    async def get_dashboard_data(self, dashboard_id, customer_id, time_range, variables=None):
        self.data_calls.append((time_range, variables))
        return {"dashboard_id": dashboard_id, "widgets": []}


@pytest.fixture
def api(monkeypatch):
    import routers.dashboard as dashboard

    service = FakeService()
    validated = []

    async def validate(query, tenant, variables=None):
        validated.append((query, variables))
        if "nonsense" in query:
            raise ValueError("Unknown stage: 'nonsense'")

    monkeypatch.setattr(dashboard, "get_dashboard_service", lambda: service)
    monkeypatch.setattr("routers.query.validate_pipeline_text", validate)
    app = FastAPI()
    app.include_router(dashboard.router)
    client = TestClient(app)
    client.service, client.validated = service, validated
    return client


def test_variables_are_saved_validated_and_returned(api):
    r = api.post("/v1/dashboards", headers=H, json={"name": "Ops", "variables": VARS})
    assert r.status_code == 200, r.text
    assert [v["name"] for v in api.service.dashboards["d1"]["filters"]] == ["service", "env", "user"]
    assert [v["name"] for v in api.get("/v1/dashboards/d1", headers=H).json()["variables"]] == ["service", "env", "user"]
    bad = api.put("/v1/dashboards/d1", headers=H, json={"name": "Ops", "variables": [{"name": "x y"}]})
    assert bad.status_code == 400


def test_query_widgets_are_compiled_with_the_dashboards_variables(api):
    api.post("/v1/dashboards", headers=H, json={"name": "Ops", "variables": VARS})
    ok = api.post("/v1/dashboards/d1/widgets", headers=H,
                  json={"name": "By service", "type": "bar_chart",
                        "query_definition": {"logql": "| where env = $env | stats count() by service"}})
    assert ok.status_code == 200, ok.text
    assert api.validated[-1] == ("| where env = $env | stats count() by service",
                                 {"service": "x", "env": "x", "user": "x"})
    bad = api.post("/v1/dashboards/d1/widgets", headers=H,
                   json={"name": "x", "type": "table", "query_definition": {"logql": "| nonsense"}})
    assert bad.status_code == 400 and "nonsense" in bad.json()["detail"]


def test_data_takes_var_parameters(api):
    api.post("/v1/dashboards", headers=H, json={"name": "Ops", "variables": VARS})
    r = api.get("/v1/dashboards/d1/data?start_time=2026-11-18T12:00:00Z&end_time=2026-11-19T12:00:00Z"
                "&var-service=api&var-env=staging", headers=H)
    assert r.status_code == 200, r.text
    time_range, variables = api.service.data_calls[-1]
    assert variables == {"service": "api", "env": "staging", "user": ""}
    assert time_range["end_time"] == END
    api.get("/v1/dashboards/d1/data", headers=H)
    assert api.service.data_calls[-1][1]["service"] is lp.ALL
    assert api.get("/v1/dashboards/d1/data?var-env=dev", headers=H).status_code == 400


def test_variable_options_endpoint(api, monkeypatch):
    async def fake_options(defs, tenant, start, end):
        return {v["name"]: ["*"] for v in defs}

    monkeypatch.setattr(dq, "options", fake_options)
    api.post("/v1/dashboards", headers=H, json={"name": "Ops", "variables": VARS})
    r = api.get("/v1/dashboards/d1/variables", headers=H).json()
    assert [v["name"] for v in r["variables"]] == ["service", "env", "user"] and r["options"]["env"] == ["*"]


def test_the_service_runs_query_panels(monkeypatch):
    from services.dashboard_service import DashboardService

    seen = []

    async def panel(widget, tenant, start, end, variables):
        seen.append((widget["id"], tenant, end - start, variables))
        return {"value": 1}

    monkeypatch.setattr(dq, "panel_data", panel)
    service = DashboardService.__new__(DashboardService)
    widget = {"id": "w1", "type": "metric", "query_definition": {"logql": "| stats count() as n"}}
    data = asyncio.run(service._generate_widget_data(widget, "acme", {"start_time": START, "end_time": END},
                                                     variables={"env": "prod"}))
    assert data == {"value": 1} and seen == [("w1", "acme", timedelta(hours=24), {"env": "prod"})]


def test_widgets_accept_the_time_range_the_router_passes(monkeypatch):
    """Found here: the data endpoint parses start/end into datetimes, but the
    service called str.replace on them, so every custom widget returned an
    error whenever the UI sent a time range (it always does)."""
    from services.dashboard_service import DashboardService

    class DAO:
        async def get_metric_data(self, customer_id, query_definition, start, end):
            return {"value": 7, "window": (start, end)}

    service = DashboardService.__new__(DashboardService)
    service.dashboard_dao = DAO()
    data = asyncio.run(service._generate_widget_data({"id": "w", "type": "metric", "query_definition": {}}, "acme",
                                                     {"start_time": START, "end_time": END}))
    assert data["value"] == 7 and data["window"] == (START, END)
