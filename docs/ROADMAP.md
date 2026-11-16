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

## Bugs and gaps

- **Playwright specs 01–04 are out of date.** `apps/ui/tests/01-04-*.spec.ts`
  expect a seeded `test@example.com` user and selectors the current UI no
  longer has; 44 of their tests fail against a live stack. CI runs specs 05–08
  only. Rewrite 01–04 against `scripts/bootstrap_demo.py`'s demo user (as
  05–08 do), or delete the ones that duplicate newer coverage, then add them to
  the `ui-e2e` job in `.github/workflows/ci.yml`.
- **`apiClient` errors are easy to miss.** `apps/ui/lib/api.ts` reports HTTP
  errors as `{ success: false }` instead of throwing, so a `try/catch` around a
  call never sees a 4xx/5xx. The dashboard editor and security pages now check
  `success`; about 25 other files under `apps/ui/app` and
  `apps/ui/components` call `post`/`put`/`delete` and should be audited the
  same way (or the client changed to throw, with every caller updated).
- **The brute-force rule is not loaded.** `packages/rules/brute_force_detection.yml`
  uses `count(selection) >= 10 by src_ip`, which the loader's single-event
  fixture gate cannot verify, so it is reported as awaiting content. Teach
  `mitre_default_loader._verify_fixtures` to accept a batch fixture (a list of
  events that must trip the threshold, and one that must not) and add one to
  the rule.
- **OpenTelemetry metric aliases ignore units.** `cpu.utilization` is a 0–1
  ratio while the canonical `cpu_usage` is a percentage. Mapping one to the
  other needs a unit conversion in `metric_name_mappings.yml` and the
  normalizer, not just a rename.
- **Gzip request bodies are rejected.** Shippers can compress batches, but the
  API does not decode `Content-Encoding: gzip`, so the shipper recipes leave
  compression off. Add a request-decompression middleware with a size limit.

## Remove demo / fake data from the UI

- The admin UI `billing`, `features` and `support` pages are "Coming soon"
  placeholders.

## Features

- **Auth flows**: sending password-reset and invite emails, email
  verification, and session revocation are TODOs in
  `apps/api/routers/auth_api.py`.
- **Threat-intel feed clients** (for example MISP, OTX, abuse.ch) for
  `apps/api/threat_intel.py`.
- **Pluggable LLM backend** for the natural-language query in
  `apps/api/services/ai_service.py`, which today uses keyword templates.
  Define a small provider interface selected by configuration, with **no
  provider enabled by default**: without one, the keyword templates stay the
  behaviour, and no data leaves the deployment unless an operator opts in.
- A dead-letter queue for the event bus; Grafana dashboards for Logforge's own
  metrics; OpenTelemetry self-tracing.

## Recently completed

For reference, these were on this list and are now done:

- Pattern alert rules in the `conditions` list format now match.
- `logs_raw_mt.attrs` stores only the caller's attributes.
- Tenant metric names are listed in the Metrics Explorer
  (`GET /v1/observability/metrics/names`).
- The query result cache key includes an engine fingerprint.
- Route tests are collected by pytest (216 tests) and run in CI against the
  compose stack; Playwright specs 05–08 run in CI too.
- Duplicate `GET /v1/tenants/{tenant_id}/usage` route removed.
- `GET /v1/stream/logs` live tail endpoint.
- Playwright global setup, Makefile auth, and a single ClickHouse settings
  source.
- Ingestion `500`s no longer leak exception text.
- Dead root scripts and the unmounted `events_api` router deleted.
- Dashboard editor and security pages no longer fake data or successes;
  `AiChatAssistant.tsx` deleted.
- `GET /v1/security/mitre-coverage` and `/v1/security/mitre-attack/techniques`;
  the SIEM page uses the server-side matrix.
- Setup tokens are persisted (hashed) in ClickHouse.
- `packages/rules/` is loaded at startup through the fixture gate.
- Shipper recipes authenticate, use `/v1/ingest/logs/batch` (which now accepts
  a bare JSON array), and a Fluentd recipe exists.
- Production UI images, the admin UI in compose and `deploy.sh`, and Python
  3.12 in the API image.
- The OpenAPI spec is also published as `docs/api/openapi.yaml`.
- The admin login page no longer shows non-existent demo credentials, and the
  admin UI is branded Logforge (it said "MrLogSec").
