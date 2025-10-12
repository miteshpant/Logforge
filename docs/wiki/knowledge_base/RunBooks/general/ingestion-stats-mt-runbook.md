# Ingestion Stats MT Table Runbook

## Overview
The `ingestion_stats_mt` table tracks detailed ingestion statistics for multi-tenant log processing in Logforge. This table is critical for monitoring ingestion performance, calculating storage quotas, and billing operations.

## Table Schema

```sql
CREATE TABLE ingestion_stats_mt (
    id String,
    customer_id String,
    endpoint String,
    format_type String,
    timestamp DateTime64(3),
    records_ingested UInt64,
    bytes_ingested UInt64,
    processing_time_ms UInt64,
    created_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (customer_id, endpoint, timestamp)
```

## Key Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | String | Unique identifier for the ingestion record | `uuid4()` |
| `customer_id` | String | Tenant identifier | `505908f9-8718-4dea-b2d8-9b9e5ae0bd45` |
| `endpoint` | String | API endpoint used for ingestion | `/v1/ingestion/json`, `/v1/ingestion/syslog` |
| `format_type` | String | Log format type | `json`, `syslog`, `otlp`, `cef`, `nginx`, `text` |
| `timestamp` | DateTime64(3) | When the ingestion occurred | `2025-10-09 12:16:22.000` |
| `records_ingested` | UInt64 | Number of log records processed | `1500` |
| `bytes_ingested` | UInt64 | **CRITICAL**: Actual bytes processed for billing/storage | `2048576` |
| `processing_time_ms` | UInt64 | Time taken to process the batch | `150` |
| `created_at` | DateTime64(3) | Record creation timestamp | Auto-generated |

## Critical Usage

### 1. Storage Quota Calculation
The `bytes_ingested` field is used by the Storage Quota Sync Service to calculate tenant storage usage:

```sql
-- Delta calculation for storage quotas
SELECT sum(bytes_ingested) as delta_bytes
FROM ingestion_stats_mt 
WHERE customer_id = '{tenant_id}'
AND timestamp > '{last_refresh_timestamp}'
```

### 2. Billing & Usage Tracking
This table provides accurate usage data for billing calculations:

```sql
-- Monthly usage for billing
SELECT 
    customer_id,
    sum(bytes_ingested) as total_bytes,
    sum(records_ingested) as total_records,
    count(*) as ingestion_calls
FROM ingestion_stats_mt 
WHERE toYYYYMM(timestamp) = toYYYYMM(now())
GROUP BY customer_id
```

### 3. Performance Monitoring
Track ingestion performance across tenants and endpoints:

```sql
-- Average processing time by endpoint
SELECT 
    endpoint,
    format_type,
    avg(processing_time_ms) as avg_processing_time,
    avg(bytes_ingested) as avg_bytes_per_call
FROM ingestion_stats_mt 
WHERE timestamp >= now() - INTERVAL 1 DAY
GROUP BY endpoint, format_type
```

## Data Sources

### Where Records Come From
Records are inserted by the **Ingestion Service** via the `track_ingestion_success()` method:

```python
# Called from routers/ingestion.py
await ingestion_service.track_ingestion_success(
    customer_id=customer_id,
    endpoint=request.url.path,
    format_type="json",  # or syslog, otlp, etc.
    log_count=len(parsed_logs),
    bytes_processed=len(request_body),
    processing_time_ms=processing_time
)
```

### Integration Points
1. **Ingestion APIs**: All `/v1/ingestion/*` endpoints write to this table
2. **Storage Quota Service**: Reads `bytes_ingested` for quota calculations
3. **Usage Tracking**: Feeds into `usage_records_mt` for billing
4. **Monitoring Dashboards**: Performance metrics and alerting

## FAQs

### Q: Why are there no ingestion stats for a tenant?
**A:** Several possible causes:
1. **No recent ingestion activity** - Check if logs are actually being sent
2. **Async processing delays** - Stats are written in background, may take 1-2 minutes
3. **Service errors** - Check application logs for ingestion failures
4. **Wrong customer_id** - Verify tenant ID in requests

**Debug Steps:**
```sql
-- Check if any data exists for tenant
SELECT count(*) FROM ingestion_stats_mt WHERE customer_id = '{tenant_id}'

-- Check recent activity
SELECT * FROM ingestion_stats_mt 
WHERE customer_id = '{tenant_id}' 
ORDER BY timestamp DESC LIMIT 10
```

