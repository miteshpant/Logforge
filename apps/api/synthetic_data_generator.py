#!/usr/bin/env python3
"""
Synthetic Test Data Generator for Logforge

Generates realistic log data for testing performance, parsing, and functionality.
Supports multiple log formats and configurable volume/patterns.
"""

import json
import random
import time
import argparse
from datetime import datetime, timezone, timedelta
from faker import Faker
from typing import List, Dict, Any
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

fake = Faker()

class SyntheticLogGenerator:
    """Generate synthetic logs in various formats"""
    
    def __init__(self):
        self.services = ["web-api", "user-service", "payment-service", "notification-service", 
                        "auth-service", "database-proxy", "cache-service", "search-engine"]
        self.hosts = ["web-01", "web-02", "api-01", "api-02", "db-01", "cache-01"]
        self.users = [f"user-{i:06d}" for i in range(1, 10000)]
        self.endpoints = ["/api/users", "/api/orders", "/api/payments", "/api/auth/login", 
                         "/api/auth/logout", "/api/health", "/api/metrics", "/api/search"]
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "curl/7.68.0", "Python-requests/2.28.1", "Go-http-client/1.1"
        ]
    
    def generate_json_log(self, timestamp: datetime = None) -> Dict[str, Any]:
        """Generate a structured JSON log entry"""
        if not timestamp:
            timestamp = datetime.now(timezone.utc)
            
        # Simulate different log patterns
        log_type = random.choice(["request", "error", "info", "performance"])
        
        base_log = {
            "timestamp": timestamp.isoformat(),
            "host": random.choice(self.hosts),
            "service": random.choice(self.services),
            "level": "info",
            "msg": "",
            "trace_id": fake.uuid4(),
            "span_id": fake.uuid4()[:16],
            "user_id": random.choice(self.users),
            "attrs": {}
        }
        
        if log_type == "request":
            method = random.choice(["GET", "POST", "PUT", "DELETE"])
            endpoint = random.choice(self.endpoints)
            status = random.choices([200, 201, 400, 401, 403, 404, 500], 
                                  weights=[60, 10, 5, 8, 3, 5, 9])[0]
            duration_ms = random.randint(10, 2000) if status < 400 else random.randint(100, 5000)
            
            base_log.update({
                "level": "error" if status >= 500 else "warn" if status >= 400 else "info",
                "msg": f"{method} {endpoint} {status} {duration_ms}ms",
                "status": status,
                "src_ip": fake.ipv4(),
                "attrs": {
                    "method": method,
                    "uri": endpoint,
                    "status": status,
                    "duration_ms": duration_ms,
                    "bytes": random.randint(100, 10000),
                    "user_agent": random.choice(self.user_agents),
                    "referrer": fake.url() if random.random() < 0.3 else None
                }
            })
            
        elif log_type == "error":
            error_types = ["DatabaseConnectionError", "ValidationError", "AuthenticationError", 
                          "TimeoutError", "ServiceUnavailableError"]
            error_type = random.choice(error_types)
            
            base_log.update({
                "level": "error",
                "msg": f"{error_type}: {fake.sentence()}",
                "attrs": {
                    "error_type": error_type,
                    "error_code": f"E{random.randint(1000, 9999)}",
                    "stack_trace": self._generate_stack_trace(),
                    "retry_count": random.randint(0, 3)
                }
            })
            
        elif log_type == "performance":
            metric_name = random.choice(["cpu_usage", "memory_usage", "disk_io", "network_io"])
            value = random.uniform(0.1, 100.0)
            
            base_log.update({
                "level": "info",
                "msg": f"Performance metric: {metric_name}={value:.2f}",
                "attrs": {
                    "metric_name": metric_name,
                    "value": value,
                    "unit": "percent" if "usage" in metric_name else "mbps",
                    "threshold_exceeded": value > 80.0
                }
            })
            
        else:  # info log
            actions = ["user_created", "order_processed", "payment_completed", 
                      "cache_miss", "cache_hit", "background_job_completed"]
            action = random.choice(actions)
            
            base_log.update({
                "level": "info", 
                "msg": f"Action completed: {action}",
                "attrs": {
                    "action": action,
                    "execution_time_ms": random.randint(1, 100),
                    "success": random.random() < 0.95
                }
            })
        
        return base_log
    
    def generate_nginx_log(self, timestamp: datetime = None) -> str:
        """Generate Nginx access log entry"""
        if not timestamp:
            timestamp = datetime.now(timezone.utc)
            
        ip = fake.ipv4()
        user = random.choice(["-"] + self.users[:100])  # Most requests are anonymous
        method = random.choice(["GET", "POST", "PUT", "DELETE"])
        endpoint = random.choice(self.endpoints + ["/static/css/style.css", "/static/js/app.js", 
                                                  "/favicon.ico", "/robots.txt"])
        status = random.choices([200, 201, 304, 400, 401, 403, 404, 500], 
                              weights=[50, 5, 10, 8, 5, 3, 10, 9])[0]
        bytes_sent = random.randint(200, 50000)
        referrer = fake.url() if random.random() < 0.4 else "-"
        user_agent = random.choice(self.user_agents)
        
        time_str = timestamp.strftime("%d/%b/%Y:%H:%M:%S %z")
        
        return (f'{ip} - {user} [{time_str}] '
                f'"{method} {endpoint} HTTP/1.1" {status} {bytes_sent} '
                f'"{referrer}" "{user_agent}"')
    
    def generate_syslog_message(self, timestamp: datetime = None) -> str:
        """Generate RFC 3164 syslog message"""
        if not timestamp:
            timestamp = datetime.now(timezone.utc)
            
        # Priority = facility * 8 + severity
        facilities = {"kern": 0, "user": 1, "daemon": 3, "auth": 4, "syslog": 5, 
                     "mail": 2, "news": 7, "local0": 16, "local1": 17}
        severities = {"emerg": 0, "alert": 1, "crit": 2, "err": 3, 
                     "warning": 4, "notice": 5, "info": 6, "debug": 7}
        
        facility = random.choice(list(facilities.keys()))
        severity = random.choice(list(severities.keys()))
        priority = facilities[facility] * 8 + severities[severity]
        
        host = random.choice(self.hosts)
        service = random.choice(self.services)
        pid = random.randint(1000, 99999)
        
        messages = [
            "Connection established from client",
            "Authentication successful for user",
            "Service started successfully", 
            "Configuration reloaded",
            "Database connection pool exhausted",
            "Backup completed successfully",
            "Certificate renewal required",
            "Disk space low on /var partition"
        ]
        
        message = random.choice(messages)
        time_str = timestamp.strftime("%b %d %H:%M:%S")
        
        return f"<{priority}>{time_str} {host} {service}[{pid}]: {message}"
    
    def generate_cef_log(self, timestamp: datetime = None) -> str:
        """Generate Common Event Format log"""
        if not timestamp:
            timestamp = datetime.now(timezone.utc)
            
        events = [
            ("100", "User Login", "3", "msg=Successful user authentication"),
            ("101", "User Logout", "3", "msg=User session terminated"),
            ("200", "File Access", "5", "msg=Unauthorized file access attempt"),
            ("201", "System Alert", "8", "msg=Critical system resource threshold exceeded"),
            ("300", "Network Event", "4", "msg=Suspicious network activity detected")
        ]
        
        event_id, name, severity, extension = random.choice(events)
        
        # Add standard CEF fields
        src_ip = fake.ipv4()
        dst_ip = fake.ipv4()
        user = random.choice(self.users)
        
        extension += f" src={src_ip} dst={dst_ip} suser={user} start={timestamp.strftime('%b %d %Y %H:%M:%S')}"
        
        return f"CEF:0|Logforge|TestSystem|1.0|{event_id}|{name}|{severity}|{extension}"
    
    def _generate_stack_trace(self) -> str:
        """Generate realistic stack trace"""
        files = ["main.py", "auth.py", "database.py", "utils.py", "models.py"]
        functions = ["handle_request", "authenticate_user", "execute_query", "validate_input", "process_data"]
        
        trace_lines = []
        for i in range(random.randint(3, 8)):
            file_name = random.choice(files)
            function = random.choice(functions)
            line_num = random.randint(10, 500)
            trace_lines.append(f"  File \"{file_name}\", line {line_num}, in {function}")
            
        return "\n".join(trace_lines)


