"""
M8 User Management API
FastAPI router for user CRUD operations, admin user management, and user profile management
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional
import structlog
from datetime import datetime

from models import (
    UserCreateRequest, UserUpdateRequest, UserResponse, UserListResponse,
    User, UserStatus, UserRole
)
from authn_authz_middleware import (
    get_current_user, require_platform_admin, require_tenant_admin,
    # ENH-010: the ACCESSOR, not the instance. Importing the instance
    # constructed it (and connected to the database) at import time.
    get_user_service,
)

logger = structlog.get_logger()

# Create router for user management
router = APIRouter(prefix="/v1", tags=["User Management"])

# =================================================================
# USER CRUD OPERATIONS
# =================================================================

@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    user_request: UserCreateRequest,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Create new user account"""
    try:
        # Check if user already exists
        existing_user = await get_user_service().get_user_by_email(user_request.email)
        if existing_user:
            raise HTTPException(409, f"User with email {user_request.email} already exists")
        
        # Create user (this will validate password strength)
        user_data = user_request.dict()
        new_user = await get_user_service().create_user(user_data)
    
    except HTTPException:
        # Re-raise HTTP exceptions (including 409 for duplicate email)
        raise
    except ValueError as e:
        # Handle password validation errors
        raise HTTPException(400, f"Password validation failed: {str(e)}")
    except Exception as e:
        logger.error("User creation failed", error=str(e), email=user_request.email)
        raise HTTPException(500, "Failed to create user")
        
    logger.info("User created", 
               user_id=new_user.id, 
               email=new_user.email,
               created_by=current_user.id)
        
    # Return user response without sensitive data
    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        name=new_user.name,
        status=new_user.status,
        created_at=new_user.created_at,
        updated_at=new_user.updated_at,
        last_login_at=new_user.last_login_at,
        email_verified_at=new_user.email_verified_at
    )

@router.get("/users/search", response_model=UserListResponse)
async def search_users(
    q: str,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Search users by name or email"""
    try:
        # Check permissions - only admins or tenant admins can search users
        tenant_id = request.headers.get("X-Customer-ID", "platform")
        
        is_platform_admin = any(
            r["tenant_id"] == "platform" for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        is_tenant_admin = any(
            r["tenant_id"] == tenant_id and r["role"] == "tenant_admin"
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        if not is_platform_admin and not is_tenant_admin:
            raise HTTPException(403, "Admin permissions required to search users")
        
        # Search users from database (handled at database level)
        result = await get_user_service().list_users(page, page_size, None, q)
        matching_users = result["users"]
        total_count = result["total_count"]
        
        user_responses = [
            UserResponse(
                id=u.id,
                email=u.email,
                name=u.name,
                status=u.status,
                created_at=u.created_at,
                updated_at=u.updated_at,
                last_login_at=u.last_login_at,
                email_verified_at=u.email_verified_at
            ) for u in matching_users
        ]
        
        return UserListResponse(
            users=user_responses,
            total_count=total_count,
            page=page,
            page_size=page_size
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("User search failed", query=q, error=str(e))
        raise HTTPException(500, "User search failed")

@router.get("/users/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user's profile"""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        status=current_user.status,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        last_login_at=current_user.last_login_at,
        email_verified_at=current_user.email_verified_at
    )

