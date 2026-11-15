#!/usr/bin/env python3
"""
Simple Log Ingestion Test Script
================================

Quick test to verify log ingestion APIs work for tenant: bf084eec-d6ba-427a-a787-98c4d809e54e
Tests all available ingestion endpoints with sample data.
"""

import os
import asyncio
import aiohttp
import json
from datetime import datetime, timezone
import uuid

# Configuration
LOGFORGE_API_BASE = os.getenv("LOGFORGE_API_URL", "http://localhost:7080")
TENANT_ID = os.getenv("LOGFORGE_TENANT_ID", "")

# Authentication
AUTH_EMAIL = os.getenv("LOGFORGE_EMAIL", "testuser@testorg.com")
AUTH_PASSWORD = os.getenv("LOGFORGE_PASSWORD", "")

async def login_and_get_token(session):
    """Login and get JWT token"""
    login_data = {
        "email": AUTH_EMAIL,
        "password": AUTH_PASSWORD,
        "remember_me": True
    }
    
    try:
        async with session.post(
            f"{LOGFORGE_API_BASE}/v1/auth/login",
            json=login_data,
            headers={"Content-Type": "application/json"}
        ) as response:
            if response.status == 200:
                data = await response.json()
                access_token = data.get("access_token")
                tenant = data.get("tenant", {})
                tenant_id = tenant.get("id", TENANT_ID)
                
                print(f"✅ Authentication successful")
                print(f"🏢 Tenant: {tenant.get('name', 'Unknown')} ({tenant_id})")
                return access_token, tenant_id
            else:
                error = await response.text()
                print(f"❌ Authentication failed: {response.status} - {error}")
                return None, None
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return None, None

async def test_ingestion_endpoints():
    """Test all ingestion endpoints"""
    
    async with aiohttp.ClientSession() as session:
        
        print("🧪 Testing Logforge Ingestion APIs")
        print(f"Tenant: {TENANT_ID}")
        print(f"API Base: {LOGFORGE_API_BASE}")
        print("-" * 50)
        
        # First, authenticate and get token
        print("🔐 Authenticating...")
        access_token, actual_tenant_id = await login_and_get_token(session)
        if not access_token:
            print("❌ Authentication failed. Cannot proceed with tests.")
            return
        
        # Prepare headers with authentication
        auth_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-Customer-ID": actual_tenant_id
        }
        
        # Test 1: Single log entry
        print("1️⃣ Testing /v1/ingest/logs (single log)")
        single_log = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "host": "test-server.testorg.com",
            "service": "test-service",
            "level": "info",
            "msg": "Test log message from simulation script",
            "user_id": "test_user_001",
            "src_ip": "192.168.1.100",
            "attrs": {
                "test": True,
                "environment": "simulation",
                "endpoint": "single_log"
            }
        }
        
        try:
            async with session.post(f"{LOGFORGE_API_BASE}/v1/ingest/logs", json=single_log, headers=auth_headers) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"   ✅ Success: {result}")
                else:
                    error = await response.text()
                    print(f"   ❌ Failed: {response.status} - {error}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 2: Batch logs
        print("\n2️⃣ Testing /v1/ingest/logs/batch")
        batch_logs = {
            "logs": [
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "host": "web-01.testorg.com",
                    "service": "web-frontend",
                    "level": "info",
                    "msg": "User login successful",
                    "user_id": "user_12345",
                    "src_ip": "203.0.113.50",
                    "attrs": {"action": "login", "method": "password"}
                },
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "host": "api-01.testorg.com",
                    "service": "api-gateway",
                    "level": "info",
                    "msg": "API request processed",
                    "status": 200,
                    "attrs": {"endpoint": "/api/users/profile", "duration_ms": 45}
                },
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "host": "db-01.testorg.com",
                    "service": "database-proxy",
                    "level": "warn",
                    "msg": "Slow query detected",
                    "attrs": {"table": "users", "duration_ms": 1200, "operation": "SELECT"}
                }
            ],
            "batch_id": str(uuid.uuid4()),
            "source": "test_script"
        }
        
        try:
            async with session.post(f"{LOGFORGE_API_BASE}/v1/ingest/logs/batch", json=batch_logs, headers=auth_headers) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"   ✅ Success: {result}")
                else:
                    error = await response.text()
                    print(f"   ❌ Failed: {response.status} - {error}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 3: Bulk logs
        print("\n3️⃣ Testing /v1/ingest/logs/bulk")
        bulk_data = {
            "format": "json",
            "data": [
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "host": "security-01.testorg.com",
                    "service": "security-engine",
                    "level": "error",
                    "msg": "Failed login attempt detected",
                    "src_ip": "1.2.3.4",
                    "user_id": "unknown",
                    "attrs": {
                        "security.event": "login_failed",
                        "attempts": 5,
                        "blocked": True
                    }
                },
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "host": "payment-01.testorg.com", 
                    "service": "payment-service",
                    "level": "info",
                    "msg": "Payment processed successfully",
                    "user_id": "user_67890",
                    "attrs": {
                        "payment.amount": 99.99,
                        "payment.currency": "USD",
                        "payment.method": "credit_card",
                        "order_id": "ord_123456"
                    }
                }
            ],
            "metadata": {
                "source": "test_script",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
        try:
            async with session.post(f"{LOGFORGE_API_BASE}/v1/ingest/logs/bulk", json=bulk_data, headers=auth_headers) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"   ✅ Success: {result}")
                else:
                    error = await response.text()
                    print(f"   ❌ Failed: {response.status} - {error}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 4: Structured data
        print("\n4️⃣ Testing /v1/ingest/structured")
        structured_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "info",
            "message": "Application started successfully",
            "logger": "com.testorg.Application",
            "thread": "main",
            "context": {
                "application": "testorg-api",
                "version": "1.2.3",
                "environment": "production",
                "startup_time_ms": 2345
            }
        }
        
        try:
            async with session.post(f"{LOGFORGE_API_BASE}/v1/ingest/structured", json=structured_data, headers=auth_headers) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"   ✅ Success: {result}")
                else:
                    error = await response.text()
                    print(f"   ❌ Failed: {response.status} - {error}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 5: Syslog format
        print("\n5️⃣ Testing /v1/ingest/syslog")
        syslog_data = "<134>Oct  6 18:30:15 web-server sshd[12345]: Failed password for invalid user admin from 192.168.1.50 port 22 ssh2"
        
        try:
            syslog_headers = {
                "Content-Type": "text/plain",
                "Authorization": f"Bearer {access_token}",
                "X-Customer-ID": actual_tenant_id
            }
            async with session.post(
                f"{LOGFORGE_API_BASE}/v1/ingest/syslog", 
                data=syslog_data,
                headers=syslog_headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"   ✅ Success: {result}")
                else:
                    error = await response.text()
                    print(f"   ❌ Failed: {response.status} - {error}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print("\n" + "=" * 50)
        print("🎯 All ingestion tests completed!")
        print("If successful, you should see logs appearing in your Logforge dashboard.")
        print("Run the full simulation script with:")
        print("   python3 simulate_tenant_logs.py --rate 100 --duration 60")

if __name__ == "__main__":
    asyncio.run(test_ingestion_endpoints())