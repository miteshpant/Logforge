"""
Comprehensive test suite for DatabaseLayer
Tests database operations, security, and performance
"""

import pytest
import asyncio
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, List, Optional

# Import the DatabaseLayer when implemented
# from database_layer import DatabaseLayer, DatabaseError, SecurityError

class TestDatabaseLayer:
    """Test suite for DatabaseLayer implementation"""
    
    @pytest.fixture
    async def mock_clickhouse_client(self):
        """Mock ClickHouse client for testing"""
        client = Mock()
        client.execute = AsyncMock()
        client.query = AsyncMock()
        return client
    
    @pytest.fixture
    async def db_layer(self, mock_clickhouse_client):
        """DatabaseLayer instance with mocked client"""
        with patch('database_layer.clickhouse_connect.get_client', return_value=mock_clickhouse_client):
            db = DatabaseLayer('TestService', 'test-service-key')
            yield db
    
    @pytest.fixture
    def sample_user_data(self):
        """Sample user data for testing"""
        return {
            'id': str(uuid.uuid4()),
            'email': 'test@logforge.com',
            'name': 'Test User',
            'password_hash': '$2b$12$hashedpassword',
            'status': 'active',
            'customer_id': 'test-tenant'
        }
    
    @pytest.fixture
    def sample_session_data(self, sample_user_data):
        """Sample session data for testing"""
        return {
            'id': str(uuid.uuid4()),
            'user_id': sample_user_data['id'],
            'session_token': 'jwt-token-here',
            'ip_address': '192.168.1.100',
            'user_agent': 'Mozilla/5.0',
            'expires_at': datetime.utcnow() + timedelta(hours=8),
            'status': 'active',
            'customer_id': 'test-tenant'
        }

class TestDatabaseLayerInitialization:
    """Test database layer initialization and configuration"""
    
    def test_initialization_with_valid_credentials(self):
        """Test successful initialization with valid service credentials"""
        with patch('database_layer.clickhouse_connect.get_client') as mock_client:
            db = DatabaseLayer('UserService', 'valid-key')
            assert db.service_name == 'UserService'
            assert db.client is not None
            mock_client.assert_called_once()
    
    def test_initialization_with_invalid_credentials(self):
        """Test initialization fails with invalid credentials"""
        with pytest.raises(SecurityError):
            DatabaseLayer('UnknownService', 'invalid-key')
    
    def test_initialization_creates_tables(self):
        """Test that initialization creates required tables"""
        with patch('database_layer.clickhouse_connect.get_client') as mock_client:
            mock_client.return_value.execute = Mock()
            
            db = DatabaseLayer('UserService', 'valid-key')
            
            # Verify table creation queries were executed
            expected_calls = [
                'CREATE TABLE IF NOT EXISTS users_mt',
                'CREATE TABLE IF NOT EXISTS user_sessions_mt', 
                'CREATE TABLE IF NOT EXISTS user_tenant_roles_mt'
            ]
            
            for expected in expected_calls:
                assert any(expected in str(call) for call in mock_client.return_value.execute.call_args_list)

