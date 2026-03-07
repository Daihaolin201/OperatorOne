#!/usr/bin/env python3
"""OperatorOne Venture Studio service.

Implements the Phase 0-4 studio workflow on top of existing OperatorOne scripts.

Key capabilities:
- Idea board from Product Stage1/2 artifacts
- Venture lifecycle + state machine
- Stage execution actions (Product/Marketing/Sales/Operations)
- Human decision gates + audit timeline
- Artifact snapshotting by venture_id
- Async job execution for long-running stage actions
"""

from __future__ import annotations

import copy
import hashlib
import html
import json
import re
import shutil
import subprocess
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

try:
    from collector import collect_snapshot
except ModuleNotFoundError:  # pragma: no cover
    from dashboard.collector import collect_snapshot


STAGE_ORDER = [
    "IDEA_POOL",
    "SELECTED",
    "PRODUCT",
    "MARKETING",
    "SALES",
    "OPERATIONS",
    "ITERATE",
]

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"

ASYNC_ACTIONS = {
    "refresh_ideas",
    "run_product",
    "run_marketing_seo",
    "run_marketing_content",
    "review_marketing_content",
    "run_marketing_campaign",
    "run_sales_prospecting",
    "run_sales_outreach_plan",
    "approve_sales_outreach",
    "dispatch_sales_outreach",
    "run_sales_conversion",
    "run_operations_full",
    "writeback_operations",
    "stage_preflight",
    "rehearsal_e2e",
    "run_ceo_autopilot",
}

DUPLICATE_GUARD_ACTIONS = {
    "run_product",
    "run_marketing_seo",
    "run_marketing_content",
    "run_marketing_campaign",
    "run_sales_prospecting",
    "run_sales_outreach_plan",
    "approve_sales_outreach",
    "dispatch_sales_outreach",
    "run_sales_conversion",
    "run_operations_full",
    "writeback_operations",
    "stage_preflight",
    "rehearsal_e2e",
    "run_ceo_autopilot",
}

COPILOT_TIMEOUT_SECONDS = 45
COPILOT_TO = "+10000000000"


def now_dt() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_dt().isoformat()


def slugify(text: str, max_len: int = 80) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", text.strip().lower()).strip("-")
    cleaned = re.sub(r"-+", "-", cleaned)
    return cleaned[:max_len] or "item"


def canonical_opp_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    m = re.search(r"opp[_-]?(\d{1,4})", text, re.IGNORECASE)
    if not m:
        return None
    num = int(m.group(1))
    return f"opp_{num:03d}"


def opp_variants(opp_id: str) -> List[str]:
    base = canonical_opp_id(opp_id)
    if not base:
        return []
    num = base.split("_")[1]
    return [base, f"opp-{num}", f"opp{num}", f"proj-opp-{num}"]


def flatten_strings(obj: Any) -> List[str]:
    out: List[str] = []
    if obj is None:
        return out
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, (int, float, bool)):
        return [str(obj)]
    if isinstance(obj, dict):
        for v in obj.values():
            out.extend(flatten_strings(v))
        return out
    if isinstance(obj, list):
        for v in obj:
            out.extend(flatten_strings(v))
        return out
    return out


def deep_find_first_value(obj: Any, candidate_keys: List[str]) -> Optional[str]:
    keyset = {k.lower() for k in candidate_keys}

    def _walk(node: Any) -> Optional[str]:
        if isinstance(node, dict):
            for k, v in node.items():
                if str(k).lower() in keyset and isinstance(v, (str, int, float)):
                    text = str(v).strip()
                    if text:
                        return text
            for v in node.values():
                found = _walk(v)
                if found:
                    return found
            return None
        if isinstance(node, list):
            for v in node:
                found = _walk(v)
                if found:
                    return found
            return None
        return None

    return _walk(obj)


def item_matches_opp(item: Any, opp_id: Optional[str]) -> bool:
    if not opp_id:
        return True
    normalized = canonical_opp_id(opp_id)
    if not normalized:
        return True

    # Direct field match shortcut.
    if isinstance(item, dict):
        direct = canonical_opp_id(item.get("opportunity_id"))
        if direct == normalized:
            return True

    variants = [v.lower() for v in opp_variants(normalized)]
    for text in flatten_strings(item):
        low = text.lower()
        if any(v in low for v in variants):
            return True
    return False


class StudioError(RuntimeError):
    pass


@dataclass
class CommandResult:
    ok: bool
    code: int
    command: List[str]
    cwd: str
    started_at: str
    ended_at: str
    duration_ms: int
    stdout_tail: str
    stderr_tail: str


