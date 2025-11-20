# OIDC/SSO Architecture - Subdomain-Based Multi-Tenant Authentication

## Executive Summary

This document describes Logforge's OIDC (OpenID Connect) SSO implementation using subdomain-based tenant routing. This architecture enables enterprise customers to use their existing identity providers (Okta, Auth0, Azure AD, Google Workspace, etc.) for seamless single sign-on.

**Key Features:**
- Subdomain-based tenant identification (`acme.logforge.io`, `globex.logforge.io`)
- Standards-compliant OIDC with PKCE security
- Automatic user provisioning from identity provider
- Role mapping from OIDC groups to Logforge permissions
- Zero-downtime single deployment architecture

---

## Architecture Overview

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         User's Browser                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ 1. Visit login URL
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    https://acme.logforge.io/login                       │
│                    (Tenant Detection Middleware)                         │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ 2. Detect tenant "acme"
                                  │    Load OIDC config for Acme Corp
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Logforge OIDC Service                           │
│  • Generate PKCE challenge                                              │
│  • Generate state (CSRF protection)                                     │
│  • Generate nonce (replay protection)                                   │
│  • Store session in Redis                                               │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ 3. Redirect to OIDC provider
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Acme Corp's Identity Provider                        │
│                    (Okta, Auth0, Azure AD, etc.)                        │
│  • User authenticates (username/password, MFA, etc.)                    │
│  • Provider validates credentials                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ 4. Redirect with authorization code
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│            https://acme.logforge.io/auth/oidc/callback                  │
│                      (OIDC Callback Handler)                            │
│  • Validate state parameter                                             │
│  • Exchange code for tokens (using PKCE verifier)                       │
│  • Validate ID token signature (JWKS)                                   │
│  • Validate ID token claims (issuer, audience, expiration, nonce)       │
│  • Extract user claims (email, name, groups)                            │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ 5. Provision/update user
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Logforge User Provisioning                           │
│  • Check if user exists (by email)                                      │
│  • Create user if new (auto-provision)                                  │
│  • Update user profile from OIDC claims                                 │
│  • Map OIDC groups → Logforge roles                                     │
│  • Create Logforge session (JWT)                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ 6. Redirect to dashboard
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│            https://acme.logforge.io/dashboard?token=XXX                 │
│                       (User logged in)                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Subdomain-Based Tenant Detection

#### How It Works

**DNS Configuration:**
```
Wildcard DNS record:
*.logforge.io  →  A  →  54.123.45.67 (your server)

This routes ALL subdomains to the same server:
acme.logforge.io      → 54.123.45.67
globex.logforge.io    → 54.123.45.67
customer1.logforge.io → 54.123.45.67
```

**Middleware Processing:**
```python
# Request: https://acme.logforge.io/login
# Host header: "acme.logforge.io"

# Extract subdomain
subdomain = "acme"  # First part before .logforge.io

# Lookup tenant
tenant = db.query("SELECT id FROM tenants WHERE subdomain = 'acme'")
# Result: tenant_id = "832f393c-..."

# Store in request state
request.state.tenant_id = tenant_id
request.state.subdomain = subdomain
```

**Why This Works:**
- Single application deployment
- Single SSL certificate (wildcard: `*.logforge.io`)
- No additional hosting costs
- Simple DNS management

---

### 2. OIDC Provider Discovery

#### OpenID Connect Discovery

OIDC providers expose a standardized discovery endpoint:

```
https://YOUR_PROVIDER/.well-known/openid-configuration
```

**Example for Okta:**
```
https://acme.okta.com/.well-known/openid-configuration
```

**Response:**
```json
{
  "issuer": "https://acme.okta.com",
  "authorization_endpoint": "https://acme.okta.com/oauth2/v1/authorize",
  "token_endpoint": "https://acme.okta.com/oauth2/v1/token",
  "userinfo_endpoint": "https://acme.okta.com/oauth2/v1/userinfo",
  "jwks_uri": "https://acme.okta.com/oauth2/v1/keys",
  "scopes_supported": ["openid", "profile", "email", "groups"],
  "response_types_supported": ["code"],
  "grant_types_supported": ["authorization_code", "refresh_token"],
  "code_challenge_methods_supported": ["S256"]
}
```

