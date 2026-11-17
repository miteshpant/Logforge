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

- **`logforge_pe001-privilege-escalation` is noisy.** It fires on every
  successful `sudo`: 127 false positives in the 2,000-event benign corpus,
  all of the false positives measured
  ([tests/eval/detection](../tests/eval/detection/README.md)). Narrow it to
  suspicious patterns (sudo to a shell, users not normally using sudo,
  `sudo` failures followed by success) and update the baseline.
- **Detection gaps found by the evaluation corpus:** no rule detects
  T1105 (certutil / PowerShell download cradles), T1059.004 (Linux reverse
  shells), T1569.002 (PsExec service execution) or T1069.002 (domain group
  discovery). Add fixture-tested rules to `packages/rules/` and record the
  improvement with `--update-baseline`.
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
