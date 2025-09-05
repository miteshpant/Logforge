"""
M8 Authentication & Authorization Middleware
Provides authentication, authorization, and API usage tracking for Logforge platform
"""

import asyncio
import time
import secrets
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from models import (
    User, UserSession, UserTenantRole, APIUsageAudit,
    UserRole, UserStatus, SessionStatus
)

logger = structlog.get_logger()

# Authentication configuration
JWT_SECRET = "logforge-jwt-secret-key-change-in-production"  # TODO: Use env variable
JWT_ALGORITHM = "HS256"
SESSION_EXPIRY_HOURS = 8

# Security scheme
security = HTTPBearer()

# =================================================================
# USAGE TRACKING SYSTEM (ASYNC ZERO-LATENCY)
# =================================================================

class UsageBuffer:
    """Batched usage tracking for zero-latency API calls"""
    
    def __init__(self):
        self.buffer: List[Dict[str, Any]] = []
        self.batch_size = 100
        self.flush_interval = 30  # seconds
        self._last_flush = time.time()
        
    async def add_usage(self, usage_data: Dict[str, Any]):
        """Add usage data to buffer, flush when batch size reached"""
        self.buffer.append(usage_data)
        
        # Flush if batch size reached or time interval exceeded
        if (len(self.buffer) >= self.batch_size or 
            time.time() - self._last_flush > self.flush_interval):
            await self.flush_batch()
    
    async def flush_batch(self):
        """Batch insert to database with retry logic"""
        if not self.buffer:
            return
            
        try:
            await self._insert_usage_batch(self.buffer.copy())
            self.buffer.clear()
            self._last_flush = time.time()
            logger.info(f"Usage batch flushed", count=len(self.buffer))
        except Exception as e:
            logger.error(f"Usage tracking batch failed", error=str(e))
            # Keep buffer for retry on next flush
    
    async def _insert_usage_batch(self, usage_records: List[Dict[str, Any]]):
        """Insert usage records to database (implement with actual DB)"""
        # TODO: Implement actual database insertion
        # For now, just log the records
        logger.info("Usage batch insert", records=len(usage_records))
        pass

# Global usage buffer instance
usage_buffer = UsageBuffer()

# =================================================================
# AUTHENTICATION UTILITIES
# =================================================================

