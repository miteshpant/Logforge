# Security Analytics APIs

## Overview

The Security Analytics APIs provide comprehensive SIEM (Security Information and Event Management) capabilities including Sigma-based detection rules, threat intelligence, MITRE ATT&CK framework integration, and proactive threat hunting. These APIs enable security teams to detect, investigate, and respond to security threats in real-time.

**Base Path**: `/v1/security`  
**Total Endpoints**: 15+  
**Authentication Required**: Yes (Bearer token + X-Customer-ID header)  
**Required Roles**: `security_analyst`, `admin` or higher

## Core Security Features

### 1. Security Health Check
```http
GET /v1/security/health
```

**Description**: Get security analytics engine health and status

**Authentication**: Required

**Response** (200):
```json
{
  "status": "healthy",
  "detection_engine": {
    "status": "running",
    "rules_loaded": 45,
    "rules_active": 42,
    "rules_error": 3,
    "last_rule_update": "2024-01-20T15:30:00Z"
  },
  "threat_intelligence": {
    "status": "healthy",
    "indicators_loaded": 12500,
    "last_update": "2024-01-20T14:45:00Z",
    "feeds_active": 8
  },
  "event_processing": {
    "events_per_second": 850,
    "queue_depth": 125,
    "processing_latency_ms": 45
  },
  "mitre_attack": {
    "techniques_mapped": 284,
    "last_update": "2024-01-15T10:00:00Z"
  }
}
```

### 2. Security Dashboard
```http
GET /v1/security/dashboard
```

**Description**: Get comprehensive security overview dashboard data

**Authentication**: Required

**Query Parameters**:
- `time_range` (string, default: "24h"): Time range for analysis
- `include_mitre` (boolean, default: true): Include MITRE ATT&CK data

**Response** (200):
```json
{
  "time_range": "24h",
  "summary": {
    "total_events": 1250,
    "high_severity_events": 15,
    "medium_severity_events": 78,
    "low_severity_events": 1157,
    "events_requiring_action": 23,
    "threat_level": "medium"
  },
  "events_by_severity": [
    {"severity": "critical", "count": 3, "change_24h": "+2"},
    {"severity": "high", "count": 12, "change_24h": "-1"},
    {"severity": "medium", "count": 78, "change_24h": "+15"},
    {"severity": "low", "count": 1157, "change_24h": "+89"}
  ],
  "top_triggered_rules": [
    {
      "rule_id": "brute_force_detection",
      "rule_name": "Brute Force Login Attempts",
      "trigger_count": 45,
      "severity": "high",
      "mitre_techniques": ["T1110"]
    }
  ],
  "mitre_attack_coverage": {
    "techniques_detected": 12,
    "tactics_covered": 8,
    "top_tactics": [
      {"tactic": "Initial Access", "technique_count": 4},
      {"tactic": "Persistence", "technique_count": 3},
      {"tactic": "Privilege Escalation", "technique_count": 2}
    ]
  },
  "threat_intelligence_hits": {
    "total": 8,
    "malicious_ips": 5,
    "suspicious_domains": 2,
    "known_malware_hashes": 1
  }
}
```

## Sigma Detection Rules

### 3. List Sigma Rules
```http
GET /v1/security/sigma-rules
```

**Description**: List all Sigma detection rules

**Authentication**: Required

**Query Parameters**:
- `enabled` (boolean, optional): Filter by enabled status
- `severity` (string, optional): Filter by severity (low, medium, high, critical)
- `category` (string, optional): Filter by rule category
- `limit` (integer, default: 50): Maximum rules to return
- `offset` (integer, default: 0): Number of rules to skip

**Response** (200):
```json
{
  "rules": [
    {
      "id": "sigma_001",
      "name": "Brute Force Detection",
      "description": "Detects multiple failed login attempts from same source",
      "severity": "high",
      "category": "authentication",
      "enabled": true,
      "mitre_techniques": ["T1110.001", "T1110.003"],
      "detection_count_24h": 45,
      "last_triggered": "2024-01-20T15:30:00Z",
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-18T14:30:00Z"
    },
    {
      "id": "sigma_002", 
      "name": "Suspicious PowerShell Execution",
      "description": "Detects potentially malicious PowerShell commands",
      "severity": "medium",
      "category": "execution",
      "enabled": true,
      "mitre_techniques": ["T1059.001"],
      "detection_count_24h": 12,
      "last_triggered": "2024-01-20T14:15:00Z"
    }
  ],
  "total": 45,
  "enabled_count": 42,
  "disabled_count": 3
}
```

