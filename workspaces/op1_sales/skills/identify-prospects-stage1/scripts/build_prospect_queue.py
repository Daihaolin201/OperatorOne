#!/usr/bin/env python3
"""Build a ranked prospect-identification queue from OperatorOne Stage1 signals.

Inputs
- handoffs/marketing_to_sales.json
- workspaces/op1_product/research/stage1_idea_discovery/opportunity_records.json
- workspaces/op1_product/research/reddit_signals.json

Outputs
- workspaces/op1_sales/research/prospecting/prospect_queue.latest.json
- workspaces/op1_sales/research/prospecting/prospect_queue.latest.csv
- workspaces/op1_sales/research/prospecting/prospect_queue.latest.md
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass
class SegmentSpec:
    opportunity_id: str
    name: str
    term_weights: Dict[str, float]
    subreddit_bonus: Dict[str, float]
    min_classify_score: float
    search_queries: Tuple[str, ...]


SEGMENT_SPECS: Dict[str, SegmentSpec] = {
    "opp_001": SegmentSpec(
        opportunity_id="opp_001",
        name="Invoice follow-up automation",
        term_weights={
            "invoice": 3.0,
            "invoices": 3.0,
            "overdue": 3.0,
            "late payment": 3.0,
            "accounts receivable": 3.5,
            "receivable": 2.0,
            "collections": 2.0,
            "chasing": 1.5,
        },
        subreddit_bonus={"smallbusiness": 0.8, "freelance": 1.2},
        min_classify_score=3.0,
        search_queries=(
            '"small business" "overdue invoices" "manual"',
            '"freelancer" "invoice follow up" "time"',
            '"accounts receivable" "small business" "hiring"',
            '"bookkeeping" "late invoice" "pain"',
            '"agency" "client payment" "follow up"',
        ),
    ),
    "opp_002": SegmentSpec(
        opportunity_id="opp_002",
        name="Chargeback response operations",
        term_weights={
            "chargeback": 4.0,
            "chargebacks": 4.0,
            "dispute": 3.0,
            "disputes": 3.0,
            "fraud": 2.5,
            "stripe": 2.0,
            "shopify": 1.0,
        },
        subreddit_bonus={"ecommerce": 1.8, "shopify": 1.2},
        min_classify_score=3.0,
        search_queries=(
            '"shopify" "chargeback" "manual"',
            '"ecommerce" "dispute" "time"',
            '"chargeback" "operations manager"',
            '"stripe" "chargeback" "help"',
            '"dtc" "fraud" "orders"',
        ),
    ),
    "opp_003": SegmentSpec(
        opportunity_id="opp_003",
        name="Agency client reporting",
        term_weights={
            "agency": 3.0,
            "client report": 3.0,
            "reporting": 2.0,
            "ga4": 3.0,
            "ppc": 2.5,
            "dashboard": 2.0,
            "analytics": 2.0,
        },
        subreddit_bonus={"agency": 2.0, "ppc": 2.0, "googleanalytics": 2.0},
        min_classify_score=3.5,
        search_queries=(
            '"marketing agency" "monthly report" "manual"',
            '"ga4" "agency" "client reporting"',
            '"ppc" "reporting" "hours"',
            '"agency" "reporting analyst" "hiring"',
            '"digital marketing" "client dashboard" "pain"',
        ),
    ),
    "opp_004": SegmentSpec(
        opportunity_id="opp_004",
        name="Property manager owner/tenant workflow",
        term_weights={
            "property management": 4.0,
            "property manager": 3.0,
            "tenant": 2.5,
            "owner report": 3.0,
            "rent collection": 3.0,
            "appfolio": 2.0,
            "maintenance": 1.5,
            "doors": 1.0,
        },
        subreddit_bonus={"propertymanagement": 2.2},
        min_classify_score=3.0,
        search_queries=(
            '"property management" "owner report" "manual"',
            '"tenant communication" "spreadsheet"',
            '"property manager" "rent collection" "workflow"',
            '"appfolio" "custom report"',
            '"property management" "operations" "hiring"',
        ),
    ),
    "opp_005": SegmentSpec(
        opportunity_id="opp_005",
        name="Expense reimbursement control",
        term_weights={
            "expense": 3.0,
            "expenses": 3.0,
            "receipt": 3.0,
            "reimbursement": 3.0,
            "bookkeeper": 2.0,
            "bookkeeping": 1.6,
            "fraud": 1.8,
            "venmo": 1.5,
        },
        subreddit_bonus={"smallbusiness": 1.0},
        min_classify_score=3.0,
        search_queries=(
            '"employee expenses" "manual" "small business"',
            '"receipt chasing" "bookkeeper"',
            '"expense reimbursement" "finance admin" "hiring"',
            '"duplicate expense" "small business"',
            '"expense policy" "smb"',
        ),
    ),
    "opp_006": SegmentSpec(
        opportunity_id="opp_006",
        name="Spreadsheet/PDF workflow fragility",
        term_weights={
            "spreadsheet": 3.0,
            "excel": 3.0,
            "pdf": 3.0,
            "data entry": 3.0,
            "formula": 2.0,
            "macro": 2.0,
            "copy paste": 2.0,
            "workflow": 1.5,
        },
        subreddit_bonus={"smallbusiness": 0.8, "operations": 1.0},
        min_classify_score=3.0,
        search_queries=(
            '"pdf to excel" "manual" "small business"',
            '"spreadsheet" "operations" "breaking"',
            '"data entry" "bottleneck" "smb"',
            '"excel macro" "risk" "business"',
            '"ops admin" "workflow" "manual"',
        ),
    ),
}

TOP_POSTS_PER_SEGMENT = 20
TOP1_DEFAULT_OUTPUT_FILE = "top1_20_outreach.latest.md"

SUBREDDIT_ICP_HINT = {
    "smallbusiness": "SMB老板/财务负责人",
    "ecommerce": "电商老板/运营负责人",
    "agency": "Agency owner/Account lead",
    "ppc": "投放负责人/绩效营销负责人",
    "googleanalytics": "数据分析/增长负责人",
    "propertymanagement": "物业管理负责人",
    "freelance": "自由职业者/小团队主理人",
}

OUTREACH_ANGLE_BY_OPP = {
    "opp_001": {
        "A1": "先把逾期跟进节奏自动化（D+1/D+7/D+14），不改现有开票流程。",
        "A2": "先做轻量提醒+回款看板，验证回款率提升后再扩流程。",
        "B1": "先提供模板与跟进提醒，降低手工催款负担。",
    },
    "opp_002": {
        "A1": "先做争议证据包自动汇总，优先降低单次拒付损失。",
        "A2": "先把争议截止日和处理清单拉通，减少漏处理。",
        "B1": "先用标准化拒付流程做试点，逐步接更多店铺。",
    },
    "opp_003": {
        "A1": "先把月报解释层自动生成，让客户看懂关键变化。",
        "A2": "先接GA4/Ads最核心指标，减少手工拼报表时间。",
        "B1": "先做固定模板和复用组件，降低每月重复劳动。",
    },
    "opp_004": {
        "A1": "先解决业主报告/租客沟通双线割裂，减少月末手工。",
        "A2": "先做报表模板与沟通记录归档，不替换现有PM系统。",
        "B1": "先从单门店/单业主试点，验证交付效率提升。",
    },
    "opp_005": {
        "A1": "先做重复报销拦截+凭证追缴，不改你现有财务主流程。",
        "A2": "先把收据归集与分类自动化，减少月底关账时间。",
        "B1": "先上税季资料归档模板，降低资料交接混乱。",
    },
    "opp_006": {
        "A1": "先处理PDF→表格高频场景，减少复制粘贴和公式出错。",
        "A2": "先做关键字段抽取和人工复核，控制误差风险。",
        "B1": "先从一个报表流程改造，逐步替代脆弱表格链路。",
    },
}


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def _term_hits(text: str, term_weights: Dict[str, float]) -> Tuple[float, int]:
    score = 0.0
    hits = 0
    for term, weight in term_weights.items():
        if term in text:
            score += weight
            hits += 1
    return score, hits


def _classify_text_to_segment(text: str, subreddit: str = "") -> Tuple[str | None, float, int]:
    t = _normalize(text)
    sub = _normalize(subreddit)

    best_seg = None
    best_score = 0.0
    best_hits = 0

    for seg_id, spec in SEGMENT_SPECS.items():
        score, hits = _term_hits(t, spec.term_weights)
        score += spec.subreddit_bonus.get(sub, 0.0)

        if score > best_score:
            best_seg = seg_id
            best_score = score
            best_hits = hits

    if not best_seg:
        return None, 0.0, 0

    if best_score < SEGMENT_SPECS[best_seg].min_classify_score:
        return None, best_score, best_hits

    return best_seg, best_score, best_hits


def _classify_asset(asset: Dict[str, Any]) -> Tuple[str | None, float, int]:
    content_id = _normalize(str(asset.get("content_id", "")))

    # explicit mapping first (more reliable than fuzzy matching)
    if "project-spec" in content_id:
        if "invoice" in content_id:
            return "opp_001", 99.0, 99
        if "chargeback" in content_id:
            return "opp_002", 99.0, 99
        if "client-report" in content_id or "reporti" in content_id:
            return "opp_003", 99.0, 99

    if "opp-001" in content_id:
        return "opp_001", 95.0, 95
    if "opp-004" in content_id:
        return "opp_004", 95.0, 95
    if "opp-005" in content_id:
        return "opp_005", 95.0, 95
    if "opp-006" in content_id:
        return "opp_006", 95.0, 95

    blob = " ".join(
        [
            str(asset.get("keyword", "")),
            str(asset.get("title", "")),
            str(asset.get("content_id", "")),
            str(asset.get("experiment_id", "")),
        ]
    )
    return _classify_text_to_segment(blob)


def _post_signal_score(post: Dict[str, Any], relevance_score: float, now_ts: float) -> float:
    score = float(post.get("score", 0) or 0)
    comments = float(post.get("num_comments", 0) or 0)
    created = float(post.get("created_utc", 0) or 0)
    age_days = max(1.0, (now_ts - created) / 86400.0) if created > 0 else 365.0

    engagement = (math.log1p(score) * 0.58) + (math.log1p(comments) * 0.32)
    recency = max(0.2, min(1.0, 180.0 / age_days))
    relevance = min(1.0, relevance_score / 8.0)

    return round((engagement * 0.75 + relevance * 0.25) * recency, 4)


def _priority_band(rank_index: int) -> str:
    if rank_index <= 7:
        return "A1"
    if rank_index <= 14:
        return "A2"
    return "B1"


def _infer_icp_from_post(subreddit: str, fallback_role: str) -> str:
    return SUBREDDIT_ICP_HINT.get(_normalize(subreddit), fallback_role or "目标业务负责人")


def _pain_signal_from_title(title: str) -> str:
    short = " ".join((title or "").split())
    if len(short) <= 72:
        return short
    return short[:69] + "..."


def _outreach_angle(opportunity_id: str, band: str) -> str:
    by_opp = OUTREACH_ANGLE_BY_OPP.get(opportunity_id, {})
    return by_opp.get(band, "先从高频手工痛点切入，低风险试点后再扩。")


def _draft_copy(opportunity_id: str, band: str, segment_name: str) -> str:
    angle = _outreach_angle(opportunity_id, band)
    if band == "A1":
        return (
            f"看到你最近在处理{segment_name}相关问题。"
            f"我们通常先做一周试点：{angle}"
            "如果你愿意，我可以给你一个不改现有系统的最小落地方案。"
        )
    if band == "A2":
        return (
            f"你提到的{segment_name}问题很典型。"
            f"建议先做轻量改造：{angle}"
            "先把最耗时的手工环节降下来，再决定要不要扩。"
        )
    return (
        f"你这类{segment_name}场景我们有标准化切入点。"
        f"可以从低成本步骤开始：{angle}"
        "如果你愿意，我发你一页版执行清单。"
    )


def _write_top1_default_output(payload: Dict[str, Any], out_dir: Path) -> Path:
    segments = payload.get("segments", [])
    out_path = out_dir / TOP1_DEFAULT_OUTPUT_FILE

    if not segments:
        out_path.write_text(
            "# Top1→20条候选→外联草稿 (latest)\n\n暂无可用分段数据。\n",
            encoding="utf-8",
        )
        return out_path

    top1 = segments[0]
    top_posts = (top1.get("social_signals", {}) or {}).get("top_posts", [])[:TOP_POSTS_PER_SEGMENT]
    target = top1.get("target_segment", {}) or {}

    lines = [
        "# Top1→20条候选→外联草稿 (latest)",
        "",
        f"Generated at: {payload.get('generated_at', '')}",
        "",
        "## 1) Top1 分段快照",
        f"- Opportunity: {top1.get('opportunity_id', '')}",
        f"- Segment: {top1.get('segment_name', '')}",
        f"- Priority score: {(top1.get('scores', {}) or {}).get('priority_score', 0)}",
        f"- Matched signals: {(top1.get('social_signals', {}) or {}).get('matched_posts', 0)}",
        f"- ICP: {target.get('role', '')} | size {target.get('company_size', '')} | {target.get('industry', '')}",
        "",
        "## 2) 20条候选（默认模板）",
        "",
        "| # | 优先级 | 候选画像（推断） | 痛点信号 | 证据URL | 建议切入角度 |",
        "|---:|---|---|---|---|---|",
    ]

    for idx, post in enumerate(top_posts, start=1):
        band = _priority_band(idx)
        icp = _infer_icp_from_post(post.get("subreddit", ""), target.get("role", ""))
        pain = _pain_signal_from_title(post.get("title", ""))
        url = post.get("permalink", "")
        angle = _outreach_angle(top1.get("opportunity_id", ""), band)
        lines.append(
            f"| {idx} | {band} | {icp} | {pain} | {url} | {angle} |"
        )

    if len(top_posts) < TOP_POSTS_PER_SEGMENT:
        lines.extend(
            [
                "",
                f"> 当前可用候选 {len(top_posts)} 条（不足20条时按现有高信号样本输出）。",
            ]
        )

    segment_name = top1.get("segment_name", "目标分段")
    lines.extend(
        [
            "",
            "## 3) 外联草稿（默认模板）",
            "",
            "### A1（高痛点，高紧迫）",
            f"- { _draft_copy(top1.get('opportunity_id', ''), 'A1', segment_name) }",
            "",
            "### A2（中高痛点，可快速试点）",
            f"- { _draft_copy(top1.get('opportunity_id', ''), 'A2', segment_name) }",
            "",
            "### B1（有意向，先教育再转化）",
            f"- { _draft_copy(top1.get('opportunity_id', ''), 'B1', segment_name) }",
            "",
            "## 4) 使用说明",
            "- 先打 A1，再打 A2，最后 B1。",
            "- 每条候选必须保留证据URL；不补造公司名或联系人信息。",
            "- 若需要真实公司名单，再叠加外部搜索源做账号级扩展。",
        ]
    )

    out_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return out_path


def _find_repo_root(start: Path) -> Path:
    for candidate in [start.resolve(), *start.resolve().parents]:
        if (
            (candidate / "handoffs" / "marketing_to_sales.json").exists()
            and (candidate / "workspaces" / "op1_product" / "research" / "reddit_signals.json").exists()
            and (candidate / "workspaces" / "op1_sales").exists()
        ):
            return candidate
    raise FileNotFoundError(
        "Cannot locate OperatorOne repo root. Pass --repo-root explicitly."
    )


def _build_payload(repo_root: Path) -> Dict[str, Any]:
    marketing_path = repo_root / "handoffs" / "marketing_to_sales.json"
    opportunities_path = (
        repo_root
        / "workspaces"
        / "op1_product"
        / "research"
        / "stage1_idea_discovery"
        / "opportunity_records.json"
    )
    reddit_signals_path = (
        repo_root / "workspaces" / "op1_product" / "research" / "reddit_signals.json"
    )

    marketing = _read_json(marketing_path)
    opportunities_payload = _read_json(opportunities_path)
    reddit_payload = _read_json(reddit_signals_path)

    opportunities = opportunities_payload.get("opportunities", [])
    posts = reddit_payload.get("posts", [])
    now_ts = datetime.now(tz=timezone.utc).timestamp()

    seo_priority = {
        item.get("keyword", ""): float(item.get("priority_score", 0) or 0)
        for item in marketing.get("seo_targets", [])
    }

    # classify and group content assets once
    assets_by_segment: Dict[str, List[Dict[str, Any]]] = {k: [] for k in SEGMENT_SPECS.keys()}
    for asset in marketing.get("content_assets", []):
        seg_id, relevance_score, _ = _classify_asset(asset)
        if not seg_id:
            continue
        asset_copy = dict(asset)
        asset_copy["priority_score"] = seo_priority.get(asset_copy.get("keyword", ""), 0.0)
        asset_copy["relevance_score"] = relevance_score
        assets_by_segment[seg_id].append(asset_copy)

    # classify and group posts once (exclusive assignment)
    posts_by_segment: Dict[str, List[Dict[str, Any]]] = {k: [] for k in SEGMENT_SPECS.keys()}
    unclassified_posts = 0
    for post in posts:
        blob = " ".join(
            [
                str(post.get("title", "")),
                str(post.get("selftext", "")),
                " ".join(post.get("queries_matched", []) or []),
            ]
        )
        seg_id, relevance_score, term_hits = _classify_text_to_segment(
            blob, str(post.get("subreddit", ""))
        )
        if not seg_id:
            unclassified_posts += 1
            continue

        p = {
            "title": post.get("title", ""),
            "subreddit": post.get("subreddit", ""),
            "permalink": post.get("permalink", ""),
            "score": post.get("score", 0),
            "num_comments": post.get("num_comments", 0),
            "queries_matched": post.get("queries_matched", []),
            "relevance_score": round(relevance_score, 2),
            "term_hits": term_hits,
            "signal_score": _post_signal_score(post, relevance_score, now_ts),
        }
        posts_by_segment[seg_id].append(p)

    segment_rows: List[Dict[str, Any]] = []

    for opp in opportunities:
        opp_id = opp.get("opportunity_id")
        if opp_id not in SEGMENT_SPECS:
            continue

        spec = SEGMENT_SPECS[opp_id]

        seg_posts = sorted(
            posts_by_segment.get(opp_id, []),
            key=lambda x: x["signal_score"],
            reverse=True,
        )
        top_posts = seg_posts[:TOP_POSTS_PER_SEGMENT]

        seg_assets = sorted(
            assets_by_segment.get(opp_id, []),
            key=lambda x: x.get("priority_score", 0.0),
            reverse=True,
        )

        keyword_signals = [
            {
                "keyword": a.get("keyword", ""),
                "intent": a.get("intent", ""),
                "priority_score": a.get("priority_score", 0.0),
                "content_id": a.get("content_id", ""),
            }
            for a in seg_assets[:6]
        ]

        market_score = (
            sum(x["priority_score"] for x in keyword_signals) / max(1, len(keyword_signals)) / 100.0
            if keyword_signals
            else 0.5
        )

        # enough community evidence ~= 25+ matched posts
        evidence_score = min(1.0, len(seg_posts) / 25.0)
        urgency_score = 1.0 if (opp.get("urgency_signal", {}) or {}).get("exists") else 0.6

        priority_score = round((market_score * 0.45 + evidence_score * 0.35 + urgency_score * 0.20) * 100, 2)

        segment_rows.append(
            {
                "opportunity_id": opp_id,
                "segment_name": spec.name,
                "target_segment": opp.get("target_segment", {}),
                "core_problem": opp.get("core_problem", ""),
                "distribution_entry": opp.get("distribution_entry", {}),
                "implementation_constraint": opp.get("implementation_constraint", []),
                "keyword_signals": keyword_signals,
                "social_signals": {
                    "matched_posts": len(seg_posts),
                    "top_posts": top_posts,
                },
                "search_queries": list(spec.search_queries),
                "scores": {
                    "market_score": round(market_score * 100, 2),
                    "evidence_score": round(evidence_score * 100, 2),
                    "urgency_score": round(urgency_score * 100, 2),
                    "priority_score": priority_score,
                },
            }
        )

    segment_rows.sort(key=lambda x: x["scores"]["priority_score"], reverse=True)

    return {
        "generated_at": datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat(),
        "builder": "workspaces/op1_sales/skills/identify-prospects-stage1/scripts/build_prospect_queue.py",
        "inputs": {
            "marketing_to_sales": str(marketing_path.relative_to(repo_root)),
            "opportunity_records": str(opportunities_path.relative_to(repo_root)),
            "reddit_signals": str(reddit_signals_path.relative_to(repo_root)),
        },
        "summary": {
            "segments_ranked": len(segment_rows),
            "posts_scanned": len(posts),
            "posts_classified": len(posts) - unclassified_posts,
            "posts_unclassified": unclassified_posts,
            "content_assets_scanned": len(marketing.get("content_assets", [])),
            "top_channels": (marketing.get("lead_signals", {}) or {}).get("top_channels", []),
            "estimated_weekly_leads": (marketing.get("lead_signals", {}) or {}).get("estimated_weekly_leads", 0),
            "estimated_weekly_mql": (marketing.get("lead_signals", {}) or {}).get("estimated_weekly_mql", 0),
        },
        "segments": segment_rows,
    }


def _write_outputs(payload: Dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "prospect_queue.latest.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    segment_rows = payload.get("segments", [])

    csv_path = out_dir / "prospect_queue.latest.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "rank",
                "opportunity_id",
                "segment_name",
                "target_role",
                "target_company_size",
                "target_industry",
                "priority_score",
                "matched_posts",
                "top_keyword",
                "first_20_targets_how",
            ]
        )
        for idx, row in enumerate(segment_rows, start=1):
            target = row.get("target_segment", {})
            top_keyword = ""
            if row.get("keyword_signals"):
                top_keyword = row["keyword_signals"][0].get("keyword", "")
            writer.writerow(
                [
                    idx,
                    row.get("opportunity_id", ""),
                    row.get("segment_name", ""),
                    target.get("role", ""),
                    target.get("company_size", ""),
                    target.get("industry", ""),
                    row.get("scores", {}).get("priority_score", 0),
                    row.get("social_signals", {}).get("matched_posts", 0),
                    top_keyword,
                    (row.get("distribution_entry", {}) or {}).get("first_20_targets_how", ""),
                ]
            )

    md_lines = [
        "# Prospect Queue (latest)",
        "",
        f"Generated at: {payload['generated_at']}",
        "",
        "## Ranked segments",
        "",
        "| Rank | Opportunity | Segment | Priority | Matched community signals | Top keyword |",
        "|---:|---|---|---:|---:|---|",
    ]

    for idx, row in enumerate(segment_rows, start=1):
        top_keyword = row["keyword_signals"][0]["keyword"] if row.get("keyword_signals") else "-"
        md_lines.append(
            f"| {idx} | {row['opportunity_id']} | {row['segment_name']} | {row['scores']['priority_score']} | {row['social_signals']['matched_posts']} | {top_keyword} |"
        )

    md_lines.extend(["", "## Segment briefs", ""])

    for idx, row in enumerate(segment_rows, start=1):
        target = row.get("target_segment", {})
        md_lines.extend(
            [
                f"### {idx}. {row['segment_name']} ({row['opportunity_id']})",
                f"- ICP: {target.get('role', '')} | size {target.get('company_size', '')} | {target.get('industry', '')}",
                f"- Core problem: {row.get('core_problem', '')}",
                f"- Priority score: {row.get('scores', {}).get('priority_score', 0)}",
                f"- First-20 approach: {(row.get('distribution_entry', {}) or {}).get('first_20_targets_how', '')}",
                "- Suggested search queries:",
            ]
        )
        for q in row.get("search_queries", []):
            md_lines.append(f"  - {q}")

        top_posts = row.get("social_signals", {}).get("top_posts", [])[:3]
        if top_posts:
            md_lines.append("- Top evidence posts:")
            for p in top_posts:
                md_lines.append(
                    f"  - [{p.get('title','')}]({p.get('permalink','')}) — signal_score={p.get('signal_score',0)}"
                )
        md_lines.append("")

    md_path = out_dir / "prospect_queue.latest.md"
    md_path.write_text("\n".join(md_lines).strip() + "\n")

    top1_path = _write_top1_default_output(payload, out_dir)

    print(f"Wrote: {json_path}")
    print(f"Wrote: {csv_path}")
    print(f"Wrote: {md_path}")
    print(f"Wrote: {top1_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage1 prospect queue for op1_sales")
    parser.add_argument(
        "--repo-root",
        type=str,
        default="",
        help="Path to OperatorOne repo root. Auto-detected when omitted.",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="",
        help="Output directory. Defaults to workspaces/op1_sales/research/prospecting under repo root.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.repo_root:
        repo_root = Path(args.repo_root).resolve()
    else:
        try:
            repo_root = _find_repo_root(Path.cwd())
        except FileNotFoundError:
            repo_root = _find_repo_root(Path(__file__).resolve())

    if args.out_dir:
        out_dir = Path(args.out_dir).resolve()
    else:
        out_dir = repo_root / "workspaces" / "op1_sales" / "research" / "prospecting"

    payload = _build_payload(repo_root)
    _write_outputs(payload, out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
