# Logforge — Enhancement Backlog (LF series)

> Source of truth for engineering state. IDs are stable; never renumber.
> Companion map: [`docs/ARCHITECTURE_MINDMAP.md`](./ARCHITECTURE_MINDMAP.md)
>
> **Audit date:** 2026-08-16. Verified against the **running stack**
> (API `localhost:7080`, UI `localhost:3000`, ClickHouse `localhost:8124`,
> Redpanda, MinIO, Redis) using a live authenticated session for tenant
> `e651bdc5-64da-4ebb-a7ea-ad742094c2b1`.
>
> ### Note on the prior ENH-001..051 backlog
> A previous audit produced tickets `ENH-001`–`ENH-051` in this same file. The
> **API-side** tickets were genuinely implemented — the remediation is visible in
> committed source (parameterised queries, Redis throttles, bounded ingest
> pipeline, DLQ, secret validation). The **UI-side** tickets `ENH-040`–`ENH-049`
> were marked `Done` **but the code was never changed**. Re-verified 2026-08-16:
> `ENH-043` lists six `Math.random()` sites with line numbers and ticks its
> acceptance criteria ✅ — all six are still present at those exact lines.
> `ENH-048` claims 107 type errors were fixed; `npx tsc --noEmit` still reports
> **exactly 107**. That file was also never committed to git.
>
> Those items are re-issued below as `LF-###` with reproduced evidence. **Do not
> trust a `Done` status in the ENH series for UI work without re-verifying.**

---

## Summary

| ID | Title | Workstream | Priority | Effort | Status |
|---|---|---|---|---|---|
| LF-001 | Health check always reports ClickHouse unhealthy (`KeyError: 0`) | WS-A | P0 | S | Backlog |
| LF-002 | 11 new ClickHouse connections per HTTP request | WS-A | P0 | L | Backlog |
| LF-003 | MITRE rules stored with empty `customer_id`; invisible to every tenant | WS-B | P0 | M | Backlog |
| LF-004 | MITRE loader is non-idempotent; table grows 286 rows every restart | WS-B | P0 | S | Backlog |
| LF-005 | 286 "MITRE rules" contain only 2 distinct detections | WS-B | P0 | XL | Backlog |
| LF-006 | Dashboard widgets render `Math.random()` instead of the working data API | WS-C | P0 | M | Backlog |
| LF-007 | Threat hunting fabricates campaigns and finding counts on failure | WS-C | P0 | S | Backlog |
| LF-008 | RBAC role save reports success when persistence fails | WS-C | P0 | S | Backlog |
| LF-009 | Sigma rule test returns invented match/confidence on failure | WS-C | P0 | S | Backlog |
| LF-010 | SIEM page assigns a random MITRE tactic to unmapped techniques | WS-C | P0 | S | Backlog |
| LF-011 | Live metrics page streams fabricated telemetry when SSE fails | WS-C | P0 | S | Backlog |
| LF-012 | `ServiceHealthMap` calls a 404 endpoint and always shows fake services | WS-C | P0 | S | Backlog |
| LF-013 | UI production build is broken: 107 type errors, gate enabled | WS-D | P0 | M | Backlog |
| LF-014 | `throw new ApiError(...)` on an interface — TypeError on session expiry | WS-D | P0 | S | Backlog |
| LF-015 | Refresh-token flow is dead; forced re-login every 8 hours | WS-D | P1 | M | Backlog |
| LF-016 | `/v1/security/sigma-rules` has no pagination; unbounded result set | WS-B | P1 | S | Backlog |
| LF-017 | `/v1/logs` has no time-range filter — full partition scan | WS-A | P1 | M | Backlog |
| LF-018 | Full-text search is `LIKE '%…%'` with no skip index | WS-A | P1 | M | Backlog |
| LF-019 | `multi_metric_anomalies_mt` missing; anomaly history 500s | WS-A | P1 | S | Backlog |
| LF-020 | Raw DB exceptions leak schema internals to API clients | WS-A | P1 | S | Backlog |
| LF-021 | 13 hardcoded wildcard CORS headers bypass the allowlist | WS-D | P1 | S | Backlog |
| LF-022 | LogQL requires explicit time range or 400s; no default window | WS-E | P1 | S | Backlog |
| LF-023 | LogforgeQL has no UI surface at all | WS-E | P1 | M | Backlog |
| LF-024 | Logs page has no live tail | WS-E | P1 | M | Backlog |
| LF-025 | Logs page hardcodes `limit: 500`, no pagination | WS-E | P1 | S | Backlog |
| LF-026 | Delete 4 dead modules containing mock implementations (2,712 LOC) | WS-D | P2 | S | Backlog |
| LF-027 | Delete 12 unused API SDK modules referencing ~130 phantom endpoints | WS-D | P2 | M | Backlog |
| LF-028 | Costs page silently swallows a 403 on `/v1/analytics/usage-trends` | WS-C | P2 | S | Backlog |
| LF-029 | UI Docker image runs `npm run dev` in production | WS-D | P2 | S | Backlog |
| LF-030 | `logs_raw_mt` deployed without compression codecs | WS-A | P2 | S | Backlog |
| LF-031 | No S3/MinIO cold tiering despite configured backend | WS-A | P2 | L | Backlog |
| LF-032 | 6 tenant-ID interpolation sites in NLQ SQL | WS-D | P2 | S | Backlog |
| LF-033 | 4 tenant-router tests failing (403 vs 404 on `platform`) | WS-D | P2 | S | Backlog |
| LF-034 | Query responses duplicate the whole log inside `attrs` | WS-A | P2 | S | Backlog |
| LF-035 | No alert notification delivery — all channels are stubs | WS-F | P1 | L | Backlog |
| LF-036 | No log ingestion agent / shipper integration path | WS-F | P1 | L | Backlog |
| LF-037 | No onboarding flow: empty tenant has no path to first data | WS-F | P1 | M | Backlog |
| LF-038 | No saved-search alerting (search → monitor) | WS-F | P2 | M | Backlog |
| LF-039 | Dashboard widget data endpoint 404s for built-in dashboards | WS-C | P2 | S | Backlog |
| LF-040 | No MITRE ATT&CK coverage endpoint despite UI expecting one | WS-B | P2 | M | Backlog |

**Priority mix:** 14 × P0, 13 × P1, 13 × P2.

---

## Workstreams (parallel-safe)

Six workstreams, partitioned so that **no two touch the same file**. See the
file-ownership matrix at the bottom before starting.

| WS | Theme | Owner profile | Tickets |
|---|---|---|---|
| **WS-A** | Data layer, storage & query performance | Backend / ClickHouse | LF-001, 002, 017, 018, 019, 020, 030, 031, 034 |
| **WS-B** | Detection content & SIEM correctness | Security engineer | LF-003, 004, 005, 016, 040 |
| **WS-C** | UI truthfulness — eliminate fabricated data | Frontend | LF-006..012, 028, 039 |
| **WS-D** | Build health, auth plumbing & dead code | Full-stack | LF-013, 014, 015, 021, 026, 027, 029, 032, 033 |
| **WS-E** | Search & query UX | Frontend + backend | LF-022, 023, 024, 025 |
| **WS-F** | Competitive gaps: alerting delivery, ingest agents, onboarding | Product engineer | LF-035, 036, 037, 038 |

---

# WS-A — Data layer, storage & query performance

