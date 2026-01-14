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

    async def get_traces_by_service_with_context(self, service_context: Dict[str, Any], customer_id: str,
                                               limit: int = 100, hours: int = 24) -> List[Dict[str, Any]]:
        """Get traces for a service with environment context filtering using normalization service"""
        try:
            # First, get all traces for the service without environment filtering
            query = """
            SELECT * FROM traces_mt
            WHERE service_name = %(service_name)s
            AND customer_id = %(customer_id)s
            AND start_time >= now() - INTERVAL %(hours)s HOUR
            ORDER BY start_time DESC
            LIMIT %(limit)s
            """

            params = {
                "service_name": service_context.get("service_name"),
                "customer_id": customer_id,
                "hours": hours,
                "limit": limit
            }

            results = await self.db.execute_query(query, params)

            # Parse JSON fields
            for result in results:
                for json_field in ["attributes", "events", "links", "resource"]:
                    if result.get(json_field):
                        try:
                            result[json_field] = json.loads(result[json_field])
                        except (json.JSONDecodeError, TypeError):
                            result[json_field] = {} if json_field in ["attributes", "resource"] else []

            # Apply environment context filtering using normalization service
            if any([service_context.get("deployment_environment"),
                   service_context.get("namespace"),
                   service_context.get("cluster")]):

                # Import normalization service
                try:
                    from services.simple_otel_mapper import normalize_otel_service_simple
                except ImportError:
                    logger.warning("Could not import normalization service, skipping environment filtering")
                    return results

                filtered_results = []
                for result in results:
                    # Normalize the resource attributes to get standard field names
                    resource_data = result.get("resource", {})
                    if resource_data:
                        normalized = normalize_otel_service_simple(resource_data)

                        # Check if this trace matches the environment context exactly
                        matches = True

                        if service_context.get("deployment_environment"):
                            trace_env = normalized.get("deployment_environment")
                            # Must have the exact environment value - exclude if missing or different
                            if trace_env != service_context.get("deployment_environment"):
                                matches = False

                        if service_context.get("namespace") and matches:
                            trace_ns = normalized.get("namespace")
                            # Must have the exact namespace value - exclude if missing or different
                            if trace_ns != service_context.get("namespace"):
                                matches = False

                        if service_context.get("cluster") and matches:
                            trace_cluster = normalized.get("cluster")
                            # Must have the exact cluster value - exclude if missing or different
                            if trace_cluster != service_context.get("cluster"):
                                matches = False

                        if matches:
                            # Add normalized environment info to result for debugging
                            result["_normalized_env"] = {
                                "deployment_environment": normalized.get("deployment_environment"),
                                "namespace": normalized.get("namespace"),
                                "cluster": normalized.get("cluster")
                            }
                            filtered_results.append(result)

                logger.info(f"Environment filtering: {len(results)} -> {len(filtered_results)} traces")
                return filtered_results

            return results
        except Exception as e:
            logger.error(f"Failed to get traces for service with context {service_context}: {e}")
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
            # Ensure proper formatting for ClickHouse DateTime64
            if "timestamp" in metric_data and metric_data["timestamp"]:
                if isinstance(metric_data["timestamp"], str):
                    # Parse and convert to ClickHouse-compatible format
                    timestamp = datetime.fromisoformat(metric_data["timestamp"].replace('Z', '+00:00'))
                    metric_data["timestamp"] = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(metric_data["timestamp"], datetime):
                    metric_data["timestamp"] = metric_data["timestamp"].strftime('%Y-%m-%d %H:%M:%S')

            # Set required fields with proper formatting
            metric_data["id"] = metric_id
            metric_data["ingested_at"] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

            # Ensure JSON fields are properly serialized
            if "labels" in metric_data and not isinstance(metric_data["labels"], str):
                metric_data["labels"] = json.dumps(metric_data["labels"])
            if "resource" in metric_data and not isinstance(metric_data["resource"], str):
                metric_data["resource"] = json.dumps(metric_data["resource"])
            logger.info(f"metric data {metric_data}")
            db_data = {
                        "id": metric_data["id"],
                        "metric_name": metric_data["metric_name"],
                        "metric_type": metric_data["metric_type"],
                        "value": metric_data["value"],
                        "labels": metric_data["labels"],
                        "timestamp": metric_data["timestamp"],
                        "service_name": metric_data["service_name"],
                        "resource": metric_data["resource"],
                        "customer_id":metric_data["customer_id"],
                        "ingested_at": metric_data["ingested_at"]
                      }
            logger.info(f"DB DATA {db_data}")
            await self.db.execute_query(query, db_data)
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
        """Save or update service topology information with Phase 3 schema"""
        try:
            # Extract OpenTelemetry resource attributes first
            resource = service_data.get("resource_attributes", service_data.get("attributes", {}))

            customer_id = service_data.get("customer_id", "default")
            service_name = service_data.get("service_name", "")
            service_instance_id = resource.get("service.instance.id", service_data.get("service_instance_id", ""))

            # Check if service already exists based on service_name, customer_id, and instance_id
            # This creates a unique key for the service
            existing_query = """
            SELECT id, request_count, error_count
            FROM service_topology_mt
            WHERE customer_id = %(customer_id)s
              AND service_name = %(service_name)s
              AND service_instance_id = %(service_instance_id)s
            ORDER BY updated_at DESC
            LIMIT 1
            """

            existing_result = await self.db.execute_query(existing_query, {
                "customer_id": customer_id,
                "service_name": service_name,
                "service_instance_id": service_instance_id
            })

            # Determine if this is an update or insert
            if existing_result and len(existing_result) > 0:
                # Update existing service with new last_seen and metrics
                service_id = existing_result[0]["id"]
                existing_request_count = existing_result[0].get("request_count", 0)
                existing_error_count = existing_result[0].get("error_count", 0)

                # Increment counts (handle None values properly)
                request_count_increment = service_data.get("request_count")
                if request_count_increment is None:
                    request_count_increment = 1
                error_count_increment = service_data.get("error_count")
                if error_count_increment is None:
                    error_count_increment = 0

                new_request_count = existing_request_count + request_count_increment
                new_error_count = existing_error_count + error_count_increment

                query = """
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

                params = {
                    "id": service_id,
                    "customer_id": customer_id,
                    "last_seen": datetime.now(timezone.utc),
                    "request_count": new_request_count,
                    "error_count": new_error_count,
                    "avg_response_time_ms": service_data.get("avg_response_time_ms", 0.0),
                    "health_status": service_data.get("health_status", "unknown"),
                    "updated_at": datetime.now(timezone.utc)
                }

                await self.db.execute_query(query, params)
                logger.debug(f"Service topology updated: {service_id} (last_seen, request_count: {new_request_count})")

            else:
                # Insert new service
                service_id = service_data.get("id", str(uuid.uuid4()))

                query = """
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

                params = {
                    "id": service_id,
                    "customer_id": service_data.get("customer_id", "default"),
                    "service_name": service_data.get("service_name", ""),
                    "service_version": resource.get("service.version", service_data.get("service_version", "unknown")),
                    "service_instance_id": resource.get("service.instance.id", service_data.get("service_instance_id", "")),
                    "deployment_environment": resource.get("deployment.environment", service_data.get("deployment_environment", "production")),
                    "namespace": resource.get("k8s.namespace.name", service_data.get("namespace", "")),
                    "cluster": resource.get("k8s.cluster.name", service_data.get("cluster", "")),
                    "host": resource.get("host.name", service_data.get("host", "")),
                    "container_id": resource.get("container.id", service_data.get("container_id", "")),
                    "service_type": service_data.get("service_type", "application"),
                    "dependencies": service_data.get("dependencies", []),  # Pass as list, not JSON string
                    "endpoints": service_data.get("endpoints", []),        # Pass as list, not JSON string
                    "health_status": service_data.get("health_status", "unknown"),
                    "last_seen": service_data.get("last_seen", datetime.now(timezone.utc)),
                    "request_count": service_data.get("request_count", 0),
                    "error_count": service_data.get("error_count", 0),
                    "avg_response_time_ms": service_data.get("avg_response_time_ms", 0.0),
                    "metadata": json.dumps(service_data.get("metadata", {})),
                    "resource_attributes": json.dumps(resource),
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

            # Parse JSON fields (metadata and resource_attributes are stored as JSON strings)
            # Note: dependencies and endpoints are Array(String) in ClickHouse and are already returned as lists
            for result in results:
                # Only parse fields that are actually JSON strings
                for json_field in ["metadata", "resource_attributes"]:
                    if result.get(json_field):
                        try:
                            # Only parse if it's a string, otherwise leave as-is
                            if isinstance(result[json_field], str):
                                result[json_field] = json.loads(result[json_field])
                        except (json.JSONDecodeError, TypeError):
                            result[json_field] = {}

                # Ensure array fields are lists (they should already be from ClickHouse)
                for array_field in ["dependencies", "endpoints"]:
                    if result.get(array_field) is None:
                        result[array_field] = []
                    elif not isinstance(result[array_field], list):
                        # Convert tuple to list if needed
                        result[array_field] = list(result[array_field]) if hasattr(result[array_field], '__iter__') else []

            return results

        except Exception as e:
            logger.error(f"Failed to get service topology: {e}")
            raise

    async def get_service_metrics_summary(self, customer_id: str) -> Dict[str, Any]:
        """
        Get aggregated service metrics summary - optimized for dashboard widgets.
        Returns total requests, errors, error rate, and avg response time.
        Much faster than fetching all services and aggregating in application layer.
        """
        try:
            query = """
            SELECT
                sum(error_count) as total_errors,
                sum(request_count) as total_requests,
                (sum(error_count) * 100.0) / nullIf(sum(request_count), 0) as error_rate_percent,
                avg(avg_response_time_ms) as avg_response_time_ms,
                count() as total_services,
                countIf(request_count > 0) as active_services
            FROM service_topology_mt
            WHERE customer_id = %(customer_id)s
            """

            results = await self.db.execute_query(query, {"customer_id": customer_id})

            if not results or len(results) == 0:
                return {
                    "total_errors": 0,
                    "total_requests": 0,
                    "error_rate_percent": 0.0,
                    "avg_response_time_ms": 0.0,
                    "total_services": 0,
                    "active_services": 0
                }

            return results[0]

        except Exception as e:
            logger.error(f"Failed to get service metrics summary: {e}")
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
                if(count(*) > 0 AND count(duration_ms) > 0, AVG(duration_ms), 0) as avg_duration_ms,
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
                if(count(*) > 0 AND count(duration_ms) > 0, AVG(duration_ms), 0) as avg_duration_ms
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

    async def search_trace_summaries(self, customer_id: str, filters: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        """Search traces and return aggregated summaries grouped by trace_id"""
        try:
            where_clauses = ["customer_id = %(customer_id)s"]
            params = {"customer_id": customer_id, "limit": limit}

            if filters.get("service_name"):
                where_clauses.append("service_name = %(service_name)s")
                params["service_name"] = filters["service_name"]

            if filters.get("operation_name"):
                where_clauses.append("operation_name LIKE %(operation_name)s")
                params["operation_name"] = f"%{filters['operation_name']}%"

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

            # Aggregate by trace_id to get trace summaries
            query = f"""
            SELECT
                trace_id,
                min(start_time) as trace_start_time,
                max(duration_ms) as duration_ms,
                count() as span_count,
                countIf(status = 'error') as error_count,
                groupArray(DISTINCT service_name) as services,
                argMin(service_name, if(parent_span_id = '', 0, 1)) as root_service,
                argMin(operation_name, if(parent_span_id = '', 0, 1)) as root_operation,
                if(countIf(status = 'error') > 0, 'error', 'ok') as trace_status
            FROM traces_mt
            WHERE {' AND '.join(where_clauses)}
            GROUP BY trace_id
            ORDER BY trace_start_time DESC
            LIMIT %(limit)s
            """

            if filters.get("offset"):
                query += " OFFSET %(offset)s"
                params["offset"] = filters["offset"]

            results = await self.db.execute_query(query, params)
            return results

        except Exception as e:
            logger.error(f"Failed to search trace summaries: {e}")
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
        """Update or insert service topology using Phase 3 schema with unique service instances"""
        try:
            service_name = service_data.get("service_name")
            customer_id = service_data.get("customer_id")

            # Phase 3: Check for unique service instance instead of just service name
            resource = service_data.get("resource_attributes", service_data.get("attributes", {}))
            service_version = resource.get("service.version", service_data.get("service_version", "unknown"))
            service_instance_id = resource.get("service.instance.id", service_data.get("service_instance_id", ""))
            deployment_environment = resource.get("deployment.environment", service_data.get("deployment_environment", "production"))

            # Check if this specific service instance already exists
            check_query = """
            SELECT id FROM service_topology_mt
            WHERE service_name = %(service_name)s
            AND customer_id = %(customer_id)s
            AND service_version = %(service_version)s
            AND deployment_environment = %(deployment_environment)s
            """

            check_params = {
                "service_name": service_name,
                "customer_id": customer_id,
                "service_version": service_version,
                "deployment_environment": deployment_environment
            }

            # Add service_instance_id to check if it's available
            if service_instance_id:
                check_query += " AND service_instance_id = %(service_instance_id)s"
                check_params["service_instance_id"] = service_instance_id

            service_topology_data = {
                "service_name": service_name,
                "service_type": service_data.get("service_type", "api"),
                "service_version": service_version,
                "service_instance_id": service_instance_id,
                "deployment_environment": deployment_environment,
                "dependencies": service_data.get("dependencies", []),
                "endpoints": service_data.get("endpoints", []),
                "health_status": service_data.get("health_status", "unknown"),
                "metadata": service_data.get("metadata", {}),
                "resource_attributes": resource,
                "customer_id": customer_id,
                "namespace": service_data.get("namespace", None),
                "cluster": service_data.get("cluster", None),
                "host": service_data.get("host", None),
                "last_seen": service_data.get("last_seen", datetime.now(timezone.utc)),  # Always set to current time
                "request_count": service_data.get("request_count", 1),  # Default to 1 for this span
                "error_count": service_data.get("error_count", 0),
                "avg_response_time_ms": service_data.get("avg_response_time_ms", 0.0),
                "container_id" : service_data.get("container_id", None)
            }
            existing = await self.db.execute_query(check_query, check_params)

            if existing:
                # For ReplacingMergeTree, INSERT new record with same composite key to replace
                service_topology_data["id"] = existing[0]["id"]  # Fixed: added quotes around "id"

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
                data_points = result.get("data_points", 0)
                
                # If no actual data points found, return None (no mock data)
                if data_points == 0:
                    return None
                
                # Safely handle aggregated value (can be NULL/None from ClickHouse)
                aggregated_value = result.get("aggregated_value", 0)
                if aggregated_value is None or (isinstance(aggregated_value, float) and
                   (aggregated_value != aggregated_value or abs(aggregated_value) == float('inf'))):
                    aggregated_value = 0.0

                return {
                    "metric_name": metric_name,
                    "aggregation": aggregation,
                    "value": float(aggregated_value),
                    "data_points": data_points,
                    "time_range": {
                        "start": result.get("start_time").isoformat() if result.get("start_time") else None,
                        "end": result.get("end_time").isoformat() if result.get("end_time") else None,
                        "hours": hours
                    }
                }
            else:
                # Return None when no data found - let API handle response
                return None

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
                if(count(*) > 0 AND count(duration_ms) > 0, AVG(duration_ms), 0) as avg_duration,
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

    async def get_observability_overview_stats(self, customer_id: str, start_time: str, end_time: str) -> Dict[str, Any]:
        """
        Get observability overview statistics for centrum page widgets
        Returns traces, performance, reliability, services, and spans metrics
        """
        try:
            from dateutil import parser

            start_dt = parser.parse(start_time)
            end_dt = parser.parse(end_time)

            # Query 1: Traces and Performance metrics (count unique traces only)
            traces_query = """
            SELECT
                COUNT(DISTINCT trace_id) as total_traces,
                COUNT(CASE WHEN status = 'error' THEN 1 END) as error_count,
                AVG(duration_ms) as avg_response_time_ms,
                quantile(0.95)(duration_ms) as p95_latency_ms,
                quantile(0.99)(duration_ms) as p99_latency_ms
            FROM traces_mt
            WHERE customer_id = %(customer_id)s
              AND start_time >= %(start_time)s
              AND start_time <= %(end_time)s
            """

            traces_result = await self.db.fetch_one(traces_query, {
                "customer_id": customer_id,
                "start_time": start_dt,
                "end_time": end_dt
            })

            # Query 2: Active services count
            services_query = """
            SELECT COUNT(DISTINCT service_name) as active_count
            FROM traces_mt
            WHERE customer_id = %(customer_id)s
              AND start_time >= %(start_time)s
              AND start_time <= %(end_time)s
            """

            services_result = await self.db.fetch_one(services_query, {
                "customer_id": customer_id,
                "start_time": start_dt,
                "end_time": end_dt
            })

            # Query 3: Total spans count
            spans_query = """
            SELECT COUNT(*) as total_count
            FROM traces_mt
            WHERE customer_id = %(customer_id)s
              AND start_time >= %(start_time)s
              AND start_time <= %(end_time)s
            """

            spans_result = await self.db.fetch_one(spans_query, {
                "customer_id": customer_id,
                "start_time": start_dt,
                "end_time": end_dt
            })

            # Calculate time range in seconds for rate calculations
            time_range_seconds = (end_dt - start_dt).total_seconds()

            # Safe float conversion
            def safe_float(value, default=0.0):
                if value is None or (isinstance(value, float) and
                   (value != value or abs(value) == float('inf'))):
                    return default
                return float(value)

            # Build response
            total_traces = traces_result.get("total_traces", 0) if traces_result else 0
            error_count = traces_result.get("error_count", 0) if traces_result else 0
            total_spans = spans_result.get("total_count", 0) if spans_result else 0
            active_services = services_result.get("active_count", 0) if services_result else 0

            # Calculate error rate
            error_rate_percent = (error_count / total_traces * 100) if total_traces > 0 else 0.0

            # Calculate spans per second
            spans_per_second = (total_spans / time_range_seconds) if time_range_seconds > 0 else 0.0

            overview = {
                "traces": {
                    "total_count": total_traces,
                    "error_count": error_count
                },
                "performance": {
                    "avg_response_time_ms": safe_float(traces_result.get("avg_response_time_ms")) if traces_result else 0.0,
                    "p95_latency_ms": safe_float(traces_result.get("p95_latency_ms")) if traces_result else 0.0,
                    "p99_latency_ms": safe_float(traces_result.get("p99_latency_ms")) if traces_result else 0.0
                },
                "reliability": {
                    "error_rate_percent": round(error_rate_percent, 2),
                    "total_errors": error_count,
                    "total_success": total_traces - error_count
                },
                "services": {
                    "active_count": active_services
                },
                "spans": {
                    "total_count": total_spans,
                    "spans_per_second": round(spans_per_second, 2)
                },
                "time_range": {
                    "start_time": start_time,
                    "end_time": end_time
                }
            }

            return overview

        except Exception as e:
            logger.error(f"Failed to get observability overview stats for customer {customer_id}: {e}")
            raise

    async def get_slowest_endpoints(
        self,
        customer_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get slowest endpoints by average latency"""
        try:
            query = """
            SELECT
                operation_name as endpoint,
                service_name as service,
                count() as request_count,
                avg(duration_ms) as avg_latency_ms,
                quantile(0.5)(duration_ms) as p50_latency_ms,
                quantile(0.95)(duration_ms) as p95_latency_ms,
                quantile(0.99)(duration_ms) as p99_latency_ms,
                countIf(status = 'error') * 100.0 / count() as error_rate
            FROM traces_mt
            WHERE customer_id = %(customer_id)s
              AND start_time >= %(start_time)s
              AND start_time <= %(end_time)s
            GROUP BY operation_name, service_name
            ORDER BY avg_latency_ms DESC
            LIMIT %(limit)s
            """

            results = await self.db.execute_query(query, {
                "customer_id": customer_id,
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit
            })

            return [
                {
                    "endpoint": row["endpoint"],
                    "service": row["service"],
                    "request_count": row["request_count"],
                    "avg_latency_ms": float(row["avg_latency_ms"] or 0),
                    "p50_latency_ms": float(row["p50_latency_ms"] or 0),
                    "p95_latency_ms": float(row["p95_latency_ms"] or 0),
                    "p99_latency_ms": float(row["p99_latency_ms"] or 0),
                    "error_rate": float(row["error_rate"] or 0)
                }
                for row in results
            ] if results else []

        except Exception as e:
            logger.error(f"Failed to get slowest endpoints: {e}", customer_id=customer_id)
            return []

    async def get_error_rates_over_time(
        self,
        customer_id: str,
        start_time: datetime,
        end_time: datetime,
        interval: str = "5m"
    ) -> List[Dict[str, Any]]:
        """Get error rates bucketed by time interval for each service"""
        try:
            # Parse interval to seconds
            interval_seconds = 300  # default 5 minutes
            if interval.endswith('m'):
                interval_seconds = int(interval[:-1]) * 60
            elif interval.endswith('h'):
                interval_seconds = int(interval[:-1]) * 3600

            query = f"""
            SELECT
                toUnixTimestamp(toStartOfInterval(start_time, INTERVAL {interval_seconds} SECOND)) * 1000 as timestamp,
                service_name as service,
                count() as total_requests,
                countIf(status = 'error') as error_count,
                countIf(status = 'error') * 100.0 / count() as error_rate
            FROM traces_mt
            WHERE customer_id = %(customer_id)s
              AND start_time >= %(start_time)s
              AND start_time <= %(end_time)s
            GROUP BY timestamp, service_name
            ORDER BY timestamp ASC, service_name ASC
            """

            results = await self.db.execute_query(query, {
                "customer_id": customer_id,
                "start_time": start_time,
                "end_time": end_time
            })

            return [
                {
                    "timestamp": int(row["timestamp"]),
                    "service": row["service"],
                    "total_requests": row["total_requests"],
                    "error_count": row["error_count"],
                    "error_rate": float(row["error_rate"] or 0)
                }
                for row in results
            ] if results else []

        except Exception as e:
            logger.error(f"Failed to get error rates over time: {e}", customer_id=customer_id)
            return []

    async def get_top_transactions(
        self,
        customer_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top transactions by request count"""
        try:
            # First get total count for percentage calculation
            total_query = """
            SELECT count() as total
            FROM traces_mt
            WHERE customer_id = %(customer_id)s
              AND start_time >= %(start_time)s
              AND start_time <= %(end_time)s
            """

            total_result = await self.db.execute_query(total_query, {
                "customer_id": customer_id,
                "start_time": start_time,
                "end_time": end_time
            })
            total_count = total_result[0]["total"] if total_result else 0

            query = """
            SELECT
                operation_name as name,
                service_name as service,
                count() as count,
                avg(duration_ms) as avg_duration_ms
            FROM traces_mt
            WHERE customer_id = %(customer_id)s
              AND start_time >= %(start_time)s
              AND start_time <= %(end_time)s
            GROUP BY operation_name, service_name
            ORDER BY count DESC
            LIMIT %(limit)s
            """

            results = await self.db.execute_query(query, {
                "customer_id": customer_id,
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit
            })

            return [
                {
                    "name": row["name"],
                    "service": row["service"],
                    "count": row["count"],
                    "avg_duration_ms": float(row["avg_duration_ms"] or 0),
                    "percentage": (row["count"] / total_count * 100) if total_count > 0 else 0
                }
                for row in results
            ] if results else []

        except Exception as e:
            logger.error(f"Failed to get top transactions: {e}", customer_id=customer_id)
            return []

    async def get_service_performance(
        self,
        customer_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """Get performance metrics for all services"""
        try:
            query = """
            SELECT
                service_name,
                count() as request_count,
                avg(duration_ms) as avg_latency_ms,
                quantile(0.5)(duration_ms) as p50_latency_ms,
                quantile(0.95)(duration_ms) as p95_latency_ms,
                quantile(0.99)(duration_ms) as p99_latency_ms,
                countIf(status = 'error') * 100.0 / count() as error_rate,
                count() / (toUnixTimestamp(%(end_time)s) - toUnixTimestamp(%(start_time)s) + 1) as throughput
            FROM traces_mt
            WHERE customer_id = %(customer_id)s
              AND start_time >= %(start_time)s
              AND start_time <= %(end_time)s
            GROUP BY service_name
            ORDER BY request_count DESC
            """

            results = await self.db.execute_query(query, {
                "customer_id": customer_id,
                "start_time": start_time,
                "end_time": end_time
            })

            services = []
            for row in results or []:
                # Calculate apdex score (simplified: satisfied < 100ms, tolerating < 400ms)
                avg_latency = float(row["avg_latency_ms"] or 0)
                error_rate = float(row["error_rate"] or 0)

                # Simple apdex approximation based on avg latency and error rate
                if avg_latency < 100 and error_rate < 1:
                    apdex = 0.95
                elif avg_latency < 200 and error_rate < 3:
                    apdex = 0.85
                elif avg_latency < 400 and error_rate < 5:
                    apdex = 0.70
                else:
                    apdex = max(0.3, 1.0 - (avg_latency / 1000) - (error_rate / 20))

                services.append({
                    "service_name": row["service_name"],
                    "request_count": row["request_count"],
                    "avg_latency_ms": avg_latency,
                    "p50_latency_ms": float(row["p50_latency_ms"] or 0),
                    "p95_latency_ms": float(row["p95_latency_ms"] or 0),
                    "p99_latency_ms": float(row["p99_latency_ms"] or 0),
                    "error_rate": error_rate,
                    "throughput": float(row["throughput"] or 0),
                    "apdex_score": round(apdex, 2)
                })

            return services

        except Exception as e:
            logger.error(f"Failed to get service performance: {e}", customer_id=customer_id)
            return []
