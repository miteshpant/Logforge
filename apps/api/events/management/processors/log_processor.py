"""
Log Processor

Handles log processing operations including batch insertion to ClickHouse.
Moved functions exactly as-is from event_processing.py to preserve functionality.
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
