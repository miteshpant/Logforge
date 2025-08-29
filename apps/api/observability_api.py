"""
M5 Observability API - OpenTelemetry Traces & Metrics Endpoints
Multi-tenant APM capabilities with trace-log correlation
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

from observability_engine import (
    ObservabilityEngine, TraceSpan, MetricData, SpanKind, SpanStatus, MetricType,
    get_observability_engine
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/observability", tags=["observability"])


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
        observability_engine = get_observability_engine()
        
        # Convert request spans to internal format
        spans = []
        for span_req in request.spans:
            # Calculate duration if not provided
            duration_ms = span_req.duration_ms
            if not duration_ms and span_req.start_time and span_req.end_time:
                duration_ms = int((span_req.end_time - span_req.start_time).total_seconds() * 1000)
            
            span = TraceSpan(
                trace_id=span_req.trace_id,
                span_id=span_req.span_id,
                parent_span_id=span_req.parent_span_id,
                operation_name=span_req.operation_name,
                service_name=span_req.service_name,
                start_time=span_req.start_time,
                end_time=span_req.end_time,
                duration_ms=duration_ms,
                kind=span_req.kind,
                status=span_req.status,
                status_message=span_req.status_message,
                attributes=span_req.attributes,
                events=span_req.events,
                links=span_req.links,
                resource=span_req.resource,
                customer_id=customer_id,
                ingested_at=datetime.utcnow()
            )
            spans.append(span)
        
        # Ingest spans with customer isolation
        result = await observability_engine.ingest_traces(spans)
        
        return JSONResponse(
            status_code=202,
            content={
                "message": "Traces ingested successfully",
                "spans_ingested": result["ingested"],
                "customer_id": customer_id,
                "errors": result.get("errors", [])
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
        observability_engine = get_observability_engine()
        
        # Convert request metrics to internal format
        metrics = []
        for metric_req in request.metrics:
            metric = MetricData(
                metric_name=metric_req.metric_name,
                metric_type=metric_req.metric_type,
                value=metric_req.value,
                timestamp=metric_req.timestamp,
                labels=metric_req.labels,
                service_name=metric_req.service_name,
                resource=metric_req.resource,
                customer_id=customer_id,
                ingested_at=datetime.utcnow()
            )
            metrics.append(metric)
        
        # Ingest metrics with customer isolation
        result = await observability_engine.ingest_metrics(metrics)
        
        return JSONResponse(
            status_code=202,
            content={
                "message": "Metrics ingested successfully",
                "metrics_ingested": result["ingested"],
                "customer_id": customer_id,
                "errors": result.get("errors", [])
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
        observability_engine = get_observability_engine()
        
        # Build ClickHouse query with customer isolation
        where_conditions = ["customer_id = %(customer_id)s"]
        params = {"customer_id": customer_id}
        
        if query.service_name:
            where_conditions.append("service_name = %(service_name)s")
            params["service_name"] = query.service_name
        
        if query.operation_name:
            where_conditions.append("operation_name = %(operation_name)s")
            params["operation_name"] = query.operation_name
        
        if query.start_time:
            where_conditions.append("start_time >= %(start_time)s")
            params["start_time"] = query.start_time
        
        if query.end_time:
            where_conditions.append("start_time <= %(end_time)s")
            params["end_time"] = query.end_time
        
        if query.min_duration_ms:
            where_conditions.append("duration_ms >= %(min_duration)s")
            params["min_duration"] = query.min_duration_ms
        
        if query.max_duration_ms:
            where_conditions.append("duration_ms <= %(max_duration)s")
            params["max_duration"] = query.max_duration_ms
        
        if query.status:
            where_conditions.append("status = %(status)s")
            params["status"] = query.status.value
        
        where_clause = " AND ".join(where_conditions)
        
        search_query = f"""
        SELECT 
            trace_id, span_id, parent_span_id, operation_name, service_name,
            start_time, end_time, duration_ms, kind, status, status_message,
            attributes, events, links, resource
        FROM traces 
        WHERE {where_clause}
        ORDER BY start_time DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """
        
        params["limit"] = query.limit
        params["offset"] = query.offset
        
        result = observability_engine.clickhouse_client.query(search_query, parameters=params)
        
        traces = []
        for row in result.result_rows:
            traces.append({
                "trace_id": row[0],
                "span_id": row[1], 
                "parent_span_id": row[2],
                "operation_name": row[3],
                "service_name": row[4],
                "start_time": row[5],
                "end_time": row[6],
                "duration_ms": row[7],
                "kind": row[8],
                "status": row[9],
                "status_message": row[10],
                "attributes": json.loads(row[11]) if row[11] else {},
                "events": json.loads(row[12]) if row[12] else [],
                "links": json.loads(row[13]) if row[13] else [],
                "resource": json.loads(row[14]) if row[14] else {}
            })
        
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
    """Get detailed trace information including correlated logs"""
    try:
        observability_engine = get_observability_engine()
        
        # Get trace with correlated logs
        result = await observability_engine.correlate_traces_with_logs(trace_id, customer_id)
        
        if not result["traces"]:
            raise HTTPException(status_code=404, detail="Trace not found")
        
        return {
            "trace_id": trace_id,
            "spans": result["traces"],
            "correlated_logs": result["logs"],
            "correlation_info": result["correlation"],
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
        observability_engine = get_observability_engine()
        
        service_map = await observability_engine.get_service_map(customer_id, time_range_hours)
        
        return {
            "services": service_map["services"],
            "dependencies": service_map["dependencies"],
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
        observability_engine = get_observability_engine()
        
        metrics = await observability_engine.get_apm_metrics(customer_id, service_name, time_range_hours)
        
        return {
            "service_name": service_name,
            "metrics": metrics,
            "time_range_hours": time_range_hours,
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to get APM metrics", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get APM metrics: {str(e)}")


@router.post("/metrics/query")
async def query_metrics(
    query: MetricQueryRequest,
    customer_id: str = Depends(get_customer_id)
):
    """Query time series metrics"""
    try:
        observability_engine = get_observability_engine()
        
        # Build ClickHouse query with customer isolation
        where_conditions = ["customer_id = %(customer_id)s"]
        params = {"customer_id": customer_id}
        
        if query.metric_name:
            where_conditions.append("metric_name = %(metric_name)s")
            params["metric_name"] = query.metric_name
        
        if query.service_name:
            where_conditions.append("service_name = %(service_name)s")
            params["service_name"] = query.service_name
        
        if query.start_time:
            where_conditions.append("timestamp >= %(start_time)s")
            params["start_time"] = query.start_time
        
        if query.end_time:
            where_conditions.append("timestamp <= %(end_time)s")
            params["end_time"] = query.end_time
        
        # Handle label filters
        for label_key, label_value in query.labels.items():
            where_conditions.append(f"JSONExtractString(labels, '{label_key}') = %(label_{label_key})s")
            params[f"label_{label_key}"] = label_value
        
        where_clause = " AND ".join(where_conditions)
        
        # Map granularity to ClickHouse intervals
        granularity_map = {
            "1m": "toStartOfMinute",
            "5m": "toStartOfFiveMinutes", 
            "1h": "toStartOfHour",
            "1d": "toDate"
        }
        
        time_func = granularity_map.get(query.granularity, "toStartOfMinute")
        agg_func = query.aggregation.lower()
        
        metrics_query = f"""
        SELECT 
            {time_func}(timestamp) as time_bucket,
            metric_name,
            {agg_func}(value) as aggregated_value
        FROM metrics 
        WHERE {where_clause}
        GROUP BY time_bucket, metric_name
        ORDER BY time_bucket, metric_name
        """
        
        result = observability_engine.clickhouse_client.query(metrics_query, parameters=params)
        
        # Group results by metric name
        metrics_data = {}
        for row in result.result_rows:
            time_bucket, metric_name, value = row
            if metric_name not in metrics_data:
                metrics_data[metric_name] = []
            metrics_data[metric_name].append({
                "timestamp": time_bucket,
                "value": value
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


@router.get("/health")
async def observability_health():
    """Health check for observability engine"""
    try:
        observability_engine = get_observability_engine()
        
        if not observability_engine.clickhouse_client:
            return {"status": "warning", "message": "ClickHouse client not available"}
        
        # Test ClickHouse connectivity
        observability_engine.clickhouse_client.query("SELECT 1")
        
        return {
            "status": "healthy",
            "message": "Observability engine operational",
            "features": [
                "trace_ingestion",
                "metrics_ingestion", 
                "trace_search",
                "service_map",
                "apm_metrics",
                "trace_log_correlation"
            ]
        }
        
    except Exception as e:
        logger.error("Observability health check failed", error=str(e))
        return {"status": "error", "message": f"Health check failed: {str(e)}"}