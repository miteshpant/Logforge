"""
Event Handler

Main orchestrator for handling log ingestion events.
Moved functions exactly as-is from event_processing.py to preserve functionality.
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from models import LogEntry
from .log_processor import process_log_batch_with_client
from .usage_processor import track_usage_with_cost_calculation

logger = logging.getLogger(__name__)

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