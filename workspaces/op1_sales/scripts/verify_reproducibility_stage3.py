#!/usr/bin/env python3
"""Verify Stage3 convert-early-customers reproducibility.

Reproducibility definition:
- With identical inputs and fixed --as-of timestamp,
  two simulate runs produce byte-identical core output artifacts.
- Core structural checks (DoD subset) stay true.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from conversion_stage3_common import find_repo_root, now_iso, read_json, read_jsonl, write_json  # noqa: E402


def _run(cmd: List[str], cwd: Path) -> None:
    proc = subprocess.run(cmd, cwd=str(cwd), text=True)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _file_hashes(paths: List[Path]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for p in paths:
        out[str(p)] = _sha256(p) if p.exists() else ""
    return out


def _dod_checks(repo_root: Path, conv_dir: Path) -> Dict[str, Any]:
    required = [
        conv_dir / "conversion_pipeline.latest.json",
        conv_dir / "close_motion.latest.md",
        conv_dir / "pilot_onboarding.latest.json",
        conv_dir / "conversion_events.latest.jsonl",
        conv_dir / "objection_playbook.latest.md",
        conv_dir / "conversion_scoreboard.latest.md",
    ]

    pipeline = read_json(conv_dir / "conversion_pipeline.latest.json", default={})
    onboarding = read_json(conv_dir / "pilot_onboarding.latest.json", default={})
    scoreboard = read_json(conv_dir / "conversion_scoreboard.latest.json", default={})
    events = read_jsonl(conv_dir / "conversion_events.latest.jsonl")
    signal_inbox = read_json(conv_dir / "conversion_signal_inbox.latest.json", default={})

    active = [x for x in (pipeline.get("leads", []) or []) if str(x.get("current_stage", "")) not in {"paid_started", "closed_lost"}]
    active_missing = [
        x.get("lead_id", "")
        for x in active
        if not str(x.get("next_best_action", "")).strip() or not str(x.get("next_action_due_at", "")).strip()
    ]

    stage_history_missing = [x.get("lead_id", "") for x in (pipeline.get("leads", []) or []) if not x.get("stage_history")]

    pilot_missing = [
        p.get("lead_id", "")
        for p in (onboarding.get("pilots", []) or [])
        if "ttfv_hours" not in p or "onboarding_risk" not in p
    ]

    score_required = {
        "qualified_interest_to_pilot_rate",
        "pilot_to_commitment_rate",
        "commitment_to_paid_start_rate",
        "median_time_to_first_value_hours",
        "median_time_to_paid_start_hours",
        "new_customers_converted",
        "new_business_mrr_proxy",
        "asp_proxy",
        "objection_resolution_rate",
        "closed_lost_reason_mix",
        "opt_out_rate",
        "onboarding_stall_rate",
        "no_response_after_terms_rate",
        "stage_counts",
    }
    summary = scoreboard.get("summary", {}) or {}
    missing_score = sorted([k for k in score_required if k not in summary])

    event_types = {str(e.get("event_type", "")) for e in events}

    return {
        "required_outputs_exist": all(p.exists() for p in required),
        "missing_outputs": [str(p) for p in required if not p.exists()],
        "events_count": len(events),
        "stage_history_traceability_ok": len(stage_history_missing) == 0 and len(events) > 0,
        "active_leads_have_next_action_ok": len(active_missing) == 0,
        "onboarding_fields_ok": len(pilot_missing) == 0,
        "supports_commitment_signal_type": "commitment_received" in (signal_inbox.get("allowed_signal_types", []) or []),
        "paid_and_lost_event_observed": ("paid_started" in event_types and "closed_lost" in event_types),
        "objection_playbook_exists_and_nonempty": (conv_dir / "objection_playbook.latest.md").exists() and (conv_dir / "objection_playbook.latest.md").stat().st_size > 0,
        "scoreboard_metrics_complete": len(missing_score) == 0,
        "stage_history_missing": stage_history_missing,
        "active_missing_next_action": active_missing,
        "pilot_missing_fields": pilot_missing,
        "scoreboard_missing_keys": missing_score,
    }


def _write_md(path: Path, payload: Dict[str, Any]) -> None:
    checks = payload.get("checks", {})

    lines = [
        "# Stage3 Reproducibility Report",
        "",
        f"Generated at: {payload.get('generated_at', '')}",
        f"As-of timestamp: {payload.get('as_of', '')}",
        f"Reproducible: {payload.get('reproducible', False)}",
        "",
        "## Hash comparison",
        "",
        "| File | Run1 hash | Run2 hash | Match |",
        "|---|---|---|---|",
    ]

    run1 = payload.get("hashes", {}).get("run1", {})
    run2 = payload.get("hashes", {}).get("run2", {})

    for file_path in sorted(set(run1.keys()) | set(run2.keys())):
        h1 = run1.get(file_path, "")
        h2 = run2.get(file_path, "")
        lines.append(f"| {file_path} | {h1} | {h2} | {h1 == h2} |")

    lines.extend(["", "## DoD subset checks", ""])
    for k, v in checks.items():
        if isinstance(v, (list, dict)):
            continue
        lines.append(f"- {k}: {v}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify Stage3 reproducibility")
    p.add_argument("--repo-root", type=str, default="", help="OperatorOne repo root")
    p.add_argument(
        "--as-of",
        type=str,
        default="2026-03-05T00:00:00+00:00",
        help="Fixed ISO timestamp used for deterministic simulate runs.",
    )
    p.add_argument("--python", type=str, default="python3", help="Python executable")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    conv_dir = repo_root / "workspaces" / "op1_sales" / "research" / "conversion"
    conv_dir.mkdir(parents=True, exist_ok=True)

    runner = repo_root / "workspaces" / "op1_sales" / "scripts" / "run_convert_early_customers_stage3.py"
    cmd = [args.python, str(runner), "--repo-root", str(repo_root), "--mode", "simulate", "--as-of", args.as_of]

    _run(cmd, cwd=repo_root)

    target_files = [
        conv_dir / "conversion_signal_processing.latest.json",
        conv_dir / "conversion_pipeline.latest.json",
        conv_dir / "close_motion.latest.json",
        conv_dir / "pilot_onboarding.latest.json",
        conv_dir / "conversion_scoreboard.latest.json",
        conv_dir / "objection_playbook.latest.md",
    ]

    hashes_run1 = _file_hashes(target_files)

    _run(cmd, cwd=repo_root)
    hashes_run2 = _file_hashes(target_files)

    reproducible = hashes_run1 == hashes_run2

    checks = _dod_checks(repo_root, conv_dir)

    report = {
        "generated_at": now_iso(),
        "builder": "workspaces/op1_sales/scripts/verify_reproducibility_stage3.py",
        "as_of": args.as_of,
        "reproducible": reproducible,
        "hashes": {"run1": hashes_run1, "run2": hashes_run2},
        "checks": checks,
    }

    out_json = conv_dir / "reproducibility_report.latest.json"
    out_md = conv_dir / "reproducibility_report.latest.md"
    write_json(out_json, report)
    _write_md(out_md, report)

    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_md}")

    if not reproducible:
        print("Reproducibility check failed: hashes differ.")
        return 2

    critical_checks = [
        "required_outputs_exist",
        "stage_history_traceability_ok",
        "active_leads_have_next_action_ok",
        "onboarding_fields_ok",
        "supports_commitment_signal_type",
        "scoreboard_metrics_complete",
    ]

    if any(not checks.get(k, False) for k in critical_checks):
        print("Reproducibility check failed: critical DoD subset check did not pass.")
        return 3

    print("Reproducibility check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
