#!/usr/bin/env python3
"""One-command orchestration for Stage3 convert-early-customers capability."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from conversion_stage3_common import find_repo_root  # noqa: E402


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, env=env)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Stage3 convert-early-customers end-to-end")
    p.add_argument("--repo-root", type=str, default="", help="OperatorOne repo root")
    p.add_argument("--mode", type=str, default="commit", choices=["simulate", "commit"], help="commit updates events + handoff")
    p.add_argument("--python", type=str, default="python3", help="Python executable")
    p.add_argument(
        "--as-of",
        type=str,
        default="",
        help="Optional fixed ISO8601 timestamp for reproducible runs (sets STAGE3_AS_OF).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())

    env = os.environ.copy()
    if args.as_of:
        env["STAGE3_AS_OF"] = args.as_of
        print(f"Using fixed as-of timestamp: {args.as_of}")

    scripts = [
        ("process_conversion_events_stage3.py", ["--mode", args.mode]),
        ("build_conversion_pipeline_stage3.py", []),
        ("build_close_motion_stage3.py", []),
        ("track_pilot_onboarding_stage3.py", []),
        ("render_conversion_scoreboard_stage3.py", ["--mode", args.mode]),
    ]

    for script_name, extra in scripts:
        script_path = repo_root / "workspaces" / "op1_sales" / "scripts" / script_name
        cmd = [args.python, str(script_path), "--repo-root", str(repo_root), *extra]
        _run(cmd, cwd=repo_root, env=env)

    print("\nStage3 convert-early-customers run complete.")
    print("Key outputs:")
    base = "workspaces/op1_sales/research/conversion"
    for rel in [
        f"{base}/conversion_events.latest.jsonl",
        f"{base}/conversion_pipeline.latest.json",
        f"{base}/close_motion.latest.md",
        f"{base}/pilot_onboarding.latest.json",
        f"{base}/objection_playbook.latest.md",
        f"{base}/conversion_scoreboard.latest.md",
    ]:
        print("-", rel)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
