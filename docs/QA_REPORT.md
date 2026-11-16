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

## Open issues found (not fixed here)

### Deploy and setup
1. ✅ *Fixed:* **`minio/minio` is gone from Docker Hub.** The pinned tag and
   `latest` both returned "not found", so `./deploy.sh` failed on every fresh
   machine. MinIO is now built from official source
   (`infra/docker/minio/Dockerfile`).
2. **Linux bind-mount permissions.** The UI container runs as uid 1000 and
   writes `.next/` into the bind-mounted `apps/ui`. On hosts where the user
   isn't uid 1000 the UI restart-loops with `EACCES`. A workaround is in the
   README.
3. **Startup warning:** "Could not read migration history". `schema_migrations`
   lacks the `version`, `checksum` and `success` columns the API queries.

### Backend
4. **Alert rules are not evaluated on ingest.** On every batch the log shows:
   `'AlertService' object has no attribute 'get_alert_rules_for_customer'`
   (`events/management/cache/alert_rule_cache.py`).
5. **Rate limiting fails open.** `'RedisManager' object has no attribute
   'incr'`, so per-tenant rate limits are never enforced.
6. **The auth cache never writes.** `RedisManager.set()` doesn't accept `ex=`.
7. **Login succeeds for `pending` users**, but every later request returns
   `401 Invalid or expired session`. Login should either reject pending users
   or accept their sessions.
8. **LogforgeQL `*` is not a wildcard.** `* | where …` searches for a literal
   `*`.

### Tenant UI
9. **Every full page load fires API calls before auth state is restored from
   `localStorage`.** They go out without `Authorization`, get 401s, and the UI
   then calls `/v1/auth/refresh`; later calls succeed. There were 59
   avoidable 401s across 28 routes. Gate data fetching on auth hydration.
10. **A failed login shows no message.** For example, a platform admin logging
    into the tenant UI (tenant `platform` → 404) stays on the login page with
    only a console error.
11. **Endpoint mismatches:**
    - *Settings → Costs* calls `/v1/analytics/usage-trends`, which is
      platform-admin only (403).
    - *Settings → Compliance* omits the required `compliance_framework`,
      `period_start` and `period_end` (500).
    - *System Intelligence* (`/dashboards/system`) sends bodies that
      `/v1/query/advanced` and `/timeseries` reject (400).
12. **The Metrics Explorer shows "No data"** even when `metrics_mt` holds points
    for the selected range.
13. **The SIEM and Detection Rules pages overflow horizontally** at 1440 px:
    the header, filters and "Create Rule" button are cut off.
14. **The header plan badge shows the tenant *type*** ("startup") rather than
    the current subscription tier.

## Reproducing

```bash
./deploy.sh                       # see the README for the MinIO and Linux workarounds
# then follow README "Quick start" steps 2-4
```

The browser pass used Playwright: log in through `[data-testid=email-input]`,
`[data-testid=password-input]` and `[data-testid=login-button]`, then visit
each route under `apps/ui/app/`, recording `console` errors, `pageerror`s, and
responses with status ≥ 400 from `:7080`.
