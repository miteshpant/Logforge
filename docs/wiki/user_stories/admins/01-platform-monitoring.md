# Admin User Story: Platform Health Monitoring

## Story
**As a** Logforge platform administrator  
**I want to** monitor the overall health and status of the Logforge platform  
**So that** I can ensure uptime, identify issues, and maintain service availability for all tenants

## User Journey

### 1. Login to Admin Interface
- Admin opens browser to `http://localhost:3002` (Admin UI)
- Enters admin credentials (email/password)
- System authenticates via `/v1/auth/login`
- Receives JWT token for admin operations
- Redirected to admin dashboard

### 2. View Platform Dashboard
- Admin lands on dashboard (`/`)
- Sees platform-wide statistics:
  - Active Tenants: 1,247
  - Monthly Revenue: $127,450
  - Total Data Ingested: 15.2TB
  - System Uptime: 99.97%
- Views recent alerts and system notifications

### 3. Check System Health
- Admin navigates to health monitoring section
- System calls `GET /health` endpoint
- Views detailed health status:
  - API Service: Healthy
  - ClickHouse Database: Healthy
  - Storage Layer: Healthy
  - Message Queue (Redpanda): Healthy
- Reviews response times and performance metrics

### 4. Monitor Service Components
- Admin checks individual service status
- Reviews API endpoint availability
- Monitors ingestion pipeline health
- Checks query engine performance
- Views storage utilization across tenants

### 5. Alert Management
- Admin receives notification of service degradation
- Views alert details and affected tenants
- Checks system logs for root cause analysis
- Takes corrective action (restart services, scale resources)
- Documents incident for postmortem

## API Endpoints Used
- `GET /health` - System health check
- `GET /v1/tenants` - List all tenants for monitoring
- `GET /v1/usage/analytics` - Platform usage analytics
- `POST /v1/auth/login` - Admin authentication

## Success Criteria
- Admin can quickly assess overall platform health
- System alerts are delivered promptly
- Historical health data is available for trend analysis
- Admin can drill down into specific service issues
- Platform statistics are accurate and real-time

## Technical Implementation
- **Admin UI**: Dashboard on port 3002
- **Authentication**: JWT-based admin auth
- **Monitoring**: Real-time health status checks
- **Alerting**: Push notifications for critical issues
- **Data**: Platform-wide aggregated metrics