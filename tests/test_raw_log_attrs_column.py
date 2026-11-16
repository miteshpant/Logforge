"""
Regression tests: logs_raw_mt.attrs holds the caller's attributes only.

Two of the three raw-write paths in log_processor serialised the whole LogEntry
into `attrs`, so every row duplicated its own columns and the caller's
attributes ended up nested under attrs.attrs. The same paths hard-coded
`status` to 0. Found during the QA run (the query engine had to look in two
places for every attribute).
"""

import json
from unittest.mock import MagicMock

import pytest

from events.management.processors import log_processor
from models import LogEntry

COLUMNS_ATTRS, COLUMNS_STATUS = 7, 8  # positions in the logs_raw_mt row


def _log(**kw):
    return LogEntry(service="checkout", msg="payment declined", level="error",
                    attrs={"region": "eu-west-1", "latency_ms": 334}, **kw)


@pytest.mark.asyncio
async def test_internal_batch_writes_only_caller_attrs_and_real_status():
    client = MagicMock()
    await log_processor.process_log_batch_internal([_log(status=502)], client, "t1")

    row = client.insert.call_args.args[1][0]
    assert json.loads(row[COLUMNS_ATTRS]) == {"region": "eu-west-1", "latency_ms": 334}
    assert row[COLUMNS_STATUS] == 502


def test_helpers_handle_missing_and_bad_values():
    assert log_processor._attrs_json(MagicMock(attrs=None)) == "{}"
    assert log_processor._status(MagicMock(status="oops")) == 0
    assert log_processor._status(MagicMock(status=70000)) == 0
    assert log_processor._status(MagicMock(status=404)) == 404
