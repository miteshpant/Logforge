# Alert Rules Guide

This guide provides comprehensive examples of alert rule types available in Logforge and the log patterns that trigger them.

## Overview

Logforge supports multiple alert rule types with nested condition evaluation:
- **Threshold Rules**: Count-based alerts with time windows
- **Pattern Rules**: Regex and text pattern matching
- **Anomaly Rules**: Statistical anomaly detection
- **Frequency Rules**: Rate-based detection
- **Absence Rules**: Missing log detection
- **Sequence Rules**: Event sequence detection

All rule types support nested conditions with `AND`, `OR`, and `NOT` logical operators for complex scenarios.

## Threshold Rules

### Example 1: High Error Rate Alert

**Use Case**: Detect when error logs exceed 5 occurrences in 5 minutes

```json
{
  "name": "High Error Rate Alert",
  "rule_type": "threshold",
  "is_enabled": true,
  "cooldown_minutes": 10,
  "condition_config": {
    "operator": "AND",
    "conditions": [
      {
        "field": "level",
        "operator": "eq",
        "value": "error"
      },
      {
        "field": "service",
        "operator": "eq", 
        "value": "api-gateway"
      }
    ]
  },
  "threshold_config": {
    "count": 5,
    "time_window_minutes": 5,
    "comparison": "gte"
  }
}
```

**Matching Logs**:
```json
[
  {
    "ts": "2025-01-21T10:00:00Z",
    "level": "error",
    "service": "api-gateway",
    "msg": "Database connection failed",
    "host": "api-01"
  },
  {
    "ts": "2025-01-21T10:01:00Z", 
    "level": "error",
    "service": "api-gateway",
    "msg": "Authentication timeout",
    "host": "api-02"
  },
  {
    "ts": "2025-01-21T10:02:00Z",
    "level": "error", 
    "service": "api-gateway",
    "msg": "Rate limit exceeded",
    "host": "api-01"
  }
]
```

### Example 2: Critical Security Events

**Use Case**: Immediate alert for any critical security event

```json
{
  "name": "Critical Security Alert",
  "rule_type": "threshold", 
  "is_enabled": true,
  "cooldown_minutes": 5,
  "condition_config": {
    "operator": "AND",
    "conditions": [
      {
        "field": "level",
        "operator": "eq",
        "value": "critical"
      },
      {
        "operator": "OR",
        "conditions": [
          {
            "field": "event_type",
            "operator": "contains",
            "value": "security"
          },
          {
            "field": "category",
            "operator": "eq",
            "value": "auth_failure"
          }
        ]
      }
    ]
  },
  "threshold_config": {
    "count": 1,
    "time_window_minutes": 1,
    "comparison": "gte"
  }
}
```

**Matching Log**:
```json
{
  "ts": "2025-01-21T10:15:00Z",
  "level": "critical",
  "service": "auth-service",
  "event_type": "security_breach",
  "category": "auth_failure", 
  "msg": "Multiple failed admin login attempts detected",
  "source_ip": "192.168.1.100",
  "user": "admin"
}
```

## Pattern Rules

### Example 1: SQL Injection Detection

**Use Case**: Detect potential SQL injection attacks in web logs

```json
{
  "name": "SQL Injection Detection",
  "rule_type": "pattern",
  "is_enabled": true,
  "cooldown_minutes": 15,
  "condition_config": {
    "operator": "AND",
    "conditions": [
      {
        "field": "service",
        "operator": "eq",
        "value": "web-app"
      },
      {
        "operator": "OR",
        "conditions": [
          {
            "field": "request_uri",
            "operator": "regex",
            "value": "(union|select|insert|delete|drop|exec)\\s"
          },
          {
            "field": "request_body",
            "operator": "regex", 
            "value": "'\\s*(or|and)\\s*'.*'\\s*="
          }
        ]
      }
    ]
  }
}
```

**Matching Log**:
```json
{
  "ts": "2025-01-21T11:00:00Z",
  "level": "warn",
  "service": "web-app",
  "request_uri": "/api/users?id=1' OR '1'='1",
  "request_method": "GET",
  "source_ip": "203.0.113.45",
  "user_agent": "Mozilla/5.0 (suspicious)",
  "msg": "Suspicious query parameter detected"
}
```

### Example 2: Privilege Escalation Attempts

**Use Case**: Detect Unix/Linux privilege escalation commands

```json
{
  "name": "Privilege Escalation Detection",
  "rule_type": "pattern",
  "is_enabled": true,
  "cooldown_minutes": 5,
  "condition_config": {
    "operator": "AND",
    "conditions": [
      {
        "field": "host_type",
        "operator": "eq",
        "value": "linux"
      },
      {
        "operator": "OR",
        "conditions": [
          {
            "field": "command",
            "operator": "regex",
            "value": "sudo\\s+(su|passwd|usermod|chmod\\s+[47]77)"
          },
          {
            "field": "msg",
            "operator": "contains",
            "value": "setuid"
          }
        ]
      }
    ]
  }
}
```

