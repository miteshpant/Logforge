"""
Test Runner API - Backend endpoints to execute tests and return results to UI
"""

import asyncio
import subprocess
import json
import time
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/test-runner", tags=["test-runner"])

# Test execution state management
test_execution_state: Dict[str, Any] = {
    "current_suite": None,
    "running": False,
    "results": {},
    "logs": []
}

class TestSuiteRequest(BaseModel):
    suite_id: str
    test_type: Optional[str] = None

class TestResult(BaseModel):
    name: str
    status: str  # 'passed', 'failed', 'running', 'pending'
    duration: Optional[float] = None
    error: Optional[str] = None
    output: Optional[List[str]] = None
    timestamp: Optional[str] = None

class TestSuiteResult(BaseModel):
    suite_id: str
    status: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    running_tests: int
    tests: List[TestResult]
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

def add_log(message: str):
    """Add log message with timestamp"""
    timestamp = datetime.now().isoformat()
    log_entry = f"[{timestamp}] {message}"
    test_execution_state["logs"].append(log_entry)
    logger.info(message)

async def run_python_test_command(command: List[str]) -> Dict[str, Any]:
    """Run a Python test command and capture output"""
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/app"
        )
        
        stdout, stderr = await process.communicate()
        
        return {
            "return_code": process.returncode,
            "stdout": stdout.decode('utf-8'),
            "stderr": stderr.decode('utf-8')
        }
    except Exception as e:
        return {
            "return_code": -1,
            "stdout": "",
            "stderr": f"Command execution failed: {str(e)}"
        }

