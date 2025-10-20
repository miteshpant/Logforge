# Cold Storage Technical Implementation Guide

## Quick Reference

This document provides technical implementation details for developers working on the cold storage and archival system.

## Current Architecture Issues

### 🚨 Critical Problems to Fix

1. **TTL Policies Not Applied**
   ```sql
   -- Current (BROKEN):
   TTL toDateTime(ts) + toIntervalDay(7)  -- Hardcoded!
   
   -- Should be (DYNAMIC):
   TTL toDateTime(ts) + toIntervalDay({tenant_policy.hot_retention_days})
   ```

2. **No Cold Storage Queries**
   - Data archived to MinIO but not queryable
   - Need external table integration or federated queries

3. **Tenant Isolation Gaps**
   - Cold storage paths not tenant-specific
   - No access control validation for archived data

## Core Components to Implement

### 1. Dynamic TTL Policy Engine

**Location**: `/apps/api/engines/ttl_policy_engine.py`

```python
class TTLPolicyEngine:
    """Manages dynamic TTL application for multi-tenant tables"""
    
    def __init__(self, clickhouse_client):
        self.ch_client = clickhouse_client
        self.applied_policies = {}  # Cache to avoid duplicate applications
    
    async def apply_retention_policy(self, customer_id: str, policy: Dict[str, Any]):
        """Apply retention policy to tenant's data"""
        try:
            hot_days = policy['hot_retention_days']
            archive_days = policy['archive_retention_days']
            
            # Apply TTL to move data to cold storage after hot period
            await self._apply_hot_to_cold_ttl(hot_days)
            
            # Apply TTL to delete data after archive period
            await self._apply_deletion_ttl(customer_id, archive_days)
            
            # Cache applied policy
            self.applied_policies[customer_id] = policy
            
            logger.info("TTL policy applied", customer_id=customer_id, 
                       hot_days=hot_days, archive_days=archive_days)
                       
        except Exception as e:
            logger.error("Failed to apply TTL policy", error=str(e), customer_id=customer_id)
            raise
    
    async def _apply_hot_to_cold_ttl(self, hot_days: int):
        """Apply TTL to transition data from hot to cold storage"""
        
        # For multi-tenant tables, we can't use per-tenant TTL directly
        # Instead, we'll use the archival service triggered by TTL events
        ttl_sql = f"""
        ALTER TABLE logs_raw_mt MODIFY TTL 
            ts + toIntervalDay({hot_days}) 
            TO VOLUME 'default'  -- Keep in ClickHouse but mark for archival
        """
        
        await self.ch_client.command(ttl_sql)
        
        # Also update normalized table
        ttl_normalized_sql = f"""
        ALTER TABLE logs_normalized_mt MODIFY TTL 
            ts + toIntervalDay({hot_days}) 
            TO VOLUME 'default'
        """
        
        await self.ch_client.command(ttl_normalized_sql)
    
    async def _apply_deletion_ttl(self, customer_id: str, archive_days: int):
        """Apply TTL for final deletion (per tenant)"""
        
        # Use DELETE TTL with WHERE clause for tenant isolation
        delete_ttl_sql = f"""
        ALTER TABLE logs_raw_mt MODIFY TTL 
            ts + toIntervalDay({archive_days}) DELETE 
            WHERE customer_id = '{customer_id}'
        """
        
        await self.ch_client.command(delete_ttl_sql)
        
        # Same for normalized table
        delete_normalized_sql = f"""
        ALTER TABLE logs_normalized_mt MODIFY TTL 
            ts + toIntervalDay({archive_days}) DELETE 
            WHERE customer_id = '{customer_id}'
        """
        
        await self.ch_client.command(delete_normalized_sql)
```

### 2. Cold Storage Service

**Location**: `/apps/api/services/cold_storage_service.py`

