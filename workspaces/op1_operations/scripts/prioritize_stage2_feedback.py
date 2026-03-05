#!/usr/bin/env python3
"""Build Stage2 feedback priority queue, loop tracker, impact model, and handoffs."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List

from stage2_feedback_common import (
    now_iso,
    now_utc,
    parse_iso,
    read_json,
    read_json_or_yaml_like,
    read_jsonl,
    resolve_repo_root,
    to_float,
    write_json,
    write_text,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prioritize Stage2 feedback items")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root")
    p.add_argument(
        "--in-dir",
        default="workspaces/op1_operations/research/stage2_feedback",
        help="Input/output directory",
    )
    p.add_argument(
        "--weights",
        default="workspaces/op1_operations/config/feedback_priority_weights.v1.yaml",
        help="Priority weights path",
    )
    p.add_argument(
        "--stage1-scoreboard",
        default="workspaces/op1_operations/research/stage1_tracking/stage1_scoreboard.latest.json",
        help="Stage1 scoreboard path",
    )
    p.add_argument(
        "--conversion-scoreboard",
        default="workspaces/op1_sales/research/conversion/conversion_scoreboard.latest.json",
        help="Sales conversion scoreboard path",
    )
    return p.parse_args()


def _status_defaults(priority_tier: str, rank: int) -> str:
    if priority_tier == "P0":
        return "triaged"
    if priority_tier == "P1":
        return "triaged"
    # Ensure top queue is actively triaged even when all items score below P1.
    if rank <= 20:
        return "triaged"
    return "new"


def _sla_hours(priority_tier: str) -> int:
    return {
        "P0": 24,
        "P1": 72,
        "P2": 168,
        "P3": 336,
    }.get(priority_tier, 336)


def _estimate_impact(
    row: Dict[str, Any],
    *,
    base: Dict[str, float],
    asp_proxy: float,
) -> Dict[str, float]:
    stage = str(row.get("journey_stage") or "unknown")
    score = to_float(row.get("priority_score"), 0.0)
    dup = max(1.0, to_float(row.get("duplicate_count"), 1.0))
    fit = max(0.4, to_float(row.get("lead_fit"), 0.65))

    visit_to_signup = max(0.001, base.get("visit_to_signup_rate", 0.01))
    signup_to_paid = max(0.01, base.get("signup_to_paid_rate", 0.06))

    expected_signup_delta = 0.0
    expected_paid_delta = 0.0
    expected_mrr_delta = 0.0

    leverage = 1.0
    if str(row.get("feedback_type") or "") in {"objection", "churn_risk", "bug", "pricing"}:
        leverage = 1.2

    if stage == "signup_to_paid":
        expected_paid_delta = max(0.05, (dup * fit * (0.05 + min(0.25, score * 0.08))))
        expected_signup_delta = expected_paid_delta / max(0.02, signup_to_paid)
    elif stage == "problem_discovery":
        expected_signup_delta = max(0.2, (dup * fit * (0.08 + min(0.3, score * 0.1))))
        expected_paid_delta = expected_signup_delta * signup_to_paid
    elif stage == "post_purchase":
        # Model as churn avoided; proxy to paid-equivalent retained.
        expected_paid_delta = max(0.03, (dup * fit * (0.03 + min(0.2, score * 0.06))))
        expected_signup_delta = expected_paid_delta / max(0.02, signup_to_paid)
    else:
        expected_signup_delta = max(0.1, dup * fit * (0.04 + min(0.15, score * 0.05)))
        expected_paid_delta = expected_signup_delta * signup_to_paid

    expected_mrr_delta = expected_paid_delta * asp_proxy * leverage

    expected_visit_to_signup_pp = expected_signup_delta / max(1.0, base.get("sessions", 1.0))
    expected_signup_to_paid_pp = expected_paid_delta / max(1.0, base.get("qualified_signups", 1.0))

    return {
        "expected_signup_delta_30d": round(expected_signup_delta, 4),
        "expected_paid_delta_30d": round(expected_paid_delta, 4),
        "expected_mrr_delta_30d": round(expected_mrr_delta, 4),
        "expected_visit_to_signup_lift_pp": round(expected_visit_to_signup_pp, 6),
        "expected_signup_to_paid_lift_pp": round(expected_signup_to_paid_pp, 6),
    }


def _brief_md(queue_rows: List[Dict[str, Any]], theme_name: Dict[str, str]) -> str:
    lines: List[str] = [
        "# Stage2 Insight Briefs (latest)",
        "",
        f"Generated at: {now_iso()}",
        "",
    ]

    for idx, row in enumerate(queue_rows[:10], start=1):
        title = theme_name.get(str(row.get("theme_id") or ""), f"{row.get('topic')} / {row.get('subtopic')}")
        lines.extend(
            [
                f"## {idx}. {title}",
                f"- feedback_item_id: {row.get('feedback_item_id')}",
                f"- priority: {row.get('priority_tier')} ({row.get('priority_score')})",
                f"- owner: {row.get('owner_team')}",
                f"- journey_stage: {row.get('journey_stage')}",
                f"- hypothesis: Fixing this theme should improve {row.get('journey_stage')} conversion efficiency.",
                f"- recommended action: {row.get('recommended_action')}",
                f"- expected signup delta (30d): {row.get('expected_signup_delta_30d')}",
                f"- expected paid delta (30d): {row.get('expected_paid_delta_30d')}",
                f"- expected MRR delta (30d): {row.get('expected_mrr_delta_30d')}",
                "- evidence:",
            ]
        )

        for ex in (row.get("evidence_examples") if isinstance(row.get("evidence_examples"), list) else [])[:3]:
            lines.append(f"  - {str(ex)}")
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else resolve_repo_root(Path(__file__))
    in_dir = repo_root / args.in_dir

    scored_rows = read_jsonl(in_dir / "feedback_scored.latest.jsonl")
    theme_clusters = read_json(in_dir / "theme_clusters.latest.json", default={}) or {}
    themes = theme_clusters.get("themes", []) if isinstance(theme_clusters.get("themes"), list) else []

    stage1 = read_json(repo_root / args.stage1_scoreboard, default={}) or {}
    conversion_score = read_json(repo_root / args.conversion_scoreboard, default={}) or {}

    weights_cfg = read_json_or_yaml_like(repo_root / args.weights, default={}) or {}

    asp_proxy = to_float((((conversion_score.get("summary") or {}).get("asp_proxy")), 49.0), 49.0)
    if asp_proxy <= 0:
        asp_proxy = 49.0

    base_summary = stage1.get("summary", {}) if isinstance(stage1.get("summary"), dict) else {}
    base_traffic = base_summary.get("traffic", {}) if isinstance(base_summary.get("traffic"), dict) else {}
    base_signups = base_summary.get("signups", {}) if isinstance(base_summary.get("signups"), dict) else {}
    base_conversion = base_summary.get("conversion", {}) if isinstance(base_summary.get("conversion"), dict) else {}

    base = {
        "sessions": to_float(base_traffic.get("sessions"), 1.0),
        "qualified_signups": to_float(base_signups.get("qualified_signups"), 1.0),
        "paid_customers": to_float(base_signups.get("paid_customers"), 1.0),
        "visit_to_signup_rate": to_float(base_conversion.get("visit_to_signup_rate"), 0.01),
        "signup_to_paid_rate": to_float(base_conversion.get("signup_to_paid_rate"), 0.06),
    }

    theme_name_map = {str(t.get("theme_id") or ""): str(t.get("theme_name") or "") for t in themes if isinstance(t, dict)}

    # Existing loop status for persistence.
    prev_loop = read_json(in_dir / "feedback_loop_status.latest.json", default={}) or {}
    prev_rows = prev_loop.get("items", []) if isinstance(prev_loop.get("items"), list) else []
    prev_map = {str(r.get("feedback_item_id") or ""): r for r in prev_rows if isinstance(r, dict)}

    queue_rows: List[Dict[str, Any]] = []
    loop_rows: List[Dict[str, Any]] = []

    now_dt = now_utc()

    for idx, row in enumerate(scored_rows, start=1):
        item_id = str(row.get("feedback_item_id") or "")
        if not item_id:
            continue
        priority_tier = str(row.get("priority_tier") or "P3")

        prev = prev_map.get(item_id, {})
        prev_status = str(prev.get("status") or "").strip()
        if prev_status:
            # Keep persisted status, but allow automatic bootstrap from new -> triaged for top queue.
            status = _status_defaults(priority_tier, idx) if prev_status == "new" else prev_status
        else:
            status = _status_defaults(priority_tier, idx)

        owner = str(prev.get("owner") or row.get("owner_team") or "operations")

        sla_hours = _sla_hours(priority_tier)
        due_dt = now_dt + timedelta(hours=sla_hours)

        impact = _estimate_impact(row, base=base, asp_proxy=asp_proxy)

        q = {
            "rank": idx,
            "feedback_item_id": item_id,
            "theme_id": row.get("theme_id"),
            "theme_name": theme_name_map.get(str(row.get("theme_id") or ""), ""),
            "topic": row.get("topic"),
            "subtopic": row.get("subtopic"),
            "feedback_type": row.get("feedback_type"),
            "journey_stage": row.get("journey_stage"),
            "priority_tier": priority_tier,
            "priority_score": row.get("priority_score"),
            "kano_label": row.get("kano_label"),
            "owner_team": row.get("owner_team"),
            "owner": owner,
            "status": status,
            "recommended_action": row.get("recommended_action"),
            "lead_ids": row.get("lead_ids") if isinstance(row.get("lead_ids"), list) else [],
            "duplicate_count": row.get("duplicate_count"),
            "unique_actor_count": row.get("unique_actor_count"),
            "first_seen": row.get("first_seen"),
            "last_seen": row.get("last_seen"),
            "sla_hours": sla_hours,
            "due_at": due_dt.replace(microsecond=0).isoformat(),
            "evidence_examples": row.get("evidence_examples") if isinstance(row.get("evidence_examples"), list) else [],
            **impact,
        }
        queue_rows.append(q)

        loop_rows.append(
            {
                "feedback_item_id": item_id,
                "theme_id": row.get("theme_id"),
                "priority_tier": priority_tier,
                "status": status,
                "owner": owner,
                "owner_team": row.get("owner_team"),
                "sla_hours": sla_hours,
                "due_at": q["due_at"],
                "first_seen": row.get("first_seen"),
                "last_seen": row.get("last_seen"),
                "last_updated": now_iso(),
                "recommended_action": row.get("recommended_action"),
            }
        )

    queue_rows = sorted(queue_rows, key=lambda r: (to_float(r.get("priority_score"), 0.0), int(r.get("duplicate_count") or 0)), reverse=True)
    for i, row in enumerate(queue_rows, start=1):
        row["rank"] = i

    loop_map = {str(r.get("feedback_item_id") or ""): r for r in loop_rows}

    triaged_status = {"triaged", "accepted", "planned", "shipped", "verified", "notified"}
    closed_status = {"verified", "notified"}

    status_counts = Counter(str(r.get("status") or "new") for r in loop_rows)
    p0_items = [r for r in loop_rows if str(r.get("priority_tier") or "") == "P0"]
    p0_untriaged = sum(1 for r in p0_items if str(r.get("status") or "") not in triaged_status)
    p0_unowned = sum(1 for r in p0_items if not str(r.get("owner") or "").strip())

    loop_payload = {
        "generated_at": now_iso(),
        "item_count": len(loop_rows),
        "status_counts": dict(sorted(status_counts.items())),
        "triaged_rate": round(sum(1 for r in loop_rows if str(r.get("status") or "") in triaged_status) / max(1, len(loop_rows)), 4),
        "closure_rate": round(sum(1 for r in loop_rows if str(r.get("status") or "") in closed_status) / max(1, len(loop_rows)), 4),
        "p0_count": len(p0_items),
        "p0_untriaged": p0_untriaged,
        "p0_unowned": p0_unowned,
        "items": loop_rows,
    }

    impact_rows = []
    for row in queue_rows:
        impact_rows.append(
            {
                "feedback_item_id": row.get("feedback_item_id"),
                "theme_id": row.get("theme_id"),
                "topic": row.get("topic"),
                "subtopic": row.get("subtopic"),
                "journey_stage": row.get("journey_stage"),
                "priority_tier": row.get("priority_tier"),
                "priority_score": row.get("priority_score"),
                "expected_signup_delta_30d": row.get("expected_signup_delta_30d"),
                "expected_paid_delta_30d": row.get("expected_paid_delta_30d"),
                "expected_mrr_delta_30d": row.get("expected_mrr_delta_30d"),
                "expected_visit_to_signup_lift_pp": row.get("expected_visit_to_signup_lift_pp"),
                "expected_signup_to_paid_lift_pp": row.get("expected_signup_to_paid_lift_pp"),
            }
        )

    total_signup = round(sum(to_float(r.get("expected_signup_delta_30d"), 0.0) for r in impact_rows), 4)
    total_paid = round(sum(to_float(r.get("expected_paid_delta_30d"), 0.0) for r in impact_rows), 4)
    total_mrr = round(sum(to_float(r.get("expected_mrr_delta_30d"), 0.0) for r in impact_rows), 4)

    impact_payload = {
        "generated_at": now_iso(),
        "base_metrics": base,
        "asp_proxy": asp_proxy,
        "total_expected_signup_delta_30d": total_signup,
        "total_expected_paid_delta_30d": total_paid,
        "total_expected_mrr_delta_30d": total_mrr,
        "rows": impact_rows,
    }

    # Priority queue output
    priority_payload = {
        "generated_at": now_iso(),
        "item_count": len(queue_rows),
        "tier_counts": dict(sorted(Counter(str(r.get("priority_tier") or "P3") for r in queue_rows).items())),
        "queue": queue_rows,
    }

    write_json(in_dir / "feedback_priority_queue.latest.json", priority_payload)
    write_json(in_dir / "feedback_loop_status.latest.json", loop_payload)
    write_json(in_dir / "impact_model.latest.json", impact_payload)
    write_text(in_dir / "insight_briefs.latest.md", _brief_md(queue_rows, theme_name_map))

    # Handoffs for downstream teams.
    product_items = []

    def _as_product_item(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "feedback_item_id": row.get("feedback_item_id"),
            "theme_id": row.get("theme_id"),
            "topic": row.get("topic"),
            "subtopic": row.get("subtopic"),
            "priority_tier": row.get("priority_tier"),
            "priority_score": row.get("priority_score"),
            "owner_team": row.get("owner_team"),
            "recommended_action": row.get("recommended_action"),
            "expected_mrr_delta_30d": row.get("expected_mrr_delta_30d"),
            "evidence_examples": row.get("evidence_examples"),
        }

    for row in queue_rows:
        if str(row.get("priority_tier") or "") not in {"P0", "P1"}:
            continue
        product_items.append(_as_product_item(row))

    # Fallback: if queue has no P0/P1, still hand off top-ranked items.
    if not product_items:
        for row in queue_rows[:10]:
            product_items.append(_as_product_item(row))

    marketing_signals = defaultdict(float)
    sales_objections = defaultdict(int)
    for row in queue_rows:
        topic = str(row.get("topic") or "general")
        marketing_signals[topic] += to_float(row.get("priority_score"), 0.0)
        if str(row.get("feedback_type") or "") in {"objection", "pricing", "churn_risk"}:
            key = f"{row.get('topic')}::{row.get('subtopic')}"
            sales_objections[key] += int(to_float(row.get("duplicate_count"), 1.0))

    handoff_product = {
        "generated_at": now_iso(),
        "from": "op1_operations.stage2_feedback",
        "objective": "prioritized_feedback_backlog",
        "items": product_items[:20],
        "notes": "Items are sorted by Stage2 priority score and expected 30d MRR leverage.",
    }

    handoff_marketing = {
        "generated_at": now_iso(),
        "from": "op1_operations.stage2_feedback",
        "objective": "message_and_content_adjustments",
        "top_signal_topics": [
            {"topic": k, "weighted_score": round(v, 4)}
            for k, v in sorted(marketing_signals.items(), key=lambda x: x[1], reverse=True)[:10]
        ],
        "recommendations": [
            "Increase trust proof in top-of-funnel messaging for high negative trust themes.",
            "Add pricing clarity + ROI examples where budget objections concentrate.",
            "Publish onboarding walkthroughs for manual-work and setup-friction themes.",
        ],
    }

    handoff_sales = {
        "generated_at": now_iso(),
        "from": "op1_operations.stage2_feedback",
        "objective": "objection_playbook_refresh",
        "objection_counts": [
            {"objection_key": k, "count": v}
            for k, v in sorted(sales_objections.items(), key=lambda x: x[1], reverse=True)[:15]
        ],
        "talk_tracks": [
            "For budget objections: start with scoped pilot + explicit ROI checkpoint in 14 days.",
            "For competitor lock-in: position migration-lite workflow and no-rip-and-replace path.",
            "For trust risk: lead with controls, auditability, and risk mitigation proof points.",
        ],
    }

    write_json(repo_root / "handoffs/operations_to_product.json", handoff_product)
    write_json(repo_root / "handoffs/operations_to_marketing.json", handoff_marketing)
    write_json(repo_root / "handoffs/operations_to_sales.json", handoff_sales)

    print(
        {
            "queue_items": len(queue_rows),
            "p0": priority_payload["tier_counts"].get("P0", 0),
            "p1": priority_payload["tier_counts"].get("P1", 0),
            "expected_mrr_delta_30d": total_mrr,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
