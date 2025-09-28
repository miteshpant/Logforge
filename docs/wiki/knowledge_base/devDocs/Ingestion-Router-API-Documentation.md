# Ingestion Router API - Developer Documentation

## Overview

The Ingestion Router API (`/v1/ingest`) provides comprehensive log ingestion capabilities for the Logforge platform. This system supports multiple log formats, automatic format detection, batch processing, and real-time log processing with enterprise-grade performance and reliability.

**Location**: `/apps/api/routers/ingestion.py`  
**Service Layer**: `/apps/api/services/ingestion_service.py`  
**Data Layer**: `/apps/api/dao/ingestion_dao.py`  
**Authentication**: Required for all endpoints  
**Multi-Tenancy**: `X-Customer-ID` header required for all endpoints  
**Subscription**: Requires `ingestion.*` features in subscription

## Architecture & Components

### System Architecture
```
FastAPI Router → IngestionService → IngestionDAO → ClickHouse Database
     ↓              ↓                 ↓              ↓
Middleware     Business Logic    Database Ops   Multi-tenant Storage
Validation     Format Detection  Stats Tracking  Log Persistence
Background     Performance       Error Tracking  Usage Analytics
Processing     Optimization      Metrics         Performance Data
```

### Core Components

1. **Ingestion Router** (`ingestion.py`): HTTP endpoint definitions for all log formats
2. **Ingestion Service** (`ingestion_service.py`): Business logic, validation, and processing orchestration
3. **Ingestion DAO** (`ingestion_dao.py`): Database operations for logging and statistics tracking
4. **Parser Factory**: Multi-format log parsing with automatic format detection
5. **Background Processing**: Asynchronous log processing and storage
6. **Usage Tracking**: Real-time ingestion analytics and billing integration

### Supported Log Formats

**Structured Formats**:
- **JSON**: Standard JSON log entries with flexible schema
- **OTLP**: OpenTelemetry Protocol for distributed tracing integration
- **Structured**: Custom structured data with nested objects

**Text-Based Formats**:
- **Syslog**: RFC 3164 and RFC 5424 compliant syslog messages
- **CEF**: Common Event Format for security event ingestion
- **Nginx**: Nginx access log format with automatic field extraction
- **Text**: Plain text logs with intelligent parsing

**Advanced Features**:
- **Auto-Detection**: Automatic format detection based on content analysis
- **Batch Processing**: High-throughput batch ingestion for bulk data
- **Background Processing**: Non-blocking asynchronous log processing

### Performance Characteristics

- **Ingestion Rate**: 50,000+ logs per second per node
- **Format Support**: 7 distinct log formats with auto-detection
- **Batch Size**: Up to 1,000 logs per batch request
- **Processing Latency**: <100ms for single log, <500ms for batch processing
- **Storage Integration**: Direct ClickHouse integration with multi-tenant isolation

## API Endpoints (9 Total)

### 1. Single Log Ingestion (3 endpoints)

#### **POST /v1/ingest/logs** - Ingest Single Log
Ingest a single structured log entry with full validation and processing.

**Authentication**: Required (Bearer token)

**Request Model**: `LogEntry`
```json
{
  "ts": "2024-01-01T12:00:00Z",
  "host": "api-server-01",
  "service": "payment-api",
  "level": "info",
  "msg": "Payment transaction completed successfully",
  "trace_id": "trace_abc123def456",
  "span_id": "span_789ghi012",
  "attrs": {
    "transaction_id": "txn_456789",
    "amount": 99.99,
    "currency": "USD",
    "user_id": "user_123",
    "response_time": 250
  },
  "status": 200,
  "src_ip": "192.168.1.100",
  "user_id": "user_123"
}
```

**Response**: (200 OK) `IngestResponse`
```json
{
  "status": "success",
  "message": "Successfully ingested 1 log",
  "log_id": "log-1704110400-1234",
  "processed_count": 1
}
```

#### **POST /v1/ingest/structured** - Ingest Structured Data
Ingest structured JSON data with automatic LogEntry conversion.

