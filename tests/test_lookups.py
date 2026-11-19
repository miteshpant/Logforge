"""
Lookup tables (Phase 6): CSV files and managed lists a tenant uploads, used
in LogforgeQL by `| lookup` and `inlookup()`.

API, under /v1/query/lookups (queries read / write):

  GET    ""             the tenant's lookups (name, kind, columns, key, rows)
  PUT    /{name}        create or replace: {"csv": "..."} or {"values": [...]}
  GET    /{name}        metadata and the first rows (?limit=)
  POST   /{name}/values add / remove values of a managed list
  DELETE /{name}

A replacement is a new version: queries read the current version, so a
half-written upload is never visible.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import lookup_tables as lt
from lookup_tables import LookupValidationError

H = {"X-Customer-ID": "acme"}
CSV = "user_id,department,manager\nu1,finance,ann\nu2,it,bob\nu3,it,bob\n"


def test_csv_is_parsed_with_the_first_column_as_key():
    columns, key, rows = lt.parse_csv(CSV)
    assert columns == ["user_id", "department", "manager"] and key == "user_id"
    assert rows == {"u1": {"department": "finance", "manager": "ann"}, "u2": {"department": "it", "manager": "bob"},
                    "u3": {"department": "it", "manager": "bob"}}
    assert lt.parse_csv(CSV, key="manager")[2]["bob"] == {"user_id": "u3", "department": "it"}


def test_duplicate_keys_keep_the_last_row_and_blank_keys_are_skipped():
    _, _, rows = lt.parse_csv("ip,label\n1.1.1.1,a\n,x\n1.1.1.1,b\n")
    assert rows == {"1.1.1.1": {"label": "b"}}


@pytest.mark.parametrize("text, message", [
    ("", "empty"),
    ("a,a\n1,2\n", "twice"),
    ("good,bad name\n1,2\n", "bad name"),
    ("a,b\n1,2,3\n", "line 2 has 3 values"),
    ("a\n", "no rows"),
])
def test_bad_csv_is_explained(text, message):
    with pytest.raises(LookupValidationError, match=message):
        lt.parse_csv(text)


def test_limits(monkeypatch):
    monkeypatch.setattr(lt, "MAX_ROWS", 3)
    with pytest.raises(LookupValidationError, match="at most 3 rows"):
        lt.parse_csv("k\n1\n2\n3\n4\n")
    with pytest.raises(LookupValidationError, match="key column"):
        lt.parse_csv(CSV, key="nope")
    with pytest.raises(LookupValidationError, match="name"):
        lt.check_name("bad-name!")


def test_lists_are_single_column_lookups():
    columns, key, rows = lt.parse_list(["10.0.0.1", " 10.0.0.2 ", "", "10.0.0.1"])
    assert columns == ["value"] and key == "value" and rows == {"10.0.0.1": {}, "10.0.0.2": {}}


class MemoryDAO:
    def __init__(self):
        self.tables, self.data = {}, {}

    async def list(self, tenant_id):
        return [t for (tenant, _), t in sorted(self.tables.items()) if tenant == tenant_id]

    async def get(self, tenant_id, name):
        return self.tables.get((tenant_id, name))

    async def save(self, tenant_id, name, kind, columns, key, rows, description, actor):
        previous = self.tables.get((tenant_id, name))
        table = lt.LookupTable(name=name, kind=kind, columns=columns, key=key, row_count=len(rows),
                               version=(previous.version + 1) if previous else 1, description=description,
                               updated_by=actor)
        self.tables[(tenant_id, name)] = table
        self.data[(tenant_id, name)] = rows
        return table

    async def rows(self, tenant_id, table, limit):
        data = self.data[(tenant_id, table.name)]
        return [{table.key: k, **v} for k, v in sorted(data.items())[:limit]]

    async def all_rows(self, tenant_id, table):
        return dict(self.data[(tenant_id, table.name)])

    async def delete(self, tenant_id, name, actor):
        self.tables.pop((tenant_id, name))


@pytest.fixture
def api(monkeypatch):
    import routers.lookups_api as lookups_api
    from authn_authz_middleware import get_current_user

    dao = MemoryDAO()
    monkeypatch.setattr(lookups_api, "_dao", lambda: dao)
    app = FastAPI()
    app.include_router(lookups_api.router)
    app.dependency_overrides[get_current_user] = lambda: type("U", (), {"id": "u1", "email": "dana@acme.example"})()
    client = TestClient(app)
    client.dao = dao
    return client


def test_upload_list_get_replace_delete(api):
    r = api.put("/v1/query/lookups/users", headers=H, json={"csv": CSV, "description": "HR export"})
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 1 and r.json()["row_count"] == 3 and r.json()["key"] == "user_id"
    assert [t["name"] for t in api.get("/v1/query/lookups", headers=H).json()["lookups"]] == ["users"]
    one = api.get("/v1/query/lookups/users?limit=2", headers=H).json()
    assert one["columns"] == ["user_id", "department", "manager"] and len(one["rows"]) == 2
    assert one["rows"][0] == {"user_id": "u1", "department": "finance", "manager": "ann"}
    r = api.put("/v1/query/lookups/users", headers=H, json={"csv": "user_id,department\nu9,ops\n"})
    assert r.json()["version"] == 2 and r.json()["columns"] == ["user_id", "department"]
    assert api.delete("/v1/query/lookups/users", headers=H).status_code == 204
    assert api.get("/v1/query/lookups/users", headers=H).status_code == 404


def test_managed_lists_add_and_remove_values(api):
    api.put("/v1/query/lookups/blocklist", headers=H, json={"values": ["203.0.113.9"]})
    r = api.post("/v1/query/lookups/blocklist/values", headers=H,
                 json={"add": ["198.51.100.7", "198.51.100.8"], "remove": ["203.0.113.9"]})
    assert r.status_code == 200 and r.json()["row_count"] == 2 and r.json()["version"] == 2
    assert sorted(api.dao.data[("acme", "blocklist")]) == ["198.51.100.7", "198.51.100.8"]
    api.put("/v1/query/lookups/users", headers=H, json={"csv": CSV})
    assert api.post("/v1/query/lookups/users/values", headers=H, json={"add": ["x"]}).status_code == 400


@pytest.mark.parametrize("body, status", [
    ({}, 400), ({"csv": "a,a\n1,2"}, 400), ({"csv": CSV, "values": ["x"]}, 400), ({"values": "x"}, 422),
])
def test_bad_uploads(api, body, status):
    assert api.put("/v1/query/lookups/users", headers=H, json=body).status_code == status


def test_bad_names_and_missing_lookups(api):
    assert api.put("/v1/query/lookups/bad-name", headers=H, json={"values": ["x"]}).status_code == 400
    assert api.post("/v1/query/lookups/none/values", headers=H, json={"add": ["x"]}).status_code == 404
    assert api.delete("/v1/query/lookups/none", headers=H).status_code == 404