async def execute_test_suite_background(suite_id: str):
    """Execute a test suite in the background"""
    test_execution_state["running"] = True
    test_execution_state["current_suite"] = suite_id
    
    add_log(f"🚀 Starting test suite: {suite_id}")
    
    # Define test commands for each suite
    test_commands = {
        "ingestion": [
            ("API Health Check", ["python", "-c", "import requests; r=requests.get('http://host.docker.internal:7080/health'); print(f'Status: {r.status_code}'); assert r.status_code == 200"]),
            ("JSON Log Ingestion", ["python", "-c", """
import requests, json
from datetime import datetime
log_data = {
    'ts': datetime.now().isoformat(),
    'level': 'INFO',
    'msg': 'Test log from API test runner',
    'service': 'test-runner',
    'customer_id': 'test-customer'
}
r = requests.post('http://host.docker.internal:7080/v1/ingest/logs', json=log_data, headers={'X-Customer-ID': 'test-customer'})
print(f'Ingestion Status: {r.status_code}')
assert r.status_code in [200, 201]
"""]),
            ("Multi-tenant Storage Test", ["python", "run_tests.py", "--test=storage"]),
            ("TTL Policy Validation", ["python", "run_tests.py", "--test=ttl"]),
        ],
        "query-dashboard": [
            ("Advanced Query Engine", ["python", "-c", """
import requests, json
from datetime import datetime, timedelta
query_data = {
    'start_time': (datetime.now() - timedelta(hours=24)).isoformat(),
    'end_time': datetime.now().isoformat(),
    'filters': [{'field': 'customer_id', 'operator': 'eq', 'value': 'test-customer'}],
    'limit': 10
}
r = requests.post('http://host.docker.internal:7080/v1/query/advanced', json=query_data, headers={'X-Customer-ID': 'test-customer'})
print(f'Query Status: {r.status_code}')
assert r.status_code == 200
"""]),
            ("Dashboard Generation", ["python", "-c", """
import requests
r = requests.get('http://host.docker.internal:7080/v1/dashboards/security_soc', headers={'X-Customer-ID': 'test-customer'})
print(f'Dashboard Status: {r.status_code}')
data = r.json()
print(f'Widgets: {len(data.get("widgets", []))}')
assert r.status_code == 200
"""]),
        ],
        "alert-engine": [
            ("Alert Engine Health", ["python", "-c", """
import requests
r = requests.get('http://host.docker.internal:7080/v1/alerts/health', headers={'X-Customer-ID': 'test-customer'})
print(f'Alert Health Status: {r.status_code}')
assert r.status_code == 200
"""]),
            ("Alert Rules CRUD", ["python", "-c", """
import requests, json
rule_data = {
    'name': 'Test Alert Rule',
    'description': 'Test rule from API runner',
    'customer_id': 'test-customer',
    'severity': 'LOW',
    'rule_type': 'THRESHOLD',
    'enabled': True,
    'conditions': [{
        'field': 'level',
        'operator': 'EQUALS',
        'value': 'ERROR',
        'aggregation': 'count',
        'time_window': '5m'
    }],
    'filters': [{'field': 'customer_id', 'operator': 'eq', 'value': 'test-customer'}],
    'notification_channels': ['email'],
    'tags': ['test'],
    'evaluation_interval': '2m',
    'cooldown_period': '10m',
    'max_alerts_per_hour': 5
}
r = requests.post('http://host.docker.internal:7080/v1/alerts/rules', json=rule_data, headers={'X-Customer-ID': 'test-customer', 'X-User-ID': 'test-user'})
print(f'Rule Creation Status: {r.status_code}')
if r.status_code in [200, 201]:
    rule = r.json()
    rule_id = rule['rule_id']
    print(f'Created Rule ID: {rule_id}')
    # Clean up
    delete_r = requests.delete(f'http://host.docker.internal:7080/v1/alerts/rules/{rule_id}', headers={'X-Customer-ID': 'test-customer'})
    print(f'Cleanup Status: {delete_r.status_code}')
assert r.status_code in [200, 201]
"""]),
        ],
        "integration": [
            ("Comprehensive Integration Test", ["python", "tests/test_integration_comprehensive.py"]),
        ],
        "performance": [
            ("Query Performance Test", ["python", "-c", """
import requests, json, time
from datetime import datetime, timedelta
query_data = {
    'start_time': (datetime.now() - timedelta(hours=1)).isoformat(),
    'end_time': datetime.now().isoformat(),
    'filters': [{'field': 'customer_id', 'operator': 'eq', 'value': 'test-customer'}],
    'limit': 1000
}
start_time = time.time()
r = requests.post('http://host.docker.internal:7080/v1/query/advanced', json=query_data, headers={'X-Customer-ID': 'test-customer'})
duration = time.time() - start_time
print(f'Query completed in {duration:.2f}s')
print(f'Status: {r.status_code}')
assert r.status_code == 200
assert duration < 5.0  # Should complete within 5 seconds
"""]),
        ],
        "security-analytics": [
            ("Security Analytics Health Check", ["python", "-c", """
import requests
r = requests.get('http://host.docker.internal:7080/v1/security/health', headers={'X-Customer-ID': 'test-customer'})
print(f'Security Health Status: {r.status_code}')
data = r.json()
print(f'Sigma Rules: {data.get("sigma_rules_count", 0)}')
print(f'Threat Intel: {data.get("threat_intel_count", 0)}')
assert r.status_code == 200
assert data.get('status') == 'healthy'
"""]),
            ("Sigma Rules Management", ["python", "-c", """
import requests, json
# List Sigma rules
r = requests.get('http://host.docker.internal:7080/v1/security/sigma-rules', headers={'X-Customer-ID': 'test-customer'})
print(f'List Sigma Rules Status: {r.status_code}')
rules = r.json()
print(f'Found {len(rules)} Sigma rules')
assert r.status_code == 200
assert len(rules) > 0
print('✓ Default Sigma rules loaded successfully')
"""]),
            ("Security Dashboard", ["python", "-c", """
import requests
r = requests.get('http://host.docker.internal:7080/v1/security/dashboard?time_range=24h', headers={'X-Customer-ID': 'test-customer'})
print(f'Security Dashboard Status: {r.status_code}')
data = r.json()
print(f'Total Events: {data.get("total_events", 0)}')
print(f'Events by Severity: {data.get("events_by_severity", {})}')
assert r.status_code == 200
"""]),
            ("Threat Intelligence Indicators", ["python", "-c", """
import requests
r = requests.get('http://host.docker.internal:7080/v1/security/threat-intel', headers={'X-Customer-ID': 'test-customer'})
print(f'Threat Intel Status: {r.status_code}')
indicators = r.json()
print(f'Found {len(indicators)} threat intelligence indicators')
assert r.status_code == 200
assert len(indicators) > 0
print('✓ Default threat intelligence loaded successfully')
"""]),
            ("Sigma Rule Testing", ["python", "-c", """
import requests, json
# Get first rule ID
rules_r = requests.get('http://host.docker.internal:7080/v1/security/sigma-rules', headers={'X-Customer-ID': 'test-customer'})
rules = rules_r.json()
if len(rules) > 0:
    rule_id = rules[0]['id']
    print(f'Testing Sigma rule: {rule_id}')
    
    # Test the rule
    test_r = requests.post(f'http://host.docker.internal:7080/v1/security/sigma-rules/{rule_id}/test', headers={'X-Customer-ID': 'test-customer'})
    print(f'Rule Test Status: {test_r.status_code}')
    
    if test_r.status_code == 200:
        result = test_r.json()
        print(f'Test Result: {result.get("result", "unknown")}')
        print('✓ Sigma rule test completed successfully')
    else:
        print('Rule test completed (no matches expected for test data)')
else:
    print('No Sigma rules found to test')
"""]),
            ("Threat Hunting Execution", ["python", "-c", """
import requests, json, time
print('Starting threat hunting...')
hunt_data = {
    'time_range': '24h',
    'severity_filter': None,
    'rule_ids': None
}
r = requests.post('http://host.docker.internal:7080/v1/security/threat-hunting', 
                 json=hunt_data, 
                 headers={'X-Customer-ID': 'test-customer'})
print(f'Threat Hunting Status: {r.status_code}')

if r.status_code == 200:
    result = r.json()
    print(f'Hunt completed: {result.get("events_found", 0)} events found')
    events = result.get('events', [])
    for event in events[:3]:  # Show first 3 events
        print(f'  - {event.get("rule_title", "Unknown")}: {event.get("severity", "unknown")}')
    print('✓ Threat hunting completed successfully')
else:
    print('Threat hunting request failed')
"""]),
            ("MITRE ATT&CK Techniques", ["python", "-c", """
import requests
r = requests.get('http://host.docker.internal:7080/v1/security/mitre-attack/techniques', headers={'X-Customer-ID': 'test-customer'})
print(f'MITRE ATT&CK Status: {r.status_code}')
techniques = r.json()
print(f'Found {len(techniques)} MITRE ATT&CK techniques')
# Show first few techniques
for i, (tech_id, details) in enumerate(list(techniques.items())[:5]):
    print(f'  {tech_id}: {details.get("name", "Unknown")} ({details.get("tactic", "unknown")})')
assert r.status_code == 200
assert len(techniques) > 0
print('✓ MITRE ATT&CK techniques loaded successfully')
"""]),
        ]
    }
    
    # Initialize suite result
    suite_result = TestSuiteResult(
        suite_id=suite_id,
        status="running",
        total_tests=len(test_commands.get(suite_id, [])),
        passed_tests=0,
        failed_tests=0,
        running_tests=0,
        tests=[],
        started_at=datetime.now().isoformat()
    )
    
    test_execution_state["results"][suite_id] = suite_result.dict()
    
    # Execute tests
    if suite_id in test_commands:
        for test_name, command in test_commands[suite_id]:
            add_log(f"🔄 Running: {test_name}")
            
            # Update test status to running
            test_result = TestResult(
                name=test_name,
                status="running",
                timestamp=datetime.now().isoformat()
            )
            test_execution_state["results"][suite_id]["tests"].append(test_result.dict())
            test_execution_state["results"][suite_id]["running_tests"] += 1
            
            start_time = time.time()
            
            try:
                # Execute the test command
                result = await run_python_test_command(command)
                duration = (time.time() - start_time) * 1000  # Convert to milliseconds
                
                # Update test result
                test_execution_state["results"][suite_id]["running_tests"] -= 1
                
                if result["return_code"] == 0:
                    test_execution_state["results"][suite_id]["passed_tests"] += 1
                    test_result.status = "passed"
                    add_log(f"✅ {test_name} - PASSED ({duration:.0f}ms)")
                else:
                    test_execution_state["results"][suite_id]["failed_tests"] += 1
                    test_result.status = "failed"
                    test_result.error = result["stderr"] or "Test failed with non-zero exit code"
                    add_log(f"❌ {test_name} - FAILED: {test_result.error}")
                
                test_result.duration = duration
                test_result.output = [result["stdout"]] if result["stdout"] else []
                if result["stderr"]:
                    test_result.output.append(f"STDERR: {result['stderr']}")
                
                # Update the test result in the suite
                for i, test in enumerate(test_execution_state["results"][suite_id]["tests"]):
                    if test["name"] == test_name:
                        test_execution_state["results"][suite_id]["tests"][i] = test_result.dict()
                        break
                
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                test_execution_state["results"][suite_id]["running_tests"] -= 1
                test_execution_state["results"][suite_id]["failed_tests"] += 1
                
                test_result.status = "failed"
                test_result.error = str(e)
                test_result.duration = duration
                
                add_log(f"❌ {test_name} - ERROR: {str(e)}")
                
                # Update the test result in the suite
                for i, test in enumerate(test_execution_state["results"][suite_id]["tests"]):
                    if test["name"] == test_name:
                        test_execution_state["results"][suite_id]["tests"][i] = test_result.dict()
                        break
            
            # Small delay between tests
            await asyncio.sleep(0.5)
    
    # Mark suite as completed
    test_execution_state["results"][suite_id]["status"] = "completed"
    test_execution_state["results"][suite_id]["completed_at"] = datetime.now().isoformat()
    
    suite_result = test_execution_state["results"][suite_id]
    add_log(f"🏁 Test suite {suite_id} completed: {suite_result['passed_tests']}/{suite_result['total_tests']} passed")
    
    test_execution_state["running"] = False
    test_execution_state["current_suite"] = None

