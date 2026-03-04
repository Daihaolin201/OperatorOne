#!/usr/bin/env python3
"""Verify Stage2 content publish output contract for op1_marketing."""

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


def infer_workspace_root(script_file: Path) -> Path:
    # expected path:
    # <workspace>/skills/<skill-name>/scripts/verify_stage2_contract.py
    return script_file.resolve().parents[3]


def check(name: str, condition: bool, detail: str = "") -> Tuple[str, bool, str]:
    return (name, bool(condition), detail)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Stage2 content publish contract")
    parser.add_argument("--workspace-root", default=None, help="Workspace root (defaults to inferred path)")
    args = parser.parse_args()

    root = Path(args.workspace_root).resolve() if args.workspace_root else infer_workspace_root(Path(__file__))
    stage = (root / "research/stage2_content_publish").resolve()

    run = read_json(stage / "run.latest.json", default={}) or {}
    state = read_json(stage / "state.latest.json", default={}) or {}
    backlog = read_json(stage / "content.backlog.latest.json", default={}) or {}
    queue = read_json(stage / "publish.queue.latest.json", default={}) or {}
    qa = read_json(stage / "qa.latest.json", default={}) or {}
    handoff = read_json((root / "../../handoffs/marketing_to_sales.json").resolve(), default={}) or {}

    checks: List[Tuple[str, bool, str]] = []

    checks.append(check("run_status_known", run.get("status") in {"passed", "no_change", "blocked_input_incomplete", "blocked_upstream_stage1_unhealthy"}, str(run.get("status"))))
    checks.append(check("run_auto_publish_false", run.get("auto_publish") is False, str(run.get("auto_publish"))))
    checks.append(check("run_publish_mode_disabled", run.get("publish_mode") == "disabled", str(run.get("publish_mode"))))

    items = backlog.get("items", []) or []
    q = queue.get("queue", {}) or {}
    counts = queue.get("counts", {}) or {}

    approved = q.get("approved", []) or []
    review_ready = q.get("review_ready", []) or []
    needs_revision = q.get("needs_revision", []) or []
    blocked = q.get("blocked", []) or []

    checks.append(check("queue_bucket_counts", counts.get("approved", 0) == len(approved) and counts.get("review_ready", 0) == len(review_ready) and counts.get("needs_revision", 0) == len(needs_revision) and counts.get("blocked", 0) == len(blocked), json.dumps(counts, ensure_ascii=False)))

    if run.get("status") == "passed":
        checks.append(check("run_selected_matches_backlog", int((run.get("stats", {}) or {}).get("selected", -1)) == len(items), f"selected={int((run.get('stats', {}) or {}).get('selected', -1))} items={len(items)}"))

    checks.append(check("state_auto_publish_false", state.get("auto_publish") is False, str(state.get("auto_publish"))))
    checks.append(check("state_queue_consistency", int(state.get("approved", 0)) == len(approved) and int(state.get("review_ready", 0)) == len(review_ready) and int(state.get("needs_revision", 0)) == len(needs_revision), f"state={{approved:{state.get('approved')},review_ready:{state.get('review_ready')},needs_revision:{state.get('needs_revision')}}}"))

    qa_items = qa.get("items", []) or []
    checks.append(check("qa_items_match_backlog", len(qa_items) == len(items), f"qa={len(qa_items)} backlog={len(items)}"))

    checks.append(check("handoff_assets_match_backlog", len((handoff.get("content_assets", []) or [])) == len(items), f"handoff_assets={len((handoff.get('content_assets', []) or []))} backlog={len(items)}"))

    failed = [
        {"name": name, "detail": detail}
        for (name, passed, detail) in checks
        if not passed
    ]

    summary: Dict[str, Any] = {
        "workspace_root": str(root),
        "stage_dir": str(stage),
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
        "failed": failed,
        "queue_counts": {
            "approved": len(approved),
            "review_ready": len(review_ready),
            "needs_revision": len(needs_revision),
            "blocked": len(blocked),
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
