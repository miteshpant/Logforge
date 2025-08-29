# Logforge API Test Suite

This directory contains comprehensive tests for the Logforge API, covering unit tests, integration tests, and performance benchmarks.

## Test Structure

### Core Test Files

- **`test_parsers.py`** - Unit tests for log parsers (JSON, Nginx, Syslog, CEF, OTLP, Text)
- **`test_models.py`** - Unit tests for Pydantic data models and validation
- **`test_api.py`** - Unit tests for FastAPI endpoints and HTTP handlers
- **`test_storage_config.py`** - Unit tests for multi-cloud storage configuration
- **`test_integration.py`** - End-to-end integration tests for the complete pipeline
- **`test_performance.py`** - Performance benchmarks and scalability tests

### Test Configuration

- **`conftest.py`** - Pytest configuration and shared fixtures
- **`__init__.py`** - Test package initialization

## Running Tests

### Quick Start

```bash
# Run all tests
python run_tests.py

# Run specific test suite
python run_tests.py --suite unit
python run_tests.py --suite integration  
python run_tests.py --suite performance

# Run with coverage
python run_tests.py --coverage

# Run in parallel
python run_tests.py --parallel

# Filter tests
python run_tests.py --filter "test_json"
```

### Direct pytest Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run specific file
pytest tests/test_parsers.py

# Run with coverage
pytest --cov=. --cov-report=html

# Run performance tests
pytest tests/test_performance.py -v

