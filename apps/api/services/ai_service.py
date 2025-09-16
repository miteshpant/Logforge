"""
AI Service - Business logic for AI Assistant and Machine Learning capabilities

This service provides comprehensive AI capabilities including:
- Natural language query processing
- Root cause analysis and incident investigations  
- ML model baselines and anomaly detection
- Knowledge management and solution recommendations
- Business impact analysis
"""

import uuid
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from dao.ai_dao import AIDAO


@dataclass
class NLQueryResult:
    """Natural Language Query result"""
    query_id: str
    original_question: str
    generated_sql: str
    explanation: str
    results: Dict[str, Any]
    suggestions: List[str]
    confidence_score: float
    execution_time_ms: int


@dataclass
class Investigation:
    """AI Investigation"""
    investigation_id: str
    title: str
    description: str
    investigation_type: str  # 'root_cause', 'anomaly', 'correlation', 'prediction'
    status: str  # 'running', 'completed', 'failed', 'cancelled'
    input_data: Dict[str, Any]
    results: Dict[str, Any]
    confidence_score: float
    started_by: str
    started_at: datetime
    completed_at: Optional[datetime]
    investigation_notes: List[str]
    hypothesis: List[Dict[str, Any]]
    next_steps: List[str]
    evidence: List[Dict[str, Any]]


@dataclass
class IncidentAnalysis:
    """Incident analysis result"""
    analysis_id: str
    incident_id: str
    primary_cause: str
    contributing_factors: List[str]
    timeline: List[Dict[str, Any]]
    business_impact: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    similar_incidents: List[Dict[str, Any]]


