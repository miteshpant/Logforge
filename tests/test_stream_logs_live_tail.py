"""
GET /v1/stream/logs (live tail). The tenant UI's Log Explorer called this
endpoint, but it did not exist, so live tail sat in "unavailable" and retried
forever.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROW = {"ts": "2026-11-16 07:00:00", "service": "checkout", "level": "error",
       "msg": "payment declined", "trace_id": "t1", "span_id": "",
       "ingested_at": datetime(2026, 11, 16, 7, 0, 1, tzinfo=timezone.utc)}


async def _collect(response, max_events=10):
    events = []
    async for chunk in response.body_iterator:
        events.append(chunk)
        if len(events) >= max_events:
            break
    return events


@pytest.mark.asyncio
async def test_streams_new_logs_once_and_scopes_to_tenant():
    from routers import query as query_router
    from routers import streaming_api

    engine = MagicMock()
    # Two polls see the same row (overlap window); a third poll ends the stream.
    engine.execute_query = AsyncMock(return_value=SimpleNamespace(logs=[ROW]))
    manager = MagicMock()
    manager.register_connection.return_value = "c1"
    polls = {"n": 0}

    def shutting_down():
        polls["n"] += 1
        return polls["n"] > 2

    type(manager).is_shutting_down = property(lambda self: shutting_down())

    with patch.object(query_router, "query_engine", engine), \
         patch.object(streaming_api, "get_streaming_connection_manager", return_value=manager), \
         patch.object(streaming_api.asyncio, "sleep", AsyncMock()):
        response = await streaming_api.stream_logs(service="checkout", level="ERROR", customer_id="tenant-1")
        events = await _collect(response)

    log_events = [e for e in events if e.startswith("event: log_event")]
    assert len(log_events) == 1  # deduplicated across overlapping polls
    assert '"msg": "payment declined"' in log_events[0]

    request = engine.execute_query.await_args.args[0]
    fields = {(f.field, f.operator.value) for f in request.filters}
    assert ("customer_id", "eq") in fields          # tenant isolation
    assert ("service", "eq") in fields
    assert ("level", "in") in fields                # case-insensitive level
    assert request.sort_field == "ingested_at"
    manager.unregister_connection.assert_called_once_with("c1")
