#!/usr/bin/env python3
"""
Seed the demo tenant with an hour of realistic telemetry and a few attacks,
for screenshots and demos (see scripts/capture_screenshots.js).

* about 1,800 logs across 5 services, 120 traces (480 spans), 240 metric
  points;
* three small intrusions that the shipped rules detect (brute force then a
  successful login, a password spray, discovery then an LSASS dump), so
  case grouping opens cases on its own;
* one of those cases worked by an analyst: assigned, a note, pinned
  evidence, moved to investigating.

Run after scripts/bootstrap_demo.py, against a running stack:

    python scripts/seed_demo_telemetry.py
"""

from __future__ import annotations

import random
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootstrap_demo as demo  # noqa: E402

random.seed(7)
NOW = datetime.now(timezone.utc)
ANALYST = "dana@acme.example"

SERVICES = {
    "checkout": ["order placed", "payment authorized", "payment declined", "cart validated"],
    "auth": ["user login succeeded", "token refreshed", "session expired", "password changed"],
    "inventory": ["stock reserved", "stock level low", "warehouse sync complete"],
    "api-gateway": ["GET /v1/orders 200", "POST /v1/cart 201", "GET /v1/products 200", "upstream timeout"],
    "payments": ["charge created", "refund issued", "card network error"],
}
LEVELS = ["info"] * 14 + ["warn"] * 3 + ["error"] * 2 + ["debug"]
HOSTS = ["web-01", "web-02", "worker-01", "worker-02"]


def call(method, path, body=None):
    status, data = demo.call(method, path, body, token=TOKEN, tenant=TENANT)
    if status >= 400:
        raise SystemExit(f"{method} {path} failed: {status} {data}")
    return data


def at(seconds_ago: float) -> str:
    return (NOW - timedelta(seconds=seconds_ago)).isoformat()


def seed_logs():
    logs = []
    for _ in range(1800):
        service = random.choice(list(SERVICES))
        message = random.choice(SERVICES[service])
        level = "error" if any(w in message for w in ("declined", "error", "timeout")) else random.choice(LEVELS)
        logs.append({"service": service, "level": level, "msg": message, "host": random.choice(HOSTS),
                     "ts": at(random.randint(0, 3500)), "trace_id": uuid.uuid4().hex,
                     "src_ip": f"10.0.{random.randint(0, 3)}.{random.randint(2, 250)}",
                     "attrs": {"region": random.choice(["us-east-1", "eu-west-1"]),
                               "latency_ms": random.randint(5, 900)}})
    for i in range(0, len(logs), 200):
        call("POST", "/v1/ingest/logs/batch", {"logs": logs[i:i + 200]})
    print(f"logs: {len(logs)}")


def seed_traces():
    spans = []
    chain = [("api-gateway", "HTTP POST /checkout"), ("checkout", "place_order"),
             ("inventory", "reserve_stock"), ("payments", "charge_card")]
    for _ in range(120):
        trace_id, parent = uuid.uuid4().hex, None
        start = NOW - timedelta(seconds=random.randint(0, 3500))
        for depth, (service, operation) in enumerate(chain):
            span_id = uuid.uuid4().hex[:16]
            failed = service == "payments" and random.random() < 0.08
            spans.append({"trace_id": trace_id, "span_id": span_id, "parent_span_id": parent,
                          "operation_name": operation, "service_name": service,
                          "start_time": (start + timedelta(milliseconds=depth * 5)).isoformat(),
                          "duration_ms": random.randint(20, 400) // (depth + 1),
                          "status": "error" if failed else "ok", "kind": "server",
                          "attributes": {"http.method": "POST"} if depth == 0 else {}})
            parent = span_id
    for i in range(0, len(spans), 200):
        call("POST", "/v1/observability/traces/ingest", {"spans": spans[i:i + 200]})
    print(f"spans: {len(spans)}")


def seed_metrics():
    metrics = []
    for minute in range(60):
        ts = (NOW - timedelta(minutes=60 - minute)).isoformat()
        for name, base in [("cpu.utilization", 45), ("memory.used_pct", 62),
                           ("http.requests_per_sec", 320), ("http.p95_latency_ms", 180)]:
            metrics.append({"metric_name": name, "metric_type": "gauge", "timestamp": ts,
                            "value": round(base * random.uniform(0.75, 1.3), 2)})
    call("POST", "/v1/observability/metrics/ingest", {"metrics": metrics})
    print(f"metrics: {len(metrics)}")


def seed_attacks() -> str:
    """Three intrusions the shipped rules detect; returns the brute-force source."""
    brute = f"203.0.113.{random.randint(10, 250)}"
    spray = f"45.155.205.{random.randint(10, 250)}"

    def auth(ip, user, result, seconds_ago):
        return {"ts": at(seconds_ago), "service": "sshd", "host": "bastion-01", "msg": f"authentication {result}",
                "src_ip": ip, "attrs": {"event_type": "authentication", "result": result, "user": user}}

    batches = [
        [auth(brute, "deploy", "failed", 900 - i * 5) for i in range(12)] + [auth(brute, "deploy", "success", 780)],
        [auth(spray, user, "failed", 600 - i * 3) for i, user in enumerate(
            ["alice", "bob", "carol", "dave", "erin", "frank"])],
        [{"ts": at(400), "service": "sysmon", "host": "WS-044", "msg": "Process created",
          "attrs": {"user": "carol", "process_name": r"C:\Windows\System32\whoami.exe", "command_line": "whoami /priv"}},
         {"ts": at(300), "service": "sysmon", "host": "WS-044", "msg": "Process created",
          "attrs": {"user": "carol", "process_name": r"C:\Users\Public\procdump64.exe",
                    "command_line": r"procdump64.exe -accepteula -ma lsass.exe C:\Users\Public\l.dmp"}}],
    ]
    for batch in batches:
        call("POST", "/v1/ingest/logs/batch", {"logs": batch})
        time.sleep(2)
    print(f"attacks: brute force from {brute}, spray from {spray}, LSASS dump on WS-044")
    return brute


def work_a_case(source_ip: str):
    """An analyst picks up the brute-force case."""
    for _ in range(45):  # detection and grouping run asynchronously
        found = call("GET", f"/v1/security/cases?q={source_ip}")
        if found.get("total"):
            break
        time.sleep(2)
    else:
        print("no case opened for the brute force (is detection running?)")
        return
    case_id = found["cases"][0]["id"]
    call("POST", f"/v1/security/cases/{case_id}/assign", {"assignee": ANALYST})
    call("POST", f"/v1/security/cases/{case_id}/status", {"status": "investigating"})
    call("POST", f"/v1/security/cases/{case_id}/comments", {
        "text": f"12 failed logins for `deploy` from {source_ip}, then a success. Checking what the session did; "
                "@soc-lead the bastion key for deploy may need rotating."})
    call("POST", f"/v1/security/cases/{case_id}/evidence", {
        "kind": "search", "ref": source_ip, "title": "Everything from the source address"})
    call("POST", f"/v1/security/cases/{case_id}/tags", {"add": ["bastion", "credential-access"]})
    print(f"case worked: {case_id}")


if __name__ == "__main__":
    TOKEN = demo.admin_token()
    TENANT = demo.tenant_id(TOKEN)
    seed_logs()
    seed_traces()
    seed_metrics()
    work_a_case(seed_attacks())
