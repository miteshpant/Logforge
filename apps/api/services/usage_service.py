"""
Usage Management Service - Business Logic for Usage Tracking and Billing
Handles usage analytics, billing calculations, and cost management
"""

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import asyncio

from dao.usage_dao import UsageDAO

logger = structlog.get_logger(__name__)

class UsageService:
    """Business Logic Layer for Usage Analytics and Billing"""
    
    def __init__(self):
        self.usage_dao = UsageDAO()
        self._usage_buffer = []
        self._buffer_size = 100
    
    # Usage Tracking Operations
    
    async def track_api_usage(self, usage_data: Dict[str, Any]) -> str:
        """Track single API usage event"""
        try:
            # Validate required fields
            required_fields = ["tenant_id", "endpoint", "method"]
            for field in required_fields:
                if field not in usage_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Set defaults and validate data
            validated_data = {
                "tenant_id": usage_data["tenant_id"],
                "customer_id": usage_data.get("customer_id", usage_data["tenant_id"]),
                "user_id": usage_data.get("user_id"),
                "endpoint": usage_data["endpoint"],
                "method": usage_data["method"].upper(),
                "request_timestamp": usage_data.get("request_timestamp", datetime.now(timezone.utc)),
                "response_status": usage_data.get("response_status", 200),
                "response_time_ms": max(0, usage_data.get("response_time_ms", 0)),
                "feature_type": self._classify_feature_type(usage_data["endpoint"]),
                "request_size_bytes": max(0, usage_data.get("request_size_bytes", 0)),
                "response_size_bytes": max(0, usage_data.get("response_size_bytes", 0)),
                "ip_address": usage_data.get("ip_address"),
                "user_agent": usage_data.get("user_agent"),
                "api_version": usage_data.get("api_version", "v1")
            }
            
            # Save to database
            record_id = await self.usage_dao.save_usage_record(validated_data)
            
            return record_id
            
        except Exception as e:
            logger.error(f"Failed to track API usage: {e}")
            raise
    
    async def track_batch_usage(self, usage_records: List[Dict[str, Any]]) -> int:
        """Track multiple API usage events in batch"""
        try:
            if not usage_records:
                return 0
            
            # Validate and prepare all records
            validated_records = []
            for record in usage_records:
                try:
                    validated_data = {
                        "tenant_id": record.get("tenant_id", "default"),
                        "customer_id": record.get("customer_id", record.get("tenant_id", "default")),
                        "user_id": record.get("user_id"),
                        "endpoint": record.get("endpoint", "unknown"),
                        "method": record.get("method", "GET").upper(),
                        "request_timestamp": record.get("request_timestamp", datetime.now(timezone.utc)),
                        "response_status": record.get("response_status", 200),
                        "response_time_ms": max(0, record.get("response_time_ms", 0)),
                        "feature_type": self._classify_feature_type(record.get("endpoint", "unknown")),
                        "request_size_bytes": max(0, record.get("request_size_bytes", 0)),
                        "response_size_bytes": max(0, record.get("response_size_bytes", 0)),
                        "ip_address": record.get("ip_address"),
                        "user_agent": record.get("user_agent"),
                        "api_version": record.get("api_version", "v1")
                    }
                    validated_records.append(validated_data)
                except Exception as e:
                    logger.warning(f"Skipping invalid usage record: {e}")
                    continue
            
            if not validated_records:
                return 0
            
            # Batch save to database
            saved_count = await self.usage_dao.batch_save_usage_records(validated_records)
            
            logger.info(f"Batch usage tracking completed: {saved_count} records")
            return saved_count
            
        except Exception as e:
            logger.error(f"Failed to track batch usage: {e}")
            raise
    
    # Usage Analytics Operations
    
    async def get_tenant_usage_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Get comprehensive usage summary for tenant"""
        try:
            # Get current month usage
            current_usage = await self.usage_dao.get_tenant_usage_current_month(tenant_id)
            
            # Get real-time metrics
            realtime_usage = await self.usage_dao.get_realtime_usage(tenant_id, 60)  # Last hour
            
            # Calculate cost estimate
            cost_data = await self.usage_dao.calculate_tenant_cost(tenant_id)
            
            return {
                "tenant_id": tenant_id,
                "current_month": current_usage,
                "realtime": realtime_usage,
                "billing": cost_data,
                "summary_generated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get usage summary for tenant {tenant_id}: {e}")
            raise
    
    async def get_tenant_usage_analytics(self, tenant_id: str, time_range: str = "30d") -> Dict[str, Any]:
        """Get detailed usage analytics for tenant"""
        try:
            # Parse time range
            months = self._parse_time_range(time_range)
            
            # Get historical usage data
            history = await self.usage_dao.get_tenant_usage_history(tenant_id, months)
            
            # Get current month usage
            current_usage = await self.usage_dao.get_tenant_usage_current_month(tenant_id)
            
            # Calculate trends and insights
            trends = self._calculate_usage_trends(history)
            
            return {
                "tenant_id": tenant_id,
                "time_range": time_range,
                "current_month": current_usage,
                "historical_data": history,
                "trends": trends,
                "analytics_generated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get usage analytics for tenant {tenant_id}: {e}")
            raise
    
    async def get_billing_estimate(self, tenant_id: str, billing_period: Optional[str] = None) -> Dict[str, Any]:
        """Get billing estimate for tenant"""
        try:
            # Calculate cost for specified period or current month
            cost_data = await self.usage_dao.calculate_tenant_cost(tenant_id, billing_period)
            
            # Add billing insights
            insights = self._generate_billing_insights(cost_data)
            
            return {
                **cost_data,
                "insights": insights,
                "next_billing_date": self._calculate_next_billing_date(),
                "estimate_generated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get billing estimate for tenant {tenant_id}: {e}")
            raise
    
    # Platform Analytics Operations
    
    async def get_platform_analytics(self) -> Dict[str, Any]:
        """Get platform-wide usage analytics"""
        try:
            logger.debug("Starting get_platform_analytics")
            
            # Get platform statistics
            logger.debug("Getting platform stats...")
            platform_stats = await self.usage_dao.get_platform_usage_stats()
            logger.debug(f"Platform stats result: {platform_stats}")
            
            # Get top consuming tenants
            logger.debug("Getting top consuming tenants...")
            top_tenants = await self.usage_dao.get_top_consuming_tenants(10)
            logger.debug(f"Top tenants result: {top_tenants}")
            
            # Calculate platform metrics with safer handling
            total_revenue_estimate = 0.0
            if top_tenants:
                logger.debug("Calculating revenue estimates...")
                for tenant in top_tenants:
                    try:
                        tenant_revenue = await self._estimate_tenant_revenue(tenant["tenant_id"])
                        total_revenue_estimate += tenant_revenue
                        logger.debug(f"Tenant {tenant['tenant_id']} revenue: {tenant_revenue}")
                    except Exception as e:
                        logger.warning(f"Failed to estimate revenue for tenant {tenant['tenant_id']}: {e}")
                        continue
            
            platform_metrics = {
                "total_revenue_estimate": total_revenue_estimate,
                "avg_calls_per_tenant": (
                    platform_stats["total_api_calls_month"] / 
                    max(1, platform_stats["active_tenants_this_month"])
                ),
                "platform_health_score": self._calculate_platform_health(platform_stats)
            }
            
            result = {
                "platform_stats": platform_stats,
                "top_tenants": top_tenants,
                "metrics": platform_metrics,
                "analytics_generated_at": datetime.now(timezone.utc).isoformat()
            }
            
            logger.debug(f"get_platform_analytics completed successfully: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get platform analytics: {e}", exc_info=True)
            raise
    
    async def export_usage_report(self, tenant_id: str, format: str = "json", 
                                 billing_period: Optional[str] = None) -> Dict[str, Any]:
        """Export comprehensive usage report"""
        try:
            # Get comprehensive data
            usage_analytics = await self.get_tenant_usage_analytics(tenant_id, "90d")  # 3 months
            billing_data = await self.get_billing_estimate(tenant_id, billing_period)
            
            # Compile report
            report = {
                "report_type": "usage_export",
                "tenant_id": tenant_id,
                "billing_period": billing_period or datetime.now(timezone.utc).strftime("%Y-%m"),
                "format": format,
                "usage_analytics": usage_analytics,
                "billing_data": billing_data,
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "report_version": "1.0"
            }
            
            # TODO: In production, would generate actual file exports (CSV, PDF, etc.)
            if format.lower() == "csv":
                report["download_url"] = f"/api/v1/usage/reports/{tenant_id}/download?format=csv"
            elif format.lower() == "pdf":
                report["download_url"] = f"/api/v1/usage/reports/{tenant_id}/download?format=pdf"
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to export usage report for tenant {tenant_id}: {e}")
            raise
    
    # Utility Methods
    
    def _classify_feature_type(self, endpoint: str) -> str:
        """Classify API endpoint into feature type for billing"""
        endpoint = endpoint.lower()
        
        if "/ingest" in endpoint or "/logs" in endpoint:
            return "ingestion"
        elif "/query" in endpoint or "/search" in endpoint:
            return "query"
        elif "/dashboard" in endpoint or "/analytics" in endpoint:
            return "analytics"
        elif "/alert" in endpoint:
            return "alerts"
        elif "/security" in endpoint:
            return "security"
        elif "/storage" in endpoint:
            return "storage"
        else:
            return "api"
    
    def _parse_time_range(self, time_range: str) -> int:
        """Parse time range string to number of months"""
        if time_range.endswith("d"):
            days = int(time_range[:-1])
            return max(1, days // 30)
        elif time_range.endswith("m"):
            return max(1, int(time_range[:-1]))
        else:
            return 1  # Default to 1 month
    
    def _calculate_usage_trends(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate usage trends from historical data"""
        if len(history) < 2:
            return {"trend": "insufficient_data"}
        
        # Calculate month-over-month growth
        latest = history[0]["api_calls"]
        previous = history[1]["api_calls"]
        
        if previous == 0:
            growth_rate = 100.0 if latest > 0 else 0.0
        else:
            growth_rate = ((latest - previous) / previous) * 100
        
        # Determine trend direction
        if growth_rate > 10:
            trend = "growing"
        elif growth_rate < -10:
            trend = "declining"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "growth_rate": round(growth_rate, 2),
            "latest_month_calls": latest,
            "previous_month_calls": previous
        }
    
    def _generate_billing_insights(self, cost_data: Dict[str, Any]) -> List[str]:
        """Generate billing insights and recommendations"""
        insights = []
        
        total_cost = cost_data.get("total_cost", 0)
        cost_breakdown = cost_data.get("cost_breakdown", {})
        
        if total_cost > 100:
            insights.append("High usage month - consider reviewing API call patterns")
        
        # Find highest cost feature
        if cost_breakdown:
            highest_cost_feature = max(cost_breakdown.items(), key=lambda x: x[1]["cost"])
            insights.append(f"Highest cost feature: {highest_cost_feature[0]} (${highest_cost_feature[1]['cost']:.2f})")
        
        if total_cost < 10:
            insights.append("Low usage month - consider increasing platform adoption")
        
        return insights
    
    def _calculate_next_billing_date(self) -> str:
        """Calculate next billing date (first day of next month)"""
        now = datetime.now(timezone.utc)
        next_month = now.replace(day=1) + timedelta(days=32)
        next_billing = next_month.replace(day=1)
        return next_billing.isoformat()
    
    async def _estimate_tenant_revenue(self, tenant_id: str) -> float:
        """Estimate revenue from tenant (simplified)"""
        try:
            cost_data = await self.usage_dao.calculate_tenant_cost(tenant_id)
            return cost_data.get("total_cost", 0.0)
        except:
            return 0.0
    
    def _calculate_platform_health(self, platform_stats: Dict[str, Any]) -> float:
        """Calculate platform health score (0-100)"""
        try:
            # Simple health calculation based on metrics
            api_calls = platform_stats.get("total_api_calls_month", 0)
            active_tenants = platform_stats.get("active_tenants_this_month", 0)
            error_rate = platform_stats.get("total_errors", 0) / max(1, api_calls)
            
            # Health factors (simplified)
            activity_score = min(100, (api_calls / 10000) * 50)  # Up to 50 points for activity
            tenant_score = min(30, active_tenants * 3)           # Up to 30 points for tenants
            reliability_score = max(0, 20 - (error_rate * 100))  # Up to 20 points for reliability
            
            return round(activity_score + tenant_score + reliability_score, 1)
        except:
            return 50.0  # Default health score