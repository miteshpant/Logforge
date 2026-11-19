"""
Field catalogue (Phase 5): every field seen for a tenant, with type, the
services it comes from, cardinality and example values. Drives autocomplete
and the Log Explorer's field sidebar.

* GET /v1/fields: computed from a sample of the most recent events in the
  window (the response says how many). Fields are columns, flattened attrs
  paths (attrs.http.status), and the common-schema fields (ocsf.*) that
  resolve for the sampled events.
* GET /v1/fields/values?field=...: exact top values for one field over the
  window (ClickHouse GROUP BY), with the total and distinct counts.

Both need logs:read.
"""

import json
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from field_catalogue import build_catalogue, top_values_sql

T0 = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)


def row(service, attrs, **cols):
    base = {"ts": T0, "host": "web-01", "service": service, "level": "info", "msg": "m", "status": 0, "src_ip": "",
            "user_id": "", "trace_id": "", "attrs": json.dumps(attrs)}
    return {**base, **cols}


ROWS = [row("nginx", {"http": {"status": 200}, "path": "/a", "bytes": 10}, src_ip="203.0.113.9"),
        row("nginx", {"http": {"status": 404}, "path": "/b", "bytes": 20}, src_ip="203.0.113.10"),
        row("nginx", {"http": {"status": 200}, "path": "/a", "bytes": 30}, src_ip="203.0.113.9"),
        row("sshd", {"user": "root", "result": "failed", "ok": False}, src_ip="198.51.100.7", level="warn")]


def by_name(catalogue):
    return {f["name"]: f for f in catalogue["fields"]}


def test_columns_attrs_paths_and_types():
    fields = by_name(build_catalogue(ROWS))
    assert fields["attrs.http.status"]["type"] == "number" and fields["attrs.http.status"]["present"] == 3
    assert fields["attrs.http.status"]["services"] == ["nginx"]
    assert fields["attrs.path"]["cardinality"] == 2
    assert fields["attrs.path"]["examples"][0] == {"value": "/a", "count": 2}
    assert fields["attrs.ok"]["type"] == "boolean"
    assert fields["src_ip"]["type"] == "ip" and fields["src_ip"]["present"] == 4
    assert fields["level"]["examples"][0] == {"value": "info", "count": 3}
    assert "user_id" not in fields  # empty in every sampled row
    assert fields["attrs.http.status"]["presence_pct"] == 75.0


def test_schema_fields_that_resolve_are_listed():
    fields = by_name(build_catalogue(ROWS))
    assert fields["ocsf.src_endpoint.ip"]["present"] == 4 and fields["ocsf.src_endpoint.ip"]["schema"] is True
    assert fields["ocsf.actor.user.name"]["examples"] == [{"value": "root", "count": 1}]
    assert fields["ocsf.status_id"]["examples"] == [{"value": 2, "count": 1}]
    assert "ocsf.process.cmd_line" not in fields  # nothing in the sample resolves it


def test_cardinality_is_capped_and_examples_limited():
    rows = [row("app", {"request_id": f"r{i}"}) for i in range(600)]
    field = by_name(build_catalogue(rows, max_distinct=500))["attrs.request_id"]
    assert field["cardinality"] == 500 and field["cardinality_capped"] is True and len(field["examples"]) == 5


def test_top_values_sql_binds_the_field_and_filters():
    sql, params = top_values_sql("acme", "attrs.http.status", T0, T0, service="nginx", limit=10)
    assert "customer_id = %(tenant_id)s" in sql and "service = %(service)s" in sql
    assert "http" not in sql.replace("%(", "")  # keys are parameters
    assert params["tenant_id"] == "acme" and params["limit"] == 10
    sql, _ = top_values_sql("acme", "ocsf.actor.user.name", T0, T0)
    assert "coalesce(" in sql
    with pytest.raises(Exception, match="Unknown query field|not in the common schema"):
        top_values_sql("acme", "nope", T0, T0)


class FakeDB:
    def __init__(self):
        self.queries = []

    async def fetch_all(self, sql, params=None):
        self.queries.append((sql, params))
        if "GROUP BY value" in sql:
            return [{"value": "200", "count": 2}, {"value": "404", "count": 1}]
        if "uniq(" in sql:
            return [{"total": 3, "distinct": 2}]
        return ROWS


@pytest.fixture
def api(monkeypatch):
    import routers.fields_api as fields_api
    from authn_authz_middleware import get_current_user

    db = FakeDB()
    monkeypatch.setattr(fields_api, "_db", lambda: db)
    fields_api._cache.clear()
    app = FastAPI()
    app.include_router(fields_api.router)
    app.dependency_overrides[get_current_user] = lambda: type("U", (), {"id": "u1", "email": "x@y"})()
    client = TestClient(app)
    client.db = db
    return client


def test_catalogue_and_values_endpoints(api):
    body = api.get("/v1/fields?window=24h", headers={"X-Customer-ID": "acme"}).json()
    assert body["sampled_events"] == 4 and any(f["name"] == "attrs.http.status" for f in body["fields"])
    sql, params = api.db.queries[0]
    assert "LIMIT %(limit)s" in sql and params["tenant_id"] == "acme"
    values = api.get("/v1/fields/values?field=attrs.http.status&window=1h", headers={"X-Customer-ID": "acme"}).json()
    assert values == {"field": "attrs.http.status", "total": 3, "distinct": 2,
                      "values": [{"value": "200", "count": 2}, {"value": "404", "count": 1}]}
    assert api.get("/v1/fields/values?field=nope", headers={"X-Customer-ID": "acme"}).status_code == 400
    assert api.get("/v1/fields?window=400d", headers={"X-Customer-ID": "acme"}).status_code == 400


def test_fields_need_logs_read():
    from authn_authz_middleware import get_endpoint_permission

    assert get_endpoint_permission("/v1/fields", "GET") == "logs:read:tenant"
    assert get_endpoint_permission("/v1/fields/values", "GET") == "logs:read:tenant"


def test_ingest_internals_and_column_defaults_are_not_fields():
    """Found live: every event listed attrs.processing_version/source_format
    (added by ingest) and ocsf.http_response.code = 0 (the status column's
    default)."""
    rows = [row("app", {"source_format": "json", "processing_version": "smart_v1", "k": 1})]
    fields = by_name(build_catalogue(rows))
    assert "attrs.source_format" not in fields and "attrs.processing_version" not in fields
    assert "ocsf.http_response.code" not in fields and "attrs.k" in fields
