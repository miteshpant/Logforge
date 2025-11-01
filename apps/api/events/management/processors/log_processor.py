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


async def process_dual_write_optimized(
    raw_table_data: List[Dict[str, Any]], 
    normalized_table_data: List[Dict[str, Any]], 
    customer_id: str
) -> bool:
    """
    Optimized dual-write to both logs_raw_mt and logs_normalized_mt tables
    Targets <2ms total write time for market-leading performance
    
    Args:
        raw_table_data: Prepared data for logs_raw_mt table
        normalized_table_data: Prepared data for logs_normalized_mt table  
        customer_id: Customer/tenant ID for multi-tenant isolation
        
    Returns:
        bool: True if both writes successful, False otherwise
    """
    if not raw_table_data and not normalized_table_data:
        logger.warning(f"Empty dual-write batch received for customer {customer_id}")
        return True
        
    start_time = datetime.now()
    
    try:
        # Create single ClickHouse client for both operations
        client = get_client(
            host=config["clickhouse_host"],
            port=config["clickhouse_port"],
            username=config["clickhouse_user"],
            password=config["clickhouse_password"],
            database=config["clickhouse_database"],
            send_receive_timeout=30  # Reduced timeout for performance
        ) if config else None

        if not client:
            logger.error("Failed to create ClickHouse client for dual-write")
            return False

        try:
            write_start = datetime.now()
            
            # Write 1: Raw logs table (original format for compliance/audit)
            if raw_table_data:
                raw_rows = []
                for raw_data in raw_table_data:
                    row = [
                        raw_data.get("ts", datetime.now(timezone.utc)),
                        raw_data.get("host", ""),
                        raw_data.get("service", "unknown"),
                        raw_data.get("level", "info"),
                        raw_data.get("msg", ""),
                        raw_data.get("trace_id", ""),
                        raw_data.get("span_id", ""),
                        json.dumps(raw_data.get("attrs", {}), default=str),
                        raw_data.get("status", 0),
                        raw_data.get("src_ip", ""),
                        raw_data.get("user_id", ""),
                        raw_data.get("ingested_at", datetime.now(timezone.utc)),
                        raw_data.get("severity_num", 0),
                        raw_data.get("facility", 16),
                        raw_data.get("parser_version", "smart_v1"),
                        customer_id
                    ]
                    raw_rows.append(row)
                
                client.insert(
                    "logs_raw_mt",
                    raw_rows,
                    column_names=[
                        "ts", "host", "service", "level", "msg", "trace_id", "span_id",
                        "attrs", "status", "src_ip", "user_id", "ingested_at",
                        "severity_num", "facility", "parser_version", "customer_id"
                    ]
                )
                
                raw_write_time = (datetime.now() - write_start).total_seconds() * 1000
                logger.debug(f"Raw table write completed in {raw_write_time:.2f}ms")
            
            # Write 2: Normalized logs table (for analytics/Sigma rules)
            # Schema: ts, date, hour, host, service, level, msg, trace_id, span_id, status, src_ip, user_id, severity_num, facility, ingested_at, customer_id
            if normalized_table_data:
                norm_start = datetime.now()
                norm_rows = []
                
                for norm_data in normalized_table_data:
                    ts_value = norm_data.get("ts", datetime.now(timezone.utc))
                    if isinstance(ts_value, str):
                        # Parse ISO string to datetime
                        try:
                            ts_value = datetime.fromisoformat(ts_value.replace('Z', '+00:00'))
                        except:
                            ts_value = datetime.now(timezone.utc)
                    
                    # Build normalized row matching logs_normalized_mt schema (NO attrs column)
                    row = [
                        ts_value,  # ts
                        ts_value.date(),  # date (derived from ts)
                        ts_value.hour,  # hour (derived from ts)
                        norm_data.get("host", ""),  # host
                        norm_data.get("service", "unknown"),  # service
                        norm_data.get("level", "info"),  # level
                        norm_data.get("msg", ""),  # msg
                        norm_data.get("trace_id", ""),  # trace_id
                        norm_data.get("span_id", ""),  # span_id
                        norm_data.get("status", 0),  # status
                        norm_data.get("src_ip", ""),  # src_ip (using normalized field name)
                        norm_data.get("user", ""),  # user_id (using normalized field name)
                        norm_data.get("severity_num", 0),  # severity_num
                        norm_data.get("facility", 16),  # facility
                        norm_data.get("ingested_at", datetime.now(timezone.utc)),  # ingested_at
                        customer_id  # customer_id
                    ]
                    norm_rows.append(row)
                
                client.insert(
                    "logs_normalized_mt",
                    norm_rows,
                    column_names=[
                        "ts", "date", "hour", "host", "service", "level", "msg", 
                        "trace_id", "span_id", "status", "src_ip", "user_id", 
                        "severity_num", "facility", "ingested_at", "customer_id"
                    ]
                )
                
                norm_write_time = (datetime.now() - norm_start).total_seconds() * 1000
                logger.debug(f"Normalized table write completed in {norm_write_time:.2f}ms")
            
            # Calculate total performance metrics
            total_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            total_records = len(raw_table_data) + len(normalized_table_data)
            
            # Performance validation (<2ms target)
            performance_target_met = total_time_ms < 2.0
            if not performance_target_met:
                logger.warning(f"Dual-write performance target missed: {total_time_ms:.2f}ms (target: <2ms)")
            
            logger.info(
                f"Dual-write completed for customer {customer_id}: "
                f"{len(raw_table_data)} raw + {len(normalized_table_data)} normalized records "
                f"in {total_time_ms:.2f}ms "
                f"({total_time_ms/total_records:.3f}ms per record) "
                f"{'✅ TARGET MET' if performance_target_met else '⚠️ TARGET MISSED'}"
            )
            
            return True

        finally:
            client.close()

    except Exception as e:
        total_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"Dual-write failed for customer {customer_id} after {total_time_ms:.2f}ms: {e}")
        return False


