"""
TTL (Time To Live) and Cold Storage Manager
Handles data lifecycle, retention policies, and multi-cloud archival
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import clickhouse_connect
from storage_config import StorageConfigManager, DeploymentType
import structlog

logger = structlog.get_logger()

class RetentionPeriod(Enum):
    """Standard retention periods for different compliance requirements"""
    DEVELOPMENT = 7      # 1 week
    STANDARD = 90        # 3 months  
    ENTERPRISE = 365     # 1 year
    FINANCIAL = 2555     # 7 years (SOX compliance)
    HEALTHCARE = 2190    # 6 years (HIPAA compliance)
    GOVERNMENT = 2555    # 7 years (FedRAMP compliance)
    UNLIMITED = 0        # No automatic deletion

class ComplianceTier(Enum):
    """Compliance tier requirements"""
    STANDARD = "standard"
    FEDRAMP = "fedramp"
    HIPAA = "hipaa"
    SOX = "sox"
    GDPR = "gdpr"

@dataclass
class RetentionPolicy:
    """Customer-specific retention policy configuration"""
    customer_id: str
    deployment_type: str
    hot_storage_days: int = 30      # Keep in ClickHouse
    cold_storage_days: int = 365    # Keep in object storage
    total_retention_days: int = 365 # Total retention before deletion
    compliance_extended_days: int = 0  # Additional retention for compliance
    encryption_required: bool = False
    geographic_restrictions: List[str] = None
    
    def __post_init__(self):
        if self.geographic_restrictions is None:
            self.geographic_restrictions = []

class TTLManager:
    """Manages TTL policies and data lifecycle for log retention"""
    
    def __init__(self, clickhouse_client, storage_manager: StorageConfigManager):
        self.ch_client = clickhouse_client
        self.storage_manager = storage_manager
        self.policies: Dict[str, RetentionPolicy] = {}
        self.logger = structlog.get_logger("ttl_manager")
        
    async def initialize_policies(self):
        """Initialize retention policies for all customers"""
        try:
            # Initialize default retention policies
            # In a full implementation, this would load actual customer configurations
            default_customers = [
                "shared-tenant",
                "enterprise-demo", 
                "compliance-test"
            ]
            
            for customer_id in default_customers:
                # Get retention days from storage manager or use default
                try:
                    retention_days = self.storage_manager.get_compliance_retention_days(customer_id)
                except:
                    retention_days = 90  # Default 90 days
                
                # Create policy with storage manager configuration
                policy = RetentionPolicy(
                    customer_id=customer_id,
                    deployment_type="shared",
                    hot_storage_days=30,
                    cold_storage_days=retention_days,
                    total_retention_days=retention_days,
                    compliance_extended_days=0,
                    encryption_required=False,
                    geographic_restrictions=[]
                )
                
                self.policies[customer_id] = policy
                await self._apply_ttl_policy(policy)
                
            self.logger.info("TTL policies initialized", customer_count=len(self.policies))
            
        except Exception as e:
            self.logger.error("Failed to initialize TTL policies", error=str(e))
            # Don't raise - allow system to continue without TTL if there are issues
            self.logger.warning("Continuing without TTL policies - manual cleanup required")
    
    def _create_retention_policy(self, customer_id: str, config: Dict[str, Any]) -> RetentionPolicy:
        """Create retention policy based on customer configuration"""
        deployment_type = config.get('deployment_type', 'shared')
        retention_days = config.get('retention_days', 90)
        
        # Set retention based on deployment type
        if deployment_type == 'fedramp':
            policy = RetentionPolicy(
                customer_id=customer_id,
                deployment_type=deployment_type,
                hot_storage_days=30,
                cold_storage_days=2555,  # 7 years
                total_retention_days=2555,
                compliance_extended_days=365,  # Additional year for audits
                encryption_required=True,
                geographic_restrictions=['US']
            )
        elif deployment_type == 'healthcare':
            policy = RetentionPolicy(
                customer_id=customer_id,
                deployment_type=deployment_type,
                hot_storage_days=30,
                cold_storage_days=2190,  # 6 years
                total_retention_days=2190,
                compliance_extended_days=365,
                encryption_required=True
            )
        elif deployment_type == 'financial':
            policy = RetentionPolicy(
                customer_id=customer_id,
                deployment_type=deployment_type,
                hot_storage_days=90,     # Keep longer in hot for trading analysis
                cold_storage_days=2555,  # 7 years (SOX compliance)
                total_retention_days=2555,
                compliance_extended_days=365,
                encryption_required=True
            )
        elif deployment_type == 'dedicated':
            policy = RetentionPolicy(
                customer_id=customer_id,
                deployment_type=deployment_type,
                hot_storage_days=60,
                cold_storage_days=retention_days,
                total_retention_days=retention_days,
                encryption_required=config.get('encryption_at_rest', False)
            )
        else:  # shared deployment
            policy = RetentionPolicy(
                customer_id=customer_id,
                deployment_type=deployment_type,
                hot_storage_days=7,      # Limited hot storage for shared
                cold_storage_days=retention_days,
                total_retention_days=retention_days
            )
        
        return policy
    
    async def _apply_ttl_policy(self, policy: RetentionPolicy):
        """Apply TTL policy to ClickHouse tables for specific customer"""
        try:
            # Generate TTL ALTER statements for customer-specific partitions
            ttl_statements = self._generate_ttl_statements(policy)
            
            for statement in ttl_statements:
                await asyncio.to_thread(self.ch_client.command, statement)
                self.logger.info("Applied TTL statement", 
                               customer_id=policy.customer_id,
                               statement=statement[:100] + "...")
                
        except Exception as e:
            self.logger.error("Failed to apply TTL policy",
                            customer_id=policy.customer_id,
                            error=str(e))
            raise
    
    def _generate_ttl_statements(self, policy: RetentionPolicy) -> List[str]:
        """Generate ClickHouse TTL statements for multi-tenant tables"""
        statements = []
        
        total_days = policy.total_retention_days + policy.compliance_extended_days
        
        # Store policy in customer_ttl_policies table for tracking
        compliance_tier = getattr(policy, 'compliance_tier', ComplianceTier.STANDARD)
        policy_insert = f"""
        INSERT INTO logforge.customer_ttl_policies 
        (customer_id, deployment_type, compliance_tier, hot_storage_days, 
         cold_storage_days, total_retention_days, created_at, updated_at)
        VALUES (
            '{policy.customer_id}',
            '{policy.deployment_type}', 
            '{compliance_tier.value}',
            {policy.hot_storage_days},
            {policy.cold_storage_days},
            {policy.total_retention_days},
            now64(),
            now64()
        )
        """
        statements.append(policy_insert.strip())
        
        # Multi-tenant tables use partition-level TTL (applied globally, filtered by partition)
        # Each customer has separate partitions: (customer_id, toYYYYMM(ts))
        
        # TTL for multi-tenant raw logs table
        ttl_raw_mt = f"""
        ALTER TABLE logforge.logs_raw_mt MODIFY TTL 
            ts + toIntervalDay({total_days}) DELETE
        """
        statements.append(ttl_raw_mt.strip())
        
        # TTL for multi-tenant normalized logs table  
        ttl_normalized_mt = f"""
        ALTER TABLE logforge.logs_normalized_mt MODIFY TTL 
            ts + toIntervalDay({total_days}) DELETE
        """
        statements.append(ttl_normalized_mt.strip())
        
        # TTL for multi-tenant hourly stats (longer retention)
        stats_retention = max(365, total_days)  # Keep stats for at least 1 year
        ttl_stats_mt = f"""
        ALTER TABLE logforge.logs_hourly_stats_mt MODIFY TTL 
            date + toIntervalDay({stats_retention}) DELETE
        """
        statements.append(ttl_stats_mt.strip())
        
        # Extended retention for security data if compliance required
        if policy.compliance_extended_days > 0:
            security_ttl = f"""
            ALTER TABLE security_daily_summary MODIFY TTL 
                toDate(date) + toIntervalDay({total_days + 365}) 
                WHERE customer_id = '{policy.customer_id}' DELETE
            """
            statements.append(security_ttl.strip())
        
        return statements
    
    async def archive_to_cold_storage(self, customer_id: str, before_date: datetime):
        """Archive customer data to cold storage"""
        try:
            policy = self.policies.get(customer_id)
            if not policy:
                raise ValueError(f"No retention policy found for customer {customer_id}")
            
            # Get customer's storage client
            storage_client = self.storage_manager.get_storage_client(customer_id)
            
            # Query data to archive
            query = f"""
            SELECT * FROM logs_normalized 
            WHERE customer_id = '{customer_id}' 
              AND ts < '{before_date.isoformat()}'
              AND ts >= '{(before_date - timedelta(days=30)).isoformat()}'
            ORDER BY ts
            """
            
            result = await asyncio.to_thread(self.ch_client.query, query)
            
            if not result.result_rows:
                self.logger.info("No data to archive", 
                               customer_id=customer_id, 
                               before_date=before_date)
                return
            
            # Archive to appropriate storage backend
            archive_key = f"logs/{customer_id}/{before_date.strftime('%Y/%m/%d')}/archived_logs.parquet"
            
            await self._upload_to_storage(storage_client, archive_key, result.result_rows, policy)
            
            self.logger.info("Data archived successfully",
                           customer_id=customer_id,
                           records_count=len(result.result_rows),
                           archive_key=archive_key)
            
        except Exception as e:
            self.logger.error("Failed to archive data",
                            customer_id=customer_id,
                            error=str(e))
            raise
    
    async def _upload_to_storage(self, storage_client, key: str, data: List, policy: RetentionPolicy):
        """Upload archived data to configured storage backend"""
        try:
            # Check for required dependencies
            try:
                import pandas as pd
                import pyarrow
                import io
            except ImportError as e:
                raise ValueError(f"Required dependencies missing for data archival: {e}. Please install pandas and pyarrow.")
            
            # Validate input data
            if not data or len(data) == 0:
                raise ValueError("No data provided for archival")
            
            # Create DataFrame from ClickHouse result
            df = pd.DataFrame(data)
            
            # Compress and encrypt if required
            buffer = io.BytesIO()
            df.to_parquet(buffer, compression='gzip', engine='pyarrow')
            compressed_data = buffer.getvalue()
            
            # Encrypt if required by policy
            if policy.encryption_required:
                compressed_data = await self._encrypt_data(compressed_data, policy.customer_id)
            
            # Get bucket name from storage endpoint
            storage_endpoint = self.storage_manager.get_storage_endpoint(policy.customer_id)
            bucket_name = storage_endpoint.bucket
            
            # Upload based on storage type
            if hasattr(storage_client, 'put_object'):  # S3-compatible
                # Build upload parameters
                upload_params = {
                    'Bucket': bucket_name,
                    'Key': key,
                    'Body': compressed_data
                }
                
                # Only add ServerSideEncryption if encryption is required
                if policy.encryption_required:
                    upload_params['ServerSideEncryption'] = 'AES256'
                
                storage_client.put_object(**upload_params)
            elif hasattr(storage_client, 'blob'):  # GCS
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(key)
                blob.upload_from_string(compressed_data)
            
        except Exception as e:
            self.logger.error("Failed to upload to storage", key=key, error=str(e))
            raise
    
    async def _encrypt_data(self, data: bytes, customer_id: str) -> bytes:
        """Encrypt data using customer-specific encryption key"""
        try:
            from cryptography.fernet import Fernet
            
            # Get or generate customer encryption key
            encryption_key = self._get_customer_encryption_key(customer_id)
            fernet = Fernet(encryption_key)
            
            return fernet.encrypt(data)
            
        except Exception as e:
            self.logger.error("Failed to encrypt data", 
                            customer_id=customer_id, 
                            error=str(e))
            raise
    
    def _get_customer_encryption_key(self, customer_id: str) -> bytes:
        """Get or generate customer-specific encryption key"""
        # In production, this would use a proper key management service
        # For now, generate deterministic key based on customer ID
        from cryptography.fernet import Fernet
        import hashlib
        
        # Generate consistent key for customer
        key_material = f"logforge_customer_{customer_id}_encryption_key".encode()
        key_hash = hashlib.sha256(key_material).digest()[:32]
        return Fernet.generate_key()  # Replace with proper key derivation
    
    async def archive_data(self, customer_id: str) -> Dict[str, Any]:
        """Archive data for a specific customer based on their database retention policy"""
        try:
            # Get tenant's retention policy from database via storage service
            from services.storage_service import StorageService
            storage_service = StorageService()
            db_policy = await storage_service.get_retention_policy(customer_id)
            
            if not db_policy:
                raise ValueError(f"No retention policy found for customer {customer_id}")
            
            # Extract retention settings from database policy
            hot_retention_days = db_policy.get('hot_retention_days', 30)
            cold_retention_days = db_policy.get('cold_retention_days', 90)
            archive_retention_days = db_policy.get('archive_retention_days', 365)
            compression_enabled = db_policy.get('compression_enabled', True)
            
            # Calculate archive cutoff date (data older than hot_retention_days should be archived)
            from datetime import datetime, timedelta, timezone
            archive_before_date = datetime.now(timezone.utc) - timedelta(days=hot_retention_days)
            cold_cutoff_date = datetime.now(timezone.utc) - timedelta(days=cold_retention_days)
            
            # Get actual data size for the time period from ingestion_stats_mt
            # Convert datetime to ClickHouse-compatible format
            archive_before_str = archive_before_date.strftime('%Y-%m-%d %H:%M:%S')
            cold_cutoff_str = cold_cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
            
            size_query = f"""
            SELECT 
                SUM(records_ingested) as total_log_count,
                SUM(bytes_ingested) as total_bytes_ingested
            FROM ingestion_stats_mt 
            WHERE customer_id = '{customer_id}' 
              AND timestamp < '{archive_before_str}'
              AND timestamp >= '{cold_cutoff_str}'
            """
            
            size_result = await asyncio.to_thread(self.ch_client.query, size_query)
            
            if not size_result.result_rows or not size_result.result_rows[0][0]:
                self.logger.info("No ingestion stats found for archive period", 
                               customer_id=customer_id, 
                               archive_before_date=archive_before_date)
                return {
                    "status": "completed",
                    "records_processed": 0,
                    "data_size_gb": 0.0,
                    "archive_cutoff_date": archive_before_date.isoformat(),
                    "message": "No data found for archival based on ingestion stats"
                }
            
            # Extract actual size data
            total_log_count = size_result.result_rows[0][0] or 0
            total_bytes_ingested = size_result.result_rows[0][1] or 0
            
            # Convert bytes to GB
            data_size_gb = total_bytes_ingested / (1024**3) if total_bytes_ingested > 0 else 0.0
            
            if total_log_count == 0:
                self.logger.info("No records to archive for period", 
                               customer_id=customer_id, 
                               archive_before_date=archive_before_date)
                return {
                    "status": "completed",
                    "records_processed": 0,
                    "data_size_gb": 0.0,
                    "archive_cutoff_date": archive_before_date.isoformat(),
                    "message": "No records found in archive time period"
                }
            
            # Query actual log data to archive (limited batch for performance)
            # Use exact column names from logs_raw_mt table schema
            archive_query = f"""
            SELECT 
                ts, host, service, level, msg, trace_id, span_id, 
                attrs, status, src_ip, user_id, customer_id,
                ingested_at, severity_num, facility, parser_version
            FROM logs_raw_mt 
            WHERE customer_id = '{customer_id}' 
              AND ts < toDateTime64('{archive_before_str}', 3)
              AND ts >= toDateTime64('{cold_cutoff_str}', 3)
            ORDER BY ts
            LIMIT 5000
            """
            
            result = await asyncio.to_thread(self.ch_client.query, archive_query)
            actual_records_archived = len(result.result_rows) if result.result_rows else 0
            
            # Get storage client for archival
            storage_client = self.storage_manager.get_storage_client(customer_id)
            
            # Create archive path with customer isolation
            archive_date_str = archive_before_date.strftime('%Y/%m/%d')
            archive_key = f"archived_logs/{customer_id}/{archive_date_str}/logs_batch_{int(datetime.now(timezone.utc).timestamp())}.parquet"
            
            # Create a temporary policy object for upload method compatibility
            temp_policy = RetentionPolicy(
                customer_id=customer_id,
                deployment_type="shared",
                hot_storage_days=hot_retention_days,
                cold_storage_days=cold_retention_days,
                total_retention_days=archive_retention_days,
                encryption_required=False
            )
            
            # Check if this time period has already been archived to prevent duplicates
            existing_archive_query = f"""
            SELECT COUNT(*) as existing_count 
            FROM archive_metadata_mt 
            WHERE customer_id = '{customer_id}' 
              AND original_start_date <= toDateTime64('{cold_cutoff_str}', 3)
              AND original_end_date >= toDateTime64('{archive_before_str}', 3)
              AND status = 'completed'
            """
            
            existing_result = await asyncio.to_thread(self.ch_client.query, existing_archive_query)
            existing_archives = existing_result.result_rows[0][0] if existing_result.result_rows else 0
            
            if existing_archives > 0:
                self.logger.info("Time period already archived, skipping",
                               customer_id=customer_id,
                               existing_archives=existing_archives,
                               time_period=f"{cold_cutoff_str} to {archive_before_str}")
                return {
                    "status": "completed",
                    "records_processed": 0,
                    "data_size_gb": round(data_size_gb, 6),
                    "message": f"Time period already archived ({existing_archives} existing archives found)"
                }
            
            # Only upload if we have data to archive
            if actual_records_archived > 0:
                # Upload to cold storage first
                await self._upload_to_storage(storage_client, archive_key, result.result_rows, temp_policy)
                
                # Calculate checksum for data integrity
                import hashlib
                data_str = str(result.result_rows).encode('utf-8')
                checksum = hashlib.sha256(data_str).hexdigest()
                
                # Record archive metadata BEFORE deleting data
                storage_endpoint = self.storage_manager.get_storage_endpoint(customer_id)
                
                archive_metadata_insert = f"""
                INSERT INTO archive_metadata_mt (
                    customer_id, archive_key, original_start_date, original_end_date,
                    records_archived, data_size_bytes, compression_type, encryption_enabled,
                    archive_date, storage_backend, bucket_name, checksum, retention_policy_id,
                    status
                ) VALUES (
                    '{customer_id}',
                    '{archive_key}',
                    toDateTime64('{cold_cutoff_str}', 3),
                    toDateTime64('{archive_before_str}', 3),
                    {actual_records_archived},
                    {total_bytes_ingested},
                    'gzip',
                    0,
                    now64(),
                    '{storage_endpoint.backend.value}',
                    '{storage_endpoint.bucket}',
                    '{checksum}',
                    'default',
                    'completed'
                )
                """
                
                await asyncio.to_thread(self.ch_client.command, archive_metadata_insert)
                
                # After successful upload and metadata tracking, DELETE the archived data from ClickHouse (MOVE operation)
                delete_query = f"""
                DELETE FROM logs_raw_mt 
                WHERE customer_id = '{customer_id}' 
                  AND ts < toDateTime64('{archive_before_str}', 3)
                  AND ts >= toDateTime64('{cold_cutoff_str}', 3)
                """
                
                delete_result = await asyncio.to_thread(self.ch_client.command, delete_query)
                self.logger.info(f"Successfully moved data to archive",
                               customer_id=customer_id,
                               records_moved=actual_records_archived,
                               archive_key=archive_key,
                               checksum=checksum[:16] + "...")
                
                archive_message = f"Successfully moved {actual_records_archived} records to cold storage (deleted from hot storage)"
            else:
                archive_message = f"No actual log records found in time period (estimated {total_log_count} from stats)"
            
            self.logger.info("Data archival completed",
                           customer_id=customer_id,
                           estimated_total_records=total_log_count,
                           actual_records_archived=actual_records_archived,
                           data_size_gb=round(data_size_gb, 6),
                           archive_key=archive_key if actual_records_archived > 0 else None,
                           archive_cutoff_date=archive_before_date.isoformat())
            
            return {
                "status": "completed",
                "records_processed": actual_records_archived,
                "estimated_total_records": total_log_count,
                "data_size_gb": round(data_size_gb, 6),
                "archive_key": archive_key if actual_records_archived > 0 else None,
                "archive_cutoff_date": archive_before_date.isoformat(),
                "storage_backend": "minio",
                "compression_enabled": compression_enabled,
                "hot_retention_days": hot_retention_days,
                "message": archive_message
            }
            
        except Exception as e:
            self.logger.error("Failed to archive data",
                            customer_id=customer_id,
                            error=str(e))
            return {
                "status": "failed",
                "error": str(e),
                "records_processed": 0,
                "data_size_gb": 0.0,
                "message": f"Archive operation failed: {str(e)}"
            }

    async def cleanup_expired_data(self):
        """Clean up expired data across all customers"""
        try:
            cleanup_stats = {}
            
            for customer_id, policy in self.policies.items():
                # Force TTL cleanup for customer partitions
                cleanup_query = f"""
                OPTIMIZE TABLE logs_raw 
                PARTITION tuple(toYYYYMM(subtractDays(now(), {policy.total_retention_days + 1})), '{customer_id}')
                FINAL
                """
                
                try:
                    await asyncio.to_thread(self.ch_client.command, cleanup_query)
                    cleanup_stats[customer_id] = "success"
                except Exception as e:
                    cleanup_stats[customer_id] = f"error: {str(e)}"
                    self.logger.error("Failed to cleanup data",
                                    customer_id=customer_id,
                                    error=str(e))
            
            self.logger.info("Cleanup completed", stats=cleanup_stats)
            return cleanup_stats
            
        except Exception as e:
            self.logger.error("Failed to cleanup expired data", error=str(e))
            raise
    
    async def get_retention_status(self, customer_id: str) -> Dict[str, Any]:
        """Get retention status and storage statistics for customer"""
        try:
            policy = self.policies.get(customer_id)
            if not policy:
                return {"error": f"No policy found for customer {customer_id}"}
            
            # Query current storage distribution
            stats_query = f"""
            SELECT 
                'hot' as storage_tier,
                count() as record_count,
                sum(length(msg)) as total_bytes,
                min(ts) as earliest_date,
                max(ts) as latest_date
            FROM logs_normalized 
            WHERE customer_id = '{customer_id}'
              AND ts > now() - INTERVAL {policy.hot_storage_days} DAY
            
            UNION ALL
            
            SELECT 
                'cold' as storage_tier,
                count() as record_count,
                sum(length(msg)) as total_bytes,
                min(ts) as earliest_date,
                max(ts) as latest_date
            FROM logs_normalized 
            WHERE customer_id = '{customer_id}'
              AND ts <= now() - INTERVAL {policy.hot_storage_days} DAY
              AND ts > now() - INTERVAL {policy.total_retention_days} DAY
            """
            
            result = await asyncio.to_thread(self.ch_client.query, stats_query)
            
            status = {
                "customer_id": customer_id,
                "policy": {
                    "hot_storage_days": policy.hot_storage_days,
                    "cold_storage_days": policy.cold_storage_days,
                    "total_retention_days": policy.total_retention_days,
                    "compliance_extended_days": policy.compliance_extended_days,
                    "encryption_required": policy.encryption_required
                },
                "storage_tiers": {}
            }
            
            for row in result.result_rows:
                tier = row[0]
                status["storage_tiers"][tier] = {
                    "record_count": row[1],
                    "total_bytes": row[2],
                    "earliest_date": row[3],
                    "latest_date": row[4]
                }
            
            return status
            
        except Exception as e:
            self.logger.error("Failed to get retention status",
                            customer_id=customer_id,
                            error=str(e))
            return {"error": str(e)}
    
    async def update_retention_policy(self, customer_id: str, new_policy: Dict[str, Any]):
        """Update retention policy for customer"""
        try:
            current_policy = self.policies.get(customer_id)
            if not current_policy:
                raise ValueError(f"No existing policy for customer {customer_id}")
            
            # Update policy fields
            for field, value in new_policy.items():
                if hasattr(current_policy, field):
                    setattr(current_policy, field, value)
            
            # Apply updated TTL
            await self._apply_ttl_policy(current_policy)
            
            self.logger.info("Retention policy updated",
                           customer_id=customer_id,
                           updated_fields=list(new_policy.keys()))
            
            return {"status": "success", "updated_policy": current_policy.__dict__}
            
        except Exception as e:
            self.logger.error("Failed to update retention policy",
                            customer_id=customer_id,
                            error=str(e))
            raise

# Background task scheduler for TTL management
class TTLScheduler:
    """Scheduler for TTL-related background tasks"""
    
    def __init__(self, ttl_manager: TTLManager):
        self.ttl_manager = ttl_manager
        self.logger = structlog.get_logger("ttl_scheduler")
        self._running = False
    
    async def start(self):
        """Start the TTL scheduler"""
        self._running = True
        
        # Initialize policies
        await self.ttl_manager.initialize_policies()
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self._cleanup_loop()),
            asyncio.create_task(self._archive_loop()),
            asyncio.create_task(self._health_check_loop())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            self.logger.info("TTL scheduler stopped")
    
    async def stop(self):
        """Stop the TTL scheduler"""
        self._running = False
    
    async def _cleanup_loop(self):
        """Periodic cleanup of expired data"""
        while self._running:
            try:
                await self.ttl_manager.cleanup_expired_data()
                await asyncio.sleep(3600 * 6)  # Run every 6 hours
            except Exception as e:
                self.logger.error("Cleanup loop error", error=str(e))
                await asyncio.sleep(300)  # Retry in 5 minutes
    
    async def _archive_loop(self):
        """Periodic archival to cold storage"""
        while self._running:
            try:
                # Archive data older than hot storage threshold for each customer
                for customer_id, policy in self.ttl_manager.policies.items():
                    archive_before = datetime.utcnow() - timedelta(days=policy.hot_storage_days)
                    await self.ttl_manager.archive_to_cold_storage(customer_id, archive_before)
                
                await asyncio.sleep(3600 * 12)  # Run every 12 hours
            except Exception as e:
                self.logger.error("Archive loop error", error=str(e))
                await asyncio.sleep(900)  # Retry in 15 minutes
    
    async def _health_check_loop(self):
        """Periodic health checks for TTL system"""
        while self._running:
            try:
                # Check storage utilization and policy compliance
                for customer_id in self.ttl_manager.policies.keys():
                    status = await self.ttl_manager.get_retention_status(customer_id)
                    
                    # Log warnings for policy violations
                    if 'storage_tiers' in status and 'hot' in status['storage_tiers']:
                        hot_data = status['storage_tiers']['hot']
                        if hot_data['record_count'] > 10000000:  # 10M records warning
                            self.logger.warning("High hot storage utilization",
                                              customer_id=customer_id,
                                              hot_records=hot_data['record_count'])
                
                await asyncio.sleep(3600)  # Check every hour
            except Exception as e:
                self.logger.error("Health check loop error", error=str(e))
                await asyncio.sleep(300)  # Retry in 5 minutes