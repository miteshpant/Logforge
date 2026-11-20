"""
Reference entries for "explain this event" (Phase 9): what kinds of event
are, and what common fields mean. They are cited like evidence, so an
explanation can say "a failed Windows logon" and point at where that comes
from. Plain data; extend freely.
"""

from __future__ import annotations

import re

WINDOWS_EVENTS = {
    1102: "the Security audit log was cleared",
    4624: "a successful Windows logon",
    4625: "a failed Windows logon",
    4634: "a Windows logoff",
    4648: "a logon with explicitly given credentials (runas, or a network logon as another user)",
    4672: "special privileges assigned to a new logon (an administrator-equivalent logon)",
    4688: "a new process was created",
    4697: "a service was installed",
    4698: "a scheduled task was created",
    4719: "the system audit policy was changed",
    4720: "a user account was created",
    4722: "a user account was enabled",
    4724: "an attempt to reset an account's password",
    4726: "a user account was deleted",
    4728: "a member was added to a global security group",
    4732: "a member was added to a local security group",
    4740: "a user account was locked out",
    4756: "a member was added to a universal security group",
    4768: "a Kerberos ticket-granting ticket was requested",
    4769: "a Kerberos service ticket was requested",
    4771: "Kerberos pre-authentication failed",
    4776: "a domain controller validated an account's credentials (NTLM)",
    7045: "a new service was installed",
}

SYSMON_EVENTS = {
    1: "Sysmon: a process was created",
    3: "Sysmon: a network connection was made",
    7: "Sysmon: an image (DLL) was loaded",
    8: "Sysmon: a thread was created in another process (CreateRemoteThread)",
    10: "Sysmon: a process opened another process (process access)",
    11: "Sysmon: a file was created",
    12: "Sysmon: a registry key was created or deleted",
    13: "Sysmon: a registry value was set",
    22: "Sysmon: a DNS query was made",
}

AUDIT_TYPES = {
    "SYSCALL": "an audited system call (auditd)",
    "EXECVE": "the arguments of a program that was run (auditd)",
    "PATH": "a file path touched by an audited call (auditd)",
    "USER_LOGIN": "a user login (auditd)",
    "USER_AUTH": "an authentication attempt (auditd)",
    "USER_CMD": "a command run through sudo (auditd)",
    "USER_START": "a user session started (auditd)",
    "CRED_ACQ": "credentials acquired for a session (auditd)",
    "ADD_USER": "a user account was added (auditd)",
    "DEL_USER": "a user account was deleted (auditd)",
    "ADD_GROUP": "a group was added (auditd)",
    "CONFIG_CHANGE": "the audit configuration was changed (auditd)",
    "AVC": "an SELinux access decision (auditd)",
    "ANOM_ABEND": "a process ended abnormally (auditd)",
}

# (pattern on msg, service pattern or None, what it is)
MESSAGES = [
    (r"Failed password for (?:invalid user )?\S+ from", r"ssh", "a failed SSH password login"),
    (r"Accepted (?:password|publickey|keyboard-interactive\S*) for", r"ssh", "a successful SSH login"),
    (r"Invalid user \S+ from", r"ssh", "an SSH login attempt for a user that doesn't exist"),
    (r"\bCOMMAND=", r"sudo", "a command run with sudo"),
    (r"authentication failure", None, "an authentication failure"),
    (r"session opened for user", None, "a login session was opened"),
    (r"\bCMD \(", r"cron", "a scheduled job started by cron"),
    (r"^(?:Started|Starting|Stopped|Stopping) ", r"systemd", "systemd starting or stopping a unit (a service, timer or mount)"),
    (r"upstream timed out", r"nginx", "a request that timed out waiting for the upstream server"),
    (r'open\(\) "[^"]*" failed', r"nginx", "a request for a file that doesn't exist or can't be read"),
    (r"(?i)\bsegfault\b", None, "a program crashed (segmentation fault)"),
    (r"(?i)out of memory|oom-kill", None, "the kernel killed a process for lack of memory"),
]

