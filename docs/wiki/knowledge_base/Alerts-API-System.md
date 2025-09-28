# Logforge Alerts API System

## Overview

The Alerts API (`/v1/alerts`) provides comprehensive real-time alerting and notification capabilities for the Logforge platform. This system enables automated monitoring, rule-based alerting, multi-channel notifications, and complete alert lifecycle management with enterprise-grade reliability and performance.

## Architecture

**Location**: `/apps/api/routers/alerts.py`  
**Service**: `AlertService` (dependency injection)  
**Authentication**: Required for all endpoints  
**Multi-Tenancy**: `X-Customer-ID` header required for all endpoints  
**Subscription**: Requires `alerts.*` features in subscription  

## Core Endpoint Categories

The Alerts API provides **15 endpoints** organized into 4 functional categories:

1. **Alert Rules Management** (6 endpoints) - Rule creation, testing, lifecycle
2. **Alert Instance Management** (5 endpoints) - Active alerts, acknowledgment, resolution
3. **Notification Channels** (2 endpoints) - Multi-channel notification setup
4. **Webhook Integrations** (2 endpoints) - External system integration

## 1. Alert Rules Management (6 endpoints)

### **POST /v1/alerts/rules** - Create Alert Rule
Create sophisticated alert rules with multiple rule types and conditions.

**Request Model**: `Dict[str, Any]`
```json
{
  "name": "High Error Rate Alert",
  "description": "Alert when error rate exceeds threshold",
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

**Response**: (200 OK)
```json
{
  "rule_id": "rule_abc123def456",
  "name": "High Error Rate Alert",
  "customer_id": "tenant-uuid",
  "enabled": true,
  "rule_type": "threshold",
  "severity": "critical",
  "created_at": "2024-01-01T12:00:00Z",
  "status": "active"
}
```

**Supported Rule Types**:
- **threshold**: Value exceeds/falls below threshold
- **frequency**: Event frequency within time window
- **pattern**: Complex pattern matching in logs
- **anomaly**: Statistical anomaly detection
- **absence**: Missing expected events
- **sequence**: Event sequence pattern detection

**Severity Levels**: `low`, `medium`, `high`, `critical`

### **GET /v1/alerts/rules** - List Alert Rules
List all alert rules with filtering and pagination.

**Query Parameters**:
- `enabled`: Filter by enabled status (boolean)
- `severity`: Filter by severity level (low, medium, high, critical)
- `limit`: Maximum results per page (default: 100, max: 1000)
- `offset`: Pagination offset (default: 0)

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
      "last_triggered": "2024-01-01T11:45:00Z",
      "trigger_count": 5
    }
  ],
  "total": 25,
  "limit": 100,
  "offset": 0,
  "customer_id": "tenant-uuid"
}
```

### **GET /v1/alerts/rules/{rule_id}** - Get Alert Rule
Retrieve detailed configuration for a specific alert rule.

**Response**: (200 OK)
```json
{
  "rule_id": "rule_abc123def456",
  "name": "High Error Rate Alert",
  "description": "Alert when error rate exceeds threshold",
  "rule_type": "threshold",
  "severity": "critical",
  "enabled": true,
  "evaluation_interval": 300,
  "cooldown_period": 600,
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
  "customer_id": "tenant-uuid",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T15:30:00Z",
  "statistics": {
    "total_triggers": 15,
    "last_triggered": "2024-01-01T11:45:00Z",
    "avg_evaluation_time_ms": 45
  }
}
```

### **PUT /v1/alerts/rules/{rule_id}** - Update Alert Rule
Update existing alert rule configuration.

**Request Model**: `AlertRuleUpdateRequest`
```json
{
  "description": "Updated alert description",
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
  "customer_id": "tenant-uuid",
  "status": "updated"
}
```

### **DELETE /v1/alerts/rules/{rule_id}** - Delete Alert Rule
Permanently delete an alert rule and stop all evaluations.

**Response**: (200 OK)
```json
{
  "status": "deleted",
  "rule_id": "rule_abc123def456",
  "customer_id": "tenant-uuid",
  "deleted_at": "2024-01-01T16:15:00Z"
}
```

### **POST /v1/alerts/rules/{rule_id}/test** - Test Alert Rule
Test alert rule evaluation against recent log data.

