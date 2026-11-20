"""
M8 Unified Authentication & Authorization Middleware
Combined authn/authz layer providing authentication, authorization, feature access, and usage tracking
"""

import asyncio
import time
import hashlib
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
# ENH-008/ENH-010: `subscription_service` is resolved lazily inside
# UnifiedAuthMiddleware.__init__ rather than imported at module scope.
# Importing the singleton here opened a ClickHouse connection during
# `import authn_authz_middleware`, which made the whole authentication layer
# un-importable -- and untestable -- without live infrastructure.
from subscription_service import get_subscription_service
from database_layer import DatabaseLayer, DatabaseError, SecurityError

logger = structlog.get_logger()

# Authentication configuration from environment variables.
#
# ENH-005: the JWT signing key previously fell back to a literal published in
# this repository, so any deployment that forgot to set JWT_SECRET would accept
# tokens forged by anyone who had read the source. The development default is
# retained ONLY for local work; `security_config.validate_security_configuration()`
# runs at startup and refuses to boot any non-development environment that is
# still using it. See apps/api/security_config.py.
JWT_SECRET = os.getenv("JWT_SECRET", "logforge-jwt-secret-key-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
SESSION_EXPIRY_HOURS = int(os.getenv("SESSION_EXPIRY_HOURS", "8"))

# ClickHouse configuration (single source: app_config.clickhouse_settings)
from app_config import clickhouse_settings as _clickhouse_settings

_CH = _clickhouse_settings()
CLICKHOUSE_HOST = _CH["host"]
CLICKHOUSE_PORT = _CH["port"]
CLICKHOUSE_USER = _CH["username"]
CLICKHOUSE_PASSWORD = _CH["password"]
CLICKHOUSE_DATABASE = _CH["database"]

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
        try:
            # Debug: Create JSON-serializable copy for validation (datetime objects -> ISO strings)
            import json
            json_test_data = {}
            for key, value in usage_data.items():
                if isinstance(value, datetime):
                    json_test_data[key] = value.isoformat()
                else:
                    json_test_data[key] = value
        except (TypeError, ValueError) as e:
            # Try to sanitize the data (keep original datetime objects for database)
            for key, value in usage_data.items():
                if isinstance(value, float):
                    if value != value or abs(value) == float('inf'):
                        usage_data[key] = 0.0

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
            logger.debug(f"Usage batch flushed", count=len(self.buffer))
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
            logger.debug("Usage batch inserted to database", records=result)

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

def generate_jwt_token(user_id: str, tenant_id: str, user_role: str, expires_in_hours: int = SESSION_EXPIRY_HOURS) -> Dict[str, Any]:
    """Generate JWT token for user session with tenant context and role"""
    import time

    now_timestamp = time.time()
    expires_timestamp = now_timestamp + (expires_in_hours * 3600)
    expires_dt = datetime.utcfromtimestamp(expires_timestamp)

    payload = {
        "user_id": user_id,
        "tenant_id": tenant_id,  # Include tenant_id in JWT payload
        "user_role": user_role,  # Include user's primary role in JWT payload
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
            # Cap response_size to prevent overflow (max 10GB)
            capped_response_size = min(response_size, 10 * 1024 * 1024 * 1024)
            gb_retrieved = capped_response_size / (1024 * 1024 * 1024)
            multiplier = max(1, gb_retrieved * 1000)
            # Cap the multiplier to prevent JSON overflow (max 1M multiplier)
            multiplier = min(multiplier, 1000000)
            cost = base_cost * multiplier
            # Ensure cost is JSON-safe and within reasonable bounds
            if cost != cost or abs(cost) == float('inf') or cost > 1000000:
                return 1.0  # Default to $1 for extreme cases
            return cost
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
        "observability:*:tenant", "roles:*:tenant", "usage:*:tenant", "billing:read:tenant",
        "costs:*:tenant", "analytics:read:tenant", "tenants:read,write:tenant"
    ],
    UserRole.SECURITY_ANALYST: [
        "security:*:tenant", "logs:read,search:tenant", "ai:read:tenant",
        "alerts:read,investigate:tenant", "compliance:read:tenant",
        "threat_hunting:*:tenant"
    ],
    UserRole.DEVOPS_ENGINEER: [
        "logs:read,search:tenant", "alerts:*:tenant", "ai:read:tenant",
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

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


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
        if method in WRITE_METHODS:
            return "users:write:tenant"
        return "users:read:tenant"
    elif path.startswith("/v1/security/"):
        if method in WRITE_METHODS:
            return "security:write:tenant"
        return "security:read:tenant"
    elif path.startswith("/v1/query/"):
        if method in WRITE_METHODS:
            return "queries:write:tenant"
        return "queries:read:tenant"
    elif path.startswith("/v1/packs"):
        # Installing a pack writes pipelines, rules, searches and dashboards
        # at once, so it takes the tenant-admin settings permission.
        if method in WRITE_METHODS:
            return "settings:write:tenant"
        return "logs:read:tenant"
    elif path.startswith("/v1/pipelines"):
        # Ingest pipelines shape stored logs: managing them is a logs write.
        if method in WRITE_METHODS:
            return "logs:write:tenant"
        return "logs:read:tenant"
    elif path.startswith("/v1/logs") or path.startswith("/v1/ingest") or path.startswith("/v1/fields"):
        if method in WRITE_METHODS:
            return "logs:write:tenant"
        return "logs:read:tenant"
    elif path.startswith("/v1/alerts"):
        if method in WRITE_METHODS:
            return "alerts:write:tenant"
        return "alerts:read:tenant"
    elif path.startswith("/v1/dashboards"):
        if method in WRITE_METHODS:
            return "dashboards:write:tenant"
        return "dashboards:read:tenant"
    elif path.startswith("/v1/billing/"):
        return "billing:read:platform"
    elif path.startswith("/v1/usage/"):
        return "usage:read:tenant"
    elif path.startswith("/v1/costs/"):
        if method in WRITE_METHODS:
            return "costs:write:tenant"
        return "costs:read:tenant"
    elif path.startswith("/v1/analytics/"):
        if method in WRITE_METHODS:
            return "analytics:write:tenant"
        return "analytics:read:tenant"
    elif path.startswith("/v1/storage/"):
        if method in WRITE_METHODS:
            return "storage:write:tenant"
        return "storage:read:tenant"
    elif path.startswith("/v1/export"):
        if method in WRITE_METHODS:
            return "logs:write:tenant"  # Export is a read operation that generates output
        return "logs:read:tenant"
    elif path in ("/v1/ai/settings", "/v1/ai/audit"):
        # AI settings and the AI audit log are the tenant admin's.
        if method in WRITE_METHODS:
            return "settings:write:tenant"
        return "settings:read:tenant"
    elif path in ("/v1/ai/status", "/v1/ai/usage", "/v1/ai/ask", "/v1/ai/nl2query"):
        # Asking is read-only: the model's tools only read, as the person asking.
        return "ai:read:tenant"
    elif path.startswith("/v1/ai"):
        if method in WRITE_METHODS:
            return "ai:write:tenant"
        return "ai:read:tenant"
    elif path.startswith("/v1/enterprise"):
        if method in WRITE_METHODS:
            return "enterprise:write:tenant"
        return "enterprise:read:tenant"
    elif path.startswith("/v1/observability"):
        if method in WRITE_METHODS:
            return "observability:write:tenant"
        return "observability:read:tenant"
    elif path.startswith("/v1/stream/"):
        return "observability:read:tenant"  # Streaming endpoints require observability read access
    elif path.startswith("/v1/streaming/config"):
        if method in WRITE_METHODS:
            return "observability:write:tenant"  # Streaming config management requires write access
        return "observability:read:tenant"  # Reading streaming config requires read access
    elif path == "/v1/tenants" or (path.startswith("/v1/tenants") and path.count("/") == 2):
        # /v1/tenants (list all) requires platform admin
        # /v1/tenants (create) requires platform admin
        return "platform:admin:platform"
    elif path.startswith("/v1/tenants/") and path.count("/") >= 3:
        # /v1/tenants/{tenant_id}/* allows both platform admin and tenant admin
        if method in WRITE_METHODS:
            return "tenants:write:tenant"
        return "tenants:read:tenant"
    elif path.startswith("/v1/roles") or path.startswith("/v1/permissions"):
        if method in WRITE_METHODS:
            return "roles:write:tenant"
        return "roles:read:tenant"
    elif "/roles" in path or path.startswith("/v1/tenants") and "/users" in path:
        if method in WRITE_METHODS:
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

# Import UserService from proper service layer.
#
# ENH-008/ENH-010: `UserService()` opens a database connection in its
# constructor, so instantiating it here connected during
# `import authn_authz_middleware`. Built lazily instead; the PEP 562
# `__getattr__` at the bottom of this module keeps the bare `user_service` name
# working at every existing call site.
from services.user_service import UserService

_user_service_instance: Optional[UserService] = None


def get_user_service() -> UserService:
    """Get the shared UserService, constructing it on first use."""
    global _user_service_instance
    if _user_service_instance is None:
        _user_service_instance = UserService()
    return _user_service_instance

# =================================================================
# SETUP TOKEN MANAGEMENT
# =================================================================

class SetupTokenManager:
    """
    Manages initial platform setup tokens.

    Tokens are persisted in ClickHouse (`platform_setup_tokens_mt`, migration
    015) so they survive restarts and work across API replicas. Only the
    SHA-256 hash of a token is stored. A token expires after
    SETUP_TOKEN_TTL_HOURS and can be used once.

    Construction failure and setup-status errors propagate rather than
    falling back to fabricated answers. See `get_setup_token_manager()`.
    """

    TABLE = "platform_setup_tokens_mt"
    SETUP_TOKEN_TTL_HOURS = 24

    def __init__(self):
        from database_layer import DatabaseLayer
        self.db = DatabaseLayer("PlatformSetup", "platform-setup-key")

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def generate_setup_token(self) -> Dict[str, Any]:
        """Issue a setup token and store its hash with an expiry."""
        token = generate_secure_token(32)
        expires_at = datetime.utcnow() + timedelta(hours=self.SETUP_TOKEN_TTL_HOURS)

        # Timestamps are computed server-side so the expiry check below never
        # depends on the API host's clock or timezone handling.
        self.db.client.command(
            f"""
            INSERT INTO {self.TABLE} (token_hash, created_at, expires_at, used_at)
            SELECT {{token_hash:String}}, now64(3),
                   now64(3) + INTERVAL {self.SETUP_TOKEN_TTL_HOURS} HOUR, NULL
            """,
            parameters={"token_hash": self._hash(token)},
        )
        logger.debug("Setup token generated", expires_at=expires_at)

        return {
            "setup_token": token,
            "expires_at": expires_at
        }

    def validate_setup_token(self, token: str) -> bool:
        """Validate and consume a setup token (single use)."""
        if not token:
            return False
        token_hash = self._hash(token)

        result = self.db.client.query(
            f"""
            SELECT count() FROM {self.TABLE}
            WHERE token_hash = {{token_hash:String}}
              AND used_at IS NULL
              AND expires_at > now64(3)
            """,
            parameters={"token_hash": token_hash},
        )
        if not result.result_rows or result.result_rows[0][0] == 0:
            return False

        # Consume it. mutations_sync=2 waits until every replica has applied
        # the update, so a second request cannot see the token as unused.
        self.db.client.command(
            f"""
            ALTER TABLE {self.TABLE} UPDATE used_at = now64(3)
            WHERE token_hash = {{token_hash:String}} AND used_at IS NULL
            SETTINGS mutations_sync = 2
            """,
            parameters={"token_hash": token_hash},
        )
        logger.debug("Setup token consumed", token=token[:8] + "...")
        return True

    def has_setup_completed(self) -> bool:
        """Check if initial setup has been completed"""
        try:
            # Check if any super_admin users exist in the database
            query = """
                SELECT count() FROM users_mt
                WHERE customer_id = 'platform'
                AND id IN (
                    SELECT user_id FROM user_tenant_roles_mt
                    WHERE role = 'super_admin' AND status = 'active'
                )
            """
            result = self.db.client.query(query)
            super_admin_count = result.result_rows[0][0] if result.result_rows else 0

            # Setup is completed if there's at least one active super admin
            setup_completed = super_admin_count > 0
            logger.debug("Setup completion check", super_admin_count=super_admin_count, completed=setup_completed)

            return setup_completed

        except Exception as e:
            # ENH-014: previously fell back to "has any in-process token been
            # used?", which is unrelated to whether a super admin actually
            # exists. Answering this wrongly either re-opens the bootstrap
            # endpoint on a live platform or locks out a legitimate first admin,
            # so an unknown answer must be an error, not a guess.
            logger.error("Failed to check setup completion", error=str(e))
            raise

# Global setup token manager (lazy initialization)
_setup_token_manager_instance = None


def get_setup_token_manager() -> "SetupTokenManager":
    """
    Get the setup token manager, constructing it on first use.

    ENH-014: construction failure previously substituted a dummy object whose
    `generate_setup_token()` returned a HARDCODED `"test-token"` and whose
    `is_setup_complete()` always returned `True`. That is fabricated behaviour
    masking a hard failure -- and a security hazard, because a predictable
    bootstrap token is a platform-takeover primitive if it is ever honoured.

    Failure now propagates. A platform that cannot reach its database must not
    pretend it can bootstrap.
    """
    global _setup_token_manager_instance
    if _setup_token_manager_instance is None:
        _setup_token_manager_instance = SetupTokenManager()
    return _setup_token_manager_instance

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
        return await get_user_service().create_invitation(email, tenant_id, role, invited_by)

    async def validate_invitation(self, token: str, email: str) -> Optional[Dict[str, Any]]:
        """Validate invitation token and email match using database"""
        # Use the global user_service instance
        return await get_user_service().validate_invitation(token, email)

    async def accept_invitation(self, token: str, invitation_id: str) -> bool:
        """Mark invitation as accepted using database"""
        # Use the global user_service instance
        return await get_user_service().accept_invitation(invitation_id)

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
        self.user_service = get_user_service()
        # Resolved on first middleware construction (app startup), not at import.
        self.subscription_service = get_subscription_service()

        # Public endpoints (no authentication required)
        self.public_endpoints = [
            "/",
            "/health",
            # ENH-019: Prometheus scrape target. Reports no tenant-identifying
            # data; expected to be restricted at the ingress.
            "/metrics",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/v1/auth/login",
            # LF-015: the refresh endpoint authenticates via the refresh token
            # in its body — requiring a valid (unexpired) access token here
            # made refresh useless by design.
            "/v1/auth/refresh",
            "/v1/auth/setup/init",
            "/v1/auth/setup",
            "/v1/auth/accept-invite",
            "/v1/auth/password/reset",
            "/v1/auth/password/reset-confirm"
        ]

        # Admin endpoints (bypass feature validation)
        self.admin_endpoints = [
            "/v1/admin/"
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
            # Step 1: Authentication - Extract and validate JWT token or API key
            auth_context = await self._extract_authentication(request)

            user = await self._validate_user_session(auth_context, request)

            # Step 2: Tenant Context - Extract tenant ID
            # For API keys, tenant_id comes from the key; for JWT, from header
            # For SSE streams, allow customer_id from query params (EventSource can't send headers)
            if hasattr(request.state, "is_api_key_auth") and request.state.is_api_key_auth:
                # API key auth - tenant_id from service account's customer_id
                tenant_id = user.customer_id
            else:
                # JWT auth - require X-Customer-ID header (or query param for SSE streams)
                tenant_id = request.headers.get("X-Customer-ID")

                # For SSE stream endpoints, also check query params (EventSource limitation)
                if not tenant_id and request.url.path.startswith("/v1/stream/"):
                    tenant_id = request.query_params.get("customer_id")

                if not tenant_id and not request.url.path.startswith("/v1/auth/"):
                    raise HTTPException(400, "X-Customer-ID header required")

            # Step 3: Authorization - Verify user has access to tenant
            user_roles = []
            if tenant_id:
                user_roles = await self.user_service.get_user_tenant_roles(user.id, tenant_id)

                if not user_roles and tenant_id != "platform":
                    # LF-033: 'platform' is a ROLE SCOPE, not a tenant. A
                    # tenant-less platform admin (role assignment with
                    # tenant_id='platform') may access any tenant-scoped
                    # route; check_permission() already understands
                    # platform-scoped role rows.
                    platform_roles = await self.user_service.get_user_tenant_roles(
                        user.id, "platform"
                    )
                    if platform_roles:
                        user_roles = platform_roles

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
                if not feature_access.get("access_granted"):
                    return JSONResponse(
                        status_code=403,
                        content={
                            # `.get()` so a malformed denial payload yields a
                            # correct 403 rather than a KeyError -> 500.
                            "error": feature_access.get("error_code", "feature_not_available"),
                            "message": feature_access.get("reason", "Feature not available on your plan"),
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

            # Step 9: Audit Logging - Track admin activities for platform admins
            if user_roles and any(role["tenant_id"] == "platform" for role in user_roles):
                asyncio.create_task(
                    self._track_audit_activity(request, response, user, tenant_id, user_roles)
                )

            return response

        except HTTPException as e:
            logger.error("🔍 AUTH HTTP EXCEPTION", status_code=e.status_code, detail=e.detail, path=str(request.url.path))
            return JSONResponse(
                status_code=e.status_code,
                content={"error": e.detail}
            )
        except Exception as e:
            logger.error("🔍 AUTH SYSTEM ERROR: Unhandled exception in middleware",
                        error=str(e),
                        error_type=type(e).__name__,
                        path=str(request.url.path),
                        method=request.method,
                        exc_info=True)
            import traceback
            logger.error("🔍 AUTH SYSTEM ERROR: Full traceback", traceback=traceback.format_exc())
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
        """Extract authentication context from request (supports JWT and API keys)"""
        auth_header = request.headers.get("Authorization")

        # For SSE stream endpoints, also check query params (EventSource can't send headers)
        if (not auth_header or not auth_header.startswith("Bearer ")) and request.url.path.startswith("/v1/stream/"):
            token = request.query_params.get("token")
            if not token:
                raise HTTPException(401, "Missing authentication token")
        elif not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(401, "Missing or invalid Authorization header")
        else:
            token = auth_header.split(" ")[1]

        # Detect token type
        if "." in token:
            # JWT tokens have dots (header.payload.signature)
            return {"token": token, "type": "jwt"}
        elif token.startswith("lf_"):
            # API keys start with "lf_"
            return {"token": token, "type": "api_key"}
        else:
            raise HTTPException(401, "Invalid token format")

    async def _validate_user_session(self, auth_context: Dict[str, Any], request: Request) -> User:
        """Validate user session from token (supports both JWT and API keys)"""
        token = auth_context["token"]
        token_type = auth_context["type"]

        if token_type == "jwt":
            # Existing JWT flow
            user = await self.user_service.validate_session(token)
            if not user:
                raise HTTPException(401, "Invalid or expired session")
            return user

        elif token_type == "api_key":
            # NEW: API key flow with service account loading
            from services.enterprise_service import EnterpriseService
            enterprise_service = EnterpriseService()

            # Authenticate API key (global lookup - no customer_id needed)
            key_info = await enterprise_service.authenticate_api_key(token, None)

            if not key_info:
                raise HTTPException(401, "Invalid API key")

            # Load the REAL service account user from database
            service_account_id = key_info.get("service_account_id")
            if not service_account_id:
                raise HTTPException(401, "API key not linked to service account")

            user = await self.user_service.get_user_by_id(service_account_id)
            if not user:
                raise HTTPException(401, "Service account not found")

            # Mark request as API key auth (for audit logs and tenant_id extraction)
            request.state.auth_method = "api_key"
            request.state.api_key_id = key_info["key_id"]
            request.state.is_api_key_auth = True
            request.state.api_key_permissions = key_info["permissions"]
            request.state.api_key_rate_limit = key_info["rate_limit"]

            logger.info("API key authenticated",
                       key_id=key_info["key_id"],
                       service_account_id=service_account_id,
                       tenant_id=key_info["tenant_id"])

            return user  # Real User object from database!

        else:
            raise HTTPException(401, "Unsupported token type")

    async def _validate_feature_access(self, tenant_id: str, endpoint: str) -> Dict[str, Any]:
        """
        Validate feature access based on subscription.

        ENH-008: this previously returned `{"access_granted": True}` whenever the
        subscription lookup raised. Degrading the subscription service therefore
        granted EVERY tenant EVERY paid feature -- a revenue-integrity and
        entitlement failure, and a fabricated success response of exactly the
        kind the project forbids.

        It now fails closed with a 503. A 503 is deliberately distinct from the
        403 used for a genuine entitlement denial: the tenant may well be
        entitled, we simply cannot currently prove it, and the client should
        retry rather than be told to upgrade.
        """
        try:
            return await self.subscription_service.validate_feature_access(tenant_id, endpoint)
        except Exception as e:
            logger.error(
                "Feature validation failed -- denying access (fail closed)",
                tenant_id=tenant_id,
                endpoint=endpoint,
                error=str(e)
            )
            raise HTTPException(
                status_code=503,
                detail=(
                    "Subscription verification is temporarily unavailable. "
                    "Please retry shortly."
                )
            )

    async def _calculate_api_call_cost(self, endpoint: str, status_code: int, response_size: int = 0) -> float:
        """Calculate API call cost using pricing.yml configuration"""
        try:
            # Import BillingService to use pricing configuration
            from services.billing_service import BillingService
            billing_service = BillingService()

            # Get pricing from configuration
            feature_pricing = billing_service.pricing_config.get("feature_pricing", {})
            api_pricing = feature_pricing.get("api.calls", {})
            base_price_per_1000 = api_pricing.get("base_price", 1.50)  # $1.50 per 1000 calls as per pricing.yml

            # Calculate cost per single API call
            cost_per_call = base_price_per_1000 / 1000.0

            # Apply billing policy for failed requests (same as before)
            if 500 <= status_code < 600:
                return 0.0  # No charge for server errors
            elif status_code in [401, 403]:
                return cost_per_call * 0.1  # Minimal charge for auth processing
            elif 400 <= status_code < 500:
                return cost_per_call * 0.5  # Partial charge for client errors
            else:
                # Full charge for successful requests
                return cost_per_call

        except Exception as e:
            logger.warning("Failed to calculate API cost from pricing.yml, using fallback", error=str(e))
            # Fallback to a reasonable default if pricing config fails
            return 0.0015  # $1.50 / 1000 calls = $0.0015 per call

    def _track_api_cost_background(self, tenant_id: str):
        """Track API call cost calculation in background thread (same pattern as monthly_ingestion)"""
        try:
            import threading
            import asyncio

            def run_async_in_thread():
                """Run async processing in a separate thread with its own event loop (same as dependencies.py)"""
                try:
                    # Create a new ClickHouse client instance for this background task
                    from clickhouse_connect import get_client
                    background_client = get_client(
                        host=CLICKHOUSE_HOST,
                        port=CLICKHOUSE_PORT,
                        username=CLICKHOUSE_USER,
                        password=CLICKHOUSE_PASSWORD,
                        database=CLICKHOUSE_DATABASE,
                        send_receive_timeout=120
                    )

                    if not background_client:
                        logger.error("Failed to create background ClickHouse client")
                        return

                    # Run the async function in a new event loop
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    try:
                        loop.run_until_complete(
                            self._track_api_cost_async(tenant_id, background_client)
                        )
                    finally:
                        loop.close()
                        background_client.close()

                except Exception as e:
                    logger.error(f"Async background API cost tracking failed: {e}")

            # Start the processing in a daemon thread (fire-and-forget - same as dependencies.py)
            thread = threading.Thread(target=run_async_in_thread, daemon=True)
            thread.start()

            logger.debug(f"Non-blocking API cost tracking started for tenant {tenant_id}")

        except Exception as e:
            logger.error(f"Failed to start background API cost tracking: {e}")

    async def _track_api_cost_async(self, tenant_id: str, client):
        """Async function for API cost calculation and tracking (same pattern as track_usage_with_cost_calculation)"""
        try:
            # Import services within the function to avoid circular imports (same as dependencies.py)
            from services.tenant_service import TenantService
            from event_processing import track_usage_with_cost_calculation

            # Track API call quota with proper cost calculation (same as monthly_ingestion)
            tenant_service = TenantService()
            await track_usage_with_cost_calculation(tenant_service, tenant_id, "api_calls", 1)

            logger.debug(f"API cost tracking completed: tenant_id={tenant_id}")

        except Exception as e:
            logger.warning(f"API cost calculation failed in background: tenant_id={tenant_id}, error={str(e)}")

    async def _track_api_usage(self, request: Request, response, user: User,
                              tenant_id: str, start_time: float):
        """Track API usage for billing (async)"""
        try:
            current_time = time.time()
            processing_time = int((current_time - start_time) * 1000)

            # Get request and response sizes safely
            request_size = 0
            response_size = 0

            # Get request size
            if hasattr(request, "headers"):
                content_length = request.headers.get("content-length")
                if content_length:
                    try:
                        request_size = int(content_length)
                    except (ValueError, TypeError):
                        request_size = 0

            # Get response size
            if hasattr(response, "body"):
                response_size = len(response.body)
            elif hasattr(response, "headers"):
                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        response_size = int(content_length)
                    except (ValueError, TypeError):
                        response_size = 0

            # Calculate cost using pricing.yml configuration
            cost_credits = 0.0
            try:
                cost_credits = await self._calculate_api_call_cost(
                    request.url.path,
                    getattr(response, "status_code", 200),
                    response_size
                )
                # Ensure cost is JSON-safe
                if not isinstance(cost_credits, (int, float)) or cost_credits != cost_credits or abs(cost_credits) == float('inf'):
                    cost_credits = 0.0
            except Exception:
                cost_credits = 0.0

            usage_data = {
                "tenant_id": tenant_id,
                "user_id": user.id,
                "endpoint": request.url.path,
                "method": request.method,
                "response_status": getattr(response, "status_code", 200),
                "processing_time_ms": processing_time,
                "request_size_bytes": request_size,
                "response_size_bytes": response_size,
                "ip_address": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", ""),
                "request_timestamp": datetime.utcnow(),  # Keep as datetime for ClickHouse compatibility
                "billing_feature": map_endpoint_to_feature(request.url.path),
                "cost_credits": cost_credits,
                "customer_id": tenant_id  # customer_id is the same as tenant_id in our architecture
            }

            await usage_buffer.add_usage(usage_data)

            # Track API call quota with proper cost calculation (non-blocking, same pattern as monthly_ingestion)
            self._track_api_cost_background(tenant_id)

        except Exception as e:
            logger.error("Usage tracking failed", error=str(e),
                        tenant_id=tenant_id,
                        endpoint=request.url.path)

    async def _track_audit_activity(self, request: Request, response, user: User,
                                   tenant_id: str, user_roles: List[Dict[str, Any]]):
        """Track audit activity for platform admins (async)"""
        try:
            # Determine action type based on HTTP method
            method_to_action = {
                "POST": "create",
                "PUT": "update",
                "PATCH": "update",
                "DELETE": "delete",
                "GET": "view"
            }
            action_type = method_to_action.get(request.method, "view")

            # Determine resource type and ID from endpoint
            resource_type = "unknown"
            resource_id = None

            path = request.url.path
            if path.startswith("/v1/tenants/"):
                resource_type = "tenant"
                # Extract tenant ID from path if present
                path_parts = path.split("/")
                if len(path_parts) >= 3 and path_parts[2] != "stats":
                    resource_id = path_parts[2]
            elif path.startswith("/v1/users/"):
                resource_type = "user"
                path_parts = path.split("/")
                if len(path_parts) >= 3:
                    resource_id = path_parts[2]
            elif path.startswith("/v1/admin/"):
                resource_type = "admin_panel"
            elif path.startswith("/v1/billing/"):
                resource_type = "billing"
            elif path.startswith("/v1/usage/"):
                resource_type = "usage_analytics"
            elif path.startswith("/v1/analytics/"):
                resource_type = "platform_analytics"
            elif path.startswith("/v1/enterprise/"):
                resource_type = "enterprise_config"
            else:
                # Use the path to determine resource
                resource_type = path.split("/")[2] if len(path.split("/")) > 2 else "platform"

            # Get request body for details (if available and safe)
            request_details = {
                "endpoint": path,
                "method": request.method,
                "response_status": getattr(response, "status_code", 200),
                "user_agent": request.headers.get("user-agent", ""),
                "target_tenant": tenant_id,
                "platform_roles": [role["role"] for role in user_roles if role["tenant_id"] == "platform"]
            }

            # Add query parameters if present
            if request.url.query:
                request_details["query_params"] = str(request.url.query)

            # Try to get request body for certain operations (be careful with large payloads)
            if action_type in ["create", "update"] and request.method in ["POST", "PUT", "PATCH"]:
                try:
                    # Only for small payloads to avoid memory issues
                    content_length = request.headers.get("content-length")
                    if content_length and int(content_length) < 10000:  # 10KB limit
                        # Note: request.body() can only be called once, so we might not have access
                        # This is a limitation of FastAPI middleware - body is already consumed
                        request_details["has_request_body"] = True
                        request_details["content_length"] = int(content_length)
                except:
                    pass

            # Import json for serialization
            import json
            details_json = json.dumps(request_details)

            # Create audit log entry
            audit_entry = {
                "id": str(uuid.uuid4()),
                "user_id": user.id,
                "tenant_id": tenant_id if tenant_id != "platform" else None,  # NULL for platform operations
                "action_type": action_type,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "details": details_json,
                "ip_address": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", ""),
                "timestamp": datetime.utcnow(),
                "customer_id": "platform"  # All admin activities go to platform customer
            }

            # Insert audit log to database
            await self._insert_audit_log(audit_entry)

        except Exception as e:
            logger.error("Audit logging failed", error=str(e),
                        user_id=user.id,
                        endpoint=request.url.path)

    async def _insert_audit_log(self, audit_entry: Dict[str, Any]):
        """Insert audit log entry to database"""
        try:
            # Initialize DatabaseLayer for audit logging
            service_key = os.getenv("AUDIT_SERVICE_KEY", "audit-service-key-dev")
            db = DatabaseLayer("AuditService", service_key)

            # Insert into enterprise_audit_logs_mt table
            insert_query = """
                INSERT INTO enterprise_audit_logs_mt
                (id, user_id, tenant_id, action_type, resource_type, resource_id,
                 details, ip_address, user_agent, timestamp, customer_id)
                VALUES
                (%(id)s, %(user_id)s, %(tenant_id)s, %(action_type)s, %(resource_type)s,
                 %(resource_id)s, %(details)s, %(ip_address)s, %(user_agent)s, %(timestamp)s, %(customer_id)s)
            """

            # Convert action_type to enum value for ClickHouse
            action_type_map = {
                "create": 1,
                "update": 2,
                "delete": 3,
                "view": 4,
                "login": 5,
                "logout": 6
            }

            # Prepare data for ClickHouse
            clickhouse_data = audit_entry.copy()
            clickhouse_data["action_type"] = action_type_map.get(audit_entry["action_type"], 4)  # Default to 'view'

            await db.execute_update(insert_query, clickhouse_data)
            logger.debug("Audit log entry inserted",
                        user_id=audit_entry["user_id"],
                        action=audit_entry["action_type"],
                        resource=audit_entry["resource_type"])

        except Exception as e:
            logger.error("Failed to insert audit log entry to database",
                        error=str(e),
                        user_id=audit_entry["user_id"])
            # Continue without failing - audit logging should not block requests

# =================================================================
# DEPENDENCY INJECTION
# =================================================================

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends

security = HTTPBearer()

async def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current authenticated user (supports both JWT sessions and API keys)"""
    # Check if middleware already authenticated the user
    if hasattr(request.state, "user") and request.state.user:
        return request.state.user

    # Fallback: validate session directly (for endpoints not going through middleware)
    user = await get_user_service().validate_session(credentials.credentials)
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

# Global instances.
#
# `InvitationManager()` does no I/O in its constructor, so it stays eager.
# `setup_token_manager` and `user_service` DO connect to the database, so they
# are resolved on first attribute access via the PEP 562 hook below
# (ENH-008/ENH-010). This keeps every existing `user_service.…` /
# `setup_token_manager.…` call site working unchanged while allowing this
# module -- the whole authentication layer -- to be imported and tested without
# live infrastructure.
invitation_manager = InvitationManager()


def __getattr__(name: str):
    """Resolve database-backed module globals lazily (PEP 562)."""
    if name == "user_service":
        return get_user_service()
    if name == "setup_token_manager":
        return get_setup_token_manager()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def setup_unified_auth_middleware(app):
    """Setup unified authentication and authorization middleware"""
    app.add_middleware(UnifiedAuthMiddleware)
    logger.debug("Unified Authentication & Authorization middleware configured")
