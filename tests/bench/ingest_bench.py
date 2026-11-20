#!/usr/bin/env python3
"""
Ingest throughput with concurrent shippers (Phase 12): events per second
accepted by POST /v1/ingest/logs/batch, and stored in ClickHouse, through a
load balancer in front of the API replicas (the HA compose by default).

Each writer sends batches back to back (as Vector or Fluent Bit do); the
benchmark then waits until every accepted event is in ClickHouse, so
"stored per second" covers the whole path: API -> Redpanda -> consumer ->
ClickHouse (replicated).

    LOGFORGE_API_URL=http://localhost:7180 python tests/bench/ingest_bench.py --writers 8 --seconds 60
"""

import argparse
import json
import os
import sys
import threading
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
os.environ.setdefault("LOGFORGE_API_URL", "http://localhost:7180")
sys.path.insert(0, str(REPO / "scripts"))
from bootstrap_demo import admin_token, tenant_id  # noqa: E402

API = os.environ["LOGFORGE_API_URL"].rstrip("/")
CLICKHOUSE = os.getenv("LOGFORGE_HA_CLICKHOUSE", "http://localhost:8180")


def clickhouse(sql):
    req = urllib.request.Request(CLICKHOUSE + "/?database=logforge", data=sql.encode(), method="POST",
                                 headers={"X-ClickHouse-User": "logforge", "X-ClickHouse-Key": "logforge123"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode().strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--writers", type=int, default=8)
    parser.add_argument("--batch", type=int, default=500)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--api-replicas", type=int, default=2, help="for the report")
    parser.add_argument("--out", default=str(REPO / "docs" / "benchmarks" / "2026-11-20-ingest-ha.json"))
    args = parser.parse_args()
    token = admin_token()
    tenant = tenant_id(token)
    run = uuid.uuid4().hex[:10]
    accepted, failed, raw_bytes = [0], [0], [0]
    lock = threading.Lock()
    stop = time.time() + args.seconds

    def writer(w):
        n = 0
        while time.time() < stop:
            logs = [{"ts": datetime.now(timezone.utc).isoformat(), "service": f"bench-{i % 12}", "level": "info",
                     "host": f"host-{w}", "msg": f"GET /api/orders/{n + i} 200 {12 + i % 300}ms user=u{i % 977}",
                     "attrs": {"bench_run": run, "path": "/api/orders", "status": 200}} for i in range(args.batch)]
            body = json.dumps({"logs": logs}).encode()
            req = urllib.request.Request(API + "/v1/ingest/logs/batch", data=body, method="POST", headers={
                "Content-Type": "application/json", "Authorization": f"Bearer {token}", "X-Customer-ID": tenant})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    ok = 200 <= r.status < 300
            except Exception:
                ok = False
            with lock:
                if ok:
                    accepted[0] += args.batch
                    raw_bytes[0] += len(body)
                else:
                    failed[0] += 1
            n += args.batch

    began = time.time()
    threads = [threading.Thread(target=writer, args=(w,)) for w in range(args.writers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    sent_s = time.time() - began
    stored = 0
    while time.time() - began < sent_s + 600:
        stored = int(clickhouse(f"SELECT count() FROM logs_raw_mt WHERE customer_id = '{tenant}' "
                                f"AND JSONExtractString(attrs, 'bench_run') = '{run}'") or 0)
        if stored >= accepted[0]:
            break
        time.sleep(2)
    stored_s = time.time() - began
    report = {"writers": args.writers, "batch": args.batch, "api_replicas": args.api_replicas,
              "seconds_sending": round(sent_s, 1), "accepted_events": accepted[0], "failed_requests": failed[0],
              "accepted_per_second": round(accepted[0] / sent_s), "request_bytes": raw_bytes[0],
              "stored_events": stored, "seconds_until_stored": round(stored_s, 1),
              "stored_per_second": round(stored / stored_s), "machine": f"{os.cpu_count()} vCPUs, every service "
                                                                         "on one host"}
    print(json.dumps(report, indent=2))
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