class TestUserOperations:
    """Test user-related database operations"""
    
    @pytest.mark.asyncio
    async def test_create_user_success(self, db_layer, sample_user_data, mock_clickhouse_client):
        """Test successful user creation"""
        mock_clickhouse_client.execute.return_value = None
        
        user_id = await db_layer.create_user(sample_user_data)
        
        assert user_id == sample_user_data['id']
        mock_clickhouse_client.execute.assert_called_once()
        
        # Verify the INSERT query structure
        call_args = mock_clickhouse_client.execute.call_args[0]
        query = call_args[0]
        assert 'INSERT INTO users_mt' in query
        assert 'VALUES' in query
    
    @pytest.mark.asyncio
    async def test_get_user_by_email_exists(self, db_layer, sample_user_data, mock_clickhouse_client):
        """Test retrieving existing user by email"""
        mock_clickhouse_client.query.return_value.result_rows = [
            [sample_user_data['id'], sample_user_data['email'], sample_user_data['name'], 
             sample_user_data['password_hash'], 1, datetime.utcnow(), datetime.utcnow(), 
             None, None, None, None, None, None, sample_user_data['customer_id']]
        ]
        mock_clickhouse_client.query.return_value.column_names = [
            'id', 'email', 'name', 'password_hash', 'status', 'created_at', 'updated_at',
            'last_login_at', 'password_reset_token', 'password_reset_expires', 
            'email_verified_at', 'setup_token', 'setup_token_expires', 'customer_id'
        ]
        
        user = await db_layer.get_user_by_email(sample_user_data['email'])
        
        assert user is not None
        assert user['email'] == sample_user_data['email']
        assert user['id'] == sample_user_data['id']
        
        # Verify the SELECT query
        call_args = mock_clickhouse_client.query.call_args[0]
        query = call_args[0]
        assert 'SELECT * FROM users_mt' in query
        assert 'WHERE email = %(email)s' in query
    
    @pytest.mark.asyncio
    async def test_get_user_by_email_not_exists(self, db_layer, mock_clickhouse_client):
        """Test retrieving non-existent user returns None"""
        mock_clickhouse_client.query.return_value.result_rows = []
        
        user = await db_layer.get_user_by_email('nonexistent@example.com')
        
        assert user is None
    
    @pytest.mark.asyncio
    async def test_update_user_success(self, db_layer, sample_user_data, mock_clickhouse_client):
        """Test successful user update"""
        mock_clickhouse_client.execute.return_value = 1
        
        updates = {'name': 'Updated Name', 'last_login_at': datetime.utcnow()}
        result = await db_layer.update_user(sample_user_data['id'], updates)
        
        assert result is True
        mock_clickhouse_client.execute.assert_called_once()
        
        # Verify UPDATE query structure
        call_args = mock_clickhouse_client.execute.call_args[0]
        query = call_args[0]
        assert 'ALTER TABLE users_mt UPDATE' in query
        assert 'WHERE id = %(user_id)s' in query

class TestSessionOperations:
    """Test session-related database operations"""
    
    @pytest.mark.asyncio
    async def test_create_session_success(self, db_layer, sample_session_data, mock_clickhouse_client):
        """Test successful session creation"""
        mock_clickhouse_client.execute.return_value = None
        
        session_id = await db_layer.create_session(sample_session_data)
        
        assert session_id == sample_session_data['id']
        mock_clickhouse_client.execute.assert_called_once()
        
        # Verify INSERT query
        call_args = mock_clickhouse_client.execute.call_args[0]
        query = call_args[0]
        assert 'INSERT INTO user_sessions_mt' in query
    
    @pytest.mark.asyncio
    async def test_get_session_active(self, db_layer, sample_session_data, mock_clickhouse_client):
        """Test retrieving active session"""
        mock_clickhouse_client.query.return_value.result_rows = [
            [sample_session_data['id'], sample_session_data['user_id'], 
             sample_session_data['session_token'], sample_session_data['ip_address'],
             sample_session_data['user_agent'], datetime.utcnow(), datetime.utcnow(),
             sample_session_data['expires_at'], 1, sample_session_data['customer_id']]
        ]
        mock_clickhouse_client.query.return_value.column_names = [
            'id', 'user_id', 'session_token', 'ip_address', 'user_agent',
            'created_at', 'last_activity', 'expires_at', 'status', 'customer_id'
        ]
        
        session = await db_layer.get_session(sample_session_data['session_token'])
        
        assert session is not None
        assert session['session_token'] == sample_session_data['session_token']
        assert session['status'] == 1  # active
    
    @pytest.mark.asyncio
    async def test_update_session_activity_success(self, db_layer, sample_session_data, mock_clickhouse_client):
        """Test updating session last activity"""
        mock_clickhouse_client.execute.return_value = 1
        
        result = await db_layer.update_session_activity(sample_session_data['session_token'])
        
        assert result is True
        mock_clickhouse_client.execute.assert_called_once()
        
        # Verify UPDATE query
        call_args = mock_clickhouse_client.execute.call_args[0]
        query = call_args[0]
        assert 'ALTER TABLE user_sessions_mt UPDATE' in query
        assert 'last_activity = now()' in query
        assert 'WHERE session_token = %(session_token)s' in query
    
    @pytest.mark.asyncio
    async def test_revoke_session_success(self, db_layer, sample_session_data, mock_clickhouse_client):
        """Test revoking session"""
        mock_clickhouse_client.execute.return_value = 1
        
        result = await db_layer.revoke_session(sample_session_data['session_token'])
        
        assert result is True
        mock_clickhouse_client.execute.assert_called_once()
        
        # Verify UPDATE query sets status to revoked
        call_args = mock_clickhouse_client.execute.call_args[0]
        query = call_args[0]
        assert 'ALTER TABLE user_sessions_mt UPDATE' in query
        assert 'status = 3' in query  # revoked = 3

