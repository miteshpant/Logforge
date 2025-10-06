# Authentication APIs

## Overview

The Authentication APIs provide secure user authentication, session management, and API key operations for the Logforge platform. All authentication endpoints support JWT-based session management with multi-tenant isolation.

**Base Path**: `/v1/auth`  
**Total Endpoints**: 18  
**Authentication Required**: Most endpoints (except login, setup, password reset)

## Core Authentication Flow

### 1. User Login
```http
POST /v1/auth/login
```

**Description**: User login with email and password

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "secure_password"
}
```

**Response** (200):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 28800,
  "user": {
    "id": "user_123",
    "email": "user@example.com",
    "tenant_id": "tenant_456",
    "roles": ["user", "analyst"]
  }
}
```

**Usage Example**:
```bash
curl -X POST "http://localhost:7080/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'
```

### 2. User Logout
```http
POST /v1/auth/logout
```

**Description**: User logout - invalidate current session

**Authentication**: Required (Bearer token)

**Headers**:
```http
Authorization: Bearer <access_token>
```

**Response** (200):
```json
{
  "message": "Successfully logged out"
}
```

**Usage Example**:
```bash
curl -X POST "http://localhost:7080/v1/auth/logout" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## User Profile & Session Management

### 3. Get Current User Profile
```http
GET /v1/auth/me
```

**Description**: Get current authenticated user's profile information

**Authentication**: Required

**Response** (200):
```json
{
  "id": "user_123",
  "email": "user@example.com",
  "tenant_id": "tenant_456",
  "roles": ["user", "analyst"],
  "created_at": "2024-01-15T10:30:00Z",
  "last_login": "2024-01-20T14:25:00Z",
  "preferences": {
    "timezone": "UTC",
    "notifications": true
  }
}
```

### 4. Session Refresh
```http
POST /v1/auth/refresh
```

**Description**: Refresh JWT token to extend session

**Authentication**: Required

**Response** (200):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 28800
}
```

### 5. List User Sessions
```http
GET /v1/auth/sessions
```

**Description**: List all active sessions for current user

**Authentication**: Required

**Response** (200):
```json
{
  "sessions": [
    {
      "session_id": "sess_123",
      "device": "Chrome on MacOS",
      "ip_address": "192.168.1.100",
      "created_at": "2024-01-20T14:25:00Z",
      "last_activity": "2024-01-20T16:30:00Z",
      "is_current": true
    }
  ]
}
```

### 6. Get Specific Session
```http
GET /v1/auth/sessions/{session_id}
```

**Description**: Get details of a specific session

**Authentication**: Required

**Path Parameters**:
- `session_id` (string): Session identifier

**Response** (200):
```json
{
  "session_id": "sess_123",
  "device": "Chrome on MacOS",
  "ip_address": "192.168.1.100",
  "created_at": "2024-01-20T14:25:00Z",
  "last_activity": "2024-01-20T16:30:00Z",
  "is_current": true
}
```

### 7. Delete Session
```http
DELETE /v1/auth/sessions/{session_id}
```

**Description**: Revoke a specific session

**Authentication**: Required

**Path Parameters**:
- `session_id` (string): Session identifier

**Response** (200):
```json
{
  "message": "Session revoked successfully"
}
```

### 8. Delete All Sessions
```http
DELETE /v1/auth/sessions/all
```

**Description**: Revoke all sessions (force re-login)

**Authentication**: Required

**Response** (200):
```json
{
  "message": "All sessions revoked successfully",
  "sessions_revoked": 3
}
```

## Password Management

### 9. Change Password
```http
POST /v1/auth/password/change
```

**Description**: Change user password (authenticated)

**Authentication**: Required

**Request Body**:
```json
{
  "current_password": "old_password",
  "new_password": "new_secure_password"
}
```

**Response** (200):
```json
{
  "message": "Password changed successfully"
}
```

### 10. Request Password Reset
```http
POST /v1/auth/password/reset
```

**Description**: Request password reset email

**Authentication**: Not required

**Request Body**:
```json
{
  "email": "user@example.com"
}
```

**Response** (200):
```json
{
  "message": "Password reset email sent"
}
```

### 11. Confirm Password Reset
```http
POST /v1/auth/password/reset-confirm
```

**Description**: Confirm password reset with token

**Authentication**: Not required

**Request Body**:
```json
{
  "token": "reset_token_123",
  "new_password": "new_secure_password"
}
```

**Response** (200):
```json
{
  "message": "Password reset successfully"
}
```

## Email Verification

### 12. Request Email Verification
```http
POST /v1/auth/verify-email
```

**Description**: Request email verification

**Authentication**: Required

**Response** (200):
```json
{
  "message": "Verification email sent"
}
```

### 13. Confirm Email Verification
```http
POST /v1/auth/verify-email-confirm
```

**Description**: Confirm email verification with token

**Authentication**: Not required

**Request Body**:
```json
{
  "token": "verify_token_123"
}
```

**Response** (200):
```json
{
  "message": "Email verified successfully"
}
```

## User Invitation System

### 14. Send User Invitation
```http
POST /v1/auth/invite
```

**Description**: Send invitation to new user

**Authentication**: Required (admin role)

**Request Body**:
```json
{
  "email": "newuser@example.com",
  "roles": ["user"],
  "tenant_id": "tenant_456"
}
```

**Response** (200):
```json
{
  "message": "Invitation sent successfully",
  "invitation_id": "inv_123"
}
```

