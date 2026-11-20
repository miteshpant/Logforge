"""
M8 Authentication API
FastAPI router for authentication operations: login, logout, setup, password management, invitations
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from datetime import datetime, timedelta
from typing import Optional
import asyncio

import structlog
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from models import (
    LoginRequest, LoginResponse, RefreshRequest, LogoutRequest,
    UserResponse, UserCreateRequest,
    SetupTokenResponse, AdminSetupRequest,
    InvitationRequest, InvitationResponse, AcceptInviteRequest,
    PasswordResetRequest, PasswordChangeRequest,
    User, UserRole, UserStatus
)
from authn_authz_middleware import (
    # ENH-013/ENH-014: `setup_token_manager` is imported as an ACCESSOR, not as
    # the instance. Importing the instance triggered its construction (and a
    # database connection) at module import time.
    get_setup_token_manager, invitation_manager,
    get_current_user, generate_secure_token, require_platform_admin
)
from services.user_service import UserService
from tenant_dependencies import MiddlewareTenant
import uuid
import os

logger = structlog.get_logger()

# Create router for authentication
router = APIRouter(prefix="/v1/auth", tags=["Authentication"])

# Initialize services using proper service layer.
#
# ENH-013/ENH-010: `UserService()` opens a database connection in its
# constructor, so building it here connected during `import routers.auth_api`,
# making the login endpoint untestable without live infrastructure.
# Built on first use; the PEP 562 hook below preserves the bare
# `user_service` name at every call site.
_user_service_instance: Optional[UserService] = None


class ResetConfirmBody(BaseModel):
    token: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., min_length=1, max_length=200)


class VerifyEmailBody(BaseModel):
    token: str = Field(..., min_length=1, max_length=200)


def _role_service():
    from routers.role_api import get_role_service

    return get_role_service()


def get_user_service() -> UserService:
    """Get the shared UserService, constructing it on first use."""
    global _user_service_instance
    if _user_service_instance is None:
        _user_service_instance = UserService()
    return _user_service_instance


def __getattr__(name: str):
    """Resolve `user_service` lazily (PEP 562)."""
    if name == "user_service":
        return get_user_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# LF-015: rotating refresh tokens. Issuance is feature-flagged so a rollback
# is a config change, not a deploy; the UI tolerates a missing refresh token.
def _refresh_tokens_enabled() -> bool:
    return os.getenv("LOGFORGE_REFRESH_TOKENS_ENABLED", "true").lower() == "true"


_refresh_token_service = None


def get_refresh_token_service():
    """Shared RefreshTokenService bound to the UserDAO database layer."""
    global _refresh_token_service
    if _refresh_token_service is None:
        from services.refresh_token_service import RefreshTokenService
        _refresh_token_service = RefreshTokenService(get_user_service().user_dao.db)
    return _refresh_token_service

# =================================================================
# AUTHENTICATION ENDPOINTS
# =================================================================

async def _finish_login(user, request: Request, email: str) -> LoginResponse:
    """Issue the session for a user whose credentials (and MFA code, if enrolled) checked out."""
    from login_throttle import get_login_throttle

    ip_address = request.client.host if request.client else "unknown"
    # Get user's tenant roles to determine primary tenant context
    from services.role_service import RoleService
    role_service = RoleService()
    user_roles = await role_service.get_user_roles(user.id)
    
    # Determine primary tenant ID from user's roles
    primary_tenant_id = None  # No default - user must have tenant assignment
    if user_roles:
        # Use the first role's tenant_id as primary tenant context
        primary_tenant_id = user_roles[0].tenant_id
    
    if not primary_tenant_id:
        logger.error("User has no tenant role assignments", user_id=user.id, email=user.email)
        raise HTTPException(403, "User has no tenant role assignments. Contact administrator.")
    
    # Create session with tenant context
    user_agent = request.headers.get("user-agent", "unknown")

    session_data = await get_user_service().create_session(user, ip_address, user_agent, primary_tenant_id, user_roles[0].role)

    # ENH-013: clear the account counter so a legitimate user who mistyped
    # a few times is not penalised after a successful login.
    await get_login_throttle().record_success(email)

    logger.info("User login successful",
               user_id=user.id,
               email=user.email,
               ip_address=ip_address)

    # LF-015: issue a rotating refresh token alongside the access token.
    refresh_token = None
    refresh_expires_at = None
    if _refresh_tokens_enabled():
        refresh_data = await get_refresh_token_service().issue(
            user.id, primary_tenant_id, ip_address, user_agent
        )
        refresh_token = refresh_data["refresh_token"]
        refresh_expires_at = refresh_data["expires_at"]

    return LoginResponse(
        access_token=session_data["access_token"],
        expires_at=session_data["expires_at"],
        refresh_token=refresh_token,
        refresh_expires_at=refresh_expires_at,
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


@router.post("/login", response_model=LoginResponse)
async def login_user(
    login_request: LoginRequest,
    request: Request
):
    """User login with email and password"""
    ip_address = request.client.host if request.client else "unknown"

    # ENH-013: brute-force / credential-stuffing defence. Checked BEFORE
    # authenticate_user(), because bcrypt verification at 12 rounds is
    # deliberately expensive -- letting unlimited attempts reach it is also a
    # CPU-exhaustion vector against our own servers.
    from login_throttle import LoginThrottleError, get_login_throttle

    throttle = get_login_throttle()
    try:
        decision = await throttle.check(login_request.email, ip_address)
    except LoginThrottleError:
        # Fail closed: if we cannot count attempts we must not accept them.
        raise HTTPException(
            503,
            "Authentication is temporarily unavailable. Please retry shortly.",
        )

    if not decision.allowed:
        logger.warning(
            "Login blocked by throttle",
            scope=decision.scope,
            ip_address=ip_address,
        )
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts. Please try again later.",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )

    try:
        # Authenticate user
        user = await get_user_service().authenticate_user(
            login_request.email,
            login_request.password
        )

        if not user:
            await throttle.record_failure(login_request.email, ip_address)
            # Log failed attempt for security monitoring
            logger.warning("Login attempt failed",
                          email=login_request.email,
                          ip_address=ip_address)
            # Deliberately identical to the "unknown account" response: the
            # message must not disclose whether the email exists.
            raise HTTPException(401, "Invalid email or password")

        # The credentials are valid, but the account must also be usable.
        # validate_session() only accepts ACTIVE users, so issuing a token to a
        # pending/inactive/suspended account produced a "successful" login whose
        # every request then failed with 401 "Invalid or expired session".
        # Checked only AFTER the password, so status never helps enumerate
        # accounts; not counted as a failed attempt (the password was right).
        if user.status != UserStatus.ACTIVE:
            logger.warning("Login refused for non-active account",
                           user_id=user.id, status=user.status.value)
            raise HTTPException(
                403,
                f"Account is {user.status.value}. Ask an administrator to activate it.",
            )

        # Phase 14 follow-up: with MFA confirmed, the password alone gets a short-lived
        # challenge, not a session; POST /v1/auth/login/mfa with a code completes it.
        enrolled = await asyncio.to_thread(_mfa_store().get, user.id)
        if enrolled and enrolled["confirmed"]:
            import mfa

            return JSONResponse({"mfa_required": True, "mfa_token": mfa.challenge(user.id)})

        return await _finish_login(user, request, login_request.email)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Login failed", error=str(e))
        raise HTTPException(500, "Login system error")

class MfaCode(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)


class MfaLogin(BaseModel):
    mfa_token: str = Field(..., min_length=1, max_length=2000)
    code: str = Field(..., min_length=1, max_length=20)


def _mfa_store():
    from dependencies import get_clickhouse_client
    from mfa import MFAStore

    return MFAStore(get_clickhouse_client())


def _verify_code(record: dict, code: str):
    """(updated record, True) if `code` is a valid TOTP code or an unused backup code."""
    import mfa

    step = mfa.check(record["secret"], code, record.get("last_step", 0))
    if step is not None:
        return {**record, "last_step": step}, True
    remaining = mfa.use_backup_code(record.get("backup_hashes") or [], code)
    if remaining is not None:
        return {**record, "backup_hashes": remaining}, True
    return record, False


@router.post("/login/mfa", response_model=LoginResponse)
async def login_mfa(body: MfaLogin, request: Request):
    """Second step of sign-in for accounts with MFA: the challenge from /login and a code."""
    import mfa
    from login_throttle import get_login_throttle

    ip_address = request.client.host if request.client else "unknown"
    try:
        user_id = mfa.open_challenge(body.mfa_token)
    except mfa.MFAError as e:
        raise HTTPException(401, str(e))
    user = await get_user_service().get_user_by_id(user_id)
    if not user:
        raise HTTPException(401, "The sign-in expired; start again")
    throttle = get_login_throttle()
    decision = await throttle.check(user.email, ip_address)
    if not decision.allowed:
        raise HTTPException(429, "Too many failed attempts. Please try again later.")
    record = await asyncio.to_thread(_mfa_store().get, user.id)
    if not record or not record["confirmed"]:
        raise HTTPException(401, "The sign-in expired; start again")
    updated, ok = _verify_code(record, body.code)
    if not ok:
        await throttle.record_failure(user.email, ip_address)
        raise HTTPException(401, "That code isn't valid")
    await asyncio.to_thread(_mfa_store().save, user.id, updated)
    return await _finish_login(user, request, user.email)


@router.get("/mfa")
async def mfa_status(current_user: User = Depends(get_current_user)):
    record = await asyncio.to_thread(_mfa_store().get, current_user.id)
    return {"enabled": bool(record and record["confirmed"]), "pending": bool(record and not record["confirmed"]),
            "backup_codes_left": len(record["backup_hashes"]) if record and record["confirmed"] else 0}


@router.post("/mfa/setup")
async def mfa_setup(current_user: User = Depends(get_current_user)):
    """Start enrolling: a new secret for the authenticator app (not active until confirmed)."""
    import mfa

    record = await asyncio.to_thread(_mfa_store().get, current_user.id)
    if record and record["confirmed"]:
        raise HTTPException(409, "MFA is already on; turn it off first to enrol a new device")
    secret = mfa.new_secret()
    await asyncio.to_thread(_mfa_store().save, current_user.id, {"secret": secret, "confirmed": False})
    return {"secret": secret, "otpauth_url": mfa.otpauth_url(secret, current_user.email)}


@router.post("/mfa/confirm")
async def mfa_confirm(body: MfaCode, current_user: User = Depends(get_current_user)):
    """Turn MFA on with a code from the app. Returns one-time backup codes, shown only now."""
    import mfa

    record = await asyncio.to_thread(_mfa_store().get, current_user.id)
    if not record or record["confirmed"]:
        raise HTTPException(400, "Start enrolment first")
    step = mfa.check(record["secret"], body.code, 0)
    if step is None:
        raise HTTPException(400, "That code isn't valid; check the app's clock")
    codes, hashes = mfa.new_backup_codes(8)
    await asyncio.to_thread(_mfa_store().save, current_user.id,
                            {"secret": record["secret"], "confirmed": True, "backup_hashes": hashes, "last_step": step})
    logger.info("MFA enabled", user_id=current_user.id)
    return {"enabled": True, "backup_codes": codes}


@router.delete("/mfa")
async def mfa_disable(body: MfaCode, current_user: User = Depends(get_current_user)):
    """Turn MFA off; needs a current code or a backup code."""
    record = await asyncio.to_thread(_mfa_store().get, current_user.id)
    if not record or not record["confirmed"]:
        raise HTTPException(400, "MFA isn't on")
    _, ok = _verify_code(record, body.code)
    if not ok:
        raise HTTPException(400, "That code isn't valid")
    await asyncio.to_thread(_mfa_store().delete, current_user.id)
    logger.info("MFA disabled", user_id=current_user.id)
    return {"enabled": False}


@router.post("/logout")
async def logout_user(
    logout_request: Optional[LogoutRequest] = None,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """User logout - invalidate session and revoke the refresh token"""
    try:
        # Extract token from request
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            await get_user_service().revoke_session(token)

        # LF-015: revoke the refresh token server-side so logout genuinely
        # ends the session — a copied refresh token must stop working.
        if logout_request and logout_request.refresh_token:
            await get_refresh_token_service().revoke(logout_request.refresh_token)

        logger.info("User logout successful", user_id=current_user.id)

        return {"message": "Logout successful"}

    except Exception as e:
        logger.error("Logout failed", user_id=current_user.id, error=str(e))
        raise HTTPException(500, "Logout system error")

@router.post("/refresh", response_model=LoginResponse)
async def refresh_session(
    refresh_request: RefreshRequest,
    request: Request
):
    """Exchange a refresh token for a new access + refresh token pair.

    LF-015: this endpoint deliberately does NOT require a valid access token
    (the old `Depends(get_current_user)` guard made it useless — it could
    never renew an expired session). The refresh token itself is the
    credential: it is validated against the server-side store, rotated
    (single use), and reuse of a rotated token revokes the whole chain.
    """
    from services.refresh_token_service import (
        RefreshTokenError, RefreshTokenReuseError
    )

    if not _refresh_tokens_enabled():
        raise HTTPException(403, "Refresh tokens are disabled")

    try:
        token_row = await get_refresh_token_service().validate_and_rotate(
            refresh_request.refresh_token
        )
    except RefreshTokenReuseError:
        raise HTTPException(401, "Refresh token reuse detected. Please log in again.")
    except RefreshTokenError:
        raise HTTPException(401, "Invalid or expired refresh token")

    try:
        user = await get_user_service().get_user_by_id(token_row["user_id"])
        if not user or user.status != UserStatus.ACTIVE:
            raise HTTPException(401, "User account is not active")

        # Get user's tenant roles to determine tenant context for refresh
        from services.role_service import RoleService
        role_service = RoleService()
        user_roles = await role_service.get_user_roles(user.id)

        # Determine tenant ID from user's roles
        primary_tenant_id = None
        if user_roles:
            primary_tenant_id = user_roles[0].tenant_id

        if not primary_tenant_id:
            logger.error("User has no tenant role assignments during refresh", user_id=user.id)
            raise HTTPException(403, "User has no tenant role assignments. Contact administrator.")

        # Create new access-token session
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        session_data = await get_user_service().create_session(
            user, ip_address, user_agent, primary_tenant_id, user_roles[0].role
        )

        # Rotation: issue the replacement refresh token
        refresh_data = await get_refresh_token_service().issue(
            user.id, primary_tenant_id, ip_address, user_agent
        )

        logger.info("Session refreshed via refresh token", user_id=user.id)

        return LoginResponse(
            access_token=session_data["access_token"],
            expires_at=session_data["expires_at"],
            refresh_token=refresh_data["refresh_token"],
            refresh_expires_at=refresh_data["expires_at"],
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

@router.get("/me/roles")
async def get_current_user_roles(
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Get current user's role assignments"""
    try:
        from services.role_service import RoleService
        role_service = RoleService()

        # Get all roles for current user
        user_roles = await role_service.get_user_roles(current_user.id)

        roles_response = []
        for role in user_roles:
            roles_response.append({
                "id": role.id,
                "tenant_id": role.tenant_id,
                "role": role.role.value if hasattr(role.role, 'value') else role.role,
                "granted_at": role.granted_at.isoformat() if role.granted_at else None,
                "status": role.status.value if hasattr(role.status, 'value') else role.status
            })

        return {
            "user_id": current_user.id,
            "roles": roles_response
        }

    except Exception as e:
        logger.error("Failed to get user roles", user_id=current_user.id, error=str(e))
        raise HTTPException(500, "Failed to retrieve user roles")

