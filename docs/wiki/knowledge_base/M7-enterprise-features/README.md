# Enterprise Features Documentation

## Overview

Logforge Enterprise provides advanced security, compliance, and governance features for organizations that need enterprise-grade observability with strict security and compliance requirements.

**Enterprise Tier Benefits:**
- SSO/OIDC authentication with major identity providers
- Advanced RBAC with custom roles and permissions
- Multi-tenancy with data isolation
- Compliance reporting (SOC 2, HIPAA, GDPR, ISO 27001)
- Enterprise integrations (Slack, PagerDuty, JIRA, ServiceNow)
- SLA guarantees and 24/7 priority support
- Advanced security features (API keys, MFA, IP whitelisting, audit logs)

---

## Documentation Index

### Authentication & Security

| Guide | Description | API Endpoints |
|-------|-------------|---------------|
| **[OIDC/SSO Configuration](./OIDC-SSO-Configuration-Guide.md)** | Configure Single Sign-On with Okta, Auth0, Azure AD, Google Workspace | `/v1/enterprise/auth/oidc/*` |
| **[API Keys Management](./API-Keys-Management-Guide.md)** | Generate and manage API keys for programmatic access | `/v1/enterprise/auth/api-keys/*` |
| **[MFA Setup](./MFA-Setup-Guide.md)** _(Coming Soon)_ | Multi-factor authentication configuration | `/v1/enterprise/auth/mfa/*` |

### Access Control

| Guide | Description | API Endpoints |
|-------|-------------|---------------|
| **[RBAC & Permissions](./RBAC-Permissions-Guide.md)** _(Coming Soon)_ | Role-based access control and custom roles | `/v1/enterprise/rbac/*` |
| **[User Management](./User-Management-Guide.md)** _(Coming Soon)_ | User provisioning, deprovisioning, group sync | `/v1/enterprise/users/*` |

### Compliance & Governance

| Guide | Description | API Endpoints |
|-------|-------------|---------------|
| **[Multi-Tenancy](./Multi-Tenancy-Guide.md)** _(Coming Soon)_ | Tenant management and data isolation | `/v1/enterprise/tenants/*` |
| **[Compliance Reporting](./Compliance-Reporting-Guide.md)** _(Coming Soon)_ | SOC 2, HIPAA, GDPR compliance reports | `/v1/enterprise/compliance/*` |
| **[Audit Logs](./Audit-Logs-Guide.md)** _(Coming Soon)_ | Comprehensive audit trail for all operations | `/v1/enterprise/audit-logs` |
| **[Data Retention](./Data-Retention-Guide.md)** _(Coming Soon)_ | Configure retention policies and legal holds | `/v1/enterprise/retention/*` |

### Integrations

| Guide | Description | API Endpoints |
|-------|-------------|---------------|
| **[Slack Integration](./Slack-Integration-Guide.md)** _(Coming Soon)_ | Send alerts and notifications to Slack | `/v1/enterprise/integrations/slack/*` |
| **[PagerDuty Integration](./PagerDuty-Integration-Guide.md)** _(Coming Soon)_ | Incident management with PagerDuty | `/v1/enterprise/integrations/pagerduty/*` |
| **[JIRA Integration](./JIRA-Integration-Guide.md)** _(Coming Soon)_ | Create tickets from alerts | `/v1/enterprise/integrations/jira/*` |
| **[Webhook Integration](./Webhook-Integration-Guide.md)** _(Coming Soon)_ | Custom webhooks for events | `/v1/enterprise/integrations/webhooks/*` |

### Administration

| Guide | Description | API Endpoints |
|-------|-------------|---------------|
| **[Usage & Billing](./Usage-Billing-Guide.md)** _(Coming Soon)_ | View usage metrics and billing breakdowns | `/v1/enterprise/usage/*` |
| **[Backup & Disaster Recovery](./Backup-DR-Guide.md)** _(Coming Soon)_ | Configure backup policies and DR | `/v1/enterprise/backup/*` |
| **[System Health](./System-Health-Guide.md)** _(Coming Soon)_ | Monitor system health and performance | `/v1/enterprise/system/*` |

---

## Quick Start Guides

### For Administrators

**First-Time Enterprise Setup** (30 minutes):

1. **Configure SSO** → [OIDC/SSO Guide](./OIDC-SSO-Configuration-Guide.md)
   - Set up your identity provider (Okta, Auth0, etc.)
   - Configure OIDC in Logforge
   - Test SSO login with pilot users

2. **Setup RBAC** → [RBAC Guide](./RBAC-Permissions-Guide.md) _(Coming Soon)_
   - Review default roles (admin, developer, viewer)
   - Create custom roles for your organization
   - Map IdP groups to Logforge roles

3. **Generate API Keys** → [API Keys Guide](./API-Keys-Management-Guide.md)
   - Create keys for CI/CD pipelines
   - Configure permissions and rate limits
   - Store keys in secrets manager

4. **Configure Integrations** → Integration Guides _(Coming Soon)_
   - Connect Slack for alert notifications
   - Setup PagerDuty for incident management
   - Configure webhooks for custom workflows

