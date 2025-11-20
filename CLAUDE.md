# Logforge - Enterprise OIDC/SSO Implementation Plan
## Subdomain-Based Multi-Tenant Authentication

---

## <¯ Objective

Implement production-ready OIDC/SSO authentication with subdomain-based tenant routing:
- `acme.logforge.io` ’ Acme Corp's OIDC configuration
- `globex.logforge.io` ’ Globex Inc's OIDC configuration
- Automatic user provisioning from OIDC provider
- Role mapping from OIDC groups to Logforge roles
- Enterprise-grade security (PKCE, state validation, token verification)

---

## =Ë Implementation Phases

### Phase 1: Infrastructure & Subdomain Detection (2 days)

**Goal:** Enable subdomain-based tenant routing without OIDC

#### 1.1 DNS Configuration
```bash
# Add wildcard DNS record
*.logforge.io  ’  A  ’  YOUR_SERVER_IP
```

#### 1.2 SSL Certificate
```bash
# Get wildcard SSL certificate from Let's Encrypt
certbot certonly --manual --preferred-challenges dns \
  -d "*.logforge.io" -d "logforge.io"
```

#### 1.3 Subdomain Detection Middleware
**File:** `/apps/api/middleware/tenant_detection_middleware.py` (NEW)

```python
"""
Tenant Detection Middleware - Extract tenant from subdomain
Runs BEFORE authentication to determine which tenant's auth config to use
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger()


class TenantDetectionMiddleware(BaseHTTPMiddleware):
    """Detect tenant from subdomain and add to request state"""

    def __init__(self, app):
        super().__init__(app)
        self.dao = None  # Lazy init to avoid circular imports

    async def dispatch(self, request: Request, call_next):
        """Extract tenant from subdomain and store in request.state"""

        # Get hostname from request
        host = request.headers.get("host", "")

        # Extract subdomain
        tenant_subdomain = await self._extract_subdomain(host)

        if tenant_subdomain:
            # Look up tenant_id from subdomain
            tenant_id = await self._get_tenant_id_from_subdomain(tenant_subdomain)

            if tenant_id:
                # Store in request state for use by auth middleware
                request.state.tenant_subdomain = tenant_subdomain
                request.state.tenant_id_from_subdomain = tenant_id
                logger.debug("Tenant detected from subdomain",
                           subdomain=tenant_subdomain,
                           tenant_id=tenant_id)

        response = await call_next(request)
        return response

    async def _extract_subdomain(self, host: str) -> Optional[str]:
        """Extract subdomain from host header"""
        # Remove port if present
        host = host.split(':')[0]

        # Split by dots
        parts = host.split('.')

        # logforge.io = 2 parts (no subdomain)
        # acme.logforge.io = 3 parts (subdomain = "acme")
        # api.acme.logforge.io = 4 parts (subdomain = "acme", ignore "api")

        if len(parts) >= 3:
            # Return first part as subdomain (ignore "api", "www", etc.)
            subdomain = parts[0]

            # Skip common prefixes
            if subdomain in ['www', 'api', 'app']:
                # Check if there's another subdomain
                if len(parts) >= 4:
                    return parts[1]  # e.g., api.acme.logforge.io ’ "acme"
                return None

            return subdomain

        return None

    async def _get_tenant_id_from_subdomain(self, subdomain: str) -> Optional[str]:
        """Look up tenant_id from subdomain in database"""
        try:
            from dao.tenant_dao import TenantDAO

            if not self.dao:
                self.dao = TenantDAO()

            # Query tenants table for subdomain match
            query = """
                SELECT id FROM tenants_mt
                WHERE subdomain = %(subdomain)s
                  AND status = 'active'
                LIMIT 1
            """

            result = await self.dao.db.execute_query(query, {"subdomain": subdomain})

            if result and len(result) > 0:
                return result[0]['id']

            return None

        except Exception as e:
            logger.error("Failed to lookup tenant from subdomain",
                        error=str(e),
                        subdomain=subdomain)
            return None
```

#### 1.4 Add Subdomain Column to Tenants Table
**File:** `/infra/docker/clickhouse/migrations/006_add_tenant_subdomain.sql` (NEW)