# =================================================================
# PLATFORM SETUP ENDPOINTS
# =================================================================

@router.post("/setup/init", response_model=SetupTokenResponse)
async def initialize_platform_setup():
    """Generate initial setup token for platform admin creation"""
    try:
        # Check if setup is already completed
        if get_setup_token_manager().has_setup_completed():
            raise HTTPException(400, "Platform setup already completed")
        
        # Generate setup token
        token_data = get_setup_token_manager().generate_setup_token()
        
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
        if not get_setup_token_manager().validate_setup_token(setup_request.setup_token):
            raise HTTPException(400, "Invalid or expired setup token")
        
        # Check if admin already exists with this email
        existing_user = await get_user_service().get_user_by_email(setup_request.email)
        if existing_user:
            raise HTTPException(409, f"User with email {setup_request.email} already exists")
        
        # Create initial admin user
        admin_data = {
            "email": setup_request.email,
            "name": setup_request.name,
            "password": setup_request.password,
            "status": UserStatus.ACTIVE
        }
        
        admin_user = await get_user_service().create_user(admin_data)
        
        # Assign super_admin role for platform-wide access using role service
        try:
            from services.role_service import RoleService
            role_service = RoleService()
            
            # Assign platform super admin role
            await role_service.assign_role(
                user_id=admin_user.id,
                tenant_id="platform",
                role=UserRole.SUPER_ADMIN,
                granted_by="system"
            )
            
            logger.info("Platform admin role assigned", 
                       user_id=admin_user.id, 
                       tenant_id="platform", 
                       role="super_admin")
            
        except Exception as e:
            logger.error("Failed to assign platform admin role", 
                        user_id=admin_user.id, 
                        error=str(e))
            # Continue anyway - user is created but may need manual role assignment
        
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
        user = await get_user_service().get_user_by_email(reset_request.email)
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
        
        # Update user in database
        await get_user_service().update_user(user.id, {
            "password_reset_token": user.password_reset_token,
            "password_reset_expires": user.password_reset_expires,
            "updated_at": user.updated_at
        })
        
        import account_emails

        await account_emails.send(account_emails.reset_message(user.email, reset_token))
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
    body: ResetConfirmBody,
    request: Request
):
    """Confirm password reset with token. Every session of the account ends."""
    token, new_password = body.token, body.new_password
    try:
        # Find user with valid reset token through user service
        user = await get_user_service().get_user_by_reset_token(token)
        
        if not user:
            raise HTTPException(400, "Invalid or expired reset token")
        
        # Validate new password (would use UserCreateRequest validator)
        from models import UserCreateRequest
        try:
            # Use validator from UserCreateRequest
            UserCreateRequest.validate_password_strength(new_password)
        except ValueError as e:
            raise HTTPException(400, str(e))
        
        # Update password
        from authn_authz_middleware import hash_password
        user.password_hash = hash_password(new_password)
        user.password_reset_token = None
        user.password_reset_expires = None
        user.updated_at = datetime.utcnow()
        
        # Update password in database and clear reset token
        await get_user_service().update_user(user.id, {
            "password_hash": user.password_hash,
            "password_reset_token": None,
            "password_reset_expires": None,
            "updated_at": user.updated_at
        })
        # whoever had the old password may have a session: end them all
        revoked = await get_user_service().revoke_all_user_sessions_for_security(user.id)
        logger.info("Sessions revoked after password reset", user_id=user.id, sessions=revoked)
        
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
        from authn_authz_middleware import verify_password, hash_password
        if not verify_password(password_change.current_password, current_user.password_hash):
            raise HTTPException(400, "Current password is incorrect")
        
        # Validate new password
        from models import UserCreateRequest
        try:
            UserCreateRequest.validate_password_strength(password_change.new_password)
        except ValueError as e:
            raise HTTPException(400, str(e))
        
        # Update password
        current_user.password_hash = hash_password(password_change.new_password)
        current_user.updated_at = datetime.utcnow()
        
        # Update password in database
        await get_user_service().update_user(current_user.id, {
            "password_hash": current_user.password_hash,
            "updated_at": current_user.updated_at
        })
        
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
        existing_user = await get_user_service().get_user_by_email(invitation_request.email)
        if existing_user:
            raise HTTPException(409, f"User with email {invitation_request.email} already exists")
        
        # Create invitation
        invitation_data = await invitation_manager.create_invitation(
            email=invitation_request.email,
            tenant_id=tenant_id,
            role=invitation_request.role,
            invited_by=current_user.id
        )
        
        import account_emails

        await account_emails.send(account_emails.invite_message(
            invitation_request.email, invitation_data["invitation_token"], tenant_id,
            str(getattr(invitation_request.role, "value", invitation_request.role)),
            current_user.name or current_user.email))
        
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
        invitation = await invitation_manager.validate_invitation(
            accept_request.invitation_token,
            accept_request.email
        )
        
        if not invitation:
            raise HTTPException(400, "Invalid or expired invitation")
        
        # Verify tenant ID matches invitation
        if invitation["tenant_id"] != accept_request.tenant_id:
            raise HTTPException(400, "Tenant ID does not match invitation")
        
        # Check if user already exists
        existing_user = await get_user_service().get_user_by_email(accept_request.email)
        if existing_user:
            raise HTTPException(409, f"User with email {accept_request.email} already exists")
        
        # Create user account
        user_data = {
            "email": accept_request.email,
            "name": accept_request.name,
            "password": accept_request.password,
            "status": UserStatus.ACTIVE  # Invited users start active
        }
        
        new_user = await get_user_service().create_user(user_data)
        
        # Mark invitation as accepted
        await invitation_manager.accept_invitation(accept_request.invitation_token, invitation["id"])
        
        # the role the invitation was for, granted by whoever invited
        await _role_service().assign_role(
            user_id=new_user.id, tenant_id=invitation["tenant_id"], role=UserRole(invitation["role"]),
            granted_by=invitation.get("invited_by") or "invitation")
        
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
        
        # a signed token bound to this user and address, valid 24 hours (account_tokens.py)
        import account_emails
        import account_tokens

        verification_token = account_tokens.issue(current_user.id, current_user.email, "verify_email",
                                                  timedelta(hours=24))
        await account_emails.send(account_emails.verify_message(current_user.email, verification_token))
        
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
    body: VerifyEmailBody,
    current_user: User = Depends(get_current_user)
):
    """Confirm email verification with the token that was emailed to this address"""
    import account_tokens

    try:
        if not account_tokens.check(body.token, current_user.id, current_user.email, "verify_email"):
            raise HTTPException(400, "Invalid or expired verification token")
        
        # Mark email as verified
        current_user.email_verified_at = datetime.utcnow()
        current_user.updated_at = datetime.utcnow()
        
        # Update email verification in database
        await get_user_service().update_user(current_user.id, {
            "email_verified_at": current_user.email_verified_at,
            "updated_at": current_user.updated_at
        })
        
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
        invitation_data = await invitation_manager.create_invitation(
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
        # Get user sessions through user service
        session_list = await get_user_service().get_user_sessions(current_user.id)
        
        return {"sessions": session_list, "total_count": len(session_list)}
        
    except Exception as e:
        logger.error("Session listing failed", user_id=current_user.id, error=str(e))
        raise HTTPException(500, "Session listing failed")

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
        
        # Revoke all other sessions except current through user service
        revoked_count = await get_user_service().revoke_all_user_sessions_except_current(
            current_user.id, 
            current_token
        )
        
        logger.info("All sessions revoked",
                   user_id=current_user.id,
                   revoked_count=revoked_count)
        
        return {"message": f"Revoked {revoked_count} sessions successfully"}
        
    except Exception as e:
        logger.error("Session revocation failed", user_id=current_user.id, error=str(e))
        raise HTTPException(500, "Session revocation failed")

@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Revoke specific session"""
    try:
        # Revoke session by ID through user service
        success = await get_user_service().revoke_session_by_id(session_id, current_user.id)
        
        if not success:
            raise HTTPException(404, f"Session {session_id} not found or already revoked")
        
        logger.info("Session revoked",
                   session_id=session_id,
                   user_id=current_user.id)
        
        return {"message": "Session revoked successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Session revocation failed", session_id=session_id, error=str(e))
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
        
        # Deactivate user in database
        await get_user_service().update_user(current_user.id, {
            "status": current_user.status,
            "updated_at": current_user.updated_at
        })
        # TODO: Revoke all sessions for security
        
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
        user = await get_user_service().get_user_by_id(user_id)
        if not user:
            raise HTTPException(404, f"User {user_id} not found")
        
        if user.status != UserStatus.INACTIVE:
            raise HTTPException(400, f"User is not inactive (current status: {user.status})")
        
        # Reactivate user
        user.status = UserStatus.ACTIVE
        user.updated_at = datetime.utcnow()
        
        # Reactivate user in database
        await get_user_service().update_user(user.id, {
            "status": user.status,
            "updated_at": user.updated_at
        })
        
        logger.info("Account reactivated",
                   user_id=user.id,
                   reactivated_by=current_admin.id)
        
        return {"message": "Account reactivated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Account reactivation failed", user_id=user_id, error=str(e))
        raise HTTPException(500, "Account reactivation failed")