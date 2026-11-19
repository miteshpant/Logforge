"""
LogforgeQL pipeline commands (Phase 6): the compiler, checked without a
database. What the queries return is checked against ClickHouse in
test_logql_pipeline_live.py.

The pipeline compiler turns a query into one parameterised ClickHouse
statement. Every stage wraps the previous one as a subquery. The tenant and
the time window are applied at the innermost level, every value a user typed
is a bound parameter, and names are checked before they become SQL.
"""

from datetime import datetime, timedelta, timezone

import pytest

import logql
import logql_pipeline as lp
from logql_pipeline import PipelineError

END = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
START = END - timedelta(hours=24)


def compile_(query, **kw):
    kw.setdefault("customer_id", "acme")
    kw.setdefault("start", START)
    kw.setdefault("end", END)
    return lp.compile_pipeline(query, **kw)


def test_tenant_and_window_are_applied_innermost_and_bound():
    q = compile_('| where service = "api" | stats count() by level')
    inner = q.sql[q.sql.rindex("FROM logs_raw_mt"):]
    assert "customer_id = %(" in inner and "ts >= %(" in inner and "ts <= %(" in inner
    assert "acme" in q.params.values() and START in q.params.values() and END in q.params.values()
    assert "'acme'" not in q.sql and "'api'" not in q.sql and "api" in q.params.values()
    assert q.result_type == "table" and q.columns == ["level", "count"]


def test_user_strings_never_reach_the_sql_text():
    nasty = "x') OR 1=1 OR ('"
    q = compile_(f'| where msg = "{nasty}" | eval tag = "{nasty}" | where tag contains "{nasty}"')
    assert nasty not in q.sql and "OR 1=1" not in q.sql
    assert nasty in q.params.values() and f"%{nasty}%" in q.params.values()


@pytest.mark.parametrize("query, message", [
    ("| eval `x` = 1", "Unexpected character"),
    ("| eval x-y = 1", "eval"),
    ("| rename level as `a`", "Unexpected character|name"),
    ("| eval x = frobnicate(1)", "Unknown function: frobnicate"),
    ("| where nosuchfield = 1", "Unknown query field"),
    ("| stats count() by service | where level = \"error\"", "level is not available"),
    ("| stats count() by service | stats avg(duration) ", "duration is not available"),
    ("| stats sum() by service", "sum needs a field"),
    ("| stats count() as n, avg(status) as n", "twice"),
    ("| eval x = if(1)", "if takes 3 arguments"),
    ("| head 0", "positive"),
    ("| head 1000000", "at most"),
    ("| sort", "`sort` needs"),
    ("| timechart span=7q count()", "span"),
    ("| bin status", "span"),
    ("| top", "`top` needs"),
    ("| dedup", "`dedup` needs"),
    ("| fields", "`fields` needs"),
    ("| where $nope = 1", "Unknown variable: \\$nope"),
    ("| eval x = (1 + ", "end of the expression"),
    ("| where status >", "end of the expression"),
    ("| frobnicate", "Unknown stage: 'frobnicate'"),
])
def test_errors_are_explained(query, message):
    with pytest.raises(PipelineError, match=message):
        compile_(query)


def test_expressions_compile_with_types():
    q = compile_('| where (service = "api" or service = "web") and not level in ["debug", "info"] '
                 '| eval slow = if(attrs.duration_ms > 1000, "slow", "ok"), kb = round(attrs.bytes / 1024, 1)')
    # attrs values are text: numeric comparisons and arithmetic convert them
    assert "toFloat64OrNull(" in q.sql
    assert {"api", "web", "debug", "info", "slow", "ok"} <= set(q.params.values())
    assert q.result_type == "events" and q.columns[-2:] == ["slow", "kb"]


def test_numbers_are_rendered_from_parsed_values_only():
    q = compile_("| where status >= 500 | eval x = 2.5 * status - 1e3")
    assert ">= 500" in q.sql and "2.5" in q.sql and "1000.0" in q.sql


def test_variables_are_bound_values():
    q = compile_('| where service = $service and host in $hosts', variables={"service": "api", "hosts": ["a", "b"]})
    assert "api" in q.params.values() and {"a", "b"} <= set(q.params.values())
    assert "'api'" not in q.sql


def test_timechart_picks_a_span_and_fills_gaps():
    q = compile_("| timechart count()")
    assert q.result_type == "timechart" and q.columns == ["_time", "count"]
    assert "toStartOfInterval(toDateTime(ts, 'UTC'), INTERVAL 30 minute)" in q.sql and "WITH FILL" in q.sql
    q = compile_("| timechart span=1h limit=5 avg(status) by service")
    assert q.columns == ["_time", "service", "avg(status)"]
    assert "INTERVAL 1 hour" in q.sql and "'OTHER'" in q.sql


def test_stats_after_stats_and_eventstats():
    q = compile_("| stats count() as failures by user_id | where failures > 3 | stats count() as users, "
                 "max(failures) as worst")
    assert q.columns == ["users", "worst"]
    q = compile_("| eventstats avg(status) as avg_status by service | where status > avg_status * 2")
    assert "OVER (PARTITION BY" in q.sql and q.result_type == "events"


def test_the_row_limit_is_always_applied():
    assert compile_("| stats count() by host").sql.rstrip().endswith("LIMIT 10000")
    assert compile_("| head 5").sql.rstrip().endswith("LIMIT 5")
    assert compile_("error").sql.rstrip().endswith("LIMIT 100")


def test_routing_keeps_v1_queries_on_the_v1_compiler():
    """Queries the original LogforgeQL accepts keep their exact behaviour; any
    query that uses Phase 6 syntax goes to the pipeline compiler."""
    for query in ['error | where level = "error" | limit 100', "| stats count() by level",
                  '| where msg = "costs $5" | stats count() by level',
                  '| rex "user=(?<user>\\w+)" | where user = "root"', "| last 24h"]:
        assert not lp.uses_pipeline(query), query
    for query in ['| where level = "error" or level = "fatal"', "| eval x = 1", "| stats p95(status) by service",
                  "| timechart count()", "| top src_ip", "| stats count() as n by service", "| head 5",
                  "| where (status > 1)", "| stats dc(src_ip)", "| stats count by service",
                  '| stats count() by service | where level = "x"', "| where service = $svc"]:
        assert lp.uses_pipeline(query), query


def test_extraction_stages_are_shared_with_v1():
    q = compile_(r'| rex "user=(?<user>\w+)" | stats count() by user | sort -count | head 3')
    assert q.columns == ["user", "count"]
    assert r"user=(?P<user>\w+)" in q.params.values()
    with pytest.raises(PipelineError, match="named group"):
        compile_('| rex "nothing" | head 1')


def test_v1_compile_is_unchanged():
    assert logql.compile_to_request_payload("| stats count() by level")["group_by"] == ["level"]
