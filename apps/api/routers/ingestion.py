"""
Log ingestion API endpoints - all formats and methods
"""

import json
import time
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Body, Request, HTTPException
from fastapi.responses import JSONResponse

from models import (
    LogEntry, BatchLogEntry, OTLPLogsData,
    IngestResponse, BatchIngestResponse
)
from error_handling import internal_error
from parsers import ParserFactory
from storage_config import get_customer_id
from tenant_dependencies import TenantOrDefault, RequiredTenant, MiddlewareTenant
from fastapi import Depends
# ENH-033/ENH-010: resolved lazily; importing the singleton connected to
# the database at import time and made this module untestable offline.
from tenant_service import get_tenant_service
from services.ingestion_service import IngestionService

router = APIRouter(prefix="/v1/ingest")

# Global instances (will be injected)
parser_factory = None
process_logs_background = None
process_logs_and_tracking_background = None
# ENH-010: `IngestionService()` opens a database connection in its constructor, so
# building it at import time made this router un-importable -- and untestable --
# without live infrastructure. Built on first use; the PEP 562 hook below
# preserves the bare `ingestion_service` name at every call site.
_ingestion_service_instance: Optional[IngestionService] = None


def get_ingestion_service() -> IngestionService:
    """Get the shared IngestionService, constructing it on first use."""
    global _ingestion_service_instance
    if _ingestion_service_instance is None:
        _ingestion_service_instance = IngestionService()
    return _ingestion_service_instance


def __getattr__(name: str):
    """Resolve `ingestion_service` lazily (PEP 562)."""
    if name == "ingestion_service":
        return get_ingestion_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
logger = logging.getLogger(__name__)

def check_ingest_capacity() -> None:
    """
    Reject the request if the ingest pipeline is saturated (ENH-029).

    Ingest endpoints return 202 and hand off to a background worker pool. If the
    pool is full, that 202 is a lie: the batch will be dropped and the customer
    will believe their logs were accepted. Shedding load with an honest 429 lets
    the shipper retry, which is how Vector/Fluent Bit/OTel collectors are all
    designed to behave.

    Raises:
        HTTPException(429): with `Retry-After`, when saturated.
    """
    from ingest_pipeline import get_ingest_pipeline

    pipeline = get_ingest_pipeline()
    if pipeline.is_saturated():
        retry_after = pipeline.retry_after_seconds()
        # NOTE: `logger` here is stdlib logging, not structlog, so keyword
        # fields must be formatted into the message rather than passed as kwargs.
        logger.warning(
            "Ingest rejected: pipeline saturated (queue_depth=%s)",
            pipeline.get_stats()["queue_depth"],
        )
        raise HTTPException(
            status_code=429,
            detail=(
                "Ingest pipeline is saturated. Retry after "
                f"{retry_after}s."
            ),
            headers={"Retry-After": str(retry_after)},
        )


def setup_dependencies(pf, plb, pltb=None):
    """Setup dependencies from main app"""
    global parser_factory, process_logs_background, process_logs_and_tracking_background
    parser_factory = pf
    process_logs_background = plb
    process_logs_and_tracking_background = pltb

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🔧 INGESTION DEPENDENCIES SETUP: pf={pf is not None}, plb={plb is not None}, pltb={pltb is not None}")
    logger.info(f"🔧 process_logs_and_tracking_background = {process_logs_and_tracking_background}")

    if process_logs_and_tracking_background:
        logger.info("✅ NEW TRACKING FUNCTION AVAILABLE")
    else:
        logger.warning("⚠️ NEW TRACKING FUNCTION IS NONE - USING FALLBACK")

