"""
Log ingestion API endpoints - all formats and methods
"""

import json
from typing import Dict, Any, List
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from fastapi.responses import JSONResponse

from models import (
    LogEntry, BatchLogEntry, OTLPLogsData, 
    IngestResponse, BatchIngestResponse
)
from parsers import ParserFactory
from storage_config import get_customer_id

router = APIRouter(prefix="/v1/ingest")

# Global instances (will be injected)
parser_factory = None
process_logs_background = None

def setup_dependencies(pf, plb):
    """Setup dependencies from main app"""
    global parser_factory, process_logs_background
    parser_factory = pf
    process_logs_background = plb

@router.post("/logs", response_model=IngestResponse)
async def ingest_logs(log_entry: LogEntry, background_tasks: BackgroundTasks, request: Request):
    """Single log entry ingestion endpoint"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        # Add metadata
        log_entry.ingested_at = datetime.now(timezone.utc)
        log_entry.customer_id = customer_id
        
        # Background processing
        background_tasks.add_task(process_logs_background, [log_entry], customer_id)
        
        # Generate a simple log_id for M0 compatibility
        log_id = f"log-{int(datetime.now().timestamp())}-{hash(str(log_entry)) % 10000}"
        
        return IngestResponse(
            status="success",
            message="Successfully ingested 1 log",
            log_id=log_id,
            processed_count=1
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@router.post("/logs/batch", response_model=BatchIngestResponse)
async def ingest_logs_batch(batch: BatchLogEntry, background_tasks: BackgroundTasks, request: Request):
    """Batch log entry ingestion"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        ingested_at = datetime.now(timezone.utc)
        
        # Add metadata to all logs
        for log in batch.logs:
            log.ingested_at = ingested_at
            log.customer_id = customer_id
        
        background_tasks.add_task(process_logs_background, batch.logs, customer_id)
        
        return BatchIngestResponse(
            status="accepted",
            message=f"Successfully ingested {len(batch.logs)} logs",
            processed_count=len(batch.logs),
            error_count=0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch ingestion failed: {str(e)}")

@router.post("/logs/bulk", response_model=BatchIngestResponse)  
async def ingest_logs_bulk(bulk_data: Dict[str, Any], background_tasks: BackgroundTasks, request: Request):
    """Bulk ingestion from various sources"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        if "logs" not in bulk_data:
            raise HTTPException(status_code=400, detail="Missing 'logs' field in request")
        
        logs = []
        ingested_at = datetime.now(timezone.utc)
        
        for log_data in bulk_data["logs"]:
            log = LogEntry(**log_data) if isinstance(log_data, dict) else LogEntry.from_json(log_data)
            log.ingested_at = ingested_at
            log.customer_id = customer_id
            logs.append(log)
        
        background_tasks.add_task(process_logs_background, logs, customer_id)
        
        return BatchIngestResponse(
            status="success",
            message=f"Successfully ingested {len(logs)} logs",
            processed_count=len(logs),
            error_count=0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk ingestion failed: {str(e)}")

@router.post("/otlp", response_model=BatchIngestResponse)
async def ingest_otlp_logs(otlp_data: OTLPLogsData, background_tasks: BackgroundTasks, request: Request):
    """OpenTelemetry Protocol (OTLP) log ingestion"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        if not parser_factory:
            raise HTTPException(status_code=500, detail="Parser factory not initialized")
        
        parser = parser_factory.get_parser("otlp")
        logs = parser.parse(otlp_data.model_dump())
        
        ingested_at = datetime.now(timezone.utc)
        for log in logs:
            log.ingested_at = ingested_at
            log.customer_id = customer_id
        
        background_tasks.add_task(process_logs_background, logs, customer_id)
        
        return BatchIngestResponse(
            status="success",
            message=f"Successfully ingested {len(logs)} logs",
            processed_count=len(logs),
            error_count=0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OTLP ingestion failed: {str(e)}")

@router.post("/syslog", response_model=IngestResponse)
async def ingest_syslog(request: Request, background_tasks: BackgroundTasks):
    """Syslog format ingestion (RFC 3164 and RFC 5424)"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        raw_content = await request.body()
        syslog_data = raw_content.decode('utf-8').strip()
        
        if not parser_factory:
            raise HTTPException(status_code=500, detail="Parser factory not initialized")
        
        parser = parser_factory.get_parser("syslog")
        log = parser.parse(syslog_data)
        
        ingested_at = datetime.now(timezone.utc)
        log.ingested_at = ingested_at
        log.customer_id = customer_id
        logs = [log]
        
        background_tasks.add_task(process_logs_background, logs, customer_id)
        
        return IngestResponse(
            status="success",
            message=f"Successfully ingested {len(logs)} logs",
            processed_count=len(logs)
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Syslog parsing failed: {str(e)}")

@router.post("/nginx", response_model=IngestResponse) 
async def ingest_nginx(request: Request, background_tasks: BackgroundTasks):
    """Nginx access log ingestion"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        raw_content = await request.body()
        nginx_logs = raw_content.decode('utf-8').strip()
        
        if not parser_factory:
            raise HTTPException(status_code=500, detail="Parser factory not initialized")
        
        parser = parser_factory.get_parser("nginx")
        log = parser.parse(nginx_logs)
        
        ingested_at = datetime.now(timezone.utc)
        log.ingested_at = ingested_at
        log.customer_id = customer_id
        logs = [log]
        
        background_tasks.add_task(process_logs_background, logs, customer_id)
        
        return IngestResponse(
            status="success",
            message=f"Successfully ingested {len(logs)} logs",
            processed_count=len(logs)
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Nginx log parsing failed: {str(e)}")

@router.post("/cef", response_model=IngestResponse)
async def ingest_cef(request: Request, background_tasks: BackgroundTasks):
    """Common Event Format (CEF) log ingestion"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        raw_content = await request.body()
        cef_data = raw_content.decode('utf-8').strip()
        
        if not parser_factory:
            raise HTTPException(status_code=500, detail="Parser factory not initialized")
        
        parser = parser_factory.get_parser("cef")
        log = parser.parse(cef_data)
        
        ingested_at = datetime.now(timezone.utc)
        log.ingested_at = ingested_at
        log.customer_id = customer_id
        logs = [log]
        
        background_tasks.add_task(process_logs_background, logs, customer_id)
        
        return IngestResponse(
            status="success",
            message=f"Successfully ingested {len(logs)} logs",
            processed_count=len(logs)
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CEF parsing failed: {str(e)}")

@router.post("/text", response_model=IngestResponse)
async def ingest_text(request: Request, background_tasks: BackgroundTasks):
    """Plain text log ingestion with basic parsing"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        raw_content = await request.body()
        text_data = raw_content.decode('utf-8').strip()
        
        if not parser_factory:
            raise HTTPException(status_code=500, detail="Parser factory not initialized")
        
        parser = parser_factory.get_parser("text")
        log = parser.parse(text_data)
        
        ingested_at = datetime.now(timezone.utc)
        log.ingested_at = ingested_at
        log.customer_id = customer_id
        logs = [log]
        
        background_tasks.add_task(process_logs_background, logs, customer_id)
        
        return IngestResponse(
            status="success",
            message=f"Successfully ingested {len(logs)} logs",
            processed_count=len(logs)
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Text parsing failed: {str(e)}")

@router.post("/structured", response_model=IngestResponse)
async def ingest_structured(structured_data: Dict[str, Any], background_tasks: BackgroundTasks, request: Request):
    """Structured JSON log ingestion"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        logs = []
        ingested_at = datetime.now(timezone.utc)
        
        if isinstance(structured_data, list):
            for item in structured_data:
                log = LogEntry(**item) if isinstance(item, dict) else LogEntry.from_json(str(item))
                log.ingested_at = ingested_at
                log.customer_id = customer_id
                logs.append(log)
        else:
            log = LogEntry(**structured_data)
            log.ingested_at = ingested_at
            log.customer_id = customer_id
            logs.append(log)
        
        background_tasks.add_task(process_logs_background, logs, customer_id)
        
        return IngestResponse(
            status="success",
            message=f"Successfully ingested {len(logs)} logs",
            processed_count=len(logs)
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Structured data parsing failed: {str(e)}")

# Generic format-aware endpoint
@router.post("", response_model=IngestResponse)
async def ingest_auto_detect(request: Request, background_tasks: BackgroundTasks):
    """Auto-detect format and ingest logs"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        content_type = request.headers.get("content-type", "")
        raw_content = await request.body()
        
        if not parser_factory:
            raise HTTPException(status_code=500, detail="Parser factory not initialized")
        
        # Auto-detect format based on content type and content
        if "application/json" in content_type:
            try:
                json_data = json.loads(raw_content.decode('utf-8'))
                
                # Check if it's OTLP format
                if "resource_logs" in json_data:
                    parser = parser_factory.get_parser("otlp")
                    logs = parser.parse(json_data)
                    detected_format = "otlp"
                else:
                    # Regular JSON log
                    log = LogEntry(**json_data) if isinstance(json_data, dict) else LogEntry.from_json(str(json_data))
                    logs = [log]
                    detected_format = "json"
                    
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON format")
                
        else:
            # Try to detect text-based formats
            text_content = raw_content.decode('utf-8').strip()
            
            if text_content.startswith('<') and 'CEF:' in text_content:
                parser = parser_factory.get_parser("cef")
                log = parser.parse(text_content)
                logs = [log]
                detected_format = "cef"
            elif text_content.startswith('<'):
                parser = parser_factory.get_parser("syslog")
                log = parser.parse(text_content)
                logs = [log]
                detected_format = "syslog"
            elif ' - ' in text_content and '[' in text_content:
                parser = parser_factory.get_parser("nginx")
                log = parser.parse(text_content)
                logs = [log]
                detected_format = "nginx"
            else:
                parser = parser_factory.get_parser("text")
                log = parser.parse(text_content)
                logs = [log]
                detected_format = "text"
        
        ingested_at = datetime.now(timezone.utc)
        for log in logs:
            log.ingested_at = ingested_at
            log.customer_id = customer_id
        
        background_tasks.add_task(process_logs_background, logs, customer_id)
        
        return IngestResponse(
            status="success",
            message=f"Successfully ingested {len(logs)} logs - detected format: {detected_format}",
            processed_count=len(logs)
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Auto-detection failed: {str(e)}")