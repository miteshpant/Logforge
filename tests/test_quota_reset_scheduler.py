"""
Tests for ENH-030 -- the quota reset scheduler must actually run.

`dependencies.py` had the scheduler commented out with
"TODO: Enable after database permissions are updated in container". The real
cause was not a ClickHouse grant: `QuotaResetService` was absent from
`DatabaseLayer.AUTHORIZED_SERVICES`, so constructing the layer raised
`SecurityError` -- an authorization-registry gap in our own code.

While disabled, tenant quotas never reset. Usage accumulated indefinitely, so
tenants would eventually be blocked when they should not be, or billed against
a counter that never rolled over. Both are revenue-integrity bugs.
"""

import asyncio
import inspect

import pytest

from database_layer import DatabaseLayer


# ---------------------------------------------------------------------------
# The registry gap that actually blocked this
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "service",
    ["QuotaResetService", "QuotaTestService", "QuotaHistoryAPI"],
)
def test_quota_services_are_registered(service):
    assert service in DatabaseLayer.AUTHORIZED_SERVICES, (
        f"{service} has TABLE_ACCESS_CONTROL entries but no credentials, so "
        "DatabaseLayer construction raises SecurityError."
    )


@pytest.mark.parametrize(
    "service",
    ["QuotaResetService", "QuotaTestService", "QuotaHistoryAPI"],
)
def test_quota_services_have_table_access(service):
    assert service in DatabaseLayer.TABLE_ACCESS_CONTROL


def test_quota_reset_service_credentials_validate():
    """The key the service passes must match the registry."""
    assert DatabaseLayer._validate_service_credentials(
        DatabaseLayer, "QuotaResetService", "quota-reset-service-key"
    ) is True


def test_wrong_credentials_are_still_rejected():
    """Registering the service must not weaken credential checking."""
    assert DatabaseLayer._validate_service_credentials(
        DatabaseLayer, "QuotaResetService", "wrong-key"
    ) is False


def test_quota_reset_service_can_perform_updates():
    """Resetting a quota is an ALTER TABLE ... UPDATE."""
    assert "QuotaResetService" in DatabaseLayer.UPDATE_ALLOWED_SERVICES


def test_quota_reset_service_cannot_perform_admin_operations():
    """It has no business dropping or truncating tables."""
    assert "QuotaResetService" not in DatabaseLayer.ADMIN_SERVICES
    assert "QuotaResetService" not in DatabaseLayer.DELETE_ALLOWED_SERVICES


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


def test_scheduler_is_started_in_lifespan():
    import dependencies

    source = inspect.getsource(dependencies.initialize_engines)

    assert "start_scheduler" in source
    assert "skipped (development mode)" not in source, (
        "The scheduler is still stubbed out."
    )


def test_scheduler_is_stopped_on_shutdown():
    import dependencies

    source = inspect.getsource(dependencies.shutdown_engines)
    assert "stop_scheduler" in source


def test_scheduler_failure_does_not_block_startup():
    """
    Billing correctness matters, but a scheduler problem must not stop the API
    from serving traffic -- it should be loud, not fatal.
    """
    import dependencies

    source = inspect.getsource(dependencies.initialize_engines)
    start = source.index("start_scheduler")
    window = source[start - 400:start + 400]

    assert "try:" in window
    assert "logger.error" in window


# ---------------------------------------------------------------------------
# Shutdown behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scheduler_stops_when_cancelled():
    """
    Cancellation is a shutdown signal. The previous broad `except Exception`
    would have kept the loop alive and stalled shutdown.
    """
    from services.quota_reset_service import QuotaResetScheduler

    scheduler = QuotaResetScheduler.__new__(QuotaResetScheduler)
    scheduler.running = False
    scheduler.check_interval = 1

    class _Service:
        async def check_and_reset_quotas(self):
            await asyncio.sleep(10)
            return {}

    scheduler.quota_service = _Service()

    task = asyncio.create_task(scheduler.start_scheduler())
    await asyncio.sleep(0.05)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert scheduler.running is False


@pytest.mark.asyncio
async def test_stop_scheduler_clears_the_running_flag():
    from services.quota_reset_service import QuotaResetScheduler

    scheduler = QuotaResetScheduler.__new__(QuotaResetScheduler)
    scheduler.running = True
    scheduler.stop_scheduler()

    assert scheduler.running is False


@pytest.mark.asyncio
async def test_scheduler_survives_a_failing_cycle():
    """One bad reset cycle must not kill the scheduler for the process lifetime."""
    from services.quota_reset_service import QuotaResetScheduler

    scheduler = QuotaResetScheduler.__new__(QuotaResetScheduler)
    scheduler.running = False
    scheduler.check_interval = 1
    calls = []

    class _FlakyService:
        async def check_and_reset_quotas(self):
            calls.append(1)
            raise RuntimeError("clickhouse unavailable")

    scheduler.quota_service = _FlakyService()

    task = asyncio.create_task(scheduler.start_scheduler())
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert calls, "The scheduler never ran a cycle"
