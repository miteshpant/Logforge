"""
M7 Enterprise Readiness - Individual Tests
Testing enterprise features: SSO/OIDC, RBAC, multi-tenancy, compliance, integrations

Test Coverage:
- Authentication & Authorization (6 endpoints)
- RBAC & Permissions (4 endpoints)  
- Multi-Tenancy & Compliance (6 endpoints)
- Enterprise Integration (3 endpoints)
- Administration & Governance (3 endpoints)
Total: 22 endpoints, 15 comprehensive tests
"""

import pytest
import httpx
import asyncio
from datetime import datetime, timedelta
import json
import uuid
from typing import Dict, List, Any

# Test Configuration
API_BASE_URL = "http://localhost:7080"
TEST_CUSTOMER_ID = "enterprise-test-tenant"
TEST_ADMIN_USER = "admin@enterprise.com"
TEST_ANALYST_USER = "analyst@enterprise.com"

class TestM7EnterpriseReadiness:
    """M7 Enterprise Readiness Individual Tests - 15 Tests Total"""

    @pytest.mark.asyncio
    async def test_01_authentication_provider_configuration(self):
        """Test OIDC provider configuration and management"""
        async with httpx.AsyncClient() as client:
            # Configure OIDC provider
            oidc_config = {
                "provider_name": "enterprise-auth0",
                "provider_type": "auth0",
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
                "domain": "enterprise.auth0.com",
                "scopes": ["openid", "profile", "email"],
                "enabled": True
            }
            
            response = await client.post(
                f"{API_BASE_URL}/v1/enterprise/auth/oidc/configure",
                json=oidc_config,
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            config_result = response.json()
            assert config_result["provider_name"] == "enterprise-auth0"
            assert config_result["status"] == "configured"
            
            # List authentication providers
            response = await client.get(
                f"{API_BASE_URL}/v1/enterprise/auth/providers",
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            providers = response.json()
            assert len(providers["providers"]) >= 1
            assert any(p["name"] == "enterprise-auth0" for p in providers["providers"])

    @pytest.mark.asyncio
    async def test_02_api_key_management(self):
        """Test API key generation, listing, and revocation"""
        async with httpx.AsyncClient() as client:
            # Generate API key
            key_request = {
                "name": "integration-api-key",
                "description": "API key for enterprise integration",
                "permissions": ["logs:read", "alerts:manage", "dashboards:read"],
                "expires_at": (datetime.now() + timedelta(days=90)).isoformat()
            }
            
            response = await client.post(
                f"{API_BASE_URL}/v1/enterprise/auth/api-keys",
                json=key_request,
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            key_result = response.json()
            assert "key" in key_result
            assert "key_id" in key_result
            assert key_result["name"] == "integration-api-key"
            key_id = key_result["key_id"]
            
            # List API keys
            response = await client.get(
                f"{API_BASE_URL}/v1/enterprise/auth/api-keys",
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            keys = response.json()
            assert len(keys["api_keys"]) >= 1
            assert any(k["key_id"] == key_id for k in keys["api_keys"])
            
            # Revoke API key
            response = await client.delete(
                f"{API_BASE_URL}/v1/enterprise/auth/api-keys/{key_id}",
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            revoke_result = response.json()
            assert revoke_result["status"] == "revoked"

    @pytest.mark.asyncio
    async def test_03_mfa_setup_and_validation(self):
        """Test Multi-Factor Authentication setup and validation"""
        async with httpx.AsyncClient() as client:
            # Setup MFA for user
            mfa_request = {
                "user_id": TEST_ADMIN_USER,
                "mfa_type": "totp",
                "backup_codes": True
            }
            
            response = await client.post(
                f"{API_BASE_URL}/v1/enterprise/auth/mfa/setup",
                json=mfa_request,
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            mfa_result = response.json()
            assert "qr_code" in mfa_result
            assert "backup_codes" in mfa_result
            assert mfa_result["mfa_enabled"] is True
            assert len(mfa_result["backup_codes"]) == 10

    @pytest.mark.asyncio
    async def test_04_rbac_roles_and_permissions(self):
        """Test Role-Based Access Control implementation"""
        async with httpx.AsyncClient() as client:
            # List default roles
            response = await client.get(
                f"{API_BASE_URL}/v1/enterprise/rbac/roles",
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            roles = response.json()
            default_roles = ["admin", "analyst", "viewer", "security_admin"]
            assert len(roles["roles"]) >= 4
            for role in default_roles:
                assert any(r["name"] == role for r in roles["roles"])
            
            # Create custom role
            custom_role = {
                "name": "compliance_officer",
                "description": "Compliance and audit access",
                "permissions": [
                    "compliance:read",
                    "audit_logs:read", 
                    "reports:generate",
                    "legal_hold:manage"
                ]
            }
            
            response = await client.post(
                f"{API_BASE_URL}/v1/enterprise/rbac/roles",
                json=custom_role,
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            role_result = response.json()
            assert role_result["name"] == "compliance_officer"
            assert role_result["status"] == "created"
            
            # Assign roles to user
            role_assignment = {
                "roles": ["analyst", "compliance_officer"]
            }
            
            response = await client.put(
                f"{API_BASE_URL}/v1/enterprise/rbac/users/{TEST_ANALYST_USER}/roles",
                json=role_assignment,
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            assignment_result = response.json()
            assert set(assignment_result["assigned_roles"]) == {"analyst", "compliance_officer"}

    @pytest.mark.asyncio
    async def test_05_user_permissions_validation(self):
        """Test user permission checking and validation"""
        async with httpx.AsyncClient() as client:
            # Get user permissions
            response = await client.get(
                f"{API_BASE_URL}/v1/enterprise/rbac/permissions",
                headers={
                    "X-Customer-ID": TEST_CUSTOMER_ID,
                    "X-User-ID": TEST_ANALYST_USER
                }
            )
            assert response.status_code == 200
            permissions = response.json()
            assert "permissions" in permissions
            assert "effective_roles" in permissions
            
            # Validate analyst permissions
            expected_permissions = [
                "logs:read", "alerts:read", "dashboards:read",
                "security:investigate", "compliance:read"
            ]
            user_permissions = permissions["permissions"]
            for perm in expected_permissions:
                assert perm in user_permissions

    @pytest.mark.asyncio
    async def test_06_multi_tenant_management(self):
        """Test tenant management and isolation"""
        async with httpx.AsyncClient() as client:
            # List existing tenants
            response = await client.get(
                f"{API_BASE_URL}/v1/enterprise/tenants",
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            tenants = response.json()
            assert "tenants" in tenants
            
            # Create new tenant
            tenant_config = {
                "tenant_id": "enterprise-demo-tenant",
                "name": "Enterprise Demo Customer",
                "tier": "enterprise",
                "data_residency": "us-east-1",
                "compliance_requirements": ["SOX", "PCI-DSS"],
                "retention_policy": {
                    "hot_storage_days": 30,
                    "warm_storage_days": 365,
                    "cold_storage_days": 2555  # 7 years
                },
                "resource_limits": {
                    "daily_ingestion_gb": 100,
                    "query_rate_limit": 1000,
                    "storage_limit_gb": 50000
                }
            }
            
            response = await client.post(
                f"{API_BASE_URL}/v1/enterprise/tenants",
                json=tenant_config,
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            tenant_result = response.json()
            assert tenant_result["tenant_id"] == "enterprise-demo-tenant"
            assert tenant_result["status"] == "active"
            assert tenant_result["compliance_requirements"] == ["SOX", "PCI-DSS"]

    @pytest.mark.asyncio
    async def test_07_tenant_settings_management(self):
        """Test tenant configuration and settings updates"""
        async with httpx.AsyncClient() as client:
            # Update tenant settings
            tenant_updates = {
                "data_residency": "eu-west-1",
                "compliance_requirements": ["GDPR", "SOX"],
                "retention_policy": {
                    "hot_storage_days": 60,
                    "warm_storage_days": 730,
                    "cold_storage_days": 3650
                },
                "security_settings": {
                    "require_mfa": True,
                    "session_timeout_minutes": 480,
                    "ip_whitelist": ["192.168.1.0/24", "10.0.0.0/8"]
                }
            }
            
            response = await client.put(
                f"{API_BASE_URL}/v1/enterprise/tenants/enterprise-demo-tenant/settings",
                json=tenant_updates,
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            update_result = response.json()
            assert update_result["data_residency"] == "eu-west-1"
            assert "GDPR" in update_result["compliance_requirements"]
            assert update_result["security_settings"]["require_mfa"] is True

    @pytest.mark.asyncio
    async def test_08_compliance_reporting_automation(self):
        """Test automated compliance report generation"""
        async with httpx.AsyncClient() as client:
            # Generate SOX compliance report
            report_request = {
                "compliance_framework": "SOX",
                "period_start": (datetime.now() - timedelta(days=90)).isoformat(),
                "period_end": datetime.now().isoformat(),
                "sections": ["access_controls", "audit_trail", "data_integrity", "incident_response"]
            }
            
            response = await client.get(
                f"{API_BASE_URL}/v1/enterprise/compliance/reports",
                params=report_request,
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            report = response.json()
            assert report["framework"] == "SOX"
            assert "compliance_score" in report
            assert "sections" in report
            assert len(report["sections"]) == 4
            
            # Validate compliance sections
            section_names = [s["name"] for s in report["sections"]]
            assert "access_controls" in section_names
            assert "audit_trail" in section_names
            assert report["compliance_score"] >= 0.0
            assert report["compliance_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_09_legal_hold_and_data_preservation(self):
        """Test legal hold functionality for data preservation"""
        async with httpx.AsyncClient() as client:
            # Place legal hold
            legal_hold_request = {
                "case_id": "LEGAL-2024-001",
                "custodian": "legal@enterprise.com",
                "reason": "Litigation support - contract dispute",
                "date_range": {
                    "start": (datetime.now() - timedelta(days=180)).isoformat(),
                    "end": datetime.now().isoformat()
                },
                "scope": {
                    "data_types": ["logs", "alerts", "investigations"],
                    "sources": ["api_gateway", "payment_service", "user_auth"],
                    "users": ["user123", "user456"]
                }
            }
            
            response = await client.post(
                f"{API_BASE_URL}/v1/enterprise/compliance/legal-hold",
                json=legal_hold_request,
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            hold_result = response.json()
            assert hold_result["case_id"] == "LEGAL-2024-001"
            assert hold_result["status"] == "active"
            assert "data_count" in hold_result
            assert hold_result["data_count"] >= 0

    @pytest.mark.asyncio
    async def test_10_audit_logging_and_trail(self):
        """Test comprehensive audit logging for all user actions"""
        async with httpx.AsyncClient() as client:
            # Retrieve audit logs
            audit_params = {
                "start_time": (datetime.now() - timedelta(hours=24)).isoformat(),
                "end_time": datetime.now().isoformat(),
                "user_id": TEST_ADMIN_USER,
                "action_types": ["authentication", "authorization", "configuration", "data_access"]
            }
            
            response = await client.get(
                f"{API_BASE_URL}/v1/enterprise/audit-logs",
                params=audit_params,
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            audit_logs = response.json()
            assert "logs" in audit_logs
            assert "total_count" in audit_logs
            
            # Validate audit log structure
            if audit_logs["logs"]:
                log_entry = audit_logs["logs"][0]
                required_fields = ["timestamp", "user_id", "action", "resource", "result", "ip_address", "user_agent"]
                for field in required_fields:
                    assert field in log_entry

    @pytest.mark.asyncio
    async def test_11_enterprise_integrations_management(self):
        """Test enterprise integration configuration and health monitoring"""
        async with httpx.AsyncClient() as client:
            # List available integrations
            response = await client.get(
                f"{API_BASE_URL}/v1/enterprise/integrations",
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            integrations = response.json()
            assert "integrations" in integrations
            
            # Validate integration types
            integration_types = [i["type"] for i in integrations["integrations"]]
            expected_types = ["slack", "servicenow", "jira", "pagerduty", "email", "webhook", "soar"]
            for int_type in expected_types:
                assert int_type in integration_types
            
            # Configure Slack integration
            slack_config = {
                "webhook_url": "https://hooks.slack.com/test-webhook",
                "channel": "#security-alerts",
                "bot_token": "xoxb-test-token",
                "enabled": True,
                "notification_types": ["critical_alerts", "compliance_violations", "security_incidents"]
            }
            
            response = await client.post(
                f"{API_BASE_URL}/v1/enterprise/integrations/slack/configure",
                json=slack_config,
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            config_result = response.json()
            assert config_result["type"] == "slack"
            assert config_result["status"] == "configured"

    @pytest.mark.asyncio
    async def test_12_integration_health_monitoring(self):
        """Test integration health checking and status monitoring"""
        async with httpx.AsyncClient() as client:
            # Check Slack integration health
            response = await client.get(
                f"{API_BASE_URL}/v1/enterprise/integrations/slack/status",
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            health_status = response.json()
            assert "status" in health_status
            assert "last_check" in health_status
            assert "response_time_ms" in health_status
            assert health_status["status"] in ["healthy", "degraded", "unhealthy"]
            
            # Validate health metrics
            if health_status["status"] == "healthy":
                assert health_status["response_time_ms"] < 5000
            assert "connectivity" in health_status
            assert "authentication" in health_status

    @pytest.mark.asyncio
    async def test_13_billing_and_usage_analytics(self):
        """Test billing metrics and usage reporting"""
        async with httpx.AsyncClient() as client:
            # Get billing and usage metrics
            billing_params = {
                "period_start": (datetime.now() - timedelta(days=30)).isoformat(),
                "period_end": datetime.now().isoformat(),
                "breakdown": ["storage", "ingestion", "queries", "alerts"]
            }
            
            response = await client.get(
                f"{API_BASE_URL}/v1/enterprise/usage/billing",
                params=billing_params,
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            billing = response.json()
            assert "period" in billing
            assert "usage_summary" in billing
            assert "cost_breakdown" in billing
            
            # Validate usage metrics
            usage = billing["usage_summary"]
            required_metrics = ["total_storage_gb", "ingestion_volume_gb", "query_count", "alert_count"]
            for metric in required_metrics:
                assert metric in usage
                assert isinstance(usage[metric], (int, float))
                assert usage[metric] >= 0
            
            # Validate cost breakdown
            costs = billing["cost_breakdown"]
            cost_categories = ["storage", "compute", "ingestion", "features"]
            for category in cost_categories:
                assert category in costs
                assert isinstance(costs[category], (int, float))

    @pytest.mark.asyncio
    async def test_14_enterprise_system_health(self):
        """Test enterprise system health monitoring and diagnostics"""
        async with httpx.AsyncClient() as client:
            # Get enterprise system health
            response = await client.get(
                f"{API_BASE_URL}/v1/enterprise/system/health",
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            health = response.json()
            assert "overall_status" in health
            assert "components" in health
            assert "sla_metrics" in health
            
            # Validate component health
            components = health["components"]
            required_components = ["authentication", "database", "message_queue", "storage", "integrations"]
            for component in required_components:
                assert component in components
                comp_health = components[component]
                assert comp_health["status"] in ["healthy", "degraded", "unhealthy"]
                assert "response_time_ms" in comp_health
                assert "uptime_percentage" in comp_health
            
            # Validate SLA metrics
            sla = health["sla_metrics"]
            sla_fields = ["availability", "performance", "reliability"]
            for field in sla_fields:
                assert field in sla
                assert sla[field] >= 0.0
                assert sla[field] <= 1.0

    @pytest.mark.asyncio
    async def test_15_backup_and_disaster_recovery(self):
        """Test backup configuration and disaster recovery capabilities"""
        async with httpx.AsyncClient() as client:
            # Configure backup policies
            backup_config = {
                "policy_name": "enterprise_backup",
                "schedule": "daily",
                "retention_days": 2555,  # 7 years
                "storage_location": "s3://enterprise-backups/logforge",
                "encryption": True,
                "compression": True,
                "components": ["clickhouse", "configurations", "user_data", "compliance_data"],
                "disaster_recovery": {
                    "rpo_hours": 4,  # Recovery Point Objective
                    "rto_hours": 2   # Recovery Time Objective
                }
            }
            
            response = await client.post(
                f"{API_BASE_URL}/v1/enterprise/backup/configure",
                json=backup_config,
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            backup_result = response.json()
            assert backup_result["policy_name"] == "enterprise_backup"
            assert backup_result["status"] == "configured"
            assert backup_result["next_backup"] is not None
            
            # Validate DR metrics
            dr_metrics = backup_result["disaster_recovery"]
            assert dr_metrics["rpo_hours"] == 4
            assert dr_metrics["rto_hours"] == 2
            assert "backup_verification" in backup_result


# Integration Test - All M7 Features Working Together
class TestM7EnterpriseIntegration:
    """M7 Enterprise Integration Test - End-to-End Enterprise Workflow"""

    @pytest.mark.asyncio
    async def test_enterprise_workflow_integration(self):
        """Test complete enterprise workflow with all M7 features"""
        async with httpx.AsyncClient() as client:
            # 1. Setup enterprise tenant with full configuration
            enterprise_tenant = {
                "tenant_id": "full-enterprise-test",
                "name": "Full Enterprise Test Customer",
                "tier": "enterprise_plus",
                "data_residency": "us-west-2",
                "compliance_requirements": ["SOX", "HIPAA", "PCI-DSS", "GDPR"],
                "retention_policy": {
                    "hot_storage_days": 90,
                    "warm_storage_days": 1095,  # 3 years
                    "cold_storage_days": 2555   # 7 years
                }
            }
            
            response = await client.post(
                f"{API_BASE_URL}/v1/enterprise/tenants",
                json=enterprise_tenant,
                headers={"X-Customer-ID": TEST_CUSTOMER_ID}
            )
            assert response.status_code == 200
            
            # 2. Configure OIDC authentication
            oidc_config = {
                "provider_name": "enterprise-keycloak",
                "provider_type": "keycloak", 
                "client_id": "logforge-enterprise",
                "domain": "auth.enterprise.local",
                "enabled": True
            }
            
            response = await client.post(
                f"{API_BASE_URL}/v1/enterprise/auth/oidc/configure",
                json=oidc_config,
                headers={"X-Customer-ID": "full-enterprise-test"}
            )
            assert response.status_code == 200
            
            # 3. Setup RBAC with custom compliance role
            compliance_role = {
                "name": "sox_auditor",
                "description": "SOX compliance auditor role",
                "permissions": ["compliance:read", "audit_logs:read", "reports:generate"]
            }
            
            response = await client.post(
                f"{API_BASE_URL}/v1/enterprise/rbac/roles",
                json=compliance_role,
                headers={"X-Customer-ID": "full-enterprise-test"}
            )
            assert response.status_code == 200
            
            # 4. Generate compliance report
            response = await client.get(
                f"{API_BASE_URL}/v1/enterprise/compliance/reports",
                params={
                    "compliance_framework": "SOX",
                    "period_start": (datetime.now() - timedelta(days=30)).isoformat(),
                    "period_end": datetime.now().isoformat()
                },
                headers={"X-Customer-ID": "full-enterprise-test"}
            )
            assert response.status_code == 200
            
            # 5. Configure enterprise integrations
            servicenow_config = {
                "instance_url": "https://enterprise.service-now.com",
                "username": "logforge_integration",
                "enabled": True,
                "incident_creation": True
            }
            
            response = await client.post(
                f"{API_BASE_URL}/v1/enterprise/integrations/servicenow/configure",
                json=servicenow_config,
                headers={"X-Customer-ID": "full-enterprise-test"}
            )
            assert response.status_code == 200
            
            # 6. Validate enterprise system health
            response = await client.get(
                f"{API_BASE_URL}/v1/enterprise/system/health",
                headers={"X-Customer-ID": "full-enterprise-test"}
            )
            assert response.status_code == 200
            health = response.json()
            assert health["overall_status"] in ["healthy", "degraded"]
            
            # 7. Verify audit trail captures all actions
            response = await client.get(
                f"{API_BASE_URL}/v1/enterprise/audit-logs",
                params={"action_types": ["tenant_created", "oidc_provider_configured", "role_created"]},
                headers={"X-Customer-ID": "full-enterprise-test"}
            )
            assert response.status_code == 200
            audit_logs = response.json()
            assert audit_logs["total_count"] >= 3  # At least 3 actions logged


if __name__ == "__main__":
    print("M7 Enterprise Readiness - Individual Tests")
    print("=========================================")
    print("Testing enterprise authentication, RBAC, compliance, and integrations")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Test Customer ID: {TEST_CUSTOMER_ID}")
    print()
    
    # Run tests with pytest
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])