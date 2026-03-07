#!/usr/bin/env python3
"""Build Stage2 send-outreach capability artifacts for op1_sales.

This script does NOT send messages. It prepares:
- ranked outreach queue
- channel-specific copy pack
- approval-gated batch artifacts
- suppression + events files for future dispatch
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


SUBREDDIT_ROLE_HINT = {
    "smallbusiness": "SMB老板/财务负责人",
    "freelance": "自由职业者/小团队主理人",
    "ecommerce": "电商老板/运营负责人",
    "agency": "Agency owner/Account lead",
    "propertymanagement": "物业管理负责人",
    "ppc": "投放负责人/绩效负责人",
}

SEQUENCE_BY_BAND = {
    "A1": [
        {"step": 1, "day_offset": 0, "channel": "email_nurture", "touch_type": "initial"},
        {"step": 2, "day_offset": 2, "channel": "linkedin", "touch_type": "follow_up"},
        {"step": 3, "day_offset": 4, "channel": "email_nurture", "touch_type": "follow_up"},
    ],
    "A2": [
        {"step": 1, "day_offset": 0, "channel": "email_nurture", "touch_type": "initial"},
        {"step": 2, "day_offset": 3, "channel": "linkedin", "touch_type": "follow_up"},
    ],
    "B1": [
        {"step": 1, "day_offset": 0, "channel": "email_nurture", "touch_type": "initial"},
    ],
}

KEY_TERMS_BY_OPP = {
    "opp_001": ["invoice", "overdue", "receivable", "late payment", "collections"],
    "opp_002": ["chargeback", "dispute", "fraud", "shopify", "stripe"],
    "opp_003": ["agency", "reporting", "ga4", "ppc", "dashboard"],
    "opp_004": ["property", "tenant", "owner report", "rent", "appfolio"],
    "opp_005": ["expense", "receipt", "reimbursement", "bookkeeping", "accounting"],
    "opp_006": ["spreadsheet", "excel", "pdf", "data entry", "copy paste"],
}

ANGLE_BY_OPP = {
    "opp_001": {
        "A1": "先把逾期发票跟进节奏自动化，减少尴尬催款和漏跟进。",
        "A2": "先跑轻量提醒流程，验证回款率提升后再扩展。",
        "B1": "先给你一页回款流程模板，低成本试点。",
    },
    "opp_002": {
        "A1": "先把拒付证据包和截止日管理拉通，优先止损。",
        "A2": "先上争议任务清单，降低漏处理风险。",
        "B1": "先从单流程模板试点，不改现有栈。",
    },
    "opp_003": {
        "A1": "先自动化月报解释层，减少手工拼接和复述。",
        "A2": "先接核心指标看板，缩短出报时间。",
        "B1": "先上可复用模板，降低重复劳动。",
    },
    "opp_004": {
        "A1": "先打通业主报告与租客沟通记录，减少月末混乱。",
        "A2": "先做流程模板化，不替换现有系统。",
        "B1": "先从单项目试点，验证节省工时。",
    },
    "opp_005": {
        "A1": "先做重复报销拦截+凭证追缴，不动主账务流程。",
        "A2": "先把收据归集和分类自动化，减少月底关账时间。",
        "B1": "先上税季资料归档模板，降低交接混乱。",
    },
    "opp_006": {
        "A1": "先解决PDF到表格的高频录入场景，降低错误率。",
        "A2": "先上关键字段抽取+人工复核，稳步替换手工。",
        "B1": "先从一个流程改造，低风险验证。",
    },
}


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def _priority_band(rank_index: int) -> str:
    if rank_index <= 7:
        return "A1"
    if rank_index <= 14:
        return "A2"
    return "B1"


def _find_repo_root(start: Path) -> Path:
    for candidate in [start.resolve(), *start.resolve().parents]:
        if (
            (candidate / "handoffs" / "marketing_to_sales.json").exists()
            and (candidate / "workspaces" / "op1_sales" / "research" / "prospecting" / "prospect_queue.latest.json").exists()
        ):
            return candidate
    raise FileNotFoundError("Cannot locate OperatorOne repo root. Pass --repo-root.")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def _infer_role(post: Dict[str, Any], fallback_role: str) -> str:
    sub = _normalize(str(post.get("subreddit", "")))
    return SUBREDDIT_ROLE_HINT.get(sub, fallback_role or "业务负责人")


def _short(text: str, max_len: int = 80) -> str:
    t = " ".join((text or "").split())
    if len(t) <= max_len:
        return t
    return t[: max_len - 3] + "..."


def _angle(opportunity_id: str, band: str) -> str:
    return ANGLE_BY_OPP.get(opportunity_id, {}).get(
        band, "先从高频手工痛点切入，低风险试点验证。"
    )


def _email_subjects(segment_name: str, pain_signal: str, band: str) -> Dict[str, str]:
    base = _short(pain_signal, 54)
    control = f"关于{segment_name}：{base}"
    if band == "A1":
        challenger = f"{segment_name}能否一周内先降手工负担？"
    elif band == "A2":
        challenger = f"{segment_name}：先做小改造，少走弯路"
    else:
        challenger = f"{segment_name}的低成本试点建议"
    return {"control": control, "challenger": challenger}


def _email_body(role: str, segment_name: str, angle: str, evidence_url: str, band: str) -> str:
    urgency_line = (
        "你这个场景紧迫度很高，通常先做不改系统的轻量试点。"
        if band == "A1"
        else "这个场景我们建议先从最耗时环节切入。"
    )
    return (
        f"你好，看到你在{segment_name}相关讨论中的信号（{evidence_url}）。\n"
        f"我们最近在帮{role}处理类似问题。{urgency_line}\n"
        f"建议第一步：{angle}\n"
        "如果你愿意，我可以给你一份一页版执行清单（本周可落地）。"
    )


def _linkedin_dm(segment_name: str, angle: str) -> Dict[str, str]:
    initial = (
        f"看到你在{segment_name}上的讨论，"
        f"我们最近用一个轻量流程把这类手工环节压下来了。"
        f"如果你有兴趣，我发你一个可直接照搬的做法：{angle}"
    )
    follow_up = (
        "补一条：如果你愿意，我可以把‘先试点再扩展’的步骤发你，"
        "全程不要求替换你现有系统。"
    )
    return {"initial": initial, "follow_up": follow_up}


def _fit_hits(post: Dict[str, Any], opportunity_id: str) -> int:
    text = _normalize(
        " ".join(
            [
                str(post.get("title", "")),
                " ".join(post.get("queries_matched", []) or []),
            ]
        )
    )
    anchors = KEY_TERMS_BY_OPP.get(opportunity_id, [])
    return sum(1 for term in anchors if term in text)


def _build_leads(
    segment: Dict[str, Any],
    top_n: int,
    preferred_channels: List[str],
) -> List[Dict[str, Any]]:
    social = segment.get("social_signals", {}) or {}
    raw_posts = social.get("top_posts", []) or []
    target = segment.get("target_segment", {}) or {}
    opp_id = segment.get("opportunity_id", "")
    seg_name = segment.get("segment_name", "")

    qualified_posts: List[Dict[str, Any]] = []
    for p in raw_posts:
        hits = _fit_hits(p, opp_id)
        signal = float(p.get("signal_score", 0) or 0)
        if hits >= 1 and signal >= 2.2:
            qualified_posts.append(p)

    posts = qualified_posts[:top_n]

    if len(posts) < top_n:
        used = {str(p.get('permalink', '')) for p in posts}
        for p in raw_posts:
            if len(posts) >= top_n:
                break
            key = str(p.get("permalink", ""))
            if key in used:
                continue
            posts.append(p)
            used.add(key)

    leads: List[Dict[str, Any]] = []
    for idx, post in enumerate(posts, start=1):
        band = _priority_band(idx)
        role = _infer_role(post, target.get("role", ""))
        pain = _short(str(post.get("title", "")), 96)
        evidence_url = str(post.get("permalink", ""))
        angle = _angle(opp_id, band)

        subjects = _email_subjects(seg_name, pain, band)
        email = {
            "subject_control": subjects["control"],
            "subject_challenger": subjects["challenger"],
            "body": _email_body(role, seg_name, angle, evidence_url, band),
        }
        linkedin = _linkedin_dm(seg_name, angle)

        sequence = [
            step
            for step in SEQUENCE_BY_BAND[band]
            if step["channel"] in preferred_channels
        ]
        if not sequence:
            sequence = [{"step": 1, "day_offset": 0, "channel": "manual_export", "touch_type": "initial"}]

        fit_hits = _fit_hits(post, opp_id)
        fit_status = "qualified" if fit_hits >= 1 else "low_fit"
        assumptions = [
            "角色画像由 subreddit + ICP 规则推断，需人工二次确认。",
            "该线索来自公开讨论信号，不等于已确认购买权限。",
            "默认优先使用 email_nurture / linkedin，如通道不可用则走 manual_export。",
        ]
        if fit_status == "low_fit":
            assumptions.append("低匹配线索：发送前必须人工复核后再入正式触达批次。")

        lead = {
            "lead_id": f"{opp_id}-lead-{idx:03d}",
            "rank": idx,
            "priority_band": band,
            "opportunity_id": opp_id,
            "segment_name": seg_name,
            "inferred_role": role,
            "target_company_size": target.get("company_size", ""),
            "target_industry": target.get("industry", ""),
            "pain_signal": pain,
            "evidence_url": evidence_url,
            "fit_hits": fit_hits,
            "fit_status": fit_status,
            "source": {
                "subreddit": post.get("subreddit", ""),
                "signal_score": post.get("signal_score", 0),
                "queries_matched": post.get("queries_matched", []),
            },
            "channel_plan": sequence,
            "message_pack": {
                "email_nurture": email,
                "linkedin": linkedin,
            },
            "assumptions": assumptions,
            "status": "queued" if fit_status == "qualified" else "needs_review",
        }
        leads.append(lead)

    return leads


def _write_queue_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_queue_csv(path: Path, leads: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "lead_id",
                "rank",
                "priority_band",
                "opportunity_id",
                "segment_name",
                "inferred_role",
                "pain_signal",
                "evidence_url",
                "fit_status",
                "primary_channel",
                "status",
                "assumptions_count",
            ]
        )
        for lead in leads:
            primary_channel = lead.get("channel_plan", [{}])[0].get("channel", "manual_export")
            writer.writerow(
                [
                    lead.get("lead_id", ""),
                    lead.get("rank", ""),
                    lead.get("priority_band", ""),
                    lead.get("opportunity_id", ""),
                    lead.get("segment_name", ""),
                    lead.get("inferred_role", ""),
                    lead.get("pain_signal", ""),
                    lead.get("evidence_url", ""),
                    lead.get("fit_status", ""),
                    primary_channel,
                    lead.get("status", ""),
                    len(lead.get("assumptions", [])),
                ]
            )


def _write_outreach_pack(path: Path, payload: Dict[str, Any]) -> None:
    segment = payload.get("segment", {})
    leads = payload.get("leads", [])
    summary = payload.get("summary", {})

    lines = [
        "# Outreach Pack (Stage2 latest)",
        "",
        f"Generated at: {payload.get('generated_at', '')}",
        f"Mode: {payload.get('mode', '')}",
        "",
        "## Segment snapshot",
        f"- Opportunity: {segment.get('opportunity_id', '')}",
        f"- Segment: {segment.get('segment_name', '')}",
        f"- Priority score: {segment.get('priority_score', 0)}",
        f"- Queue size: {summary.get('leads_total', 0)}",
        f"- Qualified leads: {summary.get('qualified_leads', 0)} | Low-fit leads: {summary.get('low_fit_leads', 0)}",
        f"- Send-ready leads: {summary.get('send_ready_leads', 0)} | Review-required: {summary.get('review_required_leads', 0)}",
        f"- Band mix: A1={summary.get('band_counts', {}).get('A1', 0)}, A2={summary.get('band_counts', {}).get('A2', 0)}, B1={summary.get('band_counts', {}).get('B1', 0)}",
        "",
        "## Sequence policy",
        "- A1: Day0 email -> Day2 linkedin -> Day4 email",
        "- A2: Day0 email -> Day3 linkedin",
        "- B1: Day0 email",
        "",
        "## First 20 leads",
        "",
        "| # | Lead ID | Band | Role (inferred) | Pain signal | Fit | Channel step1 | Evidence |",
        "|---:|---|---|---|---|---|---|---|",
    ]

    for lead in leads:
        ch = lead.get("channel_plan", [{}])[0].get("channel", "manual_export")
        lines.append(
            f"| {lead.get('rank', '')} | {lead.get('lead_id', '')} | {lead.get('priority_band', '')} | {lead.get('inferred_role', '')} | {lead.get('pain_signal', '')} | {lead.get('fit_status', '')} | {ch} | {lead.get('evidence_url', '')} |"
        )

    lines.extend(["", "## Outreach draft snippets (A1/A2/B1 examples)", ""])

    for band in ["A1", "A2", "B1"]:
        sample = next((x for x in leads if x.get("priority_band") == band), None)
        if not sample:
            continue
        email = sample.get("message_pack", {}).get("email_nurture", {})
        li = sample.get("message_pack", {}).get("linkedin", {})
        lines.extend(
            [
                f"### {band}",
                f"- Subject (control): {email.get('subject_control', '')}",
                f"- Subject (challenger): {email.get('subject_challenger', '')}",
                f"- Email body:\n{email.get('body', '')}",
                f"- LinkedIn initial: {li.get('initial', '')}",
                f"- LinkedIn follow-up: {li.get('follow_up', '')}",
                "",
            ]
        )

    lines.extend(
        [
            "## Assumption tracking",
            "- 每条线索都附带 assumptions 字段，发送前必须逐条确认。",
            "- 没有真实联系人邮箱/LinkedIn URL 时，只能进入 manual_export 阶段。",
        ]
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _write_batch_artifacts(out_dir: Path, payload: Dict[str, Any]) -> None:
    leads = payload.get("leads", [])
    eligible = [x for x in leads if x.get("status") == "queued"]
    now = _now_iso()
    batch_id = f"batch-{now.replace(':', '').replace('+00:00', 'Z')}"

    ready = {
        "batch_id": batch_id,
        "generated_at": now,
        "approval_required": True,
        "approved": False,
        "mode": payload.get("mode", "draft_only"),
        "segment": {
            "opportunity_id": payload.get("segment", {}).get("opportunity_id", ""),
            "segment_name": payload.get("segment", {}).get("segment_name", ""),
        },
        "lead_ids": [x.get("lead_id", "") for x in eligible],
        "eligible_count": len(eligible),
        "dispatch_policy": {
            "max_send_per_day": 20,
            "frequency_cap_hours": 48,
            "channel_fallback": "manual_export",
        },
    }

    approved_template = {
        **ready,
        "approved": False,
        "approved_at": "",
        "approved_by": "",
        "approval_note": "Set approved=true and fill approved_at/by before any dispatch script can run.",
    }

    (out_dir / "outreach_batch.ready.json").write_text(
        json.dumps(ready, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "outreach_batch.approved.template.json").write_text(
        json.dumps(approved_template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _ensure_state_files(out_dir: Path) -> None:
    suppression = out_dir / "suppression_list.latest.json"
    if not suppression.exists():
        suppression.write_text(
            json.dumps(
                {
                    "generated_at": _now_iso(),
                    "opted_out_leads": [],
                    "do_not_contact": [],
                    "notes": "Append opted-out leads before any real dispatch.",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    events = out_dir / "outreach_events.latest.jsonl"
    if not events.exists():
        events.write_text("", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Stage2 outreach capability artifacts")
    p.add_argument("--repo-root", type=str, default="", help="OperatorOne repo root")
    p.add_argument("--segment-index", type=int, default=0, help="Ranked segment index from prospect_queue")
    p.add_argument("--top-n", type=int, default=20, help="Number of leads to include")
    p.add_argument("--mode", type=str, default="draft_only", choices=["draft_only", "approval_required"], help="Execution mode")
    p.add_argument("--out-dir", type=str, default="", help="Output dir (default: workspaces/op1_sales/research/outreach)")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else _find_repo_root(Path.cwd())
    out_dir = Path(args.out_dir).resolve() if args.out_dir else repo_root / "workspaces" / "op1_sales" / "research" / "outreach"
    out_dir.mkdir(parents=True, exist_ok=True)

    prospect_path = repo_root / "workspaces" / "op1_sales" / "research" / "prospecting" / "prospect_queue.latest.json"
    marketing_path = repo_root / "handoffs" / "marketing_to_sales.json"

    prospect = _read_json(prospect_path)
    marketing = _read_json(marketing_path)

    segments = prospect.get("segments", [])
    if not segments:
        raise SystemExit("No segments found in prospect_queue.latest.json")
    if args.segment_index < 0 or args.segment_index >= len(segments):
        raise SystemExit(f"segment-index out of range: {args.segment_index} (segments={len(segments)})")

    seg = segments[args.segment_index]

    preferred_channels = []
    top_channels = (marketing.get("lead_signals", {}) or {}).get("top_channels", [])
    for ch in ["email_nurture", "linkedin", "organic_search"]:
        if ch in top_channels:
            preferred_channels.append(ch)
    if not preferred_channels:
        preferred_channels = ["manual_export"]

    leads = _build_leads(seg, max(1, args.top_n), preferred_channels)

    band_counts = {"A1": 0, "A2": 0, "B1": 0}
    for lead in leads:
        band = lead.get("priority_band", "B1")
        band_counts[band] = band_counts.get(band, 0) + 1

    qualified_count = sum(1 for x in leads if x.get("fit_status") == "qualified")
    send_ready_count = sum(1 for x in leads if x.get("status") == "queued")

    payload = {
        "generated_at": _now_iso(),
        "builder": "workspaces/op1_sales/scripts/build_outreach_stage2.py",
        "mode": args.mode,
        "inputs": {
            "prospect_queue": str(prospect_path.relative_to(repo_root)),
            "marketing_to_sales": str(marketing_path.relative_to(repo_root)),
        },
        "segment": {
            "rank_index": args.segment_index,
            "opportunity_id": seg.get("opportunity_id", ""),
            "segment_name": seg.get("segment_name", ""),
            "priority_score": (seg.get("scores", {}) or {}).get("priority_score", 0),
        },
        "summary": {
            "leads_total": len(leads),
            "qualified_leads": qualified_count,
            "low_fit_leads": len(leads) - qualified_count,
            "send_ready_leads": send_ready_count,
            "review_required_leads": len(leads) - send_ready_count,
            "band_counts": band_counts,
            "preferred_channels": preferred_channels,
            "dispatch_ready": False,
            "dispatch_blockers": [
                "manual_approval_required",
                "channel_config_not_verified",
            ],
        },
        "leads": leads,
    }

    json_path = out_dir / "outreach_queue.latest.json"
    csv_path = out_dir / "outreach_queue.latest.csv"
    md_path = out_dir / "outreach_pack.latest.md"

    _write_queue_json(json_path, payload)
    _write_queue_csv(csv_path, leads)
    _write_outreach_pack(md_path, payload)
    _write_batch_artifacts(out_dir, payload)
    _ensure_state_files(out_dir)

    print(f"Wrote: {json_path}")
    print(f"Wrote: {csv_path}")
    print(f"Wrote: {md_path}")
    print(f"Wrote: {out_dir / 'outreach_batch.ready.json'}")
    print(f"Wrote: {out_dir / 'outreach_batch.approved.template.json'}")
    print(f"Ensured: {out_dir / 'suppression_list.latest.json'}")
    print(f"Ensured: {out_dir / 'outreach_events.latest.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
