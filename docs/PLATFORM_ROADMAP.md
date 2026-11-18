# Platform roadmap: from log store to a unified, AI-assisted security and observability platform

This is the long-range product plan. It breaks the work into small phases
(2–4 weeks each for a team of 2–3 engineers), each with a clear outcome,
concrete deliverables, the existing code it builds on, and acceptance
criteria. Short-term, claimable tasks stay in [ROADMAP.md](./ROADMAP.md);
when a phase starts, its deliverables should be split into issues there.

- [Vision and positioning](#vision-and-positioning)
- [Principles](#principles)
- [Where we start](#where-we-start)
- [Phase overview](#phase-overview)
- Phases: [0](#phase-0--foundations-and-measurement) ·
  [1](#phase-1--detection-engine-v2-thresholds-sequences-and-backtesting) ·
  [2](#phase-2--cases-and-the-investigation-workflow) ·
  [3](#phase-3--threat-intelligence-and-enrichment) ·
  [4](#phase-4--ingest-pipelines-the-logstash-layer) ·
  [5](#phase-5--common-schema-and-search-time-fields) ·
  [6](#phase-6--query-language-and-analytics-v2) ·
  [7](#phase-7--content-packs) ·
  [8](#phase-8--ai-foundation) ·
  [9](#phase-9--ai-wave-1-ask-triage-parse) ·
  [10](#phase-10--ai-wave-2-investigate-and-author) ·
  [11](#phase-11--entity-analytics-and-ueba) ·
  [12](#phase-12--storage-tiers-and-scale) ·
  [13](#phase-13--response-and-integrations) ·
  [14](#phase-14--enterprise-readiness)
- [Releases](#releases)
- [Metrics we track](#metrics-we-track)
- [Risks](#risks)
- [What we deliberately do not build](#what-we-deliberately-do-not-build)

---

## Vision and positioning

**Splunk-grade search and detection for teams that can't afford Splunk, with
AI that shows its evidence.**

Elastic (Logstash + Elasticsearch + Kibana + Elastic Security) and Splunk
(Enterprise + Enterprise Security + SOAR) win on one thing above all: a
**closed loop** — collect → parse → store → search → detect → investigate →
respond — in one product, with an ecosystem of content for common sources.
Logforge should deliver that same loop for small and mid-sized teams, and
differentiate on three things those products are weak at for this audience:

1. **Cost.** ClickHouse storage and compute are a fraction of an
   Elasticsearch or Splunk-licence footprint. Tiered storage makes long
   retention affordable.
2. **Honesty.** Detections are verified against fixtures before they are
   enabled, ATT&CK coverage is computed from what actually runs, and every AI
   answer cites the events it is based on.
3. **Simplicity.** One `./deploy.sh`, multi-tenant from day one, content packs
   that make a new source useful in minutes.

We do **not** aim for feature parity with Elastic or Splunk. Each phase below
is chosen because it closes part of that loop for the target user.

## Principles

These apply to every phase and are part of every phase's acceptance criteria.

- **Evidence over claims.** No feature is described as "AI" or "detection" in
  the UI or docs until it has an evaluation (see Phase 0) with published
  numbers.
- **Privacy by default.** AI providers are pluggable and **off by default**.
  With no provider configured, every feature still works (with non-AI
  fallbacks) and no data leaves the deployment.
- **Everything as code.** Rules, pipelines, packs, dashboards and playbooks
  are versioned YAML/JSON that can live in git, be reviewed, and be tested in
  CI.
- **Tenant isolation is non-negotiable.** Every new table carries
  `customer_id` in its sort key; every new endpoint goes through the existing
  tenant middleware and gets a route test proving cross-tenant access fails.
- **Each phase ships.** A phase ends with a release note, docs, an updated
  OpenAPI spec, route tests and (for UI work) a Playwright spec in CI.

## Where we start

What exists today, and how mature it is. "Builds on" sections below refer to
these files.

| Area | Today | Maturity | Main code |
|---|---|---|---|
| Ingest | JSON, batch, bulk, syslog, nginx, CEF, text, OTLP; Vector/Fluent Bit/Fluentd recipes | Solid | `routers/ingestion.py`, `parsers.py`, `packages/shipper-recipes/` |
| Normalisation | Index-time field normalisation with a per-source schema registry | Partial: fixed mappings, no user pipelines | `services/high_performance_normalizer.py`, `routers/schema_registry_api.py`, `services/smart_ingestion_service.py` |
| Storage | ClickHouse hot tables, MinIO archives, per-tenant quotas | Partial: no tiering policy, no archive search | `services/storage_service.py`, `infra/docker/clickhouse/migrations/` |
| Search | LogforgeQL, query cache, live tail | Solid core, limited analytics | `query_engine.py`, `services/query_service.py`, `routers/query.py` |
| Detection | Sigma engine (incl. `count()` aggregation), ~270 fixture-verified rules, ATT&CK coverage API | Solid single-event; aggregation rules can't pass the loader gate | `sigma_engine.py`, `sigma_condition.py`, `mitre_default_loader.py`, `packages/rules/` |
| Alerting | Threshold/pattern rules, correlation and dedup, notifications | Partial | `services/alert_service.py`, `services/alert_correlation_service.py`, `events/management/matchers/` |
| SIEM workflow | Security events with ack/investigate/resolve, threat hunting campaigns | Partial: no cases, no entity view | `routers/security_api.py`, `services/security_service.py` |
| Threat intel | IOC store and detection-time matching | Partial: no feeds | `threat_intel.py` |
| Observability | Traces, metrics, service map, APM views | Solid | `routers/observability_api.py` |
| Analytics / "AI" | Statistical anomaly detection, heuristic RCA, rule-based NLQ, keyword-template answers | Statistical parts real; no language model | `services/anomaly_detector.py`, `services/rca_engine.py`, `services/nlq_processor.py`, `services/ai_service.py` |
| Platform | Multi-tenant, RBAC, API keys, audit, plans/features, CI with live-stack tests | Solid | `authn_authz_middleware.py`, `services/subscription_service.py` |

## Phase overview

| # | Phase | Size | Depends on | Outcome |
|---|---|---|---|---|
| 0 | Foundations and measurement | 2–3 w | — | Known-good baseline, benchmark and evaluation harnesses |
| 1 | Detection engine v2 | 3–4 w | 0 | Threshold, sequence and entity rules; backtesting; detection-as-code |
| 2 | Cases and investigation workflow | 3 w | 1 | Alerts become owned, tracked investigations |
| 3 | Threat intelligence and enrichment | 2–3 w | 0 | Live IOC feeds, GeoIP/ASN, intel hits on events |
| 4 | Ingest pipelines (Logstash layer) | 4 w | 0 | User-defined parse/enrich/route/drop pipelines with simulation and DLQ |
| 5 | Common schema and search-time fields | 3 w | 4 | One schema across sources; extract fields at search time |
| 6 | Query language and analytics v2 | 3 w | 5 | Stats, timecharts, lookups, scheduled searches |
| 7 | Content packs | 3 w + ongoing | 1, 4, 5 | Install a source in minutes: parsers + rules + dashboards |
| 8 | AI foundation | 2–3 w | 0 | Provider interface, guardrails, audit, evaluation wiring |
| 9 | AI wave 1: ask, triage, parse | 4 w | 6, 8 | Natural-language search, alert summaries, parser generation |
| 10 | AI wave 2: investigate and author | 4 w | 2, 9 | Investigation copilot, AI-drafted detections gated by tests |
| 11 | Entity analytics and UEBA | 4 w | 2, 3, 5 | Entity pages, risk scores, log pattern clustering |
| 12 | Storage tiers and scale | 4 w | 5 | Hot/cold tiers, archive search, retention policies, HA deploy |
| 13 | Response and integrations | 3 w | 2 | Actions, playbooks, ticketing and chat integrations |
| 14 | Enterprise readiness | ongoing | — | SSO, fine-grained RBAC, Helm, backups |

Phases 3, 4 and 8 can run in parallel with phases 1–2 if the team is larger.

---

## Phase 0 — Foundations and measurement

**Goal:** a trustworthy baseline to measure every later phase against.

> **Status: done (2026-11-17).** All deliverables shipped and their
> acceptance criteria are met:
>
> - **Known gaps cleared:** `count()` rules load through batch fixtures;
>   gzip request bodies are accepted; failed UI mutations reject, with a
>   test over every call site; Playwright specs 01–04 were rewritten and the
>   full suite (43 tests) runs in CI. This work also fixed three bugs: Sigma
>   rules couldn't see fields under `attrs`, `/v1/logs` dropped attributes,
>   and `apiClient.get` dropped `{ params }` filters.
> - **Detection evaluation** with a CI regression gate
>   ([tests/eval/detection](https://github.com/miteshpant/Logforge/tree/main/tests/eval/detection)).
> - **Performance benchmarks**, with results published in
>   [benchmarks](./benchmarks/README.md).
> - **AI evaluation harness skeleton**
>   ([tests/eval/ai](https://github.com/miteshpant/Logforge/tree/main/tests/eval/ai)).
> - **Docs site** (MkDocs on GitHub Pages).
>
> Baseline exit metrics:
>
> | Metric | Value |
> |---|---|
> | Sustained ingest, one client | 277 events/s (4 vCPU, single node) |
> | Ingest → searchable | 36.8 s |
> | Query p95 at 10 M rows | 117–311 ms |
> | Detection scenarios detected | 10 / 12 |
> | False positives | 63.5 per 1,000 benign events, all from one rule |
>
> Follow-ups are in [ROADMAP.md](./ROADMAP.md): the ingest bottleneck, the
> noisy sudo rule, and four detection gaps (the last two fixed in Phase 1). Public datasets (e.g. OTRF
> Security-Datasets) are not in the corpus yet; adding them belongs with
> Phase 1, where the rules they exercise land.

**Why first:** later phases (correlation, AI) make claims about accuracy and
speed. Without a harness, those claims can't be checked, and regressions go
unnoticed.

### Deliverables

1. **Clear the known gaps** from [ROADMAP.md](./ROADMAP.md) that later phases
   depend on:
   - batch fixtures in the rule loader, so `count()` rules (brute force) load;
   - gzip request decoding with a decompressed-size limit;
   - the `apiClient` `{ success: false }` audit across the UI;
   - rewrite Playwright specs 01–04 so the whole UI suite runs in CI.
2. **Detection evaluation harness** (`tests/eval/detection/`):
   - a labelled corpus: benign logs (several days of realistic traffic per
     source) and attack scenarios mapped to ATT&CK techniques (public datasets
     such as Mordor/OTRF Security-Datasets, plus scripted scenarios);
   - a runner that replays the corpus through ingestion and reports, per rule
     and per technique: true positives, false positives, alerts per day;
   - a CI job that fails if precision or recall drops for any rule.
3. **Performance benchmarks** (`tests/bench/`): ingest throughput (events/s
   per core), end-to-end latency (ingest → searchable → alert), query p50/p95
   for a fixed query set at 10 M / 100 M / 1 B rows. Results are published per
   release.
4. **AI evaluation harness skeleton** (`tests/eval/ai/`): dataset format and
   scorer for NL→query, summarisation and rule drafting (filled in Phase 8).
5. **Docs site:** turn `docs/` into a browsable site (MkDocs or Docusaurus on
   GitHub Pages, next to the Redoc API reference).

### Acceptance criteria

- Every rule in `packages/rules/` and the vendored content has a measured
  false-positive rate on the benign corpus.
- Benchmark numbers for the current release are published in the docs.
- CI runs the full Playwright suite.

### Exit metrics

- Baseline: ingest events/s/core, p95 query latency, alert false-positive
  rate per 1,000 benign events.

---

## Phase 1 — Detection engine v2: thresholds, sequences and backtesting

**Goal:** detect attacks that are only visible across many events, which is
what separates a SIEM from grep with alerts.

> **Status: done (2026-11-17), with the gaps listed below.**
>
> - **Thresholds, sequences, entity scope:** Sigma correlation rules
>   (`event_count`, `value_count`, `value_sum`, `temporal`,
>   `temporal_ordered`) grouped by any fields, chained correlations, and
>   `generate: false` building blocks. They run in the live path with bounded
>   per-group state (`apps/api/correlation.py`); `count()` rules now window
>   across ingest batches.
> - **Fixture gate v2:** timed fixture timelines, replayed through the
>   runtime (`detection_replay`), for count and correlation rules. The eval
>   harness and AI eval use the same replay.
> - **Content:** 12 new aggregation/sequence rules (password spray, brute
>   force then success, account-lockout burst, MFA fatigue, web content
>   scanning, discovery burst, discovery then LSASS dump, sudo-failure
>   burst, lateral logon fan-out, archive then cloud upload, outbound
>   volume, mass file encryption), rules for the four Phase 0 gaps, and a
>   quiet pe001.
> - **Backtesting:** `POST /v1/security/rules/{id}/backtest`, with a
>   Sigma→ClickHouse prefilter that only narrows and the engine deciding
>   every match.
> - **Suppression and tuning:** exclusions, throttles, and
>   `GET /v1/security/rules/{id}/tuning-suggestion` from false-positive
>   verdicts.
> - **Detection-as-code:** `POST /v1/security/rules/sync` (gate + optional
>   backtest, all-or-nothing), YAML export, `scripts/rules_sync.py` for CI
>   ([guide](./detection-as-code.md)).
>
> | Acceptance criterion | Result |
> |---|---|
> | Brute force + ≥10 new aggregation/sequence rules through the gate and the evaluation | 13 aggregation/sequence rules; 24/24 scenarios detected; 0 false positives on the benign corpus |
> | 7 days / 100 M events backtest < 60 s | 20–27 s (5 s with no matches), peak RSS < 200 MB ([details](./benchmarks/backtest.md)) |
> | Bounded streaming state | Capped per group and by group count (LRU); 200k-event soak test. No 24 h soak yet |
>
> | Exit metric | Phase 0 | Phase 1 |
> |---|---|---|
> | ATT&CK techniques with verified rules | 360 | 362 |
> | Aggregation/sequence rules | 1 | 13 |
> | Scenarios detected | 10 / 12 | 24 / 24 |
> | False positives per 1,000 benign events | 63.5 | 0 |
>
> Most new rules add cross-event detection for techniques the vendored rules
> already tagged, so the technique count barely moves. The scenarios were
> written alongside the rules, which flatters the detection numbers; public
> datasets (OTRF) remain the honest test.
>
> **Not done** (tracked in [ROADMAP.md](./ROADMAP.md)): `until` abort
> conditions; impossible travel (needs GeoIP, Phase 3); correlation over
> alerts ("3+ distinct techniques on one host"); server-side git pull (sync
> is pushed from CI); a 24 h soak; correlation state shared across API
> replicas.

### Deliverables

1. **Threshold and aggregation rules** as first-class rules:
   `count`, `distinct_count`, `sum` over a sliding window, grouped by fields
   (`count() >= 10 by src_ip within 5m`). The Sigma engine already parses
   these; add the streaming state (per group, per window) in the matchers with
   bounded memory and eviction.
2. **Sequence rules** ("A then B then C by the same entity within T"), in the
   spirit of EQL sequences and Sigma correlation rules:
   - YAML syntax that references existing rules or inline selections;
   - optional `until` (abort) condition;
   - state held per entity key with TTL.
3. **Entity-scoped correlation:** rules that fire on combinations of alerts
   for the same user/host/IP (e.g. "3+ distinct techniques on one host in
   1 h"). Reuse grouping from `services/alert_correlation_service.py`.
4. **Backtesting:** run a rule (new or edited) over the last N days of stored
   data before enabling it, and show how many alerts it would have produced,
   with samples. API: `POST /v1/security/rules/{id}/backtest`.
5. **Suppression and tuning:** per-rule allowlists (field = value), throttling
   ("one alert per entity per hour"), and a "mark false positive → suggest
   exclusion" flow.
6. **Detection-as-code:** sync rules from a git repository (pull on schedule
   or webhook), with the fixture gate and backtest run on every change; rules
   edited in the UI can be exported as YAML.
7. **Fixture gate v2:** batch fixtures (event lists) for aggregation and
   sequence rules, so every rule type is verified before it is enabled.

### Builds on

`sigma_engine.py`, `sigma_condition.py`, `events/management/matchers/`,
`services/alert_correlation_service.py`, `mitre_default_loader.py`.

### Acceptance criteria

- The brute-force rule and at least 10 new aggregation/sequence rules
  (password spraying, impossible travel, privilege escalation chains,
  data-staging-then-exfiltration) load through the gate and pass the Phase 0
  evaluation with a measured false-positive rate.
- Backtest of a rule over 7 days of 100 M events completes in under 60 s.
- Streaming state is bounded: memory stays flat under a 24 h soak test.

### Exit metrics

- ATT&CK techniques covered by verified rules (up from the current baseline).
- Alerts per day on the benign corpus (should not rise).

---

## Phase 2 — Cases and the investigation workflow

**Goal:** turn alerts into owned, tracked investigations, which is the daily
workflow of a SOC analyst.

> **Status: done (2026-11-18), with the gaps listed below.**
>
> - **Case model and storage:** `apps/api/cases.py` holds the status flow,
>   SLA timestamps and analyst actions. Storage is `cases_mt` (versioned
>   rows) plus `case_events_mt`, an append-only timeline that doubles as the
>   audit trail (migration 017).
> - **Automatic grouping:** each detection joins the open case for its
>   source IP, host or user, taken from the correlation group when there is
>   one, within 24 h. Low alerts don't open cases.
> - **Analyst actions** (`/v1/security/cases`): assign, notes with
>   @mentions, status with a close reason, tags, severity, evidence
>   (searches, events, traces, log lines, links), attach alerts, merge,
>   split and bulk actions. Closing sets the alerts' verdicts, so
>   false-positive closes feed the Phase 1 tuning suggestions.
> - **SLA and overview:** mean and median time to acknowledge and resolve per
>   severity, SLA breaches, ageing, analyst load and alerts per case. The
>   audit trail exports as JSON or CSV.
> - **UI:** a Cases list with the SOC overview and a case detail page with
>   timeline, alerts, entities and evidence. Cases can be created from an
>   alert (Events) and from a search (Log Explorer); the README screenshots
>   show both pages.
>
> | Acceptance criterion | Result |
> |---|---|
> | Alert → case → evidence → resolution in the product, covered by a Playwright spec | `apps/ui/tests/09-cases.spec.ts`: ingested failed logins open a case on their own; the analyst notes, pins evidence, investigates, resolves; the alerts carry the verdict |
> | Grouping reduces items needing triage by a measured percentage | 64 alerts → 14 cases on the evaluation corpus: **78% fewer items** (`eval_harness.grouping_report`, CI-tested) |
>
> | Exit metric | Result |
> |---|---|
> | Alerts per case | 4.6 on the evaluation corpus |
> | Mean time to acknowledge / resolve | Reported live by `/v1/security/cases/metrics`. Demo and test runs take seconds, so they say nothing yet; real numbers need real analysts |
>
> **Not done** (tracked in [ROADMAP.md](./ROADMAP.md)): merge and split are
> API-only (no UI yet); @mentions are recorded but not delivered (no
> per-user notifications); "create case" exists on Events and the Log
> Explorer but not on every page showing an alert; lateral movement across
> two hosts opens two cases (no source→destination linking); the grouping
> lock is per API process; SLA targets are fixed.

### Deliverables

1. **Case model** (`cases_mt`, `case_events_mt`): title, severity, status
   (new → investigating → contained → resolved / false positive), assignee,
   linked alerts, linked entities, tags, SLA timestamps.
2. **Automatic case creation and grouping:** alerts for the same entity and
   time window are attached to an open case instead of creating noise. Uses
   the Phase 1 correlation keys.
3. **Case timeline:** alerts, notes, status changes, and pinned evidence
   (saved log searches, individual events, traces) in one chronological view.
4. **Analyst actions:** assign, comment (with @mentions), merge and split
   cases, bulk actions, close with a reason (the reason feeds tuning in
   Phase 1).
5. **SLA and metrics:** time to acknowledge and time to resolve per severity;
   a SOC overview dashboard (open cases, ageing, analyst load).
6. **Audit:** every case change is recorded and exportable.
7. **UI:** case list, case detail page, "create case from alert/search"
   everywhere an alert or event is shown.

### Builds on

`routers/security_api.py` (event ack/investigate/resolve endpoints become case
actions), `services/notification_service.py`, existing audit trail.

### Acceptance criteria

- An analyst can go from alert → case → evidence → resolution without leaving
  the product; covered by a Playwright spec.
- Grouping reduces items needing triage by a measured percentage on the
  evaluation corpus.

### Exit metrics

- Mean time to acknowledge and resolve (on demo/benchmark scenarios).
- Alerts per case (higher = less noise).

---

## Phase 3 — Threat intelligence and enrichment

**Goal:** know when an event involves something known to be bad, and give
every IP and domain context.

### Deliverables

1. **Feed framework:** scheduled pulls with per-feed config (URL, auth,
   interval, confidence, TTL), deduplication and expiry. Feeds:
   abuse.ch (URLhaus, ThreatFox, Feodo), AlienVault OTX, MISP (API), and
   generic STIX/TAXII 2.1 and CSV/plain lists.
2. **Ingest-time matching:** look up IPs, domains, URLs and hashes against the
   IOC set during normalisation (in-memory filter + ClickHouse dictionary),
   and stamp matches onto the event (`threat.indicator.*`).
3. **Retro-hunting:** when a new IOC arrives, search recent history for it and
   raise alerts for past matches.
4. **Enrichment processors:** GeoIP and ASN (MaxMind GeoLite2 or DB-IP Lite,
   downloaded by the operator), reverse DNS (optional, cached), and asset or
   user lookups from CSV.
5. **UI:** feed management, indicator search, "seen in your data" counts on
   each indicator, intel badges on events and alerts.

### Builds on

`threat_intel.py` (storage and detection-time matching), `threat_intel_mt`,
the threat-intel page.

### Acceptance criteria

- Adding the abuse.ch feeds produces matches on a replayed malicious corpus,
  and none on the benign corpus beyond the feed's own error rate.
- Ingest throughput drops by less than 10% with enrichment enabled (Phase 0
  benchmark).

---

## Phase 4 — Ingest pipelines (the Logstash layer)

**Goal:** let users shape any log on the way in, without code changes.
This is the single biggest functional gap against Logstash and Elastic ingest
pipelines.

### Deliverables

1. **Pipeline model:** an ordered list of processors, stored per tenant,
   versioned, with conditions (`if: source == "nginx"`). Processors:
   - parse: `json`, `kv`, `csv`, `regex`/`grok` (with a bundled pattern
     library), `syslog`, `cef`, `leef`, `date`, `user_agent`;
   - transform: `rename`, `set`, `remove`, `convert`, `lowercase`, `split`,
     `script` (sandboxed expressions only, no arbitrary code);
   - enrich: `geoip`, `lookup` (CSV/table), `threat_intel` (Phase 3);
   - privacy: `mask`/`hash` for PII (emails, card numbers, tokens);
   - flow: `drop` (noise reduction before storage), `route` (to a different
     table, retention class or tenant-defined index), `fail`.
2. **Simulation API and UI:** `POST /v1/pipelines/simulate` with sample
   events returns the output of each processor step, like Elastic's
   `_simulate`. The editor shows before/after side by side.
3. **Routing from shippers:** pick a pipeline by source, by shipper header, or
   by matching rules; default pipelines for the existing parsers.
4. **Dead-letter queue:** events that fail a pipeline go to a DLQ topic and
   table with the error, and can be replayed after the pipeline is fixed.
5. **Observability of pipelines:** per-processor throughput, error and drop
   counts, and latency, shown in the UI.
6. **Migration:** express today's hard-coded parsers (`parsers.py`) and
   schema-registry mappings as built-in pipelines, so there is one mechanism.

### Builds on

`parsers.py`, `services/high_performance_normalizer.py`,
`routers/schema_registry_api.py`, the Redpanda event bus.

### Acceptance criteria

- A user can onboard an unknown log format end to end (sample → pipeline →
  searchable fields) in the UI, covered by a Playwright spec.
- Pipelines with 10 processors keep ingest within 20% of the Phase 0
  baseline.
- No event is silently lost: failures land in the DLQ with the reason.

---

## Phase 5 — Common schema and search-time fields

**Goal:** one vocabulary across sources, so a rule, dashboard or question
works no matter where the data came from.

### Deliverables

1. **Adopt a common schema.** Recommendation: **OCSF** (vendor-neutral, used
   by AWS Security Lake and others) for security events, with OpenTelemetry
   semantic conventions for observability data. Publish the mapping of today's
   fields to it.
2. **Field catalogue:** every field seen per tenant, with type, source,
   cardinality and example values; drives autocomplete and the field sidebar.
3. **Search-time extraction** in LogforgeQL: `| parse "<pattern>"`,
   `| rex field=msg "(?<user>\w+)"`, `| json`, so users can query fields they
   didn't extract at ingest (Splunk's schema-on-read).
4. **Rules on the schema:** rules and dashboards reference schema fields;
   packs (Phase 7) map sources into it.
5. **Field explorer UI:** top values, distribution, "add to query" from any
   field.

### Acceptance criteria

- The same detection (e.g. failed logins) works unchanged across Linux auth,
  Windows Security, Okta and an application log once each is mapped.
- Search-time extraction on 10 M rows completes within 2× the cost of the
  same query on an ingest-time field.

---

## Phase 6 — Query language and analytics v2

**Goal:** answer analytical questions, not just find lines. This is what
analysts expect from SPL or ES|QL.

### Deliverables

1. **Pipeline commands** in LogforgeQL: `stats` (count, sum, avg, percentiles,
   distinct count) `by`, `timechart`, `top`, `rare`, `eval`, `where`, `sort`,
   `head`, `dedup`, `fields`, `rename`, `bin`.
2. **Lookups and joins:** lookup tables (uploaded CSV or managed lists) and a
   bounded `join` between searches.
3. **Saved and scheduled searches:** run on a schedule, alert on results, or
   email/export reports.
4. **Dashboards from queries:** any query result can become a panel;
   dashboard variables (time, service, host).
5. **Performance:** use materialized views and skip indexes for common
   aggregations; query cost estimation and limits per plan.
6. **Language reference and query builder** in the docs and UI.

### Builds on

`query_engine.py`, `services/query_service.py`,
`services/dashboard_service.py`.

### Acceptance criteria

- A published set of 30 analyst questions (e.g. "top 10 source IPs by failed
  logins per hour this week") are each answerable in one query.
- p95 latency for that set stays within the Phase 0 targets at 100 M rows.

---

## Phase 7 — Content packs

**Goal:** make a new data source useful in minutes. Content is why Splunk
and Elastic are sticky, and it's where an open-source community can
contribute most.

### Deliverables

1. **Pack format:** a versioned directory containing pipelines (Phase 4),
   schema mappings (Phase 5), rules with fixtures (Phase 1), dashboards,
   saved searches, alert templates and sample data.
2. **Pack manager:** list, install, upgrade and remove per tenant; show what
   a pack changes before installing; keep local customisations on upgrade.
3. **Pack CI:** every pack is validated in CI: its sample data goes through
   its pipelines, the rules' fixtures pass, and dashboards' queries run.
4. **First packs** (chosen for what small companies run):
   - Linux (auth.log, syslog, auditd)
   - Web servers (nginx, Apache)
   - AWS CloudTrail and VPC Flow Logs
   - Okta and Google Workspace audit
   - Windows Security and Sysmon
   - Kubernetes audit and container logs
5. **Contributor guide** for writing a pack, plus a template.

### Acceptance criteria

- Installing a pack and pointing a shipper at the source yields parsed
  events, a working dashboard and enabled rules within 15 minutes (timed
  walkthrough in the docs).

---

## Phase 8 — AI foundation

**Goal:** the plumbing that makes every AI feature safe, private, auditable
and measurable.

### Deliverables

1. **Provider interface** (`apps/api/ai/providers/`): one interface for chat
   and tool calling, with adapters for an OpenAI-compatible endpoint (covers
   many hosted and local servers), Anthropic, and Ollama/local models.
   Configured per deployment and enabled per tenant. **No provider is enabled
   by default.**
2. **Grounding through tools, not raw data:** models call read-only tools
   (run a LogforgeQL query, fetch an alert, list a case's events, look up an
   indicator) that go through normal tenant authorisation, instead of being
   handed bulk logs.
3. **Citations:** every AI output carries references to the events, alerts or
   query results it used; the UI renders them as links. Outputs without
   citations are flagged.
4. **Data controls:** redaction of configured fields before anything is sent
   to a provider; per-tenant opt-in; a visible indicator when an external
   model is used.
5. **Audit and cost controls:** log every prompt, tool call and response
   (with retention); per-tenant token budgets and rate limits.
6. **Evaluation wiring:** the Phase 0 AI harness runs each feature against
   its dataset in CI (with a recorded or local model) and blocks regressions.
7. **Fallbacks:** with AI disabled, the existing rule-based NLQ
   (`services/nlq_processor.py`) and templates stay the behaviour.

### Acceptance criteria

- A security review signs off on data flow and tenant isolation of AI calls.
- AI can be disabled per tenant and globally, verified by route tests.

---

## Phase 9 — AI wave 1: ask, triage, parse

**Goal:** the first AI features, each useful on day one and each measured.

### Deliverables

1. **Natural language → LogforgeQL.** The user asks a question; the AI
   produces a query using the field catalogue (Phase 5), shows it, explains
   it, and the user runs or edits it. The query, not the model, produces the
   answer.
   - Eval: execution accuracy on a set of 200+ question/query pairs per
     schema; target ≥ 85% before release.
2. **Alert and case triage summaries.** For an alert or case: what happened,
   why it matters (ATT&CK context), affected entities, related activity, and
   suggested next steps, with citations.
   - Eval: analyst-rated helpfulness and factual accuracy on a labelled set;
     zero uncited claims in automated checks.
3. **Parser and pipeline generation.** Paste sample logs; the AI drafts a
   pipeline (Phase 4), validated by the simulation API before it's offered.
   - Eval: fields correctly extracted on a held-out set of formats.
4. **Log explanation:** "explain this event" for unfamiliar log lines.

### Builds on

Phase 8, `services/nlq_processor.py`, `services/ai_service.py` (whose
template answers are replaced by grounded ones).

### Acceptance criteria

- Each feature meets its evaluation target and has its numbers in the docs.
- Every feature works (with reduced capability) when AI is disabled.

---

## Phase 10 — AI wave 2: investigate and author

**Goal:** move from answering questions to doing investigative work, under
human control.

### Deliverables

1. **Investigation copilot.** From a case or an entity, the copilot plans
   and runs read-only searches ("what else did this IP touch?", "what
   happened on this host before the alert?"), builds a timeline, proposes
   hypotheses, and pins evidence to the case. Every step is visible and
   reversible; the analyst approves pinning and conclusions.
2. **Detection drafting gated by tests.** Describe a behaviour or paste an
   attack log; the AI drafts a Sigma rule **and** its fixtures; the rule must
   pass the fixture gate (Phase 1) and a backtest before it can be enabled.
   "AI drafts, the gate verifies."
3. **Case reports:** incident summaries for management and post-incident
   reviews, generated from the case timeline with citations.
4. **Replace heuristic RCA output** in `services/rca_engine.py` with grounded,
   cited analysis where a provider is configured, keeping the statistical
   correlation as input.

### Acceptance criteria

- On the evaluation scenarios, the copilot finds the root-cause events in
  ≥ 80% of cases with no fabricated evidence.
- ≥ 70% of AI-drafted rules for the evaluation behaviours pass the gate on
  the first or second attempt; 0% are enabled without passing.

---

## Phase 11 — Entity analytics and UEBA

**Goal:** see risk per user, host, IP and service, not just per alert.

### Deliverables

1. **Entity model:** entities extracted from events (user, host, IP, service,
   cloud account), with first/last seen and relationships.
2. **Entity pages:** everything about one entity: timeline, alerts, cases,
   intel hits, anomalies, related entities.
3. **Risk scoring:** a score per entity combining alert severity, ATT&CK
   tactic progression, intel hits and anomalies, with decay over time and an
   explanation of the contributing factors.
4. **Behaviour baselines:** per-entity baselines (login times, locations,
   volumes) using `services/anomaly_detector.py` and
   `services/multi_metric_anomaly_detector.py`; peer-group comparison.
5. **Log pattern clustering** (no language model needed): group log lines
   into templates (Drain-style), show new and rare patterns, and alert on a
   sudden new pattern.

### Acceptance criteria

- On the evaluation corpus, the compromised entities rank in the top 5 by
  risk within the scenario window.
- Pattern clustering reduces 1 M log lines to a browsable set of templates
  in under 30 s.

---

## Phase 12 — Storage tiers and scale

**Goal:** make long retention cheap and the platform resilient.

### Deliverables

1. **Tiered storage:** hot (ClickHouse local disks), warm (ClickHouse
   S3-backed storage policies), cold (Parquet archives in object storage),
   with per-tenant, per-data-type retention policies.
2. **Archive search and rehydration:** query cold data in place (ClickHouse
   reading Parquet from S3) or rehydrate a time range back to hot.
3. **Cost visibility:** per-tenant storage and ingest by source and tier,
   with projections; links to Phase 4 `drop` rules to cut noise.
4. **Scale-out:** ClickHouse replication and sharding, Redpanda replication,
   stateless API replicas, documented capacity sizing.
5. **Kubernetes:** a Helm chart (and later an operator) alongside compose.
6. **Backup and restore** for ClickHouse and configuration, tested in CI.

### Builds on

`services/storage_service.py`, MinIO archives, storage quota sync.

### Acceptance criteria

- One year of retention for a 50 GB/day tenant costs less than a published
  target (documented reference architecture).
- Losing one ClickHouse replica or API pod causes no data loss and no
  downtime in a chaos test.

---

## Phase 13 — Response and integrations

**Goal:** act on findings, not only observe them (SOAR-lite).

### Deliverables

1. **Actions:** webhook, Slack, Microsoft Teams, PagerDuty/Opsgenie, email,
   Jira/GitHub issues; with templates and secrets management.
2. **Playbooks:** YAML workflows triggered by case or alert conditions,
   with steps (enrich, notify, create ticket, run search, wait for approval).
   Containment steps (disable user, block IP) only through integrations and
   always with human approval.
3. **Bi-directional ticket sync:** case status mirrors the external ticket.
4. **Exports and reporting:** ATT&CK coverage (Navigator layer export),
   compliance reports, scheduled PDF/CSV reports.

### Acceptance criteria

- A playbook can take an alert to a Slack notification and a Jira ticket, and
  a resolved ticket closes the case, covered by an integration test with
  mocked services.

---

## Phase 14 — Enterprise readiness

**Ongoing, pulled forward when users ask for it.**

- SSO: OIDC first, then SAML; SCIM user provisioning.
- Fine-grained RBAC: per-data-source and per-field access, roles per tenant.
- Auth flows from [ROADMAP.md](./ROADMAP.md): password reset, invites, email
  verification, session revocation.
- Admin UI: billing, feature management and support pages (currently
  placeholders).
- Security hardening: dependency and image scanning in CI, signed releases,
  SBOMs, a published threat model.
- Self-monitoring: Logforge's own metrics in Grafana dashboards and
  OpenTelemetry self-tracing (also on [ROADMAP.md](./ROADMAP.md)).

---

## Releases

| Release | Phases | Story |
|---|---|---|
| **v0.2 "Credible SIEM"** | 0, 1, 2, 3 | Correlation rules, cases and threat intel, all measured |
| **v0.3 "Unified pipeline"** | 4, 5, 6, 7 | Logstash-style pipelines, common schema, analytics, content packs |
| **v0.4 "AI that shows its work"** | 8, 9, 10 | Grounded, cited AI for search, triage, investigation and detection authoring |
| **v1.0 "Platform"** | 11, 12, 13, 14 | Entity risk, tiered storage, response, enterprise features |

Each release has a public changelog, benchmark and evaluation numbers, and a
migration guide.

## Metrics we track

| Area | Metric |
|---|---|
| Detection | Verified ATT&CK techniques covered; precision/recall per rule on the evaluation corpus; false positives per 1,000 benign events |
| Workflow | Mean time to acknowledge/resolve on benchmark scenarios; alerts per case |
| Performance | Ingest events/s/core; ingest → searchable latency; query p95 at 100 M / 1 B rows |
| Cost | Storage per GB ingested per tier; cost per tenant per month at reference volumes |
| AI | NL→query execution accuracy; uncited-claim rate (target 0); copilot root-cause hit rate; AI-drafted rules passing the gate |
| Adoption | Time from install to first alert; packs installed; contributors and community packs |

## Risks

| Risk | Mitigation |
|---|---|
| Scope creep toward Elastic/Splunk parity | Each phase must close part of the collect → respond loop for the target user; anything else goes to "not now". |
| AI hallucinations damage trust in a security product | Tools-not-data grounding, mandatory citations, evaluations gating releases, human approval for any action. |
| Streaming correlation state grows without bound | Bounded per-key state with TTL and eviction; 24 h soak tests in CI. |
| Ingest slowdown from pipelines and enrichment | Phase 0 benchmarks as release gates; compiled processors; drop rules to cut volume. |
| Tenant data leaking through new features | Tenant key in every table's sort key; route tests for cross-tenant denial on every new endpoint; AI tools use normal authorisation. |
| Small team, wide plan | Phases are small and independently shippable; content packs and rules are designed for community contribution. |

## What we deliberately do not build

- Full compatibility with Elasticsearch's query DSL or Splunk's SPL. We take
  their best ideas into LogforgeQL instead.
- A general-purpose SOAR platform. Phase 13 covers the common 80%.
- Autonomous AI response. AI investigates and drafts; humans approve actions.
- An APM agent ecosystem. We ingest OpenTelemetry rather than ship agents.
