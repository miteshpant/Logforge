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

class SubscriptionDAO:
    """Data Access Object for subscription and billing operations"""
    
    def __init__(self):
        self.db = DatabaseLayer("SubscriptionDAO", "subscription-dao-service-key")
    
    # Tenant Subscriptions Operations
    async def create_subscription(self, subscription_data: Dict[str, Any]) -> str:
        """Create tenant subscription in database"""
        try:
            subscription_id = str(uuid.uuid4())
            
            db_subscription_data = {
                'id': subscription_id,
                'tenant_id': subscription_data['tenant_id'],
                'subscribed_features': subscription_data['subscribed_features'],
                'subscription_tier': subscription_data['subscription_tier'],
                'billing_cycle': subscription_data['billing_cycle'],
                'status': subscription_data.get('status', 'active'),
                'started_at': subscription_data.get('started_at', datetime.now(timezone.utc)),
                'expires_at': subscription_data.get('expires_at'),
                'auto_renew': subscription_data.get('auto_renew', True),
                'monthly_spend_limit': subscription_data.get('monthly_spend_limit'),
                'overage_allowed': subscription_data.get('overage_allowed', False),
                'customer_id': subscription_data.get('customer_id', subscription_data['tenant_id']),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
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
                   ORDER BY started_at DESC LIMIT 1""",
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