class TestRoleOperations:
    """Test role-related database operations"""
    
    @pytest.mark.asyncio
    async def test_get_user_tenant_roles(self, db_layer, sample_user_data, mock_clickhouse_client):
        """Test retrieving user roles for tenant"""
        mock_clickhouse_client.query.return_value.result_rows = [
            [str(uuid.uuid4()), sample_user_data['id'], 'test-tenant', 'tenant_admin',
             sample_user_data['id'], datetime.utcnow(), None, 1, 'test-tenant']
        ]
        mock_clickhouse_client.query.return_value.column_names = [
            'id', 'user_id', 'tenant_id', 'role', 'granted_by', 'granted_at',
            'expires_at', 'status', 'customer_id'
        ]
        
        roles = await db_layer.get_user_tenant_roles(sample_user_data['id'], 'test-tenant')
        
        assert len(roles) == 1
        assert roles[0]['role'] == 'tenant_admin'
        assert roles[0]['tenant_id'] == 'test-tenant'
    
    @pytest.mark.asyncio
    async def test_create_user_role_success(self, db_layer, sample_user_data, mock_clickhouse_client):
        """Test creating user role assignment"""
        mock_clickhouse_client.execute.return_value = None
        
        role_data = {
            'id': str(uuid.uuid4()),
            'user_id': sample_user_data['id'],
            'tenant_id': 'test-tenant',
            'role': 'security_analyst',
            'granted_by': sample_user_data['id'],
            'customer_id': 'test-tenant'
        }
        
        role_id = await db_layer.create_user_role(role_data)
        
        assert role_id == role_data['id']
        mock_clickhouse_client.execute.assert_called_once()

class TestSecurityFeatures:
    """Test security features and access control"""
    
    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self, db_layer, mock_clickhouse_client):
        """Test that SQL injection attempts are prevented"""
        malicious_email = "test@example.com'; DROP TABLE users_mt; --"
        
        mock_clickhouse_client.query.return_value.result_rows = []
        
        # Should not raise exception, parameters should be escaped
        user = await db_layer.get_user_by_email(malicious_email)
        
        # Verify parameterized query was used
        call_args = mock_clickhouse_client.query.call_args
        assert '%(email)s' in call_args[0][0]  # Parameterized placeholder
        assert malicious_email in call_args[1].values()  # Parameter value
    
    def test_unauthorized_service_access(self):
        """Test that unauthorized services cannot access database layer"""
        with pytest.raises(SecurityError):
            DatabaseLayer('UnauthorizedService', 'wrong-key')
    
    @pytest.mark.asyncio
    async def test_table_access_control(self, db_layer, mock_clickhouse_client):
        """Test that services can only access authorized tables"""
        # UserService should be able to access users_mt
        await db_layer.get_user_by_email('test@example.com')
        
        # Should work fine for authorized table
        assert mock_clickhouse_client.query.called
        
        # Test direct query with unauthorized table should fail
        with pytest.raises(SecurityError):
            await db_layer.execute_query('SELECT * FROM logs_raw_mt')

