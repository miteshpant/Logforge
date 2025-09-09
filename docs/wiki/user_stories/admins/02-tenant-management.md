# Admin User Story: Tenant Lifecycle Management

## Story
**As a** Logforge platform administrator  
**I want to** manage tenant accounts throughout their lifecycle  
**So that** I can onboard new customers, configure their environments, and maintain their services

## User Journey

### 1. New Tenant Onboarding
- Admin receives customer signup request
- Logs into Admin UI at `http://localhost:3002`
- Navigates to Tenant Management (`/tenants`)
- Clicks "Add New Tenant" button
- Fills out onboarding form:
  - Organization name: "Acme Corp"
  - Admin email: "admin@acme.com"
  - Subscription tier: "Enterprise"
  - Industry: "Financial Services"
  - Data retention period: 7 years
  - Region: US-East-1

### 2. Tenant Creation Process
- System calls `POST /v1/tenants` with tenant data
- Backend creates tenant record with UUID
- Generates customer_id for multi-tenant isolation
- Sets up initial user account with admin role
- Configures default quotas and limits
- Creates ClickHouse tenant tables
- Sets up storage buckets
- Admin sees success notification

### 3. Tenant Configuration
- Admin views tenant details page
- Reviews configuration settings:
  - Storage quota: 1TB
  - API rate limits: 10,000 requests/hour
  - User limit: 50 users
  - Data retention: 7 years
- Configures compliance settings:
  - HIPAA compliance: Disabled
  - SOX compliance: Enabled
  - Data residency: US only

### 4. Monitor Tenant Health
- Admin navigates to tenant dashboard
- Views tenant-specific metrics:
  - Data ingestion rate: 5,000 EPS
  - Storage usage: 250GB / 1TB
  - Active users: 12
  - API usage: 2,500 requests/hour
- Checks tenant health status
- Reviews recent alerts and issues

### 5. Tenant Support Operations
- Customer reports login issues
- Admin searches tenant by email/name
- Views user accounts via `GET /v1/users`
- Identifies disabled user account
- Re-enables user via `PUT /v1/users/{id}/status`
- Sends password reset email
- Documents support ticket resolution

### 6. Tenant Suspension/Termination
- Tenant exceeds billing threshold
- Admin marks tenant as suspended
- System calls `PUT /v1/tenants/{id}/status`
- All tenant services are disabled
- Data remains accessible for 30 days
- Admin schedules data deletion after grace period

## API Endpoints Used
- `POST /v1/tenants` - Create new tenant
- `GET /v1/tenants` - List all tenants
- `GET /v1/tenants/{id}` - Get tenant details
- `PUT /v1/tenants/{id}` - Update tenant configuration
- `PUT /v1/tenants/{id}/status` - Change tenant status
- `GET /v1/tenants/{id}/usage` - Tenant usage analytics
- `GET /v1/users` - List tenant users
- `POST /v1/users` - Create admin user for tenant

## Success Criteria
- New tenants can be onboarded in under 5 minutes
- Tenant configuration is immediately active
- Multi-tenant isolation is enforced
- Usage monitoring shows accurate data
- Support operations can be performed quickly
- Tenant lifecycle is properly managed

## Technical Implementation
- **Admin UI**: React forms with validation
- **Backend**: Tenant service with UUID generation
- **Database**: Multi-tenant ClickHouse tables
- **Storage**: Isolated tenant buckets
- **Security**: JWT-based admin authentication
- **Audit**: All tenant operations logged