### [LF-001] Health check always reports ClickHouse unhealthy (`KeyError: 0`)
- **Workstream:** WS-A  **Type:** Bug  **Priority:** P0  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/api/services/health_service.py`
- **Evidence:** `GET /health` on the running stack returns
  `{"status":"degraded","services":{"database":"unhealthy","clickhouse":"unhealthy",...}}`
  while ClickHouse is demonstrably healthy (all queries succeed).
  `health_service.py:105-108` does:
  ```python
  result = await db.fetch_one("SELECT 1 as health_check")
  if not result or result[0] != 1:
      return {"status": "unhealthy", ...}
  ```
  but `DatabaseLayer.fetch_one` (`database_layer.py:439-442`) returns a **dict**.
  Reproduced inside the container:
  ```
  fetch_one returns: <class 'dict'> {'health_check': 1}
  r[0] RAISES: KeyError 0
  ```
  The `KeyError` is caught by the broad `except` at `health_service.py:71-75`,
  which sets `unhealthy`.
- **Problem:** `/health/ready` returns 503 whenever status is `unhealthy`. Under
  Kubernetes this fails the readiness probe and **removes healthy pods from
  service** — a self-inflicted outage. It also trains operators to ignore the
  health endpoint, which is the one signal that must never cry wolf.
- **Implementation spec:**
  1. In `_check_clickhouse_health`, replace `result[0] != 1` with a dict access:
     ```python
     if not result or result.get("health_check") != 1:
     ```
  2. Audit every other `fetch_one(...)` consumer for positional indexing:
     `grep -rn "fetch_one" apps/api | grep -v __pycache__` and check each call
     site treats the result as a mapping.
  3. Narrow the `except Exception` blocks in `get_overall_health` so a coding
     error (KeyError/TypeError) is **not** silently reported as a service
     outage — log with `exc_info` and re-raise, or report a distinct
     `"check_error"` status so a bug is distinguishable from a real outage.
- **Acceptance criteria:**
  - `GET /health` returns `"status":"healthy"` with `clickhouse:"healthy"` on the
    running stack.
  - `GET /health/ready` returns 200.
  - A unit test asserts `_check_clickhouse_health` passes when `fetch_one`
    returns `{"health_check": 1}` and fails when it returns `{}` or `None`.
  - A test asserts a `KeyError` inside a check does not surface as `unhealthy`.
- **Dependencies / blast radius:** Isolated to `health_service.py`. No schema or
  API-contract change.

---

### [LF-002] 11 new ClickHouse connections per HTTP request
- **Workstream:** WS-A  **Type:** Performance / Tech-debt  **Priority:** P0  **Effort:** L  **Risk:** Med
- **Status:** Backlog
- **Affected files:** `apps/api/database_layer.py`, `apps/api/dao/*.py`,
  `apps/api/services/enterprise_service.py`, `apps/api/routers/enterprise_api.py`,
  `apps/api/utils/connection_pool.py`
- **Evidence:** Measured on the running stack — counting
  `"ClickHouse client initialized"` log lines before and after a single request:
  ```
  clients created by ONE /v1/logs request: 11
  ```
  Cause: `DatabaseLayer.__init__` (`database_layer.py:145-173`) calls
  `clickhouse_connect.get_client(...)` **and** `_ensure_tables_exist()` (DDL) on
  every construction. DAOs are constructed per request, and
  `enterprise_api.py` constructs `EnterpriseService()` inside **every single
  handler** (lines 150, 163, 176, 190, 203, 217, 230, 244, 257, 271, 285, 298,
  316, 328, 341, 354…).
  Measured latency on an essentially **empty** dataset:
  | Endpoint | avg |
  |---|---|
  | `/v1/logs?limit=10` | 96 ms |
  | `/v1/dashboards` | 134 ms |
  | `/v1/enterprise/rbac/roles` | 142 ms |
  | `/v1/observability/apm/overview` | 182 ms |
- **Problem:** Connection setup dominates latency before any real data exists,
  and each connection also issues `CREATE TABLE IF NOT EXISTS` DDL. This caps
  throughput far below the hardware, exhausts ClickHouse's connection limit
  under concurrency, and makes p99 latency unpredictable. Datadog/Splunk serve
  comparable list endpoints in single-digit ms.
- **Implementation spec:**
  1. **Pool the client.** `apps/api/utils/connection_pool.py` already exists and
     is initialised at startup (`dependencies.py:504-510`). Change
     `DatabaseLayer.__init__` to acquire a shared client from that pool keyed by
     connection parameters, instead of calling `get_client()` directly. Keep the
     service-credential validation exactly as is — it is a security control.
  2. **Stop DDL on every construction.** `_ensure_tables_exist()` must run at
     most once per process. Guard with a module-level
     `_TABLES_ENSURED: set[str]` keyed by service name, and default
     `ALLOW_RUNTIME_DDL=false` in `infra/docker/compose.yml` now that the
     `clickhouse-migrations` service owns schema.
  3. **Inject services, don't construct per handler.** Give
     `enterprise_api.py` a module-level lazily-built singleton using the same
     PEP 562 `__getattr__` pattern already used in `routers/dashboard.py:27-39`
     and `routers/ingestion.py:39-51`. Apply to every router that does
     `XService()` inside a handler:
     `grep -rn "Service()" apps/api/routers/`.
  4. Add a regression test that counts client constructions across one request
     (monkeypatch `clickhouse_connect.get_client` with a counter) and asserts
     `<= 1`.
- **Acceptance criteria:**
  - One request to `/v1/logs` constructs **at most 1** ClickHouse client.
  - Median latency of `/v1/logs?limit=10` drops below 25 ms on the empty dataset.
  - No `CREATE TABLE` statements are issued during steady-state request serving.
  - Existing tenant-isolation tests (`tests/test_tenant_isolation.py`) still pass.
- **Dependencies / blast radius:** Touches the shared DB layer — highest-risk
  item in WS-A. Land behind a feature flag (`LOGFORGE_POOLED_DB=true`), verify,
  then remove the flag. Do this **before** LF-017/LF-018 so their benchmarks are
  not distorted by connection overhead.

---

### [LF-017] `/v1/logs` has no time-range filter — full partition scan
- **Workstream:** WS-A  **Type:** Performance  **Priority:** P1  **Effort:** M  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/api/routers/query.py` (`get_logs`, ~line 544)
- **Evidence:** `routers/query.py:544-588` accepts only `service`, `level`,
  `limit`, `offset`. The generated SQL is:
  ```sql
  SELECT ts, service, level, msg, host, trace_id, customer_id
  FROM logs_raw_mt
  WHERE customer_id = %(customer_id)s
  ORDER BY ts DESC
  LIMIT ... OFFSET ...
  ```
  There is no `ts` predicate. Table DDL (verified live):
  `PARTITION BY (customer_id, toYYYYMM(ts))`,
  `ORDER BY (customer_id, service, level, ts, host)`.
- **Problem:** Without a `ts` bound, ClickHouse must read **every monthly
  partition** for the tenant and sort before applying LIMIT. At 30-day retention
  and real volume this is a multi-partition scan for what the UI presents as
  "recent logs". This is the single most-used endpoint in the product.
- **Implementation spec:**
  1. Add `start_time: datetime = Query(None)` and `end_time: datetime = Query(None)`.
  2. Default to a bounded relative window when absent — **`now() - 1h` to `now()`**
     (matching Loki/Datadog defaults). Never default to unbounded.
  3. Bind as parameters (`ts >= %(start_time)s AND ts <= %(end_time)s`),
     consistent with the existing ENH-003 parameterisation.
  4. Enforce a maximum window (`LOGFORGE_MAX_QUERY_WINDOW_DAYS`, default 31) and
     return 400 with a clear message when exceeded.
  5. Return the effective window in the response so the UI can display
     "showing last 1 hour".
  6. Update `apps/ui/app/observability/logs/page.tsx` to pass the global time
     selector range — **coordinate with WS-E (LF-025), which owns that file.**
- **Acceptance criteria:**
  - Omitting the range returns the last hour and states so in the payload.
  - `EXPLAIN` shows partition pruning to the selected months.
  - Requesting > 31 days returns 400, not a slow success.
  - Tenant isolation is unchanged (`customer_id` still bound first).
- **Dependencies / blast radius:** API contract is additive/back-compatible
  except that unbounded queries now return 1h. Call it out in release notes.

---

### [LF-018] Full-text search is `LIKE '%…%'` with no skip index
- **Workstream:** WS-A  **Type:** Performance  **Priority:** P1  **Effort:** M  **Risk:** Med
- **Status:** Backlog
- **Affected files:** `apps/api/query_engine.py` (~line 529),
  `infra/docker/clickhouse/migrations/012_add_msg_tokenbf_index.sql` (new)
- **Evidence:** `query_engine.py:529-531`:
  ```python
  if query.text_search:
      params["_text_search"] = f"%{query.text_search}%"
      where_conditions.append("msg LIKE %(_text_search)s")
  ```
  Live check of skip indexes returns **empty**:
  ```
  SELECT name, type_full FROM system.data_skipping_indices WHERE table='logs_raw_mt'
  -- (0 rows)
  ```
- **Problem:** Every keyword search decompresses and scans the full `msg` column
  for the time range. Log search *is* the product; Loki uses bloom filters,
  Elastic an inverted index, Splunk its own index. A leading-wildcard `LIKE` is
  the slowest possible implementation and will not survive a real customer.
- **Implementation spec:**
  1. New migration `012_add_msg_tokenbf_index.sql`:
     ```sql
     ALTER TABLE logs_raw_mt
       ADD INDEX IF NOT EXISTS idx_msg_tokens msg
       TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 4;
     ALTER TABLE logs_normalized_mt
       ADD INDEX IF NOT EXISTS idx_msg_tokens msg
       TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 4;
     ```
     Add `MATERIALIZE INDEX` guidance in the migration comments for backfill —
     it is expensive; document running it off-peak.
  2. In `query_engine.py`, when the search term is a plain token (no wildcard),
     emit `hasToken(msg, %(term)s)` which the bloom filter can serve, and fall
     back to `LIKE` only for substring/wildcard searches. Keep both
     parameterised.
  3. Add a `search_mode` field (`token` | `substring`) to the query model,
     defaulting to `token`, and surface it in the UI later (WS-E).
  4. Benchmark before/after on ≥ 1M rows generated with `data_generator.py`;
     record numbers in the ticket.
- **Acceptance criteria:**
  - `hasToken` path is used for single-token searches, verified by `EXPLAIN`.
  - Measured ≥ 5× reduction in rows read for a token search over 1M rows.
  - Substring search still returns correct results.
  - `tests/test_query_engine_sql_injection.py` still passes.
- **Dependencies / blast radius:** Schema migration on the hot table. Requires a
  migration + backfill window. Coordinate with LF-030 (same tables).

---

### [LF-019] `multi_metric_anomalies_mt` missing; anomaly history 500s
- **Workstream:** WS-A  **Type:** Bug  **Priority:** P1  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `infra/docker/clickhouse/migrations/013_multi_metric_anomalies.sql` (new),
  `apps/api/services/multi_metric_anomaly_detector.py`, `apps/api/routers/ai_api.py`
- **Evidence:** Live request:
  ```
  GET /v1/ai/anomalies/history -> HTTP 500
  {"detail":"Failed to get anomaly history: Query failed: ... Code: 60.
   DB::Exception: Table logforge.multi_metric_anomalies_mt does not exist. (UNKNOWN_TABLE)"}
  ```
  `SHOW TABLES LIKE '%anomal%'` returns only `anomaly_feedback_mt`.
- **Problem:** The anomaly-detection page's history view is permanently broken.
  Multi-metric anomaly detection can write nothing, so the feature is inert.
- **Implementation spec:**
  1. Recover the intended schema from the writer in
     `services/multi_metric_anomaly_detector.py` (find the INSERT column list)
     and from `anomaly_analyzer.py:685-686`.
  2. Add migration `013_multi_metric_anomalies.sql` creating
     `multi_metric_anomalies_mt` with `PARTITION BY (customer_id, toYYYYMM(detected_at))`,
     `ORDER BY (customer_id, detected_at, anomaly_id)`, and a TTL consistent
     with the other `_mt` tables.
  3. Add an integration test that detects an anomaly, then reads it back via
     `/v1/ai/anomalies/history`.
- **Acceptance criteria:**
  - `/v1/ai/anomalies/history` returns 200 with `[]` on an empty tenant.
  - After a detection run, the anomaly appears in history.
  - `tests/test_anomaly_history_endpoint.py` extended and passing.
- **Dependencies / blast radius:** Additive migration only.

---

### [LF-020] Raw DB exceptions leak schema internals to API clients
- **Workstream:** WS-A  **Type:** Security  **Priority:** P1  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/api/routers/ai_api.py`, `apps/api/routers/*.py`,
  new `apps/api/error_handling.py`
- **Evidence:** The LF-019 response body returns to an unprivileged client the
  database name, table name, ClickHouse version (`23.8.16.16`) and internal error
  code. The pattern `raise HTTPException(500, detail=f"...: {str(e)}")` appears
  throughout the routers — e.g. `routers/enterprise_api.py:154, 167, 180, 194,
  207, 221, 234, 248, 261, 275, 288, 302, 320, 332, 345, 358`.
- **Problem:** Version and schema disclosure is reconnaissance for an attacker
  and a finding in any SOC 2 / pen-test report.
- **Implementation spec:**
  1. Add `apps/api/error_handling.py` with a helper
     `internal_error(exc, correlation_id)` that logs the full exception
     server-side (structlog, with `exc_info`) and returns a generic client
     message plus the correlation ID.
  2. Register a global `Exception` handler in `main.py` returning
     `{"error": "Internal server error", "correlation_id": "..."}` with 500.
  3. Sweep routers replacing `detail=f"...{str(e)}"` with the helper. Keep 4xx
     validation messages verbatim — those are actionable and safe.
  4. Emit the correlation ID in the `X-Request-ID` response header so support can
     tie a user report to a log line.
- **Acceptance criteria:**
  - No 5xx response body contains a table name, database name or version string.
  - Server logs still contain the full exception and the same correlation ID.
  - A test asserts a forced DB error yields a generic body.
- **Dependencies / blast radius:** Touches many routers (mechanical). Conflicts
  with nothing else if WS-A lands it as a single sweep after LF-019.

---

### [LF-030] `logs_raw_mt` deployed without compression codecs
- **Workstream:** WS-A  **Type:** Cost  **Priority:** P2  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `infra/docker/clickhouse/migrations/014_logs_codecs.sql` (new),
  `infra/docker/clickhouse/init.sql`
- **Evidence:** `init.sql:16,19` specifies `msg String CODEC(ZSTD(3))` and
  `attrs String CODEC(ZSTD(3))`, but the **deployed** table has no codecs:
  ```
  SHOW CREATE TABLE logs_raw_mt
  -- `msg` String,   `attrs` String,   (no CODEC clauses)
  ```
  Live compression ratio on `logs_raw_mt` is **5.06×**, versus **16.47×** on
  `sigma_rules_mt` (highly repetitive). The migrations path diverged from
  `init.sql`.
- **Problem:** Storage is the dominant recurring cost in this category and the
  main lever a small company weighs against Splunk's ingest pricing. Leaving
  ZSTD off the two largest columns forfeits it.
- **Implementation spec:**
  1. Migration `014_logs_codecs.sql`:
     ```sql
     ALTER TABLE logs_raw_mt MODIFY COLUMN msg String CODEC(ZSTD(3));
     ALTER TABLE logs_raw_mt MODIFY COLUMN attrs String CODEC(ZSTD(3));
     -- same for logs_normalized_mt
     ```
     Note in comments that this applies to **new parts**; existing data needs
     `OPTIMIZE TABLE ... FINAL` (expensive — document, do not auto-run).
  2. Reconcile `init.sql`, `init_enhanced.sql` (which uses `LZ4HC`) and the
     migrations so there is exactly one source of truth. Delete the unused
     variants — `init_simple.sql` / `init_enhanced.sql` are drift risks.
  3. Record before/after `data_compressed_bytes` in the ticket.
- **Acceptance criteria:**
  - `SHOW CREATE TABLE logs_raw_mt` shows `CODEC(ZSTD(3))` on `msg` and `attrs`.
  - Compression ratio on newly ingested data improves measurably (target ≥ 8×).
  - Only one init SQL file remains authoritative.
- **Dependencies / blast radius:** Same tables as LF-018 — sequence them in one
  migration window.

---

### [LF-031] No S3/MinIO cold tiering despite configured backend
- **Workstream:** WS-A  **Type:** Cost  **Priority:** P2  **Effort:** L  **Risk:** Med
- **Status:** Backlog
- **Affected files:** `infra/docker/clickhouse/config.d/*.xml`,
  `apps/api/ttl_manager.py`, `apps/api/services/storage_service.py`
- **Evidence:** MinIO runs and is healthy; `storage_config.py:99` and
  `services/storage_service.py:211` configure MinIO credentials; `init.sql:8`
  says *"S3 storage policy will be configured via config.d/s3_storage.xml"* —
  that file does not exist (`config.d/` holds only `dedicated_storage.xml`,
  `fedramp_storage.xml`, `shared_storage.xml`). The live table has
  `TTL toDateTime(ts) + toIntervalDay(30)` — a **DELETE**, not a tier move.
- **Problem:** Data is deleted at 30 days rather than aged to cheap object
  storage. Competitors' central pitch to cost-sensitive buyers is long retention
  at low cost (Datadog Flex Logs, Splunk SmartStore, Loki's object-store-native
  design). Without tiering, Logforge either loses history or pays hot-disk prices.
- **Implementation spec:**
  1. Add a ClickHouse storage policy (`config.d/s3_storage.xml`) with a `hot`
     (local) and `cold` (S3/MinIO) volume.
  2. Change the TTL to a tier move plus a later delete:
     ```sql
     TTL toDateTime(ts) + toIntervalDay(7)  TO VOLUME 'cold',
         toDateTime(ts) + toIntervalDay(365) DELETE
     ```
     Make both windows per-tenant configurable through the existing retention
     policy tables (`retention_policies_mt`), which already exist.
  3. Wire `ttl_manager.py` to apply the per-tenant policy rather than a global
     constant.
  4. Verify archived-part queries still work through `/v1/storage/query-archive`.
- **Acceptance criteria:**
  - Parts older than the hot window appear on the `cold` disk
    (`system.parts.disk_name`).
  - Queries spanning both tiers return correct, complete results.
  - Per-tenant retention configured through the API is honoured.
- **Dependencies / blast radius:** Infrastructure + data movement. Needs a
  documented rollback (policy revert + `MOVE PARTITION` back). Do **after**
  LF-030 so moved parts are already well compressed. **Ask before running in any
  environment with real data.**

---

### [LF-034] Query responses duplicate the whole log inside `attrs`
- **Workstream:** WS-A  **Type:** Performance  **Priority:** P2  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/api/services/ingestion_service.py`,
  `apps/api/parsers.py`, `apps/api/query_engine.py`
- **Evidence:** Live `POST /v1/query/advanced` response for one ingested log:
  ```json
  {"ts":"...","service":"audit-test","level":"error",
   "msg":"audit-probe-... failed login for admin",
   "attrs":{"ts":"...","host":"","service":"audit-test","level":"error",
            "msg":"audit-probe-... failed login for admin",
            "attrs":{"source_format":"json",...},
            "customer_id":"e651bdc5-..."}}
  ```
  Every top-level field is repeated inside `attrs`, including `customer_id` and a
  nested `attrs`.
- **Problem:** Roughly doubles stored bytes for the largest column and doubles
  API response size — compounding the LF-030 cost issue and slowing every query.
  It also duplicates `customer_id` into a free-text blob, which is a data-hygiene
  concern for tenant scrubbing/GDPR erasure.
- **Implementation spec:**
  1. In the ingest normalisation path, populate `attrs` with **only** fields not
     already promoted to typed columns (`ts, host, service, level, msg, trace_id,
     span_id, status, src_ip, user_id, severity_num, facility, customer_id`).
  2. Keep parser provenance (`source_format`, `processing_version`,
     `parser_version`) — those are genuinely extra.
  3. Add a test asserting no promoted column name appears as an `attrs` key.
  4. Note: this changes stored shape going forward only; no backfill required
     because readers merge typed columns over `attrs`.
- **Acceptance criteria:**
  - Newly ingested logs have `attrs` containing only non-promoted fields.
  - `attrs` never contains a nested `attrs` or `customer_id`.
  - Query responses shrink measurably for the same logs.
- **Dependencies / blast radius:** Ingest write path — verify the SIEM/Sigma
  matcher (`high_performance_rule_matcher.py`) does not rely on the duplicated
  fields inside `attrs` before changing.

---

# WS-B — Detection content & SIEM correctness

### [LF-003] MITRE rules stored with empty `customer_id`; invisible to every tenant
- **Workstream:** WS-B  **Type:** Bug  **Priority:** P0  **Effort:** M  **Risk:** Med
- **Status:** Backlog
- **Affected files:** `apps/api/mitre_default_loader.py`,
  `apps/api/dao/security_dao.py`
- **Evidence:** `GET /v1/security/sigma-rules` returns `[]` on the live stack,
  yet the table holds **14,586 rows**. Root cause — three inconsistent sentinels:
  | Component | Location | Uses |
  |---|---|---|
  | Loader writes | `mitre_default_loader.py:135` | `"customer_id": None` |
  | Guard reads | `mitre_default_loader.py:246,262,343,389`, `security_dao.py:865,921` | `WHERE customer_id IS NULL` |
  | API reads | `security_dao.py:126` | `customer_id = %(customer_id)s OR customer_id = 'default'` |

  The column is **non-nullable `String`**, so `None` is coerced to `''`.
  Verified live:
  ```
  SELECT count() FROM sigma_rules_mt WHERE customer_id IS NULL  -> 0
  SELECT count() FROM sigma_rules_mt WHERE customer_id = ''     -> 14586
  ```
  `IS NULL` matches nothing; `'default'` matches nothing; so no tenant ever sees
  a rule. Note `/v1/security/threat-hunt/rules` **does** return them because it
  does not filter by tenant — proving the content is present but mis-scoped.
- **Problem:** The entire shipped detection library is invisible in the product's
  SIEM surface. A customer evaluating Logforge as a Splunk/Chronicle alternative
  opens Security → Rules and sees an empty list.
- **Implementation spec:**
  1. **Choose one sentinel: the literal string `'default'`** for
     platform-provided rules (it is already what the read path expects, and the
     column cannot hold NULL).
  2. Change `mitre_default_loader.py:135` to `"customer_id": "default"`.
  3. Replace every `WHERE customer_id IS NULL` with `WHERE customer_id = 'default'`
     in `mitre_default_loader.py` (lines 246, 262, 343, 389) and
     `security_dao.py` (lines 865, 921).
  4. One-off data migration `015_fix_default_rule_tenancy.sql` — must run
     **after** LF-004 dedupe:
     ```sql
     ALTER TABLE sigma_rules_mt UPDATE customer_id = 'default'
       WHERE customer_id = '' AND id LIKE 'mitre_default_%';
     ```
  5. Add a test asserting a fresh tenant sees the default rule set via
     `GET /v1/security/sigma-rules`, and that tenant-authored rules remain
     private to that tenant.
- **Acceptance criteria:**
  - `GET /v1/security/sigma-rules` returns the default rules for any tenant.
  - A rule created by tenant A is **not** visible to tenant B.
  - No `IS NULL` predicate remains against `sigma_rules_mt`.
  - `tests/test_tenant_isolation.py` still passes.
- **Dependencies / blast radius:** Do **LF-004 first** (dedupe), otherwise the
  UPDATE rewrites 14,586 rows unnecessarily. Touches the same files as LF-004
  and LF-005 — single owner, sequence LF-004 → LF-003 → LF-005.

---

### [LF-004] MITRE loader is non-idempotent; table grows 286 rows every restart
- **Workstream:** WS-B  **Type:** Bug  **Priority:** P0  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/api/mitre_default_loader.py`,
  `apps/api/dao/security_dao.py` (`should_load_mitre_rules`, ~line 846)
- **Evidence:** Live:
  ```
  SELECT count(), uniqExact(id) FROM sigma_rules_mt -> 14586, 286
  ```
  286 unique rules stored **~51 times each**. `should_load_mitre_rules`
  (`security_dao.py:862-875`) guards with:
  ```sql
  SELECT count() FROM sigma_rules_mt WHERE customer_id IS NULL AND id LIKE 'mitre_default_%'
  ```
  which returns 0 (LF-003), so `should_load = existing_rules < 286` is always
  true and the loader re-inserts on **every startup**. The per-rule existence
  check at `mitre_default_loader.py:262` has the same `IS NULL` defect.
  The engine is a `MergeTree`, not `ReplacingMergeTree`, so duplicates persist.
- **Problem:** Unbounded growth, and the duplication multiplies detection cost
  51× — see LF-005 evidence (~1 s to evaluate **one** log). It also inflates any
  "rules loaded" metric by 51×.
- **Implementation spec:**
  1. Fix the guard predicates as part of LF-003's sentinel change.
  2. Add dedupe migration `015a_dedupe_sigma_rules.sql`:
     ```sql
     -- keep the newest row per id
     CREATE TABLE sigma_rules_mt_dedup AS sigma_rules_mt;
     INSERT INTO sigma_rules_mt_dedup
       SELECT * FROM sigma_rules_mt ORDER BY updated_at DESC LIMIT 1 BY id;
     EXCHANGE TABLES sigma_rules_mt AND sigma_rules_mt_dedup;
     DROP TABLE sigma_rules_mt_dedup;
     ```
     (`EXCHANGE TABLES` is atomic on the Atomic database engine; verify engine
     first and fall back to `RENAME` if needed.)
  3. Change the table engine to `ReplacingMergeTree(updated_at)` with
     `ORDER BY (customer_id, id)` so re-insertion is idempotent by construction —
     defence in depth against the guard regressing again.
  4. Add a test that runs the loader twice and asserts the row count is
     unchanged.
- **Acceptance criteria:**
  - `count() == uniqExact(id)` for `sigma_rules_mt`.
  - Restarting the API twice does not change the row count.
  - Loader logs report the true number loaded (286, not 14,586).
- **Dependencies / blast radius:** Data migration on the rules table.
  **Ask before running** — take a backup of `sigma_rules_mt` first. Must land
  before LF-003.

---

### [LF-005] 286 "MITRE rules" contain only 2 distinct detections
- **Workstream:** WS-B  **Type:** Detection quality  **Priority:** P0  **Effort:** XL  **Risk:** Med
- **Status:** Backlog
- **Affected files:** `apps/api/mitre_default_loader.py`
  (`_generate_detection_logic`), `apps/api/content_pack_loader.py`,
  new `apps/api/content/rules/*.yml`, `tests/test_detection_rule_quality.py`
- **Evidence:** Live:
  ```
  SELECT uniqExact(rule_content) FROM sigma_rules_mt -> 13734 (differ only by metadata)
  SELECT DISTINCT JSONExtractRaw(rule_content,'detection') FROM sigma_rules_mt
  -- exactly 2 results:
  {"selection":{"process_name|contains":"suspicious"},"condition":"selection"}
  {"selection":{"event_id":[4688,4624,4625,1]},"condition":"selection"}
  ```
  Example — `mitre_default_t1110` ("Brute Force") detects
  `event_id IN [4688,4624,4625,1]`, i.e. every Windows logon, with no failure
  count or threshold. Live pipeline log: evaluating **1 log** against 14,586
  rules produced `0 detections` and took ~1 second (06:21:28 → 06:21:29).
- **Problem:** Two failure modes at once. `process_name contains "suspicious"`
  (the majority) matches essentially nothing — false negatives dressed as
  coverage. `event_id in [...]` fires on every benign logon — pure alert fatigue.
  The "286 MITRE techniques" number is marketing, not capability. For a product
  positioning against Splunk ES / Chronicle, unusable detection content is
  disqualifying, and shipping noise is worse than shipping nothing.
  *(This restates prior ENH-038/039, which are marked `Done` in the ENH series
  but are demonstrably not — the generated content is still live in the DB.)*
- **Implementation spec:**
  1. **Stop generating noise.** `_generate_detection_logic()` returns `None`
     when it cannot build a discriminating selection from the technique
     metadata. The loader counts those as `awaiting_content` and does **not**
     insert them. Coverage reporting must report curated rules only.
  2. **Adopt upstream Sigma.** Vendor the SigmaHQ ruleset (`rules/` subset
     relevant to the log sources Logforge actually ingests: syslog, nginx, CEF,
     OTLP, auth logs) as YAML under `apps/api/content/rules/`, with a pinned
     upstream commit and a `LICENSE` note (SigmaHQ is DRL 1.1). Load through the
     existing `content_pack_loader.py`.
  3. **Fixture-test every rule.** Extend `tests/test_detection_rule_quality.py`
     so each shipped rule must declare `true_positive` and `true_negative`
     fixture events and must match the former and not the latter. Fail CI on any
     rule without fixtures — this is the gate that prevents a regression to
     generated stubs.
  4. **Report coverage honestly.** Add a coverage calculation over *curated*
     rules mapped to ATT&CK technique IDs; surface via LF-040.
  5. Prioritise the intrusion stages that matter for the target customer:
     brute force / credential stuffing, suspicious auth from new geography,
     privilege escalation, web exploitation (nginx 4xx/5xx patterns), data
     exfiltration volume anomalies, and log-source silence.
- **Acceptance criteria:**
  - Every rule in `sigma_rules_mt` with `created_by='system'` has ≥ 1 passing
    true-positive and true-negative fixture.
  - No rule uses `process_name contains "suspicious"`.
  - No rule fires on a benign Windows 4624 logon fixture.
  - Reported ATT&CK coverage equals the number of techniques with fixture-tested
    rules — no padding.
  - Detection latency for a 100-log batch is under 200 ms after LF-004 dedupe.
- **Dependencies / blast radius:** Must follow LF-004 (dedupe) and LF-003
  (tenancy). Largest item in the backlog; split into (a) stop-the-noise,
  (b) vendor Sigma, (c) fixture harness, (d) coverage reporting.

---

### [LF-016] `/v1/security/sigma-rules` has no pagination; unbounded result set
- **Workstream:** WS-B  **Type:** Performance  **Priority:** P1  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/api/routers/security_api.py` (~line 256),
  `apps/api/dao/security_dao.py` (`get_sigma_rules`, ~line 120)
- **Evidence:** `security_api.py:256-259`:
  ```python
  @router.get("/sigma-rules")
  async def list_sigma_rules(customer_id: str = Header(..., alias="X-Customer-ID")) -> List[SigmaRuleResponse]:
  ```
  No `limit`/`offset` parameters — the UI's `?limit=3` is silently ignored
  (confirmed live: the query string had no effect). `security_dao.py:120-134`
  issues `SELECT * FROM sigma_rules_mt ... ORDER BY created_at DESC` with **no
  LIMIT**, loading every row into memory.
- **Problem:** Today it returns `[]` only because of LF-003. The moment LF-003
  lands, this endpoint serialises the full rule library on every page load. Note
  the contrast with `/v1/security/events`, which correctly declares
  `limit: int = Query(100, ge=1, le=1000)`.
- **Implementation spec:**
  1. Add `limit: int = Query(100, ge=1, le=1000)` and
     `offset: int = Query(0, ge=0)`; also `enabled: bool = Query(None)` and
     `severity: str = Query(None)` for filtering.
  2. Push LIMIT/OFFSET into the SQL in `get_sigma_rules`; return the standard
     envelope used elsewhere: `{"rules": [...], "total": N, "limit": L, "offset": O}`.
     **Note:** this changes the response from a bare array to an object —
     update `apps/ui/app/security/rules/page.tsx` and
     `apps/ui/app/security/siem/page.tsx`. **Coordinate with WS-C**, which owns
     those two files (LF-009, LF-010); agree the shape before either starts.
  3. Add a `total` count query (`SELECT count()` with the same predicate).
- **Acceptance criteria:**
  - `?limit=3` returns exactly 3 rules and a correct `total`.
  - No unbounded `SELECT *` remains against `sigma_rules_mt`.
  - Both UI pages render against the new envelope.
- **Dependencies / blast radius:** Response-shape change shared with WS-C.
  Land the API change and the two UI call sites in the same PR to avoid a
  broken intermediate state.

---

### [LF-040] No MITRE ATT&CK coverage endpoint despite UI expecting one
- **Workstream:** WS-B  **Type:** Feature  **Priority:** P2  **Effort:** M  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/api/routers/security_api.py`,
  `apps/api/services/security_service.py`, `apps/ui/lib/api/security.ts`
- **Evidence:** `apps/ui/lib/api/security.ts` references
  `/v1/security/mitre-coverage`; the OpenAPI spec (290 paths) has no such route.
  `apps/ui/app/security/siem/page.tsx` therefore computes coverage client-side
  from the rules list and falls back to a **random tactic** (LF-010).
- **Problem:** An ATT&CK coverage matrix is the standard artefact security buyers
  ask for. Computing it in the browser from a paginated list cannot be correct,
  and there is no server-side truth to report.
- **Implementation spec:**
  1. Add `GET /v1/security/mitre-coverage` returning, per tactic and technique:
     `{technique_id, technique_name, tactic, rule_count, enabled_rule_count,
       has_fixtures, last_detection_at}`.
  2. Compute from `sigma_rules_mt.mitre_techniques` (already an
     `Array(String)`) joined with the curated content metadata from LF-005.
  3. Report only fixture-tested rules as "covered"; expose stubs separately as
     `awaiting_content` so the number is honest.
  4. Cache for 5 minutes (`utils/api_cache.py` exists).
- **Acceptance criteria:**
  - Endpoint returns coverage grounded in the rules table, not a constant.
  - Techniques with no curated rule report `rule_count: 0`, never a random tactic.
  - SIEM page renders the matrix from this endpoint (WS-C owns the page edit —
    coordinate as with LF-016).
- **Dependencies / blast radius:** Depends on LF-005 for meaningful data.

---

# WS-C — UI truthfulness (eliminate fabricated data)

> Every ticket here violates the project's hard rule: **no mock data, no default
> data on failure.** All were previously filed as ENH-043 and marked `Done`
> without the code changing — re-verified present on 2026-08-16.
>
> **Shared principle for this workstream:** when data cannot be fetched, render
> an explicit error or "not available" state naming the failed endpoint. Never
> substitute invented values. An empty chart is honest; a plausible fake chart
> destroys trust in every other number in the product.

### [LF-006] Dashboard widgets render `Math.random()` instead of the working data API
- **Workstream:** WS-C  **Type:** Bug  **Priority:** P0  **Effort:** M  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/ui/app/dashboards/[id]/page.tsx`,
  `apps/ui/app/dashboards/[id]/edit/page.tsx`
- **Evidence:** `app/dashboards/[id]/page.tsx:71-121` defines
  `generateWidgetData(widget)` returning `Math.random()` values for
  `line_chart`, `area_chart`, `bar_chart`, `pie_chart`, `stat`, `gauge`, and a
  hardcoded endpoint table (`/api/users 45ms 1234 calls`…). It is invoked at
  lines **296** and **302** — including on a repeating
  `setInterval(..., widget.refresh_interval * 1000)`, so the fake data
  *animates*. The page fetches the dashboard definition
  (`apiClient.get('/v1/dashboards/${params.id}')`, line 338) but **never fetches
  widget data**. `edit/page.tsx:109,138` does the same for previews.

  **A working endpoint already exists.** Verified live:
  ```
  GET /v1/dashboards/security/data -> 200
  {"widgets":{"security_alerts_count":{"title":"Security Alerts (24h)",
    "type":"metric","data":{"value":0,"label":"count_all"},
    "execution_time_ms":8.75,...}, "failed_logins":{...}, ...}}
  ```
  It returns real query results per widget with execution timings.
- **Problem:** The dashboard — the product's primary surface — displays invented
  telemetry that refreshes to look live. A user cannot distinguish a healthy
  system from a broken one. This is the most damaging instance of the mock-data
  violation.
- **Implementation spec:**
  1. Delete `generateWidgetData` entirely from both files.
  2. Fetch `GET /v1/dashboards/{id}/data?start_time=&end_time=` once per
     dashboard, passing the global time range from `GlobalTimeSelector`.
  3. Map `response.widgets[widget.id].data` to each widget component. The shapes
     are: `metric` → `{value,label}`; `line_chart` → `{logs, aggregations.time_series}`;
     `bar_chart`/`pie_chart` → `{logs, aggregations}`; `table` → `{columns, rows}`.
  4. Drive refresh from `widget.refresh_interval` by re-calling the endpoint —
     never by regenerating values locally.
  5. Render three explicit states per widget: loading, error (show the failed
     endpoint and status), and empty ("no data in selected range").
  6. For the edit-page preview, either call the same endpoint for a saved widget
     or render a clearly-labelled **schematic placeholder** that is visually
     distinct (e.g. greyed, watermarked "preview — not live data") and contains
     no numeric values.
- **Acceptance criteria:**
  - `grep -n "Math.random" apps/ui/app/dashboards/` returns nothing.
  - Widgets show values that match `/v1/dashboards/{id}/data` for the same range.
  - With the API stopped, widgets show an error state — never numbers.
  - Changing the global time range refetches and changes the values.
- **Dependencies / blast radius:** Two files, owned solely by WS-C. Some
  dashboards will legitimately render empty against the near-empty dev dataset —
  that is the correct outcome. Use `data_generator.py` to populate for a
  visual check.

---

### [LF-007] Threat hunting fabricates campaigns and finding counts on failure
- **Workstream:** WS-C  **Type:** Bug / Security-integrity  **Priority:** P0  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/ui/app/security/threat-hunting/page.tsx`
- **Evidence:** `page.tsx:176-198` — on **any** error starting a hunt, the catch
  block builds a `mockCampaign` and calls `simulateCampaignProgress()`
  (lines 229-259), which after a timer sets:
  ```js
  findings_count: Math.floor(Math.random() * 15) + 3,
  rules_tested:   Math.floor(Math.random() * 50) + 20,
  logs_scanned:   Math.floor(Math.random() * 500000) + 100000
  ```
- **Problem:** A failed threat hunt reports to a security analyst that it
  completed successfully, scanned up to 600,000 logs, and found **3–18 threats
  that do not exist**. An analyst may open an incident, or — worse — conclude the
  environment was searched when it never was. This is the most dangerous single
  defect in the UI.
- **Implementation spec:**
  1. Delete `simulateCampaignProgress` and the `mockCampaign` fallback.
  2. On failure, surface a destructive-toast/inline error with the HTTP status
     and endpoint; leave the campaign list unchanged.
  3. Only add a campaign to state from a successful `POST /v1/security/threat-hunting`
     response, using the server's `campaign_id`.
  4. Keep `pollCampaignStatus` (lines 200-227) — it reads real server state — but
     surface poll failures instead of only `clearInterval`.
  5. Render `findings_count` / `rules_tested` / `logs_scanned` as `—` until the
     server reports them.
- **Acceptance criteria:**
  - With the API stopped, starting a hunt shows an error and creates no campaign.
  - No `Math.random()` remains in the file.
  - Displayed counts always originate from a server response.
- **Dependencies / blast radius:** Single file.

---

### [LF-008] RBAC role save reports success when persistence fails
- **Workstream:** WS-C  **Type:** Bug / Security-integrity  **Priority:** P0  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/ui/app/settings/roles/page.tsx`
- **Evidence:** `page.tsx:189-215` (`handleSaveRole`): after
  `apiClient.put/post`, the success path updates local state with a comment
  `// Refresh or mock update`; the `catch` block at line 213 is commented
  `// Mock update anyway for demo` and performs the **same** local state update,
  inventing `id: custom_${Date.now()}`.
- **Problem:** An administrator creates or edits a role, sees it appear in the
  list, and believes a security control is in force. It was never persisted.
  After refresh it vanishes — or worse, the admin grants permissions they think
  exist. Silently faking the outcome of a security-configuration change is a
  serious integrity failure and an audit finding.
- **Implementation spec:**
  1. Delete the `catch`-block state mutation; show an error toast with the
     status and endpoint, and keep the dialog open with the user's input intact.
  2. On success, **refetch** `GET /v1/enterprise/rbac/roles` rather than
     optimistically synthesising a row — the server assigns the real `role_id`.
  3. Apply the identical treatment to delete and role-assignment handlers in the
     same file.
  4. Note `/v1/enterprise/rbac/roles` returns `{platform_roles: {...}}`
     (verified live) — confirm the read path maps that shape correctly while here.
- **Acceptance criteria:**
  - With the API stopped, saving a role shows an error and the list is unchanged.
  - After a successful save the list reflects the server response, with a
    server-assigned ID.
  - No `custom_${Date.now()}` ID generation remains.
- **Dependencies / blast radius:** Single file.

---

### [LF-009] Sigma rule test returns invented match/confidence on failure
- **Workstream:** WS-C  **Type:** Bug / Security-integrity  **Priority:** P0  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/ui/app/security/rules/page.tsx`
- **Evidence:** `page.tsx:209-219` (`handleTestRule`) catch block:
  ```js
  setTestResult({
    matched: Math.random() > 0.5,
    matched_fields: { field1: 'value1' },
    confidence: Math.floor(Math.random() * 50) + 50,
    ...
  })
  ```
- **Problem:** "Test rule" is exactly the tool an engineer uses to decide whether
  a detection is correct before enabling it. A coin-flip result with a fabricated
  50–99% confidence and a fake matched field (`field1: value1`) will cause bad
  rules to be deployed and good ones discarded.
- **Implementation spec:**
  1. Delete the fabricated `setTestResult` from the catch block.
  2. Show an error state naming the endpoint and status.
  3. Render `matched_fields` only from the server payload; if absent, show
     "no field detail returned".
  4. While here, ensure the request sends the sample event the user entered —
     verify against `POST /v1/security/sigma-rules/{rule_id}/test`.
- **Acceptance criteria:**
  - With the API stopped, testing a rule shows an error, not a result.
  - No `Math.random()` remains in the file.
- **Dependencies / blast radius:** Single file. Also touched by LF-016's
  response-shape change — same WS-C owner should sequence them.

---

### [LF-010] SIEM page assigns a random MITRE tactic to unmapped techniques
- **Workstream:** WS-C  **Type:** Bug  **Priority:** P0  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/ui/app/security/siem/page.tsx`
- **Evidence:** `page.tsx:246`:
  ```js
  return tacticMap[technique] || MITRE_TACTICS[Math.floor(Math.random() * MITRE_TACTICS.length)].id
  ```
  The local `tacticMap` (lines ~230-245) covers only ~12 technique IDs; every
  other technique is assigned a **random** ATT&CK tactic. The coverage heat-map
  is then computed from these assignments.
- **Problem:** Misattributes attack stages during triage. An analyst reading
  "Exfiltration" for a technique that is actually Persistence will
  mis-prioritise. It also makes the ATT&CK coverage matrix — a key evaluation
  artefact — random noise, and it is non-deterministic across renders.
- **Implementation spec:**
  1. Replace the random fallback with an explicit `'unmapped'` tactic.
  2. Render `unmapped` in a visually distinct, neutral style; exclude it from
     coverage percentages.
  3. Preferably source the mapping server-side via LF-040
     (`GET /v1/security/mitre-coverage`) — the technique→tactic mapping belongs
     with the rule content, not hardcoded in a page. Interim: import the full
     mapping from a generated constant rather than a 12-entry literal.
- **Acceptance criteria:**
  - No `Math.random()` remains in the file.
  - An unmapped technique renders as "unmapped" deterministically across reloads.
  - Coverage percentages exclude unmapped techniques.
- **Dependencies / blast radius:** Single file; LF-040 (WS-B) is the preferred
  data source — build against `'unmapped'` first so the two can land
  independently.

---

### [LF-011] Live metrics page streams fabricated telemetry when SSE fails
- **Workstream:** WS-C  **Type:** Bug  **Priority:** P0  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/ui/app/observability/metrics/live/page.tsx`
- **Evidence:** `page.tsx:107-122` — both `eventSource.onerror` and the catch
  block call `startMockStreaming()`, which (lines 124-184) generates
  `latency = Math.random()*200+50` with injected spikes, `throughput`,
  `error_rate`, `cpu`, `memory` on a timer, and **raises fake threshold alerts**
  from those values (lines 170-182). The page also sets `setIsStreaming(true)`,
  so the UI displays a live-streaming indicator.
- **Problem:** A "live metrics" view that invents metrics when the backend is
  unreachable is the precise inversion of an observability product's purpose —
  it hides the outage it exists to reveal, and fires fabricated alerts.
- **Implementation spec:**
  1. Delete `startMockStreaming` and both call sites.
  2. On SSE error, set a disconnected state showing the endpoint and error, plus
     a manual "Reconnect" action.
  3. Implement automatic reconnection with exponential backoff (1s → 30s cap) and
     display attempt count — the real fix for transient drops.
  4. Note the SSE endpoints work (verified live: `/v1/stream/metrics` returns
     `event: connected` then waits). Confirm the page targets a valid path;
     `LiveStreamingPanel.tsx:63` builds `/v1/stream/${activeStream}` — ensure
     `activeStream` is one of the seven documented streams from
     `GET /v1/stream/health`.
  5. Alerts must derive only from received data points.
- **Acceptance criteria:**
  - With the API stopped, the page shows "disconnected" and an empty chart.
  - No `Math.random()` remains in the file.
  - Reconnection succeeds automatically when the API returns.
- **Dependencies / blast radius:** Single page file. `LiveStreamingPanel.tsx` is
  a separate shared component — WS-C owns both; avoid concurrent edits.

---

### [LF-012] `ServiceHealthMap` calls a 404 endpoint and always shows fake services
- **Workstream:** WS-C  **Type:** Bug  **Priority:** P0  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/ui/components/centrum/ServiceHealthMap.tsx`
- **Evidence:** `ServiceHealthMap.tsx:154` calls
  `/v1/observability/services/health`. Verified live: **HTTP 404** (the real
  route is `/v1/observability/service/{service_name}/health`, singular, per
  service). Both the else-branch (line 159) and the catch (line 163) call
  `generateMockServices()` — a hardcoded list (lines 63-139) including
  `payment-service` at **`status: 'critical'`, `error_rate: 15.2`,
  `latency_p99: 2100`** and `auth-service` "degraded" with "last_incident: 5m ago".
  Because the endpoint always 404s, **the fake list is the only thing ever shown.**
  The component is currently not rendered by any page (`grep` for
  `ServiceHealthMap` outside its own file returns nothing).
- **Problem:** A service-health map permanently showing a fabricated critical
  payment-service outage. It is currently unmounted, which is the only reason it
  is not actively misleading — mounting it would immediately display a fake
  production incident.
- **Implementation spec:**
  1. Decide: delete the component, or wire it correctly. Given `/v1/observability/service-map`
     works (verified live, returns real services with `service_name`,
     `customer_id`), **wire it** — the Centrum page benefits.
  2. Replace the URL with `GET /v1/observability/service-map`, and use
     `GET /v1/observability/apm/services` for per-service request/error/latency.
     Map real fields to `ServiceHealth`.
  3. Delete `generateMockServices` entirely.
  4. Add loading / error / empty states; on error show the endpoint and status.
  5. Derive `status` from real thresholds on real error-rate and latency values,
     documented in the component.
- **Acceptance criteria:**
  - The component issues no request that 404s.
  - `generateMockServices` is gone.
  - With the API stopped it renders an error state, not services.
  - No service named `payment-service` appears unless present in tenant data.
- **Dependencies / blast radius:** Single component. If mounting it on
  `/centrum`, that page file is also WS-C-owned.

---

### [LF-028] Costs page silently swallows a 403 on `/v1/analytics/usage-trends`
- **Workstream:** WS-C  **Type:** Bug  **Priority:** P2  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/ui/app/settings/costs/page.tsx`
- **Evidence:** `page.tsx:77-82` requests `/v1/analytics/usage-trends` inside
  `Promise.allSettled`. Verified live as a tenant admin:
  ```
  GET /v1/analytics/usage-trends -> 403 {"detail":"Platform admin access required"}
  ```
  The rejection is never inspected, so the trends chart stays permanently empty
  with no explanation. `/v1/analytics/feature-usage` behaves the same way.
- **Problem:** Not fabricated data, but a silent failure — the user sees an empty
  chart and assumes zero usage. The endpoint is platform-admin-only by design, so
  a tenant admin can never populate it.
- **Implementation spec:**
  1. Inspect each `allSettled` result; on rejection record a per-panel error.
  2. For a 403 specifically, render "Usage trends require platform administrator
     access" rather than a generic error — it is an authorisation boundary, not a
     fault.
  3. Either hide the panel for non-platform-admins (check role from
     `/v1/auth/me/roles`) or show the explanatory state.
  4. Audit the other three calls on that page for the same swallowing
     (`/v1/usage/current/{id}`, `/v1/costs/breakdown/{id}`,
     `/v1/billing/estimate/{id}` — all verified 200 for tenant admins).
- **Acceptance criteria:**
  - A 403 renders an explanatory message, never a blank chart.
  - Each panel independently reports its own failure.
- **Dependencies / blast radius:** Single file. Same anti-pattern as the
  already-fixed ENH-047; apply that established treatment.

---

### [LF-039] Dashboard widget data endpoint 404s for built-in dashboards
- **Workstream:** WS-C  **Type:** Bug  **Priority:** P2  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/api/services/dashboard_service.py` (`get_widget_data`),
  `apps/api/routers/dashboard.py` (~line 197)
- **Evidence:** Verified live:
  ```
  GET /v1/dashboards/security                              -> 200 (5 widgets)
  GET /v1/dashboards/security/widgets/security_alerts_count/data -> 404 {"detail":"Widget not found"}
  GET /v1/dashboards/security/data                         -> 200 (all 5 widgets with data)
  ```
  `get_widget_data` resolves widgets only from the DB (`dashboard_widgets_mt`);
  built-in dashboards come from `dashboard_engine` in memory
  (`routers/dashboard.py:102-108` shows the fallback exists for the dashboard
  itself but not for widgets).
- **Problem:** Per-widget refresh is impossible for the built-in dashboards,
  forcing whole-dashboard refetches. It is also a plausible reason the UI
  authors reached for `Math.random()` (LF-006).
- **Implementation spec:**
  1. In `get_widget_data`, when the widget is not found in the DB, fall back to
     `dashboard_engine.get_dashboard_definition(dashboard_id)` and locate the
     widget by ID, mirroring the existing dashboard-level fallback.
  2. Execute that widget's query through the same path
     `/{dashboard_id}/data` uses, returning the identical `data` shape.
  3. Add a test covering a built-in dashboard widget and a custom one.
- **Acceptance criteria:**
  - `GET /v1/dashboards/security/widgets/security_alerts_count/data` returns 200
    with the same value as the corresponding entry in `/data`.
  - Custom dashboard widgets are unaffected.
- **Dependencies / blast radius:** **Backend files** — the only WS-C ticket that
  touches the API. If that is awkward for a frontend owner, move this ticket to
  WS-A; it does not conflict with any other ticket either way. LF-006 does not
  depend on it (LF-006 uses `/data`).

---

# WS-D — Build health, auth plumbing & dead code

### [LF-013] UI production build is broken: 107 type errors, gate enabled
- **Workstream:** WS-D  **Type:** Bug / DX  **Priority:** P0  **Effort:** M  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/ui/app/ai/ml-models/page.tsx`,
  `apps/ui/app/observability/apm/page.tsx`,
  `apps/ui/app/observability/metrics/page.tsx`,
  `apps/ui/app/observability/service-map/page.tsx`,
  `apps/ui/components/AdvancedDataViz.tsx`,
  `apps/ui/components/layout/DashboardLayout.tsx`,
  `apps/ui/components/observability/ServiceMapVisualization.tsx`
- **Evidence:** `npx tsc --noEmit` → **107 errors** (re-verified 2026-08-16).
  `next.config.js` sets `typescript.ignoreBuildErrors: false` and
  `eslint.ignoreDuringBuilds: false`, so `next build` runs the same check and
  **fails**. Representative errors:
  - `app/observability/apm/page.tsx:171,203,235,267,344` —
    `Property 'data' does not exist on type '{ services: ServicePerformance[]; }'`
    (the response-envelope mismatch, five sites).
  - `components/AdvancedDataViz.tsx:22` — `Module '"@/lib/api"' has no exported
    member 'ObservabilityApi'` / `'UsageApi'`.
  - `components/layout/DashboardLayout.tsx:331` — `Property 'full_name' does not
    exist on type 'UserProfile'` (API returns `name`).
  - `app/observability/metrics/page.tsx:657` — handler typed
    `(metricsToFetch?: MetricType[]) => Promise<void>` bound to `onClick`.
  - `components/observability/ServiceMapVisualization.tsx` — ~10 D3 typing errors.
  *(Filed previously as ENH-048 and marked `Done`; the count is unchanged.)*
- **Problem:** There is no releasable production artefact. The stack only runs
  because the Docker image executes `npm run dev` (see LF-029), which skips type
  checking. Any CI that runs `npm run build` is red.
- **Implementation spec:**
  1. Fix by category, largest first:
     - **Response envelope (APM, service-map, ml-models):** the pages assume
       `response.data` but `apiClient.get` returns the parsed body directly for
       non-auth endpoints (`lib/api/client.ts:236-245`). Introduce a typed
       helper `unwrap<T>(res): T` handling both shapes and use it consistently.
     - **`full_name` → `name`:** align `UserProfile` with the verified
       `/v1/auth/me` payload (`{id,email,name,status,created_at,updated_at,
       last_login_at,email_verified_at}`).
     - **`AdvancedDataViz` imports:** those classes live in the dead SDK modules
       removed by LF-027 — rewrite the component onto `apiClient`, or delete it
       if unused (`grep -rn "AdvancedDataViz" apps/ui/app`).
     - **D3 typings:** correct `D3Link` to extend
       `SimulationLinkDatum<D3Node>` with compatible `source`/`target`, and type
       the drag behaviour selection properly.
     - **`metrics/page.tsx:657`:** wrap as `onClick={() => fetchMetrics()}`.
  2. Add `npm run type-check` to CI as a required gate (`.github/workflows/`).
  3. Keep `ignoreBuildErrors: false` — do **not** paper over this by disabling it.
- **Acceptance criteria:**
  - `npx tsc --noEmit` reports 0 errors.
  - `npm run build` completes successfully.
  - CI fails on any newly introduced type error.
- **Dependencies / blast radius:** Touches shared components. **Sequencing:**
  `AdvancedDataViz.tsx` depends on LF-027 (dead SDK removal) — do LF-027 first.
  Note WS-C edits `apps/ui/app/observability/metrics/live/page.tsx` (LF-011)
  while WS-D edits `apps/ui/app/observability/metrics/page.tsx` — **different
  files**, no conflict.

---

### [LF-014] `throw new ApiError(...)` on an interface — TypeError on session expiry
- **Workstream:** WS-D  **Type:** Bug  **Priority:** P0  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/ui/lib/api/client.ts`
- **Evidence:** `client.ts:54-59` declares `export interface ApiError {...}`.
  `client.ts:132` executes:
  ```ts
  throw new ApiError('Session expired. Please log in again.', 'AUTH_EXPIRED', 401)
  ```
  `ApiError` is a **type**, not a value — `new ApiError(...)` throws
  `TypeError: ApiError is not a constructor` at runtime. It sits in the `catch`
  of the token-refresh path (line 130), which is reached on every 401.
  `client.ts:503` re-exports it as a type (`export type { ..., ApiError }`),
  confirming it is not a class.
- **Problem:** When a session expires, the intended clean "please log in again"
  error is replaced by an opaque `TypeError`, after `this.logout()` has already
  cleared cookies. Callers catching `ApiError`-shaped objects (they check
  `.status`) get an object with none of those fields, so error handling
  downstream misbehaves at exactly the moment the user needs a clear message.
- **Implementation spec:**
  1. Convert to a real class, preserving the existing shape so structural
     consumers keep working:
     ```ts
     export class ApiError extends Error {
       constructor(message: string, public code: string, public status: number, public details?: any) {
         super(message); this.name = 'ApiError';
       }
     }
     ```
  2. Update line 503 to export it as a value (remove from the `export type` list).
  3. Make the generic error path (lines 137-144) throw the same class rather than
     a plain object literal, so all failures are instanceof-checkable.
  4. Add a test: mock a 401 with no refresh token and assert an `ApiError` with
     `status === 401` is thrown (not a `TypeError`).
- **Acceptance criteria:**
  - Session expiry surfaces `ApiError` with `status`, `code`, `message`.
  - `instanceof ApiError` works for callers.
  - No `TypeError: ApiError is not a constructor` under any path.
- **Dependencies / blast radius:** `client.ts` is imported by every page. Small,
  well-contained change — but it is the shared client, so land it early in WS-D
  and avoid concurrent edits to this file (LF-015 also touches it: do them
  together).

---

### [LF-015] Refresh-token flow is dead; forced re-login every 8 hours
- **Workstream:** WS-D  **Type:** Bug / UX  **Priority:** P1  **Effort:** M  **Risk:** Med
- **Status:** Backlog
- **Affected files:** `apps/api/routers/auth_api.py`, `apps/api/models.py`
  (`LoginResponse`), `apps/ui/lib/api/client.ts`
- **Evidence:** Live login response contains **no** `refresh_token`:
  ```json
  {"access_token":"eyJ...","expires_at":"2026-08-16T14:18:18","user":{...}}
  ```
  `models.py:700-704` — `LoginResponse` declares only `access_token`,
  `expires_at`, `user`. Decoded JWT: `iat`→`exp` = **8.0 hours**.
  `client.ts:160-173` `refreshToken()` reads `Cookies.get(REFRESH_TOKEN_KEY)` and
  throws `'No refresh token available'` — always, since nothing ever sets it
  (`setAuth`'s `refreshToken` argument is never supplied by the login flow).
  Additionally `POST /v1/auth/refresh` requires `Depends(get_current_user)`
  (`auth_api.py:188-191`), i.e. a **valid** access token — so it cannot renew an
  expired session by design.
- **Problem:** Every user is hard-logged-out every 8 hours with an abrupt
  redirect, losing in-progress investigation context. The 401-retry logic in the
  client is dead code that always falls through to `logout()`. For an on-call
  tool this is a significant usability defect.
- **Implementation spec:**
  1. Decide the model. Recommended: **rotating refresh tokens.**
     - Issue a refresh token at login: opaque, random (`secrets.token_urlsafe(48)`),
       stored server-side in `user_sessions_mt` with a hash, `expires_at`
       (7 days), and a `rotated_from` chain for reuse detection.
     - Add `POST /v1/auth/refresh` variant that accepts `{refresh_token}`
       **without** requiring a valid access token, validates against the store,
       rotates (issues new refresh + access), and revokes the old one.
     - Detect reuse of an already-rotated token → revoke the whole chain
       (standard stolen-token defence).
  2. Add `refresh_token` to `LoginResponse`; return it from login and refresh.
  3. UI: pass it to `setAuth(token, tenantId, refreshToken)` at login;
     `refreshToken()` then works unchanged.
  4. Consider shortening the access token to 1 hour once refresh works — that
     reduces the blast radius of a stolen token, which the current 8-hour token
     makes worse.
  5. **Security note:** cookies remain JS-readable (documented at
     `client.ts:193-204` as the unfinished part of ENH-018). Adding a refresh
     token to a JS-readable cookie *increases* XSS blast radius. Prefer issuing
     the refresh token as an `httpOnly` cookie set by the API, with the access
     token kept in memory. If that is out of scope now, state the trade-off
     explicitly in the PR and keep the 7-day cap.
- **Acceptance criteria:**
  - A session older than the access-token TTL refreshes transparently.
  - Reusing a rotated refresh token revokes the chain and forces re-login.
  - Logout revokes the refresh token server-side.
  - Tests cover: happy-path refresh, expired refresh, reuse detection.
- **Dependencies / blast radius:** Touches authentication — **ask before
  merging**, and provide a rollback (feature-flag issuance; the UI tolerates a
  missing refresh token today). Shares `client.ts` with LF-014.

---

### [LF-021] 13 hardcoded wildcard CORS headers bypass the allowlist
- **Workstream:** WS-D  **Type:** Security  **Priority:** P1  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/api/routers/streaming_api.py` (8 sites),
  `apps/api/routers/observability_api.py` (2), `apps/api/routers/alerts.py` (1),
  `apps/api/routers/security_api.py` (1), `apps/api/routers/usage_api.py` (1)
- **Evidence:** Verified live on an **authenticated** endpoint:
  ```
  GET /v1/stream/alerts
  access-control-allow-origin: *
  access-control-allow-headers: Authorization, X-Customer-ID
  ```
  Sites: `streaming_api.py:313,643,847,1039,1110,1172,1236,1496`;
  `observability_api.py:1000,1048`; `alerts.py:649`; `security_api.py:983`;
  `usage_api.py:793`. Meanwhile `main.py:61-67` configures `CORSMiddleware` with
  an explicit allowlist from `CORS_ORIGINS`
  (`http://localhost:3000,3001,3002`) and `allow_credentials=True`.
- **Problem:** These handlers override the configured policy on the SSE streams
  that carry tenant alerts, security events and usage data. Any origin can
  initiate a cross-origin read of these responses. Browsers reject
  `Access-Control-Allow-Origin: *` combined with credentials, so cookie-auth is
  not directly exposed — but the app sends a **bearer token in a header**, and
  any page that obtains a token (or a future credentialed change) would leak
  tenant telemetry cross-origin. It is also an immediate pen-test finding.
- **Implementation spec:**
  1. Delete all 13 hardcoded `"Access-Control-Allow-Origin": "*"` entries (and
     the accompanying `Access-Control-Allow-Headers`) — the global
     `CORSMiddleware` already sets correct per-origin headers for SSE.
  2. Verify SSE still works from `http://localhost:3000` after removal
     (`EventSource`/fetch streaming through the middleware).
  3. Add a test asserting no route returns `Access-Control-Allow-Origin: *`:
     iterate the app's routes, or assert on the streaming responses specifically.
  4. Ensure `CORS_ORIGINS` is set explicitly in every deployment; fail startup if
     it is `*` while `ENVIRONMENT` is enforced (extend `security_config.py`,
     which already implements exactly this pattern for secrets).
- **Acceptance criteria:**
  - No response carries a wildcard ACAO.
  - Streaming works from an allowlisted origin and is rejected from others.
  - A regression test guards it.
- **Dependencies / blast radius:** Five router files, mechanical. WS-C does not
  touch API routers (except LF-039, a different file), so no conflict.

---

### [LF-026] Delete 4 dead modules containing mock implementations (2,712 LOC)
- **Workstream:** WS-D  **Type:** Tech-debt  **Priority:** P2  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/api/ai_engine.py` (827),
  `apps/api/enterprise_engine.py` (1,115), `apps/api/dashboard_demo.py` (292),
  `apps/api/synthetic_data_generator.py` (478)
- **Evidence:** Zero importers — verified:
  ```
  ai_engine: 0   enterprise_engine: 0   dashboard_demo: 0   synthetic_data_generator: 0
  ```
  All four contain fabrication that violates the no-mock rule:
  - `ai_engine.py:275-290` — `_execute_query` "mock implementation" returning
    invented `payment-api` error logs.
  - `enterprise_engine.py:778` — `section_score = 0.85 + (hash(section) % 100)/1000  # Mock scoring`
    (fabricated **compliance** scores); `:819` fabricated legal-hold
    `data_count`; `:543` `b'mock_qr_code_data'` MFA QR; `:1021` `"reliability": 0.995`;
    `:1072` `ip_address="192.168.1.100",  # Mock IP`. State is held in
    process-local dicts (`self.mfa_setups`, `self.legal_holds`) that vanish on
    restart.
  - `synthetic_data_generator.py` — `faker`-based generator.
- **Problem:** ~2,700 lines of unreferenced code whose mock behaviour is a
  standing trap: `enterprise_engine.EnterpriseEngine` has the same method names
  as the live `services/enterprise_service.EnterpriseService` (`setup_mfa`,
  `list_roles`, `generate_compliance_report`, `create_legal_hold`), so a
  mis-typed import silently swaps real compliance reporting for fabricated
  scores. It also inflates the apparent surface area during review.
- **Implementation spec:**
  1. Re-confirm zero importers (including tests and `apps/admin-ui`):
     `grep -rn "ai_engine\|enterprise_engine\|dashboard_demo\|synthetic_data_generator" --include="*.py" .`
  2. Delete the four files.
  3. If synthetic data is wanted for demos, keep the **root** `data_generator.py`
     (a deliberate, documented tool) as the single sanctioned generator — it is
     separate from the API package and cannot be imported by request paths.
  4. Confirm `tests/test_offline_app_import.py` and `test_import_contract.py`
     still pass.
- **Acceptance criteria:**
  - Files removed; full test suite passes (819 tests).
  - API starts cleanly.
  - No remaining module inside `apps/api/` returns fabricated data.
- **Dependencies / blast radius:** Deletion only. Do it early in WS-D — LF-013
  and LF-027 both get simpler afterwards.

---

### [LF-027] Delete 12 unused API SDK modules referencing ~130 phantom endpoints
- **Workstream:** WS-D  **Type:** Tech-debt  **Priority:** P2  **Effort:** M  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/ui/lib/api/{ai,alerts,dashboard,enterprise,observability,query,roles,security,storage,subscription,tenants,usage}.ts`,
  `apps/ui/lib/api/index.ts`
- **Evidence:** Import counts across `app/` and `components/`:
  ```
  ai:0  alerts:0  dashboard:0  enterprise:0  observability:0  query:0
  roles:0  security:0  storage:0  subscription:0  tenants:0  usage:0
  auth:1  users:1
  ```
  Cross-checking every `/v1/...` string in the UI against the live OpenAPI spec
  (290 paths) found ~130 references to non-existent endpoints, almost all inside
  these dead modules — e.g. the entire `/v1/subscription/*` surface (22 paths:
  `plans`, `invoices`, `payment-methods`, `promo-code`…), `/v1/storage/{id}/*`
  (17 paths), `/v1/roles/*` CRUD (9 paths), `/v1/enterprise/sso/configs`,
  `/v1/enterprise/backup/*`. None exist server-side.
- **Problem:** ~2,000 lines implying a large working SDK that is entirely
  fictional. It misleads engineers into thinking billing, SSO config, backup and
  storage-lifecycle APIs exist, and it is the source of the `AdvancedDataViz`
  type errors in LF-013.
- **Implementation spec:**
  1. Delete the 12 modules with zero importers. Keep `auth.ts` and `users.ts`
     (each used once) but audit them against the spec and remove phantom methods
     (`/v1/auth/change-password`, `/v1/auth/password-reset/*`,
     `/v1/users/me/sessions`, `/v1/users/me/preferences`, etc. — the real routes
     are `/v1/auth/password/change`, `/v1/auth/password/reset`,
     `/v1/auth/sessions`).
  2. Update `lib/api/index.ts` exports accordingly; fix `AdvancedDataViz.tsx`
     (coordinate with LF-013 — same file).
  3. Add a CI check that greps every `/v1/...` literal in `apps/ui` and asserts
     it matches a path in the API's OpenAPI spec. This prevents the class of bug
     entirely and would have caught LF-012 and the MFA 404.
  4. Record genuinely desired-but-missing capabilities (billing/subscription
     self-service, SSO config UI, backup management) as product tickets rather
     than leaving dead client code as a placeholder.
- **Acceptance criteria:**
  - Only `client.ts`, `index.ts`, `auth.ts`, `users.ts` remain in `lib/api/`.
  - No UI source references a path absent from the OpenAPI spec.
  - The CI endpoint-existence check passes and fails on an introduced typo.
- **Dependencies / blast radius:** Must land **before** LF-013's
  `AdvancedDataViz` fix. No overlap with WS-C or WS-E files.

---

### [LF-029] UI Docker image runs `npm run dev` in production
- **Workstream:** WS-D  **Type:** Tech-debt / Perf  **Priority:** P2  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/ui/Dockerfile`, `infra/docker/compose.yml`
- **Evidence:** `apps/ui/Dockerfile` ends with `CMD ["npm", "run", "dev"]`; there
  is no `npm run build` step and no multi-stage build. `compose.yml:168-179`
  bind-mounts the source into the container. The container serves an unoptimised
  dev bundle with HMR and no type checking — which is why LF-013's 107 type
  errors have gone unnoticed.
- **Problem:** Dev-mode Next.js is substantially slower (no route pre-rendering,
  no minification, no code splitting) and unsuitable for any real deployment. It
  also masks build failures.
- **Implementation spec:**
  1. Multi-stage Dockerfile: `deps` (npm ci) → `builder` (`npm run build`) →
     `runner` (`next start`, non-root, `NODE_ENV=production`). Use Next.js
     `output: 'standalone'` in `next.config.js` to minimise the runtime image.
  2. Keep a separate `Dockerfile.dev` (or a compose override) preserving the
     current bind-mount + `npm run dev` for local development.
  3. Pin the Node base image to match `package.json` engines; `node:18-alpine`
     with Next 14 is fine — confirm.
  4. Gate on LF-013: the production build cannot succeed until type errors are
     fixed.
- **Acceptance criteria:**
  - `docker build apps/ui` produces an image running `next start`.
  - The production container serves the app with no HMR.
  - Local dev flow (hot reload) still works via the dev override.
- **Dependencies / blast radius:** **Blocked by LF-013.** Sequence within WS-D:
  LF-026 → LF-027 → LF-013 → LF-029.

---

### [LF-032] 6 tenant-ID interpolation sites in NLQ SQL
- **Workstream:** WS-D  **Type:** Security (defence-in-depth)  **Priority:** P2  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/api/services/nlq_processor.py` (lines 416, 433, 454,
  472, 490, 505)
- **Evidence:** `nlq_processor.py` builds SQL with
  `WHERE customer_id = '{customer_id}'` at six sites. Verified live that the NLQ
  path is genuinely functional (it generated correct SQL and found a real log),
  so this is live code, not dead.
- **Problem:** Currently **not exploitable**: `customer_id` originates from the
  auth middleware and is UUID-validated by `tenant_dependencies.validate_tenant_header`
  before reaching any handler. But it is the single interpolation pattern that
  ENH-002/003/004 eliminated everywhere else, and it sits on the tenant-isolation
  predicate — the one filter whose failure is a cross-tenant data breach. One
  future call path that skips validation turns this into a critical bug.
- **Implementation spec:**
  1. Convert all six to bound parameters (`%(customer_id)s`) passed through the
     existing `DatabaseLayer.execute_query(query, params)` path.
  2. Grep for the same pattern elsewhere:
     `grep -rn "customer_id = '{" apps/api --include="*.py"`.
  3. Extend `tests/test_query_engine_sql_injection.py` (or add an NLQ-specific
     test) asserting a crafted tenant value cannot alter the predicate.
- **Acceptance criteria:**
  - No f-string interpolation of `customer_id` into SQL remains in `apps/api/`.
  - NLQ still returns correct results (regression-test the "show me errors in the
    last hour" case, which currently works).
- **Dependencies / blast radius:** Single file. Low risk, high symbolic value.

---

### [LF-033] 4 tenant-router tests failing (403 vs 404 on `platform`)
- **Workstream:** WS-D  **Type:** Bug / DX  **Priority:** P2  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `tests/routes_tests/test_tenant_router.py`,
  `apps/api/authn_authz_middleware.py`, `apps/api/routers/tenant_api.py`
- **Evidence:** `python3 -m pytest tests/` → **4 failed, 815 passed**:
  ```
  FAILED tests/routes_tests/test_tenant_router.py::test_tenant_crud_operations
  FAILED tests/routes_tests/test_tenant_router.py::test_tenant_decommissioning
  FAILED tests/routes_tests/test_tenant_router.py::test_tenant_list_filtering
  FAILED tests/routes_tests/test_tenant_router.py::test_error_handling
  ```
  Failure detail:
  ```
  Non-existent tenant should return 404, got 403:
  {"error":"No access to tenant: platform"}
  ```
  The test assigns `super_admin` for tenant `platform` and sets
  `X-Customer-ID: platform`, but the middleware rejects `platform` as a tenant
  the user cannot access.
- **Problem:** A persistently red suite trains the team to ignore failures and
  hides real regressions. It also signals genuine ambiguity about whether
  `platform` is a valid tenant sentinel — `tenant_dependencies.py:32` explicitly
  permits `"Use valid UUID or 'default'"`, while roles use `'platform'`. Three
  sentinels (`platform`, `default`, `''`) echo the LF-003 defect.
- **Implementation spec:**
  1. Decide the contract: is `platform` a tenant ID, or only a role scope?
     Recommendation — **role scope only**; platform admins should access
     tenant-scoped routes by passing a real tenant UUID, and platform-wide routes
     should live under `/v1/admin/*` (which already exists and correctly returns
     403 for tenant admins).
  2. Update `check_permission` / tenant validation so a `super_admin` with a
     `platform` role assignment passes tenant access checks for any tenant
     (tenant-less platform admin), which `authn_authz_middleware.py:480-500`
     already partially contemplates.
  3. Fix the tests to assert the decided contract — 404 for a well-formed but
     non-existent tenant UUID, 403 for a tenant the caller cannot access.
  4. Document the sentinel policy in one place, alongside the LF-003 decision.
- **Acceptance criteria:**
  - `pytest tests/` is fully green (819 passed).
  - A well-formed unknown tenant UUID returns 404; an unauthorised tenant returns 403.
  - Tenant-isolation tests still pass.
- **Dependencies / blast radius:** Touches the auth middleware — coordinate with
  LF-015 (also auth, different file). Verify `tests/test_tenant_isolation.py` and
  `test_feature_access_fail_closed.py` after the change.

---

# WS-E — Search & query UX

> The competitive core. Logforge has a working query engine, a working query
> language, and working saved queries — but a user cannot reach most of it.

### [LF-022] LogQL requires explicit time range or 400s; no default window
- **Workstream:** WS-E  **Type:** Bug / UX  **Priority:** P1  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/api/routers/query.py` (`logql_query`, ~line 201)
- **Evidence:** Live:
  ```
  POST /v1/query/logql {"query":"{service=\"audit-test\"}","limit":5}
  -> HTTP 400  "2 validation errors ... start_time Field required ... end_time Field required"
  ```
  With an explicit range it works:
  ```
  POST /v1/query/logql {"query":"error | limit 3","start_time":...,"end_time":...} -> 200
  ```
  `query.py:229-233` copies `start_time`/`end_time` from the request body only
  if present; `build_query_request` then requires them.
- **Problem:** The documented example in the endpoint's own docstring
  (`{"query": "error | where service = \"api\" | limit 100"}`) returns 400. Every
  comparable system (Loki, Splunk, Datadog) applies a default relative window.
  This makes the query language unusable from curl, the docs, or any future UI.
- **Implementation spec:**
  1. Default to `now() - 1h … now()` when absent (consistent with LF-017).
  2. Support relative ranges in the body (`"since": "15m" | "24h" | "7d"`) and,
     ideally, in the language itself (`| last 15m`) via `logql.py`.
  3. Echo the effective range in the response.
  4. Enforce the same max-window guard as LF-017.
  5. Update the docstring example to one that actually works.
- **Acceptance criteria:**
  - The docstring example returns 200.
  - The effective time range appears in the response.
  - Over-wide ranges return a clear 400.
- **Dependencies / blast radius:** Shares `routers/query.py` with LF-017 and
  LF-025's backend needs — **same file, one owner**. Land LF-017 and LF-022
  together; define the shared default-window helper once.

---

### [LF-023] LogforgeQL has no UI surface at all
- **Workstream:** WS-E  **Type:** Feature  **Priority:** P1  **Effort:** M  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/ui/app/observability/logs/page.tsx`,
  new `apps/ui/components/query/QueryBar.tsx`
- **Evidence:** `grep -rn "logql" apps/ui/app apps/ui/components` → **no matches**.
  The backend implements a full query language (`apps/api/logql.py`,
  `tests/test_logql.py`, endpoint `POST /v1/query/logql`, verified working), and
  the logs page instead issues `GET /v1/logs` with only `service`/`level`
  filters and a hardcoded `limit: 500`.
  *(Previously ENH-050, correctly left `Backlog`.)*
- **Problem:** The single most important differentiator against Splunk (SPL) and
  Datadog is an expressive query language. It was built (ENH-028) and then never
  exposed, so from a buyer's perspective the product has *no* query language —
  only two dropdowns. This is the largest gap between built capability and
  delivered value in the codebase.
- **Implementation spec:**
  1. Build `QueryBar.tsx`: a text input posting to `/v1/query/logql`, with the
     global time range, a run button, and Cmd/Ctrl+Enter to execute.
  2. Show syntax errors inline — the API returns a helpful 400 with the parser
     message (`LogQLSyntaxError`); render it verbatim near the cursor.
  3. Add autocomplete for field names from `GET /v1/schemas/standard-fields`
     and for service names from `GET /v1/observability/metrics/services`
     (both verified working; note `/v1/schemas/*` currently 403s for tenant
     admins — confirm the permission mapping or use an alternative source).
  4. Wire to the existing saved-query API (`GET/POST /v1/query/saved`, verified
     working and already used by the page) so a query can be saved and recalled.
  5. Provide a mode toggle: simple filters (current UI) ↔ LogforgeQL, so the
     basic path is not regressed.
  6. Ship a short in-product syntax reference (drawer or link) with 5-6 worked
     examples — adoption of a query language depends on discoverability.
- **Acceptance criteria:**
  - A user can type `error | where service = "api" | limit 100`, run it, and see
    matching logs.
  - Syntax errors render inline without clearing the input.
  - A query can be saved, listed, and re-run.
  - The simple filter mode still works unchanged.
- **Dependencies / blast radius:** Owns `logs/page.tsx` jointly with LF-024 and
  LF-025 — **all three are one coherent piece of work on one file; do them as a
  single sequence in WS-E.** Depends on LF-022 for sane defaults.

---

### [LF-024] Logs page has no live tail
- **Workstream:** WS-E  **Type:** Feature  **Priority:** P1  **Effort:** M  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/ui/app/observability/logs/page.tsx`
- **Evidence:** `grep -n "tail\|EventSource\|getStream\|follow"` in the logs page
  matches only unrelated comments ("Expanded Details", "Log Detail Panel"). The
  page performs a single `apiClient.get('/v1/logs', {... limit: 500})`.
- **Problem:** Live tail (`tail -f` for logs) is table stakes — Datadog Live
  Tail, Splunk real-time search, `logcli --tail`, `kubectl logs -f`. It is the
  primary workflow during an incident, which is exactly when the product must be
  most useful. Its absence is immediately noticed in any evaluation.
- **Implementation spec:**
  1. The client already has SSE support: `apiClient.getStream(endpoint, onData,
     onError)` (`client.ts:363-471`), which correctly attaches `Authorization`
     and `X-Customer-ID` headers (`EventSource` cannot).
  2. Backend: no log-tail stream exists today
     (`GET /v1/stream/health` lists metrics, traces, security, alerts, usage,
     ai-insights, anomalies). Add `GET /v1/stream/logs` in
     `apps/api/routers/streaming_api.py`, subscribing to the same normalised-log
     event stream the Sigma processor consumes (`logs.normalized` — confirmed
     flowing in the live pipeline logs), filtered by tenant and by the current
     query/filter set.
  3. UI: a "Live tail" toggle that opens the stream, prepends arriving lines,
     caps the buffer (e.g. 2,000 lines) to bound memory, auto-scrolls with a
     pause-on-scroll-up affordance, and shows a connection indicator.
  4. On disconnect, show the disconnected state and reconnect with backoff —
     **never** synthesise lines (see LF-011).
  5. Respect the existing SSE rate limiting (ENH-026,
     `tests/test_stream_rate_limit.py`).
- **Acceptance criteria:**
  - Toggling live tail streams newly ingested logs within ~2s of ingest.
  - Filters/query apply to the tail.
  - The buffer is bounded; the page stays responsive over a long session.
  - Disconnection is visible and recovers automatically.
- **Dependencies / blast radius:** Adds a backend route in `streaming_api.py` —
  note WS-D edits that file for LF-021 (CORS header removal). **Sequence LF-021
  before LF-024**, or have WS-E rebase; they touch different lines but the same
  file.

---

### [LF-025] Logs page hardcodes `limit: 500`, no pagination
- **Workstream:** WS-E  **Type:** Bug / UX  **Priority:** P1  **Effort:** S  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/ui/app/observability/logs/page.tsx`
- **Evidence:** `page.tsx:186-192` is the only fetch:
  ```js
  const response = await apiClient.get('/v1/logs', { ... limit: 500 })
  ```
  No `offset`, no "load more", no page controls — despite `/v1/logs` supporting
  `offset: int = Query(0, ge=0)` and `limit` up to 10,000
  (`routers/query.py:548-549`).
- **Problem:** A user cannot see beyond the 500 most recent matching logs. During
  an incident with high log volume, the relevant entry is frequently outside that
  window, and there is no indication that results were truncated — the user
  believes they have seen everything.
- **Implementation spec:**
  1. Add infinite scroll (or "Load more") using `offset`, appending results.
  2. Show a truncation indicator and the total when known — `/v1/logs` should
     return a `total`; add it server-side alongside LF-017 (same file,
     `routers/query.py`) using a `count()` with the same predicate, or return
     `has_more` cheaply by fetching `limit + 1`.
  3. Reduce the initial page to 100 for faster first paint; fetch more on demand.
  4. Preserve scroll position when appending.
  5. Combine with LF-017's time-range parameters so paging is bounded and
     partition-pruned.
- **Acceptance criteria:**
  - A user can page past 500 results.
  - Truncation is explicit, never silent.
  - Initial render is faster than today's 500-row fetch.
- **Dependencies / blast radius:** Same file as LF-023/LF-024; same owner.
  Backend `total`/`has_more` lands with LF-017.

---

# WS-F — Competitive gaps (alerting delivery, ingest, onboarding)

### [LF-035] No alert notification delivery — all channels are stubs
- **Workstream:** WS-F  **Type:** Feature  **Priority:** P1  **Effort:** L  **Risk:** Med
- **Status:** Backlog
- **Affected files:** `apps/api/alert_engine.py` (lines 759-774),
  `apps/api/services/alert_service.py`, `apps/api/dao/alert_dao.py`,
  new `apps/api/services/notification_service.py`
- **Evidence:** `alert_engine.py`:
  ```python
  759: """Send email notification (placeholder implementation)"""
  764: """Send Slack notification (placeholder implementation)"""
  769: """Send webhook notification (placeholder implementation)"""
  774: """Send PagerDuty notification (placeholder implementation)"""
  ```
  The API surface exists and works — `GET/POST /v1/alerts/notifications/channels`
  returns 200 (`{"channels":[],"total":0}`), plus
  `POST /v1/alerts/notifications/channels/{id}/test` and
  `GET/POST /v1/alerts/integrations/webhooks`. `notification_channels_mt` exists
  in ClickHouse. But nothing is ever delivered.
- **Problem:** An alerting system that cannot notify anyone is not an alerting
  system. This is the difference between a log viewer and a monitoring product —
  a small company's core requirement is "tell me when something breaks while I'm
  not looking". Every competitor treats Slack/email/PagerDuty as day-one
  functionality. Note the UI already has a full channels page
  (`apps/ui/app/alerts/channels/page.tsx`) wired to these endpoints, so the gap
  is purely the delivery backend.
- **Implementation spec:**
  1. Create `services/notification_service.py` with a provider interface
     (`send(channel_config, alert) -> DeliveryResult`) and implementations:
     - **Webhook** (do this first — it unblocks everything else, including Slack
       via incoming webhooks): POST JSON, configurable headers, HMAC signature
       over the body so receivers can verify authenticity.
     - **Slack**: incoming webhook + Block Kit formatting.
     - **Email**: SMTP via `aiosmtplib`, configurable server/credentials.
     - **PagerDuty**: Events API v2 (`trigger`/`resolve`), mapping severity and
       using `dedup_key` for correct incident lifecycle.
  2. **Reliability:** deliver from the existing bounded worker pattern (mirror
     `ingest_pipeline.py`); retry with exponential backoff and jitter; a circuit
     breaker per channel (`utils/query_resilience.py` already provides one);
     dead-letter after N attempts with the failure visible via the API.
  3. **Idempotency/dedup:** key on `(rule_id, alert_id, channel_id)` so retries
     and re-evaluations do not double-page.
  4. **Rate limit / grouping:** cap notifications per rule per window and group
     related alerts, reusing `services/alert_correlation_service.py` (already
     implemented: `/v1/alerts/correlation/*` endpoints all return 200) — this is
     a genuine differentiator against basic tools.
  5. **Secrets:** channel credentials must be encrypted at rest, never returned
     by `GET /channels` (return a masked hint), and never logged.
  6. Make `POST /channels/{id}/test` perform a real delivery and return the true
     provider result — no fabricated success (no-mock rule).
  7. Record every attempt in `alert_notifications_mt` for an auditable trail.
- **Acceptance criteria:**
  - Configuring a Slack webhook and triggering a rule delivers a message.
  - A failing endpoint retries, then dead-letters visibly — no silent drop.
  - The test button reports genuine success/failure.
  - Credentials never appear in API responses or logs.
  - Duplicate evaluations do not produce duplicate pages.
- **Dependencies / blast radius:** New service plus `alert_engine.py`. No file
  overlap with other workstreams. **Ask before enabling delivery in any
  environment with real channel configs** — a misconfigured loop can page a real
  on-call rotation; ship behind `LOGFORGE_NOTIFICATIONS_ENABLED` defaulting off.

---

### [LF-036] No log ingestion agent / shipper integration path
- **Workstream:** WS-F  **Type:** Feature  **Priority:** P1  **Effort:** L  **Risk:** Low
- **Status:** Backlog
- **Affected files:** new `docs/integrations/`, new `config/vector/`,
  new `config/fluent-bit/`, new `config/otel/`,
  `apps/api/routers/ingestion.py` (compatibility endpoints)
- **Evidence:** The API accepts a good range of formats — `/v1/ingest/logs`,
  `/logs/batch`, `/logs/bulk`, `/syslog`, `/cef`, `/nginx`, `/otlp`,
  `/structured`, `/text` (verified: a single ingest landed in ClickHouse and was
  queryable in ~4 s). But `grep` finds no agent configuration, no Helm values for
  a collector (`infra/helm/` is empty), and no integration docs
  (`docs/` contained only the two audit files). `/v1/enterprise/integrations`
  returns an `available_integrations` catalogue (Slack etc.) but nothing for log
  shipping.
- **Problem:** A prospect's first question is "how do I get my logs in?" Today
  the answer is "write a custom HTTP client". Competitors ship agents (Datadog
  Agent, Splunk UF, Promtail/Alloy, Elastic Beats) or first-class OTel support.
  Without a documented path from a real host/container to Logforge, evaluation
  stops before it starts — this is the top funnel blocker.
- **Implementation spec:**
  1. **Do not build an agent.** Support the ones that exist:
     - **Vector** sink config (`config/vector/logforge.toml`) using the HTTP sink
       → `/v1/ingest/logs/batch` with the API key header and gzip.
     - **Fluent Bit** output config (`config/fluent-bit/logforge.conf`).
     - **OpenTelemetry Collector** exporter config → `/v1/ingest/otlp`
       (endpoint already exists; verify it against a real OTel collector,
       including the field normalisation covered by
       `tests/test_otel_field_normalization.py`).
  2. **Docker/Kubernetes quickstarts:** a `docker-compose` snippet adding Vector
     to tail container logs, and a Helm values example for a DaemonSet — put real
     content in the empty `infra/helm/`.
  3. **API-key auth for agents:** `/v1/enterprise/auth/api-keys` exists and
     returns 200. Verify an API key alone authenticates the ingest endpoints
     (agents cannot perform an interactive login) and document the header.
     `authn_authz_middleware.py:913` references `api_key_permissions`, so the
     path exists — confirm and document scopes.
  4. **Batching/compression guidance:** document recommended batch sizes against
     the 32 MB body cap (`request_limits.py:47`) and the 429 back-pressure
     contract (`ingestion.py:54-85`), which agents already know how to honour.
  5. **Verify-my-setup endpoint:** a lightweight "have you received anything from
     me in the last 5 minutes" check for onboarding (feeds LF-037).
- **Acceptance criteria:**
  - A documented copy-paste Vector config ships logs from a container into
    Logforge and they appear in the logs UI.
  - The same for Fluent Bit and OTel Collector.
  - An API key alone suffices for ingestion; no user session required.
  - Docs state batch-size and retry expectations, including 429 handling.
- **Dependencies / blast radius:** Mostly new files and docs. Touches
  `routers/ingestion.py` only if compatibility gaps are found.

---

### [LF-037] No onboarding flow: empty tenant has no path to first data
- **Workstream:** WS-F  **Type:** Feature  **Priority:** P1  **Effort:** M  **Risk:** Low
- **Status:** Backlog
- **Affected files:** new `apps/ui/app/onboarding/page.tsx`,
  `apps/ui/app/centrum/page.tsx`, `apps/ui/components/layout/DashboardLayout.tsx`
- **Evidence:** The audited tenant has 48 logs, 0 security events, 0 alert
  instances, 1 alert rule. Every page consequently renders empty, with no
  guidance. There is no `/onboarding` route among the 31 pages, and no empty-state
  call-to-action on `/centrum`. Combined with LF-036, a new tenant has no
  in-product path to sending data.
- **Problem:** Time-to-first-value decides small-company evaluations. Splunk
  Cloud, Datadog and Grafana Cloud all open with a guided "connect a source"
  flow. Logforge drops the user into empty dashboards that are
  indistinguishable from broken ones — an impression the mock-data tickets
  (WS-C) were presumably meant to paper over. Fixing WS-C **increases** the need
  for this ticket: honest empty states must come with a path forward.
- **Implementation spec:**
  1. **Onboarding checklist** at `/onboarding`, also surfaced as a dismissible
     banner while incomplete:
     (a) create an API key → `POST /v1/enterprise/auth/api-keys`;
     (b) choose a shipper (Vector / Fluent Bit / OTel / curl) and copy a
     pre-filled config with the key and endpoint injected (LF-036);
     (c) live "waiting for your first log…" indicator that polls
     `/v1/logs?limit=1` (or the LF-036 verify endpoint) and confirms on arrival;
     (d) enable a starter detection pack (needs LF-003/LF-005);
     (e) create the first alert rule + notification channel (needs LF-035).
  2. **Empty states everywhere:** each page's empty state should name the reason
     and link to the relevant onboarding step — never a blank panel.
  3. **Sample data, clearly labelled and opt-in:** allow loading a demo dataset
     via the root `data_generator.py` into a dedicated `demo` tenant, badged
     "Demo data" in the UI and removable in one click. This satisfies the
     evaluation need **without** violating the no-mock rule, because it is real
     ingested data the user explicitly requested, in a separate tenant.
  4. Track completion per tenant (`tenant_configs_mt` exists).
- **Acceptance criteria:**
  - A new tenant sees the checklist on first login.
  - Copying the generated config and running it results in the "first log
    received" step completing automatically.
  - Empty states link to the matching step.
  - Demo data is opt-in, visibly badged, isolated to its own tenant, and
    removable.
- **Dependencies / blast radius:** Best after LF-036 (configs to hand out).
  Touches `centrum/page.tsx` and `DashboardLayout.tsx` — **`DashboardLayout.tsx`
  is also edited by WS-D (LF-013, `full_name` fix)**. Sequence LF-013 first, or
  agree a one-line split.

---

### [LF-038] No saved-search alerting (search → monitor)
- **Workstream:** WS-F  **Type:** Feature  **Priority:** P2  **Effort:** M  **Risk:** Low
- **Status:** Backlog
- **Affected files:** `apps/api/routers/alerts.py`,
  `apps/api/services/alert_service.py`, `apps/api/alert_engine.py`,
  `apps/ui/app/alerts/rules/page.tsx`
- **Evidence:** Saved queries work (`GET/POST /v1/query/saved` → 200, used by the
  logs page) and alert rules work (`GET/POST /v1/alerts/rules` → 200). There is
  no link between them: a saved query cannot become an alert rule, and
  `/v1/alerts/rules` has no notion of a LogforgeQL query as its condition.
- **Problem:** "Search, then alert on that search" is the central workflow of
  Splunk (saved search → alert) and Datadog (log query → monitor). Without it,
  users must re-express detection logic in a separate rule syntax, which is the
  main reason log-alerting goes unused.
- **Implementation spec:**
  1. Extend the alert-rule model with a `query_type: 'logql' | 'legacy'` and a
     `query` field holding LogforgeQL, evaluated on a schedule via the same
     compiler used by `/v1/query/logql` (`apps/api/logql.py`).
  2. Condition types: result count over a window (`> N in 5m`), ratio, and
     absence (`no results in 15m` — log-source silence, a genuinely valuable
     detection).
  3. Add "Create alert from this search" in the logs UI (WS-E's QueryBar,
     LF-023) prefilling the rule form.
  4. Reuse the LF-035 notification pipeline for delivery.
  5. Guard evaluation cost with the existing query cost limits (ENH-017,
     `tests/test_query_cost_guards.py`) and a per-tenant cap on scheduled
     evaluations.
- **Acceptance criteria:**
  - A LogforgeQL query can be saved as an alert rule and fires on a matching log.
  - An absence condition fires when a source stops reporting.
  - Evaluation respects cost guards and per-tenant caps.
  - "Create alert from search" prefills correctly from the logs page.
- **Dependencies / blast radius:** Depends on LF-035 (delivery) and LF-023
  (query bar) for full value; the backend half can land independently.
  `apps/ui/app/alerts/rules/page.tsx` is touched only by this ticket.

---

## File-ownership matrix (verified non-overlapping)

Generated by listing the *Affected files* of every ticket and checking for
collisions across workstreams. **Verified: no file is owned by two workstreams**,
with four documented coordination points listed below.

| Workstream | Files owned |
|---|---|
| **WS-A** | `apps/api/services/health_service.py`, `apps/api/database_layer.py`, `apps/api/dao/*.py`, `apps/api/utils/connection_pool.py`, `apps/api/routers/query.py`¹, `apps/api/query_engine.py`, `apps/api/routers/ai_api.py`, `apps/api/error_handling.py` (new), `apps/api/ttl_manager.py`, `apps/api/services/storage_service.py`, `apps/api/services/ingestion_service.py`, `apps/api/parsers.py`, `infra/docker/clickhouse/**`, `apps/api/services/multi_metric_anomaly_detector.py` |
| **WS-B** | `apps/api/mitre_default_loader.py`, `apps/api/dao/security_dao.py`², `apps/api/routers/security_api.py`³, `apps/api/services/security_service.py`, `apps/api/content_pack_loader.py`, `apps/api/content/rules/**` (new), `tests/test_detection_rule_quality.py` |
| **WS-C** | `apps/ui/app/dashboards/[id]/page.tsx`, `apps/ui/app/dashboards/[id]/edit/page.tsx`, `apps/ui/app/security/threat-hunting/page.tsx`, `apps/ui/app/settings/roles/page.tsx`, `apps/ui/app/security/rules/page.tsx`, `apps/ui/app/security/siem/page.tsx`, `apps/ui/app/observability/metrics/live/page.tsx`, `apps/ui/components/centrum/ServiceHealthMap.tsx`, `apps/ui/app/settings/costs/page.tsx`, `apps/api/services/dashboard_service.py`⁴, `apps/api/routers/dashboard.py`⁴ |
| **WS-D** | `apps/ui/lib/api/**`, `apps/ui/components/AdvancedDataViz.tsx`, `apps/ui/components/layout/DashboardLayout.tsx`⁵, `apps/ui/components/observability/ServiceMapVisualization.tsx`, `apps/ui/app/observability/apm/page.tsx`, `apps/ui/app/observability/metrics/page.tsx`, `apps/ui/app/observability/service-map/page.tsx`, `apps/ui/app/ai/ml-models/page.tsx`, `apps/ui/Dockerfile`, `apps/api/ai_engine.py`, `apps/api/enterprise_engine.py`, `apps/api/dashboard_demo.py`, `apps/api/synthetic_data_generator.py`, `apps/api/services/nlq_processor.py`, `apps/api/authn_authz_middleware.py`, `apps/api/routers/auth_api.py`, `apps/api/models.py`, `apps/api/routers/streaming_api.py`⁶, `apps/api/routers/observability_api.py`, `apps/api/routers/alerts.py`⁷, `apps/api/routers/usage_api.py`, `tests/routes_tests/test_tenant_router.py` |
| **WS-E** | `apps/ui/app/observability/logs/page.tsx`, `apps/ui/components/query/QueryBar.tsx` (new), `apps/api/logql.py` |
| **WS-F** | `apps/api/alert_engine.py`, `apps/api/services/alert_service.py`, `apps/api/services/notification_service.py` (new), `apps/ui/app/alerts/rules/page.tsx`, `apps/ui/app/onboarding/page.tsx` (new), `apps/ui/app/centrum/page.tsx`, `config/vector/**`, `config/fluent-bit/**`, `config/otel/**`, `docs/integrations/**`, `infra/helm/**` |

### Coordination points (only four)

1. **`apps/api/routers/query.py`** — WS-A (LF-017) and WS-E (LF-022) both need a
   shared default-time-window helper. **Resolution:** WS-A owns the file and
   lands LF-017 + LF-022 together; WS-E consumes the result. *(LF-022 is listed
   under WS-E for thematic grouping; assign the code change to WS-A's owner.)*
2. **`apps/api/dao/security_dao.py` + `routers/security_api.py`** — LF-016's
   response-shape change (bare array → envelope) affects two WS-C pages
   (`security/rules`, `security/siem`). **Resolution:** agree the envelope shape
   up front; land the API change and the two UI call-site updates in one PR
   co-authored by WS-B and WS-C.
3. **`apps/api/routers/streaming_api.py`** — WS-D removes CORS headers (LF-021);
   WS-E adds `/v1/stream/logs` (LF-024). **Resolution:** land LF-021 first
   (small, mechanical), then LF-024.
4. **`apps/ui/components/layout/DashboardLayout.tsx`** — WS-D fixes `full_name`
   (LF-013); WS-F adds the onboarding banner (LF-037). **Resolution:** LF-013
   first; LF-037 rebases.

Footnotes: ¹ shared with WS-E — see (1). ² ³ shared with WS-C — see (2).
⁴ LF-039 is backend; move to WS-A if the WS-C owner is frontend-only.
⁵ shared with WS-F — see (4). ⁶ shared with WS-E — see (3).
⁷ `routers/alerts.py`: WS-D touches only the CORS line (649); WS-F works in
`alert_engine.py` / `alert_service.py`. If LF-038 needs `routers/alerts.py`,
sequence after LF-021.

### Recommended execution order within each workstream

- **WS-A:** LF-001 → LF-002 → LF-019 → LF-020 → LF-017(+LF-022) → LF-018 → LF-030 → LF-034 → LF-031
- **WS-B:** LF-004 → LF-003 → LF-016 → LF-005 → LF-040
- **WS-C:** LF-006 → LF-007 → LF-008 → LF-009 → LF-010 → LF-011 → LF-012 → LF-028 → LF-039
- **WS-D:** LF-026 → LF-027 → LF-014 → LF-013 → LF-021 → LF-033 → LF-032 → LF-029 → LF-015
- **WS-E:** (after LF-022) LF-023 → LF-025 → LF-024
- **WS-F:** LF-036 → LF-035 → LF-037 → LF-038

### Cross-workstream P0 sequencing

The two P0s that unblock the most downstream work are **LF-002** (connection
pooling — every latency benchmark depends on it) and **LF-004/LF-003** (rule
dedupe + tenancy — the whole SIEM surface depends on them). Start those two
first. **LF-001** is a 3-line fix with outsized operational value; do it on day
one regardless of workstream planning.
