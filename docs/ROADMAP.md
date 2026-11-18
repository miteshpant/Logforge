# Roadmap and where to help

These tasks are concrete and scoped, and each was checked against the code. To
claim one, open an issue (or comment on an existing one) so nobody duplicates
the work. Items marked **good first issue** are self-contained and need little
knowledge of the system.

The long-range product plan (phased path to a unified, AI-assisted security
and observability platform) is in [PLATFORM_ROADMAP.md](./PLATFORM_ROADMAP.md).
This file lists the short, claimable tasks.

A full code analysis (architecture, security, quality, priorities) is in
[CODE_ANALYSIS.md](./CODE_ANALYSIS.md). Historical design notes and the full
enhancement log are in
[ENHANCEMENTS.md](./ENHANCEMENTS.md). Its `Status` column is out of date: many
of those tickets are already fixed in the code (look for `LF-0xx` / `ENH-0xx`
markers).

## Bugs and gaps

- **Sustained ingest is slow: 277 events/s, 37 s until searchable**
  ([benchmarks](./benchmarks/README.md)). A single 1,000-event batch takes
  60–95 ms, but under sustained load the API container is CPU-bound (~100%)
  while ClickHouse idles, and requests slow to seconds. Profile the ingest
  path, move post-ingest work (normalisation, detection) out of the
  request-serving process into separate workers, and run the API with
  multiple workers instead of a single `--reload` process.
- **The normalizer maps `hostname` onto the DNS `query` field**
  (`apps/api/config/field_mapping.yml`), so every event with a host name
  carries `query: <hostname>` and DNS rules on `query` can match host names.
  Remove the mapping and check the evaluation baseline.
- **Detection engine follow-ups from Phase 1**
  ([platform roadmap](./PLATFORM_ROADMAP.md)): sequence rules have no `until`
  (abort) condition; no correlation over alerts (e.g. "3+ distinct
  techniques on one host"); git sync is push-from-CI only (no server-side
  pull on a schedule or webhook); synced correlations can't reference the
  shipped library; the streaming state has a 200k-event soak test, not a
  24 h one; correlation state is per process (lost on restart, not shared
  between API replicas).
- **Cases follow-ups from Phase 2**
  ([platform roadmap](./PLATFORM_ROADMAP.md)): merge and split need UI
  (the API has them); @mentions are recorded on notes but not delivered,
  which needs per-user notifications; "create case" should be available
  wherever an alert is shown (SIEM dashboard, Centrum incidents); a case
  per host splits lateral movement across hosts (link source and
  destination hosts); the grouping lock is per API process, so two
  replicas can open duplicate cases for one entity; SLA targets should be
  configurable per tenant.
- **Threat-intel follow-ups from Phase 3**
  ([guide](./threat-intel.md)): URLhaus and ThreatFox need an abuse.ch
  Auth-Key (anonymous downloads return 410), so those feeds have only been
  tested against fixtures, never live; in the reference compose setup the
  API container has no outbound DNS, so feed fetches fail until egress is
  allowed; matching is an in-memory index per API process (no ClickHouse
  dictionary), and each replica reloads it separately; MISP and TAXII are
  read as exported documents (no live MISP API, no TAXII collection
  paging); GeoIP has been tested with DB-IP-format fixtures, not the full
  download; impossible-travel rules (which need GeoIP) are still to be
  written; matches are stamped as `attrs.threat`, not ECS
  `threat.indicator.*`.
- **OpenTelemetry metric aliases ignore units.** `cpu.utilization` is a 0–1
  ratio while the canonical `cpu_usage` is a percentage. Mapping one to the
  other needs a unit conversion in `metric_name_mappings.yml` and the
  normalizer, not just a rename.

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

- `logforge_pe001-privilege-escalation` no longer fires on every successful
  `sudo` (0 false positives on the benign corpus, down from 127); sudo
  abuse is covered by `lf-c-sudo-failure-burst`.
- Rules for the four detection gaps the evaluation found: T1105, T1059.004,
  T1569.002 and T1069.002.
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
- `count()` rules load through batch fixtures (the brute-force rule now fires),
  and Sigma rules see fields kept under `attrs`.
- Failed UI mutations reject (`ApiError`), every call site is checked by a
  test, and `get()` no longer drops `{ params }` filters.
- Playwright specs 01–04 rewritten; the whole suite (43 tests) runs in CI.
- gzip-compressed request bodies are accepted (bounded), and the shipper
  recipes compress.
- The admin login page no longer shows non-existent demo credentials, and the
  admin UI is branded Logforge (it said "MrLogSec").
