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
- **Services**: 
  - **API**: `localhost:7080` (container internal: 8080)
  - **UI**: `localhost:3001` (container internal: 3000)
  - **ClickHouse**: `localhost:8124` (container internal: 8123)
  - **MinIO**: `localhost:9003` (container internal: 9000), Admin: `localhost:9004`
  - **Redpanda**: `localhost:19092` (container internal: 9092), Admin: `localhost:18081-18082`
- **Start Command**: `docker compose -f infra/docker/compose.yml up -d`

### Directory Structure
```
logforge/
  apps/
    api/            # FastAPI services  
    ui/             # Next.js frontend
    workers/        # background processors
  tests/            # All test files (moved from apps/api)
    test_m*_individual.py  # Individual milestone tests
    test_*.py       # Unit and integration tests
    conftest.py     # Pytest fixtures and configuration
  packages/
    sdk-python/     # client SDK
    rules/          # Sigma-like detections
    dashboards/     # JSON dashboard packs
    shipper-recipes/# Vector/FluentBit configs
  infra/
    docker/         # compose files
    helm/           # k8s charts
    terraform/      # cloud infra
  docs/
    wiki/           # Milestone documentation (M0-M5)
```

### Development Milestones
- **M0**: Scaffold & Hello Logs (1 week) ✓ **COMPLETE**
- **M1**: Ingestion & Storage MVP (2 weeks) ✓ **COMPLETE**
- **M2**: Search & Dashboards (2 weeks) ✓ **COMPLETE**
- **M3**: Alerts & Integrations (2 weeks) ✓ **COMPLETE**
- **M4**: Security Analytics/SIEM-lite (3 weeks) ✓ **COMPLETE**
- **M5**: Traces & Metrics (3 weeks)
- **M6**: AI Assistant & RCA (3 weeks)
- **M7**: Enterprise Readiness (3 weeks) ✓ **COMPLETE**
- **M8**: User Service & Authentication Foundation (2 weeks) ✓ **COMPLETE**
- **M9**: Production Demo Environment (2 weeks)

### Key APIs
- **Ingestion**: 9 endpoints supporting JSON, Syslog, OTLP, CEF, Nginx, Text formats
- **Query**: `POST /v1/query/advanced` - Advanced log querying with filters, aggregations, time-series
- **M3 Alerts**: Complete rule-based alerting system with 15+ endpoints
- **M4 Security Analytics**: Full SIEM capabilities with Sigma rules and threat intelligence
  - `GET /v1/security/health` - Security analytics health check
  - `GET /v1/security/dashboard` - Security overview dashboard with MITRE ATT&CK mapping
  - `GET /v1/security/sigma-rules` - List all Sigma detection rules
  - `POST /v1/security/sigma-rules` - Create custom Sigma rules
  - `POST /v1/security/sigma-rules/{id}/test` - Test rule evaluation
  - `GET /v1/security/events` - List security events/detections
  - `PUT /v1/security/events/{id}/status` - Update event status (investigating, resolved, etc.)
  - `POST /v1/security/threat-hunting` - Execute threat hunting campaigns
  - `GET /v1/security/threat-intel` - List threat intelligence indicators
  - `GET /v1/security/mitre-attack/techniques` - MITRE ATT&CK technique mappings
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
- MITRE ATT&CK framework mapping
- Threat intelligence integration
- Security event correlation
- Threat hunting capabilities

### Testing Commands
**CRITICAL**: Always run comprehensive integration tests after implementing new features:

```bash
# Comprehensive integration test (includes multi-tenancy validation)
python tests/test_integration_comprehensive.py

# Unit tests for specific components
python -m pytest tests/test_m2_comprehensive.py -v --asyncio-mode=auto
python -m pytest tests/test_m2_api_endpoints.py -v --asyncio-mode=auto

# Test runner with full validation
python tests/run_m2_tests.py

# Individual milestone tests (M0-M5)
python tests/test_m0_individual.py
python tests/test_m1_individual.py
python tests/test_m2_individual.py
python tests/test_m3_individual.py
python tests/test_m4_individual.py
python tests/test_m5_individual.py
```

