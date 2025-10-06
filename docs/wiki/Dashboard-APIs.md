# Dashboard APIs

## Overview

The Dashboard APIs provide comprehensive dashboard management and data visualization capabilities. These APIs enable users to create, customize, and share interactive dashboards with real-time data from logs, metrics, and security analytics.

**Base Path**: `/v1/dashboards`  
**Total Endpoints**: 12+  
**Authentication Required**: Yes (Bearer token + X-Customer-ID header)  
**Required Roles**: Basic `user` role for viewing, `analyst` or higher for creation

## Core Dashboard Management

### 1. List Dashboards
```http
GET /v1/dashboards
```

**Description**: List all available dashboards for the customer

**Authentication**: Required

**Query Parameters**:
- `created_by` (string, optional): Filter by creator user ID
- `is_public` (boolean, optional): Filter public/private dashboards
- `include_default` (boolean, default: true): Include default dashboards
- `category` (string, optional): Filter by dashboard category
- `limit` (integer, default: 50): Maximum dashboards to return
- `offset` (integer, default: 0): Number of dashboards to skip

**Response** (200):
```json
{
  "dashboards": [
    {
      "id": "dash_001",
      "name": "Security Operations Center",
      "description": "Real-time security monitoring and incident response",
      "category": "security",
      "is_public": true,
      "is_default": true,
      "created_by": "system",
      "created_at": "2024-01-15T10:00:00Z",
      "last_modified": "2024-01-18T14:30:00Z",
      "widget_count": 8,
      "tags": ["security", "soc", "monitoring"],
      "thumbnail_url": "/thumbnails/dash_001.png"
    },
    {
      "id": "dash_002",
      "name": "Application Performance",
      "description": "APM dashboard for service monitoring",
      "category": "observability",
      "is_public": false,
      "is_default": false,
      "created_by": "user_123",
      "created_at": "2024-01-16T09:15:00Z",
      "last_modified": "2024-01-20T11:45:00Z",
      "widget_count": 6,
      "tags": ["apm", "performance", "services"]
    }
  ],
  "total": 25,
  "categories": {
    "security": 8,
    "observability": 6,
    "business": 4,
    "infrastructure": 5,
    "custom": 2
  }
}
```

**Usage Example**:
```bash
curl -X GET "http://localhost:7080/v1/dashboards?category=security&is_public=true" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: tenant_456"
```

### 2. Create Dashboard
```http
POST /v1/dashboards
```

**Description**: Create a new custom dashboard

**Authentication**: Required

**Request Body**:
```json
{
  "name": "Custom Security Dashboard",
  "description": "Custom dashboard for security team monitoring",
  "category": "security",
  "is_public": false,
  "tags": ["security", "custom", "team"],
  "layout": {
    "columns": 12,
    "rows": 8,
    "gap": 16
  },
  "settings": {
    "auto_refresh": true,
    "refresh_interval": 30,
    "theme": "dark",
    "timezone": "UTC"
  },
  "widgets": [
    {
      "id": "widget_001",
      "type": "metric_chart",
      "title": "Security Events by Severity",
      "position": {"x": 0, "y": 0, "width": 6, "height": 3},
      "config": {
        "chart_type": "bar",
        "data_source": "security_events",
        "query": {
          "filters": [
            {"field": "timestamp", "operator": "gte", "value": "now-24h"}
          ],
          "group_by": "severity",
          "metric": "count"
        }
      }
    }
  ]
}
```

**Response** (201):
```json
{
  "id": "dash_026",
  "name": "Custom Security Dashboard",
  "created_at": "2024-01-20T16:00:00Z",
  "created_by": "user_123",
  "message": "Dashboard created successfully",
  "widget_count": 1,
  "url": "/dashboards/dash_026"
}
```

### 3. Get Dashboard Configuration
```http
GET /v1/dashboards/{dashboard_id}
```

**Description**: Get dashboard configuration and metadata

**Authentication**: Required

**Path Parameters**:
- `dashboard_id` (string): Dashboard identifier

