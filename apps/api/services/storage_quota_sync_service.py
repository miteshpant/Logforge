"""
Storage Quota Sync Service
Periodically calculates actual storage usage and updates tenants_quotas_mt table
"""

import asyncio
import structlog
import yaml
import os
from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta

from database_layer import DatabaseLayer
from services.tenant_service import TenantService

logger = structlog.get_logger()

class StorageQuotaSyncService:
    """Service for periodic storage quota calculations and sync"""
    
    def __init__(self):
        self.db = DatabaseLayer("StorageQuotaSyncService", "storage-quota-sync-service-key")
        self.tenant_service = TenantService()
        self.config = self._load_config()
        self._sync_task = None
        # Store last refresh timestamps in memory (simple approach)
        self._last_refresh_times = {}
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), '../config/storage_quota.yml')
            
            if not os.path.exists(config_path):
                logger.warning("Storage quota config not found, using defaults", path=config_path)
                return self._get_default_config()
            
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                
            logger.info("Storage quota sync config loaded", 
                       interval=config.get('storage_quota_sync', {}).get('interval_minutes', 30))
            return config
            
        except Exception as e:
            logger.error("Failed to load storage quota config, using defaults", error=str(e))
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration if YAML file is missing"""
        return {
            'storage_quota_sync': {
                'interval_minutes': 30,
                'enabled': True,
                'run_on_startup': True,
                'startup_delay_seconds': 60
            },
            'storage_calculation': {
                'use_actual_log_sizes': True,
                'overhead_multiplier': 1.2,
                'minimum_storage_mb': 1.0
            },
            'logging': {
                'log_level': 'INFO',
                'log_quota_changes': True
            }
        }
    
    async def get_last_refresh_timestamp(self, customer_id: str) -> datetime:
        """Get the last refresh timestamp for a tenant (stored in memory)"""
        if customer_id in self._last_refresh_times:
            return self._last_refresh_times[customer_id]
        else:
            # For first run, use timestamp from 7 days ago as baseline
            # (enough to capture recent data without overwhelming the system)
            initial_timestamp = datetime.now(timezone.utc) - timedelta(days=7)
            self._last_refresh_times[customer_id] = initial_timestamp
            logger.debug("First refresh for tenant, using 7-day baseline", 
                       customer_id=customer_id, 
                       baseline_timestamp=initial_timestamp)
            return initial_timestamp
    
    def update_last_refresh_timestamp(self, customer_id: str, timestamp: datetime):
        """Update the last refresh timestamp for a tenant (in memory)"""
        self._last_refresh_times[customer_id] = timestamp
        logger.debug("Updated last refresh timestamp", 
                   customer_id=customer_id, 
                   timestamp=timestamp)

    async def calculate_storage_delta_bytes(self, customer_id: str, since_timestamp: datetime) -> int:
        """Calculate storage delta since last refresh using ingestion_stats_mt"""
        try:
            # Query ingestion data since last refresh
            query = """
                SELECT 
                    sum(bytes_ingested) as delta_bytes
                FROM ingestion_stats_mt 
                WHERE customer_id = %(customer_id)s
                AND timestamp > %(since_timestamp)s
            """
            
            result = await self.db.execute_query(query, {
                "customer_id": customer_id,
                "since_timestamp": since_timestamp
            })
            
            if result and result[0].get('delta_bytes') is not None:
                delta_bytes = result[0]['delta_bytes']
                logger.debug("Calculated storage delta", 
                           customer_id=customer_id,
                           since_timestamp=since_timestamp,
                           delta_bytes=delta_bytes)
                return int(delta_bytes)
            else:
                logger.debug("No new ingestion data found", 
                           customer_id=customer_id,
                           since_timestamp=since_timestamp)
                return 0
                
        except Exception as e:
            logger.error("Failed to calculate storage delta", 
                        error=str(e), 
                        customer_id=customer_id)
            return 0
    
    async def update_tenant_storage_quota(self, customer_id: str) -> bool:
        """Update storage quota using delta approach (avoids double-counting)"""
        try:
            # Get last refresh timestamp for this tenant
            last_refresh = await self.get_last_refresh_timestamp(customer_id)
            current_time = datetime.now(timezone.utc)
            
            # Calculate storage delta since last refresh
            delta_bytes = await self.calculate_storage_delta_bytes(customer_id, last_refresh)
            
            if delta_bytes == 0:
                logger.debug("No new storage delta for tenant", 
                           customer_id=customer_id,
                           last_refresh=last_refresh)
                return True  # No update needed, but not a failure
            
            # Apply overhead multiplier to delta
            overhead_multiplier = self.config.get('storage_calculation', {}).get('overhead_multiplier', 1.2)
            adjusted_delta_bytes = int(delta_bytes * overhead_multiplier)
            
            # Get current quotas for this tenant
            db_quotas = await self.tenant_service.tenant_dao.get_tenant_quotas(customer_id)
            
            # Find storage quota and update it by adding delta
            quota_updated = False
            for quota in db_quotas:
                if quota['quota_type'] in ['storage_gb', 'storage_gb_quota']:
                    current_usage_bytes = quota.get('current_usage', 0)
                    new_usage_bytes = current_usage_bytes + adjusted_delta_bytes
                    
                    # Update current usage by adding the delta
                    await self.tenant_service.tenant_dao.update_tenant_quota(
                        customer_id, 
                        quota['quota_type'], 
                        {'current_usage': new_usage_bytes}
                    )
                    quota_updated = True
                    
                    # Update last refresh timestamp
                    self.update_last_refresh_timestamp(customer_id, current_time)
                    
                    if self.config.get('logging', {}).get('log_quota_changes', True):
                        logger.info("Storage quota updated with delta", 
                                  customer_id=customer_id,
                                  delta_bytes=delta_bytes,
                                  adjusted_delta_bytes=adjusted_delta_bytes,
                                  previous_usage_bytes=current_usage_bytes,
                                  new_usage_bytes=new_usage_bytes,
                                  new_usage_gb=round(new_usage_bytes / (1024**3), 3),
                                  quota_type=quota['quota_type'])
                    break
            
            if not quota_updated:
                logger.warning("No storage quota found for tenant", 
                             customer_id=customer_id,
                             available_quotas=[q['quota_type'] for q in db_quotas])
                return False
                
            return True
                
        except Exception as e:
            logger.error("Failed to update tenant storage quota", 
                        error=str(e), 
                        customer_id=customer_id,
                        exc_info=True)
            # Re-raise to see full stack trace
            raise
    
    async def sync_all_tenant_storage_quotas(self) -> Dict[str, Any]:
        """Calculate and update storage quotas for all tenants"""
        try:
            # Get list of all active tenants with log data
            tenants_query = """
                SELECT DISTINCT customer_id 
                FROM logs_raw_mt 
                WHERE customer_id != 'platform'
                AND customer_id != ''
                AND customer_id IS NOT NULL
            """
            
            result = await self.db.execute_query(tenants_query, {})
            
            if not result:
                logger.info("No tenants found for storage quota sync")
                return {"updated": 0, "failed": 0, "total": 0}
            
            tenant_count = len(result)
            updated_count = 0
            failed_count = 0
            
            logger.info("Starting storage quota sync", total_tenants=tenant_count)
            
            for row in result:
                # Database layer returns dict format: {"customer_id": "uuid"}
                customer_id = row['customer_id']
                if customer_id:
                    try:
                        success = await self.update_tenant_storage_quota(customer_id)
                        if success:
                            updated_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        logger.error("Failed to update storage quota for tenant",
                                   customer_id=customer_id, error=str(e), exc_info=True)
                        failed_count += 1
                        # Re-raise on first error to see what's happening
                        raise
            
            logger.info("Storage quota sync completed", 
                       total=tenant_count,
                       updated=updated_count, 
                       failed=failed_count)
            
            return {
                "updated": updated_count,
                "failed": failed_count,
                "total": tenant_count,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to sync all tenant storage quotas", error=str(e), exc_info=True)
            # Re-raise to see the actual error
            raise
    
    async def _periodic_sync_task(self):
        """Background task for periodic storage quota sync"""
        sync_config = self.config.get('storage_quota_sync', {})
        interval_minutes = sync_config.get('interval_minutes', 30)
        
        logger.info("Storage quota periodic sync started", 
                   interval_minutes=interval_minutes)
        
        try:
            while True:
                try:
                    # Run the sync
                    result = await self.sync_all_tenant_storage_quotas()
                    
                    if result.get('failed', 0) > 0:
                        logger.warning("Storage quota sync completed with failures", **result)
                    
                    # Wait for next interval
                    await asyncio.sleep(interval_minutes * 60)
                    
                except Exception as e:
                    logger.error("Error in periodic storage quota sync", error=str(e), exc_info=True)
                    # Wait 5 minutes before retrying on error
                    await asyncio.sleep(300)
                    
        except asyncio.CancelledError:
            logger.info("Storage quota periodic sync cancelled")
            raise
        except Exception as e:
            logger.error("Storage quota periodic sync failed", error=str(e))
    
    def start_periodic_sync(self):
        """Start the periodic storage quota sync"""
        sync_config = self.config.get('storage_quota_sync', {})
        
        if not sync_config.get('enabled', True):
            logger.info("Storage quota sync is disabled in config")
            return
        
        if self._sync_task and not self._sync_task.done():
            logger.warning("Storage quota sync task already running")
            return
        
        startup_delay = sync_config.get('startup_delay_seconds', 60)
        
        async def delayed_start():
            if startup_delay > 0:
                logger.info("Storage quota sync starting with delay", 
                           delay_seconds=startup_delay)
                await asyncio.sleep(startup_delay)
            
            # Run initial sync if configured
            if sync_config.get('run_on_startup', True):
                logger.info("Running initial storage quota sync")
                await self.sync_all_tenant_storage_quotas()
            
            # Start periodic task
            await self._periodic_sync_task()
        
        self._sync_task = asyncio.create_task(delayed_start())
        logger.info("Storage quota sync task created")
    
    def stop_periodic_sync(self):
        """Stop the periodic storage quota sync"""
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            logger.info("Storage quota sync task cancelled")
    
    async def trigger_manual_sync(self, customer_id: str = None) -> Dict[str, Any]:
        """Trigger manual storage quota sync for specific tenant or all tenants"""
        if customer_id:
            # Update specific tenant
            success = await self.update_tenant_storage_quota(customer_id)
            return {
                "customer_id": customer_id,
                "success": success,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            # Update all tenants
            return await self.sync_all_tenant_storage_quotas()

# Global instance
storage_quota_sync_service = StorageQuotaSyncService()