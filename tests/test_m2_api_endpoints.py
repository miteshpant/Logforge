"""
API Endpoint Tests for M2 Advanced Query Engine & Dashboard Framework
Tests all new API endpoints with realistic scenarios
"""

import pytest
import asyncio
import sys
import os
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import json
from unittest.mock import Mock, patch

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the FastAPI app
from main import app
from query_engine import AdvancedQueryRequest, QueryFilter, QueryAggregation, AggregationType, QueryOperator


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_query_engine():
    """Mock query engine for testing"""
    mock = Mock()
    mock.execute_query.return_value = {
        "logs": [],
        "aggregations": {"total_count": 1500, "avg_response_time": 250.5},
        "total_count": 1500,
        "execution_time_ms": 45.2,
        "has_more": False,
        "query_info": {"sql_query": "SELECT count() FROM logs_raw"}
    }
    return mock


@pytest.fixture
def mock_dashboard_engine():
    """Mock dashboard engine for testing"""
    mock = Mock()
    mock.get_dashboard_list.return_value = [
        {
            "id": "security",
            "name": "Security Operations Center",
            "type": "security",
            "description": "Real-time security monitoring",
            "widget_count": 5,
            "tags": ["security", "soc"]
        }
    ]
    mock.get_dashboard_definition.return_value = {
        "id": "security",
        "name": "Security Operations Center",
        "type": "security",
        "description": "Real-time security monitoring",
        "widgets": [
            {
                "id": "security_alerts_count",
                "title": "Security Alerts (24h)",
                "type": "metric"
            }
        ]
    }
    mock.get_dashboard_data.return_value = {
        "dashboard_id": "security",
        "generated_at": datetime.utcnow().isoformat(),
        "widgets": {
            "security_alerts_count": {
                "title": "Security Alerts (24h)",
                "type": "metric",
                "data": {"value": 25, "label": "alerts"},
                "last_updated": datetime.utcnow().isoformat()
            }
        },
        "metadata": {"total_widgets": 1}
    }
    return mock


class TestAdvancedQueryEndpoints:
    """Test advanced query API endpoints"""

    @patch('main.query_engine')
    def test_advanced_query_endpoint(self, mock_engine, client):
        """Test POST /v1/query/advanced"""
        mock_engine.execute_query.return_value = Mock(
            logs=[],
            aggregations={"total_count": 100},
            total_count=100,
            execution_time_ms=25.4,
            has_more=False,
            query_info={"sql_query": "SELECT * FROM logs_raw"}
        )

        query_data = {
            "start_time": "2023-12-01T00:00:00Z",
            "end_time": "2023-12-01T23:59:59Z",
            "filters": [],
            "aggregations": [
                {"type": "count", "field": "*"}
            ],
            "limit": 1000
        }

        response = client.post("/v1/query/advanced", json=query_data)

        assert response.status_code == 200
        data = response.json()
        assert "execution_time_ms" in data
        assert "total_count" in data

    @patch('main.query_engine')
    def test_aggregate_query_endpoint(self, mock_engine, client):
        """Test POST /v1/query/aggregate"""
        mock_engine.execute_query.return_value = Mock(
            logs=[],
            aggregations={"count_all": 500, "unique_users": 25},
            total_count=1,
            execution_time_ms=15.8,
            has_more=False,
            query_info={}
        )

        query_params = {
            "start_time": "2023-12-01T00:00:00Z",
            "end_time": "2023-12-01T23:59:59Z",
            "aggregations": [
                {"type": "count", "field": "*"},
                {"type": "unique", "field": "user_id"}
            ],
            "group_by": ["service"],
            "time_series": False
        }

        response = client.post("/v1/query/aggregate", json=query_params)

        assert response.status_code == 200
        data = response.json()
        assert "aggregations" in data

    @patch('main.query_engine')
    def test_timeseries_query_endpoint(self, mock_engine, client):
        """Test POST /v1/query/timeseries"""
        mock_engine.execute_query.return_value = Mock(
            logs=[],
            aggregations={
                "time_series": [
                    {"time": "2023-12-01T10:00:00Z", "count": 100},
                    {"time": "2023-12-01T11:00:00Z", "count": 150}
                ]
            },
            total_count=2,
            execution_time_ms=35.1,
            has_more=False,
            query_info={}
        )

        query_params = {
            "start_time": "2023-12-01T00:00:00Z",
            "end_time": "2023-12-01T23:59:59Z",
            "aggregations": [{"type": "count", "field": "*"}],
            "granularity": "hour"
        }

        response = client.post("/v1/query/timeseries", json=query_params)

        assert response.status_code == 200
        data = response.json()
        assert "aggregations" in data

    def test_query_engine_not_initialized(self, client):
        """Test error when query engine not initialized"""
        # Mock query_engine as None
        with patch('main.query_engine', None):
            query_data = {
                "start_time": "2023-12-01T00:00:00Z",
                "end_time": "2023-12-01T23:59:59Z"
            }

            response = client.post("/v1/query/advanced", json=query_data)
            assert response.status_code == 503
            assert "Query engine not initialized" in response.json()["detail"]

    @patch('main.query_engine')
    def test_query_error_handling(self, mock_engine, client):
        """Test query error handling"""
        mock_engine.execute_query.side_effect = Exception("Database connection failed")

        query_data = {
            "start_time": "2023-12-01T00:00:00Z",
            "end_time": "2023-12-01T23:59:59Z"
        }

        response = client.post("/v1/query/advanced", json=query_data)

        assert response.status_code == 500
        assert "Advanced query failed" in response.json()["detail"]


