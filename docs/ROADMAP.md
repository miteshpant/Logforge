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
- **Ingest pipeline follow-ups from Phase 4** ([guide](./pipelines.md)):
  `route` only records a destination in `attrs.route` (separate tables
  and retention tiers are not implemented); pipeline metrics are per API
  process and reset on restart; the editor takes processors as JSON, with
  no form-based builder; the OTLP and JSON parsers and the normalizer's
  field mappings (`field_mapping.yml`, schema registry) are not expressed
  as pipelines yet, only nginx, syslog, CEF and text are; the legacy
  parser classes remain as the reference for the parity tests; the runner
  costs about 39 µs per event against the processors' 22 µs (stats are
  taken per step and each routed event is snapshotted for the dead-letter
  queue), which could be trimmed.
- **Common schema follow-ups from Phase 5** ([guide](./schema.md)): only
  OCSF Authentication has source mappings (Linux sshd, Windows Security,
  Okta); Process Activity, Network Activity, HTTP Activity and DNS have
  only the generic field mapping, with no class, activity or status. The
  shipped Sigma and Logforge rules still use today's field names (the
  Sigma field mapping covers them) and aren't migrated to `ocsf.*`.
  Dashboards aren't migrated either. The field catalogue is computed from
  a sample of the latest events per request (cached 60 s), not a
  persistent per-tenant index with type history. LogforgeQL extraction
  uses RE2, so no lookaround or backreferences, and allows at most 32
  extracted fields per query.
- **Response follow-ups from Phase 13** ([response automation](./response.md)):
  - **Compliance reports** (the Phase 13 deliverable not done): evidence
    for SOC 2 and ISO 27001 controls from the audit log, retention and
    access reviews.
  - **More ticket systems with sync:** ServiceNow and Linear. Today they
    can only be reached by a webhook action.
  - **Approve from Slack or Teams** (interactive messages), with the same
    role check as in Logforge.
  - **Built-in containment connectors** (Okta and Entra ID user disable,
    AWS security groups), each behind an approval.
  - **Branches and parallel steps in playbooks**, and a run history kept
    longer than 180 days for audits.
  - **A Unicode font in the PDF report** (today Latin-1 only).
  - **Retire the older `/v1/enterprise/integrations` API** and its tables
    (`integrations_mt` in `init_simple.sql`, `enterprise_integrations_mt`).
    The Settings → Integrations page no longer uses them.
- **Storage and scale follow-ups from Phase 12** ([storage](./storage.md), [deployment](./deployment.md)):
  - **Ingest throughput, for the cost target:**
    - measure per-replica throughput on dedicated nodes;
    - run several uvicorn workers per pod;
    - move the log consumer out of the API process.

    The reference architecture needs 18 API replicas at today's 343 events/s.
  - **Exactly-once ingest:** deduplicate redelivered batches (a batch id,
    ClickHouse insert deduplication tokens). Today a failure stores a batch
    twice.
  - **ClickHouse 24.x:** a production-ready Replicated database that
    converts MergeTree tables itself, so `REPLICATED_ENGINES` can go.
  - **Bind mutation timestamps as parameters** (about 16 `now64()`
    mutations), so `allow_nondeterministic_mutations` can go.
  - **Three Keepers and three Redpanda brokers in the HA compose**, and the
    chaos test killing them too.
  - **Install the Helm chart on a real cluster in CI** (kind), and publish
    the images it names.
  - **Exact per-tenant hot/warm sizes:** tenants share parts, so they're
    estimated from rows by age.
- **Entity analytics follow-ups from Phase 11** ([guide](./entities.md)):
  - **Stored risk:** keep each entity's daily risk, so pages show how it
    moved and ranking doesn't recompute 14 days of alerts.
  - **Learned peer groups:** cluster by role (hosts used, services) instead
    of comparing with every entity of a type.
  - **Baselines for every entity in the ranking**, not just the top 30.
  - **Patterns at scale:** cluster in a background job per service and keep
    templates, so `| patterns` covers more than 1 M lines.
  - **Independent scenarios:** risk scenarios written by someone other than
    the author of the scoring.
