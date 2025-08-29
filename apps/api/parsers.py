"""
Log parsers for different formats
Supports Nginx, Syslog, CEF, JSON, and plain text parsing
"""

import re
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union, Tuple
from urllib.parse import unquote
import structlog

from models import (
    LogEntry, SyslogEntry, CEFEntry, NginxAccessEntry, 
    StructuredLogEntry, TextLogEntry, OTLPLogRecord, OTLPLogsData,
    LogLevel, SyslogSeverity, SyslogFacility
)

logger = structlog.get_logger()

class ParseError(Exception):
    """Exception raised when log parsing fails"""
    pass

class BaseParser:
    """Base class for log parsers"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.default_service = self.config.get('default_service', 'unknown')
        self.default_level = self.config.get('default_level', 'info')
        self.default_host = self.config.get('default_host', '')
        
    def parse(self, raw_message: str, **kwargs) -> LogEntry:
        """Parse raw message into LogEntry"""
        raise NotImplementedError
        
    def extract_fields(self, raw_message: str) -> Dict[str, Any]:
        """Extract fields from raw message"""
        raise NotImplementedError
        
    def normalize_timestamp(self, timestamp_str: str) -> datetime:
        """Normalize timestamp to datetime object"""
        if not timestamp_str or timestamp_str == '-':
            return datetime.utcnow()
            
        # Common timestamp formats
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",       # ISO format with microseconds
            "%Y-%m-%dT%H:%M:%SZ",          # ISO format
            "%Y-%m-%d %H:%M:%S.%f",        # Space separated with microseconds
            "%Y-%m-%d %H:%M:%S",           # Space separated
            "%d/%b/%Y:%H:%M:%S %z",        # Nginx format with timezone
            "%d/%b/%Y:%H:%M:%S",           # Nginx format without timezone
            "%b %d %H:%M:%S",              # Syslog format (current year)
            "%Y %b %d %H:%M:%S",           # Syslog with year
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue
                
        # Try dateutil parser as fallback
        try:
            from dateutil.parser import parse
            return parse(timestamp_str)
        except:
            logger.warning("Failed to parse timestamp", timestamp=timestamp_str)
            return datetime.utcnow()

class NginxAccessLogParser(BaseParser):
    """Parser for Nginx access logs"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        
        # Default nginx log format: log_format combined
        self.log_format = self.config.get('log_format', 'combined')
        
        # Regex patterns for different nginx log formats
        self.patterns = {
            'combined': re.compile(
                r'(?P<remote_addr>\S+) - (?P<remote_user>\S+) \[(?P<time_local>[^\]]+)\] '
                r'"(?P<request>[^"]*)" (?P<status>\d+) (?P<body_bytes_sent>\d+) '
                r'"(?P<http_referer>[^"]*)" "(?P<http_user_agent>[^"]*)"'
            ),
            'main': re.compile(
                r'(?P<remote_addr>\S+) - (?P<remote_user>\S+) \[(?P<time_local>[^\]]+)\] '
                r'"(?P<request>[^"]*)" (?P<status>\d+) (?P<body_bytes_sent>\d+)'
            ),
            'json': re.compile(r'.*'),  # JSON format handled separately
        }
        
        # Enhanced pattern with timing information
        self.timing_pattern = re.compile(
            r'(?P<remote_addr>\S+) - (?P<remote_user>\S+) \[(?P<time_local>[^\]]+)\] '
            r'"(?P<request>[^"]*)" (?P<status>\d+) (?P<body_bytes_sent>\d+) '
            r'"(?P<http_referer>[^"]*)" "(?P<http_user_agent>[^"]*)" '
            r'(?P<request_time>[\d.-]+)(?: (?P<upstream_response_time>[\d.-]+))?'
        )
    
    def parse(self, raw_message: str, **kwargs) -> LogEntry:
        """Parse nginx access log line"""
        try:
            # Try JSON format first
            if raw_message.strip().startswith('{'):
                return self._parse_json_format(raw_message)
            
            # Try timing pattern first (most complete)
            match = self.timing_pattern.match(raw_message)
            if not match:
                # Fallback to standard patterns
                pattern = self.patterns.get(self.log_format, self.patterns['combined'])
                match = pattern.match(raw_message)
                
            if not match:
                raise ParseError(f"No matching pattern for nginx log: {raw_message[:100]}...")
                
            fields = match.groupdict()
            return self._build_log_entry(fields)
            
        except Exception as e:
            logger.error("Failed to parse nginx log", error=str(e), raw_message=raw_message[:200])
            raise ParseError(f"Nginx parse error: {str(e)}")
    
    def _parse_json_format(self, raw_message: str) -> LogEntry:
        """Parse JSON format nginx log"""
        try:
            data = json.loads(raw_message)
            
            # Extract request components
            request_line = data.get('request', '')
            method, uri, protocol = self._parse_request_line(request_line)
            
            timestamp = self.normalize_timestamp(data.get('time_local', data.get('time_iso8601', '')))
            
            attrs = {
                'method': method,
                'uri': uri,
                'protocol': protocol,
                'status': int(data.get('status', 0)),
                'bytes': int(data.get('body_bytes_sent', 0)),
                'referer': data.get('http_referer', ''),
                'user_agent': data.get('http_user_agent', ''),
                'request_time': float(data.get('request_time', 0)),
                'upstream_response_time': data.get('upstream_response_time', ''),
                'remote_user': data.get('remote_user', ''),
                'geoip_country_code': data.get('geoip_country_code', ''),
                'ssl_protocol': data.get('ssl_protocol', ''),
                'ssl_cipher': data.get('ssl_cipher', ''),
            }
            
            # Remove empty/null values
            attrs = {k: v for k, v in attrs.items() if v not in ['', '-', None]}
            
            level = self._determine_log_level(int(data.get('status', 200)))
            
            return LogEntry(
                ts=timestamp,
                host=kwargs.get('host', self.default_host),
                service=kwargs.get('service', 'nginx'),
                level=level,
                msg=f"{method} {uri} {data.get('status')} {data.get('body_bytes_sent')}",
                attrs=attrs,
                status=int(data.get('status', 0)),
                src_ip=data.get('remote_addr', ''),
                user_id=data.get('remote_user', '') if data.get('remote_user') != '-' else ''
            )
            
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON in nginx log: {str(e)}")
    
    def _build_log_entry(self, fields: Dict[str, str]) -> LogEntry:
        """Build LogEntry from parsed fields"""
        timestamp = self.normalize_timestamp(fields.get('time_local', ''))
        
        # Parse request line
        request_line = fields.get('request', '')
        method, uri, protocol = self._parse_request_line(request_line)
        
        status = int(fields.get('status', 0))
        level = self._determine_log_level(status)
        
        attrs = {
            'method': method,
            'uri': uri,
            'protocol': protocol,
            'bytes': int(fields.get('body_bytes_sent', 0)),
            'referer': fields.get('http_referer', ''),
            'user_agent': fields.get('http_user_agent', ''),
        }
        
        # Add timing information if available
        if 'request_time' in fields:
            attrs['request_time'] = float(fields['request_time'])
        if 'upstream_response_time' in fields and fields['upstream_response_time'] != '-':
            attrs['upstream_response_time'] = float(fields['upstream_response_time'])
            
        # Remove empty/null values
        attrs = {k: v for k, v in attrs.items() if v not in ['', '-', None]}
        
        return LogEntry(
            ts=timestamp,
            host=self.default_host,
            service='nginx',
            level=level,
            msg=f"{method} {uri} {status} {fields.get('body_bytes_sent')}",
            attrs=attrs,
            status=status,
            src_ip=fields.get('remote_addr', ''),
            user_id=fields.get('remote_user', '') if fields.get('remote_user') != '-' else ''
        )
    
    def _parse_request_line(self, request_line: str) -> Tuple[str, str, str]:
        """Parse HTTP request line into method, URI, protocol"""
        if not request_line or request_line == '-':
            return '', '', ''
            
        parts = request_line.split(' ', 2)
        method = parts[0] if len(parts) > 0 else ''
        uri = parts[1] if len(parts) > 1 else ''
        protocol = parts[2] if len(parts) > 2 else ''
        
        # URL decode the URI
        try:
            uri = unquote(uri)
        except:
            pass
            
        return method, uri, protocol
    
    def _determine_log_level(self, status_code: int) -> str:
        """Determine log level based on HTTP status code"""
        if status_code >= 500:
            return 'error'
        elif status_code >= 400:
            return 'warn'
        elif status_code >= 300:
            return 'info'
        else:
            return 'info'

