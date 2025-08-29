# M0: Basic Scaffold & Hello Logs

## Overview

M0 provides the foundational infrastructure for Logforge, including basic health monitoring, API scaffolding, and core log ingestion capabilities. This milestone establishes the "Hello World" equivalent for log processing systems.

## Features

### 🏥 Health Monitoring
- **Endpoint**: `GET /health`
- **Purpose**: System health verification and service dependency checks
- **Response**: JSON with overall status, timestamp, and individual service status
- **Services Monitored**: ClickHouse database connectivity

### 🏠 Root API Information
- **Endpoint**: `GET /`
- **Purpose**: API metadata and feature discovery
- **Response**: API version, capabilities, documentation links
- **Features Listed**: Multi-format ingestion, storage tiering, analytics, SIEM

### 📥 Basic Log Ingestion
- **Endpoint**: `POST /v1/ingest/logs`
- **Purpose**: Single log entry ingestion
- **Format**: JSON log entries with structured fields
- **Storage**: Direct ClickHouse insertion with legacy table compatibility

### 📤 Basic Log Retrieval
- **Endpoint**: `GET /v1/logs`
- **Purpose**: Simple log querying with basic filters
- **Parameters**: `service`, `level`, `start_time`, `end_time`, `limit`
- **Response**: JSON array of log entries with metadata

## API Endpoints

| Method | Endpoint | Description | Status |
|--------|----------|-------------|--------|
| GET | `/health` | Health check with service status | ✅ Tested |
| GET | `/` | API information and features | ✅ Tested |
| POST | `/v1/ingest/logs` | Ingest single log entry | ✅ Tested |
| GET | `/v1/logs` | Retrieve logs with basic filtering | ✅ Tested |

## Data Schema

### Log Entry Structure
```json
{
  "ts": "2025-08-26T18:30:00.000Z",      // ISO timestamp
  "service": "web-server",                // Service identifier
  "level": "INFO",                        // Log level
  "msg": "Request processed successfully", // Message content
  "host": "web-01",                       // Source host
  "trace_id": "req-12345",               // Optional trace ID
  "attrs": {}                            // Additional attributes
}
```

### Health Response Structure
```json
{
  "status": "healthy",
  "timestamp": "2025-08-26T18:30:00.000Z",
  "services": {
    "clickhouse": "healthy"
  }
}
```

## Storage Architecture

### Tables Used
- **`logs_raw`**: Primary storage for ingested logs
- **Legacy Support**: Maintains backward compatibility with existing schema

### Fields Stored
| Field | Type | Description | Required |
|-------|------|-------------|----------|
| ts | DateTime64 | Event timestamp | Yes |
| host | String | Source hostname | No |
| service | String | Service name | Yes |
| level | String | Log level | Yes |
| msg | String | Log message | Yes |
| trace_id | String | Trace identifier | No |
| attrs | JSON | Additional attributes | No |

## Test Coverage

### Test Suite: `test_m0_individual.py`
- ✅ **Health Check Test**: Verifies API health and ClickHouse connectivity
- ✅ **Root Endpoint Test**: Validates API metadata and feature listing
- ✅ **Basic Ingestion Test**: Tests single log entry ingestion
- ✅ **Basic Retrieval Test**: Tests log querying and filtering

### Test Results
```
M0 Results: 4/4 tests passed
✅ M0 Basic Scaffold & Hello Logs: ALL TESTS PASSED
```

## Performance Characteristics

- **Ingestion Latency**: ~10-50ms per log entry
- **Storage**: Direct ClickHouse insertion
- **Concurrency**: Single-threaded processing
- **Scalability**: Designed for development/testing workloads

## Dependencies

### Required Services
- **ClickHouse**: Primary data storage
- **FastAPI**: Web framework for API endpoints
- **Docker**: Containerized deployment

### Configuration
- **Host**: `localhost:7080` (external), `api:8080` (container)
- **Database**: `logforge` schema in ClickHouse
- **Timeout**: 30s for ingestion operations

## Known Limitations

1. **Single Log Processing**: No batch ingestion capability
2. **Basic Filtering**: Limited query capabilities
3. **No Multi-Tenancy**: Single-tenant storage model
4. **No TTL Management**: No automated data lifecycle
5. **No Format Parsing**: JSON-only log acceptance

## Next Steps

M0 serves as the foundation for:
- **M1**: Multi-format ingestion and storage lifecycle management
- **M2**: Advanced querying and dashboard capabilities
- **M3**: Alert engine and notification systems
- **M4**: Security analytics and SIEM functionality

## Usage Examples

### Basic Log Ingestion
```bash
curl -X POST http://localhost:7080/v1/ingest/logs \
  -H "Content-Type: application/json" \
  -d '{
    "ts": "2025-08-26T18:30:00.000Z",
    "service": "web-server",
    "level": "INFO",
    "msg": "User login successful",
    "host": "web-01",
    "trace_id": "login-12345"
  }'
```

### Basic Log Retrieval
```bash
curl "http://localhost:7080/v1/logs?service=web-server&limit=10"
```

### Health Check
```bash
curl http://localhost:7080/health
```

## Architecture Decisions

1. **FastAPI Framework**: Chosen for async capabilities and automatic OpenAPI generation
2. **ClickHouse Storage**: Selected for high-performance log analytics
3. **JSON Format**: Standard log format for initial implementation
4. **Direct Storage**: Immediate persistence without queuing for simplicity
5. **Legacy Schema**: Maintains compatibility with existing log formats