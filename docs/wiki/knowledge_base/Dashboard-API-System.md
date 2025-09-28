# Logforge Dashboard API System

## Overview

The Logforge Dashboard API provides comprehensive dashboard management capabilities for creating, managing, and displaying real-time data visualizations. Built on FastAPI with multi-tenant architecture, the system supports both custom user dashboards and pre-built enterprise templates with advanced widget management and sharing capabilities.

**Base URL**: `/v1/dashboards`  
**Authentication**: Bearer token required via `Authorization` header  
**Multi-tenant**: X-Customer-ID header required for tenant isolation

---

## Dashboard Management Endpoints

### 1. List Dashboards
**Endpoint**: `GET /v1/dashboards`

Lists all available dashboards for a customer, including both custom dashboards and default enterprise templates.

**Query Parameters**:
- `created_by` (optional): Filter by dashboard creator
- `is_public` (optional): Filter public/private dashboards
- `include_default` (optional): Include default enterprise dashboards (default: true)
- `limit` (optional): Maximum dashboards to return (default: 50, max: 100)

**Request Example**:
```bash
curl -X GET "https://api.logforge.com/v1/dashboards?include_default=true&limit=25" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>"
```

**Response Structure**:
```json
{
  "dashboards": [
    {
      "id": "security-soc",
      "name": "Security SOC Dashboard",
      "type": "security",
      "description": "Comprehensive security operations dashboard",
      "widget_count": 8,
      "tags": ["security", "siem", "enterprise"],
      "is_default": true,
      "created_by": "system"
    },
    {
      "id": "custom-dashboard-123",
      "name": "Custom Performance Dashboard",
      "description": "Application performance monitoring",
      "widget_count": 6,
      "tags": ["performance", "custom"],
      "is_default": false,
      "created_by": "user@company.com"
    }
  ],
  "total": 8,
  "custom_count": 2,
  "customer_id": "tenant-uuid",
  "filters": {
    "created_by": null,
    "is_public": null,
    "include_default": true,
    "limit": 50
  }
}
```

### 2. Get Dashboard Configuration
**Endpoint**: `GET /v1/dashboards/{dashboard_id}`

Retrieves detailed dashboard configuration including widgets, layout, and metadata.

**Path Parameters**:
- `dashboard_id`: Dashboard identifier (UUID or slug)

**Request Example**:
```bash
curl -X GET "https://api.logforge.com/v1/dashboards/security-soc" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>"
```

**Response Structure**:
```json
{
  "id": "security-soc",
  "name": "Security SOC Dashboard",
  "description": "Comprehensive security operations dashboard",
  "type": "security",
  "layout": {
    "columns": 12,
    "rows": 8,
    "grid_size": 60
  },
  "widgets": [
    {
      "id": "failed-logins",
      "title": "Failed Login Attempts",
      "type": "line_chart",
      "position": {"x": 0, "y": 0, "w": 6, "h": 4},
      "query_definition": {
        "filters": [
          {"field": "event_type", "operator": "eq", "value": "login_failed"}
        ],
        "aggregations": [
          {"type": "count", "field": "*", "group_by": ["timestamp"]}
        ],
        "time_granularity": "hour"
      },
      "refresh_interval": 30
    }
  ],
  "filters": [
    {
      "field": "timestamp",
      "operator": "gte",
      "value": "2024-01-01T00:00:00Z",
      "label": "Time Range"
    }
  ],
  "tags": ["security", "siem"],
  "is_public": true,
  "is_default": true,
  "created_by": "system",
  "customer_id": "tenant-uuid"
}
```

### 3. Get Dashboard Data
**Endpoint**: `GET /v1/dashboards/{dashboard_id}/data`

Retrieves real-time data for all dashboard widgets with optional time range filtering.

**Path Parameters**:
- `dashboard_id`: Dashboard identifier

**Query Parameters**:
- `start_time` (optional): ISO 8601 start time for data range
- `end_time` (optional): ISO 8601 end time for data range

**Request Example**:
```bash
curl -X GET "https://api.logforge.com/v1/dashboards/security-soc/data?start_time=2024-01-01T00:00:00Z&end_time=2024-01-01T23:59:59Z" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>"
```