**Authentication**: Required (Bearer token)

**Single Log Example**:
```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "error",
  "message": "Database connection timeout",
  "service": "user-service",
  "metadata": {
    "database": "users_db",
    "timeout_ms": 5000,
    "retry_count": 3
  }
}
```

**Array of Logs Example**:
```json
[
  {
    "timestamp": "2024-01-01T12:00:00Z",
    "level": "info",
    "message": "User login successful",
    "service": "auth-service"
  },
  {
    "timestamp": "2024-01-01T12:00:01Z",
    "level": "warn",
    "message": "Rate limit approaching",
    "service": "api-gateway"
  }
]
```

**Response**: (200 OK) `IngestResponse`
```json
{
  "status": "success",
  "message": "Successfully ingested 2 logs",
  "processed_count": 2
}
```

#### **POST /v1/ingest** - Auto-Detect Format
Automatically detect log format and ingest with optimal parsing.

**Authentication**: Required (Bearer token)

**Content-Type Detection**:
- `application/json`: JSON or OTLP format detection
- `text/plain`: Syslog, CEF, Nginx, or plain text detection
- Auto-detection: Based on content patterns and structure

**JSON Log Example**:
```bash
POST /v1/ingest
Content-Type: application/json

{
  "level": "info",
  "message": "User authenticated",
  "service": "auth-service",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**Syslog Example**:
```bash
POST /v1/ingest
Content-Type: text/plain

<134>Jan 1 12:00:00 server01 auth-service: User authentication successful for user_123
```

**Response**: (200 OK) `IngestResponse`
```json
{
  "status": "success",
  "message": "Successfully ingested 1 logs - detected format: json",
  "processed_count": 1
}
```

### 2. Batch Processing (2 endpoints)

#### **POST /v1/ingest/logs/batch** - Batch Log Ingestion
High-performance batch ingestion for multiple log entries.

**Authentication**: Required (Bearer token)

**Request Model**: `BatchLogEntry`
```json
{
  "logs": [
    {
      "ts": "2024-01-01T12:00:00Z",
      "service": "payment-api",
      "level": "info",
      "msg": "Payment initiated",
      "attrs": {"transaction_id": "txn_001", "amount": 50.00}
    },
    {
      "ts": "2024-01-01T12:00:01Z",
      "service": "payment-api",
      "level": "info",
      "msg": "Payment completed",
      "attrs": {"transaction_id": "txn_001", "status": "success"}
    },
    {
      "ts": "2024-01-01T12:00:02Z",
      "service": "notification-service",
      "level": "info",
      "msg": "Payment notification sent",
      "attrs": {"transaction_id": "txn_001", "channel": "email"}
    }
  ]
}
```

**Response**: (200 OK) `BatchIngestResponse`
```json
{
  "status": "accepted",
  "message": "Successfully ingested 3 logs",
  "processed_count": 3,
  "error_count": 0
}
```

#### **POST /v1/ingest/logs/bulk** - Bulk Data Ingestion
Flexible bulk ingestion for various data sources and formats.

**Authentication**: Required (Bearer token)

**Request Format**:
```json
{
  "logs": [
    {
      "timestamp": "2024-01-01T12:00:00Z",
      "level": "info",
      "message": "Service started",
      "service": "api-gateway"
    },
    {
      "timestamp": "2024-01-01T12:00:01Z",
      "level": "info",
      "message": "Health check passed",
      "service": "api-gateway"
    }
  ],
  "metadata": {
    "source": "log-forwarder",
    "version": "1.2.3"
  }
}
```

**Response**: (200 OK) `BatchIngestResponse`
```json
{
  "status": "success",
  "message": "Successfully ingested 2 logs",
  "processed_count": 2,
  "error_count": 0
}
```

### 3. Format-Specific Endpoints (4 endpoints)

#### **POST /v1/ingest/otlp** - OpenTelemetry Protocol
Ingest OpenTelemetry logs with full distributed tracing support.

**Authentication**: Required (Bearer token)

**Request Model**: `OTLPLogsData`
```json
{
  "resource_logs": [
    {
      "resource": {
        "attributes": [
          {"key": "service.name", "value": "payment-service"},
          {"key": "service.version", "value": "1.0.0"}
        ]
      },
      "scope_logs": [
        {
          "scope": {
            "name": "payment-operations",
            "version": "1.0.0"
          },
          "log_records": [
            {
              "time_unix_nano": 1704110400000000000,
              "severity_number": 9,
              "severity_text": "INFO",
              "body": "Payment transaction processed",
              "attributes": [
                {"key": "transaction.id", "value": "txn_123"},
                {"key": "amount", "value": 99.99},
                {"key": "currency", "value": "USD"}
              ],
              "trace_id": "0123456789abcdef0123456789abcdef",
              "span_id": "0123456789abcdef"
            }
          ]
        }
      ]
    }
  ]
}
```

**Response**: (200 OK) `BatchIngestResponse`
```json
{
  "status": "success",
  "message": "Successfully ingested 1 logs",
  "processed_count": 1,
  "error_count": 0
}
```

#### **POST /v1/ingest/syslog** - Syslog Format
Ingest RFC 3164 and RFC 5424 compliant syslog messages.

**Authentication**: Required (Bearer token)

**RFC 3164 Example**:
```bash
POST /v1/ingest/syslog
Content-Type: text/plain

