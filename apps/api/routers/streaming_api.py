"""
Real-Time Streaming API - Server-Sent Events (SSE) Endpoints
Provides live streaming capabilities for observability, security, alerts, usage, and AI insights
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, AsyncGenerator
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import structlog

from authn_authz_middleware import get_current_user
from models import User
from services.observability_service import ObservabilityService
from services.security_service import SecurityService
from services.usage_service import UsageService
from services.ai_service import AiService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["streaming"])

# Service instances
observability_service = ObservabilityService()
security_service = SecurityService()
usage_service = UsageService()
ai_service = AiService()

# SSE response headers
SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Cache-Control",
}

# Active streaming connections tracking for cleanup
active_connections: Dict[str, Dict[str, Any]] = {}

class StreamingResponse(StreamingResponse):
    """Custom SSE Streaming Response with proper headers"""
    def __init__(self, content, status_code: int = 200):
        super().__init__(content=content, status_code=status_code, headers=SSE_HEADERS, media_type="text/event-stream")

def format_sse_message(data: Dict[str, Any], event_type: str = "message") -> str:
    """Format data as Server-Sent Events message"""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

async def heartbeat_generator() -> AsyncGenerator[str, None]:
    """Generate periodic heartbeat messages to keep connection alive"""
    while True:
        yield format_sse_message({"type": "heartbeat", "timestamp": datetime.now().isoformat()}, "heartbeat")
        await asyncio.sleep(30)  # Send heartbeat every 30 seconds

# =================================================================
# OBSERVABILITY STREAMING ENDPOINTS
# =================================================================

@router.get("/observability/metrics/stream")
async def stream_metrics(
    metrics: str = Query(..., description="Comma-separated list of metric names to stream"),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """
    Stream real-time metrics data
    
    Streams selected metrics in real-time using Server-Sent Events.
    Client will receive metric updates as they occur.
    """
    connection_id = str(uuid.uuid4())
    metric_names = [m.strip() for m in metrics.split(',')]
    
    logger.info("Starting metrics stream", 
                connection_id=connection_id, 
                metrics=metric_names,
                user_id=current_user.id)
    
    async def metrics_stream_generator():
        try:
            active_connections[connection_id] = {
                "type": "metrics",
                "user_id": current_user.id,
                "metrics": metric_names,
                "started_at": datetime.now()
            }
            
            # Send initial connection confirmation
            yield format_sse_message({
                "type": "connection_established",
                "connection_id": connection_id,
                "metrics": metric_names,
                "timestamp": datetime.now().isoformat()
            }, "connection")
            
            # Stream metrics data
            last_update = time.time()
            while True:
                try:
                    # Check if client disconnected
                    if await request.is_disconnected():
                        logger.info("Client disconnected", connection_id=connection_id)
                        break
                    
                    # Generate sample metrics data (replace with real observability service calls)
                    current_time = datetime.now()
                    for metric_name in metric_names:
                        metric_data = await generate_sample_metric(metric_name, current_time)
                        yield format_sse_message(metric_data, "metric")
                    
                    # Stream interval - every 2 seconds
                    await asyncio.sleep(2)
                    
                except asyncio.CancelledError:
                    logger.info("Metrics stream cancelled", connection_id=connection_id)
                    break
                except Exception as e:
                    logger.error("Error in metrics stream", connection_id=connection_id, error=str(e))
                    yield format_sse_message({
                        "type": "error",
                        "message": f"Stream error: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    }, "error")
                    break
                    
        finally:
            # Cleanup connection
            if connection_id in active_connections:
                del active_connections[connection_id]
            logger.info("Metrics stream ended", connection_id=connection_id)
    
    return StreamingResponse(metrics_stream_generator())

@router.get("/observability/traces/stream")
async def stream_traces(
    min_duration: int = Query(100, description="Minimum trace duration in milliseconds"),
    status: str = Query("error,timeout", description="Comma-separated status filters"),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Stream real-time distributed tracing data"""
    connection_id = str(uuid.uuid4())
    status_filters = [s.strip() for s in status.split(',')]
    
    logger.info("Starting traces stream", 
                connection_id=connection_id,
                min_duration=min_duration,
                status_filters=status_filters,
                user_id=current_user.id)
    
    async def traces_stream_generator():
        try:
            active_connections[connection_id] = {
                "type": "traces",
                "user_id": current_user.id,
                "filters": {"min_duration": min_duration, "status": status_filters},
                "started_at": datetime.now()
            }
            
            yield format_sse_message({
                "type": "connection_established",
                "connection_id": connection_id,
                "filters": {"min_duration": min_duration, "status": status_filters},
                "timestamp": datetime.now().isoformat()
            }, "connection")
            
            while True:
                try:
                    if await request.is_disconnected():
                        break
                    
                    # Generate sample trace data
                    trace_data = await generate_sample_trace(min_duration, status_filters)
                    if trace_data:
                        yield format_sse_message(trace_data, "trace")
                    
                    await asyncio.sleep(3)  # Traces every 3 seconds
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("Error in traces stream", connection_id=connection_id, error=str(e))
                    break
                    
        finally:
            if connection_id in active_connections:
                del active_connections[connection_id]
            logger.info("Traces stream ended", connection_id=connection_id)
    
    return StreamingResponse(traces_stream_generator())

