# Auth Router API - Developer Documentation

## Overview

The Auth Router API (`/v1/auth`) provides comprehensive authentication and authorization services for the Logforge platform. This system handles user login/logout, session management, password operations, user invitations, platform setup, and account management with enterprise-grade security and compliance.

**Location**: `/apps/api/routers/auth_api.py`  
**Middleware**: `/apps/api/authn_authz_middleware.py`  
**Service Layer**: `/apps/api/services/user_service.py`  
**Authentication**: Most endpoints require authentication (exceptions noted)  
**Multi-Tenancy**: Some endpoints require `X-Customer-ID` header  

## Architecture & Components

### System Architecture
```
FastAPI Router → UserService → DatabaseLayer → ClickHouse Database
     ↓              ↓             ↓              ↓
Auth Middleware  Business Logic  Database Ops   Multi-tenant Storage
JWT Generation   Password Mgmt   Session Storage User Management
Role Validation  Invitation Mgmt Query Execution Permission Control
```

### Core Components

1. **Auth Router** (`auth_api.py`): HTTP endpoint definitions and request/response handling
2. **Auth Middleware** (`authn_authz_middleware.py`): JWT validation, role-based access control, usage tracking
3. **User Service** (`user_service.py`): Business logic for user management and authentication
4. **Database Layer**: ClickHouse multi-tenant storage with secure service-level access
5. **Security Utilities**: Password hashing, token generation, invitation management

### Security Features

- **Password Validation**: 12+ characters, mixed case, numbers, special characters, dictionary check
- **JWT Sessions**: Secure token-based authentication with configurable expiry (8 hours default)
- **Multi-Factor Setup**: Foundation for MFA integration
- **Role-Based Access**: Platform and tenant-level role assignments
- **Session Management**: Multiple session support with revocation capabilities
- **Invitation System**: Secure user invitation workflow with token validation
- **Audit Logging**: Complete audit trail for all authentication operations

## API Endpoints (20 Total)

### 1. Authentication Endpoints (4 endpoints)

#### **POST /v1/auth/login** - User Login
Authenticate user with email and password, create new session.

**Authentication**: None (public endpoint)

**Request Model**: `LoginRequest`
```json
{
  "email": "user@company.com",
  "password": "SecurePassword123!"
}
```

**Response**: (200 OK) `LoginResponse`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": "2024-01-01T20:00:00Z",
  "user": {
    "id": "user_abc123def456",
    "email": "user@company.com",
    "name": "John Doe",
    "status": "active",
    "created_at": "2024-01-01T10:00:00Z",
    "updated_at": "2024-01-01T12:00:00Z",
    "last_login_at": "2024-01-01T12:00:00Z",
    "email_verified_at": "2024-01-01T10:05:00Z"
  }
}
```

**Error Responses**:
- **401 Unauthorized**: Invalid email or password
- **500 Internal Server Error**: Login system error

#### **POST /v1/auth/logout** - User Logout
Invalidate current user session.

**Authentication**: Required (Bearer token)

**Response**: (200 OK)
```json
{
  "message": "Logout successful"
}
```

**Error Responses**:
- **401 Unauthorized**: Invalid or expired token
- **500 Internal Server Error**: Logout system error

#### **POST /v1/auth/refresh** - Refresh Session
Refresh user session with new token, invalidate old token.

**Authentication**: Required (Bearer token)

**Response**: (200 OK) `LoginResponse`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": "2024-01-01T20:00:00Z",
  "user": {
    "id": "user_abc123def456",
    "email": "user@company.com",
    "name": "John Doe",
    "status": "active",
    "created_at": "2024-01-01T10:00:00Z",
    "updated_at": "2024-01-01T12:00:00Z",
    "last_login_at": "2024-01-01T12:00:00Z",
    "email_verified_at": "2024-01-01T10:05:00Z"
  }
}
```

#### **GET /v1/auth/me** - Get User Profile
Retrieve current user profile information.

**Authentication**: Required (Bearer token)

**Response**: (200 OK) `UserResponse`
```json
{
  "id": "user_abc123def456",
  "email": "user@company.com",
  "name": "John Doe",
  "status": "active",
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z",
  "last_login_at": "2024-01-01T12:00:00Z",
  "email_verified_at": "2024-01-01T10:05:00Z"
}
```

