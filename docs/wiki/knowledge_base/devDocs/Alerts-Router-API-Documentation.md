# Alerts Router API - Developer Documentation

## Overview

The Alerts Router API (`/v1/alerts`) provides enterprise-grade real-time alerting and notification capabilities for the Logforge platform. This comprehensive system enables automated monitoring, rule-based alerting, multi-channel notifications, and complete alert lifecycle management with enterprise reliability and performance.

**Location**: `/apps/api/routers/alerts.py`  
**Service Layer**: `/apps/api/services/alert_service.py`  
**Data Layer**: `/apps/api/dao/alert_dao.py`  
**Authentication**: Required for all endpoints  
**Multi-Tenancy**: `X-Customer-ID` header required for all endpoints  
**Subscription**: Requires `alerts.*` or `alerts.basic` features in subscription

## Architecture & Components

### System Architecture
```
FastAPI Router → AlertService → AlertDAO → ClickHouse Database
     ↓              ↓             ↓            ↓
Middleware     Business Logic  Database    Multi-tenant
Validation     Rule Engine     Operations   Data Storage
```

### Core Components

1. **FastAPI Router** (`alerts.py`): HTTP endpoint definitions and request/response handling
2. **Alert Service** (`alert_service.py`): Business logic, validation, and orchestration
3. **Alert DAO** (`alert_dao.py`): Database operations and query management
4. **Middleware Integration**: Authentication and tenant isolation
5. **Database Layer**: ClickHouse multi-tenant storage with optimized schemas

### Database Schema

**Alert Rules Table**: `alert_rules_mt`
```sql
CREATE TABLE alert_rules_mt (
    id String,
    customer_id String,
    name String,
    description String,
    rule_type String,
    query String,
    condition_config String,  -- JSON: conditions, filters, evaluation settings
    notification_channels Array(String),
    severity String,
    is_enabled UInt8,
    cooldown_minutes UInt32,
    created_at DateTime64(3),
    updated_at DateTime64(3),
    created_by String
) ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY customer_id
ORDER BY (customer_id, id);
```

**Alert Instances Table**: `alert_instances_mt`
```sql
CREATE TABLE alert_instances_mt (
    id String,
    rule_id String,
    customer_id String,
    status String,  -- 'triggered', 'acknowledged', 'resolved'
    triggered_at DateTime64(3),
    acknowledged_at Nullable(DateTime64(3)),
    resolved_at Nullable(DateTime64(3)),
    acknowledged_by Nullable(String),
    trigger_data String,  -- JSON: alert details, severity, message
    resolution_data Nullable(String),
    escalation_level UInt8
) ENGINE = ReplacingMergeTree(triggered_at)
PARTITION BY customer_id
ORDER BY (customer_id, id);
```

**Notification Channels Table**: `notification_channels_mt`
```sql
CREATE TABLE notification_channels_mt (
    id String,
    customer_id String,
    name String,
    channel_type String,  -- 'email', 'slack', 'webhook', etc.
    config String,  -- JSON: channel configuration
    is_enabled UInt8,
    created_at DateTime64(3),
    updated_at DateTime64(3)
) ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY customer_id
ORDER BY (customer_id, id);
```

## API Endpoints (15 Total)

### 1. Alert Rules Management (6 endpoints)

#### **POST /v1/alerts/rules** - Create Alert Rule
Create sophisticated alert rules with multiple rule types and advanced conditions.

**Request Model**: `Dict[str, Any]`
```json
{
  "name": "High Error Rate Alert",
  "description": "Alert when error rate exceeds threshold in payment service",
  "rule_type": "threshold",
  "severity": "critical",
  "enabled": true,
  "evaluation_interval": 300,
  "cooldown_period": 600,
  "max_alerts_per_hour": 10,
  "conditions": [
    {
      "field": "level",
      "operator": "eq",
      "value": "ERROR"
    },
    {
      "field": "service",
      "operator": "eq", 
      "value": "payment-api"
    },
    {
      "field": "count",
      "operator": "gte",
      "value": 25
    }
  ],
  "filters": [
    {
      "field": "environment",
      "operator": "eq",
      "value": "production"
    }
  ],
  "notification_channels": ["email", "slack"],
  "tags": ["production", "payment", "critical"]
}
```