**Optional Request Body**: `Dict[str, Any]` (test parameters)
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
    "threshold_value": 10,
    "matched_logs": [
      {
        "timestamp": "2024-01-01T15:30:00Z",
        "level": "ERROR",
        "message": "Payment processing failed",
        "service": "payment-api"
      }
    ],
    "evaluation_time_ms": 45,
    "next_evaluation": "2024-01-01T16:05:00Z"
  },
  "customer_id": "tenant-uuid"
}
```

## 2. Alert Instance Management (5 endpoints)

### **GET /v1/alerts** - List Active Alerts
List all active, acknowledged, or resolved alerts with filtering.

**Query Parameters**:
- `status`: Filter by alert status (active, acknowledged, resolved)
- `severity`: Filter by severity level (low, medium, high, critical)
- `limit`: Maximum results per page (default: 100)
- `offset`: Pagination offset (default: 0)

**Response**: (200 OK)
```json
{
  "alerts": [
    {
      "alert_id": "alert_xyz789",
      "rule_id": "rule_abc123",
      "rule_name": "High Error Rate Alert",
      "status": "active",
      "severity": "critical",
      "triggered_at": "2024-01-01T15:30:00Z",
      "message": "Error rate exceeded threshold: 25 errors in 5 minutes",
      "conditions_met": [
        {
          "field": "level",
          "operator": "eq",
          "value": "ERROR",
          "actual_count": 25
        }
      ],
      "affected_services": ["payment-api"],
      "notification_status": {
        "email": "sent",
        "slack": "sent", 
        "pagerduty": "pending"
      }
    }
  ],
  "total": 8,
  "limit": 100,
  "offset": 0,
  "customer_id": "tenant-uuid"
}
```

### **GET /v1/alerts/stats** - Alert Engine Statistics
Get comprehensive alert engine performance and statistics.

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
  "customer_id": "tenant-uuid"
}
```

### **GET /v1/alerts/health** - Alert Engine Health
Get alert engine health status and diagnostics.

**Response**: (200 OK)
```json
{
  "status": "healthy",
  "active_rules": 23,
  "active_alerts": 8,
  "last_evaluation": "2024-01-01T16:00:00Z",
  "customer_id": "tenant-uuid",
  "checked_at": "2024-01-01T16:00:30Z"
}
```

**Health Status Values**:
- **healthy**: All systems operational
- **unhealthy**: Critical issues detected
- **unknown**: Unable to determine status

### **GET /v1/alerts/{alert_id}** - Get Alert Instance
Retrieve detailed information for a specific alert instance.

**Response**: (200 OK)
```json
{
  "alert_id": "alert_xyz789",
  "rule_id": "rule_abc123",
  "rule_name": "High Error Rate Alert",
  "status": "active",
  "severity": "critical",
  "triggered_at": "2024-01-01T15:30:00Z",
  "message": "Error rate exceeded threshold: 25 errors in 5 minutes",
  "conditions_met": [
    {
      "field": "level",
      "operator": "eq", 
      "value": "ERROR",
      "actual_count": 25,
      "threshold": 10
    }
  ],
  "context": {
    "query_window": {
      "start": "2024-01-01T15:25:00Z",
      "end": "2024-01-01T15:30:00Z"
    },
    "affected_logs": 25,
    "sample_logs": [
      {
        "timestamp": "2024-01-01T15:29:45Z",
        "level": "ERROR",
        "message": "Payment processing timeout",
        "service": "payment-api",
        "trace_id": "trace_abc123"
      }
    ]
  },
  "notifications": [
    {
      "channel": "email",
      "status": "sent",
      "sent_at": "2024-01-01T15:30:15Z",
      "recipients": ["ops-team@company.com"]
    },
    {
      "channel": "slack", 
      "status": "sent",
      "sent_at": "2024-01-01T15:30:20Z",
      "channel_name": "#alerts"
    }
  ],
  "customer_id": "tenant-uuid"
}
```

### **POST /v1/alerts/{alert_id}/acknowledge** - Acknowledge Alert
Mark an alert as acknowledged to stop further notifications.

**Request Model**: `AlertStatusUpdate`
```json
{
  "status": "acknowledged",
  "notes": "Investigating payment API issues"
}
```

**Response**: (200 OK)
```json
{
  "status": "acknowledged",
  "alert_id": "alert_xyz789",
  "customer_id": "tenant-uuid",
  "acknowledged_at": "2024-01-01T16:05:00Z",
  "acknowledged_by": "api-user"
}
```

### **POST /v1/alerts/{alert_id}/resolve** - Resolve Alert
Mark an alert as resolved with resolution notes.

**Request Model**: `AlertStatusUpdate`
```json
{
  "status": "resolved",
  "notes": "Fixed payment API timeout configuration"
}
```