@router.post("/logs", response_model=IngestResponse)
async def ingest_logs(
    log_entry: LogEntry,
    background_tasks: BackgroundTasks,
    customer_id: str = MiddlewareTenant
):
    """Single log entry ingestion endpoint"""
    # ENH-029: shed load honestly rather than accepting data we cannot persist.
    check_ingest_capacity()

    start_time = time.time()

    try:
        # Validate log entry (only validation in main thread)
        if not get_ingestion_service().validate_log_entry(log_entry):
            # Error tracking also moved to background to avoid blocking
            background_tasks.add_task(
                get_ingestion_service().track_ingestion_error,
                customer_id, "/logs", "validation_error", "Log entry validation failed"
            )
            raise HTTPException(status_code=400, detail="Invalid log entry")

        # Prepare logs for storage
        logs = get_ingestion_service().prepare_logs_for_storage([log_entry], customer_id)

        # Calculate metrics for background tracking
        bytes_processed = len(str(log_entry.msg))
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Move ALL tracking to background tasks for fast response
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🚀 INGESTION ENDPOINT: customer_id={customer_id}, bytes={bytes_processed}, processing_time={processing_time_ms}ms")

        if process_logs_and_tracking_background:
            logger.info("✅ USING NEW TRACKING FUNCTION")
            background_tasks.add_task(
                process_logs_and_tracking_background,
                logs,
                customer_id,
                "/logs",
                "json",
                1,  # log_count
                bytes_processed,
                processing_time_ms
            )
        else:
            logger.warning("⚠️ USING FALLBACK METHOD")
            background_tasks.add_task(process_logs_background, logs, customer_id)

        # Generate a simple log_id for compatibility
        log_id = f"log-{int(datetime.now().timestamp())}-{hash(str(log_entry)) % 10000}"

        return IngestResponse(
            status="accepted",
            message="Successfully accepted 1 log for processing",
            log_id=log_id,
            processed_count=1
        )

    except HTTPException:
        raise
    except Exception as e:
        # Error tracking moved to background
        background_tasks.add_task(
            get_ingestion_service().track_ingestion_error,
            customer_id, "/logs", "processing_error", str(e)
        )
        raise internal_error(e, "Ingestion failed", customer_id=customer_id, endpoint="/logs")

MAX_BATCH_LOGS = 1000


@router.post("/logs/batch", response_model=BatchIngestResponse)
async def ingest_logs_batch(
    background_tasks: BackgroundTasks,
    batch: Union[BatchLogEntry, List[LogEntry]] = Body(
        ...,
        description='Either {"logs": [...]} or a bare JSON array of log entries '
                    '(what Vector, Fluent Bit and Fluentd send). At most 1000 per request.',
    ),
    customer_id: str = MiddlewareTenant
):
    """Batch log entry ingestion"""
    # ENH-029: shed load honestly rather than accepting data we cannot persist.
    check_ingest_capacity()

    if isinstance(batch, list):
        # Same limit as BatchLogEntry.
        if len(batch) > MAX_BATCH_LOGS:
            raise HTTPException(status_code=413, detail=f"Batch size cannot exceed {MAX_BATCH_LOGS} logs")
        batch = BatchLogEntry.model_construct(logs=batch)

    start_time = time.time()

    try:
        # Add metadata to all logs (minimal processing in main thread)
        ingested_at = datetime.now(timezone.utc)
        for log in batch.logs:
            log.ingested_at = ingested_at
            log.customer_id = customer_id

        # Calculate metrics for background tracking
        total_bytes_processed = sum(len(str(log.msg)) for log in batch.logs)
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Move ALL tracking to background tasks for fast response
        if process_logs_and_tracking_background:
            background_tasks.add_task(
                process_logs_and_tracking_background,
                batch.logs,
                customer_id,
                "/logs/batch",
                "json",
                len(batch.logs),  # log_count
                total_bytes_processed,
                processing_time_ms
            )
        else:
            # Fallback to old method if new function not available
            background_tasks.add_task(process_logs_background, batch.logs, customer_id)

        return BatchIngestResponse(
            status="accepted",
            message=f"Successfully accepted {len(batch.logs)} logs for processing",
            processed_count=len(batch.logs),
            error_count=0
        )
    except HTTPException:
        raise
    except Exception as e:
        # Error tracking moved to background
        background_tasks.add_task(
            get_ingestion_service().track_ingestion_error,
            customer_id, "/logs/batch", "processing_error", str(e)
        )
        raise internal_error(e, "Batch ingestion failed", customer_id=customer_id, endpoint="/logs/batch")

@router.post("/logs/bulk", response_model=BatchIngestResponse)
async def ingest_logs_bulk(
    bulk_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    customer_id: str = MiddlewareTenant
):
    """Bulk ingestion from various sources"""
    # ENH-029: shed load honestly rather than accepting data we cannot persist.
    check_ingest_capacity()

    try:

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
    except HTTPException:
        raise
    except ValueError as e:
        # A malformed entry (pydantic ValidationError is a ValueError) is the
        # caller's error: 400 with what was wrong, not a 500.
        raise HTTPException(status_code=400, detail=f"Invalid log entry: {e}")
    except Exception as e:
        raise internal_error(e, "Bulk ingestion failed", customer_id=customer_id, endpoint="/logs/bulk")

