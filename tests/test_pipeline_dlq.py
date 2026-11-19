"""
Dead-letter queue storage (Phase 4): rows are written with ClickHouse
DateTime64 text for times, whether the entry comes from ingest (datetime)
or back from the API (ISO strings), so status changes can be saved.

Found live: resolving entries read through the API failed with
"Cannot parse string '2026-11-19T00:27:45.684000+00:00' as DateTime64(3)".
"""

import asyncio
from datetime import datetime, timezone

from pipeline_dlq import PipelineDLQ


class DB:
    def __init__(self):
        self.params = []

    async def execute_update(self, sql, params):
        self.params.append(params)


def test_times_are_written_as_clickhouse_text_from_datetimes_and_iso_strings():
    db = DB()
    dlq = PipelineDLQ(db=db)
    entry = {"id": "d1", "pipeline_id": "p", "pipeline_version": 1, "processor": "grok", "processor_index": 0,
             "tag": "", "error": "x", "event": {"msg": "m"}, "failed_at": datetime(2026, 11, 19, 0, 27, 45, 684000,
                                                                                      tzinfo=timezone.utc)}
    asyncio.run(dlq.add("acme", [entry]))
    assert db.params[0]["failed_at_0"] == "2026-11-19 00:27:45.684"
    from_api = {**entry, "failed_at": "2026-11-19T00:27:45.684000+00:00", "status": "pending"}
    asyncio.run(dlq.resolve("acme", [from_api], "replayed", actor="dana",
                            now=datetime(2026, 11, 19, 1, 0, tzinfo=timezone.utc)))
    row = db.params[1]
    assert row["failed_at_0"] == "2026-11-19 00:27:45.684" and row["resolved_at_0"] == "2026-11-19 01:00:00.000"
    assert row["status_0"] == "replayed" and row["resolved_by_0"] == "dana"