<134>Jan 1 12:00:00 server01 auth-service[1234]: User login attempt from 192.168.1.100
```

**RFC 5424 Example**:
```bash
POST /v1/ingest/syslog
Content-Type: text/plain

<134>1 2024-01-01T12:00:00.000Z server01 auth-service 1234 ID47 [user@example username="john"] User authenticated successfully
```

**Response**: (200 OK) `IngestResponse`
```json
{
  "status": "success",
  "message": "Successfully ingested 1 logs",
  "processed_count": 1
}
```

#### **POST /v1/ingest/cef** - Common Event Format
Ingest CEF (Common Event Format) security events.

**Authentication**: Required (Bearer token)

**CEF Example**:
```bash
POST /v1/ingest/cef
Content-Type: text/plain

CEF:0|Logforge|SIEM|1.0|100|User Authentication|3|src=192.168.1.100 suser=john.doe act=login outcome=success
```

**Response**: (200 OK) `IngestResponse`
```json
{
  "status": "success",
  "message": "Successfully ingested 1 logs",
  "processed_count": 1
}
```

#### **POST /v1/ingest/nginx** - Nginx Access Logs
Ingest Nginx access logs with automatic field extraction.

**Authentication**: Required (Bearer token)

**Nginx Combined Log Format**:
```bash
POST /v1/ingest/nginx
Content-Type: text/plain

192.168.1.100 - - [01/Jan/2024:12:00:00 +0000] "GET /api/users HTTP/1.1" 200 1234 "https://example.com" "Mozilla/5.0 (compatible; API-Client/1.0)"
```

**Response**: (200 OK) `IngestResponse`
```json
{
  "status": "success",
  "message": "Successfully ingested 1 logs",
  "processed_count": 1
}
```

#### **POST /v1/ingest/text** - Plain Text Logs
Ingest plain text logs with intelligent parsing.

**Authentication**: Required (Bearer token)

**Text Log Example**:
```bash
POST /v1/ingest/text
Content-Type: text/plain

