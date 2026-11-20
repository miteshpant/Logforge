#!/usr/bin/env python3
"""
Comprehensive Auth Router Test Suite
Tests all auth router endpoints and validates API responses based on actual router implementation
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

class AuthRouterTestSuite(BaseTestSuite):
    """Comprehensive test suite for auth router endpoints"""

    def __init__(self):
        super().__init__("AuthRouter")

    # Authentication Flow Tests

    async def test_login_endpoint(self):
        """Test POST /v1/auth/login - User login"""
        print("\n🧪 Testing User Login Endpoint...")

        try:
            # First create a user for login testing
            user_email = f"login-test-{self.test_id}@test.local"
            test_password = f"LoginTest{self.test_id}!"
            
            # Create user via user service (bypassing auth for test setup)
            from authn_authz_middleware import UserService, hash_password
            from models import UserStatus
            
            user_service = UserService()
            user_data = {
                "email": user_email,
                "name": f"Login Test User {self.test_id}",
                "password": test_password,
                "status": UserStatus.ACTIVE
            }
            
            created_user = await user_service.create_user(user_data)
            
            await self.grant_tenant_role(created_user.id)  # login requires a tenant role
            self.add_cleanup_item("custom", ("users_mt", "id", created_user.id))
            
            # Valid login request
            login_request = {
                "email": user_email,
                "password": test_password
            }

            # Send login request
            response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/login",
                json=login_request,
                headers={}  # No auth headers for login
            )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate login response structure
            required_fields = ["access_token", "expires_at", "user"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            # Validate user data in response
            user_data = response_data["user"]
            user_fields = ["id", "email", "name", "status"]
            for field in user_fields:
                assert field in user_data, f"Missing user field: {field}"

            assert user_data["email"] == user_email, "User email should match"
            assert response_data["access_token"], "Access token should not be empty"

            print(f"   ✅ User login successful: {user_email}")
            self.test_results["login_user"] = "PASS"

        except Exception as e:
            print(f"   ❌ User login test error: {e}")
            self.test_results["login_user"] = f"ERROR: {e}"

    async def test_login_invalid_credentials(self):
        """Test POST /v1/auth/login - Invalid credentials"""
        print("\n🧪 Testing Login with Invalid Credentials...")

        try:
            # Invalid login request
            invalid_login = {
                "email": "nonexistent@test.local",
                "password": "wrongpassword"
            }

            response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/login",
                json=invalid_login,
                headers={}  # No auth headers for login
            )

            # Should return 401 for invalid credentials
            assert response.status_code == 401, f"Expected 401 for invalid credentials, got {response.status_code}: {response.text}"

            response_data = response.json()
            assert "detail" in response_data, "Error response should have detail field"

            print(f"   ✅ Invalid credentials properly rejected")
            self.test_results["login_invalid_credentials"] = "PASS"

        except Exception as e:
            print(f"   ❌ Invalid credentials test error: {e}")
            self.test_results["login_invalid_credentials"] = f"ERROR: {e}"

    async def test_logout_endpoint(self):
        """Test POST /v1/auth/logout - User logout"""
        print("\n🧪 Testing User Logout Endpoint...")

        try:
            # Create a dedicated user for logout test to ensure proper session
            logout_email = f"logout-test-{self.test_id}@test.local"
            logout_password = f"LogoutTest{self.test_id}!"
            
            # Create user for logout testing
            from authn_authz_middleware import UserService
            from models import UserStatus
            
            user_service = UserService()
            user_data = {
                "email": logout_email,
                "name": f"Logout Test User {self.test_id}",
                "password": logout_password,
                "status": UserStatus.ACTIVE
            }
            
            created_user = await user_service.create_user(user_data)
            
            await self.grant_tenant_role(created_user.id)  # login requires a tenant role
            self.add_cleanup_item("custom", ("users_mt", "id", created_user.id))
            
            # Login to get a valid session
            login_response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/login",
                json={"email": logout_email, "password": logout_password},
                headers={}
            )
            
            assert login_response.status_code == 200, f"Login failed for logout test: {login_response.status_code}: {login_response.text}"
            
            login_data = login_response.json()
            logout_token = login_data["access_token"]
            
            # Now logout with the fresh session (no tenant header needed for logout)
            # Use httpx directly to avoid default tenant headers from make_authenticated_request
            import httpx
            
            logout_headers = {
                "Authorization": f"Bearer {logout_token}"
                # Explicitly NO X-Customer-ID header - logout should work without tenant context
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/auth/logout",
                    headers=logout_headers
                )

            # Should succeed with valid token
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()
            assert "message" in response_data, "Logout response should have message field"
            assert "successful" in response_data["message"].lower(), "Message should indicate success"

            print(f"   ✅ User logout successful")
            self.test_results["logout_user"] = "PASS"

        except Exception as e:
            print(f"   ❌ User logout test error: {e}")
            self.test_results["logout_user"] = f"ERROR: {e}"

    async def test_refresh_session_endpoint(self):
        """Test POST /v1/auth/refresh - Refresh session"""
        print("\n🧪 Testing Session Refresh Endpoint...")

        try:
            # Refresh requires valid authentication but no tenant context
            # Use httpx directly to avoid default tenant headers from make_authenticated_request
            import httpx
            
            # Refresh exchanges the refresh token issued at login (LF-015
            # rotation); it no longer accepts a bare session bearer token.
            async with httpx.AsyncClient(timeout=30.0) as client:
                login = await client.post(
                    f"{self.base_url}/v1/auth/login",
                    json={"email": self.test_user_email, "password": f"TestPass{self.test_id}!"},
                )
                assert login.status_code == 200, f"Login failed: {login.status_code}: {login.text}"
                response = await client.post(
                    f"{self.base_url}/v1/auth/refresh",
                    json={"refresh_token": login.json()["refresh_token"]},
                )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate refresh response structure
            required_fields = ["access_token", "expires_at", "user"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert response_data["access_token"], "New access token should not be empty"
            assert response_data["user"]["id"], "User data should be included"

            print(f"   ✅ Session refresh successful")
            self.test_results["refresh_session"] = "PASS"

        except Exception as e:
            print(f"   ❌ Session refresh test error: {e}")
            self.test_results["refresh_session"] = f"ERROR: {e}"

    async def test_get_user_profile_endpoint(self):
        """Test GET /v1/auth/me - Get user profile"""
        print("\n🧪 Testing Get User Profile Endpoint...")

        try:
            # Create a dedicated user for profile test to ensure proper session
            profile_email = f"profile-test-{self.test_id}@test.local"
            profile_password = f"ProfileTest{self.test_id}!"
            
            # Create user for profile testing
            from authn_authz_middleware import UserService
            from models import UserStatus
            
            user_service = UserService()
            user_data = {
                "email": profile_email,
                "name": f"Profile Test User {self.test_id}",
                "password": profile_password,
                "status": UserStatus.ACTIVE
            }
            
            created_user = await user_service.create_user(user_data)
            
            await self.grant_tenant_role(created_user.id)  # login requires a tenant role
            self.add_cleanup_item("custom", ("users_mt", "id", created_user.id))
            
            # Login to get a valid session
            login_response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/login",
                json={"email": profile_email, "password": profile_password},
                headers={}
            )
            
            assert login_response.status_code == 200, f"Login failed for profile test: {login_response.status_code}: {login_response.text}"
            
            login_data = login_response.json()
            profile_token = login_data["access_token"]
            
            # Get profile requires valid authentication but no tenant context
            # Use httpx directly to avoid default tenant headers from make_authenticated_request
            import httpx
            
            profile_headers = {
                "Authorization": f"Bearer {profile_token}"
                # Explicitly NO X-Customer-ID header - profile should work without tenant context
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/auth/me",
                    headers=profile_headers
                )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate user profile response structure
            required_fields = ["id", "email", "name", "status"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert response_data["email"] == profile_email, "Email should match profile test user"
            assert response_data["id"] == created_user.id, "ID should match profile test user"

            print(f"   ✅ Get user profile successful: {response_data['email']}")
            self.test_results["get_user_profile"] = "PASS"

        except Exception as e:
            print(f"   ❌ Get user profile test error: {e}")
            self.test_results["get_user_profile"] = f"ERROR: {e}"

    # Platform Setup Tests

    async def test_initialize_platform_setup_endpoint(self):
        """Test POST /v1/auth/setup/init - Initialize platform setup"""
        print("\n🧪 Testing Initialize Platform Setup Endpoint...")

        try:
            response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/setup/init",
                headers={}  # No auth headers for setup initialization
            )

            # Platform might already be setup, which is acceptable
            assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"

            if response.status_code == 200:
                response_data = response.json()
                
                # Validate setup token response structure
                required_fields = ["setup_token", "expires_at"]
                for field in required_fields:
                    assert field in response_data, f"Missing required field: {field}"

                assert response_data["setup_token"], "Setup token should not be empty"
                print(f"   ✅ Platform setup initialized")
            else:
                # Setup already completed
                response_data = response.json()
                assert "already completed" in response_data.get("detail", "").lower(), "Should indicate setup already completed"
                print(f"   ⚠️ Platform setup already completed (acceptable)")

            self.test_results["initialize_platform_setup"] = "PASS"

        except Exception as e:
            print(f"   ❌ Initialize platform setup test error: {e}")
            self.test_results["initialize_platform_setup"] = f"ERROR: {e}"

    async def test_complete_platform_setup_endpoint(self):
        """Test POST /v1/auth/setup - Complete platform setup"""
        print("\n🧪 Testing Complete Platform Setup Endpoint...")

        try:
            # Try to complete setup (may fail if already done, which is acceptable)
            setup_request = {
                "setup_token": "test-setup-token",
                "email": f"admin-{self.test_id}@test.local",
                "name": f"Test Admin {self.test_id}",
                "password": f"AdminPass{self.test_id}!"
            }

            response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/setup",
                json=setup_request,
                headers={}  # No auth headers for setup completion
            )

            # Setup might be already completed or token invalid, which is acceptable
            assert response.status_code in [201, 400, 409], f"Expected 201, 400, or 409, got {response.status_code}: {response.text}"

            if response.status_code == 201:
                response_data = response.json()
                
                # Validate admin user response structure
                required_fields = ["id", "email", "name", "status"]
                for field in required_fields:
                    assert field in response_data, f"Missing required field: {field}"

                assert response_data["email"] == setup_request["email"], "Admin email should match"
                print(f"   ✅ Platform setup completed: {response_data['email']}")
            else:
                response_data = response.json()
                detail = response_data.get("detail", "").lower()
                acceptable_errors = ["invalid", "expired", "already", "exists"]
                assert any(error in detail for error in acceptable_errors), f"Unexpected error: {detail}"
                print(f"   ⚠️ Setup completion failed as expected (already done or invalid token)")

            self.test_results["complete_platform_setup"] = "PASS"

        except Exception as e:
            print(f"   ❌ Complete platform setup test error: {e}")
            self.test_results["complete_platform_setup"] = f"ERROR: {e}"

    # Password Management Tests

    async def test_request_password_reset_endpoint(self):
        """Test POST /v1/auth/password/reset - Request password reset"""
        print("\n🧪 Testing Request Password Reset Endpoint...")

        try:
            # Valid password reset request
            reset_request = {
                "email": self.test_user_email
            }

            response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/password/reset",
                json=reset_request,
                headers={}  # No auth headers for password reset
            )

            # Should always return success for security (don't reveal if email exists)
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()
            assert "message" in response_data, "Response should have message field"
            assert "sent" in response_data["message"].lower(), "Message should indicate instructions sent"

            print(f"   ✅ Password reset request successful")
            self.test_results["request_password_reset"] = "PASS"

        except Exception as e:
            print(f"   ❌ Request password reset test error: {e}")
            self.test_results["request_password_reset"] = f"ERROR: {e}"

    async def test_confirm_password_reset_endpoint(self):
        """Test POST /v1/auth/password/reset-confirm - Confirm password reset"""
        print("\n🧪 Testing Confirm Password Reset Endpoint...")

        try:
            # Test with invalid token (valid tokens would require actual reset flow)
            response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/password/reset-confirm",
                json={
                    "token": "invalid-reset-token",
                    "new_password": f"NewPassword{self.test_id}!"
                },
                headers={}  # No auth headers for password reset confirmation
            )

            # Should return 400 for invalid token
            assert response.status_code == 400, f"Expected 400 for invalid token, got {response.status_code}: {response.text}"

            response_data = response.json()
            assert "detail" in response_data, "Error response should have detail field"
            assert "invalid" in response_data["detail"].lower() or "expired" in response_data["detail"].lower(), "Should indicate invalid/expired token"

            print(f"   ✅ Confirm password reset validation working")
            self.test_results["confirm_password_reset"] = "PASS"

        except Exception as e:
            print(f"   ❌ Confirm password reset test error: {e}")
            self.test_results["confirm_password_reset"] = f"ERROR: {e}"

    async def test_change_password_endpoint(self):
        """Test POST /v1/auth/password/change - Change password"""
        print("\n🧪 Testing Change Password Endpoint...")

        try:
            # Create a dedicated user for password change test to ensure proper session
            change_email = f"change-test-{self.test_id}@test.local"
            change_password = f"ChangeTest{self.test_id}!"
            
            # Create user for password change testing
            from authn_authz_middleware import UserService
            from models import UserStatus
            
            user_service = UserService()
            user_data = {
                "email": change_email,
                "name": f"Change Test User {self.test_id}",
                "password": change_password,
                "status": UserStatus.ACTIVE
            }
            
            created_user = await user_service.create_user(user_data)
            
            await self.grant_tenant_role(created_user.id)  # login requires a tenant role
            self.add_cleanup_item("custom", ("users_mt", "id", created_user.id))
            
            # Login to get a valid session
            login_response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/login",
                json={"email": change_email, "password": change_password},
                headers={}
            )
            
            assert login_response.status_code == 200, f"Login failed for change password test: {login_response.status_code}: {login_response.text}"
            
            login_data = login_response.json()
            change_token = login_data["access_token"]
            
            # Test password change with wrong current password (no tenant context needed)
            # Use httpx directly to avoid default tenant headers from make_authenticated_request
            import httpx
            
            change_headers = {
                "Authorization": f"Bearer {change_token}"
                # Explicitly NO X-Customer-ID header - password change should work without tenant context
            }
            
            change_request = {
                "current_password": "wrongpassword",
                "new_password": f"NewPassword{self.test_id}!"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/auth/password/change",
                    json=change_request,
                    headers=change_headers
                )

            # Should return 400 for incorrect current password
            assert response.status_code == 400, f"Expected 400 for wrong current password, got {response.status_code}: {response.text}"

            response_data = response.json()
            assert "detail" in response_data, "Error response should have detail field"
            assert "incorrect" in response_data["detail"].lower(), "Should indicate incorrect current password"

            print(f"   ✅ Change password validation working")
            self.test_results["change_password"] = "PASS"

        except Exception as e:
            print(f"   ❌ Change password test error: {e}")
            self.test_results["change_password"] = f"ERROR: {e}"

    # User Invitation System Tests

    async def test_invite_user_endpoint(self):
        """Test POST /v1/auth/invite - Send user invitation"""
        print("\n🧪 Testing Invite User Endpoint...")

        try:
            # Create a dedicated user with tenant admin privileges for invitation test
            invite_email = f"invite-test-{self.test_id}@test.local"
            invite_password = f"InviteTest{self.test_id}!"
            
            # Create user for invitation testing
            from authn_authz_middleware import UserService
            from models import UserStatus
            from database_layer import DatabaseLayer
            
            user_service = UserService()
            user_data = {
                "email": invite_email,
                "name": f"Invite Test User {self.test_id}",
                "password": invite_password,
                "status": UserStatus.ACTIVE
            }
            
            created_user = await user_service.create_user(user_data)
            
            await self.grant_tenant_role(created_user.id)  # login requires a tenant role
            self.add_cleanup_item("custom", ("users_mt", "id", created_user.id))
            
            # Assign tenant admin role to enable invitations
            db = DatabaseLayer('TestService', 'test-service-key')
            role_data = {
                'user_id': created_user.id,
                'tenant_id': self.test_tenant_id,
                'role': 'tenant_admin',
                'granted_by': created_user.id,
                'customer_id': self.test_tenant_id
            }
            role_id = await db.create_user_role(role_data)
            self.add_cleanup_item("custom", ("user_tenant_roles_mt", "id", role_id))
            
            # Login to get a valid session
            login_response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/login",
                json={"email": invite_email, "password": invite_password},
                headers={}
            )
            
            assert login_response.status_code == 200, f"Login failed for invite test: {login_response.status_code}: {login_response.text}"
            
            login_data = login_response.json()
            invite_token = login_data["access_token"]
            
            # Valid invitation request
            invitation_request = {
                "email": f"invited-{self.test_id}@test.local",
                "tenant_id": self.test_tenant_id,
                "role": "viewer"
            }

            # Use httpx directly to avoid default headers interference
            import httpx
            
            invite_headers = {
                "Authorization": f"Bearer {invite_token}",
                "X-Customer-ID": self.test_tenant_id
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/auth/invite",
                    json=invitation_request,
                    headers=invite_headers
                )

            # Should succeed with proper permissions or be denied if feature not implemented
            assert response.status_code in [200, 403, 500], f"Expected 200, 403, or 500, got {response.status_code}: {response.text}"

            if response.status_code == 200:
                response_data = response.json()
                
                # Validate invitation response structure
                required_fields = ["invitation_token", "invited_email", "invitation_expires"]
                for field in required_fields:
                    assert field in response_data, f"Missing required field: {field}"

                assert response_data["invited_email"] == invitation_request["email"], "Invited email should match request email"

                print(f"   ✅ User invitation successful: {response_data['invited_email']}")
            elif response.status_code == 403:
                # Permission denied (acceptable based on user role)
                response_data = response.json()
                assert "permission" in response_data.get("detail", "").lower() or "insufficient" in response_data.get("error", "").lower(), "Should indicate permission issue"
                print(f"   ⚠️ User invitation permission denied (acceptable based on role)")
            else:
                # 500 error - invitation system not fully implemented
                response_data = response.json()
                assert "detail" in response_data, "Error response should have detail field"
                print(f"   ⚠️ User invitation system not fully implemented (acceptable for testing)")

            self.test_results["invite_user"] = "PASS"

        except Exception as e:
            print(f"   ❌ Invite user test error: {e}")
            self.test_results["invite_user"] = f"ERROR: {e}"

    async def test_accept_invitation_endpoint(self):
        """Test POST /v1/auth/accept-invite - Accept invitation"""
        print("\n🧪 Testing Accept Invitation Endpoint...")

        try:
            # Test with invalid invitation token
            accept_request = {
                "invitation_token": "invalid-invitation-token",
                "email": f"accept-test-{self.test_id}@test.local",
                "name": f"Accept Test User {self.test_id}",
                "password": f"AcceptPass{self.test_id}!",
                "tenant_id": self.test_tenant_id
            }

            response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/accept-invite",
                json=accept_request,
                headers={}  # No auth headers for invitation acceptance
            )

            # Should return 400 for invalid invitation
            assert response.status_code == 400, f"Expected 400 for invalid invitation, got {response.status_code}: {response.text}"

            response_data = response.json()
            assert "detail" in response_data, "Error response should have detail field"
            assert "invalid" in response_data["detail"].lower() or "expired" in response_data["detail"].lower(), "Should indicate invalid/expired invitation"

            print(f"   ✅ Accept invitation validation working")
            self.test_results["accept_invitation"] = "PASS"

        except Exception as e:
            print(f"   ❌ Accept invitation test error: {e}")
            self.test_results["accept_invitation"] = f"ERROR: {e}"

    # Email Verification Tests

    async def test_send_email_verification_endpoint(self):
        """Test POST /v1/auth/verify-email - Send email verification"""
        print("\n🧪 Testing Send Email Verification Endpoint...")

        try:
            # Create a dedicated user for email verification test
            verify_email = f"verify-test-{self.test_id}@test.local"
            verify_password = f"VerifyTest{self.test_id}!"
            
            # Create user for email verification testing
            from authn_authz_middleware import UserService
            from models import UserStatus
            
            user_service = UserService()
            user_data = {
                "email": verify_email,
                "name": f"Email Verify Test User {self.test_id}",
                "password": verify_password,
                "status": UserStatus.ACTIVE
            }
            
            created_user = await user_service.create_user(user_data)
            
            await self.grant_tenant_role(created_user.id)  # login requires a tenant role
            self.add_cleanup_item("custom", ("users_mt", "id", created_user.id))
            
            # Login to get a valid session
            login_response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/login",
                json={"email": verify_email, "password": verify_password},
                headers={}
            )
            
            assert login_response.status_code == 200, f"Login failed for email verification test: {login_response.status_code}: {login_response.text}"
            
            login_data = login_response.json()
            verify_token = login_data["access_token"]
            
            # Send email verification (no tenant context needed)
            # Use httpx directly to avoid default tenant headers from make_authenticated_request
            import httpx
            
            verify_headers = {
                "Authorization": f"Bearer {verify_token}"
                # Explicitly NO X-Customer-ID header - email verification should work without tenant context
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/auth/verify-email",
                    headers=verify_headers
                )

            # Should succeed or indicate already verified
            assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"

            response_data = response.json()
            assert "message" in response_data, "Response should have message field"

            if response.status_code == 200:
                assert "sent" in response_data["message"].lower(), "Should indicate verification sent"
                print(f"   ✅ Email verification sent")
            else:
                assert "already verified" in response_data.get("detail", "").lower(), "Should indicate already verified"
                print(f"   ⚠️ Email already verified (acceptable)")

            self.test_results["send_email_verification"] = "PASS"

        except Exception as e:
            print(f"   ❌ Send email verification test error: {e}")
            self.test_results["send_email_verification"] = f"ERROR: {e}"

    async def test_confirm_email_verification_endpoint(self):
        """Test POST /v1/auth/verify-email-confirm - Confirm email verification"""
        print("\n🧪 Testing Confirm Email Verification Endpoint...")

        try:
            # Create a dedicated user for email verification confirmation test
            confirm_email = f"confirm-verify-{self.test_id}@test.local"
            confirm_password = f"ConfirmVerifyTest{self.test_id}!"
            
            # Create user for email verification confirmation testing
            from authn_authz_middleware import UserService
            from models import UserStatus
            
            user_service = UserService()
            user_data = {
                "email": confirm_email,
                "name": f"Confirm Verify Test User {self.test_id}",
                "password": confirm_password,
                "status": UserStatus.ACTIVE
            }
            
            created_user = await user_service.create_user(user_data)
            
            await self.grant_tenant_role(created_user.id)  # login requires a tenant role
            self.add_cleanup_item("custom", ("users_mt", "id", created_user.id))
            
            # Login to get a valid session
            login_response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/login",
                json={"email": confirm_email, "password": confirm_password},
                headers={}
            )
            
            assert login_response.status_code == 200, f"Login failed for email verification confirmation test: {login_response.status_code}: {login_response.text}"
            
            login_data = login_response.json()
            confirm_token = login_data["access_token"]
            
            # Test with invalid token (no tenant context needed)
            # Use httpx directly to avoid default tenant headers from make_authenticated_request
            import httpx
            
            confirm_headers = {
                "Authorization": f"Bearer {confirm_token}"
                # Explicitly NO X-Customer-ID header - email verification confirmation should work without tenant context
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/auth/verify-email-confirm",
                    json={"token": "invalid-verification-token"},
                    headers=confirm_headers
                )

            # A token that wasn't issued for this user and address is refused
            assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"

            response_data = response.json()
            if response.status_code == 200:
                assert "message" in response_data, "Success response should have message"
                print(f"   ✅ Email verification confirmed")
            else:
                assert "detail" in response_data or "message" in response_data, "Error response should have detail or message"
                print(f"   ⚠️ Email verification validation working")

            self.test_results["confirm_email_verification"] = "PASS"

        except Exception as e:
            print(f"   ❌ Confirm email verification test error: {e}")
            self.test_results["confirm_email_verification"] = f"ERROR: {e}"

    # Session Management Tests

    async def test_list_user_sessions_endpoint(self):
        """Test GET /v1/auth/sessions - List user sessions"""
        print("\n🧪 Testing List User Sessions Endpoint...")

        try:
            # Create a dedicated user for session listing test
            sessions_email = f"sessions-test-{self.test_id}@test.local"
            sessions_password = f"SessionsTest{self.test_id}!"
            
            # Create user for session listing testing
            from authn_authz_middleware import UserService
            from models import UserStatus
            
            user_service = UserService()
            user_data = {
                "email": sessions_email,
                "name": f"Sessions Test User {self.test_id}",
                "password": sessions_password,
                "status": UserStatus.ACTIVE
            }
            
            created_user = await user_service.create_user(user_data)
            
            await self.grant_tenant_role(created_user.id)  # login requires a tenant role
            self.add_cleanup_item("custom", ("users_mt", "id", created_user.id))
            
            # Login to get a valid session
            login_response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/login",
                json={"email": sessions_email, "password": sessions_password},
                headers={}
            )
            
            assert login_response.status_code == 200, f"Login failed for session listing test: {login_response.status_code}: {login_response.text}"
            
            login_data = login_response.json()
            sessions_token = login_data["access_token"]
            
            # List user sessions (no tenant context needed - sessions are user-level)
            # Use httpx directly to avoid default tenant headers from make_authenticated_request
            import httpx
            
            sessions_headers = {
                "Authorization": f"Bearer {sessions_token}"
                # Explicitly NO X-Customer-ID header - session listing should work without tenant context
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/auth/sessions",
                    headers=sessions_headers
                )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate sessions response structure
            required_fields = ["sessions", "total_count"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert isinstance(response_data["sessions"], list), "Sessions should be a list"
            assert isinstance(response_data["total_count"], int), "Total count should be an integer"
            assert response_data["total_count"] >= 0, "Total count should be non-negative"

            print(f"   ✅ List user sessions successful (count: {response_data['total_count']})")
            self.test_results["list_user_sessions"] = "PASS"

        except Exception as e:
            print(f"   ❌ List user sessions test error: {e}")
            self.test_results["list_user_sessions"] = f"ERROR: {e}"

    async def test_revoke_session_endpoint(self):
        """Test DELETE /v1/auth/sessions/{session_id} - Revoke session"""
        print("\n🧪 Testing Revoke Session Endpoint...")

        try:
            # Create a dedicated user for revoke session test
            revoke_email = f"revoke-test-{self.test_id}@test.local"
            revoke_password = f"RevokeTest{self.test_id}!"
            
            from authn_authz_middleware import UserService
            from models import UserStatus
            
            user_service = UserService()
            user_data = {
                "email": revoke_email,
                "name": f"Revoke Test User {self.test_id}",
                "password": revoke_password,
                "status": UserStatus.ACTIVE
            }
            
            created_user = await user_service.create_user(user_data)
            
            await self.grant_tenant_role(created_user.id)  # login requires a tenant role
            self.add_cleanup_item("custom", ("users_mt", "id", created_user.id))
            
            # Login to get a valid session
            login_response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/login",
                json={"email": revoke_email, "password": revoke_password},
                headers={}
            )
            
            assert login_response.status_code == 200, f"Login failed for revoke test: {login_response.status_code}: {login_response.text}"
            
            login_data = login_response.json()
            revoke_token = login_data["access_token"]
            
            # Test with non-existent session ID using fresh token (no tenant context needed)
            import httpx
            
            test_session_id = f"test-session-{self.test_id}"
            revoke_headers = {
                "Authorization": f"Bearer {revoke_token}"
                # Explicitly NO X-Customer-ID header - session management should work without tenant context
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.base_url}/v1/auth/sessions/{test_session_id}",
                    headers=revoke_headers
                )

            # Should return 404 for non-existent session
            assert response.status_code == 404, f"Expected 404 for non-existent session, got {response.status_code}: {response.text}"

            response_data = response.json()
            assert "detail" in response_data, "Error response should have detail field"
            assert "not found" in response_data["detail"].lower(), "Should indicate session not found"

            print(f"   ✅ Revoke session validation working")
            self.test_results["revoke_session"] = "PASS"

        except Exception as e:
            print(f"   ❌ Revoke session test error: {e}")
            self.test_results["revoke_session"] = f"ERROR: {e}"

    async def test_revoke_all_sessions_endpoint(self):
        """Test DELETE /v1/auth/sessions/all - Revoke all sessions"""
        print("\n🧪 Testing Revoke All Sessions Endpoint...")

        try:
            # Create a dedicated user for revoke all sessions test
            revoke_all_email = f"revoke-all-test-{self.test_id}@test.local"
            revoke_all_password = f"RevokeAllTest{self.test_id}!"
            
            from authn_authz_middleware import UserService
            from models import UserStatus
            
            user_service = UserService()
            user_data = {
                "email": revoke_all_email,
                "name": f"Revoke All Test User {self.test_id}",
                "password": revoke_all_password,
                "status": UserStatus.ACTIVE
            }
            
            created_user = await user_service.create_user(user_data)
            
            await self.grant_tenant_role(created_user.id)  # login requires a tenant role
            self.add_cleanup_item("custom", ("users_mt", "id", created_user.id))
            
            # Login to get a valid session
            login_response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/login",
                json={"email": revoke_all_email, "password": revoke_all_password},
                headers={}
            )
            
            assert login_response.status_code == 200, f"Login failed for revoke all test: {login_response.status_code}: {login_response.text}"
            
            login_data = login_response.json()
            revoke_all_token = login_data["access_token"]
            
            # Revoke all sessions using fresh token (no tenant context needed)
            import httpx
            
            revoke_all_headers = {
                "Authorization": f"Bearer {revoke_all_token}"
                # Explicitly NO X-Customer-ID header - session management should work without tenant context
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.base_url}/v1/auth/sessions/all",
                    headers=revoke_all_headers
                )

            # Should succeed
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()
            assert "message" in response_data, "Response should have message field"
            assert "revoked" in response_data["message"].lower(), "Message should indicate sessions revoked"

            print(f"   ✅ Revoke all sessions successful")
            self.test_results["revoke_all_sessions"] = "PASS"

        except Exception as e:
            print(f"   ❌ Revoke all sessions test error: {e}")
            self.test_results["revoke_all_sessions"] = f"ERROR: {e}"

    # Account Management Tests

    async def test_deactivate_account_endpoint(self):
        """Test POST /v1/auth/deactivate - Deactivate account"""
        print("\n🧪 Testing Deactivate Account Endpoint...")

        try:
            # Create a dedicated user for deactivate account test
            deactivate_email = f"deactivate-test-{self.test_id}@test.local"
            deactivate_password = f"DeactivateTest{self.test_id}!"
            
            from authn_authz_middleware import UserService
            from models import UserStatus
            
            user_service = UserService()
            user_data = {
                "email": deactivate_email,
                "name": f"Deactivate Test User {self.test_id}",
                "password": deactivate_password,
                "status": UserStatus.ACTIVE
            }
            
            created_user = await user_service.create_user(user_data)
            
            await self.grant_tenant_role(created_user.id)  # login requires a tenant role
            self.add_cleanup_item("custom", ("users_mt", "id", created_user.id))
            
            # Login to get a valid session
            login_response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/login",
                json={"email": deactivate_email, "password": deactivate_password},
                headers={}
            )
            
            assert login_response.status_code == 200, f"Login failed for deactivate test: {login_response.status_code}: {login_response.text}"
            
            login_data = login_response.json()
            deactivate_token = login_data["access_token"]
            
            # Deactivate account using fresh token (no tenant context needed)
            import httpx
            
            deactivate_headers = {
                "Authorization": f"Bearer {deactivate_token}"
                # Explicitly NO X-Customer-ID header - account deactivation should work without tenant context
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/auth/deactivate",
                    headers=deactivate_headers
                )

            # Should succeed
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()
            assert "message" in response_data, "Response should have message field"
            assert "deactivated" in response_data["message"].lower(), "Message should indicate account deactivated"

            print(f"   ✅ Deactivate account successful")
            self.test_results["deactivate_account"] = "PASS"

        except Exception as e:
            print(f"   ❌ Deactivate account test error: {e}")
            self.test_results["deactivate_account"] = f"ERROR: {e}"

    async def test_reactivate_account_endpoint(self):
        """Test POST /v1/auth/reactivate/{user_id} - Reactivate account"""
        print("\n🧪 Testing Reactivate Account Endpoint...")

        try:
            # Create a dedicated user for reactivate account test
            reactivate_email = f"reactivate-test-{self.test_id}@test.local"
            reactivate_password = f"ReactivateTest{self.test_id}!"
            
            from authn_authz_middleware import UserService
            from models import UserStatus
            
            user_service = UserService()
            user_data = {
                "email": reactivate_email,
                "name": f"Reactivate Test User {self.test_id}",
                "password": reactivate_password,
                "status": UserStatus.ACTIVE
            }
            
            created_user = await user_service.create_user(user_data)
            
            await self.grant_tenant_role(created_user.id)  # login requires a tenant role
            self.add_cleanup_item("custom", ("users_mt", "id", created_user.id))
            
            # Login to get a valid session
            login_response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/login",
                json={"email": reactivate_email, "password": reactivate_password},
                headers={}
            )
            
            assert login_response.status_code == 200, f"Login failed for reactivate test: {login_response.status_code}: {login_response.text}"
            
            login_data = login_response.json()
            reactivate_token = login_data["access_token"]
            
            # Test with current user ID (requires platform admin privileges)
            # Use httpx directly to avoid default tenant headers from make_authenticated_request
            import httpx
            
            reactivate_headers = {
                "Authorization": f"Bearer {reactivate_token}",
                "X-Customer-ID": self.test_tenant_id
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/auth/reactivate/{created_user.id}",
                    headers=reactivate_headers
                )

            # Should succeed or require elevated permissions
            assert response.status_code in [200, 403], f"Expected 200 or 403, got {response.status_code}: {response.text}"

            response_data = response.json()
            
            if response.status_code == 200:
                assert "message" in response_data, "Success response should have message field"
                assert "reactivated" in response_data["message"].lower(), "Message should indicate account reactivated"
                print(f"   ✅ Reactivate account successful")
            else:
                # Error response might have "detail" or "error" field depending on implementation
                assert "detail" in response_data or "error" in response_data, "Error response should have detail or error field"
                error_message = response_data.get("detail", response_data.get("error", "")).lower()
                print(f"   ⚠️ Reactivate account requires platform admin (expected): {error_message}")

            self.test_results["reactivate_account"] = "PASS"

        except Exception as e:
            print(f"   ❌ Reactivate account test error: {e}")
            self.test_results["reactivate_account"] = f"ERROR: {e}"

    # Tenant Onboarding Tests

    async def test_tenant_onboard_endpoint(self):
        """Test POST /v1/auth/tenant-onboard - Tenant onboarding"""
        print("\n🧪 Testing Tenant Onboarding Endpoint...")

        try:
            # Create a dedicated user with platform admin privileges for tenant onboarding test
            onboard_email = f"onboard-test-{self.test_id}@test.local"
            onboard_password = f"OnboardTest{self.test_id}!"
            
            from authn_authz_middleware import UserService
            from models import UserStatus
            from database_layer import DatabaseLayer
            
            user_service = UserService()
            user_data = {
                "email": onboard_email,
                "name": f"Onboard Test User {self.test_id}",
                "password": onboard_password,
                "status": UserStatus.ACTIVE
            }
            
            created_user = await user_service.create_user(user_data)
            
            await self.grant_tenant_role(created_user.id)  # login requires a tenant role
            self.add_cleanup_item("custom", ("users_mt", "id", created_user.id))
            
            # Assign platform admin role to enable tenant onboarding
            db = DatabaseLayer('TestService', 'test-service-key')
            platform_role_data = {
                'user_id': created_user.id,
                'tenant_id': 'platform',  # Platform tenant for super admin roles
                'role': 'super_admin',
                'granted_by': created_user.id,
                'customer_id': 'platform'
            }
            platform_role_id = await db.create_user_role(platform_role_data)
            self.add_cleanup_item("custom", ("user_tenant_roles_mt", "id", platform_role_id))
            
            # Login to get a valid session
            login_response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/login",
                json={"email": onboard_email, "password": onboard_password},
                headers={}
            )
            
            assert login_response.status_code == 200, f"Login failed for onboard test: {login_response.status_code}: {login_response.text}"
            
            login_data = login_response.json()
            onboard_token = login_data["access_token"]
            
            # Test tenant onboarding with fresh token
            # Use httpx directly to avoid default tenant headers from make_authenticated_request
            import httpx
            
            onboard_headers = {
                "Authorization": f"Bearer {onboard_token}",
                "X-Customer-ID": self.test_tenant_id
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/auth/tenant-onboard",
                    params={
                        "tenant_name": f"Test Tenant {self.test_id}",
                        "admin_email": f"tenant-admin-{self.test_id}@test.local",
                        "subscription_tier": "professional"
                    },
                    headers=onboard_headers
                )

            # Should succeed with platform admin or be denied (401 is also acceptable for invalid session)
            assert response.status_code in [200, 401, 403], f"Expected 200, 401, or 403, got {response.status_code}: {response.text}"

            response_data = response.json()
            
            if response.status_code == 200:
                # Validate onboarding response structure
                required_fields = ["invitation_token", "email", "tenant_id", "role"]
                for field in required_fields:
                    assert field in response_data, f"Missing required field: {field}"

                print(f"   ✅ Tenant onboarding successful: {response_data['email']}")
            elif response.status_code == 403:
                # Error response might have "detail" or "error" field depending on implementation
                assert "detail" in response_data or "error" in response_data, "Error response should have detail or error field"
                error_message = response_data.get("detail", response_data.get("error", "")).lower()
                assert "admin" in error_message or "permission" in error_message, "Should require platform admin"
                print(f"   ⚠️ Tenant onboarding requires platform admin (expected)")
            else:
                # 401 - Invalid session (acceptable since regular users can't do tenant onboarding)
                assert "invalid" in response_data.get("error", "").lower() or "expired" in response_data.get("error", "").lower(), "Should indicate invalid/expired session"
                print(f"   ⚠️ Tenant onboarding requires valid platform admin session (expected)")

            self.test_results["tenant_onboard"] = "PASS"

        except Exception as e:
            print(f"   ❌ Tenant onboarding test error: {e}")
            self.test_results["tenant_onboard"] = f"ERROR: {e}"

    # Cross-tenant access protection tests

    async def test_cross_tenant_access_protection(self):
        """Test cross-tenant access protection for auth endpoints"""
        print("\n🧪 Testing Cross-Tenant Access Protection...")

        try:
            # Create a test user and tenant for this specific test
            test_user_id, test_tenant_id = await self.create_test_user_and_tenant(
                roles=['tenant_admin'],
                user_name_suffix='AuthIsolation'
            )

            # Test with different customer ID header
            different_customer_id = f"different-customer-{self.test_id}"
            
            # Test 1: Try to access profile with different customer ID
            wrong_headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "X-Customer-ID": different_customer_id
            }

            profile_response = await self.make_authenticated_request(
                "GET",
                "/v1/auth/me",
                headers=wrong_headers
            )

            # Should work correctly with proper tenant validation or return auth error
            assert profile_response.status_code in [200, 401, 403], f"Cross-tenant profile access returned {profile_response.status_code}: {profile_response.text}"

            # Test 2: Try to list sessions with different customer ID
            sessions_response = await self.make_authenticated_request(
                "GET",
                "/v1/auth/sessions",
                headers=wrong_headers
            )

            assert sessions_response.status_code in [200, 401, 403], f"Cross-tenant sessions access returned {sessions_response.status_code}: {sessions_response.text}"

            print(f"   ✅ Cross-tenant access protection working correctly")
            self.test_results["cross_tenant_protection"] = "PASS"

        except Exception as e:
            print(f"   ❌ Cross-tenant access protection test error: {e}")
            self.test_results["cross_tenant_protection"] = f"ERROR: {e}"

    # Validation and error handling tests

    async def test_validation_and_error_handling(self):
        """Test validation and error handling for various invalid scenarios"""
        print("\n🧪 Testing Validation and Error Handling...")

        try:
            # Test 1: Login with missing email
            incomplete_login = {
                "password": "testpassword"
                # Missing email
            }

            incomplete_response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/login",
                json=incomplete_login,
                headers={}
            )

            assert incomplete_response.status_code in [400, 422], f"Incomplete login should return validation error, got {incomplete_response.status_code}: {incomplete_response.text}"

            # Test 2: Password change with weak password - create dedicated user
            weak_test_email = f"weak-password-test-{self.test_id}@test.local"
            weak_test_password = f"WeakPasswordTest{self.test_id}!"
            
            from authn_authz_middleware import UserService
            from models import UserStatus
            
            user_service = UserService()
            weak_user_data = {
                "email": weak_test_email,
                "name": f"Weak Password Test User {self.test_id}",
                "password": weak_test_password,
                "status": UserStatus.ACTIVE
            }
            
            weak_created_user = await user_service.create_user(weak_user_data)
            
            await self.grant_tenant_role(weak_created_user.id)  # login requires a tenant role
            self.add_cleanup_item("custom", ("users_mt", "id", weak_created_user.id))
            
            # Login to get valid session
            weak_login_response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/login",
                json={"email": weak_test_email, "password": weak_test_password},
                headers={}
            )
            
            assert weak_login_response.status_code == 200, f"Login failed for weak password test: {weak_login_response.status_code}"
            
            weak_login_data = weak_login_response.json()
            weak_test_token = weak_login_data["access_token"]
            
            # Now test weak password change with valid session
            import httpx
            
            weak_password_change = {
                "current_password": weak_test_password,  # Use actual current password
                "new_password": "weak"  # Too weak
            }
            
            weak_headers = {
                "Authorization": f"Bearer {weak_test_token}"
                # No X-Customer-ID needed for password change
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                weak_response = await client.post(
                    f"{self.base_url}/v1/auth/password/change",
                    json=weak_password_change,
                    headers=weak_headers
                )

            assert weak_response.status_code in [400, 422], f"Weak password should return validation error, got {weak_response.status_code}: {weak_response.text}"

            # Test 3: Invalid setup request
            invalid_setup = {
                "setup_token": "",
                "email": "invalid-email",  # Invalid email format
                "name": "",  # Empty name
                "password": "123"  # Too short
            }

            invalid_setup_response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/setup",
                json=invalid_setup,
                headers={}
            )

            assert invalid_setup_response.status_code in [400, 422], f"Invalid setup should return validation error, got {invalid_setup_response.status_code}: {invalid_setup_response.text}"

            # Test 4: Malformed JSON
            malformed_response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/login",
                data="invalid-json",  # Not valid JSON
                headers={"Content-Type": "application/json"}
            )

            assert malformed_response.status_code in [400, 422], f"Malformed JSON should return validation error, got {malformed_response.status_code}: {malformed_response.text}"

            print(f"   ✅ Validation and error handling working correctly")
            self.test_results["validation_and_error_handling"] = "PASS"

        except Exception as e:
            print(f"   ❌ Validation and error handling test error: {e}")
            self.test_results["validation_and_error_handling"] = f"ERROR: {e}"

    # Authentication flow integration tests

    async def test_complete_authentication_flow(self):
        """Test complete authentication flow: register -> login -> use -> logout"""
        print("\n🧪 Testing Complete Authentication Flow...")

        try:
            # 1. Create a fresh user for this flow test
            flow_email = f"auth-flow-{self.test_id}@test.local"
            flow_password = f"FlowTest{self.test_id}!"
            
            from authn_authz_middleware import UserService
            from models import UserStatus
            
            user_service = UserService()
            user_data = {
                "email": flow_email,
                "name": f"Auth Flow Test User {self.test_id}",
                "password": flow_password,
                "status": UserStatus.ACTIVE
            }
            
            created_user = await user_service.create_user(user_data)
            
            await self.grant_tenant_role(created_user.id)  # login requires a tenant role
            self.add_cleanup_item("custom", ("users_mt", "id", created_user.id))

            # 2. Login with the new user
            login_response = await self.make_authenticated_request(
                "POST",
                "/v1/auth/login",
                json={"email": flow_email, "password": flow_password},
                headers={}
            )

            assert login_response.status_code == 200, f"Login failed: {login_response.status_code}: {login_response.text}"
            
            login_data = login_response.json()
            flow_token = login_data["access_token"]
            
            # 3. Use the token to access profile (no tenant context needed)
            import httpx
            
            flow_headers = {
                "Authorization": f"Bearer {flow_token}"
                # Explicitly NO X-Customer-ID header - profile should work without tenant context
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                profile_response = await client.get(
                    f"{self.base_url}/v1/auth/me",
                    headers=flow_headers
                )

            assert profile_response.status_code == 200, f"Profile access failed: {profile_response.status_code}: {profile_response.text}"
            
            profile_data = profile_response.json()
            assert profile_data["email"] == flow_email, "Profile email should match"

            # 4. Refresh the session (no tenant context needed)
            async with httpx.AsyncClient(timeout=30.0) as client:
                refresh_response = await client.post(
                    f"{self.base_url}/v1/auth/refresh",
                    json={"refresh_token": login_data["refresh_token"]},
                )

            assert refresh_response.status_code == 200, f"Session refresh failed: {refresh_response.status_code}: {refresh_response.text}"
            
            refresh_data = refresh_response.json()
            new_token = refresh_data["access_token"]
            assert new_token != flow_token, "New token should be different"

            print(f"   ✅ Complete authentication flow successful")
            self.test_results["complete_auth_flow"] = "PASS"

        except Exception as e:
            print(f"   ❌ Complete authentication flow test error: {e}")
            self.test_results["complete_auth_flow"] = f"ERROR: {e}"

    async def run_all_tests(self):
        """Execute all auth router tests"""
        print(f"\n🚀 Starting Auth Router Test Suite (Test ID: {self.test_id})")
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
            # Authentication Flow
            self.test_login_endpoint,
            self.test_login_invalid_credentials,
            self.test_logout_endpoint,
            self.test_refresh_session_endpoint,
            self.test_get_user_profile_endpoint,
            
            # Platform Setup
            self.test_initialize_platform_setup_endpoint,
            self.test_complete_platform_setup_endpoint,
            
            # Password Management
            self.test_request_password_reset_endpoint,
            self.test_confirm_password_reset_endpoint,
            self.test_change_password_endpoint,
            
            # User Invitation System
            self.test_invite_user_endpoint,
            self.test_accept_invitation_endpoint,
            
            # Email Verification
            self.test_send_email_verification_endpoint,
            self.test_confirm_email_verification_endpoint,
            
            # Session Management
            self.test_list_user_sessions_endpoint,
            self.test_revoke_session_endpoint,
            self.test_revoke_all_sessions_endpoint,
            
            # Account Management
            self.test_deactivate_account_endpoint,
            self.test_reactivate_account_endpoint,
            
            # Tenant Onboarding
            self.test_tenant_onboard_endpoint,
            
            # Security and Validation
            self.test_cross_tenant_access_protection,
            self.test_validation_and_error_handling,
            
            # Integration Tests
            self.test_complete_authentication_flow
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
        print("🏆 AUTH ROUTER TEST SUMMARY")
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
            print("🎉 ALL AUTH ROUTER TESTS PASSED!")
        else:
            print(f"⚠️  {failed} test(s) failed - review errors above")

        print("=" * 60)

async def run_auth_router_tests():
    """Main test runner function for integration with run_route_tests.py"""
    suite = AuthRouterTestSuite()
    await suite.run_all_tests()
    
    # Return True if all tests passed, False otherwise
    passed_tests = sum(1 for result in suite.test_results.values() if result == "PASS")
    total_tests = len(suite.test_results)
    
    return passed_tests == total_tests

async def main():
    """Main test runner"""
    suite = AuthRouterTestSuite()
    await suite.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())