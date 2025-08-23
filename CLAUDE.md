# Claude Code Memory - Logforge Project

## Project Overview
Logforge is an incremental, open observability + SIEM platform designed as a pragmatic Splunk alternative. This is a security-focused project for defensive purposes only.

## Key Project Details

### Architecture
- **Storage**: ClickHouse (hot data), S3/MinIO (cold storage)
- **Ingestion**: HTTP/OTLP (OpenTelemetry), Syslog
- **Message Queue**: Redpanda (dev) / Kafka (prod)
- **API**: FastAPI (Python)
- **Frontend**: Next.js (React), Tailwind, shadcn/ui
- **Auth**: OIDC (Auth0/Keycloak), API Keys

### Development Environment
- **Local Setup**: Docker Compose
- **Services**: api:8080, ui:3000, clickhouse:8123, minio:9000, redpanda:9092
- **Start Command**: `docker compose -f infra/docker/compose.yml up -d`

### Directory Structure
```
logforge/
  apps/
    api/            # FastAPI services  
    ui/             # Next.js frontend
    workers/        # background processors
  packages/
    sdk-python/     # client SDK
    rules/          # Sigma-like detections
    dashboards/     # JSON dashboard packs
    shipper-recipes/# Vector/FluentBit configs
  infra/
    docker/         # compose files
    helm/           # k8s charts
    terraform/      # cloud infra
```

### Development Milestones
- **M0**: Scaffold & Hello Logs (1 week)
- **M1**: Ingestion & Storage MVP (2 weeks) 
- **M2**: Search & Dashboards (2 weeks)
- **M3**: Alerts & Integrations (2 weeks)
- **M4**: Security Analytics/SIEM-lite (3 weeks)
- **M5**: Traces & Metrics (3 weeks)
- **M6**: AI Assistant & RCA (3 weeks)
- **M7**: Enterprise Readiness (3 weeks)

### Key APIs
- `POST /v1/ingest/logs` - Log ingestion
- `POST /v1/query` - Query logs with filters
- `POST /v1/alerts/test` - Test alert rules

### Performance Targets
- **Ingest**: ≥50k EPS per node
- **Query**: p50 < 1.5s for 24h window on 200M rows
- **Storage**: 3-6x compression ratio
- **Alert latency**: <60s schedule-to-notify

### Security Features
- PII redaction at ingest
- TLS everywhere, optional mTLS
- OIDC SSO + RBAC
- Audit logging
- Sigma-like detection rules
- ATT&CK framework mapping

### Testing Commands
The project doesn't have specific test commands defined yet. Check package.json or Makefile when available.

### Lint/Typecheck Commands
Not yet defined - will need to check for:
- Python: ruff, black, mypy
- JavaScript/TypeScript: eslint, prettier, tsc
- Or check package.json/pyproject.toml when created

## Implementation Plan

### M0: Scaffold & Hello Logs (Current - 1 Week)
**Phase 1: Repository Scaffold & Development Environment**
1. Repository Structure Setup - monorepo with proper structure
2. Docker Compose Infrastructure - ClickHouse, MinIO, Redpanda, API, UI
3. Minimal FastAPI Backend - health check + basic log ingestion
4. Basic Next.js Frontend - simple log viewer interface
5. Acceptance: `docker compose up -d` works, can POST logs to ClickHouse

**Next Milestones (M1-M7)**
- M1: Ingestion & Storage MVP (2 weeks) - 10k EPS performance target
- M2: Search & Dashboards (2 weeks) - Query API + 6 pre-built dashboards  
- M3: Alerts & Integrations (2 weeks) - Rule engine + notifications
- M4: SIEM-lite (3 weeks) - Sigma rules + threat intelligence
- M5: Traces & Metrics (3 weeks) - OTLP ingestion + correlation
- M6: AI Assistant & RCA (3 weeks) - NL queries + incident analysis
- M7: Enterprise (3 weeks) - SSO, multi-tenancy, compliance

### Current Focus
Starting with M0 implementation - building the foundational infrastructure and "hello logs" functionality to establish the core data pipeline.

## Important Notes
- This is a defensive security project only
- Focus on observability, SIEM, and log analysis capabilities
- Open source alternative to Splunk
- Emphasizes cost efficiency and openness
- Incremental development approach - each milestone must be demonstrable