class SyslogParser(BaseParser):
    """Parser for Syslog messages (RFC 3164 and RFC 5424)"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        
        # RFC 3164 pattern
        self.rfc3164_pattern = re.compile(
            r'<(?P<priority>\d+)>(?P<timestamp>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}) '
            r'(?P<hostname>\S+) (?P<program>\S+?)(?:\[(?P<pid>\d+)\])?: (?P<message>.*)'
        )
        
        # RFC 5424 pattern  
        self.rfc5424_pattern = re.compile(
            r'<(?P<priority>\d+)>(?P<version>\d+) (?P<timestamp>\S+) (?P<hostname>\S+) '
            r'(?P<program>\S+) (?P<procid>\S+) (?P<msgid>\S+) (?P<structured_data>.*?) (?P<message>.*)'
        )
        
        # Simple pattern for messages without full syslog header
        self.simple_pattern = re.compile(
            r'(?P<timestamp>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}) (?P<hostname>\S+) '
            r'(?P<program>\S+?)(?:\[(?P<pid>\d+)\])?: (?P<message>.*)'
        )
    
    def parse(self, raw_message: str, **kwargs) -> LogEntry:
        """Parse syslog message"""
        try:
            # Try RFC 5424 first
            match = self.rfc5424_pattern.match(raw_message)
            if match:
                return self._parse_rfc5424(match.groupdict())
                
            # Try RFC 3164
            match = self.rfc3164_pattern.match(raw_message)
            if match:
                return self._parse_rfc3164(match.groupdict())
                
            # Try simple pattern
            match = self.simple_pattern.match(raw_message)
            if match:
                return self._parse_simple(match.groupdict())
                
            # If no pattern matches, treat as plain message
            return self._parse_fallback(raw_message, **kwargs)
            
        except Exception as e:
            logger.error("Failed to parse syslog", error=str(e), raw_message=raw_message[:200])
            raise ParseError(f"Syslog parse error: {str(e)}")
    
    def _parse_rfc5424(self, fields: Dict[str, str]) -> LogEntry:
        """Parse RFC 5424 syslog message"""
        priority = int(fields.get('priority', 16))
        facility, severity = self._parse_priority(priority)
        
        timestamp = self.normalize_timestamp(fields.get('timestamp', ''))
        level = self._severity_to_level(severity)
        
        attrs = {
            'syslog_version': fields.get('version', '1'),
            'facility': facility,
            'severity': severity,
            'procid': fields.get('procid', ''),
            'msgid': fields.get('msgid', ''),
            'structured_data': fields.get('structured_data', ''),
        }
        
        # Remove null values
        attrs = {k: v for k, v in attrs.items() if v not in ['-', '', None]}
        
        return LogEntry(
            ts=timestamp,
            host=fields.get('hostname', ''),
            service=fields.get('program', self.default_service),
            level=level,
            msg=fields.get('message', ''),
            attrs=attrs,
            severity_num=severity,
            facility=facility
        )
    
    def _parse_rfc3164(self, fields: Dict[str, str]) -> LogEntry:
        """Parse RFC 3164 syslog message"""
        priority = int(fields.get('priority', 16))
        facility, severity = self._parse_priority(priority)
        
        # RFC 3164 timestamps don't include year, add current year
        timestamp_str = fields.get('timestamp', '')
        if timestamp_str:
            current_year = datetime.now().year
            timestamp_str = f"{current_year} {timestamp_str}"
        timestamp = self.normalize_timestamp(timestamp_str)
        
        level = self._severity_to_level(severity)
        
        attrs = {
            'facility': facility,
            'severity': severity,
            'pid': int(fields['pid']) if fields.get('pid') else None,
        }
        
        attrs = {k: v for k, v in attrs.items() if v is not None}
        
        return LogEntry(
            ts=timestamp,
            host=fields.get('hostname', ''),
            service=fields.get('program', self.default_service),
            level=level,
            msg=fields.get('message', ''),
            attrs=attrs,
            severity_num=severity,
            facility=facility
        )
    
    def _parse_simple(self, fields: Dict[str, str]) -> LogEntry:
        """Parse simple syslog format"""
        timestamp_str = fields.get('timestamp', '')
        if timestamp_str:
            current_year = datetime.now().year
            timestamp_str = f"{current_year} {timestamp_str}"
        timestamp = self.normalize_timestamp(timestamp_str)
        
        attrs = {
            'pid': int(fields['pid']) if fields.get('pid') else None,
        }
        
        attrs = {k: v for k, v in attrs.items() if v is not None}
        
        return LogEntry(
            ts=timestamp,
            host=fields.get('hostname', ''),
            service=fields.get('program', self.default_service),
            level=self.default_level,
            msg=fields.get('message', ''),
            attrs=attrs
        )
    
    def _parse_fallback(self, raw_message: str, **kwargs) -> LogEntry:
        """Fallback parser for unstructured syslog"""
        return LogEntry(
            ts=datetime.utcnow(),
            host=kwargs.get('host', self.default_host),
            service=kwargs.get('service', self.default_service),
            level=self.default_level,
            msg=raw_message,
            attrs={'parser': 'syslog_fallback'}
        )
    
    def _parse_priority(self, priority: int) -> Tuple[int, int]:
        """Parse syslog priority into facility and severity"""
        facility = priority >> 3
        severity = priority & 0x07
        return facility, severity
    
    def _severity_to_level(self, severity: int) -> str:
        """Convert syslog severity to log level"""
        mapping = {
            0: 'fatal',    # Emergency
            1: 'fatal',    # Alert
            2: 'fatal',    # Critical
            3: 'error',    # Error
            4: 'warn',     # Warning
            5: 'info',     # Notice
            6: 'info',     # Info
            7: 'debug',    # Debug
        }
        return mapping.get(severity, 'info')

class CEFParser(BaseParser):
    """Parser for Common Event Format (CEF) logs"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        
        # CEF header pattern
        self.cef_pattern = re.compile(
            r'CEF:(?P<version>\d+)\|(?P<device_vendor>[^|]*)\|(?P<device_product>[^|]*)\|'
            r'(?P<device_version>[^|]*)\|(?P<signature_id>[^|]*)\|(?P<name>[^|]*)\|'
            r'(?P<severity>\d+)\|(?P<extensions>.*)'
        )
    
    def parse(self, raw_message: str, **kwargs) -> LogEntry:
        """Parse CEF message"""
        try:
            match = self.cef_pattern.match(raw_message.strip())
            if not match:
                raise ParseError(f"Invalid CEF format: {raw_message[:100]}...")
                
            fields = match.groupdict()
            extensions = self._parse_extensions(fields.get('extensions', ''))
            
            # Extract timestamp if present in extensions
            timestamp = datetime.utcnow()
            if 'rt' in extensions:  # Receipt time
                timestamp = self.normalize_timestamp(extensions['rt'])
            elif 'start' in extensions:  # Start time
                timestamp = self.normalize_timestamp(extensions['start'])
                
            severity = int(fields.get('severity', 5))
            level = self._cef_severity_to_level(severity)
            
            attrs = {
                'cef_version': int(fields.get('version', 0)),
                'device_vendor': fields.get('device_vendor', ''),
                'device_product': fields.get('device_product', ''),
                'device_version': fields.get('device_version', ''),
                'signature_id': fields.get('signature_id', ''),
                'cef_severity': severity,
                **extensions
            }
            
            return LogEntry(
                ts=timestamp,
                host=extensions.get('dhost', extensions.get('shost', kwargs.get('host', self.default_host))),
                service=kwargs.get('service', fields.get('device_product', 'cef')),
                level=level,
                msg=fields.get('name', ''),
                attrs=attrs,
                src_ip=extensions.get('src', ''),
                user_id=extensions.get('suser', extensions.get('duser', ''))
            )
            
        except Exception as e:
            logger.error("Failed to parse CEF log", error=str(e), raw_message=raw_message[:200])
            raise ParseError(f"CEF parse error: {str(e)}")
    
    def _parse_extensions(self, extensions_str: str) -> Dict[str, str]:
        """Parse CEF extensions string"""
        extensions = {}
        if not extensions_str:
            return extensions
            
        # Split on space, but handle escaped spaces and quoted values
        parts = []
        current = ""
        in_quotes = False
        escaped = False
        
        for char in extensions_str:
            if escaped:
                current += char
                escaped = False
            elif char == '\\':
                escaped = True
                current += char
            elif char == '"' and not escaped:
                in_quotes = not in_quotes
                current += char
            elif char == ' ' and not in_quotes and not escaped:
                if current:
                    parts.append(current)
                    current = ""
            else:
                current += char
                
        if current:
            parts.append(current)
        
        # Parse key=value pairs
        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                # Remove quotes from value
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                extensions[key] = value
                
        return extensions
    
    def _cef_severity_to_level(self, severity: int) -> str:
        """Convert CEF severity (0-10) to log level"""
        if severity >= 8:
            return 'fatal'
        elif severity >= 6:
            return 'error'
        elif severity >= 4:
            return 'warn'
        else:
            return 'info'

