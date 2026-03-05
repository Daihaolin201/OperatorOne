#!/usr/bin/env python3
"""Run full Stage2 Process feedback pipeline for OperatorOne op1_operations."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Dict

from stage2_feedback_common import now_iso, read_json, resolve_repo_root, write_json


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Stage2 feedback pipeline")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root (auto-detect when omitted)")
    p.add_argument(
        "--in-dir",
        default="workspaces/op1_operations/research/stage2_feedback",
        help="Output directory (repo-root relative)",
    )
    p.add_argument(
        "--adapters-config",
        default="workspaces/op1_operations/config/feedback_source_adapters.v1.json",
        help="Feedback adapters config path",
    )
    p.add_argument(
        "--weights",
        default="workspaces/op1_operations/config/feedback_priority_weights.v1.yaml",
        help="Feedback priority weights path",
    )
    p.add_argument(
        "--feedback-contract",
        default="workspaces/op1_operations/contracts/feedback_contract.v1.json",
        help="Feedback contract path",
    )
    p.add_argument(
        "--stage1-scoreboard",
        default="workspaces/op1_operations/research/stage1_tracking/stage1_scoreboard.latest.json",
        help="Stage1 scoreboard path",
    )
    p.add_argument(
        "--conversion-scoreboard",
        default="workspaces/op1_sales/research/conversion/conversion_scoreboard.latest.json",
        help="Sales conversion scoreboard path",
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

    ingest_script = script_dir / "ingest_stage2_feedback.py"
    normalize_script = script_dir / "normalize_stage2_feedback.py"
    cluster_script = script_dir / "cluster_stage2_feedback.py"
    score_script = script_dir / "score_stage2_feedback.py"
    prioritize_script = script_dir / "prioritize_stage2_feedback.py"
    scoreboard_script = script_dir / "build_stage2_feedback_scoreboard.py"
    verify_script = script_dir / "verify_stage2_feedback_reproducibility.py"

    run(
        [
            "python3",
            str(ingest_script),
            "--repo-root",
            str(repo_root),
            "--adapters-config",
            args.adapters_config,
            "--out-dir",
            args.in_dir,
        ],
        cwd=repo_root,
    )

    run(
        [
            "python3",
            str(normalize_script),
            "--repo-root",
            str(repo_root),
            "--in-dir",
            args.in_dir,
        ],
        cwd=repo_root,
    )

    run(
        [
            "python3",
            str(cluster_script),
            "--repo-root",
            str(repo_root),
            "--in-dir",
            args.in_dir,
        ],
        cwd=repo_root,
    )

    run(
        [
            "python3",
            str(score_script),
            "--repo-root",
            str(repo_root),
            "--in-dir",
            args.in_dir,
            "--weights",
            args.weights,
            "--adapters-config",
            args.adapters_config,
        ],
        cwd=repo_root,
    )

    run(
        [
            "python3",
            str(prioritize_script),
            "--repo-root",
            str(repo_root),
            "--in-dir",
            args.in_dir,
            "--weights",
            args.weights,
            "--stage1-scoreboard",
            args.stage1_scoreboard,
            "--conversion-scoreboard",
            args.conversion_scoreboard,
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
            "--adapters-config",
            args.adapters_config,
            "--feedback-contract",
            args.feedback_contract,
            "--stage1-scoreboard",
            args.stage1_scoreboard,
        ],
        cwd=repo_root,
    )

    baseline_rel = "workspaces/op1_operations/research/stage2_feedback/reproducibility_baseline.json"
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

    scoreboard = read_json(out_dir / "stage2_feedback_scoreboard.latest.json", default={}) or {}
    repro = read_json(out_dir / "reproducibility_report.latest.json", default={}) or {}

    run_report: Dict[str, Any] = {
        "generated_at": now_iso(),
        "status": "passed" if repro.get("status") == "passed" else "failed",
        "pipeline": "stage2_feedback",
        "outputs": {
            "scoreboard_json": str(out_dir / "stage2_feedback_scoreboard.latest.json"),
            "scoreboard_md": str(out_dir / "stage2_feedback_scoreboard.latest.md"),
            "weekly_snapshot_md": str(out_dir / "weekly_feedback_snapshot.latest.md"),
            "reproducibility_json": str(out_dir / "reproducibility_report.latest.json"),
        },
        "headline": {
            "feedback_events_total": ((scoreboard.get("summary") or {}).get("feedback") or {}).get("feedback_events_total"),
            "feedback_items_total": ((scoreboard.get("summary") or {}).get("feedback") or {}).get("feedback_items_total"),
            "p0_count": ((scoreboard.get("summary") or {}).get("priority") or {}).get("p0_count"),
            "expected_mrr_delta_30d": ((scoreboard.get("summary") or {}).get("impact") or {}).get("expected_mrr_delta_30d"),
            "alerts_count": scoreboard.get("alerts_count"),
        },
    }

    write_json(out_dir / "run_stage2.latest.json", run_report)
    print(json.dumps(run_report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
