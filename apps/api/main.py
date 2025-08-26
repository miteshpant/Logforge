from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union
import clickhouse_connect
import structlog
import yaml
import os
import json
import asyncio
import re
import time
from pathlib import Path
from dataclasses import asdict

from models import (
    LogEntry, BatchLogEntry, SyslogEntry, CEFEntry, NginxAccessEntry,
    StructuredLogEntry, TextLogEntry, OTLPLogsData, IngestResponse,
    BatchIngestResponse, HealthResponse, IngestFormat
)
from parsers import ParserFactory, ParseError
from storage_config import StorageConfigManager
from ttl_manager import TTLManager, TTLScheduler
from query_engine import (
    AdvancedQueryEngine, AdvancedQueryRequest, QueryResponse,
    SavedQuery, QueryFilter, QueryAggregation
)
from dashboard_engine import DashboardEngine, DashboardDefinition, DashboardData
from alert_engine import (
    AlertEngine, AlertRule, AlertInstance, AlertCondition,
    AlertSeverity, AlertStatus, AlertRuleType, ThresholdOperator,
    AlertRuleCreateRequest, AlertRuleResponse, AlertInstanceResponse,
    alert_engine
)
from query_engine import QueryFilter
from test_runner_api import router as test_runner_router
from security_api import router as security_router

# Configure structured logging
logger = structlog.get_logger()

app = FastAPI(
    title="Logforge API",
    description="Open Observability + SIEM Platform API",
    version="0.1.0"
)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize storage config manager
storage_manager = StorageConfigManager()

# Initialize parser factory
parser_factory = ParserFactory()

# Initialize TTL manager (will be initialized on startup)
ttl_manager = None
ttl_scheduler = None

# Initialize query engine (will be initialized with ClickHouse client)
query_engine = None

# Initialize dashboard engine (will be initialized with query engine)
dashboard_engine = None

# Initialize alert engine (will be started on application startup)
alert_engine_instance = None

# Include test runner router
app.include_router(test_runner_router)

# Include security analytics router
app.include_router(security_router)

# Background task for async log processing with multi-tenancy support
async def process_log_batch(logs: List[LogEntry], client, customer_id: str = "default"):
    """Process log batch in background with multi-tenant support"""
    try:
        # Insert into both old and new tables for compatibility
        data_rows_raw = []
        data_rows_mt = []

        for log_entry in logs:
            # Extract additional fields for normalized table
            http_method = log_entry.attrs.get('http_method', '') if log_entry.attrs else ''
            http_uri = log_entry.attrs.get('http_uri', '') if log_entry.attrs else ''
            http_status = log_entry.attrs.get('http_status', 0) if log_entry.attrs else 0
            http_response_time_ms = log_entry.attrs.get('http_response_time_ms', 0) if log_entry.attrs else 0
            http_bytes = log_entry.attrs.get('http_bytes', 0) if log_entry.attrs else 0
            error_code = log_entry.attrs.get('error_code', '') if log_entry.attrs else ''
            error_category = log_entry.attrs.get('error_category', '') if log_entry.attrs else ''
            extracted_user_id = log_entry.attrs.get('extracted_user_id', '') if log_entry.attrs else ''
            extracted_ip = log_entry.attrs.get('extracted_ip', '') if log_entry.attrs else ''

            # Multi-tenant raw logs
            data_row_mt = [
                customer_id,                    # customer_id
                log_entry.ts,                  # ts
                log_entry.level,              # level
                log_entry.msg,                # msg
                log_entry.host or "",         # host
                log_entry.service,            # service
                log_entry.trace_id or "",     # trace_id
                log_entry.span_id or "",      # span_id
                json.dumps(log_entry.attrs or {}),  # raw_data
            ]
            data_rows_mt.append(data_row_mt)

            # Legacy table for compatibility
            attrs_json = json.dumps(log_entry.attrs or {})
            data_row_legacy = [
                log_entry.ts,
                log_entry.host or "",
                log_entry.service,
                log_entry.level,
                log_entry.msg,
                log_entry.trace_id or "",
                log_entry.span_id or "",
                attrs_json,
                log_entry.status or 0,
                log_entry.src_ip or "",
                log_entry.user_id or "",
                log_entry.severity_num or 0,
                log_entry.facility or 16,
                log_entry.parser_version or "v1"
            ]
            data_rows_raw.append(data_row_legacy)

        # Insert into multi-tenant table
        client.insert(
            "logs_raw_mt",
            data_rows_mt,
            column_names=[
                'customer_id', 'ts', 'level', 'msg', 'host', 'service',
                'trace_id', 'span_id', 'raw_data'
            ]
        )

        # Insert into legacy table for compatibility
        client.insert(
            "logs_raw",
            data_rows_raw,
            column_names=[
                'ts', 'host', 'service', 'level', 'msg', 'trace_id', 'span_id',
                'attrs', 'status', 'src_ip', 'user_id', 'severity_num', 'facility', 'parser_version'
            ]
        )

        logger.info("Multi-tenant batch inserted", count=len(logs), customer_id=customer_id)

    except Exception as e:
        logger.error("Failed to insert batch", error=str(e), count=len(logs))

# Configuration
def load_config():
    config_path = Path("/app/config/logforge.yaml")
    if config_path.exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return {
        "storage": {
            "clickhouse_url": os.getenv("CLICKHOUSE_URL", "http://clickhouse:8123"),
            "clickhouse_user": os.getenv("CLICKHOUSE_USER", "logforge"),
            "clickhouse_password": os.getenv("CLICKHOUSE_PASSWORD", "logforge123"),
            "clickhouse_database": os.getenv("CLICKHOUSE_DATABASE", "logforge")
        }
    }

config = load_config()

