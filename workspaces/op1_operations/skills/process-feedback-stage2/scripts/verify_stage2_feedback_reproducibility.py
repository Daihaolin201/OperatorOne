#!/usr/bin/env python3
"""Verify Stage2 feedback outputs for completeness and reproducibility."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, List

from stage2_feedback_common import now_iso, read_json, resolve_repo_root, sha256_file, write_json, write_text


REQUIRED_OUTPUT_FILES = [
    "raw_feedback_events.latest.jsonl",
    "feedback_ingest_report.latest.json",
    "feedback_normalized.latest.jsonl",
    "feedback_dedup.latest.json",
    "feedback_normalize_report.latest.json",
    "theme_clusters.latest.json",
    "feedback_scored.latest.jsonl",
    "feedback_scoring_report.latest.json",
    "feedback_priority_queue.latest.json",
    "feedback_loop_status.latest.json",
    "impact_model.latest.json",
    "insight_briefs.latest.md",
    "feedback_data_quality.latest.json",
    "feedback_alerts.latest.json",
    "stage2_feedback_scoreboard.latest.json",
    "stage2_feedback_scoreboard.latest.md",
    "weekly_feedback_snapshot.latest.md",
]

REQUIRED_HANDOFF_FILES = [
    "handoffs/operations_to_product.json",
    "handoffs/operations_to_marketing.json",
    "handoffs/operations_to_sales.json",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify Stage2 feedback reproducibility")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root")
    p.add_argument(
        "--in-dir",
        default="workspaces/op1_operations/research/stage2_feedback",
        help="Stage2 output directory",
    )
    p.add_argument(
        "--baseline-file",
        default="workspaces/op1_operations/research/stage2_feedback/reproducibility_baseline.json",
        help="Baseline hashes file",
    )
    p.add_argument("--update-baseline", action="store_true", help="Write current hash set as baseline")
    p.add_argument("--strict", action="store_true", help="Fail if files changed vs baseline")
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

    scoreboard = read_json(in_dir / "stage2_feedback_scoreboard.latest.json", default={}) or {}
    summary = scoreboard.get("summary", {}) if isinstance(scoreboard.get("summary"), dict) else {}

    required_metric_keys = [
        "feedback.feedback_events_total",
        "feedback.feedback_items_total",
        "feedback.themes_total",
        "priority.p0_count",
        "loop.triaged_rate",
        "impact.expected_mrr_delta_30d",
    ]

    missing_metric_keys: List[str] = []

    feedback = summary.get("feedback", {}) if isinstance(summary.get("feedback"), dict) else {}
    priority = summary.get("priority", {}) if isinstance(summary.get("priority"), dict) else {}
    loop = summary.get("loop", {}) if isinstance(summary.get("loop"), dict) else {}
    impact = summary.get("impact", {}) if isinstance(summary.get("impact"), dict) else {}

    if "feedback_events_total" not in feedback:
        missing_metric_keys.append("feedback.feedback_events_total")
    if "feedback_items_total" not in feedback:
        missing_metric_keys.append("feedback.feedback_items_total")
    if "themes_total" not in feedback:
        missing_metric_keys.append("feedback.themes_total")
    if "p0_count" not in priority:
        missing_metric_keys.append("priority.p0_count")
    if "triaged_rate" not in loop:
        missing_metric_keys.append("loop.triaged_rate")
    if "expected_mrr_delta_30d" not in impact:
        missing_metric_keys.append("impact.expected_mrr_delta_30d")

    baseline = read_json(baseline_path, default={}) or {}
    baseline_hashes = baseline.get("hashes", {}) if isinstance(baseline.get("hashes"), dict) else {}

    changed_files: List[str] = []
    for path, digest in hashes.items():
        old = baseline_hashes.get(path)
        if old is None:
            continue
        if old != digest:
            changed_files.append(path)

    as_of = str(os.environ.get("STAGE2_AS_OF", "")).strip()
    strict_mode = bool(args.strict or (as_of and baseline_hashes))

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
            "note": "Baseline for Stage2 reproducibility checks",
        }
        write_json(baseline_path, baseline_payload)
        report["baseline_updated"] = True

    write_json(in_dir / "reproducibility_report.latest.json", report)

    lines = [
        "# Reproducibility Report (Stage2 feedback)",
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
