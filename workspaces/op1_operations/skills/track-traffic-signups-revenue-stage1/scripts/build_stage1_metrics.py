#!/usr/bin/env python3
"""Compute Stage1 metrics, quality reports, and scoreboards."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from stage1_common import (
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

TRAFFIC_EVENTS = {"session_observed"}
QUALIFIED_SIGNUP_EVENTS = {"signup_qualified"}
SIGNUP_EVENTS = {"signup_captured", "signup_qualified", "paid_started"}
PAID_EVENTS = {"paid_started"}
MRR_EVENTS = {"mrr_movement"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Stage1 tracking metrics")
    p.add_argument("--repo-root", default="", help="Repo root (optional)")
    p.add_argument(
        "--in-dir",
        default="workspaces/op1_operations/research/stage1_tracking",
        help="Input/output directory containing raw_events.latest.jsonl",
    )
    p.add_argument(
        "--adapters-config",
        default="workspaces/op1_operations/config/source_adapters.v1.json",
        help="Adapter config path",
    )
    return p.parse_args()


def _safe_rate(num: float, den: float) -> float:
    if den <= 0:
        return 0.0
    return num / den


def _movement_buckets() -> Dict[str, float]:
    return {
        "new_business": 0.0,
        "expansion": 0.0,
        "contraction": 0.0,
        "churn": 0.0,
        "reactivation": 0.0,
    }


def _movement_apply(bucket: Dict[str, float], movement_type: str, delta: float) -> None:
    t = movement_type.strip().lower()
    if t not in bucket:
        return
    if t in {"contraction", "churn"}:
        bucket[t] += abs(delta)
    else:
        bucket[t] += delta


def _channel_key(ev: Dict[str, Any]) -> Tuple[str, str, str]:
    source = str(ev.get("event_source") or "unknown").strip().lower() or "unknown"
    medium = str(ev.get("event_medium") or "unknown").strip().lower() or "unknown"
    campaign = str(ev.get("campaign_id") or "unknown").strip() or "unknown"
    return source, medium, campaign


def _identity(ev: Dict[str, Any]) -> str:
    for k in ["lead_id", "user_id", "distinct_id", "anonymous_id", "event_id"]:
        val = str(ev.get(k) or "").strip()
        if val:
            return val
    return "unknown"


def build_markdown(scoreboard: Dict[str, Any], top_channels: List[Dict[str, Any]], alerts: List[Dict[str, Any]]) -> str:
    traffic = scoreboard.get("summary", {}).get("traffic", {})
    signup = scoreboard.get("summary", {}).get("signups", {})
    revenue = scoreboard.get("summary", {}).get("revenue", {})
    conversion = scoreboard.get("summary", {}).get("conversion", {})
    milestone = scoreboard.get("summary", {}).get("milestone", {})

    lines = [
        "# Stage1 Scoreboard (Track traffic, signups, revenue)",
        "",
        f"Generated at: {scoreboard.get('generated_at')}",
        f"Mode: {scoreboard.get('mode')}",
        "",
        "## Traffic",
        f"- sessions: {traffic.get('sessions', 0)}",
        f"- unique_visitors_est: {traffic.get('unique_visitors_est', 0)}",
        f"- unattributed_traffic_rate: {traffic.get('unattributed_traffic_rate', 0)}",
        "",
        "## Signups",
        f"- signups_total: {signup.get('signups_total', 0)}",
        f"- qualified_signups: {signup.get('qualified_signups', 0)}",
        f"- paid_customers: {signup.get('paid_customers', 0)}",
        "",
        "## Revenue",
        f"- new_mrr: {revenue.get('new_mrr', 0)}",
        f"- expansion_mrr: {revenue.get('expansion_mrr', 0)}",
        f"- contraction_mrr: {revenue.get('contraction_mrr', 0)}",
        f"- churn_mrr: {revenue.get('churn_mrr', 0)}",
        f"- reactivation_mrr: {revenue.get('reactivation_mrr', 0)}",
        f"- net_new_mrr: {revenue.get('net_new_mrr', 0)}",
        "",
        "## Conversion",
        f"- visit_to_signup_rate: {conversion.get('visit_to_signup_rate', 0)}",
        f"- signup_to_paid_rate: {conversion.get('signup_to_paid_rate', 0)}",
        f"- visit_to_paid_rate: {conversion.get('visit_to_paid_rate', 0)}",
        "",
        "## Milestone",
        f"- target_mrr: {milestone.get('target_mrr', 100)}",
        f"- achieved_mrr: {milestone.get('achieved_mrr', 0)}",
        f"- progress_ratio: {milestone.get('progress_ratio', 0)}",
        "",
        "## Top channels",
        "",
        "| Source | Medium | Campaign | Sessions | Qualified Signups | Paid | New MRR |",
        "|---|---|---|---:|---:|---:|---:|",
    ]

    for row in top_channels[:10]:
        lines.append(
            f"| {row.get('source')} | {row.get('medium')} | {row.get('campaign_id')} | "
            f"{row.get('sessions', 0)} | {row.get('qualified_signups', 0)} | {row.get('paid_customers', 0)} | {row.get('new_mrr', 0)} |"
        )

    lines.append("")
    lines.append("## Alerts")
    if not alerts:
        lines.append("- none")
    else:
        for alert in alerts:
            lines.append(f"- [{alert.get('severity', 'info')}] {alert.get('code')}: {alert.get('message')}")

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else resolve_repo_root(Path(__file__))
    in_dir = repo_root / args.in_dir
    cfg = read_json(repo_root / args.adapters_config, default={}) or {}

    thresholds = cfg.get("quality_thresholds", {}) if isinstance(cfg.get("quality_thresholds"), dict) else {}
    unique_ratio = to_float((cfg.get("traffic_estimation") or {}).get("unique_visitor_ratio"), 0.82)

    events = read_jsonl(in_dir / "raw_events.latest.jsonl")
    ingest_report = read_json(in_dir / "ingest_report.latest.json", default={}) or {}

    prev_scoreboard_path = in_dir / "stage1_scoreboard.latest.json"
    prev_scoreboard = read_json(prev_scoreboard_path, default={}) if prev_scoreboard_path.exists() else {}

    traffic_sessions = 0.0
    unattributed_sessions = 0.0
    forecast_sessions = 0.0
    source_sessions = defaultdict(float)

    qualified_signup_ids: Set[str] = set()
    signup_total_ids: Set[str] = set()
    paid_ids: Set[str] = set()
    opt_out_ids: Set[str] = set()

    qualified_signup_by_source = Counter()

    movement = _movement_buckets()

    # Date aggregates
    daily = defaultdict(lambda: {
        "sessions": 0.0,
        "qualified_signup_ids": set(),
        "paid_ids": set(),
        "movement": _movement_buckets(),
    })

    # Channel aggregates
    channel = defaultdict(lambda: {
        "sessions": 0.0,
        "qualified_signup_ids": set(),
        "paid_ids": set(),
        "new_mrr": 0.0,
    })

    # signup duplication stats
    qualified_signup_occurrences = Counter()

    for ev in events:
        name = str(ev.get("event_name") or "")
        day = iso_date(str(ev.get("event_time") or ""))
        count = to_float(ev.get("event_count"), 1.0)
        identity = _identity(ev)
        key = _channel_key(ev)

        if name in TRAFFIC_EVENTS and not ev.get("quality_is_bot") and not ev.get("quality_is_internal"):
            traffic_sessions += count
            source_sessions[str(ev.get("event_source") or "unknown")] += count
            daily[day]["sessions"] += count
            channel[key]["sessions"] += count
            if not ev.get("quality_is_attributed", False):
                unattributed_sessions += count
            if bool(ev.get("is_forecast", False)):
                forecast_sessions += count

        if name in SIGNUP_EVENTS:
            signup_total_ids.add(identity)

        if name in QUALIFIED_SIGNUP_EVENTS:
            qualified_signup_ids.add(identity)
            qualified_signup_occurrences[identity] += 1
            src = str(ev.get("event_source") or "unknown")
            qualified_signup_by_source[src] += 1
            daily[day]["qualified_signup_ids"].add(identity)
            channel[key]["qualified_signup_ids"].add(identity)

        if name in PAID_EVENTS:
            paid_ids.add(identity)
            daily[day]["paid_ids"].add(identity)
            channel[key]["paid_ids"].add(identity)

        if name == "lead_unsubscribed":
            opt_out_ids.add(identity)

        if name in MRR_EVENTS:
            m_type = str(ev.get("mrr_movement_type") or "").strip().lower()
            delta = to_float(ev.get("revenue_delta_mrr"), 0.0)
            if m_type:
                _movement_apply(movement, m_type, delta)
                _movement_apply(daily[day]["movement"], m_type, delta)
                if m_type == "new_business":
                    channel[key]["new_mrr"] += max(delta, 0.0)

    # Fallback: if no explicit movement events, derive from paid_started.
    if sum(movement.values()) == 0.0:
        for ev in events:
            if str(ev.get("event_name")) == "paid_started":
                delta = to_float(ev.get("revenue_delta_mrr"), 0.0)
                if delta > 0:
                    movement["new_business"] += delta

    new_mrr = round(movement["new_business"], 2)
    expansion_mrr = round(movement["expansion"], 2)
    contraction_mrr = round(movement["contraction"], 2)
    churn_mrr = round(movement["churn"], 2)
    reactivation_mrr = round(movement["reactivation"], 2)
    net_new_mrr = round(new_mrr + expansion_mrr + reactivation_mrr - contraction_mrr - churn_mrr, 2)

    qualified_signups = len(qualified_signup_ids)
    signups_total = len(signup_total_ids)
    paid_customers = len(paid_ids)

    visit_to_signup_rate = round(_safe_rate(float(qualified_signups), traffic_sessions), 4)
    signup_to_paid_rate = round(_safe_rate(float(paid_customers), float(qualified_signups)), 4)
    visit_to_paid_rate = round(_safe_rate(float(paid_customers), traffic_sessions), 4)

    unattributed_rate = round(_safe_rate(unattributed_sessions, traffic_sessions), 4)
    forecast_share = round(_safe_rate(forecast_sessions, traffic_sessions), 4)

    unique_visitors_est = round(traffic_sessions * unique_ratio, 2)

    # Daily outputs
    funnel_daily_rows = []
    revenue_daily_rows = []

    for day in sorted(daily.keys()):
        d = daily[day]
        day_sessions = round(to_float(d.get("sessions"), 0.0), 2)
        day_signups = len(d.get("qualified_signup_ids") or set())
        day_paid = len(d.get("paid_ids") or set())
        mv = d.get("movement") or _movement_buckets()
        day_new = round(to_float(mv.get("new_business"), 0.0), 2)
        day_exp = round(to_float(mv.get("expansion"), 0.0), 2)
        day_con = round(to_float(mv.get("contraction"), 0.0), 2)
        day_churn = round(to_float(mv.get("churn"), 0.0), 2)
        day_react = round(to_float(mv.get("reactivation"), 0.0), 2)
        day_net = round(day_new + day_exp + day_react - day_con - day_churn, 2)

        funnel_daily_rows.append(
            {
                "date": day,
                "sessions": day_sessions,
                "qualified_signups": day_signups,
                "paid_customers": day_paid,
                "visit_to_signup_rate": round(_safe_rate(day_signups, day_sessions), 4),
                "signup_to_paid_rate": round(_safe_rate(day_paid, float(day_signups)), 4),
                "visit_to_paid_rate": round(_safe_rate(day_paid, day_sessions), 4),
                "net_new_mrr": day_net,
            }
        )

        revenue_daily_rows.append(
            {
                "date": day,
                "new_business": day_new,
                "expansion": day_exp,
                "contraction": day_con,
                "churn": day_churn,
                "reactivation": day_react,
                "net_new_mrr": day_net,
            }
        )

    # Channel scoreboard
    channel_rows = []
    for (source, medium, campaign_id), row in channel.items():
        sessions = round(to_float(row.get("sessions"), 0.0), 2)
        q_signups = len(row.get("qualified_signup_ids") or set())
        paid = len(row.get("paid_ids") or set())
        new_mrr_ch = round(to_float(row.get("new_mrr"), 0.0), 2)
        channel_rows.append(
            {
                "source": source,
                "medium": medium,
                "campaign_id": campaign_id,
                "sessions": sessions,
                "qualified_signups": q_signups,
                "paid_customers": paid,
                "new_mrr": new_mrr_ch,
                "visit_to_signup_rate": round(_safe_rate(q_signups, sessions), 4),
                "signup_to_paid_rate": round(_safe_rate(paid, float(q_signups)), 4),
                "visit_to_paid_rate": round(_safe_rate(paid, sessions), 4),
            }
        )

    channel_rows.sort(key=lambda r: (r["new_mrr"], r["qualified_signups"], r["sessions"]), reverse=True)

    # Quality reports
    duplicate_count = int(ingest_report.get("duplicates_skipped") or 0)
    event_count = len(events)
    duplicate_rate = round(_safe_rate(float(duplicate_count), float(event_count + duplicate_count)), 4)

    max_event_time = None
    for ev in events:
        ts = parse_iso(str(ev.get("event_time") or ""))
        if ts is None:
            continue
        if max_event_time is None or ts > max_event_time:
            max_event_time = ts

    freshness_hours = None
    if max_event_time is not None:
        freshness_hours = round((now_utc() - max_event_time.astimezone(timezone.utc)).total_seconds() / 3600.0, 2)

    traffic_quality = {
        "generated_at": now_iso(),
        "sessions_total": round(traffic_sessions, 2),
        "unattributed_sessions": round(unattributed_sessions, 2),
        "unattributed_traffic_rate": unattributed_rate,
        "forecast_sessions": round(forecast_sessions, 2),
        "forecast_share": forecast_share,
        "source_mix": [
            {"source": src, "sessions": round(cnt, 2)}
            for src, cnt in sorted(source_sessions.items(), key=lambda x: x[1], reverse=True)
        ],
    }

    duplicate_signup_leads = sorted([k for k, v in qualified_signup_occurrences.items() if v > 1])

    signup_quality = {
        "generated_at": now_iso(),
        "signups_total": signups_total,
        "qualified_signups": qualified_signups,
        "paid_customers": paid_customers,
        "qualification_rate": round(_safe_rate(float(qualified_signups), float(signups_total)), 4),
        "duplicate_signup_leads": duplicate_signup_leads,
        "duplicate_signup_leads_count": len(duplicate_signup_leads),
        "opt_out_count": len(opt_out_ids),
        "qualified_signup_by_source": dict(sorted(qualified_signup_by_source.items())),
    }

    data_quality = {
        "generated_at": now_iso(),
        "event_count": event_count,
        "duplicate_count": duplicate_count,
        "duplicate_rate": duplicate_rate,
        "schema_missing_required": ingest_report.get("schema_missing_required", {}),
        "freshness_hours": freshness_hours,
        "events_by_adapter": ingest_report.get("events_by_adapter", {}),
        "warnings": ingest_report.get("warnings", []),
    }

    # Alerts
    alerts: List[Dict[str, Any]] = []

    max_unattr = to_float(thresholds.get("max_unattributed_traffic_rate"), 0.05)
    min_v2s = to_float(thresholds.get("min_visit_to_signup_rate"), 0.005)
    min_s2p = to_float(thresholds.get("min_signup_to_paid_rate"), 0.03)
    max_dup = to_float(thresholds.get("max_duplicate_rate"), 0.01)
    max_lag = to_float(thresholds.get("max_data_lag_hours"), 48)

    if traffic_sessions <= 0:
        alerts.append({"severity": "critical", "code": "traffic_zero", "message": "No traffic sessions observed."})
    if unattributed_rate > max_unattr:
        alerts.append(
            {
                "severity": "warning",
                "code": "unattributed_traffic_high",
                "message": f"Unattributed traffic rate {unattributed_rate} exceeds threshold {max_unattr}.",
            }
        )
    if visit_to_signup_rate < min_v2s:
        alerts.append(
            {
                "severity": "warning",
                "code": "visit_to_signup_low",
                "message": f"Visit to signup rate {visit_to_signup_rate} below threshold {min_v2s}.",
            }
        )
    if signup_to_paid_rate < min_s2p:
        alerts.append(
            {
                "severity": "warning",
                "code": "signup_to_paid_low",
                "message": f"Signup to paid rate {signup_to_paid_rate} below threshold {min_s2p}.",
            }
        )
    if duplicate_rate > max_dup:
        alerts.append(
            {
                "severity": "warning",
                "code": "duplicate_rate_high",
                "message": f"Duplicate event rate {duplicate_rate} exceeds threshold {max_dup}.",
            }
        )
    if freshness_hours is not None and freshness_hours > max_lag:
        alerts.append(
            {
                "severity": "warning",
                "code": "data_stale",
                "message": f"Data freshness lag {freshness_hours}h exceeds threshold {max_lag}h.",
            }
        )
    if net_new_mrr < 0:
        alerts.append(
            {
                "severity": "critical",
                "code": "net_new_mrr_negative",
                "message": f"Net new MRR is negative ({net_new_mrr}).",
            }
        )

    prev_summary = (prev_scoreboard or {}).get("summary", {}) if isinstance(prev_scoreboard, dict) else {}
    prev_traffic = (prev_summary.get("traffic", {}) if isinstance(prev_summary, dict) else {}).get("sessions")
    prev_signups = (prev_summary.get("signups", {}) if isinstance(prev_summary, dict) else {}).get("qualified_signups")

    if to_float(prev_traffic, 0.0) > 0 and traffic_sessions < (to_float(prev_traffic, 0.0) * 0.6):
        alerts.append(
            {
                "severity": "warning",
                "code": "traffic_drop",
                "message": f"Traffic sessions dropped >40% vs previous run ({prev_traffic} -> {round(traffic_sessions, 2)}).",
            }
        )

    if to_float(prev_signups, 0.0) > 0 and qualified_signups < (to_float(prev_signups, 0.0) * 0.6):
        alerts.append(
            {
                "severity": "warning",
                "code": "signup_drop",
                "message": f"Qualified signups dropped >40% vs previous run ({prev_signups} -> {qualified_signups}).",
            }
        )

    # Capability completeness matrix
    capability_status = [
        {"capability": "metric_governance", "status": "implemented", "evidence": "contracts/metric_dictionary.v1.yaml"},
        {"capability": "tracking_plan", "status": "implemented", "evidence": "contracts/tracking_plan.v1.json"},
        {"capability": "event_collection", "status": "implemented", "evidence": "research/stage1_tracking/raw_events.latest.jsonl"},
        {"capability": "identity_stitching", "status": "implemented", "evidence": "research/stage1_tracking/identity_map.latest.json"},
        {"capability": "attribution", "status": "implemented", "evidence": "research/stage1_tracking/attribution_facts.latest.json"},
        {"capability": "traffic_quality", "status": "implemented", "evidence": "research/stage1_tracking/traffic_quality_report.latest.json"},
        {"capability": "funnel_engine", "status": "implemented", "evidence": "research/stage1_tracking/funnel_daily.latest.json"},
        {"capability": "signup_quality", "status": "implemented", "evidence": "research/stage1_tracking/signup_quality_daily.latest.json"},
        {"capability": "revenue_engine", "status": "implemented", "evidence": "research/stage1_tracking/revenue_mrr_daily.latest.json"},
        {"capability": "channel_economics", "status": "implemented", "evidence": "research/stage1_tracking/channel_scoreboard.latest.json"},
        {"capability": "ops_scoreboard", "status": "implemented", "evidence": "research/stage1_tracking/stage1_scoreboard.latest.md"},
        {"capability": "alerting", "status": "implemented", "evidence": "research/stage1_tracking/alerts.latest.json"},
        {"capability": "data_quality", "status": "implemented", "evidence": "research/stage1_tracking/data_quality_report.latest.json"},
        {"capability": "reproducibility", "status": "implemented", "evidence": "research/stage1_tracking/reproducibility_report.latest.json"},
        {"capability": "prod_migration_adapter", "status": "implemented", "evidence": "config/source_adapters.v1.json"},
    ]

    scoreboard = {
        "generated_at": now_iso(),
        "stage": "stage1_tracking",
        "mode": "simulated_signals",
        "inputs": {
            "events_path": "workspaces/op1_operations/research/stage1_tracking/raw_events.latest.jsonl",
            "ingest_report_path": "workspaces/op1_operations/research/stage1_tracking/ingest_report.latest.json",
            "adapter_config_path": "workspaces/op1_operations/config/source_adapters.v1.json",
        },
        "summary": {
            "traffic": {
                "sessions": round(traffic_sessions, 2),
                "unique_visitors_est": unique_visitors_est,
                "unattributed_traffic_rate": unattributed_rate,
                "forecast_share": forecast_share,
            },
            "signups": {
                "signups_total": signups_total,
                "qualified_signups": qualified_signups,
                "paid_customers": paid_customers,
                "opt_out_count": len(opt_out_ids),
            },
            "revenue": {
                "new_mrr": new_mrr,
                "expansion_mrr": expansion_mrr,
                "contraction_mrr": contraction_mrr,
                "churn_mrr": churn_mrr,
                "reactivation_mrr": reactivation_mrr,
                "net_new_mrr": net_new_mrr,
            },
            "conversion": {
                "visit_to_signup_rate": visit_to_signup_rate,
                "signup_to_paid_rate": signup_to_paid_rate,
                "visit_to_paid_rate": visit_to_paid_rate,
            },
            "milestone": {
                "target_mrr": 100.0,
                "achieved_mrr": new_mrr,
                "remaining_mrr": round(max(0.0, 100.0 - new_mrr), 2),
                "progress_ratio": round(_safe_rate(new_mrr, 100.0), 4),
            },
        },
        "quality_refs": {
            "traffic_quality": "workspaces/op1_operations/research/stage1_tracking/traffic_quality_report.latest.json",
            "signup_quality": "workspaces/op1_operations/research/stage1_tracking/signup_quality_daily.latest.json",
            "data_quality": "workspaces/op1_operations/research/stage1_tracking/data_quality_report.latest.json",
        },
        "alerts_count": len(alerts),
        "capability_status": capability_status,
        "notes": [
            "Sales-side signals are simulated. Pipeline is built for adapter-based migration to live sources.",
            "Traffic currently includes forecast-based sessions from marketing shadow launch packets."
        ],
    }

    # Weekly snapshot (based on available rows)
    last_7 = funnel_daily_rows[-7:]
    week_sessions = round(sum(to_float(r.get("sessions"), 0.0) for r in last_7), 2)
    week_signups = sum(int(r.get("qualified_signups") or 0) for r in last_7)
    week_paid = sum(int(r.get("paid_customers") or 0) for r in last_7)
    week_mrr = round(sum(to_float(r.get("net_new_mrr"), 0.0) for r in last_7), 2)

    top_channel = channel_rows[0] if channel_rows else {
        "source": "unknown",
        "medium": "unknown",
        "campaign_id": "unknown",
        "sessions": 0,
        "qualified_signups": 0,
        "new_mrr": 0,
    }

    weekly_snapshot_md = "\n".join(
        [
            "# Weekly KPI Snapshot (Stage1)",
            "",
            f"Generated at: {now_iso()}",
            "",
            "## 7-day rollup",
            f"- sessions: {week_sessions}",
            f"- qualified_signups: {week_signups}",
            f"- paid_customers: {week_paid}",
            f"- net_new_mrr: {week_mrr}",
            "",
            "## Leading channel",
            f"- source/medium: {top_channel.get('source')} / {top_channel.get('medium')}",
            f"- campaign_id: {top_channel.get('campaign_id')}",
            f"- sessions: {top_channel.get('sessions')}",
            f"- qualified_signups: {top_channel.get('qualified_signups')}",
            f"- new_mrr: {top_channel.get('new_mrr')}",
            "",
            "## Actionable next steps",
            "- Improve attribution coverage where source/medium is unknown.",
            "- Increase qualified signup conversion on top-session channels.",
            "- Push paid start follow-through for high-intent qualified leads.",
        ]
    ) + "\n"

    # Save outputs
    write_json(in_dir / "funnel_daily.latest.json", {"generated_at": now_iso(), "rows": funnel_daily_rows})
    write_json(in_dir / "revenue_mrr_daily.latest.json", {"generated_at": now_iso(), "rows": revenue_daily_rows})
    write_json(in_dir / "channel_scoreboard.latest.json", {"generated_at": now_iso(), "rows": channel_rows})
    write_json(in_dir / "traffic_quality_report.latest.json", traffic_quality)
    write_json(in_dir / "signup_quality_daily.latest.json", signup_quality)
    write_json(in_dir / "data_quality_report.latest.json", data_quality)
    write_json(in_dir / "alerts.latest.json", {"generated_at": now_iso(), "alerts": alerts})
    write_json(in_dir / "stage1_scoreboard.latest.json", scoreboard)

    md = build_markdown(scoreboard, channel_rows, alerts)
    write_text(in_dir / "stage1_scoreboard.latest.md", md)
    write_text(in_dir / "weekly_kpi_snapshot.latest.md", weekly_snapshot_md)

    print(
        {
            "sessions": round(traffic_sessions, 2),
            "qualified_signups": qualified_signups,
            "paid_customers": paid_customers,
            "net_new_mrr": net_new_mrr,
            "alerts": len(alerts),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
