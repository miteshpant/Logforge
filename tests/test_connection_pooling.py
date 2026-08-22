"""
Tests for LF-002 -- one shared ClickHouse client per process.

Measured on the running stack, a single `/v1/logs` request constructed **11**
new ClickHouse clients, because `DatabaseLayer.__init__` called
`clickhouse_connect.get_client(...)` (and table-existence DDL) on every
construction, and DAOs are constructed per request.

Pinned here:
* constructing many DatabaseLayers yields exactly ONE underlying client
  construction (the pooled path);
* `close()` on a pooled layer does NOT close the shared client out from under
  every other consumer;
* table-existence DDL runs at most once per process per service;
* `LOGFORGE_POOLED_DB=false` restores the legacy per-instance behaviour.
"""

import pytest

import database_layer
import utils.connection_pool as connection_pool
from database_layer import DatabaseLayer


class _FakeResult:
    result_rows = []
    column_names = []


class _FakeClient:
    def __init__(self):
        self.closed = False
        self.commands = []

    def command(self, sql, *args, **kwargs):
        self.commands.append(sql)
        return None

    def query(self, sql, *args, **kwargs):
        return _FakeResult()

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _isolated_pool_state(monkeypatch):
    """Fresh shared-client and DDL-guard state for every test."""
    monkeypatch.setattr(connection_pool, "_shared_client", None)
    monkeypatch.setattr(DatabaseLayer, "_TABLES_ENSURED", set())
    yield
    connection_pool._shared_client = None


@pytest.fixture
def counted_pool_client(monkeypatch):
    """Count client constructions through the pool's get_client."""
    constructed = []

    def _fake_get_client(**kwargs):
        client = _FakeClient()
        constructed.append(client)
        return client

    monkeypatch.setattr(
        connection_pool.clickhouse_connect, "get_client", _fake_get_client
    )
    return constructed


def _key(service_name: str) -> str:
    return DatabaseLayer.AUTHORIZED_SERVICES[service_name]


# ---------------------------------------------------------------------------
# One client per process, no matter how many DatabaseLayers are constructed
# ---------------------------------------------------------------------------


def test_many_database_layers_share_one_client(counted_pool_client, monkeypatch):
    monkeypatch.setenv("LOGFORGE_POOLED_DB", "true")

    layers = [
        DatabaseLayer(name, _key(name))
        for name in ("SecurityDAO", "AIDAO", "TenantDAO", "SecurityDAO", "AIDAO")
    ]

    assert len(counted_pool_client) == 1, (
        f"{len(counted_pool_client)} ClickHouse clients constructed for "
        f"{len(layers)} DatabaseLayers; the pool must construct exactly one"
    )
    assert all(layer.client is layers[0].client for layer in layers)


@pytest.mark.asyncio
async def test_close_does_not_close_the_shared_client(counted_pool_client, monkeypatch):
    monkeypatch.setenv("LOGFORGE_POOLED_DB", "true")

    layer = DatabaseLayer("SecurityDAO", _key("SecurityDAO"))
    other = DatabaseLayer("AIDAO", _key("AIDAO"))

    await layer.close()

    assert counted_pool_client[0].closed is False, (
        "closing one DatabaseLayer closed the shared client under every "
        "other consumer in the process"
    )
    # The other consumer's client is still the same live object.
    assert other.client is counted_pool_client[0]


# ---------------------------------------------------------------------------
# DDL runs at most once per process per service
# ---------------------------------------------------------------------------


def test_table_ddl_runs_once_per_service(counted_pool_client, monkeypatch):
    monkeypatch.setenv("LOGFORGE_POOLED_DB", "true")
    monkeypatch.setenv("ALLOW_RUNTIME_DDL", "true")

    DatabaseLayer("UserDAO", _key("UserDAO"))
    commands_after_first = len(counted_pool_client[0].commands)
    assert commands_after_first > 0, "UserDAO issues CREATE TABLE IF NOT EXISTS DDL"

    DatabaseLayer("UserDAO", _key("UserDAO"))
    assert len(counted_pool_client[0].commands) == commands_after_first, (
        "second construction re-issued DDL; it must run once per process"
    )


# ---------------------------------------------------------------------------
# Opt-out flag restores legacy behaviour
# ---------------------------------------------------------------------------


def test_pooling_can_be_disabled(monkeypatch):
    monkeypatch.setenv("LOGFORGE_POOLED_DB", "false")

    constructed = []

    def _fake_get_client(**kwargs):
        client = _FakeClient()
        constructed.append(client)
        return client

    monkeypatch.setattr(
        database_layer.clickhouse_connect, "get_client", _fake_get_client
    )

    first = DatabaseLayer("SecurityDAO", _key("SecurityDAO"))
    second = DatabaseLayer("SecurityDAO", _key("SecurityDAO"))

    assert len(constructed) == 2
    assert first.client is not second.client
