"""
LogforgeQL pipeline commands (Phase 6), run against a real ClickHouse.

A seeded, known dataset is inserted into a scratch copy of logs_raw_mt and
each query's answer is compared with the same answer computed in Python.
Skipped when no ClickHouse is reachable (the unit job); the live-stack CI job
runs it.

Connection: LOGFORGE_TEST_CLICKHOUSE (host:port, default localhost:8123, then
localhost:8124), CLICKHOUSE_USER / CLICKHOUSE_PASSWORD (compose defaults).
"""

import json
import os
import random
import statistics
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import pytest

import logql_pipeline as lp

END = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
START = END - timedelta(hours=24)
TENANT = "pipeline-live"
OTHER = "someone-else"


def _client():
    try:
        import clickhouse_connect
    except ImportError:
        return None
    candidates = [os.getenv("LOGFORGE_TEST_CLICKHOUSE")] if os.getenv("LOGFORGE_TEST_CLICKHOUSE") else \
        ["localhost:8123", "localhost:8124"]
    for candidate in candidates:
        host, port = candidate.rsplit(":", 1)
        try:
            client = clickhouse_connect.get_client(
                host=host, port=int(port), username=os.getenv("CLICKHOUSE_USER", "logforge"),
                password=os.getenv("CLICKHOUSE_PASSWORD", "logforge123"),
                database=os.getenv("CLICKHOUSE_DATABASE", "logforge"), connect_timeout=2)
            client.query("SELECT 1")
            return client
        except Exception:
            continue
    return None


def make_events(n=3000, seed=7):
    rng = random.Random(seed)
    services = ["api", "web", "auth", "billing"]
    levels = ["info"] * 6 + ["warn"] * 2 + ["error"]
    users = [f"u{i}" for i in range(25)]
    ips = [f"10.0.{i // 10}.{i % 10}" for i in range(40)] + ["203.0.113.9"]
    events = []
    for i in range(n):
        ts = START + timedelta(seconds=rng.randrange(0, 24 * 3600 - 1))
        service = rng.choice(services)
        level = rng.choice(levels)
        status = rng.choice([200] * 8 + [404, 500, 503])
        duration = round(rng.lognormvariate(4.5, 0.8), 1)
        user = rng.choice(users)
        ip = rng.choice(ips)
        outcome = rng.choice(["success"] * 3 + ["failure"])
        msg = f"user={user} action=login outcome={outcome} took {int(duration)} ms"
        events.append({
            "ts": ts, "host": f"h{rng.randrange(5)}", "service": service, "level": level, "msg": msg,
            "status": status, "src_ip": ip, "user_id": user, "duration": duration, "outcome": outcome,
            "bytes": rng.randrange(100, 100000),
        })
    return events


@pytest.fixture(scope="module")
def ch():
    client = _client()
    if client is None:
        if os.getenv("LOGFORGE_REQUIRE_CLICKHOUSE") == "1":
            pytest.fail("ClickHouse is not reachable and LOGFORGE_REQUIRE_CLICKHOUSE=1")
        pytest.skip("ClickHouse is not reachable")
    table = f"test_pipeline_{uuid.uuid4().hex[:8]}"
    client.command(f"CREATE TABLE {table} AS logs_raw_mt")
    events = make_events()
    rows = []
    for e in events:
        attrs = {"duration_ms": e["duration"], "bytes": e["bytes"], "outcome": e["outcome"]}
        rows.append([e["ts"], e["host"], e["service"], e["level"], e["msg"], "", "", json.dumps(attrs),
                     e["status"], e["src_ip"], e["user_id"], e["ts"], 0, 16, "v1", TENANT])
    # Another tenant's events in the same table must never show up.
    rows += [[END - timedelta(minutes=5), "x", "api", "error", "user=intruder", "", "", "{}", 500, "6.6.6.6",
              "intruder", END, 0, 16, "v1", OTHER]] * 50
    columns = ["ts", "host", "service", "level", "msg", "trace_id", "span_id", "attrs", "status", "src_ip",
               "user_id", "ingested_at", "severity_num", "facility", "parser_version", "customer_id"]
    client.insert(table, rows, column_names=columns)
    yield client, table, events
    client.command(f"DROP TABLE IF EXISTS {table}")


def run(ch, query, **kw):
    client, table, _ = ch
    compiled = lp.compile_pipeline(query, customer_id=TENANT, start=START, end=END, table=table, **kw)
    return lp.execute(client, compiled)


def rows_of(ch, query, **kw):
    return run(ch, query, **kw)["rows"]


