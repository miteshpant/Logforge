# Logforge — An Incremental, Open Observability + SIEM Platform

A pragmatic roadmap to build a credible Splunk alternative, step by step.

## Table of Contents

- [Vision & Goals](#vision--goals)
- [Non-Goals (for now)](#non-goals-for-now)
- [High-Level Architecture](#high-level-architecture)
- [Tech Choices](#tech-choices)
- [Delivery Plan (Milestones & Sprints)](#delivery-plan-milestones--sprints)
- [Milestone Details](#milestone-details)
  - [M0: Scaffold & Hello Logs](#m0-scaffold--hello-logs)
  - [M1: Ingestion & Storage MVP](#m1-ingestion--storage-mvp)
  - [M2: Search & Dashboards](#m2-search--dashboards)
  - [M3: Alerts & Integrations](#m3-alerts--integrations)
  - [M4: Security Analytics (SIEM-lite)](#m4-security-analytics-siem-lite)
  - [M5: Traces & Metrics](#m5-traces--metrics)
  - [M6: AI Assistant & RCA](#m6-ai-assistant--rca)
  - [M7: Enterprise Readiness](#m7-enterprise-readiness)
- [Directory Structure](#directory-structure)
- [Local Dev via Docker Compose](#local-dev-via-docker-compose)
- [Configuration](#configuration)
- [APIs (Initial)](#apis-initial)
- [Rule Formats](#rule-formats)
- [Dashboards](#dashboards)
- [Data Model](#data-model)
- [Testing Strategy](#testing-strategy)
- [Performance Targets](#performance-targets)
- [Security & Compliance](#security--compliance)
- [Migration from Splunk](#migration-from-splunk)
- [Pricing Model (suggested)](#pricing-model-suggested)
- [KPIs](#kpis)
- [Risks & Mitigations](#risks--mitigations)
- [Contributing](#contributing)
- [License](#license)

## Vision & Goals

- Build an open, cloud-native platform for logs first, then security analytics and observability — cheaper, simpler, and no lock-in.
- **Win on cost**: object storage tiers + compression + retention policies.
- **Win on simplicity**: SQL-first search; curated dashboards; sane defaults.
- **Win on openness**: OpenTelemetry, Vector/Fluent Bit, ClickHouse, S3-compatible storage.
- **Win on time-to-value**: 15-minute setup; out-of-the-box parsers & content packs.

## Non-Goals (for now)

- Full SOAR with complex playbooks (we'll ship "SOAR-lite" webhooks first).
- Proprietary agents (prefer open shippers) unless there's a clear gap.
- Niche compliance frameworks beyond PCI/SOC 2/HIPAA in MVP.

High-Level Architecture
Shippers (Vector/Fluent Bit/Beats) 
        │
        ▼
    Ingest API  ──►  Kafka/Redpanda  ──►  Transform (Rust/Python)
        │                               (enrich, parse, PII redact)
        ▼
   Hot Store (ClickHouse)  ──►  Cold Store (S3/MinIO)
        │
        ├─► Query API (SQL + filters)
        ├─► Alert Engine (rules + schedules)
        └─► Content Packs (dashboards, detections, parsers)
               │
               ▼
        Web UI (Next.js/React) + AuthN/Z (OIDC)

Tech Choices

Ingestion: HTTP/OTLP (OpenTelemetry), Syslog; brokers: Redpanda (dev) / Kafka (prod).

Transforms: Vector remap + custom processors (Rust for perf, Python for quick wins).

Storage: ClickHouse (hot), S3/MinIO (warm/cold) via table TTL + S3 offload.

APIs: FastAPI (Python) to start; consider Rust for ingest path later.

UI: Next.js (React), Tailwind, shadcn/ui.

Auth: OIDC (Auth0/Keycloak), API Keys for service-to-service.

Infra: Terraform, Helm charts; Docker Compose for local.

Observability of the platform: OpenTelemetry SDKs + Prometheus exporters.

CI/CD: GitHub Actions (lint, test, sec scans, build images).

Delivery Plan (Milestones & Sprints)
Milestone	Scope (short)	Duration	Exit Criteria
M0	Repo scaffold, local env, “hello logs”	1 wk	docker compose up ingests sample logs; basic UI alive
M1	Ingestion + storage MVP	2 wks	HTTP ingest → ClickHouse; searchable via API; 10k EPS on laptop
M2	Search + dashboards	2 wks	SQL/filters; saved searches; 6 starter dashboards
M3	Alerts + integrations	2 wks	Rule engine; Slack/Email/Webhook; alert dedupe/silence
M4	SIEM-lite	3 wks	Sigma-like rules; ATT&CK tagging; 25 detections; TI feed ingest
M5	Traces + metrics	3 wks	OTLP traces/metrics ingest; correlated views
M6	AI assistant & RCA	3 wks	NL→SQL; log summarization; guided RCA workflow
M7	Enterprise	3 wks	RBAC, SSO, multi-tenant, quotas, usage billing

Tip: If solo, run 1-week sprints; if a small team, 2-week sprints with demo at end.

Milestone Details
M0: Scaffold & Hello Logs

Objectives

Bootstrap monorepo, CI, code quality.

Local dev with Docker Compose.

Tasks

Init repo, templates (.editorconfig, pre-commit, black/ruff).

Compose services: clickhouse, minio, redpanda, api, ui.

“Hello logs”: POST /ingest writes to ClickHouse; GET /health.

Acceptance

One command to run stack.

Post sample log, visible in ClickHouse table.

M1: Ingestion & Storage MVP

Objectives

Reliable ingestion, schema-on-read friendly.

Retention strategy (hot→cold).

Tasks

Ingest endpoints: /v1/ingest/logs (JSON, text), /v1/ingest/otlp.

Vector/Fluent Bit recipes.

ClickHouse tables: logs_raw, logs_view (Materialized View).

TTL/partitioning by day; S3 offload to MinIO.

Basic parsers: Nginx, Syslog, App JSON.

Acceptance

10k EPS sustained locally; 7-day hot retention; queries < 1s p50 on 10M rows.

M2: Search & Dashboards

Objectives

Fast search (filters + SQL).

Easy dashboards.

Tasks

Query API: filters (time, service, severity, text), SQL passthrough.

Saved searches & pinned queries.

UI dashboards: Nginx, K8s, Postgres, AWS CloudTrail, App logs, “Errors & Latency”.

RBAC scaffold (roles: viewer, analyst, admin).

Acceptance

Query 30M rows in <2s p50 for filtered search.

At least 6 reusable dashboards.

M3: Alerts & Integrations

Objectives

Rule-based alerting, noise controls.

Tasks

Rule engine (CRON schedule, thresholds, query-based).

Notifications: Email, Slack, Webhook, PagerDuty.

Dedupe (fingerprints), group-by, silence windows, maintenance mode.

Alert UI: create, test, simulate.

Acceptance

Simulate alert against historical window; audit log of notifications.

M4: Security Analytics (SIEM-lite)

Objectives

Detections, enrichment, ATT&CK mapping.

Tasks

Sigma-like YAML for rules; built-in 25 detections (CloudTrail, auth anomalies, firewall).

Threat intel (file, TAXII) → enrich src_ip, hash.

Asset/IP/Identity enrichment tables.

Case management MVP: open/assign/close with notes.

Acceptance

3 live POCs on demo data (brute force, exfil spike, suspicious admin action).

Rule versioning + hit counts.

M5: Traces & Metrics

Objectives

Unified observability.

Tasks

OTLP ingest for traces/metrics.

Service map; link logs ⇄ trace spans (trace_id).

Metrics store (ClickHouse time-series or VictoriaMetrics) with retention.

Acceptance

From a 500 error log, jump to related trace; metrics panel overlays.

M6: AI Assistant & RCA

Objectives

Lower barrier to insights.

Tasks

NL → query translation (templated; later add LLM).

Summarize incident timelines from logs.

RCA wizard: “blast radius”, “first seen”, “top contributing services”.

Acceptance

Analyst can ask: “show spikes in 5xx last 2h by service” and get a chart + query.

M7: Enterprise Readiness

Objectives

Security, scale, governance.

Tasks

SSO (OIDC), fine-grained RBAC, audit trails.

Multi-tenant namespaces, quotas.

Usage metering (ingest GB/day, storage GB, queries).

Backups, DR docs, HA deployment patterns.

Acceptance

Pass basic security review checklist; on-call runbook ready.

Directory Structure
logforge/
  apps/
    api/            # FastAPI services
    ui/             # Next.js frontend
    workers/        # background processors (enrichment, alerts)
  packages/
    sdk-python/     # client SDK
    rules/          # Sigma-like detections
    dashboards/     # JSON dashboard packs
    shipper-recipes/# Vector/FluentBit configs
  infra/
    docker/         # compose files
    helm/           # k8s charts
    terraform/      # cloud infra
  datasets/
    demo/           # synthetic nginx, cloudtrail, auth logs
  docs/
    adr/            # architecture decision records
  .github/
    workflows/

Local Dev via Docker Compose
# 1) Start the stack
docker compose -f infra/docker/compose.yml up -d

# 2) Seed demo data
make seed-demo

# 3) Send a test log
curl -X POST localhost:8080/v1/ingest/logs \
  -H 'Content-Type: application/json' \
  -d '{"ts":"2025-01-01T00:00:00Z","service":"web","level":"error","msg":"oops","trace_id":"abc"}'


Compose services

api:8080 (FastAPI), ui:3000 (Next.js), clickhouse:8123, minio:9000, redpanda:9092.

Configuration

config/logforge.yaml

auth:
  oidc:
    enabled: false
    issuer: ""
    client_id: ""
    client_secret: ""
ingest:
  max_body_mb: 10
  rate_limit_rps: 2000
storage:
  clickhouse_url: http://clickhouse:8123
  hot_retention_days: 7
  warm_to_s3_after_days: 7
  s3:
    endpoint: http://minio:9000
    bucket: logforge
    access_key: minio
    secret_key: minio123
alerts:
  scheduler: "*/2 * * * *"
  sinks:
    slack_webhook: ""
    email_smtp: ""
security:
  pii_redaction:
    enabled: true
    patterns: ["(?i)password=\\S+", "\\b\\d{16}\\b"]

APIs (Initial)

POST /v1/ingest/logs

{
  "ts": "2025-01-01T00:00:00Z",
  "host": "ip-10-0-0-1",
  "service": "checkout",
  "level": "info",
  "msg": "user login",
  "trace_id": "c0ffee",
  "attrs": {"user_id":"123","ip":"1.2.3.4"}
}


POST /v1/query

{
  "range": {"from":"now-1h","to":"now"},
  "filter": {"service":"checkout","level":["error","warn"],"text":"timeout"},
  "group_by": ["service","level"],
  "limit": 1000,
  "sql": null
}


POST /v1/alerts/test

{
  "name":"High 5xx",
  "query":"SELECT count() FROM logs_view WHERE status >= 500 AND ts > now() - INTERVAL 5 MINUTE",
  "threshold":100,
  "compare":"gt",
  "notify":["slack"]
}

Rule Formats

Detection Rule (Sigma-like) — rules/detections/cloudtrail/root-login.yml

id: CT-ROOT-LOGIN
title: AWS Root Account Login
status: stable
logsource:
  product: aws
  service: cloudtrail
detection:
  selection:
    eventName: "ConsoleLogin"
    userIdentity.type: "Root"
  condition: selection
severity: high
mitre:
  tactics: ["TA0001"]
  techniques: ["T1078"]
enrichment:
  - geoip: src_ip
  - ti_ip: src_ip
respond:
  - type: alert
  - type: webhook
    url: ${WEBHOOK_IR}


Alert Rule (threshold) — rules/alerts/high-5xx.yml

name: High 5xx errors
schedule: "*/1 * * * *"
query: >
  SELECT toStartOfMinute(ts) AS m, count() AS c
  FROM logs_view
  WHERE status >= 500 AND ts > now() - INTERVAL 5 MINUTE
  GROUP BY m
threshold:
  compare: "gt"
  value: 100
notify: ["slack","pagerduty"]

Dashboards

Errors & Latency (HTTP status, p50/p95 latency, top URIs)

Kubernetes (pod restarts, container OOMs, node pressure)

Nginx/Ingress (reqs/sec, 4xx/5xx, upstreams)

CloudTrail (CreateUser, AttachPolicy, root login)

Postgres (slow queries, locks)

Auth (failed logins by geo, unusual success outside business hours)

Ship as JSON packs under packages/dashboards/.

Data Model

ClickHouse logs_raw

CREATE TABLE logs_raw (
  ts DateTime64(3, 'UTC'),
  host String,
  service LowCardinality(String),
  level LowCardinality(String),
  msg String,
  trace_id String,
  attrs JSON,
  status UInt16 DEFAULT 0
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ts)
ORDER BY (service, ts)
TTL ts + toIntervalDay(7) TO VOLUME 'cold';


logs_view: materialized view that normalizes common fields and extracts keys from attrs.

Testing Strategy

Unit: parsers, API handlers, rule evaluators.

Integration: ingest → ClickHouse roundtrip; alert firing to sinks.

Load: k6/Gatling scripts for 10k–50k EPS synthetic logs.

Detections: replay PCAP/JSON fixtures for each Sigma rule with expected hits.

Security: dependency scans (Trivy), SAST (CodeQL), secrets scan (gitleaks).

E2E: Playwright checks: login, search, dashboard render, alert create/test.

Performance Targets

Ingest: ≥50k EPS per node (baseline) with batching.

Query: p50 < 1.5s for 24h window on 200M rows with selective filters.

Storage: compression 3–6×; hot: 7–14 days, warm: 30–90, cold: 180–365+.

Alert latency: schedule-to-notify <60s.

Security & Compliance

TLS everywhere; mTLS optional for shippers.

OIDC SSO; API keys with scopes; per-tenant RBAC.

PII redaction at ingest (regex + allowlist).

Audit logging of admin actions and rule changes.

Data retention & legal hold flags per index/tenant.

Backups tested monthly; DR docs with RPO 1h / RTO 4h.

Migration from Splunk

Export Paths: use Splunk REST/CLI to export saved searches to CSV/JSON, dashboards to SimpleXML/JSON.

Transformers: map SPL → SQL templates for common patterns (stats, timechart).

Side-by-side: dual ship logs for 2–4 weeks; validate parity via golden queries.

Cost Report: built-in estimator shows hot vs cold savings vs current Splunk ingest license.

Pricing Model (suggested)

Free tier: 5 GB/day ingest, 7-day hot retention, 1 user.

Pro: $0.20/GB stored/month (not ingested), 30-day hot; unlimited users.

Enterprise: custom + SSO, SLOs, VPC peering, on-prem.

KPIs

Time to first dashboard < 15 minutes.

$ per TB-month vs Splunk (target: ≤ 30%).

MTTR reduction on incidents (target: 20% with M6).

False positive rate for detections (target: < 5%).

Risks & Mitigations

Query latency on huge datasets → summarize tables, rollups, projections.

Noisy alerts → dedupe, adaptive thresholds, preview simulations.

Vendor lock-in fear → open formats (Parquet), export everything.

Team bandwidth → content packs first (90/10 rule), then advanced features.

Contributing

ADRs for every major change in docs/adr/.

Conventional commits; PR checks must pass (lint, tests, security).

Add datasets & expected results when adding parsers or rules.

License

TBD (recommend AGPLv3 if you want to discourage closed forks, or Apache-2.0 to maximize adoption).

Getting Started (Today)

Clone & run compose: boot clickhouse, minio, api, ui.

Send logs from Vector/Fluent Bit using provided recipes.

Build first dashboard (Nginx) and wire first alert (High 5xx).

Record a demo showing ingest → search → dashboard → alert.

When you’re ready, I can turn this into an initial repo skeleton with the Compose file, FastAPI stubs, and a Next.js shell so you can start coding immediately.
