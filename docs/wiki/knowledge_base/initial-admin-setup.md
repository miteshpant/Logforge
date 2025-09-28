# Initial Admin Setup - Logforge Platform

## Overview
This document explains how to set up the first super administrator user for the Logforge platform. This initial setup is required before the Admin UI can be used and is a one-time process that creates the foundation for platform administration.

## Prerequisites
- Logforge API server running on port 7080
- Docker Compose services started (`docker compose -f infra/docker/compose.yml up -d`)
- ClickHouse database accessible
- No existing super admin users (fresh installation)

## Setup Process

### Step 1: Check Setup Availability
First, verify that initial setup is available and no super admin users exist:

```bash
curl -X POST http://localhost:7080/v1/auth/setup/init
```

**Expected Response:**
```json
{
  "setup_token": "1OEyFmdyBJah9eD-BQZsiIzJVrHU6FP9ih_XdxO_63s",
  "expires_at": "2025-09-22T04:54:39.761099"
}
```

**If Setup Already Completed:**
```json
{
  "detail": "Platform setup already completed"
}
```

### Step 2: Create Initial Super Admin User
Use the setup token from Step 1 to create the first super administrator:

```bash
curl -X POST http://localhost:7080/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{
    "setup_token": "YOUR_SETUP_TOKEN_HERE",
    "email": "admin@mrlogsec.com",
    "name": "Platform Administrator",
    "password": "SecureAdmin123!"
  }'
```

**Expected Response:**
```json
{
  "id": "a78a4bf1-6d0e-497c-8def-7bb397b177ef",
  "email": "admin@mrlogsec.com",
  "name": "Platform Administrator", 
  "status": "active",
  "created_at": "2025-09-21T04:54:45",
  "updated_at": "2025-09-21T04:54:45",
  "last_login_at": null,
  "email_verified_at": null
}
```

### Step 3: Verify Super Admin Login
Test that the newly created admin user can log in:

```bash
curl -X POST http://localhost:7080/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@mrlogsec.com",
    "password": "SecureAdmin123!"
  }'
```

**Expected Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": "2025-09-21T12:54:49.896707",
  "user": {
    "id": "a78a4bf1-6d0e-497c-8def-7bb397b177ef",
    "email": "admin@mrlogsec.com",
    "name": "Platform Administrator",
    "status": "active",
    "created_at": "2025-09-21T04:54:45",
    "updated_at": "2025-09-21T04:54:45",
    "last_login_at": "2025-09-21T04:54:49.896602Z",
    "email_verified_at": null
  }
}
```

## Admin UI Access

### Logging into Admin UI
1. Navigate to `http://localhost:3002` (Admin UI)
2. Use the credentials created in Step 2:
   - **Email:** `admin@mrlogsec.com`
   - **Password:** `SecureAdmin123!`
3. Click "Login"
4. You will be redirected to the Admin Dashboard

### Admin UI Capabilities
Once logged in, the super admin can:
- **Platform Health Monitoring:** View system health, uptime, and service status
- **Tenant Management:** Create, update, and manage customer tenants
- **Usage Analytics:** Monitor platform usage and billing data
- **Admin User Management:** Create additional admin users
- **Billing & Subscriptions:** Manage customer subscriptions and billing
- **Feature Management:** Configure feature availability
- **Support & Tickets:** Handle customer support requests

## Security Considerations

### Password Requirements
- Minimum 12 characters
- Must contain uppercase, lowercase, numbers, and special characters
- Cannot be a common dictionary word

### Best Practices
1. **Use Strong Passwords:** Never use default or weak passwords
2. **Limit Super Admin Users:** Only create necessary super admin accounts
3. **Regular Token Rotation:** Access tokens expire after 8 hours
4. **Audit Trail:** All admin actions are logged for security auditing
5. **Multi-Factor Authentication:** Enable MFA for production environments

## Role Hierarchy

### Platform Roles
- **super_admin:** Full platform access, can manage all tenants and users
- **admin:** Platform operations, limited tenant management
- **support_admin:** Customer support access, read-only tenant data
- **billing_admin:** Billing and subscription management only

### Tenant Roles (Assigned by Platform Admins)
- **tenant_admin:** Full access within their organization
- **security_analyst:** Security monitoring and threat detection
- **devops_engineer:** Infrastructure and application monitoring
- **compliance_officer:** Compliance reporting and audit access
- **viewer:** Read-only access to dashboards and reports

## Troubleshooting

### Setup Token Expired
If setup token expires before completion:
```bash
# Generate new setup token
curl -X POST http://localhost:7080/v1/auth/setup/init
```

### Login Failures
1. **Invalid Credentials:** Verify email and password match exactly
2. **User Not Active:** Check user status in database
3. **Token Issues:** Ensure API server is running and accessible

### Database Connection Issues
1. **ClickHouse Not Running:** Start services with `docker compose up -d`
2. **Permission Errors:** Check database permissions and service keys
3. **Table Schema:** Ensure database tables are initialized

### API Access Issues
```bash
# Test basic health endpoint
curl http://localhost:7080/health

# Test with authentication
curl -H "Authorization: Bearer YOUR_TOKEN" \
     -H "X-Customer-ID: platform" \
     http://localhost:7080/v1/tenants
```

## Database Details

### User Storage
- **Table:** `users_mt` (multi-tenant users table)
- **Role Assignment:** `user_tenant_roles_mt` table
- **Platform Context:** Super admins have `tenant_id: "platform"`
- **Session Management:** `user_sessions_mt` table

### Role Assignment Process
1. User created in `users_mt`
2. Platform role assigned in `user_tenant_roles_mt`
3. Role verification during authentication
4. Platform-wide access granted for super_admin role

## Next Steps

After completing initial setup:

1. **Configure Platform Settings:** Review health monitoring and alerting
2. **Create Additional Admins:** Use Admin UI to create support and billing admins
3. **Onboard First Tenant:** Create test tenant for validation
4. **Setup Monitoring:** Configure platform health alerts
5. **Security Hardening:** Enable production security features

## API Endpoints Reference

### Authentication Endpoints
- `POST /v1/auth/setup/init` - Generate setup token
- `POST /v1/auth/setup` - Complete initial setup
- `POST /v1/auth/login` - User login
- `POST /v1/auth/logout` - User logout

### Admin Management Endpoints  
- `GET /v1/admin/users` - List admin users
- `POST /v1/admin/users` - Create admin user
- `PUT /v1/admin/users/{id}` - Update admin user
- `DELETE /v1/admin/users/{id}` - Delete admin user

### Platform Monitoring Endpoints
- `GET /health` - Basic system health
- `GET /health/detailed` - Detailed health metrics (requires auth)
- `GET /v1/tenants` - List all tenants (platform admin only)
- `GET /v1/analytics/usage-trends` - Platform usage analytics (platform admin only)

## Conclusion

The initial admin setup creates the foundation for Logforge platform administration. This one-time process establishes the first super administrator who can then manage the entire platform, create additional admin users, and onboard customer tenants.

For ongoing platform management, refer to the Admin UI user stories and operational documentation.