**Supported Rule Types**:
- `threshold`: Value exceeds/falls below threshold
- `frequency`: Event frequency within time window
- `pattern`: Complex pattern matching in logs
- `anomaly`: Statistical anomaly detection
- `absence`: Missing expected events  
- `sequence`: Event sequence pattern detection

**Response**: (200 OK)
```json
{
  "rule_id": "rule_abc123def456",
  "name": "High Error Rate Alert",
  "customer_id": "tenant-uuid-123",
  "enabled": true,
  "rule_type": "threshold",
  "severity": "critical",
  "created_at": "2024-01-01T12:00:00Z",
  "status": "active"
}
```

#### **GET /v1/alerts/rules** - List Alert Rules
List all alert rules with filtering and pagination.

**Query Parameters**:
- `enabled` (bool): Filter by enabled status
- `severity` (str): Filter by severity (`low`, `medium`, `high`, `critical`)
- `limit` (int): Maximum results per page (default: 100, max: 1000)
- `offset` (int): Pagination offset (default: 0)

**Response**: (200 OK)
```json
{
  "rules": [
    {
      "rule_id": "rule_abc123",
      "name": "High Error Rate Alert",
      "rule_type": "threshold",
      "severity": "critical",
      "enabled": true,
      "created_at": "2024-01-01T12:00:00Z",
      "conditions": [
        {
          "field": "level",
          "operator": "eq",
          "value": "ERROR"
        }
      ],
      "filters": [
        {
          "field": "environment",
          "operator": "eq",
          "value": "production"
        }
      ],
      "notification_channels": ["email", "slack"],
      "tags": ["production", "payment"]
    }
  ],
  "total": 25,
  "limit": 100,
  "offset": 0,
  "customer_id": "tenant-uuid-123"
}
```

#### **GET /v1/alerts/rules/{rule_id}** - Get Alert Rule
Retrieve detailed configuration for a specific alert rule.

**Response**: (200 OK)
```json
{
  "rule_id": "rule_abc123def456",
  "name": "High Error Rate Alert",
  "description": "Alert when error rate exceeds threshold in payment service",
  "rule_type": "threshold",
  "severity": "critical",
  "enabled": true,
  "evaluation_interval": 300,
  "cooldown_period": 600,
  "max_alerts_per_hour": 10,
  "conditions": [
    {
      "field": "level",
      "operator": "eq",
      "value": "ERROR"
    }
  ],
  "filters": [
    {
      "field": "environment",
      "operator": "eq",
      "value": "production"
    }
  ],
  "notification_channels": ["email", "slack"],
  "tags": ["production", "payment", "critical"],
  "customer_id": "tenant-uuid-123",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T15:30:00Z"
}
```

#### **PUT /v1/alerts/rules/{rule_id}** - Update Alert Rule
Update existing alert rule configuration with partial updates.

**Request Model**: `AlertRuleUpdateRequest`
```json
{
  "description": "Updated alert description with new threshold",
  "severity": "high",
  "enabled": false,
  "conditions": [
    {
      "field": "level",
      "operator": "in",
      "value": ["ERROR", "FATAL"]
    }
  ],
  "notification_channels": ["slack", "pagerduty"]
}
```

**Response**: (200 OK)
```json
{
  "rule_id": "rule_abc123def456",
  "name": "High Error Rate Alert",
  "severity": "high",
  "enabled": false,
  "updated_at": "2024-01-01T16:00:00Z",
  "customer_id": "tenant-uuid-123",
  "status": "updated"
}
```

#### **DELETE /v1/alerts/rules/{rule_id}** - Delete Alert Rule
Permanently delete an alert rule and stop all evaluations.

**Response**: (200 OK)
```json
{
  "status": "deleted",
  "rule_id": "rule_abc123def456",
  "customer_id": "tenant-uuid-123",
  "deleted_at": "2024-01-01T16:15:00Z"
}
```

#### **POST /v1/alerts/rules/{rule_id}/test** - Test Alert Rule
Test alert rule evaluation against current log data to validate rule logic.

**Optional Request Body**: `Dict[str, Any]`
```json
{
  "time_range": {
    "start": "2024-01-01T15:00:00Z",
    "end": "2024-01-01T16:00:00Z"
  },
  "sample_size": 1000
}
```

