#!/usr/bin/env python3
"""
Manual review workflow for Stage2 content publishing.

This script applies human review decisions to Stage2 artifacts without auto publishing.
Actions:
- Approve review-ready items
- Request revision for review-ready items

It updates:
- research/stage2_content_publish/content.backlog.latest.json
- research/stage2_content_publish/publish.queue.latest.json
- research/stage2_content_publish/state.latest.json
- research/stage2_content_publish/review_log.latest.json
- ../../handoffs/marketing_to_sales.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set


def now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_id_values(values: List[str]) -> Set[str]:
    out: Set[str] = set()
    for raw in values or []:
        for part in str(raw).split(","):
            cid = part.strip()
            if cid:
                out.add(cid)
    return out


def update_marketing_to_sales_handoff(
    root: Path,
    generated_at: str,
    items: List[Dict[str, Any]],
) -> Path:
    handoff_path = (root / "../../handoffs/marketing_to_sales.json").resolve()
    existing = read_json(handoff_path, default={})
    if not isinstance(existing, dict):
        existing = {}

    approved = [x for x in items if x.get("queue_state") == "approved"]
    review_ready = [x for x in items if x.get("queue_state") == "review_ready"]

    content_assets = []
    seo_targets = []

    for item in items:
        content_assets.append(
            {
                "content_id": item.get("content_id"),
                "experiment_id": item.get("experiment_id"),
                "keyword": item.get("primary_keyword"),
                "intent": item.get("intent"),
                "status": item.get("queue_state", "needs_revision"),
                "format": item.get("recommended_format"),
                "title": item.get("selected_title"),
                "draft_path": item.get("draft_path"),
            }
        )
        seo_targets.append(
            {
                "keyword": item.get("primary_keyword"),
                "intent": item.get("intent"),
                "priority_score": item.get("priority_score"),
                "status": item.get("queue_state", "needs_revision"),
            }
        )

    campaigns = [
        {
            "campaign_id": f"stage2-review-{dt.datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "name": "Stage2 content publish manual review",
            "status": "review_approved" if approved else "review_only",
            "auto_publish": False,
            "assets_total": len(items),
            "assets_approved": len(approved),
            "assets_review_ready": len(review_ready),
            "generated_at": generated_at,
        }
    ]

    updated = {
        "contract_version": "1.0.0",
        "generated_at": generated_at,
        "generated_by": "workspaces/op1_marketing/scripts/review_marketing_content_stage2.py",
        "campaigns": campaigns,
        "content_assets": content_assets,
        "seo_targets": seo_targets,
        "lead_signals": {
            "top_channels": ["organic_search", "linkedin", "email_nurture"],
            "estimated_weekly_leads": max(0, len(approved) * 2),
            "note": "Shadow estimate from manually approved assets only; requires live distribution and attribution calibration.",
        },
        "offer_context": {
            "pricing": existing.get("offer_context", {}).get("pricing", ""),
            "trial_policy": existing.get("offer_context", {}).get("trial_policy", ""),
        },
    }

    write_json(handoff_path, updated)
    return handoff_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply manual review decisions to Stage2 content queue")
    parser.add_argument("--root-dir", default=None, help="Workspace root (defaults to script parent)")
    parser.add_argument("--stage-dir", default=None, help="Stage2 output directory")

    parser.add_argument("--approve", action="append", default=[], help="Approve content_id (repeatable or comma-separated)")
    parser.add_argument("--reject", action="append", default=[], help="Request revision for content_id (repeatable or comma-separated)")
    parser.add_argument("--approve-all", action="store_true", help="Approve all current review_ready items")
    parser.add_argument("--reject-all", action="store_true", help="Request revision for all current review_ready items")

    parser.add_argument("--reason", default="manual_review_requested_changes", help="Reason for rejection/revision")
    parser.add_argument("--note", default="", help="Optional reviewer note for approvals/rejections")
    parser.add_argument("--print-summary", action="store_true", help="Print compact JSON summary")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    script_dir = Path(__file__).resolve().parent
    root = Path(args.root_dir).resolve() if args.root_dir else script_dir.parent.resolve()
    stage_dir = Path(args.stage_dir).resolve() if args.stage_dir else (root / "research/stage2_content_publish").resolve()

    backlog_path = stage_dir / "content.backlog.latest.json"
    queue_path = stage_dir / "publish.queue.latest.json"
    state_path = stage_dir / "state.latest.json"
    run_path = stage_dir / "run.latest.json"
    review_log_path = stage_dir / "review_log.latest.json"

    generated_at = now_iso()

    backlog_payload = read_json(backlog_path, default={}) or {}
    queue_payload = read_json(queue_path, default={}) or {}
    state_payload = read_json(state_path, default={}) or {}
    run_payload = read_json(run_path, default={}) or {}

    if not isinstance(backlog_payload, dict) or backlog_payload.get("status") != "ok":
        raise RuntimeError("Stage2 backlog is not ready; run Stage2 pipeline first.")

    if not isinstance(queue_payload, dict) or queue_payload.get("status") != "ok":
        raise RuntimeError("Stage2 queue is not ready; run Stage2 pipeline first.")

    queue = queue_payload.get("queue", {}) or {}
    review_ready_items = queue.get("review_ready", []) or []

    review_ready_ids = {x.get("content_id") for x in review_ready_items if x.get("content_id")}

    approve_ids = parse_id_values(args.approve)
    reject_ids = parse_id_values(args.reject)

    if args.approve_all and args.reject_all:
        raise RuntimeError("--approve-all and --reject-all cannot be used together")

    if args.approve_all:
        approve_ids = set(review_ready_ids)
    if args.reject_all:
        reject_ids = set(review_ready_ids)

    if not approve_ids and not reject_ids:
        raise RuntimeError("No review action provided. Use --approve/--reject or --approve-all/--reject-all.")

    overlap = approve_ids.intersection(reject_ids)
    if overlap:
        raise RuntimeError(f"Conflicting decisions for content_ids: {sorted(overlap)}")

    invalid_for_approve = sorted([cid for cid in approve_ids if cid not in review_ready_ids])
    invalid_for_reject = sorted([cid for cid in reject_ids if cid not in review_ready_ids])
    if invalid_for_approve or invalid_for_reject:
        raise RuntimeError(
            json.dumps(
                {
                    "error": "content_id_not_in_review_ready",
                    "invalid_approve": invalid_for_approve,
                    "invalid_reject": invalid_for_reject,
                },
                ensure_ascii=False,
            )
        )

    items = backlog_payload.get("items", []) or []
    if not isinstance(items, list):
        raise RuntimeError("Invalid Stage2 backlog payload")

    approved: List[Dict[str, Any]] = []
    review_ready: List[Dict[str, Any]] = []
    needs_revision: List[Dict[str, Any]] = []

    for item in items:
        cid = item.get("content_id")
        if not cid:
            continue

        if cid in approve_ids:
            item["queue_state"] = "approved"
            item["stage_status"] = "approved"
            item["review_decision"] = {
                "decision": "approved",
                "reviewed_at": generated_at,
                "reason": "manual_approval",
                "note": args.note or "",
            }

        elif cid in reject_ids:
            item["queue_state"] = "needs_revision"
            item["stage_status"] = "needs_revision"
            item["review_decision"] = {
                "decision": "needs_revision",
                "reviewed_at": generated_at,
                "reason": args.reason,
                "note": args.note or "",
            }

        state = item.get("queue_state")
        if state == "approved":
            approved.append(item)
        elif state == "review_ready":
            review_ready.append(item)
        else:
            item["queue_state"] = "needs_revision"
            needs_revision.append(item)

    approved.sort(key=lambda x: (-float(x.get("priority_score", 0.0)), x.get("content_id", "")))
    review_ready.sort(key=lambda x: (-float(x.get("priority_score", 0.0)), x.get("content_id", "")))
    needs_revision.sort(key=lambda x: (-float(x.get("priority_score", 0.0)), x.get("content_id", "")))

    blocked = queue.get("blocked", []) or []

    backlog_payload["generated_at"] = generated_at
    backlog_payload["items"] = sorted(items, key=lambda x: (-float(x.get("priority_score", 0.0)), x.get("content_id", "")))
    backlog_payload["summary"] = {
        "selected": len(items),
        "approved": len(approved),
        "review_ready": len(review_ready),
        "needs_revision": len(needs_revision),
        "max_items": int((backlog_payload.get("summary", {}) or {}).get("max_items", len(items)) or len(items)),
        "include_hold": bool((backlog_payload.get("summary", {}) or {}).get("include_hold", False)),
        "min_score": float((backlog_payload.get("summary", {}) or {}).get("min_score", 0.0)),
    }
    backlog_payload["last_manual_review"] = {
        "at": generated_at,
        "approved": sorted(list(approve_ids)),
        "needs_revision": sorted(list(reject_ids)),
        "reason": args.reason,
        "note": args.note or "",
    }

    queue_payload["generated_at"] = generated_at
    queue_payload["status"] = "ok"
    queue_payload["auto_publish"] = False
    queue_payload["queue"] = {
        "approved": approved,
        "review_ready": review_ready,
        "needs_revision": needs_revision,
        "blocked": blocked,
    }
    queue_payload["counts"] = {
        "approved": len(approved),
        "review_ready": len(review_ready),
        "needs_revision": len(needs_revision),
        "blocked": len(blocked),
    }
    queue_payload["last_manual_review"] = {
        "at": generated_at,
        "approved": sorted(list(approve_ids)),
        "needs_revision": sorted(list(reject_ids)),
        "reason": args.reason,
        "note": args.note or "",
    }

    state_payload.update(
        {
            "loop_state": "idle_ready",
            "auto_publish": False,
            "last_run_status": "passed",
            "last_incremental_run_at": generated_at,
            "active_items": len(items),
            "approved": len(approved),
            "review_ready": len(review_ready),
            "needs_revision": len(needs_revision),
            "last_manual_review_at": generated_at,
        }
    )

    review_log = read_json(review_log_path, default={}) or {}
    if not isinstance(review_log, dict):
        review_log = {}
    entries = review_log.get("entries", []) or []
    if not isinstance(entries, list):
        entries = []

    entries.append(
        {
            "at": generated_at,
            "approved": sorted(list(approve_ids)),
            "needs_revision": sorted(list(reject_ids)),
            "reason": args.reason,
            "note": args.note or "",
            "snapshot_id": backlog_payload.get("snapshot_id"),
        }
    )

    # Keep log bounded.
    if len(entries) > 200:
        entries = entries[-200:]

    review_log_payload = {
        "generated_at": generated_at,
        "status": "ok",
        "entries": entries,
    }

    write_json(backlog_path, backlog_payload)
    write_json(queue_path, queue_payload)
    write_json(state_path, state_payload)
    write_json(review_log_path, review_log_payload)

    handoff_path = update_marketing_to_sales_handoff(root=root, generated_at=generated_at, items=items)

    if isinstance(run_payload, dict):
        run_payload["manual_review"] = {
            "at": generated_at,
            "approved": sorted(list(approve_ids)),
            "needs_revision": sorted(list(reject_ids)),
            "counts": {
                "approved": len(approved),
                "review_ready": len(review_ready),
                "needs_revision": len(needs_revision),
            },
        }
        write_json(run_path, run_payload)

    summary = {
        "status": "ok",
        "generated_at": generated_at,
        "approved_now": sorted(list(approve_ids)),
        "needs_revision_now": sorted(list(reject_ids)),
        "counts": {
            "approved": len(approved),
            "review_ready": len(review_ready),
            "needs_revision": len(needs_revision),
        },
        "handoff": str(handoff_path),
    }

    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
