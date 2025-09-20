#!/usr/bin/env python3
"""
Comprehensive Tenant Router Test Suite
Tests all tenant router endpoints and validates API responses based on actual router implementation
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

class TenantRouterTestSuite(BaseTestSuite):
    """Comprehensive test suite for tenant router endpoints"""

    def __init__(self):
        super().__init__("TenantRouter")
        self.created_tenant_ids = []  # Track created tenants for cleanup

    async def test_tenant_crud_operations(self):
        """Test tenant CRUD operations: POST, GET, PUT, DELETE /v1/tenants"""
        print("\n🧪 Testing Tenant CRUD Operations...")

        try:
            # 1. Create a new tenant
            tenant_create_request = {
                "name": f"Test Organization {self.test_id}",
                "type": "enterprise",
                "primary_contact_name": "John Smith",
                "primary_contact_email": f"john.smith+{self.test_id}@example.com",
                "industry": "technology"
            }

            # Create tenant
            create_response = await self.make_authenticated_request(
                "POST",
                "/v1/tenants",
                json=tenant_create_request
            )

            assert create_response.status_code == 201, f"Expected 201, got {create_response.status_code}: {create_response.text}"
            create_data = create_response.json()

            # Debug: Print actual response data
            print(f"\n🔍 DEBUG: Tenant Create Request:")
            print(f"   Request data: {tenant_create_request}")
            print(f"\n🔍 DEBUG: Tenant Create Response:")
            print(f"   Status code: {create_response.status_code}")
            print(f"   Response data: {create_data}")
            print(f"   Available fields: {list(create_data.keys())}")

            # Validate tenant creation response
            required_fields = ["tenant_id", "name", "type", "status", "primary_contact_name", "primary_contact_email", "industry", "created_at", "updated_at"]
            print(f"\n🔍 DEBUG: Expected fields: {required_fields}")
            print(f"🔍 DEBUG: Checking each field:")
            for field in required_fields:
                field_present = field in create_data
                field_value = create_data.get(field, "NOT_FOUND")
                print(f"   - {field}: {'✅' if field_present else '❌'} = {field_value}")
                assert field in create_data, f"Missing required field: {field}"

            tenant_id = create_data["tenant_id"]
            self.created_tenant_ids.append(tenant_id)
            assert create_data["name"] == tenant_create_request["name"]
            assert create_data["type"] == tenant_create_request["type"]

            # 2. Get tenant by ID
            print(f"\n🔍 DEBUG: Getting tenant by ID: {tenant_id}")
            get_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{tenant_id}"
            )

            print(f"🔍 DEBUG: GET Response Status: {get_response.status_code}")
            print(f"🔍 DEBUG: GET Response Text: {get_response.text}")
            assert get_response.status_code == 200, f"Expected 200, got {get_response.status_code}: {get_response.text}"
            get_data = get_response.json()
            print(f"🔍 DEBUG: GET Response Data: {get_data}")
            assert get_data["tenant_id"] == tenant_id
            assert get_data["name"] == tenant_create_request["name"]

            # 3. Update tenant
            tenant_update_request = {
                "name": f"Updated Test Organization {self.test_id}",
                "primary_contact_name": "Jane Doe"
            }

            print(f"\n🔍 DEBUG: Updating tenant with data: {tenant_update_request}")
            update_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/tenants/{tenant_id}",
                json=tenant_update_request
            )

            print(f"🔍 DEBUG: UPDATE Response Status: {update_response.status_code}")
            print(f"🔍 DEBUG: UPDATE Response Text: {update_response.text}")
            assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
            update_data = update_response.json()
            print(f"🔍 DEBUG: UPDATE Response Data: {update_data}")
            print(f"🔍 DEBUG: Checking update assertions...")
            print(f"   Expected name: {tenant_update_request['name']}")
            print(f"   Actual name: {update_data.get('name', 'NOT_FOUND')}")
            print(f"   Expected primary_contact_name: {tenant_update_request['primary_contact_name']}")
            print(f"   Actual primary_contact_name: {update_data.get('primary_contact_name', 'NOT_FOUND')}")
            assert update_data["name"] == tenant_update_request["name"]
            assert update_data["primary_contact_name"] == tenant_update_request["primary_contact_name"]

            # 4. List tenants (should include our created tenant)
            print(f"\n🔍 DEBUG: Listing tenants...")
            list_response = await self.make_authenticated_request(
                "GET",
                "/v1/tenants?page=1&page_size=10"
            )

            print(f"🔍 DEBUG: LIST Response Status: {list_response.status_code}")
            print(f"🔍 DEBUG: LIST Response Text: {list_response.text}")
            assert list_response.status_code == 200, f"Expected 200, got {list_response.status_code}: {list_response.text}"
            list_data = list_response.json()
            print(f"🔍 DEBUG: LIST Response Data keys: {list(list_data.keys())}")
            print(f"🔍 DEBUG: LIST Response Data: {list_data}")
            assert "tenants" in list_data
            assert "total_count" in list_data  # API returns "total_count" not "total"
            assert "page" in list_data
            assert isinstance(list_data["tenants"], list)

            # Verify our created tenant is in the list
            tenant_found = any(t["tenant_id"] == tenant_id for t in list_data["tenants"])
            print(f"🔍 DEBUG: Looking for tenant {tenant_id} in list of {len(list_data['tenants'])} tenants")
            print(f"🔍 DEBUG: Tenant found in list: {tenant_found}")

            if tenant_found:
                print(f"   ✅ Tenant CRUD operations successful: Created, retrieved, updated, listed tenant {tenant_id}")
                self.test_results["tenant_crud_operations"] = "PASS"
            else:
                print(f"   ❌ Tenant {tenant_id} not found in tenant list")
                raise AssertionError(f"Created tenant {tenant_id} not found in tenant list")

        except Exception as e:
            print(f"   ❌ Tenant CRUD operations test error: {e}")
            self.test_results["tenant_crud_operations"] = f"ERROR: {e}"

    async def test_tenant_decommissioning(self):
        """Test DELETE /v1/tenants/{tenant_id} - Secure tenant decommissioning"""
        print("\n🧪 Testing Tenant Decommissioning...")

        try:
            # Create a tenant for decommissioning test
            tenant_create_request = {
                "name": f"Decommission Test Org {self.test_id}",
                "type": "smb",  # Changed from "professional" to valid enum value
                "primary_contact_name": "Test User",
                "primary_contact_email": f"decommission+{self.test_id}@example.com",
                "industry": "testing"
            }

            create_response = await self.make_authenticated_request(
                "POST",
                "/v1/tenants",
                json=tenant_create_request
            )

            assert create_response.status_code == 201, f"Expected 201, got {create_response.status_code}: {create_response.text}"
            tenant_id = create_response.json()["tenant_id"]

            # Decommission tenant with parameters
            decommission_response = await self.make_authenticated_request(
                "DELETE",
                f"/v1/tenants/{tenant_id}?reason=test_cleanup&data_retention=backup&backup_required=true"
            )

            assert decommission_response.status_code == 200, f"Expected 200, got {decommission_response.status_code}: {decommission_response.text}"
            decommission_data = decommission_response.json()

            # Validate decommissioning response structure
            expected_fields = ["status", "tenant_id", "decommissioned_at"]
            for field in expected_fields:
                assert field in decommission_data, f"Missing required field: {field}"

            # Verify tenant cannot be accessed after decommissioning
            get_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{tenant_id}"
            )

            assert get_response.status_code in [404, 410], f"Decommissioned tenant should not be accessible, got {get_response.status_code}: {get_response.text}"

            print(f"   ✅ Tenant decommissioning successful: Securely decommissioned tenant {tenant_id}")
            self.test_results["tenant_decommissioning"] = "PASS"

        except Exception as e:
            print(f"   ❌ Tenant decommissioning test error: {e}")
            self.test_results["tenant_decommissioning"] = f"ERROR: {e}"

    async def test_storage_management(self):
        """Test storage configuration and management endpoints"""
        print("\n🧪 Testing Storage Management...")

        try:
            # Create a real tenant for storage operations (platform admin can't have storage config)
            print(f"🔍 DEBUG: Step 1 - Creating storage test tenant")
            tenant_create_request = {
                "name": f"Storage Test Org {self.test_id}",
                "type": "enterprise",
                "primary_contact_name": "Storage Admin",
                "primary_contact_email": f"storage+{self.test_id}@example.com",
                "industry": "technology"
            }

            create_response = await self.make_authenticated_request(
                "POST",
                "/v1/tenants",
                json=tenant_create_request
            )

            print(f"🔍 DEBUG: Tenant creation response: {create_response.status_code}")
            assert create_response.status_code == 201, f"Expected 201, got {create_response.status_code}: {create_response.text}"
            tenant_id = create_response.json()["tenant_id"]
            self.created_tenant_ids.append(tenant_id)  # Track for cleanup
            print(f"🔍 DEBUG: Created tenant {tenant_id} for storage tests")

            # 1. Configure storage backend
            print(f"🔍 DEBUG: Step 2 - Configuring storage backend")
            storage_config_request = {
                "backend_type": "s3",
                "region": "us-east-1",
                "bucket_name": f"test-bucket-{self.test_id}",
                "access_key_id": "test-access-key",
                "secret_access_key": "test-secret-key",
                "encryption_enabled": True,
                "lifecycle_policy": {
                    "hot_storage_days": 30,
                    "warm_storage_days": 90,
                    "cold_storage_days": 365
                }
            }

            print(f"🔍 DEBUG: Storage config request: {storage_config_request}")
            config_response = await self.make_authenticated_request(
                "POST",
                f"/v1/tenants/{tenant_id}/storage/configure",
                json=storage_config_request
            )

            print(f"🔍 DEBUG: Storage config response: {config_response.status_code} - {config_response.text}")
            assert config_response.status_code == 200, f"Expected 200, got {config_response.status_code}: {config_response.text}"
            config_data = config_response.json()
            print(f"🔍 DEBUG: Storage config data: {config_data}")
            assert "status" in config_data

            # 2. Test storage connection
            print(f"🔍 DEBUG: Step 3 - Testing storage connection")
            test_connection_response = await self.make_authenticated_request(
                "POST",
                f"/v1/tenants/{tenant_id}/storage/test-connection"
            )

            print(f"🔍 DEBUG: Connection test response: {test_connection_response.status_code} - {test_connection_response.text}")
            assert test_connection_response.status_code == 200, f"Expected 200, got {test_connection_response.status_code}: {test_connection_response.text}"
            connection_data = test_connection_response.json()
            print(f"🔍 DEBUG: Connection test data: {connection_data}")

            # Check for actual API response fields based on debug output
            assert "connection_status" in connection_data, f"Missing 'connection_status' field in connection test result: {connection_data}"
            assert "tenant_id" in connection_data, f"Missing 'tenant_id' field in connection test result: {connection_data}"
            assert connection_data["connection_status"] == "success", f"Expected connection_status to be 'success', got: {connection_data.get('connection_status')}"

            # 3. Get storage status
            print(f"🔍 DEBUG: Step 4 - Getting storage status")
            status_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{tenant_id}/storage/status"
            )

            print(f"🔍 DEBUG: Storage status response: {status_response.status_code} - {status_response.text}")
            assert status_response.status_code == 200, f"Expected 200, got {status_response.status_code}: {status_response.text}"
            status_data = status_response.json()
            print(f"🔍 DEBUG: Storage status data: {status_data}")

            # Validate storage status response structure
            print(f"🔍 DEBUG: Step 5 - Validating storage status fields")
            expected_fields = ["storage_backend", "total_size_bytes", "hot_storage_bytes", "warm_storage_bytes", "cold_storage_bytes", "health_status"]
            print(f"🔍 DEBUG: Expected fields: {expected_fields}")
            print(f"🔍 DEBUG: Actual fields: {list(status_data.keys())}")
            for field in expected_fields:
                field_present = field in status_data
                print(f"🔍 DEBUG: Field {field}: {'✅' if field_present else '❌'}")
                assert field in status_data, f"Missing required field: {field}"

            print(f"   ✅ Storage management successful: Configured and tested storage for tenant {tenant_id}")
            self.test_results["storage_management"] = "PASS"

        except Exception as e:
            print(f"   ❌ Storage management test error: {e}")
            self.test_results["storage_management"] = f"ERROR: {e}"

    async def test_usage_and_billing(self):
        """Test usage statistics and billing endpoints"""
        print("\n🧪 Testing Usage and Billing...")

        try:
            # Use the tenant created in CRUD test, not the platform tenant
            if not self.created_tenant_ids:
                print("❌ No tenant created yet, skipping usage test")
                self.test_results["usage_and_billing"] = "SKIPPED: No tenant created"
                return

            tenant_id = self.created_tenant_ids[0]  # Use the first created tenant
            print(f"🔍 DEBUG: Using tenant {tenant_id} for usage test")
            print(f"🔍 DEBUG: Current auth headers: {self.auth_headers}")

            # Test platform admin access to any tenant's usage (should work)
            # Platform admin should be able to access any tenant's data
            headers_to_use = self.auth_headers.copy()
            headers_to_use["X-Customer-ID"] = "platform"  # Platform admin context
            print(f"🔍 DEBUG: Platform admin headers for cross-tenant usage test: {headers_to_use}")
            print(f"🔍 DEBUG: JWT token customer_id should be 'platform', accessing tenant {tenant_id}")

            # 1. Get tenant usage statistics
            usage_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{tenant_id}/usage",
                headers=headers_to_use
            )

            assert usage_response.status_code == 200, f"Expected 200, got {usage_response.status_code}: {usage_response.text}"
            usage_data = usage_response.json()

            # Validate usage response structure
            expected_fields = ["tenant_id", "current_period", "data_ingested_bytes", "queries_executed", "alerts_triggered", "storage_used_bytes", "cost_breakdown"]
            for field in expected_fields:
                assert field in usage_data, f"Missing required field: {field}"

            # 2. Get tenant quotas
            quotas_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{tenant_id}/quotas"
            )

            assert quotas_response.status_code == 200, f"Expected 200, got {quotas_response.status_code}: {quotas_response.text}"
            quotas_data = quotas_response.json()

            # Validate quotas response structure
            expected_quota_fields = ["max_data_ingestion_gb_per_day", "max_queries_per_hour", "max_storage_gb", "max_alerts", "max_users"]
            for field in expected_quota_fields:
                assert field in quotas_data, f"Missing required quota field: {field}"

            # 3. Update tenant quotas
            quota_update_request = {
                "max_data_ingestion_gb_per_day": 100,
                "max_queries_per_hour": 1000,
                "max_storage_gb": 500,
                "max_alerts": 50,
                "max_users": 25
            }

            update_quotas_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/tenants/{tenant_id}/quotas",
                json=quota_update_request
            )

            assert update_quotas_response.status_code == 200, f"Expected 200, got {update_quotas_response.status_code}: {update_quotas_response.text}"
            updated_quotas_data = update_quotas_response.json()
            assert updated_quotas_data["max_data_ingestion_gb_per_day"] == quota_update_request["max_data_ingestion_gb_per_day"]

            print(f"   ✅ Usage and billing successful: Retrieved usage data and updated quotas for tenant {tenant_id}")
            self.test_results["usage_and_billing"] = "PASS"

        except Exception as e:
            print(f"   ❌ Usage and billing test error: {e}")
            self.test_results["usage_and_billing"] = f"ERROR: {e}"

    async def test_tenant_configuration(self):
        """Test tenant configuration management"""
        print("\n🧪 Testing Tenant Configuration...")

        try:
            # Use a created tenant, not the platform tenant
            if not self.created_tenant_ids:
                print("❌ No tenant created yet, skipping config test")
                self.test_results["tenant_configuration"] = "SKIPPED: No tenant created"
                return

            tenant_id = self.created_tenant_ids[0]  # Use the first created tenant

            # 1. Get tenant configuration
            config_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{tenant_id}/config"
            )

            assert config_response.status_code == 200, f"Expected 200, got {config_response.status_code}: {config_response.text}"
            config_data = config_response.json()

            # Validate config response structure
            expected_fields = ["tenant_id", "log_retention_days", "alert_settings", "integration_settings", "security_settings", "ui_preferences"]
            for field in expected_fields:
                assert field in config_data, f"Missing required config field: {field}"

            # 2. Update tenant configuration
            config_update_request = {
                "log_retention_days": 90,
                "alert_settings": {
                    "email_notifications": True,
                    "slack_notifications": False,
                    "alert_threshold": "medium"
                },
                "security_settings": {
                    "require_mfa": True,
                    "session_timeout_minutes": 480,
                    "password_policy": "strict"
                },
                "ui_preferences": {
                    "theme": "dark",
                    "timezone": "UTC",
                    "date_format": "ISO"
                }
            }

            update_config_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/tenants/{tenant_id}/config",
                json=config_update_request
            )

            assert update_config_response.status_code == 200, f"Expected 200, got {update_config_response.status_code}: {update_config_response.text}"
            updated_config_data = update_config_response.json()
            assert updated_config_data["log_retention_days"] == config_update_request["log_retention_days"]
            assert updated_config_data["security_settings"]["require_mfa"] == config_update_request["security_settings"]["require_mfa"]

            print(f"   ✅ Tenant configuration successful: Retrieved and updated config for tenant {tenant_id}")
            self.test_results["tenant_configuration"] = "PASS"

        except Exception as e:
            print(f"   ❌ Tenant configuration test error: {e}")
            self.test_results["tenant_configuration"] = f"ERROR: {e}"

    async def test_compliance_operations(self):
        """Test compliance and legal hold operations"""
        print("\n🧪 Testing Compliance Operations...")

        try:
            # Use a created tenant, not the platform tenant
            if not self.created_tenant_ids:
                print("❌ No tenant created yet, skipping compliance test")
                self.test_results["compliance_operations"] = "SKIPPED: No tenant created"
                return

            tenant_id = self.created_tenant_ids[0]  # Use the first created tenant

            # 1. Get compliance status
            compliance_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{tenant_id}/compliance"
            )

            assert compliance_response.status_code == 200, f"Expected 200, got {compliance_response.status_code}: {compliance_response.text}"
            compliance_data = compliance_response.json()

            # Validate compliance response structure
            expected_fields = ["tenant_id", "compliance_frameworks", "audit_logs_enabled", "data_classification", "privacy_settings"]
            for field in expected_fields:
                assert field in compliance_data, f"Missing required compliance field: {field}"

            # 2. Create legal hold
            legal_hold_request = {
                "case_name": f"CASE-{self.test_id}",
                "description": "Litigation hold for test case",
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-12-31T23:59:59Z",
                "contact_person": "legal-team",
                "contact_email": "legal@company.com",
                "data_types": ["logs", "alerts", "user_activity"],
                "justification": "Legal preservation requirement for ongoing litigation"
            }

            legal_hold_response = await self.make_authenticated_request(
                "POST",
                f"/v1/tenants/{tenant_id}/legal-hold",
                json=legal_hold_request
            )

            assert legal_hold_response.status_code == 200, f"Expected 200, got {legal_hold_response.status_code}: {legal_hold_response.text}"
            legal_hold_data = legal_hold_response.json()

            # Validate legal hold response structure
            expected_hold_fields = ["hold_id", "status", "case_id", "created_at", "custodian"]
            for field in expected_hold_fields:
                assert field in legal_hold_data, f"Missing required legal hold field: {field}"

            assert legal_hold_data["case_id"] == legal_hold_request["case_name"]
            assert legal_hold_data["custodian"] == legal_hold_request["contact_person"]

            print(f"   ✅ Compliance operations successful: Retrieved compliance status and created legal hold for tenant {tenant_id}")
            self.test_results["compliance_operations"] = "PASS"

        except Exception as e:
            print(f"   ❌ Compliance operations test error: {e}")
            self.test_results["compliance_operations"] = f"ERROR: {e}"

    async def test_health_and_monitoring(self):
        """Test tenant health and monitoring endpoints"""
        print("\n🧪 Testing Health and Monitoring...")

        try:
            # Use a created tenant, not the platform tenant
            if not self.created_tenant_ids:
                print("❌ No tenant created yet, skipping health test")
                self.test_results["health_and_monitoring"] = "SKIPPED: No tenant created"
                return

            tenant_id = self.created_tenant_ids[0]  # Use the first created tenant

            # 1. Get tenant health status
            health_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{tenant_id}/health"
            )

            assert health_response.status_code == 200, f"Expected 200, got {health_response.status_code}: {health_response.text}"
            health_data = health_response.json()

            # Validate health response structure
            expected_fields = ["tenant_id", "overall_health", "service_status", "storage_health", "ingestion_health", "query_health", "alert_health", "last_check"]
            for field in expected_fields:
                assert field in health_data, f"Missing required health field: {field}"

            assert health_data["overall_health"] in ["healthy", "degraded", "unhealthy"]

            # 2. Get tenant metrics
            metrics_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{tenant_id}/metrics"
            )

            assert metrics_response.status_code == 200, f"Expected 200, got {metrics_response.status_code}: {metrics_response.text}"
            metrics_data = metrics_response.json()

            # Validate metrics response structure
            expected_metric_fields = ["tenant_id", "performance_metrics", "usage_metrics", "error_rates", "response_times", "resource_utilization"]
            for field in expected_metric_fields:
                assert field in metrics_data, f"Missing required metrics field: {field}"

            # 3. Get tenant alerts configuration
            alerts_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{tenant_id}/alerts"
            )

            assert alerts_response.status_code == 200, f"Expected 200, got {alerts_response.status_code}: {alerts_response.text}"
            alerts_data = alerts_response.json()

            # Validate alerts response structure
            expected_alert_fields = ["tenant_id", "active_alerts", "alert_rules", "notification_channels", "escalation_policies"]
            for field in expected_alert_fields:
                assert field in alerts_data, f"Missing required alerts field: {field}"

            print(f"   ✅ Health and monitoring successful: Retrieved health, metrics, and alerts for tenant {tenant_id}")
            self.test_results["health_and_monitoring"] = "PASS"

        except Exception as e:
            print(f"   ❌ Health and monitoring test error: {e}")
            self.test_results["health_and_monitoring"] = f"ERROR: {e}"

    async def test_tenant_validation(self):
        """Test tenant validation utility endpoint"""
        print("\n🧪 Testing Tenant Validation...")

        try:
            # Use a created tenant, not the platform tenant
            if not self.created_tenant_ids:
                print("❌ No tenant created yet, skipping validation test")
                self.test_results["tenant_validation"] = "SKIPPED: No tenant created"
                return

            tenant_id = self.created_tenant_ids[0]  # Use the first created tenant

            # Test valid tenant validation
            validate_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{tenant_id}/validate"
            )

            assert validate_response.status_code == 200, f"Expected 200, got {validate_response.status_code}: {validate_response.text}"
            validate_data = validate_response.json()

            # Validate validation response structure
            expected_fields = ["tenant_id", "valid", "exists", "validated_at"]
            for field in expected_fields:
                assert field in validate_data, f"Missing required validation field: {field}"

            assert validate_data["tenant_id"] == tenant_id
            assert validate_data["valid"] is True
            assert validate_data["exists"] is True
            assert "validated_at" in validate_data

            # Test invalid tenant validation
            invalid_tenant_id = "invalid-tenant-id"
            invalid_validate_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{invalid_tenant_id}/validate"
            )

            assert invalid_validate_response.status_code == 200, f"Expected 200, got {invalid_validate_response.status_code}: {invalid_validate_response.text}"
            invalid_validate_data = invalid_validate_response.json()
            assert invalid_validate_data["valid"] is False or invalid_validate_data["exists"] is False

            print(f"   ✅ Tenant validation successful: Validated existing and non-existing tenants")
            self.test_results["tenant_validation"] = "PASS"

        except Exception as e:
            print(f"   ❌ Tenant validation test error: {e}")
            self.test_results["tenant_validation"] = f"ERROR: {e}"

    async def test_tenant_list_filtering(self):
        """Test tenant listing with pagination and filtering"""
        print("\n🧪 Testing Tenant List Filtering...")

        try:
            # Test pagination
            page1_response = await self.make_authenticated_request(
                "GET",
                "/v1/tenants?page=1&page_size=5"
            )

            assert page1_response.status_code == 200, f"Expected 200, got {page1_response.status_code}: {page1_response.text}"
            page1_data = page1_response.json()

            # Validate pagination response structure
            expected_fields = ["tenants", "total_count", "page", "page_size", "total_pages"]
            for field in expected_fields:
                assert field in page1_data, f"Missing required pagination field: {field}"

            assert len(page1_data["tenants"]) <= 5
            assert page1_data["page"] == 1
            assert page1_data["page_size"] == 5

            # Test filtering by status
            status_filter_response = await self.make_authenticated_request(
                "GET",
                "/v1/tenants?status=active&page=1&page_size=10"
            )

            assert status_filter_response.status_code == 200, f"Expected 200, got {status_filter_response.status_code}: {status_filter_response.text}"
            status_filter_data = status_filter_response.json()
            assert "tenants" in status_filter_data

            # Test filtering by type
            type_filter_response = await self.make_authenticated_request(
                "GET",
                "/v1/tenants?type=enterprise&page=1&page_size=10"
            )

            assert type_filter_response.status_code == 200, f"Expected 200, got {type_filter_response.status_code}: {type_filter_response.text}"
            type_filter_data = type_filter_response.json()
            assert "tenants" in type_filter_data

            print(f"   ✅ Tenant list filtering successful: Tested pagination and filtering")
            self.test_results["tenant_list_filtering"] = "PASS"

        except Exception as e:
            print(f"   ❌ Tenant list filtering test error: {e}")
            self.test_results["tenant_list_filtering"] = f"ERROR: {e}"

    async def test_error_handling(self):
        """Test error handling for various invalid scenarios"""
        print("\n🧪 Testing Error Handling...")

        try:
            # Test get non-existent tenant
            get_invalid_response = await self.make_authenticated_request(
                "GET",
                "/v1/tenants/non-existent-tenant-id"
            )
            assert get_invalid_response.status_code == 404, f"Non-existent tenant should return 404, got {get_invalid_response.status_code}: {get_invalid_response.text}"

            # Test update non-existent tenant
            update_invalid_response = await self.make_authenticated_request(
                "PUT",
                "/v1/tenants/non-existent-tenant-id",
                json={"name": "Updated Name"}
            )
            assert update_invalid_response.status_code == 404, f"Update non-existent tenant should return 404, got {update_invalid_response.status_code}: {update_invalid_response.text}"

            # Test create tenant with invalid data
            invalid_create_response = await self.make_authenticated_request(
                "POST",
                "/v1/tenants",
                json={}  # Empty request
            )
            assert invalid_create_response.status_code == 422, f"Invalid tenant creation should return 422, got {invalid_create_response.status_code}: {invalid_create_response.text}"

            # Test invalid pagination parameters
            invalid_pagination_response = await self.make_authenticated_request(
                "GET",
                "/v1/tenants?page=0&page_size=1000"  # Invalid page and page_size
            )
            assert invalid_pagination_response.status_code in [400, 422], f"Invalid pagination should return error, got {invalid_pagination_response.status_code}: {invalid_pagination_response.text}"

            print(f"   ✅ Error handling working correctly")
            self.test_results["error_handling"] = "PASS"

        except Exception as e:
            print(f"   ❌ Error handling test error: {e}")
            self.test_results["error_handling"] = f"ERROR: {e}"

    async def run_all_tests(self):
        """Execute all tenant router tests"""
        print(f"\n🚀 Starting Tenant Router Test Suite (Test ID: {self.test_id})")
        print("=" * 60)

        # Create test user and tenant for authentication with platform-level access
        try:
            await self.create_test_user_and_tenant(['super_admin'])
            await self.setup_auth(['super_admin'])
            # Override tenant_id for platform admin operations
            self.tenant_id = "platform"
            self.auth_headers["X-Customer-ID"] = "platform"
        except Exception as e:
            print(f"❌ Failed to setup test environment: {e}")
            return

        # Run all tests
        test_methods = [
            self.test_tenant_crud_operations,
            self.test_tenant_decommissioning,
            self.test_storage_management,
            self.test_usage_and_billing,
            self.test_tenant_configuration,
            self.test_compliance_operations,
            self.test_health_and_monitoring,
            self.test_tenant_validation,
            self.test_tenant_list_filtering,
            self.test_error_handling
        ]

        for test_method in test_methods:
            try:
                await test_method()
                await asyncio.sleep(0.1)  # Brief pause between tests
            except Exception as e:
                test_name = test_method.__name__
                print(f"   ❌ {test_name} failed: {e}")
                self.test_results[test_name] = f"ERROR: {e}"

        # Cleanup created tenants
        await self.cleanup_created_tenants()

        # Cleanup test data
        await self.cleanup_test_data()

        # Print results summary
        self.print_test_summary()

    async def cleanup_created_tenants(self):
        """Clean up tenants created during testing"""
        for tenant_id in self.created_tenant_ids:
            try:
                await self.make_authenticated_request(
                    "DELETE",
                    f"/v1/tenants/{tenant_id}?reason=test_cleanup&backup_required=false"
                )
            except Exception as e:
                print(f"Warning: Failed to cleanup tenant {tenant_id}: {e}")

    def print_test_summary(self):
        """Print comprehensive test results summary"""
        print("\n" + "=" * 60)
        print("🏆 TENANT ROUTER TEST SUMMARY")
        print("=" * 60)

        passed = 0
        failed = 0

        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result == "PASS" else "❌ FAIL"
            print(f"{status:8} | {test_name:<35} | {result}")

            if result == "PASS":
                passed += 1
            else:
                failed += 1

        print("=" * 60)
        print(f"📊 TOTAL: {passed + failed} tests | ✅ PASSED: {passed} | ❌ FAILED: {failed}")

        if failed == 0:
            print("🎉 ALL TENANT ROUTER TESTS PASSED!")
        else:
            print(f"⚠️  {failed} test(s) failed - review errors above")

        print("=" * 60)

async def run_tenant_router_tests():
    """Main test runner function for integration with run_route_tests.py"""
    suite = TenantRouterTestSuite()
    await suite.run_all_tests()

    # Return True if all tests passed, False otherwise
    passed_tests = sum(1 for result in suite.test_results.values() if result == "PASS")
    total_tests = len(suite.test_results)

    return passed_tests == total_tests

# Pytest-compatible test functions for PyCharm debugging
import pytest

@pytest.mark.asyncio
async def test_tenant_crud_operations():
    """Pytest-compatible test for tenant CRUD operations"""
    suite = TenantRouterTestSuite()
    await suite.create_test_user_and_tenant(['super_admin'])
    await suite.setup_auth()
    suite.tenant_id = "platform"
    suite.auth_headers["X-Customer-ID"] = "platform"

    await suite.test_tenant_crud_operations()
    await suite.cleanup_test_data()

    # Assert test passed
    assert suite.test_results.get("tenant_crud_operations") == "PASS"

@pytest.mark.asyncio
async def test_tenant_decommissioning():
    """Pytest-compatible test for tenant decommissioning"""
    suite = TenantRouterTestSuite()
    await suite.create_test_user_and_tenant(['super_admin'])
    await suite.setup_auth()
    suite.tenant_id = "platform"
    suite.auth_headers["X-Customer-ID"] = "platform"

    await suite.test_tenant_decommissioning()
    await suite.cleanup_test_data()

    # Assert test passed
    assert suite.test_results.get("tenant_decommissioning") == "PASS"

@pytest.mark.asyncio
async def test_tenant_list_filtering():
    """Pytest-compatible test for tenant list filtering"""
    suite = TenantRouterTestSuite()
    await suite.create_test_user_and_tenant(['super_admin'])
    await suite.setup_auth()
    suite.tenant_id = "platform"
    suite.auth_headers["X-Customer-ID"] = "platform"

    await suite.test_tenant_list_filtering()
    await suite.cleanup_test_data()

    # Assert test passed
    assert suite.test_results.get("tenant_list_filtering") == "PASS"

@pytest.mark.asyncio
async def test_error_handling():
    """Pytest-compatible test for error handling"""
    suite = TenantRouterTestSuite()
    await suite.create_test_user_and_tenant(['super_admin'])
    await suite.setup_auth()
    suite.tenant_id = "platform"
    suite.auth_headers["X-Customer-ID"] = "platform"

    await suite.test_error_handling()
    await suite.cleanup_test_data()

    # Assert test passed
    assert suite.test_results.get("error_handling") == "PASS"

async def main():
    """Main test runner"""
    suite = TenantRouterTestSuite()
    await suite.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