### 15. Accept Invitation
```http
POST /v1/auth/accept-invite
```

**Description**: Accept user invitation

**Authentication**: Not required

**Request Body**:
```json
{
  "invitation_token": "inv_token_123",
  "password": "secure_password",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Response** (200):
```json
{
  "message": "Invitation accepted successfully",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "user_124",
    "email": "newuser@example.com",
    "tenant_id": "tenant_456"
  }
}
```

## Account Management

### 16. Deactivate Account
```http
POST /v1/auth/deactivate
```

**Description**: Deactivate current user account

**Authentication**: Required

**Request Body**:
```json
{
  "password": "current_password",
  "reason": "no_longer_needed"
}
```

**Response** (200):
```json
{
  "message": "Account deactivated successfully"
}
```

### 17. Reactivate User Account
```http
POST /v1/auth/reactivate/{user_id}
```

**Description**: Reactivate deactivated user account

**Authentication**: Required (admin role)

**Path Parameters**:
- `user_id` (string): User identifier

**Response** (200):
```json
{
  "message": "Account reactivated successfully"
}
```

## System Setup

### 18. Initial System Setup
```http
POST /v1/auth/setup/init
```

**Description**: Initialize system with first admin user

**Authentication**: Not required (only during initial setup)

**Request Body**:
```json
{
  "admin_email": "admin@company.com",
  "admin_password": "secure_admin_password",
  "company_name": "ACME Corp",
  "tenant_name": "acme"
}
```

**Response** (200):
```json
{
  "message": "System initialized successfully",
  "admin_user_id": "user_001",
  "tenant_id": "tenant_001"
}
```

### 19. Complete Setup
```http
POST /v1/auth/setup
```

**Description**: Complete system setup configuration

**Authentication**: Required (admin role)

**Request Body**:
```json
{
  "smtp_config": {
    "host": "smtp.company.com",
    "port": 587,
    "username": "noreply@company.com"
  },
  "security_config": {
    "password_policy": "strong",
    "session_timeout": 28800
  }
}
```

## Tenant Onboarding

### 20. Tenant Onboarding
```http
POST /v1/auth/tenant-onboard
```

**Description**: Onboard new tenant with admin user

**Authentication**: Required (platform admin)

**Request Body**:
```json
{
  "tenant_name": "newclient",
  "admin_email": "admin@newclient.com",
  "admin_password": "secure_password",
  "subscription_tier": "professional"
}
```

**Response** (200):
```json
{
  "message": "Tenant onboarded successfully",
  "tenant_id": "tenant_789",
  "admin_user_id": "user_456"
}
```

## API Keys (Enterprise)

### 21. List API Keys
```http
GET /v1/enterprise/auth/api-keys
```

**Description**: List API keys for current tenant

**Authentication**: Required

**Response** (200):
```json
{
  "api_keys": [
    {
      "id": "key_123",
      "name": "Production API Key",
      "prefix": "lf_prod_",
      "created_at": "2024-01-15T10:30:00Z",
      "last_used": "2024-01-20T14:25:00Z",
      "permissions": ["logs:read", "logs:write"]
    }
  ]
}
```

### 22. Create API Key
```http
POST /v1/enterprise/auth/api-keys
```

**Description**: Create new API key

**Authentication**: Required

**Request Body**:
```json
{
  "name": "Integration API Key",
  "permissions": ["logs:read", "logs:write"],
  "expires_at": "2025-01-15T10:30:00Z"
}
```

**Response** (200):
```json
{
  "id": "key_124",
  "name": "Integration API Key",
  "api_key": "lf_prod_abc123xyz789...",
  "permissions": ["logs:read", "logs:write"],
  "expires_at": "2025-01-15T10:30:00Z"
}
```

### 23. Delete API Key
```http
DELETE /v1/enterprise/auth/api-keys/{key_id}
```

**Description**: Delete API key

**Authentication**: Required

**Path Parameters**:
- `key_id` (string): API key identifier

**Response** (200):
```json
{
  "message": "API key deleted successfully"
}
```

## Error Responses

### Common Error Codes

| Status Code | Error Type | Description |
|-------------|------------|-------------|
| 400 | `invalid_credentials` | Invalid email/password |
| 401 | `unauthorized` | Missing or invalid token |
| 403 | `insufficient_permissions` | User lacks required permissions |
| 404 | `user_not_found` | User does not exist |
| 409 | `user_already_exists` | User with email already exists |
| 422 | `validation_error` | Request validation failed |
| 429 | `rate_limit_exceeded` | Too many requests |

### Example Error Response
```json
{
  "detail": "Invalid credentials provided",
  "type": "invalid_credentials",
  "code": "AUTH_001"
}
```

## Security Features

### Password Policy
- Minimum 12 characters
- Mixed case letters, numbers, special characters
- Dictionary check for common passwords
- Password history prevention

### Session Security
- JWT tokens with 8-hour expiration
- Automatic token refresh
- Session revocation support
- Device tracking and management

### Multi-Factor Authentication
- TOTP support (Google Authenticator, Authy)
- Backup codes generation
- Admin-enforced MFA policies

### Rate Limiting
- Login attempts: 5/minute per IP
- Password reset: 3/hour per email
- API key operations: 10/minute per user

---

*See [API Overview](./API-Overview.md) for general authentication requirements and [User Management APIs](./User-Management-APIs.md) for user CRUD operations.*