**Logforge uses this to:**
- Locate authorization endpoint (where to redirect user)
- Locate token endpoint (where to exchange code for tokens)
- Locate JWKS endpoint (for token signature validation)
- Validate provider capabilities (PKCE support, etc.)

---

### 3. OIDC Authorization Flow (Authorization Code + PKCE)

#### Step 1: Login Initiation

**User Action:** Clicks "Login with SSO" or visits `https://acme.logforge.io/auth/oidc/login`

**Logforge Processing:**
```python
# 1. Generate PKCE parameters
code_verifier = random_string(32)  # "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
code_challenge = base64url(sha256(code_verifier))  # "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"

# 2. Generate state (CSRF protection)
state = random_string(32)  # "af0ifjsldkj"

# 3. Generate nonce (replay protection)
nonce = random_string(16)  # "n-0S6_WzA2Mj"

# 4. Store in Redis (10-minute TTL)
redis.setex(f"oidc:session:{state}", 600, {
    "code_verifier": code_verifier,
    "nonce": nonce,
    "tenant_id": "832f393c-...",
    "subdomain": "acme"
})

# 5. Build authorization URL
authorization_url = f"{provider.authorization_endpoint}?" + urlencode({
    "client_id": "logforge-acme",
    "response_type": "code",
    "scope": "openid profile email groups",
    "redirect_uri": "https://acme.logforge.io/auth/oidc/callback",
    "state": state,
    "nonce": nonce,
    "code_challenge": code_challenge,
    "code_challenge_method": "S256"
})

# 6. Redirect user
return RedirectResponse(authorization_url)
```

**Result:** User is redirected to their identity provider (Okta, Auth0, etc.)

---

#### Step 2: User Authentication at Provider

**Provider's Responsibility:**
1. Present login form
2. Validate credentials (username/password)
3. Challenge MFA if configured
4. Check authorization (user has access to this app?)
5. Generate authorization code
6. Redirect back to Logforge

**Redirect URL:**
```
https://acme.logforge.io/auth/oidc/callback?code=ABC123&state=af0ifjsldkj
```

---

#### Step 3: Token Exchange (Callback Handling)

**Logforge Processing:**
```python
# 1. Validate state
session = redis.get(f"oidc:session:{state}")
if not session:
    raise ValueError("Invalid or expired state")

# 2. Exchange authorization code for tokens
token_response = httpx.post(provider.token_endpoint, data={
    "grant_type": "authorization_code",
    "code": "ABC123",
    "redirect_uri": "https://acme.logforge.io/auth/oidc/callback",
    "client_id": "logforge-acme",
    "client_secret": "secret",
    "code_verifier": session["code_verifier"]  # PKCE verification
})

# Response:
{
    "access_token": "eyJhbG...",  # Access token for API calls
    "id_token": "eyJhbGci...",    # ID token with user claims
    "refresh_token": "v1.MTE...", # Refresh token for token renewal
    "token_type": "Bearer",
    "expires_in": 3600
}
```

---

#### Step 4: ID Token Validation

**Security Critical:** Must validate ID token before trusting claims

```python
# 1. Fetch provider's public keys (JWKS)
jwks = httpx.get(provider.jwks_uri).json()
# {
#   "keys": [
#     {
#       "kty": "RSA",
#       "kid": "SIMcQK...",
#       "use": "sig",
#       "n": "xGOr...",  # RSA public key modulus
#       "e": "AQAB"      # RSA public key exponent
#     }
#   ]
# }

# 2. Decode ID token header to get key ID
header = jwt.get_unverified_header(id_token)
# {"alg": "RS256", "kid": "SIMcQK..."}

# 3. Find matching public key
signing_key = [k for k in jwks["keys"] if k["kid"] == header["kid"]][0]

# 4. Verify signature and decode claims
claims = jwt.decode(
    id_token,
    signing_key,
    algorithms=["RS256"],
    audience="logforge-acme",  # Must match our client_id
    issuer="https://acme.okta.com",  # Must match provider
    options={"verify_exp": True}  # Check expiration
)

# 5. Validate additional claims
assert claims["nonce"] == session["nonce"]  # Prevent replay attacks
assert claims["aud"] == "logforge-acme"     # Intended for us
assert claims["iss"] == "https://acme.okta.com"  # From correct provider
assert claims["exp"] > time.time()          # Not expired

# Claims now trusted:
{
    "sub": "00uid4BxXw6I6TV4m0g3",       # User ID at provider
    "email": "john.doe@acme.com",
    "name": "John Doe",
    "groups": ["logforge-admins", "engineering"],
    "iss": "https://acme.okta.com",
    "aud": "logforge-acme",
    "exp": 1700000000,
    "iat": 1699996400,
    "nonce": "n-0S6_WzA2Mj"
}
```