class StudioService:
    def __init__(self, repo_root: Path, dashboard_dir: Path, profile: str) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.dashboard_dir = Path(dashboard_dir).resolve()
        self.profile = profile

        self.runtime_dir = self.dashboard_dir / ".runtime"
        self.studio_dir = self.runtime_dir / "studio"
        self.artifacts_dir = self.studio_dir / "artifacts"
        self.rehearsals_dir = self.studio_dir / "rehearsals"

        self.state_path = self.studio_dir / "state.json"
        self.ventures_path = self.studio_dir / "ventures.json"
        self.runs_path = self.studio_dir / "stage_runs.json"
        self.gates_path = self.studio_dir / "decision_gates.json"
        self.loop_todos_path = self.studio_dir / "loop_todos.json"
        self.deployments_path = self.studio_dir / "deployments.json"
        self.contexts_dir = self.studio_dir / "contexts"
        self.user_prompts_path = self.studio_dir / "user_prompts.json"

        self.flags_path = self.runtime_dir / "state.json"  # shared with monitor gate

        self.product_dir = self.repo_root / "workspaces" / "op1_product"
        self.marketing_dir = self.repo_root / "workspaces" / "op1_marketing"
        self.sales_dir = self.repo_root / "workspaces" / "op1_sales"
        self.operations_dir = self.repo_root / "workspaces" / "op1_operations"
        self.scripts_dir = self.repo_root / "scripts"

        self.store_lock = threading.Lock()

        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="studio-job")
        self.jobs_lock = threading.Lock()
        self.jobs: Dict[str, Dict[str, Any]] = {}

        self._ensure_store()

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------
    def _ensure_store(self) -> None:
        self.studio_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.contexts_dir.mkdir(parents=True, exist_ok=True)
        self.rehearsals_dir.mkdir(parents=True, exist_ok=True)

        if not self.state_path.exists():
            self._write_json(
                self.state_path,
                {
                    "activeVentureId": None,
                    "ideaNonce": 0,
                    "updatedAt": now_iso(),
                },
            )
        if not self.ventures_path.exists():
            self._write_json(self.ventures_path, {"items": []})
        if not self.runs_path.exists():
            self._write_json(self.runs_path, {"items": []})
        if not self.gates_path.exists():
            self._write_json(self.gates_path, {"items": []})
        if not self.loop_todos_path.exists():
            self._write_json(self.loop_todos_path, {"items": []})
        if not self.deployments_path.exists():
            self._write_json(self.deployments_path, {"items": []})
        if not self.user_prompts_path.exists():
            self._write_json(self.user_prompts_path, {"items": []})

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return copy.deepcopy(default)
        try:
            return json.loads(path.read_text())
        except Exception:
            return copy.deepcopy(default)

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    def _load_state(self) -> Dict[str, Any]:
        return self._read_json(self.state_path, {"activeVentureId": None})

    def _save_state(self, state: Dict[str, Any]) -> None:
        state = dict(state)
        state["updatedAt"] = now_iso()
        self._write_json(self.state_path, state)

    def _load_ventures(self) -> Dict[str, Any]:
        payload = self._read_json(self.ventures_path, {"items": []})
        if "items" not in payload or not isinstance(payload["items"], list):
            payload["items"] = []
        return payload

    def _save_ventures(self, payload: Dict[str, Any]) -> None:
        payload = dict(payload)
        payload["updatedAt"] = now_iso()
        self._write_json(self.ventures_path, payload)

    def _load_runs(self) -> Dict[str, Any]:
        payload = self._read_json(self.runs_path, {"items": []})
        if "items" not in payload or not isinstance(payload["items"], list):
            payload["items"] = []
        return payload

    def _save_runs(self, payload: Dict[str, Any]) -> None:
        payload = dict(payload)
        payload["updatedAt"] = now_iso()
        self._write_json(self.runs_path, payload)

    def _load_gates(self) -> Dict[str, Any]:
        payload = self._read_json(self.gates_path, {"items": []})
        if "items" not in payload or not isinstance(payload["items"], list):
            payload["items"] = []
        return payload

    def _save_gates(self, payload: Dict[str, Any]) -> None:
        payload = dict(payload)
        payload["updatedAt"] = now_iso()
        self._write_json(self.gates_path, payload)

    def _load_loop_todos(self) -> Dict[str, Any]:
        payload = self._read_json(self.loop_todos_path, {"items": []})
        if "items" not in payload or not isinstance(payload["items"], list):
            payload["items"] = []
        return payload

    def _save_loop_todos(self, payload: Dict[str, Any]) -> None:
        payload = dict(payload)
        payload["updatedAt"] = now_iso()
        self._write_json(self.loop_todos_path, payload)

    def _load_deployments(self) -> Dict[str, Any]:
        payload = self._read_json(self.deployments_path, {"items": []})
        if "items" not in payload or not isinstance(payload["items"], list):
            payload["items"] = []
        return payload

    def _save_deployments(self, payload: Dict[str, Any]) -> None:
        payload = dict(payload)
        payload["updatedAt"] = now_iso()
        self._write_json(self.deployments_path, payload)

    def _load_user_prompts(self) -> Dict[str, Any]:
        payload = self._read_json(self.user_prompts_path, {"items": []})
        if "items" not in payload or not isinstance(payload["items"], list):
            payload["items"] = []
        return payload

    def _save_user_prompts(self, payload: Dict[str, Any]) -> None:
        payload = dict(payload)
        payload["updatedAt"] = now_iso()
        self._write_json(self.user_prompts_path, payload)

    def _context_path(self, venture_id: str) -> Path:
        safe = slugify(venture_id, 120)
        return self.contexts_dir / f"{safe}.json"

    def _write_venture_context(self, venture_id: str, context: Dict[str, Any]) -> None:
        payload = {
            "version": "venture_context.v1",
            "ventureId": venture_id,
            "updatedAt": now_iso(),
            "context": context,
        }
        self._write_json(self._context_path(venture_id), payload)

    def _read_venture_context(self, venture_id: str) -> Dict[str, Any]:
        payload = self._read_json(self._context_path(venture_id), {})
        if not isinstance(payload, dict):
            return {}
        return payload

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def _manual_arm_enabled(self) -> bool:
        payload = self._read_json(self.flags_path, {"manualArmEnabled": False})
        return bool(payload.get("manualArmEnabled", False))

    def _vercel_status(self) -> Dict[str, Any]:
        vercel_bin = shutil.which("vercel")
        installed = bool(vercel_bin)
        authenticated = False
        note = ""
        if installed:
            try:
                proc = subprocess.run(
                    ["vercel", "whoami"],
                    cwd=str(self.repo_root),
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                authenticated = proc.returncode == 0
                if proc.returncode != 0:
                    note = (proc.stderr or proc.stdout or "").strip()[:300]
                else:
                    note = (proc.stdout or "").strip()[:120]
            except Exception as exc:  # noqa: BLE001
                note = str(exc)
        return {
            "installed": installed,
            "authenticated": authenticated,
            "note": note,
        }

    def _vercel_project_name_for_venture(self, venture: Dict[str, Any]) -> str:
        opp = canonical_opp_id(venture.get("opportunityId")) or "opp-unknown"
        venture_name = slugify(str(venture.get("name") or venture.get("id") or "venture"), 36)
        return slugify(f"op1-{opp}-{venture_name}", 56)

    def _git_commit_sha(self) -> Optional[str]:
        try:
            proc = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode != 0:
                return None
            return (proc.stdout or "").strip()[:40] or None
        except Exception:
            return None

    def _append_deployment_record(self, record: Dict[str, Any]) -> None:
        with self.store_lock:
            payload = self._load_deployments()
            items = payload.get("items", [])
            items.append(record)
            payload["items"] = items[-300:]
            self._save_deployments(payload)

    def _run_cmd(self, command: List[str], cwd: Path, timeout: int = 1800) -> CommandResult:
        started = now_dt()
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        ended = now_dt()
        return CommandResult(
            ok=proc.returncode == 0,
            code=proc.returncode,
            command=command,
            cwd=str(cwd),
            started_at=started.isoformat(),
            ended_at=ended.isoformat(),
            duration_ms=int((ended - started).total_seconds() * 1000),
            stdout_tail=(proc.stdout or "")[-4000:],
            stderr_tail=(proc.stderr or "")[-4000:],
        )

    def _agent_relay_enabled(self, payload: Optional[Dict[str, Any]] = None) -> bool:
        if isinstance(payload, dict) and "agentRelayEnabled" in payload:
            return bool(payload.get("agentRelayEnabled"))

        flags = self._read_json(self.flags_path, {})
        if isinstance(flags, dict) and "agentRelayEnabled" in flags:
            return bool(flags.get("agentRelayEnabled"))

        # 默认开启，便于在 Studio 中形成真实的子 Agent 协作链路。
        return True

    def _append_agent_relay_event(self, event: Dict[str, Any]) -> None:
        path = self.studio_dir / "agent_relay.events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False)
        with self.store_lock:
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def _extract_agent_text_payload(self, payload: Optional[Dict[str, Any]], fallback: str = "") -> str:
        if isinstance(payload, dict):
            result = payload.get("result") or {}
            text_payloads = result.get("payloads") or []
            if isinstance(text_payloads, list):
                for item in text_payloads:
                    if not isinstance(item, dict):
                        continue
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        return text.strip()

        raw = str(fallback or "").strip()
        if not raw:
            return ""
        return raw[-2000:]

    def _run_agent_turn(self, *, agent_id: str, message: str, timeout: int = 75) -> Dict[str, Any]:
        started = now_dt()
        cmd = [
            "openclaw",
            "--profile",
            self.profile,
            "agent",
            "--agent",
            str(agent_id),
            "--message",
            str(message),
            "--timeout",
            str(max(20, int(timeout))),
            "--json",
        ]

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=max(30, int(timeout)) + 20,
                check=False,
            )
            ended = now_dt()
            payload = self._extract_json_object(proc.stdout)
            reply_text = self._extract_agent_text_payload(payload, proc.stdout)
            return {
                "ok": proc.returncode == 0,
                "code": proc.returncode,
                "agentId": agent_id,
                "reply": reply_text[:1600],
                "durationMs": int((ended - started).total_seconds() * 1000),
                "stdoutTail": (proc.stdout or "")[-1200:],
                "stderrTail": (proc.stderr or "")[-1200:],
                "startedAt": started.isoformat(),
                "endedAt": ended.isoformat(),
            }
        except Exception as exc:  # noqa: BLE001
            ended = now_dt()
            return {
                "ok": False,
                "code": -1,
                "agentId": agent_id,
                "reply": "",
                "durationMs": int((ended - started).total_seconds() * 1000),
                "stdoutTail": "",
                "stderrTail": str(exc),
                "startedAt": started.isoformat(),
                "endedAt": ended.isoformat(),
            }

    def _relay_stage_agents(
        self,
        *,
        payload: Dict[str, Any],
        venture: Dict[str, Any],
        stage: str,
        action: str,
        owner_agent: str,
        notify_agents: List[str],
        handoff_paths: Optional[List[Path]] = None,
        stage_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self._agent_relay_enabled(payload):
            return {
                "enabled": False,
                "reason": "agentRelayDisabled",
            }

        handoffs: List[Dict[str, Any]] = []
        for raw in (handoff_paths or []):
            path = Path(raw)
            rel_path = None
            try:
                rel_path = str(path.resolve().relative_to(self.repo_root))
            except Exception:
                rel_path = str(path)

            item = {
                "path": rel_path,
                "exists": bool(path.exists() and path.is_file()),
            }
            if path.exists() and path.is_file():
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                    item["sha16"] = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
                except Exception:
                    pass
            handoffs.append(item)

        base_context = {
            "kind": "studio_stage_event.v1",
            "stage": stage,
            "action": action,
            "ventureId": venture.get("id"),
            "opportunityId": canonical_opp_id(venture.get("opportunityId")) or venture.get("opportunityId"),
            "cycle": venture.get("cycle"),
            "timestamp": now_iso(),
            "handoffs": handoffs,
            "summary": stage_summary or {},
        }

        owner_request = {
            **base_context,
            "relayRole": "owner",
            "request": "请读取你工作区内相关最新产物，输出紧凑 JSON：{ack,summary,next_actions,risks}。",
        }
        owner_res = self._run_agent_turn(agent_id=owner_agent, message=json.dumps(owner_request, ensure_ascii=False), timeout=75)
        owner_reply = str(owner_res.get("reply") or "")

        self._append_agent_relay_event(
            {
                "id": f"relay_{uuid.uuid4().hex[:10]}",
                "createdAt": now_iso(),
                "ventureId": venture.get("id"),
                "stage": stage,
                "action": action,
                "agentId": owner_agent,
                "relayRole": "owner",
                "ok": bool(owner_res.get("ok")),
                "durationMs": owner_res.get("durationMs"),
                "reply": owner_reply[:800],
                "error": owner_res.get("stderrTail") if not owner_res.get("ok") else None,
            }
        )

        notify_results: List[Dict[str, Any]] = []
        for target in notify_agents:
            req = {
                **base_context,
                "relayRole": "downstream",
                "fromAgent": owner_agent,
                "toAgent": target,
                "ownerReply": owner_reply[:1200],
                "request": "请确认是否可接棒下一阶段，并输出 JSON：{ack,ready,next_inputs_needed,risks}。",
            }
            res = self._run_agent_turn(agent_id=target, message=json.dumps(req, ensure_ascii=False), timeout=60)
            reply = str(res.get("reply") or "")
            notify_results.append(
                {
                    "agentId": target,
                    "ok": bool(res.get("ok")),
                    "reply": reply[:500],
                    "durationMs": res.get("durationMs"),
                }
            )
            self._append_agent_relay_event(
                {
                    "id": f"relay_{uuid.uuid4().hex[:10]}",
                    "createdAt": now_iso(),
                    "ventureId": venture.get("id"),
                    "stage": stage,
                    "action": action,
                    "agentId": target,
                    "relayRole": "downstream",
                    "ok": bool(res.get("ok")),
                    "durationMs": res.get("durationMs"),
                    "reply": reply[:800],
                    "error": res.get("stderrTail") if not res.get("ok") else None,
                }
            )

        return {
            "enabled": True,
            "stage": stage,
            "action": action,
            "owner": {
                "agentId": owner_agent,
                "ok": bool(owner_res.get("ok")),
                "reply": owner_reply[:500],
                "durationMs": owner_res.get("durationMs"),
            },
            "notifications": notify_results,
            "handoffs": handoffs,
        }

    def _copy_artifacts(
        self,
        venture_id: str,
        stage: str,
        run_id: str,
        paths: Iterable[Path],
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        base = self.artifacts_dir / venture_id / run_id
        base.mkdir(parents=True, exist_ok=True)

        for raw in paths:
            path = Path(raw)
            if not path.exists() or not path.is_file():
                continue

            rel_source = None
            try:
                rel_source = str(path.resolve().relative_to(self.repo_root))
            except Exception:
                rel_source = str(path.resolve())

            filename = path.name
            safe_name = f"{len(out)+1:02d}_{slugify(filename, 120)}"
            if "." in filename:
                ext = filename.split(".")[-1]
                if not safe_name.endswith(ext):
                    safe_name = f"{safe_name}.{ext}"
            dst = base / safe_name
            shutil.copy2(path, dst)

            out.append(
                {
                    "id": f"art_{uuid.uuid4().hex[:10]}",
                    "ventureId": venture_id,
                    "stage": stage,
                    "type": path.suffix.lstrip(".") or "file",
                    "sourcePath": rel_source,
                    "snapshotPath": str(dst.relative_to(self.repo_root)),
                    "createdAt": now_iso(),
                }
            )
        return out

    def _append_run(self, record: Dict[str, Any]) -> None:
        with self.store_lock:
            payload = self._load_runs()
            items = payload.get("items", [])
            items.append(record)
            if len(items) > 500:
                items = items[-500:]
            payload["items"] = items
            self._save_runs(payload)

    def _append_gate(self, record: Dict[str, Any]) -> None:
        with self.store_lock:
            payload = self._load_gates()
            items = payload.get("items", [])
            items.append(record)
            if len(items) > 500:
                items = items[-500:]
            payload["items"] = items
            self._save_gates(payload)

    def _artifact_latest_by_stage(self, venture_id: str) -> Dict[str, Dict[str, Any]]:
        runs_payload = self._load_runs()
        latest: Dict[str, Dict[str, Any]] = {}
        for run in runs_payload.get("items", []):
            if run.get("ventureId") != venture_id:
                continue
            stage = str(run.get("stage") or "UNKNOWN")
            created = str(run.get("createdAt") or "")
            prev = latest.get(stage)
            if not prev or str(prev.get("createdAt") or "") <= created:
                latest[stage] = run
        return latest

    def _sync_venture_context(self, venture_id: str) -> None:
        venture = self._require_venture(venture_id)
        opp_id = venture.get("opportunityId")
        context = {
            "venture": {
                "id": venture.get("id"),
                "name": venture.get("name"),
                "stage": venture.get("stage"),
                "status": venture.get("status"),
                "cycle": venture.get("cycle"),
                "opportunityId": opp_id,
                "selections": venture.get("selections") or {},
                "links": venture.get("links") or {},
            },
            "activeContext": self._read_active_context(opp_id),
            "latestRunsByStage": {
                stage: self._summarize_run(run, include_details=False)
                for stage, run in self._artifact_latest_by_stage(venture_id).items()
            },
            "updatedAt": now_iso(),
        }
        self._write_venture_context(venture_id, context)

    # ------------------------------------------------------------------
    # Ideas / ventures
    # ------------------------------------------------------------------
    def _ideas_paths(self) -> Tuple[Path, Path]:
        return (
            self.product_dir / "research/stage1_idea_discovery/opportunity_records.json",
            self.product_dir / "research/stage2_idea_screening/decision_log.json",
        )

    def list_ideas(self) -> List[Dict[str, Any]]:
        stage1_path, stage2_path = self._ideas_paths()
        if not stage1_path.exists():
            return []

        try:
            stage1 = json.loads(stage1_path.read_text())
        except Exception:
            return []

        stage2 = {}
        if stage2_path.exists():
            try:
                stage2 = json.loads(stage2_path.read_text())
            except Exception:
                stage2 = {}

        decisions = {}
        for row in (stage2.get("decisions") or []):
            if not isinstance(row, dict):
                continue
            opp = canonical_opp_id(row.get("opportunity_id"))
            if opp:
                decisions[opp] = row

        ideas: List[Dict[str, Any]] = []
        for opp in stage1.get("opportunities", []) or []:
            if not isinstance(opp, dict):
                continue
            opp_id = canonical_opp_id(opp.get("opportunity_id"))
            if not opp_id:
                continue

            dec = decisions.get(opp_id, {})
            target = opp.get("target_segment") or {}
            pains = opp.get("pain_evidence") or []
            lead_pain = pains[0].get("claim") if pains and isinstance(pains[0], dict) else ""

            risk_list: List[str] = []
            for item in opp.get("implementation_constraint") or []:
                if item:
                    risk_list.append(str(item))
            dec_scores = (dec.get("scores") or {}) if isinstance(dec, dict) else {}
            for score_key, score_val in dec_scores.items():
                if isinstance(score_val, dict):
                    risk = score_val.get("risk_if_wrong")
                    if risk:
                        risk_list.append(str(risk))

            idea = {
                "opportunityId": opp_id,
                "title": f"{target.get('role', 'Operator')} · {opp.get('core_problem', '')[:80]}",
                "segment": target,
                "coreProblem": opp.get("core_problem"),
                "currentWorkaround": opp.get("current_workaround"),
                "motivation": {
                    "leadPainEvidence": lead_pain,
                    "distributionEntry": (opp.get("distribution_entry") or {}).get("first_20_targets_how"),
                    "budgetSignal": (opp.get("budget_signal") or {}).get("evidence"),
                    "urgencySignal": (opp.get("urgency_signal") or {}).get("evidence"),
                },
                "riskSummary": risk_list[:5],
                "feasibilityScore": dec.get("weighted_score"),
                "decision": dec.get("decision"),
                "confidence": (dec.get("confidence") or {}).get("level"),
                "hardGatePass": ((opp.get("hard_gate_check") or {}).get("pass")),
            }
            ideas.append(idea)

        state = self._load_state()
        nonce = int(state.get("ideaNonce", 0) or 0)

        def _rank(item: Dict[str, Any]) -> float:
            base = float(item.get("feasibilityScore") or 0.0)
            if nonce <= 0:
                return base
            key = f"{item.get('opportunityId')}::{nonce}"
            jitter = (abs(hash(key)) % 1000) / 1000.0
            return base + jitter * 0.3

        ideas.sort(key=_rank, reverse=True)
        return ideas

    def _find_venture(self, ventures: List[Dict[str, Any]], venture_id: str) -> Optional[Dict[str, Any]]:
        for item in ventures:
            if item.get("id") == venture_id:
                return item
        return None

    def _require_venture(self, venture_id: str) -> Dict[str, Any]:
        with self.store_lock:
            payload = self._load_ventures()
            ventures = payload.get("items", [])
            venture = self._find_venture(ventures, venture_id)
            if not venture:
                raise StudioError(f"venture not found: {venture_id}")
            return copy.deepcopy(venture)

    def _require_stage(self, venture: Dict[str, Any], expected_stage: str, action: str) -> None:
        current = str(venture.get("stage") or "IDEA_POOL")
        if current == expected_stage:
            return

        pending = self._pending_transition(venture)
        if pending:
            from_stage = str(pending.get("fromStage") or current)
            to_stage = str(pending.get("toStage") or "UNKNOWN")
            source_action = str(pending.get("sourceAction") or "unknown_action")
            raise StudioError(
                f"{action} requires stage={expected_stage}, current={current}. "
                f"Current blocker: pending transition {from_stage}->{to_stage} (source={source_action}). "
                "Please confirm or reject that transition first."
            )

        raise StudioError(
            f"{action} requires stage={expected_stage}, current={current}. "
            "Current blocker: stage mismatch (no pending transition). "
            f"Run actions for {current} stage or move venture to {expected_stage} first."
        )

    def _update_venture(self, venture_id: str, updater) -> Dict[str, Any]:
        with self.store_lock:
            payload = self._load_ventures()
            ventures = payload.get("items", [])
            idx = -1
            for i, item in enumerate(ventures):
                if item.get("id") == venture_id:
                    idx = i
                    break
            if idx < 0:
                raise StudioError(f"venture not found: {venture_id}")
            current = ventures[idx]
            updated = updater(copy.deepcopy(current))
            updated["updatedAt"] = now_iso()
            ventures[idx] = updated
            payload["items"] = ventures
            self._save_ventures(payload)
            return copy.deepcopy(updated)

    def _pending_transition(self, venture: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not isinstance(venture, dict):
            return None
        trans = venture.get("pendingTransition")
        if not isinstance(trans, dict):
            return None
        if str(trans.get("status") or "pending") != "pending":
            return None
        return trans

    def _propose_stage_transition(
        self,
        *,
        venture_id: str,
        to_stage: str,
        reason: str,
        source_action: str,
        summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if to_stage not in STAGE_ORDER:
            raise StudioError(f"unsupported stage transition target: {to_stage}")

        transition_id = f"tran_{uuid.uuid4().hex[:10]}"

        def _up(v: Dict[str, Any]) -> Dict[str, Any]:
            current_stage = str(v.get("stage") or "IDEA_POOL")
            pending = {
                "id": transition_id,
                "status": "pending",
                "fromStage": current_stage,
                "toStage": to_stage,
                "reason": reason,
                "sourceAction": source_action,
                "summary": summary or {},
                "createdAt": now_iso(),
                "requiresConfirmation": True,
            }
            v["pendingTransition"] = pending
            return v

        return self._update_venture(venture_id, _up)

    def _apply_stage_transition(
        self,
        *,
        venture_id: str,
        decision: str,
        note: str,
        expected_transition_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        decision = str(decision or "approved").strip().lower()
        if decision not in {"approved", "rejected"}:
            raise StudioError("decision must be approved or rejected")

        def _up(v: Dict[str, Any]) -> Dict[str, Any]:
            pending = self._pending_transition(v)
            if not pending:
                raise StudioError("no pending stage transition")
            if expected_transition_id and str(pending.get("id")) != expected_transition_id:
                raise StudioError("transition id mismatch")

            from_stage = str(pending.get("fromStage") or v.get("stage") or "IDEA_POOL")
            to_stage = str(pending.get("toStage") or from_stage)

            history_item = {
                "id": pending.get("id") or f"tran_{uuid.uuid4().hex[:8]}",
                "decidedAt": now_iso(),
                "decision": decision,
                "fromStage": from_stage,
                "toStage": to_stage,
                "reason": pending.get("reason"),
                "sourceAction": pending.get("sourceAction"),
                "note": note,
            }
            history = [x for x in (v.get("transitionHistory") or []) if isinstance(x, dict)]
            history.append(history_item)
            v["transitionHistory"] = history[-60:]

            if decision == "approved":
                v["stage"] = to_stage
                if from_stage == "ITERATE" and to_stage == "PRODUCT":
                    v["cycle"] = int(v.get("cycle", 1) or 1) + 1
                v["status"] = "active"

            v.pop("pendingTransition", None)
            return v

        return self._update_venture(venture_id, _up)

    def create_venture(self, opportunity_id: str, name: Optional[str] = None) -> Dict[str, Any]:
        opp_id = canonical_opp_id(opportunity_id)
        if not opp_id:
            raise StudioError("invalid opportunity id")

        ideas = self.list_ideas()
        selected = None
        for idea in ideas:
            if canonical_opp_id(idea.get("opportunityId")) == opp_id:
                selected = idea
                break
        if not selected:
            raise StudioError(f"opportunity not found in idea pool: {opp_id}")

        venture_id = f"venture-{slugify(opp_id)}-{now_dt().strftime('%Y%m%d%H%M%S')}"
        venture_name = name.strip() if isinstance(name, str) and name.strip() else selected.get("title") or opp_id

        venture = {
            "id": venture_id,
            "name": venture_name,
            "opportunityId": opp_id,
            "stage": "SELECTED",
            "status": "active",
            "cycle": 1,
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
            "selectedIdea": selected,
            "selections": {
                "contentApprovedIds": [],
                "contentRejectedIds": [],
                "campaignId": None,
                "salesSegmentIndex": None,
                "outreachBatchApproved": False,
            },
            "links": {},
            "kpiSnapshots": [],
            "lastActions": {},
        }

        with self.store_lock:
            ventures_payload = self._load_ventures()
            items = ventures_payload.get("items", [])
            items.append(venture)
            ventures_payload["items"] = items
            self._save_ventures(ventures_payload)

            state = self._load_state()
            state["activeVentureId"] = venture_id
            self._save_state(state)

        self._append_gate(
            {
                "gateId": f"gate_{uuid.uuid4().hex[:10]}",
                "ventureId": venture_id,
                "stage": "IDEA_POOL",
                "decision": "approved",
                "reason": "venture_selected_from_idea_pool",
                "decidedAt": now_iso(),
            }
        )

        self._sync_venture_context(venture_id)
        return venture

    def set_active_venture(self, venture_id: str) -> Dict[str, Any]:
        venture = self._require_venture(venture_id)
        with self.store_lock:
            state = self._load_state()
            state["activeVentureId"] = venture["id"]
            self._save_state(state)
        self._sync_venture_context(venture_id)
        return venture

    # ------------------------------------------------------------------
    # Job management
    # ------------------------------------------------------------------
    def _job_update(self, job_id: str, updates: Dict[str, Any]) -> None:
        with self.jobs_lock:
            if job_id not in self.jobs:
                return
            self.jobs[job_id].update(updates)

    def _submit_job(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = payload.get("ventureId")
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job = {
            "id": job_id,
            "action": action,
            "ventureId": venture_id,
            "status": "queued",
            "createdAt": now_iso(),
        }
        with self.jobs_lock:
            self.jobs[job_id] = job

        def runner() -> None:
            self._job_update(job_id, {"status": "running", "startedAt": now_iso()})
            try:
                result = self._run_action_sync(action, payload)
                self._job_update(
                    job_id,
                    {
                        "status": "succeeded",
                        "finishedAt": now_iso(),
                        "result": result,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self._job_update(
                    job_id,
                    {
                        "status": "failed",
                        "finishedAt": now_iso(),
                        "error": str(exc),
                        "traceback": traceback.format_exc()[-4000:],
                    },
                )

        self.executor.submit(runner)
        return copy.deepcopy(job)

    def _summarize_job(self, job: Dict[str, Any], *, include_result: bool = False) -> Dict[str, Any]:
        summary = {
            "id": job.get("id"),
            "action": job.get("action"),
            "ventureId": job.get("ventureId"),
            "status": job.get("status"),
            "createdAt": job.get("createdAt"),
            "startedAt": job.get("startedAt"),
            "finishedAt": job.get("finishedAt"),
            "error": job.get("error"),
        }
        if include_result:
            summary["result"] = job.get("result")
        else:
            result = job.get("result") or {}
            run = result.get("run") if isinstance(result, dict) else None
            if isinstance(run, dict):
                summary["resultSummary"] = {
                    "runId": run.get("id"),
                    "stage": run.get("stage"),
                    "status": run.get("status"),
                }
        return summary

    def list_jobs(self, *, include_result: bool = False) -> List[Dict[str, Any]]:
        with self.jobs_lock:
            items = [self._summarize_job(copy.deepcopy(v), include_result=include_result) for v in self.jobs.values()]
        items.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
        return items[:100]

    def get_job(self, job_id: str, *, include_result: bool = True) -> Optional[Dict[str, Any]]:
        with self.jobs_lock:
            item = self.jobs.get(job_id)
            if not item:
                return None
            return self._summarize_job(copy.deepcopy(item), include_result=include_result)

    # ------------------------------------------------------------------
    # Action execution helpers
    # ------------------------------------------------------------------
    def _record_run(
        self,
        *,
        venture_id: Optional[str],
        stage: str,
        action: str,
        mode: str,
        status: str,
        steps: List[Dict[str, Any]],
        artifacts: List[Dict[str, Any]],
        summary: Dict[str, Any],
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        started = steps[0].get("startedAt") if steps else now_iso()
        ended = steps[-1].get("endedAt") if steps else now_iso()
        run = {
            "id": f"run_{uuid.uuid4().hex[:12]}",
            "ventureId": venture_id,
            "stage": stage,
            "action": action,
            "mode": mode,
            "status": status,
            "startedAt": started,
            "endedAt": ended,
            "steps": steps,
            "artifacts": artifacts,
            "summary": summary,
            "error": error,
            "createdAt": now_iso(),
        }
        self._append_run(run)
        return run

    def _command_step(self, name: str, cmd: List[str], cwd: Path, timeout: int = 1800) -> Dict[str, Any]:
        res = self._run_cmd(cmd, cwd=cwd, timeout=timeout)
        return {
            "name": name,
            "command": cmd,
            "cwd": res.cwd,
            "status": "passed" if res.ok else "failed",
            "code": res.code,
            "startedAt": res.started_at,
            "endedAt": res.ended_at,
            "durationMs": res.duration_ms,
            "stdoutTail": res.stdout_tail,
            "stderrTail": res.stderr_tail,
        }

    def _extract_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        raw = str(text or "")
        if not raw.strip():
            return None

        # Fast path: whole text is JSON object
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass

        # Fallback: locate first balanced JSON object in text
        start = raw.find("{")
        while start >= 0:
            depth = 0
            for idx in range(start, len(raw)):
                ch = raw[idx]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = raw[start : idx + 1]
                        try:
                            payload = json.loads(candidate)
                            if isinstance(payload, dict):
                                return payload
                        except Exception:
                            pass
                        break
            start = raw.find("{", start + 1)
        return None

    def _copilot_compact_context(
        self,
        *,
        active_venture: Optional[Dict[str, Any]],
        progress: Dict[str, Any],
        recommended_actions: List[Dict[str, Any]],
        pending_questions: List[Dict[str, Any]],
        manual_arm_enabled: bool,
        active_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        venture = active_venture or {}
        marketing_ctx = (active_context or {}).get("marketing") or {}
        sales_ctx = (active_context or {}).get("sales") or {}
        ops_ctx = (active_context or {}).get("operations") or {}

        core = {
            "ventureId": venture.get("id"),
            "opportunityId": venture.get("opportunityId"),
            "stage": progress.get("stage"),
            "stageIndex": progress.get("index"),
            "stageTotal": progress.get("total"),
            "cycle": venture.get("cycle"),
            "manualArmEnabled": manual_arm_enabled,
            "pendingTransition": venture.get("pendingTransition"),
            "selectedCampaignId": ((venture.get("selections") or {}).get("campaignId")),
            "recommendedActions": [
                {
                    "action": x.get("action"),
                    "label": x.get("label"),
                    "stage": x.get("stage"),
                    "requiresUserChoice": bool(x.get("requiresUserChoice")),
                }
                for x in recommended_actions[:8]
            ],
            "pendingQuestions": [
                {
                    "id": q.get("id"),
                    "priority": q.get("priority"),
                    "question": q.get("question"),
                }
                for q in pending_questions[:8]
            ],
            "signals": {
                "marketing": {
                    "campaignCandidates": len(marketing_ctx.get("campaignCandidates") or []),
                    "contentApproved": len(marketing_ctx.get("contentApproved") or []),
                    "stage3Status": (marketing_ctx.get("stage3Run") or {}).get("status"),
                },
                "sales": {
                    "segmentIndex": sales_ctx.get("segmentIndex"),
                    "outreachBatchReady": bool(sales_ctx.get("outreachBatchReady")),
                    "outreachBatchApproved": bool(sales_ctx.get("outreachBatchApproved")),
                },
                "operations": {
                    "writebackItems": len(ops_ctx.get("writebackItems") or []),
                    "kpiKeys": list((ops_ctx.get("kpiSnapshot") or {}).get("metrics", {}).keys())[:6],
                },
            },
        }

        if not venture.get("id"):
            ideas = self.list_ideas()[:5]
            core["ideaCandidates"] = [
                {
                    "opportunityId": x.get("opportunityId"),
                    "title": x.get("title"),
                    "coreProblem": x.get("coreProblem"),
                    "feasibilityScore": x.get("feasibilityScore"),
                    "hardGatePass": x.get("hardGatePass"),
                }
                for x in ideas
            ]
        digest = hashlib.sha1(json.dumps(core, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]
        core["contextHash"] = digest
        return core

    def _call_copilot_llm(self, user_prompt: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        instruction = {
            "task": "You are OperatorOne Studio Copilot. Answer user in concise Simplified Chinese.",
            "requirements": [
                "Ground answer on provided context only.",
                "Do not fabricate stage state or tool outputs.",
                "If transition confirmation is required, explicitly mention it.",
                "Prefer simulation-first recommendations unless user explicitly asks live.",
            ],
            "output_schema": {
                "answer": "string",
                "suggestedActionIds": ["string"],
                "questionsForUser": ["string"],
                "riskFlags": ["string"],
                "tone": "brief"
            },
            "user_prompt": user_prompt,
            "context": context,
            "respond": "Return JSON object only. No markdown.",
        }

        cmd = [
            "openclaw",
            "--profile",
            "operatorone",
            "agent",
            "--to",
            COPILOT_TO,
            "--message",
            json.dumps(instruction, ensure_ascii=False),
            "--timeout",
            str(COPILOT_TIMEOUT_SECONDS),
            "--json",
        ]

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=COPILOT_TIMEOUT_SECONDS + 30,
                check=False,
            )
        except Exception:
            return None

        if proc.returncode != 0:
            return None

        payload = self._extract_json_object(proc.stdout)
        if not payload:
            return None
        text_payloads = (((payload.get("result") or {}).get("payloads") or []))
        if not text_payloads:
            return None

        model_text = str((text_payloads[0] or {}).get("text") or "")
        model_json = self._extract_json_object(model_text)
        if not isinstance(model_json, dict):
            return None
        return model_json

    def _parse_json(self, path: Path, default: Any = None) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text())
        except Exception:
            return default

    def _read_active_context(self, opp_id: Optional[str]) -> Dict[str, Any]:
        marketing_stage1 = self._parse_json(
            self.marketing_dir / "research/stage1_marketing_seo/experiments.queue.latest.json",
            {},
        )
        stage1_ready = []
        for item in ((marketing_stage1.get("queue") or {}).get("ready") or []):
            if item_matches_opp(item, opp_id):
                stage1_ready.append(
                    {
                        "experiment_id": item.get("experiment_id"),
                        "opportunity_id": item.get("opportunity_id"),
                        "primary_keyword": item.get("primary_keyword"),
                        "intent": item.get("intent"),
                        "queue_state": item.get("queue_state"),
                        "score": item.get("score") or item.get("priority_score"),
                    }
                )

        marketing_stage2 = self._parse_json(
            self.marketing_dir / "research/stage2_content_publish/publish.queue.latest.json",
            {},
        )
        content_candidates = []
        for bucket in ["approved", "review_ready", "needs_revision", "blocked"]:
            for item in ((marketing_stage2.get("queue") or {}).get(bucket) or []):
                if item_matches_opp(item, opp_id):
                    content_candidates.append(
                        {
                            "content_id": item.get("content_id") or item.get("id"),
                            "_bucket": bucket,
                            "topic": item.get("topic"),
                            "primary_keyword": item.get("primary_keyword") or item.get("keyword"),
                            "priority_score": item.get("priority_score") or item.get("score"),
                            "opportunity_id": item.get("opportunity_id"),
                            "summary": item.get("summary") or item.get("angle"),
                            "channel": item.get("channel") or item.get("platform"),
                            "cta": item.get("cta") or item.get("call_to_action"),
                            "raw": item,
                        }
                    )

        marketing_stage3 = self._parse_json(
            self.marketing_dir / "research/stage3_campaign_launch/campaigns.queue.latest.json",
            {},
        )
        campaign_candidates = []
        for bucket in ["launch_ready", "watchlist", "hold"]:
            for item in ((marketing_stage3.get("queue") or {}).get(bucket) or []):
                if item_matches_opp(item, opp_id):
                    campaign_candidates.append(
                        {
                            "campaign_id": item.get("campaign_id") or item.get("id"),
                            "_bucket": bucket,
                            "primary_keyword": item.get("primary_keyword") or item.get("keyword"),
                            "readiness_score": item.get("readiness_score") or item.get("score"),
                            "opportunity_id": item.get("opportunity_id"),
                            "ad_copy": item.get("ad_copy") or item.get("copy"),
                            "channel": item.get("channel") or item.get("platform"),
                            "budget": item.get("budget"),
                            "raw": item,
                        }
                    )

        prospect_queue = self._parse_json(
            self.sales_dir / "research/prospecting/prospect_queue.latest.json",
            {},
        )
        segments = []
        for idx, seg in enumerate(prospect_queue.get("segments") or []):
            if item_matches_opp(seg, opp_id):
                scores = seg.get("scores") or {}
                segments.append(
                    {
                        "segmentIndex": idx,
                        "segment_name": seg.get("segment_name") or ((seg.get("target_segment") or {}).get("role")),
                        "scores": {
                            "estimated_weekly_leads": scores.get("estimated_weekly_leads") or scores.get("weekly_leads"),
                            "estimated_weekly_mql": scores.get("estimated_weekly_mql") or scores.get("weekly_mql"),
                            "segment_score": scores.get("segment_score") or scores.get("score"),
                        },
                    }
                )

        outreach_ready = self._parse_json(
            self.sales_dir / "research/outreach/outreach_batch.ready.json",
            {},
        )
        outreach_dispatch = self._parse_json(
            self.sales_dir / "research/outreach/outreach_dispatch_report.latest.json",
            {},
        )

        close_motion = self._parse_json(
            self.sales_dir / "research/conversion/close_motion.latest.json",
            {},
        )

        ops_stage1 = self._parse_json(
            self.operations_dir / "research/stage1_tracking/stage1_scoreboard.latest.json",
            {},
        )
        ops_stage2 = self._parse_json(
            self.operations_dir / "research/stage2_feedback/stage2_feedback_scoreboard.latest.json",
            {},
        )
        ops_stage3 = self._parse_json(
            self.operations_dir / "research/stage3_product_iteration/stage3_iteration_scoreboard.latest.json",
            {},
        )

        stage1_summary = ops_stage1.get("summary") or {}
        stage2_summary = ops_stage2.get("summary") or {}
        stage3_summary = ops_stage3.get("summary") or {}

        content_counts = {
            k: len(((marketing_stage2.get("queue") or {}).get(k) or []))
            for k in ["approved", "review_ready", "needs_revision", "blocked"]
        }
        campaign_counts = {
            k: len(((marketing_stage3.get("queue") or {}).get(k) or []))
            for k in ["launch_ready", "watchlist", "hold"]
        }
        campaign_total = sum(campaign_counts.values())
        blockers: List[Dict[str, Any]] = []
        if str(marketing_stage3.get("status") or "").lower() in {"blocked_no_launchable_assets", "no_launchable_assets"}:
            blockers.append(
                {
                    "id": "marketing_stage3_no_launchable_assets",
                    "severity": "warning",
                    "message": "当前没有可发布 campaign 资产（不是能力缺失，而是当前数据结果）。",
                    "recommended": ["继续跑 SEO/content 产出更多候选", "或直接进入 Sales prospecting 走 fallback"],
                }
            )
        if campaign_total == 0:
            blockers.append(
                {
                    "id": "marketing_campaign_queue_empty",
                    "severity": "info",
                    "message": "campaign 队列为空，暂时无法“选为 Sales 输入”。",
                    "recommended": ["继续生成 campaign 候选", "或直接执行 Sales 阶段动作"],
                }
            )

        return {
            "marketing": {
                "stage1Ready": stage1_ready[:30],
                "contentCandidates": content_candidates[:50],
                "campaignCandidates": campaign_candidates[:50],
                "stage2Status": marketing_stage2.get("status"),
                "stage3Status": marketing_stage3.get("status"),
                "blockers": blockers,
                "queueCounts": {
                    "content": content_counts,
                    "campaign": campaign_counts,
                },
            },
            "sales": {
                "segments": segments[:20],
                "outreachBatchReady": {
                    "generated_at": outreach_ready.get("generated_at"),
                    "segment_index": outreach_ready.get("segment_index"),
                    "message_count": len(outreach_ready.get("messages") or []),
                    "status": outreach_ready.get("status"),
                },
                "outreachDispatch": {
                    "generated_at": outreach_dispatch.get("generated_at"),
                    "mode": outreach_dispatch.get("mode"),
                    "summary": outreach_dispatch.get("summary"),
                },
                "closeMotion": {
                    "generated_at": close_motion.get("generated_at"),
                    "headline": close_motion.get("headline") or close_motion.get("summary"),
                },
            },
            "operations": {
                "stage1": {
                    "sessions": ((stage1_summary.get("traffic") or {}).get("sessions")),
                    "qualified_signups": ((stage1_summary.get("signups") or {}).get("qualified_signups")),
                    "paid_customers": ((stage1_summary.get("signups") or {}).get("paid_customers")),
                    "net_new_mrr": ((stage1_summary.get("revenue") or {}).get("net_new_mrr")),
                },
                "stage2": {
                    "feedback_items_total": ((stage2_summary.get("feedback") or {}).get("feedback_items_total")),
                    "themes_total": ((stage2_summary.get("feedback") or {}).get("themes_total")),
                    "expected_mrr_delta_30d": ((stage2_summary.get("impact") or {}).get("expected_mrr_delta_30d")),
                },
                "stage3": {
                    "experiments_planned": ((stage3_summary.get("flow") or {}).get("experiments_planned")),
                    "ship_count": ((stage3_summary.get("outcomes") or {}).get("ship_count")),
                    "iterate_count": ((stage3_summary.get("outcomes") or {}).get("iterate_count")),
                    "observed_mrr_delta_30d": ((stage3_summary.get("outcomes") or {}).get("observed_mrr_delta_30d")),
                },
            },
        }

    def _capability_summary(self, monitor_snapshot: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(monitor_snapshot, dict):
            return {"total": 0, "passed": 0, "failed": 0, "byAgent": []}

        caps = monitor_snapshot.get("capabilities") or []
        passed = sum(1 for c in caps if str((c or {}).get("status")) == "passed")
        failed = sum(1 for c in caps if str((c or {}).get("status")) != "passed")
        by_agent = []
        for row in monitor_snapshot.get("agents") or []:
            by_agent.append(
                {
                    "agent": row.get("agent"),
                    "status": row.get("status"),
                    "passed": row.get("passed"),
                    "failed": row.get("failed"),
                    "capabilityTotal": row.get("capabilityTotal"),
                }
            )

        return {
            "total": len(caps),
            "passed": passed,
            "failed": failed,
            "byAgent": by_agent,
        }

    def _with_utm(self, url: Optional[str], *, source: str, medium: str, campaign: str, content: str) -> Optional[str]:
        if not url or not isinstance(url, str) or not url.startswith("http"):
            return None
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query.update(
            {
                "utm_source": source,
                "utm_medium": medium,
                "utm_campaign": campaign,
                "utm_content": content,
            }
        )
        return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

    def _find_landing_url(self, landing: Dict[str, Any]) -> Optional[str]:
        for value in flatten_strings(landing):
            text = str(value).strip()
            if text.startswith("http://") or text.startswith("https://"):
                return text
        return None

    def _latest_preview_path_for_venture(self, venture_id: str) -> Optional[Path]:
        deployments = self._parse_json(self.deployments_path, {"items": []}).get("items") or []
        for row in reversed(deployments):
            if str(row.get("ventureId") or "") != str(venture_id):
                continue
            preview = row.get("previewPath")
            if not preview:
                continue
            p = Path(str(preview))
            if not p.is_absolute():
                p = (self.repo_root / p).resolve()
            else:
                p = p.resolve()
            if p.exists():
                return p
        return None

    def _ensure_landing_preview_html(self, venture: Dict[str, Any]) -> Optional[str]:
        venture_id = str(venture.get("id") or "").strip()
        if not venture_id:
            return None

        landing = self._parse_json(self.product_dir / "research/landing_v1/landing_package.json", {})
        headline = deep_find_first_value(landing, ["headline", "hero_headline", "title", "value_proposition"]) or "Landing Preview"
        subheadline = deep_find_first_value(landing, ["subheadline", "value_proposition", "description"]) or ""
        cta = deep_find_first_value(landing, ["cta", "primary_cta", "button_text", "call_to_action"]) or "Join waitlist"

        bullets: List[str] = []
        for value in flatten_strings(landing):
            text = str(value).strip()
            if len(text) < 20:
                continue
            if text in {headline, subheadline}:
                continue
            bullets.append(text)
            if len(bullets) >= 6:
                break

        out_dir = self.runtime_dir / "studio" / "landing_previews"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{venture_id}.html"

        bullet_html = "\n".join(f"<li>{html.escape(x)}</li>" for x in bullets)
        body = f"""<!doctype html>
<html lang=\"en\"><head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>{html.escape(str(headline))}</title>
<style>
body{{font-family:Inter,ui-sans-serif,system-ui;background:#0b1220;color:#e8efff;margin:0;padding:24px}}
.shell{{max-width:920px;margin:0 auto;background:#131c2b;border:1px solid #2b3b57;border-radius:14px;padding:24px}}
h1{{margin:0 0 10px;font-size:32px;line-height:1.2}}
p{{color:#b6c4db}}ul{{margin-top:16px}}li{{margin:8px 0}}
.cta{{display:inline-block;margin-top:16px;background:#4d82ff;color:white;padding:10px 16px;border-radius:999px;text-decoration:none;font-weight:700}}
.badge{{display:inline-block;font-size:12px;background:#22334f;color:#9ec2ff;padding:4px 10px;border-radius:999px;margin-bottom:10px}}
</style>
</head><body><main class=\"shell\">
<div class=\"badge\">Landing Page Preview (Readable)</div>
<h1>{html.escape(str(headline))}</h1>
<p>{html.escape(str(subheadline))}</p>
<ul>{bullet_html}</ul>
<a class=\"cta\" href=\"#\">{html.escape(str(cta))}</a>
</main></body></html>
"""
        out_file.write_text(body, encoding="utf-8")
        return str(out_file.relative_to(self.repo_root))

    def _sync_preview_with_gtm(self, venture: Dict[str, Any], *, preview_path: Optional[str] = None) -> Dict[str, Any]:
        venture_id = str(venture.get("id") or "").strip()
        opp_id = venture.get("opportunityId")
        if not venture_id:
            return {"ok": False, "reason": "missing venture id"}

        preview_dir = None
        if preview_path:
            p = Path(str(preview_path))
            if not p.is_absolute():
                p = (self.repo_root / p).resolve()
            else:
                p = p.resolve()
            if p.exists():
                preview_dir = p
        if not preview_dir:
            preview_dir = self._latest_preview_path_for_venture(venture_id)
        if not preview_dir:
            return {"ok": False, "reason": "preview path not found"}

        index_candidates = [
            preview_dir / "public" / "index.html",
            preview_dir / "index.html",
        ]
        index_path = None
        for c in index_candidates:
            if c.exists() and c.is_file():
                index_path = c
                break
        if not index_path:
            return {"ok": False, "reason": "preview index missing"}

        payload = self._build_message_pack(opp_id)
        pack = payload.get("messagePack") or {}
        campaign = payload.get("campaign") or {}
        sales = payload.get("sales") or {}
        links = payload.get("utmLinks") or {}

        value = str(pack.get("valueProposition") or "").strip()
        cta = str(pack.get("primaryCta") or "").strip()
        proof = str(pack.get("proofPoint") or "").strip()
        ad_copy = str(campaign.get("adCopy") or "").strip()
        sales_opening = str(sales.get("opening") or "").strip()

        content_queue = self._parse_json(self.marketing_dir / "research/stage2_content_publish/publish.queue.latest.json", {})
        campaign_queue = self._parse_json(self.marketing_dir / "research/stage3_campaign_launch/campaigns.queue.latest.json", {})

        content_items: List[Dict[str, Any]] = []
        for bucket in ["approved", "review_ready", "needs_revision", "blocked"]:
            for item in ((content_queue.get("queue") or {}).get(bucket) or []):
                if not item_matches_opp(item, opp_id):
                    continue
                content_items.append(
                    {
                        "bucket": bucket,
                        "title": item.get("selected_title") or item.get("title") or item.get("topic"),
                        "keyword": item.get("primary_keyword") or item.get("keyword"),
                        "cta": item.get("cta") or item.get("call_to_action"),
                    }
                )
                if len(content_items) >= 3:
                    break
            if len(content_items) >= 3:
                break

        campaign_items: List[Dict[str, Any]] = []
        for bucket in ["launch_ready", "watchlist", "hold"]:
            for item in ((campaign_queue.get("queue") or {}).get(bucket) or []):
                if not item_matches_opp(item, opp_id):
                    continue
                campaign_items.append(
                    {
                        "bucket": bucket,
                        "name": item.get("name") or item.get("title") or item.get("campaign_id"),
                        "channel": item.get("primary_channel") or item.get("channel"),
                        "budget": item.get("budget_total") or item.get("budget"),
                        "readiness": item.get("readiness_score") or item.get("score"),
                        "copy": item.get("ad_copy") or item.get("copy") or item.get("title"),
                    }
                )
                if len(campaign_items) >= 3:
                    break
            if len(campaign_items) >= 3:
                break

        prospect = self._parse_json(self.sales_dir / "research/prospecting/prospect_queue.latest.json", {})
        dispatch = self._parse_json(self.sales_dir / "research/outreach/outreach_dispatch_report.latest.json", {})
        conversion = self._parse_json(self.sales_dir / "research/conversion/conversion_scoreboard.latest.json", {})

        segment_name = None
        weekly_leads = None
        weekly_mql = None
        for seg in prospect.get("segments") or []:
            if item_matches_opp(seg, opp_id):
                segment_name = seg.get("segment_name") or seg.get("target_segment")
                scores = seg.get("scores") or {}
                weekly_leads = scores.get("estimated_weekly_leads")
                weekly_mql = scores.get("estimated_weekly_mql")
                break

        dispatch_summary = dispatch.get("summary") or {}
        conversion_summary = conversion.get("summary") or {}

        ops1 = self._parse_json(self.operations_dir / "research/stage1_tracking/stage1_scoreboard.latest.json", {})
        ops2 = self._parse_json(self.operations_dir / "research/stage2_feedback/stage2_feedback_scoreboard.latest.json", {})
        ops3 = self._parse_json(self.operations_dir / "research/stage3_product_iteration/stage3_iteration_scoreboard.latest.json", {})

        ops1_sum = ops1.get("summary") or {}
        ops2_sum = ops2.get("summary") or {}
        ops3_sum = ops3.get("summary") or {}

        caps: List[Dict[str, Any]] = []
        try:
            monitor_snapshot = collect_snapshot(runtime_flags={"manualArmEnabled": self._manual_arm_enabled()})
            for c in monitor_snapshot.get("capabilities") or []:
                caps.append({"label": c.get("label") or c.get("id"), "status": c.get("status")})
        except Exception:
            caps = []

        def _cap_color(status: str) -> str:
            s = str(status or "unknown").lower()
            if s == "passed":
                return "#0f9d58"
            if s in {"warning", "review_required"}:
                return "#c68a00"
            return "#d93025"

        content_html = "".join(
            f"<li><strong>{html.escape(str(x.get('title') or '-'))}</strong> "
            f"<span style='color:#60708a'>([{html.escape(str(x.get('bucket') or '-'))}] kw: {html.escape(str(x.get('keyword') or '-'))})</span>"
            f"<div style='font-size:12px;color:#44546b'>CTA: {html.escape(str(x.get('cta') or '-'))}</div></li>"
            for x in content_items
        )
        if not content_html:
            content_html = "<li>暂无可展示 content 项（先执行/审批 Publish content）</li>"

        campaign_html = "".join(
            f"<li><strong>{html.escape(str(x.get('name') or '-'))}</strong> "
            f"<span style='color:#60708a'>([{html.escape(str(x.get('bucket') or '-'))}] {html.escape(str(x.get('channel') or '-'))}, readiness={html.escape(str(x.get('readiness') or '-'))})</span>"
            f"<div style='font-size:12px;color:#44546b'>copy: {html.escape(str(x.get('copy') or '-'))}</div></li>"
            for x in campaign_items
        )
        if not campaign_html:
            campaign_html = "<li>暂无 launchable campaign（可继续 SEO/content 或走 Sales fallback）</li>"

        capability_html = "".join(
            f"<span style='display:inline-block;border:1px solid #d1d8e2;border-radius:999px;padding:4px 10px;margin:4px;'>"
            f"{html.escape(str(c.get('label') or '-'))}: <b style='color:{_cap_color(str(c.get('status')))}'>{html.escape(str(c.get('status') or '-'))}</b></span>"
            for c in caps
        )
        if not capability_html:
            capability_html = "<span style='color:#60708a'>能力快照暂不可用</span>"

        snippet = f"""
<!-- STUDIO_GTM_SYNC_START -->
<section id=\"studio-gtm-sync\" style=\"margin:20px auto;max-width:980px;border:1px solid #d0d7e2;border-radius:12px;padding:16px;background:#f7f9fc;color:#1f2a37;\">
  <h2 style=\"margin:0 0 10px;font-size:20px;\">AI Founder Live Sync Panel</h2>
  <p style=\"margin:0 0 8px;\"><strong>Value proposition:</strong> {html.escape(value or '-')}</p>
  <p style=\"margin:0 0 8px;\"><strong>Ad copy:</strong> {html.escape(ad_copy or '-')}</p>
  <p style=\"margin:0 0 8px;\"><strong>Sales opening:</strong> {html.escape(sales_opening or '-')}</p>
  <p style=\"margin:0 0 8px;\"><strong>Proof:</strong> {html.escape(proof or '-')}</p>
  <p style=\"margin:0 0 8px;\"><strong>CTA:</strong> {html.escape(cta or '-')}</p>

  <div style=\"display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 14px;\">
    {f'<a href="{html.escape(str(links.get("search")))}" target="_blank" rel="noreferrer">Search UTM</a>' if links.get('search') else ''}
    {f'<a href="{html.escape(str(links.get("linkedin")))}" target="_blank" rel="noreferrer">LinkedIn UTM</a>' if links.get('linkedin') else ''}
    {f'<a href="{html.escape(str(links.get("x")))}" target="_blank" rel="noreferrer">X UTM</a>' if links.get('x') else ''}
    {f'<a href="{html.escape(str(links.get("sales_email")))}" target="_blank" rel="noreferrer">Sales Email UTM</a>' if links.get('sales_email') else ''}
  </div>

  <div style=\"display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;\">
    <div style=\"border:1px solid #d7deea;border-radius:10px;padding:10px;background:#fff\">
      <h3 style=\"margin:0 0 8px;font-size:16px;\">Publish content（实时）</h3>
      <ul style=\"margin:0;padding-left:18px\">{content_html}</ul>
    </div>
    <div style=\"border:1px solid #d7deea;border-radius:10px;padding:10px;background:#fff\">
      <h3 style=\"margin:0 0 8px;font-size:16px;\">Launch campaigns（实时）</h3>
      <ul style=\"margin:0;padding-left:18px\">{campaign_html}</ul>
    </div>
  </div>

  <div style=\"display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:12px;\">
    <div style=\"border:1px solid #d7deea;border-radius:10px;padding:10px;background:#fff\">
      <h3 style=\"margin:0 0 8px;font-size:16px;\">Sales pulse</h3>
      <p style=\"margin:4px 0\"><strong>Segment:</strong> {html.escape(str(segment_name or '-'))}</p>
      <p style=\"margin:4px 0\"><strong>Weekly leads/MQL:</strong> {html.escape(str(weekly_leads))} / {html.escape(str(weekly_mql))}</p>
      <p style=\"margin:4px 0\"><strong>Dispatch processed:</strong> {html.escape(str(dispatch_summary.get('processed')))}</p>
      <p style=\"margin:4px 0\"><strong>New customers:</strong> {html.escape(str(conversion_summary.get('new_customers_converted')))} | <strong>MRR proxy:</strong> {html.escape(str(conversion_summary.get('new_business_mrr_proxy')))}</p>
    </div>
    <div style=\"border:1px solid #d7deea;border-radius:10px;padding:10px;background:#fff\">
      <h3 style=\"margin:0 0 8px;font-size:16px;\">Operations pulse</h3>
      <p style=\"margin:4px 0\"><strong>Sessions:</strong> {html.escape(str(((ops1_sum.get('traffic') or {}).get('sessions'))))}</p>
      <p style=\"margin:4px 0\"><strong>Qualified signups:</strong> {html.escape(str(((ops1_sum.get('signups') or {}).get('qualified_signups'))))}</p>
      <p style=\"margin:4px 0\"><strong>Net new MRR:</strong> {html.escape(str(((ops1_sum.get('revenue') or {}).get('net_new_mrr'))))}</p>
      <p style=\"margin:4px 0\"><strong>Feedback items:</strong> {html.escape(str(((ops2_sum.get('feedback') or {}).get('feedback_items_total'))))} | <strong>Themes:</strong> {html.escape(str(((ops2_sum.get('feedback') or {}).get('themes_total'))))}</p>
      <p style=\"margin:4px 0\"><strong>Experiments planned:</strong> {html.escape(str(((ops3_sum.get('flow') or {}).get('experiments_planned'))))}</p>
    </div>
  </div>

  <div style=\"margin-top:12px;border:1px solid #d7deea;border-radius:10px;padding:10px;background:#fff\">
    <h3 style=\"margin:0 0 8px;font-size:16px;\">12 Capability proof wall</h3>
    <div>{capability_html}</div>
  </div>

  <p style=\"margin-top:10px;font-size:12px;color:#5b6472;\">Auto-synced by Studio from Product + Marketing + Sales + Operations artifacts.</p>
</section>
<!-- STUDIO_GTM_SYNC_END -->
""".strip()

        html_text = index_path.read_text(encoding="utf-8", errors="ignore")
        pattern = r"<!-- STUDIO_GTM_SYNC_START -->.*?<!-- STUDIO_GTM_SYNC_END -->"
        if re.search(pattern, html_text, flags=re.S):
            updated = re.sub(pattern, snippet, html_text, flags=re.S)
        elif "</main>" in html_text:
            updated = html_text.replace("</main>", snippet + "\n</main>")
        elif "</body>" in html_text:
            updated = html_text.replace("</body>", snippet + "\n</body>")
        else:
            updated = html_text + "\n" + snippet

        index_path.write_text(updated, encoding="utf-8")
        return {
            "ok": True,
            "indexPath": str(index_path),
            "contentItems": len(content_items),
            "campaignItems": len(campaign_items),
            "capabilityCount": len(caps),
        }

    def _build_message_pack(self, opp_id: Optional[str]) -> Dict[str, Any]:
        landing = self._parse_json(self.product_dir / "research/landing_v1/landing_package.json", {})
        content_queue = self._parse_json(self.marketing_dir / "research/stage2_content_publish/publish.queue.latest.json", {})
        campaign_queue = self._parse_json(self.marketing_dir / "research/stage3_campaign_launch/campaigns.queue.latest.json", {})
        outreach = self._parse_json(self.sales_dir / "research/outreach/outreach_batch.ready.json", {})

        landing_headline = deep_find_first_value(landing, ["headline", "hero_headline", "title", "value_proposition"]) or ""
        landing_cta = deep_find_first_value(landing, ["cta", "primary_cta", "button_text", "call_to_action"]) or ""
        proof_point = deep_find_first_value(landing, ["social_proof", "proof", "credibility", "metric", "result"]) or ""

        top_content = None
        top_content_bucket = None
        for bucket in ["approved", "review_ready", "needs_revision", "blocked"]:
            for item in ((content_queue.get("queue") or {}).get(bucket) or []):
                if item_matches_opp(item, opp_id):
                    top_content = item
                    top_content_bucket = bucket
                    break
            if top_content:
                break

        top_campaign = None
        top_campaign_bucket = None
        for bucket in ["launch_ready", "watchlist", "hold"]:
            for item in ((campaign_queue.get("queue") or {}).get(bucket) or []):
                if item_matches_opp(item, opp_id):
                    top_campaign = item
                    top_campaign_bucket = bucket
                    break
            if top_campaign:
                break

        first_message = None
        for msg in outreach.get("messages") or []:
            if isinstance(msg, dict):
                first_message = msg
                break

        ad_copy = None
        if isinstance(top_campaign, dict):
            ad_copy = (
                top_campaign.get("ad_copy")
                or top_campaign.get("copy")
                or top_campaign.get("hook")
                or top_campaign.get("title")
                or top_campaign.get("name")
            )
        if not ad_copy and isinstance(top_content, dict):
            ad_copy = top_content.get("summary") or top_content.get("angle")

        sales_opening = None
        if isinstance(first_message, dict):
            sales_opening = first_message.get("body") or first_message.get("opening_line")

        base_url = self._find_landing_url(landing)
        campaign_slug = slugify(str(opp_id or "venture-campaign"), 48)
        utm_links = {
            "search": self._with_utm(base_url, source="google", medium="cpc", campaign=campaign_slug, content="judge-search-ad"),
            "linkedin": self._with_utm(base_url, source="linkedin", medium="paid_social", campaign=campaign_slug, content="judge-linkedin-ad"),
            "x": self._with_utm(base_url, source="x", medium="paid_social", campaign=campaign_slug, content="judge-x-ad"),
            "sales_email": self._with_utm(base_url, source="sales", medium="email", campaign=campaign_slug, content="judge-outreach"),
        }

        alignment = {
            "landingVsAd": bool(landing_headline and ad_copy),
            "adVsSales": bool(ad_copy and sales_opening),
            "landingVsSales": bool(landing_headline and sales_opening),
        }

        return {
            "opportunityId": opp_id,
            "messagePack": {
                "valueProposition": landing_headline or None,
                "primaryCta": landing_cta or None,
                "proofPoint": proof_point or None,
            },
            "content": {
                "contentId": (top_content or {}).get("content_id") if isinstance(top_content, dict) else None,
                "bucket": top_content_bucket,
                "snippet": (
                    (top_content or {}).get("summary")
                    or (top_content or {}).get("selected_title")
                    or (top_content or {}).get("title")
                )
                if isinstance(top_content, dict)
                else None,
            },
            "campaign": {
                "campaignId": (top_campaign or {}).get("campaign_id") if isinstance(top_campaign, dict) else None,
                "bucket": top_campaign_bucket,
                "adCopy": ad_copy,
            },
            "sales": {
                "messageId": (first_message or {}).get("id") if isinstance(first_message, dict) else None,
                "opening": sales_opening,
            },
            "utmLinks": utm_links,
            "alignment": alignment,
        }

    def _build_go_to_market_preview(self, opp_id: Optional[str]) -> Dict[str, Any]:
        payload = self._build_message_pack(opp_id)
        pack = payload.get("messagePack") or {}
        campaign = payload.get("campaign") or {}
        content = payload.get("content") or {}
        sales = payload.get("sales") or {}
        return {
            "landingHeadline": pack.get("valueProposition"),
            "landingCta": pack.get("primaryCta"),
            "adPreview": campaign.get("adCopy") or content.get("snippet"),
            "campaignId": campaign.get("campaignId"),
            "contentId": content.get("contentId"),
            "salesOpening": sales.get("opening"),
            "messageMatch": payload.get("alignment") or {},
            "utmLinks": payload.get("utmLinks") or {},
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _action_refresh_ideas(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mode = str(payload.get("mode") or "deterministic").strip().lower()
        if mode not in {"deterministic", "explore"}:
            raise StudioError("refresh_ideas mode must be deterministic or explore")

        step = self._command_step(
            "run_generate_startup_ideas",
            ["bash", "scripts/run_generate_startup_ideas.sh"],
            cwd=self.product_dir,
            timeout=1800,
        )
        status = "passed" if step["status"] == "passed" else "failed"

        artifacts = self._copy_artifacts(
            venture_id="global",
            stage="IDEA_POOL",
            run_id=f"ideas_{now_dt().strftime('%Y%m%d%H%M%S')}",
            paths=list(self._ideas_paths()),
        )

        if status == "passed":
            with self.store_lock:
                state = self._load_state()
                if mode == "explore":
                    state["ideaNonce"] = int(state.get("ideaNonce", 0) or 0) + 1
                else:
                    state["ideaNonce"] = 0
                self._save_state(state)

        run = self._record_run(
            venture_id=None,
            stage="IDEA_POOL",
            action="refresh_ideas",
            mode="simulation",
            status=status,
            steps=[step],
            artifacts=artifacts,
            summary={"ideasCount": len(self.list_ideas()), "mode": mode},
            error=step["stderrTail"][-500:] if status == "failed" else None,
        )
        if status != "passed":
            raise StudioError(f"refresh ideas failed: {step['stderrTail'][:300]}")
        return {"run": run, "ideas": self.list_ideas()}

    def _action_create_venture(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        opp_id = payload.get("opportunityId")
        name = payload.get("name")
        venture = self.create_venture(opportunity_id=str(opp_id), name=name)
        return {"venture": venture}

    def _action_set_active_venture(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")
        venture = self.set_active_venture(venture_id)
        return {"venture": venture}

    def _action_reset_demo_state(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        keep_ideas = bool(payload.get("keepIdeas", True))

        with self.store_lock:
            self._write_json(
                self.state_path,
                {
                    "activeVentureId": None,
                    "ideaNonce": 0,
                    "updatedAt": now_iso(),
                },
            )
            self._write_json(self.ventures_path, {"items": []})
            self._write_json(self.runs_path, {"items": []})
            self._write_json(self.gates_path, {"items": []})
            self._write_json(self.loop_todos_path, {"items": []})
            self._write_json(self.deployments_path, {"items": []})

        for folder in [self.artifacts_dir, self.contexts_dir, self.rehearsals_dir]:
            if folder.exists():
                shutil.rmtree(folder, ignore_errors=True)
            folder.mkdir(parents=True, exist_ok=True)

        if not keep_ideas:
            # optional hard reset of idea artifacts generated by Product
            for p in self._ideas_paths():
                try:
                    if p.exists() and p.is_file():
                        p.unlink()
                except Exception:
                    pass

        return {"ok": True, "message": "studio demo state reset", "keepIdeas": keep_ideas}

    def _action_run_product(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

        venture = self._require_venture(venture_id)
        current_stage = str(venture.get("stage") or "IDEA_POOL")
        if current_stage not in {"SELECTED", "PRODUCT"}:
            raise StudioError(f"run_product requires SELECTED/PRODUCT stage, current={current_stage}")

        mode = str(payload.get("mode") or "simulation").strip().lower()
        if mode not in {"simulation", "live"}:
            raise StudioError("mode must be simulation or live")

        confirm_live = bool(payload.get("confirmLive", False))
        dry_run = bool(payload.get("dryRun", False))
        deploy_target = str(payload.get("deployTarget") or "preview").strip().lower()
        if deploy_target not in {"preview", "production"}:
            raise StudioError("deployTarget must be preview or production")

        page_profile = str(payload.get("pageProfile") or "").strip() or None

        venture = self._require_venture(venture_id)
        opp_id = venture.get("opportunityId")
        if not opp_id:
            raise StudioError("venture opportunityId missing")

        vercel_project = self._vercel_project_name_for_venture(venture)
        commit_sha = self._git_commit_sha()

        steps: List[Dict[str, Any]] = []

        landing_cmd = ["bash", "scripts/run_create_landing_pages_v1.sh", "--opp-id", str(opp_id)]
        if page_profile:
            landing_cmd.extend(["--page-profile", page_profile])

        step_landing = self._command_step(
            "create_landing_pages",
            landing_cmd,
            cwd=self.product_dir,
            timeout=1800,
        )
        steps.append(step_landing)
        if step_landing["status"] != "passed":
            self._record_run(
                venture_id=venture_id,
                stage="PRODUCT",
                action="run_product",
                mode=mode,
                status="failed",
                steps=steps,
                artifacts=[],
                summary={"vercelProject": vercel_project, "deployTarget": deploy_target},
                error=step_landing["stderrTail"][-500:],
            )
            raise StudioError(f"Product landing step failed: {step_landing['stderrTail'][:300]}")

        deployment_url = None
        preview_path = None

        if mode == "live":
            if not confirm_live:
                raise StudioError("live mode requires confirmLive=true")

            # Safety policy:
            # - preview deployments are allowed with explicit confirmLive (judge rehearsal convenience)
            # - production deployments still require manual arm + explicit production confirmation
            if deploy_target == "production":
                if not self._manual_arm_enabled():
                    raise StudioError("manual arm is OFF; cannot run production deployment")
                if not bool(payload.get("confirmProduction", False)):
                    raise StudioError("production deployment requires confirmProduction=true")

            vercel = self._vercel_status()
            if not (vercel.get("installed") and vercel.get("authenticated")):
                raise StudioError("Vercel not ready (install/login required)")

            if dry_run:
                summary = {
                    "opportunityId": opp_id,
                    "deploymentUrl": None,
                    "previewPath": None,
                    "vercelProject": vercel_project,
                    "deployTarget": deploy_target,
                    "dryRun": True,
                    "pageProfile": page_profile,
                    "message": "Live deployment preflight passed; dry-run skipped deploy.",
                }
                run = self._record_run(
                    venture_id=venture_id,
                    stage="PRODUCT",
                    action="run_product",
                    mode=mode,
                    status="passed",
                    steps=steps,
                    artifacts=[],
                    summary=summary,
                )
                updated = self._update_venture(
                    venture_id,
                    lambda v: {
                        **v,
                        "links": {
                            **(v.get("links") or {}),
                            "vercelProject": vercel_project,
                        },
                        "lastActions": {
                            **(v.get("lastActions") or {}),
                            "product": {
                                "runId": run["id"],
                                "at": now_iso(),
                                "mode": mode,
                                "dryRun": True,
                                "deployTarget": deploy_target,
                            },
                        },
                    },
                )
                updated = self._propose_stage_transition(
                    venture_id=venture_id,
                    to_stage="MARKETING",
                    reason="product_dryrun_preflight_completed",
                    source_action="run_product",
                    summary={
                        "runId": run["id"],
                        "mode": mode,
                        "dryRun": True,
                        "deployTarget": deploy_target,
                    },
                )
                self._sync_venture_context(venture_id)
                return {"run": run, "venture": updated, "pendingTransition": updated.get("pendingTransition")}

            build_cmd = [
                "bash",
                "scripts/run_build_deploy_v1.sh",
                "--opp-id",
                str(opp_id),
                "--allow-spec-autogen",
                "--vercel-project",
                vercel_project,
                "--deploy-target",
                deploy_target,
            ]
            if page_profile:
                build_cmd.extend(["--page-profile", page_profile])

            step_build = self._command_step(
                "build_and_deploy",
                build_cmd,
                cwd=self.product_dir,
                timeout=3600,
            )
            steps.append(step_build)
            if step_build["status"] != "passed":
                self._record_run(
                    venture_id=venture_id,
                    stage="PRODUCT",
                    action="run_product",
                    mode=mode,
                    status="failed",
                    steps=steps,
                    artifacts=[],
                    summary={"vercelProject": vercel_project, "deployTarget": deploy_target},
                    error=step_build["stderrTail"][-500:],
                )
                raise StudioError(f"Product build/deploy failed: {step_build['stderrTail'][:300]}")

            product_run = self._parse_json(self.product_dir / "research/stage2_web_product/run.latest.json", {})
            deployment_url = ((product_run.get("output") or {}).get("deployed_url"))
        else:
            # Simulation mode: build local preview without external deployment.
            landing_run = self._parse_json(self.product_dir / "research/stage3_landing_launch/run.latest.json", {})
            project_spec = ((landing_run.get("artifacts") or {}).get("project_spec"))
            if project_spec:
                preview_dir = self.product_dir / "research/build_deploy_v1/apps" / f"{venture_id}_preview"
                summary_out = self.product_dir / "research/build_deploy_v1" / f"scaffold_summary.{venture_id}.json"
                step_preview = self._command_step(
                    "scaffold_preview",
                    [
                        "python3",
                        "scripts/scaffold_web_product.py",
                        "--project-spec",
                        str(project_spec),
                        "--out-dir",
                        str(preview_dir),
                        "--summary-out",
                        str(summary_out),
                        "--force",
                    ],
                    cwd=self.product_dir,
                    timeout=1800,
                )
                steps.append(step_preview)
                if step_preview["status"] == "passed":
                    preview_path = str(preview_dir)

        artifact_paths = [
            self.product_dir / "research/stage3_landing_launch/run.latest.json",
            self.product_dir / "research/stage2_web_product/run.latest.json",
            self.product_dir / "research/landing_v1/landing_package.json",
            self.repo_root / "handoffs/product_to_marketing.json",
            self.product_dir / "research/build_deploy_v1/deploy_latest.json",
        ]
        if preview_path:
            preview_index = Path(preview_path) / "index.html"
            if preview_index.exists():
                artifact_paths.append(preview_index)

        run_id = f"product_{now_dt().strftime('%Y%m%d%H%M%S')}"
        artifacts = self._copy_artifacts(
            venture_id=venture_id,
            stage="PRODUCT",
            run_id=run_id,
            paths=artifact_paths,
        )

        landing_preview_path = self._ensure_landing_preview_html(venture)
        sync_result = self._sync_preview_with_gtm(venture, preview_path=preview_path)

        summary = {
            "opportunityId": opp_id,
            "deploymentUrl": deployment_url,
            "previewPath": preview_path,
            "landingPreviewPath": landing_preview_path,
            "vercelProject": vercel_project,
            "deployTarget": deploy_target,
            "dryRun": dry_run,
            "commit": commit_sha,
            "pageProfile": page_profile,
            "previewSync": sync_result,
        }
        summary["agentRelay"] = self._relay_stage_agents(
            payload=payload,
            venture=venture,
            stage="PRODUCT",
            action="run_product",
            owner_agent="op1_product",
            notify_agents=["op1_marketing"],
            handoff_paths=[self.repo_root / "handoffs/product_to_marketing.json"],
            stage_summary={
                "mode": mode,
                "deployTarget": deploy_target,
                "hasDeploymentUrl": bool(deployment_url),
                "hasPreview": bool(preview_path),
            },
        )

        run = self._record_run(
            venture_id=venture_id,
            stage="PRODUCT",
            action="run_product",
            mode=mode,
            status="passed",
            steps=steps,
            artifacts=artifacts,
            summary=summary,
        )

        self._append_deployment_record(
            {
                "id": f"dep_{uuid.uuid4().hex[:10]}",
                "ventureId": venture_id,
                "opportunityId": opp_id,
                "mode": mode,
                "project": vercel_project,
                "env": "production" if deploy_target == "production" else "preview",
                "url": deployment_url,
                "previewPath": preview_path,
                "commit": commit_sha,
                "runId": run["id"],
                "createdAt": now_iso(),
                "runHint": "run_build_deploy_v1.sh" if mode == "live" else "scaffold_web_product.py",
            }
        )

        updated = self._update_venture(
            venture_id,
            lambda v: {
                **v,
                "links": {
                    **(v.get("links") or {}),
                    "productDeploymentUrl": deployment_url,
                    "productPreviewPath": preview_path,
                    "landingPreviewPath": landing_preview_path,
                    "vercelProject": vercel_project,
                    "vercelEnv": "production" if deploy_target == "production" else "preview",
                },
                "lastActions": {
                    **(v.get("lastActions") or {}),
                    "product": {
                        "runId": run["id"],
                        "at": now_iso(),
                        "mode": mode,
                        "dryRun": dry_run,
                        "deployTarget": deploy_target,
                        "pageProfile": page_profile,
                    },
                },
            },
        )

        updated = self._propose_stage_transition(
            venture_id=venture_id,
            to_stage="MARKETING",
            reason="product_run_completed",
            source_action="run_product",
            summary={
                "runId": run["id"],
                "mode": mode,
                "deployTarget": deploy_target,
                "hasDeploymentUrl": bool(deployment_url),
            },
        )

        self._sync_venture_context(venture_id)
        return {"run": run, "venture": updated, "pendingTransition": updated.get("pendingTransition")}

    def _action_run_marketing_seo(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

        venture = self._require_venture(venture_id)
        self._require_stage(venture, "MARKETING", "run_marketing_seo")

        mode = str(payload.get("mode") or "shadow").strip().lower()
        if mode not in {"shadow", "live"}:
            raise StudioError("marketing seo mode must be shadow or live")

        step = self._command_step(
            "marketing_stage1_seo",
            ["python3", "scripts/run_marketing_seo_stage1.py", "--mode", mode, "--print-summary", "--force"],
            cwd=self.marketing_dir,
            timeout=1800,
        )

        if step["status"] != "passed":
            run = self._record_run(
                venture_id=venture_id,
                stage="MARKETING",
                action="run_marketing_seo",
                mode=mode,
                status="failed",
                steps=[step],
                artifacts=[],
                summary={},
                error=step["stderrTail"][-500:],
            )
            raise StudioError(f"Marketing SEO failed: {step['stderrTail'][:300]}")

        artifacts = self._copy_artifacts(
            venture_id=venture_id,
            stage="MARKETING",
            run_id=f"marketing_seo_{now_dt().strftime('%Y%m%d%H%M%S')}",
            paths=[
                self.marketing_dir / "research/stage1_marketing_seo/run.latest.json",
                self.marketing_dir / "research/stage1_marketing_seo/experiments.queue.latest.json",
                self.marketing_dir / "research/stage1_marketing_seo/scoreboard.latest.json",
            ],
        )

        run = self._record_run(
            venture_id=venture_id,
            stage="MARKETING",
            action="run_marketing_seo",
            mode=mode,
            status="passed",
            steps=[step],
            artifacts=artifacts,
            summary={},
        )

        updated = self._update_venture(
            venture_id,
            lambda v: {
                **v,
                "stage": "MARKETING",
                "lastActions": {
                    **(v.get("lastActions") or {}),
                    "marketingSeo": {"runId": run["id"], "at": now_iso(), "mode": mode},
                },
            },
        )
        self._sync_venture_context(venture_id)
        return {"run": run, "venture": updated}

    def _action_run_marketing_content(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

        venture = self._require_venture(venture_id)
        self._require_stage(venture, "MARKETING", "run_marketing_content")

        mode = str(payload.get("mode") or "shadow").strip().lower()
        if mode not in {"shadow", "review"}:
            raise StudioError("marketing content mode must be shadow or review")

        opportunity_id = canonical_opp_id(venture.get("opportunityId"))
        cmd = ["python3", "scripts/run_marketing_content_stage2.py", "--mode", mode, "--force", "--print-summary"]
        if opportunity_id:
            cmd.extend(["--opportunity-id", opportunity_id])

        step = self._command_step(
            "marketing_stage2_content",
            cmd,
            cwd=self.marketing_dir,
            timeout=1800,
        )

        if step["status"] != "passed":
            self._record_run(
                venture_id=venture_id,
                stage="MARKETING",
                action="run_marketing_content",
                mode=mode,
                status="failed",
                steps=[step],
                artifacts=[],
                summary={},
                error=step["stderrTail"][-500:],
            )
            raise StudioError(f"Marketing content failed: {step['stderrTail'][:300]}")

        artifacts = self._copy_artifacts(
            venture_id=venture_id,
            stage="MARKETING",
            run_id=f"marketing_content_{now_dt().strftime('%Y%m%d%H%M%S')}",
            paths=[
                self.marketing_dir / "research/stage2_content_publish/run.latest.json",
                self.marketing_dir / "research/stage2_content_publish/publish.queue.latest.json",
                self.marketing_dir / "research/stage2_content_publish/content.backlog.latest.json",
                self.repo_root / "handoffs/marketing_to_sales.json",
            ],
        )

        run = self._record_run(
            venture_id=venture_id,
            stage="MARKETING",
            action="run_marketing_content",
            mode=mode,
            status="passed",
            steps=[step],
            artifacts=artifacts,
            summary={},
        )

        updated = self._update_venture(
            venture_id,
            lambda v: {
                **v,
                "stage": "MARKETING",
                "lastActions": {
                    **(v.get("lastActions") or {}),
                    "marketingContent": {"runId": run["id"], "at": now_iso(), "mode": mode},
                },
            },
        )
        preview_sync = self._sync_preview_with_gtm(updated)
        self._sync_venture_context(venture_id)
        return {"run": run, "venture": updated, "previewSync": preview_sync}

    def _action_review_marketing_content(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

        venture = self._require_venture(venture_id)
        self._require_stage(venture, "MARKETING", "review_marketing_content")

        approve_ids = [str(x).strip() for x in (payload.get("approveIds") or []) if str(x).strip()]
        reject_ids = [str(x).strip() for x in (payload.get("rejectIds") or []) if str(x).strip()]
        note = str(payload.get("note") or "studio_review")
        reason = str(payload.get("reason") or "manual_review_requested_changes")
        auto_generate_campaign = bool(payload.get("autoGenerateCampaign", True))

        if not approve_ids and not reject_ids:
            raise StudioError("provide approveIds or rejectIds")

        cmd = ["python3", "scripts/review_marketing_content_stage2.py", "--print-summary", "--note", note, "--reason", reason]
        for cid in approve_ids:
            cmd.extend(["--approve", cid])
        for cid in reject_ids:
            cmd.extend(["--reject", cid])

        step = self._command_step("marketing_stage2_review", cmd, cwd=self.marketing_dir, timeout=1200)
        steps = [step]
        if step["status"] != "passed":
            self._record_run(
                venture_id=venture_id,
                stage="MARKETING",
                action="review_marketing_content",
                mode="review",
                status="failed",
                steps=steps,
                artifacts=[],
                summary={},
                error=step["stderrTail"][-500:],
            )
            raise StudioError(f"Marketing content review failed: {step['stderrTail'][:300]}")

        campaign_autogen: Dict[str, Any] = {
            "enabled": bool(auto_generate_campaign and approve_ids),
            "status": "skipped",
            "mode": "review",
        }
        if auto_generate_campaign and approve_ids:
            opportunity_id = canonical_opp_id(venture.get("opportunityId"))
            campaign_cmd = [
                "python3",
                "scripts/run_marketing_campaign_stage3.py",
                "--mode",
                "review",
                "--force",
                "--include-review-ready",
                "--print-summary",
            ]
            if opportunity_id:
                campaign_cmd.extend(["--opportunity-id", opportunity_id])

            campaign_step = self._command_step(
                "marketing_stage3_campaign_after_review",
                campaign_cmd,
                cwd=self.marketing_dir,
                timeout=1800,
            )
            steps.append(campaign_step)
            campaign_autogen["status"] = campaign_step.get("status")
            if campaign_step.get("status") == "passed":
                queue = self._parse_json(self.marketing_dir / "research/stage3_campaign_launch/campaigns.queue.latest.json", {})
                counts = queue.get("counts") or {}
                campaign_autogen["stage3Status"] = queue.get("status")
                campaign_autogen["counts"] = {
                    "launch_ready": int(counts.get("launch_ready", 0) or 0),
                    "watchlist": int(counts.get("watchlist", 0) or 0),
                    "hold": int(counts.get("hold", 0) or 0),
                }
            else:
                campaign_autogen["error"] = str(campaign_step.get("stderrTail") or "")[-400:]

        artifact_paths = [
            self.marketing_dir / "research/stage2_content_publish/review_log.latest.json",
            self.marketing_dir / "research/stage2_content_publish/publish.queue.latest.json",
            self.repo_root / "handoffs/marketing_to_sales.json",
        ]
        if campaign_autogen.get("enabled"):
            artifact_paths.extend(
                [
                    self.marketing_dir / "research/stage3_campaign_launch/run.latest.json",
                    self.marketing_dir / "research/stage3_campaign_launch/campaigns.queue.latest.json",
                ]
            )

        artifacts = self._copy_artifacts(
            venture_id=venture_id,
            stage="MARKETING",
            run_id=f"marketing_review_{now_dt().strftime('%Y%m%d%H%M%S')}",
            paths=artifact_paths,
        )

        run = self._record_run(
            venture_id=venture_id,
            stage="MARKETING",
            action="review_marketing_content",
            mode="review",
            status="passed",
            steps=steps,
            artifacts=artifacts,
            summary={
                "approved": approve_ids,
                "rejected": reject_ids,
                "campaignAutogen": campaign_autogen,
            },
        )

        updated = self._update_venture(
            venture_id,
            lambda v: {
                **v,
                "selections": {
                    **(v.get("selections") or {}),
                    "contentApprovedIds": approve_ids,
                    "contentRejectedIds": reject_ids,
                },
                "lastActions": {
                    **(v.get("lastActions") or {}),
                    "marketingReview": {"runId": run["id"], "at": now_iso()},
                    **(
                        {
                            "marketingCampaignAutogen": {
                                "runId": run["id"],
                                "at": now_iso(),
                                "status": campaign_autogen.get("status"),
                                "counts": campaign_autogen.get("counts"),
                            }
                        }
                        if campaign_autogen.get("enabled")
                        else {}
                    ),
                },
            },
        )

        preview_sync = self._sync_preview_with_gtm(updated)
        self._sync_venture_context(venture_id)
        return {
            "run": run,
            "venture": updated,
            "previewSync": preview_sync,
            "campaignAutogen": campaign_autogen,
        }

    def _action_run_marketing_campaign(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

        venture = self._require_venture(venture_id)
        self._require_stage(venture, "MARKETING", "run_marketing_campaign")

        mode = str(payload.get("mode") or "shadow").strip().lower()
        if mode not in {"shadow", "review"}:
            raise StudioError("marketing campaign mode must be shadow or review")

        opportunity_id = canonical_opp_id(venture.get("opportunityId"))
        cmd = ["python3", "scripts/run_marketing_campaign_stage3.py", "--mode", mode, "--force", "--print-summary"]
        if mode == "review":
            cmd.append("--include-review-ready")
        if opportunity_id:
            cmd.extend(["--opportunity-id", opportunity_id])

        step = self._command_step(
            "marketing_stage3_campaign",
            cmd,
            cwd=self.marketing_dir,
            timeout=1800,
        )
        if step["status"] != "passed":
            self._record_run(
                venture_id=venture_id,
                stage="MARKETING",
                action="run_marketing_campaign",
                mode=mode,
                status="failed",
                steps=[step],
                artifacts=[],
                summary={},
                error=step["stderrTail"][-500:],
            )
            raise StudioError(f"Marketing campaign failed: {step['stderrTail'][:300]}")

        artifacts = self._copy_artifacts(
            venture_id=venture_id,
            stage="MARKETING",
            run_id=f"marketing_campaign_{now_dt().strftime('%Y%m%d%H%M%S')}",
            paths=[
                self.marketing_dir / "research/stage3_campaign_launch/run.latest.json",
                self.marketing_dir / "research/stage3_campaign_launch/campaigns.queue.latest.json",
                self.repo_root / "handoffs/marketing_to_sales.json",
            ],
        )

        queue = self._parse_json(self.marketing_dir / "research/stage3_campaign_launch/campaigns.queue.latest.json", {})
        counts = queue.get("counts") or {}
        launch_ready = int(counts.get("launch_ready", 0) or 0)
        watchlist = int(counts.get("watchlist", 0) or 0)
        hold = int(counts.get("hold", 0) or 0)
        total_campaigns = launch_ready + watchlist + hold
        stage3_status = queue.get("status")

        fallback_to_sales = total_campaigns == 0
        summary = {
            "stage3Status": stage3_status,
            "campaignCounts": {"launch_ready": launch_ready, "watchlist": watchlist, "hold": hold},
            "fallbackToSales": fallback_to_sales,
            "needsUserDecision": True,
        }
        summary["agentRelay"] = self._relay_stage_agents(
            payload=payload,
            venture=venture,
            stage="MARKETING",
            action="run_marketing_campaign",
            owner_agent="op1_marketing",
            notify_agents=["op1_sales"],
            handoff_paths=[self.repo_root / "handoffs/marketing_to_sales.json"],
            stage_summary={
                "mode": mode,
                "campaignCounts": summary.get("campaignCounts"),
                "fallbackToSales": fallback_to_sales,
            },
        )

        run = self._record_run(
            venture_id=venture_id,
            stage="MARKETING",
            action="run_marketing_campaign",
            mode=mode,
            status="passed",
            steps=[step],
            artifacts=artifacts,
            summary=summary,
        )

        updated = self._update_venture(
            venture_id,
            lambda v: {
                **v,
                "lastActions": {
                    **(v.get("lastActions") or {}),
                    "marketingCampaign": {
                        "runId": run["id"],
                        "at": now_iso(),
                        "mode": mode,
                        "stage3Status": stage3_status,
                        "fallbackToSales": fallback_to_sales,
                    },
                },
                "notes": [
                    *([x for x in (v.get("notes") or []) if isinstance(x, str)][-5:]),
                    "marketing_stage3_no_launchable_assets_requires_user_decision"
                    if fallback_to_sales
                    else "marketing_stage3_candidates_ready_select_campaign",
                ],
            },
        )
        if fallback_to_sales:
            updated = self._propose_stage_transition(
                venture_id=venture_id,
                to_stage="SALES",
                reason="marketing_no_launchable_campaign_assets",
                source_action="run_marketing_campaign",
                summary={"stage3Status": stage3_status, "campaignCounts": summary.get("campaignCounts")},
            )

        preview_sync = self._sync_preview_with_gtm(updated)
        self._sync_venture_context(venture_id)
        return {
            "run": run,
            "venture": updated,
            "previewSync": preview_sync,
            "blockedReason": "no_campaign_candidates" if fallback_to_sales else None,
            "pendingTransition": updated.get("pendingTransition"),
        }

    def _action_select_marketing_campaign(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        campaign_id = str(payload.get("campaignId") or "").strip()
        if not venture_id or not campaign_id:
            raise StudioError("ventureId and campaignId are required")

        venture = self._require_venture(venture_id)
        current_stage = str(venture.get("stage") or "IDEA_POOL")
        if current_stage not in {"MARKETING", "SALES"}:
            pending = self._pending_transition(venture)
            if pending:
                from_stage = str(pending.get("fromStage") or current_stage)
                to_stage = str(pending.get("toStage") or "UNKNOWN")
                raise StudioError(
                    f"select_marketing_campaign requires stage=MARKETING/SALES, current={current_stage}. "
                    f"Current blocker: pending transition {from_stage}->{to_stage}. "
                    "Please confirm or reject that transition first."
                )
            raise StudioError(
                f"select_marketing_campaign requires stage=MARKETING/SALES, current={current_stage}. "
                "Current blocker: stage mismatch."
            )

        pending_before = self._pending_transition(venture)
        clear_pending_to_operations = bool(
            current_stage == "SALES"
            and isinstance(pending_before, dict)
            and str(pending_before.get("toStage") or "") == "OPERATIONS"
        )

        def _up(v: Dict[str, Any]) -> Dict[str, Any]:
            selections = {**(v.get("selections") or {})}
            selections["campaignId"] = campaign_id
            if current_stage == "SALES":
                selections["outreachBatchApproved"] = False

            notes = [x for x in (v.get("notes") or []) if isinstance(x, str)][-6:]
            if current_stage == "SALES":
                notes.append(f"campaign_updated_in_sales:{campaign_id}")
                if clear_pending_to_operations:
                    notes.append("sales_to_operations_transition_cleared_after_campaign_change")
            else:
                notes.append(f"campaign_selected_in_marketing:{campaign_id}")

            out = {
                **v,
                "selections": selections,
                "notes": notes,
                "lastActions": {
                    **(v.get("lastActions") or {}),
                    "campaignSelection": {
                        "campaignId": campaign_id,
                        "at": now_iso(),
                        "stage": current_stage,
                    },
                },
            }
            if clear_pending_to_operations:
                out.pop("pendingTransition", None)
            return out

        updated = self._update_venture(venture_id, _up)

        if current_stage == "MARKETING":
            updated = self._propose_stage_transition(
                venture_id=venture_id,
                to_stage="SALES",
                reason=f"marketing_campaign_selected:{campaign_id}",
                source_action="select_marketing_campaign",
                summary={"campaignId": campaign_id},
            )

        preview_sync = self._sync_preview_with_gtm(updated)
        self._sync_venture_context(venture_id)
        return {
            "venture": updated,
            "previewSync": preview_sync,
            "pendingTransition": updated.get("pendingTransition"),
            "campaignSelectionStage": current_stage,
            "clearedPendingTransition": clear_pending_to_operations,
        }

    def _find_segment_index_for_venture(self, opp_id: str) -> Optional[int]:
        queue = self._parse_json(self.sales_dir / "research/prospecting/prospect_queue.latest.json", {})
        segments = queue.get("segments") or []
        for idx, seg in enumerate(segments):
            if item_matches_opp(seg, opp_id):
                return idx
        return None

    def _action_run_sales_prospecting(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")
        venture = self._require_venture(venture_id)
        self._require_stage(venture, "SALES", "run_sales_prospecting")

        step = self._command_step(
            "sales_stage1_prospecting",
            ["python3", "scripts/build_prospect_queue.py"],
            cwd=self.sales_dir,
            timeout=1800,
        )
        if step["status"] != "passed":
            self._record_run(
                venture_id=venture_id,
                stage="SALES",
                action="run_sales_prospecting",
                mode="simulation",
                status="failed",
                steps=[step],
                artifacts=[],
                summary={},
                error=step["stderrTail"][-500:],
            )
            raise StudioError(f"Sales prospecting failed: {step['stderrTail'][:300]}")

        segment_index = self._find_segment_index_for_venture(venture.get("opportunityId"))

        artifacts = self._copy_artifacts(
            venture_id=venture_id,
            stage="SALES",
            run_id=f"sales_prospect_{now_dt().strftime('%Y%m%d%H%M%S')}",
            paths=[
                self.sales_dir / "research/prospecting/prospect_queue.latest.json",
                self.sales_dir / "research/prospecting/prospect_queue.latest.md",
                self.repo_root / "handoffs/sales_to_operations.json",
            ],
        )

        run = self._record_run(
            venture_id=venture_id,
            stage="SALES",
            action="run_sales_prospecting",
            mode="simulation",
            status="passed",
            steps=[step],
            artifacts=artifacts,
            summary={"segmentIndex": segment_index},
        )

        updated = self._update_venture(
            venture_id,
            lambda v: {
                **v,
                "stage": "SALES",
                "selections": {
                    **(v.get("selections") or {}),
                    "salesSegmentIndex": segment_index,
                },
                "lastActions": {
                    **(v.get("lastActions") or {}),
                    "salesProspecting": {"runId": run["id"], "at": now_iso()},
                },
            },
        )

        preview_sync = self._sync_preview_with_gtm(updated)
        self._sync_venture_context(venture_id)
        return {"run": run, "venture": updated, "previewSync": preview_sync}

    def _action_run_sales_outreach_plan(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")
        venture = self._require_venture(venture_id)
        self._require_stage(venture, "SALES", "run_sales_outreach_plan")

        seg_index = payload.get("segmentIndex")
        if seg_index is None:
            seg_index = (venture.get("selections") or {}).get("salesSegmentIndex")
        if seg_index is None:
            seg_index = self._find_segment_index_for_venture(venture.get("opportunityId"))
        if seg_index is None:
            raise StudioError("cannot determine segment index for venture; run prospecting first")

        step = self._command_step(
            "sales_stage2_outreach_plan",
            [
                "python3",
                "scripts/build_outreach_stage2.py",
                "--segment-index",
                str(seg_index),
                "--mode",
                "approval_required",
            ],
            cwd=self.sales_dir,
            timeout=1800,
        )
        if step["status"] != "passed":
            self._record_run(
                venture_id=venture_id,
                stage="SALES",
                action="run_sales_outreach_plan",
                mode="simulation",
                status="failed",
                steps=[step],
                artifacts=[],
                summary={"segmentIndex": seg_index},
                error=step["stderrTail"][-500:],
            )
            raise StudioError(f"Sales outreach plan failed: {step['stderrTail'][:300]}")

        artifacts = self._copy_artifacts(
            venture_id=venture_id,
            stage="SALES",
            run_id=f"sales_outreach_plan_{now_dt().strftime('%Y%m%d%H%M%S')}",
            paths=[
                self.sales_dir / "research/outreach/outreach_queue.latest.json",
                self.sales_dir / "research/outreach/outreach_batch.ready.json",
                self.sales_dir / "research/outreach/outreach_pack.latest.md",
            ],
        )

        run = self._record_run(
            venture_id=venture_id,
            stage="SALES",
            action="run_sales_outreach_plan",
            mode="simulation",
            status="passed",
            steps=[step],
            artifacts=artifacts,
            summary={"segmentIndex": seg_index},
        )

        updated = self._update_venture(
            venture_id,
            lambda v: {
                **v,
                "stage": "SALES",
                "selections": {
                    **(v.get("selections") or {}),
                    "salesSegmentIndex": seg_index,
                },
                "lastActions": {
                    **(v.get("lastActions") or {}),
                    "salesOutreachPlan": {"runId": run["id"], "at": now_iso()},
                },
            },
        )

        preview_sync = self._sync_preview_with_gtm(updated)
        self._sync_venture_context(venture_id)
        return {"run": run, "venture": updated, "previewSync": preview_sync}

    def _action_approve_sales_outreach(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

        venture = self._require_venture(venture_id)
        self._require_stage(venture, "SALES", "approve_sales_outreach")

        approver = str(payload.get("approver") or "studio_user")
        note = str(payload.get("note") or "approved in studio")

        step = self._command_step(
            "sales_stage2_outreach_approve",
            [
                "python3",
                "scripts/approve_outreach_batch_stage2.py",
                "--approver",
                approver,
                "--note",
                note,
            ],
            cwd=self.sales_dir,
            timeout=600,
        )

        if step["status"] != "passed":
            self._record_run(
                venture_id=venture_id,
                stage="SALES",
                action="approve_sales_outreach",
                mode="review",
                status="failed",
                steps=[step],
                artifacts=[],
                summary={},
                error=step["stderrTail"][-500:],
            )
            raise StudioError(f"Approve outreach failed: {step['stderrTail'][:300]}")

        artifacts = self._copy_artifacts(
            venture_id=venture_id,
            stage="SALES",
            run_id=f"sales_outreach_approve_{now_dt().strftime('%Y%m%d%H%M%S')}",
            paths=[
                self.sales_dir / "research/outreach/outreach_batch.approved.json",
            ],
        )

        run = self._record_run(
            venture_id=venture_id,
            stage="SALES",
            action="approve_sales_outreach",
            mode="review",
            status="passed",
            steps=[step],
            artifacts=artifacts,
            summary={"approver": approver},
        )

        updated = self._update_venture(
            venture_id,
            lambda v: {
                **v,
                "selections": {
                    **(v.get("selections") or {}),
                    "outreachBatchApproved": True,
                },
                "lastActions": {
                    **(v.get("lastActions") or {}),
                    "salesApproveOutreach": {"runId": run["id"], "at": now_iso(), "approver": approver},
                },
            },
        )
        preview_sync = self._sync_preview_with_gtm(updated)
        self._sync_venture_context(venture_id)
        return {"run": run, "venture": updated, "previewSync": preview_sync}

    def _action_dispatch_sales_outreach(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

        venture = self._require_venture(venture_id)
        self._require_stage(venture, "SALES", "dispatch_sales_outreach")

        mode = str(payload.get("mode") or "simulate").strip().lower()
        if mode not in {"simulate", "commit"}:
            raise StudioError("dispatch mode must be simulate or commit")

        confirm_live = bool(payload.get("confirmLive", False))
        if mode == "commit":
            if not confirm_live:
                raise StudioError("commit dispatch requires confirmLive=true")
            if not self._manual_arm_enabled():
                raise StudioError("manual arm is OFF; cannot commit dispatch")

        step = self._command_step(
            "sales_stage2_dispatch",
            ["python3", "scripts/dispatch_outreach_stage2.py", "--mode", mode],
            cwd=self.sales_dir,
            timeout=1200,
        )

        if step["status"] != "passed":
            self._record_run(
                venture_id=venture_id,
                stage="SALES",
                action="dispatch_sales_outreach",
                mode=mode,
                status="failed",
                steps=[step],
                artifacts=[],
                summary={},
                error=step["stderrTail"][-500:],
            )
            raise StudioError(f"Dispatch outreach failed: {step['stderrTail'][:300]}")

        artifacts = self._copy_artifacts(
            venture_id=venture_id,
            stage="SALES",
            run_id=f"sales_dispatch_{now_dt().strftime('%Y%m%d%H%M%S')}",
            paths=[
                self.sales_dir / "research/outreach/outreach_dispatch_report.latest.json",
                self.sales_dir / "research/outreach/outreach_send_requests.latest.json",
                self.repo_root / "handoffs/sales_to_operations.json",
            ],
        )

        run = self._record_run(
            venture_id=venture_id,
            stage="SALES",
            action="dispatch_sales_outreach",
            mode=mode,
            status="passed",
            steps=[step],
            artifacts=artifacts,
            summary={"mode": mode},
        )

        updated = self._update_venture(
            venture_id,
            lambda v: {
                **v,
                "stage": "SALES",
                "lastActions": {
                    **(v.get("lastActions") or {}),
                    "salesDispatch": {"runId": run["id"], "at": now_iso(), "mode": mode},
                },
            },
        )
        preview_sync = self._sync_preview_with_gtm(updated)
        self._sync_venture_context(venture_id)
        return {"run": run, "venture": updated, "previewSync": preview_sync}

    def _action_run_sales_conversion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

        venture = self._require_venture(venture_id)
        self._require_stage(venture, "SALES", "run_sales_conversion")

        mode = str(payload.get("mode") or "simulate").strip().lower()
        if mode not in {"simulate", "commit"}:
            raise StudioError("conversion mode must be simulate or commit")

        confirm_live = bool(payload.get("confirmLive", False))
        if mode == "commit":
            if not confirm_live:
                raise StudioError("commit conversion requires confirmLive=true")
            if not self._manual_arm_enabled():
                raise StudioError("manual arm is OFF; cannot commit conversion")

        step = self._command_step(
            "sales_stage3_conversion",
            ["python3", "scripts/run_convert_early_customers_stage3.py", "--mode", mode],
            cwd=self.sales_dir,
            timeout=2400,
        )

        if step["status"] != "passed":
            self._record_run(
                venture_id=venture_id,
                stage="SALES",
                action="run_sales_conversion",
                mode=mode,
                status="failed",
                steps=[step],
                artifacts=[],
                summary={},
                error=step["stderrTail"][-500:],
            )
            raise StudioError(f"Sales conversion failed: {step['stderrTail'][:300]}")

        artifacts = self._copy_artifacts(
            venture_id=venture_id,
            stage="SALES",
            run_id=f"sales_conversion_{now_dt().strftime('%Y%m%d%H%M%S')}",
            paths=[
                self.sales_dir / "research/conversion/conversion_scoreboard.latest.json",
                self.sales_dir / "research/conversion/close_motion.latest.json",
                self.sales_dir / "research/conversion/objection_playbook.latest.md",
                self.repo_root / "handoffs/sales_to_operations.json",
            ],
        )

        conversion_board = self._parse_json(self.sales_dir / "research/conversion/conversion_scoreboard.latest.json", {})
        conversion_summary = {
            "mode": mode,
            "scoreboardStatus": conversion_board.get("status"),
            "targetMrr": conversion_board.get("target_mrr") or conversion_board.get("targetMrr"),
            "currentMrr": conversion_board.get("current_mrr") or conversion_board.get("currentMrr"),
        }
        conversion_summary["agentRelay"] = self._relay_stage_agents(
            payload=payload,
            venture=venture,
            stage="SALES",
            action="run_sales_conversion",
            owner_agent="op1_sales",
            notify_agents=["op1_operations"],
            handoff_paths=[self.repo_root / "handoffs/sales_to_operations.json"],
            stage_summary=conversion_summary,
        )

        run = self._record_run(
            venture_id=venture_id,
            stage="SALES",
            action="run_sales_conversion",
            mode=mode,
            status="passed",
            steps=[step],
            artifacts=artifacts,
            summary=conversion_summary,
        )

        updated = self._update_venture(
            venture_id,
            lambda v: {
                **v,
                "lastActions": {
                    **(v.get("lastActions") or {}),
                    "salesConversion": {"runId": run["id"], "at": now_iso(), "mode": mode},
                },
            },
        )
        updated = self._propose_stage_transition(
            venture_id=venture_id,
            to_stage="OPERATIONS",
            reason="sales_conversion_completed",
            source_action="run_sales_conversion",
            summary={"runId": run["id"], "mode": mode},
        )
        preview_sync = self._sync_preview_with_gtm(updated)
        self._sync_venture_context(venture_id)
        return {"run": run, "venture": updated, "previewSync": preview_sync, "pendingTransition": updated.get("pendingTransition")}

    def _action_run_operations_full(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

        venture = self._require_venture(venture_id)
        self._require_stage(venture, "OPERATIONS", "run_operations_full")

        steps = [
            self._command_step("ops_stage1_tracking", ["bash", "scripts/run_stage1_tracking.sh"], cwd=self.operations_dir, timeout=2400),
            self._command_step("ops_stage2_feedback", ["bash", "scripts/run_stage2_feedback.sh"], cwd=self.operations_dir, timeout=2400),
            self._command_step("ops_stage3_iteration", ["bash", "scripts/run_stage3_iteration.sh"], cwd=self.operations_dir, timeout=2400),
        ]

        for step in steps:
            if step["status"] != "passed":
                self._record_run(
                    venture_id=venture_id,
                    stage="OPERATIONS",
                    action="run_operations_full",
                    mode="simulation",
                    status="failed",
                    steps=steps,
                    artifacts=[],
                    summary={},
                    error=step["stderrTail"][-500:],
                )
                raise StudioError(f"Operations pipeline failed at {step['name']}: {step['stderrTail'][:300]}")

        artifacts = self._copy_artifacts(
            venture_id=venture_id,
            stage="OPERATIONS",
            run_id=f"operations_full_{now_dt().strftime('%Y%m%d%H%M%S')}",
            paths=[
                self.operations_dir / "research/stage1_tracking/stage1_scoreboard.latest.json",
                self.operations_dir / "research/stage2_feedback/stage2_feedback_scoreboard.latest.json",
                self.operations_dir / "research/stage3_product_iteration/stage3_iteration_scoreboard.latest.json",
                self.repo_root / "handoffs/operations_to_product.json",
                self.repo_root / "handoffs/operations_to_marketing.json",
                self.repo_root / "handoffs/operations_to_sales.json",
                self.repo_root / "handoffs/operations_to_product_iterate.json",
                self.repo_root / "handoffs/operations_to_marketing_iterate.json",
                self.repo_root / "handoffs/operations_to_sales_iterate.json",
            ],
        )

        # KPI snapshot for venture
        stage1 = self._parse_json(self.operations_dir / "research/stage1_tracking/stage1_scoreboard.latest.json", {})
        stage2 = self._parse_json(self.operations_dir / "research/stage2_feedback/stage2_feedback_scoreboard.latest.json", {})
        stage3 = self._parse_json(self.operations_dir / "research/stage3_product_iteration/stage3_iteration_scoreboard.latest.json", {})

        kpi = {
            "ventureId": venture_id,
            "stage": "OPERATIONS",
            "capturedAt": now_iso(),
            "metrics": {
                "sessions": (((stage1.get("summary") or {}).get("traffic") or {}).get("sessions")),
                "qualifiedSignups": (((stage1.get("summary") or {}).get("signups") or {}).get("qualified_signups")),
                "paidCustomers": (((stage1.get("summary") or {}).get("signups") or {}).get("paid_customers")),
                "netNewMrr": (((stage1.get("summary") or {}).get("revenue") or {}).get("net_new_mrr")),
                "feedbackItems": (((stage2.get("summary") or {}).get("feedback") or {}).get("feedback_items_total")),
                "themes": (((stage2.get("summary") or {}).get("feedback") or {}).get("themes_total")),
                "experimentsPlanned": (((stage3.get("summary") or {}).get("flow") or {}).get("experiments_planned")),
                "shipCount": (((stage3.get("summary") or {}).get("outcomes") or {}).get("ship_count")),
                "iterateCount": (((stage3.get("summary") or {}).get("outcomes") or {}).get("iterate_count")),
                "observedMrrDelta30d": (((stage3.get("summary") or {}).get("outcomes") or {}).get("observed_mrr_delta_30d")),
            },
        }

        ops_summary = {
            "stage1Status": stage1.get("status"),
            "stage2Status": stage2.get("status"),
            "stage3Status": stage3.get("status"),
            "kpi": kpi.get("metrics") or {},
        }
        ops_summary["agentRelay"] = self._relay_stage_agents(
            payload=payload,
            venture=venture,
            stage="OPERATIONS",
            action="run_operations_full",
            owner_agent="op1_operations",
            notify_agents=["op1_product", "op1_marketing", "op1_sales"],
            handoff_paths=[
                self.repo_root / "handoffs/operations_to_product.json",
                self.repo_root / "handoffs/operations_to_marketing.json",
                self.repo_root / "handoffs/operations_to_sales.json",
                self.repo_root / "handoffs/operations_to_product_iterate.json",
                self.repo_root / "handoffs/operations_to_marketing_iterate.json",
                self.repo_root / "handoffs/operations_to_sales_iterate.json",
            ],
            stage_summary=ops_summary,
        )

        run = self._record_run(
            venture_id=venture_id,
            stage="OPERATIONS",
            action="run_operations_full",
            mode="simulation",
            status="passed",
            steps=steps,
            artifacts=artifacts,
            summary=ops_summary,
        )

        updated = self._update_venture(
            venture_id,
            lambda v: {
                **v,
                "kpiSnapshots": [*(v.get("kpiSnapshots") or []), kpi][-30:],
                "lastActions": {
                    **(v.get("lastActions") or {}),
                    "operationsFull": {"runId": run["id"], "at": now_iso()},
                },
            },
        )

        updated = self._propose_stage_transition(
            venture_id=venture_id,
            to_stage="ITERATE",
            reason="operations_full_completed",
            source_action="run_operations_full",
            summary={"runId": run["id"]},
        )

        preview_sync = self._sync_preview_with_gtm(updated)
        return {
            "run": run,
            "venture": updated,
            "kpiSnapshot": kpi,
            "previewSync": preview_sync,
            "pendingTransition": updated.get("pendingTransition"),
        }

    def _action_writeback_operations(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

        venture = self._require_venture(venture_id)
        current_stage = str(venture.get("stage") or "IDEA_POOL")
        if current_stage not in {"OPERATIONS", "ITERATE"}:
            raise StudioError(
                f"writeback_operations requires OPERATIONS/ITERATE stage, current={current_stage}. "
                "Please confirm pending transition first."
            )

        handoff_specs = [
            ("product", self.repo_root / "handoffs/operations_to_product.json", "PRODUCT"),
            ("marketing", self.repo_root / "handoffs/operations_to_marketing.json", "MARKETING"),
            ("sales", self.repo_root / "handoffs/operations_to_sales.json", "SALES"),
            ("product", self.repo_root / "handoffs/operations_to_product_iterate.json", "PRODUCT"),
            ("marketing", self.repo_root / "handoffs/operations_to_marketing_iterate.json", "MARKETING"),
            ("sales", self.repo_root / "handoffs/operations_to_sales_iterate.json", "SALES"),
        ]

        todos: List[Dict[str, Any]] = []
        for team, path, stage in handoff_specs:
            payload_json = self._parse_json(path, {})
            for idx, item in enumerate(payload_json.get("items") or []):
                if not isinstance(item, dict):
                    continue
                todo = {
                    "id": f"todo_{uuid.uuid4().hex[:10]}",
                    "ventureId": venture_id,
                    "team": team,
                    "stage": stage,
                    "title": item.get("recommended_action") or item.get("next_action") or f"{team} follow-up",
                    "priority": item.get("priority_tier") or ("P1" if str(item.get("decision")) == "ship" else "P2"),
                    "sourceFile": str(path.relative_to(self.repo_root)),
                    "sourceIndex": idx,
                    "data": item,
                    "createdAt": now_iso(),
                    "status": "open",
                }
                todos.append(todo)

        with self.store_lock:
            payload_store = self._load_loop_todos()
            items = [x for x in payload_store.get("items", []) if x.get("ventureId") != venture_id]
            items.extend(todos)
            payload_store["items"] = items
            self._save_loop_todos(payload_store)

        suggestions: Dict[str, List[Dict[str, Any]]] = {"product": [], "marketing": [], "sales": []}
        for team in ["product", "marketing", "sales"]:
            team_todos = [x for x in todos if x.get("team") == team]
            team_todos.sort(key=lambda x: str(x.get("priority") or "P9"))
            for item in team_todos[:3]:
                suggestions[team].append(
                    {
                        "title": item.get("title"),
                        "priority": item.get("priority"),
                        "source": item.get("sourceFile"),
                    }
                )

        run = self._record_run(
            venture_id=venture_id,
            stage="OPERATIONS",
            action="writeback_operations",
            mode="simulation",
            status="passed",
            steps=[],
            artifacts=[],
            summary={"todoCount": len(todos), "suggestions": suggestions},
        )

        updated = self._update_venture(
            venture_id,
            lambda v: {
                **v,
                "lastActions": {
                    **(v.get("lastActions") or {}),
                    "operationsWriteback": {
                        "runId": run["id"],
                        "at": now_iso(),
                        "todoCount": len(todos),
                        "suggestions": suggestions,
                    },
                },
            },
        )

        updated = self._propose_stage_transition(
            venture_id=venture_id,
            to_stage="ITERATE",
            reason="operations_writeback_ready",
            source_action="writeback_operations",
            summary={"runId": run["id"], "todoCount": len(todos)},
        )

        preview_sync = self._sync_preview_with_gtm(updated)
        self._sync_venture_context(venture_id)
        return {
            "run": run,
            "venture": updated,
            "todos": todos,
            "suggestions": suggestions,
            "previewSync": preview_sync,
            "pendingTransition": updated.get("pendingTransition"),
        }

    def _action_confirm_stage_transition(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

        decision = str(payload.get("decision") or "approved").strip().lower()
        note = str(payload.get("note") or "studio_confirmed")
        transition_id = str(payload.get("transitionId") or "").strip() or None

        before = self._require_venture(venture_id)
        pending = self._pending_transition(before)
        if not pending:
            raise StudioError("no pending stage transition")

        updated = self._apply_stage_transition(
            venture_id=venture_id,
            decision=decision,
            note=note,
            expected_transition_id=transition_id,
        )

        self._append_gate(
            {
                "gateId": f"gate_{uuid.uuid4().hex[:10]}",
                "ventureId": venture_id,
                "stage": str(pending.get("fromStage") or before.get("stage") or "UNKNOWN"),
                "decision": decision,
                "reason": str(pending.get("reason") or pending.get("sourceAction") or "pending_transition"),
                "decidedAt": now_iso(),
                "metadata": {
                    "transitionId": pending.get("id"),
                    "toStage": pending.get("toStage"),
                    "sourceAction": pending.get("sourceAction"),
                    "note": note,
                },
            }
        )

        preview_sync = self._sync_preview_with_gtm(updated)
        self._sync_venture_context(venture_id)
        return {
            "venture": updated,
            "previewSync": preview_sync,
            "decision": decision,
            "appliedTransition": pending,
        }

    def _action_confirm_iterate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        note = str(payload.get("note") or "confirm_next_cycle")
        if not venture_id:
            raise StudioError("ventureId is required")

        venture = self._require_venture(venture_id)
        stage = str(venture.get("stage") or "")
        if stage != "ITERATE":
            raise StudioError("confirm_iterate is only available in ITERATE stage")

        updated = self._propose_stage_transition(
            venture_id=venture_id,
            to_stage="PRODUCT",
            reason=f"next_cycle_requested:{note}",
            source_action="confirm_iterate",
            summary={
                "effect": "move_to_product_and_increment_cycle",
                "currentCycle": int(venture.get("cycle", 1) or 1),
            },
        )

        self._sync_venture_context(venture_id)
        return {"venture": updated, "pendingTransition": updated.get("pendingTransition")}

    def _action_stage_preflight(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip() or None

        checks = [
            ("marketing_verify_stage2", ["python3", "skills/op1-marketing-content-publish-stage2/scripts/verify_stage2_contract.py"], self.marketing_dir),
            ("marketing_verify_stage3", ["python3", "skills/op1-marketing-campaign-launch-stage3/scripts/verify_stage3_contract.py"], self.marketing_dir),
            ("sales_validate_classifier", ["python3", "scripts/validate_stage2_reply_classifier.py"], self.sales_dir),
            ("sales_verify_repro_stage3", ["python3", "scripts/verify_reproducibility_stage3.py"], self.sales_dir),
            ("ops_verify_stage1", ["python3", "scripts/verify_stage1_reproducibility.py"], self.operations_dir),
            ("ops_verify_stage2", ["python3", "scripts/verify_stage2_feedback_reproducibility.py"], self.operations_dir),
            ("ops_verify_stage3", ["python3", "scripts/verify_stage3_reproducibility.py"], self.operations_dir),
        ]
        raw_steps = [self._command_step(name, cmd, cwd=cwd, timeout=900) for name, cmd, cwd in checks]

        steps: List[Dict[str, Any]] = []
        for step in raw_steps:
            patched = dict(step)
            if patched.get("name") == "marketing_verify_stage3" and patched.get("status") == "failed":
                degrade = False
                reason = None
                # Tolerate stage3 preflight failure when there is no launchable campaign asset
                # (implementation exists, but current dataset has no launch candidate).
                try:
                    payload_json = json.loads(str(patched.get("stdoutTail") or "{}"))
                    failed_checks = payload_json.get("failed") or []
                    queue_counts = payload_json.get("queue_counts") or {}
                    only_missing_handoff = (
                        len(failed_checks) == 1
                        and isinstance(failed_checks[0], dict)
                        and failed_checks[0].get("name") == "handoff_campaign_launch_present"
                    )
                    queue_all_zero = all(int(queue_counts.get(k, 0) or 0) == 0 for k in ["launch_ready", "watchlist", "hold"])
                    if only_missing_handoff and queue_all_zero:
                        degrade = True
                        reason = "no_launchable_campaign_assets"
                except Exception:
                    pass

                if not degrade:
                    stage3_run = self._parse_json(self.marketing_dir / "research/stage3_campaign_launch/run.latest.json", {})
                    stage3_status = str(stage3_run.get("status") or "").lower()
                    if stage3_status in {"blocked_no_launchable_assets", "no_launchable_assets"}:
                        degrade = True
                        reason = stage3_status

                if degrade:
                    patched["status"] = "warning"
                    patched["warning"] = reason or "stage3_no_launchable_assets"
            steps.append(patched)

        extra_checks = []
        vercel = self._vercel_status()
        extra_checks.append(
            {
                "name": "vercel_ready",
                "status": "passed" if (vercel.get("installed") and vercel.get("authenticated")) else "warning",
                "summary": {"installed": vercel.get("installed"), "authenticated": vercel.get("authenticated"), "note": vercel.get("note")},
            }
        )

        arm_on = self._manual_arm_enabled()
        extra_checks.append(
            {
                "name": "manual_arm",
                "status": "passed" if arm_on else "warning",
                "summary": {"enabled": arm_on},
            }
        )

        if venture_id:
            venture = self._require_venture(venture_id)
            has_opp = bool(venture.get("opportunityId"))
            extra_checks.append(
                {
                    "name": "venture_context_contract",
                    "status": "passed" if has_opp else "failed",
                    "summary": {"ventureId": venture_id, "opportunityId": venture.get("opportunityId"), "stage": venture.get("stage")},
                }
            )

        failed_steps = [s for s in steps if s.get("status") == "failed"]
        warning_steps = [s for s in steps if s.get("status") == "warning"]
        failed_extra = [s for s in extra_checks if s.get("status") == "failed"]
        warning_extra = [s for s in extra_checks if s.get("status") == "warning"]

        status = "failed" if (failed_steps or failed_extra) else "passed"

        summary = {
            "totalChecks": len(steps) + len(extra_checks),
            "failedChecks": len(failed_steps) + len(failed_extra),
            "warningChecks": len(warning_steps) + len(warning_extra),
            "warningSteps": [s.get("name") for s in warning_steps],
            "extraChecks": extra_checks,
            "nextSteps": [
                "如果要 live 演示：先打开 Manual Arm 并确认 Vercel 登录可用。",
                "如果 preflight 失败：先修复 failed check，再执行 rehearsal_e2e。",
            ],
        }

        run = self._record_run(
            venture_id=venture_id,
            stage="PRECHECK",
            action="stage_preflight",
            mode="simulation",
            status=status,
            steps=steps,
            artifacts=[],
            summary=summary,
            error=failed_steps[0].get("stderrTail")[-500:] if failed_steps else (failed_extra[0].get("name") if failed_extra else None),
        )
        if status == "failed":
            first_name = failed_steps[0].get("name") if failed_steps else failed_extra[0].get("name")
            raise StudioError(f"preflight failed at {first_name}")
        return {"run": run}

    def _action_rehearsal_e2e(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

        # Safety: rehearsal is simulation-only.
        sequence = [
            ("run_product", {"ventureId": venture_id, "mode": "simulation", "async": False}),
            ("run_marketing_seo", {"ventureId": venture_id, "mode": "shadow", "async": False}),
            ("run_marketing_content", {"ventureId": venture_id, "mode": "review", "async": False}),
            ("run_marketing_campaign", {"ventureId": venture_id, "mode": "review", "async": False}),
            ("run_sales_prospecting", {"ventureId": venture_id, "async": False}),
            ("run_sales_outreach_plan", {"ventureId": venture_id, "async": False}),
            ("approve_sales_outreach", {"ventureId": venture_id, "approver": "studio_rehearsal", "note": "rehearsal", "async": False}),
            ("dispatch_sales_outreach", {"ventureId": venture_id, "mode": "simulate", "async": False}),
            ("run_sales_conversion", {"ventureId": venture_id, "mode": "simulate", "async": False}),
            ("run_operations_full", {"ventureId": venture_id, "async": False}),
            ("writeback_operations", {"ventureId": venture_id, "async": False}),
        ]

        completed = []
        replay = {
            "generatedAt": now_iso(),
            "ventureId": venture_id,
            "sequence": [x[0] for x in sequence],
            "steps": completed,
        }

        for action, p in sequence:
            try:
                result = self._run_action_sync(action, {"action": action, **p})
                completed.append({"action": action, "status": "passed", "resultKeys": list(result.keys())})

                # Rehearsal auto-approves pending transitions to keep end-to-end simulation continuous.
                venture_now = self._require_venture(venture_id)
                pending = self._pending_transition(venture_now)
                if pending:
                    confirm_res = self._run_action_sync(
                        "confirm_stage_transition",
                        {
                            "action": "confirm_stage_transition",
                            "ventureId": venture_id,
                            "transitionId": pending.get("id"),
                            "decision": "approved",
                            "note": f"rehearsal_auto_approve_after_{action}",
                            "async": False,
                        },
                    )
                    completed.append(
                        {
                            "action": "confirm_stage_transition",
                            "status": "passed",
                            "auto": True,
                            "toStage": (confirm_res.get("appliedTransition") or {}).get("toStage"),
                        }
                    )

                # Special case: marketing campaign generated candidates but no fallback pending transition.
                venture_now = self._require_venture(venture_id)
                if action == "run_marketing_campaign" and str(venture_now.get("stage") or "") == "MARKETING":
                    ctx = self._read_active_context(venture_now.get("opportunityId"))
                    candidates = (ctx.get("marketing") or {}).get("campaignCandidates") or []
                    if candidates:
                        cid = str((candidates[0] or {}).get("campaign_id") or (candidates[0] or {}).get("campaignId") or "").strip()
                        if cid:
                            self._run_action_sync(
                                "select_marketing_campaign",
                                {
                                    "action": "select_marketing_campaign",
                                    "ventureId": venture_id,
                                    "campaignId": cid,
                                    "async": False,
                                },
                            )
                            completed.append(
                                {
                                    "action": "select_marketing_campaign",
                                    "status": "passed",
                                    "auto": True,
                                    "campaignId": cid,
                                }
                            )
                            venture_now = self._require_venture(venture_id)
                            pending = self._pending_transition(venture_now)
                            if pending:
                                self._run_action_sync(
                                    "confirm_stage_transition",
                                    {
                                        "action": "confirm_stage_transition",
                                        "ventureId": venture_id,
                                        "transitionId": pending.get("id"),
                                        "decision": "approved",
                                        "note": "rehearsal_auto_approve_after_campaign_select",
                                        "async": False,
                                    },
                                )
                                completed.append(
                                    {
                                        "action": "confirm_stage_transition",
                                        "status": "passed",
                                        "auto": True,
                                        "toStage": str(pending.get("toStage") or ""),
                                    }
                                )
            except Exception as exc:  # noqa: BLE001
                completed.append({"action": action, "status": "failed", "error": str(exc)})
                replay["status"] = "failed"
                replay["error"] = str(exc)
                replay_path = self.rehearsals_dir / f"rehearsal_{venture_id}_{now_dt().strftime('%Y%m%d%H%M%S')}.json"
                self._write_json(replay_path, replay)

                run = self._record_run(
                    venture_id=venture_id,
                    stage="REHEARSAL",
                    action="rehearsal_e2e",
                    mode="simulation",
                    status="failed",
                    steps=[],
                    artifacts=self._copy_artifacts(
                        venture_id=venture_id,
                        stage="REHEARSAL",
                        run_id=f"rehearsal_{now_dt().strftime('%Y%m%d%H%M%S')}",
                        paths=[replay_path],
                    ),
                    summary={"completed": completed, "replayPath": str(replay_path.relative_to(self.repo_root))},
                    error=str(exc),
                )
                raise StudioError(f"rehearsal failed at {action}: {exc}")

        replay["status"] = "passed"
        replay_path = self.rehearsals_dir / f"rehearsal_{venture_id}_{now_dt().strftime('%Y%m%d%H%M%S')}.json"
        self._write_json(replay_path, replay)

        artifacts = self._copy_artifacts(
            venture_id=venture_id,
            stage="REHEARSAL",
            run_id=f"rehearsal_{now_dt().strftime('%Y%m%d%H%M%S')}",
            paths=[replay_path],
        )

        run = self._record_run(
            venture_id=venture_id,
            stage="REHEARSAL",
            action="rehearsal_e2e",
            mode="simulation",
            status="passed",
            steps=[],
            artifacts=artifacts,
            summary={"completed": completed, "replayPath": str(replay_path.relative_to(self.repo_root))},
        )
        self._sync_venture_context(venture_id)
        return {"run": run, "completed": completed, "replayPath": str(replay_path.relative_to(self.repo_root))}

    def _action_run_ceo_autopilot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        goal = str(payload.get("goal") or "Reach first $100 MRR with disciplined experimentation").strip()
        target_mrr = int(payload.get("targetMrr", 100) or 100)
        max_days = int(payload.get("maxDays", 14) or 14)
        max_spend = int(payload.get("maxSpend", 200) or 200)
        max_stage2_retries = int(payload.get("maxStage2Retries", 3) or 3)
        require_approval = bool(payload.get("requireApproval", True))
        orchestration_mode = str(payload.get("orchestrationMode") or "autopilot").strip().lower()

        if orchestration_mode == "multi_agent":
            ceo_ws = self.repo_root / "workspaces" / "op1_ceo"
            cmd = [
                "python3",
                "scripts/run_ceo_multi_agent_orchestrator_v1.py",
                "--goal",
                goal,
                "--target-mrr",
                str(target_mrr),
                "--max-days",
                str(max_days),
                "--max-spend",
                str(max_spend),
            ]
            if not require_approval:
                cmd.append("--no-require-approval")

            step = self._command_step(
                "run_ceo_multi_agent_orchestrator_v1",
                cmd,
                cwd=ceo_ws,
                timeout=5400,
            )

            status = "passed" if step["status"] == "passed" else "failed"
            paths = [
                ceo_ws / "research" / "ceo_orchestration" / "run.latest.json",
                ceo_ws / "research" / "ceo_orchestration" / "orchestrator_summary.latest.json",
            ]
        else:
            cmd = [
                "python3",
                "scripts/run_ceo_autopilot_v1.py",
                "--goal",
                goal,
                "--target-mrr",
                str(target_mrr),
                "--max-days",
                str(max_days),
                "--max-spend",
                str(max_spend),
                "--max-stage2-retries",
                str(max_stage2_retries),
            ]
            if not require_approval:
                cmd.append("--no-require-approval")

            step = self._command_step(
                "run_ceo_autopilot_v1",
                cmd,
                cwd=self.product_dir,
                timeout=5400,
            )

            status = "passed" if step["status"] == "passed" else "failed"
            paths = [
                self.product_dir / "research" / "ceo_orchestration" / "run.latest.json",
                self.product_dir / "research" / "ceo_orchestration" / "venture_state.latest.json",
            ]
        artifacts = self._copy_artifacts(
            venture_id=payload.get("ventureId") or "global",
            stage="CEO",
            run_id=f"ceo_{now_dt().strftime('%Y%m%d%H%M%S')}",
            paths=paths,
        )

        run = self._record_run(
            venture_id=payload.get("ventureId"),
            stage="CEO",
            action="run_ceo_autopilot",
            mode="simulation",
            status=status,
            steps=[step],
            artifacts=artifacts,
            summary={
                "goal": goal,
                "targetMrr": target_mrr,
                "maxDays": max_days,
                "maxSpend": max_spend,
                "requireApproval": require_approval,
                "maxStage2Retries": max_stage2_retries,
                "orchestrationMode": orchestration_mode,
            },
            error=step["stderrTail"][-500:] if status == "failed" else None,
        )

        if status != "passed":
            raise StudioError(f"run_ceo_autopilot failed: {step['stderrTail'][:300]}")

        return {"run": run, "artifacts": artifacts}

    def _run_vercel_audit_script(self, *, apply: bool = False, max_delete: int = 5, strategy: str = "archive") -> Dict[str, Any]:
        script = self.scripts_dir / "vercel_audit_cleanup.py"
        if not script.exists():
            raise StudioError("missing scripts/vercel_audit_cleanup.py")

        cmd = ["python3", str(script), "--keep-prefix", "op1-"]
        if apply:
            cmd.extend(["--apply", "--strategy", strategy, "--max-delete", str(max_delete)])

        step = self._command_step("vercel_audit_cleanup", cmd, cwd=self.repo_root, timeout=600)
        if step["status"] != "passed":
            raise StudioError(f"vercel audit script failed: {step['stderrTail'][:300]}")

        report_path = self.runtime_dir / "studio" / "vercel_audit.latest.json"
        report = self._parse_json(report_path, {})
        return {"step": step, "report": report, "reportPath": str(report_path.relative_to(self.repo_root))}

    def _action_vercel_audit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = self._run_vercel_audit_script(apply=False)
        run = self._record_run(
            venture_id=payload.get("ventureId"),
            stage="PRECHECK",
            action="vercel_audit",
            mode="simulation",
            status="passed",
            steps=[result["step"]],
            artifacts=[],
            summary={"reportPath": result["reportPath"]},
        )
        return {"run": run, "report": result["report"], "reportPath": result["reportPath"]}

    def _action_vercel_cleanup_apply(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        max_delete = int(payload.get("maxDelete", 3) or 3)
        strategy = str(payload.get("strategy") or "archive").strip().lower()
        if strategy not in {"archive", "delete"}:
            raise StudioError("strategy must be archive or delete")

        confirm = bool(payload.get("confirm", False))
        if not confirm:
            raise StudioError("vercel cleanup apply requires confirm=true")
        if strategy == "delete" and not bool(payload.get("confirmDelete", False)):
            raise StudioError("delete strategy requires confirmDelete=true")

        result = self._run_vercel_audit_script(apply=True, max_delete=max_delete, strategy=strategy)
        run = self._record_run(
            venture_id=payload.get("ventureId"),
            stage="PRECHECK",
            action="vercel_cleanup_apply",
            mode="live",
            status="passed",
            steps=[result["step"]],
            artifacts=[],
            summary={"reportPath": result["reportPath"], "maxDelete": max_delete, "strategy": strategy},
        )
        return {"run": run, "report": result["report"], "reportPath": result["reportPath"]}

    def _summarize_run(self, run: Dict[str, Any], *, include_details: bool = False) -> Dict[str, Any]:
        summary = {
            "id": run.get("id"),
            "ventureId": run.get("ventureId"),
            "stage": run.get("stage"),
            "action": run.get("action"),
            "mode": run.get("mode"),
            "status": run.get("status"),
            "createdAt": run.get("createdAt"),
            "startedAt": run.get("startedAt"),
            "endedAt": run.get("endedAt"),
            "error": run.get("error"),
            "summary": run.get("summary"),
            "artifactCount": len(run.get("artifacts") or []),
            "stepCount": len(run.get("steps") or []),
        }
        if include_details:
            summary["steps"] = run.get("steps")
            summary["artifacts"] = run.get("artifacts")
        return summary

    def _running_job_for(self, action: str, venture_id: Optional[str]) -> Optional[Dict[str, Any]]:
        with self.jobs_lock:
            items = list(self.jobs.values())
        for job in items:
            if job.get("action") != action:
                continue
            if str(job.get("ventureId") or "") != str(venture_id or ""):
                continue
            if job.get("status") in {"queued", "running"}:
                return copy.deepcopy(job)
        return None

    def _action_state_map(self, *, venture_id: Optional[str], recommended_actions: List[Dict[str, Any]], recent_runs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        actions = {str(item.get("action")) for item in recommended_actions if item.get("action")}
        status_map: Dict[str, Dict[str, Any]] = {}

        # Running/queued jobs dominate state.
        for action in actions:
            job = self._running_job_for(action, venture_id)
            if job:
                status_map[action] = {
                    "status": str(job.get("status") or "running"),
                    "jobId": job.get("id"),
                    "updatedAt": job.get("updatedAt") or job.get("createdAt"),
                    "message": job.get("error") or None,
                }

        # Backfill with latest run status when no running job.
        for run in recent_runs:
            action = str(run.get("action") or "")
            if action not in actions:
                continue
            if action in status_map:
                continue
            status = str(run.get("status") or "unknown")
            normalized = "succeeded" if status == "passed" else "failed" if status == "failed" else "idle"
            status_map[action] = {
                "status": normalized,
                "runId": run.get("id"),
                "updatedAt": run.get("endedAt") or run.get("createdAt"),
                "message": run.get("error"),
            }

        for action in actions:
            status_map.setdefault(action, {"status": "idle", "message": None})

        return status_map

    def _global_run_state(self, *, venture_id: Optional[str], recent_runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        with self.jobs_lock:
            jobs = [copy.deepcopy(v) for v in self.jobs.values()]

        scoped_jobs = [
            j
            for j in jobs
            if (not venture_id or str(j.get("ventureId") or "") == str(venture_id)) and j.get("status") in {"queued", "running"}
        ]
        scoped_jobs.sort(key=lambda x: str(x.get("createdAt") or ""), reverse=True)

        if scoped_jobs:
            top = scoped_jobs[0]
            started_at = top.get("startedAt") or top.get("createdAt")
            elapsed_ms = None
            if started_at:
                try:
                    dt = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
                    elapsed_ms = int((now_dt() - dt).total_seconds() * 1000)
                except Exception:
                    elapsed_ms = None
            return {
                "status": str(top.get("status") or "running"),
                "runningAction": top.get("action"),
                "runningJobId": top.get("id"),
                "elapsedMs": elapsed_ms,
                "runningCount": len(scoped_jobs),
                "lastError": None,
            }

        last_failed = None
        for run in recent_runs:
            if run.get("status") == "failed":
                last_failed = run
                break

        return {
            "status": "idle",
            "runningAction": None,
            "runningJobId": None,
            "elapsedMs": None,
            "runningCount": 0,
            "lastError": last_failed.get("error") if last_failed else None,
            "lastFailedAction": last_failed.get("action") if last_failed else None,
        }

    def _build_stage_artifact_cards(self, stage_results: List[Dict[str, Any]], deployments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_stage: Dict[str, Dict[str, Any]] = {str(x.get("stage")): x for x in stage_results}
        cards: List[Dict[str, Any]] = []

        def file_item(label: str, path: Optional[str]) -> Optional[Dict[str, Any]]:
            if not path:
                return None
            p = str(path)
            return {
                "label": label,
                "kind": "file",
                "path": p,
                "previewable": p.endswith(".html") or p.endswith(".htm"),
            }

        def preview_item(label: str, path: Optional[str]) -> Optional[Dict[str, Any]]:
            if not path:
                return None
            return {"label": label, "kind": "preview", "path": str(path)}

        def url_item(label: str, url: Optional[str]) -> Optional[Dict[str, Any]]:
            if not url:
                return None
            return {"label": label, "kind": "url", "url": url}

        def detect_path(art: Dict[str, Any]) -> Tuple[str, Optional[str]]:
            source = str(art.get("sourcePath") or "")
            open_path = art.get("snapshotPath") or art.get("sourcePath")
            return source, open_path

        product = by_stage.get("PRODUCT") or {}
        product_summary = product.get("summary") or {}
        product_artifacts = product.get("artifacts") or []
        build_report = None
        for art in product_artifacts:
            source, open_path = detect_path(art)
            if source and ("stage2_web_product/run.latest.json" in source or source.endswith("run.latest.json")):
                build_report = open_path
                break
        preview_ref = product_summary.get("previewPath")
        landing_preview_ref = product_summary.get("landingPreviewPath")

        if not preview_ref:
            for dep in deployments:
                if dep.get("previewPath"):
                    preview_ref = dep.get("previewPath")
                    break
        if not build_report:
            fallback_build = self.product_dir / "research/stage2_web_product/run.latest.json"
            if fallback_build.exists():
                build_report = str(fallback_build.relative_to(self.repo_root))

        if not landing_preview_ref:
            landing_dir = self.runtime_dir / "studio" / "landing_previews"
            if landing_dir.exists():
                html_files = sorted(landing_dir.glob("*.html"), key=lambda p: p.stat().st_mtime)
                if html_files:
                    landing_preview_ref = str(html_files[-1].relative_to(self.repo_root))
        if not landing_preview_ref:
            generated = self._ensure_landing_preview_html({"id": "latest-landing", "opportunityId": None})
            if generated:
                landing_preview_ref = generated

        live_examples = self._parse_json(self.product_dir / "research/live_examples.latest.json", {})
        online_examples = [x for x in (live_examples.get("all_online_examples") or []) if isinstance(x, str) and x.startswith("http")]

        product_items = [
            url_item("Open Deployment", product_summary.get("deploymentUrl")),
            preview_item("Open Web Product Preview", preview_ref),
            preview_item("Open Landing Preview", landing_preview_ref),
            file_item("Open Build Report", build_report),
            url_item("Open in Vercel", f"https://vercel.com/dashboard/projects/{product_summary.get('vercelProject')}" if product_summary.get("vercelProject") else None),
            url_item("Open Best-practice Example 1", online_examples[0] if len(online_examples) > 0 else None),
            url_item("Open Best-practice Example 2", online_examples[1] if len(online_examples) > 1 else None),
        ]
        cards.append({"stage": "PRODUCT", "title": "Product 产物", "items": [x for x in product_items if x]})

        marketing = by_stage.get("MARKETING") or {}
        marketing_artifacts = marketing.get("artifacts") or []
        content_queue = None
        campaign_queue = None
        for art in marketing_artifacts:
            source, open_path = detect_path(art)
            if not source:
                continue
            if "publish.queue.latest.json" in source and not content_queue:
                content_queue = open_path
            if "campaigns.queue.latest.json" in source and not campaign_queue:
                campaign_queue = open_path
        if not content_queue:
            fallback = self.marketing_dir / "research/stage2_content_publish/publish.queue.latest.json"
            if fallback.exists():
                content_queue = str(fallback.relative_to(self.repo_root))
        if not campaign_queue:
            fallback = self.marketing_dir / "research/stage3_campaign_launch/campaigns.queue.latest.json"
            if fallback.exists():
                campaign_queue = str(fallback.relative_to(self.repo_root))

        cards.append(
            {
                "stage": "MARKETING",
                "title": "Marketing 产物",
                "items": [x for x in [file_item("Open Content Queue", content_queue), file_item("Open Campaign Queue", campaign_queue)] if x],
            }
        )

        sales = by_stage.get("SALES") or {}
        sales_artifacts = sales.get("artifacts") or []
        outreach_pack = None
        conversion_board = None
        for art in sales_artifacts:
            source, open_path = detect_path(art)
            if not source:
                continue
            if "outreach_batch.ready.json" in source and not outreach_pack:
                outreach_pack = open_path
            if "conversion_scoreboard" in source and not conversion_board:
                conversion_board = open_path
        if not outreach_pack:
            fallback = self.sales_dir / "research/outreach/outreach_batch.ready.json"
            if fallback.exists():
                outreach_pack = str(fallback.relative_to(self.repo_root))
        if not conversion_board:
            fallback = self.sales_dir / "research/conversion/conversion_scoreboard.latest.json"
            if fallback.exists():
                conversion_board = str(fallback.relative_to(self.repo_root))

        cards.append(
            {
                "stage": "SALES",
                "title": "Sales 产物",
                "items": [x for x in [file_item("Open Outreach Pack", outreach_pack), file_item("Open Conversion Scoreboard", conversion_board)] if x],
            }
        )

        ops = by_stage.get("OPERATIONS") or {}
        ops_artifacts = ops.get("artifacts") or []
        kpi_snapshot = None
        loop_todos = None
        for art in ops_artifacts:
            source, open_path = detect_path(art)
            if not source:
                continue
            if "stage1_scoreboard" in source and not kpi_snapshot:
                kpi_snapshot = open_path
            if "loop_todos" in source and not loop_todos:
                loop_todos = open_path
        if not kpi_snapshot:
            fallback = self.operations_dir / "research/stage1_tracking/stage1_scoreboard.latest.json"
            if fallback.exists():
                kpi_snapshot = str(fallback.relative_to(self.repo_root))
        if not loop_todos:
            loop_todos = "dashboard/.runtime/studio/loop_todos.json"
        cards.append(
            {
                "stage": "OPERATIONS",
                "title": "Operations 产物",
                "items": [x for x in [file_item("Open KPI Snapshot", kpi_snapshot), file_item("Open Loop Todos", loop_todos)] if x],
            }
        )

        return cards

    def _next_recommended_actions(self, active_venture: Optional[Dict[str, Any]], active_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not active_venture:
            return [
                {
                    "action": "refresh_ideas",
                    "label": "刷新 startup ideas",
                    "description": "先刷新 Product ideas，再选择一个项目创建 venture。",
                    "stage": "IDEA_POOL",
                    "payload": {"action": "refresh_ideas", "async": True},
                }
            ]

        stage = str(active_venture.get("stage") or "SELECTED")
        vid = active_venture.get("id")
        selections = active_venture.get("selections") or {}
        out: List[Dict[str, Any]] = []

        pending = self._pending_transition(active_venture)
        if pending:
            to_stage = str(pending.get("toStage") or "UNKNOWN")
            from_stage = str(pending.get("fromStage") or stage)
            reason = str(pending.get("reason") or "pending_transition")
            trans_id = str(pending.get("id") or "")
            return [
                {
                    "action": "confirm_stage_transition",
                    "label": f"确认进入 {to_stage}",
                    "description": f"当前阶段 {from_stage}，待确认迁移到 {to_stage}。原因：{reason}",
                    "stage": from_stage,
                    "payload": {
                        "action": "confirm_stage_transition",
                        "ventureId": vid,
                        "transitionId": trans_id,
                        "decision": "approved",
                        "note": f"approve_{from_stage}_to_{to_stage}",
                        "async": False,
                    },
                    "requiresUserChoice": False,
                },
                {
                    "action": "reject_stage_transition",
                    "label": f"拒绝进入 {to_stage}",
                    "description": "拒绝后保持当前阶段，继续人工选择。",
                    "stage": from_stage,
                    "payload": {
                        "action": "confirm_stage_transition",
                        "ventureId": vid,
                        "transitionId": trans_id,
                        "decision": "rejected",
                        "note": f"reject_{from_stage}_to_{to_stage}",
                        "async": False,
                    },
                    "requiresUserChoice": False,
                },
            ]

        if stage in {"SELECTED", "PRODUCT"}:
            out.append(
                {
                    "action": "run_product",
                    "label": "执行 Product（simulation）",
                    "description": "生成 landing + 本地预览（不触发 live 部署）。",
                    "stage": "PRODUCT",
                    "payload": {"action": "run_product", "ventureId": vid, "mode": "simulation", "async": True},
                }
            )
        if stage == "MARKETING":
            out.extend(
                [
                    {
                        "action": "run_marketing_seo",
                        "label": "运行 SEO experiments",
                        "description": "刷新关键词与实验队列。",
                        "stage": "MARKETING",
                        "payload": {"action": "run_marketing_seo", "ventureId": vid, "mode": "shadow", "async": True},
                    },
                    {
                        "action": "run_marketing_content",
                        "label": "生成 Publish content 候选",
                        "description": "生成内容候选后进行人工勾选审批。",
                        "stage": "MARKETING",
                        "payload": {"action": "run_marketing_content", "ventureId": vid, "mode": "review", "async": True},
                    },
                    {
                        "action": "run_marketing_campaign",
                        "label": "生成 Launch campaigns 候选",
                        "description": "选择 campaign 后推进到 Sales。",
                        "stage": "MARKETING",
                        "payload": {"action": "run_marketing_campaign", "ventureId": vid, "mode": "review", "async": True},
                    },
                ]
            )
            if not selections.get("campaignId"):
                out.append(
                    {
                        "action": "select_marketing_campaign",
                        "label": "从候选中选择 campaign",
                        "description": "选择一个 campaign 作为 Sales 输入。",
                        "stage": "MARKETING",
                        "payload": {"action": "select_marketing_campaign", "ventureId": vid},
                        "requiresUserChoice": True,
                    }
                )
        if stage == "SALES":
            out.append(
                {
                    "action": "select_marketing_campaign",
                    "label": "更换/确认 campaign 输入",
                    "description": "从 Marketing 候选中选择 campaign（支持在 SALES 阶段变更）。",
                    "stage": "SALES",
                    "payload": {"action": "select_marketing_campaign", "ventureId": vid},
                    "requiresUserChoice": True,
                }
            )
            out.extend(
                [
                    {
                        "action": "run_sales_prospecting",
                        "label": "Identify prospects",
                        "description": "生成分层线索队列。",
                        "stage": "SALES",
                        "payload": {"action": "run_sales_prospecting", "ventureId": vid, "async": True},
                    },
                    {
                        "action": "run_sales_outreach_plan",
                        "label": "规划 Send outreach",
                        "description": "生成外联批次并等待人工批准。",
                        "stage": "SALES",
                        "payload": {"action": "run_sales_outreach_plan", "ventureId": vid, "async": True},
                    },
                    {
                        "action": "approve_sales_outreach",
                        "label": "批准外联批次",
                        "description": "人工审批后才允许 dispatch。",
                        "stage": "SALES",
                        "payload": {"action": "approve_sales_outreach", "ventureId": vid, "async": True},
                    },
                    {
                        "action": "dispatch_sales_outreach",
                        "label": "Dispatch（simulate）",
                        "description": "建议先 simulate，确认后再 commit。",
                        "stage": "SALES",
                        "payload": {
                            "action": "dispatch_sales_outreach",
                            "ventureId": vid,
                            "mode": "simulate",
                            "async": True,
                        },
                    },
                    {
                        "action": "run_sales_conversion",
                        "label": "Convert（simulate）",
                        "description": "模拟转化，观察 close motion 与 scorecard。",
                        "stage": "SALES",
                        "payload": {
                            "action": "run_sales_conversion",
                            "ventureId": vid,
                            "mode": "simulate",
                            "async": True,
                        },
                    },
                ]
            )
        if stage == "OPERATIONS":
            out.append(
                {
                    "action": "run_operations_full",
                    "label": "Run Operations full loop",
                    "description": "执行 tracking + feedback + iteration。",
                    "stage": "OPERATIONS",
                    "payload": {"action": "run_operations_full", "ventureId": vid, "async": True},
                }
            )
        if stage == "ITERATE":
            out.extend(
                [
                    {
                        "action": "writeback_operations",
                        "label": "回写下一轮待办",
                        "description": "把 Ops 产物回写到 Product/Marketing/Sales 待办。",
                        "stage": "ITERATE",
                        "payload": {"action": "writeback_operations", "ventureId": vid, "async": True},
                    },
                    {
                        "action": "confirm_iterate",
                        "label": "准备进入下一轮",
                        "description": "会创建‘ITERATE→PRODUCT’待确认迁移，不会直接跳转。",
                        "stage": "ITERATE",
                        "payload": {
                            "action": "confirm_iterate",
                            "ventureId": vid,
                            "note": "next_cycle_requested",
                            "async": False,
                        },
                    },
                ]
            )

        out.extend(
            [
                {
                    "action": "stage_preflight",
                    "label": "运行演示前预检查",
                    "description": "执行 Marketing/Sales/Ops 合同与可复现性检查。",
                    "stage": "PRECHECK",
                    "payload": {"action": "stage_preflight", "ventureId": vid, "async": True},
                },
                {
                    "action": "vercel_audit",
                    "label": "审计 Vercel 项目",
                    "description": "整理项目清单并识别可清理候选。",
                    "stage": "PRECHECK",
                    "payload": {"action": "vercel_audit", "ventureId": vid, "async": True},
                },
                {
                    "action": "rehearsal_e2e",
                    "label": "一键彩排（simulation）",
                    "description": "按安全模式串行执行全流程，用于演示前检查。",
                    "stage": "REHEARSAL",
                    "payload": {"action": "rehearsal_e2e", "ventureId": vid, "async": True},
                },
            ]
        )

        return out[:10]

    def _stage_progress(self, stage: str) -> Dict[str, Any]:
        normalized = stage if stage in STAGE_ORDER else "IDEA_POOL"
        idx = STAGE_ORDER.index(normalized) + 1
        return {
            "stage": normalized,
            "index": idx,
            "total": len(STAGE_ORDER),
            "label": f"{normalized} ({idx}/{len(STAGE_ORDER)})",
        }

    def _recent_user_prompt_history(self, venture_id: Optional[str], limit: int = 8) -> List[Dict[str, Any]]:
        payload = self._load_user_prompts()
        items = payload.get("items") or []
        if venture_id:
            items = [x for x in items if x.get("ventureId") in {None, venture_id}]
        else:
            items = [x for x in items if x.get("ventureId") is None]
        return list(reversed(items[-limit:]))

    def _append_user_prompt_history(self, entry: Dict[str, Any]) -> None:
        payload = self._load_user_prompts()
        items = payload.get("items") or []
        items.append(entry)
        payload["items"] = items[-400:]
        self._save_user_prompts(payload)

    def _build_user_questions(
        self,
        *,
        active_venture: Optional[Dict[str, Any]],
        active_context: Dict[str, Any],
        recommended_actions: List[Dict[str, Any]],
        manual_arm_enabled: bool,
    ) -> List[Dict[str, Any]]:
        stage = str((active_venture or {}).get("stage") or "IDEA_POOL")
        selections = (active_venture or {}).get("selections") or {}
        by_action = {
            str(item.get("action")): item
            for item in recommended_actions
            if isinstance(item, dict) and item.get("action")
        }

        out: List[Dict[str, Any]] = []

        def add_question(
            *,
            question_id: str,
            priority: str,
            question: str,
            reason: str,
            suggested_action: Optional[str] = None,
        ) -> None:
            item: Dict[str, Any] = {
                "id": question_id,
                "priority": priority,
                "question": question,
                "reason": reason,
            }
            if suggested_action and suggested_action in by_action:
                action = by_action[suggested_action]
                item["suggestedAction"] = {
                    "action": action.get("action"),
                    "label": action.get("label"),
                    "stage": action.get("stage"),
                    "payload": action.get("payload"),
                    "requiresUserChoice": bool(action.get("requiresUserChoice")),
                }
            out.append(item)

        if not active_venture:
            add_question(
                question_id="q_idea_refresh",
                priority="high",
                question="要先刷新 startup ideas 吗？",
                reason="当前没有 active venture，无法推进 Product/Marketing/Sales/Ops 阶段。",
                suggested_action="refresh_ideas",
            )
            return out

        pending = self._pending_transition(active_venture)
        if pending:
            to_stage = str(pending.get("toStage") or "UNKNOWN")
            from_stage = str(pending.get("fromStage") or stage)
            add_question(
                question_id="q_pending_transition",
                priority="high",
                question=f"是否确认从 {from_stage} 进入 {to_stage}？",
                reason="阶段迁移已准备好，但需要你显式确认。",
                suggested_action="confirm_stage_transition",
            )

        if stage in {"SELECTED", "PRODUCT"}:
            add_question(
                question_id="q_product_sim",
                priority="high",
                question="是否现在先执行 Product simulation（先不做 live 部署）？",
                reason="先拿到 landing + preview 产物，再推进到 Marketing，风险最低。",
                suggested_action="run_product",
            )

        if stage == "MARKETING":
            add_question(
                question_id="q_marketing_content",
                priority="high",
                question="是否先生成并审批内容候选（Publish content）？",
                reason="Sales 依赖可用内容资产和 campaign 输入。",
                suggested_action="run_marketing_content",
            )
            if not selections.get("campaignId"):
                add_question(
                    question_id="q_marketing_campaign_select",
                    priority="high",
                    question="需要你从候选里明确选定一个 campaign，是否现在完成？",
                    reason="未选 campaign 会阻塞后续 Sales 路径。",
                    suggested_action="select_marketing_campaign",
                )

        if stage == "SALES":
            if not selections.get("campaignId"):
                add_question(
                    question_id="q_sales_campaign_select",
                    priority="high",
                    question="当前 SALES 阶段还未绑定 campaign，是否现在补选/更换？",
                    reason="campaign 输入会直接影响外联文案与转化节奏。",
                    suggested_action="select_marketing_campaign",
                )
            add_question(
                question_id="q_sales_safe_mode",
                priority="high",
                question="这轮是否坚持先 simulate，再决定 commit？",
                reason="先验证外联与转化路径可避免误触 live 行为。",
                suggested_action="dispatch_sales_outreach",
            )
            add_question(
                question_id="q_sales_conversion",
                priority="medium",
                question="是否现在跑一轮 conversion simulate 看 scorecard？",
                reason="可提前发现漏斗瓶颈，减少盲目 commit。",
                suggested_action="run_sales_conversion",
            )

        if stage == "OPERATIONS":
            add_question(
                question_id="q_ops_full",
                priority="high",
                question="是否现在执行 Operations 全流程（stage1+2+3）？",
                reason="只有完成运营回路，才能形成下一轮可执行改进。",
                suggested_action="run_operations_full",
            )

        if stage == "ITERATE":
            add_question(
                question_id="q_iterate_confirm",
                priority="high",
                question="是否现在创建“下一轮迁移申请”（ITERATE -> PRODUCT）？",
                reason="点击后不会直接跳转，仍需在迁移卡片中二次确认。",
                suggested_action="confirm_iterate",
            )

        if not manual_arm_enabled:
            add_question(
                question_id="q_live_gate",
                priority="medium",
                question="如需 live 动作，是否先手动打开 Manual Arm？",
                reason="Manual Arm=OFF 时，live 路径会被安全门禁阻断。",
            )

        return out[:8]

    def _build_user_prompt_reply(
        self,
        *,
        prompt: str,
        progress: Dict[str, Any],
        pending_questions: List[Dict[str, Any]],
        recommended_actions: List[Dict[str, Any]],
        manual_arm_enabled: bool,
    ) -> str:
        text = prompt.strip()
        low = text.lower()

        lines: List[str] = []
        lines.append(f"你当前在 {progress.get('label')}。")

        if any(k in text for k in ["现在", "哪一步", "进度", "阶段", "到哪", "current"]):
            lines.append("当前建议优先完成该阶段的高优先问题，再进入下一阶段。")

        if any(k in low for k in ["live", "上线", "commit", "外联", "deploy", "发布"]):
            if manual_arm_enabled:
                lines.append("你已开启 Manual Arm；live 动作仍需显式 confirmLive/confirmProduction。")
            else:
                lines.append("当前 Manual Arm=OFF，live 动作会被门禁阻断。建议先 simulation。")

        if any(k in text for k in ["下一步", "next", "先做什么", "建议"]):
            top = recommended_actions[:3]
            if top:
                lines.append("建议动作（按优先级）：")
                for idx, item in enumerate(top, start=1):
                    lines.append(f"{idx}. {item.get('label')} [{item.get('stage')}]")
            else:
                lines.append("当前没有推荐动作，建议先刷新快照或检查 active venture。")

        if pending_questions:
            lines.append("当前需要你决策的问题：")
            for idx, q in enumerate(pending_questions[:3], start=1):
                lines.append(f"- Q{idx}: {q.get('question')}")
            if any(str(q.get("id") or "") == "q_pending_transition" for q in pending_questions):
                lines.append("提示：阶段迁移必须显式确认，不会自动推进。")
        else:
            lines.append("当前没有阻塞型用户问题。")

        if len(lines) <= 2:
            lines.append("你可以继续追问：是否应该先 simulation、当前阻塞点、或下一步唯一动作。")

        return "\n".join(lines)

    def _action_submit_user_prompt(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt_text = str(payload.get("prompt") or payload.get("message") or "").strip()
        if not prompt_text:
            raise StudioError("prompt is required")
        if len(prompt_text) > 4000:
            raise StudioError("prompt is too long (max 4000 chars)")

        with self.store_lock:
            state = self._load_state()
            ventures_payload = self._load_ventures()

        ventures = ventures_payload.get("items") or []
        requested_venture_id = str(payload.get("ventureId") or "").strip() or None
        active_id = requested_venture_id or state.get("activeVentureId")

        active_venture = None
        for venture in ventures:
            if venture.get("id") == active_id:
                active_venture = venture
                break

        if not active_venture and ventures:
            active_venture = ventures[-1]
            active_id = active_venture.get("id")

        opp_id = (active_venture or {}).get("opportunityId")
        active_context = self._read_active_context(opp_id)
        recommended_actions = self._next_recommended_actions(active_venture, active_context)
        manual_arm_enabled = bool(self._manual_arm_enabled())
        pending_questions = self._build_user_questions(
            active_venture=active_venture,
            active_context=active_context,
            recommended_actions=recommended_actions,
            manual_arm_enabled=manual_arm_enabled,
        )

        stage = str((active_venture or {}).get("stage") or "IDEA_POOL")
        progress = self._stage_progress(stage)

        copilot_ctx = self._copilot_compact_context(
            active_venture=active_venture,
            progress=progress,
            recommended_actions=recommended_actions,
            pending_questions=pending_questions,
            manual_arm_enabled=manual_arm_enabled,
            active_context=active_context,
        )
        llm_json = self._call_copilot_llm(prompt_text, copilot_ctx)

        suggested_action_ids: List[str] = []
        questions_for_user: List[str] = []
        risk_flags: List[str] = []
        answer_mode = "fallback"

        if isinstance(llm_json, dict) and isinstance(llm_json.get("answer"), str) and llm_json.get("answer", "").strip():
            reply = str(llm_json.get("answer")).strip()
            answer_mode = "llm"
            raw_ids = llm_json.get("suggestedActionIds") or []
            if isinstance(raw_ids, list):
                suggested_action_ids = [str(x).strip() for x in raw_ids if str(x).strip()]
            raw_questions = llm_json.get("questionsForUser") or []
            if isinstance(raw_questions, list):
                questions_for_user = [str(x).strip() for x in raw_questions if str(x).strip()]
            raw_risks = llm_json.get("riskFlags") or []
            if isinstance(raw_risks, list):
                risk_flags = [str(x).strip() for x in raw_risks if str(x).strip()]
        else:
            reply = self._build_user_prompt_reply(
                prompt=prompt_text,
                progress=progress,
                pending_questions=pending_questions,
                recommended_actions=recommended_actions,
                manual_arm_enabled=manual_arm_enabled,
            )

        suggested_actions = []
        by_action = {str(x.get("action")): x for x in recommended_actions if isinstance(x, dict) and x.get("action")}
        if suggested_action_ids:
            for aid in suggested_action_ids:
                if aid in by_action:
                    suggested_actions.append(by_action[aid])
        if not suggested_actions:
            suggested_actions = recommended_actions[:3]

        entry = {
            "id": f"prompt_{uuid.uuid4().hex[:10]}",
            "createdAt": now_iso(),
            "ventureId": active_id,
            "stage": progress.get("stage"),
            "prompt": prompt_text,
            "reply": reply,
            "mode": answer_mode,
            "riskFlags": risk_flags,
            "questionsForUser": questions_for_user,
        }

        with self.store_lock:
            self._append_user_prompt_history(entry)
            history = self._recent_user_prompt_history(active_id, limit=8)

        return {
            "submitted": True,
            "entry": entry,
            "reply": reply,
            "mode": answer_mode,
            "progress": progress,
            "pendingQuestions": pending_questions,
            "suggestedActions": suggested_actions,
            "questionsForUser": questions_for_user,
            "riskFlags": risk_flags,
            "history": history,
            "manualArmEnabled": manual_arm_enabled,
            "contextHash": copilot_ctx.get("contextHash"),
        }

    def _run_action_sync(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        dispatch = {
            "refresh_ideas": self._action_refresh_ideas,
            "create_venture": self._action_create_venture,
            "set_active_venture": self._action_set_active_venture,
            "submit_user_prompt": self._action_submit_user_prompt,
            "reset_demo_state": self._action_reset_demo_state,
            "run_product": self._action_run_product,
            "run_marketing_seo": self._action_run_marketing_seo,
            "run_marketing_content": self._action_run_marketing_content,
            "review_marketing_content": self._action_review_marketing_content,
            "run_marketing_campaign": self._action_run_marketing_campaign,
            "select_marketing_campaign": self._action_select_marketing_campaign,
            "run_sales_prospecting": self._action_run_sales_prospecting,
            "run_sales_outreach_plan": self._action_run_sales_outreach_plan,
            "approve_sales_outreach": self._action_approve_sales_outreach,
            "dispatch_sales_outreach": self._action_dispatch_sales_outreach,
            "run_sales_conversion": self._action_run_sales_conversion,
            "run_operations_full": self._action_run_operations_full,
            "writeback_operations": self._action_writeback_operations,
            "confirm_iterate": self._action_confirm_iterate,
            "confirm_stage_transition": self._action_confirm_stage_transition,
            "stage_preflight": self._action_stage_preflight,
            "rehearsal_e2e": self._action_rehearsal_e2e,
            "run_ceo_autopilot": self._action_run_ceo_autopilot,
            "vercel_audit": self._action_vercel_audit,
            "vercel_cleanup_apply": self._action_vercel_cleanup_apply,
        }
        fn = dispatch.get(action)
        if not fn:
            raise StudioError(f"unsupported action: {action}")
        return fn(payload)

    def dispatch_action(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        action = str(payload.get("action") or "").strip()
        if not action:
            raise StudioError("action is required")

        venture_id = payload.get("ventureId")
        request_async = bool(payload.get("async", True))

        if action in ASYNC_ACTIONS and request_async:
            if action in DUPLICATE_GUARD_ACTIONS:
                existing = self._running_job_for(action, venture_id)
                if existing:
                    return {
                        "ok": True,
                        "async": True,
                        "duplicate": True,
                        "job": self._summarize_job(existing, include_result=False),
                        "message": "existing queued/running job reused",
                    }
            job = self._submit_job(action, payload)
            return {"ok": True, "async": True, "job": self._summarize_job(job, include_result=False)}

        result = self._run_action_sync(action, payload)
        return {"ok": True, "async": False, "result": result}

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------
    def snapshot(
        self,
        *,
        monitor_snapshot: Optional[Dict[str, Any]] = None,
        include_run_details: bool = False,
    ) -> Dict[str, Any]:
        with self.store_lock:
            state = self._load_state()
            ventures_payload = self._load_ventures()
            runs_payload = self._load_runs()
            gates_payload = self._load_gates()
            todos_payload = self._load_loop_todos()
            deployments_payload = self._load_deployments()
            user_prompts_payload = self._load_user_prompts()

        ventures = ventures_payload.get("items", [])
        active_id = state.get("activeVentureId")
        active_venture = None
        for venture in ventures:
            if venture.get("id") == active_id:
                active_venture = venture
                break
        if not active_venture and ventures:
            active_venture = ventures[-1]
            active_id = active_venture.get("id")

        opp_id = (active_venture or {}).get("opportunityId")
        active_context = self._read_active_context(opp_id)

        runs = runs_payload.get("items", [])
        gates = gates_payload.get("items", [])
        todos = [x for x in (todos_payload.get("items") or []) if (not active_id or x.get("ventureId") == active_id)]

        recent_runs_raw = [x for x in reversed(runs) if (not active_id or x.get("ventureId") in {None, active_id})][:60]
        recent_runs = [self._summarize_run(run, include_details=include_run_details) for run in recent_runs_raw]

        latest_by_stage: Dict[str, Dict[str, Any]] = {}
        for run in recent_runs_raw:
            stage = str(run.get("stage") or "UNKNOWN")
            if stage not in latest_by_stage:
                latest_by_stage[stage] = run

        stage_narrative = {
            "IDEA_POOL": "从市场机会池中选择有潜力的 startup idea。",
            "SELECTED": "确定一个 venture 并冻结初始商业假设。",
            "PRODUCT": "产出 landing 与可演示网页（simulation/live）。",
            "MARKETING": "产出并人工选择内容与 campaign。",
            "SALES": "执行线索、外联与转化动作。",
            "OPERATIONS": "汇总指标与反馈并评估改进。",
            "ITERATE": "把运营反馈回写到下一轮待办。",
        }

        stage_flow = []
        active_stage = str((active_venture or {}).get("stage") or "IDEA_POOL")
        if active_stage not in STAGE_ORDER:
            active_stage = "IDEA_POOL"
        current_idx = STAGE_ORDER.index(active_stage)
        pending_transition = self._pending_transition(active_venture)
        pending_to_stage = str((pending_transition or {}).get("toStage") or "")
        for idx, stage in enumerate(STAGE_ORDER):
            if idx < current_idx:
                state_flag = "completed"
            elif idx == current_idx:
                state_flag = "current"
            else:
                state_flag = "pending"
            if pending_transition and stage == pending_to_stage and state_flag == "pending":
                state_flag = "awaiting_confirmation"
            last_run = latest_by_stage.get(stage)
            stage_flow.append(
                {
                    "stage": stage,
                    "state": state_flag,
                    "narrative": stage_narrative.get(stage),
                    "lastRun": self._summarize_run(last_run, include_details=False) if last_run else None,
                }
            )

        # Stage result visibility: latest artifacts + key output by stage.
        stage_results = []
        for stage in [*STAGE_ORDER, "PRECHECK", "REHEARSAL"]:
            run = latest_by_stage.get(stage)
            if not run:
                continue
            artifacts = []
            for art in run.get("artifacts") or []:
                artifacts.append(
                    {
                        "id": art.get("id"),
                        "type": art.get("type"),
                        "sourcePath": art.get("sourcePath"),
                        "snapshotPath": art.get("snapshotPath"),
                    }
                )
            stage_results.append(
                {
                    "stage": stage,
                    "run": self._summarize_run(run, include_details=False),
                    "summary": run.get("summary") or {},
                    "artifacts": artifacts,
                }
            )

        quickstart = [
            "先看顶部状态：项目、阶段、下一步。",
            "优先在“问我”里提问，再执行建议动作。",
            "每次阶段迁移都要显式确认。",
            "先 simulation，后 live；live 必须 Manual Arm + 双确认。",
        ]

        deployments = [
            x
            for x in reversed(deployments_payload.get("items") or [])
            if (not active_id or x.get("ventureId") == active_id)
        ][:30]

        vercel_audit = self._parse_json(self.runtime_dir / "studio" / "vercel_audit.latest.json", {})

        venture_context = self._read_venture_context(active_id) if active_id else {}

        cross_agent_insights = []
        for todo in todos[:20]:
            cross_agent_insights.append(
                {
                    "team": todo.get("team"),
                    "priority": todo.get("priority"),
                    "title": todo.get("title"),
                    "source": todo.get("sourceFile"),
                }
            )

        message_pack = self._build_message_pack(opp_id)
        recommended_actions = self._next_recommended_actions(active_venture, active_context)
        action_states = self._action_state_map(venture_id=active_id, recommended_actions=recommended_actions, recent_runs=recent_runs)
        global_run_state = self._global_run_state(venture_id=active_id, recent_runs=recent_runs_raw)
        stage_artifact_cards = self._build_stage_artifact_cards(stage_results, deployments)
        user_prompt_progress = self._stage_progress(active_stage)
        user_prompt_questions = self._build_user_questions(
            active_venture=active_venture,
            active_context=active_context,
            recommended_actions=recommended_actions,
            manual_arm_enabled=bool(self._manual_arm_enabled()),
        )
        user_prompt_items = user_prompts_payload.get("items") or []
        if active_id:
            user_prompt_items = [x for x in user_prompt_items if x.get("ventureId") in {None, active_id}]
        else:
            user_prompt_items = [x for x in user_prompt_items if x.get("ventureId") is None]
        user_prompt_history = list(reversed(user_prompt_items[-8:]))

        vercel_audit_summary = {
            "generatedAt": vercel_audit.get("generatedAt"),
            "ok": vercel_audit.get("ok"),
            "projectCount": vercel_audit.get("projectCount"),
            "keep": len(((vercel_audit.get("classified") or {}).get("keep") or [])),
            "review": len(((vercel_audit.get("classified") or {}).get("review") or [])),
            "cleanupCandidates": len(((vercel_audit.get("classified") or {}).get("cleanupCandidates") or [])),
            "reportPath": "dashboard/.runtime/studio/vercel_audit.latest.json" if vercel_audit else None,
        }

        return {
            "generatedAt": now_iso(),
            "ideas": self.list_ideas(),
            "ventures": ventures,
            "activeVentureId": active_id,
            "activeVenture": active_venture,
            "pendingTransition": self._pending_transition(active_venture),
            "activeContext": active_context,
            "ventureContext": venture_context,
            "stageFlow": stage_flow,
            "stageResults": stage_results,
            "stageArtifactCards": stage_artifact_cards,
            "recentRuns": recent_runs,
            "recentGates": [x for x in reversed(gates) if (not active_id or x.get("ventureId") == active_id)][:40],
            "loopTodos": todos[:100],
            "deployments": deployments,
            "crossAgentInsights": cross_agent_insights,
            "goToMarketPreview": self._build_go_to_market_preview(opp_id),
            "messagePack": message_pack,
            "capabilitySummary": self._capability_summary(monitor_snapshot),
            "jobs": self.list_jobs(include_result=False),
            "vercel": self._vercel_status(),
            "vercelAuditSummary": vercel_audit_summary,
            "manualArmEnabled": bool(self._manual_arm_enabled()),
            "monitor": monitor_snapshot,
            "stateMachine": STAGE_ORDER,
            "globalRunState": global_run_state,
            "guide": {
                "quickstart": quickstart,
                "nextRecommendedActions": recommended_actions,
                "primaryRecommendedAction": recommended_actions[0] if recommended_actions else None,
                "actionStates": action_states,
            },
            "userPromptPanel": {
                "progress": user_prompt_progress,
                "pendingTransition": pending_transition,
                "pendingQuestions": user_prompt_questions,
                "history": user_prompt_history,
                "placeholder": "问我：现在到哪一步？下一步做什么？这轮活动为什么没转化？",
            },
        }