2024-01-01 12:00:00 INFO [payment-service] Transaction txn_123 completed successfully (amount: $99.99)
```

**Response**: (200 OK) `IngestResponse`
```json
{
  "status": "success",
  "message": "Successfully ingested 1 logs",
  "processed_count": 1
}
```

## Data Models & Validation

### Core Request Models

#### LogEntry
```python
class LogEntry(BaseModel):
    ts: datetime = Field(default_factory=datetime.utcnow, description="Timestamp")
    host: Optional[str] = Field("", description="Hostname or IP")
    service: str = Field(..., description="Service name")
    level: str = Field("info", description="Log level")
    msg: str = Field(..., description="Log message")
    trace_id: Optional[str] = Field("", description="Distributed trace ID")
    span_id: Optional[str] = Field("", description="Span ID for tracing")
    attrs: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional attributes")
    status: Optional[int] = Field(0, description="HTTP status or error code")
    src_ip: Optional[str] = Field("", description="Source IP address")
    user_id: Optional[str] = Field("", description="User identifier")
    
    # Runtime metadata (auto-populated)
    ingested_at: Optional[datetime] = Field(None, description="Ingestion timestamp")
    customer_id: Optional[str] = Field("default", description="Customer identifier")
```

#### BatchLogEntry
```python
class BatchLogEntry(BaseModel):
    logs: List[LogEntry] = Field(..., description="Array of log entries")
    
    @validator('logs')
    def validate_batch_size(cls, v):
        if len(v) > 1000:
            raise ValueError("Batch size cannot exceed 1000 logs")
        return v
```

#### OTLPLogsData
```python
class OTLPLogsData(BaseModel):
    resource_logs: List[OTLPResourceLogs] = Field(..., description="Resource logs")

class OTLPResourceLogs(BaseModel):
    resource: Optional[OTLPResource] = Field(default_factory=OTLPResource)
    scope_logs: List[OTLPScopeLogs] = Field(..., description="Scope logs")

class OTLPLogRecord(BaseModel):
    time_unix_nano: int = Field(..., description="Timestamp in nanoseconds")
    severity_number: Optional[int] = Field(0, description="Severity number")
    severity_text: Optional[str] = Field("", description="Severity text")
    body: str = Field(..., description="Log body/message")
    attributes: List[OTLPAttribute] = Field(default_factory=list)
    trace_id: Optional[str] = Field("", description="Trace ID (hex)")
    span_id: Optional[str] = Field("", description="Span ID (hex)")
```

### Core Response Models

#### IngestResponse
```python
class IngestResponse(BaseModel):
    status: str = Field(..., description="Ingestion status")
    message: str = Field(..., description="Human-readable message")
    log_id: Optional[str] = Field(None, description="Generated log ID")
    processed_count: int = Field(..., description="Number of logs processed")
```

#### BatchIngestResponse
```python
class BatchIngestResponse(BaseModel):
    status: str = Field(..., description="Batch ingestion status")
    message: str = Field(..., description="Human-readable message")
    processed_count: int = Field(..., description="Number of logs processed")
    error_count: int = Field(0, description="Number of failed logs")
```

### Log Level Normalization

**Supported Log Levels**:
- `trace`: Detailed debugging information
- `debug`: Debug-level messages
- `info`: Informational messages (default)
- `warn`/`warning`: Warning conditions
- `error`: Error conditions
- `fatal`/`critical`: Critical error conditions

**Auto-Normalization**:
```python
level_map = {
    'trace': 'trace', 'debug': 'debug', 'info': 'info',
    'warn': 'warn', 'warning': 'warn', 'error': 'error',
    'fatal': 'fatal', 'critical': 'fatal', 'crit': 'fatal'
}
```

### Validation Rules

#### Log Entry Validation
- **Required Fields**: `service`, `msg` (message cannot be empty)
- **Maximum Message Size**: 64KB per log message
- **Timestamp**: Auto-populated if not provided
- **Customer ID**: Auto-populated from X-Customer-ID header

#### Batch Validation
- **Maximum Batch Size**: 1,000 logs per batch request
- **Total Size Limit**: 10MB per batch request
- **Partial Failure Handling**: Invalid logs filtered out, valid logs processed

## Integration Examples

### Python SDK Integration

```python
import httpx
import asyncio
from datetime import datetime
import json

