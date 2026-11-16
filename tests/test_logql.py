"""
Tests for ENH-028 -- LogforgeQL, a pipe-oriented text query language.

The only query interface was a JSON filter DSL, unusable for interactive
hunting. Analysts expect SPL / KQL / LogQL; requiring hand-written JSON is a
real barrier for experienced SOC teams.

The security-critical property, tested hardest below: the language compiles to
an `AdvancedQueryRequest` and is executed by the parameterised builder from
ENH-002. It must **never** emit SQL text, or it would reintroduce the injection
class that ticket removed.
"""

from datetime import datetime, timedelta, timezone

import pytest

from logql import LogQLSyntaxError, compile_to_request_payload, parse
from query_engine import (
    AdvancedQueryEngine,
    AggregationType,
    QueryFieldError,
    QueryOperator,
    SortOrder,
)
from routers.query import build_query_request

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = START + timedelta(hours=1)


def _build_sql(query_text, customer_id="tenant-a"):
    """Compile a query all the way to SQL + bound parameters."""
    payload = compile_to_request_payload(query_text)
    payload.setdefault("start_time", START)
    payload.setdefault("end_time", END)

    request = build_query_request(payload, customer_id)
    engine = AdvancedQueryEngine(clickhouse_client=None)
    params = {}
    sql = engine._build_sql_query(
        request, engine._select_optimal_table(request), params
    )
    return sql, params


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_free_text_search():
    parsed = parse("connection timeout")
    assert parsed.text_search == "connection timeout"


def test_simple_where_clause():
    parsed = parse('| where service = "api"')

    assert len(parsed.filters) == 1
    assert parsed.filters[0].field == "service"
    assert parsed.filters[0].operator == QueryOperator.EQ
    assert parsed.filters[0].value == "api"


def test_free_text_combined_with_where():
    parsed = parse('timeout | where level = "error"')

    assert parsed.text_search == "timeout"
    assert len(parsed.filters) == 1


@pytest.mark.parametrize(
    "expression,operator",
    [
        ('service = "api"', QueryOperator.EQ),
        ('service != "api"', QueryOperator.NE),
        ("status > 400", QueryOperator.GT),
        ("status >= 500", QueryOperator.GTE),
        ("status < 300", QueryOperator.LT),
        ("status <= 299", QueryOperator.LTE),
        ('msg contains "panic"', QueryOperator.CONTAINS),
        ('msg startswith "GET"', QueryOperator.STARTS_WITH),
        ('msg endswith "done"', QueryOperator.ENDS_WITH),
        ('service =~ "api|web"', QueryOperator.REGEX),
    ],
)
def test_all_operators_parse(expression, operator):
    parsed = parse(f"| where {expression}")
    assert parsed.filters[0].operator == operator


def test_in_operator_with_a_list():
    parsed = parse('| where level in ["error", "warn"]')

    assert parsed.filters[0].operator == QueryOperator.IN
    assert parsed.filters[0].value == ["error", "warn"]


def test_multiple_and_conditions():
    parsed = parse('| where service = "api" and status >= 500')
    assert len(parsed.filters) == 2


def test_numeric_values_keep_their_type():
    parsed = parse("| where status >= 500")
    assert parsed.filters[0].value == 500
    assert isinstance(parsed.filters[0].value, int)


def test_quoted_values_stay_strings():
    parsed = parse('| where service = "500"')
    assert parsed.filters[0].value == "500"


def test_stats_aggregation():
    parsed = parse("| stats count()")

    assert len(parsed.aggregations) == 1
    assert parsed.aggregations[0].type == AggregationType.COUNT


def test_stats_with_group_by():
    parsed = parse("| stats count() by service, level")

    assert parsed.group_by == ["service", "level"]


def test_sort_and_limit():
    parsed = parse("| sort ts asc | limit 25")

    assert parsed.sort_field == "ts"
    assert parsed.sort_order == SortOrder.ASC
    assert parsed.limit == 25


def test_full_pipeline():
    parsed = parse(
        'error | where service = "api" and status >= 500 '
        "| stats count() by service | sort service desc | limit 10"
    )

    assert parsed.text_search == "error"
    assert len(parsed.filters) == 2
    assert parsed.group_by == ["service"]
    assert parsed.limit == 10


# ---------------------------------------------------------------------------
# SECURITY: the language must never emit SQL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        "x' OR customer_id != '",
        "'; DROP TABLE logs_raw_mt; --",
        "' UNION SELECT * FROM users_mt --",
        "' OR '1'='1",
    ],
)
def test_injection_in_a_value_is_bound_not_interpolated(payload):
    """
    The whole reason the language targets the request model rather than
    generating SQL: it inherits ENH-002's parameter binding.
    """
    sql, params = _build_sql(f'| where service = "{payload}"')

    assert payload not in sql, f"Payload leaked into SQL: {sql}"
    assert payload in params.values()
    assert " OR " not in sql.upper()
    assert "DROP" not in sql.upper()


@pytest.mark.parametrize(
    "payload",
    ["x' OR 1=1 --", "'; DROP TABLE logs_raw_mt; --"],
)
def test_injection_in_free_text_is_bound(payload):
    sql, params = _build_sql(payload)

    assert payload not in sql
    assert any(payload in str(v) for v in params.values())


def test_tenant_isolation_survives_a_logql_query():
    """A text query must not be able to escape its tenant."""
    sql, params = _build_sql(
        '| where service = "x\' OR customer_id != \'"', customer_id="tenant-a"
    )

    assert "tenant-a" in params.values()
    assert " OR " not in sql.upper()


