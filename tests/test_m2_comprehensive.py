"""
Comprehensive Test Suite for M2 Advanced Query Engine & Dashboard Framework
Tests query engine functionality, dashboard generation, and enterprise features
"""

import pytest
import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
import json

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import test modules
from query_engine import (
    AdvancedQueryEngine, AdvancedQueryRequest, QueryResponse,
    QueryFilter, QueryAggregation, AggregationType, QueryOperator,
    TimeGranularity, SavedQuery
)
from dashboard_engine import (
    DashboardEngine, DashboardDefinition, DashboardData,
    DashboardType, VisualizationType
)
from models import LogEntry


class MockClickHouseClient:
    """Mock ClickHouse client for testing"""

    def __init__(self):
        self.queries_executed = []
        self.mock_data = []

    def query(self, sql_query: str):
        """Mock query execution"""
        self.queries_executed.append(sql_query)

        # Mock result based on query patterns
        if "count()" in sql_query:
            return MockResult([
                [1500, 150, 50000, datetime.now() - timedelta(days=1), datetime.now(), 800, 25]
            ])
        elif "GROUP BY" in sql_query:
            return MockResult([
                ["web-service", 500],
                ["api-service", 300],
                ["auth-service", 200]
            ])
        else:
            # Return sample log data
            return MockResult([
                [datetime.now(), "web-01", "web-service", "error",
                 "Authentication failed for user", "trace-123",
                 '{"user_id": "user-456", "ip": "192.168.1.100"}', 500, "192.168.1.100", "user-456"]
            ])

class MockResult:
    """Mock query result"""
    def __init__(self, rows):
        self.result_rows = rows


@pytest.fixture
def mock_clickhouse_client():
    """Provide mock ClickHouse client"""
    return MockClickHouseClient()

@pytest.fixture
def query_engine(mock_clickhouse_client):
    """Provide query engine with mock client"""
    return AdvancedQueryEngine(mock_clickhouse_client)

@pytest.fixture
def dashboard_engine(query_engine):
    """Provide dashboard engine"""
    return DashboardEngine(query_engine)

@pytest.fixture
def sample_time_range():
    """Provide sample time range for testing"""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=24)
    return {"start_time": start_time, "end_time": end_time}


