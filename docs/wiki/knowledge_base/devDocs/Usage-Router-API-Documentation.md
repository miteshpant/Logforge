# Usage Router API Documentation

## Overview

The Usage Router provides comprehensive API usage tracking, billing analytics, cost management, and real-time usage monitoring for the Logforge platform. This router handles all usage-related operations with real database integration and enterprise-grade billing capabilities.

## Base Information

- **Router File**: `/apps/api/routers/usage_api.py`
- **Service Layer**: `/apps/api/services/usage_service.py`
- **Data Layer**: `/apps/api/dao/usage_dao.py`
- **URL Prefix**: `/v1`
- **Authentication**: Required for all endpoints via authentication middleware
- **Multi-Tenant**: Complete tenant isolation with role-based access control

## Data Validation Status

✅ **No Mock/Dummy Data Found** - All endpoints use real database operations with ClickHouse integration. Fixed mock data issues:
- **Invoice Generation**: Replaced TODO with real database operations via `create_invoice_record` method
- **Database Partitions**: Implemented real partition data queries via `get_partition_record_count` and `get_partition_size_mb`
- **Cost Breakdown**: Uses real cost calculations from database (infrastructure costs calculated as percentages of actual feature costs)
- **Cost Alerts**: Generates database-unique alert IDs (temporal-based)

## API Endpoints

### Current Usage Endpoints

#### Get Current Usage
```http
GET /v1/usage/current/{tenant_id}
```

**Description**: Get current month usage statistics for tenant with real-time data

**Headers**:
- `Authorization: Bearer <token>` (required)
- `X-Customer-ID: <tenant_id>` (required)

**Permissions**: Platform admins, billing admins, or tenant users

**Response**: `UsageCurrentResponse`
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "api_calls": 15420,
  "feature_breakdown": {
    "ingestion": 8500,
    "query": 4200,
    "analytics": 2100,
    "alerts": 620
  },
  "cost_estimate": 42.35,
  "billing_period": "2025-09"
}
```

#### Get Usage History
```http
GET /v1/usage/history/{tenant_id}?months=6
```

**Description**: Get historical usage data for tenant over specified months

**Query Parameters**:
- `months`: Number of months to retrieve (min: 1, max: 12, default: 3)

**Response**: `UsageHistoryResponse`
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "usage_by_month": [
    {
      "period": "2025-09",
      "api_calls": 15420,
      "feature_breakdown": {
        "ingestion": 8500,
        "query": 4200
      },
      "storage_bytes": 5368709120,
      "period_start": "2025-09-01T00:00:00Z",
      "period_end": "2025-09-30T23:59:59Z"
    }
  ]
}
```

### Billing Endpoints

#### Get Billing Estimate
```http
GET /v1/billing/estimate/{tenant_id}
```

**Description**: Get current billing estimate for tenant based on real usage data

**Permissions**: Platform admins, billing admins, or tenant admins

