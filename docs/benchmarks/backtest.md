# Backtest performance

`POST /v1/security/rules/{rule_id}/backtest` replays a rule over a tenant's
stored logs. A SQL prefilter compiled from the rule (`apps/api/sigma_sql.py`)
narrows what is read from `logs_raw_mt`; every match is then decided by the
detection engine itself (`detection_replay`), so count and correlation rules
behave exactly as in the live path, with windows that span the whole range.

## Phase 1 acceptance: 7 days / 100M events in under 60 s

Measured 2026-11-17 on the single-node development stack (4 vCPU, 15 GB RAM,
ClickHouse 23.8 in Docker on the same host as the API).

Data: 100,000,000 synthetic rows over 7 days for one tenant (one every 6 ms;
786 MiB compressed). One row in 200 is a failed login (500k), grouped into
bursts from rotating external addresses; the rest are HTTP request events.
Generated with `INSERT ... SELECT ... FROM numbers(100000000)`; timed with
`scripts/bench_backtest.py`.

| Rule | Type | Events replayed | Alerts | Time | Peak RSS |
|---|---|---:|---:|---:|---:|
| `bf001-brute-force-login` | count() >= 10 by src_ip / 5m | 500,000 | 50,000 | 20.1 s | 189 MB |
| `lf-c-password-spray` | value_count of user / 10m | 500,000 | 100,000 | 21.2 s | 194 MB |
| `lf-c-brute-force-then-success` | chained correlation (3 base rules) | 500,000 | 0 | 27.4 s | 193 MB |
| `lf-unix-reverse-shell` | single event, no matches | 0 | 0 | 5.1 s | 193 MB |

At 20M rows the same rules took 5.1 s, 6.4 s and 1.4 s, so time grows
linearly with rows scanned plus events replayed.

What the numbers depend on, honestly:

* **Selectivity.** The ClickHouse scan of 100M rows costs about 5 s; the
  rest is replaying the events the prefilter selects, roughly 30-45 µs per
  event in Python. A rule whose prefilter selects 5M events would take about
  3 minutes.
* **Rules that can't be narrowed.** The compiler widens what it can't express
  exactly (negations, regexes, event types the normalizer guesses), so a
  rule made only of those scans everything. 2 of the 289 shipped rules
  compile to no prefilter. The scan stops after `max_events` (default 2M,
  reported as `truncated`).
* **Memory** stays bounded: rows are read in 6-hour chunks and correlation
  state is capped (see `apps/api/correlation.py`).

## Prefilter parity

The prefilter must select a superset of what the engine matches, or a
backtest would silently miss alerts. `scripts/check_backtest_parity.py`
checks every rule against a tenant's stored logs. On the development tenant
loaded with the evaluation corpus (24 attack scenarios + 2000 benign events,
4095 rows): 289 rules, 287 narrowed, 0 SQL errors, 0 engine matches missed by
the SQL (it selected 1686 rows where the engine matched 868).
