"""
Regression tests for ENH-002 / ENH-003 -- SQL injection breaking tenant isolation.

Threat model
------------
`routers/query.py` enforces multi-tenancy by APPENDING a `customer_id` filter to
every query. Because `QueryFilter.to_clickhouse_condition()` previously
interpolated values straight into SQL, a caller could submit a filter value such
as::

    x' OR customer_id != '

which closed the quoted literal and neutralised the isolation predicate,
exposing every other tenant's logs. That is a total failure of the platform's
core multi-tenant guarantee.

These tests assert the structural property that prevents it: caller-supplied
VALUES are bound as parameters and never appear in SQL text, and caller-supplied
IDENTIFIERS are allow-listed against the real schema.

No database is required -- we inspect the generated SQL and parameter dict.
"""

from datetime import datetime, timedelta, timezone

import pytest

from query_engine import (
    AdvancedQueryEngine,
    AdvancedQueryRequest,
    AggregationType,
    QueryAggregation,
    QueryFieldError,
    QueryFilter,
    QueryOperator,
    validate_identifier,
)


# Values that would break out of a single-quoted SQL literal.
INJECTION_VALUES = [
    "x' OR customer_id != '",
    "'; DROP TABLE logs_raw_mt; --",
    "' OR '1'='1",
    "' UNION SELECT * FROM users_mt --",
    "admin'--",
]

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = START + timedelta(hours=1)


def _request(**overrides):
    base = dict(start_time=START, end_time=END)
    base.update(overrides)
    return AdvancedQueryRequest(**base)


def _build(request):
    """Build SQL + params the way execute_query does."""
    engine = AdvancedQueryEngine(clickhouse_client=None)
    table = engine._select_optimal_table(request)
    params = {}
    sql = engine._build_sql_query(request, table, params)
    return sql, params


# ---------------------------------------------------------------------------
# Values must be bound, never interpolated
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payload", INJECTION_VALUES)
def test_filter_value_never_appears_in_sql_text(payload):
    """The core property: a hostile value must not reach the statement."""
    request = _request(
        filters=[QueryFilter(field="service", operator=QueryOperator.EQ, value=payload)]
    )
    sql, params = _build(request)

    assert payload not in sql, (
        f"Injection payload leaked into SQL text: {sql}\n"
        "Values must be bound as parameters (ENH-002)."
    )
    assert payload in params.values(), "Payload should be carried as bound data."


@pytest.mark.parametrize("payload", INJECTION_VALUES)
def test_tenant_isolation_predicate_survives_injection(payload):
    """
    Simulates the router: a tenant filter is appended after caller filters. The
    hostile value must not be able to disable it.
    """
    request = _request(
        filters=[
            QueryFilter(field="service", operator=QueryOperator.EQ, value=payload),
            # Appended by routers/query.py for multi-tenant isolation
            QueryFilter(
                field="customer_id", operator=QueryOperator.EQ, value="tenant-a"
            ),
        ]
    )
    sql, params = _build(request)

    # The isolation predicate is present and bound.
    assert "customer_id = %(" in sql
    assert "tenant-a" in params.values()

    # And no OR was smuggled in to widen the predicate.
    assert " OR " not in sql.upper(), (
        f"Injected OR reached the WHERE clause: {sql}"
    )


@pytest.mark.parametrize("payload", INJECTION_VALUES)
def test_text_search_is_bound(payload):
    request = _request(text_search=payload)
    sql, params = _build(request)

    assert payload not in sql
    assert f"%{payload}%" in params.values()


def test_like_wildcards_in_user_input_stay_literal():
    """
    A '%' supplied by the caller must remain data. If wildcards were applied to
    SQL text rather than the bound value, `%` would silently widen the match.
    """
    request = _request(
        filters=[
            QueryFilter(
                field="msg", operator=QueryOperator.CONTAINS, value="100%_done"
            )
        ]
    )
    sql, params = _build(request)

    assert "100%_done" in "".join(str(v) for v in params.values())
    assert "100%_done" not in sql


@pytest.mark.parametrize("operator", list(QueryOperator))
def test_every_operator_binds_its_value(operator):
    """No operator may leave an interpolation path open."""
    payload = "'; DROP TABLE logs_raw_mt; --"
    value = [payload] if operator in (QueryOperator.IN, QueryOperator.NOT_IN) else payload

    request = _request(
        filters=[QueryFilter(field="service", operator=operator, value=value)]
    )
    sql, params = _build(request)

    assert payload not in sql, f"Operator {operator} leaked a raw value into SQL"
    flattened = [str(v) for v in params.values()]
    assert any(payload in v for v in flattened)