### Q: Storage quota is not updating - what's wrong?
**A:** The Storage Quota Sync Service depends on this table. Common issues:

1. **No ingestion data** - No `bytes_ingested` records for the time window
2. **Service not running** - Check if StorageQuotaSyncService is active
3. **Time window mismatch** - Service uses delta calculation based on refresh timestamps

**Debug Steps:**
```sql
-- Check bytes ingested in last 24 hours
SELECT 
    customer_id,
    sum(bytes_ingested) as total_bytes,
    count(*) as records
FROM ingestion_stats_mt 
WHERE timestamp >= now() - INTERVAL 1 DAY
GROUP BY customer_id

-- Check if storage service is finding data
SELECT sum(bytes_ingested) as delta_bytes
FROM ingestion_stats_mt 
WHERE customer_id = '{tenant_id}'
AND timestamp > '{last_sync_time}'
```

### Q: Bytes ingested seems too high/low - is it accurate?
**A:** The `bytes_ingested` field represents the raw request body size:

- **Includes**: JSON formatting, whitespace, metadata
- **Before**: Compression or processing
- **Overhead**: 1.2x multiplier applied for storage calculation (indexes, metadata)

**Debug Steps:**
```sql
-- Compare with actual request patterns
SELECT 
    format_type,
    avg(bytes_ingested) as avg_bytes,
    avg(records_ingested) as avg_records,
    avg(bytes_ingested / records_ingested) as bytes_per_record
FROM ingestion_stats_mt 
WHERE customer_id = '{tenant_id}'
AND timestamp >= now() - INTERVAL 1 DAY
GROUP BY format_type
```

### Q: How long is data retained in this table?
**A:** Data retention follows the table's TTL policy:

- **Partitioned by month**: `toYYYYMM(timestamp)`
- **Typical retention**: 12-24 months for billing/audit purposes
- **Performance**: Older partitions may be moved to cold storage

### Q: Can I trust the processing_time_ms values?
**A:** Yes, but understand what it measures:

- **Includes**: Parsing, validation, database insertion
- **Excludes**: Network latency, authentication overhead
- **Typical values**: 50-500ms depending on batch size and format

## Troubleshooting Guide

### Problem: Missing Ingestion Records

**Symptoms:**
- Tenant reports logs sent but no stats in table
- Storage quotas not updating
- Billing shows zero usage

**Investigation:**
```sql
-- Check recent ingestion activity
SELECT customer_id, count(*), max(timestamp) as last_ingestion
FROM ingestion_stats_mt 
WHERE timestamp >= now() - INTERVAL 6 HOUR
GROUP BY customer_id
ORDER BY last_ingestion DESC

-- Look for specific tenant
SELECT * FROM ingestion_stats_mt 
WHERE customer_id = '{tenant_id}'
ORDER BY timestamp DESC LIMIT 20
```

**Common Causes:**
1. **Authentication failures** - Check API logs for 401/403 errors
2. **Async processing delays** - Stats written in background threads
3. **Database permissions** - IngestionService may lack INSERT permissions
4. **Service crashes** - Check if ingestion service is running

**Resolution:**
1. Verify tenant authentication and API access
2. Check application logs for ingestion errors
3. Restart ingestion service if needed
4. Manual verification with test API calls

### Problem: Incorrect Byte Counts

**Symptoms:**
- Storage quotas much higher/lower than expected
- Billing discrepancies
- Unusual bytes-per-record ratios

**Investigation:**
```sql
-- Analyze byte patterns
SELECT 
    endpoint,
    format_type,
    min(bytes_ingested) as min_bytes,
    max(bytes_ingested) as max_bytes,
    avg(bytes_ingested) as avg_bytes,
    count(*) as call_count
FROM ingestion_stats_mt 
WHERE customer_id = '{tenant_id}'
AND timestamp >= now() - INTERVAL 1 DAY
GROUP BY endpoint, format_type

-- Check for outliers
SELECT * FROM ingestion_stats_mt 
WHERE customer_id = '{tenant_id}'
AND (bytes_ingested > 10000000 OR bytes_ingested < 100)
ORDER BY timestamp DESC
```

**Common Causes:**
1. **Request body size calculation error** - Check ingestion service code
2. **Compression artifacts** - Compressed vs uncompressed data confusion
3. **Large batch uploads** - Single request with many records
4. **Format overhead** - JSON includes significant metadata

