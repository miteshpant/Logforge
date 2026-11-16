# QA report: full-stack deploy and browser pass

*November 2026, `main` at `2b627a2`, run on a Linux host. This is a point-in-time
record. Open items are tracked in [ROADMAP.md](./ROADMAP.md); fixed items were
fixed in the same PR as this report.*

## What was tested

1. **Deploy.** A fresh `./deploy.sh` with no changes. It started ClickHouse,
   MinIO, Redpanda, Redis, the migrations job, the API and the tenant UI.
   `/health` reported every service healthy, and all six Kafka topics were
   created.
2. **README quick start**, run verbatim:
   - first-admin setup and login;
   - tenant creation;
   - single-log ingest, then a LogforgeQL query.
3. **Demo data.** One tenant was seeded with an hour of synthetic telemetry
   across 5 services:
   - about 1,800 logs;
   - 480 trace spans (120 traces);
   - 240 metric points.

   Rows were then checked directly in ClickHouse (`logs_raw_mt`,
   `logs_normalized_mt`, `traces_mt`, `metrics_mt`).
4. **Browser pass.** Headless Chromium at 1440×900 logged in as a
   `tenant_admin` and visited **all 28 tenant-UI routes**. On each page it
   recorded console errors, uncaught exceptions and failed API calls, and took
   a screenshot. A subset of the screenshots is in the
   [README](../README.md#screenshots).

**Not covered:**
- the admin UI (port 3002), which `deploy.sh` doesn't start;
- alert notification delivery;
- Sigma *matches*: the 233 active rules were evaluated against every batch, but
  the synthetic logs contain no attack patterns.

## Result summary

| Area | Result |
| --- | --- |
| Deploy | ✅ After working around two environment issues (below) |
| Auth: setup, login, tenants, users, roles | ✅ |
| Log ingest → Kafka → ClickHouse → query | ✅ End to end, about 1 s from ingest to queryable |
| Traces → service map, APM, Apdex | ✅ After the duration fix (below) |
| Metrics ingest | ✅ After the KeyError fix (below) |
| Sigma detection | ✅ 233 rules evaluated per batch |
| UI: 28 routes | ✅ All render; no page crashes or uncaught exceptions |
| UI API calls | ⚠️ A burst of 401s on every full page load, plus 4 endpoint mismatches |

## Bugs fixed in this PR

| # | Bug | Effect | Fix |
| --- | --- | --- | --- |
| F1 | `ObservabilityDAO.save_metric` read `labels`, `service_name` and `resource` with `[...]`, but the public `MetricRequest` schema doesn't define them | **Every** metric sent per the documented schema failed with `KeyError` while the endpoint still returned `202` | Default the optional fields. Test: `tests/test_metric_save_optional_fields.py` |
| F2 | `ingest_trace_span` ignored the client's `duration_ms` and only derived the duration from `end_time` | Spans without `end_time` were stored as 0 ms: trace list, APM latency, P95 and Apdex all read 0 | Use `duration_ms` and still prefer `end_time - start_time`. Test: `tests/test_span_duration_ingest.py` |
| F3 | `CORSMiddleware` was registered first, so it was the *innermost* layer | 401, 403 and 429 responses from the auth and rate-limit middleware had no CORS headers. The browser reported an opaque CORS error, so the UI couldn't tell it was a 401 | Register CORS last, making it outermost. Test: `tests/test_cors_outermost.py` |

The README quick start was corrected too. Its LogforgeQL example
(`error | where …`) returned nothing, because a leading bare word is a
full-text search on the message. Two steps were also missing: a tenant user and
user activation, without which nobody can log into the tenant UI.

## Findings and resolution

The issues below were found in this QA run and fixed in a follow-up PR, one
commit each, with a regression test. Every row was re-verified on the
running stack. A full re-run of the browser pass afterwards recorded
**0 failed API calls, 0 page errors and 0 crashes across all 28 routes**.
The first run recorded 63 failed calls.

| # | Finding | Resolution |
| --- | --- | --- |
| 1 | `minio/minio` removed from Docker Hub; `./deploy.sh` failed on every fresh machine | ✅ MinIO built from official source (`infra/docker/minio/Dockerfile`) |
| 2 | Linux: UI restart loop with `EACCES` on `/app/.next` | ✅ `/app/.next` is a container-owned volume |
| 3 | "Could not read migration history" on every start; every migration reported pending | ✅ The runner reads the shell runner's history format |
| 4 | Alert rules never evaluated on ingest (`get_alert_rules_for_customer` missing) | ✅ Method added; a pattern rule now fires end to end |
| 5–6 | Rate limiting failed open, the auth cache never wrote, and **the login brute-force throttle never tripped** (12 wrong passwords, all 401) | ✅ `RedisManager.client` / `incr` / `set(ex=)`; the throttle now returns 429 after 5 failures |
| 7 | Login succeeded for `pending` users whose every request then failed | ✅ Login returns 403 with the account status |
| 8 | LogforgeQL `* \| where …` searched for a literal `*` | ✅ A leading `*` means match-all |
| 9 | 59 unauthenticated API calls (401) on full page loads | ✅ The API client restores auth before every request; a route guard keeps pages from mounting without a session |
| 10 | Login errors unclear, and a failed login left a half-established session | ✅ The real server message is shown and state is cleared. *Correction:* the error banner did render; the original report was wrong to call it silent |
| 11a | Costs page called a platform-admin-only endpoint (403) | ✅ Dead call removed |
| 11b | Compliance: unsupported "SOC2" gave a 500, and the Frameworks tab was always empty | ✅ 400 for bad input; the tab shows the four supported frameworks |
| 11c | System Intelligence: 8 failing queries | ✅ Derived fields computed from `attrs`, the aggregate endpoint returns its rows, and UI field names fixed |
| 12 | Metrics Explorer "No data" | ➖ **Not a code bug.** The QA data used unregistered metric names (`cpu.utilization`). With canonical names (`response_time`, `cpu_usage`, …) the explorer charts correctly. The UI gives no hint about non-canonical names; see ROADMAP |
| 13 | SIEM and Detection Rules pages overflow at 1440 px | ✅ `min-w-0` on the layout column; the rules table scrolls |
| 14 | Plan badge showed the tenant type, not the subscription tier | ✅ Badge reads `/v1/tenants/{id}/subscription` |

Also found while fixing these, and fixed in the same PR:
- metric ingestion and trace durations (F1, F2 above);
- the `/v1/query/aggregate` endpoint dropped grouped rows;
- `attrs.<key>` filters missed caller attributes nested in the stored envelope;
- there was no route guard (deep links rendered an empty shell);
- `ApiClient` ignored FastAPI's `detail`, so the UI showed "HTTP 4xx" instead of the server's message.

## Reproducing

```bash
./deploy.sh
# then follow README "Quick start" steps 2-4
```

The browser pass used Playwright: log in through `[data-testid=email-input]`,
`[data-testid=password-input]` and `[data-testid=login-button]`, then visit
each route under `apps/ui/app/`, recording `console` errors, `pageerror`s, and
responses with status ≥ 400 from `:7080`.