def hash_password(password: str) -> str:
    """Hash password using bcrypt with 12 rounds"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_jwt_token(user_id: str, expires_in_hours: int = SESSION_EXPIRY_HOURS) -> Dict[str, Any]:
    """Generate JWT token for user session"""
    now = datetime.utcnow()
    expires = now + timedelta(hours=expires_in_hours)
    
    payload = {
        "user_id": user_id,
        "iat": now.timestamp(),
        "exp": expires.timestamp(),
        "type": "access_token"
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {
        "access_token": token,
        "expires_at": expires
    }

def decode_jwt_token(token: str) -> Dict[str, Any]:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

def generate_secure_token(length: int = 32) -> str:
    """Generate cryptographically secure token"""
    return secrets.token_urlsafe(length)

# =================================================================
# BILLING FEATURE MAPPING
# =================================================================

BILLING_FEATURE_MAP = {
    # Ingestion endpoints
    "/v1/ingestion/json": "ingestion.basic",
    "/v1/ingestion/syslog": "ingestion.basic",
    "/v1/ingestion/otlp": "ingestion.basic",
    "/v1/ingestion/cef": "ingestion.basic",
    "/v1/ingestion/nginx": "ingestion.basic",
    "/v1/ingestion/text": "ingestion.basic",
    
    # Query endpoints
    "/v1/query/advanced": "queries.advanced",
    "/v1/logs/search": "queries.advanced",
    "/v1/logs": "queries.basic",
    
    # Security endpoints
    "/v1/security/events": "security.analytics",
    "/v1/security/threat-hunting": "security.analytics",
    "/v1/security/sigma-rules": "security.analytics",
    "/v1/security/dashboard": "security.analytics",
    
    # Alert endpoints
    "/v1/alerts/rules": "alerts.management",
    "/v1/alerts/events": "alerts.management",
    "/v1/alerts/notifications": "alerts.management",
    
    # Storage endpoints
    "/v1/storage/export": "storage.retrieval",
    "/v1/storage/download": "storage.retrieval",
}

FEATURE_BASE_COSTS = {
    "ingestion.basic": 0.0001,      # $0.10 per 1M events
    "queries.advanced": 0.00005,    # $0.05 per 1K queries
    "queries.basic": 0.00001,       # $0.01 per 1K queries
    "security.analytics": 0.0005,   # $0.50 per 1K security queries
    "alerts.management": 0.0002,    # $0.20 per 1K alert operations
    "storage.retrieval": 0.00002,   # $0.02 per GB (calculated separately)
}

def map_endpoint_to_feature(endpoint: str) -> str:
    """Map API endpoint to billing feature"""
    # Exact match first
    if endpoint in BILLING_FEATURE_MAP:
        return BILLING_FEATURE_MAP[endpoint]
    
    # Pattern matching for dynamic endpoints
    if endpoint.startswith("/v1/security/"):
        return "security.analytics"
    elif endpoint.startswith("/v1/alerts/"):
        return "alerts.management"
    elif endpoint.startswith("/v1/query/"):
        return "queries.advanced"
    elif endpoint.startswith("/v1/logs"):
        return "queries.basic"
    elif endpoint.startswith("/v1/ingestion/"):
        return "ingestion.basic"
    elif endpoint.startswith("/v1/storage/"):
        return "storage.retrieval"
    else:
        return "platform.general"

def calculate_request_cost(endpoint: str, status_code: int, response_size: int = 0) -> float:
    """Calculate cost based on endpoint, status, and response size"""
    billing_feature = map_endpoint_to_feature(endpoint)
    base_cost = FEATURE_BASE_COSTS.get(billing_feature, 0.0001)
    
    # Apply billing policy for failed requests
    if 500 <= status_code < 600:
        return 0.0  # No charge for server errors
    elif status_code in [401, 403]:
        return base_cost * 0.1  # Minimal charge for auth processing
    elif 400 <= status_code < 500:
        return base_cost * 0.5  # Partial charge for client errors
    else:
        # Full charge for successful requests
        # For storage retrieval, factor in response size
        if billing_feature == "storage.retrieval" and response_size > 0:
            gb_retrieved = response_size / (1024 * 1024 * 1024)
            return base_cost * max(1, gb_retrieved * 1000)  # Scale by GB
        return base_cost

# =================================================================
# PERMISSION SYSTEM
# =================================================================

ROLE_PERMISSIONS = {
    # Platform Admin Roles
    UserRole.SUPER_ADMIN: [
        "platform:*:*", "tenants:*:*", "users:*:*", 
        "billing:*:*", "system:*:*", "audit:*:*"
    ],
    UserRole.ADMIN: [
        "tenants:read,write,create:platform", "usage:read:platform",
        "billing:read,generate:platform", "users:read:platform"
    ],
    UserRole.SUPPORT_ADMIN: [
        "support:*:platform", "users:read,write:platform",
        "tenants:read:platform", "audit:read:platform"
    ],
    UserRole.BILLING_ADMIN: [
        "billing:*:platform", "usage:read:platform",
        "reports:generate:platform", "tenants:read:platform"
    ],
    
    # Customer User Roles
    UserRole.TENANT_ADMIN: [
        "logs:*:tenant", "alerts:*:tenant", "dashboards:*:tenant",
        "security:*:tenant", "users:*:tenant", "settings:*:tenant"
    ],
    UserRole.SECURITY_ANALYST: [
        "security:*:tenant", "logs:read,search:tenant",
        "alerts:read,investigate:tenant", "compliance:read:tenant",
        "threat_hunting:*:tenant"
    ],
    UserRole.DEVOPS_ENGINEER: [
        "logs:read,search:tenant", "alerts:*:tenant",
        "dashboards:*:tenant", "observability:*:tenant",
        "integrations:*:tenant"
    ],
    UserRole.COMPLIANCE_OFFICER: [
        "compliance:*:tenant", "audit:read:tenant",
        "reports:generate:tenant", "legal_hold:*:tenant",
        "logs:read:tenant"
    ],
    UserRole.VIEWER: [
        "logs:read:tenant", "dashboards:read:tenant",
        "alerts:read:own", "reports:read:tenant"
    ]
}

def get_endpoint_permission(path: str, method: str) -> str:
    """Get required permission for endpoint"""
    # Normalize method
    method = method.upper()
    
    # Map endpoints to permissions
    if path.startswith("/v1/admin/"):
        return "platform:admin:platform"
    elif path.startswith("/v1/users"):
        if method in ["POST", "PUT", "DELETE"]:
            return "users:write:tenant"
        return "users:read:tenant"
    elif path.startswith("/v1/security/"):
        if method in ["POST", "PUT", "DELETE"]:
            return "security:write:tenant"
        return "security:read:tenant"
    elif path.startswith("/v1/logs"):
        if method in ["POST", "PUT", "DELETE"]:
            return "logs:write:tenant"
        return "logs:read:tenant"
    elif path.startswith("/v1/alerts/"):
        if method in ["POST", "PUT", "DELETE"]:
            return "alerts:write:tenant"
        return "alerts:read:tenant"
    elif path.startswith("/v1/dashboards"):
        if method in ["POST", "PUT", "DELETE"]:
            return "dashboards:write:tenant"
        return "dashboards:read:tenant"
    elif path.startswith("/v1/billing/"):
        return "billing:read:platform"
    elif path.startswith("/v1/usage/"):
        return "usage:read:tenant"
    else:
        return "platform:general:tenant"

def check_permission(user_roles: List[Dict[str, Any]], required_permission: str, tenant_id: str) -> bool:
    """Check if user has required permission for tenant"""
    resource, action, scope = required_permission.split(":")
    
    for role_assignment in user_roles:
        if role_assignment["tenant_id"] != tenant_id and role_assignment["tenant_id"] != "platform":
            continue
            
        role = UserRole(role_assignment["role"])
        role_permissions = ROLE_PERMISSIONS.get(role, [])
        
        for permission in role_permissions:
            perm_resource, perm_action, perm_scope = permission.split(":")
            
            # Check resource match
            if perm_resource != "*" and perm_resource != resource:
                continue
                
            # Check action match (supports comma-separated actions)
            if perm_action != "*":
                allowed_actions = perm_action.split(",")
                if action not in allowed_actions:
                    continue
            
            # Check scope match
            if perm_scope == "*":
                return True
            elif perm_scope == "platform" and role_assignment["tenant_id"] == "platform":
                return True
            elif perm_scope == "tenant" and role_assignment["tenant_id"] == tenant_id:
                return True
    
    return False

# =================================================================
# USER SERVICE UTILITIES
# =================================================================

class UserService:
    """Core user management service"""
    
    def __init__(self):
        self.users_cache = {}  # Simple in-memory cache (use Redis in production)
        self.sessions_cache = {}
    
    async def create_user(self, user_data: Dict[str, Any]) -> User:
        """Create new user with hashed password"""
        # Hash password
        password_hash = hash_password(user_data["password"])
        
        user = User(
            email=user_data["email"],
            name=user_data["name"],
            password_hash=password_hash,
            status=user_data.get("status", UserStatus.PENDING)
        )
        
        # TODO: Save to database
        self.users_cache[user.id] = user
        
        logger.info("User created", user_id=user.id, email=user.email)
        return user
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address"""
        # TODO: Query database
        for user in self.users_cache.values():
            if user.email.lower() == email.lower():
                return user
        return None
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        # TODO: Query database
        return self.users_cache.get(user_id)
    
    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user credentials"""
        user = await self.get_user_by_email(email)
        if not user or not user.password_hash:
            return None
            
        if not verify_password(password, user.password_hash):
            logger.warning("Authentication failed", email=email)
            return None
            
        if user.status != UserStatus.ACTIVE:
            logger.warning("Inactive user login attempt", email=email, status=user.status)
            return None
            
        # Update last login
        user.last_login_at = datetime.utcnow()
        # TODO: Update in database
        
        logger.info("User authenticated", user_id=user.id, email=email)
        return user
    
    async def create_session(self, user: User, ip_address: str, user_agent: str) -> Dict[str, Any]:
        """Create new user session"""
        session_data = generate_jwt_token(user.id)
        
        session = UserSession(
            user_id=user.id,
            session_token=session_data["access_token"],
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=session_data["expires_at"]
        )
        
        # TODO: Save session to database
        self.sessions_cache[session.session_token] = session
        
        logger.info("Session created", user_id=user.id, session_id=session.id)
        return session_data
    
    async def validate_session(self, token: str) -> Optional[User]:
        """Validate session token and return user"""
        try:
            payload = decode_jwt_token(token)
            user_id = payload["user_id"]
            
            # Check session exists and is active
            session = self.sessions_cache.get(token)
            if session and session.status == SessionStatus.ACTIVE:
                # Update last activity
                session.last_activity = datetime.utcnow()
                
                user = await self.get_user_by_id(user_id)
                if user and user.status == UserStatus.ACTIVE:
                    return user
            
            return None
        except Exception:
            return None
    
    async def revoke_session(self, token: str):
        """Revoke user session"""
        session = self.sessions_cache.get(token)
        if session:
            session.status = SessionStatus.REVOKED
            logger.info("Session revoked", session_id=session.id)
    
    async def get_user_tenant_roles(self, user_id: str, tenant_id: str) -> List[Dict[str, Any]]:
        """Get user's roles for specific tenant"""
        # TODO: Query database for user_tenant_roles
        # For now, return mock data
        return [
            {
                "user_id": user_id,
                "tenant_id": tenant_id, 
                "role": "tenant_admin",
                "status": "active",
                "granted_at": datetime.utcnow()
            }
        ]

# Global user service instance
user_service = UserService()

# =================================================================
# AUTHENTICATION MIDDLEWARE
# =================================================================

class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Authentication and authorization middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.user_service = user_service
        
    async def dispatch(self, request: Request, call_next):
        """Process authentication and authorization"""
        start_time = time.time()
        
        # Skip authentication for public endpoints
        if self._is_public_endpoint(request.url.path):
            return await call_next(request)
        
        try:
            # 1. Extract authentication
            auth_context = await self._extract_auth(request)
            
            # 2. Validate user exists and is active
            user = await self._validate_user(auth_context)
            
            # 3. Extract requested tenant from X-Customer-ID header
            tenant_id = request.headers.get("X-Customer-ID")
            if not tenant_id and not request.url.path.startswith("/v1/auth/"):
                raise HTTPException(400, "X-Customer-ID header required")
            
            # 4. Verify user has access to requested tenant
            user_roles = []
            if tenant_id:
                user_roles = await self.user_service.get_user_tenant_roles(user.id, tenant_id)
                if not user_roles:
                    raise HTTPException(403, f"No access to tenant: {tenant_id}")
            
            # 5. Check permissions for requested endpoint
            if tenant_id:
                required_permission = get_endpoint_permission(request.url.path, request.method)
                if not check_permission(user_roles, required_permission, tenant_id):
                    raise HTTPException(403, f"Insufficient permissions for {request.url.path}")
            
            # 6. Add user context to request
            request.state.user = user
            request.state.tenant_id = tenant_id
            request.state.roles = user_roles
            
            # 7. Process request
            response = await call_next(request)
            
            # 8. Track API usage asynchronously (zero latency impact)
            if tenant_id and tenant_id != "platform":
                asyncio.create_task(
                    self._track_api_usage(request, response, user, tenant_id, start_time)
                )
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Authentication middleware error", error=str(e))
            raise HTTPException(500, "Authentication system error")
    
    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public (no auth required)"""
        public_endpoints = [
            "/",
            "/health",
            "/docs",
            "/openapi.json",
            "/v1/auth/login",
            "/v1/auth/setup/init",
            "/v1/auth/setup",
            "/v1/auth/accept-invite",
            "/v1/auth/password/reset",
            "/v1/auth/password/reset-confirm"
        ]
        return any(path.startswith(endpoint) for endpoint in public_endpoints)
    
    async def _extract_auth(self, request: Request) -> Dict[str, Any]:
        """Extract authentication context from request"""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(401, "Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        return {"token": token, "type": "bearer"}
    
    async def _validate_user(self, auth_context: Dict[str, Any]) -> User:
        """Validate user from authentication context"""
        token = auth_context["token"]
        user = await self.user_service.validate_session(token)
        
        if not user:
            raise HTTPException(401, "Invalid or expired session")
        
        return user
    
    async def _track_api_usage(self, request: Request, response, user: User, 
                              tenant_id: str, start_time: float):
        """Track API usage for billing (async)"""
        try:
            processing_time = int((time.time() - start_time) * 1000)
            
            # Get response size
            response_size = 0
            if hasattr(response, "body"):
                response_size = len(response.body)
            elif hasattr(response, "headers"):
                content_length = response.headers.get("content-length")
                if content_length:
                    response_size = int(content_length)
            
            usage_data = {
                "tenant_id": tenant_id,
                "user_id": user.id,
                "endpoint": request.url.path,
                "method": request.method,
                "status_code": getattr(response, "status_code", 200),
                "processing_time_ms": processing_time,
                "response_size_bytes": response_size,
                "ip_address": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", ""),
                "request_timestamp": datetime.utcnow(),
                "billing_feature": map_endpoint_to_feature(request.url.path),
                "cost_credits": calculate_request_cost(
                    request.url.path, 
                    getattr(response, "status_code", 200),
                    response_size
                )
            }
            
            await usage_buffer.add_usage(usage_data)
            
        except Exception as e:
            logger.error("Usage tracking failed", error=str(e))
            # Don't fail the request for usage tracking errors

# =================================================================
# DEPENDENCY INJECTION
# =================================================================

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current authenticated user"""
    user = await user_service.validate_session(credentials.credentials)
    if not user:
        raise HTTPException(401, "Invalid or expired session")
    return user