def test_stats_count_by_matches_python(ch):
    _, _, events = ch
    expected = Counter(e["service"] for e in events if e["level"] == "error")
    got = rows_of(ch, '| where level = "error" | stats count() by service')
    assert {r["service"]: r["count"] for r in got} == dict(expected)
    assert [r["service"] for r in got] == sorted(expected)  # stats ... by sorts by the group keys


def test_or_and_not_and_parentheses(ch):
    _, _, events = ch
    want = sum(1 for e in events if (e["service"] in ("api", "web") or e["status"] >= 500) and not e["level"] == "info")
    got = rows_of(ch, '| where (service = "api" or service = "web" or status >= 500) and not level = "info" '
                      '| stats count() as n')
    assert got == [{"n": want}]


def test_numeric_aggregations_on_attrs(ch):
    _, _, events = ch
    by = defaultdict(list)
    for e in events:
        by[e["service"]].append(e["duration"])
    got = rows_of(ch, "| stats avg(attrs.duration_ms) as avg, max(attrs.duration_ms) as max, "
                      "p95(attrs.duration_ms) as p95, median(attrs.duration_ms) as med, "
                      "dc(user_id) as users by service")
    for r in got:
        values = sorted(by[r["service"]])
        assert r["avg"] == pytest.approx(statistics.fmean(values), rel=1e-9)
        assert r["max"] == pytest.approx(max(values))
        assert r["p95"] == pytest.approx(statistics.quantiles(values, n=100, method="inclusive")[94], rel=0.02)
        assert r["med"] == pytest.approx(statistics.median(values), rel=0.02)
        assert r["users"] == len({e["user_id"] for e in events if e["service"] == r["service"]})


def test_top_10_source_ips_by_failed_logins_per_hour(ch):
    """The roadmap's example question, in one query."""
    _, _, events = ch
    failed = [e for e in events if e["outcome"] == "failure"]
    counts = Counter((e["ts"].replace(minute=0, second=0, microsecond=0), e["src_ip"]) for e in failed)
    got = rows_of(ch, '| where attrs.outcome = "failure" | bin span=1h ts | stats count() as failures by ts, src_ip '
                      '| sort -failures, ts, src_ip | head 10')
    expected = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))[:10]
    assert [(r["ts"], r["src_ip"], r["failures"]) for r in got] == [(t, ip, n) for (t, ip), n in expected]


def test_eval_case_and_stats_on_the_result(ch):
    _, _, events = ch

    def klass(s):
        return "5xx" if s >= 500 else "4xx" if s >= 400 else "ok"
    expected = Counter(klass(e["status"]) for e in events)
    got = rows_of(ch, '| eval class = case(status >= 500, "5xx", status >= 400, "4xx", "ok") '
                      '| stats count() by class')
    assert {r["class"]: r["count"] for r in got} == dict(expected)


def test_stats_after_stats(ch):
    _, _, events = ch
    failures = Counter(e["user_id"] for e in events if e["outcome"] == "failure")
    heavy = [n for n in failures.values() if n > 10]
    got = rows_of(ch, '| where attrs.outcome = "failure" | stats count() as failures by user_id '
                      '| where failures > 10 | stats count() as users, max(failures) as worst')
    assert got == [{"users": len(heavy), "worst": max(heavy)}]


def test_top_and_rare_with_percent(ch):
    _, _, events = ch
    counts = Counter(e["src_ip"] for e in events)
    got = rows_of(ch, "| top limit=3 src_ip")
    top3 = counts.most_common()
    assert [r["count"] for r in got] == [n for _, n in top3[:3]]
    assert got[0]["percent"] == pytest.approx(100 * top3[0][1] / len(events), abs=1e-3)
    rare = rows_of(ch, "| rare limit=1 src_ip")
    assert rare[0]["count"] == min(counts.values())


def test_top_by_group_is_per_group(ch):
    _, _, events = ch
    got = rows_of(ch, "| top limit=2 status by service")
    by = defaultdict(Counter)
    for e in events:
        by[e["service"]][e["status"]] += 1
    assert len(got) == 2 * len(by)
    for r in got:
        assert r["count"] in sorted(by[r["service"]].values(), reverse=True)[:2]
        assert r["percent"] == pytest.approx(100 * r["count"] / sum(by[r["service"]].values()), abs=1e-3)


def test_timechart_buckets_and_fills(ch):
    _, _, events = ch
    got = run(ch, '| where level = "error" | timechart span=1h count()')
    assert got["result_type"] == "timechart"
    buckets = Counter(e["ts"].replace(minute=0, second=0, microsecond=0) for e in events if e["level"] == "error")
    assert len(got["rows"]) == 24  # every hour, including empty ones
    assert {r["_time"]: r["count"] for r in got["rows"] if r["count"]} == dict(buckets)


