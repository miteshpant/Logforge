"""
Data models for Logforge API
Supports multiple log formats and ingestion protocols
"""

from pydantic import BaseModel, Field, validator, root_validator
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Union, Literal
from enum import Enum
from dataclasses import dataclass, field
import json
import re
import uuid

class BaseResponse(BaseModel):
    """Generic response model for API endpoints"""
    status: str = Field(description="Response status: success, error, warning")
    message: str = Field(description="Human-readable response message")
    timestamp: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc), description="Response timestamp")

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

    class Config:
        # Allow customers to send any field names - field mapping will normalize them
        extra = "allow"

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

    @root_validator(pre=True)
    def apply_comprehensive_field_mapping(cls, values):
        """Apply comprehensive field mapping using field_mapper.py and field_mapping.yml"""
        try:
            # Import field mapper (handles comprehensive YAML-based mappings)
            from field_mapper import normalize_log_for_sigma
            
            # Apply comprehensive field normalization
            normalized_values = normalize_log_for_sigma(values)
            
            # Merge normalized values back into original values
            # Always use normalized values when available to ensure field mapping works
            for key, value in normalized_values.items():
                values[key] = value
                    
            return values
            
        except Exception as e:
            # If field mapping fails, log warning but don't break ingestion
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Field mapping failed, using original values: {e}")
            return values

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
    logs: List[Dict[str, Any]] = Field(description="Log entries")
    logs: List[Dict[str, Any]] = []
    aggregations: Dict[str, Any] = Field(description="Aggregation results")
    aggregations: Dict[str, Any] = {}
    total_count: int = Field(0, description="Total matching records")
    execution_time_ms: float = Field(0, description="Query execution time")
    has_more: bool = Field(False, description="More results available")
    next_offset: Optional[int] = Field(None, description="Next offset for pagination")
    query_info: Dict[str, Any] = Field(description="Query execution information")
    query_info: Dict[str, Any] = {}
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
    CLICKHOUSE = "clickhouse"

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
    max_data_ingestion_gb_per_day: Optional[int] = Field(None, description="Maximum data ingestion per day in GB")
    max_queries_per_hour: Optional[int] = Field(1000, description="Maximum queries per hour")
    max_storage_gb: Optional[int] = Field(None, description="Maximum storage in GB")
    max_alerts: Optional[int] = Field(50, description="Maximum number of alerts")
    max_users: Optional[int] = Field(25, description="Maximum number of users")

class TenantConfig(BaseModel):
    """Tenant configuration settings"""
    tenant_id: Optional[str] = Field(None, description="Tenant identifier")
    timezone: str = Field("UTC", description="Default timezone")
    log_retention_days: int = Field(90, description="Log retention period in days")
    encryption_enabled: bool = Field(True, description="Whether encryption is enabled")
    notification_settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Notification settings")
    custom_branding: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom branding settings")
    alert_settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Alert configuration")
    integration_settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Integration settings")
    security_settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Security settings")
    ui_preferences: Optional[Dict[str, Any]] = Field(default_factory=dict, description="UI preferences")

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
    tenants: List[TenantResponse] = Field(default_factory=list, description="List of tenants")
    total_count: int = Field(0, description="Total tenant count")
    page: int = Field(1, description="Current page")
    page_size: int = Field(50, description="Page size")
    total_pages: int = Field(1, description="Total number of pages")

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
    current_period: str = Field("", description="Current billing period")
    data_ingested_bytes: int = Field(0, description="Data ingested in bytes")
    queries_executed: int = Field(0, description="Queries executed")
    alerts_triggered: int = Field(0, description="Alerts triggered")
    storage_used_bytes: int = Field(0, description="Storage used in bytes")
    cost_breakdown: Dict[str, float] = Field(default_factory=dict, description="Cost breakdown by feature")

