"""
Logforge performance benchmarks.

Measures, against a running stack:

* **ingest throughput**: events/s accepted by POST /v1/ingest/logs/batch;
* **ingest to searchable**: seconds until a just-ingested log is returned by
  GET /v1/logs;
* **query latency**: p50/p95 for a fixed set of searches and aggregations,
  over a dataset seeded directly into ClickHouse at a chosen size.

The benchmark runs in its own tenant so millions of synthetic rows never
reach real or demo data. Create one with the bootstrap script:

    TENANT_NAME=Bench DEMO_USER_EMAIL=bench@bench.example \\
      DEMO_USER_PASSWORD='Bench-Pass-123!' python scripts/bootstrap_demo.py

then:

    BENCH_EMAIL=bench@bench.example BENCH_PASSWORD='Bench-Pass-123!' \\
      python tests/bench/perf_bench.py --rows 10000000 --out docs/benchmarks/results.json

Seeding uses ClickHouse's HTTP interface (CLICKHOUSE_URL, default
http://localhost:8124 with the compose credentials).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def percentile(values: List[float], p: float) -> float:
    """Percentile with linear interpolation between closest ranks."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (p / 100) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def summarize(seconds: List[float]) -> Dict[str, float]:
    ms = [s * 1000 for s in seconds]
    return {
        "count": len(ms),
        "p50_ms": round(percentile(ms, 50), 3),
        "p95_ms": round(percentile(ms, 95), 3),
        "max_ms": round(max(ms), 3),
        "mean_ms": round(statistics.fmean(ms), 3),
    }


# ---------------------------------------------------------------------------
# Measurements (client: object with .get(path, params) and .post(path, json))
# ---------------------------------------------------------------------------


def run_query_bench(client, queries: List[Dict[str, Any]], repeats: int = 20,
                    clock: Callable[[], float] = time.perf_counter) -> Dict[str, Dict[str, float]]:
    results = {}
    for query in queries:
        timings = []
        for repeat in range(repeats):
            body = query.get("body")
            if query.get("vary_window") and body and body.get("end_time"):
                # Result-cached endpoints key on the request body: shift the
                # window end by 1 ms per repeat so each run is a real query.
                end = datetime.fromisoformat(body["end_time"]) + timedelta(milliseconds=repeat)
                body = dict(body, end_time=end.isoformat())
            start = clock()
            if query.get("method", "GET") == "GET":
                client.get(query["path"], query.get("params"))
            else:
                client.post(query["path"], body)
            timings.append(clock() - start)
        results[query["name"]] = summarize(timings)
    return results


def _batch(size: int, run_id: str) -> List[Dict[str, Any]]:
    return [{"service": f"bench-ingest-{i % 8}", "level": "info" if i % 10 else "error",
             "msg": f"bench {run_id} event {i}", "attrs": {"request_id": f"{run_id}-{i}"}}
            for i in range(size)]


def run_ingest_bench(client, batch_size: int = 1000, batches: int = 50,
                     clock: Callable[[], float] = time.perf_counter) -> Dict[str, Any]:
    run_id = uuid.uuid4().hex[:8]
    payloads = [_batch(batch_size, f"{run_id}-{b}") for b in range(batches)]
    start = clock()
    for payload in payloads:
        client.post("/v1/ingest/logs/batch", payload)
    seconds = clock() - start
    events = batch_size * batches
    return {"events": events, "seconds": round(seconds, 3),
            "events_per_second": round(events / seconds, 1) if seconds else 0.0,
            "batch_size": batch_size}


def measure_ingest_to_searchable(client, clock: Callable[[], float] = time.perf_counter,
                                 poll_interval: float = 0.25, timeout: float = 60.0,
                                 sleep: Callable[[float], None] = time.sleep) -> float:
    service = f"bench-latency-{uuid.uuid4().hex[:10]}"
    start = clock()
    client.post("/v1/ingest/logs/batch", [{"service": service, "level": "info", "msg": "latency probe"}])
    while clock() - start < timeout:
        page = client.get("/v1/logs", {"service": service, "limit": 1})
        if page.get("logs"):
            return clock() - start
        sleep(poll_interval)
    raise TimeoutError(f"probe log not searchable after {timeout}s")


# ---------------------------------------------------------------------------
# Dataset seeding
# ---------------------------------------------------------------------------


def seed_sql(tenant_id: str, rows: int, days: int = 7) -> str:
    """INSERT ... SELECT generating `rows` realistic-shaped logs over `days`."""
    tenant = tenant_id.replace("'", "")
    span = days * 86400
    return f"""
INSERT INTO logs_raw_mt (ts, host, service, level, msg, trace_id, span_id, attrs, status, src_ip, user_id, customer_id)
SELECT
    now64(3) - toIntervalMillisecond(rand64(1) % ({span} * 1000)) AS ts,
    concat('host-', toString(number % 40)) AS host,
    arrayElement(['checkout','auth','inventory','api-gateway','payments','search','email','billing'], (number % 8) + 1) AS service,
    arrayElement(['info','info','info','info','info','info','warn','warn','error','debug'], (number % 10) + 1) AS level,
    concat(arrayElement(['request completed','user login','cache miss','payment authorized','order placed',
                         'upstream timeout','connection reset','query slow'], (rand(2) % 8) + 1),
           ' id=', toString(number)) AS msg,
    lower(hex(rand64(3))) AS trace_id,
    lower(hex(rand(4))) AS span_id,
    concat('{{"region":"', arrayElement(['us-east-1','eu-west-1','ap-south-1'], (number % 3) + 1),
           '","latency_ms":', toString(rand(5) % 2000), '}}') AS attrs,
    arrayElement([200,200,200,200,201,304,400,404,500,503], (number % 10) + 1) AS status,
    concat('10.', toString(rand(6) % 4), '.', toString(rand(7) % 255), '.', toString(rand(8) % 255)) AS src_ip,
    concat('user-', toString(rand(9) % 5000)) AS user_id,
    '{tenant}' AS customer_id
FROM numbers({rows})
"""


