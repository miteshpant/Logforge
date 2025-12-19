"""
ObservabilityService - Business logic layer for OpenTelemetry traces, metrics, and APM

This service provides comprehensive observability capabilities including:
- OpenTelemetry trace processing and analysis
- Metrics collection and aggregation
- Service topology mapping and dependency analysis
- Application Performance Monitoring (APM)
- Distributed tracing visualization
"""

import json
import uuid
import structlog
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from dao.observability_dao import ObservabilityDAO

logger = structlog.get_logger(__name__)


@dataclass
class TraceSpan:
    """OpenTelemetry trace span representation"""
    id: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation_name: str
    service_name: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: int
    kind: str  # 'unspecified', 'internal', 'server', 'client', 'producer', 'consumer'
    status: str  # 'unset', 'ok', 'error'
    attributes: Dict[str, Any]
    events: List[Dict[str, Any]]
    links: List[Dict[str, Any]]
    resource: Dict[str, Any]
    customer_id: str


@dataclass
class Metric:
    """OpenTelemetry metric representation"""
    id: str
    name: str
    type: str  # 'counter', 'gauge', 'histogram', 'summary'
    value: float
    unit: str
    description: str
    attributes: Dict[str, Any]
    resource: Dict[str, Any]
    timestamp: datetime
    customer_id: str


@dataclass
class ServiceTopology:
    """Service topology and dependency mapping"""
    id: str
    service_name: str
    service_version: str
    endpoints: List[str]
    dependencies: List[str]
    health_status: str  # 'healthy', 'degraded', 'unhealthy', 'unknown'
    last_seen: datetime
    attributes: Dict[str, Any]
    customer_id: str