**Response**: (200 OK)
```json
{
  "status": "resolved",
  "alert_id": "alert_xyz789",
  "customer_id": "tenant-uuid",
  "resolved_at": "2024-01-01T16:30:00Z",
  "resolved_by": "api-user",
  "resolution_notes": "Fixed payment API timeout configuration"
}
```

## 3. Notification Channels (2 endpoints)

### **GET /v1/alerts/notifications/channels** - List Notification Channels
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
        "subject_template": "🚨 Alert: {{rule_name}}"
      },
      "created_at": "2024-01-01T10:00:00Z",
      "last_used": "2024-01-01T15:30:00Z",
      "success_rate": 99.5
    },
    {
      "channel_id": "channel_slack_001", 
      "name": "Dev Team Slack",
      "type": "slack",
      "enabled": true,
      "configuration": {
        "webhook_url": "https://hooks.slack.com/...",
        "channel": "#alerts",
        "username": "LogforgeBot"
      },
      "created_at": "2024-01-01T10:00:00Z",
      "last_used": "2024-01-01T15:30:00Z",
      "success_rate": 100.0
    }
  ],
  "total": 5,
  "customer_id": "tenant-uuid"
}
```

**Supported Channel Types**:
- **email**: SMTP email notifications
- **slack**: Slack webhook integration
- **webhook**: Generic HTTP webhook
- **pagerduty**: PagerDuty incident creation
- **teams**: Microsoft Teams integration
- **sms**: SMS text message alerts

### **POST /v1/alerts/notifications/channels** - Create Notification Channel
Create a new notification channel for alert delivery.

**Request Examples by Type**:

**Email Channel**:
```json
{
  "name": "Critical Alerts Email",
  "type": "email",
  "configuration": {
    "recipients": ["critical-ops@company.com"],
    "subject_template": "🔥 CRITICAL: {{rule_name}}",
    "body_template": "Alert: {{message}}\nTriggered: {{triggered_at}}\nSeverity: {{severity}}"
  },
  "enabled": true
}
```

**Slack Channel**:
```json
{
  "name": "Dev Team Slack Alerts",
  "type": "slack", 
  "configuration": {
    "webhook_url": "https://hooks.slack.com/services/T123/B456/xyz",
    "channel": "#dev-alerts",
    "username": "LogforgeBot",
    "icon_emoji": ":warning:",
    "message_template": ":rotating_light: *{{rule_name}}*\n{{message}}"
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
  "customer_id": "tenant-uuid"
}
```

## 4. Webhook Integrations (2 endpoints)

### **GET /v1/alerts/integrations/webhooks** - List Webhook Integrations
List all webhook integrations for external system connectivity.

**Response**: (200 OK)
```json
{
  "webhooks": [
    {
      "channel_id": "webhook_servicenow_001",
      "name": "ServiceNow Integration", 
      "type": "webhook",
      "url": "https://company.service-now.com/api/logforge/alerts",
      "method": "POST",
      "headers": {
        "Authorization": "Bearer token_masked",
        "Content-Type": "application/json"
      },
      "enabled": true,
      "created_at": "2024-01-01T10:00:00Z",
      "last_used": "2024-01-01T15:30:00Z",
      "success_rate": 98.2,
      "recent_failures": 2
    }
  ],
  "total": 3,
  "customer_id": "tenant-uuid"
}
```

### **POST /v1/alerts/integrations/webhooks** - Create Webhook Integration
Create webhook integration for external system notifications.

**Request Examples**:

**ServiceNow Integration**:
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

**Generic Webhook**:
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
    "url": "https://company.service-now.com/api/incidents",
    "method": "POST",
    "enabled": true,
    "created_at": "2024-01-01T16:00:00Z"
  },
  "customer_id": "tenant-uuid"
}
```

## Data Models

### Core Models

**AlertStatusUpdate**:
```python
class AlertStatusUpdate(BaseModel):
    status: str  # acknowledged, resolved
    notes: Optional[str] = None
```

**AlertRuleUpdateRequest**:
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

### Rule Types & Operators

**Supported Operators**:
- **eq**: Equals
- **ne**: Not equals  
- **gt**: Greater than
- **gte**: Greater than or equal
- **lt**: Less than
- **lte**: Less than or equal
- **contains**: String contains
- **starts_with**: String starts with
- **ends_with**: String ends with
- **regex**: Regular expression match
- **in**: Value in list
- **not_in**: Value not in list

**Condition Examples**:
```json
{
  "field": "level",
  "operator": "in",
  "value": ["ERROR", "FATAL"]
}
```

```json
{
  "field": "response_time",
  "operator": "gt", 
  "value": 5000
}
```

```json
{
  "field": "message",
  "operator": "regex",
  "value": "timeout|connection.*failed"
}
```

## Authentication & Authorization

### Required Headers

**All endpoints require**:
- `Authorization: Bearer <jwt_token>` - Valid JWT token
- `X-Customer-ID: <tenant_id>` - Tenant context (UUID format)

### Permission Requirements

| Endpoint Category | Required Permissions | Role Examples |
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
  "subscription_tier": "smb"
}
```

## Error Handling

### HTTP Status Codes

- **200 OK**: Successful operation
- **404 Not Found**: Alert rule/instance not found
- **500 Internal Server Error**: Server-side processing error

### Error Response Format

```json
{
  "detail": "Failed to create alert rule: Invalid severity level"
}
```

### Common Errors

- **Rule not found**: Alert rule ID doesn't exist or belongs to different tenant
- **Alert not found**: Alert instance not found or already resolved
- **Invalid severity**: Severity must be low, medium, high, or critical
- **Invalid operator**: Unsupported condition operator
- **Notification failed**: Channel configuration error or external service unavailable

## Performance Characteristics

- **Rule Creation**: ~100-300ms (includes validation and persistence)
- **Rule Evaluation**: ~25-100ms per rule (depends on log volume)
- **Alert Listing**: ~50-200ms (pagination optimized)
- **Alert Acknowledgment**: ~25-75ms (simple status update)
- **Notification Delivery**: ~100-2000ms (depends on channel type)
- **Webhook Delivery**: ~200-5000ms (depends on external service)

## Real-Time Features

### Alert Engine Performance

- **Evaluation Frequency**: Every 5 minutes (configurable per rule)
- **Concurrent Evaluations**: Up to 100 rules evaluated simultaneously
- **Queue Processing**: High-priority alerts processed within 30 seconds
- **Notification Batching**: Multiple alerts batched within 2-minute windows
- **Retry Logic**: Failed notifications retried up to 3 times with exponential backoff

### Monitoring Capabilities

- **Rule Performance**: Tracks evaluation time, trigger frequency, false positive rates
- **Notification Success**: Monitors delivery success rates per channel type
- **System Health**: Real-time engine health monitoring with automatic recovery
- **Alert Correlation**: Groups related alerts to reduce notification noise
- **Escalation Policies**: Automatic escalation for unacknowledged critical alerts

## Integration Points

### External Systems

- **ITSM Platforms**: ServiceNow, Jira Service Management
- **Communication**: Slack, Microsoft Teams, email
- **Incident Management**: PagerDuty, Opsgenie, VictorOps
- **SIEM Systems**: Splunk, Elastic Security, QRadar
- **Custom Webhooks**: Generic HTTP integrations

### Internal Dependencies

- **Query Engine**: Log data analysis for rule evaluation
- **Ingestion System**: Real-time log processing pipeline
- **User Management**: Role-based access control
- **Tenant System**: Multi-tenant data isolation
- **Subscription System**: Feature access validation

## Security Features

1. **Multi-Tenant Isolation**: Complete alert data separation by tenant
2. **Role-Based Access**: Granular permissions for alert operations
3. **Webhook Security**: Token-based authentication for external integrations
4. **Audit Logging**: Complete audit trail for all alert operations
5. **Rate Limiting**: Protection against alert spam and abuse
6. **Data Encryption**: All alert data encrypted at rest and in transit
7. **Secure Notifications**: Encrypted channels for sensitive alert content

## Best Practices

### For Operations Teams

1. **Start with Basic Rules**: Begin with simple threshold-based alerts
2. **Use Appropriate Severity**: Reserve critical for actual emergencies
3. **Configure Escalation**: Set up proper notification escalation chains
4. **Test Alert Rules**: Use test functionality before enabling rules
5. **Monitor False Positives**: Regularly review and tune alert thresholds
6. **Organize by Service**: Group alerts logically by service or component
7. **Document Runbooks**: Link alerts to resolution procedures

### For Developers

1. **Structured Logging**: Ensure logs contain fields suitable for alerting
2. **Alert Context**: Include relevant identifiers (trace_id, user_id, etc.)
3. **Gradual Rollout**: Test alerts in development before production
4. **Alert Hygiene**: Regularly clean up obsolete or redundant rules
5. **Performance Monitoring**: Monitor alert evaluation performance
6. **Integration Testing**: Test webhook integrations thoroughly

The Alerts API provides enterprise-grade alerting capabilities with comprehensive rule management, multi-channel notifications, and complete alert lifecycle tracking to ensure critical issues are detected and resolved promptly.