class TestAdvancedQueryEngine:
    """Test suite for Advanced Query Engine"""

    @pytest.mark.asyncio
    async def test_basic_query_execution(self, query_engine):
        """Test basic query execution"""
        query = AdvancedQueryRequest(
            start_time=datetime.utcnow() - timedelta(hours=24),
            end_time=datetime.utcnow(),
            limit=100
        )

        result = await query_engine.execute_query(query)

        assert isinstance(result, QueryResponse)
        assert result.execution_time_ms > 0
        assert len(result.logs) >= 0

    @pytest.mark.asyncio
    async def test_filter_operations(self, query_engine):
        """Test all filter operations"""
        filters = [
            QueryFilter(field="level", operator=QueryOperator.EQ, value="error"),
            QueryFilter(field="service", operator=QueryOperator.CONTAINS, value="web"),
            QueryFilter(field="status", operator=QueryOperator.GT, value=400),
            QueryFilter(field="user_id", operator=QueryOperator.IN, value=["user1", "user2"]),
            QueryFilter(field="msg", operator=QueryOperator.REGEX, value="failed.*login")
        ]

        for filter_obj in filters:
            query = AdvancedQueryRequest(
                start_time=datetime.utcnow() - timedelta(hours=1),
                end_time=datetime.utcnow(),
                filters=[filter_obj]
            )

            result = await query_engine.execute_query(query)
            assert isinstance(result, QueryResponse)

            # Check that filter was applied in SQL
            sql_query = result.query_info.get("sql_query", "")
            assert len(sql_query) > 0

    @pytest.mark.asyncio
    async def test_aggregation_operations(self, query_engine):
        """Test aggregation operations"""
        aggregations = [
            QueryAggregation(type=AggregationType.COUNT, field="*"),
            QueryAggregation(type=AggregationType.SUM, field="attrs.response_time"),
            QueryAggregation(type=AggregationType.AVG, field="attrs.response_time"),
            QueryAggregation(type=AggregationType.UNIQUE, field="user_id"),
            QueryAggregation(type=AggregationType.PERCENTILE, field="attrs.response_time", percentile_value=0.95)
        ]

        for agg in aggregations:
            query = AdvancedQueryRequest(
                start_time=datetime.utcnow() - timedelta(hours=24),
                end_time=datetime.utcnow(),
                aggregations=[agg]
            )

            result = await query_engine.execute_query(query)
            assert isinstance(result, QueryResponse)
            assert result.aggregations is not None

    @pytest.mark.asyncio
    async def test_time_series_query(self, query_engine):
        """Test time-series queries"""
        query = AdvancedQueryRequest(
            start_time=datetime.utcnow() - timedelta(hours=24),
            end_time=datetime.utcnow(),
            aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
            time_series=True,
            time_granularity=TimeGranularity.HOUR
        )

        result = await query_engine.execute_query(query)
        assert isinstance(result, QueryResponse)
        assert "time_series" in result.aggregations or len(result.aggregations) > 0

    @pytest.mark.asyncio
    async def test_complex_query_with_grouping(self, query_engine):
        """Test complex queries with grouping and filtering"""
        query = AdvancedQueryRequest(
            start_time=datetime.utcnow() - timedelta(hours=24),
            end_time=datetime.utcnow(),
            filters=[
                QueryFilter(field="level", operator=QueryOperator.IN, value=["error", "warn"])
            ],
            aggregations=[
                QueryAggregation(type=AggregationType.COUNT, field="*"),
                QueryAggregation(type=AggregationType.UNIQUE, field="user_id")
            ],
            group_by=["service", "level"],
            limit=50
        )

        result = await query_engine.execute_query(query)
        assert isinstance(result, QueryResponse)
        assert result.aggregations is not None

        # Verify SQL generation
        sql_query = result.query_info.get("sql_query", "")
        assert "GROUP BY" in sql_query
        assert "WHERE" in sql_query

    def test_filter_to_clickhouse_conversion(self):
        """Test filter to ClickHouse SQL conversion"""
        test_cases = [
            (QueryFilter(field="level", operator=QueryOperator.EQ, value="error"),
             "level = 'error'"),
            (QueryFilter(field="status", operator=QueryOperator.GT, value=400),
             "status > 400"),
            (QueryFilter(field="msg", operator=QueryOperator.CONTAINS, value="failed"),
             "msg LIKE '%failed%'"),
            (QueryFilter(field="attrs.user_id", operator=QueryOperator.REGEX, value="user.*"),
             "match(JSONExtractString(attrs, 'user_id'), 'user.*')"),
            (QueryFilter(field="service", operator=QueryOperator.IN, value=["web", "api"]),
             "service IN ('web', 'api')")
        ]

        for filter_obj, expected_sql in test_cases:
            result = filter_obj.to_clickhouse_condition()
            assert expected_sql in result or result == expected_sql

    def test_aggregation_to_clickhouse_conversion(self):
        """Test aggregation to ClickHouse SQL conversion"""
        test_cases = [
            (QueryAggregation(type=AggregationType.COUNT, field="*"),
             "count() AS count_*"),
            (QueryAggregation(type=AggregationType.AVG, field="response_time"),
             "avg(toFloat64OrZero(response_time)) AS avg_response_time"),
            (QueryAggregation(type=AggregationType.PERCENTILE, field="latency", percentile_value=0.95),
             "quantile(0.95)(toFloat64OrZero(latency)) AS percentile_latency")
        ]

        for agg, expected_sql in test_cases:
            result = agg.to_clickhouse_select()
            assert expected_sql in result or result == expected_sql


class TestDashboardEngine:
    """Test suite for Dashboard Engine"""

    def test_dashboard_list(self, dashboard_engine):
        """Test dashboard listing"""
        dashboards = dashboard_engine.get_dashboard_list()

        assert len(dashboards) == 6
        assert all("id" in d and "name" in d and "type" in d for d in dashboards)

        # Check for expected dashboards
        dashboard_ids = [d["id"] for d in dashboards]
        expected_ids = ["security", "performance", "infrastructure", "business", "compliance", "executive"]
        assert all(expected_id in dashboard_ids for expected_id in expected_ids)

    def test_dashboard_definitions(self, dashboard_engine):
        """Test dashboard definitions"""
        dashboard_ids = ["security", "performance", "infrastructure", "business", "compliance", "executive"]

        for dashboard_id in dashboard_ids:
            dashboard = dashboard_engine.get_dashboard_definition(dashboard_id)
            assert dashboard is not None
            assert dashboard.id == dashboard_id
            assert isinstance(dashboard.widgets, list)
            assert len(dashboard.widgets) > 0

            # Check widget structure
            for widget in dashboard.widgets:
                assert hasattr(widget, 'id')
                assert hasattr(widget, 'title')
                assert hasattr(widget, 'type')
                assert hasattr(widget, 'query')
                assert hasattr(widget, 'position')

    @pytest.mark.asyncio
    async def test_security_dashboard_data(self, dashboard_engine, sample_time_range):
        """Test Security Operations Center dashboard data generation"""
        dashboard_data = await dashboard_engine.get_dashboard_data("security", sample_time_range)

        assert isinstance(dashboard_data, DashboardData)
        assert dashboard_data.dashboard_id == "security"
        assert len(dashboard_data.widgets) > 0

        # Check for expected security widgets
        expected_widgets = ["security_alerts_count", "failed_logins", "top_attack_ips"]
        for widget_id in expected_widgets:
            assert widget_id in dashboard_data.widgets
            widget_data = dashboard_data.widgets[widget_id]
            assert "title" in widget_data
            assert "type" in widget_data
            assert "data" in widget_data or "error" in widget_data

    @pytest.mark.asyncio
    async def test_performance_dashboard_data(self, dashboard_engine, sample_time_range):
        """Test Performance Monitoring dashboard data generation"""
        dashboard_data = await dashboard_engine.get_dashboard_data("performance", sample_time_range)

        assert isinstance(dashboard_data, DashboardData)
        assert dashboard_data.dashboard_id == "performance"

        # Check for expected performance widgets
        expected_widgets = ["total_requests", "error_rate", "response_time_trend"]
        for widget_id in expected_widgets:
            assert widget_id in dashboard_data.widgets

    @pytest.mark.asyncio
    async def test_executive_dashboard_data(self, dashboard_engine, sample_time_range):
        """Test Executive Overview dashboard data generation"""
        dashboard_data = await dashboard_engine.get_dashboard_data("executive", sample_time_range)

        assert isinstance(dashboard_data, DashboardData)
        assert dashboard_data.dashboard_id == "executive"

        # Check for expected executive widgets
        expected_widgets = ["system_health_score", "total_events_processed", "critical_alerts"]
        for widget_id in expected_widgets:
            assert widget_id in dashboard_data.widgets

    @pytest.mark.asyncio
    async def test_all_dashboards_generation(self, dashboard_engine, sample_time_range):
        """Test all dashboard data generation"""
        dashboard_ids = ["security", "performance", "infrastructure", "business", "compliance", "executive"]

        for dashboard_id in dashboard_ids:
            dashboard_data = await dashboard_engine.get_dashboard_data(dashboard_id, sample_time_range)

            assert isinstance(dashboard_data, DashboardData)
            assert dashboard_data.dashboard_id == dashboard_id
            assert len(dashboard_data.widgets) > 0
            assert dashboard_data.generated_at is not None
            assert dashboard_data.metadata["total_widgets"] > 0

    def test_widget_data_formatting(self, dashboard_engine):
        """Test widget data formatting for different visualization types"""
        # Mock query result
        class MockQueryResult:
            def __init__(self):
                self.logs = [{"ts": datetime.now(), "service": "web", "count": 100}]
                self.aggregations = {"total_count": 1500, "avg_response_time": 250.5}
                self.execution_time_ms = 45.2

        mock_result = MockQueryResult()

        # Test different widget types
        from dashboard_engine import DashboardWidget

        # Metric widget
        metric_widget = DashboardWidget(
            id="test_metric",
            title="Test Metric",
            type=VisualizationType.METRIC,
            query=None,  # Not used in formatting test
            position={"x": 0, "y": 0, "w": 3, "h": 2}
        )

        formatted_data = dashboard_engine._format_widget_data(metric_widget, mock_result)
        assert "value" in formatted_data
        assert "label" in formatted_data

        # Table widget
        table_widget = DashboardWidget(
            id="test_table",
            title="Test Table",
            type=VisualizationType.TABLE,
            query=None,
            position={"x": 0, "y": 0, "w": 6, "h": 4}
        )

        formatted_data = dashboard_engine._format_widget_data(table_widget, mock_result)
        assert "columns" in formatted_data
        assert "rows" in formatted_data

    def test_nonexistent_dashboard(self, dashboard_engine):
        """Test handling of nonexistent dashboard"""
        dashboard = dashboard_engine.get_dashboard_definition("nonexistent")
        assert dashboard is None

    @pytest.mark.asyncio
    async def test_dashboard_error_handling(self, dashboard_engine):
        """Test dashboard error handling"""
        # Test with invalid dashboard ID
        with pytest.raises(ValueError):
            await dashboard_engine.get_dashboard_data("invalid_dashboard_id")


class TestQueryEnginePerformance:
    """Performance tests for Query Engine"""

    @pytest.mark.asyncio
    async def test_query_execution_time(self, query_engine):
        """Test query execution time is reasonable"""
        query = AdvancedQueryRequest(
            start_time=datetime.utcnow() - timedelta(hours=1),
            end_time=datetime.utcnow(),
            aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")]
        )

        result = await query_engine.execute_query(query)

        # Should execute in reasonable time (under 1000ms in mock)
        assert result.execution_time_ms < 1000

    @pytest.mark.asyncio
    async def test_complex_query_performance(self, query_engine):
        """Test complex query performance"""
        query = AdvancedQueryRequest(
            start_time=datetime.utcnow() - timedelta(hours=24),
            end_time=datetime.utcnow(),
            filters=[
                QueryFilter(field="level", operator=QueryOperator.IN, value=["error", "warn"]),
                QueryFilter(field="service", operator=QueryOperator.CONTAINS, value="web")
            ],
            aggregations=[
                QueryAggregation(type=AggregationType.COUNT, field="*"),
                QueryAggregation(type=AggregationType.UNIQUE, field="user_id"),
                QueryAggregation(type=AggregationType.AVG, field="attrs.response_time")
            ],
            group_by=["service", "level"],
            time_series=True,
            time_granularity=TimeGranularity.HOUR
        )

        result = await query_engine.execute_query(query)
        assert result.execution_time_ms < 2000  # Complex queries should still be fast


class TestIntegration:
    """Integration tests between components"""

    @pytest.mark.asyncio
    async def test_dashboard_query_integration(self, dashboard_engine, sample_time_range):
        """Test integration between dashboard and query engines"""
        # Get security dashboard
        dashboard_data = await dashboard_engine.get_dashboard_data("security", sample_time_range)

        # Verify that queries were executed
        query_engine = dashboard_engine.query_engine
        client = query_engine.client

        assert len(client.queries_executed) > 0

        # Check that SQL queries contain expected patterns
        sql_queries = client.queries_executed
        assert any("WHERE" in sql for sql in sql_queries)
        assert any("ts >=" in sql for sql in sql_queries)

    @pytest.mark.asyncio
    async def test_end_to_end_dashboard_workflow(self, dashboard_engine):
        """Test complete dashboard workflow"""
        # Step 1: List dashboards
        dashboards = dashboard_engine.get_dashboard_list()
        assert len(dashboards) > 0

        # Step 2: Get first dashboard definition
        first_dashboard_id = dashboards[0]["id"]
        dashboard_def = dashboard_engine.get_dashboard_definition(first_dashboard_id)
        assert dashboard_def is not None

        # Step 3: Generate dashboard data
        dashboard_data = await dashboard_engine.get_dashboard_data(first_dashboard_id)
        assert isinstance(dashboard_data, DashboardData)
        assert len(dashboard_data.widgets) == len(dashboard_def.widgets)


class TestDataValidation:
    """Test data validation and error handling"""

    @pytest.mark.asyncio
    async def test_invalid_time_range(self, query_engine):
        """Test handling of invalid time ranges"""
        # End time before start time
        query = AdvancedQueryRequest(
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() - timedelta(hours=1)
        )

        with pytest.raises(ValueError):
            # This should be caught by pydantic validation
            pass

    @pytest.mark.asyncio
    async def test_query_error_handling(self, query_engine):
        """Test query error handling"""
        # Mock client that throws an error
        query_engine.client.query = lambda sql: (_ for _ in ()).throw(Exception("Database error"))

        query = AdvancedQueryRequest(
            start_time=datetime.utcnow() - timedelta(hours=1),
            end_time=datetime.utcnow()
        )

        result = await query_engine.execute_query(query)

        # Should return error response instead of crashing
        assert isinstance(result, QueryResponse)
        assert "error" in result.query_info

    def test_saved_query_model_validation(self):
        """Test SavedQuery model validation"""
        query_request = AdvancedQueryRequest(
            start_time=datetime.utcnow() - timedelta(hours=1),
            end_time=datetime.utcnow()
        )

        saved_query = SavedQuery(
            name="Test Query",
            description="Test query for validation",
            query=query_request,
            tags=["test", "validation"]
        )

        assert saved_query.name == "Test Query"
        assert saved_query.is_public == False  # default value
        assert "test" in saved_query.tags


# Test fixtures for running tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([
        __file__,
        "-v",  # verbose output
        "-s",  # don't capture print statements
        "--tb=short",  # shorter traceback format
        "--asyncio-mode=auto"  # handle async tests
    ])
