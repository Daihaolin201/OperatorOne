#!/usr/bin/env python3
"""Render Stage3 conversion scoreboard, objection playbook, and ops rollup."""

from __future__ import annotations

import argparse
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from conversion_stage3_common import (  # noqa: E402
    STAGE_RANK,
    find_repo_root,
    now_iso,
    parse_iso,
    parse_monthly_price,
    read_json,
    read_jsonl,
    stage_rank,
    write_json,
)


OBJECTION_PLAYS = {
    "budget": "以14天小范围试点验证ROI，先证明回收价值再扩投入。",
    "integration": "先并行运行，不改现有栈；价值确认后再决定是否集成。",
    "security": "先最小数据范围试点，补齐权限边界与审计记录。",
    "capacity": "用concierge执行前置步骤，降低客户团队负担。",
    "timing": "锁定回访日期并保持低摩擦入口，避免长时间沉没。",
    "trust_or_value": "先用真实样本跑出可见结果，再推进商业承诺。",
    "unknown_objection": "先澄清真实阻碍，再给低风险可执行路径。",
    "unsubscribe": "立即停发并更新抑制列表，避免进一步损害声誉。",
    "no_interest": "记录原因并用于后续筛选规则优化。",
}


def _price_lookup(repo_root: Path) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}

    build_dir = repo_root / "workspaces" / "op1_product" / "research" / "build_deploy_v1"
    for p in sorted(build_dir.glob("project_spec*.json")):
        obj = read_json(p)
        pid = str(obj.get("project_id", "")).lower()
        adapter = str((obj.get("adapter", {}) or {}).get("name", "")).lower()

        opp = ""
        if "invoice" in pid or "invoice" in adapter:
            opp = "opp_001"
        elif "chargeback" in pid or "chargeback" in adapter:
            opp = "opp_002"
        elif "reporting" in pid or "reporting" in adapter:
            opp = "opp_003"

        if not opp:
            src = str((obj.get("source", {}) or {}).get("opportunity_id", "")).strip()
            if src:
                opp = src

        if not opp:
            continue

        pa = str((obj.get("pricing", {}) or {}).get("plan_a", "")).strip()
        pb = str((obj.get("pricing", {}) or {}).get("plan_b", "")).strip()
        out[opp] = {
            "plan_a": parse_monthly_price(pa),
            "plan_b": parse_monthly_price(pb),
            "plan_a_raw": pa,
            "plan_b_raw": pb,
        }

    blueprint = read_json(repo_root / "workspaces" / "op1_product" / "research" / "stage3_mvp_scope" / "project_blueprint.json")
    ph = blueprint.get("pricing_hypothesis", {}) or {}
    if ph:
        out.setdefault(
            "opp_001",
            {
                "plan_a": parse_monthly_price(str(ph.get("plan_a", ""))),
                "plan_b": parse_monthly_price(str(ph.get("plan_b", ""))),
                "plan_a_raw": str(ph.get("plan_a", "")),
                "plan_b_raw": str(ph.get("plan_b", "")),
            },
        )

    return out


def _rollup_stage2_ops(events: List[Dict[str, Any]]) -> Dict[str, Any]:
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

    objection_counts = Counter(
        str(e.get("detail", "")).strip()
        for e in events
        if str(e.get("event_type", "")) == "reply_objection"
    )

    return {
        "prospects_contacted": len(contacted),
        "replies": len(replied),
        "calls_booked": len(booked),
        "stage2_converted": len(converted),
        "stage2_objection_counts": objection_counts,
    }