```sql
-- Add subdomain column to tenants_mt table
ALTER TABLE tenants_mt ADD COLUMN IF NOT EXISTS subdomain String DEFAULT '';

-- Add index for fast subdomain lookups
-- (ClickHouse doesn't support unique constraints, so enforce in application)
```

#### 1.5 Update Tenant Creation
**File:** `/apps/api/services/tenant_service.py`

```python
async def create_tenant(self, tenant_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create tenant with subdomain"""

    # Generate subdomain from company name if not provided
    if not tenant_data.get('subdomain'):
        company_name = tenant_data['name']
        subdomain = self._generate_subdomain(company_name)
    else:
        subdomain = tenant_data['subdomain'].lower().strip()

    # Validate subdomain (alphanumeric + hyphens only)
    if not self._is_valid_subdomain(subdomain):
        raise ValueError(f"Invalid subdomain: {subdomain}")

    # Check if subdomain already exists
    if await self._subdomain_exists(subdomain):
        raise ValueError(f"Subdomain '{subdomain}' is already taken")

    # Add subdomain to tenant data
    tenant_data['subdomain'] = subdomain

    # Create tenant (existing code)
    tenant = await self.tenant_dao.create_tenant(tenant_data)

    return {
        **tenant,
        'subdomain': subdomain,
        'login_url': f"https://{subdomain}.logforge.io/login"
    }

def _generate_subdomain(self, company_name: str) -> str:
    """Generate subdomain from company name"""
    import re

    # Convert to lowercase, remove special chars, replace spaces with hyphens
    subdomain = company_name.lower()
    subdomain = re.sub(r'[^a-z0-9-]', '', subdomain.replace(' ', '-'))
    subdomain = re.sub(r'-+', '-', subdomain)  # Remove duplicate hyphens
    subdomain = subdomain.strip('-')

    return subdomain

def _is_valid_subdomain(self, subdomain: str) -> bool:
    """Validate subdomain format"""
    import re

    # Alphanumeric + hyphens, 3-63 chars, no leading/trailing hyphens
    pattern = r'^[a-z0-9]([a-z0-9-]{1,61}[a-z0-9])?$'

    # Reserved subdomains
    reserved = ['www', 'api', 'app', 'admin', 'staging', 'dev', 'test', 'demo']

    if subdomain in reserved:
        return False

    return bool(re.match(pattern, subdomain))

async def _subdomain_exists(self, subdomain: str) -> bool:
    """Check if subdomain is already taken"""
    existing = await self.tenant_dao.get_tenant_by_subdomain(subdomain)
    return existing is not None
```

#### 1.6 Register Middleware in Main App
**File:** `/apps/api/main.py`

```python
from middleware.tenant_detection_middleware import TenantDetectionMiddleware

# Add BEFORE authentication middleware
app.add_middleware(TenantDetectionMiddleware)
```

**Deliverables:**
-  Wildcard DNS configured
-  Wildcard SSL certificate installed
-  Subdomain detection middleware
-  Tenants have subdomain field
-  Tenant creation validates subdomain uniqueness

---

### Phase 2: OIDC Core Flow (3 days)

**Goal:** Implement complete OIDC authorization code flow

#### 2.1 OIDC Service
**File:** `/apps/api/services/oidc_service.py` (NEW)

