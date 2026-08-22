#!/usr/bin/env python3
"""
Test script for anomaly detection flow
Sends metrics -> Triggers detection -> Verifies results
"""

import requests
import time
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:7080"
BEARER_TOKEN = "lf_832f393c_-BTG4wbidMe8tjYdJZ02471eCRN9UBtN7r_w2EEMKJY"
CUSTOMER_ID = "832f393c-d9de-4a80-a183-aa913ad27266"

HEADERS = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "Content-Type": "application/json",
    "X-Customer-ID": CUSTOMER_ID
}

def send_normal_metrics():
    """Send normal baseline metrics"""
    print("\n📊 Step 1: Sending NORMAL metrics (baseline)...")

    endpoint = f"{API_BASE_URL}/v1/observability/metrics/ingest"

    metrics = [
        {
            "metric_name": "cpu_usage",
            "metric_type": "gauge",
            "value": 25.0,  # Normal CPU
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "labels": {
                "host": "payment-server-01",
                "env": "production"
            },
            "service_name": "payment-service",
            "resource": {
                "service.name": "payment-service"
            }
        },
        {
            "metric_name": "memory_usage",
            "metric_type": "gauge",
            "value": 2000.0,  # Normal memory
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "labels": {
                "host": "payment-server-01",
                "env": "production"
            },
            "service_name": "payment-service",
            "resource": {
                "service.name": "payment-service"
            }
        },
        {
            "metric_name": "error_rate",
            "metric_type": "gauge",
            "value": 2.0,  # Normal error rate
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "labels": {
                "host": "payment-server-01",
                "env": "production"
            },
            "service_name": "payment-service",
            "resource": {
                "service.name": "payment-service"
            }
        }
    ]

    payload = {"metrics": metrics}

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload, timeout=10)
        if response.status_code in [200, 202]:
            print(f"   ✓ Sent {len(metrics)} normal metrics")
            return True
        else:
            print(f"   ✗ Failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False


def send_anomalous_metrics():
    """Send anomalous metrics (extreme spikes)"""
    print("\n🚨 Step 2: Sending ANOMALOUS metrics (extreme spikes)...")

    endpoint = f"{API_BASE_URL}/v1/observability/metrics/ingest"

    # Send 10 anomalous data points to build a pattern
    for i in range(10):
        metrics = [
            {
                "metric_name": "cpu_usage",
                "metric_type": "gauge",
                "value": 98.0 + (i * 0.1),  # EXTREME CPU spike
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "labels": {
                    "host": "payment-server-01",
                    "env": "production"
                },
                "service_name": "payment-service",
                "resource": {
                    "service.name": "payment-service"
                }
            },
            {
                "metric_name": "memory_usage",
                "metric_type": "gauge",
                "value": 7800.0 + (i * 10),  # EXTREME memory spike
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "labels": {
                    "host": "payment-server-01",
                    "env": "production"
                },
                "service_name": "payment-service",
                "resource": {
                    "service.name": "payment-service"
                }
            },
            {
                "metric_name": "error_rate",
                "metric_type": "gauge",
                "value": 45.0 + (i * 0.5),  # EXTREME error rate
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "labels": {
                    "host": "payment-server-01",
                    "env": "production"
                },
                "service_name": "payment-service",
                "resource": {
                    "service.name": "payment-service"
                }
            }
        ]

        payload = {"metrics": metrics}

        try:
            response = requests.post(endpoint, headers=HEADERS, json=payload, timeout=10)
            if response.status_code in [200, 202]:
                print(f"   ✓ Batch {i+1}/10: Sent {len(metrics)} anomalous metrics")
            else:
                print(f"   ✗ Batch {i+1}/10 Failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"   ✗ Error on batch {i+1}: {e}")
            return False

        time.sleep(0.1)  # Small delay between batches

    return True


def trigger_detection():
    """Trigger multi-metric anomaly detection"""
    print("\n🔍 Step 3: Triggering multi-metric anomaly detection...")

    endpoint = f"{API_BASE_URL}/v1/ai/anomalies/detect/multi-metric"

    payload = {
        "metrics": [
            {"type": "cpu_usage", "service": "payment-service", "weight": 1.0},
            {"type": "memory_usage", "service": "payment-service", "weight": 0.9},
            {"type": "error_rate", "service": "payment-service", "weight": 0.8}
        ],
        "time_range": "1h",
        "correlation_threshold": 0.5,
        "algorithms": ["z_score"]
    }

    try:
        response = requests.post(endpoint, headers=HEADERS, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            anomaly_count = len(data.get("anomalies", []))
            print(f"   ✓ Detection complete: Found {anomaly_count} anomalies")

            if anomaly_count > 0:
                print("\n   📋 Detected Anomalies:")
                for i, anomaly in enumerate(data["anomalies"][:5], 1):
                    print(f"      {i}. {anomaly.get('title', 'Unknown')}")
                    print(f"         Severity: {anomaly.get('severity')}, Confidence: {anomaly.get('confidence', 0):.2f}")
                    print(f"         Affected metrics: {len(anomaly.get('affected_metrics', []))}")

            return data
        else:
            print(f"   ✗ Detection failed: {response.status_code}")
            print(f"      Response: {response.text}")
            return None
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return None


def main():
    print("=" * 60)
    print("🧪 Anomaly Detection Flow Test")
    print("=" * 60)
    print(f"API: {API_BASE_URL}")
    print(f"Customer ID: {CUSTOMER_ID}")
    print("=" * 60)

    # Step 1: Send normal baseline metrics
    if not send_normal_metrics():
        print("\n❌ Failed to send normal metrics. Aborting.")
        return

    time.sleep(2)

    # Step 2: Send anomalous metrics
    if not send_anomalous_metrics():
        print("\n❌ Failed to send anomalous metrics. Aborting.")
        return

    print("\n⏳ Waiting 3 seconds for metrics to be processed...")
    time.sleep(3)

    # Step 3: Trigger detection
    result = trigger_detection()

    if result:
        anomaly_count = len(result.get("anomalies", []))
        if anomaly_count > 0:
            print("\n✅ SUCCESS! Anomaly detection is working.")
            print(f"   Detected {anomaly_count} anomalies from the test data.")
        else:
            print("\n⚠️  Detection ran but found NO anomalies.")
            print("   This could mean:")
            print("   - Detection algorithm thresholds are too strict")
            print("   - Metrics weren't stored in database")
            print("   - Time window doesn't match metric timestamps")
    else:
        print("\n❌ FAILED! Anomaly detection endpoint returned an error.")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()