# Roadmap and where to help

These tasks are concrete and scoped, and each was checked against the code. To
claim one, open an issue (or comment on an existing one) so nobody duplicates
the work. Items marked **good first issue** are self-contained and need little
knowledge of the system.

A full code analysis (architecture, security, quality, priorities) is in
[CODE_ANALYSIS.md](./CODE_ANALYSIS.md). Historical design notes and the full
enhancement log are in
[ENHANCEMENTS.md](./ENHANCEMENTS.md). Its `Status` column is out of date: many
of those tickets are already fixed in the code (look for `LF-0xx` / `ENH-0xx`
markers).

## Bugs and broken things

- **Route tests are mostly not collected.** `pytest tests/routes_tests --co`
  finds only 4 tests although the directory holds about 220 `test_*`
  functions, most of them inside suites built on `base_test.BaseTestSuite`
  rather than pytest classes. Convert them so pytest collects them, then run
  them in CI with service containers.
- **Duplicate route.** `GET /v1/tenants/{tenant_id}/usage` is defined in both
  `apps/api/routers/tenant_api.py` and `apps/api/routers/subscription_api.py`.
  The tenant router is registered first, so the subscription version can never
  be reached. Pick one and remove or rename the other. *(good first issue)*
- **UI live tail calls a missing endpoint.** `apps/ui/components/query/useLiveTail.ts`
  calls `/v1/stream/logs`, which does not exist. Add it to
  `apps/api/routers/streaming_api.py`, following the existing SSE streams.
- **Playwright global setup** (`apps/ui/tests/global-setup.ts`) calls
  `/v1/health`, which does not exist; the endpoint is `/health`.
  *(good first issue)*
- **Makefile `seed-demo` / `test-log`** post to `/v1/ingest/logs` without auth
  and get `401`. Make them take an `LOGFORGE_TOKEN` env var.
  *(good first issue)*
- **Ingestion `500` responses leak exception text** (`str(e)`) to clients
  (`apps/api/routers/ingestion.py`).
- **Inconsistent `CLICKHOUSE_HOST` default**: `localhost` in
  `apps/api/app_config.py`, `clickhouse` elsewhere.
- **Dead root scripts**: `test_event_flow.py`, `test_event_flow_simple.py`,
  `test_kafka_availability.py` and `test_event_publishers_subscribers.py` import
  modules that no longer exist. Delete them or port them into `tests/`.
  *(good first issue)*
- `apps/api/routers/events_api.py` is never mounted. Mount it or delete it.

## Remove demo / fake data from the UI

- Dashboard editor `apps/ui/app/dashboards/[id]/edit/page.tsx` previews
  `Math.random()` data, and on a failed save it reports success.
- `apps/ui/app/security/events/page.tsx` and `security/threat-intel/page.tsx`
  update state only locally ("for demo").
- `apps/ui/components/AiChatAssistant.tsx` returns canned answers and is not
  used anywhere. Delete it. *(good first issue)*
- The admin UI `billing`, `features` and `support` pages are "Coming soon"
  placeholders.

## Features

- **MITRE ATT&CK coverage API**: `security_service.py` already computes a
  coverage matrix. Expose it as `GET /v1/security/mitre-coverage` and have
  `apps/ui/app/security/siem/page.tsx` use it instead of computing coverage in
  the browser.
- **Auth flows**: sending password-reset and invite emails, email
  verification, and session revocation are TODOs in
  `apps/api/routers/auth_api.py`.
- **Persist setup tokens** in the database instead of process memory.
- **Load `packages/rules/`** (the hand-written rules and content pack) at
  runtime. Today only tests use it.
- **Threat-intel feed clients** (for example MISP, OTX, abuse.ch) for
  `apps/api/threat_intel.py`.
- **A real LLM backend** for the natural-language query in
  `apps/api/services/ai_service.py`, which today uses keyword templates.
- **Shipper recipes**: add the `Authorization` header and use
  `/v1/ingest/logs/batch` in the Vector config, and add a Fluentd recipe (the
  README mentions one, but it is missing).
- A dead-letter queue for the event bus; Grafana dashboards for Logforge's own
  metrics; OpenTelemetry self-tracing.

## Infrastructure and CI

- Run the UI containers in production mode instead of `npm run dev`
  (`apps/ui/Dockerfile`).
- Add the admin UI to `infra/docker/compose.yml` and `deploy.sh`.
- Add ClickHouse, RedPanda and Redis service containers to CI so
  `tests/routes_tests` runs on every PR.
- Run the Playwright suites in CI.
- Align Python versions: the Dockerfile uses 3.11 and CI uses 3.12.