```python
class ColdStorageService:
    """Handles cold storage operations with tenant isolation"""
    
    def __init__(self, storage_manager, clickhouse_client):
        self.storage_manager = storage_manager
        self.ch_client = clickhouse_client
        self.archive_metadata_dao = ArchiveMetadataDAO()
    
    async def archive_tenant_partition(self, customer_id: str, partition_date: str):
        """Archive a specific date partition for a tenant"""
        try:
            # 1. Query data to archive
            data = await self._query_partition_data(customer_id, partition_date)
            
            if not data:
                logger.info("No data to archive", customer_id=customer_id, partition=partition_date)
                return
            
            # 2. Create tenant-specific archive path
            archive_path = self._get_tenant_archive_path(customer_id, partition_date)
            
            # 3. Convert to Parquet and upload
            await self._upload_parquet_data(data, archive_path, customer_id)
            
            # 4. Create metadata record
            await self._create_archive_metadata(customer_id, archive_path, data)
            
            # 5. Verify upload success
            if await self._verify_archive_integrity(archive_path):
                # 6. Delete from hot storage
                await self._delete_hot_partition(customer_id, partition_date)
                logger.info("Partition archived successfully", 
                          customer_id=customer_id, partition=partition_date)
            else:
                raise Exception("Archive integrity verification failed")
                
        except Exception as e:
            logger.error("Partition archival failed", error=str(e), 
                        customer_id=customer_id, partition=partition_date)
            raise
    
    def _get_tenant_archive_path(self, customer_id: str, partition_date: str) -> str:
        """Generate tenant-isolated archive path"""
        date_obj = datetime.strptime(partition_date, '%Y-%m-%d')
        
        return (f"tenants/{customer_id}/cold/"
                f"year={date_obj.year}/"
                f"month={date_obj.month:02d}/"
                f"day={date_obj.day:02d}/"
                f"logs_{partition_date}.parquet")
    
    async def _query_partition_data(self, customer_id: str, partition_date: str) -> List[Dict]:
        """Query all data for a tenant's partition"""
        
        query = f"""
        SELECT 
            ts, customer_id, host, service, level, msg, 
            trace_id, span_id, attrs, status, src_ip, user_id
        FROM logs_raw_mt 
        WHERE customer_id = '{customer_id}'
        AND toDate(ts) = '{partition_date}'
        ORDER BY ts
        """
        
        result = await self.ch_client.query(query)
        return [dict(row) for row in result]
    
    async def _upload_parquet_data(self, data: List[Dict], archive_path: str, customer_id: str):
        """Upload data as Parquet file to object storage"""
        import pandas as pd
        import io
        
        # Convert to pandas DataFrame
        df = pd.DataFrame(data)
        
        # Write to Parquet in memory
        parquet_buffer = io.BytesIO()
        df.to_parquet(parquet_buffer, engine='pyarrow', compression='snappy')
        parquet_buffer.seek(0)
        
        # Get storage client for tenant
        storage_client = self.storage_manager.get_storage_client(customer_id)
        bucket = self.storage_manager.get_storage_bucket(customer_id)
        
        # Upload to object storage
        if hasattr(storage_client, 'put_object'):  # S3/MinIO
            storage_client.put_object(
                Bucket=bucket,
                Key=archive_path,
                Body=parquet_buffer.getvalue(),
                ContentType='application/octet-stream'
            )
        else:
            raise NotImplementedError(f"Storage client type not supported")
    
    async def _create_archive_metadata(self, customer_id: str, archive_path: str, data: List[Dict]):
        """Create metadata record for archived data"""
        
        metadata = {
            'archive_key': archive_path,
            'customer_id': customer_id,
            'record_count': len(data),
            'data_size_bytes': len(str(data).encode('utf-8')),
            'compression_type': 'snappy',
            'created_at': datetime.utcnow(),
            'status': 'completed'
        }
        
        await self.archive_metadata_dao.create_archive_metadata(metadata)
```

### 3. Federated Query Engine

**Location**: `/apps/api/engines/federated_query_engine.py`

