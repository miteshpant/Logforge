# Actual API Reference - Existing Endpoints Only

This document lists only the APIs that actually exist in the Logforge codebase for accurate user story mapping.

## Core APIs (M0-M1)

### Health & System
- `GET /health` - System health check
- `GET /` - Root endpoint with platform info

### Authentication (M8)
- `POST /v1/auth/login` - User login
- `POST /v1/auth/logout` - User logout  
- `POST /v1/auth/refresh` - Refresh JWT token
- `GET /v1/auth/me` - Get current user info
- `POST /v1/auth/setup/init` - Initialize setup
- `POST /v1/auth/setup` - Complete setup
- `POST /v1/auth/password/reset` - Password reset
- `POST /v1/auth/password/reset-confirm` - Confirm password reset
- `POST /v1/auth/password/change` - Change password
- `POST /v1/auth/invite` - Send invitation
- `POST /v1/auth/accept-invite` - Accept invitation
- `POST /v1/auth/tenant-onboard` - Tenant onboarding
- `GET /v1/auth/sessions` - List user sessions
- `DELETE /v1/auth/sessions/{session_id}` - Delete session
- `DELETE /v1/auth/sessions/all` - Delete all sessions

### Log Ingestion (M1)
- `POST /v1/ingest/logs` - Single log ingestion
- `POST /v1/ingest/logs/batch` - Batch log ingestion
- `POST /v1/ingest/logs/bulk` - Bulk log ingestion
- `POST /v1/ingest/otlp` - OTLP log ingestion
- `POST /v1/ingest/syslog` - Syslog ingestion
- `POST /v1/ingest/nginx` - Nginx log ingestion
- `POST /v1/ingest/cef` - CEF log ingestion
- `POST /v1/ingest/text` - Text log ingestion
- `POST /v1/ingest/structured` - Structured JSON ingestion
- `POST /v1/ingest` - Auto-detect format ingestion

## Query & Analytics (M2)

### Query Engine
- `POST /v1/query/advanced` - Advanced log queries
- `POST /v1/query/aggregate` - Aggregation queries
- `POST /v1/query/timeseries` - Time-series queries
- `GET /v1/query/saved` - List saved queries
- `POST /v1/query/saved` - Save query
- `GET /v1/query/saved/{query_id}` - Get saved query
- `POST /v1/export` - Export query results
- `GET /v1/logs` - Basic log retrieval

### Dashboards
- `GET /v1/dashboards` - List dashboards
- `GET /v1/dashboards/{dashboard_id}` - Get dashboard
- `GET /v1/dashboards/{dashboard_id}/data` - Get dashboard data
- `POST /v1/dashboards` - Create dashboard
- `PUT /v1/dashboards/{dashboard_id}` - Update dashboard
- `DELETE /v1/dashboards/{dashboard_id}` - Delete dashboard
- `GET /v1/dashboards/{dashboard_id}/widgets/{widget_id}/data` - Get widget data

## Alerting (M3)

### Alert Rules
- `POST /v1/alerts/rules` - Create alert rule
- `GET /v1/alerts/rules` - List alert rules
- `GET /v1/alerts/rules/{rule_id}` - Get alert rule
- `PUT /v1/alerts/rules/{rule_id}` - Update alert rule
- `DELETE /v1/alerts/rules/{rule_id}` - Delete alert rule
- `POST /v1/alerts/rules/{rule_id}/test` - Test alert rule

### Alert Instances
- `GET /v1/alerts` - List active alerts
- `GET /v1/alerts/stats` - Alert statistics
- `GET /v1/alerts/{alert_id}` - Get alert details
- `POST /v1/alerts/{alert_id}/acknowledge` - Acknowledge alert
- `POST /v1/alerts/{alert_id}/resolve` - Resolve alert
- `GET /v1/alerts/health` - Alerting health

### Notifications
- `GET /v1/alerts/notifications/channels` - List notification channels
- `POST /v1/alerts/notifications/channels` - Create notification channel
- `GET /v1/alerts/integrations/webhooks` - List webhooks
- `POST /v1/alerts/integrations/webhooks` - Create webhook

## Security Analytics (M4)

### Security Dashboard
- `GET /v1/security/health` - Security system health
- `GET /v1/security/dashboard` - Security overview dashboard

### Sigma Rules & Detection
- `GET /v1/security/sigma-rules` - List Sigma rules
- `POST /v1/security/sigma-rules` - Create Sigma rule
- `GET /v1/security/sigma-rules/{rule_id}` - Get Sigma rule
- `POST /v1/security/sigma-rules/{rule_id}/test` - Test Sigma rule

### Security Events
- `GET /v1/security/events` - List security events
- `PUT /v1/security/events/{event_id}/status` - Update event status

### Threat Hunting & Intelligence
- `POST /v1/security/threat-hunting` - Execute threat hunt
- `GET /v1/security/threat-intel` - Get threat intelligence
- `POST /v1/security/background-hunting` - Background hunting
- `GET /v1/security/mitre-attack/techniques` - MITRE ATT&CK data

## Observability (M5)

