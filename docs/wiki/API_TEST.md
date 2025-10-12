# Logforge API Testing Results

## Auth APIs

### Test Progress
- [✅] POST /v1/auth/login (login API )
  #### This API works properly and updates/inserts data in:
    - updates users_mt (last_login_at timestamp)
    - inserts in user_sessions_mt (new session record)
    - reads from user_tenant_roles_mt (to get user permissions)

## Log Ingestion Router APIs

### Test Progress
- [✅] POST /v1/ingest/logs (Generic JSON log ingestion)
- [✅] POST /v1/ingest/logs/batch (High-performance batch ingestion)
- [✅] POST /v1/ingest/otlp (OpenTelemetry Protocol logs)
- [✅] POST /v1/ingest/syslog (RFC 3164/5424 syslog messages)
- [✅] POST /v1/ingest/nginx (Nginx access log parsing)
- [✅] POST /v1/ingest/cef (Common Event Format - security logs)
- [✅] POST /v1/ingest/text (Plain text with regex matching)
- [✅] POST /v1/ingest/structured (Application JSON logs)
- [✅] POST /v1/ingest (Auto-detect format and parse)
  #### Ingestion APIs work properly creates logs entry in 
    - inserts in logs_raw_mt 
    - inserts in ingestion_stats_mt
    - inserts in usage_records_mt
    - updates tenant_quotas_mt


## Query Router APIs
- [✅] GET /v1/logs (Simple log retrieval)
  #### This API works properly
  - reads from logs_raw_mt: Primary log storage table (READ-ONLY access)

- [✅] GET /v1/saved (List saved queries)
- [✅] POST /v1/saved (Save query for reuse)
- [✅] GET /v1/saved/{id} (Get specific saved query)
- [✅] DELETE /v1/saved/{id} (Delete saved query)
  #### These APIs work properly and do CRUD on 
  - saved_queries_mt

- [✅] POST /v1/query/advanced (Advanced log querying with filters, aggregations, time-series)
  #### This API works properly
  - query_cache_mt
  - logs_raw_mt

## Dashboard Router
- [✅] GET /v1/dashboards (List available enterprise dashboards)
- [✅] GET /v1/dashboards/{id} (Get specific dashboard definition)
- [✅] GET /v1/dashboards/{id}/data (Get dashboard data with filters)
- [✅] POST /v1/export (Export query results (JSON, CSV))
- [✅] GET /v1/dashboards/{id}/realtime (Real-time dashboard data updates)
- [✅] GET /v1/dashboards/health (Dashboard service health)
  #### This API works properly
  - DB tables updated 
    - dashboards_mt - Custom dashboard storage
    - dashboard_widgets_mt - Dashboard widget configurations
    - dashboard_shares_mt - Dashboard sharing permissions

## Storage Router

### TTL and Retention Management
- [✅] **POST /v1/storage/retention/{customer_id}** (Create retention policy)
  - **Purpose**: Create new TTL retention policy for customer  
  - **Tables**: retention_policies_mt
  - **Request**: `{ "hot_retention_days": 30, "cold_retention_days": 90, "archive_retention_days": 365, "compression_enabled": true, "auto_deletion_enabled": false }`
  - **Auth**: Customer can only create their own policies

- [✅] **GET /v1/storage/retention/{customer_id}** (Get retention policy)
  - **Purpose**: Retrieve current retention policy for customer
  - **Tables**: retention_policies_mt (READ)
  - **Auth**: Customer can only see their own policies

- [✅] **PUT /v1/storage/retention/{customer_id}** (Update retention policy)
  - **Purpose**: Update existing retention policy for customer
  - **Tables**: retention_policies_mt (UPDATE)
  - **Auth**: Customer can only update their own policies

### Data Operations
- [✅] **POST /v1/storage/cleanup** (Trigger manual cleanup)
  - **Purpose**: Trigger manual cleanup based on TTL policies
  - **Tables**: logs_raw_mt (DELETE old data)
  - **Request**: `{ "policy_name": "optional" }`
  - **Auth**: Uses authenticated tenant from middleware

- [✅] **POST /v1/storage/archive/{customer_id}** (Archive old data)
  - **Purpose**: Archive old data to cold storage (MinIO/S3)
  - **Tables**: logs_raw_mt (DELETE), archive_metadata_mt (INSERT)
  - **Storage**: Uploads to MinIO/S3 with path: `archived_logs/{customer_id}/{date_range}.parquet`
  - **Auth**: Customer can only archive their own data

