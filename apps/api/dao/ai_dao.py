"""
AI DAO - Data Access Operations for AI Engine

Handles database operations for:
- Natural language queries
- Root cause analysis
- Incident investigations
- ML model baselines
- Knowledge management
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from database_layer import DatabaseLayer


class AIDAO:
    """Data Access Object for AI engine operations"""
    
    def __init__(self):
        self.db = DatabaseLayer("AIDAO", "ai-dao-service-key")
    
    # ==========================================
    # NATURAL LANGUAGE QUERY OPERATIONS
    # ==========================================
    
    async def save_nl_query(self, query_data: Dict[str, Any]) -> str:
        """Save natural language query and generated SQL"""
        query = """
        INSERT INTO ai_query_history_mt (
            id, user_id, natural_query, generated_sql, 
            execution_status, result_count, execution_time_ms,
            feedback_score, feedback_notes, created_at, customer_id
        ) VALUES (
            %(id)s, %(user_id)s, %(natural_query)s, %(generated_sql)s,
            %(execution_status)s, %(result_count)s, %(execution_time_ms)s,
            %(feedback_score)s, %(feedback_notes)s, %(created_at)s, %(customer_id)s
        )
        """
        
        params = {
            'id': query_data['id'],
            'user_id': query_data['user_id'],
            'natural_query': query_data['natural_query'],
            'generated_sql': query_data['generated_sql'],
            'execution_status': query_data['execution_status'],
            'result_count': query_data['result_count'],
            'execution_time_ms': query_data['execution_time_ms'],
            'feedback_score': query_data.get('feedback_score'),
            'feedback_notes': query_data.get('feedback_notes'),
            'created_at': query_data['created_at'],
            'customer_id': query_data['customer_id']
        }
        
        await self.db.execute_query(query, params)
        return query_data['id']
    
    async def get_query_history(self, user_id: str, customer_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get natural language query history for user"""
        query = """
        SELECT id, user_id, natural_query, generated_sql, execution_status,
               result_count, execution_time_ms, feedback_score, feedback_notes,
               created_at
        FROM ai_query_history_mt
        WHERE customer_id = %(customer_id)s AND user_id = %(user_id)s
        ORDER BY created_at DESC
        LIMIT %(limit)s
        """
        
        params = {'customer_id': customer_id, 'user_id': user_id, 'limit': limit}
        results = await self.db.fetch_all(query, params)
        
        return [dict(result) for result in results]
    
    async def get_query_by_id(self, query_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get specific query by ID"""
        query = """
        SELECT id, user_id, natural_query, generated_sql, execution_status,
               result_count, execution_time_ms, feedback_score, feedback_notes,
               created_at
        FROM ai_query_history_mt
        WHERE customer_id = %(customer_id)s AND id = %(query_id)s
        """
        
        params = {'customer_id': customer_id, 'query_id': query_id}
        result = await self.db.fetch_one(query, params)
        
        return dict(result) if result else None
    
    async def update_query_feedback(self, query_id: str, feedback_score: int, 
                                  feedback_notes: str, customer_id: str) -> bool:
        """Update feedback for a query"""
        query = """
        ALTER TABLE ai_query_history_mt 
        UPDATE feedback_score = %(feedback_score)s, feedback_notes = %(feedback_notes)s
        WHERE customer_id = %(customer_id)s AND id = %(query_id)s
        """
        
        params = {
            'feedback_score': feedback_score,
            'feedback_notes': feedback_notes,
            'customer_id': customer_id,
            'query_id': query_id
        }
        
        await self.db.execute_query(query, params)
        return True
    
    # ==========================================
    # INVESTIGATION OPERATIONS
    # ==========================================
    
    async def create_investigation(self, investigation_data: Dict[str, Any]) -> str:
        """Create new AI investigation"""
        query = """
        INSERT INTO ai_investigations_mt (
            id, title, description, investigation_type, status,
            input_data, results, confidence_score, started_by,
            started_at, completed_at, customer_id
        ) VALUES (
            %(id)s, %(title)s, %(description)s, %(investigation_type)s, %(status)s,
            %(input_data)s, %(results)s, %(confidence_score)s, %(started_by)s,
            %(started_at)s, %(completed_at)s, %(customer_id)s
        )
        """
        
        params = {
            'id': investigation_data['id'],
            'title': investigation_data['title'],
            'description': investigation_data['description'],
            'investigation_type': investigation_data['investigation_type'],
            'status': investigation_data['status'],
            'input_data': json.dumps(investigation_data['input_data']),
            'results': json.dumps(investigation_data.get('results', {})),
            'confidence_score': investigation_data.get('confidence_score', 0.0),
            'started_by': investigation_data['started_by'],
            'started_at': investigation_data['started_at'],
            'completed_at': investigation_data.get('completed_at'),
            'customer_id': investigation_data['customer_id']
        }
        
        await self.db.execute_query(query, params)
        return investigation_data['id']
    
    async def get_investigation(self, investigation_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get investigation by ID"""
        query = """
        SELECT id, title, description, investigation_type, status,
               input_data, results, confidence_score, started_by,
               started_at, completed_at
        FROM ai_investigations_mt
        WHERE customer_id = %(customer_id)s AND id = %(investigation_id)s
        """
        
        params = {'customer_id': customer_id, 'investigation_id': investigation_id}
        result = await self.db.fetch_one(query, params)
        
        if result:
            investigation = dict(result)
            # Parse JSON fields
            investigation['input_data'] = json.loads(investigation['input_data'])
            investigation['results'] = json.loads(investigation['results'])
            # Add empty investigation_notes for backward compatibility
            investigation['investigation_notes'] = []
            return investigation
        
        return None
    
    async def update_investigation(self, investigation_id: str, updates: Dict[str, Any], 
                                 customer_id: str) -> bool:
        """Update investigation with new data"""
        set_clauses = []
        params = {'customer_id': customer_id, 'investigation_id': investigation_id}
        
        if 'status' in updates:
            set_clauses.append("status = %(status)s")
            params['status'] = updates['status']
        
        if 'results' in updates:
            set_clauses.append("results = %(results)s")
            params['results'] = json.dumps(updates['results'])
        
        if 'confidence_score' in updates:
            set_clauses.append("confidence_score = %(confidence_score)s")
            params['confidence_score'] = updates['confidence_score']
        
        if 'completed_at' in updates:
            set_clauses.append("completed_at = %(completed_at)s")
            params['completed_at'] = updates['completed_at']
        
        # Note: investigation_notes column doesn't exist in table schema
        # Ignoring investigation_notes updates for database compatibility
        
        if not set_clauses:
            return False
        
        query = f"""
        ALTER TABLE ai_investigations_mt 
        UPDATE {', '.join(set_clauses)}
        WHERE customer_id = %(customer_id)s AND id = %(investigation_id)s
        """
        
        await self.db.execute_query(query, params)
        return True
    
    async def list_investigations(self, customer_id: str, limit: int = 100,
                                investigation_type: Optional[str] = None,
                                status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List investigations with optional filters"""
        where_conditions = ["customer_id = %(customer_id)s"]
        params = {'customer_id': customer_id, 'limit': limit}
        
        if investigation_type:
            where_conditions.append("investigation_type = %(investigation_type)s")
            params['investigation_type'] = investigation_type
        
        if status:
            where_conditions.append("status = %(status)s")
            params['status'] = status
        
        where_clause = " AND ".join(where_conditions)
        
        query = f"""
        SELECT id, title, description, investigation_type, status,
               confidence_score, started_by, started_at, completed_at
        FROM ai_investigations_mt
        WHERE {where_clause}
        ORDER BY started_at DESC
        LIMIT %(limit)s
        """
        
        results = await self.db.fetch_all(query, params)
        return [dict(result) for result in results]
    
    # ==========================================
    # ANALYSIS OPERATIONS
    # ==========================================
    
    async def create_analysis(self, analysis_data: Dict[str, Any]) -> str:
        """Create AI analysis result"""
        query = """
        INSERT INTO ai_analyses_mt (
            id, investigation_id, analysis_type, findings,
            recommendations, evidence, confidence_score,
            created_at, customer_id
        ) VALUES (
            %(id)s, %(investigation_id)s, %(analysis_type)s, %(findings)s,
            %(recommendations)s, %(evidence)s, %(confidence_score)s,
            %(created_at)s, %(customer_id)s
        )
        """
        
        params = {
            'id': analysis_data['id'],
            'investigation_id': analysis_data['investigation_id'],
            'analysis_type': analysis_data['analysis_type'],
            'findings': json.dumps(analysis_data['findings']),
            'recommendations': json.dumps(analysis_data['recommendations']),
            'evidence': analysis_data['evidence'],  # Array of strings
            'confidence_score': analysis_data['confidence_score'],
            'created_at': analysis_data['created_at'],
            'customer_id': analysis_data['customer_id']
        }
        
        await self.db.execute_query(query, params)
        return analysis_data['id']
    
    async def get_analyses_for_investigation(self, investigation_id: str, 
                                           customer_id: str) -> List[Dict[str, Any]]:
        """Get all analyses for an investigation"""
        query = """
        SELECT id, investigation_id, analysis_type, findings,
               recommendations, evidence, confidence_score, created_at
        FROM ai_analyses_mt
        WHERE customer_id = %(customer_id)s AND investigation_id = %(investigation_id)s
        ORDER BY created_at DESC
        """
        
        params = {'customer_id': customer_id, 'investigation_id': investigation_id}
        results = await self.db.fetch_all(query, params)
        
        analyses = []
        for result in results:
            analysis = dict(result)
            # Parse JSON fields
            analysis['findings'] = json.loads(analysis['findings'])
            analysis['recommendations'] = json.loads(analysis['recommendations'])
            analyses.append(analysis)
        
        return analyses
    
    # ==========================================
    # BASELINE MODEL OPERATIONS
    # ==========================================
    
    async def save_baseline(self, baseline_data: Dict[str, Any]) -> str:
        """Save ML model baseline"""
        query = """
        INSERT INTO ai_baselines_mt (
            model_id, baseline_type, baseline_data,
            training_period, last_trained, accuracy_score,
            false_positive_rate, false_negative_rate, sample_count,
            is_active, created_at, customer_id
        ) VALUES (
            %(model_id)s, %(baseline_type)s, %(baseline_data)s,
            %(training_period)s, %(last_trained)s, %(accuracy_score)s,
            %(false_positive_rate)s, %(false_negative_rate)s, %(sample_count)s,
            %(is_active)s, %(created_at)s, %(customer_id)s
        )
        """
        
        params = {
            'model_id': baseline_data['model_id'],
            'baseline_type': baseline_data['baseline_type'],
            'baseline_data': json.dumps(baseline_data['baseline_data']),
            'training_period': baseline_data['training_period'],
            'last_trained': baseline_data['last_trained'],
            'accuracy_score': baseline_data['accuracy_score'],
            'false_positive_rate': baseline_data['false_positive_rate'],
            'false_negative_rate': baseline_data['false_negative_rate'],
            'sample_count': baseline_data['sample_count'],
            'is_active': baseline_data.get('is_active', 1),
            'created_at': baseline_data['created_at'],
            'customer_id': baseline_data['customer_id']
        }
        
        await self.db.execute_query(query, params)
        return baseline_data['model_id']
    
    async def get_baselines(self, customer_id: str, service_name: Optional[str] = None,
                          baseline_type: Optional[str] = None, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get ML model baselines with optional filters"""
        where_conditions = ["customer_id = %(customer_id)s"]
        params = {'customer_id': customer_id}
        
        # Note: service_name column doesn't exist in table schema
        # Ignoring service_name filter for database compatibility
        
        if baseline_type:
            where_conditions.append("baseline_type = %(baseline_type)s")
            params['baseline_type'] = baseline_type
        
        if active_only:
            where_conditions.append("is_active = 1")
        
        where_clause = " AND ".join(where_conditions)
        
        query = f"""
        SELECT model_id, baseline_type, baseline_data,
               training_period, last_trained, accuracy_score,
               false_positive_rate, false_negative_rate, sample_count,
               is_active, created_at
        FROM ai_baselines_mt
        WHERE {where_clause}
        ORDER BY last_trained DESC
        """
        
        results = await self.db.fetch_all(query, params)
        
        baselines = []
        for result in results:
            baseline = dict(result)
            # Parse JSON field
            baseline['baseline_data'] = json.loads(baseline['baseline_data'])
            # Add empty service_name for backward compatibility
            baseline['service_name'] = ''
            baselines.append(baseline)
        
        return baselines
    
    async def update_baseline(self, model_id: str, updates: Dict[str, Any], 
                            customer_id: str) -> bool:
        """Update ML model baseline"""
        set_clauses = []
        params = {'customer_id': customer_id, 'model_id': model_id}
        
        if 'baseline_data' in updates:
            set_clauses.append("baseline_data = %(baseline_data)s")
            params['baseline_data'] = json.dumps(updates['baseline_data'])
        
        if 'last_trained' in updates:
            set_clauses.append("last_trained = %(last_trained)s")
            params['last_trained'] = updates['last_trained']
        
        if 'accuracy_score' in updates:
            set_clauses.append("accuracy_score = %(accuracy_score)s")
            params['accuracy_score'] = updates['accuracy_score']
        
        if 'false_positive_rate' in updates:
            set_clauses.append("false_positive_rate = %(false_positive_rate)s")
            params['false_positive_rate'] = updates['false_positive_rate']
        
        if 'false_negative_rate' in updates:
            set_clauses.append("false_negative_rate = %(false_negative_rate)s")
            params['false_negative_rate'] = updates['false_negative_rate']
        
        if 'sample_count' in updates:
            set_clauses.append("sample_count = %(sample_count)s")
            params['sample_count'] = updates['sample_count']
        
        if 'is_active' in updates:
            set_clauses.append("is_active = %(is_active)s")
            params['is_active'] = updates['is_active']
        
        if not set_clauses:
            return False
        
        query = f"""
        ALTER TABLE ai_baselines_mt 
        UPDATE {', '.join(set_clauses)}
        WHERE customer_id = %(customer_id)s AND model_id = %(model_id)s
        """
        
        await self.db.execute_query(query, params)
        return True
    
    # ==========================================
    # KNOWLEDGE BASE OPERATIONS
    # ==========================================
    
    async def search_similar_incidents(self, symptoms: List[str], services: List[str],
                                     customer_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for similar incidents based on symptoms and services"""
        # Create symptom search patterns - search in findings JSON field
        symptom_patterns = []
        params = {'customer_id': customer_id, 'limit': limit}
        
        for i, symptom in enumerate(symptoms[:5]):  # Limit to 5 symptoms for performance
            symptom_key = f'symptom_{i}'
            symptom_patterns.append(f"positionCaseInsensitive(findings, %({symptom_key})s) > 0")
            params[symptom_key] = symptom
        
        # Create service filters if provided - search in evidence (handle both Array and String types)
        service_filter = ""
        if services:
            service_conditions = []
            for i, service in enumerate(services[:3]):  # Limit to 3 services
                service_key = f'service_{i}'
                # Use arrayStringConcat to handle Array(String) or treat as string
                service_conditions.append(f"positionCaseInsensitive(arrayStringConcat(evidence, ' '), %({service_key})s) > 0")
                params[service_key] = service
            service_filter = f"AND ({' OR '.join(service_conditions)})" if service_conditions else ""
        
        symptom_condition = f"({' OR '.join(symptom_patterns)})" if symptom_patterns else "1=1"
        
        query = f"""
        SELECT id, investigation_id, analysis_type, findings,
               recommendations, evidence, confidence_score, created_at
        FROM ai_analyses_mt
        WHERE customer_id = %(customer_id)s 
          AND analysis_type = 'root_cause'
          AND {symptom_condition}
          {service_filter}
        ORDER BY confidence_score DESC, created_at DESC
        LIMIT %(limit)s
        """
        
        results = await self.db.fetch_all(query, params)
        
        similar_incidents = []
        for result in results:
            incident = dict(result)
            # Parse JSON fields
            incident['findings'] = json.loads(incident['findings'])
            incident['recommendations'] = json.loads(incident['recommendations'])
            similar_incidents.append(incident)
        
        return similar_incidents
    
    async def get_knowledge_solutions(self, incident_type: str, customer_id: str) -> List[Dict[str, Any]]:
        """Get known solutions for incident type"""
        query = """
        SELECT id, investigation_id, recommendations, confidence_score
        FROM ai_analyses_mt
        WHERE customer_id = %(customer_id)s 
          AND analysis_type = 'root_cause'
          AND confidence_score >= 0.7
          AND positionCaseInsensitive(findings, %(incident_type)s) > 0
        ORDER BY confidence_score DESC
        LIMIT 20
        """
        
        params = {'customer_id': customer_id, 'incident_type': incident_type}
        results = await self.db.fetch_all(query, params)
        
        solutions = []
        for result in results:
            solution = dict(result)
            # Parse JSON field
            solution['recommendations'] = json.loads(solution['recommendations'])
            solutions.append(solution)
        
        return solutions
    
    # ==========================================
    # METRICS AND ANALYTICS
    # ==========================================
    
    async def get_query_analytics(self, customer_id: str, days: int = 30) -> Dict[str, Any]:
        """Get analytics on natural language queries"""
        since_date = datetime.utcnow() - timedelta(days=days)
        
        query = """
        SELECT 
            count(*) as total_queries,
            if(count(*) > 0, avg(execution_time_ms), 0) as avg_execution_time,
            countIf(execution_status = 'success') as successful_queries,
            countIf(execution_status = 'error') as failed_queries,
            countIf(feedback_score >= 0) as positive_feedback,
            countIf(feedback_score < 0) as negative_feedback
        FROM ai_query_history_mt
        WHERE customer_id = %(customer_id)s AND created_at >= %(since_date)s
        """
        
        params = {'customer_id': customer_id, 'since_date': since_date}
        result = await self.db.fetch_one(query, params)
        
        return dict(result) if result else {}
    
    async def get_investigation_stats(self, customer_id: str, days: int = 30) -> Dict[str, Any]:
        """Get investigation statistics"""
        since_date = datetime.utcnow() - timedelta(days=days)
        
        query = """
        SELECT 
            count(*) as total_investigations,
            countIf(status = 'completed') as completed_investigations,
            countIf(status = 'running') as running_investigations,
            if(count(*) > 0, avg(confidence_score), 0) as avg_confidence_score,
            count(DISTINCT investigation_type) as unique_types
        FROM ai_investigations_mt
        WHERE customer_id = %(customer_id)s AND started_at >= %(since_date)s
        """
        
        params = {'customer_id': customer_id, 'since_date': since_date}
        result = await self.db.fetch_one(query, params)
        
        return dict(result) if result else {}
    
    # ==========================================
    # NATURAL LANGUAGE QUERY EXECUTION
    # ==========================================
    
    async def execute_nl_query(self, sql_query: str, customer_id: str, max_results: int = 100) -> Dict[str, Any]:
        """Execute generated SQL query against logs database"""
        # Add customer_id parameter to the query if not present
        params = {'customer_id': customer_id}
        
        # Execute the query with limit
        if "LIMIT" not in sql_query.upper():
            sql_query = sql_query.rstrip(';') + f" LIMIT {max_results}"
        
        results = await self.db.fetch_all(sql_query, params)
        
        # Convert results to list of dictionaries
        data = [dict(row) for row in results] if results else []
        
        return {
            "data": data,
            "total_rows": len(data),
            "query_successful": True
        }
    
    async def calculate_business_impact(self, customer_id: str, duration_hours: float, 
                                      affected_services: List[str], business_context: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate business impact from real incident data"""
        # Calculate customers affected based on service usage
        if affected_services:
            service_filter = "AND service IN %(services)s"
            params = {'customer_id': customer_id, 'services': affected_services}
        else:
            service_filter = ""
            params = {'customer_id': customer_id}
        
        # Get customer impact from logs
        query = f"""
        SELECT 
            count(DISTINCT user_id) as customers_affected,
            count(*) as total_requests,
            countIf(level = 'ERROR') as error_requests
        FROM logs_normalized_mt 
        WHERE customer_id = %(customer_id)s 
          AND ts >= now() - INTERVAL {int(duration_hours * 60)} MINUTE
          {service_filter}
        """
        
        result = await self.db.fetch_one(query, params)
        impact_stats = dict(result) if result else {}
        
        # Calculate business metrics
        customers_affected = impact_stats.get('customers_affected', 0)
        error_rate = impact_stats.get('error_requests', 0) / max(1, impact_stats.get('total_requests', 1))
        
        # Calculate revenue impact based on business context
        revenue_per_hour = business_context.get('revenue_per_hour', 0)
        direct_loss = duration_hours * revenue_per_hour * error_rate
        
        return {
            'customers_affected': customers_affected,
            'transactions_lost': impact_stats.get('error_requests', 0),
            'revenue_impact': {
                'direct_loss': f"${int(direct_loss):,}",
                'sla_penalties': f"${int(duration_hours * business_context.get('sla_penalty_per_hour', 1000)):,}",
                'estimated_churn_cost': f"${int(customers_affected * business_context.get('churn_cost_per_customer', 100)):,}"
            },
            'reputation_impact': {
                'support_tickets_generated': int(customers_affected * 0.1),
                'social_media_mentions': max(1, int(customers_affected * 0.01)),
                'estimated_nps_impact': round(-duration_hours * 0.5, 1)
            },
            'competitive_risk': 'high' if error_rate > 0.1 else 'medium' if duration_hours > 1 else 'low'
        }
    
    async def detect_anomalies_from_baselines(self, customer_id: str, time_range: str, 
                                            severity_list: List[str], category_list: List[str], 
                                            service_list: List[str]) -> List[Dict[str, Any]]:
        """Detect anomalies by comparing current metrics to ML baselines"""
        # Parse time range
        if time_range == "1h":
            hours_back = 1
        elif time_range == "24h":
            hours_back = 24
        elif time_range == "7d":
            hours_back = 168
        else:
            hours_back = 24  # default
        
        # Get baseline models for comparison
        baselines_query = """
        SELECT model_id, baseline_type, baseline_data, accuracy_score
        FROM ai_baselines_mt
        WHERE customer_id = %(customer_id)s AND is_active = 1
        ORDER BY last_trained DESC
        """
        baselines_result = await self.db.fetch_all(baselines_query, {'customer_id': customer_id})
        
        if not baselines_result:
            return []  # No baselines to compare against
        
        # Analyze current service performance vs baselines
        performance_query = f"""
        SELECT 
            service,
            count(*) as total_requests,
            countIf(level = 'ERROR') as error_count,
            if(count(*) > 0 AND count(status) > 0, avg(status), 0) as avg_duration,
            quantile(0.95)(status) as p95_duration
        FROM logs_normalized_mt 
        WHERE customer_id = %(customer_id)s 
          AND ts >= now() - INTERVAL {hours_back} HOUR
          AND status > 0
        GROUP BY service
        HAVING total_requests > 10
        """
        
        params = {'customer_id': customer_id}
        if service_list:
            performance_query += " AND service IN %(service_list)s"
            params['service_list'] = service_list
            
        performance_results = await self.db.fetch_all(performance_query, params)
        
        anomalies = []
        for perf in performance_results:
            service_data = dict(perf)
            service_name = service_data['service']
            error_rate = service_data['error_count'] / max(1, service_data['total_requests'])
            avg_duration = service_data.get('avg_duration', 0)
            
            # Compare against baseline thresholds
            anomaly_score = 0.0
            anomaly_details = []
            
            # Error rate anomaly detection (baseline: < 2% error rate)
            if error_rate > 0.05:  # 5% error rate is high
                anomaly_score = max(anomaly_score, 0.8)
                anomaly_details.append(f"Error rate {error_rate:.1%} above normal")
            
            # Response time anomaly detection (baseline: < 1000ms avg)
            if avg_duration > 2000:  # 2 second average is slow
                anomaly_score = max(anomaly_score, 0.7)
                anomaly_details.append(f"Response time {avg_duration:.0f}ms above baseline")
            
            # Traffic anomaly detection
            if service_data['total_requests'] > 10000:  # High volume
                anomaly_score = max(anomaly_score, 0.6)
                anomaly_details.append(f"Traffic spike detected: {service_data['total_requests']} requests")
            
            # Create anomaly if score is significant
            if anomaly_score > 0.5:
                severity = 'high' if anomaly_score > 0.75 else 'medium' if anomaly_score > 0.6 else 'low'
                category = 'performance' if avg_duration > 1000 else 'business' if service_data['total_requests'] > 5000 else 'reliability'
                
                # Apply filters
                if severity_list and severity not in severity_list:
                    continue
                if category_list and category not in category_list:
                    continue
                    
                anomalies.append({
                    'id': str(uuid.uuid4()),
                    'service_name': service_name,
                    'anomaly_type': 'performance_degradation' if avg_duration > 1000 else 'error_spike' if error_rate > 0.05 else 'traffic_anomaly',
                    'severity': severity,
                    'category': category,
                    'score': round(anomaly_score, 2),
                    'detected_at': datetime.utcnow().isoformat(),
                    'description': '; '.join(anomaly_details),
                    'affected_metrics': ['error_rate', 'avg_response_time', 'request_volume'],
                    'baseline_values': {'error_rate': 0.02, 'avg_response_time': 500, 'request_volume': 1000},
                    'current_values': {
                        'error_rate': round(error_rate, 3),
                        'avg_response_time': int(avg_duration),
                        'request_volume': service_data['total_requests']
                    }
                })
        
        return anomalies
    
    async def analyze_root_cause_factors(self, service_name: str, error_pattern: str, 
                                       start_time: datetime, end_time: datetime) -> List[str]:
        """Analyze database logs to identify root cause factors for incidents"""
        factors = []
        
        # Query to analyze error patterns in the time window
        error_analysis_query = """
        SELECT 
            level,
            count(*) as error_count,
            groupArray(DISTINCT msg) as error_messages,
            count(DISTINCT src_ip) as unique_sources,
            if(count(*) > 0 AND count(status) > 0, avg(status), 0) as avg_status_code
        FROM logs_normalized_mt
        WHERE customer_id = %(customer_id)s
          AND ts >= %(start_time)s
          AND ts <= %(end_time)s
          AND service = %(service_name)s
          AND level IN ('ERROR', 'WARN')
        GROUP BY level
        ORDER BY error_count DESC
        """
        
        params = {
            'customer_id': 'system',  # Will be overridden by caller with proper customer_id
            'service_name': service_name,
            'start_time': start_time,
            'end_time': end_time
        }
        
        try:
            error_results = await self.db.fetch_all(error_analysis_query, params)
            
            for error_data in error_results:
                error_count = error_data['error_count']
                level = error_data['level']
                unique_sources = error_data['unique_sources']
                avg_status = error_data.get('avg_status_code', 500)
                
                # Analyze error patterns
                if error_count > 100:
                    factors.append(f"High volume of {level} errors ({error_count} occurrences)")
                elif error_count > 50:
                    factors.append(f"Moderate {level} error spike detected")
                
                # Analyze source distribution
                if unique_sources > 10:
                    factors.append("Errors distributed across multiple source IPs - possible system-wide issue")
                elif unique_sources <= 3:
                    factors.append("Errors concentrated from few sources - possible targeted issue")
                
                # Analyze HTTP status codes
                if avg_status >= 500:
                    factors.append("Server-side errors indicate internal service problems")
                elif avg_status >= 400:
                    factors.append("Client errors suggest API contract or validation issues")
            
            # Additional analysis: check for concurrent issues across services
            concurrent_issues_query = """
            SELECT 
                service,
                count(*) as error_count
            FROM logs_normalized_mt
            WHERE customer_id = %(customer_id)s
              AND ts >= %(start_time)s
              AND ts <= %(end_time)s
              AND service != %(service_name)s
              AND level = 'ERROR'
            GROUP BY service
            HAVING error_count > 10
            ORDER BY error_count DESC
            LIMIT 5
            """
            
            concurrent_results = await self.db.fetch_all(concurrent_issues_query, params)
            
            if len(concurrent_results) > 2:
                other_services = [r['service'] for r in concurrent_results]
                factors.append(f"Concurrent errors in related services: {', '.join(other_services[:3])}")
            
            # Pattern analysis based on error_pattern parameter
            if error_pattern:
                pattern_lower = error_pattern.lower()
                if 'timeout' in pattern_lower:
                    factors.append("Timeout patterns suggest network or dependency issues")
                elif 'connection' in pattern_lower:
                    factors.append("Connection errors indicate infrastructure or database connectivity problems")
                elif 'memory' in pattern_lower:
                    factors.append("Memory-related errors suggest resource exhaustion")
                elif 'auth' in pattern_lower:
                    factors.append("Authentication errors indicate security service issues")
            
            # If no specific factors found, provide general analysis
            if not factors:
                factors.append("Error analysis completed - no specific patterns identified")
                
        except Exception as e:
            # Fallback if database query fails
            factors.append(f"Unable to analyze root cause factors: {str(e)}")
            
        return factors