### 4. Create Sigma Rule
```http
POST /v1/security/sigma-rules
```

**Description**: Create new Sigma detection rule

**Authentication**: Required (security_analyst role)

**Request Body**:
```json
{
  "name": "Suspicious File Downloads",
  "description": "Detects downloads of potentially malicious file types",
  "severity": "medium",
  "category": "network",
  "enabled": true,
  "sigma_rule": {
    "title": "Suspicious File Downloads",
    "status": "stable",
    "description": "Detects downloads of executable files from suspicious domains",
    "detection": {
      "selection": {
        "event_type": "http_request",
        "method": "GET",
        "file_extension": [".exe", ".bat", ".ps1", ".scr"]
      },
      "suspicious_domains": {
        "domain": [
          "*.tempfile.net",
          "*.malicious-site.com"
        ]
      },
      "condition": "selection and suspicious_domains"
    },
    "falsepositives": [
      "Legitimate software downloads from corporate domains"
    ],
    "level": "medium"
  },
  "mitre_techniques": ["T1566.001", "T1204.002"],
  "custom_fields": {
    "team": "security_operations",
    "review_date": "2024-04-01"
  }
}
```

**Response** (201):
```json
{
  "id": "sigma_046",
  "name": "Suspicious File Downloads",
  "status": "active",
  "enabled": true,
  "created_at": "2024-01-20T16:00:00Z",
  "message": "Sigma rule created successfully"
}
```

### 5. Get Sigma Rule Details
```http
GET /v1/security/sigma-rules/{rule_id}
```

**Description**: Get detailed information for specific Sigma rule

**Authentication**: Required

**Path Parameters**:
- `rule_id` (string): Rule identifier

**Response** (200):
```json
{
  "id": "sigma_001",
  "name": "Brute Force Detection", 
  "description": "Detects multiple failed login attempts from same source",
  "severity": "high",
  "category": "authentication",
  "enabled": true,
  "sigma_rule": {
    "title": "Brute Force Detection",
    "status": "stable",
    "description": "Detects brute force login attempts",
    "detection": {
      "selection": {
        "event_type": "authentication",
        "result": "failed"
      },
      "timeframe": "5m",
      "condition": "selection | count() > 10"
    },
    "level": "high"
  },
  "mitre_techniques": ["T1110.001", "T1110.003"],
  "statistics": {
    "total_detections": 1250,
    "detections_24h": 45,
    "false_positives": 12,
    "accuracy_rate": 0.96
  },
  "created_by": "security_analyst_01",
  "created_at": "2024-01-15T10:00:00Z",
  "last_modified": "2024-01-18T14:30:00Z"
}
```

### 6. Update Sigma Rule
```http
PUT /v1/security/sigma-rules/{rule_id}
```

**Description**: Update existing Sigma rule

**Authentication**: Required (security_analyst role)

**Path Parameters**:
- `rule_id` (string): Rule identifier

**Request Body**:
```json
{
  "enabled": false,
  "severity": "medium",
  "description": "Updated description with additional context",
  "sigma_rule": {
    "detection": {
      "condition": "selection | count() > 15"
    }
  }
}
```

**Response** (200):
```json
{
  "id": "sigma_001",
  "message": "Sigma rule updated successfully",
  "updated_at": "2024-01-20T16:15:00Z",
  "changes": {
    "enabled": "true -> false",
    "severity": "high -> medium", 
    "detection_threshold": "10 -> 15"
  }
}
```

### 7. Test Sigma Rule
```http
POST /v1/security/sigma-rules/{rule_id}/test
```

**Description**: Test Sigma rule against sample or live data

**Authentication**: Required

**Path Parameters**:
- `rule_id` (string): Rule identifier

**Request Body**:
```json
{
  "test_type": "sample_data",
  "time_range": {
    "start": "2024-01-20T00:00:00Z",
    "end": "2024-01-20T23:59:59Z"
  },
  "sample_events": [
    {
      "timestamp": "2024-01-20T15:30:00Z",
      "event_type": "authentication",
      "result": "failed",
      "source_ip": "192.168.1.100",
      "username": "admin"
    }
  ]
}
```