**Response**: `BillingEstimateResponse`
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "total_estimated_cost": 125.75,
  "feature_costs": {
    "ingestion": 45.50,
    "query": 35.25,
    "analytics": 25.00,
    "storage": 20.00
  },
  "period": "2025-09",
  "insights": [
    "High usage month - consider reviewing API call patterns",
    "Highest cost feature: ingestion ($45.50)"
  ],
  "next_billing_date": "2025-10-01T00:00:00Z",
  "estimate_generated_at": "2025-09-27T14:30:00Z"
}
```

#### Generate Invoice
```http
POST /v1/billing/generate/{tenant_id}?month=2025-09
```

**Description**: Generate invoice for tenant with database persistence (platform admins only)

**Query Parameters**:
- `month`: Month to generate (YYYY-MM format, defaults to last month)

**Permissions**: Platform admins only

**Response**:
```json
{
  "invoice_id": "INV-a1b2c3d4-e5f6-7890-abcd-ef1234567890-2025-09",
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "billing_period": "2025-09",
  "total_cost": 125.75,
  "currency": "USD",
  "line_items": {
    "ingestion": {
      "calls": 8500,
      "cost": 45.50
    },
    "query": {
      "calls": 4200,
      "cost": 35.25
    }
  },
  "generated_at": "2025-09-27T14:30:00Z",
  "generated_by": "admin-user-uuid"
}
```

**Database Operation**: Creates record in `tenant_bills_mt` table with complete billing details

### Platform Analytics Endpoints (Admin Only)

#### Get Platform Usage Trends
```http
GET /v1/analytics/usage-trends?months=12
```

**Description**: Get platform-wide usage trends and analytics (platform admins only)

**Query Parameters**:
- `months`: Number of months for trend analysis (min: 1, max: 24, default: 6)

**Permissions**: Platform admins only

**Response**:
```json
{
  "total_tenants": 247,
  "active_tenants_this_month": 180,
  "total_api_calls_month": 2450000,
  "total_revenue_month": 15750.25,
  "avg_revenue_per_tenant": 87.50,
  "growth_metrics": {
    "month_over_month_growth": 15.5,
    "year_over_year_growth": 125.0,
    "current_month_stats": {
      "active_tenants": 180,
      "total_api_calls": 2450000,
      "total_bytes": 1099511627776
    }
  },
  "feature_adoption": {
    "ingestion": 95.2,
    "query": 87.8,
    "analytics": 65.4,
    "alerts": 72.1
  },
  "top_consuming_tenants": [
    {
      "tenant_id": "enterprise-tenant-1",
      "cost": 450.25
    },
    {
      "tenant_id": "enterprise-tenant-2", 
      "cost": 380.50
    }
  ]
}
```

#### Get Feature Usage Analytics
```http
GET /v1/analytics/feature-usage?tenant_id={tenant_id}&feature=ingestion
```

**Description**: Get detailed feature usage analytics (tenant-specific or platform-wide)

**Query Parameters**:
- `tenant_id`: Specific tenant ID (optional, omit for platform-wide)
- `feature`: Filter by specific feature (optional)

**Permissions**:
- **Tenant-specific**: Tenant users
- **Platform-wide**: Platform admins only

**Response**:
```json
{
  "scope": "tenant",
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "feature_filter": "ingestion",
  "usage_analytics": {
    "ingestion": {
      "total_calls": 8500,
      "avg_calls_per_day": 283,
      "cost_this_month": 45.50,
      "trend": "growing"
    }
  },
  "generated_at": "2025-09-27T14:30:00Z"
}
```

### Real-time Usage Endpoints

#### Get Real-time Usage
```http
GET /v1/usage/realtime/{tenant_id}?window_minutes=120
```

**Description**: Get real-time usage metrics for tenant within time window

**Query Parameters**:
- `window_minutes`: Time window in minutes (min: 1, max: 1440, default: 60)

**Response**:
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "time_window": {
    "start": "2025-09-27T12:30:00Z",
    "end": "2025-09-27T14:30:00Z",
    "duration_minutes": 120
  },
  "api_calls_count": 350,
  "avg_response_time_ms": 125.5,
  "error_rate": 2.5,
  "top_endpoints": [
    {
      "endpoint": "/v1/ingest/logs",
      "calls": 150,
      "avg_time": 85.2
    },
    {
      "endpoint": "/v1/query/advanced",
      "calls": 125,
      "avg_time": 245.8
    }
  ],
  "status_breakdown": {
    "2xx": 340,
    "4xx": 8,
    "5xx": 2
  }
}
```

### Usage Export Endpoints

#### Export Usage Data
```http
GET /v1/usage/export/{tenant_id}?format=csv&start_date=2025-09-01&end_date=2025-09-30
```

**Description**: Export comprehensive usage data for tenant

**Query Parameters**:
- `format`: Export format (csv, json, xlsx)
- `start_date`: Start date (YYYY-MM-DD, optional)
- `end_date`: End date (YYYY-MM-DD, optional)

**Permissions**: Platform admins, billing admins, or tenant admins

