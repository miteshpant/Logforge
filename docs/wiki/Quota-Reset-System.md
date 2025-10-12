# Quota Reset System Documentation

## Overview

The Quota Reset System provides automated quota management with configurable reset periods for different quota types. It stores historical usage data when quotas are reset and provides administrative APIs for monitoring and control.

## Architecture

### Components

1. **QuotaResetService** - Core service for quota reset logic
2. **QuotaResetScheduler** - Background scheduler for automated resets  
3. **quota_usage_history_mt** - Database table for historical usage storage
4. **Quota Management API** - Administrative endpoints for system control
5. **Environment Configuration** - Configurable reset periods per quota type

### Database Tables

#### tenant_quotas_mt (Existing)
```sql
CREATE TABLE tenant_quotas_mt (
    id String,
    tenant_id String,
    quota_type Enum8('daily_ingestion' = 1, 'monthly_ingestion' = 2, 'storage_gb' = 3, 'api_calls' = 4, 'users' = 5, 'alerts' = 6),
    quota_limit UInt64,
    current_usage UInt64 DEFAULT 0,
    reset_period Enum8('daily' = 1, 'monthly' = 2, 'never' = 3),
    last_reset DateTime64(3) DEFAULT now64(3),
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String
);
```

#### quota_usage_history_mt (New)
```sql
CREATE TABLE quota_usage_history_mt (
    id String,
    tenant_id String,
    customer_id String,
    quota_type Enum8('daily_ingestion' = 1, 'monthly_ingestion' = 2, 'storage_gb' = 3, 'api_calls' = 4, 'users' = 5, 'alerts' = 6),
    usage_amount UInt64,
    quota_limit UInt64,
    reset_period_start DateTime64(3),
    reset_period_end DateTime64(3),
    billing_period String, -- YYYY-MM format
    reset_reason Enum8('scheduled_reset' = 1, 'manual_reset' = 2, 'policy_change' = 3, 'billing_cycle' = 4),
    metadata String DEFAULT '{}',
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3)
);
```

## Configuration

### Environment Variables

Configure reset periods for each quota type (in days):

```bash
# Daily ingestion quota - reset every day
QUOTA_RESET_DAILY_INGESTION_DAYS=1

# Monthly ingestion quota - reset every month
QUOTA_RESET_MONTHLY_INGESTION_DAYS=30

# Storage quota - never reset (cumulative)
QUOTA_RESET_STORAGE_GB_DAYS=0

# API calls quota - reset every month
QUOTA_RESET_API_CALLS_DAYS=30

# Users quota - never reset (subscription-based)
QUOTA_RESET_USERS_DAYS=0

# Alerts quota - reset every month
QUOTA_RESET_ALERTS_DAYS=30

# Scheduler check interval (minutes)
QUOTA_RESET_CHECK_INTERVAL_MINUTES=60
```

### Configuration Patterns

#### Production Configuration
```bash
QUOTA_RESET_DAILY_INGESTION_DAYS=1     # Reset daily
QUOTA_RESET_MONTHLY_INGESTION_DAYS=30  # Reset monthly  
QUOTA_RESET_STORAGE_GB_DAYS=0          # Never reset
QUOTA_RESET_API_CALLS_DAYS=30          # Reset monthly
QUOTA_RESET_USERS_DAYS=0               # Never reset
QUOTA_RESET_ALERTS_DAYS=30             # Reset monthly
QUOTA_RESET_CHECK_INTERVAL_MINUTES=60  # Check hourly
```

#### Development Configuration
```bash
QUOTA_RESET_DAILY_INGESTION_DAYS=1     # Reset daily
QUOTA_RESET_MONTHLY_INGESTION_DAYS=7   # Reset weekly (faster testing)
QUOTA_RESET_STORAGE_GB_DAYS=0          # Never reset
QUOTA_RESET_API_CALLS_DAYS=7           # Reset weekly
QUOTA_RESET_USERS_DAYS=0               # Never reset
QUOTA_RESET_ALERTS_DAYS=7              # Reset weekly
QUOTA_RESET_CHECK_INTERVAL_MINUTES=10  # Check every 10 minutes
```

## API Endpoints

### Administrative Quota Management

Base path: `/v1/admin/quotas`

#### 1. Get Reset Schedule
```http
GET /v1/admin/quotas/reset-schedule
```
Returns current configuration and next reset times.

#### 2. Trigger Manual Reset Check
```http
POST /v1/admin/quotas/check-and-reset
```
Manually trigger quota reset check (platform admin only).

#### 3. Force Reset Tenant Quotas
```http
POST /v1/admin/quotas/reset-tenant/{tenant_id}
Content-Type: application/json

{
  "quota_types": ["monthly_ingestion", "api_calls"]  // Optional
}
```

#### 4. Get Quota History
```http
GET /v1/admin/quotas/usage-history/{tenant_id}?quota_type=monthly_ingestion&months=6
```

#### 5. Scheduler Control
```http
GET /v1/admin/quotas/scheduler/status    # Get status
POST /v1/admin/quotas/scheduler/start    # Start scheduler
POST /v1/admin/quotas/scheduler/stop     # Stop scheduler
```

## Quota Reset Process

### Automated Reset Flow