@router.post("/otlp", response_model=BatchIngestResponse)
async def ingest_otlp_logs(
    otlp_data: OTLPLogsData,
    background_tasks: BackgroundTasks,
    customer_id: str = MiddlewareTenant
):
    """OpenTelemetry Protocol (OTLP) log ingestion"""
    # ENH-029: shed load honestly rather than accepting data we cannot persist.
    check_ingest_capacity()

    start_time = time.time()

    try:
        if not parser_factory:
            raise HTTPException(status_code=500, detail="Parser factory not initialized")

        parser = parser_factory.get_parser("otlp")
        logs = parser.parse_batch(otlp_data)

        if not logs:
            raise HTTPException(status_code=400, detail="No valid log records found in OTLP data")

        # Prepare logs for storage
        logs = get_ingestion_service().prepare_logs_for_storage(logs, customer_id)

        # Calculate metrics for background tracking
        total_bytes_processed = sum(len(str(log.msg)) for log in logs)
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Move ALL tracking to background tasks for fast response
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🚀 OTLP INGESTION: customer_id={customer_id}, log_count={len(logs)}, bytes={total_bytes_processed}, processing_time={processing_time_ms}ms")

        if process_logs_and_tracking_background:
            logger.info("✅ USING OTLP NON-BLOCKING TRACKING")
            background_tasks.add_task(
                process_logs_and_tracking_background,
                logs,
                customer_id,
                "/otlp",
                "otlp",
                len(logs),  # log_count
                total_bytes_processed,
                processing_time_ms
            )
        else:
            logger.warning("⚠️ OTLP USING FALLBACK METHOD")
            background_tasks.add_task(process_logs_background, logs, customer_id)

        return BatchIngestResponse(
            status="accepted",
            message=f"Successfully accepted {len(logs)} OTLP logs for processing",
            processed_count=len(logs),
            error_count=0
        )
    except HTTPException:
        raise
    except Exception as e:
        # Error tracking moved to background
        background_tasks.add_task(
            get_ingestion_service().track_ingestion_error,
            customer_id, "/otlp", "processing_error", str(e), str(otlp_data)[:500], "application/json"
        )
        raise internal_error(e, "OTLP ingestion failed", customer_id=customer_id, endpoint="/otlp")

@router.post("/syslog", response_model=IngestResponse)
async def ingest_syslog(
    request: Request,
    background_tasks: BackgroundTasks,
    customer_id: str = MiddlewareTenant
):
    """Syslog format ingestion (RFC 3164 and RFC 5424)"""
    # ENH-029: shed load honestly rather than accepting data we cannot persist.
    check_ingest_capacity()

    start_time = time.time()

    try:
        raw_content = await request.body()
        syslog_data = raw_content.decode('utf-8').strip()

        if not parser_factory:
            raise HTTPException(status_code=500, detail="Parser factory not initialized")

        parser = parser_factory.get_parser("syslog")
        log = parser.parse(syslog_data)

        if not log:
            raise HTTPException(status_code=400, detail="No valid log records found in syslog data")

        # Prepare logs for storage
        logs = get_ingestion_service().prepare_logs_for_storage([log], customer_id)

        # Calculate metrics for background tracking
        total_bytes_processed = len(syslog_data.encode('utf-8'))
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Move ALL tracking to background tasks for fast response
        if process_logs_and_tracking_background:
            background_tasks.add_task(
                process_logs_and_tracking_background,
                logs,
                customer_id,
                "/syslog",
                "syslog",
                len(logs),  # log_count
                total_bytes_processed,
                processing_time_ms
            )
        else:
            # Fallback to old method if new function not available
            background_tasks.add_task(process_logs_background, logs, customer_id)

        return IngestResponse(
            status="success",
            message=f"Successfully ingested {len(logs)} logs",
            processed_count=len(logs)
        )
    except HTTPException:
        # ENH-029: preserve deliberate 4xx (e.g. the 429 from
        # check_ingest_capacity) instead of relabelling it.
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Syslog parsing failed: {str(e)}")