**Response** (200):
```json
{
  "id": "dash_001",
  "name": "Security Operations Center",
  "description": "Real-time security monitoring and incident response",
  "category": "security",
  "is_public": true,
  "is_default": true,
  "created_by": "system",
  "created_at": "2024-01-15T10:00:00Z",
  "last_modified": "2024-01-18T14:30:00Z",
  "tags": ["security", "soc", "monitoring"],
  "layout": {
    "columns": 12,
    "rows": 10,
    "gap": 16
  },
  "settings": {
    "auto_refresh": true,
    "refresh_interval": 30,
    "theme": "dark",
    "timezone": "UTC",
    "enable_export": true,
    "enable_alerts": true
  },
  "widgets": [
    {
      "id": "widget_001",
      "type": "metric_chart",
      "title": "Security Events by Severity",
      "position": {"x": 0, "y": 0, "width": 6, "height": 3},
      "config": {
        "chart_type": "donut",
        "data_source": "security_events",
        "query": {
          "time_range": {"last": "24h"},
          "group_by": "severity",
          "metric": "count"
        },
        "colors": {
          "critical": "#FF4444",
          "high": "#FF8800",
          "medium": "#FFBB00",
          "low": "#44AA44"
        }
      }
    },
    {
      "id": "widget_002",
      "type": "time_series",
      "title": "Events Over Time",
      "position": {"x": 6, "y": 0, "width": 6, "height": 3},
      "config": {
        "chart_type": "line",
        "data_source": "security_events",
        "query": {
          "time_range": {"last": "24h"},
          "interval": "1h",
          "metric": "count"
        }
      }
    }
  ],
  "permissions": {
    "can_edit": true,
    "can_delete": false,
    "can_share": true
  }
}
```

### 4. Update Dashboard
```http
PUT /v1/dashboards/{dashboard_id}
```

**Description**: Update existing dashboard configuration

**Authentication**: Required

**Path Parameters**:
- `dashboard_id` (string): Dashboard identifier

**Request Body**:
```json
{
  "name": "Updated Security Dashboard",
  "description": "Enhanced security monitoring with new widgets",
  "tags": ["security", "soc", "monitoring", "enhanced"],
  "settings": {
    "refresh_interval": 15,
    "theme": "light"
  }
}
```

**Response** (200):
```json
{
  "id": "dash_001",
  "name": "Updated Security Dashboard",
  "updated_at": "2024-01-20T16:15:00Z",
  "message": "Dashboard updated successfully",
  "changes": [
    "name updated",
    "description updated", 
    "tags updated",
    "refresh_interval changed from 30 to 15",
    "theme changed from dark to light"
  ]
}
```

### 5. Delete Dashboard
```http
DELETE /v1/dashboards/{dashboard_id}
```

**Description**: Delete a dashboard (only custom dashboards can be deleted)

**Authentication**: Required

**Path Parameters**:
- `dashboard_id` (string): Dashboard identifier

**Response** (200):
```json
{
  "message": "Dashboard deleted successfully",
  "dashboard_id": "dash_026",
  "deleted_at": "2024-01-20T16:30:00Z"
}
```

## Dashboard Data & Visualization

### 6. Get Dashboard Data
```http
GET /v1/dashboards/{dashboard_id}/data
```

**Description**: Get dashboard data with all widget results

**Authentication**: Required

**Path Parameters**:
- `dashboard_id` (string): Dashboard identifier

**Query Parameters**:
- `start_time` (string, optional): Start time for data range
- `end_time` (string, optional): End time for data range
- `refresh` (boolean, default: false): Force refresh cached data

**Response** (200):
```json
{
  "dashboard_id": "dash_001",
  "generated_at": "2024-01-20T16:45:00Z",
  "time_range": {
    "start": "2024-01-19T16:45:00Z",
    "end": "2024-01-20T16:45:00Z"
  },
  "widgets": [
    {
      "widget_id": "widget_001",
      "title": "Security Events by Severity",
      "type": "metric_chart",
      "status": "success",
      "data": {
        "labels": ["Critical", "High", "Medium", "Low"],
        "values": [3, 15, 78, 1157],
        "total": 1253,
        "colors": ["#FF4444", "#FF8800", "#FFBB00", "#44AA44"]
      },
      "metadata": {
        "query_time_ms": 25,
        "cache_hit": false,
        "last_updated": "2024-01-20T16:45:00Z"
      }
    },
    {
      "widget_id": "widget_002",
      "title": "Events Over Time",
      "type": "time_series",
      "status": "success",
      "data": {
        "series": [
          {
            "name": "Security Events",
            "data": [
              {"timestamp": "2024-01-20T15:00:00Z", "value": 45},
              {"timestamp": "2024-01-20T16:00:00Z", "value": 52},
              {"timestamp": "2024-01-20T17:00:00Z", "value": 38}
            ]
          }
        ]
      },
      "metadata": {
        "query_time_ms": 156,
        "cache_hit": true,
        "last_updated": "2024-01-20T16:40:00Z"
      }
    }
  ],
  "performance": {
    "total_query_time_ms": 181,
    "widgets_cached": 1,
    "widgets_fresh": 1
  }
}
```

**Usage Example**:
```bash
curl -X GET "http://localhost:7080/v1/dashboards/dash_001/data?refresh=true" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: tenant_456"
```

## Widget Management

### 7. Create Widget
```http
POST /v1/dashboards/{dashboard_id}/widgets
```

**Description**: Create a new dashboard widget

**Authentication**: Required

**Path Parameters**:
- `dashboard_id` (string): Dashboard identifier

**Request Body**:
```json
{
  "type": "table",
  "title": "Recent Security Events",
  "position": {"x": 0, "y": 6, "width": 12, "height": 4},
  "config": {
    "data_source": "security_events",
    "query": {
      "time_range": {"last": "1h"},
      "filters": [
        {"field": "severity", "operator": "in", "value": ["high", "critical"]}
      ],
      "fields": ["timestamp", "severity", "event_type", "source_ip", "description"],
      "sort": [{"field": "timestamp", "direction": "desc"}],
      "limit": 100
    },
    "columns": [
      {"field": "timestamp", "title": "Time", "width": 180, "format": "datetime"},
      {"field": "severity", "title": "Severity", "width": 100, "format": "badge"},
      {"field": "event_type", "title": "Event Type", "width": 150},
      {"field": "source_ip", "title": "Source IP", "width": 120},
      {"field": "description", "title": "Description", "width": 300}
    ],
    "pagination": {
      "enabled": true,
      "page_size": 25
    }
  }
}
```

**Response** (201):
```json
{
  "widget_id": "widget_009",
  "title": "Recent Security Events",
  "type": "table",
  "created_at": "2024-01-20T17:00:00Z",
  "message": "Widget created successfully",
  "position": {"x": 0, "y": 6, "width": 12, "height": 4}
}
```

### 8. Get Widget Data
```http
GET /v1/dashboards/{dashboard_id}/widgets/{widget_id}/data
```

**Description**: Get data for a specific dashboard widget

**Authentication**: Required

**Path Parameters**:
- `dashboard_id` (string): Dashboard identifier
- `widget_id` (string): Widget identifier

**Query Parameters**:
- `start_time` (string, optional): Start time override
- `end_time` (string, optional): End time override
- `refresh` (boolean, default: false): Force refresh

**Response** (200):
```json
{
  "widget_id": "widget_001",
  "title": "Security Events by Severity",
  "type": "metric_chart",
  "status": "success",
  "data": {
    "chart_type": "donut",
    "labels": ["Critical", "High", "Medium", "Low"],
    "datasets": [
      {
        "data": [3, 15, 78, 1157],
        "backgroundColor": ["#FF4444", "#FF8800", "#FFBB00", "#44AA44"],
        "borderWidth": 0
      }
    ],
    "total": 1253,
    "summary": {
      "critical_percent": 0.24,
      "high_percent": 1.20,
      "medium_percent": 6.22,
      "low_percent": 92.34
    }
  },
  "metadata": {
    "query": {
      "time_range": {"last": "24h"},
      "group_by": "severity",
      "metric": "count"
    },
    "execution": {
      "query_time_ms": 25,
      "rows_scanned": 125000,
      "cache_hit": false
    },
    "last_updated": "2024-01-20T17:15:00Z"
  }
}
```

### 9. Update Widget
```http
PUT /v1/dashboards/{dashboard_id}/widgets/{widget_id}
```

