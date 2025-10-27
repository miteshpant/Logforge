"""
Security Event Handler - Handles Sigma rule events and security-related events
"""

from typing import List, Dict, Any
import structlog

from .base import EventHandler
from ..base import BaseEvent
from ..constants import (
    EVENT_LOGS_BATCH_INGESTED,
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

            if event_type == EVENT_LOGS_BATCH_INGESTED:
                return await self._handle_log_batch_event(event_data)
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

    async def _handle_log_batch_event(self, event_data: Dict[str, Any]) -> bool:
        """Handle logs.batch.ingested events for Sigma rule matching."""
        try:
            customer_id = event_data.get('customer_id')
            logs_count = len(event_data.get('logs', []))
            
            logger.info(f"🛡️ Processing log batch for Sigma rule matching: {logs_count} logs from customer {customer_id}")
            
            # Get Sigma rules for this customer (including default rules)
            sigma_rules = await self.sigma_rule_cache.get_customer_rules(customer_id, include_defaults=True)
            
            if not sigma_rules:
                logger.debug(f"No Sigma rules found for customer {customer_id}, skipping security analysis")
                return True
            
            logger.debug(f"📋 Found {len(sigma_rules)} Sigma rules for customer {customer_id}")
            
            # Process logs through Sigma rule matching
            # For now, this is a placeholder - actual matching logic will be implemented later
            detections_count = await self._process_logs_with_sigma_rules(event_data, sigma_rules)
            
            logger.debug(f"✅ Sigma rule processing completed for customer {customer_id}: {detections_count} detections")
            return True
            
        except Exception as e:
            logger.error(f"Error handling log batch event for Sigma rules: {e}")
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
            
            # For now, just log the security detection event
            # In the future, this could trigger additional processing:
            # - Send security notifications
            # - Create SIEM tickets
            # - Trigger automated incident response
            # - Update security dashboards
            # - Escalate based on severity
            
            if event_type == EVENT_SECURITY_DETECTION_TRIGGERED:
                logger.debug(f"🚨 New security detection triggered: {detection_id}")
            elif event_type == EVENT_SECURITY_DETECTION_RESOLVED:
                logger.debug(f"✅ Security detection resolved: {detection_id}")
            elif event_type == EVENT_SECURITY_DETECTION_ACKNOWLEDGED:
                logger.debug(f"👁️ Security detection acknowledged: {detection_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling security detection event {event_type}: {e}")
            return False

    async def _process_logs_with_sigma_rules(self, event_data: Dict[str, Any], sigma_rules: List[Dict[str, Any]]) -> int:
        """
        Process logs with Sigma rules to detect security events.
        
        This is a placeholder implementation. The actual Sigma rule matching logic
        will be implemented in a separate component.
        
        Args:
            event_data: Log batch event data
            sigma_rules: List of Sigma rules to match against
            
        Returns:
            int: Number of detections found
        """
        try:
            logs = event_data.get('logs', [])
            customer_id = event_data.get('customer_id')
            
            # Placeholder for actual Sigma rule matching
            # This would involve:
            # 1. Parse each log entry
            # 2. Apply each Sigma rule's detection logic
            # 3. Generate security events for matches
            # 4. Publish detection events
            
            detections_count = 0
            
            logger.debug(f"🔍 Would process {len(logs)} logs with {len(sigma_rules)} Sigma rules for customer {customer_id}")
            
            # For now, just simulate some processing
            # TODO: Implement actual Sigma rule matching logic
            
            return detections_count
            
        except Exception as e:
            logger.error(f"Error processing logs with Sigma rules: {e}")
            return 0

    def get_supported_event_types(self) -> List[str]:
        """Support security events and log events for Sigma rule matching"""
        return [
            EVENT_LOGS_BATCH_INGESTED,         # Main log processing for Sigma rule matching
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