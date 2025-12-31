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
BEARER_TOKEN = "lf_832f393c_-BTG4wbidMe8tjYdJZ02471eCRN9UBtN7r_w2EEMKJY"
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


def send_normal_metrics():
    """Send NORMAL baseline metrics"""
    endpoint = f"{API_BASE_URL}/v1/observability/metrics/ingest"

    service = "payment-service"
    host = "payment-server-01"

    metrics = []

    # NORMAL CPU usage (20-40%)
    cpu_metric = {
        "metric_name": "cpu_usage",
        "metric_type": "gauge",
        "value": random.uniform(20, 40),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "labels": {
            "host": host,
            "env": "production",
            "core": "0"
        },
        "service_name": service,
        "resource": {
            "service.name": service
        }
    }
    metrics.append(cpu_metric)

    # NORMAL Memory usage (2000-3500 MB)
    memory_metric = {
        "metric_name": "memory_usage",
        "metric_type": "gauge",
        "value": random.uniform(2000, 3500),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "labels": {
            "host": host,
            "env": "production"
        },
        "service_name": service,
        "resource": {
            "service.name": service
        }
    }
    metrics.append(memory_metric)

    # NORMAL Error rate (1-5%)
    error_metric = {
        "metric_name": "error_rate",
        "metric_type": "gauge",
        "value": random.uniform(1, 5),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "labels": {
            "env": "production",
            "http.status_code": "500"
        },
        "service_name": service,
        "resource": {
            "service.name": service
        }
    }
    metrics.append(error_metric)

    # NORMAL Response time (50-200ms)
    response_time_metric = {
        "metric_name": "response_time",
        "metric_type": "gauge",
        "value": random.uniform(50, 200),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "labels": {
            "env": "production",
            "endpoint": "/api/payments"
        },
        "service_name": service,
        "resource": {
            "service.name": service
        }
    }
    metrics.append(response_time_metric)

    payload = {"metrics": metrics}

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code in [200, 202]:
            print(f"✓ Sent {len(metrics)} NORMAL metrics (CPU: {cpu_metric['value']:.1f}%, Mem: {memory_metric['value']:.0f}MB, Err: {error_metric['value']:.1f}%)")
        else:
            print(f"✗ Failed to send normal metrics: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Error sending normal metrics: {e}")


def send_anomalous_metrics():
    """Send anomalous metrics to trigger multi-metric anomaly detection"""
    endpoint = f"{API_BASE_URL}/v1/observability/metrics/ingest"

    service = "payment-service"  # Target specific service for anomaly
    host = "payment-server-01"

    metrics = []

    # ANOMALY 1: Extreme CPU spike (normally 10-50%, now 95%+)
    cpu_metric = {
        "metric_name": "cpu_usage",
        "metric_type": "gauge",
        "value": random.uniform(95, 99.9),  # Extreme CPU usage
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "labels": {
            "host": host,
            "env": "production",
            "core": "0"
        },
        "service_name": service,
        "resource": {
            "service.name": service
        }
    }
    metrics.append(cpu_metric)

    # ANOMALY 2: Extreme memory spike (normally 1000-4000MB, now 7500MB+)
    memory_metric = {
        "metric_name": "memory_usage",
        "metric_type": "gauge",
        "value": random.uniform(7500, 7900),  # Extreme memory usage
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "labels": {
            "host": host,
            "env": "production"
        },
        "service_name": service,
        "resource": {
            "service.name": service
        }
    }
    metrics.append(memory_metric)

    # ANOMALY 3: High error rate (normally <5%, now 40%+)
    error_metric = {
        "metric_name": "error_rate",
        "metric_type": "gauge",
        "value": random.uniform(40, 60),  # High error rate
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "labels": {
            "env": "production",
            "http.status_code": "500"
        },
        "service_name": service,
        "resource": {
            "service.name": service
        }
    }
    metrics.append(error_metric)

    # ANOMALY 4: Extreme response time (normally 10-100ms, now 5000ms+)
    response_time_metric = {
        "metric_name": "response_time",
        "metric_type": "gauge",
        "value": random.uniform(5000, 10000),  # Extreme latency
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "labels": {
            "env": "production",
            "endpoint": "/api/payments"
        },
        "service_name": service,
        "resource": {
            "service.name": service
        }
    }
    metrics.append(response_time_metric)

    # ANOMALY 5: Low throughput (normally 500-1000, now <50)
    throughput_metric = {
        "metric_name": "throughput",
        "metric_type": "counter",
        "value": random.randint(10, 50),  # Very low request count
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "labels": {
            "env": "production",
            "http.status_code": "200"
        },
        "service_name": service,
        "resource": {
            "service.name": service
        }
    }
    metrics.append(throughput_metric)

    payload = {"metrics": metrics}

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload)
        if response.status_code in [200, 202]:
            print(f"🚨 Sent {len(metrics)} ANOMALOUS metrics for {service}")
            print(f"   CPU: {cpu_metric['value']:.1f}%, Memory: {memory_metric['value']:.0f}MB, Errors: {error_metric['value']:.1f}%")
        else:
            print(f"✗ Failed to send anomalous metrics: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Error sending anomalous metrics: {e}")


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
    print("=" * 60)
    print()

    iteration = 0

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

            # Send metrics
            send_metrics()
            time.sleep(1)

            # Every 5 iterations, trigger alert rules
            if iteration % 5 == 0:
                print("\n🔔 Triggering alert rules...")
                send_high_error_rate_logs()
                time.sleep(1)
                send_critical_security_logs()
                time.sleep(1)

            # Every 7 iterations, trigger Sigma rules
            if iteration % 7 == 0:
                print("\n🛡️  Triggering Sigma security rules...")
                send_brute_force_logs()
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