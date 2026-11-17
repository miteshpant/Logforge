"""
Deterministic benign corpus: ordinary activity from a small company.

Every alert a rule raises on these events is a false positive. The mix is
deliberately realistic rather than sanitised: admins run sudo and
PowerShell, people mistype passwords, scanners hit 404s, backups move data.
Field names follow Logforge's normalised schema (what the rules match on).

Deterministic (fixed seed), so evaluation results are reproducible.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

SEED = 1337

USERS = ["alice", "bob", "carol", "dave", "erin", "frank", "grace", "heidi"]
ADMINS = ["ops_admin", "svc_backup"]
LINUX_HOSTS = ["app-01", "app-02", "db-01", "bastion-01"]
WIN_HOSTS = ["WS-042", "WS-043", "WS-044", "WS-051", "LAPTOP-07"]
OFFICE_IPS = [f"10.0.{a}.{b}" for a in (1, 2) for b in range(10, 40)]
PUBLIC_IPS = ["198.51.100.23", "198.51.100.87", "203.0.113.140", "192.0.2.61"]

WIN_PROCESSES = [
    ("C:\\Windows\\explorer.exe", "C:\\Windows\\explorer.exe"),
    ("C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
     '"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --type=renderer'),
    ("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
     '"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"'),
    ("C:\\Windows\\System32\\svchost.exe", "C:\\Windows\\system32\\svchost.exe -k netsvcs -p"),
    ("C:\\Program Files\\Microsoft Office\\root\\Office16\\OUTLOOK.EXE",
     '"C:\\Program Files\\Microsoft Office\\root\\Office16\\OUTLOOK.EXE"'),
    ("C:\\Users\\alice\\AppData\\Local\\Microsoft\\Teams\\current\\Teams.exe",
     "Teams.exe --system-initiated"),
    ("C:\\Windows\\System32\\notepad.exe", "notepad.exe C:\\Users\\bob\\Documents\\notes.txt"),
    ("C:\\Windows\\System32\\cmd.exe", "cmd.exe /c dir C:\\Users\\carol\\Downloads"),
    ("C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
     "powershell.exe -File C:\\scripts\\backup.ps1"),
    ("C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
     "powershell.exe Get-ChildItem C:\\Users\\dave\\Desktop"),
    ("C:\\Windows\\System32\\taskhostw.exe", "taskhostw.exe"),
    ("C:\\Windows\\System32\\SearchIndexer.exe", "C:\\Windows\\system32\\SearchIndexer.exe /Embedding"),
    ("C:\\Program Files\\Git\\cmd\\git.exe", "git.exe pull origin main"),
    ("C:\\Program Files\\nodejs\\node.exe", "node.exe server.js"),
    ("C:\\Windows\\System32\\whoami.exe", "whoami"),
]

WEB_PATHS = ["/", "/index.html", "/login", "/api/orders", "/api/orders/42", "/static/app.js",
             "/static/style.css", "/favicon.ico", "/api/health", "/products?page=2"]
WEB_404 = ["/wp-login.php", "/.env", "/robots.txt", "/old-page"]
AGENTS = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 Safari/605.1.15",
          "curl/8.4.0", "kube-probe/1.28"]
DOMAINS = ["github.com", "slack.com", "office365.com", "google.com", "pypi.org",
           "registry.npmjs.org", "api.stripe.com", "cdn.jsdelivr.net"]


def benign_events(count: int = 2000, seed: int = SEED) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    makers = [
        (_ssh_login, 12), (_sudo, 6), (_cron, 10), (_failed_login, 4), (_windows_logon, 10),
        (_windows_process, 25), (_web_request, 20), (_web_404, 3), (_dns, 6), (_network_flow, 4),
    ]
    population = [m for m, weight in makers for _ in range(weight)]
    return [rng.choice(population)(rng) for _ in range(count)]


def _ssh_login(rng):
    user = rng.choice(USERS + ADMINS)
    return {"service": "sshd", "hostname": rng.choice(LINUX_HOSTS), "user": user,
            "process_name": "/usr/sbin/sshd", "command_line": f"sshd: {user} [priv]",
            "src_ip": rng.choice(OFFICE_IPS), "event_type": "authentication", "result": "success",
            "message": f"Accepted publickey for {user} from {rng.choice(OFFICE_IPS)} port 52144 ssh2"}


def _sudo(rng):
    user = rng.choice(ADMINS)
    cmd = rng.choice(["systemctl restart nginx", "apt-get update", "journalctl -u app",
                      "cat /var/log/syslog", "docker ps"])
    return {"service": "sudo", "hostname": rng.choice(LINUX_HOSTS), "user": user,
            "process_name": "/usr/bin/sudo", "command_line": f"sudo {cmd}",
            "event_type": "sudo", "result": "success",
            "message": f"{user} : TTY=pts/0 ; PWD=/home/{user} ; USER=root ; COMMAND=/usr/bin/{cmd}"}


def _cron(rng):
    return {"service": "cron", "hostname": rng.choice(LINUX_HOSTS), "user": "root",
            "process_name": "/usr/sbin/cron", "command_line": "/usr/sbin/CRON -f",
            "message": "pam_unix(cron:session): session opened for user root"}


def _failed_login(rng):
    user = rng.choice(USERS)
    return {"service": rng.choice(["sshd", "webapp"]), "hostname": rng.choice(LINUX_HOSTS),
            "user": user, "src_ip": rng.choice(OFFICE_IPS),
            "event_type": "authentication", "result": "failed",
            "message": f"Failed password for {user}"}


def _windows_logon(rng):
    user = rng.choice(USERS)
    return {"service": "windows-security", "event_id": 4624, "hostname": rng.choice(WIN_HOSTS),
            "user": user, "process_name": "C:\\Windows\\System32\\winlogon.exe",
            "event_type": "login_success", "status": "success",
            "message": "An account was successfully logged on"}


def _windows_process(rng):
    image, cmd = rng.choice(WIN_PROCESSES)
    return {"service": "sysmon", "event_id": 1, "hostname": rng.choice(WIN_HOSTS),
            "user": rng.choice(USERS), "process_name": image, "command_line": cmd,
            "parent_process_name": "C:\\Windows\\explorer.exe", "message": "Process created"}


def _web_request(rng):
    return {"service": "nginx", "hostname": "web-01", "src_ip": rng.choice(PUBLIC_IPS + OFFICE_IPS),
            "http_method": rng.choice(["GET", "GET", "GET", "POST"]), "url": rng.choice(WEB_PATHS),
            "status_code": rng.choice([200, 200, 200, 304, 201]), "user_agent": rng.choice(AGENTS),
            "bytes_out": rng.randint(200, 90_000), "message": "request completed"}


def _web_404(rng):
    return {"service": "nginx", "hostname": "web-01", "src_ip": rng.choice(PUBLIC_IPS),
            "http_method": "GET", "url": rng.choice(WEB_404), "status_code": 404,
            "user_agent": rng.choice(AGENTS), "message": "not found"}


def _dns(rng):
    return {"service": "dns", "hostname": rng.choice(WIN_HOSTS + LINUX_HOSTS),
            "query": rng.choice(DOMAINS), "event_type": "dns_query", "message": "query resolved"}


def _network_flow(rng):
    return {"service": "netflow", "src_ip": rng.choice(OFFICE_IPS), "dst_ip": rng.choice(PUBLIC_IPS),
            "port": rng.choice([443, 443, 443, 80, 53]), "protocol": rng.choice(["https", "https", "dns", "http"]),
            "bytes_out": rng.randint(500, 400_000), "message": "flow closed"}
