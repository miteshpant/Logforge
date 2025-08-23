from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
import clickhouse_connect
import structlog
import yaml
import os
import json
import asyncio
import re
from pathlib import Path

from models import (
    LogEntry, BatchLogEntry, SyslogEntry, CEFEntry, NginxAccessEntry,
    StructuredLogEntry, TextLogEntry, OTLPLogsData, IngestResponse,
    BatchIngestResponse, HealthResponse, QueryResponse, IngestFormat
)
from parsers import ParserFactory, ParseError
from storage_config import StorageConfigManager
from ttl_manager import TTLManager, TTLScheduler

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
    allow_origins=["http://localhost:3000"],
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

# Background task for async log processing
async def process_log_batch(logs: List[LogEntry], client):
    """Process log batch in background"""
    try:
        data_rows = []
        for log_entry in logs:
            attrs_json = json.dumps(log_entry.attrs or {})
            data_row = [
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
            data_rows.append(data_row)
        
        # Insert into enhanced logs_raw table
        client.insert(
            "logs_raw",
            data_rows,
            column_names=[
                'ts', 'host', 'service', 'level', 'msg', 'trace_id', 'span_id',
                'attrs', 'status', 'src_ip', 'user_id', 'severity_num', 'facility', 'parser_version'
            ]
        )
        
        logger.info("Batch inserted", count=len(logs))
        
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
async def ingest_logs_batch(batch: BatchLogEntry, background_tasks: BackgroundTasks):
    """Ingest batch of log entries"""
    try:
        client = get_clickhouse_client()
        
        # Process batch in background for better performance
        background_tasks.add_task(process_log_batch, batch.logs, client)
        
        return BatchIngestResponse(
            status="accepted",
            message=f"Batch of {len(batch.logs)} logs accepted for processing",
            processed_count=len(batch.logs)
        )
        
    except Exception as e:
        logger.error("Failed to accept batch", error=str(e), batch_size=len(batch.logs))
        raise HTTPException(status_code=500, detail=f"Failed to accept batch: {str(e)}")

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
        background_tasks.add_task(process_log_batch, log_entries, client)
        
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
        await process_log_batch([log_entry], client)
        
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
        await process_log_batch([log_entry], client)
        
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
        await process_log_batch([log_entry], client)
        
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
        await process_log_batch([log_entry], client)
        
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
        await process_log_batch([log_entry], client)
        
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
        await process_log_batch([log_entry], client)
        
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

# Application lifecycle events
@app.on_event("startup")
async def startup_event():
    """Initialize TTL manager on application startup"""
    global ttl_manager, ttl_scheduler
    
    try:
        client = get_clickhouse_client()
        ttl_manager = TTLManager(client, storage_manager)
        ttl_scheduler = TTLScheduler(ttl_manager)
        
        # Start TTL scheduler in background
        asyncio.create_task(ttl_scheduler.start())
        
        logger.info("TTL management system initialized")
        
    except Exception as e:
        logger.error("Failed to initialize TTL management", error=str(e))

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown of TTL manager"""
    global ttl_scheduler
    
    if ttl_scheduler:
        await ttl_scheduler.stop()
        logger.info("TTL management system stopped")

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