```python
class FederatedQueryEngine:
    """Executes queries across hot and cold storage"""
    
    def __init__(self, clickhouse_client, cold_storage_service):
        self.ch_client = clickhouse_client
        self.cold_storage = cold_storage_service
    
    async def execute_query(self, query_request: QueryRequest, customer_id: str) -> QueryResult:
        """Execute query across all available storage tiers"""
        
        # 1. Analyze query to determine required storage tiers
        tiers_needed = self._analyze_required_tiers(query_request, customer_id)
        
        # 2. Execute queries in parallel
        tasks = []
        
        if 'hot' in tiers_needed:
            tasks.append(self._query_hot_storage(query_request, customer_id))
        
        if 'cold' in tiers_needed:
            tasks.append(self._query_cold_storage(query_request, customer_id))
        
        # 3. Execute all queries
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 4. Merge results
        merged_results = self._merge_results(results)
        
        return merged_results
    
    def _analyze_required_tiers(self, query_request: QueryRequest, customer_id: str) -> List[str]:
        """Determine which storage tiers are needed for the query"""
        
        tiers = []
        
        # Get retention policy for customer
        policy = self._get_customer_retention_policy(customer_id)
        hot_cutoff = datetime.utcnow() - timedelta(days=policy.hot_retention_days)
        
        # Check if query time range overlaps with hot storage
        if query_request.end_time >= hot_cutoff:
            tiers.append('hot')
        
        # Check if query time range requires cold storage
        if query_request.start_time < hot_cutoff:
            tiers.append('cold')
        
        return tiers
    
    async def _query_cold_storage(self, query_request: QueryRequest, customer_id: str) -> List[Dict]:
        """Query cold storage using external table function"""
        
        # Generate S3 path pattern for tenant's cold storage
        s3_pattern = f"http://minio:9000/logforge-cold/tenants/{customer_id}/cold/**/*.parquet"
        
        # Convert query filters to ClickHouse WHERE clause
        where_clause = self._build_where_clause(query_request.filters, customer_id)
        
        # Execute query using S3 table function
        cold_query = f"""
        SELECT * FROM s3(
            '{s3_pattern}',
            'minio',
            'minio123', 
            'Parquet'
        )
        WHERE {where_clause}
        ORDER BY ts
        LIMIT {query_request.limit}
        """
        
        try:
            result = await self.ch_client.query(cold_query)
            return [dict(row) for row in result]
        except Exception as e:
            logger.warning("Cold storage query failed", error=str(e), customer_id=customer_id)
            return []  # Return empty results instead of failing
    
    def _build_where_clause(self, filters: Dict[str, Any], customer_id: str) -> str:
        """Build WHERE clause from query filters"""
        
        conditions = [f"customer_id = '{customer_id}'"]  # Always filter by tenant
        
        for field, filter_config in filters.items():
            operator = filter_config.get('operator', 'eq')
            value = filter_config.get('value')
            
            if operator == 'eq':
                conditions.append(f"{field} = '{value}'")
            elif operator == 'contains':
                conditions.append(f"{field} LIKE '%{value}%'")
            elif operator == 'gte':
                conditions.append(f"{field} >= '{value}'")
            elif operator == 'lte':
                conditions.append(f"{field} <= '{value}'")
        
        return ' AND '.join(conditions)
```

### 4. Retention Policy Integration

**Update**: `/apps/api/services/storage_service.py`

```python
# Add to StorageService class

async def apply_retention_policy(self, customer_id: str, policy_data: Dict[str, Any]):
    """Apply retention policy immediately after creation/update"""
    
    try:
        # 1. Save to database (existing functionality)
        policy_id = await self.storage_dao.save_retention_policy(policy_data)
        
        # 2. Apply TTL policies to ClickHouse (NEW)
        ttl_engine = TTLPolicyEngine(self.clickhouse_client)
        await ttl_engine.apply_retention_policy(customer_id, policy_data)
        
        # 3. Schedule background archival if needed (NEW)
        await self._schedule_background_archival(customer_id, policy_data)
        
        logger.info("Retention policy applied successfully", 
                   policy_id=policy_id, customer_id=customer_id)
        
        return policy_id
        
    except Exception as e:
        logger.error("Failed to apply retention policy", error=str(e))
        raise

async def _schedule_background_archival(self, customer_id: str, policy: Dict[str, Any]):
    """Schedule background task to archive old data"""
    
    # Calculate cutoff date for archival
    hot_days = policy['hot_retention_days']
    cutoff_date = datetime.utcnow() - timedelta(days=hot_days)
    
    # Find partitions that need archival
    partitions_query = f"""
    SELECT DISTINCT toDate(ts) as partition_date
    FROM logs_raw_mt 
    WHERE customer_id = '{customer_id}'
    AND ts < '{cutoff_date}'
    ORDER BY partition_date
    """
    
    partitions = await self.clickhouse_client.query(partitions_query)
    
    # Schedule archival for each partition
    cold_storage = ColdStorageService(self.storage_manager, self.clickhouse_client)
    
    for partition in partitions:
        asyncio.create_task(
            cold_storage.archive_tenant_partition(
                customer_id, 
                partition['partition_date'].strftime('%Y-%m-%d')
            )
        )
```

