"""
Phase 6 acceptance: 30 analyst questions, each answered by one LogforgeQL
query (tests/eval/analytics/questions.yml), checked against the same answer
computed in Python over a seeded week of auth, HTTP and DNS events.

Runs against ClickHouse (skipped when none is reachable; the live-stack CI
job runs it).
"""

import json
import random
import re
import statistics
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

import logql_pipeline as lp
from test_logql_pipeline_live import MIGRATION, _client

END = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
START = END - timedelta(days=7)
TENANT = "analyst-questions"
QUESTIONS = yaml.safe_load((Path(__file__).parent / "eval" / "analytics" / "questions.yml").read_text())["questions"]

HOSTS = [f"h{i:02d}" for i in range(20)]
USERS = [f"u{i:03d}" for i in range(100)]
ATTACKERS = USERS[90:]          # only ever fail to log in
INTERNAL = [f"10.0.{a}.{b}" for a in range(20) for b in range(10)]
EXTERNAL = [f"203.0.113.{i}" for i in range(20)]
BLOCKLIST = EXTERNAL[:3]
COUNTRIES = ["US", "DE", "IN", "BR", "GB", "CN"]
AGENTS = ["Mozilla/5.0"] * 30 + ["curl/8.4"] * 6 + ["python-requests/2.31"] * 3 + ["Go-http-client/1.1", "sqlmap/1.7"]
ROUTES = ["/api/orders/{n}", "/api/users/{n}/profile", "/login", "/static/app.js", "/api/search"]
DOMAINS = ["example.com"] * 20 + ["api.github.com"] * 10 + ["login.microsoftonline.com"] * 8 + ["pool.ntp.org"] * 5 \
    + ["cdn.jsdelivr.net"] * 3
DEPARTMENTS = {u: ["finance", "it", "ops", "sales"][i % 4] for i, u in enumerate(USERS[:80])}
OWNERS = {h: ["payments", "platform", "search"][i % 3] for i, h in enumerate(HOSTS)}


def make_events(n=6000, seed=11):
    rng = random.Random(seed)
    events = []
    for i in range(n):
        ts = START + timedelta(seconds=rng.randrange(7 * 86400 - 1))
        service = rng.choice(["api", "web", "auth", "billing", "dns", "vpn"])
        user = rng.choice(USERS)
        e = {"ts": ts, "service": service, "host": rng.choice(HOSTS), "user_id": user,
             "level": rng.choice(["info"] * 7 + ["warn"] * 2 + ["error"]), "status": 0,
             "src_ip": rng.choice(EXTERNAL) if rng.random() < 0.1 else rng.choice(INTERNAL),
             "attrs": {"duration_ms": int(rng.lognormvariate(5, 0.9)), "bytes": rng.randrange(200, 90000),
                       "country": rng.choice(COUNTRIES), "user_agent": rng.choice(AGENTS)}}
        if service in ("api", "web"):
            e["status"] = rng.choice([200] * 8 + [404, 500, 503])
            e["attrs"]["uri"] = rng.choice(ROUTES).format(n=rng.randrange(1, 5000))
            e["attrs"]["method"] = rng.choice(["GET"] * 6 + ["POST"] * 3 + ["PUT"])
            msg = f'{e["attrs"]["method"]} {e["attrs"]["uri"]} {e["status"]}'
        elif service in ("auth", "vpn"):
            outcome = "failure" if user in ATTACKERS or rng.random() < 0.25 else "success"
            e["attrs"]["outcome"] = outcome
            msg = f"login {outcome} user={user}"
        elif service == "dns":
            e["attrs"]["query"] = rng.choice(DOMAINS)
            msg = f'query {e["attrs"]["query"]}'
        else:
            msg = f"invoice {i} processed"
        e["msg"] = msg
        events.append(e)
    # a rare name queried by one host only
    for j in range(3):
        events.append({"ts": START + timedelta(hours=30 + j), "service": "dns", "host": "h07", "user_id": "u001",
                       "level": "warn", "status": 0, "src_ip": "10.0.7.7", "msg": "query x7f3k.badcdn.net",
                       "attrs": {"duration_ms": 3, "bytes": 90, "country": "US", "user_agent": "Mozilla/5.0",
                                 "query": "x7f3k.badcdn.net"}})
    return events