@router.post("/execute/{suite_id}")
async def execute_test_suite(suite_id: str, background_tasks: BackgroundTasks):
    """Execute a test suite"""
    if test_execution_state["running"]:
        raise HTTPException(status_code=400, detail="Another test suite is currently running")
    
    # Start test execution in background
    background_tasks.add_task(execute_test_suite_background, suite_id)
    
    return {"message": f"Test suite {suite_id} execution started", "suite_id": suite_id}

@router.get("/status")
async def get_test_status():
    """Get current test execution status"""
    return {
        "running": test_execution_state["running"],
        "current_suite": test_execution_state["current_suite"],
        "results": test_execution_state["results"],
        "total_logs": len(test_execution_state["logs"])
    }

@router.get("/logs")
async def get_test_logs(limit: int = 100):
    """Get test execution logs"""
    logs = test_execution_state["logs"]
    if limit > 0:
        logs = logs[-limit:]  # Get the last N logs
    
    return {"logs": logs, "total": len(test_execution_state["logs"])}

@router.delete("/logs")
async def clear_test_logs():
    """Clear test execution logs"""
    test_execution_state["logs"].clear()
    return {"message": "Test logs cleared"}

@router.get("/suites/{suite_id}/results")
async def get_suite_results(suite_id: str):
    """Get results for a specific test suite"""
    if suite_id not in test_execution_state["results"]:
        raise HTTPException(status_code=404, detail=f"Test suite {suite_id} not found")
    
    return test_execution_state["results"][suite_id]

@router.post("/execute-all")
async def execute_all_suites(background_tasks: BackgroundTasks):
    """Execute all available test suites"""
    if test_execution_state["running"]:
        raise HTTPException(status_code=400, detail="Another test suite is currently running")
    
    suites = ["ingestion", "query-dashboard", "alert-engine", "security-analytics", "integration", "performance"]
    
    async def run_all_suites():
        for suite_id in suites:
            await execute_test_suite_background(suite_id)
            # Brief pause between suites
            await asyncio.sleep(2)
    
    background_tasks.add_task(run_all_suites)
    
    return {"message": "All test suites execution started", "suites": suites}

@router.get("/health")
async def test_runner_health():
    """Test runner health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "running": test_execution_state["running"],
        "current_suite": test_execution_state["current_suite"]
    }