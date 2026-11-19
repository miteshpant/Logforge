"""
Ingest pipeline benchmark (Phase 4 acceptance: pipelines with 10 processors
keep ingest within 20% of the Phase 0 baseline).

Ingest is asynchronous: POST /v1/ingest/logs/batch returns once the batch is
queued, and normalisation, pipelines, enrichment, detection and storage run
after that. Timing the POSTs alone would not include the pipeline at all. So
this measures END-TO-END throughput: N events are posted and the clock stops
when all N are stored in logs_raw_mt.

Rounds alternate a benchmark tenant with no pipeline (A) and with a
10-processor default pipeline (B); the medians are compared. An in-process
figure (the pipeline's own cost per event) is reported as well.

    BENCH_EMAIL=bench@bench.example BENCH_PASSWORD='Bench-Pass-123!' \\
      python tests/bench/pipeline_bench.py --live --out docs/benchmarks/<date>-pipelines.json
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import platform
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

PIPELINE_ID = "bench-ten-processors"
TEN_PROCESSORS: Dict[str, Any] = {
    "name": PIPELINE_ID, "description": "Benchmark: ten typical processors",
    "routing": {"default": True},
    "processors": [
        {"kv": {"field": "msg", "target": "attrs", "include_keys": ["user", "action", "bytes", "latency_ms", "path"]}},
        {"convert": {"field": "attrs.bytes", "type": "integer"}},
        {"convert": {"field": "attrs.latency_ms", "type": "float"}},
        {"lowercase": {"field": "attrs.action"}},
        {"rename": {"field": "attrs.path", "target_field": "attrs.http_path"}},
        {"set": {"field": "attrs.summary", "value": "{{attrs.user}} {{attrs.action}} {{attrs.http_path}}"}},
        {"script": {"source": "attrs.slow = attrs.latency_ms > 500; attrs.kb = attrs.bytes / 1024"}},
        {"mask": {"field": "msg", "kinds": ["email"]}},
        {"set": {"field": "level", "value": "warn"}, "if": "attrs.slow"},
        {"remove": {"field": "attrs.user"}},
    ],
}


def traffic(n: int, run_id: str) -> List[Dict[str, Any]]:
    events = []
    for i in range(n):
        events.append({"service": f"bench-pl-{run_id}", "level": "info",
                       "msg": (f"user=user{i % 50}@corp.example action={'LOGIN' if i % 3 else 'Download'} "
                               f"bytes={100 + i % 900} latency_ms={(i * 37) % 900}.5 path=/api/v1/items/{i % 40}"),
                       "attrs": {"run": run_id}})
    return events


def rate(events: int, seconds: float) -> float:
    return round(events / seconds, 1) if seconds > 0 else 0.0


def compare(off: Dict[str, Any], on: Dict[str, Any], limit_pct: float = 20) -> Dict[str, Any]:
    off_eps, on_eps = float(off["events_per_second"]), float(on["events_per_second"])
    drop = round(100 * (off_eps - on_eps) / off_eps, 2) if off_eps else 0.0
    return {"off_eps": off_eps, "on_eps": on_eps, "drop_pct": drop, "limit_pct": limit_pct, "pass": drop < limit_pct}


def in_process(events: int = 20_000, rounds: int = 5) -> Dict[str, Any]:
    from pipeline_processors import ProcessorContext
    from pipeline_store import PipelineRecord

    pipeline = PipelineRecord.from_dict(TEN_PROCESSORS).pipeline
    timings = []
    for r in range(rounds):
        batch = traffic(events, f"inproc-{r}")
        docs = [dict(e, attrs=dict(e["attrs"])) for e in batch]
        start = time.perf_counter()
        for doc in docs:
            pipeline.run(doc, ProcessorContext())
        timings.append((time.perf_counter() - start) / events)
    return {"processors": len(pipeline.steps), "events": events, "rounds": rounds,
            "us_per_event": round(statistics.median(timings) * 1e6, 2)}


# -- live ---------------------------------------------------------------------

def _stored(tenant_id: str, service: str) -> int:
    from perf_bench import clickhouse

    if not all(c.isalnum() or c in "-_" for c in tenant_id + service):
        raise ValueError("unexpected identifier")
    out = clickhouse(f"SELECT count() FROM logs_raw_mt WHERE customer_id = '{tenant_id}' AND service = '{service}'")
    return int(out.strip() or 0)


def _round(connect, n: int, batch_size: int = 1000, timeout_s: float = 600) -> Dict[str, Any]:
    client = connect()
    run_id = uuid.uuid4().hex[:10]
    events = traffic(n, run_id)
    service = events[0]["service"]
    start = time.perf_counter()
    for i in range(0, n, batch_size):
        client.post("/v1/ingest/logs/batch", copy.deepcopy(events[i:i + batch_size]))
    posted = time.perf_counter() - start
    while True:
        stored = _stored(client.tenant_id, service)
        if stored >= n or time.perf_counter() - start > timeout_s:
            break
        time.sleep(0.5)
    seconds = time.perf_counter() - start
    return {"events": n, "stored": stored, "post_seconds": round(posted, 2), "seconds": round(seconds, 2),
            "events_per_second": rate(stored, seconds)}


def _settle(connect, quiet_rounds: int = 3) -> None:
    from enrichment_bench import _settle as settle

    settle(connect())


def live_ab(connect, rounds: int = 3, n: int = 5000, cache_ttl_s: int = 35) -> Dict[str, Any]:
    runs: Dict[str, List[Dict[str, Any]]] = {"off": [], "on": []}

    def set_pipeline(on: bool) -> None:
        client = connect()
        try:
            client._call("DELETE", f"/v1/pipelines/{PIPELINE_ID}")
        except Exception:
            pass  # not there
        if on:
            client.post("/v1/pipelines", TEN_PROCESSORS)
        time.sleep(cache_ttl_s)  # every API worker's pipeline cache has expired

    try:
        for r in range(rounds):
            for side in (("off", "on") if r % 2 == 0 else ("on", "off")):
                set_pipeline(side == "on")
                _settle(connect)
                runs[side].append(_round(connect, n))
                print(f"round {r + 1} {side}: {runs[side][-1]}", flush=True)
    finally:
        set_pipeline(False)
    median = lambda side: {"events_per_second": statistics.median(x["events_per_second"] for x in runs[side])}  # noqa: E731
    return {"rounds": rounds, "events_per_round": n, **runs, **compare(median("off"), median("on"))}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest pipeline benchmark")
    parser.add_argument("--api", default=os.getenv("LOGFORGE_API_URL", "http://localhost:7080"))
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--events", type=int, default=5000)
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    results: Dict[str, Any] = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "environment": {"host": platform.platform(), "python": platform.python_version(),
                                               "cpus": os.cpu_count()},
                               "in_process": in_process()}
    print(f"in-process: {results['in_process']}", flush=True)
    if args.live:
        from perf_bench import login

        email, password = os.getenv("BENCH_EMAIL"), os.getenv("BENCH_PASSWORD")
        if not email or not password:
            print("Set BENCH_EMAIL and BENCH_PASSWORD (a user of a dedicated benchmark tenant).", file=sys.stderr)
            return 2
        results["live_end_to_end"] = live_ab(lambda: login(args.api, email, password), rounds=args.rounds,
                                             n=args.events)
        live = results["live_end_to_end"]
        print(f"end to end: off {live['off_eps']} ev/s, on {live['on_eps']} ev/s, drop {live['drop_pct']}%")
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
