"""
Trace search with a duration filter must not put an aggregate in WHERE.

search_trace_summaries selects `max(duration_ms) AS duration_ms` and appended
`duration_ms >= ...` to WHERE; ClickHouse resolves that name to the aggregate
alias and rejects the query (ILLEGAL_AGGREGATION, code 184), so every
duration-filtered trace search (the Tracing page's Min/Max Duration) returned
500. Duration is a trace-level property, so it is filtered in HAVING.
Surfaced once the route tests were actually run.
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_duration_filters_go_in_having():
    with patch("dao.observability_dao.DatabaseLayer"):
        from dao.observability_dao import ObservabilityDAO

        dao = ObservabilityDAO()
    dao.db.execute_query = AsyncMock(return_value=[])

    await dao.search_trace_summaries("t1", {"min_duration_ms": 100, "max_duration_ms": 900, "service_name": "api"})

    sql, params = dao.db.execute_query.await_args.args
    where = sql[sql.index("WHERE"):sql.index("GROUP BY")]
    having = sql[sql.index("GROUP BY"):sql.index("ORDER BY")]
    assert "duration_ms" not in where
    assert "HAVING duration_ms >= %(min_duration_ms)s AND duration_ms <= %(max_duration_ms)s" in having
    assert "service_name = %(service_name)s" in where
    assert params["min_duration_ms"] == 100


@pytest.mark.asyncio
async def test_no_having_without_duration_filters():
    with patch("dao.observability_dao.DatabaseLayer"):
        from dao.observability_dao import ObservabilityDAO

        dao = ObservabilityDAO()
    dao.db.execute_query = AsyncMock(return_value=[])
    await dao.search_trace_summaries("t1", {})
    assert "HAVING" not in dao.db.execute_query.await_args.args[0]
