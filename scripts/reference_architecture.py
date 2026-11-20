#!/usr/bin/env python3
"""
Reference architecture (Phase 12): what one year of retention costs for a
tenant ingesting 50 GB/day, from measured sizes and list prices.

Inputs, all measured on this repository's benchmark data (docs/storage.md):

    raw_bytes_per_event       297   JSON as a shipper sends it
    stored_bytes_per_event     29   ClickHouse, compressed, per replica
    archive_bytes_per_event    33   Parquet

and a retention of 30 days searchable (7 hot, 23 warm) and 365 days
archived. Compute is sized for the average rate with 3x headroom for peaks,
with ingest throughput per API replica from tests/bench/ingest_bench.py.

Prices are public on-demand list prices (AWS us-east-1, late 2026) and are
assumptions, not quotes; change PRICES for your provider. The published
target (docs/deployment.md) is checked against the total.

    python scripts/reference_architecture.py [--gb-per-day 50] [--out FILE]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "apps" / "api"))

GB = 1024 ** 3
HOURS_PER_MONTH = 730
TARGET_PER_MONTH = 2000.0  # the published target, USD (docs/deployment.md)

MEASURED = {"raw_bytes_per_event": 297, "stored_bytes_per_event": 29, "archive_bytes_per_event": 33}

PRICES = {
    # storage, per GB-month
    "ebs_gp3": 0.08, "s3_standard": 0.023, "s3_standard_ia": 0.0125,
    # compute, per hour (on demand)
    "clickhouse_node": 0.768,   # 16 vCPU / 64 GiB (m6i.4xlarge)
    "keeper_node": 0.0416,      # 2 vCPU / 4 GiB (t3.medium)
    "redpanda_node": 0.192,     # 4 vCPU / 16 GiB (m6i.xlarge)
    "api_replica": 0.096,       # 2 vCPU / 8 GiB (m6i.large share)
    "ui_and_jobs": 0.096,
    # S3 requests: retention writes one Parquet object per tenant-day; warm
    # parts are few and large. Small next to storage; budgeted at a fixed amount.
    "s3_requests_month": 20.0,
}


def plan(gb_per_day: float, events_per_second_per_api: float, hot_days: int = 7, searchable_days: int = 30,
         archive_days: int = 365, replicas: int = 2, peak_factor: float = 3.0,
         measured=MEASURED, prices=PRICES) -> dict:
    events_per_day = gb_per_day * 1e9 / measured["raw_bytes_per_event"]
    avg_eps = events_per_day / 86400
    stored_day = events_per_day * measured["stored_bytes_per_event"] / GB      # GiB per replica
    archive_day = events_per_day * measured["archive_bytes_per_event"] / GB
    hot_gb = stored_day * hot_days * replicas
    warm_gb = stored_day * max(0, searchable_days - hot_days) * replicas
    cold_gb = archive_day * max(0, archive_days - searchable_days)
    # local disks: hot data plus merge headroom (2x) and a 100 GiB floor per node
    disk_per_node = max(100.0, 2 * hot_gb / replicas)
    redpanda_disk = 3 * events_per_day * measured["raw_bytes_per_event"] / GB / 4  # ~6 h of raw ingest x3 replicas
    api_replicas = max(2, math.ceil(avg_eps * peak_factor / events_per_second_per_api))
    storage = {
        "clickhouse_local_disks": round(disk_per_node * replicas * prices["ebs_gp3"], 2),
        "warm_s3": round(warm_gb * prices["s3_standard"], 2),
        "cold_parquet_s3_ia": round(cold_gb * prices["s3_standard_ia"], 2),
        "redpanda_disks": round(redpanda_disk * prices["ebs_gp3"], 2),
        "s3_requests": prices["s3_requests_month"],
    }
    compute = {
        "clickhouse_replicas": round(replicas * prices["clickhouse_node"] * HOURS_PER_MONTH, 2),
        "keeper_x3": round(3 * prices["keeper_node"] * HOURS_PER_MONTH, 2),
        "redpanda_x3": round(3 * prices["redpanda_node"] * HOURS_PER_MONTH, 2),
        "api_replicas": round(api_replicas * prices["api_replica"] * HOURS_PER_MONTH, 2),
        "ui_and_jobs": round(prices["ui_and_jobs"] * HOURS_PER_MONTH, 2),
    }
    monthly = round(sum(storage.values()) + sum(compute.values()), 2)
    return {
        "inputs": {"gb_per_day": gb_per_day, "hot_days": hot_days, "searchable_days": searchable_days,
                   "archive_days": archive_days, "clickhouse_replicas": replicas, "peak_factor": peak_factor,
                   "events_per_second_per_api_replica": events_per_second_per_api, **measured},
        "volume": {"events_per_day": round(events_per_day), "average_events_per_second": round(avg_eps),
                   "peak_events_per_second": round(avg_eps * peak_factor),
                   "stored_gib_per_day_per_replica": round(stored_day, 2),
                   "archive_gib_per_day": round(archive_day, 2)},
        "steady_state_gib": {"hot_all_replicas": round(hot_gb), "warm_all_replicas": round(warm_gb),
                             "cold_parquet": round(cold_gb), "local_disk_per_clickhouse_node": round(disk_per_node)},
        "api_replicas": api_replicas,
        "monthly_usd": {"storage": storage, "compute": compute, "total": monthly},
        "yearly_usd": round(monthly * 12),
        "target_monthly_usd": TARGET_PER_MONTH,
        "within_target": monthly <= TARGET_PER_MONTH,
        "prices": prices,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gb-per-day", type=float, default=50)
    parser.add_argument("--api-eps", type=float, help="events/s one API replica stores (default: from the "
                                                       "ingest benchmark)")
    parser.add_argument("--out", default=str(REPO / "docs" / "benchmarks" / "2026-11-20-reference-architecture.json"))
    args = parser.parse_args()
    eps = args.api_eps
    if eps is None:
        bench = json.loads((REPO / "docs" / "benchmarks" / "2026-11-20-ingest-ha.json").read_text())
        eps = bench["stored_per_second"] / bench["api_replicas"]
    out = plan(args.gb_per_day, eps)
    print(json.dumps(out, indent=2))
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    return 0 if out["within_target"] else 1


if __name__ == "__main__":
    sys.exit(main())
