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
                    logger.error("Error streaming metrics", error=str(e), customer_id=customer_id)
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
    """Stream real-time alert events"""
    try:
        alert_service = AlertService()
        
        async def generate_alerts():
            while True:
                try:
                    # Get recent alerts
                    alerts = await alert_service.get_alerts(
                        customer_id=customer_id,
                        limit=20,
                        status_filter=None
                    )
                    
                    # Filter for recent alerts (last 10 minutes)
                    recent_alerts = [
                        alert for alert in alerts
                        if datetime.fromisoformat(alert.get('created_at', '1970-01-01')) > 
                           datetime.now() - timedelta(minutes=10)
                    ]
                    
                    if recent_alerts:
                        yield format_sse_message("alerts", recent_alerts)
                    
                    await asyncio.sleep(20)  # Update every 20 seconds
                    
                except Exception as e:
                    logger.error("Error streaming alerts", error=str(e), customer_id=customer_id)
                    yield format_sse_message("error", {"message": f"Alerts streaming error: {str(e)}"})
                    break
        
        return StreamingResponse(
            generate_alerts(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, X-Customer-ID"
            }
        )
        
    except Exception as e:
        logger.error("Failed to start alerts stream", error=str(e), customer_id=customer_id)
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
                    usage_data = await usage_service.get_usage_summary(
                        customer_id=customer_id,
                        start_date=datetime.now().date() - timedelta(days=1),
                        end_date=datetime.now().date()
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