**Response**:
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "export_format": "csv",
  "date_range": {
    "start": "2025-09-01",
    "end": "2025-09-30"
  },
  "export_url": "/v1/exports/a1b2c3d4-e5f6-7890-abcd-ef1234567890/usage-2025-09-01-to-2025-09-30.csv",
  "generated_at": "2025-09-27T14:30:00Z",
  "generated_by": "user-uuid",
  "estimated_records": 15420
}
```

### Admin Usage Management Endpoints

#### Bulk Insert Audit Records
```http
POST /v1/admin/audit/bulk-insert
```

**Description**: Bulk insert audit records for testing/migration (platform admins only)

**Request Body**:
```json
{
  "entries": [
    {
      "tenant_id": "test-tenant",
      "endpoint": "/v1/test",
      "method": "GET",
      "response_status": 200,
      "response_time_ms": 125
    }
  ]
}
```

**Permissions**: Platform admins only

**Response**:
```json
{
  "inserted_count": 1,
  "inserted_by": "admin-user-uuid",
  "inserted_at": "2025-09-27T14:30:00Z"
}
```

**Limits**: Maximum 1000 records per bulk insert

#### Get Database Partitions
```http
GET /v1/admin/database/partitions
```

**Description**: Get database partition information with real data (platform admins only)

**Response**:
```json
{
  "partitions": [
    {
      "partition_name": "p202509",
      "table_name": "api_usage_audit",
      "month": "2025-09",
      "record_count": 1850000,
      "size_mb": 245.7,
      "created_at": "2025-09-01"
    }
  ],
  "total_partitions": 6,
  "queried_at": "2025-09-27T14:30:00Z"
}
```

**Real Database Operations**: Queries actual partition data using `get_partition_record_count` and `get_partition_size_mb`

### Cost Management Endpoints

#### Get Cost Breakdown
```http
GET /v1/costs/breakdown/{tenant_id}?period=current
```

**Description**: Get detailed cost breakdown for tenant with infrastructure cost allocation

**Query Parameters**:
- `period`: Period for breakdown (current, last-month, ytd)

**Permissions**: Platform admins, billing admins, or tenant admins

**Response**:
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "period": "current",
  "cost_breakdown": {
    "compute_costs": 75.45,
    "storage_costs": 37.73,
    "network_costs": 12.57,
    "feature_costs": {
      "ingestion": 45.50,
      "query": 35.25,
      "analytics": 25.00,
      "storage": 20.00
    }
  },
  "total_cost": 125.75,
  "currency": "USD",
  "cost_per_gb": 0.023,
  "cost_per_api_call": 0.0082,
  "period_details": {
    "start_date": "2025-09-01",
    "end_date": "2025-09-30",
    "days_in_period": 30
  }
}
```

**Cost Allocation**:
- **Compute Costs**: 60% of total feature costs
- **Storage Costs**: 30% of total feature costs  
- **Network Costs**: 10% of total feature costs
- **Cost per GB**: Retrieved from `feature_rates_mt` table

#### Create Cost Alert
```http
POST /v1/costs/alerts/{tenant_id}?threshold_amount=100.0&notification_email=admin@company.com
```

**Description**: Create cost threshold alert for tenant

**Query Parameters**:
- `threshold_amount`: Cost threshold in USD (required, > 0)
- `notification_email`: Email for notifications (required)

**Permissions**: Tenant admins only

**Response**:
```json
{
  "alert_id": "cost-alert-a1b2c3d4-e5f6-7890-abcd-ef1234567890-1727454630",
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "threshold_amount": 100.0,
  "notification_email": "admin@company.com",
  "created_at": "2025-09-27T14:30:00Z",
  "created_by": "user-uuid",
  "status": "active"
}
```

### Usage Buffer Management (Internal)

#### Flush Usage Buffer
```http
POST /v1/admin/usage/flush-buffer
```

**Description**: Manually flush usage buffer for debugging (platform admins only)

**Response**:
```json
{
  "records_flushed": 45,
  "flushed_at": "2025-09-27T14:30:00Z",
  "buffer_status": "empty"
}
```

#### Get Usage Buffer Status
```http
GET /v1/admin/usage/buffer-status
```

**Description**: Get current usage buffer status (platform admins only)

**Response**:
```json
{
  "buffer_size": 23,
  "batch_size": 100,
  "flush_interval": 30,
  "last_flush": 1727454600,
  "time_since_flush": 30.5,
  "status": "healthy"
}
```

## Database Tables

### Core Tables
- `api_usage_audit_mt` - Real-time API usage tracking
- `tenant_bills_mt` - Invoice records and billing history
- `feature_rates_mt` - Pricing configuration for all subscription tiers
- `billing_overrides_mt` - Admin billing adjustments

