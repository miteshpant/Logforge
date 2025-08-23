"""
Data models for Logforge API
Supports multiple log formats and ingestion protocols
"""

from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, Dict, Any, List, Union, Literal
from enum import Enum
import json
import re

class LogLevel(str, Enum):
    """Standard log levels"""
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"
    CRITICAL = "critical"

class SyslogSeverity(int, Enum):
    """Syslog severity levels (RFC 3164)"""
    EMERGENCY = 0
    ALERT = 1
    CRITICAL = 2
    ERROR = 3
    WARNING = 4
    NOTICE = 5
    INFO = 6
    DEBUG = 7

class SyslogFacility(int, Enum):
    """Syslog facility codes (RFC 3164)"""
    KERNEL = 0
    USER = 1
    MAIL = 2
    DAEMON = 3
    SECURITY = 4
    SYSLOGD = 5
    LPR = 6
    NEWS = 7
    UUCP = 8
    CRON = 9
    AUTHPRIV = 10
    FTP = 11
    NTP = 12
    LOGAUDIT = 13
    LOGALERT = 14
    CLOCK = 15
    LOCAL0 = 16
    LOCAL1 = 17
    LOCAL2 = 18
    LOCAL3 = 19
    LOCAL4 = 20
    LOCAL5 = 21
    LOCAL6 = 22
    LOCAL7 = 23