**Response Structure**:
```json
{
  "dashboard_id": "security-soc",
  "generated_at": "2024-01-01T12:00:00Z",
  "widgets": {
    "failed-logins": {
      "title": "Failed Login Attempts",
      "type": "line_chart",
      "data": {
        "series": [
          {
            "name": "Failed Logins",
            "data": [12, 18, 22, 15, 28, 35, 19]
          }
        ],
        "labels": ["06:00", "09:00", "12:00", "15:00", "18:00", "21:00", "00:00"],
        "total_events": 149
      },
      "execution_time_ms": 245,
      "last_updated": "2024-01-01T12:00:00Z"
    },
    "security-events": {
      "title": "Security Events by Type",
      "type": "pie_chart",
      "data": {
        "series": [45, 32, 28, 15, 8],
        "labels": ["Brute Force", "Malware", "Phishing", "DDoS", "Other"],
        "total": 128
      },
      "execution_time_ms": 189,
      "last_updated": "2024-01-01T12:00:00Z"
    }
  },
  "metadata": {
    "time_range": {
      "start_time": "2024-01-01T00:00:00Z",
      "end_time": "2024-01-01T23:59:59Z"
    },
    "total_widgets": 8,
    "dashboard_name": "Security SOC Dashboard"
  }
}
```

### 4. Create Custom Dashboard
**Endpoint**: `POST /v1/dashboards`

Creates a new custom dashboard with specified configuration and widgets.

**Request Body**:
```json
{
  "name": "Custom Performance Dashboard",
  "description": "Application performance monitoring dashboard",
  "widgets": [
    {
      "name": "Response Time Trends",
      "type": "line_chart",
      "query_definition": {
        "filters": [
          {"field": "service", "operator": "eq", "value": "api-service"}
        ],
        "aggregations": [
          {"type": "avg", "field": "response_time_ms", "group_by": ["timestamp"]}
        ]
      },
      "position": {"x": 0, "y": 0, "w": 6, "h": 4},
      "refresh_interval": 60
    }
  ],
  "layout": {
    "columns": 12,
    "rows": 6
  },
  "filters": [
    {
      "field": "service",
      "operator": "in",
      "value": ["api-service", "web-service"],
      "label": "Services"
    }
  ],
  "tags": ["performance", "api"],
  "is_public": false
}
```

**Response Structure**:
```json
{
  "status": "created",
  "dashboard_id": "dashboard-uuid-123",
  "message": "Dashboard created successfully",
  "customer_id": "tenant-uuid"
}
```

### 5. Update Dashboard
**Endpoint**: `PUT /v1/dashboards/{dashboard_id}`

Updates an existing custom dashboard configuration.

**Path Parameters**:
- `dashboard_id`: Dashboard identifier

**Request Body**: Same structure as create dashboard

**Response Structure**:
```json
{
  "status": "updated",
  "dashboard_id": "dashboard-uuid-123",
  "message": "Dashboard updated successfully",
  "customer_id": "tenant-uuid"
}
```

### 6. Delete Dashboard
**Endpoint**: `DELETE /v1/dashboards/{dashboard_id}`

Deletes a custom dashboard (default dashboards cannot be deleted).

**Path Parameters**:
- `dashboard_id`: Dashboard identifier

**Response Structure**:
```json
{
  "status": "deleted",
  "dashboard_id": "dashboard-uuid-123",
  "message": "Dashboard deleted successfully",
  "customer_id": "tenant-uuid"
}
```

---

## Widget Management Endpoints

### 7. Get Widget Data
**Endpoint**: `GET /v1/dashboards/{dashboard_id}/widgets/{widget_id}/data`

Retrieves real-time data for a specific dashboard widget.

**Path Parameters**:
- `dashboard_id`: Dashboard identifier
- `widget_id`: Widget identifier

**Response Structure**:
```json
{
  "dashboard_id": "security-soc",
  "widget_id": "failed-logins",
  "data": {
    "series": [
      {
        "name": "Failed Logins",
        "data": [12, 18, 22, 15, 28, 35, 19]
      }
    ],
    "labels": ["06:00", "09:00", "12:00", "15:00", "18:00", "21:00", "00:00"],
    "query_definition": {
      "filters": [{"field": "event_type", "operator": "eq", "value": "login_failed"}]
    }
  },
  "customer_id": "tenant-uuid"
}
```

