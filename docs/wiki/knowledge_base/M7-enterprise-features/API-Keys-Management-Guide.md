# API Keys Management Guide

## Overview

API Keys provide programmatic access to Logforge APIs for automated systems, CI/CD pipelines, integrations, and scripts. Unlike user accounts, API keys are designed for machine-to-machine authentication.

**Use Cases:**
- CI/CD pipelines sending logs from automated tests
- Infrastructure monitoring agents
- Third-party integrations (Grafana, Prometheus, etc.)
- Custom scripts and automation tools
- Partner integrations

---

## How API Keys Work

### Authentication Flow

```
1. Application makes API request with API key in header
   ↓
2. Logforge validates API key
   ↓
3. Checks permissions and rate limits
   ↓
4. Processes request
   ↓
5. Returns response
```

### API Key Format

```
lf_prod_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0
│   │    └─────────────────────────────────────────── Random token (40 chars)
│   └──────────────────────────────────────────────── Environment (prod/dev/test)
└──────────────────────────────────────────────────── Prefix (lf)
```

---

## Creating API Keys

### Via Web UI

1. Navigate to **Settings** → **Enterprise** → **API Keys**
2. Click **Generate New API Key**
3. Configure:
   - **Name**: "Production CI/CD Pipeline"
   - **Description**: "Used by GitHub Actions to send test logs"
   - **Permissions**: Select required permissions
   - **Expiration**: Set expiry date (recommended: 90 days)
   - **Rate Limit**: Requests per minute (default: 10,000)
   - **IP Whitelist**: Optional IP restrictions

4. Click **Generate**
5. **IMPORTANT**: Copy the API key immediately (shown only once)
6. Store securely in your secrets manager

### Via API

```bash
curl -X POST https://api.logforge.io/v1/enterprise/auth/api-keys \
  -H "Content-Type: application/json" \
  -H "X-Customer-ID: your-tenant-id" \
  -H "Authorization: Bearer your-admin-token" \
  -d '{
    "name": "Production CI/CD Pipeline",
    "description": "GitHub Actions integration for test log ingestion",
    "permissions": [
      "logs:write",
      "metrics:write",
      "traces:write"
    ],
    "expires_at": "2026-02-15T23:59:59Z",
    "rate_limit": 10000,
    "ip_whitelist": [
      "192.168.1.100",
      "10.0.0.0/24",
      "github-actions-ip-range"
    ]
  }'
```

**Response:**
```json
{
  "api_key_id": "key_abc123xyz",
  "api_key": "lf_prod_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0",
  "name": "Production CI/CD Pipeline",
  "permissions": ["logs:write", "metrics:write", "traces:write"],
  "expires_at": "2026-02-15T23:59:59Z",
  "created_at": "2025-11-15T10:30:00Z",
  "rate_limit": 10000,
  "ip_whitelist": ["192.168.1.100", "10.0.0.0/24"],
  "warning": "This API key will only be shown once. Store it securely."
}
```

---

## Permissions System

### Available Permissions

| Permission | Description | Use Case |
|------------|-------------|----------|
| `logs:read` | Query and read logs | Dashboards, analytics |
| `logs:write` | Ingest logs | Log collectors, agents |
| `metrics:read` | Query metrics | Grafana integration |
| `metrics:write` | Ingest metrics | Prometheus remote write |
| `traces:read` | Query traces | APM tools |
| `traces:write` | Ingest traces | OpenTelemetry collectors |
| `alerts:read` | View alerts | Monitoring systems |
| `alerts:write` | Create/modify alerts | Infrastructure as Code |
| `dashboards:read` | View dashboards | Embedding, exports |
| `dashboards:write` | Create dashboards | Terraform providers |
| `admin:read` | View admin settings | Audit tools |
| `admin:write` | Modify settings | Automation scripts |

### Permission Scopes

**Read-Only Keys** (safest for integrations):
```json
{
  "permissions": ["logs:read", "metrics:read", "traces:read"]
}
```

**Ingestion-Only Keys** (for data collectors):
```json
{
  "permissions": ["logs:write", "metrics:write", "traces:write"]
}
```

**Full Access Keys** (for admin automation):
```json
{
  "permissions": ["*"]
}
```

---

## Using API Keys

### HTTP Header Authentication

```bash
curl -X POST https://api.logforge.io/v1/ingest/logs \
  -H "Authorization: Bearer lf_prod_a1b2c3d4e5..." \
  -H "Content-Type: application/json" \
  -d '{
    "service": "web-api",
    "level": "info",
    "message": "User logged in"
  }'
```

### SDK Usage

**Python:**
```python
from logforge import LogforgeClient

client = LogforgeClient(
    api_key="lf_prod_a1b2c3d4e5...",
    tenant_id="your-tenant-id"
)

client.ingest_log({
    "service": "web-api",
    "level": "info",
    "message": "User logged in"
})
```

