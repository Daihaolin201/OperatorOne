#!/usr/bin/env python3
"""Verify Stage3 campaign launch output contract for op1_marketing."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def check(name: str, condition: bool, detail: str = "") -> Tuple[str, bool, str]:
    return (name, bool(condition), detail)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Stage3 launch contract")
    parser.add_argument("--workspace-root", default=None, help="Workspace root (defaults to script parent)")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    root = Path(args.workspace_root).resolve() if args.workspace_root else script_dir.parent.resolve()

    stage = (root / "research/stage3_campaign_launch").resolve()

    run = read_json(stage / "run.latest.json", default={}) or {}
    state = read_json(stage / "state.latest.json", default={}) or {}
    backlog = read_json(stage / "campaigns.backlog.latest.json", default={}) or {}
    queue = read_json(stage / "campaigns.queue.latest.json", default={}) or {}
    experiments = read_json(stage / "experiments.latest.json", default={}) or {}
    handoff = read_json((root / "../../handoffs/marketing_to_sales.json").resolve(), default={}) or {}

    checks: List[Tuple[str, bool, str]] = []

    checks.append(check("run_status_known", run.get("status") in {"passed", "no_change", "blocked_input_incomplete", "blocked_upstream_stage2_unhealthy", "blocked_no_launchable_assets"}, str(run.get("status"))))
    checks.append(check("run_auto_launch_false", run.get("auto_launch") is False, str(run.get("auto_launch"))))
    checks.append(check("run_launch_mode_disabled", run.get("launch_mode") == "disabled", str(run.get("launch_mode"))))

    items = backlog.get("items", []) or []
    q = queue.get("queue", {}) or {}
    counts = queue.get("counts", {}) or {}

    launch_ready = q.get("launch_ready", []) or []
    watchlist = q.get("watchlist", []) or []
    hold = q.get("hold", []) or []

    checks.append(check("queue_counts_match", int(counts.get("launch_ready", 0)) == len(launch_ready) and int(counts.get("watchlist", 0)) == len(watchlist) and int(counts.get("hold", 0)) == len(hold), json.dumps(counts, ensure_ascii=False)))

    if run.get("status") == "passed":
        stats = run.get("stats", {}) or {}
        checks.append(check("run_campaign_total_match", int(stats.get("campaigns_total", -1)) == len(items), f"run={stats.get('campaigns_total')} backlog={len(items)}"))
        checks.append(check("state_campaign_total_match", int(state.get("campaigns_total", -1)) == len(items), f"state={state.get('campaigns_total')} backlog={len(items)}"))

    exp_items = experiments.get("experiments", []) or []
    checks.append(check("experiments_match_items", len(exp_items) == len(items), f"experiments={len(exp_items)} items={len(items)}"))

    attr_path = stage / "attribution.map.latest.csv"
    checks.append(check("attribution_map_exists", attr_path.exists(), str(attr_path)))

    if attr_path.exists():
        lines = attr_path.read_text(encoding="utf-8").splitlines()
        checks.append(check("attribution_map_non_empty", len(lines) >= 1, f"lines={len(lines)}"))

    checks.append(check("handoff_campaign_launch_present", isinstance(handoff.get("campaign_launch"), dict), "campaign_launch"))

    failed = [{"name": n, "detail": d} for (n, ok, d) in checks if not ok]

    result: Dict[str, Any] = {
        "workspace_root": str(root),
        "stage_dir": str(stage),
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
        "failed": failed,
        "queue_counts": {
            "launch_ready": len(launch_ready),
            "watchlist": len(watchlist),
            "hold": len(hold),
        },
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
