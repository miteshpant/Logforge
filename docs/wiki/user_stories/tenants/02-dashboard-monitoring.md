# Tenant User Story: Real-Time Dashboard Monitoring

## Story
**As a** DevOps team lead  
**I want to** monitor system health and performance through real-time dashboards  
**So that** I can quickly identify issues and maintain service availability

## User Journey

### 1. Dashboard Access
- User logs into Logforge at `http://localhost:3001`
- Authenticates via `POST /v1/auth/login`
- Navigates to Dashboards section
- Views available dashboard templates:
  - Infrastructure Overview
  - Application Performance
  - Security Operations Center (SOC)
  - Business Analytics
  - Compliance Monitoring
  - Executive Summary

### 2. Infrastructure Dashboard Setup
- User selects "Infrastructure Overview" dashboard
- System calls `GET /v1/dashboards/infrastructure`
- Dashboard loads with real-time widgets:
  - **System Health**: 99.2% uptime
  - **Error Rate**: 0.8% (last hour)
  - **Response Time**: P50: 245ms, P95: 1.2s, P99: 3.1s
  - **Active Services**: 12 services detected
  - **Top Errors**: Payment timeout (23), Database connection (8)

### 3. Customize Dashboard Layout
- User clicks "Customize Dashboard" 
- Adds new widget for specific service monitoring
- Configures "Payment Service Health" widget:
  - Query: `service = "payment-service" AND level != "DEBUG"`
  - Time range: Last 4 hours
  - Refresh interval: 30 seconds
- System calls `POST /v1/query/advanced` for widget data

### 4. Real-Time Alert Investigation
- Dashboard shows spike in error rate at 14:30
- User clicks on error rate widget to drill down
- Views detailed error breakdown:
  - Database timeouts: 45 errors
  - API rate limit exceeded: 23 errors
  - Authentication failures: 12 errors
- System executes real-time queries via `POST /v1/query/timeseries`

### 5. Service Performance Analysis
- User switches to "Application Performance" dashboard
- Reviews service-level metrics:

**Web API Service**
- Request volume: 1,247 req/min
- Average response time: 180ms
- Error rate: 0.2%
- CPU utilization: 45%

**Payment Service**
- Request volume: 234 req/min
- Average response time: 850ms (ALERT: High)
- Error rate: 2.1% (ALERT: High)
- Database query time: 650ms (ALERT: High)

### 6. Historical Trend Analysis
- User notices payment service degradation
- Switches time range to "Last 24 hours"
- System calls `POST /v1/query/timeseries` with extended range
- Identifies performance degradation started at 12:00 PM
- Correlates with recent deployment timestamp
- Plans rollback strategy

### 7. Business Impact Dashboard
- User switches to "Business Analytics" dashboard
- Reviews business-critical metrics:
  - Successful transactions: $127,450 (today)
  - Failed transactions: $3,200 (impact of errors)
  - Customer logins: 2,847
  - New user signups: 23
  - Average session duration: 8.5 minutes

### 8. Share Dashboard Insights
- User creates dashboard snapshot
- Generates shareable link for management review
- Exports key metrics as CSV for reporting
- System calls `POST /v1/export` with dashboard queries
- Schedules daily dashboard report email

### 9. Mobile Dashboard Access
- User receives critical alert on phone
- Opens mobile browser to Logforge dashboard
- Views responsive mobile version
- Quickly assesses situation:
  - Payment service: DOWN
  - Error spike: 450% increase
  - Customer impact: HIGH
- Initiates incident response from mobile device

## API Endpoints Used
- `GET /v1/dashboards` - List available dashboards
- `GET /v1/dashboards/{dashboard_id}` - Load specific dashboard
- `GET /v1/dashboards/{dashboard_id}/data` - Get dashboard data
- `POST /v1/dashboards` - Create custom dashboard
- `PUT /v1/dashboards/{dashboard_id}` - Update dashboard
- `GET /v1/dashboards/{dashboard_id}/widgets/{widget_id}/data` - Get widget data
- `POST /v1/query/advanced` - Execute dashboard queries
- `POST /v1/query/timeseries` - Time-series data for charts
- `POST /v1/query/aggregate` - Aggregated metrics
- `POST /v1/export` - Export dashboard data

## Success Criteria
- Dashboards load quickly with real-time data (< 2 seconds)
- Widgets refresh automatically with configurable intervals
- Historical trends are clearly visualized
- Drill-down capabilities provide detailed analysis
- Mobile access enables on-call monitoring
- Dashboard customization meets specific monitoring needs
- Business impact is quantified and visible

## Technical Implementation
- **Frontend**: React dashboard with responsive design
- **Backend**: FastAPI with real-time query execution
- **Database**: ClickHouse optimized for analytics queries
- **Caching**: Query result caching for performance
- **WebSockets**: Real-time data updates
- **Export**: Multiple formats (JSON, CSV, PDF)
- **Mobile**: PWA capabilities for offline access