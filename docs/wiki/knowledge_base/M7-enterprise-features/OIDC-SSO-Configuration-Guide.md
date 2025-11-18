# OIDC/SSO Configuration Guide

## Overview

OpenID Connect (OIDC) Single Sign-On (SSO) allows your organization's employees to log into Logforge using their existing corporate identity provider (Okta, Auth0, Azure AD, Google Workspace, etc.) instead of creating separate Logforge accounts.

**Benefits:**
- **Centralized Authentication**: Employees use their company credentials
- **Enhanced Security**: Leverage your existing MFA and security policies
- **Simplified User Management**: No need to create/delete Logforge accounts separately
- **Audit Trail**: All authentication events tracked in your IdP

---

## How It Works

### Authentication Flow

```
1. User clicks "Sign in with SSO" on Logforge login page
   ↓
2. User redirected to your company's IdP (e.g., Okta)
   ↓
3. User authenticates with company credentials + MFA
   ↓
4. IdP sends authentication token back to Logforge
   ↓
5. Logforge validates token and creates/updates user session
   ↓
6. User logged into Logforge
```

### Security Model

**IMPORTANT SECURITY NOTES:**

1. **Client Secret Storage**: The `client_secret` is encrypted at rest in our database using AES-256 encryption
2. **Secrets Rotation**: Supports rotating secrets without downtime
3. **Access Control**: Only tenant administrators can configure OIDC
4. **Audit Logging**: All OIDC configuration changes are logged

---

## Supported Identity Providers