**Response**: (200 OK)
```json
{
  "rule_id": "rule_abc123def456",
  "triggered": true,
  "query_result": 25,
  "evaluation_time_ms": 45,
  "test_result": {
    "would_trigger": true,
    "query_result_count": 25,
    "conditions_evaluated": 3,
    "filters_applied": 1,
    "test_timestamp": "2024-01-01T16:00:00Z"
  },
  "customer_id": "tenant-uuid-123"
}
```

### 2. Alert Instance Management (5 endpoints)

#### **GET /v1/alerts** - List Active Alerts
List all active, acknowledged, or resolved alerts with comprehensive filtering.

**Query Parameters**:
- `status` (str): Filter by alert status (`active`, `acknowledged`, `resolved`)
- `severity` (str): Filter by severity level (`low`, `medium`, `high`, `critical`)
- `limit` (int): Maximum results per page (default: 100)
- `offset` (int): Pagination offset (default: 0)

**Response**: (200 OK)
```json
{
  "alerts": [
    {
      "alert_id": "alert_xyz789",
      "rule_id": "rule_abc123",
      "title": "High Error Rate Detected",
      "message": "Error rate exceeded threshold: 25 errors in 5 minutes",
      "status": "active",
      "severity": "critical",
      "triggered_at": "2024-01-01T15:30:00Z",
      "details": {
        "error_count": 25,
        "threshold": 10,
        "affected_service": "payment-api",
        "time_window": "5m"
      }
    }
  ],
  "total": 8,
  "limit": 100,
  "offset": 0,
  "customer_id": "tenant-uuid-123"
}
```

#### **GET /v1/alerts/stats** - Alert Engine Statistics
Get comprehensive alert engine performance and operational statistics.

**Response**: (200 OK)
```json
{
  "rules": {
    "total": 25,
    "enabled": 23,
    "disabled": 2
  },
  "alerts": {
    "active": 8,
    "acknowledged": 3,
    "resolved": 142,
    "total_fired": 153
  },
  "notifications": {
    "sent": 245,
    "failed": 12
  },
  "performance": {
    "avg_evaluation_time_ms": 45,
    "last_evaluation": "2024-01-01T16:00:00Z"
  },
  "customer_id": "tenant-uuid-123"
}
```

#### **GET /v1/alerts/health** - Alert Engine Health
Get alert engine health status and system diagnostics.

**Response**: (200 OK)
```json
{
  "status": "healthy",
  "active_rules": 23,
  "active_alerts": 8,
  "last_evaluation": "2024-01-01T16:00:00Z",
  "database_connected": true,
  "notification_channels_available": true,
  "health_check_duration_ms": 15,
  "customer_id": "tenant-uuid-123",
  "checked_at": "2024-01-01T16:00:30Z"
}
```

**Health Status Values**:
- `healthy`: All systems operational
- `degraded`: Some issues detected but functioning
- `unhealthy`: Critical issues detected

#### **GET /v1/alerts/{alert_id}** - Get Alert Instance
Retrieve detailed information for a specific alert instance.

**Response**: (200 OK)
```json
{
  "alert_id": "alert_xyz789",
  "rule_id": "rule_abc123",
  "title": "High Error Rate Detected",
  "message": "Error rate exceeded threshold: 25 errors in 5 minutes",
  "status": "active",
  "severity": "critical",
  "triggered_at": "2024-01-01T15:30:00Z",
  "details": {
    "error_count": 25,
    "threshold": 10,
    "affected_service": "payment-api",
    "time_window": "5m",
    "sample_errors": [
      {
        "timestamp": "2024-01-01T15:29:45Z",
        "level": "ERROR",
        "message": "Payment processing timeout",
        "service": "payment-api",
        "trace_id": "trace_abc123"
      }
    ]
  },
  "customer_id": "tenant-uuid-123"
}
```

#### **POST /v1/alerts/{alert_id}/acknowledge** - Acknowledge Alert
Mark an alert as acknowledged to stop further notifications.

**Request Model**: `AlertStatusUpdate`
```json
{
  "status": "acknowledged",
  "notes": "Investigating payment API timeout issues"
}
```

**Response**: (200 OK)
```json
{
  "status": "acknowledged",
  "alert_id": "alert_xyz789",
  "customer_id": "tenant-uuid-123",
  "acknowledged_at": "2024-01-01T16:05:00Z",
  "acknowledged_by": "api-user"
}
```

