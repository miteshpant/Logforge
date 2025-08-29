"""
M5 Observability Engine - OpenTelemetry Traces & Metrics
Full APM capabilities with tenant isolation and correlation
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Literal
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
from pydantic import BaseModel, Field

# Import ClickHouse for storage
import clickhouse_connect

logger = structlog.get_logger(__name__)


class SpanKind(str, Enum):
    """OpenTelemetry span kinds"""
    UNSPECIFIED = "unspecified"
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(str, Enum):
    """Span status codes"""
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


class MetricType(str, Enum):
    """Metric data types"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class TraceSpan:
    """OpenTelemetry trace span"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation_name: str
    service_name: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: Optional[int]
    kind: SpanKind
    status: SpanStatus
    status_message: Optional[str]
    attributes: Dict[str, Any]
    events: List[Dict[str, Any]]
    links: List[Dict[str, Any]]
    resource: Dict[str, Any]
    customer_id: str
    ingested_at: datetime


@dataclass 
class MetricData:
    """Time series metric data point"""
    metric_name: str
    metric_type: MetricType
    value: Union[int, float]
    timestamp: datetime
    labels: Dict[str, str]
    service_name: str
    resource: Dict[str, Any]
    customer_id: str
    ingested_at: datetime


class ServiceMap:
    """Service topology and dependency mapping"""
    
    def __init__(self):
        self.services: Dict[str, Dict] = {}
        self.dependencies: List[Dict] = []
    
    def update_from_spans(self, spans: List[TraceSpan], customer_id: str):
        """Update service map from trace spans"""
        for span in spans:
            # Update service info
            service_key = f"{customer_id}:{span.service_name}"
            if service_key not in self.services:
                self.services[service_key] = {
                    'name': span.service_name,
                    'customer_id': customer_id,
                    'operations': set(),
                    'error_rate': 0.0,
                    'avg_latency_ms': 0.0,
                    'request_count': 0
                }
            
            self.services[service_key]['operations'].add(span.operation_name)
            
            # Track dependencies from parent-child relationships
            if span.parent_span_id:
                # Find parent span to establish service dependency
                parent_spans = [s for s in spans if s.span_id == span.parent_span_id]
                if parent_spans:
                    parent_span = parent_spans[0]
                    if parent_span.service_name != span.service_name:
                        dependency = {
                            'from_service': parent_span.service_name,
                            'to_service': span.service_name,
                            'customer_id': customer_id,
                            'call_count': 1,
                            'avg_latency_ms': span.duration_ms or 0
                        }
                        self.dependencies.append(dependency)


class ObservabilityEngine:
    """Core engine for traces and metrics processing"""
    
    def __init__(self, clickhouse_client=None):
        self.clickhouse_client = clickhouse_client
        self.service_map = ServiceMap()
        
        # Initialize ClickHouse tables for observability data
        self._init_observability_tables()
    
    def _init_observability_tables(self):
        """Initialize ClickHouse tables for traces and metrics"""
        if not self.clickhouse_client:
            return
            
        try:
            # Create traces table
            traces_table = """
            CREATE TABLE IF NOT EXISTS traces (
                trace_id String,
                span_id String,
                parent_span_id String,
                operation_name LowCardinality(String),
                service_name LowCardinality(String),
                start_time DateTime64(3, 'UTC'),
                end_time DateTime64(3, 'UTC'),
                duration_ms UInt32,
                kind LowCardinality(String),
                status LowCardinality(String),
                status_message String,
                attributes String,
                events String,
                links String,
                resource String,
                customer_id LowCardinality(String),
                ingested_at DateTime64(3, 'UTC')
            ) ENGINE = MergeTree()
            PARTITION BY (customer_id, toYYYYMM(start_time))
            ORDER BY (customer_id, service_name, start_time, trace_id, span_id)
            TTL toDateTime(start_time) + INTERVAL 30 DAY DELETE
            """
            
            # Create metrics table
            metrics_table = """
            CREATE TABLE IF NOT EXISTS metrics (
                metric_name LowCardinality(String),
                metric_type LowCardinality(String),
                value Float64,
                timestamp DateTime64(3, 'UTC'),
                labels String,
                service_name LowCardinality(String),
                resource String,
                customer_id LowCardinality(String),
                ingested_at DateTime64(3, 'UTC')
            ) ENGINE = MergeTree()
            PARTITION BY (customer_id, toYYYYMM(timestamp))
            ORDER BY (customer_id, service_name, metric_name, timestamp)
            TTL toDateTime(timestamp) + INTERVAL 90 DAY DELETE
            """
            
            # Create service map table
            service_map_table = """
            CREATE TABLE IF NOT EXISTS service_map (
                from_service LowCardinality(String),
                to_service LowCardinality(String),
                customer_id LowCardinality(String),
                call_count UInt64,
                avg_latency_ms Float64,
                error_rate Float64,
                last_seen DateTime64(3, 'UTC')
            ) ENGINE = ReplacingMergeTree(last_seen)
            PARTITION BY customer_id
            ORDER BY (customer_id, from_service, to_service)
            """
            
            self.clickhouse_client.command(traces_table)
            self.clickhouse_client.command(metrics_table)
            self.clickhouse_client.command(service_map_table)
            
            logger.info("Observability tables initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize observability tables", error=str(e))
    
    async def ingest_traces(self, spans: List[TraceSpan]) -> Dict[str, Any]:
        """Ingest OpenTelemetry trace spans with customer isolation"""
        try:
            if not spans:
                return {"ingested": 0, "errors": []}
            
            # Group spans by customer for isolation
            spans_by_customer = {}
            for span in spans:
                customer_id = span.customer_id
                if customer_id not in spans_by_customer:
                    spans_by_customer[customer_id] = []
                spans_by_customer[customer_id].append(span)
            
            total_ingested = 0
            errors = []
            
            # Process spans per customer
            for customer_id, customer_spans in spans_by_customer.items():
                try:
                    # Update service map
                    self.service_map.update_from_spans(customer_spans, customer_id)
                    
                    # Prepare data for ClickHouse
                    rows = []
                    for span in customer_spans:
                        row = [
                            span.trace_id,
                            span.span_id,
                            span.parent_span_id or '',
                            span.operation_name,
                            span.service_name,
                            span.start_time,
                            span.end_time or span.start_time,
                            span.duration_ms or 0,
                            span.kind.value,
                            span.status.value,
                            span.status_message or '',
                            json.dumps(span.attributes),
                            json.dumps(span.events),
                            json.dumps(span.links),
                            json.dumps(span.resource),
                            span.customer_id,
                            span.ingested_at
                        ]
                        rows.append(row)
                    
                    # Insert into ClickHouse
                    if self.clickhouse_client and rows:
                        self.clickhouse_client.insert('traces', rows)
                        total_ingested += len(rows)
                        
                        logger.info(
                            "Traces ingested successfully",
                            customer_id=customer_id,
                            count=len(rows)
                        )
                
                except Exception as e:
                    error_msg = f"Failed to ingest traces for customer {customer_id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg, customer_id=customer_id)
            
            return {
                "ingested": total_ingested,
                "errors": errors,
                "customers_processed": len(spans_by_customer)
            }
            
        except Exception as e:
            logger.error("Failed to ingest traces", error=str(e))
            return {"ingested": 0, "errors": [str(e)]}
    
    async def ingest_metrics(self, metrics: List[MetricData]) -> Dict[str, Any]:
        """Ingest time series metrics with customer isolation"""
        try:
            if not metrics:
                return {"ingested": 0, "errors": []}
            
            # Group metrics by customer
            metrics_by_customer = {}
            for metric in metrics:
                customer_id = metric.customer_id
                if customer_id not in metrics_by_customer:
                    metrics_by_customer[customer_id] = []
                metrics_by_customer[customer_id].append(metric)
            
            total_ingested = 0
            errors = []
            
            # Process metrics per customer
            for customer_id, customer_metrics in metrics_by_customer.items():
                try:
                    # Prepare data for ClickHouse
                    rows = []
                    for metric in customer_metrics:
                        row = [
                            metric.metric_name,
                            metric.metric_type.value,
                            metric.value,
                            metric.timestamp,
                            json.dumps(metric.labels),
                            metric.service_name,
                            json.dumps(metric.resource),
                            metric.customer_id,
                            metric.ingested_at
                        ]
                        rows.append(row)
                    
                    # Insert into ClickHouse
                    if self.clickhouse_client and rows:
                        self.clickhouse_client.insert('metrics', rows)
                        total_ingested += len(rows)
                        
                        logger.info(
                            "Metrics ingested successfully",
                            customer_id=customer_id,
                            count=len(rows)
                        )
                
                except Exception as e:
                    error_msg = f"Failed to ingest metrics for customer {customer_id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg, customer_id=customer_id)
            
            return {
                "ingested": total_ingested,
                "errors": errors,
                "customers_processed": len(metrics_by_customer)
            }
            
        except Exception as e:
            logger.error("Failed to ingest metrics", error=str(e))
            return {"ingested": 0, "errors": [str(e)]}
    
    async def correlate_traces_with_logs(self, trace_id: str, customer_id: str) -> Dict[str, Any]:
        """Correlate traces with logs using trace_id"""
        try:
            if not self.clickhouse_client:
                return {"traces": [], "logs": [], "correlation": {}}
            
            # Get trace spans
            traces_query = """
            SELECT * FROM traces 
            WHERE customer_id = %(customer_id)s 
            AND trace_id = %(trace_id)s
            ORDER BY start_time
            """
            
            # Get correlated logs (using multi-tenant table)
            logs_query = """
            SELECT * FROM logs_raw_mt 
            WHERE customer_id = %(customer_id)s 
            AND trace_id = %(trace_id)s
            ORDER BY ts
            """
            
            traces_result = self.clickhouse_client.query(
                traces_query,
                parameters={'customer_id': customer_id, 'trace_id': trace_id}
            )
            
            logs_result = self.clickhouse_client.query(
                logs_query,
                parameters={'customer_id': customer_id, 'trace_id': trace_id}
            )
            
            traces = traces_result.result_rows if traces_result else []
            logs = logs_result.result_rows if logs_result else []
            
            # Build correlation timeline
            correlation = {
                "trace_duration_ms": 0,
                "total_spans": len(traces),
                "total_logs": len(logs),
                "services_involved": list(set([t[4] for t in traces])),
                "error_spans": len([t for t in traces if t[9] == 'error']),
                "timeline": []
            }
            
            if traces:
                start_time = min([t[5] for t in traces])
                end_time = max([t[6] for t in traces])
                correlation["trace_duration_ms"] = int((end_time - start_time).total_seconds() * 1000)
            
            return {
                "traces": traces,
                "logs": logs,
                "correlation": correlation
            }
            
        except Exception as e:
            logger.error("Failed to correlate traces with logs", error=str(e))
            return {"traces": [], "logs": [], "correlation": {}}
    
    async def get_service_map(self, customer_id: str, time_range_hours: int = 24) -> Dict[str, Any]:
        """Get service topology and dependencies for customer"""
        try:
            if not self.clickhouse_client:
                return {"services": [], "dependencies": []}
            
            # Get service statistics
            services_query = """
            SELECT 
                service_name,
                count(*) as total_spans,
                avg(duration_ms) as avg_latency_ms,
                sum(case when status = 'error' then 1 else 0 end) / count(*) as error_rate,
                uniq(operation_name) as operation_count
            FROM traces 
            WHERE customer_id = %(customer_id)s 
            AND start_time >= now() - INTERVAL %(hours)s HOUR
            GROUP BY service_name
            """
            
            # Get service dependencies
            dependencies_query = """
            SELECT 
                t1.service_name as from_service,
                t2.service_name as to_service,
                count(*) as call_count,
                avg(t2.duration_ms) as avg_latency_ms
            FROM traces t1
            JOIN traces t2 ON t1.trace_id = t2.trace_id 
                AND t1.span_id = t2.parent_span_id
            WHERE t1.customer_id = %(customer_id)s 
            AND t1.start_time >= now() - INTERVAL %(hours)s HOUR
            AND t1.service_name != t2.service_name
            GROUP BY t1.service_name, t2.service_name
            """
            
            services_result = self.clickhouse_client.query(
                services_query,
                parameters={'customer_id': customer_id, 'hours': time_range_hours}
            )
            
            dependencies_result = self.clickhouse_client.query(
                dependencies_query,
                parameters={'customer_id': customer_id, 'hours': time_range_hours}
            )
            
            # Helper function to handle NaN/infinity values
            def safe_float(val):
                import math
                if val is None or math.isnan(val) or math.isinf(val):
                    return 0.0
                return float(val)
            
            services = []
            for row in services_result.result_rows:
                services.append({
                    'name': row[0],
                    'total_spans': row[1],
                    'avg_latency_ms': round(safe_float(row[2]), 2),
                    'error_rate': round(safe_float(row[3]) * 100, 2),
                    'operation_count': row[4]
                })
            
            dependencies = []
            for row in dependencies_result.result_rows:
                dependencies.append({
                    'from_service': row[0],
                    'to_service': row[1],
                    'call_count': row[2],
                    'avg_latency_ms': round(safe_float(row[3]), 2)
                })
            
            return {
                "services": services,
                "dependencies": dependencies,
                "time_range_hours": time_range_hours
            }
            
        except Exception as e:
            logger.error("Failed to get service map", error=str(e))
            return {"services": [], "dependencies": []}
    
    async def get_apm_metrics(self, customer_id: str, service_name: str = None, 
                            time_range_hours: int = 1) -> Dict[str, Any]:
        """Get APM metrics for service performance monitoring"""
        try:
            if not self.clickhouse_client:
                return {}
            
            service_filter = ""
            params = {'customer_id': customer_id, 'hours': time_range_hours}
            
            if service_name:
                service_filter = "AND service_name = %(service_name)s"
                params['service_name'] = service_name
            
            # Request rate
            rate_query = f"""
            SELECT 
                toStartOfMinute(start_time) as time_bucket,
                count(*) as requests_per_minute
            FROM traces 
            WHERE customer_id = %(customer_id)s 
            AND start_time >= now() - INTERVAL %(hours)s HOUR
            {service_filter}
            GROUP BY time_bucket
            ORDER BY time_bucket
            """
            
            # Latency percentiles
            latency_query = f"""
            SELECT 
                quantile(0.5)(duration_ms) as p50_ms,
                quantile(0.95)(duration_ms) as p95_ms,
                quantile(0.99)(duration_ms) as p99_ms,
                avg(duration_ms) as avg_ms
            FROM traces 
            WHERE customer_id = %(customer_id)s 
            AND start_time >= now() - INTERVAL %(hours)s HOUR
            {service_filter}
            """
            
            # Error rate
            error_query = f"""
            SELECT 
                toStartOfMinute(start_time) as time_bucket,
                sum(case when status = 'error' then 1 else 0 end) / count(*) * 100 as error_rate_percent
            FROM traces 
            WHERE customer_id = %(customer_id)s 
            AND start_time >= now() - INTERVAL %(hours)s HOUR
            {service_filter}
            GROUP BY time_bucket
            ORDER BY time_bucket
            """
            
            rate_result = self.clickhouse_client.query(rate_query, parameters=params)
            latency_result = self.clickhouse_client.query(latency_query, parameters=params)
            error_result = self.clickhouse_client.query(error_query, parameters=params)
            
            # Helper function to handle NaN/infinity values
            def safe_float(val):
                import math
                if val is None or math.isnan(val) or math.isinf(val):
                    return 0.0
                return float(val)
            
            return {
                "request_rate": [{'time': row[0], 'rpm': safe_float(row[1])} for row in rate_result.result_rows],
                "latency": {
                    'p50_ms': safe_float(latency_result.result_rows[0][0]) if latency_result.result_rows else 0,
                    'p95_ms': safe_float(latency_result.result_rows[0][1]) if latency_result.result_rows else 0,
                    'p99_ms': safe_float(latency_result.result_rows[0][2]) if latency_result.result_rows else 0,
                    'avg_ms': safe_float(latency_result.result_rows[0][3]) if latency_result.result_rows else 0
                },
                "error_rate": [{'time': row[0], 'error_rate': safe_float(row[1])} for row in error_result.result_rows],
                "time_range_hours": time_range_hours,
                "service_name": service_name
            }
            
        except Exception as e:
            logger.error("Failed to get APM metrics", error=str(e))
            return {}


# Global observability engine instance
observability_engine = None

def get_observability_engine():
    """Get the global observability engine instance"""
    global observability_engine
    if observability_engine is None:
        from dependencies import get_clickhouse_client
        client = get_clickhouse_client()
        observability_engine = ObservabilityEngine(client)
    return observability_engine