```python
"""
OIDC Service - OpenID Connect authentication flow
Handles provider discovery, authorization, token exchange, and validation
"""

import httpx
import jwt
import secrets
import hashlib
import base64
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger()


class OIDCService:
    """OIDC authentication service"""

    def __init__(self):
        from dao.enterprise_dao import EnterpriseDAO
        self.dao = EnterpriseDAO()
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def discover_provider_config(self, issuer_url: str) -> Dict[str, Any]:
        """Fetch OIDC configuration from .well-known endpoint"""
        discovery_url = f"{issuer_url}/.well-known/openid-configuration"

        try:
            response = await self.http_client.get(discovery_url)
            response.raise_for_status()

            config = response.json()

            return {
                'issuer': config['issuer'],
                'authorization_endpoint': config['authorization_endpoint'],
                'token_endpoint': config['token_endpoint'],
                'userinfo_endpoint': config.get('userinfo_endpoint'),
                'jwks_uri': config['jwks_uri'],
                'scopes_supported': config.get('scopes_supported', []),
                'response_types_supported': config.get('response_types_supported', [])
            }

        except Exception as e:
            logger.error("OIDC provider discovery failed",
                        error=str(e),
                        issuer=issuer_url)
            raise ValueError(f"Failed to discover OIDC provider: {str(e)}")

    async def initiate_authorization(self, tenant_id: str, subdomain: str) -> Dict[str, Any]:
        """Initiate OIDC authorization flow"""

        # Get OIDC provider configuration for this tenant
        provider = await self.dao.get_default_auth_provider(tenant_id)

        if not provider or provider['provider_type'] != 'oidc':
            raise ValueError(f"No OIDC provider configured for tenant {tenant_id}")

        # Generate PKCE parameters
        code_verifier = secrets.token_urlsafe(32)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip('=')

        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)

        # Generate nonce for replay protection
        nonce = secrets.token_urlsafe(16)

        # Store PKCE verifier and state in Redis/session
        await self._store_oidc_session(state, {
            'code_verifier': code_verifier,
            'nonce': nonce,
            'tenant_id': tenant_id,
            'subdomain': subdomain,
            'provider_id': provider['id'],
            'created_at': datetime.utcnow().isoformat()
        })

        # Build authorization URL
        config = provider['config']
        auth_endpoint = config['authorization_endpoint']

        # Redirect URI includes subdomain
        redirect_uri = f"https://{subdomain}.logforge.io/auth/oidc/callback"

        params = {
            'client_id': config['client_id'],
            'response_type': 'code',
            'scope': ' '.join(config.get('scopes', ['openid', 'profile', 'email'])),
            'redirect_uri': redirect_uri,
            'state': state,
            'nonce': nonce,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256'
        }

        # Build authorization URL
        from urllib.parse import urlencode
        authorization_url = f"{auth_endpoint}?{urlencode(params)}"

        return {
            'authorization_url': authorization_url,
            'state': state
        }

    async def handle_callback(self, code: str, state: str, subdomain: str) -> Dict[str, Any]:
        """Handle OIDC callback - exchange code for tokens"""

        # Validate state and retrieve session
        session = await self._get_oidc_session(state)

        if not session:
            raise ValueError("Invalid or expired state parameter")

        if session['subdomain'] != subdomain:
            raise ValueError("Subdomain mismatch")

        # Get provider configuration
        provider = await self.dao.get_auth_provider_by_id(
            session['provider_id'],
            session['tenant_id']
        )

        config = provider['config']

        # Exchange authorization code for tokens
        redirect_uri = f"https://{subdomain}.logforge.io/auth/oidc/callback"

        token_response = await self.http_client.post(
            config['token_endpoint'],
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': redirect_uri,
                'client_id': config['client_id'],
                'client_secret': config.get('client_secret', ''),
                'code_verifier': session['code_verifier']
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )

        if token_response.status_code != 200:
            raise ValueError(f"Token exchange failed: {token_response.text}")

        tokens = token_response.json()

        # Validate ID token
        id_token = tokens['id_token']
        claims = await self._validate_id_token(
            id_token,
            config,
            session['nonce']
        )

        # Clean up session
        await self._delete_oidc_session(state)

        return {
            'claims': claims,
            'access_token': tokens.get('access_token'),
            'refresh_token': tokens.get('refresh_token'),
            'tenant_id': session['tenant_id']
        }

    async def _validate_id_token(self, id_token: str, provider_config: Dict,
                                 expected_nonce: str) -> Dict[str, Any]:
        """Validate ID token signature and claims"""

        # Fetch JWKS for signature verification
        jwks = await self._fetch_jwks(provider_config['jwks_uri'])

        # Decode and verify token
        try:
            claims = jwt.decode(
                id_token,
                jwks,
                algorithms=['RS256'],
                audience=provider_config['client_id'],
                issuer=provider_config['issuer'],
                options={'verify_exp': True}
            )

            # Validate nonce
            if claims.get('nonce') != expected_nonce:
                raise ValueError("Nonce mismatch")

            return claims

        except jwt.ExpiredSignatureError:
            raise ValueError("ID token has expired")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid ID token: {str(e)}")

    async def _fetch_jwks(self, jwks_uri: str) -> Dict[str, Any]:
        """Fetch JSON Web Key Set for token validation"""
        response = await self.http_client.get(jwks_uri)
        response.raise_for_status()
        return response.json()

    async def _store_oidc_session(self, state: str, session_data: Dict[str, Any]):
        """Store OIDC session (Redis or database)"""
        # TODO: Use Redis for better performance
        # For now, store in ClickHouse with TTL
        pass

    async def _get_oidc_session(self, state: str) -> Optional[Dict[str, Any]]:
        """Retrieve OIDC session"""
        # TODO: Retrieve from Redis
        pass

    async def _delete_oidc_session(self, state: str):
        """Delete OIDC session after use"""
        # TODO: Delete from Redis
        pass
```