class APMMetrics:
    """Application Performance Monitoring metrics"""
    def __init__(self, service_name: str, request_rate: float = 0, error_rate: float = 0,
                 avg_response_time: float = 0, p95_response_time: float = 0,
                 p99_response_time: float = 0, throughput: float = 0,
                 error_count: int = 0, total_requests: int = 0, time_window: str = "1h"):
        self.service_name = service_name
        self.request_rate = request_rate  # requests per second
        self.error_rate = error_rate    # error percentage
        self.avg_response_time = avg_response_time  # milliseconds
        self.p95_response_time = p95_response_time  # milliseconds
        self.p99_response_time = p99_response_time  # milliseconds
        self.throughput = throughput    # requests per minute
        self.error_count = error_count
        self.total_requests = total_requests
        self.time_window = time_window     # e.g., "1h", "24h"

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for JSON serialization"""
        return {
            "service_name": self.service_name,
            "request_rate": self.request_rate,
            "error_rate": self.error_rate,
            "avg_response_time": self.avg_response_time,
            "p95_response_time": self.p95_response_time,
            "p99_response_time": self.p99_response_time,
            "throughput": self.throughput,
            "error_count": self.error_count,
            "total_requests": self.total_requests,
            "time_window": self.time_window
        }


class ObservabilityService:
    """Business logic for observability, tracing, and APM operations"""

    def __init__(self):
        self.dao = ObservabilityDAO()

    # ==========================================
    # TRACE MANAGEMENT
    # ==========================================

    async def ingest_trace_span(self, span_data: Dict[str, Any], customer_id: str) -> str:
        """
        Ingest and process an OpenTelemetry trace span

        Args:
            span_data: OpenTelemetry span data
            customer_id: Customer tenant ID

        Returns:
            Generated span ID
        """
        # Generate unique span ID if not provided
        span_id = span_data.get('span_id', str(uuid.uuid4()))

        # Calculate duration if end_time is provided
        duration_ms = 0
        if span_data.get('end_time') and span_data.get('start_time'):
            start = datetime.fromisoformat(span_data['start_time'].replace('Z', '+00:00'))
            end = datetime.fromisoformat(span_data['end_time'].replace('Z', '+00:00'))
            duration_ms = int((end - start).total_seconds() * 1000)
        # Validate required fields
        required_fields = ['trace_id', 'operation_name', 'service_name']
        for field in required_fields:
            if not span_data.get(field):
                raise ValueError(f"Missing required field: {field}")
        processed_resource = span_data.get('resource', {}).copy()

        # Add environment context using proper OTEL field names
        if span_data.get('deployment_environment'):
            processed_resource["deployment.environment"] = span_data.get('deployment_environment')
        if span_data.get('cluster'):
            processed_resource["cluster"] = span_data.get('cluster')
        if span_data.get('namespace'):
            processed_resource["namespace"] = span_data.get('namespace')
        # Create TraceSpan object
        trace_span = TraceSpan(
            id=str(uuid.uuid4()),
            trace_id=span_data['trace_id'],
            span_id=span_id,
            parent_span_id=span_data.get('parent_span_id'),
            operation_name=span_data['operation_name'],
            service_name=span_data['service_name'],
            start_time=datetime.fromisoformat(span_data.get('start_time', datetime.utcnow().isoformat()).replace('Z', '+00:00')),
            end_time=datetime.fromisoformat(span_data['end_time'].replace('Z', '+00:00')) if span_data.get('end_time') else None,
            duration_ms=duration_ms,
            kind=span_data.get('kind', 'unspecified'),
            status=span_data.get('status', 'unset'),
            attributes=span_data.get('attributes', {}),
            events=span_data.get('events', []),
            links=span_data.get('links', []),
            resource=processed_resource,
            customer_id=customer_id
        )
        # Save to database
        span_id = await self.dao.save_trace_span(asdict(trace_span))

        # NOTE: Service topology updates are now handled by batch aggregation in the event handler
        # This prevents per-span UPDATE queries and improves performance
        # await self._update_service_topology(trace_span, span_data)

        return span_id

    async def get_traces_by_service(self, service_name: str, customer_id: str,
                                  limit: int = 100, hours: int = 24) -> List[Dict[str, Any]]:
        """Get traces for a specific service"""
        return await self.dao.get_traces_by_service(service_name, customer_id, limit, hours)

    async def get_trace_by_id(self, trace_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get complete trace by trace ID"""
        spans = await self.dao.get_trace_spans(trace_id, customer_id)
        if not spans:
            return None

        # Build trace tree structure
        trace = {
            'trace_id': trace_id,
            'spans': spans,
            'total_spans': len(spans),
            'duration_ms': max(span['duration_ms'] for span in spans),
            'services': list(set(span['service_name'] for span in spans)),
            'status': 'error' if any(span['status'] == 'error' for span in spans) else 'ok'
        }

        return trace

    async def search_traces(self, customer_id: str, filters: Dict[str, Any],
                          limit: int = 100) -> List[Dict[str, Any]]:
        """Search traces with filters"""
        return await self.dao.search_traces(customer_id, filters, limit)

    # ==========================================
    # METRICS MANAGEMENT
    # ==========================================

    async def ingest_metric(self, metric_data: Dict[str, Any], customer_id: str) -> str:
        """
        Ingest and process an OpenTelemetry metric

        Args:
            metric_data: OpenTelemetry metric data
            customer_id: Customer tenant ID

        Returns:
            Generated metric ID
        """
        # Validate required fields (expecting normalized field names matching metrics_mt table)
        required_fields = ['metric_name', 'metric_type', 'value']
        for field in required_fields:
            if not metric_data.get(field):
                raise ValueError(f"Missing required normalized field: {field}")

        # Prepare database record directly from normalized data (no dataclass conversion needed)
        metric_data[ "customer_id"] = customer_id
        # Save to database
        return await self.dao.save_metric(metric_data)

    async def get_metrics(self, customer_id: str, metric_name: Optional[str] = None,
                         hours: int = 24, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get metrics with optional filtering"""
        return await self.dao.get_metrics(customer_id, metric_name, hours, limit)

    async def get_metric_aggregation(self, customer_id: str, metric_name: str,
                                   aggregation: str, hours: int = 24) -> Dict[str, Any]:
        """Get aggregated metric values"""
        return await self.dao.get_metric_aggregation(customer_id, metric_name, aggregation, hours)

    # ==========================================
    # SERVICE TOPOLOGY & DEPENDENCIES
    # ==========================================

    def _detect_service_type(self, trace_span: TraceSpan) -> str:
        """Intelligently detect service type based on span characteristics"""
        operation = trace_span.operation_name.lower()
        attributes = trace_span.attributes or {}
        resource = trace_span.resource or {}
        kind = trace_span.kind.lower() if trace_span.kind else ""

        # Database services
        if any(keyword in operation for keyword in ['sql', 'query', 'select', 'insert', 'update', 'delete']):
            return 'database'
        if any(keyword in operation for keyword in ['mongodb', 'postgres', 'mysql', 'redis', 'cassandra']):
            return 'database'
        if 'db.' in attributes.get('db.system', ''):
            return 'database'

        # Cache services
        if any(keyword in operation for keyword in ['cache', 'redis', 'memcached', 'get_cache', 'set_cache']):
            return 'cache'
        if 'redis' in trace_span.service_name.lower() or 'memcached' in trace_span.service_name.lower():
            return 'cache'

        # Queue/messaging services
        if any(keyword in operation for keyword in ['queue', 'publish', 'consume', 'message', 'kafka', 'rabbit']):
            return 'queue'
        if any(keyword in trace_span.service_name.lower() for keyword in ['queue', 'kafka', 'rabbit', 'sqs', 'pubsub']):
            return 'queue'
        if kind in ['producer', 'consumer']:
            return 'queue'

        # API services (HTTP-based)
        if any(keyword in operation for keyword in ['http', 'get', 'post', 'put', 'delete', 'api']):
            return 'api'
        if attributes.get('http.method') or attributes.get('http.url'):
            return 'api'
        if kind in ['server', 'client'] and ('http' in operation or 'api' in operation):
            return 'api'

        # External services (3rd party integrations)
        if any(keyword in trace_span.service_name.lower() for keyword in ['external', 'third-party', 'vendor']):
            return 'external'
        if 'external' in operation:
            return 'external'

        # Default to api for general business logic services
        return 'api'

    async def _update_service_topology(self, trace_span: TraceSpan, original_span_data: Dict[str, Any] = None):
        """Update service topology based on trace span with field normalization"""
        raw_service_data = {
            'service_name': original_span_data["service_name"],
            'service_type': self._detect_service_type(trace_span),  # Smart detection!
            'service_version': trace_span.resource.get('service.version', 'unknown'),
            'endpoints': [trace_span.operation_name],
            'dependencies': [],
            'health_status': 'healthy' if trace_span.status != 'error' else 'degraded',
            'metadata': {},  # Additional service metadata
            'resource_attributes': trace_span.resource or {},  # OpenTelemetry resource attributes
            'customer_id': trace_span.customer_id,
            # Add potential field variations for normalization
            'serviceName': trace_span.service_name,  # Alternative naming
            'service': {'name': trace_span.service_name},  # Nested naming
            'app': {'name': trace_span.service_name},  # App-based naming
            'resource': trace_span.resource,  # Full resource for nested extraction
            # Remove hardcoded deployment_environment - let field mapper handle it
            # 'deployment_environment': will be handled by field mapper
            'service_instance_id': original_span_data.get("service_instance_id", "unknown"),
            'namespace':  original_span_data.get("namespace", "unknown"),
            'host':original_span_data.get("host", "unknown"),
            'container_id' : original_span_data.get("container_id", "unknown"),
            'cluster' :  original_span_data.get("cluster", "unknown"),
            "request_count": original_span_data.get("request_count", None),
            "error_count": original_span_data.get("error_count", None),
            "avg_response_time_ms": original_span_data.get("avg_response_time_ms", None),
        }

        # Add customer_id for field mapping cache
        raw_service_data['customer_id'] = trace_span.customer_id

        # Extract dependencies from parent-child relationships
        if trace_span.parent_span_id:
            # This is a child span, indicating a dependency
            parent_spans = await self.dao.get_span_by_id(trace_span.parent_span_id, trace_span.customer_id)
            if parent_spans:
                parent_service = parent_spans[0]['service_name']
                raw_service_data['dependencies'].append(parent_service)
        await self.dao.update_service_topology(raw_service_data)

    async def get_service_topology(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get complete service topology map"""
        return await self.dao.get_service_topology(customer_id)

    async def get_service_metrics_summary(self, customer_id: str) -> Dict[str, Any]:
        """
        Get aggregated service metrics summary - optimized for dashboard.
        Returns pre-calculated totals instead of fetching all services.
        """
        return await self.dao.get_service_metrics_summary(customer_id)

    async def update_service_metrics_aggregated(self, customer_id: str, service_name: str,
                                               service_instance_id: str,
                                               request_count_increment: int,
                                               error_count_increment: int,
                                               avg_response_time_ms: float,
                                               last_seen: datetime,
                                               resource_attributes: Dict[str, Any] = None,
                                               namespace: str = None,
                                               cluster: str = None,
                                               host: str = None,
                                               container_id: str = None,
                                               deployment_environment: str = None,
                                               service_version: str = None,
                                               dependencies: List[str] = None,
                                               endpoints: List[str] = None) -> str:
        """
        Update service metrics with aggregated values from a batch of spans
        This is called once per service per batch, not once per span

        Args:
            customer_id: Customer tenant ID
            service_name: Name of the service
            service_instance_id: Unique instance ID
            request_count_increment: Number of requests in this batch
            error_count_increment: Number of errors in this batch
            avg_response_time_ms: Average response time for this batch
            last_seen: Latest timestamp from the batch
            resource_attributes: OpenTelemetry resource attributes

        Returns:
            Service ID
        """
        try:
            # Check if service exists
            existing_query = """
            SELECT id, request_count, error_count
            FROM service_topology_mt
            WHERE customer_id = %(customer_id)s
              AND service_name = %(service_name)s
              AND service_instance_id = %(service_instance_id)s
            ORDER BY updated_at DESC
            LIMIT 1
            """

            existing_result = await self.dao.db.execute_query(existing_query, {
                "customer_id": customer_id,
                "service_name": service_name,
                "service_instance_id": service_instance_id
            })

            if existing_result and len(existing_result) > 0:
                # UPDATE existing service with incremented counts
                service_id = existing_result[0]["id"]
                new_request_count = existing_result[0].get("request_count", 0) + request_count_increment
                new_error_count = existing_result[0].get("error_count", 0) + error_count_increment

                update_query = """
                ALTER TABLE service_topology_mt
                UPDATE
                    last_seen = %(last_seen)s,
                    request_count = %(request_count)s,
                    error_count = %(error_count)s,
                    avg_response_time_ms = %(avg_response_time_ms)s,
                    health_status = %(health_status)s,
                    updated_at = %(updated_at)s
                WHERE id = %(id)s AND customer_id = %(customer_id)s
                """

                # Determine health status based on error rate
                error_rate = (new_error_count / new_request_count * 100) if new_request_count > 0 else 0
                health_status = 'degraded' if error_rate > 5 else 'healthy'

                await self.dao.db.execute_query(update_query, {
                    "id": service_id,
                    "customer_id": customer_id,
                    "last_seen": last_seen,
                    "request_count": new_request_count,
                    "error_count": new_error_count,
                    "avg_response_time_ms": avg_response_time_ms,
                    "health_status": health_status,
                    "updated_at": datetime.now(timezone.utc)
                })

                logger.debug(
                    f"Service metrics updated: {service_name} "
                    f"(+{request_count_increment} requests, total: {new_request_count})"
                )

                return service_id

            else:
                # INSERT new service (first time seeing it)
                service_id = str(uuid.uuid4())
                resource = resource_attributes or {}

                error_rate = (error_count_increment / request_count_increment * 100) if request_count_increment > 0 else 0
                health_status = 'degraded' if error_rate > 5 else 'healthy'

                insert_query = """
                INSERT INTO service_topology_mt (
                    id, customer_id, service_name, service_version, service_instance_id,
                    deployment_environment, namespace, cluster, host, container_id,
                    service_type, dependencies, endpoints, health_status, last_seen,
                    request_count, error_count, avg_response_time_ms, metadata,
                    resource_attributes, created_at, updated_at
                ) VALUES (
                    %(id)s, %(customer_id)s, %(service_name)s, %(service_version)s, %(service_instance_id)s,
                    %(deployment_environment)s, %(namespace)s, %(cluster)s, %(host)s, %(container_id)s,
                    %(service_type)s, %(dependencies)s, %(endpoints)s, %(health_status)s, %(last_seen)s,
                    %(request_count)s, %(error_count)s, %(avg_response_time_ms)s, %(metadata)s,
                    %(resource_attributes)s, %(created_at)s, %(updated_at)s
                )
                """

                import json

                await self.dao.db.execute_query(insert_query, {
                    "id": service_id,
                    "customer_id": customer_id,
                    "service_name": service_name,
                    "service_version": service_version or resource.get("service.version", "unknown"),
                    "service_instance_id": service_instance_id,
                    "deployment_environment": deployment_environment or resource.get("deployment.environment", "production"),
                    "namespace": namespace or "",
                    "cluster": cluster or "",
                    "host": host or "",
                    "container_id": container_id or "",
                    "service_type": "application",
                    "dependencies": dependencies or [],
                    "endpoints": endpoints or [],
                    "health_status": health_status,
                    "last_seen": last_seen,
                    "request_count": request_count_increment,
                    "error_count": error_count_increment,
                    "avg_response_time_ms": avg_response_time_ms,
                    "metadata": json.dumps({}),
                    "resource_attributes": json.dumps(resource),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                })

                logger.info(f"New service created: {service_name} (instance: {service_instance_id})")

                return service_id

        except Exception as e:
            logger.error(f"Failed to update service metrics aggregated: {e}")
            raise

    async def get_service_dependencies(self, service_name: str, customer_id: str) -> Dict[str, Any]:
        """Get dependencies for a specific service"""
        return await self.dao.get_service_dependencies(service_name, customer_id)

    # ==========================================
    # APM (APPLICATION PERFORMANCE MONITORING)
    # ==========================================

    async def get_apm_overview(self, customer_id: str, hours: int = 24) -> Dict[str, Any]:
        """Get APM overview metrics for all services - optimized with parallel execution"""
        services = await self.dao.get_service_topology(customer_id)

        # Limit to first 10 services to prevent slow queries
        services = services[:10]

        overview = {
            'total_services': len(services),
            'healthy_services': len([s for s in services if s['health_status'] == 'healthy']),
            'degraded_services': len([s for s in services if s['health_status'] == 'degraded']),
            'unhealthy_services': len([s for s in services if s['health_status'] == 'unhealthy']),
            'total_requests': 0,
            'total_errors': 0,
            'avg_response_time': 0,
            'services': []
        }

        # If no services in topology, return empty overview with defaults
        if not services:
            logger.info("No services found in topology, returning empty APM overview")
            return overview

        # Calculate metrics for all services in parallel (much faster!)
        service_metrics_tasks = [
            self.get_service_apm_metrics(service['service_name'], customer_id, hours)
            for service in services
        ]

        # Wait for all service metrics to complete in parallel
        service_metrics_list = await asyncio.gather(*service_metrics_tasks, return_exceptions=True)

        # Process results
        for metrics in service_metrics_list:
            # Skip if there was an exception
            if isinstance(metrics, Exception):
                logger.warning("Failed to get service metrics", error=str(metrics))
                continue

            overview['services'].append(metrics.to_dict())
            overview['total_requests'] += metrics.total_requests
            overview['total_errors'] += metrics.error_count

        # Calculate overall averages
        if overview['total_requests'] > 0:
            overview['error_rate'] = (overview['total_errors'] / overview['total_requests']) * 100
            overview['avg_response_time'] = sum(s['avg_response_time'] for s in overview['services']) / len(overview['services']) if overview['services'] else 0

        return overview

    async def get_service_apm_metrics(self, service_name: str, customer_id: str,
                                    hours: int = 24) -> APMMetrics:
        """Get detailed APM metrics for a specific service"""
        # Get trace data for the service
        traces = await self.dao.get_traces_by_service(service_name, customer_id, limit=10000, hours=hours)

        if not traces:
            return APMMetrics(
                service_name=service_name,
                request_rate=0,
                error_rate=0,
                avg_response_time=0,
                p95_response_time=0,
                p99_response_time=0,
                throughput=0,
                error_count=0,
                total_requests=0,
                time_window=f"{hours}h"
            )

        # Calculate metrics
        total_requests = len(traces)
        error_count = len([t for t in traces if t['status'] == 'error'])
        error_rate = (error_count / total_requests) * 100 if total_requests > 0 else 0

        # Response time statistics
        durations = [t['duration_ms'] for t in traces if t['duration_ms'] > 0]
        avg_response_time = sum(durations) / len(durations) if durations else 0

        # Calculate percentiles
        sorted_durations = sorted(durations)
        p95_index = int(0.95 * len(sorted_durations))
        p99_index = int(0.99 * len(sorted_durations))
        p95_response_time = sorted_durations[p95_index] if sorted_durations else 0
        p99_response_time = sorted_durations[p99_index] if sorted_durations else 0

        # Request rate (requests per second)
        time_span_seconds = hours * 3600
        request_rate = total_requests / time_span_seconds
        throughput = total_requests / (hours * 60)  # requests per minute

        return APMMetrics(
            service_name=service_name,
            request_rate=request_rate,
            error_rate=error_rate,
            avg_response_time=avg_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            throughput=throughput,
            error_count=error_count,
            total_requests=total_requests,
            time_window=f"{hours}h"
        )

    async def get_service_apm_metrics_with_context(self, service_context: Dict[str, Any],
                                                 customer_id: str, hours: int = 24) -> APMMetrics:
        """Get detailed APM metrics for a service with environment context filtering"""
        service_name = service_context.get("service_name")
        deployment_environment = service_context.get("deployment_environment")
        namespace = service_context.get("namespace")
        cluster = service_context.get("cluster")

        # Get trace data with environment context
        traces = await self.dao.get_traces_by_service_with_context(
            service_context, customer_id, limit=10000, hours=hours
        )

        if not traces:
            return APMMetrics(
                service_name=service_name,
                request_rate=0,
                error_rate=0,
                avg_response_time=0,
                p95_response_time=0,
                p99_response_time=0,
                throughput=0,
                error_count=0,
                total_requests=0,
                time_window=f"{hours}h"
            )

        # Calculate metrics (same logic as original method)
        total_requests = len(traces)
        error_count = len([t for t in traces if t['status'] == 'error'])
        error_rate = (error_count / total_requests) * 100 if total_requests > 0 else 0

        # Response time statistics
        durations = [t['duration_ms'] for t in traces if t['duration_ms'] > 0]
        avg_response_time = sum(durations) / len(durations) if durations else 0

        # Calculate percentiles
        sorted_durations = sorted(durations)
        p95_index = int(0.95 * len(sorted_durations))
        p99_index = int(0.99 * len(sorted_durations))
        p95_response_time = sorted_durations[p95_index] if sorted_durations else 0
        p99_response_time = sorted_durations[p99_index] if sorted_durations else 0

        # Request rate (requests per second)
        time_span_seconds = hours * 3600
        request_rate = total_requests / time_span_seconds
        throughput = total_requests / (hours * 60)  # requests per minute

        return APMMetrics(
            service_name=service_name,
            request_rate=request_rate,
            error_rate=error_rate,
            avg_response_time=avg_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            throughput=throughput,
            error_count=error_count,
            total_requests=total_requests,
            time_window=f"{hours}h"
        )

    async def get_service_health_status(self, service_name: str, customer_id: str, hours: int = 1) -> Dict[str, Any]:
        """Get detailed health status for a service"""
        apm_metrics = await self.get_service_apm_metrics(service_name, customer_id, hours=hours)

        # Determine health status based on metrics
        health_status = 'healthy'
        if apm_metrics.error_rate > 10:  # More than 10% errors
            health_status = 'unhealthy'
        elif apm_metrics.error_rate > 5 or apm_metrics.avg_response_time > 5000:  # 5% errors or 5s response time
            health_status = 'degraded'

        return {
            'service_name': service_name,
            'health_status': health_status,
            'metrics': apm_metrics.to_dict(),
            'recommendations': self._get_health_recommendations(apm_metrics),
            'last_updated': datetime.utcnow().isoformat()
        }

    def _get_health_recommendations(self, metrics: APMMetrics) -> List[str]:
        """Generate health recommendations based on metrics"""
        recommendations = []

        if metrics.error_rate > 10:
            recommendations.append("High error rate detected. Investigate recent deployments and error patterns.")
        elif metrics.error_rate > 5:
            recommendations.append("Elevated error rate. Monitor error patterns and consider investigation.")

        if metrics.avg_response_time > 5000:
            recommendations.append("High response time detected. Check for performance bottlenecks.")
        elif metrics.avg_response_time > 2000:
            recommendations.append("Elevated response time. Monitor performance trends.")

        if metrics.request_rate > 100:
            recommendations.append("High traffic volume. Ensure adequate scaling and resources.")

        if not recommendations:
            recommendations.append("Service appears healthy. Continue monitoring.")

        return recommendations

    # ==========================================
    # ANALYTICS & INSIGHTS
    # ==========================================

    async def get_trace_analytics(self, customer_id: str, hours: int = 24) -> Dict[str, Any]:
        """Get comprehensive trace analytics"""
        analytics = await self.dao.get_trace_analytics(customer_id, hours)

        # Enhance with additional insights
        analytics['insights'] = []

        if analytics.get('error_rate', 0) > 5:
            analytics['insights'].append({
                'type': 'warning',
                'message': f"Error rate is {analytics['error_rate']:.1f}%, above recommended threshold of 5%"
            })

        if analytics.get('avg_duration', 0) > 2000:
            analytics['insights'].append({
                'type': 'warning',
                'message': f"Average response time is {analytics['avg_duration']:.0f}ms, consider optimization"
            })

        return analytics

    async def get_performance_trends(self, customer_id: str, days: int = 7) -> Dict[str, Any]:
        """Get performance trends over time"""
        trends = {
            'time_period': f"{days} days",
            'daily_metrics': [],
            'trends': {}
        }

        # Get daily metrics for the specified period
        for day in range(days):
            date = datetime.utcnow() - timedelta(days=day)
            daily_analytics = await self.dao.get_trace_analytics(customer_id, hours=24, start_time=date)

            trends['daily_metrics'].append({
                'date': date.strftime('%Y-%m-%d'),
                'total_traces': daily_analytics.get('total_traces', 0),
                'avg_duration': daily_analytics.get('avg_duration', 0),
                'error_rate': daily_analytics.get('error_rate', 0),
                'unique_services': daily_analytics.get('unique_services', 0)
            })

        # Calculate trends
        if len(trends['daily_metrics']) >= 2:
            latest = trends['daily_metrics'][0]
            previous = trends['daily_metrics'][1]

            trends['trends'] = {
                'traces_trend': self._calculate_trend(latest['total_traces'], previous['total_traces']),
                'performance_trend': self._calculate_trend(previous['avg_duration'], latest['avg_duration']),  # Inverted for performance
                'error_trend': self._calculate_trend(previous['error_rate'], latest['error_rate']),  # Inverted for errors
                'services_trend': self._calculate_trend(latest['unique_services'], previous['unique_services'])
            }

        return trends

    def _calculate_trend(self, current: float, previous: float) -> Dict[str, Any]:
        """Calculate trend percentage and direction"""
        if previous == 0:
            return {'direction': 'stable', 'percentage': 0}

        change = ((current - previous) / previous) * 100

        if abs(change) < 5:
            direction = 'stable'
        elif change > 0:
            direction = 'increasing'
        else:
            direction = 'decreasing'

        return {
            'direction': direction,
            'percentage': round(abs(change), 1)
        }

    async def get_observability_overview_stats(self, customer_id: str, start_time: str, end_time: str) -> Dict[str, Any]:
        """
        Get observability overview statistics for centrum page widgets

        Args:
            customer_id: Customer ID
            start_time: ISO format datetime string
            end_time: ISO format datetime string

        Returns:
            Dict with traces, performance, reliability, services, and spans metrics
        """
        try:
            overview = await self.dao.get_observability_overview_stats(
                customer_id=customer_id,
                start_time=start_time,
                end_time=end_time
            )

            return overview

        except Exception as e:
            logger.error(f"Failed to get observability overview stats for customer {customer_id}: {e}")
            raise
