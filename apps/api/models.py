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
import uuid

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
    
    # Runtime metadata fields
    ingested_at: Optional[datetime] = Field(None, description="Ingestion timestamp")
    customer_id: Optional[str] = Field("default", description="Customer identifier for multi-tenancy")

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
    logs: List[Dict[str, Any]] = Field(default=[], description="Log entries")
    aggregations: Dict[str, Any] = Field(default={}, description="Aggregation results")
    total_count: int = Field(0, description="Total matching records")
    execution_time_ms: float = Field(0, description="Query execution time")
    has_more: bool = Field(False, description="More results available")
    next_offset: Optional[int] = Field(None, description="Next offset for pagination")
    query_info: Dict[str, Any] = Field(default={}, description="Query execution information")
    customer_id: Optional[str] = Field("default", description="Customer identifier for multi-tenancy")
    
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

# Tenant Management Models
class TenantType(str, Enum):
    """Types of tenant organizations"""
    ENTERPRISE = "enterprise"
    SMB = "smb"
    STARTUP = "startup"
    NON_PROFIT = "non_profit"
    GOVERNMENT = "government"
    EDUCATION = "education"
    HEALTHCARE = "healthcare"
    FINANCIAL = "financial"

class TenantStatus(str, Enum):
    """Tenant account status"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    PENDING = "pending"
    INACTIVE = "inactive"

class StorageBackendType(str, Enum):
    """Supported storage backend types"""
    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"
    MINIO = "minio"

class TenantCreate(BaseModel):
    """Tenant creation request"""
    name: str = Field(..., description="Organization name", min_length=1, max_length=100)
    type: TenantType = Field(..., description="Organization type")
    address: Optional[str] = Field("", description="Organization address", max_length=500)
    primary_contact_name: str = Field(..., description="Primary contact name", min_length=1, max_length=100)
    primary_contact_email: str = Field(..., description="Primary contact email")
    primary_contact_phone: Optional[str] = Field("", description="Primary contact phone", max_length=20)
    industry: Optional[str] = Field("", description="Industry sector", max_length=100)
    company_size: Optional[int] = Field(None, description="Number of employees")
    website: Optional[str] = Field("", description="Company website", max_length=200)
    notes: Optional[str] = Field("", description="Additional notes", max_length=1000)
    
    @validator('primary_contact_email')
    def validate_email(cls, v):
        """Basic email validation"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()

class TenantUpdate(BaseModel):
    """Tenant update request"""
    name: Optional[str] = Field(None, description="Organization name", min_length=1, max_length=100)
    type: Optional[TenantType] = Field(None, description="Organization type")
    address: Optional[str] = Field(None, description="Organization address", max_length=500)
    primary_contact_name: Optional[str] = Field(None, description="Primary contact name", min_length=1, max_length=100)
    primary_contact_email: Optional[str] = Field(None, description="Primary contact email")
    primary_contact_phone: Optional[str] = Field(None, description="Primary contact phone", max_length=20)
    industry: Optional[str] = Field(None, description="Industry sector", max_length=100)
    company_size: Optional[int] = Field(None, description="Number of employees")
    website: Optional[str] = Field(None, description="Company website", max_length=200)
    notes: Optional[str] = Field(None, description="Additional notes", max_length=1000)
    status: Optional[TenantStatus] = Field(None, description="Tenant status")
    
    @validator('primary_contact_email')
    def validate_email(cls, v):
        """Basic email validation"""
        if v is None:
            return v
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()

class StorageConfig(BaseModel):
    """Storage backend configuration"""
    backend_type: StorageBackendType = Field(..., description="Storage backend type")
    region: str = Field(..., description="Storage region")
    bucket_name: str = Field(..., description="Bucket/container name")
    access_key_id: Optional[str] = Field("", description="Access key ID")
    secret_access_key: Optional[str] = Field("", description="Secret access key")
    encryption_enabled: bool = Field(True, description="Enable encryption at rest")
    lifecycle_policy: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Lifecycle management policy")

class TenantQuotas(BaseModel):
    """Tenant quota configuration"""
    monthly_log_limit: Optional[int] = Field(None, description="Monthly log ingestion limit")
    storage_limit_gb: Optional[int] = Field(None, description="Storage limit in GB")
    retention_days: int = Field(30, description="Log retention period in days")
    query_rate_limit: Optional[int] = Field(1000, description="Queries per minute limit")

