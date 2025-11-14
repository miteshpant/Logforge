"""
Streaming Configuration API
Manage customer-specific streaming filters for metrics and traces
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import structlog

from services.streaming_config_service import get_streaming_config_service
from constants.streaming_config import (
    STREAMING_CONFIG_METRICS_KEY, STREAMING_CONFIG_TRACES_KEY
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/streaming/config", tags=["streaming-config"])


# Pydantic Models
class MetricsStreamingConfig(BaseModel):
    """Configuration for metrics streaming filters"""
    enabled: bool = Field(default=True, description="Enable/disable metrics streaming")
    sample_rate: float = Field(default=0.1, ge=0.0, le=1.0, description="Sample rate (0.0-1.0)")
    min_metrics_count: int = Field(default=1, ge=1, description="Minimum metrics in batch to stream")
    include_services: List[str] = Field(default=[], description="Only stream these services (empty = all)")
    exclude_services: List[str] = Field(default=[], description="Never stream these services")
    priority_metrics: List[str] = Field(default=[], description="Always stream these metric names")
    max_events_per_minute: int = Field(default=100, ge=1, description="Rate limit per minute")
    include_errors_only: bool = Field(default=False, description="Only stream metrics with errors")
    min_value_change_threshold: float = Field(default=0.05, ge=0.0, description="Minimum change to stream")


class TracesStreamingConfig(BaseModel):
    """Configuration for traces streaming filters"""
    enabled: bool = Field(default=True, description="Enable/disable traces streaming")
    sample_rate: float = Field(default=0.05, ge=0.0, le=1.0, description="Sample rate (0.0-1.0)")
    min_traces_count: int = Field(default=1, ge=1, description="Minimum traces in batch to stream")
    include_services: List[str] = Field(default=[], description="Only stream these services (empty = all)")
    exclude_services: List[str] = Field(default=[], description="Never stream these services")
    min_duration_ms: int = Field(default=100, ge=0, description="Minimum trace duration to stream")
    include_errors_only: bool = Field(default=False, description="Only stream traces with errors")
    max_events_per_minute: int = Field(default=50, ge=1, description="Rate limit per minute")
    priority_operations: List[str] = Field(default=[], description="Always stream these operations")
    include_status: List[str] = Field(default=["ok", "error"], description="Status codes to stream")


class StreamingConfigResponse(BaseModel):
    """Response for streaming configuration operations"""
    success: bool
    message: str
    config: Optional[Dict[str, Any]] = None


class AllConfigsResponse(BaseModel):
    """Response for getting all streaming configurations"""
    customer_id: str
    configs: Dict[str, Any]
    using_defaults: Dict[str, bool]


def get_current_user_id():
    """Mock function for getting current user ID - replace with actual auth"""
    return "system"


@router.get("/", response_model=AllConfigsResponse)
async def get_all_streaming_configs(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get all streaming configurations for a customer"""
    try:
        service = get_streaming_config_service()
        configs = await service.get_all_customer_configs(customer_id)
        
        # Check which configs are using defaults
        using_defaults = {}
        for event_type in configs.keys():
            config_key = None
            if event_type == "metrics.batch.ingested":
                config_key = STREAMING_CONFIG_METRICS_KEY
            elif event_type == "traces.batch.ingested":
                config_key = STREAMING_CONFIG_TRACES_KEY
            
            if config_key:
                db_config = await service.get_customer_streaming_config_from_db(customer_id, config_key)
                using_defaults[event_type] = db_config is None
        
        return AllConfigsResponse(
            customer_id=customer_id,
            configs=configs,
            using_defaults=using_defaults
        )
        
    except Exception as e:
        logger.error(f"Failed to get streaming configs for {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get configurations: {str(e)}")


@router.get("/metrics", response_model=Dict[str, Any])
async def get_metrics_streaming_config(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get metrics streaming configuration for a customer"""
    try:
        service = get_streaming_config_service()
        config = await service.get_streaming_config(customer_id, "metrics.batch.ingested")
        
        return {
            "customer_id": customer_id,
            "event_type": "metrics.batch.ingested",
            "config": config
        }
        
    except Exception as e:
        logger.error(f"Failed to get metrics config for {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics configuration: {str(e)}")


@router.post("/metrics", response_model=StreamingConfigResponse)
async def set_metrics_streaming_config(
    config: MetricsStreamingConfig,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: str = Depends(get_current_user_id)
):
    """Set metrics streaming configuration for a customer"""
    try:
        service = get_streaming_config_service()
        
        success = await service.set_streaming_config(
            customer_id=customer_id,
            config_key=STREAMING_CONFIG_METRICS_KEY,
            config=config.dict(),
            created_by=current_user
        )
        
        if success:
            return StreamingConfigResponse(
                success=True,
                message="Metrics streaming configuration updated successfully",
                config=config.dict()
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to save configuration")
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to set metrics config for {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to set metrics configuration: {str(e)}")


@router.get("/traces", response_model=Dict[str, Any])
async def get_traces_streaming_config(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get traces streaming configuration for a customer"""
    try:
        service = get_streaming_config_service()
        config = await service.get_streaming_config(customer_id, "traces.batch.ingested")
        
        return {
            "customer_id": customer_id,
            "event_type": "traces.batch.ingested",
            "config": config
        }
        
    except Exception as e:
        logger.error(f"Failed to get traces config for {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get traces configuration: {str(e)}")


@router.post("/traces", response_model=StreamingConfigResponse)
async def set_traces_streaming_config(
    config: TracesStreamingConfig,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: str = Depends(get_current_user_id)
):
    """Set traces streaming configuration for a customer"""
    try:
        service = get_streaming_config_service()
        
        success = await service.set_streaming_config(
            customer_id=customer_id,
            config_key=STREAMING_CONFIG_TRACES_KEY,
            config=config.dict(),
            created_by=current_user
        )
        
        if success:
            return StreamingConfigResponse(
                success=True,
                message="Traces streaming configuration updated successfully",
                config=config.dict()
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to save configuration")
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to set traces config for {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to set traces configuration: {str(e)}")


@router.delete("/metrics", response_model=StreamingConfigResponse)
async def delete_metrics_streaming_config(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Delete metrics streaming configuration (reverts to defaults)"""
    try:
        service = get_streaming_config_service()
        
        success = await service.delete_streaming_config(customer_id, STREAMING_CONFIG_METRICS_KEY)
        
        if success:
            return StreamingConfigResponse(
                success=True,
                message="Metrics streaming configuration deleted, reverted to defaults"
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to delete configuration")
            
    except Exception as e:
        logger.error(f"Failed to delete metrics config for {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete metrics configuration: {str(e)}")


@router.delete("/traces", response_model=StreamingConfigResponse)
async def delete_traces_streaming_config(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Delete traces streaming configuration (reverts to defaults)"""
    try:
        service = get_streaming_config_service()
        
        success = await service.delete_streaming_config(customer_id, STREAMING_CONFIG_TRACES_KEY)
        
        if success:
            return StreamingConfigResponse(
                success=True,
                message="Traces streaming configuration deleted, reverted to defaults"
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to delete configuration")
            
    except Exception as e:
        logger.error(f"Failed to delete traces config for {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete traces configuration: {str(e)}")