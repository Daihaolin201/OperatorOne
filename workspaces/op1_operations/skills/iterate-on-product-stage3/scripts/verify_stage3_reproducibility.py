#!/usr/bin/env python3
"""Verify Stage3 iteration outputs for completeness and reproducibility."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, List

from stage3_iteration_common import now_iso, read_json, resolve_repo_root, sha256_file, write_json, write_text


REQUIRED_OUTPUT_FILES = [
    "iteration_inputs.latest.json",
    "iteration_input_quality.latest.json",
    "opportunity_solution_tree.latest.json",
    "hypothesis_registry.latest.jsonl",
    "experiment_backlog.latest.json",
    "experiment_contract_validation.latest.json",
    "iteration_portfolio.latest.json",
    "variant_specs.latest.json",
    "rollout_log.latest.json",
    "experiment_monitor.latest.json",
    "experiment_results.latest.json",
    "iteration_decision_log.latest.json",
    "learning_log.latest.md",
    "delivery_performance.latest.json",
    "iteration_alerts.latest.json",
    "stage3_iteration_scoreboard.latest.json",
    "stage3_iteration_scoreboard.latest.md",
    "weekly_iteration_snapshot.latest.md",
]

REQUIRED_HANDOFF_FILES = [
    "handoffs/operations_to_product_iterate.json",
    "handoffs/operations_to_marketing_iterate.json",
    "handoffs/operations_to_sales_iterate.json",
]


REQUIRED_SCOREBOARD_KEYS = [
    "summary.inputs.top_feedback_queue_items",
    "summary.flow.experiments_planned",
    "summary.outcomes.observed_mrr_delta_30d",
    "summary.delivery.change_failure_rate",
]


def _has_path(obj: Dict, path: str) -> bool:
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False
        cur = cur[part]
    return True


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify Stage3 reproducibility")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root")
    p.add_argument(
        "--in-dir",
        default="workspaces/op1_operations/research/stage3_product_iteration",
        help="Stage3 output directory",
    )
    p.add_argument(
        "--baseline-file",
        default="workspaces/op1_operations/research/stage3_product_iteration/reproducibility_baseline.json",
        help="Baseline hash file",
    )
    p.add_argument("--update-baseline", action="store_true", help="Write current hashes as baseline")
    p.add_argument("--strict", action="store_true", help="Fail when hashes differ from baseline")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else resolve_repo_root(Path(__file__))
    in_dir = repo_root / args.in_dir
    baseline_path = repo_root / args.baseline_file

    missing_files: List[str] = []
    hashes: Dict[str, str] = {}

    for name in REQUIRED_OUTPUT_FILES:
        p = in_dir / name
        if not p.exists():
            missing_files.append(str(p))
            continue
        hashes[str(p)] = sha256_file(p)

    for rel in REQUIRED_HANDOFF_FILES:
        p = repo_root / rel
        if not p.exists():
            missing_files.append(str(p))
            continue
        hashes[str(p)] = sha256_file(p)

    scoreboard = read_json(in_dir / "stage3_iteration_scoreboard.latest.json", default={}) or {}
    missing_metric_keys: List[str] = [k for k in REQUIRED_SCOREBOARD_KEYS if not _has_path(scoreboard, k)]

    baseline = read_json(baseline_path, default={}) or {}
    baseline_hashes = baseline.get("hashes", {}) if isinstance(baseline.get("hashes"), dict) else {}

    changed_files: List[str] = []
    for p, digest in hashes.items():
        old = baseline_hashes.get(p)
        if old is None:
            continue
        if old != digest:
            changed_files.append(p)

    as_of = str(os.environ.get("STAGE3_AS_OF", "")).strip()
    strict_mode = bool(args.strict or (as_of and baseline_hashes and not args.update_baseline))

    passed = True
    if missing_files:
        passed = False
    if missing_metric_keys:
        passed = False
    if strict_mode and changed_files:
        passed = False

    report = {
        "generated_at": now_iso(),
        "status": "passed" if passed else "failed",
        "strict_mode": strict_mode,
        "as_of": as_of or None,
        "missing_files": missing_files,
        "hash_count": len(hashes),
        "missing_metric_keys": missing_metric_keys,
        "changed_files_vs_baseline": changed_files,
        "baseline_present": bool(baseline_hashes),
        "hashes": hashes,
    }

    if args.update_baseline:
        baseline_payload = {
            "generated_at": now_iso(),
            "hashes": hashes,
            "note": "Baseline for Stage3 reproducibility checks",
        }
        write_json(baseline_path, baseline_payload)
        report["baseline_updated"] = True

    write_json(in_dir / "reproducibility_report.latest.json", report)

    lines = [
        "# Reproducibility Report (Stage3 iteration)",
        "",
        f"Generated at: {report.get('generated_at')}",
        f"Status: {report.get('status')}",
        f"Strict mode: {report.get('strict_mode')}",
        "",
        "## Missing files",
    ]
    if missing_files:
        lines.extend([f"- {x}" for x in missing_files])
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## Missing metric keys")
    if missing_metric_keys:
        lines.extend([f"- {x}" for x in missing_metric_keys])
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## Changed files vs baseline")
    if changed_files:
        lines.extend([f"- {x}" for x in changed_files])
    else:
        lines.append("- none")

    write_text(in_dir / "reproducibility_report.latest.md", "\n".join(lines) + "\n")

    print({"status": report["status"], "missing_files": len(missing_files), "changed": len(changed_files)})
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
