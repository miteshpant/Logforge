#!/usr/bin/env python3
"""
Writes risk_scenarios.jsonl: entity risk evaluation scenarios (Phase 11).

Each scenario is 14 days of alerts across a few hundred entities, ending
with an intrusion in the last hours, and the compromised entities (the
attacker's address, the user it took over, the host it worked on). Noise:

* background churn: low and medium alerts on random users, hosts and
  addresses, every day;
* an admin host and its admin account with recurring medium alerts (sudo to
  root, a service installed) every day: true but benign;
* an internal vulnerability scanner tripping two high-severity rules
  hundreds of times in the last three days;
* failed-login bursts on random users; low-confidence intel hits on benign
  addresses.

The intrusion varies: the full chain (brute force, new admin, credential
dumping, lateral movement, exfiltration) or a stealthier subset, with or
without an intel hit on the attacker.

    python tests/eval/ueba/risk_scenarios.py
"""

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
END = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)

NOISE_RULES = [("dns_rare_tld", "low", ["T1071.004"]), ("powershell_profile", "low", ["T1059.001"]),
               ("usb_mount", "low", ["T1091"]), ("new_service_port", "medium", ["T1046"]),
               ("failed_login_burst", "medium", ["T1110"]), ("office_macro", "medium", ["T1204.002"]),
               ("archive_tool_run", "low", ["T1560"]), ("rdp_new_source", "medium", ["T1021.001"])]
CHAIN = [("ssh_brute_force_success", "high", ["T1110.001"], ("ip", "user", "host")),
         ("new_local_admin", "critical", ["T1136.001"], ("user", "host")),
         ("lsass_dump", "critical", ["T1003.001"], ("user", "host")),
         ("lateral_rdp_from_host", "high", ["T1021.001"], ("user", "host")),
         ("large_upload_external", "high", ["T1048"], ("host", "ip"))]


def scenario(i: int) -> dict:
    r = random.Random(i)
    users = [f"user{n:03d}" for n in range(150)]
    hosts = [f"ws-{n:03d}" for n in range(80)] + ["adm-01", "jump-01"]
    ips = [f"10.0.{n // 250}.{n % 250 + 1}" for n in range(200)]
    alerts = []

    def add(rule, severity, techniques, at, user=None, host=None, ip=None, threat=None):
        entities = {}
        if user:
            entities["user"] = [user]
        if host:
            entities["hostname"] = [host]
        if ip:
            entities["src_ip"] = [ip]
        alert = {"id": f"s{i}-{len(alerts)}", "rule_id": rule, "title": rule.replace("_", " "), "severity": severity,
                 "ts": at.isoformat(), "mitre_techniques": techniques, "entities": entities}
        if threat:
            alert["threat"] = threat
        alerts.append(alert)

    for day in range(14):
        for _ in range(r.randint(30, 50)):
            rule, sev, tech = r.choice(NOISE_RULES)
            at = END - timedelta(days=day, minutes=r.randint(0, 1439))
            add(rule, sev, tech, at, user=r.choice(users) if r.random() < .7 else None,
                host=r.choice(hosts) if r.random() < .6 else None, ip=r.choice(ips) if r.random() < .4 else None)
        for kind, tech in (("sudo_to_root", ["T1548.003"]), ("service_installed", ["T1543.003"])):
            for _ in range(r.randint(1, 3)):
                add(kind, "medium", tech, END - timedelta(days=day, minutes=r.randint(0, 1439)), user="admin",
                    host="adm-01")
    scanner = "10.9.9.9"
    for _ in range(r.randint(200, 400)):
        at = END - timedelta(minutes=r.randint(0, 3 * 1440))
        rule, tech = r.choice([("port_scan", ["T1046"]), ("web_attack_probe", ["T1190"])])
        add(rule, "high", tech, at, ip=scanner, host=r.choice(hosts))
    for _ in range(5):
        add("intel_match", "low", [], END - timedelta(minutes=r.randint(0, 5 * 1440)), ip=r.choice(ips),
            threat={"max_confidence": r.choice([30, 40, 50]), "sources": ["community-feed"]})

    attacker = f"{r.choice([45, 185, 203])}.{r.randint(1, 250)}.{r.randint(1, 250)}.{r.randint(2, 250)}"
    victim, host = r.choice(users), r.choice(hosts[:80])
    steps = CHAIN if i % 3 == 0 else [CHAIN[0], CHAIN[2], CHAIN[4]] if i % 3 == 1 else [CHAIN[0], CHAIN[1], CHAIN[3]]
    threat = {"max_confidence": 85, "sources": ["abuse-feed"]} if i % 2 == 0 else None
    start = END - timedelta(hours=r.randint(3, 8))
    for k, (rule, sev, tech, names) in enumerate(steps):
        at = start + timedelta(minutes=25 * k + r.randint(0, 10))
        add(rule, sev, tech, at, user=victim if "user" in names else None, host=host if "host" in names else None,
            ip=attacker if "ip" in names else None, threat=threat if "ip" in names else None)
    return {"id": f"risk-{i}", "end": END.isoformat(), "alerts": alerts,
            "compromised": [["ip", attacker], ["user", victim], ["host", host]],
            "chain": [s[0] for s in steps], "attacker_intel": bool(threat)}


def main():
    rows = [scenario(i) for i in range(10)]
    out = HERE / "risk_scenarios.jsonl"
    out.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    print(f"{out}: {len(rows)} scenarios, {sum(len(r['alerts']) for r in rows)} alerts")


if __name__ == "__main__":
    main()