- **AI follow-ups from Phase 10** ([guide](./ai.md#investigation-and-authoring-phase-10)):
  - **Record the models:** `record_copilot.py` (needs ClickHouse) and
    `record_rule_draft.py`, then commit the recordings and baselines.
  - **Unseen attacks:** add copilot scenarios and drafting behaviours written
    by someone other than the author of the signals and the drafter.
  - **Signals beyond keywords:** use rarity (first time a process, domain or
    address is seen for a host or user) so roots with no known signal, like
    a payload download, are found.
  - **Case report evaluation:** a labelled set with required facts.
  - **Drafting:** count and correlation rules are out of scope for drafts.
- **AI follow-ups from Phase 9** ([guide](./ai.md#features-phase-9)):
  - **Record the models:** run `tests/eval/ai/record_nl2query_exec.py`,
    `record_triage.py`, `record_pipeline_draft.py` and `record_explain.py`
    with a provider (needs an API key and, for the first, ClickHouse) and
    commit the recordings and baselines. Then check plain-English queries
    against the ≥ 85% target.
  - **Rate triage:** build an analyst-rated set (helpfulness and factual
    accuracy) for triage summaries.
  - **Real questions:** add analysts' own questions to the NL2Query sets
    beside the templated ones.
  - **Held-out formats:** add sample files the drafter and the explain
    reference were not developed against.
  - **Replace the old services:** move `/v1/ai/query` and the AI service's
    template answers onto the Phase 9 features.
  - **Explain gaps:** epoch timestamps aren't recognised by the pipeline
    drafter; ATT&CK techniques with several tactics show one.
- **AI follow-ups from Phase 8** ([guide](./ai.md)):
  - **Record the evaluations:** record a real model's answers for `nl2query`
    and `summaries` (`tests/eval/ai/run_ai_eval.py --record`, needs an API
    key) and commit the baseline, so the CI gate starts enforcing.
  - **Share the limits:** the rate limit and the in-request budget check are
    per API process. Move both to a shared counter (Redis or ClickHouse) so
    replicas and parallel requests can't overshoot.
  - **Redact renamed values:** redact at the query layer too, so values
    renamed in a query (`| eval v = attrs.password`) are still covered.
  - **Enforce API key scopes:** they are set at login but never checked
    (pre-existing, every route).
  - **Fix the rule-based NLQ:** give it per-intent permission checks and
    parameterised SQL, then open the fallback to `ai:read` again.
  - **Get a human sign-off** of the security review before enabling AI in
    production.
- **Content pack follow-ups from Phase 7** ([guide](./packs.md)): packs
  come only from the catalogue shipped with the deployment; add a registry
  (or git source) with signed packs, and per-tenant uploads. An install that
  fails part-way is not rolled back: objects written so far stay and no
  manifest is saved, so the next plan reports them as conflicts. Let the
  installer choose which rules to enable. An object kept when a pack is
  removed shows as a conflict on reinstall; offer to adopt it. Windows
  events must arrive as JSON (NXLog or Winlogbeat), not XML or WEF; the
  Workspace pipeline reads only the first event of an activity; CRI partial
  lines are not joined. Good first issues: more packs (PostgreSQL, MySQL,
  Cisco ASA, Palo Alto, Fortinet, Microsoft 365, Azure activity, GCP audit,
  GitHub audit, Cloudflare), each from `packages/packs/_template`.
- **Query language follow-ups from Phase 6** ([reference](./query-language.md)):
  questions that read `attrs` over 100 M events take 6–16 s on 4 vCPUs,
  because every event's JSON is decompressed and scanned
  ([benchmarks](./benchmarks/README.md)). Frequently queried attributes
  need typed columns materialized from `attrs` (or ClickHouse's JSON type),
  which the compiler would then read instead. The hourly counts cover only
  service, level and status (not host or attributes). `join` reads at most
  50,000 subsearch rows and keeps one row per key. The saved-search
  scheduler runs inside each API process, so with several replicas each
  would run every search (needs a lease or a separate worker). Dashboard
  panels have one query each and no per-panel time range. The query builder
  writes `where`, `stats`, `timechart`, `sort` and `head` only. Queries the
  first LogforgeQL accepted still run on the original engine.
- **Per-request quota mutations.** Every ingest request runs
  `ALTER TABLE tenant_quotas_mt UPDATE ...`. ClickHouse mutations are
  heavyweight and queue up under load; this is the likely cause of the
  several-fold run-to-run swings in the end-to-end benchmarks. Counters
  belong in an append-only table (or Redis) summed on read.
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
