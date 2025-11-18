# Enterprise Security Architecture

## Overview

This document explains how Logforge Enterprise protects sensitive customer data, credentials, and ensures compliance with industry security standards.

**Security Principles:**
- Defense in depth (multiple layers of security)
- Zero trust architecture (verify everything)
- Encryption everywhere (at rest and in transit)
- Principle of least privilege
- Complete audit trail

---

## Secrets Management

### Client Secret Storage (OIDC, OAuth, API Keys)

**User Question: "Why should the client_secret be saved in our DB?"**

#### The Challenge

When customers configure OIDC/SSO, Logforge needs to store the `client_secret` to:
1. Exchange authorization codes for access tokens (OAuth flow)
2. Refresh expired tokens
3. Validate user identity on every login

**Without storing the secret**, Logforge cannot complete the authentication flow.

#### Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Customer Input                            │
│  client_secret: "super_secret_from_okta_123"                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Application Layer (FastAPI)                     │
│  - Validates input                                           │
│  - Passes to encryption service                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Encryption Service                              │
│  ┌──────────────────────────────────────────────────┐       │
│  │ 1. Get encryption key from KMS/HSM               │       │
│  │ 2. Encrypt secret using AES-256-GCM              │       │
│  │ 3. Generate unique IV (initialization vector)    │       │
│  │ 4. Create authentication tag (prevents tampering)│       │
│  │ 5. Return encrypted blob                         │       │
│  └──────────────────────────────────────────────────┘       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Database (ClickHouse)                           │
│  ┌──────────────────────────────────────────────────┐       │
│  │ client_secret_encrypted: [binary blob]           │       │
│  │ encryption_key_id: "key_rotation_2025_11"        │       │
│  │ iv: [random bytes]                               │       │
│  │ auth_tag: [authentication tag]                   │       │
│  └──────────────────────────────────────────────────┘       │
│                                                              │
│  What's NOT stored:                                         │
│  ❌ Plaintext client_secret                                 │
│  ❌ Encryption key itself                                   │
└─────────────────────────────────────────────────────────────┘
```

### Encryption Implementation

**Algorithm**: AES-256-GCM (Galois/Counter Mode)
- **Key size**: 256 bits
- **Mode**: GCM (provides both confidentiality and authenticity)
- **IV**: 96 bits (unique per encryption)
- **Authentication tag**: 128 bits (detects tampering)

**Key Management**:
```python
# Simplified example (actual implementation uses KMS)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

class SecretsManager:
    def __init__(self):
        # In production: fetch from AWS KMS, Azure Key Vault, or HashiCorp Vault
        self.encryption_key = self._get_encryption_key_from_kms()
        self.aesgcm = AESGCM(self.encryption_key)

    def encrypt_secret(self, plaintext_secret: str) -> dict:
        """Encrypt a secret for storage"""
        # Generate unique IV for this encryption
        iv = os.urandom(12)  # 96 bits

        # Encrypt + authenticate
        ciphertext = self.aesgcm.encrypt(
            iv,
            plaintext_secret.encode('utf-8'),
            associated_data=None
        )

        return {
            "encrypted_data": ciphertext,
            "iv": iv,
            "key_id": "key_rotation_2025_11"
        }

    def decrypt_secret(self, encrypted_data: bytes, iv: bytes) -> str:
        """Decrypt a secret for use"""
        plaintext = self.aesgcm.decrypt(iv, encrypted_data, associated_data=None)
        return plaintext.decode('utf-8')
```

**Key Rotation** (Automated, Zero Downtime):
1. Generate new encryption key every 90 days
2. New secrets encrypted with new key
3. Old secrets re-encrypted during background job
4. Old key retired after all secrets migrated
5. All tracked via `encryption_key_id` field

### Secrets Lifecycle

```
┌───────────────┐
│ Creation      │ → Encrypted with current key → Stored in DB
└───────────────┘

┌───────────────┐
│ Usage         │ → Decrypted in-memory → Used for API call → Cleared from memory
└───────────────┘

┌───────────────┐
│ Rotation      │ → Old secret marked for deletion → New secret encrypted → Stored
└───────────────┘

┌───────────────┐
│ Deletion      │ → Immediate removal from DB → Encryption key deleted → Irreversible
└───────────────┘
```

---

## Authentication Flow Security

### OIDC/SSO Authentication

**Complete security flow:**

```
1. User visits Logforge login page
   ↓
