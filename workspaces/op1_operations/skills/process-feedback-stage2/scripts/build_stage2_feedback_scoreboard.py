#!/usr/bin/env python3
"""Build Stage2 feedback scoreboard, quality report, alerts, and weekly snapshot."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import timezone
from pathlib import Path
from typing import Any, Dict, List

from stage2_feedback_common import (
    iso_date,
    now_iso,
    now_utc,
    parse_iso,
    read_json,
    read_jsonl,
    resolve_repo_root,
    to_float,
    write_json,
    write_text,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Stage2 feedback scoreboard")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root")
    p.add_argument(
        "--in-dir",
        default="workspaces/op1_operations/research/stage2_feedback",
        help="Input/output directory",
    )
    p.add_argument(
        "--adapters-config",
        default="workspaces/op1_operations/config/feedback_source_adapters.v1.json",
        help="Adapter config path",
    )
    p.add_argument(
        "--feedback-contract",
        default="workspaces/op1_operations/contracts/feedback_contract.v1.json",
        help="Feedback contract path",
    )
    p.add_argument(
        "--stage1-scoreboard",
        default="workspaces/op1_operations/research/stage1_tracking/stage1_scoreboard.latest.json",
        help="Stage1 scoreboard path",
    )
    return p.parse_args()


def _safe_rate(num: float, den: float) -> float:
    if den <= 0:
        return 0.0
    return num / den


def _build_markdown(scoreboard: Dict[str, Any], queue_rows: List[Dict[str, Any]], alerts: List[Dict[str, Any]]) -> str:
    summary = scoreboard.get("summary", {}) if isinstance(scoreboard.get("summary"), dict) else {}
    feedback = summary.get("feedback", {}) if isinstance(summary.get("feedback"), dict) else {}
    priority = summary.get("priority", {}) if isinstance(summary.get("priority"), dict) else {}
    loop = summary.get("loop", {}) if isinstance(summary.get("loop"), dict) else {}
    impact = summary.get("impact", {}) if isinstance(summary.get("impact"), dict) else {}

    lines = [
        "# Stage2 Feedback Scoreboard (Process feedback)",
        "",
        f"Generated at: {scoreboard.get('generated_at')}",
        f"Mode: {scoreboard.get('mode')}",
        "",
        "## Feedback volume",
        f"- feedback_events_total: {feedback.get('feedback_events_total', 0)}",
        f"- feedback_items_total: {feedback.get('feedback_items_total', 0)}",
        f"- themes_total: {feedback.get('themes_total', 0)}",
        f"- unknown_topic_rate: {feedback.get('unknown_topic_rate', 0)}",
        f"- duplicate_rate: {feedback.get('duplicate_rate', 0)}",
        "",
        "## Priority queue",
        f"- p0: {priority.get('p0_count', 0)}",
        f"- p1: {priority.get('p1_count', 0)}",
        f"- p2: {priority.get('p2_count', 0)}",
        f"- p3: {priority.get('p3_count', 0)}",
        "",
        "## Closed loop",
        f"- triaged_rate: {loop.get('triaged_rate', 0)}",
        f"- closure_rate: {loop.get('closure_rate', 0)}",
        f"- p0_untriaged: {loop.get('p0_untriaged', 0)}",
        f"- p0_unowned: {loop.get('p0_unowned', 0)}",
        "",
        "## Impact model (30d expected)",
        f"- expected_signup_delta_30d: {impact.get('expected_signup_delta_30d', 0)}",
        f"- expected_paid_delta_30d: {impact.get('expected_paid_delta_30d', 0)}",
        f"- expected_mrr_delta_30d: {impact.get('expected_mrr_delta_30d', 0)}",
        "",
        "## Top priority items",
        "",
        "| Rank | Tier | Theme | Topic | Subtopic | Priority score | Expected MRR Δ30d | Owner |",
        "|---:|---|---|---|---|---:|---:|---|",
    ]

    for row in queue_rows[:12]:
        lines.append(
            f"| {row.get('rank')} | {row.get('priority_tier')} | {row.get('theme_name') or row.get('theme_id')} | "
            f"{row.get('topic')} | {row.get('subtopic')} | {row.get('priority_score')} | "
            f"{row.get('expected_mrr_delta_30d')} | {row.get('owner')} |"
        )

    lines.append("")
    lines.append("## Alerts")
    if not alerts:
        lines.append("- none")
    else:
        for al in alerts:
            lines.append(f"- [{al.get('severity', 'info')}] {al.get('code')}: {al.get('message')}")

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else resolve_repo_root(Path(__file__))
    in_dir = repo_root / args.in_dir

    adapters_cfg = read_json(repo_root / args.adapters_config, default={}) or {}
    contract = read_json(repo_root / args.feedback_contract, default={}) or {}
    stage1 = read_json(repo_root / args.stage1_scoreboard, default={}) or {}

    raw_rows = read_jsonl(in_dir / "raw_feedback_events.latest.jsonl")
    ingest = read_json(in_dir / "feedback_ingest_report.latest.json", default={}) or {}
    normalize_report = read_json(in_dir / "feedback_normalize_report.latest.json", default={}) or {}
    scoring_report = read_json(in_dir / "feedback_scoring_report.latest.json", default={}) or {}
    queue_payload = read_json(in_dir / "feedback_priority_queue.latest.json", default={}) or {}
    loop_payload = read_json(in_dir / "feedback_loop_status.latest.json", default={}) or {}
    impact_payload = read_json(in_dir / "impact_model.latest.json", default={}) or {}
    clusters = read_json(in_dir / "theme_clusters.latest.json", default={}) or {}

    queue_rows = queue_payload.get("queue", []) if isinstance(queue_payload.get("queue"), list) else []

    thresholds = adapters_cfg.get("thresholds", {}) if isinstance(adapters_cfg.get("thresholds"), dict) else {}

    required_fields = contract.get("required_fields", []) if isinstance(contract.get("required_fields"), list) else []
    missing_required = Counter()
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        for f in required_fields:
            val = row.get(f)
            if val is None or (isinstance(val, str) and not val.strip()):
                missing_required[f] += 1

    # Freshness
    max_ts = None
    for row in raw_rows:
        ts = parse_iso(str(row.get("feedback_time") or ""))
        if ts is None:
            continue
        if max_ts is None or ts > max_ts:
            max_ts = ts

    data_lag_hours = None
    if max_ts is not None:
        data_lag_hours = round((now_utc() - max_ts.astimezone(timezone.utc)).total_seconds() / 3600.0, 4)

    feedback_events_total = len(raw_rows)
    feedback_items_total = int(normalize_report.get("item_count") or 0)
    themes_total = int(clusters.get("theme_count") or 0)

    duplicate_rate = round(_safe_rate(to_float(normalize_report.get("duplicate_events"), 0.0), to_float(normalize_report.get("event_count"), 0.0)), 4)
    unknown_topic_rate = round(to_float(normalize_report.get("unknown_topic_rate"), 0.0), 4)

    tier_counts = queue_payload.get("tier_counts", {}) if isinstance(queue_payload.get("tier_counts"), dict) else {}

    triaged_rate = round(to_float(loop_payload.get("triaged_rate"), 0.0), 4)
    closure_rate = round(to_float(loop_payload.get("closure_rate"), 0.0), 4)
    p0_untriaged = int(loop_payload.get("p0_untriaged") or 0)
    p0_unowned = int(loop_payload.get("p0_unowned") or 0)

    # Alerts
    alerts: List[Dict[str, Any]] = []

    max_dup = to_float(thresholds.get("max_duplicate_rate"), 0.25)
    max_unknown = to_float(thresholds.get("max_unknown_topic_rate"), 0.15)
    max_lag = to_float(thresholds.get("max_data_lag_hours"), 72)
    min_triaged = to_float(thresholds.get("min_triaged_rate"), 0.6)
    max_p0_untriaged = int(to_float(thresholds.get("max_p0_untriaged"), 0))
    max_unowned_p0 = int(to_float(thresholds.get("max_unowned_p0_items"), 0))

    if duplicate_rate > max_dup:
        alerts.append(
            {
                "severity": "warning",
                "code": "duplicate_rate_high",
                "message": f"Duplicate feedback rate {duplicate_rate} exceeds threshold {max_dup}.",
            }
        )

    if unknown_topic_rate > max_unknown:
        alerts.append(
            {
                "severity": "warning",
                "code": "unknown_topic_rate_high",
                "message": f"Unknown topic rate {unknown_topic_rate} exceeds threshold {max_unknown}.",
            }
        )

    if data_lag_hours is not None and data_lag_hours > max_lag:
        alerts.append(
            {
                "severity": "warning",
                "code": "feedback_data_stale",
                "message": f"Feedback data lag {data_lag_hours}h exceeds threshold {max_lag}h.",
            }
        )

    if triaged_rate < min_triaged:
        alerts.append(
            {
                "severity": "warning",
                "code": "triage_rate_low",
                "message": f"Triaged rate {triaged_rate} below threshold {min_triaged}.",
            }
        )

    if p0_untriaged > max_p0_untriaged:
        alerts.append(
            {
                "severity": "critical",
                "code": "p0_untriaged_present",
                "message": f"P0 untriaged items {p0_untriaged} exceeds threshold {max_p0_untriaged}.",
            }
        )

    if p0_unowned > max_unowned_p0:
        alerts.append(
            {
                "severity": "critical",
                "code": "p0_unowned_present",
                "message": f"P0 unowned items {p0_unowned} exceeds threshold {max_unowned_p0}.",
            }
        )

    expected_mrr_delta = to_float(impact_payload.get("total_expected_mrr_delta_30d"), 0.0)
    if expected_mrr_delta <= 0:
        alerts.append(
            {
                "severity": "warning",
                "code": "impact_non_positive",
                "message": "Expected MRR delta is non-positive; review scoring and impact assumptions.",
            }
        )

    top_topics = []
    topic_counter = Counter()
    for row in queue_rows:
        topic_counter[str(row.get("topic") or "general")] += to_float(row.get("priority_score"), 0.0)
    for k, v in topic_counter.most_common(8):
        top_topics.append({"topic": k, "weighted_priority": round(v, 4)})

    # Data quality report
    data_quality = {
        "generated_at": now_iso(),
        "feedback_events_total": feedback_events_total,
        "feedback_items_total": feedback_items_total,
        "duplicate_rate": duplicate_rate,
        "unknown_topic_rate": unknown_topic_rate,
        "data_lag_hours": data_lag_hours,
        "missing_required_fields": dict(sorted(missing_required.items())),
        "ingest_warnings": ingest.get("warnings", []),
        "events_by_adapter": ingest.get("events_by_adapter", {}),
        "feedback_type_mix": ingest.get("feedback_type_mix", {}),
    }

    # Weekly snapshot
    daily = defaultdict(lambda: {"events": 0, "negative": 0, "p0": 0})
    p0_item_ids = {
        str(r.get("feedback_item_id") or "")
        for r in queue_rows
        if str(r.get("priority_tier") or "") == "P0"
    }
    p0_item_ids.discard("")

    event_to_item = {}
    dedup = read_json(in_dir / "feedback_dedup.latest.json", default={}) or {}
    items = dedup.get("items", []) if isinstance(dedup.get("items"), list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("feedback_item_id") or "")
        for eid in (item.get("event_refs") if isinstance(item.get("event_refs"), list) else []):
            if item_id and eid:
                event_to_item[str(eid)] = item_id

    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        day = iso_date(str(row.get("feedback_time") or ""))
        daily[day]["events"] += 1
        if to_float(row.get("sentiment_score"), 0.0) < 0:
            daily[day]["negative"] += 1
        item_id = event_to_item.get(str(row.get("feedback_id") or ""))
        if item_id and item_id in p0_item_ids:
            daily[day]["p0"] += 1

    recent_days = sorted(daily.keys())[-7:]
    week_events = sum(daily[d]["events"] for d in recent_days)
    week_negative = sum(daily[d]["negative"] for d in recent_days)
    week_p0 = sum(daily[d]["p0"] for d in recent_days)

    weekly_md = "\n".join(
        [
            "# Weekly Feedback Snapshot (Stage2)",
            "",
            f"Generated at: {now_iso()}",
            "",
            "## 7-day rollup",
            f"- feedback_events: {week_events}",
            f"- negative_sentiment_events: {week_negative}",
            f"- p0_events: {week_p0}",
            f"- triaged_rate: {triaged_rate}",
            f"- expected_mrr_delta_30d: {expected_mrr_delta}",
            "",
            "## Top topics by weighted priority",
            *[f"- {r['topic']}: {r['weighted_priority']}" for r in top_topics[:5]],
            "",
            "## Actionable next steps",
            "- Assign explicit owners to all P0/P1 items and enforce SLA due dates.",
            "- Convert top objection themes into product + sales experiments with measurable KPI targets.",
            "- Close the loop by tagging shipped fixes and notifying originating leads where possible.",
        ]
    ) + "\n"

    stage1_summary = stage1.get("summary", {}) if isinstance(stage1.get("summary"), dict) else {}

    capability_status = [
        {"capability": "feedback_source_adapters", "status": "implemented", "evidence": "config/feedback_source_adapters.v1.json"},
        {"capability": "canonical_feedback_contract", "status": "implemented", "evidence": "contracts/feedback_contract.v1.json"},
        {"capability": "taxonomy_governance", "status": "implemented", "evidence": "contracts/feedback_taxonomy.v1.yaml"},
        {"capability": "normalization_dedup", "status": "implemented", "evidence": "research/stage2_feedback/feedback_dedup.latest.json"},
        {"capability": "theme_detection", "status": "implemented", "evidence": "research/stage2_feedback/theme_clusters.latest.json"},
        {"capability": "scoring", "status": "implemented", "evidence": "research/stage2_feedback/feedback_scored.latest.jsonl"},
        {"capability": "prioritization_queue", "status": "implemented", "evidence": "research/stage2_feedback/feedback_priority_queue.latest.json"},
        {"capability": "insight_briefs", "status": "implemented", "evidence": "research/stage2_feedback/insight_briefs.latest.md"},
        {"capability": "closed_loop_tracker", "status": "implemented", "evidence": "research/stage2_feedback/feedback_loop_status.latest.json"},
        {"capability": "feedback_to_kpi_impact", "status": "implemented", "evidence": "research/stage2_feedback/impact_model.latest.json"},
        {"capability": "alerts", "status": "implemented", "evidence": "research/stage2_feedback/feedback_alerts.latest.json"},
        {"capability": "data_quality", "status": "implemented", "evidence": "research/stage2_feedback/feedback_data_quality.latest.json"},
        {"capability": "scoreboard", "status": "implemented", "evidence": "research/stage2_feedback/stage2_feedback_scoreboard.latest.md"},
        {"capability": "weekly_snapshot", "status": "implemented", "evidence": "research/stage2_feedback/weekly_feedback_snapshot.latest.md"},
        {"capability": "handoff_outputs", "status": "implemented", "evidence": "handoffs/operations_to_product.json"},
    ]

    scoreboard = {
        "generated_at": now_iso(),
        "stage": "stage2_process_feedback",
        "mode": "simulated_signals",
        "inputs": {
            "raw_feedback": "workspaces/op1_operations/research/stage2_feedback/raw_feedback_events.latest.jsonl",
            "priority_queue": "workspaces/op1_operations/research/stage2_feedback/feedback_priority_queue.latest.json",
            "loop_status": "workspaces/op1_operations/research/stage2_feedback/feedback_loop_status.latest.json",
            "impact_model": "workspaces/op1_operations/research/stage2_feedback/impact_model.latest.json",
        },
        "summary": {
            "feedback": {
                "feedback_events_total": feedback_events_total,
                "feedback_items_total": feedback_items_total,
                "themes_total": themes_total,
                "unknown_topic_rate": unknown_topic_rate,
                "duplicate_rate": duplicate_rate,
            },
            "priority": {
                "p0_count": int(tier_counts.get("P0", 0)),
                "p1_count": int(tier_counts.get("P1", 0)),
                "p2_count": int(tier_counts.get("P2", 0)),
                "p3_count": int(tier_counts.get("P3", 0)),
            },
            "loop": {
                "triaged_rate": triaged_rate,
                "closure_rate": closure_rate,
                "p0_untriaged": p0_untriaged,
                "p0_unowned": p0_unowned,
            },
            "impact": {
                "expected_signup_delta_30d": round(to_float(impact_payload.get("total_expected_signup_delta_30d"), 0.0), 4),
                "expected_paid_delta_30d": round(to_float(impact_payload.get("total_expected_paid_delta_30d"), 0.0), 4),
                "expected_mrr_delta_30d": round(expected_mrr_delta, 4),
            },
            "stage1_context": {
                "visit_to_signup_rate": ((stage1_summary.get("conversion") or {}).get("visit_to_signup_rate")),
                "signup_to_paid_rate": ((stage1_summary.get("conversion") or {}).get("signup_to_paid_rate")),
                "net_new_mrr": ((stage1_summary.get("revenue") or {}).get("net_new_mrr")),
            },
            "top_topics": top_topics,
        },
        "alerts_count": len(alerts),
        "capability_status": capability_status,
        "notes": [
            "Stage2 feedback processing currently runs on simulated sales/pipeline signals with live adapter slots ready.",
            "Priority scores are explainable and tied to impact model assumptions documented in queue outputs.",
        ],
    }

    alerts_payload = {
        "generated_at": now_iso(),
        "alerts": alerts,
    }

    write_json(in_dir / "feedback_data_quality.latest.json", data_quality)
    write_json(in_dir / "feedback_alerts.latest.json", alerts_payload)
    write_json(in_dir / "stage2_feedback_scoreboard.latest.json", scoreboard)
    write_text(in_dir / "stage2_feedback_scoreboard.latest.md", _build_markdown(scoreboard, queue_rows, alerts))
    write_text(in_dir / "weekly_feedback_snapshot.latest.md", weekly_md)

    print(
        {
            "feedback_events_total": feedback_events_total,
            "feedback_items_total": feedback_items_total,
            "p0": int(tier_counts.get("P0", 0)),
            "alerts": len(alerts),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