class TestSavedQueryEndpoints:
    """Test saved query management endpoints"""

    def test_get_saved_queries(self, client):
        """Test GET /v1/query/saved"""
        response = client.get("/v1/query/saved")

        assert response.status_code == 200
        data = response.json()
        assert "saved_queries" in data
        assert "message" in data

    def test_save_query(self, client):
        """Test POST /v1/query/saved"""
        saved_query_data = {
            "name": "Test Query",
            "description": "A test saved query",
            "query": {
                "start_time": "2023-12-01T00:00:00Z",
                "end_time": "2023-12-01T23:59:59Z",
                "filters": [
                    {"field": "level", "operator": "eq", "value": "error"}
                ]
            },
            "tags": ["test", "errors"]
        }

        response = client.post("/v1/query/saved", json=saved_query_data)

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "id" in data

    def test_get_saved_query_by_id(self, client):
        """Test GET /v1/query/saved/{query_id}"""
        response = client.get("/v1/query/saved/test-query-123")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["query_id"] == "test-query-123"


class TestDataExportEndpoints:
    """Test data export endpoints"""

    @patch('main.query_engine')
    def test_export_json_format(self, mock_engine, client):
        """Test POST /v1/export with JSON format"""
        mock_engine.execute_query.return_value = Mock(
            logs=[
                {"ts": "2023-12-01T10:00:00Z", "service": "web", "level": "info", "msg": "Request processed"},
                {"ts": "2023-12-01T10:01:00Z", "service": "api", "level": "error", "msg": "Database timeout"}
            ],
            aggregations={},
            total_count=2,
            execution_time_ms=12.5,
            has_more=False,
            query_info={}
        )

        export_request = {
            "query": {
                "start_time": "2023-12-01T00:00:00Z",
                "end_time": "2023-12-01T23:59:59Z"
            },
            "format": "json",
            "filename": "test_export.json"
        }

        response = client.post("/v1/export", json=export_request)

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "metadata" in data
        assert data["metadata"]["export_format"] == "json"
        assert data["metadata"]["filename"] == "test_export.json"

    @patch('main.query_engine')
    def test_export_csv_format_placeholder(self, mock_engine, client):
        """Test POST /v1/export with CSV format (placeholder)"""
        mock_engine.execute_query.return_value = Mock(logs=[], aggregations={})

        export_request = {
            "query": {
                "start_time": "2023-12-01T00:00:00Z",
                "end_time": "2023-12-01T23:59:59Z"
            },
            "format": "csv"
        }

        response = client.post("/v1/export", json=export_request)

        assert response.status_code == 200
        data = response.json()
        assert "CSV export coming in next update" in data["message"]

    def test_export_unsupported_format(self, client):
        """Test export with unsupported format"""
        with patch('main.query_engine') as mock_engine:
            mock_engine.execute_query.return_value = Mock(logs=[], aggregations={})

            export_request = {
                "query": {
                    "start_time": "2023-12-01T00:00:00Z",
                    "end_time": "2023-12-01T23:59:59Z"
                },
                "format": "xml"
            }

            response = client.post("/v1/export", json=export_request)

            assert response.status_code == 400
            assert "Unsupported export format" in response.json()["detail"]


