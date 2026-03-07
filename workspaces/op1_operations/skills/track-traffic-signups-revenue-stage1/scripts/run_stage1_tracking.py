#!/usr/bin/env python3
"""Run full Stage1 tracking pipeline for OperatorOne op1_operations."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Dict

from stage1_common import now_iso, read_json, resolve_repo_root, write_json


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Stage1 tracking pipeline")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root (auto-detect when omitted)")
    p.add_argument(
        "--adapters-config",
        default="workspaces/op1_operations/config/source_adapters.v1.json",
        help="Adapters config path relative to repo root",
    )
    p.add_argument(
        "--out-dir",
        default="workspaces/op1_operations/research/stage1_tracking",
        help="Output dir relative to repo root",
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

    out_dir = repo_root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    ingest_script = script_dir / "ingest_stage1_events.py"
    metrics_script = script_dir / "build_stage1_metrics.py"
    verify_script = script_dir / "verify_stage1_reproducibility.py"

    run(
        [
            "python3",
            str(ingest_script),
            "--repo-root",
            str(repo_root),
            "--adapters-config",
            args.adapters_config,
            "--out-dir",
            args.out_dir,
        ],
        cwd=repo_root,
    )

    run(
        [
            "python3",
            str(metrics_script),
            "--repo-root",
            str(repo_root),
            "--adapters-config",
            args.adapters_config,
            "--in-dir",
            args.out_dir,
        ],
        cwd=repo_root,
    )

    baseline_rel = "workspaces/op1_operations/research/stage1_tracking/reproducibility_baseline.json"
    baseline_file = repo_root / baseline_rel

    verify_cmd = [
        "python3",
        str(verify_script),
        "--repo-root",
        str(repo_root),
        "--in-dir",
        args.out_dir,
        "--baseline-file",
        baseline_rel,
    ]

    if args.update_baseline or not baseline_file.exists():
        verify_cmd.append("--update-baseline")

    if args.strict_repro:
        verify_cmd.append("--strict")

    run(verify_cmd, cwd=repo_root)

    scoreboard = read_json(out_dir / "stage1_scoreboard.latest.json", default={}) or {}
    repro = read_json(out_dir / "reproducibility_report.latest.json", default={}) or {}

    run_report: Dict[str, Any] = {
        "generated_at": now_iso(),
        "status": "passed" if repro.get("status") == "passed" else "failed",
        "pipeline": "stage1_tracking",
        "outputs": {
            "scoreboard_json": str(out_dir / "stage1_scoreboard.latest.json"),
            "scoreboard_md": str(out_dir / "stage1_scoreboard.latest.md"),
            "weekly_snapshot_md": str(out_dir / "weekly_kpi_snapshot.latest.md"),
            "reproducibility_json": str(out_dir / "reproducibility_report.latest.json"),
        },
        "headline": {
            "sessions": ((scoreboard.get("summary") or {}).get("traffic") or {}).get("sessions"),
            "qualified_signups": ((scoreboard.get("summary") or {}).get("signups") or {}).get("qualified_signups"),
            "paid_customers": ((scoreboard.get("summary") or {}).get("signups") or {}).get("paid_customers"),
            "net_new_mrr": ((scoreboard.get("summary") or {}).get("revenue") or {}).get("net_new_mrr"),
        },
    }

    write_json(out_dir / "run_stage1.latest.json", run_report)
    print(json.dumps(run_report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