#### **POST /v1/alerts/{alert_id}/resolve** - Resolve Alert
Mark an alert as resolved with detailed resolution notes.

**Request Model**: `AlertStatusUpdate`
```json
{
  "status": "resolved",
  "notes": "Fixed payment API timeout configuration and increased connection pool size"
}
```

**Response**: (200 OK)
```json
{
  "status": "resolved",
  "alert_id": "alert_xyz789",
  "customer_id": "tenant-uuid-123",
  "resolved_at": "2024-01-01T16:30:00Z",
  "resolved_by": "api-user",
  "resolution_notes": "Fixed payment API timeout configuration and increased connection pool size"
}
```

### 3. Notification Channels (2 endpoints)

#### **GET /v1/alerts/notifications/channels** - List Notification Channels
List all configured notification channels for alerts.

**Response**: (200 OK)
```json
{
  "channels": [
    {
      "channel_id": "channel_email_001",
      "name": "Operations Team Email",
      "type": "email",
      "enabled": true,
      "configuration": {
        "recipients": ["ops@company.com", "devops@company.com"],
        "subject_template": "🚨 Alert: {{rule_name}}",
        "body_template": "Alert: {{message}}\nTriggered: {{triggered_at}}\nSeverity: {{severity}}"
      },
      "created_at": "2024-01-01T10:00:00Z"
    },
    {
      "channel_id": "channel_slack_001",
      "name": "Dev Team Slack",
      "type": "slack",
      "enabled": true,
      "configuration": {
        "webhook_url": "https://hooks.slack.com/services/T123/B456/xyz",
        "channel": "#alerts",
        "username": "LogforgeBot",
        "icon_emoji": ":warning:",
        "message_template": ":rotating_light: *{{rule_name}}*\n{{message}}"
      },
      "created_at": "2024-01-01T10:00:00Z"
    }
  ],
  "total": 5,
  "customer_id": "tenant-uuid-123"
}
```

**Supported Channel Types**:
- `email`: SMTP email notifications
- `slack`: Slack webhook integration
- `webhook`: Generic HTTP webhook
- `pagerduty`: PagerDuty incident creation
- `teams`: Microsoft Teams integration
- `discord`: Discord webhook notifications

#### **POST /v1/alerts/notifications/channels** - Create Notification Channel
Create a new notification channel for alert delivery.

**Email Channel Example**:
```json
{
  "name": "Critical Alerts Email",
  "type": "email",
  "configuration": {
    "recipients": ["critical-ops@company.com"],
    "subject_template": "🔥 CRITICAL: {{rule_name}}",
    "body_template": "Alert: {{message}}\nTriggered: {{triggered_at}}\nSeverity: {{severity}}\n\nDetails:\n{{details}}"
  },
  "enabled": true
}
```

**Slack Channel Example**:
```json
{
  "name": "Dev Team Slack Alerts",
  "type": "slack",
  "configuration": {
    "webhook_url": "https://hooks.slack.com/services/T123/B456/xyz",
    "channel": "#dev-alerts",
    "username": "LogforgeBot",
    "icon_emoji": ":warning:",
    "message_template": ":rotating_light: *{{rule_name}}*\n{{message}}\n*Severity:* {{severity}}"
  },
  "enabled": true
}
```

**Response**: (200 OK)
```json
{
  "status": "created",
  "channel": {
    "channel_id": "channel_abc123",
    "name": "Critical Alerts Email",
    "type": "email",
    "enabled": true,
    "created_at": "2024-01-01T16:00:00Z"
  },
  "customer_id": "tenant-uuid-123"
}
```

### 4. Webhook Integrations (2 endpoints)

#### **GET /v1/alerts/integrations/webhooks** - List Webhook Integrations
List all webhook integrations for external system connectivity.

**Response**: (200 OK)
```json
{
  "webhooks": [
    {
      "channel_id": "webhook_servicenow_001",
      "name": "ServiceNow Integration",
      "type": "webhook",
      "configuration": {
        "url": "https://company.service-now.com/api/logforge/alerts",
        "method": "POST",
        "headers": {
          "Authorization": "Bearer token_masked",
          "Content-Type": "application/json"
        },
        "payload_template": "servicenow"
      },
      "enabled": true,
      "created_at": "2024-01-01T10:00:00Z"
    }
  ],
  "total": 3,
  "customer_id": "tenant-uuid-123"
}
```

