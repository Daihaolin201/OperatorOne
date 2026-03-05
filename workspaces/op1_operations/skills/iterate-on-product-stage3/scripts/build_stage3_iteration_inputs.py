#!/usr/bin/env python3
"""Build standardized Stage3 iteration inputs from Stage1/2/Product artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from stage3_iteration_common import (
    now_iso,
    read_json,
    resolve_repo_root,
    to_float,
    to_int,
    write_json,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Stage3 iteration inputs")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root")
    p.add_argument(
        "--out-dir",
        default="workspaces/op1_operations/research/stage3_product_iteration",
        help="Output directory (repo relative)",
    )
    p.add_argument(
        "--adapters-config",
        default="workspaces/op1_operations/config/stage3_iteration_adapters.v1.json",
        help="Stage3 iteration adapters config path",
    )
    p.add_argument(
        "--stage1-scoreboard",
        default="workspaces/op1_operations/research/stage1_tracking/stage1_scoreboard.latest.json",
        help="Stage1 scoreboard path",
    )
    p.add_argument(
        "--stage2-scoreboard",
        default="workspaces/op1_operations/research/stage2_feedback/stage2_feedback_scoreboard.latest.json",
        help="Stage2 scoreboard path",
    )
    p.add_argument(
        "--stage2-priority",
        default="workspaces/op1_operations/research/stage2_feedback/feedback_priority_queue.latest.json",
        help="Stage2 priority queue path",
    )
    p.add_argument(
        "--stage2-impact",
        default="workspaces/op1_operations/research/stage2_feedback/impact_model.latest.json",
        help="Stage2 impact model path",
    )
    p.add_argument(
        "--stage2-loop",
        default="workspaces/op1_operations/research/stage2_feedback/feedback_loop_status.latest.json",
        help="Stage2 loop status path",
    )
    p.add_argument(
        "--decision-log",
        default="workspaces/op1_product/research/stage2_idea_screening/decision_log.json",
        help="Product decision log path",
    )
    p.add_argument(
        "--project-blueprint",
        default="workspaces/op1_product/research/stage3_mvp_scope/project_blueprint.json",
        help="Product blueprint path",
    )
    p.add_argument(
        "--opportunity-records",
        default="workspaces/op1_product/research/stage1_idea_discovery/opportunity_records.json",
        help="Product opportunity records path",
    )
    p.add_argument(
        "--stage2-product-run",
        default="workspaces/op1_product/research/stage2_web_product/run.latest.json",
        help="Product stage2 run path",
    )
    p.add_argument(
        "--stage2-product-state",
        default="workspaces/op1_product/research/stage2_web_product/state.latest.json",
        help="Product stage2 state path",
    )
    return p.parse_args()


def _extract_stage1_summary(stage1: Dict[str, Any]) -> Dict[str, Any]:
    summary = stage1.get("summary", {}) if isinstance(stage1.get("summary"), dict) else {}
    traffic = summary.get("traffic", {}) if isinstance(summary.get("traffic"), dict) else {}
    signups = summary.get("signups", {}) if isinstance(summary.get("signups"), dict) else {}
    revenue = summary.get("revenue", {}) if isinstance(summary.get("revenue"), dict) else {}
    conv = summary.get("conversion", {}) if isinstance(summary.get("conversion"), dict) else {}

    return {
        "sessions": to_float(traffic.get("sessions"), 0.0),
        "qualified_signups": to_int(signups.get("qualified_signups"), 0),
        "paid_customers": to_int(signups.get("paid_customers"), 0),
        "visit_to_signup_rate": to_float(conv.get("visit_to_signup_rate"), 0.0),
        "signup_to_paid_rate": to_float(conv.get("signup_to_paid_rate"), 0.0),
        "net_new_mrr": to_float(revenue.get("net_new_mrr"), 0.0),
    }


def _extract_stage2_summary(stage2: Dict[str, Any]) -> Dict[str, Any]:
    summary = stage2.get("summary", {}) if isinstance(stage2.get("summary"), dict) else {}
    feedback = summary.get("feedback", {}) if isinstance(summary.get("feedback"), dict) else {}
    priority = summary.get("priority", {}) if isinstance(summary.get("priority"), dict) else {}
    loop = summary.get("loop", {}) if isinstance(summary.get("loop"), dict) else {}
    impact = summary.get("impact", {}) if isinstance(summary.get("impact"), dict) else {}

    return {
        "feedback_events_total": to_int(feedback.get("feedback_events_total"), 0),
        "feedback_items_total": to_int(feedback.get("feedback_items_total"), 0),
        "themes_total": to_int(feedback.get("themes_total"), 0),
        "top_topics": summary.get("top_topics", []) if isinstance(summary.get("top_topics"), list) else [],
        "p0_count": to_int(priority.get("p0_count"), 0),
        "p1_count": to_int(priority.get("p1_count"), 0),
        "p2_count": to_int(priority.get("p2_count"), 0),
        "triaged_rate": to_float(loop.get("triaged_rate"), 0.0),
        "expected_mrr_delta_30d": to_float(impact.get("expected_mrr_delta_30d"), 0.0),
    }


def _extract_product_context(
    decision_log: Dict[str, Any],
    project_blueprint: Dict[str, Any],
    opportunity_records: Dict[str, Any],
    run_latest: Dict[str, Any],
    state_latest: Dict[str, Any],
    project_specs: List[Path],
) -> Dict[str, Any]:
    selection = decision_log.get("selection_summary", {}) if isinstance(decision_log.get("selection_summary"), dict) else {}

    selected_opportunity = str(selection.get("selected_opportunity_id") or project_blueprint.get("from_opportunity_id") or "")

    opportunities = opportunity_records.get("opportunities", []) if isinstance(opportunity_records.get("opportunities"), list) else []
    opp_lookup: Dict[str, Dict[str, Any]] = {}
    for row in opportunities:
        if isinstance(row, dict):
            opp_lookup[str(row.get("opportunity_id") or "")] = row

    selected_opp = opp_lookup.get(selected_opportunity, {})

    stage2_run_status = str(run_latest.get("status") or "unknown")
    deployment_url = ((run_latest.get("output") or {}) if isinstance(run_latest.get("output"), dict) else {}).get("deployed_url")

    events = state_latest.get("events", []) if isinstance(state_latest.get("events"), list) else []
    pass_count = 0
    fail_count = 0
    for e in events:
        if not isinstance(e, dict):
            continue
        st = str(e.get("status") or "")
        step = str(e.get("step") or "")
        if step == "complete" and st == "passed":
            pass_count += 1
        if st == "failed":
            fail_count += 1

    return {
        "selected_opportunity_id": selected_opportunity or None,
        "selected_project_id": project_blueprint.get("project_id"),
        "stage2_product_run_status": stage2_run_status,
        "latest_deployment_url": deployment_url,
        "project_specs_available": [str(p) for p in sorted(project_specs)],
        "historical_pass_count": pass_count,
        "historical_fail_count": fail_count,
        "selected_opportunity_context": {
            "target_segment": selected_opp.get("target_segment"),
            "core_problem": selected_opp.get("core_problem"),
            "distribution_entry": selected_opp.get("distribution_entry"),
        },
        "project_blueprint_summary": {
            "hypothesis": project_blueprint.get("hypothesis"),
            "success_metric": project_blueprint.get("success_metric"),
            "kill_criteria": project_blueprint.get("kill_criteria"),
        },
    }


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else resolve_repo_root(Path(__file__))
    out_dir = repo_root / args.out_dir

    adapters_cfg = read_json(repo_root / args.adapters_config, default={}) or {}

    stage1 = read_json(repo_root / args.stage1_scoreboard, default={}) or {}
    stage2 = read_json(repo_root / args.stage2_scoreboard, default={}) or {}
    stage2_priority = read_json(repo_root / args.stage2_priority, default={}) or {}
    stage2_impact = read_json(repo_root / args.stage2_impact, default={}) or {}
    stage2_loop = read_json(repo_root / args.stage2_loop, default={}) or {}

    decision_log = read_json(repo_root / args.decision_log, default={}) or {}
    project_blueprint = read_json(repo_root / args.project_blueprint, default={}) or {}
    opportunity_records = read_json(repo_root / args.opportunity_records, default={}) or {}
    run_latest = read_json(repo_root / args.stage2_product_run, default={}) or {}
    state_latest = read_json(repo_root / args.stage2_product_state, default={}) or {}

    project_spec_glob = repo_root / "workspaces/op1_product/research/build_deploy_v1"
    project_specs = list(project_spec_glob.glob("project_spec*.json")) if project_spec_glob.exists() else []

    stage1_summary = _extract_stage1_summary(stage1)
    stage2_summary = _extract_stage2_summary(stage2)
    product_context = _extract_product_context(
        decision_log=decision_log,
        project_blueprint=project_blueprint,
        opportunity_records=opportunity_records,
        run_latest=run_latest,
        state_latest=state_latest,
        project_specs=project_specs,
    )

    queue_rows = stage2_priority.get("queue", []) if isinstance(stage2_priority.get("queue"), list) else []
    top_queue = queue_rows[:15]

    impact_rows = stage2_impact.get("rows", []) if isinstance(stage2_impact.get("rows"), list) else []

    iteration_inputs = {
        "generated_at": now_iso(),
        "stage": "stage3_product_iteration",
        "mode": "simulated_signals",
        "stage1_baseline": stage1_summary,
        "stage2_feedback_context": stage2_summary,
        "product_context": product_context,
        "top_feedback_queue": top_queue,
        "impact_rows": impact_rows[:25],
        "loop_status": {
            "triaged_rate": to_float(stage2_loop.get("triaged_rate"), 0.0),
            "closure_rate": to_float(stage2_loop.get("closure_rate"), 0.0),
            "p0_untriaged": to_int(stage2_loop.get("p0_untriaged"), 0),
            "p0_unowned": to_int(stage2_loop.get("p0_unowned"), 0),
        },
        "references": {
            "adapters_config": args.adapters_config,
            "stage1_scoreboard": args.stage1_scoreboard,
            "stage2_scoreboard": args.stage2_scoreboard,
            "stage2_priority": args.stage2_priority,
            "stage2_impact": args.stage2_impact,
            "stage2_loop": args.stage2_loop,
            "decision_log": args.decision_log,
            "project_blueprint": args.project_blueprint,
            "opportunity_records": args.opportunity_records,
            "stage2_product_run": args.stage2_product_run,
            "stage2_product_state": args.stage2_product_state,
        },
    }

    warnings: List[str] = []
    if stage1_summary["sessions"] <= 0:
        warnings.append("stage1 sessions missing or zero")
    if stage2_summary["feedback_items_total"] <= 0:
        warnings.append("stage2 feedback items missing or zero")
    if not product_context.get("selected_opportunity_id"):
        warnings.append("selected opportunity id not detected")
    if not project_specs:
        warnings.append("no project_spec*.json found in op1_product/research/build_deploy_v1")

    adapters = adapters_cfg.get("adapters", []) if isinstance(adapters_cfg.get("adapters"), list) else []
    adapter_status = []
    for ad in adapters:
        if not isinstance(ad, dict):
            continue
        aid = str(ad.get("id") or "")
        enabled = bool(ad.get("enabled", True))
        rel = str(ad.get("path") or "")
        p = repo_root / rel if rel else None
        exists = bool(p and p.exists())
        adapter_status.append({"adapter_id": aid, "enabled": enabled, "path": rel, "exists": exists})
        if enabled and not exists:
            warnings.append(f"enabled adapter missing path: {aid}")

    quality = {
        "generated_at": now_iso(),
        "warnings": warnings,
        "warning_count": len(warnings),
        "adapter_status": adapter_status,
        "inputs_present": {
            "adapters_config": bool(adapters_cfg),
            "stage1": bool(stage1),
            "stage2": bool(stage2),
            "product_blueprint": bool(project_blueprint),
            "priority_queue_rows": len(queue_rows),
            "project_specs": len(project_specs),
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "iteration_inputs.latest.json", iteration_inputs)
    write_json(out_dir / "iteration_input_quality.latest.json", quality)

    print({"top_queue": len(top_queue), "project_specs": len(project_specs), "warnings": len(warnings)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
