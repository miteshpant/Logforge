# Tenant User Story: Security Analytics and Threat Detection

## Story
**As a** Security Operations Center (SOC) analyst  
**I want to** detect and investigate security threats using SIEM capabilities  
**So that** I can protect our organization from cyber threats and maintain security compliance

## User Journey

### 1. Access Security Dashboard
- SOC analyst logs into Logforge at `http://localhost:3001`
- Authenticates via `POST /v1/auth/login`
- Navigates to Security section (`/security`)
- Views security analytics dashboard with real-time metrics:
  - Security events: 23 (last 24h)
  - Critical alerts: 2 active
  - MITRE ATT&CK techniques detected: 5
  - Top triggered rules: Brute Force Detection (15), Suspicious PowerShell (8)

### 2. Review Active Security Events
- Analyst clicks on "Critical Alerts" section
- System calls `GET /v1/security/events?severity=critical`
- Views active security events:

**Event #1: Brute Force Attack**
- Severity: HIGH
- Status: Investigating
- Rule: bf001 - Multiple failed login attempts
- Affected user: admin@company.com
- Source IP: 192.168.1.100
- Time: 15 minutes ago
- MITRE Technique: T1110 (Brute Force)

**Event #2: Suspicious PowerShell Execution**
- Severity: CRITICAL
- Status: New
- Rule: ps001 - Malicious PowerShell commands
- Host: WS-FINANCE-02
- Command: powershell.exe -enc [base64]
- Time: 5 minutes ago
- MITRE Technique: T1059 (Command and Scripting Interpreter)

### 3. Investigate Security Event
- Analyst clicks on PowerShell event for detailed investigation
- Views event details and context:
  - Full command line with decoded payload
  - Process parent-child relationship
  - Network connections from host
  - User context and privileges
- System provides related logs via correlated queries

### 4. Threat Hunting Campaign
- Analyst suspects advanced persistent threat (APT)
- Navigates to Threat Hunting section
- Creates new hunting campaign:
  - Name: "PowerShell Lateral Movement Hunt"
  - Time range: Last 7 days
  - Hypothesis: "Attacker using PowerShell for lateral movement"
- Defines hunting query:
```
service = "windows-logs" AND 
message CONTAINS "powershell.exe" AND 
(message CONTAINS "Invoke-" OR message CONTAINS "IEX" OR message CONTAINS "DownloadString")
```

### 5. Execute Threat Hunt
- System calls `POST /v1/security/threat-hunting`
- Query executes across 7 days of log data
- Results show 47 PowerShell executions
- Analyst reviews suspicious patterns:
  - 12 executions from same user account
  - 8 different hosts affected
  - Base64 encoded commands detected
  - Network connections to suspicious domains

### 6. Create Custom Detection Rule
- Based on hunting results, analyst creates new Sigma rule
- Navigates to Rules Management section
- Clicks "Create New Rule"
- Defines custom rule:
```yaml
title: Suspicious PowerShell Network Activity
description: Detects PowerShell with network connections to suspicious domains
severity: high
logsource:
  service: windows-logs
detection:
  selection:
    service: windows-logs
    message|contains:
      - 'powershell.exe'
      - 'Invoke-WebRequest'
      - 'DownloadString'
  network:
    message|contains:
      - 'suspicious-domain.com'
      - 'malware-c2.net'
  condition: selection and network
```

### 7. Test and Deploy Rule
- System calls `POST /v1/security/sigma-rules/{id}/test`
- Rule validation successful
- Analyst enables rule for production
- System calls `POST /v1/security/sigma-rules`
- Rule becomes active for real-time detection
- Notifications configured for security team

### 8. Update Event Status
- Analyst completes investigation of brute force attack
- Determines attack was blocked by network security
- Updates event status via `PUT /v1/security/events/{id}/status`
- Adds investigation notes:
  - "Attack blocked by firewall rules"
  - "Source IP added to blacklist"
  - "User account temporarily locked"
- Event marked as "Resolved"

### 9. Generate Security Report
- Weekly security review meeting approaching
- Analyst generates comprehensive security report
- Reviews MITRE ATT&CK technique coverage:
  - T1110 (Brute Force): 23 detections
  - T1059 (Command Line): 15 detections
  - T1068 (Privilege Escalation): 5 detections
  - T1041 (Data Exfiltration): 2 detections
- Exports security metrics for compliance reporting

### 10. Threat Intelligence Enrichment
- New threat intelligence feed indicates IOCs
- System calls `GET /v1/security/threat-intel`
- Reviews current threat indicators:
  - 127 domains (confidence: 85-95%)
  - 43 IP addresses (confidence: 90-98%)
  - 19 file hashes (confidence: 95-99%)
- Correlates IOCs with historical log data
- Identifies 3 historical matches requiring investigation

## API Endpoints Used
- `GET /v1/security/health` - Security analytics health
- `GET /v1/security/dashboard` - Security overview dashboard
- `GET /v1/security/events` - List security events
- `PUT /v1/security/events/{id}/status` - Update event status
- `GET /v1/security/sigma-rules` - List detection rules
- `POST /v1/security/sigma-rules` - Create new rule
- `POST /v1/security/sigma-rules/{id}/test` - Test rule
- `POST /v1/security/threat-hunting` - Execute threat hunt
- `GET /v1/security/threat-intel` - Threat intelligence
- `GET /v1/security/mitre-attack/techniques` - MITRE ATT&CK data

## Success Criteria
- Security events are detected in real-time (< 60 seconds)
- Investigation workflow provides comprehensive context
- Threat hunting capabilities identify advanced threats
- Custom rules can be created and deployed quickly
- MITRE ATT&CK mapping provides structured analysis
- Threat intelligence enriches detection capabilities
- Compliance reporting requirements are met
- False positive rate is manageable (< 5%)

## Technical Implementation
- **Security Engine**: Sigma-compatible rule engine
- **Event Correlation**: Real-time event correlation and enrichment
- **Threat Intelligence**: IOC matching and confidence scoring
- **MITRE Framework**: ATT&CK technique mapping and coverage
- **Investigation**: Context-rich event details and relationships
- **Reporting**: Automated compliance and security reports
- **UI**: Dedicated security analyst interface