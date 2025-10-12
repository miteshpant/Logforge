"""
Quota Reset Service - Automated quota management with configurable reset periods
Handles automated quota resets based on environment configuration
"""

import structlog
import asyncio
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from enum import Enum

from dao.tenant_dao import TenantDAO
from dao.subscription_dao import SubscriptionDAO
from database_layer import DatabaseLayer

logger = structlog.get_logger(__name__)

class QuotaType(Enum):
    """Quota types matching database enum"""
    DAILY_INGESTION = 1
    MONTHLY_INGESTION = 2
    STORAGE_GB = 3
    API_CALLS = 4
    USERS = 5
    ALERTS = 6

class QuotaResetService:
    """Service for automated quota reset management"""
    
    def __init__(self):
        self.db = DatabaseLayer("QuotaResetService", "quota-reset-service-key")
        self.tenant_dao = TenantDAO()
        self.subscription_dao = SubscriptionDAO()
        
        # Load configuration from environment variables
        self.reset_config = self._load_reset_configuration()
        logger.info("Quota reset service initialized", config=self.reset_config)
    
    def _load_reset_configuration(self) -> Dict[str, int]:
        """Load quota reset configuration from environment variables"""
        default_config = {
            'daily_ingestion': 1,     # Reset every 1 day
            'monthly_ingestion': 30,  # Reset every 30 days
            'storage_gb': 0,          # Never reset (0 = disabled)
            'api_calls': 30,          # Reset every 30 days
            'users': 0,               # Never reset (quota grows with subscription)
            'alerts': 30              # Reset every 30 days
        }
        
        config = {}
        for quota_type, default_days in default_config.items():
            env_key = f"QUOTA_RESET_{quota_type.upper()}_DAYS"
            config[quota_type] = int(os.getenv(env_key, default_days))
            
        logger.info("Loaded quota reset configuration", config=config)
        return config
    
    async def check_and_reset_quotas(self) -> Dict[str, Any]:
        """Check all quotas and reset those due for reset"""
        try:
            reset_summary = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'quotas_checked': 0,
                'quotas_reset': 0,
                'tenants_affected': [],
                'errors': []
            }
            
            # Get all quotas that need checking
            quotas_due = await self._get_quotas_due_for_reset()
            reset_summary['quotas_checked'] = len(quotas_due)
            
            logger.info("Starting quota reset check", quotas_found=len(quotas_due))
            
            for quota in quotas_due:
                try:
                    # Store current usage in historical table before reset
                    await self._store_historical_usage(quota)
                    
                    # Reset the quota
                    await self._reset_quota(quota)
                    
                    reset_summary['quotas_reset'] += 1
                    if quota['tenant_id'] not in reset_summary['tenants_affected']:
                        reset_summary['tenants_affected'].append(quota['tenant_id'])
                    
                    logger.info("Successfully reset quota", 
                              tenant_id=quota['tenant_id'], 
                              quota_type=quota['quota_type'])
                    
                except Exception as e:
                    error_msg = f"Failed to reset quota for tenant {quota['tenant_id']}, type {quota['quota_type']}: {str(e)}"
                    reset_summary['errors'].append(error_msg)
                    logger.error("Quota reset failed", 
                               tenant_id=quota['tenant_id'], 
                               quota_type=quota['quota_type'], 
                               error=str(e))
            
            logger.info("Quota reset check completed", summary=reset_summary)
            return reset_summary
            
        except Exception as e:
            logger.error("Quota reset service failed", error=str(e))
            raise Exception(f"Quota reset service failed: {str(e)}")
    
    async def _get_quotas_due_for_reset(self) -> List[Dict[str, Any]]:
        """Get all quotas that are due for reset based on configuration"""
        try:
            quotas_due = []
            current_time = datetime.now(timezone.utc)
            
            for quota_type, reset_days in self.reset_config.items():
                if reset_days <= 0:
                    continue  # Skip disabled quota types
                
                # Convert quota_type name to database enum value
                db_quota_type = self._get_db_quota_type(quota_type)
                if not db_quota_type:
                    continue
                
                # Calculate cutoff time for this quota type
                cutoff_time = current_time - timedelta(days=reset_days)
                
                # Query quotas that haven't been reset since cutoff
                query = """
                SELECT 
                    id, tenant_id, quota_type, quota_limit, current_usage, 
                    last_reset, customer_id, created_at, updated_at
                FROM tenant_quotas_mt 
                WHERE quota_type = %(quota_type)s 
                AND last_reset < %(cutoff_time)s
                AND current_usage > 0
                ORDER BY tenant_id, last_reset
                """
                
                quotas = await self.db.execute_query(query, {
                    'quota_type': db_quota_type,
                    'cutoff_time': cutoff_time
                })
                
                quotas_due.extend(quotas)
                logger.debug("Found quotas due for reset", 
                           quota_type=quota_type, 
                           count=len(quotas), 
                           cutoff_time=cutoff_time.isoformat())
            
            return quotas_due
            
        except Exception as e:
            logger.error("Failed to get quotas due for reset", error=str(e))
            raise Exception(f"Failed to get quotas due for reset: {str(e)}")
    
    def _get_db_quota_type(self, quota_type_name: str) -> Optional[str]:
        """Convert quota type name to database enum string"""
        mapping = {
            'daily_ingestion': 'daily_ingestion',
            'monthly_ingestion': 'monthly_ingestion', 
            'storage_gb': 'storage_gb',
            'api_calls': 'api_calls',
            'users': 'users',
            'alerts': 'alerts'
        }
        return mapping.get(quota_type_name)
    
    async def _store_historical_usage(self, quota: Dict[str, Any]) -> None:
        """Store current usage in historical table before reset"""
        try:
            # Create historical usage record
            historical_record = {
                'id': f"hist-{quota['id']}-{int(datetime.now(timezone.utc).timestamp())}",
                'tenant_id': quota['tenant_id'],
                'customer_id': quota['customer_id'],
                'quota_type': quota['quota_type'],
                'usage_amount': quota['current_usage'],
                'quota_limit': quota['quota_limit'],
                'reset_period_start': quota['last_reset'],
                'reset_period_end': datetime.now(timezone.utc),
                'billing_period': datetime.now(timezone.utc).strftime('%Y-%m'),
                'reset_reason': 'scheduled_reset',
                'metadata': '{}',
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            }
            
            # Insert into historical usage table
            insert_query = """
            INSERT INTO quota_usage_history_mt (
                id, tenant_id, customer_id, quota_type, usage_amount, quota_limit,
                reset_period_start, reset_period_end, billing_period, reset_reason,
                metadata, created_at, updated_at
            ) VALUES (
                %(id)s, %(tenant_id)s, %(customer_id)s, %(quota_type)s, %(usage_amount)s, %(quota_limit)s,
                %(reset_period_start)s, %(reset_period_end)s, %(billing_period)s, %(reset_reason)s,
                %(metadata)s, %(created_at)s, %(updated_at)s
            )
            """
            
            await self.db.execute_query(insert_query, historical_record)
            
            logger.debug("Stored historical usage record", 
                        tenant_id=quota['tenant_id'],
                        quota_type=quota['quota_type'],
                        usage_amount=quota['current_usage'])
            
        except Exception as e:
            logger.error("Failed to store historical usage", 
                        tenant_id=quota['tenant_id'], 
                        quota_type=quota['quota_type'], 
                        error=str(e))
            raise Exception(f"Failed to store historical usage: {str(e)}")
    
    async def _reset_quota(self, quota: Dict[str, Any]) -> None:
        """Reset quota current_usage to 0 and update last_reset timestamp"""
        try:
            current_time = datetime.now(timezone.utc)
            
            update_query = """
            ALTER TABLE tenant_quotas_mt
            UPDATE 
                current_usage = 0,
                last_reset = %(reset_time)s,
                updated_at = %(reset_time)s
            WHERE id = %(quota_id)s
            """
            
            await self.db.execute_query(update_query, {
                'reset_time': current_time,
                'quota_id': quota['id']
            })
            
            logger.debug("Reset quota successfully", 
                        tenant_id=quota['tenant_id'],
                        quota_type=quota['quota_type'],
                        previous_usage=quota['current_usage'])
            
        except Exception as e:
            logger.error("Failed to reset quota", 
                        tenant_id=quota['tenant_id'], 
                        quota_type=quota['quota_type'], 
                        error=str(e))
            raise Exception(f"Failed to reset quota: {str(e)}")
    
    async def get_quota_reset_schedule(self) -> Dict[str, Any]:
        """Get current quota reset schedule and next reset times"""
        try:
            schedule_info = {
                'configuration': self.reset_config,
                'next_resets': {},
                'status': 'active'
            }
            
            current_time = datetime.now(timezone.utc)
            
            for quota_type, reset_days in self.reset_config.items():
                if reset_days <= 0:
                    schedule_info['next_resets'][quota_type] = 'disabled'
                    continue
                
                # Get the most recent reset for this quota type
                db_quota_type = self._get_db_quota_type(quota_type)
                if not db_quota_type:
                    continue
                
                query = """
                SELECT MAX(last_reset) as last_reset
                FROM tenant_quotas_mt 
                WHERE quota_type = %(quota_type)s
                """
                
                result = await self.db.execute_query(query, {'quota_type': db_quota_type})
                
                if result and result[0]['last_reset']:
                    last_reset = result[0]['last_reset']
                    next_reset = last_reset + timedelta(days=reset_days)
                    schedule_info['next_resets'][quota_type] = next_reset.isoformat()
                else:
                    schedule_info['next_resets'][quota_type] = 'no_data'
            
            return schedule_info
            
        except Exception as e:
            logger.error("Failed to get quota reset schedule", error=str(e))
            raise Exception(f"Failed to get quota reset schedule: {str(e)}")
    
    async def force_reset_tenant_quotas(self, tenant_id: str, quota_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Force reset specific tenant quotas (admin operation)"""
        try:
            # Get tenant quotas to reset
            if quota_types:
                # Convert quota type names to database enum values
                db_quota_types = [self._get_db_quota_type(qt) for qt in quota_types if self._get_db_quota_type(qt)]
                quota_filter = "AND quota_type IN ({})".format(','.join(f"'{qt}'" for qt in db_quota_types))
            else:
                quota_filter = ""
            
            query = f"""
            SELECT 
                id, tenant_id, quota_type, quota_limit, current_usage, 
                last_reset, customer_id, created_at, updated_at
            FROM tenant_quotas_mt 
            WHERE tenant_id = %(tenant_id)s 
            {quota_filter}
            """
            
            quotas = await self.db.execute_query(query, {'tenant_id': tenant_id})
            
            reset_results = {
                'tenant_id': tenant_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'quotas_reset': 0,
                'reset_details': [],
                'errors': []
            }
            
            for quota in quotas:
                try:
                    # Store historical usage
                    await self._store_historical_usage(quota)
                    
                    # Reset quota
                    await self._reset_quota(quota)
                    
                    reset_results['quotas_reset'] += 1
                    reset_results['reset_details'].append({
                        'quota_type': quota['quota_type'],
                        'previous_usage': quota['current_usage'],
                        'quota_limit': quota['quota_limit']
                    })
                    
                except Exception as e:
                    reset_results['errors'].append(f"Failed to reset {quota['quota_type']}: {str(e)}")
            
            logger.info("Force reset completed", 
                       tenant_id=tenant_id, 
                       quotas_reset=reset_results['quotas_reset'])
            
            return reset_results
            
        except Exception as e:
            logger.error("Force reset failed", tenant_id=tenant_id, error=str(e))
            raise Exception(f"Force reset failed: {str(e)}")


# Background scheduler service
class QuotaResetScheduler:
    """Background scheduler for quota reset service"""
    
    def __init__(self, check_interval_minutes: int = None):
        self.quota_service = QuotaResetService()
        # Default check interval from environment or 60 minutes
        self.check_interval = int(os.getenv('QUOTA_RESET_CHECK_INTERVAL_MINUTES', check_interval_minutes or 60))
        self.running = False
        
    async def start_scheduler(self):
        """Start the background scheduler"""
        self.running = True
        logger.info("Starting quota reset scheduler", check_interval_minutes=self.check_interval)
        
        while self.running:
            try:
                # Run quota reset check
                summary = await self.quota_service.check_and_reset_quotas()
                logger.info("Scheduled quota reset completed", summary=summary)
                
                # Wait for next check interval
                await asyncio.sleep(self.check_interval * 60)  # Convert minutes to seconds
                
            except Exception as e:
                logger.error("Scheduler error, will retry", error=str(e))
                # Wait 5 minutes before retrying on error
                await asyncio.sleep(300)
    
    def stop_scheduler(self):
        """Stop the background scheduler"""
        self.running = False
        logger.info("Quota reset scheduler stopped")


# Lazy initialization to avoid startup errors
quota_reset_service = None
quota_reset_scheduler = None

def get_quota_reset_service():
    """Get or create quota reset service instance"""
    global quota_reset_service
    if quota_reset_service is None:
        quota_reset_service = QuotaResetService()
    return quota_reset_service

def get_quota_reset_scheduler():
    """Get or create quota reset scheduler instance"""
    global quota_reset_scheduler
    if quota_reset_scheduler is None:
        quota_reset_scheduler = QuotaResetScheduler()
    return quota_reset_scheduler