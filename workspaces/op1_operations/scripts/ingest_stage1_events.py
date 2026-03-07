#!/usr/bin/env python3
"""Build canonical Stage1 events (traffic / signup / revenue)."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from stage1_common import (
    extract_opportunity_id,
    normalize_medium,
    now_iso,
    parse_iso,
    read_json,
    read_jsonl,
    resolve_repo_root,
    stable_hash,
    to_float,
    write_json,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest Stage1 source adapters into canonical events")
    p.add_argument("--repo-root", default="", help="Repo root (auto-detect when omitted)")
    p.add_argument(
        "--adapters-config",
        default="workspaces/op1_operations/config/source_adapters.v1.json",
        help="Adapter config path (repo-root relative)",
    )
    p.add_argument(
        "--out-dir",
        default="workspaces/op1_operations/research/stage1_tracking",
        help="Output directory (repo-root relative)",
    )
    return p.parse_args()


def make_event(
    *,
    event_name: str,
    event_time: str,
    distinct_id: str,
    source_adapter: str,
    source_system: str,
    source_ref: str,
    source_path: str,
    event_count: float = 1.0,
    lead_id: str | None = None,
    anonymous_id: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    opportunity_id: str | None = None,
    campaign_id: str | None = None,
    campaign_name: str | None = None,
    event_source: str | None = None,
    event_medium: str | None = None,
    first_user_source: str | None = None,
    first_user_medium: str | None = None,
    session_source: str | None = None,
    session_medium: str | None = None,
    revenue_delta_mrr: float = 0.0,
    mrr_movement_type: str | None = None,
    detail: str | None = None,
    is_forecast: bool = False,
    properties: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    t = parse_iso(event_time)
    event_time_norm = t.isoformat() if t else now_iso()

    event_source_norm = (event_source or "unknown").strip().lower()
    event_medium_norm = (event_medium or "unknown").strip().lower()

    event_id = stable_hash(
        [
            source_adapter,
            source_ref,
            event_name,
            event_time_norm,
            distinct_id,
            lead_id or "",
            detail or "",
        ],
        length=40,
    )

    return {
        "event_id": event_id,
        "event_name": event_name,
        "event_time": event_time_norm,
        "event_count": round(float(event_count), 6),
        "distinct_id": distinct_id,
        "anonymous_id": anonymous_id or None,
        "session_id": session_id or None,
        "lead_id": lead_id or None,
        "user_id": user_id or None,
        "opportunity_id": opportunity_id or None,
        "campaign_id": campaign_id or None,
        "campaign_name": campaign_name or None,
        "first_user_source": (first_user_source or event_source_norm),
        "first_user_medium": (first_user_medium or event_medium_norm),
        "session_source": (session_source or event_source_norm),
        "session_medium": (session_medium or event_medium_norm),
        "event_source": event_source_norm,
        "event_medium": event_medium_norm,
        "revenue_delta_mrr": round(float(revenue_delta_mrr), 6),
        "mrr_movement_type": mrr_movement_type or None,
        "source_adapter": source_adapter,
        "source_system": source_system,
        "source_ref": source_ref,
        "source_path": source_path,
        "detail": detail or None,
        "is_forecast": bool(is_forecast),
        "quality_is_attributed": event_source_norm not in {"", "unknown"} and event_medium_norm not in {"", "unknown"},
        "quality_is_bot": False,
        "quality_is_internal": False,
        "properties": properties or {},
    }


def load_scoreboard_mrr_map(repo_root: Path) -> Dict[str, float]:
    p = repo_root / "workspaces/op1_sales/research/conversion/conversion_scoreboard.latest.json"
    obj = read_json(p, default={}) or {}
    summary = obj.get("summary", {}) if isinstance(obj, dict) else {}
    raw = summary.get("lead_mrr_proxy", {}) if isinstance(summary, dict) else {}
    out: Dict[str, float] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            out[str(k)] = to_float(v, 0.0)
    return out


def build_campaign_maps(marketing_payload: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    queue = marketing_payload.get("queue", {}) if isinstance(marketing_payload, dict) else {}
    campaigns: List[Dict[str, Any]] = []
    for bucket in ["launch_ready", "watchlist", "hold"]:
        rows = queue.get(bucket, []) if isinstance(queue, dict) else []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    campaigns.append(row)

    campaign_by_opp: Dict[str, Dict[str, Any]] = {}
    for camp in campaigns:
        campaign_id = str(camp.get("campaign_id", "")).strip()
        if not campaign_id:
            continue
        opp_id = extract_opportunity_id(campaign_id) or extract_opportunity_id(str(camp.get("context_id", "")))
        channels = camp.get("channels", []) if isinstance(camp.get("channels"), list) else []
        if not opp_id:
            continue
        if opp_id in campaign_by_opp:
            continue

        source = "unknown"
        medium = "unknown"
        if channels and isinstance(channels[0], dict):
            ch0 = channels[0]
            source = str(ch0.get("utm_source") or ch0.get("channel") or "unknown").strip().lower()
            medium = str(ch0.get("utm_medium") or "unknown").strip().lower()

        campaign_by_opp[opp_id] = {
            "campaign_id": campaign_id,
            "campaign_name": camp.get("name"),
            "source": source,
            "medium": medium,
        }

    return campaign_by_opp, campaigns


def ingest_marketing_campaigns(
    *,
    campaigns: List[Dict[str, Any]],
    source_adapter: str,
    source_path: str,
    medium_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []

    for camp in campaigns:
        campaign_id = str(camp.get("campaign_id", "")).strip()
        if not campaign_id:
            continue
        generated_at = str(camp.get("generated_at") or now_iso())
        campaign_name = str(camp.get("name") or campaign_id)
        opp_id = extract_opportunity_id(campaign_id) or extract_opportunity_id(str(camp.get("context_id", "")))
        channels = camp.get("channels", []) if isinstance(camp.get("channels"), list) else []

        for idx, channel in enumerate(channels):
            if not isinstance(channel, dict):
                continue
            channel_name = str(channel.get("channel") or "unknown").strip().lower()
            source = str(channel.get("utm_source") or channel_name or "unknown").strip().lower()
            medium = str(channel.get("utm_medium") or normalize_medium(source, medium_map)).strip().lower()
            metrics = channel.get("metrics", {}) if isinstance(channel.get("metrics"), dict) else {}

            sessions_est = to_float(metrics.get("sessions_est"), 0.0)
            if sessions_est > 0:
                events.append(
                    make_event(
                        event_name="session_observed",
                        event_time=generated_at,
                        distinct_id=f"session::{campaign_id}::{channel_name}::{idx}",
                        anonymous_id=f"anon::{campaign_id}::{channel_name}",
                        session_id=f"sess::{campaign_id}::{channel_name}",
                        source_adapter=source_adapter,
                        source_system="marketing",
                        source_ref=campaign_id,
                        source_path=source_path,
                        opportunity_id=opp_id,
                        campaign_id=campaign_id,
                        campaign_name=campaign_name,
                        event_source=source,
                        event_medium=medium,
                        event_count=sessions_est,
                        is_forecast=True,
                        detail="sessions_est",
                        properties={
                            "channel": channel_name,
                            "budget": to_float(channel.get("budget"), 0.0),
                            "clicks_est": to_float(metrics.get("clicks_est"), 0.0),
                            "mql_est": to_float(metrics.get("mql_est"), 0.0),
                            "sql_est": to_float(metrics.get("sql_est"), 0.0),
                            "mode": camp.get("mode", "shadow"),
                        },
                    )
                )

            mql_est = to_float(metrics.get("mql_est"), 0.0)
            if mql_est > 0:
                events.append(
                    make_event(
                        event_name="signup_forecast",
                        event_time=generated_at,
                        distinct_id=f"signup_forecast::{campaign_id}::{channel_name}::{idx}",
                        source_adapter=source_adapter,
                        source_system="marketing",
                        source_ref=campaign_id,
                        source_path=source_path,
                        opportunity_id=opp_id,
                        campaign_id=campaign_id,
                        campaign_name=campaign_name,
                        event_source=source,
                        event_medium=medium,
                        event_count=mql_est,
                        is_forecast=True,
                        detail="mql_est",
                        properties={
                            "channel": channel_name,
                            "sql_est": to_float(metrics.get("sql_est"), 0.0),
                            "budget": to_float(channel.get("budget"), 0.0),
                        },
                    )
                )

    return events


def ingest_outreach_events(
    *,
    rows: List[Dict[str, Any]],
    source_adapter: str,
    source_path: str,
    medium_map: Dict[str, str],
    campaign_by_opp: Dict[str, Dict[str, Any]],
    lead_mrr_map: Dict[str, float],
) -> List[Dict[str, Any]]:
    mapping = {
        "dispatch_manual_committed": "signup_started",
        "reply_positive": "signup_captured",
        "reply_not_now": "signup_deferred",
        "reply_unsubscribe": "lead_unsubscribed",
        "reply_objection": "objection_logged",
        "reply_converted": "paid_started",
    }

    events: List[Dict[str, Any]] = []
    for row in rows:
        event_type = str(row.get("event_type", "")).strip()
        canonical = mapping.get(event_type)
        if not canonical:
            continue

        lead_id = str(row.get("lead_id") or "").strip()
        ts = str(row.get("ts") or now_iso())
        opp_id = extract_opportunity_id(lead_id)
        camp = campaign_by_opp.get(opp_id or "", {})

        source = str(row.get("channel") or camp.get("source") or "unknown").strip().lower()
        medium = normalize_medium(source, medium_map)
        campaign_id = str(camp.get("campaign_id") or "") or None
        campaign_name = str(camp.get("campaign_name") or "") or None

        mrr_delta = 0.0
        mrr_type = None
        if canonical == "paid_started":
            mrr_delta = to_float(lead_mrr_map.get(lead_id), 49.0)
            mrr_type = "new_business"

        events.append(
            make_event(
                event_name=canonical,
                event_time=ts,
                distinct_id=lead_id or str(row.get("message_id") or stable_hash([event_type, ts], 12)),
                lead_id=lead_id or None,
                source_adapter=source_adapter,
                source_system="sales_outreach",
                source_ref=str(row.get("message_id") or row.get("batch_id") or event_type),
                source_path=source_path,
                opportunity_id=opp_id,
                campaign_id=campaign_id,
                campaign_name=campaign_name,
                event_source=source,
                event_medium=medium,
                event_count=1.0,
                revenue_delta_mrr=mrr_delta,
                mrr_movement_type=mrr_type,
                detail=str(row.get("detail") or event_type),
                properties={
                    "raw_event_type": event_type,
                    "text_excerpt": row.get("text_excerpt"),
                },
            )
        )

    return events


def ingest_conversion_events(
    *,
    rows: List[Dict[str, Any]],
    source_adapter: str,
    source_path: str,
    medium_map: Dict[str, str],
    campaign_by_opp: Dict[str, Dict[str, Any]],
    lead_mrr_map: Dict[str, float],
) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []

    for row in rows:
        event_type = str(row.get("event_type") or "").strip()
        stage = str(row.get("stage") or "").strip()

        canonical = None
        if event_type == "conversion_stage_changed":
            if stage == "qualified_interest":
                canonical = "signup_qualified"
            elif stage == "discovery_scheduled":
                canonical = "signup_captured"
            elif stage == "paid_started":
                canonical = "paid_started"
            elif stage == "closed_lost":
                canonical = "closed_lost"
            elif stage:
                canonical = f"stage_{stage}"
        elif event_type == "discovery_scheduled":
            canonical = "signup_captured"
        elif event_type in {"paid_started", "closed_lost", "objection_logged"}:
            canonical = event_type

        if not canonical:
            continue

        lead_id = str(row.get("lead_id") or "").strip()
        ts = str(row.get("ts") or row.get("created_at") or now_iso())
        opp_id = extract_opportunity_id(lead_id)
        camp = campaign_by_opp.get(opp_id or "", {})

        source = str(row.get("channel") or camp.get("source") or "unknown").strip().lower()
        medium = normalize_medium(source, medium_map)

        campaign_id = str(camp.get("campaign_id") or "") or None
        campaign_name = str(camp.get("campaign_name") or "") or None

        mrr_delta = 0.0
        mrr_type = None

        if canonical == "paid_started":
            mrr_delta = to_float(lead_mrr_map.get(lead_id), 49.0)
            mrr_type = "new_business"
        elif canonical == "closed_lost" and lead_id in lead_mrr_map:
            # Churn is only meaningful if the lead had recognized MRR.
            mrr_delta = -abs(to_float(lead_mrr_map.get(lead_id), 0.0))
            mrr_type = "churn"

        source_ref = str(row.get("source_ref") or row.get("source_key") or event_type)

        event = make_event(
            event_name=canonical,
            event_time=ts,
            distinct_id=lead_id or source_ref,
            lead_id=lead_id or None,
            source_adapter=source_adapter,
            source_system="sales_conversion",
            source_ref=source_ref,
            source_path=source_path,
            opportunity_id=opp_id,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            event_source=source,
            event_medium=medium,
            event_count=1.0,
            revenue_delta_mrr=mrr_delta,
            mrr_movement_type=mrr_type,
            detail=str(row.get("detail") or event_type),
            properties={
                "raw_event_type": event_type,
                "raw_stage": stage or None,
            },
        )
        events.append(event)

        # Explicit movement event for revenue model.
        if canonical == "paid_started":
            events.append(
                make_event(
                    event_name="mrr_movement",
                    event_time=ts,
                    distinct_id=f"mrr::{lead_id or source_ref}",
                    lead_id=lead_id or None,
                    source_adapter=source_adapter,
                    source_system="sales_conversion",
                    source_ref=f"mrr::{source_ref}",
                    source_path=source_path,
                    opportunity_id=opp_id,
                    campaign_id=campaign_id,
                    campaign_name=campaign_name,
                    event_source=source,
                    event_medium=medium,
                    event_count=1.0,
                    revenue_delta_mrr=mrr_delta,
                    mrr_movement_type="new_business",
                    detail="movement_from_paid_started",
                )
            )
        elif canonical == "closed_lost" and mrr_delta < 0:
            events.append(
                make_event(
                    event_name="mrr_movement",
                    event_time=ts,
                    distinct_id=f"mrr::{lead_id or source_ref}::churn",
                    lead_id=lead_id or None,
                    source_adapter=source_adapter,
                    source_system="sales_conversion",
                    source_ref=f"mrr_churn::{source_ref}",
                    source_path=source_path,
                    opportunity_id=opp_id,
                    campaign_id=campaign_id,
                    campaign_name=campaign_name,
                    event_source=source,
                    event_medium=medium,
                    event_count=1.0,
                    revenue_delta_mrr=mrr_delta,
                    mrr_movement_type="churn",
                    detail="movement_from_closed_lost",
                )
            )

    return events


def ingest_product_runtime_events(
    *,
    rows: List[Dict[str, Any]],
    source_adapter: str,
    source_path: str,
    medium_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        event_name = str(row.get("event_name") or row.get("event") or "").strip()
        if not event_name:
            continue
        ts = str(row.get("event_time") or row.get("ts") or now_iso())
        source = str(row.get("event_source") or row.get("utm_source") or "unknown").strip().lower()
        medium = str(row.get("event_medium") or row.get("utm_medium") or normalize_medium(source, medium_map)).strip().lower()

        events.append(
            make_event(
                event_name=event_name,
                event_time=ts,
                distinct_id=str(row.get("distinct_id") or row.get("anonymous_id") or stable_hash([event_name, ts], 12)),
                anonymous_id=str(row.get("anonymous_id") or "") or None,
                session_id=str(row.get("session_id") or "") or None,
                lead_id=str(row.get("lead_id") or "") or None,
                user_id=str(row.get("user_id") or "") or None,
                opportunity_id=extract_opportunity_id(str(row.get("lead_id") or row.get("campaign_id") or "")),
                campaign_id=str(row.get("campaign_id") or "") or None,
                campaign_name=str(row.get("campaign_name") or "") or None,
                source_adapter=source_adapter,
                source_system="product_runtime",
                source_ref=str(row.get("source_ref") or event_name),
                source_path=source_path,
                event_source=source,
                event_medium=medium,
                event_count=to_float(row.get("event_count"), 1.0),
                revenue_delta_mrr=to_float(row.get("revenue_delta_mrr"), 0.0),
                mrr_movement_type=str(row.get("mrr_movement_type") or "") or None,
                detail=str(row.get("detail") or "") or None,
                is_forecast=bool(row.get("is_forecast", False)),
                properties=row.get("properties") if isinstance(row.get("properties"), dict) else {},
            )
        )
    return events


def dedupe_events(events: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    seen = set()
    out: List[Dict[str, Any]] = []
    duplicates = 0
    for event in sorted(events, key=lambda r: (str(r.get("event_time")), str(r.get("event_id")))):
        event_id = str(event.get("event_id") or "")
        if not event_id:
            continue
        if event_id in seen:
            duplicates += 1
            continue
        seen.add(event_id)
        out.append(event)
    return out, duplicates


def build_identity_map(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    identities: Dict[str, Dict[str, Any]] = {}

    def identity_key(ev: Dict[str, Any]) -> str:
        for key in ["lead_id", "user_id", "distinct_id", "anonymous_id"]:
            val = str(ev.get(key) or "").strip()
            if val:
                return f"{key}:{val}"
        return f"event:{ev.get('event_id')}"

    for ev in sorted(events, key=lambda r: (str(r.get("event_time")), str(r.get("event_id")))):
        key = identity_key(ev)
        cur = identities.get(key)
        if cur is None:
            cur = {
                "identity_key": key,
                "lead_id": ev.get("lead_id"),
                "user_id": ev.get("user_id"),
                "distinct_id": ev.get("distinct_id"),
                "anonymous_id": ev.get("anonymous_id"),
                "opportunity_id": ev.get("opportunity_id"),
                "campaign_id": ev.get("campaign_id"),
                "first_seen": ev.get("event_time"),
                "last_seen": ev.get("event_time"),
                "first_source": ev.get("event_source"),
                "first_medium": ev.get("event_medium"),
                "last_source": ev.get("event_source"),
                "last_medium": ev.get("event_medium"),
                "events": 0,
                "weighted_events": 0.0,
            }
            identities[key] = cur

        cur["events"] += 1
        cur["weighted_events"] = round(to_float(cur.get("weighted_events"), 0.0) + to_float(ev.get("event_count"), 1.0), 6)
        cur["last_seen"] = ev.get("event_time")
        cur["last_source"] = ev.get("event_source")
        cur["last_medium"] = ev.get("event_medium")
        if not cur.get("campaign_id") and ev.get("campaign_id"):
            cur["campaign_id"] = ev.get("campaign_id")
        if not cur.get("opportunity_id") and ev.get("opportunity_id"):
            cur["opportunity_id"] = ev.get("opportunity_id")

    rows = sorted(identities.values(), key=lambda r: str(r.get("identity_key")))
    return {
        "generated_at": now_iso(),
        "identity_count": len(rows),
        "identities": rows,
    }


def build_attribution_facts(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_opp: Dict[str, Dict[str, Any]] = {}

    for ev in events:
        opp = str(ev.get("opportunity_id") or "").strip()
        if not opp:
            continue
        row = by_opp.get(opp)
        if row is None:
            row = {
                "opportunity_id": opp,
                "campaign_id": ev.get("campaign_id"),
                "first_user_source": ev.get("first_user_source"),
                "first_user_medium": ev.get("first_user_medium"),
                "traffic_sessions": 0.0,
                "qualified_signups": 0,
                "paid_customers": 0,
                "new_mrr": 0.0,
            }
            by_opp[opp] = row

        name = str(ev.get("event_name") or "")
        if name == "session_observed":
            row["traffic_sessions"] += to_float(ev.get("event_count"), 0.0)
        elif name == "signup_qualified":
            row["qualified_signups"] += 1
        elif name == "paid_started":
            row["paid_customers"] += 1
            row["new_mrr"] += to_float(ev.get("revenue_delta_mrr"), 0.0)

    rows = []
    for opp, row in sorted(by_opp.items()):
        rows.append(
            {
                **row,
                "traffic_sessions": round(to_float(row.get("traffic_sessions"), 0.0), 2),
                "new_mrr": round(to_float(row.get("new_mrr"), 0.0), 2),
            }
        )

    return {
        "generated_at": now_iso(),
        "rows": rows,
    }


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else resolve_repo_root(Path(__file__))

    config_path = repo_root / args.adapters_config
    out_dir = repo_root / args.out_dir

    config = read_json(config_path, default={}) or {}
    adapters = config.get("adapters", []) if isinstance(config.get("adapters"), list) else []
    medium_map = config.get("channel_medium_map", {}) if isinstance(config.get("channel_medium_map"), dict) else {}

    lead_mrr_map = load_scoreboard_mrr_map(repo_root)

    all_events: List[Dict[str, Any]] = []
    warnings: List[str] = []
    source_status: List[Dict[str, Any]] = []

    # Preload marketing payload for campaign-opportunity attribution map.
    marketing_payload: Dict[str, Any] = {}
    marketing_adapter = next((a for a in adapters if a.get("id") == "marketing_campaign_shadow" and a.get("enabled", True)), None)
    if isinstance(marketing_adapter, dict):
        mp = repo_root / str(marketing_adapter.get("path") or "")
        if mp.exists():
            marketing_payload = read_json(mp, default={}) or {}
        else:
            warnings.append(f"marketing adapter path missing: {mp}")

    campaign_by_opp, campaigns = build_campaign_maps(marketing_payload)

    for adapter in adapters:
        adapter_id = str(adapter.get("id") or "").strip()
        if not adapter_id:
            continue
        enabled = bool(adapter.get("enabled", True))
        source_rel = str(adapter.get("path") or "").strip()
        source_path = repo_root / source_rel if source_rel else None

        status = {
            "adapter_id": adapter_id,
            "enabled": enabled,
            "path": str(source_path) if source_path else None,
            "exists": bool(source_path and source_path.exists()),
            "events_added": 0,
        }

        if not enabled:
            source_status.append(status)
            continue
        if source_path is None or not source_path.exists():
            warnings.append(f"adapter {adapter_id} missing source path")
            source_status.append(status)
            continue

        adapter_events: List[Dict[str, Any]] = []

        if adapter_id == "marketing_campaign_shadow":
            adapter_events = ingest_marketing_campaigns(
                campaigns=campaigns,
                source_adapter=adapter_id,
                source_path=source_rel,
                medium_map=medium_map,
            )

        elif adapter_id == "sales_outreach_sim":
            rows = read_jsonl(source_path)
            adapter_events = ingest_outreach_events(
                rows=rows,
                source_adapter=adapter_id,
                source_path=source_rel,
                medium_map=medium_map,
                campaign_by_opp=campaign_by_opp,
                lead_mrr_map=lead_mrr_map,
            )

        elif adapter_id == "sales_conversion_sim":
            rows = read_jsonl(source_path)
            adapter_events = ingest_conversion_events(
                rows=rows,
                source_adapter=adapter_id,
                source_path=source_rel,
                medium_map=medium_map,
                campaign_by_opp=campaign_by_opp,
                lead_mrr_map=lead_mrr_map,
            )

        elif adapter_id == "sales_conversion_scoreboard":
            score = read_json(source_path, default={}) or {}
            summary = score.get("summary", {}) if isinstance(score, dict) else {}
            ts = str(score.get("generated_at") or now_iso())
            net_new = to_float(summary.get("new_business_mrr_proxy"), 0.0)
            adapter_events = [
                make_event(
                    event_name="mrr_snapshot",
                    event_time=ts,
                    distinct_id="mrr_snapshot::latest",
                    source_adapter=adapter_id,
                    source_system="sales_conversion",
                    source_ref="summary",
                    source_path=source_rel,
                    event_source="billing_proxy",
                    event_medium="manual",
                    event_count=1.0,
                    revenue_delta_mrr=net_new,
                    mrr_movement_type="new_business",
                    detail="scoreboard_proxy",
                    properties={
                        "new_customers_converted": summary.get("new_customers_converted"),
                        "asp_proxy": summary.get("asp_proxy"),
                    },
                )
            ]

        elif adapter_id == "product_web_runtime":
            rows = read_jsonl(source_path)
            adapter_events = ingest_product_runtime_events(
                rows=rows,
                source_adapter=adapter_id,
                source_path=source_rel,
                medium_map=medium_map,
            )

        else:
            warnings.append(f"adapter {adapter_id} not recognized")

        status["events_added"] = len(adapter_events)
        source_status.append(status)
        all_events.extend(adapter_events)

    deduped_events, duplicates = dedupe_events(all_events)

    # Schema completeness check.
    required = ["event_id", "event_name", "event_time", "event_count", "source_adapter", "distinct_id"]
    missing_counter = Counter()
    for ev in deduped_events:
        for f in required:
            val = ev.get(f)
            if val is None or (isinstance(val, str) and not val.strip()):
                missing_counter[f] += 1

    identity_map = build_identity_map(deduped_events)
    attribution_facts = build_attribution_facts(deduped_events)

    event_type_counter = Counter(str(e.get("event_name") or "unknown") for e in deduped_events)
    adapter_counter = Counter(str(e.get("source_adapter") or "unknown") for e in deduped_events)

    ingest_report = {
        "generated_at": now_iso(),
        "config_path": str(config_path),
        "event_count": len(deduped_events),
        "duplicates_skipped": duplicates,
        "events_by_type": dict(sorted(event_type_counter.items())),
        "events_by_adapter": dict(sorted(adapter_counter.items())),
        "schema_missing_required": dict(sorted(missing_counter.items())),
        "warnings": warnings,
        "source_status": source_status,
        "simulated_sources": True,
        "notes": [
            "sales-side inputs are simulated signals unless live adapters are enabled",
            "traffic from marketing shadow campaigns is forecast-based"
        ],
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "raw_events.latest.jsonl", deduped_events)
    write_json(out_dir / "identity_map.latest.json", identity_map)
    write_json(out_dir / "attribution_facts.latest.json", attribution_facts)
    write_json(out_dir / "ingest_report.latest.json", ingest_report)

    print(
        {
            "event_count": len(deduped_events),
            "duplicates_skipped": duplicates,
            "identity_count": identity_map.get("identity_count", 0),
            "warnings": len(warnings),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
