# Claude Code Memory - Logforge Project

## Project Overview
Logforge is an advanced, cost-effective observability + SIEM platform designed for enterprise security and operations teams. This is a security-focused project for defensive purposes only.

## Key Project Details

### Architecture
- **Storage**: ClickHouse (hot data), Multi-cloud (S3/GCS/Azure/MinIO) cold storage with automated TTL
- **Ingestion**: HTTP/OTLP (OpenTelemetry), Syslog, multi-format parsing
- **Message Queue**: Redpanda (dev) / Kafka (prod)
- **API**: FastAPI (Python) with comprehensive endpoint coverage
- **Frontend**: Next.js (React), Tailwind, shadcn/ui
- **Auth**: OIDC (Auth0/Keycloak), API Keys
- **Data Lifecycle**: Automated TTL policies with compliance-driven retention

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
- **Ingestion**: 9 endpoints supporting JSON, Syslog, OTLP, CEF, Nginx, Text formats
- **Query**: `POST /v1/query` - Advanced log querying with filters
- **Alerts**: `POST /v1/alerts/test` - Test alert rules  
- **Storage**: 4 endpoints for TTL management and compliance reporting

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

### M1 Progress (In Progress - 2 weeks)

**Phase 1 Complete: Enhanced Storage Architecture ✅**
- ✅ **Multi-Cloud Storage**: S3/GCS/Azure + MinIO support with deployment-aware configs
- ✅ **Enhanced ClickHouse Schema**: Monthly partitioning, materialized views, compression
- ✅ **Analytics Tables**: Pre-aggregated hourly stats, computed fields (is_error, is_slow)
- ✅ **Flexible Deployment**: Shared/Dedicated/FedRAMP/On-premises configurations

**Phase 2 Complete: Multi-Format Ingestion ✅**
- ✅ **Enhanced API Endpoints**: 8 new ingestion endpoints with format-specific parsing
- ✅ **Parser Architecture**: Modular factory pattern supporting 6 log formats
- ✅ **Format Support**: JSON, Syslog (RFC 3164/5424), OTLP, CEF, Nginx, Plain Text
- ✅ **Performance Features**: Batch ingestion, background processing, auto-format detection
- ✅ **Data Models**: 50+ validated fields with comprehensive type safety

**Phase 3 Complete: TTL & Data Lifecycle Management ✅**
- ✅ **Advanced TTL Policies**: Customer-specific retention (30 days to 7 years)
- ✅ **Multi-Cloud Storage**: S3, GCS, Azure Blob, MinIO with seamless integration
- ✅ **Compliance Framework**: FedRAMP, HIPAA, SOX, SOC 2 retention policies
- ✅ **Storage Management**: Health monitoring, usage analytics, manual archival
- ✅ **Automated Lifecycle**: Daily/weekly/monthly scheduled cleanup and reporting
- ✅ **Enhanced Schema**: Advanced partitioning, compression, materialized views

**Current API Endpoints:**

*Ingestion (9 endpoints):*
- `POST /v1/ingest/logs` - Original JSON endpoint (backwards compatible)
- `POST /v1/ingest/logs/batch` - High-performance batch ingestion (up to 1000 logs)
- `POST /v1/ingest/otlp` - OpenTelemetry Protocol logs  
- `POST /v1/ingest/syslog` - RFC 3164/5424 syslog messages
- `POST /v1/ingest/nginx` - Nginx access log parsing
- `POST /v1/ingest/cef` - Common Event Format (security logs)
- `POST /v1/ingest/text` - Plain text with regex pattern matching
- `POST /v1/ingest/structured` - Application JSON logs
- `POST /v1/ingest` - Auto-detect format and parse

*Storage Management (4 endpoints):*
- `GET /v1/storage/health` - Storage system health & capacity monitoring
- `POST /v1/storage/policies` - Apply/update customer retention policies
- `GET /v1/storage/usage` - Detailed usage analytics by customer/time
- `POST /v1/storage/archive` - Manual data archival trigger

**Next Phase 4: Integration & Testing**
- Vector/Fluent Bit configuration recipes
- Comprehensive unit and integration test suite
- Performance benchmarking (target: 50k EPS)
- E2E pipeline validation

## Important Notes
- This is a defensive security project only
- Focus on observability, SIEM, and log analysis capabilities
- Advanced, cost-effective enterprise platform (not positioned as direct competitor)
- Emphasizes 60-80% cost reduction through intelligent storage tiering
- Multi-cloud compliance support (FedRAMP, HIPAA, SOX)
- Incremental development approach - each milestone must be demonstrable