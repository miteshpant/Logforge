"""
Dashboard Data Access Object (DAO)
Handles all database operations for dashboard management
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import structlog
import json

from database_layer import DatabaseLayer
from constants.database_constants import (
    STATUS_ACTIVE, STATUS_INACTIVE,
    DASHBOARDS_TABLE, DASHBOARD_WIDGETS_TABLE, DASHBOARD_SHARES_TABLE
)

logger = structlog.get_logger()

class DashboardDAO:
    """Data Access Object for Dashboard operations"""
    
    def __init__(self):
        self.db = DatabaseLayer("DashboardDAO", "dashboard-dao-service-key")
    
    async def save_dashboard(self, dashboard_data: Dict[str, Any]) -> str:
        """Save a dashboard in database"""
        try:
            dashboard_id = str(uuid.uuid4())
            
            db_dashboard_data = {
                'id': dashboard_id,
                'customer_id': dashboard_data['customer_id'],
                'name': dashboard_data['name'],
                'description': dashboard_data.get('description', ''),
                'layout': json.dumps(dashboard_data.get('layout', {})),
                'filters': json.dumps(dashboard_data.get('filters', [])),
                'tags': json.dumps(dashboard_data.get('tags', [])),
                'is_public': dashboard_data.get('is_public', False),
                'is_default': dashboard_data.get('is_default', False),
                'created_by': dashboard_data.get('created_by', 'system'),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc),
                'status': STATUS_ACTIVE
            }
            
            await self.db.execute_query(
                f"""INSERT INTO {DASHBOARDS_TABLE} 
                   (id, customer_id, name, description, layout, filters, tags, 
                    is_public, is_default, created_by, created_at, updated_at, status)
                   VALUES (%(id)s, %(customer_id)s, %(name)s, %(description)s, %(layout)s,
                   %(filters)s, %(tags)s, %(is_public)s, %(is_default)s, %(created_by)s, 
                   %(created_at)s, %(updated_at)s, %(status)s)""",
                db_dashboard_data
            )
            
            logger.info("Dashboard saved to database", dashboard_id=dashboard_id, customer_id=dashboard_data['customer_id'])
            return dashboard_id
            
        except Exception as e:
            logger.error("Failed to save dashboard to database", error=str(e))
            raise e
    
    async def get_dashboard(self, dashboard_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get dashboard by ID from database"""
        try:
            result = await self.db.execute_query(
                f"""SELECT * FROM {DASHBOARDS_TABLE} 
                   WHERE id = %(dashboard_id)s AND customer_id = %(customer_id)s 
                   AND status = %(status)s""",
                {"dashboard_id": dashboard_id, "customer_id": customer_id, "status": STATUS_ACTIVE}
            )
            
            if result:
                dashboard_data = dict(result[0])
                # Parse JSON fields
                dashboard_data['layout'] = json.loads(dashboard_data['layout'])
                dashboard_data['filters'] = json.loads(dashboard_data['filters']) if dashboard_data['filters'] else []
                dashboard_data['tags'] = json.loads(dashboard_data['tags']) if dashboard_data['tags'] else []
                
                # Get dashboard widgets
                dashboard_data['widgets'] = await self.get_dashboard_widgets(dashboard_id, customer_id)
                
                return dashboard_data
            return None
            
        except Exception as e:
            logger.error("Failed to get dashboard", error=str(e), dashboard_id=dashboard_id)
            return None
    
    async def list_dashboards(self, customer_id: str, 
                             created_by: Optional[str] = None,
                             is_public: Optional[bool] = None,
                             limit: int = 50) -> List[Dict[str, Any]]:
        """List dashboards for a customer from database"""
        try:
            query = f"""SELECT * FROM {DASHBOARDS_TABLE} 
                       WHERE customer_id = %(customer_id)s AND status = %(status)s"""
            params = {"customer_id": customer_id, "status": STATUS_ACTIVE, "limit": limit}
            
            if created_by:
                query += " AND created_by = %(created_by)s"
                params["created_by"] = created_by
                
            if is_public is not None:
                query += " AND is_public = %(is_public)s"
                params["is_public"] = is_public
            
            query += " ORDER BY updated_at DESC LIMIT %(limit)s"
            
            result = await self.db.execute_query(query, params)
            
            dashboards = []
            for row in result:
                dashboard_data = dict(row)
                # Parse JSON fields
                dashboard_data['layout'] = json.loads(dashboard_data['layout'])
                dashboard_data['filters'] = json.loads(dashboard_data['filters']) if dashboard_data['filters'] else []
                dashboard_data['tags'] = json.loads(dashboard_data['tags']) if dashboard_data['tags'] else []
                dashboards.append(dashboard_data)
            
            return dashboards
            
        except Exception as e:
            logger.error("Failed to list dashboards", error=str(e), customer_id=customer_id)
            return []
    
    async def update_dashboard(self, dashboard_id: str, customer_id: str, 
                              update_data: Dict[str, Any]) -> bool:
        """Update dashboard in database"""
        try:
            # Build dynamic update query
            set_clauses = []
            params = {'dashboard_id': dashboard_id, 'customer_id': customer_id}
            
            for field, value in update_data.items():
                if field in ['name', 'description', 'layout', 'filters', 'tags', 'is_public', 'is_default']:
                    if field in ['layout', 'filters', 'tags']:
                        value = json.dumps(value)
                    set_clauses.append(f"{field} = %({field})s")
                    params[field] = value
            
            if not set_clauses:
                return False
            
            set_clauses.append("updated_at = %(updated_at)s")
            params["updated_at"] = datetime.now(timezone.utc)
                
            # ClickHouse requires ALTER TABLE ... UPDATE syntax
            set_clause = ', '.join(set_clauses)
            query = f"""ALTER TABLE {DASHBOARDS_TABLE} UPDATE {set_clause} 
                       WHERE id = %(dashboard_id)s AND customer_id = %(customer_id)s"""
            
            await self.db.execute_query(query, params)
            
            logger.info("Dashboard updated", dashboard_id=dashboard_id, customer_id=customer_id)
            return True
            
        except Exception as e:
            logger.error("Failed to update dashboard", error=str(e), dashboard_id=dashboard_id)
            return False
    
    async def delete_dashboard(self, dashboard_id: str, customer_id: str) -> bool:
        """Delete (deactivate) dashboard in database"""
        try:
            # ClickHouse requires ALTER TABLE ... UPDATE syntax
            await self.db.execute_query(
                f"""ALTER TABLE {DASHBOARDS_TABLE} UPDATE 
                   status = %(status)s, updated_at = %(updated_at)s
                   WHERE id = %(dashboard_id)s AND customer_id = %(customer_id)s""",
                {
                    "status": STATUS_INACTIVE,
                    "updated_at": datetime.now(timezone.utc),
                    "dashboard_id": dashboard_id,
                    "customer_id": customer_id
                }
            )
            
            logger.info("Dashboard deleted", dashboard_id=dashboard_id, customer_id=customer_id)
            return True
            
        except Exception as e:
            logger.error("Failed to delete dashboard", error=str(e), dashboard_id=dashboard_id)
            return False
    
    # Dashboard Widget operations
    
    async def save_dashboard_widget(self, widget_data: Dict[str, Any]) -> str:
        """Save a dashboard widget in database"""
        try:
            widget_id = str(uuid.uuid4())
            
            db_widget_data = {
                'id': widget_id,
                'dashboard_id': widget_data['dashboard_id'],
                'customer_id': widget_data['customer_id'],
                'name': widget_data['name'],
                'type': widget_data['type'],  # chart, table, metric, etc.
                'query_definition': json.dumps(widget_data.get('query_definition', {})),
                'visualization_config': json.dumps(widget_data.get('visualization_config', {})),
                'position': json.dumps(widget_data.get('position', {})),
                'size': json.dumps(widget_data.get('size', {})),
                'refresh_interval': widget_data.get('refresh_interval', 300),  # seconds
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc),
                'status': STATUS_ACTIVE
            }
            
            await self.db.execute_query(
                f"""INSERT INTO {DASHBOARD_WIDGETS_TABLE} 
                   (id, dashboard_id, customer_id, name, type, query_definition, 
                    visualization_config, position, size, refresh_interval, created_at, updated_at, status)
                   VALUES (%(id)s, %(dashboard_id)s, %(customer_id)s, %(name)s, %(type)s, 
                   %(query_definition)s, %(visualization_config)s, %(position)s, %(size)s, 
                   %(refresh_interval)s, %(created_at)s, %(updated_at)s, %(status)s)""",
                db_widget_data
            )
            
            logger.info("Dashboard widget saved", widget_id=widget_id, dashboard_id=widget_data['dashboard_id'])
            return widget_id
            
        except Exception as e:
            logger.error("Failed to save dashboard widget", error=str(e))
            raise e
    
    async def get_dashboard_widgets(self, dashboard_id: str, customer_id: str) -> List[Dict[str, Any]]:
        """Get all widgets for a dashboard"""
        try:
            result = await self.db.execute_query(
                f"""SELECT * FROM {DASHBOARD_WIDGETS_TABLE} 
                   WHERE dashboard_id = %(dashboard_id)s AND customer_id = %(customer_id)s 
                   AND status = %(status)s ORDER BY created_at""",
                {"dashboard_id": dashboard_id, "customer_id": customer_id, "status": STATUS_ACTIVE}
            )
            
            widgets = []
            for row in result:
                widget_data = dict(row)
                # Parse JSON fields
                widget_data['query_definition'] = json.loads(widget_data['query_definition'])
                widget_data['visualization_config'] = json.loads(widget_data['visualization_config'])
                widget_data['position'] = json.loads(widget_data['position'])
                widget_data['size'] = json.loads(widget_data['size'])
                widgets.append(widget_data)
            
            return widgets
            
        except Exception as e:
            logger.error("Failed to get dashboard widgets", error=str(e), dashboard_id=dashboard_id)
            return []
    
    async def update_dashboard_widget(self, widget_id: str, customer_id: str, 
                                     update_data: Dict[str, Any]) -> bool:
        """Update dashboard widget in database"""
        try:
            # Build dynamic update query
            set_clauses = []
            params = {'widget_id': widget_id, 'customer_id': customer_id}
            
            for field, value in update_data.items():
                if field in ['name', 'type', 'query_definition', 'visualization_config', 
                            'position', 'size', 'refresh_interval']:
                    if field in ['query_definition', 'visualization_config', 'position', 'size']:
                        value = json.dumps(value)
                    set_clauses.append(f"{field} = %({field})s")
                    params[field] = value
            
            if not set_clauses:
                return False
            
            set_clauses.append("updated_at = %(updated_at)s")
            params["updated_at"] = datetime.now(timezone.utc)
                
            # ClickHouse requires ALTER TABLE ... UPDATE syntax
            set_clause = ', '.join(set_clauses)
            query = f"""ALTER TABLE {DASHBOARD_WIDGETS_TABLE} UPDATE {set_clause} 
                       WHERE id = %(widget_id)s AND customer_id = %(customer_id)s"""
            
            await self.db.execute_query(query, params)
            
            logger.info("Dashboard widget updated", widget_id=widget_id, customer_id=customer_id)
            return True
            
        except Exception as e:
            logger.error("Failed to update dashboard widget", error=str(e), widget_id=widget_id)
            return False
    
    async def delete_dashboard_widget(self, widget_id: str, customer_id: str) -> bool:
        """Delete (deactivate) dashboard widget in database"""
        try:
            # ClickHouse requires ALTER TABLE ... UPDATE syntax
            await self.db.execute_query(
                f"""ALTER TABLE {DASHBOARD_WIDGETS_TABLE} UPDATE 
                   status = %(status)s, updated_at = %(updated_at)s
                   WHERE id = %(widget_id)s AND customer_id = %(customer_id)s""",
                {
                    "status": STATUS_INACTIVE,
                    "updated_at": datetime.now(timezone.utc),
                    "widget_id": widget_id,
                    "customer_id": customer_id
                }
            )
            
            logger.info("Dashboard widget deleted", widget_id=widget_id, customer_id=customer_id)
            return True
            
        except Exception as e:
            logger.error("Failed to delete dashboard widget", error=str(e), widget_id=widget_id)
            return False
    
    # Dashboard sharing operations
    
    async def share_dashboard(self, dashboard_id: str, customer_id: str, 
                             share_data: Dict[str, Any]) -> str:
        """Create dashboard sharing record"""
        try:
            share_id = str(uuid.uuid4())
            
            db_share_data = {
                'id': share_id,
                'dashboard_id': dashboard_id,
                'customer_id': customer_id,
                'shared_with_email': share_data.get('shared_with_email'),
                'shared_with_tenant': share_data.get('shared_with_tenant'),
                'permission_level': share_data.get('permission_level', 'view'),  # view, edit, admin
                'expires_at': share_data.get('expires_at'),
                'created_by': share_data.get('created_by', 'system'),
                'created_at': datetime.now(timezone.utc),
                'status': STATUS_ACTIVE
            }
            
            await self.db.execute_query(
                f"""INSERT INTO {DASHBOARD_SHARES_TABLE} 
                   (id, dashboard_id, customer_id, shared_with_email, shared_with_tenant, 
                    permission_level, expires_at, created_by, created_at, status)
                   VALUES (%(id)s, %(dashboard_id)s, %(customer_id)s, %(shared_with_email)s, 
                   %(shared_with_tenant)s, %(permission_level)s, %(expires_at)s, %(created_by)s, 
                   %(created_at)s, %(status)s)""",
                db_share_data
            )
            
            logger.info("Dashboard share created", share_id=share_id, dashboard_id=dashboard_id)
            return share_id
            
        except Exception as e:
            logger.error("Failed to share dashboard", error=str(e))
            raise e
    
    async def get_dashboard_shares(self, dashboard_id: str, customer_id: str) -> List[Dict[str, Any]]:
        """Get dashboard sharing records"""
        try:
            result = await self.db.execute_query(
                f"""SELECT * FROM {DASHBOARD_SHARES_TABLE} 
                   WHERE dashboard_id = %(dashboard_id)s AND customer_id = %(customer_id)s 
                   AND status = %(status)s ORDER BY created_at DESC""",
                {"dashboard_id": dashboard_id, "customer_id": customer_id, "status": STATUS_ACTIVE}
            )
            
            return [dict(row) for row in result]
            
        except Exception as e:
            logger.error("Failed to get dashboard shares", error=str(e), dashboard_id=dashboard_id)
            return []