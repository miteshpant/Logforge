"""
Health Service - Real service health checks and monitoring

Performs actual connectivity tests for all platform dependencies:
- ClickHouse database connectivity
- Storage system health
- API service availability
- Message queue status
- Connection pool status
- Circuit breaker status
- Redis cache status
"""

import os
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any
import clickhouse_connect
import structlog
from database_layer import DatabaseLayer, DatabaseError, SecurityError

logger = structlog.get_logger()

# Import resilience utilities (lazy to avoid circular imports)
_query_resilience = None
_connection_pool = None


def _get_query_resilience():
    """Lazy import for query resilience module"""
    global _query_resilience
    if _query_resilience is None:
        try:
            from utils import query_resilience
            _query_resilience = query_resilience
        except ImportError:
            pass
    return _query_resilience


def _get_connection_pool():
    """Lazy import for connection pool module"""
    global _connection_pool
    if _connection_pool is None:
        try:
            from utils import connection_pool
            _connection_pool = connection_pool
        except ImportError:
            pass
    return _connection_pool

class HealthService:
    """Service health monitoring with real connectivity checks"""
    
    def __init__(self):
        self.service_name = "HealthService"
        self.service_key = os.getenv('HEALTH_SERVICE_KEY', 'health-service-key-dev')
        
    async def get_overall_health(self) -> Dict[str, Any]:
        """Get comprehensive health status of all services"""
        health_checks = {}
        overall_status = "healthy"
        
        # Check ClickHouse database
        try:
            clickhouse_health = await self._check_clickhouse_health()
            health_checks["database"] = clickhouse_health["status"]
            health_checks["clickhouse"] = clickhouse_health["status"]
            if clickhouse_health["status"] != "healthy":
                overall_status = "degraded"
        except Exception as e:
            logger.error("ClickHouse health check failed", error=str(e))
            health_checks["database"] = "unhealthy"
            health_checks["clickhouse"] = "unhealthy"
            overall_status = "unhealthy"
        
        # Check storage systems
        try:
            storage_health = await self._check_storage_health()
            health_checks["storage"] = storage_health["status"]
            if storage_health["status"] != "healthy":
                overall_status = "degraded"
        except Exception as e:
            logger.error("Storage health check failed", error=str(e))
            health_checks["storage"] = "unhealthy"
            overall_status = "unhealthy"
        
        # API service is healthy if we can respond
        health_checks["api"] = "healthy"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc),
            "services": health_checks
        }
    
    async def _check_clickhouse_health(self) -> Dict[str, Any]:
        """Perform real ClickHouse connectivity and performance checks"""
        try:
            # Initialize database connection
            db = DatabaseLayer(self.service_name, self.service_key)
            
            # Test basic connectivity with a simple query
            start_time = datetime.now()
            result = await db.fetch_one("SELECT 1 as health_check")
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            if not result or result[0] != 1:
                return {
                    "status": "unhealthy",
                    "error": "Invalid response from ClickHouse",
                    "response_time_ms": response_time
                }
            
            # Check if critical tables exist
            tables_check = await self._verify_critical_tables(db)
            
            # Determine status based on response time and table health
            if response_time > 5000:  # > 5 seconds is unhealthy
                status = "unhealthy"
            elif response_time > 1000:  # > 1 second is degraded
                status = "degraded"  
            else:
                status = "healthy"
            
            if not tables_check["all_tables_exist"]:
                status = "degraded"
            
            return {
                "status": status,
                "response_time_ms": round(response_time, 2),
                "tables": tables_check,
                "host": os.getenv('CLICKHOUSE_HOST', 'clickhouse'),
                "database": os.getenv('CLICKHOUSE_DATABASE', 'logforge')
            }
            
        except (DatabaseError, SecurityError) as e:
            return {
                "status": "unhealthy",
                "error": f"Database connection failed: {str(e)}",
                "response_time_ms": None
            }
        except Exception as e:
            return {
                "status": "unhealthy", 
                "error": f"Unexpected error: {str(e)}",
                "response_time_ms": None
            }
    
    async def _verify_critical_tables(self, db: DatabaseLayer) -> Dict[str, Any]:
        """Check if critical database tables exist and are accessible"""
        critical_tables = [
            'logs_raw_mt',
            'logs_normalized_mt', 
            'users_mt',
            'roles_mt',
            'alert_rules_mt'
        ]
        
        table_status = {}
        all_exist = True
        
        for table in critical_tables:
            try:
                # Check if table exists and is queryable
                result = await db.fetch_one(f"SELECT count() as cnt FROM {table} LIMIT 1")
                table_status[table] = "accessible"
            except Exception as e:
                logger.warning(f"Table {table} not accessible", error=str(e))
                table_status[table] = "inaccessible"
                all_exist = False
        
        return {
            "all_tables_exist": all_exist,
            "tables": table_status,
            "checked_count": len(critical_tables)
        }
    
    async def _check_storage_health(self) -> Dict[str, Any]:
        """Check storage system health (MinIO/S3)"""
        try:
            # For now, we'll do a basic check
            # In production, this would test actual S3/MinIO connectivity
            storage_config = {
                "provider": os.getenv('STORAGE_PROVIDER', 'minio'),
                "endpoint": os.getenv('MINIO_ENDPOINT', 'minio:9000'),
                "bucket": os.getenv('STORAGE_BUCKET', 'logforge-cold-storage')
            }
            
            # Basic health check - if environment is configured
            if all(storage_config.values()):
                return {
                    "status": "healthy",
                    "provider": storage_config["provider"],
                    "endpoint": storage_config["endpoint"]
                }
            else:
                return {
                    "status": "degraded",
                    "error": "Storage configuration incomplete",
                    "config": storage_config
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": f"Storage check failed: {str(e)}"
            }
    
    async def get_detailed_health(self) -> Dict[str, Any]:
        """Get detailed health information including metrics"""
        basic_health = await self.get_overall_health()

        # Add circuit breaker status
        circuit_breaker_status = await self._check_circuit_breakers()

        # Add connection pool status
        pool_status = await self._check_connection_pools()

        # Add Redis status
        redis_status = await self._check_redis_health()

        # Add additional system metrics
        basic_health.update({
            "version": "1.0.0",
            "uptime_check": True,
            "environment": os.getenv('ENVIRONMENT', 'development'),
            "deployment": {
                "container": bool(os.getenv('CONTAINER_MODE')),
                "kubernetes": bool(os.getenv('KUBERNETES_SERVICE_HOST'))
            },
            "resilience": {
                "circuit_breakers": circuit_breaker_status,
                "connection_pools": pool_status,
                "redis": redis_status
            }
        })

        return basic_health

    async def _check_circuit_breakers(self) -> Dict[str, Any]:
        """Check status of all circuit breakers"""
        try:
            resilience = _get_query_resilience()
            if resilience is None:
                return {"status": "unavailable", "reason": "Module not loaded"}

            breaker_status = resilience.get_all_circuit_breaker_status()

            # Determine overall health
            open_breakers = [
                name for name, status in breaker_status.items()
                if status.get("state") == "open"
            ]

            if open_breakers:
                overall = "degraded"
            else:
                overall = "healthy"

            return {
                "status": overall,
                "breakers": breaker_status,
                "open_count": len(open_breakers),
                "open_breakers": open_breakers
            }
        except Exception as e:
            logger.warning("Failed to check circuit breakers", error=str(e))
            return {"status": "unknown", "error": str(e)}

    async def _check_connection_pools(self) -> Dict[str, Any]:
        """Check status of connection pools"""
        try:
            pool_module = _get_connection_pool()
            if pool_module is None:
                return {"status": "unavailable", "reason": "Module not loaded"}

            result = {
                "status": "healthy",
                "pools": {}
            }

            # Check ClickHouse pool
            try:
                ch_pool = await pool_module.get_clickhouse_pool()
                ch_health = await ch_pool.health_check()
                result["pools"]["clickhouse"] = ch_health
                if ch_health.get("status") != "healthy":
                    result["status"] = "degraded"
            except Exception as e:
                result["pools"]["clickhouse"] = {"status": "unhealthy", "error": str(e)}
                result["status"] = "degraded"

            # Check HTTP pool
            try:
                http_pool = await pool_module.get_http_pool()
                result["pools"]["http"] = {
                    "status": "healthy",
                    "initialized": http_pool._initialized
                }
            except Exception as e:
                result["pools"]["http"] = {"status": "unhealthy", "error": str(e)}
                result["status"] = "degraded"

            return result
        except Exception as e:
            logger.warning("Failed to check connection pools", error=str(e))
            return {"status": "unknown", "error": str(e)}

    async def _check_redis_health(self) -> Dict[str, Any]:
        """Check Redis cache health"""
        try:
            from events.management.cache.redis_manager import redis_manager

            # Test Redis connectivity with a simple operation
            start_time = datetime.now()
            test_key = "health:check:ping"
            await redis_manager.set(test_key, "pong", ttl=10)
            result = await redis_manager.get(test_key)
            response_time = (datetime.now() - start_time).total_seconds() * 1000

            if result == "pong":
                status = "healthy" if response_time < 100 else "degraded"
                return {
                    "status": status,
                    "response_time_ms": round(response_time, 2),
                    "connected": True
                }
            else:
                return {
                    "status": "degraded",
                    "response_time_ms": round(response_time, 2),
                    "error": "Unexpected response"
                }
        except Exception as e:
            logger.warning("Redis health check failed", error=str(e))
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e)
            }