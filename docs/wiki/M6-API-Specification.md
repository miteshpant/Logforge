# M6 AI Assistant & RCA - Complete API Specification

## Overview
The M6 AI Assistant provides 12 core endpoints delivering natural language processing, automated root cause analysis, predictive analytics, and intelligent investigation assistance.

---

## 1. Natural Language Query Interface

### `POST /v1/ai/query`
Convert natural language questions into optimized SQL queries and execute them.

**Request Body**:
```json
{
  "question": "Show me API errors for payment service in the last hour",
  "context": {
    "user_role": "devops_engineer",
    "preferred_format": "table",
    "include_suggestions": true
  },
  "max_results": 100
}
```

**Response**:
```json
{
  "query_id": "nlq_12345",
  "original_question": "Show me API errors for payment service in the last hour",
  "generated_sql": "SELECT ts, service, level, msg, trace_id FROM logs_normalized_mt WHERE service='payment-api' AND level='ERROR' AND ts > now() - interval 1 hour ORDER BY ts DESC LIMIT 100",
  "explanation": "Finding all ERROR level logs from the payment-api service in the last hour, sorted by timestamp",
  "results": {
    "logs": [...],
    "total_count": 23,
    "execution_time_ms": 245
  },
  "suggestions": [
    "Show me the error rate trend over the last 24 hours",
    "Which specific error messages are most common?",
    "Are there any related alerts for this service?"
  ],
  "confidence_score": 0.95
}
```

### `GET /v1/ai/query/suggestions`
Get intelligent query suggestions based on current data patterns and user context.

**Query Parameters**:
- `user_role`: devops_engineer, security_analyst, business_user
- `context`: current_incident, general_exploration, compliance_review
- `time_range`: 1h, 24h, 7d, 30d

**Response**:
```json
{
  "suggestions": [
    {
      "category": "performance",
      "question": "Which services have the highest error rates today?",
      "description": "Identify services that may need attention",
      "complexity": "beginner"
    },
    {
      "category": "security", 
      "question": "Are there any unusual login patterns this week?",
      "description": "Security anomaly detection",
      "complexity": "intermediate"
    }
  ],
  "trending_queries": [
    "API response time trends",
    "Security events by severity",
    "Database connection issues"
  ]
}
```

---

## 2. Root Cause Analysis Engine

### `POST /v1/ai/analyze-incident`
Perform automated root cause analysis for incidents or operational issues.

**Request Body**:
```json
{
  "incident": {
    "id": "INC-2024-001",
    "title": "Payment API High Error Rate",
    "description": "Payment service error rate spiked to 15% at 14:30 UTC",
    "start_time": "2024-01-15T14:30:00Z",
    "end_time": "2024-01-15T15:30:00Z",
    "affected_services": ["payment-api", "user-service"],
    "severity": "high"
  },
  "context": {
    "include_historical": true,
    "analysis_depth": "comprehensive",
    "business_impact": true
  }
}
```

**Response**:
```json
{
  "analysis_id": "rca_67890",
  "incident_id": "INC-2024-001",
  "root_cause_analysis": {
    "primary_cause": {
      "type": "database_connection_exhaustion",
      "confidence": 0.87,
      "description": "Database connection pool exhaustion caused by unoptimized queries",
      "evidence": [
        {
          "timestamp": "2024-01-15T14:28:00Z",
          "event": "Database connection pool utilization reached 95%",
          "service": "payment-db",
          "impact": "New connection requests began timing out"
        }
      ]
    },
    "contributing_factors": [
      {
        "type": "traffic_spike",
        "confidence": 0.72,
        "description": "20% increase in payment requests during lunch hour",
        "correlation": "Traffic spike occurred 2 minutes before error rate increase"
      }
    ],
    "timeline": [
      {
        "timestamp": "2024-01-15T14:28:00Z",
        "event": "Database connection pool near capacity",
        "impact": "Warning threshold reached"
      },
      {
        "timestamp": "2024-01-15T14:30:00Z", 
        "event": "Connection pool exhausted",
        "impact": "Payment API errors begin"
      },
      {
        "timestamp": "2024-01-15T14:45:00Z",
        "event": "Error rate peaks at 15%",
        "impact": "Customer payment failures reported"
      }
    ]
  },
  "business_impact": {
    "customers_affected": 1247,
    "estimated_revenue_impact": "$12,400",
    "sla_violations": ["payment_sla_99_5"],
    "reputation_risk": "medium"
  },
  "recommendations": [
    {
      "priority": "immediate",
      "action": "Increase database connection pool size from 50 to 100",
      "expected_resolution_time": "5 minutes",
      "confidence": 0.91
    },
    {
      "priority": "short_term",
      "action": "Optimize slow payment validation queries identified in analysis",
      "expected_resolution_time": "2-4 hours",
      "confidence": 0.78
    }
  ],
  "similar_incidents": [
    {
      "incident_id": "INC-2023-156",
      "similarity_score": 0.83,
      "resolution": "Database connection pool increased, resolved in 8 minutes"
    }
  ]
}
```

