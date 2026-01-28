"""
Health and core API endpoints
"""

from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from models import HealthResponse
from services.health_service import HealthService

router = APIRouter()


def _get_circuit_breaker_status() -> Dict[str, Any]:
    """Get circuit breaker status (lazy import to avoid circular deps)"""
    try:
        from utils.query_resilience import get_all_circuit_breaker_status
        return get_all_circuit_breaker_status()
    except ImportError:
        return {"error": "Module not available"}

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Real health check endpoint with actual service connectivity tests"""
    try:
        health_service = HealthService()
        health_status = await health_service.get_overall_health()
        
        return HealthResponse(
            status=health_status["status"],
            timestamp=health_status["timestamp"],
            services=health_status["services"]
        )
    except Exception as e:
        # If health service itself fails, return unhealthy status
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.now(timezone.utc),
            services={
                "api": "degraded",
                "database": "unknown", 
                "clickhouse": "unknown",
                "storage": "unknown",
                "error": f"Health service failed: {str(e)}"
            }
        )

@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with comprehensive metrics and diagnostics"""
    try:
        health_service = HealthService()
        return await health_service.get_detailed_health()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Health service unavailable: {str(e)}"
        )

@router.get("/health/resilience")
async def resilience_status():
    """Get circuit breaker and connection pool status for monitoring"""
    try:
        health_service = HealthService()

        circuit_breakers = await health_service._check_circuit_breakers()
        connection_pools = await health_service._check_connection_pools()

        # Determine overall resilience status
        overall = "healthy"
        if circuit_breakers.get("status") == "degraded":
            overall = "degraded"
        if connection_pools.get("status") == "degraded":
            overall = "degraded"
        if circuit_breakers.get("status") == "unhealthy" or connection_pools.get("status") == "unhealthy":
            overall = "unhealthy"

        return {
            "status": overall,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "circuit_breakers": circuit_breakers,
            "connection_pools": connection_pools
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Resilience status unavailable: {str(e)}"
        )


@router.get("/health/ready")
async def readiness_check():
    """
    Kubernetes-style readiness probe.
    Returns 200 if the service is ready to receive traffic.
    """
    try:
        health_service = HealthService()
        health_status = await health_service.get_overall_health()

        if health_status["status"] == "unhealthy":
            raise HTTPException(
                status_code=503,
                detail="Service not ready"
            )

        return {
            "status": "ready",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Readiness check failed: {str(e)}"
        )


@router.get("/health/live")
async def liveness_check():
    """
    Kubernetes-style liveness probe.
    Returns 200 if the service is alive (even if degraded).
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/")
async def root():
    """Root endpoint with basic info"""
    return {
        "message": "Logforge API - Advanced observability and SIEM platform",
        "version": "1.0.0",
        "docs": "/docs",
        "features": [
            "Multi-format log ingestion",
            "Advanced query engine",
            "Real-time dashboards",
            "Rule-based alerting",
            "Security analytics",
            "Distributed tracing",
            "Metrics collection"
        ]
    }