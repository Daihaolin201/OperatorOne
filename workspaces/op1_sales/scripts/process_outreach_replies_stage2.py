#!/usr/bin/env python3
"""Process Stage2 outreach replies and update lead + ops metrics.

Reads inbox-style reply payload and:
- classifies replies
- updates queue lead states
- appends reply events
- updates suppression list (unsubscribe)
- rolls up KPIs into handoffs/sales_to_operations.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def _find_repo_root(start: Path) -> Path:
    for candidate in [start.resolve(), *start.resolve().parents]:
        if (
            (candidate / "workspaces" / "op1_sales" / "research" / "outreach" / "outreach_events.latest.jsonl").exists()
            and (candidate / "handoffs" / "sales_to_operations.json").exists()
        ):
            return candidate
    raise FileNotFoundError("Cannot locate OperatorOne repo root. Pass --repo-root.")


def _read_json(path: Path, default: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not path.exists():
        return default or {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


CLASSIFIER_VERSION = "stage2-reply-v2"


def _contains_any(text: str, phrases: List[str]) -> bool:
    return any(p in text for p in phrases)


def _matches_any_regex(text: str, patterns: List[str]) -> bool:
    return any(re.search(p, text) is not None for p in patterns)


def _classify_reply(text: str) -> Tuple[str, str, bool]:
    t = _normalize(text)

    unsubscribe_patterns = [
        r"\bunsubscribe\b",
        r"\bstop\b",
        r"\bremove me\b",
        r"\bdo not contact\b",
        r"\bdon['’]?t email\b",
        r"\bopt out\b",
    ]
    if _matches_any_regex(t, unsubscribe_patterns):
        return "unsubscribe", "unsubscribe", False

    converted_patterns = [
        r"\bsigned\b",
        r"\bwe paid\b",
        r"\bpayment sent\b",
        r"\bpurchase\b",
        r"\bbuy\b",
        r"\bgo ahead\b",
        r"\blet['’]?s start\b",
    ]
    if _matches_any_regex(t, converted_patterns):
        return "converted", "conversion", True

    rejection_patterns = [
        r"\bnot interested\b",
        r"\bno thanks\b",
        r"\bno thank you\b",
        r"\bpass\b",
        r"\bno need\b",
        r"\balready solved\b",
        r"\balready using\b",
        r"\balready use\b",
        r"\bwe already use\b",
        r"\bnot a fit\b",
        r"\bnot for us\b",
    ]
    if _matches_any_regex(t, rejection_patterns):
        return "rejection", "no_interest", False

    not_now_patterns = [
        r"\bnot now\b",
        r"\blater\b",
        r"\bnext month\b",
        r"\bnext quarter\b",
        r"\bnext week\b",
        r"\bcircle back\b",
        r"\bfollow up later\b",
    ]
    if _matches_any_regex(t, not_now_patterns):
        return "not_now", "timing", False

    # Objection reasons
    if _contains_any(t, ["price", "cost", "budget", "expensive"]):
        return "objection", "budget", False
    if _contains_any(t, ["security", "compliance", "gdpr", "risk"]):
        return "objection", "security", False
    if _contains_any(t, ["integration", "api", "workflow", "tool", "stack"]):
        return "objection", "integration", False
    if _contains_any(t, ["time", "resources", "team", "bandwidth"]):
        return "objection", "capacity", False
    if _contains_any(t, ["who are you", "unclear", "why now", "not sure"]):
        return "objection", "trust_or_value", False

    booked_patterns = [
        r"\bbook\b",
        r"\bdemo\b",
        r"\bcall\b",
        r"\bmeeting\b",
        r"\bcalendar\b",
        r"\bschedule\b",
    ]
    if _matches_any_regex(t, booked_patterns):
        return "positive", "booked_call", True

    interested_patterns = [
        r"\binterested\b",
        r"\bsounds good\b",
        r"\bmakes sense\b",
        r"\bwant to learn more\b",
        r"\bsend details\b",
        r"\blearn more\b",
    ]
    if _matches_any_regex(t, interested_patterns):
        return "positive", "interested", False

    return "other", "uncategorized", False


def _status_for_category(category: str) -> str:
    return {
        "positive": "replied_positive",
        "converted": "customer_converted",
        "objection": "replied_objection",
        "not_now": "replied_later",
        "unsubscribe": "opted_out",
        "rejection": "closed_no_interest",
        "other": "replied_other",
    }.get(category, "replied_other")


def _ensure_inbox_template(path: Path) -> None:
    if path.exists():
        return

    template = {
        "generated_at": _now_iso(),
        "replies": [
            {
                "message_id": "",
                "lead_id": "",
                "channel": "email_nurture",
                "from": "",
                "received_at": "",
                "text": "",
            }
        ],
        "notes": [
            "Fill replies from your channel inbox export.",
            "message_id should be unique to avoid duplicate processing.",
        ],
    }
    _write_json(path, template)


def _update_suppression(payload: Dict[str, Any], lead_ids: Set[str]) -> Dict[str, Any]:
    if "opted_out_leads" not in payload:
        payload["opted_out_leads"] = []
    existing = set()
    for item in payload.get("opted_out_leads", []) or []:
        if isinstance(item, str):
            existing.add(item)
        elif isinstance(item, dict):
            lid = str(item.get("lead_id", "")).strip()
            if lid:
                existing.add(lid)

    for lead_id in sorted(lead_ids):
        if lead_id in existing:
            continue
        payload["opted_out_leads"].append(lead_id)

    payload["generated_at"] = _now_iso()
    return payload


def _rollup_ops_metrics(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    contacted = {
        str(e.get("lead_id", "")).strip()
        for e in events
        if str(e.get("event_type", "")) in {"dispatch_committed", "dispatch_manual_committed"}
        and str(e.get("lead_id", "")).strip()
    }

    replied = {
        str(e.get("lead_id", "")).strip()
        for e in events
        if str(e.get("event_type", "")).startswith("reply_")
        and str(e.get("lead_id", "")).strip()
    }

    booked = {
        str(e.get("lead_id", "")).strip()
        for e in events
        if str(e.get("event_type", "")) == "reply_positive"
        and str(e.get("detail", "")) == "booked_call"
        and str(e.get("lead_id", "")).strip()
    }

    converted = {
        str(e.get("lead_id", "")).strip()
        for e in events
        if str(e.get("event_type", "")) == "reply_converted"
        and str(e.get("lead_id", "")).strip()
    }

    objections = [
        str(e.get("detail", "")).strip()
        for e in events
        if str(e.get("event_type", "")) == "reply_objection"
    ]
    top_objections = Counter([x for x in objections if x]).most_common(5)

    return {
        "prospects_contacted": len(contacted),
        "replies": len(replied),
        "calls_booked": len(booked),
        "customers_converted": len(converted),
        "objections_summary": [
            {"reason": reason, "count": count} for reason, count in top_objections
        ],
    }


def _write_markdown(path: Path, report: Dict[str, Any]) -> None:
    summary = report.get("summary", {})
    rows = report.get("processed", [])

    lines = [
        "# Reply Processing Report (Stage2 latest)",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Classifier version: {report.get('classifier_version', '')}",
        "",
        "## Summary",
        f"- Input replies: {summary.get('input_replies', 0)}",
        f"- Processed replies: {summary.get('processed_replies', 0)}",
        f"- Skipped duplicates: {summary.get('skipped_duplicates', 0)}",
        f"- Unknown leads: {summary.get('unknown_leads', 0)}",
        f"- Unsubscribes: {summary.get('unsubscribes', 0)}",
        f"- Booked calls: {summary.get('booked_calls', 0)}",
        f"- Conversions: {summary.get('conversions', 0)}",
        "",
        "## Processed rows",
        "",
        "| Message ID | Lead ID | Category | Detail | New status |",
        "|---|---|---|---|---|",
    ]

    for row in rows:
        lines.append(
            f"| {row.get('message_id','')} | {row.get('lead_id','')} | {row.get('category','')} | {row.get('detail','')} | {row.get('new_status','')} |"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Process Stage2 outreach replies")
    p.add_argument("--repo-root", type=str, default="", help="OperatorOne repo root")
    p.add_argument(
        "--queue-file",
        type=str,
        default="",
        help="Queue file (default: outreach_queue.resolved.latest.json then fallback latest)",
    )
    p.add_argument(
        "--inbox-file",
        type=str,
        default="",
        help="Reply inbox json (default: outreach_inbox.latest.json)",
    )
    p.add_argument(
        "--events-file",
        type=str,
        default="",
        help="Events jsonl (default: outreach_events.latest.jsonl)",
    )
    p.add_argument(
        "--suppression-file",
        type=str,
        default="",
        help="Suppression list json (default: suppression_list.latest.json)",
    )
    p.add_argument(
        "--out-dir",
        type=str,
        default="",
        help="Output directory (default: research/outreach)",
    )
    p.add_argument(
        "--mode",
        type=str,
        default="commit",
        choices=["simulate", "commit"],
        help="commit updates queue/events/suppression/ops metrics",
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

    inbox_file = Path(args.inbox_file).resolve() if args.inbox_file else out_dir / "outreach_inbox.latest.json"
    events_file = Path(args.events_file).resolve() if args.events_file else out_dir / "outreach_events.latest.jsonl"
    suppression_file = Path(args.suppression_file).resolve() if args.suppression_file else out_dir / "suppression_list.latest.json"
    sales_handoff = repo_root / "handoffs" / "sales_to_operations.json"

    _ensure_inbox_template(inbox_file)

    inbox = _read_json(inbox_file)
    replies = inbox.get("replies", []) or []
    if not replies:
        print(f"Inbox template ready: {inbox_file}")
        print("No replies to process.")
        return 0

    queue = _read_json(queue_file)
    leads = queue.get("leads", []) or []
    lead_map = {str(x.get("lead_id", "")).strip(): x for x in leads}

    existing_events = _read_jsonl(events_file)
    seen_message_ids = {
        str(e.get("message_id", "")).strip()
        for e in existing_events
        if str(e.get("message_id", "")).strip()
    }

    processed_rows: List[Dict[str, Any]] = []
    new_events: List[Dict[str, Any]] = []
    unsubscribe_ids: Set[str] = set()

    summary = {
        "input_replies": len(replies),
        "processed_replies": 0,
        "skipped_duplicates": 0,
        "unknown_leads": 0,
        "unsubscribes": 0,
        "booked_calls": 0,
        "conversions": 0,
    }

    for item in replies:
        message_id = str(item.get("message_id", "")).strip()
        if message_id and message_id in seen_message_ids:
            summary["skipped_duplicates"] += 1
            continue

        lead_id = str(item.get("lead_id", "")).strip()
        text = str(item.get("text", ""))
        category, detail, signal_booked = _classify_reply(text)
        new_status = _status_for_category(category)

        if lead_id and lead_id in lead_map:
            if args.mode == "commit":
                lead_map[lead_id]["status"] = new_status
                lead_map[lead_id]["last_reply"] = {
                    "at": str(item.get("received_at", "")) or _now_iso(),
                    "channel": str(item.get("channel", "")),
                    "category": category,
                    "detail": detail,
                    "message_id": message_id,
                }
        else:
            summary["unknown_leads"] += 1

        if category == "unsubscribe" and lead_id:
            unsubscribe_ids.add(lead_id)
            summary["unsubscribes"] += 1
        if category == "converted":
            summary["conversions"] += 1
        if category == "positive" and signal_booked:
            summary["booked_calls"] += 1

        event = {
            "ts": _now_iso(),
            "event_type": f"reply_{category}",
            "lead_id": lead_id,
            "channel": str(item.get("channel", "")),
            "message_id": message_id,
            "detail": detail,
            "text_excerpt": (" ".join(text.split()))[:160],
            "classifier_version": CLASSIFIER_VERSION,
        }
        new_events.append(event)

        processed_rows.append(
            {
                "message_id": message_id,
                "lead_id": lead_id,
                "category": category,
                "detail": detail,
                "new_status": new_status,
            }
        )

        summary["processed_replies"] += 1
        if message_id:
            seen_message_ids.add(message_id)

    report = {
        "generated_at": _now_iso(),
        "builder": "workspaces/op1_sales/scripts/process_outreach_replies_stage2.py",
        "mode": args.mode,
        "classifier_version": CLASSIFIER_VERSION,
        "summary": summary,
        "processed": processed_rows,
    }

    processed_json = out_dir / "outreach_replies.processed.latest.json"
    processed_md = out_dir / "reply_processing_report.latest.md"
    objections_json = out_dir / "objections_summary.latest.json"

    objection_counts = Counter([row["detail"] for row in processed_rows if row.get("category") == "objection"])
    objections_payload = {
        "generated_at": _now_iso(),
        "top_objections": [
            {"reason": reason, "count": count} for reason, count in objection_counts.most_common(10)
        ],
    }

    _write_json(processed_json, report)
    _write_markdown(processed_md, report)
    _write_json(objections_json, objections_payload)

    if args.mode == "commit":
        # Queue update
        queue["generated_at"] = _now_iso()
        queue["reply_processor"] = "workspaces/op1_sales/scripts/process_outreach_replies_stage2.py"
        queue["leads"] = [lead_map.get(str(x.get("lead_id", "")).strip(), x) for x in leads]
        _write_json(queue_file, queue)

        # Suppression update
        suppression = _read_json(suppression_file, default={"opted_out_leads": [], "do_not_contact": []})
        suppression = _update_suppression(suppression, unsubscribe_ids)
        _write_json(suppression_file, suppression)

        # Events append
        _append_jsonl(events_file, new_events)

        # Ops rollup
        all_events = _read_jsonl(events_file)
        metrics = _rollup_ops_metrics(all_events)
        handoff = _read_json(sales_handoff, default={
            "contract_version": "1.0.0",
            "generated_at": _now_iso(),
            "generated_by": "workspaces/op1_sales/scripts/process_outreach_replies_stage2.py",
            "prospects_contacted": 0,
            "replies": 0,
            "calls_booked": 0,
            "customers_converted": 0,
            "mrr": 0,
            "objections_summary": [],
            "handoff_notes": "",
        })

        handoff["contract_version"] = "1.0.0"
        handoff["generated_at"] = _now_iso()
        handoff["generated_by"] = "workspaces/op1_sales/scripts/process_outreach_replies_stage2.py"
        handoff["prospects_contacted"] = metrics["prospects_contacted"]
        handoff["replies"] = metrics["replies"]
        handoff["calls_booked"] = metrics["calls_booked"]
        handoff["customers_converted"] = metrics["customers_converted"]
        handoff["objections_summary"] = metrics["objections_summary"]
        note = (
            f"Reply processor updated at {_now_iso()} "
            f"(processed={summary['processed_replies']}, unsub={summary['unsubscribes']}, "
            f"booked={summary['booked_calls']}, classifier={CLASSIFIER_VERSION})."
        )
        base_notes = str(handoff.get("handoff_notes", "")).strip()
        base_notes = re.sub(
            r"\s*Reply processor updated at .*?classifier=[^)]+\)\.\s*",
            " ",
            base_notes,
            flags=re.IGNORECASE,
        ).strip()
        handoff["handoff_notes"] = (base_notes + " " + note).strip()
        _write_json(sales_handoff, handoff)

    print(f"Wrote: {processed_json}")
    print(f"Wrote: {processed_md}")
    print(f"Wrote: {objections_json}")
    if args.mode == "commit":
        print(f"Updated: {queue_file}")
        print(f"Updated: {suppression_file}")
        print(f"Appended events: {events_file} (+{len(new_events)})")
        print(f"Updated: {sales_handoff}")
    else:
        print("Simulation mode: queue/suppression/events/handoff unchanged")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
