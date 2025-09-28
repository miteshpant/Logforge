# Dashboard Router API - Developer Documentation

## Overview

The Dashboard Router API (`/v1/dashboards`) provides comprehensive dashboard management capabilities for the Logforge platform. This system enables creation of custom dashboards, widget management, data visualization, and sharing functionality with real-time data integration from the advanced query engine.

**Location**: `/apps/api/routers/dashboard.py`  
**Service Layer**: `/apps/api/services/dashboard_service.py`  
**Data Layer**: `/apps/api/dao/dashboard_dao.py`  
**Engine**: `/apps/api/dashboard_engine.py` (6 pre-built enterprise dashboards)  
**Authentication**: Required for all endpoints  
**Multi-Tenancy**: `X-Customer-ID` header required for all endpoints  
**Subscription**: Requires `dashboards.*` or `queries.*` features in subscription

## Architecture & Components

### System Architecture
```
FastAPI Router → DashboardService → DashboardDAO → ClickHouse Database
     ↓              ↓                 ↓              ↓
Middleware     Business Logic    Database Ops   Multi-tenant Storage
Validation     Widget Engine     Query Execution Dashboard Persistence
Real-time      Dashboard Engine  Data Generation  Share Management
```

### Core Components

1. **Dashboard Router** (`dashboard.py`): HTTP endpoint definitions and request/response handling
2. **Dashboard Service** (`dashboard_service.py`): Business logic, validation, and data orchestration  
3. **Dashboard DAO** (`dashboard_dao.py`): Database operations and persistence management
4. **Dashboard Engine** (`dashboard_engine.py`): 6 pre-built enterprise dashboards with real-time data
5. **Query Engine Integration**: Advanced query capabilities for custom widgets
6. **Multi-Tenant Storage**: Secure dashboard isolation by customer ID

### Dashboard Types

**Pre-built Enterprise Dashboards**:
1. **Security Operations Center** (`security`): Real-time security monitoring and threat detection
2. **Performance Monitoring** (`performance`): Application performance metrics and response times
3. **Infrastructure Overview** (`infrastructure`): System health and resource utilization
4. **Business Intelligence** (`business`): User behavior and business metrics analysis
5. **Compliance & Audit** (`compliance`): Audit trails and compliance monitoring
6. **Executive Overview** (`executive`): High-level KPIs for executive decision making

**Custom Dashboard Features**:
- **Widget Types**: Line charts, bar charts, pie charts, tables, metrics, heatmaps
- **Real-time Data**: Live data integration with configurable refresh intervals
- **Advanced Filtering**: Time range, field filters, and aggregation support
- **Layout Management**: Flexible grid-based layouts with drag-and-drop positioning
- **Sharing**: Multi-tenant sharing with granular permission control

### Database Schema

**Dashboards Table**: `dashboards_mt`
```sql
CREATE TABLE dashboards_mt (
    id String,
    customer_id String,
    name String,
    description String,
    layout String,  -- JSON: grid layout configuration
    filters String,  -- JSON: dashboard-level filters
    tags String,  -- JSON: array of tags
    is_public UInt8,
    is_default UInt8,
    created_by String,
    created_at DateTime64(3),
    updated_at DateTime64(3),
    status String
) ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY customer_id
ORDER BY (customer_id, id);
```

**Dashboard Widgets Table**: `dashboard_widgets_mt`
```sql
CREATE TABLE dashboard_widgets_mt (
    id String,
    dashboard_id String,
    customer_id String,
    name String,
    type String,  -- chart, table, metric, etc.
    query_definition String,  -- JSON: query configuration
    visualization_config String,  -- JSON: chart configuration
    position String,  -- JSON: grid position {x, y, w, h}
    size String,  -- JSON: widget dimensions
    refresh_interval UInt32,  -- seconds
    created_at DateTime64(3),
    updated_at DateTime64(3),
    status String
) ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY customer_id
ORDER BY (customer_id, id);
```

**Dashboard Shares Table**: `dashboard_shares_mt`
```sql
CREATE TABLE dashboard_shares_mt (
    id String,
    dashboard_id String,
    customer_id String,
    shared_with_email Nullable(String),
    shared_with_tenant Nullable(String),
    permission_level String,  -- view, edit, admin
    expires_at Nullable(DateTime64(3)),
    created_by String,
    created_at DateTime64(3),
    status String
) ENGINE = ReplacingMergeTree(created_at)
PARTITION BY customer_id
ORDER BY (customer_id, id);
```

## API Endpoints (12 Total)

### 1. Dashboard Management (6 endpoints)

#### **GET /v1/dashboards** - List Dashboards
List all available dashboards including pre-built and custom dashboards.

**Authentication**: Required (Bearer token)

**Query Parameters**:
- `created_by` (str): Filter by creator (optional)
- `is_public` (bool): Filter public/private dashboards (optional)
- `include_default` (bool): Include pre-built dashboards (default: true)
- `limit` (int): Maximum dashboards to return (default: 50, max: 100)

