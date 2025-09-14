"""
M8 Unified Authentication & Authorization Middleware
Combined authn/authz layer providing authentication, authorization, feature access, and usage tracking
"""

import asyncio
import time
import secrets
import bcrypt
import jwt
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog
import clickhouse_connect
import uuid

from models import (
    User, UserSession, UserTenantRole, APIUsageAudit,
    UserRole, UserStatus, SessionStatus
)
from subscription_service import subscription_service
from database_layer import DatabaseLayer, DatabaseError, SecurityError

logger = structlog.get_logger()

# Authentication configuration from environment variables
JWT_SECRET = os.getenv("JWT_SECRET", "logforge-jwt-secret-key-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
SESSION_EXPIRY_HOURS = int(os.getenv("SESSION_EXPIRY_HOURS", "8"))

# ClickHouse configuration from environment variables
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "logforge")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "logforge123")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "logforge")

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
        """Insert usage records to database using DatabaseLayer"""
        try:
            # Initialize DatabaseLayer for usage tracking
            service_key = os.getenv("USER_SERVICE_KEY", "user-service-key-dev")
            db = DatabaseLayer("UserService", service_key)
            
            # Use batch insert for usage tracking
            result = await db.batch_insert_usage(usage_records)
            logger.info("Usage batch inserted to database", records=result)
            
        except Exception as e:
            logger.error("Failed to insert usage batch to database", error=str(e), records=len(usage_records))
            # Continue without failing - usage tracking should not block requests

# Global usage buffer instance
usage_buffer = UsageBuffer()

# =================================================================
# AUTHENTICATION UTILITIES
# =================================================================

def validate_password_strength(password: str) -> None:
    """
    Validate password meets security requirements
    
    Requirements:
    - Minimum 12 characters
    - At least one uppercase letter
    - At least one lowercase letter  
    - At least one number
    - At least one special character
    - Not a common weak password
    
    Raises:
        ValueError: If password doesn't meet requirements
    """
    if not password:
        raise ValueError("Password is required")
    
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters long")
    
    # Check character type requirements
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?~`" for c in password)
    
    if not has_upper:
        raise ValueError("Password must contain at least one uppercase letter")
    if not has_lower:
        raise ValueError("Password must contain at least one lowercase letter")
    if not has_digit:
        raise ValueError("Password must contain at least one number")
    if not has_special:
        raise ValueError("Password must contain at least one special character (!@#$%^&* etc.)")
    
    # Check against common weak passwords
    weak_passwords = {
        'password123!', 'password123@', 'password123#', 'password123$',
        '123456789012', 'qwertyuiopas', 'asdfghjklzxc', 'adminpassword',
        'welcome123!', 'letmein123!', 'changeme123!', '1234567890!@',
        'p@ssw0rd123', 'P@ssw0rd123', 'admin123456!', 'user123456!'
    }
    
    if password.lower() in {pwd.lower() for pwd in weak_passwords}:
        raise ValueError("Password is too common. Please choose a more unique password")

def hash_password(password: str) -> str:
    """
    Hash password using bcrypt with 12 rounds
    Validates password strength before hashing
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
        
    Raises:
        ValueError: If password doesn't meet security requirements
    """
    # Validate password strength first
    validate_password_strength(password)
    
    # Hash the password
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_jwt_token(user_id: str, expires_in_hours: int = SESSION_EXPIRY_HOURS) -> Dict[str, Any]:
    """Generate JWT token for user session"""
    import time
    
    now_timestamp = time.time()
    expires_timestamp = now_timestamp + (expires_in_hours * 3600)
    expires_dt = datetime.utcfromtimestamp(expires_timestamp)
    
    payload = {
        "user_id": user_id,
        "iat": now_timestamp,
        "exp": expires_timestamp,
        "type": "access_token"
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {
        "access_token": token,
        "expires_at": expires_dt
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
    "/v1/ingest/logs": "ingestion.basic",
    "/v1/ingest/syslog": "ingestion.basic", 
    "/v1/ingest/otlp": "ingestion.basic",
    "/v1/ingest/cef": "ingestion.basic",
    "/v1/ingest/nginx": "ingestion.basic",
    "/v1/ingest/text": "ingestion.basic",
    "/v1/ingest/logs/batch": "ingestion.basic",
    "/v1/ingest": "ingestion.basic",
    
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
    "/v1/storage/health": "storage.retrieval",
    "/v1/storage/cleanup": "storage.retrieval",
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
    elif endpoint.startswith("/v1/ingest"):
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
        "*:*:*", "platform:*:*", "tenants:*:*", "users:*:*", 
        "billing:*:*", "system:*:*", "audit:*:*", "storage:*:*"
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
        "security:*:tenant", "users:*:tenant", "settings:*:tenant",
        "storage:*:tenant", "queries:*:tenant", "ai:*:tenant", "enterprise:*:tenant",
        "observability:*:tenant", "roles:*:tenant"
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
    method = method.upper()
    
    # Map endpoints to permissions
    if path.startswith("/v1/admin/"):
        return "platform:admin:platform"
    elif path.startswith("/v1/auth/"):
        # Auth endpoints are user-level operations, no tenant-specific permissions needed
        return "auth:user:user"
    elif path.startswith("/v1/users"):
        if method in ["POST", "PUT", "DELETE"]:
            return "users:write:tenant"
        return "users:read:tenant"
    elif path.startswith("/v1/security/"):
        if method in ["POST", "PUT", "DELETE"]:
            return "security:write:tenant"
        return "security:read:tenant"
    elif path.startswith("/v1/query/"):
        if method in ["POST", "PUT", "DELETE"]:
            return "queries:write:tenant"
        return "queries:read:tenant"
    elif path.startswith("/v1/logs") or path.startswith("/v1/ingest"):
        if method in ["POST", "PUT", "DELETE"]:
            return "logs:write:tenant"
        return "logs:read:tenant"
    elif path.startswith("/v1/alerts"):
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
    elif path.startswith("/v1/storage/"):
        if method in ["POST", "PUT", "DELETE"]:
            return "storage:write:tenant"
        return "storage:read:tenant"
    elif path.startswith("/v1/export"):
        if method in ["POST", "PUT", "DELETE"]:
            return "logs:write:tenant"  # Export is a read operation that generates output
        return "logs:read:tenant"
    elif path.startswith("/v1/ai"):
        if method in ["POST", "PUT", "DELETE"]:
            return "ai:write:tenant"
        return "ai:read:tenant"
    elif path.startswith("/v1/enterprise"):
        if method in ["POST", "PUT", "DELETE"]:
            return "enterprise:write:tenant"
        return "enterprise:read:tenant"
    elif path.startswith("/v1/observability"):
        if method in ["POST", "PUT", "DELETE"]:
            return "observability:write:tenant"
        return "observability:read:tenant"
    elif path.startswith("/v1/roles") or path.startswith("/v1/permissions"):
        if method in ["POST", "PUT", "DELETE"]:
            return "roles:write:tenant"
        return "roles:read:tenant"
    elif "/roles" in path or path.startswith("/v1/tenants") and "/users" in path:
        if method in ["POST", "PUT", "DELETE"]:
            return "roles:write:tenant"
        return "roles:read:tenant"
    elif path.startswith("/v1/check-permission") or path.startswith("/v1/validate-access"):
        return "roles:read:tenant"
    else:
        return "platform:general:tenant"

def check_permission(user_roles: List[Dict[str, Any]], required_permission: str, tenant_id: str) -> bool:
    """Check if user has required permission for tenant (supports tenant-less platform admins)"""
    resource, action, scope = required_permission.split(":")
    
    for role_assignment in user_roles:
        # Platform admins (tenant_id = "platform") have platform-wide access
        is_platform_admin = role_assignment["tenant_id"] == "platform"
        is_tenant_match = role_assignment["tenant_id"] == tenant_id
        
        # Skip if not platform admin and not matching tenant
        if not is_platform_admin and not is_tenant_match:
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
            elif perm_scope == "platform" and is_platform_admin:
                return True
            elif perm_scope == "tenant" and is_tenant_match:
                return True
    
    return False

# =================================================================
# USER SERVICE (IMPORT FROM PROPER SERVICE LAYER)
# =================================================================

# Import UserService from proper service layer
from services.user_service import UserService
user_service = UserService()

# =================================================================
# SETUP TOKEN MANAGEMENT
# =================================================================

class SetupTokenManager:
    """Manages initial platform setup tokens"""
    
    def __init__(self):
        # Use database storage instead of memory
        from database_layer import DatabaseLayer
        self.db = DatabaseLayer("PlatformSetup", "platform-setup-key")
        # Initialize in-memory storage for now (TODO: move to database)
        self.setup_tokens = {}
    
    def generate_setup_token(self) -> Dict[str, Any]:
        """Generate initial setup token"""
        token = generate_secure_token(32)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        # Store in memory for now (TODO: Store in database instead)
        self.setup_tokens[token] = {
            "token": token,
            "expires_at": expires_at,
            "used": False,
            "created_at": datetime.utcnow()
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
        # TODO: Check if any super_admin users exist in database
        # For now, check if any tokens have been used
        return any(token_data["used"] for token_data in self.setup_tokens.values())

# Global setup token manager (lazy initialization)
setup_token_manager = None

def get_setup_token_manager():
    """Get setup token manager with lazy initialization"""
    global setup_token_manager
    if setup_token_manager is None:
        try:
            setup_token_manager = SetupTokenManager()
        except Exception as e:
            logger.warning("Failed to initialize SetupTokenManager", error=str(e))
            # Return a dummy manager for testing
            setup_token_manager = type('DummySetupTokenManager', (), {
                'is_setup_complete': lambda: True,
                'generate_setup_token': lambda: {"token": "test-token", "expires_at": "2024-01-01T00:00:00Z"},
                'validate_setup_token': lambda token: None,
                'complete_setup': lambda token, admin_data: True
            })()
    return setup_token_manager

# =================================================================
# INVITATION SYSTEM
# =================================================================

class InvitationManager:
    """Manages user invitations with database persistence"""
    
    def __init__(self):
        # Use the UserService from this module instead of importing
        self.user_service = None  # Will be set when needed
    
    async def create_invitation(self, email: str, tenant_id: str, role: UserRole, 
                               invited_by: str) -> Dict[str, Any]:
        """Create user invitation using database storage"""
        # Use the global user_service instance
        return await user_service.create_invitation(email, tenant_id, role, invited_by)
    
    async def validate_invitation(self, token: str, email: str) -> Optional[Dict[str, Any]]:
        """Validate invitation token and email match using database"""
        # Use the global user_service instance
        return await user_service.validate_invitation(token, email)
    
    async def accept_invitation(self, token: str, invitation_id: str) -> bool:
        """Mark invitation as accepted using database"""
        # Use the global user_service instance
        return await user_service.accept_invitation(invitation_id)

# Global invitation manager
invitation_manager = InvitationManager()

# =================================================================
# UNIFIED AUTHENTICATION & AUTHORIZATION MIDDLEWARE
# =================================================================

class UnifiedAuthMiddleware(BaseHTTPMiddleware):
    """Unified Authentication & Authorization Middleware
    
    Handles:
    1. Authentication (JWT token validation)
    2. Authorization (role-based permissions)
    3. Feature Access (subscription validation)
    4. Usage Tracking (billing and audit)
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.user_service = user_service
        self.subscription_service = subscription_service
        
        # Public endpoints (no authentication required)
        self.public_endpoints = [
            "/",
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/v1/auth/login",
            "/v1/auth/setup/init", 
            "/v1/auth/setup",
            "/v1/auth/accept-invite",
            "/v1/auth/password/reset",
            "/v1/auth/password/reset-confirm"
        ]
        
        # Admin endpoints (bypass feature validation)
        self.admin_endpoints = [
            "/v1/admin/",
            "/v1/test-runner/"
        ]
    
    async def dispatch(self, request: Request, call_next):
        """Process authentication, authorization, and feature access"""
        start_time = time.time()
        
        # Allow CORS preflight requests to pass through without authentication
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Skip authentication for public endpoints
        if self._is_public_endpoint(request.url.path):
            return await call_next(request)
        
        # Skip feature validation for admin endpoints but still require auth
        is_admin_endpoint = self._is_admin_endpoint(request.url.path)
        
        try:
            # Step 1: Authentication - Extract and validate JWT token
            auth_context = await self._extract_authentication(request)
            user = await self._validate_user_session(auth_context)
            
            # Step 2: Tenant Context - Extract tenant ID
            tenant_id = request.headers.get("X-Customer-ID")
            if not tenant_id and not request.url.path.startswith("/v1/auth/"):
                raise HTTPException(400, "X-Customer-ID header required")
            
            # Step 3: Authorization - Verify user has access to tenant
            user_roles = []
            if tenant_id:
                user_roles = await self.user_service.get_user_tenant_roles(user.id, tenant_id)
                if not user_roles:
                    raise HTTPException(403, f"No access to tenant: {tenant_id}")
            
            # Step 4: Permission Check - Verify endpoint permissions
            # Skip permission checks for auth endpoints (they are user-level operations)
            if tenant_id and not request.url.path.startswith("/v1/auth/"):
                required_permission = get_endpoint_permission(request.url.path, request.method)
                if not check_permission(user_roles, required_permission, tenant_id):
                    raise HTTPException(403, f"Insufficient permissions for {request.url.path}")
            
            # Step 5: Feature Access - Check subscription (skip for admin endpoints)
            if not is_admin_endpoint and tenant_id:
                feature_access = await self._validate_feature_access(tenant_id, request.url.path)
                if not feature_access["access_granted"]:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": feature_access["error_code"],
                            "message": feature_access["reason"],
                            "required_feature": feature_access.get("required_feature"),
                            "current_subscription": feature_access.get("current_features", []),
                            "upgrade_url": f"/v1/tenants/{tenant_id}/subscription/upgrade"
                        }
                    )
            
            # Step 6: Add context to request
            request.state.user = user
            request.state.tenant_id = tenant_id
            request.state.roles = user_roles
            
            # Step 7: Process request
            response = await call_next(request)
            
            # Step 8: Usage Tracking - Track API usage asynchronously
            if tenant_id and tenant_id != "platform":
                asyncio.create_task(
                    self._track_api_usage(request, response, user, tenant_id, start_time)
                )
            
            return response
            
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"error": e.detail}
            )
        except Exception as e:
            logger.error("Authentication/Authorization middleware error", error=str(e))
            return JSONResponse(
                status_code=500, 
                content={"error": "Authentication system error"}
            )
    
    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public (no auth required)"""
        # Strip query parameters from path before matching
        clean_path = path.split('?')[0]
        return clean_path in self.public_endpoints
    
    def _is_admin_endpoint(self, path: str) -> bool:
        """Check if endpoint is admin (bypasses feature validation)"""
        return any(path.startswith(endpoint) for endpoint in self.admin_endpoints)
    
    async def _extract_authentication(self, request: Request) -> Dict[str, Any]:
        """Extract authentication context from request"""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(401, "Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        return {"token": token, "type": "bearer"}
    
    async def _validate_user_session(self, auth_context: Dict[str, Any]) -> User:
        """Validate user session from token"""
        token = auth_context["token"]
        user = await self.user_service.validate_session(token)
        
        if not user:
            raise HTTPException(401, "Invalid or expired session")
        
        return user
    
    async def _validate_feature_access(self, tenant_id: str, endpoint: str) -> Dict[str, Any]:
        """Validate feature access based on subscription"""
        try:
            return await self.subscription_service.validate_feature_access(tenant_id, endpoint)
        except Exception as e:
            logger.error("Feature validation error", error=str(e))
            # On feature validation error, allow access but log
            return {
                "access_granted": True,
                "feature": "fallback",
                "reason": "Feature validation error - access granted"
            }
    
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
                ),
                "customer_id": tenant_id  # customer_id is the same as tenant_id in our architecture
            }
            
            await usage_buffer.add_usage(usage_data)
            
        except Exception as e:
            logger.error("Usage tracking failed", error=str(e))

# =================================================================
# DEPENDENCY INJECTION
# =================================================================

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends

security = HTTPBearer()

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
    """Require platform admin permissions (tenant-less platform admins)"""
    if not hasattr(request.state, "roles"):
        raise HTTPException(403, "No role information available")
    
    # Platform admins have tenant_id = "platform" (super-tenant)
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

# Global instances (using lazy initialization)
invitation_manager = InvitationManager()
setup_token_manager = get_setup_token_manager()

def setup_unified_auth_middleware(app):
    """Setup unified authentication and authorization middleware"""
    app.add_middleware(UnifiedAuthMiddleware)
    logger.info("Unified Authentication & Authorization middleware configured")