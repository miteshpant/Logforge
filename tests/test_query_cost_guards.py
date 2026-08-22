"""
Tests for ENH-017 -- per-query cost guards.

`AdvancedQueryRequest.timeout_seconds` was declared (and documented, and
range-validated) but never passed to the ClickHouse client, so the timeout did
nothing. No scan-byte or result-row limit existed either, so a single tenant's
unfiltered wide-time-range query could scan their whole partition set and
degrade the cluster for every other tenant -- a noisy-neighbour failure that
directly caps how many customers the platform can host.

The overflow modes are all `throw` on purpose: a query that exceeds its budget
must FAIL rather than silently return truncated data. A partial result presented
as complete makes dashboards and alerts lie.
"""

from datetime import datetime, timedelta, timezone

import pytest

from query_engine import AdvancedQueryEngine, AdvancedQueryRequest

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = START + timedelta(hours=1)


class _RecordingClient:
    """Captures the settings passed to `query()`."""

    def __init__(self):
        self.calls = []

    def query(self, sql, parameters=None, settings=None):
        self.calls.append(
            {"sql": sql, "parameters": parameters, "settings": settings}
        )

        class _Result:
            result_rows = []
            column_names = []

        return _Result()


def _request(**overrides):
    base = dict(start_time=START, end_time=END)
    base.update(overrides)
    return AdvancedQueryRequest(**base)


@pytest.fixture
def engine():
    client = _RecordingClient()
    eng = AdvancedQueryEngine(clickhouse_client=client)
    return eng, client


# ---------------------------------------------------------------------------
# Settings reach the driver
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_settings_are_passed_to_clickhouse(engine):
    eng, client = engine
    await eng.execute_query(_request())

    assert client.calls, "Query was never executed"
    assert client.calls[0]["settings"] is not None, (
        "No execution settings were sent -- cost guards are not in effect."
    )


@pytest.mark.asyncio
async def test_timeout_seconds_is_honoured(engine):
    """The declared-but-unused `timeout_seconds` must now take effect."""
    eng, client = engine
    await eng.execute_query(_request(timeout_seconds=17))

    assert client.calls[0]["settings"]["max_execution_time"] == 17


@pytest.mark.asyncio
async def test_default_timeout_is_applied(engine):
    eng, client = engine
    await eng.execute_query(_request())

    assert client.calls[0]["settings"]["max_execution_time"] == 30


@pytest.mark.asyncio
async def test_scan_byte_limit_is_set(engine):
    eng, client = engine
    await eng.execute_query(_request())

    settings = client.calls[0]["settings"]
    assert settings["max_bytes_to_read"] > 0


@pytest.mark.asyncio
async def test_result_row_limit_is_set(engine):
    eng, client = engine
    await eng.execute_query(_request())

    assert client.calls[0]["settings"]["max_result_rows"] > 0


# ---------------------------------------------------------------------------
# Overflow must throw, never truncate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode_key",
    ["timeout_overflow_mode", "read_overflow_mode", "result_overflow_mode"],
)
async def test_overflow_modes_throw(engine, mode_key):
    """
    ClickHouse's alternative is `break`, which returns whatever it had when the
    limit was hit. Silently truncated results would be indistinguishable from
    complete ones.
    """
    eng, client = engine
    await eng.execute_query(_request())

    assert client.calls[0]["settings"][mode_key] == "throw", (
        f"{mode_key} must be 'throw' so an over-budget query fails loudly "
        "instead of returning partial data as if it were complete."
    )


# ---------------------------------------------------------------------------
# Deployment tunability
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_limit_is_tunable_by_environment(engine, monkeypatch):
    monkeypatch.setenv("LOGFORGE_QUERY_MAX_BYTES", "12345")
    eng, client = engine

    await eng.execute_query(_request())

    assert client.calls[0]["settings"]["max_bytes_to_read"] == 12345


@pytest.mark.asyncio
async def test_row_limit_is_tunable_by_environment(engine, monkeypatch):
    monkeypatch.setenv("LOGFORGE_QUERY_MAX_RESULT_ROWS", "77")
    eng, client = engine

    await eng.execute_query(_request())

    assert client.calls[0]["settings"]["max_result_rows"] == 77


# ---------------------------------------------------------------------------
# Failures must surface
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_budget_exceeded_error_propagates():
    """
    An over-budget query must raise, not come back as an empty result set. An
    empty result would be read as "no matching logs", which is a materially
    different and dangerous answer during an incident.
    """

    class _ThrowingClient:
        def query(self, sql, parameters=None, settings=None):
            raise RuntimeError(
                "Limit for bytes to read exceeded, max_bytes_to_read"
            )

    eng = AdvancedQueryEngine(clickhouse_client=_ThrowingClient())

    with pytest.raises(RuntimeError, match="max_bytes_to_read"):
        await eng.execute_query(_request())
