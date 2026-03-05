#!/usr/bin/env python3
"""Simulate/track Stage3 progressive rollouts and experiment monitoring."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from stage3_iteration_common import (
    now_iso,
    read_json,
    read_json_or_yaml_like,
    resolve_repo_root,
    stable_hash,
    to_float,
    to_int,
    write_json,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Stage3 rollout planner/monitor")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root")
    p.add_argument(
        "--in-dir",
        default="workspaces/op1_operations/research/stage3_product_iteration",
        help="Input/output directory",
    )
    p.add_argument(
        "--rollout-policy",
        default="workspaces/op1_operations/config/stage3_rollout_policy.v1.yaml",
        help="Rollout policy path",
    )
    p.add_argument(
        "--guardrails",
        default="workspaces/op1_operations/config/stage3_metric_guardrails.v1.yaml",
        help="Guardrails config path",
    )
    return p.parse_args()


def _deterministic_unit(seed: str) -> float:
    h = stable_hash([seed], length=12)
    iv = int(h, 16)
    return (iv % 10000) / 10000.0


def _risk_ceiling(risk_band: str) -> int:
    rb = str(risk_band or "medium")
    if rb == "high":
        return 20
    if rb == "medium":
        return 50
    return 100


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else resolve_repo_root(Path(__file__))
    in_dir = repo_root / args.in_dir

    backlog = read_json(in_dir / "experiment_backlog.latest.json", default={}) or {}
    portfolio = read_json(in_dir / "iteration_portfolio.latest.json", default={}) or {}
    variants = read_json(in_dir / "variant_specs.latest.json", default={}) or {}

    rollout_cfg = read_json_or_yaml_like(repo_root / args.rollout_policy, default={}) or {}
    guardrails_cfg = read_json_or_yaml_like(repo_root / args.guardrails, default={}) or {}

    experiments = backlog.get("experiments", []) if isinstance(backlog.get("experiments"), list) else []
    variant_rows = variants.get("variants", []) if isinstance(variants.get("variants"), list) else []
    var_by_exp = {str(v.get("experiment_id") or ""): v for v in variant_rows if isinstance(v, dict)}

    running_candidates = set(portfolio.get("running_experiment_candidates", []) if isinstance(portfolio.get("running_experiment_candidates"), list) else [])
    rollout_steps = rollout_cfg.get("default_rollout_steps_percent", [1, 5, 20, 50, 100])
    if not isinstance(rollout_steps, list) or not rollout_steps:
        rollout_steps = [1, 5, 20, 50, 100]

    unsub_th = to_float((((guardrails_cfg.get("guardrail_metrics") or {}).get("unsubscribe_rate") or {}).get("max_delta_pp")), 0.01)
    err_th = to_float((((guardrails_cfg.get("guardrail_metrics") or {}).get("error_rate") or {}).get("max_delta_pp")), 0.03)
    srm_th = to_float((((guardrails_cfg.get("guardrail_metrics") or {}).get("srm_ratio_deviation") or {}).get("max_value")), 0.1)
    lag_th = to_float((((guardrails_cfg.get("guardrail_metrics") or {}).get("data_lag_hours") or {}).get("max_value")), 24.0)

    rollout_rows: List[Dict[str, Any]] = []
    monitor_rows: List[Dict[str, Any]] = []

    for exp in experiments:
        if not isinstance(exp, dict):
            continue

        exp_id = str(exp.get("experiment_id") or "")
        if not exp_id:
            continue

        rank = to_int(exp.get("rank"), 999)
        risk_band = str(exp.get("risk_band") or "medium")
        running = exp_id in running_candidates

        seed = f"{exp_id}:{rank}:{risk_band}"
        u = _deterministic_unit(seed)
        u2 = _deterministic_unit(seed + ":2")
        u3 = _deterministic_unit(seed + ":3")
        u4 = _deterministic_unit(seed + ":4")

        # Deterministic monitor metrics (simulated profile tuned to represent healthy-but-watchful rollouts).
        unsubscribe_delta = round((0.0015 + u * 0.006) * (1.05 if risk_band == "high" else 1.0), 4)
        error_delta = round((0.003 + u2 * 0.012) * (1.1 if risk_band == "high" else 1.0), 4)
        srm_dev = round(0.01 + u3 * 0.05, 4)
        data_lag_hours = round(3 + u4 * 8, 2)

        guardrail_breach = (
            unsubscribe_delta > unsub_th
            or error_delta > err_th
            or srm_dev > srm_th
            or data_lag_hours > lag_th
        )

        risk_ceiling = _risk_ceiling(risk_band)
        if not running:
            reached = 0
            rollout_status = "planned"
        elif guardrail_breach:
            reached = min(20, risk_ceiling)
            rollout_status = "rollback"
        else:
            reached = risk_ceiling
            rollout_status = "completed" if reached >= 100 else "held"

        steps = []
        for s in rollout_steps:
            s_int = int(s)
            if not running:
                st = "pending"
            elif guardrail_breach and s_int > reached:
                st = "cancelled"
            elif s_int <= reached:
                st = "done"
            else:
                st = "pending"
            steps.append({"step_percent": s_int, "status": st})

        monitor_row = {
            "experiment_id": exp_id,
            "rank": rank,
            "running": running,
            "guardrail_breach": guardrail_breach,
            "checks": {
                "unsubscribe_rate_delta_pp": unsubscribe_delta,
                "error_rate_delta_pp": error_delta,
                "srm_ratio_deviation": srm_dev,
                "data_lag_hours": data_lag_hours,
            },
            "thresholds": {
                "unsubscribe_rate_delta_pp": unsub_th,
                "error_rate_delta_pp": err_th,
                "srm_ratio_deviation": srm_th,
                "data_lag_hours": lag_th,
            },
            "status": "breach" if guardrail_breach else "healthy",
        }
        monitor_rows.append(monitor_row)

        rollout_rows.append(
            {
                "experiment_id": exp_id,
                "flag_key": ((var_by_exp.get(exp_id) or {}).get("flag_key")),
                "variant_set_id": ((var_by_exp.get(exp_id) or {}).get("variant_set_id")),
                "rollout_status": rollout_status,
                "running": running,
                "risk_band": risk_band,
                "reached_percent": reached,
                "steps": steps,
                "guardrail_breach": guardrail_breach,
            }
        )

    payload_rollout = {
        "generated_at": now_iso(),
        "item_count": len(rollout_rows),
        "running_count": sum(1 for r in rollout_rows if r.get("running")),
        "completed_count": sum(1 for r in rollout_rows if str(r.get("rollout_status")) == "completed"),
        "rollback_count": sum(1 for r in rollout_rows if str(r.get("rollout_status")) == "rollback"),
        "rows": rollout_rows,
    }

    payload_monitor = {
        "generated_at": now_iso(),
        "item_count": len(monitor_rows),
        "breach_count": sum(1 for r in monitor_rows if r.get("guardrail_breach")),
        "healthy_count": sum(1 for r in monitor_rows if not r.get("guardrail_breach")),
        "rows": monitor_rows,
    }

    write_json(in_dir / "rollout_log.latest.json", payload_rollout)
    write_json(in_dir / "experiment_monitor.latest.json", payload_monitor)

    print({"running": payload_rollout["running_count"], "breaches": payload_monitor["breach_count"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