async def process_normalized_write_only(
    normalized_table_data: List[Dict[str, Any]], 
    customer_id: str
) -> bool:
    """
    Write only to logs_normalized_mt table (for normalized log writer consumer)
    
    Args:
        normalized_table_data: Prepared data for logs_normalized_mt table  
        customer_id: Customer/tenant ID for multi-tenant isolation
        
    Returns:
        bool: True if write successful, False otherwise
    """
    if not normalized_table_data:
        logger.warning(f"Empty normalized batch received for customer {customer_id}")
        return True
        
    start_time = datetime.now()
    
    try:
        # Create ClickHouse client for normalized write only
        client = get_client(
            host=config["clickhouse_host"],
            port=config["clickhouse_port"],
            username=config["clickhouse_user"],
            password=config["clickhouse_password"],
            database=config["clickhouse_database"],
            send_receive_timeout=30
        ) if config else None

        if not client:
            logger.error("Failed to create ClickHouse client for normalized write")
            return False

        try:
            norm_rows = []
            
            for norm_data in normalized_table_data:
                ts_value = norm_data.get("ts", datetime.now(timezone.utc))
                if isinstance(ts_value, str):
                    # Parse ISO string to datetime
                    try:
                        ts_value = datetime.fromisoformat(ts_value.replace('Z', '+00:00'))
                    except:
                        ts_value = datetime.now(timezone.utc)
                
                # Parse ingested_at the same way
                ingested_at_value = norm_data.get("ingested_at", datetime.now(timezone.utc))
                if isinstance(ingested_at_value, str):
                    try:
                        ingested_at_value = datetime.fromisoformat(ingested_at_value.replace('Z', '+00:00'))
                    except:
                        ingested_at_value = datetime.now(timezone.utc)
                
                # Build normalized row matching logs_normalized_mt schema
                # Schema: ts, date, hour, host, service, level, msg, trace_id, span_id, status, src_ip, user_id, severity_num, facility, ingested_at, customer_id
                row = [
                    ts_value,  # ts
                    ts_value.date(),  # date (derived from ts)
                    ts_value.hour,  # hour (derived from ts)
                    norm_data.get("host", ""),  # host
                    norm_data.get("service", "unknown"),  # service
                    norm_data.get("level", "info"),  # level
                    norm_data.get("msg", ""),  # msg
                    norm_data.get("trace_id", ""),  # trace_id
                    norm_data.get("span_id", ""),  # span_id
                    norm_data.get("status", 0),  # status
                    norm_data.get("src_ip", ""),  # src_ip (normalized field name from field mapping)
                    norm_data.get("user", "") or norm_data.get("user_id", ""),  # user_id (field mapping creates 'user', fallback to 'user_id')
                    norm_data.get("severity_num", 0),  # severity_num
                    norm_data.get("facility", 16),  # facility
                    ingested_at_value,  # ingested_at
                    customer_id  # customer_id
                ]
                norm_rows.append(row)
            
            # Insert to logs_normalized_mt only
            client.insert(
                "logs_normalized_mt",
                norm_rows,
                column_names=[
                    "ts", "date", "hour", "host", "service", "level", "msg", 
                    "trace_id", "span_id", "status", "src_ip", "user_id", 
                    "severity_num", "facility", "ingested_at", "customer_id"
                ]
            )
            
            # Calculate performance metrics
            write_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            # Performance validation (<2ms target)
            performance_target_met = write_time_ms < 2.0
            if not performance_target_met:
                logger.warning(f"Normalized write performance target missed: {write_time_ms:.2f}ms (target: <2ms)")
            
            logger.info(
                f"Normalized write completed for customer {customer_id}: "
                f"{len(normalized_table_data)} records in {write_time_ms:.2f}ms "
                f"({write_time_ms/len(normalized_table_data):.3f}ms per record) "
                f"{'✅ TARGET MET' if performance_target_met else '⚠️ TARGET MISSED'}"
            )
            
            return True

        finally:
            client.close()

    except Exception as e:
        write_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"Normalized write failed for customer {customer_id} after {write_time_ms:.2f}ms: {e}")
        return False
