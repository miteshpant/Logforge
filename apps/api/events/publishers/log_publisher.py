"""
Log Event Publisher
Specialized publisher for log lifecycle events
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
import structlog

from ..base import BaseEvent, EventPriority, EventMetadata
from ..constants import (
    EVENT_LOGS_BATCH_INGESTED,
    EVENT_LOGS_PARSING_FAILED,
    EVENT_LOGS_QUOTA_EXCEEDED,
    EVENT_LOGS_REALTIME_BATCH,
    EVENT_LOGS_ARCHIVED,
    EVENT_LOGS_PARSED,
    EVENT_LOGS_INDEXED,
    EVENT_LOGS_DELETED,
    EVENT_LOGS_NORMALIZED
)

logger = structlog.get_logger(__name__)


class LogEventPublisher:
    """Publisher for log lifecycle events"""

    def __init__(self, publisher_manager):
        self.publisher_manager = publisher_manager
        self.logger = logger.bind(component="log_event_publisher")

    async def publish_batch_ingested(
        self,
        customer_id: str,
        batch_info: Dict[str, Any],
        source_format: str,
        processing_time_ms: float,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when a batch of logs is ingested

        Args:
            customer_id: Customer identifier
            batch_info: Information about the ingested batch
            source_format: Format of ingested logs (json, syslog, cef, etc.)
            processing_time_ms: Time taken to process the batch
            correlation_id: Request correlation ID
            trace_id: Distributed tracing ID
        """
        try:
            # Debug logging to trace endpoint value
            endpoint_from_batch = batch_info.get("endpoint", "unknown")
            self.logger.info(
                f"LOG_PUBLISHER DEBUG: Creating event data with endpoint",
                customer_id=customer_id,
                endpoint_from_batch=endpoint_from_batch,
                batch_info_keys=list(batch_info.keys()),
                source_format=source_format
            )
            
            event_data = {
                "batch_id": batch_info.get("batch_id"),
                "log_count": batch_info.get("log_count", 0),
                "source_format": source_format,
                "processing_time_ms": processing_time_ms,
                "bytes_processed": batch_info.get("bytes_processed", 0),
                "ingestion_endpoint": endpoint_from_batch,
                "timestamp": batch_info.get("timestamp"),
                "success_count": batch_info.get("success_count", 0),
                "error_count": batch_info.get("error_count", 0),
                "logs": batch_info.get("logs", [])  # Include actual log data for event processing
            }

            metadata = EventMetadata(
                source_service="ingestion-service",
                correlation_id=correlation_id,
                trace_id=trace_id,
                priority=EventPriority.MEDIUM
            )

            event = BaseEvent(
                event_type=EVENT_LOGS_BATCH_INGESTED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            
            # Check if any publisher succeeded
            success_count = sum(1 for result in results.values() if result)
            total_publishers = len(results)
            success = success_count > 0

            if success:
                self.logger.info(
                    "Log batch ingestion event published",
                    customer_id=customer_id,
                    batch_id=batch_info.get("batch_id"),
                    log_count=batch_info.get("log_count"),
                    source_format=source_format,
                    successful_publishers=success_count,
                    total_publishers=total_publishers,
                    publisher_results=results
                )
            else:
                self.logger.error(
                    "Failed to publish log batch ingestion event to any publisher",
                    customer_id=customer_id,
                    batch_id=batch_info.get("batch_id"),
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing log batch ingestion event",
                customer_id=customer_id,
                error=str(e),
                exc_info=True
            )
            return False

    async def publish_log_parsed(
        self,
        customer_id: str,
        log_id: str,
        parsed_fields: Dict[str, Any],
        parser_name: str,
        parsing_time_ms: float,
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when a log is successfully parsed

        Args:
            customer_id: Customer identifier
            log_id: Unique log identifier
            parsed_fields: Count and types of parsed fields
            parser_name: Name of parser used
            parsing_time_ms: Time taken to parse
            correlation_id: Request correlation ID
        """
        try:
            event_data = {
                "log_id": log_id,
                "parser_name": parser_name,
                "parsing_time_ms": parsing_time_ms,
                "field_count": len(parsed_fields),
                "field_types": list(set(type(v).__name__ for v in parsed_fields.values())),
                "has_timestamp": "timestamp" in parsed_fields,
                "has_level": "level" in parsed_fields,
                "has_message": "message" in parsed_fields
            }

            metadata = EventMetadata(
                source_service="parser-service",
                correlation_id=correlation_id,
                priority=EventPriority.MEDIUM
            )

            event = BaseEvent(
                event_type=EVENT_LOGS_PARSED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = any(results.values())

            if success:
                self.logger.debug(
                    "Log parsing event published",
                    customer_id=customer_id,
                    log_id=log_id,
                    parser=parser_name,
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing log parsing event",
                customer_id=customer_id,
                log_id=log_id,
                error=str(e)
            )
            return False

    async def publish_log_indexed(
        self,
        customer_id: str,
        log_id: str,
        index_name: str,
        indexing_time_ms: float,
        searchable_fields: List[str],
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when a log is indexed for search

        Args:
            customer_id: Customer identifier
            log_id: Unique log identifier
            index_name: Name of search index
            indexing_time_ms: Time taken to index
            searchable_fields: List of fields made searchable
            correlation_id: Request correlation ID
        """
        try:
            event_data = {
                "log_id": log_id,
                "index_name": index_name,
                "indexing_time_ms": indexing_time_ms,
                "searchable_field_count": len(searchable_fields),
                "searchable_fields": searchable_fields[:10],  # Limit for event size
                "indexed_at": datetime.utcnow().isoformat()
            }

            metadata = EventMetadata(
                source_service="indexing-service",
                correlation_id=correlation_id,
                priority=EventPriority.LOW  # Indexing is background
            )

            event = BaseEvent(
                event_type=EVENT_LOGS_INDEXED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = any(results.values())

            if success:
                self.logger.debug(
                    "Log indexing event published",
                    customer_id=customer_id,
                    log_id=log_id,
                    index=index_name,
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing log indexing event",
                customer_id=customer_id,
                log_id=log_id,
                error=str(e)
            )
            return False

    async def publish_log_archived(
        self,
        customer_id: str,
        archive_info: Dict[str, Any],
        archive_location: str,
        compression_ratio: float,
        archive_time_ms: float
    ) -> bool:
        """
        Publish event when logs are archived to cold storage

        Args:
            customer_id: Customer identifier
            archive_info: Information about archived batch
            archive_location: Storage location (S3, GCS, etc.)
            compression_ratio: Compression achieved
            archive_time_ms: Time taken to archive
        """
        try:
            event_data = {
                "archive_id": archive_info.get("archive_id"),
                "log_count": archive_info.get("log_count", 0),
                "size_bytes": archive_info.get("size_bytes", 0),
                "archive_location": archive_location,
                "compression_ratio": compression_ratio,
                "archive_time_ms": archive_time_ms,
                "archived_at": datetime.utcnow().isoformat(),
                "retention_days": archive_info.get("retention_days")
            }

            metadata = EventMetadata(
                source_service="archival-service",
                priority=EventPriority.LOW
            )

            event = BaseEvent(
                event_type=EVENT_LOGS_ARCHIVED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = any(results.values())

            if success:
                self.logger.info(
                    "Log archival event published",
                    customer_id=customer_id,
                    archive_id=archive_info.get("archive_id"),
                    log_count=archive_info.get("log_count"),
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing log archival event",
                customer_id=customer_id,
                error=str(e)
            )
            return False

    async def publish_log_deleted(
        self,
        customer_id: str,
        deletion_info: Dict[str, Any],
        reason: str = "retention_policy"
    ) -> bool:
        """
        Publish event when logs are deleted due to retention policies

        Args:
            customer_id: Customer identifier
            deletion_info: Information about deleted logs
            reason: Reason for deletion
        """
        try:
            event_data = {
                "deletion_id": deletion_info.get("deletion_id"),
                "log_count": deletion_info.get("log_count", 0),
                "size_bytes": deletion_info.get("size_bytes", 0),
                "date_range": {
                    "from": deletion_info.get("from_date"),
                    "to": deletion_info.get("to_date")
                },
                "reason": reason,
                "deleted_at": datetime.utcnow().isoformat(),
                "policy_name": deletion_info.get("policy_name")
            }

            metadata = EventMetadata(
                source_service="retention-service",
                priority=EventPriority.LOW
            )

            event = BaseEvent(
                event_type=EVENT_LOGS_DELETED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = any(results.values())

            if success:
                self.logger.info(
                    "Log deletion event published",
                    customer_id=customer_id,
                    log_count=deletion_info.get("log_count"),
                    reason=reason,
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing log deletion event",
                customer_id=customer_id,
                error=str(e)
            )
            return False

    async def publish_parsing_failed(
        self,
        customer_id: str,
        log_info: Dict[str, Any],
        error_details: Dict[str, Any],
        parser_name: str,
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when log parsing fails

        Args:
            customer_id: Customer identifier
            log_info: Information about the failed log
            error_details: Details about the parsing error
            parser_name: Name of parser that failed
            correlation_id: Request correlation ID
        """
        try:
            event_data = {
                "log_id": log_info.get("log_id"),
                "parser_name": parser_name,
                "error_message": error_details.get("error_message"),
                "error_type": error_details.get("error_type"),
                "raw_log_sample": str(log_info.get("content", ""))[:500],  # First 500 chars
                "failed_at": datetime.utcnow().isoformat(),
                "retry_count": error_details.get("retry_count", 0)
            }

            metadata = EventMetadata(
                source_service="parser-service",
                correlation_id=correlation_id,
                priority=EventPriority.HIGH  # Parsing failures need attention
            )

            event = BaseEvent(
                event_type=EVENT_LOGS_PARSING_FAILED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = any(results.values())

            if success:
                self.logger.warning(
                    "Log parsing failure event published",
                    customer_id=customer_id,
                    log_id=log_info.get("log_id"),
                    parser=parser_name,
                    error=error_details.get("error_message"),
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing log parsing failure event",
                customer_id=customer_id,
                error=str(e)
            )
            return False

    async def publish_quota_exceeded(
        self,
        customer_id: str,
        quota_info: Dict[str, Any],
        current_usage: Dict[str, Any]
    ) -> bool:
        """
        Publish event when customer exceeds log quota

        Args:
            customer_id: Customer identifier
            quota_info: Information about the quota limit
            current_usage: Current usage statistics
        """
        try:
            event_data = {
                "quota_type": quota_info.get("quota_type", "daily_logs"),
                "limit_value": quota_info.get("limit_value"),
                "current_value": current_usage.get("current_value"),
                "percentage_used": (current_usage.get("current_value", 0) / quota_info.get("limit_value", 1)) * 100,
                "exceeded_at": datetime.utcnow().isoformat(),
                "period": quota_info.get("period", "daily"),
                "action_taken": quota_info.get("action_taken", "throttle")
            }

            metadata = EventMetadata(
                source_service="quota-service",
                priority=EventPriority.CRITICAL  # Quota exceeded is critical
            )

            event = BaseEvent(
                event_type=EVENT_LOGS_QUOTA_EXCEEDED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = any(results.values())

            if success:
                self.logger.warning(
                    "Log quota exceeded event published",
                    customer_id=customer_id,
                    quota_type=quota_info.get("quota_type"),
                    percentage_used=event_data["percentage_used"],
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing log quota exceeded event",
                customer_id=customer_id,
                error=str(e)
            )
            return False

    async def publish_realtime_batch(
        self,
        customer_id: str,
        batch_info: Dict[str, Any],
        stream_name: str
    ) -> bool:
        """
        Publish event for real-time log batches (for UI streaming)

        Args:
            customer_id: Customer identifier
            batch_info: Information about the real-time batch
            stream_name: Name of the real-time stream
        """
        try:
            event_data = {
                "stream_name": stream_name,
                "batch_id": batch_info.get("batch_id"),
                "log_count": batch_info.get("log_count", 0),
                "latest_timestamp": batch_info.get("latest_timestamp"),
                "severity_counts": batch_info.get("severity_counts", {}),
                "service_counts": batch_info.get("service_counts", {}),
                "processed_at": datetime.utcnow().isoformat()
            }

            metadata = EventMetadata(
                source_service="realtime-service",
                priority=EventPriority.HIGH  # Real-time events are high priority
            )

            event = BaseEvent(
                event_type=EVENT_LOGS_REALTIME_BATCH,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            success = any(results.values())

            if success:
                self.logger.debug(
                    "Real-time log batch event published",
                    customer_id=customer_id,
                    stream_name=stream_name,
                    log_count=batch_info.get("log_count"),
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing real-time log batch event",
                customer_id=customer_id,
                error=str(e)
            )
            return False

    async def publish_normalized_batch(
        self,
        customer_id: str,
        normalized_logs: List[Dict[str, Any]],
        batch_info: Dict[str, Any],
        normalization_time_ms: float,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Publish event when logs are normalized and ready for alert/sigma processing
        
        Args:
            customer_id: Customer identifier
            normalized_logs: Field-mapped logs ready for rule evaluation
            batch_info: Original batch information 
            normalization_time_ms: Time taken for field mapping and normalization
            correlation_id: Request correlation ID
            trace_id: Distributed tracing ID
        """
        try:
            event_data = {
                "batch_id": batch_info.get("batch_id"),
                "log_count": len(normalized_logs),
                "customer_id": customer_id,
                "normalized_logs": normalized_logs,  # Field-mapped data ready for rules
                "timestamp": datetime.utcnow().isoformat(),
                "field_mapping_applied": True,
                "source_format": batch_info.get("source_format", "json"),
                "normalization_time_ms": normalization_time_ms,
                "original_batch_info": {
                    "ingestion_endpoint": batch_info.get("endpoint", "unknown"),
                    "bytes_processed": batch_info.get("bytes_processed", 0),
                    "success_count": batch_info.get("success_count", 0),
                    "error_count": batch_info.get("error_count", 0)
                }
            }

            metadata = EventMetadata(
                source_service="smart-ingestion-service",
                correlation_id=correlation_id,
                trace_id=trace_id,
                priority=EventPriority.HIGH  # High priority for real-time detection
            )

            event = BaseEvent(
                event_type=EVENT_LOGS_NORMALIZED,
                customer_id=customer_id,
                data=event_data,
                metadata=metadata
            )

            results = await self.publisher_manager.publish(event)
            
            # Check if any publisher succeeded
            success_count = sum(1 for result in results.values() if result)
            total_publishers = len(results)
            success = success_count > 0

            if success:
                self.logger.info(
                    "Normalized log batch event published",
                    customer_id=customer_id,
                    batch_id=batch_info.get("batch_id"),
                    log_count=len(normalized_logs),
                    normalization_time_ms=normalization_time_ms,
                    source_format=batch_info.get("source_format"),
                    successful_publishers=success_count,
                    total_publishers=total_publishers,
                    publisher_results=results
                )
            else:
                self.logger.error(
                    "Failed to publish normalized log batch event to any publisher",
                    customer_id=customer_id,
                    batch_id=batch_info.get("batch_id"),
                    publisher_results=results
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error publishing normalized log batch event",
                customer_id=customer_id,
                error=str(e),
                exc_info=True
            )
            return False

    async def publish_batch_events(self, events: List[BaseEvent]) -> Dict[str, Any]:
        """
        Publish multiple log events in batch for better performance

        Args:
            events: List of log events to publish

        Returns:
            Dict with success count, failed count, and errors
        """
        try:
            results = await self.publisher_manager.publish_batch(events)

            self.logger.info(
                "Batch log events published",
                total_events=len(events),
                successful=results.get("successful", 0),
                failed=results.get("failed", 0)
            )

            return results

        except Exception as e:
            self.logger.error(
                "Error publishing batch log events",
                event_count=len(events),
                error=str(e)
            )
            return {
                "successful": 0,
                "failed": len(events),
                "errors": [str(e)]
            }


# Convenience factory for creating log events
class LogEventFactory:
    """Factory for creating standardized log events"""

    @staticmethod
    def create_batch_ingestion_event(
        customer_id: str,
        batch_info: Dict[str, Any],
        source_format: str,
        processing_time_ms: float,
        **kwargs
    ) -> BaseEvent:
        """Create log batch ingestion event"""
        event_data = {
            "batch_id": batch_info.get("batch_id"),
            "log_count": batch_info.get("log_count", 0),
            "source_format": source_format,
            "processing_time_ms": processing_time_ms,
            "bytes_processed": batch_info.get("bytes_processed", 0),
            "success_count": batch_info.get("success_count", 0),
            "error_count": batch_info.get("error_count", 0),
            **kwargs
        }

        return BaseEvent(
            event_type=EVENT_LOGS_BATCH_INGESTED,
            customer_id=customer_id,
            data=event_data,
            metadata=EventMetadata(
                source_service="ingestion-service",
                priority=EventPriority.MEDIUM,
                **{k: v for k, v in kwargs.items() if k in ['correlation_id', 'trace_id']}
            )
        )

    @staticmethod
    def create_parsing_event(
        customer_id: str,
        log_id: str,
        parsed_fields: Dict[str, Any],
        parser_name: str,
        parsing_time_ms: float,
        **kwargs
    ) -> BaseEvent:
        """Create log parsing event"""
        event_data = {
            "log_id": log_id,
            "parser_name": parser_name,
            "parsing_time_ms": parsing_time_ms,
            "field_count": len(parsed_fields),
            "has_timestamp": "timestamp" in parsed_fields,
            "has_level": "level" in parsed_fields,
            "has_message": "message" in parsed_fields,
            **kwargs
        }

        return BaseEvent(
            event_type=EVENT_LOGS_PARSED,
            customer_id=customer_id,
            data=event_data,
            metadata=EventMetadata(
                source_service="parser-service",
                priority=EventPriority.MEDIUM,
                **{k: v for k, v in kwargs.items() if k in ['correlation_id', 'trace_id']}
            )
        )
