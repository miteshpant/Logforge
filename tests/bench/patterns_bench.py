#!/usr/bin/env python3
"""
Log pattern clustering benchmark (Phase 11): 1 M log lines reduced to
templates by `| patterns`, against the target of under 30 s.

Seeds a fresh tenant in logs_raw_mt with 1 M lines from 80 message shapes
(web requests, auth, database, queues, kernel, application errors), each
with variable parts (ids, addresses, durations, paths, users), plus a
200 k-line baseline over the days before; then runs pattern_query.run on the
last hour, as `| patterns` does, and reports the time, the templates found
and how many the 80 shapes became.

    LOGFORGE_TEST_CLICKHOUSE=localhost:8124 python tests/bench/patterns_bench.py [--lines 1000000]
"""

import argparse
import json
import platform
import random
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "apps" / "api"), str(REPO / "tests")]

COLUMNS = ["ts", "host", "service", "level", "msg", "trace_id", "span_id", "attrs", "status", "src_ip", "user_id",
           "ingested_at", "severity_num", "facility", "parser_version", "customer_id"]


def shapes(r: random.Random):
    ip = lambda: f"{r.randint(1, 223)}.{r.randint(0, 255)}.{r.randint(0, 255)}.{r.randint(1, 254)}"  # noqa: E731
    uid = lambda: uuid.UUID(int=r.getrandbits(128)).hex  # noqa: E731
    user = lambda: f"user{r.randint(1, 5000)}"  # noqa: E731
    path = lambda: r.choice(["/api/orders", "/api/users", "/api/carts", "/api/payments", "/static/app.js"])  # noqa: E731
    base = [
        ("nginx", lambda: f'{ip()} - - "GET {path()}/{r.randint(1, 10**6)} HTTP/1.1" {r.choice([200, 304])} {r.randint(100, 90000)}'),
        ("nginx", lambda: f'{ip()} - - "POST {path()} HTTP/1.1" {r.choice([201, 400, 500])} {r.randint(10, 900)}'),
        ("sshd", lambda: f"Failed password for {user()} from {ip()} port {r.randint(1024, 65535)} ssh2"),
        ("sshd", lambda: f"Accepted publickey for {user()} from {ip()} port {r.randint(1024, 65535)} ssh2"),
        ("sshd", lambda: f"Disconnected from user {user()} {ip()} port {r.randint(1024, 65535)}"),
        ("postgres", lambda: f"duration: {r.random() * 900:.3f} ms  statement: SELECT * FROM orders WHERE id = {r.randint(1, 10**7)}"),
        ("postgres", lambda: f"checkpoint complete: wrote {r.randint(1, 9000)} buffers ({r.random() * 10:.1f}%)"),
        ("kafka", lambda: f"Committed offset {r.randint(1, 10**9)} for partition orders-{r.randint(0, 31)}"),
        ("kafka", lambda: f"Rebalance triggered for group consumer-{r.randint(1, 20)}, generation {r.randint(1, 500)}"),
        ("kernel", lambda: f"TCP: request_sock_TCP: Possible SYN flooding on port {r.randint(1, 65535)}. Sending cookies."),
        ("checkout", lambda: f"order {uid()} paid by {user()} in {r.randint(10, 3000)}ms"),
        ("checkout", lambda: f"payment provider timeout after {r.randint(1, 30)}s for order {uid()}"),
        ("auth", lambda: f"token issued for {user()} expires_in={r.randint(60, 86400)}"),
        ("auth", lambda: f"mfa challenge sent to {user()} via {r.choice(['sms', 'push', 'totp'])}"),
        ("worker", lambda: f"job {uid()} finished in {r.randint(1, 600)}s with {r.randint(0, 5)} retries"),
        ("cache", lambda: f"evicted {r.randint(1, 10000)} keys from shard {r.randint(0, 63)} in {r.randint(1, 900)}ms"),
    ]
    # 64 more application messages with an id and a number each: "<component> <event> <id> <n>"
    for c in range(16):
        for e in range(4):
            verb = ["started", "completed", "retried", "rejected"][e]
            base.append((f"svc-{c}", lambda c=c, verb=verb: f"component{c} task {verb} id={r.randint(1, 10**6)} "
                                                           f"took={r.randint(1, 999)}ms"))
    return base


def seed(client, tenant: str, lines: int, start: datetime, end: datetime, r: random.Random) -> None:
    pool = shapes(r)
    weights = [r.randint(1, 50) for _ in pool]
    span = (end - start).total_seconds()
    batch = []
    for i in range(lines):
        service, make = r.choices(pool, weights)[0]
        at = start + timedelta(seconds=span * i / lines)
        batch.append([at, "host-1", service, "info", make(), "", "", "{}", 0, "", "", at, 0, 16, "v1", tenant])
        if len(batch) == 100_000:
            client.insert("logs_raw_mt", batch, column_names=COLUMNS)
            batch = []
    if batch:
        client.insert("logs_raw_mt", batch, column_names=COLUMNS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--lines", type=int, default=1_000_000)
    parser.add_argument("--out", default=str(REPO / "docs" / "benchmarks" / "2026-11-20-patterns.json"))
    args = parser.parse_args()
    from test_logql_pipeline_live import _client

    import pattern_query

    client = _client()
    if client is None:
        raise SystemExit("ClickHouse is not reachable (set LOGFORGE_TEST_CLICKHOUSE)")
    r = random.Random(11)
    tenant = f"patterns-bench-{uuid.uuid4().hex[:8]}"
    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(hours=1)
    began = time.perf_counter()
    seed(client, tenant, 200_000, start - timedelta(days=3), start - timedelta(hours=1), r)
    seed(client, tenant, args.lines, start, end, r)
    seeded = time.perf_counter() - began
    pattern_query.MAX_LINES = max(pattern_query.MAX_LINES, args.lines)
    began = time.perf_counter()
    result = pattern_query.run(client, "*", "all", tenant, start, end)
    took = time.perf_counter() - began
    report = {"lines": result["patterns"]["lines"], "baseline_lines": result["patterns"]["baseline_lines"],
              "message_shapes": len(shapes(random.Random(0))), "templates": result["patterns"]["templates"],
              "new_templates": sum(row["new"] for row in result["rows"]), "seconds": round(took, 2),
              "target_seconds": 30, "met": took < 30, "seed_seconds": round(seeded, 1),
              "machine": f"{platform.machine()}, {platform.python_implementation()} {platform.python_version()}"}
    print(json.dumps(report, indent=2))
    print("largest templates:")
    for row in result["rows"][:8]:
        print(f"  {row['count']:>8}  {row['pattern']}")
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["met"] else 1


if __name__ == "__main__":
    sys.exit(main())
