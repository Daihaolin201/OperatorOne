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

from collector import collect_snapshot


STAGE_ORDER = [
    "IDEA_POOL",
    "SELECTED",
    "PRODUCT",
    "MARKETING",
    "SALES",
    "OPERATIONS",
    "ITERATE",
]

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

        self.state_path = self.studio_dir / "state.json"
        self.ventures_path = self.studio_dir / "ventures.json"
        self.runs_path = self.studio_dir / "stage_runs.json"
        self.gates_path = self.studio_dir / "decision_gates.json"
        self.loop_todos_path = self.studio_dir / "loop_todos.json"

        self.flags_path = self.runtime_dir / "state.json"  # shared with monitor gate

        self.product_dir = self.repo_root / "workspaces" / "op1_product"
        self.marketing_dir = self.repo_root / "workspaces" / "op1_marketing"
        self.sales_dir = self.repo_root / "workspaces" / "op1_sales"
        self.operations_dir = self.repo_root / "workspaces" / "op1_operations"

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

        if not self.state_path.exists():
            self._write_json(
                self.state_path,
                {
                    "activeVentureId": None,
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

        ideas.sort(key=lambda x: float(x.get("feasibilityScore") or 0.0), reverse=True)
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

        return venture

    def set_active_venture(self, venture_id: str) -> Dict[str, Any]:
        venture = self._require_venture(venture_id)
        with self.store_lock:
            state = self._load_state()
            state["activeVentureId"] = venture["id"]
            self._save_state(state)
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

    def list_jobs(self) -> List[Dict[str, Any]]:
        with self.jobs_lock:
            items = [copy.deepcopy(v) for v in self.jobs.values()]
        items.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
        return items[:100]

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self.jobs_lock:
            item = self.jobs.get(job_id)
            return copy.deepcopy(item) if item else None

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
                stage1_ready.append(item)

        marketing_stage2 = self._parse_json(
            self.marketing_dir / "research/stage2_content_publish/publish.queue.latest.json",
            {},
        )
        content_candidates = []
        for bucket in ["approved", "review_ready", "needs_revision", "blocked"]:
            for item in ((marketing_stage2.get("queue") or {}).get(bucket) or []):
                if item_matches_opp(item, opp_id):
                    row = copy.deepcopy(item)
                    row["_bucket"] = bucket
                    content_candidates.append(row)

        marketing_stage3 = self._parse_json(
            self.marketing_dir / "research/stage3_campaign_launch/campaigns.queue.latest.json",
            {},
        )
        campaign_candidates = []
        for bucket in ["launch_ready", "watchlist", "hold"]:
            for item in ((marketing_stage3.get("queue") or {}).get(bucket) or []):
                if item_matches_opp(item, opp_id):
                    row = copy.deepcopy(item)
                    row["_bucket"] = bucket
                    campaign_candidates.append(row)

        prospect_queue = self._parse_json(
            self.sales_dir / "research/prospecting/prospect_queue.latest.json",
            {},
        )
        segments = []
        for idx, seg in enumerate(prospect_queue.get("segments") or []):
            if item_matches_opp(seg, opp_id):
                row = copy.deepcopy(seg)
                row["segmentIndex"] = idx
                segments.append(row)

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

        return {
            "marketing": {
                "stage1Ready": stage1_ready[:50],
                "contentCandidates": content_candidates[:100],
                "campaignCandidates": campaign_candidates[:100],
            },
            "sales": {
                "segments": segments[:20],
                "outreachBatchReady": outreach_ready,
                "outreachDispatch": outreach_dispatch,
                "closeMotion": close_motion,
            },
            "operations": {
                "stage1Scoreboard": ops_stage1,
                "stage2Scoreboard": ops_stage2,
                "stage3Scoreboard": ops_stage3,
            },
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _action_refresh_ideas(self, payload: Dict[str, Any]) -> Dict[str, Any]:
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

        run = self._record_run(
            venture_id=None,
            stage="IDEA_POOL",
            action="refresh_ideas",
            mode="simulation",
            status=status,
            steps=[step],
            artifacts=artifacts,
            summary={"ideasCount": len(self.list_ideas())},
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

    def _action_run_product(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        venture_id = str(payload.get("ventureId") or "").strip()
        if not venture_id:
            raise StudioError("ventureId is required")

        mode = str(payload.get("mode") or "simulation").strip().lower()
        if mode not in {"simulation", "live"}:
            raise StudioError("mode must be simulation or live")

        confirm_live = bool(payload.get("confirmLive", False))

        venture = self._require_venture(venture_id)
        opp_id = venture.get("opportunityId")
        if not opp_id:
            raise StudioError("venture opportunityId missing")

        steps: List[Dict[str, Any]] = []

        step_landing = self._command_step(
            "create_landing_pages",
            ["bash", "scripts/run_create_landing_pages_v1.sh", "--opp-id", str(opp_id)],
            cwd=self.product_dir,
            timeout=1800,
        )
        steps.append(step_landing)
        if step_landing["status"] != "passed":
            run = self._record_run(
                venture_id=venture_id,
                stage="PRODUCT",
                action="run_product",
                mode=mode,
                status="failed",
                steps=steps,
                artifacts=[],
                summary={},
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

            vercel = self._vercel_status()
            if not (vercel.get("installed") and vercel.get("authenticated")):
                raise StudioError("Vercel not ready (install/login required)")

            step_build = self._command_step(
                "build_and_deploy",
                [
                    "bash",
                    "scripts/run_build_deploy_v1.sh",
                    "--opp-id",
                    str(opp_id),
                    "--allow-spec-autogen",
                ],
                cwd=self.product_dir,
                timeout=3600,
            )
            steps.append(step_build)
            if step_build["status"] != "passed":
                run = self._record_run(
                    venture_id=venture_id,
                    stage="PRODUCT",
                    action="run_product",
                    mode=mode,
                    status="failed",
                    steps=steps,
                    artifacts=[],
                    summary={},
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

        updated = self._update_venture(
            venture_id,
            lambda v: {
                **v,
                "stage": "MARKETING",
                "links": {
                    **(v.get("links") or {}),
                    "productDeploymentUrl": deployment_url,
                    "productPreviewPath": preview_path,
                },
                "lastActions": {
                    **(v.get("lastActions") or {}),
                    "product": {
                        "runId": run["id"],
                        "at": now_iso(),
                        "mode": mode,
                    },
                },
            },
        )

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

        run = self._record_run(
            venture_id=venture_id,
            stage="MARKETING",
            action="run_marketing_campaign",
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
                    "marketingCampaign": {"runId": run["id"], "at": now_iso(), "mode": mode},
                },
            },
        )
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

        run = self._record_run(
            venture_id=venture_id,
            stage="OPERATIONS",
            action="writeback_operations",
            mode="simulation",
            status="passed",
            steps=[],
            artifacts=[],
            summary={"todoCount": len(todos)},
        )

        updated = self._update_venture(
            venture_id,
            lambda v: {
                **v,
                "stage": "ITERATE",
                "lastActions": {
                    **(v.get("lastActions") or {}),
                    "operationsWriteback": {"runId": run["id"], "at": now_iso(), "todoCount": len(todos)},
                },
            },
        )

        return {"run": run, "venture": updated, "todos": todos}

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

        return {"venture": updated}

    def _run_action_sync(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        dispatch = {
            "refresh_ideas": self._action_refresh_ideas,
            "create_venture": self._action_create_venture,
            "set_active_venture": self._action_set_active_venture,
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
        }
        fn = dispatch.get(action)
        if not fn:
            raise StudioError(f"unsupported action: {action}")
        return fn(payload)

    def dispatch_action(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        action = str(payload.get("action") or "").strip()
        if not action:
            raise StudioError("action is required")

        if action in ASYNC_ACTIONS and payload.get("async", True):
            job = self._submit_job(action, payload)
            return {"ok": True, "async": True, "job": job}

        result = self._run_action_sync(action, payload)
        return {"ok": True, "async": False, "result": result}

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        with self.store_lock:
            state = self._load_state()
            ventures_payload = self._load_ventures()
            runs_payload = self._load_runs()
            gates_payload = self._load_gates()
            todos_payload = self._load_loop_todos()

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

        # Keep existing monitor snapshot for readiness + connected account status.
        monitor_flags = self._read_json(self.flags_path, {"manualArmEnabled": False})
        monitor_snapshot = collect_snapshot(runtime_flags=monitor_flags)

        runs = runs_payload.get("items", [])
        gates = gates_payload.get("items", [])
        todos = [x for x in (todos_payload.get("items") or []) if (not active_id or x.get("ventureId") == active_id)]

        return {
            "generatedAt": now_iso(),
            "ideas": self.list_ideas(),
            "ventures": ventures,
            "activeVentureId": active_id,
            "activeVenture": active_venture,
            "activeContext": active_context,
            "recentRuns": [x for x in reversed(runs) if (not active_id or x.get("ventureId") in {None, active_id})][:40],
            "recentGates": [x for x in reversed(gates) if (not active_id or x.get("ventureId") == active_id)][:40],
            "loopTodos": todos[:100],
            "jobs": self.list_jobs(),
            "vercel": self._vercel_status(),
            "manualArmEnabled": bool(monitor_flags.get("manualArmEnabled", False)),
            "monitor": monitor_snapshot,
            "stateMachine": STAGE_ORDER,
        }