### 2. Platform Setup Endpoints (2 endpoints)

#### **POST /v1/auth/setup/init** - Initialize Platform Setup
Generate initial setup token for first platform admin creation.

**Authentication**: None (public endpoint)  
**Usage**: One-time platform initialization only

**Response**: (200 OK) `SetupTokenResponse`
```json
{
  "setup_token": "secure_random_token_32_chars",
  "expires_at": "2024-01-02T12:00:00Z"
}
```

**Error Responses**:
- **400 Bad Request**: Platform setup already completed
- **500 Internal Server Error**: Setup initialization failed

#### **POST /v1/auth/setup** - Complete Platform Setup
Complete initial platform setup by creating first admin user.

**Authentication**: None (requires setup token)

**Request Model**: `AdminSetupRequest`
```json
{
  "setup_token": "secure_random_token_32_chars",
  "email": "admin@company.com",
  "name": "Platform Administrator",
  "password": "SuperSecureAdminPass123!"
}
```

**Response**: (201 Created) `UserResponse`
```json
{
  "id": "admin_abc123def456",
  "email": "admin@company.com", 
  "name": "Platform Administrator",
  "status": "active",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z",
  "last_login_at": null,
  "email_verified_at": null
}
```

**Error Responses**:
- **400 Bad Request**: Invalid or expired setup token
- **409 Conflict**: User with email already exists
- **500 Internal Server Error**: Platform setup failed

### 3. Password Management (3 endpoints)

#### **POST /v1/auth/password/reset** - Request Password Reset
Request password reset token for user account.

**Authentication**: None (public endpoint)

**Request Model**: `PasswordResetRequest`
```json
{
  "email": "user@company.com"
}
```

**Response**: (200 OK)
```json
{
  "message": "Password reset instructions sent if email exists"
}
```

**Note**: Response is consistent regardless of email existence for security.

#### **POST /v1/auth/password/reset-confirm** - Confirm Password Reset
Confirm password reset with token and set new password.

**Authentication**: None (requires reset token)

**Request Body**:
```json
{
  "token": "password_reset_token",
  "new_password": "NewSecurePassword123!"
}
```

**Response**: (200 OK)
```json
{
  "message": "Password reset successfully"
}
```

**Error Responses**:
- **400 Bad Request**: Invalid or expired reset token, weak password
- **500 Internal Server Error**: Password reset confirmation failed

#### **POST /v1/auth/password/change** - Change Password
Change user password (requires current password).

**Authentication**: Required (Bearer token)

**Request Model**: `PasswordChangeRequest`
```json
{
  "current_password": "CurrentPassword123!",
  "new_password": "NewSecurePassword123!"
}
```

**Response**: (200 OK)
```json
{
  "message": "Password changed successfully"
}
```

**Error Responses**:
- **400 Bad Request**: Current password incorrect, weak new password
- **401 Unauthorized**: Invalid or expired token
- **500 Internal Server Error**: Password change failed

### 4. User Invitation System (3 endpoints)

#### **POST /v1/auth/invite** - Send User Invitation
Send invitation to new user for tenant access.

**Authentication**: Required (Bearer token)  
**Authorization**: Platform admins or tenant admins only

**Request Model**: `InvitationRequest`
```json
{
  "email": "newuser@company.com",
  "tenant_id": "tenant_uuid_123",
  "role": "security_analyst"
}
```

**Supported Roles**:
- **Platform Roles**: `super_admin`, `admin`, `support_admin`, `billing_admin`
- **Tenant Roles**: `tenant_admin`, `security_analyst`, `devops_engineer`, `compliance_officer`, `viewer`

**Response**: (200 OK) `InvitationResponse`
```json
{
  "invitation_id": "invite_abc123def456",
  "email": "newuser@company.com",
  "tenant_id": "tenant_uuid_123",
  "role": "security_analyst",
  "invitation_token": "secure_invitation_token",
  "expires_at": "2024-01-08T12:00:00Z",
  "invited_by": "admin_abc123def456",
  "created_at": "2024-01-01T12:00:00Z"
}
```

**Error Responses**:
- **403 Forbidden**: No permission to invite users to tenant
- **409 Conflict**: User with email already exists
- **500 Internal Server Error**: User invitation failed