2. Clicks "Sign in with Okta"
   ↓
3. Logforge redirects to Okta with:
   - client_id (public, not secret)
   - redirect_uri (registered in Okta)
   - state (random token to prevent CSRF)
   - nonce (prevents replay attacks)
   ↓
4. User authenticates with Okta (MFA enforced by Okta)
   ↓
5. Okta redirects back with authorization code
   ↓
6. Logforge backend (server-side only):
   - Validates state parameter (CSRF protection)
   - Decrypts client_secret from DB
   - Exchanges code for tokens using client_secret
   - Validates ID token signature (JWT verification)
   - Validates nonce (replay protection)
   - Clears client_secret from memory
   ↓
7. User session created (secure, httpOnly cookie)
   ↓
8. User logged in
```

**Security guarantees:**
- ✅ `client_secret` never sent to browser (server-side only)
- ✅ `client_secret` only decrypted when needed, immediately cleared
- ✅ CSRF protection via `state` parameter
- ✅ Replay attack prevention via `nonce`
- ✅ Token signature validation (cryptographic verification)
- ✅ TLS 1.3 for all communication

### API Key Authentication

```
1. Client sends request with API key in header:
   Authorization: Bearer lf_prod_abc123...
   ↓
2. Logforge API Gateway:
   - Extracts API key
   - Hashes API key using SHA-256
   - Looks up hash in database (NOT plaintext key)
   ↓
3. If hash matches:
   - Load permissions for this key
   - Check rate limits
   - Check IP whitelist
   - Validate expiration
   ↓
4. Request processed with key's permissions
   ↓
5. Log API key usage (audit trail)
```

**API Key Storage**:
```
When created:
  api_key_plaintext = "lf_prod_abc123..."  (shown to user ONCE)
  api_key_hash = SHA-256(api_key_plaintext)  (stored in DB)

Database stores:
  {
    "api_key_hash": "a1b2c3d4...",  (one-way hash)
    "permissions": [...],
    "rate_limit": 10000,
    "expires_at": "2026-11-15"
  }

Validation:
  incoming_hash = SHA-256(user_provided_key)
  if incoming_hash == stored_hash:
    allow request
```

**Why hash instead of encrypt?**
- One-way hashing prevents extraction (even by administrators)
- If database leaked, API keys cannot be recovered
- Similar to password hashing best practices

---

## Data Protection

### Encryption at Rest

**Database Level**:
```
ClickHouse Database
├── Logs (logs_normalized_mt, logs_raw_mt)
│   └── Encrypted using: Transparent Data Encryption (TDE)
│       └── Algorithm: AES-256-XTS
│       └── Key: Managed by Cloud Provider KMS
│
├── Metrics (metrics_mt)
│   └── Encrypted: Same as logs
│
├── Sensitive Fields (client_secret, api_key_hash, etc.)
│   └── Encrypted using: Application-level encryption (AES-256-GCM)
│       └── Key: Managed by KMS with rotation
│
└── Backups
    └── Encrypted: AES-256-GCM with separate key
```

**File Storage (S3/Blob Storage)**:
- All files encrypted with AES-256
- Server-Side Encryption (SSE) with KMS
- Separate encryption keys per tenant (multi-tenancy isolation)

### Encryption in Transit

**All communication uses TLS 1.3**:
```
Client ←──TLS 1.3──→ API Gateway ←──TLS 1.3──→ Backend Services
  │                                                    │
  └─ Certificate pinning (mobile apps)                └─ Mutual TLS (mTLS)
  └─ HSTS enabled                                     └─ Service mesh encryption
```

**Cipher suites** (in order of preference):
1. `TLS_AES_256_GCM_SHA384`
2. `TLS_AES_128_GCM_SHA256`
3. `TLS_CHACHA20_POLY1305_SHA256`

**Disabled** (insecure):
- ❌ TLS 1.0, TLS 1.1
- ❌ SSL 3.0, SSL 2.0
- ❌ All RC4, MD5, DES ciphers

---

## Access Control

### Multi-Layered Access Control

```
Layer 1: Network Security
├── IP Whitelisting
├── DDoS Protection (Cloudflare)
└── WAF Rules (OWASP Top 10)

