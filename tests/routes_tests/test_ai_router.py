#!/usr/bin/env python3
"""
Comprehensive AI Router Test Suite
Tests all AI router endpoints and validates API responses based on actual router implementation
"""

import asyncio
import json
import sys
import os
import time
from datetime import datetime, timezone, timedelta

# Add project paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'apps', 'api')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from base_test import BaseTestSuite

class AIRouterTestSuite(BaseTestSuite):
    """Comprehensive test suite for AI router endpoints"""

    def __init__(self):
        super().__init__("AIRouter")

    async def test_natural_language_query_endpoint(self):
        """Test POST /v1/ai/query - Natural language query processing"""
        print("\n🧪 Testing Natural Language Query Endpoint...")

        try:
            # Valid NL query request
            nl_request = {
                "question": "Show me all error logs from the last 24 hours",
                "context": {
                    "time_range": "24h",
                    "priority": "high"
                },
                "max_results": 50
            }

            # Send NL query request
            response = await self.make_authenticated_request(
                "POST",
                "/v1/ai/query",
                json=nl_request
            )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate NLQueryResult structure
            required_fields = [
                "query_id", "original_question", "generated_sql", 
                "explanation", "results", "suggestions", 
                "confidence_score", "execution_time_ms", "customer_id"
            ]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert isinstance(response_data["query_id"], str), "Query ID should be a string"
            assert isinstance(response_data["results"], dict), "Results should be a dictionary"
            assert isinstance(response_data["suggestions"], list), "Suggestions should be a list"
            assert isinstance(response_data["confidence_score"], (int, float)), "Confidence score should be numeric"

            print(f"   ✅ Natural language query successful: {response_data['original_question']}")
            self.test_results["natural_language_query"] = "PASS"

        except Exception as e:
            print(f"   ❌ Natural language query test error: {e}")
            self.test_results["natural_language_query"] = f"ERROR: {e}"

    async def test_query_history_endpoint(self):
        """Test GET /v1/ai/query/history - Query history retrieval"""
        print("\n🧪 Testing Query History Endpoint...")

        try:
            # Get query history
            response = await self.make_authenticated_request(
                "GET",
                "/v1/ai/query/history?limit=10"
            )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate query history response structure
            required_fields = ["history", "total", "user_id", "customer_id"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert isinstance(response_data["history"], list), "History should be a list"
            assert isinstance(response_data["total"], int), "Total should be an integer"

            print(f"   ✅ Query history retrieved: {response_data['total']} queries")
            self.test_results["query_history"] = "PASS"

        except Exception as e:
            print(f"   ❌ Query history test error: {e}")
            self.test_results["query_history"] = f"ERROR: {e}"

    async def test_incident_investigation_workflow(self):
        """Test investigation workflow: start -> get status -> analyze"""
        print("\n🧪 Testing Incident Investigation Workflow...")

        try:
            # 1. Start investigation
            investigation_request = {
                "title": f"Test Investigation {self.test_id}",
                "description": "Automated test investigation for service degradation",
                "incident_data": {
                    "service": "payment-api",
                    "symptoms": ["high latency", "connection errors"],
                    "start_time": datetime.utcnow().isoformat(),
                    "severity": "high"
                },
                "context": {
                    "recent_deployment": True,
                    "traffic_spike": False
                }
            }

            start_response = await self.make_authenticated_request(
                "POST",
                "/v1/ai/investigate",
                json=investigation_request
            )

            assert start_response.status_code == 200, f"Expected 200, got {start_response.status_code}: {start_response.text}"
            start_data = start_response.json()

            # Validate investigation start response
            required_fields = ["investigation_id", "title", "status", "hypothesis", "next_steps", "started_at", "customer_id"]
            for field in required_fields:
                assert field in start_data, f"Missing required field: {field}"

            investigation_id = start_data["investigation_id"]
            assert start_data["status"] == "running", "Investigation should start in running status"

            # 2. Get investigation status
            status_response = await self.make_authenticated_request(
                "GET",
                f"/v1/ai/investigate/{investigation_id}"
            )

            assert status_response.status_code == 200, f"Expected 200, got {status_response.status_code}: {status_response.text}"
            status_data = status_response.json()

            # Validate investigation status response
            assert status_data["investigation_id"] == investigation_id
            assert "title" in status_data
            assert "status" in status_data

            # 3. Analyze incident
            analysis_request = {
                "incident": {
                    "id": f"incident-{self.test_id}",
                    "description": "Payment API performance degradation",
                    "symptoms": ["high response time", "database connection issues"],
                    "affected_services": ["payment-api", "user-service"],
                    "start_time": datetime.utcnow().isoformat(),
                    "duration_minutes": 45
                },
                "context": {
                    "business_context": {
                        "revenue_per_hour": 15000
                    },
                    "recent_deployment": True
                }
            }

            analysis_response = await self.make_authenticated_request(
                "POST",
                "/v1/ai/analyze",
                json=analysis_request
            )

            assert analysis_response.status_code == 200, f"Expected 200, got {analysis_response.status_code}: {analysis_response.text}"
            analysis_data = analysis_response.json()

            # Validate analysis response
            analysis_fields = [
                "analysis_id", "incident_id", "primary_cause", 
                "contributing_factors", "timeline", "business_impact", 
                "recommendations", "similar_incidents", "customer_id"
            ]
            for field in analysis_fields:
                assert field in analysis_data, f"Missing analysis field: {field}"

            assert isinstance(analysis_data["contributing_factors"], list), "Contributing factors should be a list"
            assert isinstance(analysis_data["recommendations"], list), "Recommendations should be a list"
            assert isinstance(analysis_data["timeline"], list), "Timeline should be a list"

            print(f"   ✅ Investigation workflow completed: {investigation_id}")
            self.test_results["investigation_workflow"] = "PASS"

        except Exception as e:
            print(f"   ❌ Investigation workflow test error: {e}")
            self.test_results["investigation_workflow"] = f"ERROR: {e}"

    async def test_ml_baselines_crud(self):
        """Test ML baselines CRUD operations"""
        print("\n🧪 Testing ML Baselines CRUD Operations...")

        try:
            # 1. Save baseline
            baseline_request = {
                "model_id": f"test-model-{self.test_id}",
                "service_name": "payment-api",
                "baseline_type": "anomaly",  # Must be one of: anomaly, pattern, threshold, seasonal
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

            save_response = await self.make_authenticated_request(
                "POST",
                "/v1/ai/baselines",
                json=baseline_request
            )

            assert save_response.status_code == 200, f"Expected 200, got {save_response.status_code}: {save_response.text}"
            save_data = save_response.json()

            # Validate baseline save response
            assert save_data["status"] == "saved"
            assert "model_id" in save_data
            assert save_data["model_id"] == f"test-model-{self.test_id}"

            # 2. List baselines
            list_response = await self.make_authenticated_request(
                "GET",
                "/v1/ai/baselines?service_name=payment-api"
            )

            assert list_response.status_code == 200, f"Expected 200, got {list_response.status_code}: {list_response.text}"
            list_data = list_response.json()

            # Validate baselines list response
            required_fields = ["baselines", "total", "filters", "customer_id"]
            for field in required_fields:
                assert field in list_data, f"Missing required field: {field}"

            assert isinstance(list_data["baselines"], list), "Baselines should be a list"
            assert list_data["filters"]["service_name"] == "payment-api"

            print(f"   ✅ ML baselines CRUD operations successful: {list_data['total']} baselines")
            self.test_results["ml_baselines_crud"] = "PASS"

        except Exception as e:
            print(f"   ❌ ML baselines CRUD test error: {e}")
            self.test_results["ml_baselines_crud"] = f"ERROR: {e}"

    async def test_anomaly_detection(self):
        """Test POST /v1/ai/anomalies/detect - Anomaly detection"""
        print("\n🧪 Testing Anomaly Detection...")

        try:
            # Valid anomaly detection request
            anomaly_request = {
                "time_range": "4h",
                "severity_filter": ["high", "medium"],
                "category_filter": ["performance"],
                "service_filter": ["payment-api", "user-service"]
            }

            response = await self.make_authenticated_request(
                "POST",
                "/v1/ai/anomalies/detect",
                json=anomaly_request
            )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate anomaly detection response structure
            required_fields = ["anomalies", "summary", "time_range", "detection_timestamp", "customer_id"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert isinstance(response_data["anomalies"], list), "Anomalies should be a list"
            assert isinstance(response_data["summary"], dict), "Summary should be a dictionary"
            assert response_data["time_range"] == "4h"

            # Validate anomaly structure if anomalies exist
            if response_data["anomalies"]:
                anomaly = response_data["anomalies"][0]
                anomaly_fields = ["id", "service_name", "anomaly_type", "severity", "score", "detected_at"]
                for field in anomaly_fields:
                    assert field in anomaly, f"Missing anomaly field: {field}"

            print(f"   ✅ Anomaly detection successful: {len(response_data['anomalies'])} anomalies found")
            self.test_results["anomaly_detection"] = "PASS"

        except Exception as e:
            print(f"   ❌ Anomaly detection test error: {e}")
            self.test_results["anomaly_detection"] = f"ERROR: {e}"

    async def test_knowledge_base_operations(self):
        """Test knowledge base search and solution addition"""
        print("\n🧪 Testing Knowledge Base Operations...")

        try:
            # 1. Add solution to knowledge base
            solution_request = {
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

            add_response = await self.make_authenticated_request(
                "POST",
                "/v1/ai/knowledge/solutions",
                json=solution_request
            )

            assert add_response.status_code == 200, f"Expected 200, got {add_response.status_code}: {add_response.text}"
            add_data = add_response.json()

            # Validate solution addition response
            assert add_data["status"] == "added"
            assert "solution_id" in add_data
            assert "message" in add_data

            # 2. Search knowledge base
            search_request = {
                "symptoms": "connection timeout, slow queries",
                "services": "payment-api",
                "category": "database"
            }

            search_response = await self.make_authenticated_request(
                "POST",
                "/v1/ai/knowledge/search",
                json=search_request
            )

            assert search_response.status_code == 200, f"Expected 200, got {search_response.status_code}: {search_response.text}"
            search_data = search_response.json()

            # Validate knowledge base search response
            required_fields = ["solutions", "total_found", "search_terms", "knowledge_base_stats", "customer_id"]
            for field in required_fields:
                assert field in search_data, f"Missing required field: {field}"

            assert isinstance(search_data["solutions"], list), "Solutions should be a list"
            assert isinstance(search_data["search_terms"], list), "Search terms should be a list"

            # Validate solution structure if solutions exist
            if search_data["solutions"]:
                solution = search_data["solutions"][0]
                solution_fields = ["solution_id", "title", "description", "confidence", "tags"]
                for field in solution_fields:
                    assert field in solution, f"Missing solution field: {field}"

            print(f"   ✅ Knowledge base operations successful: {search_data['total_found']} solutions found")
            self.test_results["knowledge_base_operations"] = "PASS"

        except Exception as e:
            print(f"   ❌ Knowledge base operations test error: {e}")
            self.test_results["knowledge_base_operations"] = f"ERROR: {e}"

    async def test_operational_insights_and_correlation(self):
        """Test operational insights and event correlation"""
        print("\n🧪 Testing Operational Insights and Event Correlation...")

        try:
            # 1. Get operational insights
            insights_response = await self.make_authenticated_request(
                "GET",
                "/v1/ai/insights"
            )

            assert insights_response.status_code == 200, f"Expected 200, got {insights_response.status_code}: {insights_response.text}"
            insights_data = insights_response.json()

            # Validate insights response structure
            required_fields = ["insights", "statistics", "recommendations", "generated_at", "customer_id"]
            for field in required_fields:
                assert field in insights_data, f"Missing required field: {field}"

            assert isinstance(insights_data["insights"], list), "Insights should be a list"
            assert isinstance(insights_data["recommendations"], list), "Recommendations should be a list"

            # 2. Test event correlation
            correlation_request = {
                "events": [
                    {
                        "id": "event1",
                        "timestamp": datetime.utcnow().isoformat(),
                        "service": "payment-api",
                        "severity": "high",
                        "type": "error",
                        "message": "Database connection failed"
                    },
                    {
                        "id": "event2", 
                        "timestamp": (datetime.utcnow() + timedelta(minutes=2)).isoformat(),
                        "service": "payment-api",
                        "severity": "high",
                        "type": "error",
                        "message": "Service timeout"
                    },
                    {
                        "id": "event3",
                        "timestamp": (datetime.utcnow() + timedelta(minutes=5)).isoformat(),
                        "service": "user-service",
                        "severity": "medium",
                        "type": "warning",
                        "message": "Performance degradation"
                    }
                ],
                "correlation_window": "10m",
                "confidence_threshold": 0.6
            }

            correlation_response = await self.make_authenticated_request(
                "POST",
                "/v1/ai/correlate",
                json=correlation_request
            )

            assert correlation_response.status_code == 200, f"Expected 200, got {correlation_response.status_code}: {correlation_response.text}"
            correlation_data = correlation_response.json()

            # Validate correlation response structure
            correlation_fields = [
                "correlations", "total_events", "correlation_window", 
                "confidence_threshold", "analysis_timestamp", "customer_id"
            ]
            for field in correlation_fields:
                assert field in correlation_data, f"Missing correlation field: {field}"

            assert isinstance(correlation_data["correlations"], list), "Correlations should be a list"
            assert correlation_data["total_events"] == 3
            assert correlation_data["correlation_window"] == "10m"

            print(f"   ✅ Insights and correlation successful: {len(correlation_data['correlations'])} correlations found")
            self.test_results["insights_and_correlation"] = "PASS"

        except Exception as e:
            print(f"   ❌ Insights and correlation test error: {e}")
            self.test_results["insights_and_correlation"] = f"ERROR: {e}"

    async def test_advanced_ai_endpoints(self):
        """Test advanced AI endpoints: predict, optimize, models"""
        print("\n🧪 Testing Advanced AI Endpoints...")

        try:
            # 1. Test incident prediction
            predict_response = await self.make_authenticated_request(
                "POST",
                "/v1/ai/predict?time_horizon=48h&confidence_threshold=0.8"
            )

            assert predict_response.status_code == 200, f"Expected 200, got {predict_response.status_code}: {predict_response.text}"
            predict_data = predict_response.json()

            # Validate prediction response
            predict_fields = ["predictions", "time_horizon", "confidence_threshold", "total_predictions", "generated_at", "customer_id"]
            for field in predict_fields:
                assert field in predict_data, f"Missing prediction field: {field}"

            assert isinstance(predict_data["predictions"], list), "Predictions should be a list"
            assert predict_data["time_horizon"] == "48h"
            assert predict_data["confidence_threshold"] == 0.8

            # 2. Test optimization recommendations
            optimize_response = await self.make_authenticated_request(
                "POST",
                "/v1/ai/optimize?service_name=payment-api&optimization_type=performance"
            )

            assert optimize_response.status_code == 200, f"Expected 200, got {optimize_response.status_code}: {optimize_response.text}"
            optimize_data = optimize_response.json()

            # Validate optimization response
            assert "optimization_plan" in optimize_data
            assert "customer_id" in optimize_data
            
            optimization_plan = optimize_data["optimization_plan"]
            plan_fields = ["service_name", "optimization_type", "optimizations", "generated_at"]
            for field in plan_fields:
                assert field in optimization_plan, f"Missing optimization plan field: {field}"

            # 3. Test AI models listing
            models_response = await self.make_authenticated_request(
                "GET",
                "/v1/ai/models"
            )

            assert models_response.status_code == 200, f"Expected 200, got {models_response.status_code}: {models_response.text}"
            models_data = models_response.json()

            # Validate models response
            models_fields = ["models", "total", "active_models", "customer_id"]
            for field in models_fields:
                assert field in models_data, f"Missing models field: {field}"

            assert isinstance(models_data["models"], list), "Models should be a list"
            assert isinstance(models_data["total"], int), "Total should be an integer"

            # Validate model structure if models exist
            if models_data["models"]:
                model = models_data["models"][0]
                model_fields = ["model_id", "name", "type", "status", "accuracy"]
                for field in model_fields:
                    assert field in model, f"Missing model field: {field}"

            print(f"   ✅ Advanced AI endpoints successful: {models_data['total']} models, {predict_data['total_predictions']} predictions")
            self.test_results["advanced_ai_endpoints"] = "PASS"

        except Exception as e:
            print(f"   ❌ Advanced AI endpoints test error: {e}")
            self.test_results["advanced_ai_endpoints"] = f"ERROR: {e}"

    async def test_query_feedback_system(self):
        """Test query feedback submission"""
        print("\n🧪 Testing Query Feedback System...")

        try:
            # First, create a query to get a query_id
            nl_request = {
                "question": "What are the most common errors today?",
                "context": {},
                "max_results": 10
            }

            query_response = await self.make_authenticated_request(
                "POST",
                "/v1/ai/query",
                json=nl_request
            )

            assert query_response.status_code == 200, f"Expected 200, got {query_response.status_code}: {query_response.text}"
            query_data = query_response.json()
            query_id = query_data["query_id"]

            # Submit feedback for the query
            feedback_request = {
                "query_id": query_id,
                "feedback_score": 1,
                "feedback_notes": "Very helpful query results"
            }

            feedback_response = await self.make_authenticated_request(
                "POST",
                "/v1/ai/query/feedback",
                json=feedback_request
            )

            assert feedback_response.status_code == 200, f"Expected 200, got {feedback_response.status_code}: {feedback_response.text}"
            feedback_data = feedback_response.json()

            # Validate feedback response
            assert "success" in feedback_data
            assert "message" in feedback_data
            assert feedback_data["success"] == True

            print(f"   ✅ Query feedback system successful: {feedback_data['message']}")
            self.test_results["query_feedback"] = "PASS"

        except Exception as e:
            print(f"   ❌ Query feedback test error: {e}")
            self.test_results["query_feedback"] = f"ERROR: {e}"

    async def test_ai_health_check(self):
        """Test GET /v1/ai/health - AI service health check"""
        print("\n🧪 Testing AI Health Check...")

        try:
            response = await self.make_authenticated_request(
                "GET",
                "/v1/ai/health"
            )

            # Health check should always return 200, even if there are issues
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate health check response structure
            required_fields = ["status", "message"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert response_data["status"] in ["healthy", "error"], "Status should be 'healthy' or 'error'"

            # If healthy, check for features list
            if response_data["status"] == "healthy":
                assert "features" in response_data, "Healthy response should include features"
                assert isinstance(response_data["features"], list), "Features should be a list"

            print(f"   ✅ AI health check successful: {response_data['status']} - {response_data['message']}")
            self.test_results["ai_health_check"] = "PASS"

        except Exception as e:
            print(f"   ❌ AI health check test error: {e}")
            self.test_results["ai_health_check"] = f"ERROR: {e}"

    async def test_error_handling(self):
        """Test error handling for various invalid scenarios"""
        print("\n🧪 Testing Error Handling...")

        try:
            # Test empty NL query
            empty_response = await self.make_authenticated_request(
                "POST",
                "/v1/ai/query",
                json={}
            )
            assert empty_response.status_code == 422, "Empty query should return validation error"

            # Test invalid investigation ID
            invalid_investigation_response = await self.make_authenticated_request(
                "GET",
                "/v1/ai/investigate/invalid-id"
            )
            assert invalid_investigation_response.status_code in [400, 404], "Invalid investigation ID should return error"

            # Test invalid baseline data
            invalid_baseline_response = await self.make_authenticated_request(
                "POST",
                "/v1/ai/baselines",
                json={"invalid": "data"}
            )
            assert invalid_baseline_response.status_code == 422, "Invalid baseline data should return validation error"

            # Test malformed correlation request
            malformed_correlation_response = await self.make_authenticated_request(
                "POST",
                "/v1/ai/correlate",
                json={"events": "not-a-list"}
            )
            assert malformed_correlation_response.status_code == 422, "Malformed correlation request should return validation error"

            print(f"   ✅ Error handling working correctly")
            self.test_results["error_handling"] = "PASS"

        except Exception as e:
            print(f"   ❌ Error handling test error: {e}")
            self.test_results["error_handling"] = f"ERROR: {e}"

    async def test_multi_tenant_isolation(self):
        """Test multi-tenant isolation across AI endpoints"""
        print("\n🧪 Testing Multi-Tenant Isolation...")

        try:
            # Create a test user and tenant for this specific test
            test_user_id, test_tenant_id = await self.create_test_user_and_tenant(
                roles=['tenant_admin'],
                user_name_suffix='AIIsolation'
            )

            # Create a baseline for current tenant
            baseline_request = {
                "model_id": f"isolation-test-{self.test_id}",
                "service_name": "test-service",
                "baseline_type": "threshold",  # Must be one of: anomaly, pattern, threshold, seasonal
                "baseline_data": {"test": "data"},
                "training_metrics": {}
            }

            baseline_response = await self.make_authenticated_request(
                "POST",
                "/v1/ai/baselines",
                json=baseline_request
            )

            assert baseline_response.status_code == 200, f"Expected 200, got {baseline_response.status_code}: {baseline_response.text}"

            # Try to access with different tenant (should be blocked by middleware)
            different_tenant_id = f"different-tenant-{self.test_id}"
            
            # Make request with different customer ID header to test tenant isolation
            isolated_response = await self.make_authenticated_request(
                "GET",
                "/v1/ai/baselines",
                headers={
                    "X-Customer-ID": different_tenant_id  # Override tenant ID
                }
            )

            # Should return 403 due to tenant isolation (middleware blocks access)
            assert isolated_response.status_code == 403, f"Cross-tenant access should be blocked, got {isolated_response.status_code}: {isolated_response.text}"

            print(f"   ✅ Multi-tenant isolation working correctly")
            self.test_results["multi_tenant_isolation"] = "PASS"

        except Exception as e:
            print(f"   ❌ Multi-tenant isolation test error: {e}")
            self.test_results["multi_tenant_isolation"] = f"ERROR: {e}"

    async def run_all_tests(self):
        """Execute all AI router tests"""
        print(f"\n🚀 Starting AI Router Test Suite (Test ID: {self.test_id})")
        print("=" * 60)

        # Create test user and tenant for authentication
        try:
            await self.create_test_user_and_tenant(['tenant_admin'])
            await self.setup_auth()
        except Exception as e:
            print(f"❌ Failed to setup test environment: {e}")
            return

        # Run all tests
        test_methods = [
            self.test_natural_language_query_endpoint,
            self.test_query_history_endpoint,
            self.test_incident_investigation_workflow,
            self.test_ml_baselines_crud,
            self.test_anomaly_detection,
            self.test_knowledge_base_operations,
            self.test_operational_insights_and_correlation,
            self.test_advanced_ai_endpoints,
            self.test_query_feedback_system,
            self.test_ai_health_check,
            self.test_error_handling,
            self.test_multi_tenant_isolation
        ]

        for test_method in test_methods:
            try:
                await test_method()
                await asyncio.sleep(0.1)  # Brief pause between tests
            except Exception as e:
                test_name = test_method.__name__
                print(f"   ❌ {test_name} failed: {e}")
                self.test_results[test_name] = f"ERROR: {e}"

        # Cleanup
        await self.cleanup_test_data()

        # Print results summary
        self.print_test_summary()

    def print_test_summary(self):
        """Print comprehensive test results summary"""
        print("\n" + "=" * 60)
        print("🏆 AI ROUTER TEST SUMMARY")
        print("=" * 60)

        passed = 0
        failed = 0

        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result == "PASS" else "❌ FAIL"
            print(f"{status:8} | {test_name:<40} | {result}")
            
            if result == "PASS":
                passed += 1
            else:
                failed += 1

        print("=" * 60)
        print(f"📊 TOTAL: {passed + failed} tests | ✅ PASSED: {passed} | ❌ FAILED: {failed}")
        
        if failed == 0:
            print("🎉 ALL AI ROUTER TESTS PASSED!")
        else:
            print(f"⚠️  {failed} test(s) failed - review errors above")

        print("=" * 60)

async def run_ai_router_tests():
    """Main test runner function for integration with run_route_tests.py"""
    suite = AIRouterTestSuite()
    await suite.run_all_tests()
    
    # Return True if all tests passed, False otherwise
    passed_tests = sum(1 for result in suite.test_results.values() if result == "PASS")
    total_tests = len(suite.test_results)
    
    return passed_tests == total_tests

async def main():
    """Main test runner"""
    suite = AIRouterTestSuite()
    await suite.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())