#### 2.2 OIDC Authentication Endpoints
**File:** `/apps/api/routers/oidc_auth_api.py` (NEW)

```python
"""
OIDC Authentication Endpoints
Handles OIDC login initiation, callback, and logout
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from services.oidc_service import OIDCService
from services.user_service import UserService
from services.role_service import RoleService
import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/auth/oidc", tags=["oidc"])


@router.get("/login")
async def oidc_login(request: Request):
    """
    Initiate OIDC login flow

    User visits: https://acme.logforge.io/auth/oidc/login
    Redirected to OIDC provider with proper parameters
    """

    # Get tenant from subdomain (set by TenantDetectionMiddleware)
    tenant_id = getattr(request.state, 'tenant_id_from_subdomain', None)
    subdomain = getattr(request.state, 'tenant_subdomain', None)

    if not tenant_id or not subdomain:
        raise HTTPException(
            status_code=400,
            detail="Invalid subdomain or tenant not found"
        )

    oidc_service = OIDCService()

    try:
        # Initiate authorization flow
        auth_data = await oidc_service.initiate_authorization(tenant_id, subdomain)

        # Redirect user to OIDC provider
        return RedirectResponse(
            url=auth_data['authorization_url'],
            status_code=302
        )

    except Exception as e:
        logger.error("OIDC login initiation failed",
                    error=str(e),
                    tenant_id=tenant_id,
                    subdomain=subdomain)
        raise HTTPException(status_code=500, detail="Login failed")


@router.get("/callback")
async def oidc_callback(request: Request, code: str, state: str):
    """
    Handle OIDC callback after user authenticates

    Provider redirects to: https://acme.logforge.io/auth/oidc/callback?code=XXX&state=YYY
    """

    subdomain = getattr(request.state, 'tenant_subdomain', None)

    if not subdomain:
        raise HTTPException(status_code=400, detail="Invalid subdomain")

    oidc_service = OIDCService()
    user_service = UserService()

    try:
        # Exchange code for tokens and validate
        callback_data = await oidc_service.handle_callback(code, state, subdomain)

        claims = callback_data['claims']
        tenant_id = callback_data['tenant_id']

        # Provision or update user from OIDC claims
        user = await provision_user_from_oidc(claims, tenant_id, user_service)

        # Create Logforge session
        session_token = await user_service.create_session(
            user.id,
            tenant_id,
            session_type='oidc',
            metadata={
                'oidc_provider': 'configured',
                'email': claims.get('email'),
                'oidc_sub': claims.get('sub')
            }
        )

        # Redirect to dashboard with session token
        dashboard_url = f"https://{subdomain}.logforge.io/dashboard?token={session_token}"

        return RedirectResponse(
            url=dashboard_url,
            status_code=302
        )

    except Exception as e:
        logger.error("OIDC callback failed",
                    error=str(e),
                    subdomain=subdomain)
        # Redirect to login with error
        error_url = f"https://{subdomain}.logforge.io/login?error=auth_failed"
        return RedirectResponse(url=error_url, status_code=302)


@router.post("/logout")
async def oidc_logout(request: Request):
    """
    OIDC logout - logout from both Logforge and OIDC provider
    """

    subdomain = getattr(request.state, 'tenant_subdomain', None)

    # TODO: Implement SSO logout
    # 1. Invalidate Logforge session
    # 2. Redirect to OIDC provider logout endpoint

    logout_url = f"https://{subdomain}.logforge.io/login?logged_out=true"
    return RedirectResponse(url=logout_url, status_code=302)


async def provision_user_from_oidc(claims: Dict[str, Any], tenant_id: str,
                                   user_service: UserService) -> User:
    """
    Create or update user from OIDC claims
    Auto-provision users on first login
    """

    email = claims.get('email')

    if not email:
        raise ValueError("Email claim missing from OIDC token")

    # Check if user exists
    user = await user_service.get_user_by_email(email)

    if not user:
        # Create new user
        user = await user_service.create_user({
            'email': email,
            'name': claims.get('name', email),
            'customer_id': tenant_id,
            'status': 'active',
            'password_hash': '',  # OIDC users don't have passwords
            'email_verified_at': datetime.utcnow()
        })

        logger.info("New user provisioned from OIDC",
                   user_id=user.id,
                   email=email,
                   tenant_id=tenant_id)

        # Assign default role
        role_service = RoleService()
        await role_service.assign_role(
            user_id=user.id,
            tenant_id=tenant_id,
            role=UserRole.VIEWER,  # Default role for OIDC users
            granted_by='oidc-system'
        )

    # TODO: Update user from OIDC claims (name, profile picture, etc.)
    # TODO: Map OIDC groups to Logforge roles

    return user
```

