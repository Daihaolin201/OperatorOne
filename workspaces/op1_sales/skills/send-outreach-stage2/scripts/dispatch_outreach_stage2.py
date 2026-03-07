#!/usr/bin/env python3
"""Dispatch Stage2 outreach batch (stateful, approval-gated).

This script does NOT directly call provider APIs.
It produces send requests + manual bundle and updates queue/event state.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Set


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _now_iso() -> str:
    return _now().replace(microsecond=0).isoformat()


def _parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _find_repo_root(start: Path) -> Path:
    for candidate in [start.resolve(), *start.resolve().parents]:
        if (
            (candidate / "workspaces" / "op1_sales" / "research" / "outreach" / "outreach_batch.ready.json").exists()
            and (candidate / "handoffs" / "sales_to_operations.json").exists()
        ):
            return candidate
    raise FileNotFoundError("Cannot locate OperatorOne repo root. Pass --repo-root.")


def _read_json(path: Path, default: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not path.exists():
        return default or {}
    return json.loads(path.read_text())


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _append_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _suppression_set(payload: Dict[str, Any]) -> Set[str]:
    out: Set[str] = set()

    for key in ["opted_out_leads", "do_not_contact"]:
        for item in payload.get(key, []) or []:
            if isinstance(item, str):
                out.add(item.strip())
            elif isinstance(item, dict):
                lead_id = str(item.get("lead_id", "")).strip()
                if lead_id:
                    out.add(lead_id)
    return out


def _lead_text_for_channel(lead: Dict[str, Any], channel: str) -> Dict[str, str]:
    pack = lead.get("message_pack", {}) or {}
    if channel == "email_nurture":
        email = pack.get("email_nurture", {}) or {}
        subject = str(email.get("subject_control", "")).strip()
        body = str(email.get("body", "")).strip()
        return {"subject": subject, "body": body}
    if channel == "linkedin":
        li = pack.get("linkedin", {}) or {}
        body = str(li.get("initial", "")).strip()
        return {"subject": "", "body": body}

    # manual fallback uses email body by default
    email = pack.get("email_nurture", {}) or {}
    return {
        "subject": str(email.get("subject_control", "")).strip(),
        "body": str(email.get("body", "")).strip(),
    }


def _recent_dispatched(events: List[Dict[str, Any]], window_hours: int) -> Set[str]:
    cutoff = _now() - timedelta(hours=window_hours)
    out: Set[str] = set()
    for e in events:
        et = str(e.get("event_type", ""))
        if et not in {"dispatch_committed", "dispatch_manual_committed"}:
            continue
        ts = _parse_iso(str(e.get("ts", "")))
        if ts and ts >= cutoff:
            lead_id = str(e.get("lead_id", "")).strip()
            if lead_id:
                out.add(lead_id)
    return out


def _daily_dispatch_count(events: List[Dict[str, Any]]) -> int:
    today = _now().date()
    count = 0
    for e in events:
        et = str(e.get("event_type", ""))
        if et not in {"dispatch_committed", "dispatch_manual_committed"}:
            continue
        ts = _parse_iso(str(e.get("ts", "")))
        if ts and ts.date() == today:
            count += 1
    return count


def _write_markdown(path: Path, report: Dict[str, Any], manual_items: List[Dict[str, Any]]) -> None:
    summary = report.get("summary", {})
    leads = report.get("leads", [])

    lines = [
        "# Outreach Dispatch Report (Stage2 latest)",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Mode: {report.get('mode', '')}",
        f"Batch: {report.get('batch_id', '')}",
        "",
        "## Summary",
        f"- Eligible in batch: {summary.get('eligible_in_batch', 0)}",
        f"- Processed: {summary.get('processed', 0)}",
        f"- Dispatched direct: {summary.get('dispatched_direct', 0)}",
        f"- Dispatched manual: {summary.get('dispatched_manual', 0)}",
        f"- Suppressed: {summary.get('suppressed', 0)}",
        f"- Skipped review: {summary.get('skipped_review', 0)}",
        f"- Skipped cap/frequency: {summary.get('skipped_cap_or_frequency', 0)}",
        "",
        "## Lead outcomes",
        "",
        "| Lead ID | Result | Channel | Target | Note |",
        "|---|---|---|---|---|",
    ]

    for row in leads:
        lines.append(
            f"| {row.get('lead_id','')} | {row.get('result','')} | {row.get('channel','')} | {row.get('target','')} | {row.get('note','')} |"
        )

    if manual_items:
        lines.extend(["", "## Manual bundle generated", "", f"Items: {len(manual_items)}"])

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _write_manual_bundle(path: Path, report: Dict[str, Any], manual_items: List[Dict[str, Any]]) -> None:
    lines = [
        "# Manual Dispatch Bundle (Stage2 latest)",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Batch: {report.get('batch_id', '')}",
        "",
    ]

    if not manual_items:
        lines.append("No manual items in this run.")
    else:
        for idx, item in enumerate(manual_items, start=1):
            lines.extend(
                [
                    f"## {idx}. {item.get('lead_id', '')}",
                    f"- Channel: {item.get('channel', '')}",
                    f"- Priority: {item.get('priority_band', '')}",
                    f"- Evidence: {item.get('evidence_url', '')}",
                    f"- Subject: {item.get('subject', '')}",
                    "- Body:",
                    item.get("body", ""),
                    "",
                ]
            )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Dispatch Stage2 outreach batch")
    p.add_argument("--repo-root", type=str, default="", help="OperatorOne repo root")
    p.add_argument(
        "--queue-file",
        type=str,
        default="",
        help="Resolved queue JSON (default: outreach_queue.resolved.latest.json)",
    )
    p.add_argument(
        "--batch-file",
        type=str,
        default="",
        help="Approved batch JSON (default: outreach_batch.approved.json)",
    )
    p.add_argument(
        "--suppression-file",
        type=str,
        default="",
        help="Suppression list JSON (default: suppression_list.latest.json)",
    )
    p.add_argument(
        "--events-file",
        type=str,
        default="",
        help="Events JSONL (default: outreach_events.latest.jsonl)",
    )
    p.add_argument(
        "--mode",
        type=str,
        default="simulate",
        choices=["simulate", "commit"],
        help="simulate = no state write; commit = write queue/events/reports",
    )
    p.add_argument(
        "--out-dir",
        type=str,
        default="",
        help="Output dir (default: research/outreach)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else _find_repo_root(Path.cwd())
    out_dir = Path(args.out_dir).resolve() if args.out_dir else repo_root / "workspaces" / "op1_sales" / "research" / "outreach"
    out_dir.mkdir(parents=True, exist_ok=True)

    queue_file = Path(args.queue_file).resolve() if args.queue_file else out_dir / "outreach_queue.resolved.latest.json"
    if not queue_file.exists():
        queue_file = out_dir / "outreach_queue.latest.json"

    batch_file = Path(args.batch_file).resolve() if args.batch_file else out_dir / "outreach_batch.approved.json"
    suppression_file = Path(args.suppression_file).resolve() if args.suppression_file else out_dir / "suppression_list.latest.json"
    events_file = Path(args.events_file).resolve() if args.events_file else out_dir / "outreach_events.latest.jsonl"

    queue_payload = _read_json(queue_file)
    batch = _read_json(batch_file)
    if not batch:
        raise SystemExit(f"Missing batch file: {batch_file}")
    if not bool(batch.get("approved", False)):
        raise SystemExit("Batch is not approved. Approve batch first.")

    suppression = _read_json(suppression_file, default={"opted_out_leads": [], "do_not_contact": []})
    suppression_ids = _suppression_set(suppression)

    events = _read_jsonl(events_file)

    frequency_cap_hours = int((batch.get("dispatch_policy", {}) or {}).get("frequency_cap_hours", 48) or 48)
    max_send_per_day = int((batch.get("dispatch_policy", {}) or {}).get("max_send_per_day", 20) or 20)
    recent_sent = _recent_dispatched(events, frequency_cap_hours)
    sent_today = _daily_dispatch_count(events)

    eligible_ids = {str(x).strip() for x in (batch.get("lead_ids", []) or []) if str(x).strip()}

    leads = queue_payload.get("leads", []) or []
    lead_map = {str(x.get("lead_id", "")).strip(): x for x in leads}

    report_rows: List[Dict[str, Any]] = []
    manual_items: List[Dict[str, Any]] = []
    send_requests: List[Dict[str, Any]] = []
    new_events: List[Dict[str, Any]] = []

    summary = {
        "eligible_in_batch": len(eligible_ids),
        "processed": 0,
        "dispatched_direct": 0,
        "dispatched_manual": 0,
        "suppressed": 0,
        "skipped_review": 0,
        "skipped_cap_or_frequency": 0,
        "skipped_missing": 0,
    }

    for lead_id in batch.get("lead_ids", []) or []:
        lead_id = str(lead_id).strip()
        if not lead_id:
            continue
        lead = lead_map.get(lead_id)
        if not lead:
            summary["skipped_missing"] += 1
            report_rows.append({
                "lead_id": lead_id,
                "result": "skipped_missing",
                "channel": "",
                "target": "",
                "note": "lead_id not found in queue",
            })
            continue

        summary["processed"] += 1

        status = str(lead.get("status", ""))
        if status in {"needs_review", "awaiting_contact"}:
            summary["skipped_review"] += 1
            report_rows.append({
                "lead_id": lead_id,
                "result": "skipped_review",
                "channel": "",
                "target": "",
                "note": f"status={status}",
            })
            continue

        if lead_id in suppression_ids or status == "opted_out":
            summary["suppressed"] += 1
            report_rows.append({
                "lead_id": lead_id,
                "result": "suppressed",
                "channel": "",
                "target": "",
                "note": "lead is in suppression list",
            })
            new_events.append(
                {
                    "ts": _now_iso(),
                    "event_type": "dispatch_suppressed",
                    "lead_id": lead_id,
                    "batch_id": batch.get("batch_id", ""),
                    "detail": "suppression_list",
                }
            )
            continue

        if lead_id in recent_sent or sent_today >= max_send_per_day:
            summary["skipped_cap_or_frequency"] += 1
            reason = "frequency_cap" if lead_id in recent_sent else "daily_cap"
            report_rows.append({
                "lead_id": lead_id,
                "result": "skipped_cap_or_frequency",
                "channel": "",
                "target": "",
                "note": reason,
            })
            new_events.append(
                {
                    "ts": _now_iso(),
                    "event_type": "dispatch_skipped_cap_or_frequency",
                    "lead_id": lead_id,
                    "batch_id": batch.get("batch_id", ""),
                    "detail": reason,
                }
            )
            continue

        route = ((lead.get("contact_resolution", {}) or {}).get("primary_route", {}) or {})
        route_type = str(route.get("route_type", "manual")).strip() or "manual"
        channel = str(route.get("channel", "")).strip() or "manual_export"
        target = str(route.get("target", "")).strip()

        text_payload = _lead_text_for_channel(lead, channel)

        if route_type == "direct" and channel in {"email_nurture", "linkedin"} and target:
            summary["dispatched_direct"] += 1
            sent_today += 1

            send_requests.append(
                {
                    "lead_id": lead_id,
                    "channel": channel,
                    "target": target,
                    "subject": text_payload.get("subject", ""),
                    "message": text_payload.get("body", ""),
                    "mode": "prepared",
                }
            )

            report_rows.append(
                {
                    "lead_id": lead_id,
                    "result": "dispatch_prepared_direct",
                    "channel": channel,
                    "target": target,
                    "note": "send request emitted",
                }
            )

            new_events.append(
                {
                    "ts": _now_iso(),
                    "event_type": "dispatch_committed",
                    "lead_id": lead_id,
                    "batch_id": batch.get("batch_id", ""),
                    "channel": channel,
                    "target": target,
                    "detail": "prepared_for_provider_send",
                }
            )

            if args.mode == "commit":
                lead["status"] = "dispatched_prepared"
                lead["last_dispatch"] = {
                    "at": _now_iso(),
                    "channel": channel,
                    "target": target,
                    "result": "prepared",
                }

        else:
            summary["dispatched_manual"] += 1
            sent_today += 1

            manual_item = {
                "lead_id": lead_id,
                "priority_band": lead.get("priority_band", ""),
                "channel": channel if channel and channel != "manual_export" else "manual_export",
                "target": target,
                "evidence_url": lead.get("evidence_url", ""),
                "subject": text_payload.get("subject", ""),
                "body": text_payload.get("body", ""),
            }
            manual_items.append(manual_item)

            report_rows.append(
                {
                    "lead_id": lead_id,
                    "result": "dispatch_manual_bundle",
                    "channel": manual_item["channel"],
                    "target": manual_item["target"],
                    "note": "manual bundle item emitted",
                }
            )

            new_events.append(
                {
                    "ts": _now_iso(),
                    "event_type": "dispatch_manual_committed",
                    "lead_id": lead_id,
                    "batch_id": batch.get("batch_id", ""),
                    "channel": manual_item["channel"],
                    "target": manual_item["target"],
                    "detail": "manual_bundle",
                }
            )

            if args.mode == "commit":
                lead["status"] = "dispatched_manual"
                lead["last_dispatch"] = {
                    "at": _now_iso(),
                    "channel": manual_item["channel"],
                    "target": manual_item["target"],
                    "result": "manual_bundle",
                }

    report = {
        "generated_at": _now_iso(),
        "builder": "workspaces/op1_sales/scripts/dispatch_outreach_stage2.py",
        "mode": args.mode,
        "batch_id": batch.get("batch_id", ""),
        "summary": summary,
        "leads": report_rows,
    }

    report_json = out_dir / "outreach_dispatch_report.latest.json"
    report_md = out_dir / "outreach_dispatch_report.latest.md"
    send_requests_json = out_dir / "outreach_send_requests.latest.json"
    manual_bundle_md = out_dir / "outreach_manual_dispatch_bundle.latest.md"

    _write_json(report_json, report)
    _write_markdown(report_md, report, manual_items)
    _write_json(send_requests_json, {"generated_at": _now_iso(), "batch_id": batch.get("batch_id", ""), "requests": send_requests})
    _write_manual_bundle(manual_bundle_md, report, manual_items)

    if args.mode == "commit":
        queue_payload["generated_at"] = _now_iso()
        queue_payload["dispatcher"] = "workspaces/op1_sales/scripts/dispatch_outreach_stage2.py"
        queue_payload["leads"] = leads
        _write_json(queue_file, queue_payload)
        _append_jsonl(events_file, new_events)

    print(f"Wrote: {report_json}")
    print(f"Wrote: {report_md}")
    print(f"Wrote: {send_requests_json}")
    print(f"Wrote: {manual_bundle_md}")
    if args.mode == "commit":
        print(f"Updated: {queue_file}")
        print(f"Appended events: {events_file} (+{len(new_events)})")
    else:
        print("Simulation mode: queue/events unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
