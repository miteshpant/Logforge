"""
Observability Event Publisher
Specialized publisher for OpenTelemetry traces, metrics, and APM events
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
import structlog

from ..base import BaseEvent, EventPriority, EventMetadata
from ..constants import (
    EVENT_TRACES_BATCH_INGESTED,
    EVENT_METRICS_BATCH_INGESTED,
    EVENT_SERVICE_TOPOLOGY_UPDATED
)

logger = structlog.get_logger(__name__)


class ObservabilityEventPublisher:
    """Publisher for observability lifecycle events"""

    def __init__(self, publisher_manager):
        self.publisher_manager = publisher_manager
        self.logger = logger.bind(component="observability_event_publisher")

    async def publish_traces_batch_ingested(
        self,
        customer_id: str,
        batch_info: Dict[str, Any],
        spans_data: List[Any],  # Can be Pydantic objects or dicts
        processing_time_ms: float,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when a batch of traces is ingested

        Args:
            customer_id: Customer identifier
            batch_info: Information about the ingested batch
            spans_data: List of span data for processing (Pydantic objects or dicts)
            processing_time_ms: Time taken to process the batch
            correlation_id: Request correlation ID
            trace_id: Distributed tracing ID
        """
        try:
            # Convert Pydantic objects to dictionaries before publishing
            converted_spans = []
            for span in spans_data:
                if hasattr(span, 'model_dump'):
                    # Pydantic v2 model
                    span_dict = span.model_dump()
                elif hasattr(span, 'dict'):
                    # Pydantic v1 model
                    span_dict = span.dict()
                elif isinstance(span, dict):
                    # Already a dict
                    span_dict = span
                else:
                    # Convert manually
                    span_dict = {}
                    if hasattr(span, '__dict__'):
                        span_dict.update(span.__dict__)
                    
                    # Extract known fields
                    known_fields = ['trace_id', 'span_id', 'parent_span_id', 'operation_name', 
                                  'service_name', 'start_time', 'end_time', 'duration_ms', 
                                  'kind', 'status', 'status_message', 'attributes', 'events', 
                                  'links', 'resource']
                    
                    for field in known_fields:
                        if hasattr(span, field):
                            try:
                                value = getattr(span, field)
                                # Convert Pydantic enums to string
                                if hasattr(value, 'value'):
                                    value = value.value
                                # Convert datetime to ISO string  
                                elif hasattr(value, 'isoformat'):
                                    value = value.isoformat()
                                span_dict[field] = value
                            except Exception:
                                pass
                
                converted_spans.append(span_dict)
            
            self.logger.info(f"Converted {len(spans_data)} spans to dictionaries for event publishing")

            event_data = {
                "batch_id": batch_info.get("batch_id"),
                "span_count": len(spans_data),
                "processing_time_ms": processing_time_ms,
                "bytes_processed": batch_info.get("bytes_processed", 0),
                "ingestion_endpoint": "/v1/observability/traces/ingest",
                "timestamp": batch_info.get("timestamp", datetime.utcnow().isoformat()),
                "success_count": batch_info.get("success_count", len(spans_data)),
                "error_count": batch_info.get("error_count", 0),
                "spans": converted_spans,  # Use converted dictionaries
                "source_format": "otlp"  # OpenTelemetry Protocol
            }

            metadata = EventMetadata(
                source_service="observability-ingestion-service",
                correlation_id=correlation_id,
                trace_id=trace_id,
                priority=EventPriority.HIGH  # Observability data is high priority
            )

            event = BaseEvent(
                event_type=EVENT_TRACES_BATCH_INGESTED,
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
                    "Traces batch ingestion event published",
                    customer_id=customer_id,
                    batch_id=batch_info.get("batch_id"),
                    span_count=len(spans_data),
                    processing_time_ms=processing_time_ms,
                    successful_publishers=success_count,
                    total_publishers=total_publishers,
                    publisher_results=results
                )
            else:
                self.logger.error(
                    "Failed to publish traces batch ingestion event to any publisher",
                    customer_id=customer_id,
                    batch_id=batch_info.get("batch_id"),
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing traces batch ingestion event",
                customer_id=customer_id,
                error=str(e),
                exc_info=True
            )
            return False

    async def publish_metrics_batch_ingested(
        self,
        customer_id: str,
        batch_info: Dict[str, Any],
        metrics_data: List[Dict[str, Any]],
        processing_time_ms: float,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when a batch of metrics is ingested

        Args:
            customer_id: Customer identifier
            batch_info: Information about the ingested batch
            metrics_data: List of metric data for processing
            processing_time_ms: Time taken to process the batch
            correlation_id: Request correlation ID
            trace_id: Distributed tracing ID
        """
        try:
            event_data = {
                "batch_id": batch_info.get("batch_id"),
                "metric_count": len(metrics_data),
                "processing_time_ms": processing_time_ms,
                "bytes_processed": batch_info.get("bytes_processed", 0),
                "ingestion_endpoint": "/v1/observability/metrics/ingest",
                "timestamp": batch_info.get("timestamp", datetime.utcnow().isoformat()),
                "success_count": batch_info.get("success_count", len(metrics_data)),
                "error_count": batch_info.get("error_count", 0),
                "metrics": metrics_data,  # Include actual metric data for event processing
                "source_format": "otlp"  # OpenTelemetry Protocol
            }

            metadata = EventMetadata(
                source_service="observability-ingestion-service",
                correlation_id=correlation_id,
                trace_id=trace_id,
                priority=EventPriority.HIGH
            )

            event = BaseEvent(
                event_type=EVENT_METRICS_BATCH_INGESTED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            
            success_count = sum(1 for result in results.values() if result)
            total_publishers = len(results)
            success = success_count > 0

            if success:
                self.logger.info(
                    "Metrics batch ingestion event published",
                    customer_id=customer_id,
                    batch_id=batch_info.get("batch_id"),
                    metric_count=len(metrics_data),
                    processing_time_ms=processing_time_ms,
                    successful_publishers=success_count,
                    total_publishers=total_publishers,
                    publisher_results=results
                )
            else:
                self.logger.error(
                    "Failed to publish metrics batch ingestion event to any publisher",
                    customer_id=customer_id,
                    batch_id=batch_info.get("batch_id"),
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing metrics batch ingestion event",
                customer_id=customer_id,
                error=str(e),
                exc_info=True
            )
            return False

    async def publish_service_topology_updated(
        self,
        customer_id: str,
        service_info: Dict[str, Any],
        update_reason: str = "trace_analysis",
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when service topology is updated

        Args:
            customer_id: Customer identifier
            service_info: Information about the service update
            update_reason: Reason for the topology update
            correlation_id: Request correlation ID
        """
        try:
            event_data = {
                "service_name": service_info.get("service_name"),
                "service_type": service_info.get("service_type"),
                "service_version": service_info.get("service_version"),
                "deployment_environment": service_info.get("deployment_environment"),
                "update_reason": update_reason,
                "dependencies": service_info.get("dependencies", []),
                "endpoints": service_info.get("endpoints", []),
                "health_status": service_info.get("health_status"),
                "updated_at": datetime.utcnow().isoformat()
            }

            metadata = EventMetadata(
                source_service="observability-service",
                correlation_id=correlation_id,
                priority=EventPriority.MEDIUM
            )

            event = BaseEvent(
                event_type=EVENT_SERVICE_TOPOLOGY_UPDATED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = any(results.values())

            if success:
                self.logger.info(
                    "Service topology update event published",
                    customer_id=customer_id,
                    service_name=service_info.get("service_name"),
                    update_reason=update_reason,
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing service topology update event",
                customer_id=customer_id,
                error=str(e)
            )
            return False


# Convenience factory for creating observability events
class ObservabilityEventFactory:
    """Factory for creating standardized observability events"""

    @staticmethod
    def create_traces_batch_ingestion_event(
        customer_id: str,
        batch_info: Dict[str, Any],
        spans_data: List[Dict[str, Any]],
        processing_time_ms: float,
        **kwargs
    ) -> BaseEvent:
        """Create traces batch ingestion event"""
        event_data = {
            "batch_id": batch_info.get("batch_id"),
            "span_count": len(spans_data),
            "processing_time_ms": processing_time_ms,
            "bytes_processed": batch_info.get("bytes_processed", 0),
            "success_count": batch_info.get("success_count", len(spans_data)),
            "error_count": batch_info.get("error_count", 0),
            "spans": spans_data,
            "source_format": "otlp",
            **kwargs
        }

        return BaseEvent(
            event_type=EVENT_TRACES_BATCH_INGESTED,
            customer_id=customer_id,
            data=event_data,
            metadata=EventMetadata(
                source_service="observability-ingestion-service",
                priority=EventPriority.HIGH,
                **{k: v for k, v in kwargs.items() if k in ['correlation_id', 'trace_id']}
            )
        )

    @staticmethod
    def create_metrics_batch_ingestion_event(
        customer_id: str,
        batch_info: Dict[str, Any],
        metrics_data: List[Dict[str, Any]],
        processing_time_ms: float,
        **kwargs
    ) -> BaseEvent:
        """Create metrics batch ingestion event"""
        event_data = {
            "batch_id": batch_info.get("batch_id"),
            "metric_count": len(metrics_data),
            "processing_time_ms": processing_time_ms,
            "bytes_processed": batch_info.get("bytes_processed", 0),
            "success_count": batch_info.get("success_count", len(metrics_data)),
            "error_count": batch_info.get("error_count", 0),
            "metrics": metrics_data,
            "source_format": "otlp",
            **kwargs
        }

        return BaseEvent(
            event_type=EVENT_METRICS_BATCH_INGESTED,
            customer_id=customer_id,
            data=event_data,
            metadata=EventMetadata(
                source_service="observability-ingestion-service",
                priority=EventPriority.HIGH,
                **{k: v for k, v in kwargs.items() if k in ['correlation_id', 'trace_id']}
            )
        )