**Deliverables:**
-  OIDC provider discovery
-  Authorization initiation with PKCE
-  Callback handling and token exchange
-  ID token validation
-  User auto-provisioning

---

### Phase 3: Security & User Provisioning (2 days)

**Goal:** Production-grade security and role mapping

#### 3.1 Redis Session Storage
Use Redis to store OIDC sessions (state, code_verifier, nonce):

```python
import redis.asyncio as redis

class OIDCSessionStore:
    """Redis-based OIDC session storage"""

    def __init__(self):
        self.redis = redis.from_url(
            "redis://localhost:6379",
            decode_responses=True
        )

    async def store_session(self, state: str, data: Dict, ttl: int = 600):
        """Store OIDC session with 10-minute TTL"""
        key = f"oidc:session:{state}"
        await self.redis.setex(
            key,
            ttl,
            json.dumps(data)
        )

    async def get_session(self, state: str) -> Optional[Dict]:
        """Retrieve OIDC session"""
        key = f"oidc:session:{state}"
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def delete_session(self, state: str):
        """Delete OIDC session after use"""
        key = f"oidc:session:{state}"
        await self.redis.delete(key)
```

#### 3.2 OIDC Group to Role Mapping
**File:** `/apps/api/services/oidc_service.py` (UPDATE)

```python
async def map_oidc_groups_to_roles(self, claims: Dict, provider_config: Dict,
                                   tenant_id: str, user_id: str):
    """
    Map OIDC groups/roles to Logforge roles

    Example OIDC claim:
    {
        "groups": ["logforge-admins", "logforge-analysts"],
        "roles": ["admin", "viewer"]
    }

    Mapping configuration (stored in provider config):
    {
        "group_mapping": {
            "logforge-admins": "tenant_admin",
            "logforge-analysts": "security_analyst"
        }
    }
    """

    group_mapping = provider_config.get('group_mapping', {})

    # Extract groups from claims
    oidc_groups = claims.get('groups', [])

    # Map to Logforge roles
    role_service = RoleService()

    for oidc_group in oidc_groups:
        logforge_role = group_mapping.get(oidc_group)

        if logforge_role:
            try:
                await role_service.assign_role(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    role=UserRole(logforge_role),
                    granted_by='oidc-system'
                )

                logger.info("Role assigned from OIDC group",
                           user_id=user_id,
                           oidc_group=oidc_group,
                           role=logforge_role)

            except Exception as e:
                logger.warning("Failed to assign role from OIDC group",
                             error=str(e),
                             oidc_group=oidc_group)
```

