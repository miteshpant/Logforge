"""
Smart Ingestion Service - Phase 1 of Market-Leading Performance Implementation
Single-pass normalization at ingestion time for sub-5ms end-to-end latency
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
from dataclasses import dataclass

from models import LogEntry, BaseLogEntry
from services.high_performance_normalizer import normalize_batch_fast, get_high_performance_normalizer

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result of smart ingestion processing"""
    log_entries: List[LogEntry]
    normalized_data: List[Dict[str, Any]]
    processing_time_ms: float
    field_mapping_applied: bool
    errors: List[str]


class SmartIngestionService:
    """
    Smart Ingestion Service for market-leading performance
    
    Features:
    - Single-pass field normalization at ingestion time
    - Comprehensive field mapping using field_mapping.yml
    - Optimized for <2ms processing latency
    - Generates both LogEntry objects and normalized data for parallel processing
    """
    
    def __init__(self):
        """Initialize the smart ingestion service"""
        self.performance_stats = {
            "total_logs_processed": 0,
            "total_processing_time_ms": 0.0,
            "avg_processing_time_ms": 0.0,
            "field_mapping_success_rate": 0.0
        }
        logger.info("SmartIngestionService initialized for market-leading performance")
    
    async def process_logs_with_normalization(
        self, 
        raw_logs: List[Dict[str, Any]], 
        customer_id: str,
        source_format: str = "json"
    ) -> IngestionResult:
        """
        Process logs with single-pass field normalization
        
        Args:
            raw_logs: List of raw log dictionaries
            customer_id: Customer/tenant identifier  
            source_format: Source format (json, syslog, etc.)
            
        Returns:
            IngestionResult with processed logs and normalized data
        """
        start_time = datetime.now()
        log_entries = []
        normalized_data = []
        errors = []
        field_mapping_success = 0
        
        logger.debug(f"Processing {len(raw_logs)} logs for customer {customer_id}")

        # Step 1: Enrich all logs with metadata (vectorized)
        enriched_logs = []
        for raw_log in raw_logs:
            enriched_logs.append(self._enrich_log_metadata(raw_log, customer_id, source_format))

        # Step 2: Batch normalize using high-performance normalizer
        # This uses schema registry + bloom filters for O(1) lookups on repeated schemas
        normalized_data = normalize_batch_fast(enriched_logs, customer_id, source_format)

        logger.debug(f"High-performance batch normalization complete: {len(normalized_data)} logs")

        # Step 2b (Phase 3): threat intelligence matches, stamped as
        # attrs.threat on the stored log and the normalized event alike.
        await _enrich(customer_id, enriched_logs, normalized_data)

        # Step 3: Create LogEntry objects (for backward compatibility)
        for i, (enriched_log, normalized_log) in enumerate(zip(enriched_logs, normalized_data)):
            try:
                log_entry = LogEntry(**enriched_log)
                log_entries.append(log_entry)
                field_mapping_success += 1

                # Debug logging (only first log of batch)
                if i == 0:
                    added_fields = [k for k in normalized_log.keys() if k not in enriched_log]
                    if added_fields:
                        logger.debug(f"Normalized fields added: {added_fields[:5]}...")

            except Exception as e:
                error_msg = f"Failed to create LogEntry for log {i}: {str(e)}"
                errors.append(error_msg)
                logger.warning(error_msg)
        
        # Calculate performance metrics
        processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        field_mapping_rate = field_mapping_success / len(raw_logs) if raw_logs else 0
        
        # Update performance stats
        self._update_performance_stats(len(log_entries), processing_time_ms, field_mapping_rate)
        
        logger.info(
            f"Smart ingestion completed: {len(log_entries)}/{len(raw_logs)} logs processed "
            f"in {processing_time_ms:.2f}ms ({processing_time_ms/len(raw_logs):.3f}ms per log)"
        )
        
        return IngestionResult(
            log_entries=log_entries,
            normalized_data=normalized_data,
            processing_time_ms=processing_time_ms,
            field_mapping_applied=field_mapping_rate > 0.95,  # 95% success rate threshold
            errors=errors
        )
    
    def _enrich_log_metadata(
        self, 
        raw_log: Dict[str, Any], 
        customer_id: str, 
        source_format: str
    ) -> Dict[str, Any]:
        """
        Enrich log with metadata before normalization
        
        Args:
            raw_log: Raw log dictionary
            customer_id: Customer identifier
            source_format: Source format identifier
            
        Returns:
            Enriched log dictionary
        """
        enriched = raw_log.copy()
        
        # Add customer and ingestion metadata
        enriched["customer_id"] = customer_id
        enriched["ingested_at"] = datetime.now(timezone.utc)
        
        # Add source format for analytics
        if "attrs" not in enriched:
            enriched["attrs"] = {}
        enriched["attrs"]["source_format"] = source_format
        enriched["attrs"]["processing_version"] = "smart_v1"
        
        # Ensure required fields have defaults
        if "service" not in enriched:
            enriched["service"] = "unknown"
        if "level" not in enriched:
            enriched["level"] = "info"
        if "msg" not in enriched and "message" not in enriched:
            enriched["msg"] = raw_log.get("message", "")
        
        return enriched
    
    
    def _update_performance_stats(
        self, 
        logs_processed: int, 
        processing_time_ms: float, 
        field_mapping_rate: float
    ):
        """Update internal performance statistics"""
        self.performance_stats["total_logs_processed"] += logs_processed
        self.performance_stats["total_processing_time_ms"] += processing_time_ms
        
        if self.performance_stats["total_logs_processed"] > 0:
            self.performance_stats["avg_processing_time_ms"] = (
                self.performance_stats["total_processing_time_ms"] / 
                self.performance_stats["total_logs_processed"]
            )
        
        # Update field mapping success rate (moving average)
        current_rate = self.performance_stats["field_mapping_success_rate"]
        self.performance_stats["field_mapping_success_rate"] = (
            (current_rate * 0.9) + (field_mapping_rate * 0.1)
        )
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get current performance metrics
        
        Returns:
            Dictionary with performance statistics
        """
        return {
            "service_name": "SmartIngestionService",
            "version": "smart_v1",
            "performance_stats": self.performance_stats.copy(),
            "target_latency_ms": 2.0,
            "meets_target": self.performance_stats["avg_processing_time_ms"] < 2.0,
            "field_mapping_health": "healthy" if self.performance_stats["field_mapping_success_rate"] > 0.95 else "degraded"
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the smart ingestion service
        
        Returns:
            Health check results
        """
        try:
            # Test field mapping functionality
            test_log = {
                "source_ip": "192.168.1.100",
                "username": "test_user",
                "message": "Test log for health check",
                "service": "health_check"
            }
            
            start_time = datetime.now()
            result = await self.process_logs_with_normalization([test_log], "health_check")
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            health_status = "healthy" if processing_time < 5.0 and len(result.errors) == 0 else "unhealthy"
            
            return {
                "status": health_status,
                "processing_time_ms": processing_time,
                "field_mapping_working": len(result.errors) == 0,
                "normalized_data_generated": len(result.normalized_data) > 0,
                "performance_target_met": processing_time < 2.0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }


# Global instance for dependency injection
smart_ingestion_service = SmartIngestionService()


async def _enrich(customer_id: str, enriched_logs: List[Dict[str, Any]],
                  normalized_data: List[Dict[str, Any]]) -> None:
    """Look up each event once; copy the stamp onto its normalized twin
    (index-aligned). Never fails ingestion."""
    try:
        from ingest_enrichment import enrich_events

        await enrich_events(customer_id, enriched_logs)
        for raw, normalized in zip(enriched_logs, normalized_data):
            stamp = (raw.get("attrs") or {}).get("threat") if isinstance(raw.get("attrs"), dict) else None
            if stamp and isinstance(normalized, dict):
                attrs = normalized.get("attrs")
                if not isinstance(attrs, dict):
                    attrs = normalized["attrs"] = {}
                attrs["threat"] = stamp
    except Exception as e:
        logger.warning(f"Ingest enrichment skipped for {customer_id}: {e}")


def get_smart_ingestion_service() -> SmartIngestionService:
    """Get the global smart ingestion service instance"""
    return smart_ingestion_service