async def get_current_tenant_id(request: Request) -> str:
    """Get current tenant ID from request"""
    tenant_id = request.headers.get("X-Customer-ID")
    if not tenant_id:
        raise HTTPException(400, "X-Customer-ID header required")
    return tenant_id

async def require_platform_admin(user: User = Depends(get_current_user), 
                                 request: Request = None) -> User:
    """Require platform admin permissions"""
    if not hasattr(request.state, "roles"):
        raise HTTPException(403, "No role information available")
    
    platform_roles = [r for r in request.state.roles if r["tenant_id"] == "platform"]
    if not platform_roles:
        raise HTTPException(403, "Platform admin access required")
    
    return user

async def require_tenant_admin(user: User = Depends(get_current_user),
                              tenant_id: str = Depends(get_current_tenant_id),
                              request: Request = None) -> User:
    """Require tenant admin permissions"""
    if not hasattr(request.state, "roles"):
        raise HTTPException(403, "No role information available")
    
    tenant_roles = [r for r in request.state.roles if r["tenant_id"] == tenant_id]
    admin_roles = [r for r in tenant_roles if r["role"] in ["tenant_admin"]]
    
    if not admin_roles:
        raise HTTPException(403, f"Tenant admin access required for {tenant_id}")
    
    return user

# =================================================================
# SETUP TOKEN MANAGEMENT
# =================================================================

