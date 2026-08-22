#!/usr/bin/env python3
"""
Logforge Tenant Log Simulation Script
=====================================

Generates realistic log data for tenant: bf084eec-d6ba-427a-a787-98c4d809e54e
Simulates a real-world enterprise environment with:
- Web application logs (APIs, authentication, errors)
- Security events (failed logins, suspicious activity)
- Infrastructure logs (system metrics, database operations)
- Business application logs (orders, payments, user activity)
- Compliance and audit logs

Target: 1000+ logs per second across multiple formats
Environment: Technology company (TestOrg) - Enterprise tier
"""

import asyncio
import aiohttp
import json
import random
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import uuid
import logging
from dataclasses import dataclass
import argparse
import sys
import base64

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
LOGFORGE_API_BASE = "http://localhost:7080"
TENANT_ID = "832f393c-d9de-4a80-a183-aa913ad27266"
TARGET_EPS = 1000  # Events per second
BATCH_SIZE = 50    # Logs per batch request
CONCURRENT_WORKERS = 20  # Parallel workers

# Authentication
AUTH_EMAIL = "shrutipande14@gmail.com"
AUTH_PASSWORD = "I^f^1pkUXSoKcQ9g"

@dataclass
class SimulationMetrics:
    """Track simulation performance"""
    total_logs_sent: int = 0
    total_batches_sent: int = 0
    total_errors: int = 0
    start_time: float = 0
    bytes_sent: int = 0

metrics = SimulationMetrics()