**Test Runner UI - Comprehensive Testing Interface:**
- **Access**: `http://localhost:3001/test-runner` (with Docker services running)
- **Frontend**: React/Next.js comprehensive test runner at `/test-runner`
- **Backend**: FastAPI test runner API at `/v1/test-runner/*` (15+ endpoints)
- **Real-time Testing**: Live test execution with polling and progress tracking
- **Test Suites**: 7 comprehensive test suites covering all functionality:
  - M1 Ingestion & Storage (4 tests): Multi-format ingestion, TTL, storage
  - M2 Query & Dashboards (2 tests): Advanced queries, 6 enterprise dashboards
  - M3 Alert Engine (2 tests): Rule-based alerting, notifications, lifecycle
  - **M4 Security Analytics** (7 tests): Sigma rules, threat hunting, MITRE ATT&CK
  - Multi-Tenant Isolation (1 test): Customer boundary validation
  - Performance Benchmarks (1 test): Throughput, latency, resource validation
  - End-to-End Integration (1 test): Complete workflow validation
- **Live Monitoring**: Real-time test execution logs, progress tracking, results
- **API Integration**: Backend test runner executes actual API calls and validates responses
- **Memory Commitment**: UI will be updated as new functionality is added

**Security Analytics UI:**
- **Access**: `http://localhost:3001/security` (with Docker services running)
- **Frontend**: React/Next.js comprehensive security analytics interface
- **Features**: Security dashboard, event management, Sigma rule testing, threat hunting, MITRE ATT&CK visualization

**Quick Start for Testing:**
```bash
# Start all services
docker compose -f infra/docker/compose.yml up -d

# Access Test Runner UI
http://localhost:3001/test-runner

# Access Security Analytics UI
http://localhost:3001/security

# Direct API access
http://localhost:7080/health
http://localhost:7080/docs  # FastAPI Swagger documentation
```

### Lint/Typecheck Commands
**Python (API)**:
- Tests use proper async/await patterns with `--asyncio-mode=auto`
- Customer isolation validated through X-Customer-ID headers
- ClickHouse multi-tenant schema required (tables: logs_raw_mt, logs_normalized_mt)
- Filter operators: "eq", "ne", "gt", "gte", "lt", "lte", "contains", "starts_with", "ends_with", "regex", "in", "not_in"

## Implementation Status

### M4 Security Analytics Implementation Complete ✅

**M4 Security Analytics/SIEM Features (COMPLETED)**:
- **Sigma Rule Engine** (security_analytics.py): Complete Sigma-like detection system (600+ lines)
- **Threat Intelligence Platform**: IOC management with confidence scoring and source tracking
- **MITRE ATT&CK Integration**: Full technique mapping with kill chain analysis
- **Security Event Management**: Event correlation, investigation workflow, artifact tracking
- **Threat Hunting**: Proactive threat hunting with rule-based detection across log data
- **Security Dashboard**: Real-time security metrics, event visualization, technique analysis

**M4 Default Detection Rules**:
1. **Brute Force Detection** (bf001): Multiple failed login attempts (MITRE: T1110)
2. **Suspicious PowerShell** (ps001): Malicious PowerShell command execution (MITRE: T1059)
3. **Privilege Escalation** (pe001): Unix/Linux privilege escalation attempts (MITRE: T1068)
4. **Data Exfiltration** (de001): Large data transfer anomaly detection (MITRE: T1041)

**M4 Threat Intelligence**:
- **Default IOCs**: 8 threat intelligence indicators (domains, IPs)
- **Confidence Scoring**: 0-100% confidence levels with source attribution
- **Threat Types**: C2, malware, phishing, scanning categorization
- **Event Enrichment**: Automatic IOC matching and context enhancement

**M4 Security UI Components**:
- **Security Dashboard**: Events by severity, MITRE ATT&CK techniques, top triggered rules
- **Event Management**: Security event lifecycle, status updates, investigation notes
- **Sigma Rules**: Rule management, testing, enablement controls
- **Threat Intelligence**: IOC browser with confidence and source tracking
- **Threat Hunting**: Interactive hunting campaigns with real-time results

**M4 API Endpoints (10 endpoints)**:
- Security Health: `GET /v1/security/health`
- Dashboard: `GET /v1/security/dashboard`
- Sigma Rules: `GET/POST /v1/security/sigma-rules`, `GET/POST /v1/security/sigma-rules/{id}/*`
- Events: `GET /v1/security/events`, `PUT /v1/security/events/{id}/status`
- Threat Hunting: `POST /v1/security/threat-hunting`
- Threat Intel: `GET /v1/security/threat-intel`
- MITRE ATT&CK: `GET /v1/security/mitre-attack/techniques`

**M4 File Structure**:
- `/apps/api/security_analytics.py` - Core security analytics engine
- `/apps/api/security_api.py` - FastAPI security endpoints
- `/apps/ui/app/security/page.tsx` - Security analytics UI
- `/packages/rules/*.yml` - Sigma detection rules (4 default rules)

### M7 Enterprise Readiness Implementation Complete ✅

