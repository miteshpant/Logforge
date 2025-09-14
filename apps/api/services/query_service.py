"""
Query Service - Business Logic Layer
Handles query management, caching, and validation
"""

import hashlib
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import structlog

from dao.query_dao import QueryDAO
from models import QueryResponse

logger = structlog.get_logger()

class QueryService:
    """Service layer for query operations and business logic"""
    
    def __init__(self):
        self.query_dao = QueryDAO()
    
    async def save_query(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save a query with validation and business logic"""
        try:
            # Validate required fields
            required_fields = ['customer_id', 'name', 'query_definition']
            for field in required_fields:
                if field not in query_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate query definition structure
            query_def = query_data['query_definition']
            if not isinstance(query_def, dict):
                raise ValueError("Query definition must be a dictionary")
            
            # Set defaults
            query_data.setdefault('description', '')
            query_data.setdefault('query_type', 'advanced')
            query_data.setdefault('tags', [])
            query_data.setdefault('is_public', False)
            query_data.setdefault('created_by', 'system')
            
            # Save to database
            query_id = await self.query_dao.save_query(query_data)
            
            logger.info("Query saved successfully", 
                       query_id=query_id, 
                       customer_id=query_data['customer_id'],
                       name=query_data['name'])
            
            return {
                "status": "saved",
                "query_id": query_id,
                "message": "Query saved successfully",
                "customer_id": query_data['customer_id']
            }
            
        except Exception as e:
            logger.error("Failed to save query", error=str(e))
            raise e
    
    async def get_saved_query(self, query_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get saved query with tenant validation"""
        try:
            # Validate inputs
            if not query_id or not customer_id:
                raise ValueError("Query ID and customer ID are required")
            
            # Get from database
            query_data = await self.query_dao.get_saved_query(query_id, customer_id)
            
            if query_data:
                logger.info("Retrieved saved query", query_id=query_id, customer_id=customer_id)
                return query_data
            else:
                logger.warning("Query not found", query_id=query_id, customer_id=customer_id)
                return None
                
        except Exception as e:
            logger.error("Failed to get saved query", error=str(e), query_id=query_id)
            return None
    
    async def list_saved_queries(self, customer_id: str, 
                                created_by: Optional[str] = None,
                                query_type: Optional[str] = None,
                                limit: int = 50) -> Dict[str, Any]:
        """List saved queries with filtering and pagination"""
        try:
            # Validate inputs
            if not customer_id:
                raise ValueError("Customer ID is required")
            
            if limit > 100:
                limit = 100  # Enforce maximum limit
            
            # Get from database
            queries = await self.query_dao.list_saved_queries(
                customer_id=customer_id,
                created_by=created_by,
                query_type=query_type,
                limit=limit
            )
            
            logger.info("Listed saved queries", 
                       customer_id=customer_id, 
                       count=len(queries),
                       filters={"created_by": created_by, "query_type": query_type})
            
            return {
                "saved_queries": queries,
                "count": len(queries),
                "customer_id": customer_id,
                "filters": {
                    "created_by": created_by,
                    "query_type": query_type,
                    "limit": limit
                }
            }
            
        except Exception as e:
            logger.error("Failed to list saved queries", error=str(e), customer_id=customer_id)
            return {"saved_queries": [], "count": 0, "customer_id": customer_id}
    
    async def update_saved_query(self, query_id: str, customer_id: str, 
                                update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update saved query with validation"""
        try:
            # Validate inputs
            if not query_id or not customer_id:
                raise ValueError("Query ID and customer ID are required")
            
            # Validate update fields
            allowed_fields = ['name', 'description', 'query_definition', 'tags', 'is_public']
            filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields}
            
            if not filtered_data:
                raise ValueError("No valid fields to update")
            
            # Update in database
            success = await self.query_dao.update_saved_query(query_id, customer_id, filtered_data)
            
            if success:
                logger.info("Query updated successfully", query_id=query_id, customer_id=customer_id)
                return {
                    "status": "updated",
                    "query_id": query_id,
                    "message": "Query updated successfully",
                    "customer_id": customer_id
                }
            else:
                raise ValueError("Query not found or update failed")
                
        except Exception as e:
            logger.error("Failed to update saved query", error=str(e), query_id=query_id)
            raise e
    
    async def delete_saved_query(self, query_id: str, customer_id: str) -> Dict[str, Any]:
        """Delete (deactivate) saved query"""
        try:
            # Validate inputs
            if not query_id or not customer_id:
                raise ValueError("Query ID and customer ID are required")
            
            # Delete from database
            success = await self.query_dao.delete_saved_query(query_id, customer_id)
            
            if success:
                logger.info("Query deleted successfully", query_id=query_id, customer_id=customer_id)
                return {
                    "status": "deleted",
                    "query_id": query_id,
                    "message": "Query deleted successfully",
                    "customer_id": customer_id
                }
            else:
                raise ValueError("Query not found or deletion failed")
                
        except Exception as e:
            logger.error("Failed to delete saved query", error=str(e), query_id=query_id)
            raise e
    
    def _generate_cache_key(self, query_data: Dict[str, Any], customer_id: str) -> str:
        """Generate cache key for query"""
        # Create deterministic key from query data
        cache_content = {
            "customer_id": customer_id,
            "query": query_data
        }
        cache_string = json.dumps(cache_content, sort_keys=True)
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    async def cache_query_result(self, query_data: Dict[str, Any], customer_id: str,
                                result: Dict[str, Any], ttl_seconds: int = 300) -> str:
        """Cache query result with business logic"""
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(query_data, customer_id)
            
            # Cache in database
            cache_id = await self.query_dao.cache_query_result(
                cache_key=cache_key,
                customer_id=customer_id,
                query_data=query_data,
                result=result,
                ttl_seconds=ttl_seconds
            )
            
            if cache_id:
                logger.info("Query result cached", 
                           cache_key=cache_key, 
                           customer_id=customer_id,
                           ttl_seconds=ttl_seconds)
            
            return cache_key
            
        except Exception as e:
            logger.error("Failed to cache query result", error=str(e))
            return ""
    
    async def get_cached_result(self, query_data: Dict[str, Any], customer_id: str) -> Optional[Dict[str, Any]]:
        """Get cached query result if available"""
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(query_data, customer_id)
            
            # Get from database
            cached_data = await self.query_dao.get_cached_result(cache_key, customer_id)
            
            if cached_data:
                logger.info("Cache hit", cache_key=cache_key, customer_id=customer_id)
                return cached_data['result_data']
            else:
                logger.debug("Cache miss", cache_key=cache_key, customer_id=customer_id)
                return None
                
        except Exception as e:
            logger.error("Failed to get cached result", error=str(e))
            return None
    
    async def cleanup_expired_cache(self) -> Dict[str, Any]:
        """Clean up expired cache entries"""
        try:
            result = await self.query_dao.cleanup_expired_cache()
            
            if result:
                logger.info("Cache cleanup completed successfully")
                return {"status": "success", "message": "Cache cleanup completed"}
            else:
                raise ValueError("Cache cleanup failed")
                
        except Exception as e:
            logger.error("Failed to cleanup cache", error=str(e))
            raise e
    
    async def validate_query_structure(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate query structure and parameters"""
        try:
            validation_result = {
                "valid": True,
                "errors": [],
                "warnings": []
            }
            
            # Check required fields for advanced queries
            if "filters" in query_data:
                for i, filter_obj in enumerate(query_data["filters"]):
                    if not isinstance(filter_obj, dict):
                        validation_result["errors"].append(f"Filter {i} must be a dictionary")
                        continue
                    
                    required_filter_fields = ["field", "operator", "value"]
                    for field in required_filter_fields:
                        if field not in filter_obj:
                            validation_result["errors"].append(f"Filter {i} missing required field: {field}")
            
            # Check aggregations
            if "aggregations" in query_data:
                if not isinstance(query_data["aggregations"], list):
                    validation_result["errors"].append("Aggregations must be a list")
            
            # Check time range
            if "start_time" in query_data and "end_time" in query_data:
                try:
                    start = datetime.fromisoformat(query_data["start_time"].replace('Z', '+00:00'))
                    end = datetime.fromisoformat(query_data["end_time"].replace('Z', '+00:00'))
                    
                    if start >= end:
                        validation_result["errors"].append("Start time must be before end time")
                    
                    # Warn about large time ranges
                    time_diff = end - start
                    if time_diff.days > 30:
                        validation_result["warnings"].append("Large time range may impact performance")
                        
                except ValueError:
                    validation_result["errors"].append("Invalid time format")
            
            validation_result["valid"] = len(validation_result["errors"]) == 0
            
            return validation_result
            
        except Exception as e:
            logger.error("Failed to validate query structure", error=str(e))
            return {
                "valid": False,
                "errors": [f"Validation error: {str(e)}"],
                "warnings": []
            }