class AuthManager:
    """Manages JWT authentication with auto-refresh"""

    def __init__(self, base_url: str, email: str, password: str):
        self.base_url = base_url
        self.email = email
        self.password = password
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.expires_at: Optional[datetime] = None
        self.tenant_id: Optional[str] = None
        self._auth_lock = asyncio.Lock()

    def _decode_jwt_payload(self, token: str) -> Dict[str, Any]:
        """Decode JWT payload to get expiration time"""
        try:
            # JWT format: header.payload.signature
            parts = token.split('.')
            if len(parts) != 3:
                return {}

            # Decode payload (base64url)
            payload = parts[1]
            # Add padding if needed
            payload += '=' * (4 - len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload)
            return json.loads(decoded)
        except Exception as e:
            logger.warning(f"Failed to decode JWT: {e}")
            return {}

    def _get_token_expiry(self, token: str) -> Optional[datetime]:
        """Get token expiration time"""
        payload = self._decode_jwt_payload(token)
        exp = payload.get('exp')
        if exp:
            return datetime.fromtimestamp(exp, tz=timezone.utc)
        return None

    def _is_token_expired(self) -> bool:
        """Check if current token is expired or will expire soon (within 60 seconds)"""
        if not self.access_token or not self.expires_at:
            return True

        # Consider token expired if it expires in the next 60 seconds
        buffer_time = timedelta(seconds=60)
        return datetime.now(timezone.utc) + buffer_time >= self.expires_at

    async def login(self, session: aiohttp.ClientSession) -> bool:
        """Perform initial login"""
        try:
            login_data = {
                "email": self.email,
                "password": self.password,
                "remember_me": True
            }

            async with session.post(
                f"{self.base_url}/v1/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.access_token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token")

                    # Get expiration time from token
                    if self.access_token:
                        self.expires_at = self._get_token_expiry(self.access_token)

                    # Extract tenant ID from JWT token payload
                    if self.access_token:
                        payload = self._decode_jwt_payload(self.access_token)

                        # Try different possible field names for tenant ID
                        self.tenant_id = (
                            payload.get("tenant_id") or
                            payload.get("customer_id") or
                            payload.get("sub")  # Sometimes subject contains tenant info
                        )

                        # Also check if it's in the response data
                        if not self.tenant_id:
                            tenant = data.get("tenant", {})
                            self.tenant_id = tenant.get("id")

                        # As a fallback, use the default tenant ID
                        if not self.tenant_id:
                            self.tenant_id = TENANT_ID
                            logger.warning(f"Could not extract tenant ID from JWT payload: {list(payload.keys())}")
                            logger.warning(f"Using default tenant ID: {TENANT_ID}")
                    else:
                        self.tenant_id = TENANT_ID

                    logger.info(f"✅ Login successful for {self.email}")
                    logger.info(f"🏢 Tenant ID: {self.tenant_id}")
                    logger.info(f"⏰ Token expires: {self.expires_at}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Login failed: {response.status} - {error_text}")
                    return False

        except Exception as e:
            logger.error(f"❌ Login error: {e}")
            return False

    async def refresh_access_token(self, session: aiohttp.ClientSession) -> bool:
        """Refresh the access token using refresh token"""
        if not self.refresh_token:
            logger.warning("No refresh token available, need to login again")
            return await self.login(session)

        try:
            headers = {
                "Authorization": f"Bearer {self.refresh_token}",
                "Content-Type": "application/json"
            }

            async with session.post(
                f"{self.base_url}/v1/auth/refresh",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.access_token = data.get("access_token")
                    new_refresh = data.get("refresh_token")
                    if new_refresh:
                        self.refresh_token = new_refresh

                    # Get new expiration time
                    if self.access_token:
                        self.expires_at = self._get_token_expiry(self.access_token)

                    logger.info(f"🔄 Token refreshed successfully")
                    logger.info(f"⏰ New expiration: {self.expires_at}")
                    return True
                else:
                    error_text = await response.text()
                    logger.warning(f"Refresh failed: {response.status} - {error_text}")
                    # If refresh fails, try login again
                    return await self.login(session)

        except Exception as e:
            logger.error(f"Refresh error: {e}")
            # If refresh fails, try login again
            return await self.login(session)

    async def get_valid_token(self, session: aiohttp.ClientSession) -> Optional[str]:
        """Get a valid access token, refreshing if necessary"""
        async with self._auth_lock:
            if self._is_token_expired():
                logger.info("🔄 Token expired or missing, refreshing...")
                if not await self.refresh_access_token(session):
                    logger.error("❌ Failed to get valid token")
                    return None

            return self.access_token

    def get_auth_headers(self) -> Dict[str, str]:
        """Get headers with current access token"""
        headers = {
            "Content-Type": "application/json",
            "X-Customer-ID": self.tenant_id or TENANT_ID
        }

        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        return headers

class LogGenerator:
    """Generates realistic log data across different categories"""

    def __init__(self):
        self.user_ids = [f"user_{i:06d}" for i in range(1, 10001)]  # 10k users
        self.session_ids = [str(uuid.uuid4()) for _ in range(5000)]  # 5k sessions
        self.api_endpoints = [
            "/api/auth/login", "/api/auth/logout", "/api/auth/refresh",
            "/api/users/profile", "/api/users/settings", "/api/users/preferences",
            "/api/orders/create", "/api/orders/list", "/api/orders/cancel",
            "/api/payments/process", "/api/payments/refund", "/api/payments/status",
            "/api/inventory/check", "/api/inventory/update", "/api/inventory/reserve",
            "/api/analytics/track", "/api/analytics/report", "/api/analytics/dashboard",
            "/api/admin/users", "/api/admin/reports", "/api/admin/settings",
            "/api/integrations/webhook", "/api/integrations/sync", "/api/integrations/status"
        ]
        self.services = [
            "web-frontend", "api-gateway", "auth-service", "user-service",
            "order-service", "payment-service", "inventory-service", "notification-service",
            "analytics-service", "admin-service", "integration-service", "database-proxy",
            "cache-service", "search-service", "file-service", "backup-service"
        ]
        self.hosts = [
            "web-01.testorg.com", "web-02.testorg.com", "web-03.testorg.com",
            "api-01.testorg.com", "api-02.testorg.com", "api-03.testorg.com",
            "db-01.testorg.com", "db-02.testorg.com", "cache-01.testorg.com",
            "worker-01.testorg.com", "worker-02.testorg.com", "lb-01.testorg.com"
        ]
        self.ip_ranges = [
            "10.0.1.", "10.0.2.", "10.0.3.", "192.168.1.", "192.168.2.",
            "172.16.1.", "172.16.2.", "203.0.113.", "198.51.100."
        ]
        self.countries = ["US", "CA", "GB", "DE", "FR", "JP", "AU", "BR", "IN", "SG"]
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X)",
            "Mozilla/5.0 (Android 11; Mobile; rv:91.0) Gecko/91.0"
        ]

        # Initialize counters for realistic patterns
        self.request_counter = 0
        self.error_spike_chance = 0.02  # 2% chance of error spike
        self.last_error_spike = 0

    def generate_ip(self) -> str:
        """Generate realistic IP address"""
        base = random.choice(self.ip_ranges)
        return f"{base}{random.randint(1, 254)}"

    def get_log_level_distribution(self) -> str:
        """Realistic log level distribution"""
        rand = random.random()
        if rand < 0.70:  # 70% info
            return "info"
        elif rand < 0.85:  # 15% debug
            return "debug"
        elif rand < 0.92:  # 7% warn
            return "warn"
        elif rand < 0.98:  # 6% error
            return "error"
        else:  # 2% fatal
            return "fatal"

    def generate_trace_context(self) -> tuple:
        """Generate OpenTelemetry trace context"""
        if random.random() < 0.8:  # 80% of requests have tracing
            trace_id = f"{random.randint(0, 2**64-1):016x}{random.randint(0, 2**64-1):016x}"
            span_id = f"{random.randint(0, 2**64-1):016x}"
            return trace_id, span_id
        return "", ""

    def generate_web_api_log(self) -> Dict[str, Any]:
        """Generate web application API logs"""
        endpoint = random.choice(self.api_endpoints)
        user_id = random.choice(self.user_ids)
        session_id = random.choice(self.session_ids)
        source_ip = self.generate_ip()

        # Determine response characteristics
        if random.random() < 0.05:  # 5% error rate
            status_codes = [400, 401, 403, 404, 429, 500, 502, 503]
            status = random.choice(status_codes)
            response_time = random.randint(1000, 5000)  # Slower on errors
            level = "error" if status >= 500 else "warn"
        else:
            status_codes = [200, 201, 202, 204]
            status = random.choice(status_codes)
            response_time = random.randint(50, 300)  # Fast normal responses
            level = "info"

        trace_id, span_id = self.generate_trace_context()

        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "host": random.choice(self.hosts),
            "service": random.choice(["web-frontend", "api-gateway"]),
            "level": level,
            "msg": f"{endpoint} - {status} - {response_time}ms",
            "trace_id": trace_id,
            "span_id": span_id,
            "status": status,
            "src_ip": source_ip,
            "user_id": user_id,
            "attrs": {
                "http.method": random.choice(["GET", "POST", "PUT", "DELETE"]),
                "http.url": f"https://api.testorg.com{endpoint}",
                "http.status_code": status,
                "http.response_time_ms": response_time,
                "http.user_agent": random.choice(self.user_agents),
                "session_id": session_id,
                "request_id": str(uuid.uuid4()),
                "country": random.choice(self.countries),
                "api_version": "v1",
                "environment": "production"
            }
        }

    def generate_auth_log(self) -> Dict[str, Any]:
        """Generate authentication and security logs"""
        auth_events = [
            "login_success", "login_failed", "logout", "password_reset",
            "mfa_challenge", "mfa_success", "mfa_failed", "session_expired",
            "suspicious_login", "account_locked", "password_changed"
        ]

        event = random.choice(auth_events)
        user_id = random.choice(self.user_ids)
        source_ip = self.generate_ip()

        # Security events have different patterns
        if "failed" in event or "suspicious" in event or "locked" in event:
            level = "warn"
            # Simulate attack patterns
            if random.random() < 0.3:  # 30% chance of suspicious IP
                source_ip = random.choice(["1.2.3.4", "5.6.7.8", "9.10.11.12"])
        else:
            level = "info"

        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "host": random.choice(["auth-01.testorg.com", "auth-02.testorg.com"]),
            "service": "auth-service",
            "level": level,
            "msg": f"Authentication event: {event} for user {user_id}",
            "src_ip": source_ip,
            "user_id": user_id,
            "attrs": {
                "auth.event": event,
                "auth.method": random.choice(["password", "sso", "api_key", "oauth"]),
                "device.type": random.choice(["desktop", "mobile", "tablet", "api"]),
                "location.country": random.choice(self.countries),
                "risk_score": random.randint(1, 100),
                "session_id": random.choice(self.session_ids),
                "user_agent": random.choice(self.user_agents)
            }
        }

    def generate_database_log(self) -> Dict[str, Any]:
        """Generate database operation logs"""
        operations = [
            "SELECT", "INSERT", "UPDATE", "DELETE", "BEGIN", "COMMIT", "ROLLBACK"
        ]
        tables = [
            "users", "orders", "products", "payments", "inventory", "sessions",
            "audit_logs", "notifications", "analytics_events", "integrations"
        ]

        operation = random.choice(operations)
        table = random.choice(tables)

        # Query performance varies
        if operation == "SELECT":
            duration = random.randint(1, 50)  # Fast selects
        elif operation in ["INSERT", "UPDATE", "DELETE"]:
            duration = random.randint(5, 100)  # Slower writes
        else:
            duration = random.randint(1, 10)  # Transaction ops

        level = "warn" if duration > 100 else "info"

        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "host": random.choice(["db-01.testorg.com", "db-02.testorg.com"]),
            "service": "database-proxy",
            "level": level,
            "msg": f"Query executed: {operation} on {table} ({duration}ms)",
            "attrs": {
                "db.operation": operation,
                "db.table": table,
                "db.duration_ms": duration,
                "db.rows_affected": random.randint(0, 1000),
                "db.connection_id": f"conn_{random.randint(1, 100)}",
                "db.query_id": str(uuid.uuid4()),
                "slow_query": duration > 50
            }
        }

    def generate_business_log(self) -> Dict[str, Any]:
        """Generate business application logs"""
        business_events = [
            "order_created", "order_cancelled", "payment_processed", "payment_failed",
            "inventory_updated", "product_viewed", "cart_abandoned", "user_registered",
            "email_sent", "notification_delivered", "report_generated", "backup_completed"
        ]

        event = random.choice(business_events)
        user_id = random.choice(self.user_ids) if "user" in event or "order" in event else ""

        # Business metrics
        revenue_impact = 0
        if "payment_processed" in event:
            revenue_impact = round(random.uniform(10.0, 500.0), 2)
        elif "order_created" in event:
            revenue_impact = round(random.uniform(25.0, 1000.0), 2)

        level = "error" if "failed" in event else "info"

        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "host": random.choice(self.hosts),
            "service": random.choice(["order-service", "payment-service", "notification-service"]),
            "level": level,
            "msg": f"Business event: {event}",
            "user_id": user_id,
            "attrs": {
                "business.event": event,
                "business.category": random.choice(["order", "payment", "inventory", "user", "system"]),
                "business.revenue_impact": revenue_impact,
                "order_id": f"ord_{random.randint(100000, 999999)}" if "order" in event else "",
                "product_id": f"prod_{random.randint(1000, 9999)}" if "product" in event else "",
                "environment": "production",
                "region": "us-east-1"
            }
        }

    def generate_system_log(self) -> Dict[str, Any]:
        """Generate system and infrastructure logs"""
        system_events = [
            "cpu_usage_high", "memory_usage_normal", "disk_space_low",
            "network_latency_high", "service_started", "service_stopped",
            "healthcheck_passed", "healthcheck_failed", "backup_started",
            "backup_completed", "deployment_started", "deployment_completed"
        ]

        event = random.choice(system_events)

        # System metrics
        cpu_usage = random.randint(10, 95)
        memory_usage = random.randint(20, 90)
        disk_usage = random.randint(30, 95)

        level = "warn" if any(x in event for x in ["high", "low", "failed"]) else "info"

        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "host": random.choice(self.hosts),
            "service": random.choice(["system-monitor", "health-checker", "deployment-agent"]),
            "level": level,
            "msg": f"System event: {event}",
            "attrs": {
                "system.event": event,
                "system.cpu_usage_percent": cpu_usage,
                "system.memory_usage_percent": memory_usage,
                "system.disk_usage_percent": disk_usage,
                "system.load_average": round(random.uniform(0.1, 4.0), 2),
                "system.network_rx_bytes": random.randint(1000, 1000000),
                "system.network_tx_bytes": random.randint(1000, 1000000),
                "environment": "production"
            }
        }

    def generate_security_log(self) -> Dict[str, Any]:
        """Generate security and compliance logs"""
        security_events = [
            "intrusion_attempt", "malware_detected", "suspicious_file_access",
            "privilege_escalation", "data_exfiltration_attempt", "brute_force_attack",
            "sql_injection_attempt", "xss_attempt", "csrf_detected",
            "compliance_check_passed", "compliance_check_failed", "audit_event"
        ]

        event = random.choice(security_events)
        source_ip = self.generate_ip()

        # Simulate external attackers
        if "attempt" in event or "attack" in event or "detected" in event:
            if random.random() < 0.7:  # 70% external IPs for attacks
                source_ip = f"{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
            level = "error"
            severity = random.randint(7, 10)
        else:
            level = "info"
            severity = random.randint(1, 5)

        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "host": random.choice(["security-01.testorg.com", "waf-01.testorg.com"]),
            "service": "security-engine",
            "level": level,
            "msg": f"Security event: {event}",
            "src_ip": source_ip,
            "attrs": {
                "security.event": event,
                "security.severity": severity,
                "security.threat_category": random.choice(["intrusion", "malware", "data_loss", "compliance"]),
                "security.rule_id": f"rule_{random.randint(1000, 9999)}",
                "security.signature": f"sig_{random.randint(10000, 99999)}",
                "security.blocked": random.choice([True, False]),
                "mitre.technique": random.choice(["T1078", "T1110", "T1190", "T1566", "T1055"]),
                "location.country": random.choice(self.countries),
                "environment": "production"
            }
        }

    def generate_log(self) -> Dict[str, Any]:
        """Generate a single log entry based on realistic distribution"""
        self.request_counter += 1

        # Realistic log type distribution for a tech company
        rand = random.random()

        if rand < 0.40:  # 40% web/API logs
            return self.generate_web_api_log()
        elif rand < 0.55:  # 15% business application logs
            return self.generate_business_log()
        elif rand < 0.70:  # 15% system/infrastructure logs
            return self.generate_system_log()
        elif rand < 0.85:  # 15% database logs
            return self.generate_database_log()
        elif rand < 0.95:  # 10% authentication logs
            return self.generate_auth_log()
        else:  # 5% security logs
            return self.generate_security_log()