# Run with markers
pytest -m "not slow"
```

## Test Categories

### Unit Tests (Fast)

**Parser Tests (`test_parsers.py`)**
- JSON log parsing with various structures
- Nginx access log parsing (standard and JSON formats)
- Syslog parsing (RFC 3164 and RFC 5424)
- CEF (Common Event Format) parsing
- OTLP (OpenTelemetry) log parsing
- Plain text log parsing with level detection
- Error handling and malformed input testing
- Performance benchmarks for each parser

**Model Tests (`test_models.py`)**
- LogEntry validation and serialization
- BatchLogEntry handling
- OTLP data structure validation
- Query request/response models
- Storage configuration models
- Customer configuration models
- Performance tests for serialization

**API Tests (`test_api.py`)**
- Health endpoint testing
- All ingestion endpoints (`/v1/ingest/*`)
- Query endpoint with various parameters
- Error handling and validation
- Security headers and CORS
- API documentation endpoints
- Concurrent request handling

**Storage Config Tests (`test_storage_config.py`)**
- Multi-cloud client creation (S3, GCS, Azure, MinIO)
- Customer configuration loading
- ClickHouse storage policy generation
- Client caching and performance
- Credential handling and validation

### Integration Tests (Medium)

**End-to-End Pipeline Tests (`test_integration.py`)**
- Complete log ingestion → storage → query pipeline
- Multi-format batch processing
- Auto-format detection
- Storage backend integration
- Data consistency validation
- Unicode and special character handling
- Error propagation across components

### Performance Tests (Slow)

**Benchmark Tests (`test_performance.py`)**
- Parser throughput (target: >10k logs/sec per parser)
- API latency (target: P99 <50ms ingestion, <200ms query)
- Concurrent processing (target: >2k req/sec)
- Memory efficiency (target: <2KB per LogEntry)
- Sustained load testing
- Burst traffic simulation
- Resource usage monitoring

## Performance Targets

### Parser Performance
- **JSON Parser**: >10,000 logs/sec
- **Nginx Parser**: >10,000 logs/sec
- **Syslog Parser**: >10,000 logs/sec
- **CEF Parser**: >10,000 logs/sec
- **Text Parser**: >10,000 logs/sec
- **Concurrent Parsing**: >15,000 logs/sec (10 threads)

### API Performance
- **Ingestion Latency**: P50 <10ms, P95 <25ms, P99 <50ms
- **Query Latency**: P50 <50ms, P95 <100ms, P99 <200ms
- **Concurrent Throughput**: >2,000 requests/sec
- **Async Throughput**: >5,000 requests/sec

### Memory Performance
- **Parser Memory**: <50MB growth for 50k log parsing
- **LogEntry Memory**: <2KB per instance
- **API Memory**: <50MB growth under sustained load

### Storage Performance
- **Client Creation**: >500 clients/sec
- **Policy Generation**: >5,000 policies/sec

## Test Data and Fixtures

### Sample Log Formats

The test suite includes comprehensive sample data for all supported log formats:

- **JSON Logs**: Structured application logs with various field combinations
- **Nginx Logs**: Access logs in both standard and JSON formats, with timing data
- **Syslog Messages**: RFC 3164 and RFC 5424 format messages
- **CEF Logs**: Common Event Format security logs
- **OTLP Data**: OpenTelemetry logs data structures
- **Plain Text**: Various text log formats with level detection

### Error Test Cases

- Malformed JSON, Nginx, Syslog, and CEF logs
- Invalid timestamps and field values
- Oversized messages (100KB+)
- Unicode and special characters
- Empty and null inputs

### Performance Test Data

- Synthetic log batches (100, 1000, 10000 logs)
- Concurrent request generators
- Memory usage monitors
- Throughput measurement tools

## Continuous Integration

### Test Execution Order

1. **Unit Tests** - Fast feedback on core functionality
2. **Integration Tests** - Verify component interactions
3. **Performance Tests** - Ensure scalability requirements

### Coverage Requirements

- **Minimum Coverage**: 85% overall
- **Critical Components**: 95% coverage
  - Parsers
  - API endpoints
  - Storage configuration
  - Data models

### Test Markers

- `@pytest.mark.unit` - Unit tests (fast)
- `@pytest.mark.integration` - Integration tests (medium)
- `@pytest.mark.performance` - Performance tests (slow)
- `@pytest.mark.benchmark` - Benchmark tests (very slow)

## Debugging Tests

### Running Individual Tests

```bash
# Run specific test
pytest tests/test_parsers.py::TestJSONParser::test_parse_structured_json -v

# Run with pdb debugger
pytest tests/test_api.py::TestLogIngestionEndpoints::test_ingest_logs_json --pdb

# Run with print statements
pytest tests/test_integration.py -s
```

### Test Isolation

Each test is designed to be independent:
- Mock external dependencies (ClickHouse, S3, etc.)
- Clean up resources after each test
- Use fresh instances for mutable objects
- Deterministic test data

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed
2. **Mock Failures**: Verify mock patches match actual function signatures
3. **Timing Issues**: Use appropriate timeouts for async tests
4. **Resource Leaks**: Check for unclosed clients or connections

## Contributing

### Adding New Tests

1. **Unit Tests**: Add to appropriate test file (`test_*.py`)
2. **Integration Tests**: Add to `test_integration.py`
3. **Performance Tests**: Add to `test_performance.py`
4. **Fixtures**: Add to `conftest.py` if reusable

### Test Naming Conventions

- Test files: `test_<component>.py`
- Test classes: `TestComponentName`
- Test methods: `test_<specific_behavior>`
- Fixtures: `<descriptive_name>` (no test_ prefix)

### Performance Test Guidelines

- Include performance targets in assertions
- Use appropriate sample sizes (1k+ for throughput tests)
- Warm up before measurements
- Test both single-threaded and concurrent scenarios
- Monitor memory usage for long-running tests

## Test Environment

### Dependencies

All test dependencies are listed in `requirements.txt`:
- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Enhanced mocking
- `httpx` - Async HTTP client for API tests
- `faker` - Test data generation

### Docker Testing

```bash
# Run tests in Docker container
docker run --rm -v $(pwd):/app -w /app python:3.11 bash -c "
    pip install -r requirements.txt && 
    python run_tests.py --suite all --coverage
"
```

### CI/CD Integration

The test suite is designed to integrate with CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run Tests
  run: |
    pip install -r requirements.txt
    python run_tests.py --suite all --coverage --parallel
    
- name: Upload Coverage
  uses: codecov/codecov-action@v1
  with:
    file: ./coverage.xml
```