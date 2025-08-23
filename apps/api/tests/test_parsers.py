"""
Test cases for log parsers
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any, List

from parsers import (
    ParserFactory, JSONParser, NginxParser, SyslogParser, 
    CEFParser, OTLPParser, TextParser, ParseError
)
from models import LogEntry


class TestParserFactory:
    """Test the parser factory"""
    
    def test_factory_creation(self, parser_factory):
        """Test factory creates parsers correctly"""
        json_parser = parser_factory.get_parser('json')
        assert isinstance(json_parser, JSONParser)
        
        nginx_parser = parser_factory.get_parser('nginx')
        assert isinstance(nginx_parser, NginxParser)
        
        syslog_parser = parser_factory.get_parser('syslog')
        assert isinstance(syslog_parser, SyslogParser)
        
        cef_parser = parser_factory.get_parser('cef')
        assert isinstance(cef_parser, CEFParser)
        
        otlp_parser = parser_factory.get_parser('otlp')
        assert isinstance(otlp_parser, OTLPParser)
        
        text_parser = parser_factory.get_parser('text')
        assert isinstance(text_parser, TextParser)
    
    def test_factory_invalid_format(self, parser_factory):
        """Test factory raises error for invalid format"""
        with pytest.raises(ValueError, match="Unknown parser format"):
            parser_factory.get_parser('unknown')
    
    def test_factory_register_parser(self, parser_factory):
        """Test registering custom parser"""
        custom_parser = JSONParser()
        parser_factory.register_parser('custom', custom_parser)
        
        result = parser_factory.get_parser('custom')
        assert result is custom_parser


class TestJSONParser:
    """Test JSON log parser"""
    
    def test_parse_structured_json(self, sample_structured_json):
        """Test parsing structured application log"""
        parser = JSONParser()
        result = parser.parse(sample_structured_json)
        
        assert isinstance(result, LogEntry)
        assert result.level == "info"
        assert result.msg == "User authentication successful"
        assert result.service is None  # Not explicitly set
        assert result.trace_id == "trace123"
        assert result.span_id == "span456"
        assert result.attrs["user_id"] == "user123"
        assert result.attrs["http_status_code"] == 200
    
    def test_parse_json_string(self):
        """Test parsing JSON string"""
        parser = JSONParser()
        json_str = '{"level": "error", "message": "Database error", "timestamp": "2023-12-25T10:00:00Z"}'
        
        result = parser.parse(json_str)
        assert result.level == "error"
        assert result.msg == "Database error"
    
    def test_parse_invalid_json(self):
        """Test parsing invalid JSON"""
        parser = JSONParser()
        with pytest.raises(ParseError, match="Invalid JSON"):
            parser.parse('{"invalid": json')
    
    def test_parse_empty_json(self):
        """Test parsing empty JSON object"""
        parser = JSONParser()
        result = parser.parse({})
        
        assert isinstance(result, LogEntry)
        assert result.msg == ""
        assert result.level == "info"  # Default level


class TestNginxParser:
    """Test Nginx log parser"""
    
    def test_parse_nginx_access_log(self, sample_nginx_log):
        """Test parsing standard Nginx access log"""
        parser = NginxParser()
        result = parser.parse(sample_nginx_log)
        
        assert isinstance(result, LogEntry)
        assert result.src_ip == "192.168.1.100"
        assert result.user_id == "user123"
        assert result.status == 200
        assert result.attrs["method"] == "GET"
        assert result.attrs["uri"] == "/api/users/123"
        assert result.attrs["bytes_sent"] == 1234
        assert result.attrs["referer"] == "http://example.com/referrer"
        assert result.attrs["user_agent"] == "Mozilla/5.0 (compatible; test)"
    
    def test_parse_nginx_with_timing(self, sample_nginx_log_with_timing):
        """Test parsing Nginx log with timing"""
        parser = NginxParser()
        result = parser.parse(sample_nginx_log_with_timing)
        
        assert result.src_ip == "10.0.0.1"
        assert result.status == 201
        assert result.attrs["method"] == "POST"
        assert result.attrs["request_time"] == 0.042
        assert result.attrs["upstream_response_time"] == 0.041
    
    def test_parse_nginx_json_format(self, sample_nginx_json_log):
        """Test parsing Nginx JSON format"""
        parser = NginxParser()
        result = parser.parse(sample_nginx_json_log)
        
        assert result.src_ip == "203.0.113.1"
        assert result.status == 200
        assert result.attrs["method"] == "GET"
        assert result.attrs["request_time"] == 0.003
    
    def test_parse_invalid_nginx_log(self, malformed_logs):
        """Test parsing invalid Nginx log"""
        parser = NginxParser()
        with pytest.raises(ParseError, match="Failed to parse Nginx log"):
            parser.parse(malformed_logs["malformed_nginx"])


class TestSyslogParser:
    """Test Syslog parser"""
    
    def test_parse_rfc3164_syslog(self, sample_syslog_rfc3164):
        """Test parsing RFC 3164 syslog message"""
        parser = SyslogParser()
        result = parser.parse(sample_syslog_rfc3164)
        
        assert isinstance(result, LogEntry)
        assert result.host == "web-server"
        assert result.service == "nginx"
        assert result.level == "info"  # Priority 34 = info
        assert "192.168.1.100 - GET /api/users HTTP/1.1" in result.msg
    
    def test_parse_rfc5424_syslog(self, sample_syslog_rfc5424):
        """Test parsing RFC 5424 syslog message"""
        parser = SyslogParser()
        result = parser.parse(sample_syslog_rfc5424)
        
        assert result.host == "web-server.example.com"
        assert result.service == "nginx"
        assert result.level == "notice"  # Priority 165
        assert result.attrs["structured_data"]["exampleSDID@32473"]["iut"] == "3"
        assert "Request processed successfully" in result.msg
    
    def test_parse_invalid_syslog(self, malformed_logs):
        """Test parsing invalid syslog"""
        parser = SyslogParser()
        with pytest.raises(ParseError, match="Failed to parse syslog message"):
            parser.parse(malformed_logs["invalid_syslog"])
    
    def test_syslog_priority_mapping(self):
        """Test syslog priority to level mapping"""
        parser = SyslogParser()
        
        # Test various priority levels
        test_cases = [
            ("<0>", "emergency"),
            ("<8>", "emergency"),  # Kernel emergency
            ("<16>", "info"),      # Mail info
            ("<24>", "info"),      # Mail info
            ("<165>", "notice"),   # Local4 notice
        ]
        
        for priority_str, expected_level in test_cases:
            log_msg = f"{priority_str}Dec 25 10:00:00 host service: test message"
            result = parser.parse(log_msg)
            assert result.level == expected_level


class TestCEFParser:
    """Test CEF (Common Event Format) parser"""
    
    def test_parse_cef_log(self, sample_cef_log):
        """Test parsing CEF log"""
        parser = CEFParser()
        result = parser.parse(sample_cef_log)
        
        assert isinstance(result, LogEntry)
        assert result.service == "IDS"
        assert result.level == "medium"  # Severity 5
        assert result.src_ip == "192.168.1.100"
        assert result.attrs["dst"] == "10.0.0.1"
        assert result.attrs["spt"] == "1234"
        assert result.attrs["dpt"] == "22"
        assert result.attrs["suser"] == "admin"
        assert "SSH login attempt detected" in result.msg
    
    def test_parse_invalid_cef(self, malformed_logs):
        """Test parsing invalid CEF"""
        parser = CEFParser()
        with pytest.raises(ParseError, match="Invalid CEF format"):
            parser.parse(malformed_logs["invalid_cef"])
    
    def test_cef_severity_mapping(self):
        """Test CEF severity to level mapping"""
        parser = CEFParser()
        
        test_cases = [
            ("CEF:0|Vendor|Product|1.0|100|Event|0|msg=Low severity", "info"),
            ("CEF:0|Vendor|Product|1.0|100|Event|3|msg=Low severity", "info"),
            ("CEF:0|Vendor|Product|1.0|100|Event|6|msg=Medium severity", "medium"),
            ("CEF:0|Vendor|Product|1.0|100|Event|8|msg=High severity", "high"),
            ("CEF:0|Vendor|Product|1.0|100|Event|10|msg=Very High severity", "critical"),
        ]
        
        for cef_log, expected_level in test_cases:
            result = parser.parse(cef_log)
            assert result.level == expected_level


class TestOTLPParser:
    """Test OTLP (OpenTelemetry) parser"""
    
    def test_parse_otlp_data(self, sample_otlp_data):
        """Test parsing OTLP logs data"""
        parser = OTLPParser()
        results = parser.parse(sample_otlp_data)
        
        assert isinstance(results, list)
        assert len(results) == 1
        
        log_entry = results[0]
        assert isinstance(log_entry, LogEntry)
        assert log_entry.service == "user-service"
        assert log_entry.host == "web-server-01"
        assert log_entry.level == "info"
        assert log_entry.msg == "User login successful"
        assert log_entry.trace_id == "0123456789abcdef0123456789abcdef"
        assert log_entry.span_id == "0123456789abcdef"
        assert log_entry.attrs["user.id"] == "user123"
        assert log_entry.attrs["http.method"] == "POST"
        assert log_entry.attrs["http.status_code"] == 200
    
    def test_parse_empty_otlp_data(self):
        """Test parsing empty OTLP data"""
        parser = OTLPParser()
        result = parser.parse({"resource_logs": []})
        
        assert result == []
    
    def test_parse_invalid_otlp_structure(self):
        """Test parsing invalid OTLP structure"""
        parser = OTLPParser()
        with pytest.raises(ParseError, match="Invalid OTLP structure"):
            parser.parse({"invalid": "structure"})


class TestTextParser:
    """Test plain text parser"""
    
    def test_parse_text_logs(self, sample_text_logs):
        """Test parsing various text log formats"""
        parser = TextParser()
        
        for log_text in sample_text_logs:
            result = parser.parse(log_text)
            assert isinstance(result, LogEntry)
            assert result.msg == log_text.strip()
            assert result.level == "info"  # Default level
    
    def test_parse_structured_text_with_level(self):
        """Test parsing text with detectable log level"""
        parser = TextParser()
        
        test_cases = [
            ("ERROR: Database connection failed", "error"),
            ("WARN: Memory usage high", "warn"),
            ("DEBUG: Processing request", "debug"),
            ("INFO: Service started", "info"),
            ("FATAL: System crash", "critical"),
        ]
        
        for log_text, expected_level in test_cases:
            result = parser.parse(log_text)
            assert result.level == expected_level
    
    def test_parse_empty_text(self, malformed_logs):
        """Test parsing empty text"""
        parser = TextParser()
        result = parser.parse(malformed_logs["empty_message"])
        
        assert result.msg == ""
        assert result.level == "info"
    
    def test_parse_oversized_text(self, malformed_logs):
        """Test parsing oversized text message"""
        parser = TextParser()
        result = parser.parse(malformed_logs["oversized_message"])
        
        # Should truncate or handle large messages gracefully
        assert isinstance(result, LogEntry)
        assert len(result.msg) <= 100000  # Should be truncated or handled


class TestParserPerformance:
    """Performance tests for parsers"""
    
    @pytest.mark.parametrize("parser_type,sample_data", [
        ("json", "sample_structured_json"),
        ("nginx", "sample_nginx_log"),
        ("syslog", "sample_syslog_rfc3164"),
        ("cef", "sample_cef_log"),
    ])
    def test_parser_performance_single(self, parser_factory, parser_type, sample_data, request):
        """Test single log parsing performance"""
        parser = parser_factory.get_parser(parser_type)
        data = request.getfixturevalue(sample_data)
        
        import time
        start_time = time.time()
        
        # Parse same log 1000 times
        for _ in range(1000):
            result = parser.parse(data)
            assert isinstance(result, (LogEntry, list))
        
        elapsed = time.time() - start_time
        # Should parse 1000 logs in under 1 second
        assert elapsed < 1.0, f"Parser {parser_type} too slow: {elapsed}s for 1000 parses"
    
    def test_batch_parsing_performance(self, parser_factory, performance_log_batch):
        """Test batch parsing performance"""
        parser = parser_factory.get_parser("json")
        
        import time
        start_time = time.time()
        
        results = []
        for log_data in performance_log_batch:
            result = parser.parse(log_data)
            results.append(result)
        
        elapsed = time.time() - start_time
        throughput = len(performance_log_batch) / elapsed
        
        # Should achieve at least 1000 logs/second parsing
        assert throughput > 1000, f"Batch parsing too slow: {throughput} logs/sec"
        assert len(results) == len(performance_log_batch)


class TestParserErrorHandling:
    """Test error handling across all parsers"""
    
    @pytest.mark.parametrize("parser_type", ["json", "nginx", "syslog", "cef", "otlp", "text"])
    def test_parser_handles_none_input(self, parser_factory, parser_type):
        """Test all parsers handle None input gracefully"""
        parser = parser_factory.get_parser(parser_type)
        
        with pytest.raises((ParseError, ValueError, TypeError)):
            parser.parse(None)
    
    @pytest.mark.parametrize("parser_type", ["json", "nginx", "syslog", "cef", "text"])
    def test_parser_handles_empty_string(self, parser_factory, parser_type):
        """Test parsers handle empty string input"""
        parser = parser_factory.get_parser(parser_type)
        
        # Most parsers should either parse empty string or raise ParseError
        try:
            result = parser.parse("")
            if isinstance(result, LogEntry):
                assert result.msg == ""
        except ParseError:
            # This is also acceptable behavior
            pass
    
    def test_all_parsers_return_consistent_types(self, parser_factory, sample_structured_json, 
                                                sample_nginx_log, sample_syslog_rfc3164, 
                                                sample_cef_log, sample_otlp_data):
        """Test all parsers return consistent LogEntry types"""
        test_cases = [
            ("json", sample_structured_json),
            ("nginx", sample_nginx_log),
            ("syslog", sample_syslog_rfc3164),
            ("cef", sample_cef_log),
            ("text", "Simple text log message"),
        ]
        
        for parser_type, sample_data in test_cases:
            parser = parser_factory.get_parser(parser_type)
            result = parser.parse(sample_data)
            
            if isinstance(result, list):
                # OTLP parser returns list
                assert all(isinstance(entry, LogEntry) for entry in result)
            else:
                assert isinstance(result, LogEntry)
        
        # OTLP is special case that returns list
        otlp_parser = parser_factory.get_parser("otlp")
        otlp_result = otlp_parser.parse(sample_otlp_data)
        assert isinstance(otlp_result, list)
        assert all(isinstance(entry, LogEntry) for entry in otlp_result)