class JSONParser(BaseParser):
    """Parser for structured JSON logs"""
    
    def parse(self, raw_message: str, **kwargs) -> LogEntry:
        """Parse JSON log message"""
        try:
            data = json.loads(raw_message)
            
            # Handle different JSON log formats
            if 'timestamp' in data and 'level' in data and 'message' in data:
                return self._parse_structured_log(data, **kwargs)
            else:
                return self._parse_generic_json(data, **kwargs)
                
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON log", error=str(e), raw_message=raw_message[:200])
            raise ParseError(f"JSON parse error: {str(e)}")
    
    def _parse_structured_log(self, data: Dict[str, Any], **kwargs) -> LogEntry:
        """Parse structured application log format"""
        timestamp = self.normalize_timestamp(data.get('timestamp', data.get('time', '')))
        
        attrs = {k: v for k, v in data.items() if k not in [
            'timestamp', 'time', 'level', 'message', 'msg', 'host', 'service'
        ]}
        
        return LogEntry(
            ts=timestamp,
            host=data.get('host', kwargs.get('host', self.default_host)),
            service=data.get('service', data.get('logger', kwargs.get('service', self.default_service))),
            level=data.get('level', self.default_level),
            msg=data.get('message', data.get('msg', '')),
            attrs=attrs,
            trace_id=data.get('trace_id', data.get('traceId', '')),
            span_id=data.get('span_id', data.get('spanId', '')),
            user_id=data.get('user_id', data.get('userId', ''))
        )
    
    def _parse_generic_json(self, data: Dict[str, Any], **kwargs) -> LogEntry:
        """Parse generic JSON format"""
        # Try to extract common fields
        message = (
            data.get('message') or 
            data.get('msg') or 
            data.get('text') or 
            str(data)
        )
        
        level = (
            data.get('level') or 
            data.get('severity') or 
            self.default_level
        )
        
        # Extract timestamp from various fields
        timestamp_candidates = ['timestamp', 'time', 'ts', '@timestamp']
        timestamp = datetime.utcnow()
        for field in timestamp_candidates:
            if field in data:
                timestamp = self.normalize_timestamp(str(data[field]))
                break
        
        return LogEntry(
            ts=timestamp,
            host=kwargs.get('host', self.default_host),
            service=kwargs.get('service', self.default_service),
            level=level,
            msg=message,
            attrs=data
        )

