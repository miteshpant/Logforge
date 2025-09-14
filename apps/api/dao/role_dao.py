"""
Role Data Access Object (DAO)
Handles all database operations for role management
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import structlog

from database_layer import DatabaseLayer
from constants.database_constants import (
    USER_TENANT_ROLES_TABLE, 
    STATUS_ACTIVE, STATUS_INACTIVE
)

logger = structlog.get_logger()

class RoleDAO:
    """Data Access Object for Role operations"""
    
    def __init__(self):
        self.db = DatabaseLayer("RoleDAO", "role-dao-service-key")
    
    async def create_user_role(self, role_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new role assignment in database"""
        try:
            role_id = str(uuid.uuid4())
            
            # Prepare role data for database
            db_role_data = {
                'id': role_id,
                'user_id': role_data['user_id'],
                'tenant_id': role_data['tenant_id'],
                'role': role_data['role'],
                'granted_by': role_data['granted_by'],
                'granted_at': datetime.now(timezone.utc),
                'status': STATUS_ACTIVE,
                'expires_at': role_data.get('expires_at'),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc),
                'customer_id': role_data.get('customer_id', role_data['tenant_id'])
            }
            
            # Insert role into database using database layer method
            await self.db.execute_insert(USER_TENANT_ROLES_TABLE, [db_role_data])
            
            logger.info("Role assignment created in database", role_id=role_id, user_id=role_data['user_id'])
            return {'id': role_id, **db_role_data}
            
        except Exception as e:
            logger.error("Failed to create role assignment in database", error=str(e), user_id=role_data.get('user_id'))
            raise e
    
    async def get_user_tenant_roles(self, user_id: str, tenant_id: str) -> List[Dict[str, Any]]:
        """Get user roles for specific tenant from database"""
        try:
            result = await self.db.execute_query(
                f"""SELECT * FROM {USER_TENANT_ROLES_TABLE} 
                   WHERE user_id = %(user_id)s AND tenant_id = %(tenant_id)s 
                   AND status = %(status)s AND (expires_at IS NULL OR expires_at > now())""",
                {"user_id": user_id, "tenant_id": tenant_id, "status": STATUS_ACTIVE}
            )
            
            return [dict(row) for row in result] if result else []
            
        except Exception as e:
            logger.error("Failed to get user tenant roles", error=str(e), user_id=user_id, tenant_id=tenant_id)
            return []
    
    async def get_user_all_roles(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all user roles across all tenants from database"""
        try:
            result = await self.db.execute_query(
                f"""SELECT * FROM {USER_TENANT_ROLES_TABLE} 
                   WHERE user_id = %(user_id)s AND status = %(status)s 
                   AND (expires_at IS NULL OR expires_at > now())
                   ORDER BY granted_at DESC""",
                {"user_id": user_id, "status": STATUS_ACTIVE}
            )
            
            return [dict(row) for row in result] if result else []
            
        except Exception as e:
            logger.error("Failed to get all user roles", error=str(e), user_id=user_id)
            return []
    
    async def get_specific_role_assignment(self, user_id: str, tenant_id: str, role: str) -> Optional[Dict[str, Any]]:
        """Get specific role assignment from database"""
        try:
            result = await self.db.execute_query(
                f"""SELECT * FROM {USER_TENANT_ROLES_TABLE} 
                   WHERE user_id = %(user_id)s AND tenant_id = %(tenant_id)s 
                   AND role = %(role)s AND status = %(status)s
                   AND (expires_at IS NULL OR expires_at > now())""",
                {"user_id": user_id, "tenant_id": tenant_id, "role": role, "status": STATUS_ACTIVE}
            )
            
            if result:
                return dict(result[0])
            return None
            
        except Exception as e:
            logger.error("Failed to get specific role assignment", error=str(e), 
                        user_id=user_id, tenant_id=tenant_id, role=role)
            return None
    
    async def remove_role_assignment(self, user_id: str, tenant_id: str, role: str) -> bool:
        """Remove (deactivate) role assignment in database using ClickHouse ALTER TABLE syntax"""
        try:
            # ClickHouse requires ALTER TABLE ... UPDATE syntax instead of standard UPDATE
            await self.db.execute_query(
                f"""ALTER TABLE {USER_TENANT_ROLES_TABLE} 
                   UPDATE status = %(status)s, updated_at = %(updated_at)s
                   WHERE user_id = %(user_id)s AND tenant_id = %(tenant_id)s 
                   AND role = %(role)s""",
                {
                    "status": STATUS_INACTIVE,
                    "updated_at": datetime.now(timezone.utc),
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "role": role
                }
            )
            
            logger.info("Role assignment removed from database", 
                       user_id=user_id, tenant_id=tenant_id, role=role)
            return True
            
        except Exception as e:
            logger.error("Failed to remove role assignment", error=str(e), 
                        user_id=user_id, tenant_id=tenant_id, role=role)
            return False
    
    async def get_role_by_id(self, role_id: str) -> Optional[Dict[str, Any]]:
        """Get role assignment by ID from database"""
        try:
            logger.info("RoleDAO: Searching for role by ID", role_id=role_id, table=USER_TENANT_ROLES_TABLE)
            result = await self.db.execute_query(
                f"SELECT * FROM {USER_TENANT_ROLES_TABLE} WHERE id = %(role_id)s",
                {"role_id": role_id}
            )
            
            logger.info("RoleDAO: Query result", role_id=role_id, result_count=len(result) if result else 0)
            
            if result:
                logger.info("RoleDAO: Found role data", role_id=role_id, role_data=result[0])
                return dict(result[0])
            else:
                logger.warning("RoleDAO: No role found", role_id=role_id)
            return None
            
        except Exception as e:
            logger.error("Failed to get role by ID", error=str(e), role_id=role_id)
            return None
    
    async def get_tenant_users(self, tenant_id: str, role: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all users for a tenant from database"""
        try:
            query = f"""SELECT * FROM {USER_TENANT_ROLES_TABLE} 
                       WHERE tenant_id = %(tenant_id)s AND status = %(status)s
                       AND (expires_at IS NULL OR expires_at > now())"""
            params = {"tenant_id": tenant_id, "status": STATUS_ACTIVE}
            
            if role:
                query += " AND role = %(role)s"
                params["role"] = role
            
            query += " ORDER BY granted_at DESC"
            
            result = await self.db.execute_query(query, params)
            return [dict(row) for row in result] if result else []
            
        except Exception as e:
            logger.error("Failed to get tenant users", error=str(e), tenant_id=tenant_id)
            return []
    
    async def count_role_assignments(self, tenant_id: Optional[str] = None, role: Optional[str] = None) -> int:
        """Count role assignments with optional filtering"""
        try:
            query = f"SELECT COUNT(*) as count FROM {USER_TENANT_ROLES_TABLE} WHERE status = %(status)s"
            params = {"status": STATUS_ACTIVE}
            
            if tenant_id:
                query += " AND tenant_id = %(tenant_id)s"
                params["tenant_id"] = tenant_id
                
            if role:
                query += " AND role = %(role)s"
                params["role"] = role
            
            result = await self.db.execute_query(query, params)
            return result[0]['count'] if result else 0
            
        except Exception as e:
            logger.error("Failed to count role assignments", error=str(e))
            return 0