def clickhouse(sql: str, url: Optional[str] = None) -> str:
    base = url or os.getenv("CLICKHOUSE_URL", "http://localhost:8124")
    user = os.getenv("CLICKHOUSE_USER", "logforge")
    password = os.getenv("CLICKHOUSE_PASSWORD", "logforge123")
    query = urllib.parse.urlencode({"user": user, "password": password, "database": "logforge"})
    req = urllib.request.Request(f"{base}/?{query}", data=sql.encode(), method="POST")
    with urllib.request.urlopen(req, timeout=3600) as resp:
        return resp.read().decode()


# ---------------------------------------------------------------------------
# HTTP client and CLI
# ---------------------------------------------------------------------------


class ApiClient:
    def __init__(self, base: str, token: str, tenant_id: str):
        self.base, self.token, self.tenant_id = base.rstrip("/"), token, tenant_id

    def _call(self, method: str, path: str, params=None, body=None) -> Dict[str, Any]:
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {self.token}", "X-Customer-ID": self.tenant_id,
            "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}

    def get(self, path, params=None):
        return self._call("GET", path, params=params)

    def post(self, path, json=None):  # noqa: A002 - mirrors the fake client in tests
        return self._call("POST", path, body=json)


def login(base: str, email: str, password: str) -> ApiClient:
    req = urllib.request.Request(f"{base}/v1/auth/login", method="POST",
                                 data=json.dumps({"email": email, "password": password}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        token = json.loads(resp.read())["access_token"]
    import base64

    payload = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
    return ApiClient(base, token, payload["tenant_id"])


def query_set(window_hours: int = 24) -> List[Dict[str, Any]]:
    """The fixed queries measured at every dataset size."""
    end = datetime.now(timezone.utc)
    start = end.timestamp() - window_hours * 3600
    iso = lambda t: datetime.fromtimestamp(t, timezone.utc).isoformat()  # noqa: E731
    window = {"start_time": iso(start), "end_time": end.isoformat()}
    return [
        {"name": "latest 100 logs (1h)", "method": "GET", "path": "/v1/logs", "params": {"limit": 100}},
        {"name": "service filter, 100 logs (24h)", "method": "GET", "path": "/v1/logs",
         "params": {"service": "payments", "limit": 100, **window}},
        {"name": "LogforgeQL errors by service (24h)", "method": "POST", "path": "/v1/query/logql",
         "body": {"query": "where level = \"error\" | stats count() by service", "since": f"{window_hours}h"}},
        {"name": "LogforgeQL full-text search (24h)", "method": "POST", "path": "/v1/query/logql",
         "body": {"query": "timeout | limit 50", "since": f"{window_hours}h"}},
        {"name": "count by level (24h)", "method": "POST", "path": "/v1/query/advanced", "vary_window": True,
         "body": {**window, "aggregations": [{"type": "count", "field": "*", "alias": "n"}],
                  "group_by": ["level"]}},
    ]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Logforge performance benchmarks")
    parser.add_argument("--api", default=os.getenv("LOGFORGE_API_URL", "http://localhost:7080"))
    parser.add_argument("--rows", type=int, nargs="*", default=[1_000_000],
                        help="dataset sizes to measure queries at (rows seeded cumulatively)")
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--ingest-batches", type=int, default=50)
    parser.add_argument("--out", help="write results JSON here")
    args = parser.parse_args(argv)

    email = os.getenv("BENCH_EMAIL")
    password = os.getenv("BENCH_PASSWORD")
    if not email or not password:
        print("Set BENCH_EMAIL and BENCH_PASSWORD (a user of a dedicated benchmark tenant).", file=sys.stderr)
        return 2
    client = login(args.api, email, password)
    if client.tenant_id in ("platform", ""):
        print("The benchmark user must belong to a tenant.", file=sys.stderr)
        return 2

    results: Dict[str, Any] = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": {"host": platform.platform(), "python": platform.python_version(),
                        "cpus": os.cpu_count()},
        "ingest": run_ingest_bench(client, batch_size=1000, batches=args.ingest_batches),
        "ingest_to_searchable_s": round(measure_ingest_to_searchable(client), 3),
        "queries": {},
    }
    print(f"ingest: {results['ingest']['events_per_second']} events/s; "
          f"ingest->searchable: {results['ingest_to_searchable_s']} s")

    seeded = 0
    for target in sorted(args.rows):
        if target > seeded:
            clickhouse(seed_sql(client.tenant_id, target - seeded))
            seeded = target
        results["queries"][str(target)] = run_query_bench(client, query_set(), repeats=args.repeats)
        print(f"\n{target:,} rows")
        for name, s in results["queries"][str(target)].items():
            print(f"  {name:40s} p50 {s['p50_ms']:8.1f} ms   p95 {s['p95_ms']:8.1f} ms")

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w") as fh:
            json.dump(results, fh, indent=2)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
