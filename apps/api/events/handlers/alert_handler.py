"""
Alert Event Handler - Handles alert-related events and alert matching
"""

from typing import List, Dict, Any
import structlog

from .base import EventHandler
from ..base import BaseEvent
from ..constants import (
    EVENT_LOGS_BATCH_INGESTED,
    EVENT_ALERT_RULE_CREATED,
    EVENT_ALERT_RULE_UPDATED,
    EVENT_ALERT_RULE_DELETED,
    EVENT_ALERT_RULE_ENABLED,
    EVENT_ALERT_RULE_DISABLED,
    EVENT_ALERT_TRIGGERED,
    EVENT_ALERT_RESOLVED,
    EVENT_ALERT_ESCALATED,
    EVENT_ALERT_ACKNOWLEDGED
)

logger = structlog.get_logger(__name__)


class AlertEventHandler(EventHandler):
    """Handler for alert-related events and alert matching"""

    def __init__(self):
        """Initialize alert event handler with alert processor."""
        from ..management.processors.alert_processor import AlertProcessor
        self.alert_processor = AlertProcessor()

    async def handle(self, event: BaseEvent) -> bool:
        """Handle alert events"""
        logger.info(
            "Processing alert event",
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
            elif event_type.startswith("alert.rule."):
                return await self._handle_rule_event(event_type, event_data)
            elif event_type in [EVENT_ALERT_TRIGGERED, "alert.instance.triggered"]:
                return await self._handle_alert_instance_event(event_data)
            else:
                logger.info(f"Alert event type {event_type} received")
                return True

        except Exception as e:
            logger.error(f"Error handling alert event {event.event_type}: {e}")
            return False

    async def _handle_log_batch_event(self, event_data: Dict[str, Any]) -> bool:
        """Handle logs.batch.ingested events for alert matching."""
        try:
            customer_id = event_data.get('customer_id')
            logs_count = len(event_data.get('logs', []))
            
            logger.info(f"🚨 Processing log batch for alerts: {logs_count} logs from customer {customer_id}")
            
            # Process logs through alert processor
            success = await self.alert_processor.process_log_batch(event_data)
            
            if success:
                logger.debug(f"✅ Alert processing completed for customer {customer_id}")
            else:
                logger.error(f"❌ Alert processing failed for customer {customer_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error handling log batch event for alerts: {e}")
            return False

    async def _handle_rule_event(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """Handle alert rule CRUD events for cache management."""
        try:
            rule_id = event_data.get('rule_id') or event_data.get('id')
            customer_id = event_data.get('customer_id')
            
            logger.info(f"🔧 Handling rule event {event_type} for rule {rule_id} (customer: {customer_id})")
            
            # Delegate to alert processor for cache updates
            success = await self.alert_processor.handle_rule_event(event_type, event_data)
            
            if success:
                logger.debug(f"✅ Rule event {event_type} processed successfully")
            else:
                logger.error(f"❌ Failed to process rule event {event_type}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error handling rule event {event_type}: {e}")
            return False

    async def _handle_alert_instance_event(self, event_data: Dict[str, Any]) -> bool:
        """Handle alert.instance.triggered events."""
        try:
            rule_id = event_data.get('rule_id')
            customer_id = event_data.get('customer_id')
            severity = event_data.get('severity', 'unknown')
            
            logger.info(f"🚨 Alert instance triggered: rule {rule_id}, severity {severity} (customer: {customer_id})")
            
            # For now, just log the alert instance creation
            # In the future, this could trigger additional processing:
            # - Send notifications
            # - Create tickets in external systems
            # - Trigger automated responses
            # - Update alert dashboards
            
            logger.debug(f"✅ Alert instance event processed for rule {rule_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling alert instance event: {e}")
            return False

    def get_supported_event_types(self) -> List[str]:
        """Support alert events and log events for alert matching"""
        return [
            EVENT_LOGS_BATCH_INGESTED,         # Main log processing for alert matching
            EVENT_ALERT_RULE_CREATED,          # Alert rule creation
            EVENT_ALERT_RULE_UPDATED,          # Alert rule updates  
            EVENT_ALERT_RULE_DELETED,          # Alert rule deletion
            EVENT_ALERT_RULE_ENABLED,          # Alert rule enablement
            EVENT_ALERT_RULE_DISABLED,         # Alert rule disablement
            EVENT_ALERT_TRIGGERED,             # Alert triggered
            EVENT_ALERT_RESOLVED,              # Alert resolved
            EVENT_ALERT_ESCALATED,             # Alert escalated
            EVENT_ALERT_ACKNOWLEDGED,          # Alert acknowledged
            "alert.instance.triggered"         # Alert instance creation (for handling)
        ]

    def get_handler_name(self) -> str:
        """Get handler name"""
        return "alert_handler"