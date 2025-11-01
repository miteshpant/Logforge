"""
Security Event Handler - Handles Sigma rule events and security-related events
"""

from typing import List, Dict, Any
import structlog

from .base import EventHandler
from ..base import BaseEvent
from ..constants import (
    EVENT_LOGS_NORMALIZED,
    EVENT_SIGMA_RULE_CREATED,
    EVENT_SIGMA_RULE_UPDATED,
    EVENT_SIGMA_RULE_DELETED,
    EVENT_SIGMA_RULE_ENABLED,
    EVENT_SIGMA_RULE_DISABLED,
    EVENT_SECURITY_DETECTION_TRIGGERED,
    EVENT_SECURITY_DETECTION_RESOLVED,
    EVENT_SECURITY_DETECTION_ACKNOWLEDGED
)

logger = structlog.get_logger(__name__)


class SecurityEventHandler(EventHandler):
    """Handler for security-related events and Sigma rule management"""

    def __init__(self):
        """Initialize security event handler with Sigma rule cache processor."""
        from ..management.cache.sigma_rule_cache import SigmaRuleCache
        self.sigma_rule_cache = SigmaRuleCache()

    async def handle(self, event: BaseEvent) -> bool:
        """Handle security events"""
        logger.info(
            "Processing security event",
            event_id=event.metadata.event_id,
            customer_id=event.customer_id,
            event_type=event.event_type
        )

        try:
            event_type = event.event_type
            event_data = {
                'customer_id': event.customer_id,
                'rule_id': event.data.get('rule_id') or event.data.get('id'),
                **event.data
            }

            if event_type == EVENT_LOGS_NORMALIZED:
                return await self._handle_normalized_logs_event(event_data)
            elif event_type.startswith("security.sigma.rule."):
                return await self._handle_sigma_rule_event(event_type, event_data)
            elif event_type.startswith("security.detection."):
                return await self._handle_security_detection_event(event_type, event_data)
            else:
                logger.info(f"Security event type {event_type} received")
                return True

        except Exception as e:
            logger.error(f"Error handling security event {event.event_type}: {e}")
            return False

    async def _handle_normalized_logs_event(self, event_data: Dict[str, Any]) -> bool:
        """Handle logs.normalized events for Sigma rule matching."""
        try:
            customer_id = event_data.get('customer_id')
            normalized_logs = event_data.get('normalized_logs', [])
            
            logger.info(f"🛡️ Processing normalized logs for Sigma rule matching: {len(normalized_logs)} logs from customer {customer_id}")
            
            # Get Sigma rules for this customer (including default rules)
            sigma_rules = await self.sigma_rule_cache.get_customer_rules(customer_id, include_defaults=True)
            
            if not sigma_rules:
                logger.debug(f"No Sigma rules found for customer {customer_id}, skipping security analysis")
                return True
            
            logger.debug(f"📋 Found {len(sigma_rules)} Sigma rules for customer {customer_id}")
            
            # Process normalized logs through Sigma rule matching
            # Use normalized logs instead of raw logs for better field mapping support
            event_data_for_sigma = {
                'customer_id': customer_id,
                'logs': normalized_logs,  # Use normalized logs with field mapping
                'field_mapping_applied': event_data.get('field_mapping_applied', True),
                'normalization_time_ms': event_data.get('normalization_time_ms', 0)
            }
            
            detections_count = await self._process_logs_with_sigma_rules(event_data_for_sigma, sigma_rules)
            
            logger.debug(f"✅ Sigma rule processing completed for customer {customer_id}: {detections_count} detections")
            return True
            
        except Exception as e:
            logger.error(f"Error handling normalized logs event for Sigma rules: {e}")
            return False

    async def _handle_sigma_rule_event(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """Handle Sigma rule CRUD events for cache management."""
        try:
            rule_id = event_data.get('rule_id') or event_data.get('id')
            customer_id = event_data.get('customer_id')  # None for default rules
            
            logger.info(f"🔧 SecurityEventHandler received Sigma rule event {event_type} for rule {rule_id} (customer: {customer_id or 'default'})")
            logger.debug(f"🔧 Event data keys: {list(event_data.keys())}")
            
            # Delegate to Sigma rule cache for cache updates
            success = await self.sigma_rule_cache.handle_rule_event(event_type, event_data)
            
            if success:
                logger.info(f"✅ Sigma rule event {event_type} processed successfully for rule {rule_id}")
            else:
                logger.error(f"❌ Failed to process Sigma rule event {event_type} for rule {rule_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error handling Sigma rule event {event_type} for rule {rule_id}: {e}")
            return False

    async def _handle_security_detection_event(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """Handle security detection lifecycle events."""
        try:
            rule_id = event_data.get('rule_id')
            customer_id = event_data.get('customer_id')
            severity = event_data.get('severity', 'unknown')
            detection_id = event_data.get('detection_id') or event_data.get('id')
            
            logger.info(f"🚨 Security detection event: {event_type}, rule {rule_id}, severity {severity} (customer: {customer_id})")
            
            if event_type == EVENT_SECURITY_DETECTION_TRIGGERED:
                logger.debug(f"🚨 New security detection triggered: {detection_id}")
                
                # Save the security detection to database for persistence
                await self._save_security_detection_to_database(event_data)
                
            elif event_type == EVENT_SECURITY_DETECTION_RESOLVED:
                logger.debug(f"✅ Security detection resolved: {detection_id}")
                # Update status in database
                await self._update_security_detection_status(detection_id, customer_id, "resolved")
                
            elif event_type == EVENT_SECURITY_DETECTION_ACKNOWLEDGED:
                logger.debug(f"👁️ Security detection acknowledged: {detection_id}")
                # Update status in database  
                await self._update_security_detection_status(detection_id, customer_id, "acknowledged")
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling security detection event {event_type}: {e}")
            return False

    async def _process_logs_with_sigma_rules(self, event_data: Dict[str, Any], sigma_rules: List[Dict[str, Any]]) -> int:
        """
        Process logs with Sigma rules to detect security events using the SigmaRuleEngine.
        
        Args:
            event_data: Log batch event data
            sigma_rules: List of Sigma rules to match against
            
        Returns:
            int: Number of detections found
        """
        try:
            logs = event_data.get('logs', [])
            customer_id = event_data.get('customer_id')
            
            if not logs or not sigma_rules:
                logger.debug(f"📭 No logs or rules to process for customer {customer_id}")
                return 0
            
            logger.info(f"🛡️ Processing {len(logs)} logs with {len(sigma_rules)} Sigma rules for customer {customer_id}")
            
            # Import the Sigma engine
            from sigma_engine import sigma_engine
            
            # Evaluate logs against Sigma rules
            matches = await sigma_engine.evaluate_logs_against_rules(logs, sigma_rules, customer_id)
            
            detections_count = len(matches)
            
            if detections_count > 0:
                logger.info(f"🚨 Found {detections_count} security detections for customer {customer_id}")
                for match in matches:
                    logger.info(f"🔍 Detection: {match.rule_id} - {match.rule_title} (severity: {match.severity.value})")
            else:
                logger.debug(f"✅ No security detections found for customer {customer_id}")
            
            return detections_count
            
        except Exception as e:
            logger.error(f"Error processing logs with Sigma rules: {e}")
            return 0

    async def _save_security_detection_to_database(self, event_data: Dict[str, Any]) -> bool:
        """Save security detection to database for persistence."""
        try:
            from services.security_service import SecurityService
            
            security_service = SecurityService()
            
            # Transform event data for database storage
            detection_data = {
                "id": event_data.get("detection_id"),
                "customer_id": event_data.get("customer_id"),
                "rule_id": event_data.get("rule_id"),
                "rule_title": event_data.get("rule_name"),
                "severity": event_data.get("severity", "medium"),
                "status": "triggered",
                "timestamp": event_data.get("event_timestamp"),
                "event_data": event_data,  # Store full event data
                "matched_fields": event_data.get("matched_fields", {}),
                "attack_techniques": event_data.get("attack_techniques", []),
                "kill_chain_phase": None,  # Could be derived from attack_techniques
                "assigned_to": None,
                "investigation_notes": [],
                "artifacts": [],
                "source_logs": []
            }
            
            event_id = await security_service.create_security_event(detection_data)
            logger.info(f"💾 Security detection saved to database: {event_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save security detection to database: {e}")
            return False

    async def _update_security_detection_status(self, detection_id: str, customer_id: str, status: str) -> bool:
        """Update security detection status in database."""
        try:
            from services.security_service import SecurityService
            
            security_service = SecurityService()
            
            success = await security_service.update_security_event_status(
                detection_id, customer_id, status
            )
            
            if success:
                logger.info(f"💾 Security detection status updated: {detection_id} -> {status}")
            else:
                logger.warning(f"Failed to update security detection status: {detection_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to update security detection status: {e}")
            return False

    def get_supported_event_types(self) -> List[str]:
        """Support security events and log events for Sigma rule matching"""
        return [
            EVENT_LOGS_NORMALIZED,             # Process normalized logs for Sigma rule matching
            EVENT_SIGMA_RULE_CREATED,          # Sigma rule creation
            EVENT_SIGMA_RULE_UPDATED,          # Sigma rule updates  
            EVENT_SIGMA_RULE_DELETED,          # Sigma rule deletion
            EVENT_SIGMA_RULE_ENABLED,          # Sigma rule enablement
            EVENT_SIGMA_RULE_DISABLED,         # Sigma rule disablement
            EVENT_SECURITY_DETECTION_TRIGGERED, # Security detection triggered
            EVENT_SECURITY_DETECTION_RESOLVED,  # Security detection resolved
            EVENT_SECURITY_DETECTION_ACKNOWLEDGED # Security detection acknowledged
        ]

    def get_handler_name(self) -> str:
        """Get handler name"""
        return "security_handler"