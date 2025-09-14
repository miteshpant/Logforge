"""
Role Service 
Business logic layer for role management operations
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import structlog

from dao.role_dao import RoleDAO
from models import UserRole, UserStatus, UserTenantRole, User
from constants.database_constants import STATUS_ACTIVE, STATUS_INACTIVE
from authn_authz_middleware import ROLE_PERMISSIONS

logger = structlog.get_logger()

class RoleService:
    """Service layer for role management with proper database operations"""
    
    def __init__(self):
        self.role_dao = RoleDAO()
    
    async def assign_role(self, user_id: str, tenant_id: str, role: UserRole, 
                         granted_by: str) -> UserTenantRole:
        """Assign role to user for specific tenant"""
        try:
            # Check if assignment already exists
            existing_assignment = await self.get_user_tenant_role(user_id, tenant_id, role)
            if existing_assignment:
                raise ValueError(f"User already has {role.value} role for tenant {tenant_id}")
            
            # Create role assignment in database
            role_data = {
                'user_id': user_id,
                'tenant_id': tenant_id,
                'role': role.value,
                'granted_by': granted_by,
                'customer_id': tenant_id if tenant_id != 'platform' else 'platform'
            }
            
            db_role = await self.role_dao.create_user_role(role_data)
            
            # Convert to UserTenantRole model
            role_assignment = UserTenantRole(
                id=db_role['id'],
                user_id=db_role['user_id'],
                tenant_id=db_role['tenant_id'],
                role=UserRole(db_role['role']),
                granted_by=db_role['granted_by'],
                granted_at=db_role['granted_at'],
                expires_at=db_role.get('expires_at'),
                status=UserStatus.ACTIVE
            )
            
            logger.info("Role assigned successfully", 
                       user_id=user_id, tenant_id=tenant_id, role=role.value, granted_by=granted_by)
            return role_assignment
            
        except ValueError as e:
            logger.error("Role assignment validation failed", error=str(e))
            raise e
        except Exception as e:
            logger.error("Role assignment failed", error=str(e))
            raise e
    
    async def remove_role(self, user_id: str, tenant_id: str, role: UserRole) -> bool:
        """Remove role assignment from user"""
        try:
            success = await self.role_dao.remove_role_assignment(user_id, tenant_id, role.value)
            
            if success:
                logger.info("Role removed successfully", 
                           user_id=user_id, tenant_id=tenant_id, role=role.value)
            else:
                logger.warning("Role removal failed - assignment not found", 
                              user_id=user_id, tenant_id=tenant_id, role=role.value)
            
            return success
            
        except Exception as e:
            logger.error("Role removal failed", error=str(e))
            return False
    
    async def get_user_roles(self, user_id: str, tenant_id: Optional[str] = None) -> List[UserTenantRole]:
        """Get user's role assignments from database"""
        try:
            if tenant_id:
                # Get roles for specific tenant
                roles_data = await self.role_dao.get_user_tenant_roles(user_id, tenant_id)
            else:
                # Get all roles for user across all tenants
                roles_data = await self.role_dao.get_user_all_roles(user_id)
            
            # Convert database records to UserTenantRole objects
            user_roles = []
            for role_data in roles_data:
                try:
                    role_assignment = UserTenantRole(
                        id=role_data['id'],
                        user_id=role_data['user_id'],
                        tenant_id=role_data['tenant_id'],
                        role=UserRole(role_data['role']),
                        granted_by=role_data['granted_by'],
                        granted_at=role_data['granted_at'],
                        expires_at=role_data.get('expires_at'),
                        status=UserStatus(role_data.get('status', STATUS_ACTIVE))
                    )
                    user_roles.append(role_assignment)
                except (ValueError, KeyError) as e:
                    logger.warning("Failed to parse role data", role_data=role_data, error=str(e))
                    continue
            
            logger.debug("Retrieved user roles from database", 
                        user_id=user_id, tenant_id=tenant_id, count=len(user_roles))
            return user_roles
            
        except Exception as e:
            logger.error("Failed to get user roles from database", error=str(e))
            raise e
    
    async def get_user_tenant_role(self, user_id: str, tenant_id: str, role: UserRole) -> Optional[UserTenantRole]:
        """Get specific user-tenant-role assignment from database"""
        try:
            role_data = await self.role_dao.get_specific_role_assignment(user_id, tenant_id, role.value)
            
            if role_data:
                return UserTenantRole(
                    id=role_data['id'],
                    user_id=role_data['user_id'],
                    tenant_id=role_data['tenant_id'],
                    role=UserRole(role_data['role']),
                    granted_by=role_data['granted_by'],
                    granted_at=role_data['granted_at'],
                    expires_at=role_data.get('expires_at'),
                    status=UserStatus(role_data.get('status', STATUS_ACTIVE))
                )
            
            return None
            
        except Exception as e:
            logger.error("Failed to get specific role assignment", error=str(e))
            return None
    
    async def get_tenant_users(self, tenant_id: str, role: Optional[UserRole] = None) -> List[UserTenantRole]:
        """Get all users for a tenant from database"""
        try:
            role_value = role.value if role else None
            roles_data = await self.role_dao.get_tenant_users(tenant_id, role_value)
            
            tenant_roles = []
            for role_data in roles_data:
                try:
                    role_assignment = UserTenantRole(
                        id=role_data['id'],
                        user_id=role_data['user_id'],
                        tenant_id=role_data['tenant_id'],
                        role=UserRole(role_data['role']),
                        granted_by=role_data['granted_by'],
                        granted_at=role_data['granted_at'],
                        expires_at=role_data.get('expires_at'),
                        status=UserStatus(role_data.get('status', STATUS_ACTIVE))
                    )
                    tenant_roles.append(role_assignment)
                except (ValueError, KeyError) as e:
                    logger.warning("Failed to parse tenant role data", role_data=role_data, error=str(e))
                    continue
            
            return tenant_roles
            
        except Exception as e:
            logger.error("Failed to get tenant users from database", error=str(e))
            return []
    
    async def get_role_by_id(self, role_id: str) -> Optional[UserTenantRole]:
        """Get role assignment by ID from database"""
        try:
            logger.info("Getting role by ID", role_id=role_id)
            role_data = await self.role_dao.get_role_by_id(role_id)
            
            if role_data:
                logger.info("Found role data", role_data=role_data)
                return UserTenantRole(
                    id=role_data['id'],
                    user_id=role_data['user_id'],
                    tenant_id=role_data['tenant_id'],
                    role=UserRole(role_data['role']),
                    granted_by=role_data['granted_by'],
                    granted_at=role_data['granted_at'],
                    expires_at=role_data.get('expires_at'),
                    status=UserStatus(role_data.get('status', STATUS_ACTIVE))
                )
            else:
                logger.warning("No role data found", role_id=role_id)
            
            return None
            
        except Exception as e:
            logger.error("Failed to get role by ID", error=str(e))
            return None
    
    def get_role_permissions(self, role: UserRole) -> List[str]:
        """Get permissions for a specific role"""
        return ROLE_PERMISSIONS.get(role, [])
    
    async def validate_role_assignment_permission(self, granter_id: str, tenant_id: str, 
                                                 role_to_assign: UserRole) -> bool:
        """Check if user can assign specific role to tenant"""
        try:
            granter_roles = await self.get_user_roles(granter_id)
            
            # Platform admins can assign any role
            platform_roles = [r for r in granter_roles if r.tenant_id == "platform"]
            if any(r.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN] for r in platform_roles):
                return True
            
            # Tenant admins can assign customer roles to their tenant
            tenant_roles = [r for r in granter_roles if r.tenant_id == tenant_id]
            tenant_admin_roles = [r for r in tenant_roles if r.role == UserRole.TENANT_ADMIN]
            
            if tenant_admin_roles and role_to_assign in [
                UserRole.SECURITY_ANALYST, UserRole.DEVOPS_ENGINEER, 
                UserRole.COMPLIANCE_OFFICER, UserRole.VIEWER
            ]:
                return True
            
            return False
            
        except Exception as e:
            logger.error("Role assignment permission validation failed", error=str(e))
            return False
    
    async def get_role_analytics(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get role usage analytics from database"""
        try:
            if tenant_id:
                # Tenant-specific analytics
                roles_data = await self.role_dao.get_tenant_users(tenant_id)
            else:
                # Get all active roles for platform-wide analytics
                # This would need a new DAO method for all roles across tenants
                roles_data = []
                # TODO: Implement get_all_active_roles in RoleDAO
            
            # Count roles
            role_counts = {}
            tenant_breakdown = {}
            
            for role_data in roles_data:
                if role_data.get('status') == STATUS_ACTIVE:
                    # Role counts
                    role_value = role_data['role']
                    role_counts[role_value] = role_counts.get(role_value, 0) + 1
                    
                    # Tenant breakdown
                    role_tenant_id = role_data['tenant_id']
                    if role_tenant_id not in tenant_breakdown:
                        tenant_breakdown[role_tenant_id] = {}
                    
                    tenant_breakdown[role_tenant_id][role_value] = (
                        tenant_breakdown[role_tenant_id].get(role_value, 0) + 1
                    )
            
            return {
                "tenant_id": tenant_id,
                "role_distribution": role_counts,
                "tenant_breakdown": tenant_breakdown if not tenant_id else None,
                "total_assignments": len(roles_data),
                "generated_at": datetime.now(timezone.utc)
            }
            
        except Exception as e:
            logger.error("Role analytics failed", error=str(e))
            return {
                "tenant_id": tenant_id,
                "role_distribution": {},
                "tenant_breakdown": {},
                "total_assignments": 0,
                "generated_at": datetime.now(timezone.utc),
                "error": str(e)
            }