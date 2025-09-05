"""
M8 Authentication API
FastAPI router for authentication operations: login, logout, setup, password management, invitations
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from datetime import datetime, timedelta
import structlog

from models import (
    LoginRequest, LoginResponse, UserResponse, UserCreateRequest,
    SetupTokenResponse, AdminSetupRequest,
    InvitationRequest, InvitationResponse, AcceptInviteRequest,
    PasswordResetRequest, PasswordChangeRequest,
    User, UserRole, UserStatus
)
from auth_middleware import (
    user_service, setup_token_manager, invitation_manager,
    get_current_user, generate_secure_token, require_platform_admin
)

logger = structlog.get_logger()

# Create router for authentication
router = APIRouter(prefix="/v1/auth", tags=["Authentication"])

# =================================================================
# AUTHENTICATION ENDPOINTS
# =================================================================

@router.post("/login", response_model=LoginResponse)
async def login_user(
    login_request: LoginRequest,
    request: Request
):
    """User login with email and password"""
    try:
        # Authenticate user
        user = await user_service.authenticate_user(
            login_request.email, 
            login_request.password
        )
        
        if not user:
            # Log failed attempt for security monitoring
            logger.warning("Login attempt failed",
                          email=login_request.email,
                          ip_address=request.client.host if request.client else "unknown")
            raise HTTPException(401, "Invalid email or password")
        
        # Create session
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        session_data = await user_service.create_session(user, ip_address, user_agent)
        
        logger.info("User login successful",
                   user_id=user.id,
                   email=user.email,
                   ip_address=ip_address)
        
        return LoginResponse(
            access_token=session_data["access_token"],
            expires_at=session_data["expires_at"],
            user=UserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                status=user.status,
                created_at=user.created_at,
                updated_at=user.updated_at,
                last_login_at=user.last_login_at,
                email_verified_at=user.email_verified_at
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Login failed", error=str(e))
        raise HTTPException(500, "Login system error")

@router.post("/logout")
async def logout_user(
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """User logout - invalidate session"""
    try:
        # Extract token from request
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            await user_service.revoke_session(token)
        
        logger.info("User logout successful", user_id=current_user.id)
        
        return {"message": "Logout successful"}
        
    except Exception as e:
        logger.error("Logout failed", user_id=current_user.id, error=str(e))
        raise HTTPException(500, "Logout system error")

@router.post("/refresh", response_model=LoginResponse)
async def refresh_session(
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Refresh user session with new token"""
    try:
        # Create new session
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        session_data = await user_service.create_session(current_user, ip_address, user_agent)
        
        # Revoke old session
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            old_token = auth_header.split(" ")[1]
            await user_service.revoke_session(old_token)
        
        logger.info("Session refreshed", user_id=current_user.id)
        
        return LoginResponse(
            access_token=session_data["access_token"],
            expires_at=session_data["expires_at"],
            user=UserResponse(
                id=current_user.id,
                email=current_user.email,
                name=current_user.name,
                status=current_user.status,
                created_at=current_user.created_at,
                updated_at=current_user.updated_at,
                last_login_at=current_user.last_login_at,
                email_verified_at=current_user.email_verified_at
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Session refresh failed", error=str(e))
        raise HTTPException(500, "Session refresh failed")

@router.get("/me", response_model=UserResponse)
async def get_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
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

# =================================================================
# PLATFORM SETUP ENDPOINTS
# =================================================================

@router.post("/setup/init", response_model=SetupTokenResponse)
async def initialize_platform_setup():
    """Generate initial setup token for platform admin creation"""
    try:
        # Check if setup is already completed
        if setup_token_manager.has_setup_completed():
            raise HTTPException(400, "Platform setup already completed")
        
        # Generate setup token
        token_data = setup_token_manager.generate_setup_token()
        
        logger.info("Platform setup initialized", 
                   expires_at=token_data["expires_at"])
        
        return SetupTokenResponse(
            setup_token=token_data["setup_token"],
            expires_at=token_data["expires_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Setup initialization failed", error=str(e))
        raise HTTPException(500, "Setup initialization failed")

@router.post("/setup", response_model=UserResponse, status_code=201)
async def complete_platform_setup(
    setup_request: AdminSetupRequest,
    request: Request
):
    """Complete initial platform setup by creating first admin"""
    try:
        # Validate setup token
        if not setup_token_manager.validate_setup_token(setup_request.setup_token):
            raise HTTPException(400, "Invalid or expired setup token")
        
        # Check if admin already exists with this email
        existing_user = await user_service.get_user_by_email(setup_request.email)
        if existing_user:
            raise HTTPException(409, f"User with email {setup_request.email} already exists")
        
        # Create initial admin user
        admin_data = {
            "email": setup_request.email,
            "name": setup_request.name,
            "password": setup_request.password,
            "status": UserStatus.ACTIVE
        }
        
        admin_user = await user_service.create_user(admin_data)
        
        # TODO: Assign super_admin role to platform tenant
        # This would be handled by role management system
        
        logger.info("Platform setup completed",
                   admin_user_id=admin_user.id,
                   email=admin_user.email,
                   ip_address=request.client.host if request.client else "unknown")
        
        return UserResponse(
            id=admin_user.id,
            email=admin_user.email,
            name=admin_user.name,
            status=admin_user.status,
            created_at=admin_user.created_at,
            updated_at=admin_user.updated_at,
            last_login_at=admin_user.last_login_at,
            email_verified_at=admin_user.email_verified_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Platform setup failed", error=str(e))
        raise HTTPException(500, "Platform setup failed")

# =================================================================
# PASSWORD MANAGEMENT
# =================================================================

@router.post("/password/reset")
async def request_password_reset(
    reset_request: PasswordResetRequest,
    request: Request
):
    """Request password reset token"""
    try:
        # Find user by email
        user = await user_service.get_user_by_email(reset_request.email)
        if not user:
            # Don't reveal if email exists - security best practice
            logger.warning("Password reset requested for non-existent email",
                          email=reset_request.email)
            return {"message": "Password reset instructions sent if email exists"}
        
        # Generate reset token
        reset_token = generate_secure_token(32)
        expires_at = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
        
        # Update user with reset token
        user.password_reset_token = reset_token
        user.password_reset_expires = expires_at
        user.updated_at = datetime.utcnow()
        
        # TODO: Save to database
        user_service.users_cache[user.id] = user
        
        # TODO: Send reset email
        logger.info("Password reset requested",
                   user_id=user.id,
                   email=user.email,
                   ip_address=request.client.host if request.client else "unknown")
        
        return {"message": "Password reset instructions sent if email exists"}
        
    except Exception as e:
        logger.error("Password reset request failed", error=str(e))
        raise HTTPException(500, "Password reset request failed")

@router.post("/password/reset-confirm")
async def confirm_password_reset(
    token: str,
    new_password: str,
    request: Request
):
    """Confirm password reset with token"""
    try:
        # Find user with valid reset token
        user = None
        for u in user_service.users_cache.values():
            if (u.password_reset_token == token and 
                u.password_reset_expires and
                datetime.utcnow() < u.password_reset_expires):
                user = u
                break
        
        if not user:
            raise HTTPException(400, "Invalid or expired reset token")
        
        # Validate new password (would use UserCreateRequest validator)
        from models import UserCreateRequest
        try:
            # Use validator from UserCreateRequest
            UserCreateRequest.validate_password_strength(None, new_password)
        except ValueError as e:
            raise HTTPException(400, str(e))
        
        # Update password
        from auth_middleware import hash_password
        user.password_hash = hash_password(new_password)
        user.password_reset_token = None
        user.password_reset_expires = None
        user.updated_at = datetime.utcnow()
        
        # TODO: Save to database and revoke all existing sessions
        user_service.users_cache[user.id] = user
        
        logger.info("Password reset completed",
                   user_id=user.id,
                   email=user.email)
        
        return {"message": "Password reset successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Password reset confirmation failed", error=str(e))
        raise HTTPException(500, "Password reset confirmation failed")

@router.post("/password/change")
async def change_password(
    password_change: PasswordChangeRequest,
    current_user: User = Depends(get_current_user)
):
    """Change user password"""
    try:
        # Verify current password
        from auth_middleware import verify_password, hash_password
        if not verify_password(password_change.current_password, current_user.password_hash):
            raise HTTPException(400, "Current password is incorrect")
        
        # Validate new password
        from models import UserCreateRequest
        try:
            UserCreateRequest.validate_password_strength(None, password_change.new_password)
        except ValueError as e:
            raise HTTPException(400, str(e))
        
        # Update password
        current_user.password_hash = hash_password(password_change.new_password)
        current_user.updated_at = datetime.utcnow()
        
        # TODO: Save to database
        user_service.users_cache[current_user.id] = current_user
        
        logger.info("Password changed", user_id=current_user.id)
        
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Password change failed", user_id=current_user.id, error=str(e))
        raise HTTPException(500, "Password change failed")

# =================================================================
# USER INVITATION SYSTEM
# =================================================================

@router.post("/invite", response_model=InvitationResponse)
async def invite_user(
    invitation_request: InvitationRequest,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Send user invitation (tenant admins and platform admins)"""
    try:
        # Verify current user has permission to invite to this tenant
        tenant_id = invitation_request.tenant_id
        
        # Platform admins can invite to any tenant
        is_platform_admin = any(
            r["tenant_id"] == "platform" for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        # Tenant admins can invite to their tenant
        is_tenant_admin = any(
            r["tenant_id"] == tenant_id and r["role"] == "tenant_admin"
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        if not is_platform_admin and not is_tenant_admin:
            raise HTTPException(403, f"No permission to invite users to tenant {tenant_id}")
        
        # Check if user already exists
        existing_user = await user_service.get_user_by_email(invitation_request.email)
        if existing_user:
            raise HTTPException(409, f"User with email {invitation_request.email} already exists")
        
        # Create invitation
        invitation_data = invitation_manager.create_invitation(
            email=invitation_request.email,
            tenant_id=tenant_id,
            role=invitation_request.role,
            invited_by=current_user.id
        )
        
        # TODO: Send invitation email
        
        logger.info("User invitation created",
                   invited_email=invitation_request.email,
                   tenant_id=tenant_id,
                   role=invitation_request.role,
                   invited_by=current_user.id)
        
        return InvitationResponse(**invitation_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("User invitation failed", error=str(e))
        raise HTTPException(500, "User invitation failed")

@router.post("/accept-invite", response_model=UserResponse, status_code=201)
async def accept_invitation(
    accept_request: AcceptInviteRequest,
    request: Request
):
    """Accept user invitation and create account"""
    try:
        # Validate invitation token
        invitation = invitation_manager.validate_invitation(
            accept_request.invitation_token,
            accept_request.email
        )
        
        if not invitation:
            raise HTTPException(400, "Invalid or expired invitation")
        
        # Verify tenant ID matches invitation
        if invitation["tenant_id"] != accept_request.tenant_id:
            raise HTTPException(400, "Tenant ID does not match invitation")
        
        # Check if user already exists
        existing_user = await user_service.get_user_by_email(accept_request.email)
        if existing_user:
            raise HTTPException(409, f"User with email {accept_request.email} already exists")
        
        # Create user account
        user_data = {
            "email": accept_request.email,
            "name": accept_request.name,
            "password": accept_request.password,
            "status": UserStatus.ACTIVE  # Invited users start active
        }
        
        new_user = await user_service.create_user(user_data)
        
        # Mark invitation as accepted
        invitation_manager.accept_invitation(accept_request.invitation_token)
        
        # TODO: Assign role from invitation to user for tenant
        # This would be handled by role management system
        
        logger.info("Invitation accepted",
                   user_id=new_user.id,
                   email=new_user.email,
                   tenant_id=accept_request.tenant_id,
                   role=invitation["role"])
        
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Invitation acceptance failed", error=str(e))
        raise HTTPException(500, "Invitation acceptance failed")

# =================================================================
# EMAIL VERIFICATION
# =================================================================

@router.post("/verify-email")
async def send_email_verification(
    current_user: User = Depends(get_current_user)
):
    """Send email verification token"""
    try:
        if current_user.email_verified_at:
            raise HTTPException(400, "Email already verified")
        
        # Generate verification token
        verification_token = generate_secure_token(32)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        # TODO: Store verification token and send email
        
        logger.info("Email verification sent",
                   user_id=current_user.id,
                   email=current_user.email)
        
        return {"message": "Verification email sent"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Email verification failed", user_id=current_user.id, error=str(e))
        raise HTTPException(500, "Email verification failed")

@router.post("/verify-email-confirm")
async def confirm_email_verification(
    token: str,
    current_user: User = Depends(get_current_user)
):
    """Confirm email verification with token"""
    try:
        # TODO: Validate verification token
        
        # Mark email as verified
        current_user.email_verified_at = datetime.utcnow()
        current_user.updated_at = datetime.utcnow()
        
        # TODO: Save to database
        user_service.users_cache[current_user.id] = current_user
        
        logger.info("Email verified",
                   user_id=current_user.id,
                   email=current_user.email)
        
        return {"message": "Email verified successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Email verification confirmation failed", 
                    user_id=current_user.id, error=str(e))
        raise HTTPException(500, "Email verification confirmation failed")

# =================================================================
# TENANT ONBOARDING FLOWS
# =================================================================

@router.post("/tenant-onboard", response_model=InvitationResponse)
async def onboard_tenant(
    tenant_name: str,
    admin_email: str,
    subscription_tier: str = "professional",
    current_admin: User = Depends(get_current_user),
    request: Request = None
):
    """Platform admin creates tenant and invites admin (simplified endpoint)"""
    try:
        # Verify platform admin permissions
        is_platform_admin = any(
            r["tenant_id"] == "platform" for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        if not is_platform_admin:
            raise HTTPException(403, "Platform admin access required")
        
        # TODO: Create tenant using tenant service
        # For now, simulate tenant creation
        import uuid
        tenant_id = str(uuid.uuid4())
        
        # Create invitation for tenant admin
        invitation_data = invitation_manager.create_invitation(
            email=admin_email,
            tenant_id=tenant_id,
            role=UserRole.TENANT_ADMIN,
            invited_by=current_admin.id
        )
        
        # TODO: Send onboarding email with invitation
        
        logger.info("Tenant onboarding initiated",
                   tenant_id=tenant_id,
                   tenant_name=tenant_name,
                   admin_email=admin_email,
                   created_by=current_admin.id)
        
        return InvitationResponse(**invitation_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Tenant onboarding failed", error=str(e))
        raise HTTPException(500, "Tenant onboarding failed")

# =================================================================
# SESSION MANAGEMENT
# =================================================================

@router.get("/sessions")
async def list_user_sessions(
    current_user: User = Depends(get_current_user)
):
    """List current user's active sessions"""
    try:
        # TODO: Query database for user's sessions
        user_sessions = [
            session for session in user_service.sessions_cache.values()
            if session.user_id == current_user.id and session.status.value == "active"
        ]
        
        session_list = []
        for session in user_sessions:
            session_list.append({
                "id": session.id,
                "ip_address": session.ip_address,
                "user_agent": session.user_agent,
                "created_at": session.created_at,
                "last_activity": session.last_activity,
                "expires_at": session.expires_at
            })
        
        return {"sessions": session_list, "total_count": len(session_list)}
        
    except Exception as e:
        logger.error("Session listing failed", user_id=current_user.id, error=str(e))
        raise HTTPException(500, "Session listing failed")

@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Revoke specific session"""
    try:
        # Find session
        target_session = None
        for session in user_service.sessions_cache.values():
            if session.id == session_id and session.user_id == current_user.id:
                target_session = session
                break
        
        if not target_session:
            raise HTTPException(404, f"Session {session_id} not found")
        
        # Revoke session
        await user_service.revoke_session(target_session.session_token)
        
        logger.info("Session revoked",
                   session_id=session_id,
                   user_id=current_user.id)
        
        return {"message": "Session revoked successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Session revocation failed", session_id=session_id, error=str(e))
        raise HTTPException(500, "Session revocation failed")

@router.delete("/sessions/all")
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Revoke all user sessions except current"""
    try:
        # Get current session token
        auth_header = request.headers.get("Authorization", "")
        current_token = None
        if auth_header.startswith("Bearer "):
            current_token = auth_header.split(" ")[1]
        
        # Revoke all other sessions
        revoked_count = 0
        for session in user_service.sessions_cache.values():
            if (session.user_id == current_user.id and 
                session.session_token != current_token and
                session.status.value == "active"):
                await user_service.revoke_session(session.session_token)
                revoked_count += 1
        
        logger.info("All sessions revoked",
                   user_id=current_user.id,
                   revoked_count=revoked_count)
        
        return {"message": f"Revoked {revoked_count} sessions successfully"}
        
    except Exception as e:
        logger.error("Session revocation failed", user_id=current_user.id, error=str(e))
        raise HTTPException(500, "Session revocation failed")

# =================================================================
# ACCOUNT MANAGEMENT
# =================================================================

@router.post("/deactivate")
async def deactivate_account(
    current_user: User = Depends(get_current_user)
):
    """Deactivate current user account"""
    try:
        # Mark user as inactive
        current_user.status = UserStatus.INACTIVE
        current_user.updated_at = datetime.utcnow()
        
        # TODO: Save to database and revoke all sessions
        user_service.users_cache[current_user.id] = current_user
        
        logger.info("Account deactivated", user_id=current_user.id)
        
        return {"message": "Account deactivated successfully"}
        
    except Exception as e:
        logger.error("Account deactivation failed", user_id=current_user.id, error=str(e))
        raise HTTPException(500, "Account deactivation failed")

@router.post("/reactivate/{user_id}")
async def reactivate_account(
    user_id: str,
    current_admin: User = Depends(require_platform_admin)
):
    """Reactivate user account (platform admins only)"""
    try:
        user = await user_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(404, f"User {user_id} not found")
        
        if user.status != UserStatus.INACTIVE:
            raise HTTPException(400, f"User is not inactive (current status: {user.status})")
        
        # Reactivate user
        user.status = UserStatus.ACTIVE
        user.updated_at = datetime.utcnow()
        
        # TODO: Save to database
        user_service.users_cache[user.id] = user
        
        logger.info("Account reactivated",
                   user_id=user.id,
                   reactivated_by=current_admin.id)
        
        return {"message": "Account reactivated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Account reactivation failed", user_id=user_id, error=str(e))
        raise HTTPException(500, "Account reactivation failed")