#### **POST /v1/alerts/integrations/webhooks** - Create Webhook Integration
Create webhook integration for external system notifications.

**ServiceNow Integration Example**:
```json
{
  "name": "ServiceNow Incident Creation",
  "url": "https://company.service-now.com/api/incidents",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer sn_token_123",
    "Content-Type": "application/json"
  },
  "payload_template": "servicenow",
  "custom_payload": {
    "short_description": "Logforge Alert: {{rule_name}}",
    "description": "{{message}}\n\nSeverity: {{severity}}\nTriggered: {{triggered_at}}\nCustomer: {{customer_id}}",
    "urgency": "{{#if_eq severity 'critical'}}1{{else}}3{{/if_eq}}",
    "impact": "{{#if_eq severity 'critical'}}1{{else}}3{{/if_eq}}"
  },
  "timeout_seconds": 30,
  "retry_attempts": 3
}
```

**Generic Webhook Example**:
```json
{
  "name": "Custom SIEM Integration",
  "url": "https://siem.company.com/api/events",
  "method": "POST",
  "headers": {
    "X-API-Key": "siem_key_456",
    "Content-Type": "application/json"
  },
  "payload_template": "custom",
  "custom_payload": {
    "event_type": "logforge_alert",
    "severity": "{{severity}}",
    "message": "{{message}}",
    "timestamp": "{{triggered_at}}",
    "source": "logforge",
    "rule_id": "{{rule_id}}",
    "customer": "{{customer_id}}"
  }
}
```

**Response**: (200 OK)
```json
{
  "status": "created",
  "webhook": {
    "channel_id": "webhook_abc123",
    "name": "ServiceNow Incident Creation",
    "type": "webhook",
    "enabled": true,
    "created_at": "2024-01-01T16:00:00Z"
  },
  "customer_id": "tenant-uuid-123"
}
```

## Data Models & Validation

### Core Request Models

#### AlertRuleUpdateRequest
```python
class AlertRuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    filters: Optional[List[Dict[str, Any]]] = None
    notification_channels: Optional[List[str]] = None
    severity: Optional[str] = None
```

#### AlertStatusUpdate
```python
class AlertStatusUpdate(BaseModel):
    status: str  # 'acknowledged', 'resolved'
    notes: Optional[str] = None
```

### Field Validation

#### Severity Levels
- `low`: Low priority, informational alerts
- `medium`: Standard operational alerts
- `high`: Important issues requiring attention
- `critical`: Emergency issues requiring immediate response

#### Rule Types
- `threshold`: Value-based alerting (counts, percentages, metrics)
- `frequency`: Event frequency within time windows
- `pattern`: Complex pattern matching and regex
- `anomaly`: Statistical anomaly detection
- `absence`: Missing expected events or heartbeats
- `sequence`: Event sequence and correlation

#### Condition Operators
- `eq`: Equals
- `ne`: Not equals
- `gt`: Greater than
- `gte`: Greater than or equal
- `lt`: Less than
- `lte`: Less than or equal
- `contains`: String contains
- `starts_with`: String starts with
- `ends_with`: String ends with
- `regex`: Regular expression match
- `in`: Value in list
- `not_in`: Value not in list

### Condition Examples

**String Matching**:
```json
{
  "field": "level",
  "operator": "in",
  "value": ["ERROR", "FATAL", "CRITICAL"]
}
```

**Numeric Threshold**:
```json
{
  "field": "response_time_ms",
  "operator": "gt",
  "value": 5000
}
```

**Pattern Matching**:
```json
{
  "field": "message",
  "operator": "regex",
  "value": "timeout|connection.*failed|database.*error"
}
```

**Service Filtering**:
```json
{
  "field": "service",
  "operator": "contains",
  "value": "payment"
}
```

## Authentication & Authorization

### Required Headers

**All endpoints require**:
```http
Authorization: Bearer <jwt_token>
X-Customer-ID: <tenant_id>
```

### Role-Based Access Control

| Endpoint Category | Required Permissions | Allowed Roles |
|-------------------|---------------------|---------------|
| Rule Management | `alerts:write` | `tenant_admin`, `devops_engineer` |
| Alert Viewing | `alerts:read` | `tenant_admin`, `security_analyst`, `viewer` |
| Alert Lifecycle | `alerts:write` | `tenant_admin`, `devops_engineer` |
| Notifications | `alerts:admin` | `tenant_admin`, `admin` |
| Webhooks | `alerts:admin` | `tenant_admin`, `admin` |