@pytest.fixture(scope="module")
def env():
    client = _client()
    if client is None:
        import os

        if os.getenv("LOGFORGE_REQUIRE_CLICKHOUSE") == "1":
            pytest.fail("ClickHouse is not reachable and LOGFORGE_REQUIRE_CLICKHOUSE=1")
        pytest.skip("ClickHouse is not reachable")
    sql = "\n".join(l for l in open(MIGRATION).read().splitlines() if not l.lstrip().startswith("--"))
    for statement in sql.split(";"):
        if "CREATE TABLE" in statement:
            client.command(statement)
    table = f"test_questions_{uuid.uuid4().hex[:8]}"
    client.command(f"CREATE TABLE {table} AS logs_raw_mt")
    events = make_events()
    columns = ["ts", "host", "service", "level", "msg", "trace_id", "span_id", "attrs", "status", "src_ip",
               "user_id", "ingested_at", "severity_num", "facility", "parser_version", "customer_id"]
    client.insert(table, [[e["ts"], e["host"], e["service"], e["level"], e["msg"], "", "", json.dumps(e["attrs"]),
                           e["status"], e["src_ip"], e["user_id"], e["ts"], 0, 16, "v1", TENANT] for e in events],
                  column_names=columns)
    rows = [[TENANT, "users", 1, u, {"department": d, "manager": "m"}] for u, d in DEPARTMENTS.items()]
    rows += [[TENANT, "assets", 1, h, {"owner": o, "criticality": "high"}] for h, o in OWNERS.items()]
    rows += [[TENANT, "blocklist", 1, ip, {}] for ip in BLOCKLIST]
    client.insert("lookup_rows_mt", rows, column_names=["tenant_id", "lookup", "version", "key", "values"])
    lookups = {"users": lp.LookupMeta("users", 1, ["user_id", "department", "manager"], "user_id"),
               "assets": lp.LookupMeta("assets", 1, ["host", "owner", "criticality"], "host"),
               "blocklist": lp.LookupMeta("blocklist", 1, ["value"], "value")}
    yield client, table, events, lookups
    client.command(f"DROP TABLE IF EXISTS {table}")
    client.command("ALTER TABLE lookup_rows_mt DELETE WHERE tenant_id = %(t)s", {"t": TENANT})


def hour(ts):
    return ts.replace(minute=0, second=0, microsecond=0)


