# Logforge API Reference

> Auto-generated from source files under `apps/api/routers/`. Last updated: 2026-02-04.

All endpoints are served by a FastAPI application. Multi-tenant isolation is enforced via the `X-Customer-ID` header (or `MiddlewareTenant` dependency) and JWT-based authentication (`get_current_user`).

---

## Table of Contents

1. [Health](#1-health)
2. [Authentication](#2-authentication)
3. [Users](#3-users)
4. [Roles](#4-roles)
5. [Tenants](#5-tenants)
6. [Subscriptions & Billing](#6-subscriptions--billing)
7. [Ingestion](#7-ingestion)
8. [Query Engine](#8-query-engine)
9. [Dashboards](#9-dashboards)
10. [Alerts](#10-alerts)
11. [Alert Correlation](#11-alert-correlation)
12. [Security Analytics](#12-security-analytics)
13. [Observability (APM / Traces / Metrics)](#13-observability)
14. [AI & ML](#14-ai--ml)
15. [Predictive Analytics](#15-predictive-analytics)
16. [Storage & Retention](#16-storage--retention)
17. [Schema Registry](#17-schema-registry)
18. [Events (Kafka)](#18-events-kafka)
19. [Streaming (SSE)](#19-streaming-sse)
20. [Streaming Configuration](#20-streaming-configuration)
21. [Usage Analytics & Billing](#21-usage-analytics--billing)
22. [Quota Management](#22-quota-management)
23. [Enterprise](#23-enterprise)

---

## 1. Health

**Source:** `routers/health.py` | **Prefix:** none (root)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Root endpoint (API info) |
| GET | `/health` | Basic health check |
| GET | `/health/detailed` | Detailed health with dependency status |
| GET | `/health/resilience` | Resilience / circuit-breaker status |
| GET | `/health/ready` | Kubernetes readiness probe |
| GET | `/health/live` | Kubernetes liveness probe |

**Auth:** None required.
**Service:** `HealthService`

---

## 2. Authentication

**Source:** `routers/auth_api.py` | **Prefix:** `/v1/auth` | **Tags:** `Authentication`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/auth/login` | Authenticate user, returns JWT |
| POST | `/v1/auth/logout` | Invalidate current session |
| POST | `/v1/auth/refresh` | Refresh JWT session |
| GET | `/v1/auth/me` | Get authenticated user profile |
| POST | `/v1/auth/setup/init` | Initialize platform (first-run) |
| POST | `/v1/auth/setup` | Complete platform setup |
| POST | `/v1/auth/password/reset` | Request password reset email |
| POST | `/v1/auth/password/reset-confirm` | Confirm password reset with token |
| POST | `/v1/auth/password/change` | Change password (authenticated) |
| POST | `/v1/auth/invite` | Invite user to tenant |
| POST | `/v1/auth/accept-invite` | Accept invitation |
| POST | `/v1/auth/verify-email` | Send email verification |
| POST | `/v1/auth/verify-email-confirm` | Confirm email verification |
| POST | `/v1/auth/tenant-onboard` | Onboard new tenant |
| GET | `/v1/auth/sessions` | List active sessions |
| DELETE | `/v1/auth/sessions/all` | Revoke all sessions |
| DELETE | `/v1/auth/sessions/{session_id}` | Revoke specific session |
| POST | `/v1/auth/deactivate` | Deactivate own account |
| POST | `/v1/auth/reactivate/{user_id}` | Reactivate account (admin) |

**Service:** `UserService`, `RoleService`, `setup_token_manager`, `invitation_manager`

---

## 3. Users

**Source:** `routers/user_api.py` | **Prefix:** `/v1` | **Tags:** `User Management`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/users` | Create user account |
| GET | `/v1/users` | List users (scoped by role) |
| GET | `/v1/users/search` | Search users by name/email |
| GET | `/v1/users/me` | Get current user profile |
| PUT | `/v1/users/me` | Update current user profile |
| GET | `/v1/users/{user_id}` | Get user by ID |
| PUT | `/v1/users/{user_id}` | Update user |
| DELETE | `/v1/users/{user_id}` | Delete user (soft-delete) |
| POST | `/v1/users/bulk-create` | Bulk create users (max 500, admin) |
| POST | `/v1/admin/users` | Create platform admin user |
| GET | `/v1/admin/users` | List platform admin users |
| GET | `/v1/admin/users/{user_id}` | Get admin user details |
| PUT | `/v1/admin/users/{user_id}` | Update admin user |
| DELETE | `/v1/admin/users/{user_id}` | Delete admin user |

**Auth:** `get_current_user` for standard ops; `require_platform_admin` for admin ops.
**Service:** `UserService` (via `authn_authz_middleware`)

---

## 4. Roles

**Source:** `routers/role_api.py` | **Prefix:** `/v1` | **Tags:** `Role Management`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/users/{user_id}/roles` | Get user roles |
| POST | `/v1/users/{user_id}/roles` | Assign role to user |
| DELETE | `/v1/users/{user_id}/roles/{role_name}` | Remove role from user |
| GET | `/v1/roles` | List available roles |
| GET | `/v1/roles/{role_name}/permissions` | Get role permissions |
| GET | `/v1/tenants/{tenant_id}/users` | List tenant users with roles |
| GET | `/v1/permissions/check` | Check permission for user |
| GET | `/v1/permissions/validate-access` | Validate access to resource |
| GET | `/v1/users/{user_id}/effective-permissions` | Get effective permissions |
| GET | `/v1/roles/analytics` | Role analytics (counts, distribution) |
| POST | `/v1/roles/bulk-assign` | Bulk assign roles |

**Auth:** Platform admin or tenant admin depending on scope.
**Service:** `RoleService`

---

## 5. Tenants

**Source:** `routers/tenant_api.py` | **Prefix:** `/v1/tenants` | **Tags:** `tenants`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/tenants` | Create tenant |
| GET | `/v1/tenants` | List tenants (paginated, filterable) |
| GET | `/v1/tenants/stats` | Tenant statistics (dashboard) |
| GET | `/v1/tenants/{tenant_id}` | Get tenant by ID |
| PUT | `/v1/tenants/{tenant_id}` | Update tenant |
| DELETE | `/v1/tenants/{tenant_id}` | Decommission tenant |
| POST | `/v1/tenants/{tenant_id}/storage/configure` | Configure storage backend |
| POST | `/v1/tenants/{tenant_id}/storage/test-connection` | Test storage connectivity |
| GET | `/v1/tenants/{tenant_id}/storage/status` | Storage status and usage |
| GET | `/v1/tenants/{tenant_id}/usage` | Tenant usage statistics |
| GET | `/v1/tenants/{tenant_id}/quotas` | Get tenant quotas |
| PUT | `/v1/tenants/{tenant_id}/quotas` | Update tenant quotas |
| GET | `/v1/tenants/{tenant_id}/config` | Get tenant configuration |
| PUT | `/v1/tenants/{tenant_id}/config` | Update tenant configuration |
| GET | `/v1/tenants/{tenant_id}/compliance` | Compliance status |
| POST | `/v1/tenants/{tenant_id}/legal-hold` | Create legal hold |
| GET | `/v1/tenants/{tenant_id}/health` | Tenant health status |
| GET | `/v1/tenants/{tenant_id}/metrics` | Tenant performance metrics |
| GET | `/v1/tenants/{tenant_id}/alerts` | Tenant alert configuration |
| GET | `/v1/tenants/{tenant_id}/validate` | Validate tenant UUID |

**Service:** `TenantService`

---

## 6. Subscriptions & Billing

**Source:** `routers/subscription_api.py` | **Prefix:** `/v1` | **Tags:** `subscription`

### Tenant Subscription Management

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/tenants/{tenant_id}/subscription` | Get subscription details |
| PUT | `/v1/tenants/{tenant_id}/subscription` | Update subscription |
| DELETE | `/v1/tenants/{tenant_id}/subscription` | Delete tenant (with data cleanup) |
| GET | `/v1/tenants/{tenant_id}/features` | List tenant features |
| GET | `/v1/tenants/{tenant_id}/features/{feature_name}/access` | Check feature access |
| GET | `/v1/features/tier/{tier}` | Features for subscription tier |
| GET | `/v1/features/available` | List all available features |

### Usage & Billing

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/tenants/{tenant_id}/usage` | Tenant usage summary |
| GET | `/v1/tenants/{tenant_id}/usage/detailed` | Detailed usage breakdown |
| POST | `/v1/tenants/{tenant_id}/billing/generate` | Generate bill (YAML pricing) |
| GET | `/v1/tenants/{tenant_id}/billing/history` | Billing history |
| GET | `/v1/tenants/{tenant_id}/deletion/status` | Deletion status |

### Admin Rate Configuration

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/admin/rates` | List feature rates |
| POST | `/v1/admin/rates` | Create/update feature rate |
| PUT | `/v1/admin/rates/{feature_name}` | Update feature rate |
| GET | `/v1/admin/rates/{feature_name}/history` | Rate history |

### Admin Tenant Management

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/admin/tenants` | List all tenants with billing |
| GET | `/v1/admin/tenants/{tenant_id}/details` | Detailed tenant info |
| PUT | `/v1/admin/tenants/{tenant_id}/subscription` | Force subscription change |
| POST | `/v1/admin/tenants/{tenant_id}/billing/override` | Billing override |

### Compliance & Audit

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/admin/audit/subscription-changes` | Subscription audit trail |
| POST | `/v1/admin/compliance/reports` | Generate compliance report |
| GET | `/v1/admin/compliance/retention-status` | Retention compliance status |

**Service:** `SubscriptionService`, `BillingService`

---

## 7. Ingestion

**Source:** `routers/ingestion.py` | **Prefix:** `/v1/ingest`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/ingest/json` | Ingest single JSON log |
| POST | `/v1/ingest/json/batch` | Ingest batch of JSON logs |
| POST | `/v1/ingest/json/bulk` | Bulk ingest JSON logs |
| POST | `/v1/ingest/otlp` | Ingest OpenTelemetry logs |
| POST | `/v1/ingest/syslog` | Ingest syslog-format logs |
| POST | `/v1/ingest/nginx` | Ingest nginx access logs |
| POST | `/v1/ingest/cef` | Ingest CEF (Common Event Format) |
| POST | `/v1/ingest/text` | Ingest plain text logs |
| POST | `/v1/ingest/structured` | Ingest structured key-value logs |
| POST | `/v1/ingest/structured/batch` | Batch structured ingestion |
| POST | `/v1/ingest/text/batch` | Batch text ingestion |
| POST | `/v1/ingest/auto-detect` | Auto-detect format and ingest |
| POST | `/v1/ingest/auto-detect/batch` | Batch auto-detect ingestion |
| GET | `/v1/ingest/health` | Ingestion pipeline health |

**Auth:** `MiddlewareTenant` for tenant isolation.
**Service:** `IngestionService`, `ParserFactory`
**Notes:** Background task processing via `process_logs_and_tracking_background`.

---

## 8. Query Engine

**Source:** `routers/query.py` | **Prefix:** `/v1`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/query/advanced` | Advanced log query (filters, aggregations) |
| POST | `/v1/query/aggregate` | Aggregate log data with grouping |
| POST | `/v1/query/timeseries` | Time-series analysis |
| GET | `/v1/query/saved` | List saved queries |
| POST | `/v1/query/saved` | Save a query |
| GET | `/v1/query/saved/{query_id}` | Get saved query |
| PUT | `/v1/query/saved/{query_id}` | Update saved query |
| DELETE | `/v1/query/saved/{query_id}` | Delete saved query |
| POST | `/v1/query/validate` | Validate query structure |
| POST | `/v1/export` | Export query results (JSON/CSV) |
| GET | `/v1/logs` | Basic log retrieval (M0 compat) |

**Auth:** `MiddlewareTenant`
**Service:** `QueryService`, `QueryEngine`
**Notes:** Query results cached with 300s TTL.

---

## 9. Dashboards

**Source:** `routers/dashboard.py` | **Prefix:** `/v1/dashboards`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/dashboards` | List dashboards |
| POST | `/v1/dashboards` | Create dashboard |
| GET | `/v1/dashboards/{dashboard_id}` | Get dashboard config |
| PUT | `/v1/dashboards/{dashboard_id}` | Update dashboard |
| DELETE | `/v1/dashboards/{dashboard_id}` | Delete dashboard |
| GET | `/v1/dashboards/{dashboard_id}/data` | Get dashboard data |
| POST | `/v1/dashboards/{dashboard_id}/widgets` | Create widget |
| PUT | `/v1/dashboards/{dashboard_id}/widgets/{widget_id}` | Update widget |
| DELETE | `/v1/dashboards/{dashboard_id}/widgets/{widget_id}` | Delete widget |
| GET | `/v1/dashboards/{dashboard_id}/widgets/{widget_id}/data` | Get widget data |
| POST | `/v1/dashboards/{dashboard_id}/share` | Share dashboard |
| GET | `/v1/dashboards/{dashboard_id}/shares` | Get dashboard shares |

**Service:** `DashboardService`

---

## 10. Alerts

**Source:** `routers/alerts.py` | **Prefix:** `/v1/alerts`

### Alert Rules

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/alerts/rules` | Create alert rule |
| GET | `/v1/alerts/rules` | List alert rules |
| GET | `/v1/alerts/rules/{rule_id}` | Get alert rule |
| PUT | `/v1/alerts/rules/{rule_id}` | Update alert rule |
| DELETE | `/v1/alerts/rules/{rule_id}` | Delete alert rule |
| POST | `/v1/alerts/rules/{rule_id}/test` | Test alert rule |

### Alert Instances

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/alerts` | List alerts |
| GET | `/v1/alerts/{alert_id}` | Get alert details |
| POST | `/v1/alerts/{alert_id}/acknowledge` | Acknowledge alert |
| POST | `/v1/alerts/{alert_id}/resolve` | Resolve alert |
| GET | `/v1/alerts/rules/{rule_id}/instances` | Alert instances by rule |
| PUT | `/v1/alerts/rules/{rule_id}/instances/bulk-update` | Bulk update instances |

### Stats & Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/alerts/stats` | Alert engine statistics |
| GET | `/v1/alerts/stats/overview` | Alert overview stats |
| GET | `/v1/alerts/health` | Alert engine health |

### Notifications & Integrations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/alerts/notifications/channels` | List notification channels |
| POST | `/v1/alerts/notifications/channels` | Create notification channel |
| GET | `/v1/alerts/integrations/webhooks` | List webhooks |
| POST | `/v1/alerts/integrations/webhooks` | Create webhook |

### Real-time

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/alerts/events/stream` | SSE alert stream |

**Service:** `AlertService`

---

## 11. Alert Correlation

**Source:** `routers/alert_correlation_api.py` | **Prefix:** `/v1/alerts/correlation` | **Tags:** `alert-correlation`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/alerts/correlation/groups` | Correlated alert groups |
| GET | `/v1/alerts/correlation/fatigue-score` | Alert fatigue score (0-100) |
| GET | `/v1/alerts/correlation/service-dependencies` | Service dependency correlations |
| GET | `/v1/alerts/correlation/duplicates` | Duplicate alert detection |
| GET | `/v1/alerts/correlation/trends` | Alert trend analysis |
| GET | `/v1/alerts/correlation/summary` | Combined correlation summary |

**Query params:** `time_range` (default `24h`), `min_group_size`, `granularity`.
**Service:** `AlertCorrelationService`

---

## 12. Security Analytics

**Source:** `routers/security_api.py` | **Prefix:** `/v1/security` | **Tags:** `security-analytics`

### Sigma Rules

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/security/rules` | Create Sigma rule |
| GET | `/v1/security/rules` | List Sigma rules |
| GET | `/v1/security/rules/{rule_id}` | Get Sigma rule |
| PUT | `/v1/security/rules/{rule_id}` | Update Sigma rule |
| DELETE | `/v1/security/rules/{rule_id}` | Delete Sigma rule |
| POST | `/v1/security/rules/{rule_id}/test` | Test Sigma rule |

### Security Events

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/security/events` | List security events |
| POST | `/v1/security/events/{event_id}/acknowledge` | Acknowledge event |
| POST | `/v1/security/events/{event_id}/investigate` | Mark under investigation |
| POST | `/v1/security/events/{event_id}/resolve` | Resolve event |
| POST | `/v1/security/events/{event_id}/false-positive` | Mark as false positive |
| POST | `/v1/security/rules/{rule_id}/events/bulk-update` | Bulk update events by rule |

### Threat Intelligence & Hunting

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/security/threat-intel` | List threat intelligence |
| POST | `/v1/security/threat-hunting/campaigns` | Start threat hunting campaign |
| GET | `/v1/security/threat-hunting/rules` | Discover threat hunt rules |

### Dashboard & Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/security/health` | Security engine health |
| GET | `/v1/security/dashboard` | Security dashboard data |
| GET | `/v1/security/events/stream` | SSE security events stream |

**Service:** `SecurityService`

---

## 13. Observability

**Source:** `routers/observability_api.py` | **Prefix:** `/v1/observability` | **Tags:** `observability`

### Traces

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/observability/traces` | Ingest trace spans |
| GET | `/v1/observability/traces/search` | Search traces |
| GET | `/v1/observability/traces/{trace_id}` | Get trace details |

### Metrics

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/observability/metrics` | Ingest metrics |
| GET | `/v1/observability/metrics/query` | Query metrics |
| GET | `/v1/observability/metrics/standard` | Standard metrics |

### Service Map & APM

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/observability/service-map` | Service dependency map |
| GET | `/v1/observability/apm/overview` | APM overview |
| GET | `/v1/observability/apm/services` | APM service list |
| GET | `/v1/observability/apm/services/{service_name}/endpoints` | Service endpoints |
| GET | `/v1/observability/apm/services/{service_name}/error-rates` | Service error rates |
| GET | `/v1/observability/apm/transactions/{transaction_id}` | Transaction detail |

### Health & Analytics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/observability/services/{service_name}/health` | Service health |
| GET | `/v1/observability/trends` | Observability trends |
| GET | `/v1/observability/analytics` | Observability analytics |

### Real-time Streams

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/observability/stream/traces` | SSE trace stream |
| GET | `/v1/observability/stream/metrics` | SSE metric stream |

**Service:** `ObservabilityService`, `ObservabilityDAO`, `ObservabilityEventPublisher`

---

## 14. AI & ML

**Source:** `routers/ai_api.py` | **Prefix:** `/v1/ai` | **Tags:** `ai`

### Natural Language Query

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/ai/query` | Process natural language query |
| GET | `/v1/ai/query/history` | Query history |
| POST | `/v1/ai/query/feedback` | Submit query feedback |

### Investigations & RCA

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/ai/investigate` | Start AI investigation |
| GET | `/v1/ai/investigate/{investigation_id}` | Get investigation result |
| POST | `/v1/ai/analyze-incident` | Root cause analysis |

### Baselines & Anomaly Detection

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/ai/baselines` | Save baseline |
| GET | `/v1/ai/baselines` | List baselines |
| POST | `/v1/ai/anomalies/detect` | Detect anomalies |
| POST | `/v1/ai/anomalies/detect/multi-metric` | Multi-metric anomaly detection |
| POST | `/v1/ai/anomalies/{anomaly_id}/analyze` | Deep anomaly analysis |
| POST | `/v1/ai/anomalies/{anomaly_id}/dismiss` | Dismiss anomaly |
| GET | `/v1/ai/anomalies/history` | Anomaly history |
| GET | `/v1/ai/anomalies/stats` | Anomaly statistics |

### Knowledge Base & Insights

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/ai/knowledge/search` | Search knowledge base |
| POST | `/v1/ai/knowledge/solutions` | Add solution |
| GET | `/v1/ai/insights` | Operational insights |
| POST | `/v1/ai/correlate` | Event correlation |

### Predictions & Optimization

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/ai/predict` | Predict incidents |
| POST | `/v1/ai/optimize` | Optimization recommendations |

### Model Management

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/ai/models` | List AI models |
| GET | `/v1/ai/models/health` | Model health status |
| GET | `/v1/ai/models/baselines/visualization` | Baseline visualization |
| PUT | `/v1/ai/models/thresholds` | Update thresholds |
| POST | `/v1/ai/models/retrain` | Retrain model |

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/ai/health` | AI service health |

**Service:** `AIService`, `get_rca_engine()`, `get_anomaly_detector()`, `get_nlq_processor()`

---

## 15. Predictive Analytics

**Source:** `routers/predictive_api.py` | **Prefix:** `/v1/ai/predictions` | **Tags:** `ai-predictions`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/ai/predictions/forecast` | Trend forecasting (linear regression) |
| GET | `/v1/ai/predictions/capacity` | Capacity planning & growth analysis |
| GET | `/v1/ai/predictions/sla-breach` | SLA breach prediction per service |
| POST | `/v1/ai/predictions/what-if` | What-if scenario modeling |
| GET | `/v1/ai/predictions/summary` | Combined prediction summary (risk 0-100) |

**Query params:** `metric`, `time_range`, `forecast_horizon`, `sla_threshold`, `granularity`.
**Request body (what-if):** `{ scenario_type, parameters }`.
**Service:** `PredictiveAnalyticsService`

---

## 16. Storage & Retention

**Source:** `routers/storage.py` | **Prefix:** `/v1/storage`

### Retention Policies

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/storage/retention/{customer_id}` | Create retention policy |
| GET | `/v1/storage/retention/{customer_id}` | Get retention policy |
| PUT | `/v1/storage/retention/{customer_id}` | Update retention policy |

### Lifecycle Operations

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/storage/cleanup` | Trigger TTL cleanup |
| POST | `/v1/storage/archive/{customer_id}` | Archive old data to cold storage |

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/storage/health` | Customer storage health |
| GET | `/v1/storage/health/infrastructure` | Infrastructure health (admin) |
| GET | `/v1/storage/health/{target_customer_id}` | Specific customer health (admin) |

### Quota Sync

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/storage/quota/sync` | Sync storage quota (own tenant) |
| POST | `/v1/storage/quota/sync/all` | Sync all tenants (admin) |

### Archives

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/storage/archives/{customer_id}` | List archived data |
| GET | `/v1/storage/archive/{archive_key}` | Get archive metadata |
| POST | `/v1/storage/archive/{archive_key}/download` | Download archived data |
| POST | `/v1/storage/query-archive` | Query archived data (experimental) |

**Service:** `StorageService`, `StorageQuotaSyncService`

---

## 17. Schema Registry

**Source:** `routers/schema_registry_api.py` | **Prefix:** `/v1/schemas` | **Tags:** `schema-registry`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/schemas/register` | Register log schema |
| GET | `/v1/schemas` | List registered schemas |
| DELETE | `/v1/schemas/{schema_id}` | Delete schema |
| GET | `/v1/schemas/stats` | Schema statistics |
| GET | `/v1/schemas/standard-fields` | Standard field definitions |
| POST | `/v1/schemas/test-normalization` | Test normalization (~10us) |

**Service:** `HighPerformanceNormalizer`

---

## 18. Events (Kafka)

**Source:** `routers/events_api.py` | **Prefix:** `/v1/events` | **Tags:** `events`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/events/health` | Event system health |
| GET | `/v1/events/metrics` | Event system metrics |
| GET | `/v1/events/topics` | List Kafka topics |
| GET | `/v1/events/topics/{topic_name}` | Describe Kafka topic |
| POST | `/v1/events/topics/{topic_key}/create` | Create Kafka topic |
| GET | `/v1/events/cluster` | Kafka cluster info |
| POST | `/v1/events/setup` | Setup event system |
| GET | `/v1/events/config` | Event system config |

**Service:** `event_publisher_manager`, `event_subscriber_manager`, `kafka_admin`

---

## 19. Streaming (SSE)

**Source:** `routers/streaming_api.py` | **Prefix:** `/v1/stream` | **Tags:** `streaming`

All streaming endpoints use Server-Sent Events (SSE) via `text/event-stream`.
Customer ID can be passed via `X-Customer-ID` header or `customer_id` query param (since `EventSource` cannot send headers).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/stream/metrics` | Real-time metrics (Kafka-driven) |
| GET | `/v1/stream/traces` | Real-time traces (Kafka-driven) |
| GET | `/v1/stream/security` | Real-time security events (Kafka-driven) |
| GET | `/v1/stream/alerts` | Real-time alerts (Kafka-driven) |
| GET | `/v1/stream/usage` | Real-time usage data (polling) |
| GET | `/v1/stream/ai-insights` | Real-time AI insights (polling) |
| GET | `/v1/stream/anomalies` | Real-time anomaly detections (Kafka-driven) |
| GET | `/v1/stream/health` | Streaming service health |
| GET | `/v1/stream/test-alert` | Publish test alert (diagnostic) |

**Query params (anomalies):** `severity_threshold`, `services`, `categories`.
**Service:** `KafkaEventSubscriber`, `StreamingConnectionManager`, config-based filtering via `StreamingConfigService`.

---

## 20. Streaming Configuration

**Source:** `routers/streaming_config_api.py` | **Prefix:** `/v1/streaming/config` | **Tags:** `streaming-config`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/streaming/config/` | Get all streaming configs for customer |
| GET | `/v1/streaming/config/metrics` | Get metrics streaming config |
| POST | `/v1/streaming/config/metrics` | Set metrics streaming config |
| DELETE | `/v1/streaming/config/metrics` | Reset metrics config to defaults |
| GET | `/v1/streaming/config/traces` | Get traces streaming config |
| POST | `/v1/streaming/config/traces` | Set traces streaming config |
| DELETE | `/v1/streaming/config/traces` | Reset traces config to defaults |

**Config fields (metrics):** `enabled`, `sample_rate`, `min_metrics_count`, `include_services`, `exclude_services`, `priority_metrics`, `max_events_per_minute`, `include_errors_only`.
**Config fields (traces):** `enabled`, `sample_rate`, `min_traces_count`, `include_services`, `exclude_services`, `min_duration_ms`, `include_errors_only`, `max_events_per_minute`, `priority_operations`, `include_status`.
**Service:** `StreamingConfigService`

---

## 21. Usage Analytics & Billing

**Source:** `routers/usage_api.py` | **Prefix:** `/v1` | **Tags:** `Usage Analytics & Billing`

### Current Usage

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/usage/current/{tenant_id}` | Current month usage |
| GET | `/v1/usage/history/{tenant_id}` | Usage history (1-12 months) |
| GET | `/v1/usage/realtime/{tenant_id}` | Real-time usage (configurable window) |
| GET | `/v1/usage/overview/stats` | Usage overview for dashboard widgets |

### Billing

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/billing/estimate/{tenant_id}` | Current billing estimate |
| POST | `/v1/billing/generate/{tenant_id}` | Generate invoice (admin, idempotent) |

### Platform Analytics (Admin)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/analytics/usage-trends` | Platform-wide usage trends |
| GET | `/v1/analytics/feature-usage` | Feature usage analytics |

### Costs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/costs/breakdown/{tenant_id}` | Cost breakdown (compute/storage/network) |
| POST | `/v1/costs/alerts/{tenant_id}` | Create cost threshold alert |

### Export

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/usage/export/{tenant_id}` | Export usage data (CSV/JSON/XLSX) |

### Admin Operations

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/admin/audit/bulk-insert` | Bulk insert audit records (max 5000) |
| GET | `/v1/admin/database/partitions` | Database partition info |
| POST | `/v1/admin/usage/flush-buffer` | Flush usage buffer |
| GET | `/v1/admin/usage/buffer-status` | Usage buffer status |

### SSE Stream

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/usage-stream/{tenant_id}` | Real-time usage SSE stream |

**Service:** `UsageService`

---

## 22. Quota Management

**Source:** `routers/quota_management_api.py` | **Prefix:** `/v1/admin/quotas`

### Admin Operations (platform admin only)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/admin/quotas/reset-schedule` | Quota reset schedule |
| POST | `/v1/admin/quotas/check-and-reset` | Trigger quota reset check |
| POST | `/v1/admin/quotas/reset-tenant/{tenant_id}` | Force reset tenant quotas |
| GET | `/v1/admin/quotas/scheduler/status` | Scheduler status |
| POST | `/v1/admin/quotas/scheduler/start` | Start quota scheduler |
| POST | `/v1/admin/quotas/scheduler/stop` | Stop quota scheduler |

### Tenant-Facing

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/admin/quotas/current/{tenant_id}` | Current quota status |
| GET | `/v1/admin/quotas/usage-history/{tenant_id}` | Quota usage history |
| POST | `/v1/admin/quotas/reset-request/{tenant_id}` | Request quota reset (self-service) |

**Valid quota types:** `daily_ingestion`, `monthly_ingestion`, `storage_gb`, `api_calls`, `users`, `alerts`.
**Service:** `QuotaResetService`, `QuotaResetScheduler`

---

## 23. Enterprise

**Source:** `routers/enterprise_api.py` | **Prefix:** `/v1/enterprise` | **Tags:** `enterprise`

### Authentication & SSO

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/enterprise/auth/oidc/configure` | Configure OIDC provider |
| GET | `/v1/enterprise/auth/providers` | List auth providers |
| POST | `/v1/enterprise/auth/api-keys` | Generate API key |
| GET | `/v1/enterprise/auth/api-keys` | List API keys |
| DELETE | `/v1/enterprise/auth/api-keys/{key_id}` | Revoke API key |
| POST | `/v1/enterprise/auth/mfa/setup` | Setup MFA |

### RBAC

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/enterprise/rbac/roles` | List roles |
| POST | `/v1/enterprise/rbac/roles` | Create custom role |
| PUT | `/v1/enterprise/rbac/users/{user_id}/roles` | Assign roles |
| GET | `/v1/enterprise/rbac/permissions` | Get user permissions |

### Tenant Management

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/enterprise/tenants` | List tenants |
| POST | `/v1/enterprise/tenants` | Create tenant |
| PUT | `/v1/enterprise/tenants/{tenant_id}/settings` | Update tenant settings |

### Compliance & Audit

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/enterprise/compliance/reports` | Generate compliance report |
| POST | `/v1/enterprise/compliance/legal-hold` | Create legal hold |
| GET | `/v1/enterprise/audit-logs` | Audit logs |

### Integrations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/enterprise/integrations` | List integrations |
| POST | `/v1/enterprise/integrations/{integration_type}/configure` | Configure integration |
| GET | `/v1/enterprise/integrations/{integration_type}/status` | Integration health |

### System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/enterprise/usage/billing` | Usage billing data |
| GET | `/v1/enterprise/system/health` | Enterprise system health |
| POST | `/v1/enterprise/backup/configure` | Configure backup policy |
| GET | `/v1/enterprise/metrics` | Enterprise metrics |
| GET | `/v1/enterprise/health` | Enterprise health check |

**Service:** `EnterpriseService`

---

## Common Patterns

### Authentication

Most endpoints require authentication via one of:

- **JWT Bearer token** in `Authorization` header (handled by `get_current_user`)
- **`X-Customer-ID` header** for tenant isolation (resolved by `MiddlewareTenant`)
- **Platform admin guard** via `require_platform_admin` dependency
- **Tenant admin guard** via `require_tenant_admin` dependency

### Error Responses

All endpoints return standard HTTP error codes:

- `400` - Bad request / validation error
- `401` - Unauthorized
- `403` - Forbidden (insufficient permissions)
- `404` - Resource not found
- `409` - Conflict (duplicate resource)
- `500` - Internal server error

Error body format:
```json
{ "detail": "Human-readable error message" }
```

### Multi-Tenant Isolation

Every data query is scoped to `customer_id`. This is enforced at:
1. Middleware level (`MiddlewareTenant` or `X-Customer-ID` header)
2. Query level (filters appended to all ClickHouse queries)
3. Service level (DAOs enforce tenant boundaries)

### SSE Streaming

Server-Sent Event endpoints (prefix `/v1/stream/*`, plus several in other routers) follow a common pattern:
- Response type: `text/event-stream`
- Keepalive messages sent every 30 seconds
- Graceful shutdown via `StreamingConnectionManager`
- Kafka-driven (real events) or polling-driven (periodic service calls)
- Customer ID can be passed via header or query param