# =================================================================
# SECURITY STREAMING ENDPOINTS
# =================================================================

@router.get("/security/events/stream")
async def stream_security_events(
    severity: str = Query("medium,high,critical", description="Comma-separated severity levels"),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Stream real-time security events and threat detections"""
    connection_id = str(uuid.uuid4())
    severity_filters = [s.strip() for s in severity.split(',')]
    
    logger.info("Starting security events stream", 
                connection_id=connection_id,
                severity_filters=severity_filters,
                user_id=current_user.id)
    
    async def security_stream_generator():
        try:
            active_connections[connection_id] = {
                "type": "security",
                "user_id": current_user.id,
                "severity_filters": severity_filters,
                "started_at": datetime.now()
            }
            
            yield format_sse_message({
                "type": "connection_established",
                "connection_id": connection_id,
                "severity_filters": severity_filters,
                "timestamp": datetime.now().isoformat()
            }, "connection")
            
            while True:
                try:
                    if await request.is_disconnected():
                        break
                    
                    # Generate sample security event
                    security_event = await generate_sample_security_event(severity_filters)
                    if security_event:
                        yield format_sse_message(security_event, "security_event")
                    
                    await asyncio.sleep(5)  # Security events every 5 seconds
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("Error in security stream", connection_id=connection_id, error=str(e))
                    break
                    
        finally:
            if connection_id in active_connections:
                del active_connections[connection_id]
            logger.info("Security stream ended", connection_id=connection_id)
    
    return StreamingResponse(security_stream_generator())

# =================================================================
# ALERTS STREAMING ENDPOINTS
# =================================================================

@router.get("/alerts/events/stream")
async def stream_alert_events(
    severity: str = Query("medium,high,critical", description="Comma-separated severity levels"),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Stream real-time alert notifications and rule triggers"""
    connection_id = str(uuid.uuid4())
    severity_filters = [s.strip() for s in severity.split(',')]
    
    logger.info("Starting alert events stream", 
                connection_id=connection_id,
                severity_filters=severity_filters,
                user_id=current_user.id)
    
    async def alerts_stream_generator():
        try:
            active_connections[connection_id] = {
                "type": "alerts",
                "user_id": current_user.id,
                "severity_filters": severity_filters,
                "started_at": datetime.now()
            }
            
            yield format_sse_message({
                "type": "connection_established",
                "connection_id": connection_id,
                "severity_filters": severity_filters,
                "timestamp": datetime.now().isoformat()
            }, "connection")
            
            while True:
                try:
                    if await request.is_disconnected():
                        break
                    
                    # Generate sample alert event
                    alert_event = await generate_sample_alert_event(severity_filters)
                    if alert_event:
                        yield format_sse_message(alert_event, "alert_event")
                    
                    await asyncio.sleep(4)  # Alert events every 4 seconds
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("Error in alerts stream", connection_id=connection_id, error=str(e))
                    break
                    
        finally:
            if connection_id in active_connections:
                del active_connections[connection_id]
            logger.info("Alerts stream ended", connection_id=connection_id)
    
    return StreamingResponse(alerts_stream_generator())

# =================================================================
# USAGE STREAMING ENDPOINTS
# =================================================================

@router.get("/usage/stream/{tenant_id}")
async def stream_usage_updates(
    tenant_id: str,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Stream real-time usage metrics and billing data for a tenant"""
    connection_id = str(uuid.uuid4())
    
    logger.info("Starting usage stream", 
                connection_id=connection_id,
                tenant_id=tenant_id,
                user_id=current_user.id)
    
    async def usage_stream_generator():
        try:
            active_connections[connection_id] = {
                "type": "usage",
                "user_id": current_user.id,
                "tenant_id": tenant_id,
                "started_at": datetime.now()
            }
            
            yield format_sse_message({
                "type": "connection_established",
                "connection_id": connection_id,
                "tenant_id": tenant_id,
                "timestamp": datetime.now().isoformat()
            }, "connection")
            
            while True:
                try:
                    if await request.is_disconnected():
                        break
                    
                    # Generate sample usage data
                    usage_data = await generate_sample_usage_data(tenant_id)
                    if usage_data:
                        yield format_sse_message(usage_data, "usage_update")
                    
                    await asyncio.sleep(6)  # Usage updates every 6 seconds
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("Error in usage stream", connection_id=connection_id, error=str(e))
                    break
                    
        finally:
            if connection_id in active_connections:
                del active_connections[connection_id]
            logger.info("Usage stream ended", connection_id=connection_id)
    
    return StreamingResponse(usage_stream_generator())

# =================================================================
# AI INSIGHTS STREAMING ENDPOINTS
# =================================================================

@router.get("/ai/analysis/{analysis_id}/stream")
async def stream_ai_analysis_results(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Stream real-time AI analysis results and insights"""
    connection_id = str(uuid.uuid4())
    
    logger.info("Starting AI analysis stream", 
                connection_id=connection_id,
                analysis_id=analysis_id,
                user_id=current_user.id)
    
    async def ai_stream_generator():
        try:
            active_connections[connection_id] = {
                "type": "ai_analysis",
                "user_id": current_user.id,
                "analysis_id": analysis_id,
                "started_at": datetime.now()
            }
            
            yield format_sse_message({
                "type": "connection_established",
                "connection_id": connection_id,
                "analysis_id": analysis_id,
                "timestamp": datetime.now().isoformat()
            }, "connection")
            
            # Simulate AI analysis progress
            analysis_steps = [
                {"type": "progress", "step": "data_collection", "progress": 20},
                {"type": "progress", "step": "pattern_analysis", "progress": 40},
                {"type": "progress", "step": "anomaly_detection", "progress": 60},
                {"type": "progress", "step": "root_cause_analysis", "progress": 80},
                {"type": "insight", "step": "insights_generation", "progress": 90},
                {"type": "result", "step": "complete", "progress": 100},
            ]
            
            for step in analysis_steps:
                try:
                    if await request.is_disconnected():
                        break
                    
                    ai_result = await generate_sample_ai_result(analysis_id, step)
                    if ai_result:
                        yield format_sse_message(ai_result, "ai_result")
                    
                    await asyncio.sleep(3)  # Each step takes ~3 seconds
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("Error in AI stream", connection_id=connection_id, error=str(e))
                    break
            
            # Send completion message
            yield format_sse_message({
                "type": "completed",
                "analysis_id": analysis_id,
                "timestamp": datetime.now().isoformat()
            }, "completion")
                    
        finally:
            if connection_id in active_connections:
                del active_connections[connection_id]
            logger.info("AI analysis stream ended", connection_id=connection_id)
    
    return StreamingResponse(ai_stream_generator())

# =================================================================
# SAMPLE DATA GENERATORS (Replace with real service calls)
# =================================================================

async def generate_sample_metric(metric_name: str, timestamp: datetime) -> Dict[str, Any]:
    """Generate sample metric data"""
    import random
    
    base_values = {
        "http_request_duration_milliseconds": lambda: random.uniform(50, 500),
        "http_requests_total": lambda: random.randint(100, 1000),
        "cpu_usage_percent": lambda: random.uniform(10, 90),
        "memory_usage_percent": lambda: random.uniform(20, 80),
        "disk_io_bytes": lambda: random.randint(1000, 100000),
        "network_throughput_bytes": lambda: random.randint(5000, 500000),
    }
    
    value_generator = base_values.get(metric_name, lambda: random.uniform(0, 100))
    
    return {
        "metric_name": metric_name,
        "value": value_generator(),
        "timestamp": timestamp.isoformat(),
        "labels": {
            "service_name": random.choice(["api-gateway", "user-service", "auth-service", "data-processor"]),
            "environment": "production",
            "instance": f"server-{random.randint(1, 5)}"
        }
    }

async def generate_sample_trace(min_duration: int, status_filters: List[str]) -> Optional[Dict[str, Any]]:
    """Generate sample trace data"""
    import random
    
    if random.random() < 0.3:  # 30% chance of generating a trace
        status = random.choice(status_filters)
        duration = random.randint(min_duration, min_duration * 10)
        
        return {
            "trace_id": str(uuid.uuid4()),
            "service_name": random.choice(["api-gateway", "user-service", "payment-service"]),
            "operation_name": random.choice(["GET /users", "POST /payment", "GET /orders"]),
            "start_time": datetime.now().isoformat(),
            "duration": duration,
            "status": status,
            "span_count": random.randint(3, 15),
            "tags": {
                "http.method": random.choice(["GET", "POST", "PUT"]),
                "http.status_code": random.choice([200, 404, 500]) if status == "error" else 200
            }
        }
    return None

async def generate_sample_security_event(severity_filters: List[str]) -> Optional[Dict[str, Any]]:
    """Generate sample security event"""
    import random
    
    if random.random() < 0.2:  # 20% chance of generating a security event
        event_types = [
            "Brute Force Attack Detected",
            "Suspicious PowerShell Execution",
            "Unusual Network Traffic Pattern",
            "Failed Authentication Spike",
            "Privilege Escalation Attempt"
        ]
        
        mitre_techniques = ["T1110", "T1059", "T1041", "T1078", "T1068"]
        
        return {
            "id": str(uuid.uuid4()),
            "rule_name": random.choice(event_types),
            "severity": random.choice(severity_filters),
            "description": f"Security event detected: {random.choice(event_types)}",
            "timestamp": datetime.now().isoformat(),
            "mitre_technique": random.choice(mitre_techniques),
            "source_ip": f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}",
            "target_ip": f"10.0.{random.randint(1, 255)}.{random.randint(1, 255)}",
            "rule_id": f"sigma-{random.randint(1000, 9999)}"
        }
    return None

async def generate_sample_alert_event(severity_filters: List[str]) -> Optional[Dict[str, Any]]:
    """Generate sample alert event"""
    import random
    
    if random.random() < 0.25:  # 25% chance of generating an alert
        alert_types = [
            "High CPU Usage Alert",
            "Memory Threshold Exceeded",
            "Disk Space Critical",
            "Error Rate Spike",
            "Response Time Degradation"
        ]
        
        return {
            "id": str(uuid.uuid4()),
            "rule_name": random.choice(alert_types),
            "severity": random.choice(severity_filters),
            "message": f"Alert triggered: {random.choice(alert_types)}",
            "triggered_at": datetime.now().isoformat(),
            "rule_id": f"alert-{random.randint(1000, 9999)}",
            "condition": "threshold_exceeded",
            "threshold": random.uniform(70, 95),
            "current_value": random.uniform(75, 100)
        }
    return None

async def generate_sample_usage_data(tenant_id: str) -> Optional[Dict[str, Any]]:
    """Generate sample usage data"""
    import random
    
    metric_types = ["data_ingestion_gb", "api_calls_count", "storage_used_gb", "alerts_triggered"]
    
    return {
        "tenant_id": tenant_id,
        "metric_type": random.choice(metric_types),
        "current_value": random.uniform(100, 10000),
        "timestamp": datetime.now().isoformat(),
        "billing_period": datetime.now().strftime("%Y-%m"),
        "rate_limit_status": "within_limits" if random.random() > 0.1 else "approaching_limit"
    }

async def generate_sample_ai_result(analysis_id: str, step: Dict[str, Any]) -> Dict[str, Any]:
    """Generate sample AI analysis result"""
    import random
    
    if step["type"] == "progress":
        return {
            "type": "progress",
            "analysis_id": analysis_id,
            "data": {
                "step": step["step"],
                "progress": step["progress"],
                "message": f"Processing {step['step'].replace('_', ' ')}...",
                "timestamp": datetime.now().isoformat()
            }
        }
    elif step["type"] == "insight":
        insights = [
            "Detected unusual pattern in authentication logs",
            "Identified potential performance bottleneck in API gateway",
            "Found correlation between network spikes and error rates"
        ]
        return {
            "type": "insight",
            "analysis_id": analysis_id,
            "data": {
                "finding": random.choice(insights),
                "confidence": random.uniform(0.7, 0.95),
                "category": random.choice(["security", "performance", "reliability"]),
                "timestamp": datetime.now().isoformat()
            }
        }
    elif step["type"] == "result":
        return {
            "type": "result",
            "analysis_id": analysis_id,
            "data": {
                "result": "Analysis completed successfully",
                "insights_count": random.randint(3, 8),
                "recommendations": random.randint(2, 5),
                "confidence": random.uniform(0.8, 0.95),
                "timestamp": datetime.now().isoformat()
            }
        }

# =================================================================
# STREAMING MANAGEMENT ENDPOINTS
# =================================================================

@router.get("/streaming/connections")
async def get_active_connections(current_user: User = Depends(get_current_user)):
    """Get information about active streaming connections"""
    user_connections = {
        conn_id: info for conn_id, info in active_connections.items()
        if info["user_id"] == current_user.id
    }
    
    return {
        "active_connections": len(user_connections),
        "connections": user_connections,
        "total_system_connections": len(active_connections)
    }

@router.delete("/streaming/connections/{connection_id}")
async def close_streaming_connection(
    connection_id: str,
    current_user: User = Depends(get_current_user)
):
    """Close a specific streaming connection"""
    if connection_id not in active_connections:
        raise HTTPException(404, "Connection not found")
    
    connection_info = active_connections[connection_id]
    if connection_info["user_id"] != current_user.id:
        raise HTTPException(403, "Cannot close connection belonging to another user")
    
    del active_connections[connection_id]
    logger.info("Streaming connection closed by user", 
                connection_id=connection_id, 
                user_id=current_user.id)
    
    return {"message": "Connection closed successfully", "connection_id": connection_id}