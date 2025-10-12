# Logforge Tenant Log Simulation

This directory contains scripts to generate realistic log data for your Logforge tenant.

## 🎯 Overview

**Tenant ID**: `bf084eec-d6ba-427a-a787-98c4d809e54e`  
**Organization**: TestOrg (Technology, Enterprise tier)  
**Target**: 1000+ logs per second simulating real-world enterprise scenarios

## 📁 Files

1. **`test_log_ingestion.py`** - Quick test script to verify all ingestion APIs work
2. **`simulate_tenant_logs.py`** - Full simulation script generating 1000s of logs/sec
3. **`requirements_simulation.txt`** - Python dependencies

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements_simulation.txt
```

### 2. Authentication Setup
The scripts automatically authenticate using:
- **Email**: `testuser@testorg.com`
- **Password**: `TestUser123!`

JWT tokens are automatically managed with refresh capabilities.

### 3. Test API Connection
```bash
python3 test_log_ingestion.py
```
This authenticates and tests all ingestion endpoints with sample data.

### 4. Run Full Simulation
```bash
# Generate 100 logs/sec for 60 seconds
python3 simulate_tenant_logs.py --rate 100 --duration 60

# Generate 1000 logs/sec indefinitely 
python3 simulate_tenant_logs.py --rate 1000

# Custom configuration
python3 simulate_tenant_logs.py --rate 500 --workers 10 --duration 300
```

## 📊 Log Categories Generated

### 1. **Web Application Logs (40%)**
- API endpoint requests (`/api/auth/login`, `/api/orders/create`, etc.)
- HTTP status codes (realistic error rates: 5%)
- Response times (50-300ms normal, 1000-5000ms errors)
- OpenTelemetry trace context
- User sessions and authentication

### 2. **Business Application Logs (15%)**
- Order processing (`order_created`, `payment_processed`)
- Revenue tracking with realistic amounts
- Inventory management
- User activities and notifications
- Email and notification delivery

### 3. **System & Infrastructure Logs (15%)**
- CPU, memory, disk usage metrics
- Network performance
- Service health checks
- Deployment events
- Backup operations

### 4. **Database Logs (15%)**
- SQL operations (SELECT, INSERT, UPDATE, DELETE)
- Query performance (1-100ms range)
- Slow query detection (>100ms)
- Connection pooling
- Transaction management

### 5. **Authentication & Security Logs (15%)**
- Login/logout events
- Failed authentication attempts
- MFA challenges
- Session management
- Suspicious activity detection
- Brute force attack simulation

### 6. **Security & Compliance Logs (5%)**
- Intrusion attempts
- Malware detection
- SQL injection attempts
- MITRE ATT&CK technique mapping
- Compliance audit events
- WAF events

## 🔧 Configuration Options

### Command Line Arguments
```bash
--rate 1000        # Target logs per second (default: 1000)
--workers 20       # Concurrent workers (default: 20)
--duration 0       # Duration in seconds (0 = infinite)
--api-url URL      # Logforge API URL (default: http://localhost:7080)
```

### Script Configuration
Edit variables in `simulate_tenant_logs.py`:
- `BATCH_SIZE = 50` - Logs per batch request
- `TARGET_EPS = 1000` - Default logs per second
- `CONCURRENT_WORKERS = 20` - Default worker threads
- `AUTH_EMAIL` - Login email (default: testuser@testorg.com)
- `AUTH_PASSWORD` - Login password (default: TestUser123!)

## 📈 Performance Characteristics

### Realistic Data Patterns
- **Time-based patterns**: Higher activity during business hours
- **Error spikes**: Occasional 2% chance of error bursts
- **Geographic distribution**: Multi-region IP addresses
- **User behavior**: Realistic session patterns and user IDs
- **Attack simulation**: External IP ranges for security events

### Authentication Features
- **Automatic Login**: Uses testuser@testorg.com credentials
- **JWT Management**: Handles access and refresh tokens automatically  
- **Token Refresh**: Auto-refreshes tokens before expiration (60s buffer)
- **Tenant Detection**: Automatically detects and uses correct tenant ID
- **Error Recovery**: Falls back to re-login if refresh fails

### API Endpoints Used
1. **Auth**: `/v1/auth/login`, `/v1/auth/refresh` (authentication)
2. **Primary**: `/v1/ingest/logs/batch` (batch processing)
3. **Fallback**: `/v1/ingest/logs/bulk` (bulk processing)
4. **Testing**: `/v1/ingest/logs` (single log)

### Generated Data Volume
- **1000 logs/sec** = ~86M logs/day = ~2.6B logs/month
- **Average log size**: ~500-800 bytes
- **Daily data volume**: ~40-70 GB/day
- **Monthly data volume**: ~1.2-2TB/month

## 🏢 Realistic Enterprise Scenarios

### Technology Company (TestOrg)
- **Services**: Web frontend, API gateway, microservices
- **Infrastructure**: Load balancers, databases, caches
- **Security**: WAF, intrusion detection, authentication
- **Business Logic**: Orders, payments, inventory, analytics
- **Compliance**: Audit logs, data access tracking

### Generated Attributes
- **Hosts**: 12 realistic hostnames (`web-01.testorg.com`, etc.)
- **Services**: 16 microservices (auth, orders, payments, etc.)
- **Users**: 10,000 simulated user accounts
- **IPs**: Mixed internal (10.0.x.x, 192.168.x.x) and external
- **Trace IDs**: OpenTelemetry-compatible distributed tracing
- **Business Metrics**: Revenue, conversion rates, performance

## 📊 Monitoring the Simulation

### Real-time Stats (every 10 seconds)
```
📊 Stats: 12,450 logs sent | 249 batches | 0 errors | 
Rate: 1,245.0/s avg, 1,250.0/s current | Data: 8.3MB
```

### Final Statistics
```
📋 Final Statistics:
   Total Logs Sent: 60,000
   Total Batches: 1,200
   Total Errors: 0
   Duration: 60.0 seconds
   Average Rate: 1,000.0 logs/sec
   Data Sent: 45.2 MB