class TestPerformanceFeatures:
    """Test performance optimization features"""
    
    @pytest.mark.asyncio
    async def test_batch_insert_usage(self, db_layer, mock_clickhouse_client):
        """Test batch insert for usage tracking"""
        usage_records = [
            {
                'tenant_id': 'tenant1',
                'user_id': str(uuid.uuid4()),
                'endpoint': '/v1/ingest/logs',
                'method': 'POST',
                'status_code': 200,
                'processing_time_ms': 45,
                'request_timestamp': datetime.utcnow()
            }
            for _ in range(150)  # Test batching with > 100 records
        ]
        
        mock_clickhouse_client.execute.return_value = len(usage_records)
        
        result = await db_layer.batch_insert_usage(usage_records)
        
        assert result == len(usage_records)
        # Verify batch processing (should be called multiple times for chunks)
        assert mock_clickhouse_client.execute.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_connection_retry_logic(self, db_layer, mock_clickhouse_client):
        """Test retry logic for transient failures"""
        # Simulate connection failure then success
        mock_clickhouse_client.query.side_effect = [
            Exception("Connection failed"),  # First attempt
            Exception("Still failing"),      # Second attempt
            Mock(result_rows=[], column_names=[])  # Third attempt succeeds
        ]
        
        user = await db_layer.get_user_by_email('test@example.com')
        
        # Should eventually succeed after retries
        assert user is None
        assert mock_clickhouse_client.query.call_count == 3

class TestErrorHandling:
    """Test error handling and edge cases"""
    
    @pytest.mark.asyncio
    async def test_database_connection_error(self, db_layer, mock_clickhouse_client):
        """Test handling of database connection errors"""
        mock_clickhouse_client.query.side_effect = Exception("Database unavailable")
        
        with pytest.raises(DatabaseError):
            await db_layer.get_user_by_email('test@example.com')
    
    @pytest.mark.asyncio
    async def test_invalid_parameters(self, db_layer):
        """Test validation of invalid parameters"""
        with pytest.raises(ValueError):
            await db_layer.create_user({})  # Empty user data
        
        with pytest.raises(ValueError):
            await db_layer.get_user_by_email('')  # Empty email
    
    @pytest.mark.asyncio
    async def test_duplicate_user_creation(self, db_layer, sample_user_data, mock_clickhouse_client):
        """Test handling of duplicate user creation"""
        # Simulate unique constraint violation
        mock_clickhouse_client.execute.side_effect = Exception("Duplicate key error")
        
        with pytest.raises(DatabaseError):
            await db_layer.create_user(sample_user_data)

class TestUsageTracking:
    """Test usage tracking and analytics operations"""
    
    @pytest.mark.asyncio
    async def test_get_usage_stats(self, db_layer, mock_clickhouse_client):
        """Test retrieving usage statistics"""
        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()
        
        mock_clickhouse_client.query.return_value.result_rows = [
            ['tenant1', 1500, 250000, 45.5, 99.2]
        ]
        mock_clickhouse_client.query.return_value.column_names = [
            'tenant_id', 'total_requests', 'total_events', 'avg_processing_time', 'success_rate'
        ]
        
        stats = await db_layer.get_usage_stats('tenant1', start_date, end_date)
        
        assert stats['tenant_id'] == 'tenant1'
        assert stats['total_requests'] == 1500
        assert stats['total_events'] == 250000
        assert stats['avg_processing_time'] == 45.5
        assert stats['success_rate'] == 99.2

if __name__ == '__main__':
    pytest.main([__file__, '-v'])