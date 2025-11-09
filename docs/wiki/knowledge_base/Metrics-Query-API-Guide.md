# Metrics Query API Guide
## Complete Reference for Logforge Observability Metrics

### 📋 Overview
This guide covers all types of queries you can perform with the Logforge Metrics Query API (`POST /v1/observability/metrics/query`). The API provides flexible time series data analysis with aggregation capabilities.

---

## 🎯 **API Endpoint**
```
POST /v1/observability/metrics/query
Content-Type: application/json
X-Customer-ID: your-customer-id
```

---

## 📊 **Query Types & Examples**

### 1. **Raw Time Series Query**
Get individual metric data points over time (no aggregation).

```json
{
  "metric_name": "cpu_usage",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "granularity": "1m"
}
```

**Response:**
```json
{
  "metrics": {
    "cpu_usage": [
      {"timestamp": "2024-11-09T10:00:00Z", "value": 45.2},
      {"timestamp": "2024-11-09T10:01:00Z", "value": 47.8},
      {"timestamp": "2024-11-09T10:02:00Z", "value": 44.1}
    ]
  },
  "aggregation": null,
  "granularity": "1m",
  "customer_id": "832f393c-d9de-4a80-a183-aa913ad27266"
}
```

### 2. **Aggregated Metrics Query**
Get aggregated values (avg, sum, max, min, count).

```json
{
  "metric_name": "cpu_usage",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "aggregation": "avg"
}
```

**Response:**
```json
{
  "metrics": {
    "cpu_usage": [{
      "metric_name": "cpu_usage",
      "aggregation": "avg",
      "value": 46.2,
      "data_points": 60,
      "time_range": {
        "start": "2024-11-09T10:00:00Z",
        "end": "2024-11-09T10:59:00Z",
        "hours": 1
      }
    }]
  },
  "aggregation": "avg",
  "granularity": "1m",
  "customer_id": "832f393c-d9de-4a80-a183-aa913ad27266"
}
```

### 3. **Service-Specific Metrics**
Filter metrics by service.

```json
{
  "metric_name": "response_time",
  "service_name": "web-api",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "aggregation": "avg"
}
```

### 4. **Multiple Aggregations**
Compare different aggregation functions.

**Average CPU Usage:**
```json
{
  "metric_name": "cpu_usage",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "aggregation": "avg"
}
```

**Maximum CPU Usage:**
```json
{
  "metric_name": "cpu_usage",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "aggregation": "max"
}
```

**Total Request Count:**
```json
{
  "metric_name": "request_count",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "aggregation": "sum"
}
```

### 5. **Label-Based Filtering**
Filter metrics by labels/tags.

```json
{
  "metric_name": "response_time",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "labels": {
    "environment": "production",
    "region": "us-east-1"
  },
  "aggregation": "avg"
}
```

### 6. **Different Time Granularities**
Control time bucket sizes for visualization.

**1-minute granularity:**
```json
{
  "metric_name": "cpu_usage",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T10:05:00Z",
  "granularity": "1m"
}
```

**5-minute granularity:**
```json
{
  "metric_name": "cpu_usage",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "granularity": "5m"
}
```

**1-hour granularity:**
```json
{
  "metric_name": "cpu_usage",
  "start_time": "2024-11-09T00:00:00Z",
  "end_time": "2024-11-10T00:00:00Z",
  "granularity": "1h"
}
```

### 7. **Long-Term Analysis**
Query data over extended periods.

**Weekly CPU trends:**
```json
{
  "metric_name": "cpu_usage",
  "start_time": "2024-11-02T00:00:00Z",
  "end_time": "2024-11-09T00:00:00Z",
  "aggregation": "avg",
  "granularity": "1h"
}
```

**Monthly request volume:**
```json
{
  "metric_name": "request_count",
  "start_time": "2024-10-01T00:00:00Z",
  "end_time": "2024-11-01T00:00:00Z",
  "aggregation": "sum",
  "granularity": "1h"
}
```

---

## 📈 **Common Metric Types & Use Cases**

### **Infrastructure Metrics**

**CPU Usage Analysis:**
```json
{
  "metric_name": "cpu_usage",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "aggregation": "avg"
}
```

**Memory Usage Monitoring:**
```json
{
  "metric_name": "memory_usage",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "aggregation": "max"
}
```

**Disk I/O Performance:**
```json
{
  "metric_name": "disk_io_read_bytes",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "aggregation": "sum"
}
```

### **Application Metrics**

**Request Rate Monitoring:**
```json
{
  "metric_name": "requests_per_second",
  "service_name": "web-api",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "aggregation": "avg"
}
```

**Error Rate Analysis:**
```json
{
  "metric_name": "error_rate",
  "service_name": "payment-service",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "aggregation": "avg"
}
```

**Response Time Trends:**
```json
{
  "metric_name": "response_time_ms",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "aggregation": "avg"
}
```