#### **POST /v1/auth/accept-invite** - Accept User Invitation
Accept invitation and create user account.

**Authentication**: None (requires invitation token)

**Request Model**: `AcceptInviteRequest`
```json
{
  "invitation_token": "secure_invitation_token",
  "email": "newuser@company.com",
  "name": "New User",
  "password": "SecurePassword123!",
  "tenant_id": "tenant_uuid_123"
}
```

**Response**: (201 Created) `UserResponse`
```json
{
  "id": "user_xyz789abc123",
  "email": "newuser@company.com",
  "name": "New User",
  "status": "active",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z",
  "last_login_at": null,
  "email_verified_at": null
}
```

**Error Responses**:
- **400 Bad Request**: Invalid or expired invitation, tenant ID mismatch
- **409 Conflict**: User with email already exists
- **500 Internal Server Error**: Invitation acceptance failed

#### **POST /v1/auth/tenant-onboard** - Onboard Tenant
Platform admin creates tenant and invites admin (simplified workflow).

**Authentication**: Required (Bearer token)  
**Authorization**: Platform admins only

**Request Parameters**:
- `tenant_name` (str): Tenant organization name
- `admin_email` (str): Email for tenant admin user
- `subscription_tier` (str): Subscription tier (default: "professional")

**Response**: (200 OK) `InvitationResponse`
```json
{
  "invitation_id": "invite_def456ghi789",
  "email": "tenantadmin@newcompany.com",
  "tenant_id": "new_tenant_uuid_456",
  "role": "tenant_admin",
  "invitation_token": "tenant_admin_invitation_token",
  "expires_at": "2024-01-08T12:00:00Z",
  "invited_by": "platform_admin_id",
  "created_at": "2024-01-01T12:00:00Z"
}
```

### 5. Email Verification (2 endpoints)

#### **POST /v1/auth/verify-email** - Send Email Verification
Send email verification token to current user.

**Authentication**: Required (Bearer token)

**Response**: (200 OK)
```json
{
  "message": "Verification email sent"
}
```

**Error Responses**:
- **400 Bad Request**: Email already verified
- **401 Unauthorized**: Invalid or expired token
- **500 Internal Server Error**: Email verification failed

#### **POST /v1/auth/verify-email-confirm** - Confirm Email Verification
Confirm email verification with token.

**Authentication**: Required (Bearer token)

**Request Parameters**:
- `token` (str): Email verification token

**Response**: (200 OK)
```json
{
  "message": "Email verified successfully"
}
```

**Error Responses**:
- **400 Bad Request**: Invalid or expired verification token
- **401 Unauthorized**: Invalid or expired session token
- **500 Internal Server Error**: Email verification confirmation failed

### 6. Session Management (3 endpoints)

#### **GET /v1/auth/sessions** - List User Sessions
List all active sessions for current user.

**Authentication**: Required (Bearer token)

**Response**: (200 OK)
```json
{
  "sessions": [
    {
      "session_id": "session_abc123def456",
      "user_id": "user_abc123def456",
      "ip_address": "192.168.1.100",
      "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
      "created_at": "2024-01-01T12:00:00Z",
      "last_accessed": "2024-01-01T15:30:00Z",
      "expires_at": "2024-01-01T20:00:00Z",
      "status": "active"
    }
  ],
  "total_count": 1
}
```

#### **DELETE /v1/auth/sessions/all** - Revoke All Sessions
Revoke all user sessions except the current one.

**Authentication**: Required (Bearer token)

**Response**: (200 OK)
```json
{
  "message": "Revoked 3 sessions successfully"
}
```

#### **DELETE /v1/auth/sessions/{session_id}** - Revoke Specific Session
Revoke a specific session by ID.

**Authentication**: Required (Bearer token)

**Response**: (200 OK)
```json
{
  "message": "Session revoked successfully"
}
```

**Error Responses**:
- **404 Not Found**: Session not found or already revoked
- **500 Internal Server Error**: Session revocation failed

### 7. Account Management (2 endpoints)

#### **POST /v1/auth/deactivate** - Deactivate Account
Deactivate current user account.

**Authentication**: Required (Bearer token)

