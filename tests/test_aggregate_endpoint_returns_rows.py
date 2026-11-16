"""
Regression test: /v1/query/aggregate must return the grouped rows.

The engine returns one row per group in QueryResponse.logs; `aggregations` is
only filled for ungrouped totals. The endpoint returned just `aggregations`, so
grouped requests answered `total_groups: 20` with no data -- the System
Intelligence "Service Health Matrix" was always empty. The cached path must
return the same rows.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

ROWS = [{"service": "checkout", "level": "error", "event_count": 39}]
REQUEST = {
    "start_time": "2026-11-15T00:00:00Z", "end_time": "2026-11-16T00:00:00Z",
    "group_by": ["service", "level"],
    "aggregations": [{"type": "count", "field": "*", "alias": "event_count"}],
}


def _wire(monkeypatch, cached=None):
    from routers import query

    engine = MagicMock()
    engine.execute_query = AsyncMock(return_value=SimpleNamespace(
        logs=ROWS, aggregations={}, total_count=len(ROWS), execution_time_ms=1.0))
    monkeypatch.setattr(query, "query_engine", engine)

    svc = MagicMock()
    svc.get_cached_result = AsyncMock(return_value=cached)
    svc.cache_query_result = AsyncMock()
    monkeypatch.setattr(query, "get_query_service", lambda: svc)
    return query, svc


@pytest.mark.asyncio
async def test_grouped_rows_are_returned_and_cached(monkeypatch):
    query, svc = _wire(monkeypatch)
    out = await query.aggregate_logs(dict(REQUEST), customer_id="tenant-1")
    assert out["results"] == ROWS
    assert out["total_groups"] == 1
    assert svc.cache_query_result.await_args.kwargs["result"]["results"] == ROWS


@pytest.mark.asyncio
async def test_cached_path_returns_rows_too(monkeypatch):
    query, _ = _wire(monkeypatch, cached={"results": ROWS, "aggregations": {}, "total_count": 1})
    out = await query.aggregate_logs(dict(REQUEST), customer_id="tenant-1")
    assert out["results"] == ROWS