def test_in_operator_binds_each_list_element():
    payloads = ["a'", "b'; DROP TABLE x; --"]
    request = _request(
        filters=[
            QueryFilter(field="level", operator=QueryOperator.IN, value=payloads)
        ]
    )
    sql, params = _build(request)

    for payload in payloads:
        assert payload not in sql
        assert payload in params.values()


def test_empty_in_list_does_not_emit_invalid_sql():
    """`IN ()` is a ClickHouse syntax error; it must degrade to a constant."""
    request = _request(
        filters=[QueryFilter(field="level", operator=QueryOperator.IN, value=[])]
    )
    sql, _ = _build(request)
    assert "IN ()" not in sql


# ---------------------------------------------------------------------------
# Identifiers must be allow-listed
# ---------------------------------------------------------------------------


def test_unknown_filter_field_is_rejected():
    request = _request(
        filters=[
            QueryFilter(
                field="1 FROM users_mt; --", operator=QueryOperator.EQ, value="x"
            )
        ]
    )
    with pytest.raises(QueryFieldError):
        _build(request)


def test_unknown_field_is_rejected_rather_than_ignored():
    """
    Rejecting matters: silently dropping an unrecognised filter would WIDEN the
    result set, which is the opposite of safe under a tenancy predicate.
    """
    with pytest.raises(QueryFieldError):
        validate_identifier("password_hash")


def test_known_field_passes():
    assert validate_identifier("service") == "service"


def test_malicious_sort_field_is_rejected():
    request = _request(sort_field="ts; DROP TABLE logs_raw_mt")
    with pytest.raises(QueryFieldError):
        _build(request)


def test_malicious_group_by_is_rejected():
    request = _request(
        group_by=["service; DROP TABLE logs_raw_mt"],
        aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
    )
    with pytest.raises(QueryFieldError):
        _build(request)


def test_malicious_include_field_is_rejected():
    request = _request(include_fields=["msg, password_hash"])
    with pytest.raises(QueryFieldError):
        _build(request)


def test_malicious_aggregation_alias_is_rejected():
    agg = QueryAggregation(
        type=AggregationType.COUNT, field="*", alias="c FROM users_mt --"
    )
    with pytest.raises(QueryFieldError):
        agg.to_clickhouse_select()


def test_malicious_aggregation_field_is_rejected():
    agg = QueryAggregation(
        type=AggregationType.SUM, field="x); DROP TABLE logs_raw_mt; --"
    )
    with pytest.raises(QueryFieldError):
        agg.to_clickhouse_select()


def test_valid_aggregation_still_builds():
    agg = QueryAggregation(type=AggregationType.COUNT, field="*")
    assert agg.to_clickhouse_select() == "count() AS count_all"


# ---------------------------------------------------------------------------
# JSON path access keeps working, safely
# ---------------------------------------------------------------------------


def test_json_field_key_is_bound_not_interpolated():
    request = _request(
        filters=[
            QueryFilter(
                field="attrs.user_agent", operator=QueryOperator.EQ, value="curl"
            )
        ]
    )
    sql, params = _build(request)

    assert "JSONExtractString(attrs, %(" in sql
    assert "user_agent" in params.values()


def test_json_key_cannot_escape_the_extract_call():
    request = _request(
        filters=[
            QueryFilter(
                field="attrs.x'); DROP TABLE logs_raw_mt; --",
                operator=QueryOperator.EQ,
                value="v",
            )
        ]
    )
    sql, params = _build(request)

    assert "DROP TABLE" not in sql
    assert "x'); DROP TABLE logs_raw_mt; --" in params.values()


# ---------------------------------------------------------------------------
# Time bounds and limits
# ---------------------------------------------------------------------------


def test_time_bounds_are_bound_parameters():
    sql, params = _build(_request())
    assert "ts >= %(_start_time)s" in sql
    assert params["_start_time"] == START
    assert params["_end_time"] == END


def test_limit_and_offset_are_integers_in_sql():
    request = _request(limit=250, offset=50)
    sql, _ = _build(request)
    assert "LIMIT 50, 250" in sql


def test_generated_sql_is_not_returned_to_callers():
    """
    The rendered statement previously came back in `query_info`, exposing
    internal query structure to API clients. It must not be echoed.
    """
    engine = AdvancedQueryEngine(clickhouse_client=None)
    request = _request()
    params = {}
    sql = engine._build_sql_query(request, "logs_raw_mt", params)
    assert "SELECT" in sql  # sanity: we did build a statement

    # The response contract must not carry it.
    import inspect

    source = inspect.getsource(AdvancedQueryEngine.execute_query)
    assert '"sql_query"' not in source, (
        "execute_query must not echo the rendered SQL back to callers."
    )