### `GET /v1/ai/incidents/{incident_id}/analysis`
Retrieve existing RCA analysis for a specific incident.

### `POST /v1/ai/analyze-symptoms`
Analyze current symptoms without a formal incident to identify potential issues.

**Request Body**:
```json
{
  "symptoms": [
    "API response times increased by 200ms",
    "Error rate climbing slowly over 2 hours", 
    "Customer complaints about checkout failures"
  ],
  "time_range": {
    "start": "2024-01-15T12:00:00Z",
    "end": "2024-01-15T16:00:00Z"
  },
  "services": ["payment-api", "checkout-service", "user-service"]
}
```

---

## 3. Anomaly Detection & Prediction

### `GET /v1/ai/anomalies`
List detected anomalies across services, infrastructure, and security events.

**Query Parameters**:
- `time_range`: Time window to analyze
- `severity`: low, medium, high, critical
- `category`: performance, security, business, infrastructure
- `services`: Comma-separated list of services to analyze

**Response**:
```json
{
  "anomalies": [
    {
      "anomaly_id": "anom_001",
      "detected_at": "2024-01-15T14:25:00Z",
      "category": "performance",
      "severity": "high", 
      "title": "Payment API Response Time Anomaly",
      "description": "Response time increased by 300% compared to baseline",
      "confidence": 0.89,
      "baseline_value": 150.5,
      "current_value": 612.3,
      "deviation_score": 4.2,
      "affected_services": ["payment-api"],
      "potential_impact": "Customer checkout failures, revenue loss",
      "recommended_actions": [
        "Check database performance metrics",
        "Review recent deployment changes",
        "Validate infrastructure scaling"
      ]
    }
  ],
  "summary": {
    "total_anomalies": 7,
    "by_severity": {"critical": 1, "high": 2, "medium": 3, "low": 1},
    "by_category": {"performance": 4, "security": 2, "business": 1}
  }
}
```

### `POST /v1/ai/predict`
Generate predictions for potential future issues based on current trends.

**Request Body**:
```json
{
  "prediction_type": "failure_forecast",
  "time_horizon": "24h",
  "services": ["payment-api", "user-service"],
  "confidence_threshold": 0.7
}
```

**Response**:
```json
{
  "predictions": [
    {
      "prediction_id": "pred_001",
      "type": "resource_exhaustion",
      "service": "payment-api",
      "predicted_time": "2024-01-16T08:30:00Z",
      "confidence": 0.78,
      "description": "Database connection pool likely to exhaust during morning traffic peak",
      "indicators": [
        "Connection pool utilization trending upward",
        "Traffic growth pattern matches historical failure scenarios",
        "No recent capacity scaling detected"
      ],
      "preventive_actions": [
        "Scale database connection pool before 08:00 UTC",
        "Prepare additional database read replicas",
        "Enable connection pool monitoring alerts"
      ],
      "business_impact": {
        "risk_level": "high",
        "estimated_customer_impact": 2500,
        "estimated_revenue_risk": "$25,000"
      }
    }
  ]
}
```

---

## 4. Investigation Assistant

### `POST /v1/ai/investigate/start`
Begin a new guided investigation session.

**Request Body**:
```json
{
  "investigation": {
    "title": "Payment Service Degradation Investigation", 
    "initial_symptoms": [
      "Payment API error rate at 8%",
      "Customer reports of failed transactions",
      "Database connection timeouts in logs"
    ],
    "priority": "high",
    "assigned_to": ["alice@company.com", "bob@company.com"]
  }
}
```

**Response**:
```json
{
  "investigation_id": "inv_123",
  "status": "active",
  "next_steps": [
    {
      "step_id": 1,
      "action": "Analyze payment API error patterns",
      "query": "Show me payment API errors grouped by error type in the last 2 hours",
      "expected_outcome": "Identify most common error patterns"
    },
    {
      "step_id": 2,
      "action": "Check database performance metrics",
      "query": "Show database connection pool utilization and query performance",
      "expected_outcome": "Validate database health hypothesis"
    }
  ],
  "hypothesis": [
    {
      "description": "Database connection pool exhaustion",
      "confidence": 0.75,
      "supporting_evidence": ["Connection timeout errors", "High pool utilization"]
    }
  ]
}
```