**M7 Enterprise Features (COMPLETED)**:
- **22 Enterprise API Endpoints**: Complete enterprise management functionality
- **RBAC System**: Custom role creation and permission enforcement
- **Multi-Tenant Management**: Comprehensive tenant isolation and configuration
- **Compliance Automation**: SOX, GDPR, PCI-DSS, HIPAA reporting
- **Enterprise Integrations**: Slack, ServiceNow, JIRA with health monitoring
- **Audit Trails**: Complete audit logging for all user actions
- **Advanced Authentication**: OIDC, MFA, API key management
- **Disaster Recovery**: Backup and recovery policies

**M7 API Categories (22 endpoints)**:
- **Authentication & Authorization** (6 endpoints): OIDC, API keys, MFA, RBAC
- **Multi-Tenancy & Compliance** (6 endpoints): Tenant management, compliance reports, legal hold, audit logs
- **Enterprise Integrations** (3 endpoints): Integration management and health monitoring
- **Administration & Governance** (3 endpoints): Billing, system health, backup configuration

### M8 User Service & Authentication Foundation Complete ✅

**M8 Authentication Foundation (COMPLETED)**:
- **Authentication Middleware**: Request validation and permission enforcement for all API endpoints
- **Session Management**: JWT token generation, validation, and database persistence
- **Tenant Isolation**: Strict cross-tenant access controls via X-Customer-ID headers
- **API Usage Tracking**: Real-time API call tracking for billing and analytics (with database permissions)
- **Role-Based Security**: Permission-based access control integrated with all services
- **Database Layer Security**: Service-level table access controls for UserService

**M8 Core Functionality Validated**:
- ✅ **Request Authentication**: Bearer token validation for all API calls
- ✅ **Tenant Authorization**: X-Customer-ID header validation and enforcement
- ✅ **Permission Enforcement**: 403 errors for unauthorized cross-tenant access
- ✅ **Session Persistence**: JWT tokens stored and validated via ClickHouse database
- ✅ **Usage Tracking**: Database permissions configured for API billing integration
- ✅ **Security Isolation**: Complete tenant data isolation enforced at middleware level

**M8 Critical Infrastructure Role**:
M8 provides the **secure authentication foundation** that all other Logforge services (M1-M7) rely on:
- **Authentication middleware** validates every API request across all services
- **Session management** enables secure user login/logout flows
- **Tenant isolation** ensures users only access their authorized data
- **API usage tracking** provides accurate billing data for all platform usage
- **Role-based permissions** enforce granular access controls

**M8 File Structure**:
- `/apps/api/user_api.py` - User management API endpoints
- `/apps/api/auth_api.py` - Authentication endpoints (login, logout, session)
- `/apps/api/auth_middleware.py` - Authentication middleware for request validation
- `/apps/api/authn_authz_middleware.py` - Authorization and permission enforcement
- `/apps/api/database_layer.py` - Secure database layer with service-level access controls
- `/tests/test_m8_individual.py` - M8 authentication foundation test suite

**Previous Milestone Completions**:

**M1 Foundation Complete ✅**:
- Multi-format log ingestion (9 endpoints, 6 formats)
- Advanced storage architecture with TTL policies
- Multi-cloud storage support (S3/GCS/Azure/MinIO)
- Performance: 6,952+ EPS validated

**M2 Query & Dashboards Complete ✅**:
- Advanced query engine with ClickHouse optimization
- 6 enterprise dashboards (Security SOC, Performance, Infrastructure, Business, Compliance, Executive)
- Real-time dashboard data generation
- Export capabilities (JSON, CSV, PDF planned)

**M3 Alert Engine Complete ✅**:
- Rule-based alerting system (850+ lines)
- 6 rule types: Threshold, Anomaly, Pattern, Frequency, Absence, Sequence
- Multi-channel notifications (Email, Slack, Webhook, PagerDuty, etc.)
- Alert lifecycle management with audit trail
- 15+ API endpoints for complete CRUD operations

## UI Enhancement Priorities 🎨

**Current Status**: UI is functional but needs visual polish and accessibility improvements
- **Contrast Issues**: White text on white background in several areas - needs fixing
- **Accessibility**: Improve readability and navigation
- **Interactivity**: Add hover states, loading indicators, better button feedback
- **Visual Polish**: Better color coding for severity levels, improved typography, proper spacing
- **Data Visualization**: Replace numbers with charts/graphs where appropriate
- **Responsive Design**: Ensure mobile compatibility