class TenantHealthResponse(BaseModel):
    """Tenant health monitoring response"""
    tenant_id: str
    overall_health: str = Field("healthy", description="Overall health status")
    service_status: Dict[str, str] = Field(default_factory=dict, description="Individual service statuses")
    storage_health: str = Field("healthy", description="Storage system health")
    ingestion_health: str = Field("healthy", description="Log ingestion health")
    query_health: str = Field("healthy", description="Query engine health")
    alert_health: str = Field("healthy", description="Alert system health")
    active_alerts: int = Field(0, description="Number of active alerts")
    last_check: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last health check timestamp")
    uptime_percentage: Optional[float] = Field(None, description="System uptime percentage")
    issues: List[str] = Field(default_factory=list, description="Current health issues")

# =================================================================
# M8 USER SERVICE & AUTHENTICATION MODELS
# =================================================================

class UserStatus(str, Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    SUSPENDED = "suspended"

class UserRole(str, Enum):
    """User roles for platform and tenant access"""
    # Platform Admin Roles
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    SUPPORT_ADMIN = "support_admin"
    BILLING_ADMIN = "billing_admin"

    # Customer User Roles
    TENANT_ADMIN = "tenant_admin"
    SECURITY_ANALYST = "security_analyst"
    DEVOPS_ENGINEER = "devops_engineer"
    COMPLIANCE_OFFICER = "compliance_officer"
    VIEWER = "viewer"

class SessionStatus(str, Enum):
    """Session status"""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"

class User(BaseModel):
    """User entity model"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique user UUID")
    email: str = Field(..., description="User email (unique)")
    name: str = Field(..., description="Full user name")
    password_hash: Optional[str] = Field(None, description="Hashed password (not returned in API)")
    status: UserStatus = Field(UserStatus.PENDING, description="Account status")
    customer_id: str = Field(default="platform", description="Customer/tenant ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Account creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")
    password_reset_token: Optional[str] = Field(None, description="Password reset token")
    password_reset_expires: Optional[datetime] = Field(None, description="Reset token expiration")
    email_verified_at: Optional[datetime] = Field(None, description="Email verification timestamp")
    setup_token: Optional[str] = Field(None, description="Initial setup token")
    setup_token_expires: Optional[datetime] = Field(None, description="Setup token expiration")

    @validator('email')
    def validate_email(cls, v):
        """Validate email format"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Invalid email format')
        return v.lower()

class UserTenantRole(BaseModel):
    """User role assignment for specific tenant"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Role assignment UUID")
    user_id: str = Field(..., description="User UUID")
    tenant_id: str = Field(..., description="Tenant UUID ('platform' for admin users)")
    role: UserRole = Field(..., description="Assigned role")
    granted_by: str = Field(..., description="User who granted this role")
    granted_at: datetime = Field(default_factory=datetime.utcnow, description="Role granted timestamp")
    expires_at: Optional[datetime] = Field(None, description="Role expiration (optional)")
    status: UserStatus = Field(UserStatus.ACTIVE, description="Role assignment status")

class UserSession(BaseModel):
    """User session model"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Session UUID")
    user_id: str = Field(..., description="User UUID")
    session_token: str = Field(..., description="Session token (JWT or random)")
    ip_address: str = Field(..., description="Client IP address")
    user_agent: str = Field(..., description="Client user agent")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Session creation time")
    last_activity: datetime = Field(default_factory=datetime.utcnow, description="Last activity timestamp")
    expires_at: datetime = Field(..., description="Session expiration time")
    status: SessionStatus = Field(SessionStatus.ACTIVE, description="Session status")