### 8. Create Widget
**Endpoint**: `POST /v1/dashboards/{dashboard_id}/widgets`

Adds a new widget to an existing dashboard.

**Path Parameters**:
- `dashboard_id`: Dashboard identifier

**Request Body**:
```json
{
  "name": "Error Rate Metric",
  "type": "metric",
  "query_definition": {
    "filters": [{"field": "level", "operator": "eq", "value": "ERROR"}],
    "aggregations": [{"type": "count", "field": "*"}]
  },
  "visualization_config": {
    "color": "red",
    "unit": "errors/min"
  },
  "position": {"x": 6, "y": 0, "w": 3, "h": 2},
  "size": {"width": 300, "height": 200},
  "refresh_interval": 30
}
```

**Response Structure**:
```json
{
  "status": "created",
  "widget_id": "widget-uuid-456",
  "message": "Widget created successfully",
  "dashboard_id": "dashboard-uuid-123"
}
```

### 9. Update Widget
**Endpoint**: `PUT /v1/dashboards/{dashboard_id}/widgets/{widget_id}`

Updates an existing dashboard widget configuration.

**Path Parameters**:
- `dashboard_id`: Dashboard identifier
- `widget_id`: Widget identifier

**Request Body**: Same structure as create widget

**Response Structure**:
```json
{
  "status": "updated",
  "widget_id": "widget-uuid-456",
  "message": "Widget updated successfully",
  "customer_id": "tenant-uuid"
}
```

### 10. Delete Widget
**Endpoint**: `DELETE /v1/dashboards/{dashboard_id}/widgets/{widget_id}`

Removes a widget from a dashboard.

**Path Parameters**:
- `dashboard_id`: Dashboard identifier
- `widget_id`: Widget identifier

**Response Structure**:
```json
{
  "status": "deleted",
  "widget_id": "widget-uuid-456",
  "message": "Widget deleted successfully",
  "customer_id": "tenant-uuid"
}
```

---

## Dashboard Sharing Endpoints

### 11. Share Dashboard
**Endpoint**: `POST /v1/dashboards/{dashboard_id}/share`

Shares a dashboard with another user or tenant with specified permissions.

**Path Parameters**:
- `dashboard_id`: Dashboard identifier

**Request Body**:
```json
{
  "shared_with_email": "analyst@company.com",
  "permission_level": "view",
  "expires_at": "2024-12-31T23:59:59Z",
  "created_by": "admin@company.com"
}
```

**Permission Levels**:
- `view`: Read-only access to dashboard and data
- `edit`: Can modify dashboard configuration and widgets
- `admin`: Full access including sharing permissions

**Response Structure**:
```json
{
  "status": "shared",
  "share_id": "share-uuid-789",
  "message": "Dashboard shared successfully",
  "dashboard_id": "dashboard-uuid-123"
}
```

### 12. Get Dashboard Shares
**Endpoint**: `GET /v1/dashboards/{dashboard_id}/shares`

Retrieves information about who has access to a dashboard.

**Path Parameters**:
- `dashboard_id`: Dashboard identifier

**Response Structure**:
```json
{
  "dashboard_id": "dashboard-uuid-123",
  "shares": [
    {
      "share_id": "share-uuid-789",
      "shared_with_email": "analyst@company.com",
      "permission_level": "view",
      "expires_at": "2024-12-31T23:59:59Z",
      "created_by": "admin@company.com",
      "created_at": "2024-01-01T10:00:00Z",
      "status": "active"
    }
  ],
  "total": 1,
  "customer_id": "tenant-uuid"
}
```

---

## Enterprise Default Dashboards

The Dashboard API includes 6 pre-built enterprise dashboards available to all customers:

### 1. Security SOC Dashboard (`security-soc`)
**Focus**: Security operations center monitoring
**Widgets**: 8 security-focused visualizations
- Failed login attempts (line chart)
- Security events by type (pie chart)  
- Top attacked IPs (table)
- MITRE ATT&CK techniques (heatmap)
- Alert severity distribution (bar chart)
- Security event timeline (timeline)
- Threat intelligence matches (metric)
- Incident response status (gauge)

### 2. Performance Dashboard (`performance`)  
**Focus**: Application and system performance metrics
**Widgets**: 6 performance visualizations
- Response time trends (line chart)
- Throughput metrics (area chart)
- Error rate by service (bar chart)
- Resource utilization (gauge cluster)
- Top slow queries (table)
- Performance SLA status (metric)

