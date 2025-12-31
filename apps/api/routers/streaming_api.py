"""
Streaming API - Server-Sent Events for Real-Time Data
Real-time streaming endpoints for metrics, traces, security events, alerts, usage, and AI insights
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Header, Query
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any, List
import structlog
import json
import asyncio
from datetime import datetime, timedelta
import random

from services.observability_service import ObservabilityService
from services.security_service import SecurityService
from services.alert_service import AlertService
from services.usage_service import UsageService
from services.ai_service import AIService
from services.streaming_config_service import get_streaming_config_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/stream", tags=["streaming"])


def format_sse_message(event_type: str, data: Any, event_id: Optional[str] = None) -> str:
    """Format data as Server-Sent Events message"""
    message = ""
    if event_id:
        message += f"id: {event_id}\n"
    message += f"event: {event_type}\n"
    message += f"data: {json.dumps(data)}\n\n"
    return message


@router.get("/metrics")
async def stream_metrics(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Stream real-time metrics data - Pure event-driven, no polling"""
    try:
        from events.subscribers import KafkaEventSubscriber
        from events.constants import EVENT_METRICS_BATCH_INGESTED, EVENT_METRIC_PROCESSED, TOPIC_SYSTEM_EVENTS

        # Metrics event types we want to stream to UI
        metrics_events = [
            EVENT_METRICS_BATCH_INGESTED,
            EVENT_METRIC_PROCESSED
        ]

        # Create a queue to receive events from the custom handler
        event_queue = asyncio.Queue()

        # Custom handler class to capture metrics events for this streaming session
        class StreamingMetricsHandler:
            """Custom handler to capture metrics events for streaming with config-based filtering"""

            def __init__(self, target_customer_id: str, event_queue: asyncio.Queue):
                self.target_customer_id = target_customer_id
                self.event_queue = event_queue
                self.streaming_service = get_streaming_config_service()
                self.rate_limiter = {}

            async def handle(self, event) -> bool:
                """Handle events and put relevant ones in the queue with config-based filtering"""
                try:
                    # Only handle events for our target customer and metrics event types
                    if (hasattr(event, 'customer_id') and
                        event.customer_id == self.target_customer_id and
                        hasattr(event, 'event_type') and
                        event.event_type in metrics_events):

                        # Apply streaming configuration filters
                        if await self._should_stream_event(event):
                            # Put event in queue for streaming
                            await self.event_queue.put(event)
                            logger.debug(f"Metrics event queued for streaming: {event.event_type}")
                        else:
                            logger.debug(f"Metrics event filtered out: {event.event_type}")
                        return True

                    return True

                except Exception as e:
                    logger.error(f"Error in metrics streaming handler: {e}")
                    return False

            async def _should_stream_event(self, event) -> bool:
                """Apply streaming configuration filters to determine if event should be streamed"""
                try:
                    # Get streaming config for this customer
                    config = await self.streaming_service.get_streaming_config(
                        self.target_customer_id,
                        "metrics.batch.ingested"
                    )
                    # If disabled, don't stream
                    if not config.get("enabled", True):
                        return False

                    # Apply sample rate (0.0 = 0%, 1.0 = 100%)
                    sample_rate = config.get("sample_rate", 1.0)
                    random_rate = random.random()
                    logger.info(f" random rate is {random_rate}")
                    if random_rate > sample_rate:
                        return False

                    # Check rate limiting
                    max_events_per_minute = config.get("max_events_per_minute", 100)
                    logger.info(f" max_events_per_minute : {max_events_per_minute}")
                    if not self._check_rate_limit(max_events_per_minute):
                        return False
                    # Check minimum metrics count
                    min_metrics_count = config.get("min_metrics_count", 1)
                    metrics_count = event.data.get("metric_count", 0)  # Fixed: use "metric_count" not "metrics_count"
                    if metrics_count < min_metrics_count:
                        return False
                    metrics = event.data.get("metrics", [])
                    service_name = ""
                    if metrics:
                        service_name = metrics[0].get("service_name", "")
                    # Exclude services
                    exclude_services = config.get("exclude_services", [])
                    if service_name in exclude_services:
                        return False

                    # Include services (if specified, only allow these)
                    include_services = config.get("include_services", [])
                    if include_services and service_name not in include_services:
                        return False

                    # Check priority metrics (always stream if present)
                    priority_metrics = config.get("priority_metrics", [])

                    for metric in metrics:
                        if metric.get("metric_name") in priority_metrics:
                            return True

                    # Check error-only filtering
                    if config.get("include_errors_only", False):
                        for metric in metrics:
                            if metric.get("status") == "error" or metric.get("error_count", 0) > 0:
                                return True
                        return False
                    logger.info("reching here ")
                    return True

                except Exception as e:
                    logger.error(f"Error applying streaming filters: {e}")
                    # Default to streaming on error to avoid losing data
                    return True

            def _check_rate_limit(self, max_events_per_minute: int) -> bool:
                """Check if we're within the rate limit for this customer"""
                current_minute = int(datetime.now().timestamp() / 60)
                key = f"{self.target_customer_id}_{current_minute}"
                logger.info(f"key is : {key}")
                if key not in self.rate_limiter:
                    self.rate_limiter[key] = 0
                logger.info( f"self.rate_limiter : {self.rate_limiter}")
                # Clean old entries
                old_keys = [k for k in self.rate_limiter.keys() if int(k.split('_')[-1]) < current_minute - 1]
                for old_key in old_keys:
                    del self.rate_limiter[old_key]

                if self.rate_limiter[key] >= max_events_per_minute:
                    return False

                self.rate_limiter[key] += 1
                logger.info(" I am returning true")
                return True

            def get_handler_name(self) -> str:
                return f"streaming_metrics_handler_{self.target_customer_id}"

            def get_supported_event_types(self) -> List[str]:
                return metrics_events

        async def generate_real_time_metrics():
            """Generate real-time metrics events as they occur"""
            subscriber = None
            try:
                from events.subscribers import SubscriberConfig

                # Create subscriber config for metrics events
                config = SubscriberConfig(
                    name=f"streaming_metrics_{customer_id}",
                    consumer_group=f"streaming_metrics_{customer_id}",
                    topics=[TOPIC_SYSTEM_EVENTS],  # Metrics events go to system-events topic
                    event_types=metrics_events,
                    enabled=True,
                    max_batch_size=10,
                    max_parallel_workers=1
                )

                # Create Kafka subscriber for metrics events
                subscriber = KafkaEventSubscriber(config)

                # Create and register our custom streaming handler
                streaming_handler = StreamingMetricsHandler(customer_id, event_queue)
                subscriber.register_handler(streaming_handler)

                logger.info(f"Starting real-time metrics stream for customer {customer_id}")

                # Send initial connection confirmation
                yield format_sse_message("connected", {
                    "status": "streaming_started",
                    "customer_id": customer_id,
                    "event_types": metrics_events,
                    "timestamp": datetime.now().isoformat()
                })

                # Start the subscriber
                await subscriber.start()

                # Listen for events from our queue
                while True:
                    try:
                        # Wait for events with a timeout to allow for graceful shutdown
                        event = await asyncio.wait_for(event_queue.get(), timeout=30.0)

                        # Format metrics event for streaming
                        stream_data = {
                            "event_type": event.event_type,
                            "customer_id": event.customer_id,
                            "timestamp": event.metadata.created_at if hasattr(event, 'metadata') and event.metadata else datetime.now().isoformat(),
                        }

                        # Add event-specific data based on event type
                        if event.event_type == EVENT_METRICS_BATCH_INGESTED:
                            stream_data.update({
                                "batch_id": event.data.get("batch_id"),
                                "metrics_count": event.data.get("metrics_count"),
                                "service_name": event.data.get("service_name"),
                                "metrics": event.data.get("metrics", [])
                            })
                        elif event.event_type == EVENT_METRIC_PROCESSED:
                            stream_data.update({
                                "metric_name": event.data.get("metric_name"),
                                "metric_type": event.data.get("metric_type"),
                                "value": event.data.get("value"),
                                "labels": event.data.get("labels", {}),
                                "service_name": event.data.get("service_name")
                            })

                        # Stream the event immediately
                        yield format_sse_message("metrics_event", stream_data, getattr(event.metadata, 'event_id', None) if hasattr(event, 'metadata') else None)

                        logger.debug(
                            "Metrics event streamed to UI",
                            customer_id=customer_id,
                            event_type=event.event_type,
                            metric_name=stream_data.get("metric_name")
                        )

                    except asyncio.TimeoutError:
                        # Send keepalive message
                        yield format_sse_message("keepalive", {
                            "timestamp": datetime.now().isoformat(),
                            "status": "listening"
                        })

                    except Exception as e:
                        logger.error(f"Error processing metrics event for streaming: {e}")
                        yield format_sse_message("error", {"message": f"Event processing error: {str(e)}"})

            except Exception as e:
                logger.error(f"Error in real-time metrics stream for customer {customer_id}: {e}")
                yield format_sse_message("error", {
                    "message": f"Stream error: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
            finally:
                # Clean up subscriber
                if subscriber:
                    try:
                        await subscriber.stop()
                        logger.info(f"Stopped metrics subscriber for customer {customer_id}")
                    except Exception as e:
                        logger.error(f"Error stopping metrics subscriber: {e}")

        return StreamingResponse(
            generate_real_time_metrics(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, X-Customer-ID"
            }
        )

    except Exception as e:
        logger.error("Failed to start real-time metrics stream", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to start metrics stream: {str(e)}")


@router.get("/traces")
async def stream_traces(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Stream real-time trace data - Pure event-driven, no polling"""
    try:
        from events.subscribers import KafkaEventSubscriber
        from events.constants import EVENT_TRACES_BATCH_INGESTED, EVENT_TRACE_SPAN_PROCESSED, TOPIC_SYSTEM_EVENTS

        # Trace event types we want to stream to UI
        trace_events = [
            EVENT_TRACES_BATCH_INGESTED,
            EVENT_TRACE_SPAN_PROCESSED
        ]

        # Create a queue to receive events from the custom handler
        event_queue = asyncio.Queue()

        # Custom handler class to capture trace events for this streaming session
        class StreamingTracesHandler:
            """Custom handler to capture trace events for streaming with config-based filtering"""

            def __init__(self, target_customer_id: str, event_queue: asyncio.Queue):
                self.target_customer_id = target_customer_id
                self.event_queue = event_queue
                self.streaming_service = get_streaming_config_service()
                self.rate_limiter = {}

            async def handle(self, event) -> bool:
                """Handle events and put relevant ones in the queue with config-based filtering"""
                try:
                    # Only handle events for our target customer and trace event types
                    if (hasattr(event, 'customer_id') and
                        event.customer_id == self.target_customer_id and
                        hasattr(event, 'event_type') and
                        event.event_type in trace_events):

                        # Apply streaming configuration filters
                        if await self._should_stream_event(event):
                            # Put event in queue for streaming
                            await self.event_queue.put(event)
                            logger.debug(f"Trace event queued for streaming: {event.event_type}")
                        else:
                            logger.debug(f"Trace event filtered out: {event.event_type}")
                        return True

                    return True

                except Exception as e:
                    logger.error(f"Error in trace streaming handler: {e}")
                    return False

            async def _should_stream_event(self, event) -> bool:
                """Apply streaming configuration filters to determine if event should be streamed"""
                try:
                    # Get streaming config for this customer
                    config = await self.streaming_service.get_streaming_config(
                        self.target_customer_id,
                        "traces.batch.ingested"
                    )
                    logger.info(event)
                    # If disabled, don't stream
                    if not config.get("enabled", True):
                        return False

                    # Apply sample rate (0.0 = 0%, 1.0 = 100%)
                    sample_rate = config.get("sample_rate", 1.0)
                    if random.random() > sample_rate:
                        return False

                    # Check rate limiting
                    max_events_per_minute = config.get("max_events_per_minute", 50)
                    if not self._check_rate_limit(max_events_per_minute):
                        return False

                    # Check minimum traces count
                    min_traces_count = config.get("min_traces_count", 1)
                    traces_count = event.data.get("traces_count", 0)
                    if traces_count < min_traces_count:
                        return False

                    # Check service filtering
                    service_name = event.data.get("service_name", "")

                    # Exclude services
                    exclude_services = config.get("exclude_services", [])
                    if service_name in exclude_services:
                        return False

                    # Include services (if specified, only allow these)
                    include_services = config.get("include_services", [])
                    if include_services and service_name not in include_services:
                        return False

                    # Check minimum duration
                    min_duration_ms = config.get("min_duration_ms", 0)
                    traces = event.data.get("traces", [])

                    # If duration filtering is enabled, check if any trace meets criteria
                    if min_duration_ms > 0:
                        has_long_trace = False
                        for trace in traces:
                            if trace.get("duration_ms", 0) >= min_duration_ms:
                                has_long_trace = True
                                break
                        if not has_long_trace:
                            return False

                    # Check priority operations (always stream if present)
                    priority_operations = config.get("priority_operations", [])
                    for trace in traces:
                        for span in trace.get("spans", []):
                            if span.get("operation_name") in priority_operations:
                                return True

                    # Check error-only filtering
                    if config.get("include_errors_only", False):
                        for trace in traces:
                            for span in trace.get("spans", []):
                                if span.get("status", {}).get("code") == "ERROR":
                                    return True
                        return False

                    # Check status filtering
                    include_status = config.get("include_status", ["ok", "error"])
                    if include_status:
                        for trace in traces:
                            for span in trace.get("spans", []):
                                span_status = span.get("status", {}).get("code", "ok").lower()
                                if span_status in [s.lower() for s in include_status]:
                                    return True
                        return False

                    return True

                except Exception as e:
                    logger.error(f"Error applying trace streaming filters: {e}")
                    # Default to streaming on error to avoid losing data
                    return True

            def _check_rate_limit(self, max_events_per_minute: int) -> bool:
                """Check if we're within the rate limit for this customer"""
                current_minute = int(datetime.now().timestamp() / 60)
                key = f"{self.target_customer_id}_{current_minute}"

                if key not in self.rate_limiter:
                    self.rate_limiter[key] = 0

                # Clean old entries
                old_keys = [k for k in self.rate_limiter.keys() if int(k.split('_')[-1]) < current_minute - 1]
                for old_key in old_keys:
                    del self.rate_limiter[old_key]

                if self.rate_limiter[key] >= max_events_per_minute:
                    return False

                self.rate_limiter[key] += 1
                return True

            def get_handler_name(self) -> str:
                return f"streaming_traces_handler_{self.target_customer_id}"

            def get_supported_event_types(self) -> List[str]:
                return trace_events

        async def generate_real_time_traces():
            """Generate real-time trace events as they occur"""
            subscriber = None
            try:
                from events.subscribers import SubscriberConfig

                # Create subscriber config for trace events
                config = SubscriberConfig(
                    name=f"streaming_traces_{customer_id}",
                    consumer_group=f"streaming_traces_{customer_id}",
                    topics=[TOPIC_SYSTEM_EVENTS],  # Trace events go to system-events topic
                    event_types=trace_events,
                    enabled=True,
                    max_batch_size=10,
                    max_parallel_workers=1
                )

                # Create Kafka subscriber for trace events
                subscriber = KafkaEventSubscriber(config)

                # Create and register our custom streaming handler
                streaming_handler = StreamingTracesHandler(customer_id, event_queue)
                subscriber.register_handler(streaming_handler)

                logger.info(f"Starting real-time traces stream for customer {customer_id}")

                # Send initial connection confirmation
                yield format_sse_message("connected", {
                    "status": "streaming_started",
                    "customer_id": customer_id,
                    "event_types": trace_events,
                    "timestamp": datetime.now().isoformat()
                })

                # Start the subscriber
                await subscriber.start()

                # Listen for events from our queue
                while True:
                    try:
                        # Wait for events with a timeout to allow for graceful shutdown
                        event = await asyncio.wait_for(event_queue.get(), timeout=30.0)

                        # Format trace event for streaming
                        stream_data = {
                            "event_type": event.event_type,
                            "customer_id": event.customer_id,
                            "timestamp": event.metadata.created_at if hasattr(event, 'metadata') and event.metadata else datetime.now().isoformat(),
                        }

                        # Add event-specific data based on event type
                        if event.event_type == EVENT_TRACES_BATCH_INGESTED:
                            stream_data.update({
                                "batch_id": event.data.get("batch_id"),
                                "traces_count": event.data.get("traces_count"),
                                "service_name": event.data.get("service_name"),
                                "traces": event.data.get("traces", [])
                            })
                        elif event.event_type == EVENT_TRACE_SPAN_PROCESSED:
                            stream_data.update({
                                "trace_id": event.data.get("trace_id"),
                                "span_id": event.data.get("span_id"),
                                "operation_name": event.data.get("operation_name"),
                                "service_name": event.data.get("service_name"),
                                "duration_ms": event.data.get("duration_ms"),
                                "status": event.data.get("status")
                            })

                        # Stream the event immediately
                        yield format_sse_message("traces_event", stream_data, getattr(event.metadata, 'event_id', None) if hasattr(event, 'metadata') else None)

                        logger.debug(
                            "Trace event streamed to UI",
                            customer_id=customer_id,
                            event_type=event.event_type,
                            trace_id=stream_data.get("trace_id")
                        )

                    except asyncio.TimeoutError:
                        # Send keepalive message
                        yield format_sse_message("keepalive", {
                            "timestamp": datetime.now().isoformat(),
                            "status": "listening"
                        })

                    except Exception as e:
                        logger.error(f"Error processing trace event for streaming: {e}")
                        yield format_sse_message("error", {"message": f"Event processing error: {str(e)}"})

            except Exception as e:
                logger.error(f"Error in real-time traces stream for customer {customer_id}: {e}")
                yield format_sse_message("error", {
                    "message": f"Stream error: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
            finally:
                # Clean up subscriber
                if subscriber:
                    try:
                        await subscriber.stop()
                        logger.info(f"Stopped traces subscriber for customer {customer_id}")
                    except Exception as e:
                        logger.error(f"Error stopping traces subscriber: {e}")

        return StreamingResponse(
            generate_real_time_traces(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, X-Customer-ID"
            }
        )

    except Exception as e:
        logger.error("Failed to start real-time traces stream", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to start traces stream: {str(e)}")


@router.get("/security")
async def stream_security_events(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Stream real-time security events - Pure event-driven, no polling"""
    try:
        from events.subscribers import KafkaEventSubscriber
        from events.constants import (
            EVENT_SIGMA_RULE_CREATED, EVENT_SIGMA_RULE_UPDATED, EVENT_SIGMA_RULE_DELETED,
            EVENT_SIGMA_RULE_ENABLED, EVENT_SIGMA_RULE_DISABLED,
            EVENT_SECURITY_DETECTION_TRIGGERED, EVENT_SECURITY_DETECTION_RESOLVED, EVENT_SECURITY_DETECTION_ACKNOWLEDGED, EVENT_SECURITY_DETECTION_FALSE_POSITIVE,
            TOPIC_SYSTEM_EVENTS, TOPIC_UI_REALTIME_EVENTS
        )

        # Security event types we want to stream to UI
        security_events = [
            EVENT_SIGMA_RULE_CREATED,
            EVENT_SIGMA_RULE_UPDATED,
            EVENT_SIGMA_RULE_DELETED,
            EVENT_SIGMA_RULE_ENABLED,
            EVENT_SIGMA_RULE_DISABLED,
            EVENT_SECURITY_DETECTION_TRIGGERED,
            EVENT_SECURITY_DETECTION_RESOLVED,
            EVENT_SECURITY_DETECTION_ACKNOWLEDGED,
            EVENT_SECURITY_DETECTION_FALSE_POSITIVE
        ]

        # Create a queue to receive events from the custom handler
        event_queue = asyncio.Queue()

        # Custom handler class to capture security events for this streaming session
        class StreamingSecurityHandler:
            """Custom handler to capture security events for streaming"""

            def __init__(self, target_customer_id: str, event_queue: asyncio.Queue):
                self.target_customer_id = target_customer_id
                self.event_queue = event_queue

            async def handle(self, event) -> bool:
                """Handle events and put relevant ones in the queue"""
                try:
                    # Only handle events for our target customer and security event types
                    if (hasattr(event, 'customer_id') and
                        (event.customer_id == self.target_customer_id or event.customer_id is None) and  # Include default rules
                        hasattr(event, 'event_type') and
                        event.event_type in security_events):

                        # Put event in queue for streaming
                        await self.event_queue.put(event)
                        logger.debug(f"Security event queued for streaming: {event.event_type}")
                        return True

                    return True

                except Exception as e:
                    logger.error(f"Error in security streaming handler: {e}")
                    return False

            def get_handler_name(self) -> str:
                return f"streaming_security_handler_{self.target_customer_id}"

            def get_supported_event_types(self) -> List[str]:
                return security_events

        async def generate_real_time_security_events():
            """Generate real-time security events as they occur"""
            subscriber = None
            try:
                from events.subscribers import SubscriberConfig

                # Create subscriber config for security events
                config = SubscriberConfig(
                    name=f"streaming_security_{customer_id}",
                    consumer_group=f"streaming_security_{customer_id}",
                    topics=[TOPIC_SYSTEM_EVENTS],  # Security events go to system-events topic
                    event_types=security_events,
                    enabled=True,
                    max_batch_size=10,
                    max_parallel_workers=1
                )

                # Create Kafka subscriber for security events
                subscriber = KafkaEventSubscriber(config)

                # Create and register our custom streaming handler
                streaming_handler = StreamingSecurityHandler(customer_id, event_queue)
                subscriber.register_handler(streaming_handler)

                logger.info(f"Starting real-time security stream for customer {customer_id}")

                # Send initial connection confirmation
                yield format_sse_message("connected", {
                    "status": "streaming_started",
                    "customer_id": customer_id,
                    "event_types": security_events,
                    "timestamp": datetime.now().isoformat()
                })

                # Start the subscriber
                await subscriber.start()

                # Listen for events from our queue
                while True:
                    try:
                        # Wait for events with a timeout to allow for graceful shutdown
                        event = await asyncio.wait_for(event_queue.get(), timeout=30.0)

                        # Format security event for streaming
                        stream_data = {
                            "event_type": event.event_type,
                            "customer_id": event.customer_id,
                            "timestamp": event.metadata.created_at if hasattr(event, 'metadata') and event.metadata else datetime.now().isoformat(),
                        }

                        # Add event-specific data based on event type
                        if event.event_type.startswith("security.sigma.rule."):
                            stream_data.update({
                                "rule_id": event.data.get("rule_id"),
                                "rule_name": event.data.get("rule_name"),
                                "severity": event.data.get("severity"),
                                "enabled": event.data.get("enabled"),
                                "is_default_rule": event.data.get("is_default_rule", False),
                                "rule_data": event.data.get("rule_data", {})
                            })
                        elif event.event_type.startswith("security.detection."):
                            stream_data.update({
                                "detection_id": event.data.get("detection_id"),
                                "rule_id": event.data.get("rule_id"),
                                "rule_name": event.data.get("rule_name"),
                                "severity": event.data.get("severity"),
                                "confidence": event.data.get("confidence"),
                                "matched_fields": event.data.get("matched_fields", {}),
                                "attack_techniques": event.data.get("attack_techniques", [])
                            })

                        # Stream the event immediately
                        yield format_sse_message("security_event", stream_data, getattr(event.metadata, 'event_id', None) if hasattr(event, 'metadata') else None)

                        logger.debug(
                            "Security event streamed to UI",
                            customer_id=customer_id,
                            event_type=event.event_type,
                            rule_id=stream_data.get("rule_id")
                        )

                    except asyncio.TimeoutError:
                        # Send keepalive message
                        yield format_sse_message("keepalive", {
                            "timestamp": datetime.now().isoformat(),
                            "status": "listening"
                        })

                    except Exception as e:
                        logger.error(f"Error processing security event for streaming: {e}")
                        yield format_sse_message("error", {"message": f"Event processing error: {str(e)}"})

            except Exception as e:
                logger.error(f"Error in real-time security stream for customer {customer_id}: {e}")
                yield format_sse_message("error", {
                    "message": f"Stream error: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
            finally:
                # Clean up subscriber
                if subscriber:
                    try:
                        await subscriber.stop()
                        logger.info(f"Stopped security subscriber for customer {customer_id}")
                    except Exception as e:
                        logger.error(f"Error stopping security subscriber: {e}")

        return StreamingResponse(
            generate_real_time_security_events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, X-Customer-ID"
            }
        )

    except Exception as e:
        logger.error("Failed to start real-time security stream", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to start security stream: {str(e)}")


@router.get("/alerts")
async def stream_alerts(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Stream real-time alert events - Pure event-driven, no polling"""
    try:
        from events.subscribers import KafkaEventSubscriber
        from events.constants import EVENT_UI_ALERT_TRIGGERED, EVENT_UI_ALERT_ACKNOWLEDGED, EVENT_UI_ALERT_RESOLVED, TOPIC_UI_REALTIME_EVENTS

        # Event types we want to stream to UI
        ui_alert_events = [
            EVENT_UI_ALERT_TRIGGERED,
            EVENT_UI_ALERT_ACKNOWLEDGED,
            EVENT_UI_ALERT_RESOLVED
        ]

        # Create a queue to receive events from the custom handler
        event_queue = asyncio.Queue()

        # Custom handler class to capture UI events for this streaming session
        class StreamingAlertHandler:
            """Custom handler to capture UI alert events for streaming"""

            def __init__(self, target_customer_id: str, event_queue: asyncio.Queue):
                self.target_customer_id = target_customer_id
                self.event_queue = event_queue

            async def handle(self, event) -> bool:
                """Handle events and put relevant ones in the queue"""
                try:
                    logger.info(
                        "StreamingAlertHandler received event",
                        event_type=getattr(event, 'event_type', 'NONE'),
                        customer_id=getattr(event, 'customer_id', 'NONE'),
                        target_customer_id=self.target_customer_id,
                        has_customer_id=hasattr(event, 'customer_id'),
                        has_event_type=hasattr(event, 'event_type'),
                        event_data=str(event)[:200]  # Changed from 'event' to 'event_data'
                    )

                    # Only handle events for our target customer and UI alert types
                    if (hasattr(event, 'customer_id') and
                        event.customer_id == self.target_customer_id and
                        hasattr(event, 'event_type') and
                        event.event_type in ui_alert_events):

                        # Put event in queue for streaming
                        await self.event_queue.put(event)

                        return True
                    else:
                        logger.debug(
                            "Event filtered out",
                            customer_match=hasattr(event, 'customer_id') and event.customer_id == self.target_customer_id,
                            type_match=hasattr(event, 'event_type') and event.event_type in ui_alert_events
                        )

                    return True

                except Exception as e:
                    logger.error(f"Error in streaming handler: {e}")
                    return False

            def get_handler_name(self) -> str:
                return f"streaming_alert_handler_{self.target_customer_id}"

            def get_supported_event_types(self) -> List[str]:
                return ui_alert_events

        async def generate_real_time_alerts():
            """Generate real-time alert events as they occur"""
            subscriber = None
            try:
                from events.subscribers import SubscriberConfig

                # Create subscriber config for UI events
                config = SubscriberConfig(
                    name=f"streaming_alerts_{customer_id}",
                    consumer_group=f"streaming_alerts_{customer_id}",
                    topics=[TOPIC_UI_REALTIME_EVENTS],
                    event_types=ui_alert_events,
                    enabled=True,
                    max_batch_size=10,
                    max_parallel_workers=1
                )

                # Create Kafka subscriber for UI events
                subscriber = KafkaEventSubscriber(config)

                # Create and register our custom streaming handler
                streaming_handler = StreamingAlertHandler(customer_id, event_queue)
                subscriber.register_handler(streaming_handler)

                logger.info(f"Starting real-time alert stream for customer {customer_id}")

                # Send initial connection confirmation
                yield format_sse_message("connected", {
                    "status": "streaming_started",
                    "customer_id": customer_id,
                    "event_types": ui_alert_events,
                    "timestamp": datetime.now().isoformat()
                })

                # Start the subscriber
                await subscriber.start()

                # Listen for events from our queue
                while True:
                    try:
                        # Wait for events with a timeout to allow for graceful shutdown
                        event = await asyncio.wait_for(event_queue.get(), timeout=30.0)

                        # Format UI event for streaming
                        stream_data = {
                            "alert_id": event.data.get("alert_id"),
                            "rule_id": event.data.get("rule_id"),
                            "rule_name": event.data.get("rule_name"),
                            "severity": event.data.get("severity"),
                            "status": event.data.get("status"),
                            "triggered_at": event.data.get("triggered_at"),
                            "message": event.data.get("message"),
                            "event_type": event.event_type,
                            "timestamp": event.metadata.created_at if hasattr(event, 'metadata') and event.metadata else datetime.now().isoformat(),
                            "ui_metadata": event.data.get("ui_metadata", {})
                        }

                        # Stream the event immediately
                        yield format_sse_message("alert_event", stream_data, getattr(event.metadata, 'event_id', None) if hasattr(event, 'metadata') else None)

                        logger.debug(
                            "Alert event streamed to UI",
                            customer_id=customer_id,
                            alert_id=stream_data.get("alert_id"),
                            event_type=event.event_type
                        )

                    except asyncio.TimeoutError:
                        # Send keepalive message
                        yield format_sse_message("keepalive", {
                            "timestamp": datetime.now().isoformat(),
                            "status": "listening"
                        })

                    except Exception as e:
                        logger.error(f"Error processing alert event for streaming: {e}")
                        yield format_sse_message("error", {"message": f"Event processing error: {str(e)}"})

            except Exception as e:
                logger.error(f"Error in real-time alert stream for customer {customer_id}: {e}")
                yield format_sse_message("error", {
                    "message": f"Stream error: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
            finally:
                # Clean up subscriber
                if subscriber:
                    try:
                        await subscriber.stop()
                        logger.info(f"Stopped subscriber for customer {customer_id}")
                    except Exception as e:
                        logger.error(f"Error stopping subscriber: {e}")

        return StreamingResponse(
            generate_real_time_alerts(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, X-Customer-ID"
            }
        )

    except Exception as e:
        logger.error("Failed to start real-time alerts stream", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to start alerts stream: {str(e)}")


@router.get("/usage")
async def stream_usage_data(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Stream real-time usage data"""
    try:
        usage_service = UsageService()

        async def generate_usage():
            while True:
                try:
                    # Get current usage statistics
                    usage_data = await usage_service.get_tenant_usage_summary(
                        tenant_id=customer_id
                    )

                    if usage_data:
                        yield format_sse_message("usage", usage_data)

                    await asyncio.sleep(30)  # Update every 30 seconds

                except Exception as e:
                    logger.error("Error streaming usage data", error=str(e), customer_id=customer_id)
                    yield format_sse_message("error", {"message": f"Usage streaming error: {str(e)}"})
                    break

        return StreamingResponse(
            generate_usage(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, X-Customer-ID"
            }
        )

    except Exception as e:
        logger.error("Failed to start usage stream", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to start usage stream: {str(e)}")


@router.get("/ai-insights")
async def stream_ai_insights(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Stream real-time AI insights and anomaly detections"""
    try:
        ai_service = AIService()

        async def generate_ai_insights():
            while True:
                try:
                    # Get recent AI insights
                    insights = await ai_service.get_anomaly_insights(
                        customer_id=customer_id,
                        hours=1,
                        limit=10
                    )

                    if insights:
                        yield format_sse_message("ai_insights", insights)

                    await asyncio.sleep(45)  # Update every 45 seconds

                except Exception as e:
                    logger.error("Error streaming AI insights", error=str(e), customer_id=customer_id)
                    yield format_sse_message("error", {"message": f"AI insights streaming error: {str(e)}"})
                    break

        return StreamingResponse(
            generate_ai_insights(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, X-Customer-ID"
            }
        )

    except Exception as e:
        logger.error("Failed to start AI insights stream", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to start AI insights stream: {str(e)}")


@router.get("/anomalies")
async def stream_anomalies(
    severity_threshold: Optional[str] = "medium",
    services: Optional[str] = None,
    categories: Optional[str] = None,
    # Support both header and query param authentication for SSE (EventSource doesn't support headers)
    customer_id: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
    x_customer_id: Optional[str] = Header(None, alias="X-Customer-ID")
):
    """
    Stream real-time anomaly detections - Event-driven, no polling

    Query parameters:
    - severity_threshold: Minimum severity to receive (low, medium, high, critical)
    - services: Comma-separated list of services to filter
    - categories: Comma-separated list of anomaly categories
    - customer_id: Customer ID (for SSE clients that can't send headers)
    - token: Authentication token (for SSE clients that can't send headers)
    """

    # Get customer_id from query param or header
    final_customer_id = customer_id or x_customer_id
    if not final_customer_id:
        raise HTTPException(status_code=401, detail="Missing customer_id (provide via query param or X-Customer-ID header)")

    # Use the resolved customer_id for the rest of the function
    customer_id = final_customer_id
    try:
        from events.subscribers import KafkaEventSubscriber
        from events.constants import TOPIC_UI_REALTIME_EVENTS

        # Define anomaly event types
        EVENT_ANOMALY_DETECTED = "ai.anomaly.detected"
        EVENT_ANOMALY_RESOLVED = "ai.anomaly.resolved"
        EVENT_ANOMALY_UPDATED = "ai.anomaly.updated"

        anomaly_events = [
            EVENT_ANOMALY_DETECTED,
            EVENT_ANOMALY_RESOLVED,
            EVENT_ANOMALY_UPDATED
        ]

        # Parse filters
        service_list = [s.strip() for s in services.split(",")] if services else []
        category_list = [c.strip() for c in categories.split(",")] if categories else []
        severity_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        min_severity = severity_order.get(severity_threshold, 2)

        # Create event queue
        event_queue = asyncio.Queue()

        class StreamingAnomalyHandler:
            """Custom handler for anomaly event streaming with filtering"""

            def __init__(self, target_customer_id: str, event_queue: asyncio.Queue,
                        min_severity: int, service_list: List[str], category_list: List[str]):
                self.target_customer_id = target_customer_id
                self.event_queue = event_queue
                self.min_severity = min_severity
                self.service_list = service_list
                self.category_list = category_list

            async def handle(self, event) -> bool:
                """Handle anomaly events and apply filters"""
                try:
                    if (hasattr(event, 'customer_id') and
                        event.customer_id == self.target_customer_id and
                        hasattr(event, 'event_type') and
                        event.event_type in anomaly_events):

                        # Apply filters
                        if await self._should_stream_event(event):
                            await self.event_queue.put(event)
                            logger.debug(f"Anomaly event queued: {event.event_type}")
                        return True
                    return True

                except Exception as e:
                    logger.error(f"Error in anomaly streaming handler: {e}")
                    return False

            async def _should_stream_event(self, event) -> bool:
                """Apply filters to anomaly events"""
                try:
                    data = event.data

                    # Severity filter
                    event_severity = data.get("severity", "medium")
                    event_severity_num = severity_order.get(event_severity, 0)
                    if event_severity_num < self.min_severity:
                        return False

                    # Service filter
                    if self.service_list:
                        affected_services = data.get("affected_services", [])
                        if not any(s in self.service_list for s in affected_services):
                            return False

                    # Category filter
                    if self.category_list:
                        event_category = data.get("category", "")
                        if event_category not in self.category_list:
                            return False

                    return True

                except Exception as e:
                    logger.error(f"Error filtering anomaly event: {e}")
                    return True  # Default to streaming on error

            def get_handler_name(self) -> str:
                return f"streaming_anomaly_handler_{self.target_customer_id}"

            def get_supported_event_types(self) -> List[str]:
                return anomaly_events

        async def generate_real_time_anomalies():
            """Generate real-time anomaly events"""
            subscriber = None
            try:
                from events.subscribers import SubscriberConfig

                # Create subscriber config
                config = SubscriberConfig(
                    name=f"streaming_anomalies_{customer_id}",
                    consumer_group=f"streaming_anomalies_{customer_id}",
                    topics=[TOPIC_UI_REALTIME_EVENTS],
                    event_types=anomaly_events,
                    enabled=True,
                    max_batch_size=10,
                    max_parallel_workers=1
                )

                subscriber = KafkaEventSubscriber(config)
                streaming_handler = StreamingAnomalyHandler(
                    customer_id, event_queue, min_severity, service_list, category_list
                )
                subscriber.register_handler(streaming_handler)

                logger.info(f"Starting real-time anomaly stream for customer {customer_id}")

                # Send connection confirmation
                yield format_sse_message("connected", {
                    "status": "streaming_started",
                    "customer_id": customer_id,
                    "filters": {
                        "severity_threshold": severity_threshold,
                        "services": service_list,
                        "categories": category_list
                    },
                    "event_types": anomaly_events,
                    "timestamp": datetime.now().isoformat()
                })

                # Start subscriber
                await subscriber.start()

                # Stream events
                while True:
                    try:
                        event = await asyncio.wait_for(event_queue.get(), timeout=30.0)

                        stream_data = {
                            "event_type": event.event_type,
                            "customer_id": event.customer_id,
                            "timestamp": event.metadata.created_at if hasattr(event, 'metadata') and event.metadata else datetime.now().isoformat(),
                            "anomaly_id": event.data.get("anomaly_id"),
                            "title": event.data.get("title"),
                            "severity": event.data.get("severity"),
                            "confidence": event.data.get("confidence"),
                            "category": event.data.get("category"),
                            "description": event.data.get("description"),
                            "affected_services": event.data.get("affected_services", []),
                            "recommended_actions": event.data.get("recommended_actions", [])
                        }

                        # Add event-specific data
                        if event.event_type == EVENT_ANOMALY_DETECTED:
                            stream_data.update({
                                "baseline_value": event.data.get("baseline_value"),
                                "current_value": event.data.get("current_value"),
                                "deviation_score": event.data.get("deviation_score"),
                                "affected_metrics": event.data.get("affected_metrics", [])
                            })
                        elif event.event_type == EVENT_ANOMALY_RESOLVED:
                            stream_data.update({
                                "resolution": event.data.get("resolution"),
                                "resolved_by": event.data.get("resolved_by"),
                                "resolved_at": event.data.get("resolved_at")
                            })

                        yield format_sse_message("anomaly_event", stream_data,
                                                getattr(event.metadata, 'event_id', None) if hasattr(event, 'metadata') else None)

                        logger.debug(
                            "Anomaly event streamed to UI",
                            customer_id=customer_id,
                            anomaly_id=stream_data.get("anomaly_id"),
                            event_type=event.event_type
                        )

                    except asyncio.TimeoutError:
                        # Keepalive
                        yield format_sse_message("keepalive", {
                            "timestamp": datetime.now().isoformat(),
                            "status": "listening"
                        })

                    except Exception as e:
                        logger.error(f"Error processing anomaly event: {e}")
                        yield format_sse_message("error", {"message": f"Event processing error: {str(e)}"})

            except Exception as e:
                logger.error(f"Error in anomaly stream for customer {customer_id}: {e}")
                yield format_sse_message("error", {
                    "message": f"Stream error: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
            finally:
                if subscriber:
                    try:
                        await subscriber.stop()
                        logger.info(f"Stopped anomaly subscriber for customer {customer_id}")
                    except Exception as e:
                        logger.error(f"Error stopping anomaly subscriber: {e}")

        return StreamingResponse(
            generate_real_time_anomalies(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, X-Customer-ID"
            }
        )

    except Exception as e:
        logger.error("Failed to start anomaly stream", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to start anomaly stream: {str(e)}")


@router.get("/health")
async def streaming_health():
    """Health check for streaming service"""
    return {
        "status": "healthy",
        "message": "Streaming service operational",
        "endpoints": [
            "/v1/stream/metrics",
            "/v1/stream/traces",
            "/v1/stream/security",
            "/v1/stream/alerts",
            "/v1/stream/usage",
            "/v1/stream/ai-insights",
            "/v1/stream/anomalies"
        ]
    }