### **Business Metrics**

**User Activity:**
```json
{
  "metric_name": "active_users",
  "start_time": "2024-11-09T00:00:00Z",
  "end_time": "2024-11-10T00:00:00Z",
  "aggregation": "max"
}
```

**Revenue Tracking:**
```json
{
  "metric_name": "revenue_usd",
  "start_time": "2024-11-01T00:00:00Z",
  "end_time": "2024-12-01T00:00:00Z",
  "aggregation": "sum"
}
```

---

## ⚙️ **Query Parameters Reference**

| Parameter | Type | Required | Description | Examples |
|-----------|------|----------|-------------|----------|
| `metric_name` | string | No | Filter by specific metric | `"cpu_usage"`, `"response_time"` |
| `service_name` | string | No | Filter by service | `"web-api"`, `"payment-service"` |
| `start_time` | datetime | **Yes** | Query start time (ISO 8601) | `"2024-11-09T10:00:00Z"` |
| `end_time` | datetime | **Yes** | Query end time (ISO 8601) | `"2024-11-09T11:00:00Z"` |
| `labels` | object | No | Label-based filtering | `{"env": "prod", "region": "us-east"}` |
| `aggregation` | string | No | Aggregation function | `"avg"`, `"sum"`, `"max"`, `"min"`, `"count"` |
| `granularity` | string | No | Time bucket size | `"1m"`, `"5m"`, `"1h"` |

---

## 🔄 **Aggregation Functions**

| Function | Description | Use Case | Example |
|----------|-------------|----------|---------|
| **avg** | Average value | CPU usage, response times | `{"aggregation": "avg"}` |
| **sum** | Total sum | Request counts, data volumes | `{"aggregation": "sum"}` |
| **max** | Maximum value | Peak usage, worst-case performance | `{"aggregation": "max"}` |
| **min** | Minimum value | Best performance, baseline | `{"aggregation": "min"}` |
| **count** | Number of data points | Data availability, sampling rate | `{"aggregation": "count"}` |

---

## 🕐 **Time Range Examples**

### **Real-Time Monitoring (Last 5 minutes)**
```json
{
  "start_time": "2024-11-09T10:55:00Z",
  "end_time": "2024-11-09T11:00:00Z"
}
```

### **Hourly Analysis**
```json
{
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z"
}
```

### **Daily Trends**
```json
{
  "start_time": "2024-11-08T00:00:00Z",
  "end_time": "2024-11-09T00:00:00Z"
}
```

### **Weekly Analysis**
```json
{
  "start_time": "2024-11-02T00:00:00Z",
  "end_time": "2024-11-09T00:00:00Z"
}
```

### **Monthly Reports**
```json
{
  "start_time": "2024-10-01T00:00:00Z",
  "end_time": "2024-11-01T00:00:00Z"
}
```

---

## 📤 **Response Formats**

### **Raw Time Series Response**
When no `aggregation` is specified:
```json
{
  "metrics": {
    "cpu_usage": [
      {"timestamp": "2024-11-09T10:00:00Z", "value": 45.2},
      {"timestamp": "2024-11-09T10:01:00Z", "value": 47.8},
      {"timestamp": "2024-11-09T10:02:00Z", "value": 44.1}
    ]
  },
  "aggregation": null,
  "granularity": "1m",
  "customer_id": "832f393c-d9de-4a80-a183-aa913ad27266"
}
```

### **Aggregated Response**
When `aggregation` is specified:
```json
{
  "metrics": {
    "cpu_usage": [{
      "metric_name": "cpu_usage",
      "aggregation": "avg",
      "value": 46.2,
      "data_points": 60,
      "time_range": {
        "start": "2024-11-09T10:00:00Z",
        "end": "2024-11-09T10:59:00Z",
        "hours": 1
      }
    }]
  },
  "aggregation": "avg",
  "granularity": "1m",
  "customer_id": "832f393c-d9de-4a80-a183-aa913ad27266"
}
```

### **No Data Response**
When no metrics are found:
```json
{
  "message": "No metric data found for 'cpu_usage' in the specified time range",
  "metrics": {},
  "aggregation": "avg",
  "granularity": "1m",
  "customer_id": "832f393c-d9de-4a80-a183-aa913ad27266"
}
```

---

## 🛠️ **Dashboard Use Cases**

### **1. Real-Time System Dashboard**
Monitor live system metrics with 1-minute granularity.

**CPU Usage:**
```json
{
  "metric_name": "cpu_usage",
  "start_time": "2024-11-09T10:55:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "granularity": "1m"
}
```

**Memory Usage:**
```json
{
  "metric_name": "memory_usage",
  "start_time": "2024-11-09T10:55:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "granularity": "1m"
}
```

### **2. Application Performance Dashboard**
Track application health and performance.

**Request Rate:**
```json
{
  "metric_name": "requests_per_second",
  "service_name": "web-api",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "aggregation": "avg"
}
```

**Error Percentage:**
```json
{
  "metric_name": "error_rate",
  "service_name": "web-api",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "aggregation": "avg"
}
```

### **3. Business Intelligence Dashboard**
Track business metrics and KPIs.

**Daily Revenue:**
```json
{
  "metric_name": "revenue_usd",
  "start_time": "2024-11-08T00:00:00Z",
  "end_time": "2024-11-09T00:00:00Z",
  "aggregation": "sum"
}
```

**Active Users:**
```json
{
  "metric_name": "daily_active_users",
  "start_time": "2024-11-01T00:00:00Z",
  "end_time": "2024-11-09T00:00:00Z",
  "aggregation": "avg",
  "granularity": "1h"
}
```

---

## 🚨 **Alerting Queries**

### **Threshold-Based Alerts**
Query current values to compare against thresholds.

**High CPU Alert:**
```json
{
  "metric_name": "cpu_usage",
  "start_time": "2024-11-09T10:55:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "aggregation": "avg"
}
```
*Alert if value > 80%*

**Low Disk Space Alert:**
```json
{
  "metric_name": "disk_free_percent",
  "start_time": "2024-11-09T10:55:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "aggregation": "min"
}
```
*Alert if value < 10%*

### **Trend-Based Alerts**
Detect unusual patterns over time.

**Error Rate Spike:**
```json
{
  "metric_name": "error_rate",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "aggregation": "avg"
}
```
*Alert if current > baseline + 2σ*

---

## 🔍 **Debugging & Troubleshooting**

### **Common Issues**

**1. No Data Returned**
```json
{
  "message": "No metric data found for 'cpu_usage' in the specified time range",
  "metrics": {}
}
```

**Possible Causes:**
- Metric name doesn't exist
- Time range is outside data availability
- Service name filter excludes all data
- No metrics ingested for that period

**2. Empty Raw Time Series**
```json
{
  "metrics": {}
}
```

**Debugging Steps:**
- Check if metrics are being ingested: `GET /v1/observability/health`
- Verify metric names: Remove `metric_name` filter to see all available metrics
- Expand time range: Try longer time windows
- Check service filters: Remove `service_name` to see all services

### **3. Validation Errors**
```json
{
  "detail": "Field required",
  "type": "missing"
}
```

**Required Fields:**
- `start_time` (always required)
- `end_time` (always required)

### **4. Getting Aggregated Data Instead of Time Series**
**Problem**: You want individual data points but get aggregated values.
**Solution**: Remove the `aggregation` parameter from your request.

**Wrong:**
```json
{
  "metric_name": "cpu_usage",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z",
  "aggregation": "avg"  // Remove this
}
```

**Correct:**
```json
{
  "metric_name": "cpu_usage",
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z"
}
```

---

## 🎯 **Performance Tips**

### **Optimize Query Performance**

**1. Use Specific Metric Names**
```json
// Good - specific metric
{"metric_name": "cpu_usage"}

// Avoid - querying all metrics
{}
```

**2. Limit Time Ranges**
```json
// Good - 1 hour window
{
  "start_time": "2024-11-09T10:00:00Z",
  "end_time": "2024-11-09T11:00:00Z"
}

// Avoid - very large windows without aggregation
{
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-11-09T11:00:00Z"
}
```

**3. Use Aggregation for Large Datasets**
```json
// Good - aggregated for large time ranges
{
  "start_time": "2024-11-01T00:00:00Z",
  "end_time": "2024-11-09T00:00:00Z",
  "aggregation": "avg"
}
```

**4. Choose Appropriate Granularity**
```json
// Good - 1h granularity for daily views
{
  "start_time": "2024-11-08T00:00:00Z",
  "end_time": "2024-11-09T00:00:00Z",
  "granularity": "1h"
}

// Avoid - 1m granularity for large time ranges
{
  "start_time": "2024-11-01T00:00:00Z",
  "end_time": "2024-11-09T00:00:00Z",
  "granularity": "1m"  // Too many data points
}
```

---

## 📝 **Quick Reference**

### **Common Query Patterns**

| Use Case | Query Pattern | Response Type |
|----------|---------------|---------------|
| Chart visualization | No `aggregation` | Raw time series |
| KPI dashboard | With `aggregation` | Single aggregated value |
| Real-time monitoring | Recent time range, no aggregation | Live data points |
| Historical analysis | Long time range, with aggregation | Summarized data |
| Alerting | Current time window, with aggregation | Threshold comparison |

### **Response Type Guide**

| Query Has `aggregation`? | Response Format |
|-------------------------|-----------------|
| **No** (or `null`) | Array of `{timestamp, value}` objects |
| **Yes** | Single aggregated object with metadata |

---

This comprehensive guide covers all query types and use cases for the Logforge Metrics Query API. Use these examples as templates for building your own monitoring, alerting, and analytics solutions.