**Response**: (200 OK)
```json
{
  "message": "Account deactivated successfully"
}
```

#### **POST /v1/auth/reactivate/{user_id}** - Reactivate Account
Reactivate user account (platform admins only).

**Authentication**: Required (Bearer token)  
**Authorization**: Platform admins only

**Response**: (200 OK)
```json
{
  "message": "Account reactivated successfully"
}
```

**Error Responses**:
- **403 Forbidden**: Platform admin access required
- **404 Not Found**: User not found
- **400 Bad Request**: User is not inactive

## Data Models & Validation

### Core Request Models

#### LoginRequest
```python
class LoginRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")
```

#### AdminSetupRequest
```python
class AdminSetupRequest(BaseModel):
    setup_token: str = Field(..., description="Setup token from init endpoint")
    email: str = Field(..., description="Admin email address")
    name: str = Field(..., description="Admin full name")
    password: str = Field(..., description="Admin password")
```

#### PasswordResetRequest
```python
class PasswordResetRequest(BaseModel):
    email: str = Field(..., description="User email address")
```

#### PasswordChangeRequest
```python
class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., description="New password")
```

#### InvitationRequest
```python
class InvitationRequest(BaseModel):
    email: str = Field(..., description="Invited user email")
    tenant_id: str = Field(..., description="Target tenant ID")
    role: UserRole = Field(..., description="Role to assign")
```

#### AcceptInviteRequest
```python
class AcceptInviteRequest(BaseModel):
    invitation_token: str = Field(..., description="Invitation token")
    email: str = Field(..., description="User email (must match invitation)")
    name: str = Field(..., description="User full name")
    password: str = Field(..., description="User password")
    tenant_id: str = Field(..., description="Tenant ID")
```

### Core Response Models

#### LoginResponse
```python
class LoginResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    expires_at: datetime = Field(..., description="Token expiration time")
    user: UserResponse = Field(..., description="User information")
```

#### UserResponse
```python
class UserResponse(BaseModel):
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    name: str = Field(..., description="User full name")
    status: UserStatus = Field(..., description="User status")
    created_at: datetime = Field(..., description="Account creation time")
    updated_at: datetime = Field(..., description="Last update time")
    last_login_at: Optional[datetime] = Field(None, description="Last login time")
    email_verified_at: Optional[datetime] = Field(None, description="Email verification time")
```

#### SetupTokenResponse
```python
class SetupTokenResponse(BaseModel):
    setup_token: str = Field(..., description="Setup token")
    expires_at: datetime = Field(..., description="Token expiration time")
```

#### InvitationResponse
```python
class InvitationResponse(BaseModel):
    invitation_id: str = Field(..., description="Invitation ID")
    email: str = Field(..., description="Invited email")
    tenant_id: str = Field(..., description="Target tenant ID")
    role: UserRole = Field(..., description="Assigned role")
    invitation_token: str = Field(..., description="Invitation token")
    expires_at: datetime = Field(..., description="Invitation expiration")
    invited_by: str = Field(..., description="Inviting user ID")
    created_at: datetime = Field(..., description="Invitation creation time")
```

### User Roles & Status

#### UserRole Enum
```python
class UserRole(str, Enum):
    # Platform Roles (tenant_id = "platform")
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    SUPPORT_ADMIN = "support_admin"
    BILLING_ADMIN = "billing_admin"
    
    # Tenant Roles
    TENANT_ADMIN = "tenant_admin"
    SECURITY_ANALYST = "security_analyst"
    DEVOPS_ENGINEER = "devops_engineer"
    COMPLIANCE_OFFICER = "compliance_officer"
    VIEWER = "viewer"
```

#### UserStatus Enum
```python
class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    SUSPENDED = "suspended"
```

### Password Validation

