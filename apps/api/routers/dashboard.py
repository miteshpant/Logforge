"""
Dashboard API endpoints - M2 core functionality
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from storage_config import get_customer_id

router = APIRouter(prefix="/v1/dashboards")

# Global instances (will be injected)
dashboard_engine = None

def setup_dependencies(de):
    """Setup dependencies from main app"""
    global dashboard_engine
    dashboard_engine = de

class DashboardRequest(BaseModel):
    name: str
    description: str
    widgets: List[Dict[str, Any]]
    layout: Dict[str, Any]
    filters: List[Dict[str, Any]] = []

@router.get("")
async def list_dashboards(request: Request):
    """List all available dashboards for the customer"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")

        if not dashboard_engine:
            raise HTTPException(status_code=500, detail="Dashboard engine not initialized")

        dashboards = dashboard_engine.get_dashboard_list()

        return {
            "dashboards": dashboards,
            "total": len(dashboards),
            "customer_id": customer_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list dashboards: {str(e)}")

@router.get("/{dashboard_id}")
async def get_dashboard_config(dashboard_id: str, request: Request):
    """Get dashboard configuration and metadata"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")

        if not dashboard_engine:
            raise HTTPException(status_code=500, detail="Dashboard engine not initialized")

        dashboard = dashboard_engine.get_dashboard_definition(dashboard_id)

        if not dashboard:
            raise HTTPException(status_code=404, detail="Dashboard not found")

        return dashboard

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard: {str(e)}")

@router.get("/{dashboard_id}/data")
async def get_dashboard_data(dashboard_id: str, request: Request):
    """Get dashboard data with all widget results"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")

        if not dashboard_engine:
            raise HTTPException(status_code=500, detail="Dashboard engine not initialized")

        # Parse time range from query parameters
        from datetime import datetime
        import urllib.parse
        
        time_range = None
        if hasattr(request, 'query_params'):
            start_time_str = request.query_params.get('start_time')
            end_time_str = request.query_params.get('end_time')
            if start_time_str and end_time_str:
                try:
                    start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                    end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                    time_range = {"start_time": start_time, "end_time": end_time}
                except:
                    pass  # Use default time range
        
        # Get dashboard data
        data = await dashboard_engine.get_dashboard_data(dashboard_id, time_range)

        if not data:
            raise HTTPException(status_code=404, detail="Dashboard not found")

        return data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard data: {str(e)}")

@router.post("")
async def create_dashboard(dashboard_request: DashboardRequest, request: Request):
    """Create a new custom dashboard"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")

        # Placeholder for custom dashboard creation
        # This would integrate with a dashboard storage system

        return {
            "status": "created",
            "message": "Custom dashboard creation not yet implemented",
            "customer_id": customer_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create dashboard: {str(e)}")

@router.put("/{dashboard_id}")
async def update_dashboard(dashboard_id: str, dashboard_request: DashboardRequest, request: Request):
    """Update an existing dashboard"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")

        # Placeholder for dashboard update
        return {
            "status": "updated",
            "message": "Dashboard update not yet implemented",
            "customer_id": customer_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update dashboard: {str(e)}")

@router.delete("/{dashboard_id}")
async def delete_dashboard(dashboard_id: str, request: Request):
    """Delete a dashboard"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")

        # Placeholder for dashboard deletion
        return {
            "status": "deleted",
            "message": "Dashboard deletion not yet implemented",
            "customer_id": customer_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete dashboard: {str(e)}")

# Dashboard Widget-Level Endpoints

@router.get("/{dashboard_id}/widgets/{widget_id}/data")
async def get_widget_data(dashboard_id: str, widget_id: str, request: Request):
    """Get data for a specific dashboard widget"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")

        if not dashboard_engine:
            raise HTTPException(status_code=500, detail="Dashboard engine not initialized")

        # Get widget-specific data
        widget_data = await dashboard_engine.get_widget_data(
            dashboard_id,
            widget_id,
            customer_id
        )

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