**Why Each Validation Matters:**
- **Signature verification**: Proves token came from trusted provider
- **Audience validation**: Prevents token replay to different apps
- **Issuer validation**: Prevents tokens from other providers
- **Expiration check**: Prevents use of old tokens
- **Nonce validation**: Prevents replay attacks

---

### 4. User Provisioning

#### Auto-Provisioning Flow

```python
email = claims["email"]  # "john.doe@acme.com"

# 1. Check if user exists
user = db.query("SELECT * FROM users WHERE email = ?", email)

if not user:
    # 2. Create new user (auto-provision)
    user = db.insert("users", {
        "id": str(uuid4()),
        "email": email,
        "name": claims.get("name", email),
        "customer_id": tenant_id,
        "status": "active",
        "password_hash": "",  # OIDC users don't have passwords
        "email_verified_at": datetime.utcnow(),  # Trust provider
        "created_via": "oidc",
        "oidc_sub": claims["sub"]  # Link to provider user ID
    })

    logger.info("New user auto-provisioned",
               user_id=user.id,
               email=email,
               provider="okta")

# 3. Update user profile from latest claims
db.update("users", {
    "name": claims.get("name"),
    "last_login_at": datetime.utcnow(),
    "oidc_sub": claims["sub"]
}, where={"id": user.id})
```

**Benefits:**
- No manual user creation needed
- Users can login immediately
- Profile stays synchronized with identity provider
- Audit trail of OIDC-created users

---

### 5. Role Mapping

#### OIDC Groups → Logforge Roles

**OIDC Provider Configuration:**
```json
{
  "provider_name": "Okta",
  "group_mapping": {
    "logforge-admins": "tenant_admin",
    "logforge-security": "security_analyst",
    "logforge-devops": "devops_engineer",
    "logforge-viewers": "viewer"
  }
}
```

**User's OIDC Claims:**
```json
{
  "email": "john.doe@acme.com",
  "groups": ["logforge-admins", "engineering", "all-staff"]
}
```

**Role Mapping Logic:**
```python
oidc_groups = claims.get("groups", [])
# ["logforge-admins", "engineering", "all-staff"]

group_mapping = provider_config["group_mapping"]
# {"logforge-admins": "tenant_admin", ...}

for oidc_group in oidc_groups:
    logforge_role = group_mapping.get(oidc_group)

    if logforge_role:
        # Assign role in Logforge
        db.insert("user_tenant_roles", {
            "user_id": user.id,
            "tenant_id": tenant_id,
            "role": logforge_role,
            "granted_by": "oidc-system"
        })

# Result: John is assigned "tenant_admin" role
```

**Role Hierarchy:**

| OIDC Group | Logforge Role | Permissions |
|------------|---------------|-------------|
| `logforge-admins` | `tenant_admin` | Full tenant access (users, settings, billing) |
| `logforge-security` | `security_analyst` | Security events, threat hunting, alerts |
| `logforge-devops` | `devops_engineer` | Logs, dashboards, observability |
| `logforge-viewers` | `viewer` | Read-only access to logs and dashboards |

**Default Behavior:**
- If user has no matching groups → Assign `viewer` role
- If user has multiple matching groups → Assign all roles (cumulative permissions)
- If group mapping changes → Roles updated on next login

---

### 6. Session Management

#### Creating Logforge Session

After successful OIDC authentication and user provisioning:

```python
# 1. Create session in database
session = db.insert("user_sessions", {
    "id": str(uuid4()),
    "user_id": user.id,
    "tenant_id": tenant_id,
    "session_type": "oidc",
    "created_at": datetime.utcnow(),
    "expires_at": datetime.utcnow() + timedelta(hours=8),
    "ip_address": request.client.host,
    "user_agent": request.headers.get("user-agent"),
    "oidc_provider": "okta",
    "oidc_sub": claims["sub"]
})

# 2. Generate Logforge JWT
jwt_payload = {
    "user_id": user.id,
    "tenant_id": tenant_id,
    "session_id": session.id,
    "roles": ["tenant_admin"],
    "exp": int(time.time()) + (8 * 3600),  # 8 hours
    "iat": int(time.time()),
    "type": "session"
}

jwt_token = jwt.encode(jwt_payload, JWT_SECRET, algorithm="HS256")

# 3. Redirect to dashboard with session token
return RedirectResponse(
    f"https://acme.logforge.io/dashboard?token={jwt_token}"
)
```

**Session Lifecycle:**
- **Duration**: 8 hours (configurable per tenant)
- **Renewal**: Automatic using refresh token (if provider supports)
- **Logout**: Invalidates both Logforge session and OIDC session

---

## Security Architecture

### Defense in Depth

#### 1. PKCE (Proof Key for Code Exchange)

**Problem:** Authorization code interception attack
- Attacker intercepts authorization code during redirect
- Attacker exchanges code for tokens (if no PKCE)

**Solution:** PKCE
```python
# Client generates random verifier
code_verifier = random_string(32)

# Client hashes verifier → challenge
code_challenge = base64url(sha256(code_verifier))

# Authorization request includes challenge
authorization_url += f"&code_challenge={code_challenge}&code_challenge_method=S256"

# Token exchange includes verifier
token_request = {
    "code": "ABC123",
    "code_verifier": code_verifier  # Provider validates: sha256(verifier) == challenge
}
```

**Result:** Even if attacker intercepts code, they can't exchange it (no verifier)

---

#### 2. State Parameter (CSRF Protection)

**Problem:** Cross-Site Request Forgery
- Attacker tricks user into completing OIDC flow with attacker's code
- User's session links to attacker's account

**Solution:** State parameter
```python
# Generate random state
state = random_string(32)

# Store in user's session (server-side)
redis.setex(f"oidc:session:{state}", 600, {...})

# Include in authorization URL
authorization_url += f"&state={state}"

# Validate on callback
if state_from_url != state_from_session:
    raise ValueError("CSRF attack detected")
```

**Result:** Callback must come from same user's browser session

---

#### 3. Nonce (Replay Attack Prevention)

**Problem:** ID token replay attack
- Attacker captures valid ID token
- Attacker replays token to authenticate

**Solution:** Nonce
```python
# Generate nonce for this login attempt
nonce = random_string(16)

# Store in session
session["nonce"] = nonce

# Include in authorization request
authorization_url += f"&nonce={nonce}"

# Provider includes nonce in ID token
id_token_claims = {"nonce": nonce, ...}

# Validate nonce matches
if id_token["nonce"] != session["nonce"]:
    raise ValueError("Replay attack detected")
```

**Result:** Each ID token is single-use

---

#### 4. Token Signature Validation

**Problem:** Token forgery
- Attacker creates fake ID token with arbitrary claims

**Solution:** Cryptographic signature
```python
# Provider signs token with private key
id_token = jwt.encode(claims, provider_private_key, algorithm="RS256")

# Logforge validates with provider's public key
claims = jwt.decode(id_token, provider_public_key, algorithms=["RS256"])
```

**Result:** Only provider can issue valid tokens

---

#### 5. HTTPS Enforcement

**Problem:** Man-in-the-middle attacks

**Solution:** HTTPS everywhere
- All OIDC flows require HTTPS
- Wildcard SSL certificate for `*.logforge.io`
- HSTS headers to prevent downgrade attacks

```python
# Middleware enforces HTTPS
if request.url.scheme != "https":
    return Response("HTTPS required", status_code=403)
```

---

## Deployment Architecture

### Single-Application Multi-Tenant

```
                        Internet
                           │
                           │
                           ▼
                    ┌──────────────┐
                    │   Wildcard   │
                    │   DNS A      │
                    │ *.logforge.io│
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Load Balancer│
                    │  (Nginx/ALB) │
                    │   SSL Cert   │
                    └──────┬───────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ Logforge │    │ Logforge │    │ Logforge │
    │ App #1   │    │ App #2   │    │ App #3   │
    │ (Docker) │    │ (Docker) │    │ (Docker) │
    └────┬─────┘    └────┬─────┘    └────┬─────┘
         │               │               │
         └───────────────┼───────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
    ┌────────┐     ┌────────┐     ┌────────┐
    │ Redis  │     │ClickHou│     │Postgres│
    │(Session│     │  se    │     │  (User)│
    └────────┘     └────────┘     └────────┘
```

