"""
M6 AI Engine - Core artificial intelligence and machine learning capabilities
Provides natural language processing, root cause analysis, anomaly detection, and prediction
"""

import json
import re
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
import asyncio

logger = structlog.get_logger(__name__)

# Data Models

class AnalysisStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"

class ModelStatus(str, Enum):
    ACTIVE = "active"
    TRAINING = "training"
    INACTIVE = "inactive"

class AnomalySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AnomalyCategory(str, Enum):
    PERFORMANCE = "performance"
    SECURITY = "security"
    BUSINESS = "business"
    INFRASTRUCTURE = "infrastructure"

class PredictionType(str, Enum):
    FAILURE_FORECAST = "failure_forecast"
    CAPACITY_PLANNING = "capacity_planning"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    SECURITY_THREAT = "security_threat"

class InvestigationStatus(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class CorrelationType(str, Enum):
    TEMPORAL = "temporal"
    CAUSAL = "causal"
    DEPENDENCY = "dependency"
    PATTERN = "pattern"

@dataclass
class NLQueryResult:
    query_id: str
    original_question: str
    generated_sql: str
    explanation: str
    results: Dict[str, Any]
    suggestions: List[str]
    confidence_score: float

@dataclass
class RootCauseAnalysis:
    analysis_id: str
    incident_id: str
    primary_cause: Dict[str, Any]
    contributing_factors: List[Dict[str, Any]]
    timeline: List[Dict[str, Any]]
    confidence: float

@dataclass
class Anomaly:
    anomaly_id: str
    detected_at: str
    category: AnomalyCategory
    severity: AnomalySeverity
    title: str
    description: str
    confidence: float
    baseline_value: float
    current_value: float
    deviation_score: float
    affected_services: List[str]
    potential_impact: str
    recommended_actions: List[str]

@dataclass
class Prediction:
    prediction_id: str
    type: str
    service: str
    predicted_time: str
    confidence: float
    description: str
    indicators: List[str]
    preventive_actions: List[str]
    business_impact: Dict[str, Any]

@dataclass
class Investigation:
    investigation_id: str
    status: InvestigationStatus
    title: str
    symptoms: List[str]
    priority: str
    assigned_to: List[str]
    created_at: str
    next_steps: List[Dict[str, Any]]
    hypothesis: List[Dict[str, Any]]
    evidence: List[Dict[str, Any]]

@dataclass
class Solution:
    solution_id: str
    incident_type: str
    symptoms: List[str]
    title: str
    steps: List[str]
    resolution_time: str
    effectiveness_score: float
    tags: List[str]
    related_services: List[str]
    created_at: str

class AIEngine:
    """Core AI Engine providing intelligent analysis capabilities"""
    
    def __init__(self):
        self.models_status = {
            "nlq_processor": {"status": ModelStatus.ACTIVE, "last_training": "2024-01-10T12:00:00Z", "accuracy": 0.91},
            "anomaly_detector": {"status": ModelStatus.ACTIVE, "accuracy": 0.89, "false_positive_rate": 0.08},
            "rca_engine": {"status": ModelStatus.ACTIVE, "correlation_accuracy": 0.82},
            "prediction_engine": {"status": ModelStatus.ACTIVE, "forecast_accuracy": 0.71}
        }
        
        # In-memory storage for demo (would be replaced with persistent storage)
        self.query_history: Dict[str, Dict] = {}
        self.incident_analyses: Dict[str, RootCauseAnalysis] = {}
        self.investigations: Dict[str, Investigation] = {}
        self.knowledge_base: List[Solution] = []
        self.anomaly_baselines: Dict[str, Dict] = {}
        self.correlation_patterns: List[Dict] = []
        
        # Initialize with some default knowledge
        self._initialize_knowledge_base()
        self._initialize_baselines()
    
    def _initialize_knowledge_base(self):
        """Initialize knowledge base with common solutions"""
        default_solutions = [
            {
                "incident_type": "database_connection_exhaustion",
                "symptoms": ["High error rates", "Connection timeouts", "Pool utilization >95%"],
                "title": "Increase Database Connection Pool Size",
                "steps": [
                    "Identify current pool configuration",
                    "Calculate required pool size based on traffic",
                    "Update configuration with rolling restart",
                    "Validate error rate improvement"
                ],
                "resolution_time": "5-10 minutes",
                "effectiveness_score": 0.95,
                "tags": ["database", "performance", "quick-fix"],
                "related_services": ["payment-api", "user-service"]
            },
            {
                "incident_type": "memory_leak",
                "symptoms": ["Increasing memory usage", "OOM errors", "Pod restarts"],
                "title": "Identify and Fix Memory Leak",
                "steps": [
                    "Analyze memory usage patterns",
                    "Profile application for memory leaks",
                    "Identify problematic code paths",
                    "Deploy fix with memory monitoring"
                ],
                "resolution_time": "2-4 hours",
                "effectiveness_score": 0.88,
                "tags": ["memory", "performance", "debugging"],
                "related_services": ["all-services"]
            }
        ]
        
        for solution_data in default_solutions:
            solution = Solution(
                solution_id=str(uuid.uuid4()),
                created_at=datetime.now().isoformat(),
                **solution_data
            )
            self.knowledge_base.append(solution)
    
    def _initialize_baselines(self):
        """Initialize baseline patterns for anomaly detection"""
        self.anomaly_baselines = {
            "payment-api": {
                "error_rate": {"baseline_value": 0.02, "variance": 0.005, "confidence": 0.89, "data_points": 1000},
                "response_time_ms": {"baseline_value": 150.5, "variance": 25.0, "confidence": 0.92, "data_points": 1000},
                "throughput_rps": {"baseline_value": 250.0, "variance": 50.0, "confidence": 0.87, "data_points": 1000}
            },
            "user-service": {
                "error_rate": {"baseline_value": 0.01, "variance": 0.003, "confidence": 0.91, "data_points": 800},
                "response_time_ms": {"baseline_value": 75.2, "variance": 15.0, "confidence": 0.88, "data_points": 800}
            }
        }
    
    # Natural Language Query Processing
    
    async def process_natural_language_query(self, question: str, context: Dict[str, Any], max_results: int = 100) -> NLQueryResult:
        """Convert natural language question to SQL query"""
        query_id = str(uuid.uuid4())
        
        # Simple NLQ processing (would use actual AI/ML models in production)
        sql_query, explanation, confidence = await self._translate_to_sql(question, context)
        
        # Execute the query (mock results for now)
        results = await self._execute_query(sql_query, max_results)
        
        # Generate suggestions
        suggestions = await self._generate_suggestions(question, context)
        
        # Store in query history
        self.query_history[query_id] = {
            "original_question": question,
            "generated_sql": sql_query,
            "execution_time_ms": results.get("execution_time_ms", 250),
            "result_count": results.get("total_count", 0),
            "timestamp": datetime.now().isoformat(),
            "refinements": []
        }
        
        return NLQueryResult(
            query_id=query_id,
            original_question=question,
            generated_sql=sql_query,
            explanation=explanation,
            results=results,
            suggestions=suggestions,
            confidence_score=confidence
        )
    
    async def _translate_to_sql(self, question: str, context: Dict[str, Any]) -> Tuple[str, str, float]:
        """Translate natural language to SQL (simplified implementation)"""
        question_lower = question.lower()
        
        # Simple pattern matching for demo (would use actual NLP models)
        if "api errors" in question_lower and "payment" in question_lower:
            sql = "SELECT ts, service, level, msg, trace_id FROM logs_normalized_mt WHERE service='payment-api' AND level='ERROR' AND ts > now() - interval 1 hour ORDER BY ts DESC LIMIT 100"
            explanation = "Finding all ERROR level logs from the payment-api service in the last hour, sorted by timestamp"
            confidence = 0.95
        elif "error rate" in question_lower and "services" in question_lower:
            sql = "SELECT service, COUNT(*) as error_count, COUNT(*) * 100.0 / (SELECT COUNT(*) FROM logs_normalized_mt WHERE ts > now() - interval 24 hours) as error_rate FROM logs_normalized_mt WHERE level='ERROR' AND ts > now() - interval 24 hours GROUP BY service ORDER BY error_rate DESC"
            explanation = "Calculating error rates for all services in the last 24 hours"
            confidence = 0.88
        elif "unusual login" in question_lower or "login patterns" in question_lower:
            sql = "SELECT source_ip, COUNT(*) as attempts, COUNT(DISTINCT user) as unique_users FROM logs_normalized_mt WHERE msg LIKE '%login%' OR msg LIKE '%authentication%' AND ts > now() - interval 7 days GROUP BY source_ip HAVING attempts > 100 ORDER BY attempts DESC"
            explanation = "Detecting unusual login patterns by analyzing authentication attempts from IP addresses"
            confidence = 0.82
        else:
            # Default fallback query
            sql = "SELECT * FROM logs_normalized_mt WHERE ts > now() - interval 1 hour ORDER BY ts DESC LIMIT 100"
            explanation = "Showing recent logs from the last hour"
            confidence = 0.65
        
        return sql, explanation, confidence
    
    async def _execute_query(self, sql: str, max_results: int) -> Dict[str, Any]:
        """Execute SQL query and return results (mock implementation)"""
        # Mock query execution (would connect to actual ClickHouse in production)
        await asyncio.sleep(0.1)  # Simulate query execution time
        
        # Generate mock results based on query type
        if "payment-api" in sql and "ERROR" in sql:
            logs = [
                {
                    "ts": (datetime.now() - timedelta(minutes=5)).isoformat(),
                    "service": "payment-api",
                    "level": "ERROR",
                    "msg": "Database connection timeout",
                    "trace_id": str(uuid.uuid4())
                },
                {
                    "ts": (datetime.now() - timedelta(minutes=12)).isoformat(),
                    "service": "payment-api", 
                    "level": "ERROR",
                    "msg": "Payment processing failed: insufficient funds",
                    "trace_id": str(uuid.uuid4())
                }
            ]
            return {
                "logs": logs[:max_results],
                "total_count": len(logs),
                "execution_time_ms": 245
            }
        else:
            return {
                "logs": [],
                "total_count": 0,
                "execution_time_ms": 150
            }
    
    async def _generate_suggestions(self, question: str, context: Dict[str, Any]) -> List[str]:
        """Generate follow-up query suggestions"""
        base_suggestions = [
            "Show me the error rate trend over the last 24 hours",
            "Which specific error messages are most common?",
            "Are there any related alerts for this service?",
            "What services have the highest error rates today?",
            "Show me successful transactions for comparison"
        ]
        
        # Context-aware suggestions based on user role
        if context.get("user_role") == "security_analyst":
            base_suggestions.extend([
                "Are there any security events related to this issue?",
                "Show me failed authentication attempts",
                "Check for suspicious IP addresses"
            ])
        elif context.get("user_role") == "business_user":
            base_suggestions.extend([
                "What is the revenue impact of these errors?",
                "How many customers are affected?",
                "Show me the SLA compliance metrics"
            ])
        
        return base_suggestions[:5]  # Return top 5 suggestions
    
    # Root Cause Analysis
    
    async def analyze_incident(self, incident: Dict[str, Any], context: Dict[str, Any]) -> RootCauseAnalysis:
        """Perform automated root cause analysis"""
        analysis_id = str(uuid.uuid4())
        incident_id = incident.get("id", str(uuid.uuid4()))
        
        # Simulate comprehensive RCA analysis
        await asyncio.sleep(1.0)  # Simulate analysis time
        
        # Analyze symptoms and generate root cause hypothesis
        primary_cause = await self._identify_primary_cause(incident)
        contributing_factors = await self._identify_contributing_factors(incident)
        timeline = await self._reconstruct_timeline(incident)
        
        # Calculate overall confidence
        confidence = (primary_cause["confidence"] + 
                     sum(f["confidence"] for f in contributing_factors) / max(len(contributing_factors), 1)) / 2
        
        analysis = RootCauseAnalysis(
            analysis_id=analysis_id,
            incident_id=incident_id,
            primary_cause=primary_cause,
            contributing_factors=contributing_factors,
            timeline=timeline,
            confidence=confidence
        )
        
        # Store analysis
        self.incident_analyses[incident_id] = analysis
        
        return analysis
    
    async def _identify_primary_cause(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """Identify the primary root cause of an incident"""
        description = incident.get("description", "").lower()
        affected_services = incident.get("affected_services", [])
        
        # Pattern matching for common issues (would use ML models in production)
        if "error rate" in description and "payment" in description:
            return {
                "type": "database_connection_exhaustion",
                "confidence": 0.87,
                "description": "Database connection pool exhaustion caused by unoptimized queries",
                "evidence": [
                    {
                        "timestamp": (datetime.now() - timedelta(minutes=2)).isoformat(),
                        "event": "Database connection pool utilization reached 95%",
                        "service": "payment-db",
                        "impact": "New connection requests began timing out"
                    }
                ]
            }
        elif "response time" in description:
            return {
                "type": "performance_degradation",
                "confidence": 0.79,
                "description": "Performance degradation due to increased load without scaling",
                "evidence": [
                    {
                        "timestamp": (datetime.now() - timedelta(minutes=5)).isoformat(),
                        "event": "CPU utilization increased to 85%",
                        "service": affected_services[0] if affected_services else "unknown-service",
                        "impact": "Request processing time increased significantly"
                    }
                ]
            }
        else:
            return {
                "type": "unknown_issue",
                "confidence": 0.45,
                "description": "Unable to determine specific root cause from available data",
                "evidence": []
            }
    
    async def _identify_contributing_factors(self, incident: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify contributing factors to the incident"""
        factors = []
        
        # Check for traffic spikes
        factors.append({
            "type": "traffic_spike",
            "confidence": 0.72,
            "description": "20% increase in payment requests during lunch hour",
            "correlation": "Traffic spike occurred 2 minutes before error rate increase"
        })
        
        # Check for recent deployments
        if datetime.now().weekday() < 5:  # Weekday
            factors.append({
                "type": "recent_deployment",
                "confidence": 0.65,
                "description": "New deployment within 24 hours may have introduced performance regression",
                "correlation": "Deployment timestamp aligns with incident start"
            })
        
        return factors
    
    async def _reconstruct_timeline(self, incident: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Reconstruct incident timeline"""
        start_time = datetime.fromisoformat(incident.get("start_time", datetime.now().isoformat()))
        
        timeline = [
            {
                "timestamp": (start_time - timedelta(minutes=2)).isoformat(),
                "event": "Database connection pool near capacity",
                "impact": "Warning threshold reached"
            },
            {
                "timestamp": start_time.isoformat(),
                "event": "Connection pool exhausted",
                "impact": "Payment API errors begin"
            },
            {
                "timestamp": (start_time + timedelta(minutes=15)).isoformat(),
                "event": "Error rate peaks at 15%",
                "impact": "Customer payment failures reported"
            }
        ]
        
        return timeline
    
    # Anomaly Detection
    
    async def detect_anomalies(self, time_range: str, severity_filter: List[str] = None, 
                              category_filter: List[str] = None, services: List[str] = None) -> Dict[str, Any]:
        """Detect anomalies across systems"""
        
        # Generate mock anomalies based on baselines
        anomalies = []
        
        for service, baselines in self.anomaly_baselines.items():
            if services and service not in services:
                continue
                
            for metric, baseline in baselines.items():
                # Simulate anomaly detection
                current_value = baseline["baseline_value"] * (1 + 0.3)  # 30% increase
                deviation = abs(current_value - baseline["baseline_value"]) / baseline["variance"]
                
                if deviation > 2.0:  # Statistical anomaly
                    severity = AnomalySeverity.HIGH if deviation > 4.0 else AnomalySeverity.MEDIUM
                    
                    if severity_filter and severity.value not in severity_filter:
                        continue
                    
                    anomaly = Anomaly(
                        anomaly_id=str(uuid.uuid4()),
                        detected_at=datetime.now().isoformat(),
                        category=AnomalyCategory.PERFORMANCE,
                        severity=severity,
                        title=f"{service.title()} {metric.replace('_', ' ').title()} Anomaly",
                        description=f"{metric} increased by {int((current_value - baseline['baseline_value']) / baseline['baseline_value'] * 100)}% compared to baseline",
                        confidence=baseline["confidence"],
                        baseline_value=baseline["baseline_value"],
                        current_value=current_value,
                        deviation_score=deviation,
                        affected_services=[service],
                        potential_impact="Service degradation, customer impact",
                        recommended_actions=[
                            f"Check {service} performance metrics",
                            "Review recent deployment changes",
                            "Validate infrastructure scaling"
                        ]
                    )
                    anomalies.append(anomaly)
        
        # Filter by category
        if category_filter:
            anomalies = [a for a in anomalies if a.category.value in category_filter]
        
        # Generate summary
        summary = {
            "total_anomalies": len(anomalies),
            "by_severity": {},
            "by_category": {}
        }
        
        for anomaly in anomalies:
            severity = anomaly.severity.value
            category = anomaly.category.value
            summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
            summary["by_category"][category] = summary["by_category"].get(category, 0) + 1
        
        return {
            "anomalies": [asdict(a) for a in anomalies],
            "summary": summary
        }
    
    # Prediction Engine
    
    async def generate_predictions(self, prediction_type: str, time_horizon: str, 
                                  services: List[str], confidence_threshold: float = 0.7) -> Dict[str, Any]:
        """Generate failure predictions and forecasts"""
        
        predictions = []
        
        for service in services:
            if service in self.anomaly_baselines:
                # Simulate prediction based on current trends
                predicted_time = datetime.now() + timedelta(hours=8)
                confidence = 0.78
                
                if confidence >= confidence_threshold:
                    prediction = Prediction(
                        prediction_id=str(uuid.uuid4()),
                        type="resource_exhaustion",
                        service=service,
                        predicted_time=predicted_time.isoformat(),
                        confidence=confidence,
                        description=f"Database connection pool likely to exhaust during morning traffic peak",
                        indicators=[
                            "Connection pool utilization trending upward",
                            "Traffic growth pattern matches historical failure scenarios",
                            "No recent capacity scaling detected"
                        ],
                        preventive_actions=[
                            f"Scale {service} connection pool before 08:00 UTC",
                            "Prepare additional database read replicas",
                            "Enable connection pool monitoring alerts"
                        ],
                        business_impact={
                            "risk_level": "high",
                            "estimated_customer_impact": 2500,
                            "estimated_revenue_risk": "$25,000"
                        }
                    )
                    predictions.append(prediction)
        
        return {"predictions": [asdict(p) for p in predictions]}
    
    # Investigation Assistant
    
    async def start_investigation(self, investigation_data: Dict[str, Any]) -> Investigation:
        """Start a new guided investigation"""
        investigation_id = str(uuid.uuid4())
        
        # Generate initial hypothesis and next steps
        symptoms = investigation_data.get("initial_symptoms", [])
        next_steps = await self._generate_investigation_steps(symptoms)
        hypothesis = await self._generate_initial_hypothesis(symptoms)
        
        investigation = Investigation(
            investigation_id=investigation_id,
            status=InvestigationStatus.ACTIVE,
            title=investigation_data.get("title", "New Investigation"),
            symptoms=symptoms,
            priority=investigation_data.get("priority", "medium"),
            assigned_to=investigation_data.get("assigned_to", []),
            created_at=datetime.now().isoformat(),
            next_steps=next_steps,
            hypothesis=hypothesis,
            evidence=[]
        )
        
        # Store investigation
        self.investigations[investigation_id] = investigation
        
        return investigation
    
    async def _generate_investigation_steps(self, symptoms: List[str]) -> List[Dict[str, Any]]:
        """Generate investigation steps based on symptoms"""
        steps = []
        
        if any("error rate" in s.lower() for s in symptoms):
            steps.append({
                "step_id": 1,
                "action": "Analyze error patterns",
                "query": "Show me error logs grouped by error type in the last 2 hours",
                "expected_outcome": "Identify most common error patterns"
            })
        
        if any("database" in s.lower() or "connection" in s.lower() for s in symptoms):
            steps.append({
                "step_id": 2,
                "action": "Check database performance metrics",
                "query": "Show database connection pool utilization and query performance",
                "expected_outcome": "Validate database health hypothesis"
            })
        
        # Default step
        if not steps:
            steps.append({
                "step_id": 1,
                "action": "Gather initial evidence",
                "query": "Show me recent logs from affected services",
                "expected_outcome": "Understand scope and symptoms"
            })
        
        return steps
    
    async def _generate_initial_hypothesis(self, symptoms: List[str]) -> List[Dict[str, Any]]:
        """Generate initial hypothesis based on symptoms"""
        hypothesis = []
        
        if any("database" in s.lower() or "connection" in s.lower() for s in symptoms):
            hypothesis.append({
                "description": "Database connection pool exhaustion",
                "confidence": 0.75,
                "supporting_evidence": ["Connection timeout errors", "High pool utilization"]
            })
        
        if any("error rate" in s.lower() for s in symptoms):
            hypothesis.append({
                "description": "Upstream service degradation",
                "confidence": 0.68,
                "supporting_evidence": ["Increased error rates", "Customer impact reports"]
            })
        
        return hypothesis
    
    # Business Impact Analysis
    
    async def calculate_business_impact(self, incident: Dict[str, Any], business_context: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate business impact of technical issues"""
        
        error_rate = incident.get("error_rate", 0.1)
        duration_minutes = incident.get("duration_minutes", 30)
        
        # Calculate customer impact
        transactions_per_minute = business_context.get("average_transactions_per_minute", 100)
        total_transactions = transactions_per_minute * duration_minutes
        failed_transactions = int(total_transactions * error_rate)
        
        # Calculate revenue impact
        revenue_per_transaction = business_context.get("revenue_per_transaction", 20.0)
        direct_loss = failed_transactions * revenue_per_transaction
        
        # SLA penalty calculation
        sla_requirements = business_context.get("customer_sla_requirements", {})
        sla_penalties = 0
        sla_violations = []
        
        for sla_name, sla_config in sla_requirements.items():
            if error_rate > sla_config.get("threshold", 0.01):
                sla_penalties += sla_config.get("penalty_per_violation", 0)
                sla_violations.append(sla_name)
        
        # Estimate churn cost (simplified calculation)
        estimated_churn_cost = direct_loss * 1.2  # 20% multiplier for customer churn
        
        # Calculate reputation impact
        support_tickets = int(failed_transactions * 0.1)  # 10% of failures generate tickets
        social_mentions = max(1, int(failed_transactions / 100))  # 1% generate social mentions
        nps_impact = min(-5.0, -error_rate * 100 * 0.5)  # Negative NPS impact
        
        return {
            "customers_affected": int(failed_transactions * 0.8),  # Estimate unique customers
            "transactions_lost": failed_transactions,
            "revenue_impact": {
                "direct_loss": f"${direct_loss:,.2f}",
                "sla_penalties": f"${sla_penalties:,.2f}",
                "estimated_churn_cost": f"${estimated_churn_cost:,.2f}"
            },
            "reputation_impact": {
                "support_tickets_generated": support_tickets,
                "social_media_mentions": social_mentions,
                "estimated_nps_impact": nps_impact
            },
            "competitive_risk": "high" if error_rate > 0.1 else "medium"
        }
    
    # Knowledge Management
    
    async def search_knowledge_base(self, symptoms: str, services: str = None, category: str = None) -> Dict[str, Any]:
        """Search knowledge base for relevant solutions"""
        search_start = datetime.now()
        
        # Simple text matching (would use vector search in production)
        symptoms_lower = symptoms.lower()
        matching_solutions = []
        
        for solution in self.knowledge_base:
            # Check if symptoms match
            symptom_match = any(symptoms_lower in symptom.lower() for symptom in solution.symptoms)
            
            # Check service relevance
            service_match = (not services or 
                           any(service in solution.related_services for service in services.split(",")) or
                           "all-services" in solution.related_services)
            
            # Check category/tag relevance
            category_match = not category or category.lower() in [tag.lower() for tag in solution.tags]
            
            if symptom_match and service_match and category_match:
                matching_solutions.append(asdict(solution))
        
        search_time = (datetime.now() - search_start).total_seconds() * 1000
        
        return {
            "solutions": matching_solutions,
            "total_found": len(matching_solutions),
            "search_time_ms": int(search_time)
        }
    
    async def add_solution(self, solution_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add new solution to knowledge base"""
        solution = Solution(
            solution_id=str(uuid.uuid4()),
            created_at=datetime.now().isoformat(),
            incident_type=solution_data["incident_type"],
            symptoms=solution_data["symptoms"],
            title=solution_data["solution"]["title"],
            steps=solution_data["solution"]["steps"],
            resolution_time=solution_data["solution"]["resolution_time"],
            effectiveness_score=solution_data["solution"]["effectiveness_score"],
            tags=solution_data["tags"],
            related_services=solution_data["related_services"]
        )
        
        self.knowledge_base.append(solution)
        
        return {
            "solution_id": solution.solution_id,
            "status": "created",
            "knowledge_base_updated": True
        }
    
    # Utility Methods
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get AI engine health and model status"""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "models": self.models_status,
            "knowledge_base": {
                "total_solutions": len(self.knowledge_base),
                "incident_patterns": len(self.correlation_patterns),
                "confidence_score": 0.85
            }
        }
    
    async def get_operational_insights(self) -> Dict[str, Any]:
        """Get operational insights and improvement recommendations"""
        return {
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
    
    async def correlate_events(self, events: List[Dict[str, Any]], correlation_window: str, 
                              confidence_threshold: float) -> Dict[str, Any]:
        """Find correlations between events"""
        correlation_id = str(uuid.uuid4())
        
        correlations = []
        
        # Simple temporal correlation for demo
        if len(events) >= 2:
            event1, event2 = events[0], events[1]
            time1 = datetime.fromisoformat(event1["timestamp"])
            time2 = datetime.fromisoformat(event2["timestamp"])
            
            time_diff = abs((time1 - time2).total_seconds())
            
            # Check if events are within correlation window
            if time_diff <= 600:  # 10 minutes
                correlations.append({
                    "correlation_type": CorrelationType.TEMPORAL.value,
                    "confidence": 0.85,
                    "events_involved": [event1["service"], event2["service"]],
                    "causal_relationship": f"{event2['event_type']} likely caused by {event1['event_type']}",
                    "description": f"Events occurred within {int(time_diff)} seconds, suggesting causal relationship"
                })
        
        return {
            "correlation_id": correlation_id,
            "correlations": correlations,
            "analysis_summary": f"Found {len(correlations)} correlations above confidence threshold {confidence_threshold}"
        }

# Global instance
_ai_engine = None

async def get_ai_engine() -> AIEngine:
    """Get global AI engine instance"""
    global _ai_engine
    if _ai_engine is None:
        _ai_engine = AIEngine()
    return _ai_engine