| Provider | Type | Documentation |
|----------|------|---------------|
| **Okta** | `okta` | [Okta OIDC Setup](#okta-setup) |
| **Auth0** | `auth0` | [Auth0 OIDC Setup](#auth0-setup) |
| **Azure AD** | `azure` | [Azure AD Setup](#azure-ad-setup) |
| **Google Workspace** | `google` | [Google Workspace Setup](#google-setup) |
| **Keycloak** | `keycloak` | [Keycloak Setup](#keycloak-setup) |
| **Generic OIDC** | `generic` | [Generic OIDC Setup](#generic-oidc-setup) |

---

## Initial Setup (One-Time Configuration)

### Step 1: Configure Your Identity Provider

Before configuring Logforge, you need to register Logforge as an application in your IdP.

**What you'll need from your IdP:**
- Client ID
- Client Secret
- Domain/Issuer URL
- Authorization/Token endpoints (for generic OIDC)

### Step 2: Configure Logforge

#### Option A: Using the Web UI (Recommended)

1. Log into Logforge as a tenant administrator
2. Navigate to **Settings** → **Enterprise** → **Authentication**
3. Click **Configure SSO/OIDC**
4. Fill in the configuration form:
   - **Provider Name**: "Acme Corporation Okta"
   - **Provider Type**: Select from dropdown (okta, auth0, etc.)
   - **Client ID**: Paste from your IdP
   - **Client Secret**: Paste from your IdP (encrypted on save)
   - **Domain**: Your IdP domain (e.g., `acme.okta.com`)
   - **Scopes**: Default: `openid profile email`
   - **Enabled**: Toggle ON

5. Click **Test Connection** to verify
6. Click **Save Configuration**

#### Option B: Using the API

```bash
curl -X POST https://api.logforge.io/v1/enterprise/auth/oidc/configure \
  -H "Content-Type: application/json" \
  -H "X-Customer-ID: your-tenant-id" \
  -H "Authorization: Bearer your-admin-token" \
  -d '{
    "provider_name": "Acme Corporation Okta",
    "provider_type": "okta",
    "client_id": "0oa1234567890abcdef",
    "client_secret": "YOUR_CLIENT_SECRET_HERE",
    "domain": "acme.okta.com",
    "scopes": ["openid", "profile", "email"],
    "enabled": true
  }'
```

**Response:**
```json
{
  "status": "success",
  "provider_id": "oidc_provider_abc123",
  "provider_name": "Acme Corporation Okta",
  "enabled": true,
  "created_at": "2025-11-15T10:30:00Z",
  "redirect_uri": "https://app.logforge.io/auth/callback",
  "message": "OIDC provider configured successfully. Add this redirect URI to your IdP configuration."
}
```

### Step 3: Update Your IdP Configuration

Add the **redirect_uri** from the response to your IdP's allowed callback URLs:
- **Redirect URI**: `https://app.logforge.io/auth/callback`

---

## Provider-Specific Setup Guides

### Okta Setup

#### In Okta Admin Console:

1. Navigate to **Applications** → **Applications**
2. Click **Create App Integration**
3. Select **OIDC - OpenID Connect**
4. Select **Web Application**
5. Configure:
   - **App integration name**: "Logforge"
   - **Grant type**: Authorization Code
   - **Sign-in redirect URIs**: `https://app.logforge.io/auth/callback`
   - **Sign-out redirect URIs**: `https://app.logforge.io/logout`
   - **Assignments**: Select which users/groups can access

6. Click **Save**
7. Copy **Client ID** and **Client Secret**

#### In Logforge:

```json
{
  "provider_name": "Acme Okta Production",
  "provider_type": "okta",
  "client_id": "0oa1234567890abcdef",
  "client_secret": "xxxxxxxxxxxxxxxxxxxx",
  "domain": "acme.okta.com",
  "scopes": ["openid", "profile", "email", "groups"],
  "enabled": true
}
```

---

### Auth0 Setup

#### In Auth0 Dashboard:

1. Navigate to **Applications** → **Applications**
2. Click **Create Application**
3. Select **Regular Web Applications**
4. Configure:
   - **Name**: "Logforge"
   - **Allowed Callback URLs**: `https://app.logforge.io/auth/callback`
   - **Allowed Logout URLs**: `https://app.logforge.io/logout`
   - **Allowed Web Origins**: `https://app.logforge.io`

5. Copy **Client ID**, **Client Secret**, and **Domain**

#### In Logforge:

```json
{
  "provider_name": "Acme Auth0",
  "provider_type": "auth0",
  "client_id": "abc123xyz",
  "client_secret": "xxxxxxxxxxxxxxxxxxxx",
  "domain": "acme.us.auth0.com",
  "scopes": ["openid", "profile", "email"],
  "enabled": true
}
```

---

### Azure AD Setup

#### In Azure Portal:

1. Navigate to **Azure Active Directory** → **App registrations**
2. Click **New registration**
3. Configure:
   - **Name**: "Logforge"
   - **Supported account types**: Accounts in this organizational directory only
   - **Redirect URI**: Web - `https://app.logforge.io/auth/callback`

4. After creation:
   - Copy **Application (client) ID**
   - Go to **Certificates & secrets** → **New client secret**
   - Copy the secret value (shown only once)
   - Go to **Endpoints** to find your domain

#### In Logforge:

```json
{
  "provider_name": "Acme Azure AD",
  "provider_type": "azure",
  "client_id": "12345678-1234-1234-1234-123456789012",
  "client_secret": "xxxxxxxxxxxxxxxxxxxx",
  "domain": "login.microsoftonline.com/your-tenant-id",
  "scopes": ["openid", "profile", "email"],
  "enabled": true
}
```

---

### Google Workspace Setup

#### In Google Cloud Console:

1. Navigate to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth 2.0 Client ID**
3. Configure:
   - **Application type**: Web application
   - **Name**: "Logforge"
   - **Authorized redirect URIs**: `https://app.logforge.io/auth/callback`

4. Copy **Client ID** and **Client Secret**

#### In Logforge:

```json
{
  "provider_name": "Acme Google Workspace",
  "provider_type": "google",
  "client_id": "123456789012-abcdefghijklmnop.apps.googleusercontent.com",
  "client_secret": "xxxxxxxxxxxxxxxxxxxx",
  "domain": "accounts.google.com",
  "scopes": ["openid", "profile", "email"],
  "enabled": true
}
```

---

## Managing OIDC Configuration

### View All Configured Providers

```bash
curl -X GET https://api.logforge.io/v1/enterprise/auth/providers \
  -H "X-Customer-ID: your-tenant-id" \
  -H "Authorization: Bearer your-admin-token"
```

**Response:**
```json
{
  "providers": [
    {
      "provider_id": "oidc_provider_abc123",
      "provider_name": "Acme Corporation Okta",
      "provider_type": "okta",
      "domain": "acme.okta.com",
      "enabled": true,
      "created_at": "2025-11-15T10:30:00Z",
      "last_used": "2025-11-15T14:22:33Z",
      "user_count": 245
    }
  ]
}
```

### Update OIDC Configuration

**When to update:**
- Rotating client secret (recommended quarterly)
- Changing scopes
- Enabling/disabling the provider
- Updating domain (during migration)

```bash
curl -X PUT https://api.logforge.io/v1/enterprise/auth/oidc/{provider_id} \
  -H "Content-Type: application/json" \
  -H "X-Customer-ID: your-tenant-id" \
  -H "Authorization: Bearer your-admin-token" \
  -d '{
    "client_secret": "NEW_CLIENT_SECRET_HERE",
    "enabled": true
  }'
```

### Delete/Disable OIDC Provider

**Option 1: Disable (Recommended)**
```bash
curl -X PUT https://api.logforge.io/v1/enterprise/auth/oidc/{provider_id} \
  -H "Content-Type: application/json" \
  -H "X-Customer-ID: your-tenant-id" \
  -H "Authorization: Bearer your-admin-token" \
  -d '{"enabled": false}'
```

**Option 2: Delete (Permanent)**
```bash
curl -X DELETE https://api.logforge.io/v1/enterprise/auth/oidc/{provider_id} \
  -H "X-Customer-ID: your-tenant-id" \
  -H "Authorization: Bearer your-admin-token"
```

---

## Security Best Practices

### Client Secret Management

#### ❌ **What NOT to Do:**
- Store client secret in version control
- Share client secret via email or Slack
- Use the same secret across environments
- Never rotate secrets

#### ✅ **What TO Do:**
- Use environment-specific secrets (dev, staging, prod)
- Rotate secrets quarterly (or after employee departure)
- Store secrets in a secret manager (e.g., AWS Secrets Manager, HashiCorp Vault)
- Use API to update secrets programmatically

#### Secret Rotation Process (Zero Downtime)

1. **In your IdP**: Generate a new client secret (keep old one active)
2. **In Logforge**: Update to new secret via API
3. **Test**: Verify SSO login works with new secret
4. **In your IdP**: Deactivate old secret after 24 hours

```bash
# Step 2: Update Logforge with new secret
curl -X PUT https://api.logforge.io/v1/enterprise/auth/oidc/{provider_id} \
  -H "Content-Type: application/json" \
  -H "X-Customer-ID: your-tenant-id" \
  -H "Authorization: Bearer your-admin-token" \
  -d '{
    "client_secret": "NEW_SECRET_GENERATED_IN_IDP"
  }'
```

### Encryption at Rest

Logforge encrypts all OIDC client secrets using:
- **Algorithm**: AES-256-GCM
- **Key Management**: AWS KMS / Hardware Security Module (HSM)
- **Rotation**: Encryption keys rotated automatically every 90 days
- **Access Control**: Secrets only accessible by authentication service

### Network Security

- All OIDC communication uses TLS 1.3
- Certificate pinning for IdP connections
- IP whitelisting available for API access

---

## User Provisioning

### Just-In-Time (JIT) Provisioning

When a user logs in via SSO for the first time:
1. Logforge automatically creates a user account
2. User attributes synced from IdP (name, email, groups)
3. Default role assigned based on group mapping

### Group-to-Role Mapping

Map your IdP groups to Logforge roles:

```bash
curl -X POST https://api.logforge.io/v1/enterprise/auth/oidc/{provider_id}/group-mapping \
  -H "Content-Type: application/json" \
  -H "X-Customer-ID: your-tenant-id" \
  -H "Authorization: Bearer your-admin-token" \
  -d '{
    "mappings": [
      {
        "idp_group": "Logforge-Admins",
        "logforge_role": "admin"
      },
      {
        "idp_group": "Logforge-Developers",
        "logforge_role": "developer"
      },
      {
        "idp_group": "Logforge-Viewers",
        "logforge_role": "viewer"
      }
    ],
    "default_role": "viewer"
  }'
```

### User Deprovisioning

When a user is removed from your IdP:
- **Immediate**: User cannot log in via SSO
- **After 24 hours**: User session invalidated in Logforge
- **After 7 days**: User account deactivated (audit trail preserved)

---

## Troubleshooting

### Common Issues

#### Issue: "Invalid redirect URI"
**Cause**: Redirect URI in IdP doesn't match Logforge's callback URL

**Solution**: Ensure these URLs match exactly:
- IdP: `https://app.logforge.io/auth/callback`
- No trailing slash
- HTTPS only

#### Issue: "Invalid client secret"
**Cause**: Secret was rotated in IdP but not updated in Logforge

**Solution**: Update Logforge configuration with new secret

#### Issue: "User not authorized"
**Cause**: User/group not assigned to Logforge application in IdP

**Solution**: In your IdP, assign user/group to the Logforge application

#### Issue: "Missing required scopes"
**Cause**: IdP not returning `email` or `profile` claims

**Solution**: Update IdP configuration to include these scopes

### Debug Mode

Enable OIDC debug logging:
```bash
curl -X PUT https://api.logforge.io/v1/enterprise/auth/oidc/{provider_id}/debug \
  -H "X-Customer-ID: your-tenant-id" \
  -H "Authorization: Bearer your-admin-token" \
  -d '{"debug_enabled": true, "duration_minutes": 30}'
```

View debug logs:
```bash
curl -X GET https://api.logforge.io/v1/enterprise/audit-logs \
  -H "X-Customer-ID: your-tenant-id" \
  -H "Authorization: Bearer your-admin-token" \
  -G --data-urlencode 'action_types=oidc_authentication'
```

---

## Testing SSO Configuration

### Pre-Production Testing

1. **Test Connection**: Use the API test endpoint
```bash
curl -X POST https://api.logforge.io/v1/enterprise/auth/oidc/{provider_id}/test \
  -H "X-Customer-ID: your-tenant-id" \
  -H "Authorization: Bearer your-admin-token"
```

2. **Test User Login**: Try logging in with a test user
3. **Verify User Attributes**: Check that name, email, groups are synced correctly
4. **Test Role Mapping**: Verify correct role assigned based on group
5. **Test Session Timeout**: Verify session expires as expected

### Production Rollout

**Phase 1: Pilot (Day 1-7)**
- Enable SSO for IT team only (5-10 users)
- Monitor authentication logs
- Gather feedback

**Phase 2: Department (Day 8-14)**
- Roll out to engineering department (50-100 users)
- Monitor for issues
- Adjust group mappings if needed

**Phase 3: Company-Wide (Day 15+)**
- Enable SSO for all users
- Communicate change to organization
- Provide migration support

---

## Compliance & Audit

### Audit Trail

All OIDC-related events are logged:
- Configuration changes (create, update, delete)
- Authentication attempts (success, failure)
- Token validations
- User provisioning/deprovisioning

View audit logs:
```bash
curl -X GET https://api.logforge.io/v1/enterprise/audit-logs \
  -H "X-Customer-ID: your-tenant-id" \
  -H "Authorization: Bearer your-admin-token" \
  -G --data-urlencode 'action_types=oidc_config_change,oidc_authentication'
```

### Compliance Requirements

OIDC configuration supports:
- **SOC 2**: Encrypted secrets, audit logging, access controls
- **HIPAA**: PHI protection through IdP-managed authentication
- **GDPR**: User consent tracking, right to erasure
- **ISO 27001**: Information security controls

---

## Migration Guide

### Migrating from Password-Based Auth to SSO

1. **Preparation**:
   - Configure OIDC provider
   - Map existing users to IdP users by email
   - Test with pilot group

2. **Migration**:
   - Enable SSO alongside password auth (dual mode)
   - Communicate to users about SSO option
   - Monitor adoption rate

3. **Enforcement**:
   - After 90% adoption, enforce SSO-only
   - Disable password-based authentication
   - Archive old password hashes

---

## FAQ

**Q: Can we use multiple OIDC providers?**
A: Yes, you can configure multiple providers (e.g., Okta for employees, Google for contractors)

**Q: What happens if our IdP goes down?**
A: Emergency access available for admin accounts via password. Configure break-glass accounts.

**Q: Can we customize the login page?**
A: Yes, branding and custom login page available in Enterprise tier

**Q: How long are user sessions valid?**
A: Default 8 hours, configurable from 1 hour to 7 days

**Q: Do we need to pay extra for SSO?**
A: SSO is included in Enterprise and Professional tiers

**Q: Can we require MFA?**
A: MFA is enforced by your IdP. Configure MFA policies in your IdP (Okta, Auth0, etc.)

---

## Support

For assistance with OIDC/SSO configuration:
- **Documentation**: https://docs.logforge.io/enterprise/sso
- **Support Email**: enterprise-support@logforge.io
- **Slack Community**: #enterprise-auth channel
- **Priority Support**: Available 24/7 for Enterprise customers