**Key Points:**
- **Single Application**: All instances run same code
- **Horizontal Scaling**: Add more instances for load
- **Shared State**: Redis for sessions, ClickHouse for data
- **Single SSL Cert**: Wildcard `*.logforge.io` covers all subdomains

---

### Infrastructure Requirements

#### DNS
```bash
# Single wildcard A record
*.logforge.io  A  54.123.45.67
```

#### SSL Certificate
```bash
# Let's Encrypt wildcard certificate
certbot certonly --manual --preferred-challenges dns \
  -d "*.logforge.io" -d "logforge.io"

# Auto-renewal
certbot renew --deploy-hook "systemctl reload nginx"
```

#### Redis
```bash
# For OIDC session storage
docker run -d \
  --name redis \
  -p 6379:6379 \
  redis:7-alpine
```

#### Application Environment
```bash
# .env
LOGFORGE_BASE_URL=https://logforge.io
REDIS_URL=redis://localhost:6379
JWT_SECRET=your-secret-key
```

---

## Customer Onboarding Guide

### For Tenant Administrators

#### Step 1: Get Your Subdomain

**Option A: During Signup**
```
Company Name: Acme Corporation
Suggested Subdomain: acme  (editable)
```

**Option B: Via API**
```bash
POST /v1/tenants
{
  "name": "Acme Corporation",
  "subdomain": "acme"
}

Response:
{
  "tenant_id": "832f393c-...",
  "subdomain": "acme",
  "login_url": "https://acme.logforge.io/login"
}
```

---

#### Step 2: Configure OIDC Provider

**In Logforge:**
```bash
POST /v1/enterprise/auth/oidc/configure
Headers:
  X-Customer-ID: 832f393c-...

Body:
{
  "provider_name": "Okta",
  "provider_type": "oidc",
  "client_id": "0oa2t7obiy9ZZDasx5d7",
  "client_secret": "very-secret-value",
  "domain": "acme.okta.com",
  "scopes": ["openid", "profile", "email", "groups"]
}
```

**In Your Identity Provider (Okta example):**

1. Create new OIDC application
   - **Application Type**: Web Application
   - **Grant Types**: Authorization Code
   - **Sign-in redirect URIs**: `https://acme.logforge.io/auth/oidc/callback`
   - **Sign-out redirect URIs**: `https://acme.logforge.io/login`
   - **Initiate login URI**: `https://acme.logforge.io/auth/oidc/login`

2. Configure group claims
   - **Token Type**: ID Token
   - **Claims**: Add `groups` claim
   - **Filter**: Regex `logforge-.*` (only groups starting with "logforge-")

3. Assign users to application

---

#### Step 3: Configure Role Mapping

```bash
POST /v1/enterprise/auth/oidc/configure
Body:
{
  ...existing config...,
  "group_mapping": {
    "logforge-admins": "tenant_admin",
    "logforge-security": "security_analyst",
    "logforge-devops": "devops_engineer",
    "logforge-viewers": "viewer"
  }
}
```

**Create Groups in Identity Provider:**
- `logforge-admins` - Full admin access
- `logforge-security` - Security operations team
- `logforge-devops` - DevOps engineers
- `logforge-viewers` - Read-only access

**Assign Users to Groups** in your identity provider

---

#### Step 4: Test SSO

1. **Open login URL** in incognito window
   ```
   https://acme.logforge.io/auth/oidc/login
   ```

2. **Redirected to your identity provider**
   - Enter your credentials
   - Complete MFA if configured

3. **Redirected back to Logforge**
   ```
   https://acme.logforge.io/dashboard
   ```

4. **Verify permissions**
   - Check your assigned role
   - Verify you have expected access

**Troubleshooting:**
- Check OIDC configuration in Logforge
- Verify redirect URIs in identity provider
- Check user is assigned to OIDC application
- Review audit logs for errors

---

## Supported Identity Providers

