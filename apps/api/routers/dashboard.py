"""
Dashboard API endpoints - M2 core functionality
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel
import structlog

from storage_config import get_customer_id
from tenant_dependencies import MiddlewareTenant
from services.dashboard_service import DashboardService

logger = structlog.get_logger()

router = APIRouter(prefix="/v1/dashboards")

# Global instances (will be injected)
dashboard_engine = None
# ENH-010: `DashboardService()` opens a database connection in its constructor, so
# building it at import time made this router un-importable -- and untestable --
# without live infrastructure. Built on first use; the PEP 562 hook below
# preserves the bare `dashboard_service` name at every call site.
_dashboard_service_instance: Optional[DashboardService] = None


def get_dashboard_service() -> DashboardService:
    """Get the shared DashboardService, constructing it on first use."""
    global _dashboard_service_instance
    if _dashboard_service_instance is None:
        _dashboard_service_instance = DashboardService()
    return _dashboard_service_instance


def __getattr__(name: str):
    """Resolve `dashboard_service` lazily (PEP 562)."""
    if name == "dashboard_service":
        return get_dashboard_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def setup_dependencies(de):
    """Setup dependencies from main app"""
    global dashboard_engine
    dashboard_engine = de
    get_dashboard_service().set_dashboard_engine(de)

class DashboardRequest(BaseModel):
    name: str
    description: str = ""
    widgets: List[Dict[str, Any]] = []
    layout: Dict[str, Any] = {}
    filters: List[Dict[str, Any]] = []
    tags: List[str] = []
    is_public: bool = False

class WidgetRequest(BaseModel):
    name: str
    type: str  # chart, table, metric, etc.
    query_definition: Dict[str, Any] = {}
    visualization_config: Dict[str, Any] = {}
    position: Dict[str, Any] = {}
    size: Dict[str, Any] = {}
    refresh_interval: int = 300

class ShareRequest(BaseModel):
    shared_with_email: Optional[str] = None
    shared_with_tenant: Optional[str] = None
    permission_level: str = "view"  # view, edit, admin
    expires_at: Optional[str] = None
    created_by: str = "system"

@router.get("")
async def list_dashboards(
    created_by: str = Query(None, description="Filter by creator"),
    is_public: bool = Query(None, description="Filter public/private dashboards"),
    include_default: bool = Query(True, description="Include default dashboards"),
    limit: int = Query(50, description="Maximum number of dashboards to return"),
    customer_id: str = MiddlewareTenant
):
    """List all available dashboards for the customer"""
    try:
        result = await get_dashboard_service().list_dashboards(
            customer_id=customer_id,
            created_by=created_by,
            is_public=is_public,
            include_default=include_default,
            limit=limit
        )
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list dashboards: {str(e)}")

@router.get("/{dashboard_id}")
async def get_dashboard_config(dashboard_id: str, customer_id: str = MiddlewareTenant):
    """Get dashboard configuration and metadata"""
    try:
        dashboard = await get_dashboard_service().get_dashboard(dashboard_id, customer_id)

        if not dashboard:
            # Try default dashboard engine as fallback
            if dashboard_engine:
                dashboard_def = dashboard_engine.get_dashboard_definition(dashboard_id)
                if dashboard_def:
                    # Convert Pydantic model to dict and add customer_id
                    dashboard = dashboard_def.model_dump()
                    dashboard['customer_id'] = customer_id
                    return dashboard

            raise HTTPException(status_code=404, detail="Dashboard not found")

        return dashboard

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard: {str(e)}")

@router.get("/{dashboard_id}/data")
async def get_dashboard_data(
    dashboard_id: str,
    start_time: str = Query(None, description="Start time for data range"),
    end_time: str = Query(None, description="End time for data range"),
    customer_id: str = MiddlewareTenant
):
    """Get dashboard data with all widget results"""
    try:
        # Parse time range from query parameters
        time_range = None
        if start_time and end_time:
            try:
                from datetime import datetime
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                time_range = {"start_time": start_dt, "end_time": end_dt}
            except Exception as e:
                logger.warning("Invalid time range format", error=str(e))

        # Get dashboard data
        data = await get_dashboard_service().get_dashboard_data(dashboard_id, customer_id, time_range)

        if not data:
            raise HTTPException(status_code=404, detail="Dashboard not found")

        return data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard data: {str(e)}")

@router.post("")
async def create_dashboard(dashboard_request: DashboardRequest, customer_id: str = MiddlewareTenant):
    """Create a new custom dashboard"""
    try:
        # Add customer_id to dashboard data
        dashboard_data = dashboard_request.model_dump()
        dashboard_data['customer_id'] = customer_id

        # Create dashboard
        result = await get_dashboard_service().create_dashboard(dashboard_data)
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create dashboard: {str(e)}")

@router.put("/{dashboard_id}")
async def update_dashboard(dashboard_id: str, dashboard_request: DashboardRequest, customer_id: str = MiddlewareTenant):
    """Update an existing dashboard"""
    try:
        # Update dashboard
        update_data = dashboard_request.model_dump()
        result = await get_dashboard_service().update_dashboard(dashboard_id, customer_id, update_data)
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update dashboard: {str(e)}")

@router.delete("/{dashboard_id}")
async def delete_dashboard(dashboard_id: str, customer_id: str = MiddlewareTenant):
    """Delete a dashboard"""
    try:
        result = await get_dashboard_service().delete_dashboard(dashboard_id, customer_id)
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete dashboard: {str(e)}")

# Dashboard Widget-Level Endpoints

@router.get("/{dashboard_id}/widgets/{widget_id}/data")
async def get_widget_data(dashboard_id: str, widget_id: str, customer_id: str = MiddlewareTenant):
    """Get data for a specific dashboard widget"""
    try:
        # Get widget-specific data
        widget_data = await get_dashboard_service().get_widget_data(dashboard_id, widget_id, customer_id)

        if not widget_data:
            raise HTTPException(status_code=404, detail="Widget not found")

        return {
            "dashboard_id": dashboard_id,
            "widget_id": widget_id,
            "data": widget_data,
            "customer_id": customer_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get widget data: {str(e)}")

# Widget Management Endpoints

@router.post("/{dashboard_id}/widgets")
async def create_widget(dashboard_id: str, widget_request: WidgetRequest, customer_id: str = MiddlewareTenant):
    """Create a new dashboard widget"""
    try:
        # Add dashboard_id and customer_id to widget data
        widget_data = widget_request.model_dump()
        widget_data['dashboard_id'] = dashboard_id
        widget_data['customer_id'] = customer_id

        result = await get_dashboard_service().create_widget(widget_data)
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create widget: {str(e)}")

@router.put("/{dashboard_id}/widgets/{widget_id}")
async def update_widget(dashboard_id: str, widget_id: str, widget_request: WidgetRequest, customer_id: str = MiddlewareTenant):
    """Update a dashboard widget"""
    try:
        update_data = widget_request.model_dump()
        result = await get_dashboard_service().update_widget(widget_id, customer_id, update_data)
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update widget: {str(e)}")

@router.delete("/{dashboard_id}/widgets/{widget_id}")
async def delete_widget(dashboard_id: str, widget_id: str, customer_id: str = MiddlewareTenant):
    """Delete a dashboard widget"""
    try:
        result = await get_dashboard_service().delete_widget(widget_id, customer_id)
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete widget: {str(e)}")

# Dashboard Sharing Endpoints

@router.post("/{dashboard_id}/share")
async def share_dashboard(dashboard_id: str, share_request: ShareRequest, customer_id: str = MiddlewareTenant):
    """Share dashboard with another user or tenant"""
    try:
        # Validate the dashboard_id format - reject template placeholders
        if dashboard_id.startswith('{{') and dashboard_id.endswith('}}'):
            raise HTTPException(status_code=400, detail="Invalid dashboard ID: template placeholder not allowed")
        
        # First validate that the dashboard exists
        dashboard = await get_dashboard_service().get_dashboard(dashboard_id, customer_id)
        
        # If not found in custom dashboards, check default dashboards
        if not dashboard and dashboard_engine:
            dashboard = dashboard_engine.get_dashboard_definition(dashboard_id)
        
        if not dashboard:
            raise HTTPException(status_code=404, detail=f"Dashboard '{dashboard_id}' not found")
        
        share_data = share_request.model_dump()
        result = await get_dashboard_service().share_dashboard(dashboard_id, customer_id, share_data)
        return result

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to share dashboard: {str(e)}")

@router.get("/{dashboard_id}/shares")
async def get_dashboard_shares(dashboard_id: str, customer_id: str = MiddlewareTenant):
    """Get dashboard sharing information"""
    try:
        shares = await get_dashboard_service().get_dashboard_shares(dashboard_id, customer_id)
        return {
            "dashboard_id": dashboard_id,
            "shares": shares,
            "total": len(shares),
            "customer_id": customer_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard shares: {str(e)}")