class OTLPParser(BaseParser):
    """Parser for OpenTelemetry Protocol (OTLP) logs"""
    
    def parse_batch(self, otlp_data: OTLPLogsData, **kwargs) -> List[LogEntry]:
        """Parse OTLP logs data into LogEntry list"""
        log_entries = []
        
        try:
            for resource_logs in otlp_data.resource_logs:
                # Extract resource attributes
                resource_attrs = {}
                if resource_logs.resource:
                    for attr in resource_logs.resource.attributes:
                        resource_attrs[attr.key] = attr.value
                
                for scope_logs in resource_logs.scope_logs:
                    # Extract scope information
                    scope_info = scope_logs.scope or {}
                    
                    for log_record in scope_logs.log_records:
                        entry = self._parse_log_record(log_record, resource_attrs, scope_info, **kwargs)
                        log_entries.append(entry)
                        
        except Exception as e:
            logger.error("Failed to parse OTLP batch", error=str(e))
            raise ParseError(f"OTLP parse error: {str(e)}")
            
        return log_entries
    
    def _parse_log_record(self, log_record: OTLPLogRecord, resource_attrs: Dict, 
                         scope_info: Dict, **kwargs) -> LogEntry:
        """Parse individual OTLP log record"""
        # Convert nanosecond timestamp to datetime
        timestamp = datetime.fromtimestamp(log_record.time_unix_nano / 1e9, tz=timezone.utc)
        
        # Convert OTLP severity to log level
        level = self._otlp_severity_to_level(log_record.severity_number or 9)  # Default to INFO
        
        # Combine all attributes
        attrs = {**resource_attrs}
        for attr in log_record.attributes:
            attrs[attr.key] = attr.value
            
        # Add OTLP-specific fields
        if scope_info:
            attrs['scope'] = scope_info
        if log_record.dropped_attributes_count:
            attrs['dropped_attributes_count'] = log_record.dropped_attributes_count
        if log_record.flags:
            attrs['flags'] = log_record.flags
            
        return LogEntry(
            ts=timestamp,
            host=resource_attrs.get('host.name', kwargs.get('host', self.default_host)),
            service=resource_attrs.get('service.name', kwargs.get('service', self.default_service)),
            level=level,
            msg=log_record.body,
            trace_id=log_record.trace_id or '',
            span_id=log_record.span_id or '',
            attrs=attrs,
            severity_num=log_record.severity_number or 9
        )
    
    def _otlp_severity_to_level(self, severity_number: int) -> str:
        """Convert OTLP severity number to log level"""
        # OTLP severity numbers: https://opentelemetry.io/docs/specs/otel/logs/data-model/#severity-fields
        if severity_number >= 21:  # FATAL
            return 'fatal'
        elif severity_number >= 17:  # ERROR
            return 'error'
        elif severity_number >= 13:  # WARN
            return 'warn'
        elif severity_number >= 9:   # INFO
            return 'info'
        elif severity_number >= 5:   # DEBUG
            return 'debug'
        else:  # TRACE
            return 'trace'

