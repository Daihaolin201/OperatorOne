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
}


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
            ad_copy = top_campaign.get("ad_copy") or top_campaign.get("copy") or top_campaign.get("hook")
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
                "snippet": (top_content or {}).get("summary") if isinstance(top_content, dict) else None,
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

        mode = str(payload.get("mode") or "simulation").strip().lower()
        if mode not in {"simulation", "live"}:
            raise StudioError("mode must be simulation or live")

        confirm_live = bool(payload.get("confirmLive", False))
        dry_run = bool(payload.get("dryRun", False))
        deploy_target = str(payload.get("deployTarget") or "preview").strip().lower()
        if deploy_target not in {"preview", "production"}:
            raise StudioError("deployTarget must be preview or production")

        venture = self._require_venture(venture_id)
        opp_id = venture.get("opportunityId")
        if not opp_id:
            raise StudioError("venture opportunityId missing")

        vercel_project = self._vercel_project_name_for_venture(venture)
        commit_sha = self._git_commit_sha()

        steps: List[Dict[str, Any]] = []

        step_landing = self._command_step(
            "create_landing_pages",
            ["bash", "scripts/run_create_landing_pages_v1.sh", "--opp-id", str(opp_id)],
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
            if not self._manual_arm_enabled():
                raise StudioError("manual arm is OFF; cannot run live product deployment")
            if deploy_target == "production" and not bool(payload.get("confirmProduction", False)):
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
                        "stage": "PRODUCT",
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
                self._sync_venture_context(venture_id)
                return {"run": run, "venture": updated}

            step_build = self._command_step(
                "build_and_deploy",
                [
                    "bash",
                    "scripts/run_build_deploy_v1.sh",
                    "--opp-id",
                    str(opp_id),
                    "--allow-spec-autogen",
                    "--vercel-project",
                    vercel_project,
                    "--deploy-target",
                    deploy_target,
                ],
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

        summary = {
            "opportunityId": opp_id,
            "deploymentUrl": deployment_url,
            "previewPath": preview_path,
            "vercelProject": vercel_project,
            "deployTarget": deploy_target,
            "dryRun": dry_run,
            "commit": commit_sha,
        }

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
                "stage": "MARKETING",
                "links": {
                    **(v.get("links") or {}),
                    "productDeploymentUrl": deployment_url,
                    "productPreviewPath": preview_path,
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
                    },
                },
            },
        )

        self._sync_venture_context(venture_id)
        return {"run": run, "venture": updated}

    def _action_run_marketing_seo(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

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

        mode = str(payload.get("mode") or "shadow").strip().lower()
        if mode not in {"shadow", "review"}:
            raise StudioError("marketing content mode must be shadow or review")

        step = self._command_step(
            "marketing_stage2_content",
            ["python3", "scripts/run_marketing_content_stage2.py", "--mode", mode, "--force", "--print-summary"],
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
        self._sync_venture_context(venture_id)
        return {"run": run, "venture": updated}

    def _action_review_marketing_content(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

        approve_ids = [str(x).strip() for x in (payload.get("approveIds") or []) if str(x).strip()]
        reject_ids = [str(x).strip() for x in (payload.get("rejectIds") or []) if str(x).strip()]
        note = str(payload.get("note") or "studio_review")
        reason = str(payload.get("reason") or "manual_review_requested_changes")

        if not approve_ids and not reject_ids:
            raise StudioError("provide approveIds or rejectIds")

        cmd = ["python3", "scripts/review_marketing_content_stage2.py", "--print-summary", "--note", note, "--reason", reason]
        for cid in approve_ids:
            cmd.extend(["--approve", cid])
        for cid in reject_ids:
            cmd.extend(["--reject", cid])

        step = self._command_step("marketing_stage2_review", cmd, cwd=self.marketing_dir, timeout=1200)
        if step["status"] != "passed":
            self._record_run(
                venture_id=venture_id,
                stage="MARKETING",
                action="review_marketing_content",
                mode="review",
                status="failed",
                steps=[step],
                artifacts=[],
                summary={},
                error=step["stderrTail"][-500:],
            )
            raise StudioError(f"Marketing content review failed: {step['stderrTail'][:300]}")

        artifacts = self._copy_artifacts(
            venture_id=venture_id,
            stage="MARKETING",
            run_id=f"marketing_review_{now_dt().strftime('%Y%m%d%H%M%S')}",
            paths=[
                self.marketing_dir / "research/stage2_content_publish/review_log.latest.json",
                self.marketing_dir / "research/stage2_content_publish/publish.queue.latest.json",
                self.repo_root / "handoffs/marketing_to_sales.json",
            ],
        )

        run = self._record_run(
            venture_id=venture_id,
            stage="MARKETING",
            action="review_marketing_content",
            mode="review",
            status="passed",
            steps=[step],
            artifacts=artifacts,
            summary={"approved": approve_ids, "rejected": reject_ids},
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
                },
            },
        )

        self._sync_venture_context(venture_id)
        return {"run": run, "venture": updated}

    def _action_run_marketing_campaign(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

        mode = str(payload.get("mode") or "shadow").strip().lower()
        if mode not in {"shadow", "review"}:
            raise StudioError("marketing campaign mode must be shadow or review")

        step = self._command_step(
            "marketing_stage3_campaign",
            ["python3", "scripts/run_marketing_campaign_stage3.py", "--mode", mode, "--force", "--print-summary"],
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
        }

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
                "stage": "SALES" if fallback_to_sales else "MARKETING",
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
                    "marketing_stage3_no_launchable_assets -> moved to SALES fallback"
                    if fallback_to_sales
                    else "marketing_stage3_candidates_ready",
                ],
            },
        )
        self._sync_venture_context(venture_id)
        return {"run": run, "venture": updated}

    def _action_select_marketing_campaign(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        campaign_id = str(payload.get("campaignId") or "").strip()
        if not venture_id or not campaign_id:
            raise StudioError("ventureId and campaignId are required")

        updated = self._update_venture(
            venture_id,
            lambda v: {
                **v,
                "stage": "SALES",
                "selections": {
                    **(v.get("selections") or {}),
                    "campaignId": campaign_id,
                },
            },
        )

        self._append_gate(
            {
                "gateId": f"gate_{uuid.uuid4().hex[:10]}",
                "ventureId": venture_id,
                "stage": "MARKETING",
                "decision": "approved",
                "reason": f"campaign_selected:{campaign_id}",
                "decidedAt": now_iso(),
            }
        )
        self._sync_venture_context(venture_id)
        return {"venture": updated}

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

        self._sync_venture_context(venture_id)
        return {"run": run, "venture": updated}

    def _action_run_sales_outreach_plan(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")
        venture = self._require_venture(venture_id)

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

        self._sync_venture_context(venture_id)
        return {"run": run, "venture": updated}

    def _action_approve_sales_outreach(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

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
        self._sync_venture_context(venture_id)
        return {"run": run, "venture": updated}

    def _action_dispatch_sales_outreach(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

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
        self._sync_venture_context(venture_id)
        return {"run": run, "venture": updated}

    def _action_run_sales_conversion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

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

        run = self._record_run(
            venture_id=venture_id,
            stage="SALES",
            action="run_sales_conversion",
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
                "stage": "OPERATIONS",
                "lastActions": {
                    **(v.get("lastActions") or {}),
                    "salesConversion": {"runId": run["id"], "at": now_iso(), "mode": mode},
                },
            },
        )
        self._sync_venture_context(venture_id)
        return {"run": run, "venture": updated}

    def _action_run_operations_full(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

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

        run = self._record_run(
            venture_id=venture_id,
            stage="OPERATIONS",
            action="run_operations_full",
            mode="simulation",
            status="passed",
            steps=steps,
            artifacts=artifacts,
            summary={},
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

        updated = self._update_venture(
            venture_id,
            lambda v: {
                **v,
                "stage": "ITERATE",
                "kpiSnapshots": [*(v.get("kpiSnapshots") or []), kpi][-30:],
                "lastActions": {
                    **(v.get("lastActions") or {}),
                    "operationsFull": {"runId": run["id"], "at": now_iso()},
                },
            },
        )

        return {"run": run, "venture": updated, "kpiSnapshot": kpi}

    def _action_writeback_operations(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

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
                "stage": "ITERATE",
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

        self._sync_venture_context(venture_id)
        return {"run": run, "venture": updated, "todos": todos, "suggestions": suggestions}

    def _action_confirm_iterate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        note = str(payload.get("note") or "confirm_next_cycle")
        if not venture_id:
            raise StudioError("ventureId is required")

        updated = self._update_venture(
            venture_id,
            lambda v: {
                **v,
                "stage": "PRODUCT",
                "cycle": int(v.get("cycle", 1) or 1) + 1,
                "status": "active",
                "lastActions": {
                    **(v.get("lastActions") or {}),
                    "iterateConfirm": {"at": now_iso(), "note": note},
                },
            },
        )

        self._append_gate(
            {
                "gateId": f"gate_{uuid.uuid4().hex[:10]}",
                "ventureId": venture_id,
                "stage": "ITERATE",
                "decision": "approved",
                "reason": note,
                "decidedAt": now_iso(),
            }
        )

        self._sync_venture_context(venture_id)
        return {"venture": updated}

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

        if not preview_ref:
            for dep in deployments:
                if dep.get("previewPath"):
                    preview_ref = dep.get("previewPath")
                    break
        if not build_report:
            fallback_build = self.product_dir / "research/stage2_web_product/run.latest.json"
            if fallback_build.exists():
                build_report = str(fallback_build.relative_to(self.repo_root))

        product_items = [
            url_item("Open Deployment", product_summary.get("deploymentUrl")),
            preview_item("Open Preview", preview_ref),
            file_item("Open Build Report", build_report),
            url_item("Open in Vercel", f"https://vercel.com/dashboard/projects/{product_summary.get('vercelProject')}" if product_summary.get("vercelProject") else None),
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
                        "label": "确认进入下一轮",
                        "description": "人工确认后回到 Product 阶段。",
                        "stage": "ITERATE",
                        "payload": {"action": "confirm_iterate", "ventureId": vid, "async": False},
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

    def _run_action_sync(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        dispatch = {
            "refresh_ideas": self._action_refresh_ideas,
            "create_venture": self._action_create_venture,
            "set_active_venture": self._action_set_active_venture,
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
            "stage_preflight": self._action_stage_preflight,
            "rehearsal_e2e": self._action_rehearsal_e2e,
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
        for idx, stage in enumerate(STAGE_ORDER):
            if idx < current_idx:
                state_flag = "completed"
            elif idx == current_idx:
                state_flag = "current"
            else:
                state_flag = "pending"
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
            "先看 Judge Mode 顶部：当前项目、阶段、产物入口、下一步动作。",
            "点击“运行演示前预检查”，确认合同与环境都通过。",
            "先走 simulation 全流程，再决定是否 live。",
            "live 仅在 Manual Arm ON + 显式确认后执行。",
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
        }
