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
without indicators and 3,160 / 2,882 / 3,039 / 3,186 with them.

**Correction (2026-11-19).** The live row measured how fast the API
*accepts* batches, not how fast it processes them. `POST
/v1/ingest/logs/batch` returns once a batch is queued; normalisation,
enrichment, detection and storage run afterwards in the ingest worker. The
live A/B therefore did not include enrichment, and its "no measurable drop"
says nothing about it. The evidence is the in-process cost: 12 µs per event.
Against the end-to-end cost of an event on this stack (about 590 µs,
measured by the pipeline benchmark below, which times until events are
stored), that is about **2%**, under the 10% limit. GeoIP, asset and
reverse-DNS lookups were not enabled.

These numbers are higher than the 277 events/s baseline above because this
run times smaller bursts with the API drained between them. The baseline
measured 50 batches back to back, with detection work piling up.

## Ingest pipelines: 2026-11-19

Phase 4 acceptance: with a 10-processor pipeline, ingest must stay within
20% of the Phase 0 baseline (277 events/s), so at least 222 events/s.
Measured with
[`tests/bench/pipeline_bench.py`](https://github.com/miteshpant/Logforge/blob/main/tests/bench/pipeline_bench.py)
on the same 4-vCPU stack. It runs a typical 10-processor pipeline (kv,
2 × convert, lowercase, rename, set, script, mask, conditional set,
remove) as the tenant's default. Unlike the Phase 3 run, this benchmark
times **end to end**: 5,000 events are posted and the clock stops when all
5,000 are stored in `logs_raw_mt`. Raw results of the 5-round run:
[`2026-11-19-pipelines.json`](./2026-11-19-pipelines.json).

| Measurement | Without a pipeline | With the 10-processor pipeline |
|---|---|---|
| In process: the pipeline alone, per event | — | 21–22 µs |
| Smart-ingestion stage per 1,000-event batch (the API's own timing log) | ~114 ms | ~158 ms (+44 µs per event) |
| End to end, run 1 (3 rounds) | 1,996 / 1,712 / 334 events/s | 1,458 / 437 / 452 events/s |
| End to end, run 2 (5 rounds) | 328 / 329 / 338 / 338 / 335 events/s | 331 / 437 / 462 / 1,650 / 326 events/s |

**Result: criterion met.** Every run with the pipeline (8 of 8) stored at
least 326 events/s, above the 222 events/s floor and above the Phase 0
baseline itself.

**What the end-to-end numbers can't show.** On this shared single-node
stack, whole runs drop several-fold at random to a ceiling of about
330 events/s, with or without the pipeline. In run 2 every run without a
pipeline landed in that slow phase, while one run with the pipeline did
not, so comparing medians or best runs between the sides would mostly
measure the noise. The cost of the pipeline itself comes from the API's
own per-batch timing: about 44 µs per event. That is about 7% of the
~590 µs an event costs end to end when the stack is in its fast phase.

The 44 µs is the processors (22 µs) plus the runner (stats per step, a
snapshot of each routed event for the dead-letter queue), plus more fields
for normalisation to handle. The likely cause of the slow phase, quota
counters updated by a ClickHouse mutation on every request, is tracked in
[ROADMAP.md](../ROADMAP.md).

## Search-time extraction: 2026-11-19

Phase 5 acceptance: search-time extraction on 10 M rows must complete
within 2× the cost of the same query on an ingest-time field. Measured with
[`tests/bench/extraction_bench.py`](https://github.com/miteshpant/Logforge/blob/main/tests/bench/extraction_bench.py)
on the same 4-vCPU stack. The benchmark tenant held 10,000,000 rows over 7
days, and each query counted `region = "eu-west-1"` (about 3.2 M rows) over
all of them, once from the stored `attrs.region` and once extracted at query
time. Medians of 7 runs, server time; raw results:
[`2026-11-19-extraction.json`](./2026-11-19-extraction.json).

| Search-time stage | Ingest-time field | Search-time | Ratio | Same answer |
|---|---|---|---|---|
| `rex field=attrs "\"region\":\"(?<region>[^\"]+)\""` | 622 ms | 738 ms | **1.19×** | yes |
| `parse field=attrs "\"region\":\"*\"" as region` | 613 ms | 748 ms | **1.22×** | yes |
| `json field=attrs "region" as reg` | 608 ms | 398 ms | **0.66×** | yes |

**Result: criterion met** for all three. The `json` extraction is faster
than the stored-field path, because the stored-field path also checks the
legacy envelope location (`JSONHas` + fallback).

Found by this benchmark, and fixed:
- a first run put `parse` at 2.02×, because its wildcards compiled to a
  lazy `(.*?)`, which is slow in RE2. Before a single-character delimiter
  it now compiles to `([^c]*)`, which matches the same text;
- the benchmark's own patterns exposed a LogforgeQL bug: `\"` inside a
  quoted pattern ended the string early.

## Analyst questions at 100 M rows: 2026-11-19

Phase 6 acceptance: a published set of 30 analyst questions
([`tests/eval/analytics/questions.yml`](https://github.com/miteshpant/Logforge/blob/main/tests/eval/analytics/questions.yml))
must each be answerable in one query, and their p95 latency must stay within
the Phase 0 targets at 100 M rows. Phase 0 set no number. Its baseline,
"well under a second" (p95 117–311 ms at 10 M rows), is the bar used here.

- **Answerable in one query: met.** Each question is one LogforgeQL query.
  `tests/test_analyst_questions_live.py` seeds a week of auth, HTTP and DNS
  events and three lookup tables, and checks every answer against the same
  answer computed in Python. All 30 match. It runs in CI.
- **Latency at 100 M rows: not met.** Measured with
  [`tests/bench/analytics_bench.py`](https://github.com/miteshpant/Logforge/blob/main/tests/bench/analytics_bench.py)
  on the same 4-vCPU single-node stack. The benchmark tenant held
  99,999,668 events in the last 7 days, and every question covered all
  of them. Each question ran 10 times through `POST /v1/query/logql`; p50
  and p95 are over runs 2–10 (the first run took about as long). Raw
  results: [`2026-11-19-analytics.json`](./2026-11-19-analytics.json).
  - **p95 under 1 s: 8 of 30.** These are the counts over service, level
    and status (answered from the hourly counts), plus questions that only
    read stored columns.
  - **1–2.5 s: 7.**
  - **2.5–5 s: 2.**
  - **Over 5 s: 13.** Every one of these reads `attrs` (the JSON of event
    attributes) for every event in the week.

| # | Question | p50 | p95 | Rows read | Hourly counts |
|---|---|---|---|---|---|
| 01 | Top 10 source IPs by failed logins per hour this week | 9.10 s | 11.19 s | 100.8 M |  |
| 02 | Errors per service | 122 ms | 133 ms | 1.3 M | yes |
| 03 | Error rate per service | 847 ms | 912 ms | 100.8 M |  |
| 04 | p95 and p99 latency per service | 6.99 s | 7.34 s | 100.8 M |  |
| 05 | The 5 slowest endpoints at p95 with at least 50 requests | 11.11 s | 11.76 s | 100.8 M |  |
| 06 | HTTP requests per day by status class | 208 ms | 224 ms | 2.0 M | yes |
| 07 | Users with more than 3 failed logins and no successful login | 15.72 s | 16.26 s | 201.6 M |  |
| 08 | Distinct users who logged in, per country | 8.88 s | 9.14 s | 100.8 M |  |
| 09 | How many users logged in from more than 2 countries | 8.91 s | 9.30 s | 100.8 M |  |
| 10 | The 5 hosts with the most errors, with their share | 178 ms | 233 ms | 11.0 M |  |
| 11 | The 3 rarest user agents | 6.05 s | 6.46 s | 100.8 M |  |
| 12 | Failed logins from outside the internal network, by source IP | 3.97 s | 4.14 s | 100.7 M |  |
| 13 | Activity from blocklisted IPs | 1.08 s | 1.46 s | 92.4 M |  |
| 14 | Events per department | 7.23 s | 8.37 s | 100.7 M |  |
| 15 | Errors per team that owns the host | 990 ms | 1.03 s | 11.0 M |  |
| 16 | Daily event volume per service | 139 ms | 147 ms | 3.4 M | yes |
| 17 | The busiest hour of the day | 856 ms | 894 ms | 100.7 M |  |
| 18 | The 10 users who transferred the most bytes | 7.03 s | 7.38 s | 100.7 M |  |
| 19 | Average response size and request count by HTTP method | 10.19 s | 10.54 s | 100.7 M |  |
| 20 | The latest event from each host | 3.25 s | 3.46 s | 4.0 M |  |
| 21 | First and last seen, and event count, per user | 1.11 s | 1.14 s | 100.7 M |  |
| 22 | Requests slower than 3x their service's average, per service | 14.93 s | 15.51 s | 201.4 M |  |
| 23 | Server errors per endpoint, with ids normalised | 1.53 s | 1.66 s | 100.7 M |  |
| 24 | The 5 most queried DNS names | 1.05 s | 1.36 s | 15.4 M |  |
| 25 | How many DNS names were queried by only one host | 1.08 s | 1.14 s | 15.4 M |  |
| 26 | HTTP status code distribution | 144 ms | 164 ms | 1.1 M | yes |
| 27 | Distinct source IPs every 6 hours | 2.08 s | 2.15 s | 100.7 M |  |
| 28 | Latency histogram in 250 ms buckets | 13.46 s | 13.80 s | 100.7 M |  |
| 29 | User and host pairs with 5 or more failed logins | 8.29 s | 8.58 s | 100.6 M |  |
| 30 | Each service's share of all errors | 291 ms | 323 ms | 2.4 M | yes |

**Why the slow ones are slow.** Reading one `attrs` key from 100 M events
means decompressing and scanning about 15 GB of JSON. On 4 vCPUs that alone
takes about 3 s (`visitParamExtractString`, the cheapest ClickHouse JSON
read) to 5 s (a full JSON parse). Questions that read several keys, or read
them twice, cost more. The questions that meet the bar read stored columns
or the hourly counts. Closing the gap needs frequently queried attributes
stored as columns (typed, materialized from `attrs`). That is storage work
(Phase 12), and it is tracked in the [roadmap](../ROADMAP.md).

Found by this benchmark, and fixed (the numbers above are after the fixes):

- an `attrs` field read every row's JSON twice (`JSONHas`, then the
  value). It is now read once, with the legacy location as a fallback:
  attrs questions got 15–35% faster;
- `eventstats` used a window function, which sorted all 100 M rows by the
  partition. It now computes the group values with `GROUP BY` and joins
  them back. Question 22: 36 s → 15 s;
- `dedup` sorted every event to keep the latest per key. It now finds each
  key's latest time first. Question 20: 11.6 s → 3.3 s through the API
  (1.7 s in ClickHouse);
- `not cidrmatch(...)` never matched anything (operator precedence in the
  generated SQL). This was found by the answer checks;
- a query over the 30 s limit returned a bare 500. It is now a 504 that
  says how to narrow the query.

## Content pack walkthrough: 2026-11-19

`scripts/pack_walkthrough.py` installs the Linux pack, creates an ingest
key, runs Vector 0.41.1 in Docker with
`packages/shipper-recipes/vector/vector-linux-pack.toml` on a scratch
`/var/log`, appends 11 auth.log and 5 audit.log lines and waits for the
results through the API. Single node, 4 vCPU. Results:
[`2026-11-19-pack-walkthrough.json`](./2026-11-19-pack-walkthrough.json).

| Seconds after the install | |
|---|---|
| 0.3 | ingest key created, Vector started |
| 4.8 | all 16 events searchable and parsed |
| 5.0 | the pack's dashboard: 7 of 7 panels show data |
| 10.6 | all 4 rules enabled, each with alerts for the new lines |

The time is the system's part of the 15-minute target in
[docs/packs.md](../packs.md); a person's time is not included.

## History

| Date | Setup | Ingest (events/s) | Ingest → searchable | Slowest query p95 @ 10 M |
|---|---|---|---|---|
| 2026-11-17 | single node, 4 vCPU | 277 | 36.8 s | 311 ms (full-text search) |
| 2026-11-18 | single node, 4 vCPU; enrichment, in process | +12 µs per event with 100k indicators (request acceptance only was timed live; see the correction) | — | — |
| 2026-11-19 | single node, 4 vCPU; 10-processor pipeline, end to end | 326–1,650 with the pipeline (8 runs; Phase 0 floor 222) | — | — |
| 2026-11-19 | single node, 4 vCPU; search-time extraction, 10 M rows | — | — | rex 1.19×, parse 1.22×, json 0.66× of the ingest-time field |
| 2026-11-19 | single node, 4 vCPU; 30 analyst questions, 100 M rows, 7 days | — | — | p95 < 1 s for 8 of 30 (counts and stored columns); 6–16 s for the 13 that read `attrs` over all 100 M events |
