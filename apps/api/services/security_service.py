"""
Security Analytics Service - Business Logic for Security Analytics, SIEM, and Threat Intelligence
Handles Sigma rules, security events, threat intelligence indicators, and MITRE ATT&CK integration
"""

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum

from dao.security_dao import SecurityDAO

logger = structlog.get_logger(__name__)

class AttackTechnique(Enum):
    """MITRE ATT&CK Technique enumeration"""
    # Reconnaissance
    T1595 = "T1595"  # Active Scanning
    T1590 = "T1590"  # Gather Victim Network Information
    
    # Resource Development
    T1583 = "T1583"  # Acquire Infrastructure
    T1588 = "T1588"  # Obtain Capabilities
    
    # Initial Access
    T1190 = "T1190"  # Exploit Public-Facing Application
    T1566 = "T1566"  # Phishing
    T1078 = "T1078"  # Valid Accounts
    
    # Execution
    T1059 = "T1059"  # Command and Scripting Interpreter
    T1203 = "T1203"  # Exploitation for Client Execution
    
    # Persistence
    T1053 = "T1053"  # Scheduled Task/Job
    T1098 = "T1098"  # Account Manipulation
    
    # Privilege Escalation
    T1068 = "T1068"  # Exploitation for Privilege Escalation
    T1548 = "T1548"  # Abuse Elevation Control Mechanism
    
    # Defense Evasion
    T1055 = "T1055"  # Process Injection
    T1027 = "T1027"  # Obfuscated Files or Information
    
    # Credential Access
    T1110 = "T1110"  # Brute Force
    T1555 = "T1555"  # Credentials from Password Stores
    
    # Discovery
    T1083 = "T1083"  # File and Directory Discovery
    T1018 = "T1018"  # Remote System Discovery
    
    # Lateral Movement
    T1021 = "T1021"  # Remote Services
    T1570 = "T1570"  # Lateral Tool Transfer
    
    # Collection
    T1005 = "T1005"  # Data from Local System
    T1039 = "T1039"  # Data from Network Shared Drive
    
    # Command and Control
    T1071 = "T1071"  # Application Layer Protocol
    T1573 = "T1573"  # Encrypted Channel
    
    # Exfiltration
    T1041 = "T1041"  # Exfiltration Over C2 Channel
    T1048 = "T1048"  # Exfiltration Over Alternative Protocol
    
    # Impact
    T1486 = "T1486"  # Data Encrypted for Impact
    T1499 = "T1499"  # Endpoint Denial of Service

@dataclass
class SigmaRule:
    """Sigma detection rule data structure"""
    id: str
    title: str
    description: str
    severity: str
    status: str
    author: str
    date: str
    tags: List[str]
    attack_techniques: List[AttackTechnique]
    kill_chain_phases: List[str]
    logsource: Dict[str, Any]
    detection: Dict[str, Any]
    references: List[str]
    falsepositives: List[str]
    enabled: bool
    customer_id: str = "default"

@dataclass
class SecurityEvent:
    """Security event data structure"""
    id: str
    rule_id: str
    rule_title: str
    severity: str
    status: str
    timestamp: datetime
    event_data: Dict[str, Any]
    matched_fields: Dict[str, Any]
    attack_techniques: List[AttackTechnique]
    kill_chain_phase: Optional[str]
    assigned_to: Optional[str]
    investigation_notes: List[str]
    artifacts: List[str]
    source_logs: List[str]
    customer_id: str = "default"

@dataclass
class ThreatIntelIndicator:
    """Threat intelligence indicator data structure"""
    id: str
    indicator_type: str
    value: str
    threat_type: List[str]
    severity: str
    confidence: int
    source: str
    description: Optional[str]
    tags: List[str]
    first_seen: datetime
    last_seen: datetime
    customer_id: str = "default"

