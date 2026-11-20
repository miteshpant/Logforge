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
    assert "GROUP BY `__ek0`" in q.sql and "isNotDistinctFrom" in q.sql and q.result_type == "events"


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


# ---------------------------------------------------------------------------
# Lookups and joins (P6.2)
# ---------------------------------------------------------------------------

LOOKUPS = {"users": lp.LookupMeta(name="users", version=3, columns=["user_id", "department", "manager"],
                                  key="user_id"),
           "blocklist": lp.LookupMeta(name="blocklist", version=1, columns=["value"], key="value")}


def test_lookup_joins_the_current_version_of_the_tenants_table():
    q = compile_("| lookup users user_id output department as dept | stats count() by dept", lookups=LOOKUPS)
    assert "lookup_rows_mt" in q.sql and "ANY LEFT JOIN" in q.sql and "version = 3" in q.sql
    assert {"acme", "users", "department"} <= set(q.params.values())
    assert q.columns == ["dept", "count"]
    # every output column by default, and a field matched to a differently named key
    q = compile_("| lookup users attrs.actor as user_id", lookups=LOOKUPS)
    assert q.columns[-2:] == ["department", "manager"]


def test_inlookup_is_a_set_membership_test():
    q = compile_('| where inlookup("blocklist", src_ip) | stats count() as hits', lookups=LOOKUPS)
    assert "IN (SELECT key FROM lookup_rows_mt" in q.sql and "blocklist" in q.params.values()


@pytest.mark.parametrize("query, message", [
    ("| lookup nope user_id", "Unknown lookup: nope"),
    ("| lookup users user_id output salary", "users has no column salary"),
    ("| lookup users", "`lookup` needs"),
    ('| where inlookup(src_ip, "blocklist")', "quoted lookup name"),
    ('| where inlookup("nope", src_ip)', "Unknown lookup: nope"),
    ("| join user_id", "subsearch"),
    ("| join user_id [ | stats count() as n by host ]", "user_id is not in the subsearch"),
    ("| stats count() by user_id | join user_id [ | stats count() by user_id ]", "both sides have count"),
    ("| join type=outer user_id [ | stats count() as n by user_id ]", "type must be inner or left"),
    ("| join max=100000 user_id [ | stats count() as n by user_id ]", "at most 50000"),
])
def test_lookup_and_join_errors(query, message):
    with pytest.raises(PipelineError, match=message):
        compile_(query, lookups=LOOKUPS)


def test_join_runs_the_subsearch_on_the_same_tenant_and_window_bounded():
    q = compile_('| where attrs.outcome = "failure" | stats count() as failures by user_id '
                 '| join type=left max=500 user_id [ | where attrs.outcome = "success" | stats count() as ok by user_id ] '
                 '| where failures > ok', lookups=LOOKUPS)
    assert q.columns == ["user_id", "failures", "ok"]
    assert " LEFT JOIN (" in q.sql and "LIMIT 500" in q.sql and "LIMIT 1 BY `user_id`" in q.sql
    assert q.sql.count("customer_id = %(") == 2  # both sides are tenant-bound
    assert "'acme'" not in q.sql


def test_join_keeps_event_fields_available():
    q = compile_("| join user_id [ | stats dc(src_ip) as ips by user_id ] | where ips > 3 | head 5", lookups=LOOKUPS)
    assert q.result_type == "events" and q.columns[-1] == "ips"


def test_quoted_free_text_searches_for_the_text_inside_the_quotes():
    q = compile_('"connection reset" | stats count() as n')
    assert "%connection reset%" in q.params.values()
    q = compile_('timeout 50% | head 1')
    assert "%timeout 50\\%%" in q.params.values()  # LIKE wildcards in the text are literal