#### 3.3 JWT Signature Validation
Use `PyJWT` with JWKS for proper token validation:

```python
import jwt
from jwt import PyJWKClient

async def validate_id_token_with_jwks(self, id_token: str, provider_config: Dict,
                                      expected_nonce: str) -> Dict[str, Any]:
    """Validate ID token using JWKS"""

    jwks_uri = provider_config['jwks_uri']

    # Create JWKS client
    jwks_client = PyJWKClient(jwks_uri)

    # Get signing key from token header
    signing_key = jwks_client.get_signing_key_from_jwt(id_token)

    # Decode and verify
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=['RS256', 'ES256'],
        audience=provider_config['client_id'],
        issuer=provider_config['issuer'],
        options={
            'verify_exp': True,
            'verify_iat': True,
            'verify_aud': True,
            'verify_iss': True
        }
    )

    # Validate nonce
    if claims.get('nonce') != expected_nonce:
        raise jwt.InvalidTokenError("Nonce mismatch")

    return claims
```

**Deliverables:**
-  Redis session storage
-  OIDC group to role mapping
-  Proper JWT signature validation
-  User profile sync from OIDC

---

### Phase 4: Testing & Documentation (1 day)

**Goal:** Test with real OIDC provider and document setup

#### 4.1 Test with Auth0 Free Tier

1. Create Auth0 account
2. Configure Auth0 application:
   - Allowed Callback URLs: `https://acme.logforge.io/auth/oidc/callback`
   - Allowed Logout URLs: `https://acme.logforge.io/login`
   - Allowed Web Origins: `https://acme.logforge.io`
3. Configure OIDC in Logforge:
   ```bash
   POST /v1/enterprise/auth/oidc/configure
   {
     "provider_name": "Auth0",
     "provider_type": "oidc",
     "client_id": "YOUR_CLIENT_ID",
     "client_secret": "YOUR_CLIENT_SECRET",
     "domain": "YOUR_TENANT.auth0.com",
     "scopes": ["openid", "profile", "email", "groups"]
   }
   ```

#### 4.2 End-to-End Testing Checklist

- [ ] User visits `acme.logforge.io/auth/oidc/login`
- [ ] Redirected to Auth0 login page
- [ ] User authenticates with Auth0
- [ ] Redirected back to `acme.logforge.io/auth/oidc/callback`
- [ ] User auto-provisioned in Logforge
- [ ] Roles assigned from Auth0 groups
- [ ] Logged in with Logforge session
- [ ] Can access dashboard with proper permissions

**Deliverables:**
-  Tested with Auth0
-  Documentation for customers
-  Setup guide for other OIDC providers

---

## = Security Considerations

### 1. PKCE (Proof Key for Code Exchange)
- **Required** for authorization code flow
- Prevents authorization code interception attacks
- Code verifier stored securely in Redis

### 2. State Parameter
- **Required** for CSRF protection
- Random 32-byte value
- Validated on callback

### 3. Nonce Parameter
- **Required** for replay attack prevention
- Included in ID token claims
- Validated during token verification

### 4. Token Validation
- **Signature verification** using JWKS
- **Expiration check** (exp claim)
- **Audience validation** (aud claim matches client_id)
- **Issuer validation** (iss claim matches provider)

### 5. HTTPS Only
- **All OIDC flows require HTTPS**
- Wildcard SSL certificate for subdomains
- No HTTP fallback allowed

---

## =Ê Database Schema Updates

### Tenants Table
```sql
ALTER TABLE tenants_mt ADD COLUMN subdomain String DEFAULT '';
CREATE INDEX idx_subdomain ON tenants_mt (subdomain);
```

### OIDC Sessions (Redis)
```
Key: oidc:session:{state}
Value: {
  "code_verifier": "...",
  "nonce": "...",
  "tenant_id": "...",
  "subdomain": "...",
  "provider_id": "...",
  "created_at": "2025-11-17T10:00:00Z"
}
TTL: 600 seconds (10 minutes)
```