**Response**: (200 OK)
```json
{
  "dashboards": [
    {
      "id": "security",
      "name": "Security Operations Center",
      "type": "security",
      "description": "Real-time security monitoring, threat detection, and incident response",
      "widget_count": 5,
      "tags": ["security", "soc", "alerts", "threats"],
      "is_default": true,
      "customer_id": "tenant-uuid-123",
      "created_by": "system",
      "created_at": "2024-01-01T12:00:00Z",
      "updated_at": "2024-01-01T12:00:00Z"
    },
    {
      "id": "dashboard_abc123def456",
      "name": "Custom Application Dashboard",
      "description": "Custom dashboard for application monitoring",
      "layout": {"columns": 12, "rows": 8},
      "filters": [
        {"field": "service", "operator": "eq", "value": "my-service"}
      ],
      "tags": ["custom", "application"],
      "is_public": false,
      "is_default": false,
      "customer_id": "tenant-uuid-123",
      "created_by": "user_123",
      "created_at": "2024-01-01T14:00:00Z",
      "updated_at": "2024-01-01T15:30:00Z"
    }
  ],
  "total": 7,
  "custom_count": 1,
  "customer_id": "tenant-uuid-123",
  "filters": {
    "created_by": null,
    "is_public": null,
    "include_default": true,
    "limit": 50
  }
}
```

#### **GET /v1/dashboards/{dashboard_id}** - Get Dashboard Configuration
Retrieve dashboard configuration and metadata.

**Authentication**: Required (Bearer token)

**Response**: (200 OK)
```json
{
  "id": "security",
  "name": "Security Operations Center",
  "type": "security",
  "description": "Real-time security monitoring, threat detection, and incident response",
  "layout": {"columns": 12, "rows": 12},
  "filters": [],
  "tags": ["security", "soc", "alerts", "threats"],
  "is_public": true,
  "is_default": true,
  "widgets": [
    {
      "id": "security_alerts_count",
      "title": "Security Alerts (24h)",
      "type": "metric",
      "query_definition": {
        "start_time": "2024-01-01T12:00:00Z",
        "end_time": "2024-01-02T12:00:00Z",
        "aggregations": [{"type": "count", "field": "*"}],
        "filters": [{"field": "level", "operator": "in", "value": ["error", "critical", "alert"]}]
      },
      "visualization_config": {
        "color": "#ef4444",
        "format": "number",
        "threshold": 100
      },
      "position": {"x": 0, "y": 0, "w": 3, "h": 2},
      "size": {"width": 250, "height": 150},
      "refresh_interval": 30
    }
  ],
  "customer_id": "tenant-uuid-123",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z"
}
```

#### **GET /v1/dashboards/{dashboard_id}/data** - Get Dashboard Data
Retrieve dashboard data with all widget results and real-time values.

**Authentication**: Required (Bearer token)

**Query Parameters**:
- `start_time` (str): Start time for data range (ISO 8601)
- `end_time` (str): End time for data range (ISO 8601)

**Response**: (200 OK)
```json
{
  "dashboard_id": "security",
  "generated_at": "2024-01-01T16:00:00Z",
  "widgets": {
    "security_alerts_count": {
      "title": "Security Alerts (24h)",
      "type": "metric",
      "data": {
        "value": 23,
        "formatted_value": "23",
        "change": "+15%",
        "trend": "increasing"
      },
      "execution_time_ms": 45,
      "last_updated": "2024-01-01T16:00:00Z"
    },
    "failed_logins": {
      "title": "Failed Login Attempts",
      "type": "line_chart",
      "data": {
        "series": [{
          "name": "Failed Logins",
          "data": [
            {"x": "2024-01-01T12:00:00Z", "y": 5},
            {"x": "2024-01-01T13:00:00Z", "y": 8},
            {"x": "2024-01-01T14:00:00Z", "y": 12},
            {"x": "2024-01-01T15:00:00Z", "y": 6}
          ]
        }]
      },
      "execution_time_ms": 120,
      "last_updated": "2024-01-01T16:00:00Z"
    },
    "top_attack_ips": {
      "title": "Top Attack Source IPs",
      "type": "bar_chart",
      "data": {
        "categories": ["192.168.1.100", "10.0.1.50", "172.16.0.25"],
        "series": [{
          "name": "Attack Count",
          "data": [15, 8, 5]
        }]
      },
      "execution_time_ms": 85,
      "last_updated": "2024-01-01T16:00:00Z"
    }
  },
  "metadata": {
    "time_range": {
      "start_time": "2024-01-01T12:00:00Z", 
      "end_time": "2024-01-01T16:00:00Z"
    },
    "total_widgets": 5,
    "dashboard_name": "Security Operations Center"
  }
}
```

#### **POST /v1/dashboards** - Create Dashboard
Create a new custom dashboard with widgets and configuration.

**Authentication**: Required (Bearer token)

