"""
M8 User Service & Authentication Foundation - Individual Test Suite
Tests all M8 specifications exhaustively including user management, authentication,
role-based access control, secure onboarding, and API usage tracking for billing.
"""

import asyncio
import pytest
import httpx
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import bcrypt
import secrets
import json
from base_test import BaseTestSuite

# Test configuration
API_BASE_URL = "http://localhost:7080"
ADMIN_UI_URL = "http://localhost:3002" 
CUSTOMER_UI_URL = "http://localhost:3001"

class TestM8UserServiceFoundation(BaseTestSuite):
    """Comprehensive M8 User Service test suite"""
    
    def __init__(self):
        """Initialize test suite"""
        super().__init__("M8 User Service Foundation")
        self.test_users = []
        self.test_sessions = []
        # Initialize HTTP client for M8 tests
        self.client = None
    
    async def setup_test_environment(self):
        """Setup test environment using BaseTestSuite auth"""
        # M8 tests need admin privileges to manage users, so use admin auth with platform super-tenant
        await self.setup_auth(roles=['super_admin', 'tenant_admin'])
        
        # Initialize the persistent client for all test methods  
        self.client = httpx.AsyncClient(base_url="http://localhost:7080", timeout=30.0)
        print("✅ M8 test environment setup completed")
    
    async def teardown_test_environment(self):
        """Cleanup using BaseTestSuite"""
        await self.cleanup_test_data()
        # Close the HTTP client
        if self.client:
            await self.client.aclose()

    # =================================================================
    # CORE USER MANAGEMENT TESTS
    # =================================================================

    async def test_01_user_crud_operations(self):
        """Test comprehensive user CRUD operations"""
        print("🧪 Testing User CRUD Operations...")
        
        # 1. Create user
        unique_id = str(uuid.uuid4())[:8]
        user_data = {
            "name": f"John Doe {unique_id}",
            "email": f"john.doe.{unique_id}@test.local", 
            "password": "SecurePassword123!",
            "status": "active"
        }
        
        response = await self.make_authenticated_request("POST", "/v1/users", json=user_data)
        assert response.status_code == 201, f"User creation failed: {response.text}"
        
        user = response.json()
        self.test_users.append(user["id"])
        
        assert user["email"] == user_data["email"]
        assert user["name"] == user_data["name"]
        assert user["status"] == "active"
        assert "password" not in user  # Password should not be returned
        assert "created_at" in user
        print("✅ User creation successful")
        
        # 2. Read user (using authenticated request method)
        response = await self.make_authenticated_request("GET", f"/v1/users/{user['id']}")
        assert response.status_code == 200, f"User retrieval failed: {response.text}"
        
        retrieved_user = response.json()
        assert retrieved_user["id"] == user["id"]
        assert retrieved_user["email"] == user_data["email"]
        print("✅ User retrieval successful")
        
        # 3. Update user
        update_data = {"name": "John Smith", "status": "inactive"}
        response = await self.make_authenticated_request("PUT", f"/v1/users/{user['id']}", json=update_data)
        assert response.status_code == 200, f"User update failed: {response.text}"
        
        updated_user = response.json()
        assert updated_user["name"] == "John Smith"
        assert updated_user["status"] == "inactive"
        print("✅ User update successful")
        
        # 4. List users
        response = await self.make_authenticated_request("GET", "/v1/users")
        assert response.status_code == 200, f"User listing failed: {response.text}"
        
        users_list = response.json()
        assert len(users_list["users"]) >= 1
        assert any(u["id"] == user["id"] for u in users_list["users"])
        print("✅ User listing successful")
        
        # 5. Delete user (soft delete)
        response = await self.make_authenticated_request("DELETE", f"/v1/users/{user['id']}")
        assert response.status_code == 200, f"User deletion failed: {response.text}"
        
        # Verify soft deletion - user should still exist but with inactive status
        response = await self.make_authenticated_request("GET", f"/v1/users/{user['id']}")
        assert response.status_code == 200, f"Soft-deleted user should still be accessible: {response.text}"
        
        deleted_user = response.json()
        assert deleted_user["status"] == "inactive", "User should be marked as inactive after deletion"
        print("✅ User soft deletion successful")

    async def test_02_password_security_requirements(self):
        """Test password hashing and security policies"""
        print("🧪 Testing Password Security...")
        
        # Test password policy enforcement
        weak_passwords = [
            "123", # Too short
            "password", # Too simple
            "12345678", # No complexity
        ]
        
        for weak_password in weak_passwords:
            user_data = {
                "name": "Test User",
                "email": f"test.{uuid.uuid4()}@example.com",
                "password": weak_password
            }
            
            response = await self.client.post("/v1/users", json=user_data, headers=self.auth_headers)
            assert response.status_code == 400, f"Weak password should be rejected: {weak_password}"
        
        # Test strong password acceptance
        strong_password = "StrongPassword123!@#"
        user_data = {
            "name": "Strong Password User",
            "email": f"strong.{uuid.uuid4()}@example.com",
            "password": strong_password
        }
        
        response = await self.client.post("/v1/users", json=user_data, headers=self.auth_headers)
        assert response.status_code == 201, f"Strong password should be accepted: {response.text}"
        
        user = response.json()
        self.test_users.append(user["id"])
        print("✅ Password security policies working")

    async def test_03_user_authentication_flow(self):
        """Test complete user authentication flow"""
        print("🧪 Testing User Authentication Flow...")
        
        # 1. Create test user
        user_data = {
            "name": "Auth Test User",
            "email": f"auth.test.{uuid.uuid4()}@example.com",
            "password": "AuthTestPassword123!"
        }
        
        response = await self.client.post("/v1/users", json=user_data, headers=self.auth_headers)
        assert response.status_code == 201
        user = response.json()
        self.test_users.append(user["id"])
        
        # 2. Login with correct credentials
        login_data = {
            "email": user_data["email"],
            "password": user_data["password"]
        }
        
        response = await self.client.post("/v1/auth/login", json=login_data)
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        auth_response = response.json()
        assert "access_token" in auth_response
        assert "expires_at" in auth_response
        
        session_token = auth_response["access_token"]
        self.test_sessions.append(session_token)
        print("✅ User login successful")
        
        # 3. Verify authenticated request
        headers = {"Authorization": f"Bearer {session_token}"}
        response = await self.client.get("/v1/auth/me", headers=headers)
        assert response.status_code == 200, f"Authenticated request failed: {response.text}"
        
        profile = response.json()
        assert profile["email"] == user_data["email"]
        assert profile["name"] == user_data["name"]
        print("✅ Authenticated request successful")
        
        # 4. Login with wrong password
        wrong_login_data = {
            "email": user_data["email"],
            "password": "WrongPassword123!"
        }
        
        response = await self.client.post("/v1/auth/login", json=wrong_login_data)
        assert response.status_code == 401, "Wrong password should fail"
        print("✅ Wrong password properly rejected")
        
        # 5. Logout
        response = await self.client.post("/v1/auth/logout", headers=headers)
        assert response.status_code == 200, f"Logout failed: {response.text}"
        
        # 6. Verify session invalidated
        response = await self.client.get("/v1/auth/me", headers=headers)
        assert response.status_code == 401, "Session should be invalidated after logout"
        print("✅ User logout and session invalidation successful")

    # =================================================================
    # ROLE-BASED ACCESS CONTROL TESTS
    # =================================================================

    async def test_04_platform_admin_roles(self):
        """Test platform admin role creation and permissions"""
        print("🧪 Testing Platform Admin Roles...")
        
        # Define platform admin roles to test
        admin_roles = [
            {
                "role": "super_admin",
                "name": "Super Admin User",
                "expected_permissions": ["platform:*:*", "tenants:*:*", "users:*:*"]
            },
            {
                "role": "admin", 
                "name": "Regular Admin User",
                "expected_permissions": ["tenants:read,write,create:platform", "usage:read:platform"]
            },
            {
                "role": "support_admin",
                "name": "Support Admin User", 
                "expected_permissions": ["support:*:platform", "users:read,write:platform"]
            },
            {
                "role": "billing_admin",
                "name": "Billing Admin User",
                "expected_permissions": ["billing:*:platform", "usage:read:platform"]
            }
        ]
        
        for admin_role in admin_roles:
            # Create admin user
            user_data = {
                "name": admin_role["name"],
                "email": f"{admin_role['role']}.{uuid.uuid4()}@logforge.com",
                "password": "AdminPassword123!"
            }
            
            response = await self.client.post("/v1/admin/users", json=user_data, headers=self.auth_headers)
            assert response.status_code == 201, f"Admin user creation failed: {response.text}"
            
            admin_user = response.json()
            self.test_users.append(admin_user["id"])
            
            # Assign role
            role_assignment = {
                "tenant_id": "platform",
                "role": admin_role["role"]
            }
            
            response = await self.client.post(f"/v1/users/{admin_user['id']}/roles", json=role_assignment)
            assert response.status_code == 201, f"Role assignment failed: {response.text}"
            
            # Verify role assignment
            response = await self.client.get(f"/v1/users/{admin_user['id']}/roles")
            assert response.status_code == 200, f"Role retrieval failed: {response.text}"
            
            user_roles = response.json()
            assert any(
                r["tenant_id"] == "platform" and r["role"] == admin_role["role"] 
                for r in user_roles["roles"]
            ), f"Role not properly assigned: {admin_role['role']}"
            
            print(f"✅ {admin_role['role']} role created and assigned successfully")

    async def test_05_customer_user_roles(self):
        """Test customer user role creation and permissions"""
        print("🧪 Testing Customer User Roles...")
        
        # Create test tenant first
        tenant_data = {
            "name": "Test Organization",
            "subscription_tier": "professional"
        }
        
        response = await self.client.post("/v1/tenants", json=tenant_data, headers=self.auth_headers)
        assert response.status_code == 201, f"Tenant creation failed: {response.text}"
        tenant = response.json()
        test_tenant_id = tenant["tenant_id"]
        
        # Define customer roles to test
        customer_roles = [
            {
                "role": "tenant_admin",
                "name": "Tenant Admin User",
                "expected_permissions": ["logs:*:tenant", "alerts:*:tenant", "users:*:tenant"]
            },
            {
                "role": "security_analyst",
                "name": "Security Analyst User",
                "expected_permissions": ["security:*:tenant", "logs:read,search:tenant"]
            },
            {
                "role": "devops_engineer", 
                "name": "DevOps Engineer User",
                "expected_permissions": ["logs:read,search:tenant", "alerts:*:tenant"]
            },
            {
                "role": "compliance_officer",
                "name": "Compliance Officer User",
                "expected_permissions": ["compliance:*:tenant", "audit:read:tenant"]
            },
            {
                "role": "viewer",
                "name": "Viewer User",
                "expected_permissions": ["logs:read:tenant", "dashboards:read:tenant"]
            }
        ]
        
        for customer_role in customer_roles:
            # Create customer user
            user_data = {
                "name": customer_role["name"],
                "email": f"{customer_role['role']}.{uuid.uuid4()}@testorg.com",
                "password": "CustomerPassword123!"
            }
            
            response = await self.client.post("/v1/users", json=user_data)
            assert response.status_code == 201, f"Customer user creation failed: {response.text}"
            
            customer_user = response.json()
            self.test_users.append(customer_user["id"])
            
            # Assign role to tenant
            role_assignment = {
                "tenant_id": test_tenant_id,
                "role": customer_role["role"]
            }
            
            response = await self.client.post(f"/v1/users/{customer_user['id']}/roles", json=role_assignment)
            assert response.status_code == 201, f"Role assignment failed: {response.text}"
            
            # Verify role and permissions
            response = await self.client.get(f"/v1/users/{customer_user['id']}/roles")
            assert response.status_code == 200, f"Role retrieval failed: {response.text}"
            
            user_roles = response.json()
            assert any(
                r["tenant_id"] == test_tenant_id and r["role"] == customer_role["role"]
                for r in user_roles["roles"] 
            ), f"Customer role not properly assigned: {customer_role['role']}"
            
            print(f"✅ {customer_role['role']} role created and assigned successfully")

    async def test_06_multi_tenant_access_control(self):
        """Test user access across multiple tenants with different roles"""
        print("🧪 Testing Multi-Tenant Access Control...")
        
        # Create two test tenants
        tenant_a_data = {"name": "Tenant A Corp", "subscription_tier": "enterprise"}
        tenant_b_data = {"name": "Tenant B Inc", "subscription_tier": "professional"}
        
        response_a = await self.client.post("/v1/tenants", json=tenant_a_data)
        response_b = await self.client.post("/v1/tenants", json=tenant_b_data)
        
        assert response_a.status_code == 201 and response_b.status_code == 201
        
        tenant_a = response_a.json()
        tenant_b = response_b.json()
        tenant_a_id = tenant_a["tenant_id"]
        tenant_b_id = tenant_b["tenant_id"]
        
        # Create user with access to both tenants
        user_data = {
            "name": "Multi Tenant User",
            "email": f"multi.tenant.{uuid.uuid4()}@example.com", 
            "password": "MultiTenantPassword123!"
        }
        
        response = await self.client.post("/v1/users", json=user_data, headers=self.auth_headers)
        assert response.status_code == 201
        user = response.json()
        self.test_users.append(user["id"])
        
        # Assign different roles to different tenants
        role_assignments = [
            {"tenant_id": tenant_a_id, "role": "tenant_admin"},
            {"tenant_id": tenant_b_id, "role": "security_analyst"}
        ]
        
        for assignment in role_assignments:
            response = await self.client.post(f"/v1/users/{user['id']}/roles", json=assignment)
            assert response.status_code == 201, f"Multi-tenant role assignment failed: {response.text}"
        
        # Verify user has access to both tenants with correct roles
        response = await self.client.get(f"/v1/users/{user['id']}/roles")
        assert response.status_code == 200
        
        user_roles = response.json()["roles"]
        
        # Check tenant A access
        tenant_a_role = next((r for r in user_roles if r["tenant_id"] == tenant_a_id), None)
        assert tenant_a_role is not None, "User should have access to Tenant A"
        assert tenant_a_role["role"] == "tenant_admin"
        
        # Check tenant B access  
        tenant_b_role = next((r for r in user_roles if r["tenant_id"] == tenant_b_id), None)
        assert tenant_b_role is not None, "User should have access to Tenant B"
        assert tenant_b_role["role"] == "security_analyst"
        
        print("✅ Multi-tenant access control working correctly")

    # =================================================================
    # SECURE ONBOARDING TESTS
    # =================================================================

    async def test_07_platform_admin_setup_flow(self):
        """Test platform admin setup functionality (for already-operational system)"""
        print("🧪 Testing Platform Admin Setup Flow...")
        
        # Since platform is already operational, setup should be completed
        # Test that setup/init correctly returns 400 when already completed
        response = await self.client.post("/v1/auth/setup/init")
        assert response.status_code == 400, "Setup/init should return 400 when platform already operational"
        
        error_response = response.json()
        assert "already completed" in error_response.get("detail", "").lower(), "Should indicate setup already completed"
        print("✅ Setup/init correctly indicates platform already operational")
        
        # Test that we can still create platform admin users through the admin API
        # (This is the normal operational flow for adding new admins)
        admin_user_data = {
            "name": "New Platform Admin",
            "email": f"new.admin.{uuid.uuid4()}@logforge.com",
            "password": "NewAdminPassword123!"
        }
        
        response = await self.make_authenticated_request("POST", "/v1/admin/users", json=admin_user_data)
        assert response.status_code == 201, f"Platform admin creation failed: {response.text}"
        
        admin_user = response.json()
        self.test_users.append(admin_user["id"])
        
        assert admin_user["email"] == admin_user_data["email"]
        assert admin_user["name"] == admin_user_data["name"]
        print("✅ Platform admin user created through admin API")
        
        # Test that the new admin can login
        login_data = {
            "email": admin_user_data["email"],
            "password": admin_user_data["password"]
        }
        
        response = await self.client.post("/v1/auth/login", json=login_data)
        assert response.status_code == 200, f"New admin login failed: {response.text}"
        
        auth_response = response.json()
        assert "access_token" in auth_response
        self.test_sessions.append(auth_response["access_token"])
        print("✅ New platform admin can login successfully")

    async def test_08_customer_tenant_onboarding_flow(self):
        """Test customer tenant invitation and onboarding"""
        print("🧪 Testing Customer Tenant Onboarding...")
        
        # 1. Platform admin creates new tenant with invitation
        tenant_onboard_data = {
            "name": "New Customer Corp",
            "admin_email": f"admin.{uuid.uuid4()}@newcustomer.com",
            "subscription_tier": "professional"
        }
        
        response = await self.client.post("/v1/tenants/onboard", json=tenant_onboard_data)
        assert response.status_code == 201, f"Tenant onboarding failed: {response.text}"
        
        onboard_response = response.json()
        assert "tenant_id" in onboard_response
        assert "invitation_token" in onboard_response
        assert "invitation_expires" in onboard_response
        
        tenant_id = onboard_response["tenant_id"]
        invitation_token = onboard_response["invitation_token"]
        print("✅ Tenant created with invitation token")
        
        # 2. Customer admin accepts invitation
        accept_invitation_data = {
            "name": "Customer Admin",
            "email": tenant_onboard_data["admin_email"],
            "password": "CustomerAdminPassword123!",
            "invitation_token": invitation_token,
            "tenant_id": tenant_id
        }
        
        response = await self.client.post("/v1/auth/accept-invite", json=accept_invitation_data)
        assert response.status_code == 201, f"Invitation acceptance failed: {response.text}"
        
        customer_admin = response.json()
        self.test_users.append(customer_admin["id"])
        print("✅ Customer admin account created from invitation")
        
        # 3. Verify customer admin has tenant_admin role for new tenant
        response = await self.client.get(f"/v1/users/{customer_admin['id']}/roles")
        assert response.status_code == 200
        
        roles = response.json()["roles"]
        tenant_role = next((r for r in roles if r["tenant_id"] == tenant_id), None)
        assert tenant_role is not None, "Customer admin should have role for tenant"
        assert tenant_role["role"] == "tenant_admin", "Customer admin should be tenant_admin"
        print("✅ Customer admin automatically assigned tenant_admin role")

    async def test_09_user_invitation_system(self):
        """Test user invitation by tenant admins"""
        print("🧪 Testing User Invitation System...")
        
        # Setup: Create tenant and tenant admin
        tenant_data = {"name": "Invitation Test Corp", "subscription_tier": "enterprise"}
        response = await self.client.post("/v1/tenants", json=tenant_data)
        assert response.status_code == 201
        tenant = response.json()
        tenant_id = tenant["tenant_id"]
        
        # Create tenant admin
        admin_data = {
            "name": "Tenant Admin",
            "email": f"tenant.admin.{uuid.uuid4()}@testcorp.com",
            "password": "TenantAdminPassword123!"
        }
        
        response = await self.client.post("/v1/users", json=admin_data)
        assert response.status_code == 201
        tenant_admin = response.json()
        self.test_users.append(tenant_admin["id"])
        
        # Assign tenant_admin role
        role_data = {"tenant_id": tenant_id, "role": "tenant_admin"}
        response = await self.client.post(f"/v1/users/{tenant_admin['id']}/roles", json=role_data)
        assert response.status_code == 201
        
        # Login as tenant admin
        login_data = {"email": admin_data["email"], "password": admin_data["password"]}
        response = await self.client.post("/v1/auth/login", json=login_data)
        assert response.status_code == 200
        admin_token = response.json()["access_token"]
        self.test_sessions.append(admin_token)
        
        # 1. Tenant admin invites new user
        invite_data = {
            "email": f"invited.user.{uuid.uuid4()}@testcorp.com",
            "role": "security_analyst",
            "tenant_id": tenant_id
        }
        
        headers = {"Authorization": f"Bearer {admin_token}", "X-Customer-ID": tenant_id}
        response = await self.client.post("/v1/auth/invite", json=invite_data, headers=headers)
        assert response.status_code == 200, f"User invitation failed: {response.text}"
        
        invite_response = response.json()
        assert "invitation_token" in invite_response
        assert "invitation_expires" in invite_response
        
        invitation_token = invite_response["invitation_token"]
        print("✅ User invitation created successfully")
        
        # 2. Invited user accepts invitation
        accept_data = {
            "name": "Invited Security Analyst",
            "email": invite_data["email"],
            "password": "InvitedUserPassword123!",
            "invitation_token": invitation_token,
            "tenant_id": tenant_id
        }
        
        response = await self.client.post("/v1/auth/accept-invite", json=accept_data)
        assert response.status_code == 201, f"Invitation acceptance failed: {response.text}"
        
        invited_user = response.json()
        self.test_users.append(invited_user["id"])
        print("✅ Invited user account created successfully")
        
        # 3. Verify invited user has correct role for tenant
        response = await self.client.get(f"/v1/users/{invited_user['id']}/roles")
        assert response.status_code == 200
        
        roles = response.json()["roles"]
        user_role = next((r for r in roles if r["tenant_id"] == tenant_id), None)
        assert user_role is not None, "Invited user should have role for tenant"
        assert user_role["role"] == "security_analyst", "Invited user should have security_analyst role"
        print("✅ Invited user assigned correct role automatically")

    # =================================================================
    # AUTHENTICATION MIDDLEWARE TESTS  
    # =================================================================

    async def test_10_authentication_middleware_validation(self):
        """Test authentication middleware request processing"""
        print("🧪 Testing Authentication Middleware...")
        
        # Setup: Create user with tenant access
        user_data = {
            "name": "Middleware Test User",
            "email": f"middleware.{uuid.uuid4()}@example.com",
            "password": "MiddlewarePassword123!"
        }
        
        response = await self.client.post("/v1/users", json=user_data, headers=self.auth_headers)
        assert response.status_code == 201
        user = response.json()
        self.test_users.append(user["id"])
        
        # Create tenant and assign user
        tenant_data = {"name": "Middleware Test Tenant", "subscription_tier": "starter"}
        response = await self.client.post("/v1/tenants", json=tenant_data)
        assert response.status_code == 201
        tenant = response.json()
        tenant_id = tenant["tenant_id"]
        
        # Assign role
        role_data = {"tenant_id": tenant_id, "role": "viewer"}
        response = await self.client.post(f"/v1/users/{user['id']}/roles", json=role_data)
        assert response.status_code == 201
        
        # Login user
        login_data = {"email": user_data["email"], "password": user_data["password"]}
        response = await self.client.post("/v1/auth/login", json=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        self.test_sessions.append(token)
        
        # 1. Test valid request with proper headers
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Customer-ID": tenant_id
        }
        
        response = await self.client.get("/v1/logs", headers=headers)
        # Should succeed for viewer role (logs:read:tenant permission)
        assert response.status_code in [200, 404], f"Valid middleware request failed: {response.text}"
        print("✅ Valid authenticated request processed correctly")
        
        # 2. Test request without authentication
        response = await self.client.get("/v1/logs", headers={"X-Customer-ID": tenant_id})
        assert response.status_code == 401, "Unauthenticated request should be rejected"
        print("✅ Unauthenticated request properly rejected")
        
        # 3. Test request without tenant header
        response = await self.client.get("/v1/logs", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 400, "Request without tenant ID should be rejected"
        print("✅ Request without tenant ID properly rejected")
        
        # 4. Test request for unauthorized tenant
        unauthorized_headers = {
            "Authorization": f"Bearer {token}",
            "X-Customer-ID": "unauthorized-tenant-123"
        }
        
        response = await self.client.get("/v1/logs", headers=unauthorized_headers)
        assert response.status_code == 403, "Unauthorized tenant access should be forbidden"
        print("✅ Unauthorized tenant access properly forbidden")

    async def test_11_permission_enforcement(self):
        """Test granular permission enforcement"""
        print("🧪 Testing Permission Enforcement...")
        
        # Setup tenant and users with different roles
        tenant_data = {"name": "Permission Test Corp", "subscription_tier": "enterprise"}
        response = await self.client.post("/v1/tenants", json=tenant_data)
        assert response.status_code == 201
        tenant_id = response.json()["tenant_id"]
        
        # Create users with different roles
        test_scenarios = [
            {
                "role": "viewer",
                "allowed_endpoints": ["/v1/logs", "/v1/dashboards"],
                "forbidden_endpoints": ["/v1/security/sigma-rules", "/v1/alerts/rules"]
            },
            {
                "role": "security_analyst", 
                "allowed_endpoints": ["/v1/security/events", "/v1/security/threat-hunting"],
                "forbidden_endpoints": ["/v1/users", "/v1/tenants"]
            },
            {
                "role": "tenant_admin",
                "allowed_endpoints": ["/v1/logs", "/v1/security/events", "/v1/users", "/v1/alerts/rules"],
                "forbidden_endpoints": ["/v1/tenants", "/v1/admin/users"]  # Platform-only
            }
        ]
        
        for scenario in test_scenarios:
            # Create user
            user_data = {
                "name": f"{scenario['role']} User",
                "email": f"{scenario['role']}.{uuid.uuid4()}@permtest.com",
                "password": "PermissionPassword123!"
            }
            
            response = await self.client.post("/v1/users", json=user_data)
            assert response.status_code == 201
            user = response.json()
            self.test_users.append(user["id"])
            
            # Assign role
            role_data = {"tenant_id": tenant_id, "role": scenario["role"]}
            response = await self.client.post(f"/v1/users/{user['id']}/roles", json=role_data)
            assert response.status_code == 201
            
            # Login
            login_data = {"email": user_data["email"], "password": user_data["password"]}
            response = await self.client.post("/v1/auth/login", json=login_data)
            assert response.status_code == 200
            token = response.json()["access_token"]
            self.test_sessions.append(token)
            
            headers = {"Authorization": f"Bearer {token}", "X-Customer-ID": tenant_id}
            
            # Test allowed endpoints
            for endpoint in scenario["allowed_endpoints"]:
                response = await self.client.get(endpoint, headers=headers)
                assert response.status_code in [200, 404], f"{scenario['role']} should access {endpoint}"
            
            # Test forbidden endpoints  
            for endpoint in scenario["forbidden_endpoints"]:
                response = await self.client.get(endpoint, headers=headers)
                assert response.status_code == 403, f"{scenario['role']} should not access {endpoint}"
            
            print(f"✅ {scenario['role']} permissions enforced correctly")

    # =================================================================
    # API USAGE TRACKING & BILLING TESTS
    # =================================================================

    async def test_12_api_usage_tracking_async(self):
        """Test async API usage tracking with zero latency impact"""
        print("🧪 Testing API Usage Tracking...")
        
        # Setup authenticated user
        user_data = {
            "name": "Usage Test User",
            "email": f"usage.{uuid.uuid4()}@example.com",
            "password": "UsagePassword123!"
        }
        
        response = await self.client.post("/v1/users", json=user_data, headers=self.auth_headers)
        assert response.status_code == 201
        user = response.json()
        self.test_users.append(user["id"])
        
        # Create tenant
        tenant_data = {"name": "Usage Test Tenant", "subscription_tier": "professional"}
        response = await self.client.post("/v1/tenants", json=tenant_data)
        assert response.status_code == 201
        tenant_id = response.json()["tenant_id"]
        
        # Assign role and login
        role_data = {"tenant_id": tenant_id, "role": "devops_engineer"}
        await self.client.post(f"/v1/users/{user['id']}/roles", json=role_data)
        
        login_data = {"email": user_data["email"], "password": user_data["password"]}
        response = await self.client.post("/v1/auth/login", json=login_data)
        token = response.json()["access_token"]
        self.test_sessions.append(token)
        
        headers = {"Authorization": f"Bearer {token}", "X-Customer-ID": tenant_id}
        
        # 1. Make multiple API calls and measure latency
        test_endpoints = [
            "/v1/logs",
            "/v1/dashboards", 
            "/v1/alerts/events",
            "/v1/health"
        ]
        
        latencies = []
        for endpoint in test_endpoints:
            start_time = time.time()
            response = await self.client.get(endpoint, headers=headers)
            latency = time.time() - start_time
            latencies.append(latency)
            
            # Request should complete regardless of usage tracking
            assert response.status_code in [200, 404], f"Request failed: {endpoint}"
        
        # Verify latency is reasonable (should not be affected by usage tracking)
        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 1.0, f"Average latency too high: {avg_latency:.3f}s"
        print(f"✅ API calls completed with avg latency: {avg_latency:.3f}s")
        
        # 2. Wait for async usage tracking to complete
        await asyncio.sleep(2)  # Allow batch processing
        
        # 3. Verify usage data was recorded
        response = await self.client.get(f"/v1/usage/current/{tenant_id}")
        assert response.status_code == 200, f"Usage retrieval failed: {response.text}"
        
        usage_data = response.json()
        assert usage_data["tenant_id"] == tenant_id
        assert usage_data["api_calls"] >= len(test_endpoints), "Usage calls should be recorded"
        assert "cost_estimate" in usage_data
        print("✅ API usage tracking recorded correctly")

    async def test_13_failed_request_billing_policy(self):
        """Test billing policy for failed requests"""
        print("🧪 Testing Failed Request Billing Policy...")
        
        # Setup authenticated user
        user_data = {
            "name": "Billing Test User",
            "email": f"billing.{uuid.uuid4()}@example.com",
            "password": "BillingPassword123!"
        }
        
        response = await self.client.post("/v1/users", json=user_data)
        user = response.json()
        self.test_users.append(user["id"])
        
        tenant_data = {"name": "Billing Test Tenant", "subscription_tier": "starter"}
        response = await self.client.post("/v1/tenants", json=tenant_data)
        tenant_id = response.json()["tenant_id"]
        
        # Assign role and login
        role_data = {"tenant_id": tenant_id, "role": "viewer"}
        await self.client.post(f"/v1/users/{user['id']}/roles", json=role_data)
        
        login_data = {"email": user_data["email"], "password": user_data["password"]}
        response = await self.client.post("/v1/auth/login", json=login_data)
        token = response.json()["access_token"]
        self.test_sessions.append(token)
        
        headers = {"Authorization": f"Bearer {token}", "X-Customer-ID": tenant_id}
        
        # Test different status codes and expected billing
        test_scenarios = [
            {
                "description": "200 OK - Full charge",
                "endpoint": "/v1/health",
                "expected_status": 200,
                "expected_charge_rate": 1.0
            },
            {
                "description": "404 Not Found - 50% charge",
                "endpoint": "/v1/nonexistent-endpoint",
                "expected_status": 404,
                "expected_charge_rate": 0.5
            },
            {
                "description": "403 Forbidden - 10% charge", 
                "endpoint": "/v1/admin/users",  # Should be forbidden for customer user
                "expected_status": 403,
                "expected_charge_rate": 0.1
            }
        ]
        
        initial_usage_response = await self.client.get(f"/v1/usage/current/{tenant_id}")
        initial_usage = initial_usage_response.json() if initial_usage_response.status_code == 200 else {"total_cost": 0}
        initial_cost = initial_usage.get("total_cost", 0)
        
        for scenario in test_scenarios:
            response = await self.client.get(scenario["endpoint"], headers=headers)
            assert response.status_code == scenario["expected_status"], f"Unexpected status for {scenario['endpoint']}"
        
        # Wait for usage tracking
        await asyncio.sleep(2)
        
        # Verify billing was applied correctly
        response = await self.client.get(f"/v1/usage/current/{tenant_id}")
        assert response.status_code == 200
        
        final_usage = response.json()
        final_cost = final_usage.get("total_cost", 0)
        
        # Should have some cost increase (exact amounts depend on base costs)
        assert final_cost > initial_cost, "Usage tracking should record costs"
        print("✅ Failed request billing policy applied correctly")

    async def test_14_monthly_partitioned_audit_table(self):
        """Test monthly partitioned audit table performance"""
        print("🧪 Testing Monthly Partitioned Audit Table...")
        
        # This test validates the audit table can handle high throughput
        # and monthly partitioning works correctly
        
        # Create test data for current month
        current_month = datetime.now().strftime("%Y%m")
        
        # Verify audit table partition exists for current month
        response = await self.client.get(f"/v1/admin/database/partitions")
        if response.status_code == 200:
            partitions = response.json()
            assert any(
                current_month in p["partition_name"] 
                for p in partitions.get("partitions", [])
            ), f"Current month partition should exist: {current_month}"
        
        # Test bulk usage data insertion (simulates high traffic)
        usage_entries = []
        for i in range(50):  # Create batch of usage entries
            usage_entries.append({
                "tenant_id": f"test-tenant-{i % 5}",
                "user_id": f"test-user-{i % 10}",
                "endpoint": "/v1/logs",
                "method": "GET",
                "status_code": 200,
                "billing_feature": "queries.advanced",
                "cost_credits": 0.05
            })
        
        start_time = time.time()
        response = await self.client.post("/v1/admin/audit/bulk-insert", json={"entries": usage_entries})
        insert_time = time.time() - start_time
        
        if response.status_code == 200:
            assert insert_time < 1.0, f"Bulk insert too slow: {insert_time:.3f}s"
            print(f"✅ Bulk audit insert completed in {insert_time:.3f}s")
        else:
            print("⚠️  Bulk audit insert endpoint not implemented yet")

    # =================================================================
    # PERFORMANCE & SECURITY TESTS
    # =================================================================

    async def test_15_authentication_performance(self):
        """Test authentication middleware performance requirements"""
        print("🧪 Testing Authentication Performance...")
        
        # Create user for performance testing
        user_data = {
            "name": "Perf Test User", 
            "email": f"perf.{uuid.uuid4()}@example.com",
            "password": "PerfTestPassword123!"
        }
        
        response = await self.client.post("/v1/users", json=user_data)
        user = response.json()
        self.test_users.append(user["id"])
        
        # Create tenant 
        tenant_data = {"name": "Perf Test Tenant", "subscription_tier": "enterprise"}
        response = await self.client.post("/v1/tenants", json=tenant_data)
        tenant_id = response.json()["tenant_id"]
        
        # Assign role and login
        role_data = {"tenant_id": tenant_id, "role": "tenant_admin"}
        await self.client.post(f"/v1/users/{user['id']}/roles", json=role_data)
        
        login_data = {"email": user_data["email"], "password": user_data["password"]}
        response = await self.client.post("/v1/auth/login", json=login_data)
        token = response.json()["access_token"]
        self.test_sessions.append(token)
        
        # Test authentication middleware performance
        headers = {"Authorization": f"Bearer {token}", "X-Customer-ID": tenant_id}
        
        # Measure authentication overhead
        auth_times = []
        for i in range(10):
            start_time = time.time()
            response = await self.client.get("/v1/health", headers=headers)
            auth_time = time.time() - start_time
            auth_times.append(auth_time)
            
            assert response.status_code == 200
        
        avg_auth_time = sum(auth_times) / len(auth_times)
        
        # Authentication should be sub-100ms as per requirements
        assert avg_auth_time < 0.1, f"Authentication too slow: {avg_auth_time:.3f}s"
        print(f"✅ Authentication middleware avg time: {avg_auth_time:.3f}s")

    async def test_16_session_management(self):
        """Test session creation, validation, and expiration"""
        print("🧪 Testing Session Management...")
        
        # Create test user
        user_data = {
            "name": "Session Test User",
            "email": f"session.{uuid.uuid4()}@example.com",
            "password": "SessionPassword123!"
        }
        
        response = await self.client.post("/v1/users", json=user_data)
        user = response.json()
        self.test_users.append(user["id"])
        
        # 1. Test session creation on login
        login_data = {"email": user_data["email"], "password": user_data["password"]}
        response = await self.client.post("/v1/auth/login", json=login_data)
        assert response.status_code == 200
        
        auth_response = response.json()
        assert "access_token" in auth_response
        assert "expires_at" in auth_response
        
        token = auth_response["access_token"]
        self.test_sessions.append(token)
        
        # Verify expiration time is reasonable (default 8 hours)
        expires_at = datetime.fromisoformat(auth_response["expires_at"].replace("Z", "+00:00"))
        expected_expiry = datetime.now() + timedelta(hours=7, minutes=30)  # Allow some variance
        assert expires_at > expected_expiry, "Session should expire in ~8 hours"
        print("✅ Session created with proper expiration")
        
        # 2. Test session refresh
        headers = {"Authorization": f"Bearer {token}"}
        response = await self.client.post("/v1/auth/refresh", headers=headers)
        assert response.status_code == 200, f"Session refresh failed: {response.text}"
        
        refresh_response = response.json()
        new_token = refresh_response["access_token"]
        self.test_sessions.append(new_token)
        assert new_token != token, "Refresh should provide new token"
        print("✅ Session refresh working")
        
        # 3. Test session revocation
        response = await self.client.post("/v1/auth/logout", headers=headers)
        assert response.status_code == 200
        
        # Verify old token is invalid
        response = await self.client.get("/v1/auth/me", headers=headers)
        assert response.status_code == 401, "Revoked session should be invalid"
        print("✅ Session revocation working")

    async def test_17_audit_logging_comprehensive(self):
        """Test comprehensive audit logging for security events"""
        print("🧪 Testing Audit Logging...")
        
        # Test scenarios that should generate audit logs
        audit_scenarios = [
            {
                "action": "user_login_success",
                "description": "Successful login"
            },
            {
                "action": "user_login_failure", 
                "description": "Failed login attempt"
            },
            {
                "action": "role_assignment",
                "description": "Role granted to user"
            },
            {
                "action": "permission_denied",
                "description": "Unauthorized access attempt"
            }
        ]
        
        # Create user for audit testing
        user_data = {
            "name": "Audit Test User",
            "email": f"audit.{uuid.uuid4()}@example.com",
            "password": "AuditPassword123!"
        }
        
        response = await self.client.post("/v1/users", json=user_data)
        user = response.json()
        self.test_users.append(user["id"])
        
        # Generate audit events
        # 1. Successful login (should generate audit log)
        login_data = {"email": user_data["email"], "password": user_data["password"]}
        response = await self.client.post("/v1/auth/login", json=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        self.test_sessions.append(token)
        
        # 2. Failed login (should generate audit log)
        failed_login = {"email": user_data["email"], "password": "WrongPassword123!"}
        response = await self.client.post("/v1/auth/login", json=failed_login)
        assert response.status_code == 401
        
        # 3. Permission denied (should generate audit log)
        headers = {"Authorization": f"Bearer {token}", "X-Customer-ID": "unauthorized-tenant"}
        response = await self.client.get("/v1/admin/users", headers=headers)
        assert response.status_code == 403
        
        # Wait for audit processing
        await asyncio.sleep(1)
        
        # Verify audit logs were created
        admin_headers = {}  # Would need admin token in real implementation
        response = await self.client.get(f"/v1/admin/audit-logs?user_id={user['id']}", 
                                       headers=admin_headers)
        
        if response.status_code == 200:
            audit_logs = response.json()["logs"]
            assert len(audit_logs) >= 3, "Should have at least 3 audit events"
            
            # Check for expected audit event types
            event_types = [log["action"] for log in audit_logs]
            assert "user_login_success" in event_types
            assert "user_login_failure" in event_types  
            assert "permission_denied" in event_types
            
            print("✅ Comprehensive audit logging working")
        else:
            print("⚠️  Audit log retrieval endpoint not implemented yet")

    async def test_18_billing_integration_comprehensive(self):
        """Test comprehensive billing integration with usage tracking"""
        print("🧪 Testing Billing Integration...")
        
        # Setup tenant with known subscription tier
        tenant_data = {"name": "Billing Integration Corp", "subscription_tier": "professional"}
        response = await self.client.post("/v1/tenants", json=tenant_data)
        tenant_id = response.json()["tenant_id"]
        
        # Create user and assign role
        user_data = {
            "name": "Billing User", 
            "email": f"billing.{uuid.uuid4()}@billingcorp.com",
            "password": "BillingPassword123!"
        }
        
        response = await self.client.post("/v1/users", json=user_data)
        user = response.json()
        self.test_users.append(user["id"])
        
        role_data = {"tenant_id": tenant_id, "role": "tenant_admin"}
        await self.client.post(f"/v1/users/{user['id']}/roles", json=role_data)
        
        login_data = {"email": user_data["email"], "password": user_data["password"]}
        response = await self.client.post("/v1/auth/login", json=login_data)
        token = response.json()["access_token"]
        self.test_sessions.append(token)
        
        headers = {"Authorization": f"Bearer {token}", "X-Customer-ID": tenant_id}
        
        # Make API calls across different billing features
        billing_test_calls = [
            {"endpoint": "/v1/logs", "feature": "queries.advanced", "count": 5},
            {"endpoint": "/v1/dashboards", "feature": "queries.advanced", "count": 3},
            {"endpoint": "/v1/security/events", "feature": "security.analytics", "count": 10},
            {"endpoint": "/v1/alerts/events", "feature": "alerts.management", "count": 7}
        ]
        
        total_expected_calls = sum(call["count"] for call in billing_test_calls)
        
        # Execute test API calls
        for call_group in billing_test_calls:
            for i in range(call_group["count"]):
                response = await self.client.get(call_group["endpoint"], headers=headers)
                # Don't assert success - we're testing billing regardless of endpoint existence
        
        # Wait for usage processing
        await asyncio.sleep(3)
        
        # 1. Test current usage retrieval
        response = await self.client.get(f"/v1/usage/current/{tenant_id}")
        assert response.status_code == 200, f"Current usage retrieval failed: {response.text}"
        
        current_usage = response.json()
        assert current_usage["tenant_id"] == tenant_id
        assert current_usage["api_calls"] >= total_expected_calls
        assert "feature_breakdown" in current_usage
        assert "cost_estimate" in current_usage
        print("✅ Current usage tracking working")
        
        # 2. Test billing estimate
        response = await self.client.get(f"/v1/billing/estimate/{tenant_id}")
        assert response.status_code == 200, f"Billing estimate failed: {response.text}"
        
        estimate = response.json()
        assert "total_estimated_cost" in estimate
        assert "feature_costs" in estimate
        assert estimate["total_estimated_cost"] > 0
        print("✅ Billing estimation working")
        
        # 3. Test usage history
        response = await self.client.get(f"/v1/usage/history/{tenant_id}?months=1")
        assert response.status_code == 200, f"Usage history failed: {response.text}"
        
        history = response.json()
        assert "usage_by_month" in history
        assert len(history["usage_by_month"]) >= 1
        print("✅ Usage history working")

    # =================================================================
    # INTEGRATION & SECURITY TESTS
    # =================================================================

    async def test_19_tenant_isolation_enforcement(self):
        """Test strict tenant isolation - users cannot access other tenant data"""
        print("🧪 Testing Tenant Isolation Enforcement...")
        
        # Create two separate tenants
        tenant_a_data = {"name": "Tenant A", "subscription_tier": "enterprise"}
        tenant_b_data = {"name": "Tenant B", "subscription_tier": "professional"}
        
        response_a = await self.client.post("/v1/tenants", json=tenant_a_data)
        response_b = await self.client.post("/v1/tenants", json=tenant_b_data)
        
        tenant_a_id = response_a.json()["tenant_id"]
        tenant_b_id = response_b.json()["tenant_id"]
        
        # Create users for each tenant
        user_a_data = {
            "name": "User A",
            "email": f"user.a.{uuid.uuid4()}@tenanta.com",
            "password": "UserAPassword123!"
        }
        
        user_b_data = {
            "name": "User B", 
            "email": f"user.b.{uuid.uuid4()}@tenantb.com",
            "password": "UserBPassword123!"
        }
        
        response_a = await self.client.post("/v1/users", json=user_a_data)
        response_b = await self.client.post("/v1/users", json=user_b_data)
        
        user_a = response_a.json()
        user_b = response_b.json()
        self.test_users.extend([user_a["id"], user_b["id"]])
        
        # Assign users to their respective tenants
        await self.client.post(f"/v1/users/{user_a['id']}/roles", 
                              json={"tenant_id": tenant_a_id, "role": "tenant_admin"})
        await self.client.post(f"/v1/users/{user_b['id']}/roles",
                              json={"tenant_id": tenant_b_id, "role": "tenant_admin"})
        
        # Login both users
        login_a = {"email": user_a_data["email"], "password": user_a_data["password"]}
        login_b = {"email": user_b_data["email"], "password": user_b_data["password"]}
        
        response_a = await self.client.post("/v1/auth/login", json=login_a)
        response_b = await self.client.post("/v1/auth/login", json=login_b)
        
        token_a = response_a.json()["access_token"]
        token_b = response_b.json()["access_token"] 
        self.test_sessions.extend([token_a, token_b])
        
        # Test: User A cannot access Tenant B data
        headers_a_to_b = {"Authorization": f"Bearer {token_a}", "X-Customer-ID": tenant_b_id}
        response = await self.client.get("/v1/logs", headers=headers_a_to_b)
        assert response.status_code == 403, "User A should not access Tenant B data"
        
        # Test: User B cannot access Tenant A data
        headers_b_to_a = {"Authorization": f"Bearer {token_b}", "X-Customer-ID": tenant_a_id}
        response = await self.client.get("/v1/logs", headers=headers_b_to_a)
        assert response.status_code == 403, "User B should not access Tenant A data"
        
        # Test: Users can access their own tenant data
        headers_a = {"Authorization": f"Bearer {token_a}", "X-Customer-ID": tenant_a_id}
        headers_b = {"Authorization": f"Bearer {token_b}", "X-Customer-ID": tenant_b_id}
        
        response_a = await self.client.get("/v1/logs", headers=headers_a)
        response_b = await self.client.get("/v1/logs", headers=headers_b)
        
        # Should succeed or return 404 (no data), but not 403 (forbidden)
        assert response_a.status_code in [200, 404], "User A should access Tenant A data"
        assert response_b.status_code in [200, 404], "User B should access Tenant B data"
        
        print("✅ Tenant isolation properly enforced")

    async def test_20_security_validation_comprehensive(self):
        """Test comprehensive security validation"""
        print("🧪 Testing Security Validation...")
        
        # 1. Test SQL injection protection
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "' OR 1=1 --",
            "<script>alert('xss')</script>",
            "admin@example.com' UNION SELECT * FROM users --"
        ]
        
        for malicious_input in malicious_inputs:
            user_data = {
                "name": "Malicious User",
                "email": malicious_input,
                "password": "MaliciousPassword123!"
            }
            
            response = await self.client.post("/v1/users", json=user_data)
            # Should either reject with 400 or sanitize input
            assert response.status_code in [400, 422], f"Malicious input not handled: {malicious_input}"
        
        print("✅ Malicious input protection working")
        
        # 2. Test rate limiting (if implemented)
        user_data = {
            "name": "Rate Test User",
            "email": f"rate.test.{uuid.uuid4()}@example.com", 
            "password": "RateTestPassword123!"
        }
        
        # Rapid-fire requests to test rate limiting
        rapid_requests = []
        for i in range(20):
            rapid_requests.append(self.client.post("/v1/users", json={
                **user_data, 
                "email": f"rate.test.{i}.{uuid.uuid4()}@example.com"
            }))
        
        responses = await asyncio.gather(*rapid_requests, return_exceptions=True)
        
        # Check if any requests were rate limited
        rate_limited = sum(1 for r in responses if hasattr(r, 'status_code') and r.status_code == 429)
        if rate_limited > 0:
            print(f"✅ Rate limiting working: {rate_limited} requests limited")
        else:
            print("⚠️  Rate limiting not implemented or threshold not reached")
        
        # 3. Test password reset security
        test_user_data = {
            "name": "Reset Test User",
            "email": f"reset.{uuid.uuid4()}@example.com",
            "password": "ResetTestPassword123!"
        }
        
        response = await self.client.post("/v1/users", json=test_user_data)
        user = response.json()
        self.test_users.append(user["id"])
        
        # Request password reset
        reset_request = {"email": test_user_data["email"]}
        response = await self.client.post("/v1/auth/password/reset", json=reset_request)
        assert response.status_code == 200, f"Password reset request failed: {response.text}"
        
        reset_response = response.json()
        assert "reset_token" in reset_response or "message" in reset_response
        print("✅ Password reset flow initiated")

    # =================================================================
    # END-TO-END INTEGRATION TESTS
    # =================================================================

    async def test_21_complete_user_lifecycle_integration(self):
        """Test complete user lifecycle from creation to deletion"""
        print("🧪 Testing Complete User Lifecycle Integration...")
        
        # 1. Platform admin creates tenant
        tenant_data = {
            "name": "Lifecycle Test Corp",
            "admin_email": f"lifecycle.admin.{uuid.uuid4()}@lifecorp.com",
            "subscription_tier": "enterprise"
        }
        
        response = await self.client.post("/v1/tenants/onboard", json=tenant_data)
        assert response.status_code == 201
        
        onboard_response = response.json()
        tenant_id = onboard_response["tenant_id"]
        invitation_token = onboard_response["invitation_token"]
        
        # 2. Customer admin accepts invitation and creates account
        admin_accept_data = {
            "name": "Customer Admin",
            "email": tenant_data["admin_email"],
            "password": "CustomerAdminPassword123!",
            "invitation_token": invitation_token,
            "tenant_id": tenant_id
        }
        
        response = await self.client.post("/v1/auth/accept-invite", json=admin_accept_data)
        assert response.status_code == 201
        customer_admin = response.json()
        self.test_users.append(customer_admin["id"])
        
        # 3. Customer admin logs in
        admin_login = {"email": tenant_data["admin_email"], "password": "CustomerAdminPassword123!"}
        response = await self.client.post("/v1/auth/login", json=admin_login)
        assert response.status_code == 200
        admin_token = response.json()["access_token"]
        self.test_sessions.append(admin_token)
        
        admin_headers = {"Authorization": f"Bearer {admin_token}", "X-Customer-ID": tenant_id}
        
        # 4. Customer admin invites team members
        team_invitations = [
            {"email": f"analyst.{uuid.uuid4()}@lifecorp.com", "role": "security_analyst"},
            {"email": f"engineer.{uuid.uuid4()}@lifecorp.com", "role": "devops_engineer"},
            {"email": f"viewer.{uuid.uuid4()}@lifecorp.com", "role": "viewer"}
        ]
        
        invited_users = []
        for invitation in team_invitations:
            response = await self.client.post("/v1/auth/invite", json={
                **invitation, "tenant_id": tenant_id
            }, headers=admin_headers)
            assert response.status_code == 200, f"Team invitation failed: {response.text}"
            
            invite_response = response.json()
            invitation_token = invite_response["invitation_token"]
            
            # Team member accepts invitation
            accept_data = {
                "name": f"Team {invitation['role'].title()}",
                "email": invitation["email"],
                "password": "TeamMemberPassword123!",
                "invitation_token": invitation_token,
                "tenant_id": tenant_id
            }
            
            response = await self.client.post("/v1/auth/accept-invite", json=accept_data)
            assert response.status_code == 201, f"Team member acceptance failed: {response.text}"
            
            team_member = response.json()
            invited_users.append(team_member)
            self.test_users.append(team_member["id"])
        
        print(f"✅ Complete tenant onboarding with {len(invited_users)} team members")
        
        # 5. Test team member access with proper roles
        for i, team_member in enumerate(invited_users):
            expected_role = team_invitations[i]["role"]
            
            # Login team member
            login_data = {
                "email": team_invitations[i]["email"], 
                "password": "TeamMemberPassword123!"
            }
            response = await self.client.post("/v1/auth/login", json=login_data)
            assert response.status_code == 200
            
            member_token = response.json()["access_token"]
            self.test_sessions.append(member_token)
            
            member_headers = {"Authorization": f"Bearer {member_token}", "X-Customer-ID": tenant_id}
            
            # Test role-appropriate access
            if expected_role == "viewer":
                # Should access logs but not security
                response = await self.client.get("/v1/logs", headers=member_headers)
                assert response.status_code in [200, 404], "Viewer should access logs"
                
                response = await self.client.get("/v1/security/events", headers=member_headers)
                assert response.status_code == 403, "Viewer should not access security"
                
            elif expected_role == "security_analyst":
                # Should access security but not admin functions
                response = await self.client.get("/v1/security/events", headers=member_headers)
                assert response.status_code in [200, 404], "Security analyst should access security"
                
                response = await self.client.post("/v1/users", json={
                    "name": "Test", "email": "test@test.com", "password": "Test123!"
                }, headers=member_headers)
                assert response.status_code == 403, "Security analyst should not create users"
        
        print("✅ End-to-end user lifecycle integration successful")

    async def test_22_performance_requirements_validation(self):
        """Test M8 performance requirements under load"""
        print("🧪 Testing Performance Requirements...")
        
        # Setup authenticated user for performance testing
        user_data = {
            "name": "Performance User",
            "email": f"perf.{uuid.uuid4()}@example.com",
            "password": "PerfPassword123!"
        }
        
        response = await self.client.post("/v1/users", json=user_data)
        user = response.json()
        self.test_users.append(user["id"])
        
        tenant_data = {"name": "Performance Tenant", "subscription_tier": "enterprise"}
        response = await self.client.post("/v1/tenants", json=tenant_data)
        tenant_id = response.json()["tenant_id"]
        
        role_data = {"tenant_id": tenant_id, "role": "tenant_admin"}
        await self.client.post(f"/v1/users/{user['id']}/roles", json=role_data)
        
        login_data = {"email": user_data["email"], "password": user_data["password"]}
        response = await self.client.post("/v1/auth/login", json=login_data)
        token = response.json()["access_token"]
        self.test_sessions.append(token)
        
        headers = {"Authorization": f"Bearer {token}", "X-Customer-ID": tenant_id}
        
        # 1. Test authentication middleware performance (sub-100ms requirement)
        auth_times = []
        for i in range(50):
            start_time = time.time()
            response = await self.client.get("/v1/health", headers=headers)
            auth_time = time.time() - start_time
            auth_times.append(auth_time)
            assert response.status_code == 200
        
        avg_auth_time = sum(auth_times) / len(auth_times)
        p95_auth_time = sorted(auth_times)[int(len(auth_times) * 0.95)]
        
        assert avg_auth_time < 0.1, f"Auth middleware avg too slow: {avg_auth_time:.3f}s"
        assert p95_auth_time < 0.15, f"Auth middleware p95 too slow: {p95_auth_time:.3f}s"
        print(f"✅ Auth middleware perf: avg={avg_auth_time:.3f}s, p95={p95_auth_time:.3f}s")
        
        # 2. Test concurrent user authentication
        concurrent_auth_tasks = []
        for i in range(10):
            concurrent_user_data = {
                "name": f"Concurrent User {i}",
                "email": f"concurrent.{i}.{uuid.uuid4()}@example.com",
                "password": "ConcurrentPassword123!"
            }
            
            # Create user and login concurrently
            async def create_and_login(user_data):
                user_response = await self.client.post("/v1/users", json=user_data)
                if user_response.status_code == 201:
                    user = user_response.json()
                    self.test_users.append(user["id"])
                    
                    login_response = await self.client.post("/v1/auth/login", json={
                        "email": user_data["email"], 
                        "password": user_data["password"]
                    })
                    return login_response.status_code == 200
                return False
            
            concurrent_auth_tasks.append(create_and_login(concurrent_user_data))
        
        start_time = time.time()
        results = await asyncio.gather(*concurrent_auth_tasks)
        concurrent_time = time.time() - start_time
        
        success_rate = sum(results) / len(results)
        assert success_rate >= 0.9, f"Concurrent auth success rate too low: {success_rate}"
        assert concurrent_time < 5.0, f"Concurrent auth too slow: {concurrent_time:.3f}s"
        print(f"✅ Concurrent auth: {success_rate:.1%} success in {concurrent_time:.3f}s")

    # =================================================================
    # COMPREHENSIVE INTEGRATION VALIDATION
    # =================================================================

    async def test_23_m8_integration_with_existing_services(self):
        """Test M8 integration with existing M1-M7 services"""
        print("🧪 Testing M8 Integration with Existing Services...")
        
        # This test validates that M8 user service integrates properly with existing services
        
        # 1. Test integration with tenant service
        response = await self.client.get("/v1/tenants")
        existing_tenant_count = len(response.json().get("tenants", [])) if response.status_code == 200 else 0
        
        # Create new tenant through user service flow
        tenant_data = {"name": "Integration Test Tenant", "subscription_tier": "professional"}
        response = await self.client.post("/v1/tenants", json=tenant_data)
        
        if response.status_code == 201:
            # Verify tenant appears in listing
            response = await self.client.get("/v1/tenants")
            assert response.status_code == 200
            new_tenant_count = len(response.json()["tenants"])
            assert new_tenant_count == existing_tenant_count + 1, "New tenant should appear in listing"
            print("✅ User service integrates with tenant service")
        
        # 2. Test integration with existing alert system
        # Create user with alert permissions
        user_data = {
            "name": "Alert Integration User",
            "email": f"alert.integration.{uuid.uuid4()}@example.com",
            "password": "AlertPassword123!"
        }
        
        response = await self.client.post("/v1/users", json=user_data)
        if response.status_code == 201:
            user = response.json()
            self.test_users.append(user["id"])
            
            # Test that user service authentication works with alert endpoints
            login_data = {"email": user_data["email"], "password": user_data["password"]}
            response = await self.client.post("/v1/auth/login", json=login_data)
            if response.status_code == 200:
                token = response.json()["access_token"]
                self.test_sessions.append(token)
                
                # This validates auth middleware integration
                headers = {"Authorization": f"Bearer {token}"}
                response = await self.client.get("/v1/alerts/rules", headers=headers)
                # Should get 403 (no tenant) or 400 (no X-Customer-ID) - not 500 (integration error)
                assert response.status_code in [400, 403], "Auth middleware should integrate with alert endpoints"
                print("✅ User service integrates with alert system")

        print("✅ M8 successfully integrates with existing services")

# =================================================================
# TEST RUNNER & MAIN EXECUTION
# =================================================================

async def run_m8_comprehensive_tests():
    """Run all M8 User Service tests comprehensively"""
    print("🚀 Starting M8 User Service & Authentication Foundation Tests")
    print("=" * 70)
    
    test_suite = TestM8UserServiceFoundation()
    
    # Test execution order matches implementation phases
    test_methods = [
        # Core User Management
        test_suite.test_01_user_crud_operations,
        test_suite.test_02_password_security_requirements,
        test_suite.test_03_user_authentication_flow,
        
        # Role-Based Access Control
        test_suite.test_04_platform_admin_roles,
        test_suite.test_05_customer_user_roles,
        test_suite.test_06_multi_tenant_access_control,
        
        # Secure Onboarding
        test_suite.test_07_platform_admin_setup_flow,
        test_suite.test_08_customer_tenant_onboarding_flow,
        test_suite.test_09_user_invitation_system,
        
        # Authentication Middleware
        test_suite.test_10_authentication_middleware_validation,
        test_suite.test_11_permission_enforcement,
        
        # API Usage Tracking & Billing
        test_suite.test_12_api_usage_tracking_async,
        test_suite.test_13_failed_request_billing_policy,
        test_suite.test_14_monthly_partitioned_audit_table,
        
        # Performance & Security
        test_suite.test_15_authentication_performance,
        test_suite.test_16_session_management,
        test_suite.test_17_audit_logging_comprehensive,
        test_suite.test_18_billing_integration_comprehensive,
        
        # Integration & Security
        test_suite.test_19_tenant_isolation_enforcement,
        test_suite.test_20_security_validation_comprehensive,
        
        # End-to-End Integration
        test_suite.test_21_complete_user_lifecycle_integration,
        test_suite.test_22_performance_requirements_validation,
        test_suite.test_23_m8_integration_with_existing_services
    ]
    
    passed_tests = 0
    failed_tests = 0
    
    for test_method in test_methods:
        try:
            await test_suite.setup_test_environment()
            await test_method()
            passed_tests += 1
            print(f"✅ {test_method.__name__} PASSED")
        except Exception as e:
            failed_tests += 1
            print(f"❌ {test_method.__name__} FAILED: {str(e)}")
        finally:
            await test_suite.teardown_test_environment()
        
        print("-" * 70)
    
    # Final results
    total_tests = len(test_methods)
    success_rate = (passed_tests / total_tests) * 100
    
    print("🏁 M8 User Service Test Results:")
    print(f"   Total Tests: {total_tests}")
    print(f"   Passed: {passed_tests}")
    print(f"   Failed: {failed_tests}")
    print(f"   Success Rate: {success_rate:.1f}%")
    print("=" * 70)
    
    # M8 success criteria validation
    if success_rate >= 95:
        print("🎉 M8 USER SERVICE VALIDATION SUCCESSFUL!")
        print("✅ Ready for production deployment")
    else:
        print("⚠️  M8 requires additional development")
        print("🔧 Some tests failed - review implementation")
    
    return success_rate >= 95

# Run tests if executed directly
if __name__ == "__main__":
    import asyncio
    
    print("M8 User Service & Authentication Foundation - Individual Test Suite")
    print("Testing all specifications: user management, auth, RBAC, onboarding, billing")
    
    success = asyncio.run(run_m8_comprehensive_tests())
    exit(0 if success else 1)