#!/usr/bin/env python3
"""Verify Stage1 tracking output completeness and reproducibility."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, List

from stage1_common import now_iso, read_json, sha256_file, write_json, write_text


REQUIRED_FILES = [
    "raw_events.latest.jsonl",
    "identity_map.latest.json",
    "attribution_facts.latest.json",
    "ingest_report.latest.json",
    "funnel_daily.latest.json",
    "revenue_mrr_daily.latest.json",
    "channel_scoreboard.latest.json",
    "traffic_quality_report.latest.json",
    "signup_quality_daily.latest.json",
    "data_quality_report.latest.json",
    "alerts.latest.json",
    "stage1_scoreboard.latest.json",
    "stage1_scoreboard.latest.md",
    "weekly_kpi_snapshot.latest.md",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify Stage1 tracking reproducibility")
    p.add_argument("--repo-root", default="", help="Repo root (optional)")
    p.add_argument(
        "--in-dir",
        default="workspaces/op1_operations/research/stage1_tracking",
        help="Stage1 output directory",
    )
    p.add_argument(
        "--baseline-file",
        default="workspaces/op1_operations/research/stage1_tracking/reproducibility_baseline.json",
        help="Baseline hash file",
    )
    p.add_argument("--update-baseline", action="store_true", help="Write current hashes as new baseline")
    p.add_argument("--strict", action="store_true", help="Fail when hashes differ from baseline")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[3]
    in_dir = repo_root / args.in_dir
    baseline_path = repo_root / args.baseline_file

    missing_files: List[str] = []
    hashes: Dict[str, str] = {}

    for name in REQUIRED_FILES:
        p = in_dir / name
        if not p.exists():
            missing_files.append(name)
            continue
        hashes[str(p)] = sha256_file(p)

    scoreboard = read_json(in_dir / "stage1_scoreboard.latest.json", default={}) or {}
    summary = scoreboard.get("summary", {}) if isinstance(scoreboard, dict) else {}
    traffic = summary.get("traffic", {}) if isinstance(summary, dict) else {}
    signups = summary.get("signups", {}) if isinstance(summary, dict) else {}
    revenue = summary.get("revenue", {}) if isinstance(summary, dict) else {}

    required_metric_keys = {
        "traffic": ["sessions", "unique_visitors_est", "unattributed_traffic_rate"],
        "signups": ["signups_total", "qualified_signups", "paid_customers"],
        "revenue": ["new_mrr", "net_new_mrr"],
    }

    missing_metric_keys: List[str] = []
    for key in required_metric_keys["traffic"]:
        if key not in traffic:
            missing_metric_keys.append(f"traffic.{key}")
    for key in required_metric_keys["signups"]:
        if key not in signups:
            missing_metric_keys.append(f"signups.{key}")
    for key in required_metric_keys["revenue"]:
        if key not in revenue:
            missing_metric_keys.append(f"revenue.{key}")

    baseline = read_json(baseline_path, default={}) or {}
    baseline_hashes = baseline.get("hashes", {}) if isinstance(baseline, dict) else {}

    changed_files: List[str] = []
    for path, digest in hashes.items():
        old = baseline_hashes.get(path)
        if old is None:
            continue
        if old != digest:
            changed_files.append(path)

    as_of = str(os.environ.get("STAGE1_AS_OF", "")).strip()
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
            "note": "Baseline for Stage1 reproducibility checks",
        }
        write_json(baseline_path, baseline_payload)
        report["baseline_updated"] = True

    report_path = in_dir / "reproducibility_report.latest.json"
    write_json(report_path, report)

    md_lines = [
        "# Reproducibility Report (Stage1)",
        "",
        f"Generated at: {report.get('generated_at')}",
        f"Status: {report.get('status')}",
        f"Strict mode: {report.get('strict_mode')}",
        "",
        "## Missing files",
    ]
    if missing_files:
        md_lines.extend([f"- {x}" for x in missing_files])
    else:
        md_lines.append("- none")

    md_lines.append("")
    md_lines.append("## Missing metric keys")
    if missing_metric_keys:
        md_lines.extend([f"- {x}" for x in missing_metric_keys])
    else:
        md_lines.append("- none")

    md_lines.append("")
    md_lines.append("## Changed files vs baseline")
    if changed_files:
        md_lines.extend([f"- {x}" for x in changed_files])
    else:
        md_lines.append("- none")

    write_text(in_dir / "reproducibility_report.latest.md", "\n".join(md_lines) + "\n")

    print({"status": report["status"], "missing_files": len(missing_files), "changed": len(changed_files)})
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