### Traces
- `POST /v1/observability/traces/ingest` - Ingest traces
- `POST /v1/observability/traces/search` - Search traces
- `GET /v1/observability/traces/{trace_id}` - Get trace details

### Metrics & APM
- `POST /v1/observability/metrics/ingest` - Ingest metrics
- `POST /v1/observability/metrics/query` - Query metrics
- `GET /v1/observability/service-map` - Service map
- `GET /v1/observability/apm/{service_name}` - APM data
- `GET /v1/observability/health` - Observability health

## AI Assistant (M6)

### Query & Analysis
- `GET /v1/ai/health` - AI system health
- `POST /v1/ai/query` - AI query processing
- `GET /v1/ai/query/suggestions` - Query suggestions
- `GET /v1/ai/query/{query_id}/history` - Query history

### Incident Analysis
- `POST /v1/ai/analyze-incident` - Analyze incident
- `POST /v1/ai/analyze-symptoms` - Analyze symptoms
- `GET /v1/ai/incidents/{incident_id}/analysis` - Get incident analysis

### Intelligence & Insights
- `POST /v1/ai/correlate` - Correlate events
- `GET /v1/ai/anomalies` - Get anomalies
- `POST /v1/ai/predict` - Predictive analysis
- `GET /v1/ai/baselines` - System baselines
- `GET /v1/ai/insights/operational` - Operational insights
- `POST /v1/ai/business-impact` - Business impact analysis
- `GET /v1/ai/metrics/business` - Business metrics

### Investigation
- `POST /v1/ai/investigate/start` - Start investigation
- `POST /v1/ai/investigate/{investigation_id}/evidence` - Add evidence
- `GET /v1/ai/investigate/{investigation_id}/recommendations` - Get recommendations

### Knowledge Management
- `GET /v1/ai/knowledge/search` - Search knowledge base
- `POST /v1/ai/knowledge/solutions` - Get solutions
- `POST /v1/ai/learn/incident` - Learn from incident

## Enterprise (M7)

### Authentication & RBAC
- `POST /v1/enterprise/auth/oidc/configure` - Configure OIDC
- `GET /v1/enterprise/auth/providers` - List auth providers
- `POST /v1/enterprise/auth/api-keys` - Create API key
- `GET /v1/enterprise/auth/api-keys` - List API keys
- `DELETE /v1/enterprise/auth/api-keys/{key_id}` - Delete API key
- `POST /v1/enterprise/auth/mfa/setup` - Setup MFA

### RBAC
- `GET /v1/enterprise/rbac/roles` - List roles
- `POST /v1/enterprise/rbac/roles` - Create role
- `PUT /v1/enterprise/rbac/users/{user_id}/roles` - Assign user roles
- `GET /v1/enterprise/rbac/permissions` - Get user permissions

### Multi-Tenancy
- `GET /v1/enterprise/tenants` - List tenants (enterprise view)
- `POST /v1/enterprise/tenants` - Create tenant
- `PUT /v1/enterprise/tenants/{tenant_id}/settings` - Update tenant settings

### Compliance & Audit
- `GET /v1/enterprise/compliance/reports` - Compliance reports
- `POST /v1/enterprise/compliance/legal-hold` - Legal hold
- `GET /v1/enterprise/audit-logs` - Audit logs

### Integrations & System
- `GET /v1/enterprise/integrations` - List integrations
- `POST /v1/enterprise/integrations/{integration_type}/configure` - Configure integration
- `GET /v1/enterprise/integrations/{integration_type}/status` - Integration status
- `GET /v1/enterprise/usage/billing` - Enterprise billing
- `GET /v1/enterprise/system/health` - System health
- `POST /v1/enterprise/backup/configure` - Configure backup
- `GET /v1/enterprise/metrics` - Enterprise metrics
- `GET /v1/enterprise/health` - Enterprise health

## User Management (M8)

### User CRUD
- `POST /v1/users` - Create user
- `GET /v1/users/{user_id}` - Get user details
- `PUT /v1/users/{user_id}` - Update user
- `DELETE /v1/users/{user_id}` - Delete user
- `GET /v1/users` - List users

### Admin User Management
- `POST /v1/admin/users` - Create admin user
- `GET /v1/admin/users` - List admin users
- `GET /v1/admin/users/{user_id}` - Get admin user details
- `PUT /v1/admin/users/{user_id}` - Update admin user
- `DELETE /v1/admin/users/{user_id}` - Delete admin user

### Role Management
- `POST /v1/users/{user_id}/roles` - Assign user role
- `GET /v1/users/{user_id}/roles` - Get user roles
- `DELETE /v1/users/{user_id}/roles/{role_id}` - Remove user role
- `GET /v1/roles` - List all roles
- `GET /v1/roles/{role}/permissions` - Get role permissions
- `GET /v1/tenants/{tenant_id}/users` - List tenant users
- `POST /v1/tenants/{tenant_id}/users/{user_id}/roles` - Assign tenant role

## Tenant Management