def test_timechart_by_with_other(ch):
    got = rows_of(ch, "| timechart span=6h limit=2 count() by service")
    assert {r["service"] for r in got} <= {"api", "web", "auth", "billing", "OTHER"}
    assert len({r["service"] for r in got}) == 3
    assert sum(r["count"] for r in got) == len(ch[2])


def test_dedup_keeps_the_latest_per_key(ch):
    _, _, events = ch
    got = rows_of(ch, "| dedup user_id | fields ts, user_id")
    latest = {}
    for e in events:
        if e["user_id"] not in latest or e["ts"] > latest[e["user_id"]]:
            latest[e["user_id"]] = e["ts"]
    assert {r["user_id"]: r["ts"] for r in got} == latest
    assert list(got[0]) == ["ts", "user_id"]


def test_rename_fields_sort_head_and_events_shape(ch):
    _, _, events = ch
    got = run(ch, '| where status = 503 | rename src_ip as client | fields ts, client, status | sort ts | head 3')
    expected = sorted((e for e in events if e["status"] == 503), key=lambda e: e["ts"])[:3]
    assert got["result_type"] == "events"
    assert [(r["ts"], r["client"]) for r in got["rows"]] == [(e["ts"], e["src_ip"]) for e in expected]


def test_events_default_to_newest_first_with_computed_fields(ch):
    _, _, events = ch
    got = rows_of(ch, '| eval kb = round(attrs.bytes / 1024, 2) | head 5')
    newest = sorted(events, key=lambda e: e["ts"], reverse=True)[:5]
    assert [r["ts"] for r in got] == [e["ts"] for e in newest]
    assert [r["kb"] for r in got] == [round(e["bytes"] / 1024, 2) for e in newest]
    assert isinstance(got[0]["attrs"], dict) and got[0]["msg"].startswith("user=")


def test_bin_numeric(ch):
    _, _, events = ch
    got = rows_of(ch, "| bin span=100 attrs.bytes as bucket | stats count() by bucket | head 1000")
    expected = Counter((e["bytes"] // 100) * 100 for e in events)
    assert {int(r["bucket"]): r["count"] for r in got} == dict(expected)


def test_eventstats_compares_each_event_with_its_group(ch):
    _, _, events = ch
    avg = {s: statistics.fmean(e["duration"] for e in events if e["service"] == s) for s in {"api", "web", "auth", "billing"}}
    want = sum(1 for e in events if e["duration"] > 3 * avg[e["service"]])
    got = rows_of(ch, "| eventstats avg(attrs.duration_ms) as svc_avg by service "
                      "| where attrs.duration_ms > 3 * svc_avg | stats count() as n")
    assert got == [{"n": want}]


def test_rex_then_stats(ch):
    _, _, events = ch
    got = rows_of(ch, r'| rex "took (?<took>\d+) ms" | where took >= 200 | stats count() as n')
    assert got == [{"n": sum(1 for e in events if int(e["duration"]) >= 200)}]


def test_functions(ch):
    _, _, events = ch
    got = rows_of(ch, '| where cidrmatch("10.0.1.0/24", src_ip) and match(msg, "outcome=fail") '
                      '| eval u = upper(user_id), l = len(user_id), h = hour(ts) | stats count() as n, '
                      'values(u) as us')
    expected = [e for e in events if e["src_ip"].startswith("10.0.1.") and e["outcome"] == "failure"]
    assert got[0]["n"] == len(expected)
    assert got[0]["us"] == sorted({e["user_id"].upper() for e in expected})


def test_coalesce_and_isnull_treat_missing_text_as_null(ch):
    got = rows_of(ch, '| eval region = coalesce(attrs.region, "none") | where isnull(attrs.region) '
                      '| stats count() by region')
    assert got == [{"region": "none", "count": len(ch[2])}]


def test_variables(ch):
    _, _, events = ch
    got = rows_of(ch, "| where service = $service and status in $codes | stats count() as n",
                  variables={"service": "api", "codes": [500, 503]})
    assert got == [{"n": sum(1 for e in events if e["service"] == "api" and e["status"] in (500, 503))}]


def test_tenant_isolation(ch):
    got = rows_of(ch, '| where user_id = "intruder" | stats count() as n')
    assert got == [{"n": 0}]
    assert all(r["user_id"] != "intruder" for r in rows_of(ch, "| head 10000"))


def test_ocsf_fields_work_in_pipelines(ch):
    _, _, events = ch
    got = rows_of(ch, "| stats count() by ocsf.src_endpoint.ip | sort -count | head 1")
    top = Counter(e["src_ip"] for e in events).most_common(1)[0]
    assert got == [{"ocsf.src_endpoint.ip": top[0], "count": top[1]}]
