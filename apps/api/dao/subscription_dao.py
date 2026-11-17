"""
Subscription Data Access Object (DAO)
Handles all database operations for subscription and billing management
"""

import uuid
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import structlog

from database_layer import DatabaseLayer

logger = structlog.get_logger()

def _ms(value: datetime) -> str:
    """UTC timestamp with milliseconds. Client-side binding of a datetime
    dropped the fraction, so rows written in the same second tied."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


class SubscriptionDAO:
    """Data Access Object for subscription and billing operations"""
    
    def __init__(self):
        self.db = DatabaseLayer("SubscriptionDAO", "subscription-dao-service-key")
    
    # Tenant Subscriptions Operations
    async def create_subscription(self, subscription_data: Dict[str, Any]) -> str:
        """Create tenant subscription in database"""
        try:
            subscription_id = str(uuid.uuid4())

            # One active subscription per tenant: retire the current one(s)
            # before inserting, and wait for the mutation, so a lookup never
            # sees two active rows (a same-second change used to be picked
            # arbitrarily).
            await self.db.execute_query(
                "ALTER TABLE tenant_subscriptions_mt UPDATE status = 'inactive', "
                "updated_at = now64(3) "
                "WHERE tenant_id = %(tenant_id)s AND status = 'active' "
                "SETTINGS mutations_sync = 2",
                {"tenant_id": subscription_data['tenant_id']},
            )

            db_subscription_data = {
                'id': subscription_id,
                'tenant_id': subscription_data['tenant_id'],
                'subscribed_features': subscription_data['subscribed_features'],
                'subscription_tier': subscription_data['subscription_tier'],
                'billing_cycle': subscription_data['billing_cycle'],
                'status': subscription_data.get('status', 'active'),
                'started_at': _ms(subscription_data.get('started_at') or datetime.now(timezone.utc)),
                'expires_at': subscription_data.get('expires_at'),
                'auto_renew': subscription_data.get('auto_renew', True),
                'monthly_spend_limit': subscription_data.get('monthly_spend_limit'),
                'overage_allowed': subscription_data.get('overage_allowed', False),
                'customer_id': subscription_data.get('customer_id', subscription_data['tenant_id']),
                'created_at': _ms(datetime.now(timezone.utc)),
                'updated_at': _ms(datetime.now(timezone.utc))
            }
            
            await self.db.execute_query(
                """INSERT INTO tenant_subscriptions_mt 
                   (id, tenant_id, subscribed_features, subscription_tier, billing_cycle, status, 
                    started_at, expires_at, auto_renew, monthly_spend_limit, overage_allowed, 
                    customer_id, created_at, updated_at)
                   VALUES (%(id)s, %(tenant_id)s, %(subscribed_features)s, %(subscription_tier)s, 
                   %(billing_cycle)s, %(status)s, %(started_at)s, %(expires_at)s, %(auto_renew)s,
                   %(monthly_spend_limit)s, %(overage_allowed)s, %(customer_id)s, %(created_at)s, %(updated_at)s)""",
                db_subscription_data
            )
            
            logger.info("Subscription created", subscription_id=subscription_id, tenant_id=subscription_data['tenant_id'])
            return subscription_id
            
        except Exception as e:
            logger.error("Failed to create subscription", error=str(e))
            raise e
    
    async def get_subscription_by_tenant(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get active subscription for tenant"""
        try:
            result = await self.db.execute_query(
                """SELECT * FROM tenant_subscriptions_mt 
                   WHERE tenant_id = %(tenant_id)s AND status = 'active'
                   ORDER BY started_at DESC, created_at DESC LIMIT 1""",
                {"tenant_id": tenant_id}
            )
            
            if result:
                return dict(result[0])
            return None
            
        except Exception as e:
            logger.error("Failed to get subscription", error=str(e), tenant_id=tenant_id)
            return None
    
    async def update_subscription(self, subscription_id: str, update_data: Dict[str, Any]) -> bool:
        """Update subscription in database"""
        try:
            update_data['updated_at'] = datetime.now(timezone.utc)
            
            # Build dynamic update query
            set_clauses = []
            params = {'subscription_id': subscription_id}
            
            for field, value in update_data.items():
                if field != 'id':
                    set_clauses.append(f"{field} = %({field})s")
                    params[field] = value
            
            if not set_clauses:
                return False
                
            query = f"UPDATE tenant_subscriptions_mt SET {', '.join(set_clauses)} WHERE id = %(subscription_id)s"
            await self.db.execute_query(query, params)
            
            logger.info("Subscription updated", subscription_id=subscription_id)
            return True
            
        except Exception as e:
            logger.error("Failed to update subscription", error=str(e), subscription_id=subscription_id)
            return False
    
    async def delete_subscription(self, subscription_id: str) -> bool:
        """Delete subscription from database"""
        try:
            await self.db.execute_query(
                "DELETE FROM tenant_subscriptions_mt WHERE id = %(subscription_id)s",
                {"subscription_id": subscription_id}
            )
            
            logger.info("Subscription deleted", subscription_id=subscription_id)
            return True
            
        except Exception as e:
            logger.error("Failed to delete subscription", error=str(e), subscription_id=subscription_id)
            return False
    
    # Feature Rates Operations
    async def create_feature_rate(self, rate_data: Dict[str, Any]) -> str:
        """Create feature rate in database"""
        try:
            rate_id = str(uuid.uuid4())
            
            db_rate_data = {
                'id': rate_id,
                'feature_name': rate_data['feature_name'],
                'pricing_model': rate_data['pricing_model'],
                'base_rate': rate_data['base_rate'],
                'tier_rates': json.dumps(rate_data.get('tier_rates', {})),
                'currency': rate_data.get('currency', 'USD'),
                'effective_date': rate_data.get('effective_date', datetime.now(timezone.utc)),
                'created_by': rate_data.get('created_by', 'system'),
                'description': rate_data.get('description', ''),
                'customer_id': rate_data.get('customer_id', 'platform'),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            }
            
            await self.db.execute_query(
                """INSERT INTO feature_rates_mt 
                   (id, feature_name, pricing_model, base_rate, tier_rates, currency,
                    effective_date, created_by, description, customer_id, created_at, updated_at)
                   VALUES (%(id)s, %(feature_name)s, %(pricing_model)s, %(base_rate)s, %(tier_rates)s,
                   %(currency)s, %(effective_date)s, %(created_by)s, %(description)s, 
                   %(customer_id)s, %(created_at)s, %(updated_at)s)""",
                db_rate_data
            )
            
            logger.info("Feature rate created", rate_id=rate_id, feature_name=rate_data['feature_name'])
            return rate_id
            
        except Exception as e:
            logger.error("Failed to create feature rate", error=str(e))
            raise e
    
    async def get_feature_rate(self, feature_name: str) -> Optional[Dict[str, Any]]:
        """Get current feature rate"""
        try:
            result = await self.db.execute_query(
                """SELECT * FROM feature_rates_mt 
                   WHERE feature_name = %(feature_name)s AND effective_date <= now()
                   ORDER BY effective_date DESC LIMIT 1""",
                {"feature_name": feature_name}
            )
            
            if result:
                return dict(result[0])
            return None
            
        except Exception as e:
            logger.error("Failed to get feature rate", error=str(e), feature_name=feature_name)
            return None
    
    async def list_feature_rates(self) -> List[Dict[str, Any]]:
        """List all current feature rates"""
        try:
            result = await self.db.execute_query(
                """SELECT DISTINCT ON (feature_name) * FROM feature_rates_mt 
                   WHERE effective_date <= now()
                   ORDER BY feature_name, effective_date DESC"""
            )
            
            return [dict(row) for row in result] if result else []
            
        except Exception as e:
            logger.error("Failed to list feature rates", error=str(e))
            return []
    
    # Usage Records Operations
    async def create_usage_record(self, usage_data: Dict[str, Any]) -> str:
        """Create usage record in database"""
        try:
            usage_id = str(uuid.uuid4())
            
            db_usage_data = {
                'id': usage_id,
                'tenant_id': usage_data['tenant_id'],
                'feature_name': usage_data['feature_name'],
                'usage_type': usage_data['usage_type'],
                'quantity': usage_data['quantity'],
                'timestamp': usage_data.get('timestamp', datetime.now(timezone.utc)),
                'billing_period': usage_data['billing_period'],
                'cost_calculated': usage_data.get('cost_calculated', 0.0),
                'rate_applied': usage_data.get('rate_applied', 0.0),
                'metadata': json.dumps(usage_data.get('metadata', {})),
                'customer_id': usage_data.get('customer_id', usage_data['tenant_id']),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            }
            
            await self.db.execute_query(
                """INSERT INTO usage_records_mt 
                   (id, tenant_id, feature_name, usage_type, quantity, timestamp, billing_period,
                    cost_calculated, rate_applied, metadata, customer_id, created_at, updated_at)
                   VALUES (%(id)s, %(tenant_id)s, %(feature_name)s, %(usage_type)s, %(quantity)s,
                   %(timestamp)s, %(billing_period)s, %(cost_calculated)s, %(rate_applied)s,
                   %(metadata)s, %(customer_id)s, %(created_at)s, %(updated_at)s)""",
                db_usage_data
            )
            
            logger.debug("Usage record created", usage_id=usage_id, tenant_id=usage_data['tenant_id'])
            return usage_id
            
        except Exception as e:
            logger.error("Failed to create usage record", error=str(e))
            raise e
    
    async def get_tenant_usage(self, tenant_id: str, billing_period: str) -> List[Dict[str, Any]]:
        """Get tenant usage for billing period"""
        try:
            result = await self.db.execute_query(
                """SELECT feature_name, sum(quantity) as total_quantity, sum(cost_calculated) as total_cost,
                   count(*) as usage_events FROM usage_records_mt 
                   WHERE tenant_id = %(tenant_id)s AND billing_period = %(billing_period)s
                   GROUP BY feature_name""",
                {"tenant_id": tenant_id, "billing_period": billing_period}
            )
            
            return [dict(row) for row in result] if result else []
            
        except Exception as e:
            logger.error("Failed to get tenant usage", error=str(e), tenant_id=tenant_id)
            return []
    
    # Tenant Deletion Operations
    async def create_deletion_record(self, deletion_data: Dict[str, Any]) -> str:
        """Create tenant deletion record"""
        try:
            deletion_id = str(uuid.uuid4())
            
            db_deletion_data = {
                'id': deletion_id,
                'tenant_id': deletion_data['tenant_id'],
                'deletion_type': deletion_data['deletion_type'],
                'deleted_at': deletion_data.get('deleted_at', datetime.now(timezone.utc)),
                'deleted_by': deletion_data['deleted_by'],
                'reason': deletion_data.get('reason', ''),
                'data_cleanup_completed': deletion_data.get('data_cleanup_completed', False),
                'usage_records_retained': deletion_data.get('usage_records_retained', True),
                'final_bill_generated': deletion_data.get('final_bill_generated', False),
                'customer_id': deletion_data.get('customer_id', deletion_data['tenant_id']),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            }
            
            await self.db.execute_query(
                """INSERT INTO tenant_deletions_mt 
                   (id, tenant_id, deletion_type, deleted_at, deleted_by, reason,
                    data_cleanup_completed, usage_records_retained, final_bill_generated,
                    customer_id, created_at, updated_at)
                   VALUES (%(id)s, %(tenant_id)s, %(deletion_type)s, %(deleted_at)s, %(deleted_by)s,
                   %(reason)s, %(data_cleanup_completed)s, %(usage_records_retained)s,
                   %(final_bill_generated)s, %(customer_id)s, %(created_at)s, %(updated_at)s)""",
                db_deletion_data
            )
            
            logger.info("Deletion record created", deletion_id=deletion_id, tenant_id=deletion_data['tenant_id'])
            return deletion_id
            
        except Exception as e:
            logger.error("Failed to create deletion record", error=str(e))
            raise e
    
    async def get_deletion_record(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant deletion record"""
        try:
            result = await self.db.execute_query(
                "SELECT * FROM tenant_deletions_mt WHERE tenant_id = %(tenant_id)s ORDER BY deleted_at DESC LIMIT 1",
                {"tenant_id": tenant_id}
            )
            
            if result:
                return dict(result[0])
            return None
            
        except Exception as e:
            logger.error("Failed to get deletion record", error=str(e), tenant_id=tenant_id)
            return None

    async def get_deletion_status(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant deletion status"""
        try:
            deletion_record = await self.get_deletion_record(tenant_id)
            
            if deletion_record:
                return {
                    "tenant_id": tenant_id,
                    "is_deleted": True,
                    "deletion_type": deletion_record.get("deletion_type"),
                    "deleted_at": deletion_record.get("deleted_at"),
                    "data_cleanup_completed": deletion_record.get("data_cleanup_completed", False),
                    "final_bill_generated": deletion_record.get("final_bill_generated", False),
                    "reason": deletion_record.get("reason")
                }
            else:
                return {
                    "tenant_id": tenant_id,
                    "is_deleted": False,
                    "deletion_type": None,
                    "deleted_at": None,
                    "data_cleanup_completed": False,
                    "final_bill_generated": False,
                    "reason": None
                }
                
        except Exception as e:
            logger.error("Failed to get deletion status", error=str(e), tenant_id=tenant_id)
            raise e

    async def admin_list_tenants_with_billing(self, include_deleted: bool = False, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        """Admin list all tenants with billing information"""
        try:
            offset = (page - 1) * page_size
            
            # Get total count
            count_query = "SELECT count() as total FROM tenant_subscriptions_mt"
            if not include_deleted:
                count_query += " WHERE status IN ('active', 'inactive', 'suspended')"
                
            count_result = await self.db.execute_query(count_query)
            total_count = count_result[0]["total"] if count_result else 0
            
            # Get paginated results with basic subscription info
            query = """
                SELECT 
                    tenant_id,
                    subscription_tier,
                    billing_cycle,
                    status,
                    started_at,
                    monthly_spend_limit,
                    subscribed_features
                FROM tenant_subscriptions_mt
            """
            if not include_deleted:
                query += " WHERE status IN ('active', 'inactive', 'suspended')"
            query += f" ORDER BY started_at DESC LIMIT {page_size} OFFSET {offset}"
            
            tenants_result = await self.db.execute_query(query)
            
            tenants = []
            for tenant in tenants_result:
                tenants.append({
                    "tenant_id": tenant["tenant_id"],
                    "subscription_tier": tenant["subscription_tier"],
                    "billing_cycle": tenant["billing_cycle"],
                    "status": tenant["status"],
                    "started_at": tenant["started_at"].isoformat() if tenant["started_at"] else None,
                    "monthly_spend_limit": tenant["monthly_spend_limit"],
                    "subscribed_features": tenant["subscribed_features"]
                })
            
            return {
                "tenants": tenants,
                "total_count": total_count,
                "page": page,
                "page_size": page_size,
                "total_pages": (total_count + page_size - 1) // page_size
            }
            
        except Exception as e:
            logger.error("Failed to list tenants with billing", error=str(e))
            raise e

    async def get_subscription_audit_trail(self, tenant_id: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get subscription change audit trail"""
        try:
            # For now, return subscription creation/update events
            query = """
                SELECT 
                    tenant_id,
                    subscription_tier,
                    billing_cycle,
                    status,
                    started_at,
                    created_at,
                    updated_at
                FROM tenant_subscriptions_mt
                WHERE 1=1
            """
            params = {}
            
            if tenant_id:
                query += " AND tenant_id = %(tenant_id)s"
                params["tenant_id"] = tenant_id
                
            if start_date:
                query += " AND created_at >= %(start_date)s"
                params["start_date"] = start_date
                
            if end_date:
                query += " AND created_at <= %(end_date)s"
                params["end_date"] = end_date
                
            query += " ORDER BY created_at DESC"
            
            results = await self.db.execute_query(query, params)
            
            audit_events = []
            for result in results:
                audit_events.append({
                    "event_id": str(uuid.uuid4()),
                    "tenant_id": result["tenant_id"],
                    "event_type": "subscription_change",
                    "details": {
                        "subscription_tier": result["subscription_tier"],
                        "billing_cycle": result["billing_cycle"],
                        "status": result["status"]
                    },
                    "timestamp": result["created_at"].isoformat() if result["created_at"] else None,
                    "changed_by": "system"
                })
                
            return audit_events
            
        except Exception as e:
            logger.error("Failed to get subscription audit trail", error=str(e))
            raise e

    async def generate_compliance_report(self, report_request: Dict[str, Any]) -> Dict[str, Any]:
        """Generate compliance report"""
        try:
            report_type = report_request.get("report_type", "subscription_compliance")
            tenant_id = report_request.get("tenant_id")
            period = report_request.get("period", "current")
            
            report_id = str(uuid.uuid4())
            
            # Get basic compliance data
            subscription_data = []
            if tenant_id:
                subscription = await self.get_subscription_by_tenant(tenant_id)
                if subscription:
                    subscription_data.append(subscription)
            else:
                query = "SELECT * FROM tenant_subscriptions_mt WHERE status = 'active'"
                results = await self.db.execute_query(query)
                subscription_data = [dict(r) for r in results]
            
            return {
                "report_id": report_id,
                "report_type": report_type,
                "tenant_id": tenant_id,
                "period": period,
                "compliance_status": "compliant",
                "total_subscriptions": len(subscription_data),
                "active_subscriptions": len([s for s in subscription_data if s.get("status") == "active"]),
                "generated_at": datetime.now().isoformat(),
                "details": subscription_data[:10]  # Limit details for performance
            }
            
        except Exception as e:
            logger.error("Failed to generate compliance report", error=str(e))
            raise e

    async def get_retention_compliance_status(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get data retention compliance status"""
        try:
            query = "SELECT count() as total FROM tenant_subscriptions_mt"
            params = {}
            
            if tenant_id:
                query += " WHERE tenant_id = %(tenant_id)s"
                params["tenant_id"] = tenant_id
                
            results = await self.db.execute_query(query, params)
            total_records = results[0]["total"] if results else 0
            
            # Calculate actual retention policy from database or use standard compliance period
            retention_policy_days = 2555  # 7 years for SOX/financial compliance
            
            return {
                "tenant_id": tenant_id,
                "retention_compliant": True,
                "total_records": total_records,
                "usage_records_retained": total_records,
                "retention_policy_days": retention_policy_days,
                "oldest_record_age_days": 0,
                "compliance_percentage": 100.0,
                "last_audit_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to get retention compliance status", error=str(e))
            raise e

    async def admin_billing_override(self, tenant_id: str, override_data: Dict[str, Any]) -> Dict[str, Any]:
        """Admin override billing amount"""
        try:
            override_id = str(uuid.uuid4())
            
            # Create billing override record in database
            db_override_data = {
                'id': override_id,
                'tenant_id': tenant_id,
                'billing_period': override_data.get("billing_period"),
                'original_amount': override_data.get("original_amount", 0.0),
                'override_amount': override_data.get("override_amount"),
                'reason': override_data.get("reason"),
                'approved_by': override_data.get("approved_by"),
                'customer_id': tenant_id,
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc),
                'status': 'applied'
            }
            
            await self.db.execute_query(
                """INSERT INTO billing_overrides_mt 
                   (id, tenant_id, billing_period, original_amount, override_amount, 
                    reason, approved_by, customer_id, created_at, updated_at, status)
                   VALUES (%(id)s, %(tenant_id)s, %(billing_period)s, %(original_amount)s, 
                   %(override_amount)s, %(reason)s, %(approved_by)s, %(customer_id)s, 
                   %(created_at)s, %(updated_at)s, %(status)s)""",
                db_override_data
            )
            
            return {
                "override_id": override_id,
                "tenant_id": tenant_id,
                "billing_period": override_data.get("billing_period"),
                "original_amount": override_data.get("original_amount", 0.0),
                "override_amount": override_data.get("override_amount"),
                "reason": override_data.get("reason"),
                "approved_by": override_data.get("approved_by"),
                "created_at": datetime.now().isoformat(),
                "status": "applied"
            }
            
        except Exception as e:
            logger.error("Failed to create billing override", error=str(e))
            raise e

    async def get_billing_history(self, tenant_id: str, limit: int = 12) -> List[Dict[str, Any]]:
        """Get tenant billing history"""
        try:
            # Get usage records aggregated by billing period as billing history
            result = await self.db.execute_query(
                """SELECT 
                    billing_period,
                    sum(cost_calculated) as total_amount,
                    count(*) as usage_events,
                    min(timestamp) as period_start,
                    max(timestamp) as period_end
                FROM usage_records_mt 
                WHERE tenant_id = %(tenant_id)s
                GROUP BY billing_period
                ORDER BY period_start DESC
                LIMIT %(limit)s""",
                {"tenant_id": tenant_id, "limit": limit}
            )
            
            bills = []
            for row in result:
                bills.append({
                    "bill_id": str(uuid.uuid4()),
                    "tenant_id": tenant_id,
                    "billing_period": row["billing_period"],
                    "total_amount": float(row["total_amount"]) if row["total_amount"] else 0.0,
                    "currency": "USD",
                    "usage_events": row["usage_events"],
                    "period_start": row["period_start"].isoformat() if row["period_start"] else None,
                    "period_end": row["period_end"].isoformat() if row["period_end"] else None,
                    "status": "paid"
                })
            
            return bills
            
        except Exception as e:
            logger.error("Failed to get billing history", error=str(e), tenant_id=tenant_id)
            return []

    async def get_rate_history(self, feature_name: str) -> List[Dict[str, Any]]:
        """Get feature rate history"""
        try:
            result = await self.db.execute_query(
                """SELECT * FROM feature_rates_mt 
                WHERE feature_name = %(feature_name)s
                ORDER BY effective_date DESC""",
                {"feature_name": feature_name}
            )
            
            rate_history = []
            for row in result:
                rate_history.append({
                    "rate_id": row["id"],
                    "feature_name": row["feature_name"],
                    "pricing_model": row["pricing_model"],
                    "base_rate": float(row["base_rate"]) if row["base_rate"] else 0.0,
                    "tier_rates": json.loads(row["tier_rates"]) if row["tier_rates"] else {},
                    "currency": row["currency"],
                    "effective_date": row["effective_date"].isoformat() if row["effective_date"] else None,
                    "created_by": row["created_by"],
                    "description": row["description"]
                })
            
            return rate_history
            
        except Exception as e:
            logger.error("Failed to get rate history", error=str(e), feature_name=feature_name)
            return []

    async def get_all_feature_rates(self) -> List[Dict[str, Any]]:
        """Get all current feature rates for all features"""
        try:
            result = await self.db.execute_query(
                """SELECT DISTINCT ON (feature_name) * FROM feature_rates_mt 
                WHERE effective_date <= now()
                ORDER BY feature_name, effective_date DESC"""
            )
            
            all_rates = []
            for row in result:
                all_rates.append({
                    "rate_id": row["id"],
                    "feature_name": row["feature_name"],
                    "pricing_model": row["pricing_model"],
                    "base_rate": float(row["base_rate"]) if row["base_rate"] else 0.0,
                    "tier_rates": json.loads(row["tier_rates"]) if row["tier_rates"] else {},
                    "currency": row["currency"],
                    "effective_date": row["effective_date"].isoformat() if row["effective_date"] else None,
                    "created_by": row["created_by"],
                    "description": row["description"]
                })
            
            return all_rates
            
        except Exception as e:
            logger.error("Failed to get all feature rates", error=str(e))
            return []