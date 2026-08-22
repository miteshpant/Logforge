"""
Alert Correlation API - Smart alert grouping, fatigue analysis, and noise reduction.
Provides endpoints for correlated alert groups, fatigue scoring, service dependency
correlation, duplicate detection, trend analysis, and a combined summary view.
"""

import structlog
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any

from services.alert_correlation_service import AlertCorrelationService
from authn_authz_middleware import get_current_user
from models import User

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/alerts/correlation", tags=["alert-correlation"])

# Shared service instance
# ENH-010: `AlertCorrelationService()` opens a database connection in its constructor, so
# building it at import time made this router un-importable -- and untestable --
# without live infrastructure. Built on first use; the PEP 562 hook below
# preserves the bare `correlation_service` name at every call site.
_correlation_service_instance: Optional[AlertCorrelationService] = None


def get_correlation_service() -> AlertCorrelationService:
    """Get the shared AlertCorrelationService, constructing it on first use."""
    global _correlation_service_instance
    if _correlation_service_instance is None:
        _correlation_service_instance = AlertCorrelationService()
    return _correlation_service_instance


def __getattr__(name: str):
    """Resolve `correlation_service` lazily (PEP 562)."""
    if name == "correlation_service":
        return get_correlation_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class RootAlertDetail(BaseModel):
    alert_id: str
    rule_name: str
    severity: str
    triggered_at: str

class MemberAlertDetail(BaseModel):
    alert_id: str
    rule_name: str
    severity: str
    status: str
    triggered_at: str

class AlertGroup(BaseModel):
    group_id: str
    root_alert: RootAlertDetail
    member_alerts: List[MemberAlertDetail]
    group_size: int
    correlation_score: int
    common_severities: List[str]
    common_rules: List[str]
    common_services: List[str]
    suggested_root_cause: str

class CorrelatedGroupsResponse(BaseModel):
    groups: List[AlertGroup]
    total_alerts_analysed: int
    total_groups: int
    time_range: str

class ContributingFactor(BaseModel):
    factor: str
    score_contribution: float

class FatigueScoreResponse(BaseModel):
    fatigue_score: int
    rating: str
    contributing_factors: List[Dict[str, Any]]
    recommendations: List[str]

class ServiceGroupDetail(BaseModel):
    service: str
    alert_count: int
    error_log_count: int
    first_error: Optional[str] = None
    last_error: Optional[str] = None
    severities: List[str]

class CrossServiceCorrelation(BaseModel):
    upstream_service: str
    downstream_service: str
    time_gap_seconds: float
    correlation_confidence: float

class ServiceDependencyResponse(BaseModel):
    service_groups: List[ServiceGroupDetail]
    cross_service_correlations: List[CrossServiceCorrelation]
    total_services: int
    total_correlations: int
    time_range: str

class DuplicateGroupDetail(BaseModel):
    rule_id: str
    rule_name: str
    severity: str
    total_count: int
    suppressible_count: int
    first_fired: str
    last_fired: str
    span_minutes: int

class DuplicateDetectionResponse(BaseModel):
    duplicate_groups: List[DuplicateGroupDetail]
    total_duplicate_groups: int
    total_alerts: int
    total_suppressible: int
    noise_reduction_percent: float
    time_range: str

class TrendDirection(BaseModel):
    direction: str
    change_percent: float

class TrendSummary(BaseModel):
    total_alerts: int
    total_buckets: int
    peak_bucket: Optional[str] = None
    peak_count: int

class TimeBucket(BaseModel):
    timestamp: str
    total: int
    by_severity: Dict[str, int]
    by_status: Dict[str, int]

class AlertTrendResponse(BaseModel):
    time_series: List[TimeBucket]
    trend: TrendDirection
    summary: TrendSummary
    time_range: str
    granularity: str