**Request Model**: `DashboardRequest`
```json
{
  "name": "Custom Application Dashboard",
  "description": "Monitoring dashboard for my application services",
  "widgets": [
    {
      "name": "Error Rate",
      "type": "metric",
      "query_definition": {
        "aggregations": [{"type": "count", "field": "*"}],
        "filters": [
          {"field": "level", "operator": "eq", "value": "error"},
          {"field": "service", "operator": "eq", "value": "my-service"}
        ]
      },
      "visualization_config": {
        "color": "#ef4444",
        "format": "percentage",
        "threshold": 5
      },
      "position": {"x": 0, "y": 0},
      "size": {"width": 6, "height": 4},
      "refresh_interval": 60
    }
  ],
  "layout": {"columns": 12, "rows": 8},
  "filters": [
    {"field": "environment", "operator": "eq", "value": "production"}
  ],
  "tags": ["custom", "application", "monitoring"],
  "is_public": false
}
```

**Response**: (201 Created)
```json
{
  "status": "created",
  "dashboard_id": "dashboard_abc123def456",
  "message": "Dashboard created successfully",
  "customer_id": "tenant-uuid-123"
}
```

#### **PUT /v1/dashboards/{dashboard_id}** - Update Dashboard
Update existing dashboard configuration and metadata.

**Authentication**: Required (Bearer token)

**Request Model**: `DashboardRequest`
```json
{
  "name": "Updated Dashboard Name",
  "description": "Updated description with new widgets",
  "layout": {"columns": 12, "rows": 10},
  "tags": ["updated", "application", "monitoring", "v2"],
  "is_public": true
}
```

**Response**: (200 OK)
```json
{
  "status": "updated",
  "dashboard_id": "dashboard_abc123def456",
  "message": "Dashboard updated successfully",
  "customer_id": "tenant-uuid-123"
}
```

#### **DELETE /v1/dashboards/{dashboard_id}** - Delete Dashboard
Delete (deactivate) a custom dashboard and all its widgets.

**Authentication**: Required (Bearer token)

**Response**: (200 OK)
```json
{
  "status": "deleted",
  "dashboard_id": "dashboard_abc123def456",
  "message": "Dashboard deleted successfully",
  "customer_id": "tenant-uuid-123"
}
```

### 2. Widget Management (4 endpoints)

#### **GET /v1/dashboards/{dashboard_id}/widgets/{widget_id}/data** - Get Widget Data
Retrieve data for a specific dashboard widget with real-time values.

**Authentication**: Required (Bearer token)

**Response**: (200 OK)
```json
{
  "dashboard_id": "security",
  "widget_id": "security_alerts_count",
  "data": {
    "value": 23,
    "formatted_value": "23 alerts",
    "change": "+15%",
    "trend": "increasing",
    "previous_value": 20,
    "threshold_status": "warning"
  },
  "customer_id": "tenant-uuid-123"
}
```

#### **POST /v1/dashboards/{dashboard_id}/widgets** - Create Widget
Add a new widget to an existing dashboard.

**Authentication**: Required (Bearer token)

**Request Model**: `WidgetRequest`
```json
{
  "name": "Response Time Trend",
  "type": "line_chart",
  "query_definition": {
    "aggregations": [{"type": "avg", "field": "response_time"}],
    "filters": [{"field": "service", "operator": "eq", "value": "api-gateway"}],
    "time_series": true,
    "time_granularity": "hour"
  },
  "visualization_config": {
    "colors": ["#3b82f6"],
    "y_axis_label": "Response Time (ms)",
    "show_legend": true
  },
  "position": {"x": 6, "y": 0},
  "size": {"width": 6, "height": 4},
  "refresh_interval": 300
}
```

**Response**: (201 Created)
```json
{
  "status": "created",
  "widget_id": "widget_xyz789abc123",
  "message": "Widget created successfully",
  "dashboard_id": "dashboard_abc123def456"
}
```

#### **PUT /v1/dashboards/{dashboard_id}/widgets/{widget_id}** - Update Widget
Update widget configuration, query, or visualization settings.

**Authentication**: Required (Bearer token)

**Request Model**: `WidgetRequest`
```json
{
  "name": "Updated Response Time Trend",
  "query_definition": {
    "aggregations": [{"type": "avg", "field": "response_time"}],
    "filters": [
      {"field": "service", "operator": "eq", "value": "api-gateway"},
      {"field": "environment", "operator": "eq", "value": "production"}
    ],
    "time_series": true,
    "time_granularity": "minute"
  },
  "refresh_interval": 120
}
```

**Response**: (200 OK)
```json
{
  "status": "updated",
  "widget_id": "widget_xyz789abc123",
  "message": "Widget updated successfully",
  "customer_id": "tenant-uuid-123"
}
```

#### **DELETE /v1/dashboards/{dashboard_id}/widgets/{widget_id}** - Delete Widget
Remove a widget from the dashboard.

**Authentication**: Required (Bearer token)

**Response**: (200 OK)
```json
{
  "status": "deleted",
  "widget_id": "widget_xyz789abc123",
  "message": "Widget deleted successfully",
  "customer_id": "tenant-uuid-123"
}
```

### 3. Dashboard Sharing (2 endpoints)

