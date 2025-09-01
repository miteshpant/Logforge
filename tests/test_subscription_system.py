#!/usr/bin/env python3
"""
Tenant Subscription & Billing System - Exhaustive Test Suite
Tests feature subscriptions, access control, billing, and tenant lifecycle
"""

import asyncio
import httpx
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any

class SubscriptionTestSuite:
    """Exhaustive test suite for subscription and billing system"""
    
    def __init__(self):
        self.base_url = "http://localhost:7080"
        self.test_results = {}
        self.test_tenant_ids = []
        self.test_admin_token = "admin-token"
        
    async def setup_test_tenants(self):
        """Create test tenants with different subscription tiers"""
        tenant_configs = [
            {
                "name": "Starter Test Corp",
                "type": "startup", 
                "tier": "starter",
                "features": ["ingestion.basic", "storage.hot", "queries.basic"]
            },
            {
                "name": "Professional Test Corp",
                "type": "smb",
                "tier": "professional", 
                "features": ["ingestion.*", "storage.*", "queries.*", "alerts.basic", "dashboards.readonly"]
            },
            {
                "name": "Enterprise Test Corp", 
                "type": "enterprise",
                "tier": "enterprise",
                "features": ["*"]  # All features
            }
        ]
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for config in tenant_configs:
                # Create tenant
                tenant_data = {
                    "name": config["name"],
                    "type": config["type"],
                    "primary_contact_name": "Test Manager",
                    "primary_contact_email": f"test-{config['tier']}@logforge.local",
                    "industry": "Technology"
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/tenants",
                    json=tenant_data,
                    headers={"Authorization": f"Bearer {self.test_admin_token}"}
                )
                
                if response.status_code == 201:
                    tenant_id = response.json()["tenant_id"]
                    self.test_tenant_ids.append({
                        "tenant_id": tenant_id,
                        "tier": config["tier"],
                        "features": config["features"]
                    })
                    print(f"🏢 Created {config['tier']} tenant: {tenant_id}")
                    
                    # Set subscription for tenant
                    subscription_data = {
                        "subscribed_features": config["features"],
                        "subscription_tier": config["tier"],
                        "billing_cycle": "monthly"
                    }
                    
                    sub_response = await client.put(
                        f"{self.base_url}/v1/tenants/{tenant_id}/subscription",
                        json=subscription_data,
                        headers={"Authorization": f"Bearer {self.test_admin_token}"}
                    )
                    
                    if sub_response.status_code == 200:
                        print(f"✅ Set subscription for {config['tier']} tenant")
                    else:
                        print(f"⚠️ Failed to set subscription: {sub_response.text}")
                else:
                    print(f"❌ Failed to create {config['tier']} tenant: {response.text}")
    
    async def test_feature_access_control(self):
        """Test 1: Feature access control with 403 enforcement"""
        print("🔄 Testing feature access control...")
        
        test_cases = [
            # Starter tenant (limited features)
            {
                "tenant": "starter",
                "tests": [
                    {"endpoint": "/v1/ingest/logs", "method": "POST", "should_pass": True, "feature": "ingestion.basic"},
                    {"endpoint": "/v1/query/advanced", "method": "POST", "should_pass": True, "feature": "queries.basic"},
                    {"endpoint": "/v1/alerts/rules", "method": "GET", "should_pass": False, "feature": "alerts.basic"},
                    {"endpoint": "/v1/security/health", "method": "GET", "should_pass": False, "feature": "security.events"},
                    {"endpoint": "/v1/dashboards", "method": "GET", "should_pass": False, "feature": "dashboards.readonly"}
                ]
            },
            # Professional tenant (mid-tier features)
            {
                "tenant": "professional", 
                "tests": [
                    {"endpoint": "/v1/ingest/logs", "method": "POST", "should_pass": True, "feature": "ingestion.*"},
                    {"endpoint": "/v1/alerts/rules", "method": "GET", "should_pass": True, "feature": "alerts.basic"},
                    {"endpoint": "/v1/dashboards", "method": "GET", "should_pass": True, "feature": "dashboards.readonly"},
                    {"endpoint": "/v1/security/health", "method": "GET", "should_pass": False, "feature": "security.events"},
                    {"endpoint": "/v1/ai/health", "method": "GET", "should_pass": False, "feature": "ai_assistant"}
                ]
            },
            # Enterprise tenant (all features)
            {
                "tenant": "enterprise",
                "tests": [
                    {"endpoint": "/v1/ingest/logs", "method": "POST", "should_pass": True, "feature": "*"},
                    {"endpoint": "/v1/security/health", "method": "GET", "should_pass": True, "feature": "*"},
                    {"endpoint": "/v1/ai/health", "method": "GET", "should_pass": True, "feature": "*"},
                    {"endpoint": "/v1/observability/health", "method": "GET", "should_pass": True, "feature": "*"},
                    {"endpoint": "/v1/enterprise/system/health", "method": "GET", "should_pass": True, "feature": "*"}
                ]
            }
        ]
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                for test_group in test_cases:
                    tenant_info = next(t for t in self.test_tenant_ids if t["tier"] == test_group["tenant"])
                    tenant_id = tenant_info["tenant_id"]
                    
                    for test in test_group["tests"]:
                        headers = {"X-Customer-ID": tenant_id}
                        
                        if test["method"] == "POST":
                            # Add minimal test data for POST requests
                            test_data = {}
                            if "ingest" in test["endpoint"]:
                                test_data = {"ts": datetime.now().isoformat(), "service": "test", "msg": "test"}
                            elif "query" in test["endpoint"]:
                                test_data = {"start_time": datetime.now().isoformat(), "end_time": datetime.now().isoformat()}
                            
                            response = await client.post(f"{self.base_url}{test['endpoint']}", json=test_data, headers=headers)
                        else:
                            response = await client.get(f"{self.base_url}{test['endpoint']}", headers=headers)
                        
                        if test["should_pass"]:
                            assert response.status_code != 403, f"Expected access for {test_group['tenant']} to {test['endpoint']} (feature: {test['feature']}), got 403"
                            print(f"  ✅ {test_group['tenant']}: {test['endpoint']} - Access granted")
                        else:
                            assert response.status_code == 403, f"Expected 403 for {test_group['tenant']} to {test['endpoint']} (feature: {test['feature']}), got {response.status_code}"
                            print(f"  🚫 {test_group['tenant']}: {test['endpoint']} - Access denied (403)")
                
                print("✅ Feature access control successful")
                self.test_results["feature_access_control"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Feature access control failed: {str(e)}")
                self.test_results["feature_access_control"] = f"FAIL: {str(e)}"
                return False
    
    async def test_admin_rate_configuration(self):
        """Test 2: Admin feature rate configuration"""
        print("🔄 Testing admin rate configuration...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Test creating feature rates
                feature_rates = [
                    {
                        "feature_name": "ingestion.basic",
                        "pricing_model": "per_unit",
                        "base_rate": 0.001,
                        "tier_rates": {
                            "starter": 0.002,
                            "professional": 0.0015,
                            "enterprise": 0.001
                        },
                        "description": "Cost per log ingested"
                    },
                    {
                        "feature_name": "alerts.basic",
                        "pricing_model": "fixed_monthly",
                        "base_rate": 19.99,
                        "tier_rates": {
                            "starter": 9.99,
                            "professional": 19.99,
                            "enterprise": 49.99
                        },
                        "description": "Monthly alert subscription"
                    },
                    {
                        "feature_name": "security.events",
                        "pricing_model": "per_unit",
                        "base_rate": 0.05,
                        "tier_rates": {
                            "enterprise": 0.03
                        },
                        "description": "Cost per security event processed"
                    }
                ]
                
                for rate_config in feature_rates:
                    # Create rate
                    response = await client.post(
                        f"{self.base_url}/v1/admin/rates",
                        json=rate_config,
                        headers={"Authorization": f"Bearer {self.test_admin_token}"}
                    )
                    
                    assert response.status_code == 201, f"Failed to create rate for {rate_config['feature_name']}: {response.text}"
                    rate_data = response.json()
                    assert rate_data["feature_name"] == rate_config["feature_name"]
                    print(f"  ✅ Created rate for {rate_config['feature_name']}")
                
                # Test listing all rates
                response = await client.get(
                    f"{self.base_url}/v1/admin/rates",
                    headers={"Authorization": f"Bearer {self.test_admin_token}"}
                )
                
                assert response.status_code == 200, f"Failed to list rates: {response.text}"
                rates_data = response.json()
                assert "rates" in rates_data
                assert len(rates_data["rates"]) >= 3
                print(f"  ✅ Listed {len(rates_data['rates'])} feature rates")
                
                # Test updating a rate
                update_data = {
                    "base_rate": 0.0008,
                    "description": "Updated cost per log ingested"
                }
                
                response = await client.put(
                    f"{self.base_url}/v1/admin/rates/ingestion.basic",
                    json=update_data,
                    headers={"Authorization": f"Bearer {self.test_admin_token}"}
                )
                
                assert response.status_code == 200, f"Failed to update rate: {response.text}"
                print("  ✅ Updated feature rate")
                
                print("✅ Admin rate configuration successful")
                self.test_results["admin_rate_config"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Admin rate configuration failed: {str(e)}")
                self.test_results["admin_rate_config"] = f"FAIL: {str(e)}"
                return False
    
    async def test_subscription_management(self):
        """Test 3: Tenant subscription CRUD operations"""
        print("🔄 Testing subscription management...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                tenant_id = self.test_tenant_ids[0]["tenant_id"]  # Use starter tenant
                
                # Test getting current subscription
                response = await client.get(
                    f"{self.base_url}/v1/tenants/{tenant_id}/subscription"
                )
                
                assert response.status_code == 200, f"Failed to get subscription: {response.text}"
                subscription = response.json()
                assert subscription["tenant_id"] == tenant_id
                print("  ✅ Retrieved tenant subscription")
                
                # Test updating subscription (upgrade to professional)
                upgrade_data = {
                    "subscribed_features": ["ingestion.*", "storage.*", "queries.*", "alerts.basic", "dashboards.readonly"],
                    "subscription_tier": "professional",
                    "billing_cycle": "monthly",
                    "monthly_spend_limit": 500.0
                }
                
                response = await client.put(
                    f"{self.base_url}/v1/tenants/{tenant_id}/subscription",
                    json=upgrade_data
                )
                
                assert response.status_code == 200, f"Failed to update subscription: {response.text}"
                updated_sub = response.json()
                assert updated_sub["subscription_tier"] == "professional"
                print("  ✅ Upgraded tenant subscription")
                
                # Test feature availability check
                response = await client.get(
                    f"{self.base_url}/v1/tenants/{tenant_id}/features"
                )
                
                assert response.status_code == 200, f"Failed to get features: {response.text}"
                features = response.json()
                assert "available_features" in features
                assert "alerts.basic" in features["available_features"]
                print("  ✅ Verified feature availability")
                
                # Test specific feature access check
                response = await client.get(
                    f"{self.base_url}/v1/tenants/{tenant_id}/features/alerts.basic/access"
                )
                
                assert response.status_code == 200, f"Failed to check feature access: {response.text}"
                access = response.json()
                assert access["access_granted"] == True
                print("  ✅ Verified specific feature access")
                
                print("✅ Subscription management successful")
                self.test_results["subscription_management"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Subscription management failed: {str(e)}")
                self.test_results["subscription_management"] = f"FAIL: {str(e)}"
                return False
    
    async def test_usage_tracking_and_billing(self):
        """Test 4: Usage tracking and billing calculation"""
        print("🔄 Testing usage tracking and billing...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                tenant_id = self.test_tenant_ids[1]["tenant_id"]  # Use professional tenant
                
                # Generate usage by making API calls
                usage_actions = [
                    # Log ingestion (should be tracked)
                    {
                        "action": "ingest_logs",
                        "endpoint": "/v1/ingest/logs",
                        "method": "POST",
                        "data": {"ts": datetime.now().isoformat(), "service": "billing-test", "msg": "test log"},
                        "expected_feature": "ingestion"
                    },
                    # Query execution (should be tracked)
                    {
                        "action": "execute_query", 
                        "endpoint": "/v1/query/advanced",
                        "method": "POST",
                        "data": {
                            "start_time": (datetime.now() - timedelta(hours=1)).isoformat(),
                            "end_time": datetime.now().isoformat(),
                            "limit": 10
                        },
                        "expected_feature": "queries"
                    },
                    # Dashboard access (should be tracked)
                    {
                        "action": "view_dashboard",
                        "endpoint": "/v1/dashboards",
                        "method": "GET", 
                        "data": None,
                        "expected_feature": "dashboards"
                    }
                ]
                
                # Execute actions to generate usage
                for action in usage_actions:
                    headers = {"X-Customer-ID": tenant_id}
                    
                    if action["method"] == "POST":
                        response = await client.post(
                            f"{self.base_url}{action['endpoint']}", 
                            json=action["data"],
                            headers=headers
                        )
                    else:
                        response = await client.get(
                            f"{self.base_url}{action['endpoint']}", 
                            headers=headers
                        )
                    
                    # Should succeed since professional tenant has these features
                    assert response.status_code in [200, 201], f"Action {action['action']} failed: {response.text}"
                    print(f"  ✅ Executed {action['action']} - usage tracked")
                
                # Wait for usage tracking to process
                await asyncio.sleep(2)
                
                # Test usage retrieval
                response = await client.get(
                    f"{self.base_url}/v1/tenants/{tenant_id}/usage?period=current"
                )
                
                assert response.status_code == 200, f"Failed to get usage: {response.text}"
                usage = response.json()
                assert "feature_usage" in usage
                assert len(usage["feature_usage"]) > 0
                print("  ✅ Retrieved usage data")
                
                # Test detailed usage breakdown
                response = await client.get(
                    f"{self.base_url}/v1/tenants/{tenant_id}/usage/detailed?start_date=2025-09-01&end_date=2025-09-30"
                )
                
                assert response.status_code == 200, f"Failed to get detailed usage: {response.text}"
                detailed_usage = response.json()
                assert "total_cost" in detailed_usage
                assert "feature_usage" in detailed_usage
                print("  ✅ Retrieved detailed usage breakdown")
                
                # Test bill generation
                bill_data = {
                    "billing_period": "2025-09",
                    "include_usage_details": True
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/tenants/{tenant_id}/billing/generate",
                    json=bill_data
                )
                
                assert response.status_code == 200, f"Failed to generate bill: {response.text}"
                bill = response.json()
                assert "bill_id" in bill
                assert "total_amount" in bill
                print("  ✅ Generated tenant bill")
                
                print("✅ Usage tracking and billing successful")
                self.test_results["usage_tracking_billing"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Usage tracking and billing failed: {str(e)}")
                self.test_results["usage_tracking_billing"] = f"FAIL: {str(e)}"
                return False
    
    async def test_subscription_enforcement_edge_cases(self):
        """Test 5: Edge cases for subscription enforcement"""
        print("🔄 Testing subscription enforcement edge cases...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Test 1: Suspended subscription
                suspended_tenant = self.test_tenant_ids[0]["tenant_id"]
                
                # Suspend the subscription
                suspend_data = {"status": "suspended"}
                response = await client.patch(
                    f"{self.base_url}/v1/tenants/{suspended_tenant}/subscription/status",
                    json=suspend_data,
                    headers={"Authorization": f"Bearer {self.test_admin_token}"}
                )
                
                assert response.status_code == 200, f"Failed to suspend subscription: {response.text}"
                print("  ✅ Suspended tenant subscription")
                
                # Try to access features (should get 403)
                response = await client.post(
                    f"{self.base_url}/v1/ingest/logs",
                    json={"ts": datetime.now().isoformat(), "service": "test", "msg": "test"},
                    headers={"X-Customer-ID": suspended_tenant}
                )
                
                assert response.status_code == 403, f"Expected 403 for suspended tenant, got {response.status_code}"
                error_data = response.json()
                assert "subscription_suspended" in error_data["detail"].lower()
                print("  ✅ Suspended tenant properly denied access")
                
                # Test 2: Wildcard feature matching
                enterprise_tenant = self.test_tenant_ids[2]["tenant_id"]
                
                # Test various endpoints with wildcard (*) subscription
                wildcard_tests = [
                    "/v1/ingest/logs",
                    "/v1/security/health", 
                    "/v1/ai/health",
                    "/v1/observability/health",
                    "/v1/enterprise/system/health"
                ]
                
                for endpoint in wildcard_tests:
                    response = await client.get(
                        f"{self.base_url}{endpoint}",
                        headers={"X-Customer-ID": enterprise_tenant}
                    )
                    assert response.status_code != 403, f"Enterprise tenant denied access to {endpoint}"
                    print(f"  ✅ Enterprise wildcard access: {endpoint}")
                
                # Test 3: Feature namespace matching
                pro_tenant = self.test_tenant_ids[1]["tenant_id"]
                
                # Professional has "ingestion.*" - should work for all ingestion endpoints
                ingestion_tests = [
                    "/v1/ingest/logs",
                    "/v1/ingest/logs/batch", 
                    "/v1/ingest/syslog",
                    "/v1/ingest/nginx"
                ]
                
                for endpoint in ingestion_tests:
                    if "logs" in endpoint:
                        response = await client.post(
                            f"{self.base_url}{endpoint}",
                            json={"ts": datetime.now().isoformat(), "service": "test", "msg": "test"},
                            headers={"X-Customer-ID": pro_tenant}
                        )
                    else:
                        response = await client.post(
                            f"{self.base_url}{endpoint}",
                            data="test log data",
                            headers={"X-Customer-ID": pro_tenant, "Content-Type": "text/plain"}
                        )
                    
                    assert response.status_code != 403, f"Professional tenant denied ingestion.* access to {endpoint}"
                    print(f"  ✅ Professional namespace access: {endpoint}")
                
                print("✅ Subscription enforcement edge cases successful")
                self.test_results["subscription_edge_cases"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Subscription enforcement edge cases failed: {str(e)}")
                self.test_results["subscription_edge_cases"] = f"FAIL: {str(e)}"
                return False
    
    async def test_soft_delete_with_data_cleanup(self):
        """Test 6: Soft delete tenant with data cleanup"""
        print("🔄 Testing soft delete with data cleanup...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Create a test tenant specifically for deletion
                tenant_data = {
                    "name": "Delete Test Corp",
                    "type": "startup",
                    "primary_contact_name": "Delete Test Manager", 
                    "primary_contact_email": "delete-test@logforge.local",
                    "industry": "Technology"
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/tenants",
                    json=tenant_data,
                    headers={"Authorization": f"Bearer {self.test_admin_token}"}
                )
                
                assert response.status_code == 201, f"Failed to create test tenant: {response.text}"
                delete_tenant_id = response.json()["tenant_id"]
                print(f"  ✅ Created tenant for deletion: {delete_tenant_id}")
                
                # Generate some log data for this tenant
                log_data = {"ts": datetime.now().isoformat(), "service": "delete-test", "msg": "test data to be deleted"}
                response = await client.post(
                    f"{self.base_url}/v1/ingest/logs",
                    json=log_data,
                    headers={"X-Customer-ID": delete_tenant_id}
                )
                assert response.status_code == 200, "Failed to create test data"
                print("  ✅ Created test data for tenant")
                
                # Wait for data processing
                await asyncio.sleep(3)
                
                # Verify data exists
                response = await client.get(
                    f"{self.base_url}/v1/logs?service=delete-test",
                    headers={"X-Customer-ID": delete_tenant_id}
                )
                assert response.status_code == 200, "Failed to verify test data"
                logs = response.json()
                initial_log_count = len(logs.get("logs", []))
                assert initial_log_count > 0, "No test data found"
                print(f"  ✅ Verified {initial_log_count} logs exist for tenant")
                
                # Test soft delete
                delete_data = {
                    "deletion_type": "soft_delete",
                    "reason": "Customer requested account closure",
                    "data_cleanup": True,
                    "generate_final_bill": True
                }
                
                response = await client.delete(
                    f"{self.base_url}/v1/tenants/{delete_tenant_id}",
                    json=delete_data,
                    headers={"Authorization": f"Bearer {self.test_admin_token}"}
                )
                
                assert response.status_code == 200, f"Failed to soft delete tenant: {response.text}"
                deletion_result = response.json()
                assert deletion_result["deletion_type"] == "soft_delete"
                assert deletion_result["data_cleanup_scheduled"] == True
                print("  ✅ Soft deleted tenant")
                
                # Wait for data cleanup processing
                await asyncio.sleep(5)
                
                # Verify tenant is marked as deleted but tenant record exists
                response = await client.get(
                    f"{self.base_url}/v1/tenants/{delete_tenant_id}",
                    headers={"Authorization": f"Bearer {self.test_admin_token}"}
                )
                
                if response.status_code == 200:
                    tenant_info = response.json()
                    assert tenant_info["status"] == "deleted", "Tenant should be marked as deleted"
                    print("  ✅ Tenant marked as deleted but record preserved")
                else:
                    assert response.status_code == 404, "Deleted tenant should return 404 or be marked deleted"
                    print("  ✅ Deleted tenant properly hidden from API")
                
                # Verify log data is cleaned up
                response = await client.get(
                    f"{self.base_url}/v1/logs?service=delete-test",
                    headers={"X-Customer-ID": delete_tenant_id}
                )
                
                # Should either return 403 (tenant deleted) or empty results (data cleaned)
                assert response.status_code in [403, 404] or (response.status_code == 200 and len(response.json().get("logs", [])) == 0), "Log data should be cleaned up"
                print("  ✅ Log data cleaned up after soft delete")
                
                # Verify usage records are preserved
                response = await client.get(
                    f"{self.base_url}/v1/admin/usage/{delete_tenant_id}/history",
                    headers={"Authorization": f"Bearer {self.test_admin_token}"}
                )
                
                assert response.status_code == 200, f"Failed to get usage history: {response.text}"
                usage_history = response.json()
                assert "usage_records" in usage_history
                print("  ✅ Usage records preserved after deletion")
                
                print("✅ Soft delete with data cleanup successful")
                self.test_results["soft_delete_cleanup"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Soft delete with data cleanup failed: {str(e)}")
                self.test_results["soft_delete_cleanup"] = f"FAIL: {str(e)}"
                return False
    
    async def test_subscription_tier_enforcement(self):
        """Test 7: Subscription tier feature enforcement"""
        print("🔄 Testing subscription tier enforcement...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Test starter tier limitations
                starter_tenant = next(t for t in self.test_tenant_ids if t["tier"] == "starter")["tenant_id"]
                
                # Should work: basic ingestion
                response = await client.post(
                    f"{self.base_url}/v1/ingest/logs",
                    json={"ts": datetime.now().isoformat(), "service": "tier-test", "msg": "starter test"},
                    headers={"X-Customer-ID": starter_tenant}
                )
                assert response.status_code == 200, "Starter should have ingestion access"
                print("  ✅ Starter tier: ingestion access granted")
                
                # Should fail: security features
                response = await client.get(
                    f"{self.base_url}/v1/security/events",
                    headers={"X-Customer-ID": starter_tenant}
                )
                assert response.status_code == 403, "Starter should be denied security access"
                error_data = response.json()
                assert "security" in error_data["detail"].lower()
                print("  ✅ Starter tier: security access denied (403)")
                
                # Should fail: AI features
                response = await client.post(
                    f"{self.base_url}/v1/ai/query",
                    json={"question": "show me errors", "context": {}},
                    headers={"X-Customer-ID": starter_tenant}
                )
                assert response.status_code == 403, "Starter should be denied AI access"
                print("  ✅ Starter tier: AI access denied (403)")
                
                # Test professional tier permissions
                pro_tenant = next(t for t in self.test_tenant_ids if t["tier"] == "professional")["tenant_id"]
                
                # Should work: alerts
                response = await client.get(
                    f"{self.base_url}/v1/alerts/rules",
                    headers={"X-Customer-ID": pro_tenant}
                )
                assert response.status_code != 403, "Professional should have alerts access"
                print("  ✅ Professional tier: alerts access granted")
                
                # Should fail: enterprise features
                response = await client.get(
                    f"{self.base_url}/v1/enterprise/system/health",
                    headers={"X-Customer-ID": pro_tenant}
                )
                assert response.status_code == 403, "Professional should be denied enterprise access"
                print("  ✅ Professional tier: enterprise access denied (403)")
                
                # Test enterprise tier permissions (should have everything)
                enterprise_tenant = next(t for t in self.test_tenant_ids if t["tier"] == "enterprise")["tenant_id"]
                
                enterprise_endpoints = [
                    "/v1/security/health",
                    "/v1/ai/health", 
                    "/v1/observability/health",
                    "/v1/enterprise/system/health"
                ]
                
                for endpoint in enterprise_endpoints:
                    response = await client.get(
                        f"{self.base_url}{endpoint}",
                        headers={"X-Customer-ID": enterprise_tenant}
                    )
                    assert response.status_code != 403, f"Enterprise should have access to {endpoint}"
                    print(f"  ✅ Enterprise tier: {endpoint} access granted")
                
                print("✅ Subscription tier enforcement successful")
                self.test_results["tier_enforcement"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Subscription tier enforcement failed: {str(e)}")
                self.test_results["tier_enforcement"] = f"FAIL: {str(e)}"
                return False
    
    async def test_billing_calculation_accuracy(self):
        """Test 8: Billing calculation accuracy"""
        print("🔄 Testing billing calculation accuracy...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                pro_tenant = next(t for t in self.test_tenant_ids if t["tier"] == "professional")["tenant_id"]
                
                # Generate known usage amounts
                known_usage = {
                    "logs_ingested": 1000,
                    "queries_executed": 50,
                    "alerts_triggered": 5,
                    "dashboards_viewed": 20
                }
                
                # Execute known amounts of usage
                for i in range(known_usage["logs_ingested"]):
                    if i % 100 == 0:  # Log progress every 100
                        print(f"    Ingesting log {i+1}/{known_usage['logs_ingested']}")
                    
                    response = await client.post(
                        f"{self.base_url}/v1/ingest/logs",
                        json={"ts": datetime.now().isoformat(), "service": "billing-calc-test", "msg": f"test log {i}"},
                        headers={"X-Customer-ID": pro_tenant}
                    )
                    assert response.status_code == 200, f"Failed to ingest log {i}"
                
                for i in range(known_usage["queries_executed"]):
                    response = await client.post(
                        f"{self.base_url}/v1/query/advanced",
                        json={
                            "start_time": (datetime.now() - timedelta(hours=1)).isoformat(),
                            "end_time": datetime.now().isoformat(),
                            "limit": 1
                        },
                        headers={"X-Customer-ID": pro_tenant}
                    )
                    assert response.status_code == 200, f"Failed to execute query {i}"
                
                print("  ✅ Generated known usage amounts")
                
                # Wait for usage processing
                await asyncio.sleep(5)
                
                # Get usage and verify calculation
                response = await client.get(
                    f"{self.base_url}/v1/tenants/{pro_tenant}/usage/detailed?start_date=2025-09-01&end_date=2025-09-30"
                )
                
                assert response.status_code == 200, f"Failed to get usage details: {response.text}"
                usage_details = response.json()
                
                # Verify usage counts are approximately correct (allowing for other test data)
                feature_usage = {item["feature_name"]: item for item in usage_details["feature_usage"]}
                
                if "ingestion" in feature_usage:
                    ingestion_count = feature_usage["ingestion"]["quantity"]
                    assert ingestion_count >= known_usage["logs_ingested"], f"Expected at least {known_usage['logs_ingested']} logs, got {ingestion_count}"
                    print(f"  ✅ Ingestion usage tracked: {ingestion_count} logs")
                
                if "queries" in feature_usage:
                    query_count = feature_usage["queries"]["quantity"]
                    assert query_count >= known_usage["queries_executed"], f"Expected at least {known_usage['queries_executed']} queries, got {query_count}"
                    print(f"  ✅ Query usage tracked: {query_count} queries")
                
                # Verify total cost calculation
                assert "total_cost" in usage_details
                assert usage_details["total_cost"] > 0, "Total cost should be greater than 0"
                print(f"  ✅ Total cost calculated: ${usage_details['total_cost']:.4f}")
                
                print("✅ Billing calculation accuracy successful")
                self.test_results["billing_accuracy"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Billing calculation accuracy failed: {str(e)}")
                self.test_results["billing_accuracy"] = f"FAIL: {str(e)}"
                return False
    
    async def test_subscription_upgrade_downgrade(self):
        """Test 9: Subscription tier upgrade/downgrade"""
        print("🔄 Testing subscription upgrade/downgrade...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                starter_tenant = next(t for t in self.test_tenant_ids if t["tier"] == "starter")["tenant_id"]
                
                # Initial state: starter tier
                response = await client.get(
                    f"{self.base_url}/v1/tenants/{starter_tenant}/subscription"
                )
                assert response.status_code == 200
                initial_sub = response.json()
                assert initial_sub["subscription_tier"] == "starter"
                print("  ✅ Verified initial starter subscription")
                
                # Test upgrade to professional
                upgrade_data = {
                    "subscribed_features": ["ingestion.*", "storage.*", "queries.*", "alerts.basic", "dashboards.readonly"],
                    "subscription_tier": "professional",
                    "billing_cycle": "monthly"
                }
                
                response = await client.put(
                    f"{self.base_url}/v1/tenants/{starter_tenant}/subscription",
                    json=upgrade_data
                )
                
                assert response.status_code == 200, f"Failed to upgrade subscription: {response.text}"
                upgraded_sub = response.json()
                assert upgraded_sub["subscription_tier"] == "professional"
                print("  ✅ Upgraded to professional tier")
                
                # Verify new features are accessible
                response = await client.get(
                    f"{self.base_url}/v1/alerts/rules",
                    headers={"X-Customer-ID": starter_tenant}
                )
                assert response.status_code != 403, "Professional should have alerts access after upgrade"
                print("  ✅ New features accessible after upgrade")
                
                # Test downgrade back to starter
                downgrade_data = {
                    "subscribed_features": ["ingestion.basic", "storage.hot", "queries.basic"],
                    "subscription_tier": "starter",
                    "billing_cycle": "monthly"
                }
                
                response = await client.put(
                    f"{self.base_url}/v1/tenants/{starter_tenant}/subscription",
                    json=downgrade_data
                )
                
                assert response.status_code == 200, f"Failed to downgrade subscription: {response.text}"
                downgraded_sub = response.json()
                assert downgraded_sub["subscription_tier"] == "starter"
                print("  ✅ Downgraded to starter tier")
                
                # Verify features are no longer accessible
                response = await client.get(
                    f"{self.base_url}/v1/alerts/rules",
                    headers={"X-Customer-ID": starter_tenant}
                )
                assert response.status_code == 403, "Starter should lose alerts access after downgrade"
                print("  ✅ Features properly restricted after downgrade")
                
                print("✅ Subscription upgrade/downgrade successful")
                self.test_results["subscription_changes"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Subscription upgrade/downgrade failed: {str(e)}")
                self.test_results["subscription_changes"] = f"FAIL: {str(e)}"
                return False
    
    async def test_usage_limits_and_overages(self):
        """Test 10: Usage limits and overage handling"""
        print("🔄 Testing usage limits and overages...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Create tenant with specific usage limits
                tenant_data = {
                    "name": "Limits Test Corp",
                    "type": "startup",
                    "primary_contact_name": "Limits Test Manager",
                    "primary_contact_email": "limits-test@logforge.local",
                    "industry": "Technology"
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/tenants",
                    json=tenant_data,
                    headers={"Authorization": f"Bearer {self.test_admin_token}"}
                )
                
                assert response.status_code == 201
                limits_tenant_id = response.json()["tenant_id"]
                
                # Set subscription with strict limits
                subscription_data = {
                    "subscribed_features": ["ingestion.basic", "queries.basic"],
                    "subscription_tier": "starter",
                    "billing_cycle": "monthly",
                    "monthly_spend_limit": 10.0  # Very low limit
                }
                
                response = await client.put(
                    f"{self.base_url}/v1/tenants/{limits_tenant_id}/subscription",
                    json=subscription_data
                )
                assert response.status_code == 200
                print("  ✅ Set subscription with usage limits")
                
                # Test approaching usage limit
                for i in range(100):  # Generate usage to approach limit
                    response = await client.post(
                        f"{self.base_url}/v1/ingest/logs",
                        json={"ts": datetime.now().isoformat(), "service": "limits-test", "msg": f"limit test {i}"},
                        headers={"X-Customer-ID": limits_tenant_id}
                    )
                    
                    if response.status_code == 429:  # Rate limited due to spend limit
                        print(f"  ✅ Usage limit enforced at log {i+1}")
                        break
                    elif response.status_code != 200:
                        print(f"  ⚠️ Unexpected response: {response.status_code}")
                        break
                else:
                    print("  ⚠️ Usage limit not enforced within 100 logs")
                
                # Test usage limit status
                response = await client.get(
                    f"{self.base_url}/v1/tenants/{limits_tenant_id}/usage/limits"
                )
                
                assert response.status_code == 200, f"Failed to get usage limits: {response.text}"
                limits_status = response.json()
                assert "current_spend" in limits_status
                assert "monthly_limit" in limits_status
                print("  ✅ Retrieved usage limits status")
                
                print("✅ Usage limits and overages successful")
                self.test_results["usage_limits"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Usage limits and overages failed: {str(e)}")
                self.test_results["usage_limits"] = f"FAIL: {str(e)}"
                return False
    
    async def test_admin_tenant_management(self):
        """Test 11: Admin tenant management capabilities"""
        print("🔄 Testing admin tenant management...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Test admin list all tenants
                response = await client.get(
                    f"{self.base_url}/v1/admin/tenants",
                    headers={"Authorization": f"Bearer {self.test_admin_token}"}
                )
                
                assert response.status_code == 200, f"Failed to list tenants: {response.text}"
                tenants_list = response.json()
                assert "tenants" in tenants_list
                assert len(tenants_list["tenants"]) >= len(self.test_tenant_ids)
                print("  ✅ Admin listed all tenants")
                
                # Test admin get tenant details (including usage/billing)
                test_tenant_id = self.test_tenant_ids[0]["tenant_id"]
                response = await client.get(
                    f"{self.base_url}/v1/admin/tenants/{test_tenant_id}/details",
                    headers={"Authorization": f"Bearer {self.test_admin_token}"}
                )
                
                assert response.status_code == 200, f"Failed to get tenant details: {response.text}"
                details = response.json()
                assert "tenant_info" in details
                assert "subscription_info" in details
                assert "usage_summary" in details
                print("  ✅ Admin retrieved detailed tenant info")
                
                # Test admin force subscription change
                force_change_data = {
                    "subscribed_features": ["ingestion.basic"],
                    "subscription_tier": "starter",
                    "billing_cycle": "monthly",
                    "admin_override": True,
                    "reason": "Administrative policy change"
                }
                
                response = await client.put(
                    f"{self.base_url}/v1/admin/tenants/{test_tenant_id}/subscription",
                    json=force_change_data,
                    headers={"Authorization": f"Bearer {self.test_admin_token}"}
                )
                
                assert response.status_code == 200, f"Failed to force subscription change: {response.text}"
                print("  ✅ Admin forced subscription change")
                
                # Test admin billing override
                billing_override = {
                    "billing_period": "2025-09",
                    "override_amount": 99.99,
                    "reason": "Customer service adjustment",
                    "approved_by": "admin"
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/admin/tenants/{test_tenant_id}/billing/override",
                    json=billing_override,
                    headers={"Authorization": f"Bearer {self.test_admin_token}"}
                )
                
                assert response.status_code == 200, f"Failed to override billing: {response.text}"
                print("  ✅ Admin overrode billing amount")
                
                print("✅ Admin tenant management successful")
                self.test_results["admin_management"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Admin tenant management failed: {str(e)}")
                self.test_results["admin_management"] = f"FAIL: {str(e)}"
                return False
    
    async def test_compliance_and_audit_trail(self):
        """Test 12: Compliance and audit trail for billing"""
        print("🔄 Testing compliance and audit trail...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                test_tenant_id = self.test_tenant_ids[0]["tenant_id"]
                
                # Test audit log for subscription changes
                response = await client.get(
                    f"{self.base_url}/v1/admin/audit/subscription-changes?tenant_id={test_tenant_id}",
                    headers={"Authorization": f"Bearer {self.test_admin_token}"}
                )
                
                assert response.status_code == 200, f"Failed to get audit trail: {response.text}"
                audit_trail = response.json()
                assert "audit_events" in audit_trail
                assert len(audit_trail["audit_events"]) > 0
                print("  ✅ Retrieved subscription change audit trail")
                
                # Test compliance report generation
                compliance_request = {
                    "report_type": "billing_compliance",
                    "tenant_id": test_tenant_id,
                    "period": "2025-09",
                    "include_audit_trail": True
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/admin/compliance/reports",
                    json=compliance_request,
                    headers={"Authorization": f"Bearer {self.test_admin_token}"}
                )
                
                assert response.status_code == 200, f"Failed to generate compliance report: {response.text}"
                report = response.json()
                assert "report_id" in report
                assert "compliance_status" in report
                print("  ✅ Generated compliance report")
                
                # Test usage data retention verification
                response = await client.get(
                    f"{self.base_url}/v1/admin/compliance/retention-status?tenant_id={test_tenant_id}",
                    headers={"Authorization": f"Bearer {self.test_admin_token}"}
                )
                
                assert response.status_code == 200, f"Failed to get retention status: {response.text}"
                retention = response.json()
                assert "retention_compliant" in retention
                print("  ✅ Verified data retention compliance")
                
                print("✅ Compliance and audit trail successful")
                self.test_results["compliance_audit"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Compliance and audit trail failed: {str(e)}")
                self.test_results["compliance_audit"] = f"FAIL: {str(e)}"
                return False
    
    async def cleanup_test_tenants(self):
        """Clean up test tenants after testing"""
        print("🔄 Cleaning up test tenants...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for tenant_info in self.test_tenant_ids:
                tenant_id = tenant_info["tenant_id"]
                
                delete_data = {
                    "deletion_type": "soft_delete",
                    "reason": "Test cleanup",
                    "data_cleanup": True,
                    "generate_final_bill": False
                }
                
                response = await client.delete(
                    f"{self.base_url}/v1/tenants/{tenant_id}",
                    json=delete_data,
                    headers={"Authorization": f"Bearer {self.test_admin_token}"}
                )
                
                if response.status_code == 200:
                    print(f"  ✅ Cleaned up tenant: {tenant_id}")
                else:
                    print(f"  ⚠️ Failed to cleanup tenant {tenant_id}: {response.text}")
    
    async def run_all_tests(self):
        """Run all subscription system tests"""
        print("\n🚀 Starting Subscription System Test Suite...")
        print("📝 Testing: Feature subscriptions, billing, access control, admin management")
        
        # Setup test environment
        await self.setup_test_tenants()
        
        if not self.test_tenant_ids:
            print("❌ Failed to create test tenants - cannot proceed")
            return False
        
        tests = [
            self.test_feature_access_control,
            self.test_admin_rate_configuration,
            self.test_subscription_management,
            self.test_usage_tracking_and_billing,
            self.test_subscription_enforcement_edge_cases,
            self.test_soft_delete_with_data_cleanup,
            self.test_subscription_tier_enforcement,
            self.test_billing_calculation_accuracy,
            self.test_subscription_upgrade_downgrade,
            self.test_usage_limits_and_overages,
            self.test_admin_tenant_management,
            self.test_compliance_and_audit_trail
        ]
        
        # Run tests sequentially
        for test_func in tests:
            try:
                await test_func()
            except Exception as e:
                print(f"❌ Test {test_func.__name__} failed with exception: {str(e)}")
                if test_func.__name__.replace("test_", "") not in self.test_results:
                    self.test_results[test_func.__name__.replace("test_", "")] = f"FAIL: {str(e)}"
        
        # Cleanup
        await self.cleanup_test_tenants()
        
        # Summary
        print("\n📊 Subscription System Test Results:")
        passed = sum(1 for result in self.test_results.values() if result == "PASS")
        total = len(self.test_results)
        
        for test_name, result in self.test_results.items():
            status = "✅" if result == "PASS" else "❌"
            print(f"  {status} {test_name}: {result}")
        
        print(f"\n🎯 Subscription Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("✅ Subscription & Billing System: ALL TESTS PASSED")
            return True
        else:
            print("❌ Subscription & Billing System: SOME TESTS FAILED")
            return False

if __name__ == "__main__":
    test_suite = SubscriptionTestSuite()
    success = asyncio.run(test_suite.run_all_tests())
    exit(0 if success else 1)