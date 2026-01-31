"""
Predictive Analytics API - AI-Powered Forecasting Endpoints

Provides RESTful endpoints for:
- Trend forecasting with configurable metrics and horizons
- Capacity planning with growth rate analysis
- SLA breach prediction per service
- What-if scenario modeling against real baselines
- Combined prediction summary with risk scoring

All endpoints require authentication and tenant isolation via X-Customer-ID.
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import structlog

from services.predictive_analytics_service import PredictiveAnalyticsService
from authn_authz_middleware import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/ai/predictions", tags=["ai-predictions"])


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------

class WhatIfRequest(BaseModel):
    """Request body for what-if scenario modeling."""

    scenario_type: str = Field(
        ...,
        description=(
            "Type of scenario: 'traffic_increase', 'add_services', "
            "'error_rate_change', or 'combined'"
        ),
        examples=["traffic_increase"],
    )
    parameters: Dict[str, Any] = Field(
        ...,
        description=(
            "Scenario parameters. Examples: "
            "{'factor': 2.0} for traffic_increase, "
            "{'count': 5} for add_services, "
            "{'factor': 1.5} for error_rate_change, "
            "{'traffic_factor': 2.0, 'service_count': 3, 'error_factor': 1.2} for combined"
        ),
        examples=[{"factor": 2.0}],
    )


class ForecastResponse(BaseModel):
    """Shape of the trend forecast response."""

    metric: str
    time_range: str
    forecast_horizon: str
    historical: List[Dict[str, Any]]
    projected: List[Dict[str, Any]]
    regression: Dict[str, float]
    data_points: int = 0
    generated_at: str = ""


class CapacityResponse(BaseModel):
    """Shape of the capacity planning response."""

    time_range: str
    analysis_days: int
    current_daily_volume: int = 0
    average_daily_volume: int = 0
    growth_rate_per_day: float = 0.0
    growth_rate_percent: float = 0.0
    r_squared: float = 0.0
    daily_volumes: List[Dict[str, Any]] = []
    capacity_projections: List[Dict[str, Any]] = []
    top_services: List[Dict[str, Any]] = []
    generated_at: str = ""


class SLABreachResponse(BaseModel):
    """Shape of the SLA breach prediction response."""

    time_range: str
    sla_threshold: float
    sla_threshold_pct: float = 0.0
    prediction_horizon_hours: int = 72
    at_risk_services: List[Dict[str, Any]] = []
    total_services_analysed: int = 0
    services_at_risk: int = 0
    generated_at: str = ""


# ---------------------------------------------------------------------------
# Helper to instantiate the service (keeps endpoints clean)
# ---------------------------------------------------------------------------

def _get_service() -> PredictiveAnalyticsService:
    """Return a PredictiveAnalyticsService instance."""
    return PredictiveAnalyticsService()


# ---------------------------------------------------------------------------
# 1. GET /v1/ai/predictions/forecast
# ---------------------------------------------------------------------------

@router.get("/forecast", summary="Trend Forecasting")
async def forecast_trends(
    metric: str = Query(
        "error_rate",
        description="Metric to forecast: error_rate, log_volume, service_count, warn_rate",
    ),
    time_range: str = Query(
        "7d", description="Historical window to analyse (e.g. '7d', '14d', '30d')"
    ),
    forecast_horizon: str = Query(
        "7d", description="How far to project forward (e.g. '7d', '24h')"
    ),
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user=Depends(get_current_user),
):
    """Forecast metric trends using linear regression on real hourly data.

    Queries actual log data from ClickHouse, fits a linear model to hourly
    data points, and projects forward with 95% confidence intervals.

    Supported metrics:
    - **error_rate** -- percentage of ERROR-level logs per hour
    - **log_volume** -- total log count per hour
    - **service_count** -- distinct services emitting logs per hour
    - **warn_rate** -- percentage of WARN-level logs per hour
    """
    try:
        service = _get_service()
        result = await service.forecast_trends(
            customer_id=customer_id,
            metric=metric,
            time_range=time_range,
            forecast_horizon=forecast_horizon,
        )
        return result
    except Exception as exc:
        logger.error(
            "Forecast trends failed",
            error=str(exc),
            customer_id=customer_id,
            metric=metric,
        )
        raise HTTPException(
            status_code=500, detail=f"Forecast failed: {str(exc)}"
        )


# ---------------------------------------------------------------------------
# 2. GET /v1/ai/predictions/capacity
# ---------------------------------------------------------------------------

@router.get("/capacity", summary="Capacity Planning")
async def capacity_planning(
    time_range: str = Query(
        "30d", description="Historical window for growth analysis (e.g. '30d', '90d')"
    ),
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user=Depends(get_current_user),
):
    """Analyse data volume growth and project capacity thresholds.

    Queries daily log volumes from ClickHouse, computes a linear growth
    model, and estimates when pre-defined capacity limits will be reached.
    Also returns top-20 services ranked by volume.
    """
    try:
        service = _get_service()
        result = await service.get_capacity_planning(
            customer_id=customer_id,
            time_range=time_range,
        )
        return result
    except Exception as exc:
        logger.error(
            "Capacity planning failed",
            error=str(exc),
            customer_id=customer_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Capacity planning failed: {str(exc)}"
        )


# ---------------------------------------------------------------------------
# 3. GET /v1/ai/predictions/sla-breach
# ---------------------------------------------------------------------------

@router.get("/sla-breach", summary="SLA Breach Prediction")
async def sla_breach_prediction(
    time_range: str = Query(
        "7d", description="Historical window for trend analysis (e.g. '7d', '14d')"
    ),
    sla_threshold: float = Query(
        0.01,
        description="Error rate SLA threshold as a fraction (0.01 = 1%)",
        ge=0.0001,
        le=1.0,
    ),
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user=Depends(get_current_user),
):
    """Predict which services risk breaching SLA error-rate thresholds.

    Computes hourly error-rate trends per service using linear regression
    and flags services whose projected error rate will exceed the SLA
    threshold within the next 72 hours. Results are sorted by risk level.
    """
    try:
        service = _get_service()
        result = await service.predict_sla_breaches(
            customer_id=customer_id,
            time_range=time_range,
            sla_threshold=sla_threshold,
        )
        return result
    except Exception as exc:
        logger.error(
            "SLA breach prediction failed",
            error=str(exc),
            customer_id=customer_id,
        )
        raise HTTPException(
            status_code=500, detail=f"SLA breach prediction failed: {str(exc)}"
        )


# ---------------------------------------------------------------------------
# 4. POST /v1/ai/predictions/what-if
# ---------------------------------------------------------------------------

@router.post("/what-if", summary="What-If Scenario Modeling")
async def what_if_scenario(
    request: WhatIfRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user=Depends(get_current_user),
):
    """Model the impact of hypothetical changes against real baselines.

    Queries current 24-hour metrics from ClickHouse and applies the
    specified scenario to project impact on log volumes, error rates,
    service counts, and capacity.

    **Scenario types:**
    - `traffic_increase` -- multiply traffic by `factor`
    - `add_services` -- add `count` new services
    - `error_rate_change` -- multiply error rate by `factor`
    - `combined` -- apply multiple changes at once
    """
    try:
        service = _get_service()
        result = await service.run_what_if_scenario(
            customer_id=customer_id,
            scenario_type=request.scenario_type,
            parameters=request.parameters,
        )
        return result
    except Exception as exc:
        logger.error(
            "What-if scenario failed",
            error=str(exc),
            customer_id=customer_id,
            scenario_type=request.scenario_type,
        )
        raise HTTPException(
            status_code=500, detail=f"What-if scenario failed: {str(exc)}"
        )


# ---------------------------------------------------------------------------
# 5. GET /v1/ai/predictions/summary
# ---------------------------------------------------------------------------

@router.get("/summary", summary="Prediction Summary")
async def prediction_summary(
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user=Depends(get_current_user),
):
    """Combined prediction summary with overall risk scoring.

    Runs trend forecasting, capacity planning, and SLA breach prediction
    with sensible defaults, then aggregates the results into a single
    payload with an overall risk score (0--100) and risk level.
    """
    try:
        service = _get_service()
        result = await service.get_prediction_summary(customer_id=customer_id)
        return result
    except Exception as exc:
        logger.error(
            "Prediction summary failed",
            error=str(exc),
            customer_id=customer_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Prediction summary failed: {str(exc)}"
        )
