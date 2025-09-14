"""
Usage Management DAO - Database Operations for Usage Tracking and Billing
Handles usage analytics, billing calculations, and cost management
"""

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import json
import uuid

from database_layer import DatabaseLayer
from constants.database_constants import (
    DEFAULT_BATCH_SIZE, MAX_BATCH_SIZE
)

logger = structlog.get_logger(__name__)

class UsageDAO:
    """Data Access Object for Usage Analytics and Billing"""
    
    def __init__(self):
        self.db = DatabaseLayer("UsageDAO", "usage-dao-service-key")
    
    # Usage Records Operations
    
    async def save_usage_record(self, usage_data: Dict[str, Any]) -> str:
        """Save single usage record to database"""
        try:
            record_id = usage_data.get("id", str(uuid.uuid4()))
            
            # Create usage record in api_usage_audit_mt table
            query = """
            INSERT INTO api_usage_audit_mt (
                id, customer_id, tenant_id, user_id, endpoint, method,
                request_timestamp, response_status, response_time_ms,
                feature_type, request_size_bytes, response_size_bytes,
                ip_address, user_agent, api_version
            ) VALUES (
                %(id)s, %(customer_id)s, %(tenant_id)s, %(user_id)s, %(endpoint)s, %(method)s,
                %(request_timestamp)s, %(response_status)s, %(response_time_ms)s,
                %(feature_type)s, %(request_size_bytes)s, %(response_size_bytes)s,
                %(ip_address)s, %(user_agent)s, %(api_version)s
            )
            """
            
            params = {
                "id": record_id,
                "customer_id": usage_data.get("customer_id", usage_data.get("tenant_id", "default")),
                "tenant_id": usage_data.get("tenant_id", "default"),
                "user_id": usage_data.get("user_id"),
                "endpoint": usage_data.get("endpoint", ""),
                "method": usage_data.get("method", "GET"),
                "request_timestamp": usage_data.get("request_timestamp", datetime.now(timezone.utc)),
                "response_status": usage_data.get("response_status", 200),
                "response_time_ms": usage_data.get("response_time_ms", 0),
                "feature_type": usage_data.get("feature_type", "unknown"),
                "request_size_bytes": usage_data.get("request_size_bytes", 0),
                "response_size_bytes": usage_data.get("response_size_bytes", 0),
                "ip_address": usage_data.get("ip_address"),
                "user_agent": usage_data.get("user_agent"),
                "api_version": usage_data.get("api_version", "v1")
            }
            
            await self.db.execute_query(query, params)
            logger.debug(f"Usage record saved: {record_id}")
            
            return record_id
            
        except Exception as e:
            logger.error(f"Failed to save usage record: {e}")
            raise
    
    async def batch_save_usage_records(self, usage_records: List[Dict[str, Any]]) -> int:
        """Batch save multiple usage records to database"""
        try:
            if not usage_records:
                return 0
            
            # Prepare batch data with proper defaults
            processed_records = []
            for record in usage_records:
                record_data = {
                    "id": record.get("id", str(uuid.uuid4())),
                    "customer_id": record.get("customer_id", record.get("tenant_id", "default")),
                    "tenant_id": record.get("tenant_id", "default"),
                    "user_id": record.get("user_id"),
                    "endpoint": record.get("endpoint", ""),
                    "method": record.get("method", "GET"),
                    "request_timestamp": record.get("request_timestamp", datetime.now(timezone.utc)),
                    "response_status": record.get("response_status", 200),
                    "response_time_ms": record.get("response_time_ms", 0),
                    "feature_type": record.get("feature_type", "unknown"),
                    "request_size_bytes": record.get("request_size_bytes", 0),
                    "response_size_bytes": record.get("response_size_bytes", 0),
                    "ip_address": record.get("ip_address"),
                    "user_agent": record.get("user_agent"),
                    "api_version": record.get("api_version", "v1")
                }
                processed_records.append(record_data)
            
            # Batch insert using multiple single inserts for ClickHouse compatibility
            for record in processed_records:
                await self.save_usage_record(record)
            
            logger.info(f"Usage batch saved: {len(processed_records)} records")
            return len(processed_records)
            
        except Exception as e:
            logger.error(f"Failed to batch save usage records: {e}")
            raise
    
    # Usage Analytics Queries
    
    async def get_tenant_usage_current_month(self, tenant_id: str) -> Dict[str, Any]:
        """Get current month usage statistics for tenant"""
        try:
            current_month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Query for current month usage
            query = """
            SELECT 
                COUNT(*) as total_api_calls,
                COUNT(DISTINCT endpoint) as unique_endpoints,
                AVG(response_time_ms) as avg_response_time,
                COUNT(CASE WHEN response_status >= 400 THEN 1 END) as error_count,
                SUM(request_size_bytes) as total_request_bytes,
                SUM(response_size_bytes) as total_response_bytes,
                feature_type,
                COUNT(*) as feature_calls
            FROM api_usage_audit_mt
            WHERE tenant_id = %(tenant_id)s 
            AND request_timestamp >= %(current_month_start)s
            GROUP BY feature_type
            """
            
            params = {
                "tenant_id": tenant_id,
                "current_month_start": current_month_start
            }
            
            results = await self.db.fetch_all(query, params)
            
            # Process results into structured format
            feature_breakdown = {}
            total_calls = 0
            total_errors = 0
            
            for row in results:
                feature_type = row.get("feature_type", "unknown")
                feature_calls = row.get("feature_calls", 0)
                
                feature_breakdown[feature_type] = feature_calls
                total_calls += feature_calls
                total_errors += row.get("error_count", 0)
            
            return {
                "tenant_id": tenant_id,
                "api_calls": total_calls,
                "feature_breakdown": feature_breakdown,
                "error_count": total_errors,
                "billing_period": current_month_start.strftime("%Y-%m"),
                "retrieved_at": datetime.now(timezone.utc)
            }
            
        except Exception as e:
            logger.error(f"Failed to get current usage for tenant {tenant_id}: {e}")
            raise
    
    async def get_tenant_usage_history(self, tenant_id: str, months: int = 3) -> List[Dict[str, Any]]:
        """Get historical usage data for tenant"""
        try:
            history_data = []
            
            for i in range(months):
                # Calculate month boundaries
                current_date = datetime.now(timezone.utc)
                month_start = (current_date.replace(day=1) - timedelta(days=30 * i)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                
                query = """
                SELECT 
                    COUNT(*) as api_calls,
                    feature_type,
                    COUNT(*) as feature_calls,
                    AVG(response_time_ms) as avg_response_time,
                    SUM(request_size_bytes + response_size_bytes) as total_bytes
                FROM api_usage_audit_mt
                WHERE tenant_id = %(tenant_id)s 
                AND request_timestamp >= %(month_start)s
                AND request_timestamp < %(month_end)s
                GROUP BY feature_type
                """
                
                results = await self.db.fetch_all(query, {
                    "tenant_id": tenant_id,
                    "month_start": month_start,
                    "month_end": month_end
                })
                
                # Process monthly data
                feature_breakdown = {}
                total_calls = 0
                total_bytes = 0
                
                for row in results:
                    feature_type = row.get("feature_type", "unknown")
                    feature_calls = row.get("feature_calls", 0)
                    
                    feature_breakdown[feature_type] = feature_calls
                    total_calls += feature_calls
                    total_bytes += row.get("total_bytes", 0)
                
                month_data = {
                    "period": month_start.strftime("%Y-%m"),
                    "api_calls": total_calls,
                    "feature_breakdown": feature_breakdown,
                    "storage_bytes": total_bytes,
                    "period_start": month_start.isoformat(),
                    "period_end": month_end.isoformat()
                }
                
                history_data.append(month_data)
            
            # Sort by period descending (most recent first)
            history_data.sort(key=lambda x: x["period"], reverse=True)
            
            return history_data
            
        except Exception as e:
            logger.error(f"Failed to get usage history for tenant {tenant_id}: {e}")
            raise
    
    # Real-time Usage Queries
    
    async def get_realtime_usage(self, tenant_id: str, window_minutes: int = 60) -> Dict[str, Any]:
        """Get real-time usage metrics for tenant"""
        try:
            # Calculate time window
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=window_minutes)
            
            query = """
            SELECT 
                COUNT(*) as api_calls,
                AVG(response_time_ms) as avg_response_time,
                COUNT(CASE WHEN response_status >= 400 THEN 1 END) * 100.0 / COUNT(*) as error_rate,
                endpoint,
                COUNT(*) as endpoint_calls
            FROM api_usage_audit_mt
            WHERE tenant_id = %(tenant_id)s 
            AND request_timestamp >= %(start_time)s
            AND request_timestamp <= %(end_time)s
            GROUP BY endpoint
            ORDER BY endpoint_calls DESC
            LIMIT 10
            """
            
            params = {
                "tenant_id": tenant_id,
                "start_time": start_time,
                "end_time": end_time
            }
            
            results = await self.db.fetch_all(query, params)
            
            # Process results
            total_calls = sum(row.get("endpoint_calls", 0) for row in results)
            avg_response_time = results[0].get("avg_response_time", 0) if results else 0
            error_rate = results[0].get("error_rate", 0) if results else 0
            
            top_endpoints = [
                {
                    "endpoint": row.get("endpoint", ""),
                    "calls": row.get("endpoint_calls", 0),
                    "avg_time": row.get("avg_response_time", 0)
                }
                for row in results[:5]
            ]
            
            return {
                "tenant_id": tenant_id,
                "time_window": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                    "duration_minutes": window_minutes
                },
                "api_calls_count": total_calls,
                "avg_response_time_ms": round(avg_response_time, 2),
                "error_rate": round(error_rate, 2),
                "top_endpoints": top_endpoints
            }
            
        except Exception as e:
            logger.error(f"Failed to get realtime usage for tenant {tenant_id}: {e}")
            raise
    
    # Platform Analytics
    
    async def get_platform_usage_stats(self) -> Dict[str, Any]:
        """Get platform-wide usage statistics"""
        try:
            current_month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            query = """
            SELECT 
                COUNT(DISTINCT tenant_id) as active_tenants,
                COUNT(*) as total_api_calls,
                AVG(response_time_ms) as avg_response_time,
                COUNT(CASE WHEN response_status >= 400 THEN 1 END) as total_errors
            FROM api_usage_audit_mt
            WHERE request_timestamp >= %(current_month_start)s
            """
            
            result = await self.db.fetch_one(query, {"current_month_start": current_month_start})
            
            return {
                "active_tenants_this_month": result.get("active_tenants", 0),
                "total_api_calls_month": result.get("total_api_calls", 0),
                "avg_response_time_ms": round(result.get("avg_response_time", 0), 2),
                "total_errors": result.get("total_errors", 0),
                "calculated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get platform usage stats: {e}")
            raise
    
    async def get_top_consuming_tenants(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top consuming tenants by API calls"""
        try:
            current_month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            query = """
            SELECT 
                tenant_id,
                COUNT(*) as api_calls,
                AVG(response_time_ms) as avg_response_time
            FROM api_usage_audit_mt
            WHERE request_timestamp >= %(current_month_start)s
            GROUP BY tenant_id
            ORDER BY api_calls DESC
            LIMIT %(limit)s
            """
            
            results = await self.db.fetch_all(query, {
                "current_month_start": current_month_start,
                "limit": limit
            })
            
            return [
                {
                    "tenant_id": row.get("tenant_id"),
                    "api_calls": row.get("api_calls", 0),
                    "avg_response_time": round(row.get("avg_response_time", 0), 2)
                }
                for row in results
            ]
            
        except Exception as e:
            logger.error(f"Failed to get top consuming tenants: {e}")
            raise
    
    # Cost Calculation Methods
    
    async def calculate_tenant_cost(self, tenant_id: str, billing_period: Optional[str] = None) -> Dict[str, Any]:
        """Calculate billing cost for tenant"""
        try:
            # Use current month if no billing period specified
            if not billing_period:
                billing_period = datetime.now(timezone.utc).strftime("%Y-%m")
            
            # Parse billing period
            year, month = map(int, billing_period.split("-"))
            period_start = datetime(year, month, 1, tzinfo=timezone.utc)
            period_end = (period_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            # Get usage data for billing period
            query = """
            SELECT 
                feature_type,
                COUNT(*) as api_calls,
                SUM(request_size_bytes + response_size_bytes) as total_bytes
            FROM api_usage_audit_mt
            WHERE tenant_id = %(tenant_id)s 
            AND request_timestamp >= %(period_start)s
            AND request_timestamp < %(period_end)s
            GROUP BY feature_type
            """
            
            results = await self.db.fetch_all(query, {
                "tenant_id": tenant_id,
                "period_start": period_start,
                "period_end": period_end
            })
            
            # Simple cost calculation (would be more sophisticated in production)
            total_cost = 0.0
            cost_breakdown = {}
            
            # Basic pricing model
            pricing = {
                "ingestion": 0.001,  # $0.001 per API call
                "query": 0.002,      # $0.002 per query
                "storage": 0.0001,   # $0.0001 per MB
                "analytics": 0.003,  # $0.003 per analytics call
                "default": 0.001     # Default rate
            }
            
            for row in results:
                feature_type = row.get("feature_type", "default")
                api_calls = row.get("api_calls", 0)
                total_bytes = row.get("total_bytes", 0)
                
                # Calculate cost based on feature type
                rate = pricing.get(feature_type, pricing["default"])
                feature_cost = api_calls * rate
                
                # Add storage cost if applicable
                if total_bytes > 0:
                    storage_cost = (total_bytes / 1024 / 1024) * pricing["storage"]
                    feature_cost += storage_cost
                
                cost_breakdown[feature_type] = {
                    "api_calls": api_calls,
                    "total_bytes": total_bytes,
                    "cost": round(feature_cost, 4)
                }
                
                total_cost += feature_cost
            
            return {
                "tenant_id": tenant_id,
                "billing_period": billing_period,
                "total_cost": round(total_cost, 2),
                "cost_breakdown": cost_breakdown,
                "currency": "USD",
                "calculated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate cost for tenant {tenant_id}: {e}")
            raise