**Response** (200):
```json
{
  "test_id": "test_123",
  "rule_id": "sigma_001",
  "test_type": "sample_data",
  "results": {
    "matched": true,
    "match_count": 1,
    "execution_time_ms": 15,
    "matched_events": [
      {
        "event_id": "evt_456",
        "timestamp": "2024-01-20T15:30:00Z",
        "confidence": 0.95,
        "matched_fields": ["event_type", "result"]
      }
    ]
  },
  "performance": {
    "cpu_usage_ms": 8,
    "memory_usage_mb": 2.1,
    "estimated_production_load": "low"
  }
}
```

### 8. Delete Sigma Rule
```http
DELETE /v1/security/sigma-rules/{rule_id}
```

**Description**: Delete Sigma rule

**Authentication**: Required (admin role)

**Path Parameters**:
- `rule_id` (string): Rule identifier

**Response** (200):
```json
{
  "message": "Sigma rule deleted successfully",
  "rule_id": "sigma_001",
  "deleted_at": "2024-01-20T16:30:00Z"
}
```

## Security Events Management

### 9. List Security Events
```http
GET /v1/security/events
```

**Description**: List security events and detections

**Authentication**: Required

**Query Parameters**:
- `status` (string, optional): Filter by status (new, investigating, resolved)
- `severity` (string, optional): Filter by severity
- `assigned_to` (string, optional): Filter by assignee
- `rule_id` (string, optional): Filter by triggering rule
- `limit` (integer, default: 50): Maximum events to return
- `offset` (integer, default: 0): Number of events to skip
- `start_time` (string, optional): Start time filter
- `end_time` (string, optional): End time filter

**Response** (200):
```json
{
  "events": [
    {
      "id": "event_789",
      "title": "Brute Force Attack Detected",
      "description": "Multiple failed login attempts from 192.168.1.100",
      "severity": "high",
      "status": "investigating",
      "confidence": 0.95,
      "rule_id": "sigma_001",
      "rule_name": "Brute Force Detection",
      "mitre_techniques": ["T1110.001"],
      "source_ip": "192.168.1.100",
      "target_user": "admin",
      "event_count": 15,
      "first_seen": "2024-01-20T15:25:00Z",
      "last_seen": "2024-01-20T15:35:00Z",
      "assigned_to": "analyst_01",
      "tags": ["authentication", "brute_force"]
    }
  ],
  "total": 156,
  "new_count": 23,
  "investigating_count": 45,
  "resolved_count": 88
}
```

### 10. Update Security Event Status
```http
PUT /v1/security/events/{event_id}/status
```

**Description**: Update security event status and investigation details

**Authentication**: Required

**Path Parameters**:
- `event_id` (string): Event identifier

**Request Body**:
```json
{
  "status": "investigating",
  "assigned_to": "analyst_02",
  "notes": "Investigating source IP, appears to be automated attack",
  "tags": ["confirmed_threat", "external_source"],
  "severity": "high",
  "false_positive": false
}
```

**Response** (200):
```json
{
  "id": "event_789",
  "status": "investigating", 
  "assigned_to": "analyst_02",
  "updated_at": "2024-01-20T16:45:00Z",
  "status_history": [
    {
      "status": "new",
      "timestamp": "2024-01-20T15:30:00Z",
      "updated_by": "system"
    },
    {
      "status": "investigating",
      "timestamp": "2024-01-20T16:45:00Z",
      "updated_by": "analyst_02",
      "notes": "Investigating source IP, appears to be automated attack"
    }
  ]
}
```

### 11. Security Events Stream
```http
GET /v1/security/events/stream
```

**Description**: Real-time stream of security events (WebSocket or Server-Sent Events)

**Authentication**: Required

**Query Parameters**:
- `severity` (string, optional): Filter by minimum severity
- `format` (string, default: "sse"): Stream format (sse, websocket)

**Response** (Server-Sent Events):
```
data: {"id":"event_790","title":"Suspicious PowerShell Execution","severity":"medium","timestamp":"2024-01-20T16:50:00Z"}

data: {"id":"event_791","title":"Malware Communication Detected","severity":"high","timestamp":"2024-01-20T16:52:00Z"}
```

## Threat Intelligence

### 12. List Threat Intelligence Indicators
```http
GET /v1/security/threat-intel
```

**Description**: List threat intelligence indicators (IOCs)

**Authentication**: Required

**Query Parameters**:
- `type` (string, optional): Filter by IOC type (ip, domain, hash, url)
- `threat_type` (string, optional): Filter by threat type (malware, c2, phishing)
- `confidence` (integer, optional): Minimum confidence level (0-100)
- `active` (boolean, default: true): Filter active indicators
- `limit` (integer, default: 100): Maximum indicators to return

