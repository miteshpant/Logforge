# Threat Intelligence System

## Overview

Logforge's Threat Intelligence system automatically extracts Indicators of Compromise (IOCs) from real security detections and makes them available through the `/v1/security/threat-intel` API endpoint. This transforms security events into actionable threat intelligence data.

## How It Works

### 1. Automatic IOC Extraction

When security detections are triggered (via Sigma rules or alerts), the **ThreatIntelHandler** automatically extracts IOCs from the detection data:

```
Security Detection → ThreatIntelHandler → threat_intel_mt table → API endpoint
```

### 2. Event-Driven Processing

The system uses Logforge's event framework to process security events:

1. **Security Detection Triggered** → `security.detection.triggered` event
2. **ThreatIntelHandler** consumes the event
3. **IOCs extracted** from detection data (IPs, domains, hashes, usernames)
4. **Stored** in `threat_intel_mt` table
5. **Available** via `/v1/security/threat-intel` API

### 3. IOC Types Extracted

| IOC Type | Fields Extracted From | Database Type | Example |
|----------|----------------------|---------------|---------|
| **IP Addresses** | `src_ip`, `dst_ip`, `client_ip`, `remote_ip` | `ip` | `203.0.113.45` |
| **Domains** | `domain` | `domain` | `malicious.com` |
| **Hostnames** | `host`, `hostname` | `domain` | `web-server-01` |
| **Usernames** | `user` (high-severity only) | `email` | `admin` |
| **File Hashes** | `hash`, `md5`, `sha1`, `sha256` | `hash` | `abc123def...` |

### 4. Smart Filtering

The system applies intelligent filtering to ensure high-quality IOCs:

#### IP Address Filtering
- ✅ **Includes**: Public IP addresses
- ❌ **Excludes**: Private ranges (192.168.x.x, 10.x.x.x, 127.x.x.x)

#### Domain Filtering  
- ✅ **Includes**: Valid domains with TLD (e.g., `malicious.com`)
- ❌ **Excludes**: Internal domains (`.internal`, `.local`, `localhost`)

#### Hostname Filtering
- ✅ **Includes**: Server hostnames (e.g., `web-server-01`)
- ❌ **Excludes**: Common usernames (`admin`, `user`, `test`)

#### Username Filtering
- ✅ **Includes**: Users from high-severity detections or brute force attacks
- ❌ **Excludes**: Low-severity user activity

## Threat Type Mapping

Based on MITRE ATT&CK techniques detected:

```python
"T1110": "scanning",    # Brute Force
"T1078": "scanning",    # Valid Accounts  
"T1190": "scanning",    # Exploit Public-Facing Application
"T1566": "phishing",    # Phishing
"T1059": "malware",     # Command and Scripting Interpreter
"T1071": "c2",          # Application Layer Protocol
```

## Confidence Scoring

IOCs receive confidence scores based on:

1. **Detection Severity**:
   - Critical: 90 base score
   - High: 75 base score
   - Medium: 60 base score
   - Low: 45 base score

2. **Detection Confidence**: Multiplied by rule confidence (0.0-1.0)

3. **IOC Type Adjustments**:
   - File hashes: +10 confidence (more reliable)
   - Hostnames: -10 confidence (less reliable)
   - Usernames: -20 confidence (context-dependent)

## API Usage

### List All Threat Intel
```bash
curl -H "X-Customer-ID: your-customer-id" \
     "https://api.logforge.com/v1/security/threat-intel"
```

### Filter by IOC Type
```bash
curl -H "X-Customer-ID: your-customer-id" \
     "https://api.logforge.com/v1/security/threat-intel?indicator_type=ip"
```

### Response Format
```json
[
  {
    "id": "abc-123-def",
    "indicator_type": "ip",
    "value": "203.0.113.45",
    "threat_type": ["scanning"], 
    "severity": "medium",
    "confidence": 75,
    "source": "detection_Brute_Force_Detection",
    "description": "Extracted from security detection: Brute Force Detection",
    "tags": ["T1110"],
    "first_seen": "2025-11-05T13:46:27.000000",
    "last_seen": "2025-11-05T13:46:27.000000"
  }
]
```

## Business Value

### 1. **Automatic IOC Generation**
- No manual IOC entry required
- Real-time extraction from actual detections
- Reduces analyst workload

### 2. **Contextualized Intelligence**
- IOCs linked to specific detection rules
- MITRE ATT&CK technique mapping
- Source attribution for reliability

