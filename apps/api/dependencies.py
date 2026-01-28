"""
Application dependencies and initialization
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List
from contextlib import asynccontextmanager

from clickhouse_connect import get_client
from clickhouse_connect.driver.exceptions import ClickHouseError

from app_config import load_config
from parsers import ParserFactory
from storage_config import StorageConfigManager
from ttl_manager import TTLManager
from query_engine import AdvancedQueryEngine
from dashboard_engine import DashboardEngine
from alert_engine import AlertEngine
from observability_engine import ObservabilityEngine
from models import LogEntry

# Add events to Python path
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Event system imports
from events.publishers import EventPublisherManager
from events.publishers.log_publisher import LogEventPublisher
from events.publishers.alert_publisher import AlertEventPublisher
from events.subscribers import EventSubscriberManager

logger = logging.getLogger(__name__)

# Global instances
config = None
clickhouse_client = None
storage_manager = None
parser_factory = None
ttl_manager = None
query_engine = None
dashboard_engine = None
alert_engine = None
observability_engine = None
event_publisher_manager = None
event_subscriber_manager = None
log_event_publisher = None
alert_event_publisher = None
alert_rule_cache_instance = None
sigma_rule_cache_instance = None

def get_clickhouse_client():
    """Get or create ClickHouse client"""
    global clickhouse_client, config

    if not clickhouse_client and config:
        try:
            clickhouse_client = get_client(
                host=config["clickhouse_host"],
                port=config["clickhouse_port"],
                username=config["clickhouse_user"],
                password=config["clickhouse_password"],
                database=config["clickhouse_database"],
                send_receive_timeout=120
            )
            logger.info("ClickHouse connection established")
        except ClickHouseError as e:
            logger.error(f"Failed to connect to ClickHouse: {e}")
            raise

    return clickhouse_client

def get_alert_event_publisher():
    """Get alert event publisher instance"""
    global alert_event_publisher
    return alert_event_publisher

def get_event_publisher_manager():
    """Get event publisher manager instance"""
    global event_publisher_manager
    return event_publisher_manager

def get_sigma_rule_cache():
    """Get sigma rule cache instance"""
    global sigma_rule_cache_instance
    return sigma_rule_cache_instance

# process_log_batch() function removed - now handled by event_processing.py

def process_logs_background(logs: List[LogEntry], customer_id: str = "default"):
    """Legacy function - now redirects to event system"""
    try:
        # This function is now deprecated - the event system handles log processing
        # Import the event processing module
        import event_processing
        import asyncio

        # Use event-driven processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(event_processing.process_log_batch(logs, customer_id))
        finally:
            loop.close()

        logger.info(f"Legacy background processing redirected to event system for customer {customer_id}")
    except Exception as e:
        logger.error(f"Legacy background log processing failed: {e}")

def process_logs_and_tracking_background(
    logs: List[LogEntry],
    customer_id: str,
    endpoint: str,
    format_type: str,
    log_count: int,
    bytes_processed: int,
    processing_time_ms: int
):
    """Unified background task for logs processing + all tracking with proper cost calculation"""
    try:
        # Fire-and-forget: create async task that runs independently
        import asyncio
        import threading

        def run_async_in_thread():
            """Run async processing in a separate thread with its own event loop"""
            try:
                # Create a new ClickHouse client instance for this background task
                from clickhouse_connect import get_client
                background_client = get_client(
                    host=config["clickhouse_host"],
                    port=config["clickhouse_port"],
                    username=config["clickhouse_user"],
                    password=config["clickhouse_password"],
                    database=config["clickhouse_database"],
                    send_receive_timeout=120
                ) if config else None

                if not background_client:
                    logger.error("Failed to create background ClickHouse client")
                    return

                # Run the async function in a new event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                try:
                    loop.run_until_complete(
                        process_logs_and_tracking_async(
                            logs, customer_id, endpoint, format_type,
                            log_count, bytes_processed, processing_time_ms,
                            background_client
                        )
                    )
                finally:
                    loop.close()
                    background_client.close()

            except Exception as e:
                logger.error(f"Async background processing failed: {e}")

        # Start the processing in a daemon thread (fire-and-forget)
        thread = threading.Thread(target=run_async_in_thread, daemon=True)
        thread.start()

        logger.info(f"Non-blocking background processing started for customer {customer_id}")

    except Exception as e:
        logger.error(f"Failed to start background processing: {e}")

async def process_logs_and_tracking_async(
    logs: List[LogEntry],
    customer_id: str,
    endpoint: str,
    format_type: str,
    log_count: int,
    bytes_processed: int,
    processing_time_ms: int,
    client
):
    """Event-driven log processing - publish event and let event system handle all processing"""
    try:
        # EVENT-DRIVEN ONLY - Publish log ingestion event for complete processing
        # The event-driven system handles all processing (logs, usage, stats)
        global log_event_publisher

        logger.info(f"🚀 EVENT-DRIVEN: Publishing event for complete processing - customer {customer_id}")

        batch_info = {
            "batch_id": f"batch_{customer_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "log_count": log_count,
            "bytes_processed": bytes_processed,
            "endpoint": endpoint,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success_count": log_count,
            "error_count": 0,
            "logs": [log.model_dump(mode='json') if hasattr(log, 'model_dump') else log.__dict__ for log in logs]
        }

        await log_event_publisher.publish_batch_ingested(
            customer_id=customer_id,
            batch_info=batch_info,
            source_format=format_type,
            processing_time_ms=float(processing_time_ms)
        )

        logger.info(f"🚀 EVENT-DRIVEN: Event published - all processing delegated to event system - customer {customer_id}")
    except Exception as e:
        logger.error(f"🚀 EVENT-DRIVEN: Failed to publish event: {e}")
        raise

# Duplicate functions removed - now handled by event_processing.py:
# - track_usage_with_cost_calculation()
# - update_tenant_quota_only()

async def initialize_engines():
    """Initialize all engines with their dependencies"""
    global storage_manager, parser_factory, ttl_manager, query_engine
    global dashboard_engine, alert_engine, observability_engine
    global event_publisher_manager, event_subscriber_manager, log_event_publisher, alert_event_publisher

    logger.info("Initializing application engines...")

    try:
        # Initialize storage config manager
        storage_manager = StorageConfigManager()
        logger.info("Storage config manager initialized")

        # Initialize parser factory
        parser_factory = ParserFactory()
        logger.info("Parser factory initialized")

        # Get ClickHouse client
        client = get_clickhouse_client()

        # Initialize TTL manager with storage manager
        ttl_manager = TTLManager(client, storage_manager)
        logger.info("TTL manager initialized")

        # Initialize query engine
        query_engine = AdvancedQueryEngine(client)
        logger.info("Query engine initialized")

        # Initialize dashboard engine
        dashboard_engine = DashboardEngine(query_engine)
        logger.info("Dashboard engine initialized")

        # Initialize alert engine
        alert_engine = AlertEngine()
        await alert_engine.start()
        logger.info("Alert engine initialized and started")

        # Initialize observability engine (M5)
        observability_engine = ObservabilityEngine(client)
        logger.info("Observability engine initialized")

        # Initialize event processing module config
        try:
            import event_processing
            event_processing.set_config(config)
            logger.info("Event processing module configured")
        except Exception as e:
            logger.warning(f"Failed to configure event processing module: {e}")

         # Initialize event system
        try:
            # Initialize event publisher manager
            event_publisher_manager = EventPublisherManager()
            await event_publisher_manager.start()
            logger.info("Event publisher manager started")

            # Initialize event subscriber manager
            event_subscriber_manager = EventSubscriberManager()
            await event_subscriber_manager.start()
            logger.info("Event subscriber manager started")

            # Initialize log event publisher
            log_event_publisher = LogEventPublisher(event_publisher_manager)
            logger.info("Log event publisher initialized")

            # Initialize alert event publisher
            alert_event_publisher = AlertEventPublisher(event_publisher_manager)
            logger.info("Alert event publisher initialized")

            logger.info("Event system initialized successfully")

        except Exception as e:
            logger.warning(f"Event system initialization failed: {e}")
            # Event system is optional, don't fail startup
            event_publisher_manager = None
            event_subscriber_manager = None
            log_event_publisher = None
            alert_event_publisher = None

        # Initialize Redis and Rule Caches (Alert + Sigma)
        try:
            logger.info("🔄 Initializing Redis and Rule Caches...")

            # Initialize Redis connection
            from events.management.cache import init_redis
            redis_manager = await init_redis()
            logger.info("✅ Redis connection initialized successfully")

            # Initialize Alert Rule Cache and load rules from database
            from events.management.cache.alert_rule_cache import AlertRuleCache
            alert_rule_cache = AlertRuleCache(redis_manager)

            # Load all alert rules from database into Redis cache
            cache_success = await alert_rule_cache.initialize_cache_from_db()
            if cache_success:
                logger.info("✅ Alert rule cache initialized and loaded from database")
            else:
                logger.warning("⚠️ Alert rule cache initialization completed with some failures")

            # Make alert rule cache globally available
            global alert_rule_cache_instance
            alert_rule_cache_instance = alert_rule_cache

            # Check for MITRE Rules Migration and Load if Needed
            try:
                logger.info("🔍 Checking MITRE rules migration status...")

                from dao.security_dao import SecurityDAO
                security_dao = SecurityDAO()

                # Check if migration marker exists and rules need to be loaded
                if await security_dao.should_load_mitre_rules():
                    logger.info("🎯 Loading default MITRE ATT&CK rules from migration...")
                    from mitre_default_loader import mitre_default_loader

                    # Load default MITRE rules into database (migration-triggered)
                    mitre_result = await mitre_default_loader.load_default_mitre_rules()

                    if mitre_result["status"] == "success":
                        # Mark migration as completed
                        await security_dao.mark_mitre_migration_completed()
                        logger.info(f"✅ Migration completed: {mitre_result['rules_loaded']}/{mitre_result['total_techniques']} MITRE rules loaded ({mitre_result['success_rate']:.1f}% success)")
                    else:
                        logger.warning(f"⚠️ MITRE rules migration completed with issues: {mitre_result.get('error', 'Unknown error')}")
                else:
                    mitre_count = await security_dao.get_mitre_rules_count()
                    logger.info(f"ℹ️ MITRE rules already loaded ({mitre_count}/286) or migration not required")

            except Exception as e:
                logger.error(f"❌ MITRE rules migration check failed: {e}")
                # Continue startup even if MITRE loading fails

            # Initialize Sigma Rule Cache and load rules from database
            from events.management.cache.sigma_rule_cache import SigmaRuleCache
            sigma_rule_cache = SigmaRuleCache(redis_manager)

            # Load all sigma rules from database into Redis cache (includes default MITRE rules)
            sigma_cache_success = await sigma_rule_cache.initialize_cache_from_db()
            if sigma_cache_success:
                logger.info("✅ Sigma rule cache initialized and loaded from database")
            else:
                logger.warning("⚠️ Sigma rule cache initialization completed with some failures")

            # Make sigma rule cache globally available
            global sigma_rule_cache_instance
            sigma_rule_cache_instance = sigma_rule_cache

        except Exception as e:
            logger.error(f"❌ Redis/Alert cache initialization failed: {e}")
            # This is not critical for startup, so don't fail
            alert_rule_cache_instance = None

        # Initialize quota reset scheduler (disabled during development)
        # TODO: Enable after database permissions are updated in container
        # from services.quota_reset_service import get_quota_reset_scheduler
        # scheduler = get_quota_reset_scheduler()
        # asyncio.create_task(scheduler.start_scheduler())
        logger.info("Quota reset scheduler initialization skipped (development mode)")

        logger.info("All engines initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize engines: {e}")
        raise

async def shutdown_engines():
    """Cleanup and shutdown all engines"""
    global event_publisher_manager, event_subscriber_manager, alert_rule_cache_instance

    logger.info("Shutting down application engines...")

    try:
        # First, gracefully shutdown all streaming connections
        try:
            from services.streaming_connection_manager import get_streaming_connection_manager
            streaming_manager = get_streaming_connection_manager()
            connection_count = streaming_manager.get_connection_count()
            if connection_count > 0:
                logger.info(f"Shutting down {connection_count} active streaming connections...")
            await streaming_manager.shutdown(timeout=5.0)
            logger.info("Streaming connections shutdown complete")
        except Exception as e:
            logger.warning(f"Error shutting down streaming connections: {e}")

        # Shutdown event system first
        if event_subscriber_manager:
            await event_subscriber_manager.stop()
            logger.info("Event subscriber manager stopped")

        if event_publisher_manager:
            await event_publisher_manager.stop()
            logger.info("Event publisher manager stopped")

        if alert_engine:
            await alert_engine.stop()
            logger.info("Alert engine stopped")

        if observability_engine:
            await observability_engine.shutdown()
            logger.info("Observability engine shutdown")

        # Cleanup Redis connection
        try:
            from events.management.cache import cleanup_redis
            await cleanup_redis()
            logger.info("Redis connection cleaned up")
        except Exception as e:
            logger.warning(f"Error cleaning up Redis: {e}")

        # Stop quota reset scheduler (disabled during development)
        # TODO: Enable after database permissions are updated in container
        # from services.quota_reset_service import get_quota_reset_scheduler
        # scheduler = get_quota_reset_scheduler()
        # scheduler.stop_scheduler()
        logger.info("Quota reset scheduler shutdown skipped (development mode)")

        if clickhouse_client:
            clickhouse_client.close()
            logger.info("ClickHouse connection closed")

        logger.info("All engines shutdown successfully")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

def setup_router_dependencies():
    """Setup dependencies for all routers"""
    from routers import ingestion, query, dashboard, storage, alerts

    # Setup router dependencies
    ingestion.setup_dependencies(parser_factory, process_logs_background, process_logs_and_tracking_background)
    query.setup_dependencies(query_engine, clickhouse_client)
    dashboard.setup_dependencies(dashboard_engine)
    storage.setup_dependencies(ttl_manager)
    alerts.setup_dependencies(alert_engine)

@asynccontextmanager
async def lifespan(app):
    """Application lifespan manager"""
    global config

    # Startup
    logger.info("Starting Logforge API server...")

    # Load configuration
    config = load_config()
    logger.info("Configuration loaded")

    # Initialize engines
    await initialize_engines()

    # Setup router dependencies
    setup_router_dependencies()

    # Start storage quota sync service
    try:
        from services.storage_quota_sync_service import storage_quota_sync_service
        storage_quota_sync_service.start_periodic_sync()
        logger.info("Storage quota sync service started")
    except Exception as e:
        logger.warning(f"Failed to start storage quota sync service: {str(e)}")

    # Initialize write buffer service for batched ClickHouse writes
    try:
        from services.write_buffer_service import init_write_buffer, BufferConfig
        # Configure buffer: flush every 100 logs or 100ms, whichever comes first
        buffer_config = BufferConfig(
            max_buffer_size=100,
            flush_interval_ms=100
        )
        await init_write_buffer(buffer_config)
        logger.info("Write buffer service started (batch size: 100, interval: 100ms)")
    except Exception as e:
        logger.warning(f"Failed to start write buffer service: {str(e)}")

    # Initialize connection pools for improved performance
    try:
        from utils.connection_pool import initialize_pools
        await initialize_pools()
        logger.info("Connection pools initialized (ClickHouse + HTTP)")
    except Exception as e:
        logger.warning(f"Failed to initialize connection pools: {str(e)}")

    logger.info("Logforge API server started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Logforge API server...")

    # Stop storage quota sync service
    try:
        from services.storage_quota_sync_service import storage_quota_sync_service
        storage_quota_sync_service.stop_periodic_sync()
        logger.info("Storage quota sync service stopped")
    except Exception as e:
        logger.warning(f"Failed to stop storage quota sync service: {str(e)}")

    # Shutdown write buffer service (flushes remaining logs)
    try:
        from services.write_buffer_service import shutdown_write_buffer
        await shutdown_write_buffer()
        logger.info("Write buffer service stopped (remaining logs flushed)")
    except Exception as e:
        logger.warning(f"Failed to stop write buffer service: {str(e)}")

    # Close connection pools
    try:
        from utils.connection_pool import close_pools
        await close_pools()
        logger.info("Connection pools closed")
    except Exception as e:
        logger.warning(f"Failed to close connection pools: {str(e)}")

    await shutdown_engines()
    logger.info("Logforge API server shutdown complete")
