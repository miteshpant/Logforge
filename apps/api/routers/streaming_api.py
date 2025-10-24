"""
Streaming API - Server-Sent Events for Real-Time Data
Real-time streaming endpoints for metrics, traces, security events, alerts, usage, and AI insights
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Header
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any, List
import structlog
import json
import asyncio
from datetime import datetime, timedelta

from services.observability_service import ObservabilityService
from services.security_service import SecurityService
from services.alert_service import AlertService
from services.usage_service import UsageService
from services.ai_service import AIService

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
    metric_names: str = "cpu_usage,memory_usage,disk_usage",
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Stream real-time metrics data"""
    try:
        observability_service = ObservabilityService()
        metric_list = metric_names.split(",")
        
        async def generate_metrics():
            while True:
                try:
                    # Get latest metrics for the specified names
                    metrics = await observability_service.get_metrics(
                        customer_id=customer_id,
                        metric_name=None,
                        hours=1,
                        limit=100
                    )
                    
                    # Filter metrics by requested names
                    filtered_metrics = [
                        metric for metric in metrics 
                        if metric.get('name') in metric_list
                    ]
                    
                    if filtered_metrics:
                        yield format_sse_message("metrics", filtered_metrics)
                    
                    await asyncio.sleep(5)  # Update every 5 seconds
                    
                except Exception as e:
                    logger.error("Error streaming metrics", error=str(e), customer_id=customer_id, 
                               error_type=type(e).__name__, metric_names=metric_names)
                    yield format_sse_message("error", {"message": f"Metrics streaming error: {str(e)}"})
                    break
        
        return StreamingResponse(
            generate_metrics(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, X-Customer-ID"
            }
        )
        
    except Exception as e:
        logger.error("Failed to start metrics stream", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to start metrics stream: {str(e)}")


@router.get("/traces")
async def stream_traces(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Stream real-time trace data"""
    try:
        observability_service = ObservabilityService()
        
        async def generate_traces():
            while True:
                try:
                    # Get recent traces
                    traces = await observability_service.search_traces(
                        customer_id=customer_id,
                        filters={
                            "start_time": datetime.now() - timedelta(minutes=5),
                            "end_time": datetime.now(),
                            "limit": 10
                        },
                        limit=10
                    )
                    
                    if traces:
                        yield format_sse_message("traces", traces)
                    
                    await asyncio.sleep(10)  # Update every 10 seconds
                    
                except Exception as e:
                    logger.error("Error streaming traces", error=str(e), customer_id=customer_id)
                    yield format_sse_message("error", {"message": f"Traces streaming error: {str(e)}"})
                    break
        
        return StreamingResponse(
            generate_traces(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, X-Customer-ID"
            }
        )
        
    except Exception as e:
        logger.error("Failed to start traces stream", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to start traces stream: {str(e)}")


@router.get("/security")
async def stream_security_events(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Stream real-time security events"""
    try:
        security_service = SecurityService()
        
        async def generate_security_events():
            while True:
                try:
                    # Get recent security events
                    events = await security_service.get_security_events(
                        customer_id=customer_id,
                        limit=20,
                        status_filter=None
                    )
                    
                    # Filter for recent events (last 5 minutes)
                    recent_events = [
                        event for event in events
                        if datetime.fromisoformat(event.get('timestamp', '1970-01-01')) > 
                           datetime.now() - timedelta(minutes=5)
                    ]
                    
                    if recent_events:
                        yield format_sse_message("security_events", recent_events)
                    
                    await asyncio.sleep(15)  # Update every 15 seconds
                    
                except Exception as e:
                    logger.error("Error streaming security events", error=str(e), customer_id=customer_id)
                    yield format_sse_message("error", {"message": f"Security events streaming error: {str(e)}"})
                    break
        
        return StreamingResponse(
            generate_security_events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, X-Customer-ID"
            }
        )
        
    except Exception as e:
        logger.error("Failed to start security events stream", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to start security events stream: {str(e)}")


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
                    # Only handle events for our target customer and UI alert types
                    if (hasattr(event, 'customer_id') and 
                        event.customer_id == self.target_customer_id and
                        hasattr(event, 'event_type') and
                        event.event_type in ui_alert_events):
                        
                        # Put event in queue for streaming
                        await self.event_queue.put(event)
                        logger.debug(f"UI event queued for streaming: {event.event_type}")
                        return True
                        
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
            "/v1/stream/ai-insights"
        ]
    }