**Matching Log**:
```json
{
  "ts": "2025-01-21T11:30:00Z",
  "level": "info",
  "service": "system-audit",
  "host_type": "linux",
  "host": "web-server-01",
  "user": "webuser",
  "command": "sudo chmod 777 /etc/passwd",
  "msg": "Privilege escalation attempt detected"
}
```

## Anomaly Rules

### Example 1: Unusual Data Transfer Volume

**Use Case**: Detect abnormal data transfer patterns that might indicate data exfiltration

```json
{
  "name": "Data Exfiltration Detection",
  "rule_type": "anomaly",
  "is_enabled": true,
  "cooldown_minutes": 30,
  "condition_config": {
    "operator": "AND",
    "conditions": [
      {
        "field": "event_type",
        "operator": "eq",
        "value": "data_transfer"
      },
      {
        "field": "bytes_transferred",
        "operator": "gt",
        "value": "1000000"
      }
    ]
  },
  "anomaly_config": {
    "baseline_days": 7,
    "threshold_std_dev": 3.0,
    "metric_field": "bytes_transferred"
  }
}
```

**Matching Log**:
```json
{
  "ts": "2025-01-21T14:00:00Z",
  "level": "info",
  "service": "file-service",
  "event_type": "data_transfer",
  "user": "john.doe",
  "source_file": "/sensitive/customer_data.db",
  "destination": "external_storage",
  "bytes_transferred": 15000000,
  "msg": "Large file transfer completed"
}
```

### Example 2: Unusual Login Pattern

**Use Case**: Detect login attempts from unusual locations or times

```json
{
  "name": "Unusual Login Pattern",
  "rule_type": "anomaly",
  "is_enabled": true,
  "cooldown_minutes": 60,
  "condition_config": {
    "operator": "AND",
    "conditions": [
      {
        "field": "event_type",
        "operator": "eq",
        "value": "user_login"
      },
      {
        "field": "login_status",
        "operator": "eq",
        "value": "success"
      }
    ]
  },
  "anomaly_config": {
    "baseline_days": 14,
    "threshold_std_dev": 2.5,
    "grouping_fields": ["user", "source_country"]
  }
}
```

**Matching Log**:
```json
{
  "ts": "2025-01-21T02:30:00Z",
  "level": "info",
  "service": "auth-service",
  "event_type": "user_login",
  "login_status": "success",
  "user": "alice.smith",
  "source_ip": "185.220.101.23",
  "source_country": "Russia",
  "user_agent": "Chrome/120.0",
  "msg": "User login from unusual location"
}
```

## Frequency Rules

### Example 1: Brute Force Attack Detection

**Use Case**: Detect rapid failed login attempts indicating brute force attacks

```json
{
  "name": "Brute Force Attack Detection",
  "rule_type": "frequency",
  "is_enabled": true,
  "cooldown_minutes": 20,
  "condition_config": {
    "operator": "AND",
    "conditions": [
      {
        "field": "event_type",
        "operator": "eq",
        "value": "login_attempt"
      },
      {
        "field": "login_status",
        "operator": "eq",
        "value": "failed"
      }
    ]
  },
  "threshold_config": {
    "count": 10,
    "time_window_minutes": 5,
    "comparison": "gte"
  }
}
```

**Matching Logs** (10 failed attempts in 5 minutes):
```json
[
  {
    "ts": "2025-01-21T09:00:00Z",
    "level": "warn",
    "service": "auth-service",
    "event_type": "login_attempt",
    "login_status": "failed",
    "user": "admin",
    "source_ip": "192.168.1.50",
    "reason": "invalid_password"
  },
  {
    "ts": "2025-01-21T09:00:30Z",
    "level": "warn", 
    "service": "auth-service",
    "event_type": "login_attempt",
    "login_status": "failed",
    "user": "admin",
    "source_ip": "192.168.1.50",
    "reason": "invalid_password"
  }
]
```

### Example 2: API Rate Limit Violations

**Use Case**: Detect excessive API usage patterns

```json
{
  "name": "API Rate Limit Violations",
  "rule_type": "frequency",
  "is_enabled": true,
  "cooldown_minutes": 10,
  "condition_config": {
    "operator": "AND",
    "conditions": [
      {
        "field": "service",
        "operator": "eq",
        "value": "api-gateway"
      },
      {
        "field": "response_code",
        "operator": "eq",
        "value": "429"
      }
    ]
  },
  "threshold_config": {
    "count": 20,
    "time_window_minutes": 2,
    "comparison": "gte"
  }
}
```