### Health Monitoring
- [✅] **GET /v1/storage/health** (Customer storage health)
  - **Purpose**: Get customer-specific storage health metrics
  - **Tables**: logs_raw_mt, retention_policies_mt, archive_metadata_mt (READ)
  - **Auth**: Tenant-level access (customer sees own data only)

- [✅] **GET /v1/storage/health/{target_customer_id}** (Specific customer health)
  - **Purpose**: Get storage health for specific customer (admin or self)
  - **Tables**: logs_raw_mt, retention_policies_mt, archive_metadata_mt (READ)
  - **Auth**: Admin access required for cross-tenant viewing

- [✅] **GET /v1/storage/health/infrastructure** (Infrastructure health)
  - **Purpose**: System-wide infrastructure health check (Platform Admin only)
  - **Tables**: System-wide metrics across all tenants
  - **Auth**: Platform admin roles only ('super_admin', 'admin', 'support_admin')

### Quota Management
- [✅] **POST /v1/storage/quota/sync** (Sync tenant quota)
  - **Purpose**: Trigger manual storage quota sync for authenticated tenant
  - **Tables**: tenant_quotas_mt, usage_records_mt
  - **Auth**: Tenant-level access

- [✅] **POST /v1/storage/quota/sync/all** (Sync all tenant quotas)
  - **Purpose**: Trigger storage quota sync for all tenants (Platform Admin only)
  - **Tables**: tenant_quotas_mt, usage_records_mt (all tenants)
  - **Auth**: Platform admin roles only ('super_admin', 'admin')

### Archive Retrieval APIs
- [✅] **GET /v1/storage/archives/{customer_id}** (List customer archives)
  - **Purpose**: List archived data for customer with pagination and filtering
  - **Tables**: archive_metadata_mt (READ)
  - **Query Params**: `limit=50`, `offset=0`, `start_date`, `end_date`
  - **Auth**: Customer can only see their own archives

- [✅] **GET /v1/storage/archive/{archive_key}** (Get archive metadata)
  - **Purpose**: Get metadata for a specific archive file
  - **Tables**: archive_metadata_mt (READ)
  - **Auth**: Tenant validation via middleware

- [✅] **POST /v1/storage/archive/{archive_key}/download** (Download archive)
  - **Purpose**: Generate presigned URL for secure archive download
  - **Tables**: archive_metadata_mt (READ), archive_access_log_mt (INSERT)
  - **Storage**: Generates presigned MinIO/S3 URLs with expiration
  - **Auth**: Tenant validation + access logging

- [✅] **POST /v1/storage/query-archive** (Query archived data)
  - **Purpose**: Query data from archived files (experimental feature)
  - **Tables**: archive_metadata_mt (READ), archive_access_log_mt (INSERT)  
  - **Request**: `{ "archive_keys": ["key1", "key2"], "filters": {}, "limit": 1000 }`
  - **Storage**: Reads Parquet files from MinIO/S3 and applies filters
  - **Auth**: Tenant validation + access logging
    ### this feature is not ready, it returns metadata only

### Database Tables Used
- **retention_policies_mt**: TTL policy storage and management
- **logs_raw_mt**: Primary log data (cleanup/archive operations)
- **archive_metadata_mt**: Archive tracking and metadata
- **archive_access_log_mt**: Audit trail for archive access
- **tenant_quotas_mt**: Storage quota tracking per tenant
- **usage_records_mt**: API usage and billing data

## Alerts Router

The Alerts Router (`/v1/alerts/*`) provides comprehensive alert rule management, alert instance monitoring, and notification system integration for the Logforge platform.

**Base URL**: `/v1/alerts`  
**Authentication**: Bearer JWT + X-Customer-ID header  
**Database Tables**: `alert_rules_mt`, `alert_instances_mt`, `notification_channels_mt`, `alert_rule_states_mt`

### Alert Rules Management

#### 1. Create Alert Rule
- **Endpoint**: `POST /v1/alerts/rules`
- **Purpose**: Create a new alert rule with conditions and notification settings
- **Database Table**: `alert_rules_mt`
- **Request Body**:
```json
{
  "name": "High Error Rate Alert",
  "description": "Alert when error rate exceeds 5% in 5 minutes",
  "rule_type": "threshold",
  "severity": "high",
  "enabled": true,
  "evaluation_interval": 300,
  "cooldown_period": 600,
  "conditions": [
    {
      "field": "level",
      "operator": "eq",
      "value": "error"
    }
  ],
  "filters": [
    {
      "field": "service",
      "operator": "eq", 
      "value": "web-api"
    }
  ],
  "notification_channels": ["email-ops", "slack-alerts"],
  "tags": ["web", "critical"]
}
```

#### 2. List Alert Rules
- **Endpoint**: `GET /v1/alerts/rules`
- **Purpose**: Retrieve all alert rules for the customer with optional filtering
- **Database Table**: `alert_rules_mt`
- **Query Parameters**:
  - `enabled` (boolean): Filter by enabled status
  - `severity` (string): Filter by severity level
  - `limit` (int, default: 100): Number of results to return
  - `offset` (int, default: 0): Pagination offset
- **Response**:
```json
{
  "rules": [
    {
      "id": "rule-123",
      "name": "High Error Rate Alert",
      "description": "Alert when error rate exceeds 5%",
      "rule_type": "threshold",
      "severity": "high",
      "enabled": true,
      "created_at": "2025-10-11T10:00:00Z",
      "created_by": "api-user",
      "customer_id": "tenant-123"
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0,
  "customer_id": "tenant-123"
}
```

#### 3. Get Specific Alert Rule
- **Endpoint**: `GET /v1/alerts/rules/{id}`
- **Purpose**: Retrieve detailed information about a specific alert rule
- **Database Table**: `alert_rules_mt`
- **URL Parameters**:
  - `{id}`: Alert rule ID
- **Response**:
```json
{
  "id": "rule-123",
  "name": "High Error Rate Alert",
  "description": "Alert when error rate exceeds 5% in 5 minutes",
  "rule_type": "threshold",
  "severity": "high",
  "enabled": true,
  "evaluation_interval": 300,
  "cooldown_period": 600,
  "conditions": [...],
  "filters": [...],
  "notification_channels": ["email-ops", "slack-alerts"],
  "tags": ["web", "critical"],
  "created_at": "2025-10-11T10:00:00Z",
  "updated_at": "2025-10-11T10:00:00Z",
  "created_by": "api-user",
  "customer_id": "tenant-123"
}
```

#### 4. Update Alert Rule
- **Endpoint**: `PUT /v1/alerts/rules/{id}`
- **Purpose**: Modify an existing alert rule
- **Database Table**: `alert_rules_mt`
- **URL Parameters**:
  - `{id}`: Alert rule ID
- **Request Body** (all fields optional):
```json
{
  "name": "Updated Alert Name",
  "description": "Updated description",
  "enabled": false,
  "conditions": [...],
  "filters": [...],
  "notification_channels": ["updated-channel"],
  "severity": "critical"
}
```

#### 5. Test Alert Rule
- **Endpoint**: `POST /v1/alerts/rules/{id}/test`
- **Database Tables**: `alert_rules_mt`, `logs_raw_mt`

#### 6. Delete Alert Rule
- **Endpoint**: `DELETE /v1/alerts/rules/{id}`
- **Purpose**: Remove an alert rule permanently
- **Database Table**: `alert_rules_mt`
- **URL Parameters**:
  - `{id}`: Alert rule ID
- **Response**:
```json
{
  "status": "deleted",
  "rule_id": "rule-123",
  "customer_id": "tenant-123"
}
```

### Data Validation

**Rule Types**: `threshold`, `anomaly`, `pattern`, `frequency`, `absence`, `sequence`  
**Severity Levels**: `low`, `medium`, `high`, `critical`  
**Required Fields**: `name`, `customer_id` (auto-populated)  
**No Mock Data**: All endpoints use real database operations via `AlertDAO` and `DatabaseLayer`

### Database Schema

```sql
-- Primary alert rules table
alert_rules_mt (
  id String,
  customer_id String,
  name String,
  description String,
  rule_type String,
  query String,
  condition_config String,
  notification_channels String,
  severity String,
  is_enabled Boolean,
  cooldown_minutes Int32,
  created_at DateTime,
  updated_at DateTime,
  created_by String
)

-- Alert instances when rules fire
alert_instances_mt (
  id String,
  rule_id String,
  customer_id String,
  status String,
  triggered_at DateTime,
  resolved_at DateTime,
  acknowledged_at DateTime
)

-- Notification channels configuration
notification_channels_mt (
  id String,
  customer_id String,
  name String,
  type String,
  config String,
  enabled Boolean
)

-- Alert rule evaluation states
alert_rule_states_mt (
  rule_id String,
  customer_id String,
  last_evaluation DateTime,
  last_triggered DateTime,
  evaluation_count Int64
)
```

### Error Handling

- **404 Not Found**: Alert rule does not exist or doesn't belong to customer
- **400 Bad Request**: Invalid rule type, severity, or missing required fields
- **403 Forbidden**: Cross-tenant access denied
- **500 Internal Server Error**: Database operation failures

---

## Test Results