class APIUsageAudit(BaseModel):
    """API usage audit record for billing"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Audit record UUID")
    tenant_id: str = Field(..., description="Tenant UUID")
    user_id: str = Field(..., description="User UUID")
    endpoint: str = Field(..., description="API endpoint accessed")
    method: str = Field(..., description="HTTP method")
    status_code: int = Field(..., description="HTTP response status code")
    response_size_bytes: int = Field(0, description="Response size in bytes")
    processing_time_ms: int = Field(0, description="Processing time in milliseconds")
    ip_address: str = Field(..., description="Client IP address")
    user_agent: str = Field(..., description="Client user agent")
    request_timestamp: datetime = Field(default_factory=datetime.utcnow, description="Request timestamp")
    billing_feature: str = Field(..., description="Billing feature category")
    cost_credits: float = Field(0.0, description="Cost in credits")

# =================================================================
# API REQUEST/RESPONSE MODELS
# =================================================================

class UserCreateRequest(BaseModel):
    """Request to create new user"""
    name: str = Field(..., min_length=1, max_length=255, description="Full user name")
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=12, description="User password (min 12 chars)")
    status: UserStatus = Field(UserStatus.PENDING, description="Initial account status")

    @validator('password')
    def validate_password_strength(cls, v):
        """Enforce strong password policy"""
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain number')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain special character')
        return v

class UserUpdateRequest(BaseModel):
    """Request to update user"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Full user name")
    email: Optional[str] = Field(None, description="User email address")
    status: Optional[UserStatus] = Field(None, description="Account status")

class UserResponse(BaseModel):
    """User response (no sensitive data)"""
    id: str
    email: str
    name: str
    status: UserStatus
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime]
    email_verified_at: Optional[datetime]

class UserListResponse(BaseModel):
    """User list response"""
    users: List[UserResponse] = Field(description="List of users")
    total_count: int = Field(0, description="Total user count")
    page: int = Field(1, description="Current page")
    page_size: int = Field(50, description="Page size")

class LoginRequest(BaseModel):
    """User login request"""
    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password")

class LoginResponse(BaseModel):
    """User login response"""
    access_token: str = Field(..., description="Access token")
    expires_at: datetime = Field(..., description="Token expiration time")
    user: UserResponse = Field(..., description="User profile")
    # LF-015: rotating refresh token. Optional so the response stays
    # backward-compatible with clients that ignore it.
    refresh_token: Optional[str] = Field(None, description="Opaque rotating refresh token")
    refresh_expires_at: Optional[datetime] = Field(None, description="Refresh token expiration time")

class RefreshRequest(BaseModel):
    """Token refresh request (LF-015).

    Carries the opaque refresh token; deliberately does NOT require a valid
    access token, since its whole purpose is renewing an expired session.
    """
    refresh_token: str = Field(..., min_length=16, description="Refresh token issued at login")

class LogoutRequest(BaseModel):
    """Optional logout body carrying the refresh token to revoke (LF-015)."""
    refresh_token: Optional[str] = Field(None, description="Refresh token to revoke")

class RoleAssignmentRequest(BaseModel):
    """Request to assign role to user"""
    tenant_id: str = Field(..., description="Tenant UUID ('platform' for admin)")
    role: UserRole = Field(..., description="Role to assign")

class RoleAssignmentResponse(BaseModel):
    """Role assignment response"""
    id: str
    user_id: str
    tenant_id: str
    role: UserRole
    granted_by: str
    granted_at: datetime
    expires_at: Optional[datetime]
    status: UserStatus

class UserRolesResponse(BaseModel):
    """User roles response"""
    user_id: str
    roles: List[RoleAssignmentResponse] = Field(description="User's role assignments")

class PermissionCheckRequest(BaseModel):
    """Request to check user permission"""
    resource: str = Field(..., description="Resource to check access for (e.g., 'logs', 'dashboards')")
    action: str = Field(..., description="Action to check (e.g., 'read', 'write', 'delete')")
    scope: str = Field(..., description="Scope of access (e.g., 'tenant', 'platform')")
    tenant_id: Optional[str] = Field(None, description="Tenant ID (optional, defaults to X-Customer-ID header)")

class SetupTokenResponse(BaseModel):
    """Initial setup token response"""
    setup_token: str = Field(..., description="Secure setup token")
    expires_at: datetime = Field(..., description="Token expiration time")

