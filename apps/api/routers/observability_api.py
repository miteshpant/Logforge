"""
M5 Observability API - OpenTelemetry Traces & Metrics Endpoints
Multi-tenant APM capabilities with database-backed service/dao pattern
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union
import structlog
import json
import uuid
from dataclasses import asdict
from enum import Enum

from services.observability_service import ObservabilityService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/observability", tags=["observability"])


# Enums for span status and kind
class SpanKind(str, Enum):
    UNSPECIFIED = "unspecified"
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"

class SpanStatus(str, Enum):
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"

class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


# Pydantic models for API requests/responses
class SpanRequest(BaseModel):
    """OpenTelemetry span ingestion request"""
    trace_id: str = Field(..., description="Unique trace identifier")
    span_id: str = Field(..., description="Unique span identifier") 
    parent_span_id: Optional[str] = Field(None, description="Parent span ID")
    operation_name: str = Field(..., description="Span operation name")
    service_name: str = Field(..., description="Service generating the span")
    start_time: datetime = Field(..., description="Span start timestamp")
    end_time: Optional[datetime] = Field(None, description="Span end timestamp")
    duration_ms: Optional[int] = Field(None, description="Span duration in milliseconds")
    kind: SpanKind = Field(SpanKind.INTERNAL, description="Span kind")
    status: SpanStatus = Field(SpanStatus.OK, description="Span status")
    status_message: Optional[str] = Field(None, description="Status description")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Span attributes")
    events: List[Dict[str, Any]] = Field(default_factory=list, description="Span events")
    links: List[Dict[str, Any]] = Field(default_factory=list, description="Span links")
    resource: Dict[str, Any] = Field(default_factory=dict, description="Resource attributes")


class BatchSpanRequest(BaseModel):
    """Batch span ingestion request"""
    spans: List[SpanRequest] = Field(..., description="List of spans to ingest")
    resource_spans: List[Dict[str, Any]] = Field(default_factory=list, description="OTLP resource spans")


class MetricRequest(BaseModel):
    """Time series metric ingestion request"""
    metric_name: str = Field(..., description="Metric name")
    metric_type: MetricType = Field(..., description="Metric type")
    value: Union[int, float] = Field(..., description="Metric value")
    timestamp: datetime = Field(..., description="Metric timestamp")
    labels: Dict[str, str] = Field(default_factory=dict, description="Metric labels")
    service_name: str = Field(..., description="Service generating the metric")
    resource: Dict[str, Any] = Field(default_factory=dict, description="Resource attributes")


class BatchMetricRequest(BaseModel):
    """Batch metric ingestion request"""
    metrics: List[MetricRequest] = Field(..., description="List of metrics to ingest")


class TraceQueryRequest(BaseModel):
    """Trace search/query request"""
    service_name: Optional[str] = Field(None, description="Filter by service name")
    operation_name: Optional[str] = Field(None, description="Filter by operation name")
    start_time: Optional[datetime] = Field(None, description="Start time filter")
    end_time: Optional[datetime] = Field(None, description="End time filter")
    min_duration_ms: Optional[int] = Field(None, description="Minimum duration filter")
    max_duration_ms: Optional[int] = Field(None, description="Maximum duration filter")
    status: Optional[SpanStatus] = Field(None, description="Status filter")
    limit: int = Field(100, description="Result limit")
    offset: int = Field(0, description="Result offset")


class MetricQueryRequest(BaseModel):
    """Metric query request"""
    metric_name: Optional[str] = Field(None, description="Metric name filter")
    service_name: Optional[str] = Field(None, description="Service name filter")
    start_time: datetime = Field(..., description="Start time filter (required)")
    end_time: datetime = Field(..., description="End time filter (required)")
    labels: Dict[str, str] = Field(default_factory=dict, description="Label filters")
    aggregation: str = Field("avg", description="Aggregation function (avg, sum, max, min)")
    granularity: str = Field("1m", description="Time granularity (1m, 5m, 1h)")


# Header dependency for customer isolation
async def get_customer_id(x_customer_id: str = Header(..., alias="X-Customer-ID")) -> str:
    """Extract customer ID from request header"""
    if not x_customer_id:
        raise HTTPException(status_code=400, detail="X-Customer-ID header is required")
    return x_customer_id


@router.post("/traces/ingest")
async def ingest_trace_spans(
    request: BatchSpanRequest,
    customer_id: str = Depends(get_customer_id)
):
    """Ingest OpenTelemetry trace spans"""
    try:
        observability_service = ObservabilityService()
        
        # Process each span in the batch
        ingested_spans = []
        errors = []
        
        for span_req in request.spans:
            try:
                # Convert to dict format for service
                span_data = {
                    'trace_id': span_req.trace_id,
                    'span_id': span_req.span_id,
                    'parent_span_id': span_req.parent_span_id,
                    'operation_name': span_req.operation_name,
                    'service_name': span_req.service_name,
                    'start_time': span_req.start_time.isoformat(),
                    'end_time': span_req.end_time.isoformat() if span_req.end_time else None,
                    'kind': span_req.kind.value,
                    'status': span_req.status.value,
                    'attributes': span_req.attributes,
                    'events': span_req.events,
                    'links': span_req.links,
                    'resource': span_req.resource
                }
                
                span_id = await observability_service.ingest_trace_span(span_data, customer_id)
                ingested_spans.append(span_id)
                
            except Exception as e:
                errors.append(f"Failed to ingest span {span_req.span_id}: {str(e)}")
        
        return JSONResponse(
            status_code=202,
            content={
                "message": "Traces ingested successfully",
                "spans_ingested": len(ingested_spans),
                "customer_id": customer_id,
                "errors": errors
            }
        )
        
    except Exception as e:
        logger.error("Failed to ingest traces", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to ingest traces: {str(e)}")


@router.post("/metrics/ingest")
async def ingest_metrics(
    request: BatchMetricRequest,
    customer_id: str = Depends(get_customer_id)
):
    """Ingest time series metrics"""
    try:
        observability_service = ObservabilityService()
        
        # Process each metric in the batch
        ingested_metrics = []
        errors = []
        
        for metric_req in request.metrics:
            try:
                # Convert to dict format for service
                metric_data = {
                    'name': metric_req.metric_name,
                    'type': metric_req.metric_type.value,
                    'value': metric_req.value,
                    'unit': '',
                    'description': '',
                    'attributes': metric_req.labels,
                    'resource': metric_req.resource,
                    'timestamp': metric_req.timestamp.isoformat()
                }
                
                metric_id = await observability_service.ingest_metric(metric_data, customer_id)
                ingested_metrics.append(metric_id)
                
            except Exception as e:
                errors.append(f"Failed to ingest metric {metric_req.metric_name}: {str(e)}")
        
        return JSONResponse(
            status_code=202,
            content={
                "message": "Metrics ingested successfully",
                "metrics_ingested": len(ingested_metrics),
                "customer_id": customer_id,
                "errors": errors
            }
        )
        
    except Exception as e:
        logger.error("Failed to ingest metrics", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to ingest metrics: {str(e)}")


@router.post("/traces/search")
async def search_traces(
    query: TraceQueryRequest,
    customer_id: str = Depends(get_customer_id)
):
    """Search traces with filters"""
    try:
        observability_service = ObservabilityService()
        
        # Build filters dict for service
        filters = {}
        
        if query.service_name:
            filters['service_name'] = query.service_name
        
        if query.operation_name:
            filters['operation_name'] = query.operation_name
        
        if query.start_time:
            filters['start_time'] = query.start_time
        
        if query.end_time:
            filters['end_time'] = query.end_time
        
        if query.min_duration_ms:
            filters['min_duration_ms'] = query.min_duration_ms
        
        if query.max_duration_ms:
            filters['max_duration_ms'] = query.max_duration_ms
        
        if query.status:
            filters['status'] = query.status.value
        
        filters['limit'] = query.limit
        filters['offset'] = query.offset
        
        traces = await observability_service.search_traces(customer_id, filters, query.limit)
        
        return {
            "traces": traces,
            "total": len(traces),
            "limit": query.limit,
            "offset": query.offset,
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to search traces", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to search traces: {str(e)}")


@router.get("/traces/{trace_id}")
async def get_trace_details(
    trace_id: str,
    customer_id: str = Depends(get_customer_id)
):
    """Get detailed trace information"""
    try:
        observability_service = ObservabilityService()
        
        # Get complete trace
        trace = await observability_service.get_trace_by_id(trace_id, customer_id)
        
        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")
        
        return {
            "trace_id": trace_id,
            "trace": trace,
            "customer_id": customer_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get trace details", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get trace details: {str(e)}")


@router.get("/service-map")
async def get_service_map(
    time_range_hours: int = 24,
    customer_id: str = Depends(get_customer_id)
):
    """Get service topology and dependencies"""
    try:
        observability_service = ObservabilityService()
        
        services = await observability_service.get_service_topology(customer_id)
        
        return {
            "services": services,
            "time_range_hours": time_range_hours,
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to get service map", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get service map: {str(e)}")


@router.get("/apm/{service_name}")
async def get_apm_metrics(
    service_name: str,
    time_range_hours: int = 1,
    customer_id: str = Depends(get_customer_id)
):
    """Get APM metrics for a specific service"""
    try:
        observability_service = ObservabilityService()
        
        metrics = await observability_service.get_service_apm_metrics(service_name, customer_id, time_range_hours)
        
        return {
            "service_name": service_name,
            "metrics": asdict(metrics),
            "time_range_hours": time_range_hours,
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to get APM metrics", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get APM metrics: {str(e)}")


@router.get("/apm/overview")
async def get_apm_overview(
    time_range_hours: int = 24,
    customer_id: str = Depends(get_customer_id)
):
    """Get APM overview for all services"""
    try:
        observability_service = ObservabilityService()
        
        overview = await observability_service.get_apm_overview(customer_id, time_range_hours)
        
        return {
            "overview": overview,
            "time_range_hours": time_range_hours,
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to get APM overview", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get APM overview: {str(e)}")


@router.get("/analytics")
async def get_trace_analytics(
    time_range_hours: int = 24,
    customer_id: str = Depends(get_customer_id)
):
    """Get comprehensive trace analytics"""
    try:
        observability_service = ObservabilityService()
        
        analytics = await observability_service.get_trace_analytics(customer_id, time_range_hours)
        
        return {
            "analytics": analytics,
            "time_range_hours": time_range_hours,
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to get trace analytics", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get trace analytics: {str(e)}")


@router.post("/metrics/query")
async def query_metrics(
    query: MetricQueryRequest,
    customer_id: str = Depends(get_customer_id)
):
    """Query time series metrics"""
    try:
        observability_service = ObservabilityService()
        
        # Get basic metrics data
        hours = int((query.end_time - query.start_time).total_seconds() / 3600)
        metrics = await observability_service.get_metrics(customer_id, query.metric_name, hours)
        
        # If aggregation is requested, get aggregated data
        if query.aggregation and query.metric_name:
            aggregated = await observability_service.get_metric_aggregation(
                customer_id, query.metric_name, query.aggregation, hours
            )
            
            return {
                "metrics": {query.metric_name: [aggregated]},
                "aggregation": query.aggregation,
                "granularity": query.granularity,
                "customer_id": customer_id
            }
        
        # Group metrics by name
        metrics_data = {}
        for metric in metrics:
            name = metric['name']
            if name not in metrics_data:
                metrics_data[name] = []
            metrics_data[name].append({
                "timestamp": metric['timestamp'],
                "value": metric['value']
            })
        
        return {
            "metrics": metrics_data,
            "aggregation": query.aggregation,
            "granularity": query.granularity,
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to query metrics", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to query metrics: {str(e)}")


@router.get("/service/{service_name}/health")
async def get_service_health(
    service_name: str,
    customer_id: str = Depends(get_customer_id)
):
    """Get detailed health status for a service"""
    try:
        observability_service = ObservabilityService()
        
        health = await observability_service.get_service_health_status(service_name, customer_id)
        
        return {
            "service_name": service_name,
            "health": health,
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to get service health", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get service health: {str(e)}")


@router.get("/trends")
async def get_performance_trends(
    days: int = 7,
    customer_id: str = Depends(get_customer_id)
):
    """Get performance trends over time"""
    try:
        observability_service = ObservabilityService()
        
        trends = await observability_service.get_performance_trends(customer_id, days)
        
        return {
            "trends": trends,
            "days": days,
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to get performance trends", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get performance trends: {str(e)}")


@router.get("/health")
async def observability_health():
    """Health check for observability service"""
    try:
        observability_service = ObservabilityService()
        
        # Test database connectivity through service
        test_customer = "health-check-test"
        await observability_service.get_metrics(test_customer, limit=1, hours=1)
        
        return {
            "status": "healthy",
            "message": "Observability service operational",
            "features": [
                "trace_ingestion",
                "metrics_ingestion", 
                "trace_search",
                "service_map",
                "apm_metrics",
                "apm_overview",
                "trace_analytics",
                "service_health",
                "performance_trends"
            ]
        }
        
    except Exception as e:
        logger.error("Observability health check failed", error=str(e))
        return {"status": "error", "message": f"Health check failed: {str(e)}"}