Layer 2: Authentication
├── SSO/OIDC (enterprise)
├── API Keys (programmatic)
├── MFA (required for admins)
└── Session Management (secure cookies)

Layer 3: Authorization (RBAC)
├── Role-Based Access Control
├── Fine-Grained Permissions
├── Resource-Level Policies
└── Attribute-Based Access (coming soon)

Layer 4: Data Access
├── Tenant Isolation (customer_id filtering)
├── Field-Level Masking (PII protection)
├── Query Restrictions
└── Audit Logging
```

### Permission Model

**Hierarchical Permissions**:
```
admin
├── logs:*
│   ├── logs:read
│   ├── logs:write
│   └── logs:delete
├── metrics:*
├── alerts:*
└── admin:*

developer
├── logs:read
├── logs:write
├── metrics:read
└── dashboards:write

viewer
├── logs:read
└── dashboards:read
```

**Enforcement Points**:
1. **API Gateway**: Validates API key/token
2. **Authorization Service**: Checks permissions
3. **Database Query**: Adds tenant_id filter
4. **Response Filter**: Masks sensitive fields

---

## Audit & Compliance

### Audit Logging

**What's logged:**
```json
{
  "timestamp": "2025-11-15T10:30:00.000Z",
  "event_id": "evt_abc123",
  "event_type": "oidc_config_updated",
  "actor": {
    "user_id": "user_123",
    "email": "admin@company.com",
    "ip_address": "203.0.113.10",
    "user_agent": "Mozilla/5.0..."
  },
  "resource": {
    "type": "oidc_provider",
    "id": "oidc_provider_xyz",
    "name": "Acme Okta Production"
  },
  "action": "update",
  "changes": {
    "fields_modified": ["client_secret", "scopes"],
    "old_values": null,  // Secrets not logged
    "new_values": null
  },
  "result": "success",
  "tenant_id": "tenant_acme_corp"
}
```

**Retention**:
- Standard: 1 year
- Enterprise: 7 years
- Legal Hold: Indefinite

**Immutable Storage**:
- Audit logs written to append-only storage
- Cryptographically signed (prevents tampering)
- Stored in separate database (isolation)

### Compliance Frameworks

#### SOC 2 Type II

**Coverage:**
- Security: Access controls, encryption, monitoring
- Availability: 99.9% uptime SLA
- Confidentiality: Data isolation, encryption
- Privacy: GDPR compliance, data residency

#### HIPAA

**PHI Protection:**
- Encryption at rest and in transit
- Access controls and audit logging
- Data backup and disaster recovery
- Business Associate Agreements (BAA)

#### GDPR

**Requirements:**
- Data residency (EU region option)
- Right to erasure (data deletion API)
- Data portability (export API)
- Consent tracking (audit logs)
- DPO contact information

---

## Incident Response

### Security Incident Workflow

```
Detection
├── Automated: Anomaly detection, failed auth attempts
├── Reported: Customer report, security researcher
└── Discovered: Internal audit, penetration testing
   ↓
Triage (< 15 minutes)
├── Classify severity (P0, P1, P2, P3)
├── Assemble response team
└── Create incident ticket
   ↓
Containment (< 1 hour for P0)
├── Revoke compromised credentials
├── Block malicious IPs
├── Isolate affected systems
└── Preserve evidence
   ↓
Investigation (< 24 hours)
├── Determine root cause
├── Identify affected customers
├── Assess data exposure
└── Document timeline
   ↓
Remediation (< 7 days)
├── Deploy security patches
├── Rotate credentials
├── Update security controls
└── Notify affected parties
   ↓
Post-Incident (< 30 days)
├── Complete incident report
├── Customer communication
├── Update security procedures
└── Schedule security review
```

### Breach Notification

**Timeline** (GDPR compliance):
- **T+0**: Incident detected
- **T+24h**: Management notified
- **T+72h**: Regulatory notification (if required)
- **T+7d**: Customer notification (if PII affected)
- **T+30d**: Post-incident report published

---

## Security Monitoring

### Continuous Monitoring

**Metrics Monitored**:
```yaml
Authentication:
  - Failed login attempts (threshold: 5 per minute)
  - Suspicious login locations
  - MFA failures
  - API key usage anomalies