# Base models
class BaseLogEntry(BaseModel):
    """Base log entry with common fields"""
    ts: datetime = Field(default_factory=datetime.utcnow, description="Timestamp")
    host: Optional[str] = Field("", description="Hostname or IP")
    service: str = Field(..., description="Service name")
    level: str = Field("info", description="Log level")
    msg: str = Field(..., description="Log message")
    trace_id: Optional[str] = Field("", description="Distributed trace ID")
    span_id: Optional[str] = Field("", description="Span ID for tracing")
    attrs: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional attributes")
    status: Optional[int] = Field(0, description="HTTP status or error code")
    src_ip: Optional[str] = Field("", description="Source IP address")
    user_id: Optional[str] = Field("", description="User identifier")
    
    # Enhanced fields for M1
    severity_num: Optional[int] = Field(0, description="Numeric severity (0-7)")
    facility: Optional[int] = Field(16, description="Syslog facility code")
    parser_version: Optional[str] = Field("v1", description="Parser version used")

    @validator('level')
    def normalize_level(cls, v):
        """Normalize log level to standard values"""
        if not v:
            return "info"
        level_map = {
            'trace': 'trace', 'debug': 'debug', 'info': 'info',
            'warn': 'warn', 'warning': 'warn', 'error': 'error',
            'fatal': 'fatal', 'critical': 'fatal', 'crit': 'fatal'
        }
        return level_map.get(v.lower(), v.lower())

    @validator('ts', pre=True)
    def parse_timestamp(cls, v):
        """Parse various timestamp formats"""
        if isinstance(v, str):
            # Handle common timestamp formats
            formats = [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ", 
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%d/%b/%Y:%H:%M:%S %z",  # Nginx format
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
            # If none match, try parsing with dateutil
            try:
                from dateutil.parser import parse
                return parse(v)
            except:
                return datetime.utcnow()
        return v if isinstance(v, datetime) else datetime.utcnow()

class LogEntry(BaseLogEntry):
    """Standard JSON log entry"""
    pass

class BatchLogEntry(BaseModel):
    """Batch log ingestion"""
    logs: List[LogEntry] = Field(..., description="Array of log entries")
    
    @validator('logs')
    def validate_batch_size(cls, v):
        if len(v) > 1000:
            raise ValueError("Batch size cannot exceed 1000 logs")
        return v

# Syslog models
class SyslogEntry(BaseModel):
    """Syslog format entry (RFC 3164/5424)"""
    raw_message: str = Field(..., description="Raw syslog message")
    facility: Optional[int] = Field(16, description="Syslog facility")
    severity: Optional[int] = Field(6, description="Syslog severity") 
    timestamp: Optional[str] = Field(None, description="Syslog timestamp")
    hostname: Optional[str] = Field("", description="Hostname from syslog")
    program: Optional[str] = Field("", description="Program name")
    pid: Optional[int] = Field(None, description="Process ID")
    message: str = Field(..., description="Log message content")

# OTLP (OpenTelemetry) models
class OTLPAttribute(BaseModel):
    """OTLP attribute key-value pair"""
    key: str
    value: Union[str, int, float, bool]

class OTLPResource(BaseModel):
    """OTLP resource information"""
    attributes: List[OTLPAttribute] = Field(default_factory=list)

class OTLPLogRecord(BaseModel):
    """OTLP log record"""
    time_unix_nano: int = Field(..., description="Timestamp in nanoseconds")
    severity_number: Optional[int] = Field(0, description="Severity number")
    severity_text: Optional[str] = Field("", description="Severity text")
    body: str = Field(..., description="Log body/message")
    attributes: List[OTLPAttribute] = Field(default_factory=list)
    dropped_attributes_count: Optional[int] = 0
    flags: Optional[int] = 0
    trace_id: Optional[str] = Field("", description="Trace ID (hex)")
    span_id: Optional[str] = Field("", description="Span ID (hex)")

class OTLPScopeLogs(BaseModel):
    """OTLP scope logs"""
    scope: Optional[Dict[str, Any]] = Field(default_factory=dict)
    log_records: List[OTLPLogRecord] = Field(..., description="Log records")

class OTLPResourceLogs(BaseModel):
    """OTLP resource logs"""
    resource: Optional[OTLPResource] = Field(default_factory=OTLPResource)
    scope_logs: List[OTLPScopeLogs] = Field(..., description="Scope logs")

class OTLPLogsData(BaseModel):
    """OTLP logs data container"""
    resource_logs: List[OTLPResourceLogs] = Field(..., description="Resource logs")

# CEF (Common Event Format) models
class CEFEntry(BaseModel):
    """Common Event Format entry"""
    version: int = Field(0, description="CEF version")
    device_vendor: str = Field(..., description="Device vendor")
    device_product: str = Field(..., description="Device product") 
    device_version: str = Field(..., description="Device version")
    signature_id: str = Field(..., description="Signature ID")
    name: str = Field(..., description="Event name")
    severity: int = Field(..., description="Event severity (0-10)")
    extensions: Dict[str, str] = Field(default_factory=dict, description="CEF extensions")

# Nginx access log model
class NginxAccessEntry(BaseModel):
    """Nginx access log entry"""
    remote_addr: str = Field(..., description="Client IP")
    remote_user: Optional[str] = Field("-", description="Remote user")
    time_local: str = Field(..., description="Local timestamp")
    request: str = Field(..., description="HTTP request line")
    status: int = Field(..., description="HTTP status code")
    body_bytes_sent: int = Field(0, description="Response body bytes")
    http_referer: Optional[str] = Field("-", description="HTTP referer")
    http_user_agent: str = Field(..., description="User agent")
    request_time: Optional[float] = Field(0.0, description="Request time in seconds")
    upstream_response_time: Optional[str] = Field("-", description="Upstream response time")

# Application JSON log models
class StructuredLogEntry(BaseModel):
    """Structured application log (common JSON format)"""
    timestamp: Union[str, datetime] = Field(..., description="Log timestamp")
    level: str = Field(..., description="Log level")
    logger: Optional[str] = Field("", description="Logger name")
    message: str = Field(..., description="Log message")
    thread: Optional[str] = Field("", description="Thread name")
    mdc: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Mapped Diagnostic Context")
    exception: Optional[Dict[str, Any]] = Field(None, description="Exception details")
    
    # Common application fields
    user_id: Optional[str] = Field("", description="User ID")
    session_id: Optional[str] = Field("", description="Session ID") 
    request_id: Optional[str] = Field("", description="Request ID")
    correlation_id: Optional[str] = Field("", description="Correlation ID")
    
    # HTTP-specific fields
    http_method: Optional[str] = Field("", description="HTTP method")
    http_url: Optional[str] = Field("", description="HTTP URL")
    http_status_code: Optional[int] = Field(0, description="HTTP status")
    response_time_ms: Optional[int] = Field(0, description="Response time milliseconds")

# Response models
class IngestResponse(BaseModel):
    """Response for log ingestion"""
    status: str
    message: str
    log_id: Optional[str] = None
    processed_count: Optional[int] = 1
    errors: Optional[List[str]] = Field(default_factory=list)

class BatchIngestResponse(BaseModel):
    """Response for batch log ingestion"""
    status: str
    message: str
    processed_count: int
    error_count: int = 0
    errors: Optional[List[str]] = Field(default_factory=list)

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    services: Dict[str, str]

class QueryResponse(BaseModel):
    """Log query response"""
    logs: List[Dict[str, Any]]
    total: int
    query_time_ms: Optional[float] = 0
    
# Validation models for different ingestion formats
class IngestFormat(str, Enum):
    """Supported ingestion formats"""
    JSON = "json"
    SYSLOG = "syslog" 
    OTLP = "otlp"
    CEF = "cef"
    NGINX = "nginx"
    TEXT = "text"

class TextLogEntry(BaseModel):
    """Plain text log entry"""
    message: str = Field(..., description="Raw log message")
    source: Optional[str] = Field("", description="Log source/file")
    
    # Optional fields that may be extracted
    service: Optional[str] = Field("unknown", description="Service name")
    level: Optional[str] = Field("info", description="Log level")
    host: Optional[str] = Field("", description="Hostname")

# Parser configuration
class ParserConfig(BaseModel):
    """Configuration for log parsers"""
    format: IngestFormat
    patterns: Optional[Dict[str, str]] = Field(default_factory=dict, description="Regex patterns")
    field_mappings: Optional[Dict[str, str]] = Field(default_factory=dict, description="Field name mappings")
    default_service: Optional[str] = Field("unknown", description="Default service name")
    default_level: Optional[str] = Field("info", description="Default log level")
    timezone: Optional[str] = Field("UTC", description="Default timezone")
    
# Bulk operations
class BulkOperation(BaseModel):
    """Bulk log operation"""
    operation: Literal["index", "create", "update", "delete"]
    index: Optional[str] = Field(None, description="Target table/index")
    doc: Optional[Dict[str, Any]] = Field(None, description="Document data")

class BulkRequest(BaseModel):
    """Bulk request with multiple operations"""
    operations: List[BulkOperation] = Field(..., description="List of bulk operations")
    
    @validator('operations')
    def validate_bulk_size(cls, v):
        if len(v) > 10000:
            raise ValueError("Bulk operation size cannot exceed 10000 operations")
        return v