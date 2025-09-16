"""
Observability DAO - Database Operations for OpenTelemetry Traces, Metrics, and APM
Handles distributed tracing, metrics collection, and service topology mapping
"""

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import json
import uuid

from database_layer import DatabaseLayer

logger = structlog.get_logger(__name__)

class ObservabilityDAO:
    """Data Access Object for Observability and APM"""
    
    def __init__(self):
        self.db = DatabaseLayer("ObservabilityDAO", "observability-dao-service-key")
    
    # Traces Operations
    
    async def save_trace_span(self, span_data: Dict[str, Any]) -> str:
        """Save OpenTelemetry trace span to database"""
        try:
            span_id = span_data.get("id", str(uuid.uuid4()))
            
            query = """
            INSERT INTO traces_mt (
                id, trace_id, span_id, parent_span_id, operation_name, service_name,
                start_time, end_time, duration_ms, kind, status, status_message,
                attributes, events, links, resource, customer_id, ingested_at
            ) VALUES (
                %(id)s, %(trace_id)s, %(span_id)s, %(parent_span_id)s, %(operation_name)s, %(service_name)s,
                %(start_time)s, %(end_time)s, %(duration_ms)s, %(kind)s, %(status)s, %(status_message)s,
                %(attributes)s, %(events)s, %(links)s, %(resource)s, %(customer_id)s, %(ingested_at)s
            )
            """
            
            params = {
                "id": span_id,
                "trace_id": span_data.get("trace_id", ""),
                "span_id": span_data.get("span_id", ""),
                "parent_span_id": span_data.get("parent_span_id"),
                "operation_name": span_data.get("operation_name", ""),
                "service_name": span_data.get("service_name", ""),
                "start_time": span_data.get("start_time", datetime.now(timezone.utc)),
                "end_time": span_data.get("end_time"),
                "duration_ms": span_data.get("duration_ms", 0),
                "kind": span_data.get("kind", "internal"),
                "status": span_data.get("status", "ok"),
                "status_message": span_data.get("status_message"),
                "attributes": json.dumps(span_data.get("attributes", {})),
                "events": json.dumps(span_data.get("events", [])),
                "links": json.dumps(span_data.get("links", [])),
                "resource": json.dumps(span_data.get("resource", {})),
                "customer_id": span_data.get("customer_id", "default"),
                "ingested_at": datetime.now(timezone.utc)
            }
            
            await self.db.execute_query(query, params)
            logger.debug(f"Trace span saved: {span_id}")
            
            return span_id
            
        except Exception as e:
            logger.error(f"Failed to save trace span: {e}")
            raise
    
    async def batch_save_trace_spans(self, spans: List[Dict[str, Any]]) -> int:
        """Batch save multiple trace spans"""
        try:
            if not spans:
                return 0
            
            saved_count = 0
            for span in spans:
                try:
                    await self.save_trace_span(span)
                    saved_count += 1
                except Exception as e:
                    logger.warning(f"Failed to save span {span.get('span_id', 'unknown')}: {e}")
            
            logger.info(f"Batch trace spans saved: {saved_count}/{len(spans)}")
            return saved_count
            
        except Exception as e:
            logger.error(f"Failed to batch save trace spans: {e}")
            raise
    
    async def get_traces_by_trace_id(self, trace_id: str, customer_id: str) -> List[Dict[str, Any]]:
        """Get all spans for a specific trace ID"""
        try:
            query = """
            SELECT * FROM traces_mt 
            WHERE trace_id = %(trace_id)s AND customer_id = %(customer_id)s
            ORDER BY start_time ASC
            """
            
            results = await self.db.execute_query(query, {
                "trace_id": trace_id,
                "customer_id": customer_id
            })
            
            # Parse JSON fields
            for result in results:
                for json_field in ["attributes", "events", "links", "resource"]:
                    if result.get(json_field):
                        try:
                            result[json_field] = json.loads(result[json_field])
                        except (json.JSONDecodeError, TypeError):
                            result[json_field] = {} if json_field in ["attributes", "resource"] else []
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get traces for trace_id {trace_id}: {e}")
            raise
    
    async def get_traces_by_service(self, service_name: str, customer_id: str, 
                                  limit: int = 100, hours: int = 24) -> List[Dict[str, Any]]:
        """Get traces for a specific service within time range"""
        try:
            query = """
            SELECT * FROM traces_mt 
            WHERE service_name = %(service_name)s 
            AND customer_id = %(customer_id)s
            AND start_time >= now() - INTERVAL %(hours)s HOUR
            ORDER BY start_time DESC
            LIMIT %(limit)s
            """
            
            results = await self.db.execute_query(query, {
                "service_name": service_name,
                "customer_id": customer_id,
                "hours": hours,
                "limit": limit
            })
            
            # Parse JSON fields
            for result in results:
                for json_field in ["attributes", "events", "links", "resource"]:
                    if result.get(json_field):
                        try:
                            result[json_field] = json.loads(result[json_field])
                        except (json.JSONDecodeError, TypeError):
                            result[json_field] = {} if json_field in ["attributes", "resource"] else []
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get traces for service {service_name}: {e}")
            raise
    
    # Metrics Operations
    
    async def save_metric(self, metric_data: Dict[str, Any]) -> str:
        """Save metric data point to database"""
        try:
            metric_id = metric_data.get("id", str(uuid.uuid4()))
            
            query = """
            INSERT INTO metrics_mt (
                id, metric_name, metric_type, value, timestamp, labels,
                service_name, resource, customer_id, ingested_at
            ) VALUES (
                %(id)s, %(metric_name)s, %(metric_type)s, %(value)s, %(timestamp)s, %(labels)s,
                %(service_name)s, %(resource)s, %(customer_id)s, %(ingested_at)s
            )
            """
            
            params = {
                "id": metric_id,
                "metric_name": metric_data.get("metric_name", ""),
                "metric_type": metric_data.get("metric_type", "gauge"),
                "value": metric_data.get("value", 0.0),
                "timestamp": metric_data.get("timestamp", datetime.now(timezone.utc)),
                "labels": json.dumps(metric_data.get("labels", {})),
                "service_name": metric_data.get("service_name", ""),
                "resource": json.dumps(metric_data.get("resource", {})),
                "customer_id": metric_data.get("customer_id", "default"),
                "ingested_at": datetime.now(timezone.utc)
            }
            
            await self.db.execute_query(query, params)
            logger.debug(f"Metric saved: {metric_id}")
            
            return metric_id
            
        except Exception as e:
            logger.error(f"Failed to save metric: {e}")
            raise
    
    async def batch_save_metrics(self, metrics: List[Dict[str, Any]]) -> int:
        """Batch save multiple metrics"""
        try:
            if not metrics:
                return 0
            
            saved_count = 0
            for metric in metrics:
                try:
                    await self.save_metric(metric)
                    saved_count += 1
                except Exception as e:
                    logger.warning(f"Failed to save metric {metric.get('metric_name', 'unknown')}: {e}")
            
            logger.info(f"Batch metrics saved: {saved_count}/{len(metrics)}")
            return saved_count
            
        except Exception as e:
            logger.error(f"Failed to batch save metrics: {e}")
            raise
    
    async def get_metrics_by_name(self, metric_name: str, customer_id: str, 
                                service_name: str = None, hours: int = 24) -> List[Dict[str, Any]]:
        """Get metric data points by name within time range"""
        try:
            where_clauses = [
                "metric_name = %(metric_name)s",
                "customer_id = %(customer_id)s",
                "timestamp >= now() - INTERVAL %(hours)s HOUR"
            ]
            params = {
                "metric_name": metric_name,
                "customer_id": customer_id,
                "hours": hours
            }
            
            if service_name:
                where_clauses.append("service_name = %(service_name)s")
                params["service_name"] = service_name
            
            query = f"""
            SELECT * FROM metrics_mt 
            WHERE {' AND '.join(where_clauses)}
            ORDER BY timestamp DESC
            LIMIT 1000
            """
            
            results = await self.db.execute_query(query, params)
            
            # Parse JSON fields
            for result in results:
                for json_field in ["labels", "resource"]:
                    if result.get(json_field):
                        try:
                            result[json_field] = json.loads(result[json_field])
                        except (json.JSONDecodeError, TypeError):
                            result[json_field] = {}
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get metrics for {metric_name}: {e}")
            raise
    
    # Service Topology Operations
    
    async def save_service_topology(self, service_data: Dict[str, Any]) -> str:
        """Save service topology information"""
        try:
            service_id = service_data.get("id", str(uuid.uuid4()))
            
            query = """
            INSERT INTO service_topology_mt (
                id, service_name, service_type, dependencies, health_status,
                metadata, last_seen, customer_id, created_at, updated_at
            ) VALUES (
                %(id)s, %(service_name)s, %(service_type)s, %(dependencies)s, %(health_status)s,
                %(metadata)s, %(last_seen)s, %(customer_id)s, %(created_at)s, %(updated_at)s
            )
            """
            
            params = {
                "id": service_id,
                "service_name": service_data.get("service_name", ""),
                "service_type": service_data.get("service_type", "unknown"),
                "dependencies": json.dumps(service_data.get("dependencies", [])),
                "health_status": service_data.get("health_status", "unknown"),
                "metadata": json.dumps(service_data.get("metadata", {})),
                "last_seen": service_data.get("last_seen", datetime.now(timezone.utc)),
                "customer_id": service_data.get("customer_id", "default"),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            await self.db.execute_query(query, params)
            logger.debug(f"Service topology saved: {service_id}")
            
            return service_id
            
        except Exception as e:
            logger.error(f"Failed to save service topology: {e}")
            raise
    
    async def get_service_topology(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get service topology for customer"""
        try:
            query = """
            SELECT * FROM service_topology_mt 
            WHERE customer_id = %(customer_id)s
            ORDER BY service_name ASC
            """
            
            results = await self.db.execute_query(query, {"customer_id": customer_id})
            
            # Parse JSON fields
            for result in results:
                for json_field in ["dependencies", "metadata"]:
                    if result.get(json_field):
                        try:
                            result[json_field] = json.loads(result[json_field])
                        except (json.JSONDecodeError, TypeError):
                            result[json_field] = [] if json_field == "dependencies" else {}
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get service topology: {e}")
            raise
    
    async def save_service_dependency(self, dependency_data: Dict[str, Any]) -> str:
        """Save service dependency mapping"""
        try:
            dependency_id = dependency_data.get("id", str(uuid.uuid4()))
            
            query = """
            INSERT INTO service_dependencies_mt (
                id, from_service, to_service, call_count, avg_latency_ms,
                error_rate, last_seen, customer_id, created_at, updated_at
            ) VALUES (
                %(id)s, %(from_service)s, %(to_service)s, %(call_count)s, %(avg_latency_ms)s,
                %(error_rate)s, %(last_seen)s, %(customer_id)s, %(created_at)s, %(updated_at)s
            )
            """
            
            params = {
                "id": dependency_id,
                "from_service": dependency_data.get("from_service", ""),
                "to_service": dependency_data.get("to_service", ""),
                "call_count": dependency_data.get("call_count", 0),
                "avg_latency_ms": dependency_data.get("avg_latency_ms", 0.0),
                "error_rate": dependency_data.get("error_rate", 0.0),
                "last_seen": dependency_data.get("last_seen", datetime.now(timezone.utc)),
                "customer_id": dependency_data.get("customer_id", "default"),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            await self.db.execute_query(query, params)
            logger.debug(f"Service dependency saved: {dependency_id}")
            
            return dependency_id
            
        except Exception as e:
            logger.error(f"Failed to save service dependency: {e}")
            raise
    
    async def get_service_dependencies(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get service dependencies for customer"""
        try:
            query = """
            SELECT * FROM service_dependencies_mt 
            WHERE customer_id = %(customer_id)s
            ORDER BY call_count DESC, avg_latency_ms ASC
            """
            
            results = await self.db.execute_query(query, {"customer_id": customer_id})
            return results
            
        except Exception as e:
            logger.error(f"Failed to get service dependencies: {e}")
            raise
    
    # Analytics and Aggregations
    
    async def get_service_performance_stats(self, service_name: str, customer_id: str, 
                                          hours: int = 24) -> Dict[str, Any]:
        """Get performance statistics for a service"""
        try:
            # Get trace statistics
            trace_query = """
            SELECT 
                COUNT(*) as total_spans,
                AVG(duration_ms) as avg_duration_ms,
                quantile(0.5)(duration_ms) as p50_duration_ms,
                quantile(0.95)(duration_ms) as p95_duration_ms,
                quantile(0.99)(duration_ms) as p99_duration_ms,
                COUNT(CASE WHEN status = 'error' THEN 1 END) * 100.0 / COUNT(*) as error_rate
            FROM traces_mt 
            WHERE service_name = %(service_name)s 
            AND customer_id = %(customer_id)s
            AND start_time >= now() - INTERVAL %(hours)s HOUR
            """
            
            trace_stats = await self.db.execute_query(trace_query, {
                "service_name": service_name,
                "customer_id": customer_id,
                "hours": hours
            })
            
            return {
                "service_name": service_name,
                "time_window_hours": hours,
                "trace_stats": trace_stats[0] if trace_stats else {},
                "calculated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get performance stats for {service_name}: {e}")
            raise
    
    async def get_platform_observability_stats(self, customer_id: str) -> Dict[str, Any]:
        """Get platform-wide observability statistics"""
        try:
            # Service count
            service_query = """
            SELECT COUNT(DISTINCT service_name) as service_count
            FROM traces_mt 
            WHERE customer_id = %(customer_id)s
            AND start_time >= now() - INTERVAL 24 HOUR
            """
            
            # Trace count
            trace_query = """
            SELECT 
                COUNT(*) as total_traces,
                COUNT(DISTINCT trace_id) as unique_traces,
                AVG(duration_ms) as avg_duration_ms
            FROM traces_mt 
            WHERE customer_id = %(customer_id)s
            AND start_time >= now() - INTERVAL 24 HOUR
            """
            
            # Metric count
            metric_query = """
            SELECT 
                COUNT(*) as total_metrics,
                COUNT(DISTINCT metric_name) as unique_metrics
            FROM metrics_mt 
            WHERE customer_id = %(customer_id)s
            AND timestamp >= now() - INTERVAL 24 HOUR
            """
            
            service_stats = await self.db.execute_query(service_query, {"customer_id": customer_id})
            trace_stats = await self.db.execute_query(trace_query, {"customer_id": customer_id})
            metric_stats = await self.db.execute_query(metric_query, {"customer_id": customer_id})
            
            return {
                "customer_id": customer_id,
                "services": service_stats[0] if service_stats else {"service_count": 0},
                "traces": trace_stats[0] if trace_stats else {"total_traces": 0, "unique_traces": 0, "avg_duration_ms": 0},
                "metrics": metric_stats[0] if metric_stats else {"total_metrics": 0, "unique_metrics": 0},
                "calculated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get platform observability stats: {e}")
            raise

    # Missing methods needed by ObservabilityService

    async def get_trace_spans(self, trace_id: str, customer_id: str) -> List[Dict[str, Any]]:
        """Get all spans for a specific trace ID - alias for get_traces_by_trace_id"""
        return await self.get_traces_by_trace_id(trace_id, customer_id)

    async def search_traces(self, customer_id: str, filters: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        """Search traces with filters"""
        try:
            where_clauses = ["customer_id = %(customer_id)s"]
            params = {"customer_id": customer_id, "limit": limit}
            
            if filters.get("service_name"):
                where_clauses.append("service_name = %(service_name)s")
                params["service_name"] = filters["service_name"]
            
            if filters.get("operation_name"):
                where_clauses.append("operation_name = %(operation_name)s")
                params["operation_name"] = filters["operation_name"]
                
            if filters.get("start_time"):
                where_clauses.append("start_time >= %(start_time)s")
                params["start_time"] = filters["start_time"]
                
            if filters.get("end_time"):
                where_clauses.append("start_time <= %(end_time)s")
                params["end_time"] = filters["end_time"]
                
            if filters.get("min_duration_ms"):
                where_clauses.append("duration_ms >= %(min_duration_ms)s")
                params["min_duration_ms"] = filters["min_duration_ms"]
                
            if filters.get("max_duration_ms"):
                where_clauses.append("duration_ms <= %(max_duration_ms)s")
                params["max_duration_ms"] = filters["max_duration_ms"]
                
            if filters.get("status"):
                where_clauses.append("status = %(status)s")
                params["status"] = filters["status"]
            
            query = f"""
            SELECT * FROM traces_mt 
            WHERE {' AND '.join(where_clauses)}
            ORDER BY start_time DESC
            LIMIT %(limit)s
            """
            
            if filters.get("offset"):
                query += " OFFSET %(offset)s"
                params["offset"] = filters["offset"]
            
            results = await self.db.execute_query(query, params)
            
            # Parse JSON fields
            for result in results:
                for json_field in ["attributes", "events", "links", "resource"]:
                    if result.get(json_field):
                        try:
                            result[json_field] = json.loads(result[json_field])
                        except (json.JSONDecodeError, TypeError):
                            result[json_field] = {} if json_field in ["attributes", "resource"] else []
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search traces: {e}")
            raise

    async def get_span_by_id(self, span_id: str, customer_id: str) -> List[Dict[str, Any]]:
        """Get span by span ID"""
        try:
            query = """
            SELECT * FROM traces_mt 
            WHERE span_id = %(span_id)s AND customer_id = %(customer_id)s
            """
            
            results = await self.db.execute_query(query, {
                "span_id": span_id,
                "customer_id": customer_id
            })
            
            # Parse JSON fields
            for result in results:
                for json_field in ["attributes", "events", "links", "resource"]:
                    if result.get(json_field):
                        try:
                            result[json_field] = json.loads(result[json_field])
                        except (json.JSONDecodeError, TypeError):
                            result[json_field] = {} if json_field in ["attributes", "resource"] else []
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get span by ID {span_id}: {e}")
            raise

    async def update_service_topology(self, service_data: Dict[str, Any]) -> str:
        """Update or insert service topology"""
        try:
            service_name = service_data.get("service_name")
            customer_id = service_data.get("customer_id")
            
            # Check if service already exists
            check_query = """
            SELECT id FROM service_topology_mt 
            WHERE service_name = %(service_name)s AND customer_id = %(customer_id)s
            """
            
            existing = await self.db.execute_query(check_query, {
                "service_name": service_name,
                "customer_id": customer_id
            })
            
            if existing:
                # Update existing service
                update_query = """
                ALTER TABLE service_topology_mt 
                UPDATE 
                    health_status = %(health_status)s,
                    metadata = %(metadata)s,
                    last_seen = %(last_seen)s,
                    updated_at = %(updated_at)s
                WHERE service_name = %(service_name)s AND customer_id = %(customer_id)s
                """
                
                params = {
                    "service_name": service_name,
                    "customer_id": customer_id,
                    "health_status": service_data.get("health_status", "unknown"),
                    "metadata": json.dumps(service_data.get("attributes", {})),
                    "last_seen": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
                
                await self.db.execute_query(update_query, params)
                return existing[0]["id"]
            else:
                # Create new service
                service_topology_data = {
                    "service_name": service_name,
                    "service_type": "application",
                    "dependencies": service_data.get("dependencies", []),
                    "health_status": service_data.get("health_status", "unknown"),
                    "metadata": service_data.get("attributes", {}),
                    "customer_id": customer_id
                }
                return await self.save_service_topology(service_topology_data)
                
        except Exception as e:
            logger.error(f"Failed to update service topology: {e}")
            raise

    async def get_metrics(self, customer_id: str, metric_name: Optional[str] = None, 
                         hours: int = 24, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get metrics with optional filtering"""
        try:
            where_clauses = [
                "customer_id = %(customer_id)s",
                "timestamp >= now() - INTERVAL %(hours)s HOUR"
            ]
            params = {
                "customer_id": customer_id,
                "hours": hours,
                "limit": limit
            }
            
            if metric_name:
                where_clauses.append("metric_name = %(metric_name)s")
                params["metric_name"] = metric_name
            
            query = f"""
            SELECT * FROM metrics_mt 
            WHERE {' AND '.join(where_clauses)}
            ORDER BY timestamp DESC
            LIMIT %(limit)s
            """
            
            results = await self.db.execute_query(query, params)
            
            # Parse JSON fields and convert to expected format
            for result in results:
                for json_field in ["labels", "resource"]:
                    if result.get(json_field):
                        try:
                            result[json_field] = json.loads(result[json_field])
                        except (json.JSONDecodeError, TypeError):
                            result[json_field] = {}
                            
                # Convert to expected format
                result["name"] = result.get("metric_name", "")
                result["type"] = result.get("metric_type", "gauge")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            raise

    async def get_metric_aggregation(self, customer_id: str, metric_name: str, 
                                   aggregation: str, hours: int = 24) -> Dict[str, Any]:
        """Get aggregated metric values"""
        try:
            agg_function = {
                "avg": "AVG",
                "sum": "SUM", 
                "max": "MAX",
                "min": "MIN",
                "count": "COUNT"
            }.get(aggregation.lower(), "AVG")
            
            query = f"""
            SELECT 
                {agg_function}(value) as aggregated_value,
                COUNT(*) as data_points,
                MIN(timestamp) as start_time,
                MAX(timestamp) as end_time
            FROM metrics_mt 
            WHERE metric_name = %(metric_name)s 
            AND customer_id = %(customer_id)s
            AND timestamp >= now() - INTERVAL %(hours)s HOUR
            """
            
            results = await self.db.execute_query(query, {
                "metric_name": metric_name,
                "customer_id": customer_id,
                "hours": hours
            })
            
            if results:
                result = results[0]
                # Safely handle aggregated value (can be NULL/None from ClickHouse)
                aggregated_value = result.get("aggregated_value", 0)
                if aggregated_value is None or (isinstance(aggregated_value, float) and 
                   (aggregated_value != aggregated_value or abs(aggregated_value) == float('inf'))):
                    aggregated_value = 0.0
                
                return {
                    "metric_name": metric_name,
                    "aggregation": aggregation,
                    "value": float(aggregated_value),
                    "data_points": result.get("data_points", 0),
                    "time_range": {
                        "start": result.get("start_time").isoformat() if result.get("start_time") else None,
                        "end": result.get("end_time").isoformat() if result.get("end_time") else None,
                        "hours": hours
                    }
                }
            else:
                return {
                    "metric_name": metric_name,
                    "aggregation": aggregation,
                    "value": 0,
                    "data_points": 0,
                    "time_range": {"hours": hours}
                }
                
        except Exception as e:
            logger.error(f"Failed to get metric aggregation: {e}")
            raise

    async def get_trace_analytics(self, customer_id: str, hours: int = 24, start_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Get comprehensive trace analytics"""
        try:
            where_clauses = ["customer_id = %(customer_id)s"]
            params = {"customer_id": customer_id, "hours": hours}
            
            if start_time:
                where_clauses.append("start_time >= %(start_time)s")
                where_clauses.append("start_time < %(end_time)s")
                params["start_time"] = start_time
                params["end_time"] = start_time + timedelta(hours=hours)
            else:
                where_clauses.append("start_time >= now() - INTERVAL %(hours)s HOUR")
            
            query = f"""
            SELECT 
                COUNT(*) as total_traces,
                COUNT(DISTINCT trace_id) as unique_traces,
                COUNT(DISTINCT service_name) as unique_services,
                AVG(duration_ms) as avg_duration,
                quantile(0.5)(duration_ms) as p50_duration,
                quantile(0.95)(duration_ms) as p95_duration,
                quantile(0.99)(duration_ms) as p99_duration,
                COUNT(CASE WHEN status = 'error' THEN 1 END) * 100.0 / COUNT(*) as error_rate,
                COUNT(CASE WHEN status = 'error' THEN 1 END) as error_count
            FROM traces_mt 
            WHERE {' AND '.join(where_clauses)}
            """
            
            results = await self.db.execute_query(query, params)
            
            if results:
                analytics = results[0]
                
                # Safely handle all float values from ClickHouse aggregations
                def safe_float(value, default=0.0):
                    if value is None or (isinstance(value, float) and 
                       (value != value or abs(value) == float('inf'))):
                        return default
                    return float(value)
                
                return {
                    "total_traces": analytics.get("total_traces", 0),
                    "unique_traces": analytics.get("unique_traces", 0),
                    "unique_services": analytics.get("unique_services", 0),
                    "avg_duration": safe_float(analytics.get("avg_duration")),
                    "p50_duration": safe_float(analytics.get("p50_duration")),
                    "p95_duration": safe_float(analytics.get("p95_duration")),
                    "p99_duration": safe_float(analytics.get("p99_duration")),
                    "error_rate": safe_float(analytics.get("error_rate")),
                    "error_count": analytics.get("error_count", 0),
                    "time_window_hours": hours,
                    "calculated_at": datetime.now(timezone.utc).isoformat()
                }
            else:
                return {
                    "total_traces": 0,
                    "unique_traces": 0,
                    "unique_services": 0,
                    "avg_duration": 0,
                    "p50_duration": 0,
                    "p95_duration": 0,
                    "p99_duration": 0,
                    "error_rate": 0,
                    "error_count": 0,
                    "time_window_hours": hours,
                    "calculated_at": datetime.now(timezone.utc).isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to get trace analytics: {e}")
            raise