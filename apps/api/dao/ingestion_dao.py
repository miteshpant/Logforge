"""
Ingestion Data Access Object (DAO)
Handles all database operations for log ingestion tracking and storage
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import structlog

from database_layer import DatabaseLayer
from constants.database_constants import (
    INGESTION_STATS_TABLE, INGESTION_ERRORS_TABLE,
    STATUS_ACTIVE, STATUS_INACTIVE
)

logger = structlog.get_logger()

class IngestionDAO:
    """Data Access Object for Ingestion operations"""
    
    def __init__(self):
        self.db = DatabaseLayer("IngestionDAO", "ingestion-dao-service-key")
    
    async def track_ingestion_stats(self, stats_data: Dict[str, Any]) -> str:
        """Track ingestion statistics in database"""
        try:
            stats_id = str(uuid.uuid4())
            
            db_stats_data = {
                'id': stats_id,
                'customer_id': stats_data['customer_id'],
                'endpoint': stats_data['endpoint'],
                'format_detected': stats_data['format_detected'],
                'log_count': stats_data['log_count'],
                'bytes_processed': stats_data['bytes_processed'],
                'processing_time_ms': stats_data['processing_time_ms'],
                'status': stats_data.get('status', STATUS_ACTIVE),
                'ingested_at': stats_data.get('ingested_at', datetime.now(timezone.utc)),
                'created_at': datetime.now(timezone.utc)
            }
            
            await self.db.execute_query(
                f"""INSERT INTO {INGESTION_STATS_TABLE} 
                   (id, customer_id, endpoint, format_detected, log_count, bytes_processed, 
                    processing_time_ms, status, ingested_at, created_at)
                   VALUES (%(id)s, %(customer_id)s, %(endpoint)s, %(format_detected)s, %(log_count)s,
                   %(bytes_processed)s, %(processing_time_ms)s, %(status)s, %(ingested_at)s, %(created_at)s)""",
                db_stats_data
            )
            
            logger.info("Ingestion stats tracked", stats_id=stats_id, customer_id=stats_data['customer_id'])
            return stats_id
            
        except Exception as e:
            logger.error("Failed to track ingestion stats", error=str(e), customer_id=stats_data.get('customer_id'))
            raise e
    
    async def track_ingestion_error(self, error_data: Dict[str, Any]) -> str:
        """Track ingestion errors in database"""
        try:
            error_id = str(uuid.uuid4())
            
            db_error_data = {
                'id': error_id,
                'customer_id': error_data['customer_id'],
                'endpoint': error_data['endpoint'],
                'error_type': error_data['error_type'],
                'error_message': error_data['error_message'],
                'raw_content': error_data.get('raw_content', ''),
                'content_type': error_data.get('content_type', ''),
                'created_at': datetime.now(timezone.utc)
            }
            
            await self.db.execute_query(
                f"""INSERT INTO {INGESTION_ERRORS_TABLE} 
                   (id, customer_id, endpoint, error_type, error_message, raw_content, content_type, created_at)
                   VALUES (%(id)s, %(customer_id)s, %(endpoint)s, %(error_type)s, %(error_message)s,
                   %(raw_content)s, %(content_type)s, %(created_at)s)""",
                db_error_data
            )
            
            logger.info("Ingestion error tracked", error_id=error_id, customer_id=error_data['customer_id'])
            return error_id
            
        except Exception as e:
            logger.error("Failed to track ingestion error", error=str(e), customer_id=error_data.get('customer_id'))
            raise e
    
    async def get_ingestion_stats(self, customer_id: str, 
                                 start_date: Optional[datetime] = None,
                                 end_date: Optional[datetime] = None,
                                 limit: int = 100) -> List[Dict[str, Any]]:
        """Get ingestion statistics for a customer"""
        try:
            query = f"SELECT * FROM {INGESTION_STATS_TABLE} WHERE customer_id = %(customer_id)s"
            params = {"customer_id": customer_id, "limit": limit}
            
            if start_date:
                query += " AND ingested_at >= %(start_date)s"
                params["start_date"] = start_date
                
            if end_date:
                query += " AND ingested_at <= %(end_date)s"
                params["end_date"] = end_date
            
            query += " ORDER BY ingested_at DESC LIMIT %(limit)s"
            
            result = await self.db.execute_query(query, params)
            return [dict(row) for row in result] if result else []
            
        except Exception as e:
            logger.error("Failed to get ingestion stats", error=str(e), customer_id=customer_id)
            return []
    
    async def get_ingestion_summary(self, customer_id: str,
                                  start_date: Optional[datetime] = None,
                                  end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get ingestion summary statistics"""
        try:
            query = f"""SELECT 
                       COUNT(*) as total_ingestions,
                       SUM(log_count) as total_logs,
                       SUM(bytes_processed) as total_bytes,
                       AVG(processing_time_ms) as avg_processing_time,
                       format_detected,
                       COUNT(*) as format_count
                       FROM {INGESTION_STATS_TABLE} 
                       WHERE customer_id = %(customer_id)s"""
            
            params = {"customer_id": customer_id}
            
            if start_date:
                query += " AND ingested_at >= %(start_date)s"
                params["start_date"] = start_date
                
            if end_date:
                query += " AND ingested_at <= %(end_date)s"
                params["end_date"] = end_date
            
            query += " GROUP BY format_detected ORDER BY format_count DESC"
            
            result = await self.db.execute_query(query, params)
            
            if result:
                # Calculate totals
                total_ingestions = sum(row['format_count'] for row in result)
                total_logs = sum(row.get('total_logs', 0) for row in result)
                total_bytes = sum(row.get('total_bytes', 0) for row in result)
                
                return {
                    "total_ingestions": total_ingestions,
                    "total_logs": total_logs,
                    "total_bytes": total_bytes,
                    "format_breakdown": [dict(row) for row in result]
                }
            
            return {
                "total_ingestions": 0,
                "total_logs": 0,
                "total_bytes": 0,
                "format_breakdown": []
            }
            
        except Exception as e:
            logger.error("Failed to get ingestion summary", error=str(e), customer_id=customer_id)
            return {
                "total_ingestions": 0,
                "total_logs": 0,
                "total_bytes": 0,
                "format_breakdown": [],
                "error": str(e)
            }
    
    async def get_recent_errors(self, customer_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent ingestion errors for a customer"""
        try:
            result = await self.db.execute_query(
                f"""SELECT * FROM {INGESTION_ERRORS_TABLE} 
                   WHERE customer_id = %(customer_id)s 
                   ORDER BY created_at DESC LIMIT %(limit)s""",
                {"customer_id": customer_id, "limit": limit}
            )
            
            return [dict(row) for row in result] if result else []
            
        except Exception as e:
            logger.error("Failed to get ingestion errors", error=str(e), customer_id=customer_id)
            return []