### Subscription Requirements

All endpoints require `alerts.*` or `alerts.basic` feature in tenant subscription:
```json
{
  "subscribed_features": [
    "alerts.*",
    "ingestion.*", 
    "queries.*"
  ],
  "subscription_tier": "professional"
}
```

## Integration Examples

### Python SDK Integration

```python
import httpx
import asyncio
from datetime import datetime, timezone

class LogforgeAlertsClient:
    def __init__(self, base_url: str, token: str, customer_id: str):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {token}",
            "X-Customer-ID": customer_id,
            "Content-Type": "application/json"
        }
    
    async def create_alert_rule(self, rule_data: dict) -> dict:
        """Create a new alert rule"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/alerts/rules",
                json=rule_data,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def list_active_alerts(self, severity: str = None) -> dict:
        """List active alerts with optional severity filter"""
        params = {"status": "active"}
        if severity:
            params["severity"] = severity
            
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v1/alerts",
                params=params,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def acknowledge_alert(self, alert_id: str, notes: str = None) -> dict:
        """Acknowledge an active alert"""
        data = {"status": "acknowledged"}
        if notes:
            data["notes"] = notes
            
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/alerts/{alert_id}/acknowledge",
                json=data,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

# Usage Example
async def main():
    client = LogforgeAlertsClient(
        base_url="http://localhost:7080",
        token="your_jwt_token",
        customer_id="your_tenant_id"
    )
    
    # Create an error rate alert rule
    rule_data = {
        "name": "High Error Rate - Payment API",
        "description": "Alert when payment API error rate exceeds 5%",
        "rule_type": "threshold",
        "severity": "critical",
        "conditions": [
            {"field": "level", "operator": "eq", "value": "ERROR"},
            {"field": "service", "operator": "eq", "value": "payment-api"}
        ],
        "filters": [
            {"field": "environment", "operator": "eq", "value": "production"}
        ],
        "notification_channels": ["email", "slack"]
    }
    
    rule = await client.create_alert_rule(rule_data)
    print(f"Created rule: {rule['rule_id']}")
    
    # Check for active alerts
    alerts = await client.list_active_alerts(severity="critical")
    print(f"Found {len(alerts['alerts'])} critical alerts")
    
    # Acknowledge alerts if any
    for alert in alerts['alerts']:
        await client.acknowledge_alert(
            alert['alert_id'], 
            "Investigating payment system issues"
        )

# Run the example
asyncio.run(main())
```

### cURL Examples

**Create Alert Rule**:
```bash
curl -X POST "http://localhost:7080/v1/alerts/rules" \
  -H "Authorization: Bearer your_jwt_token" \
  -H "X-Customer-ID: your_tenant_id" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Database Connection Errors",
    "rule_type": "threshold",
    "severity": "high",
    "conditions": [
      {"field": "level", "operator": "eq", "value": "ERROR"},
      {"field": "message", "operator": "contains", "value": "database"}
    ],
    "notification_channels": ["email"]
  }'
```

**List Active Alerts**:
```bash
curl -X GET "http://localhost:7080/v1/alerts?status=active&severity=critical" \
  -H "Authorization: Bearer your_jwt_token" \
  -H "X-Customer-ID: your_tenant_id"
```

**Acknowledge Alert**:
```bash
curl -X POST "http://localhost:7080/v1/alerts/alert_xyz789/acknowledge" \
  -H "Authorization: Bearer your_jwt_token" \
  -H "X-Customer-ID: your_tenant_id" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "acknowledged",
    "notes": "Team investigating database performance issues"
  }'
```

### JavaScript/Node.js Integration

