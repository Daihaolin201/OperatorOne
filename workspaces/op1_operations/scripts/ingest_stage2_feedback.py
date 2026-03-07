#!/usr/bin/env python3
"""Ingest Stage2 feedback signals into canonical raw feedback events."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from stage2_feedback_common import (
    classify_feedback,
    detect_language,
    now_iso,
    read_json,
    read_jsonl,
    resolve_repo_root,
    stable_hash,
    to_float,
    write_json,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest Stage2 feedback events")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root (auto-detect if omitted)")
    p.add_argument(
        "--adapters-config",
        default="workspaces/op1_operations/config/feedback_source_adapters.v1.json",
        help="Adapter config path (repo relative)",
    )
    p.add_argument(
        "--out-dir",
        default="workspaces/op1_operations/research/stage2_feedback",
        help="Output dir (repo relative)",
    )
    return p.parse_args()


def extract_opportunity_id(value: str | None) -> str | None:
    if not value:
        return None
    m = re.search(r"opp[_-](\d+)", str(value), flags=re.IGNORECASE)
    if not m:
        return None
    return f"opp_{m.group(1).zfill(3)}"


def load_lead_context(repo_root: Path) -> Dict[str, Dict[str, Any]]:
    path = repo_root / "workspaces/op1_sales/research/conversion/conversion_pipeline.latest.json"
    obj = read_json(path, default={}) or {}
    leads = obj.get("leads", []) if isinstance(obj.get("leads"), list) else []

    out: Dict[str, Dict[str, Any]] = {}
    for lead in leads:
        if not isinstance(lead, dict):
            continue
        lead_id = str(lead.get("lead_id") or "").strip()
        if not lead_id:
            continue
        out[lead_id] = {
            "lead_id": lead_id,
            "opportunity_id": str(lead.get("opportunity_id") or extract_opportunity_id(lead_id) or "") or None,
            "priority_band": str(lead.get("priority_band") or "") or None,
            "segment_name": str(lead.get("segment_name") or "") or None,
            "inferred_role": str(lead.get("inferred_role") or "") or None,
            "pain_signal": str(lead.get("pain_signal") or "") or None,
            "evidence_url": str(lead.get("evidence_url") or "") or None,
            "current_stage": str(lead.get("current_stage") or "") or None,
            "rank": lead.get("rank"),
            "source_subreddit": ((lead.get("source") or {}) if isinstance(lead.get("source"), dict) else {}).get("subreddit"),
        }
    return out


def make_event(
    *,
    adapter: Dict[str, Any],
    source_ref: str,
    source_path: str,
    feedback_time: str,
    raw_text: str,
    detail: str,
    event_type: str,
    channel: str,
    lead_id: str | None,
    user_id: str | None,
    anonymous_id: str | None,
    lead_ctx: Dict[str, Any] | None,
    properties: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    source_adapter = str(adapter.get("id") or "unknown")
    source_system = str(adapter.get("source_system") or "unknown")
    feedback_origin = str(adapter.get("feedback_origin") or "unknown")
    source_reliability = to_float(adapter.get("source_reliability"), 0.75)

    classification = classify_feedback(
        raw_text=raw_text,
        detail=detail,
        event_type=event_type,
        source_adapter=source_adapter,
    )

    opportunity_id = None
    if lead_ctx:
        opportunity_id = lead_ctx.get("opportunity_id")
    if not opportunity_id:
        opportunity_id = extract_opportunity_id(lead_id or source_ref or "")

    actor_id = ""
    if lead_id:
        actor_id = f"lead:{lead_id}"
    elif user_id:
        actor_id = f"user:{user_id}"
    elif anonymous_id:
        actor_id = f"anon:{anonymous_id}"
    else:
        actor_id = f"src:{source_adapter}:{source_ref}"

    feedback_id = "fb_" + stable_hash(
        [source_adapter, source_ref, feedback_time, actor_id, event_type, raw_text, detail],
        length=40,
    )

    base_confidence = 0.82 if feedback_origin in {"solicited", "prompted"} else 0.7
    confidence = max(0.0, min(1.0, (base_confidence * 0.65) + (source_reliability * 0.35)))

    evidence_weight = max(0.0, min(1.0, source_reliability))

    return {
        "feedback_id": feedback_id,
        "feedback_time": feedback_time,
        "source_adapter": source_adapter,
        "source_system": source_system,
        "source_ref": source_ref,
        "source_path": source_path,
        "feedback_origin": feedback_origin,
        "actor_id": actor_id,
        "lead_id": lead_id or None,
        "user_id": user_id or None,
        "anonymous_id": anonymous_id or None,
        "opportunity_id": opportunity_id,
        "channel": channel or "unknown",
        "language": detect_language(raw_text),
        "raw_text": str(raw_text or "").strip() or str(detail or "").strip(),
        "detail": str(detail or "").strip() or None,
        "event_type": event_type,
        "feedback_type": classification["feedback_type"],
        "topic": classification["topic"],
        "subtopic": classification["subtopic"],
        "journey_stage": classification["journey_stage"],
        "severity": classification["severity"],
        "urgency": classification["urgency"],
        "sentiment": classification["sentiment"],
        "sentiment_score": classification["sentiment_score"],
        "evidence_weight": round(evidence_weight, 4),
        "confidence": round(confidence, 4),
        "priority_band": (lead_ctx or {}).get("priority_band") if isinstance(lead_ctx, dict) else None,
        "segment_name": (lead_ctx or {}).get("segment_name") if isinstance(lead_ctx, dict) else None,
        "current_stage": (lead_ctx or {}).get("current_stage") if isinstance(lead_ctx, dict) else None,
        "evidence_url": (lead_ctx or {}).get("evidence_url") if isinstance(lead_ctx, dict) else None,
        "properties": properties or {},
    }


def ingest_outreach_replies(
    *,
    rows: List[Dict[str, Any]],
    adapter: Dict[str, Any],
    source_path: str,
    lead_context: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        ev = str(row.get("event_type") or "").strip().lower()
        if not ev.startswith("reply_"):
            continue

        lead_id = str(row.get("lead_id") or "").strip() or None
        lead_ctx = lead_context.get(lead_id or "", {})
        out.append(
            make_event(
                adapter=adapter,
                source_ref=str(row.get("message_id") or row.get("batch_id") or ev),
                source_path=source_path,
                feedback_time=str(row.get("ts") or now_iso()),
                raw_text=str(row.get("text_excerpt") or row.get("raw_text") or row.get("detail") or ev),
                detail=str(row.get("detail") or ""),
                event_type=ev,
                channel=str(row.get("channel") or "unknown"),
                lead_id=lead_id,
                user_id=None,
                anonymous_id=None,
                lead_ctx=lead_ctx,
                properties={
                    "batch_id": row.get("batch_id"),
                    "target": row.get("target"),
                },
            )
        )
    return out


def ingest_conversion_events(
    *,
    rows: List[Dict[str, Any]],
    adapter: Dict[str, Any],
    source_path: str,
    lead_context: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    allowed = {"objection_logged", "closed_lost", "discovery_scheduled", "paid_started"}
    out: List[Dict[str, Any]] = []
    for row in rows:
        ev = str(row.get("event_type") or "").strip().lower()
        if ev not in allowed:
            continue

        lead_id = str(row.get("lead_id") or "").strip() or None
        lead_ctx = lead_context.get(lead_id or "", {})
        detail = str(row.get("detail") or row.get("stage") or ev)

        out.append(
            make_event(
                adapter=adapter,
                source_ref=str(row.get("source_ref") or row.get("source_key") or ev),
                source_path=source_path,
                feedback_time=str(row.get("ts") or row.get("created_at") or now_iso()),
                raw_text=detail,
                detail=detail,
                event_type=ev,
                channel=str(row.get("channel") or "unknown"),
                lead_id=lead_id,
                user_id=None,
                anonymous_id=None,
                lead_ctx=lead_ctx,
                properties={
                    "source": row.get("source"),
                    "stage": row.get("stage"),
                },
            )
        )
    return out


def ingest_pipeline_pains(
    *,
    payload: Dict[str, Any],
    adapter: Dict[str, Any],
    source_path: str,
) -> List[Dict[str, Any]]:
    leads = payload.get("leads", []) if isinstance(payload.get("leads"), list) else []
    generated_at = str(payload.get("generated_at") or now_iso())

    out: List[Dict[str, Any]] = []
    for lead in leads:
        if not isinstance(lead, dict):
            continue

        lead_id = str(lead.get("lead_id") or "").strip() or None
        pain_signal = str(lead.get("pain_signal") or "").strip()
        if not pain_signal:
            continue

        feedback_time = str(lead.get("stage_entered_at") or generated_at)
        out.append(
            make_event(
                adapter=adapter,
                source_ref=lead_id or stable_hash([pain_signal], 16),
                source_path=source_path,
                feedback_time=feedback_time,
                raw_text=pain_signal,
                detail=str(lead.get("segment_name") or "pain_signal"),
                event_type="pain_signal",
                channel=str((((lead.get("source") or {}) if isinstance(lead.get("source"), dict) else {}).get("subreddit")) or "social_signal"),
                lead_id=lead_id,
                user_id=None,
                anonymous_id=None,
                lead_ctx={
                    "opportunity_id": lead.get("opportunity_id"),
                    "priority_band": lead.get("priority_band"),
                    "segment_name": lead.get("segment_name"),
                    "current_stage": lead.get("current_stage"),
                    "evidence_url": lead.get("evidence_url"),
                },
                properties={
                    "rank": lead.get("rank"),
                    "fit_status": lead.get("fit_status"),
                    "evidence_url": lead.get("evidence_url"),
                },
            )
        )

    return out


def ingest_manual_notes(
    *,
    rows: List[Dict[str, Any]],
    adapter: Dict[str, Any],
    source_path: str,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_text = str(row.get("raw_text") or row.get("text") or row.get("note") or "").strip()
        if not raw_text:
            continue

        out.append(
            make_event(
                adapter=adapter,
                source_ref=str(row.get("source_ref") or row.get("feedback_id") or stable_hash([raw_text], 16)),
                source_path=source_path,
                feedback_time=str(row.get("feedback_time") or row.get("ts") or now_iso()),
                raw_text=raw_text,
                detail=str(row.get("detail") or row.get("label") or "manual_note"),
                event_type=str(row.get("event_type") or "manual_feedback"),
                channel=str(row.get("channel") or "manual"),
                lead_id=str(row.get("lead_id") or "").strip() or None,
                user_id=str(row.get("user_id") or "").strip() or None,
                anonymous_id=str(row.get("anonymous_id") or "").strip() or None,
                lead_ctx={
                    "opportunity_id": row.get("opportunity_id"),
                    "priority_band": row.get("priority_band"),
                    "segment_name": row.get("segment_name"),
                    "current_stage": row.get("current_stage"),
                    "evidence_url": row.get("evidence_url"),
                },
                properties={
                    "manual_tags": row.get("tags") if isinstance(row.get("tags"), list) else [],
                },
            )
        )
    return out


def ingest_product_runtime(
    *,
    rows: List[Dict[str, Any]],
    adapter: Dict[str, Any],
    source_path: str,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        event_name = str(row.get("event_type") or row.get("event_name") or "").strip().lower()
        if event_name not in {"feedback_submitted", "nps_submitted", "csat_submitted", "issue_reported"}:
            continue

        raw_text = str(row.get("raw_text") or row.get("text") or row.get("comment") or event_name)
        out.append(
            make_event(
                adapter=adapter,
                source_ref=str(row.get("source_ref") or row.get("event_id") or stable_hash([event_name, raw_text], 16)),
                source_path=source_path,
                feedback_time=str(row.get("feedback_time") or row.get("event_time") or row.get("ts") or now_iso()),
                raw_text=raw_text,
                detail=str(row.get("detail") or event_name),
                event_type=event_name,
                channel=str(row.get("channel") or row.get("event_source") or "product_runtime"),
                lead_id=str(row.get("lead_id") or "").strip() or None,
                user_id=str(row.get("user_id") or "").strip() or None,
                anonymous_id=str(row.get("anonymous_id") or "").strip() or None,
                lead_ctx={
                    "opportunity_id": row.get("opportunity_id"),
                    "priority_band": row.get("priority_band"),
                    "segment_name": row.get("segment_name"),
                    "current_stage": row.get("current_stage"),
                    "evidence_url": row.get("evidence_url"),
                },
                properties={
                    "rating": row.get("rating"),
                    "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
                },
            )
        )
    return out


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else resolve_repo_root(Path(__file__))

    cfg_path = repo_root / args.adapters_config
    out_dir = repo_root / args.out_dir

    cfg = read_json(cfg_path, default={}) or {}
    adapters = cfg.get("adapters", []) if isinstance(cfg.get("adapters"), list) else []

    lead_context = load_lead_context(repo_root)

    events: List[Dict[str, Any]] = []
    source_status: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for adapter in adapters:
        adapter_id = str(adapter.get("id") or "").strip()
        if not adapter_id:
            continue

        enabled = bool(adapter.get("enabled", True))
        source_rel = str(adapter.get("path") or "")
        source_path = repo_root / source_rel if source_rel else None

        status = {
            "adapter_id": adapter_id,
            "enabled": enabled,
            "optional": bool(adapter.get("optional", False)),
            "path": str(source_path) if source_path else None,
            "exists": bool(source_path and source_path.exists()),
            "events_added": 0,
        }

        if not enabled:
            source_status.append(status)
            continue

        if source_path is None or not source_path.exists():
            if status["optional"]:
                warnings.append(f"optional adapter missing: {adapter_id}")
                source_status.append(status)
                continue
            warnings.append(f"required adapter missing: {adapter_id}")
            source_status.append(status)
            continue

        adapter_events: List[Dict[str, Any]] = []

        if adapter_id == "sales_outreach_replies":
            adapter_events = ingest_outreach_replies(
                rows=read_jsonl(source_path),
                adapter=adapter,
                source_path=source_rel,
                lead_context=lead_context,
            )
        elif adapter_id == "sales_conversion_events":
            adapter_events = ingest_conversion_events(
                rows=read_jsonl(source_path),
                adapter=adapter,
                source_path=source_rel,
                lead_context=lead_context,
            )
        elif adapter_id == "conversion_pipeline_pains":
            adapter_events = ingest_pipeline_pains(
                payload=read_json(source_path, default={}) or {},
                adapter=adapter,
                source_path=source_rel,
            )
        elif adapter_id == "manual_feedback_notes":
            adapter_events = ingest_manual_notes(
                rows=read_jsonl(source_path),
                adapter=adapter,
                source_path=source_rel,
            )
        elif adapter_id == "product_runtime_feedback":
            adapter_events = ingest_product_runtime(
                rows=read_jsonl(source_path),
                adapter=adapter,
                source_path=source_rel,
            )
        else:
            warnings.append(f"adapter not recognized: {adapter_id}")

        status["events_added"] = len(adapter_events)
        source_status.append(status)
        events.extend(adapter_events)

    # Deduplicate by feedback_id.
    dedup: Dict[str, Dict[str, Any]] = {}
    dup_count = 0
    for ev in sorted(events, key=lambda r: (str(r.get("feedback_time")), str(r.get("feedback_id")))):
        fid = str(ev.get("feedback_id") or "")
        if not fid:
            continue
        if fid in dedup:
            dup_count += 1
            continue
        dedup[fid] = ev

    rows = list(dedup.values())

    by_type = Counter(str(r.get("feedback_type") or "unknown") for r in rows)
    by_topic = Counter(str(r.get("topic") or "general") for r in rows)
    by_adapter = Counter(str(r.get("source_adapter") or "unknown") for r in rows)

    ingest_report = {
        "generated_at": now_iso(),
        "config_path": str(cfg_path),
        "event_count": len(rows),
        "duplicates_skipped": dup_count,
        "feedback_type_mix": dict(sorted(by_type.items())),
        "topic_mix": dict(sorted(by_topic.items())),
        "events_by_adapter": dict(sorted(by_adapter.items())),
        "source_status": source_status,
        "warnings": warnings,
        "mode": "simulated_signals",
        "notes": [
            "Input includes sales-side simulated signals and pipeline pain statements.",
            "Adapters are externalized for future live-source migration."
        ],
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "raw_feedback_events.latest.jsonl", rows)
    write_json(out_dir / "feedback_ingest_report.latest.json", ingest_report)

    print({"event_count": len(rows), "duplicates_skipped": dup_count, "warnings": len(warnings)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