def test_unknown_field_is_rejected():
    """
    The language inherits the ENH-002 identifier allow-list, so it cannot
    address columns the query engine does not know.
    """
    with pytest.raises((LogQLSyntaxError, QueryFieldError)):
        parse('| where password_hash = "x"')


def test_malicious_sort_field_is_rejected():
    with pytest.raises((LogQLSyntaxError, QueryFieldError)):
        parse("| sort ts; DROP TABLE logs_raw_mt")


def test_malicious_group_by_is_rejected():
    with pytest.raises((LogQLSyntaxError, QueryFieldError)):
        parse("| stats count() by service; DROP TABLE x")


def test_compiled_payload_contains_no_sql():
    payload = compile_to_request_payload(
        '| where service = "api" | stats count() by level'
    )
    text = str(payload).upper()

    for keyword in ("SELECT", "FROM", "WHERE ", "DROP", "UNION"):
        assert keyword not in text, f"Compiled payload contains SQL: {keyword}"


def test_compiler_does_not_set_a_tenant_filter():
    """
    Tenant isolation stays the router's responsibility. If the language set it,
    a language bug would become a tenancy bug.
    """
    payload = compile_to_request_payload('| where service = "api"')
    fields = [f["field"] for f in payload["filters"]]

    assert "customer_id" not in fields


# ---------------------------------------------------------------------------
# Error handling -- explain, never guess
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    [
        "| where",
        "| where service",
        "| stats",
        "| stats notafunction()",
        "| sort",
        "| limit abc",
        "| limit -5",
    ],
)
def test_malformed_queries_raise_a_syntax_error(query):
    with pytest.raises((LogQLSyntaxError, QueryFieldError)):
        parse(query)


def test_unknown_stage_after_the_first_is_rejected():
    """
    A typo'd stage name must be an error, not silently ignored -- silently
    dropping `| limir 10` would return far more data than the analyst asked for.
    """
    with pytest.raises(LogQLSyntaxError, match="Unknown stage"):
        parse('| where service = "api" | frobnicate service')


def test_leading_bare_text_is_treated_as_free_text_search():
    """
    Documents a deliberate ambiguity: the FIRST stage may be free text, so
    `foo bar` is a search, not an unknown stage. Only later stages must name a
    known keyword. This is how LogQL and SPL both behave.
    """
    parsed = parse("frobnicate service")
    assert parsed.text_search == "frobnicate service"
    assert parsed.filters == []


def test_or_is_rejected_rather_than_silently_treated_as_and():
    """
    The request model ANDs its filters. Silently treating `or` as `and` would
    return wrong results, which is worse than an error message.
    """
    with pytest.raises(LogQLSyntaxError, match="not supported"):
        parse('| where service = "a" or service = "b"')


def test_error_message_suggests_an_alternative():
    """A good error tells the analyst what to do instead."""
    with pytest.raises(LogQLSyntaxError) as err:
        parse('| where service = "a" or service = "b"')

    message = str(err.value)
    assert "in [" in message or "=~" in message


def test_empty_query_raises():
    with pytest.raises(LogQLSyntaxError):
        parse("")


# ---------------------------------------------------------------------------
# Compilation to a working query
# ---------------------------------------------------------------------------


def test_compiled_query_produces_valid_sql():
    sql, params = _build_sql('error | where service = "api" | limit 10')

    assert sql.startswith("SELECT")
    assert "FROM" in sql
    assert "LIMIT 0, 10" in sql
    assert "api" in params.values()


def test_aggregation_query_compiles():
    sql, _ = _build_sql("| stats count() by service")

    assert "count()" in sql
    assert "GROUP BY service" in sql


def test_sort_direction_reaches_the_sql():
    sql, _ = _build_sql("| sort ts asc")
    assert "ORDER BY ts ASC" in sql


def test_json_field_access_still_works():
    sql, params = _build_sql('| where attrs.user_agent = "curl"')

    assert "JSONExtractString(attrs, %(" in sql
    assert "user_agent" in params.values()


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


def test_endpoint_exists_and_uses_the_isolation_choke_point():
    import inspect

    from routers import query as query_router

    source = inspect.getsource(query_router.logql_query)

    assert "compile_to_request_payload" in source
    assert "build_query_request" in source, (
        "The endpoint must route through the tenant-isolation choke point."
    )


def test_endpoint_returns_400_for_a_syntax_error():
    import inspect

    from routers import query as query_router

    source = inspect.getsource(query_router.logql_query)

    assert "status_code=400" in source
    assert "LogQLSyntaxError" in source


# --- `*` match-all selector -------------------------------------------------
# QA found `* | where service = "checkout"` returned nothing: the `*` was sent
# as a literal full-text search term.

def test_star_selector_means_match_all():
    from logql import compile_to_request_payload

    payload = compile_to_request_payload('* | where service = "checkout" | limit 10')
    assert "text_search" not in payload
    assert payload["filters"][0]["field"] == "service"


def test_star_alone_is_match_all():
    from logql import compile_to_request_payload

    assert "text_search" not in compile_to_request_payload("*")


def test_star_with_stats_by_keeps_grouping():
    from logql import compile_to_request_payload

    payload = compile_to_request_payload("* | stats count() by service")
    assert "text_search" not in payload
    assert payload["group_by"] == ["service"]


def test_star_inside_a_search_term_is_still_text():
    from logql import compile_to_request_payload

    assert compile_to_request_payload("err*r")["text_search"] == "err*r"