#### **POST /v1/dashboards/{dashboard_id}/share** - Share Dashboard
Share dashboard with another user or tenant with specific permissions.

**Authentication**: Required (Bearer token)

**Request Model**: `ShareRequest`
```json
{
  "shared_with_email": "analyst@company.com",
  "permission_level": "view",
  "expires_at": "2024-02-01T12:00:00Z",
  "created_by": "user_123"
}
```

**Permission Levels**:
- `view`: Read-only access to dashboard and data
- `edit`: Can modify widgets and configuration
- `admin`: Full control including sharing management

**Alternative Tenant Sharing**:
```json
{
  "shared_with_tenant": "partner-tenant-uuid-456",
  "permission_level": "view",
  "expires_at": "2024-06-01T12:00:00Z"
}
```

**Response**: (200 OK)
```json
{
  "status": "shared",
  "share_id": "share_def456ghi789",
  "message": "Dashboard shared successfully",
  "dashboard_id": "dashboard_abc123def456"
}
```

#### **GET /v1/dashboards/{dashboard_id}/shares** - Get Dashboard Shares
Retrieve dashboard sharing information and permissions.

**Authentication**: Required (Bearer token)

**Response**: (200 OK)
```json
{
  "dashboard_id": "dashboard_abc123def456",
  "shares": [
    {
      "id": "share_def456ghi789",
      "shared_with_email": "analyst@company.com",
      "shared_with_tenant": null,
      "permission_level": "view",
      "expires_at": "2024-02-01T12:00:00Z",
      "created_by": "user_123",
      "created_at": "2024-01-01T14:00:00Z",
      "status": "active"
    },
    {
      "id": "share_ghi789jkl012",
      "shared_with_email": null,
      "shared_with_tenant": "partner-tenant-uuid-456",
      "permission_level": "view",
      "expires_at": "2024-06-01T12:00:00Z",
      "created_by": "user_123",
      "created_at": "2024-01-01T15:00:00Z",
      "status": "active"
    }
  ],
  "total": 2,
  "customer_id": "tenant-uuid-123"
}
```

## Data Models & Validation

### Core Request Models

#### DashboardRequest
```python
class DashboardRequest(BaseModel):
    name: str = Field(..., description="Dashboard name")
    description: str = Field("", description="Dashboard description")
    widgets: List[Dict[str, Any]] = Field(default=[], description="Dashboard widgets")
    layout: Dict[str, Any] = Field(default={}, description="Grid layout configuration")
    filters: List[Dict[str, Any]] = Field(default=[], description="Dashboard-level filters")
    tags: List[str] = Field(default=[], description="Dashboard tags")
    is_public: bool = Field(False, description="Public visibility flag")
```

#### WidgetRequest
```python
class WidgetRequest(BaseModel):
    name: str = Field(..., description="Widget name")
    type: str = Field(..., description="Widget type")
    query_definition: Dict[str, Any] = Field(default={}, description="Query configuration")
    visualization_config: Dict[str, Any] = Field(default={}, description="Chart configuration")
    position: Dict[str, Any] = Field(default={}, description="Grid position")
    size: Dict[str, Any] = Field(default={}, description="Widget dimensions")
    refresh_interval: int = Field(300, description="Refresh interval in seconds")
```

#### ShareRequest
```python
class ShareRequest(BaseModel):
    shared_with_email: Optional[str] = Field(None, description="Shared user email")
    shared_with_tenant: Optional[str] = Field(None, description="Shared tenant ID")
    permission_level: str = Field("view", description="Permission level")
    expires_at: Optional[str] = Field(None, description="Share expiration time")
    created_by: str = Field("system", description="Share creator")
```

### Widget Types & Configuration

#### Supported Widget Types
- `metric`: Single value displays with trend indicators
- `line_chart`: Time series line charts with multiple series support
- `bar_chart`: Categorical bar charts with grouping capabilities
- `pie_chart`: Pie/donut charts for categorical data distribution
- `table`: Tabular data display with sorting and pagination
- `heatmap`: Heat map visualizations for correlation analysis

#### Query Definition Structure
```json
{
  "aggregations": [
    {"type": "count|sum|avg|min|max|unique", "field": "field_name", "alias": "custom_name"}
  ],
  "filters": [
    {"field": "field_name", "operator": "eq|ne|gt|lt|contains|in", "value": "filter_value"}
  ],
  "group_by": ["field1", "field2"],
  "time_series": true,
  "time_granularity": "minute|hour|day|week|month",
  "limit": 100,
  "include_fields": ["field1", "field2", "field3"]
}
```

#### Visualization Configuration
```json
{
  "colors": ["#3b82f6", "#ef4444", "#10b981"],
  "x_axis_label": "Time",
  "y_axis_label": "Value",
  "show_legend": true,
  "show_grid": true,
  "format": "number|percentage|currency|bytes",
  "threshold": 100,
  "threshold_color": "#ef4444"
}
```

### Layout & Positioning

#### Grid Layout System
```json
{
  "columns": 12,
  "rows": 8,
  "row_height": 100,
  "margin": [10, 10],
  "responsive": true
}
```

#### Widget Position
```json
{
  "x": 0,       // Grid column position (0-11)
  "y": 0,       // Grid row position
  "w": 6,       // Width in grid units (1-12)
  "h": 4        // Height in grid units
}
```

## Pre-built Enterprise Dashboards

### 1. Security Operations Center (`security`)
**Focus**: Real-time security monitoring and threat detection

**Widgets**:
- Security Alerts Count (24h) - Critical security events counter
- Failed Login Attempts - Time series of authentication failures
- Top Attack Source IPs - Bar chart of most active malicious IPs
- Security Events by Service - Pie chart of service-level security events
- Recent Critical Security Events - Table of latest critical incidents

**Use Cases**: SOC monitoring, incident response, threat analysis

### 2. Performance Monitoring (`performance`)
**Focus**: Application performance metrics and optimization

**Widgets**:
- Total Requests (24h) - Request volume metric
- Error Rate % - Error percentage indicator
- Response Time Trend - Time series of application response times
- Slowest Endpoints - Bar chart of high-latency endpoints
- HTTP Status Code Distribution - Pie chart of response codes

**Use Cases**: Application monitoring, performance optimization, SLA tracking

### 3. Infrastructure Overview (`infrastructure`)
**Focus**: System health and resource utilization

**Widgets**:
- Active Services - Count of currently running services
- Log Volume Over Time - Time series of logging activity
- Log Volume by Service - Bar chart of service-level log generation
- Log Distribution by Host - Pie chart of host-level activity
- Log Levels Distribution - Bar chart of log severity levels

**Use Cases**: Infrastructure monitoring, capacity planning, system health

### 4. Business Intelligence (`business`)
**Focus**: User behavior and business metrics analysis

**Widgets**:
- Active Users (24h) - Unique user count
- User Activity Trend - Time series of user engagement
- Most Used Features - Bar chart of feature utilization
- User Geographic Distribution - Pie chart of user locations
- Business Conversion Events - Table of conversion activities

**Use Cases**: Product analytics, user engagement, business insights

### 5. Compliance & Audit (`compliance`)
**Focus**: Audit trails and regulatory compliance

**Widgets**:
- Audit Events (24h) - Count of audit-logged events
- Data Access Events - Time series of data access patterns
- Privileged Access Activities - Bar chart of privileged operations
- Policy Violations by Type - Pie chart of compliance violations
- Recent Audit Trail - Table of recent audit events

**Use Cases**: Compliance monitoring, audit reporting, governance

### 6. Executive Overview (`executive`)
**Focus**: High-level KPIs for executive decision making

**Widgets**:
- System Health Score - Overall system health metric
- Total Events Processed - Platform throughput indicator
- Critical Alerts (24h) - Critical issue counter
- Security Posture Trend - Time series of security metrics
- Service Availability - Bar chart of service uptime
- Key Performance Indicators - Summary table of critical metrics

**Use Cases**: Executive reporting, strategic planning, high-level monitoring

## Integration Examples

### Python SDK Integration

```python
import httpx
import asyncio
from datetime import datetime, timedelta
import json

class LogforgeDashboardClient:
    def __init__(self, base_url: str, token: str, customer_id: str):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {token}",
            "X-Customer-ID": customer_id,
            "Content-Type": "application/json"
        }
    
    async def list_dashboards(self, include_default: bool = True) -> dict:
        """List all available dashboards"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v1/dashboards",
                params={"include_default": include_default},
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def get_dashboard_data(self, dashboard_id: str, 
                               start_time: datetime = None, 
                               end_time: datetime = None) -> dict:
        """Get dashboard data with optional time range"""
        params = {}
        if start_time:
            params["start_time"] = start_time.isoformat()
        if end_time:
            params["end_time"] = end_time.isoformat()
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v1/dashboards/{dashboard_id}/data",
                params=params,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def create_custom_dashboard(self, dashboard_config: dict) -> dict:
        """Create a new custom dashboard"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/dashboards",
                json=dashboard_config,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def add_widget(self, dashboard_id: str, widget_config: dict) -> dict:
        """Add widget to dashboard"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/dashboards/{dashboard_id}/widgets",
                json=widget_config,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def share_dashboard(self, dashboard_id: str, email: str, 
                            permission: str = "view") -> dict:
        """Share dashboard with another user"""
        share_config = {
            "shared_with_email": email,
            "permission_level": permission
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/dashboards/{dashboard_id}/share",
                json=share_config,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

# Usage Example
async def main():
    client = LogforgeDashboardClient(
        base_url="http://localhost:7080",
        token="your_jwt_token",
        customer_id="your_tenant_id"
    )
    
    try:
        # List all dashboards
        dashboards = await client.list_dashboards()
        print(f"Found {dashboards['total']} dashboards")
        
        # Get security dashboard data for last 6 hours
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=6)
        
        security_data = await client.get_dashboard_data(
            "security", 
            start_time=start_time, 
            end_time=end_time
        )
        print(f"Security dashboard loaded with {len(security_data['widgets'])} widgets")
        
        # Create custom application dashboard
        custom_dashboard = {
            "name": "My Application Dashboard",
            "description": "Custom monitoring for my application",
            "widgets": [
                {
                    "name": "Error Rate",
                    "type": "metric",
                    "query_definition": {
                        "aggregations": [{"type": "count", "field": "*"}],
                        "filters": [
                            {"field": "level", "operator": "eq", "value": "error"},
                            {"field": "service", "operator": "eq", "value": "my-app"}
                        ]
                    },
                    "position": {"x": 0, "y": 0},
                    "size": {"width": 6, "height": 4}
                }
            ],
            "tags": ["custom", "application"]
        }
        
        result = await client.create_custom_dashboard(custom_dashboard)
        dashboard_id = result["dashboard_id"]
        print(f"Created custom dashboard: {dashboard_id}")
        
        # Add response time widget
        response_time_widget = {
            "name": "Response Time Trend",
            "type": "line_chart",
            "query_definition": {
                "aggregations": [{"type": "avg", "field": "response_time"}],
                "filters": [{"field": "service", "operator": "eq", "value": "my-app"}],
                "time_series": True,
                "time_granularity": "minute"
            },
            "position": {"x": 6, "y": 0},
            "size": {"width": 6, "height": 4}
        }
        
        await client.add_widget(dashboard_id, response_time_widget)
        print("Added response time widget")
        
        # Share dashboard with team member
        await client.share_dashboard(
            dashboard_id, 
            "teammate@company.com", 
            "edit"
        )
        print("Dashboard shared with teammate")
        
    except httpx.HTTPStatusError as e:
        print(f"API Error {e.response.status_code}: {e.response.text}")
    except Exception as e:
        print(f"Error: {e}")

# Run the example
asyncio.run(main())
```

