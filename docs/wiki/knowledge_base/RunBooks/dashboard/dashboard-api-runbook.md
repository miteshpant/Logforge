# Dashboard API Runbook

## Overview

The Dashboard API provides comprehensive dashboard management functionality for Logforge, supporting both default enterprise dashboards and custom user-created dashboards. This system enables real-time data visualization, widget management, and dashboard sharing capabilities.

## API Endpoints Summary

| Endpoint | Method | Purpose | Tables Used |
|----------|---------|---------|-------------|
| `/v1/dashboards` | GET | List all dashboards | `dashboards_mt` + DashboardEngine |
| `/v1/dashboards` | POST | Create custom dashboard | `dashboards_mt` |
| `/v1/dashboards/{id}` | GET | Get dashboard configuration | `dashboards_mt`, `dashboard_widgets_mt` + DashboardEngine |
| `/v1/dashboards/{id}/data` | GET | Get dashboard with live data | `logs_raw_mt` + widget queries |
| `/v1/dashboards/{id}` | PUT | Update dashboard | `dashboards_mt` |
| `/v1/dashboards/{id}` | DELETE | Delete dashboard | `dashboards_mt` |
| `/v1/dashboards/{id}/widgets` | POST | Create widget | `dashboard_widgets_mt` |
| `/v1/dashboards/{id}/widgets/{widget_id}/data` | GET | Get widget data | `logs_raw_mt` |
| `/v1/dashboards/{id}/widgets/{widget_id}` | PUT | Update widget | `dashboard_widgets_mt` |
| `/v1/dashboards/{id}/widgets/{widget_id}` | DELETE | Delete widget | `dashboard_widgets_mt` |
| `/v1/dashboards/{id}/share` | POST | Share dashboard | `dashboard_shares_mt` |
| `/v1/dashboards/{id}/shares` | GET | Get sharing info | `dashboard_shares_mt` |

## Database Tables

### Primary Tables
- **`dashboards_mt`**: Custom dashboard storage with multi-tenant isolation
- **`dashboard_widgets_mt`**: Widget configurations and query definitions
- **`dashboard_shares_mt`**: Dashboard sharing permissions and access control

### Data Source Tables
- **`logs_raw_mt`**: Primary data source for all widget queries and visualizations
- **`query_cache_mt`**: Query result caching for improved performance

## Authentication & Authorization

All endpoints require:
- **Bearer Token**: Valid JWT token in Authorization header
- **X-Customer-ID**: Tenant identifier for multi-tenant data isolation
- **Tenant Validation**: Automatic customer_id filtering for all database operations

## Default Dashboards

The system provides 6 pre-built enterprise dashboards via DashboardEngine:

1. **Security Operations Center** (`security`)
   - Real-time security monitoring and threat detection
   - 5 widgets: threat timeline, event types, source IPs, security levels, incident status

2. **Performance Monitoring** (`performance`)
   - Application performance metrics and error rates
   - 5 widgets: response times, error rates, throughput, slow queries, service health

3. **Infrastructure Overview** (`infrastructure`)
   - System health and resource utilization
   - 5 widgets: CPU usage, memory usage, disk I/O, network traffic, service availability

4. **Business Intelligence** (`business`)
   - User behavior and business metrics analysis
   - 5 widgets: user activity, feature usage, conversion rates, revenue metrics, geographical data

5. **Compliance & Audit** (`compliance`)
   - Audit trails and regulatory compliance monitoring
   - 5 widgets: audit events, policy violations, data access logs, compliance score, risk assessment

6. **Executive Overview** (`executive`)
   - High-level KPIs for executive decision making
   - 6 widgets: business metrics, operational health, security posture, financial indicators, growth metrics, executive summary

## Widget Types & Data Generation

### 1. Line Charts (`line_chart`)
**Purpose**: Time series visualization
**Data Source**: `get_time_series_data()` from DashboardDAO
**Features**:
- Hourly time buckets using `toStartOfHour(ts)`
- Dynamic filtering (eq, in operators)
- Configurable aggregations (count, sum, avg)
**Output Format**:
```json
{
  "series": [{"name": "Time Series", "data": [1, 2, 3]}],
  "labels": ["2025-10-09 12:00:00", "2025-10-09 13:00:00"]
}
```

### 2. Bar Charts (`bar_chart`)
**Purpose**: Categorical data visualization
**Data Source**: `get_categorical_data()` from DashboardDAO
**Features**:
- Grouping by any field (default: service)
- Top 20 categories ordered by value DESC
- Category name handling for null values
**Output Format**:
```json
{
  "series": [{"name": "Service", "data": [100, 50, 25]}],
  "labels": ["api-gateway", "auth-service", "user-service"]
}
```