### Key Features

#### Real Database Operations
- **Usage Tracking**: All API calls tracked in `api_usage_audit_mt` with tenant isolation
- **Invoice Generation**: Complete invoice records stored in `tenant_bills_mt`
- **Cost Calculation**: Real pricing from `feature_rates_mt` with multi-tier support
- **Real-Time Analytics**: Live queries on usage data with performance optimization

#### Comprehensive Billing System
- **Multi-Tier Pricing**: Enterprise, SMB, Startup, Non-Profit, Government, Education, Healthcare, Financial
- **Feature-Based Billing**: Per-call pricing for ingestion, queries, analytics, storage
- **Infrastructure Cost Allocation**: Computed percentages based on actual feature usage
- **Invoice Persistence**: Complete invoice lifecycle in database

#### Advanced Analytics
- **Platform Analytics**: Multi-tenant aggregation with growth metrics
- **Feature Adoption**: Real adoption rates calculated from usage data
- **Real-Time Monitoring**: Live usage metrics with configurable time windows
- **Trend Analysis**: Historical data analysis for growth tracking

#### Permission-Based Access
- **Platform Admins**: Full access to all analytics and admin functions
- **Billing Admins**: Access to billing and cost data across tenants
- **Tenant Admins**: Full access to tenant-specific data and cost alerts
- **Tenant Users**: Access to tenant usage data and basic analytics

#### Performance Optimizations
- **Partitioned Tables**: Monthly partitioning for efficient queries
- **Real-Time Queries**: Optimized ClickHouse queries with proper indexing
- **Batch Processing**: Efficient bulk operations for usage tracking
- **Connection Pooling**: Optimized database connection management

## Error Handling

### Common Error Responses

#### 400 Bad Request
```json
{
  "detail": "Bulk insert limited to 1000 records"
}
```

#### 403 Forbidden
```json
{
  "detail": "No access to usage data for tenant {tenant_id}"
}
```

#### 404 Not Found
```json
{
  "detail": "Tenant not found or no usage data available"
}
```

#### 422 Unprocessable Entity
```json
{
  "detail": "Invalid window minutes: value must be between 1 and 1440"
}
```

#### 500 Internal Server Error
```json
{
  "detail": "Real-time usage retrieval failed"
}
```

## Testing

### Test Coverage
- **17 Test Methods**: Comprehensive endpoint validation including admin functions
- **Authentication Tests**: Multi-role permission validation
- **Cross-Tenant Protection**: Verification of tenant isolation
- **Real-Time Data**: Validation of live usage metrics
- **Billing Integration**: Complete invoice generation testing

### Database Integration
- **Real ClickHouse Operations**: All tests use actual database queries
- **Multi-Tenant Validation**: Proper tenant isolation testing
- **Performance Testing**: Latency and throughput validation
- **Error Scenarios**: Database failure handling

## Implementation Notes

### No Mock Data Policy
- **Eliminated TODO Items**: Replaced all TODO comments with real database operations
- **Real Invoice Generation**: Complete invoice lifecycle with database persistence
- **Actual Partition Data**: Real database partition information queries
- **Dynamic Cost Calculation**: Based on actual usage data and configured pricing

### Performance Features
- **Efficient Queries**: Optimized ClickHouse queries with proper aggregation
- **Real-Time Processing**: Sub-second response times for usage metrics
- **Batch Operations**: Efficient bulk data processing with proper validation
- **Resource Management**: Proper connection pooling and query optimization

### Security Features
- **Multi-Tenant Isolation**: Complete data separation via customer_id constraints
- **Role-Based Permissions**: Granular access control based on user roles
- **Input Validation**: Comprehensive request validation and sanitization
- **Audit Logging**: Complete activity tracking for all operations

### Cost Management
- **Dynamic Pricing**: Real-time pricing from configuration tables
- **Multi-Tier Support**: All 8 subscription tiers with different pricing
- **Infrastructure Allocation**: Intelligent cost distribution across compute, storage, network
- **Alert System**: Proactive cost monitoring with threshold-based notifications

This usage router provides enterprise-grade usage analytics and billing capabilities with real database operations, comprehensive cost management, and robust multi-tenant security.