### Tenant CRUD
- `POST /v1/tenants` - Create tenant
- `GET /v1/tenants` - List tenants
- `GET /v1/tenants/{tenant_id}` - Get tenant details
- `PUT /v1/tenants/{tenant_id}` - Update tenant
- `DELETE /v1/tenants/{tenant_id}` - Delete tenant

### Tenant Configuration
- `POST /v1/tenants/{tenant_id}/storage/configure` - Configure storage
- `POST /v1/tenants/{tenant_id}/storage/test-connection` - Test storage connection
- `GET /v1/tenants/{tenant_id}/storage/status` - Storage status
- `GET /v1/tenants/{tenant_id}/quotas` - Get quotas
- `PUT /v1/tenants/{tenant_id}/quotas` - Update quotas
- `GET /v1/tenants/{tenant_id}/config` - Get config
- `PUT /v1/tenants/{tenant_id}/config` - Update config

### Tenant Operations
- `GET /v1/tenants/{tenant_id}/usage` - Usage analytics
- `GET /v1/tenants/{tenant_id}/compliance` - Compliance status
- `POST /v1/tenants/{tenant_id}/legal-hold` - Legal hold
- `GET /v1/tenants/{tenant_id}/health` - Tenant health
- `GET /v1/tenants/{tenant_id}/metrics` - Tenant metrics
- `GET /v1/tenants/{tenant_id}/alerts` - Tenant alerts
- `GET /v1/tenants/{tenant_id}/validate` - Validate tenant

## Subscription & Billing

### Subscription Management
- `GET /v1/tenants/{tenant_id}/subscription` - Get subscription
- `PUT /v1/tenants/{tenant_id}/subscription` - Update subscription
- `GET /v1/tenants/{tenant_id}/features` - Get tenant features

### Usage & Billing
- `GET /v1/usage/current/{tenant_id}` - Current usage
- `GET /v1/usage/history/{tenant_id}` - Usage history
- `GET /v1/billing/estimate/{tenant_id}` - Billing estimate
- `POST /v1/billing/generate/{tenant_id}` - Generate bill
- `GET /v1/analytics/usage-trends` - Usage trends
- `GET /v1/analytics/feature-usage` - Feature usage
- `GET /v1/usage/realtime/{tenant_id}` - Real-time usage
- `GET /v1/usage/export/{tenant_id}` - Export usage data
- `GET /v1/costs/breakdown/{tenant_id}` - Cost breakdown
- `POST /v1/costs/alerts/{tenant_id}` - Cost alerts

### Admin Operations
- `GET /v1/admin/rates` - Get feature rates
- `POST /v1/admin/rates` - Create feature rate
- `PUT /v1/admin/rates/{feature_name}` - Update feature rate
- `GET /v1/admin/rates/{feature_name}/history` - Rate history
- `GET /v1/admin/tenants` - Admin tenant list
- `GET /v1/admin/tenants/{tenant_id}/details` - Admin tenant details
- `PUT /v1/admin/tenants/{tenant_id}/subscription` - Admin update subscription
- `POST /v1/admin/tenants/{tenant_id}/billing/override` - Billing override
- `GET /v1/admin/audit/subscription-changes` - Subscription audit
- `POST /v1/admin/compliance/reports` - Generate compliance reports
- `GET /v1/admin/compliance/retention-status` - Retention compliance

## Storage Management

### Data Lifecycle
- `GET /v1/storage/retention/{customer_id}` - Get retention policy
- `PUT /v1/storage/retention/{customer_id}` - Update retention policy
- `POST /v1/storage/cleanup` - Trigger cleanup
- `POST /v1/storage/archive/{customer_id}` - Archive data
- `GET /v1/storage/health` - Storage health

## Test Runner (Internal)
- `POST /v1/test-runner/execute/{suite_id}` - Execute test suite
- `GET /v1/test-runner/status` - Get test status
- `GET /v1/test-runner/logs` - Get test logs
- `DELETE /v1/test-runner/logs` - Clear test logs
- `GET /v1/test-runner/suites/{suite_id}/results` - Get test results
- `POST /v1/test-runner/execute-all` - Execute all tests
- `GET /v1/test-runner/suites` - List test suites
- `GET /v1/test-runner/health` - Test runner health

## Important Notes

### APIs That DO NOT EXIST (commonly referenced incorrectly):
- `/v1/compliance/*` - Only exists under `/v1/enterprise/compliance/*` 
- `/v1/billing/generate` - Only exists as `/v1/billing/generate/{tenant_id}`
- `/v1/usage/analytics` - Only exists as `/v1/analytics/usage-trends`
- `/v1/ai/anomaly-detection` - Only exists as `/v1/ai/anomalies`
- `/v1/ai/root-cause-analysis` - Does not exist
- `/v1/alerts/analytics` - Does not exist
- `/v1/users/audit-report` - Does not exist
- `/v1/users/bulk-create` - Does not exist

### Multi-Tenant Context:
- Most APIs require `X-Customer-ID` header for tenant isolation
- Admin APIs (prefixed with `/admin/`) bypass tenant isolation
- Enterprise APIs provide cross-tenant visibility