### 3. Metrics (`metric`)
**Purpose**: Single KPI values with trend analysis
**Data Source**: `get_metric_data()` from DashboardDAO
**Features**:
- Current vs previous period comparison
- Automatic trend calculation (up/down/stable)
- Smart value formatting (K, M suffixes)
**Output Format**:
```json
{
  "value": 1234,
  "formatted_value": "1.2K",
  "change": "+15.3%",
  "trend": "up"
}
```

### 4. Tables (`table`)
**Purpose**: Tabular data display
**Data Source**: `get_table_data()` from DashboardDAO
**Features**:
- Configurable column selection
- Dynamic filtering (eq, ne, contains)
- Proper datetime formatting
**Output Format**:
```json
{
  "headers": [{"key": "ts", "label": "Timestamp"}],
  "rows": [{"ts": "2025-10-09 12:00:00", "level": "error"}],
  "total": 100
}
```

## API Usage Examples

### 1. List All Dashboards
```bash
curl -X GET "http://localhost:7080/v1/dashboards?include_default=true&limit=50" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Customer-ID: $TENANT_ID"
```

**Response:**
```json
{
  "dashboards": [
    {
      "id": "security",
      "name": "Security Operations Center",
      "type": "security",
      "description": "Real-time security monitoring",
      "is_default": true,
      "widget_count": 5
    }
  ],
  "total": 6,
  "custom_count": 0
}
```

### 2. Get Dashboard Configuration
```bash
curl -X GET "http://localhost:7080/v1/dashboards/security" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Customer-ID: $TENANT_ID"
```

### 3. Get Dashboard Data with Time Range
```bash
curl -X GET "http://localhost:7080/v1/dashboards/security/data?start_time=2025-10-08T00:00:00Z&end_time=2025-10-10T23:59:59Z" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Customer-ID: $TENANT_ID"
```

### 4. Create Custom Dashboard
```bash
curl -X POST "http://localhost:7080/v1/dashboards" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '{
    "name": "Custom Security Dashboard",
    "description": "Real-time security monitoring",
    "widgets": [
      {
        "id": "widget-1",
        "name": "Error Rate Over Time",
        "type": "line_chart",
        "query_definition": {
          "filters": [
            {
              "field": "level",
              "operator": "eq",
              "value": "error"
            }
          ],
          "aggregations": [
            {
              "type": "count",
              "field": "*",
              "alias": "error_count"
            }
          ],
          "time_series": true,
          "time_granularity": "hour"
        },
        "position": {"x": 0, "y": 0},
        "size": {"width": 6, "height": 4}
      }
    ],
    "layout": {"columns": 12, "rows": 8},
    "tags": ["security", "monitoring"],
    "is_public": false
  }'
```

### 5. Share Dashboard
```bash
curl -X POST "http://localhost:7080/v1/dashboards/security/share" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '{
    "shared_with_email": "analyst@example.com",
    "permission_level": "view",
    "expires_at": "2025-12-31T23:59:59Z"
  }'
```

## Code Flow

### Request Processing Flow
1. **Router** (`dashboard.py`) → **Service** (`dashboard_service.py`) → **DAO** (`dashboard_dao.py`)
2. **Authentication**: Middleware validates Bearer token and X-Customer-ID
3. **Data Sources**: 
   - Custom dashboards: Database queries via DAO
   - Default dashboards: DashboardEngine definitions + real-time data generation
4. **Widget Data**: Real-time generation from `logs_raw_mt` using specialized query methods

### Multi-Tenant Isolation
- All database queries include `customer_id = %(customer_id)s` filter
- ClickHouse multi-tenant tables ensure data separation
- Service-level access controls prevent cross-tenant data access

## Common Issues & Troubleshooting

### 1. Dashboard Not Found (404)
**Error**: `Dashboard 'invalid-id' not found`
**Causes**:
- Invalid dashboard ID
- Dashboard not accessible to current tenant
- Default dashboard engine not initialized
**Solutions**:
- Verify dashboard ID exists in list response
- Check tenant permissions
- Ensure DashboardEngine is properly initialized in main app

### 2. Pydantic Model Assignment Error (500)
**Error**: `'DashboardDefinition' object does not support item assignment`
**Cause**: Attempting to modify Pydantic model objects directly
**Solution**: Convert to dict first using `model_dump()` before modification

### 3. Widget Data Generation Errors
**Common Errors**:
- `Missing columns: 'field_name' while processing query`
- `Illegal type UInt8 of first argument of function toFloat64OrZero`
- `tuple index out of range`

**Solutions**:
- Use only existing fields from `logs_raw_mt` table: `ts`, `host`, `service`, `level`, `msg`, `trace_id`, `span_id`, `attrs`, `status`, `src_ip`, `user_id`, `customer_id`, `severity_num`, `facility`
- For numeric fields (`severity_num`, `status`, `facility`): Use direct aggregation without conversion
- For string fields: Automatic conversion with `toFloat64OrZero()`
- For field selection: Ensure `include_fields` contains only existing columns