**Matching Log**:
```json
{
  "ts": "2025-01-21T12:00:00Z",
  "level": "warn",
  "service": "api-gateway",
  "endpoint": "/api/v1/data",
  "response_code": "429",
  "source_ip": "10.0.1.25",
  "api_key": "key_abc123",
  "msg": "Rate limit exceeded for API key"
}
```

## Absence Rules

### Example 1: Missing Health Check

**Use Case**: Alert when expected health check logs are missing

```json
{
  "name": "Missing Health Check Alert",
  "rule_type": "absence",
  "is_enabled": true,
  "cooldown_minutes": 15,
  "condition_config": {
    "operator": "AND",
    "conditions": [
      {
        "field": "service",
        "operator": "eq",
        "value": "payment-service"
      },
      {
        "field": "event_type",
        "operator": "eq",
        "value": "health_check"
      }
    ]
  },
  "absence_config": {
    "expected_interval_minutes": 5,
    "alert_after_minutes": 10
  }
}
```

**Expected Log** (should appear every 5 minutes):
```json
{
  "ts": "2025-01-21T13:00:00Z",
  "level": "info",
  "service": "payment-service",
  "event_type": "health_check",
  "status": "healthy",
  "response_time_ms": 45,
  "msg": "Health check completed successfully"
}
```

### Example 2: Missing Backup Completion

**Use Case**: Alert when daily backup logs are missing

```json
{
  "name": "Missing Backup Alert",
  "rule_type": "absence", 
  "is_enabled": true,
  "cooldown_minutes": 60,
  "condition_config": {
    "operator": "AND",
    "conditions": [
      {
        "field": "service",
        "operator": "eq",
        "value": "backup-service"
      },
      {
        "field": "event_type",
        "operator": "eq",
        "value": "backup_completed"
      }
    ]
  },
  "absence_config": {
    "expected_interval_minutes": 1440,
    "alert_after_minutes": 1500
  }
}
```

**Expected Log** (should appear daily):
```json
{
  "ts": "2025-01-21T02:00:00Z",
  "level": "info",
  "service": "backup-service",
  "event_type": "backup_completed",
  "backup_size_gb": 25.4,
  "duration_minutes": 45,
  "backup_location": "s3://backups/daily/2025-01-21",
  "msg": "Daily backup completed successfully"
}
```

## Sequence Rules

### Example 1: Suspicious Login Sequence

**Use Case**: Detect successful login immediately after multiple failed attempts

```json
{
  "name": "Suspicious Login Sequence",
  "rule_type": "sequence",
  "is_enabled": true,
  "cooldown_minutes": 30,
  "condition_config": {
    "operator": "AND",
    "conditions": [
      {
        "field": "event_type",
        "operator": "eq",
        "value": "login_attempt"
      },
      {
        "field": "user",
        "operator": "eq",
        "value": "admin"
      }
    ]
  },
  "sequence_config": {
    "events": [
      {
        "condition": {
          "field": "login_status",
          "operator": "eq",
          "value": "failed"
        },
        "min_occurrences": 3,
        "max_time_between_minutes": 10
      },
      {
        "condition": {
          "field": "login_status", 
          "operator": "eq",
          "value": "success"
        },
        "min_occurrences": 1,
        "max_time_between_minutes": 5
      }
    ]
  }
}
```

**Matching Log Sequence**:
```json
[
  {
    "ts": "2025-01-21T15:00:00Z",
    "level": "warn",
    "service": "auth-service",
    "event_type": "login_attempt",
    "login_status": "failed",
    "user": "admin",
    "source_ip": "203.0.113.10"
  },
  {
    "ts": "2025-01-21T15:02:00Z",
    "level": "warn",
    "service": "auth-service", 
    "event_type": "login_attempt",
    "login_status": "failed",
    "user": "admin",
    "source_ip": "203.0.113.10"
  },
  {
    "ts": "2025-01-21T15:04:00Z",
    "level": "warn",
    "service": "auth-service",
    "event_type": "login_attempt", 
    "login_status": "failed",
    "user": "admin",
    "source_ip": "203.0.113.10"
  },
  {
    "ts": "2025-01-21T15:06:00Z",
    "level": "info",
    "service": "auth-service",
    "event_type": "login_attempt",
    "login_status": "success", 
    "user": "admin",
    "source_ip": "203.0.113.10"
  }
]
```

### Example 2: Attack Chain Detection

**Use Case**: Detect multi-stage attack progression

