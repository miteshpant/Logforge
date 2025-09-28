# Security Router API Documentation

## Overview

The Security Router provides comprehensive security analytics and SIEM capabilities with Sigma rule management, threat intelligence, security event tracking, and MITRE ATT&CK framework integration. This router enables enterprise-grade security operations with threat hunting, detection rule management, and security event lifecycle management.

## Architecture

```
Request → Security Router → Security Service → Security DAO → ClickHouse
                        ↓
                Security Analytics Engine → MITRE ATT&CK Integration
```

**Core Components:**
- **Router**: `/apps/api/routers/security_api.py` - FastAPI endpoints for security operations
- **Service**: `/apps/api/services/security_service.py` - Business logic for security analytics
- **DAO**: `/apps/api/dao/security_dao.py` - Database operations for security data
- **Engine**: `/apps/api/security_analytics.py` - Core security analytics and rule engine
- **Database**: Multi-tenant ClickHouse tables (`sigma_rules_mt`, `security_events_mt`, `threat_intel_mt`)

## API Endpoints

### Health & Status

#### 1. Security Health Check
**Endpoint**: `GET /v1/security/health`

Get security analytics service health and status.

**Headers:**
- `X-Customer-ID`: Customer identifier
- `Authorization`: Bearer token

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "sigma_rules_count": 15,
  "threat_intel_count": 8,
  "security_events_count": 42,
  "database_connected": true
}
```

**Degraded Response:**
```json
{
  "status": "degraded",
  "timestamp": "2024-01-15T10:30:00Z",
  "error": "Database connection timeout",
  "database_connected": false
}
```

### Security Dashboard

#### 2. Get Security Dashboard
**Endpoint**: `GET /v1/security/dashboard`

Get security analytics dashboard overview with events, techniques, and statistics.

**Query Parameters:**
- `time_range`: Time range for analysis (`1h`, `24h`, `7d`, `30d`) - default: `24h`

**Response:**
```json
{
  "total_events": 156,
  "events_by_severity": {
    "critical": 5,
    "high": 23,
    "medium": 89,
    "low": 39,
    "info": 0
  },
  "events_by_technique": {
    "T1110": 15,
    "T1059": 8,
    "T1068": 3,
    "T1041": 2
  },
  "top_rules": [
    {
      "rule_id": "bf001",
      "rule_title": "Brute Force Detection",
      "triggered_count": 15,
      "severity": "high"
    },
    {
      "rule_id": "ps001", 
      "rule_title": "Suspicious PowerShell",
      "triggered_count": 8,
      "severity": "medium"
    }
  ],
  "recent_events": [
    {
      "id": "event_123",
      "rule_id": "bf001",
      "rule_title": "Brute Force Detection",
      "severity": "high",
      "status": "triggered",
      "timestamp": "2024-01-15T10:25:00Z",
      "event_data": {
        "src_ip": "192.168.1.100",
        "failed_attempts": 6,
        "target_user": "admin"
      },
      "matched_fields": {
        "event_type": "login_failed",
        "status_code": 401
      },
      "attack_techniques": ["T1110"],
      "kill_chain_phase": "credential-access",
      "assigned_to": null,
      "investigation_notes": [],
      "artifacts": []
    }
  ],
  "threat_intel_stats": {
    "total_indicators": 8,
    "high_confidence": 3,
    "recent_additions": 1
  }
}
```

### Sigma Rule Management

#### 3. List Sigma Rules
**Endpoint**: `GET /v1/security/sigma-rules`

List all Sigma detection rules for the customer.

**Response:**
```json
[
  {
    "id": "bf001",
    "title": "Brute Force Detection",
    "description": "Detects multiple failed login attempts indicating brute force attacks",
    "severity": "high",
    "status": "active",
    "author": "Security Team",
    "date": "2024-01-10",
    "enabled": true,
    "attack_techniques": ["T1110"],
    "tags": ["authentication", "brute_force", "credential_access"]
  },
  {
    "id": "ps001",
    "title": "Suspicious PowerShell",
    "description": "Detects suspicious PowerShell command execution",
    "severity": "medium", 
    "status": "active",
    "author": "Detection Engineer",
    "date": "2024-01-12",
    "enabled": true,
    "attack_techniques": ["T1059"],
    "tags": ["powershell", "execution", "command_line"]
  }
]
```

#### 4. Create Sigma Rule
**Endpoint**: `POST /v1/security/sigma-rules`

Create a new Sigma detection rule.

**Request Body:**
```json
{
  "title": "Suspicious Network Activity",
  "description": "Detects unusual network connections to suspicious domains",
  "severity": "medium",
  "author": "Security Analyst",
  "tags": ["network", "c2", "suspicious_domains"],
  "logsource": {
    "category": "network",
    "product": "firewall"
  },
  "detection": {
    "selection": {
      "event_type": "connection",
      "destination_port": [80, 443],
      "domain": ["*.suspicious-domain.com", "malicious-site.org"]
    },
    "condition": "selection"
  },
  "attack_techniques": ["T1071"],
  "kill_chain_phases": ["command-and-control"],
  "references": [
    "https://attack.mitre.org/techniques/T1071/"
  ],
  "falsepositives": [
    "Legitimate business connections to partner domains"
  ],
  "enabled": true
}
```

**Response:**
```json
{
  "message": "Sigma rule created",
  "rule_id": "net001"
}
```

#### 5. Get Sigma Rule
**Endpoint**: `GET /v1/security/sigma-rules/{rule_id}`

Get specific Sigma rule by ID.

**Path Parameters:**
- `rule_id`: Sigma rule identifier

**Response:**
```json
{
  "id": "bf001",
  "title": "Brute Force Detection", 
  "description": "Detects multiple failed login attempts indicating brute force attacks",
  "severity": "high",
  "status": "active",
  "author": "Security Team",
  "date": "2024-01-10",
  "enabled": true,
  "attack_techniques": ["T1110"],
  "tags": ["authentication", "brute_force", "credential_access"],
  "logsource": {
    "category": "authentication",
    "product": "linux"
  },
  "detection": {
    "selection": {
      "event_type": "login_failed",
      "status_code": 401
    },
    "condition": "selection | count() > 5"
  },
  "references": [
    "https://attack.mitre.org/techniques/T1110/"
  ],
  "falsepositives": [
    "Password reset attempts",
    "Account lockout policies"
  ]
}
```

#### 6. Test Sigma Rule
**Endpoint**: `POST /v1/security/sigma-rules/{rule_id}/test`

Test a Sigma rule against sample data to validate detection logic.

**Path Parameters:**
- `rule_id`: Sigma rule identifier

**Response:**
```json
{
  "result": "triggered",
  "test_details": {
    "rule_id": "bf001",
    "rule_title": "Brute Force Detection",
    "matched": true,
    "matched_fields": {
      "event_type": "login_failed",
      "status_code": 401
    },
    "confidence": 85,
    "test_timestamp": "2024-01-15T10:30:00Z",
    "test_data": {
      "event_type": "login_failed",
      "status_code": 401,
      "src_ip": "192.168.1.100",
      "user": "admin",
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
}
```

**No Match Response:**
```json
{
  "result": "no_match",
  "test_details": {
    "rule_id": "bf001",
    "rule_title": "Brute Force Detection",
    "matched": false,
    "matched_fields": {},
    "confidence": 0,
    "test_timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Security Events

#### 7. List Security Events
**Endpoint**: `GET /v1/security/events`

List security events generated by detection rules.

**Query Parameters:**
- `limit`: Maximum number of events to return (default: 100)
- `severity`: Filter by severity level (`critical`, `high`, `medium`, `low`, `info`)
- `status`: Filter by event status (`triggered`, `investigating`, `resolved`, `false_positive`)
- `rule_id`: Filter by specific rule ID

**Example:**
```
GET /v1/security/events?limit=50&severity=high&status=triggered
```

**Response:**
```json
[
  {
    "id": "event_123",
    "rule_id": "bf001",
    "rule_title": "Brute Force Detection",
    "severity": "high",
    "status": "triggered",
    "timestamp": "2024-01-15T10:25:00Z",
    "event_data": {
      "src_ip": "192.168.1.100",
      "failed_attempts": 6,
      "target_user": "admin",
      "time_window": "5 minutes"
    },
    "matched_fields": {
      "event_type": "login_failed",
      "status_code": 401,
      "src_ip": "192.168.1.100"
    },
    "attack_techniques": ["T1110"],
    "kill_chain_phase": "credential-access",
    "assigned_to": null,
    "investigation_notes": [],
    "artifacts": ["ip:192.168.1.100", "user:admin"]
  },
  {
    "id": "event_456",
    "rule_id": "ps001",
    "rule_title": "Suspicious PowerShell",
    "severity": "medium",
    "status": "investigating",
    "timestamp": "2024-01-15T10:20:00Z",
    "event_data": {
      "command": "powershell.exe -encodedCommand BASE64_ENCODED_COMMAND",
      "process_id": 1234,
      "parent_process": "cmd.exe"
    },
    "matched_fields": {
      "process_name": "powershell.exe",
      "command_line": "*-encodedCommand*"
    },
    "attack_techniques": ["T1059"],
    "kill_chain_phase": "execution",
    "assigned_to": "analyst@company.com",
    "investigation_notes": [
      "Initial triage completed - suspicious encoded command detected"
    ],
    "artifacts": ["process:powershell.exe", "command:encoded"]
  }
]
```

#### 8. Update Security Event Status
**Endpoint**: `PUT /v1/security/events/{event_id}/status`

Update security event status and investigation details.

**Path Parameters:**
- `event_id`: Security event identifier

**Query Parameters:**
- `status`: New event status (`investigating`, `resolved`, `false_positive`)
- `assigned_to`: Analyst email (optional)

**Example:**
```
PUT /v1/security/events/event_123/status?status=investigating&assigned_to=analyst@company.com
```

**Response:**
```json
{
  "message": "Security event updated",
  "event_id": "event_123"
}
```

### Threat Hunting

#### 9. Execute Threat Hunting
**Endpoint**: `POST /v1/security/threat-hunting`

Execute threat hunting campaign to proactively search for threats.

**Request Body:**
```json
{
  "time_range": "7d",
  "severity_filter": ["medium", "high", "critical"],
  "rule_ids": ["bf001", "ps001"],
  "description": "Weekly threat hunting for credential access techniques"
}
```

**Response:**
```json
{
  "campaign_id": "hunt_789",
  "description": "Weekly threat hunting for credential access techniques",
  "time_range": "7d",
  "rules_evaluated": 2,
  "events_found": 8,
  "high_priority_findings": 3,
  "summary": {
    "T1110": {
      "technique": "Brute Force",
      "events": 5,
      "highest_severity": "high"
    },
    "T1059": {
      "technique": "Command and Scripting Interpreter",
      "events": 3,
      "highest_severity": "medium"
    }
  },
  "recommendations": [
    "Investigate brute force attempts from 192.168.1.0/24",
    "Review PowerShell execution policies"
  ],
  "executed_at": "2024-01-15T10:30:00Z"
}
```

#### 10. Background Threat Hunting
**Endpoint**: `POST /v1/security/background-hunting`

Trigger background threat hunting for continuous monitoring.

**Response:**
```json
{
  "message": "Background threat hunting triggered",
  "status": "scheduled"
}
```

### Threat Intelligence

#### 11. List Threat Intelligence
**Endpoint**: `GET /v1/security/threat-intel`

List threat intelligence indicators.

**Query Parameters:**
- `indicator_type`: Filter by indicator type (`ip`, `domain`, `url`, `hash`, `email`, `file`)
- `threat_type`: Filter by threat type (`malware`, `c2`, `phishing`, `scanning`)
- `confidence`: Minimum confidence level (0-100)

**Example:**
```
GET /v1/security/threat-intel?indicator_type=ip&confidence=80
```

**Response:**
```json
[
  {
    "id": "ioc_001",
    "indicator_type": "ip",
    "value": "192.168.100.50",
    "threat_type": ["c2", "malware"],
    "severity": "high",
    "confidence": 95,
    "source": "threat_feed_alpha",
    "description": "Known C2 server associated with APT group",
    "tags": ["apt", "c2_server", "malware_infrastructure"],
    "first_seen": "2024-01-10T08:00:00Z",
    "last_seen": "2024-01-15T10:25:00Z"
  },
  {
    "id": "ioc_002",
    "indicator_type": "domain",
    "value": "malicious-domain.com",
    "threat_type": ["phishing", "malware"],
    "severity": "medium",
    "confidence": 82,
    "source": "threat_feed_beta",
    "description": "Domain used for phishing campaigns",
    "tags": ["phishing", "campaign_infrastructure"],
    "first_seen": "2024-01-12T14:30:00Z",
    "last_seen": "2024-01-15T09:15:00Z"
  }
]
```

### MITRE ATT&CK Integration

#### 12. List MITRE ATT&CK Techniques
**Endpoint**: `GET /v1/security/mitre-attack/techniques`

Get MITRE ATT&CK techniques and mappings.

**Response:**
```json
{
  "techniques": [
    {
      "id": "T1110",
      "name": "Brute Force",
      "description": "Adversaries may use brute force techniques to gain access to accounts when passwords are unknown or when password hashes are obtained."
    },
    {
      "id": "T1059",
      "name": "Command and Scripting Interpreter",
      "description": "Adversaries may abuse command and script interpreters to execute commands, scripts, or binaries."
    },
    {
      "id": "T1068",
      "name": "Exploitation for Privilege Escalation", 
      "description": "Adversaries may exploit software vulnerabilities in an attempt to elevate privileges."
    },
    {
      "id": "T1041",
      "name": "Exfiltration Over C2 Channel",
      "description": "Adversaries may steal data by exfiltrating it over an existing command and control channel."
    }
  ],
  "total_count": 29,
  "framework_version": "v12.1"
}
```

## Data Models

### Sigma Rule Structure
```python
class SigmaRuleRequest(BaseModel):
    title: str
    description: str
    severity: str = "medium"  # critical, high, medium, low, info
    author: Optional[str] = "Logforge User"
    tags: Optional[List[str]] = []
    logsource: Dict[str, Any]
    detection: Dict[str, Any]
    attack_techniques: Optional[List[str]] = []
    kill_chain_phases: Optional[List[str]] = []
    references: Optional[List[str]] = []
    falsepositives: Optional[List[str]] = []
    enabled: bool = True
```

### Security Event Structure
```python
class SecurityEventResponse(BaseModel):
    id: str
    rule_id: str
    rule_title: str
    severity: str
    status: str
    timestamp: str
    event_data: Dict[str, Any]
    matched_fields: Dict[str, Any]
    attack_techniques: List[str]
    kill_chain_phase: Optional[str]
    assigned_to: Optional[str]
    investigation_notes: List[str]
    artifacts: List[str]
```

### Threat Intelligence Structure
```python
class ThreatIntelResponse(BaseModel):
    id: str
    indicator_type: str  # ip, domain, url, hash, email, file
    value: str
    threat_type: List[str]  # malware, c2, phishing, scanning
    severity: str
    confidence: int  # 0-100
    source: str
    description: Optional[str]
    tags: List[str]
    first_seen: str
    last_seen: str
```

## Authentication & Headers

All security endpoints require authentication:

```http
Authorization: Bearer <jwt_token>
X-Customer-ID: <customer_id>
Content-Type: application/json
```

## Error Handling

**Common HTTP Status Codes:**
- `200`: Success
- `400`: Bad request (validation error)
- `401`: Unauthorized (invalid token)
- `403`: Forbidden (insufficient permissions)
- `404`: Resource not found (rule/event not found)
- `422`: Unprocessable entity (invalid rule format)
- `500`: Internal server error

**Error Response Format:**
```json
{
  "detail": "Sigma rule validation failed: Missing required field 'logsource'",
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_123"
}
```

## Code Integration

### Service Layer Integration

```python
from services.security_service import SecurityService

# Initialize service
security_service = SecurityService()

# Create Sigma rule
rule_data = {
    "title": "Custom Detection Rule",
    "description": "Detects suspicious activity",
    "severity": "high",
    "logsource": {"category": "authentication"},
    "detection": {
        "selection": {"event_type": "login_failed"},
        "condition": "selection"
    },
    "enabled": True
}
rule_id = await security_service.create_sigma_rule(rule_data, customer_id)

# Get security events
events = await security_service.get_security_events(customer_id, limit=50)

# Execute threat hunting
hunt_results = await security_service.execute_threat_hunting(
    customer_id,
    time_range="7d",
    severity_filter=["high", "critical"]
)

# Get threat intelligence
indicators = await security_service.get_threat_indicators(customer_id)
```

### Direct Database Integration

```python
from dao.security_dao import SecurityDAO

# Initialize DAO
security_dao = SecurityDAO()

# Store Sigma rule
rule_id = await security_dao.create_sigma_rule(rule_data)

# Get security events
events = await security_dao.get_security_events(customer_id, filters)

# Store threat intelligence
ioc_id = await security_dao.create_threat_indicator(indicator_data)
```

### Rule Testing Example

```python
# Test Sigma rule against sample data
test_data = {
    "event_type": "login_failed",
    "status_code": 401,
    "src_ip": "192.168.1.100",
    "user": "admin"
}

test_result = await security_service.test_sigma_rule(rule_id, test_data)

if test_result["matched"]:
    print(f"Rule triggered: {test_result['matched_fields']}")
else:
    print("Rule did not match test data")
```

## Database Schema

**Key Security Tables:**
- `sigma_rules_mt`: Sigma detection rules with detection logic
- `security_events_mt`: Security events generated by rules  
- `threat_intel_mt`: Threat intelligence indicators and IOCs
- `mitre_techniques_mt`: MITRE ATT&CK technique mappings

**Sigma Rules Schema:**
```sql
CREATE TABLE sigma_rules_mt (
    id String,
    customer_id String,
    title String,
    description String,
    severity String,
    author String,
    tags String,  -- JSON Array
    logsource String,  -- JSON
    detection String,  -- JSON
    attack_techniques String,  -- JSON Array
    enabled Boolean,
    created_at DateTime64(9),
    updated_at DateTime64(9)
) ENGINE = MergeTree()
PARTITION BY customer_id
ORDER BY (customer_id, created_at)
```

**Security Events Schema:**
```sql
CREATE TABLE security_events_mt (
    id String,
    customer_id String,
    rule_id String,
    rule_title String,
    severity String,
    status String,
    event_data String,  -- JSON
    matched_fields String,  -- JSON
    attack_techniques String,  -- JSON Array
    created_at DateTime64(9),
    updated_at DateTime64(9)
) ENGINE = MergeTree()
PARTITION BY customer_id
ORDER BY (customer_id, created_at)
```

## Performance Characteristics

- **Rule Creation**: < 200ms for Sigma rule validation and storage
- **Event Generation**: < 100ms for rule evaluation and event creation
- **Threat Hunting**: < 10s for 7-day analysis across 1M+ events
- **Dashboard Loading**: < 2s for real-time security overview
- **Rule Testing**: < 50ms for sample data evaluation
- **Threat Intel Lookup**: < 25ms for IOC matching

## MITRE ATT&CK Integration

### Supported Techniques
The security router supports 29 MITRE ATT&CK techniques across all tactics:

**Reconnaissance**: T1595, T1590
**Resource Development**: T1583, T1588  
**Initial Access**: T1190, T1566, T1078
**Execution**: T1059, T1203
**Persistence**: T1053, T1098
**Privilege Escalation**: T1068, T1548
**Defense Evasion**: T1055, T1027
**Credential Access**: T1110, T1555
**Discovery**: T1083, T1018
**Lateral Movement**: T1021, T1570
**Collection**: T1005, T1039
**Command and Control**: T1071, T1573
**Exfiltration**: T1041, T1048
**Impact**: T1486, T1499

### Kill Chain Mapping
Rules are mapped to MITRE ATT&CK kill chain phases:
- `reconnaissance`
- `resource-development`
- `initial-access`
- `execution`
- `persistence`
- `privilege-escalation`
- `defense-evasion`
- `credential-access`
- `discovery`
- `lateral-movement`
- `collection`
- `command-and-control`
- `exfiltration`
- `impact`

## Security Considerations

- **Multi-Tenant Isolation**: Complete rule and event isolation via customer_id
- **Rule Validation**: Input sanitization and Sigma rule format validation
- **Event Integrity**: Immutable security events with audit trails
- **Threat Intel Verification**: Confidence scoring and source attribution
- **Access Control**: Role-based permissions for security operations
- **Data Retention**: Configurable retention for compliance requirements

## Best Practices

1. **Rule Design**: Create specific, low false-positive detection rules
2. **Severity Assignment**: Use appropriate severity levels based on business impact
3. **Technique Mapping**: Map rules to relevant MITRE ATT&CK techniques
4. **Event Lifecycle**: Manage security events through investigation workflow
5. **Threat Hunting**: Regular proactive hunting campaigns
6. **IOC Management**: Maintain up-to-date threat intelligence feeds
7. **False Positive Handling**: Document and tune rules to reduce noise

## Related Documentation

- [MITRE ATT&CK Framework](https://attack.mitre.org/)
- [Sigma Rule Format](https://github.com/SigmaHQ/sigma)
- [Threat Intelligence Guide](../../../wiki/Threat-Intelligence-Guide.md)
- [Security Event Management](../../../wiki/Security-Event-Management.md)