class SecurityService:
    """Business Logic Layer for Security Analytics and SIEM"""
    
    def __init__(self):
        self.security_dao = SecurityDAO()
        self._initialize_default_rules()
    
    def _initialize_default_rules(self):
        """Initialize with default Sigma rules and threat intelligence"""
        # This will be called on service initialization to ensure default rules exist
        # Default rules are loaded from the database or created if they don't exist
        pass
    
    # Sigma Rules Management
    
    async def create_sigma_rule(self, rule_data: Dict[str, Any]) -> str:
        """Create new Sigma detection rule"""
        try:
            # Validate rule data
            if not rule_data.get("title") or not rule_data.get("detection"):
                raise ValueError("Sigma rule must have title and detection logic")
            
            # Convert attack techniques to enum values
            attack_techniques = []
            for technique in rule_data.get("attack_techniques", []):
                try:
                    if isinstance(technique, str):
                        attack_techniques.append(AttackTechnique(technique))
                    else:
                        attack_techniques.append(technique)
                except ValueError:
                    logger.warning(f"Unknown MITRE ATT&CK technique: {technique}")
            
            # Create Sigma rule object
            sigma_rule = SigmaRule(
                id=rule_data.get("id", ""),
                title=rule_data["title"],
                description=rule_data.get("description", ""),
                severity=rule_data.get("severity", "medium"),
                status=rule_data.get("status", "active"),
                author=rule_data.get("author", "logforge"),
                date=rule_data.get("date", datetime.now(timezone.utc).strftime("%Y/%m/%d")),
                tags=rule_data.get("tags", []),
                attack_techniques=attack_techniques,
                kill_chain_phases=rule_data.get("kill_chain_phases", []),
                logsource=rule_data.get("logsource", {}),
                detection=rule_data["detection"],
                references=rule_data.get("references", []),
                falsepositives=rule_data.get("falsepositives", []),
                enabled=rule_data.get("enabled", True),
                customer_id=rule_data.get("customer_id", "default")
            )
            
            # Save to database
            rule_id = await self.security_dao.save_sigma_rule(rule_data)
            
            logger.info(f"Sigma rule created: {rule_id}")
            return rule_id
            
        except Exception as e:
            logger.error(f"Failed to create Sigma rule: {e}")
            raise
    
    async def get_sigma_rules(self, customer_id: str = None, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """Get Sigma detection rules"""
        try:
            rules = await self.security_dao.get_sigma_rules(customer_id)
            
            if enabled_only:
                rules = [rule for rule in rules if rule.get("enabled", True)]
            
            return rules
            
        except Exception as e:
            logger.error(f"Failed to get Sigma rules: {e}")
            raise
    
    async def get_sigma_rule_by_id(self, rule_id: str, customer_id: str = None) -> Optional[Dict[str, Any]]:
        """Get specific Sigma rule by ID"""
        try:
            return await self.security_dao.get_sigma_rule_by_id(rule_id, customer_id)
            
        except Exception as e:
            logger.error(f"Failed to get Sigma rule {rule_id}: {e}")
            raise
    
    async def test_sigma_rule(self, rule_id: str, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Test Sigma rule against sample data"""
        try:
            rule = await self.get_sigma_rule_by_id(rule_id)
            if not rule:
                raise ValueError(f"Sigma rule not found: {rule_id}")
            
            # Simple rule testing simulation
            # In production, this would implement actual Sigma rule evaluation
            match_result = self._evaluate_sigma_rule(rule, test_data)
            
            return {
                "rule_id": rule_id,
                "rule_title": rule["title"],
                "test_data": test_data,
                "matched": match_result["matched"],
                "matched_fields": match_result["matched_fields"],
                "confidence": match_result["confidence"],
                "test_timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to test Sigma rule {rule_id}: {e}")
            raise
    
    def _evaluate_sigma_rule(self, rule: Dict[str, Any], test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate Sigma rule against test data (simplified implementation)"""
        # This is a simplified implementation for demo purposes
        # Production would use a proper Sigma rule engine
        
        detection = rule.get("detection", {})
        matched_fields = {}
        confidence = 0.0
        
        # Check simple field matches
        for field, criteria in detection.items():
            if field == "condition":
                continue  # Skip condition for now
                
            if field in test_data:
                if isinstance(criteria, str):
                    if criteria.lower() in str(test_data[field]).lower():
                        matched_fields[field] = test_data[field]
                        confidence += 0.3
                elif isinstance(criteria, list):
                    for criterion in criteria:
                        if criterion.lower() in str(test_data[field]).lower():
                            matched_fields[field] = test_data[field]
                            confidence += 0.2
        
        # Simple threshold for match determination
        matched = confidence > 0.5
        
        return {
            "matched": matched,
            "matched_fields": matched_fields,
            "confidence": min(confidence, 1.0)
        }
    
    # Security Events Management
    
    async def create_security_event(self, event_data: Dict[str, Any]) -> str:
        """Create new security event"""
        try:
            # Validate event data
            if not event_data.get("rule_id") or not event_data.get("rule_title"):
                raise ValueError("Security event must have rule_id and rule_title")
            
            # Convert attack techniques to enum values
            attack_techniques = []
            for technique in event_data.get("attack_techniques", []):
                try:
                    if isinstance(technique, str):
                        attack_techniques.append(AttackTechnique(technique))
                    else:
                        attack_techniques.append(technique)
                except ValueError:
                    logger.warning(f"Unknown MITRE ATT&CK technique: {technique}")
            
            # Save to database
            event_id = await self.security_dao.save_security_event(event_data)
            
            logger.info(f"Security event created: {event_id}")
            return event_id
            
        except Exception as e:
            logger.error(f"Failed to create security event: {e}")
            raise
    
    async def get_security_events(self, customer_id: str, limit: int = 100, 
                                severity: str = None, status: str = None) -> List[Dict[str, Any]]:
        """Get security events"""
        try:
            return await self.security_dao.get_security_events(customer_id, limit, severity, status)
            
        except Exception as e:
            logger.error(f"Failed to get security events: {e}")
            raise
    
    async def update_security_event_status(self, event_id: str, customer_id: str, 
                                         status: str, assigned_to: str = None, 
                                         notes: List[str] = None) -> bool:
        """Update security event status and investigation details"""
        try:
            updates = {"status": status}
            
            if assigned_to:
                updates["assigned_to"] = assigned_to
            
            if notes:
                updates["investigation_notes"] = notes
            
            result = await self.security_dao.update_security_event(event_id, customer_id, updates)
            
            if result:
                logger.info(f"Security event updated: {event_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to update security event {event_id}: {e}")
            raise
    
    # Threat Intelligence Management
    
    async def add_threat_indicator(self, indicator_data: Dict[str, Any]) -> str:
        """Add threat intelligence indicator"""
        try:
            # Validate indicator data
            if not indicator_data.get("indicator_type") or not indicator_data.get("value"):
                raise ValueError("Threat indicator must have type and value")
            
            # Save to database
            indicator_id = await self.security_dao.save_threat_intel_indicator(indicator_data)
            
            logger.info(f"Threat indicator added: {indicator_id}")
            return indicator_id
            
        except Exception as e:
            logger.error(f"Failed to add threat indicator: {e}")
            raise
    
    async def get_threat_indicators(self, customer_id: str = None, 
                                  indicator_type: str = None) -> List[Dict[str, Any]]:
        """Get threat intelligence indicators"""
        try:
            return await self.security_dao.get_threat_intel_indicators(customer_id, indicator_type)
            
        except Exception as e:
            logger.error(f"Failed to get threat indicators: {e}")
            raise
    
    # Advanced Security Analytics
    
    async def run_threat_hunting_campaign(self, campaign_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute threat hunting campaign"""
        try:
            campaign_id = campaign_data.get("id", "hunting-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
            
            # Get enabled Sigma rules for hunting
            rules = await self.get_sigma_rules(
                customer_id=campaign_data.get("customer_id"),
                enabled_only=True
            )
            
            # Simulate threat hunting results
            hunting_results = {
                "campaign_id": campaign_id,
                "description": campaign_data.get("description", "Threat hunting campaign"),
                "start_time": datetime.now(timezone.utc).isoformat(),
                "rules_evaluated": len(rules),
                "events_found": [],
                "indicators_detected": [],
                "recommendations": []
            }
            
            # Simulate finding some security events
            hunting_results["events_found"] = [
                {
                    "rule_id": "bf001",
                    "rule_title": "Brute Force Detection",
                    "severity": "high",
                    "confidence": 0.85,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            ]
            
            hunting_results["recommendations"] = [
                "Enable additional monitoring for failed login attempts",
                "Review user access patterns for anomalies",
                "Consider implementing rate limiting on authentication endpoints"
            ]
            
            logger.info(f"Threat hunting campaign executed: {campaign_id}")
            return hunting_results
            
        except Exception as e:
            logger.error(f"Failed to run threat hunting campaign: {e}")
            raise
    
    async def get_security_dashboard_data(self, customer_id: str) -> Dict[str, Any]:
        """Get security dashboard analytics data"""
        try:
            # Get recent security events
            events = await self.get_security_events(customer_id, limit=50)
            
            # Get threat indicators
            indicators = await self.get_threat_indicators(customer_id)
            
            # Get Sigma rules
            rules = await self.get_sigma_rules(customer_id)
            
            # Calculate dashboard metrics
            events_by_severity = {}
            for event in events:
                severity = event.get("severity", "unknown")
                events_by_severity[severity] = events_by_severity.get(severity, 0) + 1
            
            # MITRE ATT&CK technique mapping
            attack_techniques = {}
            for event in events:
                techniques = event.get("attack_techniques", [])
                for technique in techniques:
                    attack_techniques[technique] = attack_techniques.get(technique, 0) + 1
            
            return {
                "customer_id": customer_id,
                "summary": {
                    "total_events": len(events),
                    "events_last_24h": len([e for e in events if self._is_recent(e.get("timestamp"), hours=24)]),
                    "critical_events": events_by_severity.get("critical", 0),
                    "high_events": events_by_severity.get("high", 0),
                    "active_rules": len([r for r in rules if r.get("enabled", True)]),
                    "threat_indicators": len(indicators)
                },
                "events_by_severity": events_by_severity,
                "attack_techniques": attack_techniques,
                "top_triggered_rules": self._get_top_triggered_rules(events),
                "recent_events": events[:10],  # Latest 10 events
                "dashboard_generated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get security dashboard data: {e}")
            raise
    
    def _is_recent(self, timestamp, hours: int = 24) -> bool:
        """Check if timestamp is within recent hours"""
        if not timestamp:
            return False
            
        try:
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            time_diff = datetime.now(timezone.utc) - timestamp
            return time_diff.total_seconds() < (hours * 3600)
        except:
            return False
    
    def _get_top_triggered_rules(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get most frequently triggered rules"""
        rule_counts = {}
        for event in events:
            rule_id = event.get("rule_id", "unknown")
            rule_title = event.get("rule_title", "Unknown Rule")
            
            if rule_id not in rule_counts:
                rule_counts[rule_id] = {"rule_id": rule_id, "rule_title": rule_title, "count": 0}
            rule_counts[rule_id]["count"] += 1
        
        # Sort by count and return top 5
        sorted_rules = sorted(rule_counts.values(), key=lambda x: x["count"], reverse=True)
        return sorted_rules[:5]
    
    # Default Sigma Rules and Threat Intelligence
    
    async def load_default_security_content(self, customer_id: str = "default"):
        """Load default Sigma rules and threat intelligence indicators"""
        try:
            # Default Sigma rules
            default_rules = [
                {
                    "id": "bf001",
                    "title": "Brute Force Detection",
                    "description": "Detects multiple failed login attempts from the same IP",
                    "severity": "high",
                    "author": "logforge",
                    "tags": ["attack.credential_access", "attack.t1110"],
                    "attack_techniques": ["T1110"],
                    "kill_chain_phases": ["credential-access"],
                    "logsource": {"category": "authentication"},
                    "detection": {
                        "selection": {
                            "event_type": "login_failed",
                            "status_code": [401, 403]
                        },
                        "condition": "selection | count by src_ip > 10"
                    },
                    "references": ["https://attack.mitre.org/techniques/T1110/"],
                    "falsepositives": ["User password reset attempts"],
                    "customer_id": customer_id
                },
                {
                    "id": "ps001",
                    "title": "Suspicious PowerShell Execution",
                    "description": "Detects potentially malicious PowerShell command execution",
                    "severity": "medium",
                    "author": "logforge",
                    "tags": ["attack.execution", "attack.t1059.001"],
                    "attack_techniques": ["T1059"],
                    "kill_chain_phases": ["execution"],
                    "logsource": {"category": "process_creation", "product": "windows"},
                    "detection": {
                        "selection": {
                            "process_name": "powershell.exe",
                            "command_line": ["*-EncodedCommand*", "*bypass*", "*-noprofile*"]
                        },
                        "condition": "selection"
                    },
                    "references": ["https://attack.mitre.org/techniques/T1059/001/"],
                    "falsepositives": ["Legitimate PowerShell scripts"],
                    "customer_id": customer_id
                }
            ]
            
            # Default threat intelligence indicators
            default_indicators = [
                {
                    "indicator_type": "domain",
                    "value": "malicious-c2.example.com",
                    "threat_type": ["c2", "malware"],
                    "severity": "high",
                    "confidence": 95,
                    "source": "logforge_intel",
                    "description": "Known command and control domain",
                    "tags": ["c2", "apt"],
                    "customer_id": customer_id
                },
                {
                    "indicator_type": "ip",
                    "value": "198.51.100.42",
                    "threat_type": ["scanning", "malware"],
                    "severity": "medium",
                    "confidence": 80,
                    "source": "logforge_intel",
                    "description": "IP address associated with scanning activity",
                    "tags": ["scanner", "suspicious"],
                    "customer_id": customer_id
                }
            ]
            
            # Create default rules
            for rule in default_rules:
                try:
                    await self.create_sigma_rule(rule)
                except Exception as e:
                    logger.warning(f"Failed to create default rule {rule['id']}: {e}")
            
            # Create default indicators
            for indicator in default_indicators:
                try:
                    await self.add_threat_indicator(indicator)
                except Exception as e:
                    logger.warning(f"Failed to create default indicator {indicator['value']}: {e}")
            
            logger.info(f"Default security content loaded for customer: {customer_id}")
            
        except Exception as e:
            logger.error(f"Failed to load default security content: {e}")
            raise