# ClickHouse connection
def get_clickhouse_client():
    try:
        client = clickhouse_connect.get_client(
            host=config["storage"]["clickhouse_url"].replace("http://", "").split(":")[0],
            port=int(config["storage"]["clickhouse_url"].split(":")[-1]) if ":" in config["storage"]["clickhouse_url"] else 8123,
            username=config["storage"]["clickhouse_user"],
            password=config["storage"]["clickhouse_password"],
            database=config["storage"]["clickhouse_database"]
        )
        return client
    except Exception as e:
        logger.error("Failed to connect to ClickHouse", error=str(e))
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    services = {}

    # Check ClickHouse connection
    try:
        client = get_clickhouse_client()
        result = client.query("SELECT 1")
        services["clickhouse"] = "healthy"
    except Exception as e:
        services["clickhouse"] = f"unhealthy: {str(e)}"
        logger.error("ClickHouse health check failed", error=str(e))

    overall_status = "healthy" if all(status == "healthy" for status in services.values()) else "unhealthy"

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        services=services
    )

@app.post("/v1/ingest/logs", response_model=IngestResponse)
async def ingest_logs(log_entry: LogEntry):
    """Ingest log entries into ClickHouse"""
    try:
        client = get_clickhouse_client()

        # Prepare data for insertion (convert attrs dict to JSON string)
        import json
        attrs_json = json.dumps(log_entry.attrs or {})

        data = [
            log_entry.ts,
            log_entry.host or "",
            log_entry.service,
            log_entry.level,
            log_entry.msg,
            log_entry.trace_id or "",
            attrs_json,
            log_entry.status or 0,
            log_entry.src_ip or "",
            log_entry.user_id or ""
        ]

        # Insert into logs_raw table
        client.insert(
            "logs_raw",
            [data],
            column_names=['ts', 'host', 'service', 'level', 'msg', 'trace_id', 'attrs', 'status', 'src_ip', 'user_id']
        )

        logger.info("Log entry inserted", service=log_entry.service, level=log_entry.level)

        return IngestResponse(
            status="success",
            message="Log entry ingested successfully",
            log_id=log_entry.trace_id
        )

    except Exception as e:
        logger.error("Failed to ingest log entry", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to ingest log: {str(e)}")

# Enhanced Multi-Format Ingestion Endpoints

@app.post("/v1/ingest/logs/batch", response_model=BatchIngestResponse)
async def ingest_logs_batch(batch: BatchLogEntry, background_tasks: BackgroundTasks, request: Request):
    """Ingest batch of log entries"""
    try:
        client = get_clickhouse_client()

        # Extract customer_id from headers
        customer_id = request.headers.get("X-Customer-ID", "default")
        # Process batch in background for better performance
        background_tasks.add_task(process_log_batch, batch.logs, client, customer_id)

        return BatchIngestResponse(
            status="accepted",
            message=f"Batch of {len(batch.logs)} logs accepted for processing",
            processed_count=len(batch.logs)
        )

    except Exception as e:
        logger.error("Failed to accept batch", error=str(e), batch_size=len(batch.logs))
        raise HTTPException(status_code=500, detail=f"Failed to accept batch: {str(e)}")

@app.post("/v1/ingest/logs/bulk", response_model=BatchIngestResponse)
async def ingest_logs_bulk(bulk_data: Dict[str, Any], background_tasks: BackgroundTasks, request: Request):
    """Ingest bulk logs from integration test"""
    try:
        client = get_clickhouse_client()

        # Extract customer_id from headers
        customer_id = request.headers.get("X-Customer-ID", "default")

        # Handle different bulk formats
        logs_data = bulk_data.get("logs", [])

        # Convert to LogEntry objects
        log_entries = []
        for log_data in logs_data:
            log_entry = LogEntry(
                ts=log_data.get("ts", datetime.utcnow().isoformat()),
                service=log_data.get("service", "unknown"),
                level=log_data.get("level", "INFO"),
                msg=log_data.get("msg", ""),
                host=log_data.get("host", ""),
                trace_id=log_data.get("trace_id", ""),
                span_id=log_data.get("span_id", ""),
                user_id=log_data.get("user_id", ""),
                src_ip=log_data.get("src_ip", ""),
                attrs=log_data
            )
            log_entries.append(log_entry)

        # Process batch in background for better performance
        background_tasks.add_task(process_log_batch, log_entries, client, customer_id)

        return BatchIngestResponse(
            status="accepted",
            message=f"Bulk of {len(log_entries)} logs accepted for processing",
            processed_count=len(log_entries)
        )

    except Exception as e:
        logger.error("Failed to accept bulk", error=str(e), bulk_size=len(bulk_data.get("logs", [])))
        raise HTTPException(status_code=500, detail=f"Failed to accept bulk: {str(e)}")

@app.post("/v1/ingest/otlp", response_model=BatchIngestResponse)
async def ingest_otlp_logs(otlp_data: OTLPLogsData, background_tasks: BackgroundTasks):
    """Ingest OpenTelemetry Protocol (OTLP) logs"""
    try:
        parser = parser_factory.create_parser('otlp')
        log_entries = parser.parse_batch(otlp_data)

        if not log_entries:
            return BatchIngestResponse(
                status="success",
                message="No log entries to process",
                processed_count=0
            )

        client = get_clickhouse_client()
        background_tasks.add_task(process_log_batch, log_entries, client, "default")

        return BatchIngestResponse(
            status="accepted",
            message=f"OTLP batch with {len(log_entries)} logs accepted for processing",
            processed_count=len(log_entries)
        )

    except ParseError as e:
        logger.error("OTLP parse error", error=str(e))
        raise HTTPException(status_code=400, detail=f"OTLP parse error: {str(e)}")
    except Exception as e:
        logger.error("Failed to process OTLP logs", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to process OTLP logs: {str(e)}")

@app.post("/v1/ingest/syslog", response_model=IngestResponse)
async def ingest_syslog(request: Request):
    """Ingest syslog messages (RFC 3164/5424)"""
    try:
        raw_message = (await request.body()).decode('utf-8')

        parser = parser_factory.create_parser('syslog')
        log_entry = parser.parse(raw_message)

        client = get_clickhouse_client()
        await process_log_batch([log_entry], client, "default")

        return IngestResponse(
            status="success",
            message="Syslog message ingested successfully",
            log_id=log_entry.trace_id
        )

    except ParseError as e:
        logger.error("Syslog parse error", error=str(e), raw_message=raw_message[:200])
        raise HTTPException(status_code=400, detail=f"Syslog parse error: {str(e)}")
    except Exception as e:
        logger.error("Failed to ingest syslog", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to ingest syslog: {str(e)}")

@app.post("/v1/ingest/nginx", response_model=IngestResponse)
async def ingest_nginx_logs(request: Request):
    """Ingest Nginx access logs"""
    try:
        raw_message = (await request.body()).decode('utf-8')

        parser = parser_factory.create_parser('nginx')
        log_entry = parser.parse(raw_message)

        client = get_clickhouse_client()
        await process_log_batch([log_entry], client, "default")

        return IngestResponse(
            status="success",
            message="Nginx log ingested successfully",
            log_id=log_entry.trace_id
        )

    except ParseError as e:
        logger.error("Nginx parse error", error=str(e), raw_message=raw_message[:200])
        raise HTTPException(status_code=400, detail=f"Nginx parse error: {str(e)}")
    except Exception as e:
        logger.error("Failed to ingest nginx log", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to ingest nginx log: {str(e)}")

@app.post("/v1/ingest/cef", response_model=IngestResponse)
async def ingest_cef_logs(request: Request):
    """Ingest Common Event Format (CEF) logs"""
    try:
        raw_message = (await request.body()).decode('utf-8')

        parser = parser_factory.create_parser('cef')
        log_entry = parser.parse(raw_message)

        client = get_clickhouse_client()
        await process_log_batch([log_entry], client, "default")

        return IngestResponse(
            status="success",
            message="CEF log ingested successfully",
            log_id=log_entry.trace_id
        )

    except ParseError as e:
        logger.error("CEF parse error", error=str(e), raw_message=raw_message[:200])
        raise HTTPException(status_code=400, detail=f"CEF parse error: {str(e)}")
    except Exception as e:
        logger.error("Failed to ingest CEF log", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to ingest CEF log: {str(e)}")

@app.post("/v1/ingest/text", response_model=IngestResponse)
async def ingest_text_logs(request: Request,
                          service: Optional[str] = "unknown",
                          host: Optional[str] = ""):
    """Ingest plain text logs with pattern matching"""
    try:
        raw_message = (await request.body()).decode('utf-8')

        parser = parser_factory.create_parser('text')
        log_entry = parser.parse(raw_message, service=service, host=host)

        client = get_clickhouse_client()
        await process_log_batch([log_entry], client, "default")

        return IngestResponse(
            status="success",
            message="Text log ingested successfully",
            log_id=log_entry.trace_id
        )

    except ParseError as e:
        logger.error("Text parse error", error=str(e), raw_message=raw_message[:200])
        raise HTTPException(status_code=400, detail=f"Text parse error: {str(e)}")
    except Exception as e:
        logger.error("Failed to ingest text log", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to ingest text log: {str(e)}")

@app.post("/v1/ingest/structured", response_model=IngestResponse)
async def ingest_structured_logs(log_data: StructuredLogEntry):
    """Ingest structured JSON application logs"""
    try:
        # Convert structured log to LogEntry
        attrs = log_data.dict()
        msg = attrs.pop('message', '')
        level = attrs.pop('level', 'info')
        timestamp = attrs.pop('timestamp', datetime.utcnow())

        log_entry = LogEntry(
            ts=timestamp,
            host=attrs.pop('host', ''),
            service=attrs.pop('logger', 'app'),
            level=level,
            msg=msg,
            trace_id=attrs.pop('correlation_id', attrs.pop('request_id', '')),
            user_id=attrs.pop('user_id', ''),
            attrs=attrs
        )

        client = get_clickhouse_client()
        await process_log_batch([log_entry], client, "default")

        return IngestResponse(
            status="success",
            message="Structured log ingested successfully",
            log_id=log_entry.trace_id
        )

    except Exception as e:
        logger.error("Failed to ingest structured log", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to ingest structured log: {str(e)}")

# Generic format-aware endpoint
@app.post("/v1/ingest", response_model=IngestResponse)
async def ingest_auto_detect(request: Request,
                            format: Optional[IngestFormat] = None,
                            service: Optional[str] = "unknown",
                            host: Optional[str] = ""):
    """Auto-detect format and ingest logs"""
    try:
        raw_message = (await request.body()).decode('utf-8')

        # Auto-detect format if not specified
        if not format:
            format = _detect_log_format(raw_message)

        parser = parser_factory.create_parser(format.value)
        log_entry = parser.parse(raw_message, service=service, host=host)

        client = get_clickhouse_client()
        await process_log_batch([log_entry], client, "default")

        return IngestResponse(
            status="success",
            message=f"Log ingested successfully (detected format: {format.value})",
            log_id=log_entry.trace_id
        )

    except ParseError as e:
        logger.error("Auto-detect parse error", error=str(e), detected_format=format)
        raise HTTPException(status_code=400, detail=f"Parse error: {str(e)}")
    except Exception as e:
        logger.error("Failed to auto-ingest log", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to ingest log: {str(e)}")

def _detect_log_format(raw_message: str) -> IngestFormat:
    """Detect log format from raw message"""
    message = raw_message.strip()

    # JSON format
    if message.startswith('{') and message.endswith('}'):
        return IngestFormat.JSON

    # CEF format
    if message.startswith('CEF:'):
        return IngestFormat.CEF

    # Syslog format (with priority)
    if re.match(r'^<\d+>', message):
        return IngestFormat.SYSLOG

    # Nginx combined log format
    if re.match(r'^\S+ - \S+ \[[^\]]+\] "[^"]*" \d+ \d+', message):
        return IngestFormat.NGINX

    # Default to text format
    return IngestFormat.TEXT

@app.get("/v1/logs")
async def get_logs(
    limit: int = 100,
    service: Optional[str] = None,
    level: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
):
    """Query logs from ClickHouse"""
    try:
        client = get_clickhouse_client()

        # Build query
        where_conditions = []
        if service:
            where_conditions.append(f"service = '{service}'")
        if level:
            where_conditions.append(f"level = '{level}'")
        if start_time:
            where_conditions.append(f"ts >= '{start_time.isoformat()}'")
        if end_time:
            where_conditions.append(f"ts <= '{end_time.isoformat()}'")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        query = f"""
        SELECT ts, host, service, level, msg, trace_id, attrs, status, src_ip, user_id
        FROM logs_raw
        WHERE {where_clause}
        ORDER BY ts DESC
        LIMIT {limit}
        """

        result = client.query(query)

        logs = []
        for row in result.result_rows:
            # Parse JSON string back to dict
            import json
            try:
                attrs = json.loads(row[6]) if row[6] else {}
            except:
                attrs = {}

            logs.append({
                "ts": row[0],
                "host": row[1],
                "service": row[2],
                "level": row[3],
                "msg": row[4],
                "trace_id": row[5],
                "attrs": attrs,
                "status": row[7],
                "src_ip": row[8],
                "user_id": row[9]
            })

        return {"logs": logs, "total": len(logs)}

    except Exception as e:
        logger.error("Failed to query logs", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to query logs: {str(e)}")


# Advanced Query Engine Endpoints (M2 Core)

@app.post("/v1/query/advanced", response_model=QueryResponse)
async def advanced_query(query: AdvancedQueryRequest):
    """Execute advanced query with complex filtering, aggregation, and time-series analysis"""
    try:
        if not query_engine:
            raise HTTPException(status_code=503, detail="Query engine not initialized")

        # Execute the advanced query
        result = await query_engine.execute_query(query)

        logger.info("Advanced query executed",
                   execution_time=result.execution_time_ms,
                   total_count=result.total_count,
                   has_aggregations=bool(query.aggregations))

        return result

    except Exception as e:
        logger.error("Failed to execute advanced query", error=str(e))
        raise HTTPException(status_code=500, detail=f"Advanced query failed: {str(e)}")


@app.post("/v1/query/aggregate")
async def aggregate_query(
    start_time: datetime,
    end_time: datetime,
    aggregations: List[QueryAggregation],
    group_by: List[str] = [],
    filters: List[QueryFilter] = [],
    time_series: bool = False,
    time_granularity: str = "hour"
):
    """Execute aggregation query with grouping and time-series support"""
    try:
        if not query_engine:
            raise HTTPException(status_code=503, detail="Query engine not initialized")

        # Build advanced query request from parameters
        from query_engine import TimeGranularity

        granularity_map = {
            "second": TimeGranularity.SECOND,
            "minute": TimeGranularity.MINUTE,
            "hour": TimeGranularity.HOUR,
            "day": TimeGranularity.DAY,
            "week": TimeGranularity.WEEK,
            "month": TimeGranularity.MONTH
        }

        query_request = AdvancedQueryRequest(
            start_time=start_time,
            end_time=end_time,
            aggregations=aggregations,
            group_by=group_by,
            filters=filters,
            time_series=time_series,
            time_granularity=granularity_map.get(time_granularity, TimeGranularity.HOUR)
        )

        result = await query_engine.execute_query(query_request)
        return result

    except Exception as e:
        logger.error("Failed to execute aggregation query", error=str(e))
        raise HTTPException(status_code=500, detail=f"Aggregation query failed: {str(e)}")


@app.post("/v1/query/timeseries")
async def timeseries_query(
    start_time: datetime,
    end_time: datetime,
    aggregations: List[QueryAggregation],
    granularity: str = "hour",
    group_by: List[str] = [],
    filters: List[QueryFilter] = []
):
    """Execute time-series analysis query"""
    try:
        if not query_engine:
            raise HTTPException(status_code=503, detail="Query engine not initialized")

        from query_engine import TimeGranularity

        granularity_map = {
            "second": TimeGranularity.SECOND,
            "minute": TimeGranularity.MINUTE,
            "hour": TimeGranularity.HOUR,
            "day": TimeGranularity.DAY,
            "week": TimeGranularity.WEEK,
            "month": TimeGranularity.MONTH
        }

        query_request = AdvancedQueryRequest(
            start_time=start_time,
            end_time=end_time,
            aggregations=aggregations,
            group_by=group_by,
            filters=filters,
            time_series=True,
            time_granularity=granularity_map.get(granularity, TimeGranularity.HOUR)
        )

        result = await query_engine.execute_query(query_request)
        return result

    except Exception as e:
        logger.error("Failed to execute time-series query", error=str(e))
        raise HTTPException(status_code=500, detail=f"Time-series query failed: {str(e)}")


# Saved Query Management

@app.get("/v1/query/saved")
async def get_saved_queries():
    """Get all saved queries"""
    # TODO: Implement saved query storage (will use ClickHouse or separate DB)
    return {"saved_queries": [], "message": "Saved queries feature coming in next update"}


@app.post("/v1/query/saved")
async def save_query(saved_query: SavedQuery):
    """Save a query for later use"""
    # TODO: Implement saved query storage
    return {"message": "Query saved successfully", "id": "temp_id", "saved_query": saved_query}


@app.get("/v1/query/saved/{query_id}")
async def get_saved_query(query_id: str):
    """Get a specific saved query"""
    # TODO: Implement saved query retrieval
    return {"message": "Saved query retrieval coming in next update", "query_id": query_id}


# Data Export Endpoints

@app.post("/v1/export")
async def export_data(
    query: AdvancedQueryRequest,
    format: str = "json",  # json, csv, pdf
    filename: Optional[str] = None
):
    """Export query results in various formats"""
    try:
        if not query_engine:
            raise HTTPException(status_code=503, detail="Query engine not initialized")

        # Execute the query
        result = await query_engine.execute_query(query)

        # Format the data based on requested format
        if format.lower() == "json":
            return {
                "data": result.logs if result.logs else result.aggregations,
                "metadata": {
                    "total_count": result.total_count,
                    "execution_time_ms": result.execution_time_ms,
                    "export_format": "json",
                    "filename": filename or f"logforge_export_{datetime.now().isoformat()}.json"
                }
            }

        elif format.lower() == "csv":
            # TODO: Implement CSV export
            return {"message": "CSV export coming in next update", "format": "csv"}

        elif format.lower() == "pdf":
            # TODO: Implement PDF export
            return {"message": "PDF export coming in next update", "format": "pdf"}

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported export format: {format}")

    except Exception as e:
        logger.error("Failed to export data", error=str(e))
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# Enterprise Dashboard Endpoints (M2 Core)

@app.get("/v1/dashboards")
async def get_dashboards():
    """Get list of available dashboards"""
    try:
        if not dashboard_engine:
            raise HTTPException(status_code=503, detail="Dashboard engine not initialized")

        dashboards = dashboard_engine.get_dashboard_list()
        return {"dashboards": dashboards, "total": len(dashboards)}

    except Exception as e:
        logger.error("Failed to get dashboards", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get dashboards: {str(e)}")


@app.get("/v1/dashboards/{dashboard_id}")
async def get_dashboard_definition(dashboard_id: str):
    """Get dashboard definition"""
    try:
        if not dashboard_engine:
            raise HTTPException(status_code=503, detail="Dashboard engine not initialized")

        dashboard = dashboard_engine.get_dashboard_definition(dashboard_id)
        if not dashboard:
            raise HTTPException(status_code=404, detail=f"Dashboard {dashboard_id} not found")

        return dashboard

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get dashboard definition", dashboard_id=dashboard_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard definition: {str(e)}")


@app.get("/v1/dashboards/{dashboard_id}/data")
async def get_dashboard_data(
    dashboard_id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
):
    """Get dashboard data with real-time widgets"""
    try:
        if not dashboard_engine:
            raise HTTPException(status_code=503, detail="Dashboard engine not initialized")

        # Prepare time range
        time_range = None
        if start_time or end_time:
            if not start_time:
                start_time = datetime.utcnow() - timedelta(hours=24)
            if not end_time:
                end_time = datetime.utcnow()
            time_range = {"start_time": start_time, "end_time": end_time}

        # Get dashboard data
        dashboard_data = await dashboard_engine.get_dashboard_data(dashboard_id, time_range)

        logger.info("Dashboard data generated",
                   dashboard_id=dashboard_id,
                   widget_count=len(dashboard_data.widgets))

        return dashboard_data

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to get dashboard data", dashboard_id=dashboard_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard data: {str(e)}")


@app.post("/v1/dashboards")
async def create_custom_dashboard(dashboard: DashboardDefinition):
    """Create custom dashboard (TODO: Implement storage)"""
    # TODO: Implement custom dashboard storage and management
    return {"message": "Custom dashboard creation coming in next update", "dashboard": dashboard}


@app.put("/v1/dashboards/{dashboard_id}")
async def update_dashboard(dashboard_id: str, dashboard_update: Dict[str, Any]):
    """Update dashboard configuration (TODO: Implement storage)"""
    # TODO: Implement dashboard update functionality
    return {"message": "Dashboard update coming in next update", "dashboard_id": dashboard_id}


@app.delete("/v1/dashboards/{dashboard_id}")
async def delete_dashboard(dashboard_id: str):
    """Delete custom dashboard (TODO: Implement storage)"""
    # TODO: Implement dashboard deletion
    return {"message": "Dashboard deletion coming in next update", "dashboard_id": dashboard_id}


# Dashboard Widget-Level Endpoints

@app.get("/v1/dashboards/{dashboard_id}/widgets/{widget_id}/data")
async def get_widget_data(
    dashboard_id: str,
    widget_id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
):
    """Get data for specific dashboard widget"""
    try:
        if not dashboard_engine:
            raise HTTPException(status_code=503, detail="Dashboard engine not initialized")

        # Get full dashboard data and extract widget
        time_range = None
        if start_time or end_time:
            if not start_time:
                start_time = datetime.utcnow() - timedelta(hours=24)
            if not end_time:
                end_time = datetime.utcnow()
            time_range = {"start_time": start_time, "end_time": end_time}

        dashboard_data = await dashboard_engine.get_dashboard_data(dashboard_id, time_range)

        widget_data = dashboard_data.widgets.get(widget_id)
        if not widget_data:
            raise HTTPException(status_code=404, detail=f"Widget {widget_id} not found in dashboard {dashboard_id}")

        return {
            "dashboard_id": dashboard_id,
            "widget_id": widget_id,
            "widget_data": widget_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get widget data", dashboard_id=dashboard_id, widget_id=widget_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get widget data: {str(e)}")


# TTL and Storage Management Endpoints

@app.get("/v1/storage/retention/{customer_id}")
async def get_retention_status(customer_id: str):
    """Get retention policy status for customer"""
    try:
        if not ttl_manager:
            raise HTTPException(status_code=503, detail="TTL manager not initialized")

        status = await ttl_manager.get_retention_status(customer_id)
        return status

    except Exception as e:
        logger.error("Failed to get retention status", customer_id=customer_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get retention status: {str(e)}")

@app.put("/v1/storage/retention/{customer_id}")
async def update_retention_policy(customer_id: str, policy_update: Dict[str, Any]):
    """Update retention policy for customer"""
    try:
        if not ttl_manager:
            raise HTTPException(status_code=503, detail="TTL manager not initialized")

        result = await ttl_manager.update_retention_policy(customer_id, policy_update)
        return result

    except Exception as e:
        logger.error("Failed to update retention policy", customer_id=customer_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to update retention policy: {str(e)}")

@app.post("/v1/storage/cleanup")
async def trigger_cleanup():
    """Trigger manual cleanup of expired data"""
    try:
        if not ttl_manager:
            raise HTTPException(status_code=503, detail="TTL manager not initialized")

        cleanup_stats = await ttl_manager.cleanup_expired_data()
        return {"status": "completed", "cleanup_stats": cleanup_stats}

    except Exception as e:
        logger.error("Failed to trigger cleanup", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger cleanup: {str(e)}")

@app.post("/v1/storage/archive/{customer_id}")
async def trigger_archive(customer_id: str, before_date: datetime):
    """Trigger manual archival of customer data to cold storage"""
    try:
        if not ttl_manager:
            raise HTTPException(status_code=503, detail="TTL manager not initialized")

        await ttl_manager.archive_to_cold_storage(customer_id, before_date)
        return {"status": "completed", "customer_id": customer_id, "archived_before": before_date}

    except Exception as e:
        logger.error("Failed to trigger archive", customer_id=customer_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger archive: {str(e)}")

@app.get("/v1/storage/health")
async def storage_health():
    """Get storage system health and metrics"""
    try:
        client = get_clickhouse_client()

        # Get overall storage statistics
        stats_query = """
        SELECT
            count() as total_logs,
            uniqHLL12(customer_id) as total_customers,
            sum(length(msg)) as total_bytes,
            min(ts) as earliest_log,
            max(ts) as latest_log,
            countIf(ts > now() - INTERVAL 24 HOUR) as logs_last_24h,
            countIf(is_error = 1) as total_errors
        FROM logs_normalized
        """

        result = client.query(stats_query)
        row = result.result_rows[0] if result.result_rows else [0] * 7

        # Get per-customer storage stats
        customer_stats_query = """
        SELECT
            customer_id,
            count() as log_count,
            sum(length(msg)) as storage_bytes,
            countIf(ts > now() - INTERVAL 24 HOUR) as recent_logs
        FROM logs_normalized
        GROUP BY customer_id
        ORDER BY log_count DESC
        LIMIT 10
        """

        customer_result = client.query(customer_stats_query)

        health_data = {
            "status": "healthy",
            "timestamp": datetime.utcnow(),
            "overall_stats": {
                "total_logs": row[0],
                "total_customers": row[1],
                "total_bytes": row[2],
                "earliest_log": row[3],
                "latest_log": row[4],
                "logs_last_24h": row[5],
                "total_errors": row[6]
            },
            "top_customers": [
                {
                    "customer_id": r[0],
                    "log_count": r[1],
                    "storage_bytes": r[2],
                    "recent_logs": r[3]
                }
                for r in customer_result.result_rows
            ],
            "ttl_manager_status": "active" if ttl_manager else "inactive"
        }

        return health_data

    except Exception as e:
        logger.error("Failed to get storage health", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get storage health: {str(e)}")


# ========== M3 Alert Engine Endpoints ==========

@app.post("/v1/alerts/rules", response_model=AlertRuleResponse)
async def create_alert_rule(rule_request: AlertRuleCreateRequest, request: Request):
    """Create a new alert rule"""
    try:
        if not alert_engine_instance:
            raise HTTPException(status_code=503, detail="Alert engine not initialized")

        # Extract customer_id from headers if not provided
        customer_id = request.headers.get("X-Customer-ID", rule_request.customer_id)

        # Build alert conditions from request
        conditions = []
        for cond_data in rule_request.conditions:
            condition = AlertCondition(
                field=cond_data.get("field"),
                operator=ThresholdOperator(cond_data.get("operator")),
                value=cond_data.get("value"),
                aggregation=cond_data.get("aggregation", "count"),
                time_window=cond_data.get("time_window", "5m")
            )
            conditions.append(condition)

        # Build filter conditions from request
        filters = []
        for filter_data in rule_request.filters:
            filter_condition = QueryFilter(
                field=filter_data.get("field"),
                operator=filter_data.get("operator"),
                value=filter_data.get("value")
            )
            filters.append(filter_condition)

        # Create alert rule
        rule = AlertRule(
            rule_id=f"rule-{int(time.time())}-{customer_id}",
            name=rule_request.name,
            description=rule_request.description,
            customer_id=customer_id,
            severity=rule_request.severity,
            rule_type=rule_request.rule_type,
            enabled=rule_request.enabled,
            conditions=conditions,
            filters=filters,
            notification_channels=rule_request.notification_channels,
            tags=rule_request.tags,
            evaluation_interval=rule_request.evaluation_interval,
            cooldown_period=rule_request.cooldown_period,
            max_alerts_per_hour=rule_request.max_alerts_per_hour,
            created_by=request.headers.get("X-User-ID", "api")
        )

        created_rule = await alert_engine_instance.create_rule(rule)

        # Convert to response model
        rule_response = AlertRuleResponse(
            rule_id=created_rule.rule_id,
            name=created_rule.name,
            description=created_rule.description,
            customer_id=created_rule.customer_id,
            severity=created_rule.severity,
            rule_type=created_rule.rule_type,
            enabled=created_rule.enabled,
            conditions=[asdict(c) for c in created_rule.conditions],
            filters=[asdict(f) for f in created_rule.filters],
            notification_channels=created_rule.notification_channels,
            tags=created_rule.tags,
            evaluation_interval=created_rule.evaluation_interval,
            cooldown_period=created_rule.cooldown_period,
            max_alerts_per_hour=created_rule.max_alerts_per_hour,
            created_at=created_rule.created_at,
            updated_at=created_rule.updated_at,
            created_by=created_rule.created_by
        )

        logger.info("Alert rule created", rule_id=created_rule.rule_id, customer_id=customer_id)
        return rule_response

    except Exception as e:
        logger.error("Failed to create alert rule", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create alert rule: {str(e)}")


@app.get("/v1/alerts/rules")
async def list_alert_rules(request: Request, customer_id: Optional[str] = None):
    """List alert rules, optionally filtered by customer"""
    try:
        if not alert_engine_instance:
            raise HTTPException(status_code=503, detail="Alert engine not initialized")

        # Use customer ID from header if not provided in query
        filter_customer_id = customer_id or request.headers.get("X-Customer-ID")

        rules = await alert_engine_instance.list_rules(filter_customer_id)

        rule_responses = []
        for rule in rules:
            rule_response = AlertRuleResponse(
                rule_id=rule.rule_id,
                name=rule.name,
                description=rule.description,
                customer_id=rule.customer_id,
                severity=rule.severity,
                rule_type=rule.rule_type,
                enabled=rule.enabled,
                conditions=[asdict(c) for c in rule.conditions],
                filters=[asdict(f) for f in rule.filters],
                notification_channels=rule.notification_channels,
                tags=rule.tags,
                evaluation_interval=rule.evaluation_interval,
                cooldown_period=rule.cooldown_period,
                max_alerts_per_hour=rule.max_alerts_per_hour,
                created_at=rule.created_at,
                updated_at=rule.updated_at,
                created_by=rule.created_by
            )
            rule_responses.append(rule_response)

        return {"rules": rule_responses, "total": len(rule_responses)}

    except Exception as e:
        logger.error("Failed to list alert rules", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list alert rules: {str(e)}")


@app.get("/v1/alerts/rules/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(rule_id: str):
    """Get alert rule by ID"""
    try:
        if not alert_engine_instance:
            raise HTTPException(status_code=503, detail="Alert engine not initialized")

        rule = await alert_engine_instance.get_rule(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail=f"Alert rule {rule_id} not found")

        rule_response = AlertRuleResponse(
            rule_id=rule.rule_id,
            name=rule.name,
            description=rule.description,
            customer_id=rule.customer_id,
            severity=rule.severity,
            rule_type=rule.rule_type,
            enabled=rule.enabled,
            conditions=[asdict(c) for c in rule.conditions],
            filters=[asdict(f) for f in rule.filters],
            notification_channels=rule.notification_channels,
            tags=rule.tags,
            evaluation_interval=rule.evaluation_interval,
            cooldown_period=rule.cooldown_period,
            max_alerts_per_hour=rule.max_alerts_per_hour,
            created_at=rule.created_at,
            updated_at=rule.updated_at,
            created_by=rule.created_by
        )

        return rule_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get alert rule", rule_id=rule_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get alert rule: {str(e)}")


@app.put("/v1/alerts/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(rule_id: str, updates: Dict[str, Any]):
    """Update alert rule"""
    try:
        if not alert_engine_instance:
            raise HTTPException(status_code=503, detail="Alert engine not initialized")

        updated_rule = await alert_engine_instance.update_rule(rule_id, updates)
        if not updated_rule:
            raise HTTPException(status_code=404, detail=f"Alert rule {rule_id} not found")

        rule_response = AlertRuleResponse(
            rule_id=updated_rule.rule_id,
            name=updated_rule.name,
            description=updated_rule.description,
            customer_id=updated_rule.customer_id,
            severity=updated_rule.severity,
            rule_type=updated_rule.rule_type,
            enabled=updated_rule.enabled,
            conditions=[asdict(c) for c in updated_rule.conditions],
            filters=[asdict(f) for f in updated_rule.filters],
            notification_channels=updated_rule.notification_channels,
            tags=updated_rule.tags,
            evaluation_interval=updated_rule.evaluation_interval,
            cooldown_period=updated_rule.cooldown_period,
            max_alerts_per_hour=updated_rule.max_alerts_per_hour,
            created_at=updated_rule.created_at,
            updated_at=updated_rule.updated_at,
            created_by=updated_rule.created_by
        )

        logger.info("Alert rule updated", rule_id=rule_id)
        return rule_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update alert rule", rule_id=rule_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to update alert rule: {str(e)}")


@app.delete("/v1/alerts/rules/{rule_id}")
async def delete_alert_rule(rule_id: str):
    """Delete alert rule"""
    try:
        if not alert_engine_instance:
            raise HTTPException(status_code=503, detail="Alert engine not initialized")

        success = await alert_engine_instance.delete_rule(rule_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Alert rule {rule_id} not found")

        logger.info("Alert rule deleted", rule_id=rule_id)
        return {"message": f"Alert rule {rule_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete alert rule", rule_id=rule_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete alert rule: {str(e)}")


@app.post("/v1/alerts/rules/{rule_id}/test")
async def test_alert_rule(rule_id: str):
    """Test alert rule evaluation without triggering notifications"""
    try:
        if not alert_engine_instance:
            raise HTTPException(status_code=503, detail="Alert engine not initialized")

        rule = await alert_engine_instance.get_rule(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail=f"Alert rule {rule_id} not found")

        test_result = await alert_engine_instance.test_rule(rule)

        return test_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to test alert rule", rule_id=rule_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to test alert rule: {str(e)}")


# Alert Instance Management

@app.get("/v1/alerts")
async def list_alerts(request: Request,
                     customer_id: Optional[str] = None,
                     status: Optional[AlertStatus] = None,
                     limit: int = 100):
    """List alerts with optional filters"""
    try:
        if not alert_engine_instance:
            raise HTTPException(status_code=503, detail="Alert engine not initialized")

        # Use customer ID from header if not provided in query
        filter_customer_id = customer_id or request.headers.get("X-Customer-ID")

        alerts = await alert_engine_instance.list_alerts(filter_customer_id, status)

        # Limit results
        alerts = alerts[:limit]

        alert_responses = []
        for alert in alerts:
            alert_response = AlertInstanceResponse(
                alert_id=alert.alert_id,
                rule_id=alert.rule_id,
                customer_id=alert.customer_id,
                name=alert.name,
                description=alert.description,
                severity=alert.severity,
                status=alert.status,
                triggered_at=alert.triggered_at,
                resolved_at=alert.resolved_at,
                acknowledged_at=alert.acknowledged_at,
                acknowledged_by=alert.acknowledged_by,
                trigger_data=alert.trigger_data,
                notification_count=alert.notification_count,
                last_notification_at=alert.last_notification_at,
                tags=alert.tags
            )
            alert_responses.append(alert_response)

        return {"alerts": alert_responses, "total": len(alert_responses)}

    except Exception as e:
        logger.error("Failed to list alerts", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list alerts: {str(e)}")


@app.get("/v1/alerts/{alert_id}", response_model=AlertInstanceResponse)
async def get_alert(alert_id: str):
    """Get alert instance by ID"""
    try:
        if not alert_engine_instance:
            raise HTTPException(status_code=503, detail="Alert engine not initialized")

        alert = await alert_engine_instance.get_alert(alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

        alert_response = AlertInstanceResponse(
            alert_id=alert.alert_id,
            rule_id=alert.rule_id,
            customer_id=alert.customer_id,
            name=alert.name,
            description=alert.description,
            severity=alert.severity,
            status=alert.status,
            triggered_at=alert.triggered_at,
            resolved_at=alert.resolved_at,
            acknowledged_at=alert.acknowledged_at,
            acknowledged_by=alert.acknowledged_by,
            trigger_data=alert.trigger_data,
            notification_count=alert.notification_count,
            last_notification_at=alert.last_notification_at,
            tags=alert.tags
        )

        return alert_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get alert", alert_id=alert_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get alert: {str(e)}")


@app.post("/v1/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, request: Request):
    """Acknowledge an alert"""
    try:
        if not alert_engine_instance:
            raise HTTPException(status_code=503, detail="Alert engine not initialized")

        acknowledged_by = request.headers.get("X-User-ID", "api-user")

        success = await alert_engine_instance.acknowledge_alert(alert_id, acknowledged_by)
        if not success:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found or cannot be acknowledged")

        logger.info("Alert acknowledged", alert_id=alert_id, acknowledged_by=acknowledged_by)
        return {"message": f"Alert {alert_id} acknowledged successfully", "acknowledged_by": acknowledged_by}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to acknowledge alert", alert_id=alert_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to acknowledge alert: {str(e)}")


@app.post("/v1/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, request: Request, resolution_data: Optional[Dict[str, Any]] = None):
    """Manually resolve an alert"""
    try:
        if not alert_engine_instance:
            raise HTTPException(status_code=503, detail="Alert engine not initialized")

        resolved_by = request.headers.get("X-User-ID", "api-user")
        reason = resolution_data.get("reason", "") if resolution_data else ""

        success = await alert_engine_instance.resolve_alert(alert_id, resolved_by, reason)
        if not success:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

        logger.info("Alert resolved", alert_id=alert_id, resolved_by=resolved_by)
        return {"message": f"Alert {alert_id} resolved successfully", "resolved_by": resolved_by}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to resolve alert", alert_id=alert_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to resolve alert: {str(e)}")


# Alert Engine Status and Health

@app.get("/v1/alerts/health")
async def alert_engine_health():
    """Get alert engine health status"""
    try:
        if not alert_engine_instance:
            return {"status": "inactive", "message": "Alert engine not initialized"}

        # Get basic health info
        health_info = {
            "status": "active" if alert_engine_instance.is_running else "inactive",
            "timestamp": datetime.utcnow(),
            "total_rules": len(alert_engine_instance.rules),
            "active_alerts": len([a for a in alert_engine_instance.active_alerts.values() if a.status == AlertStatus.ACTIVE]),
            "running_evaluations": len(alert_engine_instance.evaluation_tasks)
        }

        return health_info

    except Exception as e:
        logger.error("Failed to get alert engine health", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get alert engine health: {str(e)}")


@app.get("/v1/alerts/stats")
async def alert_engine_stats(request: Request, customer_id: Optional[str] = None):
    """Get alert engine statistics"""
    try:
        if not alert_engine_instance:
            raise HTTPException(status_code=503, detail="Alert engine not initialized")

        # Use customer ID from header if not provided
        filter_customer_id = customer_id or request.headers.get("X-Customer-ID")

        # Get rules and alerts for customer
        rules = await alert_engine_instance.list_rules(filter_customer_id)
        alerts = await alert_engine_instance.list_alerts(filter_customer_id)

        # Calculate statistics
        stats = {
            "customer_id": filter_customer_id,
            "timestamp": datetime.utcnow(),
            "rules": {
                "total": len(rules),
                "enabled": len([r for r in rules if r.enabled]),
                "disabled": len([r for r in rules if not r.enabled]),
                "by_severity": {
                    severity.value: len([r for r in rules if r.severity == severity])
                    for severity in AlertSeverity
                }
            },
            "alerts": {
                "total": len(alerts),
                "active": len([a for a in alerts if a.status == AlertStatus.ACTIVE]),
                "resolved": len([a for a in alerts if a.status == AlertStatus.RESOLVED]),
                "acknowledged": len([a for a in alerts if a.status == AlertStatus.ACKNOWLEDGED]),
                "by_severity": {
                    severity.value: len([a for a in alerts if a.severity == severity])
                    for severity in AlertSeverity
                }
            }
        }

        return stats

    except Exception as e:
        logger.error("Failed to get alert engine stats", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get alert engine stats: {str(e)}")

# Application lifecycle events
@app.on_event("startup")
async def startup_event():
    """Initialize TTL manager, query engine, dashboard engine, and alert engine on application startup"""
    global ttl_manager, ttl_scheduler, query_engine, dashboard_engine, alert_engine_instance

    try:
        client = get_clickhouse_client()

        # Initialize TTL management
        ttl_manager = TTLManager(client, storage_manager)
        ttl_scheduler = TTLScheduler(ttl_manager)

        # Initialize advanced query engine
        query_engine = AdvancedQueryEngine(client)

        # Initialize enterprise dashboard engine
        dashboard_engine = DashboardEngine(query_engine)

        # Initialize M3 alert engine
        alert_engine_instance = AlertEngine()
        await alert_engine_instance.start()

        # Start TTL scheduler in background
        asyncio.create_task(ttl_scheduler.start())

        logger.info("All services initialized: TTL management, query engine, dashboard engine, and alert engine")

    except Exception as e:
        logger.error("Failed to initialize services", error=str(e))

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown of TTL manager and alert engine"""
    global ttl_scheduler, alert_engine_instance

    if ttl_scheduler:
        await ttl_scheduler.stop()
        logger.info("TTL management system stopped")

    if alert_engine_instance:
        await alert_engine_instance.stop()
        logger.info("Alert engine stopped")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Logforge API - Advanced SIEM Platform",
        "version": "0.1.0",
        "docs": "/docs",
        "features": [
            "Multi-format log ingestion (JSON, Syslog, Nginx, CEF, OTLP, Text)",
            "Intelligent data tiering (Hot/Cold storage)",
            "Multi-cloud storage support (S3, GCS, Azure, MinIO)",
            "Advanced TTL policies with compliance support",
            "Real-time security analytics",
            "Cost-effective alternative to enterprise SIEM solutions"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