@router.post("/nginx", response_model=IngestResponse)
async def ingest_nginx(
    request: Request,
    background_tasks: BackgroundTasks,
    customer_id: str = MiddlewareTenant
):
    """Nginx access log ingestion"""
    # ENH-029: shed load honestly rather than accepting data we cannot persist.
    check_ingest_capacity()

    start_time = time.time()

    try:
        raw_content = await request.body()
        nginx_logs = raw_content.decode('utf-8').strip()

        if not parser_factory:
            raise HTTPException(status_code=500, detail="Parser factory not initialized")

        parser = parser_factory.get_parser("nginx")
        log = parser.parse(nginx_logs)

        if not log:
            raise HTTPException(status_code=400, detail="No valid log records found in nginx data")

        # Prepare logs for storage
        logs = get_ingestion_service().prepare_logs_for_storage([log], customer_id)

        # Calculate metrics for background tracking
        total_bytes_processed = len(nginx_logs.encode('utf-8'))
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Move ALL tracking to background tasks for fast response
        if process_logs_and_tracking_background:
            background_tasks.add_task(
                process_logs_and_tracking_background,
                logs,
                customer_id,
                "/nginx",
                "nginx",
                len(logs),  # log_count
                total_bytes_processed,
                processing_time_ms
            )
        else:
            # Fallback to old method if new function not available
            background_tasks.add_task(process_logs_background, logs, customer_id)

        return IngestResponse(
            status="success",
            message=f"Successfully ingested {len(logs)} logs",
            processed_count=len(logs)
        )
    except HTTPException:
        # ENH-029: preserve deliberate 4xx (e.g. the 429 from
        # check_ingest_capacity) instead of relabelling it.
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Nginx log parsing failed: {str(e)}")

@router.post("/cef", response_model=IngestResponse)
async def ingest_cef(
    request: Request,
    background_tasks: BackgroundTasks,
    customer_id: str = MiddlewareTenant
):
    """Common Event Format (CEF) log ingestion"""
    # ENH-029: shed load honestly rather than accepting data we cannot persist.
    check_ingest_capacity()

    start_time = time.time()

    try:
        raw_content = await request.body()
        cef_data = raw_content.decode('utf-8').strip()

        if not parser_factory:
            raise HTTPException(status_code=500, detail="Parser factory not initialized")

        parser = parser_factory.get_parser("cef")
        log = parser.parse(cef_data)

        if not log:
            raise HTTPException(status_code=400, detail="No valid log records found in CEF data")

        # Prepare logs for storage
        logs = get_ingestion_service().prepare_logs_for_storage([log], customer_id)

        # Calculate metrics for background tracking
        total_bytes_processed = len(cef_data.encode('utf-8'))
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Move ALL tracking to background tasks for fast response
        if process_logs_and_tracking_background:
            background_tasks.add_task(
                process_logs_and_tracking_background,
                logs,
                customer_id,
                "/cef",
                "cef",
                len(logs),  # log_count
                total_bytes_processed,
                processing_time_ms
            )
        else:
            # Fallback to old method if new function not available
            background_tasks.add_task(process_logs_background, logs, customer_id)

        return IngestResponse(
            status="success",
            message=f"Successfully ingested {len(logs)} logs",
            processed_count=len(logs)
        )
    except HTTPException:
        # ENH-029: preserve deliberate 4xx (e.g. the 429 from
        # check_ingest_capacity) instead of relabelling it.
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CEF parsing failed: {str(e)}")

@router.post("/text", response_model=IngestResponse)
async def ingest_text(
    request: Request,
    background_tasks: BackgroundTasks,
    customer_id: str = MiddlewareTenant
):
    """Plain text log ingestion with basic parsing"""
    # ENH-029: shed load honestly rather than accepting data we cannot persist.
    check_ingest_capacity()

    start_time = time.time()

    try:
        raw_content = await request.body()
        text_data = raw_content.decode('utf-8').strip()

        if not parser_factory:
            raise HTTPException(status_code=500, detail="Parser factory not initialized")

        parser = parser_factory.get_parser("text")
        log = parser.parse(text_data)

        if not log:
            raise HTTPException(status_code=400, detail="No valid log records found in text data")

        # Prepare logs for storage
        logs = get_ingestion_service().prepare_logs_for_storage([log], customer_id)

        # Calculate metrics for background tracking
        total_bytes_processed = len(text_data.encode('utf-8'))
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Move ALL tracking to background tasks for fast response
        if process_logs_and_tracking_background:
            background_tasks.add_task(
                process_logs_and_tracking_background,
                logs,
                customer_id,
                "/text",
                "text",
                len(logs),  # log_count
                total_bytes_processed,
                processing_time_ms
            )
        else:
            # Fallback to old method if new function not available
            background_tasks.add_task(process_logs_background, logs, customer_id)

        return IngestResponse(
            status="success",
            message=f"Successfully ingested {len(logs)} logs",
            processed_count=len(logs)
        )
    except HTTPException:
        # ENH-029: preserve deliberate 4xx (e.g. the 429 from
        # check_ingest_capacity) instead of relabelling it.
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Text parsing failed: {str(e)}")