---

## =€ Deployment Steps

### 1. DNS Configuration
```bash
# Add wildcard A record
*.logforge.io  ’  YOUR_SERVER_IP
```

### 2. SSL Certificate
```bash
# Get wildcard SSL from Let's Encrypt
certbot certonly --manual --preferred-challenges dns \
  -d "*.logforge.io" -d "logforge.io"
```

### 3. Redis Setup
```bash
# Install Redis
docker run -d --name redis -p 6379:6379 redis:7

# Test connection
redis-cli ping
```

### 4. Database Migration
```bash
# Run migration to add subdomain column
clickhouse-client < migrations/006_add_tenant_subdomain.sql
```

### 5. Update Environment Variables
```bash
# .env
REDIS_URL=redis://localhost:6379
LOGFORGE_BASE_URL=https://logforge.io
```

### 6. Register Middleware
```python
# main.py
app.add_middleware(TenantDetectionMiddleware)  # Before auth
app.add_middleware(UnifiedAuthMiddleware)      # After tenant detection
```

### 7. Deploy
```bash
docker-compose up -d --build
```

---

## =Ú Customer Setup Guide

### For Tenant Admins

1. **Get your subdomain**
   - Contact Logforge support or create tenant via API
   - Example: `acme.logforge.io`

2. **Configure OIDC Provider**
   - POST to `/v1/enterprise/auth/oidc/configure`
   - Provide: client_id, client_secret, domain

3. **Configure OIDC Provider Settings**
   - **Allowed Callback URLs**: `https://acme.logforge.io/auth/oidc/callback`
   - **Allowed Logout URLs**: `https://acme.logforge.io/login`

4. **Map Groups to Roles**
   - Configure group mapping in OIDC provider settings
   - Example: `logforge-admins` ’ `tenant_admin`

5. **Test Login**
   - Visit `https://acme.logforge.io/auth/oidc/login`
   - Authenticate with your OIDC provider
   - Verify you're logged into Logforge

---

## <¯ Success Metrics

- **Authentication Time**: <3 seconds from login to dashboard
- **Security**: 100% OIDC flows use PKCE + state + nonce
- **User Provisioning**: 0 manual user creation (auto-provision)
- **Role Accuracy**: 95%+ users get correct roles from group mapping
- **Uptime**: 99.9% availability for OIDC endpoints

---

## =Ë Implementation Checklist

### Phase 1: Infrastructure ó
- [ ] Configure wildcard DNS
- [ ] Install wildcard SSL certificate
- [ ] Implement TenantDetectionMiddleware
- [ ] Add subdomain column to tenants table
- [ ] Update tenant creation to generate/validate subdomains
- [ ] Test subdomain routing without OIDC

### Phase 2: OIDC Core ó
- [ ] Implement OIDCService (provider discovery, authorization, callback)
- [ ] Create OIDC authentication endpoints
- [ ] Implement PKCE flow
- [ ] Implement state validation
- [ ] Implement ID token validation
- [ ] Test with Auth0

### Phase 3: Security & Provisioning ó
- [ ] Setup Redis for session storage
- [ ] Implement OIDC group to role mapping
- [ ] Implement proper JWT signature validation
- [ ] Auto-provision users on first login
- [ ] Sync user profiles from OIDC

### Phase 4: Testing & Docs ó
- [ ] End-to-end testing with Auth0
- [ ] Test with Okta
- [ ] Create customer setup documentation
- [ ] Create admin configuration guide
- [ ] Security audit

---

## =' Dependencies

```bash
# Python packages
pip install PyJWT[crypto]  # JWT validation with JWKS
pip install redis          # Redis session storage
pip install httpx          # Async HTTP client for OIDC calls
```

---

## =Þ Support

For questions or issues:
- Documentation: `/docs/wiki/knowledge_base/M7-enterprise-features/OIDC-SSO-Architecture.md`
- API Reference: `https://acme.logforge.io/docs`

---

**Implementation Start Date:** TBD
**Estimated Completion:** 8-10 days
**Owner:** Engineering Team