def bucket(ts, hours):
    return ts.replace(hour=ts.hour // hours * hours, minute=0, second=0, microsecond=0)


def pct(values, p):
    return statistics.quantiles(sorted(values), n=100, method="inclusive")[p - 1]


def failures(events):
    return [e for e in events if e["attrs"].get("outcome") == "failure"]


def successes(events):
    return [e for e in events if e["attrs"].get("outcome") == "success"]


def route(uri):
    return re.sub(r"[0-9]+", ":id", uri)


def http(events):
    return [e for e in events if e["service"] in ("api", "web")]


def ordered(counter, key=lambda kv: (-kv[1], kv[0])):
    return sorted(counter.items(), key=key)


# Each check returns the expected answer in the same shape as `simplify(rows)`.
CHECKS = {
    "q01": lambda ev: [(t, ip, n) for (t, ip), n in ordered(Counter((hour(e["ts"]), e["src_ip"]) for e in failures(ev)),
                                                          key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))[:10]],
    "q02": lambda ev: ordered(Counter(e["service"] for e in ev if e["level"] == "error")),
    "q03": lambda ev: sorted(((s, total, err, round(100 * err / total, 2))
                              for s, total, err in ((s, sum(1 for e in ev if e["service"] == s),
                                                     sum(1 for e in ev if e["service"] == s and e["level"] == "error"))
                                                    for s in {e["service"] for e in ev})),
                             key=lambda t: (-t[3], t[0])),
    "q06": lambda ev: sorted(Counter((e["ts"].replace(hour=0, minute=0, second=0, microsecond=0),
                                      "5xx" if e["status"] >= 500 else "4xx" if e["status"] >= 400 else "2xx")
                                     for e in http(ev)).items()),
    "q07": lambda ev: [(u, n, 0) for u, n in ordered(Counter(e["user_id"] for e in failures(ev)))
                       if n > 3 and u not in {e["user_id"] for e in successes(ev)}],
    "q08": lambda ev: sorted(((c, len({e["user_id"] for e in successes(ev) if e["attrs"]["country"] == c}))
                              for c in {e["attrs"]["country"] for e in successes(ev)}), key=lambda t: (-t[1], t[0])),
    "q09": lambda ev: [sum(1 for u in {e["user_id"] for e in successes(ev)}
                           if len({e["attrs"]["country"] for e in successes(ev) if e["user_id"] == u}) > 2)],
    "q12": lambda ev: ordered(Counter(e["src_ip"] for e in failures(ev) if not e["src_ip"].startswith("10."))),
    "q13": lambda ev: sorted((ip, sum(1 for e in ev if e["src_ip"] == ip), len({e["user_id"] for e in ev
                                                                               if e["src_ip"] == ip}))
                             for ip in BLOCKLIST),
    "q14": lambda ev: sorted(Counter(DEPARTMENTS.get(e["user_id"]) for e in ev).items(), key=lambda kv: str(kv[0])),
    "q15": lambda ev: ordered(Counter(OWNERS[e["host"]] for e in ev if e["level"] == "error")),
    "q16": lambda ev: sorted(Counter((e["ts"].replace(hour=0, minute=0, second=0, microsecond=0), e["service"])
                                     for e in ev).items()),
    "q17": lambda ev: ordered(Counter(e["ts"].hour for e in ev))[:1],
    "q18": lambda ev: [(u, float(b)) for u, b in ordered(Counter({u: sum(e["attrs"]["bytes"] for e in ev
                                                                         if e["user_id"] == u)
                                                                   for u in {e["user_id"] for e in ev}}))[:10]],
    "q20": lambda ev: sorted((h, *max((e["ts"], e["service"]) for e in ev if e["host"] == h)) for h in HOSTS),
    "q21": lambda ev: sorted((u, min(e["ts"] for e in ev if e["user_id"] == u),
                              max(e["ts"] for e in ev if e["user_id"] == u),
                              sum(1 for e in ev if e["user_id"] == u)) for u in {e["user_id"] for e in ev})[:20],
    "q22": lambda ev: sorted(Counter(e["service"] for e in ev if e["attrs"]["duration_ms"] > 3 * statistics.fmean(
        x["attrs"]["duration_ms"] for x in ev if x["service"] == e["service"])).items()),
    "q23": lambda ev: ordered(Counter(route(e["attrs"]["uri"]) for e in ev if e["status"] >= 500)),
    "q25": lambda ev: [sum(1 for q in {e["attrs"]["query"] for e in ev if e["service"] == "dns"}
                           if len({e["host"] for e in ev if e["service"] == "dns" and e["attrs"]["query"] == q}) == 1)],
    "q27": lambda ev: sorted((b, len({e["src_ip"] for e in ev if bucket(e["ts"], 6) == b}))
                             for b in {bucket(e["ts"], 6) for e in ev}),
    "q28": lambda ev: sorted(Counter(e["attrs"]["duration_ms"] // 250 * 250 for e in ev).items()),
    "q29": lambda ev: [(u, h, n) for (u, h), n in sorted(Counter((e["user_id"], e["host"]) for e in failures(ev)).items(),
                                                        key=lambda kv: (-kv[1], kv[0])) if n >= 5],
}


def simplify(question_id, rows):
    """The answer's rows as tuples, in the shape CHECKS uses."""
    if question_id == "q27":
        return [(r["_time"], r["ips"]) for r in rows if r["ips"]]
    if question_id in ("q06", "q16"):
        return sorted((r["_time"], r[k], r["count"]) for r in rows for k in r if k not in ("_time", "count"))
    if question_id in ("q14",):
        return sorted(((r["department"], r["events"]) for r in rows), key=lambda t: str(t[0]))
    if question_id in ("q22", "q28"):
        return sorted(tuple(int(v) if isinstance(v, float) and v.is_integer() else v for v in r.values()) for r in rows)
    return [tuple(r.values()) for r in rows]


def expected(question_id, events):
    value = CHECKS[question_id](events)
    if question_id in ("q06", "q16"):
        return sorted((t, k, n) for (t, k), n in value)
    if question_id in ("q14", "q22", "q28"):
        return [tuple(kv) for kv in value]
    if question_id in ("q09", "q25"):
        return [(value[0],)]
    return [tuple(v) for v in value]


def run(env, query):
    client, table, _, lookups = env
    compiled = lp.compile_pipeline(query, customer_id=TENANT, start=START, end=END, table=table, lookups=lookups)
    return lp.execute(client, compiled)["rows"]


def test_there_are_30_questions():
    assert len(QUESTIONS) == 30 and len({q["id"] for q in QUESTIONS}) == 30


@pytest.mark.parametrize("q", QUESTIONS, ids=[q["id"] for q in QUESTIONS])
def test_each_question_is_answered_by_one_query(env, q):
    events = env[2]
    rows = run(env, q["query"])
    qid = q["id"]
    if qid in CHECKS:
        assert simplify(qid, rows) == expected(qid, events), q["question"]
    elif qid == "q04":
        for r in rows:
            values = [e["attrs"]["duration_ms"] for e in events if e["service"] == r["service"]]
            assert r["p95"] == pytest.approx(pct(values, 95), rel=0.02)
            assert r["p99"] == pytest.approx(pct(values, 99), rel=0.02)
        assert len(rows) == 6
    elif qid == "q05":
        by = defaultdict(list)
        for e in events:
            if "uri" in e["attrs"]:
                by[route(e["attrs"]["uri"])].append(e["attrs"]["duration_ms"])
        want = sorted(((r, len(v), pct(v, 95)) for r, v in by.items() if len(v) >= 50), key=lambda t: -t[2])[:5]
        assert [r["route"] for r in rows] == [w[0] for w in want]
        assert [r["requests"] for r in rows] == [w[1] for w in want]
    elif qid in ("q10", "q11", "q24", "q26"):
        field = {"q10": "host", "q11": "attrs.user_agent", "q24": "attrs.query", "q26": "status"}[qid]
        pool = {"q10": [e for e in events if e["level"] == "error"], "q11": events,
                "q24": [e for e in events if e["service"] == "dns"], "q26": http(events)}[qid]
        get = (lambda e: e["host"]) if field == "host" else (lambda e: e["status"]) if field == "status" else \
            (lambda e, k=field.split(".")[1]: e["attrs"][k])
        counts = Counter(get(e) for e in pool)
        limit = {"q10": 5, "q11": 3, "q24": 5, "q26": 10}[qid]
        want = sorted(counts.items(), key=lambda kv: (kv[1], str(kv[0])) if qid == "q11" else (-kv[1], str(kv[0])))
        assert [(r[field], r["count"]) for r in rows] == [(k, n) for k, n in want[:limit]]
        assert rows[0]["percent"] == pytest.approx(100 * want[0][1] / len(pool), abs=1e-6)
    elif qid == "q19":
        by = defaultdict(list)
        for e in events:
            if "method" in e["attrs"]:
                by[e["attrs"]["method"]].append(e["attrs"]["bytes"])
        assert {r["attrs.method"]: (pytest.approx(r["avg_bytes"]), r["requests"]) for r in rows} == \
            {m: (pytest.approx(statistics.fmean(v)), len(v)) for m, v in by.items()}
    elif qid == "q30":
        counts = Counter(e["service"] for e in events if e["level"] == "error")
        total = sum(counts.values())
        want = sorted(((s, n, total, round(100 * n / total, 2)) for s, n in counts.items()), key=lambda t: (-t[3], t[0]))
        assert [tuple(r.values()) for r in rows] == want
    else:
        pytest.fail(f"no check for {qid}")
