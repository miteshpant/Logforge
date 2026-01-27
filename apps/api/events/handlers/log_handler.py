"""
Log Event Handler - Handles log lifecycle events
"""

from typing import List
import structlog

from .base import EventHandler
from ..base import BaseEvent
from ..constants import (
    EVENT_LOGS_BATCH_INGESTED,
    EVENT_LOGS_PARSED,
    EVENT_LOGS_INDEXED,
    EVENT_LOGS_ARCHIVED,
    EVENT_LOGS_DELETED,
    EVENT_LOGS_NORMALIZED
)

logger = structlog.get_logger(__name__)


class LogEventHandler(EventHandler):
    """Handler for log lifecycle events"""

    async def handle(self, event: BaseEvent) -> bool:
        """Handle log events"""
        logger.info(
            "Processing log event",
            event_id=event.metadata.event_id,
            customer_id=event.customer_id,
            event_type=event.event_type
        )

        # Handle different types of log events
        if event.event_type == EVENT_LOGS_BATCH_INGESTED:
            return await self._handle_logs_batch_ingested(event)
        else:
            # For now, just log other event types
            logger.info(f"Log event type {event.event_type} received but not yet implemented")
            return True

    async def _handle_logs_batch_ingested(self, event: BaseEvent) -> bool:
        """Handle logs.batch.ingested event using SmartIngestionService + buffered writes"""
        try:
            # Import here to avoid circular dependencies
            from services.smart_ingestion_service import get_smart_ingestion_service
            from services.write_buffer_service import get_write_buffer
            from events.management.processors.log_processor import track_ingestion_metrics
            from events.publishers.log_publisher import LogEventPublisher
            from datetime import datetime

            customer_id = event.customer_id
            raw_logs = event.data.get('logs', [])
            source_format = event.data.get('source_format', 'json')
            batch_info = {
                'batch_id': event.data.get('batch_id', ''),
                'endpoint': event.data.get('ingestion_endpoint', '/logs'),
                'bytes_processed': event.data.get('bytes_processed', 0),
                'success_count': event.data.get('log_count', 0),
                'error_count': event.data.get('error_count', 0),
                'timestamp': event.data.get('timestamp', datetime.utcnow().isoformat()),
                'source_format': source_format
            }

            logger.info(
                "🚀 SMART PROCESSING: Processing log batch ingestion event",
                event_id=event.metadata.event_id,
                customer_id=customer_id,
                log_count=len(raw_logs),
                source_format=source_format
            )

            start_time = datetime.now()

            # Step 1: Process logs with SmartIngestionService (field mapping + normalization)
            smart_service = get_smart_ingestion_service()
            ingestion_result = await smart_service.process_logs_with_normalization(
                raw_logs=raw_logs,
                customer_id=customer_id,
                source_format=source_format
            )

            logger.info(
                f"Smart normalization completed",
                event_id=event.metadata.event_id,
                customer_id=customer_id,
                processed_logs=len(ingestion_result.log_entries),
                errors=len(ingestion_result.errors),
                normalization_time_ms=ingestion_result.processing_time_ms,
                field_mapping_applied=ingestion_result.field_mapping_applied
            )

            # Step 2: Buffer raw logs for batched write to logs_raw_mt
            # Convert LogEntry objects to dicts for buffering
            raw_logs_dicts = [
                {
                    "ts": log.ts,
                    "host": log.host,
                    "service": log.service,
                    "level": log.level,
                    "msg": log.msg,
                    "trace_id": log.trace_id,
                    "span_id": log.span_id,
                    "attrs": log.attrs,
                    "status": log.status,
                    "src_ip": log.src_ip,
                    "user_id": log.user_id,
                    "ingested_at": log.ingested_at,
                    "customer_id": customer_id
                }
                for log in ingestion_result.log_entries
            ]

            write_buffer = get_write_buffer()
            raw_buffer_success = await write_buffer.add_logs(
                customer_id=customer_id,
                raw_logs=raw_logs_dicts
            )

            if not raw_buffer_success:
                logger.error(
                    "Raw log buffering failed",
                    event_id=event.metadata.event_id,
                    customer_id=customer_id
                )
                return False

            # Step 3: Track ingestion metrics
            total_processing_time = (datetime.now() - start_time).total_seconds() * 1000
            await track_ingestion_metrics(
                customer_id=customer_id,
                endpoint=batch_info.get('endpoint', '/logs'),
                log_count=len(ingestion_result.log_entries),
                bytes_processed=batch_info.get('bytes_processed', 0),
                format_type=source_format,
                processing_time_ms=int(total_processing_time)
            )

            # Step 4: Track monthly ingestion usage and update tenant quotas
            try:
                from services.tenant_service import TenantService
                from events.management.processors.usage_processor import track_usage_with_cost_calculation

                tenant_service = TenantService()

                # Track monthly ingestion usage (this was missing!)
                await track_usage_with_cost_calculation(
                    tenant_service,
                    customer_id,
                    "monthly_ingestion",
                    batch_info.get('bytes_processed', 0)
                )

                logger.debug(f"Monthly ingestion usage tracked for customer {customer_id}: {batch_info.get('bytes_processed', 0)} bytes")

            except Exception as e:
                logger.warning(f"Failed to track monthly ingestion usage for customer {customer_id}: {e}")
                # Don't fail the whole operation if usage tracking fails

            # Step 5: Publish normalized event for alert/sigma processing
            # Get the publisher manager from somewhere in the system
            try:
                from dependencies import get_event_publisher_manager
                publisher_manager = get_event_publisher_manager()
                log_publisher = LogEventPublisher(publisher_manager)

                await log_publisher.publish_normalized_batch(
                    customer_id=customer_id,
                    normalized_logs=ingestion_result.normalized_data,
                    batch_info=batch_info,
                    normalization_time_ms=ingestion_result.processing_time_ms,
                    correlation_id=event.metadata.correlation_id,
                    trace_id=event.metadata.trace_id
                )

                logger.info(
                    "📤 NORMALIZED EVENT PUBLISHED: Normalized logs ready for alert/sigma engines",
                    event_id=event.metadata.event_id,
                    customer_id=customer_id,
                    normalized_logs=len(ingestion_result.normalized_data)
                )

            except Exception as e:
                logger.warning(
                    f"Failed to publish normalized event, but dual-write succeeded: {e}",
                    event_id=event.metadata.event_id,
                    customer_id=customer_id
                )
                # Don't fail the whole operation if event publishing fails

            # Performance validation
            performance_target_met = ingestion_result.processing_time_ms < 2.0

            logger.info(
                "🚀 SMART PROCESSING COMPLETE",
                event_id=event.metadata.event_id,
                customer_id=customer_id,
                processed_logs=len(ingestion_result.log_entries),
                errors=len(ingestion_result.errors),
                normalization_time_ms=ingestion_result.processing_time_ms,
                total_time_ms=total_processing_time,
                field_mapping_applied=ingestion_result.field_mapping_applied,
                performance_target_met='✅ TARGET MET' if performance_target_met else '⚠️ TARGET MISSED'
            )

            return True

        except Exception as e:
            logger.error(
                f"🚀 SMART PROCESSING FAILED: {e}",
                event_id=event.metadata.event_id,
                customer_id=event.customer_id,
                exc_info=True
            )
            return False

    def get_supported_event_types(self) -> List[str]:
        """Support log events"""
        return [
            EVENT_LOGS_BATCH_INGESTED,
            EVENT_LOGS_PARSED,
            EVENT_LOGS_INDEXED,
            EVENT_LOGS_ARCHIVED,
            EVENT_LOGS_DELETED
        ]

    def get_handler_name(self) -> str:
        """Get handler name"""
        return "log_handler"
