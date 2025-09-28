# Storage Router API Documentation

## Overview

The Storage Router provides comprehensive data lifecycle management with TTL policies, storage backend configuration, quota management, and multi-tier storage operations. This router enables enterprise-grade storage operations with automated data archival, compression, and retention policy enforcement.

## Architecture

```
Request → Storage Router → Storage Service → Storage DAO → ClickHouse
                       ↓
                TTL Manager → Multi-Tier Storage (Hot/Cold/Archive)
```

**Core Components:**
- **Router**: `/apps/api/routers/storage.py` - FastAPI endpoints for storage management
- **Service**: `/apps/api/services/storage_service.py` - Business logic for storage operations
- **DAO**: `/apps/api/dao/storage_dao.py` - Database operations for storage data
- **TTL Manager**: Background service for automated data lifecycle management
- **Database**: Multi-tenant ClickHouse tables for storage metadata and configuration

## Multi-Tier Storage Architecture

### Storage Tiers
- **Hot Storage**: Recent data in ClickHouse for fast queries (default: 30 days)
- **Cold Storage**: Older data compressed in object storage (default: 90 days)
- **Archive Storage**: Long-term retention with maximum compression (default: 365+ days)

### Supported Backends
- **AWS S3**: Production-grade object storage
- **Google Cloud Storage**: Enterprise cloud storage
- **Azure Blob Storage**: Microsoft cloud storage
- **MinIO**: Self-hosted S3-compatible storage
- **Local Storage**: Development and on-premises deployments

## API Endpoints

### Retention Policy Management

#### 1. Create Retention Policy
**Endpoint**: `POST /v1/storage/retention/{customer_id}`

Create a new data retention policy with TTL configuration.

**Headers:**
- `Authorization`: Bearer token (via MiddlewareTenant)

**Path Parameters:**
- `customer_id`: Target customer identifier

**Request Body:**
```json
{
  "hot_retention_days": 30,
  "cold_retention_days": 90,
  "archive_retention_days": 365,
  "compression_enabled": true,
  "auto_deletion_enabled": false
}
```

