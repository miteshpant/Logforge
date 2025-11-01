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

        if not customer_id:
            logger.error("No customer_id in event data")
            return False
        # Convert logs data back to LogEntry objects if needed
        logs = []
        if logs_data:
            for log_data in logs_data:
                if isinstance(log_data, dict):
                    # Convert dict back to LogEntry
                    try:
                        log_entry = LogEntry(**log_data)
                        logs.append(log_entry)
                    except Exception as e:
                        logger.error(f"🔍 DEBUG: Failed to convert log_data to LogEntry: {e}")
                else:
                    logs.append(log_data)


        success_count = 0
        total_steps = 3

        # DEV MODE: Do exactly what process_logs_and_tracking_async does
        # Map exactly to the old system's 3 steps

        # Step 1: Smart normalization + logs_raw_mt write (Phase 2 enhancement)
        normalized_data = None
        try:
            from services.smart_ingestion_service import get_smart_ingestion_service
            smart_service = get_smart_ingestion_service()
            
            # Process logs with single-pass normalization (generates both raw LogEntry and normalized data)
            ingestion_result = await smart_service.process_logs_with_normalization(
                logs_data, customer_id, format_type
            )
            
            # Write ONLY to logs_raw_mt (for customer alerts on raw data)
            raw_write_success = await process_log_batch_with_client(ingestion_result.log_entries, customer_id)
            
            if raw_write_success:
                success_count += 1
                # Store normalized data for event publishing (consumers will write to logs_normalized_mt)
                normalized_data = ingestion_result.normalized_data
                logger.debug(f"Step 1/3 completed: Smart ingestion + raw log storage for {customer_id}")
            else:
                logger.error(f"Step 1/3 failed: Smart ingestion for {customer_id}")
                
        except Exception as e:
            logger.error(f"Step 1/3 failed: Smart ingestion error for {customer_id}: {e}")
            # Fallback to original log processing
            if await process_log_batch_with_client(logs, customer_id):
                success_count += 1
                logger.debug(f"Step 1/3 completed (fallback): Raw log processing for {customer_id}")

        # Step 2: Track usage with proper cost calculation (usage_records_mt + tenant_quotas_mt)
        from services.tenant_service import TenantService
        tenant_service = TenantService()
        try:
            await track_usage_with_cost_calculation(
                tenant_service, customer_id, "monthly_ingestion", bytes_processed
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Step 2/3 failed: Usage tracking for {customer_id}: {e}")

        # Step 3: Track ingestion statistics (ingestion_stats_mt)
        from services.ingestion_service import IngestionService
        ingestion_service = IngestionService()
        try:
            await ingestion_service.track_ingestion_success(
                customer_id, endpoint, format_type, log_count, bytes_processed, processing_time_ms
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Step 3/3 failed: Ingestion metrics tracking for {customer_id}: {e}")

        # Step 4: Process alert rules against RAW logs (preserves customer alert rules)
        try:
            from .sigma_processor import sigma_processor
            
            # Create event data for alert processing (using raw logs as customers expect)
            alert_event_data = {
                'customer_id': customer_id,
                'logs': logs_data,  # Raw logs for customer alert rules
                'ingestion_endpoint': endpoint,
                'source_format': format_type,
                'log_count': log_count,
                'bytes_processed': bytes_processed,
                'processing_time_ms': processing_time_ms
            }
            
            # Process logs through alert engine (matches raw logs)
            alert_success = await sigma_processor.process_log_batch(alert_event_data)
            
            if alert_success:
                logger.debug(f"Step 4: Alert rule processing completed for {customer_id}")
            else:
                logger.warning(f"Step 4: Alert rule processing failed for {customer_id}")
            
        except Exception as e:
            logger.error(f"Step 4: Alert rule processing error for {customer_id}: {e}")

        # Step 5: Publish logs.normalized event for Sigma processing (if normalization succeeded)
        if normalized_data:
            try:
                from events.publishers.log_publisher import LogEventPublisher
                from events.constants import EVENT_LOGS_NORMALIZED
                
                publisher = LogEventPublisher()
                
                # Publish normalized logs event for Sigma engine consumer
                publish_success = await publisher.publish_normalized_batch(
                    normalized_logs=normalized_data,
                    customer_id=customer_id,
                    batch_info={
                        'batch_id': event_data.get('batch_id', f"batch_{datetime.now().isoformat()}"),
                        'source_format': format_type,
                        'ingestion_endpoint': endpoint,
                        'log_count': log_count,
                        'original_event': event_data
                    }
                )
                
                if publish_success:
                    logger.debug(f"Step 5: Published logs.normalized event for {customer_id}")
                else:
                    logger.warning(f"Step 5: Failed to publish logs.normalized event for {customer_id}")
                    
            except Exception as e:
                logger.error(f"Step 5: Event publishing error for {customer_id}: {e}")

        # Log overall success
        success_rate = (success_count / total_steps) * 100
        logger.info(f"Event processing completed for customer {customer_id}: {success_count}/{total_steps} core steps successful ({success_rate:.1f}%)")

        # Return True if at least log processing succeeded (critical path)
        return success_count >= 1

    except Exception as e:
        logger.error(f"Failed to handle log ingestion event: {e}")
        return False
