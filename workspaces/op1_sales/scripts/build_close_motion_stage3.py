#!/usr/bin/env python3
"""Build close-motion package from Stage3 conversion pipeline."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from conversion_stage3_common import (  # noqa: E402
    find_repo_root,
    now_iso,
    parse_monthly_price,
    read_json,
    write_json,
)


OBJECTION_PLAYS = {
    "budget": {
        "response": "先用14天最小范围试点验证‘节省工时/减少损失’，再决定是否扩量，避免一次性重投入。",
        "proof_request": "请给出当前每周手工处理时长或损失区间，用于ROI对比。",
    },
    "integration": {
        "response": "先走不改现有系统的并行流程，验证价值后再决定是否做集成。",
        "proof_request": "请列出现有关键工具栈与必须保留的字段。",
    },
    "security": {
        "response": "试点阶段仅用最小必要数据，先建立权限边界与审计记录。",
        "proof_request": "请确认可用于试点的数据范围与合规要求。",
    },
    "capacity": {
        "response": "采用 concierge 方式代劳前置配置，降低客户团队执行负担。",
        "proof_request": "请确认每周可投入的时间窗口（例如30分钟/周）。",
    },
    "timing": {
        "response": "保持低摩擦入口，约定明确回访日期并提前发送一页执行清单。",
        "proof_request": "请确认下一个决策窗口（具体周次/日期）。",
    },
    "trust_or_value": {
        "response": "先用真实场景小样本跑出可验证结果，再进入商业承诺。",
        "proof_request": "请给一个最痛点场景作为试点样本。",
    },
    "unknown_objection": {
        "response": "先澄清真实阻碍，再给定制化低风险路径。",
        "proof_request": "请明确最担心的1个风险点。",
    },
}


def _choose_ask(lead: Dict[str, Any]) -> Tuple[str, str]:
    stage = str(lead.get("current_stage", ""))
    status = str(lead.get("status", ""))

    if status == "needs_review":
        return (
            "先完成人工复核并确认目标角色后再发起成交动作",
            "review_required",
        )

    if stage in {"qualified_interest", "discovery_scheduled"}:
        return (
            "请求确认15分钟Discovery + 是否进入14天Pilot",
            "book_discovery_and_pilot_fit",
        )
    if stage in {"discovery_completed", "pilot_offered"}:
        return (
            "请求锁定14天Pilot启动日期与样本范围",
            "start_pilot",
        )
    if stage in {"pilot_active", "pilot_value_confirmed", "commercial_terms_sent"}:
        return (
            "请求签署付费启动承诺（含时间与负责人）",
            "paid_start_commitment",
        )
    if stage == "commitment_received":
        return (
            "请求完成付款并执行Paid Start",
            "collect_payment",
        )
    if stage == "paid_started":
        return (
            "推进首月复盘与扩展机会（非首单成交动作）",
            "post_conversion_expand",
        )

    return (
        "推进到下一转化阶段并发起明确请求",
        "advance_stage",
    )


def _price_map(repo_root: Path) -> Dict[str, Dict[str, Any]]:
    pricing: Dict[str, Dict[str, Any]] = {}

    build_dir = repo_root / "workspaces" / "op1_product" / "research" / "build_deploy_v1"
    for p in sorted(build_dir.glob("project_spec*.json")):
        obj = read_json(p)
        project_id = str(obj.get("project_id", "")).lower()
        adapter = str((obj.get("adapter", {}) or {}).get("name", "")).lower()

        opp_id = ""
        if "invoice" in project_id or "invoice" in adapter:
            opp_id = "opp_001"
        elif "chargeback" in project_id or "chargeback" in adapter:
            opp_id = "opp_002"
        elif "reporting" in project_id or "reporting" in adapter:
            opp_id = "opp_003"

        if not opp_id:
            src_opp = str((obj.get("source", {}) or {}).get("opportunity_id", "")).strip()
            if src_opp:
                opp_id = src_opp

        if not opp_id:
            continue

        plan_a = str((obj.get("pricing", {}) or {}).get("plan_a", "")).strip()
        plan_b = str((obj.get("pricing", {}) or {}).get("plan_b", "")).strip()

        pricing[opp_id] = {
            "plan_a": plan_a,
            "plan_b": plan_b,
            "plan_a_value": parse_monthly_price(plan_a),
            "plan_b_value": parse_monthly_price(plan_b),
            "source": str(p.relative_to(repo_root)),
        }

    blueprint = read_json(repo_root / "workspaces" / "op1_product" / "research" / "stage3_mvp_scope" / "project_blueprint.json")
    if blueprint:
        ph = blueprint.get("pricing_hypothesis", {}) or {}
        if ph:
            pricing.setdefault("opp_001", {
                "plan_a": str(ph.get("plan_a", "")).strip(),
                "plan_b": str(ph.get("plan_b", "")).strip(),
                "plan_a_value": parse_monthly_price(str(ph.get("plan_a", ""))),
                "plan_b_value": parse_monthly_price(str(ph.get("plan_b", ""))),
                "source": "workspaces/op1_product/research/stage3_mvp_scope/project_blueprint.json",
            })

    return pricing


def _value_recap(lead: Dict[str, Any]) -> str:
    pain = str(lead.get("pain_signal", "")).strip()
    role = str(lead.get("inferred_role", "")).strip()
    seg = str(lead.get("segment_name", "")).strip()
    if pain:
        return f"{role}在“{seg}”场景中暴露了明确痛点：{pain}。目标是先在14天内验证可见价值（效率/损失控制）。"
    return f"{role}属于“{seg}”高匹配画像，建议以14天低风险试点先验证价值。"


def _top_objection_block(lead: Dict[str, Any]) -> Dict[str, Any]:
    open_items = lead.get("objections_open", []) or []
    if not open_items:
        return {
            "reason": "none",
            "response": "当前无显性异议，保持单一成交请求并设定明确截止时间。",
            "proof_request": "确认试点起始日期与负责人。",
        }

    reason = str(open_items[0].get("reason", "unknown_objection")) or "unknown_objection"
    play = OBJECTION_PLAYS.get(reason, OBJECTION_PLAYS["unknown_objection"])
    return {
        "reason": reason,
        "response": play["response"],
        "proof_request": play["proof_request"],
    }


def _price_anchor(lead: Dict[str, Any], price_lookup: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    opp_id = str(lead.get("opportunity_id", "")).strip()
    entry = price_lookup.get(opp_id)
    if entry:
        return {
            "plan_a": entry.get("plan_a", ""),
            "plan_b": entry.get("plan_b", ""),
            "source": entry.get("source", ""),
        }

    return {
        "plan_a": "TBD（需确认）",
        "plan_b": "TBD（需确认）",
        "source": "not_available",
    }


def _write_md(path: Path, payload: Dict[str, Any]) -> None:
    motions = payload.get("close_motions", [])
    summary = payload.get("summary", {})

    lines = [
        "# Close Motion (Stage3 latest)",
        "",
        f"Generated at: {payload.get('generated_at', '')}",
        "",
        "## Summary",
        f"- Opportunities in motion: {summary.get('in_motion', 0)}",
        f"- Needs review: {summary.get('needs_review', 0)}",
        f"- Commitment asks: {summary.get('commitment_asks', 0)}",
        f"- Payment asks: {summary.get('payment_asks', 0)}",
        "",
        "## Close motion table",
        "",
        "| Lead ID | Stage | Readiness | Single Ask | Due | Top Objection |",
        "|---|---|---:|---|---|---|",
    ]

    for m in motions:
        lines.append(
            f"| {m.get('lead_id','')} | {m.get('current_stage','')} | {m.get('conversion_readiness_score',0)} | {m.get('single_ask','')} | {m.get('ask_due_at','')} | {m.get('objection_play',{}).get('reason','')} |"
        )

    lines.extend(["", "## Detailed motions", ""])

    for i, m in enumerate(motions, start=1):
        lines.extend(
            [
                f"### {i}. {m.get('lead_id','')} ({m.get('current_stage','')})",
                f"- Value recap: {m.get('value_recap','')}",
                f"- Single ask: {m.get('single_ask','')}",
                f"- Ask code: {m.get('ask_code','')}",
                f"- Due: {m.get('ask_due_at','')}",
                f"- Top objection: {m.get('objection_play',{}).get('reason','')}",
                f"- Objection response: {m.get('objection_play',{}).get('response','')}",
                f"- Proof request: {m.get('objection_play',{}).get('proof_request','')}",
                f"- Price anchor: A={m.get('price_anchor',{}).get('plan_a','')} | B={m.get('price_anchor',{}).get('plan_b','')}",
                f"- Evidence URL: {m.get('evidence_url','')}",
                "",
            ]
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Stage3 close motion package")
    p.add_argument("--repo-root", type=str, default="", help="OperatorOne repo root")
    p.add_argument("--out-dir", type=str, default="", help="Output dir (default: research/conversion)")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    out_dir = Path(args.out_dir).resolve() if args.out_dir else repo_root / "workspaces" / "op1_sales" / "research" / "conversion"
    out_dir.mkdir(parents=True, exist_ok=True)

    pipeline = read_json(out_dir / "conversion_pipeline.latest.json")
    leads = pipeline.get("leads", []) or []

    prices = _price_map(repo_root)

    motions: List[Dict[str, Any]] = []
    needs_review = 0
    commitment_asks = 0
    payment_asks = 0

    for lead in leads:
        stage = str(lead.get("current_stage", "")).strip()
        if stage == "closed_lost":
            continue

        single_ask, ask_code = _choose_ask(lead)
        if ask_code == "review_required":
            needs_review += 1
        if ask_code == "paid_start_commitment":
            commitment_asks += 1
        if ask_code == "collect_payment":
            payment_asks += 1

        motion = {
            "lead_id": lead.get("lead_id", ""),
            "opportunity_id": lead.get("opportunity_id", ""),
            "segment_name": lead.get("segment_name", ""),
            "current_stage": stage,
            "conversion_readiness_score": lead.get("conversion_readiness_score", 0),
            "champion_confidence": lead.get("champion_confidence", 0),
            "single_ask": single_ask,
            "ask_code": ask_code,
            "ask_due_at": lead.get("next_action_due_at", ""),
            "value_recap": _value_recap(lead),
            "objection_play": _top_objection_block(lead),
            "price_anchor": _price_anchor(lead, prices),
            "evidence_url": lead.get("evidence_url", ""),
            "next_best_action": lead.get("next_best_action", ""),
            "assumptions": [
                "成交动作基于当前状态与事件信号，需人工确认真实权限链。",
                "价格锚点为假设，最终报价以商业条款为准。",
            ],
        }
        motions.append(motion)

    # Highest readiness first.
    motions.sort(key=lambda x: float(x.get("conversion_readiness_score", 0) or 0), reverse=True)

    payload = {
        "generated_at": now_iso(),
        "builder": "workspaces/op1_sales/scripts/build_close_motion_stage3.py",
        "inputs": {
            "conversion_pipeline": "workspaces/op1_sales/research/conversion/conversion_pipeline.latest.json",
            "pricing_sources": "workspaces/op1_product/research/build_deploy_v1/project_spec*.json + stage3_mvp_scope/project_blueprint.json",
        },
        "summary": {
            "in_motion": len(motions),
            "needs_review": needs_review,
            "commitment_asks": commitment_asks,
            "payment_asks": payment_asks,
        },
        "close_motions": motions,
    }

    out_json = out_dir / "close_motion.latest.json"
    out_md = out_dir / "close_motion.latest.md"
    write_json(out_json, payload)
    _write_md(out_md, payload)

    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
