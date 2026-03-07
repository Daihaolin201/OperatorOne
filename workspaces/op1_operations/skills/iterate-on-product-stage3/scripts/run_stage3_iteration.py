#!/usr/bin/env python3
"""Run full Stage3 Iterate on product pipeline for OperatorOne op1_operations."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Dict

from stage3_iteration_common import now_iso, read_json, resolve_repo_root, write_json


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Stage3 product iteration pipeline")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root (auto-detect when omitted)")
    p.add_argument(
        "--in-dir",
        default="workspaces/op1_operations/research/stage3_product_iteration",
        help="Output directory (repo-root relative)",
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
        "--adapters-config",
        default="workspaces/op1_operations/config/stage3_iteration_adapters.v1.json",
        help="Stage3 adapters config path",
    )
    p.add_argument(
        "--weights",
        default="workspaces/op1_operations/config/stage3_iteration_weights.v1.yaml",
        help="Stage3 iteration weights path",
    )
    p.add_argument(
        "--guardrails",
        default="workspaces/op1_operations/config/stage3_metric_guardrails.v1.yaml",
        help="Stage3 guardrails config path",
    )
    p.add_argument(
        "--rollout-policy",
        default="workspaces/op1_operations/config/stage3_rollout_policy.v1.yaml",
        help="Stage3 rollout policy path",
    )
    p.add_argument(
        "--decision-policy",
        default="workspaces/op1_operations/contracts/stage3_decision_policy.v1.json",
        help="Stage3 decision policy path",
    )
    p.add_argument(
        "--experiment-contract",
        default="workspaces/op1_operations/contracts/stage3_experiment_contract.v1.json",
        help="Stage3 experiment contract path",
    )
    p.add_argument(
        "--product-state",
        default="workspaces/op1_product/research/stage2_web_product/state.latest.json",
        help="Product state path for delivery metrics",
    )
    p.add_argument(
        "--product-run",
        default="workspaces/op1_product/research/stage2_web_product/run.latest.json",
        help="Product run path for variant runtime context",
    )
    p.add_argument("--strict-repro", action="store_true", help="Force strict reproducibility check")
    p.add_argument("--update-baseline", action="store_true", help="Update reproducibility baseline")
    return p.parse_args()


def run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True)


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    repo_root = Path(args.repo_root).resolve() if args.repo_root else resolve_repo_root(script_dir)

    out_dir = repo_root / args.in_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    inputs_script = script_dir / "build_stage3_iteration_inputs.py"
    ost_script = script_dir / "build_opportunity_solution_tree.py"
    backlog_script = script_dir / "build_stage3_experiment_backlog.py"
    variants_script = script_dir / "build_stage3_variant_specs.py"
    rollout_script = script_dir / "run_stage3_rollouts.py"
    eval_script = script_dir / "evaluate_stage3_experiments.py"
    scoreboard_script = script_dir / "build_stage3_iteration_scoreboard.py"
    verify_script = script_dir / "verify_stage3_reproducibility.py"

    run(
        [
            "python3",
            str(inputs_script),
            "--repo-root",
            str(repo_root),
            "--out-dir",
            args.in_dir,
            "--adapters-config",
            args.adapters_config,
            "--stage1-scoreboard",
            args.stage1_scoreboard,
            "--stage2-scoreboard",
            args.stage2_scoreboard,
            "--stage2-priority",
            args.stage2_priority,
            "--stage2-impact",
            args.stage2_impact,
            "--stage2-loop",
            args.stage2_loop,
        ],
        cwd=repo_root,
    )

    run(["python3", str(ost_script), "--repo-root", str(repo_root), "--in-dir", args.in_dir], cwd=repo_root)

    run(
        [
            "python3",
            str(backlog_script),
            "--repo-root",
            str(repo_root),
            "--in-dir",
            args.in_dir,
            "--weights",
            args.weights,
            "--guardrails",
            args.guardrails,
            "--decision-policy",
            args.decision_policy,
            "--experiment-contract",
            args.experiment_contract,
        ],
        cwd=repo_root,
    )

    run(
        [
            "python3",
            str(variants_script),
            "--repo-root",
            str(repo_root),
            "--in-dir",
            args.in_dir,
            "--product-run",
            args.product_run,
        ],
        cwd=repo_root,
    )

    run(
        [
            "python3",
            str(rollout_script),
            "--repo-root",
            str(repo_root),
            "--in-dir",
            args.in_dir,
            "--rollout-policy",
            args.rollout_policy,
            "--guardrails",
            args.guardrails,
        ],
        cwd=repo_root,
    )

    run(
        [
            "python3",
            str(eval_script),
            "--repo-root",
            str(repo_root),
            "--in-dir",
            args.in_dir,
            "--decision-policy",
            args.decision_policy,
            "--product-state",
            args.product_state,
        ],
        cwd=repo_root,
    )

    run(
        [
            "python3",
            str(scoreboard_script),
            "--repo-root",
            str(repo_root),
            "--in-dir",
            args.in_dir,
            "--guardrails",
            args.guardrails,
            "--stage1-scoreboard",
            args.stage1_scoreboard,
            "--stage2-scoreboard",
            args.stage2_scoreboard,
        ],
        cwd=repo_root,
    )

    baseline_rel = "workspaces/op1_operations/research/stage3_product_iteration/reproducibility_baseline.json"
    baseline_file = repo_root / baseline_rel

    verify_cmd = [
        "python3",
        str(verify_script),
        "--repo-root",
        str(repo_root),
        "--in-dir",
        args.in_dir,
        "--baseline-file",
        baseline_rel,
    ]

    if args.update_baseline or not baseline_file.exists():
        verify_cmd.append("--update-baseline")
    if args.strict_repro:
        verify_cmd.append("--strict")

    run(verify_cmd, cwd=repo_root)

    scoreboard = read_json(out_dir / "stage3_iteration_scoreboard.latest.json", default={}) or {}
    repro = read_json(out_dir / "reproducibility_report.latest.json", default={}) or {}

    run_report: Dict[str, Any] = {
        "generated_at": now_iso(),
        "status": "passed" if repro.get("status") == "passed" else "failed",
        "pipeline": "stage3_iteration",
        "outputs": {
            "scoreboard_json": str(out_dir / "stage3_iteration_scoreboard.latest.json"),
            "scoreboard_md": str(out_dir / "stage3_iteration_scoreboard.latest.md"),
            "weekly_snapshot_md": str(out_dir / "weekly_iteration_snapshot.latest.md"),
            "reproducibility_json": str(out_dir / "reproducibility_report.latest.json"),
        },
        "headline": {
            "experiments_planned": (((scoreboard.get("summary") or {}).get("flow") or {}).get("experiments_planned")),
            "ship_count": (((scoreboard.get("summary") or {}).get("outcomes") or {}).get("ship_count")),
            "rollback_count": (((scoreboard.get("summary") or {}).get("outcomes") or {}).get("rollback_count")),
            "observed_mrr_delta_30d": (((scoreboard.get("summary") or {}).get("outcomes") or {}).get("observed_mrr_delta_30d")),
            "alerts_count": scoreboard.get("alerts_count"),
        },
    }

    write_json(out_dir / "run_stage3.latest.json", run_report)
    print(json.dumps(run_report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
