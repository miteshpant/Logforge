"""
Search-time extraction benchmark (Phase 5 acceptance: search-time
extraction on 10 M rows completes within 2x the cost of the same query on
an ingest-time field).

Each pair counts the same value two ways over the benchmark tenant's whole
dataset (last 7d): from the stored attrs field, and by extracting it at
query time from the raw text (rex, parse) or the JSON (json). Both go
through POST /v1/query/logql, so they pay the same API overhead; each run
gets a slightly different window so the result cache can't serve it.

    BENCH_EMAIL=bench@bench.example BENCH_PASSWORD='Bench-Pass-123!' \\
      python tests/bench/extraction_bench.py --rows 10000000 --out docs/benchmarks/<date>-extraction.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

REGION = "eu-west-1"
QUERY_PAIRS = [
    ("rex", f'| where attrs.region = "{REGION}" | stats count()',
     f'| rex field=attrs "\\"region\\":\\"(?<region>[^\\"]+)\\"" | where region = "{REGION}" | stats count()'),
    ("parse", f'| where attrs.region = "{REGION}" | stats count()',
     f'| parse field=attrs "\\"region\\":\\"*\\"" as region | where region = "{REGION}" | stats count()'),
    ("json", f'| where attrs.region = "{REGION}" | stats count()',
     f'| json field=attrs "region" as reg | where reg = "{REGION}" | stats count()'),
]


def verdict(results: Dict[str, Dict[str, float]], limit: float = 2.0) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name, r in results.items():
        ratio = round(r["search_p50_ms"] / r["ingest_p50_ms"], 2) if r["ingest_p50_ms"] else 0.0
        out[name] = {"ratio": ratio, "pass": ratio <= limit}
    out["all_pass"] = all(v["pass"] for v in out.values() if isinstance(v, dict))
    return out


def _rows(tenant_id: str) -> int:
    from perf_bench import clickhouse

    if not all(c.isalnum() or c == "-" for c in tenant_id):
        raise ValueError("unexpected tenant id")
    return int(clickhouse(f"SELECT count() FROM logs_raw_mt WHERE customer_id = '{tenant_id}' "
                          "AND ts >= now() - INTERVAL 7 DAY").strip() or 0)


def _run(client, query: str, shift_s: int, end: Optional[datetime] = None) -> Dict[str, Any]:
    end = end or datetime.now(timezone.utc) - timedelta(seconds=shift_s)
    body = {"query": query, "start_time": (end - timedelta(days=7) + timedelta(minutes=1)).isoformat(),
            "end_time": end.isoformat()}
    start = time.perf_counter()
    result = client._call("POST", "/v1/query/logql", body=body)
    return {"wall_ms": (time.perf_counter() - start) * 1000, "server_ms": result.get("execution_time_ms"),
            "count": (result.get("aggregations") or {}).get("count_all")}


def measure(client, repeats: int = 7) -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    shift = 0
    for name, ingest_time, search_time in QUERY_PAIRS:
        runs: Dict[str, List[Dict[str, Any]]] = {"ingest": [], "search": []}
        for i in range(repeats + 1):  # the first round warms up
            for side, query in (("ingest", ingest_time), ("search", search_time)):
                shift += 1
                run = _run(client, query, shift)
                if i:
                    runs[side].append(run)
        # The timed runs use shifted windows (cache-busting); check the answers over one identical window.
        same_end = datetime.now(timezone.utc) - timedelta(hours=1)
        counts = {"ingest": _run(client, ingest_time, 0, same_end)["count"],
                  "search": _run(client, search_time, 0, same_end)["count"]}
        results[name] = {
            "ingest_p50_ms": round(statistics.median(r["server_ms"] for r in runs["ingest"]), 1),
            "search_p50_ms": round(statistics.median(r["server_ms"] for r in runs["search"]), 1),
            "ingest_wall_p50_ms": round(statistics.median(r["wall_ms"] for r in runs["ingest"]), 1),
            "search_wall_p50_ms": round(statistics.median(r["wall_ms"] for r in runs["search"]), 1),
            "counts": counts, "same_answer": counts["ingest"] == counts["search"],
            "queries": {"ingest": ingest_time, "search": search_time},
        }
        print(f"{name}: {results[name]}", flush=True)
    return results


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Search-time extraction benchmark")
    parser.add_argument("--api", default=os.getenv("LOGFORGE_API_URL", "http://localhost:7080"))
    parser.add_argument("--rows", type=int, default=10_000_000, help="seed the tenant up to this many rows")
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    email, password = os.getenv("BENCH_EMAIL"), os.getenv("BENCH_PASSWORD")
    if not email or not password:
        print("Set BENCH_EMAIL and BENCH_PASSWORD (a user of a dedicated benchmark tenant).", file=sys.stderr)
        return 2
    from perf_bench import clickhouse, login, seed_sql

    client = login(args.api, email, password)
    have = _rows(client.tenant_id)
    if have < args.rows:
        print(f"seeding {args.rows - have:,} rows", flush=True)
        clickhouse(seed_sql(client.tenant_id, args.rows - have))
    rows = _rows(client.tenant_id)
    print(f"{rows:,} rows in the window", flush=True)
    results = measure(client, repeats=args.repeats)
    report = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "rows": rows,
              "environment": {"host": platform.platform(), "python": platform.python_version(),
                              "cpus": os.cpu_count()},
              "results": results, "verdict": verdict(results)}
    print(json.dumps(report["verdict"]), flush=True)
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