class LogforgeClient:
    """HTTP client for Logforge API with authentication"""

    def __init__(self, base_url: str, tenant_id: str, auth_manager: AuthManager):
        self.base_url = base_url
        self.tenant_id = tenant_id
        self.auth_manager = auth_manager
        self.session = None

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                "User-Agent": "LogforgeSimulator/1.0"
            }
        )

        # Perform initial authentication
        logger.info("🔐 Authenticating with Logforge API...")
        if not await self.auth_manager.login(self.session):
            raise Exception("Failed to authenticate with Logforge API")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def send_logs_batch(self, logs: List[Dict[str, Any]]) -> bool:
        """Send batch of logs to /v1/ingest/logs/batch"""
        try:
            # Get valid authentication token
            token = await self.auth_manager.get_valid_token(self.session)
            if not token:
                logger.error("Failed to get valid authentication token")
                metrics.total_errors += 1
                return False

            batch_data = {
                "logs": logs,
                "batch_id": str(uuid.uuid4()),
                "source": "simulation_script"
            }

            headers = self.auth_manager.get_auth_headers()

            async with self.session.post(
                f"{self.base_url}/v1/ingest/logs/batch",
                json=batch_data,
                headers=headers
            ) as response:
                if response.status == 200:
                    metrics.total_logs_sent += len(logs)
                    metrics.total_batches_sent += 1
                    metrics.bytes_sent += len(json.dumps(batch_data))
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Batch failed: {response.status} - {error_text}")
                    metrics.total_errors += 1
                    return False

        except Exception as e:
            logger.error(f"Batch request failed: {e}")
            metrics.total_errors += 1
            return False

    async def send_logs_bulk(self, logs: List[Dict[str, Any]]) -> bool:
        """Send bulk logs to /v1/ingest/logs/bulk"""
        try:
            # Get valid authentication token
            token = await self.auth_manager.get_valid_token(self.session)
            if not token:
                logger.error("Failed to get valid authentication token")
                metrics.total_errors += 1
                return False

            bulk_data = {
                "format": "json",
                "data": logs,
                "metadata": {
                    "source": "simulation_script",
                    "batch_size": len(logs),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }

            headers = self.auth_manager.get_auth_headers()

            async with self.session.post(
                f"{self.base_url}/v1/ingest/logs/bulk",
                json=bulk_data,
                headers=headers
            ) as response:
                if response.status == 200:
                    metrics.total_logs_sent += len(logs)
                    metrics.total_batches_sent += 1
                    metrics.bytes_sent += len(json.dumps(bulk_data))
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Bulk failed: {response.status} - {error_text}")
                    metrics.total_errors += 1
                    return False

        except Exception as e:
            logger.error(f"Bulk request failed: {e}")
            metrics.total_errors += 1
            return False

    async def send_single_log(self, log: Dict[str, Any]) -> bool:
        """Send single log to /v1/ingest/logs"""
        try:
            # Get valid authentication token
            token = await self.auth_manager.get_valid_token(self.session)
            if not token:
                logger.error("Failed to get valid authentication token")
                metrics.total_errors += 1
                return False

            headers = self.auth_manager.get_auth_headers()

            async with self.session.post(
                f"{self.base_url}/v1/ingest/logs",
                json=log,
                headers=headers
            ) as response:
                if response.status == 200:
                    metrics.total_logs_sent += 1
                    metrics.bytes_sent += len(json.dumps(log))
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Single log failed: {response.status} - {error_text}")
                    metrics.total_errors += 1
                    return False

        except Exception as e:
            logger.error(f"Single log request failed: {e}")
            metrics.total_errors += 1
            return False

async def worker(worker_id: int, client: LogforgeClient, generator: LogGenerator, logs_per_second: int):
    """Worker coroutine that generates and sends logs"""
    logger.info(f"Worker {worker_id} started, target: {logs_per_second} logs/sec")

    interval = 1.0 / logs_per_second if logs_per_second > 0 else 0.001
    batch_interval = max(interval * BATCH_SIZE, 0.1)  # At least 100ms between batches

    while True:
        try:
            # Generate batch of logs
            logs = []
            for _ in range(BATCH_SIZE):
                log = generator.generate_log()
                logs.append(log)

            # Send batch
            success = await client.send_logs_batch(logs)

            if not success:
                logger.warning(f"Worker {worker_id} failed to send batch")

            # Control rate
            await asyncio.sleep(batch_interval)

        except asyncio.CancelledError:
            logger.info(f"Worker {worker_id} cancelled")
            break
        except Exception as e:
            logger.error(f"Worker {worker_id} error: {e}")
            await asyncio.sleep(1)  # Error backoff

async def stats_reporter():
    """Report simulation statistics every 10 seconds"""
    last_logs = 0
    last_time = time.time()

    while True:
        await asyncio.sleep(10)

        current_time = time.time()
        elapsed = current_time - metrics.start_time
        current_logs = metrics.total_logs_sent

        # Calculate rates
        total_rate = current_logs / elapsed if elapsed > 0 else 0
        interval_rate = (current_logs - last_logs) / 10

        logger.info(
            f"📊 Stats: {current_logs:,} logs sent | "
            f"{metrics.total_batches_sent:,} batches | "
            f"{metrics.total_errors} errors | "
            f"Rate: {total_rate:.1f}/s avg, {interval_rate:.1f}/s current | "
            f"Data: {metrics.bytes_sent/1024/1024:.1f}MB"
        )

        last_logs = current_logs
        last_time = current_time

async def main(args):
    """Main simulation function"""
    logger.info("🚀 Starting Logforge Tenant Log Simulation")
    logger.info(f"Target Tenant: {TENANT_ID}")
    logger.info(f"Target Rate: {args.rate} logs/sec")
    logger.info(f"Workers: {args.workers}")
    logger.info(f"Batch Size: {BATCH_SIZE}")
    logger.info(f"Logforge API: {LOGFORGE_API_BASE}")

    metrics.start_time = time.time()
    generator = LogGenerator()

    # Calculate logs per worker
    logs_per_worker = args.rate // args.workers

    # Create authentication manager
    auth_manager = AuthManager(LOGFORGE_API_BASE, AUTH_EMAIL, AUTH_PASSWORD)

    async with LogforgeClient(LOGFORGE_API_BASE, TENANT_ID, auth_manager) as client:
        # Test connection
        try:
            test_log = generator.generate_log()
            success = await client.send_single_log(test_log)
            if not success:
                logger.error("❌ Failed to send test log - check API connection")
                return
            logger.info("✅ API connection successful")
        except Exception as e:
            logger.error(f"❌ API connection failed: {e}")
            return

        # Start workers and stats reporter
        tasks = []

        # Start worker tasks
        for i in range(args.workers):
            task = asyncio.create_task(
                worker(i, client, generator, logs_per_worker)
            )
            tasks.append(task)

        # Start stats reporter
        stats_task = asyncio.create_task(stats_reporter())
        tasks.append(stats_task)

        try:
            if args.duration > 0:
                logger.info(f"⏱️  Running for {args.duration} seconds...")
                await asyncio.sleep(args.duration)
            else:
                logger.info("🔄 Running indefinitely (Ctrl+C to stop)...")
                await asyncio.gather(*tasks)

        except KeyboardInterrupt:
            logger.info("🛑 Stopping simulation...")
        finally:
            # Cancel all tasks
            for task in tasks:
                task.cancel()

            # Wait for tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)

            # Final stats
            elapsed = time.time() - metrics.start_time
            rate = metrics.total_logs_sent / elapsed if elapsed > 0 else 0

            logger.info("📋 Final Statistics:")
            logger.info(f"   Total Logs Sent: {metrics.total_logs_sent:,}")
            logger.info(f"   Total Batches: {metrics.total_batches_sent:,}")
            logger.info(f"   Total Errors: {metrics.total_errors}")
            logger.info(f"   Duration: {elapsed:.1f} seconds")
            logger.info(f"   Average Rate: {rate:.1f} logs/sec")
            logger.info(f"   Data Sent: {metrics.bytes_sent/1024/1024:.1f} MB")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Logforge Tenant Log Simulation")
    parser.add_argument("--rate", type=int, default=TARGET_EPS,
                       help=f"Target logs per second (default: {TARGET_EPS})")
    parser.add_argument("--workers", type=int, default=CONCURRENT_WORKERS,
                       help=f"Number of concurrent workers (default: {CONCURRENT_WORKERS})")
    parser.add_argument("--duration", type=int, default=0,
                       help="Duration in seconds (0 = run indefinitely)")
    parser.add_argument("--api-url", type=str, default=LOGFORGE_API_BASE,
                       help=f"Logforge API base URL (default: {LOGFORGE_API_BASE})")

    args = parser.parse_args()

    # Update globals from args
    LOGFORGE_API_BASE = args.api_url
    TARGET_EPS = args.rate
    CONCURRENT_WORKERS = args.workers

    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        logger.info("Simulation interrupted by user")
    except Exception as e:
        logger.error(f"Simulation failed: {e}")
        sys.exit(1)
