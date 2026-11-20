"""
Logforge API - Modular FastAPI Application
"""

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

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
from routers.security_api import router as security_router
from routers.cases_api import router as cases_router
from routers.threat_intel_api import router as threat_intel_router
from routers.pipelines_api import router as pipelines_router
from routers.fields_api import router as fields_router
from routers.lookups_api import router as lookups_router
from routers.searches_api import router as searches_router
from routers.packs_api import router as packs_router
from routers.observability_api import router as observability_router
from routers.ai_api import router as ai_router
from routers.ai_assistant_api import router as ai_assistant_router
from routers.entities_api import router as entities_router
from routers.storage_tiers_api import router as storage_tiers_router
from routers.integrations_api import router as integrations_router, hooks_router
from routers.playbooks_api import router as playbooks_router
from routers.reports_api import router as reports_router
from routers.sso_api import login_router as sso_login_router, router as sso_router
from routers.enterprise_api import router as enterprise_router
from routers.tenant_api import router as tenant_router
from routers.subscription_api import router as subscription_router
from routers.streaming_api import router as streaming_router
from routers.streaming_config_api import router as streaming_config_router
from routers.schema_registry_api import router as schema_registry_router
from routers.alert_correlation_api import router as alert_correlation_router
from routers.predictive_api import router as predictive_router

# Import M8 User Service routers
from routers.user_api import router as user_router
from routers.auth_api import router as auth_router
from routers.role_api import router as role_router
from routers.usage_api import router as usage_router
from routers.quota_management_api import router as quota_management_router

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

# Decode gzip-compressed request bodies (shippers compress batches), with the
# decompressed size capped at the request body limit. Registered first, so it
# is innermost: auth and the compressed-size check run before it.
from request_decompression import RequestDecompressionMiddleware
app.add_middleware(RequestDecompressionMiddleware)

# Add GZip compression middleware for responses > 1KB
# Reduces bandwidth by 60-80% for JSON responses
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add unified authentication & authorization middleware
from authn_authz_middleware import setup_unified_auth_middleware
setup_unified_auth_middleware(app)

# ENH-012: request body size caps and per-tenant rate limiting.
#
# Registered AFTER the auth middleware deliberately. Starlette applies
# middleware in reverse registration order, so this runs BEFORE authentication
# -- an oversized or rate-limited request is rejected without paying for JWT
# validation and the database lookups that auth performs.
from request_limits import setup_request_limits
setup_request_limits(app)

# ENH-019: RED metrics. Registered last so it runs FIRST and therefore observes
# every request -- including those rejected by rate limiting or authentication,
# which are exactly the ones an on-call engineer needs to see.
from self_metrics import MetricsMiddleware
app.add_middleware(MetricsMiddleware)

# CORS is registered LAST so it is the OUTERMOST layer. Every response then
# carries CORS headers -- including the 401/403/429 that the auth and
# rate-limit middleware return without reaching a route. Registered earlier
# (inside those layers), such errors reached the browser without
# Access-Control-Allow-Origin and surfaced as an opaque "CORS error", so the UI
# could not see the 401 and react to it (e.g. by sending the user to /login).
app.add_middleware(
    CORSMiddleware,
    allow_origins=config["cors_origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(health_router, tags=["Health"])
app.include_router(ingestion_router, tags=["Ingestion"])
app.include_router(lookups_router)
app.include_router(searches_router)
app.include_router(packs_router)
app.include_router(query_router, tags=["Query"])
app.include_router(dashboard_router, tags=["Dashboards"])
app.include_router(storage_router, tags=["Storage"])
app.include_router(alerts_router, tags=["Alerts"])

# Include M8 User Service routers
app.include_router(user_router)
app.include_router(auth_router)
app.include_router(role_router)
app.include_router(usage_router)
app.include_router(quota_management_router, tags=["Quota Management"])

# Include additional API routers
# Cases first: its /v1/security/cases/... routes must win over the security
# router's /{detection_id}/... patterns.
app.include_router(cases_router)
app.include_router(threat_intel_router)
app.include_router(pipelines_router)
app.include_router(fields_router)
app.include_router(security_router)
app.include_router(observability_router)
app.include_router(ai_router)
app.include_router(ai_assistant_router)
app.include_router(entities_router)
app.include_router(storage_tiers_router)
app.include_router(integrations_router)
app.include_router(hooks_router)
app.include_router(playbooks_router)
app.include_router(reports_router)
app.include_router(sso_login_router)
app.include_router(sso_router)
app.include_router(enterprise_router)
app.include_router(tenant_router)
app.include_router(subscription_router)
app.include_router(streaming_router)
app.include_router(streaming_config_router)
app.include_router(schema_registry_router)
app.include_router(alert_correlation_router)
app.include_router(predictive_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