### `POST /v1/ai/investigate/{investigation_id}/evidence`
Add evidence to an ongoing investigation.

### `GET /v1/ai/investigate/{investigation_id}/recommendations`
Get AI-powered next steps for investigation.

---

## 5. Knowledge Management

### `POST /v1/ai/knowledge/solutions`
Add successful solution to knowledge base.

**Request Body**:
```json
{
  "incident_type": "database_connection_exhaustion",
  "symptoms": ["High error rates", "Connection timeouts", "Pool utilization >95%"],
  "solution": {
    "title": "Increase Database Connection Pool Size",
    "steps": [
      "Identify current pool configuration",
      "Calculate required pool size based on traffic",
      "Update configuration with rolling restart",
      "Validate error rate improvement"
    ],
    "resolution_time": "5-10 minutes",
    "effectiveness_score": 0.95
  },
  "tags": ["database", "performance", "quick-fix"],
  "related_services": ["payment-api", "user-service"]
}
```

### `GET /v1/ai/knowledge/search`
Search knowledge base for relevant solutions and runbooks.

**Query Parameters**:
- `symptoms`: Description of current symptoms
- `services`: Affected services
- `category`: performance, security, infrastructure

---

## 6. Business Context & Impact Analysis

### `POST /v1/ai/business-impact`
Calculate business impact of technical issues.

**Request Body**:
```json
{
  "incident": {
    "affected_services": ["payment-api"],
    "error_rate": 0.15,
    "duration_minutes": 45,
    "customer_segments": ["premium", "enterprise"]
  },
  "business_context": {
    "revenue_per_transaction": 25.50,
    "average_transactions_per_minute": 150,
    "customer_sla_requirements": {
      "payment_sla_99_5": {"threshold": 0.005, "penalty_per_violation": 1000}
    }
  }
}
```

**Response**:
```json
{
  "impact_analysis": {
    "customers_affected": 1247,
    "transactions_lost": 342,
    "revenue_impact": {
      "direct_loss": "$8,721",
      "sla_penalties": "$3,000", 
      "estimated_churn_cost": "$15,000"
    },
    "reputation_impact": {
      "support_tickets_generated": 89,
      "social_media_mentions": 12,
      "estimated_nps_impact": -2.3
    },
    "competitive_risk": "medium"
  }
}
```

---

## 7. Learning & Continuous Improvement

### `POST /v1/ai/learn/incident`
Submit incident resolution data for ML model training.

### `GET /v1/ai/insights/operational`
Get operational insights and improvement recommendations.

**Response**:
```json
{
  "insights": [
    {
      "type": "recurring_pattern",
      "title": "Weekly Database Connection Issues",
      "description": "Database connection pool exhaustion occurs every Monday at 09:00 UTC",
      "frequency": "weekly",
      "impact": "3-5 minute service degradation affecting 500-1000 customers",
      "recommended_fix": "Implement predictive scaling for Monday morning traffic",
      "estimated_savings": "$5,000/month in prevented downtime"
    }
  ],
  "team_performance": {
    "average_investigation_time": "12 minutes",
    "improvement_trend": "+15% faster vs last month",
    "knowledge_base_usage": "78% of investigations reference existing solutions"
  }
}
```

---

## 8. Integration & Workflow APIs

### `POST /v1/ai/integrations/slack`
Handle Slack integration for conversational AI assistance.

**Request Body**:
```json
{
  "slack_event": {
    "user": "alice@company.com",
    "channel": "#incidents", 
    "message": "What caused the payment service issues this morning?",
    "thread_ts": "1642261200.123456"
  }
}
```

