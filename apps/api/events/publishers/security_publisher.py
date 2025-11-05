"""
Security Event Publisher
Specialized publisher for Sigma rule and security detection events
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
import structlog

from ..base import BaseEvent, EventPriority, EventMetadata
from ..constants import (
    EVENT_SIGMA_RULE_CREATED,
    EVENT_SIGMA_RULE_UPDATED,
    EVENT_SIGMA_RULE_DELETED,
    EVENT_SIGMA_RULE_ENABLED,
    EVENT_SIGMA_RULE_DISABLED,
    EVENT_SECURITY_DETECTION_TRIGGERED,
    EVENT_SECURITY_DETECTION_RESOLVED,
    EVENT_SECURITY_DETECTION_ACKNOWLEDGED, EVENT_SECURITY_DETECTION_FALSE_POSITIVE
)

logger = structlog.get_logger(__name__)


class SecurityEventPublisher:
    """Publisher for security and Sigma rule events"""

    def __init__(self, publisher_manager):
        self.publisher_manager = publisher_manager
        self.logger = logger.bind(component="security_event_publisher")

    async def publish_sigma_rule_created(
        self,
        customer_id: Optional[str],
        rule_data: Dict[str, Any],
        created_by: str = "api-user",
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when a Sigma rule is created

        Args:
            customer_id: Customer identifier (None for default rules)
            rule_data: The created Sigma rule data
            created_by: User who created the rule
            correlation_id: Request correlation ID
            trace_id: Distributed tracing ID
        """
        try:
            event_data = {
                "rule_id": rule_data.get("id"),
                "rule_name": rule_data.get("name") or rule_data.get("title"),
                "severity": rule_data.get("severity"),
                "enabled": rule_data.get("is_enabled", True),
                "created_by": created_by,
                "attack_techniques": rule_data.get("mitre_techniques", []),
                "kill_chain_phases": rule_data.get("kill_chain_phases", []),
                "logsource": rule_data.get("logsource", {}),
                "tags": rule_data.get("tags", []),
                "is_default_rule": customer_id is None,
                "created_at": datetime.utcnow().isoformat(),
                "rule_data": rule_data  # Include full rule data for cache updates
            }

            metadata = EventMetadata(
                source_service="security-service",
                correlation_id=correlation_id,
                trace_id=trace_id,
                priority=EventPriority.MEDIUM
            )

            event = BaseEvent(
                event_type=EVENT_SIGMA_RULE_CREATED,
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
                    "Sigma rule created event published",
                    customer_id=customer_id or "default",
                    rule_id=rule_data.get("id"),
                    rule_name=rule_data.get("name") or rule_data.get("title"),
                    severity=rule_data.get("severity"),
                    created_by=created_by,
                    successful_publishers=success_count,
                    total_publishers=total_publishers
                )
            else:
                self.logger.warning(
                    "Failed to publish Sigma rule created event",
                    customer_id=customer_id or "default",
                    rule_id=rule_data.get("id"),
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing Sigma rule created event",
                customer_id=customer_id or "default",
                rule_id=rule_data.get("id"),
                error=str(e)
            )
            return False

    async def publish_sigma_rule_updated(
        self,
        customer_id: Optional[str],
        rule_data: Dict[str, Any],
        updated_by: str = "api-user",
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when a Sigma rule is updated

        Args:
            customer_id: Customer identifier (None for default rules)
            rule_data: The updated Sigma rule data
            updated_by: User who updated the rule
            correlation_id: Request correlation ID
            trace_id: Distributed tracing ID
        """
        try:
            event_data = {
                "rule_id": rule_data.get("id"),
                "rule_name": rule_data.get("name") or rule_data.get("title"),
                "severity": rule_data.get("severity"),
                "enabled": rule_data.get("is_enabled", True),
                "updated_by": updated_by,
                "attack_techniques": rule_data.get("mitre_techniques", []),
                "kill_chain_phases": rule_data.get("kill_chain_phases", []),
                "logsource": rule_data.get("logsource", {}),
                "tags": rule_data.get("tags", []),
                "is_default_rule": customer_id is None,
                "updated_at": datetime.utcnow().isoformat(),
                "rule_data": rule_data  # Include full rule data for cache updates
            }

            metadata = EventMetadata(
                source_service="security-service",
                correlation_id=correlation_id,
                trace_id=trace_id,
                priority=EventPriority.MEDIUM
            )

            event = BaseEvent(
                event_type=EVENT_SIGMA_RULE_UPDATED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)

            success_count = sum(1 for result in results.values() if result)
            success = success_count > 0

            if success:
                self.logger.info(
                    "Sigma rule updated event published",
                    customer_id=customer_id or "default",
                    rule_id=rule_data.get("id"),
                    rule_name=rule_data.get("name") or rule_data.get("title"),
                    updated_by=updated_by
                )
            else:
                self.logger.warning(
                    "Failed to publish Sigma rule updated event",
                    customer_id=customer_id or "default",
                    rule_id=rule_data.get("id"),
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing Sigma rule updated event",
                customer_id=customer_id or "default",
                rule_id=rule_data.get("id"),
                error=str(e)
            )
            return False

    async def publish_sigma_rule_deleted(
        self,
        customer_id: Optional[str],
        rule_id: str,
        rule_name: str = None,
        deleted_by: str = "api-user",
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when a Sigma rule is deleted

        Args:
            customer_id: Customer identifier (None for default rules)
            rule_id: ID of the deleted rule
            rule_name: Name of the deleted rule
            deleted_by: User who deleted the rule
            correlation_id: Request correlation ID
            trace_id: Distributed tracing ID
        """
        try:
            event_data = {
                "rule_id": rule_id,
                "rule_name": rule_name,
                "deleted_by": deleted_by,
                "is_default_rule": customer_id is None,
                "deleted_at": datetime.utcnow().isoformat()
            }

            metadata = EventMetadata(
                source_service="security-service",
                correlation_id=correlation_id,
                trace_id=trace_id,
                priority=EventPriority.MEDIUM
            )

            event = BaseEvent(
                event_type=EVENT_SIGMA_RULE_DELETED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)

            success_count = sum(1 for result in results.values() if result)
            success = success_count > 0

            if success:
                self.logger.info(
                    "Sigma rule deleted event published",
                    customer_id=customer_id or "default",
                    rule_id=rule_id,
                    rule_name=rule_name,
                    deleted_by=deleted_by
                )
            else:
                self.logger.warning(
                    "Failed to publish Sigma rule deleted event",
                    customer_id=customer_id or "default",
                    rule_id=rule_id,
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing Sigma rule deleted event",
                customer_id=customer_id or "default",
                rule_id=rule_id,
                error=str(e)
            )
            return False

    async def publish_sigma_rule_enabled(
        self,
        customer_id: Optional[str],
        rule_data: Dict[str, Any],
        enabled_by: str = "api-user",
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when a Sigma rule is enabled

        Args:
            customer_id: Customer identifier (None for default rules)
            rule_data: The Sigma rule data
            enabled_by: User who enabled the rule
            correlation_id: Request correlation ID
            trace_id: Distributed tracing ID
        """
        try:
            event_data = {
                "rule_id": rule_data.get("id"),
                "rule_name": rule_data.get("name") or rule_data.get("title"),
                "enabled_by": enabled_by,
                "is_default_rule": customer_id is None,
                "enabled_at": datetime.utcnow().isoformat(),
                "rule_data": rule_data  # Include full rule data for cache updates
            }

            metadata = EventMetadata(
                source_service="security-service",
                correlation_id=correlation_id,
                trace_id=trace_id,
                priority=EventPriority.MEDIUM
            )

            event = BaseEvent(
                event_type=EVENT_SIGMA_RULE_ENABLED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = sum(1 for result in results.values() if result) > 0

            if success:
                self.logger.info(
                    "Sigma rule enabled event published",
                    customer_id=customer_id or "default",
                    rule_id=rule_data.get("id"),
                    enabled_by=enabled_by
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing Sigma rule enabled event",
                customer_id=customer_id or "default",
                rule_id=rule_data.get("id"),
                error=str(e)
            )
            return False

    async def publish_sigma_rule_disabled(
        self,
        customer_id: Optional[str],
        rule_data: Dict[str, Any],
        disabled_by: str = "api-user",
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when a Sigma rule is disabled

        Args:
            customer_id: Customer identifier (None for default rules)
            rule_data: The Sigma rule data
            disabled_by: User who disabled the rule
            correlation_id: Request correlation ID
            trace_id: Distributed tracing ID
        """
        try:
            event_data = {
                "rule_id": rule_data.get("id"),
                "rule_name": rule_data.get("name") or rule_data.get("title"),
                "disabled_by": disabled_by,
                "is_default_rule": customer_id is None,
                "disabled_at": datetime.utcnow().isoformat(),
                "rule_data": rule_data  # Include full rule data for cache updates
            }

            metadata = EventMetadata(
                source_service="security-service",
                correlation_id=correlation_id,
                trace_id=trace_id,
                priority=EventPriority.MEDIUM
            )

            event = BaseEvent(
                event_type=EVENT_SIGMA_RULE_DISABLED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = sum(1 for result in results.values() if result) > 0

            if success:
                self.logger.info(
                    "Sigma rule disabled event published",
                    customer_id=customer_id or "default",
                    rule_id=rule_data.get("id"),
                    disabled_by=disabled_by
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing Sigma rule disabled event",
                customer_id=customer_id or "default",
                rule_id=rule_data.get("id"),
                error=str(e)
            )
            return False

    async def publish_security_detection_triggered(
        self,
        customer_id: str,
        detection_data: Dict[str, Any],
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when a security detection is triggered

        Args:
            customer_id: Customer identifier
            detection_data: The security detection data
            correlation_id: Request correlation ID
            trace_id: Distributed tracing ID
        """
        try:
            # Start with core detection fields
            event_data = {
                "detection_id": detection_data.get("id"),
                "rule_id": detection_data.get("rule_id"),
                "rule_name": detection_data.get("rule_name"),
                "severity": detection_data.get("severity"),
                "attack_techniques": detection_data.get("attack_techniques", []),
                "matched_fields": detection_data.get("matched_fields", {}),
                "confidence": detection_data.get("confidence", 1.0),
                "event_timestamp": detection_data.get("event_timestamp"),
                "triggered_at": datetime.utcnow().isoformat()
            }
            
            # Add ALL enriched log data fields that are directly in detection_data
            enriched_fields = [
                "src_ip", "user", "host", "hostname", "service", "event_type", 
                "status_code", "message", "msg", "ts", "timestamp", "level", 
                "log_level", "user_id", "severity_num", "facility", "parser_version",
                "ingested_at", "query", "trace_id", "span_id", "attrs"
            ]
            
            for field in enriched_fields:
                if field in detection_data and detection_data[field] is not None:
                    event_data[field] = detection_data[field]
            
            # Add structured data sections
            if "artifact_data" in detection_data and detection_data["artifact_data"]:
                event_data["raw_log_data"] = detection_data["artifact_data"]
                
            if "normalized_log" in detection_data and detection_data["normalized_log"]:
                event_data["enrichment_data"] = detection_data["normalized_log"]
                
            # Add additional metadata
            event_data.update({
                "title": detection_data.get("title"),
                "description": detection_data.get("description"),
                "kill_chain_phases": detection_data.get("kill_chain_phases", []),
                "source_format": detection_data.get("source_format"),
                "field_mapping_applied": detection_data.get("field_mapping_applied", False),
                "rule_version": detection_data.get("rule_version"),
                "processing_time_ms": detection_data.get("processing_time_ms", 0),
                "recommended_actions": detection_data.get("recommended_actions", []),
                "investigation_queries": detection_data.get("investigation_queries", [])
            })

            metadata = EventMetadata(
                source_service="security-service",
                correlation_id=correlation_id,
                trace_id=trace_id,
                priority=EventPriority.HIGH  # Security detections are high priority
            )

            event = BaseEvent(
                event_type=EVENT_SECURITY_DETECTION_TRIGGERED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = sum(1 for result in results.values() if result) > 0

            if success:
                self.logger.info(
                    "Security detection triggered event published",
                    customer_id=customer_id,
                    detection_id=detection_data.get("id"),
                    rule_id=detection_data.get("rule_id"),
                    severity=detection_data.get("severity")
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing security detection triggered event",
                customer_id=customer_id,
                detection_id=detection_data.get("id"),
                error=str(e)
            )
            return False

    async def publish_security_detection_acknowledged(
        self,
        customer_id: str,
        detection_id: str,
        acknowledged_by: str,
        acknowledgment_notes: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when a security detection is acknowledged
        """
        try:
            # Combine action data with full event details
            action_data = {
                "detection_id": detection_id,
                "acknowledged_by": acknowledged_by,
                "acknowledged_at": datetime.utcnow().isoformat(),
                "status": "investigating",
                "acknowledgment_notes": acknowledgment_notes,
                "event_type": "status_change"
            }

            # Include full event data if provided
            if event_data:
                # Extract important fields from the security event
                action_data.update({
                    "rule_id": event_data.get("rule_id"),
                    "rule_name": event_data.get("title", "Unknown Rule"),
                    "severity": event_data.get("severity"),
                    "confidence": 1.0,  # Default confidence for status changes
                    "attack_techniques": self._parse_mitre_techniques(event_data.get("mitre_techniques", "[]")),
                    "matched_fields": self._parse_enrichment_data(event_data.get("enrichment_data", "{}")),
                })

            final_event_data = action_data

            event = BaseEvent(
                event_type=EVENT_SECURITY_DETECTION_ACKNOWLEDGED,
                customer_id=customer_id,
                data=final_event_data,
                metadata=EventMetadata(
                    source_service="security-service",
                    priority=EventPriority.HIGH,
                    correlation_id=correlation_id,
                    trace_id=trace_id
                )
            )

            success = await self.publisher_manager.publish(event)

            if success:
                self.logger.info(
                    "Security detection acknowledged event published",
                    customer_id=customer_id,
                    detection_id=detection_id,
                    acknowledged_by=acknowledged_by
                )
            else:
                self.logger.warning(
                    "Failed to publish security detection acknowledged event",
                    customer_id=customer_id,
                    detection_id=detection_id
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing security detection acknowledged event",
                customer_id=customer_id,
                detection_id=detection_id,
                error=str(e)
            )
            return False

    async def publish_security_detection_resolved(
        self,
        customer_id: str,
        detection_id: str,
        resolved_by: str,
        resolution_notes: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when a security detection is resolved
        """
        try:
            # Combine action data with full event details
            action_data = {
                "detection_id": detection_id,
                "resolved_by": resolved_by,
                "resolved_at": datetime.utcnow().isoformat(),
                "status": "resolved",
                "resolution_notes": resolution_notes,
                "event_type": "status_change"
            }

            # Include full event data if provided
            if event_data:
                # Extract important fields from the security event
                action_data.update({
                    "rule_id": event_data.get("rule_id"),
                    "rule_name": event_data.get("title", "Unknown Rule"),
                    "severity": event_data.get("severity"),
                    "confidence": 1.0,  # Default confidence for status changes
                    "attack_techniques": self._parse_mitre_techniques(event_data.get("mitre_techniques", "[]")),
                    "matched_fields": self._parse_enrichment_data(event_data.get("enrichment_data", "{}")),
                })

            event = BaseEvent(
                event_type=EVENT_SECURITY_DETECTION_RESOLVED,
                customer_id=customer_id,
                data=action_data,
                metadata=EventMetadata(
                    source_service="security-service",
                    priority=EventPriority.HIGH,
                    correlation_id=correlation_id,
                    trace_id=trace_id
                )
            )

            success = await self.publisher_manager.publish(event)

            if success:
                self.logger.info(
                    "Security detection resolved event published",
                    customer_id=customer_id,
                    detection_id=detection_id,
                    resolved_by=resolved_by
                )
            else:
                self.logger.warning(
                    "Failed to publish security detection resolved event",
                    customer_id=customer_id,
                    detection_id=detection_id
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing security detection resolved event",
                customer_id=customer_id,
                detection_id=detection_id,
                error=str(e)
            )
            return False

    async def publish_security_detection_false_positive(
        self,
        customer_id: str,
        detection_id: str,
        marked_by: str,
        notes: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when a security detection is marked as false positive
        """
        try:
            # Combine action data with full event details
            action_data = {
                "detection_id": detection_id,
                "marked_by": marked_by,
                "marked_at": datetime.utcnow().isoformat(),
                "status": "false_positive",
                "notes": notes,
                "event_type": "status_change"
            }

            # Include full event data if provided
            if event_data:
                # Extract important fields from the security event
                action_data.update({
                    "rule_id": event_data.get("rule_id"),
                    "rule_name": event_data.get("title", "Unknown Rule"),
                    "severity": event_data.get("severity"),
                    "confidence": 1.0,  # Default confidence for status changes
                    "attack_techniques": self._parse_mitre_techniques(event_data.get("mitre_techniques", "[]")),
                    "matched_fields": self._parse_enrichment_data(event_data.get("enrichment_data", "{}")),
                })

            final_event_data = action_data

            # Use resolved event type for false positives (same topic)
            event = BaseEvent(
                event_type=EVENT_SECURITY_DETECTION_FALSE_POSITIVE,
                customer_id=customer_id,
                data=final_event_data,
                metadata=EventMetadata(
                    source_service="security-service",
                    priority=EventPriority.MEDIUM,
                    correlation_id=correlation_id,
                    trace_id=trace_id
                )
            )

            success = await self.publisher_manager.publish(event)

            if success:
                self.logger.info(
                    "Security detection false positive event published",
                    customer_id=customer_id,
                    detection_id=detection_id,
                    marked_by=marked_by
                )
            else:
                self.logger.warning(
                    "Failed to publish security detection false positive event",
                    customer_id=customer_id,
                    detection_id=detection_id
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing security detection false positive event",
                customer_id=customer_id,
                detection_id=detection_id,
                error=str(e)
            )
            return False

    async def publish_security_detection_investigating(
        self,
        customer_id: str,
        detection_id: str,
        assigned_to: str,
        investigation_notes: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when a security detection is being investigated
        """
        try:
            # Combine action data with full event details
            action_data = {
                "detection_id": detection_id,
                "assigned_to": assigned_to,
                "investigation_started_at": datetime.utcnow().isoformat(),
                "status": "investigating",
                "investigation_notes": investigation_notes,
                "event_type": "status_change"
            }

            # Include full event data if provided
            if event_data:
                # Extract important fields from the security event
                action_data.update({
                    "rule_id": event_data.get("rule_id"),
                    "rule_name": event_data.get("title", "Unknown Rule"),
                    "severity": event_data.get("severity"),
                    "confidence": 1.0,  # Default confidence for status changes
                    "attack_techniques": self._parse_mitre_techniques(event_data.get("mitre_techniques", "[]")),
                    "matched_fields": self._parse_enrichment_data(event_data.get("enrichment_data", "{}")),
                })

            final_event_data = action_data

            event = BaseEvent(
                event_type=EVENT_SECURITY_DETECTION_ACKNOWLEDGED,  # Reuse acknowledged for investigating
                customer_id=customer_id,
                data=final_event_data,
                metadata=EventMetadata(
                    source_service="security-service",
                    priority=EventPriority.HIGH,
                    correlation_id=correlation_id,
                    trace_id=trace_id
                )
            )

            success = await self.publisher_manager.publish(event)

            if success:
                self.logger.info(
                    "Security detection investigating event published",
                    customer_id=customer_id,
                    detection_id=detection_id,
                    assigned_to=assigned_to
                )
            else:
                self.logger.warning(
                    "Failed to publish security detection investigating event",
                    customer_id=customer_id,
                    detection_id=detection_id
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing security detection investigating event",
                customer_id=customer_id,
                detection_id=detection_id,
                error=str(e)
            )
            return False

    def _parse_mitre_techniques(self, mitre_techniques_str: str) -> List[str]:
        """Parse MITRE techniques from string format to list"""
        try:
            import json
            if isinstance(mitre_techniques_str, str):
                # Handle string representation of list like "['T1110']"
                if mitre_techniques_str.startswith('[') and mitre_techniques_str.endswith(']'):
                    return json.loads(mitre_techniques_str.replace("'", '"'))
                # Handle comma-separated string
                elif ',' in mitre_techniques_str:
                    return [t.strip() for t in mitre_techniques_str.split(',')]
                # Handle single technique
                elif mitre_techniques_str:
                    return [mitre_techniques_str]
            elif isinstance(mitre_techniques_str, list):
                return mitre_techniques_str
            return []
        except Exception:
            return []

    def _parse_enrichment_data(self, enrichment_data_str: str) -> Dict[str, Any]:
        """Parse enrichment data from string format to dict"""
        try:
            import json
            if isinstance(enrichment_data_str, str) and enrichment_data_str:
                return json.loads(enrichment_data_str)
            elif isinstance(enrichment_data_str, dict):
                return enrichment_data_str
            return {}
        except Exception:
            return {}
