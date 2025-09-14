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
            started_at, completed_at, investigation_notes, customer_id
        ) VALUES (
            %(id)s, %(title)s, %(description)s, %(investigation_type)s, %(status)s,
            %(input_data)s, %(results)s, %(confidence_score)s, %(started_by)s,
            %(started_at)s, %(completed_at)s, %(investigation_notes)s, %(customer_id)s
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
            'investigation_notes': json.dumps(investigation_data.get('investigation_notes', [])),
            'customer_id': investigation_data['customer_id']
        }
        
        await self.db.execute_query(query, params)
        return investigation_data['id']
    
    async def get_investigation(self, investigation_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get investigation by ID"""
        query = """
        SELECT id, title, description, investigation_type, status,
               input_data, results, confidence_score, started_by,
               started_at, completed_at, investigation_notes
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
            investigation['investigation_notes'] = json.loads(investigation['investigation_notes'])
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
        
        if 'investigation_notes' in updates:
            set_clauses.append("investigation_notes = %(investigation_notes)s")
            params['investigation_notes'] = json.dumps(updates['investigation_notes'])
        
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
            model_id, service_name, baseline_type, baseline_data,
            training_period, last_trained, accuracy_score,
            false_positive_rate, false_negative_rate, sample_count,
            is_active, created_at, customer_id
        ) VALUES (
            %(model_id)s, %(service_name)s, %(baseline_type)s, %(baseline_data)s,
            %(training_period)s, %(last_trained)s, %(accuracy_score)s,
            %(false_positive_rate)s, %(false_negative_rate)s, %(sample_count)s,
            %(is_active)s, %(created_at)s, %(customer_id)s
        )
        """
        
        params = {
            'model_id': baseline_data['model_id'],
            'service_name': baseline_data['service_name'],
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
        
        if service_name:
            where_conditions.append("service_name = %(service_name)s")
            params['service_name'] = service_name
        
        if baseline_type:
            where_conditions.append("baseline_type = %(baseline_type)s")
            params['baseline_type'] = baseline_type
        
        if active_only:
            where_conditions.append("is_active = 1")
        
        where_clause = " AND ".join(where_conditions)
        
        query = f"""
        SELECT model_id, service_name, baseline_type, baseline_data,
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
        # Create symptom search patterns
        symptom_patterns = []
        params = {'customer_id': customer_id, 'limit': limit}
        
        for i, symptom in enumerate(symptoms[:5]):  # Limit to 5 symptoms for performance
            symptom_key = f'symptom_{i}'
            symptom_patterns.append(f"positionCaseInsensitive(description, %({symptom_key})s) > 0")
            params[symptom_key] = symptom
        
        # Create service filters if provided
        service_filter = ""
        if services:
            service_conditions = []
            for i, service in enumerate(services[:3]):  # Limit to 3 services
                service_key = f'service_{i}'
                service_conditions.append(f"hasAny(arrayStringConcat(evidence, ' '), %({service_key})s)")
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
            avg(execution_time_ms) as avg_execution_time,
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
            avg(confidence_score) as avg_confidence_score,
            count(DISTINCT investigation_type) as unique_types
        FROM ai_investigations_mt
        WHERE customer_id = %(customer_id)s AND started_at >= %(since_date)s
        """
        
        params = {'customer_id': customer_id, 'since_date': since_date}
        result = await self.db.fetch_one(query, params)
        
        return dict(result) if result else {}