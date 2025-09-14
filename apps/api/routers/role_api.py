"""
M8 Role Management API
FastAPI router for user role assignments, permissions, and role-based access control
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import structlog

from models import (
    RoleAssignmentRequest, RoleAssignmentResponse, UserRolesResponse,
    UserRole, UserStatus, User, PermissionCheckRequest
)
from authn_authz_middleware import (
    get_current_user, require_platform_admin, require_tenant_admin,
    user_service, check_permission
)
from tenant_dependencies import MiddlewareTenant

logger = structlog.get_logger()

# Create router for role management
router = APIRouter(prefix="/v1", tags=["Role Management"])

# Import proper service
from services.role_service import RoleService








# Global role service instance
role_service = RoleService()

# =================================================================
# ROLE ASSIGNMENT ENDPOINTS
# =================================================================

@router.post("/users/{user_id}/roles", response_model=RoleAssignmentResponse, status_code=201)
async def assign_user_role(
    user_id: str,
    role_request: RoleAssignmentRequest,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Assign role to user for specific tenant"""
    try:
        # Verify target user exists
        target_user = await user_service.get_user_by_id(user_id)
        if not target_user:
            raise HTTPException(404, f"User {user_id} not found")

        # Check permission to assign this role
        can_assign = await role_service.validate_role_assignment_permission(
            current_user.id,
            role_request.tenant_id,
            role_request.role
        )

        if not can_assign:
            raise HTTPException(403, f"No permission to assign {role_request.role} to tenant {role_request.tenant_id}")

        # Assign role
        role_assignment = await role_service.assign_role(
            user_id=user_id,
            tenant_id=role_request.tenant_id,
            role=role_request.role,
            granted_by=current_user.id
        )

        logger.info("Role assigned to user",
                   target_user_id=user_id,
                   tenant_id=role_request.tenant_id,
                   role=role_request.role,
                   granted_by=current_user.id)

        return RoleAssignmentResponse(
            id=role_assignment.id,
            user_id=role_assignment.user_id,
            tenant_id=role_assignment.tenant_id,
            role=role_assignment.role,
            granted_by=role_assignment.granted_by,
            granted_at=role_assignment.granted_at,
            expires_at=role_assignment.expires_at,
            status=role_assignment.status
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("Role assignment failed", user_id=user_id, error=str(e))
        raise HTTPException(500, f"Role assignment failed: {str(e)}")

@router.get("/users/{user_id}/roles", response_model=UserRolesResponse)
async def get_user_roles(
    user_id: str,
    tenant_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Get user's role assignments"""
    try:
        # Verify target user exists
        target_user = await user_service.get_user_by_id(user_id)
        if not target_user:
            raise HTTPException(404, f"User {user_id} not found")

        # Check permissions - users can view their own roles, admins can view others
        is_self = user_id == current_user.id
        is_platform_admin = any(
            r["tenant_id"] == "platform" for r in request.state.roles
        ) if hasattr(request.state, "roles") else False

        # Tenant admins can view roles for their tenant
        current_tenant_id = request.headers.get("X-Customer-ID")
        is_tenant_admin = False
        if current_tenant_id:
            is_tenant_admin = any(
                r["tenant_id"] == current_tenant_id and r["role"] == "tenant_admin"
                for r in request.state.roles
            ) if hasattr(request.state, "roles") else False

        if not is_self and not is_platform_admin and not is_tenant_admin:
            raise HTTPException(403, "No permission to view user roles")

        # Get user roles
        user_roles = await role_service.get_user_roles(user_id, tenant_id)

        # Filter roles based on current user's scope
        if not is_platform_admin and is_tenant_admin and current_tenant_id:
            # Tenant admins can only see roles for their tenant
            user_roles = [r for r in user_roles if r.tenant_id == current_tenant_id]

        role_responses = [
            RoleAssignmentResponse(
                id=r.id,
                user_id=r.user_id,
                tenant_id=r.tenant_id,
                role=r.role,
                granted_by=r.granted_by,
                granted_at=r.granted_at,
                expires_at=r.expires_at,
                status=r.status
            ) for r in user_roles
        ]

        return UserRolesResponse(
            user_id=user_id,
            roles=role_responses
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("User roles retrieval failed", user_id=user_id, error=str(e))
        raise HTTPException(500, "User roles retrieval failed")

@router.delete("/users/{user_id}/roles/{role_id}")
async def remove_user_role(
    user_id: str,
    role_id: str,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Remove role assignment from user"""
    try:
        # Find the role assignment by ID
        target_assignment = await role_service.get_role_by_id(role_id)

        if not target_assignment or target_assignment.user_id != user_id:
            raise HTTPException(404, f"Role assignment {role_id} not found for user {user_id}")

        # Check permission to remove this role
        can_remove = await role_service.validate_role_assignment_permission(
            current_user.id,
            target_assignment.tenant_id,
            target_assignment.role
        )

        if not can_remove:
            raise HTTPException(403, f"No permission to remove {target_assignment.role} from tenant {target_assignment.tenant_id}")

        # Remove role
        removed = await role_service.remove_role(
            user_id,
            target_assignment.tenant_id,
            target_assignment.role
        )

        if not removed:
            raise HTTPException(404, "Role assignment not found")

        logger.info("Role removed from user",
                   user_id=user_id,
                   role_id=role_id,
                   tenant_id=target_assignment.tenant_id,
                   role=target_assignment.role,
                   removed_by=current_user.id)

        return {"message": "Role removed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Role removal failed", user_id=user_id, role_id=role_id, error=str(e))
        raise HTTPException(500, "Role removal failed")

# =================================================================
# ROLE INFORMATION ENDPOINTS
# =================================================================

@router.get("/roles")
async def list_available_roles(
    current_user: User = Depends(get_current_user),
    tenant_id: str = MiddlewareTenant,
    request: Request = None
):
    """List available roles and their permissions"""
    try:
        # Get current user's scope to determine which roles they can see/assign
        request_tenant_id = tenant_id

        is_platform_admin = any(
            r["tenant_id"] == "platform" for r in request.state.roles
        ) if hasattr(request.state, "roles") else False

        is_tenant_admin = any(
            r["tenant_id"] == tenant_id and r["role"] == "tenant_admin"
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False

        available_roles = []

        if is_platform_admin:
            # Platform admins can see all roles
            for role in UserRole:
                available_roles.append({
                    "role": role.value,
                    "name": role.value.replace("_", " ").title(),
                    "permissions": role_service.get_role_permissions(role),
                    "scope": "platform" if role.value.endswith("_admin") else "tenant",
                    "assignable": True
                })
        elif is_tenant_admin:
            # Tenant admins can see and assign customer roles
            customer_roles = [
                UserRole.SECURITY_ANALYST, UserRole.DEVOPS_ENGINEER,
                UserRole.COMPLIANCE_OFFICER, UserRole.VIEWER
            ]
            for role in customer_roles:
                available_roles.append({
                    "role": role.value,
                    "name": role.value.replace("_", " ").title(),
                    "permissions": role_service.get_role_permissions(role),
                    "scope": "tenant",
                    "assignable": True
                })
        else:
            # Regular users can see available roles but cannot assign
            for role in UserRole:
                available_roles.append({
                    "role": role.value,
                    "name": role.value.replace("_", " ").title(),
                    "permissions": role_service.get_role_permissions(role),
                    "scope": "platform" if role.value.endswith("_admin") else "tenant",
                    "assignable": False
                })

        return {"roles": available_roles}

    except Exception as e:
        logger.error("Role listing failed", error=str(e))
        raise HTTPException(500, "Role listing failed")

@router.get("/roles/{role}/permissions")
async def get_role_permissions(
    role: UserRole,
    current_user: User = Depends(get_current_user)
):
    """Get permissions for specific role"""
    try:
        permissions = role_service.get_role_permissions(role)

        return {
            "role": role.value,
            "permissions": permissions,
            "permission_count": len(permissions),
            "scope": "platform" if role.value.endswith("_admin") else "tenant"
        }

    except Exception as e:
        logger.error("Role permissions retrieval failed", role=role, error=str(e))
        raise HTTPException(500, "Role permissions retrieval failed")

# =================================================================
# TENANT USER MANAGEMENT
# =================================================================

@router.get("/tenants/{tenant_id}/users", response_model=List[Dict[str, Any]])
async def list_tenant_users(
    tenant_id: str,
    role: Optional[UserRole] = None,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """List users for specific tenant"""
    try:
        # Check permissions - platform admins or tenant admins for this tenant
        is_platform_admin = any(
            r["tenant_id"] == "platform" for r in request.state.roles
        ) if hasattr(request.state, "roles") else False

        is_tenant_admin = any(
            r["tenant_id"] == tenant_id and r["role"] == "tenant_admin"
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False

        if not is_platform_admin and not is_tenant_admin:
            raise HTTPException(403, f"No permission to list users for tenant {tenant_id}")

        # Get tenant users
        tenant_roles = await role_service.get_tenant_users(tenant_id, role)

        # Build response with user details
        tenant_users = []
        for role_assignment in tenant_roles:
            user = await user_service.get_user_by_id(role_assignment.user_id)
            if user:
                tenant_users.append({
                    "user_id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "status": user.status,
                    "role": role_assignment.role,
                    "granted_at": role_assignment.granted_at,
                    "granted_by": role_assignment.granted_by
                })

        return tenant_users

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Tenant users listing failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(500, "Tenant users listing failed")

@router.post("/tenants/{tenant_id}/users/{user_id}/roles", response_model=RoleAssignmentResponse)
async def assign_tenant_role(
    tenant_id: str,
    user_id: str,
    role: UserRole,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Assign role to user for specific tenant (alternative endpoint)"""
    try:
        role_request = RoleAssignmentRequest(tenant_id=tenant_id, role=role)
        return await assign_user_role(user_id, role_request, current_user, request)

    except Exception as e:
        logger.error("Tenant role assignment failed",
                    tenant_id=tenant_id, user_id=user_id, role=role, error=str(e))
        raise HTTPException(500, "Tenant role assignment failed")

# =================================================================
# PERMISSION VALIDATION ENDPOINTS
# =================================================================

@router.post("/check-permission")
async def check_user_permission(
    permission_request: PermissionCheckRequest,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Check if current user has specific permission"""
    try:
        # Use tenant from request or header
        check_tenant_id = permission_request.tenant_id or request.headers.get("X-Customer-ID", "platform")

        # Build permission string
        required_permission = f"{permission_request.resource}:{permission_request.action}:{permission_request.scope}"

        # Get user's roles for the tenant
        user_roles_data = []
        if hasattr(request.state, "roles"):
            user_roles_data = request.state.roles
        else:
            # Fallback: get from role service
            user_roles = await role_service.get_user_roles(current_user.id, check_tenant_id)
            user_roles_data = [
                {
                    "tenant_id": r.tenant_id,
                    "role": r.role.value,
                    "status": r.status.value
                } for r in user_roles
            ]

        # Check permission
        has_permission = check_permission(user_roles_data, required_permission, check_tenant_id)

        return {
            "user_id": current_user.id,
            "tenant_id": check_tenant_id,
            "permission": required_permission,
            "granted": has_permission,
            "roles": user_roles_data
        }

    except Exception as e:
        logger.error("Permission check failed",
                    user_id=current_user.id,
                    permission=f"{permission_request.resource}:{permission_request.action}:{permission_request.scope}",
                    error=str(e))
        raise HTTPException(500, "Permission check failed")

@router.get("/permissions/map")
async def get_permission_map(
    current_user: User = Depends(get_current_user)
):
    """Get complete permission mapping for all roles"""
    try:
        permission_map = {}

        for role in UserRole:
            permissions = role_service.get_role_permissions(role)
            permission_map[role.value] = {
                "name": role.value.replace("_", " ").title(),
                "permissions": permissions,
                "scope": "platform" if role.value.endswith("_admin") else "tenant",
                "description": f"Role for {role.value.replace('_', ' ')}"
            }

        return {
            "roles": permission_map,
            "total_roles": len(permission_map)
        }

    except Exception as e:
        logger.error("Permission map retrieval failed", error=str(e))
        raise HTTPException(500, "Permission map retrieval failed")

# =================================================================
# ROLE ANALYTICS & REPORTING
# =================================================================

@router.get("/roles/analytics")
async def get_role_analytics(
    tenant_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Get role usage analytics"""
    try:
        # Check permissions - platform admins or tenant admins
        check_tenant_id = tenant_id or request.headers.get("X-Customer-ID", "platform")

        is_platform_admin = any(
            r["tenant_id"] == "platform" for r in request.state.roles
        ) if hasattr(request.state, "roles") else False

        is_tenant_admin = any(
            r["tenant_id"] == check_tenant_id and r["role"] == "tenant_admin"
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False

        if not is_platform_admin and not is_tenant_admin:
            raise HTTPException(403, "Admin permissions required for role analytics")

        # Get analytics from service layer
        analytics_data = await role_service.get_role_analytics(
            None if (is_platform_admin and not tenant_id) else check_tenant_id
        )

        return analytics_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Role analytics failed", error=str(e))
        raise HTTPException(500, "Role analytics failed")

# =================================================================
# BULK ROLE OPERATIONS
# =================================================================

@router.post("/users/bulk-assign-roles")
async def bulk_assign_roles(
    assignments: List[Dict[str, str]],  # [{"user_id": "", "tenant_id": "", "role": ""}]
    current_admin: User = Depends(require_platform_admin)
):
    """Bulk assign roles to multiple users (platform admins only)"""
    try:
        if len(assignments) > 100:
            raise HTTPException(400, "Bulk assignment limited to 100 operations")

        successful_assignments = []
        errors = []

        for assignment_data in assignments:
            try:
                user_id = assignment_data["user_id"]
                tenant_id = assignment_data["tenant_id"]
                role = UserRole(assignment_data["role"])

                # Verify user exists
                user = await user_service.get_user_by_id(user_id)
                if not user:
                    errors.append(f"User {user_id} not found")
                    continue

                # Assign role
                role_assignment = await role_service.assign_role(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    role=role,
                    granted_by=current_admin.id
                )

                successful_assignments.append(role_assignment)

            except ValueError as e:
                errors.append(f"Invalid assignment {assignment_data}: {str(e)}")
            except Exception as e:
                errors.append(f"Failed assignment {assignment_data}: {str(e)}")

        logger.info("Bulk role assignment completed",
                   successful_count=len(successful_assignments),
                   error_count=len(errors),
                   assigned_by=current_admin.id)

        if errors:
            logger.warning("Bulk assignment errors", errors=errors)

        return {
            "successful_assignments": len(successful_assignments),
            "errors": errors,
            "assignments": [
                {
                    "id": a.id,
                    "user_id": a.user_id,
                    "tenant_id": a.tenant_id,
                    "role": a.role.value
                } for a in successful_assignments
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Bulk role assignment failed", error=str(e))
        raise HTTPException(500, "Bulk role assignment failed")

# =================================================================
# ROLE VALIDATION & DEBUGGING
# =================================================================

@router.post("/validate-access")
async def validate_user_access(
    endpoint: str,
    method: str = "GET",
    tenant_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Validate if user can access specific endpoint"""
    try:
        # Use tenant from parameter or header
        check_tenant_id = tenant_id or request.headers.get("X-Customer-ID", "platform")

        # Get required permission for endpoint
        from authn_authz_middleware import get_endpoint_permission
        required_permission = get_endpoint_permission(endpoint, method)

        # Get user's roles
        user_roles_data = []
        if hasattr(request.state, "roles"):
            user_roles_data = request.state.roles
        else:
            user_roles = await role_service.get_user_roles(current_user.id, check_tenant_id)
            user_roles_data = [
                {
                    "tenant_id": r.tenant_id,
                    "role": r.role.value,
                    "status": r.status.value
                } for r in user_roles
            ]

        # Check access
        has_access = check_permission(user_roles_data, required_permission, check_tenant_id)

        return {
            "user_id": current_user.id,
            "endpoint": endpoint,
            "method": method,
            "tenant_id": check_tenant_id,
            "required_permission": required_permission,
            "access_granted": has_access,
            "user_roles": user_roles_data,
            "validation_timestamp": datetime.now(timezone.utc)
        }

    except Exception as e:
        logger.error("Access validation failed",
                    user_id=current_user.id,
                    endpoint=endpoint,
                    error=str(e))
        raise HTTPException(500, "Access validation failed")

# =================================================================
# ROLE HIERARCHY & DELEGATION
# =================================================================

@router.get("/users/{user_id}/effective-permissions")
async def get_user_effective_permissions(
    user_id: str,
    tenant_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Get user's effective permissions across all roles"""
    try:
        # Verify target user exists
        target_user = await user_service.get_user_by_id(user_id)
        if not target_user:
            raise HTTPException(404, f"User {user_id} not found")

        # Check permissions
        is_self = user_id == current_user.id
        is_platform_admin = any(
            r["tenant_id"] == "platform" for r in request.state.roles
        ) if hasattr(request.state, "roles") else False

        if not is_self and not is_platform_admin:
            raise HTTPException(403, "Can only view your own permissions or need admin access")

        # Get user's roles
        user_roles = await role_service.get_user_roles(user_id, tenant_id)

        # Calculate effective permissions
        effective_permissions = set()
        role_breakdown = {}

        for role_assignment in user_roles:
            role_permissions = role_service.get_role_permissions(role_assignment.role)
            effective_permissions.update(role_permissions)

            role_breakdown[f"{role_assignment.tenant_id}:{role_assignment.role.value}"] = role_permissions

        return {
            "user_id": user_id,
            "tenant_filter": tenant_id,
            "effective_permissions": sorted(list(effective_permissions)),
            "role_breakdown": role_breakdown,
            "total_permissions": len(effective_permissions),
            "calculated_at": datetime.now(timezone.utc)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Effective permissions calculation failed",
                    user_id=user_id, error=str(e))
        raise HTTPException(500, "Effective permissions calculation failed")

# =================================================================
# GLOBAL ROLE SERVICE INSTANCE
# =================================================================

# Make role service available for dependency injection
async def get_role_service() -> RoleService:
    """Get role service instance"""
    return role_service