@router.post("/structured", response_model=IngestResponse)
async def ingest_structured(
    structured_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    customer_id: str = MiddlewareTenant
):
    """Structured JSON log ingestion"""
    # ENH-029: shed load honestly rather than accepting data we cannot persist.
    check_ingest_capacity()

    start_time = time.time()

    try:
        logs = []

        if isinstance(structured_data, list):
            for item in structured_data:
                log = LogEntry(**item) if isinstance(item, dict) else LogEntry.from_json(str(item))
                logs.append(log)
        else:
            log = LogEntry(**structured_data)
            logs.append(log)

        if not logs:
            raise HTTPException(status_code=400, detail="No valid log records found in structured data")

        # Prepare logs for storage
        logs = get_ingestion_service().prepare_logs_for_storage(logs, customer_id)

        # Calculate metrics for background tracking
        total_bytes_processed = len(str(structured_data).encode('utf-8'))
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Move ALL tracking to background tasks for fast response
        if process_logs_and_tracking_background:
            background_tasks.add_task(
                process_logs_and_tracking_background,
                logs,
                customer_id,
                "/structured",
                "json",
                len(logs),  # log_count
                total_bytes_processed,
                processing_time_ms
            )
        else:
            # Fallback to old method if new function not available
            background_tasks.add_task(process_logs_background, logs, customer_id)

        return IngestResponse(
            status="success",
            message=f"Successfully ingested {len(logs)} logs",
            processed_count=len(logs)
        )
    except HTTPException:
        # ENH-029: preserve deliberate 4xx (e.g. the 429 from
        # check_ingest_capacity) instead of relabelling it.
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Structured data parsing failed: {str(e)}")

# Batch processing endpoints
@router.post("/nginx/batch", response_model=IngestResponse)
async def ingest_nginx_batch(
    request: Request,
    background_tasks: BackgroundTasks,
    customer_id: str = MiddlewareTenant
):
    """Nginx access logs batch ingestion (newline-separated)"""
    # ENH-029: shed load honestly rather than accepting data we cannot persist.
    check_ingest_capacity()

    start_time = time.time()

    try:
        raw_content = await request.body()
        nginx_logs_text = raw_content.decode('utf-8').strip()

        if not parser_factory:
            raise HTTPException(status_code=500, detail="Parser factory not initialized")

        # Split by newlines and parse each log
        nginx_log_lines = [line.strip() for line in nginx_logs_text.split('\n') if line.strip()]
        
        if not nginx_log_lines:
            raise HTTPException(status_code=400, detail="No valid nginx log lines found")

        parser = parser_factory.get_parser("nginx")
        logs = []

        for i, line in enumerate(nginx_log_lines):
            try:
                log = parser.parse(line)
                logs.append(log)
            except HTTPException:
                # ENH-029: preserve deliberate 4xx (e.g. the 429 from
                # check_ingest_capacity) instead of relabelling it.
                raise
            except Exception as e:
                logger.warning(f"Failed to parse nginx log line {i+1}: {e}")
                continue

        if not logs:
            raise HTTPException(status_code=400, detail="No valid nginx log records could be parsed")

        # Prepare logs for storage
        logs = get_ingestion_service().prepare_logs_for_storage(logs, customer_id)

        # Calculate metrics for background tracking
        total_bytes_processed = len(nginx_logs_text.encode('utf-8'))
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Move ALL tracking to background tasks for fast response
        if process_logs_and_tracking_background:
            background_tasks.add_task(
                process_logs_and_tracking_background,
                logs,
                customer_id,
                "/nginx/batch",
                "nginx",
                len(logs),
                total_bytes_processed,
                processing_time_ms
            )
        else:
            background_tasks.add_task(process_logs_background, logs, customer_id)

        return IngestResponse(
            status="success",
            message=f"Successfully ingested {len(logs)} nginx logs from {len(nginx_log_lines)} lines",
            processed_count=len(logs)
        )
    except HTTPException:
        # ENH-029: preserve deliberate 4xx (e.g. the 429 from
        # check_ingest_capacity) instead of relabelling it.
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Nginx batch parsing failed: {str(e)}")