### 3. Infrastructure Dashboard (`infrastructure`)
**Focus**: System health and resource monitoring  
**Widgets**: 7 infrastructure visualizations
- CPU utilization (line chart)
- Memory usage patterns (stacked area)
- Disk I/O metrics (multi-line chart)
- Network traffic (area chart)
- Service health status (status grid)
- Container resource usage (heat map)
- Infrastructure alerts (table)

### 4. Business Dashboard (`business`)
**Focus**: Business metrics and KPIs
**Widgets**: 5 business-oriented visualizations  
- User activity trends (line chart)
- Revenue metrics (bar chart)
- Feature adoption rates (funnel chart)
- Geographic usage distribution (map)
- Business KPI summary (metric cluster)

### 5. Compliance Dashboard (`compliance`)
**Focus**: Regulatory compliance monitoring
**Widgets**: 6 compliance visualizations
- Audit trail events (table)
- Compliance score trends (gauge)
- Data retention status (stacked bar)
- Access control violations (timeline)
- Regulatory reporting status (status grid)
- Compliance alerts (alert list)

### 6. Executive Dashboard (`executive`)
**Focus**: High-level executive summary
**Widgets**: 4 executive-level visualizations
- Platform health summary (scorecard)
- Cost optimization metrics (trend chart)
- Security posture overview (gauge cluster)
- Key business metrics (KPI grid)

---

## Data Models

### Dashboard Widget Types

**Supported Visualization Types**:
- `line_chart`: Time-series line charts for trending data
- `bar_chart`: Categorical data comparison
- `pie_chart`: Proportional data representation  
- `table`: Tabular data display with sorting/pagination
- `metric`: Single value KPI displays with trends
- `heatmap`: Matrix data visualization
- `map`: Geographic data visualization

### Query Definition Structure

Dashboard widgets use the advanced query engine with the following structure:

```json
{
  "query_definition": {
    "filters": [
      {
        "field": "level",
        "operator": "eq|ne|gt|gte|lt|lte|contains|starts_with|ends_with|regex|in|not_in",
        "value": "ERROR"
      }
    ],
    "aggregations": [
      {
        "type": "count|sum|avg|min|max|distinct_count",
        "field": "response_time_ms",
        "group_by": ["service", "timestamp"]
      }
    ],
    "time_granularity": "minute|hour|day|week|month",
    "limit": 1000,
    "sort": [{"field": "timestamp", "direction": "desc"}]
  }
}
```

---

## Authentication & Authorization

### Required Headers
All dashboard API endpoints require:
- `Authorization: Bearer <jwt-token>`
- `X-Customer-ID: <tenant-uuid>` (for multi-tenant isolation)

### Permission Requirements
- **Dashboard CRUD**: Requires `dashboards.*` subscription feature  
- **Widget Management**: Requires `dashboards.*` and `queries.*` features
- **Data Access**: Requires appropriate data access permissions based on query scope
- **Sharing**: Requires dashboard ownership or admin permissions

### Subscription Features
The Dashboard API requires the following subscription features:
- `dashboards.*` - Core dashboard management functionality
- `queries.*` - Widget data querying capabilities  
- `ingestion.*` - Access to ingested log data
- `alerts.*` - Dashboard widgets showing alert data
- `security.*` - Security dashboard features

---

## Error Handling

### Common Error Responses

**404 - Dashboard Not Found**:
```json
{
  "error": "not_found",
  "message": "Dashboard not found",
  "dashboard_id": "invalid-id"
}
```

**400 - Invalid Request**:
```json
{
  "error": "validation_error", 
  "message": "Dashboard layout must be a dictionary",
  "field": "layout"
}
```

**403 - Insufficient Permissions**:
```json
{
  "error": "insufficient_permissions",
  "message": "Dashboard modification requires edit permissions",
  "required_permission": "dashboard:edit"
}
```

**403 - Subscription Required**:
```json
{
  "error": "subscription_not_found",
  "message": "No subscription found",
  "required_feature": "dashboards.*",
  "current_subscription": ["ingestion.*"],
  "upgrade_url": "/v1/tenants/{tenant_id}/subscription/upgrade"
}
```

