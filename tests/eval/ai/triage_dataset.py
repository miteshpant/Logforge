#!/usr/bin/env python3
"""
Writes datasets/triage.jsonl: alerts and cases with the evidence a triage
summary is built from (the alert row or case details, related activity per
entity, threat intelligence matches), and the facts a summary must carry.

    python tests/eval/ai/triage_dataset.py
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TS = "2026-11-19T{}:00+00:00"

# (id, title, rule, severity, techniques, entities, event message, activity, intel)
ALERTS = [
    ("ssh-brute", "SSH brute force then success", "ssh_brute_force_success", "high", ["T1110.001"],
     {"src_ip": "45.155.205.233", "user": "root", "hostname": "bastion-01"},
     "Accepted password for root from 45.155.205.233 port 50122 ssh2",
     {"45.155.205.233": [("sshd", "warn", 15), ("sshd", "info", 1)], "root": [("sshd", "info", 4)]},
     {"45.155.205.233": ("bruteforce", 90, "abuse-feed")}),
    ("lsass", "LSASS memory dumped", "lsass_dump", "critical", ["T1003.001"],
     {"user": "bob", "hostname": "WS-043"}, "procdump64.exe -ma lsass.exe lsass.dmp",
     {"WS-043": [("sysmon", "info", 312)], "bob": [("sysmon", "info", 88), ("auth", "info", 6)]}, {}),
    ("shadow", "Volume shadow copies deleted", "shadow_copy_delete", "critical", ["T1490"],
     {"user": "dave", "hostname": "WS-051"}, "vssadmin.exe delete shadows /all /quiet",
     {"WS-051": [("sysmon", "info", 140)]}, {}),
    ("logclear", "Security event log cleared", "log_cleared", "high", ["T1070.001"],
     {"user": "bob", "hostname": "WS-043"}, "wevtutil cl Security", {"WS-043": [("sysmon", "info", 52)]}, {}),
    ("newadmin", "New local administrator", "local_admin_added", "high", ["T1136.001", "T1098"],
     {"user": "svc-backup", "hostname": "srv-files-02"}, "net localgroup administrators svc-backup /add",
     {"svc-backup": [], "srv-files-02": [("windows", "info", 75)]}, {}),
    ("pwsh", "Encoded PowerShell command", "powershell_encoded", "medium", ["T1059.001"],
     {"user": "carol", "hostname": "WS-012"}, "powershell.exe -nop -w hidden -enc SQBFAFgA",
     {"WS-012": [("sysmon", "info", 41)]}, {}),
    ("dnstunnel", "Possible DNS tunnelling", "dns_long_subdomains", "medium", ["T1071.004"],
     {"src_ip": "10.0.4.17", "hostname": "WS-077"}, "query aGVsbG8gd29ybGQ.x7.badcdn.example A",
     {"10.0.4.17": [("dns", "info", 4210)]}, {}),
    ("portscan", "Internal port scan", "port_scan", "medium", ["T1046"],
     {"src_ip": "10.0.9.200"}, "1,024 destination ports in 60s from 10.0.9.200",
     {"10.0.9.200": [("firewall", "warn", 1024)]}, {}),
    ("travel", "Impossible travel", "impossible_travel", "high", ["T1078"],
     {"user": "erin", "src_ip": "185.220.101.4"}, "Sign-in for erin from Romania 40 minutes after Germany",
     {"erin": [("auth", "info", 12)], "185.220.101.4": [("auth", "info", 2)]},
     {"185.220.101.4": ("tor_exit", 70, "tor-exits")}),
    ("webshell", "Web shell request", "webshell_request", "critical", ["T1505.003"],
     {"src_ip": "203.0.113.50", "hostname": "web-1"}, "POST /uploads/cmd.php?c=whoami 200",
     {"203.0.113.50": [("nginx", "info", 37)], "web-1": [("nginx", "info", 18230), ("nginx", "error", 12)]},
     {"203.0.113.50": ("scanner", 60, "honeypot-feed")}),
    ("exfil", "Large outbound transfer", "large_upload", "high", ["T1048"],
     {"src_ip": "10.0.2.31", "dst_ip": "198.51.100.77", "user": "frank"}, "4.2 GB sent to 198.51.100.77:443",
     {"10.0.2.31": [("firewall", "info", 220)], "198.51.100.77": [("firewall", "info", 3)]},
     {"198.51.100.77": ("c2", 85, "c2-tracker")}),
    ("beacon", "Periodic beacon to rare domain", "c2_beacon", "high", ["T1071.001"],
     {"src_ip": "10.0.3.8", "dst_ip": "192.0.2.10", "hostname": "WS-030"}, "GET /pixel.gif every 60s ±2s",
     {"10.0.3.8": [("proxy", "info", 1440)]}, {"192.0.2.10": ("c2", 95, "c2-tracker")}),
    ("sudo", "Sudo to root by unexpected user", "sudo_root", "medium", ["T1548.003"],
     {"user": "intern1", "hostname": "db-02"}, "intern1 : TTY=pts/0 ; COMMAND=/bin/bash",
     {"intern1": [("sudo", "info", 3)]}, {}),
    ("cron", "New cron job runs from /tmp", "cron_tmp", "high", ["T1053.003"],
     {"hostname": "app-3"}, "*/5 * * * * /tmp/.x/upd", {"app-3": [("cron", "info", 288)]}, {}),
    ("mfa", "MFA push fatigue", "mfa_fatigue", "high", ["T1621"],
     {"user": "grace", "src_ip": "102.89.34.1"}, "23 MFA push requests denied for grace in 10 minutes",
     {"grace": [("auth", "warn", 23), ("auth", "info", 1)]}, {}),
    ("noattack", "Disk nearly full", "disk_full", "low", [],
     {"hostname": "log-01"}, "filesystem /var at 96%", {"log-01": [("node", "warn", 6)]}, {}),
]

CASES = [
    ("case-bastion", "bastion-01 compromise", "investigating", "critical",
     {"src_ip": ["45.155.205.233"], "hostname": ["bastion-01"]}, ["ssh-brute", "newadmin"]),
    ("case-ws043", "Credential theft on WS-043", "new", "critical",
     {"hostname": ["WS-043"], "user": ["bob"]}, ["lsass", "logclear"]),
    ("case-exfil", "Data leaving through 198.51.100.77", "contained", "high",
     {"dst_ip": ["198.51.100.77"]}, ["exfil", "beacon"]),
    ("case-ransom", "Ransomware precursors on WS-051", "investigating", "critical",
     {"hostname": ["WS-051"]}, ["shadow", "pwsh"]),
]


def _alert_row(spec):
    aid, title, rule, sev, techniques, entities, msg, _, _ = spec
    event = {**entities, "msg": msg}
    return {"id": aid, "rule_id": rule, "title": title, "severity": sev, "status": "open",
            "created_at": TS.format("02:13"), "mitre_techniques": techniques,
            "raw_log_data": {"normalized_log": event}}


def _activity(spec):
    return {value: [{"service": s, "level": lvl, "events": n} for s, lvl, n in rows]
            for value, rows in spec[7].items()}


def _intel(spec):
    return {ip: [{"indicator_type": "ipv4", "value": ip, "threat_type": t, "confidence": c, "source": src,
                  "seen_7d": 3}] for ip, (t, c, src) in spec[8].items()}


def _facts(spec):
    _, title, _, _, techniques, entities, _, _, intel = spec
    return [title, *entities.values(), *techniques, *[v[2] for v in intel.values()]]


def items():
    by_id = {a[0]: a for a in ALERTS}
    for spec in ALERTS:
        yield {"id": f"alert-{spec[0]}", "kind": "alert", "subject_id": spec[0], "alert": _alert_row(spec),
               "activity": _activity(spec), "intel": _intel(spec), "required_facts": _facts(spec)}
    for cid, title, status, sev, entities, alert_ids in CASES:
        from services.case_service import alert_summary

        specs = [by_id[a] for a in alert_ids]
        activity, intel, facts = {}, {}, [title]
        for spec in specs:
            activity.update(_activity(spec))
            intel.update(_intel(spec))
            facts += [spec[1], *spec[4]]
        alerts = [alert_summary(_alert_row(s)) for s in specs]
        yield {"id": cid, "kind": "case", "subject_id": cid,
               "case": {"case": {"id": cid, "title": title, "status": status, "severity": sev, "entities": entities},
                        "alerts": alerts, "timeline": []},
               "activity": activity, "intel": intel, "required_facts": facts}


def main():
    import sys

    sys.path.insert(0, str(HERE.parents[2] / "apps" / "api"))
    out = HERE / "datasets" / "triage.jsonl"
    rows = list(items())
    out.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    print(f"{out}: {len(rows)} items")


if __name__ == "__main__":
    main()