@router.post("/syslog/batch", response_model=IngestResponse)
async def ingest_syslog_batch(
    request: Request,
    background_tasks: BackgroundTasks,
    customer_id: str = MiddlewareTenant
):
    """Syslog messages batch ingestion (newline-separated)"""
    # ENH-029: shed load honestly rather than accepting data we cannot persist.
    check_ingest_capacity()

    start_time = time.time()

    try:
        raw_content = await request.body()
        syslog_text = raw_content.decode('utf-8').strip()

        if not parser_factory:
            raise HTTPException(status_code=500, detail="Parser factory not initialized")

        # Split by newlines and parse each log
        syslog_lines = [line.strip() for line in syslog_text.split('\n') if line.strip()]
        
        if not syslog_lines:
            raise HTTPException(status_code=400, detail="No valid syslog lines found")

        parser = parser_factory.get_parser("syslog")
        logs = []

        for i, line in enumerate(syslog_lines):
            try:
                log = parser.parse(line)
                logs.append(log)
            except HTTPException:
                # ENH-029: preserve deliberate 4xx (e.g. the 429 from
                # check_ingest_capacity) instead of relabelling it.
                raise
            except Exception as e:
                logger.warning(f"Failed to parse syslog line {i+1}: {e}")
                continue

        if not logs:
            raise HTTPException(status_code=400, detail="No valid syslog records could be parsed")

        # Prepare logs for storage
        logs = get_ingestion_service().prepare_logs_for_storage(logs, customer_id)

        # Calculate metrics for background tracking
        total_bytes_processed = len(syslog_text.encode('utf-8'))
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Move ALL tracking to background tasks for fast response
        if process_logs_and_tracking_background:
            background_tasks.add_task(
                process_logs_and_tracking_background,
                logs,
                customer_id,
                "/syslog/batch",
                "syslog",
                len(logs),
                total_bytes_processed,
                processing_time_ms
            )
        else:
            background_tasks.add_task(process_logs_background, logs, customer_id)

        return IngestResponse(
            status="success",
            message=f"Successfully ingested {len(logs)} syslog entries from {len(syslog_lines)} lines",
            processed_count=len(logs)
        )
    except HTTPException:
        # ENH-029: preserve deliberate 4xx (e.g. the 429 from
        # check_ingest_capacity) instead of relabelling it.
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Syslog batch parsing failed: {str(e)}")

@router.post("/cef/batch", response_model=IngestResponse)
async def ingest_cef_batch(
    request: Request,
    background_tasks: BackgroundTasks,
    customer_id: str = MiddlewareTenant
):
    """CEF events batch ingestion (newline-separated)"""
    # ENH-029: shed load honestly rather than accepting data we cannot persist.
    check_ingest_capacity()

    start_time = time.time()

    try:
        raw_content = await request.body()
        cef_text = raw_content.decode('utf-8').strip()

        if not parser_factory:
            raise HTTPException(status_code=500, detail="Parser factory not initialized")

        # Split by newlines and parse each log
        cef_lines = [line.strip() for line in cef_text.split('\n') if line.strip()]
        
        if not cef_lines:
            raise HTTPException(status_code=400, detail="No valid CEF lines found")

        parser = parser_factory.get_parser("cef")
        logs = []

        for i, line in enumerate(cef_lines):
            try:
                log = parser.parse(line)
                logs.append(log)
            except HTTPException:
                # ENH-029: preserve deliberate 4xx (e.g. the 429 from
                # check_ingest_capacity) instead of relabelling it.
                raise
            except Exception as e:
                logger.warning(f"Failed to parse CEF line {i+1}: {e}")
                continue

        if not logs:
            raise HTTPException(status_code=400, detail="No valid CEF records could be parsed")

        # Prepare logs for storage
        logs = get_ingestion_service().prepare_logs_for_storage(logs, customer_id)

        # Calculate metrics for background tracking
        total_bytes_processed = len(cef_text.encode('utf-8'))
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Move ALL tracking to background tasks for fast response
        if process_logs_and_tracking_background:
            background_tasks.add_task(
                process_logs_and_tracking_background,
                logs,
                customer_id,
                "/cef/batch",
                "cef",
                len(logs),
                total_bytes_processed,
                processing_time_ms
            )
        else:
            background_tasks.add_task(process_logs_background, logs, customer_id)

        return IngestResponse(
            status="success",
            message=f"Successfully ingested {len(logs)} CEF events from {len(cef_lines)} lines",
            processed_count=len(logs)
        )
    except HTTPException:
        # ENH-029: preserve deliberate 4xx (e.g. the 429 from
        # check_ingest_capacity) instead of relabelling it.
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CEF batch parsing failed: {str(e)}")