class LogforgeIngestionClient:
    def __init__(self, base_url: str, token: str, customer_id: str):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {token}",
            "X-Customer-ID": customer_id,
            "Content-Type": "application/json"
        }
    
    async def ingest_single_log(self, log_data: dict) -> dict:
        """Ingest a single structured log entry"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/ingest/logs",
                json=log_data,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def ingest_batch_logs(self, logs: list) -> dict:
        """Ingest multiple logs in a single batch"""
        batch_data = {"logs": logs}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/ingest/logs/batch",
                json=batch_data,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def ingest_syslog(self, syslog_message: str) -> dict:
        """Ingest syslog format message"""
        headers = dict(self.headers)
        headers["Content-Type"] = "text/plain"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/ingest/syslog",
                content=syslog_message,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
    
    async def ingest_auto_detect(self, content: str, content_type: str = "text/plain") -> dict:
        """Auto-detect format and ingest"""
        headers = dict(self.headers)
        headers["Content-Type"] = content_type
        
        async with httpx.AsyncClient() as client:
            if content_type == "application/json":
                response = await client.post(
                    f"{self.base_url}/v1/ingest",
                    json=json.loads(content),
                    headers=headers
                )
            else:
                response = await client.post(
                    f"{self.base_url}/v1/ingest",
                    content=content,
                    headers=headers
                )
            response.raise_for_status()
            return response.json()

# Usage Example
async def main():
    client = LogforgeIngestionClient(
        base_url="http://localhost:7080",
        token="your_jwt_token",
        customer_id="your_tenant_id"
    )
    
    try:
        # Single log ingestion
        log_entry = {
            "ts": datetime.utcnow().isoformat(),
            "service": "payment-api",
            "level": "info",
            "msg": "Payment transaction completed",
            "attrs": {
                "transaction_id": "txn_123",
                "amount": 99.99,
                "user_id": "user_456"
            }
        }
        
        result = await client.ingest_single_log(log_entry)
        print(f"Single log ingested: {result['processed_count']}")
        
        # Batch ingestion
        batch_logs = [
            {
                "service": "auth-service",
                "level": "info",
                "msg": "User login successful",
                "attrs": {"user_id": "user_123"}
            },
            {
                "service": "auth-service", 
                "level": "warn",
                "msg": "Multiple login attempts detected",
                "attrs": {"user_id": "user_123", "attempts": 3}
            }
        ]
        
        batch_result = await client.ingest_batch_logs(batch_logs)
        print(f"Batch ingested: {batch_result['processed_count']} logs")
        
        # Syslog ingestion
        syslog_msg = "<134>Jan 1 12:00:00 server01 auth-service: User authenticated"
        syslog_result = await client.ingest_syslog(syslog_msg)
        print(f"Syslog ingested: {syslog_result['processed_count']}")
        
        # Auto-detection
        json_log = '{"level": "error", "message": "Database timeout", "service": "db-proxy"}'
        auto_result = await client.ingest_auto_detect(json_log, "application/json")
        print(f"Auto-detected format and ingested: {auto_result['processed_count']}")
        
    except httpx.HTTPStatusError as e:
        print(f"API Error {e.response.status_code}: {e.response.text}")
    except Exception as e:
        print(f"Error: {e}")

# Run the example
asyncio.run(main())
```

### JavaScript/Node.js Integration

```javascript
const axios = require('axios');

class LogforgeIngestionClient {
  constructor(baseUrl, token, customerId) {
    this.baseUrl = baseUrl;
    this.headers = {
      'Authorization': `Bearer ${token}`,
      'X-Customer-ID': customerId,
      'Content-Type': 'application/json'
    };
  }

  async ingestSingleLog(logData) {
    try {
      const response = await axios.post(
        `${this.baseUrl}/v1/ingest/logs`,
        logData,
        { headers: this.headers }
      );
      return response.data;
    } catch (error) {
      throw new Error(`Single log ingestion failed: ${error.response?.data?.detail}`);
    }
  }

  async ingestBatchLogs(logs) {
    try {
      const response = await axios.post(
        `${this.baseUrl}/v1/ingest/logs/batch`,
        { logs },
        { headers: this.headers }
      );
      return response.data;
    } catch (error) {
      throw new Error(`Batch ingestion failed: ${error.response?.data?.detail}`);
    }
  }

  async ingestStructuredData(data) {
    try {
      const response = await axios.post(
        `${this.baseUrl}/v1/ingest/structured`,
        data,
        { headers: this.headers }
      );
      return response.data;
    } catch (error) {
      throw new Error(`Structured data ingestion failed: ${error.response?.data?.detail}`);
    }
  }

  async ingestOTLP(otlpData) {
    try {
      const response = await axios.post(
        `${this.baseUrl}/v1/ingest/otlp`,
        otlpData,
        { headers: this.headers }
      );
      return response.data;
    } catch (error) {
      throw new Error(`OTLP ingestion failed: ${error.response?.data?.detail}`);
    }
  }

  async ingestTextFormat(content, format) {
    const endpoint = format ? `/v1/ingest/${format}` : '/v1/ingest';
    const headers = {
      ...this.headers,
      'Content-Type': 'text/plain'
    };

    try {
      const response = await axios.post(
        `${this.baseUrl}${endpoint}`,
        content,
        { headers }
      );
      return response.data;
    } catch (error) {
      throw new Error(`${format || 'Auto-detect'} ingestion failed: ${error.response?.data?.detail}`);
    }
  }

  // High-level convenience methods
  async ingestApplicationLogs(appName, logs) {
    const structuredLogs = logs.map(log => ({
      service: appName,
      level: log.level || 'info',
      msg: log.message,
      ts: log.timestamp || new Date().toISOString(),
      attrs: log.metadata || {}
    }));

    return await this.ingestBatchLogs(structuredLogs);
  }

  async ingestErrorLog(service, error, context = {}) {
    const errorLog = {
      service,
      level: 'error',
      msg: error.message || String(error),
      ts: new Date().toISOString(),
      attrs: {
        error_type: error.name || 'Error',
        stack_trace: error.stack,
        ...context
      }
    };

    return await this.ingestSingleLog(errorLog);
  }
}

// Usage Example
async function demonstrateIngestionFeatures() {
  const client = new LogforgeIngestionClient(
    'http://localhost:7080',
    process.env.LOGFORGE_TOKEN,
    process.env.CUSTOMER_ID
  );

  try {
    // Application logging
    console.log('Ingesting application logs...');
    const appLogs = [
      { level: 'info', message: 'Application started', metadata: { version: '1.2.3' } },
      { level: 'warn', message: 'High memory usage detected', metadata: { memory_mb: 512 } },
      { level: 'info', message: 'User session created', metadata: { user_id: 'user_123' } }
    ];

    const appResult = await client.ingestApplicationLogs('my-service', appLogs);
    console.log(`Application logs ingested: ${appResult.processed_count}`);

    // Error logging
    console.log('Ingesting error log...');
    try {
      throw new Error('Database connection failed');
    } catch (error) {
      const errorResult = await client.ingestErrorLog('database-service', error, {
        database: 'users_db',
        connection_string: 'postgresql://...'
      });
      console.log(`Error log ingested: ${errorResult.processed_count}`);
    }

    // OTLP ingestion (OpenTelemetry)
    console.log('Ingesting OTLP data...');
    const otlpData = {
      resource_logs: [{
        resource: {
          attributes: [
            { key: 'service.name', value: 'payment-service' },
            { key: 'service.version', value: '2.1.0' }
          ]
        },
        scope_logs: [{
          log_records: [{
            time_unix_nano: Date.now() * 1000000,
            severity_number: 9,
            severity_text: 'INFO',
            body: 'Payment processed successfully',
            attributes: [
              { key: 'transaction.id', value: 'txn_456' },
              { key: 'amount', value: 150.00 }
            ]
          }]
        }]
      }]
    };

    const otlpResult = await client.ingestOTLP(otlpData);
    console.log(`OTLP logs ingested: ${otlpResult.processed_count}`);

    // Syslog ingestion
    console.log('Ingesting syslog message...');
    const syslogMessage = '<134>Jan 1 12:00:00 web-server nginx: GET /api/health 200';
    const syslogResult = await client.ingestTextFormat(syslogMessage, 'syslog');
    console.log(`Syslog ingested: ${syslogResult.processed_count}`);

    // Auto-detection
    console.log('Testing auto-detection...');
    const nginxLog = '192.168.1.100 - - [01/Jan/2024:12:00:00 +0000] "GET /api/users HTTP/1.1" 200 1234';
    const autoResult = await client.ingestTextFormat(nginxLog);
    console.log(`Auto-detected and ingested: ${autoResult.processed_count}`);

  } catch (error) {
    console.error('Ingestion demonstration failed:', error.message);
  }
}

// Run the demonstration
demonstrateIngestionFeatures();
```

### cURL Examples

**Single Log Ingestion**:
```bash
curl -X POST "http://localhost:7080/v1/ingest/logs" \
  -H "Authorization: Bearer your_jwt_token" \
  -H "X-Customer-ID: your_tenant_id" \
  -H "Content-Type: application/json" \
  -d '{
    "service": "payment-api",
    "level": "info",
    "msg": "Payment transaction completed",
    "attrs": {
      "transaction_id": "txn_123",
      "amount": 99.99
    }
  }'
```

**Batch Ingestion**:
```bash
curl -X POST "http://localhost:7080/v1/ingest/logs/batch" \
  -H "Authorization: Bearer your_jwt_token" \
  -H "X-Customer-ID: your_tenant_id" \
  -H "Content-Type: application/json" \
  -d '{
    "logs": [
      {
        "service": "auth-service",
        "level": "info",
        "msg": "User login successful"
      },
      {
        "service": "auth-service",
        "level": "warn", 
        "msg": "Failed login attempt"
      }
    ]
  }'
```

**Syslog Ingestion**:
```bash
curl -X POST "http://localhost:7080/v1/ingest/syslog" \
  -H "Authorization: Bearer your_jwt_token" \
  -H "X-Customer-ID: your_tenant_id" \
  -H "Content-Type: text/plain" \
  -d '<134>Jan 1 12:00:00 server01 auth-service: User authenticated'
```

**Auto-Detection**:
```bash
curl -X POST "http://localhost:7080/v1/ingest" \
  -H "Authorization: Bearer your_jwt_token" \
  -H "X-Customer-ID: your_tenant_id" \
  -H "Content-Type: application/json" \
  -d '{
    "level": "error",
    "message": "Database connection timeout",
    "service": "db-service"
  }'
```

**OTLP Ingestion**:
```bash
curl -X POST "http://localhost:7080/v1/ingest/otlp" \
  -H "Authorization: Bearer your_jwt_token" \
  -H "X-Customer-ID: your_tenant_id" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_logs": [{
      "scope_logs": [{
        "log_records": [{
          "time_unix_nano": 1704110400000000000,
          "severity_text": "INFO",
          "body": "Service health check passed"
        }]
      }]
    }]
  }'
```

## Error Handling

### HTTP Status Codes

- **200 OK**: Successful ingestion
- **400 Bad Request**: Invalid log format, validation errors, parsing failures
- **401 Unauthorized**: Invalid or expired authentication token
- **403 Forbidden**: Insufficient subscription permissions
- **413 Payload Too Large**: Batch size or log size exceeds limits
- **429 Too Many Requests**: Rate limiting exceeded
- **500 Internal Server Error**: Server-side processing error

### Error Response Format

```json
{
  "detail": "Detailed error message describing the issue"
}
```

### Common Error Scenarios

#### Validation Errors
```json
{
  "detail": "Invalid log entry: message field is required"
}
```

#### Format Parsing Errors
```json
{
  "detail": "Syslog parsing failed: Invalid priority value"
}
```

#### Size Limit Errors
```json
{
  "detail": "Batch ingestion failed: Batch size cannot exceed 1000 logs"
}
```

#### Subscription Errors
```json
{
  "detail": "Insufficient subscription permissions for log ingestion"
}
```

### Error Handling Best Practices

```python
async def handle_ingestion_errors(api_call):
    """Error handling wrapper for ingestion API calls"""
    try:
        return await api_call()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            error_detail = e.response.json().get("detail", "Validation error")
            print(f"Validation error: {error_detail}")
        elif e.response.status_code == 413:
            print("Payload too large - reduce batch size or log size")
        elif e.response.status_code == 429:
            print("Rate limit exceeded - implement backoff and retry")
        elif e.response.status_code == 403:
            print("Insufficient subscription permissions")
        else:
            print(f"API error {e.response.status_code}: {e.response.text}")
        raise
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise
```

## Performance Optimization

### Ingestion Performance
- **Single Log**: ~50-100ms processing time
- **Batch Processing**: ~200-500ms for 100-1000 logs
- **Throughput**: 50,000+ logs per second per node
- **Concurrent Requests**: Up to 100 concurrent ingestion requests

### Best Practices

#### For High-Volume Ingestion
1. **Use Batch Endpoints**: Prefer batch ingestion over single log for high throughput
2. **Optimal Batch Size**: 100-500 logs per batch for best performance/latency balance
3. **Async Processing**: Leverage background processing for non-blocking ingestion
4. **Connection Pooling**: Reuse HTTP connections for multiple requests
5. **Format Selection**: Use structured formats (JSON) for best parsing performance

#### For Low-Latency Ingestion  
1. **Single Log Endpoint**: Use single log endpoint for time-critical events
2. **Regional Deployment**: Deploy ingestion endpoints close to log sources
3. **Connection Optimization**: Use HTTP/2 and keep-alive connections
4. **Minimal Payloads**: Include only essential fields in log entries

#### For Reliability
1. **Error Handling**: Implement proper retry logic with exponential backoff
2. **Circuit Breakers**: Implement circuit breaker pattern for fault tolerance
3. **Monitoring**: Monitor ingestion success rates and error patterns
4. **Graceful Degradation**: Handle partial batch failures gracefully

## Security Considerations

### Data Security
1. **Encryption in Transit**: All API communication over HTTPS/TLS
2. **Authentication**: JWT-based authentication for all endpoints
3. **Authorization**: Subscription-based access control for ingestion features
4. **Multi-Tenant Isolation**: Complete log data separation by customer ID

### Input Validation
1. **Schema Validation**: Strict validation of all log entry fields
2. **Size Limits**: Enforced limits on log message size and batch size
3. **Content Filtering**: Automatic filtering of potentially malicious content
4. **Rate Limiting**: Protection against ingestion abuse and DDoS

### Privacy Protection
1. **PII Detection**: Optional automatic detection and redaction of PII
2. **Data Retention**: Configurable retention policies per tenant
3. **Audit Logging**: Complete audit trail of all ingestion operations
4. **Access Controls**: Role-based access to ingestion endpoints

## Monitoring & Analytics

### Ingestion Metrics
- **Ingestion Rate**: Logs per second, bytes per second
- **Success Rate**: Percentage of successful ingestions
- **Error Rate**: Percentage of failed ingestions by error type
- **Processing Latency**: End-to-end processing time distribution
- **Format Distribution**: Breakdown of ingested log formats

### Usage Analytics
- **Tenant Usage**: Per-tenant ingestion volume and costs
- **Endpoint Usage**: Usage patterns across different ingestion endpoints
- **Peak Load Analysis**: Identification of peak ingestion periods
- **Error Analysis**: Detailed error categorization and trending

### Alerting & Health Checks
- **Service Health**: Real-time health monitoring of ingestion services
- **Error Rate Alerts**: Automated alerts for high error rates
- **Performance Alerts**: Alerts for degraded ingestion performance
- **Capacity Alerts**: Warnings for approaching ingestion limits

The Ingestion Router API provides comprehensive, high-performance log ingestion capabilities with support for multiple formats, automatic detection, and enterprise-grade reliability to ensure seamless integration with diverse logging environments and data sources.