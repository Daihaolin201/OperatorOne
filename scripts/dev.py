#!/usr/bin/env python3
"""OperatorOne dev launcher — one-click multi-service development environment.

Commands:
  dev up       Start all services (dashboard → platform-portal → product-ui)
  dev status   Check health of all services without starting them
  dev down     Gracefully stop all services started by dev up

Usage:
  ./dev up [--dashboard-port PORT] [--portal-port PORT] [--product-port PORT]
           [--timeout SECONDS] [--skip-health-check] [--verbose]
  ./dev status
  ./dev down

Python stdlib only (subprocess, urllib.request, argparse, time, socket, json, os, signal).
PID tracking: .sisyphus/runtime/pids.json
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Repo root detection
# ──────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

# ──────────────────────────────────────────────────────────────────────────────
# PID file location
# ──────────────────────────────────────────────────────────────────────────────

PIDS_FILE = REPO_ROOT / ".sisyphus" / "runtime" / "pids.json"


# ──────────────────────────────────────────────────────────────────────────────
# Service definitions
# ──────────────────────────────────────────────────────────────────────────────

def make_services(
    dashboard_port: int = 8765,
    portal_port: int = 5173,
    product_port: int = 5174,
) -> List[Dict[str, Any]]:
    """Return ordered service configuration list."""
    return [
        {
            "name": "dashboard",
            "type": "Flask",
            "port": dashboard_port,
            "host": "127.0.0.1",
            "health_url": f"http://127.0.0.1:{dashboard_port}/api/health",
            "readiness_url": f"http://127.0.0.1:{dashboard_port}/api/health",
            "cmd": [
                sys.executable,
                str(REPO_ROOT / "dashboard" / "server.py"),
                "--host", "127.0.0.1",
                "--port", str(dashboard_port),
            ],
            "cwd": str(REPO_ROOT / "dashboard"),
            "required_path": REPO_ROOT / "dashboard" / "server.py",
            "app_dir": None,  # Not an apps/ service
            "remediation": "Ensure dashboard/server.py exists and run: pip3 install -r dashboard/requirements.txt",
        },
        {
            "name": "platform-portal",
            "type": "Vite",
            "port": portal_port,
            "host": "127.0.0.1",
            "health_url": f"http://localhost:{portal_port}/healthz",
            "readiness_url": f"http://localhost:{portal_port}/healthz",
            "cmd": ["pnpm", "--filter", "platform-portal", "dev"],
            "cwd": str(REPO_ROOT),
            "required_path": REPO_ROOT / "apps" / "platform-portal",
            "app_dir": REPO_ROOT / "apps" / "platform-portal",
            "remediation": "Run 'pnpm install' in the repo root, then scaffold platform-portal (T8).",
        },
        {
            "name": "product-ui",
            "type": "Vite",
            "port": product_port,
            "host": "127.0.0.1",
            "health_url": f"http://localhost:{product_port}/healthz",
            "readiness_url": f"http://localhost:{product_port}/healthz",
            "cmd": ["pnpm", "--filter", "product-ui", "dev"],
            "cwd": str(REPO_ROOT),
            "required_path": REPO_ROOT / "apps" / "product-ui",
            "app_dir": REPO_ROOT / "apps" / "product-ui",
            "remediation": "Run 'pnpm install' in the repo root, then scaffold product-ui (T9).",
        },
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

PAD_NAME = 18  # column width for service name label


def label(name: str) -> str:
    return f"[{name}]".ljust(PAD_NAME)


def print_err(msg: str) -> None:
    print(msg, file=sys.stderr)


def is_port_free(port: int) -> Tuple[bool, Optional[str]]:
    """Return (free, process_info). free=True means port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        result = s.connect_ex(("127.0.0.1", port))
        if result != 0:
            # Try localhost too
            result2 = s.connect_ex(("localhost", port))
            if result2 != 0:
                return True, None

    # Port is in use — try to get PID via lsof (macOS/Linux)
    try:
        proc = subprocess.run(
            ["lsof", "-Pi", f":{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, timeout=5
        )
        pids = proc.stdout.strip()
        if pids:
            return False, f"PID {pids.splitlines()[0]}"
    except Exception:
        pass
    return False, "unknown process"


def http_get(url: str, timeout: float = 5.0) -> Tuple[Optional[int], float]:
    """Return (status_code, elapsed_ms). status_code=None on failure."""
    start = time.perf_counter()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = (time.perf_counter() - start) * 1000
            return resp.status, elapsed
    except urllib.error.HTTPError as e:
        elapsed = (time.perf_counter() - start) * 1000
        return e.code, elapsed
    except Exception:
        elapsed = (time.perf_counter() - start) * 1000
        return None, elapsed


def load_pids() -> Dict[str, Any]:
    """Load PID tracking file, return empty dict on missing/corrupt."""
    if not PIDS_FILE.exists():
        return {}
    try:
        return json.loads(PIDS_FILE.read_text())
    except Exception:
        return {}


def save_pids(pids: Dict[str, Any]) -> None:
    PIDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PIDS_FILE.write_text(json.dumps(pids, indent=2))


def clear_pids() -> None:
    save_pids({})


# ──────────────────────────────────────────────────────────────────────────────
# Prerequisite checks
# ──────────────────────────────────────────────────────────────────────────────

def check_version_cmd(cmd: List[str], min_major: int, min_minor: int, label_str: str) -> Optional[str]:
    """Run version command, parse major.minor, return error string or None."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        output = (result.stdout + result.stderr).strip()
        # Find first X.Y.Z-like pattern
        import re
        match = re.search(r"(\d+)\.(\d+)", output)
        if not match:
            return f"{label_str}: could not parse version from: {output!r}"
        major, minor = int(match.group(1)), int(match.group(2))
        if (major, minor) < (min_major, min_minor):
            return f"{label_str}: {min_major}.{min_minor}+ required (found {major}.{minor})"
        return None
    except FileNotFoundError:
        return f"{label_str}: command not found ({cmd[0]})"
    except Exception as e:
        return f"{label_str}: check failed ({e})"


def run_prereq_checks(services: List[Dict[str, Any]], verbose: bool = False) -> bool:
    """Run all prerequisite checks. Return True if all pass."""
    print("[dev up] Checking prerequisites...")
    errors: List[str] = []

    # Python version
    err = check_version_cmd([sys.executable, "--version"], 3, 8, "Python 3.8+")
    if err:
        errors.append(err)
    elif verbose:
        print("[dev up]   ✓ Python OK")

    # Node.js
    err = check_version_cmd(["node", "--version"], 18, 0, "Node.js 18.0+")
    if err:
        errors.append(err)
    elif verbose:
        print("[dev up]   ✓ Node.js OK")

    # pnpm
    err = check_version_cmd(["pnpm", "--version"], 7, 0, "pnpm 7.0+")
    if err:
        errors.append(err)
    elif verbose:
        print("[dev up]   ✓ pnpm OK")

    # dashboard/server.py
    if not (REPO_ROOT / "dashboard" / "server.py").exists():
        errors.append("dashboard/server.py not found — cannot start dashboard service")

    # pnpm-workspace.yaml
    if not (REPO_ROOT / "pnpm-workspace.yaml").exists():
        errors.append("pnpm-workspace.yaml not found — pnpm workspace not configured")
    elif verbose:
        print("[dev up]   ✓ pnpm-workspace.yaml OK")

    # node_modules warning (warn only, don't fail)
    if not (REPO_ROOT / "node_modules").exists():
        print("[dev up]   ⚠ node_modules/ not found — run 'pnpm install' before starting app services")

    # apps/ dirs: warn if missing (they'll be SKIP'd during startup, not fail)
    # Dashboard error already captured above; portal/product-ui are SKIP if missing.

    if errors:
        for err_msg in errors:
            print_err(f"[dev up] ✗ Prerequisite check failed: {err_msg}")
        print_err("[dev up] Exiting.")
        return False

    print("[dev up] ✓ Prerequisite checks passed")
    return True


def check_port_availability(services: List[Dict[str, Any]]) -> bool:
    """Check all service ports are free. Return True if all free."""
    all_free = True
    for svc in services:
        if svc.get("app_dir") and not svc["app_dir"].exists():
            continue  # Will be SKIP'd — don't check port
        port = svc["port"]
        free, proc_info = is_port_free(port)
        if not free:
            print_err(f"[dev up] ✗ Port {port} is already in use.")
            if proc_info:
                print_err(f"[dev up] Process: {proc_info}")
                pid_part = proc_info.replace("PID ", "")
                print_err(f"[dev up] Kill the process with: kill {pid_part}")
            print_err(f"[dev up] Exiting.")
            all_free = False
    return all_free


# ──────────────────────────────────────────────────────────────────────────────
# dev up
# ──────────────────────────────────────────────────────────────────────────────

def cmd_up(args: argparse.Namespace) -> int:
    services = make_services(
        dashboard_port=args.dashboard_port,
        portal_port=args.portal_port,
        product_port=args.product_port,
    )
    timeout_per_svc = 30
    overall_timeout = args.timeout

    # ── Prerequisite checks ──────────────────────────────────────────────────
    if not run_prereq_checks(services, verbose=args.verbose):
        return 1

    # Separate skippable services from required ones
    to_start: List[Dict[str, Any]] = []
    skipped: List[str] = []
    for svc in services:
        if svc.get("app_dir") is not None and not svc["app_dir"].exists():
            print(f"{label(svc['name'])} SKIP: app not yet scaffolded ({svc['app_dir'].relative_to(REPO_ROOT)})")
            skipped.append(svc["name"])
        else:
            to_start.append(svc)

    if not to_start:
        print("[dev up] No services to start.")
        return 0

    # ── Port availability ─────────────────────────────────────────────────────
    if not check_port_availability(to_start):
        return 1

    # ── Start processes ───────────────────────────────────────────────────────
    print(f"[dev up] Starting OperatorOne services...")
    print(f"[dev up] Starting {len(to_start)} service(s) in parallel...")

    procs: Dict[str, subprocess.Popen] = {}
    pid_data: Dict[str, Any] = {}
    start_time = time.time()

    for svc in to_start:
        url = f"http://{svc['host']}:{svc['port']}"
        print(f"{label(svc['name'])} Starting on {url}")
        try:
            proc = subprocess.Popen(
                svc["cmd"],
                cwd=svc["cwd"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            procs[svc["name"]] = proc
            pid_data[svc["name"]] = {
                "pid": proc.pid,
                "port": svc["port"],
                "type": svc["type"],
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        except FileNotFoundError as e:
            print_err(f"[dev up] ✗ {svc['name']} service failed to start.")
            print_err(f"{label(svc['name'])} Error: {e}")
            print_err(f"[dev up] Remediation: {svc['remediation']}")
            # Kill already-started procs
            _kill_all(procs)
            return 1

    save_pids(pid_data)

    if args.skip_health_check:
        print("[dev up] ✅ All services launched (health check skipped).")
        print("[dev up] Press Ctrl+C to shut down.")
        try:
            _tail_logs(procs, args.verbose)
        except KeyboardInterrupt:
            print("\n[dev up] Interrupted. Shutting down...")
            _graceful_shutdown(procs)
            clear_pids()
            return 130
        return 0

    # ── Health polling ────────────────────────────────────────────────────────
    print("[dev up] Waiting for health endpoints...")

    def setup_signal_handler(active_procs: Dict[str, subprocess.Popen]) -> None:
        def _handler(sig: int, frame: Any) -> None:
            print("\n[dev up] Interrupted. Shutting down...")
            _graceful_shutdown(active_procs)
            clear_pids()
            sys.exit(130)
        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)

    setup_signal_handler(procs)

    ready: Dict[str, bool] = {name: False for name in procs}
    failed: Dict[str, Optional[str]] = {}
    overall_start = time.time()

    while not all(ready.values()):
        if time.time() - overall_start > overall_timeout:
            print_err("[dev up] ✗ Overall timeout exceeded.")
            _graceful_shutdown(procs)
            clear_pids()
            return 1

        for svc in to_start:
            name = svc["name"]
            if ready.get(name) or name in failed:
                continue

            proc = procs[name]
            # Check if process exited unexpectedly
            ret = proc.poll()
            if ret is not None:
                print_err(f"{label(name)} ✗ Process exited unexpectedly (exit code {ret}).")
                failed[name] = f"exited with code {ret}"
                # Read remaining output
                try:
                    out, _ = proc.communicate(timeout=2)
                    if out:
                        for line in out.splitlines()[:20]:
                            print_err(f"{label(name)}   {line}")
                except Exception:
                    pass
                continue

            elapsed = time.time() - overall_start
            if elapsed > timeout_per_svc:
                url = svc["readiness_url"]
                print_err(f"{label(name)} ✗ Health check timeout (>30s). Service may not be running correctly.")
                print_err(f"{label(name)} Last error: Connection refused on {url}")
                print_err(f"[dev up] Remediation: {svc['remediation']}")
                failed[name] = "health check timeout"
                continue

            # Poll health
            status, ms = http_get(svc["readiness_url"], timeout=3.0)
            if status == 200:
                print(f"{label(name)} ✓ READY ({int(ms)}ms)")
                ready[name] = True
            elif args.verbose:
                print(f"{label(name)} … waiting ({int(elapsed)}s elapsed)")

        if failed:
            print_err("[dev up] Service startup failed. See logs above.")
            print_err("[dev up] Exiting.")
            _graceful_shutdown(procs)
            clear_pids()
            return 1

        if not all(ready.values()):
            time.sleep(1)

    if skipped:
        for name in skipped:
            print(f"{label(name)} SKIP (not yet scaffolded)")

    print("[dev up] ✅ All services ready. Dev environment online.")
    print("[dev up] Press Ctrl+C to shut down.")

    try:
        _tail_logs(procs, args.verbose)
    except KeyboardInterrupt:
        print("\n[dev up] Interrupted. Shutting down...")
        _graceful_shutdown(procs)
        clear_pids()
        return 130

    return 0


def _tail_logs(procs: Dict[str, subprocess.Popen], verbose: bool) -> None:
    """Continuously read and print output from all service processes."""
    import select
    import threading

    def drain(name: str, proc: subprocess.Popen) -> None:
        try:
            for line in proc.stdout:  # type: ignore[union-attr]
                if verbose:
                    print(f"{label(name)} {line}", end="")
        except Exception:
            pass

    threads = []
    for name, proc in procs.items():
        t = threading.Thread(target=drain, args=(name, proc), daemon=True)
        t.start()
        threads.append(t)

    # Wait until all processes exit
    while True:
        alive = [p for p in procs.values() if p.poll() is None]
        if not alive:
            break
        time.sleep(0.5)

    for t in threads:
        t.join(timeout=2)


def _kill_all(procs: Dict[str, subprocess.Popen]) -> None:
    for name, proc in procs.items():
        try:
            proc.terminate()
        except Exception:
            pass


def _graceful_shutdown(procs: Dict[str, subprocess.Popen]) -> None:
    """SIGTERM → wait 10s → SIGKILL."""
    print("[dev down] Shutting down running services...")
    for name, proc in procs.items():
        if proc.poll() is None:
            print(f"{label(name)} Sending SIGTERM (PID {proc.pid})")
            try:
                proc.terminate()
            except Exception:
                pass

    deadline = time.time() + 10
    still_alive = list(procs.items())
    while still_alive and time.time() < deadline:
        time.sleep(0.5)
        still_alive = [(n, p) for n, p in still_alive if p.poll() is None]

    for name, proc in still_alive:
        print(f"{label(name)} ⚠ Still running — sending SIGKILL (PID {proc.pid})")
        try:
            proc.kill()
        except Exception:
            pass

    for name, proc in procs.items():
        try:
            proc.wait(timeout=5)
            code = proc.returncode
            print(f"{label(name)} ✓ Exited (exit code {code})")
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# dev status
# ──────────────────────────────────────────────────────────────────────────────

def cmd_status(args: argparse.Namespace) -> int:
    services = make_services(
        dashboard_port=getattr(args, "dashboard_port", 8765),
        portal_port=getattr(args, "portal_port", 5173),
        product_port=getattr(args, "product_port", 5174),
    )
    pid_data = load_pids()

    print("[dev status] Checking service status...")
    print()

    all_ready = True
    for svc in services:
        name = svc["name"]
        port = svc["port"]
        host = svc["host"]
        url = f"http://{host}:{port}"

        # Check if app dir missing → SKIP
        if svc.get("app_dir") is not None and not svc["app_dir"].exists():
            print(f"Service: {name} ({svc['type']})")
            print(f"  Port: {port}")
            print(f"  Status: ○ SKIP (app not yet scaffolded)")
            print(f"  URL: {url}")
            print()
            continue

        # Get PID from tracking file
        pid_info = pid_data.get(name, {})
        pid_display = pid_info.get("pid", "—")

        # Check port
        free, _ = is_port_free(port)

        if free:
            status_str = "○ STOPPED"
            health_str = "port free"
            all_ready = False
        else:
            # Try health endpoint
            health_url = svc["readiness_url"]
            status_code, ms = http_get(health_url, timeout=5.0)
            if status_code == 200:
                status_str = "✓ READY"
                endpoint = health_url.replace(f"http://{host}:{port}", "").replace(f"http://localhost:{port}", "")
                health_str = f"{endpoint} → 200 OK (response time: {int(ms)}ms)"
            elif status_code is not None:
                status_str = "⚠ STARTING"
                health_str = f"HTTP {status_code} (response time: {int(ms)}ms)"
                all_ready = False
            else:
                # Port in use but no HTTP response yet
                status_str = "⚠ STARTING"
                health_str = "no response yet"
                all_ready = False

        print(f"Service: {name} ({svc['type']})")
        print(f"  Port: {port}")
        print(f"  Status: {status_str}")
        print(f"  Health: {health_str}")
        print(f"  URL: {url}")
        print(f"  PID: {pid_display}")
        print()

    if all_ready:
        print("[dev status] ✅ All services ready.")
        return 0
    else:
        print("[dev status] Some services are not ready.")
        return 1


# ──────────────────────────────────────────────────────────────────────────────
# dev down
# ──────────────────────────────────────────────────────────────────────────────

def cmd_down(args: argparse.Namespace) -> int:
    pid_data = load_pids()

    if not pid_data:
        print("[dev down] No services tracked in pids.json — nothing to stop.")
        print("[dev down] (If services are running, stop them manually.)")
        return 0

    print("[dev down] Shutting down OperatorOne services...")

    sigkill_used = False

    for name, info in pid_data.items():
        pid = info.get("pid")
        if not pid:
            continue

        # Check if process is alive
        try:
            os.kill(pid, 0)  # Signal 0 = existence check
            process_alive = True
        except ProcessLookupError:
            process_alive = False
        except PermissionError:
            process_alive = True  # Exists but no permission to signal

        if not process_alive:
            print(f"{label(name)} Already stopped (PID {pid})")
            continue

        print(f"{label(name)} Received SIGTERM (PID {pid})")
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception as e:
            print_err(f"{label(name)} ⚠ Failed to send SIGTERM: {e}")
            continue

    print("[dev down] Waiting for graceful shutdown (10s timeout)...")

    deadline = time.time() + 10
    remaining = list(pid_data.items())

    while remaining and time.time() < deadline:
        time.sleep(0.5)
        still_alive = []
        for name, info in remaining:
            pid = info.get("pid")
            if not pid:
                continue
            try:
                os.kill(pid, 0)
                still_alive.append((name, info))
            except ProcessLookupError:
                print(f"{label(name)} ✓ Exited cleanly")
            except PermissionError:
                still_alive.append((name, info))
        remaining = still_alive

    # SIGKILL stragglers
    for name, info in remaining:
        pid = info.get("pid")
        if not pid:
            continue
        print(f"{label(name)} ⚠ Force-killing (SIGKILL) PID {pid}")
        try:
            os.kill(pid, signal.SIGKILL)
            sigkill_used = True
        except Exception as e:
            print_err(f"{label(name)} ⚠ SIGKILL failed: {e}")

    # Final wait
    time.sleep(1)
    for name, info in remaining:
        pid = info.get("pid")
        if not pid:
            continue
        try:
            os.kill(pid, 0)
            print_err(f"{label(name)} ✗ Process {pid} still alive after SIGKILL")
        except ProcessLookupError:
            print(f"{label(name)} ✓ Exited (after SIGKILL)")

    clear_pids()

    if sigkill_used:
        print("[dev down] ⚠ Some services required SIGKILL.")
        return 1
    else:
        print("[dev down] ✅ All services shut down.")
        return 0


# ──────────────────────────────────────────────────────────────────────────────
# CLI argument parsing
# ──────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dev",
        description=(
            "OperatorOne one-click development launcher.\n\n"
            "Manages three local services:\n"
            "  dashboard      Flask API + UI  (port 8765)\n"
            "  platform-portal  React/Vite app  (port 5173)\n"
            "  product-ui       React/Vite app  (port 5174)\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = False  # We handle missing command below

    # ── up ────────────────────────────────────────────────────────────────────
    up_parser = subparsers.add_parser(
        "up",
        help="Start all services and wait for them to be READY",
        description="Start all OperatorOne services. Validates prerequisites, starts services in parallel, polls health endpoints.",
    )
    up_parser.add_argument("--dashboard-port", type=int, default=8765, metavar="PORT",
                           help="Dashboard port (default: 8765)")
    up_parser.add_argument("--portal-port", type=int, default=5173, metavar="PORT",
                           help="platform-portal port (default: 5173)")
    up_parser.add_argument("--product-port", type=int, default=5174, metavar="PORT",
                           help="product-ui port (default: 5174)")
    up_parser.add_argument("--timeout", type=int, default=120, metavar="SECONDS",
                           help="Overall startup timeout in seconds (default: 120)")
    up_parser.add_argument("--skip-health-check", action="store_true",
                           help="Start services without waiting for health endpoints")
    up_parser.add_argument("--verbose", "-v", action="store_true",
                           help="Print detailed debug/progress output")

    # ── status ────────────────────────────────────────────────────────────────
    subparsers.add_parser(
        "status",
        help="Check health of all services (does NOT start them)",
        description="Check the current health status of all OperatorOne services. Exits 0 if all READY, 1 otherwise.",
    )

    # ── down ──────────────────────────────────────────────────────────────────
    subparsers.add_parser(
        "down",
        help="Gracefully stop all services started by dev up",
        description="Send SIGTERM to all tracked services, wait 10s, then SIGKILL stragglers.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 2

    if args.command == "up":
        return cmd_up(args)
    elif args.command == "status":
        return cmd_status(args)
    elif args.command == "down":
        return cmd_down(args)
    else:
        print_err(f"Unknown command: {args.command}")
        parser.print_help()
        return 2


if __name__ == "__main__":
    sys.exit(main())
