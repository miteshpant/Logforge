"""
User Data Access Object (DAO)
Handles all database operations for user management
"""

import os
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import structlog

from database_layer import DatabaseLayer
from constants.database_constants import (
    USERS_TABLE, USER_SESSIONS_TABLE, USER_INVITATIONS_TABLE,
    STATUS_ACTIVE, STATUS_INACTIVE, STATUS_PENDING
)

logger = structlog.get_logger()

class UserDAO:
    """Data Access Object for User operations"""
    
    def __init__(self):
        service_key = os.getenv("USER_SERVICE_KEY", "user-dao-service-key") 
        self.db = DatabaseLayer("UserDAO", service_key)
    
    async def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new user in database using DatabaseLayer method"""
        try:
            # Prepare user data for DatabaseLayer's create_user method
            db_user_data = {
                'email': user_data['email'].lower(),
                'name': user_data['name'],
                'password_hash': user_data['password_hash'],
                'status': user_data.get('status', STATUS_ACTIVE),
                'customer_id': user_data.get('customer_id', 'platform')
            }
            
            # Use DatabaseLayer's create_user method
            user_id = await self.db.create_user(db_user_data)
            
            # Return the created user data by fetching it back
            created_user = await self.get_user_by_id(user_id)
            if created_user:
                logger.info("User created in database", user_id=user_id, email=user_data['email'])
                return created_user
            else:
                raise Exception("Failed to retrieve created user")
            
        except Exception as e:
            logger.error("Failed to create user in database", error=str(e), email=user_data.get('email'))
            raise e
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID from database using DatabaseLayer method"""
        try:
            # Use DatabaseLayer's get_user_by_id method
            result = await self.db.get_user_by_id(user_id)
            return result
            
        except Exception as e:
            logger.error("Failed to get user by ID", error=str(e), user_id=user_id)
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email from database using DatabaseLayer method"""
        try:
            # Use DatabaseLayer's get_user_by_email method
            result = await self.db.get_user_by_email(email)
            return result
            
        except Exception as e:
            logger.error("Failed to get user by email", error=str(e), email=email)
            return None
    
    async def update_user(self, user_id: str, update_data: Dict[str, Any]) -> bool:
        """Update user in database using DatabaseLayer method"""
        try:
            # Use DatabaseLayer's update_user method which already has correct ClickHouse syntax
            result = await self.db.update_user(user_id, update_data)
            
            logger.info("User updated in database", user_id=user_id)
            return result
            
        except Exception as e:
            logger.error("Failed to update user", error=str(e), user_id=user_id)
            return False
    
    async def delete_user(self, user_id: str) -> bool:
        """Soft delete user (set status to inactive)"""
        try:
            from datetime import datetime, timezone
            
            # Soft delete by setting status to inactive instead of hard delete
            await self.db.execute_update(
                f"ALTER TABLE {USERS_TABLE} UPDATE status = %(status)s, updated_at = %(updated_at)s WHERE id = %(user_id)s",
                {
                    "status": STATUS_INACTIVE,
                    "updated_at": datetime.now(timezone.utc),
                    "user_id": user_id
                }
            )
            
            logger.info("User soft deleted (status set to inactive)", user_id=user_id)
            return True
            
        except Exception as e:
            logger.error("Failed to soft delete user", error=str(e), user_id=user_id)
            return False
    
    async def list_users(self, limit: int = 50, offset: int = 0, 
                        status_filter: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """List users with pagination and filtering"""
        try:
            query = f"SELECT * FROM {USERS_TABLE} WHERE 1=1"
            params = {'limit': limit, 'offset': offset}
            
            if status_filter:
                query += " AND status = %(status)s"
                params['status'] = status_filter
            
            if search:
                query += " AND (lower(name) LIKE %(search)s OR lower(email) LIKE %(search)s)"
                params['search'] = f"%{search.lower()}%"
            
            query += " ORDER BY created_at DESC LIMIT %(limit)s OFFSET %(offset)s"
            
            result = await self.db.execute_query(query, params)
            return [dict(row) for row in result] if result else []
            
        except Exception as e:
            logger.error("Failed to list users", error=str(e))
            return []
    
    async def count_users(self, status_filter: Optional[str] = None, search: Optional[str] = None) -> int:
        """Count total users with optional filtering"""
        try:
            query = f"SELECT COUNT(*) as count FROM {USERS_TABLE} WHERE 1=1"
            params = {}
            
            if status_filter:
                query += " AND status = %(status)s"
                params['status'] = status_filter
            
            if search:
                query += " AND (lower(name) LIKE %(search)s OR lower(email) LIKE %(search)s)"
                params['search'] = f"%{search.lower()}%"
            
            result = await self.db.execute_query(query, params)
            return result[0]['count'] if result else 0
            
        except Exception as e:
            logger.error("Failed to count users", error=str(e))
            return 0

    # User invitation methods (replacing memory storage)
    async def create_invitation(self, invitation_data: Dict[str, Any]) -> str:
        """Create user invitation in database"""
        try:
            invitation_id = str(uuid.uuid4())
            
            db_invitation_data = {
                'id': invitation_id,
                'email': invitation_data['email'].lower(),
                'tenant_id': invitation_data['tenant_id'],
                'invited_by': invitation_data['invited_by'],
                'role': invitation_data['role'],
                'invitation_token': invitation_data['invitation_token'],
                'status': STATUS_PENDING,
                'expires_at': invitation_data['expires_at'],
                'created_at': datetime.now(timezone.utc),
                'customer_id': invitation_data.get('customer_id', 'platform')
            }
            
            await self.db.execute_query(
                f"""INSERT INTO {USER_INVITATIONS_TABLE} 
                   (id, email, tenant_id, invited_by, role, invitation_token, status, expires_at, created_at, customer_id)
                   VALUES (%(id)s, %(email)s, %(tenant_id)s, %(invited_by)s, %(role)s, 
                   %(invitation_token)s, %(status)s, %(expires_at)s, %(created_at)s, %(customer_id)s)""",
                db_invitation_data
            )
            
            logger.info("Invitation created in database", invitation_id=invitation_id, email=invitation_data['email'])
            return invitation_id
            
        except Exception as e:
            logger.error("Failed to create invitation", error=str(e))
            raise e
    
    async def get_invitation_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get invitation by token from database"""
        try:
            result = await self.db.execute_query(
                f"SELECT * FROM {USER_INVITATIONS_TABLE} WHERE invitation_token = %(token)s",
                {"token": token}
            )
            
            if result:
                return dict(result[0])
            return None
            
        except Exception as e:
            logger.error("Failed to get invitation by token", error=str(e))
            return None
    
    async def update_invitation_status(self, invitation_id: str, status: str) -> bool:
        """Update invitation status in database"""
        try:
            await self.db.execute_update(
                f"ALTER TABLE {USER_INVITATIONS_TABLE} UPDATE status = %(status)s, updated_at = %(updated_at)s WHERE id = %(invitation_id)s",
                {
                    "status": status,
                    "updated_at": datetime.now(timezone.utc),
                    "invitation_id": invitation_id
                }
            )
            
            logger.info("Invitation status updated", invitation_id=invitation_id, status=status)
            return True
            
        except Exception as e:
            logger.error("Failed to update invitation status", error=str(e))
            return False

    # Session management methods
    async def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active sessions for a user from database"""
        try:
            result = await self.db.execute_query(
                f"""SELECT * FROM {USER_SESSIONS_TABLE} 
                   WHERE user_id = %(user_id)s 
                   AND expires_at > now()
                   AND status = %(status)s
                   ORDER BY created_at DESC""",
                {"user_id": user_id, "status": STATUS_ACTIVE}
            )
            
            sessions = [dict(row) for row in result] if result else []
            logger.info("User sessions retrieved from database", user_id=user_id, session_count=len(sessions))
            return sessions
            
        except Exception as e:
            logger.error("Failed to get user sessions", error=str(e), user_id=user_id)
            return []
    
    async def revoke_user_session(self, user_id: str, session_id: str) -> bool:
        """Revoke a specific user session in database"""
        try:
            await self.db.execute_update(
                f"""ALTER TABLE {USER_SESSIONS_TABLE} UPDATE 
                   status = %(status)s, updated_at = %(updated_at)s 
                   WHERE id = %(session_id)s AND user_id = %(user_id)s""",
                {
                    "status": STATUS_INACTIVE,
                    "updated_at": datetime.now(timezone.utc),
                    "session_id": session_id,
                    "user_id": user_id
                }
            )
            
            logger.info("User session revoked in database", user_id=user_id, session_id=session_id)
            return True
            
        except Exception as e:
            logger.error("Failed to revoke user session", error=str(e), user_id=user_id, session_id=session_id)
            return False
    
    async def revoke_all_user_sessions(self, user_id: str, except_session_id: Optional[str] = None) -> int:
        """Revoke all user sessions except optionally the current one"""
        try:
            params = {
                "user_id": user_id,
                "status": STATUS_INACTIVE,
                "updated_at": datetime.now(timezone.utc)
            }
            
            if except_session_id:
                query = f"""ALTER TABLE {USER_SESSIONS_TABLE} UPDATE 
                           status = %(status)s, updated_at = %(updated_at)s 
                           WHERE user_id = %(user_id)s 
                           AND id != %(except_session_id)s 
                           AND status = %(active_status)s"""
                params["except_session_id"] = except_session_id
                params["active_status"] = STATUS_ACTIVE
            else:
                query = f"""ALTER TABLE {USER_SESSIONS_TABLE} UPDATE 
                           status = %(status)s, updated_at = %(updated_at)s 
                           WHERE user_id = %(user_id)s 
                           AND status = %(active_status)s"""
                params["active_status"] = STATUS_ACTIVE
            
            result = await self.db.execute_update(query, params)
            
            # Count affected rows (database dependent, but we'll return a reasonable value)
            revoked_count = 1 if result else 0  # Simplified for now
            
            logger.info("User sessions revoked in database", 
                       user_id=user_id, 
                       revoked_count=revoked_count,
                       except_session=except_session_id)
            return revoked_count
            
        except Exception as e:
            logger.error("Failed to revoke user sessions", error=str(e), user_id=user_id)
            return 0
    
    async def get_user_tenant_roles(self, user_id: str, tenant_id: str) -> List[Dict[str, Any]]:
        """Get user's roles for specific tenant (includes platform admin roles)"""
        try:
            # Get all roles for user (both tenant-specific and platform admin roles)
            query = """
                SELECT * FROM user_tenant_roles_mt 
                WHERE user_id = %(user_id)s 
                AND (tenant_id = %(tenant_id)s OR tenant_id = 'platform')
                AND status = 'active'
                AND (expires_at IS NULL OR expires_at > now())
            """
            
            result = await self.db.execute_query(query, {"user_id": user_id, "tenant_id": tenant_id})
            return [dict(row) for row in result] if result else []
            
        except Exception as e:
            logger.error("Failed to get user tenant roles", error=str(e), user_id=user_id, tenant_id=tenant_id)
            return []