"""
Tests for LF-001 -- /health must not cry wolf about ClickHouse.

`_check_clickhouse_health` did `result[0] != 1`, but `DatabaseLayer.fetch_one`
returns a dict -- so the check raised `KeyError: 0` on every call, the broad
`except` in `get_overall_health` reported ClickHouse "unhealthy", and
`/health/ready` returned 503 while the database was demonstrably fine. Under
Kubernetes that fails the readiness probe and removes healthy pods from
service.

Pinned here:
* the check passes when `fetch_one` returns `{"health_check": 1}`;
* it fails when `fetch_one` returns `{}` or `None`;
* a coding error (KeyError) inside a check surfaces as a distinct
  `check_error` status, never as `unhealthy`.
"""

import pytest

import services.health_service as health_service_module
from database_layer import DatabaseError
from services.health_service import HealthService


class _FakeDB:
    """Stands in for DatabaseLayer; fetch_one returns dicts, as the real one does."""

    def __init__(self, health_row):
        self._health_row = health_row

    async def fetch_one(self, query, params=None):
        if "health_check" in query:
            return self._health_row
        # _verify_critical_tables issues `SELECT count() as cnt FROM <table>`
        return {"cnt": 0}


@pytest.fixture
def fake_db_factory(monkeypatch):
    """Patch DatabaseLayer construction inside health_service."""

    def _install(health_row):
        monkeypatch.setattr(
            health_service_module,
            "DatabaseLayer",
            lambda service_name, service_key: _FakeDB(health_row),
        )

    return _install


# ---------------------------------------------------------------------------
# _check_clickhouse_health treats fetch_one's dict correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clickhouse_check_passes_on_dict_row(fake_db_factory):
    fake_db_factory({"health_check": 1})
    result = await HealthService()._check_clickhouse_health()
    assert result["status"] == "healthy"


@pytest.mark.asyncio
async def test_clickhouse_check_fails_on_empty_dict(fake_db_factory):
    fake_db_factory({})
    result = await HealthService()._check_clickhouse_health()
    assert result["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_clickhouse_check_fails_on_none(fake_db_factory):
    fake_db_factory(None)
    result = await HealthService()._check_clickhouse_health()
    assert result["status"] == "unhealthy"


# ---------------------------------------------------------------------------
# A bug inside a check must not masquerade as an outage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_keyerror_in_check_reports_check_error_not_unhealthy(monkeypatch):
    service = HealthService()

    async def _broken_check():
        raise KeyError(0)

    monkeypatch.setattr(service, "_check_clickhouse_health", _broken_check)

    health = await service.get_overall_health()

    assert health["services"]["clickhouse"] == "check_error"
    assert health["services"]["database"] == "check_error"
    # A coding error degrades observability but is not a service outage:
    # /health/ready 503s only on "unhealthy".
    assert health["status"] != "unhealthy"


@pytest.mark.asyncio
async def test_real_database_error_still_reports_unhealthy(monkeypatch):
    service = HealthService()

    async def _down_check():
        raise DatabaseError("connection refused")

    monkeypatch.setattr(service, "_check_clickhouse_health", _down_check)

    health = await service.get_overall_health()

    assert health["services"]["clickhouse"] == "unhealthy"
    assert health["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_overall_health_is_healthy_with_working_db(fake_db_factory):
    fake_db_factory({"health_check": 1})
    health = await HealthService().get_overall_health()
    assert health["services"]["clickhouse"] == "healthy"
    assert health["services"]["database"] == "healthy"
    assert health["status"] == "healthy"