@router.put("/users/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """Update current user's profile"""
    try:
        # Apply updates to current user
        update_data = user_update.dict(exclude_none=True)
        for field, value in update_data.items():
            if field != "status":  # Users cannot change their own status
                setattr(current_user, field, value)
        
        current_user.updated_at = datetime.utcnow()
        
        # Update user profile in database
        filtered_update_data = {k: v for k, v in update_data.items() if k != "status"}
        await get_user_service().update_user(current_user.id, {
            **filtered_update_data,
            "updated_at": current_user.updated_at
        })
        
        logger.info("User profile updated",
                   user_id=current_user.id,
                   fields=list(update_data.keys()))
        
        return UserResponse(
            id=current_user.id,
            email=current_user.email,
            name=current_user.name,
            status=current_user.status,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
            last_login_at=current_user.last_login_at,
            email_verified_at=current_user.email_verified_at
        )
        
    except Exception as e:
        logger.error("Profile update failed", user_id=current_user.id, error=str(e))
        raise HTTPException(500, "Profile update failed")

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Get user by ID"""
    try:
        user = await get_user_service().get_user_by_id(user_id)
        if not user:
            raise HTTPException(404, f"User {user_id} not found")
        
        # Check permissions - users can view themselves or admins can view anyone
        current_tenant_id = request.headers.get("X-Customer-ID", "platform")
        is_self = user.id == current_user.id
        is_platform_admin = any(
            r["tenant_id"] == "platform" for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        # For cross-tenant access attempts, block unless platform admin
        user_current_tenant = current_user.id == user.id  # Current user accessing their own profile
        if not user_current_tenant and not is_platform_admin:
            # This is a cross-user access attempt - only allow if user has admin permissions in current tenant
            is_tenant_admin = any(
                r["tenant_id"] == current_tenant_id and r["role"] in ["tenant_admin", "super_admin"]
                for r in request.state.roles
            ) if hasattr(request.state, "roles") else False
            
            if not is_tenant_admin:
                raise HTTPException(403, "Cross-tenant access denied")
        
        # Additional check - if not self and not admin, deny
        if not is_self and not is_platform_admin:
            # Check if user is tenant admin for current tenant
            is_tenant_admin = any(
                r["tenant_id"] == current_tenant_id and r["role"] in ["tenant_admin", "super_admin"]
                for r in request.state.roles
            ) if hasattr(request.state, "roles") else False
            
            if not is_tenant_admin:
                raise HTTPException(403, "Can only view your own profile or need admin access")
        
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            status=user.status,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login_at,
            email_verified_at=user.email_verified_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("User retrieval failed", user_id=user_id, error=str(e))
        raise HTTPException(500, "User retrieval failed")

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Update user account"""
    try:
        user = await get_user_service().get_user_by_id(user_id)
        if not user:
            raise HTTPException(404, f"User {user_id} not found")
        
        # Check permissions - users can update themselves or admins can update anyone
        is_self = user.id == current_user.id
        is_platform_admin = any(
            r["tenant_id"] == "platform" for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        if not is_self and not is_platform_admin:
            raise HTTPException(403, "Can only update your own profile or need admin access")
        
        # Apply updates through user service (database-enabled)
        update_data = user_update.dict(exclude_none=True)
        updated_user = await get_user_service().update_user(user.id, update_data)
        
        if not updated_user:
            raise HTTPException(500, "User update failed - could not retrieve updated user")
        
        logger.info("User updated", 
                   user_id=updated_user.id,
                   updated_by=current_user.id,
                   fields=list(update_data.keys()))
        
        return UserResponse(
            id=updated_user.id,
            email=updated_user.email,
            name=updated_user.name,
            status=updated_user.status,
            created_at=updated_user.created_at,
            updated_at=updated_user.updated_at,
            last_login_at=updated_user.last_login_at,
            email_verified_at=updated_user.email_verified_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("User update failed", user_id=user_id, error=str(e))
        raise HTTPException(500, "User update failed")

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Delete user account"""
    try:
        user = await get_user_service().get_user_by_id(user_id)
        if not user:
            raise HTTPException(404, f"User {user_id} not found")
        
        # Only platform admins or tenant admins can delete users
        is_platform_admin = any(
            r["tenant_id"] == "platform" for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        if not is_platform_admin:
            # Check if user is tenant admin for the user being deleted
            # This would require checking user's tenant memberships
            raise HTTPException(403, "Admin permissions required to delete users")
        
        # Soft delete using user service (database-enabled)
        deleted = await get_user_service().delete_user(user.id)
        
        logger.info("User deleted", 
                   user_id=user.id,
                   deleted_by=current_user.id)
        
        return {"message": "User deleted successfully", "user_id": user_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("User deletion failed", user_id=user_id, error=str(e))
        raise HTTPException(500, "User deletion failed")

@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = 1,
    page_size: int = 50,
    search: Optional[str] = None,
    status: Optional[UserStatus] = None,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """List users (filtered by current user's scope)"""
    try:
        # Get user's accessible scope
        tenant_id = request.headers.get("X-Customer-ID", "platform")
        
        # Platform admins can see all users
        is_platform_admin = any(
            r["tenant_id"] == "platform" for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        # Tenant admins can see users in their tenant
        is_tenant_admin = any(
            r["tenant_id"] == tenant_id and r["role"] == "tenant_admin" 
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        if not is_platform_admin and not is_tenant_admin:
            # Regular users can only see themselves
            users = [current_user]
            total_count = 1
        else:
            # Query database with proper filtering (search handled at database level)
            result = await get_user_service().list_users(page, page_size, status, search)
            users = result["users"]
            total_count = result["total_count"]
        
        # Convert to response format  
        user_responses = [
            UserResponse(
                id=u.id,
                email=u.email,
                name=u.name,
                status=u.status,
                created_at=u.created_at,
                updated_at=u.updated_at,
                last_login_at=u.last_login_at,
                email_verified_at=u.email_verified_at
            ) for u in users
        ]
        
        return UserListResponse(
            users=user_responses,
            total_count=total_count,
            page=page,
            page_size=page_size
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("User listing failed", error=str(e))
        raise HTTPException(500, "User listing failed")

# =================================================================
# PLATFORM ADMIN USER MANAGEMENT
# =================================================================

@router.post("/admin/users", response_model=UserResponse, status_code=201)
async def create_admin_user(
    user_request: UserCreateRequest,
    current_admin: User = Depends(require_platform_admin)
):
    """Create platform admin user (platform admins only)"""
    try:
        # Check if admin user already exists
        existing_user = await get_user_service().get_user_by_email(user_request.email)
        if existing_user:
            raise HTTPException(409, f"Admin user with email {user_request.email} already exists")
        
        # Create admin user
        user_data = user_request.dict()
        user_data["status"] = UserStatus.ACTIVE  # Admin users start active
        
        new_admin = await get_user_service().create_user(user_data)
        
        logger.info("Admin user created", 
                   admin_user_id=new_admin.id,
                   email=new_admin.email,
                   created_by=current_admin.id)
        
        return UserResponse(
            id=new_admin.id,
            email=new_admin.email,
            name=new_admin.name,
            status=new_admin.status,
            created_at=new_admin.created_at,
            updated_at=new_admin.updated_at,
            last_login_at=new_admin.last_login_at,
            email_verified_at=new_admin.email_verified_at
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (including 409 for duplicate email)
        raise
    except ValueError as e:
        # Handle password validation errors
        raise HTTPException(400, f"Password validation failed: {str(e)}")
    except Exception as e:
        logger.error("Admin user creation failed", error=str(e))
        raise HTTPException(500, "Admin user creation failed")

@router.get("/admin/users", response_model=UserListResponse)
async def list_admin_users(
    page: int = 1,
    page_size: int = 50,
    current_admin: User = Depends(require_platform_admin)
):
    """List platform admin users (platform admins only)"""
    try:
        # Query database for users with platform admin roles
        result = await get_user_service().list_platform_admin_users(page, page_size)
        users = result["users"]
        total_count = result["total_count"]
        
        user_responses = [
            UserResponse(
                id=u.id,
                email=u.email,
                name=u.name,
                status=u.status,
                created_at=u.created_at,
                updated_at=u.updated_at,
                last_login_at=u.last_login_at,
                email_verified_at=u.email_verified_at
            ) for u in users
        ]
        
        return UserListResponse(
            users=user_responses,
            total_count=total_count,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error("Admin user listing failed", error=str(e))
        raise HTTPException(500, "Admin user listing failed")

@router.put("/admin/users/{user_id}", response_model=UserResponse)
async def update_admin_user(
    user_id: str,
    user_update: UserUpdateRequest,
    current_admin: User = Depends(require_platform_admin)
):
    """Update admin user (platform admins only)"""
    try:
        user = await get_user_service().get_user_by_id(user_id)
        if not user:
            raise HTTPException(404, f"Admin user {user_id} not found")
        
        # Verify target user has platform roles
        has_platform_roles = await get_user_service().verify_user_has_platform_roles(user_id)
        if not has_platform_roles:
            raise HTTPException(403, "Target user does not have platform admin roles")
        
        # Apply updates
        update_data = user_update.dict(exclude_none=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        
        user.updated_at = datetime.utcnow()
        
        # Update user in database
        await get_user_service().update_user(user.id, {
            "status": user.status,
            "updated_at": user.updated_at
        })
        
        logger.info("Admin user updated",
                   user_id=user.id,
                   updated_by=current_admin.id,
                   fields=list(update_data.keys()))
        
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            status=user.status,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login_at,
            email_verified_at=user.email_verified_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Admin user update failed", user_id=user_id, error=str(e))
        raise HTTPException(500, "Admin user update failed")

@router.delete("/admin/users/{user_id}")
async def delete_admin_user(
    user_id: str,
    current_admin: User = Depends(require_platform_admin)
):
    """Delete admin user (platform admins only)"""
    try:
        user = await get_user_service().get_user_by_id(user_id)
        if not user:
            raise HTTPException(404, f"Admin user {user_id} not found")
        
        # Prevent self-deletion
        if user.id == current_admin.id:
            raise HTTPException(400, "Cannot delete your own admin account")
        
        # Verify target user has platform roles
        has_platform_roles = await get_user_service().verify_user_has_platform_roles(user_id)
        if not has_platform_roles:
            raise HTTPException(403, "Target user does not have platform admin roles")
        
        # Check if this is the last super_admin (prevent lockout)
        super_admin_count = await get_user_service().check_super_admin_count()
        if super_admin_count <= 1:
            raise HTTPException(400, "Cannot delete the last super admin - this would lock out the platform")
        
        # Soft delete
        user.status = UserStatus.INACTIVE
        user.updated_at = datetime.utcnow()
        
        # Soft delete user in database
        await get_user_service().update_user(user.id, {
            "status": user.status,
            "updated_at": user.updated_at
        })
        
        # Revoke all sessions for security
        revoked_sessions = await get_user_service().revoke_all_user_sessions_for_security(user_id)
        logger.info("User sessions revoked for security", user_id=user_id, revoked_count=revoked_sessions)
        
        logger.info("Admin user deleted",
                   user_id=user.id,
                   deleted_by=current_admin.id)
        
        return {"message": "Admin user deleted successfully", "user_id": user_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Admin user deletion failed", user_id=user_id, error=str(e))
        raise HTTPException(500, "Admin user deletion failed")

@router.get("/admin/users/{user_id}", response_model=UserResponse)
async def get_admin_user(
    user_id: str,
    current_admin: User = Depends(require_platform_admin)
):
    """Get admin user details (platform admins only)"""
    try:
        user = await get_user_service().get_user_by_id(user_id)
        if not user:
            raise HTTPException(404, f"Admin user {user_id} not found")
        
        # Verify target user has platform roles
        has_platform_roles = await get_user_service().verify_user_has_platform_roles(user_id)
        if not has_platform_roles:
            raise HTTPException(403, "Target user does not have platform admin roles")
        
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            status=user.status,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login_at,
            email_verified_at=user.email_verified_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Admin user retrieval failed", user_id=user_id, error=str(e))
        raise HTTPException(500, "Admin user retrieval failed")

# =================================================================
# USER PROFILE MANAGEMENT
# =================================================================


# =================================================================
# USER SEARCH & FILTERING
# =================================================================


# =================================================================
# BULK USER OPERATIONS
# =================================================================

@router.post("/users/bulk-create", response_model=List[UserResponse])
async def bulk_create_users(
    users: List[UserCreateRequest],
    current_admin: User = Depends(require_platform_admin)
):
    """Bulk create multiple users (platform admins only)"""
    try:
        if len(users) > 500:
            raise HTTPException(400, "Bulk creation limited to 500 users")

        created_users = []
        errors = []

        # Batch check for existing emails (O(1) query instead of O(n))
        all_emails = [u.email.lower() for u in users]
        existing_emails = await get_user_service().get_existing_emails_batch(all_emails)

        for user_request in users:
            try:
                # Check if user exists using batch result
                if user_request.email.lower() in existing_emails:
                    errors.append(f"User {user_request.email} already exists")
                    continue

                # Create user
                user_data = user_request.dict()
                new_user = await get_user_service().create_user(user_data)
                created_users.append(new_user)

                # Add to existing set to prevent duplicates within same batch
                existing_emails.add(user_request.email.lower())

            except Exception as e:
                errors.append(f"Failed to create {user_request.email}: {str(e)}")

        logger.info("Bulk user creation completed",
                   created_count=len(created_users),
                   error_count=len(errors),
                   created_by=current_admin.id)

        if errors:
            logger.warning("Bulk creation errors", errors=errors)

        # Return successfully created users
        return [
            UserResponse(
                id=u.id,
                email=u.email,
                name=u.name,
                status=u.status,
                created_at=u.created_at,
                updated_at=u.updated_at,
                last_login_at=u.last_login_at,
                email_verified_at=u.email_verified_at
            ) for u in created_users
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Bulk user creation failed", error=str(e))
        raise HTTPException(500, "Bulk user creation failed")