```

## 🎯 Expected Results in Logforge

After running the simulation, you should see:

### Dashboard Metrics
- **Log volume**: Steady stream of incoming logs
- **Service breakdown**: 16 different services
- **Error rates**: ~5% realistic error distribution
- **Response times**: Performance metrics across services

### Real-Time Analytics
- **Live charts**: CPU, memory, response times
- **Geographic data**: Multi-region activity
- **User sessions**: Authentication patterns
- **Business metrics**: Revenue and order tracking

### Security Analytics
- **Failed logins**: Brute force attempts
- **Suspicious IPs**: External attack simulations  
- **MITRE techniques**: Mapped security events
- **Compliance events**: Audit trail generation

### Alert Triggers
Based on your alert rules, expect triggers for:
- High error rates (>10%)
- Slow queries (>100ms)
- Failed authentication attempts
- Security events (intrusion attempts)
- System resource usage (CPU >90%)

## 🔍 Troubleshooting

### Common Issues

1. **Connection Refused**
   ```bash
   # Check if Logforge API is running
   curl http://localhost:7080/health
   ```

2. **Authentication Errors**
   ```bash
   # Verify tenant ID is correct
   X-Customer-ID: bf084eec-d6ba-427a-a787-98c4d809e54e
   ```

3. **Rate Limiting**
   - Reduce `--rate` parameter
   - Increase `--workers` for better distribution
   - Check API logs for throttling

4. **Memory Issues**
   - Reduce `BATCH_SIZE` in script
   - Lower `--workers` count
   - Monitor system resources

### Debug Mode
Add debug logging to the script:
```python
logging.basicConfig(level=logging.DEBUG)
```

## 🎮 Usage Examples

### Development Testing
```bash
# Light load for development
python3 simulate_tenant_logs.py --rate 10 --duration 30
```

### Load Testing  
```bash
# Heavy load testing
python3 simulate_tenant_logs.py --rate 5000 --workers 50 --duration 300
```

### Demo Preparation
```bash
# Continuous realistic load for demos
python3 simulate_tenant_logs.py --rate 200 --duration 3600
```

### Performance Benchmarking
```bash
# Maximum throughput test
python3 simulate_tenant_logs.py --rate 10000 --workers 100 --duration 60
```

---

**🎉 Ready to simulate real-world enterprise log data for Logforge!**

The simulation generates authentic patterns that will showcase all Logforge features including real-time analytics, security detection, compliance reporting, and AI-powered insights.