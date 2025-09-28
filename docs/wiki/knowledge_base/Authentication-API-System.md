# Logforge Authentication API System

## Overview

The Logforge Authentication API provides comprehensive user authentication and authorization services for the M8 foundation layer. Built on FastAPI with JWT token-based sessions and multi-tenant architecture, the system supports platform setup, user management, password security, invitation workflows, and session management.

**Base URL**: `/v1/auth`  
**Authentication**: Bearer token required for most endpoints  
**Multi-tenant**: X-Customer-ID header required for tenant-scoped operations

---

## Core Authentication Endpoints

### 1. User Login
**Endpoint**: `POST /v1/auth/login`

Authenticates user with email and password, returns JWT access token and user profile.

**Request Body**:
```json
{
  "email": "user@company.com",
  "password": "SecurePassword123!"
}
```

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@mrlogsec.com",
    "password": "SecureAdmin123!"
  }'
```

**Response Structure**:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "expires_at": "2024-01-01T20:00:00Z",
  "user": {
    "id": "user-uuid-123",
    "email": "admin@mrlogsec.com",
    "name": "Platform Administrator",
    "status": "active",
    "created_at": "2024-01-01T10:00:00Z",
    "updated_at": "2024-01-01T12:00:00Z",
    "last_login_at": "2024-01-01T12:00:00Z",
    "email_verified_at": "2024-01-01T10:05:00Z"
  }
}
```

**Error Responses**:
- `401`: Invalid email or password
- `500`: Login system error

### 2. User Logout
**Endpoint**: `POST /v1/auth/logout`

Invalidates current user session and revokes access token.

**Authentication**: Bearer token required

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/auth/logout" \
  -H "Authorization: Bearer <access-token>"
```

**Response Structure**:
```json
{
  "message": "Logout successful"
}
```

### 3. Refresh Session
**Endpoint**: `POST /v1/auth/refresh`

Refreshes user session with new access token, invalidates old token.

**Authentication**: Bearer token required

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/auth/refresh" \
  -H "Authorization: Bearer <current-token>"
```

**Response Structure**:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "expires_at": "2024-01-01T20:00:00Z",
  "user": {
    "id": "user-uuid-123",
    "email": "admin@mrlogsec.com",
    "name": "Platform Administrator",
    "status": "active",
    "created_at": "2024-01-01T10:00:00Z",
    "updated_at": "2024-01-01T12:00:00Z",
    "last_login_at": "2024-01-01T12:00:00Z",
    "email_verified_at": "2024-01-01T10:05:00Z"
  }
}
```

### 4. Get User Profile
**Endpoint**: `GET /v1/auth/me`

Retrieves current user profile information.

**Authentication**: Bearer token required

**Request Example**:
```bash
curl -X GET "https://api.logforge.com/v1/auth/me" \
  -H "Authorization: Bearer <access-token>"
```

**Response Structure**:
```json
{
  "id": "user-uuid-123",
  "email": "admin@mrlogsec.com",
  "name": "Platform Administrator",
  "status": "active",
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z",
  "last_login_at": "2024-01-01T12:00:00Z",
  "email_verified_at": "2024-01-01T10:05:00Z"
}
```

---

## Platform Setup Endpoints

### 5. Initialize Platform Setup
**Endpoint**: `POST /v1/auth/setup/init`

Generates initial setup token for creating the first platform administrator. Only works if platform setup is not already completed.

**No Authentication Required**

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/auth/setup/init"
```

**Response Structure**:
```json
{
  "setup_token": "setup_3a8f9c2d1b4e5f6a7c8d9e0f1a2b3c4d",
  "expires_at": "2024-01-01T13:00:00Z"
}
```

**Error Responses**:
- `400`: Platform setup already completed
- `500`: Setup initialization failed

### 6. Complete Platform Setup
**Endpoint**: `POST /v1/auth/setup`

Creates the first platform administrator using the setup token from the initialization endpoint.

**Request Body**:
```json
{
  "name": "Platform Administrator",
  "email": "admin@company.com",
  "password": "SecurePassword123!",
  "setup_token": "setup_3a8f9c2d1b4e5f6a7c8d9e0f1a2b3c4d"
}
```

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/auth/setup" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Platform Administrator",
    "email": "admin@mrlogsec.com",
    "password": "SecureAdmin123!",
    "setup_token": "setup_3a8f9c2d1b4e5f6a7c8d9e0f1a2b3c4d"
  }'
```

**Response Structure**:
```json
{
  "id": "admin-uuid-456",
  "email": "admin@mrlogsec.com",
  "name": "Platform Administrator",
  "status": "active",
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:00:00Z",
  "last_login_at": null,
  "email_verified_at": null
}
```

**Error Responses**:
- `400`: Invalid or expired setup token
- `409`: User with email already exists
- `500`: Platform setup failed

---

## Password Management Endpoints

### 7. Request Password Reset
**Endpoint**: `POST /v1/auth/password/reset`

Initiates password reset process by generating reset token and sending instructions (email implementation pending).

**Request Body**:
```json
{
  "email": "user@company.com"
}
```

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/auth/password/reset" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@company.com"
  }'
```

**Response Structure**:
```json
{
  "message": "Password reset instructions sent if email exists"
}
```

**Security Note**: Always returns same message regardless of whether email exists to prevent email enumeration.

### 8. Confirm Password Reset
**Endpoint**: `POST /v1/auth/password/reset-confirm`

Completes password reset using reset token and new password.

**Query Parameters**:
- `token`: Password reset token from email
- `new_password`: New password (must meet strength requirements)

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/auth/password/reset-confirm?token=reset_token_123&new_password=NewSecurePassword123!" \
  -H "Content-Type: application/json"
```

**Response Structure**:
```json
{
  "message": "Password reset successfully"
}
```

**Error Responses**:
- `400`: Invalid or expired reset token
- `400`: Password strength validation failed
- `500`: Password reset confirmation failed

### 9. Change Password
**Endpoint**: `POST /v1/auth/password/change`

Changes user password with current password verification.

**Authentication**: Bearer token required

**Request Body**:
```json
{
  "current_password": "OldPassword123!",
  "new_password": "NewSecurePassword123!"
}
```

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/auth/password/change" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "OldPassword123!",
    "new_password": "NewSecurePassword123!"
  }'
```

**Response Structure**:
```json
{
  "message": "Password changed successfully"
}
```

**Error Responses**:
- `400`: Current password is incorrect
- `400`: New password strength validation failed
- `500`: Password change failed

---

## User Invitation System

### 10. Send User Invitation
**Endpoint**: `POST /v1/auth/invite`

Sends invitation to new user for specific tenant and role. Requires platform admin or tenant admin permissions.

**Authentication**: Bearer token required
**Authorization**: Platform admin or tenant admin for target tenant

**Request Body**:
```json
{
  "email": "newuser@company.com",
  "role": "security_analyst",
  "tenant_id": "tenant-uuid-789"
}
```

**Available Roles**:
- Platform roles: `super_admin`, `admin`, `support_admin`, `billing_admin`
- Tenant roles: `tenant_admin`, `security_analyst`, `devops_engineer`, `compliance_officer`, `viewer`

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/auth/invite" \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "analyst@company.com",
    "role": "security_analyst",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**Response Structure**:
```json
{
  "invitation_token": "invite_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
  "invitation_expires": "2024-01-08T10:00:00Z",
  "invited_email": "analyst@company.com",
  "email": "analyst@company.com"
}
```

**Error Responses**:
- `403`: No permission to invite users to tenant
- `409`: User with email already exists
- `500`: User invitation failed

### 11. Accept Invitation
**Endpoint**: `POST /v1/auth/accept-invite`

Accepts user invitation and creates new user account with specified role.

**Request Body**:
```json
{
  "name": "Security Analyst",
  "email": "analyst@company.com",
  "password": "SecurePassword123!",
  "invitation_token": "invite_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
  "tenant_id": "tenant-uuid-789"
}
```

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/auth/accept-invite" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Security Analyst",
    "email": "analyst@company.com",
    "password": "SecureAnalyst123!",
    "invitation_token": "invite_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**Response Structure**:
```json
{
  "id": "analyst-uuid-789",
  "email": "analyst@company.com",
  "name": "Security Analyst",
  "status": "active",
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:00:00Z",
  "last_login_at": null,
  "email_verified_at": null
}
```

**Error Responses**:
- `400`: Invalid or expired invitation
- `400`: Tenant ID does not match invitation
- `409`: User with email already exists
- `500`: Invitation acceptance failed

---

## Email Verification Endpoints

### 12. Send Email Verification
**Endpoint**: `POST /v1/auth/verify-email`

Sends email verification token to current user (implementation pending).

**Authentication**: Bearer token required

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/auth/verify-email" \
  -H "Authorization: Bearer <access-token>"
```

**Response Structure**:
```json
{
  "message": "Verification email sent"
}
```

**Error Responses**:
- `400`: Email already verified
- `500`: Email verification failed

### 13. Confirm Email Verification
**Endpoint**: `POST /v1/auth/verify-email-confirm`

Confirms email verification with token (implementation pending).

**Authentication**: Bearer token required

**Query Parameters**:
- `token`: Email verification token

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/auth/verify-email-confirm?token=verify_token_456" \
  -H "Authorization: Bearer <access-token>"
```

**Response Structure**:
```json
{
  "message": "Email verified successfully"
}
```

**Error Responses**:
- `500`: Email verification confirmation failed

---

## Tenant Onboarding

### 14. Tenant Onboarding
**Endpoint**: `POST /v1/auth/tenant-onboard`

Platform admin creates new tenant and sends invitation to tenant administrator.

**Authentication**: Bearer token required
**Authorization**: Platform admin permissions required

**Query Parameters**:
- `tenant_name`: Name for new tenant organization
- `admin_email`: Email for tenant administrator
- `subscription_tier`: Subscription tier (default: "professional")

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/auth/tenant-onboard?tenant_name=Acme%20Corp&admin_email=admin@acme.com&subscription_tier=enterprise" \
  -H "Authorization: Bearer <platform-admin-token>"
```

**Response Structure**:
```json
{
  "invitation_token": "invite_b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7",
  "invitation_expires": "2024-01-08T10:00:00Z",
  "invited_email": "admin@acme.com",
  "email": "admin@acme.com"
}
```

**Error Responses**:
- `403`: Platform admin access required
- `500`: Tenant onboarding failed

---

## Session Management Endpoints

### 15. List User Sessions
**Endpoint**: `GET /v1/auth/sessions`

Lists all active sessions for the current user.

**Authentication**: Bearer token required

**Request Example**:
```bash
curl -X GET "https://api.logforge.com/v1/auth/sessions" \
  -H "Authorization: Bearer <access-token>"
```

**Response Structure**:
```json
{
  "sessions": [
    {
      "session_id": "session-uuid-123",
      "ip_address": "192.168.1.100",
      "user_agent": "Mozilla/5.0...",
      "created_at": "2024-01-01T10:00:00Z",
      "expires_at": "2024-01-01T18:00:00Z",
      "is_current": true
    },
    {
      "session_id": "session-uuid-456",
      "ip_address": "10.0.0.50",
      "user_agent": "curl/7.68.0",
      "created_at": "2024-01-01T09:00:00Z",
      "expires_at": "2024-01-01T17:00:00Z",
      "is_current": false
    }
  ],
  "total_count": 2
}
```

### 16. Revoke All Sessions
**Endpoint**: `DELETE /v1/auth/sessions/all`

Revokes all user sessions except the current one used for the request.

**Authentication**: Bearer token required

**Request Example**:
```bash
curl -X DELETE "https://api.logforge.com/v1/auth/sessions/all" \
  -H "Authorization: Bearer <access-token>"
```

**Response Structure**:
```json
{
  "message": "Revoked 3 sessions successfully"
}
```

### 17. Revoke Specific Session
**Endpoint**: `DELETE /v1/auth/sessions/{session_id}`

Revokes a specific user session by session ID.

**Authentication**: Bearer token required

**Path Parameters**:
- `session_id`: Session identifier to revoke

**Request Example**:
```bash
curl -X DELETE "https://api.logforge.com/v1/auth/sessions/session-uuid-456" \
  -H "Authorization: Bearer <access-token>"
```

**Response Structure**:
```json
{
  "message": "Session revoked successfully"
}
```

**Error Responses**:
- `404`: Session not found or already revoked
- `500`: Session revocation failed

---

## Account Management Endpoints

### 18. Deactivate Account
**Endpoint**: `POST /v1/auth/deactivate`

Deactivates current user account (sets status to inactive).

**Authentication**: Bearer token required

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/auth/deactivate" \
  -H "Authorization: Bearer <access-token>"
```

**Response Structure**:
```json
{
  "message": "Account deactivated successfully"
}
```

### 19. Reactivate Account
**Endpoint**: `POST /v1/auth/reactivate/{user_id}`

Reactivates deactivated user account (platform admins only).

**Authentication**: Bearer token required
**Authorization**: Platform admin permissions required

**Path Parameters**:
- `user_id`: User identifier to reactivate

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/auth/reactivate/user-uuid-789" \
  -H "Authorization: Bearer <platform-admin-token>"
```

**Response Structure**:
```json
{
  "message": "Account reactivated successfully"
}
```

**Error Responses**:
- `404`: User not found
- `400`: User is not inactive
- `403`: Platform admin access required
- `500`: Account reactivation failed

---

## Security Features

### Password Security Requirements

**Password Strength Validation**:
- Minimum 12 characters length
- Must contain uppercase letters
- Must contain lowercase letters  
- Must contain numbers
- Must contain special characters
- Dictionary check for common weak passwords
- Bcrypt hashing with 12+ rounds

**Example Password Validation Error**:
```json
{
  "error": "validation_error",
  "message": "Password must be at least 12 characters and contain uppercase, lowercase, numbers, and special characters",
  "field": "password"
}
```

### Session Security

**JWT Token Properties**:
- **Algorithm**: HS256 (HMAC with SHA-256)
- **Default Expiration**: 8 hours
- **Refresh Capability**: Tokens can be refreshed before expiration
- **Automatic Revocation**: Old tokens revoked on refresh/logout

**Session Tracking**:
- IP address logging for security monitoring
- User agent tracking for device identification
- Session expiration and cleanup
- Multi-session support with individual revocation

### Security Monitoring

**Login Security**:
- Failed login attempt logging with IP tracking
- Brute force protection (rate limiting recommended)
- Email enumeration prevention (consistent responses)
- Suspicious activity alerts

**Account Security**:
- Password reset token expiration (1 hour)
- Email verification token expiration (24 hours)
- Invitation token expiration (7 days)
- Session timeout and cleanup

---

## Multi-Tenant Architecture

### Tenant Isolation

**Platform vs Tenant Roles**:
- **Platform Tenant ID**: `"platform"` for global administration
- **Tenant-Specific Roles**: UUID-based tenant identification
- **Role Hierarchy**: Platform admins can access any tenant

**Permission Structure**:
```
Platform Admin (tenant_id: "platform")
├── super_admin: Full platform access
├── admin: Platform management
├── support_admin: Support operations
└── billing_admin: Billing management

Tenant Roles (tenant_id: "<uuid>")
├── tenant_admin: Full tenant access
├── security_analyst: Security operations
├── devops_engineer: Infrastructure management
├── compliance_officer: Compliance reporting
└── viewer: Read-only access
```

### Cross-Tenant Access

**Platform Admin Privileges**:
- Can create and manage any tenant
- Can invite users to any tenant
- Can reactivate any user account
- Can access tenant onboarding flows

**Tenant Admin Privileges**:
- Can invite users to their tenant only
- Can manage users within their tenant
- Cannot access other tenants

---

## Data Models

### User Status Enumeration
```
ACTIVE: "active" - User can login and access resources
INACTIVE: "inactive" - User deactivated, cannot login
PENDING: "pending" - User created but not activated
SUSPENDED: "suspended" - User temporarily blocked
```

### User Role Enumeration
```
Platform Roles:
- SUPER_ADMIN: "super_admin"
- ADMIN: "admin"  
- SUPPORT_ADMIN: "support_admin"
- BILLING_ADMIN: "billing_admin"

Tenant Roles:
- TENANT_ADMIN: "tenant_admin"
- SECURITY_ANALYST: "security_analyst"
- DEVOPS_ENGINEER: "devops_engineer"
- COMPLIANCE_OFFICER: "compliance_officer"
- VIEWER: "viewer"
```

### Authentication Flow Models

**Login Request/Response**:
```json
{
  "LoginRequest": {
    "email": "string",
    "password": "string"
  },
  "LoginResponse": {
    "access_token": "string",
    "expires_at": "datetime",
    "user": "UserResponse"
  }
}
```

**Setup Request/Response**:
```json
{
  "AdminSetupRequest": {
    "name": "string",
    "email": "string", 
    "password": "string",
    "setup_token": "string"
  },
  "SetupTokenResponse": {
    "setup_token": "string",
    "expires_at": "datetime"
  }
}
```

**Invitation Request/Response**:
```json
{
  "InvitationRequest": {
    "email": "string",
    "role": "UserRole",
    "tenant_id": "string"
  },
  "InvitationResponse": {
    "invitation_token": "string",
    "invitation_expires": "datetime",
    "invited_email": "string",
    "email": "string"
  }
}
```

---

## Error Handling

### Authentication Errors

**401 - Unauthorized**:
```json
{
  "error": "unauthorized",
  "message": "Invalid email or password"
}
```

**403 - Forbidden**:
```json
{
  "error": "insufficient_permissions",
  "message": "Platform admin access required"
}
```

**409 - Conflict**:
```json
{
  "error": "user_exists",
  "message": "User with email user@company.com already exists"
}
```

**400 - Validation Error**:
```json
{
  "error": "validation_error",
  "message": "Password must be at least 12 characters and contain uppercase, lowercase, numbers, and special characters",
  "field": "password"
}
```

**500 - Server Error**:
```json
{
  "error": "internal_error",
  "message": "Login system error"
}
```

---

## Integration Examples

### Complete Authentication Flow
```javascript
// 1. Platform Setup (First Time Only)
const initSetup = async () => {
  const setupResponse = await fetch('/v1/auth/setup/init', {
    method: 'POST'
  });
  const { setup_token } = await setupResponse.json();
  
  return await fetch('/v1/auth/setup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: 'Platform Admin',
      email: 'admin@company.com',
      password: 'SecureAdmin123!',
      setup_token
    })
  });
};

// 2. User Login
const login = async (email, password) => {
  const response = await fetch('/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  
  const { access_token, user } = await response.json();
  localStorage.setItem('access_token', access_token);
  return { token: access_token, user };
};

// 3. Authenticated API Calls
const makeAuthenticatedRequest = async (url, options = {}) => {
  const token = localStorage.getItem('access_token');
  return fetch(url, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...options.headers
    }
  });
};

// 4. Session Refresh
const refreshToken = async () => {
  const token = localStorage.getItem('access_token');
  const response = await fetch('/v1/auth/refresh', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  const { access_token } = await response.json();
  localStorage.setItem('access_token', access_token);
  return access_token;
};
```

### User Invitation Workflow
```bash
# 1. Platform admin invites new user
curl -X POST "https://api.logforge.com/v1/auth/invite" \
  -H "Authorization: Bearer $PLATFORM_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@company.com",
    "role": "security_analyst", 
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
  }'

# Response: {"invitation_token": "invite_abc123...", ...}

# 2. New user accepts invitation
curl -X POST "https://api.logforge.com/v1/auth/accept-invite" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Security Analyst",
    "email": "newuser@company.com",
    "password": "SecurePassword123!",
    "invitation_token": "invite_abc123...",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
  }'

# 3. New user can now login
curl -X POST "https://api.logforge.com/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@company.com",
    "password": "SecurePassword123!"
  }'
```

### Password Management Workflow
```bash
# 1. Request password reset
curl -X POST "https://api.logforge.com/v1/auth/password/reset" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@company.com"}'

# 2. Confirm reset with token (from email)
curl -X POST "https://api.logforge.com/v1/auth/password/reset-confirm?token=reset_token_123&new_password=NewSecurePassword123!" \
  -H "Content-Type: application/json"

# 3. Change password (authenticated)
curl -X POST "https://api.logforge.com/v1/auth/password/change" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "OldPassword123!",
    "new_password": "NewSecurePassword123!"
  }'
```

---

## API Reference Summary

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/v1/auth/login` | POST | User authentication | ✗ |
| `/v1/auth/logout` | POST | Session termination | ✓ |
| `/v1/auth/refresh` | POST | Token refresh | ✓ |
| `/v1/auth/me` | GET | User profile | ✓ |
| `/v1/auth/setup/init` | POST | Initialize platform | ✗ |
| `/v1/auth/setup` | POST | Complete platform setup | ✗ |
| `/v1/auth/password/reset` | POST | Request password reset | ✗ |
| `/v1/auth/password/reset-confirm` | POST | Confirm password reset | ✗ |
| `/v1/auth/password/change` | POST | Change password | ✓ |
| `/v1/auth/invite` | POST | Send user invitation | ✓ (Admin) |
| `/v1/auth/accept-invite` | POST | Accept invitation | ✗ |
| `/v1/auth/verify-email` | POST | Send email verification | ✓ |
| `/v1/auth/verify-email-confirm` | POST | Confirm email verification | ✓ |
| `/v1/auth/tenant-onboard` | POST | Tenant onboarding | ✓ (Platform Admin) |
| `/v1/auth/sessions` | GET | List user sessions | ✓ |
| `/v1/auth/sessions/all` | DELETE | Revoke all sessions | ✓ |
| `/v1/auth/sessions/{id}` | DELETE | Revoke specific session | ✓ |
| `/v1/auth/deactivate` | POST | Deactivate account | ✓ |
| `/v1/auth/reactivate/{user_id}` | POST | Reactivate account | ✓ (Platform Admin) |

**Total Endpoints**: 19  
**Security Foundation**: JWT tokens, bcrypt hashing, multi-tenant isolation  
**Platform Setup**: First-time administrator creation with secure token flow  
**User Management**: Invitation system, password security, session management