#### Security Requirements
- **Minimum Length**: 12 characters
- **Character Requirements**:
  - At least one uppercase letter (A-Z)
  - At least one lowercase letter (a-z)
  - At least one number (0-9)
  - At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?~`)
- **Dictionary Check**: Not in common weak passwords list
- **Hashing**: bcrypt with 12 rounds

#### Validation Function
```python
def validate_password_strength(password: str) -> None:
    """
    Validate password meets security requirements
    
    Raises:
        ValueError: If password doesn't meet requirements
    """
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters long")
    
    if not any(c.isupper() for c in password):
        raise ValueError("Password must contain at least one uppercase letter")
    
    if not any(c.islower() for c in password):
        raise ValueError("Password must contain at least one lowercase letter")
    
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one number")
    
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?~`" for c in password):
        raise ValueError("Password must contain at least one special character")
    
    # Check against common weak passwords
    weak_passwords = {
        'password123!', 'password123@', 'welcome123!', 'letmein123!', 
        'changeme123!', 'p@ssw0rd123', 'P@ssw0rd123', 'admin123456!'
    }
    if password.lower() in {pwd.lower() for pwd in weak_passwords}:
        raise ValueError("Password is too common. Please choose a more unique password")
```

## Authentication & Authorization

### JWT Token Structure

**Token Payload**:
```json
{
  "user_id": "user_abc123def456",
  "iat": 1704110400,
  "exp": 1704139200,
  "type": "access_token"
}
```

**Token Configuration**:
- **Algorithm**: HS256 (HMAC SHA-256)
- **Expiry**: 8 hours (configurable via `SESSION_EXPIRY_HOURS`)
- **Secret**: Environment variable `JWT_SECRET`

### Role-Based Access Control

#### Permission System
Permissions follow the format: `resource:action:scope`

**Examples**:
- `users:read:tenant` - Read users in current tenant
- `users:write:tenant` - Create/update users in current tenant
- `platform:admin:platform` - Platform administration access
- `security:*:tenant` - All security operations in tenant

#### Role Permissions Matrix

| Role | Scope | Permissions |
|------|-------|-------------|
| **super_admin** | Platform | `*:*:*` (all permissions) |
| **admin** | Platform | `tenants:*`, `users:read`, `billing:read` |
| **support_admin** | Platform | `support:*`, `users:read,write`, `audit:read` |
| **billing_admin** | Platform | `billing:*`, `usage:read`, `reports:generate` |
| **tenant_admin** | Tenant | `logs:*`, `alerts:*`, `users:*`, `settings:*` |
| **security_analyst** | Tenant | `security:*`, `logs:read,search`, `alerts:read,investigate` |
| **devops_engineer** | Tenant | `logs:read,search`, `alerts:*`, `dashboards:*` |
| **compliance_officer** | Tenant | `compliance:*`, `audit:read`, `reports:generate` |
| **viewer** | Tenant | `logs:read`, `dashboards:read`, `alerts:read:own` |

### Tenant Context

#### Multi-Tenant Architecture
- **Platform Tenant**: `tenant_id = "platform"` for platform-wide operations
- **Customer Tenants**: UUID-based tenant IDs for customer isolation
- **Header Requirement**: `X-Customer-ID` header for tenant context
- **Cross-Tenant Access**: Platform admins can access any tenant

#### Tenant Validation
```python
async def validate_tenant_access(user_id: str, tenant_id: str) -> List[Dict[str, Any]]:
    """Validate user has access to tenant and return roles"""
    user_roles = await user_service.get_user_tenant_roles(user_id, tenant_id)
    
    if not user_roles:
        # Check if user has platform admin role (cross-tenant access)
        platform_roles = await user_service.get_user_tenant_roles(user_id, "platform")
        if not platform_roles:
            raise HTTPException(403, f"No access to tenant: {tenant_id}")
        return platform_roles
    
    return user_roles
```

## Integration Examples

### Python SDK Integration

