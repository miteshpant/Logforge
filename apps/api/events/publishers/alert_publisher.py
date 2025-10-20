"""
Alert Event Publisher
Specialized publisher for alert lifecycle events
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
import structlog

from ..base import BaseEvent, EventPriority, EventMetadata
from ..constants import (
    EVENT_ALERT_RULE_CREATED,
    EVENT_ALERT_RULE_UPDATED,
    EVENT_ALERT_RULE_DELETED,
    EVENT_ALERT_RULE_ENABLED,
    EVENT_ALERT_RULE_DISABLED,
    EVENT_ALERT_TRIGGERED,
    EVENT_ALERT_ACKNOWLEDGED,
    EVENT_ALERT_RESOLVED
)

logger = structlog.get_logger(__name__)


class AlertEventPublisher:
    """Publisher for alert lifecycle events"""

    def __init__(self, publisher_manager):
        self.publisher_manager = publisher_manager
        self.logger = logger.bind(component="alert_event_publisher")

    async def publish_rule_created(
        self,
        customer_id: str,
        rule_data: Dict[str, Any],
        created_by: str = "api-user",
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when an alert rule is created

        Args:
            customer_id: Customer identifier
            rule_data: The created alert rule data
            created_by: User who created the rule
            correlation_id: Request correlation ID
            trace_id: Distributed tracing ID
        """
        try:
            event_data = {
                "rule_id": rule_data.get("id"),
                "rule_name": rule_data.get("name"),
                "rule_type": rule_data.get("rule_type"),
                "severity": rule_data.get("severity"),
                "enabled": rule_data.get("enabled", True),
                "created_by": created_by,
                "conditions_count": len(rule_data.get("conditions", [])),
                "filters_count": len(rule_data.get("filters", [])),
                "notification_channels": rule_data.get("notification_channels", []),
                "evaluation_interval": rule_data.get("evaluation_interval"),
                "cooldown_period": rule_data.get("cooldown_period"),
                "created_at": datetime.utcnow().isoformat(),
                "rule_data": rule_data  # Include full rule data for cache updates
            }

            metadata = EventMetadata(
                source_service="alert-service",
                correlation_id=correlation_id,
                trace_id=trace_id,
                priority=EventPriority.MEDIUM
            )

            event = BaseEvent(
                event_type=EVENT_ALERT_RULE_CREATED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            
            # Check if any publisher succeeded
            success_count = sum(1 for result in results.values() if result)
            total_publishers = len(results)
            success = success_count > 0

            if success:
                self.logger.info(
                    "Alert rule created event published",
                    customer_id=customer_id,
                    rule_id=rule_data.get("id"),
                    rule_name=rule_data.get("name"),
                    rule_type=rule_data.get("rule_type"),
                    created_by=created_by,
                    successful_publishers=success_count,
                    total_publishers=total_publishers,
                    publisher_results=results
                )
            else:
                self.logger.error(
                    "Failed to publish alert rule created event to any publisher",
                    customer_id=customer_id,
                    rule_id=rule_data.get("id"),
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing alert rule created event",
                customer_id=customer_id,
                rule_id=rule_data.get("id"),
                error=str(e),
                exc_info=True
            )
            return False

    async def publish_rule_updated(
        self,
        customer_id: str,
        rule_data: Dict[str, Any],
        updates: Dict[str, Any],
        updated_by: str = "api-user",
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when an alert rule is updated

        Args:
            customer_id: Customer identifier
            rule_data: The updated alert rule data
            updates: Dictionary of fields that were updated
            updated_by: User who updated the rule
            correlation_id: Request correlation ID
            trace_id: Distributed tracing ID
        """
        try:
            event_data = {
                "rule_id": rule_data.get("id"),
                "rule_name": rule_data.get("name"),
                "rule_type": rule_data.get("rule_type"),
                "severity": rule_data.get("severity"),
                "enabled": rule_data.get("enabled", True),
                "updated_by": updated_by,
                "updated_fields": list(updates.keys()),
                "conditions_count": len(rule_data.get("conditions", [])),
                "filters_count": len(rule_data.get("filters", [])),
                "notification_channels": rule_data.get("notification_channels", []),
                "evaluation_interval": rule_data.get("evaluation_interval"),
                "cooldown_period": rule_data.get("cooldown_period"),
                "updated_at": datetime.utcnow().isoformat(),
                "rule_data": rule_data,  # Include full rule data for cache updates
                "changes": updates  # Include the specific changes made
            }

            metadata = EventMetadata(
                source_service="alert-service",
                correlation_id=correlation_id,
                trace_id=trace_id,
                priority=EventPriority.MEDIUM
            )

            event = BaseEvent(
                event_type=EVENT_ALERT_RULE_UPDATED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = any(results.values())

            if success:
                self.logger.info(
                    "Alert rule updated event published",
                    customer_id=customer_id,
                    rule_id=rule_data.get("id"),
                    rule_name=rule_data.get("name"),
                    updated_fields=list(updates.keys()),
                    updated_by=updated_by,
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing alert rule updated event",
                customer_id=customer_id,
                rule_id=rule_data.get("id"),
                error=str(e),
                exc_info=True
            )
            return False

    async def publish_rule_deleted(
        self,
        customer_id: str,
        rule_id: str,
        rule_data: Optional[Dict[str, Any]] = None,
        deleted_by: str = "api-user",
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when an alert rule is deleted

        Args:
            customer_id: Customer identifier
            rule_id: ID of the deleted rule
            rule_data: Optional rule data (if available before deletion)
            deleted_by: User who deleted the rule
            correlation_id: Request correlation ID
            trace_id: Distributed tracing ID
        """
        try:
            event_data = {
                "rule_id": rule_id,
                "rule_name": rule_data.get("name") if rule_data else "unknown",
                "rule_type": rule_data.get("rule_type") if rule_data else "unknown",
                "severity": rule_data.get("severity") if rule_data else "unknown",
                "deleted_by": deleted_by,
                "deleted_at": datetime.utcnow().isoformat(),
                "was_enabled": rule_data.get("enabled", False) if rule_data else False,
                "conditions_count": len(rule_data.get("conditions", [])) if rule_data else 0,
                "filters_count": len(rule_data.get("filters", [])) if rule_data else 0
            }

            metadata = EventMetadata(
                source_service="alert-service",
                correlation_id=correlation_id,
                trace_id=trace_id,
                priority=EventPriority.MEDIUM
            )

            event = BaseEvent(
                event_type=EVENT_ALERT_RULE_DELETED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = any(results.values())

            if success:
                self.logger.info(
                    "Alert rule deleted event published",
                    customer_id=customer_id,
                    rule_id=rule_id,
                    rule_name=event_data["rule_name"],
                    deleted_by=deleted_by,
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing alert rule deleted event",
                customer_id=customer_id,
                rule_id=rule_id,
                error=str(e),
                exc_info=True
            )
            return False

    async def publish_rule_enabled(
        self,
        customer_id: str,
        rule_data: Dict[str, Any],
        enabled_by: str = "api-user",
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when an alert rule is enabled

        Args:
            customer_id: Customer identifier
            rule_data: The enabled alert rule data
            enabled_by: User who enabled the rule
            correlation_id: Request correlation ID
        """
        try:
            event_data = {
                "rule_id": rule_data.get("id"),
                "rule_name": rule_data.get("name"),
                "rule_type": rule_data.get("rule_type"),
                "severity": rule_data.get("severity"),
                "enabled_by": enabled_by,
                "enabled_at": datetime.utcnow().isoformat(),
                "evaluation_interval": rule_data.get("evaluation_interval"),
                "rule_data": rule_data  # Include full rule data for cache updates
            }

            metadata = EventMetadata(
                source_service="alert-service",
                correlation_id=correlation_id,
                priority=EventPriority.MEDIUM
            )

            event = BaseEvent(
                event_type=EVENT_ALERT_RULE_ENABLED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = any(results.values())

            if success:
                self.logger.info(
                    "Alert rule enabled event published",
                    customer_id=customer_id,
                    rule_id=rule_data.get("id"),
                    rule_name=rule_data.get("name"),
                    enabled_by=enabled_by,
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing alert rule enabled event",
                customer_id=customer_id,
                rule_id=rule_data.get("id"),
                error=str(e)
            )
            return False

    async def publish_rule_disabled(
        self,
        customer_id: str,
        rule_data: Dict[str, Any],
        disabled_by: str = "api-user",
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when an alert rule is disabled

        Args:
            customer_id: Customer identifier
            rule_data: The disabled alert rule data
            disabled_by: User who disabled the rule
            correlation_id: Request correlation ID
        """
        try:
            event_data = {
                "rule_id": rule_data.get("id"),
                "rule_name": rule_data.get("name"),
                "rule_type": rule_data.get("rule_type"),
                "severity": rule_data.get("severity"),
                "disabled_by": disabled_by,
                "disabled_at": datetime.utcnow().isoformat(),
                "rule_data": rule_data  # Include full rule data for cache updates
            }

            metadata = EventMetadata(
                source_service="alert-service",
                correlation_id=correlation_id,
                priority=EventPriority.MEDIUM
            )

            event = BaseEvent(
                event_type=EVENT_ALERT_RULE_DISABLED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = any(results.values())

            if success:
                self.logger.info(
                    "Alert rule disabled event published",
                    customer_id=customer_id,
                    rule_id=rule_data.get("id"),
                    rule_name=rule_data.get("name"),
                    disabled_by=disabled_by,
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing alert rule disabled event",
                customer_id=customer_id,
                rule_id=rule_data.get("id"),
                error=str(e)
            )
            return False

    async def publish_alert_triggered(
        self,
        customer_id: str,
        alert_data: Dict[str, Any],
        rule_data: Dict[str, Any],
        trigger_context: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when an alert is triggered

        Args:
            customer_id: Customer identifier
            alert_data: The triggered alert instance data
            rule_data: The rule that triggered the alert
            trigger_context: Context about what triggered the alert
            correlation_id: Request correlation ID
        """
        try:
            event_data = {
                "alert_id": alert_data.get("id"),
                "rule_id": rule_data.get("id"),
                "rule_name": rule_data.get("name"),
                "rule_type": rule_data.get("rule_type"),
                "severity": alert_data.get("severity"),
                "title": alert_data.get("title"),
                "message": alert_data.get("message"),
                "triggered_at": datetime.utcnow().isoformat(),
                "trigger_context": trigger_context,
                "notification_channels": rule_data.get("notification_channels", []),
                "status": alert_data.get("status", "active")
            }

            metadata = EventMetadata(
                source_service="alert-engine",
                correlation_id=correlation_id,
                priority=EventPriority.HIGH  # Alert triggers are high priority
            )

            event = BaseEvent(
                event_type=EVENT_ALERT_TRIGGERED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = any(results.values())

            if success:
                self.logger.info(
                    "Alert triggered event published",
                    customer_id=customer_id,
                    alert_id=alert_data.get("id"),
                    rule_id=rule_data.get("id"),
                    rule_name=rule_data.get("name"),
                    severity=alert_data.get("severity"),
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing alert triggered event",
                customer_id=customer_id,
                alert_id=alert_data.get("id"),
                rule_id=rule_data.get("id"),
                error=str(e)
            )
            return False

    async def publish_batch_events(self, events: List[BaseEvent]) -> Dict[str, Any]:
        """
        Publish multiple alert events in batch for better performance

        Args:
            events: List of alert events to publish

        Returns:
            Dict with success count, failed count, and errors
        """
        try:
            results = await self.publisher_manager.publish_batch(events)

            self.logger.info(
                "Batch alert events published",
                total_events=len(events),
                successful=results.get("successful", 0),
                failed=results.get("failed", 0)
            )

            return results

        except Exception as e:
            self.logger.error(
                "Error publishing batch alert events",
                event_count=len(events),
                error=str(e)
            )
            return {
                "successful": 0,
                "failed": len(events),
                "errors": [str(e)]
            }


# Convenience factory for creating alert events
class AlertEventFactory:
    """Factory for creating standardized alert events"""

    @staticmethod
    def create_rule_created_event(
        customer_id: str,
        rule_data: Dict[str, Any],
        created_by: str = "api-user",
        **kwargs
    ) -> BaseEvent:
        """Create alert rule created event"""
        event_data = {
            "rule_id": rule_data.get("id"),
            "rule_name": rule_data.get("name"),
            "rule_type": rule_data.get("rule_type"),
            "severity": rule_data.get("severity"),
            "enabled": rule_data.get("enabled", True),
            "created_by": created_by,
            "created_at": datetime.utcnow().isoformat(),
            "rule_data": rule_data,
            **kwargs
        }

        return BaseEvent(
            event_type=EVENT_ALERT_RULE_CREATED,
            customer_id=customer_id,
            data=event_data,
            metadata=EventMetadata(
                source_service="alert-service",
                priority=EventPriority.MEDIUM,
                **{k: v for k, v in kwargs.items() if k in ['correlation_id', 'trace_id']}
            )
        )

    @staticmethod
    def create_rule_updated_event(
        customer_id: str,
        rule_data: Dict[str, Any],
        updates: Dict[str, Any],
        updated_by: str = "api-user",
        **kwargs
    ) -> BaseEvent:
        """Create alert rule updated event"""
        event_data = {
            "rule_id": rule_data.get("id"),
            "rule_name": rule_data.get("name"),
            "rule_type": rule_data.get("rule_type"),
            "severity": rule_data.get("severity"),
            "enabled": rule_data.get("enabled", True),
            "updated_by": updated_by,
            "updated_fields": list(updates.keys()),
            "updated_at": datetime.utcnow().isoformat(),
            "rule_data": rule_data,
            "changes": updates,
            **kwargs
        }

        return BaseEvent(
            event_type=EVENT_ALERT_RULE_UPDATED,
            customer_id=customer_id,
            data=event_data,
            metadata=EventMetadata(
                source_service="alert-service",
                priority=EventPriority.MEDIUM,
                **{k: v for k, v in kwargs.items() if k in ['correlation_id', 'trace_id']}
            )
        )

    @staticmethod
    def create_rule_deleted_event(
        customer_id: str,
        rule_id: str,
        rule_data: Optional[Dict[str, Any]] = None,
        deleted_by: str = "api-user",
        **kwargs
    ) -> BaseEvent:
        """Create alert rule deleted event"""
        event_data = {
            "rule_id": rule_id,
            "rule_name": rule_data.get("name") if rule_data else "unknown",
            "rule_type": rule_data.get("rule_type") if rule_data else "unknown",
            "severity": rule_data.get("severity") if rule_data else "unknown",
            "deleted_by": deleted_by,
            "deleted_at": datetime.utcnow().isoformat(),
            "was_enabled": rule_data.get("enabled", False) if rule_data else False,
            **kwargs
        }

        return BaseEvent(
            event_type=EVENT_ALERT_RULE_DELETED,
            customer_id=customer_id,
            data=event_data,
            metadata=EventMetadata(
                source_service="alert-service",
                priority=EventPriority.MEDIUM,
                **{k: v for k, v in kwargs.items() if k in ['correlation_id', 'trace_id']}
            )
        )