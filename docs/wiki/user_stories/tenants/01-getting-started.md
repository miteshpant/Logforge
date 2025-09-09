# Tenant User Story: Getting Started with Log Ingestion

## Story
**As a** new Logforge customer (DevOps Engineer)  
**I want to** start ingesting logs from my applications  
**So that** I can monitor system health and troubleshoot issues

## User Journey

### 1. Initial Login
- User receives welcome email from Logforge admin
- Opens browser to `http://localhost:3001` (Customer UI)
- Enters provided credentials (email/password)
- System calls `POST /v1/auth/login`
- Receives JWT token and customer_id
- Lands on welcome dashboard

### 2. Explore Platform Capabilities
- User sees dashboard overview with sample data
- Views platform features:
  - Multi-format log ingestion
  - Advanced query engine
  - Real-time dashboards
  - Rule-based alerting
  - Security analytics
- Clicks "Get Started" tutorial

### 3. First Log Ingestion Test
- User navigates to ingestion testing page
- Selects "JSON Log" format
- Enters sample log entry:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "service": "web-api",
  "message": "User login successful",
  "user_id": "user123",
  "host": "web-01"
}
```
- Clicks "Send Test Log"
- System calls `POST /v1/ingest/logs` with X-Customer-ID header
- Receives success response with log_id

### 4. Verify Log Storage
- User navigates to log search page
- Performs basic search for recent logs
- System calls `GET /v1/logs?limit=10`
- Views ingested log in search results
- Confirms timestamp, service, and message fields
- Sees customer isolation working (only their logs visible)

### 5. Set Up Production Ingestion
- User accesses API documentation at `/docs`
- Reviews ingestion endpoints:
  - `POST /v1/ingest/logs` - Single log
  - `POST /v1/ingest/logs/batch` - Batch logs
  - `POST /v1/ingest/syslog` - Syslog format
  - `POST /v1/ingest/otlp` - OpenTelemetry
- Copies API endpoint and authentication details

### 6. Configure Application Logging
- User updates application logging configuration
- Sets up HTTP log shipping to Logforge:
```bash
# Example curl command for testing
curl -X POST http://localhost:7080/v1/ingest/logs \
  -H "Content-Type: application/json" \
  -H "X-Customer-ID: customer-123" \
  -d '{
    "timestamp": "2024-01-15T10:35:00Z",
    "level": "ERROR",
    "service": "payment-service",
    "message": "Payment processing failed",
    "error_code": "CARD_DECLINED",
    "transaction_id": "txn_456"
  }'
```

### 7. Monitor Ingestion Success
- User returns to Logforge dashboard
- Views real-time ingestion statistics:
  - Logs ingested: 1,247 in last hour
  - Services detected: 3 (web-api, payment-service, auth-service)
  - Error rate: 2.3%
- Confirms logs are flowing from production systems

### 8. Basic Log Analysis
- User performs first operational query
- Searches for errors: `level = "ERROR"`
- System calls `POST /v1/query/advanced`
- Reviews error patterns and frequencies
- Identifies payment service issues
- Uses results to prioritize bug fixes

## API Endpoints Used
- `POST /v1/auth/login` - User authentication
- `POST /v1/ingest/logs` - Single log ingestion
- `POST /v1/ingest/logs/batch` - Batch log ingestion
- `GET /v1/logs` - Basic log retrieval
- `POST /v1/query/advanced` - Advanced log queries
- `GET /health` - System health check

## Success Criteria
- User can successfully log in and access the platform
- First test log is ingested and visible in search results
- Production log ingestion is configured and working
- Real-time dashboard shows accurate ingestion metrics
- User can perform basic log searches and analysis
- API documentation is clear and actionable

## Technical Implementation
- **Authentication**: JWT-based with X-Customer-ID for tenant isolation
- **Ingestion**: Multiple format support with parser factory
- **Storage**: ClickHouse with multi-tenant tables
- **UI**: React-based customer dashboard
- **API**: RESTful endpoints with comprehensive documentation
- **Monitoring**: Real-time ingestion statistics and health checks