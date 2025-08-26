"""
Multi-Tenant Schema Migration for Logforge
Adds customer_id support to all tables for proper tenant isolation
"""

import asyncio
import structlog
import clickhouse_connect
from typing import List, Dict, Any

logger = structlog.get_logger(__name__)


class MultiTenantSchemaMigration:
    """Handles multi-tenant schema migration for ClickHouse"""
    
    def __init__(self, clickhouse_url: str = "clickhouse://localhost:8124/logforge"):
        self.ch_client = clickhouse_connect.get_client(host='localhost', port=8124, database='logforge')
        
    async def migrate_to_multitenant(self) -> bool:
        """Migrate existing schema to support multi-tenancy"""
        try:
            logger.info("Starting multi-tenant schema migration...")
            
            # Step 1: Add customer_id columns to existing tables
            await self._add_customer_id_columns()
            
            # Step 2: Create new multi-tenant optimized tables
            await self._create_multitenant_tables()
            
            # Step 3: Update materialized views
            await self._update_materialized_views()
            
            # Step 4: Create partition optimization
            await self._create_partition_optimization()
            
            # Step 5: Update TTL policies for multi-tenancy
            await self._create_multitenant_ttl_tables()
            
            logger.info("Multi-tenant schema migration completed successfully")
            return True
            
        except Exception as e:
            logger.error("Multi-tenant schema migration failed", error=str(e))
            return False
    
    async def _add_customer_id_columns(self):
        """Add customer_id columns to existing tables"""
        tables_to_migrate = [
            'logs_raw',
            'logs_normalized'
        ]
        
        for table in tables_to_migrate:
            try:
                # Check if customer_id column already exists
                result = await asyncio.to_thread(
                    self.ch_client.execute,
                    f"DESCRIBE {table}"
                )
                
                columns = [row[0] for row in result]
                
                if 'customer_id' not in columns:
                    # Add customer_id column with default value
                    await asyncio.to_thread(
                        self.ch_client.command,
                        f"ALTER TABLE {table} ADD COLUMN customer_id LowCardinality(String) DEFAULT 'default'"
                    )
                    logger.info(f"Added customer_id column to {table}")
                else:
                    logger.info(f"customer_id column already exists in {table}")
                    
            except Exception as e:
                logger.error(f"Failed to add customer_id to {table}", error=str(e))
                raise
    
    async def _create_multitenant_tables(self):
        """Create new multi-tenant optimized tables"""
        
        # Multi-tenant optimized logs table with proper partitioning
        mt_logs_raw_sql = """
        CREATE TABLE IF NOT EXISTS logs_raw_mt (
            customer_id LowCardinality(String),
            ts DateTime64(3, 'UTC'),
            date Date MATERIALIZED toDate(ts),
            hour UInt8 MATERIALIZED toHour(ts),
            level LowCardinality(String),
            msg String,
            host LowCardinality(String) DEFAULT '',
            service LowCardinality(String) DEFAULT '',
            trace_id String DEFAULT '',
            span_id String DEFAULT '',
            raw_data String,
            ingested_at DateTime64(3, 'UTC') DEFAULT now64(),
            
            -- Performance indexes
            INDEX idx_customer_ts (customer_id, ts) TYPE bloom_filter GRANULARITY 1,
            INDEX idx_service (service) TYPE bloom_filter GRANULARITY 1,
            INDEX idx_level (level) TYPE bloom_filter GRANULARITY 1
        )
        ENGINE = MergeTree()
        PARTITION BY (customer_id, toYYYYMM(ts))
        ORDER BY (customer_id, ts, service)
        TTL ts + toIntervalDay(90)
        SETTINGS index_granularity = 8192
        """
        
        # Multi-tenant normalized logs with optimized schema
        mt_logs_normalized_sql = """
        CREATE TABLE IF NOT EXISTS logs_normalized_mt (
            customer_id LowCardinality(String),
            ts DateTime64(3, 'UTC'),
            date Date MATERIALIZED toDate(ts),
            hour UInt8 MATERIALIZED toHour(ts),
            host LowCardinality(String),
            service LowCardinality(String),
            level LowCardinality(String),
            msg String,
            trace_id String DEFAULT '',
            span_id String DEFAULT '',
            status UInt16 DEFAULT 0,
            src_ip String DEFAULT '',
            user_id String DEFAULT '',
            severity_num UInt8 DEFAULT 0,
            facility UInt8 DEFAULT 0,
            extracted_user_id String DEFAULT '',
            extracted_ip String DEFAULT '',
            http_method LowCardinality(String) DEFAULT '',
            http_uri String DEFAULT '',
            http_status UInt16 DEFAULT 0,
            http_response_time_ms UInt32 DEFAULT 0,
            http_bytes UInt64 DEFAULT 0,
            error_code String DEFAULT '',
            error_category LowCardinality(String) DEFAULT '',
            ingested_at DateTime64(3, 'UTC') DEFAULT now64(),
            is_error UInt8 DEFAULT 0,
            is_slow UInt8 DEFAULT 0,
            
            -- Multi-tenant performance indexes
            INDEX idx_customer_ts (customer_id, ts) TYPE bloom_filter GRANULARITY 1,
            INDEX idx_service (service) TYPE bloom_filter GRANULARITY 1,
            INDEX idx_level (level) TYPE bloom_filter GRANULARITY 1,
            INDEX idx_user (user_id) TYPE bloom_filter GRANULARITY 1,
            INDEX idx_error (is_error) TYPE bloom_filter GRANULARITY 1
        )
        ENGINE = MergeTree()
        PARTITION BY (customer_id, toYYYYMM(ts))
        ORDER BY (customer_id, ts, service, level)
        TTL ts + toIntervalDay(90)
        SETTINGS index_granularity = 8192
        """
        
        # Multi-tenant hourly statistics
        mt_hourly_stats_sql = """
        CREATE TABLE IF NOT EXISTS logs_hourly_stats_mt (
            customer_id LowCardinality(String),
            date Date,
            hour UInt8,
            service LowCardinality(String),
            level LowCardinality(String),
            total_logs UInt64,
            error_count UInt64,
            unique_users UInt64,
            avg_response_time Float32,
            p95_response_time Float32,
            total_bytes UInt64
        )
        ENGINE = SummingMergeTree()
        PARTITION BY (customer_id, toYYYYMM(date))
        ORDER BY (customer_id, date, hour, service, level)
        TTL date + toIntervalDay(365)
        """
        
        tables_sql = [
            mt_logs_raw_sql,
            mt_logs_normalized_sql, 
            mt_hourly_stats_sql
        ]
        
        for sql in tables_sql:
            try:
                await asyncio.to_thread(self.ch_client.command, sql)
                logger.info("Created multi-tenant table")
            except Exception as e:
                logger.error(f"Failed to create multi-tenant table: {e}")
                raise
    
    async def _update_materialized_views(self):
        """Update materialized views for multi-tenant support"""
        
        # Drop old materialized view if exists
        try:
            await asyncio.to_thread(
                self.ch_client.command,
                "DROP VIEW IF EXISTS logs_hourly_stats_mv"
            )
        except:
            pass  # Ignore if doesn't exist
        
        # Create new multi-tenant materialized view
        mv_sql = """
        CREATE MATERIALIZED VIEW IF NOT EXISTS logs_hourly_stats_mt_mv
        TO logs_hourly_stats_mt
        AS SELECT
            customer_id,
            date,
            hour,
            service,
            level,
            count() as total_logs,
            countIf(is_error = 1) as error_count,
            uniq(user_id) as unique_users,
            avg(http_response_time_ms) as avg_response_time,
            quantile(0.95)(http_response_time_ms) as p95_response_time,
            sum(http_bytes) as total_bytes
        FROM logs_normalized_mt
        WHERE customer_id != ''
        GROUP BY customer_id, date, hour, service, level
        """
        
        try:
            await asyncio.to_thread(self.ch_client.command, mv_sql)
            logger.info("Created multi-tenant materialized view")
        except Exception as e:
            logger.error(f"Failed to create materialized view: {e}")
            raise
    
    async def _create_partition_optimization(self):
        """Create partition optimization for better query performance"""
        
        # Create customer-specific views for common query patterns
        customer_view_sql = """
        CREATE VIEW IF NOT EXISTS logs_by_customer AS
        SELECT 
            customer_id,
            ts,
            service,
            level,
            msg,
            host,
            user_id,
            http_status,
            http_response_time_ms,
            is_error
        FROM logs_normalized_mt
        WHERE customer_id IN (
            SELECT DISTINCT customer_id 
            FROM logs_normalized_mt 
            WHERE ts >= now() - INTERVAL 7 DAY
        )
        """
        
        try:
            await asyncio.to_thread(self.ch_client.command, customer_view_sql)
            logger.info("Created partition optimization views")
        except Exception as e:
            logger.error(f"Failed to create partition optimization: {e}")
            raise
    
    async def _create_multitenant_ttl_tables(self):
        """Create TTL management tables for multi-tenant support"""
        
        # Customer TTL policies table
        ttl_policies_sql = """
        CREATE TABLE IF NOT EXISTS customer_ttl_policies (
            customer_id LowCardinality(String),
            deployment_type LowCardinality(String),
            compliance_tier LowCardinality(String),
            hot_storage_days UInt16,
            cold_storage_days UInt16,
            total_retention_days UInt16,
            created_at DateTime64(3, 'UTC'),
            updated_at DateTime64(3, 'UTC')
        )
        ENGINE = ReplacingMergeTree(updated_at)
        ORDER BY customer_id
        """
        
        # TTL execution history table
        ttl_history_sql = """
        CREATE TABLE IF NOT EXISTS ttl_execution_history (
            customer_id LowCardinality(String),
            execution_time DateTime64(3, 'UTC'),
            operation_type LowCardinality(String), -- 'archive', 'delete', 'cleanup'
            records_affected UInt64,
            bytes_processed UInt64,
            duration_ms UInt32,
            status LowCardinality(String), -- 'success', 'error', 'partial'
            error_message String DEFAULT ''
        )
        ENGINE = MergeTree()
        PARTITION BY toYYYYMM(execution_time)
        ORDER BY (customer_id, execution_time)
        TTL execution_time + toIntervalDay(30)
        """
        
        tables = [ttl_policies_sql, ttl_history_sql]
        
        for sql in tables:
            try:
                await asyncio.to_thread(self.ch_client.command, sql)
                logger.info("Created TTL management table")
            except Exception as e:
                logger.error(f"Failed to create TTL table: {e}")
                raise
    
    async def migrate_existing_data(self):
        """Migrate existing data to multi-tenant tables"""
        logger.info("Starting data migration to multi-tenant tables...")
        
        try:
            # Check if old tables have data
            result = await asyncio.to_thread(
                self.ch_client.execute,
                "SELECT count() FROM logs_normalized"
            )
            
            old_count = result[0][0] if result else 0
            
            if old_count > 0:
                logger.info(f"Migrating {old_count} records from old tables...")
                
                # Migrate with default customer_id for existing data
                migrate_sql = """
                INSERT INTO logs_normalized_mt
                SELECT 
                    'migrated-default' as customer_id,
                    ts, date, hour, host, service, level, msg, trace_id, span_id,
                    status, src_ip, user_id, severity_num, facility,
                    extracted_user_id, extracted_ip, http_method, http_uri,
                    http_status, http_response_time_ms, http_bytes,
                    error_code, error_category, ingested_at, is_error, is_slow
                FROM logs_normalized
                WHERE ts >= now() - INTERVAL 30 DAY  -- Only migrate recent data
                """
                
                await asyncio.to_thread(self.ch_client.command, migrate_sql)
                logger.info("Data migration completed")
            
        except Exception as e:
            logger.error(f"Data migration failed: {e}")
            # Non-critical error, continue
    
    async def verify_migration(self) -> Dict[str, Any]:
        """Verify the migration was successful"""
        verification = {
            "status": "success",
            "tables_created": [],
            "data_migrated": False,
            "indexes_created": [],
            "errors": []
        }
        
        try:
            # Check tables exist
            tables_to_check = ['logs_raw_mt', 'logs_normalized_mt', 'logs_hourly_stats_mt']
            
            for table in tables_to_check:
                try:
                    result = await asyncio.to_thread(
                        self.ch_client.execute,
                        f"SELECT count() FROM {table}"
                    )
                    verification["tables_created"].append(table)
                except Exception as e:
                    verification["errors"].append(f"Table {table} not accessible: {e}")
            
            # Check data migration
            try:
                result = await asyncio.to_thread(
                    self.ch_client.execute,
                    "SELECT count() FROM logs_normalized_mt"
                )
                verification["data_migrated"] = result[0][0] > 0 if result else False
            except Exception as e:
                verification["errors"].append(f"Data verification failed: {e}")
            
            if verification["errors"]:
                verification["status"] = "partial"
                
        except Exception as e:
            verification["status"] = "failed"
            verification["errors"].append(f"Verification failed: {e}")
        
        return verification


async def run_migration():
    """Run the multi-tenant migration"""
    print("🔧 Starting Multi-Tenant Schema Migration...")
    
    migrator = MultiTenantSchemaMigration()
    
    # Run migration
    success = await migrator.migrate_to_multitenant()
    
    if success:
        print("✅ Schema migration completed")
        
        # Migrate existing data
        await migrator.migrate_existing_data()
        
        # Verify migration
        verification = await migrator.verify_migration()
        print(f"🔍 Migration verification: {verification['status']}")
        
        if verification["errors"]:
            print("⚠️  Verification warnings:")
            for error in verification["errors"]:
                print(f"   • {error}")
        
        return True
    else:
        print("❌ Schema migration failed")
        return False


if __name__ == "__main__":
    result = asyncio.run(run_migration())
    exit(0 if result else 1)