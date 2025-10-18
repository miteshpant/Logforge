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

async def process_log_batch(logs: List[LogEntry], client, customer_id: str = "default"):
    """Background task for async log processing with multi-tenancy support"""
    try:
        if not logs:
            return

        logger.info(f"Processing batch of {len(logs)} logs for customer {customer_id}")

        # Prepare batch insert data
        rows = []
        for log in logs:
            # Convert LogEntry to ClickHouse row format matching logs_raw_mt schema
            # Schema: ts, host, service, level, msg, trace_id, span_id, attrs, status, src_ip, user_id, ingested_at, severity_num, facility, parser_version, customer_id
            row = [
                log.ts or datetime.now(timezone.utc),  # ts
                log.host or "unknown",  # host
                log.service or "unknown",  # service
                log.level or "info",  # level
                log.msg or "",  # msg
                log.trace_id or "",  # trace_id
                log.span_id or "",  # span_id
                json.dumps(log.model_dump(mode='json'), default=str) if hasattr(log, 'model_dump') else json.dumps(log.__dict__, default=str),  # attrs
                0,  # status (UInt16, default 0)
                getattr(log, 'src_ip', ''),  # src_ip
                getattr(log, 'user_id', ''),  # user_id
                log.ingested_at or datetime.now(timezone.utc),  # ingested_at
                0,  # severity_num (UInt8, default 0)
                16,  # facility (UInt8, default 16)
                'v1',  # parser_version (default 'v1')
                customer_id  # customer_id (last column)
            ]
            rows.append(row)

        # Batch insert to ClickHouse matching actual table schema
        client.insert(
            "logs_raw_mt",
            rows,
            column_names=[
                "ts", "host", "service", "level", "msg", "trace_id", "span_id",
                "attrs", "status", "src_ip", "user_id", "ingested_at",
                "severity_num", "facility", "parser_version", "customer_id"
            ]
        )

        logger.info(f"Successfully inserted {len(logs)} logs for customer {customer_id}")

        # TTL cleanup is handled by the TTL manager's scheduled tasks

    except Exception as e:
        logger.error(f"Failed to process log batch for customer {customer_id}: {e}")
        raise

def process_logs_background(logs: List[LogEntry], customer_id: str = "default"):
    """Wrapper for background task execution"""
    try:
        # Create a new ClickHouse client instance for this background task to avoid concurrent queries
        from clickhouse_connect import get_client
        background_client = get_client(
            host=config["clickhouse_host"],
            port=config["clickhouse_port"],
            username=config["clickhouse_user"],
            password=config["clickhouse_password"],
            database=config["clickhouse_database"],
            send_receive_timeout=120
        ) if config else None

        if background_client:
            # Run the async function in a new event loop since we're in a thread
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(process_log_batch(logs, background_client, customer_id))
            finally:
                loop.close()
                # Close the background client
                background_client.close()
    except Exception as e:
        logger.error(f"Background log processing failed: {e}")

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
    """Async function for comprehensive log processing and tracking"""
    try:
        # Import services within the function to avoid circular imports
        from services.tenant_service import TenantService
        from services.ingestion_service import IngestionService

        # 1. Store logs in logs_raw_mt (existing functionality)
        await process_log_batch(logs, client, customer_id)

        # 2. Track usage with proper cost calculation (usage_records_mt + tenant_quotas_mt)
        tenant_service = TenantService()
        await track_usage_with_cost_calculation(
            tenant_service, customer_id, "monthly_ingestion", bytes_processed
        )

        # 3. Track ingestion statistics (ingestion_stats_mt)
        ingestion_service = IngestionService()
        await ingestion_service.track_ingestion_success(
            customer_id, endpoint, format_type, log_count, bytes_processed, processing_time_ms
        )

        # 4. Publish log ingestion event (if event system is available)
        global log_event_publisher
        if log_event_publisher:
            try:
                batch_info = {
                    "batch_id": f"batch_{customer_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                    "log_count": log_count,
                    "bytes_processed": bytes_processed,
                    "endpoint": endpoint,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "success_count": log_count,  # Assuming all logs processed successfully
                    "error_count": 0
                }

                await log_event_publisher.publish_batch_ingested(
                    customer_id=customer_id,
                    batch_info=batch_info,
                    source_format=format_type,
                    processing_time_ms=float(processing_time_ms)
                )
                logger.debug(f"Log ingestion event published for customer {customer_id}")

            except Exception as e:
                logger.warning(f"Failed to publish log ingestion event: {e}")

        logger.info(f"Complete log processing and tracking finished: customer_id={customer_id}, endpoint={endpoint}, log_count={log_count}, bytes_processed={bytes_processed}")

    except Exception as e:
        logger.error("Failed comprehensive log processing", exc_info=e)
        raise

