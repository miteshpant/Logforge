from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any, List
import clickhouse_connect
import structlog
import yaml
import os
from pathlib import Path

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

# Pydantic models
class LogEntry(BaseModel):
    ts: datetime = Field(default_factory=datetime.utcnow)
    host: Optional[str] = ""
    service: str = Field(..., description="Service name")
    level: str = Field(default="info", description="Log level")
    msg: str = Field(..., description="Log message")
    trace_id: Optional[str] = ""
    attrs: Optional[Dict[str, Any]] = Field(default_factory=dict)
    status: Optional[int] = 0
    src_ip: Optional[str] = ""
    user_id: Optional[str] = ""

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    services: Dict[str, str]

class IngestResponse(BaseModel):
    status: str
    message: str
    log_id: Optional[str] = None

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

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Logforge API", 
        "version": "0.1.0",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)