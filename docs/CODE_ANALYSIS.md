# Logforge code analysis

*Snapshot of `main` as of November 2026. Every claim here was checked against
the code, by reading it or by running tests, linters and scanners. File paths
are relative to the repository root. If you fix something listed here, update
this file or [ROADMAP.md](./ROADMAP.md) in the same PR.*

> **Update:** many findings below (dead code, the duplicate route, fake UI
> data, development-mode containers, route tests outside CI, in-memory setup
> tokens, unused `packages/rules/`) have since been fixed. See
> [ROADMAP.md → Recently completed](./ROADMAP.md#recently-completed) for the
> list; the sections below are left as the original snapshot.

## 1. Executive summary

Logforge is a substantial, mostly genuine observability and SIEM backend: about
87k lines of Python, 744 pytest tests and 290 API paths. Its core pipeline is
real and defended by tests: ingest, then Kafka, then ClickHouse, then query,
alert and Sigma detection. Many of those tests are regression guards for
specific past bugs, such as SQL-injection guards, fail-closed auth and
delivery confirmation.

The weak points are at the edges:

| Area | Verdict |
| --- | --- |
| Ingestion, storage, query, detection | **Solid.** Real implementations, bounded resources, tested. |
| Auth and multi-tenancy | **Solid design, a few gaps.** Fail-closed middleware, production secret checks; setup tokens live only in memory. |
| Python dependencies | **✅ Clean.** About 170 advisories were fixed by upgrading; pip-audit now blocks merges (section 6.1). |
| Front ends | **Mixed.** Most screens call the real API. A few still fabricate data, and type errors had masked real bugs (now fixed). |
| "AI" features | **Overstated.** Keyword templates and canned output, with no model behind them. |
| Operability | **Development-grade.** UIs run `npm run dev` in containers; admin UI is not in compose; route tests are not in CI. |

## 2. Size and shape

| Component | Lines (py/ts/tsx) | Notes |
| --- | --- | --- |
| `apps/api` | 86,956 | FastAPI; 23 router files (22 mounted), about 40 services, 17 DAOs, event bus |
| `apps/ui` | 36,832 | Next.js 14 tenant UI |
| `apps/admin-ui` | 6,880 | Next.js 14 platform-admin UI |
| `tests` | 25,021 | 744 tests; 222 of them in `tests/routes_tests` need live infrastructure |

The largest modules are candidates for splitting:

| Module | Lines |
| --- | --- |
| `routers/ai_api.py` | 2,056 |
| `services/security_service.py` | 1,931 |
| `services/enterprise_service.py` | 1,626 |
| `routers/streaming_api.py` | 1,598 |
| `dao/observability_dao.py` | 1,563 |

## 3. Architecture

```
client ──► /v1/ingest/* (auth, parse, validate)
             │  bounded worker pool (ingest_pipeline.py) ─► 429 + Retry-After when full
             ▼
        Kafka topic "log-events"   (publish is awaited: no ack-before-durable)
             ▼
        log_handler ─► field mapping ─► write_buffer_service ─► ClickHouse logs_raw_mt
             │                                  └─► disk DLQ on write failure
             ▼  "logs.normalized"
        ├─► normalized_writer_consumer ─► logs_normalized_mt
        └─► sigma_consumer (rules cached in Redis) ─► security_events_mt
```

- **Topics** are defined in `apps/api/config/events.yml`: `log-events`, `usage-events`, `alert-events`, `tenant-events`, `ui-realtime-events`, `system-events`.
- **Schema:** `infra/docker/clickhouse/init_simple.sql` is authoritative, followed by `migrations/001–014`. Migrations 005 and 006 do not exist.
- **Tenant isolation** is by a `customer_id` column on every `*_mt` table. The middleware takes the tenant from the API key, or from the `X-Customer-ID` header for JWTs.
- **Process model:**
  - Ingest, consumers, the alert engine and the SSE streams all run inside one API process. The container starts it as `uvicorn --reload`: a single worker in development mode.
  - Running more workers or replicas would duplicate the timer-driven alert loop and the in-memory correlation state. Every rule would fire once per worker, and correlation windows would each see only part of the traffic. Fix this before scaling out.

## 4. Subsystem assessment

### Ingestion ✅
- Formats: JSON, batch, bulk, OTLP, syslog, nginx, CEF, text and structured, in `routers/ingestion.py` and `parsers.py`.
- Back-pressure is real: a bounded queue answers `429` with `Retry-After`.
- Gap: `500` responses return `str(e)` to the client, which leaks internal details.

### Query ✅
- `query_engine.py` builds parameterised SQL with tenant scoping and window and cost guards. Ranges wider than `LOGFORGE_MAX_QUERY_WINDOW_DAYS` are rejected.
- **LogforgeQL** (`logql.py`) is a pipe language that compiles to the request model, never to raw SQL. That is a good safety property. The name invites confusion with Grafana's LogQL.
- No user-supplied raw SQL path was found.

### Detection ✅
- `sigma_engine.py` and `sigma_condition.py` implement Sigma conditions and modifiers.
- 243 rules vendored from SigmaHQ (DRL 1.1) are loaded at startup, gated by fixtures.
- `packages/rules/` (11 hand-written rules plus a content pack) is used **only by tests**.
- A MITRE coverage matrix exists in `security_service.py`, but no route exposes it, so the UI computes coverage itself.

### Alerting and notifications ✅
- Threshold, pattern, anomaly and saved-search rules (`alert_engine.py`).
- Real webhook, Slack, SMTP, PagerDuty, Teams and Discord senders. Delivery is off unless `LOGFORGE_NOTIFICATIONS_ENABLED` is set.
- Channel secrets are encrypted with Fernet, keyed from `LOGFORGE_SECRET_KEY`.

### Anomaly and predictive 🟡
- z-score and EWMA detectors and forecasting are real statistics.
- `rca_engine.py` contains placeholder scores, e.g. `similarity_score: 0.75  # TODO`.

### "AI" 🧪
- `services/ai_service.py::_convert_nl_to_sql` picks one of four hardcoded SQL templates by keyword.
- `generate_optimization_recommendations` returns fixed numbers.
- No LLM dependency exists.
- Either implement these properly or label them as experimental in the UI.

### Auth and tenancy ✅/🟡
- `authn_authz_middleware.py` is fail-closed. Tokens containing `.` are treated as JWTs; tokens starting with `lf_` are API keys.
- Each endpoint maps to a permission, for example `logs:write:tenant`.
- Platform roles are expressed as role rows with `tenant_id='platform'`.
- `security_config.py` refuses to start in production-like environments when the defaults for `JWT_SECRET`, `CLICKHOUSE_PASSWORD` or `MINIO_SECRET_KEY` are still in use. This is a good guard.
- Gaps:
  - Setup tokens are held in process memory and lost on restart.
  - Password-reset and invite emails, email verification and session revocation are TODOs in `routers/auth_api.py`.
  - The admin UI keeps tokens in `localStorage` (documented in `tests/test_ui_token_storage.py`).

### Billing 🟡
- Usage metering, rate cards and invoice computation exist. There is no payment provider.
- The admin usage page falls back to hardcoded per-tier revenue (`997/499/99`) when platform statistics are unavailable, so it can show invented revenue.

## 5. Front ends

**Bugs found and fixed in this pass** (they were hidden among type errors that had stopped CI from building the UIs):

| Bug | Effect | Fix |
| --- | --- | --- |
| Admin UI: three pages passed `<option>` and `onChange` to the custom compound `Select`, which ignores both | Role, status and period dropdowns could not be changed | Added `NativeSelect` |
| UI `contexts/AuthContext.tsx` stored the `{user_id, roles}` object where an array was expected | `availableTenants.find()` threw, breaking tenant switching | Use `.roles` |
| UI metrics "Refresh" button passed the click event as `queryMetrics(metricsToFetch)` | The refresh queried with an event object instead of a list of metrics | Wrapped in an arrow function |
| Admin UI `src/lib/` was gitignored | No clone could build the admin UI | Restored and un-ignored |

**Still open:**
- `apps/ui/components/query/useLiveTail.ts` calls `/v1/stream/logs`, which does not exist.
- The dashboard editor previews `Math.random()` data and reports success when a save fails.
- The security events and threat-intel pages change only local state ("for demo").
- `AiChatAssistant.tsx` is unused, canned, and should be deleted.
- The admin `billing`, `features` and `support` pages are placeholders.
- Containers run in development mode: `uvicorn --reload` for the API, `npm run dev` for the UI. The admin UI's Dockerfile has an unused production stage, and the admin UI is not in the main compose file.

## 6. Security posture

### 6.1 Dependency vulnerabilities: ✅ resolved

At the time of the analysis, `pip-audit -r apps/api/requirements.txt` reported
about 170 advisories across 13 pinned packages. The worst were aiohttp 3.9.1
(84), PyJWT (19), python-multipart (16), Starlette 0.27 via FastAPI 0.104
(14) and cryptography 41 (14).

All of them were fixed by upgrading:

- **Web stack:** FastAPI 0.163, Starlette 1.10, uvicorn 0.54, pydantic 2.14, python-multipart 0.0.33, httpx 0.28.
- **Security-related libraries:** aiohttp 3.14, PyJWT 2.15, cryptography 50.
- **Data and serialisation:** orjson 3.13, msgpack 1.2, pyarrow 26.
- **Test tooling:** pytest 9 with pytest-asyncio 1.5.
- **Removed:** `python-jose`, which nothing imported and which had advisories with no fix, including through its `ecdsa` dependency.

The audit now reports no known vulnerabilities, and the pip-audit step in CI
is blocking.

The FastAPI upgrade also changes how startup events behave: router-level
`on_event("startup")` hooks now run alongside the app's custom lifespan.
The only such hook (`routers/security_api.py`) had never run before and
called a method that does not exist, so it was removed.

### 6.2 Static analysis (bandit, medium and high)

| Finding | Count | Assessment |
| --- | --- | --- |
| B608 SQL built from strings | 163 | A sample checked by hand was safe: interpolated parts are constant table names or allow-listed expressions, and values are passed as parameters. The concentration in DAOs (`alert_dao` 23, `storage_dao` 15, `tenant_dao` 12) is worth a systematic audit. Existing tests (`test_*_sql_injection.py`) cover the query engine and Sigma processor. |
| B324 MD5/SHA1 | 5 | Probably used for IDs or fingerprints. Mark them `usedforsecurity=False` or switch to SHA-256. |
| B104 bind to all interfaces | 3 | Expected inside containers. |

### 6.3 Secrets and configuration
- gitleaks runs on every push and PR. Its PR scan was failing with a 403 permissions error; fixed in this pass.
- Hardcoded tokens and passwords were removed from the scripts at the repository root. **Git history still contains old development credentials and a contributor's email address.** Rewriting history is the only way to remove them.
- The Compose file ships development credentials (`logforge123`, `minio123`). `SECURITY.md` documents this.

## 7. Code quality

`ruff check apps/api --statistics`:

| Count | Rule | Meaning |
| --- | --- | --- |
| 2,470 | UP006 / UP045 / UP035 | Old-style typing. Auto-fixable. |
| 1,079 | BLE001 | `except Exception` |
| 259 | F401 | Unused imports. Auto-fixable. |
| 168 | DTZ003 | Naive `datetime.utcnow()`. Correctness risk around timezones; deprecated in Python 3.12. |
| 113 | B008 | Function calls in default arguments (mostly FastAPI `Depends`, which is acceptable) |

Other markers:
- 50 bare or blanket `except` clauses in `apps/api`.
- 56 `print()` calls in API code; they bypass structured logging.
- 37 `TODO` / `FIXME` markers.
- 18 "for demo" / mock / `Math.random()` markers in UI code.
- Dead code: `routers/events_api.py` is never mounted. Four root scripts (`test_event_flow*.py`, `test_kafka_availability.py`, `test_event_publishers_subscribers.py`) import modules that no longer exist.
- Duplicate route: `GET /v1/tenants/{tenant_id}/usage` is defined in both `tenant_api.py` and `subscription_api.py`, and only the first one registered is ever reached.

Recommendations:
- Run `ruff --fix` for the safe UP/F401/I001 classes in one mechanical PR.
- Replace `datetime.utcnow()` with `datetime.now(timezone.utc)`.
- Replace `print` with the structured logger.

## 8. Testing and CI

| Job | State after this pass |
| --- | --- |
| API tests | 845 pass, run without infrastructure, plus an OpenAPI freshness check |
| API lint | Blocking on F821/F811, advisory otherwise |
| Security scan | pip-audit and gitleaks blocking; bandit advisory |
| UI build (ui, admin-ui) | `tsc` now **blocking** and clean; `next build` passes |
| Publish API docs | Needs Settings → Pages → Source: GitHub Actions |

Gaps:
- `tests/routes_tests` (222 tests) never runs in CI. Add ClickHouse, RedPanda and Redis service containers.
- The Playwright suites never run in CI. `apps/ui` has no `npm test` script, and `global-setup.ts` calls the nonexistent `/v1/health`.
- Python versions differ: 3.11 in the Dockerfile, 3.12 in CI.

## 9. Prioritised recommendations

| # | Priority | Item |
| --- | --- | --- |
| 1 | ✅ | ~~Upgrade the vulnerable Python dependencies (6.1); make pip-audit blocking.~~ Done. |
| 2 | P0 | Decide on git history (old development credentials and personal email) **before** making the repository public. |
| 3 | P1 | Remove or clearly label fabricated UI data and the "AI" features, so users can trust what they see. |
| 4 | P1 | Run `routes_tests` and Playwright in CI. |
| 5 | P1 | Production-mode images: drop `--reload`, run `next start`; add the admin UI to compose. |
| 6 | P1 | Fix the duplicate tenant-usage route; add `/v1/stream/logs`; expose MITRE coverage. |
| 7 | P2 | Persist setup tokens; finish the email-based auth flows. |
| 8 | P2 | Mechanical lint clean-up; timezone-aware datetimes; structured logging instead of `print`. |
| 9 | P2 | Make alerting and correlation safe for multiple workers before running more than one. |
| 10 | P3 | Split the 1,500+ line modules; delete dead routers and scripts. |

Concrete, claimable versions of these items are in [ROADMAP.md](./ROADMAP.md).
