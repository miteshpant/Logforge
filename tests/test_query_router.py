"""
Comprehensive tests for Query Router (Route 3)
Tests service/dao pattern implementation, database operations, and multi-tenant isolation
"""

import pytest
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from apps.api.services.query_service import QueryService
from apps.api.dao.query_dao import QueryDAO
from apps.api.routers.query import router as query_router, setup_dependencies
from apps.api.database_layer import DatabaseLayer

# Test fixtures and configuration
TEST_CUSTOMER_ID = f"test-customer-{uuid.uuid4().hex[:8]}"
TEST_CUSTOMER_ID_2 = f"test-customer-{uuid.uuid4().hex[:8]}"

class TestQueryDAO:
    """Test QueryDAO database operations"""
    
    @pytest.fixture
    async def query_dao(self):
        """Create QueryDAO instance for testing"""
        dao = QueryDAO()
        yield dao
        # Cleanup after tests
        await self._cleanup_test_data(dao)
    
    async def _cleanup_test_data(self, dao: QueryDAO):
        """Clean up test data from database"""
        try:
            # Clean up saved queries
            await dao.db.execute_query(
                "DELETE FROM saved_queries_mt WHERE customer_id IN (%s, %s)",
                (TEST_CUSTOMER_ID, TEST_CUSTOMER_ID_2)
            )
            # Clean up query cache
            await dao.db.execute_query(
                "DELETE FROM query_cache_mt WHERE customer_id IN (%s, %s)", 
                (TEST_CUSTOMER_ID, TEST_CUSTOMER_ID_2)
            )
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    @pytest.mark.asyncio
    async def test_save_and_retrieve_query(self, query_dao):
        """Test saving and retrieving a query"""
        query_data = {
            'customer_id': TEST_CUSTOMER_ID,
            'name': 'Test Query',
            'description': 'A test query for validation',
            'query_definition': {
                'filters': [{'field': 'level', 'operator': 'eq', 'value': 'ERROR'}],
                'limit': 100
            },
            'query_type': 'advanced',
            'created_by': 'test-user',
            'tags': ['test', 'error-logs'],
            'is_public': False
        }
        
        # Save query
        query_id = await query_dao.save_query(query_data)
        assert query_id is not None
        assert len(query_id) == 36  # UUID length
        
        # Retrieve query
        retrieved_query = await query_dao.get_saved_query(query_id, TEST_CUSTOMER_ID)
        assert retrieved_query is not None
        assert retrieved_query['name'] == 'Test Query'
        assert retrieved_query['customer_id'] == TEST_CUSTOMER_ID
        assert retrieved_query['query_definition'] == query_data['query_definition']
        assert retrieved_query['tags'] == ['test', 'error-logs']
    
    @pytest.mark.asyncio
    async def test_list_saved_queries(self, query_dao):
        """Test listing saved queries with filters"""
        # Save multiple queries
        query1_data = {
            'customer_id': TEST_CUSTOMER_ID,
            'name': 'Error Query',
            'query_definition': {'filters': []},
            'query_type': 'advanced',
            'created_by': 'user1'
        }
        query2_data = {
            'customer_id': TEST_CUSTOMER_ID,
            'name': 'Performance Query',
            'query_definition': {'filters': []},
            'query_type': 'timeseries',
            'created_by': 'user2'
        }
        
        query1_id = await query_dao.save_query(query1_data)
        query2_id = await query_dao.save_query(query2_data)
        
        # List all queries
        all_queries = await query_dao.list_saved_queries(TEST_CUSTOMER_ID)
        assert len(all_queries) >= 2
        
        # Filter by created_by
        user1_queries = await query_dao.list_saved_queries(TEST_CUSTOMER_ID, created_by='user1')
        assert len(user1_queries) >= 1
        assert any(q['name'] == 'Error Query' for q in user1_queries)
        
        # Filter by query_type
        advanced_queries = await query_dao.list_saved_queries(TEST_CUSTOMER_ID, query_type='advanced')
        assert len(advanced_queries) >= 1
        assert any(q['name'] == 'Error Query' for q in advanced_queries)
    
    @pytest.mark.asyncio
    async def test_update_saved_query(self, query_dao):
        """Test updating a saved query"""
        # Save initial query
        query_data = {
            'customer_id': TEST_CUSTOMER_ID,
            'name': 'Original Query',
            'description': 'Original description',
            'query_definition': {'filters': []},
            'tags': ['original']
        }
        query_id = await query_dao.save_query(query_data)
        
        # Update query
        update_data = {
            'name': 'Updated Query',
            'description': 'Updated description',
            'tags': ['updated', 'modified']
        }
        success = await query_dao.update_saved_query(query_id, TEST_CUSTOMER_ID, update_data)
        assert success is True
        
        # Verify update
        updated_query = await query_dao.get_saved_query(query_id, TEST_CUSTOMER_ID)
        assert updated_query['name'] == 'Updated Query'
        assert updated_query['description'] == 'Updated description'
        assert updated_query['tags'] == ['updated', 'modified']
    
    @pytest.mark.asyncio
    async def test_delete_saved_query(self, query_dao):
        """Test deleting (deactivating) a saved query"""
        # Save query
        query_data = {
            'customer_id': TEST_CUSTOMER_ID,
            'name': 'To Delete Query',
            'query_definition': {'filters': []}
        }
        query_id = await query_dao.save_query(query_data)
        
        # Delete query
        success = await query_dao.delete_saved_query(query_id, TEST_CUSTOMER_ID)
        assert success is True
        
        # Verify deletion (should not be retrievable)
        deleted_query = await query_dao.get_saved_query(query_id, TEST_CUSTOMER_ID)
        assert deleted_query is None
    
    @pytest.mark.asyncio
    async def test_query_caching(self, query_dao):
        """Test query result caching functionality"""
        cache_key = f"test-cache-{uuid.uuid4().hex[:8]}"
        query_data = {'filters': [{'field': 'level', 'operator': 'eq', 'value': 'INFO'}]}
        result_data = {'logs': [{'msg': 'test log'}], 'total_count': 1}
        
        # Cache result
        cache_id = await query_dao.cache_query_result(
            cache_key=cache_key,
            customer_id=TEST_CUSTOMER_ID,
            query_data=query_data,
            result=result_data,
            ttl_seconds=300
        )
        assert cache_id is not None
        assert len(cache_id) == 36
        
        # Retrieve cached result
        cached_result = await query_dao.get_cached_result(cache_key, TEST_CUSTOMER_ID)
        assert cached_result is not None
        assert cached_result['result_data'] == result_data
        
        # Test cache miss
        missing_result = await query_dao.get_cached_result('nonexistent-key', TEST_CUSTOMER_ID)
        assert missing_result is None
    
    @pytest.mark.asyncio
    async def test_multi_tenant_isolation(self, query_dao):
        """Test that queries are isolated between tenants"""
        # Save query for first customer
        query_data = {
            'customer_id': TEST_CUSTOMER_ID,
            'name': 'Customer 1 Query',
            'query_definition': {'filters': []}
        }
        query_id = await query_dao.save_query(query_data)
        
        # Try to retrieve with wrong customer ID
        wrong_customer_query = await query_dao.get_saved_query(query_id, TEST_CUSTOMER_ID_2)
        assert wrong_customer_query is None
        
        # List queries for wrong customer should be empty
        wrong_customer_queries = await query_dao.list_saved_queries(TEST_CUSTOMER_ID_2)
        assert len(wrong_customer_queries) == 0