5. **Review Compliance Settings** → [Compliance Guide](./Compliance-Reporting-Guide.md) _(Coming Soon)_
   - Set data retention policies
   - Configure audit logging
   - Generate compliance reports

### For Developers

**Getting Started with Enterprise APIs**:

1. **Authentication**
   - Obtain API key from your administrator
   - Set environment variable: `export LOGFORGE_API_KEY=lf_prod_...`
   - Test access: `curl -H "Authorization: Bearer $LOGFORGE_API_KEY" https://api.logforge.io/v1/enterprise/health`

2. **Send Logs**
   ```bash
   curl -X POST https://api.logforge.io/v1/ingest/logs \
     -H "Authorization: Bearer $LOGFORGE_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "service": "my-service",
       "level": "info",
       "message": "Application started"
     }'
   ```

3. **Query Logs**
   ```bash
   curl -X POST https://api.logforge.io/v1/query/logs \
     -H "Authorization: Bearer $LOGFORGE_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "service=my-service AND level=ERROR",
       "start_time": "2025-11-15T00:00:00Z",
       "end_time": "2025-11-15T23:59:59Z"
     }'
   ```

---

## Security Best Practices

### 1. **Authentication**
- ✅ Use SSO/OIDC for user authentication (never use passwords for production)
- ✅ Enable MFA for all admin accounts
- ✅ Use API keys for programmatic access (not user tokens)
- ✅ Rotate API keys every 90 days
- ❌ Never hardcode credentials in source code
- ❌ Never share API keys via email or Slack

### 2. **Access Control**
- ✅ Follow principle of least privilege (give minimum required permissions)
- ✅ Use custom roles for specific team needs
- ✅ Review user permissions quarterly
- ✅ Immediately revoke access when employees leave
- ❌ Don't use admin accounts for day-to-day operations
- ❌ Don't share accounts across users

### 3. **Data Protection**
- ✅ Enable encryption at rest and in transit
- ✅ Use IP whitelisting for production API keys
- ✅ Configure appropriate data retention policies
- ✅ Enable audit logging for compliance
- ❌ Don't store PII in log messages without consent
- ❌ Don't disable security features for convenience

### 4. **Monitoring & Compliance**
- ✅ Monitor audit logs for suspicious activity
- ✅ Setup alerts for security events (failed logins, permission changes)
- ✅ Generate compliance reports regularly
- ✅ Test disaster recovery procedures quarterly
- ❌ Don't ignore security alerts
- ❌ Don't skip compliance reviews

---

## Common Enterprise Workflows

### Onboarding New Team Member

1. **IdP Administrator**: Add user to appropriate IdP groups
2. **Logforge Sync**: User automatically provisioned via SSO (JIT provisioning)
3. **Role Assignment**: User gets role based on IdP group mapping
4. **First Login**: User logs in via SSO, lands in Logforge with correct permissions
5. **Generate API Key** (if needed): User generates personal API key for development

### Rotating API Keys (Zero Downtime)

1. Generate new API key with same permissions
2. Update secrets manager with new key
3. Deploy applications to pick up new key (rolling deployment)
4. Wait 24-48 hours for all services to migrate
5. Verify old key has no recent usage
6. Revoke old API key

### Compliance Audit Preparation

1. Generate compliance report for audit period
2. Export audit logs for the period
3. Collect access control documentation
4. Document data retention policies
5. Provide evidence of encryption (at rest & in transit)
6. Show MFA enforcement for admin accounts
7. Demonstrate incident response procedures

### Incident Response (Compromised API Key)

1. **Immediate**: Revoke compromised API key via API or UI
2. **Within 15 min**: Review audit logs for unauthorized access
3. **Within 1 hour**: Generate new API key, update affected services
4. **Within 4 hours**: Investigate scope of breach, notify security team
5. **Within 24 hours**: Complete incident report, update security procedures
6. **Within 7 days**: Review and improve key management practices

---

## API Endpoint Reference

### Authentication & Authorization

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/enterprise/auth/oidc/configure` | Configure OIDC provider |
| GET | `/v1/enterprise/auth/providers` | List configured auth providers |
| PUT | `/v1/enterprise/auth/oidc/{provider_id}` | Update OIDC configuration |
| DELETE | `/v1/enterprise/auth/oidc/{provider_id}` | Delete OIDC provider |
| POST | `/v1/enterprise/auth/api-keys` | Generate API key |
| GET | `/v1/enterprise/auth/api-keys` | List API keys |
| GET | `/v1/enterprise/auth/api-keys/{key_id}` | Get API key details |
| PUT | `/v1/enterprise/auth/api-keys/{key_id}` | Update API key |
| DELETE | `/v1/enterprise/auth/api-keys/{key_id}` | Revoke API key |
| POST | `/v1/enterprise/auth/mfa/setup` | Setup MFA for user |
| POST | `/v1/enterprise/auth/mfa/verify` | Verify MFA code |

### RBAC & Permissions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/enterprise/rbac/roles` | List all roles |
| POST | `/v1/enterprise/rbac/roles` | Create custom role |
| GET | `/v1/enterprise/rbac/roles/{role_id}` | Get role details |
| PUT | `/v1/enterprise/rbac/roles/{role_id}` | Update role |
| DELETE | `/v1/enterprise/rbac/roles/{role_id}` | Delete role |
| PUT | `/v1/enterprise/rbac/users/{user_id}/roles` | Assign roles to user |
| GET | `/v1/enterprise/rbac/permissions` | Get current user permissions |

