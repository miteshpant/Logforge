"""
M5 Observability API - OpenTelemetry Traces & Metrics Endpoints
Multi-tenant APM capabilities with database-backed service/dao pattern
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Header, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, ValidationError
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union
import structlog
import json
import uuid
import asyncio
from dataclasses import asdict
from enum import Enum

from services.observability_service import ObservabilityService
from tenant_dependencies import MiddlewareTenant

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
    model_config = {"extra": "allow"}  # Allow extra fields for custom attributes

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
    """Time series metric ingestion request - validation only, no field modification"""
    model_config = {"extra": "allow"}  # Allow extra fields for custom attributes

    # Core required fields for validation only
    metric_name: Optional[str] = Field(default=None, description="Metric name")
    metric_type: Optional[MetricType] = Field(default=None, description="Metric type")
    value: Union[int, float] = Field(..., description="Metric value")
    timestamp: Optional[datetime] = Field(default=None, description="Metric timestamp")

    # Optional fields - no defaults added, let normalizer handle field mapping
    # labels: will be mapped from properties/tags/attributes/etc by normalizer
    # service_name: will be mapped from serviceName/service.name/etc by normalizer
    # resource: will be mapped from various resource fields by normalizer


class BatchMetricRequest(BaseModel):
    """Batch metric ingestion request"""
    metrics: List[MetricRequest] = Field(..., description="List of metrics to ingest")


class TraceQueryRequest(BaseModel):
    model_config = {"extra": "allow"}  # Allow extra fields for custom attributes
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
    aggregation: Optional[str] = Field(None, description="Aggregation function (avg, sum, max, min, count)")
    granularity: str = Field("1m", description="Time granularity (1m, 5m, 1h)")


# Use proper authentication middleware instead of simple header dependency


@router.post("/traces/ingest")
async def ingest_trace_spans(
    request: BatchSpanRequest,
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Ingest OpenTelemetry trace spans asynchronously via events"""
    try:
        # Import here to avoid circular dependencies
        from events.publishers.observability_publisher import ObservabilityEventPublisher
        from dependencies import get_event_publisher_manager
        import uuid
        from datetime import datetime, timezone

        start_time = datetime.now(timezone.utc)

        # Convert span requests to dict format preserving ALL original fields
        spans_data = []
        conversion_errors = []

        if not request.spans:
            return JSONResponse(
                status_code=400,
                content={
                    "message": "No valid spans to process",
                    "spans_ingested": 0,
                    "customer_id": customer_id,
                    "errors": conversion_errors
                }
            )

        # Calculate processing time for API response
        processing_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        # Create batch info for event
        batch_info = {
            "batch_id": str(uuid.uuid4()),
            "timestamp": start_time.isoformat(),
            "success_count": len(request.spans),
            "error_count": len(conversion_errors),
            "bytes_processed": len(str(request.dict()))  # Approximate
        }

        # Get the initialized event publisher manager
        publisher_manager = get_event_publisher_manager()
        if not publisher_manager:
            return JSONResponse(
                status_code=500,
                content={
                    "message": "Event publisher not available",
                    "spans_ingested": 0,
                    "customer_id": customer_id,
                    "errors": ["Event system not initialized"]
                }
            )

        # Initialize event publisher
        observability_publisher = ObservabilityEventPublisher(publisher_manager)

        # Publish traces batch ingestion event
        event_published = await observability_publisher.publish_traces_batch_ingested(
            customer_id=customer_id,
            batch_info=batch_info,
            spans_data=request.spans,
            processing_time_ms=processing_time_ms
        )

        if event_published:
            return JSONResponse(
                status_code=202,  # Accepted - will be processed asynchronously
                content={
                    "message": "Traces accepted for processing",
                    "spans_accepted": len(request.spans),
                    "customer_id": customer_id,
                    "batch_id": batch_info["batch_id"],
                    "processing_status": "queued",
                    "errors": conversion_errors
                }
            )
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "message": "Failed to queue traces for processing",
                    "spans_ingested": 0,
                    "customer_id": customer_id,
                    "errors": conversion_errors + ["Event publishing failed"]
                }
            )

    except Exception as e:
        logger.error("Failed to queue traces for processing", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to queue traces for processing: {str(e)}")


@router.post("/metrics/ingest")
async def ingest_metrics(
    request: BatchMetricRequest,
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Ingest time series metrics asynchronously via events"""
    try:
        # Import here to avoid circular dependencies
        from events.publishers.observability_publisher import ObservabilityEventPublisher
        from dependencies import get_event_publisher_manager
        import uuid
        from datetime import datetime, timezone

        start_time = datetime.now(timezone.utc)

        if not request.metrics:
            return JSONResponse(
                status_code=400,
                content={
                    "message": "No valid metrics to process",
                    "metrics_ingested": 0,
                    "customer_id": customer_id,
                    "errors": []
                }
            )

        # Calculate processing time for API response
        processing_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        # Create batch info for event
        batch_info = {
            "batch_id": str(uuid.uuid4()),
            "timestamp": start_time.isoformat(),
            "success_count": len(request.metrics),
            "error_count": 0,
            "bytes_processed": len(str(request.dict()))  # Approximate
        }

        # Get the initialized event publisher manager
        publisher_manager = get_event_publisher_manager()
        if not publisher_manager:
            return JSONResponse(
                status_code=500,
                content={
                    "message": "Event publisher not available",
                    "metrics_ingested": 0,
                    "customer_id": customer_id,
                    "errors": ["Event system not initialized"]
                }
            )

        # Initialize event publisher
        observability_publisher = ObservabilityEventPublisher(publisher_manager)

        # Publish metrics batch ingestion event
        event_published = await observability_publisher.publish_metrics_batch_ingested(
            customer_id=customer_id,
            batch_info=batch_info,
            metrics_data=request.metrics,
            processing_time_ms=processing_time_ms
        )

        if event_published:
            return JSONResponse(
                status_code=202,  # Accepted - will be processed asynchronously
                content={
                    "message": "Metrics accepted for processing",
                    "metrics_accepted": len(request.metrics),
                    "customer_id": customer_id,
                    "batch_id": batch_info["batch_id"],
                    "processing_status": "queued",
                    "errors": []
                }
            )
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "message": "Failed to queue metrics for processing",
                    "metrics_ingested": 0,
                    "customer_id": customer_id,
                    "errors": ["Event publishing failed"]
                }
            )

    except Exception as e:
        logger.error("Failed to queue metrics for processing", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to queue metrics for processing: {str(e)}")


@router.post("/traces/search")
async def search_traces(
    query: TraceQueryRequest,
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Search traces with filters - supports both normalized and customer field variations"""
    try:
        # Import field normalizer
        from services.simple_otel_mapper import normalize_otel_service_simple
        
        observability_service = ObservabilityService()

        # Convert query to dict and normalize field names to handle customer variations
        query_dict = query.dict(exclude_none=True)  # Only include non-None values
        normalized_query = normalize_otel_service_simple(query_dict)
        
        # Build filters dict using normalized field names
        filters = {}

        # Use normalized fields (supports serviceName -> service_name, etc.)
        if normalized_query.get('service_name') or query.service_name:
            filters['service_name'] = normalized_query.get('service_name') or query.service_name

        if normalized_query.get('operation_name') or query.operation_name:
            filters['operation_name'] = normalized_query.get('operation_name') or query.operation_name

        if normalized_query.get('start_time') or query.start_time:
            filters['start_time'] = normalized_query.get('start_time') or query.start_time

        if normalized_query.get('end_time') or query.end_time:
            filters['end_time'] = normalized_query.get('end_time') or query.end_time

        if normalized_query.get('min_duration_ms') or query.min_duration_ms:
            filters['min_duration_ms'] = normalized_query.get('min_duration_ms') or query.min_duration_ms

        if normalized_query.get('max_duration_ms') or query.max_duration_ms:
            filters['max_duration_ms'] = normalized_query.get('max_duration_ms') or query.max_duration_ms

        # Handle status field (might be mapped from result/outcome/etc.)
        status_value = normalized_query.get('status') or (query.status.value if query.status else None)
        if status_value:
            filters['status'] = status_value

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
    customer_id: str = Header(..., alias="X-Customer-ID")
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
    customer_id: str = Header(..., alias="X-Customer-ID")
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


@router.get("/service-metrics-summary")
async def get_service_metrics_summary(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """
    Get aggregated service metrics summary - optimized endpoint for dashboards.

    Returns pre-calculated totals from ClickHouse aggregation instead of fetching
    all services and aggregating in the application layer.

    Much faster than /service-map when you only need totals for widgets.

    Response:
    {
        "total_errors": 87,
        "total_requests": 435,
        "error_rate_percent": 20.0,
        "avg_response_time_ms": 45.0,
        "total_services": 5,
        "active_services": 3
    }
    """
    try:
        observability_service = ObservabilityService()

        summary = await observability_service.get_service_metrics_summary(customer_id)

        return summary

    except Exception as e:
        logger.error("Failed to get service metrics summary", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get service metrics summary: {str(e)}")


@router.get("/apm/overview/stats")
async def get_apm_overview_stats(
    start_time: Optional[str] = Query(None, description="Start time in ISO format"),
    end_time: Optional[str] = Query(None, description="End time in ISO format"),
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get APM overview statistics for centrum dashboard widgets"""
    try:
        observability_service = ObservabilityService()

        # Calculate hours from time range or default to 24h
        if start_time and end_time:
            from dateutil import parser
            start_dt = parser.isoparse(start_time)
            end_dt = parser.isoparse(end_time)
            hours = max(1, (end_dt - start_dt).total_seconds() / 3600)
        else:
            hours = 24

        overview = await observability_service.get_apm_overview(customer_id, int(hours))

        # Extract key metrics for widgets
        return {
            "avg_response_time": {
                "value_ms": round(overview.get('avg_response_time', 0), 2),
                "p95_ms": round(sum(s.get('p95_response_time', 0) for s in overview.get('services', [])) / max(1, len(overview.get('services', []))), 2),
                "p99_ms": round(sum(s.get('p99_response_time', 0) for s in overview.get('services', [])) / max(1, len(overview.get('services', []))), 2)
            },
            "error_rate": {
                "percentage": round(overview.get('error_rate', 0), 2),
                "total_errors": overview.get('total_errors', 0),
                "total_requests": overview.get('total_requests', 0)
            },
            "throughput": {
                "requests_per_second": round(overview.get('total_requests', 0) / (hours * 3600), 2),
                "requests_per_minute": round(overview.get('total_requests', 0) / (hours * 60), 2),
                "total_requests": overview.get('total_requests', 0)
            },
            "slowest_services": sorted(
                [
                    {
                        "service_name": s.get('service_name', 'unknown'),
                        "avg_response_time_ms": round(s.get('avg_response_time', 0), 2)
                    }
                    for s in overview.get('services', [])
                ],
                key=lambda x: x['avg_response_time_ms'],
                reverse=True
            )[:3]
        }

    except Exception as e:
        logger.error("Failed to get APM overview stats", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get APM overview stats: {str(e)}")


@router.get("/apm/overview")
async def get_apm_overview(
    time_range_hours: int = 24,
    customer_id: str = Header(..., alias="X-Customer-ID")
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


@router.get("/apm/services")
async def get_apm_services(
    start_time: Optional[str] = Query(None, description="Start time in ISO format"),
    end_time: Optional[str] = Query(None, description="End time in ISO format"),
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get APM metrics for all services"""
    try:
        from dao.observability_dao import ObservabilityDAO
        from dateutil import parser

        dao = ObservabilityDAO()

        # Parse time range
        if start_time and end_time:
            start_dt = parser.isoparse(start_time)
            end_dt = parser.isoparse(end_time)
        else:
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(hours=24)

        services = await dao.get_service_performance(customer_id, start_dt, end_dt)

        return {
            "services": services,
            "customer_id": customer_id
        }

    except Exception as e:
        logger.error("Failed to get APM services", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get APM services: {str(e)}")


@router.get("/apm/slowest-endpoints")
async def get_slowest_endpoints(
    start_time: Optional[str] = Query(None, description="Start time in ISO format"),
    end_time: Optional[str] = Query(None, description="End time in ISO format"),
    limit: int = Query(10, description="Number of endpoints to return"),
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get slowest endpoints by average latency"""
    try:
        from dao.observability_dao import ObservabilityDAO
        from dateutil import parser

        dao = ObservabilityDAO()

        # Parse time range
        if start_time and end_time:
            start_dt = parser.isoparse(start_time)
            end_dt = parser.isoparse(end_time)
        else:
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(hours=24)

        endpoints = await dao.get_slowest_endpoints(customer_id, start_dt, end_dt, limit)

        return {
            "endpoints": endpoints,
            "customer_id": customer_id
        }

    except Exception as e:
        logger.error("Failed to get slowest endpoints", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get slowest endpoints: {str(e)}")


@router.get("/apm/error-rates")
async def get_error_rates(
    start_time: Optional[str] = Query(None, description="Start time in ISO format"),
    end_time: Optional[str] = Query(None, description="End time in ISO format"),
    interval: str = Query("5m", description="Time bucket interval (e.g., 5m, 1h)"),
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get error rates over time for each service"""
    try:
        from dao.observability_dao import ObservabilityDAO
        from dateutil import parser

        dao = ObservabilityDAO()

        # Parse time range
        if start_time and end_time:
            start_dt = parser.isoparse(start_time)
            end_dt = parser.isoparse(end_time)
        else:
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(hours=24)

        metrics = await dao.get_error_rates_over_time(customer_id, start_dt, end_dt, interval)

        return {
            "metrics": metrics,
            "customer_id": customer_id
        }

    except Exception as e:
        logger.error("Failed to get error rates", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get error rates: {str(e)}")


@router.get("/apm/transactions")
async def get_transactions(
    start_time: Optional[str] = Query(None, description="Start time in ISO format"),
    end_time: Optional[str] = Query(None, description="End time in ISO format"),
    limit: int = Query(10, description="Number of transactions to return"),
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get top transactions by request count"""
    try:
        from dao.observability_dao import ObservabilityDAO
        from dateutil import parser

        dao = ObservabilityDAO()

        # Parse time range
        if start_time and end_time:
            start_dt = parser.isoparse(start_time)
            end_dt = parser.isoparse(end_time)
        else:
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(hours=24)

        transactions = await dao.get_top_transactions(customer_id, start_dt, end_dt, limit)

        return {
            "transactions": transactions,
            "customer_id": customer_id
        }

    except Exception as e:
        logger.error("Failed to get transactions", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get transactions: {str(e)}")


@router.get("/apm/{service_name}")
async def get_apm_metrics(
    service_name: str,
    time_range_hours: int = 1,
    deployment_environment: Optional[str] = Query(None, description="Deployment environment (production, staging, dev)"),
    namespace: Optional[str] = Query(None, description="Kubernetes namespace"),
    cluster: Optional[str] = Query(None, description="Cluster name"),
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get APM metrics for a specific service with environment context"""
    try:
        observability_service = ObservabilityService()

        # Create service context for environment-aware filtering
        service_context = {
            "service_name": service_name,
            "deployment_environment": deployment_environment,
            "namespace": namespace,
            "cluster": cluster
        }

        metrics = await observability_service.get_service_apm_metrics_with_context(
            service_context, customer_id, time_range_hours
        )

        return {
            "service_name": service_name,
            "deployment_environment": deployment_environment,
            "namespace": namespace,
            "cluster": cluster,
            "metrics": metrics.to_dict(),
            "time_range_hours": time_range_hours,
            "customer_id": customer_id
        }

    except Exception as e:
        logger.error("Failed to get APM metrics", error=str(e), customer_id=customer_id,
                    service_name=service_name, deployment_environment=deployment_environment)
        raise HTTPException(status_code=500, detail=f"Failed to get APM metrics: {str(e)}")


@router.get("/analytics")
async def get_trace_analytics(
    time_range_hours: int = 24,
    customer_id: str = Header(..., alias="X-Customer-ID")
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
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Query time series metrics with aggregation and granularity support"""
    try:
        observability_service = ObservabilityService()

        # If metric_name and granularity are provided, return time series data
        if query.metric_name and query.granularity:
            time_series = await observability_service.get_metric_time_series(
                customer_id=customer_id,
                metric_name=query.metric_name,
                start_time=query.start_time,
                end_time=query.end_time,
                aggregation=query.aggregation or "avg",
                granularity=query.granularity
            )

            if not time_series:
                return {
                    "message": f"No metric data found for '{query.metric_name}' in the specified time range",
                    "metrics": {},
                    "aggregation": query.aggregation,
                    "granularity": query.granularity,
                    "customer_id": customer_id
                }

            return {
                "metrics": {query.metric_name: time_series},
                "aggregation": query.aggregation,
                "granularity": query.granularity,
                "customer_id": customer_id
            }

        # Fallback: Get raw metrics without time bucketing
        hours = max(1, int((query.end_time - query.start_time).total_seconds() / 3600))
        metrics = await observability_service.get_metrics(customer_id, query.metric_name, hours)

        # Group metrics by name
        metrics_data = {}
        for metric in metrics:
            name = metric.get('name', query.metric_name or 'unknown')
            if name not in metrics_data:
                metrics_data[name] = []
            metrics_data[name].append({
                "timestamp": metric.get('timestamp'),
                "value": metric.get('value', 0)
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
    customer_id: str = Header(..., alias="X-Customer-ID"),
    hours: int = Query(1, description="Time range in hours for health calculation", ge=1, le=168)
):
    """Get detailed health status for a service"""
    try:
        observability_service = ObservabilityService()

        health = await observability_service.get_service_health_status(service_name, customer_id, hours)

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
    customer_id: str = Header(..., alias="X-Customer-ID")
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


def format_sse_message(event_type: str, data: Any, event_id: Optional[str] = None) -> str:
    """Format data as Server-Sent Events message"""
    message = ""
    if event_id:
        message += f"id: {event_id}\n"
    message += f"event: {event_type}\n"
    message += f"data: {json.dumps(data)}\n\n"
    return message


@router.get("/metrics/stream")
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


@router.get("/traces/stream")
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


@router.get("/overview/stats")
async def get_observability_overview_stats(
    start_time: str,
    end_time: str,
    customer_id: str = MiddlewareTenant
):
    """
    Get observability overview statistics for centrum page widgets

    Returns aggregated metrics for:
    - Traces (total count, error count)
    - Performance (avg response time, P95/P99 latency)
    - Reliability (error rate, success/failure counts)
    - Services (active service count)
    - Spans (total count, ingestion rate)

    Query params:
    - start_time: ISO format datetime string
    - end_time: ISO format datetime string
    """
    try:
        observability_service = ObservabilityService()

        overview = await observability_service.get_observability_overview_stats(
            customer_id=customer_id,
            start_time=start_time,
            end_time=end_time
        )

        return overview

    except Exception as e:
        logger.error(f"Failed to get observability overview stats: {e}", customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get observability overview stats: {str(e)}")
