#!/usr/bin/env python3
"""
M6 Individual Functionality Test
Tests AI Assistant, Natural Language Query, Root Cause Analysis, Anomaly Detection, and Investigation Assistant
"""

import asyncio
import httpx
import json
import uuid
from datetime import datetime, timedelta

class M6TestSuite:
    """Test M6 AI Assistant & RCA functionality"""
    
    def __init__(self):
        self.base_url = "http://localhost:7080"
        self.test_results = {}
        self.test_customer = "test-m6-customer"
        self.test_incident_id = None
        self.test_investigation_id = None
        self.test_query_id = None
    
    async def test_ai_health(self):
        """Test AI engine health and model status"""
        print("🔄 Testing AI engine health...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/v1/ai/health",
                    headers={"X-Customer-ID": self.test_customer}
                )
                
                assert response.status_code == 200, f"AI health check failed: {response.text}"
                result = response.json()
                
                # Verify health response structure
                assert "status" in result
                assert "timestamp" in result
                assert "models" in result
                assert "knowledge_base" in result
                
                # Check model status
                models = result["models"]
                expected_models = ["nlq_processor", "anomaly_detector", "rca_engine", "prediction_engine"]
                for model in expected_models:
                    assert model in models, f"Missing model: {model}"
                    assert "status" in models[model]
                    assert models[model]["status"] in ["active", "training", "inactive"]
                
                # Check knowledge base stats
                kb = result["knowledge_base"]
                assert "total_solutions" in kb
                assert "incident_patterns" in kb
                assert "confidence_score" in kb
                assert isinstance(kb["total_solutions"], int)
                assert isinstance(kb["confidence_score"], float)
                
                print("✅ AI engine health successful")
                self.test_results["ai_health"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ AI engine health failed: {str(e)}")
                self.test_results["ai_health"] = f"FAIL: {str(e)}"
                return False
    
    async def test_natural_language_query(self):
        """Test natural language query processing"""
        print("🔄 Testing natural language query...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Test basic NLQ
                nlq_request = {
                    "question": "Show me API errors for payment service in the last hour",
                    "context": {
                        "user_role": "devops_engineer",
                        "preferred_format": "table",
                        "include_suggestions": True
                    },
                    "max_results": 100
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/ai/query",
                    json=nlq_request,
                    headers={"X-Customer-ID": self.test_customer}
                )
                
                assert response.status_code == 200, f"Natural language query failed: {response.text}"
                result = response.json()
                
                # Verify NLQ response structure
                assert "query_id" in result
                assert "original_question" in result
                assert "generated_sql" in result
                assert "explanation" in result
                assert "results" in result
                assert "suggestions" in result
                assert "confidence_score" in result
                
                # Store query ID for future tests
                self.test_query_id = result["query_id"]
                
                # Verify SQL generation
                assert isinstance(result["generated_sql"], str)
                assert len(result["generated_sql"]) > 0
                assert "SELECT" in result["generated_sql"].upper()
                
                # Verify confidence score
                assert isinstance(result["confidence_score"], float)
                assert 0.0 <= result["confidence_score"] <= 1.0
                
                # Verify suggestions
                assert isinstance(result["suggestions"], list)
                
                # Verify results structure
                query_results = result["results"]
                assert "logs" in query_results
                assert "total_count" in query_results
                assert "execution_time_ms" in query_results
                assert isinstance(query_results["logs"], list)
                assert isinstance(query_results["total_count"], int)
                assert isinstance(query_results["execution_time_ms"], int)
                
                print("✅ Natural language query successful")
                self.test_results["natural_language_query"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Natural language query failed: {str(e)}")
                self.test_results["natural_language_query"] = f"FAIL: {str(e)}"
                return False
    
    async def test_query_suggestions(self):
        """Test intelligent query suggestions"""
        print("🔄 Testing query suggestions...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/v1/ai/query/suggestions",
                    headers={"X-Customer-ID": self.test_customer},
                    params={
                        "user_role": "devops_engineer",
                        "context": "general_exploration",
                        "time_range": "24h"
                    }
                )
                
                assert response.status_code == 200, f"Query suggestions failed: {response.text}"
                result = response.json()
                
                # Verify suggestions structure
                assert "suggestions" in result
                assert "trending_queries" in result
                assert isinstance(result["suggestions"], list)
                assert isinstance(result["trending_queries"], list)
                
                # Check suggestion items
                if result["suggestions"]:
                    suggestion = result["suggestions"][0]
                    assert "category" in suggestion
                    assert "question" in suggestion
                    assert "description" in suggestion
                    assert "complexity" in suggestion
                    assert suggestion["complexity"] in ["beginner", "intermediate", "advanced"]
                
                print("✅ Query suggestions successful")
                self.test_results["query_suggestions"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Query suggestions failed: {str(e)}")
                self.test_results["query_suggestions"] = f"FAIL: {str(e)}"
                return False
    
    async def test_incident_analysis(self):
        """Test automated root cause analysis"""
        print("🔄 Testing incident analysis...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Create test incident for RCA
                self.test_incident_id = f"INC-M6-{str(uuid.uuid4())[:8]}"
                
                incident_request = {
                    "incident": {
                        "id": self.test_incident_id,
                        "title": "Payment API High Error Rate",
                        "description": "Payment service error rate spiked to 15% at 14:30 UTC",
                        "start_time": (datetime.now() - timedelta(hours=1)).isoformat(),
                        "end_time": datetime.now().isoformat(),
                        "affected_services": ["payment-api", "user-service"],
                        "severity": "high"
                    },
                    "context": {
                        "include_historical": True,
                        "analysis_depth": "comprehensive",
                        "business_impact": True
                    }
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/ai/analyze-incident",
                    json=incident_request,
                    headers={"X-Customer-ID": self.test_customer}
                )
                
                assert response.status_code == 200, f"Incident analysis failed: {response.text}"
                result = response.json()
                
                # Verify RCA response structure
                assert "analysis_id" in result
                assert "incident_id" in result
                assert "root_cause_analysis" in result
                assert "business_impact" in result
                assert "recommendations" in result
                assert "similar_incidents" in result
                
                # Check root cause analysis
                rca = result["root_cause_analysis"]
                assert "primary_cause" in rca
                assert "contributing_factors" in rca
                assert "timeline" in rca
                
                # Check primary cause structure
                primary_cause = rca["primary_cause"]
                assert "type" in primary_cause
                assert "confidence" in primary_cause
                assert "description" in primary_cause
                assert "evidence" in primary_cause
                assert isinstance(primary_cause["confidence"], float)
                assert 0.0 <= primary_cause["confidence"] <= 1.0
                
                # Check business impact
                business_impact = result["business_impact"]
                assert "customers_affected" in business_impact
                assert "revenue_impact" in business_impact
                assert "reputation_impact" in business_impact
                assert "competitive_risk" in business_impact
                
                # Check recommendations
                recommendations = result["recommendations"]
                assert isinstance(recommendations, list)
                if recommendations:
                    rec = recommendations[0]
                    assert "priority" in rec
                    assert "action" in rec
                    assert "expected_resolution_time" in rec
                    assert "confidence" in rec
                    assert rec["priority"] in ["immediate", "short_term", "long_term"]
                
                print("✅ Incident analysis successful")
                self.test_results["incident_analysis"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Incident analysis failed: {str(e)}")
                if hasattr(e, 'response'):
                    print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
                import traceback
                traceback.print_exc()
                self.test_results["incident_analysis"] = f"FAIL: {str(e)}"
                return False
    
    async def test_symptom_analysis(self):
        """Test symptom analysis without formal incident"""
        print("🔄 Testing symptom analysis...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                symptom_request = {
                    "symptoms": [
                        "API response times increased by 200ms",
                        "Error rate climbing slowly over 2 hours", 
                        "Customer complaints about checkout failures"
                    ],
                    "time_range": {
                        "start": (datetime.now() - timedelta(hours=4)).isoformat(),
                        "end": datetime.now().isoformat()
                    },
                    "services": ["payment-api", "checkout-service", "user-service"]
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/ai/analyze-symptoms",
                    json=symptom_request,
                    headers={"X-Customer-ID": self.test_customer}
                )
                
                assert response.status_code == 200, f"Symptom analysis failed: {response.text}"
                result = response.json()
                
                # Verify symptom analysis response
                assert "analysis_id" in result
                assert "symptoms_analyzed" in result
                assert "potential_causes" in result
                assert "confidence_scores" in result
                assert "recommended_investigations" in result
                
                # Check potential causes
                causes = result["potential_causes"]
                assert isinstance(causes, list)
                if causes:
                    cause = causes[0]
                    assert "type" in cause
                    assert "description" in cause
                    assert "likelihood" in cause
                    assert isinstance(cause["likelihood"], float)
                    assert 0.0 <= cause["likelihood"] <= 1.0
                
                print("✅ Symptom analysis successful")
                self.test_results["symptom_analysis"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Symptom analysis failed: {str(e)}")
                self.test_results["symptom_analysis"] = f"FAIL: {str(e)}"
                return False
    
    async def test_anomaly_detection(self):
        """Test anomaly detection across systems"""
        print("🔄 Testing anomaly detection...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/v1/ai/anomalies",
                    headers={"X-Customer-ID": self.test_customer},
                    params={
                        "time_range": "24h",
                        "severity": "medium,high,critical",
                        "category": "performance,security,business"
                    }
                )
                
                assert response.status_code == 200, f"Anomaly detection failed: {response.text}"
                result = response.json()
                
                # Verify anomaly response structure
                assert "anomalies" in result
                assert "summary" in result
                assert isinstance(result["anomalies"], list)
                
                # Check summary structure
                summary = result["summary"]
                assert "total_anomalies" in summary
                assert "by_severity" in summary
                assert "by_category" in summary
                assert isinstance(summary["total_anomalies"], int)
                
                # Check anomaly items if present
                if result["anomalies"]:
                    anomaly = result["anomalies"][0]
                    assert "anomaly_id" in anomaly
                    assert "detected_at" in anomaly
                    assert "category" in anomaly
                    assert "severity" in anomaly
                    assert "title" in anomaly
                    assert "description" in anomaly
                    assert "confidence" in anomaly
                    assert "baseline_value" in anomaly
                    assert "current_value" in anomaly
                    assert "deviation_score" in anomaly
                    assert "affected_services" in anomaly
                    assert "potential_impact" in anomaly
                    assert "recommended_actions" in anomaly
                    
                    # Validate field types
                    assert isinstance(anomaly["confidence"], float)
                    assert 0.0 <= anomaly["confidence"] <= 1.0
                    assert anomaly["severity"] in ["low", "medium", "high", "critical"]
                    assert anomaly["category"] in ["performance", "security", "business", "infrastructure"]
                    assert isinstance(anomaly["affected_services"], list)
                    assert isinstance(anomaly["recommended_actions"], list)
                
                print("✅ Anomaly detection successful")
                self.test_results["anomaly_detection"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Anomaly detection failed: {str(e)}")
                self.test_results["anomaly_detection"] = f"FAIL: {str(e)}"
                return False
    
    async def test_failure_prediction(self):
        """Test failure prediction and forecasting"""
        print("🔄 Testing failure prediction...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                prediction_request = {
                    "prediction_type": "failure_forecast",
                    "time_horizon": "24h",
                    "services": ["payment-api", "user-service"],
                    "confidence_threshold": 0.7
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/ai/predict",
                    json=prediction_request,
                    headers={"X-Customer-ID": self.test_customer}
                )
                
                assert response.status_code == 200, f"Failure prediction failed: {response.text}"
                result = response.json()
                
                # Verify prediction response structure
                assert "predictions" in result
                assert isinstance(result["predictions"], list)
                
                # Check prediction items if present
                if result["predictions"]:
                    prediction = result["predictions"][0]
                    assert "prediction_id" in prediction
                    assert "type" in prediction
                    assert "service" in prediction
                    assert "predicted_time" in prediction
                    assert "confidence" in prediction
                    assert "description" in prediction
                    assert "indicators" in prediction
                    assert "preventive_actions" in prediction
                    assert "business_impact" in prediction
                    
                    # Validate prediction confidence
                    assert isinstance(prediction["confidence"], float)
                    assert 0.0 <= prediction["confidence"] <= 1.0
                    
                    # Check business impact structure
                    business_impact = prediction["business_impact"]
                    assert "risk_level" in business_impact
                    assert "estimated_customer_impact" in business_impact
                    assert "estimated_revenue_risk" in business_impact
                    assert business_impact["risk_level"] in ["low", "medium", "high", "critical"]
                    
                    # Check indicators and actions are lists
                    assert isinstance(prediction["indicators"], list)
                    assert isinstance(prediction["preventive_actions"], list)
                
                print("✅ Failure prediction successful")
                self.test_results["failure_prediction"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Failure prediction failed: {str(e)}")
                self.test_results["failure_prediction"] = f"FAIL: {str(e)}"
                return False
    
    async def test_investigation_assistant(self):
        """Test guided investigation session"""
        print("🔄 Testing investigation assistant...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Start new investigation
                investigation_request = {
                    "investigation": {
                        "title": "Payment Service Degradation Investigation", 
                        "initial_symptoms": [
                            "Payment API error rate at 8%",
                            "Customer reports of failed transactions",
                            "Database connection timeouts in logs"
                        ],
                        "priority": "high",
                        "assigned_to": ["test@company.com"]
                    }
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/ai/investigate/start",
                    json=investigation_request,
                    headers={"X-Customer-ID": self.test_customer}
                )
                
                assert response.status_code == 200, f"Investigation start failed: {response.text}"
                result = response.json()
                
                # Verify investigation response structure
                assert "investigation_id" in result
                assert "status" in result
                assert "next_steps" in result
                assert "hypothesis" in result
                
                # Store investigation ID for follow-up tests
                self.test_investigation_id = result["investigation_id"]
                
                # Check investigation status
                assert result["status"] in ["active", "pending", "completed"]
                
                # Check next steps
                next_steps = result["next_steps"]
                assert isinstance(next_steps, list)
                if next_steps:
                    step = next_steps[0]
                    assert "step_id" in step
                    assert "action" in step
                    assert "query" in step
                    assert "expected_outcome" in step
                    assert isinstance(step["step_id"], int)
                
                # Check hypothesis
                hypothesis = result["hypothesis"]
                assert isinstance(hypothesis, list)
                if hypothesis:
                    hyp = hypothesis[0]
                    assert "description" in hyp
                    assert "confidence" in hyp
                    assert "supporting_evidence" in hyp
                    assert isinstance(hyp["confidence"], float)
                    assert 0.0 <= hyp["confidence"] <= 1.0
                    assert isinstance(hyp["supporting_evidence"], list)
                
                print("✅ Investigation assistant successful")
                self.test_results["investigation_assistant"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Investigation assistant failed: {str(e)}")
                self.test_results["investigation_assistant"] = f"FAIL: {str(e)}"
                return False
    
    async def test_investigation_evidence(self):
        """Test adding evidence to investigation"""
        print("🔄 Testing investigation evidence...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Skip if no investigation ID
                if not self.test_investigation_id:
                    print("⚠️ No investigation available for evidence testing")
                    self.test_results["investigation_evidence"] = "SKIP: No investigation"
                    return True
                
                evidence_request = {
                    "evidence": {
                        "type": "log_analysis",
                        "description": "Found database connection timeouts in payment service logs",
                        "data": {
                            "query": "SELECT * FROM logs_normalized_mt WHERE service='payment-api' AND msg LIKE '%connection timeout%'",
                            "results_count": 45,
                            "time_range": "last 2 hours"
                        },
                        "confidence": 0.85,
                        "source": "manual_analysis"
                    }
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/ai/investigate/{self.test_investigation_id}/evidence",
                    json=evidence_request,
                    headers={"X-Customer-ID": self.test_customer}
                )
                
                assert response.status_code == 200, f"Investigation evidence failed: {response.text}"
                result = response.json()
                
                # Verify evidence response
                assert "evidence_id" in result
                assert "investigation_id" in result
                assert "updated_hypothesis" in result
                assert "confidence_change" in result
                
                # Check updated hypothesis
                hypothesis = result["updated_hypothesis"]
                assert isinstance(hypothesis, list)
                if hypothesis:
                    hyp = hypothesis[0]
                    assert "description" in hyp
                    assert "confidence" in hyp
                    assert isinstance(hyp["confidence"], float)
                
                print("✅ Investigation evidence successful")
                self.test_results["investigation_evidence"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Investigation evidence failed: {str(e)}")
                self.test_results["investigation_evidence"] = f"FAIL: {str(e)}"
                return False
    
    async def test_investigation_recommendations(self):
        """Test AI-powered investigation recommendations"""
        print("🔄 Testing investigation recommendations...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Skip if no investigation ID
                if not self.test_investigation_id:
                    print("⚠️ No investigation available for recommendations testing")
                    self.test_results["investigation_recommendations"] = "SKIP: No investigation"
                    return True
                
                response = await client.get(
                    f"{self.base_url}/v1/ai/investigate/{self.test_investigation_id}/recommendations",
                    headers={"X-Customer-ID": self.test_customer}
                )
                
                assert response.status_code == 200, f"Investigation recommendations failed: {response.text}"
                result = response.json()
                
                # Verify recommendations response
                assert "investigation_id" in result
                assert "next_steps" in result
                assert "priority_actions" in result
                assert "additional_evidence" in result
                
                # Check next steps
                next_steps = result["next_steps"]
                assert isinstance(next_steps, list)
                if next_steps:
                    step = next_steps[0]
                    assert "action" in step
                    assert "reasoning" in step
                    assert "expected_outcome" in step
                    assert "confidence" in step
                    assert isinstance(step["confidence"], float)
                
                # Check priority actions
                priority_actions = result["priority_actions"]
                assert isinstance(priority_actions, list)
                if priority_actions:
                    action = priority_actions[0]
                    assert "description" in action
                    assert "urgency" in action
                    assert "impact" in action
                    assert action["urgency"] in ["low", "medium", "high", "critical"]
                
                print("✅ Investigation recommendations successful")
                self.test_results["investigation_recommendations"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Investigation recommendations failed: {str(e)}")
                self.test_results["investigation_recommendations"] = f"FAIL: {str(e)}"
                return False
    
    async def test_knowledge_search(self):
        """Test knowledge base search for solutions"""
        print("🔄 Testing knowledge search...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/v1/ai/knowledge/search",
                    headers={"X-Customer-ID": self.test_customer},
                    params={
                        "symptoms": "database connection timeout",
                        "services": "payment-api",
                        "category": "performance"
                    }
                )
                
                assert response.status_code == 200, f"Knowledge search failed: {response.text}"
                result = response.json()
                
                # Verify knowledge search response
                assert "solutions" in result
                assert "total_found" in result
                assert "search_time_ms" in result
                assert isinstance(result["solutions"], list)
                assert isinstance(result["total_found"], int)
                
                # Check solution structure if present
                if result["solutions"]:
                    solution = result["solutions"][0]
                    assert "solution_id" in solution
                    assert "title" in solution
                    assert "description" in solution
                    assert "steps" in solution
                    assert "resolution_time" in solution
                    assert "effectiveness_score" in solution
                    assert "tags" in solution
                    assert "related_services" in solution
                    
                    # Validate effectiveness score
                    assert isinstance(solution["effectiveness_score"], float)
                    assert 0.0 <= solution["effectiveness_score"] <= 1.0
                    
                    # Check steps are a list
                    assert isinstance(solution["steps"], list)
                    assert isinstance(solution["tags"], list)
                    assert isinstance(solution["related_services"], list)
                
                print("✅ Knowledge search successful")
                self.test_results["knowledge_search"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Knowledge search failed: {str(e)}")
                self.test_results["knowledge_search"] = f"FAIL: {str(e)}"
                return False
    
    async def test_knowledge_solutions(self):
        """Test adding solutions to knowledge base"""
        print("🔄 Testing knowledge solutions...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                solution_request = {
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
                
                response = await client.post(
                    f"{self.base_url}/v1/ai/knowledge/solutions",
                    json=solution_request,
                    headers={"X-Customer-ID": self.test_customer}
                )
                
                assert response.status_code == 200, f"Knowledge solutions failed: {response.text}"
                result = response.json()
                
                # Verify solution creation response
                assert "solution_id" in result
                assert "status" in result
                assert "knowledge_base_updated" in result
                assert result["status"] in ["created", "updated"]
                assert isinstance(result["knowledge_base_updated"], bool)
                
                print("✅ Knowledge solutions successful")
                self.test_results["knowledge_solutions"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Knowledge solutions failed: {str(e)}")
                self.test_results["knowledge_solutions"] = f"FAIL: {str(e)}"
                return False
    
    async def test_business_impact(self):
        """Test business impact calculation"""
        print("🔄 Testing business impact analysis...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                impact_request = {
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
                
                response = await client.post(
                    f"{self.base_url}/v1/ai/business-impact",
                    json=impact_request,
                    headers={"X-Customer-ID": self.test_customer}
                )
                
                assert response.status_code == 200, f"Business impact failed: {response.text}"
                result = response.json()
                
                # Verify business impact response
                assert "impact_analysis" in result
                impact = result["impact_analysis"]
                
                assert "customers_affected" in impact
                assert "transactions_lost" in impact
                assert "revenue_impact" in impact
                assert "reputation_impact" in impact
                assert "competitive_risk" in impact
                
                # Check revenue impact structure
                revenue = impact["revenue_impact"]
                assert "direct_loss" in revenue
                assert "sla_penalties" in revenue
                assert "estimated_churn_cost" in revenue
                
                # Check reputation impact structure
                reputation = impact["reputation_impact"]
                assert "support_tickets_generated" in reputation
                assert "social_media_mentions" in reputation
                assert "estimated_nps_impact" in reputation
                
                # Validate numeric fields
                assert isinstance(impact["customers_affected"], int)
                assert isinstance(impact["transactions_lost"], int)
                assert impact["competitive_risk"] in ["low", "medium", "high", "critical"]
                
                print("✅ Business impact analysis successful")
                self.test_results["business_impact"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Business impact analysis failed: {str(e)}")
                self.test_results["business_impact"] = f"FAIL: {str(e)}"
                return False
    
    async def test_operational_insights(self):
        """Test operational insights and improvement recommendations"""
        print("🔄 Testing operational insights...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/v1/ai/insights/operational",
                    headers={"X-Customer-ID": self.test_customer}
                )
                
                assert response.status_code == 200, f"Operational insights failed: {response.text}"
                result = response.json()
                
                # Verify insights response structure
                assert "insights" in result
                assert "team_performance" in result
                assert isinstance(result["insights"], list)
                
                # Check insight structure if present
                if result["insights"]:
                    insight = result["insights"][0]
                    assert "type" in insight
                    assert "title" in insight
                    assert "description" in insight
                    assert "frequency" in insight
                    assert "impact" in insight
                    assert "recommended_fix" in insight
                    assert "estimated_savings" in insight
                    assert insight["type"] in ["recurring_pattern", "performance_drift", "capacity_issue", "process_improvement"]
                
                # Check team performance metrics
                team_perf = result["team_performance"]
                assert "average_investigation_time" in team_perf
                assert "improvement_trend" in team_perf
                assert "knowledge_base_usage" in team_perf
                
                print("✅ Operational insights successful")
                self.test_results["operational_insights"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Operational insights failed: {str(e)}")
                self.test_results["operational_insights"] = f"FAIL: {str(e)}"
                return False
    
    async def test_business_metrics(self):
        """Test business-context performance metrics"""
        print("🔄 Testing business metrics...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/v1/ai/metrics/business",
                    headers={"X-Customer-ID": self.test_customer},
                    params={
                        "time_range": "24h",
                        "services": "payment-api,user-service",
                        "metrics": "revenue_correlation,sla_compliance,customer_satisfaction"
                    }
                )
                
                assert response.status_code == 200, f"Business metrics failed: {response.text}"
                result = response.json()
                
                # Verify business metrics response
                assert "metrics" in result
                assert "time_range" in result
                assert "correlation_analysis" in result
                
                # Check metrics structure
                metrics = result["metrics"]
                if metrics:
                    for metric_name, metric_data in metrics.items():
                        assert "current_value" in metric_data
                        assert "baseline_value" in metric_data
                        assert "trend" in metric_data
                        assert "business_impact" in metric_data
                        assert metric_data["trend"] in ["improving", "stable", "degrading", "critical"]
                
                # Check correlation analysis
                correlation = result["correlation_analysis"]
                assert "technical_business_correlation" in correlation
                assert "confidence_score" in correlation
                assert isinstance(correlation["confidence_score"], float)
                
                print("✅ Business metrics successful")
                self.test_results["business_metrics"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Business metrics failed: {str(e)}")
                self.test_results["business_metrics"] = f"FAIL: {str(e)}"
                return False
    
    async def test_slack_integration(self):
        """Test Slack integration for conversational AI"""
        print("🔄 Testing Slack integration...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                slack_request = {
                    "slack_event": {
                        "user": "test@company.com",
                        "channel": "#incidents",
                        "message": "What caused the payment service issues this morning?",
                        "thread_ts": "1642261200.123456"
                    }
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/ai/integrations/slack",
                    json=slack_request,
                    headers={"X-Customer-ID": self.test_customer}
                )
                
                assert response.status_code == 200, f"Slack integration failed: {response.text}"
                result = response.json()
                
                # Verify Slack response structure
                assert "response_message" in result
                assert "response_type" in result
                assert "thread_ts" in result
                assert "attachments" in result
                
                # Check response type
                assert result["response_type"] in ["analysis_summary", "query_result", "investigation_update", "help"]
                
                # Check response message
                assert isinstance(result["response_message"], str)
                assert len(result["response_message"]) > 0
                
                # Check attachments if present
                attachments = result["attachments"]
                assert isinstance(attachments, list)
                if attachments:
                    attachment = attachments[0]
                    assert "title" in attachment
                    assert "text" in attachment or "fields" in attachment
                
                print("✅ Slack integration successful")
                self.test_results["slack_integration"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Slack integration failed: {str(e)}")
                self.test_results["slack_integration"] = f"FAIL: {str(e)}"
                return False
    
    async def test_incident_learning(self):
        """Test incident data submission for ML model training"""
        print("🔄 Testing incident learning...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                learning_request = {
                    "incident_data": {
                        "incident_id": self.test_incident_id or "INC-M6-TEST-001",
                        "root_cause": "database_connection_exhaustion",
                        "resolution_actions": [
                            "Increased connection pool size from 50 to 100",
                            "Optimized slow queries identified in analysis"
                        ],
                        "resolution_time_minutes": 15,
                        "effectiveness_score": 0.92,
                        "symptoms": [
                            "High error rates",
                            "Connection timeouts",
                            "Customer complaints"
                        ],
                        "services_affected": ["payment-api", "user-service"]
                    },
                    "feedback": {
                        "rca_accuracy": 0.85,
                        "recommendation_usefulness": 0.90,
                        "analyst_notes": "RCA correctly identified database issue, recommendations were accurate and effective"
                    }
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/ai/learn/incident",
                    json=learning_request,
                    headers={"X-Customer-ID": self.test_customer}
                )
                
                assert response.status_code == 200, f"Incident learning failed: {response.text}"
                result = response.json()
                
                # Verify learning response
                assert "learning_id" in result
                assert "status" in result
                assert "model_update_queued" in result
                assert "knowledge_base_updated" in result
                assert result["status"] in ["accepted", "processed", "queued"]
                assert isinstance(result["model_update_queued"], bool)
                assert isinstance(result["knowledge_base_updated"], bool)
                
                print("✅ Incident learning successful")
                self.test_results["incident_learning"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Incident learning failed: {str(e)}")
                self.test_results["incident_learning"] = f"FAIL: {str(e)}"
                return False
    
    async def test_event_correlation(self):
        """Test event correlation analysis"""
        print("🔄 Testing event correlation...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                correlation_request = {
                    "events": [
                        {
                            "timestamp": (datetime.now() - timedelta(minutes=5)).isoformat(),
                            "service": "payment-api",
                            "event_type": "error_rate_spike",
                            "severity": "high",
                            "attributes": {"error_rate": 0.15, "affected_endpoints": ["/payment/process"]}
                        },
                        {
                            "timestamp": (datetime.now() - timedelta(minutes=7)).isoformat(),
                            "service": "database-service",
                            "event_type": "connection_pool_high",
                            "severity": "medium",
                            "attributes": {"pool_utilization": 0.95, "active_connections": 48}
                        }
                    ],
                    "correlation_window": "10m",
                    "confidence_threshold": 0.6
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/ai/correlate",
                    json=correlation_request,
                    headers={"X-Customer-ID": self.test_customer}
                )
                
                assert response.status_code == 200, f"Event correlation failed: {response.text}"
                result = response.json()
                
                # Verify correlation response
                assert "correlation_id" in result
                assert "correlations" in result
                assert "analysis_summary" in result
                assert isinstance(result["correlations"], list)
                
                # Check correlation structure if present
                if result["correlations"]:
                    correlation = result["correlations"][0]
                    assert "correlation_type" in correlation
                    assert "confidence" in correlation
                    assert "events_involved" in correlation
                    assert "causal_relationship" in correlation
                    assert "description" in correlation
                    
                    # Validate correlation confidence
                    assert isinstance(correlation["confidence"], float)
                    assert 0.0 <= correlation["confidence"] <= 1.0
                    
                    # Check correlation type
                    assert correlation["correlation_type"] in ["temporal", "causal", "dependency", "pattern"]
                    
                    # Check events involved
                    assert isinstance(correlation["events_involved"], list)
                    assert len(correlation["events_involved"]) >= 2
                
                print("✅ Event correlation successful")
                self.test_results["event_correlation"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Event correlation failed: {str(e)}")
                self.test_results["event_correlation"] = f"FAIL: {str(e)}"
                return False
    
    async def test_baseline_patterns(self):
        """Test learned baselines and patterns"""
        print("🔄 Testing baseline patterns...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/v1/ai/baselines",
                    headers={"X-Customer-ID": self.test_customer},
                    params={
                        "services": "payment-api,user-service",
                        "metric_types": "performance,business,security"
                    }
                )
                
                assert response.status_code == 200, f"Baseline patterns failed: {response.text}"
                result = response.json()
                
                # Verify baselines response structure
                assert "baselines" in result
                assert "learning_status" in result
                assert "last_updated" in result
                assert isinstance(result["baselines"], dict)
                
                # Check baseline structure if present
                if result["baselines"]:
                    for service, baselines in result["baselines"].items():
                        assert isinstance(baselines, dict)
                        if baselines:
                            for metric, baseline in baselines.items():
                                assert "baseline_value" in baseline
                                assert "variance" in baseline
                                assert "confidence" in baseline
                                assert "last_calculated" in baseline
                                assert "data_points" in baseline
                                
                                # Validate baseline confidence
                                assert isinstance(baseline["confidence"], float)
                                assert 0.0 <= baseline["confidence"] <= 1.0
                                assert isinstance(baseline["data_points"], int)
                
                # Check learning status
                learning_status = result["learning_status"]
                assert "models_trained" in learning_status
                assert "training_data_points" in learning_status
                assert "accuracy_score" in learning_status
                assert isinstance(learning_status["models_trained"], int)
                assert isinstance(learning_status["training_data_points"], int)
                
                print("✅ Baseline patterns successful")
                self.test_results["baseline_patterns"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Baseline patterns failed: {str(e)}")
                self.test_results["baseline_patterns"] = f"FAIL: {str(e)}"
                return False
    
    async def test_query_history(self):
        """Test query history and refinements"""
        print("🔄 Testing query history...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Skip if no query ID
                if not self.test_query_id:
                    print("⚠️ No query ID available for history testing")
                    self.test_results["query_history"] = "SKIP: No query ID"
                    return True
                
                response = await client.get(
                    f"{self.base_url}/v1/ai/query/{self.test_query_id}/history",
                    headers={"X-Customer-ID": self.test_customer}
                )
                
                assert response.status_code == 200, f"Query history failed: {response.text}"
                result = response.json()
                
                # Verify query history response
                assert "query_id" in result
                assert "original_question" in result
                assert "refinements" in result
                assert "performance_metrics" in result
                assert isinstance(result["refinements"], list)
                
                # Check refinement structure if present
                if result["refinements"]:
                    refinement = result["refinements"][0]
                    assert "timestamp" in refinement
                    assert "refined_question" in refinement
                    assert "sql_query" in refinement
                    assert "execution_time_ms" in refinement
                    assert "result_count" in refinement
                
                # Check performance metrics
                perf = result["performance_metrics"]
                assert "total_executions" in perf
                assert "average_execution_time_ms" in perf
                assert "success_rate" in perf
                assert isinstance(perf["success_rate"], float)
                assert 0.0 <= perf["success_rate"] <= 1.0
                
                print("✅ Query history successful")
                self.test_results["query_history"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Query history failed: {str(e)}")
                self.test_results["query_history"] = f"FAIL: {str(e)}"
                return False
    
    async def test_incident_analysis_retrieval(self):
        """Test retrieving existing RCA analysis"""
        print("🔄 Testing incident analysis retrieval...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Skip if no incident ID
                if not self.test_incident_id:
                    print("⚠️ No incident ID available for analysis retrieval testing")
                    self.test_results["incident_analysis_retrieval"] = "SKIP: No incident ID"
                    return True
                
                response = await client.get(
                    f"{self.base_url}/v1/ai/incidents/{self.test_incident_id}/analysis",
                    headers={"X-Customer-ID": self.test_customer}
                )
                
                assert response.status_code == 200, f"Incident analysis retrieval failed: {response.text}"
                result = response.json()
                
                # Verify analysis retrieval response (should match analyze-incident response)
                assert "analysis_id" in result
                assert "incident_id" in result
                assert "root_cause_analysis" in result
                assert "business_impact" in result
                assert "recommendations" in result
                assert result["incident_id"] == self.test_incident_id
                
                print("✅ Incident analysis retrieval successful")
                self.test_results["incident_analysis_retrieval"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Incident analysis retrieval failed: {str(e)}")
                self.test_results["incident_analysis_retrieval"] = f"FAIL: {str(e)}"
                return False
    
    async def run_all_tests(self):
        """Run all M6 tests"""
        print("\n🚀 Starting M6 Individual Test Suite...")
        print("📝 Testing: AI Assistant, NLQ, RCA, Anomaly Detection, Investigation Assistant, Knowledge Management")
        
        # Run tests in logical order
        tests = [
            self.test_ai_health,
            self.test_natural_language_query,
            self.test_query_suggestions,
            self.test_query_history,
            self.test_incident_analysis,
            self.test_incident_analysis_retrieval,
            self.test_symptom_analysis,
            self.test_anomaly_detection,
            self.test_failure_prediction,
            self.test_baseline_patterns,
            self.test_investigation_assistant,
            self.test_investigation_evidence,
            self.test_investigation_recommendations,
            self.test_knowledge_search,
            self.test_knowledge_solutions,
            self.test_business_impact,
            self.test_business_metrics,
            self.test_operational_insights,
            self.test_event_correlation,
            self.test_slack_integration,
            self.test_incident_learning
        ]
        
        # Run tests sequentially since some depend on previous ones
        for test_func in tests:
            try:
                await test_func()
            except Exception as e:
                print(f"❌ Test {test_func.__name__} failed with exception: {str(e)}")
                if test_func.__name__.replace("test_", "") not in self.test_results:
                    self.test_results[test_func.__name__.replace("test_", "")] = f"FAIL: {str(e)}"
        
        # Summary
        print("\n📊 M6 Test Results Summary:")
        passed = sum(1 for result in self.test_results.values() if result == "PASS" or result.startswith("SKIP"))
        total = len(self.test_results)
        
        for test_name, result in self.test_results.items():
            if result == "PASS":
                status = "✅"
            elif result.startswith("SKIP"):
                status = "⚠️"
            else:
                status = "❌"
            print(f"  {status} {test_name}: {result}")
        
        print(f"\n🎯 M6 Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("✅ M6 AI Assistant & RCA: ALL TESTS PASSED")
            return True
        else:
            print("❌ M6 AI Assistant & RCA: SOME TESTS FAILED")
            return False

if __name__ == "__main__":
    test_suite = M6TestSuite()
    success = asyncio.run(test_suite.run_all_tests())
    exit(0 if success else 1)