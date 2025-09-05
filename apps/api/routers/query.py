"""
Advanced query API endpoints - M2 core functionality
"""

import json
from typing import Dict, Any, List
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel

from models import QueryResponse
from query_engine import AdvancedQueryRequest, QueryFilter, QueryOperator
from storage_config import get_customer_id
from tenant_dependencies import MiddlewareTenant

router = APIRouter(prefix="/v1")

# Global instances (will be injected)
query_engine = None
clickhouse_client = None

def setup_dependencies(qe, client):
    """Setup dependencies from main app"""
    global query_engine, clickhouse_client
    query_engine = qe
    clickhouse_client = client

# Define TimeseriesQueryRequest model here since it's query-specific
class TimeseriesQueryRequest(BaseModel):
    start_time: datetime
    end_time: datetime
    interval: str = "1h"  # 1m, 5m, 15m, 30m, 1h, 6h, 12h, 24h
    metrics: List[str] = []  # Optional, can be derived from aggregations
    filters: List[Dict[str, Any]] = []
    group_by: List[str] = []
    aggregations: List[Dict[str, Any]] = []  # For M2 compatibility
    granularity: str = "hour"  # For M2 compatibility


# Advanced Query Engine Endpoints (M2 Core)

@router.post("/query/advanced", response_model=QueryResponse)
async def advanced_query_logs(query_request: AdvancedQueryRequest, customer_id: str = MiddlewareTenant):
    """Advanced log querying with filters, aggregations, and analysis"""
    try:
        
        if not query_engine:
            raise HTTPException(status_code=500, detail="Query engine not initialized")
        
        # Add customer_id filter to ensure multi-tenant isolation
        if not query_request.filters:
            query_request.filters = []
        query_request.filters.append(QueryFilter(
            field="customer_id",
            operator=QueryOperator.EQ,
            value=customer_id
        ))
        
        # Execute advanced query
        result = await query_engine.execute_query(query_request)
        
        # result is already a QueryResponse object, just return it
        result.customer_id = customer_id
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Advanced query failed: {str(e)}")

