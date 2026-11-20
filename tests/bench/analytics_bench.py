"""
Phase 6 acceptance benchmark: the 30 analyst questions
(tests/eval/analytics/questions.yml), timed through the API at a dataset
size (default 100 M rows) seeded directly in ClickHouse.

    BENCH_EMAIL=... BENCH_PASSWORD=... \\
      python tests/bench/analytics_bench.py --rows 100000000 \\
        --out docs/benchmarks/<date>-analytics.json

Each question runs `--repeats` times (default 20) over the last 7 days. The
first run is reported separately (cold caches); p50 / p95 are over the
rest. The response's estimated rows read and whether the hourly counts
were used are recorded too.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from perf_bench import clickhouse, login, summarize  # noqa: E402

QUESTIONS = Path(__file__).resolve().parents[1] / "eval" / "analytics" / "questions.yml"
HOSTS = [f"h{i:02d}" for i in range(20)]
USERS = [f"u{i:03d}" for i in range(100)]


def load_questions(path: Path = QUESTIONS) -> List[Dict[str, Any]]:
    return yaml.safe_load(path.read_text())["questions"]


def seed_sql(tenant_id: str, rows: int, days: int = 7, offset: int = 0) -> str:
    """INSERT ... SELECT of `rows` compact auth / HTTP / DNS events over `days`
    (the shape of tests/test_analyst_questions_live.py)."""
    tenant = tenant_id.replace("'", "")
    span_s = days * 86400
    return f"""