class TenantConfig(BaseModel):
    """Tenant configuration settings"""
    timezone: str = Field("UTC", description="Default timezone")
    data_residency: str = Field("US", description="Data residency requirement")
    compliance_frameworks: List[str] = Field(default_factory=list, description="Active compliance frameworks")
    encryption_required: bool = Field(True, description="Require encryption")
    retention_policy: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Data retention policy")
    notification_preferences: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Notification settings")

class LegalHoldRequest(BaseModel):
    """Legal hold creation request"""
    case_name: str = Field(..., description="Legal case name")
    description: str = Field(..., description="Hold description")
    start_date: str = Field(..., description="Hold start date")
    end_date: str = Field(..., description="Hold end date")
    contact_person: str = Field(..., description="Legal contact person")
    contact_email: str = Field(..., description="Legal contact email")
    data_types: List[str] = Field(..., description="Data types to preserve")
    justification: str = Field(..., description="Legal justification")

class Tenant(BaseModel):
    """Tenant entity"""
    tenant_id: str = Field(..., description="Unique tenant UUID")
    name: str = Field(..., description="Organization name")
    type: TenantType = Field(..., description="Organization type")
    address: str = Field("", description="Organization address")
    primary_contact_name: str = Field(..., description="Primary contact name")
    primary_contact_email: str = Field(..., description="Primary contact email")
    primary_contact_phone: str = Field("", description="Primary contact phone")
    industry: str = Field("", description="Industry sector")
    company_size: Optional[int] = Field(None, description="Number of employees")
    website: str = Field("", description="Company website")
    notes: str = Field("", description="Additional notes")
    status: TenantStatus = Field(TenantStatus.ACTIVE, description="Tenant status")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    # Usage and billing
    monthly_log_limit: Optional[int] = Field(None, description="Monthly log ingestion limit")
    storage_limit_gb: Optional[int] = Field(None, description="Storage limit in GB")
    retention_days: int = Field(30, description="Log retention period in days")
    
    # Settings
    timezone: str = Field("UTC", description="Default timezone")
    data_residency: str = Field("US", description="Data residency requirement")

class TenantResponse(BaseModel):
    """Tenant response model"""
    tenant_id: str
    name: str
    type: TenantType
    status: TenantStatus
    primary_contact_name: str
    primary_contact_email: str
    industry: str
    created_at: datetime
    updated_at: datetime

class TenantListResponse(BaseModel):
    """Tenant list response"""
    tenants: List[TenantResponse] = Field(default=[], description="List of tenants")
    total_count: int = Field(0, description="Total tenant count")
    page: int = Field(1, description="Current page")
    page_size: int = Field(50, description="Page size")

class TenantStatsResponse(BaseModel):
    """Tenant statistics response"""
    tenant_id: str
    log_count_today: int = Field(0, description="Logs ingested today")
    log_count_month: int = Field(0, description="Logs ingested this month")
    storage_used_gb: float = Field(0.0, description="Storage used in GB")
    storage_limit_gb: Optional[int] = Field(None, description="Storage limit in GB")
    active_alerts: int = Field(0, description="Active alert count")
    last_activity: Optional[datetime] = Field(None, description="Last log ingestion time")

class TenantUsageResponse(BaseModel):
    """Tenant usage and billing response"""
    tenant_id: str
    log_count_today: int = Field(0, description="Logs ingested today")
    log_count_month: int = Field(0, description="Logs ingested this month")
    storage_used_gb: float = Field(0.0, description="Storage used in GB")
    query_count: int = Field(0, description="Queries executed")
    api_calls: int = Field(0, description="API calls made")
    billing_period: str = Field("", description="Current billing period")

class TenantHealthResponse(BaseModel):
    """Tenant health monitoring response"""
    tenant_id: str
    status: str = Field("healthy", description="Overall health status")
    ingestion_health: str = Field("healthy", description="Log ingestion health")
    storage_health: str = Field("healthy", description="Storage backend health")
    query_performance: Dict[str, Any] = Field(default_factory=dict, description="Query performance metrics")
    last_activity: Optional[datetime] = Field(None, description="Last activity timestamp")

class StorageStatusResponse(BaseModel):
    """Storage status response"""
    tenant_id: str
    backend_type: StorageBackendType
    storage_used_gb: float = Field(0.0, description="Storage used in GB")
    storage_limit_gb: Optional[int] = Field(None, description="Storage limit in GB")
    health_status: str = Field("healthy", description="Storage health status")
    connection_status: str = Field("connected", description="Connection status")
    last_backup: Optional[datetime] = Field(None, description="Last backup timestamp")