@router.post("/query/aggregate")
async def aggregate_logs(query_data: Dict[str, Any], customer_id: str = MiddlewareTenant):
    """Aggregate log data with grouping and calculations"""
    try:
        
        if not query_engine:
            raise HTTPException(status_code=500, detail="Query engine not initialized")
        
        # Add customer_id filter to ensure multi-tenant isolation
        if "filters" not in query_data:
            query_data["filters"] = []
        query_data["filters"].append({
            "field": "customer_id",
            "operator": "eq",
            "value": customer_id
        })
        
        # Build aggregation query
        result = await query_engine.execute_query(query_data)
        
        return {
            "aggregations": result.aggregations or {},
            "group_by": query_data.get("group_by", []),
            "total_groups": result.total_count or 0,
            "execution_time_ms": result.execution_time_ms or 0,
            "customer_id": customer_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Aggregation failed: {str(e)}")

@router.post("/query/timeseries")
async def timeseries_query(query_request: TimeseriesQueryRequest, customer_id: str = MiddlewareTenant):
    """Time-series analysis endpoint for trends and patterns"""
    try:
        
        if not query_engine:
            raise HTTPException(status_code=500, detail="Query engine not initialized")
        
        # Add customer_id filter to ensure multi-tenant isolation
        query_data = query_request.model_dump()
        if "filters" not in query_data:
            query_data["filters"] = []
        query_data["filters"].append({
            "field": "customer_id",
            "operator": "eq",
            "value": customer_id
        })
        
        # Execute time-series query
        result = await query_engine.execute_query(query_data)
        
        return {
            "buckets": result.aggregations.get("time_series", []),
            "aggregations": result.aggregations or {},
            "total_count": result.total_count or 0,
            "execution_time_ms": result.execution_time_ms or 0,
            "customer_id": customer_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Timeseries query failed: {str(e)}")

# Saved Query Management

@router.get("/query/saved")
async def list_saved_queries(customer_id: str = MiddlewareTenant):
    """List saved queries for the customer"""
    # Placeholder - implement saved query storage
    return {"saved_queries": [], "customer_id": customer_id}

@router.post("/query/saved") 
async def save_query(query_data: Dict[str, Any], customer_id: str = MiddlewareTenant):
    """Save a query for future use"""
    # Placeholder - implement saved query storage
    return {"status": "saved", "customer_id": customer_id}

@router.get("/query/saved/{query_id}")
async def get_saved_query(query_id: str, customer_id: str = MiddlewareTenant):
    """Retrieve a specific saved query"""
    # Placeholder - implement saved query retrieval
    return {"query_id": query_id, "customer_id": customer_id}

# Data Export Endpoints

@router.post("/export")
async def export_query_results(export_request: Dict[str, Any], customer_id: str = MiddlewareTenant):
    """Export query results in various formats (JSON, CSV, etc.)"""
    try:
        
        # Get query results first
        if not query_engine:
            raise HTTPException(status_code=500, detail="Query engine not initialized")
        
        query_data = export_request.get("query", {})
        export_format = export_request.get("format", "json")
        
        # Add customer_id filter to ensure multi-tenant isolation
        if "filters" not in query_data:
            query_data["filters"] = []
        query_data["filters"].append({
            "field": "customer_id",
            "operator": "eq",
            "value": customer_id
        })
        
        # Execute query
        result = await query_engine.execute_query(query_data)
        
        # Format results based on requested format
        if export_format.lower() == "csv":
            # Convert to CSV format
            csv_data = "timestamp,level,service,message,host\n"
            for log in result.logs or []:
                csv_data += f"{log.get('ts')},{log.get('level')},{log.get('service')},{log.get('msg')},{log.get('host')}\n"
            
            return {
                "data": csv_data,
                "format": "csv",
                "count": result.total_count or 0,
                "customer_id": customer_id
            }
        else:
            # Default JSON format
            return {
                "data": result.logs or [],
                "format": "json", 
                "count": result.total_count or 0,
                "customer_id": customer_id
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

# Basic log retrieval for M0 compatibility
@router.get("/logs")
async def get_logs(
    service: str = Query(None, description="Filter by service name"),
    level: str = Query(None, description="Filter by log level"),
    limit: int = Query(100, description="Maximum number of logs to return"),
    offset: int = Query(0, description="Number of logs to skip"),
    customer_id: str = MiddlewareTenant
):
    """Simple log retrieval endpoint for basic queries (M0 compatibility)"""
    try:
        
        if not clickhouse_client:
            raise HTTPException(status_code=500, detail="Database client not initialized")
        
        # Build a simple query
        where_conditions = [f"customer_id = '{customer_id}'"]
        
        if service:
            where_conditions.append(f"service = '{service}'")
        if level:
            where_conditions.append(f"level = '{level}'")
        
        where_clause = " AND ".join(where_conditions)
        
        # Simple query to get logs
        query = f"""
        SELECT ts, service, level, msg, host, trace_id, customer_id
        FROM logs_raw_mt
        WHERE {where_clause}
        ORDER BY ts DESC
        LIMIT {limit} OFFSET {offset}
        """
        
        result = clickhouse_client.query(query)
        
        # Convert to expected format
        logs = []
        for row in result.result_rows:
            logs.append({
                "ts": row[0].isoformat() if hasattr(row[0], 'isoformat') else str(row[0]),
                "service": row[1],
                "level": row[2],
                "msg": row[3],
                "host": row[4],
                "trace_id": row[5],
                "customer_id": row[6]
            })
        
        # Get total count for pagination
        count_query = f"""
        SELECT count() FROM logs_raw_mt WHERE {where_clause}
        """
        total_result = clickhouse_client.query(count_query)
        total = total_result.result_rows[0][0] if total_result.result_rows else 0
        
        return {
            "logs": logs,
            "total": total,
            "limit": limit,
            "offset": offset,
            "customer_id": customer_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Log retrieval failed: {str(e)}")