async def track_usage_with_cost_calculation(tenant_service, customer_id: str, usage_type: str, bytes_processed: int):
    """Track usage with proper cost calculation using actual bytes"""
    try:
        from services.subscription_service import SubscriptionService
        import json
        from datetime import datetime, timezone
        import uuid

        subscription_service = SubscriptionService()

        # Map usage type to feature name for pricing
        feature_map = {
            'monthly_ingestion': 'ingestion.basic',
            'api_calls': 'api.calls',
            'queries': 'queries.basic',
            'storage': 'storage.hot',
            'alerts': 'alerts.basic'
        }

        feature_name = feature_map.get(usage_type, usage_type)

        # Get the feature rate for this tenant
        feature_rate = await subscription_service.get_feature_rate(feature_name, customer_id)

        # Calculate cost based on actual bytes (convert to GB for ingestion)
        cost_calculated = 0.0
        rate_applied = 0.0

        logger.info(f"Debug cost calculation: feature_name={feature_name}, feature_rate={feature_rate}, bytes_processed={bytes_processed}")

        if feature_rate:
            if 'ingestion' in feature_name:
                # Convert bytes to GB for pricing calculation
                gb_ingested = bytes_processed / (1024 * 1024 * 1024)
                cost_calculated = feature_rate.base_rate * gb_ingested
                logger.info(f"Ingestion cost calc: gb_ingested={gb_ingested}, base_rate={feature_rate.base_rate}, cost={cost_calculated}")
            elif 'api.calls' in feature_name:
                # API calls: rate is per 1000 calls, convert to per-call rate
                per_call_rate = feature_rate.base_rate / 1000.0
                cost_calculated = per_call_rate * bytes_processed
                logger.info(f"API calls cost calc: per_call_rate={per_call_rate}, calls={bytes_processed}, cost={cost_calculated}")
            elif 'queries' in feature_name:
                # Queries: rate is per 1000 queries, convert to per-query rate
                per_query_rate = feature_rate.base_rate / 1000.0
                cost_calculated = per_query_rate * bytes_processed
                logger.info(f"Queries cost calc: per_query_rate={per_query_rate}, queries={bytes_processed}, cost={cost_calculated}")
            else:
                # For other features, bytes represent different units
                cost_calculated = feature_rate.base_rate * bytes_processed
                logger.info(f"Other cost calc: base_rate={feature_rate.base_rate}, bytes={bytes_processed}, cost={cost_calculated}")
            rate_applied = feature_rate.base_rate
        else:
            logger.warning(f"No feature rate found for {feature_name}, cost will be 0")

        # Update tenant quota directly (without creating duplicate usage record)
        await update_tenant_quota_only(tenant_service, customer_id, usage_type, 1)

        # Create detailed usage record with proper cost calculation
        usage_record = {
            'id': str(uuid.uuid4()),
            'tenant_id': customer_id,
            'customer_id': customer_id,
            'feature_name': feature_name,
            'usage_type': usage_type,
            'quantity': bytes_processed,  # Store actual bytes
            'timestamp': datetime.now(timezone.utc),
            'billing_period': datetime.now(timezone.utc).strftime('%Y-%m'),
            'cost_calculated': round(cost_calculated, 10) if cost_calculated > 0 else 0,
            'rate_applied': round(rate_applied, 6),
            'metadata': json.dumps({
                'original_usage_type': usage_type,
                'bytes_processed': bytes_processed,
                'gb_calculated': bytes_processed / (1024 * 1024 * 1024) if 'ingestion' in feature_name else 0
            }),
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc)
        }

        # Insert usage record with cost calculation
        from dao.subscription_dao import SubscriptionDAO
        subscription_dao = SubscriptionDAO()
        await subscription_dao.create_usage_record(usage_record)

        logger.info(f"Usage tracked with accurate cost calculation: customer_id={customer_id}, feature={feature_name}, bytes_processed={bytes_processed}, cost={cost_calculated}, rate={rate_applied}")

    except Exception as e:
        logger.warning(f"Cost calculation failed in background: customer_id={customer_id}, usage_type={usage_type}, error={str(e)}")

async def update_tenant_quota_only(tenant_service, customer_id: str, usage_type: str, amount: int = 1):
    """Update tenant quota without creating usage record"""
    try:
        # Get current quota for this usage type
        db_quotas = await tenant_service.tenant_dao.get_tenant_quotas(customer_id)

        # Find the relevant quota and update usage
        for quota in db_quotas:
            if quota['quota_type'] == f"{usage_type}_quota" or quota['quota_type'] == usage_type:
                current_used = quota['current_usage']
                new_used = current_used + amount

                # Update usage in database
                await tenant_service.tenant_dao.update_tenant_quota(
                    customer_id,
                    quota['quota_type'],
                    {'current_usage': new_used}
                )
                logger.debug(f"Quota updated: customer_id={customer_id}, usage_type={usage_type}, amount={amount}")
                break

    except Exception as e:
        logger.warning(f"Failed to update quota: customer_id={customer_id}, usage_type={usage_type}, error={str(e)}")

async def initialize_engines():
    """Initialize all engines with their dependencies"""
    global storage_manager, parser_factory, ttl_manager, query_engine
    global dashboard_engine, alert_engine, observability_engine
    global event_publisher_manager, event_subscriber_manager, log_event_publisher

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

            logger.info("Event system initialized successfully")

        except Exception as e:
            logger.warning(f"Event system initialization failed: {e}")
            # Event system is optional, don't fail startup
            event_publisher_manager = None
            event_subscriber_manager = None
            log_event_publisher = None

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
    global event_publisher_manager, event_subscriber_manager

    logger.info("Shutting down application engines...")

    try:
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

    await shutdown_engines()
    logger.info("Logforge API server shutdown complete")