class TextParser(BaseParser):
    """Parser for plain text logs with regex pattern matching"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        
        # Common log patterns
        self.patterns = self.config.get('patterns', {})
        
        # Default patterns for common formats
        if not self.patterns:
            self.patterns = {
                'timestamp_level_message': re.compile(
                    r'(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.,]\d{3})\s+'
                    r'(?P<level>\w+)\s+(?P<message>.*)'
                ),
                'level_timestamp_message': re.compile(
                    r'(?P<level>\w+)\s+(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.,]\d{3})\s+'
                    r'(?P<message>.*)'
                ),
                'java_exception': re.compile(
                    r'(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.,]\d{3})\s+'
                    r'(?P<level>\w+)\s+\[(?P<thread>[^\]]+)\]\s+(?P<logger>\S+)\s+-\s+(?P<message>.*)'
                ),
            }
    
    def parse(self, raw_message: str, **kwargs) -> LogEntry:
        """Parse plain text log message"""
        try:
            # Try each pattern
            for pattern_name, pattern in self.patterns.items():
                match = pattern.match(raw_message)
                if match:
                    fields = match.groupdict()
                    return self._build_log_entry(fields, pattern_name, **kwargs)
            
            # If no pattern matches, use fallback
            return self._parse_fallback(raw_message, **kwargs)
            
        except Exception as e:
            logger.error("Failed to parse text log", error=str(e), raw_message=raw_message[:200])
            raise ParseError(f"Text parse error: {str(e)}")
    
    def _build_log_entry(self, fields: Dict[str, str], pattern_name: str, **kwargs) -> LogEntry:
        """Build LogEntry from parsed fields"""
        timestamp = self.normalize_timestamp(fields.get('timestamp', ''))
        
        attrs = {k: v for k, v in fields.items() if k not in ['timestamp', 'level', 'message']}
        attrs['pattern'] = pattern_name
        
        return LogEntry(
            ts=timestamp,
            host=kwargs.get('host', self.default_host),
            service=kwargs.get('service', fields.get('logger', self.default_service)),
            level=fields.get('level', self.default_level).lower(),
            msg=fields.get('message', raw_message),
            attrs=attrs
        )
    
    def _parse_fallback(self, raw_message: str, **kwargs) -> LogEntry:
        """Fallback parser for unstructured text"""
        # Try to extract log level from message
        level = self.default_level
        level_patterns = {
            'fatal': re.compile(r'\b(fatal|critical|crit)\b', re.IGNORECASE),
            'error': re.compile(r'\b(error|err|exception|fail)\b', re.IGNORECASE),
            'warn': re.compile(r'\b(warn|warning|caution)\b', re.IGNORECASE),
            'info': re.compile(r'\b(info|information)\b', re.IGNORECASE),
            'debug': re.compile(r'\b(debug|trace|verbose)\b', re.IGNORECASE),
        }
        
        for lvl, pattern in level_patterns.items():
            if pattern.search(raw_message):
                level = lvl
                break
        
        return LogEntry(
            ts=datetime.utcnow(),
            host=kwargs.get('host', self.default_host),
            service=kwargs.get('service', self.default_service),
            level=level,
            msg=raw_message,
            attrs={'parser': 'text_fallback'}
        )

# Parser factory
class ParserFactory:
    """Factory for creating log parsers"""
    
    _parsers = {
        'nginx': NginxAccessLogParser,
        'syslog': SyslogParser,
        'cef': CEFParser,
        'json': JSONParser,
        'otlp': OTLPParser,
        'text': TextParser,
    }
    
    @classmethod
    def create_parser(cls, format_type: str, config: Dict[str, Any] = None) -> BaseParser:
        """Create parser for specified format"""
        if format_type not in cls._parsers:
            raise ValueError(f"Unsupported parser format: {format_type}")
        
        return cls._parsers[format_type](config)
    
    def get_parser(self, format_type: str, config: Dict[str, Any] = None) -> BaseParser:
        """Instance method to get parser for specified format"""
        return self.create_parser(format_type, config)
    
    @classmethod
    def get_supported_formats(cls) -> List[str]:
        """Get list of supported parser formats"""
        return list(cls._parsers.keys())
    
    @classmethod
    def register_parser(cls, format_type: str, parser_class: type):
        """Register custom parser"""
        cls._parsers[format_type] = parser_class