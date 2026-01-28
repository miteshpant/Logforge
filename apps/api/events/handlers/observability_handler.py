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
        """Handle traces.batch.ingested event with field normalization and batch aggregation"""
        try:
            # Import here to avoid circular dependencies
            from services.observability_service import ObservabilityService
            from services.simple_otel_mapper import normalize_otel_service_simple
            from collections import defaultdict

            start_time = datetime.now(timezone.utc)
            customer_id = event.customer_id
            event_data = event.data

            # Extract span data from event
            # The publisher sends "traces" (grouped trace objects with nested "spans")
            # We need to flatten all spans from all traces for processing
            spans_data = []
            traces_data = event_data.get("traces", [])

            if traces_data:
                # New format: traces array with nested spans
                for trace in traces_data:
                    trace_spans = trace.get("spans", [])
                    spans_data.extend(trace_spans)
                logger.info(
                    "Extracted spans from traces structure",
                    customer_id=customer_id,
                    trace_count=len(traces_data),
                    total_span_count=len(spans_data)
                )
            else:
                # Fallback: legacy format with direct spans array
                spans_data = event_data.get("spans", [])

            if not spans_data:
                logger.warning("No spans data found in trace ingestion event", customer_id=customer_id)
                return True

            logger.info(
                "Processing traces batch with aggregated service metrics",
                customer_id=customer_id,
                span_count=len(spans_data),
                batch_id=event_data.get("batch_id")
            )

            # Initialize observability service
            observability_service = ObservabilityService()

            # Process each span with field normalization
            ingested_spans = []
            errors = []

            # Build span index for dependency resolution within batch
            span_index = {}  # {span_id: {service_name, operation_name}}

            # **NEW: Aggregate service metrics across the batch**
            service_metrics = defaultdict(lambda: {
                'request_count': 0,
                'error_count': 0,
                'total_duration_ms': 0,
                'service_name': '',
                'service_instance_id': '',
                'customer_id': customer_id,
                'last_seen': datetime.now(timezone.utc),
                'resource_attributes': {},
                # Infrastructure fields from normalization
                'namespace': None,
                'cluster': None,
                'host': None,
                'container_id': None,
                'deployment_environment': None,
                'service_version': None,
                # Track dependencies (set to avoid duplicates)
                'dependencies': set(),
                'endpoints': set()
            })

            for span_data in spans_data:
                try:
                    # span_data should already be a dict from the publisher conversion
                    if not isinstance(span_data, dict):
                        logger.error(f"Expected dict from publisher, got {type(span_data)}: {span_data}")
                        continue

                    if not span_data:
                        logger.error("Received empty span dict from publisher")
                        continue

                    logger.debug(f"Processing span dict with {len(span_data)} fields: {list(span_data.keys())}")

                    # Step 1: Apply field normalization using otel_field_mapping.yml
                    normalized_span = normalize_otel_service_simple(span_data)
                    logger.debug(
                        "Applied OTel field normalization",
                        customer_id=customer_id,
                        normalized_span_id=normalized_span.get('span_id'),
                        normalized_service=normalized_span.get('service_name')
                    )

                    # Step 2: Save span to traces_mt (WITHOUT updating service topology yet)
                    span_id = await observability_service.ingest_trace_span(normalized_span, customer_id)
                    ingested_spans.append(span_id)

                    # **NEW: Aggregate metrics for this service**
                    service_name = normalized_span.get('service_name', 'unknown')
                    resource = normalized_span.get('resource', {})
                    # Use normalized service_instance_id from top level (not from resource)
                    service_instance_id = normalized_span.get('service_instance_id', '')
                    operation_name = normalized_span.get('operation_name', '')
                    current_span_id = normalized_span.get('span_id')
                    parent_span_id = normalized_span.get('parent_span_id')

                    # Build span index for dependency resolution
                    if current_span_id:
                        span_index[current_span_id] = {
                            'service_name': service_name,
                            'operation_name': operation_name
                        }

                    service_key = (service_name, service_instance_id)

                    metrics = service_metrics[service_key]
                    metrics['service_name'] = service_name
                    metrics['service_instance_id'] = service_instance_id
                    metrics['request_count'] += 1
                    metrics['error_count'] += 1 if normalized_span.get('status') == 'error' else 0
                    # Handle None values properly - .get() returns None if key exists with None value
                    duration_ms = normalized_span.get('duration_ms') or 0
                    metrics['total_duration_ms'] += duration_ms
                    metrics['resource_attributes'] = resource  # Keep latest resource attributes

                    # Track endpoints (operation names)
                    if operation_name:
                        metrics['endpoints'].add(operation_name)

                    # Track dependencies from parent-child relationships
                    if parent_span_id and parent_span_id in span_index:
                        parent_service = span_index[parent_span_id]['service_name']
                        if parent_service != service_name:  # Don't add self as dependency
                            metrics['dependencies'].add(parent_service)

                    # **NEW: Capture normalized infrastructure fields**
                    metrics['namespace'] = normalized_span.get('namespace', metrics['namespace'])
                    metrics['cluster'] = normalized_span.get('cluster', metrics['cluster'])
                    metrics['host'] = normalized_span.get('host', metrics['host'])
                    metrics['container_id'] = normalized_span.get('container_id', metrics['container_id'])
                    metrics['deployment_environment'] = normalized_span.get('deployment_environment', metrics['deployment_environment'])
                    metrics['service_version'] = normalized_span.get('service_version', metrics['service_version'])

                    # Update last_seen to latest timestamp
                    span_start_time = normalized_span.get('start_time')
                    if span_start_time:
                        try:
                            span_timestamp = datetime.fromisoformat(span_start_time.replace('Z', '+00:00'))
                            if span_timestamp > metrics['last_seen']:
                                metrics['last_seen'] = span_timestamp
                        except:
                            pass

                except Exception as span_error:
                    error_msg = f"Failed to ingest span {span_data.get('span_id', 'unknown')}: {span_error}"
                    errors.append(error_msg)
                    logger.error(
                        "Span ingestion failed",
                        customer_id=customer_id,
                        span_id=span_data.get('span_id') or span_data.get('spanId') or span_data.get('id'),
                        error=str(span_error)
                    )

            # **NEW: Update service_topology ONCE per service (not per span)**
            services_updated = 0
            for service_key, metrics in service_metrics.items():
                try:
                    avg_response_time = (
                        metrics['total_duration_ms'] / metrics['request_count']
                        if metrics['request_count'] > 0 else 0
                    )

                    await observability_service.update_service_metrics_aggregated(
                        customer_id=customer_id,
                        service_name=metrics['service_name'],
                        service_instance_id=metrics['service_instance_id'],
                        request_count_increment=metrics['request_count'],
                        error_count_increment=metrics['error_count'],
                        avg_response_time_ms=avg_response_time,
                        last_seen=metrics['last_seen'],
                        resource_attributes=metrics['resource_attributes'],
                        # Pass normalized infrastructure fields
                        namespace=metrics['namespace'],
                        cluster=metrics['cluster'],
                        host=metrics['host'],
                        container_id=metrics['container_id'],
                        deployment_environment=metrics['deployment_environment'],
                        service_version=metrics['service_version'],
                        # Pass dependencies and endpoints
                        dependencies=list(metrics['dependencies']),
                        endpoints=list(metrics['endpoints'])
                    )

                    services_updated += 1

                except Exception as e:
                    logger.error(f"Failed to update service metrics for {service_key}: {e}")

            # Calculate processing time
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            # Log results
            success_count = len(ingested_spans)
            error_count = len(errors)

            logger.info(
                "Traces batch ingestion completed with aggregated metrics",
                customer_id=customer_id,
                batch_id=event_data.get("batch_id"),
                total_spans=len(spans_data),
                successful_spans=success_count,
                failed_spans=error_count,
                services_updated=services_updated,
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
            from services.metric_normalizer import normalize_metric_data

            start_time = datetime.now(timezone.utc)
            customer_id = event.customer_id
            event_data = event.data

            # Extract metrics data from event
            metrics_data = event_data.get("metrics", [])
            if not metrics_data:
                logger.warning("No metrics data found in metrics ingestion event", customer_id=customer_id)
                return True

            logger.info(
                "Processing metrics batch ingestion event with field and metric name normalization",
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
                    # (normalizes field names like metricName -> metric_name)
                    normalized_metric = normalize_otel_service_simple(metric_data)

                    # Step 2: Apply metric NAME normalization
                    # (normalizes metric values like "latency" -> "response_time")
                    normalized_metric = normalize_metric_data(normalized_metric)

                    logger.debug(
                        "Applied field and metric name normalization",
                        customer_id=customer_id,
                        original_metric_name=metric_data.get('metric_name') or metric_data.get('metricName') or metric_data.get('name'),
                        normalized_metric_name=normalized_metric.get('metric_name'),
                        original_service=metric_data.get('service_name') or metric_data.get('serviceName') or metric_data.get('service', {}).get('name'),
                        normalized_service=normalized_metric.get('service_name')
                    )

                    # Step 3: Process the normalized metric (stores to metrics_mt table)
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
