# Storage Router Runbook

## Overview

The Storage Router (`/v1/storage/*`) provides comprehensive data lifecycle management, TTL policies, archive retrieval, and multi-cloud storage operations for the Logforge platform.

**Base URL**: `/v1/storage`  
**Authentication**: Bearer JWT + X-Customer-ID header  
**Documentation**: Covers 13 API endpoints across 5 functional categories

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [TTL & Retention Management](#ttl--retention-management)
3. [Data Operations](#data-operations)
4. [Health Monitoring](#health-monitoring)
5. [Quota Management](#quota-management)
6. [Archive Retrieval](#archive-retrieval)
7. [Troubleshooting](#troubleshooting)
8. [Emergency Procedures](#emergency-procedures)
9. [Configuration Management](#configuration-management)

---

## Quick Reference

### Endpoint Categories

| Category | Endpoints | Purpose |
|----------|-----------|---------|
| **TTL/Retention** | 3 endpoints | Policy management, lifecycle configuration |
| **Data Operations** | 2 endpoints | Manual cleanup, archival triggers |
| **Health Monitoring** | 3 endpoints | System health, customer metrics |
| **Quota Management** | 2 endpoints | Storage quota synchronization |
| **Archive Retrieval** | 4 endpoints | Archive browsing, download, query |

### Database Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `retention_policies_mt` | TTL policy storage | customer_id, policy_name, retention_days |
| `archive_metadata_mt` | Archive file metadata | archive_key, data_size_bytes, access_count |
| `archive_access_log_mt` | Access audit trail | access_type, bytes_transferred, accessed_at |
| `storage_operations_mt` | Operation tracking | operation_type, status, completed_at |
| `tenant_quotas_mt` | Storage quotas | quota_type, current_usage, quota_limit |

---

## TTL & Retention Management

### 1. Create Retention Policy

**Endpoint**: `POST /v1/storage/retention/{customer_id}`

**Purpose**: Establish data lifecycle rules with hot/cold/archive tiers

**Request Body**:
```json
{
  "hot_retention_days": 30,
  "cold_retention_days": 90,
  "archive_retention_days": 365,
  "compression_enabled": true,
  "auto_deletion_enabled": false
}
```

**Success Response**:
```json
{
  "status": "created",
  "customer_id": "tenant-123",
  "policy": {...},
  "created_at": "2025-10-11T17:30:00Z"
}
```

**Common Issues**:
- **403 Forbidden**: Cross-tenant access - customer_id in URL must match X-Customer-ID header
- **Validation errors**: Ensure retention_days increase: hot < cold < archive

### 2. Get Retention Policy

**Endpoint**: `GET /v1/storage/retention/{customer_id}`

**Purpose**: Retrieve current TTL configuration

**Response**:
```json
{
  "customer_id": "tenant-123",
  "retention_policy": {
    "policy_name": "default",
    "hot_retention_days": 30,
    "cold_retention_days": 90,
    "archive_retention_days": 365
  },
  "retrieved_at": "2025-10-11T17:30:00Z"
}
```

### 3. Update Retention Policy

**Endpoint**: `PUT /v1/storage/retention/{customer_id}`

**Purpose**: Modify existing lifecycle rules

**Request Body**: Same as create, only include fields to update

---

## Data Operations

### 1. Manual Cleanup

**Endpoint**: `POST /v1/storage/cleanup`

**Purpose**: Trigger TTL-based data deletion

**Request Body** (optional):
```json
{
  "policy_name": "custom-policy"
}
```

**Response**:
```json
{
  "status": "completed",
  "cleanup_stats": {
    "records_processed": 50000,
    "data_size_gb": 25.6,
    "deleted_files": 1250
  },
  "triggered_at": "2025-10-11T17:30:00Z"
}
```

**Use Cases**:
- Emergency storage cleanup
- Manual policy enforcement
- Pre-maintenance cleanup

### 2. Archive Old Data

**Endpoint**: `POST /v1/storage/archive/{customer_id}`

**Purpose**: Move cold data to archive storage

**Response**:
```json
{
  "status": "archival_started",
  "customer_id": "tenant-123",
  "result": {
    "estimated_data_gb": 150.2,
    "estimated_files": 5000
  },
  "started_at": "2025-10-11T17:30:00Z"
}
```

---

## Health Monitoring

### 1. Infrastructure Health (Admin Only)

**Endpoint**: `GET /v1/storage/health/infrastructure`

**Authentication**: Requires platform admin JWT token

**Purpose**: System-wide storage infrastructure monitoring

**Response**:
```json
{
  "infrastructure_health": {
    "storage_backend": {
      "type": "minio",
      "status": "healthy",
      "endpoint": "http://minio:9000",
      "bucket": "logforge"
    },
    "capacity": {
      "total_capacity_gb": 10000,
      "used_capacity_gb": 2500,
      "usage_percentage": 25.0
    },
    "performance": {
      "daily_operations": 1000,
      "avg_operation_time_ms": 45.2,
      "read_iops": 1200,
      "write_iops": 800
    }
  },
  "access_level": "platform_admin",
  "checked_at": "2025-10-11T17:30:00Z"
}
```

**Troubleshooting**:
- **403 User context not found**: Use admin login credentials (admin@mrlogsec.com)
- **403 Platform admin access required**: User lacks admin role in platform tenant

### 2. Customer Storage Health

**Endpoint**: `GET /v1/storage/health`

**Purpose**: Tenant-specific storage metrics

**Response**:
```json
{
  "overall_status": "healthy",
  "customer_id": "tenant-123",
  "customer_data": {
    "quotas": [...],
    "usage_stats": {
      "storage_gb": 45.6,
      "monthly_ingestion_gb": 12.3,
      "total_logs_current_month": 500000
    },
    "recent_operations": [...]
  },
  "checked_at": "2025-10-11T17:30:00Z"
}
```

### 3. Specific Customer Health (Admin)

**Endpoint**: `GET /v1/storage/health/{target_customer_id}`

**Purpose**: Cross-tenant health monitoring (admin access)

---

## Quota Management

### 1. Sync Customer Quota

**Endpoint**: `POST /v1/storage/quota/sync`

**Purpose**: Refresh storage usage calculations for authenticated tenant

**Response**:
```json
{
  "status": "completed",
  "customer_id": "tenant-123",
  "sync_result": {
    "updated_quotas": ["storage_gb", "monthly_ingestion"],
    "previous_usage_gb": 45.2,
    "current_usage_gb": 47.1
  },
  "triggered_at": "2025-10-11T17:30:00Z"
}
```

### 2. Sync All Quotas (Admin Only)

**Endpoint**: `POST /v1/storage/quota/sync/all`

**Authentication**: Requires platform admin JWT token

**Purpose**: System-wide quota recalculation

**Response**:
```json
{
  "status": "completed",
  "sync_result": {
    "tenants_processed": 247,
    "total_quotas_updated": 1235,
    "system_usage_gb": 2847.3
  },
  "triggered_by": "admin-user",
  "triggered_at": "2025-10-11T17:30:00Z"
}
```

---

## Archive Retrieval

### 1. List Customer Archives

**Endpoint**: `GET /v1/storage/archives/{customer_id}`

**Query Parameters**:
- `limit` (default: 50): Number of archives to return
- `offset` (default: 0): Pagination offset
- `start_date`: Filter by archive date (YYYY-MM-DD)
- `end_date`: Filter by archive date (YYYY-MM-DD)

**Response**:
```json
{
  "customer_id": "tenant-123",
  "archives": [
    {
      "id": "8de44692-63bc-4340-b310-9eb70deb2fdb",
      "archive_key": "archived_logs/tenant-123/2025/10/10/logs_batch_1760154276.parquet",
      "time_period": {
        "start": "2025-06-13T03:44:36",
        "end": "2025-10-10T03:44:36"
      },
      "records_count": 3,
      "data_size_bytes": 9554,
      "data_size_gb": 0.000009,
      "compression_type": "gzip",
      "encryption_enabled": false,
      "storage_backend": "minio",
      "bucket_name": "logforge",
      "access_stats": {
        "access_count": 0,
        "last_accessed_at": "2025-10-11T03:44:36Z"
      }
    }
  ],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total_count": 2
  },
  "retrieved_at": "2025-10-11T17:30:00Z"
}
```

### 2. Get Archive Metadata

**Endpoint**: `GET /v1/storage/archive/{archive_key}`

**URL Format**: Use the full `archive_key` from list API (not the `id`)
```
/v1/storage/archive/archived_logs/tenant-123/2025/10/10/logs_batch_1760154276.parquet
```

**Response**:
```json
{
  "archive_metadata": {
    "id": "8de44692-63bc-4340-b310-9eb70deb2fdb",
    "archive_key": "archived_logs/tenant-123/2025/10/10/logs_batch_1760154276.parquet",
    "customer_id": "tenant-123",
    "time_period": {
      "start": "2025-06-13T03:44:36",
      "end": "2025-10-10T03:44:36"
    },
    "content_info": {
      "records_count": 3,
      "data_size_bytes": 9554,
      "data_size_gb": 0.000009,
      "compression_type": "gzip",
      "encryption_enabled": false
    },
    "storage_info": {
      "archive_date": "2025-10-11T03:44:36Z",
      "storage_backend": "minio",
      "bucket_name": "logforge",
      "checksum": "ac4adb81a69ef8c588b9c6727406e3825809806af8dace861d60f5c2b15cb52c"
    },
    "access_methods": {
      "download_url": "/v1/storage/archive/{archive_key}/download",
      "query_api": "/v1/storage/query-archive"
    }
  },
  "retrieved_at": "2025-10-11T17:30:00Z"
}
```

### 3. Download Archive

**Endpoint**: `POST /v1/storage/archive/{archive_key}/download`

**Purpose**: Generate presigned download URL with access logging

**Response**:
```json
{
  "archive_key": "archived_logs/tenant-123/2025/10/10/logs_batch_1760154276.parquet",
  "download_url": "http://minio:9000/logforge/archived_logs/tenant-123/2025/10/10/logs_batch_1760154276.parquet?AWSAccessKeyId=minio&Signature=df5lQQ%2B81HA%2BdO5oY%2BoIyalz%2BZk%3D&Expires=1760207254",
  "expires_in_seconds": 3600,
  "archive_metadata": {
    "records_count": 3,
    "data_size_gb": 0.000009,
    "time_period": {
      "start": "2025-06-13T03:44:36",
      "end": "2025-10-10T03:44:36"
    }
  },
  "access_logged": true,
  "generated_at": "2025-10-11T17:30:00Z"
}
```

**Access Logging**: Downloads are automatically logged in `archive_access_log_mt` for audit compliance

### 4. Query Archive Data

**Endpoint**: `POST /v1/storage/query-archive`

**Purpose**: Query archived data with filters (experimental feature)

**Request Body**:
```json
{
  "archive_keys": [
    "archived_logs/tenant-123/2025/10/10/logs_batch_1760154276.parquet"
  ],
  "filters": {
    "timestamp": {"gte": "2025-10-01T00:00:00Z"},
    "level": "error"
  },
  "limit": 1000
}
```

**Response**:
```json
{
  "customer_id": "tenant-123",
  "query_filters": {...},
  "results": {
    "status": "experimental_feature",
    "message": "Archive querying is an experimental feature. Currently returns metadata only.",
    "alternative_access": {
      "download_instructions": "Use /v1/storage/archive/{archive_key}/download to get full archive files"
    }
  },
  "total_archives_searched": 1,
  "queried_at": "2025-10-11T17:30:00Z"
}
```

---

## Troubleshooting

### Common Error Codes

#### 403 Forbidden Errors

**Scenario 1**: Cross-tenant access
```json
{"detail": "Access denied"}
```
**Solution**: Ensure `customer_id` in URL matches `X-Customer-ID` header

**Scenario 2**: Admin endpoint access
```json
{"detail": "User context not found"}
```
**Solution**: Use admin login credentials and admin JWT token

**Scenario 3**: Platform admin required
```json
{"detail": "Platform admin access required for infrastructure health check"}
```
**Solution**: Verify user has admin role in platform tenant

#### 404 Not Found Errors

**Scenario**: Archive not found
```json
{"detail": "Archive not found"}
```
**Solutions**:
1. Use `archive_key` from list API, not the `id` field
2. Verify archive belongs to requesting customer
3. Check archive exists in `archive_metadata_mt` table

#### 500 Database Errors

**Scenario 1**: Database method not found
```json
{"detail": "Failed to generate download: 'DatabaseLayer' object has no attribute 'command'"}
```
**Solution**: Fixed in latest version - database layer uses proper methods

**Scenario 2**: Column mismatch
```json
{"detail": "Failed to generate download: Insert failed: Insert data column count does not match column names"}
```
**Solution**: Fixed in latest version - proper column mapping for `archive_access_log_mt`

### Performance Issues

#### Slow Archive Listing
- **Symptom**: `GET /v1/storage/archives/{customer_id}` takes >5 seconds
- **Diagnosis**: Check ClickHouse query performance
- **Solution**: Use date filters to reduce result set

#### Large Download URLs
- **Symptom**: Download URL generation timeout
- **Diagnosis**: Check storage backend connectivity
- **Solution**: Verify storage configuration and credentials

---

## Emergency Procedures

### Storage Quota Exceeded

1. **Immediate Actions**:
   ```bash
   # Check quota status
   GET /v1/storage/health
   
   # Trigger emergency cleanup
   POST /v1/storage/cleanup
   ```

2. **Investigate**:
   - Review retention policies
   - Check for data ingestion spikes
   - Verify TTL operations are running

3. **Resolve**:
   - Adjust retention policies if needed
   - Archive old data manually
   - Increase quota limits (admin only)

### Archive Access Failures

1. **Check Storage Backend**:
   ```bash
   GET /v1/storage/health/infrastructure
   ```

2. **Verify Archive Exists**:
   ```bash
   GET /v1/storage/archives/{customer_id}
   ```

3. **Test Download Generation**:
   - Check storage credentials
   - Verify bucket permissions
   - Test presigned URL generation

### Database Connection Issues

1. **Symptoms**:
   - All storage APIs returning 500 errors
   - "Database connection failed" messages

2. **Diagnosis**:
   ```bash
   # Check ClickHouse connectivity
   docker exec logforge-clickhouse clickhouse-client --query "SELECT 1"
   
   # Check database layer permissions
   grep "StorageDAO" apps/api/database_layer.py
   ```

3. **Resolution**:
   - Restart ClickHouse container if needed
   - Verify database layer service keys
   - Check table permissions

---

## Configuration Management

### Environment Variables

#### Storage Backend Configuration
```bash
# MinIO (Development)
MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=minio
MINIO_SECRET_KEY=minio123

# Production S3
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1

# System Capacity
SYSTEM_TOTAL_CAPACITY_GB=10000
```

#### Service Authentication
```bash
STORAGE_SERVICE_KEY=storage-service-key-dev
STORAGE_QUOTA_SYNC_KEY=storage-quota-sync-service-key
```

### Database Permissions

The `StorageDAO` requires access to these tables:
```python
'StorageDAO': [
    'retention_policies_mt', 'storage_backends_mt', 'storage_operations_mt', 
    'storage_quotas_mt', 'data_archives_mt', 'archive_metadata_mt', 
    'archive_access_log_mt', 'logs_raw_mt', 'logs_normalized_mt'
]
```

### Storage Config Manager

Configuration hierarchy (highest to lowest priority):
1. Environment variables
2. YAML configuration file (`config/storage-config.yaml`)
3. Default development settings

**Example YAML Configuration**:
```yaml
storage:
  deployment:
    type: shared
    region: us-east-1
  cold:
    backend: s3
    backends:
      s3:
        shared:
          enabled: true
          bucket_prefix: logforge-prod
          region: us-east-1
          access_key: ${AWS_ACCESS_KEY_ID}
          secret_key: ${AWS_SECRET_ACCESS_KEY}
```

---

## Monitoring & Metrics

### Key Performance Indicators

1. **Storage Usage**:
   - Total storage utilization percentage
   - Growth rate (GB/month)
   - Archive efficiency (compression ratio)

2. **Operation Performance**:
   - Average cleanup time
   - Archive operation success rate
   - Download URL generation latency

3. **Access Patterns**:
   - Archive download frequency
   - Query request volume
   - Failed access attempts

### Health Check Automation

**Infrastructure Monitoring**:
```bash
# Daily health check
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "X-Customer-ID: platform" \
     http://localhost:7080/v1/storage/health/infrastructure
```

**Customer Quota Monitoring**:
```bash
# Check all customer quotas
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "X-Customer-ID: platform" \
     -X POST http://localhost:7080/v1/storage/quota/sync/all
```

---

## Security Considerations

### Access Control

1. **Tenant Isolation**: All endpoints enforce customer_id validation
2. **Admin Operations**: Infrastructure and system-wide operations require platform admin role
3. **Archive Access**: Archive keys must belong to requesting customer
4. **Audit Logging**: All archive access logged with user context

### Data Protection

1. **Encryption**: Archive data can be encrypted at rest
2. **Access Logging**: Complete audit trail of data access
3. **Presigned URLs**: Temporary download links with expiration
4. **Cross-Tenant Prevention**: Multiple validation layers prevent data leakage

### Compliance Features

1. **Data Retention**: Configurable retention policies for compliance requirements
2. **Access Audit**: Complete archive access history
3. **Secure Deletion**: Automated data deletion based on policies
4. **Export Control**: Controlled data export through download APIs

---

## Version Information

**Last Updated**: October 2025  
**API Version**: v1  
**Compatible Versions**: Logforge M1-M7  
**Database Schema**: Multi-tenant ClickHouse  

**Change Log**:
- Fixed database layer method calls (execute_query, execute_insert, execute_update)
- Added proper column mapping for archive_access_log_mt
- Removed hardcoded URLs, now uses environment-based configuration
- Added platform admin authentication for infrastructure endpoints
- Implemented comprehensive error handling and validation