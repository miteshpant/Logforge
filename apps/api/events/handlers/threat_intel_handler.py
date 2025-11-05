"""
Threat Intelligence Event Handler
Extracts IOCs from security detection events and populates threat_intel_mt table
"""

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import re
import json

from .base import EventHandler
from ..base import BaseEvent
from dao.security_dao import SecurityDAO

logger = structlog.get_logger(__name__)


class ThreatIntelHandler(EventHandler):
    """
    Handles security detection events and extracts IOCs to threat_intel_mt table
    
    This handler automatically populates the threat intelligence database with
    indicators of compromise (IOCs) extracted from real security detections,
    making the /v1/security/threat-intel endpoint useful with actual data.
    """
    
    def __init__(self):
        super().__init__()
        self.security_dao = SecurityDAO()
        self.logger = logger.bind(component="threat_intel_handler")
        
        # IP address regex pattern
        self.ip_pattern = re.compile(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$')
        
        # Domain regex pattern (basic)
        self.domain_pattern = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$')
        
        # Hash patterns
        self.md5_pattern = re.compile(r'^[a-fA-F0-9]{32}$')
        self.sha1_pattern = re.compile(r'^[a-fA-F0-9]{40}$')
        self.sha256_pattern = re.compile(r'^[a-fA-F0-9]{64}$')

    async def handle(self, event: BaseEvent) -> bool:
        """Handle security detection events for threat intelligence extraction"""
        try:
            event_type = event.event_type
            event_data = {
                'customer_id': event.customer_id,
                **event.data
            }
            
            if event_type == "security.detection.triggered":
                await self._extract_and_store_iocs(event_data)
            elif event_type == "security.detection.false_positive":
                await self._mark_iocs_false_positive(event_data)
            elif event_type == "security.detection.resolved":
                await self._update_ioc_confidence(event_data)
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Error processing security event for threat intel",
                event_type=event.event_type,
                customer_id=event.customer_id,
                error=str(e)
            )
            return False

    def get_supported_event_types(self) -> List[str]:
        """Get list of event types this handler supports"""
        return [
            "security.detection.triggered",
            "security.detection.false_positive", 
            "security.detection.resolved"
        ]

    def get_handler_name(self) -> str:
        """Get the name of this handler"""
        return "threat_intel_handler"

    async def _extract_and_store_iocs(self, event_data: Dict[str, Any]) -> None:
        """Extract IOCs from security detection and store in threat_intel_mt"""
        try:
            customer_id = event_data.get("customer_id")
            
            # Determine threat type based on attack techniques
            threat_type = self._determine_threat_type(event_data.get("attack_techniques", []))
            
            # Calculate confidence based on rule severity and confidence
            base_confidence = self._calculate_confidence(
                event_data.get("severity", "medium"),
                event_data.get("confidence", 0.8)
            )
            
            indicators = []
            
            # Extract IP addresses
            for ip_field in ["src_ip", "dst_ip", "client_ip", "remote_ip", "host"]:
                if ip_value := event_data.get(ip_field):
                    if self._is_valid_ip(ip_value):
                        indicators.append({
                            "indicator_type": "ip",
                            "indicator_value": ip_value,
                            "threat_type": threat_type,
                            "confidence_score": base_confidence,
                            "source": f"detection_{event_data.get('rule_name', 'unknown')}",
                            "context": {
                                "detection_id": event_data.get("detection_id"),
                                "rule_id": event_data.get("rule_id"),
                                "rule_name": event_data.get("rule_name"),
                                "field": ip_field,
                                "attack_techniques": event_data.get("attack_techniques", []),
                                "detected_at": event_data.get("triggered_at")
                            }
                        })
            
            # Extract domains (only from domain field, not hostname/host)
            if domain_value := event_data.get("domain"):
                if self._is_valid_domain(domain_value):
                    indicators.append({
                        "indicator_type": "domain",
                        "indicator_value": domain_value,
                        "threat_type": threat_type,
                        "confidence_score": base_confidence,
                        "source": f"detection_{event_data.get('rule_name', 'unknown')}",
                        "context": {
                            "detection_id": event_data.get("detection_id"),
                            "rule_id": event_data.get("rule_id"),
                            "rule_name": event_data.get("rule_name"),
                            "field": "domain",
                            "attack_techniques": event_data.get("attack_techniques", []),
                            "detected_at": event_data.get("triggered_at")
                        }
                    })
            
            # Extract hostnames (from host and hostname fields) - store as domain type
            for host_field in ["host", "hostname"]:
                if host_value := event_data.get(host_field):
                    if self._is_valid_hostname(host_value):
                        indicators.append({
                            "indicator_type": "domain",  # Use domain type since hostname isn't supported
                            "indicator_value": host_value,
                            "threat_type": threat_type,
                            "confidence_score": max(base_confidence - 10, 30),  # Lower confidence for hostnames
                            "source": f"detection_{event_data.get('rule_name', 'unknown')}",
                            "context": {
                                "detection_id": event_data.get("detection_id"),
                                "rule_id": event_data.get("rule_id"),
                                "rule_name": event_data.get("rule_name"),
                                "field": host_field,
                                "attack_techniques": event_data.get("attack_techniques", []),
                                "detected_at": event_data.get("triggered_at")
                            }
                        })
            
            # Extract file hashes
            for hash_field in ["file_hash", "hash", "md5", "sha1", "sha256"]:
                if hash_value := event_data.get(hash_field):
                    hash_type = self._identify_hash_type(hash_value)
                    if hash_type:
                        indicators.append({
                            "indicator_type": "hash",
                            "indicator_value": hash_value,
                            "threat_type": "malware",  # Hashes typically indicate malware
                            "confidence_score": min(base_confidence + 10, 100),  # Higher confidence for hashes
                            "source": f"detection_{event_data.get('rule_name', 'unknown')}",
                            "context": {
                                "detection_id": event_data.get("detection_id"),
                                "rule_id": event_data.get("rule_id"),
                                "rule_name": event_data.get("rule_name"),
                                "hash_type": hash_type,
                                "field": hash_field,
                                "attack_techniques": event_data.get("attack_techniques", []),
                                "detected_at": event_data.get("triggered_at")
                            }
                        })
            
            # Extract user indicators for suspicious users
            if user_value := event_data.get("user"):
                if self._is_suspicious_user_activity(event_data):
                    indicators.append({
                        "indicator_type": "email",  # Use email type for usernames since username isn't supported  
                        "indicator_value": user_value,
                        "threat_type": threat_type,
                        "confidence_score": max(base_confidence - 20, 30),  # Lower confidence for users
                        "source": f"detection_{event_data.get('rule_name', 'unknown')}",
                        "context": {
                            "detection_id": event_data.get("detection_id"),
                            "rule_id": event_data.get("rule_id"),
                            "rule_name": event_data.get("rule_name"),
                            "field": "user",
                            "attack_techniques": event_data.get("attack_techniques", []),
                            "detected_at": event_data.get("triggered_at")
                        }
                    })
            
            # Store all indicators
            for indicator in indicators:
                await self._save_threat_indicator(indicator, customer_id)
            
            if indicators:
                self.logger.info(
                    "Extracted IOCs from security detection",
                    customer_id=customer_id,
                    detection_id=event_data.get("detection_id"),
                    rule_name=event_data.get("rule_name"),
                    indicators_count=len(indicators),
                    threat_type=threat_type
                )
                
        except Exception as e:
            self.logger.error(
                "Error extracting IOCs from security detection",
                customer_id=event_data.get("customer_id"),
                detection_id=event_data.get("detection_id"),
                error=str(e)
            )

    async def _mark_iocs_false_positive(self, event_data: Dict[str, Any]) -> None:
        """Mark IOCs as false positive when detection is marked as FP"""
        try:
            customer_id = event_data.get("customer_id")
            detection_id = event_data.get("detection_id")
            
            if not detection_id:
                return
            
            # Find and deactivate IOCs from this detection
            await self._deactivate_iocs_by_detection(detection_id, customer_id)
            
            self.logger.info(
                "Marked IOCs as false positive",
                customer_id=customer_id,
                detection_id=detection_id
            )
            
        except Exception as e:
            self.logger.error(
                "Error marking IOCs as false positive",
                customer_id=event_data.get("customer_id"),
                detection_id=event_data.get("detection_id"),
                error=str(e)
            )

    async def _update_ioc_confidence(self, event_data: Dict[str, Any]) -> None:
        """Update IOC confidence when detection is resolved (confirmed threat)"""
        try:
            customer_id = event_data.get("customer_id")
            detection_id = event_data.get("detection_id")
            
            if not detection_id:
                return
            
            # Increase confidence for confirmed threats
            await self._boost_ioc_confidence(detection_id, customer_id)
            
            self.logger.info(
                "Boosted IOC confidence for resolved detection",
                customer_id=customer_id,
                detection_id=detection_id
            )
            
        except Exception as e:
            self.logger.error(
                "Error updating IOC confidence",
                customer_id=event_data.get("customer_id"),
                detection_id=event_data.get("detection_id"),
                error=str(e)
            )

    def _determine_threat_type(self, attack_techniques: List[str]) -> str:
        """Determine threat type based on MITRE ATT&CK techniques"""
        if not attack_techniques:
            return "scanning"
        
        # Map common techniques to threat types
        technique_map = {
            "T1110": "scanning",    # Brute Force
            "T1078": "scanning",    # Valid Accounts
            "T1190": "scanning",    # Exploit Public-Facing Application
            "T1566": "phishing",    # Phishing
            "T1059": "malware",     # Command and Scripting Interpreter
            "T1105": "malware",     # Ingress Tool Transfer
            "T1055": "malware",     # Process Injection
            "T1071": "c2",          # Application Layer Protocol
            "T1090": "c2",          # Proxy
            "T1572": "c2",          # Protocol Tunneling
        }
        
        for technique in attack_techniques:
            if technique in technique_map:
                return technique_map[technique]
        
        return "scanning"  # Default

    def _calculate_confidence(self, severity: str, detection_confidence: float) -> int:
        """Calculate confidence score based on severity and detection confidence"""
        base_scores = {
            "critical": 90,
            "high": 75,
            "medium": 60,
            "low": 45,
            "info": 30
        }
        
        base_score = base_scores.get(severity, 60)
        
        # Adjust based on detection confidence
        adjusted_score = int(base_score * detection_confidence)
        
        return min(max(adjusted_score, 20), 100)  # Clamp between 20-100

    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address and filter out private/local IPs"""
        if not self.ip_pattern.match(ip):
            return False
        
        # Filter out private/local IP ranges
        private_ranges = [
            "127.",      # Loopback
            "192.168.",  # Private
            "10.",       # Private
            "172.16.",   # Private (simplified check)
            "169.254.",  # Link-local
            "224.",      # Multicast
            "0.0.0.0",   # Invalid
        ]
        
        for private_range in private_ranges:
            if ip.startswith(private_range):
                return False
        
        return True

    def _is_valid_domain(self, domain: str) -> bool:
        """Validate domain name and filter out hostnames/internal domains"""
        if not domain or len(domain) > 255:
            return False
        
        domain_lower = domain.lower()
        
        # Filter out localhost and internal domains
        internal_patterns = [
            "localhost", "local", ".internal"
        ]
        
        for pattern in internal_patterns:
            if pattern in domain_lower:
                return False
        
        # Must contain at least one dot to be a valid domain
        if "." not in domain:
            return False
        
        # Must have a valid TLD (at least 2 characters after last dot)
        parts = domain.split(".")
        if len(parts) < 2 or len(parts[-1]) < 2:
            return False
        
        return self.domain_pattern.match(domain) is not None

    def _is_valid_hostname(self, hostname: str) -> bool:
        """Validate hostname and filter out obvious non-hostnames"""
        if not hostname or len(hostname) > 255:
            return False
        
        hostname_lower = hostname.lower()
        
        # Filter out obvious non-hostnames
        invalid_patterns = [
            "localhost", "127.0.0.1", "0.0.0.0",
            "admin", "user", "test"  # Common usernames, not hostnames
        ]
        
        if hostname_lower in invalid_patterns:
            return False
        
        # Basic hostname validation - allow single words or FQDN
        # Hostnames can be single words (like "web-server-01") or have dots
        if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$', hostname):
            return False
        
        return True

    def _identify_hash_type(self, hash_value: str) -> Optional[str]:
        """Identify hash type (MD5, SHA1, SHA256)"""
        if self.md5_pattern.match(hash_value):
            return "md5"
        elif self.sha1_pattern.match(hash_value):
            return "sha1"
        elif self.sha256_pattern.match(hash_value):
            return "sha256"
        return None

    def _is_suspicious_user_activity(self, event_data: Dict[str, Any]) -> bool:
        """Determine if user activity is suspicious enough to create indicator"""
        # Only create user indicators for high-severity detections
        severity = event_data.get("severity", "medium")
        attack_techniques = event_data.get("attack_techniques", [])
        
        # High severity or specific attack techniques
        if severity in ["critical", "high"]:
            return True
        
        # Specific user-related attack techniques
        user_techniques = ["T1110", "T1078", "T1201", "T1136"]
        if any(tech in attack_techniques for tech in user_techniques):
            return True
        
        return False

    async def _save_threat_indicator(self, indicator: Dict[str, Any], customer_id: str) -> None:
        """Save threat indicator to database"""
        try:
            now = datetime.now(timezone.utc)
            
            indicator_data = {
                "customer_id": customer_id,
                "indicator_type": indicator["indicator_type"],
                "indicator_value": indicator["indicator_value"],
                "threat_type": [indicator["threat_type"]],  # Convert to list for DAO
                "confidence": indicator["confidence_score"],
                "source": indicator["source"],
                "description": f"Extracted from security detection: {indicator['context'].get('rule_name')}",
                "tags": indicator["context"].get("attack_techniques", []),
                "context": json.dumps(indicator["context"]),
                "first_seen": now,
                "last_seen": now,
                "is_active": True
            }
            
            await self.security_dao.save_threat_intel_indicator(indicator_data)
            
        except Exception as e:
            self.logger.error(
                "Error saving threat indicator",
                indicator_type=indicator["indicator_type"],
                indicator_value=indicator["indicator_value"],
                customer_id=customer_id,
                error=str(e)
            )

    async def _deactivate_iocs_by_detection(self, detection_id: str, customer_id: str) -> None:
        """Deactivate IOCs that came from a specific detection (false positive)"""
        try:
            # This would require a custom query to update indicators based on context JSON
            # For now, we'll log the action - can be implemented when needed
            self.logger.info(
                "Would deactivate IOCs for false positive detection",
                detection_id=detection_id,
                customer_id=customer_id
            )
        except Exception as e:
            self.logger.error(
                "Error deactivating IOCs",
                detection_id=detection_id,
                customer_id=customer_id,
                error=str(e)
            )

    async def _boost_ioc_confidence(self, detection_id: str, customer_id: str) -> None:
        """Boost confidence for IOCs from confirmed threats"""
        try:
            # This would require a custom query to update confidence based on context JSON
            # For now, we'll log the action - can be implemented when needed
            self.logger.info(
                "Would boost IOC confidence for confirmed threat",
                detection_id=detection_id,
                customer_id=customer_id
            )
        except Exception as e:
            self.logger.error(
                "Error boosting IOC confidence",
                detection_id=detection_id,
                customer_id=customer_id,
                error=str(e)
            )