```python
import httpx
import asyncio
from datetime import datetime
import json

class LogforgeAuthClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.token = None
        self.headers = {"Content-Type": "application/json"}
    
    async def login(self, email: str, password: str) -> dict:
        """Login and store access token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/auth/login",
                json={"email": email, "password": password},
                headers=self.headers
            )
            response.raise_for_status()
            
            data = response.json()
            self.token = data["access_token"]
            self.headers["Authorization"] = f"Bearer {self.token}"
            
            return data
    
    async def get_profile(self) -> dict:
        """Get current user profile"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v1/auth/me",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def change_password(self, current_password: str, new_password: str) -> dict:
        """Change user password"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/auth/password/change",
                json={
                    "current_password": current_password,
                    "new_password": new_password
                },
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def invite_user(self, email: str, tenant_id: str, role: str) -> dict:
        """Invite new user to tenant"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/auth/invite",
                json={
                    "email": email,
                    "tenant_id": tenant_id,
                    "role": role
                },
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def list_sessions(self) -> dict:
        """List all user sessions"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v1/auth/sessions",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def logout(self) -> dict:
        """Logout and invalidate session"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/auth/logout",
                headers=self.headers
            )
            response.raise_for_status()
            
            # Clear stored token
            self.token = None
            self.headers.pop("Authorization", None)
            
            return response.json()

# Usage Example
async def main():
    client = LogforgeAuthClient("http://localhost:7080")
    
    try:
        # Login
        login_result = await client.login(
            "user@company.com", 
            "SecurePassword123!"
        )
        print(f"Login successful. Token expires at: {login_result['expires_at']}")
        
        # Get profile
        profile = await client.get_profile()
        print(f"User: {profile['name']} ({profile['email']})")
        
        # List sessions
        sessions = await client.list_sessions()
        print(f"Active sessions: {sessions['total_count']}")
        
        # Invite user (if admin)
        try:
            invitation = await client.invite_user(
                "newuser@company.com",
                "tenant_uuid_123",
                "security_analyst"
            )
            print(f"Invitation sent: {invitation['invitation_id']}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                print("No permission to invite users")
        
        # Logout
        await client.logout()
        print("Logout successful")
        
    except httpx.HTTPStatusError as e:
        print(f"API Error {e.response.status_code}: {e.response.text}")
    except Exception as e:
        print(f"Error: {e}")

# Run the example
asyncio.run(main())
```

### JavaScript/Node.js Integration

```javascript
const axios = require('axios');

class LogforgeAuthClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
    this.token = null;
    this.headers = {
      'Content-Type': 'application/json'
    };
  }

  async login(email, password) {
    try {
      const response = await axios.post(
        `${this.baseUrl}/v1/auth/login`,
        { email, password },
        { headers: this.headers }
      );
      
      this.token = response.data.access_token;
      this.headers['Authorization'] = `Bearer ${this.token}`;
      
      return response.data;
    } catch (error) {
      throw new Error(`Login failed: ${error.response?.data?.error || error.message}`);
    }
  }

  async setupPlatform(adminEmail, adminName, adminPassword) {
    try {
      // Step 1: Initialize setup
      const initResponse = await axios.post(
        `${this.baseUrl}/v1/auth/setup/init`,
        {},
        { headers: this.headers }
      );
      
      const setupToken = initResponse.data.setup_token;
      
      // Step 2: Complete setup
      const setupResponse = await axios.post(
        `${this.baseUrl}/v1/auth/setup`,
        {
          setup_token: setupToken,
          email: adminEmail,
          name: adminName,
          password: adminPassword
        },
        { headers: this.headers }
      );
      
      return setupResponse.data;
    } catch (error) {
      throw new Error(`Platform setup failed: ${error.response?.data?.error || error.message}`);
    }
  }

  async refreshSession() {
    try {
      const response = await axios.post(
        `${this.baseUrl}/v1/auth/refresh`,
        {},
        { headers: this.headers }
      );
      
      this.token = response.data.access_token;
      this.headers['Authorization'] = `Bearer ${this.token}`;
      
      return response.data;
    } catch (error) {
      throw new Error(`Session refresh failed: ${error.response?.data?.error || error.message}`);
    }
  }

  async acceptInvitation(invitationToken, email, name, password, tenantId) {
    try {
      const response = await axios.post(
        `${this.baseUrl}/v1/auth/accept-invite`,
        {
          invitation_token: invitationToken,
          email,
          name,
          password,
          tenant_id: tenantId
        },
        { headers: this.headers }
      );
      
      return response.data;
    } catch (error) {
      throw new Error(`Invitation acceptance failed: ${error.response?.data?.error || error.message}`);
    }
  }

  async requestPasswordReset(email) {
    try {
      const response = await axios.post(
        `${this.baseUrl}/v1/auth/password/reset`,
        { email },
        { headers: this.headers }
      );
      
      return response.data;
    } catch (error) {
      throw new Error(`Password reset request failed: ${error.response?.data?.error || error.message}`);
    }
  }

  async revokeAllSessions() {
    try {
      const response = await axios.delete(
        `${this.baseUrl}/v1/auth/sessions/all`,
        { headers: this.headers }
      );
      
      return response.data;
    } catch (error) {
      throw new Error(`Session revocation failed: ${error.response?.data?.error || error.message}`);
    }
  }
}

// Usage Example
async function demonstrateAuthFlow() {
  const client = new LogforgeAuthClient('http://localhost:7080');

  try {
    // Platform setup (one-time)
    console.log('Setting up platform...');
    const admin = await client.setupPlatform(
      'admin@company.com',
      'Platform Administrator',
      'SuperSecureAdminPass123!'
    );
    console.log(`Platform admin created: ${admin.id}`);

    // Login as admin
    console.log('Logging in as admin...');
    const loginResult = await client.login(
      'admin@company.com',
      'SuperSecureAdminPass123!'
    );
    console.log(`Login successful. Token expires: ${loginResult.expires_at}`);

    // Refresh session before expiry
    console.log('Refreshing session...');
    const refreshResult = await client.refreshSession();
    console.log(`Session refreshed. New expiry: ${refreshResult.expires_at}`);

    // Security: Revoke all other sessions
    console.log('Revoking all other sessions...');
    const revokeResult = await client.revokeAllSessions();
    console.log(revokeResult.message);

  } catch (error) {
    console.error('Authentication flow error:', error.message);
  }
}

// Run the demonstration
demonstrateAuthFlow();
```

