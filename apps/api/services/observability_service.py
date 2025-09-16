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
            resource=span_data.get('resource', {}),
            customer_id=customer_id
        )
        
        # Save to database
        span_id = await self.dao.save_trace_span(asdict(trace_span))
        
        # Update service topology
        await self._update_service_topology(trace_span)
        
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
        # Validate required fields
        required_fields = ['name', 'type', 'value']
        for field in required_fields:
            if not metric_data.get(field):
                raise ValueError(f"Missing required field: {field}")
        
        # Create Metric object
        metric = Metric(
            id=str(uuid.uuid4()),
            name=metric_data['name'],
            type=metric_data['type'],
            value=float(metric_data['value']),
            unit=metric_data.get('unit', ''),
            description=metric_data.get('description', ''),
            attributes=metric_data.get('attributes', {}),
            resource=metric_data.get('resource', {}),
            timestamp=datetime.fromisoformat(metric_data.get('timestamp', datetime.utcnow().isoformat()).replace('Z', '+00:00')),
            customer_id=customer_id
        )
        
        # Save to database
        return await self.dao.save_metric(asdict(metric))
    
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
    
    async def _update_service_topology(self, trace_span: TraceSpan):
        """Update service topology based on trace span"""
        service_data = {
            'service_name': trace_span.service_name,
            'service_version': trace_span.resource.get('service.version', 'unknown'),
            'endpoints': [trace_span.operation_name],
            'dependencies': [],
            'health_status': 'healthy' if trace_span.status != 'error' else 'degraded',
            'attributes': trace_span.resource,
            'customer_id': trace_span.customer_id
        }
        
        # Extract dependencies from parent-child relationships
        if trace_span.parent_span_id:
            # This is a child span, indicating a dependency
            parent_spans = await self.dao.get_span_by_id(trace_span.parent_span_id, trace_span.customer_id)
            if parent_spans:
                parent_service = parent_spans[0]['service_name']
                service_data['dependencies'].append(parent_service)
        
        await self.dao.update_service_topology(service_data)
    
    async def get_service_topology(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get complete service topology map"""
        return await self.dao.get_service_topology(customer_id)
    
    async def get_service_dependencies(self, service_name: str, customer_id: str) -> Dict[str, Any]:
        """Get dependencies for a specific service"""
        return await self.dao.get_service_dependencies(service_name, customer_id)
    
    # ==========================================
    # APM (APPLICATION PERFORMANCE MONITORING)
    # ==========================================
    
    async def get_apm_overview(self, customer_id: str, hours: int = 24) -> Dict[str, Any]:
        """Get APM overview metrics for all services"""
        services = await self.dao.get_service_topology(customer_id)
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
        
        # Calculate metrics for each service
        for service in services:
            service_metrics = await self.get_service_apm_metrics(
                service['service_name'], customer_id, hours
            )
            overview['services'].append(service_metrics.to_dict())
            overview['total_requests'] += service_metrics.total_requests
            overview['total_errors'] += service_metrics.error_count
        
        # Calculate overall averages
        if overview['total_requests'] > 0:
            overview['error_rate'] = (overview['total_errors'] / overview['total_requests']) * 100
            overview['avg_response_time'] = sum(s['avg_response_time'] for s in overview['services']) / len(overview['services'])
        
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
    
    async def get_service_health_status(self, service_name: str, customer_id: str) -> Dict[str, Any]:
        """Get detailed health status for a service"""
        apm_metrics = await self.get_service_apm_metrics(service_name, customer_id, hours=1)
        
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