### 3. **Confidence-Based Prioritization**
- High-confidence IOCs for blocking
- Medium-confidence IOCs for monitoring
- Low-confidence IOCs for investigation

### 4. **Integration Ready**
- Standard API format
- Filter by IOC type
- Ready for SIEM/SOAR integration

## Implementation Details

### Database Schema
**Table**: `threat_intel_mt`

| Column | Type | Description |
|--------|------|-------------|
| `id` | String | Unique IOC identifier |
| `customer_id` | String | Customer isolation |
| `indicator_type` | Enum | ip, domain, hash, email, filename, url |
| `indicator_value` | String | The actual IOC value |
| `threat_type` | Enum | malware, c2, phishing, scanning, bot |
| `confidence_score` | Int | 0-100 confidence rating |
| `source` | String | Detection rule source |
| `first_seen` | DateTime | When first detected |
| `last_seen` | DateTime | Most recent detection |
| `tags` | Array | MITRE ATT&CK techniques |
| `context` | JSON | Additional detection context |
| `is_active` | Boolean | Active/inactive status |

### Event Handler
**File**: `/apps/api/events/handlers/threat_intel_handler.py`

Key methods:
- `_extract_and_store_iocs()` - Main extraction logic
- `_determine_threat_type()` - MITRE ATT&CK mapping
- `_calculate_confidence()` - Confidence scoring
- `_is_valid_*()` - IOC validation methods

## Monitoring & Observability

### Metrics Tracked
- IOCs extracted per detection
- IOC types distribution  
- Confidence score distribution
- False positive rates
- API endpoint usage

### Logging
```
"Extracted IOCs from security detection",
customer_id=customer_id,
detection_id=detection_id,
rule_name=rule_name,
indicators_count=len(indicators),
threat_type=threat_type
```

## Future Enhancements

### 1. **Cross-Customer Intelligence Sharing** 🚧
- Aggregate IOCs across customers (with consent)
- Global threat intelligence feed
- Privacy-preserving IOC sharing
- Legal framework for data sharing

### 2. **IOC Enrichment**
- External threat intel feed integration
- Geolocation data for IPs
- Reputation scoring
- Historical context

### 3. **Machine Learning Enhancement**
- IOC risk scoring models
- False positive reduction
- Automated IOC clustering
- Threat actor attribution

### 4. **Advanced Filtering**
- IOC age-based filtering
- Source reliability weighting
- Custom confidence thresholds
- Whitelist/blacklist management

## Integration Examples

### Block IPs in Firewall
```python
# Get high-confidence malicious IPs
response = requests.get(
    "https://api.logforge.com/v1/security/threat-intel?indicator_type=ip",
    headers={"X-Customer-ID": customer_id}
)

# Filter high-confidence IOCs
malicious_ips = [
    ioc["value"] for ioc in response.json() 
    if ioc["confidence"] >= 80 and "scanning" in ioc["threat_type"]
]

# Add to firewall blocklist
for ip in malicious_ips:
    firewall.block_ip(ip)
```

### SIEM Integration
```python
# Enrich logs with threat intel
def enrich_log_with_threat_intel(log_entry):
    src_ip = log_entry.get("src_ip")
    
    # Check if IP is in threat intel
    threat_data = get_threat_intel(indicator_type="ip", value=src_ip)
    
    if threat_data:
        log_entry["threat_intel"] = {
            "is_malicious": True,
            "threat_type": threat_data["threat_type"],
            "confidence": threat_data["confidence"],
            "source": threat_data["source"]
        }
    
    return log_entry
```

## Best Practices

### 1. **API Usage**
- Filter by `indicator_type` for performance
- Check confidence scores before acting
- Monitor `first_seen`/`last_seen` for freshness
- Implement rate limiting for bulk queries

### 2. **IOC Management** 
- Review low-confidence IOCs manually
- Set up alerts for high-confidence IOCs
- Periodically audit false positives
- Maintain IOC retention policies

### 3. **Integration**
- Start with high-confidence IOCs (80+)
- Implement gradual rollout
- Monitor for false positive impact
- Document IOC sources and actions taken

---

## Related Documentation
- [Security Event Processing](./Security-Event-Processing.md)
- [Sigma Rules Management](./Sigma-Rules-Management.md)
- [API Authentication](./API-Authentication.md)
- [Event-Driven Architecture](./Event-Driven-Architecture.md)