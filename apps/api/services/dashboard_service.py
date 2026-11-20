"""
Dashboard Service - Business Logic Layer
Handles dashboard management, validation, and integration with dashboard engine
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
import structlog
import os

from dao.dashboard_dao import DashboardDAO

logger = structlog.get_logger()

class DashboardService:
    """Service layer for dashboard operations and business logic"""
    
    def __init__(self):
        self.dashboard_dao = DashboardDAO()
        # Dashboard engine will be injected
        self.dashboard_engine = None
        self.service_name = "DashboardService"
        self.service_key = os.getenv('DASHBOARD_SERVICE_KEY', 'dashboard-service-key-dev')
    
    def set_dashboard_engine(self, dashboard_engine):
        """Set dashboard engine for data generation"""
        self.dashboard_engine = dashboard_engine
    
    async def create_dashboard(self, dashboard_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new dashboard with validation"""
        try:
            # Validate required fields
            required_fields = ['customer_id', 'name']
            for field in required_fields:
                if field not in dashboard_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate dashboard structure
            if 'layout' in dashboard_data and not isinstance(dashboard_data['layout'], dict):
                raise ValueError("Dashboard layout must be a dictionary")
            
            if 'filters' in dashboard_data and not isinstance(dashboard_data['filters'], list):
                raise ValueError("Dashboard filters must be a list")
            
            # Set defaults
            dashboard_data.setdefault('description', '')
            dashboard_data.setdefault('layout', {'columns': 2, 'rows': 2})
            dashboard_data.setdefault('filters', [])
            dashboard_data.setdefault('tags', [])
            dashboard_data.setdefault('is_public', False)
            dashboard_data.setdefault('is_default', False)
            dashboard_data.setdefault('created_by', 'system')
            
            # Save to database
            dashboard_id = await self.dashboard_dao.save_dashboard(dashboard_data)
            
            logger.info("Dashboard created successfully", 
                       dashboard_id=dashboard_id, 
                       customer_id=dashboard_data['customer_id'],
                       name=dashboard_data['name'])
            
            return {
                "status": "created",
                "dashboard_id": dashboard_id,
                "message": "Dashboard created successfully",
                "customer_id": dashboard_data['customer_id']
            }
            
        except Exception as e:
            logger.error("Failed to create dashboard", error=str(e))
            raise e
    
    async def get_dashboard(self, dashboard_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get dashboard with validation"""
        try:
            # Validate inputs
            if not dashboard_id or not customer_id:
                raise ValueError("Dashboard ID and customer ID are required")
            
            # Get from database
            dashboard_data = await self.dashboard_dao.get_dashboard(dashboard_id, customer_id)
            
            if dashboard_data:
                logger.info("Retrieved dashboard", dashboard_id=dashboard_id, customer_id=customer_id)
                return dashboard_data
            else:
                logger.warning("Dashboard not found", dashboard_id=dashboard_id, customer_id=customer_id)
                return None
                
        except Exception as e:
            logger.error("Failed to get dashboard", error=str(e), dashboard_id=dashboard_id)
            return None
    
    async def list_dashboards(self, customer_id: str, 
                             created_by: Optional[str] = None,
                             is_public: Optional[bool] = None,
                             include_default: bool = True,
                             limit: int = 50) -> Dict[str, Any]:
        """List dashboards with filtering and default dashboards"""
        try:
            # Validate inputs
            if not customer_id:
                raise ValueError("Customer ID is required")
            
            if limit > 100:
                limit = 100  # Enforce maximum limit
            
            # Get custom dashboards from database
            custom_dashboards = await self.dashboard_dao.list_dashboards(
                customer_id=customer_id,
                created_by=created_by,
                is_public=is_public,
                limit=limit
            )
            
            all_dashboards = custom_dashboards.copy()
            
            # Add default/built-in dashboards if requested
            if include_default and self.dashboard_engine:
                try:
                    default_dashboards = self.dashboard_engine.get_dashboard_list()
                    # Mark default dashboards
                    for dashboard in default_dashboards:
                        dashboard['is_default'] = True
                        dashboard['customer_id'] = customer_id
                        dashboard['created_by'] = 'system'
                    
                    all_dashboards.extend(default_dashboards)
                except Exception as e:
                    logger.warning("Failed to get default dashboards", error=str(e))
            
            logger.info("Listed dashboards", 
                       customer_id=customer_id, 
                       custom_count=len(custom_dashboards),
                       total_count=len(all_dashboards))
            
            return {
                "dashboards": all_dashboards,
                "total": len(all_dashboards),
                "custom_count": len(custom_dashboards),
                "customer_id": customer_id,
                "filters": {
                    "created_by": created_by,
                    "is_public": is_public,
                    "include_default": include_default,
                    "limit": limit
                }
            }
            
        except Exception as e:
            logger.error("Failed to list dashboards", error=str(e), customer_id=customer_id)
            return {"dashboards": [], "total": 0, "custom_count": 0, "customer_id": customer_id}
    
    async def update_dashboard(self, dashboard_id: str, customer_id: str, 
                              update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update dashboard with validation"""
        try:
            # Validate inputs
            if not dashboard_id or not customer_id:
                raise ValueError("Dashboard ID and customer ID are required")
            
            # Validate update fields
            allowed_fields = ['name', 'description', 'layout', 'filters', 'tags', 'is_public', 'is_default']
            filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields}
            
            if not filtered_data:
                raise ValueError("No valid fields to update")
            
            # Validate field types
            if 'layout' in filtered_data and not isinstance(filtered_data['layout'], dict):
                raise ValueError("Dashboard layout must be a dictionary")
            
            if 'filters' in filtered_data and not isinstance(filtered_data['filters'], list):
                raise ValueError("Dashboard filters must be a list")
            
            # Update in database
            success = await self.dashboard_dao.update_dashboard(dashboard_id, customer_id, filtered_data)
            
            if success:
                logger.info("Dashboard updated successfully", dashboard_id=dashboard_id, customer_id=customer_id)
                return {
                    "status": "updated",
                    "dashboard_id": dashboard_id,
                    "message": "Dashboard updated successfully",
                    "customer_id": customer_id
                }
            else:
                raise ValueError("Dashboard not found or update failed")
                
        except Exception as e:
            logger.error("Failed to update dashboard", error=str(e), dashboard_id=dashboard_id)
            raise e
    
    async def delete_dashboard(self, dashboard_id: str, customer_id: str) -> Dict[str, Any]:
        """Delete dashboard with validation"""
        try:
            # Validate inputs
            if not dashboard_id or not customer_id:
                raise ValueError("Dashboard ID and customer ID are required")
            
            # Delete from database
            success = await self.dashboard_dao.delete_dashboard(dashboard_id, customer_id)
            
            if success:
                logger.info("Dashboard deleted successfully", dashboard_id=dashboard_id, customer_id=customer_id)
                return {
                    "status": "deleted",
                    "dashboard_id": dashboard_id,
                    "message": "Dashboard deleted successfully",
                    "customer_id": customer_id
                }
            else:
                raise ValueError("Dashboard not found or deletion failed")
                
        except Exception as e:
            logger.error("Failed to delete dashboard", error=str(e), dashboard_id=dashboard_id)
            raise e
    
    async def get_dashboard_data(self, dashboard_id: str, customer_id: str, 
                                time_range: Optional[Dict[str, Any]] = None,
                                variables: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Get dashboard data with widget results"""
        try:
            # First check if it's a custom dashboard in database
            dashboard = await self.dashboard_dao.get_dashboard(dashboard_id, customer_id)
            
            if dashboard:
                # Custom dashboard - generate data for each widget
                dashboard_data = {
                    "dashboard_id": dashboard_id,
                    "name": dashboard["name"],
                    "description": dashboard["description"],
                    "layout": dashboard["layout"],
                    "filters": dashboard["filters"],
                    "widgets": []
                }
                
                # Generate data for each widget
                for widget in dashboard["widgets"]:
                    widget_data = await self._generate_widget_data(widget, customer_id, time_range, variables)
                    dashboard_data["widgets"].append({
                        "widget_id": widget["id"],
                        "name": widget["name"],
                        "type": widget["type"],
                        "data": widget_data,
                        "position": widget["position"],
                        "size": widget["size"]
                    })
                
                return dashboard_data
            
            # If not custom dashboard, try default dashboard engine
            elif self.dashboard_engine:
                return await self.dashboard_engine.get_dashboard_data(dashboard_id, time_range)
            
            return None
            
        except Exception as e:
            logger.error("Failed to get dashboard data", error=str(e), dashboard_id=dashboard_id)
            return None
    
    async def get_widget_data(self, dashboard_id: str, widget_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get data for a specific widget"""
        try:
            # Get dashboard to find the widget
            dashboard = await self.dashboard_dao.get_dashboard(dashboard_id, customer_id)
            
            if dashboard:
                # Find the specific widget
                widget = next((w for w in dashboard["widgets"] if w["id"] == widget_id), None)
                if widget:
                    widget_data = await self._generate_widget_data(widget, customer_id)
                    return widget_data
            
            # If not custom dashboard/widget, try dashboard engine
            elif self.dashboard_engine:
                return await self.dashboard_engine.get_widget_data(dashboard_id, widget_id, customer_id)
            
            return None
            
        except Exception as e:
            logger.error("Failed to get widget data", error=str(e), widget_id=widget_id)
            return None
    
    async def _generate_widget_data(self, widget: Dict[str, Any], customer_id: str, 
                                   time_range: Optional[Dict[str, Any]] = None,
                                   variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate data for a widget based on its query definition using DAO"""
        try:
            widget_type = widget.get("type", "chart")
            query_definition = widget.get("query_definition", {})
            widget_id = widget.get("id", "unknown")
            
            # Build time range for queries (default 24 hours)
            if not time_range:
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(hours=24)
            else:
                # The router passes datetimes; older callers pass ISO strings.
                # (Only strings were handled, so every custom widget failed
                # whenever the UI sent a time range.)
                start_time, end_time = time_range["start_time"], time_range["end_time"]
                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                if isinstance(end_time, str):
                    end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            
            # Phase 6: a query panel (query_definition = {"logql": "..."}).
            if isinstance(query_definition, dict) and query_definition.get("logql"):
                import dashboard_queries

                if start_time.tzinfo is None:
                    start_time, end_time = (start_time.replace(tzinfo=timezone.utc),
                                            end_time.replace(tzinfo=timezone.utc))
                return await dashboard_queries.panel_data(widget, customer_id, start_time, end_time, variables or {})

            # Execute query based on widget type using DAO
            if widget_type == "line_chart":
                return await self._generate_line_chart_data(customer_id, query_definition, start_time, end_time)
            elif widget_type == "bar_chart":
                return await self._generate_bar_chart_data(customer_id, query_definition, start_time, end_time)
            elif widget_type == "metric":
                return await self._generate_metric_data(customer_id, query_definition, start_time, end_time)
            elif widget_type == "table":
                return await self._generate_table_data(customer_id, query_definition, start_time, end_time)
            else:
                logger.warning("Unsupported widget type", widget_type=widget_type, widget_id=widget_id)
                return {
                    "message": f"Widget type '{widget_type}' not implemented",
                    "query_definition": query_definition
                }
                
        except Exception as e:
            logger.error("Failed to generate widget data", error=str(e), widget_id=widget.get("id"))
            return {"error": str(e)}
    
    async def _generate_line_chart_data(self, customer_id: str, query_definition: Dict[str, Any], 
                                       start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate line chart data using DAO"""
        try:
            # Get time series data via DAO
            result = await self.dashboard_dao.get_time_series_data(
                customer_id, query_definition, start_time, end_time
            )
            
            # Return formatted data from DAO
            if result:
                return result
            
            return {"series": [], "labels": [], "query_definition": query_definition}
            
        except Exception as e:
            logger.error("Failed to generate line chart data", error=str(e))
            return {"series": [], "labels": [], "query_definition": query_definition, "error": str(e)}
    
    async def _generate_bar_chart_data(self, customer_id: str, query_definition: Dict[str, Any],
                                      start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate bar chart data using DAO"""
        try:
            # Get categorical aggregation data via DAO
            result = await self.dashboard_dao.get_categorical_data(
                customer_id, query_definition, start_time, end_time
            )
            
            # Return formatted data from DAO
            if result:
                return result
            
            return {"series": [], "labels": [], "query_definition": query_definition}
            
        except Exception as e:
            logger.error("Failed to generate bar chart data", error=str(e))
            return {"series": [], "labels": [], "query_definition": query_definition, "error": str(e)}
    
    async def _generate_metric_data(self, customer_id: str, query_definition: Dict[str, Any],
                                   start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate single metric data using DAO"""
        try:
            # Get metric data via DAO
            result = await self.dashboard_dao.get_metric_data(
                customer_id, query_definition, start_time, end_time
            )
            
            # Return formatted data from DAO
            if result:
                return result
            
            return {"value": 0, "formatted_value": "0", "change": "0%", "trend": "stable", "query_definition": query_definition}
            
        except Exception as e:
            logger.error("Failed to generate metric data", error=str(e))
            return {"value": 0, "formatted_value": "0", "change": "0%", "trend": "stable", "query_definition": query_definition, "error": str(e)}
    
    async def _generate_table_data(self, customer_id: str, query_definition: Dict[str, Any],
                                  start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate table data using DAO"""
        try:
            # Get table data via DAO
            result = await self.dashboard_dao.get_table_data(
                customer_id, query_definition, start_time, end_time
            )
            
            # Return formatted data from DAO
            if result:
                return result
            
            return {"headers": [], "rows": [], "total": 0, "query_definition": query_definition}
            
        except Exception as e:
            logger.error("Failed to generate table data", error=str(e))
            return {"headers": [], "rows": [], "total": 0, "query_definition": query_definition, "error": str(e)}
    
    # Widget management methods
    
    async def create_widget(self, widget_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new dashboard widget"""
        try:
            # Validate required fields
            required_fields = ['dashboard_id', 'customer_id', 'name', 'type']
            for field in required_fields:
                if field not in widget_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Set defaults
            widget_data.setdefault('query_definition', {})
            widget_data.setdefault('visualization_config', {})
            widget_data.setdefault('position', {'x': 0, 'y': 0})
            widget_data.setdefault('size', {'width': 6, 'height': 4})
            widget_data.setdefault('refresh_interval', 300)
            
            # Save to database
            widget_id = await self.dashboard_dao.save_dashboard_widget(widget_data)
            
            logger.info("Dashboard widget created", widget_id=widget_id, dashboard_id=widget_data['dashboard_id'])
            
            return {
                "status": "created",
                "widget_id": widget_id,
                "message": "Widget created successfully",
                "dashboard_id": widget_data['dashboard_id']
            }
            
        except Exception as e:
            logger.error("Failed to create widget", error=str(e))
            raise e
    
    async def update_widget(self, widget_id: str, customer_id: str, 
                           update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update dashboard widget"""
        try:
            # Validate inputs
            if not widget_id or not customer_id:
                raise ValueError("Widget ID and customer ID are required")
            
            # Validate update fields
            allowed_fields = ['name', 'type', 'query_definition', 'visualization_config', 
                            'position', 'size', 'refresh_interval']
            filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields}
            
            if not filtered_data:
                raise ValueError("No valid fields to update")
            
            # Update in database
            success = await self.dashboard_dao.update_dashboard_widget(widget_id, customer_id, filtered_data)
            
            if success:
                logger.info("Widget updated successfully", widget_id=widget_id, customer_id=customer_id)
                return {
                    "status": "updated",
                    "widget_id": widget_id,
                    "message": "Widget updated successfully",
                    "customer_id": customer_id
                }
            else:
                raise ValueError("Widget not found or update failed")
                
        except Exception as e:
            logger.error("Failed to update widget", error=str(e), widget_id=widget_id)
            raise e
    
    async def delete_widget(self, widget_id: str, customer_id: str) -> Dict[str, Any]:
        """Delete dashboard widget"""
        try:
            # Validate inputs
            if not widget_id or not customer_id:
                raise ValueError("Widget ID and customer ID are required")
            
            # Delete from database
            success = await self.dashboard_dao.delete_dashboard_widget(widget_id, customer_id)
            
            if success:
                logger.info("Widget deleted successfully", widget_id=widget_id, customer_id=customer_id)
                return {
                    "status": "deleted",
                    "widget_id": widget_id,
                    "message": "Widget deleted successfully",
                    "customer_id": customer_id
                }
            else:
                raise ValueError("Widget not found or deletion failed")
                
        except Exception as e:
            logger.error("Failed to delete widget", error=str(e), widget_id=widget_id)
            raise e
    
    # Dashboard sharing methods
    
    async def share_dashboard(self, dashboard_id: str, customer_id: str, 
                             share_data: Dict[str, Any]) -> Dict[str, Any]:
        """Share dashboard with another user or tenant"""
        try:
            # Validate required fields
            if not dashboard_id or not customer_id:
                raise ValueError("Dashboard ID and customer ID are required")
            
            if not share_data.get('shared_with_email') and not share_data.get('shared_with_tenant'):
                raise ValueError("Must specify either shared_with_email or shared_with_tenant")
            
            # Set defaults
            share_data.setdefault('permission_level', 'view')
            share_data.setdefault('created_by', 'system')
            
            # Create share record
            share_id = await self.dashboard_dao.share_dashboard(dashboard_id, customer_id, share_data)
            
            logger.info("Dashboard shared", share_id=share_id, dashboard_id=dashboard_id)
            
            return {
                "status": "shared",
                "share_id": share_id,
                "message": "Dashboard shared successfully",
                "dashboard_id": dashboard_id
            }
            
        except Exception as e:
            logger.error("Failed to share dashboard", error=str(e), dashboard_id=dashboard_id)
            raise e
    
    async def get_dashboard_shares(self, dashboard_id: str, customer_id: str) -> List[Dict[str, Any]]:
        """Get dashboard sharing information"""
        try:
            shares = await self.dashboard_dao.get_dashboard_shares(dashboard_id, customer_id)
            logger.info("Retrieved dashboard shares", dashboard_id=dashboard_id, count=len(shares))
            return shares
            
        except Exception as e:
            logger.error("Failed to get dashboard shares", error=str(e), dashboard_id=dashboard_id)
            return []