**Description**: Update a dashboard widget

**Authentication**: Required

**Path Parameters**:
- `dashboard_id` (string): Dashboard identifier
- `widget_id` (string): Widget identifier

**Request Body**:
```json
{
  "title": "Updated Security Events Chart",
  "position": {"x": 0, "y": 0, "width": 8, "height": 4},
  "config": {
    "chart_type": "bar",
    "query": {
      "time_range": {"last": "48h"},
      "group_by": "severity",
      "metric": "count"
    },
    "colors": {
      "critical": "#CC0000",
      "high": "#FF6600",
      "medium": "#FFAA00",
      "low": "#00AA00"
    }
  }
}
```

**Response** (200):
```json
{
  "widget_id": "widget_001",
  "title": "Updated Security Events Chart",
  "updated_at": "2024-01-20T17:30:00Z",
  "message": "Widget updated successfully",
  "changes": [
    "title updated",
    "position resized",
    "chart_type changed from donut to bar",
    "time_range extended to 48h",
    "colors updated"
  ]
}
```

### 10. Delete Widget
```http
DELETE /v1/dashboards/{dashboard_id}/widgets/{widget_id}
```

**Description**: Delete a dashboard widget

**Authentication**: Required

**Path Parameters**:
- `dashboard_id` (string): Dashboard identifier
- `widget_id` (string): Widget identifier

**Response** (200):
```json
{
  "message": "Widget deleted successfully",
  "widget_id": "widget_009",
  "dashboard_id": "dash_001",
  "deleted_at": "2024-01-20T17:45:00Z"
}
```

## Dashboard Sharing

### 11. Share Dashboard
```http
POST /v1/dashboards/{dashboard_id}/share
```

**Description**: Share dashboard with another user or make public

**Authentication**: Required

**Path Parameters**:
- `dashboard_id` (string): Dashboard identifier

**Request Body**:
```json
{
  "share_type": "user",
  "target": "user_456",
  "permissions": ["view", "comment"],
  "expires_at": "2024-02-20T00:00:00Z",
  "message": "Sharing security dashboard for incident review"
}
```

**Share Types**:
- `user`: Share with specific user
- `team`: Share with team/role
- `public`: Make publicly accessible
- `link`: Generate shareable link

**Response** (200):
```json
{
  "share_id": "share_123",
  "dashboard_id": "dash_001",
  "share_type": "user",
  "target": "user_456",
  "permissions": ["view", "comment"],
  "share_url": "/shared/dashboards/share_123",
  "expires_at": "2024-02-20T00:00:00Z",
  "created_at": "2024-01-20T18:00:00Z",
  "message": "Dashboard shared successfully"
}
```

### 12. Get Dashboard Shares
```http
GET /v1/dashboards/{dashboard_id}/shares
```

**Description**: Get dashboard sharing information

**Authentication**: Required

**Path Parameters**:
- `dashboard_id` (string): Dashboard identifier

**Response** (200):
```json
{
  "dashboard_id": "dash_001",
  "shares": [
    {
      "share_id": "share_123",
      "share_type": "user",
      "target": "user_456",
      "target_name": "John Doe",
      "permissions": ["view", "comment"],
      "created_at": "2024-01-20T18:00:00Z",
      "expires_at": "2024-02-20T00:00:00Z",
      "last_accessed": "2024-01-20T19:30:00Z",
      "access_count": 5
    },
    {
      "share_id": "share_124",
      "share_type": "team",
      "target": "security_team",
      "target_name": "Security Team",
      "permissions": ["view", "edit"],
      "created_at": "2024-01-18T14:00:00Z",
      "expires_at": null,
      "last_accessed": "2024-01-20T16:45:00Z",
      "access_count": 25
    }
  ],
  "public_access": {
    "enabled": false,
    "public_url": null
  },
  "total_shares": 2
}
```

## Widget Types & Configuration

### Chart Widget Types

| Type | Description | Use Cases |
|------|-------------|-----------|
| `line` | Line chart for time series | Trends, metrics over time |
| `bar` | Bar chart for categorical data | Comparisons, distributions |
| `pie` | Pie chart for proportions | Percentage breakdowns |
| `donut` | Donut chart (pie with center) | Proportions with total display |
| `area` | Area chart for cumulative data | Stacked metrics, volume trends |
| `scatter` | Scatter plot for correlations | Relationship analysis |
| `heatmap` | Heat map for density data | Geographic, time-based density |

