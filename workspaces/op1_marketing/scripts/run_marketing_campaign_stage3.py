#!/usr/bin/env python3
"""
Stage3 capability: Launch campaigns (shadow/review orchestration).

This stage turns Stage2 approved content assets into campaign launch packets,
tracking maps, and experimental queue decisions without auto-launching
external ad/channel systems.

Default mode: shadow
- Builds campaign backlog and launch queue
- Generates UTM attribution map
- Creates per-campaign launch packets
- Writes decision log and updates marketing_to_sales handoff

Auto launch remains disabled in Stage3.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


REQUIRED_INPUTS = [
    {"id": "stage2_run", "path": "research/stage2_content_publish/run.latest.json"},
    {"id": "stage2_backlog", "path": "research/stage2_content_publish/content.backlog.latest.json"},
    {"id": "stage2_queue", "path": "research/stage2_content_publish/publish.queue.latest.json"},
    {"id": "stage2_qa", "path": "research/stage2_content_publish/qa.latest.json"},
    {"id": "product_to_marketing_handoff", "path": "../../handoffs/product_to_marketing.json"},
]


CHANNEL_MEDIUM = {
    "linkedin": "paid_social",
    "email_nurture": "email",
    "organic_search": "organic",
}

CHANNEL_CPC = {
    "linkedin": 5.8,
    "email_nurture": 0.75,
    "organic_search": 1.25,
}

CHANNEL_CTR = {
    "linkedin": 0.012,
    "email_nurture": 0.027,
    "organic_search": 0.038,
}

INTENT_CVR = {
    "BOFU": 0.08,
    "MOFU": 0.05,
    "TOFU": 0.03,
}

INTENT_SQL_RATE = {
    "BOFU": 0.35,
    "MOFU": 0.25,
    "TOFU": 0.18,
}

INTENT_CHANNEL_MIX = {
    "BOFU": [("email_nurture", 0.45), ("linkedin", 0.35), ("organic_search", 0.20)],
    "MOFU": [("organic_search", 0.40), ("linkedin", 0.35), ("email_nurture", 0.25)],
    "TOFU": [("organic_search", 0.50), ("linkedin", 0.40), ("email_nurture", 0.10)],
}

INTENT_OBJECTIVE = {
    "BOFU": "qualified_pipeline_capture",
    "MOFU": "problem_aware_demand_generation",
    "TOFU": "awareness_and_subscriber_growth",
}


def now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_slug(value: str, fallback: str = "item") -> str:
    v = (value or "").strip().lower()
    v = re.sub(r"[^a-z0-9]+", "-", v)
    v = re.sub(r"-+", "-", v).strip("-")
    return v or fallback


def relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


def resolve_inputs(root: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    missing: List[str] = []

    for req in REQUIRED_INPUTS:
        src = (root / req["path"]).resolve()
        exists = src.exists() and src.is_file()
        rec: Dict[str, Any] = {
            "id": req["id"],
            "path": req["path"],
            "abs": str(src),
            "exists": exists,
        }
        if exists:
            stat = src.stat()
            rec.update(
                {
                    "sha256": file_sha256(src),
                    "size": stat.st_size,
                    "mtime": int(stat.st_mtime),
                }
            )
        else:
            missing.append(req["id"])
        records.append(rec)

    completeness = {
        "required": len(REQUIRED_INPUTS),
        "available": len(REQUIRED_INPUTS) - len(missing),
        "missing": missing,
        "ratio": round((len(REQUIRED_INPUTS) - len(missing)) / max(1, len(REQUIRED_INPUTS)), 4),
    }
    return records, completeness


def copy_mirror(mirror_dir: Path, records: List[Dict[str, Any]]) -> None:
    if mirror_dir.exists():
        shutil.rmtree(mirror_dir)
    mirror_dir.mkdir(parents=True, exist_ok=True)

    for rec in records:
        if not rec.get("exists"):
            continue
        src = Path(rec["abs"])
        dst = mirror_dir / safe_slug(str(rec.get("id", "input"))) / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def snapshot_id_from_records(records: List[Dict[str, Any]]) -> str:
    material = "\n".join(
        f"{r.get('id')}|{r.get('sha256', '')}|{r.get('size', '')}|{r.get('mtime', '')}" for r in records
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    ts = dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"stage3snap_{ts}_{digest}"


def build_snapshot(root: Path, records: List[Dict[str, Any]], completeness: Dict[str, Any], generated_at: str) -> Dict[str, Any]:
    return {
        "generated_at": generated_at,
        "snapshot_id": snapshot_id_from_records(records),
        "workspace_root": str(root),
        "requirements": records,
        "completeness": completeness,
    }


def build_delta(previous_snapshot: Dict[str, Any], new_snapshot: Dict[str, Any], generated_at: str) -> Dict[str, Any]:
    prev = {x.get("id"): x for x in (previous_snapshot.get("requirements", []) or [])}
    curr = {x.get("id"): x for x in (new_snapshot.get("requirements", []) or [])}

    added: List[Dict[str, Any]] = []
    changed: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []

    for k, v in curr.items():
        if k not in prev:
            added.append(v)
            continue
        p = prev[k]
        if (
            p.get("exists") != v.get("exists")
            or p.get("sha256") != v.get("sha256")
            or p.get("size") != v.get("size")
            or p.get("mtime") != v.get("mtime")
        ):
            changed.append(v)

    for k, v in prev.items():
        if k not in curr:
            removed.append(v)

    return {
        "generated_at": generated_at,
        "previous_snapshot_id": previous_snapshot.get("snapshot_id"),
        "snapshot_id": new_snapshot.get("snapshot_id"),
        "added": added,
        "changed": changed,
        "removed": removed,
    }


def required_outputs_exist(stage_dir: Path) -> bool:
    expected = [
        stage_dir / "run.latest.json",
        stage_dir / "state.latest.json",
        stage_dir / "campaigns.backlog.latest.json",
        stage_dir / "campaigns.queue.latest.json",
        stage_dir / "experiments.latest.json",
        stage_dir / "attribution.map.latest.csv",
        stage_dir / "decision_log.latest.md",
    ]
    return all(p.exists() for p in expected)


def normalize_intent(value: str) -> str:
    v = (value or "").upper().strip()
    if v in {"BOFU", "MOFU", "TOFU"}:
        return v
    return "MOFU"


def channel_mix(intent: str) -> List[Tuple[str, float]]:
    return INTENT_CHANNEL_MIX.get(normalize_intent(intent), INTENT_CHANNEL_MIX["MOFU"])


def campaign_objective(intent: str) -> str:
    return INTENT_OBJECTIVE.get(normalize_intent(intent), INTENT_OBJECTIVE["MOFU"])


def confidence_bonus(value: str) -> float:
    return {"high": 4.0, "medium": 2.0, "low": 0.0}.get((value or "").lower(), 0.0)


def intent_bonus(value: str) -> float:
    return {"BOFU": 8.0, "MOFU": 5.0, "TOFU": 3.0}.get(normalize_intent(value), 5.0)


def split_budget(total_budget: float, shares: List[Tuple[str, float]]) -> Dict[str, float]:
    if total_budget <= 0:
        return {k: 0.0 for (k, _) in shares}

    out: Dict[str, float] = {}
    running = 0.0
    for idx, (channel, pct) in enumerate(shares):
        if idx == len(shares) - 1:
            amount = round(max(0.0, total_budget - running), 2)
        else:
            amount = round(total_budget * float(pct), 2)
            running += amount
        out[channel] = amount

    # tiny correction if rounding drifts negative
    drift = round(total_budget - sum(out.values()), 2)
    if abs(drift) >= 0.01 and out:
        first = next(iter(out.keys()))
        out[first] = round(out[first] + drift, 2)
    return out


def resolve_landing_url(product_handoff: Dict[str, Any], base_domain: str) -> str:
    raw = str(product_handoff.get("landing_page_url_or_path", "") or "").strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw

    path = raw if raw else "/landing/operatorone"
    if not path.startswith("/"):
        path = "/" + path

    domain = base_domain.strip().rstrip("/")
    if not domain.startswith("http://") and not domain.startswith("https://"):
        domain = "https://" + domain
    return f"{domain}{path}"


def build_tracked_url(base_url: str, params: Dict[str, str]) -> str:
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({k: v for k, v in params.items() if v is not None})
    new_query = urlencode(query)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


def estimate_channel_metrics(channel: str, intent: str, budget: float) -> Dict[str, float]:
    cpc = float(CHANNEL_CPC.get(channel, 2.5))
    ctr = float(CHANNEL_CTR.get(channel, 0.015))
    cvr = float(INTENT_CVR.get(normalize_intent(intent), 0.05))
    sql_rate = float(INTENT_SQL_RATE.get(normalize_intent(intent), 0.25))

    clicks = max(0.0, budget / max(0.01, cpc))
    sessions = clicks * 0.92
    # signal coefficient keeps channel-level differentiation modest
    channel_coef = {"linkedin": 1.0, "email_nurture": 1.08, "organic_search": 0.96}.get(channel, 1.0)

    mql = sessions * cvr * channel_coef
    sql = mql * sql_rate

    return {
        "budget": round(budget, 2),
        "cpc_assumption": round(cpc, 3),
        "ctr_assumption": round(ctr, 4),
        "clicks_est": round(clicks, 2),
        "sessions_est": round(sessions, 2),
        "mql_est": round(mql, 2),
        "sql_est": round(sql, 2),
    }


def compute_readiness(item: Dict[str, Any], min_readiness: float) -> Tuple[float, str, List[str]]:
    priority = float(item.get("priority_score", 0.0))
    qa_score = float(((item.get("qa", {}) or {}).get("quality_score", 0.0)) or 0.0)
    intent = normalize_intent(item.get("intent", "MOFU"))
    queue_state = str(item.get("queue_state", "")).strip()

    score = 0.0
    score += 0.42 * priority
    score += 0.18 * qa_score

    intent_weight = {"BOFU": 6.0, "MOFU": 4.0, "TOFU": 2.0}.get(intent, 4.0)
    score += intent_weight

    confidence_weight = {"high": 3.0, "medium": 1.5, "low": 0.0}.get(str(item.get("confidence", "low")).lower(), 0.0)
    score += confidence_weight

    flags: List[str] = []
    hard_block = False

    source_ptrs = item.get("source_pointers", []) or []
    if source_ptrs:
        score += 4.0
    else:
        score -= 8.0
        flags.append("missing_source_pointers")

    if item.get("draft_path"):
        score += 2.0
    else:
        score -= 12.0
        flags.append("missing_draft_path")
        hard_block = True

    review_decision = (item.get("review_decision", {}) or {}).get("decision")
    if review_decision == "approved":
        score += 5.0
    elif review_decision == "needs_revision":
        score -= 24.0
        flags.append("manual_revision_requested")
        hard_block = True

    qa_result = str((item.get("qa", {}) or {}).get("result", "")).strip().lower()
    if qa_result != "pass":
        score -= 20.0
        flags.append("qa_not_pass")

    risk_flags = (item.get("qa", {}) or {}).get("risk_flags", []) or []
    if risk_flags:
        score -= min(18.0, float(len(risk_flags)) * 6.0)
        flags.append("qa_risk_flags_present")

    if queue_state == "approved":
        score += 4.0
    elif queue_state == "review_ready":
        score += 1.0
    else:
        score -= 10.0
        flags.append(f"upstream_state_{queue_state or 'unknown'}")

    score = round(max(0.0, min(100.0, score)), 2)

    if hard_block:
        return score, "hold", flags
    if queue_state == "approved" and score >= float(min_readiness):
        return score, "launch_ready", flags
    if score >= max(0.0, float(min_readiness) - 10.0):
        return score, "watchlist", flags
    return score, "hold", flags


def select_assets(
    stage2_backlog: Dict[str, Any],
    max_campaigns: int,
    include_review_ready: bool,
) -> List[Dict[str, Any]]:
    items = (stage2_backlog.get("items", []) or []) if isinstance(stage2_backlog, dict) else []

    allowed = {"approved"}
    if include_review_ready:
        allowed.add("review_ready")

    selected: List[Dict[str, Any]] = []
    seen: set[str] = set()

    ordered = sorted(items, key=lambda x: (-float(x.get("priority_score", 0.0)), x.get("content_id", "")))

    for item in ordered:
        content_id = str(item.get("content_id", "") or "").strip()
        if not content_id or content_id in seen:
            continue
        if str(item.get("queue_state", "") or "").strip() not in allowed:
            continue

        seen.add(content_id)
        selected.append(item)
        if len(selected) >= max(1, max_campaigns):
            break

    return selected


def build_hypothesis(item: Dict[str, Any], channel_primary: str) -> str:
    keyword = item.get("primary_keyword", "")
    intent = normalize_intent(item.get("intent", "MOFU"))
    if intent == "BOFU":
        return f"For high-intent operators searching '{keyword}', a proof-led {channel_primary} narrative will lift qualified lead rate."
    if intent == "TOFU":
        return f"For early-stage audiences around '{keyword}', educational {channel_primary} creative will increase engaged sessions and subscriber growth."
    return f"For problem-aware audiences around '{keyword}', pragmatic {channel_primary} messaging will improve conversion to qualified conversations."


def build_variant_plan(primary_channel: str) -> List[Dict[str, str]]:
    if primary_channel == "linkedin":
        variable = "hook_angle"
    elif primary_channel == "email_nurture":
        variable = "subject_line"
    else:
        variable = "title_meta_frame"

    return [
        {
            "variant_id": "control",
            "label": "evidence_first",
            "variable": variable,
            "expected_effect": "baseline",
        },
        {
            "variant_id": "challenger",
            "label": "outcome_first",
            "variable": variable,
            "expected_effect": "+10% qualified_lead_rate",
        },
    ]


def write_packet(
    packets_dir: Path,
    campaign: Dict[str, Any],
    landing_url: str,
) -> str:
    campaign_id = campaign.get("campaign_id", "campaign")
    path = packets_dir / f"{safe_slug(campaign_id)}.md"

    channel_lines = []
    for c in campaign.get("channels", []):
        channel_lines.append(
            f"- **{c.get('channel')}** | budget={c.get('budget')} | medium={c.get('utm_medium')} | variants={','.join(c.get('variants', []))}"
        )

    metric = campaign.get("forecast", {})
    lines = [
        f"# Stage3 Launch Packet — {campaign_id}",
        "",
        f"- Generated at: {campaign.get('generated_at')}",
        f"- Status: `{campaign.get('queue_state')}`",
        f"- Objective: `{campaign.get('objective')}`",
        f"- Content asset: `{campaign.get('content_id')}`",
        f"- Intent: `{campaign.get('intent')}`",
        f"- Landing URL: {landing_url}",
        "",
        "## Hypothesis",
        campaign.get("hypothesis", ""),
        "",
        "## Channel allocation",
        *channel_lines,
        "",
        "## Experiment design",
        f"- Primary metric: {campaign.get('experiment', {}).get('primary_metric')}",
        f"- Guardrails: {', '.join(campaign.get('experiment', {}).get('guardrail_metrics', []))}",
        f"- Variants: {', '.join([x.get('variant_id','') for x in campaign.get('experiment', {}).get('variants', [])])}",
        "",
        "## Forecast",
        f"- Clicks est: {metric.get('clicks_est')}",
        f"- MQL est: {metric.get('mql_est')}",
        f"- SQL est: {metric.get('sql_est')}",
        "",
        "## Decision",
        f"- Readiness score: {campaign.get('readiness_score')}",
        f"- Risk flags: {', '.join(campaign.get('risk_flags', [])) or '(none)'}",
        "",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def write_attribution_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    headers = [
        "campaign_id",
        "content_id",
        "channel",
        "variant",
        "utm_id",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "landing_url",
        "tracked_url",
    ]

    lines = [",".join(headers)]
    for row in rows:
        cols: List[str] = []
        for h in headers:
            v = str(row.get(h, "") or "")
            if any(ch in v for ch in [",", '"', "\n"]):
                v = '"' + v.replace('"', '""') + '"'
            cols.append(v)
        lines.append(",".join(cols))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_decision_log(
    path: Path,
    generated_at: str,
    snapshot_id: str,
    launch_ready: List[Dict[str, Any]],
    watchlist: List[Dict[str, Any]],
    hold: List[Dict[str, Any]],
) -> None:
    lines = [
        f"# Stage3 Campaign Launch Decision Log — {dt.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
        "",
        f"- Generated at: {generated_at}",
        f"- Input snapshot: `{snapshot_id}`",
        f"- Launch ready: **{len(launch_ready)}**",
        f"- Watchlist: **{len(watchlist)}**",
        f"- Hold: **{len(hold)}**",
        "",
        "## Launch Ready",
    ]

    if launch_ready:
        for item in launch_ready[:30]:
            lines.append(
                f"- `{item.get('campaign_id')}` | {item.get('primary_keyword')} | readiness={item.get('readiness_score')} | sql_est={item.get('forecast', {}).get('sql_est')}"
            )
    else:
        lines.append("- (none)")

    lines += ["", "## Watchlist"]
    if watchlist:
        for item in watchlist[:30]:
            lines.append(
                f"- `{item.get('campaign_id')}` | {item.get('primary_keyword')} | readiness={item.get('readiness_score')} | flags={','.join(item.get('risk_flags', [])) or '(none)'}"
            )
    else:
        lines.append("- (none)")

    lines += ["", "## Hold"]
    if hold:
        for item in hold[:30]:
            lines.append(
                f"- `{item.get('campaign_id')}` | {item.get('primary_keyword')} | readiness={item.get('readiness_score')} | flags={','.join(item.get('risk_flags', [])) or '(none)'}"
            )
    else:
        lines.append("- (none)")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_marketing_to_sales_handoff(
    root: Path,
    generated_at: str,
    campaigns: List[Dict[str, Any]],
    queue_counts: Dict[str, int],
) -> Path:
    handoff_path = (root / "../../handoffs/marketing_to_sales.json").resolve()
    existing = read_json(handoff_path, default={})
    if not isinstance(existing, dict):
        existing = {}

    existing_campaigns = [
        c for c in (existing.get("campaigns", []) or []) if not str(c.get("campaign_id", "")).startswith("stage3-")
    ]

    stage3_campaigns = []
    campaign_assets = []

    total_sql = 0.0
    total_mql = 0.0

    for campaign in campaigns:
        cid = str(campaign.get("campaign_id", ""))
        queue_state = str(campaign.get("queue_state", "hold"))
        forecast = campaign.get("forecast", {}) or {}

        total_sql += float(forecast.get("sql_est", 0.0) or 0.0)
        total_mql += float(forecast.get("mql_est", 0.0) or 0.0)

        stage3_campaigns.append(
            {
                "campaign_id": cid,
                "name": campaign.get("name"),
                "status": queue_state,
                "auto_launch": False,
                "objective": campaign.get("objective"),
                "primary_channel": campaign.get("primary_channel"),
                "budget": campaign.get("budget_total", 0.0),
                "forecast_sql": round(float(forecast.get("sql_est", 0.0) or 0.0), 2),
                "generated_at": generated_at,
            }
        )

        for channel_row in campaign.get("channels", []):
            campaign_assets.append(
                {
                    "campaign_id": cid,
                    "content_id": campaign.get("content_id"),
                    "channel": channel_row.get("channel"),
                    "status": queue_state,
                    "budget": channel_row.get("budget"),
                    "utm_medium": channel_row.get("utm_medium"),
                }
            )

    updated = {
        "contract_version": "1.0.0",
        "generated_at": generated_at,
        "generated_by": "workspaces/op1_marketing/scripts/run_marketing_campaign_stage3.py",
        "campaigns": existing_campaigns + stage3_campaigns,
        "campaign_assets": campaign_assets,
        "content_assets": existing.get("content_assets", []),
        "seo_targets": existing.get("seo_targets", []),
        "lead_signals": {
            "top_channels": ["linkedin", "email_nurture", "organic_search"],
            "estimated_weekly_leads": int(round(total_sql)),
            "estimated_weekly_mql": int(round(total_mql)),
            "note": "Stage3 shadow launch forecast from approved Stage2 assets; auto-launch disabled.",
        },
        "campaign_launch": {
            "stage": "stage3_campaign_launch_shadow",
            "auto_launch": False,
            "queue_counts": queue_counts,
            "next_actions": [
                "Prioritize launch_ready queue for ops handoff",
                "Rework watchlist and hold assets",
                "Track experiment outcomes and feed learnings back to Stage1/2",
            ],
        },
        "offer_context": existing.get("offer_context", {}),
    }

    write_json(handoff_path, updated)
    return handoff_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage3 campaign launch orchestration (no auto launch)")
    parser.add_argument("--root-dir", default=None, help="Workspace root (defaults to script parent)")
    parser.add_argument("--stage-dir", default=None, help="Stage3 output directory")
    parser.add_argument("--mode", choices=["shadow", "review"], default="shadow")
    parser.add_argument("--force", action="store_true", help="Force recompute")
    parser.add_argument("--max-campaigns", type=int, default=8, help="Maximum campaign plans to generate")
    parser.add_argument("--include-review-ready", action="store_true", help="Include Stage2 review_ready items as watch candidates")
    parser.add_argument("--min-readiness", type=float, default=78.0, help="Readiness threshold for launch_ready queue")
    parser.add_argument("--default-budget", type=float, default=1200.0, help="Fallback budget when product handoff budget is not set")
    parser.add_argument("--duration-days", type=int, default=14, help="Default campaign duration in days")
    parser.add_argument("--base-domain", default="https://operatorone.ai", help="Fallback base domain for landing URL construction")
    parser.add_argument("--print-summary", action="store_true", help="Print compact JSON summary")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    script_dir = Path(__file__).resolve().parent
    root = Path(args.root_dir).resolve() if args.root_dir else script_dir.parent.resolve()
    stage_dir = Path(args.stage_dir).resolve() if args.stage_dir else (root / "research/stage3_campaign_launch").resolve()

    input_dir = stage_dir / "input"
    snapshot_path = input_dir / "stage2_snapshot.latest.json"
    delta_path = input_dir / "delta.latest.json"
    mirror_dir = input_dir / "mirror.latest"

    run_path = stage_dir / "run.latest.json"
    state_path = stage_dir / "state.latest.json"
    backlog_path = stage_dir / "campaigns.backlog.latest.json"
    queue_path = stage_dir / "campaigns.queue.latest.json"
    experiments_path = stage_dir / "experiments.latest.json"
    attribution_path = stage_dir / "attribution.map.latest.csv"
    decision_log_path = stage_dir / "decision_log.latest.md"
    packets_dir = stage_dir / "packets"

    generated_at = now_iso()
    run_id = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    previous_snapshot = read_json(snapshot_path, default={}) or {}
    previous_state = read_json(state_path, default={}) or {}

    summary: Dict[str, Any] = {
        "generated_at": generated_at,
        "run_id": run_id,
        "stage_dir": str(stage_dir),
    }

    try:
        records, completeness = resolve_inputs(root)
        copy_mirror(mirror_dir, records)

        snapshot = build_snapshot(root, records, completeness, generated_at)
        write_json(snapshot_path, snapshot)

        delta = build_delta(previous_snapshot, snapshot, generated_at)
        write_json(delta_path, delta)

        delta_counts = {
            "added": len(delta.get("added", [])),
            "changed": len(delta.get("changed", [])),
            "removed": len(delta.get("removed", [])),
        }
        has_delta = any(delta_counts.values())
        should_recompute = args.force or has_delta or not required_outputs_exist(stage_dir)

        base_run = {
            "generated_at": generated_at,
            "run_id": run_id,
            "capability": "marketing_launch_campaigns_stage3_shadow_v1",
            "mode": args.mode,
            "auto_launch": False,
            "launch_mode": "disabled",
            "input_sync": {
                "snapshot_id": snapshot.get("snapshot_id"),
                "completeness": completeness,
                "delta_counts": delta_counts,
                "requirements": records,
            },
        }

        if completeness.get("ratio", 0.0) < 1.0:
            reason = "blocked_input_incomplete"

            write_json(backlog_path, {"generated_at": generated_at, "status": reason, "items": []})
            write_json(
                queue_path,
                {
                    "generated_at": generated_at,
                    "status": reason,
                    "auto_launch": False,
                    "queue": {"launch_ready": [], "watchlist": [], "hold": []},
                    "counts": {"launch_ready": 0, "watchlist": 0, "hold": 0},
                },
            )
            write_json(experiments_path, {"generated_at": generated_at, "status": reason, "experiments": []})
            write_attribution_csv(attribution_path, rows=[])
            decision_log_path.write_text("# Stage3 Campaign Launch Decision Log\n\n- Status: blocked_input_incomplete\n", encoding="utf-8")

            run_payload = dict(base_run)
            run_payload.update({"status": reason})
            write_json(run_path, run_payload)

            write_json(
                state_path,
                {
                    "loop_state": reason,
                    "mode": args.mode,
                    "auto_launch": False,
                    "last_run_status": reason,
                    "input_completeness": completeness,
                    "snapshot_id": snapshot.get("snapshot_id"),
                    "delta_counts": delta_counts,
                    "last_incremental_run_at": generated_at,
                },
            )

            summary.update({"status": reason})
            if args.print_summary:
                print(json.dumps(summary, ensure_ascii=False))
            return 0

        if not should_recompute:
            run_payload = dict(base_run)
            run_payload.update(
                {
                    "status": "no_change",
                    "note": "Input snapshot unchanged; Stage3 recompute skipped.",
                }
            )
            write_json(run_path, run_payload)

            write_json(
                state_path,
                {
                    "loop_state": "idle_no_change",
                    "mode": args.mode,
                    "auto_launch": False,
                    "last_run_status": "no_change",
                    "input_completeness": completeness,
                    "snapshot_id": snapshot.get("snapshot_id"),
                    "delta_counts": delta_counts,
                    "last_incremental_run_at": generated_at,
                    "campaigns_total": int(previous_state.get("campaigns_total", 0)),
                    "launch_ready": int(previous_state.get("launch_ready", 0)),
                    "watchlist": int(previous_state.get("watchlist", 0)),
                    "hold": int(previous_state.get("hold", 0)),
                },
            )

            summary.update({"status": "no_change"})
            if args.print_summary:
                print(json.dumps(summary, ensure_ascii=False))
            return 0

        stage2_run = read_json((root / "research/stage2_content_publish/run.latest.json").resolve(), default={}) or {}
        stage2_status = stage2_run.get("status")
        if stage2_status not in {"passed", "no_change"}:
            reason = "blocked_upstream_stage2_unhealthy"
            run_payload = dict(base_run)
            run_payload.update(
                {
                    "status": reason,
                    "upstream_status": stage2_status,
                    "note": "Stage2 run is not healthy; refusing Stage3 orchestration.",
                }
            )
            write_json(run_path, run_payload)
            write_json(
                state_path,
                {
                    "loop_state": reason,
                    "mode": args.mode,
                    "auto_launch": False,
                    "last_run_status": reason,
                    "upstream_status": stage2_status,
                    "last_incremental_run_at": generated_at,
                },
            )
            summary.update({"status": reason, "upstream_status": stage2_status})
            if args.print_summary:
                print(json.dumps(summary, ensure_ascii=False))
            return 0

        stage2_backlog = read_json((root / "research/stage2_content_publish/content.backlog.latest.json").resolve(), default={}) or {}
        stage2_queue = read_json((root / "research/stage2_content_publish/publish.queue.latest.json").resolve(), default={}) or {}
        product_handoff = read_json((root / "../../handoffs/product_to_marketing.json").resolve(), default={}) or {}

        selected_assets = select_assets(
            stage2_backlog=stage2_backlog,
            max_campaigns=max(1, int(args.max_campaigns)),
            include_review_ready=bool(args.include_review_ready),
        )

        if not selected_assets:
            reason = "blocked_no_launchable_assets"

            write_json(backlog_path, {"generated_at": generated_at, "status": reason, "items": []})
            write_json(
                queue_path,
                {
                    "generated_at": generated_at,
                    "status": reason,
                    "auto_launch": False,
                    "queue": {"launch_ready": [], "watchlist": [], "hold": []},
                    "counts": {"launch_ready": 0, "watchlist": 0, "hold": 0},
                },
            )
            write_json(experiments_path, {"generated_at": generated_at, "status": reason, "experiments": []})
            write_attribution_csv(attribution_path, rows=[])
            decision_log_path.write_text("# Stage3 Campaign Launch Decision Log\n\n- Status: blocked_no_launchable_assets\n", encoding="utf-8")

            run_payload = dict(base_run)
            run_payload.update({"status": reason})
            write_json(run_path, run_payload)

            write_json(
                state_path,
                {
                    "loop_state": reason,
                    "mode": args.mode,
                    "auto_launch": False,
                    "last_run_status": reason,
                    "snapshot_id": snapshot.get("snapshot_id"),
                    "delta_counts": delta_counts,
                    "last_incremental_run_at": generated_at,
                    "campaigns_total": 0,
                    "launch_ready": 0,
                    "watchlist": 0,
                    "hold": 0,
                },
            )

            summary.update({"status": reason})
            if args.print_summary:
                print(json.dumps(summary, ensure_ascii=False))
            return 0

        constraints = (product_handoff.get("constraints", {}) or {}) if isinstance(product_handoff, dict) else {}
        upstream_budget = float(constraints.get("budget", 0) or 0)
        total_budget = upstream_budget if upstream_budget > 0 else float(args.default_budget)

        timeline_days = int(constraints.get("timeline_days", 0) or 0)
        if timeline_days <= 0:
            timeline_days = int(args.duration_days)
        timeline_days = max(3, timeline_days)

        landing_url = resolve_landing_url(product_handoff if isinstance(product_handoff, dict) else {}, args.base_domain)

        campaigns: List[Dict[str, Any]] = []
        experiments: List[Dict[str, Any]] = []
        attribution_rows: List[Dict[str, Any]] = []

        # First pass: compute readiness + preliminary weights
        for idx, asset in enumerate(selected_assets, start=1):
            readiness_score, queue_state, flags = compute_readiness(asset, float(args.min_readiness))
            cid = str(asset.get("content_id", "") or f"content-{idx}")
            campaign_id = f"stage3-{safe_slug(cid)}"

            shares = channel_mix(asset.get("intent", "MOFU"))
            primary_channel = shares[0][0]

            campaign = {
                "campaign_id": campaign_id,
                "name": f"Stage3 launch for {cid}",
                "generated_at": generated_at,
                "mode": args.mode,
                "auto_launch": False,
                "content_id": cid,
                "experiment_id": asset.get("experiment_id"),
                "context_id": asset.get("context_id"),
                "primary_keyword": asset.get("primary_keyword"),
                "intent": normalize_intent(asset.get("intent", "MOFU")),
                "objective": campaign_objective(asset.get("intent", "MOFU")),
                "title": asset.get("selected_title"),
                "cta": asset.get("cta"),
                "draft_path": asset.get("draft_path"),
                "source_pointers": asset.get("source_pointers", []) or [],
                "priority_score": float(asset.get("priority_score", 0.0)),
                "readiness_score": readiness_score,
                "queue_state": queue_state,
                "risk_flags": flags,
                "primary_channel": primary_channel,
                "channel_mix": [{"channel": c, "allocation_pct": p} for (c, p) in shares],
                "duration_days": timeline_days,
                "hypothesis": build_hypothesis(asset, primary_channel),
                "experiment": {
                    "primary_metric": "qualified_lead_rate",
                    "guardrail_metrics": ["cost_per_sql", "mql_to_sql_rate", "bounce_rate"],
                    "variants": build_variant_plan(primary_channel),
                },
            }
            campaigns.append(campaign)

        # Budget allocation weighted by readiness among non-hold campaigns.
        alloc_candidates = [c for c in campaigns if c.get("queue_state") in {"launch_ready", "watchlist"}]
        weight_sum = sum(max(1.0, float(c.get("readiness_score", 0.0))) for c in alloc_candidates)

        for campaign in campaigns:
            if campaign.get("queue_state") == "hold" or weight_sum <= 0.0:
                campaign_budget = 0.0
            else:
                campaign_budget = total_budget * (max(1.0, float(campaign.get("readiness_score", 0.0))) / weight_sum)

            campaign_budget = round(campaign_budget, 2)
            campaign["budget_total"] = campaign_budget

            shares = [(x["channel"], float(x["allocation_pct"])) for x in campaign.get("channel_mix", [])]
            channel_budgets = split_budget(campaign_budget, shares)

            channel_rows = []
            campaign_clicks = 0.0
            campaign_mql = 0.0
            campaign_sql = 0.0

            utm_campaign_name = f"stage3_{safe_slug(campaign.get('campaign_id', 'campaign'))}"

            for channel, pct in shares:
                medium = CHANNEL_MEDIUM.get(channel, "referral")
                budget = float(channel_budgets.get(channel, 0.0))
                metrics = estimate_channel_metrics(channel, campaign.get("intent", "MOFU"), budget)

                campaign_clicks += float(metrics.get("clicks_est", 0.0) or 0.0)
                campaign_mql += float(metrics.get("mql_est", 0.0) or 0.0)
                campaign_sql += float(metrics.get("sql_est", 0.0) or 0.0)

                variants = [x.get("variant_id") for x in campaign.get("experiment", {}).get("variants", [])]
                channel_rows.append(
                    {
                        "channel": channel,
                        "allocation_pct": round(pct, 3),
                        "budget": round(budget, 2),
                        "utm_source": channel,
                        "utm_medium": medium,
                        "variants": variants,
                        "metrics": metrics,
                    }
                )

                for variant in variants:
                    utm_params = {
                        "utm_id": campaign.get("campaign_id"),
                        "utm_source": channel,
                        "utm_medium": medium,
                        "utm_campaign": utm_campaign_name,
                        "utm_content": f"{safe_slug(campaign.get('content_id', 'content'))}_{variant}",
                    }
                    tracked = build_tracked_url(landing_url, utm_params)
                    attribution_rows.append(
                        {
                            "campaign_id": campaign.get("campaign_id"),
                            "content_id": campaign.get("content_id"),
                            "channel": channel,
                            "variant": variant,
                            "utm_id": utm_params["utm_id"],
                            "utm_source": utm_params["utm_source"],
                            "utm_medium": utm_params["utm_medium"],
                            "utm_campaign": utm_params["utm_campaign"],
                            "utm_content": utm_params["utm_content"],
                            "landing_url": landing_url,
                            "tracked_url": tracked,
                        }
                    )

            campaign["channels"] = channel_rows
            campaign["forecast"] = {
                "clicks_est": round(campaign_clicks, 2),
                "mql_est": round(campaign_mql, 2),
                "sql_est": round(campaign_sql, 2),
            }

            experiment_card = {
                "experiment_id": f"exp-{safe_slug(str(campaign.get('campaign_id', 'campaign')))}",
                "campaign_id": campaign.get("campaign_id"),
                "content_id": campaign.get("content_id"),
                "queue_state": campaign.get("queue_state"),
                "primary_metric": campaign.get("experiment", {}).get("primary_metric"),
                "guardrail_metrics": campaign.get("experiment", {}).get("guardrail_metrics", []),
                "variants": campaign.get("experiment", {}).get("variants", []),
                "runbook": {
                    "minimum_runtime_days": min(14, timeline_days),
                    "analysis_window_days": 7,
                    "decision_rules": {
                        "promote": "challenger beats control by >=10% on primary metric with stable guardrails",
                        "hold": "results inconclusive or guardrail regression >15%",
                        "pause": "primary metric regression >20% for 3 consecutive days",
                    },
                },
            }
            experiments.append(experiment_card)

        # Stable ordering for deterministic outputs.
        campaigns.sort(key=lambda x: (-float(x.get("readiness_score", 0.0)), x.get("campaign_id", "")))
        experiments.sort(key=lambda x: x.get("campaign_id", ""))
        attribution_rows.sort(key=lambda x: (x.get("campaign_id", ""), x.get("channel", ""), x.get("variant", "")))

        launch_ready = [c for c in campaigns if c.get("queue_state") == "launch_ready"]
        watchlist = [c for c in campaigns if c.get("queue_state") == "watchlist"]
        hold = [c for c in campaigns if c.get("queue_state") == "hold"]

        if packets_dir.exists():
            shutil.rmtree(packets_dir)
        packets_dir.mkdir(parents=True, exist_ok=True)

        for campaign in campaigns:
            packet_abs = write_packet(packets_dir, campaign, landing_url)
            campaign["packet_path"] = relative_path(Path(packet_abs), root)

        backlog_payload = {
            "generated_at": generated_at,
            "status": "ok",
            "snapshot_id": snapshot.get("snapshot_id"),
            "stage2_snapshot_id": stage2_run.get("input_sync", {}).get("snapshot_id"),
            "mode": args.mode,
            "auto_launch": False,
            "items": campaigns,
            "summary": {
                "campaigns_total": len(campaigns),
                "launch_ready": len(launch_ready),
                "watchlist": len(watchlist),
                "hold": len(hold),
                "max_campaigns": int(args.max_campaigns),
                "include_review_ready": bool(args.include_review_ready),
                "min_readiness": float(args.min_readiness),
                "budget_total": round(total_budget, 2),
                "duration_days": timeline_days,
            },
        }
        write_json(backlog_path, backlog_payload)

        queue_payload = {
            "generated_at": generated_at,
            "status": "ok",
            "mode": args.mode,
            "auto_launch": False,
            "queue": {
                "launch_ready": launch_ready,
                "watchlist": watchlist,
                "hold": hold,
            },
            "counts": {
                "launch_ready": len(launch_ready),
                "watchlist": len(watchlist),
                "hold": len(hold),
            },
        }
        write_json(queue_path, queue_payload)

        experiments_payload = {
            "generated_at": generated_at,
            "status": "ok",
            "mode": args.mode,
            "experiments": experiments,
            "summary": {
                "total": len(experiments),
                "launch_ready": len([x for x in experiments if str(x.get("queue_state")) == "launch_ready"]),
            },
        }
        write_json(experiments_path, experiments_payload)

        write_attribution_csv(attribution_path, rows=attribution_rows)

        write_decision_log(
            path=decision_log_path,
            generated_at=generated_at,
            snapshot_id=str(snapshot.get("snapshot_id", "")),
            launch_ready=launch_ready,
            watchlist=watchlist,
            hold=hold,
        )

        handoff_path = update_marketing_to_sales_handoff(
            root=root,
            generated_at=generated_at,
            campaigns=campaigns,
            queue_counts=queue_payload.get("counts", {}),
        )

        total_clicks = round(sum(float((x.get("forecast", {}) or {}).get("clicks_est", 0.0) or 0.0) for x in campaigns), 2)
        total_mql = round(sum(float((x.get("forecast", {}) or {}).get("mql_est", 0.0) or 0.0) for x in campaigns), 2)
        total_sql = round(sum(float((x.get("forecast", {}) or {}).get("sql_est", 0.0) or 0.0) for x in campaigns), 2)

        run_payload = dict(base_run)
        run_payload.update(
            {
                "status": "passed",
                "outputs": {
                    "campaigns_backlog": str(backlog_path),
                    "campaigns_queue": str(queue_path),
                    "experiments": str(experiments_path),
                    "attribution_map": str(attribution_path),
                    "decision_log": str(decision_log_path),
                    "packets_dir": str(packets_dir),
                    "marketing_to_sales_handoff": str(handoff_path),
                },
                "stats": {
                    "campaigns_total": len(campaigns),
                    "launch_ready": len(launch_ready),
                    "watchlist": len(watchlist),
                    "hold": len(hold),
                    "forecast_clicks": total_clicks,
                    "forecast_mql": total_mql,
                    "forecast_sql": total_sql,
                },
            }
        )
        write_json(run_path, run_payload)

        state_payload = {
            "loop_state": "idle_ready",
            "mode": args.mode,
            "auto_launch": False,
            "last_run_status": "passed",
            "input_completeness": completeness,
            "snapshot_id": snapshot.get("snapshot_id"),
            "delta_counts": delta_counts,
            "last_incremental_run_at": generated_at,
            "campaigns_total": len(campaigns),
            "launch_ready": len(launch_ready),
            "watchlist": len(watchlist),
            "hold": len(hold),
            "forecast_clicks": total_clicks,
            "forecast_mql": total_mql,
            "forecast_sql": total_sql,
            "last_stage2_snapshot_id": stage2_run.get("input_sync", {}).get("snapshot_id"),
        }
        write_json(state_path, state_payload)

        summary.update(
            {
                "status": "passed",
                "campaigns_total": len(campaigns),
                "launch_ready": len(launch_ready),
                "watchlist": len(watchlist),
                "hold": len(hold),
                "forecast_sql": total_sql,
            }
        )
        if args.print_summary:
            print(json.dumps(summary, ensure_ascii=False))
        return 0

    except Exception as exc:
        fail_payload = {
            "generated_at": generated_at,
            "run_id": run_id,
            "capability": "marketing_launch_campaigns_stage3_shadow_v1",
            "status": "failed",
            "mode": args.mode,
            "auto_launch": False,
            "error": str(exc),
        }
        write_json(run_path, fail_payload)
        write_json(
            state_path,
            {
                "loop_state": "failed",
                "mode": args.mode,
                "auto_launch": False,
                "last_run_status": "failed",
                "last_incremental_run_at": generated_at,
                "error": str(exc),
            },
        )
        if args.print_summary:
            print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        raise


if __name__ == "__main__":
    sys.exit(main())