### 4. Template Placeholder Errors (400)
**Error**: `Invalid dashboard ID: template placeholder not allowed`
**Cause**: Using Postman template variables like `{{dashboard_id}}` without replacement
**Solution**: Replace with actual dashboard ID (e.g., `security`, `performance`) or valid UUID

### 5. Authentication Failures (401/403)
**Causes**:
- Invalid or expired JWT token
- Missing X-Customer-ID header
- Cross-tenant access attempt
**Solutions**:
- Refresh authentication token
- Verify X-Customer-ID header matches tenant
- Check user permissions for dashboard access

### 6. Time Range Parsing Errors
**Error**: `Invalid time range format`
**Cause**: Incorrect ISO 8601 datetime format
**Solution**: Use format `2025-10-09T00:00:00Z` for UTC timestamps

## Performance Considerations

### Query Optimization
- **Time Series Queries**: Use hourly buckets with `toStartOfHour()` for better performance
- **Categorical Queries**: Limited to top 20 results to prevent large responses
- **Metric Queries**: Previous period calculations cached for trend analysis
- **Table Queries**: Default limit of 100 rows, configurable up to 1000

### Caching Strategy
- **Query Results**: 5-minute TTL for widget data caching
- **Dashboard Definitions**: In-memory caching for default dashboards
- **Widget Data**: Real-time generation with optional caching layer

### Database Performance
- **ClickHouse Optimization**: Uses native ClickHouse functions for time aggregation
- **Multi-Tenant Indexing**: Customer ID indexes for fast tenant isolation
- **Numeric Field Handling**: Direct aggregation for numeric types avoids conversion overhead

## Security Features

### Access Control
- **JWT Authentication**: Required for all endpoints
- **Multi-Tenant Isolation**: Automatic customer_id filtering
- **Dashboard Sharing**: Permission-based sharing (view, edit, admin levels)
- **Cross-Tenant Protection**: Prevents unauthorized data access

### Data Protection
- **Tenant Isolation**: ClickHouse multi-tenant table structure
- **Share Validation**: Dashboard existence validation before sharing
- **Template Protection**: Rejects placeholder values in dashboard IDs
- **Audit Trail**: Complete logging of dashboard operations

## Integration Points

### DashboardEngine Integration
- **Default Dashboards**: 6 pre-built enterprise dashboards
- **Real-Time Data**: Live data generation from log queries
- **Widget Definitions**: Standardized widget configurations

### Query Engine Integration
- **Advanced Queries**: Uses AdvancedQueryEngine for complex filtering
- **Field Validation**: Same field validation as query endpoints
- **Aggregation Support**: Full aggregation type support (count, sum, avg, unique, etc.)

### Frontend Integration
- **Chart Libraries**: Data formatted for popular visualization libraries
- **Real-Time Updates**: WebSocket support for live dashboard updates
- **Mobile Support**: Responsive dashboard layouts

## Monitoring & Alerts

### Key Metrics to Monitor
- **Dashboard Load Times**: < 2 seconds for dashboard data
- **Widget Generation Times**: < 1 second per widget
- **Database Query Performance**: < 500ms for widget queries
- **Error Rates**: < 1% for dashboard operations
- **Cache Hit Rates**: > 70% for frequently accessed dashboards

### Alert Conditions
- High dashboard load times (> 5 seconds)
- Widget generation failures (> 5% error rate)
- Database connection timeouts
- Authentication failures spike
- Cross-tenant access attempts

## Maintenance Procedures

### Regular Maintenance
1. **Clean up expired shares**: Remove dashboard shares past expiration date
2. **Archive old custom dashboards**: Soft delete inactive dashboards
3. **Optimize widget queries**: Review and optimize slow-performing widgets
4. **Update default dashboards**: Refresh enterprise dashboard definitions

### Backup Procedures
- **Dashboard Configurations**: Regular backup of `dashboards_mt` and `dashboard_widgets_mt`
- **Share Records**: Backup of `dashboard_shares_mt` for audit compliance
- **Widget Definitions**: Version control for default dashboard configurations

## Development Guidelines

### Adding New Widget Types
1. Implement data generation method in `DashboardDAO`
2. Add widget type handling in `DashboardService._generate_widget_data()`
3. Update widget type enum in dashboard models
4. Add frontend visualization support

### Custom Aggregations
1. Add aggregation type to `AggregationType` enum
2. Implement in `QueryAggregation.to_clickhouse_sql()`
3. Add support in widget data generation methods
4. Test with both numeric and string fields

### Performance Optimization
1. Use ClickHouse-specific functions for time operations
2. Implement proper indexing for multi-tenant queries
3. Add caching layers for frequently accessed data
4. Monitor query execution times and optimize slow queries

---

**Last Updated**: October 2025  
**Version**: 1.0  
**Contact**: Logforge Development Team