"""
Tests for ENH-029 -- ingest back-pressure and load shedding.

Ingest endpoints return `202 accepted` and hand the batch to a background worker
pool. Nothing checked whether that pool had capacity, so under overload the API
kept answering "accepted" for data it could not persist. That converts overload
into **silent loss**: the customer believes their logs were accepted and only
discovers otherwise during an incident, when they need them.

An honest 429 with `Retry-After` lets the shipper retry -- which is exactly how
Vector, Fluent Bit and the OTel collector are all designed to behave.
"""

import ast
import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from ingest_pipeline import IngestPipeline, reset_ingest_pipeline

INGESTION_ROUTER = (
    Path(__file__).resolve().parent.parent
    / "apps" / "api" / "routers" / "ingestion.py"
)


@pytest.fixture(autouse=True)
def clean():
    reset_ingest_pipeline()
    yield
    reset_ingest_pipeline()


# ---------------------------------------------------------------------------
# Saturation detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idle_pipeline_is_not_saturated():
    pipeline = IngestPipeline(workers=2, queue_size=100)
    await pipeline.start()

    assert pipeline.is_saturated() is False
    await pipeline.stop()


def test_unstarted_pipeline_reports_saturated():
    """
    If the pool is not running, nothing can be processed. Reporting "not
    saturated" would let the API accept data that is guaranteed to be dropped.
    """
    pipeline = IngestPipeline(workers=2, queue_size=100)
    assert pipeline.is_saturated() is True


@pytest.mark.asyncio
async def test_full_queue_reports_saturated(monkeypatch):
    async def _blocked(self, batch):
        import asyncio

        await asyncio.sleep(30)

    monkeypatch.setattr(IngestPipeline, "_process", _blocked)

    pipeline = IngestPipeline(workers=1, queue_size=10)
    await pipeline.start()

    for _ in range(10):
        pipeline.submit(
            logs=[{"msg": "x"}], customer_id="t1", endpoint="/logs",
            format_type="json", log_count=1, bytes_processed=1,
            processing_time_ms=1,
        )

    assert pipeline.is_saturated() is True
    await pipeline.stop(drain_timeout=0.1)


@pytest.mark.asyncio
async def test_saturation_threshold_leaves_headroom(monkeypatch):
    """
    The threshold is below 100% deliberately: a batch is queued from a request
    handler AFTER the check, so accepting right up to the cap would mean
    accepting a request and then dropping it moments later.
    """
    monkeypatch.setenv("INGEST_SATURATION_THRESHOLD", "0.5")

    async def _blocked(self, batch):
        import asyncio

        await asyncio.sleep(30)

    monkeypatch.setattr(IngestPipeline, "_process", _blocked)

    pipeline = IngestPipeline(workers=1, queue_size=10)
    await pipeline.start()

    for _ in range(6):
        pipeline.submit(
            logs=[{"msg": "x"}], customer_id="t1", endpoint="/logs",
            format_type="json", log_count=1, bytes_processed=1,
            processing_time_ms=1,
        )

    assert pipeline.is_saturated() is True, (
        "Saturation must trigger before the queue is completely full."
    )
    await pipeline.stop(drain_timeout=0.1)


def test_retry_after_is_configurable(monkeypatch):
    monkeypatch.setenv("INGEST_RETRY_AFTER_SECONDS", "17")
    assert IngestPipeline().retry_after_seconds() == 17


# ---------------------------------------------------------------------------
# The endpoint guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_capacity_check_passes_when_healthy():
    from routers.ingestion import check_ingest_capacity
    from ingest_pipeline import get_ingest_pipeline

    pipeline = get_ingest_pipeline()
    await pipeline.start()

    check_ingest_capacity()  # must not raise
    await pipeline.stop()


def test_capacity_check_raises_429_when_saturated():
    """An unstarted pipeline is saturated, which is the simplest saturated state."""
    from routers.ingestion import check_ingest_capacity

    with pytest.raises(HTTPException) as err:
        check_ingest_capacity()

    assert err.value.status_code == 429


def test_429_carries_retry_after_header():
    """Shippers use Retry-After to back off; without it they hot-loop."""
    from routers.ingestion import check_ingest_capacity

    with pytest.raises(HTTPException) as err:
        check_ingest_capacity()

    assert "Retry-After" in (err.value.headers or {})


# ---------------------------------------------------------------------------
# Wiring across every ingest endpoint
# ---------------------------------------------------------------------------


def _ingest_endpoints():
    """Every route handler in the ingestion router."""
    tree = ast.parse(INGESTION_ROUTER.read_text(encoding="utf-8"))
    handlers = []
    for node in tree.body:
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for decorator in node.decorator_list:
            source = ast.dump(decorator)
            if "router" in source and "post" in source:
                handlers.append(node)
                break
    return handlers


def test_every_ingest_endpoint_checks_capacity():
    """
    A new endpoint that forgets the check silently reintroduces the bug for its
    own traffic.
    """
    missing = []
    for handler in _ingest_endpoints():
        calls = [
            n.func.id
            for n in ast.walk(handler)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        ]
        if "check_ingest_capacity" not in calls:
            missing.append(handler.name)

    assert not missing, f"Ingest endpoints without a capacity check: {missing}"


def test_capacity_check_runs_before_any_work():
    """
    Checking after parsing would still burn CPU on data destined to be dropped.
    """
    for handler in _ingest_endpoints():
        check_line = None
        for node in ast.walk(handler):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "check_ingest_capacity"
            ):
                check_line = node.lineno
                break

        assert check_line is not None
        # It should be within the first few statements of the body.
        assert check_line - handler.lineno < 12, (
            f"{handler.name} checks capacity too late (line offset "
            f"{check_line - handler.lineno})"
        )


def test_429_is_not_relabelled_by_generic_handlers():
    """
    Most ingest endpoints wrap their body in `except Exception -> 400/500`. A
    deliberate 429 must pass through untouched.
    """
    source = INGESTION_ROUTER.read_text(encoding="utf-8")

    generic = source.count("except Exception as e:")
    passthrough = source.count("except HTTPException:")

    assert passthrough >= generic, (
        f"{generic} generic handlers but only {passthrough} HTTPException "
        "passthroughs -- a 429 would be relabelled as 400/500."
    )
