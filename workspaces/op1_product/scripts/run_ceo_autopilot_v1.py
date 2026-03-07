#!/usr/bin/env python3
"""Run a minimal CEO autopilot sequence on top of existing op1_product stage scripts.

v1.1 adds:
- human approval checkpoint before external actions (build/deploy + landing)
- stage2 adapter fallback retries
- auditable state transitions in venture_state
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "research" / "ceo_orchestration"
RUN_PATH = OUT_DIR / "run.latest.json"
STATE_PATH = OUT_DIR / "venture_state.latest.json"
APPROVAL_PATH = OUT_DIR / "approval.json"


@dataclass
class StepResult:
    name: str
    command: List[str]
    ok: bool
    code: int
    started_at: str
    finished_at: str
    duration_sec: float
    stdout_tail: str
    stderr_tail: str
    meta: Dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def run_step(name: str, cmd: List[str], dry_run: bool = False, meta: Optional[Dict[str, Any]] = None) -> StepResult:
    started = datetime.now(timezone.utc)
    meta = meta or {}
    if dry_run:
        return StepResult(
            name=name,
            command=cmd,
            ok=True,
            code=0,
            started_at=started.isoformat(),
            finished_at=utc_now(),
            duration_sec=0.0,
            stdout_tail="[dry-run] not executed",
            stderr_tail="",
            meta=meta,
        )

    proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
    finished = datetime.now(timezone.utc)
    duration = (finished - started).total_seconds()
    return StepResult(
        name=name,
        command=cmd,
        ok=(proc.returncode == 0),
        code=proc.returncode,
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        duration_sec=duration,
        stdout_tail=(proc.stdout or "")[-1500:],
        stderr_tail=(proc.stderr or "")[-1500:],
        meta=meta,
    )


def detect_advance_opportunity() -> Optional[str]:
    scoring_path = ROOT / "research" / "stage2_idea_screening" / "scoring.csv"
    if not scoring_path.exists():
        return None

    try:
        with scoring_path.open("r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except Exception:
        return None

    if not rows:
        return None

    rows.sort(key=lambda r: float(r.get("final_score") or 0), reverse=True)
    top = rows[0]
    for key in ["opportunity_id", "id", "opp_id"]:
        val = (top.get(key) or "").strip()
        if val:
            return val
    return None


def detect_deploy_url() -> Optional[str]:
    """Detect deploy URL with 4-path fallback: output.deployed_url -> output.deploy_url -> deploy_url -> deployed_url.
    
    Returns the first non-empty URL found, or None if all paths are empty.
    """
    run_payload = read_json(ROOT / "research" / "stage2_web_product" / "run.latest.json", {})
    if not isinstance(run_payload, dict):
        return None

    # Priority order for URL detection:
    # 1. output.deployed_url (preferred, used by stage2_web_product/run.latest.json)
    # 2. output.deploy_url (alternative output format)
    # 3. deploy_url (legacy top-level format)
    # 4. deployed_url (legacy alternative)
    output = run_payload.get("output") if isinstance(run_payload.get("output"), dict) else {}
    
    candidates = [
        output.get("deployed_url"),
        output.get("deploy_url"),
        run_payload.get("deploy_url"),
        run_payload.get("deployed_url"),
    ]
    
    # For backward compatibility, also check artifacts dict
    artifacts = run_payload.get("artifacts") if isinstance(run_payload.get("artifacts"), dict) else {}
    candidates.extend([artifacts.get("deploy_url"), artifacts.get("deployment_url")])

    for c in candidates:
        if isinstance(c, str) and c.strip().startswith("http"):
            return c.strip()
    return None


def load_adapter_fallbacks() -> List[str]:
    default = ["invoice-followup", "chargeback-response", "client-reporting"]
    rules = read_json(ROOT / "framework" / "ceo" / "orchestration_rules.v1.json", {})
    fallbacks = rules.get("stage2_adapter_fallback_order") if isinstance(rules, dict) else None
    if isinstance(fallbacks, list):
        normalized = [str(x).strip() for x in fallbacks if str(x).strip()]
        if normalized:
            return normalized
    return default


def approval_granted(approval_file: Path) -> bool:
    payload = read_json(approval_file, {})
    return bool(isinstance(payload, dict) and payload.get("approve_external_actions") is True)


def run_stage2_with_fallbacks(opp_id: Optional[str], dry_run: bool, max_retries: int) -> StepResult:
    adapters = load_adapter_fallbacks()[: max(1, max_retries)]
    attempts: List[StepResult] = []

    for adapter in adapters:
        cmd = ["bash", "scripts/run_build_deploy_v1.sh"]
        if opp_id:
            cmd.extend(["--opp-id", opp_id])
        cmd.extend(["--adapter", adapter])

        step = run_step(
            name="stage2_web_build_deploy",
            cmd=cmd,
            dry_run=dry_run,
            meta={"adapter": adapter},
        )
        attempts.append(step)
        if step.ok:
            break

    winner = attempts[-1]
    winner.meta = dict(winner.meta)
    winner.meta["attempts"] = [
        {"adapter": a.meta.get("adapter"), "ok": a.ok, "code": a.code} for a in attempts
    ]
    return winner


def build_venture_state(
    goal: str,
    target_mrr: int,
    max_days: int,
    max_spend: int,
    steps: List[StepResult],
    approval_required: bool,
    approval_ok: bool,
) -> Dict[str, Any]:
    selected = detect_advance_opportunity()
    deploy_url = detect_deploy_url()

    stage = "stage3_landing"
    status = "completed"
    if any(not s.ok for s in steps):
        status = "failed"
        for s in steps:
            if not s.ok:
                stage = s.name
                break

    if approval_required and not approval_ok:
        stage = "approval_pending_external"
        status = "waiting_approval"

    go_to_build = bool(selected)
    go_to_landing = bool(deploy_url)

    return {
        "venture_id": f"venture_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "goal": goal,
        "constraints": {
            "target_mrr_usd": target_mrr,
            "max_days": max_days,
            "max_cash_spend_usd": max_spend,
        },
        "state_machine": "framework/ceo/state_machine.v1.json",
        "stage": stage,
        "status": status,
        "selected_opportunity_id": selected,
        "deploy_url": deploy_url,
        "approval": {
            "required": approval_required,
            "granted": approval_ok,
            "approval_file": str(APPROVAL_PATH.relative_to(ROOT)),
        },
        "gates": {
            "go_to_build": {
                "pass": go_to_build,
                "reason": "top opportunity detected in scoring.csv" if go_to_build else "no scored opportunity detected",
            },
            "go_to_landing": {
                "pass": go_to_landing,
                "reason": "deploy url detected in stage2 run artifact" if go_to_landing else "missing deploy url in stage2 artifact",
            },
        },
        "next_actions": [
            "Review landing copy and CTA quality",
            "Run first distribution experiment",
            "Record first 10 user conversations",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CEO autopilot v1")
    parser.add_argument("--goal", default="Reach first $100 MRR with disciplined experimentation")
    parser.add_argument("--target-mrr", type=int, default=100)
    parser.add_argument("--max-days", type=int, default=14)
    parser.add_argument("--max-spend", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--require-approval", dest="require_approval", action="store_true", default=True)
    parser.add_argument("--no-require-approval", dest="require_approval", action="store_false")
    parser.add_argument("--approval-file", default=str(APPROVAL_PATH))
    parser.add_argument("--max-stage2-retries", type=int, default=3)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    steps: List[StepResult] = []

    # Stage1
    s1 = run_step("stage1_idea_discovery", ["bash", "scripts/run_generate_startup_ideas.sh"], dry_run=args.dry_run)
    steps.append(s1)

    selected = detect_advance_opportunity()
    go_to_build = bool(selected)

    approval_file = Path(args.approval_file)
    approval_ok = args.dry_run or (not args.require_approval) or approval_granted(approval_file)

    if s1.ok and go_to_build and approval_ok:
        s2 = run_stage2_with_fallbacks(opp_id=selected, dry_run=args.dry_run, max_retries=args.max_stage2_retries)
        steps.append(s2)

        if s2.ok:
            s3 = run_step("stage3_landing", ["bash", "scripts/run_create_landing_pages_v1.sh"], dry_run=args.dry_run)
            steps.append(s3)
    elif s1.ok and not go_to_build:
        steps.append(
            StepResult(
                name="stage2_web_build_deploy",
                command=[],
                ok=False,
                code=2,
                started_at=utc_now(),
                finished_at=utc_now(),
                duration_sec=0.0,
                stdout_tail="skipped: go_to_build gate failed",
                stderr_tail="",
                meta={"skipped": True},
            )
        )
    elif s1.ok and go_to_build and not approval_ok:
        steps.append(
            StepResult(
                name="approval_pending_external",
                command=[],
                ok=True,
                code=0,
                started_at=utc_now(),
                finished_at=utc_now(),
                duration_sec=0.0,
                stdout_tail=f"waiting approval: set approve_external_actions=true in {approval_file}",
                stderr_tail="",
                meta={"waitingApproval": True},
            )
        )

    venture_state = build_venture_state(
        goal=args.goal,
        target_mrr=args.target_mrr,
        max_days=args.max_days,
        max_spend=args.max_spend,
        steps=steps,
        approval_required=args.require_approval,
        approval_ok=approval_ok,
    )

    run_payload = {
        "contract": "ceo_orchestration.v1",
        "generated_at": utc_now(),
        "input": {
            "goal": args.goal,
            "constraints": {
                "target_mrr_usd": args.target_mrr,
                "max_days": args.max_days,
                "max_cash_spend_usd": args.max_spend,
            },
            "dry_run": args.dry_run,
            "require_approval": args.require_approval,
            "approval_file": str(approval_file),
            "max_stage2_retries": args.max_stage2_retries,
        },
        "summary": {
            "status": venture_state["status"],
            "selected_opportunity_id": venture_state.get("selected_opportunity_id"),
            "deploy_url": venture_state.get("deploy_url"),
            "approval": venture_state.get("approval"),
        },
        "steps": [
            {
                "name": s.name,
                "command": s.command,
                "ok": s.ok,
                "code": s.code,
                "started_at": s.started_at,
                "finished_at": s.finished_at,
                "duration_sec": s.duration_sec,
                "stdout_tail": s.stdout_tail,
                "stderr_tail": s.stderr_tail,
                "meta": s.meta,
            }
            for s in steps
        ],
    }

    RUN_PATH.write_text(json.dumps(run_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    STATE_PATH.write_text(json.dumps(venture_state, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "run": str(RUN_PATH.relative_to(ROOT)),
                "state": str(STATE_PATH.relative_to(ROOT)),
                "status": venture_state.get("status"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