OCSF_CLASSES = {
    1001: "OCSF File System Activity", 1007: "OCSF Process Activity", 2004: "OCSF Detection Finding",
    3001: "OCSF Account Change", 3002: "OCSF Authentication", 3003: "OCSF Authorize Session",
    3005: "OCSF User Access Management", 4001: "OCSF Network Activity", 4002: "OCSF HTTP Activity",
    4003: "OCSF DNS Activity", 6003: "OCSF API Activity",
}

LOGON_TYPES = {2: "interactive (at the keyboard)", 3: "network (a share or remote service)", 4: "batch",
               5: "service", 7: "unlock", 8: "network with a cleartext password", 9: "new credentials (runas)",
               10: "remote interactive (RDP)", 11: "cached interactive"}

# field name (last path segment, lower case) -> meaning
FIELDS = {
    "ts": "When the event happened (UTC).",
    "service": "The program or source that logged the event.",
    "host": "The machine that logged the event.",
    "hostname": "The machine the event is about.",
    "level": "The severity the source gave the event (debug, info, warn, error).",
    "src_ip": "The address the activity came from.",
    "source_ip": "The address the activity came from.",
    "client_ip": "The address of the client that made the request.",
    "dst_ip": "The address the activity went to.",
    "dest_ip": "The address the activity went to.",
    "src_port": "The source port of the connection.",
    "dst_port": "The destination port of the connection (the service reached).",
    "user_id": "The user the event is about.",
    "user": "The user the event is about.",
    "username": "The user the event is about.",
    "trace_id": "Ties together the events of one request across services.",
    "status": "The HTTP status: 2xx success, 3xx redirect, 4xx client error, 5xx server error.",
    "status_code": "The HTTP status: 2xx success, 3xx redirect, 4xx client error, 5xx server error.",
    "method": "The HTTP method of the request.",
    "path": "The path of the request.",
    "url": "The address requested.",
    "user_agent": "The client software that made the request, as it described itself.",
    "duration_ms": "How long the request took, in milliseconds.",
    "bytes": "The size of the response, in bytes.",
    "event_id": "The Windows or Sysmon event ID: what kind of event this is.",
    "eventid": "The Windows or Sysmon event ID: what kind of event this is.",
    "logon_type": "How the account logged on (Windows logon type: 2 interactive, 3 network, 10 RDP, ...).",
    "logontype": "How the account logged on (Windows logon type: 2 interactive, 3 network, 10 RDP, ...).",
    "process_name": "The program that ran.",
    "image": "The program that ran.",
    "command_line": "The full command the program ran with.",
    "commandline": "The full command the program ran with.",
    "parent_process": "The program that started this one.",
    "parentimage": "The program that started this one.",
    "file_path": "The file the event is about.",
    "domain": "The domain name looked up or reached.",
    "query": "The name looked up.",
    "action": "What was done (allow, deny, ...).",
    "outcome": "Whether the action succeeded.",
    "result": "Whether the action succeeded.",
    "class_uid": "The OCSF event class: the kind of event in the common schema.",
    "status_id": "The OCSF status: 1 success, 2 failure.",
    "parse_error": "The ingest pipeline couldn't parse the original line; the event was kept as it arrived.",
    "matched": "The event matched threat intelligence when it was ingested.",
    "country": "The country its address is located in (GeoIP).",
}


def message_kind(service: str, msg: str) -> str | None:
    for pattern, service_pattern, what in MESSAGES:
        if (service_pattern is None or re.search(service_pattern, service or "", re.I)) and re.search(pattern, msg):
            return what
    return None


def http_kind(status: int) -> str | None:
    if 500 <= status < 600:
        return f"an HTTP request that failed with a server error ({status})"
    if 400 <= status < 500:
        return f"an HTTP request refused as a client error ({status})"
    if 200 <= status < 400:
        return f"a successful HTTP request ({status})"
    return None