**Node.js:**
```javascript
const Logforge = require('@logforge/sdk');

const client = new Logforge({
  apiKey: process.env.LOGFORGE_API_KEY,
  tenantId: process.env.LOGFORGE_TENANT_ID
});

await client.ingestLog({
  service: 'web-api',
  level: 'info',
  message: 'User logged in'
});
```

---

## Managing API Keys

### List All API Keys

```bash
curl -X GET https://api.logforge.io/v1/enterprise/auth/api-keys \
  -H "X-Customer-ID: your-tenant-id" \
  -H "Authorization: Bearer your-admin-token"
```

**Response:**
```json
{
  "api_keys": [
    {
      "api_key_id": "key_abc123",
      "name": "Production CI/CD Pipeline",
      "description": "GitHub Actions integration",
      "permissions": ["logs:write", "metrics:write"],
      "created_at": "2025-11-15T10:30:00Z",
      "expires_at": "2026-02-15T23:59:59Z",
      "last_used_at": "2025-11-15T14:22:00Z",
      "usage_count": 1523,
      "rate_limit": 10000,
      "ip_whitelist": ["192.168.1.100"],
      "status": "active"
    },
    {
      "api_key_id": "key_xyz789",
      "name": "Grafana Dashboard",
      "permissions": ["logs:read", "metrics:read"],
      "status": "expired",
      "expires_at": "2025-10-01T00:00:00Z"
    }
  ],
  "total": 2
}
```

### Update API Key

**Use cases:**
- Rotate key after potential exposure
- Update permissions
- Extend expiration
- Modify rate limits
- Update IP whitelist

```bash
curl -X PUT https://api.logforge.io/v1/enterprise/auth/api-keys/key_abc123 \
  -H "Content-Type: application/json" \
  -H "X-Customer-ID: your-tenant-id" \
  -H "Authorization: Bearer your-admin-token" \
  -d '{
    "expires_at": "2026-12-31T23:59:59Z",
    "rate_limit": 20000,
    "ip_whitelist": ["192.168.1.0/24"]
  }'
```

### Revoke API Key

**Immediate revocation** (cannot be undone):

```bash
curl -X DELETE https://api.logforge.io/v1/enterprise/auth/api-keys/key_abc123 \
  -H "X-Customer-ID: your-tenant-id" \
  -H "Authorization: Bearer your-admin-token"
```

**Response:**
```json
{
  "status": "revoked",
  "api_key_id": "key_abc123",
  "revoked_at": "2025-11-15T15:00:00Z",
  "message": "API key revoked successfully. All requests with this key will fail immediately."
}
```

---

## Security Best Practices

### Storage

#### ❌ **Never Do This:**
```bash
# DON'T hardcode in source code
API_KEY = "lf_prod_a1b2c3d4e5..."

# DON'T commit to git
echo "LOGFORGE_API_KEY=lf_prod_..." >> .env
git add .env
```

#### ✅ **Do This:**
```bash
# Use environment variables
export LOGFORGE_API_KEY=$(aws secretsmanager get-secret-value --secret-id logforge-api-key --query SecretString --output text)

# Use secrets managers
# AWS Secrets Manager
# HashiCorp Vault
# GitHub Secrets
# Kubernetes Secrets
```

### Rotation

**Recommended rotation schedule:**
- **Production keys**: Every 90 days
- **Development keys**: Every 180 days
- **After employee departure**: Immediate
- **After potential exposure**: Immediate

**Zero-downtime rotation:**
```bash
# 1. Create new API key
NEW_KEY=$(curl -X POST .../api-keys ... | jq -r '.api_key')

# 2. Update secrets manager
aws secretsmanager update-secret --secret-id logforge-api-key --secret-string "$NEW_KEY"

# 3. Wait 24 hours for all services to pick up new key

# 4. Revoke old API key
curl -X DELETE .../api-keys/OLD_KEY_ID
```

### IP Whitelisting

**Recommended for:**
- Production environments
- Known static IPs
- VPN/corporate network access

```json
{
  "ip_whitelist": [
    "203.0.113.10",           // Single IP
    "192.168.1.0/24",         // CIDR range
    "10.0.0.0/8"              // Private network
  ]
}
```

### Rate Limiting

**Prevent abuse and control costs:**
```json
{
  "rate_limit": 10000,  // Requests per minute
  "burst_limit": 15000  // Temporary burst allowance
}
```

**What happens when limit exceeded:**
- HTTP 429 Too Many Requests
- Retry-After header indicates wait time
- Request not processed (not counted against quota)

---

## Monitoring & Alerts

### Monitor API Key Usage

```bash
curl -X GET https://api.logforge.io/v1/enterprise/auth/api-keys/key_abc123/usage \
  -H "X-Customer-ID: your-tenant-id" \
  -H "Authorization: Bearer your-admin-token" \
  -G --data-urlencode 'period=7d'
```