### Multi-Tenancy & Compliance

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/enterprise/tenants` | List tenants |
| POST | `/v1/enterprise/tenants` | Create tenant |
| GET | `/v1/enterprise/tenants/{tenant_id}` | Get tenant details |
| PUT | `/v1/enterprise/tenants/{tenant_id}/settings` | Update tenant settings |
| DELETE | `/v1/enterprise/tenants/{tenant_id}` | Delete tenant |
| GET | `/v1/enterprise/compliance/reports` | Generate compliance report |
| POST | `/v1/enterprise/compliance/legal-hold` | Create legal hold |
| GET | `/v1/enterprise/audit-logs` | Get audit logs |

### Integrations

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/enterprise/integrations` | List integrations |
| POST | `/v1/enterprise/integrations/slack/configure` | Configure Slack |
| GET | `/v1/enterprise/integrations/slack/status` | Get Slack status |
| POST | `/v1/enterprise/integrations/pagerduty/configure` | Configure PagerDuty |
| POST | `/v1/enterprise/integrations/webhooks` | Create webhook |

### Administration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/enterprise/usage/billing` | Get usage and billing |
| GET | `/v1/enterprise/system/health` | Get system health |
| POST | `/v1/enterprise/backup/configure` | Configure backup policy |
| GET | `/v1/enterprise/metrics` | Get enterprise metrics |
| GET | `/v1/enterprise/health` | Enterprise health check |

---

## Pricing & Plans

| Feature | Professional | Enterprise | Enterprise Plus |
|---------|-------------|------------|-----------------|
| **SSO/OIDC** | ✅ | ✅ | ✅ |
| **Custom Roles** | 3 | Unlimited | Unlimited |
| **API Keys** | 10 | 100 | Unlimited |
| **Audit Retention** | 30 days | 1 year | 7 years |
| **Compliance Reports** | ❌ | ✅ | ✅ |
| **Legal Hold** | ❌ | ✅ | ✅ |
| **Data Residency** | US only | Multi-region | Multi-region |
| **SLA** | 99.5% | 99.9% | 99.99% |
| **Support** | Business hours | 24/7 | 24/7 + TAM |
| **Integrations** | 5 | 20 | Unlimited |

---

## FAQ

**Q: How do we upgrade to Enterprise?**
A: Contact sales@logforge.io or your account manager

**Q: Can we try Enterprise features before purchasing?**
A: Yes, we offer 14-day Enterprise trial. Contact sales for access.

**Q: What happens to our data if we downgrade from Enterprise?**
A: Data retained according to your data retention policy. Some features become read-only.

**Q: Do we need to migrate data when enabling SSO?**
A: No, user accounts are automatically matched by email address

**Q: Can we mix SSO and password authentication?**
A: Yes, you can run in hybrid mode during migration period

**Q: How long does Enterprise setup take?**
A: Typical setup: 2-4 hours. Full rollout: 1-2 weeks

**Q: Do you support air-gapped/on-premises deployment?**
A: Yes, contact sales for Enterprise Plus on-premises options

**Q: Can we export all our data?**
A: Yes, full data export available via API or support ticket

---

## Support & Resources

### Documentation
- **Enterprise Docs**: https://docs.logforge.io/enterprise
- **API Reference**: https://docs.logforge.io/api
- **Security**: https://docs.logforge.io/security

### Support Channels
- **Email**: enterprise-support@logforge.io
- **Slack**: #enterprise-support (invite-only)
- **Phone**: +1-800-LOG-FRGE (24/7 for Enterprise)
- **Portal**: https://support.logforge.io

### Professional Services
- **Onboarding**: 4-week guided implementation
- **Migration**: Data migration from competitors
- **Training**: Team training sessions
- **Custom Integration**: Build custom integrations
- **Security Review**: Architecture and security review

### Emergency Contact
- **Security Incidents**: security@logforge.io
- **Critical Outages**: +1-800-LOG-DOWN
- **Emergency Key Revocation**: Use web UI (fastest) or call support

---

## Changelog

### Version 2.0 (November 2025)
- Added OIDC/SSO support for all major identity providers
- Enhanced RBAC with custom roles and fine-grained permissions
- Improved audit logging with 7-year retention option
- Added compliance reporting for SOC 2, HIPAA, GDPR, ISO 27001
- New integrations: Slack, PagerDuty, JIRA, ServiceNow

### Version 1.5 (August 2025)
- Initial Enterprise tier launch
- Basic SSO support (Okta, Auth0)
- API key management
- Audit logging (1-year retention)

---

**Last Updated**: November 15, 2025
**Maintained By**: Logforge Enterprise Team
**Feedback**: docs-feedback@logforge.io