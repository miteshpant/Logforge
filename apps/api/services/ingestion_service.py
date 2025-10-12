"""
Ingestion Service 
Business logic layer for log ingestion operations
"""

import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import structlog

from dao.ingestion_dao import IngestionDAO
from models import LogEntry
from constants.api_constants import MAX_BATCH_SIZE, MAX_LOG_SIZE_BYTES

logger = structlog.get_logger()

class IngestionService:
    """Service layer for ingestion operations with proper database operations"""
    
    def __init__(self):
        self.ingestion_dao = IngestionDAO()
        self.max_batch_size = MAX_BATCH_SIZE
        self.max_log_size = MAX_LOG_SIZE_BYTES
    
    async def track_ingestion_success(self, customer_id: str, endpoint: str, 
                                    format_type: str, log_count: int,
                                    bytes_processed: int, processing_time_ms: int) -> str:
        """Track successful ingestion statistics"""
        try:
            stats_data = {
                'customer_id': customer_id,
                'endpoint': endpoint,
                'format_type': format_type,
                'log_count': log_count,
                'bytes_processed': bytes_processed,
                'processing_time_ms': processing_time_ms,
                'status': 'success',
                'ingested_at': datetime.now(timezone.utc)
            }
            
            stats_id = await self.ingestion_dao.track_ingestion_stats(stats_data)
            
            logger.info("Ingestion success tracked", 
                       customer_id=customer_id, endpoint=endpoint, log_count=log_count)
            
            return stats_id
            
        except Exception as e:
            logger.error("Failed to track ingestion success", error=str(e))
            # Don't fail the ingestion if tracking fails
            return ""
    
    async def track_ingestion_error(self, customer_id: str, endpoint: str,
                                  error_type: str, error_message: str,
                                  raw_content: Optional[str] = None,
                                  content_type: Optional[str] = None) -> str:
        """Track ingestion error for debugging"""
        try:
            error_data = {
                'customer_id': customer_id,
                'endpoint': endpoint,
                'error_type': error_type,
                'error_message': error_message,
                'raw_content': raw_content or '',
                'content_type': content_type or ''
            }
            
            error_id = await self.ingestion_dao.track_ingestion_error(error_data)
            
            logger.warning("Ingestion error tracked", 
                          customer_id=customer_id, endpoint=endpoint, error_type=error_type)
            
            return error_id
            
        except Exception as e:
            logger.error("Failed to track ingestion error", error=str(e))
            # Don't fail if error tracking fails
            return ""
    
    def validate_log_entry(self, log_entry: LogEntry) -> bool:
        """Validate log entry meets requirements"""
        try:
            # Check if log entry has required fields
            if not log_entry.msg:
                return False
            
            # Check log size
            log_size = len(str(log_entry.msg))
            if log_size > self.max_log_size:
                logger.warning("Log entry too large", size=log_size, max_size=self.max_log_size)
                return False
            
            # Check customer_id is set (can be empty, will be set by middleware)
            # if not log_entry.customer_id:
            #     return False
            
            return True
            
        except Exception as e:
            logger.error("Log validation failed", error=str(e))
            return False
    
    def validate_batch_logs(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Validate batch of log entries"""
        try:
            # Check batch size
            if len(logs) > self.max_batch_size:
                return {
                    "valid": False,
                    "error": f"Batch size {len(logs)} exceeds maximum {self.max_batch_size}"
                }
            
            # Validate each log entry
            valid_logs = []
            invalid_logs = []
            
            for i, log_entry in enumerate(logs):
                if self.validate_log_entry(log_entry):
                    valid_logs.append(log_entry)
                else:
                    invalid_logs.append({"index": i, "log": log_entry})
            
            return {
                "valid": len(invalid_logs) == 0,
                "valid_logs": valid_logs,
                "invalid_logs": invalid_logs,
                "valid_count": len(valid_logs),
                "invalid_count": len(invalid_logs)
            }
            
        except Exception as e:
            logger.error("Batch validation failed", error=str(e))
            return {
                "valid": False,
                "error": str(e),
                "valid_logs": [],
                "invalid_logs": logs
            }
    
    def prepare_logs_for_storage(self, logs: List[LogEntry], customer_id: str) -> List[LogEntry]:
        """Prepare logs for storage with proper metadata"""
        try:
            prepared_logs = []
            ingested_at = datetime.now(timezone.utc)
            
            for log_entry in logs:
                # Ensure required fields are set
                log_entry.ingested_at = ingested_at
                log_entry.customer_id = customer_id
                
                # Set default timestamp if not provided
                if not log_entry.ts:
                    log_entry.ts = ingested_at
                
                prepared_logs.append(log_entry)
            
            return prepared_logs
            
        except Exception as e:
            logger.error("Failed to prepare logs for storage", error=str(e))
            return logs
    
    async def get_ingestion_stats(self, customer_id: str,
                                start_date: Optional[datetime] = None,
                                end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get ingestion statistics for a customer"""
        try:
            stats = await self.ingestion_dao.get_ingestion_stats(
                customer_id, start_date, end_date
            )
            
            summary = await self.ingestion_dao.get_ingestion_summary(
                customer_id, start_date, end_date
            )
            
            return {
                "customer_id": customer_id,
                "stats": stats,
                "summary": summary
            }
            
        except Exception as e:
            logger.error("Failed to get ingestion stats", error=str(e))
            return {
                "customer_id": customer_id,
                "stats": [],
                "summary": {
                    "total_ingestions": 0,
                    "total_logs": 0,
                    "total_bytes": 0,
                    "format_breakdown": []
                },
                "error": str(e)
            }
    
    async def get_ingestion_errors(self, customer_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent ingestion errors for debugging"""
        try:
            return await self.ingestion_dao.get_recent_errors(customer_id, limit)
            
        except Exception as e:
            logger.error("Failed to get ingestion errors", error=str(e))
            return []
    
    def calculate_processing_metrics(self, start_time: float, log_count: int, 
                                   bytes_processed: int) -> Dict[str, Any]:
        """Calculate processing performance metrics"""
        try:
            processing_time = time.time() - start_time
            processing_time_ms = int(processing_time * 1000)
            
            logs_per_second = log_count / processing_time if processing_time > 0 else 0
            bytes_per_second = bytes_processed / processing_time if processing_time > 0 else 0
            
            return {
                "processing_time_ms": processing_time_ms,
                "logs_per_second": round(logs_per_second, 2),
                "bytes_per_second": round(bytes_per_second, 2),
                "log_count": log_count,
                "bytes_processed": bytes_processed
            }
            
        except Exception as e:
            logger.error("Failed to calculate processing metrics", error=str(e))
            return {
                "processing_time_ms": 0,
                "logs_per_second": 0,
                "bytes_per_second": 0,
                "log_count": log_count,
                "bytes_processed": bytes_processed
            }