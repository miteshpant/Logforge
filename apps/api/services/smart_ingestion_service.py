"""
Smart Ingestion Service - Phase 1 of Market-Leading Performance Implementation
Single-pass normalization at ingestion time for sub-5ms end-to-end latency
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

from models import LogEntry, BaseLogEntry
from field_mapper import normalize_log_for_sigma

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
    - Dual-write preparation for raw + normalized storage
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
        
        for i, raw_log in enumerate(raw_logs):
            try:
                # Step 1: Apply metadata enrichment
                enriched_log = self._enrich_log_metadata(raw_log, customer_id, source_format)
                
                # Step 2: Apply field normalization BEFORE creating Pydantic model
                # This ensures we capture ALL normalized fields, not just model-defined ones
                normalized_log = normalize_log_for_sigma(enriched_log)
                
                # DEBUG: Print field mapping results
                logger.info(f"🔍 DEBUG Field Mapping Results for log {i}:")
                logger.info(f"  📥 Original enriched_log: {enriched_log}")
                logger.info(f"  📤 Normalized log: {normalized_log}")
                logger.info(f"  🔄 Field mapping diff:")
                for key, value in normalized_log.items():
                    if key not in enriched_log:
                        logger.info(f"    ➕ Added field: {key} = {value}")
                    elif enriched_log.get(key) != value:
                        logger.info(f"    🔄 Changed field: {key} = {enriched_log.get(key)} → {value}")
                
                # Step 3: Create LogEntry (for backward compatibility and validation)
                log_entry = LogEntry(**enriched_log)
                log_entries.append(log_entry)
                
                # Step 4: Store the fully normalized data (includes all standard Sigma fields)
                # This is what goes to logs_normalized_mt table for Sigma rule evaluation
                normalized_data.append(normalized_log)
                
                field_mapping_success += 1
                
                # Performance tracking
                if i % 100 == 0 and i > 0:
                    elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
                    logger.debug(f"Processed {i}/{len(raw_logs)} logs in {elapsed_ms:.2f}ms")
                
            except Exception as e:
                error_msg = f"Failed to process log {i}: {str(e)}"
                errors.append(error_msg)
                logger.warning(error_msg)
                continue
        
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
    
    async def prepare_dual_write_data(
        self, 
        ingestion_result: IngestionResult, 
        customer_id: str
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Prepare data for dual-write to raw and normalized tables
        
        Args:
            ingestion_result: Result from process_logs_with_normalization
            customer_id: Customer identifier
            
        Returns:
            Tuple of (raw_table_data, normalized_table_data)
        """
        raw_table_data = []
        normalized_table_data = []
        
        for i, log_entry in enumerate(ingestion_result.log_entries):
            try:
                # Prepare raw table data (original format for compliance/audit)
                raw_data = {
                    "ts": log_entry.ts,
                    "host": log_entry.host or "",
                    "service": log_entry.service,
                    "level": log_entry.level,
                    "msg": log_entry.msg,
                    "trace_id": log_entry.trace_id or "",
                    "span_id": log_entry.span_id or "",
                    "attrs": log_entry.attrs or {},
                    "status": log_entry.status or 0,
                    "src_ip": log_entry.src_ip or "",
                    "user_id": log_entry.user_id or "",
                    "severity_num": log_entry.severity_num or 0,
                    "facility": log_entry.facility or 16,
                    "parser_version": log_entry.parser_version or "smart_v1",
                    "ingested_at": log_entry.ingested_at,
                    "customer_id": customer_id
                }
                raw_table_data.append(raw_data)
                
                # Prepare normalized table data (for analytics/rules)
                normalized_data = ingestion_result.normalized_data[i].copy()
                normalized_data["customer_id"] = customer_id
                normalized_table_data.append(normalized_data)
                
            except Exception as e:
                logger.error(f"Failed to prepare dual-write data for log {i}: {e}")
                continue
        
        logger.debug(f"Prepared {len(raw_table_data)} raw and {len(normalized_table_data)} normalized records")
        return raw_table_data, normalized_table_data
    
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


def get_smart_ingestion_service() -> SmartIngestionService:
    """Get the global smart ingestion service instance"""
    return smart_ingestion_service