```javascript
const axios = require('axios');

class LogforgeAlertsClient {
  constructor(baseUrl, token, customerId) {
    this.baseUrl = baseUrl;
    this.headers = {
      'Authorization': `Bearer ${token}`,
      'X-Customer-ID': customerId,
      'Content-Type': 'application/json'
    };
  }

  async createAlertRule(ruleData) {
    try {
      const response = await axios.post(
        `${this.baseUrl}/v1/alerts/rules`,
        ruleData,
        { headers: this.headers }
      );
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create alert rule: ${error.response?.data?.detail}`);
    }
  }

  async listAlerts(filters = {}) {
    try {
      const response = await axios.get(
        `${this.baseUrl}/v1/alerts`,
        { 
          params: filters,
          headers: this.headers 
        }
      );
      return response.data;
    } catch (error) {
      throw new Error(`Failed to list alerts: ${error.response?.data?.detail}`);
    }
  }

  async createSlackChannel(channelConfig) {
    const channelData = {
      name: channelConfig.name,
      type: "slack",
      configuration: {
        webhook_url: channelConfig.webhook_url,
        channel: channelConfig.channel,
        username: "LogforgeBot",
        icon_emoji: ":warning:"
      },
      enabled: true
    };

    try {
      const response = await axios.post(
        `${this.baseUrl}/v1/alerts/notifications/channels`,
        channelData,
        { headers: this.headers }
      );
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create Slack channel: ${error.response?.data?.detail}`);
    }
  }
}

// Usage Example
async function setupAlertsSystem() {
  const client = new LogforgeAlertsClient(
    "http://localhost:7080",
    process.env.LOGFORGE_TOKEN,
    process.env.CUSTOMER_ID
  );

  try {
    // Setup Slack notification channel
    const slackChannel = await client.createSlackChannel({
      name: "Production Alerts",
      webhook_url: process.env.SLACK_WEBHOOK_URL,
      channel: "#alerts"
    });
    console.log(`Created Slack channel: ${slackChannel.channel.channel_id}`);

    // Create critical error alert rule
    const alertRule = await client.createAlertRule({
      name: "Critical System Errors",
      rule_type: "threshold",
      severity: "critical",
      conditions: [
        { field: "level", operator: "in", value: ["ERROR", "FATAL"] },
        { field: "environment", operator: "eq", value: "production" }
      ],
      notification_channels: ["slack"],
      evaluation_interval: 60,
      cooldown_period: 300
    });
    console.log(`Created alert rule: ${alertRule.rule_id}`);

    // Monitor for active alerts
    const alerts = await client.listAlerts({ status: "active" });
    console.log(`Found ${alerts.total} active alerts`);

  } catch (error) {
    console.error('Error setting up alerts system:', error.message);
  }
}

setupAlertsSystem();
```

## Error Handling

### HTTP Status Codes

- **200 OK**: Successful operation
- **400 Bad Request**: Invalid request data or parameters
- **401 Unauthorized**: Invalid or missing authentication token
- **403 Forbidden**: Insufficient permissions or subscription
- **404 Not Found**: Alert rule/instance not found
- **422 Unprocessable Entity**: Validation errors
- **500 Internal Server Error**: Server-side processing error

### Error Response Format

```json
{
  "detail": "Failed to create alert rule: Invalid severity level 'super_critical'. Must be one of: low, medium, high, critical"
}
```

### Common Error Scenarios

#### Rule Creation Errors
```json
{
  "detail": "Failed to create alert rule: Missing required field: name"
}
```

#### Rule Not Found
```json
{
  "detail": "Alert rule not found"
}
```

#### Invalid Operator
```json
{
  "detail": "Failed to create alert rule: Invalid rule type 'invalid_type'. Must be one of: threshold, anomaly, pattern, frequency, absence, sequence"
}
```

#### Subscription Validation
```json
{
  "detail": "subscription_not_found: Tenant subscription does not include alerts features"
}
```

#### Notification Channel Errors
```json
{
  "detail": "Failed to create notification channel: Slack channel requires 'webhook_url' or 'bot_token'"
}
```

### Error Handling Best Practices

```python
async def handle_alerts_api_errors(api_call):
    """Error handling wrapper for alerts API calls"""
    try:
        return await api_call()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print("Alert rule or instance not found")
        elif e.response.status_code == 403:
            print("Insufficient permissions or subscription")
        elif e.response.status_code == 422:
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
- **Rule Creation**: ~100-300ms (includes validation and persistence)
- **Rule Evaluation**: ~25-100ms per rule (depends on log volume)
- **Alert Listing**: ~50-200ms (pagination optimized)
- **Alert Acknowledgment**: ~25-75ms (simple status update)
- **Health Check**: ~15-50ms (database connectivity test)

### Throughput Limits
- **Rule Creation**: 10 requests/second per tenant
- **Alert Updates**: 50 requests/second per tenant
- **Alert Listing**: 100 requests/second per tenant
- **Rule Evaluation**: Up to 100 rules evaluated concurrently

### Database Optimization
- **Partitioning**: Tables partitioned by `customer_id` for multi-tenant isolation
- **Indexing**: Optimized indexes on `customer_id`, `status`, `severity`, `triggered_at`
- **Query Performance**: Sub-100ms for most operations on typical datasets
- **Pagination**: Efficient offset-based pagination with count optimization

## Real-Time Features

### Alert Engine Performance
- **Evaluation Frequency**: Every 5 minutes (configurable per rule)
- **Processing Latency**: <30 seconds from trigger to notification
- **Concurrent Evaluations**: Up to 100 rules evaluated simultaneously
- **Queue Processing**: High-priority alerts processed within 30 seconds
- **Retry Logic**: Failed notifications retried up to 3 times with exponential backoff

### Notification Delivery
- **Email**: ~200-1000ms delivery time
- **Slack/Teams**: ~100-500ms webhook delivery
- **Generic Webhooks**: ~200-5000ms (depends on external service)
- **Batching**: Multiple alerts batched within 2-minute windows
- **Failure Handling**: Automatic retry with circuit breaker pattern

## Best Practices

### For Operations Teams

1. **Start Simple**: Begin with basic threshold-based alerts before complex patterns
2. **Severity Management**: Reserve `critical` for actual emergencies requiring immediate response
3. **Notification Strategy**: Configure escalation chains with appropriate cooldown periods
4. **Rule Testing**: Always use test endpoint before enabling rules in production
5. **Alert Hygiene**: Regularly review and tune alert thresholds to reduce false positives
6. **Documentation**: Link alerts to runbooks and resolution procedures
7. **Monitoring**: Monitor alert engine health and notification success rates

### For Developers

1. **Structured Logging**: Ensure logs contain consistent fields suitable for alerting
2. **Context Enrichment**: Include relevant identifiers (trace_id, user_id, request_id)
3. **Gradual Rollout**: Test alerts in development/staging before production deployment
4. **Performance Monitoring**: Monitor alert evaluation performance and database impact
5. **Integration Testing**: Thoroughly test webhook integrations and payload formats
6. **Error Handling**: Implement proper error handling for all API interactions
7. **Rate Limiting**: Respect API rate limits and implement proper backoff strategies

### Alert Rule Design

#### Good Rule Examples

**High Error Rate Alert**:
```json
{
  "name": "Payment API Error Rate",
  "rule_type": "threshold",
  "conditions": [
    {"field": "level", "operator": "eq", "value": "ERROR"},
    {"field": "service", "operator": "eq", "value": "payment-api"}
  ],
  "filters": [
    {"field": "environment", "operator": "eq", "value": "production"}
  ],
  "severity": "high",
  "evaluation_interval": 300,
  "cooldown_period": 900
}
```

**Database Connection Issues**:
```json
{
  "name": "Database Connectivity",
  "rule_type": "pattern",
  "conditions": [
    {"field": "message", "operator": "regex", "value": "database.*timeout|connection.*failed|db.*unavailable"}
  ],
  "severity": "critical",
  "evaluation_interval": 60,
  "max_alerts_per_hour": 5
}
```

**Missing Heartbeats**:
```json
{
  "name": "Service Heartbeat Missing",
  "rule_type": "absence",
  "conditions": [
    {"field": "type", "operator": "eq", "value": "heartbeat"},
    {"field": "service", "operator": "eq", "value": "critical-service"}
  ],
  "severity": "critical",
  "evaluation_interval": 120,
  "cooldown_period": 600
}
```

### Security Considerations

1. **Multi-Tenant Isolation**: Complete alert data separation by tenant via `X-Customer-ID`
2. **Role-Based Access**: Granular permissions for different alert operations
3. **Webhook Security**: Use secure authentication tokens for external integrations
4. **Audit Logging**: Complete audit trail for all alert rule and instance operations
5. **Data Encryption**: All alert data encrypted at rest and in transit
6. **Rate Limiting**: Protection against alert spam and abuse
7. **Secure Notifications**: Avoid exposing sensitive data in alert messages

The Alerts Router API provides comprehensive, enterprise-grade alerting capabilities with robust rule management, multi-channel notifications, and complete alert lifecycle tracking to ensure critical issues are detected and resolved promptly.