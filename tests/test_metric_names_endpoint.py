"""
GET /v1/observability/metrics/names lists the tenant's metric names and flags
which are standard. Without it, metrics sent under non-standard names (e.g.
"cpu.utilization") were stored but invisible in the Metrics Explorer, which only
charts standard names -- QA finding #12.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_lists_names_and_flags_standard_ones():
    from routers import observability_api

    dao = MagicMock()
    dao.db.execute_query = AsyncMock(return_value=[
        {"metric_name": "cpu.utilization", "points": 60, "last_seen": datetime(2026, 11, 16, 2)},
        {"metric_name": "cpu_usage", "points": 144, "last_seen": datetime(2026, 11, 16, 3)},
    ])
    with patch("dao.observability_dao.ObservabilityDAO", return_value=dao):
        out = await observability_api.get_metric_names(days=7, customer_id="tenant-1")

    assert [(m["name"], m["standard"]) for m in out["metrics"]] == [
        ("cpu.utilization", False), ("cpu_usage", True)]
    sql, params = dao.db.execute_query.await_args.args
    assert params == {"customer_id": "tenant-1", "days": 7}  # tenant-scoped, bound
