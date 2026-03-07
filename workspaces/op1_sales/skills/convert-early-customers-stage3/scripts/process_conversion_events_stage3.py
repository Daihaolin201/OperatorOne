#!/usr/bin/env python3
"""Ingest conversion signals and append Stage3 conversion events.

Sources:
- Stage2 outreach events (`research/outreach/outreach_events.latest.jsonl`)
- Manual conversion signal inbox (`research/conversion/conversion_signal_inbox.latest.json`)

Output:
- `research/conversion/conversion_events.latest.jsonl`
- `research/conversion/conversion_signal_processing.latest.json`
- `research/conversion/conversion_signal_processing.latest.md`
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from conversion_stage3_common import (  # noqa: E402
    append_jsonl,
    find_repo_root,
    now_iso,
    normalize,
    parse_iso,
    read_json,
    read_jsonl,
    write_json,
)


MANUAL_SIGNAL_TYPES = {
    "discovery_scheduled",
    "discovery_completed",
    "pilot_offered",
    "pilot_started",
    "pilot_value_confirmed",
    "terms_sent",
    "commitment_received",
    "paid_started",
    "closed_lost",
    "objection_logged",
    "objection_resolved",
    "conversion_stage_changed",
}


def _hash_key(parts: List[str]) -> str:
    material = "|".join(parts)
    return hashlib.sha1(material.encode("utf-8")).hexdigest()[:16]


def _ensure_signal_inbox(path: Path) -> None:
    if path.exists():
        return

    template = {
        "generated_at": now_iso(),
        "signals": [
            {
                "signal_id": "",
                "lead_id": "",
                "signal_type": "commitment_received",
                "detail": "",
                "text": "",
                "occurred_at": "",
                "source": "manual_note",
            }
        ],
        "allowed_signal_types": sorted(MANUAL_SIGNAL_TYPES),
        "notes": [
            "Fill only real conversion signals.",
            "signal_id should be unique to avoid duplicate ingestion.",
            "Use signal_type from allowed_signal_types list.",
        ],
    }
    write_json(path, template)


def _map_stage2_event(ev: Dict[str, Any]) -> List[Dict[str, Any]]:
    et = str(ev.get("event_type", "")).strip()
    lead_id = str(ev.get("lead_id", "")).strip()
    ts = str(ev.get("ts", "")).strip()
    detail = str(ev.get("detail", "")).strip()
    channel = str(ev.get("channel", "")).strip()

    if not lead_id or not ts:
        return []

    base = {
        "ts": ts,
        "lead_id": lead_id,
        "source": "stage2_events",
        "source_ref": str(ev.get("message_id", "") or ""),
        "detail": detail,
        "channel": channel,
    }

    out: List[Dict[str, Any]] = []

    if et in {"dispatch_committed", "dispatch_manual_committed"}:
        out.append({**base, "event_type": "conversion_stage_changed", "stage": "qualified_interest", "detail": detail or "contacted"})
    elif et == "reply_positive":
        out.append({**base, "event_type": "discovery_scheduled", "detail": detail or "positive_reply"})
    elif et == "reply_not_now":
        out.append({**base, "event_type": "conversion_stage_changed", "stage": "qualified_interest", "detail": "timing_hold"})
    elif et == "reply_objection":
        out.append({**base, "event_type": "objection_logged", "detail": detail or "unknown_objection"})
    elif et == "reply_converted":
        out.append({**base, "event_type": "paid_started", "detail": detail or "conversion"})
    elif et == "reply_rejection":
        out.append({**base, "event_type": "closed_lost", "detail": detail or "no_interest"})
    elif et == "reply_unsubscribe":
        out.append({**base, "event_type": "closed_lost", "detail": "unsubscribe"})

    return out


def _map_manual_signal(item: Dict[str, Any]) -> Dict[str, Any] | None:
    lead_id = str(item.get("lead_id", "")).strip()
    signal_type = str(item.get("signal_type", "")).strip()
    if not lead_id or signal_type not in MANUAL_SIGNAL_TYPES:
        return None

    ts = str(item.get("occurred_at", "")).strip() or now_iso()
    if not parse_iso(ts):
        ts = now_iso()

    signal_id = str(item.get("signal_id", "")).strip()
    source = str(item.get("source", "")).strip() or "manual_signal"
    detail = str(item.get("detail", "")).strip()
    text = str(item.get("text", "")).strip()

    event: Dict[str, Any] = {
        "ts": ts,
        "event_type": signal_type,
        "lead_id": lead_id,
        "detail": detail,
        "text_excerpt": (" ".join(text.split()))[:180],
        "source": "manual_signal_inbox",
        "source_ref": signal_id,
        "signal_source": source,
    }

    if signal_type == "conversion_stage_changed":
        stage = str(item.get("stage", "")).strip() or "qualified_interest"
        event["stage"] = stage

    return event


def _event_source_key(event: Dict[str, Any]) -> str:
    if event.get("source") == "manual_signal_inbox":
        sid = str(event.get("source_ref", "")).strip()
        if sid:
            return f"manual:{sid}"

    parts = [
        str(event.get("source", "")),
        str(event.get("ts", "")),
        str(event.get("event_type", "")),
        str(event.get("lead_id", "")),
        str(event.get("detail", "")),
        str(event.get("source_ref", "")),
    ]
    return f"hash:{_hash_key(parts)}"


def _write_md(path: Path, report: Dict[str, Any]) -> None:
    summary = report.get("summary", {})
    rows = report.get("new_events", [])

    lines = [
        "# Conversion Signal Processing (Stage3 latest)",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Mode: {report.get('mode', '')}",
        "",
        "## Summary",
        f"- Stage2 events scanned: {summary.get('stage2_events_scanned', 0)}",
        f"- Manual signals scanned: {summary.get('manual_signals_scanned', 0)}",
        f"- Candidate conversion events: {summary.get('candidate_events', 0)}",
        f"- Duplicates skipped: {summary.get('duplicates_skipped', 0)}",
        f"- New events appended: {summary.get('new_events_appended', 0)}",
        "",
        "## New events",
        "",
        "| ts | lead_id | event_type | detail | source_key |",
        "|---|---|---|---|---|",
    ]

    for row in rows:
        lines.append(
            f"| {row.get('ts','')} | {row.get('lead_id','')} | {row.get('event_type','')} | {row.get('detail','')} | {row.get('source_key','')} |"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Process Stage3 conversion events")
    p.add_argument("--repo-root", type=str, default="", help="OperatorOne repo root")
    p.add_argument("--mode", type=str, default="commit", choices=["simulate", "commit"], help="commit appends events")
    p.add_argument("--out-dir", type=str, default="", help="Output dir (default: research/conversion)")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    out_dir = Path(args.out_dir).resolve() if args.out_dir else repo_root / "workspaces" / "op1_sales" / "research" / "conversion"
    out_dir.mkdir(parents=True, exist_ok=True)

    stage2_events_file = repo_root / "workspaces" / "op1_sales" / "research" / "outreach" / "outreach_events.latest.jsonl"
    manual_signal_file = out_dir / "conversion_signal_inbox.latest.json"
    conversion_events_file = out_dir / "conversion_events.latest.jsonl"

    _ensure_signal_inbox(manual_signal_file)

    stage2_events = read_jsonl(stage2_events_file)
    manual_payload = read_json(manual_signal_file, default={"signals": []})
    manual_signals = manual_payload.get("signals", []) or []
    existing_events = read_jsonl(conversion_events_file)
    existing_keys = {str(e.get("source_key", "")).strip() for e in existing_events if str(e.get("source_key", "")).strip()}

    candidates: List[Dict[str, Any]] = []

    for ev in stage2_events:
        candidates.extend(_map_stage2_event(ev))

    for sig in manual_signals:
        mapped = _map_manual_signal(sig)
        if mapped:
            candidates.append(mapped)

    new_events: List[Dict[str, Any]] = []
    dup = 0
    type_counter: Counter[str] = Counter()

    for ev in candidates:
        source_key = _event_source_key(ev)
        if source_key in existing_keys:
            dup += 1
            continue

        ev_copy = dict(ev)
        ev_copy["source_key"] = source_key
        if not ev_copy.get("created_at"):
            ev_copy["created_at"] = now_iso()

        new_events.append(ev_copy)
        existing_keys.add(source_key)
        type_counter[str(ev_copy.get("event_type", "unknown"))] += 1

    if args.mode == "commit" and new_events:
        # Keep chronological append order.
        new_events.sort(key=lambda x: str(x.get("ts", "")))
        append_jsonl(conversion_events_file, new_events)

    report = {
        "generated_at": now_iso(),
        "builder": "workspaces/op1_sales/scripts/process_conversion_events_stage3.py",
        "mode": args.mode,
        "summary": {
            "stage2_events_scanned": len(stage2_events),
            "manual_signals_scanned": len(manual_signals),
            "candidate_events": len(candidates),
            "duplicates_skipped": dup,
            "new_events_appended": len(new_events) if args.mode == "commit" else 0,
            "new_events_simulated": len(new_events) if args.mode == "simulate" else 0,
            "event_type_mix": dict(type_counter),
        },
        "new_events": new_events,
    }

    report_json = out_dir / "conversion_signal_processing.latest.json"
    report_md = out_dir / "conversion_signal_processing.latest.md"
    write_json(report_json, report)
    _write_md(report_md, report)

    print(f"Ensured: {manual_signal_file}")
    print(f"Wrote: {report_json}")
    print(f"Wrote: {report_md}")
    if args.mode == "commit":
        print(f"Appended events: {conversion_events_file} (+{len(new_events)})")
    else:
        print("Simulation mode: conversion events unchanged")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