**Enhancement Plan** (lower priority, after core features):
1. **Phase 1**: Fix critical accessibility issues (contrast, readability)
2. **Phase 2**: Add visual polish (colors, spacing, hover effects) 
3. **Phase 3**: Enhanced data visualization (charts, graphs, dashboards)
4. **Phase 4**: Advanced interactions (real-time updates, animations)

**CURRENT PRIORITY - Admin UI Implementation**:
- **Admin UI** (Separate Next.js App on port 3002): Platform administration interface for tenant management, usage analytics, billing, and admin user management
- **Missing Implementation**: Complete Admin UI application needs to be built from scratch
- **Testing**: Comprehensive Playwright test suite already written and ready for validation

## Admin UI Implementation Plan

**Objective**: Build a complete administrative interface for platform operators to manage tenants, monitor usage, handle billing, and oversee platform operations.

**Current Status**: Admin UI application does not exist - needs complete implementation

**Specifications Source**: 
- `docs/wiki/Admin-UI-Specifications.md` - Complete feature specifications
- `tests/admin-ui-comprehensive.spec.ts` - Comprehensive Playwright test suite

**Implementation Strategy** (Test-Driven Development):
1. **Foundation Setup**: Create Next.js app structure with proper configuration
2. **Backend API Gap Analysis**: Implement missing admin-specific API endpoints
3. **Page Implementation**: Build all required pages with mock data first
4. **API Integration**: Connect frontend to backend APIs
5. **Test Validation**: Ensure all Playwright tests pass
6. **Docker Integration**: Add admin-ui service to Docker Compose

**Required Pages & Features**:

### 1. Dashboard Home (`/`)
- **Platform Statistics**: Active Tenants (1,247), Monthly Revenue ($127,450), Total Data (15.2TB), Uptime (99.97%)
- **Navigation Grid**: 6 clickable cards for all admin functions
- **Responsive Design**: 3-column desktop layout, mobile-friendly stacking

### 2. Tenant Management (`/tenants`)
- **CRUD Operations**: List, create, update, delete tenants
- **Onboarding Modal**: Organization name, admin email, subscription tier selection
- **Tenant Table**: Organization, ID, subscription, status, usage, cost, actions
- **Mock Data**: Acme Corp (Enterprise), TechStart Inc (Professional), DevTeam LLC (Starter)
- **Color-coded Badges**: Enterprise (purple), Professional (blue), Starter (green)

### 3. Usage Analytics (`/usage`)
- **Period Selector**: Current month, last month, last 3 months, custom range
- **Summary Stats**: Total revenue, API calls, avg revenue/tenant, enterprise accounts
- **Usage Breakdown**: Per-tenant data ingestion, API calls, costs
- **Feature Usage**: Detailed feature-level usage and cost attribution
- **Export Functionality**: Usage reports and bill generation

### 4. Admin Users Management (`/admin-users`)
- **User Table**: Name, email, role, status, last login, permissions, actions
- **Add User Modal**: Full name, email, role selection (Admin, Super Admin, Support Admin, Billing Admin)
- **Role Badges**: Color-coded role indicators with proper permissions display
- **Mock Users**: Sarah Johnson (Super Admin), Mike Chen (Admin), Emily Rodriguez (Support Admin), David Park (Billing Admin)

**Backend API Requirements**:
- **Missing APIs**: Admin user management endpoints (`/v1/admin/users/*`)
- **Usage Analytics**: `/v1/usage/analytics`, `/v1/usage/export`, `/v1/billing/generate`
- **Enhanced Admin APIs**: Platform-wide statistics, multi-tenant usage aggregation

**Technical Implementation**:
- **Framework**: Next.js 14 with TypeScript, Tailwind CSS, shadcn/ui
- **Port**: 3002 (separate from customer UI on 3001)
- **API Integration**: FastAPI backend at localhost:7080
- **Container**: Docker service `admin-ui` in compose.yml
- **Testing**: Playwright E2E tests covering all functionality

**Design System**:
- **Consistent Styling**: Professional gray/blue palette, proper contrast ratios
- **Navigation Pattern**: "← Back to Dashboard" on all pages
- **Modal Pattern**: Consistent form styling and validation
- **Table Pattern**: Professional data tables with proper headers and actions
- **Badge System**: Color-coded status and subscription indicators

**Performance Requirements**:
- **Page Load**: < 2 seconds initial load, < 1 second navigation
- **Modal Performance**: < 500ms open/close
- **Table Rendering**: Efficient handling of large datasets with pagination

**Security Considerations**:
- **Admin-Only Access**: Separate from customer UI, role-based permissions
- **Secure API Communication**: Proper headers and validation
- **Data Protection**: No sensitive data exposure in client-side code

