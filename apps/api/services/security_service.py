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
        
        # Initialize event publisher (lazy loading to avoid circular dependencies)
        self._security_publisher = None
    
    async def _get_security_publisher(self):
        """Get security event publisher (lazy loading to avoid circular dependencies)"""
        if self._security_publisher is None:
            try:
                # Import here to avoid circular dependency
                from events.publishers.security_publisher import SecurityEventPublisher
                import dependencies
                
                # Use global event publisher manager
                if dependencies.event_publisher_manager:
                    self._security_publisher = SecurityEventPublisher(dependencies.event_publisher_manager)
                else:
                    logger.warning("Event publisher manager not available")
                    
            except Exception as e:
                logger.error(f"Failed to initialize security event publisher: {e}")
                
        return self._security_publisher
    
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
            
            # Publish event after successful creation
            try:
                publisher = await self._get_security_publisher()
                if publisher:
                    # Create rule data for event
                    event_rule_data = {
                        "id": rule_id,
                        "name": rule_data.get("title"),
                        "title": rule_data.get("title"),
                        "severity": rule_data.get("severity", "medium"),
                        "is_enabled": rule_data.get("enabled", True),
                        "mitre_techniques": [str(t) for t in attack_techniques],
                        "kill_chain_phases": rule_data.get("kill_chain_phases", []),
                        "logsource": rule_data.get("logsource", {}),
                        "tags": rule_data.get("tags", []),
                        **rule_data
                    }
                    await publisher.publish_sigma_rule_created(
                        customer_id=rule_data.get("customer_id"),
                        rule_data=event_rule_data,
                        created_by="api-user"
                    )
            except Exception as e:
                logger.warning(f"Failed to publish Sigma rule created event: {e}")
            
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
    
    async def update_sigma_rule(self, rule_id: str, rule_data: Dict[str, Any], customer_id: str = None) -> bool:
        """Update existing Sigma rule"""
        try:
            logger.info(f"🔧 Starting Sigma rule update for rule {rule_id} (customer: {customer_id})")
            
            success = await self.security_dao.update_sigma_rule(rule_id, rule_data, customer_id)
            logger.info(f"🔧 DAO update result for rule {rule_id}: {success}")
            
            if success:
                # Publish event after successful update
                try:
                    logger.info(f"🔧 Getting security publisher for update event")
                    publisher = await self._get_security_publisher()
                    if publisher:
                        logger.info(f"🔧 Publisher obtained, fetching updated rule data for {rule_id}")
                        
                        # CRITICAL FIX: Wait for ClickHouse UPDATE to be fully applied
                        # ClickHouse ALTER TABLE UPDATE is asynchronous by default
                        import asyncio
                        await asyncio.sleep(0.1)  # 100ms delay for consistency
                        
                        # Get updated rule data for event
                        updated_rule = await self.security_dao.get_sigma_rule_by_id(rule_id, customer_id)
                        if updated_rule:
                            logger.info(f"🔧 Publishing Sigma rule updated event for {rule_id} (customer: {customer_id})")
                            event_published = await publisher.publish_sigma_rule_updated(
                                customer_id=customer_id,
                                rule_data=updated_rule,
                                updated_by="api-user"
                            )
                            logger.info(f"🔧 Sigma rule updated event published: {event_published} for rule {rule_id}")
                        else:
                            logger.warning(f"🔧 Could not fetch updated rule data for {rule_id} after update")
                    else:
                        logger.warning(f"🔧 No security publisher available for update event")
                except Exception as e:
                    logger.warning(f"🔧 Failed to publish Sigma rule updated event for {rule_id}: {e}")
            else:
                logger.warning(f"🔧 DAO update failed for rule {rule_id}, no event will be published")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to update Sigma rule {rule_id}: {e}")
            raise
    
    async def delete_sigma_rule(self, rule_id: str, customer_id: str = None) -> bool:
        """Delete Sigma rule"""
        try:
            # Get rule data before deletion for event
            rule_data = await self.security_dao.get_sigma_rule_by_id(rule_id, customer_id)
            
            success = await self.security_dao.delete_sigma_rule(rule_id, customer_id)
            
            if success and rule_data:
                # Publish event after successful deletion
                try:
                    publisher = await self._get_security_publisher()
                    if publisher:
                        await publisher.publish_sigma_rule_deleted(
                            customer_id=customer_id,
                            rule_id=rule_id,
                            rule_name=rule_data.get("name") or rule_data.get("title"),
                            deleted_by="api-user"
                        )
                except Exception as e:
                    logger.warning(f"Failed to publish Sigma rule deleted event: {e}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete Sigma rule {rule_id}: {e}")
            raise
    
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
    
    # Security Event Status Management Methods
    
    async def acknowledge_security_event(
        self,
        detection_id: str,
        customer_id: str,
        user_id: str,
        notes: Optional[str] = None
    ) -> bool:
        """Acknowledge security event - assign to user and mark as investigating"""
        try:
            # Validate event exists
            event = await self.security_dao.get_security_event_by_id(detection_id, customer_id)
            if not event:
                raise ValueError(f"Security event not found: {detection_id}")
            
            if event['status'] != 'new':
                raise ValueError(f"Cannot acknowledge event with status: {event['status']}")
            
            # Update status to investigating and assign to user
            success = await self.security_dao.update_security_event_status(
                detection_id=detection_id,
                customer_id=customer_id,
                status='investigating',
                assigned_to=user_id,
                investigation_note=f"Event acknowledged by {user_id}" + (f": {notes}" if notes else "")
            )
            
            if success:
                # Publish event status change for streaming API
                try:
                    publisher = await self._get_security_publisher()
                    if publisher:
                        # Update the event status in the existing event data
                        event['status'] = 'investigating'
                        event['assigned_to'] = user_id
                        
                        await publisher.publish_security_detection_acknowledged(
                            customer_id=customer_id,
                            detection_id=detection_id,
                            acknowledged_by=user_id,
                            acknowledgment_notes=notes,
                            event_data=event  # Use existing event data
                        )
                except Exception as e:
                    logger.warning(f"Failed to publish status change event: {e}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to acknowledge security event {detection_id}: {e}")
            raise
    
    async def mark_false_positive(
        self,
        detection_id: str,
        customer_id: str,
        user_id: str,
        notes: str
    ) -> bool:
        """Mark security event as false positive"""
        try:
            event = await self.security_dao.get_security_event_by_id(detection_id, customer_id)
            if not event:
                raise ValueError(f"Security event not found: {detection_id}")
            
            success = await self.security_dao.update_security_event_status(
                detection_id=detection_id,
                customer_id=customer_id,
                status='false_positive',
                assigned_to=user_id,
                investigation_note=f"Marked as false positive by {user_id}: {notes}"
            )
            
            if success:
                try:
                    publisher = await self._get_security_publisher()
                    if publisher:
                        # Update the event status in the existing event data
                        event['status'] = 'false_positive'
                        event['assigned_to'] = user_id
                        
                        await publisher.publish_security_detection_false_positive(
                            customer_id=customer_id,
                            detection_id=detection_id,
                            marked_by=user_id,
                            notes=notes,
                            event_data=event  # Use existing event data
                        )
                except Exception as e:
                    logger.warning(f"Failed to publish status change event: {e}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to mark false positive {detection_id}: {e}")
            raise
    
    async def resolve_security_event(
        self,
        detection_id: str,
        customer_id: str,
        user_id: str,
        resolution_notes: str
    ) -> bool:
        """Resolve security event"""
        try:
            event = await self.security_dao.get_security_event_by_id(detection_id, customer_id)
            if not event:
                raise ValueError(f"Security event not found: {detection_id}")
            
            if event['status'] == 'resolved':
                raise ValueError("Event already resolved")
            
            success = await self.security_dao.update_security_event_status(
                detection_id=detection_id,
                customer_id=customer_id,
                status='resolved',
                investigation_note=f"Resolved by {user_id}: {resolution_notes}"
            )
            
            if success:
                try:
                    publisher = await self._get_security_publisher()
                    if publisher:
                        # Update the event status in the existing event data
                        event['status'] = 'resolved'
                        event['assigned_to'] = user_id
                        
                        await publisher.publish_security_detection_resolved(
                            customer_id=customer_id,
                            detection_id=detection_id,
                            resolved_by=user_id,
                            resolution_notes=resolution_notes,
                            event_data=event  # Use existing event data
                        )
                except Exception as e:
                    logger.warning(f"Failed to publish status change event: {e}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to resolve security event {detection_id}: {e}")
            raise
    
    async def investigate_security_event(
        self,
        detection_id: str,
        customer_id: str,
        user_id: str,
        notes: Optional[str] = None
    ) -> bool:
        """Mark event as under investigation"""
        try:
            event = await self.security_dao.get_security_event_by_id(detection_id, customer_id)
            if not event:
                raise ValueError(f"Security event not found: {detection_id}")
            
            success = await self.security_dao.update_security_event_status(
                detection_id=detection_id,
                customer_id=customer_id,
                status='investigating',
                assigned_to=user_id,
                investigation_note=f"Investigation started by {user_id}" + (f": {notes}" if notes else "")
            )
            
            if success:
                try:
                    publisher = await self._get_security_publisher()
                    if publisher:
                        # Update the event status in the existing event data
                        event['status'] = 'investigating'
                        event['assigned_to'] = user_id
                        
                        await publisher.publish_security_detection_investigating(
                            customer_id=customer_id,
                            detection_id=detection_id,
                            assigned_to=user_id,
                            investigation_notes=notes,
                            event_data=event  # Use existing event data
                        )
                except Exception as e:
                    logger.warning(f"Failed to publish status change event: {e}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to investigate security event {detection_id}: {e}")
            raise
    
    # Bulk Operations
    async def bulk_acknowledge_by_rule(
        self,
        rule_id: str,
        customer_id: str,
        user_id: str,
        notes: Optional[str] = None
    ) -> int:
        """Acknowledge all new events for a specific rule"""
        try:
            updated_count = await self.security_dao.bulk_update_events_by_rule(
                rule_id=rule_id,
                customer_id=customer_id,
                status='investigating',
                assigned_to=user_id,
                investigation_note=f"Bulk acknowledged by {user_id}" + (f": {notes}" if notes else "")
            )
            
            # Publish bulk operation event
            try:
                publisher = await self._get_security_publisher()
                if publisher:
                    await self._publish_bulk_operation(
                        publisher, rule_id, customer_id, 'bulk_acknowledge', user_id, updated_count
                    )
            except Exception as e:
                logger.warning(f"Failed to publish bulk operation event: {e}")
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Failed to bulk acknowledge by rule {rule_id}: {e}")
            raise
    
    async def bulk_false_positive_by_rule(
        self,
        rule_id: str,
        customer_id: str,
        user_id: str,
        notes: str
    ) -> int:
        """Mark all new events for a rule as false positive"""
        try:
            updated_count = await self.security_dao.bulk_update_events_by_rule(
                rule_id=rule_id,
                customer_id=customer_id,
                status='false_positive',
                assigned_to=user_id,
                investigation_note=f"Bulk false positive by {user_id}: {notes}"
            )
            
            try:
                publisher = await self._get_security_publisher()
                if publisher:
                    await self._publish_bulk_operation(
                        publisher, rule_id, customer_id, 'bulk_false_positive', user_id, updated_count
                    )
            except Exception as e:
                logger.warning(f"Failed to publish bulk operation event: {e}")
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Failed to bulk false positive by rule {rule_id}: {e}")
            raise
    
    async def bulk_resolve_by_rule(
        self,
        rule_id: str,
        customer_id: str,
        user_id: str,
        notes: str
    ) -> int:
        """Resolve all new events for a rule"""
        try:
            updated_count = await self.security_dao.bulk_update_events_by_rule(
                rule_id=rule_id,
                customer_id=customer_id,
                status='resolved',
                assigned_to=user_id,
                investigation_note=f"Bulk resolved by {user_id}: {notes}"
            )
            
            try:
                publisher = await self._get_security_publisher()
                if publisher:
                    await self._publish_bulk_operation(
                        publisher, rule_id, customer_id, 'bulk_resolve', user_id, updated_count
                    )
            except Exception as e:
                logger.warning(f"Failed to publish bulk operation event: {e}")
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Failed to bulk resolve by rule {rule_id}: {e}")
            raise
    
    async def get_security_event_details(
        self,
        detection_id: str,
        customer_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get full security event details including status and notes"""
        try:
            return await self.security_dao.get_security_event_by_id(detection_id, customer_id)
        except Exception as e:
            logger.error(f"Failed to get security event details {detection_id}: {e}")
            raise
    
    async def get_events_by_rule(
        self,
        rule_id: str,
        customer_id: str,
        status_filter: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get events for a specific rule"""
        try:
            return await self.security_dao.get_events_by_rule_id(rule_id, customer_id, status_filter, limit)
        except Exception as e:
            logger.error(f"Failed to get events by rule {rule_id}: {e}")
            raise
    
    # Helper methods for event publishing
    async def _publish_status_change(
        self,
        publisher,
        detection_id: str,
        customer_id: str,
        new_status: str,
        user_id: str
    ):
        """Publish individual event status change"""
        # This would use the publisher to send events to streaming API
        # Implementation depends on your event system
        logger.debug(f"Publishing status change: {detection_id} -> {new_status} by {user_id}")
    
    async def _publish_bulk_operation(
        self,
        publisher,
        rule_id: str,
        customer_id: str,
        operation: str,
        user_id: str,
        affected_count: int
    ):
        """Publish bulk operation event"""
        # This would use the publisher to send bulk operation events
        logger.debug(f"Publishing bulk operation: {operation} on rule {rule_id} affected {affected_count} events")
    
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
    
    async def start_threat_hunting_campaign(self, campaign_data: Dict[str, Any]) -> Dict[str, Any]:
        """Start a threat hunting campaign (returns immediately with campaign status)"""
        try:
            # Create campaign record in database
            campaign_id = await self.security_dao.create_threat_hunting_campaign(campaign_data)
            
            logger.info(f"Started threat hunting campaign: {campaign_id}")
            
            # Return campaign status immediately
            return {
                "campaign_id": campaign_id,
                "status": "started",
                "description": campaign_data.get("description", "Threat hunting campaign"),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "progress_percentage": 0
            }
            
        except Exception as e:
            logger.error(f"Failed to start threat hunting campaign: {e}")
            raise
    
    async def execute_threat_hunting_campaign(self, campaign_id: str, customer_id: str) -> bool:
        """Execute threat hunting campaign with enhanced analysis and unique findings"""
        import time
        start_time = time.time()
        
        try:
            # Update campaign status to running
            await self.security_dao.update_campaign_progress(campaign_id, {
                "status": "running", 
                "progress_percentage": 10,
                "started_at": datetime.now(timezone.utc)
            })
            
            # Get campaign details for rule filtering
            campaign = await self.security_dao.get_campaign_status(campaign_id, customer_id)
            rule_ids_filter = campaign.get("rule_ids", []) if campaign else []
            time_range = campaign.get("time_range", "24h") if campaign else "24h"
            severity_filter = campaign.get("severity_filter", []) if campaign else []
            
            # Get enabled Sigma rules for hunting (filtered by campaign rules if specified)
            all_rules = await self.get_sigma_rules(customer_id=customer_id, enabled_only=True)
            
            # Filter rules based on campaign specification
            if rule_ids_filter:
                rules = [rule for rule in all_rules if rule.get("id") in rule_ids_filter]
            else:
                rules = all_rules
            
            # Update progress after rule retrieval
            await self.security_dao.update_campaign_progress(campaign_id, {
                "rules_evaluated": len(rules),
                "progress_percentage": 30
            })
            
            # Calculate time range for analysis
            hours_back = self._parse_time_range(time_range)
            
            # EFFICIENT: Get existing security events for specified rules
            events = await self.security_dao.get_security_events_by_rules(
                customer_id=customer_id,
                rule_ids=rule_ids_filter,  # Focus on campaign rules only
                time_range_hours=hours_back,
                severity_filter=severity_filter,
                limit=10000  # Much smaller, focused dataset
            )
            
            # Filter events by time range and severity
            filtered_events = []
            for event in events:
                # Time filter
                if not self._is_recent(event.get("created_at"), hours=hours_back):
                    continue
                    
                # Severity filter
                if severity_filter and event.get("severity") not in severity_filter:
                    continue
                    
                filtered_events.append(event)
            
            await self.security_dao.update_campaign_progress(campaign_id, {
                "progress_percentage": 60
            })
            
            # Perform enhanced threat analysis using existing security events
            threat_analysis = await self._analyze_existing_security_events(
                events=filtered_events,
                rule_ids=rule_ids_filter,
                customer_id=customer_id,
                time_range=time_range
            )
            
            # Get threat intelligence indicators
            indicators = await self.security_dao.get_threat_intel_indicators(customer_id=customer_id)
            
            # Calculate costs based on rules used and time range
            cost_analysis = await self._calculate_hunting_costs(rules, time_range, customer_id)
            
            # Execution metrics
            execution_time = time.time() - start_time
            
            # Store enhanced results in campaign
            enhanced_results = {
                "unique_findings": threat_analysis["unique_findings"],
                "threat_summary": threat_analysis["summary"],
                "cost_analysis": cost_analysis,
                "execution_metrics": {
                    "execution_time_seconds": round(execution_time, 2),
                    "events_analyzed": len(filtered_events),
                    "total_events_processed": len(events),
                    "performance_score": "excellent" if execution_time < 5 else "good"
                }
            }
            
            await self.security_dao.update_campaign_progress(campaign_id, {
                "events_found": len(threat_analysis["unique_findings"]),
                "indicators_detected": len(indicators),
                "progress_percentage": 100,
                "completed_at": datetime.now(timezone.utc),
                "status": "completed",
                "enhanced_results": enhanced_results  # Store rich results
            })
            
            logger.info(f"Enhanced threat hunting campaign completed: {campaign_id} - {len(threat_analysis['unique_findings'])} unique threats found")
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute threat hunting campaign {campaign_id}: {e}")
            
            # Mark campaign as failed
            await self.security_dao.update_campaign_progress(campaign_id, {
                "status": "failed",
                "error_message": str(e),
                "completed_at": datetime.now(timezone.utc)
            })
            return False
    
    async def get_campaign_status(self, campaign_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get threat hunting campaign status with enhanced results"""
        try:
            campaign = await self.security_dao.get_campaign_status(campaign_id, customer_id)
            
            if not campaign:
                return None
            
            # Base response
            response = {
                "campaign_id": campaign["id"],
                "status": campaign["status"],
                "description": campaign["description"],
                "time_range": campaign["time_range"],
                "created_at": campaign["created_at"].isoformat() if campaign["created_at"] else None,
                "started_at": campaign["started_at"].isoformat() if campaign["started_at"] else None,
                "completed_at": campaign["completed_at"].isoformat() if campaign["completed_at"] else None,
                "progress_percentage": campaign["progress_percentage"],
                "rules_evaluated": campaign["rules_evaluated"],
                "events_found": campaign["events_found"],
                "indicators_detected": campaign["indicators_detected"],
                "error_message": campaign["error_message"]
            }
            
            # Add enhanced results if campaign is completed and has rich data
            enhanced_results = campaign.get("enhanced_results")
            if enhanced_results and campaign["status"] == "completed":
                response.update({
                    "summary": enhanced_results.get("threat_summary", {}),
                    "unique_findings": enhanced_results.get("unique_findings", []),
                    "cost_analysis": enhanced_results.get("cost_analysis", {}),
                    "execution_metrics": enhanced_results.get("execution_metrics", {})
                })
                
                # Calculate value metrics
                unique_findings = enhanced_results.get("unique_findings", [])
                cost_analysis = enhanced_results.get("cost_analysis", {})
                total_cost = cost_analysis.get("total_cost", 0)
                
                if unique_findings and total_cost > 0:
                    response["cost_per_unique_finding"] = round(total_cost / len(unique_findings), 2)
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to get campaign status: {e}")
            return None
    
    async def get_customer_campaigns(self, customer_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get customer's threat hunting campaigns"""
        try:
            campaigns = await self.security_dao.get_customer_campaigns(customer_id, limit)
            
            # Format campaigns for API response
            formatted_campaigns = []
            for campaign in campaigns:
                formatted_campaign = {
                    "campaign_id": campaign["id"],
                    "status": campaign["status"],
                    "description": campaign["description"],
                    "time_range": campaign["time_range"],
                    "created_at": campaign["created_at"].isoformat() if campaign["created_at"] else None,
                    "progress_percentage": campaign["progress_percentage"],
                    "rules_evaluated": campaign["rules_evaluated"],
                    "events_found": campaign["events_found"],
                    "indicators_detected": campaign["indicators_detected"]
                }
                formatted_campaigns.append(formatted_campaign)
            
            return formatted_campaigns
            
        except Exception as e:
            logger.error(f"Failed to get customer campaigns: {e}")
            return []
    
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

    async def get_threat_hunt_rules_with_pricing(self, customer_id: str, customer_tier: str = "smb") -> Dict[str, Any]:
        """Get available threat hunting rules with pricing from Redis cache and YAML config"""
        try:
            import yaml
            from pathlib import Path
            from events.management.cache.redis_manager import get_redis_manager
            
            # Load pricing from YAML file
            config_path = Path(__file__).parent.parent / "config" / "pricing.yml"
            with open(config_path, 'r') as f:
                pricing_config = yaml.safe_load(f)
            
            # Get Redis manager with proper environment configuration
            redis_manager = await get_redis_manager()
            
            # Read customer's custom rules from Redis
            customer_rules_key = f"security:sigma:rules:{customer_id}"
            customer_rules = await redis_manager.get(customer_rules_key, [])
            
            # Read default rules from Redis
            default_rules_key = "security:sigma:default:rules"
            default_rules = await redis_manager.get(default_rules_key, [])
            
            # Prepare response with pricing
            rules_with_pricing = []
            
            # Add customer's custom rules
            for rule in customer_rules:
                severity = rule.get("severity", "medium").lower()
                pricing_key = f"threat_hunting.custom_rule.{severity}"
                base_price = pricing_config["feature_pricing"].get(pricing_key, {}).get("base_price", 2.00)
                
                # Apply tier discount
                tier_discount = pricing_config["tier_discounts"].get(customer_tier, {}).get("discount_percent", 0) / 100
                final_price = base_price * (1 - tier_discount)
                
                rules_with_pricing.append({
                    "id": rule.get("id"),
                    "name": rule.get("name") or rule.get("title"),
                    "description": rule.get("description"),
                    "severity": severity,
                    "rule_type": "custom",
                    "mitre_techniques": rule.get("mitre_techniques", []),
                    "price_per_7h": round(final_price, 2)
                })
            
            # Add default rules
            for rule in default_rules:
                severity = rule.get("severity", "medium").lower()
                pricing_key = f"threat_hunting.default_rule.{severity}"
                base_price = pricing_config["feature_pricing"].get(pricing_key, {}).get("base_price", 1.00)
                
                # Apply tier discount
                tier_discount = pricing_config["tier_discounts"].get(customer_tier, {}).get("discount_percent", 0) / 100
                final_price = base_price * (1 - tier_discount)
                
                rules_with_pricing.append({
                    "id": rule.get("id"),
                    "name": rule.get("name") or rule.get("title"),
                    "description": rule.get("description"),
                    "severity": severity,
                    "rule_type": "default",
                    "mitre_techniques": rule.get("mitre_techniques", []),
                    "price_per_7h": round(final_price, 2)
                })
            
            # Group by severity for easier frontend consumption
            pricing_summary = {}
            for severity in ["low", "medium", "high", "critical"]:
                custom_price = pricing_config["feature_pricing"].get(f"threat_hunting.custom_rule.{severity}", {}).get("base_price", 2.00)
                default_price = pricing_config["feature_pricing"].get(f"threat_hunting.default_rule.{severity}", {}).get("base_price", 1.00)
                
                tier_discount = pricing_config["tier_discounts"].get(customer_tier, {}).get("discount_percent", 0) / 100
                
                pricing_summary[severity] = {
                    "custom_rule_price": round(custom_price * (1 - tier_discount), 2),
                    "default_rule_price": round(default_price * (1 - tier_discount), 2)
                }
            
            return {
                "rules": rules_with_pricing,
                "pricing_summary": pricing_summary,
                "total_available": len(rules_with_pricing),
                "customer_rules_count": len(customer_rules),
                "default_rules_count": len(default_rules),
                "tier": customer_tier,
                "currency": "USD"
            }
            
        except Exception as e:
            logger.error(f"Failed to get threat hunt rules with pricing: {e}")
            raise

    # Enhanced Threat Hunting Helper Methods
    
    def _parse_time_range(self, time_range: str) -> int:
        """Parse time range string to hours"""
        time_range = time_range.lower()
        if time_range.endswith('h'):
            return int(time_range[:-1])
        elif time_range.endswith('d'):
            return int(time_range[:-1]) * 24
        elif time_range == '24h':
            return 24
        elif time_range == '7d':
            return 168  # 7 * 24
        elif time_range == '30d':
            return 720  # 30 * 24
        else:
            return 24  # Default to 24 hours

    async def _analyze_threats_for_hunting(
        self, 
        events: List[Dict[str, Any]], 
        rules: List[Dict[str, Any]], 
        customer_id: str,
        time_range: str
    ) -> Dict[str, Any]:
        """Perform enhanced threat analysis with unique findings"""
        try:
            # Group events by unique threat patterns
            unique_findings = []
            finding_counter = 1
            
            # Group events by rule_id and key indicators for deduplication
            threat_groups = {}
            
            for event in events:
                rule_id = event.get("rule_id", "unknown")
                severity = event.get("severity", "medium")
                
                # Extract key indicators for grouping (unique threat identification)
                key_indicators = self._extract_threat_indicators(event)
                
                # Create unique key for this threat pattern
                threat_key = f"{rule_id}_{key_indicators.get('primary_indicator', 'unknown')}"
                
                if threat_key not in threat_groups:
                    threat_groups[threat_key] = {
                        "events": [],
                        "rule_id": rule_id,
                        "severity": severity,
                        "indicators": key_indicators,
                        "first_seen": event.get("created_at"),
                        "last_seen": event.get("created_at")
                    }
                
                threat_groups[threat_key]["events"].append(event)
                
                # Update time bounds
                event_time = event.get("created_at")
                if event_time:
                    if not threat_groups[threat_key]["first_seen"] or event_time < threat_groups[threat_key]["first_seen"]:
                        threat_groups[threat_key]["first_seen"] = event_time
                    if not threat_groups[threat_key]["last_seen"] or event_time > threat_groups[threat_key]["last_seen"]:
                        threat_groups[threat_key]["last_seen"] = event_time

            # Convert groups to unique findings
            for threat_key, group in threat_groups.items():
                rule_info = self._get_rule_info_by_id(group["rule_id"], rules)
                
                finding = {
                    "finding_id": f"THF-{finding_counter:03d}",
                    "rule_id": group["rule_id"],
                    "rule_name": rule_info.get("name") or rule_info.get("title", "Unknown Rule"),
                    "severity": group["severity"],
                    "threat_type": self._determine_threat_type(rule_info),
                    "attack_technique": self._extract_attack_technique(rule_info),
                    "affected_asset": group["indicators"].get("affected_asset", "unknown"),
                    "source_indicators": group["indicators"],
                    "first_seen": group["first_seen"],
                    "last_seen": group["last_seen"],
                    "event_count": len(group["events"]),
                    "confidence": self._calculate_confidence(group),
                    "recommended_action": self._generate_recommendation(group, rule_info),
                    "threat_context": self._generate_threat_context(group, rule_info)
                }
                
                unique_findings.append(finding)
                finding_counter += 1

            # Sort by severity and confidence
            unique_findings.sort(key=lambda x: (
                {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(x["severity"], 0),
                x["confidence"]
            ), reverse=True)

            # Create summary
            summary = {
                "total_events_analyzed": len(events),
                "unique_threats_found": len(unique_findings),
                "high_priority_threats": len([f for f in unique_findings if f["severity"] in ["high", "critical"]]),
                "attack_techniques_detected": list(set([f["attack_technique"] for f in unique_findings if f["attack_technique"]]))
            }

            return {
                "unique_findings": unique_findings,
                "summary": summary
            }

        except Exception as e:
            logger.error(f"Failed to analyze threats for hunting: {e}")
            return {"unique_findings": [], "summary": {"total_events_analyzed": 0, "unique_threats_found": 0, "high_priority_threats": 0, "attack_techniques_detected": []}}

    def _extract_threat_indicators(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key threat indicators from event for deduplication"""
        event_data = event.get("event_data", {})
        matched_fields = event.get("matched_fields", {})
        
        # Extract primary indicators based on common security fields
        indicators = {}
        
        # Network indicators
        src_ip = event_data.get("src_ip") or matched_fields.get("src_ip") or event_data.get("source_ip")
        dst_ip = event_data.get("dst_ip") or matched_fields.get("dst_ip") or event_data.get("destination_ip")
        
        # User indicators
        user = event_data.get("user") or matched_fields.get("user") or event_data.get("username")
        
        # Asset indicators
        hostname = event_data.get("hostname") or matched_fields.get("hostname") or event_data.get("host")
        
        # Process indicators
        process = event_data.get("process") or matched_fields.get("process") or event_data.get("process_name")
        
        # Determine primary indicator for grouping
        primary_indicator = src_ip or user or hostname or process or "generic"
        
        indicators = {
            "primary_indicator": primary_indicator,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "user": user,
            "affected_asset": hostname or "unknown",
            "process": process
        }
        
        # Add specific indicators based on event type
        if "login" in str(event_data).lower():
            indicators["failed_logins"] = event_data.get("failed_count", 1)
            indicators["login_type"] = "authentication"
            
        if "network" in str(event_data).lower():
            indicators["port"] = event_data.get("dst_port") or matched_fields.get("dst_port")
            indicators["protocol"] = event_data.get("protocol") or matched_fields.get("protocol")
        
        return indicators

    def _get_rule_info_by_id(self, rule_id: str, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get rule information by ID"""
        for rule in rules:
            if rule.get("id") == rule_id:
                return rule
        return {"name": f"Rule {rule_id[:8]}", "description": "Unknown rule"}

    def _determine_threat_type(self, rule_info: Dict[str, Any]) -> str:
        """Determine threat type from rule information"""
        rule_name = rule_info.get("name", "").lower()
        description = rule_info.get("description", "").lower()
        tags = rule_info.get("tags", [])
        
        if any(term in rule_name + description for term in ["brute", "force", "login", "auth"]):
            return "Credential Access"
        elif any(term in rule_name + description for term in ["lateral", "movement", "spread"]):
            return "Lateral Movement"
        elif any(term in rule_name + description for term in ["exec", "command", "powershell", "script"]):
            return "Execution"
        elif any(term in rule_name + description for term in ["network", "connection", "traffic"]):
            return "Command and Control"
        elif "persistence" in tags or any(term in rule_name + description for term in ["persist", "startup"]):
            return "Persistence"
        else:
            return "General Security"

    def _extract_attack_technique(self, rule_info: Dict[str, Any]) -> Optional[str]:
        """Extract MITRE ATT&CK technique from rule"""
        mitre_techniques = rule_info.get("mitre_techniques", [])
        attack_techniques = rule_info.get("attack_techniques", [])
        
        # Return first technique found
        all_techniques = mitre_techniques + attack_techniques
        return all_techniques[0] if all_techniques else None

    def _calculate_confidence(self, group: Dict[str, Any]) -> int:
        """Calculate confidence score for threat finding"""
        base_confidence = 60
        
        # More events = higher confidence
        event_count = len(group["events"])
        if event_count > 10:
            base_confidence += 30
        elif event_count > 5:
            base_confidence += 20
        elif event_count > 2:
            base_confidence += 10
        
        # High severity = higher confidence
        if group["severity"] == "critical":
            base_confidence += 25
        elif group["severity"] == "high":
            base_confidence += 15
        elif group["severity"] == "medium":
            base_confidence += 5
        
        # Multiple indicators = higher confidence
        indicators = group["indicators"]
        if indicators.get("src_ip") and indicators.get("user"):
            base_confidence += 10
        
        return min(base_confidence, 95)  # Cap at 95%

    def _generate_recommendation(self, group: Dict[str, Any], rule_info: Dict[str, Any]) -> str:
        """Generate actionable recommendation"""
        indicators = group["indicators"]
        threat_type = self._determine_threat_type(rule_info)
        
        if threat_type == "Credential Access":
            if indicators.get("src_ip"):
                return f"Block source IP {indicators['src_ip']} and review account security for affected users"
            else:
                return "Review user account security and implement additional authentication controls"
        elif threat_type == "Lateral Movement":
            return f"Isolate affected asset {indicators.get('affected_asset', 'unknown')} and review network segmentation"
        elif threat_type == "Execution":
            return f"Investigate process execution on {indicators.get('affected_asset', 'unknown')} and review endpoint security"
        elif threat_type == "Command and Control":
            return f"Block network connections and investigate potential malware on {indicators.get('affected_asset', 'unknown')}"
        else:
            return f"Investigate security event on {indicators.get('affected_asset', 'unknown')} and implement appropriate controls"

    def _generate_threat_context(self, group: Dict[str, Any], rule_info: Dict[str, Any]) -> str:
        """Generate threat context description"""
        indicators = group["indicators"]
        event_count = len(group["events"])
        threat_type = self._determine_threat_type(rule_info)
        
        if threat_type == "Credential Access" and event_count > 5:
            return f"Coordinated brute force attack with {event_count} attempts targeting authentication systems"
        elif threat_type == "Lateral Movement":
            return f"Potential lateral movement activity detected across {event_count} events"
        elif threat_type == "Execution" and indicators.get("process"):
            return f"Suspicious process execution detected {event_count} times: {indicators['process']}"
        else:
            return f"Security pattern detected across {event_count} events requiring investigation"

    async def _calculate_hunting_costs(self, rules: List[Dict[str, Any]], time_range: str, customer_id: str) -> Dict[str, Any]:
        """Calculate threat hunting campaign costs"""
        try:
            import yaml
            from pathlib import Path
            
            # Load pricing config
            config_path = Path(__file__).parent.parent / "config" / "pricing.yml"
            with open(config_path, 'r') as f:
                pricing_config = yaml.safe_load(f)
            
            # Calculate time blocks (normalize to 7-hour periods)
            hours = self._parse_time_range(time_range)
            time_blocks = max(1, hours / 7.0)  # Minimum 1 block
            
            # TODO: Get customer tier from tenant data
            customer_tier = "smb"  # Default for now
            tier_discount = pricing_config["tier_discounts"].get(customer_tier, {}).get("discount_percent", 0) / 100
            
            total_cost = 0
            cost_breakdown = []
            
            # Group rules by type and severity
            rule_costs = {}
            
            for rule in rules:
                customer_rule_id = rule.get("customer_id")
                rule_type = "custom" if customer_rule_id and customer_rule_id != "default" else "default"
                severity = rule.get("severity", "medium").lower()
                
                pricing_key = f"threat_hunting.{rule_type}_rule.{severity}"
                base_price = pricing_config["feature_pricing"].get(pricing_key, {}).get("base_price", 1.00)
                
                # Apply tier discount and time blocks
                final_price = base_price * (1 - tier_discount) * time_blocks
                
                rule_cost_key = f"{rule_type}_{severity}"
                if rule_cost_key not in rule_costs:
                    rule_costs[rule_cost_key] = {"count": 0, "total_cost": 0, "rule_type": rule_type, "severity": severity}
                
                rule_costs[rule_cost_key]["count"] += 1
                rule_costs[rule_cost_key]["total_cost"] += final_price
                total_cost += final_price
            
            # Format breakdown
            for cost_info in rule_costs.values():
                cost_breakdown.append({
                    "rule_type": cost_info["rule_type"],
                    "severity": cost_info["severity"],
                    "rule_count": cost_info["count"],
                    "cost": round(cost_info["total_cost"], 2)
                })
            
            return {
                "total_cost": round(total_cost, 2),
                "cost_breakdown": cost_breakdown,
                "time_blocks_used": round(time_blocks, 2),
                "time_range": time_range,
                "tier": customer_tier,
                "currency": "USD"
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate hunting costs: {e}")
            return {"total_cost": 0, "cost_breakdown": [], "currency": "USD"}

    async def _analyze_existing_security_events(
        self, 
        events: List[Dict[str, Any]], 
        rule_ids: List[str],
        customer_id: str,
        time_range: str
    ) -> Dict[str, Any]:
        """Analyze existing security events for unique threat patterns"""
        try:
            # Group events for deduplication
            threat_groups = {}
            
            for event in events:
                rule_id = event.get("rule_id")
                
                # Extract threat indicators from raw_log_data and enrichment_data
                raw_log = event.get("raw_log_data", {})
                enrichment = event.get("enrichment_data", {})
                
                # Create unique threat signature
                threat_indicators = self._extract_threat_signature_from_security_event(raw_log, enrichment, event)
                threat_key = f"{rule_id}_{threat_indicators.get('primary_indicator', 'unknown')}"
                
                if threat_key not in threat_groups:
                    threat_groups[threat_key] = {
                        "events": [],
                        "rule_id": rule_id,
                        "rule_name": event.get("title", "Unknown Rule"),
                        "severity": event.get("severity", "medium"),
                        "indicators": threat_indicators,
                        "first_seen": event.get("created_at"),
                        "last_seen": event.get("created_at"),
                        "mitre_techniques": event.get("mitre_techniques", [])
                    }
                
                threat_groups[threat_key]["events"].append(event)
                
                # Update time bounds
                event_time = event.get("created_at")
                if event_time:
                    if not threat_groups[threat_key]["first_seen"] or event_time < threat_groups[threat_key]["first_seen"]:
                        threat_groups[threat_key]["first_seen"] = event_time
                    if not threat_groups[threat_key]["last_seen"] or event_time > threat_groups[threat_key]["last_seen"]:
                        threat_groups[threat_key]["last_seen"] = event_time
            
            # Convert to unique findings with actionable intelligence
            unique_findings = []
            for i, (threat_key, group) in enumerate(threat_groups.items(), 1):
                finding = {
                    "finding_id": f"THF-{i:03d}",
                    "rule_id": group["rule_id"],
                    "rule_name": group["rule_name"],
                    "severity": group["severity"],
                    "threat_type": self._classify_threat_type_from_group(group),
                    "attack_technique": group["mitre_techniques"][0] if group["mitre_techniques"] else None,
                    "affected_asset": group["indicators"].get("affected_asset", "unknown"),
                    "source_indicators": group["indicators"],
                    "first_seen": group["first_seen"],
                    "last_seen": group["last_seen"],
                    "event_count": len(group["events"]),
                    "confidence": self._calculate_threat_confidence_from_group(group),
                    "recommended_action": self._generate_actionable_recommendation_from_group(group),
                    "threat_context": self._generate_threat_narrative_from_group(group)
                }
                unique_findings.append(finding)
            
            # Sort by severity and confidence
            unique_findings.sort(key=lambda x: (
                {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(x["severity"], 0),
                x["confidence"]
            ), reverse=True)
            
            # Create summary
            summary = {
                "total_events_analyzed": len(events),
                "unique_threats_found": len(unique_findings),
                "high_priority_threats": len([f for f in unique_findings if f["severity"] in ["high", "critical"]]),
                "attack_techniques_detected": list(set([f["attack_technique"] for f in unique_findings if f["attack_technique"]]))
            }
            
            return {
                "unique_findings": unique_findings,
                "summary": summary
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze existing security events: {e}")
            return {"unique_findings": [], "summary": {"total_events_analyzed": 0, "unique_threats_found": 0, "high_priority_threats": 0, "attack_techniques_detected": []}}

    def _extract_threat_signature_from_security_event(self, raw_log: Dict[str, Any], enrichment: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract threat signature from security event for deduplication"""
        # Extract nested normalized log data and threat context
        normalized_log = raw_log.get("normalized_log", {})
        threat_context = enrichment.get("threat_context", {})
        network_indicators = threat_context.get("network_indicators", {})
        
        # Combine all data sources for comprehensive indicator extraction
        combined_data = {**raw_log, **enrichment, **normalized_log, **network_indicators}
        
        # Extract primary indicators from multiple possible locations
        src_ip = (network_indicators.get("src_ip") or 
                 normalized_log.get("src_ip") or 
                 combined_data.get("source_ip"))
        
        user = (network_indicators.get("user") or 
               normalized_log.get("user") or 
               combined_data.get("username"))
        
        hostname = (network_indicators.get("host") or 
                   normalized_log.get("host") or 
                   normalized_log.get("hostname") or
                   combined_data.get("hostname"))
        
        process = (combined_data.get("process") or 
                  combined_data.get("process_name"))
        
        event_type = normalized_log.get("event_type")
        status_code = normalized_log.get("status_code")
        
        # Determine primary indicator for grouping (prefer specific indicators over generic rule ID)
        primary_indicator = (src_ip or user or hostname or process or 
                           f"{event_type}_{status_code}" if event_type else
                           f"rule_{event.get('rule_id', 'unknown')[:8]}")
        
        return {
            "primary_indicator": primary_indicator,
            "src_ip": src_ip,
            "user": user,
            "affected_asset": hostname or "unknown",
            "process": process,
            "event_type": event_type,
            "status_code": status_code,
            "raw_indicators": combined_data
        }

    def _classify_threat_type_from_group(self, group: Dict[str, Any]) -> str:
        """Classify threat type from security event group"""
        rule_name = group.get("rule_name", "").lower()
        indicators = group.get("indicators", {})
        
        if any(term in rule_name for term in ["brute", "force", "login", "auth", "credential"]):
            return "Credential Access"
        elif any(term in rule_name for term in ["lateral", "movement", "spread"]):
            return "Lateral Movement"
        elif any(term in rule_name for term in ["exec", "command", "powershell", "script"]):
            return "Execution"
        elif any(term in rule_name for term in ["network", "connection", "traffic", "c2"]):
            return "Command and Control"
        elif any(term in rule_name for term in ["persist", "startup", "install"]):
            return "Persistence"
        else:
            return "Security Event"

    def _calculate_threat_confidence_from_group(self, group: Dict[str, Any]) -> int:
        """Calculate confidence score for threat finding from event group"""
        base_confidence = 70  # Start higher for already-processed security events
        
        # More events = higher confidence
        event_count = len(group["events"])
        if event_count > 10:
            base_confidence += 20
        elif event_count > 5:
            base_confidence += 15
        elif event_count > 2:
            base_confidence += 10
        
        # Severity impact
        severity = group.get("severity", "medium")
        if severity == "critical":
            base_confidence += 20
        elif severity == "high":
            base_confidence += 15
        elif severity == "medium":
            base_confidence += 5
        
        return min(base_confidence, 95)  # Cap at 95%

    def _generate_actionable_recommendation_from_group(self, group: Dict[str, Any]) -> str:
        """Generate actionable recommendation from event group"""
        threat_type = self._classify_threat_type_from_group(group)
        indicators = group.get("indicators", {})
        
        if threat_type == "Credential Access":
            if indicators.get("src_ip"):
                return f"Block source IP {indicators['src_ip']} and review account security for user {indicators.get('user', 'affected users')}"
            return "Review account security and implement additional authentication controls"
        elif threat_type == "Lateral Movement":
            return f"Isolate affected asset {indicators.get('affected_asset', 'unknown')} and review network segmentation"
        elif threat_type == "Execution":
            return f"Investigate process execution on {indicators.get('affected_asset', 'unknown')} and review endpoint security"
        elif threat_type == "Command and Control":
            return f"Block network connections from {indicators.get('affected_asset', 'unknown')} and investigate potential malware"
        else:
            return f"Investigate security events on {indicators.get('affected_asset', 'unknown')} and implement appropriate controls"

    def _generate_threat_narrative_from_group(self, group: Dict[str, Any]) -> str:
        """Generate threat narrative from event group"""
        event_count = len(group["events"])
        threat_type = self._classify_threat_type_from_group(group)
        rule_name = group.get("rule_name", "Unknown Rule")
        
        if threat_type == "Credential Access":
            return f"Multiple authentication-related security events detected: {event_count} instances of '{rule_name}' indicating potential credential compromise"
        elif threat_type == "Lateral Movement":
            return f"Lateral movement pattern detected: {event_count} security events suggesting attacker progression through network"
        elif threat_type == "Execution":
            return f"Suspicious execution activity: {event_count} instances of '{rule_name}' indicating potential malicious code execution"
        else:
            return f"Security pattern detected: {event_count} instances of '{rule_name}' requiring investigation"
    