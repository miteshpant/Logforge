# Logforge Permission Flow & Authentication System

## Overview

Logforge implements a comprehensive 6-step authentication and authorization system through the `UnifiedAuthMiddleware` that combines:

1. **Authentication** (JWT token validation)
2. **Authorization** (role-based permissions)
3. **Tenant Context** (multi-tenant isolation)
4. **Permission Checking** (endpoint-specific permissions)
5. **Feature Access** (subscription-based feature validation)
6. **Usage Tracking** (billing and audit)

## Authentication Flow

### Step 1: Authentication - JWT Token Validation

**Location**: `authn_authz_middleware.py:697-703`

```python
auth_context = await self._extract_authentication(request)
user = await self._validate_user_session(auth_context)
```

**Process**:
- Extracts `Authorization: Bearer <token>` header
- Validates JWT token signature and expiration
- Looks up user session in ClickHouse database
- Returns authenticated `User` object

**Failure Cases**:
- Missing Authorization header → 401 "Authorization header required"
- Invalid/expired JWT token → 401 "Token has expired" or "Invalid token"
- User session not found → 401 "Invalid session"

### Step 2: Tenant Context Extraction

**Location**: `authn_authz_middleware.py:704-709`

```python
tenant_id = request.headers.get("X-Customer-ID")
if not tenant_id and not request.url.path.startswith("/v1/auth/"):
    raise HTTPException(400, "X-Customer-ID header required")
```

**Process**:
- Extracts `X-Customer-ID` header from request
- Required for all non-auth endpoints
- Establishes tenant isolation context

**Failure Cases**:
- Missing X-Customer-ID header → 400 "X-Customer-ID header required"

### Step 3: Authorization - Tenant Access Validation

**Location**: `authn_authz_middleware.py:711-719`

```python
user_roles = await self.user_service.get_user_tenant_roles(user.id, tenant_id)
if not user_roles:
    raise HTTPException(403, f"No access to tenant: {tenant_id}")
```

**Process**:
- Queries `user_tenant_roles_mt` table in ClickHouse
- Validates user has any role assignment for the tenant
- Returns list of user roles for the tenant

**Failure Cases**:
- User has no roles for tenant → 403 "No access to tenant: {tenant_id}"

### Step 4: Permission Checking

**Location**: `authn_authz_middleware.py:721-726`

```python
required_permission = get_endpoint_permission(request.url.path, request.method)
if not check_permission(user_roles, required_permission, tenant_id):
    raise HTTPException(403, f"Insufficient permissions for {request.url.path}")
```

**Process**:
- Maps endpoint + HTTP method to required permission
- Checks if user's roles grant the required permission
- Uses role-based permission hierarchy

**Failure Cases**:
- User lacks required permission → 403 "Insufficient permissions for {endpoint}"

### Step 5: Feature Access - Subscription Validation

**Location**: `authn_authz_middleware.py:728-741`

```python
feature_access = await self._validate_feature_access(tenant_id, request.url.path)
if not feature_access["access_granted"]:
    return JSONResponse(status_code=403, content={
        "error": feature_access["error_code"],
        "message": feature_access["reason"],
        "required_feature": feature_access.get("required_feature"),
        "current_subscription": feature_access.get("current_features", []),
        "upgrade_url": f"/v1/tenants/{tenant_id}/subscription/upgrade"
    })
```

**Process**:
1. Maps endpoint to required feature using `endpoint_feature_map`
2. Retrieves tenant's active subscription
3. Validates subscription includes required feature (with wildcard support)

**Feature Mapping Examples**:
```python
"/v1/enterprise/auth/*": "enterprise.auth"
"/v1/enterprise/rbac/*": "enterprise.rbac" 
"/v1/enterprise/compliance/*": "enterprise.compliance"
"/v1/security/events": "security.events"
"/v1/alerts/rules": "alerts.basic"
```

**Subscription Tiers**:
- **startup/starter**: Basic features only (`ingestion.basic`, `queries.basic`)
- **smb/professional**: Extended features with wildcards (`ingestion.*`, `alerts.basic`)
- **enterprise**: All features (`*` - universal wildcard access)
- **government**: Security-focused features
- **education/non_profit**: Limited feature sets

**Failure Cases**:
- No subscription found → 403 "subscription_not_found"
- Inactive subscription → 403 "subscription_inactive" 
- Feature not in subscription → 403 "feature_not_subscribed"

### Step 6: Request Processing & Usage Tracking

**Location**: `authn_authz_middleware.py:743-750`

```python
request.state.user = user
request.state.tenant_id = tenant_id
request.state.roles = user_roles
response = await call_next(request)
await self._track_api_usage(request, response, user, tenant_id, start_time)
```

**Process**:
- Adds authentication context to request state
- Processes the actual API request
- Tracks API usage for billing (async, zero-latency)

## Public Endpoints (No Authentication)

**Location**: `authn_authz_middleware.py:661-673`

```python
self.public_endpoints = [
    "/", "/health", "/docs", "/openapi.json", "/redoc",
    "/v1/auth/login", "/v1/auth/setup/init", "/v1/auth/setup",
    "/v1/auth/accept-invite", "/v1/auth/password/reset",
    "/v1/auth/password/reset-confirm"
]
```

These endpoints bypass all authentication and authorization checks.

## Admin Endpoints (Auth Only, No Feature Validation)

**Location**: `authn_authz_middleware.py:675-678`

```python
self.admin_endpoints = ["/v1/admin/"]
```

Admin endpoints require authentication but skip feature/subscription validation.

## Enterprise Router Authentication Issue