Access Control:
  - Permission changes
  - Role assignments
  - Privilege escalation attempts
  - Unauthorized access attempts

Data Access:
  - Large data exports
  - Unusual query patterns
  - Cross-tenant access attempts
  - Sensitive field access

System Security:
  - Vulnerability scan results
  - Patch compliance
  - Certificate expiration
  - Encryption key rotation status
```

### Alerting

**Critical Alerts** (page on-call engineer):
- Multiple failed admin logins
- API key created with admin permissions
- Large data export (> 1 TB)
- Encryption key rotation failure
- Database credential change

**High Priority** (alert security team):
- API key used from new country
- Unusual API usage spike
- Failed MFA attempts
- Permission changes

---

## Disaster Recovery

### Backup Strategy

**RPO (Recovery Point Objective)**: 15 minutes
**RTO (Recovery Time Objective)**: 4 hours

```
Continuous Backups
├── Database: Every 15 minutes (incremental)
├── Configuration: Real-time replication
└── Secrets: Encrypted backup every 1 hour

Daily Backups
├── Full database snapshot
├── Retention: 30 days
└── Geo-redundant storage

Weekly Backups
├── Full system backup
├── Retention: 1 year
└── Cold storage (Glacier)
```

### High Availability

```
Production Architecture
├── Multi-AZ Deployment (3+ availability zones)
├── Auto-scaling (2-100 instances)
├── Load Balancing (health checks every 30s)
├── Database Replication (primary + 2 replicas)
└── Failover (automatic, < 60s)
```

---

## Security Testing

### Regular Security Assessments

| Activity | Frequency | Last Completed |
|----------|-----------|----------------|
| Penetration Testing | Quarterly | Nov 2025 |
| Vulnerability Scanning | Weekly | Nov 15, 2025 |
| Security Code Review | Every PR | Continuous |
| Dependency Scanning | Daily | Nov 15, 2025 |
| Infrastructure Audit | Monthly | Nov 2025 |
| SOC 2 Audit | Annual | Oct 2025 |
| Bug Bounty Program | Continuous | Active |

### Vulnerability Management

**SLA for Patching**:
- Critical: 24 hours
- High: 7 days
- Medium: 30 days
- Low: 90 days

---

## Customer Security Controls

### What Customers Can Configure

**Authentication:**
- SSO/OIDC providers
- MFA enforcement policies
- Session timeout duration
- IP whitelisting

**Access Control:**
- Custom roles and permissions
- User/group assignments
- API key policies

**Data Protection:**
- Data retention policies
- Field masking rules
- Legal holds

**Monitoring:**
- Security alerts
- Audit log exports
- Compliance reports

---

## FAQ

**Q: How is our client_secret protected?**
A: Encrypted with AES-256-GCM, stored in encrypted database, keys managed by KMS, rotated every 90 days

**Q: Can Logforge employees access our client_secret?**
A: No. Even with database access, they only see encrypted blobs. Decryption requires KMS access which is logged and restricted.

**Q: What if your encryption keys are compromised?**
A: Keys stored in HSM (Hardware Security Module), automatic rotation, immediate key revocation capability, customer notification within 24h

**Q: How do we know our data is isolated from other tenants?**
A: Every query includes `customer_id` filter (enforced at database level), separate encryption keys per tenant, regular security audits

**Q: Can we use our own encryption keys?**
A: Yes, BYOK (Bring Your Own Key) available in Enterprise Plus tier

**Q: Do you support on-premises deployment for air-gapped environments?**
A: Yes, contact sales for Enterprise Plus on-premises options

**Q: How often do you rotate encryption keys?**
A: Automatically every 90 days. You can trigger manual rotation anytime.

**Q: What happens if we delete our OIDC configuration?**
A: Client secret immediately purged from database, encryption key deleted, irreversible (cannot be recovered)

---

## Security Contacts

**General Security:** security@logforge.io
**Vulnerability Reports:** security@logforge.io (PGP key available)
**Bug Bounty:** hackerone.com/logforge
**Compliance:** compliance@logforge.io
**DPO (GDPR):** dpo@logforge.io
**Emergency:** +1-800-LOG-SAFE (24/7)

---

**Last Updated**: November 15, 2025
**Security Team**: security@logforge.io
**Report Issues**: security@logforge.io