INSERT INTO logs_raw_mt (ts, host, service, level, msg, trace_id, attrs, status, src_ip, user_id, customer_id)
SELECT ts, host, service, level, msg, trace_id, attrs, status, src_ip, user_id, '{tenant}'
FROM (
  SELECT
    number + {int(offset)} AS n,
    toDateTime64(now() - toIntervalSecond(cityHash64(n, 1) % {span_s}), 3) AS ts,
    arrayElement(['api','web','auth','billing','dns','vpn'], (cityHash64(n, 2) % 6) + 1) AS service,
    concat('h', leftPad(toString(cityHash64(n, 3) % 20), 2, '0')) AS host,
    arrayElement(['info','info','info','info','info','info','info','warn','warn','error'],
                 (cityHash64(n, 4) % 10) + 1) AS level,
    concat('u', leftPad(toString(cityHash64(n, 5) % 100), 3, '0')) AS user_id,
    if(cityHash64(n, 6) % 10 = 0, concat('203.0.113.', toString(cityHash64(n, 7) % 20)),
       concat('10.0.', toString(cityHash64(n, 7) % 20), '.', toString(cityHash64(n, 8) % 10))) AS src_ip,
    if(service IN ('api', 'web'), arrayElement([200,200,200,200,200,200,200,200,404,500,503],
                                               (cityHash64(n, 9) % 11) + 1), 0) AS status,
    if(service IN ('auth', 'vpn'),
       if(user_id >= 'u090' OR cityHash64(n, 10) % 4 = 0, 'failure', 'success'), '') AS outcome,
    arrayElement(['GET','GET','GET','GET','GET','GET','POST','POST','POST','PUT'], (cityHash64(n, 11) % 10) + 1)
      AS method,
    replaceOne(arrayElement(['/api/orders/N','/api/users/N/profile','/login','/static/app.js','/api/search'],
                            (cityHash64(n, 12) % 5) + 1), 'N', toString(cityHash64(n, 13) % 500)) AS uri,
    arrayElement(['example.com','example.com','example.com','api.github.com','api.github.com',
                  'login.microsoftonline.com','pool.ntp.org','cdn.jsdelivr.net'], (cityHash64(n, 14) % 8) + 1) AS query,
    toUInt32(exp(5 + 0.9 * (((cityHash64(n, 15) % 10000) / 10000.0) * 2 - 1) * 2)) AS duration_ms,
    multiIf(service IN ('api', 'web'), concat(method, ' ', uri, ' ', toString(status)),
            service IN ('auth', 'vpn'), concat('login ', outcome, ' user=', user_id),
            service = 'dns', concat('query ', query), 'invoice processed') AS msg,
    if(cityHash64(n, 16) % 20 = 0, lower(hex(cityHash64(n, 17))), '') AS trace_id,
    concat('{{"duration_ms":', toString(duration_ms), ',"bytes":', toString(200 + (cityHash64(n, 18) % 900) * 100),
           ',"country":"', arrayElement(['US','DE','IN','BR','GB','CN'], (cityHash64(n, 19) % 6) + 1),
           '","user_agent":"', arrayElement(['Mozilla/5.0','Mozilla/5.0','Mozilla/5.0','curl/8.4',
                                             'python-requests/2.31','sqlmap/1.7'], (cityHash64(n, 20) % 6) + 1), '"',
           if(outcome != '', concat(',"outcome":"', outcome, '"'), ''),
           if(service IN ('api', 'web'), concat(',"method":"', method, '","uri":"', uri, '"'), ''),
           if(service = 'dns', concat(',"query":"', query, '"'), ''), '}}') AS attrs
  FROM numbers({int(rows)})
)
"""


def lookups(client) -> None:
    """The lookup tables the questions use, uploaded through the API."""
    users = "user_id,department,manager\n" + "".join(
        f"{u},{['finance', 'it', 'ops', 'sales'][i % 4]},m{i % 7}\n" for i, u in enumerate(USERS[:80]))
    assets = "host,owner,criticality\n" + "".join(
        f"{h},{['payments', 'platform', 'search'][i % 3]},{'high' if i % 4 == 0 else 'normal'}\n"
        for i, h in enumerate(HOSTS))
    client._call("PUT", "/v1/query/lookups/users", body={"csv": users})
    client._call("PUT", "/v1/query/lookups/assets", body={"csv": assets})
    client._call("PUT", "/v1/query/lookups/blocklist", body={"values": ["203.0.113.0", "203.0.113.1", "203.0.113.2"]})


def run_questions(client, questions: List[Dict[str, Any]], repeats: int = 20,
                  clock=time.perf_counter) -> Dict[str, Dict[str, Any]]:
    results = {}
    for q in questions:
        timings, info, rows = [], {}, None
        for _ in range(repeats):
            start = clock()
            response = client.post("/v1/query/logql", {"query": q["query"], "since": "7d"})
            timings.append(clock() - start)
            info = response.get("query_info") or {}
            rows = response.get("total_count")
        warm = timings[1:] if len(timings) > 1 else timings
        results[q["id"]] = {"question": q["question"], "first_ms": round(timings[0] * 1000, 3), **summarize(warm),
                            "rows_returned": rows, "estimated_rows_read": info.get("estimated_rows"),
                            "hourly_counts": bool(info.get("hourly_counts"))}
    return results


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 6 analyst-question benchmark")
    parser.add_argument("--api", default=os.getenv("LOGFORGE_API_URL", "http://localhost:7080"))
    parser.add_argument("--rows", type=int, default=100_000_000)
    parser.add_argument("--batch", type=int, default=10_000_000)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    email, password = os.getenv("BENCH_EMAIL"), os.getenv("BENCH_PASSWORD")
    if not email or not password:
        print("Set BENCH_EMAIL and BENCH_PASSWORD (a user whose tenant may hold benchmark data)", file=sys.stderr)
        return 2
    client = login(args.api, email, password)
    tenant = client.tenant_id.replace("'", "")
    have = int(clickhouse(f"SELECT count() FROM logs_raw_mt WHERE customer_id = '{tenant}' "
                          f"AND ts >= now() - INTERVAL 7 DAY").strip() or 0)
    seeded = 0
    while have + seeded < args.rows:
        n = min(args.batch, args.rows - have - seeded)
        began = time.time()
        clickhouse(seed_sql(tenant, n, offset=have + seeded))
        seeded += n
        print(f"seeded {have + seeded:,} rows ({time.time() - began:.0f} s for {n:,})", flush=True)
    lookups(client)
    total = int(clickhouse(f"SELECT count() FROM logs_raw_mt WHERE customer_id = '{tenant}' "
                           f"AND ts >= now() - INTERVAL 7 DAY").strip())
    results = run_questions(client, load_questions(), repeats=args.repeats)
    report = {"rows_in_window": total, "repeats": args.repeats, "window": "7d", "questions": results}
    for qid, r in results.items():
        print(f"{qid} p50 {r['p50_ms']:8.1f} ms  p95 {r['p95_ms']:8.1f} ms  first {r['first_ms']:8.1f} ms  "
              f"read {r['estimated_rows_read']}  {'(hourly counts) ' if r['hourly_counts'] else ''}{r['question']}")
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
