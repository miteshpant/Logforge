"""
Regression tests: derived log fields are computed, not assumed to be columns.

The allow-list admitted http_response_time_ms, http_status, is_error, date,
hour, ... -- computed columns of the legacy single-tenant `logs_normalized`
table that the multi-tenant tables never gained. Queries using them passed
validation and then failed inside ClickHouse ("Missing columns"), returning a
500; the System Intelligence page hit this on every load. Separately, caller
attributes are nested under "attrs" inside the stored envelope, so
`attrs.<key>` filters silently matched nothing.
"""

from datetime import datetime, timezone

import pytest

from query_engine import (
    DERIVED_FIELD_SQL,
    AdvancedQueryEngine,
    AdvancedQueryRequest,
    AggregationType,
    QueryAggregation,
    QueryFieldError,
    QueryFilter,
    QueryOperator,
)

START = datetime(2026, 11, 15, tzinfo=timezone.utc)
END = datetime(2026, 11, 16, tzinfo=timezone.utc)
TENANT = QueryFilter(field="customer_id", operator=QueryOperator.EQ, value="t1")


def _sql(**kw):
    engine = AdvancedQueryEngine(None)
    q = AdvancedQueryRequest(start_time=START, end_time=END, **kw)
    table = engine._select_optimal_table(q)
    params = {}
    return table, engine._build_sql_query(q, table, params), params


def test_response_time_aggregation_is_computed_from_attrs_on_raw_table():
    table, sql, _ = _sql(
        filters=[TENANT], group_by=["service"],
        aggregations=[
            QueryAggregation(type=AggregationType.AVG, field="http_response_time_ms", alias="avg_rt"),
            QueryAggregation(type=AggregationType.PERCENTILE, field="http_response_time_ms",
                             alias="p95", percentile_value=0.95),
        ],
    )
    assert table == "logs_raw_mt"
    assert "JSONExtractUInt(attrs, 'attrs', 'latency_ms')" in sql
    assert "toFloat64OrZero" not in sql  # numeric expression, aggregated directly


@pytest.mark.parametrize("field", sorted(DERIVED_FIELD_SQL))
def test_every_derived_field_filter_routes_to_raw_table(field):
    table, sql, _ = _sql(filters=[TENANT, QueryFilter(field=field, operator=QueryOperator.EQ, value=1)])
    assert table == "logs_raw_mt"
    assert DERIVED_FIELD_SQL[field] in sql


def test_derived_group_by_is_selected_under_its_own_name():
    _, sql, _ = _sql(
        filters=[TENANT], group_by=["hour"],
        aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*", alias="n")],
    )
    assert "toStartOfHour(ts)) AS hour" in sql
    assert "GROUP BY hour" in sql


def test_attrs_filter_falls_back_to_nested_caller_attributes():
    _, sql, params = _sql(filters=[TENANT, QueryFilter(field="attrs.region", operator=QueryOperator.EQ,
                                                       value="eu-west-1")])
    assert "JSONExtractString(attrs, 'attrs', %(" in sql
    assert "region" in params.values()  # the key stays a bound parameter


def test_unknown_fields_are_still_rejected():
    with pytest.raises(QueryFieldError):
        _sql(filters=[TENANT, QueryFilter(field="response_time", operator=QueryOperator.GTE, value=1)])
