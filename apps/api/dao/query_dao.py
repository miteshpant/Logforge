"""
Query Data Access Object (DAO)
Handles all database operations for query management and saved queries
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import structlog
import json

from database_layer import DatabaseLayer
from constants.database_constants import (
    SAVED_QUERIES_TABLE, QUERY_CACHE_TABLE,
    STATUS_ACTIVE, STATUS_INACTIVE
)

logger = structlog.get_logger()

class QueryDAO:
    """Data Access Object for Query operations"""
    
    def __init__(self):
        self.db = DatabaseLayer("QueryDAO", "query-dao-service-key")
    
    async def save_query(self, query_data: Dict[str, Any]) -> str:
        """Save a query for future use in database"""
        try:
            query_id = str(uuid.uuid4())
            
            db_query_data = {
                'id': query_id,
                'customer_id': query_data['customer_id'],
                'name': query_data['name'],
                'description': query_data.get('description', ''),
                'query_definition': json.dumps(query_data['query_definition']),
                'query_type': query_data.get('query_type', 'advanced'),
                'created_by': query_data.get('created_by', 'system'),
                'tags': json.dumps(query_data.get('tags', [])),
                'is_public': query_data.get('is_public', False),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc),
                'status': STATUS_ACTIVE
            }
            
            await self.db.execute_query(
                f"""INSERT INTO {SAVED_QUERIES_TABLE} 
                   (id, customer_id, name, description, query_definition, query_type, 
                    created_by, tags, is_public, created_at, updated_at, status)
                   VALUES (%(id)s, %(customer_id)s, %(name)s, %(description)s, %(query_definition)s,
                   %(query_type)s, %(created_by)s, %(tags)s, %(is_public)s, %(created_at)s, 
                   %(updated_at)s, %(status)s)""",
                db_query_data
            )
            
            logger.info("Query saved to database", query_id=query_id, customer_id=query_data['customer_id'])
            return query_id
            
        except Exception as e:
            logger.error("Failed to save query to database", error=str(e))
            raise e
    
    async def get_saved_query(self, query_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get saved query by ID from database"""
        try:
            result = await self.db.execute_query(
                f"""SELECT * FROM {SAVED_QUERIES_TABLE} 
                   WHERE id = %(query_id)s AND customer_id = %(customer_id)s 
                   AND status = %(status)s""",
                {"query_id": query_id, "customer_id": customer_id, "status": STATUS_ACTIVE}
            )
            
            if result:
                query_data = dict(result[0])
                # Parse JSON fields
                query_data['query_definition'] = json.loads(query_data['query_definition'])
                query_data['tags'] = json.loads(query_data['tags']) if query_data['tags'] else []
                return query_data
            return None
            
        except Exception as e:
            logger.error("Failed to get saved query", error=str(e), query_id=query_id)
            return None
    
    async def list_saved_queries(self, customer_id: str, 
                                created_by: Optional[str] = None,
                                query_type: Optional[str] = None,
                                limit: int = 50) -> List[Dict[str, Any]]:
        """List saved queries for a customer from database"""
        try:
            query = f"""SELECT * FROM {SAVED_QUERIES_TABLE} 
                       WHERE customer_id = %(customer_id)s AND status = %(status)s"""
            params = {"customer_id": customer_id, "status": STATUS_ACTIVE, "limit": limit}
            
            if created_by:
                query += " AND created_by = %(created_by)s"
                params["created_by"] = created_by
                
            if query_type:
                query += " AND query_type = %(query_type)s"
                params["query_type"] = query_type
            
            query += " ORDER BY updated_at DESC LIMIT %(limit)s"
            
            result = await self.db.execute_query(query, params)
            
            queries = []
            for row in result:
                query_data = dict(row)
                # Parse JSON fields
                query_data['query_definition'] = json.loads(query_data['query_definition'])
                query_data['tags'] = json.loads(query_data['tags']) if query_data['tags'] else []
                queries.append(query_data)
            
            return queries
            
        except Exception as e:
            logger.error("Failed to list saved queries", error=str(e), customer_id=customer_id)
            return []
    
    async def update_saved_query(self, query_id: str, customer_id: str, 
                                update_data: Dict[str, Any]) -> bool:
        """Update saved query in database"""
        try:
            # First check if the query exists
            existing_query = await self.get_saved_query(query_id, customer_id)
            if not existing_query:
                return False  # Query not found
            
            # Build dynamic update query
            set_clauses = []
            params = {'query_id': query_id, 'customer_id': customer_id}
            
            for field, value in update_data.items():
                if field in ['name', 'description', 'query_definition', 'tags', 'is_public']:
                    if field in ['query_definition', 'tags']:
                        value = json.dumps(value)
                    set_clauses.append(f"{field} = %({field})s")
                    params[field] = value
            
            if not set_clauses:
                return False
            
            set_clauses.append("updated_at = %(updated_at)s")
            params["updated_at"] = datetime.now(timezone.utc)
                
            # ClickHouse requires ALTER TABLE ... UPDATE syntax
            set_clause = ', '.join(set_clauses)
            query = f"""ALTER TABLE {SAVED_QUERIES_TABLE} UPDATE {set_clause} 
                       WHERE id = %(query_id)s AND customer_id = %(customer_id)s"""
            
            await self.db.execute_query(query, params)
            
            logger.info("Saved query updated", query_id=query_id, customer_id=customer_id)
            return True
            
        except Exception as e:
            logger.error("Failed to update saved query", error=str(e), query_id=query_id)
            return False
    
    async def delete_saved_query(self, query_id: str, customer_id: str) -> bool:
        """Delete (deactivate) saved query in database"""
        try:
            # ClickHouse requires ALTER TABLE ... UPDATE syntax
            await self.db.execute_query(
                f"""ALTER TABLE {SAVED_QUERIES_TABLE} UPDATE 
                   status = %(status)s, updated_at = %(updated_at)s
                   WHERE id = %(query_id)s AND customer_id = %(customer_id)s""",
                {
                    "status": STATUS_INACTIVE,
                    "updated_at": datetime.now(timezone.utc),
                    "query_id": query_id,
                    "customer_id": customer_id
                }
            )
            
            logger.info("Saved query deleted", query_id=query_id, customer_id=customer_id)
            return True
            
        except Exception as e:
            logger.error("Failed to delete saved query", error=str(e), query_id=query_id)
            return False
    
    # Query caching operations
    
    async def cache_query_result(self, cache_key: str, customer_id: str, 
                                query_data: Dict[str, Any], result: Dict[str, Any],
                                ttl_seconds: int = 300) -> str:
        """Cache query result in database"""
        try:
            cache_id = str(uuid.uuid4())
            
            cache_data = {
                'id': cache_id,
                'customer_id': customer_id,
                'cache_key': cache_key,
                'query_definition': json.dumps(query_data),
                'result_data': json.dumps(result),
                'created_at': datetime.now(timezone.utc),
                'expires_at': datetime.now(timezone.utc).timestamp() + ttl_seconds
            }
            
            await self.db.execute_query(
                f"""INSERT INTO {QUERY_CACHE_TABLE} 
                   (id, customer_id, cache_key, query_definition, result_data, created_at, expires_at)
                   VALUES (%(id)s, %(customer_id)s, %(cache_key)s, %(query_definition)s, 
                   %(result_data)s, %(created_at)s, %(expires_at)s)""",
                cache_data
            )
            
            return cache_id
            
        except Exception as e:
            logger.error("Failed to cache query result", error=str(e))
            return ""
    
    async def get_cached_result(self, cache_key: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get cached query result from database"""
        try:
            result = await self.db.execute_query(
                f"""SELECT * FROM {QUERY_CACHE_TABLE} 
                   WHERE cache_key = %(cache_key)s AND customer_id = %(customer_id)s 
                   AND expires_at > %(current_time)s""",
                {
                    "cache_key": cache_key,
                    "customer_id": customer_id,
                    "current_time": datetime.now(timezone.utc).timestamp()
                }
            )
            
            if result:
                cached_data = dict(result[0])
                cached_data['result_data'] = json.loads(cached_data['result_data'])
                return cached_data
            return None
            
        except Exception as e:
            logger.error("Failed to get cached result", error=str(e))
            return None
    
    async def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries"""
        try:
            await self.db.execute_query(
                f"""DELETE FROM {QUERY_CACHE_TABLE} 
                   WHERE expires_at <= %(current_time)s""",
                {"current_time": datetime.now(timezone.utc).timestamp()}
            )
            
            logger.info("Cleaned up expired query cache entries")
            return 1  # Success indicator
            
        except Exception as e:
            logger.error("Failed to cleanup expired cache", error=str(e))
            return 0