class LogShipper:
    """Ship generated logs to Logforge API"""
    
    def __init__(self, base_url: str = "http://localhost:7080"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.stats = {
            "sent": 0,
            "errors": 0,
            "start_time": time.time()
        }
        
    def ship_json_logs(self, logs: List[Dict[str, Any]], batch_size: int = 100) -> int:
        """Ship JSON logs to Logforge"""
        success_count = 0
        
        for i in range(0, len(logs), batch_size):
            batch = logs[i:i+batch_size]
            
            try:
                if len(batch) == 1:
                    # Single log
                    response = self.session.post(
                        f"{self.base_url}/v1/ingest/logs",
                        json=batch[0],
                        timeout=30
                    )
                else:
                    # Batch logs
                    response = self.session.post(
                        f"{self.base_url}/v1/ingest/logs/batch",
                        json={"logs": batch},
                        timeout=30
                    )
                
                if response.status_code in [200, 202]:
                    success_count += len(batch)
                    self.stats["sent"] += len(batch)
                else:
                    print(f"API Error: {response.status_code} - {response.text[:200]}")
                    self.stats["errors"] += len(batch)
                    
            except Exception as e:
                print(f"Network Error: {e}")
                self.stats["errors"] += len(batch)
                
        return success_count
    
    def ship_nginx_logs(self, logs: List[str]) -> int:
        """Ship Nginx logs to dedicated endpoint"""
        success_count = 0
        
        for log_line in logs:
            try:
                response = self.session.post(
                    f"{self.base_url}/v1/ingest/nginx",
                    data=log_line,
                    headers={"Content-Type": "text/plain"},
                    timeout=30
                )
                
                if response.status_code in [200, 202]:
                    success_count += 1
                    self.stats["sent"] += 1
                else:
                    self.stats["errors"] += 1
                    
            except Exception as e:
                print(f"Error shipping nginx log: {e}")
                self.stats["errors"] += 1
                
        return success_count
    
    def ship_syslog_messages(self, messages: List[str]) -> int:
        """Ship syslog messages to dedicated endpoint"""
        success_count = 0
        
        for message in messages:
            try:
                response = self.session.post(
                    f"{self.base_url}/v1/ingest/syslog",
                    data=message,
                    headers={"Content-Type": "text/plain"},
                    timeout=30
                )
                
                if response.status_code in [200, 202]:
                    success_count += 1
                    self.stats["sent"] += 1
                else:
                    self.stats["errors"] += 1
                    
            except Exception:
                self.stats["errors"] += 1
                
        return success_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get shipping statistics"""
        elapsed = time.time() - self.stats["start_time"]
        return {
            **self.stats,
            "elapsed_seconds": elapsed,
            "logs_per_second": self.stats["sent"] / elapsed if elapsed > 0 else 0
        }


def generate_time_series_logs(generator: SyntheticLogGenerator, 
                            count: int, 
                            start_time: datetime,
                            time_span_seconds: int) -> List[Dict[str, Any]]:
    """Generate logs distributed over a time period"""
    logs = []
    
    for i in range(count):
        # Distribute logs over time span
        offset_seconds = (i / count) * time_span_seconds
        timestamp = start_time + timedelta(seconds=offset_seconds)
        
        log = generator.generate_json_log(timestamp)
        logs.append(log)
    
    return logs


def load_test_runner(args):
    """Run load test against Logforge API"""
    print(f"Starting load test: {args.count} logs over {args.duration}s")
    print(f"Target: {args.count // args.duration} logs/second")
    print(f"Threads: {args.threads}")
    print("-" * 50)
    
    generator = SyntheticLogGenerator()
    shipper = LogShipper(args.url)
    
    # Generate all logs upfront
    start_time = datetime.now(timezone.utc) - timedelta(hours=1)
    logs = generate_time_series_logs(generator, args.count, start_time, 3600)
    
    # Split logs among threads
    chunk_size = args.count // args.threads
    log_chunks = [logs[i:i+chunk_size] for i in range(0, args.count, chunk_size)]
    
    # Run load test
    test_start = time.time()
    
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = []
        
        for chunk in log_chunks:
            future = executor.submit(shipper.ship_json_logs, chunk, args.batch_size)
            futures.append(future)
        
        # Wait for completion
        for future in as_completed(futures):
            try:
                result = future.result()
                print(f"Thread completed: {result} logs shipped")
            except Exception as e:
                print(f"Thread failed: {e}")
    
    test_elapsed = time.time() - test_start
    stats = shipper.get_stats()
    
    print("-" * 50)
    print(f"Load test completed in {test_elapsed:.2f} seconds")
    print(f"Logs sent: {stats['sent']}")
    print(f"Errors: {stats['errors']}")
    print(f"Effective rate: {stats['sent'] / test_elapsed:.0f} logs/second")
    print(f"Success rate: {stats['sent'] / (stats['sent'] + stats['errors']) * 100:.1f}%")


def main():
    parser = argparse.ArgumentParser(description="Logforge Synthetic Data Generator")
    parser.add_argument("--count", "-c", type=int, default=1000, 
                       help="Number of logs to generate")
    parser.add_argument("--format", "-f", choices=["json", "nginx", "syslog", "cef", "mixed"],
                       default="json", help="Log format to generate")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument("--ship", action="store_true", 
                       help="Ship logs to Logforge API instead of printing")
    parser.add_argument("--url", default="http://localhost:7080",
                       help="Logforge API URL")
    parser.add_argument("--batch-size", type=int, default=100,
                       help="Batch size for shipping")
    parser.add_argument("--load-test", action="store_true",
                       help="Run load test")
    parser.add_argument("--duration", type=int, default=60,
                       help="Load test duration in seconds")
    parser.add_argument("--threads", type=int, default=4,
                       help="Number of threads for load test")
    
    args = parser.parse_args()
    
    if args.load_test:
        load_test_runner(args)
        return
    
    generator = SyntheticLogGenerator()
    
    # Generate logs
    logs = []
    
    if args.format == "json" or args.format == "mixed":
        for _ in range(args.count if args.format == "json" else args.count // 2):
            logs.append(generator.generate_json_log())
    
    if args.format == "mixed":
        # Add other formats for mixed
        for _ in range(args.count // 6):
            logs.append({"nginx_log": generator.generate_nginx_log()})
            logs.append({"syslog_msg": generator.generate_syslog_message()}) 
            logs.append({"cef_log": generator.generate_cef_log()})
    
    # Output or ship logs
    if args.ship:
        shipper = LogShipper(args.url)
        
        if args.format == "json":
            success = shipper.ship_json_logs(logs, args.batch_size)
        elif args.format == "nginx":
            nginx_logs = [generator.generate_nginx_log() for _ in range(args.count)]
            success = shipper.ship_nginx_logs(nginx_logs)
        elif args.format == "syslog":
            syslog_msgs = [generator.generate_syslog_message() for _ in range(args.count)]
            success = shipper.ship_syslog_messages(syslog_msgs)
        
        stats = shipper.get_stats()
        print(f"Shipped {success} logs successfully")
        print(f"Rate: {stats['logs_per_second']:.0f} logs/second")
        print(f"Errors: {stats['errors']}")
        
    else:
        # Output to file or stdout
        output = []
        for log in logs:
            if isinstance(log, dict) and "nginx_log" in log:
                output.append(log["nginx_log"])
            elif isinstance(log, dict) and "syslog_msg" in log:
                output.append(log["syslog_msg"]) 
            elif isinstance(log, dict) and "cef_log" in log:
                output.append(log["cef_log"])
            else:
                output.append(json.dumps(log))
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write('\n'.join(output))
            print(f"Generated {len(output)} logs to {args.output}")
        else:
            print('\n'.join(output))


if __name__ == "__main__":
    main()