### JavaScript/Node.js Integration

```javascript
const axios = require('axios');

class LogforgeDashboardClient {
  constructor(baseUrl, token, customerId) {
    this.baseUrl = baseUrl;
    this.headers = {
      'Authorization': `Bearer ${token}`,
      'X-Customer-ID': customerId,
      'Content-Type': 'application/json'
    };
  }

  async listDashboards(includeDefault = true) {
    try {
      const response = await axios.get(
        `${this.baseUrl}/v1/dashboards`,
        { 
          params: { include_default: includeDefault },
          headers: this.headers 
        }
      );
      return response.data;
    } catch (error) {
      throw new Error(`Failed to list dashboards: ${error.response?.data?.detail}`);
    }
  }

  async getDashboardData(dashboardId, timeRange = null) {
    try {
      const params = {};
      if (timeRange) {
        params.start_time = timeRange.startTime;
        params.end_time = timeRange.endTime;
      }

      const response = await axios.get(
        `${this.baseUrl}/v1/dashboards/${dashboardId}/data`,
        { 
          params,
          headers: this.headers 
        }
      );
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get dashboard data: ${error.response?.data?.detail}`);
    }
  }

  async createRealtimeDashboard(serviceName) {
    const dashboardConfig = {
      name: `${serviceName} Real-time Monitoring`,
      description: `Real-time monitoring dashboard for ${serviceName}`,
      widgets: [
        {
          name: "Request Volume",
          type: "line_chart",
          query_definition: {
            aggregations: [{ type: "count", field: "*" }],
            filters: [{ field: "service", operator: "eq", value: serviceName }],
            time_series: true,
            time_granularity: "minute"
          },
          visualization_config: {
            colors: ["#3b82f6"],
            y_axis_label: "Requests/min"
          },
          position: { x: 0, y: 0 },
          size: { width: 8, height: 4 },
          refresh_interval: 30
        },
        {
          name: "Error Rate",
          type: "metric",
          query_definition: {
            aggregations: [
              { type: "count", field: "*", alias: "total" },
              { type: "count", field: "level", alias: "errors" }
            ],
            filters: [
              { field: "service", operator: "eq", value: serviceName },
              { field: "level", operator: "eq", value: "error" }
            ]
          },
          visualization_config: {
            format: "percentage",
            threshold: 5,
            threshold_color: "#ef4444"
          },
          position: { x: 8, y: 0 },
          size: { width: 4, height: 2 },
          refresh_interval: 60
        },
        {
          name: "Recent Errors",
          type: "table",
          query_definition: {
            filters: [
              { field: "service", operator: "eq", value: serviceName },
              { field: "level", operator: "eq", value: "error" }
            ],
            include_fields: ["ts", "msg", "user_id", "trace_id"],
            limit: 50
          },
          position: { x: 0, y: 4 },
          size: { width: 12, height: 4 },
          refresh_interval: 120
        }
      ],
      layout: { columns: 12, rows: 8 },
      tags: ["realtime", serviceName, "monitoring"]
    };

    try {
      const response = await axios.post(
        `${this.baseUrl}/v1/dashboards`,
        dashboardConfig,
        { headers: this.headers }
      );
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create dashboard: ${error.response?.data?.detail}`);
    }
  }

  async setupDashboardSharing(dashboardId, teamEmails, permission = 'view') {
    const sharePromises = teamEmails.map(email => 
      axios.post(
        `${this.baseUrl}/v1/dashboards/${dashboardId}/share`,
        {
          shared_with_email: email,
          permission_level: permission
        },
        { headers: this.headers }
      )
    );

    try {
      const results = await Promise.all(sharePromises);
      return results.map(r => r.data);
    } catch (error) {
      throw new Error(`Failed to share dashboard: ${error.response?.data?.detail}`);
    }
  }
}

// Usage Example
async function demonstrateDashboardWorkflow() {
  const client = new LogforgeDashboardClient(
    'http://localhost:7080',
    process.env.LOGFORGE_TOKEN,
    process.env.CUSTOMER_ID
  );

  try {
    // List existing dashboards
    console.log('Fetching dashboard list...');
    const dashboards = await client.listDashboards();
    console.log(`Found ${dashboards.total} dashboards (${dashboards.custom_count} custom)`);

    // Get security dashboard data for the last hour
    console.log('Loading security dashboard...');
    const endTime = new Date().toISOString();
    const startTime = new Date(Date.now() - 60 * 60 * 1000).toISOString();
    
    const securityData = await client.getDashboardData('security', {
      startTime,
      endTime
    });
    
    console.log(`Security dashboard loaded:`);
    Object.entries(securityData.widgets).forEach(([widgetId, widget]) => {
      console.log(`  - ${widget.title}: ${JSON.stringify(widget.data.value || widget.data.series?.length || 'N/A')}`);
    });

    // Create custom service dashboard
    console.log('Creating custom service dashboard...');
    const serviceName = 'payment-api';
    const customDashboard = await client.createRealtimeDashboard(serviceName);
    console.log(`Created dashboard: ${customDashboard.dashboard_id}`);

    // Share with team
    console.log('Sharing dashboard with team...');
    const teamEmails = ['dev1@company.com', 'dev2@company.com', 'manager@company.com'];
    await client.setupDashboardSharing(customDashboard.dashboard_id, teamEmails, 'edit');
    console.log(`Dashboard shared with ${teamEmails.length} team members`);

  } catch (error) {
    console.error('Dashboard workflow error:', error.message);
  }
}

// Run the demonstration
demonstrateDashboardWorkflow();
```

### cURL Examples

**List Dashboards**:
```bash
curl -X GET "http://localhost:7080/v1/dashboards?include_default=true&limit=10" \
  -H "Authorization: Bearer your_jwt_token" \
  -H "X-Customer-ID: your_tenant_id"
```

**Get Dashboard Data**:
```bash
curl -X GET "http://localhost:7080/v1/dashboards/security/data?start_time=2024-01-01T12:00:00Z&end_time=2024-01-01T18:00:00Z" \
  -H "Authorization: Bearer your_jwt_token" \
  -H "X-Customer-ID: your_tenant_id"
```

**Create Custom Dashboard**:
```bash
curl -X POST "http://localhost:7080/v1/dashboards" \
  -H "Authorization: Bearer your_jwt_token" \
  -H "X-Customer-ID: your_tenant_id" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "API Monitoring Dashboard",
    "description": "Real-time API performance monitoring",
    "widgets": [
      {
        "name": "Request Volume",
        "type": "line_chart",
        "query_definition": {
          "aggregations": [{"type": "count", "field": "*"}],
          "time_series": true,
          "time_granularity": "minute"
        },
        "position": {"x": 0, "y": 0},
        "size": {"width": 12, "height": 4}
      }
    ],
    "tags": ["api", "monitoring"]
  }'
```

**Add Widget to Dashboard**:
```bash
curl -X POST "http://localhost:7080/v1/dashboards/dashboard_id_123/widgets" \
  -H "Authorization: Bearer your_jwt_token" \
  -H "X-Customer-ID: your_tenant_id" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Error Rate",
    "type": "metric",
    "query_definition": {
      "aggregations": [{"type": "count", "field": "*"}],
      "filters": [{"field": "level", "operator": "eq", "value": "error"}]
    },
    "position": {"x": 6, "y": 0},
    "size": {"width": 6, "height": 2}
  }'
```

**Share Dashboard**:
```bash
curl -X POST "http://localhost:7080/v1/dashboards/dashboard_id_123/share" \
  -H "Authorization: Bearer your_jwt_token" \
  -H "X-Customer-ID: your_tenant_id" \
  -H "Content-Type: application/json" \
  -d '{
    "shared_with_email": "analyst@company.com",
    "permission_level": "view",
    "expires_at": "2024-06-01T12:00:00Z"
  }'
```

## Error Handling

### HTTP Status Codes

- **200 OK**: Successful operation
- **201 Created**: Dashboard or widget created successfully
- **400 Bad Request**: Invalid request data or validation errors
- **401 Unauthorized**: Invalid or expired authentication token
- **403 Forbidden**: Insufficient permissions for operation
- **404 Not Found**: Dashboard, widget, or resource not found
- **500 Internal Server Error**: Server-side processing error

### Error Response Format

```json
{
  "detail": "Detailed error message describing the issue"
}
```

### Common Error Scenarios

#### Dashboard Not Found
```json
{
  "detail": "Dashboard not found"
}
```

#### Invalid Widget Type
```json
{
  "detail": "Failed to create widget: Invalid widget type 'invalid_chart'. Must be one of: metric, line_chart, bar_chart, pie_chart, table, heatmap"
}
```

#### Invalid Query Definition
```json
{
  "detail": "Failed to create dashboard: Invalid aggregation type 'invalid_agg'. Must be one of: count, sum, avg, min, max, unique"
}
```

#### Permission Denied
```json
{
  "detail": "Insufficient permissions to share dashboard"
}
```

### Error Handling Best Practices

```python
async def handle_dashboard_errors(api_call):
    """Error handling wrapper for dashboard API calls"""
    try:
        return await api_call()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print("Dashboard or widget not found")
        elif e.response.status_code == 403:
            print("Insufficient permissions for dashboard operation")
        elif e.response.status_code == 400:
            error_detail = e.response.json().get("detail", "Validation error")
            print(f"Validation error: {error_detail}")
        else:
            print(f"API error {e.response.status_code}: {e.response.text}")
        raise
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise
```

## Performance Characteristics

### Response Times
- **Dashboard List**: ~50-200ms (includes default dashboard metadata)
- **Dashboard Configuration**: ~25-100ms (single database query)
- **Dashboard Data Generation**: ~200-2000ms (depends on widget complexity and data volume)
- **Widget Data**: ~100-500ms (single widget query execution)
- **Dashboard Creation**: ~100-300ms (includes validation and database persistence)
- **Widget Operations**: ~50-200ms (CRUD operations)

### Data Generation Performance
- **Simple Metrics**: ~25-100ms (count aggregations)
- **Time Series Charts**: ~100-500ms (depends on time granularity and data volume)
- **Complex Aggregations**: ~200-1000ms (multiple grouping and filtering)
- **Table Queries**: ~150-800ms (depends on result set size and sorting)

### Scalability Features
- **Widget Caching**: Real-time data with configurable refresh intervals
- **Query Optimization**: Advanced query engine with index utilization
- **Concurrent Execution**: Parallel widget data generation
- **Database Optimization**: Partitioned tables and efficient query patterns

## Best Practices

### For Dashboard Designers

1. **Widget Placement**: Use grid layout effectively - place most important widgets in top-left
2. **Color Consistency**: Use consistent color schemes across related widgets
3. **Refresh Intervals**: Balance real-time needs with system performance (30s-5min recommended)
4. **Data Density**: Avoid overcrowding dashboards - 6-8 widgets maximum per view
5. **Time Ranges**: Provide meaningful default time ranges for widget queries
6. **Filter Strategy**: Use dashboard-level filters for common filtering requirements
7. **Performance Testing**: Test dashboard load times with realistic data volumes

### For Developers

1. **Query Optimization**: Use appropriate indexes and query patterns for widget queries
2. **Error Handling**: Implement robust error handling for widget data failures
3. **Caching Strategy**: Implement client-side caching for dashboard configurations
4. **Real-time Updates**: Use appropriate refresh intervals based on data freshness requirements
5. **API Batching**: Batch multiple widget updates when possible
6. **Resource Management**: Monitor memory usage for complex dashboard data
7. **Testing**: Test dashboards with various data volumes and edge cases

### For Operations Teams

1. **Monitoring**: Monitor dashboard load times and query performance
2. **Capacity Planning**: Plan for peak dashboard usage and concurrent users
3. **Data Retention**: Align widget time ranges with data retention policies
4. **Access Management**: Regularly review dashboard sharing and permissions
5. **Performance Alerts**: Set up alerts for dashboard query timeout or failures
6. **Backup Procedures**: Include custom dashboards in backup and disaster recovery
7. **Usage Analytics**: Track dashboard usage patterns for optimization

## Security Considerations

### Multi-Tenant Isolation
1. **Data Separation**: Complete dashboard isolation by customer_id
2. **Query Scoping**: All widget queries automatically scoped to tenant data
3. **Share Validation**: Cross-tenant sharing requires explicit permission
4. **Access Controls**: Role-based access to dashboard management operations

### Permission Management
1. **Dashboard Ownership**: Creators have full control over their dashboards
2. **Sharing Permissions**: Granular view/edit/admin permission levels
3. **Tenant Boundaries**: Sharing across tenant boundaries requires admin approval
4. **Expiration Controls**: Time-limited sharing with automatic expiration

### Data Security
1. **Query Validation**: All widget queries validated for security and performance
2. **Injection Prevention**: Parameterized queries prevent SQL injection
3. **Data Filtering**: Automatic filtering ensures users only see authorized data
4. **Audit Logging**: Complete audit trail for dashboard creation, modification, and sharing

The Dashboard Router API provides comprehensive dashboard management capabilities with enterprise-grade visualization, real-time data integration, and secure multi-tenant operation to enable powerful data-driven insights across the Logforge platform.