### Root Cause

Enterprise router tests were failing with:

```json
{
  "error": "subscription_not_found",
  "message": "No subscription found",
  "required_feature": null,
  "current_subscription": [],
  "upgrade_url": "/v1/tenants/test-tenant-31485/subscription/upgrade"
}
```

### Analysis

1. **Enterprise endpoints require features**: `/v1/enterprise/*` endpoints map to enterprise features
2. **Test tenant has no subscription**: Base test creates tenant but no subscription
3. **Feature validation fails**: Without subscription, feature access is denied at Step 5

### Solution

The enterprise router test needs to:

1. **Create proper UUID tenant** (not simple string like `test-tenant-31485`)
2. **Create enterprise subscription** with required features:
   ```python
   subscription_request = {
       "subscribed_features": ["enterprise.*", "ingestion.*", "queries.*", "alerts.*", "security.*"],
       "subscription_tier": "enterprise",
       "billing_cycle": "monthly",
       "auto_renewal": True
   }
   ```
3. **Use PUT method** for subscription creation (not POST)
4. **Ensure proper tenant context** throughout test execution

## Role-Based Permission System

### Built-in Roles

**Platform Roles** (tenant_id = "platform"):
- `super_admin`: Full platform access
- `admin`: Platform administration
- `support_admin`: Support operations
- `billing_admin`: Billing management

**Tenant Roles**:
- `tenant_admin`: Full tenant access
- `security_analyst`: Security features access
- `devops_engineer`: Operational access
- `compliance_officer`: Compliance features
- `viewer`: Read-only access

### Permission Hierarchy

Permissions follow a hierarchical pattern:
- `logs:read` < `logs:write` < `logs:admin`
- `dashboards:read` < `dashboards:write`
- `alerts:read` < `alerts:write` < `alerts:admin`

### Multi-Tenant Isolation

**Enforcement Points**:
1. **Middleware Level**: X-Customer-ID header validation
2. **Database Level**: All queries filtered by tenant_id
3. **Service Level**: Tenant context passed through all operations
4. **API Level**: Cross-tenant access blocked with 403 errors

## Configuration

### Environment Variables

```bash
# JWT Configuration
JWT_SECRET=logforge-jwt-secret-key-change-in-production
JWT_ALGORITHM=HS256
SESSION_EXPIRY_HOURS=8

# ClickHouse Configuration
CLICKHOUSE_HOST=clickhouse
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=logforge
CLICKHOUSE_PASSWORD=logforge123
CLICKHOUSE_DATABASE=logforge
```

### Database Tables

**Authentication Tables**:
- `users_mt`: User accounts with tenant isolation
- `user_sessions_mt`: JWT session storage
- `user_tenant_roles_mt`: User-tenant-role mappings

**Subscription Tables**:
- `tenant_subscriptions_mt`: Tenant subscription details
- `subscription_usage_mt`: Feature usage tracking
- `subscription_features_mt`: Available features and rates

## Debugging Authentication Issues

### Common Error Messages

1. **"Authorization header required"**
   - Missing `Authorization: Bearer <token>` header
   - Check JWT token generation and inclusion

2. **"Token has expired"** 
   - JWT token past expiration time
   - Generate new token or extend session

3. **"X-Customer-ID header required"**
   - Missing tenant context header
   - Add `X-Customer-ID: <tenant_id>` header

4. **"No access to tenant: {tenant_id}"**
   - User not assigned to tenant
   - Create user-tenant-role mapping

5. **"Insufficient permissions for {endpoint}"**
   - User role lacks required permission
   - Assign appropriate role or update permission mapping

6. **"subscription_not_found"**
   - Tenant has no active subscription
   - Create subscription with required features

7. **"feature_not_subscribed"**
   - Subscription doesn't include required feature
   - Upgrade subscription or add feature

### Debug Logging

Enable debug logging in middleware:
```python
logger.debug("🔍 AUTH STEP X: Description", 
            user_id=user.id, tenant_id=tenant_id, path=str(request.url.path))
```

### Testing Authentication

```python
# Proper test setup
await self.create_test_user_and_tenant(['tenant_admin'])
await self.setup_auth()
await self.setup_enterprise_subscription()  # Create subscription with enterprise features

# Request headers
headers = {
    "Authorization": f"Bearer {jwt_token}",
    "X-Customer-ID": tenant_id,
    "Content-Type": "application/json"
}
```

## Integration with FastAPI

The middleware is integrated into the FastAPI application in `main.py`:

```python
from authn_authz_middleware import setup_unified_auth_middleware

app = FastAPI()
setup_unified_auth_middleware(app)
```

This ensures all API routes (except public endpoints) go through the complete authentication and authorization flow.

## Performance Characteristics

- **Authentication**: ~10-20ms (JWT decode + database lookup)
- **Authorization**: ~5-10ms (role query and permission check)
- **Feature Validation**: ~10-15ms (subscription query and feature matching)
- **Usage Tracking**: ~1-2ms (async buffer, zero request latency)

**Total Overhead**: ~25-50ms per authenticated request

## Security Features

1. **JWT Security**: Signed tokens with configurable expiration
2. **Session Validation**: Database-backed session verification
3. **Multi-Tenant Isolation**: Complete tenant data separation
4. **Role-Based Access**: Granular permission system
5. **Feature Gating**: Subscription-based feature access
6. **Audit Logging**: Complete API usage tracking
7. **Rate Limiting**: Built-in usage monitoring for billing

The system provides enterprise-grade security with multiple layers of validation and complete audit trails for compliance requirements.