### cURL Examples

**Login**:
```bash
curl -X POST "http://localhost:7080/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@company.com",
    "password": "SecurePassword123!"
  }'
```

**Get Profile**:
```bash
curl -X GET "http://localhost:7080/v1/auth/me" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Change Password**:
```bash
curl -X POST "http://localhost:7080/v1/auth/password/change" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "OldPassword123!",
    "new_password": "NewSecurePassword123!"
  }'
```

**Invite User**:
```bash
curl -X POST "http://localhost:7080/v1/auth/invite" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@company.com",
    "tenant_id": "tenant_uuid_123",
    "role": "security_analyst"
  }'
```

**Accept Invitation**:
```bash
curl -X POST "http://localhost:7080/v1/auth/accept-invite" \
  -H "Content-Type: application/json" \
  -d '{
    "invitation_token": "secure_invitation_token",
    "email": "newuser@company.com",
    "name": "New User",
    "password": "SecurePassword123!",
    "tenant_id": "tenant_uuid_123"
  }'
```

**Platform Setup (One-time)**:
```bash
# Step 1: Initialize setup
curl -X POST "http://localhost:7080/v1/auth/setup/init"

# Step 2: Complete setup with token
curl -X POST "http://localhost:7080/v1/auth/setup" \
  -H "Content-Type: application/json" \
  -d '{
    "setup_token": "setup_token_from_step_1",
    "email": "admin@company.com",
    "name": "Platform Administrator",
    "password": "SuperSecureAdminPass123!"
  }'
