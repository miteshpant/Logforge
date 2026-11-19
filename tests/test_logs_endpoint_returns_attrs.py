"""
GET /v1/logs returns each log's attributes.

The endpoint selected ts, service, level, msg, host, trace_id and
customer_id, but not `attrs` or `span_id`, so every caller-supplied field
(order_id, user, ...) was missing from the Log Explorer's expanded view even
though ClickHouse stored it. Found by the rewritten Playwright logs spec.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


class _Result:
    def __init__(self, rows):
        self.result_rows = rows


def _client(rows):
    client = MagicMock()
    client.query.side_effect = lambda sql, parameters=None: (
        _Result([[len(rows)]]) if "count()" in sql else _Result(rows)
    )
    return client


ROW = (
    datetime(2026, 11, 17, 13, 0, tzinfo=timezone.utc),
    "checkout", "error", "payment declined", "web-01", "trace-1",
    "tenant-1", "span-9",
    json.dumps({"order_id": "42", "region": "eu", "source_format": "json",
                "processing_version": "smart_v1"}),
)


@pytest.mark.asyncio
async def test_logs_include_caller_attributes_and_span_id():
    from routers import query

    client = _client([ROW])
    with patch.object(query, "clickhouse_client", client):
        out = await query.get_logs(service=None, level=None, start_time=None, end_time=None,
                                   limit=10, offset=0, customer_id="tenant-1")

    log = out["logs"][0]
    assert log["attrs"] == {"order_id": "42", "region": "eu"}
    assert log["span_id"] == "span-9"
    sql = client.query.call_args_list[0].args[0]
    assert "attrs" in sql and "span_id" in sql


@pytest.mark.asyncio
async def test_unparseable_attrs_do_not_break_the_page():
    from routers import query

    bad = ROW[:-1] + ("not json",)
    with patch.object(query, "clickhouse_client", _client([bad])):
        out = await query.get_logs(service=None, level=None, start_time=None, end_time=None,
                                   limit=10, offset=0, customer_id="tenant-1")
    assert out["logs"][0]["attrs"] == {}
