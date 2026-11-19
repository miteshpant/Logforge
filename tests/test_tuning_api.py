"""
Tuning storage and API (Phase 1).

Records live in detection_tuning_mt (ReplacingMergeTree, one row version per
change; deletes are tombstones), per tenant. API:

  GET    /v1/security/tuning                         list the tenant's records
  POST   /v1/security/tuning                         create (validated)
  DELETE /v1/security/tuning/{id}
  GET    /v1/security/rules/{rule_id}/tuning-suggestion
         exclusion proposed from the rule's false-positive detections
"""

import asyncio
import json
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dao.tuning_dao import TuningDAO

T0 = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


class FakeDB:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    async def fetch_all(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        return self.rows

    async def execute_update(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        return True


def dao_with(rows=None):
    dao = TuningDAO.__new__(TuningDAO)
    dao.db = FakeDB(rows)
    return dao


# --- DAO ---------------------------------------------------------------------------

def test_list_reads_the_latest_live_versions_for_the_tenant():
    dao = dao_with([{"id": "x1", "rule_id": "r1", "kind": "exclusion", "spec": '{"conditions": {"a": "1"}}',
                     "reason": "r", "created_by": "u", "created_at": T0, "updated_at": T0}])
    records = asyncio.run(dao.list_records("t1"))
    sql, params = dao.db.calls[0]
    assert "FROM detection_tuning_mt FINAL" in sql and "deleted = 0" in sql
    assert "tenant_id = %(tenant_id)s" in sql and params == {"tenant_id": "t1"}
    assert records[0]["spec"] == {"conditions": {"a": "1"}}


def test_create_inserts_a_validated_record():
    dao = dao_with()
    record = asyncio.run(dao.create("t1", {"rule_id": "r1", "kind": "throttle",
                                           "spec": {"window": "10m", "group_by": ["src_ip"]},
                                           "reason": "noisy"}, "u1"))
    sql, params = dao.db.calls[0]
    assert sql.startswith("INSERT INTO detection_tuning_mt")
    assert params["tenant_id"] == "t1" and params["deleted"] == 0 and params["created_by"] == "u1"
    assert json.loads(params["spec"]) == {"window": "10m", "group_by": ["src_ip"]}
    assert record["id"] == params["id"]


def test_delete_writes_a_tombstone():
    dao = dao_with([{"id": "x1", "rule_id": "r1", "kind": "exclusion", "spec": "{}", "reason": "",
                     "created_by": "u", "created_at": T0, "updated_at": T0}])
    assert asyncio.run(dao.delete("t1", "x1")) is True
    sql, params = dao.db.calls[-1]
    assert sql.startswith("INSERT INTO detection_tuning_mt") and params["deleted"] == 1 and params["id"] == "x1"


def test_delete_of_a_missing_record_is_false():
    assert asyncio.run(dao_with([]).delete("t1", "nope")) is False


def test_detections_are_split_by_verdict():
    rows = [{"status": "false_positive", "raw_log_data": json.dumps({"normalized_log": {"src_ip": "1"}})},
            {"status": "new", "raw_log_data": json.dumps({"src_ip": "2"})},
            {"status": "resolved", "raw_log_data": "not json"}]
    fps, others = asyncio.run(dao_with(rows).detections_by_verdict("t1", "r1"))
    assert fps == [{"src_ip": "1"}] and others == [{"src_ip": "2"}]


# --- API ---------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    import routers.security_api as security_api
    from authn_authz_middleware import get_current_user

    store = {}

    class FakeDAO:
        async def list_records(self, tenant):
            return [r for r in store.values() if r["tenant"] == tenant]

        async def create(self, tenant, record, user_id):
            rid = f"x{len(store) + 1}"
            store[rid] = dict(record, id=rid, tenant=tenant, created_by=user_id)
            return store[rid]

        async def delete(self, tenant, rid):
            return store.pop(rid, None) is not None

        async def detections_by_verdict(self, tenant, rule_id, days=30, limit=500):
            scanner = {"src_ip": "10.0.5.5", "user": "svc_scan"}
            return [scanner] * 4, [{"src_ip": "45.155.205.20", "user": "root"}]

    monkeypatch.setattr(security_api, "_tuning_dao", lambda: FakeDAO())
    app = FastAPI()
    app.include_router(security_api.router)
    app.dependency_overrides[get_current_user] = lambda: type("U", (), {"id": "u1"})()
    return TestClient(app)


H = {"X-Customer-ID": "t1"}


def test_create_list_delete(client):
    created = client.post("/v1/security/tuning", headers=H, json={
        "rule_id": "r1", "kind": "exclusion", "spec": {"conditions": {"src_ip": "10.0.5.5"}}, "reason": "scanner"})
    assert created.status_code == 201, created.text
    rid = created.json()["id"]
    listed = client.get("/v1/security/tuning", headers=H).json()
    assert [r["id"] for r in listed["records"]] == [rid]
    assert client.delete(f"/v1/security/tuning/{rid}", headers=H).status_code == 204
    assert client.delete(f"/v1/security/tuning/{rid}", headers=H).status_code == 404


def test_invalid_records_are_400(client):
    response = client.post("/v1/security/tuning", headers=H, json={"rule_id": "r1", "kind": "throttle",
                                                                    "spec": {"window": "soon"}, "reason": "x"})
    assert response.status_code == 400 and "invalid timespan" in response.json()["detail"]


def test_suggestion_from_false_positives(client):
    response = client.get("/v1/security/rules/r1/tuning-suggestion", headers=H)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["conditions"] == {"src_ip": "10.0.5.5", "user": "svc_scan"}
    assert body["false_positives"] == 4 and body["would_also_suppress"] == 0
    assert body["record"] == {"rule_id": "r1", "kind": "exclusion",
                              "spec": {"conditions": {"src_ip": "10.0.5.5", "user": "svc_scan"}}}
