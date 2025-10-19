"""
Event Processing Module for Logforge Event-Driven Architecture

This module contains modular functions for processing log ingestion events.
Each function handles a specific aspect of log processing, allowing for
better separation of concerns and easier testing.

Used in the migration from direct database processing to event-driven processing.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from clickhouse_connect import get_client
from models import LogEntry

logger = logging.getLogger(__name__)

# Global config access
config = None

def set_config(app_config):
    """Set the global config for this module"""
    global config
    config = app_config

async def process_log_batch_with_client(logs: List[LogEntry], customer_id: str) -> bool:
    """
    Process log batch with client creation (for event system)
    This matches the old system but creates its own client
    """
    try:
        if not logs:
            logger.warning(f"Empty log batch received for customer {customer_id}")
            return True

        logger.info(f"Processing batch of {len(logs)} logs for customer {customer_id}")

        # Create ClickHouse client
        client = get_client(
            host=config["clickhouse_host"],
            port=config["clickhouse_port"],
            username=config["clickhouse_user"],
            password=config["clickhouse_password"],
            database=config["clickhouse_database"],
            send_receive_timeout=120
        ) if config else None

        if not client:
            logger.error("Failed to create ClickHouse client")
            return False

        try:
            # Call the exact same function as the old system but with our client
            await process_log_batch_internal(logs, client, customer_id)
            return True
        finally:
            client.close()

    except Exception as e:
        logger.error(f"Failed to process log batch for customer {customer_id}: {e}")
        return False


async def process_log_batch_internal(logs: List[LogEntry], client, customer_id: str):
    """
    Internal function that exactly matches the old system's process_log_batch
    This is the EXACT same logic as dependencies.py process_log_batch
    """
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

    # Batch insert to ClickHouse - EXACT same logic as old system
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


async def process_log_batch(logs: List[LogEntry], customer_id: str) -> bool:
    """
    Process log batch and insert into ClickHouse logs_raw_mt table
    
    Args:
        logs: List of LogEntry objects to process
        customer_id: Customer/tenant ID for multi-tenant isolation
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if not logs:
            logger.warning(f"Empty log batch received for customer {customer_id}")
            return True

        logger.info(f"Processing batch of {len(logs)} logs for customer {customer_id}")

        # Create ClickHouse client
        client = get_client(
            host=config["clickhouse_host"],
            port=config["clickhouse_port"],
            username=config["clickhouse_user"],
            password=config["clickhouse_password"],
            database=config["clickhouse_database"],
            send_receive_timeout=120
        ) if config else None

        if not client:
            logger.error("Failed to create ClickHouse client")
            return False

        try:
            # Prepare batch insert data
            rows = []
            for log in logs:
                # Convert LogEntry to ClickHouse row format matching logs_raw_mt schema
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

            # Batch insert to ClickHouse
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
            return True

        finally:
            client.close()

    except Exception as e:
        logger.error(f"Failed to process log batch for customer {customer_id}: {e}")
        return False


async def track_usage_stats(customer_id: str, feature: str, bytes_processed: int, cost: float) -> bool:
    """
    Track usage statistics and update tenant quotas
    
    Args:
        customer_id: Customer/tenant ID
        feature: Feature name (e.g., 'ingestion.basic', 'api.calls')
        bytes_processed: Number of bytes processed
        cost: Calculated cost for the usage
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from services.tenant_service import TenantService
        
        # Map feature to usage type
        usage_type_map = {
            'ingestion.basic': 'monthly_ingestion',
            'api.calls': 'api_calls',
            'queries.basic': 'queries'
        }
        
        usage_type = usage_type_map.get(feature, 'monthly_ingestion')
        
        tenant_service = TenantService()
        await track_usage_with_cost_calculation(
            tenant_service, customer_id, usage_type, bytes_processed
        )
        
        logger.debug(f"Usage tracked for customer {customer_id}: feature={feature}, bytes={bytes_processed}, cost={cost}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to track usage stats for customer {customer_id}: {e}")
        return False


async def update_tenant_quotas(customer_id: str, usage_delta: Dict[str, Any]) -> bool:
    """
    Update tenant quota usage
    
    Args:
        customer_id: Customer/tenant ID
        usage_delta: Dictionary containing usage changes
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from services.tenant_service import TenantService
        
        tenant_service = TenantService()
        
        # Extract relevant data from usage_delta
        bytes_processed = usage_delta.get('bytes_processed', 0)
        
        # Update quotas (this is handled within track_usage_with_cost_calculation)
        await track_usage_with_cost_calculation(
            tenant_service, customer_id, "monthly_ingestion", bytes_processed
        )
        
        logger.debug(f"Tenant quotas updated for customer {customer_id}: {usage_delta}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update tenant quotas for customer {customer_id}: {e}")
        return False


