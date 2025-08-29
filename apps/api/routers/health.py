"""
Health and core API endpoints
"""

from datetime import datetime, timezone
from fastapi import APIRouter
from models import HealthResponse

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        services={
            "api": "healthy",
            "database": "healthy",
            "clickhouse": "healthy",
            "storage": "healthy"
        }
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