### Okta
- **Discovery URL**: `https://YOUR_DOMAIN.okta.com/.well-known/openid-configuration`
- **Setup Guide**: [Okta OIDC Setup](https://developer.okta.com/docs/guides/implement-grant-type/authcode/main/)
- **Group Claims**: Supported via custom claims

### Auth0
- **Discovery URL**: `https://YOUR_DOMAIN.auth0.com/.well-known/openid-configuration`
- **Setup Guide**: [Auth0 OIDC Setup](https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow)
- **Group Claims**: Supported via custom claims or rules

### Azure AD (Microsoft Entra ID)
- **Discovery URL**: `https://login.microsoftonline.com/YOUR_TENANT_ID/v2.0/.well-known/openid-configuration`
- **Setup Guide**: [Azure AD OIDC Setup](https://learn.microsoft.com/en-us/azure/active-directory/develop/v2-protocols-oidc)
- **Group Claims**: Supported via app registration

### Google Workspace
- **Discovery URL**: `https://accounts.google.com/.well-known/openid-configuration`
- **Setup Guide**: [Google OIDC Setup](https://developers.google.com/identity/protocols/oauth2/openid-connect)
- **Group Claims**: Requires Google Workspace admin

### Generic OIDC
Any standards-compliant OIDC provider is supported. Minimum requirements:
- Authorization Code grant type
- PKCE support
- JWKS for token validation
- `openid`, `profile`, `email` scopes

---

## Monitoring & Observability

### Key Metrics

#### Authentication Metrics
- **OIDC login success rate**: Target >99%
- **OIDC login duration**: Target <3 seconds
- **Token validation failures**: Alert if >1%
- **User provisioning time**: Target <500ms

#### Security Metrics
- **State validation failures**: Alert if >0 (CSRF attempts)
- **Nonce validation failures**: Alert if >0 (replay attempts)
- **Token signature failures**: Alert if >0 (forgery attempts)
- **Expired token usage**: Track for user experience

#### Business Metrics
- **New users auto-provisioned**: Track adoption
- **OIDC vs password logins**: Track SSO adoption
- **Failed login reasons**: Improve user experience

---

### Logging

**Successful Login:**
```json
{
  "event": "oidc_login_success",
  "timestamp": "2025-11-17T10:30:00Z",
  "tenant_id": "832f393c-...",
  "subdomain": "acme",
  "user_id": "user_123",
  "email": "john.doe@acme.com",
  "provider": "okta",
  "oidc_sub": "00uid4BxXw6I6TV4m0g3",
  "roles_assigned": ["tenant_admin"],
  "auto_provisioned": false,
  "duration_ms": 2847
}
```

**Failed Login:**
```json
{
  "event": "oidc_login_failed",
  "timestamp": "2025-11-17T10:30:00Z",
  "tenant_id": "832f393c-...",
  "subdomain": "acme",
  "error": "invalid_state",
  "error_detail": "State parameter mismatch - possible CSRF attack",
  "ip_address": "203.0.113.42"
}
```

---

## FAQ

### Q: What happens if our identity provider goes down?

**A:** Existing sessions continue working (sessions last 8 hours). New logins fail until provider is restored. Consider:
- Configuring backup authentication (password login)
- Provider's SLA and uptime guarantees
- Implementing fallback to emergency admin account

---

### Q: Can we use multiple identity providers?

**A:** Yes! Configure multiple OIDC providers and let users choose:
```
Login Page:
- [Login with Okta]
- [Login with Azure AD]
- [Login with Google]
```

Each provider can have different group mappings.

---

### Q: How do we remove a user's access?

**A:** Revoke access in your identity provider:
1. Remove user from OIDC application
2. User's next login attempt fails
3. Existing session expires (max 8 hours)

For immediate revocation: Disable user in Logforge admin panel.

---

### Q: What if a user changes groups in the identity provider?

**A:** Roles update on next login:
1. User logs in
2. Fresh ID token includes new groups
3. Logforge re-maps groups to roles
4. User's roles updated in database
5. New permissions take effect immediately

---

### Q: Can we customize session duration?

**A:** Yes! Configure per-tenant:
```bash
POST /v1/tenants/{tenant_id}/settings
{
  "security_settings": {
    "session_timeout_hours": 4,  # Default: 8
    "require_mfa": true,
    "allowed_ip_ranges": ["203.0.113.0/24"]
  }
}
```

---

### Q: How do we test OIDC configuration before deploying to all users?

**A:** Staged rollout:
1. Configure OIDC provider
2. Test with test user account
3. Enable for specific groups (beta testers)
4. Enable for all users
5. Disable password authentication (if desired)

---

### Q: What's the cost of wildcard SSL?

**A:** Free with Let's Encrypt! Automatic renewal every 90 days.

---

## Troubleshooting Guide

### Error: "Invalid or expired state parameter"

**Cause:** CSRF protection triggered

**Possible Reasons:**
- User took too long to login (>10 minutes)
- User clicked back button after login
- Cookies disabled in browser
- Redis session expired

**Solution:**
- Try logging in again
- Enable cookies
- Check Redis connectivity

---

### Error: "ID token validation failed"

**Cause:** Token signature or claims invalid

**Possible Reasons:**
- Provider's JWKS changed (key rotation)
- Clock skew between servers
- Wrong client_id configured
- Token expired

**Solution:**
- Refresh JWKS cache
- Check system time synchronization (NTP)
- Verify OIDC configuration
- Check provider's status page

---

### Error: "No OIDC provider configured"

**Cause:** Tenant has no OIDC provider

**Solution:**
- Configure OIDC provider via API
- Check tenant_id is correct
- Verify provider is enabled

---

### Error: "User not assigned to application"

**Cause:** User exists in identity provider but not assigned to Logforge app

**Solution:**
- Assign user to OIDC application in identity provider
- Check application assignment rules
- Verify user's group memberships

---

## Security Audit Checklist

- [ ] PKCE enabled for all OIDC flows
- [ ] State parameter validated on callback
- [ ] Nonce validated in ID token
- [ ] Token signature verified using JWKS
- [ ] Token expiration checked
- [ ] Audience claim validated
- [ ] Issuer claim validated
- [ ] HTTPS enforced for all OIDC endpoints
- [ ] Session storage uses secure Redis
- [ ] Session TTL configured (not infinite)
- [ ] Logout invalidates both sessions
- [ ] Audit logs capture all authentication events
- [ ] Sensitive data (client_secret) encrypted at rest
- [ ] Rate limiting on login endpoints
- [ ] IP whitelisting supported

---

## Performance Benchmarks

### Target Performance

| Metric | Target | Notes |
|--------|--------|-------|
| OIDC Login Duration | <3 seconds | User clicks login → dashboard loaded |
| Token Validation | <100ms | JWT signature verification |
| User Provisioning | <500ms | Create new user from OIDC claims |
| Role Assignment | <200ms | Map groups to roles |
| Redirect Time | <200ms | Authorization initiation |
| Session Creation | <100ms | Generate Logforge JWT |

### Optimization Tips

1. **Cache JWKS**: Cache provider's public keys for 24 hours
2. **Use Redis**: Fast session storage (vs database)
3. **Parallel Processing**: Provision user + assign roles in parallel
4. **Connection Pooling**: Reuse HTTP connections to provider
5. **Async I/O**: Non-blocking token exchange

---

## Changelog

### Version 1.0 (2025-11-17)
- Initial OIDC/SSO architecture design
- Subdomain-based tenant routing
- PKCE implementation
- Auto-user provisioning
- Role mapping from OIDC groups
- Support for Okta, Auth0, Azure AD, Google

---

## References

### Standards
- [OAuth 2.0 RFC 6749](https://datatracker.ietf.org/doc/html/rfc6749)
- [OpenID Connect Core 1.0](https://openid.net/specs/openid-connect-core-1_0.html)
- [PKCE RFC 7636](https://datatracker.ietf.org/doc/html/rfc7636)
- [JSON Web Token RFC 7519](https://datatracker.ietf.org/doc/html/rfc7519)

### Implementation Guides
- [OIDC Best Practices](https://openid.net/specs/openid-connect-basic-1_0.html)
- [OAuth 2.0 Security Best Practices](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)
- [Token Validation](https://auth0.com/docs/secure/tokens/json-web-tokens/validate-json-web-tokens)

---

**Document Version:** 1.0
**Last Updated:** 2025-11-17
**Owner:** Engineering Team
**Review Cycle:** Quarterly