class AdminSetupRequest(BaseModel):
    """Initial admin setup request"""
    name: str = Field(..., description="Admin name")
    email: str = Field(..., description="Admin email")
    password: str = Field(..., description="Admin password")
    setup_token: str = Field(..., description="Setup token")

class InvitationRequest(BaseModel):
    """User invitation request"""
    email: str = Field(..., description="Invitee email")
    role: UserRole = Field(..., description="Role to assign")
    tenant_id: str = Field(..., description="Tenant UUID")

class InvitationResponse(BaseModel):
    """User invitation response"""
    invitation_token: str = Field(..., description="Invitation token")
    invitation_expires: datetime = Field(..., description="Invitation expiration")
    invited_email: str = Field(..., description="Invited user email")
    email: str = Field(..., description="Email (alias for invited_email for compatibility)")
    tenant_id: str = Field(..., description="Tenant ID for the invitation")
    role: str = Field(..., description="Role assigned in the invitation")

class AcceptInviteRequest(BaseModel):
    """Accept invitation request"""
    name: str = Field(..., description="User full name")
    email: str = Field(..., description="User email (must match invitation)")
    password: str = Field(..., description="User password")
    invitation_token: str = Field(..., description="Invitation token")
    tenant_id: str = Field(..., description="Tenant UUID")

class PasswordResetRequest(BaseModel):
    """Password reset request"""
    email: str = Field(..., description="User email")

class PasswordChangeRequest(BaseModel):
    """Password change request"""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., description="New password")

class UsageCurrentResponse(BaseModel):
    """Current usage response"""
    tenant_id: str
    api_calls: int = Field(0, description="API calls this month")
    feature_breakdown: Dict[str, int] = Field(default_factory=dict, description="Usage by feature")
    cost_estimate: float = Field(0.0, description="Estimated cost this month")
    billing_period: str = Field("", description="Current billing period")

class BillingEstimateResponse(BaseModel):
    """Billing estimate response"""
    tenant_id: str
    total_estimated_cost: float = Field(0.0, description="Total estimated cost")
    feature_costs: Dict[str, float] = Field(default_factory=dict, description="Cost breakdown by feature")
    period: str = Field("", description="Billing period")

class UsageHistoryResponse(BaseModel):
    """Usage history response"""
    tenant_id: str
    usage_by_month: List[Dict[str, Any]] = Field(default_factory=list, description="Monthly usage history")
    storage_health: str = Field("healthy", description="Storage backend health")
    query_performance: Dict[str, Any] = Field(default_factory=dict, description="Query performance metrics")
    last_activity: Optional[datetime] = Field(None, description="Last activity timestamp")

class StorageStatusResponse(BaseModel):
    """Storage status response"""
    tenant_id: str
    storage_backend: StorageBackendType = Field(..., description="Storage backend type")
    total_size_bytes: float = Field(0.0, description="Total storage size in bytes")
    hot_storage_bytes: float = Field(0.0, description="Hot storage bytes")
    warm_storage_bytes: float = Field(0.0, description="Warm storage bytes")
    cold_storage_bytes: float = Field(0.0, description="Cold storage bytes")
    health_status: str = Field("healthy", description="Storage health status")
    connection_status: str = Field("connected", description="Connection status")
    last_backup: Optional[datetime] = Field(None, description="Last backup timestamp")

# =====================================
# Subscription & Billing Models
# =====================================

class SubscriptionTier(str, Enum):
    """Subscription tier levels"""
    STARTUP = "startup"
    STARTER = "starter"
    SMB = "smb"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    NON_PROFIT = "non_profit"
    GOVERNMENT = "government"
    EDUCATION = "education"
    HEALTHCARE = "healthcare"
    FINANCIAL = "financial"

class BillingCycle(str, Enum):
    """Billing cycle options"""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

