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

    def __init__(self, service_name=None, service_key=None):
        # Allow service-to-service calls with specific credentials
        if service_name and service_key:
            self.db = DatabaseLayer(service_name, service_key)
        else:
            self.db = DatabaseLayer("UsageDAO", "usage-dao-service-key")

    # Bills Management Operations

    async def get_existing_bill(self, tenant_id: str, billing_period: str) -> Optional[Dict[str, Any]]:
        """Check if bill already exists for tenant and period (idempotent check)"""
        try:
            query = """
            SELECT * FROM tenant_bills_mt 
            WHERE tenant_id = %(tenant_id)s AND billing_period = %(billing_period)s
            ORDER BY generated_at DESC LIMIT 1
            """
            
            result = await self.db.execute_query(
                query,
                {"tenant_id": tenant_id, "billing_period": billing_period}
            )
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error("Failed to check existing bill", error=str(e), tenant_id=tenant_id)
            raise Exception(f"Failed to check existing bill: {str(e)}")

    async def create_bill(self, bill_data: Dict[str, Any]) -> str:
        """Create a new bill record in database"""
        try:
            bill_id = bill_data.get("id", str(uuid.uuid4()))
            
            query = """
            INSERT INTO tenant_bills_mt (
                id, tenant_id, billing_period, subscription_tier,
                base_fee, usage_charges, tier_discount, promo_discount,
                subtotal, total_amount, currency, status,
                usage_breakdown, promo_code, generated_at,
                due_date, customer_id
            ) VALUES (
                %(id)s, %(tenant_id)s, %(billing_period)s, %(subscription_tier)s,
                %(base_fee)s, %(usage_charges)s, %(tier_discount)s, %(promo_discount)s,
                %(subtotal)s, %(total_amount)s, %(currency)s, %(status)s,
                %(usage_breakdown)s, %(promo_code)s, %(generated_at)s,
                %(due_date)s, %(customer_id)s
            )
            """
            
            await self.db.execute_query(query, {
                "id": bill_id,
                "tenant_id": bill_data["tenant_id"],
                "billing_period": bill_data["billing_period"],
                "subscription_tier": bill_data["subscription_tier"],
                "base_fee": bill_data["base_fee"],
                "usage_charges": bill_data["usage_charges"],
                "tier_discount": bill_data.get("tier_discount", 0.0),
                "promo_discount": bill_data.get("promo_discount", 0.0),
                "subtotal": bill_data["subtotal"],
                "total_amount": bill_data["total_amount"],
                "currency": bill_data.get("currency", "USD"),
                "status": bill_data.get("status", "generated"),
                "usage_breakdown": json.dumps(bill_data.get("usage_breakdown", [])),
                "promo_code": bill_data.get("promo_code"),
                "generated_at": bill_data["generated_at"],
                "due_date": bill_data["due_date"],
                "customer_id": bill_data["tenant_id"]  # For multi-tenant isolation
            })
            
            logger.info("Bill created successfully", bill_id=bill_id, tenant_id=bill_data["tenant_id"])
            return bill_id
            
        except Exception as e:
            logger.error("Failed to create bill", error=str(e), tenant_id=bill_data.get("tenant_id"))
            raise Exception(f"Failed to create bill: {str(e)}")

    async def get_tenant_bills(self, tenant_id: str, limit: int = 12) -> List[Dict[str, Any]]:
        """Get billing history for tenant"""
        try:
            query = """
            SELECT * FROM tenant_bills_mt 
            WHERE tenant_id = %(tenant_id)s 
            ORDER BY generated_at DESC 
            LIMIT %(limit)s
            """
            
            bills = await self.db.execute_query(
                query,
                {"tenant_id": tenant_id, "limit": limit}
            )
            
            # Parse usage_breakdown JSON
            for bill in bills:
                if bill.get("usage_breakdown"):
                    try:
                        bill["usage_breakdown"] = json.loads(bill["usage_breakdown"])
                    except (json.JSONDecodeError, TypeError):
                        bill["usage_breakdown"] = []
            
            return bills
            
        except Exception as e:
            logger.error("Failed to get tenant bills", error=str(e), tenant_id=tenant_id)
            raise Exception(f"Failed to get tenant bills: {str(e)}")

    async def update_bill_status(self, bill_id: str, status: str) -> bool:
        """Update bill payment status"""
        try:
            query = """
            ALTER TABLE tenant_bills_mt 
            UPDATE status = %(status)s
            WHERE id = %(bill_id)s
            """
            
            await self.db.execute_query(query, {
                "bill_id": bill_id,
                "status": status
            })
            
            logger.info("Bill status updated", bill_id=bill_id, status=status)
            return True
            
        except Exception as e:
            logger.error("Failed to update bill status", error=str(e), bill_id=bill_id)
            raise Exception(f"Failed to update bill status: {str(e)}")

    # Usage Analytics for Billing
    
    async def get_monthly_usage_stats(self, tenant_id: str, year: int, month: int) -> Dict[str, Any]:
        """Get aggregated usage statistics for a specific month"""
        try:
            # Calculate month boundaries
            start_date = datetime(year, month, 1, tzinfo=timezone.utc)
            if month == 12:
                end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
            
            # Query API usage for the month
            api_usage_query = """
            SELECT 
                count(*) as total_api_calls,
                sum(request_size_bytes) as total_request_bytes,
                sum(response_size_bytes) as total_response_bytes,
                countDistinct(endpoint) as unique_endpoints
            FROM api_usage_audit_mt 
            WHERE tenant_id = %(tenant_id)s 
            AND request_timestamp >= %(start_date)s 
            AND request_timestamp < %(end_date)s
            """
            
            api_results = await self.db.execute_query(api_usage_query, {
                "tenant_id": tenant_id,
                "start_date": start_date,
                "end_date": end_date
            })
            
            # Query log ingestion data (if you have a logs table)
            ingestion_query = """
            SELECT 
                count(*) as total_logs,
                sum(size_bytes) as total_ingestion_bytes
            FROM logs_raw_mt 
            WHERE customer_id = %(tenant_id)s 
            AND timestamp >= %(start_date)s 
            AND timestamp < %(end_date)s
            """
            
            try:
                ingestion_results = await self.db.execute_query(ingestion_query, {
                    "tenant_id": tenant_id,
                    "start_date": start_date,
                    "end_date": end_date
                })
            except Exception:
                # If logs table doesn't exist or no ingestion data
                ingestion_results = [{"total_logs": 0, "total_ingestion_bytes": 0}]
            
            # Query storage usage (current storage size)
            storage_query = """
            SELECT 
                sum(size_bytes) as current_storage_bytes
            FROM logs_raw_mt 
            WHERE customer_id = %(tenant_id)s
            """
            
            try:
                storage_results = await self.db.execute_query(storage_query, {
                    "tenant_id": tenant_id
                })
            except Exception:
                storage_results = [{"current_storage_bytes": 0}]
            
            # Calculate usage metrics
            api_data = api_results[0] if api_results else {}
            ingestion_data = ingestion_results[0] if ingestion_results else {}
            storage_data = storage_results[0] if storage_results else {}
            
            usage_stats = {
                "tenant_id": tenant_id,
                "billing_period": f"{year}-{month:02d}",
                "api_calls": api_data.get("total_api_calls", 0),
                "ingestion_gb": round((ingestion_data.get("total_ingestion_bytes", 0) or 0) / (1024**3), 3),
                "storage_gb": round((storage_data.get("current_storage_bytes", 0) or 0) / (1024**3), 3),
                "query_count": api_data.get("total_api_calls", 0),  # Approximate queries as API calls
                "unique_endpoints": api_data.get("unique_endpoints", 0),
                "request_size_gb": round((api_data.get("total_request_bytes", 0) or 0) / (1024**3), 3),
                "response_size_gb": round((api_data.get("total_response_bytes", 0) or 0) / (1024**3), 3)
            }
            
            logger.info("Monthly usage stats calculated", 
                       tenant_id=tenant_id, 
                       period=f"{year}-{month:02d}",
                       api_calls=usage_stats["api_calls"],
                       ingestion_gb=usage_stats["ingestion_gb"])
            
            return usage_stats
            
        except Exception as e:
            logger.error("Failed to get monthly usage stats", error=str(e), tenant_id=tenant_id)
            raise Exception(f"Failed to get monthly usage stats: {str(e)}")

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
                if(count(*) > 0 AND count(response_time_ms) > 0, AVG(response_time_ms), 0) as avg_response_time,
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

            logger.info("🔍 STEP 9: Executing database query", tenant_id=tenant_id, query=query[:100], params=params)
            results = await self.db.fetch_all(query, params)
            logger.info("🔍 STEP 9 SUCCESS: Database query completed", tenant_id=tenant_id, result_count=len(results), results=results)

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
                    if(count(*) > 0 AND count(response_time_ms) > 0, AVG(response_time_ms), 0) as avg_response_time,
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
                if(count(*) > 0 AND count(response_time_ms) > 0, AVG(response_time_ms), 0) as avg_response_time,
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

    async def get_status_breakdown(self, tenant_id: str, window_minutes: int = 60) -> Dict[str, int]:
        """Get HTTP status code breakdown for tenant within time window"""
        try:
            # Calculate time window
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=window_minutes)

            query = """
            SELECT
                CASE 
                    WHEN response_status BETWEEN 200 AND 299 THEN '2xx'
                    WHEN response_status BETWEEN 400 AND 499 THEN '4xx'
                    WHEN response_status BETWEEN 500 AND 599 THEN '5xx'
                    ELSE 'other'
                END as status_category,
                COUNT(*) as count
            FROM api_usage_audit_mt
            WHERE tenant_id = %(tenant_id)s
            AND request_timestamp >= %(start_time)s
            AND request_timestamp <= %(end_time)s
            GROUP BY status_category
            """

            params = {
                "tenant_id": tenant_id,
                "start_time": start_time,
                "end_time": end_time
            }

            results = await self.db.fetch_all(query, params)

            # Initialize all status categories with 0
            status_breakdown = {"2xx": 0, "4xx": 0, "5xx": 0}
            
            # Fill in actual counts
            for row in results:
                category = row.get("status_category")
                if category in status_breakdown:
                    status_breakdown[category] = row.get("count", 0)

            return status_breakdown

        except Exception as e:
            logger.error(f"Failed to get status breakdown for tenant {tenant_id}: {e}")
            raise

    # Platform Analytics

    async def get_platform_usage_stats(self) -> Dict[str, Any]:
        """Get platform-wide usage statistics"""
        try:
            current_month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            logger.debug(f"Getting platform usage stats from: {current_month_start}")

            query = """
            SELECT
                COUNT(DISTINCT tenant_id) as active_tenants,
                COUNT(*) as total_api_calls,
                if(count(*) > 0 AND count(response_time_ms) > 0, AVG(response_time_ms), 0) as avg_response_time,
                COUNT(CASE WHEN response_status >= 400 THEN 1 END) as total_errors
            FROM api_usage_audit_mt
            WHERE request_timestamp >= %(current_month_start)s
            """

            logger.debug(f"Executing query: {query}")
            logger.debug(f"Query params: {{'current_month_start': {current_month_start}}}")

            result = await self.db.fetch_one(query, {"current_month_start": current_month_start})
            logger.debug(f"Raw query result: {result}")

            if not result:
                logger.warning("No result returned from platform usage stats query")
                return {
                    "active_tenants_this_month": 0,
                    "total_api_calls_month": 0,
                    "avg_response_time_ms": 0.0,
                    "total_errors": 0,
                    "calculated_at": datetime.now(timezone.utc).isoformat()
                }

            final_result = {
                "active_tenants_this_month": result.get("active_tenants", 0),
                "total_api_calls_month": result.get("total_api_calls", 0),
                "avg_response_time_ms": round(result.get("avg_response_time", 0), 2),
                "total_errors": result.get("total_errors", 0),
                "calculated_at": datetime.now(timezone.utc).isoformat()
            }

            logger.debug(f"Final platform stats result: {final_result}")
            return final_result

        except Exception as e:
            logger.error(f"Failed to get platform usage stats: {e}", exc_info=True)
            raise

    async def get_top_consuming_tenants(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top consuming tenants by API calls"""
        try:
            current_month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            query = """
            SELECT
                tenant_id,
                COUNT(*) as api_calls,
                if(count(*) > 0 AND count(response_time_ms) > 0, AVG(response_time_ms), 0) as avg_response_time
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

    # Platform Analytics Methods

    async def calculate_growth_metrics(self) -> Dict[str, Any]:
        """Calculate platform growth metrics from historical data"""
        # Get current month and previous month statistics
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        previous_month = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m")

        # Query for current month stats
        current_query = """
        SELECT
            COUNT(DISTINCT tenant_id) as active_tenants,
            COUNT(*) as total_api_calls,
            SUM(request_size_bytes + response_size_bytes) as total_bytes
        FROM api_usage_audit_mt
        WHERE toYYYYMM(request_timestamp) = toUInt32(replace(%(month)s, '-', ''))
        """

        current_result = await self.db.fetch_one(current_query, {"month": current_month})
        previous_result = await self.db.fetch_one(current_query, {"month": previous_month})

        # Calculate growth rates
        current_calls = current_result.get("total_api_calls", 0) if current_result else 0
        previous_calls = previous_result.get("total_api_calls", 0) if previous_result else 0

        if previous_calls > 0:
            month_growth = ((current_calls - previous_calls) / previous_calls) * 100
        else:
            month_growth = 100.0 if current_calls > 0 else 0.0

        # Get year-over-year data
        year_ago_month = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m")
        year_ago_result = await self.db.fetch_one(current_query, {"month": year_ago_month})

        year_ago_calls = year_ago_result.get("total_api_calls", 0) if year_ago_result else 0
        if year_ago_calls > 0:
            year_growth = ((current_calls - year_ago_calls) / year_ago_calls) * 100
        else:
            year_growth = 100.0 if current_calls > 0 else 0.0

        return {
            "month_over_month_growth": round(month_growth, 2),
            "year_over_year_growth": round(year_growth, 2),
            "current_month_stats": {
                "active_tenants": current_result.get("active_tenants", 0) if current_result else 0,
                "total_api_calls": current_calls,
                "total_bytes": current_result.get("total_bytes", 0) if current_result else 0
            }
        }

    async def calculate_feature_adoption(self) -> Dict[str, float]:
        """Calculate feature adoption rates across the platform"""
        # Get total tenants
        total_tenants_query = "SELECT COUNT(DISTINCT tenant_id) as tenant_count FROM api_usage_audit_mt"
        total_tenants_result = await self.db.fetch_one(total_tenants_query)
        total_tenants = total_tenants_result.get("tenant_count", 0) if total_tenants_result else 1

        # Get feature usage by tenant
        feature_query = """
        SELECT
            feature_type,
            COUNT(DISTINCT tenant_id) as tenant_count
        FROM api_usage_audit_mt
        WHERE request_timestamp >= now() - INTERVAL 30 DAY
        GROUP BY feature_type
        """

        feature_results = await self.db.fetch_all(feature_query)

        adoption_rates = {}
        for row in feature_results:
            feature_type = row.get("feature_type", "unknown")
            tenant_count = row.get("tenant_count", 0)
            adoption_rate = (tenant_count / total_tenants) * 100
            adoption_rates[feature_type] = round(adoption_rate, 1)

        return adoption_rates

    async def get_total_tenant_count(self) -> int:
        """Get total number of tenants from platform data"""
        # Try to get from tenants table first
        tenants_query = "SELECT COUNT(*) as count FROM tenants_mt"
        try:
            result = await self.db.fetch_one(tenants_query)
            if result and result.get("count", 0):
                return result.get("count", 0)
        except:
            # Table might not exist, fall back to usage data
            pass

        # Fall back to counting unique tenants from usage data
        usage_query = "SELECT COUNT(DISTINCT tenant_id) as count FROM api_usage_audit_mt"
        result = await self.db.fetch_one(usage_query)

        return result.get("count", 0) if result else 0

    # Additional utility methods for usage service

    async def get_current_cost_per_gb(self) -> float:
        """Get current cost per GB from pricing configuration table"""
        try:
            query = """
            SELECT base_rate 
            FROM feature_rates_mt 
            WHERE feature_name = 'storage.cost_per_gb' 
            AND effective_date <= now() 
            ORDER BY effective_date DESC 
            LIMIT 1
            """
            
            result = await self.db.fetch_one(query)
            if not result:
                raise Exception("No cost per GB rate found in feature_rates_mt table")
                
            return float(result.get("base_rate", 0))
            
        except Exception as e:
            logger.error(f"Failed to get cost per GB from database: {e}")
            raise

    async def get_partition_record_count(self, partition_name: str) -> int:
        """Get actual record count for a database partition"""
        try:
            query = """
            SELECT count() as record_count 
            FROM api_usage_audit_mt 
            WHERE toYYYYMM(request_timestamp) = %(partition_month)s
            """
            
            # Extract month from partition name (e.g., "p202409" -> 202409)
            partition_month = partition_name.replace("p", "") if partition_name.startswith("p") else partition_name
            
            result = await self.db.fetch_one(query, {"partition_month": int(partition_month)})
            return result.get("record_count", 0) if result else 0
            
        except Exception as e:
            logger.error(f"Failed to get partition record count for {partition_name}: {e}")
            raise

    async def get_partition_size_mb(self, partition_name: str) -> float:
        """Get actual size in MB for a database partition"""
        try:
            query = """
            SELECT 
                sum(request_size_bytes + response_size_bytes) as total_bytes
            FROM api_usage_audit_mt 
            WHERE toYYYYMM(request_timestamp) = %(partition_month)s
            """
            
            # Extract month from partition name (e.g., "p202409" -> 202409)
            partition_month = partition_name.replace("p", "") if partition_name.startswith("p") else partition_name
            
            result = await self.db.fetch_one(query, {"partition_month": int(partition_month)})
            total_bytes = result.get("total_bytes", 0) if result else 0
            
            # Convert bytes to MB
            return round(total_bytes / (1024 * 1024), 2)
            
        except Exception as e:
            logger.error(f"Failed to get partition size for {partition_name}: {e}")
            raise

    async def create_invoice_record(self, invoice_data: Dict[str, Any]) -> str:
        """Create invoice record in tenant_bills_mt table"""
        try:
            query = """
            INSERT INTO tenant_bills_mt (
                id, tenant_id, billing_period, subscription_tier, base_fee, usage_charges,
                tier_discount, promo_discount, subtotal, total_amount, currency, status,
                usage_breakdown, promo_code, generated_at, due_date, paid_at, customer_id
            ) VALUES (
                %(id)s, %(tenant_id)s, %(billing_period)s, %(subscription_tier)s, %(base_fee)s, %(usage_charges)s,
                %(tier_discount)s, %(promo_discount)s, %(subtotal)s, %(total_amount)s, %(currency)s, %(status)s,
                %(usage_breakdown)s, %(promo_code)s, %(generated_at)s, %(due_date)s, %(paid_at)s, %(customer_id)s
            )
            """
            
            await self.db.execute_query(query, invoice_data)
            return invoice_data["id"]
            
        except Exception as e:
            logger.error(f"Failed to create invoice record: {e}")
            raise
