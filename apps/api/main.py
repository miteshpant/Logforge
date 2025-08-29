"""
Logforge API - Modular FastAPI Application
"""

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app_config import load_config, setup_logging
from dependencies import lifespan

# Import all routers
from routers.health import router as health_router
from routers.ingestion import router as ingestion_router
from routers.query import router as query_router
from routers.dashboard import router as dashboard_router
from routers.storage import router as storage_router
from routers.alerts import router as alerts_router

# Import API routers for additional functionality
from test_runner_api import router as test_runner_router
from security_api import router as security_router
from observability_api import router as observability_router

# Configure structured logging
logger = structlog.get_logger()

# Load configuration
config = load_config()
setup_logging(config)

# Create FastAPI app with lifespan management
app = FastAPI(
    title="Logforge API",
    description="Open Observability + SIEM Platform API",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config["cors_origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(health_router)
app.include_router(ingestion_router)
app.include_router(query_router)
app.include_router(dashboard_router)
app.include_router(storage_router)
app.include_router(alerts_router)

# Include additional API routers
app.include_router(test_runner_router)
app.include_router(security_router)
app.include_router(observability_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )