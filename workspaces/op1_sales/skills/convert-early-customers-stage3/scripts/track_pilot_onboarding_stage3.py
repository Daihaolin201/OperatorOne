#!/usr/bin/env python3
"""Build Stage3 pilot onboarding tracker and TTFV monitor."""

from __future__ import annotations

import argparse
import statistics
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from conversion_stage3_common import (  # noqa: E402
    STAGE_RANK,
    find_repo_root,
    now_iso,
    now_utc,
    parse_iso,
    read_json,
    read_jsonl,
    stage_rank,
    write_json,
)


def _pilot_stage_progress(stage: str, task_count: int) -> int:
    mapping = {
        "pilot_offered": 0,
        "pilot_active": min(2, task_count),
        "pilot_value_confirmed": min(3, task_count),
        "commercial_terms_sent": min(4, task_count),
        "commitment_received": min(4, task_count),
        "paid_started": task_count,
    }
    return mapping.get(stage, 0)


def _stage_time(lead: Dict[str, Any], target_stage: str) -> str:
    for h in lead.get("stage_history", []) or []:
        if str(h.get("stage", "")) == target_stage:
            return str(h.get("entered_at", ""))
    return ""


def _write_md(path: Path, payload: Dict[str, Any]) -> None:
    summary = payload.get("summary", {})
    pilots = payload.get("pilots", [])

    lines = [
        "# Pilot Onboarding Tracker (Stage3 latest)",
        "",
        f"Generated at: {payload.get('generated_at', '')}",
        "",
        "## Summary",
        f"- Pilot candidates: {summary.get('pilot_candidates', 0)}",
        f"- Pilot active: {summary.get('pilot_active', 0)}",
        f"- Value confirmed: {summary.get('value_confirmed', 0)}",
        f"- At risk: {summary.get('at_risk', 0)}",
        f"- Median TTFV hours: {summary.get('median_ttfv_hours', 0)}",
        "",
        "## Pilot table",
        "",
        "| Lead ID | Stage | Started | First value | TTFV(h) | Risk | Next rescue action |",
        "|---|---|---|---|---:|---|---|",
    ]

    for p in pilots:
        rescue = " / ".join(p.get("rescue_actions", [])[:1])
        lines.append(
            f"| {p.get('lead_id','')} | {p.get('current_stage','')} | {p.get('pilot_started_at','')} | {p.get('first_value_at','')} | {p.get('ttfv_hours', 0)} | {p.get('onboarding_risk','')} | {rescue} |"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Track Stage3 pilot onboarding")
    p.add_argument("--repo-root", type=str, default="", help="OperatorOne repo root")
    p.add_argument("--out-dir", type=str, default="", help="Output dir (default: research/conversion)")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    out_dir = Path(args.out_dir).resolve() if args.out_dir else repo_root / "workspaces" / "op1_sales" / "research" / "conversion"
    out_dir.mkdir(parents=True, exist_ok=True)

    pipeline = read_json(out_dir / "conversion_pipeline.latest.json")
    conversion_events = read_jsonl(out_dir / "conversion_events.latest.jsonl")
    blueprint = read_json(repo_root / "workspaces" / "op1_product" / "research" / "stage3_mvp_scope" / "project_blueprint.json")

    manual_steps = ((blueprint.get("downstream_inputs", {}) or {}).get("operations", {}) or {}).get("manual_steps", []) or []
    if not manual_steps:
        manual_steps = [
            "Collect pilot input data",
            "Run first action queue",
            "Capture first value evidence",
            "Review outcomes and adjust playbook",
            "Prepare commercial handoff",
        ]

    leads = pipeline.get("leads", []) or []

    # Index event timestamps by lead and type.
    ev_idx: Dict[str, Dict[str, List[str]]] = {}
    for ev in conversion_events:
        lead_id = str(ev.get("lead_id", "")).strip()
        et = str(ev.get("event_type", "")).strip()
        ts = str(ev.get("ts", "")).strip()
        if not lead_id or not et or not ts:
            continue
        ev_idx.setdefault(lead_id, {}).setdefault(et, []).append(ts)

    pilots: List[Dict[str, Any]] = []
    ttfv_values: List[float] = []

    for lead in leads:
        stage = str(lead.get("current_stage", ""))
        if stage_rank(stage) < stage_rank("pilot_offered"):
            continue
        if stage == "closed_lost":
            continue

        lead_id = str(lead.get("lead_id", ""))
        lead_events = ev_idx.get(lead_id, {})

        started_candidates = list(lead_events.get("pilot_started", []))
        if not started_candidates:
            sh = _stage_time(lead, "pilot_active")
            if sh:
                started_candidates.append(sh)
            elif stage_rank(stage) >= stage_rank("pilot_active"):
                started_candidates.append(str(lead.get("stage_entered_at", "")))

        first_value_candidates = list(lead_events.get("pilot_value_confirmed", []))
        if not first_value_candidates:
            sh = _stage_time(lead, "pilot_value_confirmed")
            if sh:
                first_value_candidates.append(sh)

        pilot_started_at = sorted([x for x in started_candidates if x])[:1]
        first_value_at = sorted([x for x in first_value_candidates if x])[:1]
        pilot_started_at_str = pilot_started_at[0] if pilot_started_at else ""
        first_value_at_str = first_value_at[0] if first_value_at else ""

        progress = _pilot_stage_progress(stage, len(manual_steps))
        tasks = []
        for idx, step in enumerate(manual_steps, start=1):
            if idx <= progress:
                status = "done"
            elif idx == progress + 1 and stage == "pilot_active":
                status = "in_progress"
            else:
                status = "pending"
            tasks.append(
                {
                    "task_id": f"task_{idx:02d}",
                    "label": step,
                    "status": status,
                }
            )

        ttfv_hours = 0.0
        risk = "none"
        rescue_actions: List[str] = []

        started_dt = parse_iso(pilot_started_at_str)
        first_dt = parse_iso(first_value_at_str)

        if started_dt and first_dt and first_dt >= started_dt:
            ttfv_hours = round((first_dt - started_dt).total_seconds() / 3600.0, 2)
            ttfv_values.append(ttfv_hours)

        if stage == "pilot_active":
            if started_dt and not first_dt:
                age_h = (now_utc() - started_dt).total_seconds() / 3600.0
                if age_h >= 72:
                    risk = "high"
                    rescue_actions = [
                        "安排30分钟救援会：缩小试点范围到单一高价值场景",
                        "在24小时内给出首个可见结果样例",
                        "与决策人确认继续/暂停门槛",
                    ]
                elif age_h >= 48:
                    risk = "medium"
                    rescue_actions = [
                        "提前触发中期复盘并检查阻塞项",
                    ]

        pilot = {
            "lead_id": lead_id,
            "opportunity_id": lead.get("opportunity_id", ""),
            "current_stage": stage,
            "pilot_started_at": pilot_started_at_str,
            "first_value_at": first_value_at_str,
            "ttfv_hours": ttfv_hours,
            "onboarding_risk": risk,
            "rescue_actions": rescue_actions,
            "tasks": tasks,
            "assumptions": [
                "TTFV以可验证价值事件记录为准。",
                "若缺少真实事件，状态按阶段推断并标注风险。",
            ],
        }
        pilots.append(pilot)

    pilots.sort(key=lambda x: (str(x.get("onboarding_risk", "")) != "high", str(x.get("lead_id", ""))))

    summary = {
        "pilot_candidates": len(pilots),
        "pilot_active": sum(1 for x in pilots if x.get("current_stage") == "pilot_active"),
        "value_confirmed": sum(1 for x in pilots if stage_rank(str(x.get("current_stage", ""))) >= stage_rank("pilot_value_confirmed")),
        "at_risk": sum(1 for x in pilots if x.get("onboarding_risk") in {"high", "medium"}),
        "median_ttfv_hours": round(statistics.median(ttfv_values), 2) if ttfv_values else 0.0,
    }

    payload = {
        "generated_at": now_iso(),
        "builder": "workspaces/op1_sales/scripts/track_pilot_onboarding_stage3.py",
        "inputs": {
            "conversion_pipeline": "workspaces/op1_sales/research/conversion/conversion_pipeline.latest.json",
            "conversion_events": "workspaces/op1_sales/research/conversion/conversion_events.latest.jsonl",
            "blueprint": "workspaces/op1_product/research/stage3_mvp_scope/project_blueprint.json",
        },
        "summary": summary,
        "pilots": pilots,
    }

    out_json = out_dir / "pilot_onboarding.latest.json"
    out_md = out_dir / "pilot_onboarding.latest.md"
    write_json(out_json, payload)
    _write_md(out_md, payload)

    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
