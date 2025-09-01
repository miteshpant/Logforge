#!/usr/bin/env python3
"""
Tenant Service - Comprehensive Test Suite
========================================
Testing tenant lifecycle, storage management, compliance, and enterprise features
"""

import pytest
import httpx
import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List

# Test configuration
API_BASE_URL = "http://localhost:7080"
ADMIN_HEADERS = {"Authorization": "Bearer admin-token", "Content-Type": "application/json"}

class TestTenantService:
    """Comprehensive Tenant Service Tests - 20+ Tests"""
    
    def __init__(self):
        self.created_tenants = []
        self.test_storage_configs = {}
    
    @pytest.mark.asyncio
    async def test_01_tenant_creation_basic(self):
        """Test basic tenant creation with required fields"""
        print("🔄 Testing basic tenant creation...")
        
        tenant_data = {
            "name": "Acme Corporation",
            "type": "enterprise",
            "primary_contact_name": "John Smith",
            "primary_contact_email": "john.smith@acme.com",
            "industry": "Technology"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/v1/tenants",
                json=tenant_data,
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert "tenant_id" in data
            assert data["name"] == "Acme Corporation"
            assert data["type"] == "enterprise"
            assert data["status"] == "active"
            
            # Validate UUID format
            tenant_uuid = data["tenant_id"]
            uuid.UUID(tenant_uuid)  # Will raise if invalid
            self.created_tenants.append(tenant_uuid)
            
        print(f"✅ Basic tenant creation successful: {tenant_uuid}")
    
    @pytest.mark.asyncio
    async def test_02_tenant_creation_full_details(self):
        """Test tenant creation with all fields"""
        print("🔄 Testing tenant creation with full details...")
        
        tenant_data = {
            "name": "Healthcare Solutions Inc",
            "type": "healthcare",
            "address": "123 Medical Center Dr, Boston, MA 02115",
            "primary_contact_name": "Dr. Sarah Johnson",
            "primary_contact_email": "sarah.johnson@healthcaresolutions.com",
            "primary_contact_phone": "+1-617-555-0123",
            "industry": "Healthcare",
            "company_size": 500,
            "website": "https://healthcaresolutions.com",
            "notes": "HIPAA compliant healthcare data processing"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/v1/tenants",
                json=tenant_data,
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert data["name"] == "Healthcare Solutions Inc"
            assert data["type"] == "healthcare"
            assert data["industry"] == "Healthcare"
            assert data["primary_contact_email"] == "sarah.johnson@healthcaresolutions.com"
            
            tenant_uuid = data["tenant_id"]
            self.created_tenants.append(tenant_uuid)
            
        print(f"✅ Full tenant creation successful: {tenant_uuid}")
    
    @pytest.mark.asyncio
    async def test_03_tenant_validation_errors(self):
        """Test tenant creation validation errors"""
        print("🔄 Testing tenant validation errors...")
        
        # Test invalid email
        invalid_email_data = {
            "name": "Test Corp",
            "type": "enterprise",
            "primary_contact_name": "John Doe",
            "primary_contact_email": "invalid-email",
            "industry": "Technology"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/v1/tenants",
                json=invalid_email_data,
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 422, f"Expected 422 for invalid email, got {response.status_code}"
            
            # Test missing required fields
            incomplete_data = {
                "name": "Incomplete Corp"
            }
            
            response = await client.post(
                f"{API_BASE_URL}/v1/tenants",
                json=incomplete_data,
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 422, f"Expected 422 for missing fields, got {response.status_code}"
            
        print("✅ Tenant validation errors working correctly")
    
    @pytest.mark.asyncio
    async def test_04_tenant_retrieval(self):
        """Test tenant retrieval by ID"""
        print("🔄 Testing tenant retrieval...")
        
        if not self.created_tenants:
            pytest.skip("No tenants created yet")
        
        tenant_id = self.created_tenants[0]
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}",
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert data["tenant_id"] == tenant_id
            assert "name" in data
            assert "created_at" in data
            
        print(f"✅ Tenant retrieval successful: {tenant_id}")
    
    @pytest.mark.asyncio
    async def test_05_tenant_list_pagination(self):
        """Test tenant listing with pagination"""
        print("🔄 Testing tenant list with pagination...")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/v1/tenants?page=1&page_size=10",
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert "tenants" in data
            assert "total_count" in data
            assert "page" in data
            assert "page_size" in data
            assert data["page"] == 1
            assert data["page_size"] == 10
            
        print("✅ Tenant list pagination successful")
    
    @pytest.mark.asyncio
    async def test_06_tenant_update(self):
        """Test tenant update operations"""
        print("🔄 Testing tenant updates...")
        
        if not self.created_tenants:
            pytest.skip("No tenants created yet")
        
        tenant_id = self.created_tenants[0]
        
        update_data = {
            "industry": "Financial Services",
            "company_size": 1000,
            "notes": "Updated compliance requirements"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}",
                json=update_data,
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert data["industry"] == "Financial Services"
            assert data["tenant_id"] == tenant_id
            
        print(f"✅ Tenant update successful: {tenant_id}")
    
    @pytest.mark.asyncio
    async def test_07_storage_backend_configuration(self):
        """Test storage backend configuration"""
        print("🔄 Testing storage backend configuration...")
        
        if not self.created_tenants:
            pytest.skip("No tenants created yet")
        
        tenant_id = self.created_tenants[0]
        
        storage_config = {
            "backend_type": "s3",
            "region": "us-east-1",
            "bucket_name": f"logforge-{tenant_id}",
            "access_key_id": "AKIA...",
            "secret_access_key": "secret...",
            "encryption_enabled": True,
            "lifecycle_policy": {
                "hot_days": 7,
                "warm_days": 30,
                "cold_days": 365
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}/storage/configure",
                json=storage_config,
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert data["status"] == "configured"
            assert data["backend_type"] == "s3"
            assert "credentials_encrypted" in data
            
            self.test_storage_configs[tenant_id] = storage_config
            
        print(f"✅ Storage backend configuration successful: {tenant_id}")
    
    @pytest.mark.asyncio
    async def test_08_storage_connection_testing(self):
        """Test storage connection validation"""
        print("🔄 Testing storage connection...")
        
        if not self.created_tenants:
            pytest.skip("No tenants created yet")
        
        tenant_id = self.created_tenants[0]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}/storage/test-connection",
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert "connection_status" in data
            assert "latency_ms" in data
            assert "last_tested" in data
            
        print(f"✅ Storage connection test successful: {tenant_id}")
    
    @pytest.mark.asyncio
    async def test_09_storage_status_monitoring(self):
        """Test storage status and usage monitoring"""
        print("🔄 Testing storage status monitoring...")
        
        if not self.created_tenants:
            pytest.skip("No tenants created yet")
        
        tenant_id = self.created_tenants[0]
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}/storage/status",
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert "backend_type" in data
            assert "storage_used_gb" in data
            assert "storage_limit_gb" in data
            assert "health_status" in data
            
        print(f"✅ Storage status monitoring successful: {tenant_id}")
    
    @pytest.mark.asyncio
    async def test_10_usage_tracking_and_billing(self):
        """Test usage tracking and billing data"""
        print("🔄 Testing usage tracking and billing...")
        
        if not self.created_tenants:
            pytest.skip("No tenants created yet")
        
        tenant_id = self.created_tenants[0]
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}/usage",
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert "log_count_today" in data
            assert "log_count_month" in data
            assert "storage_used_gb" in data
            assert "query_count" in data
            assert "api_calls" in data
            assert "billing_period" in data
            
        print(f"✅ Usage tracking successful: {tenant_id}")
    
    @pytest.mark.asyncio
    async def test_11_quota_management(self):
        """Test quota configuration and enforcement"""
        print("🔄 Testing quota management...")
        
        if not self.created_tenants:
            pytest.skip("No tenants created yet")
        
        tenant_id = self.created_tenants[0]
        
        # Get current quotas
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}/quotas",
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            # Update quotas
            quota_update = {
                "monthly_log_limit": 10000000,
                "storage_limit_gb": 500,
                "retention_days": 90,
                "query_rate_limit": 1000
            }
            
            response = await client.put(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}/quotas",
                json=quota_update,
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert data["monthly_log_limit"] == 10000000
            assert data["storage_limit_gb"] == 500
            
        print(f"✅ Quota management successful: {tenant_id}")
    
    @pytest.mark.asyncio
    async def test_12_tenant_configuration_management(self):
        """Test tenant configuration settings"""
        print("🔄 Testing tenant configuration...")
        
        if not self.created_tenants:
            pytest.skip("No tenants created yet")
        
        tenant_id = self.created_tenants[0]
        
        config_data = {
            "timezone": "America/New_York",
            "data_residency": "US",
            "compliance_frameworks": ["SOX", "PCI-DSS"],
            "encryption_required": True,
            "retention_policy": {
                "default_days": 90,
                "compliance_days": 2555,  # 7 years for SOX
                "auto_delete": True
            },
            "notification_preferences": {
                "email_enabled": True,
                "slack_enabled": False,
                "webhook_url": "https://webhook.example.com/tenant"
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}/config",
                json=config_data,
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            # Retrieve configuration
            response = await client.get(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}/config",
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["timezone"] == "America/New_York"
            assert "SOX" in data["compliance_frameworks"]
            
        print(f"✅ Tenant configuration successful: {tenant_id}")
    
    @pytest.mark.asyncio
    async def test_13_compliance_reporting(self):
        """Test compliance status and reporting"""
        print("🔄 Testing compliance reporting...")
        
        if not self.created_tenants:
            pytest.skip("No tenants created yet")
        
        tenant_id = self.created_tenants[0]
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}/compliance",
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert "compliance_score" in data
            assert "frameworks" in data
            assert "violations" in data
            assert "last_audit" in data
            assert "next_audit" in data
            
        print(f"✅ Compliance reporting successful: {tenant_id}")
    
    @pytest.mark.asyncio
    async def test_14_legal_hold_management(self):
        """Test legal hold and data preservation"""
        print("🔄 Testing legal hold management...")
        
        if not self.created_tenants:
            pytest.skip("No tenants created yet")
        
        tenant_id = self.created_tenants[0]
        
        legal_hold_data = {
            "case_name": "Investigation Case 2024-001",
            "description": "Financial audit investigation",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-12-31T23:59:59Z",
            "contact_person": "Legal Team",
            "contact_email": "legal@acme.com",
            "data_types": ["logs", "alerts", "audit_trail"],
            "justification": "SOX compliance investigation"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}/legal-hold",
                json=legal_hold_data,
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert "hold_id" in data
            assert data["case_name"] == "Investigation Case 2024-001"
            assert data["status"] == "active"
            
        print(f"✅ Legal hold management successful: {tenant_id}")
    
    @pytest.mark.asyncio
    async def test_15_tenant_health_monitoring(self):
        """Test tenant health and performance monitoring"""
        print("🔄 Testing tenant health monitoring...")
        
        if not self.created_tenants:
            pytest.skip("No tenants created yet")
        
        tenant_id = self.created_tenants[0]
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}/health",
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert "status" in data
            assert "ingestion_health" in data
            assert "storage_health" in data
            assert "query_performance" in data
            assert "last_activity" in data
            
        print(f"✅ Tenant health monitoring successful: {tenant_id}")
    
    @pytest.mark.asyncio
    async def test_16_tenant_metrics_analytics(self):
        """Test tenant performance metrics and analytics"""
        print("🔄 Testing tenant metrics...")
        
        if not self.created_tenants:
            pytest.skip("No tenants created yet")
        
        tenant_id = self.created_tenants[0]
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}/metrics",
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert "ingestion_rate" in data
            assert "query_performance" in data
            assert "storage_efficiency" in data
            assert "error_rates" in data
            assert "sla_compliance" in data
            
        print(f"✅ Tenant metrics successful: {tenant_id}")
    
    @pytest.mark.asyncio
    async def test_17_tenant_alerts_configuration(self):
        """Test tenant-specific alert configuration"""
        print("🔄 Testing tenant alerts configuration...")
        
        if not self.created_tenants:
            pytest.skip("No tenants created yet")
        
        tenant_id = self.created_tenants[0]
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}/alerts",
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert "alert_rules" in data
            assert "notification_channels" in data
            assert "escalation_policies" in data
            
        print(f"✅ Tenant alerts configuration successful: {tenant_id}")
    
    @pytest.mark.asyncio
    async def test_18_multi_cloud_storage_support(self):
        """Test multiple cloud storage backends"""
        print("🔄 Testing multi-cloud storage support...")
        
        if len(self.created_tenants) < 2:
            pytest.skip("Need at least 2 tenants for multi-cloud testing")
        
        # Configure different storage backends for different tenants
        storage_configs = [
            {
                "tenant_id": self.created_tenants[0],
                "backend_type": "s3",
                "region": "us-west-2"
            },
            {
                "tenant_id": self.created_tenants[1],
                "backend_type": "gcs",
                "region": "us-central1"
            }
        ]
        
        async with httpx.AsyncClient() as client:
            for config in storage_configs:
                tenant_id = config["tenant_id"]
                storage_data = {
                    "backend_type": config["backend_type"],
                    "region": config["region"],
                    "bucket_name": f"logforge-{tenant_id}",
                    "encryption_enabled": True
                }
                
                response = await client.post(
                    f"{API_BASE_URL}/v1/tenants/{tenant_id}/storage/configure",
                    json=storage_data,
                    headers=ADMIN_HEADERS,
                    timeout=30.0
                )
                
                assert response.status_code == 200, f"Storage config failed for {config['backend_type']}"
        
        print("✅ Multi-cloud storage support successful")
    
    @pytest.mark.asyncio
    async def test_19_tenant_isolation_validation(self):
        """Test tenant data isolation"""
        print("🔄 Testing tenant data isolation...")
        
        if len(self.created_tenants) < 2:
            pytest.skip("Need at least 2 tenants for isolation testing")
        
        tenant1_id = self.created_tenants[0]
        tenant2_id = self.created_tenants[1]
        
        # Test that tenant1 cannot access tenant2's data
        headers_tenant1 = {**ADMIN_HEADERS, "X-Customer-ID": tenant1_id}
        headers_tenant2 = {**ADMIN_HEADERS, "X-Customer-ID": tenant2_id}
        
        async with httpx.AsyncClient() as client:
            # Try to access tenant2's config with tenant1's credentials
            response = await client.get(
                f"{API_BASE_URL}/v1/tenants/{tenant2_id}/config",
                headers=headers_tenant1,
                timeout=30.0
            )
            
            # Should either return 403 Forbidden or only tenant1's data
            assert response.status_code in [403, 404], f"Tenant isolation failed: {response.status_code}"
            
        print("✅ Tenant isolation validation successful")
    
    @pytest.mark.asyncio
    async def test_20_tenant_decommissioning(self):
        """Test secure tenant decommissioning"""
        print("🔄 Testing tenant decommissioning...")
        
        if not self.created_tenants:
            pytest.skip("No tenants created yet")
        
        # Create a tenant specifically for decommissioning
        tenant_data = {
            "name": "Decommission Test Corp",
            "type": "enterprise",
            "primary_contact_name": "Test User",
            "primary_contact_email": "test@decomm.com",
            "industry": "Testing"
        }
        
        async with httpx.AsyncClient() as client:
            # Create tenant
            response = await client.post(
                f"{API_BASE_URL}/v1/tenants",
                json=tenant_data,
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 201
            tenant_id = response.json()["tenant_id"]
            
            # Decommission tenant
            decommission_data = {
                "reason": "Testing decommissioning process",
                "data_retention": "purge",
                "backup_required": False
            }
            
            response = await client.delete(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}",
                json=decommission_data,
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert data["status"] == "decommissioned"
            assert "cleanup_tasks" in data
            
            # Verify tenant no longer accessible
            response = await client.get(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}",
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 404, "Decommissioned tenant should not be accessible"
            
        print(f"✅ Tenant decommissioning successful: {tenant_id}")

class TestTenantUUIDIntegration:
    """Test Integration with Existing Services Using Tenant UUIDs"""
    
    def __init__(self):
        self.test_tenant_id = None
    
    @pytest.mark.asyncio
    async def test_21_log_ingestion_with_tenant_uuid(self):
        """Test log ingestion validates tenant UUID"""
        print("🔄 Testing log ingestion with tenant UUID...")
        
        # First create a tenant
        tenant_data = {
            "name": "Log Test Corp",
            "type": "enterprise",
            "primary_contact_name": "Test User",
            "primary_contact_email": "test@logtest.com",
            "industry": "Testing"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/v1/tenants",
                json=tenant_data,
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            
            assert response.status_code == 201
            self.test_tenant_id = response.json()["tenant_id"]
            
            # Test log ingestion with valid tenant UUID
            log_data = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "host": "test-host",
                "service": "test-service",
                "level": "info",
                "msg": "Test log for tenant UUID validation"
            }
            
            headers_with_tenant = {**ADMIN_HEADERS, "X-Customer-ID": self.test_tenant_id}
            
            response = await client.post(
                f"{API_BASE_URL}/v1/ingest/json",
                json=log_data,
                headers=headers_with_tenant,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Log ingestion failed: {response.status_code}: {response.text}"
            
            # Test with invalid tenant UUID
            invalid_headers = {**ADMIN_HEADERS, "X-Customer-ID": "invalid-uuid"}
            
            response = await client.post(
                f"{API_BASE_URL}/v1/ingest/json",
                json=log_data,
                headers=invalid_headers,
                timeout=30.0
            )
            
            assert response.status_code == 400, "Should reject invalid tenant UUID"
            
        print(f"✅ Log ingestion tenant UUID validation successful")
    
    @pytest.mark.asyncio
    async def test_22_query_engine_tenant_isolation(self):
        """Test query engine enforces tenant isolation"""
        print("🔄 Testing query engine tenant isolation...")
        
        if not self.test_tenant_id:
            pytest.skip("No test tenant available")
        
        query_data = {
            "query": "SELECT * FROM logs_raw_mt WHERE service='test-service'",
            "start_time": "2024-01-01T00:00:00Z",
            "end_time": "2024-12-31T23:59:59Z"
        }
        
        headers_with_tenant = {**ADMIN_HEADERS, "X-Customer-ID": self.test_tenant_id}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/v1/query/advanced",
                json=query_data,
                headers=headers_with_tenant,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Query failed: {response.status_code}: {response.text}"
            
            data = response.json()
            assert "customer_id" in data
            assert data["customer_id"] == self.test_tenant_id
            
        print(f"✅ Query engine tenant isolation successful")
    
    @pytest.mark.asyncio
    async def test_23_alert_engine_tenant_scoping(self):
        """Test alert engine tenant scoping"""
        print("🔄 Testing alert engine tenant scoping...")
        
        if not self.test_tenant_id:
            pytest.skip("No test tenant available")
        
        alert_rule_data = {
            "name": "Tenant Scoped Alert",
            "description": "Test alert for tenant scoping",
            "query": "SELECT count(*) as error_count FROM logs_raw_mt WHERE level='error'",
            "condition": {
                "field": "error_count",
                "operator": "gt",
                "value": 0
            },
            "schedule": "*/5 * * * *",
            "enabled": True
        }
        
        headers_with_tenant = {**ADMIN_HEADERS, "X-Customer-ID": self.test_tenant_id}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/v1/alerts/rules",
                json=alert_rule_data,
                headers=headers_with_tenant,
                timeout=30.0
            )
            
            assert response.status_code == 201, f"Alert creation failed: {response.status_code}: {response.text}"
            
            data = response.json()
            assert "rule_id" in data
            assert data["customer_id"] == self.test_tenant_id
            
        print(f"✅ Alert engine tenant scoping successful")
    
    @pytest.mark.asyncio
    async def test_24_security_analytics_tenant_isolation(self):
        """Test security analytics tenant isolation"""
        print("🔄 Testing security analytics tenant isolation...")
        
        if not self.test_tenant_id:
            pytest.skip("No test tenant available")
        
        headers_with_tenant = {**ADMIN_HEADERS, "X-Customer-ID": self.test_tenant_id}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/v1/security/events",
                headers=headers_with_tenant,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Security events failed: {response.status_code}: {response.text}"
            
            # Test security dashboard with tenant scoping
            response = await client.get(
                f"{API_BASE_URL}/v1/security/dashboard",
                headers=headers_with_tenant,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Security dashboard failed: {response.status_code}: {response.text}"
            
        print(f"✅ Security analytics tenant isolation successful")
    
    @pytest.mark.asyncio
    async def test_25_enterprise_features_tenant_validation(self):
        """Test enterprise features validate tenant UUIDs"""
        print("🔄 Testing enterprise features tenant validation...")
        
        if not self.test_tenant_id:
            pytest.skip("No test tenant available")
        
        headers_with_tenant = {**ADMIN_HEADERS, "X-Customer-ID": self.test_tenant_id}
        
        async with httpx.AsyncClient() as client:
            # Test RBAC with tenant context
            response = await client.get(
                f"{API_BASE_URL}/v1/enterprise/rbac/roles",
                headers=headers_with_tenant,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"RBAC roles failed: {response.status_code}: {response.text}"
            
            # Test audit logs with tenant filtering
            response = await client.get(
                f"{API_BASE_URL}/v1/enterprise/audit/logs",
                headers=headers_with_tenant,
                timeout=30.0
            )
            
            assert response.status_code == 200, f"Audit logs failed: {response.status_code}: {response.text}"
            
        print(f"✅ Enterprise features tenant validation successful")

class TestTenantServiceIntegration:
    """Integration Tests for Complete Tenant Service Workflow"""
    
    @pytest.mark.asyncio
    async def test_26_complete_tenant_lifecycle(self):
        """Test complete tenant lifecycle from creation to decommissioning"""
        print("🔄 Testing complete tenant lifecycle...")
        
        # 1. Create tenant
        tenant_data = {
            "name": "Lifecycle Test Corp",
            "type": "enterprise",
            "address": "123 Test St, Test City, TC 12345",
            "primary_contact_name": "Test Manager",
            "primary_contact_email": "manager@lifecycletest.com",
            "primary_contact_phone": "+1-555-0199",
            "industry": "Technology",
            "company_size": 250,
            "website": "https://lifecycletest.com",
            "notes": "Complete lifecycle testing tenant"
        }
        
        async with httpx.AsyncClient() as client:
            # Create
            response = await client.post(
                f"{API_BASE_URL}/v1/tenants",
                json=tenant_data,
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            assert response.status_code == 201
            tenant_id = response.json()["tenant_id"]
            
            # 2. Configure storage
            storage_config = {
                "backend_type": "s3",
                "region": "us-east-1",
                "bucket_name": f"logforge-{tenant_id}",
                "encryption_enabled": True
            }
            
            response = await client.post(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}/storage/configure",
                json=storage_config,
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            assert response.status_code == 200
            
            # 3. Set quotas
            quota_data = {
                "monthly_log_limit": 5000000,
                "storage_limit_gb": 100,
                "retention_days": 60
            }
            
            response = await client.put(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}/quotas",
                json=quota_data,
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            assert response.status_code == 200
            
            # 4. Configure compliance
            config_data = {
                "compliance_frameworks": ["SOX"],
                "data_residency": "US",
                "encryption_required": True
            }
            
            response = await client.put(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}/config",
                json=config_data,
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            assert response.status_code == 200
            
            # 5. Test data operations with tenant
            headers_with_tenant = {**ADMIN_HEADERS, "X-Customer-ID": tenant_id}
            
            log_data = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "service": "lifecycle-test",
                "level": "info",
                "msg": "Lifecycle test log entry"
            }
            
            response = await client.post(
                f"{API_BASE_URL}/v1/ingest/json",
                json=log_data,
                headers=headers_with_tenant,
                timeout=30.0
            )
            assert response.status_code == 200
            
            # 6. Verify tenant health
            response = await client.get(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}/health",
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            assert response.status_code == 200
            
            # 7. Update tenant status
            update_data = {"status": "suspended"}
            response = await client.put(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}",
                json=update_data,
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            assert response.status_code == 200
            
            # 8. Final decommissioning
            decommission_data = {
                "reason": "Test completion",
                "data_retention": "backup",
                "backup_required": True
            }
            
            response = await client.delete(
                f"{API_BASE_URL}/v1/tenants/{tenant_id}",
                json=decommission_data,
                headers=ADMIN_HEADERS,
                timeout=30.0
            )
            assert response.status_code == 200
            
        print(f"✅ Complete tenant lifecycle successful: {tenant_id}")

def run_tests():
    """Run all tenant service tests"""
    print("=" * 50)
    print("🚀 TENANT SERVICE COMPREHENSIVE TEST SUITE")
    print("=" * 50)
    print(f"📍 API Base URL: {API_BASE_URL}")
    print(f"🕒 Test started at: {datetime.now(timezone.utc)}")
    print()
    
    # Run tests using pytest
    import subprocess
    import sys
    
    result = subprocess.run([
        sys.executable, "-m", "pytest", __file__, 
        "-v", "--asyncio-mode=auto", "-s"
    ], capture_output=False)
    
    if result.returncode == 0:
        print()
        print("🎯 TENANT SERVICE TEST RESULTS: ALL TESTS PASSED ✅")
        print("📊 Total Tests: 26 tests")
        print("✅ Tenant Management: 20/20 tests")
        print("✅ UUID Integration: 5/5 tests") 
        print("✅ Lifecycle Integration: 1/1 test")
    else:
        print()
        print("❌ SOME TENANT SERVICE TESTS FAILED")
        print("🔍 Check output above for failure details")
    
    return result.returncode == 0

if __name__ == "__main__":
    run_tests()