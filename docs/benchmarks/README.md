# Performance benchmarks

Measured with [`tests/bench/perf_bench.py`](https://github.com/miteshpant/Logforge/blob/main/tests/bench/perf_bench.py)
against a running compose stack, in a dedicated benchmark tenant so synthetic
rows never reach real data. Each release should add a results file here and a
row to the history table.

## How to run

```bash
# once: a tenant and user just for benchmarks
TENANT_NAME=Bench DEMO_USER_NAME="Bench Runner" DEMO_USER_EMAIL=bench@bench.example \
  DEMO_USER_PASSWORD='Bench-Pass-123!' python scripts/bootstrap_demo.py

BENCH_EMAIL=bench@bench.example BENCH_PASSWORD='Bench-Pass-123!' \
  python tests/bench/perf_bench.py --rows 1000000 10000000 --out docs/benchmarks/<date>-<setup>.json
```

What it measures:

| Metric | How |
|---|---|
| Ingest throughput | 50 batches of 1,000 events posted back to back to `/v1/ingest/logs/batch` by one client |
| Ingest → searchable | Time from posting one log until `GET /v1/logs` returns it |
| Query latency | 20 runs each of five fixed queries, p50/p95, after seeding the tenant to each dataset size directly in ClickHouse. Result-cached endpoints get a distinct window per run, so the cache is not measured |

## Baseline: 2026-11-17, single node

Setup: the compose stack on one 4-vCPU VM (API, ClickHouse, Redpanda, Redis
and MinIO sharing it); API container in its default single-process mode.
Raw results: [`2026-11-17-single-node.json`](./2026-11-17-single-node.json).

### Ingest

| Metric | Result |
|---|---|
| Sustained ingest, one client, 1,000-event batches | **277 events/s** (50,000 events in 180 s) |
| A single 1,000-event batch on an idle stack | 60–95 ms (≈ 11,000–16,000 events/s if sustained) |
| Ingest → searchable | **36.8 s** |

The gap between the single-batch and the sustained numbers is the main
finding. Under sustained load the API container sits at ~100% CPU while
ClickHouse is at ~2%, and request latency climbs from ~0.1 s to several
seconds. Post-ingest work (normalisation and running ~274 detection rules on
every event) runs inside the same single Python process that serves requests.
That is the likely bottleneck; it has not been profiled yet. Profiling the
ingest path, moving detection to separate workers and running the API with
multiple workers are tracked in [ROADMAP.md](../ROADMAP.md).

### Query latency

| Query | 1 M rows p50 / p95 | 10 M rows p50 / p95 |
|---|---|---|
| Latest 100 logs (last hour) | 113 / 144 ms | 177 / 247 ms |
| Service filter, 100 logs (24 h) | 91 / 106 ms | 128 / 158 ms |
| LogforgeQL: errors by service (24 h) | 70 / 157 ms | 89 / 117 ms |
| LogforgeQL: full-text search (24 h) | 102 / 119 ms | 233 / 311 ms |
| Count by level (24 h) | 108 / 123 ms | 140 / 172 ms |

Queries stay well under a second at 10 M rows; full-text search grows fastest
with data size.

## History

| Date | Setup | Ingest (events/s) | Ingest → searchable | Slowest query p95 @ 10 M |
|---|---|---|---|---|
| 2026-11-17 | single node, 4 vCPU | 277 | 36.8 s | 311 ms (full-text search) |
