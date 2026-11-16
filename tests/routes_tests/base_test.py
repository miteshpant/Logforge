#!/usr/bin/env python3
"""
Base Test Suite - Common functionality for all milestone tests
Provides isolated test environment setup and cleanup
"""

import asyncio
import httpx
import random
import sys
import os
from datetime import datetime
from typing import List, Dict, Any, Tuple

# Add API directory to path for database layer access
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'apps', 'api')))

class BaseTestSuite:
    """Base class for all milestone test suites with isolated test environment"""
    
    def __init__(self, milestone_name: str = "Base"):
        self.milestone_name = milestone_name
        self.base_url = "http://localhost:7080"
        self.test_results = {}
        self.auth_token = None
        self.auth_headers = {}
        
        # Generate unique test identifiers
        self.test_id = random.randint(10000, 99999)
        self.test_user_email = f"test-user-{self.test_id}@test.local"
        self.test_user_id = None
        self.test_tenant_id = f"test-tenant-{self.test_id}"
        self.test_cleanup_data = []
        # ENH-032: roles granted to the test user, as
        # [{'role': ..., 'tenant_id': ...}]. Used to mint a session token whose
        # tenant/role claims match what was actually granted.
        self.test_granted_roles = []
        
        # Set environment variables for database access
        os.environ['CLICKHOUSE_HOST'] = 'localhost'
        os.environ['CLICKHOUSE_PORT'] = '8124'
    
    async def create_test_user_and_tenant(self, 
                                         roles: List[str] = ['tenant_admin'],
                                         user_name_suffix: str = None) -> Tuple[str, str]:
        """
        Create isolated test user and tenant with specified roles
        
        Args:
            roles: List of roles to assign to the user (default: ['tenant_admin'])
            user_name_suffix: Optional suffix for user name (useful for specialized tests)
            
        Returns:
            Tuple of (user_id, tenant_id)
        """
        try:
            from database_layer import DatabaseLayer
            from authn_authz_middleware import hash_password
            
            # Initialize database layer with test service privileges
            db = DatabaseLayer('TestService', 'test-service-key')
            
            # 1. Create unique test user
            test_password = f"TestPass{self.test_id}!"
            user_name = f'Test User {self.test_id}'
            if user_name_suffix:
                user_name += f' {user_name_suffix}'
                
            user_data = {
                'email': self.test_user_email,
                'name': user_name,
                'password_hash': hash_password(test_password),
                'status': 1,  # active
                'customer_id': self.test_tenant_id
            }
            
            self.test_user_id = await db.create_user(user_data)
            self.test_cleanup_data.append(('user', self.test_user_id))
            print(f"   ✅ Created test user: {self.test_user_email} (ID: {self.test_user_id})")
            
            # 2. Create tenant role assignments
            for role in roles:
                # Platform admin roles need platform-level tenant_id
                if role in ['super_admin', 'admin', 'support_admin', 'billing_admin']:
                    tenant_id_for_role = 'platform'
                    customer_id_for_role = 'platform'
                else:
                    tenant_id_for_role = self.test_tenant_id
                    customer_id_for_role = self.test_tenant_id
                    
                role_data = {
                    'user_id': self.test_user_id,
                    'tenant_id': tenant_id_for_role,
                    'role': role,
                    'granted_by': self.test_user_id,
                    'customer_id': customer_id_for_role
                }
                role_id = await db.create_user_role(role_data)
                self.test_cleanup_data.append(('role', role_id))
                # ENH-032: remember the granted role and the tenant it applies
                # to, so create_test_session() can mint a token with matching
                # tenant/role claims instead of guessing.
                self.test_granted_roles.append(
                    {'role': role, 'tenant_id': tenant_id_for_role}
                )
                print(f"   ✅ Created role assignment: {role} for tenant: {tenant_id_for_role} (Role ID: {role_id})")
            
            return self.test_user_id, self.test_tenant_id
            
        except Exception as e:
            print(f"❌ Failed to create test user and tenant: {e}")
            raise
    
    async def grant_tenant_role(self, user_id: str, role: str = 'tenant_admin') -> str:
        """Grant `role` in this suite's test tenant to an ad-hoc test user.

        Login requires at least one tenant role assignment ("User has no tenant
        role assignments"), so a user created mid-test without one can never
        log in. The role row is registered for cleanup.
        """
        from database_layer import DatabaseLayer

        db = DatabaseLayer('TestService', 'test-service-key')
        role_id = await db.create_user_role({
            'user_id': user_id,
            'tenant_id': self.test_tenant_id,
            'role': role,
            'granted_by': self.test_user_id or user_id,
            'customer_id': self.test_tenant_id,
        })
        self.test_cleanup_data.append(('role', role_id))
        return role_id

    def _primary_granted_role(self) -> dict:
        """
        The role/tenant pair a session token should carry (ENH-032).

        Platform roles win when present, matching the middleware's own
        precedence: a platform admin's token must be scoped to 'platform', not
        to the throwaway test tenant.

        Raises if no roles were granted -- a session with no role would produce
        confusing downstream 403s rather than an obvious setup error.
        """
        if not self.test_granted_roles:
            raise RuntimeError(
                "No roles granted to the test user. Call "
                "create_test_user_and_tenant() before create_test_session()."
            )

        for granted in self.test_granted_roles:
            if granted['tenant_id'] == 'platform':
                return granted

        return self.test_granted_roles[0]

    async def create_test_session(self) -> str:
        """
        Create authenticated session for the test user
        
        Returns:
            JWT access token
        """
        try:
            from authn_authz_middleware import UserService
            from models import User, UserStatus
            
            # Get user data from database
            from database_layer import DatabaseLayer
            db = DatabaseLayer('TestService', 'test-service-key')
            user_data = await db.get_user_by_id(self.test_user_id)
            
            if not user_data:
                raise Exception(f"Test user not found: {self.test_user_id}")
            
            # Create User object for session creation
            user = User(
                id=user_data['id'],
                email=user_data['email'],
                name=user_data['name'],
                password_hash=user_data['password_hash'],
                status=UserStatus.ACTIVE
            )
            
            # Create session using UserService.
            #
            # ENH-032: this previously passed only three positional arguments
            # and raised
            #   TypeError: create_session() missing 1 required positional
            #   argument: 'tenant_id'
            # because the service signature gained `tenant_id` (and `user_role`)
            # while the helper was not updated. Keyword arguments are used so a
            # future signature change fails at the call site rather than
            # silently binding to the wrong parameter.
            primary = self._primary_granted_role()

            user_service = UserService()
            session_data = await user_service.create_session(
                user=user,
                ip_address='127.0.0.1',
                user_agent=f'{self.milestone_name}-test-client',
                tenant_id=primary['tenant_id'],
                user_role=primary['role'],
            )
            
            self.auth_token = session_data["access_token"]
            print(f"   ✅ Created session with token: {self.auth_token[:50]}...")
            
            return self.auth_token
            
        except Exception as e:
            print(f"❌ Failed to create test session: {e}")
            raise
    
    async def setup_auth(self, 
                        roles: List[str] = ['tenant_admin'], 
                        user_name_suffix: str = None,
                        custom_setup_callback: callable = None):
        """
        Setup complete isolated test authentication environment
        
        Args:
            roles: List of roles to assign to user
            user_name_suffix: Optional suffix for user name
            custom_setup_callback: Optional async callback for test-specific setup
        """
        try:
            print(f"🔧 Setting up {self.milestone_name} test isolation (ID: {self.test_id})...")
            
            # 1. Create test user and tenant
            await self.create_test_user_and_tenant(roles, user_name_suffix)
            
            # 2. Create session
            await self.create_test_session()
            
            # 3. Setup auth headers
            self.auth_headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "X-Customer-ID": self.test_tenant_id
            }
            
            print(f"   ✅ Using tenant ID: {self.test_tenant_id}")
            
            # 4. Run custom setup if provided
            if custom_setup_callback:
                await custom_setup_callback(self)
            
        except Exception as e:
            print(f"❌ {self.milestone_name} test setup failed: {e}")
            import traceback
            traceback.print_exc()
            # Set empty headers - tests will likely fail but we can see what happens
            self.auth_headers = {}
    
    async def cleanup_test_data(self):
        """Clean up all test data by deleting rows completely"""
        if not self.test_cleanup_data:
            return
            
        try:
            print(f"🧹 Cleaning up {self.milestone_name} test data...")
            
            from database_layer import DatabaseLayer
            db = DatabaseLayer('TestService', 'test-service-key')
            
            # Clean up in reverse order (roles first, then users)
            for data_type, data_id in reversed(self.test_cleanup_data):
                try:
                    if data_type == 'role':
                        # Delete role completely
                        query = "DELETE FROM user_tenant_roles_mt WHERE id = %(role_id)s"
                        await db.execute_query(query, {'role_id': data_id})
                        print(f"   ✅ Deleted role: {data_id}")
                        
                    elif data_type == 'user':
                        # Delete user sessions first
                        query = "DELETE FROM user_sessions_mt WHERE user_id = %(user_id)s"
                        await db.execute_query(query, {'user_id': data_id})
                        
                        # Delete user completely
                        query = "DELETE FROM users_mt WHERE id = %(user_id)s"
                        await db.execute_query(query, {'user_id': data_id})
                        print(f"   ✅ Deleted user: {data_id}")
                        
                    elif data_type == 'custom':
                        # For test-specific cleanup (alerts, rules, etc.)
                        # data_id should be a tuple: (table_name, id_field, id_value)
                        table_name, id_field, id_value = data_id
                        query = f"DELETE FROM {table_name} WHERE {id_field} = %({id_field})s"
                        await db.execute_query(query, {id_field: id_value})
                        print(f"   ✅ Deleted custom data from {table_name}: {id_value}")
                        
                except Exception as e:
                    print(f"   ⚠️  Failed to delete {data_type} {data_id}: {e}")
                    
            print(f"✅ {self.milestone_name} test cleanup completed")
            
        except Exception as e:
            print(f"❌ {self.milestone_name} test cleanup failed: {e}")
    
    def add_cleanup_item(self, data_type: str, data_id: Any):
        """Add item to cleanup list"""
        self.test_cleanup_data.append((data_type, data_id))
    
    async def make_authenticated_request(self, 
                                       method: str, 
                                       endpoint: str, 
                                       **kwargs) -> httpx.Response:
        """
        Make authenticated HTTP request with test headers
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (relative to base_url)
            **kwargs: Additional arguments for httpx request
            
        Returns:
            HTTP response
        """
        url = f"{self.base_url}{endpoint}"
        
        # Ensure auth headers are included, but allow custom headers to override
        headers = dict(self.auth_headers)  # Start with default auth headers
        headers.update(kwargs.get('headers', {}))  # Allow custom headers to override defaults
        kwargs['headers'] = headers
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method.upper() == 'GET':
                return await client.get(url, **kwargs)
            elif method.upper() == 'POST':
                return await client.post(url, **kwargs)
            elif method.upper() == 'PUT':
                return await client.put(url, **kwargs)
            elif method.upper() == 'DELETE':
                # For DELETE requests with JSON data, use the generic request method
                if 'json' in kwargs:
                    import json as json_module
                    content = json_module.dumps(kwargs.pop('json'))
                    if 'headers' not in kwargs:
                        kwargs['headers'] = {}
                    kwargs['headers']['Content-Type'] = 'application/json'
                    return await client.request('DELETE', url, content=content, **kwargs)
                else:
                    return await client.delete(url, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
    
    def print_test_summary(self):
        """Print test results summary"""
        print(f"\n📊 {self.milestone_name} Test Results Summary:")
        passed = sum(1 for result in self.test_results.values() if result == "PASS")
        total = len(self.test_results)
        
        for test_name, result in self.test_results.items():
            status = "✅" if result == "PASS" else "❌"
            print(f"  {status} {test_name}: {result}")
        
        print(f"\n🎯 {self.milestone_name} Results: {passed}/{total} tests passed")
        return passed, total
    
    async def setup_admin_auth(self):
        """Setup admin authentication for tests requiring elevated privileges"""
        # Create both platform admin and tenant admin roles for comprehensive access
        # This simulates a platform admin being granted temporary tenant access for debugging
        await self.setup_auth(roles=['super_admin', 'tenant_admin'], user_name_suffix='Admin')
    
    async def run_all_tests(self, tests: List[callable], setup_callback: callable = None, require_admin: bool = False):
        """
        Standard test runner for all milestone tests
        
        Args:
            tests: List of test method callables
            setup_callback: Optional async callback for milestone-specific setup
            require_admin: If True, setup super_admin role instead of tenant_admin
        """
        print(f"\n🚀 Starting {self.milestone_name} Individual Test Suite...")
        
        # Setup authentication with appropriate role
        if require_admin:
            await self.setup_admin_auth()
        else:
            await self.setup_auth(custom_setup_callback=setup_callback)
        
        # Run tests sequentially
        for test_func in tests:
            try:
                await test_func()
            except Exception as e:
                print(f"❌ Test {test_func.__name__} failed with exception: {str(e)}")
                test_name = test_func.__name__.replace("test_", "")
                if test_name not in self.test_results:
                    self.test_results[test_name] = f"FAIL: {str(e)}"
        
        # Print summary
        passed, total = self.print_test_summary()
        
        # Always clean up test data
        await self.cleanup_test_data()
        
        # Return success status
        if passed == total:
            print(f"✅ {self.milestone_name}: ALL TESTS PASSED")
            return True
        else:
            print(f"❌ {self.milestone_name}: SOME TESTS FAILED")
            return False