**Response:**
```json
{
  "api_key_id": "key_abc123",
  "period": {
    "start": "2025-11-08T00:00:00Z",
    "end": "2025-11-15T00:00:00Z"
  },
  "statistics": {
    "total_requests": 145230,
    "successful_requests": 144890,
    "failed_requests": 340,
    "rate_limited_requests": 12,
    "avg_requests_per_day": 20747,
    "peak_requests_per_minute": 892,
    "data_ingested_gb": 23.4
  },
  "usage_by_endpoint": [
    {
      "endpoint": "/v1/ingest/logs",
      "request_count": 120000,
      "percentage": 82.6
    },
    {
      "endpoint": "/v1/query/logs",
      "request_count": 25230,
      "percentage": 17.4
    }
  ],
  "usage_by_ip": [
    {
      "ip": "192.168.1.100",
      "request_count": 140000,
      "location": "US-East"
    },
    {
      "ip": "10.0.1.50",
      "request_count": 5230,
      "location": "Internal"
    }
  ]
}
```

### Setup Alerts

**Alert when API key is about to expire:**
```bash
curl -X POST https://api.logforge.io/v1/alerts/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "API Key Expiring Soon",
    "condition": "api_key_days_until_expiry < 7",
    "actions": [
      {
        "type": "email",
        "recipients": ["admin@company.com"]
      },
      {
        "type": "slack",
        "channel": "#security-alerts"
      }
    ]
  }'
```

**Alert on unusual usage:**
```bash
{
  "name": "API Key Unusual Usage",
  "condition": "api_key_requests_per_minute > baseline * 3",
  "actions": [
    {"type": "email", "recipients": ["security@company.com"]}
  ]
}
```

---

## Compliance & Audit

### Audit Trail

All API key operations are logged:
```bash
curl -X GET https://api.logforge.io/v1/enterprise/audit-logs \
  -H "X-Customer-ID: your-tenant-id" \
  -G --data-urlencode 'action_types=api_key_created,api_key_revoked,api_key_used'
```

**Response:**
```json
{
  "audit_logs": [
    {
      "timestamp": "2025-11-15T10:30:00Z",
      "action": "api_key_created",
      "actor": "admin@company.com",
      "resource": "key_abc123",
      "details": {
        "name": "Production CI/CD Pipeline",
        "permissions": ["logs:write"]
      }
    },
    {
      "timestamp": "2025-11-15T15:00:00Z",
      "action": "api_key_revoked",
      "actor": "admin@company.com",
      "resource": "key_old789",
      "reason": "Rotation after 90 days"
    }
  ]
}
```

---

## Troubleshooting

### Issue: "Invalid API Key"

**Possible causes:**
1. API key was revoked
2. API key expired
3. Typo in API key
4. Using development key in production

**Solution:**
- Verify key is active: `GET /v1/enterprise/auth/api-keys`
- Check expiration date
- Generate new key if needed

### Issue: "Permission Denied"

**Cause:** API key doesn't have required permission

**Solution:**
```bash
# Check current permissions
curl -X GET .../api-keys/key_abc123

# Update permissions
curl -X PUT .../api-keys/key_abc123 \
  -d '{"permissions": ["logs:write", "metrics:write"]}'
```

### Issue: "Rate Limit Exceeded"

**Cause:** Exceeded requests per minute limit

**Solution:**
- Implement exponential backoff
- Request rate limit increase
- Distribute load across multiple keys

```python
import time
import requests

def send_with_retry(data, max_retries=3):
    for attempt in range(max_retries):
        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            time.sleep(retry_after)
            continue

        return response

    raise Exception("Max retries exceeded")
```

### Issue: "IP Not Whitelisted"

**Cause:** Request from non-whitelisted IP

**Solution:**
```bash
# Update IP whitelist
curl -X PUT .../api-keys/key_abc123 \
  -d '{
    "ip_whitelist": [
      "192.168.1.100",
      "NEW_IP_HERE"
    ]
  }'
```

---

## Migration Guides

### Migrating from User Tokens to API Keys

**Why migrate:**
- Better security (scoped permissions)
- No session expiration issues
- Dedicated rate limits
- Easier key rotation

**Migration steps:**
1. Create API key with same permissions as user
2. Update application configuration
3. Test thoroughly
4. Remove user token dependency
5. Disable user account if no longer needed

---

## FAQ

**Q: How many API keys can we create?**
A: No hard limit, but we recommend < 50 keys per tenant for manageability

**Q: Can API keys access the web UI?**
A: No, API keys are for API access only. Use SSO/OIDC for UI access.

**Q: What if we lose an API key?**
A: Revoke the lost key immediately and generate a new one

**Q: Can we share API keys across teams?**
A: Not recommended. Create separate keys per team/service for better audit trails

**Q: Do API keys work with all endpoints?**
A: Yes, but some admin endpoints require user authentication

**Q: Can we set custom rate limits?**
A: Yes, contact support for custom limits above 100,000 req/min

---

## Support

For API key issues:
- **Documentation**: https://docs.logforge.io/enterprise/api-keys
- **Support Email**: api-support@logforge.io
- **Emergency Key Revocation**: security@logforge.io (24/7)