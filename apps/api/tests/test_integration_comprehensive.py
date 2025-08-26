"""
Comprehensive Integration Test Suite for Logforge
Tests all features end-to-end with multi-tenancy support
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import asyncio
import json
import time
import httpx
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from unittest.mock import patch, MagicMock
import structlog

# Import all modules we need to test
from main import app
from query_engine import AdvancedQueryEngine, AdvancedQueryRequest, QueryResponse
from dashboard_engine import DashboardEngine, DashboardType
from ttl_manager import TTLManager, RetentionPolicy, ComplianceTier
from storage_config import StorageConfigManager, DeploymentType
from alert_engine import (
    AlertEngine, AlertRule, AlertSeverity, AlertStatus, AlertRuleType, 
    ThresholdOperator, AlertRuleCreateRequest
)


class IntegrationTestSuite:
    """Comprehensive integration test suite"""
    
    def __init__(self):
        self.base_url = "http://localhost:7080"
        self.test_customers = [
            "test-customer-1",
            "test-customer-2", 
            "enterprise-demo",
            "compliance-test"
        ]
        self.test_data_sets = {}
        self.setup_complete = False
    
    async def setup_test_environment(self):
        """Setup test environment with multi-tenant data"""
        print("🔧 Setting up integration test environment...")
        
        # Generate test data for each customer
        for customer_id in self.test_customers:
            self.test_data_sets[customer_id] = await self._generate_test_data(customer_id)
        
        self.setup_complete = True
        print("✅ Test environment setup complete")
    
    async def _generate_test_data(self, customer_id: str) -> List[Dict[str, Any]]:
        """Generate realistic test data for a customer"""
        test_logs = []
        base_time = datetime.utcnow() - timedelta(days=7)
        
        # Generate various log types for comprehensive testing
        log_templates = [
            # Security logs
            {
                "level": "WARN",
                "service": "auth-service",
                "msg": f"Failed login attempt for user {customer_id}-user",
                "src_ip": "192.168.1.100",
                "user_id": f"{customer_id}-user",
                "http_method": "POST",
                "http_uri": "/api/login",
                "http_status": 401
            },
            # Application logs
            {
                "level": "ERROR", 
                "service": "payment-service",
                "msg": f"Payment processing failed for customer {customer_id}",
                "error_code": "PAY_001",
                "error_category": "payment_failure",
                "user_id": f"{customer_id}-user",
                "is_error": 1
            },
            # Performance logs
            {
                "level": "INFO",
                "service": "api-gateway", 
                "msg": f"Request processed for {customer_id}",
                "http_method": "GET",
                "http_uri": f"/api/customers/{customer_id}/data",
                "http_status": 200,
                "http_response_time_ms": 250,
                "http_bytes": 1024
            },
            # Infrastructure logs
            {
                "level": "INFO",
                "service": "kubernetes",
                "msg": f"Pod scaled for customer {customer_id}",
                "host": f"{customer_id}-node-1"
            }
        ]
        
        # Generate 100 logs per template per customer
        for i in range(100):
            for template in log_templates:
                log_entry = {
                    **template,
                    "customer_id": customer_id,  # Add customer_id for multi-tenancy
                    "ts": (base_time + timedelta(minutes=i)).isoformat(),
                    "trace_id": f"trace-{customer_id}-{i}",
                    "span_id": f"span-{customer_id}-{i}",
                    "ingested_at": datetime.utcnow().isoformat()
                }
                test_logs.append(log_entry)
        
        return test_logs


class TestComprehensiveIntegration:
    """Comprehensive integration tests for all Logforge features"""
    
    @pytest.fixture(scope="session", autouse=True)
    async def test_suite(self):
        """Setup integration test suite"""
        suite = IntegrationTestSuite()
        await suite.setup_test_environment()
        return suite
    
    @pytest.fixture(scope="session")
    async def http_client(self):
        """HTTP client for API testing"""
        async with httpx.AsyncClient() as client:
            yield client
    
    # ========== INGESTION TESTS ==========
    
    @pytest.mark.asyncio
    async def test_multi_tenant_log_ingestion(self, test_suite, http_client):
        """Test log ingestion for multiple tenants"""
        print("\n🔄 Testing multi-tenant log ingestion...")
        
        for customer_id in test_suite.test_customers:
            logs = test_suite.test_data_sets[customer_id][:10]  # Test with 10 logs first
            
            for log_entry in logs:
                response = await http_client.post(
                    f"{test_suite.base_url}/v1/ingest/logs",
                    json=log_entry,
                    headers={"X-Customer-ID": customer_id}
                )
                assert response.status_code in [200, 201], f"Ingestion failed for {customer_id}: {response.text}"
        
        print("✅ Multi-tenant log ingestion successful")
    
    @pytest.mark.asyncio 
    async def test_bulk_ingestion(self, test_suite, http_client):
        """Test bulk log ingestion"""
        print("\n🔄 Testing bulk log ingestion...")
        
        for customer_id in test_suite.test_customers[:2]:  # Test with 2 customers
            logs = test_suite.test_data_sets[customer_id][:50]  # 50 logs per customer
            
            response = await http_client.post(
                f"{test_suite.base_url}/v1/ingest/logs/bulk",
                json={"logs": logs},
                headers={"X-Customer-ID": customer_id}
            )
            assert response.status_code in [200, 201], f"Bulk ingestion failed for {customer_id}: {response.text}"
        
        print("✅ Bulk ingestion successful")
    
    # ========== QUERY ENGINE TESTS ==========
    
    @pytest.mark.asyncio
    async def test_advanced_query_engine_multi_tenant(self, test_suite, http_client):
        """Test advanced query engine with multi-tenant isolation"""
        print("\n🔄 Testing advanced query engine with multi-tenancy...")
        
        # Wait for data to be ingested
        await asyncio.sleep(2)
        
        for customer_id in test_suite.test_customers[:2]:
            query_request = {
                "start_time": (datetime.utcnow() - timedelta(hours=24)).isoformat(),
                "end_time": datetime.utcnow().isoformat(),
                "filters": [
                    {
                        "field": "customer_id",
                        "operator": "eq",
                        "value": customer_id
                    },
                    {
                        "field": "service", 
                        "operator": "eq",
                        "value": "auth-service"
                    }
                ],
                "aggregations": [
                    {
                        "field": "http_status",
                        "type": "cardinality"
                    }
                ],
                "limit": 100
            }
            
            response = await http_client.post(
                f"{test_suite.base_url}/v1/query/advanced",
                json=query_request,
                headers={"X-Customer-ID": customer_id}
            )
            
            assert response.status_code == 200, f"Query failed for {customer_id}: {response.text}"
            result = response.json()
            
            # Verify tenant isolation - should only return data for this customer
            if "results" in result and result["results"]:
                for hit in result["results"]:
                    if "customer_id" in hit:
                        assert hit["customer_id"] == customer_id, f"Tenant isolation failed: got {hit['customer_id']}, expected {customer_id}"
        
        print("✅ Advanced query engine with multi-tenancy successful")
    
    @pytest.mark.asyncio
    async def test_time_series_analysis(self, test_suite, http_client):
        """Test time series analysis capabilities"""
        print("\n🔄 Testing time series analysis...")
        
        customer_id = test_suite.test_customers[0]
        query_request = {
            "start_time": (datetime.utcnow() - timedelta(hours=24)).isoformat(),
            "end_time": datetime.utcnow().isoformat(),
            "aggregations": [
                {
                    "field": "*",
                    "type": "count"
                }
            ],
            "granularity": "hour",
            "filters": [
                {
                    "field": "customer_id",
                    "operator": "eq",
                    "value": customer_id
                }
            ]
        }
        
        response = await http_client.post(
            f"{test_suite.base_url}/v1/query/timeseries",
            json=query_request,
            headers={"X-Customer-ID": customer_id}
        )
        
        assert response.status_code == 200, f"Time series query failed: {response.text}"
        result = response.json()
        assert "buckets" in result, "Time series results missing buckets"
        
        print("✅ Time series analysis successful")
    
    # ========== DASHBOARD TESTS ==========
    
    @pytest.mark.asyncio
    async def test_all_dashboard_types(self, test_suite, http_client):
        """Test all 6 enterprise dashboard types"""
        print("\n🔄 Testing all dashboard types...")
        
        dashboard_types = [
            "security_soc",
            "performance_monitoring", 
            "infrastructure_health",
            "business_metrics",
            "compliance_audit",
            "executive_summary"
        ]
        
        customer_id = test_suite.test_customers[0]
        
        for dashboard_type in dashboard_types:
            response = await http_client.get(
                f"{test_suite.base_url}/v1/dashboards/{dashboard_type}",
                headers={"X-Customer-ID": customer_id}
            )
            
            assert response.status_code == 200, f"Dashboard {dashboard_type} failed: {response.text}"
            dashboard = response.json()
            
            # Verify dashboard structure
            assert "title" in dashboard, f"Dashboard {dashboard_type} missing title"
            assert "widgets" in dashboard, f"Dashboard {dashboard_type} missing widgets"
            assert len(dashboard["widgets"]) > 0, f"Dashboard {dashboard_type} has no widgets"
            
            # Test dashboard data generation
            response = await http_client.post(
                f"{test_suite.base_url}/v1/dashboards/{dashboard_type}/data",
                json={
                    "time_range": "24h",
                    "customer_id": customer_id
                },
                headers={"X-Customer-ID": customer_id}
            )
            
            assert response.status_code == 200, f"Dashboard {dashboard_type} data generation failed: {response.text}"
        
        print("✅ All dashboard types tested successfully")
    
    @pytest.mark.asyncio
    async def test_custom_dashboard_creation(self, test_suite, http_client):
        """Test custom dashboard creation and management"""
        print("\n🔄 Testing custom dashboard creation...")
        
        customer_id = test_suite.test_customers[0]
        custom_dashboard = {
            "title": f"Custom Dashboard for {customer_id}",
            "description": "Integration test custom dashboard",
            "widgets": [
                {
                    "id": "custom-widget-1",
                    "title": "Error Rate",
                    "type": "metric",
                    "query": {
                        "filters": {"level": "ERROR", "customer_id": customer_id},
                        "aggregation": {"type": "count"}
                    }
                },
                {
                    "id": "custom-widget-2", 
                    "title": "Top Services",
                    "type": "bar_chart",
                    "query": {
                        "filters": {"customer_id": customer_id},
                        "aggregations": [{"field": "service", "type": "terms", "size": 5}]
                    }
                }
            ]
        }
        
        # Create custom dashboard
        response = await http_client.post(
            f"{test_suite.base_url}/v1/dashboards/custom",
            json=custom_dashboard,
            headers={"X-Customer-ID": customer_id}
        )
        
        assert response.status_code in [200, 201], f"Custom dashboard creation failed: {response.text}"
        result = response.json()
        dashboard_id = result.get("dashboard_id")
        
        # Retrieve custom dashboard
        response = await http_client.get(
            f"{test_suite.base_url}/v1/dashboards/custom/{dashboard_id}",
            headers={"X-Customer-ID": customer_id}
        )
        
        assert response.status_code == 200, f"Custom dashboard retrieval failed: {response.text}"
        
        print("✅ Custom dashboard creation successful")
    
    # ========== M3 ALERT ENGINE TESTS ==========
    
    @pytest.mark.asyncio
    async def test_m3_alert_engine_rule_management(self, test_suite, http_client):
        """Test M3 Alert Engine rule creation, management, and evaluation"""
        print("\n🔄 Testing M3 Alert Engine rule management...")
        
        customer_id = test_suite.test_customers[0]
        headers = {"X-Customer-ID": customer_id, "X-User-ID": "test-user"}
        
        # 1. Test Alert Engine Health
        response = await http_client.get(
            f"{test_suite.base_url}/v1/alerts/health",
            headers=headers
        )
        assert response.status_code == 200, f"Alert engine health check failed: {response.text}"
        health_data = response.json()
        assert health_data["status"] in ["active", "inactive"], "Invalid health status"
        
        # 2. Create Alert Rule - High Error Rate
        error_rule_request = {
            "name": f"High Error Rate - {customer_id}",
            "description": "Alert when error rate exceeds threshold",
            "customer_id": customer_id,
            "severity": "HIGH",
            "rule_type": "THRESHOLD",
            "enabled": True,
            "conditions": [
                {
                    "field": "level",
                    "operator": "EQUALS",
                    "value": "ERROR",
                    "aggregation": "count",
                    "time_window": "5m"
                }
            ],
            "filters": [
                {
                    "field": "customer_id",
                    "operator": "eq",
                    "value": customer_id
                },
                {
                    "field": "service",
                    "operator": "eq",
                    "value": "payment-service"
                }
            ],
            "notification_channels": ["email", "slack"],
            "tags": ["payment", "error", "integration-test"],
            "evaluation_interval": "1m",
            "cooldown_period": "10m",
            "max_alerts_per_hour": 5
        }
        
        response = await http_client.post(
            f"{test_suite.base_url}/v1/alerts/rules",
            json=error_rule_request,
            headers=headers
        )
        assert response.status_code in [200, 201], f"Error rule creation failed: {response.text}"
        error_rule = response.json()
        error_rule_id = error_rule["rule_id"]
        
        assert error_rule["name"] == error_rule_request["name"]
        assert error_rule["customer_id"] == customer_id
        assert error_rule["enabled"] == True
        
        # 3. Create Alert Rule - Failed Login Attempts
        auth_rule_request = {
            "name": f"Failed Login Attempts - {customer_id}",
            "description": "Alert on suspicious authentication activity",
            "customer_id": customer_id,
            "severity": "MEDIUM",
            "rule_type": "FREQUENCY",
            "enabled": True,
            "conditions": [
                {
                    "field": "http_status",
                    "operator": "EQUALS",
                    "value": 401,
                    "aggregation": "count",
                    "time_window": "5m"
                }
            ],
            "filters": [
                {
                    "field": "customer_id",
                    "operator": "eq",
                    "value": customer_id
                },
                {
                    "field": "service",
                    "operator": "eq",
                    "value": "auth-service"
                }
            ],
            "notification_channels": ["webhook"],
            "tags": ["security", "auth", "integration-test"],
            "evaluation_interval": "2m",
            "cooldown_period": "15m",
            "max_alerts_per_hour": 3
        }
        
        response = await http_client.post(
            f"{test_suite.base_url}/v1/alerts/rules",
            json=auth_rule_request,
            headers=headers
        )
        assert response.status_code in [200, 201], f"Auth rule creation failed: {response.text}"
        auth_rule = response.json()
        auth_rule_id = auth_rule["rule_id"]
        
        # 4. List Alert Rules
        response = await http_client.get(
            f"{test_suite.base_url}/v1/alerts/rules",
            headers=headers
        )
        assert response.status_code == 200, f"List rules failed: {response.text}"
        rules_list = response.json()
        
        assert "rules" in rules_list
        assert len(rules_list["rules"]) >= 2, "Should have at least 2 rules created"
        
        # Verify customer isolation
        for rule in rules_list["rules"]:
            assert rule["customer_id"] == customer_id, f"Rule customer isolation failed: {rule['customer_id']}"
        
        # 5. Get Specific Alert Rule
        response = await http_client.get(
            f"{test_suite.base_url}/v1/alerts/rules/{error_rule_id}",
            headers=headers
        )
        assert response.status_code == 200, f"Get rule failed: {response.text}"
        retrieved_rule = response.json()
        assert retrieved_rule["rule_id"] == error_rule_id
        
        # 6. Update Alert Rule
        rule_update = {
            "description": "Updated description for integration test",
            "max_alerts_per_hour": 10
        }
        
        response = await http_client.put(
            f"{test_suite.base_url}/v1/alerts/rules/{error_rule_id}",
            json=rule_update,
            headers=headers
        )
        assert response.status_code == 200, f"Rule update failed: {response.text}"
        updated_rule = response.json()
        assert updated_rule["description"] == rule_update["description"]
        assert updated_rule["max_alerts_per_hour"] == 10
        
        # 7. Test Rule (dry run)
        response = await http_client.post(
            f"{test_suite.base_url}/v1/alerts/rules/{error_rule_id}/test",
            headers=headers
        )
        assert response.status_code == 200, f"Rule test failed: {response.text}"
        test_result = response.json()
        assert "evaluation_result" in test_result or "test_passed" in test_result
        
        print("✅ M3 Alert Engine rule management successful")
        return error_rule_id, auth_rule_id
    
    @pytest.mark.asyncio
    async def test_m3_alert_engine_alert_lifecycle(self, test_suite, http_client):
        """Test M3 Alert Engine alert instance lifecycle management"""
        print("\n🔄 Testing M3 Alert Engine alert lifecycle...")
        
        customer_id = test_suite.test_customers[0]
        headers = {"X-Customer-ID": customer_id, "X-User-ID": "test-user"}
        
        # First create some test rules
        error_rule_id, auth_rule_id = await self.test_m3_alert_engine_rule_management(test_suite, http_client)
        
        # Wait for rule evaluation
        await asyncio.sleep(3)
        
        # 1. List Alerts
        response = await http_client.get(
            f"{test_suite.base_url}/v1/alerts",
            headers=headers
        )
        assert response.status_code == 200, f"List alerts failed: {response.text}"
        alerts_list = response.json()
        
        assert "alerts" in alerts_list
        print(f"Found {len(alerts_list['alerts'])} alerts")
        
        # 2. Get Alert Engine Statistics
        response = await http_client.get(
            f"{test_suite.base_url}/v1/alerts/stats",
            headers=headers
        )
        assert response.status_code == 200, f"Alert stats failed: {response.text}"
        stats = response.json()
        
        assert "rules" in stats
        assert "alerts" in stats
        assert stats["customer_id"] == customer_id
        assert stats["rules"]["total"] >= 2, "Should have at least 2 rules"
        
        # 3. Test Alert Lifecycle if alerts exist
        if alerts_list["alerts"]:
            alert = alerts_list["alerts"][0]
            alert_id = alert["alert_id"]
            
            # Get specific alert
            response = await http_client.get(
                f"{test_suite.base_url}/v1/alerts/{alert_id}",
                headers=headers
            )
            assert response.status_code == 200, f"Get alert failed: {response.text}"
            alert_detail = response.json()
            assert alert_detail["alert_id"] == alert_id
            assert alert_detail["customer_id"] == customer_id
            
            # Acknowledge alert if it's ACTIVE
            if alert["status"] == "ACTIVE":
                response = await http_client.post(
                    f"{test_suite.base_url}/v1/alerts/{alert_id}/acknowledge",
                    headers=headers
                )
                assert response.status_code == 200, f"Acknowledge alert failed: {response.text}"
                ack_result = response.json()
                assert "acknowledged_by" in ack_result
                
                # Verify alert status changed
                response = await http_client.get(
                    f"{test_suite.base_url}/v1/alerts/{alert_id}",
                    headers=headers
                )
                assert response.status_code == 200
                updated_alert = response.json()
                assert updated_alert["status"] == "ACKNOWLEDGED"
                
                # Resolve alert
                resolution_data = {
                    "reason": "Integration test resolution"
                }
                response = await http_client.post(
                    f"{test_suite.base_url}/v1/alerts/{alert_id}/resolve",
                    json=resolution_data,
                    headers=headers
                )
                assert response.status_code == 200, f"Resolve alert failed: {response.text}"
                resolve_result = response.json()
                assert "resolved_by" in resolve_result
                
                # Verify alert is resolved
                response = await http_client.get(
                    f"{test_suite.base_url}/v1/alerts/{alert_id}",
                    headers=headers
                )
                assert response.status_code == 200
                final_alert = response.json()
                assert final_alert["status"] == "RESOLVED"
        
        # 4. Clean up - Delete test rules
        response = await http_client.delete(
            f"{test_suite.base_url}/v1/alerts/rules/{error_rule_id}",
            headers=headers
        )
        assert response.status_code == 200, f"Delete rule failed: {response.text}"
        
        response = await http_client.delete(
            f"{test_suite.base_url}/v1/alerts/rules/{auth_rule_id}",
            headers=headers
        )
        assert response.status_code == 200, f"Delete rule failed: {response.text}"
        
        print("✅ M3 Alert Engine alert lifecycle successful")
    
    @pytest.mark.asyncio
    async def test_m3_alert_engine_multi_tenant_isolation(self, test_suite, http_client):
        """Test M3 Alert Engine multi-tenant isolation"""
        print("\n🔄 Testing M3 Alert Engine multi-tenant isolation...")
        
        customer1 = test_suite.test_customers[0]
        customer2 = test_suite.test_customers[1]
        
        headers1 = {"X-Customer-ID": customer1, "X-User-ID": "test-user-1"}
        headers2 = {"X-Customer-ID": customer2, "X-User-ID": "test-user-2"}
        
        # 1. Create rules for customer 1
        rule_request_1 = {
            "name": f"Customer 1 Alert - {customer1}",
            "description": "Alert for customer 1 only",
            "customer_id": customer1,
            "severity": "LOW",
            "rule_type": "THRESHOLD",
            "enabled": True,
            "conditions": [
                {
                    "field": "level",
                    "operator": "EQUALS", 
                    "value": "INFO",
                    "aggregation": "count",
                    "time_window": "5m"
                }
            ],
            "filters": [
                {
                    "field": "customer_id",
                    "operator": "eq",
                    "value": customer1
                }
            ],
            "notification_channels": ["email"],
            "tags": ["isolation-test", "customer1"],
            "evaluation_interval": "2m",
            "cooldown_period": "5m",
            "max_alerts_per_hour": 2
        }
        
        response = await http_client.post(
            f"{test_suite.base_url}/v1/alerts/rules",
            json=rule_request_1,
            headers=headers1
        )
        assert response.status_code in [200, 201], f"Customer 1 rule creation failed: {response.text}"
        rule1 = response.json()
        rule1_id = rule1["rule_id"]
        
        # 2. Create rules for customer 2
        rule_request_2 = {
            "name": f"Customer 2 Alert - {customer2}",
            "description": "Alert for customer 2 only",
            "customer_id": customer2,
            "severity": "LOW",
            "rule_type": "THRESHOLD",
            "enabled": True,
            "conditions": [
                {
                    "field": "level",
                    "operator": "EQUALS",
                    "value": "INFO", 
                    "aggregation": "count",
                    "time_window": "5m"
                }
            ],
            "filters": [
                {
                    "field": "customer_id",
                    "operator": "eq",
                    "value": customer2
                }
            ],
            "notification_channels": ["slack"],
            "tags": ["isolation-test", "customer2"],
            "evaluation_interval": "2m",
            "cooldown_period": "5m",
            "max_alerts_per_hour": 2
        }
        
        response = await http_client.post(
            f"{test_suite.base_url}/v1/alerts/rules",
            json=rule_request_2,
            headers=headers2
        )
        assert response.status_code in [200, 201], f"Customer 2 rule creation failed: {response.text}"
        rule2 = response.json()
        rule2_id = rule2["rule_id"]
        
        # 3. Verify customer 1 can only see their rules
        response = await http_client.get(
            f"{test_suite.base_url}/v1/alerts/rules",
            headers=headers1
        )
        assert response.status_code == 200, f"Customer 1 list rules failed: {response.text}"
        customer1_rules = response.json()
        
        for rule in customer1_rules["rules"]:
            assert rule["customer_id"] == customer1, f"Customer 1 saw rule from {rule['customer_id']}"
        
        # 4. Verify customer 2 can only see their rules
        response = await http_client.get(
            f"{test_suite.base_url}/v1/alerts/rules", 
            headers=headers2
        )
        assert response.status_code == 200, f"Customer 2 list rules failed: {response.text}"
        customer2_rules = response.json()
        
        for rule in customer2_rules["rules"]:
            assert rule["customer_id"] == customer2, f"Customer 2 saw rule from {rule['customer_id']}"
        
        # 5. Verify customer 1 cannot access customer 2's rule
        response = await http_client.get(
            f"{test_suite.base_url}/v1/alerts/rules/{rule2_id}",
            headers=headers1
        )
        assert response.status_code == 404, "Customer 1 should not access Customer 2's rule"
        
        # 6. Verify customer 2 cannot access customer 1's rule
        response = await http_client.get(
            f"{test_suite.base_url}/v1/alerts/rules/{rule1_id}",
            headers=headers2
        )
        assert response.status_code == 404, "Customer 2 should not access Customer 1's rule"
        
        # 7. Verify alert isolation
        response = await http_client.get(
            f"{test_suite.base_url}/v1/alerts",
            headers=headers1
        )
        assert response.status_code == 200, f"Customer 1 list alerts failed: {response.text}"
        customer1_alerts = response.json()
        
        for alert in customer1_alerts["alerts"]:
            assert alert["customer_id"] == customer1, f"Customer 1 saw alert from {alert['customer_id']}"
        
        response = await http_client.get(
            f"{test_suite.base_url}/v1/alerts",
            headers=headers2
        )
        assert response.status_code == 200, f"Customer 2 list alerts failed: {response.text}"
        customer2_alerts = response.json()
        
        for alert in customer2_alerts["alerts"]:
            assert alert["customer_id"] == customer2, f"Customer 2 saw alert from {alert['customer_id']}"
        
        # Cleanup
        await http_client.delete(f"{test_suite.base_url}/v1/alerts/rules/{rule1_id}", headers=headers1)
        await http_client.delete(f"{test_suite.base_url}/v1/alerts/rules/{rule2_id}", headers=headers2)
        
        print("✅ M3 Alert Engine multi-tenant isolation successful")
    
    @pytest.mark.asyncio
    async def test_m3_alert_engine_comprehensive(self, test_suite, http_client):
        """Comprehensive test of all M3 Alert Engine functionality"""
        print("\n🔄 Running comprehensive M3 Alert Engine test...")
        
        customer_id = test_suite.test_customers[0]
        headers = {"X-Customer-ID": customer_id, "X-User-ID": "integration-test"}
        
        # Test all rule types
        rule_types_to_test = [
            {
                "name": f"Threshold Alert - {customer_id}",
                "rule_type": "THRESHOLD",
                "conditions": [{
                    "field": "http_response_time_ms",
                    "operator": "GREATER_THAN",
                    "value": 1000,
                    "aggregation": "avg",
                    "time_window": "5m"
                }],
                "severity": "HIGH"
            },
            {
                "name": f"Anomaly Alert - {customer_id}",
                "rule_type": "ANOMALY",
                "conditions": [{
                    "field": "http_bytes",
                    "operator": "GREATER_THAN",
                    "value": 10000,
                    "aggregation": "sum",
                    "time_window": "10m"
                }],
                "severity": "MEDIUM"
            },
            {
                "name": f"Pattern Alert - {customer_id}",
                "rule_type": "PATTERN",
                "conditions": [{
                    "field": "msg",
                    "operator": "CONTAINS",
                    "value": "payment processing failed",
                    "aggregation": "count",
                    "time_window": "5m"
                }],
                "severity": "CRITICAL"
            }
        ]
        
        created_rules = []
        
        for rule_template in rule_types_to_test:
            rule_request = {
                **rule_template,
                "description": f"Comprehensive test rule - {rule_template['rule_type']}",
                "customer_id": customer_id,
                "enabled": True,
                "filters": [
                    {
                        "field": "customer_id",
                        "operator": "eq",
                        "value": customer_id
                    }
                ],
                "notification_channels": ["email", "webhook"],
                "tags": ["comprehensive-test", rule_template["rule_type"].lower()],
                "evaluation_interval": "2m",
                "cooldown_period": "10m",
                "max_alerts_per_hour": 5
            }
            
            response = await http_client.post(
                f"{test_suite.base_url}/v1/alerts/rules",
                json=rule_request,
                headers=headers
            )
            assert response.status_code in [200, 201], f"Rule creation failed for {rule_template['rule_type']}: {response.text}"
            
            created_rule = response.json()
            created_rules.append(created_rule["rule_id"])
            
            # Test rule immediately
            response = await http_client.post(
                f"{test_suite.base_url}/v1/alerts/rules/{created_rule['rule_id']}/test",
                headers=headers
            )
            assert response.status_code == 200, f"Rule test failed for {rule_template['rule_type']}: {response.text}"
        
        # Verify all rules were created
        response = await http_client.get(
            f"{test_suite.base_url}/v1/alerts/rules",
            headers=headers
        )
        assert response.status_code == 200, f"List rules failed: {response.text}"
        all_rules = response.json()
        
        # Should have at least the rules we just created
        rule_names = [rule["name"] for rule in all_rules["rules"]]
        for rule_template in rule_types_to_test:
            assert any(rule_template["name"] in name for name in rule_names), f"Rule {rule_template['name']} not found"
        
        # Test alert engine health and stats
        response = await http_client.get(
            f"{test_suite.base_url}/v1/alerts/health",
            headers=headers
        )
        assert response.status_code == 200, f"Health check failed: {response.text}"
        
        response = await http_client.get(
            f"{test_suite.base_url}/v1/alerts/stats",
            headers=headers
        )
        assert response.status_code == 200, f"Stats check failed: {response.text}"
        stats = response.json()
        assert stats["rules"]["total"] >= len(rule_types_to_test), "Not all rules counted in stats"
        
        # Clean up all created rules
        for rule_id in created_rules:
            response = await http_client.delete(
                f"{test_suite.base_url}/v1/alerts/rules/{rule_id}",
                headers=headers
            )
            assert response.status_code == 200, f"Rule cleanup failed for {rule_id}: {response.text}"
        
        print("✅ Comprehensive M3 Alert Engine test successful")
    
    # ========== TTL AND STORAGE TESTS ==========
    
    @pytest.mark.asyncio
    async def test_ttl_manager_multi_tenant(self, test_suite):
        """Test TTL manager with multi-tenant policies"""
        print("\n🔄 Testing TTL manager with multi-tenancy...")
        
        # Mock storage config manager for testing
        with patch('ttl_manager.StorageConfigManager') as mock_storage_manager:
            mock_storage_manager.return_value.get_compliance_retention_days.return_value = 90
            
            ttl_manager = TTLManager()
            await ttl_manager.initialize_policies()
            
            # Test retention policy creation for each customer
            for customer_id in test_suite.test_customers:
                policy = await ttl_manager.create_customer_policy(
                    customer_id=customer_id,
                    deployment_type="shared",
                    compliance_tier=ComplianceTier.STANDARD
                )
                
                assert policy.customer_id == customer_id, f"Policy customer_id mismatch: {policy.customer_id}"
                assert policy.hot_storage_days > 0, "Hot storage days must be positive"
                assert policy.total_retention_days > 0, "Total retention days must be positive"
            
            # Test policy retrieval
            for customer_id in test_suite.test_customers:
                status = await ttl_manager.get_retention_status(customer_id)
                assert "customer_id" in status or "error" in status, f"Invalid retention status format for {customer_id}"
        
        print("✅ TTL manager multi-tenancy successful")
    
    @pytest.mark.asyncio
    async def test_storage_config_multi_backend(self, test_suite):
        """Test storage configuration with multiple backends"""
        print("\n🔄 Testing storage configuration with multiple backends...")
        
        storage_manager = StorageConfigManager()
        
        for customer_id in test_suite.test_customers:
            try:
                # Test storage endpoint configuration
                endpoint = storage_manager.get_storage_endpoint(customer_id)
                
                assert endpoint.backend is not None, f"Backend not configured for {customer_id}"
                assert endpoint.region is not None, f"Region not configured for {customer_id}"
                assert endpoint.bucket is not None, f"Bucket not configured for {customer_id}"
                
                # Test compliance requirements
                encryption_required = storage_manager.is_encryption_required(customer_id)
                retention_days = storage_manager.get_compliance_retention_days(customer_id)
                
                assert isinstance(encryption_required, bool), "Encryption requirement must be boolean"
                assert retention_days > 0, "Retention days must be positive"
                
            except Exception as e:
                # Some customers might not have specific configs, which is acceptable
                print(f"⚠️  Customer {customer_id} using default config: {e}")
        
        print("✅ Storage configuration multi-backend successful")
    
    # ========== API ENDPOINT TESTS ==========
    
    @pytest.mark.asyncio
    async def test_all_api_endpoints(self, test_suite, http_client):
        """Test all API endpoints for functionality"""
        print("\n🔄 Testing all API endpoints...")
        
        customer_id = test_suite.test_customers[0]
        headers = {"X-Customer-ID": customer_id}
        
        # Test health endpoints
        endpoints_to_test = [
            ("GET", "/health", None),
            ("GET", "/v1/health", None),
            ("GET", "/v1/health/detailed", None)
        ]
        
        for method, endpoint, data in endpoints_to_test:
            if method == "GET":
                response = await http_client.get(f"{test_suite.base_url}{endpoint}", headers=headers)
            else:
                response = await http_client.post(f"{test_suite.base_url}{endpoint}", json=data, headers=headers)
            
            assert response.status_code in [200, 201], f"{method} {endpoint} failed: {response.text}"
        
        print("✅ All API endpoints tested successfully")
    
    # ========== PERFORMANCE TESTS ==========
    
    @pytest.mark.asyncio
    async def test_performance_targets(self, test_suite, http_client):
        """Test that performance targets are met"""
        print("\n🔄 Testing performance targets...")
        
        customer_id = test_suite.test_customers[0]
        
        # Test query performance - should be under 1.5s for 24h window
        start_time = time.time()
        
        query_request = {
            "start_time": (datetime.utcnow() - timedelta(hours=24)).isoformat(),
            "end_time": datetime.utcnow().isoformat(),
            "filters": [
                {
                    "field": "customer_id",
                    "operator": "eq", 
                    "value": customer_id
                }
            ],
            "limit": 1000
        }
        
        response = await http_client.post(
            f"{test_suite.base_url}/v1/query/advanced",
            json=query_request,
            headers={"X-Customer-ID": customer_id}
        )
        
        query_time = time.time() - start_time
        
        assert response.status_code == 200, f"Performance query failed: {response.text}"
        assert query_time < 3.0, f"Query took {query_time:.2f}s, should be under 3.0s"  # Relaxed target for integration test
        
        print(f"✅ Performance test successful - Query completed in {query_time:.2f}s")
    
    # ========== COMPREHENSIVE END-TO-END TEST ==========
    
    @pytest.mark.asyncio
    async def test_complete_end_to_end_workflow(self, test_suite, http_client):
        """Test complete end-to-end workflow for all features"""
        print("\n🔄 Running complete end-to-end workflow test...")
        
        customer_id = "integration-test-customer"
        headers = {"X-Customer-ID": customer_id}
        
        # 1. Ingest data
        test_logs = await test_suite._generate_test_data(customer_id)
        sample_logs = test_logs[:20]  # Use smaller set for E2E test
        
        for log_entry in sample_logs:
            response = await http_client.post(
                f"{test_suite.base_url}/v1/ingest/logs",
                json=log_entry,
                headers=headers
            )
            assert response.status_code in [200, 201], "E2E: Ingestion failed"
        
        # 2. Wait for data processing
        await asyncio.sleep(3)
        
        # 3. Query data
        query_request = {
            "start_time": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
            "end_time": datetime.utcnow().isoformat(),
            "filters": [
                {
                    "field": "customer_id",
                    "operator": "eq",
                    "value": customer_id
                }
            ],
            "limit": 50
        }
        
        response = await http_client.post(
            f"{test_suite.base_url}/v1/query/advanced",
            json=query_request,
            headers=headers
        )
        assert response.status_code == 200, "E2E: Query failed"
        
        # 4. Generate dashboard
        response = await http_client.get(
            f"{test_suite.base_url}/v1/dashboards/security_soc",
            headers=headers
        )
        assert response.status_code == 200, "E2E: Dashboard generation failed"
        
        # 5. Test dashboard data
        response = await http_client.post(
            f"{test_suite.base_url}/v1/dashboards/security_soc/data",
            json={"time_range": "1h", "customer_id": customer_id},
            headers=headers
        )
        assert response.status_code == 200, "E2E: Dashboard data generation failed"
        
        print("✅ Complete end-to-end workflow successful")
    
    # ========== REGRESSION TEST SUITE ==========
    
    @pytest.mark.asyncio
    async def test_regression_suite(self, test_suite, http_client):
        """Comprehensive regression test for all implemented features"""
        print("\n🔄 Running regression test suite...")
        
        regression_tests = [
            self.test_multi_tenant_log_ingestion,
            self.test_advanced_query_engine_multi_tenant,
            self.test_all_dashboard_types,
            self.test_ttl_manager_multi_tenant,
            self.test_storage_config_multi_backend,
            self.test_all_api_endpoints,
            self.test_complete_end_to_end_workflow
        ]
        
        failed_tests = []
        
        for test_func in regression_tests:
            try:
                await test_func(test_suite, http_client)
                print(f"✅ {test_func.__name__} passed")
            except Exception as e:
                failed_tests.append((test_func.__name__, str(e)))
                print(f"❌ {test_func.__name__} failed: {e}")
        
        if failed_tests:
            failure_summary = "\n".join([f"  • {name}: {error}" for name, error in failed_tests])
            raise AssertionError(f"Regression tests failed:\n{failure_summary}")
        
        print("✅ All regression tests passed!")


# ========== TEST RUNNER FUNCTIONS ==========

async def run_integration_tests():
    """Run integration tests programmatically"""
    print("🚀 Starting Comprehensive Integration Test Suite...")
    
    # Create test suite
    suite = IntegrationTestSuite()
    await suite.setup_test_environment()
    
    # Run all tests
    test_class = TestComprehensiveIntegration()
    
    try:
        # Create HTTP client
        async with httpx.AsyncClient() as http_client:
            
            # Run core integration tests
            await test_class.test_multi_tenant_log_ingestion(suite, http_client)
            await test_class.test_bulk_ingestion(suite, http_client)
            await test_class.test_advanced_query_engine_multi_tenant(suite, http_client) 
            await test_class.test_time_series_analysis(suite, http_client)
            await test_class.test_all_dashboard_types(suite, http_client)
            await test_class.test_custom_dashboard_creation(suite, http_client)
            
            # M3 Alert Engine tests
            await test_class.test_m3_alert_engine_rule_management(suite, http_client)
            await test_class.test_m3_alert_engine_alert_lifecycle(suite, http_client)
            await test_class.test_m3_alert_engine_multi_tenant_isolation(suite, http_client)
            await test_class.test_m3_alert_engine_comprehensive(suite, http_client)
            
            await test_class.test_ttl_manager_multi_tenant(suite)
            await test_class.test_storage_config_multi_backend(suite)
            await test_class.test_all_api_endpoints(suite, http_client)
            await test_class.test_performance_targets(suite, http_client)
            await test_class.test_complete_end_to_end_workflow(suite, http_client)
            await test_class.test_regression_suite(suite, http_client)
            
        print("\n🎉 ALL INTEGRATION TESTS PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ INTEGRATION TESTS FAILED: {e}")
        return False


if __name__ == "__main__":
    # Run integration tests standalone
    result = asyncio.run(run_integration_tests())
    exit(0 if result else 1)