**500 - Server Error**:
```json
{
  "error": "internal_error",
  "message": "Failed to generate dashboard data: Query execution timeout"
}
```

---

## Performance Optimization

### Caching Strategy
- **Dashboard Definitions**: Cached for 5 minutes (default dashboards)
- **Widget Data**: Cached based on refresh_interval (30-300 seconds)
- **Query Results**: Intelligent caching based on query complexity and data freshness

### Query Performance
- **Time Range Optimization**: Automatic query optimization for large time ranges
- **Data Sampling**: Intelligent sampling for high-cardinality data
- **Parallel Execution**: Widget queries executed in parallel for faster dashboard loading
- **Incremental Updates**: Support for incremental data updates on real-time dashboards

### Scalability Features  
- **Lazy Loading**: Widgets loaded on-demand for large dashboards
- **Progressive Enhancement**: Basic data loaded first, detailed data loaded progressively
- **Auto-scaling**: Query engine automatically scales based on dashboard load
- **Resource Limits**: Configurable limits to prevent resource exhaustion

---

## Best Practices

### Dashboard Design
1. **Widget Limit**: Recommended maximum of 12 widgets per dashboard
2. **Refresh Intervals**: Balance between data freshness and system load
3. **Query Optimization**: Use appropriate aggregations and time ranges
4. **Layout Planning**: Use 12-column grid system for responsive design

### Security Considerations
1. **Data Access**: Ensure widgets only query authorized data sources
2. **Sharing Controls**: Use appropriate permission levels when sharing dashboards
3. **Query Validation**: Validate all query parameters to prevent injection attacks
4. **Audit Trail**: Monitor dashboard access and modifications

### Performance Guidelines
1. **Time Range Limits**: Avoid queries spanning more than 90 days without aggregation
2. **Aggregation Usage**: Use aggregations for large datasets instead of raw data
3. **Concurrent Limits**: Limit concurrent dashboard refreshes per customer
4. **Resource Monitoring**: Monitor dashboard performance impact

---

## Integration Examples

### Real-time Dashboard Updates
```javascript
// WebSocket connection for real-time dashboard updates
const ws = new WebSocket('wss://api.logforge.com/v1/dashboards/ws');
ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  if (update.type === 'widget_data') {
    updateWidget(update.widget_id, update.data);
  }
};
```

### Custom Widget Development
```javascript
// Custom widget query execution
const executeWidgetQuery = async (widgetId, timeRange) => {
  const response = await fetch(
    `/v1/dashboards/custom-dashboard/widgets/${widgetId}/data?` +
    `start_time=${timeRange.start}&end_time=${timeRange.end}`,
    {
      headers: {
        'Authorization': 'Bearer ' + token,
        'X-Customer-ID': tenantId
      }
    }
  );
  return response.json();
};
```

### Dashboard Automation
```bash
# Automated dashboard export for reporting
curl -X GET "https://api.logforge.com/v1/dashboards/executive/data" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  | jq '.widgets | to_entries | map({widget: .key, data: .value.data})' \
  > executive-report.json
```

---

## API Reference Summary

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/v1/dashboards` | GET | List dashboards | ✓ |
| `/v1/dashboards` | POST | Create dashboard | ✓ |  
| `/v1/dashboards/{id}` | GET | Get dashboard config | ✓ |
| `/v1/dashboards/{id}` | PUT | Update dashboard | ✓ |
| `/v1/dashboards/{id}` | DELETE | Delete dashboard | ✓ |
| `/v1/dashboards/{id}/data` | GET | Get dashboard data | ✓ |
| `/v1/dashboards/{id}/widgets/{wid}/data` | GET | Get widget data | ✓ |
| `/v1/dashboards/{id}/widgets` | POST | Create widget | ✓ |
| `/v1/dashboards/{id}/widgets/{wid}` | PUT | Update widget | ✓ |
| `/v1/dashboards/{id}/widgets/{wid}` | DELETE | Delete widget | ✓ |
| `/v1/dashboards/{id}/share` | POST | Share dashboard | ✓ |
| `/v1/dashboards/{id}/shares` | GET | Get dashboard shares | ✓ |

**Total Endpoints**: 12  
**Enterprise Dashboards**: 6 pre-built templates  
**Widget Types**: 7 visualization types supported  
**Multi-tenant**: Full tenant isolation enforced