@router.post("/text/batch", response_model=IngestResponse)
async def ingest_text_batch(
    request: Request,
    background_tasks: BackgroundTasks,
    customer_id: str = MiddlewareTenant
):
    """Plain text logs batch ingestion with IP/user extraction (newline-separated)"""
    # ENH-029: shed load honestly rather than accepting data we cannot persist.
    check_ingest_capacity()

    start_time = time.time()

    try:
        raw_content = await request.body()
        text_logs = raw_content.decode('utf-8').strip()

        if not parser_factory:
            raise HTTPException(status_code=500, detail="Parser factory not initialized")

        # Split by newlines and parse each log
        text_lines = [line.strip() for line in text_logs.split('\n') if line.strip()]
        
        if not text_lines:
            raise HTTPException(status_code=400, detail="No valid text log lines found")

        parser = parser_factory.get_parser("text")
        logs = []

        for i, line in enumerate(text_lines):
            try:
                log = parser.parse(line)
                logs.append(log)
            except HTTPException:
                # ENH-029: preserve deliberate 4xx (e.g. the 429 from
                # check_ingest_capacity) instead of relabelling it.
                raise
            except Exception as e:
                logger.warning(f"Failed to parse text log line {i+1}: {e}")
                continue

        if not logs:
            raise HTTPException(status_code=400, detail="No valid text log records could be parsed")

        # Prepare logs for storage
        logs = get_ingestion_service().prepare_logs_for_storage(logs, customer_id)

        # Calculate metrics for background tracking
        total_bytes_processed = len(text_logs.encode('utf-8'))
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Move ALL tracking to background tasks for fast response
        if process_logs_and_tracking_background:
            background_tasks.add_task(
                process_logs_and_tracking_background,
                logs,
                customer_id,
                "/text/batch",
                "text",
                len(logs),
                total_bytes_processed,
                processing_time_ms
            )
        else:
            background_tasks.add_task(process_logs_background, logs, customer_id)

        return IngestResponse(
            status="success",
            message=f"Successfully ingested {len(logs)} text logs from {len(text_lines)} lines",
            processed_count=len(logs)
        )
    except HTTPException:
        # ENH-029: preserve deliberate 4xx (e.g. the 429 from
        # check_ingest_capacity) instead of relabelling it.
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Text batch parsing failed: {str(e)}")

# Generic format-aware endpoint
@router.post("", response_model=IngestResponse)
async def ingest_auto_detect(
    request: Request,
    background_tasks: BackgroundTasks,
    customer_id: str = MiddlewareTenant
):
    """Auto-detect format and ingest logs"""
    # ENH-029: shed load honestly rather than accepting data we cannot persist.
    check_ingest_capacity()

    start_time = time.time()

    try:
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
                    logs = parser.parse_batch(json_data)
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

        if not logs:
            raise HTTPException(status_code=400, detail="No valid log records found in auto-detected data")

        # Prepare logs for storage
        logs = get_ingestion_service().prepare_logs_for_storage(logs, customer_id)

        # Calculate metrics for background tracking
        total_bytes_processed = len(raw_content)
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Move ALL tracking to background tasks for fast response
        if process_logs_and_tracking_background:
            background_tasks.add_task(
                process_logs_and_tracking_background,
                logs,
                customer_id,
                "/ingest",
                detected_format,
                len(logs),  # log_count
                total_bytes_processed,
                processing_time_ms
            )
        else:
            # Fallback to old method if new function not available
            background_tasks.add_task(process_logs_background, logs, customer_id)

        return IngestResponse(
            status="success",
            message=f"Successfully ingested {len(logs)} logs - detected format: {detected_format}",
            processed_count=len(logs)
        )

    except HTTPException:
        # ENH-029: preserve deliberate 4xx (e.g. the 429 from
        # check_ingest_capacity) instead of relabelling it.
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Auto-detection failed: {str(e)}")