### `GET /v1/ai/health`
AI engine health check and model status.

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T16:30:00Z",
  "models": {
    "nlq_processor": {"status": "active", "last_training": "2024-01-10T12:00:00Z"},
    "anomaly_detector": {"status": "active", "accuracy": 0.89},
    "rca_engine": {"status": "active", "correlation_accuracy": 0.82},
    "prediction_engine": {"status": "active", "forecast_accuracy": 0.71}
  },
  "knowledge_base": {
    "total_solutions": 234,
    "incident_patterns": 89,
    "confidence_score": 0.85
  }
}
```

---

## Complete M6 API Endpoint Summary

### **Natural Language Processing (3 endpoints)**
```yaml
POST /v1/ai/query                     # Convert natural language to SQL queries
GET  /v1/ai/query/suggestions         # Get intelligent query suggestions  
GET  /v1/ai/query/{query_id}/history  # View query history and refinements
```

### **Root Cause Analysis (4 endpoints)**  
```yaml
POST /v1/ai/analyze-incident          # Full incident RCA analysis
POST /v1/ai/analyze-symptoms          # Analyze symptoms without formal incident
GET  /v1/ai/incidents/{id}/analysis   # Retrieve existing RCA analysis
POST /v1/ai/correlate                 # Find correlations between events/metrics
```

### **Investigation Assistant (3 endpoints)**
```yaml
POST /v1/ai/investigate/start         # Start guided investigation session
POST /v1/ai/investigate/{id}/evidence # Add evidence to investigation
GET  /v1/ai/investigate/{id}/recommendations # Get next investigation steps
```

### **Anomaly Detection & Prediction (3 endpoints)**
```yaml
GET  /v1/ai/anomalies                 # List current anomalies across systems
POST /v1/ai/predict                   # Generate failure predictions and forecasts
GET  /v1/ai/baselines                 # View learned baselines and patterns
```

### **Knowledge Management (3 endpoints)**
```yaml
POST /v1/ai/knowledge/solutions       # Add solution to knowledge base
GET  /v1/ai/knowledge/search          # Search for relevant solutions/runbooks
GET  /v1/ai/insights/operational      # Get operational insights and trends
```

### **Business Context (2 endpoints)**
```yaml
POST /v1/ai/business-impact           # Calculate business impact of incidents
GET  /v1/ai/metrics/business          # Business-context performance metrics
```

### **System & Integration (3 endpoints)**
```yaml
GET  /v1/ai/health                    # AI engine health and model status
POST /v1/ai/integrations/slack        # Slack conversational AI integration
POST /v1/ai/learn/incident            # Submit incident data for model training
```

### **Total M6 Endpoints: 21 APIs**

---

## Authentication & Authorization

### **Headers Required**
```yaml
X-Customer-ID: customer_identifier    # Multi-tenant isolation
Authorization: Bearer <token>         # OIDC or API key authentication  
Content-Type: application/json        # JSON request/response format
```

### **Role-Based Access**
```yaml
AI Query Access:
├── business_user: Natural language queries only
├── analyst: NLQ + basic RCA + anomaly viewing
├── engineer: Full investigation + knowledge management
└── admin: All capabilities + model training + configuration

Rate Limiting:
├── Natural Language Queries: 100/hour per user
├── RCA Analysis: 20/hour per customer
├── Predictions: 50/hour per customer
└── Knowledge Search: 500/hour per user
```

---

## Error Handling & Response Codes

### **Standard HTTP Response Codes**
```yaml
200: Success with data
201: Successfully created (investigations, knowledge entries)
400: Bad request (invalid natural language query, malformed request)
401: Unauthorized (missing/invalid authentication)
403: Forbidden (insufficient role permissions)
404: Not found (incident, investigation, knowledge entry not found)
422: Unprocessable entity (AI couldn't parse query or analyze incident)
429: Rate limit exceeded
500: Internal server error
503: AI engine temporarily unavailable
```

### **AI-Specific Error Responses**
```json
{
  "error": {
    "code": "NLQ_PARSE_FAILED", 
    "message": "Could not understand natural language query",
    "details": "Query too ambiguous. Try specifying time range and service name.",
    "suggestions": [
      "Show me errors from payment service in the last hour",
      "What services had issues today?"
    ]
  }
}
```

---

## Performance Requirements

### **Response Time Targets**
```yaml
Natural Language Query: <500ms translation + query execution time
RCA Analysis: <30 seconds for comprehensive incident analysis
Anomaly Detection: <5 seconds for current anomaly list
Prediction Generation: <10 seconds for 24h forecasts
Knowledge Search: <200ms for solution lookup
```

### **Accuracy Targets**
```yaml
Natural Language Query Accuracy: >90% correct SQL generation
RCA Root Cause Identification: >80% correct primary cause
Anomaly Detection False Positive Rate: <10%
Failure Prediction Accuracy: >70% for 4-hour lead time
Business Impact Calculation: ±15% accuracy for revenue estimates
```

### **Scalability Requirements**
```yaml
Concurrent Users: 100+ simultaneous NLQ sessions
Query Throughput: 1000+ AI-assisted queries per hour
Model Training: Real-time learning from incident resolutions
Knowledge Base: 10,000+ solutions with sub-second search
```

This comprehensive API specification provides the foundation for building M6's AI capabilities while maintaining consistency with the existing platform architecture and multi-tenant requirements.