class CorrelationSummaryResponse(BaseModel):
    fatigue: FatigueScoreResponse
    groups: CorrelatedGroupsResponse
    duplicates: DuplicateDetectionResponse
    trends: AlertTrendResponse
    service_dependencies: ServiceDependencyResponse


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/groups", response_model=CorrelatedGroupsResponse)
async def get_correlated_groups(
    time_range: str = "24h",
    min_group_size: int = 2,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve correlated alert groups.

    Alerts that fired within 5 minutes of each other and share the same
    rule or severity are grouped together. Each group includes a root
    alert, member list, correlation score, and a suggested root cause.
    """
    try:
        result = await get_correlation_service().get_correlated_alert_groups(
            customer_id=customer_id,
            time_range=time_range,
            min_group_size=min_group_size,
        )
        return result

    except Exception as e:
        logger.error(
            "Failed to get correlated alert groups",
            error=str(e),
            customer_id=customer_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve correlated alert groups: {str(e)}",
        )


@router.get("/fatigue-score", response_model=FatigueScoreResponse)
async def get_fatigue_score(
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user),
):
    """
    Calculate the alert fatigue score for this tenant.

    The score ranges from 0 (healthy) to 100 (critical fatigue) and is
    based on alert volume, duplicate rate, acknowledgment rate, and
    average resolution time.
    """
    try:
        result = await get_correlation_service().calculate_fatigue_score(
            customer_id=customer_id,
        )
        return result

    except Exception as e:
        logger.error(
            "Failed to calculate fatigue score",
            error=str(e),
            customer_id=customer_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate alert fatigue score: {str(e)}",
        )


@router.get("/service-dependencies", response_model=ServiceDependencyResponse)
async def get_service_dependencies(
    time_range: str = "24h",
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user),
):
    """
    Identify service dependency correlations.

    Cross-references alert data with error-level log patterns to find
    services that error together, implying upstream / downstream
    relationships.
    """
    try:
        result = await get_correlation_service().get_service_dependency_alerts(
            customer_id=customer_id,
            time_range=time_range,
        )
        return result

    except Exception as e:
        logger.error(
            "Failed to get service dependency alerts",
            error=str(e),
            customer_id=customer_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve service dependency alerts: {str(e)}",
        )


@router.get("/duplicates", response_model=DuplicateDetectionResponse)
async def get_duplicates(
    time_range: str = "24h",
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user),
):
    """
    Detect duplicate alerts that could be suppressed.

    Groups alerts by rule and identifies instances that fired repeatedly
    within a short window. Returns the number of suppressible alerts and
    the potential noise reduction percentage.
    """
    try:
        result = await get_correlation_service().get_duplicate_alerts(
            customer_id=customer_id,
            time_range=time_range,
        )
        return result

    except Exception as e:
        logger.error(
            "Failed to detect duplicate alerts",
            error=str(e),
            customer_id=customer_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to detect duplicate alerts: {str(e)}",
        )


@router.get("/trends", response_model=AlertTrendResponse)
async def get_trends(
    time_range: str = "7d",
    granularity: str = "1h",
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve alert trend analysis over a configurable window.

    Returns time-bucketed alert counts broken down by severity and status,
    along with a trend indicator (increasing / decreasing / stable).
    """
    try:
        result = await get_correlation_service().get_alert_trends(
            customer_id=customer_id,
            time_range=time_range,
            granularity=granularity,
        )
        return result

    except Exception as e:
        logger.error(
            "Failed to get alert trends",
            error=str(e),
            customer_id=customer_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve alert trends: {str(e)}",
        )


@router.get("/summary", response_model=CorrelationSummaryResponse)
async def get_correlation_summary(
    time_range: str = "24h",
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve a combined summary of all correlation insights.

    This is a convenience endpoint that aggregates fatigue score,
    correlated groups, duplicate detection, trend analysis, and
    service dependency data into a single response.
    """
    try:
        fatigue = await get_correlation_service().calculate_fatigue_score(
            customer_id=customer_id,
        )
        groups = await get_correlation_service().get_correlated_alert_groups(
            customer_id=customer_id,
            time_range=time_range,
        )
        duplicates = await get_correlation_service().get_duplicate_alerts(
            customer_id=customer_id,
            time_range=time_range,
        )
        trends = await get_correlation_service().get_alert_trends(
            customer_id=customer_id,
            time_range=time_range,
            granularity="1h",
        )
        service_deps = await get_correlation_service().get_service_dependency_alerts(
            customer_id=customer_id,
            time_range=time_range,
        )

        return {
            "fatigue": fatigue,
            "groups": groups,
            "duplicates": duplicates,
            "trends": trends,
            "service_dependencies": service_deps,
        }

    except Exception as e:
        logger.error(
            "Failed to get correlation summary",
            error=str(e),
            customer_id=customer_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve correlation summary: {str(e)}",
        )
