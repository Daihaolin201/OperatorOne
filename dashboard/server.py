#!/usr/bin/env python3
"""OperatorOne Dashboard server.

A lightweight local HTTP server that:
- serves the dashboard UI
- exposes snapshot APIs for 4-agent monitoring
- evaluates external-contact readiness gates
- provides controlled channel/secrets integration actions
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote, unquote, urlparse

from collector import PROFILE, REPO_ROOT, collect_snapshot, first_json_from_text
from studio import SIMULATION_SAFE_ACTIONS, StudioError, StudioService


DASHBOARD_DIR = Path(__file__).resolve().parent
WEB_DIR = DASHBOARD_DIR / "web"
RUNTIME_DIR = DASHBOARD_DIR / ".runtime"
FLAGS_PATH = RUNTIME_DIR / "state.json"
API_CONNECTORS_PATH = RUNTIME_DIR / "api_connectors.json"
AUDIT_LOG_PATH = RUNTIME_DIR / "audit.log.jsonl"

OPENCLAW_BIN = os.environ.get("OPENCLAW_BIN", "openclaw")

MAX_BODY_BYTES = 1_000_000

SENSITIVE_FIELDS = {
    "token",
    "botToken",
    "appToken",
    "password",
    "webhookUrl",
    "accessToken",
}

CHANNEL_FLAG_MAP = {
    "telegram": {
        "token": "--token",
        "tokenFile": "--token-file",
        "account": "--account",
        "name": "--name",
    },
    "discord": {
        "token": "--token",
        "account": "--account",
        "name": "--name",
    },
    "slack": {
        "botToken": "--bot-token",
        "appToken": "--app-token",
        "account": "--account",
        "name": "--name",
    },
    "googlechat": {
        "webhookUrl": "--webhook-url",
        "account": "--account",
        "name": "--name",
        "audience": "--audience",
        "audienceType": "--audience-type",
    },
    "whatsapp": {
        "account": "--account",
        "name": "--name",
        "authDir": "--auth-dir",
    },
}

STUDIO = StudioService(REPO_ROOT, DASHBOARD_DIR, PROFILE)

MONITOR_CACHE_TTL_SECONDS = int(os.environ.get("OPERATORONE_MONITOR_CACHE_TTL", "45"))
_MONITOR_CACHE_LOCK = threading.Lock()
_MONITOR_CACHE: Dict[str, Any] = {
    "snapshot": None,
    "generatedAt": None,
    "expiresAt": 0.0,
    "durationMs": None,
    "error": None,
    "refreshing": False,
}


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_runtime_files() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    if not FLAGS_PATH.exists():
        FLAGS_PATH.write_text(
            json.dumps(
                {
                    "manualArmEnabled": False,
                    "updatedAt": utc_iso(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    if not API_CONNECTORS_PATH.exists():
        API_CONNECTORS_PATH.write_text(json.dumps({"items": []}, ensure_ascii=False, indent=2))


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def append_audit(event: Dict[str, Any]) -> None:
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def load_flags() -> Dict[str, Any]:
    ensure_runtime_files()
    payload = read_json(FLAGS_PATH, default={})
    if "manualArmEnabled" not in payload:
        payload["manualArmEnabled"] = False
    return payload


def save_flags(flags: Dict[str, Any]) -> None:
    flags = dict(flags)
    flags["updatedAt"] = utc_iso()
    write_json(FLAGS_PATH, flags)


def load_api_connectors() -> Dict[str, Any]:
    ensure_runtime_files()
    payload = read_json(API_CONNECTORS_PATH, default={"items": []})
    if "items" not in payload or not isinstance(payload["items"], list):
        payload["items"] = []
    return payload


def save_api_connectors(payload: Dict[str, Any]) -> None:
    payload = dict(payload)
    payload["updatedAt"] = utc_iso()
    write_json(API_CONNECTORS_PATH, payload)


def run_command(cmd: List[str], timeout: int = 120) -> Dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    merged = "\n".join([proc.stdout or "", proc.stderr or ""]).strip()
    out: Dict[str, Any] = {
        "ok": proc.returncode == 0,
        "code": proc.returncode,
    }
    if merged:
        out["raw"] = merged[:4000]
        try:
            out["json"] = first_json_from_text(merged)
        except Exception:  # noqa: BLE001
            pass
    return out


def _build_monitor_snapshot() -> Tuple[Dict[str, Any], int]:
    start = time.perf_counter()
    flags = load_flags()
    connectors = load_api_connectors()
    snapshot = collect_snapshot(runtime_flags=flags)
    snapshot["runtimeState"] = {
        "flags": flags,
        "apiConnectors": connectors,
    }
    duration_ms = int((time.perf_counter() - start) * 1000)
    return snapshot, duration_ms


def _refresh_monitor_cache_sync() -> None:
    try:
        snapshot, duration_ms = _build_monitor_snapshot()
        generated_at = utc_iso()
        with _MONITOR_CACHE_LOCK:
            _MONITOR_CACHE.update(
                {
                    "snapshot": snapshot,
                    "generatedAt": generated_at,
                    "expiresAt": time.time() + MONITOR_CACHE_TTL_SECONDS,
                    "durationMs": duration_ms,
                    "error": None,
                }
            )
    except Exception as exc:  # noqa: BLE001
        with _MONITOR_CACHE_LOCK:
            _MONITOR_CACHE["error"] = str(exc)


def _refresh_monitor_cache_worker() -> None:
    with _MONITOR_CACHE_LOCK:
        if _MONITOR_CACHE.get("refreshing"):
            return
        _MONITOR_CACHE["refreshing"] = True
    try:
        _refresh_monitor_cache_sync()
    finally:
        with _MONITOR_CACHE_LOCK:
            _MONITOR_CACHE["refreshing"] = False


def _trigger_monitor_refresh(force: bool = False) -> None:
    should_refresh = False
    with _MONITOR_CACHE_LOCK:
        now = time.time()
        has_snapshot = _MONITOR_CACHE.get("snapshot") is not None
        expired = now >= float(_MONITOR_CACHE.get("expiresAt") or 0.0)
        refreshing = bool(_MONITOR_CACHE.get("refreshing"))
        should_refresh = (force or (not has_snapshot) or expired) and not refreshing

    if should_refresh:
        thread = threading.Thread(target=_refresh_monitor_cache_worker, daemon=True, name="monitor-cache-refresh")
        thread.start()


def get_monitor_cache_view() -> Dict[str, Any]:
    with _MONITOR_CACHE_LOCK:
        snapshot = _MONITOR_CACHE.get("snapshot")
        generated_at = _MONITOR_CACHE.get("generatedAt")
        expires_at = float(_MONITOR_CACHE.get("expiresAt") or 0.0)
        duration_ms = _MONITOR_CACHE.get("durationMs")
        error = _MONITOR_CACHE.get("error")
        refreshing = bool(_MONITOR_CACHE.get("refreshing"))

    now = time.time()
    stale = (snapshot is None) or (now >= expires_at)
    return {
        "snapshot": snapshot,
        "meta": {
            "generatedAt": generated_at,
            "expiresAt": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat() if expires_at else None,
            "stale": stale,
            "refreshing": refreshing,
            "durationMs": duration_ms,
            "ttlSeconds": MONITOR_CACHE_TTL_SECONDS,
            "error": error,
            "hasSnapshot": snapshot is not None,
        },
    }


def safe_command_preview(cmd: List[str], payload: Dict[str, Any]) -> str:
    redacted = []
    sensitive_values = {str(v) for k, v in payload.items() if k in SENSITIVE_FIELDS and v is not None}
    for token in cmd:
        if token in sensitive_values:
            redacted.append("***")
        else:
            redacted.append(token)
    return " ".join(redacted)


def validate_channel_payload(payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    channel = str(payload.get("channel", "")).strip()
    if channel not in CHANNEL_FLAG_MAP:
        return "unsupported channel", None

    allowed = CHANNEL_FLAG_MAP[channel]
    normalized: Dict[str, Any] = {"channel": channel}

    for key, value in payload.items():
        if key == "channel":
            continue
        if key not in allowed:
            continue
        if value is None:
            continue
        text = str(value).strip()
        if text == "":
            continue
        normalized[key] = text

    # Basic required fields for selected channels.
    if channel in {"telegram", "discord"} and not normalized.get("token"):
        return "token is required for this channel", None
    if channel == "slack" and not (normalized.get("botToken") and normalized.get("appToken")):
        return "slack requires botToken and appToken", None
    if channel == "googlechat" and not (
        normalized.get("webhookUrl") or normalized.get("audience")
    ):
        return "googlechat requires webhookUrl or audience", None

    return None, normalized


def build_channel_add_command(normalized: Dict[str, Any]) -> List[str]:
    channel = normalized["channel"]
    cmd = [OPENCLAW_BIN, "--profile", PROFILE, "channels", "add", "--channel", channel]
    for key, flag in CHANNEL_FLAG_MAP[channel].items():
        if key in normalized:
            cmd.extend([flag, str(normalized[key])])
    return cmd


def build_channel_remove_command(payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[List[str]]]:
    channel = str(payload.get("channel", "")).strip()
    if channel not in CHANNEL_FLAG_MAP:
        return "unsupported channel", None

    cmd = [OPENCLAW_BIN, "--profile", PROFILE, "channels", "remove", "--channel", channel]
    account = str(payload.get("account", "")).strip()
    if account:
        cmd.extend(["--account", account])
    if bool(payload.get("delete", False)):
        cmd.append("--delete")
    return None, cmd


def upsert_api_connector(payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    name = str(payload.get("name", "")).strip()
    if not name:
        return "name is required", None

    connector_id = str(payload.get("id", "")).strip()
    if not connector_id:
        connector_id = (
            name.lower()
            .replace(" ", "-")
            .replace("/", "-")
            .replace("_", "-")
        )
        connector_id = "".join(ch for ch in connector_id if ch.isalnum() or ch == "-")
        connector_id = connector_id[:64]
    if not connector_id:
        return "failed to build connector id", None

    item = {
        "id": connector_id,
        "name": name,
        "category": str(payload.get("category", "api")).strip() or "api",
        "baseUrl": str(payload.get("baseUrl", "")).strip(),
        "authMode": str(payload.get("authMode", "secret_ref")).strip() or "secret_ref",
        "secretRef": str(payload.get("secretRef", "")).strip(),
        "ownerAgent": str(payload.get("ownerAgent", "")).strip(),
        "status": str(payload.get("status", "configured")).strip() or "configured",
        "notes": str(payload.get("notes", "")).strip(),
        "updatedAt": utc_iso(),
    }
    return None, item


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "OperatorOneDashboard/1.0"

    def _json_response(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        length_header = self.headers.get("Content-Length")
        if not length_header:
            return {}, None
        try:
            length = int(length_header)
        except ValueError:
            return None, "invalid Content-Length"
        if length < 0 or length > MAX_BODY_BYTES:
            return None, "request body too large"
        raw = self.rfile.read(length)
        if not raw:
            return {}, None
        try:
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                return None, "JSON body must be an object"
            return payload, None
        except Exception:  # noqa: BLE001
            return None, "invalid JSON body"

    def _serve_static(self, path: str) -> None:
        rel = path.lstrip("/")
        if rel == "":
            rel = "index.html"

        candidate = (WEB_DIR / rel).resolve()
        if not str(candidate).startswith(str(WEB_DIR.resolve())):
            self.send_error(HTTPStatus.FORBIDDEN)
            return

        if not candidate.exists() or not candidate.is_file():
            # SPA fallback
            candidate = WEB_DIR / "index.html"
            if not candidate.exists():
                self.send_error(HTTPStatus.NOT_FOUND)
                return

        content = candidate.read_bytes()
        mime = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{mime}; charset=utf-8" if mime.startswith("text/") else mime)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _handle_get_snapshot(self, refresh: bool = False) -> None:
        # Backward-compatible monitor endpoint, now cache-backed.
        _trigger_monitor_refresh(force=refresh)
        view = get_monitor_cache_view()
        self._json_response(200, {"ok": True, "snapshot": view.get("snapshot"), "meta": view.get("meta")})

    def _handle_get_monitor_cached_snapshot(self, refresh: bool = False) -> None:
        _trigger_monitor_refresh(force=refresh)
        view = get_monitor_cache_view()
        self._json_response(200, {"ok": True, "snapshot": view.get("snapshot"), "meta": view.get("meta")})

    def _handle_get_runtime_flags(self) -> None:
        self._json_response(200, {"ok": True, "flags": load_flags()})

    def _handle_get_api_connectors(self) -> None:
        self._json_response(200, {"ok": True, "connectors": load_api_connectors()})

    # ------------------------------------------------------------------
    # Run lifecycle helpers
    # ------------------------------------------------------------------
    def _build_run_object(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        import uuid as _uuid
        run_id = f"run_{_uuid.uuid4().hex[:12]}"
        mode = str(payload.get("mode", "simulation")).strip() or "simulation"
        model_provider = str(payload.get("model_provider", "z.ai")).strip() or "z.ai"
        model_name = str(payload.get("model_name", "glm-5")).strip() or "glm-5"
        return {
            "run_id": run_id,
            "run_type": "api",
            "status": "queued",
            "current_step": None,
            "started_at": utc_iso(),
            "finished_at": None,
            "mode": mode,
            "model_provider": model_provider,
            "model_name": model_name,
            "steps": [],
            "events": [],
        }

    def _find_active_api_run(self) -> Optional[Dict[str, Any]]:
        with STUDIO.store_lock:
            runs_payload = STUDIO._load_runs()
        for item in runs_payload.get("items", []):
            if not isinstance(item, dict):
                continue
            if item.get("run_type") != "api":
                continue
            if item.get("status") in ("queued", "running"):
                return item
        return None

    def _get_api_run_by_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        with STUDIO.store_lock:
            runs_payload = STUDIO._load_runs()
        for item in runs_payload.get("items", []):
            if not isinstance(item, dict):
                continue
            if item.get("run_type") == "api" and item.get("run_id") == run_id:
                return item
        return None

    def _upsert_api_run(self, run: Dict[str, Any]) -> None:
        run_id = run["run_id"]
        with STUDIO.store_lock:
            runs_payload = STUDIO._load_runs()
            items = runs_payload.get("items", [])
            replaced = False
            for idx, item in enumerate(items):
                if isinstance(item, dict) and item.get("run_type") == "api" and item.get("run_id") == run_id:
                    items[idx] = run
                    replaced = True
                    break
            if not replaced:
                items.append(run)
            # keep bounded
            if len(items) > 500:
                items = items[-500:]
            runs_payload["items"] = items
            STUDIO._save_runs(runs_payload)

    # ------------------------------------------------------------------
    # Run endpoint handlers
    # ------------------------------------------------------------------
    def _handle_post_runs(self, payload: Dict[str, Any]) -> None:
        # Idempotency: if active run exists, reuse it
        existing = self._find_active_api_run()
        if existing:
            resp = {
                "ok": True,
                "reused": True,
                "run_id": existing["run_id"],
                "status": existing["status"],
                "mode": existing.get("mode", "simulation"),
                "model_provider": existing.get("model_provider", "z.ai"),
                "model_name": existing.get("model_name", "glm-5"),
                "started_at": existing.get("started_at"),
            }
            self._json_response(200, resp)
            return

        run = self._build_run_object(payload)
        self._upsert_api_run(run)
        append_audit(
            {
                "ts": utc_iso(),
                "action": "run_create",
                "run_id": run["run_id"],
                "mode": run["mode"],
            }
        )
        self._json_response(
            200,
            {
                "ok": True,
                "reused": False,
                "run_id": run["run_id"],
                "status": run["status"],
                "mode": run["mode"],
                "model_provider": run["model_provider"],
                "model_name": run["model_name"],
                "started_at": run["started_at"],
            },
        )

    def _handle_get_run(self, run_id: str) -> None:
        run = self._get_api_run_by_id(run_id)
        if not run:
            self._json_response(404, {"ok": False, "error": f"run not found: {run_id}"})
            return
        self._json_response(200, {"ok": True, "run": run})

    def _handle_get_run_events(self, run_id: str) -> None:
        run = self._get_api_run_by_id(run_id)
        if not run:
            self._json_response(404, {"ok": False, "error": f"run not found: {run_id}"})
            return
        events = run.get("events") or []
        self._json_response(200, {"ok": True, "run_id": run_id, "events": events})

    def _handle_get_run_replay(self, run_id: str) -> None:
        replay_path = STUDIO.studio_dir / "replays" / f"{run_id}.json"
        if not replay_path.exists():
            self._json_response(404, {"ok": False, "error": "replay not found"})
            return
        try:
            data = json.loads(replay_path.read_text())
            self._json_response(200, data)
        except Exception as exc:  # noqa: BLE001
            self._json_response(500, {"ok": False, "error": f"replay read failed: {exc}"})

    def _handle_get_runs_list(self) -> None:
        with STUDIO.store_lock:
            runs_payload = STUDIO._load_runs()
        api_runs = [
            item
            for item in runs_payload.get("items", [])
            if isinstance(item, dict) and item.get("run_type") == "api"
        ]
        self._json_response(200, {"ok": True, "runs": api_runs})

    def _handle_post_run_cancel(self, run_id: str) -> None:
        run = self._get_api_run_by_id(run_id)
        if not run:
            self._json_response(404, {"ok": False, "error": f"run not found: {run_id}"})
            return
        if run.get("status") not in ("queued", "running"):
            self._json_response(409, {"ok": False, "error": "run is not cancellable", "status": run.get("status")})
            return
        run["status"] = "cancelled"
        run["finished_at"] = utc_iso()
        run["events"] = list(run.get("events") or []) + [
            {"ts": utc_iso(), "type": "cancelled", "message": "run cancelled via API"}
        ]
        self._upsert_api_run(run)
        append_audit({"ts": utc_iso(), "action": "run_cancel", "run_id": run_id})
        self._json_response(200, {"ok": True, "run_id": run_id, "status": "cancelled"})

    def _handle_post_manual_arm(self, payload: Dict[str, Any]) -> None:
        enabled = bool(payload.get("enabled", False))
        flags = load_flags()
        flags["manualArmEnabled"] = enabled
        save_flags(flags)
        append_audit(
            {
                "ts": utc_iso(),
                "action": "manual_arm_set",
                "enabled": enabled,
            }
        )
        _trigger_monitor_refresh(force=True)
        self._json_response(200, {"ok": True, "flags": flags})

    def _handle_post_channel_connect(self, payload: Dict[str, Any]) -> None:
        err, normalized = validate_channel_payload(payload)
        if err:
            self._json_response(400, {"ok": False, "error": err})
            return

        assert normalized is not None
        dry_run = bool(payload.get("dryRun", False))
        cmd = build_channel_add_command(normalized)
        preview = safe_command_preview(cmd, normalized)

        if dry_run:
            self._json_response(200, {"ok": True, "dryRun": True, "commandPreview": preview})
            return

        result = run_command(cmd)
        append_audit(
            {
                "ts": utc_iso(),
                "action": "channel_connect",
                "channel": normalized.get("channel"),
                "account": normalized.get("account"),
                "ok": result.get("ok"),
                "code": result.get("code"),
            }
        )
        self._json_response(
            200 if result.get("ok") else 500,
            {
                "ok": bool(result.get("ok")),
                "commandPreview": preview,
                "code": result.get("code"),
                "json": result.get("json"),
                "raw": result.get("raw"),
            },
        )

    def _handle_post_channel_disconnect(self, payload: Dict[str, Any]) -> None:
        err, cmd = build_channel_remove_command(payload)
        if err:
            self._json_response(400, {"ok": False, "error": err})
            return
        assert cmd is not None

        result = run_command(cmd)
        append_audit(
            {
                "ts": utc_iso(),
                "action": "channel_disconnect",
                "channel": payload.get("channel"),
                "account": payload.get("account"),
                "ok": result.get("ok"),
                "code": result.get("code"),
            }
        )
        self._json_response(
            200 if result.get("ok") else 500,
            {
                "ok": bool(result.get("ok")),
                "code": result.get("code"),
                "json": result.get("json"),
                "raw": result.get("raw"),
            },
        )

    def _handle_post_secrets_audit(self) -> None:
        cmd = [OPENCLAW_BIN, "--profile", PROFILE, "secrets", "audit", "--json"]
        result = run_command(cmd)
        append_audit(
            {
                "ts": utc_iso(),
                "action": "secrets_audit",
                "ok": result.get("ok"),
                "code": result.get("code"),
            }
        )
        self._json_response(
            200 if result.get("ok") else 500,
            {
                "ok": bool(result.get("ok")),
                "code": result.get("code"),
                "json": result.get("json"),
                "raw": result.get("raw"),
            },
        )

    def _handle_post_secrets_reload(self) -> None:
        cmd = [OPENCLAW_BIN, "--profile", PROFILE, "secrets", "reload", "--json"]
        result = run_command(cmd)
        append_audit(
            {
                "ts": utc_iso(),
                "action": "secrets_reload",
                "ok": result.get("ok"),
                "code": result.get("code"),
            }
        )
        self._json_response(
            200 if result.get("ok") else 500,
            {
                "ok": bool(result.get("ok")),
                "code": result.get("code"),
                "json": result.get("json"),
                "raw": result.get("raw"),
            },
        )

    def _handle_post_api_connector_upsert(self, payload: Dict[str, Any]) -> None:
        err, item = upsert_api_connector(payload)
        if err:
            self._json_response(400, {"ok": False, "error": err})
            return
        assert item is not None

        connectors = load_api_connectors()
        items = connectors.get("items", [])

        replaced = False
        for idx, existing in enumerate(items):
            if isinstance(existing, dict) and existing.get("id") == item["id"]:
                items[idx] = item
                replaced = True
                break
        if not replaced:
            items.append(item)

        connectors["items"] = items
        save_api_connectors(connectors)
        append_audit(
            {
                "ts": utc_iso(),
                "action": "api_connector_upsert",
                "id": item["id"],
                "name": item["name"],
            }
        )
        self._json_response(200, {"ok": True, "connector": item, "connectors": connectors})

    def _handle_post_api_connector_delete(self, payload: Dict[str, Any]) -> None:
        connector_id = str(payload.get("id", "")).strip()
        if not connector_id:
            self._json_response(400, {"ok": False, "error": "id is required"})
            return

        connectors = load_api_connectors()
        items = connectors.get("items", [])
        new_items = [item for item in items if not (isinstance(item, dict) and item.get("id") == connector_id)]
        connectors["items"] = new_items
        save_api_connectors(connectors)
        append_audit(
            {
                "ts": utc_iso(),
                "action": "api_connector_delete",
                "id": connector_id,
            }
        )
        self._json_response(200, {"ok": True, "connectors": connectors})

    def _handle_get_studio_snapshot(self, *, include_monitor: bool = False, include_run_details: bool = False) -> None:
        started = time.perf_counter()
        try:
            monitor_view = get_monitor_cache_view()
            monitor_snapshot = monitor_view.get("snapshot")
            if not monitor_snapshot:
                try:
                    monitor_snapshot = collect_snapshot(runtime_flags=load_flags())
                except Exception:
                    monitor_snapshot = None

            # Always inject monitor snapshot so studio summary fields (gate/capability)
            # stay meaningful even on fast-snapshot calls.
            snapshot = STUDIO.snapshot(
                monitor_snapshot=monitor_snapshot,
                include_run_details=include_run_details,
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            payload = {
                "ok": True,
                "snapshot": snapshot,
                "meta": {
                    "durationMs": duration_ms,
                    "includeMonitor": include_monitor,
                    "includeRunDetails": include_run_details,
                    "monitor": monitor_view.get("meta"),
                },
            }
            self._json_response(200, payload)
        except Exception as exc:  # noqa: BLE001
            self._json_response(500, {"ok": False, "error": f"studio snapshot failed: {exc}"})

    def _handle_get_studio_jobs(self, path: str) -> None:
        # /api/studio/jobs or /api/studio/jobs/<id>
        if path == "/api/studio/jobs":
            self._json_response(200, {"ok": True, "jobs": STUDIO.list_jobs(include_result=False)})
            return
        prefix = "/api/studio/jobs/"
        if path.startswith(prefix):
            job_id = path[len(prefix):]
            job = STUDIO.get_job(job_id, include_result=True)
            if not job:
                self._json_response(404, {"ok": False, "error": "job not found"})
                return
            self._json_response(200, {"ok": True, "job": job})
            return
        self._json_response(404, {"ok": False, "error": f"unknown studio jobs endpoint: {path}"})

    def _handle_get_studio_artifact(self, query: Dict[str, List[str]]) -> None:
        path_values = query.get("path") or []
        if not path_values:
            self._json_response(400, {"ok": False, "error": "path query parameter is required"})
            return
        rel = str(path_values[-1]).strip()
        if not rel:
            self._json_response(400, {"ok": False, "error": "path query parameter is required"})
            return

        candidate = (REPO_ROOT / rel).resolve()
        if not str(candidate).startswith(str(REPO_ROOT.resolve())):
            self._json_response(403, {"ok": False, "error": "path escapes repository"})
            return
        if not candidate.exists() or not candidate.is_file():
            self._json_response(404, {"ok": False, "error": "artifact not found"})
            return

        size = candidate.stat().st_size
        max_chars = 120_000
        text_content = None
        binary = False
        try:
            text_content = candidate.read_text(encoding="utf-8")
            if len(text_content) > max_chars:
                text_content = text_content[:max_chars]
        except Exception:
            binary = True

        self._json_response(
            200,
            {
                "ok": True,
                "path": rel,
                "absolutePath": str(candidate),
                "sizeBytes": size,
                "binary": binary,
                "content": None if binary else text_content,
            },
        )

    def _resolve_repo_path(self, raw_path: str) -> Path:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = (REPO_ROOT / raw_path).resolve()
        else:
            candidate = candidate.resolve()
        return candidate

    def _resolve_preview_entry(self, raw_path: str) -> Tuple[Path, Path]:
        """Return (entry_file, asset_dir) for preview serving."""
        candidate = self._resolve_repo_path(raw_path)

        if candidate.is_dir():
            direct = (candidate / "index.html").resolve()
            public = (candidate / "public" / "index.html").resolve()
            if direct.exists():
                entry = direct
                asset_dir = direct.parent
            elif public.exists():
                entry = public
                asset_dir = public.parent
            else:
                entry = direct
                asset_dir = candidate
        else:
            entry = candidate
            if not entry.exists() and entry.name == "index.html":
                public = (entry.parent / "public" / "index.html").resolve()
                if public.exists():
                    entry = public
            asset_dir = entry.parent
            if entry.parent.name == "public":
                asset_dir = entry.parent
            elif (entry.parent / "public").exists():
                asset_dir = (entry.parent / "public").resolve()

        return entry, asset_dir

    def _artifact_summary(self, payload: Any) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if isinstance(payload, dict):
            for key in ["status", "generated_at", "generatedAt", "mode", "run_id", "runId", "opportunity_id", "opportunityId"]:
                if key in payload:
                    out[key] = payload.get(key)

            queue = payload.get("queue")
            if isinstance(queue, dict):
                out["queue_counts"] = {
                    k: len(v) if isinstance(v, list) else (v if isinstance(v, (int, float)) else None)
                    for k, v in queue.items()
                }

            counts = payload.get("counts")
            if isinstance(counts, dict):
                out["counts"] = counts

            summary = payload.get("summary")
            if isinstance(summary, dict):
                slim = {}
                for k, v in summary.items():
                    if isinstance(v, (str, int, float, bool)) or v is None:
                        slim[k] = v
                out["summary"] = slim

            items = payload.get("items")
            if isinstance(items, list):
                out["item_count"] = len(items)

        return out

    def _handle_get_studio_artifact_readable(self, query: Dict[str, List[str]]) -> None:
        path_values = query.get("path") or []
        if not path_values:
            self._json_response(400, {"ok": False, "error": "path query parameter is required"})
            return

        rel = str(path_values[-1]).strip()
        if not rel:
            self._json_response(400, {"ok": False, "error": "path query parameter is required"})
            return

        candidate = self._resolve_repo_path(rel)
        if not str(candidate).startswith(str(REPO_ROOT.resolve())):
            self._json_response(403, {"ok": False, "error": "path escapes repository"})
            return
        if not candidate.exists() or not candidate.is_file():
            self._json_response(404, {"ok": False, "error": "artifact not found"})
            return

        title = f"Readable Artifact · {rel}"
        raw_link = f"/api/studio/artifact/raw?path={quote(rel, safe='')}"

        try:
            text = candidate.read_text(encoding="utf-8")
            payload = None
            summary = {}
            pretty = text
            if candidate.suffix.lower() == ".json":
                payload = json.loads(text)
                summary = self._artifact_summary(payload)
                pretty = json.dumps(payload, ensure_ascii=False, indent=2)

            html_doc = f"""<!doctype html>
<html lang=\"zh-CN\"><head><meta charset=\"utf-8\"/><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>
<title>{escape(title)}</title>
<style>
body{{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto; background:#0b1117; color:#e7eef9; margin:0; padding:16px;}}
.card{{background:#111a24;border:1px solid #2a3442;border-radius:10px;padding:12px;margin-bottom:12px;}}
a{{color:#88b6ff}} pre{{white-space:pre-wrap;word-break:break-word;background:#0f1722;border:1px solid #273140;border-radius:8px;padding:12px;max-height:none;overflow:auto;}}
.small{{color:#a8b6ca;font-size:12px}}
</style></head><body>
<div class=\"card\"><h2 style=\"margin-top:0\">{escape(title)}</h2>
<div class=\"small\">文件大小: {candidate.stat().st_size} bytes</div>
<div><a href=\"{escape(raw_link)}\" target=\"_blank\" rel=\"noreferrer\">打开原始文本</a></div></div>
<div class=\"card\"><h3 style=\"margin-top:0\">人工可读摘要</h3><pre>{escape(json.dumps(summary, ensure_ascii=False, indent=2) if summary else '暂无结构化摘要')}</pre></div>
<div class=\"card\"><h3 style=\"margin-top:0\">完整内容</h3><pre>{escape(pretty[:500000])}</pre></div>
</body></html>"""
            body = html_doc.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        except Exception:
            pass

        # binary fallback
        body = json.dumps(
            {
                "ok": True,
                "path": rel,
                "message": "binary artifact",
                "sizeBytes": candidate.stat().st_size,
            },
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _handle_get_studio_artifact_raw(self, query: Dict[str, List[str]]) -> None:
        path_values = query.get("path") or []
        if not path_values:
            self._json_response(400, {"ok": False, "error": "path query parameter is required"})
            return

        rel = str(path_values[-1]).strip()
        if not rel:
            self._json_response(400, {"ok": False, "error": "path query parameter is required"})
            return

        candidate = Path(rel)
        if not candidate.is_absolute():
            candidate = (REPO_ROOT / rel).resolve()
        else:
            candidate = candidate.resolve()

        if not str(candidate).startswith(str(REPO_ROOT.resolve())):
            self._json_response(403, {"ok": False, "error": "path escapes repository"})
            return
        if not candidate.exists() or not candidate.is_file():
            self._json_response(404, {"ok": False, "error": "artifact not found"})
            return

        try:
            text_content = candidate.read_text(encoding="utf-8")
            mime = "application/json" if candidate.suffix.lower() == ".json" else "text/plain"
            body = text_content.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{mime}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        except Exception:
            body = json.dumps(
                {
                    "ok": True,
                    "path": rel,
                    "message": "binary artifact; use Builder artifact viewer for metadata",
                    "sizeBytes": candidate.stat().st_size,
                },
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    def _handle_get_studio_preview(self, query: Dict[str, List[str]]) -> None:
        path_values = query.get("path") or []
        if not path_values:
            self._json_response(400, {"ok": False, "error": "path query parameter is required"})
            return

        raw = str(path_values[-1]).strip()
        if not raw:
            self._json_response(400, {"ok": False, "error": "path query parameter is required"})
            return

        try:
            entry, asset_dir = self._resolve_preview_entry(raw)
        except Exception as exc:  # noqa: BLE001
            self._json_response(400, {"ok": False, "error": f"invalid preview path: {exc}"})
            return

        if not str(entry).startswith(str(REPO_ROOT.resolve())):
            self._json_response(403, {"ok": False, "error": "path escapes repository"})
            return

        asset_values = query.get("asset") or []
        if asset_values:
            rel_asset = str(asset_values[-1]).strip().lstrip("/")
            if not rel_asset or ".." in rel_asset:
                self._json_response(400, {"ok": False, "error": "invalid asset path"})
                return
            asset_file = (asset_dir / rel_asset).resolve()
            if not str(asset_file).startswith(str(REPO_ROOT.resolve())):
                self._json_response(403, {"ok": False, "error": "asset path escapes repository"})
                return
            if not asset_file.exists() or not asset_file.is_file():
                self._json_response(404, {"ok": False, "error": "preview asset not found"})
                return
            content = asset_file.read_bytes()
            mime = mimetypes.guess_type(str(asset_file))[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{mime}; charset=utf-8" if mime.startswith("text/") else mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)
            return

        if not entry.exists() or not entry.is_file():
            self._json_response(404, {"ok": False, "error": "preview file not found"})
            return

        content = entry.read_bytes()
        mime = mimetypes.guess_type(str(entry))[0] or "text/plain"

        if mime.startswith("text/html"):
            try:
                html = content.decode("utf-8", errors="ignore")
                encoded_raw = quote(raw, safe="")

                def _asset_repl(match: re.Match[str]) -> str:
                    attr = match.group(1)
                    path = match.group(2)
                    if path.startswith("http://") or path.startswith("https://"):
                        return match.group(0)
                    asset_url = f"/api/studio/preview?path={encoded_raw}&asset={quote(path, safe='') }"
                    return f'{attr}="{asset_url}"'

                html = re.sub(r'(href|src)="/([^"#?]+)"', _asset_repl, html)
                content = html.encode("utf-8")
                mime = "text/html"
            except Exception:
                pass

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{mime}; charset=utf-8" if mime.startswith("text/") else mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _handle_post_studio_action(self, payload: Dict[str, Any]) -> None:
        try:
            result = STUDIO.dispatch_action(payload)
            append_audit(
                {
                    "ts": utc_iso(),
                    "action": "studio_action",
                    "studio_action": payload.get("action"),
                    "ventureId": payload.get("ventureId"),
                    "async": result.get("async"),
                }
            )
            self._json_response(200, result)
        except StudioError as exc:
            self._json_response(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._json_response(500, {"ok": False, "error": f"studio action failed: {exc}"})

    def _handle_get_studio_safe_actions(self) -> None:
        self._json_response(
            200,
            {
                "ok": True,
                "safeActions": sorted(SIMULATION_SAFE_ACTIONS),
                "stepTimeoutSeconds": 30,
            },
        )

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query or "")

        def _qflag(name: str, default: bool = False) -> bool:
            values = query.get(name)
            if not values:
                return default
            raw = str(values[-1]).strip().lower()
            return raw in {"1", "true", "yes", "on"}

        if path == "/api/health":
            self._json_response(
                200,
                {
                    "ok": True,
                    "service": "operatorone-dashboard",
                    "ts": utc_iso(),
                    "profile": PROFILE,
                },
            )
            return
        if path == "/api/snapshot":
            self._handle_get_snapshot(refresh=_qflag("refresh", False))
            return
        if path == "/api/monitor/cached-snapshot":
            self._handle_get_monitor_cached_snapshot(refresh=_qflag("refresh", False))
            return
        if path == "/api/studio/snapshot":
            self._handle_get_studio_snapshot(
                include_monitor=_qflag("includeMonitor", False),
                include_run_details=_qflag("includeRunDetails", False),
            )
            return
        if path == "/api/studio/fast-snapshot":
            self._handle_get_studio_snapshot(include_monitor=False, include_run_details=False)
            return
        if path == "/api/studio/safe-actions":
            self._handle_get_studio_safe_actions()
            return
        if path == "/api/studio/jobs" or path.startswith("/api/studio/jobs/"):
            self._handle_get_studio_jobs(path)
            return
        if path == "/api/studio/artifact":
            self._handle_get_studio_artifact(query)
            return
        if path == "/api/studio/artifact/raw":
            self._handle_get_studio_artifact_raw(query)
            return
        if path == "/api/studio/artifact/readable":
            self._handle_get_studio_artifact_readable(query)
            return
        if path == "/api/studio/preview":
            self._handle_get_studio_preview(query)
            return
        if path == "/api/runtime-flags":
            self._handle_get_runtime_flags()
            return
        if path == "/api/integrations/api-connectors":
            self._handle_get_api_connectors()
            return
        if path == "/api/runs":
            self._handle_get_runs_list()
            return
        if path.startswith("/api/runs/"):
            suffix = path[len("/api/runs/"):]
            if suffix.endswith("/events"):
                run_id = suffix[: -len("/events")]
                if run_id:
                    self._handle_get_run_events(run_id)
                    return
            elif suffix.endswith("/replay"):
                run_id = suffix[: -len("/replay")]
                if run_id:
                    self._handle_get_run_replay(run_id)
                    return
            elif suffix:
                self._handle_get_run(suffix)
                return

        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        payload, err = self._read_json_body()
        if err:
            self._json_response(400, {"ok": False, "error": err})
            return
        assert payload is not None

        if path == "/api/runtime-flags/manual-arm":
            self._handle_post_manual_arm(payload)
            return
        if path == "/api/studio/action":
            self._handle_post_studio_action(payload)
            return
        if path == "/api/integrations/channel/connect":
            self._handle_post_channel_connect(payload)
            return
        if path == "/api/integrations/channel/disconnect":
            self._handle_post_channel_disconnect(payload)
            return
        if path == "/api/integrations/secrets/audit":
            self._handle_post_secrets_audit()
            return
        if path == "/api/integrations/secrets/reload":
            self._handle_post_secrets_reload()
            return
        if path == "/api/integrations/api-connectors/upsert":
            self._handle_post_api_connector_upsert(payload)
            return
        if path == "/api/integrations/api-connectors/delete":
            self._handle_post_api_connector_delete(payload)
            return
        if path == "/api/runs":
            self._handle_post_runs(payload)
            return
        if path.startswith("/api/runs/") and path.endswith("/cancel"):
            run_id = path[len("/api/runs/"): -len("/cancel")]
            if run_id:
                self._handle_post_run_cancel(run_id)
                return

        self._json_response(404, {"ok": False, "error": f"unknown endpoint: {path}"})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        # Keep local stdout readable while still giving useful request logs.
        message = format % args
        print(f"[{utc_iso()}] {self.client_address[0]} {self.command} {self.path} :: {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OperatorOne dashboard server")
    parser.add_argument("--host", default="127.0.0.1", help="bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="bind port (default: 8765)")
    return parser.parse_args()


def main() -> None:
    ensure_runtime_files()
    # Warm monitor snapshot cache asynchronously so initial UI can load fast.
    _trigger_monitor_refresh(force=True)
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"OperatorOne dashboard running on http://{args.host}:{args.port}")
    print(f"Profile: {PROFILE}")
    print(f"Monitor cache TTL: {MONITOR_CACHE_TTL_SECONDS}s")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