### 5. Router Updates

**Update**: `/apps/api/routers/storage.py`

```python
# Update existing endpoints to use new functionality

@router.post("/retention/{customer_id}")
async def create_retention_policy(
    customer_id: str, 
    policy_request: RetentionPolicyRequest, 
    requesting_customer: str = MiddlewareTenant
):
    """Create and immediately apply retention policy"""
    try:
        # Existing validation...
        
        # Create policy data
        policy_data = {
            "customer_id": customer_id,
            "policy_name": "default",
            "hot_retention_days": policy_request.hot_retention_days,
            "cold_retention_days": policy_request.cold_retention_days,
            "archive_retention_days": policy_request.archive_retention_days,
            "compression_enabled": policy_request.compression_enabled,
            "auto_deletion_enabled": policy_request.auto_deletion_enabled
        }
        
        # Apply policy (this now includes TTL application)
        result = await storage_service.apply_retention_policy(customer_id, policy_data)
        
        return {
            "status": "created_and_applied",
            "customer_id": customer_id,
            "policy": result,
            "message": "Retention policy created and TTL applied to ClickHouse tables",
            "created_at": datetime.now(timezone.utc)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create retention policy: {str(e)}")

# Add new endpoint for querying across storage tiers
@router.post("/query/federated")
async def query_federated_storage(
    query_request: Dict[str, Any],
    customer_id: str = MiddlewareTenant
):
    """Query across hot and cold storage tiers"""
    try:
        federated_engine = FederatedQueryEngine(
            clickhouse_client=storage_service.clickhouse_client,
            cold_storage_service=ColdStorageService(
                storage_service.storage_manager, 
                storage_service.clickhouse_client
            )
        )
        
        # Convert request to QueryRequest object
        query = QueryRequest(
            filters=query_request.get('filters', {}),
            start_time=datetime.fromisoformat(query_request['start_time']),
            end_time=datetime.fromisoformat(query_request['end_time']),
            limit=query_request.get('limit', 1000)
        )
        
        # Execute federated query
        results = await federated_engine.execute_query(query, customer_id)
        
        return {
            "customer_id": customer_id,
            "results": results,
            "query_metadata": {
                "total_results": len(results),
                "storage_tiers_queried": ["hot", "cold"],
                "query_time": datetime.now(timezone.utc)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Federated query failed: {str(e)}")
```

## Database Schema Updates

**File**: `/infra/docker/clickhouse/cold_storage_init.sql`

