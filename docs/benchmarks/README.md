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

## Threat-intel enrichment: 2026-11-18

Phase 3 acceptance: ingest throughput must drop by less than 10% with
threat-intel matching on. Measured with
[`tests/bench/enrichment_bench.py`](https://github.com/miteshpant/Logforge/blob/main/tests/bench/enrichment_bench.py)
on the same 4-vCPU single-node stack, against 100,000 synthetic indicators
(60% IPs, 30% domains, 10% URLs). Raw results:
[`2026-11-18-enrichment.json`](./2026-11-18-enrichment.json).

| Measurement | Without indicators | With 100,000 indicators |
|---|---|---|
| In process: `enrich_events` per event (30,000 events, median of 5) | 0.03 µs | 12.0 µs |
| Live: `POST /v1/ingest/logs/batch`, 10 × 1,000 events, median of 4 rounds | 2,868 events/s | 3,100 events/s |

Per round, the live runs were 2,803 / 3,684 / 2,833 / 2,904 events/s
without indicators and 3,160 / 2,882 / 3,039 / 3,186 with them. Rounds
alternate which side goes first. Before each run the indicator index is
reloaded and the API is allowed to drain the previous run's work.

**Result: no measurable drop.** The median with indicators was 8% *higher*,
which is inside the ±15–30% spread between rounds. So the live A/B can only
say that any drop is smaller than its noise. The in-process figure gives the
bound: 12 µs added to about 349 µs per event at 2,868 events/s is about
**3.5%**, under the 10% limit. GeoIP, asset and reverse-DNS lookups were not
enabled in this run.

These numbers are higher than the 277 events/s baseline above because this
run times smaller bursts with the API drained between them. The baseline
measured 50 batches back to back, with detection work piling up.

## History

| Date | Setup | Ingest (events/s) | Ingest → searchable | Slowest query p95 @ 10 M |
|---|---|---|---|---|
| 2026-11-17 | single node, 4 vCPU | 277 | 36.8 s | 311 ms (full-text search) |
| 2026-11-18 | single node, 4 vCPU; enrichment A/B, bursts of 10,000 | 2,868 without / 3,100 with 100k indicators | — | — |