def _paid_mrr_proxy(
    paid_leads: List[Dict[str, Any]],
    conversion_events: List[Dict[str, Any]],
    price_lookup: Dict[str, Dict[str, float]],
) -> Tuple[float, Dict[str, float]]:
    by_lead_paid_detail: Dict[str, List[str]] = defaultdict(list)
    for e in conversion_events:
        if str(e.get("event_type", "")) != "paid_started":
            continue
        lead_id = str(e.get("lead_id", "")).strip()
        if not lead_id:
            continue
        by_lead_paid_detail[lead_id].append(str(e.get("detail", "")).lower())

    lead_mrr: Dict[str, float] = {}
    total = 0.0

    for lead in paid_leads:
        lead_id = str(lead.get("lead_id", "")).strip()
        opp = str(lead.get("opportunity_id", "")).strip()
        pricing = price_lookup.get(opp, {})

        plan_a = float(pricing.get("plan_a", 0.0) or 0.0)
        plan_b = float(pricing.get("plan_b", 0.0) or 0.0)

        details = " ".join(by_lead_paid_detail.get(lead_id, []))
        choose_b = any(k in details for k in ["plan_b", "growth", "team", "129", "149", "79"])

        mrr = 0.0
        if choose_b and plan_b > 0:
            mrr = plan_b
        elif plan_a > 0:
            mrr = plan_a
        elif plan_b > 0:
            mrr = plan_b
        else:
            # Conservative fallback proxy for unknown plans
            mrr = 49.0

        lead_mrr[lead_id] = round(mrr, 2)
        total += mrr

    return round(total, 2), lead_mrr


def _objection_stats(
    conversion_events: List[Dict[str, Any]],
    pipeline_leads: List[Dict[str, Any]],
    stage2_objection_counts: Counter,
) -> Dict[str, Any]:
    logged = [e for e in conversion_events if str(e.get("event_type", "")) == "objection_logged"]
    resolved = [e for e in conversion_events if str(e.get("event_type", "")) == "objection_resolved"]

    logged_counter = Counter(str(e.get("detail", "unknown_objection") or "unknown_objection") for e in logged)
    resolved_counter = Counter(str(e.get("detail", "unknown_objection") or "unknown_objection") for e in resolved)

    # Blend with stage2 objections as additional signal.
    for reason, count in stage2_objection_counts.items():
        if reason:
            logged_counter[reason] += count

    by_reason_total = dict(logged_counter)
    by_reason_resolved = dict(resolved_counter)

    lead_stage = {str(l.get("lead_id", "")): str(l.get("current_stage", "")) for l in pipeline_leads}
    reason_to_leads: Dict[str, set] = defaultdict(set)

    for e in logged:
        reason = str(e.get("detail", "unknown_objection") or "unknown_objection")
        lead_id = str(e.get("lead_id", "")).strip()
        if lead_id:
            reason_to_leads[reason].add(lead_id)

    won_after_objection: Dict[str, int] = {}
    for reason, leads in reason_to_leads.items():
        won_after_objection[reason] = sum(1 for lid in leads if lead_stage.get(lid) == "paid_started")

    total_logged = sum(by_reason_total.values())
    total_resolved = sum(by_reason_resolved.values())
    resolution_rate = (total_resolved / total_logged) if total_logged > 0 else 0.0

    # Open objections in current pipeline.
    open_counter = Counter()
    for lead in pipeline_leads:
        for item in lead.get("objections_open", []) or []:
            reason = str(item.get("reason", "unknown_objection") or "unknown_objection")
            open_counter[reason] += 1

    return {
        "total_logged": total_logged,
        "total_resolved": total_resolved,
        "resolution_rate": round(resolution_rate, 4),
        "by_reason_total": by_reason_total,
        "by_reason_resolved": by_reason_resolved,
        "open_counter": dict(open_counter),
        "won_after_objection": won_after_objection,
    }


def _closed_lost_mix(pipeline_leads: List[Dict[str, Any]], conversion_events: List[Dict[str, Any]]) -> Dict[str, int]:
    counter = Counter()
    for lead in pipeline_leads:
        if str(lead.get("current_stage", "")) == "closed_lost":
            reason = str(lead.get("lost_reason", "") or "unknown").strip() or "unknown"
            counter[reason] += 1

    if not counter:
        for ev in conversion_events:
            if str(ev.get("event_type", "")) == "closed_lost":
                reason = str(ev.get("detail", "") or "unknown").strip() or "unknown"
                counter[reason] += 1

    return dict(counter)


def _median_hours(pipeline_leads: List[Dict[str, Any]]) -> float:
    values = []
    for lead in pipeline_leads:
        if str(lead.get("current_stage", "")) != "paid_started":
            continue

        q_ts = ""
        p_ts = ""
        for h in lead.get("stage_history", []) or []:
            st = str(h.get("stage", ""))
            ts = str(h.get("entered_at", ""))
            if st == "qualified_interest" and not q_ts:
                q_ts = ts
            if st == "paid_started" and ts:
                p_ts = ts

        q_dt = parse_iso(q_ts)
        p_dt = parse_iso(p_ts)
        if q_dt and p_dt and p_dt >= q_dt:
            values.append((p_dt - q_dt).total_seconds() / 3600.0)

    if not values:
        return 0.0
    return round(statistics.median(values), 2)