```sql
-- Storage policies for tiered storage
CREATE STORAGE POLICY IF NOT EXISTS tiered_storage
DISKS default, 's3_disk'
VOLUMES hot DISK default, 
        cold DISK 's3_disk';

-- Configure S3 disk for cold storage
-- This would be added to ClickHouse config
/*
<clickhouse>
    <storage_configuration>
        <disks>
            <s3_disk>
                <type>s3</type>
                <endpoint>http://minio:9000/logforge-cold/</endpoint>
                <access_key_id>minio</access_key_id>
                <secret_access_key>minio123</secret_access_key>
                <region>us-east-1</region>
                <use_environment_credentials>false</use_environment_credentials>
            </s3_disk>
        </disks>
        <policies>
            <tiered_storage>
                <volumes>
                    <hot>
                        <disk>default</disk>
                    </hot>
                    <cold>
                        <disk>s3_disk</disk>
                    </cold>
                </volumes>
            </tiered_storage>
        </policies>
    </storage_configuration>
</clickhouse>
*/

-- Archive metadata table
CREATE TABLE IF NOT EXISTS archive_metadata_mt (
    id String,
    archive_key String,
    customer_id String,
    original_start_date Date,
    original_end_date Date,
    records_archived UInt64,
    data_size_bytes UInt64,
    compression_type String DEFAULT 'snappy',
    encryption_enabled UInt8 DEFAULT 1,
    archive_date DateTime DEFAULT now(),
    storage_backend String DEFAULT 'minio',
    bucket_name String,
    checksum String,
    retention_policy_id String,
    created_at DateTime DEFAULT now(),
    status String DEFAULT 'pending',
    access_count UInt32 DEFAULT 0,
    last_accessed_at DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(archive_date))
ORDER BY (customer_id, archive_date, archive_key)
SETTINGS index_granularity = 8192;

-- Archive access log for audit and billing
CREATE TABLE IF NOT EXISTS archive_access_log_mt (
    customer_id String,
    archive_key String,
    access_type String,  -- 'download', 'query', 'restore'
    user_id String,
    session_id String,
    accessed_at DateTime DEFAULT now(),
    bytes_transferred UInt64,
    query_filter String,
    client_ip String
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(accessed_at))
ORDER BY (customer_id, accessed_at, user_id)
SETTINGS index_granularity = 8192;
```

## Testing Strategy

### Unit Tests

**File**: `/tests/test_cold_storage.py`

```python
import pytest
from datetime import datetime, timedelta
from apps.api.services.cold_storage_service import ColdStorageService
from apps.api.engines.ttl_policy_engine import TTLPolicyEngine

class TestColdStorageService:
    
    @pytest.fixture
    async def cold_storage_service(self):
        # Mock dependencies
        storage_manager = MockStorageManager()
        clickhouse_client = MockClickHouseClient()
        return ColdStorageService(storage_manager, clickhouse_client)
    
    async def test_archive_tenant_partition(self, cold_storage_service):
        """Test archiving a tenant's partition"""
        customer_id = "test-tenant"
        partition_date = "2024-01-01"
        
        # Mock data
        mock_data = [
            {"ts": "2024-01-01 10:00:00", "customer_id": customer_id, "msg": "test log 1"},
            {"ts": "2024-01-01 11:00:00", "customer_id": customer_id, "msg": "test log 2"}
        ]
        
        cold_storage_service.ch_client.set_mock_query_result(mock_data)
        
        # Execute archival
        await cold_storage_service.archive_tenant_partition(customer_id, partition_date)
        
        # Verify archive was created
        assert cold_storage_service.storage_manager.uploaded_files
        uploaded_file = cold_storage_service.storage_manager.uploaded_files[0]
        assert customer_id in uploaded_file['key']
        assert partition_date in uploaded_file['key']
    
    async def test_tenant_isolation(self, cold_storage_service):
        """Test that tenants can only access their own archives"""
        
        # Try to access another tenant's archive
        with pytest.raises(SecurityError):
            await cold_storage_service._verify_tenant_access(
                customer_id="tenant-a",
                archive_path="tenants/tenant-b/cold/2024/01/01/logs.parquet"
            )

class TestTTLPolicyEngine:
    
    @pytest.fixture
    async def ttl_engine(self):
        clickhouse_client = MockClickHouseClient()
        return TTLPolicyEngine(clickhouse_client)
    
    async def test_apply_retention_policy(self, ttl_engine):
        """Test applying retention policy updates ClickHouse TTL"""
        
        policy = {
            "hot_retention_days": 30,
            "archive_retention_days": 365
        }
        
        await ttl_engine.apply_retention_policy("test-tenant", policy)
        
        # Verify TTL commands were executed
        executed_commands = ttl_engine.ch_client.executed_commands
        assert any("ALTER TABLE logs_raw_mt MODIFY TTL" in cmd for cmd in executed_commands)
        assert any("toIntervalDay(30)" in cmd for cmd in executed_commands)
```

