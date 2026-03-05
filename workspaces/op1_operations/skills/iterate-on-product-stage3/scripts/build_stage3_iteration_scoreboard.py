#!/usr/bin/env python3
"""Build Stage3 product iteration scoreboard, alerts, and weekly snapshot."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from stage3_iteration_common import now_iso, read_json, read_json_or_yaml_like, resolve_repo_root, to_float, to_int, write_json, write_text


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Stage3 iteration scoreboard")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root")
    p.add_argument(
        "--in-dir",
        default="workspaces/op1_operations/research/stage3_product_iteration",
        help="Input/output directory",
    )
    p.add_argument(
        "--guardrails",
        default="workspaces/op1_operations/config/stage3_metric_guardrails.v1.yaml",
        help="Guardrails config",
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
    return p.parse_args()


def _build_md(scoreboard: Dict[str, Any], alerts: List[Dict[str, Any]], results_rows: List[Dict[str, Any]]) -> str:
    s = scoreboard.get("summary", {}) if isinstance(scoreboard.get("summary"), dict) else {}
    inp = s.get("inputs", {}) if isinstance(s.get("inputs"), dict) else {}
    flow = s.get("flow", {}) if isinstance(s.get("flow"), dict) else {}
    outcome = s.get("outcomes", {}) if isinstance(s.get("outcomes"), dict) else {}
    delivery = s.get("delivery", {}) if isinstance(s.get("delivery"), dict) else {}

    lines = [
        "# Stage3 Iteration Scoreboard (Iterate on product)",
        "",
        f"Generated at: {scoreboard.get('generated_at')}",
        f"Mode: {scoreboard.get('mode')}",
        "",
        "## Inputs",
        f"- top_feedback_queue_items: {inp.get('top_feedback_queue_items', 0)}",
        f"- opportunities: {inp.get('opportunities', 0)}",
        f"- stage1_net_new_mrr_baseline: {inp.get('stage1_net_new_mrr_baseline', 0)}",
        f"- stage2_expected_mrr_delta_30d: {inp.get('stage2_expected_mrr_delta_30d', 0)}",
        "",
        "## Iteration flow",
        f"- experiments_planned: {flow.get('experiments_planned', 0)}",
        f"- running_candidates: {flow.get('running_candidates', 0)}",
        f"- rollout_completed: {flow.get('rollout_completed', 0)}",
        f"- rollout_rollback: {flow.get('rollout_rollback', 0)}",
        f"- monitor_breaches: {flow.get('monitor_breaches', 0)}",
        "",
        "## Outcomes",
        f"- ship: {outcome.get('ship_count', 0)}",
        f"- iterate: {outcome.get('iterate_count', 0)}",
        f"- rollback: {outcome.get('rollback_count', 0)}",
        f"- park: {outcome.get('park_count', 0)}",
        f"- observed_mrr_delta_30d: {outcome.get('observed_mrr_delta_30d', 0)}",
        "",
        "## Delivery performance",
        f"- deployment_frequency_30d: {delivery.get('deployment_frequency_30d', 0)}",
        f"- lead_time_hours_avg: {delivery.get('lead_time_hours_avg')}",
        f"- change_failure_rate: {delivery.get('change_failure_rate')}",
        f"- restore_time_hours_avg: {delivery.get('restore_time_hours_avg')}",
        "",
        "## Top experiment outcomes",
        "",
        "| Experiment | Decision | Lift (pp) | MRR Δ30d | Rollout |",
        "|---|---|---:|---:|---|",
    ]

    for row in results_rows[:12]:
        lines.append(
            f"| {row.get('experiment_id')} | {row.get('decision')} | {row.get('primary_metric_lift_pp')} | {row.get('observed_mrr_delta_30d')} | {row.get('rollout_status')} |"
        )

    lines.append("")
    lines.append("## Alerts")
    if not alerts:
        lines.append("- none")
    else:
        for a in alerts:
            lines.append(f"- [{a.get('severity', 'info')}] {a.get('code')}: {a.get('message')}")

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else resolve_repo_root(Path(__file__))
    in_dir = repo_root / args.in_dir

    guardrails = read_json_or_yaml_like(repo_root / args.guardrails, default={}) or {}
    stage1 = read_json(repo_root / args.stage1_scoreboard, default={}) or {}
    stage2 = read_json(repo_root / args.stage2_scoreboard, default={}) or {}

    iteration_inputs = read_json(in_dir / "iteration_inputs.latest.json", default={}) or {}
    ost = read_json(in_dir / "opportunity_solution_tree.latest.json", default={}) or {}
    backlog = read_json(in_dir / "experiment_backlog.latest.json", default={}) or {}
    contract_validation = read_json(in_dir / "experiment_contract_validation.latest.json", default={}) or {}
    variants = read_json(in_dir / "variant_specs.latest.json", default={}) or {}
    rollout = read_json(in_dir / "rollout_log.latest.json", default={}) or {}
    monitor = read_json(in_dir / "experiment_monitor.latest.json", default={}) or {}
    results = read_json(in_dir / "experiment_results.latest.json", default={}) or {}
    decisions = read_json(in_dir / "iteration_decision_log.latest.json", default={}) or {}
    delivery = read_json(in_dir / "delivery_performance.latest.json", default={}) or {}

    results_rows = results.get("rows", []) if isinstance(results.get("rows"), list) else []
    decision_counts = decisions.get("decision_counts", {}) if isinstance(decisions.get("decision_counts"), dict) else {}

    stage1_net_new = to_float((((stage1.get("summary") or {}).get("revenue") or {}).get("net_new_mrr")), 0.0)
    stage2_expected = to_float((((stage2.get("summary") or {}).get("impact") or {}).get("expected_mrr_delta_30d")), 0.0)

    alerts: List[Dict[str, Any]] = []

    guardrail_cfg = guardrails.get("guardrail_metrics", {}) if isinstance(guardrails.get("guardrail_metrics"), dict) else {}
    error_max = to_float(((guardrail_cfg.get("error_rate") or {}).get("max_delta_pp")), 0.03)
    unsub_max = to_float(((guardrail_cfg.get("unsubscribe_rate") or {}).get("max_delta_pp")), 0.01)

    if str(contract_validation.get("status") or "") != "passed":
        alerts.append({"severity": "critical", "code": "experiment_contract_invalid", "message": "Experiment contract validation failed."})

    breach_count = to_int(monitor.get("breach_count"), 0)
    if breach_count > 0:
        alerts.append(
            {
                "severity": "warning",
                "code": "monitor_breach_present",
                "message": f"{breach_count} experiments show guardrail/data monitor breaches.",
            }
        )

    rollback_count = to_int(rollout.get("rollback_count"), 0)
    if rollback_count > 0:
        alerts.append(
            {
                "severity": "warning",
                "code": "rollout_rollback_present",
                "message": f"{rollback_count} rollouts are in rollback state.",
            }
        )

    if to_int(decision_counts.get("ship"), 0) == 0:
        alerts.append(
            {
                "severity": "info",
                "code": "no_ship_yet",
                "message": "No experiments reached ship threshold yet; continue iteration learning cycle.",
            }
        )

    if to_float(delivery.get("change_failure_rate"), 0.0) > 0.3:
        alerts.append(
            {
                "severity": "warning",
                "code": "change_failure_rate_high",
                "message": f"Change failure rate {delivery.get('change_failure_rate')} is above 0.3.",
            }
        )

    if to_float(delivery.get("lead_time_hours_avg"), 0.0) > 24:
        alerts.append(
            {
                "severity": "warning",
                "code": "lead_time_high",
                "message": f"Lead time average {delivery.get('lead_time_hours_avg')}h exceeds 24h target.",
            }
        )

    # Optional check over result rows against hard guardrail thresholds.
    hard_breach = 0
    for row in results_rows:
        checks = row.get("checks", {}) if isinstance(row.get("checks"), dict) else {}
        if to_float(checks.get("error_rate_delta_pp"), 0.0) > error_max or to_float(checks.get("unsubscribe_rate_delta_pp"), 0.0) > unsub_max:
            hard_breach += 1
    if hard_breach > 0:
        alerts.append(
            {
                "severity": "warning",
                "code": "hard_guardrail_exceeded",
                "message": f"{hard_breach} experiments exceeded hard guardrail thresholds.",
            }
        )

    summary = {
        "inputs": {
            "top_feedback_queue_items": len(iteration_inputs.get("top_feedback_queue", []) if isinstance(iteration_inputs.get("top_feedback_queue"), list) else []),
            "opportunities": to_int(ost.get("opportunity_count"), 0),
            "stage1_net_new_mrr_baseline": stage1_net_new,
            "stage2_expected_mrr_delta_30d": stage2_expected,
        },
        "flow": {
            "experiments_planned": to_int(backlog.get("item_count"), 0),
            "running_candidates": to_int(rollout.get("running_count"), 0),
            "variant_sets": to_int(variants.get("variant_set_count"), 0),
            "rollout_completed": to_int(rollout.get("completed_count"), 0),
            "rollout_rollback": rollback_count,
            "monitor_breaches": breach_count,
        },
        "outcomes": {
            "ship_count": to_int(decision_counts.get("ship"), 0),
            "iterate_count": to_int(decision_counts.get("iterate"), 0),
            "rollback_count": to_int(decision_counts.get("rollback"), 0),
            "park_count": to_int(decision_counts.get("park"), 0),
            "observed_signup_delta_30d": to_float(((results.get("totals") or {}).get("observed_signup_delta_30d")), 0.0),
            "observed_paid_delta_30d": to_float(((results.get("totals") or {}).get("observed_paid_delta_30d")), 0.0),
            "observed_mrr_delta_30d": to_float(((results.get("totals") or {}).get("observed_mrr_delta_30d")), 0.0),
        },
        "delivery": {
            "deployment_frequency_30d": to_int(delivery.get("deployment_frequency_30d"), 0),
            "lead_time_hours_avg": delivery.get("lead_time_hours_avg"),
            "change_failure_rate": delivery.get("change_failure_rate"),
            "restore_time_hours_avg": delivery.get("restore_time_hours_avg"),
        },
    }

    capability_status = [
        {"capability": "iteration_inputs", "status": "implemented", "evidence": "research/stage3_product_iteration/iteration_inputs.latest.json"},
        {"capability": "opportunity_solution_tree", "status": "implemented", "evidence": "research/stage3_product_iteration/opportunity_solution_tree.latest.json"},
        {"capability": "hypothesis_registry", "status": "implemented", "evidence": "research/stage3_product_iteration/hypothesis_registry.latest.jsonl"},
        {"capability": "experiment_backlog", "status": "implemented", "evidence": "research/stage3_product_iteration/experiment_backlog.latest.json"},
        {"capability": "contract_validation", "status": "implemented", "evidence": "research/stage3_product_iteration/experiment_contract_validation.latest.json"},
        {"capability": "variant_specs", "status": "implemented", "evidence": "research/stage3_product_iteration/variant_specs.latest.json"},
        {"capability": "rollout_control", "status": "implemented", "evidence": "research/stage3_product_iteration/rollout_log.latest.json"},
        {"capability": "monitoring", "status": "implemented", "evidence": "research/stage3_product_iteration/experiment_monitor.latest.json"},
        {"capability": "evaluation_engine", "status": "implemented", "evidence": "research/stage3_product_iteration/experiment_results.latest.json"},
        {"capability": "decision_policy", "status": "implemented", "evidence": "research/stage3_product_iteration/iteration_decision_log.latest.json"},
        {"capability": "learning_repository", "status": "implemented", "evidence": "research/stage3_product_iteration/learning_log.latest.md"},
        {"capability": "portfolio_wip", "status": "implemented", "evidence": "research/stage3_product_iteration/iteration_portfolio.latest.json"},
        {"capability": "delivery_performance", "status": "implemented", "evidence": "research/stage3_product_iteration/delivery_performance.latest.json"},
        {"capability": "cross_team_handoffs", "status": "implemented", "evidence": "handoffs/operations_to_product_iterate.json"},
        {"capability": "stage3_scoreboard", "status": "implemented", "evidence": "research/stage3_product_iteration/stage3_iteration_scoreboard.latest.md"},
    ]

    scoreboard = {
        "generated_at": now_iso(),
        "stage": "stage3_iterate_on_product",
        "mode": "simulated_signals",
        "summary": summary,
        "alerts_count": len(alerts),
        "capability_status": capability_status,
        "notes": [
            "Stage3 currently operates on Stage1/Stage2 simulated signals + product delivery artifacts.",
            "Decision outputs are policy-driven and reproducible with fixed STAGE3_AS_OF.",
        ],
    }

    alerts_payload = {
        "generated_at": now_iso(),
        "alerts": alerts,
    }

    weekly_lines = [
        "# Weekly Iteration Snapshot (Stage3)",
        "",
        f"Generated at: {now_iso()}",
        "",
        "## Iteration throughput",
        f"- experiments_planned: {summary['flow']['experiments_planned']}",
        f"- running_candidates: {summary['flow']['running_candidates']}",
        f"- rollout_completed: {summary['flow']['rollout_completed']}",
        f"- rollback_count: {summary['flow']['rollout_rollback']}",
        "",
        "## Decision outcomes",
        f"- ship: {summary['outcomes']['ship_count']}",
        f"- iterate: {summary['outcomes']['iterate_count']}",
        f"- rollback: {summary['outcomes']['rollback_count']}",
        f"- park: {summary['outcomes']['park_count']}",
        f"- observed_mrr_delta_30d: {summary['outcomes']['observed_mrr_delta_30d']}",
        "",
        "## Delivery health",
        f"- deployment_frequency_30d: {summary['delivery']['deployment_frequency_30d']}",
        f"- lead_time_hours_avg: {summary['delivery']['lead_time_hours_avg']}",
        f"- change_failure_rate: {summary['delivery']['change_failure_rate']}",
        "",
        "## Recommended next actions",
        "- Promote ship-qualified experiments to stable rollout and monitor post-ship guardrails.",
        "- For iterate decisions, narrow targeting and revise variant hypotheses before rerun.",
        "- Reduce delivery failure risk by addressing top failure sources in deployment pipeline.",
    ]

    write_json(in_dir / "stage3_iteration_scoreboard.latest.json", scoreboard)
    write_json(in_dir / "iteration_alerts.latest.json", alerts_payload)
    write_text(in_dir / "stage3_iteration_scoreboard.latest.md", _build_md(scoreboard, alerts, results_rows))
    write_text(in_dir / "weekly_iteration_snapshot.latest.md", "\n".join(weekly_lines) + "\n")

    print({"alerts": len(alerts), "experiments": summary['flow']['experiments_planned']})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
