"""
Health and core API endpoints
"""

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from models import HealthResponse
from services.health_service import HealthService

router = APIRouter()

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