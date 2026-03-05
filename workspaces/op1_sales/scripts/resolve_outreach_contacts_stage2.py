#!/usr/bin/env python3
"""Resolve Stage2 outreach queue against a contact registry.

Purpose:
- Attach contact routes to queued leads.
- Mark dispatch eligibility.
- Keep low-fit leads in review state.

This script does not send messages.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def _find_repo_root(start: Path) -> Path:
    for candidate in [start.resolve(), *start.resolve().parents]:
        if (
            (candidate / "workspaces" / "op1_sales" / "research" / "outreach" / "outreach_queue.latest.json").exists()
            and (candidate / "handoffs" / "sales_to_operations.json").exists()
        ):
            return candidate
    raise FileNotFoundError("Cannot locate OperatorOne repo root. Pass --repo-root.")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _ensure_contact_registry(path: Path, leads: List[Dict[str, Any]]) -> Dict[str, Any]:
    if path.exists():
        return _read_json(path)

    contacts = []
    for lead in leads:
        first_step = (lead.get("channel_plan", [{}]) or [{}])[0]
        contacts.append(
            {
                "lead_id": lead.get("lead_id", ""),
                "channel": first_step.get("channel", "email_nurture"),
                "target": "",
                "display_name": "",
                "notes": "Fill real recipient target before live send.",
            }
        )

    template = {
        "generated_at": _now_iso(),
        "contacts": contacts,
        "notes": [
            "One row per lead + channel route.",
            "Use email address for email_nurture; profile handle/url for linkedin.",
            "Leave target blank to keep lead in manual route.",
        ],
    }
    _write_json(path, template)
    return template


def _index_contacts(contacts_payload: Dict[str, Any]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    idx: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in contacts_payload.get("contacts", []) or []:
        lead_id = str(row.get("lead_id", "")).strip()
        channel = _normalize(str(row.get("channel", "")))
        if not lead_id or not channel:
            continue
        idx[(lead_id, channel)] = row
    return idx


def _choose_route(lead: Dict[str, Any], contact_idx: Dict[Tuple[str, str], Dict[str, Any]], allow_manual: bool) -> Dict[str, Any]:
    lead_id = str(lead.get("lead_id", ""))
    channel_plan = lead.get("channel_plan", []) or []

    for step in channel_plan:
        channel = _normalize(str(step.get("channel", "")))
        if not channel:
            continue
        contact = contact_idx.get((lead_id, channel), {})
        target = str(contact.get("target", "")).strip()
        if target:
            return {
                "route_type": "direct",
                "channel": channel,
                "target": target,
                "display_name": contact.get("display_name", ""),
                "step": int(step.get("step", 1) or 1),
            }

    if allow_manual:
        first = channel_plan[0] if channel_plan else {"channel": "manual_export", "step": 1}
        return {
            "route_type": "manual",
            "channel": "manual_export",
            "target": "",
            "display_name": "",
            "fallback_from": first.get("channel", ""),
            "step": int(first.get("step", 1) or 1),
        }

    return {
        "route_type": "missing",
        "channel": "",
        "target": "",
        "display_name": "",
        "step": 0,
    }


PRESERVE_STATUSES = {
    "dispatched_manual",
    "dispatched_prepared",
    "replied_positive",
    "replied_later",
    "replied_objection",
    "replied_other",
    "customer_converted",
    "closed_no_interest",
    "opted_out",
}


def _status_after_resolution(lead_status: str, route_type: str) -> str:
    if lead_status in PRESERVE_STATUSES:
        return lead_status
    if lead_status == "needs_review":
        return "needs_review"

    if route_type == "direct":
        return "ready_to_send"
    if route_type == "manual":
        return "ready_manual"
    return "awaiting_contact"


def _write_markdown(path: Path, payload: Dict[str, Any]) -> None:
    summary = payload.get("summary", {})
    leads = payload.get("leads", [])

    lines = [
        "# Outreach Contact Resolution (Stage2 latest)",
        "",
        f"Generated at: {payload.get('generated_at', '')}",
        "",
        "## Summary",
        f"- Leads total: {summary.get('leads_total', 0)}",
        f"- Ready to send: {summary.get('ready_to_send', 0)}",
        f"- Ready manual: {summary.get('ready_manual', 0)}",
        f"- Awaiting contact: {summary.get('awaiting_contact', 0)}",
        f"- Needs review: {summary.get('needs_review', 0)}",
        f"- Preserved terminal: {summary.get('preserved_terminal', 0)}",
        f"- Dispatch eligible: {summary.get('dispatch_eligible', 0)}",
        "",
        "## Lead routing",
        "",
        "| Lead ID | Band | Fit | Current status | Route type | Channel | Target |",
        "|---|---|---|---|---|---|---|",
    ]

    for lead in leads:
        route = (lead.get("contact_resolution", {}) or {}).get("primary_route", {})
        lines.append(
            f"| {lead.get('lead_id', '')} | {lead.get('priority_band', '')} | {lead.get('fit_status', '')} | {lead.get('status', '')} | {route.get('route_type', '')} | {route.get('channel', '')} | {route.get('target', '')} |"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Resolve Stage2 outreach contacts")
    p.add_argument("--repo-root", type=str, default="", help="OperatorOne repo root")
    p.add_argument(
        "--queue-file",
        type=str,
        default="",
        help="Input outreach queue JSON (default: research/outreach/outreach_queue.latest.json)",
    )
    p.add_argument(
        "--registry-file",
        type=str,
        default="",
        help="Contact registry JSON path (default: research/outreach/contact_registry.latest.json)",
    )
    p.add_argument("--allow-manual-route", action="store_true", help="Allow manual export route when no direct target is found")
    p.add_argument("--no-allow-manual-route", dest="allow_manual_route", action="store_false")
    p.set_defaults(allow_manual_route=True)
    p.add_argument(
        "--out-dir",
        type=str,
        default="",
        help="Output directory (default: research/outreach)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else _find_repo_root(Path.cwd())
    out_dir = Path(args.out_dir).resolve() if args.out_dir else repo_root / "workspaces" / "op1_sales" / "research" / "outreach"
    out_dir.mkdir(parents=True, exist_ok=True)

    queue_file = Path(args.queue_file).resolve() if args.queue_file else out_dir / "outreach_queue.latest.json"
    registry_file = Path(args.registry_file).resolve() if args.registry_file else out_dir / "contact_registry.latest.json"

    queue_payload = _read_json(queue_file)
    leads = queue_payload.get("leads", []) or []

    registry_payload = _ensure_contact_registry(registry_file, leads)
    contact_idx = _index_contacts(registry_payload)

    counts = {
        "leads_total": 0,
        "ready_to_send": 0,
        "ready_manual": 0,
        "awaiting_contact": 0,
        "needs_review": 0,
        "preserved_terminal": 0,
        "dispatch_eligible": 0,
    }

    resolved_leads = []
    for lead in leads:
        route = _choose_route(lead, contact_idx, args.allow_manual_route)
        status = _status_after_resolution(str(lead.get("status", "")), route.get("route_type", "missing"))

        lead_copy = dict(lead)
        lead_copy["status"] = status
        lead_copy["dispatch_eligible"] = status in {"ready_to_send", "ready_manual"}
        lead_copy["contact_resolution"] = {
            "resolved_at": _now_iso(),
            "primary_route": route,
        }

        if status == "ready_manual":
            assumptions = lead_copy.get("assumptions", []) or []
            if "未匹配直接联系人，当前走 manual_export 路由。" not in assumptions:
                assumptions.append("未匹配直接联系人，当前走 manual_export 路由。")
            lead_copy["assumptions"] = assumptions

        counts["leads_total"] += 1
        if status in PRESERVE_STATUSES:
            counts["preserved_terminal"] += 1
        elif status in counts:
            counts[status] += 1
        if lead_copy["dispatch_eligible"]:
            counts["dispatch_eligible"] += 1

        resolved_leads.append(lead_copy)

    resolved_payload = {
        **queue_payload,
        "generated_at": _now_iso(),
        "resolver": "workspaces/op1_sales/scripts/resolve_outreach_contacts_stage2.py",
        "summary": {
            **(queue_payload.get("summary", {}) or {}),
            **counts,
            "contact_registry": str(registry_file.relative_to(repo_root)) if registry_file.is_absolute() and str(registry_file).startswith(str(repo_root)) else str(registry_file),
        },
        "leads": resolved_leads,
    }

    resolved_json = out_dir / "outreach_queue.resolved.latest.json"
    resolved_md = out_dir / "outreach_contact_resolution.latest.md"

    _write_json(resolved_json, resolved_payload)
    _write_markdown(resolved_md, resolved_payload)

    print(f"Wrote: {resolved_json}")
    print(f"Wrote: {resolved_md}")
    print(f"Ensured: {registry_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
