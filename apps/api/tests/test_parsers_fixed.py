"""
Test cases for log parsers - Fixed version matching actual implementation
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any, List

from parsers import (
    ParserFactory, JSONParser, NginxAccessLogParser, SyslogParser,
    CEFParser, OTLPParser, TextParser, ParseError
)
from models import LogEntry


class TestParserFactory:
    """Test the parser factory"""

    def test_factory_creation(self, parser_factory):
        """Test factory creates parsers correctly"""
        assert isinstance(parser_factory, ParserFactory)

        # Test getting each parser type
        json_parser = parser_factory.get_parser("json")
        assert isinstance(json_parser, JSONParser)

        nginx_parser = parser_factory.get_parser("nginx")
        assert isinstance(nginx_parser, NginxAccessLogParser)

        syslog_parser = parser_factory.get_parser("syslog")
        assert isinstance(syslog_parser, SyslogParser)

        cef_parser = parser_factory.get_parser("cef")
        assert isinstance(cef_parser, CEFParser)

        otlp_parser = parser_factory.get_parser("otlp")
        assert isinstance(otlp_parser, OTLPParser)

        text_parser = parser_factory.get_parser("text")
        assert isinstance(text_parser, TextParser)

    def test_factory_invalid_parser(self, parser_factory):
        """Test factory returns None for invalid parser type"""
        parser = parser_factory.get_parser("invalid_type")
        assert parser is None

    def test_factory_auto_detect(self, parser_factory):
        """Test factory auto-detection"""
        # JSON detection
        json_data = {"level": "info", "message": "test"}
        detected_type = parser_factory.auto_detect(json_data)
        assert detected_type == "json"

        # Nginx log detection
        nginx_log = '192.168.1.1 - - [25/Dec/2023:10:00:00 +0000] "GET / HTTP/1.1" 200 1234'
        detected_type = parser_factory.auto_detect(nginx_log)
        assert detected_type == "nginx"

        # Syslog detection
        syslog_message = "<34>Dec 25 10:00:00 host service: message"
        detected_type = parser_factory.auto_detect(syslog_message)
        assert detected_type == "syslog"


class TestJSONParser:
    """Test JSON log parser"""

    def test_json_parser_basic(self, parser_factory, sample_structured_json):
        """Test basic JSON parsing"""
        parser = parser_factory.get_parser("json")
        result = parser.parse(sample_structured_json)

        assert isinstance(result, LogEntry)
        assert result.level == "info"
        assert result.msg == "User authentication successful"
        assert result.user_id == "user123"
        assert result.trace_id == "trace123"
        assert result.span_id == "span456"

    def test_json_parser_minimal(self, parser_factory):
        """Test JSON parsing with minimal fields"""
        parser = parser_factory.get_parser("json")
        data = {"message": "Simple log message"}

        result = parser.parse(data)
        assert isinstance(result, LogEntry)
        assert result.msg == "Simple log message"
        assert result.level == "info"  # Default

    def test_json_parser_invalid(self, parser_factory):
        """Test JSON parser with invalid data"""
        parser = parser_factory.get_parser("json")

        with pytest.raises(ParseError):
            parser.parse("not a dict")

        with pytest.raises(ParseError):
            parser.parse(None)


class TestNginxParser:
    """Test Nginx access log parser"""

    def test_nginx_parser_basic(self, parser_factory, sample_nginx_log):
        """Test basic Nginx log parsing"""
        parser = parser_factory.get_parser("nginx")
        result = parser.parse(sample_nginx_log)

        assert isinstance(result, LogEntry)
        assert result.src_ip == "192.168.1.100"
        assert result.user_id == "user123"
        assert result.status == 200
        assert "GET" in result.attrs.get("method", "")
        assert "/api/users/123" in result.attrs.get("uri", "")

    def test_nginx_parser_with_timing(self, parser_factory, sample_nginx_log_with_timing):
        """Test Nginx parser with timing information"""
        parser = parser_factory.get_parser("nginx")
        result = parser.parse(sample_nginx_log_with_timing)

        assert isinstance(result, LogEntry)
        assert result.src_ip == "10.0.0.1"
        assert result.status == 201
        assert "response_time" in result.attrs

    def test_nginx_parser_invalid(self, parser_factory):
        """Test Nginx parser with invalid log format"""
        parser = parser_factory.get_parser("nginx")

        with pytest.raises(ParseError):
            parser.parse("Not a valid nginx log format")


class TestSyslogParser:
    """Test Syslog parser"""

    def test_syslog_parser_rfc3164(self, parser_factory, sample_syslog_rfc3164):
        """Test RFC 3164 syslog parsing"""
        parser = parser_factory.get_parser("syslog")
        result = parser.parse(sample_syslog_rfc3164)

        assert isinstance(result, LogEntry)
        assert result.host == "web-server"
        assert "nginx" in result.service.lower()
        assert "192.168.1.100" in result.msg

    def test_syslog_parser_rfc5424(self, parser_factory, sample_syslog_rfc5424):
        """Test RFC 5424 syslog parsing"""
        parser = parser_factory.get_parser("syslog")
        result = parser.parse(sample_syslog_rfc5424)

        assert isinstance(result, LogEntry)
        assert "web-server.example.com" in result.host
        assert result.service == "nginx"
        assert "Request processed successfully" in result.msg

    def test_syslog_parser_invalid_priority(self, parser_factory):
        """Test syslog parser with invalid priority"""
        parser = parser_factory.get_parser("syslog")

        with pytest.raises(ParseError):
            parser.parse("<999999>Invalid priority message")


class TestCEFParser:
    """Test CEF (Common Event Format) parser"""

    def test_cef_parser_basic(self, parser_factory, sample_cef_log):
        """Test basic CEF parsing"""
        parser = parser_factory.get_parser("cef")
        result = parser.parse(sample_cef_log)

        assert isinstance(result, LogEntry)
        assert result.level == "medium"  # CEF severity 5 maps to medium
        assert "Attempted Login" in result.msg
        assert result.src_ip == "192.168.1.100"
        assert "admin" in result.attrs.get("suser", "")

    def test_cef_parser_invalid_format(self, parser_factory):
        """Test CEF parser with invalid format"""
        parser = parser_factory.get_parser("cef")

        with pytest.raises(ParseError):
            parser.parse("CEF:INVALID|FORMAT")


class TestOTLPParser:
    """Test OpenTelemetry Logs parser"""

    def test_otlp_parser_basic(self, parser_factory, sample_otlp_data):
        """Test basic OTLP parsing"""
        parser = parser_factory.get_parser("otlp")
        results = parser.parse(sample_otlp_data)

        # OTLP parser returns a list of LogEntry objects
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

    def test_otlp_parser_empty(self, parser_factory):
        """Test OTLP parser with empty data"""
        parser = parser_factory.get_parser("otlp")
        data = {"resource_logs": []}

        results = parser.parse(data)
        assert isinstance(results, list)
        assert len(results) == 0


class TestTextParser:
    """Test plain text parser"""

    def test_text_parser_structured(self, parser_factory):
        """Test text parser with structured log"""
        parser = parser_factory.get_parser("text")
        text = "2023-12-25 10:00:00.123 INFO  [main] UserService - User login successful"

        result = parser.parse(text)
        assert isinstance(result, LogEntry)
        assert result.level == "info"
        assert "User login successful" in result.msg
        assert result.service == "UserService"

    def test_text_parser_simple(self, parser_factory):
        """Test text parser with simple log"""
        parser = parser_factory.get_parser("text")
        text = "INFO: Application started successfully"

        result = parser.parse(text)
        assert isinstance(result, LogEntry)
        assert result.level == "info"
        assert "Application started successfully" in result.msg

    def test_text_parser_unstructured(self, parser_factory):
        """Test text parser with unstructured text"""
        parser = parser_factory.get_parser("text")
        text = "Some random log message without clear structure"

        result = parser.parse(text)
        assert isinstance(result, LogEntry)
        assert result.msg == text
        assert result.level == "info"  # Default level


class TestParserPerformance:
    """Test parser performance"""

    @pytest.mark.parametrize("format_type,data_fixture", [
        ("json", "sample_structured_json"),
        ("nginx", "sample_nginx_log"),
        ("syslog", "sample_syslog_rfc3164"),
        ("cef", "sample_cef_log")
    ])
    def test_parser_throughput(self, parser_factory, format_type, data_fixture, request):
        """Test parser throughput - basic performance check"""
        import time

        parser = parser_factory.get_parser(format_type)
        test_data = request.getfixturevalue(data_fixture)

        # Warm up
        for _ in range(100):
            parser.parse(test_data)

        # Benchmark
        iterations = 1000
        start_time = time.time()

        for _ in range(iterations):
            result = parser.parse(test_data)
            assert result is not None

        elapsed = time.time() - start_time
        throughput = iterations / elapsed

        # Basic performance check - should be able to parse at least 500 logs/sec
        assert throughput > 500, f"{format_type} parser throughput: {throughput:.0f} logs/sec (target: >500)"

    def test_concurrent_parsing(self, parser_factory, sample_structured_json):
        """Test concurrent parsing performance"""
        import concurrent.futures
        import time

        parser = parser_factory.get_parser("json")

        def parse_batch(iterations):
            results = []
            for _ in range(iterations):
                result = parser.parse(sample_structured_json)
                results.append(result)
            return results

        iterations_per_thread = 100
        num_threads = 4

        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(parse_batch, iterations_per_thread) for _ in range(num_threads)]
            results = [future.result() for future in futures]

        elapsed = time.time() - start_time
        total_parsed = num_threads * iterations_per_thread
        throughput = total_parsed / elapsed

        # Should maintain reasonable performance under concurrency
        assert throughput > 1000, f"Concurrent parsing throughput: {throughput:.0f} logs/sec"
        assert all(len(result) == iterations_per_thread for result in results)


class TestParserErrorHandling:
    """Test parser error handling"""

    def test_parser_none_input(self, parser_factory):
        """Test parsers handle None input gracefully"""
        parsers = ["json", "nginx", "syslog", "cef", "text"]

        for parser_type in parsers:
            parser = parser_factory.get_parser(parser_type)
            with pytest.raises((ParseError, TypeError, ValueError)):
                parser.parse(None)

    def test_parser_empty_input(self, parser_factory):
        """Test parsers handle empty input"""
        parsers = ["nginx", "syslog", "cef", "text"]

        for parser_type in parsers:
            parser = parser_factory.get_parser(parser_type)
            with pytest.raises((ParseError, ValueError)):
                parser.parse("")

    def test_parser_malformed_input(self, parser_factory, malformed_logs):
        """Test parsers handle malformed input appropriately"""
        test_cases = [
            ("nginx", malformed_logs["malformed_nginx"]),
            ("syslog", malformed_logs["invalid_syslog"]),
            ("cef", malformed_logs["invalid_cef"])
        ]

        for parser_type, bad_data in test_cases:
            parser = parser_factory.get_parser(parser_type)
            with pytest.raises(ParseError):
                parser.parse(bad_data)
