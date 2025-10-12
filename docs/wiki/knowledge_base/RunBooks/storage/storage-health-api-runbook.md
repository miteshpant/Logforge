# Storage Health API Runbook

## Overview
The `/v1/storage/health` endpoint provides comprehensive storage health monitoring for individual tenants in the Logforge platform. This API returns real-time storage usage, quota status, performance metrics, and infrastructure health information.

## API Endpoint Details

### **GET /v1/storage/health**
Retrieve comprehensive storage health information for the authenticated tenant.

**Authentication**: Bearer token required  
**Authorization**: X-Customer-ID header required (tenant isolation)  
**Method**: GET  
**Content-Type**: application/json

### Request Headers
```http
Authorization: Bearer {auth_token}
X-Customer-ID: {tenant_id}
Content-Type: application/json
```

### Response Format
```json
{
  "overall_status": "healthy|warning|critical",
  "customer_id": "505908f9-8718-4dea-b2d8-9b9e5ae0bd45",
  "infrastructure": {
    "storage_backend": {
      "type": "minio|s3|gcs|azure",
      "status": "healthy|warning|critical",
      "endpoint": "localhost:9003",
      "bucket": "logforge-saas-logs"
    },
    "capacity": {
      "total_capacity_gb": 10000.0,
      "used_capacity_gb": 0,
      "available_capacity_gb": 10000.0,
      "usage_percentage": 0.0
    },
    "performance": {
      "daily_operations": 1000,
      "avg_operation_time_ms": 45.0,
      "read_iops": 1200,
      "write_iops": 800,
      "throughput_mbps": 500
    },
    "system_status": "healthy|warning|critical"
  },
  "customer_data": {
    "status": "healthy|warning|critical",
    "quotas": [
      {
        "quota_type": "storage_gb",
        "quota_limit": 107374182400,
        "current_usage": 23091,
        "reset_period": "never"
      }
    ],
    "usage_stats": {
      "total_logs_current_month": 85,
      "storage_gb": 0.000021,
      "monthly_ingestion_gb": 0.000018,
      "hot_storage_gb": 0.000021,
      "cold_storage_gb": 0,
      "archive_storage_gb": 0,
      "current_month": "2025-10",
      "performance": {
        "avg_ingestion_time_ms": 245.50,
        "monthly_ingestion_calls": 12,
        "avg_bytes_per_call": 1920.33
      }
    },
    "recent_operations": []
  },
  "checked_at": "2025-10-10T12:32:20.998504+00:00"
}
```

## Data Sources & Tables

### Primary Data Sources
1. **`tenant_quotas_mt`** - Tenant quota limits and current usage (bytes)
2. **`ingestion_stats_mt`** - Current month ingestion performance and volume
3. **`storage_operations_mt`** - Recent storage operations history
4. **`storage_backends_mt`** - Storage backend configuration and health

### Database Queries Used
```sql
-- Tenant quotas (storage and ingestion)
SELECT quota_type, quota_limit, current_usage, reset_period
FROM tenant_quotas_mt 
WHERE customer_id = 'tenant_id'

-- Current month performance metrics
SELECT 
    count(*) as log_count,
    avg(processing_time_ms) as avg_processing_time,
    sum(bytes_ingested) as total_bytes_ingested,
    sum(records_ingested) as total_records_ingested
FROM ingestion_stats_mt 
WHERE customer_id = 'tenant_id'
AND timestamp >= date_trunc('month', now())
```

## Key Features

### 1. **Real-Time Storage Metrics**
- **Current Storage Usage**: Accurate GB conversion from bytes stored in database
- **Monthly Ingestion**: Current month ingestion volume and performance
- **Storage Types**: Hot storage (current), cold storage (future), archive storage (future)

### 2. **Quota Health Monitoring**
- **Healthy**: < 80% quota usage
- **Warning**: 80-90% quota usage  
- **Critical**: > 90% quota usage
- **Unit Conversion**: Database stores bytes, API displays GB for readability

### 3. **Performance Analytics**
- **Ingestion Performance**: Average processing time per API call
- **Monthly Metrics**: Calls made, bytes processed, throughput rates
- **Time Scope**: Current month focus for relevant metrics

### 4. **Infrastructure Health**
- **Storage Backend**: MinIO/S3/GCS/Azure status and configuration
- **System Capacity**: Platform-wide storage capacity and usage
- **Operations**: Recent storage operations and their outcomes

## Unit Conversion Logic

### Critical Implementation Details
```python
# Database Storage (tenant_quotas_mt)
current_usage = 23091        # Stored as bytes
quota_limit = 107374182400   # Stored as bytes (100 GB)

# API Display Conversion
storage_gb = current_usage / (1024**3)           # 0.000021 GB
quota_limit_gb = quota_limit / (1024**3)         # 100.0 GB
usage_percentage = (storage_gb / quota_limit_gb) * 100  # 0.000021%
```

### Storage Type Breakdown
- **Hot Storage**: All current storage (immediate access)
- **Cold Storage**: 0 (future feature for infrequent access)
- **Archive Storage**: 0 (future feature for long-term retention)

## Common Use Cases

### 1. **Tenant Storage Monitoring**
Monitor individual tenant storage consumption and quota status.

**Example Request:**
```bash
curl -X GET "http://localhost:7080/v1/storage/health" \
  -H "Authorization: Bearer token123" \
  -H "X-Customer-ID: 505908f9-8718-4dea-b2d8-9b9e5ae0bd45"
```

**Use Case**: Dashboard widgets, quota alerts, billing calculations

### 2. **Performance Analysis**
Analyze tenant-specific ingestion performance and identify bottlenecks.

**Key Metrics:**
- `avg_ingestion_time_ms`: Processing latency per API call
- `monthly_ingestion_calls`: API usage frequency  
- `avg_bytes_per_call`: Data volume per ingestion request

### 3. **Capacity Planning**
Monitor storage growth trends and predict quota needs.

**Growth Indicators:**
- `monthly_ingestion_gb`: Current month data growth
- `storage_gb`: Cumulative storage usage
- `usage_percentage`: Quota utilization trend

## Troubleshooting Guide

### Problem: Storage Health Returns 500 Error

**Common Causes:**
1. **Database Connection Issues**
2. **Missing Tenant Quotas**
3. **Invalid Customer ID**
4. **Schema Compatibility Issues**

**Investigation Steps:**
```bash
# Check if tenant exists in quotas
curl -X GET "http://localhost:7080/v1/admin/tenants/{tenant_id}" \
  -H "Authorization: Bearer admin_token"

# Verify database connectivity
docker exec clickhouse-container clickhouse-client --query "SELECT 1"

# Check for missing columns/schema issues
docker logs api-container | grep "storage_health"
```

**Resolution:**
1. Verify tenant exists and has quota records
2. Check ClickHouse connectivity and permissions
3. Ensure database schema matches expected columns
4. Restart API service if schema was updated

### Problem: Incorrect Storage Usage Values

**Symptoms:**
- Storage GB showing as 0 when data exists
- Usage percentage incorrect
- Unit conversion errors

**Investigation:**
```sql
-- Check raw quota data
SELECT quota_type, quota_limit, current_usage 
FROM tenant_quotas_mt 
WHERE customer_id = 'tenant_id' AND quota_type = 'storage_gb'

-- Verify storage quota sync service
SELECT timestamp, delta_bytes, customer_id 
FROM ingestion_stats_mt 
WHERE customer_id = 'tenant_id' 
ORDER BY timestamp DESC LIMIT 10
```

**Common Issues:**
1. **Storage Quota Sync Not Running**: Service updates quotas every 1 minute
2. **Unit Mismatch**: Database stores bytes, API should display GB
3. **Missing Data**: No ingestion activity = no storage updates

**Resolution:**
1. Check storage quota sync service logs
2. Verify unit conversion logic (bytes → GB)
3. Trigger manual storage sync if needed
4. Ensure ingestion data exists in `ingestion_stats_mt`

### Problem: Performance Metrics Missing

**Symptoms:**
- `avg_ingestion_time_ms` showing as 0
- `monthly_ingestion_calls` incorrect
- Missing performance data

**Investigation:**
```sql
-- Check ingestion stats for current month
SELECT customer_id, count(*), avg(processing_time_ms)
FROM ingestion_stats_mt 
WHERE customer_id = 'tenant_id'
AND timestamp >= date_trunc('month', now())
GROUP BY customer_id
```

**Causes:**
1. **No Recent Ingestion**: No API calls this month
2. **Async Processing Delays**: Stats written in background
3. **Missing Ingestion Service**: Service not tracking performance

**Resolution:**
1. Verify recent ingestion API calls were made
2. Check ingestion service is running and healthy
3. Allow 1-2 minutes for async processing
4. Review ingestion service logs for errors

### Problem: Infrastructure Health Shows "Unknown"

**Symptoms:**
- Storage backend type shows "not_configured"
- System status shows "unknown"
- Missing infrastructure metrics

**Investigation:**
```sql
-- Check storage backends
SELECT backend_name, backend_type, health_status, is_default
FROM storage_backends_mt 
WHERE customer_id = 'system'
```

**Causes:**
1. **Default Backend Missing**: No system storage backend configured
2. **Health Check Failure**: Backend health check not working
3. **Configuration Error**: Invalid backend configuration

**Resolution:**
1. Create default storage backend configuration
2. Verify MinIO/S3 connectivity and credentials
3. Check storage service health monitoring
4. Update backend health status manually if needed

## Monitoring & Alerts

### Key Metrics to Monitor

#### **Storage Quota Alerts**
```yaml
# High usage warning
- alert: StorageQuotaWarning
  expr: storage_usage_percentage > 80
  summary: "Tenant {{tenant_id}} storage usage at {{usage_percentage}}%"

# Critical usage alert  
- alert: StorageQuotaCritical
  expr: storage_usage_percentage > 90
  summary: "Tenant {{tenant_id}} storage quota critical: {{usage_percentage}}%"
```

#### **Performance Alerts**
```yaml
# Slow ingestion performance
- alert: SlowIngestionPerformance
  expr: avg_ingestion_time_ms > 1000
  summary: "Tenant {{tenant_id}} ingestion latency high: {{avg_time}}ms"

# API health check failures
- alert: StorageHealthCheckFailure
  expr: storage_health_api_errors > 5
  summary: "Storage health API failing for tenant {{tenant_id}}"
```

### Dashboard Queries

#### **Storage Usage Over Time**
```sql
SELECT 
    toDate(updated_at) as date,
    customer_id,
    current_usage / (1024*1024*1024) as storage_gb
FROM tenant_quotas_mt 
WHERE quota_type = 'storage_gb'
AND updated_at >= now() - INTERVAL 30 DAY
ORDER BY date DESC
```

#### **Monthly Ingestion Trends**
```sql
SELECT 
    toYYYYMM(timestamp) as month,
    customer_id,
    sum(bytes_ingested) / (1024*1024*1024) as ingested_gb,
    avg(processing_time_ms) as avg_latency
FROM ingestion_stats_mt 
WHERE timestamp >= now() - INTERVAL 6 MONTH
GROUP BY month, customer_id
ORDER BY month DESC
```

## Integration Points

### Dependencies
- **Storage Quota Sync Service**: Updates tenant quotas every 1 minute
- **Ingestion Service**: Tracks performance metrics in real-time
- **Tenant Service**: Manages tenant quota configurations
- **Storage Service**: Provides infrastructure health data

### Related APIs
- `POST /v1/storage/quota/sync` - Manual quota sync trigger
- `GET /v1/storage/retention/{customer_id}` - Retention policy info
- `GET /v1/storage/operations` - Storage operations history
- `GET /v1/tenants/quotas` - Detailed quota management

### Data Flow
1. **Ingestion APIs** → Write to `ingestion_stats_mt`
2. **Storage Quota Sync** → Updates `tenant_quotas_mt` every minute
3. **Storage Health API** → Reads from all tables and converts units
4. **Response** → Provides GB-converted values for UI display

## Security Considerations

### Authentication & Authorization
- **Bearer Token**: Valid JWT token required
- **Tenant Isolation**: X-Customer-ID header enforced
- **Cross-Tenant Protection**: Users cannot access other tenant's data
- **Admin Access**: Platform admins can view any tenant's health

### Data Privacy
- **Tenant Isolation**: Strict customer_id filtering in all queries
- **No Sensitive Data**: Health endpoint doesn't expose log content
- **Aggregated Metrics**: Only statistical and quota information shared

## Performance Considerations

### Query Optimization
- **Indexed Queries**: All queries use customer_id (indexed)
- **Time-Range Filtering**: Monthly partitioning for historical data
- **Minimal Joins**: Direct table access for performance
- **Cached Infrastructure**: Infrastructure health cached for 5 minutes

### Response Times
- **Target**: < 500ms response time
- **Typical**: 100-300ms for most tenants
- **Factors**: Quota count, operation history size, infrastructure queries

### Scaling Considerations
- **Database Load**: Minimal impact due to indexed queries
- **Concurrent Requests**: Stateless design supports high concurrency
- **Data Volume**: Performance scales with tenant quota count

## Error Handling

### HTTP Status Codes
- **200 OK**: Success with health data
- **401 Unauthorized**: Missing or invalid auth token
- **403 Forbidden**: Invalid customer ID or access denied
- **500 Internal Server Error**: Database or service error

### Error Response Format
```json
{
  "detail": "Storage health check failed: specific error message",
  "error_type": "database_error|authentication_error|validation_error",
  "customer_id": "tenant_id",
  "timestamp": "2025-10-10T12:32:20.998504+00:00"
}
```

### Common Error Messages
- `"Customer ID is required"` - Missing X-Customer-ID header
- `"Query failed: Missing columns"` - Database schema mismatch
- `"Storage health check failed"` - General service error

## Best Practices

### API Usage
1. **Cache Results**: Health data can be cached for 1-5 minutes
2. **Error Handling**: Implement retry logic for 500 errors
3. **Rate Limiting**: Avoid excessive polling, use reasonable intervals
4. **Monitoring**: Track API response times and error rates

### Data Interpretation
1. **Unit Awareness**: Remember database stores bytes, API shows GB
2. **Time Scope**: Most metrics are current-month focused
3. **Status Logic**: Understand healthy/warning/critical thresholds
4. **Growth Trends**: Compare month-over-month for capacity planning

### Development
1. **Test Coverage**: Test with various quota states and data volumes
2. **Schema Changes**: Update conversion logic when database schema changes
3. **Error Scenarios**: Test with missing quotas, invalid tenant IDs
4. **Performance**: Monitor query performance with large datasets

---

**Last Updated**: October 2025  
**Version**: 1.0  
**Maintained By**: Logforge Platform Team  
**Related Documentation**: Storage Quota Sync Service, Ingestion Stats Runbook