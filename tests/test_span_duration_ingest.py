"""
Regression test: a span's client-supplied duration_ms must be stored.

`SpanRequest` documents `duration_ms`, but ObservabilityService.ingest_trace_span
only derived the duration from end_time - start_time and otherwise wrote 0. Any
span sent with a duration but no end_time -- common for SDKs that report
duration -- was stored as 0 ms, so trace lists, APM latency and P95 all read 0.
Found during a live QA run.
"""

from unittest.mock import AsyncMock, patch

import pytest


def _service():
    with patch("services.observability_service.ObservabilityDAO"):
        from services.observability_service import ObservabilityService

        svc = ObservabilityService()
    svc.dao.save_trace_span = AsyncMock(return_value="span-1")
    return svc


BASE = {
    "trace_id": "t1", "span_id": "s1", "operation_name": "charge_card",
    "service_name": "payments", "start_time": "2026-11-16T01:00:00+00:00",
}


@pytest.mark.asyncio
async def test_client_duration_ms_is_kept_when_no_end_time():
    svc = _service()
    await svc.ingest_trace_span({**BASE, "duration_ms": 237}, "tenant-1")
    assert svc.dao.save_trace_span.await_args.args[0]["duration_ms"] == 237


@pytest.mark.asyncio
async def test_end_time_still_determines_duration():
    svc = _service()
    await svc.ingest_trace_span(
        {**BASE, "end_time": "2026-11-16T01:00:01.500000+00:00", "duration_ms": 9}, "tenant-1"
    )
    assert svc.dao.save_trace_span.await_args.args[0]["duration_ms"] == 1500