class TestQueryService:
    """Test QueryService business logic"""
    
    @pytest.fixture
    async def query_service(self):
        """Create QueryService instance for testing"""
        service = QueryService()
        yield service
        # Cleanup after tests
        await self._cleanup_test_data(service)
    
    async def _cleanup_test_data(self, service: QueryService):
        """Clean up test data from database"""
        try:
            await service.query_dao.db.execute_query(
                "DELETE FROM saved_queries_mt WHERE customer_id IN (%s, %s)",
                (TEST_CUSTOMER_ID, TEST_CUSTOMER_ID_2)
            )
            await service.query_dao.db.execute_query(
                "DELETE FROM query_cache_mt WHERE customer_id IN (%s, %s)",
                (TEST_CUSTOMER_ID, TEST_CUSTOMER_ID_2)
            )
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    @pytest.mark.asyncio
    async def test_save_query_validation(self, query_service):
        """Test query saving with validation"""
        # Valid query
        valid_query = {
            'customer_id': TEST_CUSTOMER_ID,
            'name': 'Valid Query',
            'query_definition': {'filters': [{'field': 'level', 'operator': 'eq', 'value': 'ERROR'}]}
        }
        result = await query_service.save_query(valid_query)
        assert result['status'] == 'saved'
        assert 'query_id' in result
        
        # Invalid query - missing required fields
        invalid_query = {'name': 'Incomplete Query'}
        with pytest.raises(ValueError, match="Missing required field"):
            await query_service.save_query(invalid_query)
        
        # Invalid query - bad query definition
        bad_query = {
            'customer_id': TEST_CUSTOMER_ID,
            'name': 'Bad Query',
            'query_definition': 'not-a-dict'
        }
        with pytest.raises(ValueError, match="Query definition must be a dictionary"):
            await query_service.save_query(bad_query)
    
    @pytest.mark.asyncio
    async def test_query_structure_validation(self, query_service):
        """Test query structure validation"""
        # Valid query structure
        valid_query = {
            'filters': [
                {'field': 'level', 'operator': 'eq', 'value': 'ERROR'},
                {'field': 'service', 'operator': 'contains', 'value': 'api'}
            ],
            'aggregations': [{'field': 'service', 'type': 'count'}],
            'start_time': '2024-01-01T00:00:00Z',
            'end_time': '2024-01-02T00:00:00Z'
        }
        validation = await query_service.validate_query_structure(valid_query)
        assert validation['valid'] is True
        assert len(validation['errors']) == 0
        
        # Invalid filters
        invalid_query = {
            'filters': [
                {'field': 'level'},  # Missing operator and value
                'not-a-dict'  # Should be a dict
            ]
        }
        validation = await query_service.validate_query_structure(invalid_query)
        assert validation['valid'] is False
        assert len(validation['errors']) > 0
        
        # Invalid time range
        bad_time_query = {
            'start_time': '2024-01-02T00:00:00Z',
            'end_time': '2024-01-01T00:00:00Z'  # End before start
        }
        validation = await query_service.validate_query_structure(bad_time_query)
        assert validation['valid'] is False
        assert any('Start time must be before end time' in error for error in validation['errors'])
    
    @pytest.mark.asyncio
    async def test_cache_key_generation(self, query_service):
        """Test cache key generation consistency"""
        query_data = {'filters': [{'field': 'level', 'operator': 'eq', 'value': 'ERROR'}]}
        
        # Same query should generate same cache key
        key1 = query_service._generate_cache_key(query_data, TEST_CUSTOMER_ID)
        key2 = query_service._generate_cache_key(query_data, TEST_CUSTOMER_ID)
        assert key1 == key2
        
        # Different customer should generate different cache key
        key3 = query_service._generate_cache_key(query_data, TEST_CUSTOMER_ID_2)
        assert key1 != key3
        
        # Different query should generate different cache key
        different_query = {'filters': [{'field': 'service', 'operator': 'eq', 'value': 'api'}]}
        key4 = query_service._generate_cache_key(different_query, TEST_CUSTOMER_ID)
        assert key1 != key4
    
    @pytest.mark.asyncio
    async def test_service_error_handling(self, query_service):
        """Test service error handling"""
        # Test with invalid inputs
        with pytest.raises(ValueError):
            await query_service.get_saved_query("", TEST_CUSTOMER_ID)
        
        with pytest.raises(ValueError):
            await query_service.update_saved_query("invalid-id", TEST_CUSTOMER_ID, {})
        
        # Test update with no valid fields
        with pytest.raises(ValueError, match="No valid fields to update"):
            await query_service.update_saved_query("some-id", TEST_CUSTOMER_ID, {"invalid_field": "value"})

