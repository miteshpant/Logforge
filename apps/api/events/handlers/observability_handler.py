"""
Observability Event Handler - Handles OpenTelemetry traces, metrics, and APM events
"""

from typing import List
import structlog
import uuid
from datetime import datetime, timezone

from .base import EventHandler
from ..base import BaseEvent
from ..constants import (
    EVENT_TRACES_BATCH_INGESTED,
    EVENT_METRICS_BATCH_INGESTED,
    EVENT_SERVICE_TOPOLOGY_UPDATED
)

logger = structlog.get_logger(__name__)


class ObservabilityEventHandler(EventHandler):
    """Handler for observability lifecycle events"""

    async def handle(self, event: BaseEvent) -> bool:
        """Handle observability events"""
        logger.info(
            "Processing observability event",
            event_id=event.metadata.event_id,
            customer_id=event.customer_id,
            event_type=event.event_type
        )

        # Handle different types of observability events
        if event.event_type == EVENT_TRACES_BATCH_INGESTED:
            return await self._handle_traces_batch_ingested(event)
        elif event.event_type == EVENT_METRICS_BATCH_INGESTED:
            return await self._handle_metrics_batch_ingested(event)
        elif event.event_type == EVENT_SERVICE_TOPOLOGY_UPDATED:
            return await self._handle_service_topology_updated(event)
        else:
            # For now, just log other event types
            logger.info(f"Observability event type {event.event_type} received but not yet implemented")
            return True

    async def _handle_traces_batch_ingested(self, event: BaseEvent) -> bool:
        """Handle traces.batch.ingested event with field normalization and ObservabilityService"""
        try:
            # Import here to avoid circular dependencies
            from services.observability_service import ObservabilityService
            from services.simple_otel_mapper import normalize_otel_service_simple

            start_time = datetime.now(timezone.utc)
            customer_id = event.customer_id
            event_data = event.data

            # Extract span data from event
            spans_data = event_data.get("spans", [])
            if not spans_data:
                logger.warning("No spans data found in trace ingestion event", customer_id=customer_id)
                return True

            logger.info(
                "Processing traces batch ingestion event with field normalization",
                customer_id=customer_id,
                span_count=len(spans_data),
                batch_id=event_data.get("batch_id")
            )

            # Initialize observability service
            observability_service = ObservabilityService()

            # Process each span with field normalization
            ingested_spans = []
            errors = []
            normalization_errors = []

            for span_data in spans_data:
                try:
                    # span_data should already be a dict from the publisher conversion
                    if not isinstance(span_data, dict):
                        logger.error(f"Expected dict from publisher, got {type(span_data)}: {span_data}")
                        continue

                    if not span_data:
                        logger.error("Received empty span dict from publisher")
                        continue

                    logger.info(f"Processing span dict with {len(span_data)} fields: {list(span_data.keys())}")
                    logger.info(f"Custom fields check - namespace: {span_data.get('namespace')}, cluster: {span_data.get('cluster')}, stage: {span_data.get('stage')}")

                    # Step 1: Apply field normalization using otel_field_mapping.yml
                    normalized_span = normalize_otel_service_simple(span_data)
                    logger.debug(
                        "Applied OTel field normalization",
                        customer_id=customer_id,
                        original_span_id=span_data.get('span_id') or span_data.get('spanId') or span_data.get('id'),
                        normalized_span_id=normalized_span.get('span_id'),
                        original_service=span_data.get('service_name') or span_data.get('serviceName') or span_data.get('service', {}).get('name'),
                        normalized_service=normalized_span.get('service_name')
                    )

                    # Step 2: Process the normalized span (includes traces_mt storage and service topology update)
                    span_id = await observability_service.ingest_trace_span(normalized_span, customer_id)
                    ingested_spans.append(span_id)

                except Exception as span_error:
                    error_msg = f"Failed to ingest span {span_data.get('span_id', 'unknown')}: {span_error}"
                    errors.append(error_msg)
                    logger.error(
                        "Span ingestion failed",
                        customer_id=customer_id,
                        span_id=span_data.get('span_id') or span_data.get('spanId') or span_data.get('id'),
                        error=str(span_error)
                    )

            # Calculate processing time
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            # Log results
            success_count = len(ingested_spans)
            error_count = len(errors)

            logger.info(
                "Traces batch ingestion completed",
                customer_id=customer_id,
                batch_id=event_data.get("batch_id"),
                total_spans=len(spans_data),
                successful_spans=success_count,
                failed_spans=error_count,
                processing_time_ms=processing_time
            )

            # Consider it successful if at least some spans were processed
            return success_count > 0 or len(spans_data) == 0

        except Exception as e:
            logger.error(
                "Failed to process traces batch ingestion event",
                customer_id=event.customer_id,
                event_id=event.metadata.event_id,
                error=str(e),
                exc_info=True
            )
            return False

    async def _handle_metrics_batch_ingested(self, event: BaseEvent) -> bool:
        """Handle metrics.batch.ingested event with field normalization and ObservabilityService"""
        try:
            # Import here to avoid circular dependencies
            from services.observability_service import ObservabilityService
            from services.simple_otel_mapper import normalize_otel_service_simple

            start_time = datetime.now(timezone.utc)
            customer_id = event.customer_id
            event_data = event.data

            # Extract metrics data from event
            metrics_data = event_data.get("metrics", [])
            if not metrics_data:
                logger.warning("No metrics data found in metrics ingestion event", customer_id=customer_id)
                return True

            logger.info(
                "Processing metrics batch ingestion event with field normalization",
                customer_id=customer_id,
                metric_count=len(metrics_data),
                batch_id=event_data.get("batch_id")
            )

            # Initialize observability service
            observability_service = ObservabilityService()

            # Process each metric with field normalization
            ingested_metrics = []
            errors = []

            for metric_data in metrics_data:
                try:
                    # metric_data should already be a dict from the publisher conversion
                    if not isinstance(metric_data, dict):
                        logger.error(f"Expected dict from publisher, got {type(metric_data)}: {metric_data}")
                        continue

                    if not metric_data:
                        logger.error("Received empty metric dict from publisher")
                        continue

                    # Step 1: Apply field normalization using otel_field_mapping.yml
                    normalized_metric = normalize_otel_service_simple(metric_data)
                    logger.info(f"normalized_metric {normalized_metric}")
                    logger.debug(
                        "Applied OTel field normalization for metric",
                        customer_id=customer_id,
                        original_metric_name=metric_data.get('metric_name') or metric_data.get('metricName') or metric_data.get('name'),
                        normalized_metric_name=normalized_metric.get('metric_name'),
                        original_service=metric_data.get('service_name') or metric_data.get('serviceName') or metric_data.get('service', {}).get('name'),
                        normalized_service=normalized_metric.get('service_name')
                    )

                    # Step 2: Process the normalized metric (stores to metrics_mt table)
                    metric_id = await observability_service.ingest_metric(normalized_metric, customer_id)
                    ingested_metrics.append(metric_id)

                except Exception as metric_error:
                    error_msg = f"Failed to ingest metric {metric_data.get('name', 'unknown')}: {metric_error}"
                    errors.append(error_msg)
                    logger.error(
                        "Metric ingestion failed",
                        customer_id=customer_id,
                        metric_name=metric_data.get('name') or metric_data.get('metric_name') or metric_data.get('metricName'),
                        error=str(metric_error)
                    )

            # Calculate processing time
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            # Log results
            success_count = len(ingested_metrics)
            error_count = len(errors)

            logger.info(
                "Metrics batch ingestion completed",
                customer_id=customer_id,
                batch_id=event_data.get("batch_id"),
                total_metrics=len(metrics_data),
                successful_metrics=success_count,
                failed_metrics=error_count,
                processing_time_ms=processing_time
            )

            # Consider it successful if at least some metrics were processed
            return success_count > 0 or len(metrics_data) == 0

        except Exception as e:
            logger.error(
                "Failed to process metrics batch ingestion event",
                customer_id=event.customer_id,
                event_id=event.metadata.event_id,
                error=str(e),
                exc_info=True
            )
            return False

    async def _handle_service_topology_updated(self, event: BaseEvent) -> bool:
        """Handle service.topology.updated event for downstream processing"""
        try:
            customer_id = event.customer_id
            event_data = event.data

            logger.info(
                "Processing service topology update event",
                customer_id=customer_id,
                service_name=event_data.get("service_name"),
                service_type=event_data.get("service_type"),
                update_reason=event_data.get("update_reason")
            )

            # This event can be used by other services that need to know about topology changes
            # For example: APM dashboards, dependency analysis, alert rules, etc.

            # For now, just log the event - future integrations can subscribe to this
            logger.debug(
                "Service topology updated",
                customer_id=customer_id,
                service_data=event_data
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to process service topology update event",
                customer_id=event.customer_id,
                event_id=event.metadata.event_id,
                error=str(e),
                exc_info=True
            )
            return False

    def get_supported_event_types(self) -> List[str]:
        """Return list of event types this handler supports"""
        return [
            EVENT_TRACES_BATCH_INGESTED,
            EVENT_METRICS_BATCH_INGESTED,
            EVENT_SERVICE_TOPOLOGY_UPDATED
        ]

    def get_handler_name(self) -> str:
        """Return handler name for identification"""
        return "observability_event_handler"