```

## Error Handling

### HTTP Status Codes

- **200 OK**: Successful operation
- **201 Created**: Resource created (user, invitation)
- **400 Bad Request**: Invalid request data, validation errors
- **401 Unauthorized**: Invalid or expired token, wrong credentials
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: User, session, or resource not found
- **409 Conflict**: User already exists, duplicate email
- **500 Internal Server Error**: Server-side processing error

### Error Response Format

```json
{
  "error": "Detailed error message"
}
```

### Common Error Scenarios

#### Authentication Errors
```json
{
  "error": "Invalid email or password"
}
```

#### Token Errors
```json
{
  "error": "Invalid or expired session"
}
```

#### Permission Errors
```json
{
  "error": "No permission to invite users to tenant tenant_uuid_123"
}
```

#### Validation Errors
```json
{
  "error": "Password must be at least 12 characters long"
}
```

#### Conflict Errors
```json
{
  "error": "User with email user@company.com already exists"
}
```

### Error Handling Best Practices

```python
async def handle_auth_errors(api_call):
    """Error handling wrapper for auth API calls"""
    try:
        return await api_call()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            # Token expired or invalid - need to re-login
            print("Authentication required - please login again")
        elif e.response.status_code == 403:
            # Insufficient permissions
            print("Access denied - insufficient permissions")
        elif e.response.status_code == 409:
            # Conflict (user already exists)
            error_detail = e.response.json().get("error", "Conflict error")
            print(f"Conflict: {error_detail}")
        elif e.response.status_code == 400:
            # Validation error
            error_detail = e.response.json().get("error", "Validation error")
            print(f"Validation error: {error_detail}")
        else:
            print(f"API error {e.response.status_code}: {e.response.text}")
        raise
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise
```

## Security Considerations

### Password Security
1. **Strong Requirements**: 12+ character minimum with character type requirements
2. **Dictionary Protection**: Common weak passwords blocked
3. **Secure Hashing**: bcrypt with 12 rounds (industry standard)
4. **Reset Tokens**: Secure, time-limited password reset tokens
5. **Change Validation**: Current password required for changes

### Session Security
1. **JWT Standards**: Secure token generation with HMAC SHA-256
2. **Configurable Expiry**: Default 8-hour session timeout
3. **Token Rotation**: Refresh tokens invalidate old tokens
4. **Session Management**: Multiple session support with selective revocation
5. **Audit Trail**: Complete session activity logging

### Multi-Tenant Security
1. **Tenant Isolation**: Complete data separation by tenant_id
2. **Role-Based Access**: Granular permissions per tenant
3. **Cross-Tenant Controls**: Platform admins can access any tenant
4. **Header Validation**: X-Customer-ID header verification
5. **Permission Checking**: Real-time permission validation

### Platform Security
1. **Setup Protection**: One-time setup token for initial admin creation
2. **Invitation System**: Secure token-based user onboarding
3. **Email Verification**: Optional email verification workflow
4. **Account Management**: Secure activation/deactivation flows
5. **Audit Logging**: Complete audit trail for all operations

## Performance Characteristics

### Response Times
- **Login**: ~100-300ms (includes password verification and session creation)
- **Token Validation**: ~25-50ms (JWT verification and database lookup)
- **Profile Retrieval**: ~50-100ms (single database query)
- **Password Operations**: ~200-500ms (bcrypt hashing overhead)
- **Session Management**: ~50-150ms (database operations)
- **Invitation Operations**: ~100-250ms (token generation and persistence)

### Scalability Features
- **Stateless Authentication**: JWT tokens enable horizontal scaling
- **Database Optimization**: Indexed queries for user and session lookups
- **Connection Pooling**: Efficient database connection management
- **Async Processing**: Non-blocking I/O for all operations
- **Caching Strategy**: Session validation caching for high-frequency operations

## Best Practices

### For Developers

1. **Token Management**: Always store tokens securely, never in local storage
2. **Error Handling**: Implement comprehensive error handling for all scenarios
3. **Token Refresh**: Implement automatic token refresh before expiry
4. **Logout Handling**: Always call logout endpoint to invalidate sessions
5. **Password Validation**: Validate passwords client-side before submission
6. **Multi-Session Support**: Handle multiple active sessions gracefully
7. **Rate Limiting**: Implement client-side rate limiting for auth operations

### For Operations Teams

1. **Security Monitoring**: Monitor failed login attempts and suspicious activity
2. **Session Management**: Regular cleanup of expired sessions
3. **Password Policies**: Enforce strong password requirements
4. **Access Reviews**: Regular review of user roles and permissions
5. **Audit Logging**: Monitor all authentication and authorization events
6. **Backup Procedures**: Secure backup of user and session data
7. **Incident Response**: Procedures for compromised accounts and mass session revocation

### For Security Teams

1. **Multi-Factor Authentication**: Plan for MFA integration
2. **Password Rotation**: Encourage regular password updates
3. **Session Timeouts**: Configure appropriate session expiry times
4. **Role Separation**: Implement principle of least privilege
5. **Audit Trails**: Complete logging of all authentication events
6. **Penetration Testing**: Regular security testing of auth endpoints
7. **Compliance**: Ensure compliance with security standards (SOC 2, ISO 27001)

The Auth Router API provides enterprise-grade authentication and authorization services with comprehensive security features, role-based access control, and multi-tenant isolation to ensure secure access to the Logforge platform.