**Response** (200):
```json
{
  "indicators": [
    {
      "id": "ioc_001",
      "type": "ip",
      "value": "192.168.100.50",
      "threat_type": "c2",
      "confidence": 95,
      "source": "threat_feed_alpha",
      "first_seen": "2024-01-15T10:00:00Z",
      "last_seen": "2024-01-20T14:30:00Z",
      "tags": ["apt29", "command_control"],
      "context": {
        "country": "Unknown",
        "asn": "AS12345",
        "description": "Known C2 server for APT29 campaigns"
      },
      "matches_24h": 3
    },
    {
      "id": "ioc_002",
      "type": "domain",
      "value": "malicious-site.example.com",
      "threat_type": "phishing",
      "confidence": 88,
      "source": "community_feed",
      "first_seen": "2024-01-18T08:00:00Z",
      "tags": ["phishing", "credential_theft"],
      "matches_24h": 0
    }
  ],
  "total": 12500,
  "by_type": {
    "ip": 8500,
    "domain": 2800,
    "hash": 1000,
    "url": 200
  },
  "last_update": "2024-01-20T15:00:00Z"
}
```

## MITRE ATT&CK Integration

### 13. List MITRE ATT&CK Techniques
```http
GET /v1/security/mitre-attack/techniques
```

**Description**: List MITRE ATT&CK techniques with detection coverage

**Authentication**: Required

**Query Parameters**:
- `tactic` (string, optional): Filter by tactic
- `has_detection` (boolean, optional): Filter techniques with active detection rules
- `limit` (integer, default: 50): Maximum techniques to return

**Response** (200):
```json
{
  "techniques": [
    {
      "id": "T1110",
      "name": "Brute Force",
      "tactic": "Credential Access",
      "description": "Adversaries may use brute force techniques to gain access to accounts",
      "sub_techniques": [
        {
          "id": "T1110.001",
          "name": "Password Guessing",
          "detection_rules": ["sigma_001", "sigma_015"],
          "detections_24h": 45
        },
        {
          "id": "T1110.003", 
          "name": "Password Spraying",
          "detection_rules": ["sigma_001"],
          "detections_24h": 8
        }
      ],
      "detection_coverage": {
        "has_rules": true,
        "rule_count": 2,
        "coverage_percentage": 67,
        "last_detection": "2024-01-20T15:30:00Z"
      },
      "mitre_url": "https://attack.mitre.org/techniques/T1110/"
    }
  ],
  "coverage_summary": {
    "total_techniques": 595,
    "covered_techniques": 284,
    "coverage_percentage": 47.7,
    "by_tactic": {
      "Initial Access": {"total": 9, "covered": 6},
      "Execution": {"total": 13, "covered": 8},
      "Persistence": {"total": 19, "covered": 12}
    }
  }
}
```

## Threat Hunting

### 14. Execute Threat Hunting Campaign
```http
POST /v1/security/threat-hunting
```

**Description**: Execute proactive threat hunting campaign

**Authentication**: Required

**Request Body**:
```json
{
  "name": "APT29 TTPs Hunt",
  "description": "Hunt for APT29 tactics, techniques, and procedures",
  "time_range": {
    "start": "2024-01-15T00:00:00Z",
    "end": "2024-01-20T23:59:59Z"
  },
  "hunting_queries": [
    {
      "name": "Suspicious PowerShell",
      "query": {
        "filters": [
          {"field": "process_name", "operator": "contains", "value": "powershell"},
          {"field": "command_line", "operator": "regex", "value": ".*(EncodedCommand|DownloadString).*"}
        ]
      },
      "mitre_techniques": ["T1059.001"]
    },
    {
      "name": "Lateral Movement Indicators",
      "query": {
        "filters": [
          {"field": "event_type", "operator": "eq", "value": "network_connection"},
          {"field": "destination_port", "operator": "in", "value": [445, 139, 3389]}
        ]
      },
      "mitre_techniques": ["T1021"]
    }
  ],
  "notify_on_completion": true
}
```

**Response** (200):
```json
{
  "campaign_id": "hunt_123",
  "name": "APT29 TTPs Hunt",
  "status": "running",
  "started_at": "2024-01-20T17:00:00Z",
  "estimated_completion": "2024-01-20T17:15:00Z",
  "queries_submitted": 2,
  "progress": {
    "completed_queries": 0,
    "total_queries": 2,
    "percentage": 0
  }
}
```

