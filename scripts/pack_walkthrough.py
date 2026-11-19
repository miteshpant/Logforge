#!/usr/bin/env python3
"""
Timed content-pack walkthrough (Phase 7 acceptance, docs/packs.md).

Against a running stack seeded by scripts/bootstrap_demo.py, as the demo
tenant admin:

  1. remove the Linux pack if it is installed (a clean start; not timed)
  2. show the install plan and install the pack            (Settings -> Content Packs)
  3. create an ingest API key                               (Settings -> API keys)
  4. start Vector in Docker with packages/shipper-recipes/vector/vector-linux-pack.toml,
     tailing a scratch directory mounted as /var/log
  5. append auth.log and audit.log lines (the pack's samples, timestamps moved to now)
  6. wait until the events are searchable and parsed
  7. load the pack's dashboard and count the panels that show data
  8. check the pack's rules are enabled and have fired

Every step is timed from the start of step 2; the timings are printed as
JSON (and written to --out). Needs docker and the timberio/vector image.

    python scripts/pack_walkthrough.py --out docs/benchmarks/2026-11-19-pack-walkthrough.json
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bootstrap_demo as demo  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PACK = "linux"
RECIPE = ROOT / "packages/shipper-recipes/vector/vector-linux-pack.toml"
SAMPLES = ROOT / "packages/packs/linux/samples"
IMAGE = os.getenv("VECTOR_IMAGE", "timberio/vector:0.41.1-debian")
CONTAINER = "logforge-walkthrough-vector"
RULES = ["linux-ssh-invalid-user", "linux-sudo-root-shell", "linux-auditd-exec-from-tmp", "linux-auditd-shadow-read"]


def call(method, path, body=None, *, token, tenant, ok=(200,)):
    status, data = demo.call(method, path, body, token=token, tenant=tenant)
    if status not in ok:
        raise SystemExit(f"{method} {path}: HTTP {status}: {str(data)[:300]}")
    return data


def wait(what, check, timeout=600, every=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = check()
        if result:
            return result
        time.sleep(every)
    raise SystemExit(f"timed out waiting for {what}")


def now_lines(host: str):
    """The pack's auth and audit samples, on host `host`, stamped now."""
    now = datetime.now(timezone.utc)
    stamp = f"{now:%b} {now.day:>2} {now:%H:%M:%S}"   # syslog pads the day with a space
    auth = [re.sub(r"^\w{3} +\d+ [\d:]{8} \S+", f"{stamp} {host}", line)
            for line in (SAMPLES / "auth.log").read_text().splitlines() if line.strip()]
    epoch = f"{now.timestamp():.3f}"
    audit = [re.sub(r"audit\(\d+\.\d+:", f"audit({epoch}:", line)
             for line in (SAMPLES / "audit.log").read_text().splitlines() if line.strip()]
    return auth, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", help="write the timings here as JSON")
    parser.add_argument("--keep", action="store_true", help="leave the pack installed afterwards")
    args = parser.parse_args()
    if not shutil.which("docker"):
        raise SystemExit("docker is needed to run Vector")

    admin = demo.admin_token()
    tenant = demo.tenant_id(admin)
    status, login = demo.call("POST", "/v1/auth/login", {"email": demo.CFG["DEMO_USER_EMAIL"],
                                                         "password": demo.CFG["DEMO_USER_PASSWORD"]})
    if status != 200:
        raise SystemExit("demo user cannot log in; run scripts/bootstrap_demo.py")
    token = login.get("access_token") or login["token"]
    kw = {"token": token, "tenant": tenant}

    if call("GET", f"/v1/packs/{PACK}", **kw).get("installed"):
        call("DELETE", f"/v1/packs/{PACK}", **kw)
    subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)

    steps = []
    t0 = time.time()

    def mark(name, **detail):
        steps.append({"step": name, "at_s": round(time.time() - t0, 1), **detail})
        print(f"{steps[-1]['at_s']:7.1f}s  {name}  {json.dumps(detail) if detail else ''}", flush=True)

    plan = call("POST", f"/v1/packs/{PACK}/plan", **kw)
    mark("plan shown", counts={k: v for k, v in plan["counts"].items() if v})
    installed = call("POST", f"/v1/packs/{PACK}/install", **kw)
    mark("pack installed", objects=len(installed["installed"]["objects"]))

    key = call("POST", "/v1/enterprise/auth/api-keys", {"name": f"vector-walkthrough-{int(t0)}",
                                                        "permissions": ["logs:write"]}, **kw)
    api_key = key.get("api_key") or key.get("key")
    mark("API key created")

    logdir = Path(tempfile.mkdtemp(prefix="lf-walk-"))
    (logdir / "audit").mkdir()
    for f in ("auth.log", "audit/audit.log", "syslog"):
        (logdir / f).touch()
    os.chmod(logdir, 0o755)
    host = f"walk-{int(t0)}"
    subprocess.run(["docker", "run", "-d", "--name", CONTAINER, "--network", "host", "--hostname", host,
                    "-v", f"{logdir}:/var/log", "-v", f"{RECIPE}:/etc/vector/vector.toml:ro",
                    "-e", f"LOGFORGE_API_KEY={api_key}", "-e", f"LOGFORGE_URL={demo.API}",
                    IMAGE, "--config", "/etc/vector/vector.toml"], check=True, capture_output=True)
    wait("Vector to watch the files", lambda: "Found new file to watch" in subprocess.run(
        ["docker", "logs", CONTAINER], capture_output=True, text=True).stderr, timeout=120, every=1)
    mark("Vector running")

    auth, audit = now_lines(host)
    with open(logdir / "auth.log", "a") as f:
        f.write("\n".join(auth) + "\n")
    with open(logdir / "audit/audit.log", "a") as f:
        f.write("\n".join(audit) + "\n")
    mark("lines written", auth=len(auth), audit=len(audit))

    # auth lines name the host in their header; audit lines get Vector's hostname.
    # Parsed: the pack's pipeline extracted its fields (sshd: OCSF auth; sudo: sudo_*; auditd: audit_*)
    query = (f'| where host = "{host}" | eval p = if(isnotnull(attrs.ocsf.class_uid) or isnotnull(attrs.sudo_user) '
             f'or isnotnull(attrs.audit_type), 1, 0) '
             f'| stats count() as events, sum(p) as parsed by service | last 1h')

    def parsed():
        rows = call("POST", "/v1/query/logql", {"query": query}, **kw).get("logs") or []
        by = {r["service"]: r for r in rows}   # the syslog step names auth lines by program: sshd, sudo
        return by if sum(int(r["parsed"] or 0) for r in rows) >= len(auth) + len(audit) else None

    by_service = wait("parsed events", parsed, timeout=300)
    mark("events parsed", **{s: {"events": r["events"], "parsed": r["parsed"]} for s, r in by_service.items()})

    dashboards = call("GET", "/v1/dashboards", **kw)
    items = dashboards.get("dashboards") if isinstance(dashboards, dict) else dashboards
    board = next(d for d in items if d.get("name") == "Linux overview")
    board_id = board.get("id") or board.get("dashboard_id")
    data = call("GET", f"/v1/dashboards/{board_id}/data?var-host={host}", **kw)

    def shows_data(w):
        d = w.get("data") or {}
        return bool(d.get("rows") or d.get("value") not in (None, 0) or any(
            any(v for v in s.get("data", [])) for s in d.get("series", []) or []))

    panels = data.get("widgets") or []
    mark("dashboard loaded", panels=len(panels), with_data=sum(1 for w in panels if shows_data(w)),
         empty=[w["name"] for w in panels if not shows_data(w)])

    listed = {r["id"]: r for r in call("GET", "/v1/security/sigma-rules", **kw)}
    enabled = {r: bool(listed.get(r, {}).get("enabled")) for r in RULES}

    def fired():
        counts = {}
        for r in RULES:
            events = call("GET", f"/v1/security/rules/{r}/events", **kw).get("events") or []
            counts[r] = sum(1 for e in events if host in json.dumps(e.get("raw_log_data", "")))
        return counts if all(counts.values()) else None

    alerts = wait("alerts from this run", fired, timeout=300, every=5)
    mark("rules enabled and fired", enabled=enabled, alerts=alerts)

    subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)
    shutil.rmtree(logdir, ignore_errors=True)
    key_id = key.get("key_id") or key.get("id")
    if key_id:
        call("DELETE", f"/v1/enterprise/auth/api-keys/{key_id}", **kw)
    if not args.keep:
        call("DELETE", f"/v1/packs/{PACK}", **kw)
    result = {"pack": PACK, "vector_image": IMAGE, "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "total_s": steps[-1]["at_s"], "steps": steps}
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"total_s": result["total_s"]}))


if __name__ == "__main__":
    main()