class SubscriptionStatus(str, Enum):
    """Subscription status"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"

class PricingModel(str, Enum):
    """Pricing model types"""
    PER_UNIT = "per_unit"
    FIXED_MONTHLY = "fixed_monthly"
    TIERED = "tiered"

class DeletionType(str, Enum):
    """Tenant deletion types"""
    SOFT_DELETE = "soft_delete"
    HARD_DELETE = "hard_delete"

@dataclass
class TenantSubscription:
    """Tenant subscription configuration"""
    tenant_id: str
    subscribed_features: List[str]
    subscription_tier: SubscriptionTier
    billing_cycle: BillingCycle
    status: SubscriptionStatus
    started_at: datetime
    expires_at: Optional[datetime] = None
    auto_renew: bool = True
    monthly_spend_limit: Optional[float] = None
    overage_allowed: bool = False

@dataclass
class FeatureRate:
    """Feature pricing configuration"""
    feature_name: str
    pricing_model: PricingModel
    base_rate: float
    tier_rates: Dict[str, float]
    currency: str = "USD"
    effective_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = "system"
    description: str = ""

@dataclass
class UsageRecord:
    """Usage tracking for billing"""
    usage_id: str
    tenant_id: str
    feature_name: str
    usage_type: str
    quantity: int
    timestamp: datetime
    billing_period: str
    cost_calculated: float
    rate_applied: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TenantDeletion:
    """Tenant deletion record"""
    tenant_id: str
    deletion_type: DeletionType
    deleted_at: datetime
    deleted_by: str
    reason: str
    data_cleanup_completed: bool = False
    usage_records_retained: bool = True
    final_bill_generated: bool = False

class TenantSubscriptionRequest(BaseModel):
    """Request to update tenant subscription"""
    subscribed_features: List[str] = Field(..., description="List of subscribed features")
    subscription_tier: SubscriptionTier = Field(..., description="Subscription tier")
    billing_cycle: BillingCycle = Field(BillingCycle.MONTHLY, description="Billing cycle")
    monthly_spend_limit: Optional[float] = Field(None, description="Monthly spending limit")
    auto_renew: bool = Field(True, description="Auto-renewal enabled")

class FeatureRateRequest(BaseModel):
    """Request to set feature rate"""
    feature_name: str = Field(..., description="Feature name")
    pricing_model: PricingModel = Field(..., description="Pricing model")
    base_rate: float = Field(..., description="Base rate per unit")
    tier_rates: Dict[str, float] = Field(default_factory=dict, description="Tier-specific rates")
    currency: str = Field("USD", description="Currency code")
    description: str = Field("", description="Rate description")

class TenantDeletionRequest(BaseModel):
    """Request to delete tenant"""
    deletion_type: DeletionType = Field(DeletionType.SOFT_DELETE, description="Type of deletion")
    reason: str = Field(..., description="Reason for deletion")
    data_cleanup: bool = Field(True, description="Clean up all tenant data")
    generate_final_bill: bool = Field(True, description="Generate final bill")
    confirmation: Optional[str] = Field(None, description="Confirmation for hard delete")

class TenantSubscriptionResponse(BaseModel):
    """Tenant subscription details response"""
    tenant_id: str
    subscribed_features: List[str]
    subscription_tier: SubscriptionTier
    billing_cycle: BillingCycle
    status: SubscriptionStatus
    started_at: datetime
    expires_at: Optional[datetime]
    auto_renew: bool
    monthly_spend_limit: Optional[float]
    current_usage: Dict[str, int] = Field(default_factory=dict)

class FeatureAccessResponse(BaseModel):
    """Feature access validation response"""
    tenant_id: str
    feature: str
    access_granted: bool
    subscription_tier: SubscriptionTier
    usage_limits: Dict[str, Any] = Field(default_factory=dict)
    current_usage: Dict[str, int] = Field(default_factory=dict)

class UsageBreakdownResponse(BaseModel):
    """Detailed usage breakdown response"""
    tenant_id: str
    billing_period: str
    total_cost: float
    currency: str
    feature_usage: List[Dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime
