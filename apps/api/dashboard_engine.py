"""
Dashboard Engine for Logforge M7
Provides 6 pre-built enterprise dashboards with real-time data
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from enum import Enum
import json
from dataclasses import dataclass

from query_engine import AdvancedQueryEngine, AdvancedQueryRequest, QueryFilter, QueryAggregation, AggregationType, QueryOperator, TimeGranularity


class DashboardType(str, Enum):
    """Available dashboard types"""
    SECURITY = "security"
    PERFORMANCE = "performance" 
    INFRASTRUCTURE = "infrastructure"
    BUSINESS = "business"
    COMPLIANCE = "compliance"
    EXECUTIVE = "executive"


class VisualizationType(str, Enum):
    """Chart/visualization types"""
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    TABLE = "table"
    METRIC = "metric"
    HEATMAP = "heatmap"
    MAP = "map"


@dataclass
class DashboardWidget:
    """Individual dashboard widget/panel"""
    id: str
    title: str
    type: VisualizationType
    query: AdvancedQueryRequest
    position: Dict[str, int]  # x, y, w, h for grid layout
    refresh_interval: int = 30  # seconds
    description: Optional[str] = None


class DashboardDefinition(BaseModel):
    """Dashboard definition with widgets"""
    id: str
    name: str
    type: DashboardType
    description: str
    widgets: List[DashboardWidget]
    tags: List[str] = Field(default=[])
    is_public: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DashboardData(BaseModel):
    """Dashboard data response"""
    dashboard_id: str
    generated_at: datetime
    widgets: Dict[str, Any]  # widget_id -> data
    metadata: Dict[str, Any] = Field(default={})


class DashboardEngine:
    """Enterprise dashboard engine with pre-built dashboards"""
    
    def __init__(self, query_engine: AdvancedQueryEngine):
        self.query_engine = query_engine
        self.dashboards = self._create_enterprise_dashboards()
    
    def get_dashboard_list(self) -> List[Dict[str, Any]]:
        """Get list of available dashboards"""
        return [
            {
                "id": dashboard.id,
                "name": dashboard.name,
                "type": dashboard.type,
                "description": dashboard.description,
                "widget_count": len(dashboard.widgets),
                "tags": dashboard.tags
            }
            for dashboard in self.dashboards.values()
        ]
    
    def get_dashboard_definition(self, dashboard_id: str) -> Optional[DashboardDefinition]:
        """Get dashboard definition"""
        return self.dashboards.get(dashboard_id)
    
    async def get_dashboard_data(self, dashboard_id: str, time_range: Optional[Dict[str, datetime]] = None) -> DashboardData:
        """Generate dashboard data"""
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found")
        
        # Default to last 24 hours
        if not time_range:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=24)
            time_range = {"start_time": start_time, "end_time": end_time}
        
        widget_data = {}
        
        # Execute queries for each widget
        for widget in dashboard.widgets:
            try:
                # Update query time range
                widget_query = widget.query.copy()
                widget_query.start_time = time_range["start_time"]
                widget_query.end_time = time_range["end_time"]
                
                # Execute query
                result = await self.query_engine.execute_query(widget_query)
                
                # Format data based on visualization type
                formatted_data = self._format_widget_data(widget, result)
                
                widget_data[widget.id] = {
                    "title": widget.title,
                    "type": widget.type,
                    "data": formatted_data,
                    "execution_time_ms": result.execution_time_ms,
                    "last_updated": datetime.utcnow().isoformat()
                }
                
            except Exception as e:
                widget_data[widget.id] = {
                    "title": widget.title,
                    "type": widget.type,
                    "error": str(e),
                    "last_updated": datetime.utcnow().isoformat()
                }
        
        return DashboardData(
            dashboard_id=dashboard_id,
            generated_at=datetime.utcnow(),
            widgets=widget_data,
            metadata={
                "time_range": time_range,
                "total_widgets": len(dashboard.widgets),
                "dashboard_name": dashboard.name
            }
        )
    
    def _format_widget_data(self, widget: DashboardWidget, query_result) -> Dict[str, Any]:
        """Format query result for specific visualization type"""
        if widget.type == VisualizationType.METRIC:
            # Single metric value
            if query_result.aggregations:
                # Get first aggregation value
                for key, value in query_result.aggregations.items():
                    if isinstance(value, (int, float)):
                        return {"value": value, "label": key}
            return {"value": query_result.total_count, "label": "Total"}
        
        elif widget.type == VisualizationType.LINE_CHART:
            # Time series data
            if query_result.aggregations.get("time_series"):
                return {
                    "series": [{
                        "name": "Values",
                        "data": [
                            {"x": item["time"], "y": list(item.values())[-1]}
                            for item in query_result.aggregations["time_series"]
                        ]
                    }]
                }
        
        elif widget.type == VisualizationType.PIE_CHART:
            # Categorical data
            if query_result.aggregations and not query_result.aggregations.get("time_series"):
                return {
                    "series": [
                        {"label": key, "value": value}
                        for key, value in query_result.aggregations.items()
                        if isinstance(value, (int, float))
                    ]
                }
        
        elif widget.type == VisualizationType.TABLE:
            # Tabular data
            return {
                "columns": list(query_result.logs[0].keys()) if query_result.logs else [],
                "rows": query_result.logs[:100]  # Limit to first 100 rows
            }
        
        elif widget.type == VisualizationType.BAR_CHART:
            # Categorical data
            if query_result.logs:
                # Group by first non-timestamp field
                data = {}
                for log in query_result.logs:
                    key = list(log.values())[1] if len(log) > 1 else "Unknown"
                    data[key] = data.get(key, 0) + 1
                return {
                    "categories": list(data.keys()),
                    "series": [{"name": "Count", "data": list(data.values())}]
                }
        
        # Default: return raw data
        return {
            "logs": query_result.logs,
            "aggregations": query_result.aggregations,
            "total_count": query_result.total_count
        }
    
    def _create_enterprise_dashboards(self) -> Dict[str, DashboardDefinition]:
        """Create 6 pre-built enterprise dashboards"""
        dashboards = {}
        
        # 1. Security Operations Center (SOC) Dashboard
        dashboards["security"] = self._create_security_dashboard()
        
        # 2. Performance Monitoring Dashboard
        dashboards["performance"] = self._create_performance_dashboard()
        
        # 3. Infrastructure Overview Dashboard
        dashboards["infrastructure"] = self._create_infrastructure_dashboard()
        
        # 4. Business Intelligence Dashboard
        dashboards["business"] = self._create_business_dashboard()
        
        # 5. Compliance & Audit Dashboard
        dashboards["compliance"] = self._create_compliance_dashboard()
        
        # 6. Executive Overview Dashboard
        dashboards["executive"] = self._create_executive_dashboard()
        
        return dashboards
    
    def _create_security_dashboard(self) -> DashboardDefinition:
        """Security Operations Center Dashboard"""
        now = datetime.utcnow()
        yesterday = now - timedelta(hours=24)
        
        widgets = [
            DashboardWidget(
                id="security_alerts_count",
                title="Security Alerts (24h)",
                type=VisualizationType.METRIC,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
                    filters=[QueryFilter(field="level", operator=QueryOperator.IN, value=["error", "critical", "alert"])]
                ),
                position={"x": 0, "y": 0, "w": 3, "h": 2}
            ),
            
            DashboardWidget(
                id="failed_logins",
                title="Failed Login Attempts",
                type=VisualizationType.LINE_CHART,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
                    filters=[QueryFilter(field="msg", operator=QueryOperator.CONTAINS, value="failed login")],
                    time_series=True,
                    time_granularity=TimeGranularity.HOUR
                ),
                position={"x": 3, "y": 0, "w": 9, "h": 4}
            ),
            
            DashboardWidget(
                id="top_attack_ips",
                title="Top Attack Source IPs",
                type=VisualizationType.BAR_CHART,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
                    group_by=["src_ip"],
                    filters=[QueryFilter(field="level", operator=QueryOperator.EQ, value="error")],
                    limit=10
                ),
                position={"x": 0, "y": 4, "w": 6, "h": 4}
            ),
            
            DashboardWidget(
                id="security_events_by_service",
                title="Security Events by Service",
                type=VisualizationType.PIE_CHART,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
                    group_by=["service"],
                    filters=[QueryFilter(field="level", operator=QueryOperator.IN, value=["error", "warn"])]
                ),
                position={"x": 6, "y": 4, "w": 6, "h": 4}
            ),
            
            DashboardWidget(
                id="recent_critical_events",
                title="Recent Critical Security Events",
                type=VisualizationType.TABLE,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    filters=[QueryFilter(field="level", operator=QueryOperator.EQ, value="critical")],
                    limit=50,
                    include_fields=["ts", "service", "msg", "src_ip", "user_id"]
                ),
                position={"x": 0, "y": 8, "w": 12, "h": 4}
            )
        ]
        
        return DashboardDefinition(
            id="security",
            name="Security Operations Center",
            type=DashboardType.SECURITY,
            description="Real-time security monitoring, threat detection, and incident response",
            widgets=widgets,
            tags=["security", "soc", "alerts", "threats"]
        )
    
    def _create_performance_dashboard(self) -> DashboardDefinition:
        """Performance Monitoring Dashboard"""
        now = datetime.utcnow()
        yesterday = now - timedelta(hours=24)
        
        widgets = [
            DashboardWidget(
                id="total_requests",
                title="Total Requests (24h)",
                type=VisualizationType.METRIC,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")]
                ),
                position={"x": 0, "y": 0, "w": 3, "h": 2}
            ),
            
            DashboardWidget(
                id="error_rate",
                title="Error Rate %",
                type=VisualizationType.METRIC,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[
                        QueryAggregation(type=AggregationType.COUNT, field="*", alias="total"),
                        QueryAggregation(type=AggregationType.COUNT, field="level", alias="errors")
                    ],
                    filters=[QueryFilter(field="level", operator=QueryOperator.EQ, value="error")]
                ),
                position={"x": 3, "y": 0, "w": 3, "h": 2}
            ),
            
            DashboardWidget(
                id="response_time_trend",
                title="Response Time Trend",
                type=VisualizationType.LINE_CHART,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.AVG, field="attrs.response_time")],
                    time_series=True,
                    time_granularity=TimeGranularity.HOUR
                ),
                position={"x": 6, "y": 0, "w": 6, "h": 4}
            ),
            
            DashboardWidget(
                id="slowest_endpoints",
                title="Slowest Endpoints",
                type=VisualizationType.BAR_CHART,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.AVG, field="attrs.response_time")],
                    group_by=["attrs.endpoint"],
                    limit=10
                ),
                position={"x": 0, "y": 4, "w": 6, "h": 4}
            ),
            
            DashboardWidget(
                id="http_status_codes",
                title="HTTP Status Code Distribution",
                type=VisualizationType.PIE_CHART,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
                    group_by=["attrs.status_code"]
                ),
                position={"x": 6, "y": 4, "w": 6, "h": 4}
            )
        ]
        
        return DashboardDefinition(
            id="performance",
            name="Performance Monitoring",
            type=DashboardType.PERFORMANCE,
            description="Application performance metrics, response times, and error rates",
            widgets=widgets,
            tags=["performance", "apm", "response_time", "errors"]
        )
    
    def _create_infrastructure_dashboard(self) -> DashboardDefinition:
        """Infrastructure Overview Dashboard"""
        now = datetime.utcnow()
        yesterday = now - timedelta(hours=24)
        
        widgets = [
            DashboardWidget(
                id="active_services",
                title="Active Services",
                type=VisualizationType.METRIC,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.UNIQUE, field="service")]
                ),
                position={"x": 0, "y": 0, "w": 3, "h": 2}
            ),
            
            DashboardWidget(
                id="log_volume_trend",
                title="Log Volume Over Time",
                type=VisualizationType.LINE_CHART,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
                    time_series=True,
                    time_granularity=TimeGranularity.HOUR
                ),
                position={"x": 3, "y": 0, "w": 9, "h": 4}
            ),
            
            DashboardWidget(
                id="logs_by_service",
                title="Log Volume by Service",
                type=VisualizationType.BAR_CHART,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
                    group_by=["service"],
                    limit=15
                ),
                position={"x": 0, "y": 4, "w": 6, "h": 4}
            ),
            
            DashboardWidget(
                id="logs_by_host",
                title="Log Distribution by Host",
                type=VisualizationType.PIE_CHART,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
                    group_by=["host"],
                    limit=10
                ),
                position={"x": 6, "y": 4, "w": 6, "h": 4}
            ),
            
            DashboardWidget(
                id="log_levels_distribution",
                title="Log Levels Distribution",
                type=VisualizationType.BAR_CHART,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
                    group_by=["level"]
                ),
                position={"x": 0, "y": 8, "w": 12, "h": 3}
            )
        ]
        
        return DashboardDefinition(
            id="infrastructure",
            name="Infrastructure Overview",
            type=DashboardType.INFRASTRUCTURE,
            description="System health, resource utilization, and infrastructure monitoring",
            widgets=widgets,
            tags=["infrastructure", "systems", "monitoring", "health"]
        )
    
    def _create_business_dashboard(self) -> DashboardDefinition:
        """Business Intelligence Dashboard"""
        now = datetime.utcnow()
        yesterday = now - timedelta(hours=24)
        
        widgets = [
            DashboardWidget(
                id="active_users",
                title="Active Users (24h)",
                type=VisualizationType.METRIC,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.UNIQUE, field="user_id")],
                    filters=[QueryFilter(field="user_id", operator=QueryOperator.NE, value="")]
                ),
                position={"x": 0, "y": 0, "w": 3, "h": 2}
            ),
            
            DashboardWidget(
                id="user_activity_trend",
                title="User Activity Trend",
                type=VisualizationType.LINE_CHART,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.UNIQUE, field="user_id")],
                    time_series=True,
                    time_granularity=TimeGranularity.HOUR,
                    filters=[QueryFilter(field="user_id", operator=QueryOperator.NE, value="")]
                ),
                position={"x": 3, "y": 0, "w": 9, "h": 4}
            ),
            
            DashboardWidget(
                id="top_features_used",
                title="Most Used Features",
                type=VisualizationType.BAR_CHART,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
                    group_by=["attrs.feature"],
                    limit=10
                ),
                position={"x": 0, "y": 4, "w": 6, "h": 4}
            ),
            
            DashboardWidget(
                id="user_geographic_distribution",
                title="User Geographic Distribution",
                type=VisualizationType.PIE_CHART,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.UNIQUE, field="user_id")],
                    group_by=["attrs.country"],
                    filters=[QueryFilter(field="user_id", operator=QueryOperator.NE, value="")]
                ),
                position={"x": 6, "y": 4, "w": 6, "h": 4}
            ),
            
            DashboardWidget(
                id="conversion_events",
                title="Business Conversion Events",
                type=VisualizationType.TABLE,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    filters=[QueryFilter(field="attrs.event_type", operator=QueryOperator.IN, value=["purchase", "signup", "conversion"])],
                    limit=50,
                    include_fields=["ts", "user_id", "attrs.event_type", "attrs.value"]
                ),
                position={"x": 0, "y": 8, "w": 12, "h": 4}
            )
        ]
        
        return DashboardDefinition(
            id="business",
            name="Business Intelligence",
            type=DashboardType.BUSINESS,
            description="User behavior, feature usage, and business metrics analysis",
            widgets=widgets,
            tags=["business", "users", "analytics", "conversion"]
        )
    
    def _create_compliance_dashboard(self) -> DashboardDefinition:
        """Compliance & Audit Dashboard"""
        now = datetime.utcnow()
        yesterday = now - timedelta(hours=24)
        
        widgets = [
            DashboardWidget(
                id="audit_events_count",
                title="Audit Events (24h)",
                type=VisualizationType.METRIC,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
                    filters=[QueryFilter(field="attrs.audit", operator=QueryOperator.EQ, value="true")]
                ),
                position={"x": 0, "y": 0, "w": 3, "h": 2}
            ),
            
            DashboardWidget(
                id="data_access_events",
                title="Data Access Events",
                type=VisualizationType.LINE_CHART,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
                    filters=[QueryFilter(field="attrs.action", operator=QueryOperator.IN, value=["read", "write", "delete"])],
                    time_series=True,
                    time_granularity=TimeGranularity.HOUR
                ),
                position={"x": 3, "y": 0, "w": 9, "h": 4}
            ),
            
            DashboardWidget(
                id="privileged_access",
                title="Privileged Access Activities",
                type=VisualizationType.BAR_CHART,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
                    group_by=["user_id"],
                    filters=[QueryFilter(field="attrs.privileged", operator=QueryOperator.EQ, value="true")],
                    limit=10
                ),
                position={"x": 0, "y": 4, "w": 6, "h": 4}
            ),
            
            DashboardWidget(
                id="policy_violations",
                title="Policy Violations by Type",
                type=VisualizationType.PIE_CHART,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
                    group_by=["attrs.violation_type"],
                    filters=[QueryFilter(field="attrs.policy_violation", operator=QueryOperator.EQ, value="true")]
                ),
                position={"x": 6, "y": 4, "w": 6, "h": 4}
            ),
            
            DashboardWidget(
                id="recent_audit_trail",
                title="Recent Audit Trail",
                type=VisualizationType.TABLE,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    filters=[QueryFilter(field="attrs.audit", operator=QueryOperator.EQ, value="true")],
                    limit=100,
                    include_fields=["ts", "user_id", "attrs.action", "attrs.resource", "src_ip"]
                ),
                position={"x": 0, "y": 8, "w": 12, "h": 4}
            )
        ]
        
        return DashboardDefinition(
            id="compliance",
            name="Compliance & Audit",
            type=DashboardType.COMPLIANCE,
            description="Audit trails, compliance monitoring, and regulatory reporting",
            widgets=widgets,
            tags=["compliance", "audit", "governance", "policy"]
        )
    
    def _create_executive_dashboard(self) -> DashboardDefinition:
        """Executive Overview Dashboard"""
        now = datetime.utcnow()
        yesterday = now - timedelta(hours=24)
        
        widgets = [
            DashboardWidget(
                id="system_health_score",
                title="System Health Score",
                type=VisualizationType.METRIC,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[
                        QueryAggregation(type=AggregationType.COUNT, field="*", alias="total"),
                        QueryAggregation(type=AggregationType.COUNT, field="level", alias="errors")
                    ],
                    filters=[QueryFilter(field="level", operator=QueryOperator.EQ, value="error")]
                ),
                position={"x": 0, "y": 0, "w": 3, "h": 2}
            ),
            
            DashboardWidget(
                id="total_events_processed",
                title="Total Events Processed",
                type=VisualizationType.METRIC,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")]
                ),
                position={"x": 3, "y": 0, "w": 3, "h": 2}
            ),
            
            DashboardWidget(
                id="critical_alerts",
                title="Critical Alerts (24h)",
                type=VisualizationType.METRIC,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
                    filters=[QueryFilter(field="level", operator=QueryOperator.EQ, value="critical")]
                ),
                position={"x": 6, "y": 0, "w": 3, "h": 2}
            ),
            
            DashboardWidget(
                id="security_posture",
                title="Security Posture Trend",
                type=VisualizationType.LINE_CHART,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
                    filters=[QueryFilter(field="level", operator=QueryOperator.IN, value=["error", "critical"])],
                    time_series=True,
                    time_granularity=TimeGranularity.HOUR
                ),
                position={"x": 9, "y": 0, "w": 3, "h": 4}
            ),
            
            DashboardWidget(
                id="service_availability",
                title="Service Availability",
                type=VisualizationType.BAR_CHART,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[QueryAggregation(type=AggregationType.COUNT, field="*")],
                    group_by=["service"]
                ),
                position={"x": 0, "y": 4, "w": 9, "h": 4}
            ),
            
            DashboardWidget(
                id="key_metrics_summary",
                title="Key Performance Indicators",
                type=VisualizationType.TABLE,
                query=AdvancedQueryRequest(
                    start_time=yesterday,
                    end_time=now,
                    aggregations=[
                        QueryAggregation(type=AggregationType.COUNT, field="*", alias="total_events"),
                        QueryAggregation(type=AggregationType.UNIQUE, field="service", alias="active_services"),
                        QueryAggregation(type=AggregationType.UNIQUE, field="user_id", alias="active_users")
                    ]
                ),
                position={"x": 0, "y": 8, "w": 12, "h": 3}
            )
        ]
        
        return DashboardDefinition(
            id="executive",
            name="Executive Overview",
            type=DashboardType.EXECUTIVE,
            description="High-level business and technical KPIs for executive decision making",
            widgets=widgets,
            tags=["executive", "kpi", "overview", "summary"]
        )