class SetupTokenManager:
    """Manages initial platform setup tokens"""
    
    def __init__(self):
        self.setup_tokens = {}  # In-memory storage (use Redis in production)
    
    def generate_setup_token(self) -> Dict[str, Any]:
        """Generate initial setup token"""
        token = generate_secure_token(32)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        self.setup_tokens[token] = {
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
            "used": False
        }
        
        logger.info("Setup token generated", expires_at=expires_at)
        
        return {
            "setup_token": token,
            "expires_at": expires_at
        }
    
    def validate_setup_token(self, token: str) -> bool:
        """Validate and consume setup token"""
        token_data = self.setup_tokens.get(token)
        if not token_data:
            return False
        
        if token_data["used"]:
            return False
        
        if datetime.utcnow() > token_data["expires_at"]:
            return False
        
        # Mark token as used
        token_data["used"] = True
        logger.info("Setup token consumed", token=token[:8] + "...")
        
        return True
    
    def has_setup_completed(self) -> bool:
        """Check if initial setup has been completed"""
        # TODO: Check if any super_admin users exist
        return any(token_data["used"] for token_data in self.setup_tokens.values())

# Global setup token manager
setup_token_manager = SetupTokenManager()

# =================================================================
# INVITATION SYSTEM
# =================================================================

class InvitationManager:
    """Manages user invitations"""
    
    def __init__(self):
        self.invitations = {}  # In-memory storage (use Redis in production)
    
    def create_invitation(self, email: str, tenant_id: str, role: UserRole, 
                         invited_by: str) -> Dict[str, Any]:
        """Create user invitation"""
        token = generate_secure_token(32)
        expires_at = datetime.utcnow() + timedelta(days=7)  # 7 day expiry
        
        self.invitations[token] = {
            "email": email.lower(),
            "tenant_id": tenant_id,
            "role": role,
            "invited_by": invited_by,
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
            "accepted": False
        }
        
        logger.info("Invitation created", email=email, tenant_id=tenant_id, role=role)
        
        return {
            "invitation_token": token,
            "invitation_expires": expires_at,
            "invited_email": email
        }
    
    def validate_invitation(self, token: str, email: str) -> Optional[Dict[str, Any]]:
        """Validate invitation token and email match"""
        invitation = self.invitations.get(token)
        if not invitation:
            return None
        
        if invitation["accepted"]:
            return None
        
        if datetime.utcnow() > invitation["expires_at"]:
            return None
        
        if invitation["email"] != email.lower():
            return None
        
        return invitation
    
    def accept_invitation(self, token: str) -> Dict[str, Any]:
        """Mark invitation as accepted and return details"""
        invitation = self.invitations.get(token)
        if invitation:
            invitation["accepted"] = True
            invitation["accepted_at"] = datetime.utcnow()
        return invitation

# Global invitation manager
invitation_manager = InvitationManager()

# =================================================================
# MIDDLEWARE SETUP
# =================================================================

def setup_auth_middleware(app):
    """Setup authentication middleware on FastAPI app"""
    app.add_middleware(AuthenticationMiddleware)
    logger.info("Authentication middleware configured")