### Integration Tests

**File**: `/tests/test_federated_queries.py`

```python
class TestFederatedQueries:
    
    async def test_query_hot_and_cold_storage(self):
        """Test querying across both hot and cold storage"""
        
        # Setup: Create test data in both hot and cold storage
        customer_id = "integration-test-tenant"
        
        # Insert recent data (should be in hot storage)
        recent_data = [
            {"ts": datetime.utcnow(), "customer_id": customer_id, "msg": "recent log"}
        ]
        await self.insert_hot_data(recent_data)
        
        # Mock old data (should be in cold storage)
        old_data = [
            {"ts": datetime.utcnow() - timedelta(days=60), "customer_id": customer_id, "msg": "old log"}
        ]
        await self.mock_cold_data(old_data)
        
        # Execute federated query
        query_request = QueryRequest(
            filters={"customer_id": customer_id},
            start_time=datetime.utcnow() - timedelta(days=90),
            end_time=datetime.utcnow(),
            limit=1000
        )
        
        federated_engine = FederatedQueryEngine(self.ch_client, self.cold_storage)
        results = await federated_engine.execute_query(query_request, customer_id)
        
        # Verify both hot and cold data are returned
        messages = [r['msg'] for r in results]
        assert "recent log" in messages
        assert "old log" in messages
```

## Performance Optimization

### Query Performance

1. **Partition Pruning**: Ensure cold storage queries only scan relevant partitions
2. **Column Pruning**: Only select required columns from Parquet files
3. **Predicate Pushdown**: Apply filters at Parquet level before ClickHouse processing
4. **Parallel Execution**: Execute hot and cold queries in parallel

### Storage Optimization

1. **File Sizing**: Target 100-500MB Parquet files for optimal performance
2. **Compression**: Use Snappy for balance of speed and compression ratio
3. **Partitioning**: Organize by customer_id, year, month, day for efficient pruning
4. **Metadata Caching**: Cache archive metadata to avoid repeated object storage calls

## Operations & Monitoring

### Health Checks

```python
# Add to storage health endpoint
async def get_cold_storage_health(self, customer_id: str) -> Dict[str, Any]:
    """Check cold storage health for tenant"""
    
    return {
        "hot_storage": {
            "table_size": await self._get_table_size("logs_raw_mt", customer_id),
            "oldest_record": await self._get_oldest_record(customer_id),
            "ttl_status": await self._check_ttl_status()
        },
        "cold_storage": {
            "archive_count": await self._get_archive_count(customer_id),
            "total_size": await self._get_cold_storage_size(customer_id),
            "last_archive": await self._get_last_archive_date(customer_id)
        },
        "query_performance": {
            "avg_hot_query_time": await self._get_avg_query_time("hot", customer_id),
            "avg_cold_query_time": await self._get_avg_query_time("cold", customer_id)
        }
    }
```

### Operational Commands

```bash
# Archive specific tenant partition
curl -X POST "http://localhost:7080/v1/storage/archive/tenant-123" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Customer-ID: tenant-123" \
  -d '{"partition_date": "2024-01-01"}'

# Query federated storage
curl -X POST "http://localhost:7080/v1/storage/query/federated" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Customer-ID: tenant-123" \
  -d '{
    "filters": {"level": {"operator": "eq", "value": "ERROR"}},
    "start_time": "2024-01-01T00:00:00Z",
    "end_time": "2024-01-31T23:59:59Z",
    "limit": 1000
  }'

# Check storage health
curl -X GET "http://localhost:7080/v1/storage/health/tenant-123" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Customer-ID: tenant-123"
```

## Next Steps

1. **Implement TTL Policy Engine** - Start with dynamic TTL application
2. **Create Cold Storage Service** - Basic archival functionality  
3. **Add Federated Query Engine** - Enable cross-tier querying
4. **Update Storage Router** - Integrate new endpoints
5. **Test Integration** - Comprehensive testing across all components

This implementation will provide a solid foundation for enterprise-grade cold storage and archival capabilities while maintaining tenant isolation and query performance.