**Resolution:**
1. Verify request size calculation in ingestion service
2. Compare with actual HTTP request sizes
3. Review batch size limits and recommendations
4. Consider format efficiency (JSON vs binary formats)

### Problem: High Processing Times

**Symptoms:**
- `processing_time_ms` consistently > 1000ms
- Performance complaints from users
- Timeout errors in ingestion

**Investigation:**
```sql
-- Processing time analysis
SELECT 
    endpoint,
    format_type,
    avg(processing_time_ms) as avg_time,
    max(processing_time_ms) as max_time,
    avg(records_ingested) as avg_records,
    avg(bytes_ingested) as avg_bytes
FROM ingestion_stats_mt 
WHERE timestamp >= now() - INTERVAL 1 HOUR
GROUP BY endpoint, format_type
ORDER BY avg_time DESC

-- Identify slow requests
SELECT * FROM ingestion_stats_mt 
WHERE processing_time_ms > 2000
ORDER BY timestamp DESC LIMIT 50
```

**Common Causes:**
1. **Database performance** - ClickHouse under load
2. **Large batch sizes** - Too many records per request
3. **Complex parsing** - Inefficient format processing
4. **Network issues** - Database connection problems

**Resolution:**
1. Monitor ClickHouse performance and optimize queries
2. Implement batch size limits in ingestion API
3. Profile and optimize parsing logic
4. Check database connection pool settings

## Monitoring & Alerts

### Key Metrics to Monitor

1. **Ingestion Rate**: Records/second across all tenants
2. **Processing Latency**: Average `processing_time_ms`
3. **Error Rate**: Failed vs successful ingestion attempts
4. **Storage Growth**: `bytes_ingested` trends
5. **Tenant Activity**: Active vs inactive tenants

### Recommended Alerts

```sql
-- Alert: No ingestion activity for active tenant
SELECT customer_id
FROM tenant_quotas_mt tq
WHERE tq.quota_type = 'monthly_ingestion'
AND NOT EXISTS (
    SELECT 1 FROM ingestion_stats_mt ist 
    WHERE ist.customer_id = tq.customer_id 
    AND ist.timestamp >= now() - INTERVAL 6 HOUR
)

-- Alert: Unusually high processing times
SELECT customer_id, endpoint, avg(processing_time_ms) as avg_time
FROM ingestion_stats_mt 
WHERE timestamp >= now() - INTERVAL 1 HOUR
GROUP BY customer_id, endpoint
HAVING avg_time > 1000

-- Alert: Ingestion spikes (potential abuse)
SELECT customer_id, sum(bytes_ingested) as bytes_last_hour
FROM ingestion_stats_mt 
WHERE timestamp >= now() - INTERVAL 1 HOUR
GROUP BY customer_id
HAVING bytes_last_hour > 1000000000  -- 1GB/hour threshold
```

## Related Systems

### Dependencies
- **Ingestion Service** (`services/ingestion_service.py`) - Writes records
- **Storage Quota Sync** (`services/storage_quota_sync_service.py`) - Reads for quotas
- **Tenant Service** (`services/tenant_service.py`) - Links to quota management
- **ClickHouse Database** - Storage and query engine

### Connected Tables
- `logs_raw_mt` - Actual log data storage
- `tenant_quotas_mt` - Storage quota tracking
- `usage_records_mt` - Billing and usage records
- `api_usage_mt` - API call tracking

## Performance Considerations

### Query Optimization
- Always filter by `customer_id` for tenant isolation
- Use `timestamp` ranges for time-based queries
- Leverage monthly partitioning for historical data
- Index on `(customer_id, endpoint, timestamp)` for common patterns

### Data Volume Management
- Monitor partition sizes and growth rates
- Implement data retention policies for old months
- Consider archival to cold storage for historical data
- Use aggregation for long-term trend analysis

## Emergency Procedures

### Data Corruption Recovery
1. **Identify affected time range** from error logs
2. **Stop ingestion service** to prevent further corruption
3. **Query known good data** from adjacent time periods
4. **Restore from backups** if available
5. **Replay ingestion requests** if source data available

### Service Outage Response
1. **Check ClickHouse connectivity** and performance
2. **Verify service health** and restart if needed
3. **Monitor queue buildup** in async processing
4. **Implement temporary rate limiting** if overloaded
5. **Scale resources** if needed for recovery

---

**Last Updated**: October 2025  
**Version**: 1.0  
**Maintained By**: Logforge Platform Team