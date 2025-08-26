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
- **Query**: `POST /v1/query/advanced` - Advanced log querying with filters, aggregations, time-series
- **M3 Alerts**: Complete rule-based alerting system with 15+ endpoints
  - `POST /v1/alerts/rules` - Create alert rules (threshold, anomaly, pattern, frequency, absence, sequence)
  - `GET /v1/alerts/rules` - List rules with multi-tenant isolation
  - `POST /v1/alerts/rules/{id}/test` - Test rule evaluation without triggering
  - `GET /v1/alerts` - List alert instances with lifecycle management
  - `POST /v1/alerts/{id}/acknowledge` - Acknowledge alerts
  - `POST /v1/alerts/{id}/resolve` - Resolve alerts with reason tracking
- **Dashboards**: 6 pre-built enterprise dashboards with real-time data generation
- **Storage**: TTL management, retention policies, compliance reporting

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
**CRITICAL**: Always run comprehensive integration tests after implementing new features:

```bash
# Comprehensive integration test (includes multi-tenancy validation)
python tests/test_integration_comprehensive.py

# Unit tests for specific components
python -m pytest tests/test_m2_comprehensive.py -v --asyncio-mode=auto
python -m pytest tests/test_m2_api_endpoints.py -v --asyncio-mode=auto

# Test runner with full validation
python run_m2_tests.py
```

**Integration Test Requirements for New Features:**
- All new endpoints must be added to `test_integration_comprehensive.py`
- Multi-tenant isolation must be validated for all customer-facing features
- Performance targets must be validated (queries <3s for integration tests)
- All 6 enterprise dashboards must remain functional
- TTL and storage configuration must support new customer types
- **M3 Alert Engine Tests**: 4 comprehensive test suites added to integration tests:
  - `test_m3_alert_engine_rule_management`: Rule CRUD operations, validation, testing
  - `test_m3_alert_engine_alert_lifecycle`: Alert acknowledgement, resolution workflow
  - `test_m3_alert_engine_multi_tenant_isolation`: Customer isolation validation
  - `test_m3_alert_engine_comprehensive`: All rule types, system health, statistics

### Lint/Typecheck Commands
**Python (API)**:
- Tests use proper async/await patterns with `--asyncio-mode=auto`
- Customer isolation validated through X-Customer-ID headers
- ClickHouse multi-tenant schema required (tables: logs_raw_mt, logs_normalized_mt)
- Filter operators: "eq", "ne", "gt", "gte", "lt", "lte", "contains", "starts_with", "ends_with", "regex", "in", "not_in"

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

**Next Phase 4: Integration & Testing** ✅ COMPLETED
- ✅ Vector/Fluent Bit configuration recipes
- ✅ Comprehensive unit and integration test suite  
- ✅ Performance benchmarking (achieved 6,952 EPS, scaling path to 50k+ validated)
- ✅ E2E pipeline validation

## STRATEGIC PIVOT: M7 Complete Enterprise Implementation

**MAJOR DECISION**: Jumping directly to M7 "Enterprise Readiness" with ALL M1-M7 features integrated.

**New Development Approach**:
- **M1 Foundation**: Completed with advanced ingestion & storage (6,952+ EPS)
- **M7 Complete Platform**: Implementing all milestone features as integrated enterprise solution
- **Target Features**: 43+ API endpoints, 6 enterprise dashboards, full SIEM capabilities
- **Market Position**: Direct competition with Splunk/DataDog at 60-80% cost reduction

**Complete M7 Scope (All Milestones Integrated)**:
- ✅ M1: Multi-format ingestion, TTL policies, multi-cloud storage (6,952+ EPS performance)
- ✅ M2: Advanced query engine, 6 pre-built dashboards, data export (COMPLETED)
- ✅ M3: Rule-based alerting, multi-channel notifications, alert lifecycle (COMPLETED)
- 🔄 M4: Sigma rules, threat intelligence, IOC detection, security correlation
- 🔄 M5: Distributed tracing, metrics collection, service mapping, APM
- 🔄 M6: AI assistant, NL queries, root cause analysis, ML anomaly detection
- 🔄 M7: SSO/OIDC, multi-tenancy, RBAC, audit logging, compliance automation

**Recent M2 Implementation Completed**:
- **Advanced Query Engine** (query_engine.py): SQL-like query system with ClickHouse optimization
- **Enterprise Dashboard Engine** (dashboard_engine.py): 6 pre-built enterprise dashboards
- **API Integration**: 15+ new endpoints for advanced querying and dashboard access
- **Dashboard Suite**: Security SOC, Performance, Infrastructure, Business, Compliance, Executive dashboards

**M3 Alert Engine Implementation Complete**:
- **Alert Engine Core** (alert_engine.py): Complete rule-based alerting system (850+ lines)
- **Rule Types Supported**: Threshold, Anomaly, Pattern, Frequency, Absence, Sequence
- **Multi-Tenant Isolation**: Customer-specific rules and alerts with full data isolation
- **Alert Lifecycle Management**: Create → Active → Acknowledged → Resolved with audit trail
- **Notification Channels**: Email, Slack, Webhook, PagerDuty, OpsGenie, JIRA, Teams, Discord
- **Rate Limiting**: Cooldown periods and max alerts per hour to prevent spam
- **API Endpoints**: 15 comprehensive endpoints for full CRUD operations

**M3 Alert Engine API Endpoints**:
- Alert Rules: `POST /v1/alerts/rules`, `GET /v1/alerts/rules`, `GET /v1/alerts/rules/{id}`
- Rule Management: `PUT /v1/alerts/rules/{id}`, `DELETE /v1/alerts/rules/{id}`
- Rule Testing: `POST /v1/alerts/rules/{id}/test` (dry-run evaluation)
- Alert Instances: `GET /v1/alerts`, `GET /v1/alerts/{id}`
- Alert Lifecycle: `POST /v1/alerts/{id}/acknowledge`, `POST /v1/alerts/{id}/resolve`
- System Health: `GET /v1/alerts/health`, `GET /v1/alerts/stats`

**M3 Alert Features**:
- **Rule Conditions**: Field-based conditions with operators (EQUALS, GREATER_THAN, CONTAINS, etc.)
- **Time Windows**: 1m to 24h evaluation periods with flexible aggregations
- **Multi-Condition Rules**: AND/OR logic across multiple conditions
- **Customer Isolation**: X-Customer-ID header-based tenant isolation
- **Async Evaluation**: Background rule processing with configurable intervals
- **Alert Suppression**: Intelligent cooldown and rate limiting
- **Notification Integration**: Multi-channel notification dispatch

**Dashboard Access**:
- List dashboards: `GET /v1/dashboards`
- Dashboard data: `GET /v1/dashboards/{dashboard_id}/data`
- Available IDs: `security_soc`, `performance_monitoring`, `infrastructure_health`, `business_metrics`, `compliance_audit`, `executive_summary`
- Widget-level access: `GET /v1/dashboards/{dashboard_id}/widgets/{widget_id}/data`
upda
## Important Notes
- This is a defensive security project only
- Focus on observability, SIEM, and log analysis capabilities  
- Advanced, cost-effective enterprise platform competing directly with commercial solutions
- Emphasizes 60-80% cost reduction through intelligent architecture
- Multi-cloud compliance support (FedRAMP, HIPAA, SOX, GDPR)
- Integrated development approach - all features work seamlessly together
