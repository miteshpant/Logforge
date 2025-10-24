"""
UI Event Publisher
Specialized publisher for real-time UI notification events
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
import structlog

from ..base import BaseEvent, EventPriority, EventMetadata
from ..constants import (
    EVENT_UI_ALERT_TRIGGERED,
    EVENT_UI_ALERT_ACKNOWLEDGED,
    EVENT_UI_ALERT_RESOLVED,
    EVENT_UI_ALERT_COUNT_UPDATED,
    EVENT_UI_RULE_STATUS_CHANGED
)

logger = structlog.get_logger(__name__)


class UIEventPublisher:
    """Publisher for real-time UI notification events"""

    def __init__(self, publisher_manager):
        self.publisher_manager = publisher_manager
        self.logger = logger.bind(component="ui_event_publisher")

    async def publish_alert_triggered(
        self,
        customer_id: str,
        alert_data: Dict[str, Any],
        rule_data: Dict[str, Any],
        trigger_context: Dict[str, Any],
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Publish UI event when an alert is triggered for real-time notifications

        Args:
            customer_id: Customer identifier
            alert_data: The triggered alert instance data
            rule_data: The rule that triggered the alert
            trigger_context: Context about what triggered the alert
            correlation_id: Request correlation ID
            trace_id: Distributed tracing ID
        """
        try:
            # Extract key alert information for UI display
            event_data = {
                "alert_id": alert_data.get("id"),
                "rule_id": rule_data.get("id"),
                "rule_name": rule_data.get("name"),
                "rule_type": rule_data.get("rule_type"),
                "severity": alert_data.get("severity", rule_data.get("severity", "medium")),
                "title": self._extract_alert_title(alert_data, rule_data),
                "message": self._extract_alert_message(alert_data, trigger_context),
                "triggered_at": datetime.utcnow().isoformat(),
                "status": "triggered",
                "notification_type": "alert_triggered",
                "trigger_summary": self._create_trigger_summary(trigger_context),
                "ui_metadata": {
                    "requires_attention": True,
                    "auto_dismiss": False,
                    "display_duration": self._get_display_duration(alert_data.get("severity", "medium")),
                    "priority": self._get_ui_priority(alert_data.get("severity", "medium"))
                }
            }

            metadata = EventMetadata(
                source_service="alert-engine",
                correlation_id=correlation_id,
                trace_id=trace_id,
                priority=EventPriority.HIGH  # UI alerts are high priority for real-time display
            )

            event = BaseEvent(
                event_type=EVENT_UI_ALERT_TRIGGERED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = any(results.values())

            if success:
                self.logger.info(
                    "UI alert triggered event published",
                    customer_id=customer_id,
                    alert_id=alert_data.get("id"),
                    rule_id=rule_data.get("id"),
                    rule_name=rule_data.get("name"),
                    severity=alert_data.get("severity"),
                    publisher_results=results
                )
            else:
                self.logger.error(
                    "Failed to publish UI alert triggered event to any publisher",
                    customer_id=customer_id,
                    alert_id=alert_data.get("id"),
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing UI alert triggered event",
                customer_id=customer_id,
                alert_id=alert_data.get("id"),
                rule_id=rule_data.get("id"),
                error=str(e),
                exc_info=True
            )
            return False

    async def publish_alert_acknowledged(
        self,
        customer_id: str,
        alert_id: str,
        acknowledged_by: str,
        acknowledgment_notes: Optional[str] = None,
        correlation_id: Optional[str] = None,
        alert_instance_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Publish UI event when an alert is acknowledged

        Args:
            customer_id: Customer identifier
            alert_id: Alert instance ID
            acknowledged_by: User who acknowledged the alert
            acknowledgment_notes: Optional notes from the user
            correlation_id: Request correlation ID
        """
        try:
            event_data = {
                "alert_id": alert_id,
                "acknowledged_by": acknowledged_by,
                "acknowledged_at": datetime.utcnow().isoformat(),
                "status": "acknowledged",
                "notification_type": "alert_acknowledged",
                "acknowledgment_notes": acknowledgment_notes,
                "ui_metadata": {
                    "requires_attention": False,
                    "auto_dismiss": True,
                    "display_duration": 3000,  # 3 seconds
                    "priority": "medium"
                }
            }
            
            # Include alert instance data if provided for complete UI context
            if alert_instance_data:
                event_data.update({
                    "rule_id": alert_instance_data.get("rule_id"),
                    "rule_name": alert_instance_data.get("rule_name"),
                    "severity": alert_instance_data.get("severity"),
                    "triggered_at": alert_instance_data.get("triggered_at"),
                    "message": alert_instance_data.get("message") or alert_instance_data.get("title", "Alert acknowledged")
                })

            metadata = EventMetadata(
                source_service="alert-api",
                correlation_id=correlation_id,
                priority=EventPriority.MEDIUM
            )

            event = BaseEvent(
                event_type=EVENT_UI_ALERT_ACKNOWLEDGED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = any(results.values())

            if success:
                self.logger.info(
                    "UI alert acknowledged event published",
                    customer_id=customer_id,
                    alert_id=alert_id,
                    acknowledged_by=acknowledged_by,
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing UI alert acknowledged event",
                customer_id=customer_id,
                alert_id=alert_id,
                error=str(e)
            )
            return False

    async def publish_alert_resolved(
        self,
        customer_id: str,
        alert_id: str,
        resolved_by: str,
        resolution_notes: Optional[str] = None,
        correlation_id: Optional[str] = None,
        alert_instance_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Publish UI event when an alert is resolved

        Args:
            customer_id: Customer identifier
            alert_id: Alert instance ID
            resolved_by: User who resolved the alert
            resolution_notes: Optional resolution notes
            correlation_id: Request correlation ID
        """
        try:
            event_data = {
                "alert_id": alert_id,
                "resolved_by": resolved_by,
                "resolved_at": datetime.utcnow().isoformat(),
                "status": "resolved",
                "notification_type": "alert_resolved",
                "resolution_notes": resolution_notes,
                "ui_metadata": {
                    "requires_attention": False,
                    "auto_dismiss": True,
                    "display_duration": 5000,  # 5 seconds
                    "priority": "low"
                }
            }
            
            # Include alert instance data if provided for complete UI context
            if alert_instance_data:
                event_data.update({
                    "rule_id": alert_instance_data.get("rule_id"),
                    "rule_name": alert_instance_data.get("rule_name"),
                    "severity": alert_instance_data.get("severity"),
                    "triggered_at": alert_instance_data.get("triggered_at"),
                    "message": alert_instance_data.get("message") or alert_instance_data.get("title", "Alert resolved")
                })

            metadata = EventMetadata(
                source_service="alert-api",
                correlation_id=correlation_id,
                priority=EventPriority.MEDIUM
            )

            event = BaseEvent(
                event_type=EVENT_UI_ALERT_RESOLVED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = any(results.values())

            if success:
                self.logger.info(
                    "UI alert resolved event published",
                    customer_id=customer_id,
                    alert_id=alert_id,
                    resolved_by=resolved_by,
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing UI alert resolved event",
                customer_id=customer_id,
                alert_id=alert_id,
                error=str(e)
            )
            return False

    async def publish_alert_count_updated(
        self,
        customer_id: str,
        alert_counts: Dict[str, int],
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Publish UI event when alert counts change (for badge updates)

        Args:
            customer_id: Customer identifier
            alert_counts: Dictionary with count by status (active, acknowledged, resolved)
            correlation_id: Request correlation ID
        """
        try:
            event_data = {
                "alert_counts": alert_counts,
                "total_alerts": sum(alert_counts.values()),
                "active_alerts": alert_counts.get("active", 0),
                "acknowledged_alerts": alert_counts.get("acknowledged", 0),
                "resolved_alerts": alert_counts.get("resolved", 0),
                "updated_at": datetime.utcnow().isoformat(),
                "notification_type": "alert_count_updated",
                "ui_metadata": {
                    "requires_attention": False,
                    "auto_dismiss": True,
                    "display_duration": 0,  # No notification, just update badges
                    "priority": "low"
                }
            }

            metadata = EventMetadata(
                source_service="alert-api",
                correlation_id=correlation_id,
                priority=EventPriority.LOW  # Count updates are low priority
            )

            event = BaseEvent(
                event_type=EVENT_UI_ALERT_COUNT_UPDATED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = any(results.values())

            if success:
                self.logger.debug(
                    "UI alert count updated event published",
                    customer_id=customer_id,
                    alert_counts=alert_counts,
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing UI alert count updated event",
                customer_id=customer_id,
                error=str(e)
            )
            return False

    async def publish_rule_status_changed(
        self,
        customer_id: str,
        rule_id: str,
        rule_name: str,
        old_status: str,
        new_status: str,
        changed_by: str,
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Publish UI event when a rule status changes (enabled/disabled)

        Args:
            customer_id: Customer identifier
            rule_id: Rule ID
            rule_name: Rule name
            old_status: Previous status
            new_status: New status
            changed_by: User who changed the status
            correlation_id: Request correlation ID
        """
        try:
            event_data = {
                "rule_id": rule_id,
                "rule_name": rule_name,
                "old_status": old_status,
                "new_status": new_status,
                "changed_by": changed_by,
                "changed_at": datetime.utcnow().isoformat(),
                "notification_type": "rule_status_changed",
                "ui_metadata": {
                    "requires_attention": False,
                    "auto_dismiss": True,
                    "display_duration": 3000,  # 3 seconds
                    "priority": "medium"
                }
            }

            metadata = EventMetadata(
                source_service="alert-api",
                correlation_id=correlation_id,
                priority=EventPriority.MEDIUM
            )

            event = BaseEvent(
                event_type=EVENT_UI_RULE_STATUS_CHANGED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = any(results.values())

            if success:
                self.logger.info(
                    "UI rule status changed event published",
                    customer_id=customer_id,
                    rule_id=rule_id,
                    rule_name=rule_name,
                    old_status=old_status,
                    new_status=new_status,
                    changed_by=changed_by,
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing UI rule status changed event",
                customer_id=customer_id,
                rule_id=rule_id,
                error=str(e)
            )
            return False

    def _extract_alert_title(self, alert_data: Dict[str, Any], rule_data: Dict[str, Any]) -> str:
        """Extract or generate alert title for UI display"""
        # Try to get title from trigger_data first
        trigger_data = alert_data.get("trigger_data", {})
        if isinstance(trigger_data, str):
            import json
            try:
                trigger_data = json.loads(trigger_data)
            except:
                trigger_data = {}
        
        title = trigger_data.get("title")
        if title:
            return title
        
        # Generate title from rule name and type
        rule_name = rule_data.get("name", "Unknown Rule")
        rule_type = rule_data.get("rule_type", "alert")
        
        return f"{rule_type.title()} Alert: {rule_name}"

    def _extract_alert_message(self, alert_data: Dict[str, Any], trigger_context: Dict[str, Any]) -> str:
        """Extract or generate alert message for UI display"""
        # Try to get message from trigger_data first
        trigger_data = alert_data.get("trigger_data", {})
        if isinstance(trigger_data, str):
            import json
            try:
                trigger_data = json.loads(trigger_data)
            except:
                trigger_data = {}
        
        message = trigger_data.get("message")
        if message:
            return message
        
        # Generate message from trigger context
        condition_eval = trigger_data.get("condition_evaluation", {})
        human_readable = condition_eval.get("human_readable", "Alert condition matched")
        
        return f"Alert triggered: {human_readable}"

    def _create_trigger_summary(self, trigger_context: Dict[str, Any]) -> Dict[str, Any]:
        """Create a summary of trigger context for UI display"""
        return {
            "matched_logs_count": trigger_context.get("matched_logs_count", 0),
            "time_window": trigger_context.get("time_window", {}),
            "evaluation_time": datetime.utcnow().isoformat()
        }

    def _get_display_duration(self, severity: str) -> int:
        """Get display duration in milliseconds based on severity"""
        severity_durations = {
            "critical": 0,     # Never auto-dismiss critical alerts
            "high": 10000,     # 10 seconds
            "medium": 7000,    # 7 seconds
            "low": 5000        # 5 seconds
        }
        return severity_durations.get(severity.lower(), 7000)

    def _get_ui_priority(self, severity: str) -> str:
        """Get UI priority based on alert severity"""
        severity_priorities = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low"
        }
        return severity_priorities.get(severity.lower(), "medium")


# Convenience factory for creating UI events
class UIEventFactory:
    """Factory for creating standardized UI events"""

    @staticmethod
    def create_alert_triggered_event(
        customer_id: str,
        alert_data: Dict[str, Any],
        rule_data: Dict[str, Any],
        trigger_context: Dict[str, Any],
        **kwargs
    ) -> BaseEvent:
        """Create UI alert triggered event"""
        event_data = {
            "alert_id": alert_data.get("id"),
            "rule_id": rule_data.get("id"),
            "rule_name": rule_data.get("name"),
            "rule_type": rule_data.get("rule_type"),
            "severity": alert_data.get("severity", rule_data.get("severity", "medium")),
            "triggered_at": datetime.utcnow().isoformat(),
            "status": "triggered",
            "notification_type": "alert_triggered",
            "trigger_context": trigger_context,
            **kwargs
        }

        return BaseEvent(
            event_type=EVENT_UI_ALERT_TRIGGERED,
            customer_id=customer_id,
            data=event_data,
            metadata=EventMetadata(
                source_service="alert-engine",
                priority=EventPriority.HIGH,
                **{k: v for k, v in kwargs.items() if k in ['correlation_id', 'trace_id']}
            )
        )

    @staticmethod
    def create_alert_count_updated_event(
        customer_id: str,
        alert_counts: Dict[str, int],
        **kwargs
    ) -> BaseEvent:
        """Create UI alert count updated event"""
        event_data = {
            "alert_counts": alert_counts,
            "total_alerts": sum(alert_counts.values()),
            "updated_at": datetime.utcnow().isoformat(),
            "notification_type": "alert_count_updated",
            **kwargs
        }

        return BaseEvent(
            event_type=EVENT_UI_ALERT_COUNT_UPDATED,
            customer_id=customer_id,
            data=event_data,
            metadata=EventMetadata(
                source_service="alert-api",
                priority=EventPriority.LOW,
                **{k: v for k, v in kwargs.items() if k in ['correlation_id', 'trace_id']}
            )
        )