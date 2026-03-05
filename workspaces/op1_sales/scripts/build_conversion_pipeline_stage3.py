#!/usr/bin/env python3
"""Build Stage3 conversion pipeline from Stage2 outreach + conversion events."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from conversion_stage3_common import (  # noqa: E402
    STAGE_RANK,
    TERMINAL_STAGES,
    can_advance,
    clamp,
    find_repo_root,
    normalize,
    now_iso,
    now_utc,
    parse_iso,
    read_json,
    read_jsonl,
    stage_rank,
    write_json,
)


STATUS_TO_STAGE = {
    "ready_to_send": "qualified_interest",
    "ready_manual": "qualified_interest",
    "awaiting_contact": "qualified_interest",
    "queued": "qualified_interest",
    "dispatched_manual": "qualified_interest",
    "dispatched_prepared": "qualified_interest",
    "replied_positive": "discovery_scheduled",
    "replied_later": "qualified_interest",
    "replied_objection": "qualified_interest",
    "customer_converted": "paid_started",
    "closed_no_interest": "closed_lost",
    "opted_out": "closed_lost",
    "needs_review": "qualified_interest",
}


STAGE_EVENT_TO_STAGE = {
    "discovery_scheduled": "discovery_scheduled",
    "discovery_completed": "discovery_completed",
    "pilot_offered": "pilot_offered",
    "pilot_started": "pilot_active",
    "pilot_value_confirmed": "pilot_value_confirmed",
    "terms_sent": "commercial_terms_sent",
    "commitment_received": "commitment_received",
    "paid_started": "paid_started",
    "closed_lost": "closed_lost",
}


def _read_stage2_queue(outreach_dir: Path) -> Dict[str, Any]:
    resolved = outreach_dir / "outreach_queue.resolved.latest.json"
    latest = outreach_dir / "outreach_queue.latest.json"
    if resolved.exists():
        return read_json(resolved)
    return read_json(latest)


def _initial_stage(lead: Dict[str, Any]) -> str:
    status = str(lead.get("status", "")).strip()
    return STATUS_TO_STAGE.get(status, "qualified_interest")


def _set_stage(state: Dict[str, Any], stage: str, ts: str, source: str, detail: str = "") -> None:
    current = str(state.get("current_stage", "qualified_interest"))

    if current == "paid_started" and stage == "closed_lost":
        return

    if stage == current:
        return

    if stage != "closed_lost" and not can_advance(current, stage):
        return

    state["current_stage"] = stage
    state["stage_entered_at"] = ts
    state.setdefault("stage_history", []).append(
        {
            "stage": stage,
            "entered_at": ts,
            "source": source,
            "detail": detail,
        }
    )


def _add_objection(state: Dict[str, Any], reason: str, ts: str, source: str) -> None:
    reason = reason or "unknown_objection"
    open_items = state.setdefault("objections_open", [])
    if any(str(x.get("reason", "")) == reason for x in open_items):
        return
    open_items.append({"reason": reason, "logged_at": ts, "source": source})


def _resolve_objection(state: Dict[str, Any], reason: str, ts: str, source: str) -> None:
    reason = reason or "unknown_objection"
    open_items = state.setdefault("objections_open", [])
    kept = []
    moved = False
    for item in open_items:
        if str(item.get("reason", "")) == reason and not moved:
            moved = True
            state.setdefault("objections_resolved", []).append(
                {
                    "reason": reason,
                    "resolved_at": ts,
                    "source": source,
                }
            )
        else:
            kept.append(item)
    state["objections_open"] = kept


def _append_evidence(state: Dict[str, Any], ts: str, text: str, source: str) -> None:
    text = " ".join((text or "").split())
    if not text:
        return
    evidence = state.setdefault("value_evidence", [])
    snippet = text[:180]
    if any(str(x.get("snippet", "")) == snippet for x in evidence):
        return
    evidence.append({"ts": ts, "source": source, "snippet": snippet})


def _apply_stage2_event(state: Dict[str, Any], ev: Dict[str, Any]) -> None:
    et = str(ev.get("event_type", "")).strip()
    ts = str(ev.get("ts", "")).strip() or now_iso()
    detail = str(ev.get("detail", "")).strip()

    if et == "reply_positive":
        _set_stage(state, "discovery_scheduled", ts, "stage2_event", detail)
        _append_evidence(state, ts, detail, "stage2_event")
    elif et == "reply_converted":
        _set_stage(state, "paid_started", ts, "stage2_event", detail)
        _append_evidence(state, ts, detail, "stage2_event")
    elif et == "reply_rejection":
        state["lost_reason"] = detail or "no_interest"
        _set_stage(state, "closed_lost", ts, "stage2_event", detail)
    elif et == "reply_unsubscribe":
        state["lost_reason"] = "unsubscribe"
        _set_stage(state, "closed_lost", ts, "stage2_event", "unsubscribe")
    elif et == "reply_not_now":
        state["timing_hold"] = True
        _append_evidence(state, ts, detail or "timing_hold", "stage2_event")
    elif et == "reply_objection":
        _add_objection(state, detail or "unknown_objection", ts, "stage2_event")
        _append_evidence(state, ts, detail, "stage2_event")


def _apply_conversion_event(state: Dict[str, Any], ev: Dict[str, Any]) -> None:
    et = str(ev.get("event_type", "")).strip()
    ts = str(ev.get("ts", "")).strip() or now_iso()
    detail = str(ev.get("detail", "")).strip()

    if et in STAGE_EVENT_TO_STAGE:
        stage = STAGE_EVENT_TO_STAGE[et]
        if stage == "closed_lost" and detail:
            state["lost_reason"] = detail
        _set_stage(state, stage, ts, "conversion_event", detail)
    elif et == "conversion_stage_changed":
        stage = str(ev.get("stage", "")).strip() or "qualified_interest"
        if stage in STAGE_RANK:
            _set_stage(state, stage, ts, "conversion_event", detail)
            if detail == "timing_hold":
                state["timing_hold"] = True
    elif et == "objection_logged":
        _add_objection(state, detail or "unknown_objection", ts, "conversion_event")
    elif et == "objection_resolved":
        _resolve_objection(state, detail or "unknown_objection", ts, "conversion_event")

    _append_evidence(state, ts, str(ev.get("text_excerpt", "")), "conversion_event")


def _champion_confidence(state: Dict[str, Any]) -> float:
    stage = str(state.get("current_stage", "qualified_interest"))
    score = 0.35

    route_type = str(((state.get("contact_resolution", {}) or {}).get("primary_route", {}) or {}).get("route_type", ""))
    if route_type == "direct":
        score += 0.15
    elif route_type == "manual":
        score += 0.05

    band = str(state.get("priority_band", ""))
    if band == "A1":
        score += 0.10
    elif band == "A2":
        score += 0.06

    if stage_rank(stage) >= stage_rank("discovery_scheduled"):
        score += 0.12
    if stage_rank(stage) >= stage_rank("pilot_active"):
        score += 0.15
    if stage == "commitment_received":
        score += 0.20
    if stage == "paid_started":
        score = 0.99
    if stage == "closed_lost":
        score = 0.02

    if state.get("timing_hold"):
        score -= 0.12

    score -= min(0.20, 0.06 * len(state.get("objections_open", []) or []))
    return round(clamp(score, 0.0, 1.0), 3)


def _readiness_score(state: Dict[str, Any]) -> float:
    stage = str(state.get("current_stage", "qualified_interest"))
    if stage == "closed_lost":
        return 0.0
    if stage == "paid_started":
        return 100.0

    score = 0.0

    band = str(state.get("priority_band", ""))
    score += {"A1": 20, "A2": 14, "B1": 9}.get(band, 6)

    fit_status = str(state.get("fit_status", ""))
    score += 18 if fit_status == "qualified" else 6

    route_type = str(((state.get("contact_resolution", {}) or {}).get("primary_route", {}) or {}).get("route_type", ""))
    score += {"direct": 12, "manual": 5, "missing": 1}.get(route_type, 2)

    score += {
        "qualified_interest": 8,
        "discovery_scheduled": 16,
        "discovery_completed": 24,
        "pilot_offered": 34,
        "pilot_active": 44,
        "pilot_value_confirmed": 56,
        "commercial_terms_sent": 66,
        "commitment_received": 80,
    }.get(stage, 0)

    score -= min(22, 8 * len(state.get("objections_open", []) or []))
    if state.get("timing_hold"):
        score -= 12
    if str(state.get("status", "")) == "needs_review":
        score -= 15

    return round(clamp(score, 0, 100), 2)


def _next_action(state: Dict[str, Any]) -> Dict[str, Any]:
    stage = str(state.get("current_stage", "qualified_interest"))
    now = now_utc()

    if stage == "closed_lost":
        return {
            "action": "记录丢单复盘并更新异议打法",
            "due_at": (now + timedelta(hours=72)).replace(microsecond=0).isoformat(),
            "priority": "low",
        }

    if stage == "paid_started":
        return {
            "action": "转运营交接并确认首月扩展目标",
            "due_at": (now + timedelta(hours=72)).replace(microsecond=0).isoformat(),
            "priority": "medium",
        }

    if str(state.get("status", "")) == "needs_review":
        return {
            "action": "先完成人工复核（角色/场景/付费可能性）后再推进转化",
            "due_at": (now + timedelta(hours=24)).replace(microsecond=0).isoformat(),
            "priority": "high",
        }

    if state.get("timing_hold"):
        return {
            "action": "按客户时机窗口回访并重提14天pilot（保留低摩擦入口）",
            "due_at": (now + timedelta(hours=24 * 7)).replace(microsecond=0).isoformat(),
            "priority": "medium",
        }

    if state.get("objections_open"):
        top_reason = str(state["objections_open"][0].get("reason", ""))
        return {
            "action": f"优先处理异议：{top_reason}，处理后发起明确成交请求",
            "due_at": (now + timedelta(hours=24)).replace(microsecond=0).isoformat(),
            "priority": "high",
        }

    mapping = {
        "qualified_interest": ("预约15分钟discovery并确认是否进入14天pilot", 24, "high"),
        "discovery_scheduled": ("完成discovery并确定pilot成功标准", 24, "high"),
        "discovery_completed": ("发送pilot方案并锁定启动日期", 24, "high"),
        "pilot_offered": ("推进pilot开始并确认owner与样本", 48, "high"),
        "pilot_active": ("在72小时内拿到首个价值点（TTFV）", 48, "high"),
        "pilot_value_confirmed": ("发送商业条款并请求付费承诺", 24, "high"),
        "commercial_terms_sent": ("跟进条款并锁定签署/付款日期", 48, "high"),
        "commitment_received": ("推进付款启动并完成paid start", 24, "high"),
    }
    action, hours, priority = mapping.get(stage, ("推进到下一转化阶段", 24, "medium"))
    return {
        "action": action,
        "due_at": (now + timedelta(hours=hours)).replace(microsecond=0).isoformat(),
        "priority": priority,
    }


def _write_md(path: Path, payload: Dict[str, Any]) -> None:
    summary = payload.get("summary", {})
    leads = payload.get("leads", [])

    lines = [
        "# Conversion Pipeline (Stage3 latest)",
        "",
        f"Generated at: {payload.get('generated_at', '')}",
        "",
        "## Summary",
        f"- Leads total: {summary.get('leads_total', 0)}",
        f"- Active leads: {summary.get('active_leads', 0)}",
        f"- Paid started: {summary.get('paid_started', 0)}",
        f"- Closed lost: {summary.get('closed_lost', 0)}",
        "",
        "## Stage counts",
    ]
    for stage, count in (summary.get("stage_counts", {}) or {}).items():
        lines.append(f"- {stage}: {count}")

    lines.extend(
        [
            "",
            "## Lead table",
            "",
            "| Lead ID | Stage | Readiness | Confidence | Next action | Due |",
            "|---|---|---:|---:|---|---|",
        ]
    )

    for lead in leads:
        lines.append(
            f"| {lead.get('lead_id','')} | {lead.get('current_stage','')} | {lead.get('conversion_readiness_score',0)} | {lead.get('champion_confidence',0)} | {lead.get('next_best_action','')} | {lead.get('next_action_due_at','')} |"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Stage3 conversion pipeline")
    p.add_argument("--repo-root", type=str, default="", help="OperatorOne repo root")
    p.add_argument("--out-dir", type=str, default="", help="Output dir (default: research/conversion)")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    outreach_dir = repo_root / "workspaces" / "op1_sales" / "research" / "outreach"
    out_dir = Path(args.out_dir).resolve() if args.out_dir else repo_root / "workspaces" / "op1_sales" / "research" / "conversion"
    out_dir.mkdir(parents=True, exist_ok=True)

    queue_payload = _read_stage2_queue(outreach_dir)
    leads = queue_payload.get("leads", []) or []

    stage2_events = read_jsonl(outreach_dir / "outreach_events.latest.jsonl")
    conversion_events = read_jsonl(out_dir / "conversion_events.latest.jsonl")

    lead_state: Dict[str, Dict[str, Any]] = {}

    queue_ts = str(queue_payload.get("generated_at", "")) or now_iso()

    for lead in leads:
        lead_id = str(lead.get("lead_id", "")).strip()
        if not lead_id:
            continue

        initial_stage = _initial_stage(lead)
        state = dict(lead)
        state["current_stage"] = initial_stage
        state["stage_entered_at"] = queue_ts
        state["stage_history"] = [
            {
                "stage": initial_stage,
                "entered_at": queue_ts,
                "source": "stage2_queue",
                "detail": str(lead.get("status", "")),
            }
        ]
        state["objections_open"] = []
        state["objections_resolved"] = []
        state["value_evidence"] = []
        state["timing_hold"] = False
        state["lost_reason"] = ""

        _append_evidence(state, queue_ts, str(lead.get("pain_signal", "")), "stage2_queue")
        _append_evidence(state, queue_ts, str(lead.get("evidence_url", "")), "stage2_queue")

        lead_state[lead_id] = state

    # Stage2 event overlays.
    for ev in sorted(stage2_events, key=lambda x: str(x.get("ts", ""))):
        lead_id = str(ev.get("lead_id", "")).strip()
        if not lead_id or lead_id not in lead_state:
            continue
        _apply_stage2_event(lead_state[lead_id], ev)

    # Stage3 conversion event overlays.
    for ev in sorted(conversion_events, key=lambda x: str(x.get("ts", ""))):
        lead_id = str(ev.get("lead_id", "")).strip()
        if not lead_id or lead_id not in lead_state:
            continue
        _apply_conversion_event(lead_state[lead_id], ev)

    # Finalize fields.
    final_leads: List[Dict[str, Any]] = []
    for lead_id, state in lead_state.items():
        # Deduplicate history while preserving order.
        history = []
        seen = set()
        for h in state.get("stage_history", []):
            key = (str(h.get("stage", "")), str(h.get("entered_at", "")), str(h.get("source", "")), str(h.get("detail", "")))
            if key in seen:
                continue
            seen.add(key)
            history.append(h)
        state["stage_history"] = history

        state["champion_confidence"] = _champion_confidence(state)
        state["conversion_readiness_score"] = _readiness_score(state)

        next_step = _next_action(state)
        state["next_best_action"] = next_step["action"]
        state["next_action_due_at"] = next_step["due_at"]
        state["next_action_priority"] = next_step["priority"]

        # Keep objections sorted by logged_at for deterministic output.
        state["objections_open"] = sorted(
            state.get("objections_open", []),
            key=lambda x: str(x.get("logged_at", "")),
        )
        state["objections_resolved"] = sorted(
            state.get("objections_resolved", []),
            key=lambda x: str(x.get("resolved_at", "")),
        )
        state["value_evidence"] = sorted(
            state.get("value_evidence", []),
            key=lambda x: str(x.get("ts", "")),
        )

        final_leads.append(state)

    final_leads.sort(
        key=lambda x: (
            stage_rank(str(x.get("current_stage", "qualified_interest"))),
            float(x.get("conversion_readiness_score", 0) or 0),
        ),
        reverse=True,
    )

    stage_counts = Counter(str(x.get("current_stage", "qualified_interest")) for x in final_leads)

    summary = {
        "leads_total": len(final_leads),
        "active_leads": sum(1 for x in final_leads if str(x.get("current_stage", "")) not in TERMINAL_STAGES),
        "paid_started": stage_counts.get("paid_started", 0),
        "closed_lost": stage_counts.get("closed_lost", 0),
        "stage_counts": {stage: stage_counts.get(stage, 0) for stage in STAGE_RANK.keys()},
        "timing_hold": sum(1 for x in final_leads if x.get("timing_hold")),
        "open_objections": sum(len(x.get("objections_open", [])) for x in final_leads),
    }

    payload = {
        "generated_at": now_iso(),
        "builder": "workspaces/op1_sales/scripts/build_conversion_pipeline_stage3.py",
        "inputs": {
            "stage2_queue": "workspaces/op1_sales/research/outreach/outreach_queue.resolved.latest.json",
            "stage2_events": "workspaces/op1_sales/research/outreach/outreach_events.latest.jsonl",
            "conversion_events": "workspaces/op1_sales/research/conversion/conversion_events.latest.jsonl",
        },
        "summary": summary,
        "leads": final_leads,
    }

    out_json = out_dir / "conversion_pipeline.latest.json"
    out_md = out_dir / "conversion_pipeline.latest.md"
    write_json(out_json, payload)
    _write_md(out_md, payload)

    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