### 15. Background Threat Hunting
```http
GET /v1/security/background-hunting
```

**Description**: Get status of background threat hunting activities

**Authentication**: Required

**Response** (200):
```json
{
  "status": "active",
  "active_hunts": [
    {
      "hunt_id": "bg_hunt_001",
      "name": "Continuous IOC Monitoring",
      "type": "continuous",
      "started_at": "2024-01-20T00:00:00Z",
      "last_execution": "2024-01-20T16:45:00Z",
      "next_execution": "2024-01-20T17:45:00Z",
      "findings_24h": 8
    }
  ],
  "completed_hunts_24h": 12,
  "total_findings_24h": 25,
  "high_priority_findings": 3
}
```

## Security Analytics Configuration

### Sigma Rule Categories

| Category | Description | Example Rules |
|----------|-------------|---------------|
| `authentication` | Login and authentication events | Brute force, credential stuffing |
| `network` | Network traffic analysis | C2 communication, data exfiltration |
| `execution` | Process and command execution | Malicious PowerShell, suspicious binaries |
| `persistence` | Persistence mechanisms | Registry modifications, scheduled tasks |
| `privilege_escalation` | Privilege escalation attempts | UAC bypass, sudo abuse |
| `lateral_movement` | Movement between systems | WMI, PsExec, RDP abuse |
| `collection` | Data collection activities | Clipboard access, screen capture |
| `exfiltration` | Data exfiltration | Large uploads, DNS tunneling |

### Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| `critical` | Immediate threat requiring urgent response | < 15 minutes |
| `high` | Significant security risk | < 1 hour |
| `medium` | Moderate security concern | < 4 hours |
| `low` | Informational or low-risk event | < 24 hours |

### IOC Types and Sources

**IOC Types**:
- `ip`: IP addresses (IPv4/IPv6)
- `domain`: Domain names and subdomains
- `url`: Full URLs and URI paths
- `hash`: File hashes (MD5, SHA1, SHA256)
- `email`: Email addresses
- `filename`: File names and paths

**Threat Intelligence Sources**:
- Commercial feeds (e.g., CrowdStrike, FireEye)
- Open source intelligence (OSINT)
- Government feeds (e.g., US-CERT, CISA)
- Community sharing platforms
- Internal threat intelligence

## Error Responses

### Common Error Codes

| Status Code | Error Type | Description |
|-------------|------------|-------------|
| 400 | `invalid_sigma_rule` | Malformed Sigma rule syntax |
| 400 | `invalid_mitre_technique` | Invalid MITRE ATT&CK technique ID |
| 403 | `insufficient_security_role` | User lacks security analyst role |
| 404 | `rule_not_found` | Sigma rule does not exist |
| 409 | `rule_name_conflict` | Sigma rule name already exists |
| 422 | `validation_error` | Request validation failed |

### Example Error Response
```json
{
  "detail": "Invalid Sigma rule syntax: missing detection condition",
  "type": "invalid_sigma_rule",
  "code": "SIGMA_001",
  "context": {
    "rule_id": "sigma_046",
    "line": 15,
    "suggestion": "Add 'condition' field to detection block"
  }
}
```

## Best Practices

### Sigma Rule Development
1. **Test Rules Thoroughly**: Always test rules before deployment
2. **Minimize False Positives**: Include appropriate exclusions
3. **Document Context**: Provide clear descriptions and use cases
4. **Map to MITRE**: Associate rules with relevant ATT&CK techniques
5. **Regular Review**: Update rules based on threat landscape changes

### Threat Hunting
1. **Hypothesis-Driven**: Start with specific threat hypotheses
2. **Use IOCs**: Leverage threat intelligence indicators
3. **Historical Analysis**: Look back in time for missed threats
4. **Document Findings**: Record all hunting activities and results
5. **Continuous Improvement**: Update rules based on hunting discoveries

### Event Management
1. **Triage Quickly**: Prioritize high-severity events
2. **Assign Ownership**: Ensure all events have assigned analysts
3. **Document Thoroughly**: Maintain detailed investigation notes
4. **Learn from Incidents**: Update rules and procedures
5. **Share Intelligence**: Contribute findings to threat intelligence

---

*See [Data APIs](./Data-APIs.md) for log querying and [Enterprise APIs](./Enterprise-APIs.md) for compliance and audit features.*