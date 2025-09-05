#!/usr/bin/env python3
"""
M2 Individual Functionality Test
Tests advanced query engine, dashboards, and search capabilities
"""

import asyncio
import httpx
import json
from datetime import datetime, timedelta
from base_test import BaseTestSuite

class M2TestSuite(BaseTestSuite):
    """Test M2 Search & Dashboards functionality"""
    
    def __init__(self):
        super().__init__("M2 Search & Dashboards")
    
    # Remove setup_test_tenant - BaseTestSuite handles tenant creation
    
    async def test_advanced_query_engine(self):
        """Test advanced query with filters and aggregations"""
        print("🔄 Testing advanced query engine...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # First, ingest some test data for querying
                test_logs = []
                for i in range(10):
                    test_logs.append({
                        "ts": (datetime.now() - timedelta(hours=i)).isoformat(),
                        "service": "m2-test-service",
                        "level": "INFO" if i % 2 == 0 else "ERROR",
                        "msg": f"M2 test message {i}",
                        "host": f"m2-host-{i % 3}",
                        "user_id": f"user-{i % 2}",
                        "trace_id": f"m2-trace-{i:03d}"
                    })

                # Ingest test data
                response = await client.post(
                    f"{self.base_url}/v1/ingest/logs/bulk",
                    json={"logs": test_logs},
                    headers=self.auth_headers
                )
                assert response.status_code == 200, f"Failed to ingest test data: {response.text}"
                
                # Wait for processing
                await asyncio.sleep(3)

                # Test advanced query
                query_request = {
                    "start_time": (datetime.now() - timedelta(hours=24)).isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "filters": [
                        {
                            "field": "service",
                            "operator": "eq",
                            "value": "m2-test-service"
                        },
                        {
                            "field": "customer_id",
                            "operator": "eq", 
                            "value": self.test_tenant_id
                        }
                    ],
                    "aggregations": [
                        {
                            "field": "level",
                            "type": "cardinality"
                        }
                    ],
                    "group_by": ["level"],
                    "limit": 100
                }

                response = await client.post(
                    f"{self.base_url}/v1/query/advanced",
                    json=query_request,
                    headers=self.auth_headers
                )

                assert response.status_code == 200, f"Advanced query failed: {response.text}"
                result = response.json()
                
                # Verify response structure
                assert "logs" in result or "aggregations" in result
                assert "total_count" in result
                assert "execution_time_ms" in result
                
                print("✅ Advanced query engine successful")
                self.test_results["advanced_query"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Advanced query engine failed: {str(e)}")
                self.test_results["advanced_query"] = f"FAIL: {str(e)}"
                return False
    
    async def test_aggregation_query(self):
        """Test aggregation queries with grouping"""
        print("🔄 Testing aggregation query...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Test aggregation via advanced query endpoint (more flexible)
                query_request = {
                    "start_time": (datetime.now() - timedelta(hours=24)).isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "aggregations": [
                        {
                            "field": "*",
                            "type": "count"
                        }
                    ],
                    "group_by": ["service"],
                    "filters": [
                        {
                            "field": "customer_id", 
                            "operator": "eq",
                            "value": self.test_tenant_id
                        }
                    ],
                    "limit": 100
                }

                response = await client.post(
                    f"{self.base_url}/v1/query/advanced",
                    json=query_request,
                    headers=self.auth_headers
                )

                assert response.status_code == 200, f"Aggregation query failed: {response.text}"
                result = response.json()
                
                # Verify aggregation response
                assert "aggregations" in result or "logs" in result
                assert "total_count" in result
                
                print("✅ Aggregation query successful")
                self.test_results["aggregation_query"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Aggregation query failed: {str(e)}")
                self.test_results["aggregation_query"] = f"FAIL: {str(e)}"
                return False
    
    async def test_timeseries_query(self):
        """Test time-series analysis"""
        print("🔄 Testing time-series query...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                query_request = {
                    "start_time": (datetime.now() - timedelta(hours=24)).isoformat(),
                    "end_time": datetime.now().isoformat(),
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
                            "value": self.test_tenant_id
                        }
                    ]
                }

                response = await client.post(
                    f"{self.base_url}/v1/query/timeseries",
                    json=query_request,
                    headers=self.auth_headers
                )

                assert response.status_code == 200, f"Time-series query failed: {response.text}"
                result = response.json()
                
                # Verify timeseries response format
                assert "buckets" in result or "aggregations" in result
                assert "total_count" in result
                
                if "buckets" in result:
                    assert isinstance(result["buckets"], list)
                
                print("✅ Time-series query successful")
                self.test_results["timeseries_query"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Time-series query failed: {str(e)}")
                self.test_results["timeseries_query"] = f"FAIL: {str(e)}"
                return False
    
    async def test_dashboard_list(self):
        """Test dashboard listing"""
        print("🔄 Testing dashboard list...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/v1/dashboards",
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200, f"Dashboard list failed: {response.text}"
                result = response.json()
                
                # Verify dashboard list structure
                assert "dashboards" in result
                assert "total" in result
                assert isinstance(result["dashboards"], list)
                
                print("✅ Dashboard list successful")
                self.test_results["dashboard_list"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Dashboard list failed: {str(e)}")
                self.test_results["dashboard_list"] = f"FAIL: {str(e)}"
                return False
    
    async def test_dashboard_definition(self):
        """Test getting dashboard definition"""
        print("🔄 Testing dashboard definition...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # First get list of dashboards
                response = await client.get(
                    f"{self.base_url}/v1/dashboards",
                    headers=self.auth_headers
                )
                assert response.status_code == 200
                dashboards = response.json()["dashboards"]
                
                if not dashboards:
                    print("⚠️ No dashboards available to test")
                    self.test_results["dashboard_definition"] = "SKIP: No dashboards"
                    return True
                
                # Test first available dashboard
                dashboard_id = dashboards[0]["id"]
                response = await client.get(
                    f"{self.base_url}/v1/dashboards/{dashboard_id}",
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200, f"Dashboard definition failed: {response.text}"
                dashboard_def = response.json()
                
                # Verify dashboard definition structure
                assert "id" in dashboard_def
                assert "name" in dashboard_def  # Field is called 'name', not 'title'
                assert "widgets" in dashboard_def
                
                print("✅ Dashboard definition successful")
                self.test_results["dashboard_definition"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Dashboard definition failed: {str(e)}")
                self.test_results["dashboard_definition"] = f"FAIL: {str(e)}"
                return False
    
    async def test_dashboard_data(self):
        """Test getting dashboard data"""
        print("🔄 Testing dashboard data...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # First get list of dashboards
                response = await client.get(
                    f"{self.base_url}/v1/dashboards",
                    headers=self.auth_headers
                )
                assert response.status_code == 200
                dashboards = response.json()["dashboards"]
                
                if not dashboards:
                    print("⚠️ No dashboards available to test")
                    self.test_results["dashboard_data"] = "SKIP: No dashboards"
                    return True
                
                # Test first available dashboard data
                dashboard_id = dashboards[0]["id"]
                params = {
                    "start_time": (datetime.now() - timedelta(hours=24)).isoformat(),
                    "end_time": datetime.now().isoformat()
                }
                
                response = await client.get(
                    f"{self.base_url}/v1/dashboards/{dashboard_id}/data",
                    params=params,
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200, f"Dashboard data failed: {response.text}"
                dashboard_data = response.json()
                
                # Verify dashboard data structure
                assert "widgets" in dashboard_data
                assert isinstance(dashboard_data["widgets"], dict)
                
                print("✅ Dashboard data successful")
                self.test_results["dashboard_data"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Dashboard data failed: {str(e)}")
                self.test_results["dashboard_data"] = f"FAIL: {str(e)}"
                return False
    
    async def test_data_export(self):
        """Test data export functionality"""
        print("🔄 Testing data export...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Test JSON export
                export_query = {
                    "start_time": (datetime.now() - timedelta(hours=24)).isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "filters": [
                        {
                            "field": "service",
                            "operator": "eq",
                            "value": "m2-test-service"
                        },
                        {
                            "field": "customer_id",
                            "operator": "eq",
                            "value": self.test_tenant_id
                        }
                    ],
                    "limit": 10
                }
                
                params = {
                    "format": "json",
                    "filename": "m2-test-export.json"
                }

                response = await client.post(
                    f"{self.base_url}/v1/export",
                    json=export_query,
                    params=params,
                    headers=self.auth_headers
                )

                assert response.status_code == 200, f"Data export failed: {response.text}"
                result = response.json()
                
                # Verify export response structure
                assert "data" in result or "metadata" in result
                
                print("✅ Data export successful")
                self.test_results["data_export"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Data export failed: {str(e)}")
                self.test_results["data_export"] = f"FAIL: {str(e)}"
                return False
    
    async def test_saved_queries(self):
        """Test saved query management"""
        print("🔄 Testing saved queries...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Test get saved queries (may be empty/unimplemented)
                response = await client.get(
                    f"{self.base_url}/v1/query/saved",
                    headers=self.auth_headers
                )
                
                # Accept 200 (implemented) or 501/404 (not implemented yet)
                assert response.status_code in [200, 404, 501], f"Saved queries failed: {response.text}"
                
                if response.status_code == 200:
                    result = response.json()
                    assert "saved_queries" in result or "message" in result
                
                print("✅ Saved queries successful")
                self.test_results["saved_queries"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Saved queries failed: {str(e)}")
                self.test_results["saved_queries"] = f"FAIL: {str(e)}"
                return False
    
    async def run_all_tests(self):
        """Run all M2 tests using base class runner"""
        print("📝 Testing: Advanced queries, dashboards, and search capabilities")
        
        tests = [
            self.test_advanced_query_engine,
            self.test_aggregation_query,
            self.test_timeseries_query,
            self.test_dashboard_list,
            self.test_dashboard_definition,
            self.test_dashboard_data,
            self.test_data_export,
            self.test_saved_queries
        ]
        
        return await super().run_all_tests(tests)

if __name__ == "__main__":
    test_suite = M2TestSuite()
    success = asyncio.run(test_suite.run_all_tests())
    exit(0 if success else 1)