# ---------------------------------------------------------------------------
# Hourly counts (P6.5): exact count queries read the hourly projection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("query", [
    "| stats count() by service",
    '| where level = "error" or status >= 500 | stats count() as n by service, level',
    "| timechart span=1h count() by service",
    "| timechart span=6h count()",
    "| top limit=3 service",
    '| eval failed = if(status >= 500, "yes", "no") | stats count() by failed | sort -count',
    "| stats count() as n by service | where n > 10 | stats count() as services",
    "| last 7d | stats count()",
])
def test_count_queries_use_the_hourly_counts(query):
    q = compile_(query, end=END, start=END - timedelta(days=7, minutes=30))
    assert q.rollup, query
    assert "toStartOfHour(ts) >=" in q.sql and "UNION ALL" in q.sql and "sum(`_n`)" in q.sql


@pytest.mark.parametrize("query", [
    "| stats dc(src_ip) by service",              # not a count
    "| stats count() by host",                    # host is not in the projection
    '| where attrs.outcome = "x" | stats count()',  # a field outside it
    "error | stats count()",                      # free text
    "| timechart span=5m count()",                # finer than an hour
    "| head 10 | stats count()",                  # row stages before the count
    "| stats count() by service | lookup users service",
    "| where service = \"api\"",                  # events, no aggregation
    '| where ts > "2026-11-19" | stats count()',  # ts is hourly in the projection
    "| eventstats count() by service | stats count()",
])
def test_other_queries_scan_the_events(query):
    lookups = {"users": lp.LookupMeta("users", 1, ["service", "x"], "service")}
    assert not compile_(query, start=END - timedelta(days=7), lookups=lookups).rollup, query


def test_windows_under_two_hours_scan_the_events():
    assert not compile_("| stats count()", start=END - timedelta(minutes=90)).rollup


def test_the_projection_can_be_switched_off():
    assert not compile_("| stats count() by service", start=END - timedelta(days=7), rollup=False).rollup


def test_function_results_are_single_operands():
    """Found by the analyst questions: `not cidrmatch(...)` compiled to
    NOT (valid ip) AND (in range), which is never true."""
    q = compile_('| where not cidrmatch("10.0.0.0/8", src_ip) and isnull(attrs.x) = 0 | stats count() as n')
    assert "(NOT ((isIPv4String(" in q.sql
    assert "((NOT (isNotNull(" in q.sql


# ---------------------------------------------------------------------------
# attrs reads at 100 M rows (P6.7)
# ---------------------------------------------------------------------------

def test_an_attrs_field_is_parsed_once_in_the_common_case():
    """JSONHas + JSONExtractString parsed every row's JSON twice; reading the
    key and falling back only when it is empty parses it once."""
    q = compile_("| stats count() by attrs.outcome")
    assert "JSONHas" not in q.sql
    assert q.sql.count("JSONExtractString(attrs, 'attrs'") >= 1  # the legacy envelope is still read


@pytest.mark.parametrize("query, prefilter", [
    ('| where attrs.outcome = "failure" | stats count() as n', "position(attrs, %("),
    ('| where attrs.country in ["DE", "FR"] | stats count() as n', "multiSearchAny(attrs, ["),
])
def test_string_equality_on_attrs_is_prefiltered_by_a_substring_scan(query, prefilter):
    q = compile_(query)
    assert prefilter in q.sql
    assert "failure" in q.params.values() or "DE" in q.params.values()


@pytest.mark.parametrize("query", [
    '| where attrs.name = "Zoë" | head 1',          # non-ASCII is escaped in stored JSON
    '| where attrs.q = "say \\"hi\\"" | head 1',   # so are quotes
    "| where attrs.n = 5 | head 1",                # numbers compare as numbers
    '| where attrs.outcome != "failure" | head 1', # only = and in narrow
    '| where ocsf.status = "Failure" | head 1',    # derived from several sources
])
def test_no_prefilter_where_it_could_drop_a_match(query):
    q = compile_(query)
    assert "position(attrs" not in q.sql and "multiSearchAny(attrs" not in q.sql