async def track_ingestion_metrics(customer_id: str, endpoint: str, log_count: int, bytes_processed: int, format_type: str, processing_time_ms: int) -> bool:
    """
    Track ingestion metrics and statistics
    
    Args:
        customer_id: Customer/tenant ID
        endpoint: API endpoint used for ingestion
        log_count: Number of logs processed
        bytes_processed: Number of bytes processed
        format_type: Format of ingested logs (json, syslog, etc.)
        processing_time_ms: Processing time in milliseconds
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from services.ingestion_service import IngestionService
        
        ingestion_service = IngestionService()
        await ingestion_service.track_ingestion_success(
            customer_id, endpoint, format_type, log_count, bytes_processed, processing_time_ms
        )
        
        logger.debug(f"Ingestion metrics tracked for customer {customer_id}: endpoint={endpoint}, logs={log_count}, bytes={bytes_processed}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to track ingestion metrics for customer {customer_id}: {e}")
        return False


async def handle_log_ingestion_event(event_data: Dict[str, Any]) -> bool:
    """
    Main orchestrator function for handling log ingestion events
    This function coordinates all the individual processing steps
    
    Args:
        event_data: Dictionary containing event data from Kafka message
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Extract data from event  
        customer_id = event_data.get('customer_id')
        logs_data = event_data.get('logs', [])
        endpoint = event_data.get('ingestion_endpoint', '/logs')  # Fix: Use correct field name
        format_type = event_data.get('source_format', 'json')     # Fix: Use correct field name
        log_count = event_data.get('log_count', len(logs_data))
        bytes_processed = event_data.get('bytes_processed', 0)
        processing_time_ms = event_data.get('processing_time_ms', 0)
        
        # Debug logging to trace endpoint value through event processing
        logger.info(
            f"EVENT_PROCESSING DEBUG: Received event data - customer_id={customer_id}, "
            f"endpoint={endpoint}, format_type={format_type}, logs_count={len(logs_data)}, "
            f"event_data_keys={list(event_data.keys())}, "
            f"ingestion_endpoint_raw={event_data.get('ingestion_endpoint')}, "
            f"source_format_raw={event_data.get('source_format')}"
        )
        
        if not customer_id:
            logger.error("No customer_id in event data")
            return False
            
        logger.info(f"Handling log ingestion event for customer {customer_id}: {log_count} logs, {bytes_processed} bytes")
        logger.info(f"🔍 DEBUG: logs_data type={type(logs_data)}, length={len(logs_data) if logs_data else 0}, content={logs_data[:1] if logs_data else 'None'}")
        
        # Convert logs data back to LogEntry objects if needed
        logs = []
        if logs_data:
            for log_data in logs_data:
                logger.info(f"🔍 DEBUG: Converting log_data type={type(log_data)}, content={log_data}")
                if isinstance(log_data, dict):
                    # Convert dict back to LogEntry
                    try:
                        log_entry = LogEntry(**log_data)
                        logs.append(log_entry)
                        logger.info(f"🔍 DEBUG: Successfully converted to LogEntry: {log_entry}")
                    except Exception as e:
                        logger.error(f"🔍 DEBUG: Failed to convert log_data to LogEntry: {e}")
                        logger.error(f"🔍 DEBUG: Problematic log_data: {log_data}")
                else:
                    logs.append(log_data)
        
        logger.info(f"🔍 DEBUG: Final logs array length={len(logs)}, types={[type(log) for log in logs[:3]]}")
        
        success_count = 0
        total_steps = 3
        
        # DEV MODE: Do exactly what process_logs_and_tracking_async does
        # Map exactly to the old system's 3 steps
        
        # Step 1: Store logs in logs_raw_mt (exactly like old system)
        if await process_log_batch_with_client(logs, customer_id):
            success_count += 1
            logger.debug(f"Step 1/3 completed: Log batch processed for {customer_id}")
        else:
            logger.error(f"Step 1/3 failed: Log batch processing for {customer_id}")
        
        # Step 2: Track usage with proper cost calculation (usage_records_mt + tenant_quotas_mt)
        # This is the EXACT function the old system calls
        from services.tenant_service import TenantService
        tenant_service = TenantService()
        try:
            await track_usage_with_cost_calculation(
                tenant_service, customer_id, "monthly_ingestion", bytes_processed
            )
            success_count += 1
            logger.debug(f"Step 2/3 completed: Usage tracked with cost calculation for {customer_id}")
        except Exception as e:
            logger.error(f"Step 2/3 failed: Usage tracking for {customer_id}: {e}")
        
        # Step 3: Track ingestion statistics (ingestion_stats_mt)  
        # This is the EXACT function the old system calls
        from services.ingestion_service import IngestionService
        ingestion_service = IngestionService()
        try:
            await ingestion_service.track_ingestion_success(
                customer_id, endpoint, format_type, log_count, bytes_processed, processing_time_ms
            )
            success_count += 1
            logger.debug(f"Step 3/3 completed: Ingestion metrics tracked for {customer_id}")
        except Exception as e:
            logger.error(f"Step 3/3 failed: Ingestion metrics tracking for {customer_id}: {e}")
        
        # Log overall success
        success_rate = (success_count / total_steps) * 100
        logger.info(f"Event processing completed for customer {customer_id}: {success_count}/{total_steps} steps successful ({success_rate:.1f}%)")
        
        # Return True if at least log processing succeeded (critical path)
        return success_count >= 1
        
    except Exception as e:
        logger.error(f"Failed to handle log ingestion event: {e}")
        return False


# Helper function for cost calculation (copied exactly from dependencies.py)
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
        feature_rate = await subscription_service.get_feature_rate(feature_name, tenant_id=customer_id)

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