**Next Priorities**:
- **M5**: Distributed tracing, metrics collection, service mapping, APM
- **M6**: AI assistant, NL queries, root cause analysis, ML anomaly detection
- **M7**: SSO/OIDC, multi-tenancy, RBAC, audit logging, compliance automation
- **M8**: User Service & Authentication Foundation (core user management)
- **M9**: Production Demo Environment & Multi-Tenant Log Generation

## M9 Production Demo Environment (Post-Launch)

**Objective**: Create a realistic production demo with multiple local tenant clients continuously generating diverse log data to showcase Logforge capabilities in real-world scenarios.

**Scope** (2 weeks):
- **Multi-Tenant Client Setup**: 5-10 simulated customer environments generating realistic logs
- **Diverse Log Sources**: Web servers, databases, security systems, applications, infrastructure
- **Realistic Data Patterns**: Normal operations, security events, performance issues, compliance logs
- **Actionable Dashboards**: Customer-specific dashboards with real business scenarios
- **Self-Service Management**: Tenant UI for creating custom rules, alerts, and dashboards
- **Demo Scenarios**: Incident response, threat hunting, compliance reporting, cost optimization

**Deliverables**:
1. **Log Generation Framework**:
   - Containerized tenant simulators for different industries (fintech, healthcare, e-commerce, SaaS)
   - Realistic log patterns with seasonal/daily variations
   - Security events and attack scenarios for threat detection demos
   - Performance degradation patterns for alerting demos

2. **Multi-Tenant Demo Environment**:
   - Docker Compose setup for 5+ simulated customers
   - Industry-specific dashboards (financial services, healthcare, retail, manufacturing)
   - Pre-configured detection rules relevant to each industry
   - Compliance reporting templates (SOX, HIPAA, PCI-DSS, GDPR)

3. **Interactive Demo Scenarios**:
   - **Incident Response**: Simulated security breach with detection, investigation, and response
   - **Threat Hunting**: Proactive threat detection across multiple tenants
   - **Compliance Reporting**: Automated compliance dashboard generation
   - **Cost Optimization**: Storage tiering and retention policy demos
   - **Custom Rule Creation**: Show how customers can create industry-specific detection rules

4. **Self-Service Tenant Portal**:
   - Customer onboarding flow
   - Dashboard customization interface
   - Alert rule creation wizard
   - Data retention and cost management tools
   - Integration setup (API keys, webhooks, SIEM connectors)

**Benefits**:
- **Sales Enablement**: Realistic demos for prospective customers
- **Product Validation**: Real-world usage patterns and performance testing
- **Customer Training**: Hands-on training environment for new users
- **Competitive Differentiation**: Show cost-effectiveness vs. Splunk/Elastic/Datadog
- **Continuous Testing**: Always-on environment for regression testing

## CRITICAL STRATEGY CHANGE - Systematic Testing Approach

**STOP SPIRAL CHANGES**: No more quick fixes or cutting functionality. Follow systematic approach.

**New Development Strategy**:
1. **Individual Functionality Testing**: Test each M0-M5 feature individually with dedicated tests
2. **Documentation First**: Create docs/wiki documentation for each functionality as we test
3. **Methodical Validation**: Ensure each feature works completely before moving to integration
4. **Final Integration**: Only write integrated tests after all individual tests pass
5. **No Shortcuts**: Fix root causes, not symptoms

**Testing Order**:
- **M0**: Basic scaffold, health checks, log ingestion
- **M1**: Multi-format ingestion, TTL, storage lifecycle 
- **M2**: Query engine, aggregations, dashboards
- **M3**: Alert engine, rules, notifications
- **M4**: Security analytics, Sigma rules, threat intelligence
- **M5**: Observability, traces, metrics, APM
- **Integration**: Only after all individual tests pass

**Documentation Requirements**:
- Each functionality gets dedicated docs/wiki page
- API endpoint documentation with examples
- Test scenarios and expected behaviors
- Known limitations and future improvements

**Key Pending Issues to Address Systematically**:
- Create materialized view for logs_raw_mt → logs_normalized_mt transformation
- Multi-tenant table structure consistency
- Timeseries query engine fixes (without spiral changes)

## Important Notes
- This is a defensive security project only
- Focus on observability, SIEM, and log analysis capabilities  
- Advanced, cost-effective enterprise platform competing directly with commercial solutions
- Emphasizes 60-80% cost reduction through intelligent architecture
- Multi-cloud compliance support (FedRAMP, HIPAA, SOX, GDPR)
- Integrated development approach - all features work seamlessly together