class TestDashboardEndpoints:
    """Test enterprise dashboard endpoints"""

    @patch('main.dashboard_engine')
    def test_get_dashboards_list(self, mock_engine, client):
        """Test GET /v1/dashboards"""
        mock_engine.get_dashboard_list.return_value = [
            {
                "id": "security",
                "name": "Security Operations Center",
                "type": "security",
                "description": "Real-time security monitoring",
                "widget_count": 5,
                "tags": ["security", "soc"]
            },
            {
                "id": "performance",
                "name": "Performance Monitoring",
                "type": "performance",
                "description": "Application performance metrics",
                "widget_count": 6,
                "tags": ["performance", "apm"]
            }
        ]

        response = client.get("/v1/dashboards")

        assert response.status_code == 200
        data = response.json()
        assert "dashboards" in data
        assert "total" in data
        assert data["total"] == 2
        assert len(data["dashboards"]) == 2

        # Check dashboard structure
        dashboard = data["dashboards"][0]
        assert "id" in dashboard
        assert "name" in dashboard
        assert "type" in dashboard
        assert "widget_count" in dashboard

    @patch('main.dashboard_engine')
    def test_get_dashboard_definition(self, mock_engine, client):
        """Test GET /v1/dashboards/{dashboard_id}"""
        mock_dashboard = {
            "id": "security",
            "name": "Security Operations Center",
            "type": "security",
            "description": "Real-time security monitoring",
            "widgets": [
                {
                    "id": "security_alerts_count",
                    "title": "Security Alerts (24h)",
                    "type": "metric",
                    "position": {"x": 0, "y": 0, "w": 3, "h": 2}
                },
                {
                    "id": "failed_logins",
                    "title": "Failed Login Attempts",
                    "type": "line_chart",
                    "position": {"x": 3, "y": 0, "w": 9, "h": 4}
                }
            ]
        }
        mock_engine.get_dashboard_definition.return_value = mock_dashboard

        response = client.get("/v1/dashboards/security")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "security"
        assert "widgets" in data
        assert len(data["widgets"]) == 2

    @patch('main.dashboard_engine')
    def test_get_dashboard_data(self, mock_engine, client):
        """Test GET /v1/dashboards/{dashboard_id}/data"""
        mock_dashboard_data = {
            "dashboard_id": "security",
            "generated_at": datetime.utcnow().isoformat(),
            "widgets": {
                "security_alerts_count": {
                    "title": "Security Alerts (24h)",
                    "type": "metric",
                    "data": {"value": 25, "label": "alerts"},
                    "execution_time_ms": 15.2,
                    "last_updated": datetime.utcnow().isoformat()
                },
                "failed_logins": {
                    "title": "Failed Login Attempts",
                    "type": "line_chart",
                    "data": {
                        "series": [{
                            "name": "Failed Logins",
                            "data": [
                                {"x": "2023-12-01T10:00:00Z", "y": 5},
                                {"x": "2023-12-01T11:00:00Z", "y": 8}
                            ]
                        }]
                    },
                    "execution_time_ms": 22.8,
                    "last_updated": datetime.utcnow().isoformat()
                }
            },
            "metadata": {
                "time_range": {
                    "start_time": "2023-12-01T00:00:00Z",
                    "end_time": "2023-12-01T23:59:59Z"
                },
                "total_widgets": 2,
                "dashboard_name": "Security Operations Center"
            }
        }

        mock_engine.get_dashboard_data.return_value = mock_dashboard_data

        response = client.get("/v1/dashboards/security/data")

        assert response.status_code == 200
        data = response.json()
        assert data["dashboard_id"] == "security"
        assert "widgets" in data
        assert "metadata" in data
        assert len(data["widgets"]) == 2

    @patch('main.dashboard_engine')
    def test_get_dashboard_data_with_time_range(self, mock_engine, client):
        """Test GET /v1/dashboards/{dashboard_id}/data with custom time range"""
        mock_engine.get_dashboard_data.return_value = {"dashboard_id": "security", "widgets": {}}

        params = {
            "start_time": "2023-12-01T00:00:00Z",
            "end_time": "2023-12-01T12:00:00Z"
        }

        response = client.get("/v1/dashboards/security/data", params=params)

        assert response.status_code == 200

        # Verify that dashboard_engine.get_dashboard_data was called with time_range
        mock_engine.get_dashboard_data.assert_called_once()
        call_args = mock_engine.get_dashboard_data.call_args
        assert call_args[0][0] == "security"  # dashboard_id
        assert call_args[0][1] is not None   # time_range parameter

    @patch('main.dashboard_engine')
    def test_get_widget_data(self, mock_engine, client):
        """Test GET /v1/dashboards/{dashboard_id}/widgets/{widget_id}/data"""
        mock_dashboard_data = {
            "dashboard_id": "security",
            "widgets": {
                "security_alerts_count": {
                    "title": "Security Alerts (24h)",
                    "type": "metric",
                    "data": {"value": 25, "label": "alerts"},
                    "last_updated": datetime.utcnow().isoformat()
                }
            }
        }
        mock_engine.get_dashboard_data.return_value = mock_dashboard_data

        response = client.get("/v1/dashboards/security/widgets/security_alerts_count/data")

        assert response.status_code == 200
        data = response.json()
        assert data["dashboard_id"] == "security"
        assert data["widget_id"] == "security_alerts_count"
        assert "widget_data" in data
        assert data["widget_data"]["type"] == "metric"

    def test_get_nonexistent_dashboard(self, client):
        """Test GET /v1/dashboards/{dashboard_id} with nonexistent dashboard"""
        with patch('main.dashboard_engine') as mock_engine:
            mock_engine.get_dashboard_definition.return_value = None

            response = client.get("/v1/dashboards/nonexistent")

            assert response.status_code == 404
            assert "Dashboard nonexistent not found" in response.json()["detail"]

    @patch('main.dashboard_engine')
    def test_get_nonexistent_widget(self, mock_engine, client):
        """Test GET /v1/dashboards/{dashboard_id}/widgets/{widget_id}/data with nonexistent widget"""
        mock_dashboard_data = {
            "dashboard_id": "security",
            "widgets": {}  # No widgets
        }
        mock_engine.get_dashboard_data.return_value = mock_dashboard_data

        response = client.get("/v1/dashboards/security/widgets/nonexistent_widget/data")

        assert response.status_code == 404
        assert "Widget nonexistent_widget not found" in response.json()["detail"]

    def test_dashboard_engine_not_initialized(self, client):
        """Test dashboard endpoints when engine not initialized"""
        with patch('main.dashboard_engine', None):
            response = client.get("/v1/dashboards")
            assert response.status_code == 503
            assert "Dashboard engine not initialized" in response.json()["detail"]

    @patch('main.dashboard_engine')
    def test_create_custom_dashboard_placeholder(self, mock_engine, client):
        """Test POST /v1/dashboards (placeholder implementation)"""
        dashboard_data = {
            "id": "custom_dashboard",
            "name": "Custom Dashboard",
            "type": "custom",
            "description": "A custom dashboard",
            "widgets": []
        }

        response = client.post("/v1/dashboards", json=dashboard_data)

        assert response.status_code == 200
        data = response.json()
        assert "Custom dashboard creation coming in next update" in data["message"]

    @patch('main.dashboard_engine')
    def test_update_dashboard_placeholder(self, mock_engine, client):
        """Test PUT /v1/dashboards/{dashboard_id} (placeholder implementation)"""
        update_data = {"name": "Updated Dashboard Name"}

        response = client.put("/v1/dashboards/security", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert "Dashboard update coming in next update" in data["message"]

    @patch('main.dashboard_engine')
    def test_delete_dashboard_placeholder(self, mock_engine, client):
        """Test DELETE /v1/dashboards/{dashboard_id} (placeholder implementation)"""
        response = client.delete("/v1/dashboards/security")

        assert response.status_code == 200
        data = response.json()
        assert "Dashboard deletion coming in next update" in data["message"]


class TestErrorHandling:
    """Test error handling across all endpoints"""

    @patch('main.query_engine')
    def test_query_validation_error(self, mock_engine, client):
        """Test query validation errors"""
        # Missing required fields
        invalid_query = {
            "start_time": "2023-12-01T00:00:00Z"
            # Missing end_time
        }

        response = client.post("/v1/query/advanced", json=invalid_query)

        assert response.status_code == 422  # Validation error

    @patch('main.dashboard_engine')
    def test_dashboard_generation_error(self, mock_engine, client):
        """Test dashboard generation errors"""
        mock_engine.get_dashboard_data.side_effect = Exception("Query execution failed")

        response = client.get("/v1/dashboards/security/data")

        assert response.status_code == 500
        assert "Failed to get dashboard data" in response.json()["detail"]


class TestRealWorldScenarios:
    """Test realistic usage scenarios"""

    @patch('main.query_engine')
    @patch('main.dashboard_engine')
    def test_security_dashboard_workflow(self, mock_dashboard_engine, mock_query_engine, client):
        """Test complete security dashboard workflow"""
        # Step 1: List dashboards
        mock_dashboard_engine.get_dashboard_list.return_value = [
            {"id": "security", "name": "Security Operations Center", "type": "security"}
        ]

        response = client.get("/v1/dashboards")
        assert response.status_code == 200
        dashboards = response.json()["dashboards"]
        security_dashboard = next(d for d in dashboards if d["id"] == "security")

        # Step 2: Get security dashboard definition
        mock_dashboard_engine.get_dashboard_definition.return_value = {
            "id": "security",
            "name": "Security Operations Center",
            "widgets": [{"id": "security_alerts_count", "title": "Security Alerts"}]
        }

        response = client.get(f"/v1/dashboards/{security_dashboard['id']}")
        assert response.status_code == 200
        dashboard_def = response.json()

        # Step 3: Get real-time dashboard data
        mock_dashboard_data = {
            "dashboard_id": "security",
            "widgets": {
                "security_alerts_count": {
                    "title": "Security Alerts (24h)",
                    "data": {"value": 25, "label": "alerts"}
                }
            }
        }
        mock_dashboard_engine.get_dashboard_data.return_value = mock_dashboard_data

        response = client.get(f"/v1/dashboards/{security_dashboard['id']}/data")
        assert response.status_code == 200
        dashboard_data = response.json()

        assert dashboard_data["dashboard_id"] == "security"
        assert "security_alerts_count" in dashboard_data["widgets"]

    @patch('main.query_engine')
    def test_performance_analysis_workflow(self, mock_query_engine, client):
        """Test performance analysis using query endpoints"""
        # Mock query results
        mock_query_engine.execute_query.return_value = Mock(
            logs=[],
            aggregations={"avg_response_time": 245.6, "p95_response_time": 580.2, "total_requests": 15420},
            total_count=1,
            execution_time_ms=28.4,
            has_more=False,
            query_info={}
        )

        # Step 1: Get average response times by service
        aggregation_query = {
            "start_time": "2023-12-01T00:00:00Z",
            "end_time": "2023-12-01T23:59:59Z",
            "aggregations": [
                {"type": "avg", "field": "attrs.response_time"},
                {"type": "percentile", "field": "attrs.response_time", "percentile_value": 0.95},
                {"type": "count", "field": "*"}
            ],
            "group_by": ["service"],
            "filters": [
                {"field": "attrs.response_time", "operator": "gt", "value": 0}
            ]
        }

        response = client.post("/v1/query/aggregate", json=aggregation_query)
        assert response.status_code == 200

        # Step 2: Get response time trend over time
        timeseries_query = {
            "start_time": "2023-12-01T00:00:00Z",
            "end_time": "2023-12-01T23:59:59Z",
            "aggregations": [
                {"type": "avg", "field": "attrs.response_time"}
            ],
            "granularity": "hour"
        }

        response = client.post("/v1/query/timeseries", json=timeseries_query)
        assert response.status_code == 200

        # Step 3: Export results for further analysis
        export_query = {
            "query": {
                "start_time": "2023-12-01T00:00:00Z",
                "end_time": "2023-12-01T23:59:59Z",
                "aggregations": [{"type": "avg", "field": "attrs.response_time"}],
                "group_by": ["service"]
            },
            "format": "json",
            "filename": "performance_analysis.json"
        }

        response = client.post("/v1/export", json=export_query)
        assert response.status_code == 200


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([
        __file__,
        "-v",  # verbose output
        "-s",  # don't capture print statements
        "--tb=short"  # shorter traceback format
    ])
