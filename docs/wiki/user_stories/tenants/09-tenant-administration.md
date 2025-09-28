# Tenant User Story: Tenant Administration & Self-Service Management

## Story
**As a** Tenant Administrator (Customer Organization Admin)  
**I want to** manage my organization's users, settings, and resources within our tenant  
**So that** I can maintain security, compliance, and operational efficiency for my organization

## User Journey

### 1. Access Tenant Administration Dashboard
- Tenant admin logs into Customer UI at `http://localhost:3001`
- Authenticates via `POST /v1/auth/login` with tenant admin credentials
- Navigates to Organization Settings section (`/organization`)
- Views tenant administration dashboard with organization metrics:
  - Organization users: 47 across 6 teams
  - Storage utilization: 340GB (45% of allocated quota)
  - Monthly log volume: 2.8M events
  - Active alerts: 12 (3 critical, 9 warnings)

### 2. Tenant User Management
- Admin accesses user management for their organization
- System calls `GET /v1/users?tenant_id=my-org` with X-Customer-ID header
- Views organization user list with:
  - User profiles and team assignments
  - Role permissions within tenant scope
  - Last activity and login status
  - License/seat utilization
- Performs tenant user operations:
  - Invite new users via `POST /v1/auth/invite`
  - Assign tenant roles via `POST /v1/users/{user_id}/roles`
  - Reset user passwords via `POST /v1/auth/password/reset`
  - Deactivate users via `PUT /v1/users/{user_id}` (status: inactive)

### 3. Tenant Role & Permission Management
- Admin configures organization-specific permissions
- System calls `GET /v1/roles?tenant_scope=true`
- Views available tenant roles:
  - **Tenant Admin**: Full organizational control
  - **Security Analyst**: Security analytics and incident response
  - **DevOps Engineer**: Observability, alerts, and dashboards
  - **Compliance Officer**: Compliance reporting and audit access
  - **Viewer**: Read-only access to logs and dashboards
- Creates custom tenant role:
  - Role name: "Application Support Lead"
  - Permissions: Application log access, limited alerting
  - Team scope: Application Support team only
- System calls `POST /v1/roles` with tenant-specific permissions

### 4. Tenant Data & Storage Management
- Admin manages organization's data governance
- System calls `GET /v1/storage/usage` to view tenant storage metrics
- Reviews data breakdown:
  - **Application logs**: 180GB (critical business data)
  - **Security logs**: 95GB (compliance requirement)
  - **Debug logs**: 65GB (development data)
- Configures tenant retention policies:
  - Application logs: 2 years retention
  - Security logs: 5 years (compliance)
  - Debug logs: 90 days (cost optimization)
- Updates policies via `PUT /v1/storage/retention-policies`

### 5. Tenant Integration Configuration
- Admin sets up organization-specific integrations
- System calls `GET /v1/subscription/features` to view available integrations
- Configures tenant integrations:
  - **Slack**: Organization Slack workspace for alerts
  - **JIRA**: Internal ticketing system for incidents
  - **Active Directory**: SSO for organization users
- Sets up Slack integration via tenant configuration
- Tests integration via `POST /v1/alerts/notifications/test`

### 6. Tenant Security & Compliance
- Admin monitors organization security posture
- System calls `GET /v1/security/dashboard` (tenant-scoped)
- Reviews tenant security metrics:
  - Security events: 23 (last 30 days)
  - Failed login attempts: 8 (within normal range)
  - Suspicious activities: 2 (investigated and resolved)
  - Compliance score: 96% (4% gap in documentation)
- Configures tenant-specific security rules
- Downloads compliance reports for internal audit

### 7. Tenant Subscription & Usage Analytics
- Admin reviews organization usage and billing
- System calls `GET /v1/usage/current/{tenant_id}`
- Views detailed tenant usage:
  - **Log ingestion**: 85GB this month (within 100GB limit)
  - **Query volume**: 15K queries (unlimited plan)
  - **User seats**: 47 of 50 allocated
  - **Storage**: 340GB of 500GB quota
- Reviews billing information via `GET /v1/subscription/billing`
- Plans for subscription changes based on growth

