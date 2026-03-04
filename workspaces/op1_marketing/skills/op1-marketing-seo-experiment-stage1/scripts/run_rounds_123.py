#!/usr/bin/env python3
"""
Run Stage1 SEO validation rounds (1/2/3) for op1_marketing.

Rounds:
1) Baseline
2) Controlled handoff perturbation
3) Restore baseline and rerun (reproducibility)

Outputs are written to:
  research/stage1_marketing_seo/rounds/<timestamp>/
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

KEY_ARTIFACTS = [
    "run.latest.json",
    "state.latest.json",
    "context_index.latest.json",
    "keyword_graph.latest.csv",
    "experiments.backlog.latest.json",
    "experiments.queue.latest.json",
    "scoreboard.latest.json",
    "decision_log.latest.md",
]


def now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def stamp() -> str:
    return dt.datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(payload: Any) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def infer_workspace_root(script_file: Path) -> Path:
    # expected: <workspace>/skills/<skill-name>/scripts/run_rounds_123.py
    return script_file.resolve().parents[3]


def build_round2_handoff(original: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = dict(original or {})

    payload.update(
        {
            "status": "selected_for_seo_shadow_test",
            "idea_name": "invoice-followup-automation",
            "icp": "SMB agencies and bookkeeping teams sending recurring invoices",
            "problem": "Invoice follow-up is manual, late, and inconsistent, causing delayed cash collection.",
            "mvp_scope": [
                "Automated reminder schedule",
                "Escalation rules by due date",
                "Simple payment-link follow-up templates",
            ],
            "landing_page_url_or_path": "/landing/invoice-followup-automation",
            "positioning": {
                "headline": "Get paid faster without awkward manual chasing",
                "value_proposition": "Automate invoice follow-ups with smart timing and clear payment nudges.",
            },
            "constraints": {
                "budget": 500,
                "timeline_days": 14,
            },
            "notes": "Round2 controlled perturbation for Stage1 SEO queue stability testing.",
        }
    )
    return payload


def run_stage1_once(workspace_root: Path, mode: str) -> Dict[str, Any]:
    cmd = [
        str((workspace_root / "scripts/run_marketing_seo_stage1.sh").resolve()),
        "--mode",
        mode,
        "--force",
    ]

    proc = subprocess.run(cmd, cwd=str(workspace_root), text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "Stage1 run failed: "
            + json.dumps(
                {
                    "returncode": proc.returncode,
                    "stdout_tail": "\n".join(proc.stdout.splitlines()[-20:]),
                    "stderr_tail": "\n".join(proc.stderr.splitlines()[-20:]),
                },
                ensure_ascii=False,
            )
        )

    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        return {"status": "unknown", "note": "no stdout"}

    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        return {"status": "unknown", "note": "summary parse failed", "raw_summary": lines[-1]}


def snapshot_round(
    stage_dir: Path,
    round_dir: Path,
    label: str,
    run_summary: Dict[str, Any],
) -> Dict[str, Any]:
    round_path = round_dir / label
    round_path.mkdir(parents=True, exist_ok=True)

    artifact_hashes: Dict[str, Dict[str, Any]] = {}
    for rel in KEY_ARTIFACTS:
        src = stage_dir / rel
        if not src.exists() or not src.is_file():
            continue
        dst = round_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        artifact_hashes[rel] = {
            "sha256": sha256_file(dst),
            "size_bytes": dst.stat().st_size,
        }

    briefs_src = stage_dir / "briefs"
    briefs_dst = round_path / "briefs"
    if briefs_src.exists() and briefs_src.is_dir():
        if briefs_dst.exists():
            shutil.rmtree(briefs_dst)
        shutil.copytree(briefs_src, briefs_dst)

    queue_payload = read_json(stage_dir / "experiments.queue.latest.json", default={}) or {}
    scoreboard = read_json(stage_dir / "scoreboard.latest.json", default={}) or {}

    queue_content = queue_payload.get("queue", {}) or {}
    queue_content_hash = sha256_json(queue_content)

    top_ready: List[Dict[str, Any]] = []
    for item in queue_content.get("ready", [])[:5]:
        top_ready.append(
            {
                "experiment_id": item.get("experiment_id"),
                "keyword": item.get("keyword"),
                "overall_score": item.get("overall_score"),
                "confidence": item.get("confidence"),
            }
        )

    record = {
        "label": label,
        "ran_at": now_iso(),
        "summary": run_summary,
        "counts": queue_payload.get("counts", {}),
        "scoreboard_summary": scoreboard.get("summary", {}),
        "top_ready": top_ready,
        "artifact_hashes": artifact_hashes,
        "derived_hashes": {
            "queue_content": queue_content_hash,
        },
    }
    write_json(round_path / "round.summary.json", record)
    return record


def get_hash(record: Dict[str, Any], rel_path: str) -> str:
    return ((record.get("artifact_hashes", {}) or {}).get(rel_path, {}) or {}).get("sha256", "")


def get_derived_hash(record: Dict[str, Any], key: str) -> str:
    return ((record.get("derived_hashes", {}) or {}).get(key, ""))


def write_markdown_report(run_dir: Path, rounds: List[Dict[str, Any]], checks: Dict[str, bool]) -> None:
    lines: List[str] = [
        "# Stage1 SEO Rounds 1/2/3 Report",
        "",
        f"- Generated: {now_iso()}",
        f"- Run dir: `{run_dir}`",
        "",
        "## Round snapshots",
    ]

    for item in rounds:
        score_summary = item.get("scoreboard_summary", {}) or {}
        counts = item.get("counts", {}) or {}
        summary = item.get("summary", {}) or {}
        lines.extend(
            [
                f"### {item.get('label')}",
                f"- Status: `{summary.get('status')}`",
                f"- Contexts: **{summary.get('context_count')}**",
                f"- Keywords: **{summary.get('keyword_count')}**",
                f"- Experiments: **{summary.get('experiment_count')}**",
                f"- Queue: Ready **{counts.get('ready', 0)}** / Hold **{counts.get('hold', 0)}** / Drop **{counts.get('drop', 0)}**",
                f"- Avg overall score: **{score_summary.get('avg_overall_score')}**",
                "",
            ]
        )

    lines.extend(
        [
            "## Validation checks",
            f"- R1 vs R3 queue counts equal: **{checks.get('r1_vs_r3_queue_counts_equal')}**",
            f"- R1 vs R3 scoreboard summary equal: **{checks.get('r1_vs_r3_scoreboard_summary_equal')}**",
            f"- R1 vs R3 keyword graph hash equal: **{checks.get('r1_vs_r3_keyword_graph_hash_equal')}**",
            f"- R1 vs R3 queue content hash equal: **{checks.get('r1_vs_r3_queue_content_hash_equal')}**",
            f"- R2 differs from R1 queue content hash: **{checks.get('r2_differs_from_r1_queue_content_hash')}**",
            "",
        ]
    )

    (run_dir / "rounds_1_2_3.report.md").write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage1 SEO validation rounds 1/2/3")
    parser.add_argument("--workspace-root", default=None, help="Workspace root (defaults to inferred path)")
    parser.add_argument("--mode", default="shadow", choices=["shadow", "live"], help="Pipeline mode")
    parser.add_argument("--sleep-seconds", type=float, default=1.2, help="Sleep between rounds to avoid same-second IDs")
    parser.add_argument("--strict", dest="strict", action="store_true", default=True, help="Exit non-zero when checks fail")
    parser.add_argument("--no-strict", dest="strict", action="store_false", help="Do not fail process when checks fail")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    workspace_root = Path(args.workspace_root).resolve() if args.workspace_root else infer_workspace_root(Path(__file__))
    stage_dir = (workspace_root / "research/stage1_marketing_seo").resolve()
    handoff_path = (workspace_root / "../../handoffs/product_to_marketing.json").resolve()

    runner = (workspace_root / "scripts/run_marketing_seo_stage1.sh").resolve()
    if not runner.exists():
        raise FileNotFoundError(f"Stage1 runner not found: {runner}")
    if not handoff_path.exists():
        raise FileNotFoundError(f"Handoff file not found: {handoff_path}")

    run_dir = stage_dir / "rounds" / stamp()
    run_dir.mkdir(parents=True, exist_ok=True)

    original_handoff_text = handoff_path.read_text(encoding="utf-8")
    original_handoff_data = read_json(handoff_path, default={})
    if not isinstance(original_handoff_data, dict):
        original_handoff_data = {}

    rounds: List[Dict[str, Any]] = []

    try:
        r1_summary = run_stage1_once(workspace_root, mode=args.mode)
        rounds.append(snapshot_round(stage_dir, run_dir, "round1_baseline", r1_summary))

        time.sleep(max(0.0, args.sleep_seconds))

        round2_handoff = build_round2_handoff(original_handoff_data)
        handoff_path.write_text(json.dumps(round2_handoff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        r2_summary = run_stage1_once(workspace_root, mode=args.mode)
        rounds.append(snapshot_round(stage_dir, run_dir, "round2_input_shift", r2_summary))

        time.sleep(max(0.0, args.sleep_seconds))

        handoff_path.write_text(original_handoff_text, encoding="utf-8")
        r3_summary = run_stage1_once(workspace_root, mode=args.mode)
        rounds.append(snapshot_round(stage_dir, run_dir, "round3_restore_repro", r3_summary))

    finally:
        handoff_path.write_text(original_handoff_text, encoding="utf-8")

    if len(rounds) != 3:
        raise RuntimeError("Expected 3 round snapshots")

    r1, r2, r3 = rounds
    checks = {
        "r1_vs_r3_queue_counts_equal": (r1.get("counts") == r3.get("counts")),
        "r1_vs_r3_scoreboard_summary_equal": (r1.get("scoreboard_summary") == r3.get("scoreboard_summary")),
        "r1_vs_r3_keyword_graph_hash_equal": (get_hash(r1, "keyword_graph.latest.csv") == get_hash(r3, "keyword_graph.latest.csv")),
        "r1_vs_r3_queue_content_hash_equal": (get_derived_hash(r1, "queue_content") == get_derived_hash(r3, "queue_content")),
        "r2_differs_from_r1_queue_content_hash": (get_derived_hash(r2, "queue_content") != get_derived_hash(r1, "queue_content")),
    }

    report = {
        "generated_at": now_iso(),
        "run_dir": str(run_dir),
        "rounds": rounds,
        "checks": checks,
    }
    write_json(run_dir / "rounds_1_2_3.report.json", report)
    write_markdown_report(run_dir, rounds, checks)

    required = [
        "r1_vs_r3_queue_counts_equal",
        "r1_vs_r3_scoreboard_summary_equal",
        "r1_vs_r3_keyword_graph_hash_equal",
        "r1_vs_r3_queue_content_hash_equal",
        "r2_differs_from_r1_queue_content_hash",
    ]
    passed = all(bool(checks.get(k)) for k in required)

    summary = {
        "ok": passed,
        "run_dir": str(run_dir),
        "round1": rounds[0].get("counts", {}),
        "round2": rounds[1].get("counts", {}),
        "round3": rounds[2].get("counts", {}),
        "checks": checks,
    }
    print(json.dumps(summary, ensure_ascii=False))

    if args.strict and not passed:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
