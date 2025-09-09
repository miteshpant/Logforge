# Tenant User Story: Advanced Log Querying and Analysis

## Story
**As a** Senior Software Engineer  
**I want to** perform sophisticated log analysis and troubleshooting  
**So that** I can identify root causes, optimize performance, and maintain system reliability

## User Journey

### 1. Access Query Interface
- Engineer logs into Logforge at `http://localhost:3001`
- Navigates to Query & Analytics section
- Views query interface with:
  - Query builder (visual)
  - Advanced query editor (SQL-like syntax)
  - Saved queries library
  - Query history

### 2. Basic Error Investigation
- Production issue reported: Users can't complete payments
- Engineer starts with simple query:
```
service = "payment-service" AND level = "ERROR"
```
- System calls `POST /v1/query/advanced`
- Results show 23 errors in last hour
- Identifies pattern: "Database timeout" errors

### 3. Time-Series Analysis
- Engineer investigates error trends over time
- Configures time-series query:
  - **Time Range**: Last 24 hours
  - **Interval**: 1 hour buckets
  - **Metrics**: Error count, error rate
  - **Group By**: service, error_type
- System calls `POST /v1/query/timeseries`
- Visualizes error spike starting at 14:00

### 4. Advanced Filtering and Correlation
- Engineer creates complex multi-condition query:
```json
{
  "time_range": {
    "start": "2024-01-15T12:00:00Z",
    "end": "2024-01-15T16:00:00Z"
  },
  "filters": [
    {"field": "service", "operator": "eq", "value": "payment-service"},
    {"field": "level", "operator": "in", "value": ["ERROR", "FATAL"]},
    {"field": "message", "operator": "contains", "value": "database"},
    {"field": "response_time", "operator": "gt", "value": 5000}
  ],
  "aggregations": [
    {
      "type": "terms",
      "field": "error_code",
      "size": 10
    },
    {
      "type": "avg",
      "field": "response_time"
    }
  ]
}
```

### 5. Cross-Service Log Correlation
- Engineer suspects cascading failure
- Creates correlation query across multiple services:
```
(service = "payment-service" OR service = "database-proxy" OR service = "auth-service")
AND (level = "ERROR" OR level = "WARN")
AND timestamp >= "2024-01-15T14:00:00Z"
```
- Uses trace_id for distributed tracing:
```
trace_id = "abc123def456" AND timestamp >= "2024-01-15T14:00:00Z"
```
- Maps request flow across service boundaries

### 6. Performance Analysis Query
- Engineer investigates slow requests
- Builds performance analysis query:
```json
{
  "filters": [
    {"field": "service", "operator": "eq", "value": "web-api"},
    {"field": "response_time", "operator": "gte", "value": 1000}
  ],
  "aggregations": [
    {
      "type": "percentiles",
      "field": "response_time",
      "percents": [50, 90, 95, 99]
    },
    {
      "type": "terms",
      "field": "endpoint",
      "size": 20
    }
  ],
  "sort": [
    {"field": "response_time", "order": "desc"}
  ]
}
```
- Identifies slowest endpoints and percentile distributions

### 7. Pattern Matching and Regex Analysis
- Engineer searches for specific error patterns
- Uses regex for flexible pattern matching:
```
message REGEX "Payment failed.*card.*declined.*error_code:\s*(\d+)"
```
- Extracts error codes and categorizes failures:
  - Card declined: 67% of failures
  - Insufficient funds: 23% of failures
  - Expired card: 10% of failures

### 8. Statistical Analysis and Anomaly Detection
- Engineer performs statistical analysis on metrics
- Queries for statistical calculations:
```json
{
  "time_range": {
    "start": "2024-01-08T00:00:00Z",
    "end": "2024-01-15T23:59:59Z"
  },
  "aggregations": [
    {
      "type": "stats",
      "field": "response_time",
      "group_by": ["service", "endpoint"]
    },
    {
      "type": "date_histogram",
      "field": "timestamp",
      "interval": "1h",
      "sub_aggregations": [
        {"type": "avg", "field": "response_time"},
        {"type": "count"}
      ]
    }
  ]
}
```
- Calculates standard deviations and identifies outliers

### 9. Save and Share Query
- Engineer saves complex query for future use
- System calls `POST /v1/query/saved`
- Query saved with metadata:
  - Name: "Payment Service Error Analysis"
  - Description: "Root cause analysis for payment failures"
  - Tags: ["payment", "troubleshooting", "production"]
  - Schedule: Run daily at 9 AM
- Shares query link with team for collaboration

### 10. Export Results for Analysis
- Engineer needs data for external analysis
- Exports query results in multiple formats:
  - **CSV**: For spreadsheet analysis
  - **JSON**: For programmatic processing
  - **Dashboard**: Create monitoring dashboard
- System calls `POST /v1/export`
- Downloads 10,000 log entries for offline analysis

### 11. Real-Time Query Monitoring
- Engineer sets up continuous monitoring query
- Creates live query with auto-refresh:
```
service = "critical-service" AND level = "ERROR" AND timestamp > now() - 5m
```
- Query refreshes every 30 seconds
- Enables real-time issue detection during incident

### 12. Query Performance Optimization
- Complex query running slowly (>10 seconds)
- Engineer optimizes query structure:
  - Adds time range constraints
  - Uses indexed fields in filters
  - Reduces aggregation complexity
  - Optimizes sort operations
- Query execution time reduced to 1.2 seconds

### 13. Business Intelligence Queries
- Engineer creates business-focused analysis:
```json
{
  "filters": [
    {"field": "event_type", "operator": "eq", "value": "purchase"},
    {"field": "status", "operator": "eq", "value": "completed"}
  ],
  "aggregations": [
    {
      "type": "terms",
      "field": "product_category",
      "size": 10,
      "sub_aggregations": [
        {"type": "sum", "field": "revenue"}
      ]
    },
    {
      "type": "date_histogram",
      "field": "timestamp",
      "interval": "1d",
      "sub_aggregations": [
        {"type": "sum", "field": "revenue"},
        {"type": "cardinality", "field": "user_id"}
      ]
    }
  ]
}
```
- Analyzes revenue by product category and daily trends

## API Endpoints Used
- `POST /v1/query/advanced` - Execute advanced queries
- `POST /v1/query/timeseries` - Time-series analysis
- `POST /v1/query/aggregate` - Aggregation queries
- `GET /v1/query/saved` - List saved queries
- `POST /v1/query/saved` - Save query
- `GET /v1/query/saved/{id}` - Retrieve saved query
- `POST /v1/export` - Export query results
- `GET /v1/logs` - Basic log retrieval

## Success Criteria
- Complex queries execute within 3 seconds for 24-hour windows
- Query results are accurate and complete
- Visual query builder handles common use cases
- Advanced syntax supports sophisticated analysis
- Saved queries enable reusability and sharing
- Export functionality supports multiple formats
- Real-time queries provide immediate insights
- Query performance scales with data volume

## Technical Implementation
- **Query Engine**: ClickHouse-optimized query processing
- **Query Language**: SQL-like syntax with log-specific extensions
- **Performance**: Query optimization and caching
- **Visualization**: Real-time charts and data tables
- **Export**: Multiple format support (CSV, JSON, PDF)
- **Collaboration**: Query sharing and version control
- **UI**: Advanced query builder with syntax highlighting