def _write_scoreboard_md(path: Path, payload: Dict[str, Any]) -> None:
    summary = payload.get("summary", {})
    top_leads = payload.get("top_conversion_leads", [])

    lines = [
        "# Conversion Scoreboard (Stage3 latest)",
        "",
        f"Generated at: {payload.get('generated_at', '')}",
        "",
        "## Core metrics",
        f"- qualified_interest_to_pilot_rate: {summary.get('qualified_interest_to_pilot_rate', 0)}",
        f"- pilot_to_commitment_rate: {summary.get('pilot_to_commitment_rate', 0)}",
        f"- commitment_to_paid_start_rate: {summary.get('commitment_to_paid_start_rate', 0)}",
        f"- median_time_to_first_value_hours: {summary.get('median_time_to_first_value_hours', 0)}",
        f"- median_time_to_paid_start_hours: {summary.get('median_time_to_paid_start_hours', 0)}",
        "",
        "## Revenue/quality",
        f"- new_customers_converted: {summary.get('new_customers_converted', 0)}",
        f"- new_business_mrr_proxy: {summary.get('new_business_mrr_proxy', 0)}",
        f"- asp_proxy: {summary.get('asp_proxy', 0)}",
        f"- objection_resolution_rate: {summary.get('objection_resolution_rate', 0)}",
        "",
        "## Guardrails",
        f"- opt_out_rate: {summary.get('opt_out_rate', 0)}",
        f"- onboarding_stall_rate: {summary.get('onboarding_stall_rate', 0)}",
        f"- no_response_after_terms_rate: {summary.get('no_response_after_terms_rate', 0)}",
        "",
        "## Stage counts",
    ]

    for stage, count in (summary.get("stage_counts", {}) or {}).items():
        lines.append(f"- {stage}: {count}")

    lines.extend(
        [
            "",
            "## Top conversion leads",
            "",
            "| Lead ID | Stage | Readiness | Next action | Due |",
            "|---|---|---:|---|---|",
        ]
    )

    for row in top_leads:
        lines.append(
            f"| {row.get('lead_id','')} | {row.get('current_stage','')} | {row.get('conversion_readiness_score',0)} | {row.get('next_best_action','')} | {row.get('next_action_due_at','')} |"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _write_playbook_md(path: Path, payload: Dict[str, Any]) -> None:
    stats = payload.get("objection_stats", {})
    total = stats.get("by_reason_total", {}) or {}
    resolved = stats.get("by_reason_resolved", {}) or {}
    open_counter = stats.get("open_counter", {}) or {}
    won_after = stats.get("won_after_objection", {}) or {}

    ranked = sorted(total.items(), key=lambda x: x[1], reverse=True)

    lines = [
        "# Objection Playbook (Stage3 latest)",
        "",
        f"Generated at: {payload.get('generated_at', '')}",
        "",
        "## Ranked objections",
        "",
        "| Reason | Total | Resolved | Open | Won after objection | Suggested response |",
        "|---|---:|---:|---:|---:|---|",
    ]

    if not ranked:
        lines.append("| none | 0 | 0 | 0 | 0 | Keep logging objections from live conversations. |")

    for reason, count in ranked:
        lines.append(
            f"| {reason} | {count} | {resolved.get(reason, 0)} | {open_counter.get(reason, 0)} | {won_after.get(reason, 0)} | {OBJECTION_PLAYS.get(reason, OBJECTION_PLAYS['unknown_objection'])} |"
        )

    lines.extend(
        [
            "",
            "## Operating rule",
            "- 先确认异议真实原因，再给低风险下一步；每次回应必须绑定明确成交请求和截止时间。",
        ]
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Render Stage3 conversion scoreboard")
    p.add_argument("--repo-root", type=str, default="", help="OperatorOne repo root")
    p.add_argument("--out-dir", type=str, default="", help="Output dir (default: research/conversion)")
    p.add_argument("--mode", type=str, default="commit", choices=["simulate", "commit"], help="commit updates handoff")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    out_dir = Path(args.out_dir).resolve() if args.out_dir else repo_root / "workspaces" / "op1_sales" / "research" / "conversion"
    out_dir.mkdir(parents=True, exist_ok=True)

    pipeline = read_json(out_dir / "conversion_pipeline.latest.json")
    onboarding = read_json(out_dir / "pilot_onboarding.latest.json")
    conversion_events = read_jsonl(out_dir / "conversion_events.latest.jsonl")
    stage2_events = read_jsonl(repo_root / "workspaces" / "op1_sales" / "research" / "outreach" / "outreach_events.latest.jsonl")

    leads = pipeline.get("leads", []) or []
    stage_counts = Counter(str(x.get("current_stage", "qualified_interest")) for x in leads)

    qualified_base = sum(1 for x in leads if str(x.get("current_stage", "")) != "closed_lost")
    pilot_pool = sum(
        1
        for x in leads
        if stage_rank(str(x.get("current_stage", ""))) >= stage_rank("pilot_offered")
        and str(x.get("current_stage", "")) != "closed_lost"
    )
    commitment_pool = sum(
        1
        for x in leads
        if str(x.get("current_stage", "")) in {"commitment_received", "paid_started"}
    )
    paid_leads = [x for x in leads if str(x.get("current_stage", "")) == "paid_started"]

    q_to_pilot = (pilot_pool / qualified_base) if qualified_base else 0.0
    pilot_to_commit = (commitment_pool / pilot_pool) if pilot_pool else 0.0
    commit_to_paid = (len(paid_leads) / commitment_pool) if commitment_pool else 0.0

    ttfv = float((onboarding.get("summary", {}) or {}).get("median_ttfv_hours", 0.0) or 0.0)
    paid_time = _median_hours(leads)

    price_lookup = _price_lookup(repo_root)
    mrr_proxy, lead_mrr = _paid_mrr_proxy(paid_leads, conversion_events, price_lookup)
    asp_proxy = round((mrr_proxy / len(paid_leads)), 2) if paid_leads else 0.0

    stage2_rollup = _rollup_stage2_ops(stage2_events)

    objection_stats = _objection_stats(
        conversion_events,
        leads,
        stage2_rollup.get("stage2_objection_counts", Counter()),
    )

    closed_lost_mix = _closed_lost_mix(leads, conversion_events)

    # Guardrails
    opted_out = sum(1 for e in stage2_events if str(e.get("event_type", "")) == "reply_unsubscribe")
    contacted = stage2_rollup.get("prospects_contacted", 0)
    opt_out_rate = (opted_out / contacted) if contacted else 0.0

    pilot_candidates = int((onboarding.get("summary", {}) or {}).get("pilot_candidates", 0) or 0)
    at_risk = int((onboarding.get("summary", {}) or {}).get("at_risk", 0) or 0)
    onboarding_stall_rate = (at_risk / pilot_candidates) if pilot_candidates else 0.0

    terms_sent = stage_counts.get("commercial_terms_sent", 0)
    no_response_after_terms = max(0, terms_sent - commitment_pool - len(paid_leads))
    no_response_after_terms_rate = (no_response_after_terms / terms_sent) if terms_sent else 0.0

    top_conversion_leads = sorted(
        [x for x in leads if str(x.get("current_stage", "")) not in {"closed_lost", "paid_started"}],
        key=lambda x: float(x.get("conversion_readiness_score", 0) or 0),
        reverse=True,
    )[:10]

    payload = {
        "generated_at": now_iso(),
        "builder": "workspaces/op1_sales/scripts/render_conversion_scoreboard_stage3.py",
        "inputs": {
            "conversion_pipeline": "workspaces/op1_sales/research/conversion/conversion_pipeline.latest.json",
            "pilot_onboarding": "workspaces/op1_sales/research/conversion/pilot_onboarding.latest.json",
            "conversion_events": "workspaces/op1_sales/research/conversion/conversion_events.latest.jsonl",
            "stage2_events": "workspaces/op1_sales/research/outreach/outreach_events.latest.jsonl",
        },
        "summary": {
            "qualified_interest_to_pilot_rate": round(q_to_pilot, 4),
            "pilot_to_commitment_rate": round(pilot_to_commit, 4),
            "commitment_to_paid_start_rate": round(commit_to_paid, 4),
            "median_time_to_first_value_hours": ttfv,
            "median_time_to_paid_start_hours": paid_time,
            "new_customers_converted": len(paid_leads),
            "new_business_mrr_proxy": mrr_proxy,
            "asp_proxy": asp_proxy,
            "objection_resolution_rate": objection_stats.get("resolution_rate", 0.0),
            "closed_lost_reason_mix": closed_lost_mix,
            "opt_out_rate": round(opt_out_rate, 4),
            "onboarding_stall_rate": round(onboarding_stall_rate, 4),
            "no_response_after_terms_rate": round(no_response_after_terms_rate, 4),
            "stage_counts": {stage: stage_counts.get(stage, 0) for stage in STAGE_RANK.keys()},
            "lead_mrr_proxy": lead_mrr,
        },
        "objection_stats": objection_stats,
        "top_conversion_leads": [
            {
                "lead_id": x.get("lead_id", ""),
                "current_stage": x.get("current_stage", ""),
                "conversion_readiness_score": x.get("conversion_readiness_score", 0),
                "next_best_action": x.get("next_best_action", ""),
                "next_action_due_at": x.get("next_action_due_at", ""),
            }
            for x in top_conversion_leads
        ],
    }

    score_json = out_dir / "conversion_scoreboard.latest.json"
    score_md = out_dir / "conversion_scoreboard.latest.md"
    playbook_md = out_dir / "objection_playbook.latest.md"
    write_json(score_json, payload)
    _write_scoreboard_md(score_md, payload)
    _write_playbook_md(playbook_md, payload)

    if args.mode == "commit":
        handoff_path = repo_root / "handoffs" / "sales_to_operations.json"
        handoff = read_json(
            handoff_path,
            default={
                "contract_version": "1.0.0",
                "generated_at": now_iso(),
                "generated_by": "workspaces/op1_sales/skills/convert-early-customers-stage3/scripts/render_conversion_scoreboard_stage3.py",
                "prospects_contacted": 0,
                "replies": 0,
                "calls_booked": 0,
                "customers_converted": 0,
                "mrr": 0,
                "objections_summary": [],
                "handoff_notes": "",
            },
        )

        handoff["contract_version"] = "1.0.0"
        handoff["generated_at"] = now_iso()
        handoff["generated_by"] = "workspaces/op1_sales/skills/convert-early-customers-stage3/scripts/render_conversion_scoreboard_stage3.py"
        handoff["prospects_contacted"] = stage2_rollup.get("prospects_contacted", 0)
        handoff["replies"] = stage2_rollup.get("replies", 0)
        handoff["calls_booked"] = stage2_rollup.get("calls_booked", 0)
        handoff["customers_converted"] = max(
            int(handoff.get("customers_converted", 0) or 0),
            stage2_rollup.get("stage2_converted", 0),
            len(paid_leads),
        )
        handoff["mrr"] = round(mrr_proxy, 2)

        top_objections = sorted(
            (objection_stats.get("by_reason_total", {}) or {}).items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]
        handoff["objections_summary"] = [
            {"reason": reason, "count": count} for reason, count in top_objections
        ]

        note = (
            f"Stage3 conversion scoreboard updated at {now_iso()} "
            f"(paid={len(paid_leads)}, mrr_proxy={mrr_proxy}, "
            f"q_to_pilot={round(q_to_pilot,4)}, commit_to_paid={round(commit_to_paid,4)})."
        )

        base_notes = str(handoff.get("handoff_notes", "")).strip()
        base_notes = re.sub(
            r"\s*Stage3 conversion scoreboard updated at .*?commit_to_paid=[0-9.]+\)\.\s*",
            " ",
            base_notes,
            flags=re.IGNORECASE,
        )
        base_notes = re.sub(
            r"\s*[0-9.]+, q_to_pilot=[0-9.]+, commit_to_paid=[0-9.]+\)\.\s*",
            " ",
            base_notes,
            flags=re.IGNORECASE,
        ).strip()
        handoff["handoff_notes"] = (base_notes + " " + note).strip()
        write_json(handoff_path, handoff)

        print(f"Updated: {handoff_path}")

    print(f"Wrote: {score_json}")
    print(f"Wrote: {score_md}")
    print(f"Wrote: {playbook_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
