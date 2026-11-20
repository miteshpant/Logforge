#!/usr/bin/env python3
"""
Chaos test (Phase 12): losing a ClickHouse replica or an API replica must
lose no data and cause no downtime. Runs against the HA compose
(infra/docker/ha/compose.ha.yml), bootstrapped with
`LOGFORGE_API_URL=http://localhost:7180 python scripts/bootstrap_demo.py`.

While a loader sends numbered log batches through the load balancer
(retrying a failed batch the way a log shipper does) and a reader runs a
query every second, the test:

  1. kills ClickHouse replica ch1 (the one serving queries) with SIGKILL,
     waits, starts it again;
  2. kills API replica api1 with SIGKILL, waits, starts it again.

Then it waits for ingest to drain and checks every acknowledged event is
stored (none missing; duplicates are counted, since delivery is
at-least-once), and reports the longest stretch with no successful write
and no successful read, against a target of under 10 s each.

    python scripts/chaos_test.py [--seconds-per-fault 20]
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
os.environ.setdefault("LOGFORGE_API_URL", "http://localhost:7180")
sys.path.insert(0, str(REPO / "scripts"))
from bootstrap_demo import admin_token, tenant_id  # noqa: E402

API = os.environ["LOGFORGE_API_URL"].rstrip("/")
CLICKHOUSE = os.getenv("LOGFORGE_HA_CLICKHOUSE", "http://localhost:8180")
PROJECT = os.getenv("LOGFORGE_HA_PROJECT", "logforge-ha")
TARGET_GAP_SECONDS = 10.0


def post(path, body, token, tenant, timeout=10):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(), method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {token}", "X-Customer-ID": tenant})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read() or b"{}")


def clickhouse(sql):
    req = urllib.request.Request(CLICKHOUSE + "/?database=logforge", data=sql.encode(), method="POST",
                                 headers={"X-ClickHouse-User": "logforge", "X-ClickHouse-Key": "logforge123"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode().strip()


def docker(*args):
    subprocess.run(["docker", *args], check=True, capture_output=True)


class Load:
    def __init__(self, token, tenant, run, batch=20, interval=0.25):
        self.token, self.tenant, self.run, self.batch, self.interval = token, tenant, run, batch, interval
        self.acked, self.failures, self.stop = set(), 0, threading.Event()
        self.write_ok, self.read_ok, self.read_failures = [], [], 0
        self.seq = 0

    def writer(self):
        while not self.stop.is_set():
            seqs = list(range(self.seq, self.seq + self.batch))
            self.seq += self.batch
            logs = [{"ts": datetime.now(timezone.utc).isoformat(), "service": "chaos", "level": "info",
                     "host": "loader", "msg": f"chaos {self.run} event {s}",
                     "attrs": {"chaos_run": self.run, "seq": s}} for s in seqs]
            while not self.stop.is_set():  # a shipper retries a failed batch
                try:
                    status, _ = post("/v1/ingest/logs/batch", {"logs": logs}, self.token, self.tenant)
                    if 200 <= status < 300:
                        self.acked.update(seqs)
                        self.write_ok.append(time.time())
                        break
                except Exception:
                    pass
                self.failures += 1
                time.sleep(0.5)
            time.sleep(self.interval)

    def reader(self):
        while not self.stop.is_set():
            try:
                status, body = post("/v1/query/logql", {"query": '| where service = "chaos" | stats count()',
                                                        "since": "1h"}, self.token, self.tenant)
                if status == 200:
                    self.read_ok.append(time.time())
                else:
                    self.read_failures += 1
            except Exception:
                self.read_failures += 1
            time.sleep(1)


def longest_gap(times, start, end):
    points = [start] + sorted(t for t in times if start <= t <= end) + [end]
    return round(max(b - a for a, b in zip(points, points[1:])), 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seconds-per-fault", type=int, default=20)
    parser.add_argument("--out", default=str(REPO / "docs" / "benchmarks" / "2026-11-20-chaos.json"))
    args = parser.parse_args()
    token = admin_token()
    tenant = tenant_id(token)
    run = uuid.uuid4().hex[:10]
    load = Load(token, tenant, run)
    threads = [threading.Thread(target=load.writer, daemon=True), threading.Thread(target=load.reader, daemon=True)]
    began = time.time()
    for t in threads:
        t.start()
    timeline = []

    def step(what, *cmd):
        timeline.append({"at": round(time.time() - began, 1), "event": what})
        print(f"{timeline[-1]['at']:>6}s  {what}", flush=True)
        if cmd:
            docker(*cmd)

    wait = args.seconds_per_fault
    time.sleep(wait)
    step("kill ClickHouse replica ch1 (SIGKILL)", "kill", f"{PROJECT}-ch1-1")
    time.sleep(wait)
    step("start ch1", "start", f"{PROJECT}-ch1-1")
    time.sleep(wait)
    step("kill API replica api1 (SIGKILL)", "kill", f"{PROJECT}-api1-1")
    time.sleep(wait)
    step("start api1", "start", f"{PROJECT}-api1-1")
    time.sleep(wait)
    load.stop.set()
    for t in threads:
        t.join(timeout=15)
    ended = time.time()
    step("load stopped; waiting for ingest to drain")

    where = f"customer_id = '{tenant}' AND JSONExtractString(attrs, 'chaos_run') = '{run}'"
    stored, distinct = 0, 0
    deadline = time.time() + 180
    while time.time() < deadline:
        try:
            stored, distinct = (int(x) for x in clickhouse(
                f"SELECT count(), uniqExact(JSONExtractUInt(attrs, 'seq')) FROM logs_raw_mt WHERE {where}").split())
            if distinct >= len(load.acked):
                break
        except Exception:
            pass
        time.sleep(3)
    present = set()
    for line in clickhouse(f"SELECT DISTINCT JSONExtractUInt(attrs, 'seq') FROM logs_raw_mt WHERE {where}").split():
        present.add(int(line))
    missing = sorted(load.acked - present)
    on_replica = {}
    for replica in ("ch1", "ch2"):
        out = subprocess.run(["docker", "exec", f"{PROJECT}-{replica}-1", "clickhouse-client", "--user", "logforge",
                              "--password", "logforge123", "-q",
                              f"SELECT count() FROM logforge.logs_raw_mt WHERE {where}"],
                             capture_output=True, text=True)
        on_replica[replica] = int(out.stdout.strip() or 0)
    report = {
        "run": run, "duration_seconds": round(ended - began, 1), "timeline": timeline,
        "acknowledged_events": len(load.acked), "stored_rows": stored, "stored_distinct": distinct,
        "missing": len(missing), "missing_sample": missing[:20], "duplicates": stored - distinct,
        "rows_per_replica": on_replica,
        "write_retries": load.failures, "read_failures": load.read_failures,
        "longest_write_gap_seconds": longest_gap(load.write_ok, began, ended),
        "longest_read_gap_seconds": longest_gap(load.read_ok, began, ended),
        "target_gap_seconds": TARGET_GAP_SECONDS,
    }
    report["no_data_loss"] = report["missing"] == 0
    report["no_downtime"] = (report["longest_write_gap_seconds"] < TARGET_GAP_SECONDS
                             and report["longest_read_gap_seconds"] < TARGET_GAP_SECONDS)
    print(json.dumps(report, indent=2))
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["no_data_loss"] and report["no_downtime"] else 1


if __name__ == "__main__":
    sys.exit(main())