### 8. Tenant Dashboard & Monitoring Setup
- Admin creates organization-specific dashboards
- System calls `GET /v1/dashboards` to view existing dashboards
- Creates custom dashboards for different teams:
  - **Executive Dashboard**: High-level KPIs and business metrics
  - **Operations Dashboard**: Service health and performance
  - **Security Dashboard**: Threat detection and incident status
- Configures dashboard sharing within organization
- Sets up automated dashboard reports via `POST /v1/dashboards/schedule`

### 9. Tenant Alert & Notification Management
- Admin configures organization alert strategy
- System calls `GET /v1/alerts/rules` (tenant-scoped)
- Creates tenant-specific alert rules:
  - **High Error Rate**: Application error rate > 5%
  - **Security Incident**: Critical security events
  - **Storage Limit**: Storage usage > 80% of quota
- Configures alert routing:
  - Critical alerts → Security team + Management
  - Operational alerts → DevOps team
  - Business alerts → Management team
- Sets up escalation policies via `PUT /v1/alerts/rules/{rule_id}`

### 10. Tenant Team & Workspace Management
- Admin organizes users into functional teams
- Creates team workspaces for different functions:
  - **Development Team**: Access to application and debug logs
  - **Security Team**: Full security analytics and incident response
  - **Operations Team**: Infrastructure and service monitoring
  - **Management Team**: Executive dashboards and reports
- Assigns team-based permissions and resource quotas
- Configures team-specific data access controls

### 11. Tenant Backup & Data Export
- Admin ensures organization data protection
- System calls `GET /v1/usage/export-options`
- Configures data export policies:
  - **Monthly exports**: Compliance and audit requirements
  - **On-demand exports**: Investigation and analysis needs
  - **Emergency exports**: Incident response and forensics
- Sets up automated backup notifications
- Tests data recovery procedures

### 12. Tenant API & Developer Access
- Admin manages organization's API access
- System calls `GET /v1/enterprise/auth/api-keys` (tenant-scoped)
- Creates API keys for different use cases:
  - **Application Integration**: Log ingestion from internal apps
  - **Automation Scripts**: Automated reporting and alerting
  - **Third-party Tools**: Integration with external SIEM/monitoring
- Configures API rate limits and access controls
- Monitors API usage and security

## API Endpoints Used
- `GET /v1/users` - Tenant user management (with X-Customer-ID)
- `POST /v1/auth/invite` - User invitation within tenant
- `GET /v1/roles?tenant_scope=true` - Tenant role management
- `POST /v1/roles` - Create tenant-specific roles
- `GET /v1/storage/usage` - Tenant storage analytics
- `PUT /v1/storage/retention-policies` - Tenant data governance
- `GET /v1/subscription/features` - Available tenant features
- `GET /v1/security/dashboard` - Tenant security monitoring
- `GET /v1/usage/current/{tenant_id}` - Tenant usage analytics
- `GET /v1/subscription/billing` - Tenant billing information
- `GET /v1/dashboards` - Tenant dashboard management
- `GET /v1/alerts/rules` - Tenant alert configuration
- `GET /v1/enterprise/auth/api-keys` - Tenant API management
- `POST /v1/dashboards/schedule` - Automated reporting
- `POST /v1/alerts/notifications/test` - Integration testing

## Success Criteria
- Tenant admins can fully manage their organization (47 users) independently
- Role-based access controls work within tenant scope
- Data governance policies ensure compliance and cost control
- Integrations work with organization's existing tools
- Security monitoring provides visibility into tenant-specific threats
- Usage analytics help optimize costs and plan capacity
- Teams can collaborate effectively with appropriate access controls
- API access enables integration with organization's workflows

## Technical Implementation
- **Tenant-Scoped APIs**: All operations filtered by X-Customer-ID header
- **Self-Service Interface**: Comprehensive tenant administration without platform admin
- **Resource Quotas**: Tenant-level limits and usage monitoring
- **Team Workspaces**: Organizational structure within tenant
- **Compliance Automation**: Tenant-specific compliance monitoring
- **Integration Hub**: Organization-specific tool integrations
- **API Gateway**: Tenant-scoped API access and rate limiting