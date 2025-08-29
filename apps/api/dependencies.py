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
            row = [
                customer_id,  # customer_id for multi-tenancy (first column)
                log.ts or datetime.now(timezone.utc),
                log.level or "info",
                log.msg or "",
                log.host or "unknown", 
                log.service or "unknown",
                log.trace_id or "",
                log.span_id or "",
                json.dumps(log.model_dump(mode='json'), default=str) if hasattr(log, 'model_dump') else json.dumps(log.__dict__, default=str),  # raw_data
                log.ingested_at or datetime.now(timezone.utc)
            ]
            rows.append(row)
        
        # Batch insert to ClickHouse matching actual table schema
        client.insert(
            "logs_raw_mt",
            rows,
            column_names=[
                "customer_id", "ts", "level", "msg", "host", "service", 
                "trace_id", "span_id", "raw_data", "ingested_at"
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

async def initialize_engines():
    """Initialize all engines with their dependencies"""
    global storage_manager, parser_factory, ttl_manager, query_engine
    global dashboard_engine, alert_engine, observability_engine
    
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
        
        logger.info("All engines initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize engines: {e}")
        raise

async def shutdown_engines():
    """Cleanup and shutdown all engines"""
    logger.info("Shutting down application engines...")
    
    try:
        if alert_engine:
            await alert_engine.stop()
            logger.info("Alert engine stopped")
        
        if observability_engine:
            await observability_engine.shutdown()
            logger.info("Observability engine shutdown")
        
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
    ingestion.setup_dependencies(parser_factory, process_logs_background)
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
    
    logger.info("Logforge API server started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Logforge API server...")
    await shutdown_engines()
    logger.info("Logforge API server shutdown complete")