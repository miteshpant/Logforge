# AI Router API Documentation

## Overview

The AI Router (`/v1/ai/*`) provides comprehensive artificial intelligence and machine learning capabilities for log analysis, incident investigation, and operational insights. This API enables natural language queries, automated root cause analysis, anomaly detection, and intelligent recommendations.

## Table of Contents

1. [Authentication & Subscriptions](#authentication--subscriptions)
2. [Natural Language Query System](#natural-language-query-system)
3. [Incident Investigation & Analysis](#incident-investigation--analysis)
4. [Machine Learning Baselines](#machine-learning-baselines)
5. [Anomaly Detection](#anomaly-detection)
6. [Knowledge Base Operations](#knowledge-base-operations)
7. [Operational Insights & Correlation](#operational-insights--correlation)
8. [Advanced AI Features](#advanced-ai-features)
9. [Error Handling](#error-handling)
10. [Rate Limits & Performance](#rate-limits--performance)

---

## Authentication & Subscriptions

### Required Headers
```http
Authorization: Bearer <your-access-token>
X-Customer-ID: <your-tenant-id>
Content-Type: application/json
```

### Required Subscription Features
The AI router requires an **Enterprise** subscription with the following features:
- `ai.*` (wildcard for all AI features)
- `ai_assistant.basic` - Basic AI health checks
- `ai_assistant.query` - Natural language queries
- `ai_assistant.analysis` - Incident analysis
- `ai_assistant.rca` - Root cause analysis
- `ai_assistant.anomaly` - Anomaly detection
- `ai_assistant.investigation` - Investigation workflows

### Health Check
```http
GET /v1/ai/health
```

**Response:**
```json
{
  "status": "healthy",
  "message": "AI services are operational",
  "features": [
    "natural_language_query",
    "incident_analysis",
    "anomaly_detection",
    "knowledge_base"
  ],
  "models_loaded": 5,
  "last_training": "2024-09-26T10:30:00Z"
}
```

---

## Natural Language Query System

### Process Natural Language Queries
Convert natural language questions into SQL queries and execute them against your log data.

```http
POST /v1/ai/query
```

**Request Body:**
```json
{
  "question": "Show me all error logs from the last 24 hours",
  "context": {
    "time_range": "24h",
    "priority": "high",
    "services": ["payment-api", "user-service"]
  },
  "max_results": 50
}
```

**Response:**
```json
{
  "query_id": "nlq_abc123",
  "original_question": "Show me all error logs from the last 24 hours",
  "generated_sql": "SELECT service, level, count(*) as error_count FROM logs_normalized_mt WHERE level = 'ERROR' AND ts >= now() - INTERVAL 24 HOUR AND customer_id = 'tenant-123' GROUP BY service, level ORDER BY error_count DESC LIMIT 50",
  "explanation": "Analyzing error patterns across services in the last 24 hours",
  "results": {
    "columns": ["service", "level", "error_count"],
    "rows": [
      ["payment-api", "ERROR", 145],
      ["user-service", "ERROR", 67]
    ],
    "total_rows": 2
  },
  "suggestions": [
    "Investigate payment-api high error rate",
    "Check recent deployments",
    "Review database connectivity"
  ],
  "confidence_score": 0.85,
  "execution_time_ms": 245,
  "customer_id": "tenant-123"
}
```

### Query History
Retrieve your previous natural language queries.

```http
GET /v1/ai/query/history?limit=10
```

**Response:**
```json
{
  "history": [
    {
      "query_id": "nlq_abc123",
      "question": "Show me all error logs from the last 24 hours",
      "timestamp": "2024-09-26T10:30:00Z",
      "confidence_score": 0.85,
      "feedback_score": 1
    }
  ],
  "total": 1,
  "user_id": "user-456",
  "customer_id": "tenant-123"
}
```

### Submit Query Feedback
Provide feedback to improve AI query accuracy.

```http
POST /v1/ai/query/feedback
```

**Request Body:**
```json
{
  "query_id": "nlq_abc123",
  "feedback_score": 1,
  "feedback_notes": "Very helpful query results"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Feedback recorded successfully",
  "query_id": "nlq_abc123"
}
```

---

## Incident Investigation & Analysis

### Start AI-Powered Investigation
Initiate automated incident investigation with hypothesis generation.

```http
POST /v1/ai/investigate
```

**Request Body:**
```json
{
  "title": "Payment API Performance Degradation",
  "description": "Users reporting slow payment processing",
  "incident_data": {
    "service": "payment-api",
    "symptoms": ["high latency", "connection errors"],
    "start_time": "2024-09-26T09:00:00Z",
    "severity": "high"
  },
  "context": {
    "recent_deployment": true,
    "traffic_spike": false,
    "business_impact": "high"
  }
}
```

**Response:**
```json
{
  "investigation_id": "inv_789xyz",
  "title": "Payment API Performance Degradation",
  "status": "running",
  "hypothesis": [
    "Database connection pool exhaustion",
    "Recent deployment introduced performance regression",
    "Memory leak in payment processing service"
  ],
  "next_steps": [
    "Analyze database connection metrics",
    "Review recent deployment changes",
    "Check memory usage patterns"
  ],
  "estimated_completion": "5-10 minutes",
  "started_at": "2024-09-26T10:30:00Z",
  "customer_id": "tenant-123"
}
```

### Get Investigation Status
Check the progress and results of an ongoing investigation.

```http
GET /v1/ai/investigate/{investigation_id}
```

**Response:**
```json
{
  "investigation_id": "inv_789xyz",
  "title": "Payment API Performance Degradation",
  "status": "completed",
  "progress": 100,
  "findings": [
    {
      "category": "database",
      "severity": "high",
      "description": "Connection pool utilization at 98%",
      "confidence": 0.92
    }
  ],
  "recommendations": [
    "Increase database connection pool size from 50 to 100",
    "Implement connection pooling monitoring",
    "Review slow query performance"
  ],
  "timeline": [
    {
      "timestamp": "2024-09-26T09:00:00Z",
      "event": "Investigation started",
      "details": "Analyzing symptoms and context"
    }
  ],
  "completed_at": "2024-09-26T10:37:00Z",
  "customer_id": "tenant-123"
}
```

### Automated Root Cause Analysis
Perform deep analysis of specific incidents with business impact assessment.

```http
POST /v1/ai/analyze
```

**Request Body:**
```json
{
  "incident": {
    "id": "incident-456",
    "description": "Payment API performance degradation",
    "symptoms": ["high response time", "database connection issues"],
    "affected_services": ["payment-api", "user-service"],
    "start_time": "2024-09-26T09:00:00Z",
    "duration_minutes": 45
  },
  "context": {
    "business_context": {
      "revenue_per_hour": 15000,
      "peak_traffic_time": true
    },
    "recent_deployment": true,
    "infrastructure_changes": false
  }
}
```

**Response:**
```json
{
  "analysis_id": "rca_def456",
  "incident_id": "incident-456",
  "primary_cause": "Database connection pool exhaustion due to recent deployment increasing query complexity",
  "contributing_factors": [
    "High volume of database connection issues (234 occurrences)",
    "Moderate ERROR error spike detected",
    "Errors concentrated from few sources - possible targeted issue",
    "Server-side errors indicate internal service problems"
  ],
  "timeline": [
    {
      "timestamp": "2024-09-26T09:00:00Z",
      "event": "Performance degradation detected",
      "impact": "Response times increased to 2.5s"
    },
    {
      "timestamp": "2024-09-26T09:15:00Z",
      "event": "Database connection errors spike",
      "impact": "Payment processing failures increased by 300%"
    }
  ],
  "business_impact": {
    "estimated_revenue_loss": 11250,
    "customers_affected": 1247,
    "severity": "high",
    "downtime_minutes": 45
  },
  "recommendations": [
    {
      "priority": "immediate",
      "action": "Increase database connection pool size",
      "rationale": "Address immediate resource constraint",
      "estimated_time": "15 minutes"
    },
    {
      "priority": "short_term",
      "action": "Review recent deployment changes",
      "rationale": "Identify performance regression",
      "estimated_time": "2 hours"
    }
  ],
  "similar_incidents": [
    {
      "incident_id": "incident-123",
      "similarity_score": 0.87,
      "resolution": "Database scaling resolved issue"
    }
  ],
  "confidence_score": 0.91,
  "customer_id": "tenant-123"
}
```

---

## Machine Learning Baselines

### Save ML Model Baseline
Store performance baselines for anomaly detection.

```http
POST /v1/ai/baselines
```

**Request Body:**
```json
{
  "model_id": "payment-api-baseline-v1",
  "service_name": "payment-api",
  "baseline_type": "anomaly",
  "baseline_data": {
    "avg_response_time": 250,
    "p95_response_time": 450,
    "error_rate": 0.02,
    "throughput": 1000
  },
  "training_metrics": {
    "accuracy_score": 0.89,
    "false_positive_rate": 0.03,
    "sample_count": 50000,
    "training_period": "30d"
  }
}
```

**Response:**
```json
{
  "status": "saved",
  "model_id": "payment-api-baseline-v1",
  "version": "1.0",
  "saved_at": "2024-09-26T10:30:00Z",
  "next_training": "2024-10-26T10:30:00Z"
}
```

### List ML Baselines
Retrieve stored baselines with optional filtering.

```http
GET /v1/ai/baselines?service_name=payment-api&baseline_type=anomaly
```

**Response:**
```json
{
  "baselines": [
    {
      "model_id": "payment-api-baseline-v1",
      "service_name": "payment-api",
      "baseline_type": "anomaly",
      "created_at": "2024-09-26T10:30:00Z",
      "last_updated": "2024-09-26T10:30:00Z",
      "accuracy": 0.89,
      "status": "active"
    }
  ],
  "total": 1,
  "filters": {
    "service_name": "payment-api",
    "baseline_type": "anomaly"
  },
  "customer_id": "tenant-123"
}
```

---

## Anomaly Detection

### Detect Anomalies
Identify unusual patterns in your log data using ML baselines.

```http
POST /v1/ai/anomalies/detect
```

**Request Body:**
```json
{
  "time_range": "4h",
  "severity_filter": ["high", "medium"],
  "category_filter": ["performance"],
  "service_filter": ["payment-api", "user-service"]
}
```

**Response:**
```json
{
  "anomalies": [
    {
      "id": "anomaly_abc123",
      "service_name": "payment-api",
      "anomaly_type": "response_time_spike",
      "severity": "high",
      "score": 0.94,
      "detected_at": "2024-09-26T10:25:00Z",
      "description": "Response time 300% above baseline",
      "baseline_value": 250,
      "current_value": 750,
      "confidence": 0.91
    }
  ],
  "summary": {
    "total_anomalies": 1,
    "high_severity": 1,
    "medium_severity": 0,
    "services_affected": ["payment-api"]
  },
  "time_range": "4h",
  "detection_timestamp": "2024-09-26T10:30:00Z",
  "customer_id": "tenant-123"
}
```

---

## Knowledge Base Operations

### Search Knowledge Base
Find solutions based on symptoms and service context.

```http
POST /v1/ai/knowledge/search
```

**Request Body:**
```json
{
  "symptoms": "connection timeout, slow queries",
  "services": "payment-api",
  "category": "database"
}
```

**Response:**
```json
{
  "solutions": [
    {
      "solution_id": "sol_789",
      "title": "Database Connection Pool Optimization",
      "description": "Resolve connection timeouts by optimizing pool configuration",
      "confidence": 0.87,
      "tags": ["database", "performance", "connection"],
      "steps": [
        "Increase connection pool size",
        "Monitor connection usage",
        "Optimize query performance"
      ],
      "estimated_time": "30 minutes",
      "success_rate": 0.92
    }
  ],
  "total_found": 1,
  "search_terms": ["connection", "timeout", "database"],
  "knowledge_base_stats": {
    "total_solutions": 156,
    "last_updated": "2024-09-26T08:00:00Z"
  },
  "customer_id": "tenant-123"
}
```

### Add Solution to Knowledge Base
Contribute new solutions based on your incident resolutions.

```http
POST /v1/ai/knowledge/solutions
```

**Request Body:**
```json
{
  "incident_type": "database_connectivity",
  "symptoms": ["connection timeout", "slow queries", "high latency"],
  "solution": {
    "title": "Database Connection Pool Optimization",
    "description": "Increase connection pool size and optimize query performance",
    "steps": [
      "Increase connection pool from 50 to 100",
      "Optimize slow queries",
      "Monitor database performance"
    ],
    "estimated_time": "30 minutes"
  },
  "related_services": ["payment-api", "user-service"]
}
```

**Response:**
```json
{
  "status": "added",
  "solution_id": "sol_new456",
  "message": "Solution added to knowledge base",
  "confidence_score": 0.85
}
```

---

## Operational Insights & Correlation

### Get Operational Insights
Receive AI-powered recommendations and system insights.

```http
GET /v1/ai/insights
```

**Response:**
```json
{
  "insights": [
    {
      "type": "performance_trend",
      "priority": "high",
      "title": "Payment API showing performance degradation trend",
      "description": "Response times have increased 40% over the past week",
      "recommendation": "Consider scaling database resources",
      "confidence": 0.88,
      "detected_at": "2024-09-26T10:30:00Z"
    }
  ],
  "statistics": {
    "services_monitored": 15,
    "active_alerts": 3,
    "resolved_incidents_24h": 7,
    "overall_health_score": 0.87
  },
  "recommendations": [
    {
      "category": "optimization",
      "priority": "medium",
      "description": "Implement connection pooling for user-service",
      "estimated_impact": "20% performance improvement"
    }
  ],
  "generated_at": "2024-09-26T10:30:00Z",
  "customer_id": "tenant-123"
}
```

### Correlate Events
Find relationships between different events and metrics.

```http
POST /v1/ai/correlate
```

**Request Body:**
```json
{
  "events": [
    {
      "id": "event1",
      "timestamp": "2024-09-26T10:00:00Z",
      "service": "payment-api",
      "severity": "high",
      "type": "error",
      "message": "Database connection failed"
    },
    {
      "id": "event2",
      "timestamp": "2024-09-26T10:02:00Z",
      "service": "payment-api",
      "severity": "high",
      "type": "error",
      "message": "Service timeout"
    }
  ],
  "correlation_window": "10m",
  "confidence_threshold": 0.6
}
```

**Response:**
```json
{
  "correlations": [
    {
      "correlation_id": "corr_123",
      "events": ["event1", "event2"],
      "correlation_type": "temporal_sequence",
      "confidence": 0.89,
      "description": "Database connection failures followed by service timeouts",
      "suggested_cause": "Database connectivity issues cascading to service layer"
    }
  ],
  "total_events": 2,
  "correlation_window": "10m",
  "confidence_threshold": 0.6,
  "analysis_timestamp": "2024-09-26T10:30:00Z",
  "customer_id": "tenant-123"
}
```

---

## Advanced AI Features

### Predict Incidents
Use ML models to predict potential incidents.

```http
POST /v1/ai/predict?time_horizon=48h&confidence_threshold=0.8
```

**Response:**
```json
{
  "predictions": [
    {
      "prediction_id": "pred_456",
      "incident_type": "database_overload",
      "service": "payment-api",
      "probability": 0.82,
      "predicted_time": "2024-09-27T14:30:00Z",
      "indicators": [
        "Increasing connection pool utilization",
        "Growing query response times",
        "Memory usage trending upward"
      ],
      "prevention_actions": [
        "Scale database resources",
        "Optimize slow queries",
        "Implement query caching"
      ]
    }
  ],
  "time_horizon": "48h",
  "confidence_threshold": 0.8,
  "total_predictions": 1,
  "model_version": "v2.1",
  "generated_at": "2024-09-26T10:30:00Z",
  "customer_id": "tenant-123"
}
```

### Performance Optimization
Get AI-driven optimization recommendations.

```http
POST /v1/ai/optimize?service_name=payment-api&optimization_type=performance
```

**Response:**
```json
{
  "optimization_plan": {
    "service_name": "payment-api",
    "optimization_type": "performance",
    "optimizations": [
      {
        "category": "database",
        "recommendation": "Implement connection pooling",
        "expected_improvement": "25% response time reduction",
        "implementation_complexity": "medium",
        "estimated_effort": "4 hours"
      }
    ],
    "priority_order": [1],
    "total_estimated_improvement": "25%",
    "generated_at": "2024-09-26T10:30:00Z"
  },
  "customer_id": "tenant-123"
}
```

### List AI Models
View available AI models and their status.

```http
GET /v1/ai/models
```

**Response:**
```json
{
  "models": [
    {
      "model_id": "anomaly_detector_v2",
      "name": "Anomaly Detection Model",
      "type": "anomaly_detection",
      "status": "active",
      "accuracy": 0.89,
      "last_trained": "2024-09-25T10:00:00Z",
      "training_data_size": "1M samples"
    },
    {
      "model_id": "nlp_query_v1",
      "name": "Natural Language Query Model",
      "type": "natural_language_processing",
      "status": "active",
      "accuracy": 0.85,
      "last_trained": "2024-09-24T15:30:00Z",
      "training_data_size": "500K queries"
    }
  ],
  "total": 2,
  "active_models": 2,
  "last_model_update": "2024-09-25T10:00:00Z",
  "customer_id": "tenant-123"
}
```

---

## Error Handling

### Common Error Responses

#### Authentication Error (401)
```json
{
  "error": "authentication_required",
  "message": "Valid authentication token required",
  "code": 401
}
```

#### Subscription Error (403)
```json
{
  "error": "feature_not_subscribed",
  "message": "Feature 'ai_assistant.query' not included in subscription",
  "required_feature": "ai_assistant.query",
  "current_subscription": ["basic_features"],
  "upgrade_url": "/v1/tenants/{tenant_id}/subscription/upgrade"
}
```

#### Validation Error (422)
```json
{
  "error": "validation_error",
  "message": "Invalid request data",
  "details": [
    {
      "field": "question",
      "error": "Question is required for natural language queries"
    }
  ]
}
```

#### Rate Limit Error (429)
```json
{
  "error": "rate_limit_exceeded",
  "message": "AI query limit exceeded",
  "limit": 100,
  "reset_time": "2024-09-26T11:00:00Z",
  "retry_after": 1800
}
```

#### Internal Error (500)
```json
{
  "error": "internal_server_error",
  "message": "AI service temporarily unavailable",
  "request_id": "req_abc123",
  "support_reference": "Please contact support with this request ID"
}
```

---

## Rate Limits & Performance

### Rate Limits
- **Natural Language Queries**: 100 queries per hour per tenant
- **Incident Analysis**: 50 analyses per hour per tenant
- **Anomaly Detection**: 20 detections per hour per tenant
- **Knowledge Base Searches**: 200 searches per hour per tenant

### Performance Characteristics
- **Query Response Time**: 95th percentile < 2 seconds
- **Analysis Completion**: Typically 2-10 minutes depending on complexity
- **Anomaly Detection**: Real-time processing, results in < 5 seconds
- **Concurrent Requests**: Up to 10 simultaneous requests per tenant

### Best Practices

1. **Natural Language Queries**:
   - Use specific, clear questions
   - Include relevant context for better accuracy
   - Provide feedback to improve model performance

2. **Incident Investigation**:
   - Include comprehensive incident context
   - Specify affected services and timeframes
   - Use business context for impact assessment

3. **Anomaly Detection**:
   - Set up appropriate baselines for your services
   - Use appropriate time ranges (avoid too short periods)
   - Filter by relevant services and categories

4. **Performance Optimization**:
   - Cache baseline models when possible
   - Use appropriate confidence thresholds
   - Batch related queries when feasible

### Data Privacy & Security
- All AI processing respects tenant data isolation
- Query data is not shared between tenants
- Model training uses anonymized, aggregated data only
- Personal information is automatically redacted from analysis

---

## SDK Examples

### Python SDK Example
```python
import requests

class LogforgeAI:
    def __init__(self, base_url, token, tenant_id):
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer {token}',
            'X-Customer-ID': tenant_id,
            'Content-Type': 'application/json'
        }
    
    def natural_language_query(self, question, context=None, max_results=50):
        url = f"{self.base_url}/v1/ai/query"
        payload = {
            "question": question,
            "context": context or {},
            "max_results": max_results
        }
        response = requests.post(url, json=payload, headers=self.headers)
        return response.json()
    
    def start_investigation(self, title, description, incident_data, context=None):
        url = f"{self.base_url}/v1/ai/investigate"
        payload = {
            "title": title,
            "description": description,
            "incident_data": incident_data,
            "context": context or {}
        }
        response = requests.post(url, json=payload, headers=self.headers)
        return response.json()

# Usage
ai = LogforgeAI("https://api.logforge.com", "your-token", "your-tenant-id")

# Natural language query
result = ai.natural_language_query(
    "Show me error spikes in the last hour",
    context={"services": ["payment-api"]}
)

# Start incident investigation
investigation = ai.start_investigation(
    title="Payment API Issues",
    description="Users reporting payment failures",
    incident_data={
        "service": "payment-api",
        "symptoms": ["high error rate", "timeouts"],
        "severity": "high"
    }
)
```

### JavaScript SDK Example
```javascript
class LogforgeAI {
    constructor(baseUrl, token, tenantId) {
        this.baseUrl = baseUrl;
        this.headers = {
            'Authorization': `Bearer ${token}`,
            'X-Customer-ID': tenantId,
            'Content-Type': 'application/json'
        };
    }

    async naturalLanguageQuery(question, context = {}, maxResults = 50) {
        const response = await fetch(`${this.baseUrl}/v1/ai/query`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                question,
                context,
                max_results: maxResults
            })
        });
        return response.json();
    }

    async detectAnomalies(timeRange = '1h', filters = {}) {
        const response = await fetch(`${this.baseUrl}/v1/ai/anomalies/detect`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                time_range: timeRange,
                ...filters
            })
        });
        return response.json();
    }
}

// Usage
const ai = new LogforgeAI('https://api.logforge.com', 'your-token', 'your-tenant-id');

// Detect anomalies
const anomalies = await ai.detectAnomalies('4h', {
    severity_filter: ['high', 'medium'],
    service_filter: ['payment-api']
});
```

---

## Support & Resources

- **API Support**: [support@logforge.com](mailto:support@logforge.com)
- **Documentation**: [docs.logforge.com](https://docs.logforge.com)
- **Status Page**: [status.logforge.com](https://status.logforge.com)
- **Community**: [community.logforge.com](https://community.logforge.com)

For technical issues, please include:
- Request ID from error responses
- Tenant ID and timestamp
- Complete request/response examples
- Expected vs actual behavior

---

*Last updated: 2024-09-26*
*API Version: v1*
*Documentation Version: 1.0*