**Response:**
```json
{
  "status": "created",
  "customer_id": "customer_123",
  "policy": {
    "policy_id": "policy_456",
    "status": "created",
    "message": "Retention policy created successfully",
    "customer_id": "customer_123"
  },
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Access Control:**
- Customers can only create policies for their own tenant
- Cross-tenant access returns 403 Forbidden

#### 2. Get Retention Policy
**Endpoint**: `GET /v1/storage/retention/{customer_id}`

Retrieve current retention policy for customer.

**Response:**
```json
{
  "customer_id": "customer_123",
  "retention_policy": {
    "id": "policy_456",
    "policy_name": "default",
    "hot_retention_days": 30,
    "cold_retention_days": 90,
    "archive_retention_days": 365,
    "compression_enabled": true,
    "auto_deletion_enabled": false,
    "storage_backend": "s3",
    "customer_id": "customer_123",
    "created_by": "system",
    "created_at": "2024-01-10T09:00:00Z",
    "updated_at": "2024-01-10T09:00:00Z",
    "status": "active"
  },
  "retrieved_at": "2024-01-15T10:30:00Z"
}
```

**Default Policy Response (if none exists):**
```json
{
  "customer_id": "customer_123",
  "retention_policy": {
    "policy_name": "default",
    "hot_retention_days": 30,
    "cold_retention_days": 90,
    "archive_retention_days": 365,
    "compression_enabled": true,
    "auto_deletion_enabled": false,
    "storage_backend": "s3",
    "customer_id": "customer_123"
  },
  "retrieved_at": "2024-01-15T10:30:00Z"
}
```

#### 3. Update Retention Policy
**Endpoint**: `PUT /v1/storage/retention/{customer_id}`

Update existing retention policy with validation.

**Request Body:**
```json
{
  "hot_retention_days": 45,
  "cold_retention_days": 120,
  "archive_retention_days": 730,
  "compression_enabled": true,
  "auto_deletion_enabled": true
}
```

**Response:**
```json
{
  "status": "updated",
  "customer_id": "customer_123",
  "policy": {
    "status": "updated",
    "policy_name": "default",
    "message": "Retention policy updated successfully",
    "customer_id": "customer_123"
  },
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Validation Rules:**
- `hot_retention_days` > 0
- `cold_retention_days` >= `hot_retention_days`
- `archive_retention_days` >= `cold_retention_days`

### Storage Operations

#### 4. Trigger Manual Cleanup
**Endpoint**: `POST /v1/storage/cleanup`

Manually trigger storage cleanup based on TTL policies.

**Request Body (optional):**
```json
{
  "policy_name": "default"
}
```

**Response:**
```json
{
  "status": "completed",
  "cleanup_stats": {
    "status": "triggered",
    "operation_id": "op_789",
    "cleanup_result": {
      "records_processed": 15420,
      "data_size_gb": 2.3,
      "hot_storage_cleaned": 1.2,
      "cold_storage_cleaned": 0.8,
      "archive_storage_cleaned": 0.3
    },
    "customer_id": "customer_123",
    "triggered_at": "2024-01-15T10:30:00Z"
  },
  "triggered_at": "2024-01-15T10:30:00Z"
}
```

**Integration with TTL Manager:**
```python
# TTL Manager integration for real-time cleanup
if self.ttl_manager:
    cleanup_result = await self.ttl_manager.cleanup_expired_data()
    # Update operation record with results
    await self.storage_dao.update_storage_operation(operation_id, customer_id, {
        'operation_status': 'completed',
        'completed_at': datetime.now(timezone.utc),
        'records_processed': cleanup_result.get('records_processed', 0),
        'data_size_gb': cleanup_result.get('data_size_gb', 0)
    })
```

#### 5. Archive Old Data
**Endpoint**: `POST /v1/storage/archive/{customer_id}`

Trigger data archival to cold storage based on retention policies.

**Response:**
```json
{
  "status": "archival_started",
  "customer_id": "customer_123",
  "result": {
    "status": "triggered",
    "operation_id": "op_890",
    "archive_result": {
      "records_processed": 8750,
      "data_size_gb": 5.2,
      "compression_ratio": 3.4,
      "storage_savings_gb": 12.6
    },
    "customer_id": "customer_123",
    "triggered_at": "2024-01-15T10:30:00Z"
  },
  "started_at": "2024-01-15T10:30:00Z"
}
```

**Storage Backend Integration:**
- Uses default SaaS storage backend (shared across tenants)
- Path-based tenant isolation: `/customer_123/archive/2024/01/15/`
- Automatic backend creation if not configured

### Storage Health & Monitoring

#### 6. Get Infrastructure Health
**Endpoint**: `GET /v1/storage/health/infrastructure`

Get system-wide storage infrastructure health (Admin access).

**Response:**
```json
{
  "infrastructure_health": {
    "storage_backend": {
      "type": "minio",
      "status": "healthy",
      "endpoint": "localhost:9003",
      "bucket": "logforge-saas-logs"
    },
    "capacity": {
      "total_capacity_gb": 10000,
      "used_capacity_gb": 2500,
      "available_capacity_gb": 7500,
      "usage_percentage": 25.0,
      "breakdown": {
        "hot_storage_gb": 800,
        "cold_storage_gb": 1200,
        "archive_storage_gb": 500
      }
    },
    "performance": {
      "daily_operations": 1000,
      "avg_operation_time_ms": 45.2,
      "read_iops": 1200,
      "write_iops": 800,
      "throughput_mbps": 850
    },
    "system_status": "healthy",
    "last_backup": "2024-01-15T04:30:00Z",
    "uptime_hours": 720,
    "tenant_count": 15
  },
  "access_level": "admin",
  "checked_at": "2024-01-15T10:30:00Z"
}
```

**System Health Metrics:**
- **Real Database Data**: Aggregated from all customer quotas
- **Performance Metrics**: Calculated from recent operations (24h window)
- **Storage Distribution**: Actual hot/cold/archive usage across all tenants
- **Health Status**: "healthy" if usage < 90% and backend status is healthy

#### 7. Get Customer Storage Health
**Endpoint**: `GET /v1/storage/health`

Get customer-specific storage health and usage.

**Response:**
```json
{
  "overall_status": "healthy",
  "customer_id": "customer_123",
  "infrastructure": {
    "storage_backend": {
      "type": "minio",
      "status": "healthy"
    },
    "system_status": "healthy"
  },
  "customer_data": {
    "status": "healthy",
    "quotas": [
      {
        "id": "quota_456",
        "quota_type": "hot_storage",
        "quota_limit_gb": 100,
        "current_usage_gb": 25.3,
        "usage_percentage": 25.3,
        "warning_threshold": 80,
        "critical_threshold": 90,
        "status": "healthy"
      },
      {
        "id": "quota_789",
        "quota_type": "cold_storage",
        "quota_limit_gb": 500,
        "current_usage_gb": 78.9,
        "usage_percentage": 15.8,
        "warning_threshold": 80,
        "critical_threshold": 90,
        "status": "healthy"
      }
    ],
    "usage_stats": {
      "total_logs": 5000,
      "customer_storage_gb": 104.2,
      "hot_storage_gb": 25.3,
      "cold_storage_gb": 78.9,
      "archive_storage_gb": 0.0
    },
    "recent_operations": [
      {
        "id": "op_001",
        "operation_type": "cleanup",
        "operation_status": "completed",
        "started_at": "2024-01-15T09:00:00Z",
        "completed_at": "2024-01-15T09:02:30Z",
        "records_processed": 1500,
        "data_size_gb": 0.8
      }
    ]
  },
  "checked_at": "2024-01-15T10:30:00Z"
}
```

**Health Status Calculation:**
- **Healthy**: All quotas < 80% usage
- **Warning**: Any quota 80-90% usage
- **Critical**: Any quota > 90% usage

#### 8. Get Specific Customer Health
**Endpoint**: `GET /v1/storage/health/{target_customer_id}`

Get storage health for specific customer (Admin access or own data only).

**Access Control:**
- Customers can only view their own health data
- Admin access (future): Cross-tenant health monitoring
- Returns 403 for unauthorized cross-tenant access

### Storage Backend Configuration

#### 9. Default Storage Backend Management

The storage router automatically manages a shared SaaS storage backend for multi-tenant deployments:

**Automatic Backend Creation:**
```json
{
  "customer_id": "system",
  "backend_name": "logforge-saas-storage",
  "backend_type": "minio",
  "connection_config": {
    "endpoint": "localhost:9003",
    "access_key": "minio",
    "secret_key": "minio123",
    "bucket": "logforge-saas-logs",
    "region": "us-east-1",
    "secure": false,
    "path_style": true,
    "tenant_isolation": "path_based"
  },
  "is_default": true,
  "is_enabled": true,
  "health_status": "healthy"
}
```

**Tenant Isolation Strategy:**
- **Path-Based Isolation**: Each tenant gets isolated paths within shared bucket
- **Bucket Structure**: `/logforge-saas-logs/customer_123/hot/`, `/customer_123/cold/`, `/customer_123/archive/`
- **Security**: MinIO credentials managed at system level, not exposed to tenants

## Data Models

### Retention Policy Model
```python
class RetentionPolicyRequest(BaseModel):
    hot_retention_days: int
    cold_retention_days: int
    archive_retention_days: int
    compression_enabled: bool = True
    auto_deletion_enabled: bool = False
```

### Storage Health Model
```python
class StorageHealthResponse(BaseModel):
    overall_status: str  # healthy, warning, critical
    customer_id: str
    infrastructure: Dict[str, Any]
    customer_data: Dict[str, Any]
    checked_at: str
```

### Storage Operation Model
```python
class StorageOperation(BaseModel):
    id: str
    customer_id: str
    operation_type: str  # cleanup, archive, compression
    operation_status: str  # pending, running, completed, failed
    started_at: datetime
    completed_at: Optional[datetime]
    records_processed: int
    data_size_gb: float
    operation_metadata: Dict[str, Any]
```

## Authentication & Headers

All storage endpoints use MiddlewareTenant for authentication:

```http
Authorization: Bearer <jwt_token>
X-Customer-ID: <customer_id> (automatically extracted)
Content-Type: application/json
```

## Error Handling

**Common HTTP Status Codes:**
- `200`: Success
- `201`: Created (retention policy)
- `400`: Bad request (validation error)
- `401`: Unauthorized (invalid token)
- `403`: Forbidden (cross-tenant access denied)
- `404`: Resource not found
- `422`: Unprocessable entity (invalid retention values)
- `500`: Internal server error

**Error Response Format:**
```json
{
  "detail": "Cold retention must be >= hot retention",
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_123"
}
```

## Code Integration

### Service Layer Integration

```python
from services.storage_service import StorageService

# Initialize service
storage_service = StorageService()

# Set TTL manager for real operations
storage_service.set_ttl_manager(ttl_manager)

# Create retention policy
policy_data = {
    "customer_id": "customer_123",
    "policy_name": "default",
    "hot_retention_days": 30,
    "cold_retention_days": 90,
    "archive_retention_days": 365,
    "compression_enabled": True,
    "auto_deletion_enabled": False
}
result = await storage_service.create_retention_policy(policy_data)

# Trigger cleanup operation
cleanup_result = await storage_service.trigger_cleanup_operation(customer_id)

# Get storage health
health_info = await storage_service.get_storage_health(customer_id)
```

### TTL Manager Integration

```python
# TTL Manager setup in main application
from ttl_manager import TTLManager
from routers.storage import setup_dependencies

# Initialize TTL manager
ttl_manager = TTLManager()

# Inject TTL manager into storage router
setup_dependencies(ttl_manager)

# TTL operations integration
async def cleanup_expired_data():
    return await ttl_manager.cleanup_expired_data()

async def archive_data(customer_id):
    return await ttl_manager.archive_data(customer_id)
```

### Database Schema

**Key Storage Tables:**
- `retention_policies_mt`: TTL and retention configurations
- `storage_backends_mt`: Storage backend configurations  
- `storage_operations_mt`: Operation tracking and history
- `storage_quotas_mt`: Storage quotas and usage tracking
- `data_archives_mt`: Archived data location tracking

**Retention Policies Schema:**
```sql
CREATE TABLE retention_policies_mt (
    id String,
    customer_id String,
    policy_name String,
    hot_retention_days UInt32,
    cold_retention_days UInt32,
    archive_retention_days UInt32,
    compression_enabled Boolean,
    auto_deletion_enabled Boolean,
    storage_backend String,
    created_by String,
    created_at DateTime64(9),
    updated_at DateTime64(9),
    status String
) ENGINE = MergeTree()
PARTITION BY customer_id
ORDER BY (customer_id, policy_name)
```

**Storage Operations Schema:**
```sql
CREATE TABLE storage_operations_mt (
    id String,
    customer_id String,
    operation_type String,
    operation_status String,
    policy_id Nullable(String),
    backend_id Nullable(String),
    started_at DateTime64(9),
    completed_at Nullable(DateTime64(9)),
    duration_seconds Nullable(UInt32),
    records_processed UInt64,
    data_size_gb Float64,
    error_message Nullable(String),
    operation_metadata String,  -- JSON
    triggered_by String,
    status String
) ENGINE = MergeTree()
PARTITION BY customer_id
ORDER BY (customer_id, started_at)
```

## Performance Characteristics

- **Policy Creation**: < 200ms for validation and database insertion
- **Health Check**: < 500ms for customer-specific health (includes quota aggregation)
- **Infrastructure Health**: < 2s for system-wide aggregation across all tenants
- **Cleanup Operations**: 5-30s depending on data volume (async execution)
- **Archive Operations**: 10-60s for typical customer data volume
- **Storage Metrics**: < 1s for customer-specific storage analytics

## Storage Lifecycle Management

### Automated Data Movement
1. **Hot → Cold**: Data older than `hot_retention_days` moves to cold storage
2. **Cold → Archive**: Data older than `cold_retention_days` moves to archive storage
3. **Archive Cleanup**: Data older than `archive_retention_days` deleted (if `auto_deletion_enabled`)

### Compression Strategy
- **Hot Storage**: No compression (performance priority)
- **Cold Storage**: Standard compression (2-3x ratio)
- **Archive Storage**: Maximum compression (4-6x ratio)

### Multi-Cloud Support
```python
# S3 Configuration
s3_config = {
    "backend_type": "s3",
    "connection_config": {
        "endpoint": "s3.amazonaws.com",
        "access_key": "AWS_ACCESS_KEY",
        "secret_key": "AWS_SECRET_KEY",
        "bucket": "logforge-customer-data",
        "region": "us-west-2",
        "secure": True
    }
}

# Google Cloud Storage Configuration
gcs_config = {
    "backend_type": "gcs",
    "connection_config": {
        "project_id": "logforge-project",
        "bucket": "logforge-gcs-storage",
        "credentials_path": "/path/to/service-account.json"
    }
}
```

## Quota Management

### Storage Quota Types
- **`hot_storage`**: Hot data storage limits
- **`cold_storage`**: Cold storage limits
- **`archive_storage`**: Archive storage limits
- **`total_storage`**: Combined storage limits

### Quota Monitoring
```python
# Create storage quota
quota_data = {
    "customer_id": "customer_123",
    "quota_type": "hot_storage",
    "quota_limit_gb": 100,
    "warning_threshold": 0.8,
    "critical_threshold": 0.9,
    "alerts_enabled": True
}
quota_id = await storage_service.create_storage_quota(quota_data)

# Update storage usage
usage_data = {
    "hot_storage": 45.3,
    "cold_storage": 128.7,
    "archive_storage": 89.2
}
await storage_service.update_storage_usage(customer_id, usage_data)
```

## Security Considerations

- **Multi-Tenant Isolation**: Complete data separation via `customer_id` and path-based storage isolation
- **Backend Security**: Storage credentials managed at system level, not exposed to tenants
- **Access Control**: Strict tenant isolation enforced by MiddlewareTenant
- **Data Encryption**: Support for encryption at rest and in transit
- **Audit Logging**: All storage operations tracked with timestamps and metadata
- **Retention Compliance**: Automated compliance with data retention regulations

## Best Practices

1. **Retention Planning**: Set appropriate retention periods based on compliance requirements
2. **Compression Strategy**: Enable compression for cold and archive tiers
3. **Quota Management**: Monitor storage usage and set appropriate quotas
4. **Regular Cleanup**: Schedule regular cleanup operations to manage costs
5. **Health Monitoring**: Monitor storage health and address warnings proactively
6. **Backend Redundancy**: Consider multi-cloud backup strategies for critical data
7. **Cost Optimization**: Use archive tiers for long-term retention to reduce costs

## Related Documentation

- [TTL Manager Integration Guide](../../../wiki/TTL-Manager-Integration.md)
- [Multi-Cloud Storage Configuration](../../../wiki/Multi-Cloud-Storage-Config.md)
- [Data Lifecycle Management](../../../wiki/Data-Lifecycle-Management.md)
- [Storage Cost Optimization](../../../wiki/Storage-Cost-Optimization.md)