1. **Scheduler Check**: Runs every `QUOTA_RESET_CHECK_INTERVAL_MINUTES`
2. **Quota Discovery**: Find quotas where `last_reset < (now - reset_days)`
3. **Historical Storage**: Store current usage in `quota_usage_history_mt`
4. **Quota Reset**: Set `current_usage = 0`, update `last_reset = now()`
5. **Logging**: Log all reset activities with tenant and quota details

### Historical Data Storage

Before resetting any quota, the system:

1. Creates historical record with current usage snapshot
2. Stores billing period, reset reason, and metadata
3. Preserves quota limits and usage amounts
4. Tracks reset period boundaries for billing

### Reset Reasons

- `scheduled_reset`: Automated reset based on configuration
- `manual_reset`: Administrator-initiated reset
- `policy_change`: Reset due to subscription/policy changes
- `billing_cycle`: Reset for billing period transitions

## Usage Examples

### Basic Setup

1. **Configure Environment**:
```bash
# Copy example configuration
cp .env.quota.example .env.quota
source .env.quota
```

2. **Start Application**: The quota scheduler starts automatically with the API server.

3. **Monitor via API**:
```bash
# Check scheduler status
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "X-Customer-ID: platform" \
     http://localhost:7080/v1/admin/quotas/scheduler/status

# View reset schedule
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "X-Customer-ID: platform" \
     http://localhost:7080/v1/admin/quotas/reset-schedule
```

### Force Reset Example

```bash
# Force reset specific tenant quotas
curl -X POST \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "X-Customer-ID: platform" \
     -d '{"quota_types": ["monthly_ingestion", "api_calls"]}' \
     http://localhost:7080/v1/admin/quotas/reset-tenant/tenant-123
```

### Historical Data Query

```bash
# Get 6 months of quota history
curl -H "Authorization: Bearer $TENANT_TOKEN" \
     -H "X-Customer-ID: tenant-123" \
     "http://localhost:7080/v1/admin/quotas/usage-history/tenant-123?months=6"
```

## Testing

### Test Script

Run the comprehensive test suite:

```bash
cd /path/to/logforge
python test_quota_reset_system.py
```

The test script validates:
- Configuration loading from environment variables
- Quota reset logic with various scenarios
- Historical data storage and retrieval
- Force reset functionality
- Different environment configurations

### Manual Testing

1. **Create Test Quota**: Insert quota with old `last_reset` date
2. **Trigger Reset**: Call manual reset API
3. **Verify Results**: Check quota was reset and historical data stored
4. **Check Logs**: Review application logs for reset activities

## Monitoring

### Key Metrics

- **Reset Frequency**: How often quotas are being reset
- **Historical Data Growth**: Size of quota_usage_history_mt table
- **Error Rates**: Failed reset attempts and reasons
- **Scheduler Health**: Scheduler uptime and check intervals

### Log Analysis

The system logs all quota reset activities:

```
INFO - Quota reset completed - tenant_id=abc-123 quota_type=monthly_ingestion previous_usage=7500
INFO - Historical usage stored - tenant_id=abc-123 quota_type=monthly_ingestion usage_amount=7500
```

### Alerts

Consider setting up alerts for:
- Failed quota resets
- Scheduler downtime
- High quota utilization before reset
- Historical table growth rate

## Troubleshooting

### Common Issues

1. **Quotas Not Resetting**
   - Check environment configuration
   - Verify scheduler is running
   - Review application logs for errors

2. **Historical Data Missing**
   - Check database table permissions
   - Verify quota_usage_history_mt table exists
   - Review reset process logs

3. **Scheduler Not Starting**
   - Check database connectivity
   - Verify environment variables
   - Review application startup logs

### Debug Commands

```bash
# Check scheduler status
curl -H "X-Customer-ID: platform" /v1/admin/quotas/scheduler/status

# Manual reset check
curl -X POST -H "X-Customer-ID: platform" /v1/admin/quotas/check-and-reset

# View configuration
curl -H "X-Customer-ID: platform" /v1/admin/quotas/reset-schedule
```

## Security Considerations

### Access Control

- **Platform Admin Only**: Reset triggers and scheduler control
- **Tenant Isolation**: Historical data access restricted to tenant
- **API Authentication**: All endpoints require valid JWT tokens

### Data Protection

- **Historical Preservation**: Usage data preserved for billing accuracy
- **Audit Trail**: All reset activities logged with administrator context
- **Tenant Isolation**: Historical data partitioned by customer_id

## Performance Considerations

### Scalability

- **Partitioned Tables**: Historical data partitioned by customer and month
- **Batch Processing**: Reset operations grouped by quota type
- **Background Processing**: Non-blocking scheduler operation

### Optimization

- **Index Strategy**: Efficient queries on tenant_id and quota_type
- **Cleanup Policies**: Consider TTL for very old historical data
- **Connection Pooling**: Database connections managed efficiently

## Future Enhancements

### Planned Features

1. **Dynamic Configuration**: Update reset periods without restart
2. **Webhook Notifications**: Notify external systems of resets
3. **Usage Forecasting**: Predict quota exhaustion times
4. **Granular Permissions**: More fine-grained access control
5. **Billing Integration**: Automated invoice generation from historical data

### Extension Points

- **Custom Reset Logic**: Plugin system for tenant-specific rules
- **External Triggers**: API hooks for external reset triggers
- **Advanced Scheduling**: Cron-style scheduling expressions
- **Multi-Region Support**: Distributed quota management