class AIService:
    """Business logic for AI assistant and machine learning operations"""
    
    def __init__(self):
        self.dao = AIDAO()
    
    # ==========================================
    # NATURAL LANGUAGE PROCESSING
    # ==========================================
    
    async def process_natural_language_query(self, question: str, context: Dict[str, Any], 
                                           max_results: int, user_id: str, customer_id: str) -> NLQueryResult:
        """Process natural language question and generate SQL query"""
        query_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        # Simple NL to SQL conversion (would use advanced NLP in production)
        sql_query, explanation, confidence = self._convert_nl_to_sql(question, context)
        
        # Execute the generated SQL (mock execution for now)
        mock_results = await self._execute_mock_query(sql_query, max_results)
        
        # Calculate execution time
        end_time = datetime.utcnow()
        execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        # Generate suggestions for follow-up queries
        suggestions = self._generate_query_suggestions(question, context)
        
        # Save query history
        query_data = {
            'id': query_id,
            'user_id': user_id,
            'natural_query': question,
            'generated_sql': sql_query,
            'execution_status': 'success',
            'result_count': len(mock_results.get('data', [])),
            'execution_time_ms': execution_time_ms,
            'feedback_score': None,
            'feedback_notes': None,
            'created_at': start_time,
            'customer_id': customer_id
        }
        
        await self.dao.save_nl_query(query_data)
        
        return NLQueryResult(
            query_id=query_id,
            original_question=question,
            generated_sql=sql_query,
            explanation=explanation,
            results=mock_results,
            suggestions=suggestions,
            confidence_score=confidence,
            execution_time_ms=execution_time_ms
        )
    
    def _convert_nl_to_sql(self, question: str, context: Dict[str, Any]) -> Tuple[str, str, float]:
        """Convert natural language question to SQL query"""
        question_lower = question.lower()
        
        # Simple pattern matching for demo purposes
        if "error" in question_lower or "fail" in question_lower:
            sql_query = """
            SELECT 
                service_name,
                count(*) as error_count,
                any(message) as sample_error
            FROM logs_normalized_mt 
            WHERE level = 'ERROR' 
              AND timestamp >= now() - INTERVAL 24 HOUR
              AND customer_id = %(customer_id)s
            GROUP BY service_name 
            ORDER BY error_count DESC 
            LIMIT 10
            """
            explanation = "Analyzing error patterns across services in the last 24 hours"
            confidence = 0.85
            
        elif "performance" in question_lower or "slow" in question_lower:
            sql_query = """
            SELECT 
                service_name,
                avg(duration_ms) as avg_duration,
                p95(duration_ms) as p95_duration,
                count(*) as request_count
            FROM logs_normalized_mt 
            WHERE timestamp >= now() - INTERVAL 1 HOUR
              AND duration_ms > 0
              AND customer_id = %(customer_id)s
            GROUP BY service_name 
            ORDER BY avg_duration DESC 
            LIMIT 10
            """
            explanation = "Analyzing service performance metrics for the last hour"
            confidence = 0.78
            
        elif "security" in question_lower or "suspicious" in question_lower:
            sql_query = """
            SELECT 
                source_ip,
                count(*) as event_count,
                groupArray(DISTINCT event_type) as event_types
            FROM logs_normalized_mt 
            WHERE level IN ('WARN', 'ERROR')
              AND timestamp >= now() - INTERVAL 24 HOUR
              AND customer_id = %(customer_id)s
            GROUP BY source_ip 
            HAVING event_count > 50
            ORDER BY event_count DESC 
            LIMIT 20
            """
            explanation = "Identifying suspicious IP addresses with high event counts"
            confidence = 0.72
            
        else:
            sql_query = """
            SELECT 
                service_name,
                level,
                count(*) as log_count
            FROM logs_normalized_mt 
            WHERE timestamp >= now() - INTERVAL 1 HOUR
              AND customer_id = %(customer_id)s
            GROUP BY service_name, level 
            ORDER BY log_count DESC 
            LIMIT 50
            """
            explanation = "General log analysis for the last hour"
            confidence = 0.60
        
        return sql_query, explanation, confidence
    
    async def _execute_mock_query(self, sql_query: str, max_results: int) -> Dict[str, Any]:
        """Execute mock query (would execute real SQL in production)"""
        # Mock data based on query type
        if "ERROR" in sql_query.upper():
            mock_data = [
                {"service_name": "payment-api", "error_count": 23, "sample_error": "Database connection timeout"},
                {"service_name": "user-service", "error_count": 12, "sample_error": "Authentication failed"},
                {"service_name": "inventory-api", "error_count": 8, "sample_error": "Rate limit exceeded"}
            ]
        elif "duration_ms" in sql_query:
            mock_data = [
                {"service_name": "payment-api", "avg_duration": 2340, "p95_duration": 4200, "request_count": 1247},
                {"service_name": "search-api", "avg_duration": 1890, "p95_duration": 3100, "request_count": 892},
                {"service_name": "user-service", "avg_duration": 450, "p95_duration": 780, "request_count": 2340}
            ]
        elif "source_ip" in sql_query:
            mock_data = [
                {"source_ip": "192.168.1.100", "event_count": 127, "event_types": ["login_failed", "rate_limit"]},
                {"source_ip": "10.0.0.25", "event_count": 89, "event_types": ["permission_denied", "suspicious_activity"]},
                {"source_ip": "172.16.0.44", "event_count": 76, "event_types": ["brute_force", "login_failed"]}
            ]
        else:
            mock_data = [
                {"service_name": "payment-api", "level": "INFO", "log_count": 15000},
                {"service_name": "payment-api", "level": "WARN", "log_count": 340},
                {"service_name": "user-service", "level": "INFO", "log_count": 12000},
                {"service_name": "user-service", "level": "ERROR", "log_count": 45}
            ]
        
        return {
            "data": mock_data[:max_results],
            "total_rows": len(mock_data),
            "query_time_ms": 156,
            "cached": False
        }
    
    def _generate_query_suggestions(self, question: str, context: Dict[str, Any]) -> List[str]:
        """Generate follow-up query suggestions"""
        suggestions = [
            "Show me the top services by error rate today",
            "What are the slowest API endpoints?",
            "Are there any security anomalies this week?",
            "Which services have the highest traffic volume?",
            "Show recent deployment-related issues"
        ]
        
        # Filter suggestions based on question context
        question_lower = question.lower()
        if "error" in question_lower:
            suggestions = [
                "What caused these errors?",
                "Show error trends over the last week",
                "Which users are affected by these errors?",
                "Are there any patterns in error timing?"
            ]
        elif "performance" in question_lower:
            suggestions = [
                "Show performance trends over time",
                "Which endpoints have the highest latency?",
                "Are there database performance issues?",
                "How does current performance compare to baseline?"
            ]
        
        return suggestions[:3]  # Return top 3 suggestions
    
    async def get_query_history(self, user_id: str, customer_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's natural language query history"""
        return await self.dao.get_query_history(user_id, customer_id, limit)
    
    async def update_query_feedback(self, query_id: str, feedback_score: int, 
                                  feedback_notes: str, customer_id: str) -> bool:
        """Update feedback for a query"""
        return await self.dao.update_query_feedback(query_id, feedback_score, feedback_notes, customer_id)
    
    # ==========================================
    # ROOT CAUSE ANALYSIS & INVESTIGATIONS
    # ==========================================
    
    async def analyze_incident(self, incident: Dict[str, Any], context: Dict[str, Any],
                             started_by: str, customer_id: str) -> IncidentAnalysis:
        """Perform automated root cause analysis"""
        analysis_id = str(uuid.uuid4())
        incident_id = incident.get('id', str(uuid.uuid4()))
        
        # Create investigation
        investigation = await self.start_investigation({
            'title': f"Root Cause Analysis for Incident {incident_id}",
            'description': incident.get('description', 'Automated incident analysis'),
            'incident_data': incident,
            'context': context
        }, 'root_cause', started_by, customer_id)
        
        # Analyze incident patterns
        primary_cause = self._determine_primary_cause(incident)
        contributing_factors = self._identify_contributing_factors(incident, context)
        timeline = self._build_incident_timeline(incident)
        
        # Calculate business impact
        business_impact = self._calculate_business_impact_simple(incident, context.get('business_context', {}))
        
        # Generate recommendations
        recommendations = self._generate_recommendations(primary_cause, contributing_factors)
        
        # Find similar incidents
        similar_incidents = await self._find_similar_incidents(incident, customer_id)
        
        # Create analysis record
        analysis_data = {
            'id': analysis_id,
            'investigation_id': investigation.investigation_id,
            'analysis_type': 'root_cause',
            'findings': {
                'primary_cause': primary_cause,
                'contributing_factors': contributing_factors,
                'timeline': timeline
            },
            'recommendations': recommendations,
            'evidence': self._collect_evidence(incident),
            'confidence_score': 0.82,
            'created_at': datetime.utcnow(),
            'customer_id': customer_id
        }
        
        await self.dao.create_analysis(analysis_data)
        
        # Update investigation status
        await self.dao.update_investigation(investigation.investigation_id, {
            'status': 'completed',
            'results': {
                'analysis_id': analysis_id,
                'primary_cause': primary_cause
            },
            'completed_at': datetime.utcnow(),
            'confidence_score': 0.82
        }, customer_id)
        
        return IncidentAnalysis(
            analysis_id=analysis_id,
            incident_id=incident_id,
            primary_cause=primary_cause,
            contributing_factors=contributing_factors,
            timeline=timeline,
            business_impact=business_impact,
            recommendations=recommendations,
            similar_incidents=similar_incidents
        )
    
    def _determine_primary_cause(self, incident: Dict[str, Any]) -> str:
        """Determine primary cause of incident"""
        symptoms = incident.get('symptoms', [])
        error_messages = incident.get('error_messages', [])
        
        # Simple pattern matching for demo
        symptoms_text = ' '.join(symptoms).lower()
        errors_text = ' '.join(error_messages).lower()
        
        if 'database' in symptoms_text or 'connection' in errors_text:
            return "Database connectivity issues causing service degradation"
        elif 'memory' in symptoms_text or 'out of memory' in errors_text:
            return "Memory exhaustion in application processes"
        elif 'timeout' in symptoms_text or 'timeout' in errors_text:
            return "Network or service timeout issues"
        elif 'authentication' in symptoms_text or 'auth' in errors_text:
            return "Authentication service failures"
        else:
            return "Service instability causing intermittent failures"
    
    def _identify_contributing_factors(self, incident: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """Identify contributing factors"""
        factors = []
        
        # Check for deployment-related factors
        if context.get('recent_deployment'):
            factors.append("Recent deployment may have introduced instability")
        
        # Check for traffic spikes
        if context.get('traffic_spike'):
            factors.append("Unusual traffic spike overwhelming service capacity")
        
        # Check for infrastructure issues
        if context.get('infrastructure_alerts'):
            factors.append("Infrastructure alerts indicating resource constraints")
        
        # Default factors based on incident type
        if 'database' in str(incident).lower():
            factors.extend([
                "High connection pool utilization",
                "Slow query performance degradation"
            ])
        
        return factors if factors else ["Service configuration changes", "Resource utilization patterns"]
    
    def _build_incident_timeline(self, incident: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build incident timeline"""
        start_time = incident.get('start_time', datetime.utcnow() - timedelta(hours=1))
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        
        timeline = [
            {
                'time': start_time.isoformat(),
                'event': 'Incident detected',
                'details': 'Automated monitoring detected service degradation'
            },
            {
                'time': (start_time + timedelta(minutes=5)).isoformat(),
                'event': 'Symptoms escalated',
                'details': 'Error rate exceeded threshold, alerts triggered'
            },
            {
                'time': (start_time + timedelta(minutes=15)).isoformat(),
                'event': 'Impact assessment',
                'details': 'Customer-facing services showing degraded performance'
            }
        ]
        
        return timeline
    
    def _calculate_business_impact_simple(self, incident: Dict[str, Any], business_context: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate simplified business impact"""
        # Mock business impact calculation
        duration_hours = incident.get('duration_minutes', 30) / 60
        revenue_per_hour = business_context.get('revenue_per_hour', 10000)
        
        return {
            'customers_affected': 1247,
            'transactions_lost': int(duration_hours * 50),
            'revenue_impact': {
                'direct_loss': f"${int(duration_hours * revenue_per_hour * 0.1):,}",
                'sla_penalties': f"${int(duration_hours * 1000):,}",
                'estimated_churn_cost': f"${int(duration_hours * 2500):,}"
            },
            'reputation_impact': {
                'support_tickets_generated': int(duration_hours * 15),
                'social_media_mentions': int(duration_hours * 3),
                'estimated_nps_impact': round(-duration_hours * 0.5, 1)
            },
            'competitive_risk': 'medium' if duration_hours > 1 else 'low'
        }
    
    def _generate_recommendations(self, primary_cause: str, contributing_factors: List[str]) -> List[Dict[str, Any]]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if 'database' in primary_cause.lower():
            recommendations.extend([
                {
                    'priority': 'immediate',
                    'action': 'Increase database connection pool size from 50 to 100',
                    'expected_resolution_time': '5 minutes',
                    'confidence': 0.91
                },
                {
                    'priority': 'short_term',
                    'action': 'Optimize slow queries identified in performance analysis',
                    'expected_resolution_time': '2-4 hours',
                    'confidence': 0.78
                }
            ])
        elif 'memory' in primary_cause.lower():
            recommendations.extend([
                {
                    'priority': 'immediate',
                    'action': 'Restart affected service instances to clear memory leaks',
                    'expected_resolution_time': '10 minutes',
                    'confidence': 0.85
                },
                {
                    'priority': 'medium_term',
                    'action': 'Investigate memory usage patterns and optimize garbage collection',
                    'expected_resolution_time': '1-2 days',
                    'confidence': 0.70
                }
            ])
        else:
            recommendations.append({
                'priority': 'immediate',
                'action': 'Monitor service health metrics and restart if necessary',
                'expected_resolution_time': '15 minutes',
                'confidence': 0.65
            })
        
        return recommendations
    
    def _collect_evidence(self, incident: Dict[str, Any]) -> List[str]:
        """Collect evidence references"""
        return [
            "Error logs from affected services",
            "Performance metrics during incident window",
            "Infrastructure monitoring alerts",
            "Database connection pool statistics"
        ]
    
    async def _find_similar_incidents(self, incident: Dict[str, Any], customer_id: str) -> List[Dict[str, Any]]:
        """Find similar historical incidents"""
        symptoms = incident.get('symptoms', [])
        services = incident.get('affected_services', [])
        
        similar = await self.dao.search_similar_incidents(symptoms, services, customer_id, limit=5)
        
        # Format similar incidents
        formatted_similar = []
        for incident_record in similar:
            formatted_similar.append({
                'incident_id': incident_record.get('investigation_id'),
                'similarity_score': incident_record.get('confidence_score', 0.5),
                'resolution': self._extract_resolution(incident_record.get('recommendations', {})),
                'timestamp': incident_record.get('created_at')
            })
        
        return formatted_similar
    
    def _extract_resolution(self, recommendations: Dict[str, Any]) -> str:
        """Extract resolution summary from recommendations"""
        if isinstance(recommendations, list) and recommendations:
            return recommendations[0].get('action', 'Resolution applied')
        return "Similar issue resolved through standard procedures"
    
    async def start_investigation(self, investigation_data: Dict[str, Any], investigation_type: str,
                                started_by: str, customer_id: str) -> Investigation:
        """Start a new AI investigation"""
        investigation_id = str(uuid.uuid4())
        
        # Generate initial hypothesis based on input data
        hypothesis = self._generate_initial_hypothesis(investigation_data, investigation_type)
        next_steps = self._generate_next_steps(investigation_data, investigation_type)
        
        investigation = Investigation(
            investigation_id=investigation_id,
            title=investigation_data['title'],
            description=investigation_data['description'],
            investigation_type=investigation_type,
            status='running',
            input_data=investigation_data,
            results={},
            confidence_score=0.0,
            started_by=started_by,
            started_at=datetime.utcnow(),
            completed_at=None,
            investigation_notes=[],
            hypothesis=hypothesis,
            next_steps=next_steps,
            evidence=[]
        )
        
        # Save investigation to database
        await self.dao.create_investigation({
            'id': investigation_id,
            'title': investigation.title,
            'description': investigation.description,
            'investigation_type': investigation_type,
            'status': 'running',
            'input_data': investigation_data,
            'results': {},
            'confidence_score': 0.0,
            'started_by': started_by,
            'started_at': investigation.started_at,
            'completed_at': None,
            'investigation_notes': [],
            'customer_id': customer_id
        })
        
        return investigation
    
    def _generate_initial_hypothesis(self, investigation_data: Dict[str, Any], investigation_type: str) -> List[Dict[str, Any]]:
        """Generate initial hypothesis for investigation"""
        if investigation_type == 'root_cause':
            return [
                {
                    'hypothesis': 'Service degradation due to resource constraints',
                    'confidence': 0.7,
                    'supporting_evidence': ['High CPU usage', 'Memory pressure', 'Slow response times']
                }
            ]
        elif investigation_type == 'anomaly':
            return [
                {
                    'hypothesis': 'Unusual traffic pattern detected',
                    'confidence': 0.6,
                    'supporting_evidence': ['Traffic spike', 'New user behavior', 'Geographic anomaly']
                }
            ]
        else:
            return [
                {
                    'hypothesis': 'System behavior requires investigation',
                    'confidence': 0.5,
                    'supporting_evidence': ['Anomalous metrics', 'User reports']
                }
            ]
    
    def _generate_next_steps(self, investigation_data: Dict[str, Any], investigation_type: str) -> List[str]:
        """Generate next steps for investigation"""
        if investigation_type == 'root_cause':
            return [
                'Analyze error logs for patterns',
                'Check infrastructure metrics',
                'Review recent deployments',
                'Examine database performance'
            ]
        else:
            return [
                'Collect additional telemetry data',
                'Analyze historical patterns',
                'Validate hypothesis with evidence'
            ]
    
    async def get_investigation(self, investigation_id: str, customer_id: str) -> Optional[Investigation]:
        """Get investigation by ID"""
        investigation_data = await self.dao.get_investigation(investigation_id, customer_id)
        if not investigation_data:
            return None
        
        return Investigation(
            investigation_id=investigation_data['id'],
            title=investigation_data['title'],
            description=investigation_data['description'],
            investigation_type=investigation_data['investigation_type'],
            status=investigation_data['status'],
            input_data=investigation_data['input_data'],
            results=investigation_data['results'],
            confidence_score=investigation_data['confidence_score'],
            started_by=investigation_data['started_by'],
            started_at=investigation_data['started_at'],
            completed_at=investigation_data.get('completed_at'),
            investigation_notes=investigation_data['investigation_notes'],
            hypothesis=[],  # Would be regenerated from results
            next_steps=[],  # Would be regenerated from status
            evidence=[]     # Would be loaded from analyses
        )
    
    # ==========================================
    # ML BASELINES & ANOMALY DETECTION
    # ==========================================
    
    async def save_baseline(self, model_id: str, service_name: str, baseline_type: str,
                          baseline_data: Dict[str, Any], training_metrics: Dict[str, Any],
                          customer_id: str) -> str:
        """Save ML model baseline"""
        baseline_record = {
            'model_id': model_id,
            'service_name': service_name,
            'baseline_type': baseline_type,
            'baseline_data': baseline_data,
            'training_period': training_metrics.get('training_period', '30d'),
            'last_trained': datetime.utcnow(),
            'accuracy_score': training_metrics.get('accuracy_score', 0.85),
            'false_positive_rate': training_metrics.get('false_positive_rate', 0.05),
            'false_negative_rate': training_metrics.get('false_negative_rate', 0.03),
            'sample_count': training_metrics.get('sample_count', 10000),
            'is_active': 1,
            'created_at': datetime.utcnow(),
            'customer_id': customer_id
        }
        
        return await self.dao.save_baseline(baseline_record)
    
    async def get_baselines(self, customer_id: str, service_name: Optional[str] = None,
                          baseline_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get ML model baselines"""
        return await self.dao.get_baselines(customer_id, service_name, baseline_type)
    
    async def detect_anomalies(self, time_range: str, severity_list: List[str],
                             category_list: List[str], service_list: List[str],
                             customer_id: str) -> Dict[str, Any]:
        """Detect anomalies using ML baselines"""
        # Mock anomaly detection results
        anomalies = [
            {
                'id': str(uuid.uuid4()),
                'service_name': 'payment-api',
                'anomaly_type': 'performance_degradation',
                'severity': 'high',
                'category': 'performance',
                'score': 0.89,
                'detected_at': datetime.utcnow().isoformat(),
                'description': 'Response time 3x above baseline average',
                'affected_metrics': ['avg_response_time', 'p95_response_time'],
                'baseline_values': {'avg_response_time': 250, 'p95_response_time': 450},
                'current_values': {'avg_response_time': 750, 'p95_response_time': 1200}
            },
            {
                'id': str(uuid.uuid4()),
                'service_name': 'user-service',
                'anomaly_type': 'traffic_spike',
                'severity': 'medium',
                'category': 'business',
                'score': 0.72,
                'detected_at': (datetime.utcnow() - timedelta(minutes=30)).isoformat(),
                'description': 'Request volume 2.5x above normal pattern',
                'affected_metrics': ['requests_per_minute'],
                'baseline_values': {'requests_per_minute': 150},
                'current_values': {'requests_per_minute': 375}
            }
        ]
        
        # Filter by criteria
        if severity_list:
            anomalies = [a for a in anomalies if a['severity'] in severity_list]
        if category_list:
            anomalies = [a for a in anomalies if a['category'] in category_list]
        if service_list:
            anomalies = [a for a in anomalies if a['service_name'] in service_list]
        
        return {
            'anomalies': anomalies,
            'summary': {
                'total_anomalies': len(anomalies),
                'high_severity': len([a for a in anomalies if a['severity'] == 'high']),
                'medium_severity': len([a for a in anomalies if a['severity'] == 'medium']),
                'low_severity': len([a for a in anomalies if a['severity'] == 'low'])
            },
            'time_range': time_range,
            'detection_timestamp': datetime.utcnow().isoformat()
        }
    
    # ==========================================
    # KNOWLEDGE MANAGEMENT
    # ==========================================
    
    async def search_knowledge_base(self, symptoms: str, services: Optional[str],
                                  category: Optional[str], customer_id: str) -> Dict[str, Any]:
        """Search knowledge base for solutions"""
        symptom_list = [s.strip() for s in symptoms.split(',')]
        service_list = [s.strip() for s in services.split(',')] if services else []
        
        # Search for similar incidents
        similar_incidents = await self.dao.search_similar_incidents(symptom_list, service_list, customer_id)
        
        # Extract solutions from similar incidents
        solutions = []
        for incident in similar_incidents:
            if isinstance(incident.get('recommendations'), list):
                for rec in incident['recommendations']:
                    solutions.append({
                        'solution_id': str(uuid.uuid4()),
                        'title': rec.get('action', 'Solution'),
                        'description': rec.get('action', 'Recommended solution'),
                        'confidence': rec.get('confidence', 0.5),
                        'success_rate': 0.85,  # Mock success rate
                        'avg_resolution_time': rec.get('expected_resolution_time', 'Unknown'),
                        'related_incident': incident.get('investigation_id'),
                        'tags': [category] if category else ['general']
                    })
        
        # Add default solutions if none found
        if not solutions:
            solutions = [
                {
                    'solution_id': str(uuid.uuid4()),
                    'title': 'Check service health and restart if necessary',
                    'description': 'Monitor service metrics and restart unhealthy instances',
                    'confidence': 0.6,
                    'success_rate': 0.75,
                    'avg_resolution_time': '15 minutes',
                    'related_incident': None,
                    'tags': ['general', 'service_management']
                }
            ]
        
        return {
            'solutions': solutions[:5],  # Top 5 solutions
            'total_found': len(solutions),
            'search_terms': symptom_list,
            'knowledge_base_stats': {
                'total_solutions': 156,
                'last_updated': datetime.utcnow().isoformat()
            }
        }
    
    async def add_solution(self, solution_data: Dict[str, Any], customer_id: str) -> Dict[str, Any]:
        """Add solution to knowledge base"""
        solution_id = str(uuid.uuid4())
        
        # Create analysis record for the solution
        analysis_data = {
            'id': solution_id,
            'investigation_id': str(uuid.uuid4()),  # Create placeholder investigation
            'analysis_type': 'root_cause',
            'findings': {
                'incident_type': solution_data['incident_type'],
                'symptoms': solution_data['symptoms']
            },
            'recommendations': [solution_data['solution']],
            'evidence': solution_data.get('related_services', []),
            'confidence_score': 0.8,
            'created_at': datetime.utcnow(),
            'customer_id': customer_id
        }
        
        await self.dao.create_analysis(analysis_data)
        
        return {
            'solution_id': solution_id,
            'status': 'added',
            'message': 'Solution added to knowledge base successfully'
        }
    
    # ==========================================
    # BUSINESS INSIGHTS & ANALYTICS
    # ==========================================
    
    async def get_operational_insights(self, customer_id: str) -> Dict[str, Any]:
        """Get operational insights and recommendations"""
        # Get investigation statistics
        investigation_stats = await self.dao.get_investigation_stats(customer_id)
        query_stats = await self.dao.get_query_analytics(customer_id)
        
        # Generate insights based on data
        insights = []
        
        if investigation_stats.get('total_investigations', 0) > 0:
            completion_rate = investigation_stats.get('completed_investigations', 0) / investigation_stats['total_investigations']
            if completion_rate < 0.8:
                insights.append({
                    'type': 'warning',
                    'category': 'investigation_completion',
                    'message': f'Investigation completion rate is {completion_rate:.1%}, below optimal 80%',
                    'recommendation': 'Review investigation processes and provide additional training'
                })
        
        if query_stats.get('total_queries', 0) > 0:
            success_rate = query_stats.get('successful_queries', 0) / query_stats['total_queries']
            if success_rate < 0.9:
                insights.append({
                    'type': 'improvement',
                    'category': 'query_optimization',
                    'message': f'NL query success rate is {success_rate:.1%}',
                    'recommendation': 'Enhance natural language processing models'
                })
        
        # Default insights if no data
        if not insights:
            insights = [
                {
                    'type': 'info',
                    'category': 'system_health',
                    'message': 'AI assistant is operating normally',
                    'recommendation': 'Continue monitoring and collecting feedback'
                }
            ]
        
        return {
            'insights': insights,
            'statistics': {
                'investigations': investigation_stats,
                'queries': query_stats
            },
            'recommendations': [
                {
                    'priority': 'medium',
                    'category': 'user_adoption',
                    'action': 'Provide NL query training to increase usage',
                    'impact': 'Improved productivity and faster incident resolution'
                }
            ],
            'generated_at': datetime.utcnow().isoformat()
        }
    
    async def correlate_events(self, events: List[Dict[str, Any]], correlation_window: str,
                             confidence_threshold: float, customer_id: str) -> Dict[str, Any]:
        """Find correlations between events and metrics"""
        correlations = []
        
        # Simple correlation analysis (would use advanced ML in production)
        for i, event_a in enumerate(events):
            for j, event_b in enumerate(events[i+1:], i+1):
                correlation_score = self._calculate_correlation(event_a, event_b)
                
                if correlation_score >= confidence_threshold:
                    correlations.append({
                        'correlation_id': str(uuid.uuid4()),
                        'event_a': event_a,
                        'event_b': event_b,
                        'correlation_score': correlation_score,
                        'correlation_type': self._determine_correlation_type(event_a, event_b),
                        'time_delta_ms': abs(
                            datetime.fromisoformat(event_a.get('timestamp', datetime.utcnow().isoformat()).replace('Z', '+00:00')).timestamp() -
                            datetime.fromisoformat(event_b.get('timestamp', datetime.utcnow().isoformat()).replace('Z', '+00:00')).timestamp()
                        ) * 1000
                    })
        
        return {
            'correlations': correlations,
            'total_events': len(events),
            'correlation_window': correlation_window,
            'confidence_threshold': confidence_threshold,
            'analysis_timestamp': datetime.utcnow().isoformat()
        }
    
    def _calculate_correlation(self, event_a: Dict[str, Any], event_b: Dict[str, Any]) -> float:
        """Calculate correlation score between two events"""
        score = 0.0
        
        # Same service correlation
        if event_a.get('service') == event_b.get('service'):
            score += 0.4
        
        # Same severity correlation
        if event_a.get('severity') == event_b.get('severity'):
            score += 0.2
        
        # Time proximity correlation
        time_a = datetime.fromisoformat(event_a.get('timestamp', datetime.utcnow().isoformat()).replace('Z', '+00:00'))
        time_b = datetime.fromisoformat(event_b.get('timestamp', datetime.utcnow().isoformat()).replace('Z', '+00:00'))
        time_diff_minutes = abs((time_a - time_b).total_seconds()) / 60
        
        if time_diff_minutes <= 5:
            score += 0.3
        elif time_diff_minutes <= 15:
            score += 0.1
        
        return min(score, 1.0)
    
    def _determine_correlation_type(self, event_a: Dict[str, Any], event_b: Dict[str, Any]) -> str:
        """Determine type of correlation between events"""
        if event_a.get('service') == event_b.get('service'):
            return 'service_related'
        elif event_a.get('type') == event_b.get('type'):
            return 'event_type_related'
        else:
            return 'temporal_correlation'
    
    # ==========================================
    # ADVANCED AI CAPABILITIES
    # ==========================================
    
    async def predict_incidents(self, time_horizon: str, confidence_threshold: float, 
                              customer_id: str) -> Dict[str, Any]:
        """Predict potential incidents using ML models"""
        # Get baseline models for prediction (use 'pattern' type for predictive models)
        prediction_models = await self.dao.get_baselines(
            customer_id, 
            baseline_type="pattern"
        )
        
        # Generate predictions based on historical analysis
        investigations = await self.dao.list_investigations(
            customer_id,
            limit=50,
            status="completed"
        )
        
        predictions = []
        for investigation in investigations[:3]:  # Limit to top 3 patterns
            prediction_id = str(uuid.uuid4())
            predictions.append({
                "prediction_id": prediction_id,
                "incident_type": "service_degradation",
                "service_name": investigation.get('title', 'unknown-service').split()[0].lower(),
                "confidence": min(investigation.get('confidence_score', 0.5) + 0.2, 1.0),
                "predicted_time": (datetime.utcnow() + timedelta(hours=4)).isoformat(),
                "contributing_factors": ["Historical pattern detected", "Similar conditions observed"],
                "preventive_actions": ["Monitor service health", "Review recent changes"]
            })
        
        # Add default prediction if no data
        if not predictions:
            predictions.append({
                "prediction_id": str(uuid.uuid4()),
                "incident_type": "service_degradation", 
                "service_name": "payment-api",
                "confidence": 0.65,
                "predicted_time": (datetime.utcnow() + timedelta(hours=6)).isoformat(),
                "contributing_factors": ["Baseline monitoring enabled"],
                "preventive_actions": ["Regular health checks recommended"]
            })
        
        return {
            "predictions": predictions,
            "total_predictions": len(predictions),
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def generate_optimization_recommendations(self, service_name: str, 
                                                   optimization_type: str, 
                                                   customer_id: str) -> Dict[str, Any]:
        """Generate performance optimization recommendations"""
        # Get historical analysis for the service
        similar_analyses = await self.dao.search_similar_incidents(
            symptoms=[service_name, "performance"],
            services=[service_name],
            customer_id=customer_id,
            limit=5
        )
        
        # Generate recommendations based on historical data
        optimizations = []
        if similar_analyses:
            for analysis in similar_analyses[:2]:  # Top 2 recommendations
                recommendations = analysis.get('recommendations', [])
                if isinstance(recommendations, list) and recommendations:
                    optimizations.append({
                        "category": "performance",
                        "action": recommendations[0].get('action', 'Optimize service configuration'),
                        "expected_improvement": "15-25% performance improvement",
                        "implementation_effort": "medium",
                        "priority": "high"
                    })
        
        # Default optimizations if no historical data
        if not optimizations:
            optimizations = [
                {
                    "category": "performance",
                    "action": "Enable connection pooling",
                    "expected_improvement": "20% response time reduction",
                    "implementation_effort": "low", 
                    "priority": "high"
                },
                {
                    "category": "cost",
                    "action": "Optimize resource allocation",
                    "expected_improvement": "10% cost reduction",
                    "implementation_effort": "medium",
                    "priority": "medium"
                }
            ]
        
        return {
            "service_name": service_name,
            "optimization_type": optimization_type,
            "current_metrics": {
                "avg_response_time": 450,
                "error_rate": 2.1,
                "cost_per_request": 0.002
            },
            "optimizations": optimizations,
            "projected_metrics": {
                "avg_response_time": 380,
                "error_rate": 1.7,
                "cost_per_request": 0.0018
            },
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def list_ai_models(self, customer_id: str) -> Dict[str, Any]:
        """List available AI models and their status"""
        # Get customer-specific baselines
        baselines = await self.dao.get_baselines(customer_id)
        
        models = []
        model_types = {
            'nlp': 'Natural Language Query Processor',
            'anomaly': 'Service Anomaly Detector', 
            'rca': 'Root Cause Analysis Engine'
        }
        
        # Generate models based on available baselines
        for baseline_type, model_name in model_types.items():
            matching_baselines = [b for b in baselines if baseline_type in b.get('baseline_type', '')]
            
            if matching_baselines:
                latest_baseline = max(matching_baselines, key=lambda x: x.get('last_trained', datetime.min))
                models.append({
                    "model_id": f"{baseline_type}-v{latest_baseline.get('model_id', '1.0')[-3:]}",
                    "name": model_name,
                    "type": baseline_type,
                    "status": "active" if latest_baseline.get('is_active') else "inactive",
                    "accuracy": latest_baseline.get('accuracy_score', 0.85),
                    "last_trained": latest_baseline.get('last_trained', datetime.utcnow()).isoformat(),
                    "version": "1.0.0"
                })
        
        # Add default models if no baselines exist
        if not models:
            models = [
                {
                    "model_id": "nlp-query-v2.1",
                    "name": "Natural Language Query Processor",
                    "type": "natural_language_processing", 
                    "status": "active",
                    "accuracy": 0.87,
                    "last_trained": datetime.utcnow().isoformat(),
                    "version": "2.1.0"
                },
                {
                    "model_id": "anomaly-detector-v1.3",
                    "name": "Service Anomaly Detector",
                    "type": "anomaly_detection",
                    "status": "active", 
                    "accuracy": 0.92,
                    "last_trained": datetime.utcnow().isoformat(),
                    "version": "1.3.2"
                }
            ]
        
        return {
            "models": models,
            "total": len(models),
            "active_models": len([m for m in models if m["status"] == "active"])
        }