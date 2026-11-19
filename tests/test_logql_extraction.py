"""
Search-time field extraction in LogforgeQL (Phase 5, schema-on-read):

    | rex [field=<f>] "<regex with named groups>"     each (?<name>...) is a field
    | parse [field=<f>] "<text with * wildcards>" as a, b
    | json [field=<f>] "<path>" [as name], ...        path into JSON text

The default field is msg. Extracted names can be used by later where,
stats ... by, sort, and come back with each log under `extracted`. They
compile to ClickHouse expressions (extractGroups, JSONExtractString) whose
patterns and paths are bound parameters, never SQL text.
"""

from datetime import datetime, timedelta, timezone

import pytest

import logql
from logql import LogQLSyntaxError
from query_engine import AdvancedQueryEngine, AdvancedQueryRequest


def payload(query):
    return logql.compile_to_request_payload(query)


def sql_of(query):
    p = payload(query)
    now = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
    request = AdvancedQueryRequest(**{**p, "start_time": now - timedelta(hours=1), "end_time": now})
    engine = AdvancedQueryEngine.__new__(AdvancedQueryEngine)
    engine.base_table, engine.normalized_table = "logs_raw_mt", "logs_normalized_mt"
    params = {}
    table = engine._select_optimal_table(request)
    return engine._build_sql_query(request, table, params), params, table


def test_rex_named_groups_become_fields():
    p = payload(r'| rex "Failed password for (?<user>\S+) from (?<ip>\S+)" | where user = "root"')
    assert p["extractions"] == [
        {"name": "user", "kind": "regex", "source": "msg", "pattern": r"Failed password for (?P<user>\S+) from (?P<ip>\S+)",
         "group": 1},
        {"name": "ip", "kind": "regex", "source": "msg", "pattern": r"Failed password for (?P<user>\S+) from (?P<ip>\S+)",
         "group": 2}]
    assert p["filters"] == [{"field": "user", "operator": "eq", "value": "root"}]


def test_parse_wildcards_and_json_paths():
    p = payload('| parse "order * by *" as order_id, customer | where order_id > 100')
    assert [(e["name"], e["group"]) for e in p["extractions"]] == [("order_id", 1), ("customer", 2)]
    assert p["extractions"][0]["pattern"] == "order (.*?) by (.*)"
    p = payload('| json field=attrs.payload "user.name" as who, "action" | stats count() by who, action')
    assert p["extractions"] == [
        {"name": "who", "kind": "json", "source": "attrs.payload", "path": ["user", "name"]},
        {"name": "action", "kind": "json", "source": "attrs.payload", "path": ["action"]}]
    assert p["group_by"] == ["who", "action"]


@pytest.mark.parametrize("query, message", [
    ('| rex "no groups here"', "named group"),
    ('| rex "(?<status>\\d+)"', "already a field"),
    ('| rex "(?<a>x)(?<a>y)"', "redefinition|twice"),
    ('| rex "(?<a>x)(?=y)"', "lookaround"),
    ('| rex "(?<a>x)\\1"', "backreference"),
    ('| rex "(?<a>[x"', "invalid regular expression"),
    ('| parse "a * b *" as one', "2 wildcards but 1 name"),
    ('| json "a.b" as level', "already a field"),
    ('| rex field=nope "(?<a>x)"', "Unknown query field"),
    ('| where who = "x" | rex "(?<who>\\w+)"', "Unknown query field"),
])
def test_extraction_errors_are_explained(query, message):
    with pytest.raises((LogQLSyntaxError, Exception), match=message):
        payload(query)


def test_sql_uses_bound_patterns_and_paths():
    sql, params, table = sql_of(r'| rex "user=(?<user>\w+)" | where user = "root" | limit 5')
    assert table == "logs_raw_mt"
    assert "SELECT *, (extractGroups(msg, %(" in sql and ")[1]) AS user" in sql
    assert "user=" not in sql  # the pattern is a parameter
    assert r"user=(?P<user>\w+)" in params.values()
    assert "(extractGroups(msg, %(" in sql.split("WHERE", 1)[1]


def test_extracted_fields_in_stats_sort_and_numeric_filters():
    sql, params, _ = sql_of('| parse "took * ms" as took | where took > 500 | stats count() by took')
    assert "toFloat64OrNull((extractGroups(msg" in sql
    assert "AS took" in sql and "GROUP BY took" in sql
    sql, params, _ = sql_of('| json "user.name" as who | sort who asc')
    assert "JSONExtractString(msg, %(" in sql and "ORDER BY (JSONExtractString" in sql
    assert {"user", "name"} <= set(params.values())


def test_results_carry_the_extracted_values():
    engine = AdvancedQueryEngine.__new__(AdvancedQueryEngine)
    p = payload(r'| rex "user=(?<user>\w+) ip=(?<ip>\S+)"')
    now = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
    request = AdvancedQueryRequest(**{**p, "start_time": now - timedelta(hours=1), "end_time": now})
    row = [now, "h", "svc", "info", "user=root ip=1.2.3.4", "", "", "{}", 0, "", "", 0, 16, "v1", now, "acme",
           "root", "1.2.3.4"]
    logs = engine._process_log_results([row], request).logs
    assert logs[0]["extracted"] == {"user": "root", "ip": "1.2.3.4"} and logs[0]["msg"] == "user=root ip=1.2.3.4"


def test_the_router_passes_extractions_through():
    from routers.query import build_query_request

    p = payload(r'| rex "user=(?<user>\w+)" | where user = "root"')
    p.update(start_time="2026-11-19T10:00:00+00:00", end_time="2026-11-19T11:00:00+00:00")
    request = build_query_request(p, "acme")
    assert [e.name for e in request.extractions] == ["user"]


def test_escaped_quotes_inside_patterns_do_not_split_stages():
    """Found by the extraction benchmark: `\\"` inside a quoted pattern ended
    the string early, so the rest of the query was swallowed into the stage."""
    p = payload(r'| rex field=attrs "\"region\":\"(?<region>[^\"|]+)\"" | where region = "eu-west-1" | stats count()')
    assert p["extractions"][0]["pattern"] == r'"region":"(?P<region>[^"|]+)"'
    assert p["filters"] == [{"field": "region", "operator": "eq", "value": "eu-west-1"}]
    p = payload(r'| where msg = "say \"a or b\"" | limit 1')
    assert p["filters"][0]["value"] == 'say "a or b"'