class TestQueryRouterIntegration:
    """Test query router endpoints with actual service integration"""
    
    @pytest.fixture
    async def client(self):
        """Create test client for query router"""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(query_router)
        
        # Mock query engine and clickhouse client
        class MockQueryEngine:
            async def execute_query(self, query):
                from apps.api.models import QueryResponse
                return QueryResponse(
                    logs=[{"level": "ERROR", "msg": "test error", "ts": "2024-01-01T00:00:00Z"}],
                    total_count=1,
                    execution_time_ms=100
                )
        
        class MockClickHouseClient:
            def query(self, sql):
                class MockResult:
                    result_rows = [("2024-01-01T00:00:00Z", "api", "ERROR", "test message", "host1", "trace123", TEST_CUSTOMER_ID)]
                return MockResult()
        
        setup_dependencies(MockQueryEngine(), MockClickHouseClient())
        
        return TestClient(app)
    
    def test_list_saved_queries_endpoint(self, client):
        """Test listing saved queries endpoint"""
        response = client.get(
            "/v1/query/saved",
            headers={"X-Customer-ID": TEST_CUSTOMER_ID}
        )
        assert response.status_code == 200
        data = response.json()
        assert "saved_queries" in data
        assert "customer_id" in data
        assert data["customer_id"] == TEST_CUSTOMER_ID
    
    def test_save_query_endpoint(self, client):
        """Test saving query endpoint"""
        query_data = {
            "name": "Test API Query",
            "description": "Query created via API",
            "query_definition": {
                "filters": [{"field": "level", "operator": "eq", "value": "ERROR"}]
            },
            "query_type": "advanced"
        }
        
        response = client.post(
            "/v1/query/saved",
            json=query_data,
            headers={"X-Customer-ID": TEST_CUSTOMER_ID}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "saved"
        assert "query_id" in data
    
    def test_validate_query_endpoint(self, client):
        """Test query validation endpoint"""
        query_data = {
            "filters": [{"field": "level", "operator": "eq", "value": "ERROR"}],
            "start_time": "2024-01-01T00:00:00Z",
            "end_time": "2024-01-02T00:00:00Z"
        }
        
        response = client.post(
            "/v1/query/validate",
            json=query_data,
            headers={"X-Customer-ID": TEST_CUSTOMER_ID}
        )
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data
        assert "errors" in data
        assert "warnings" in data

if __name__ == "__main__":
    # Run tests with proper async support
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])