```json
{
  "name": "Attack Chain Detection",
  "rule_type": "sequence",
  "is_enabled": true,
  "cooldown_minutes": 60,
  "condition_config": {
    "operator": "AND", 
    "conditions": [
      {
        "field": "source_ip",
        "operator": "eq",
        "value": "203.0.113.45"
      }
    ]
  },
  "sequence_config": {
    "events": [
      {
        "condition": {
          "field": "event_type",
          "operator": "eq",
          "value": "port_scan"
        },
        "min_occurrences": 1,
        "max_time_between_minutes": 30
      },
      {
        "condition": {
          "field": "event_type",
          "operator": "eq", 
          "value": "vulnerability_probe"
        },
        "min_occurrences": 1,
        "max_time_between_minutes": 20
      },
      {
        "condition": {
          "field": "event_type",
          "operator": "eq",
          "value": "exploit_attempt"
        },
        "min_occurrences": 1,
        "max_time_between_minutes": 10
      }
    ]
  }
}
```

**Matching Log Sequence**:
```json
[
  {
    "ts": "2025-01-21T16:00:00Z",
    "level": "warn",
    "service": "firewall",
    "event_type": "port_scan",
    "source_ip": "203.0.113.45",
    "target_ports": "22,80,443,8080",
    "msg": "Port scan detected"
  },
  {
    "ts": "2025-01-21T16:15:00Z",
    "level": "warn",
    "service": "waf",
    "event_type": "vulnerability_probe",
    "source_ip": "203.0.113.45",
    "target_path": "/admin/.env",
    "msg": "Directory traversal attempt"
  },
  {
    "ts": "2025-01-21T16:25:00Z",
    "level": "critical",
    "service": "waf",
    "event_type": "exploit_attempt",
    "source_ip": "203.0.113.45",
    "payload": "../../../../etc/passwd",
    "msg": "RCE exploit attempt blocked"
  }
]
```

## Complex Nested Conditions

### Example: Multi-Layer Security Rule

**Use Case**: Comprehensive security rule with multiple conditions and exclusions

```json
{
  "name": "Advanced Security Monitoring",
  "rule_type": "threshold",
  "is_enabled": true,
  "cooldown_minutes": 15,
  "condition_config": {
    "operator": "AND",
    "conditions": [
      {
        "operator": "OR",
        "conditions": [
          {
            "field": "level",
            "operator": "eq",
            "value": "error"
          },
          {
            "field": "level", 
            "operator": "eq",
            "value": "critical"
          }
        ]
      },
      {
        "operator": "AND",
        "conditions": [
          {
            "field": "service",
            "operator": "in",
            "value": ["auth-service", "payment-service", "user-service"]
          },
          {
            "operator": "OR",
            "conditions": [
              {
                "field": "event_type",
                "operator": "contains",
                "value": "security"
              },
              {
                "field": "msg",
                "operator": "regex",
                "value": "(attack|breach|unauthorized|malicious)"
              }
            ]
          }
        ]
      },
      {
        "operator": "NOT",
        "condition": {
          "field": "user",
          "operator": "in",
          "value": ["system", "healthcheck", "monitoring"]
        }
      }
    ]
  },
  "threshold_config": {
    "count": 3,
    "time_window_minutes": 10,
    "comparison": "gte"
  }
}
```

**Matching Log**:
```json
{
  "ts": "2025-01-21T17:00:00Z",
  "level": "critical",
  "service": "auth-service",
  "event_type": "security_violation",
  "user": "attacker_user",
  "source_ip": "192.168.1.99",
  "msg": "Unauthorized access attempt detected - malicious payload blocked",
  "threat_score": 85
}
```

## Rule Configuration Best Practices

### 1. Cooldown Periods
- **High-frequency events**: 5-10 minutes
- **Security incidents**: 15-30 minutes  
- **System health**: 10-15 minutes
- **Business metrics**: 30-60 minutes

### 2. Threshold Settings
- Start conservative and tune based on baseline
- Consider time zones and business hours
- Account for seasonal patterns
- Use multiple severity levels

### 3. Condition Design
- Use specific field matches when possible
- Leverage nested conditions for complex logic
- Include exclusions for known false positives
- Test rules with historical data

### 4. Notification Strategy
- Route critical alerts to immediate channels (PagerDuty, SMS)
- Use email for informational alerts
- Implement escalation policies
- Consider alert grouping and deduplication

## Testing Your Rules

Use the Alert Rule Testing API to validate rules before deployment:

```bash
# Test rule against sample logs
curl -X POST "http://localhost:7080/v1/alerts/rules/test" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Customer-ID: YOUR_TENANT_ID" \
  -d '{
    "rule": {
      "name": "Test Rule",
      "rule_type": "threshold", 
      "condition_config": {...},
      "threshold_config": {...}
    },
    "test_logs": [...]
  }'
```

This comprehensive guide covers the major alert rule types and patterns. Customize these examples based on your specific infrastructure, applications, and security requirements.