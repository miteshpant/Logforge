"""
Data scopes against ClickHouse (Phase 14): inside a scope, every query on
logs_raw_mt sees only the scope's services, in subqueries and aggregates
too, and a hostile service name stays a string. Also the custom role store.
Needs migration 034 (LOGFORGE_TEST_CLICKHOUSE); skipped otherwise, unless
LOGFORGE_REQUIRE_CLICKHOUSE is set.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from test_logql_pipeline_live import _client


@pytest.fixture(scope="module")
def client():
    client = _client()
    if client is None or not client.query("EXISTS TABLE custom_roles_mt").result_rows[0][0]:
        if os.getenv("LOGFORGE_REQUIRE_CLICKHOUSE"):
            pytest.fail("ClickHouse with migration 034 is required")
        pytest.skip("ClickHouse with migration 034 not reachable")
    import data_scope

    data_scope.install()
    return client


@pytest.fixture(scope="module")
def tenant(client):
    tenant = f"scope-live-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    columns = ["ts", "host", "service", "level", "msg", "trace_id", "span_id", "attrs", "status", "src_ip", "user_id",
               "ingested_at", "severity_num", "facility", "parser_version", "customer_id"]
    rows = [[now - timedelta(minutes=i), "h", service, "info", "m", "", "", json.dumps({}), 0, "", "", now, 0, 16,
             "v1", tenant] for i, service in enumerate(["auth", "auth", "payments-api", "payments-worker", "billing"])]
    client.insert("logs_raw_mt", rows, column_names=columns)
    return tenant


def services(client, tenant):
    return dict(client.query("SELECT service, count() FROM (SELECT * FROM logs_raw_mt WHERE customer_id = "
                             "{t:String}) GROUP BY service", parameters={"t": tenant}).result_rows)


def test_queries_see_only_the_scope(client, tenant):
    from data_scope import DataScope, scoped

    assert services(client, tenant) == {"auth": 2, "payments-api": 1, "payments-worker": 1, "billing": 1}
    with scoped(DataScope(services=("auth", "payments-*"))):
        assert services(client, tenant) == {"auth": 2, "payments-api": 1, "payments-worker": 1}
        total = client.query("SELECT count() FROM logs_raw_mt WHERE customer_id = {t:String}",
                             parameters={"t": tenant}).result_rows[0][0]
        assert total == 4
    with scoped(DataScope(services=())):
        assert services(client, tenant) == {}
    with scoped(DataScope(services=("x') OR 1=1 OR service IN ('billing", "a\\b", "%"))):
        assert services(client, tenant) == {}  # names are values, not SQL; % isn't a wildcard
    assert services(client, tenant)["billing"] == 1  # outside the scope again


def test_the_custom_role_store(client):
    from custom_roles import CustomRole, CustomRoleStore

    tenant = f"roles-live-{uuid.uuid4().hex[:8]}"
    store = CustomRoleStore(client)
    role = store.save(CustomRole(id="", tenant_id=tenant, name="Payments read", permissions=["dashboards:read:tenant"],
                                 services=["payments-*"]), "admin")
    plain = store.save(CustomRole(id="", tenant_id=tenant, name="Reports", permissions=["reports:read:tenant"]), "admin")
    assert [r.name for r in store.list(tenant)] == ["Payments read", "Reports"]
    assert store.get(tenant, plain.id).services is None and store.get(tenant, role.id).services == ["payments-*"]
    store.set_member(tenant, role.id, "u1", "admin", True)
    assert [r.id for r in store.roles_of(tenant, "u1")] == [role.id] and store.members(tenant, role.id) == ["u1"]
    store.set_member(tenant, role.id, "u1", "admin", False)
    assert store.roles_of(tenant, "u1") == [] and store.members(tenant, role.id) == []
    store.save(role, "admin", deleted=True)
    assert [r.name for r in store.list(tenant)] == ["Reports"]