### Data Widget Types

| Type | Description | Use Cases |
|------|-------------|-----------|
| `table` | Data table with sorting/filtering | Raw data display, logs |
| `metric` | Single metric display | KPIs, current values |
| `gauge` | Gauge/speedometer display | Performance indicators |
| `progress` | Progress bar | Goal tracking, completion |
| `stat` | Statistical summary | Aggregated insights |
| `text` | Rich text/markdown | Annotations, documentation |

### Specialized Widget Types

| Type | Description | Use Cases |
|------|-------------|-----------|
| `map` | Geographic map visualization | Location-based data |
| `network` | Network topology diagram | Service dependencies |
| `alert_list` | List of active alerts | Monitoring dashboards |
| `log_stream` | Live log stream | Real-time monitoring |
| `trace_view` | Distributed trace viewer | APM, debugging |

### Default Dashboard Categories

| Category | Description | Widgets |
|----------|-------------|---------|
| `security` | Security operations center | Security events, threats, incidents |
| `observability` | Application monitoring | Metrics, traces, service health |
| `infrastructure` | Infrastructure monitoring | System resources, capacity |
| `business` | Business metrics | KPIs, revenue, user activity |
| `compliance` | Compliance reporting | Audit logs, policy violations |
| `custom` | User-created dashboards | Any combination of widgets |

## Performance & Caching

### Cache Configuration

- **Widget Data**: Cached for 1-5 minutes based on data source
- **Dashboard Config**: Cached for 15 minutes
- **Real-time Widgets**: No caching for live streams
- **Historical Data**: Cached for 1 hour for time ranges > 24h

### Query Optimization

1. **Time Range Limits**: Queries limited to 30 days max
2. **Row Limits**: Table widgets limited to 10,000 rows
3. **Aggregation**: Use aggregated data for large time ranges
4. **Indexing**: Leverage indexed fields for better performance

## Error Responses

### Common Error Codes

| Status Code | Error Type | Description |
|-------------|------------|-------------|
| 400 | `invalid_widget_config` | Widget configuration is invalid |
| 400 | `invalid_time_range` | Time range parameters are invalid |
| 403 | `dashboard_access_denied` | User cannot access dashboard |
| 404 | `dashboard_not_found` | Dashboard does not exist |
| 404 | `widget_not_found` | Widget does not exist |
| 409 | `dashboard_name_conflict` | Dashboard name already exists |
| 413 | `dashboard_too_large` | Too many widgets or data points |

### Example Error Response
```json
{
  "detail": "Widget query timeout: time range too large",
  "type": "widget_query_timeout",
  "code": "WIDGET_001",
  "context": {
    "widget_id": "widget_005",
    "time_range": "90d",
    "suggestion": "Reduce time range to 30 days or less"
  }
}
```

## Best Practices

### Dashboard Design
1. **Purpose-Driven**: Design dashboards for specific use cases
2. **Visual Hierarchy**: Use size and position to emphasize important widgets
3. **Color Consistency**: Use consistent color schemes across widgets
4. **Performance**: Limit to 10-15 widgets per dashboard
5. **Responsive**: Design for different screen sizes

### Widget Configuration
1. **Appropriate Types**: Choose widget types that match data patterns
2. **Time Ranges**: Use reasonable time ranges for performance
3. **Filtering**: Add relevant filters for user interaction
4. **Labels**: Use clear, descriptive titles and labels
5. **Refresh Rates**: Balance between freshness and performance

### Sharing & Collaboration
1. **Permissions**: Use appropriate permission levels
2. **Expiration**: Set expiration dates for temporary shares
3. **Documentation**: Add descriptions and context
4. **Version Control**: Track changes to shared dashboards
5. **Access Monitoring**: Monitor dashboard access patterns

---

*See [Data APIs](./Data-APIs.md) for dashboard data sources and [Security Analytics APIs](./Security-Analytics-APIs.md) for security-focused dashboards.*