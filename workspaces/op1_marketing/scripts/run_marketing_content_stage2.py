#!/usr/bin/env python3
"""
Stage2 capability: Publish content (shadow/review only).

This stage converts Stage1 SEO experiment outputs into publish-ready content packages,
without automatic publishing.

Default mode is shadow:
- Generates drafts and channel snippets
- Runs quality gates
- Produces review queue
- Updates marketing_to_sales handoff
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


REQUIRED_INPUTS = [
    {"id": "stage1_run", "path": "research/stage1_marketing_seo/run.latest.json"},
    {"id": "stage1_context_index", "path": "research/stage1_marketing_seo/context_index.latest.json"},
    {"id": "stage1_backlog", "path": "research/stage1_marketing_seo/experiments.backlog.latest.json"},
    {"id": "stage1_queue", "path": "research/stage1_marketing_seo/experiments.queue.latest.json"},
    {"id": "stage1_scoreboard", "path": "research/stage1_marketing_seo/scoreboard.latest.json"},
    {"id": "product_to_marketing_handoff", "path": "../../handoffs/product_to_marketing.json"},
]


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


def titleize_keyword(keyword: str) -> str:
    return " ".join([w.capitalize() for w in (keyword or "").split() if w])


def short_text(text: str, limit: int = 120) -> str:
    s = (text or "").strip()
    if len(s) <= limit:
        return s
    return s[: max(0, limit - 1)].rstrip() + "…"


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9]+", (text or "").lower())


def count_keyword_occurrences(text: str, keyword: str) -> int:
    t = (text or "").lower()
    k = (keyword or "").lower().strip()
    if not k:
        return 0
    return len(re.findall(rf"\b{re.escape(k)}\b", t))


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
        rec = {
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


def copy_mirror(root: Path, mirror_dir: Path, records: List[Dict[str, Any]]) -> None:
    if mirror_dir.exists():
        shutil.rmtree(mirror_dir)
    mirror_dir.mkdir(parents=True, exist_ok=True)

    for rec in records:
        if not rec.get("exists"):
            continue
        src = Path(rec["abs"])
        rel = safe_slug(rec["id"])
        dst = mirror_dir / rel / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def snapshot_id_from_records(records: List[Dict[str, Any]]) -> str:
    material = "\n".join(
        f"{r.get('id')}|{r.get('sha256', '')}|{r.get('size', '')}|{r.get('mtime', '')}" for r in records
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    ts = dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"stage2snap_{ts}_{digest}"


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


def snapshot_signature(snapshot_id: str) -> str:
    parts = (snapshot_id or "").split("_")
    if parts:
        return parts[-1]
    return ""


def build_prior_manual_decisions(
    previous_backlog: Dict[str, Any],
    current_snapshot_id: str,
) -> Dict[str, Dict[str, Any]]:
    if not isinstance(previous_backlog, dict):
        return {}

    prev_sig = snapshot_signature(previous_backlog.get("snapshot_id", ""))
    curr_sig = snapshot_signature(current_snapshot_id)
    if not prev_sig or prev_sig != curr_sig:
        return {}

    out: Dict[str, Dict[str, Any]] = {}
    for item in (previous_backlog.get("items", []) or []):
        content_id = item.get("content_id")
        state = item.get("queue_state")
        if not content_id or state not in {"approved", "needs_revision"}:
            continue
        out[content_id] = {
            "queue_state": state,
            "review_decision": item.get("review_decision"),
        }
    return out


def required_outputs_exist(stage_dir: Path) -> bool:
    expected = [
        stage_dir / "run.latest.json",
        stage_dir / "state.latest.json",
        stage_dir / "content.backlog.latest.json",
        stage_dir / "publish.queue.latest.json",
        stage_dir / "qa.latest.json",
        stage_dir / "decision_log.latest.md",
    ]
    return all(p.exists() for p in expected)


def confidence_bonus(value: str) -> float:
    return {"high": 4.0, "medium": 2.0, "low": 0.0}.get((value or "").lower(), 0.0)


def intent_bonus(value: str) -> float:
    return {"BOFU": 6.0, "MOFU": 3.0, "TOFU": 1.0}.get((value or "").upper(), 0.0)


def recommended_format(intent: str) -> str:
    v = (intent or "").upper()
    if v == "TOFU":
        return "educational-guide"
    if v == "MOFU":
        return "playbook-or-template"
    return "comparison-or-usecase"


def generate_title_options(keyword: str, context: Dict[str, Any], intent: str) -> List[str]:
    kw = titleize_keyword(keyword)
    problem = short_text(context.get("problem_statement", ""), 70)
    value = short_text(context.get("value_proposition", ""), 70)

    if (intent or "").upper() == "BOFU":
        return [
            f"{kw}: Practical buyer guide for teams evaluating alternatives",
            f"{kw} vs manual process: what actually changes in operations",
            f"{kw} — decision framework for operators ({short_text(context.get('icp', ''), 40)})",
        ]
    if (intent or "").upper() == "MOFU":
        return [
            f"{kw}: step-by-step playbook you can apply this week",
            f"How to fix {problem.lower()} with a lightweight workflow",
            f"{kw}: templates, checklist, and execution plan",
        ]
    return [
        f"{kw}: foundational guide for teams starting from manual workflows",
        f"What to know before changing {problem.lower()}",
        f"{kw}: definitions, examples, and next steps",
    ]


def render_draft_markdown(item: Dict[str, Any], context: Dict[str, Any], experiment: Dict[str, Any], generated_at: str) -> str:
    title = item.get("selected_title") or (item.get("title_options") or ["Untitled"])[0]
    icp = context.get("icp", "")
    problem = context.get("problem_statement", "")
    value = context.get("value_proposition", "")
    proof_points = context.get("proof_points", []) or []
    proof_points = proof_points[:4]
    cta = item.get("cta") or "Book a short walkthrough"
    keyword = item.get("primary_keyword", "")

    if not proof_points:
        proof_points = ["Reference operational evidence from product and discovery artifacts."]

    proof_md = "\n".join([f"- {p}" for p in proof_points])

    hypotheses = experiment.get("hypothesis", "")
    source_ptrs = experiment.get("source_pointers", []) or context.get("source_files", []) or []
    source_md = "\n".join([f"- `{p}`" for p in source_ptrs]) if source_ptrs else "- (none)"

    blog = f"""---
content_id: {item.get('content_id')}
experiment_id: {item.get('experiment_id')}
context_id: {item.get('context_id')}
intent: {item.get('intent')}
primary_keyword: {keyword}
mode: {item.get('mode')}
status: draft
generated_at: {generated_at}
---

# {title}

## Who this is for
{icp}

## Problem to solve
{problem}

## What a better workflow looks like
{value}

## Evidence and operational signals
{proof_md}

## Recommended approach
1. Identify where the manual process breaks most often.
2. Implement a lightweight, testable workflow around one high-friction step.
3. Measure quality of outcomes (speed, consistency, and conversion intent) before scaling.

## Why this angle was selected
{hypotheses}

## CTA
{cta}

## Channel snippets
- **LinkedIn hook**: We mapped "{keyword}" to a repeatable workflow and found the same bottleneck across operators.
- **Email intro**: If your team is still handling this manually, here’s a practical plan to de-risk the change.
- **Sales enablement note**: Use this asset to answer early-stage objections and route high-intent conversations.

## Source pointers
{source_md}
"""
    return blog


def run_quality_gates(draft_text: str, item: Dict[str, Any], context: Dict[str, Any], min_score: float) -> Dict[str, Any]:
    words = tokenize(draft_text)
    word_count = len(words)
    keyword = item.get("primary_keyword", "")
    kw_hits = count_keyword_occurrences(draft_text, keyword)
    kw_density = (kw_hits / max(1, word_count)) * 100.0

    proof_count = len(context.get("proof_points", []) or [])
    source_count = len(item.get("source_pointers", []) or [])

    claim_flags = []
    risky_claim_terms = ["guarantee", "instant", "overnight", "100%", "no effort"]
    low_text = draft_text.lower()
    for term in risky_claim_terms:
        if term in low_text:
            claim_flags.append(term)

    checks = {
        "word_count_ok": word_count >= 220,
        "source_traceability_ok": source_count >= 1,
        "evidence_depth_ok": proof_count >= 2,
        "keyword_density_ok": kw_density <= 3.0,
        "policy_claims_ok": len(claim_flags) == 0,
        "score_floor_ok": float(item.get("overall_score", 0.0)) >= float(min_score),
    }

    score = 0.0
    score += 20.0 if checks["word_count_ok"] else 0.0
    score += 20.0 if checks["source_traceability_ok"] else 0.0
    score += 20.0 if checks["evidence_depth_ok"] else 0.0
    score += 20.0 if checks["keyword_density_ok"] else 0.0
    score += 10.0 if checks["policy_claims_ok"] else 0.0
    score += 10.0 if checks["score_floor_ok"] else 0.0

    result = "pass" if all(checks.values()) else "revise"

    return {
        "result": result,
        "quality_score": round(score, 2),
        "word_count": word_count,
        "keyword_hits": kw_hits,
        "keyword_density_pct": round(kw_density, 3),
        "risk_flags": claim_flags,
        "checks": checks,
    }


def select_candidates(
    queue_payload: Dict[str, Any],
    backlog_by_id: Dict[str, Dict[str, Any]],
    contexts_by_id: Dict[str, Dict[str, Any]],
    mode: str,
    max_items: int,
    include_hold: bool,
) -> List[Dict[str, Any]]:
    queue = queue_payload.get("queue", {}) or {}
    ready = queue.get("ready", []) or []
    hold = queue.get("hold", []) or []

    ordered: List[Tuple[str, Dict[str, Any]]] = [("ready", x) for x in ready]
    if include_hold:
        ordered.extend(("hold", x) for x in hold)

    ordered.sort(key=lambda t: (0 if t[0] == "ready" else 1, -float(t[1].get("overall_score", 0.0))))

    selected: List[Dict[str, Any]] = []
    seen_keyword = set()

    for bucket, row in ordered:
        experiment_id = row.get("experiment_id")
        context_id = row.get("context_id")
        keyword = (row.get("keyword") or "").strip()

        if not experiment_id or not context_id or not keyword:
            continue

        exp = backlog_by_id.get(experiment_id)
        ctx = contexts_by_id.get(context_id)
        if not exp or not ctx:
            continue

        kw_key = keyword.lower()
        if kw_key in seen_keyword:
            continue
        seen_keyword.add(kw_key)

        priority = (
            float(row.get("overall_score", 0.0))
            + confidence_bonus(row.get("confidence", ""))
            + intent_bonus(row.get("intent", ""))
        )

        cta = ""
        if isinstance(ctx.get("cta"), dict):
            cta = (ctx.get("cta") or {}).get("label") or ""
        if not cta:
            change = exp.get("change", {}) if isinstance(exp.get("change"), dict) else {}
            cta = change.get("cta_variant_a") or change.get("cta_variant_b") or "Book a short walkthrough"

        titles = generate_title_options(keyword, ctx, row.get("intent", "TOFU"))

        item = {
            "content_id": f"cnt_{safe_slug(experiment_id)}",
            "experiment_id": experiment_id,
            "context_id": context_id,
            "source_bucket": bucket,
            "mode": mode,
            "primary_keyword": keyword,
            "intent": row.get("intent", "TOFU"),
            "overall_score": float(row.get("overall_score", 0.0)),
            "confidence": row.get("confidence", "low"),
            "priority_score": round(priority, 2),
            "recommended_format": recommended_format(row.get("intent", "TOFU")),
            "title_options": titles,
            "selected_title": titles[0] if titles else titleize_keyword(keyword),
            "cta": cta,
            "source_pointers": exp.get("source_pointers", []) or ctx.get("source_files", []) or [],
            "stage_status": "drafted",
        }
        selected.append(item)

        if len(selected) >= max_items:
            break

    return selected


def write_decision_log(
    path: Path,
    generated_at: str,
    snapshot_id: str,
    selected_items: List[Dict[str, Any]],
    review_ready: List[Dict[str, Any]],
    needs_revision: List[Dict[str, Any]],
    approved: List[Dict[str, Any]],
) -> None:
    lines = [
        f"# Stage2 Content Publish Decision Log — {dt.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
        "",
        f"- Generated at: {generated_at}",
        f"- Input snapshot: `{snapshot_id}`",
        f"- Candidates selected: **{len(selected_items)}**",
        f"- Approved: **{len(approved)}**",
        f"- Review ready: **{len(review_ready)}**",
        f"- Needs revision: **{len(needs_revision)}**",
        "",
        "## Approved",
    ]

    if approved:
        for item in approved[:20]:
            lines.append(
                f"- `{item.get('content_id')}` | {item.get('primary_keyword')} | priority={item.get('priority_score')} | score={item.get('overall_score')}"
            )
    else:
        lines.append("- (none)")

    lines += ["", "## Review Ready"]
    if review_ready:
        for item in review_ready[:20]:
            lines.append(
                f"- `{item.get('content_id')}` | {item.get('primary_keyword')} | priority={item.get('priority_score')} | score={item.get('overall_score')}"
            )
    else:
        lines.append("- (none)")

    lines += ["", "## Needs Revision"]
    if needs_revision:
        for item in needs_revision[:20]:
            lines.append(
                f"- `{item.get('content_id')}` | {item.get('primary_keyword')} | priority={item.get('priority_score')} | score={item.get('overall_score')}"
            )
    else:
        lines.append("- (none)")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_marketing_to_sales_handoff(
    root: Path,
    generated_at: str,
    review_ready: List[Dict[str, Any]],
    approved: List[Dict[str, Any]],
    all_items: List[Dict[str, Any]],
) -> Path:
    handoff_path = (root / "../../handoffs/marketing_to_sales.json").resolve()
    existing = read_json(handoff_path, default={})
    if not isinstance(existing, dict):
        existing = {}

    content_assets = []
    seo_targets = []

    for item in all_items:
        content_assets.append(
            {
                "content_id": item.get("content_id"),
                "experiment_id": item.get("experiment_id"),
                "keyword": item.get("primary_keyword"),
                "intent": item.get("intent"),
                "status": item.get("queue_state", "needs_revision"),
                "format": item.get("recommended_format"),
                "title": item.get("selected_title"),
                "draft_path": item.get("draft_path"),
            }
        )
        seo_targets.append(
            {
                "keyword": item.get("primary_keyword"),
                "intent": item.get("intent"),
                "priority_score": item.get("priority_score"),
                "status": item.get("queue_state", "needs_revision"),
            }
        )

    campaigns = [
        {
            "campaign_id": f"stage2-shadow-{dt.datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "name": "Stage2 content publish shadow batch",
            "status": "review_approved" if approved else "review_only",
            "auto_publish": False,
            "assets_total": len(all_items),
            "assets_approved": len(approved),
            "assets_review_ready": len(review_ready),
            "generated_at": generated_at,
        }
    ]

    updated = {
        "generated_at": generated_at,
        "campaigns": campaigns,
        "content_assets": content_assets,
        "seo_targets": seo_targets,
        "lead_signals": {
            "top_channels": ["organic_search", "linkedin", "email_nurture"],
            "estimated_weekly_leads": max(0, len(approved) * 2),
            "note": "Shadow estimate from manually approved assets only; requires live distribution and attribution calibration.",
        },
        "offer_context": {
            "pricing": existing.get("offer_context", {}).get("pricing", ""),
            "trial_policy": existing.get("offer_context", {}).get("trial_policy", ""),
        },
    }

    write_json(handoff_path, updated)
    return handoff_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage2 content publish pipeline (no auto publish)")
    parser.add_argument("--root-dir", default=None, help="Workspace root (defaults to script parent)")
    parser.add_argument("--stage-dir", default=None, help="Stage2 output directory")
    parser.add_argument("--mode", choices=["shadow", "review"], default="shadow")
    parser.add_argument("--force", action="store_true", help="Force recompute")
    parser.add_argument("--max-items", type=int, default=12, help="Max content items to generate")
    parser.add_argument("--include-hold", action="store_true", help="Include hold queue in candidate selection")
    parser.add_argument("--min-score", type=float, default=78.0, help="Minimum Stage1 score for pass-grade quality gate")
    parser.add_argument("--print-summary", action="store_true", help="Print compact JSON summary")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    script_dir = Path(__file__).resolve().parent
    root = Path(args.root_dir).resolve() if args.root_dir else script_dir.parent.resolve()
    stage_dir = Path(args.stage_dir).resolve() if args.stage_dir else (root / "research/stage2_content_publish").resolve()

    input_dir = stage_dir / "input"
    snapshot_path = input_dir / "stage1_snapshot.latest.json"
    delta_path = input_dir / "delta.latest.json"
    mirror_dir = input_dir / "mirror.latest"

    run_path = stage_dir / "run.latest.json"
    state_path = stage_dir / "state.latest.json"
    backlog_path = stage_dir / "content.backlog.latest.json"
    queue_path = stage_dir / "publish.queue.latest.json"
    qa_path = stage_dir / "qa.latest.json"
    decision_log_path = stage_dir / "decision_log.latest.md"
    drafts_dir = stage_dir / "drafts"

    generated_at = now_iso()
    run_id = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    previous_snapshot = read_json(snapshot_path, default={}) or {}
    previous_state = read_json(state_path, default={}) or {}
    previous_backlog = read_json(backlog_path, default={}) or {}

    summary: Dict[str, Any] = {
        "generated_at": generated_at,
        "run_id": run_id,
        "stage_dir": str(stage_dir),
    }

    try:
        records, completeness = resolve_inputs(root)
        copy_mirror(root, mirror_dir, records)

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
            "capability": "marketing_publish_content_stage2_shadow_v1",
            "mode": args.mode,
            "auto_publish": False,
            "publish_mode": "disabled",
            "input_sync": {
                "snapshot_id": snapshot.get("snapshot_id"),
                "completeness": completeness,
                "delta_counts": delta_counts,
                "requirements": records,
            },
        }

        if completeness.get("ratio", 0.0) < 1.0:
            reason = "blocked_input_incomplete"

            write_json(
                backlog_path,
                {
                    "generated_at": generated_at,
                    "status": reason,
                    "snapshot_id": snapshot.get("snapshot_id"),
                    "items": [],
                },
            )
            write_json(
                queue_path,
                {
                    "generated_at": generated_at,
                    "status": reason,
                    "auto_publish": False,
                    "queue": {"approved": [], "review_ready": [], "needs_revision": [], "blocked": []},
                    "counts": {"approved": 0, "review_ready": 0, "needs_revision": 0, "blocked": 0},
                },
            )
            write_json(
                qa_path,
                {
                    "generated_at": generated_at,
                    "status": reason,
                    "items": [],
                    "summary": {"pass": 0, "revise": 0},
                },
            )
            decision_log_path.write_text(
                "# Stage2 Content Publish Decision Log\n\n- Status: blocked_input_incomplete\n",
                encoding="utf-8",
            )

            run_payload = dict(base_run)
            run_payload.update({"status": reason})
            write_json(run_path, run_payload)

            state_payload = {
                "loop_state": reason,
                "mode": args.mode,
                "auto_publish": False,
                "last_run_status": reason,
                "input_completeness": completeness,
                "snapshot_id": snapshot.get("snapshot_id"),
                "delta_counts": delta_counts,
                "last_incremental_run_at": generated_at,
            }
            write_json(state_path, state_payload)

            summary.update({"status": reason})
            if args.print_summary:
                print(json.dumps(summary, ensure_ascii=False))
            return 0

        if not should_recompute:
            run_payload = dict(base_run)
            run_payload.update(
                {
                    "status": "no_change",
                    "note": "Input snapshot unchanged; Stage2 recompute skipped.",
                }
            )
            write_json(run_path, run_payload)

            state_payload = {
                "loop_state": "idle_no_change",
                "mode": args.mode,
                "auto_publish": False,
                "last_run_status": "no_change",
                "input_completeness": completeness,
                "snapshot_id": snapshot.get("snapshot_id"),
                "delta_counts": delta_counts,
                "last_incremental_run_at": generated_at,
                "active_items": int(previous_state.get("active_items", 0)),
                "approved": int(previous_state.get("approved", 0)),
                "review_ready": int(previous_state.get("review_ready", 0)),
                "needs_revision": int(previous_state.get("needs_revision", 0)),
            }
            write_json(state_path, state_payload)

            summary.update({"status": "no_change"})
            if args.print_summary:
                print(json.dumps(summary, ensure_ascii=False))
            return 0

        stage1_run = read_json((root / "research/stage1_marketing_seo/run.latest.json").resolve(), default={}) or {}
        stage1_status = stage1_run.get("status")
        if stage1_status not in {"passed", "no_change"}:
            reason = "blocked_upstream_stage1_unhealthy"
            run_payload = dict(base_run)
            run_payload.update(
                {
                    "status": reason,
                    "upstream_status": stage1_status,
                    "note": "Stage1 run is not healthy; refusing to generate Stage2 content.",
                }
            )
            write_json(run_path, run_payload)
            write_json(
                state_path,
                {
                    "loop_state": reason,
                    "mode": args.mode,
                    "auto_publish": False,
                    "last_run_status": reason,
                    "upstream_status": stage1_status,
                    "last_incremental_run_at": generated_at,
                },
            )
            summary.update({"status": reason, "upstream_status": stage1_status})
            if args.print_summary:
                print(json.dumps(summary, ensure_ascii=False))
            return 0

        queue_payload = read_json((root / "research/stage1_marketing_seo/experiments.queue.latest.json").resolve(), default={}) or {}
        backlog_payload = read_json((root / "research/stage1_marketing_seo/experiments.backlog.latest.json").resolve(), default={}) or {}
        context_payload = read_json((root / "research/stage1_marketing_seo/context_index.latest.json").resolve(), default={}) or {}
        scoreboard_payload = read_json((root / "research/stage1_marketing_seo/scoreboard.latest.json").resolve(), default={}) or {}

        backlog_by_id = {x.get("experiment_id"): x for x in (backlog_payload.get("experiments", []) or []) if x.get("experiment_id")}
        contexts_by_id = {x.get("context_id"): x for x in (context_payload.get("contexts", []) or []) if x.get("context_id")}

        selected_items = select_candidates(
            queue_payload=queue_payload,
            backlog_by_id=backlog_by_id,
            contexts_by_id=contexts_by_id,
            mode=args.mode,
            max_items=max(1, args.max_items),
            include_hold=bool(args.include_hold),
        )

        prior_manual_decisions = build_prior_manual_decisions(
            previous_backlog=previous_backlog,
            current_snapshot_id=snapshot.get("snapshot_id", ""),
        )

        # Keep drafts directory deterministic for the current snapshot.
        # (Avoid stale drafts from previous runs with different max-items/include-hold settings.)
        if drafts_dir.exists():
            shutil.rmtree(drafts_dir)
        drafts_dir.mkdir(parents=True, exist_ok=True)

        qa_items: List[Dict[str, Any]] = []
        approved: List[Dict[str, Any]] = []
        review_ready: List[Dict[str, Any]] = []
        needs_revision: List[Dict[str, Any]] = []

        for item in selected_items:
            exp = backlog_by_id.get(item.get("experiment_id"), {})
            ctx = contexts_by_id.get(item.get("context_id"), {})

            draft_md = render_draft_markdown(item=item, context=ctx, experiment=exp, generated_at=generated_at)
            draft_path = drafts_dir / f"{item.get('content_id')}.md"
            draft_path.write_text(draft_md, encoding="utf-8")

            qa = run_quality_gates(draft_md, item=item, context=ctx, min_score=args.min_score)
            item["qa"] = qa
            item["queue_state"] = "review_ready" if qa.get("result") == "pass" else "needs_revision"

            prior = prior_manual_decisions.get(item.get("content_id", ""), {})
            prior_state = prior.get("queue_state")
            if prior_state == "approved" and qa.get("result") == "pass":
                item["queue_state"] = "approved"
                if prior.get("review_decision"):
                    item["review_decision"] = prior.get("review_decision")
            elif prior_state == "needs_revision":
                item["queue_state"] = "needs_revision"
                if prior.get("review_decision"):
                    item["review_decision"] = prior.get("review_decision")

            item["draft_path"] = relative_path(draft_path, root)

            qa_entry = {
                "content_id": item.get("content_id"),
                "experiment_id": item.get("experiment_id"),
                "result": qa.get("result"),
                "quality_score": qa.get("quality_score"),
                "checks": qa.get("checks"),
                "risk_flags": qa.get("risk_flags"),
            }
            qa_items.append(qa_entry)

            if item["queue_state"] == "approved":
                approved.append(item)
            elif item["queue_state"] == "review_ready":
                review_ready.append(item)
            else:
                needs_revision.append(item)

        selected_items.sort(key=lambda x: (-float(x.get("priority_score", 0.0)), x.get("content_id", "")))
        approved.sort(key=lambda x: (-float(x.get("priority_score", 0.0)), x.get("content_id", "")))
        review_ready.sort(key=lambda x: (-float(x.get("priority_score", 0.0)), x.get("content_id", "")))
        needs_revision.sort(key=lambda x: (-float(x.get("priority_score", 0.0)), x.get("content_id", "")))

        backlog_payload_out = {
            "generated_at": generated_at,
            "status": "ok",
            "snapshot_id": snapshot.get("snapshot_id"),
            "stage1_snapshot_id": queue_payload.get("snapshot_id"),
            "mode": args.mode,
            "auto_publish": False,
            "items": selected_items,
            "summary": {
                "selected": len(selected_items),
                "approved": len(approved),
                "review_ready": len(review_ready),
                "needs_revision": len(needs_revision),
                "max_items": max(1, args.max_items),
                "include_hold": bool(args.include_hold),
                "min_score": float(args.min_score),
            },
        }
        write_json(backlog_path, backlog_payload_out)

        queue_payload_out = {
            "generated_at": generated_at,
            "status": "ok",
            "mode": args.mode,
            "auto_publish": False,
            "queue": {
                "approved": approved,
                "review_ready": review_ready,
                "needs_revision": needs_revision,
                "blocked": [],
            },
            "counts": {
                "approved": len(approved),
                "review_ready": len(review_ready),
                "needs_revision": len(needs_revision),
                "blocked": 0,
            },
        }
        write_json(queue_path, queue_payload_out)

        qa_payload_out = {
            "generated_at": generated_at,
            "status": "ok",
            "checks_version": "content_quality_v1",
            "items": qa_items,
            "summary": {
                "pass": sum(1 for x in qa_items if x.get("result") == "pass"),
                "revise": sum(1 for x in qa_items if x.get("result") != "pass"),
                "avg_quality_score": round(
                    (sum(float(x.get("quality_score", 0.0)) for x in qa_items) / max(1, len(qa_items))),
                    2,
                ),
            },
        }
        write_json(qa_path, qa_payload_out)

        write_decision_log(
            path=decision_log_path,
            generated_at=generated_at,
            snapshot_id=snapshot.get("snapshot_id", ""),
            selected_items=selected_items,
            review_ready=review_ready,
            needs_revision=needs_revision,
            approved=approved,
        )

        handoff_path = update_marketing_to_sales_handoff(
            root=root,
            generated_at=generated_at,
            review_ready=review_ready,
            approved=approved,
            all_items=selected_items,
        )

        run_payload = dict(base_run)
        run_payload.update(
            {
                "status": "passed",
                "outputs": {
                    "content_backlog": str(backlog_path),
                    "publish_queue": str(queue_path),
                    "qa": str(qa_path),
                    "decision_log": str(decision_log_path),
                    "drafts_dir": str(drafts_dir),
                    "marketing_to_sales_handoff": str(handoff_path),
                },
                "stats": {
                    "selected": len(selected_items),
                    "approved": len(approved),
                    "review_ready": len(review_ready),
                    "needs_revision": len(needs_revision),
                    "avg_quality_score": qa_payload_out["summary"]["avg_quality_score"],
                },
            }
        )
        write_json(run_path, run_payload)

        state_payload = {
            "loop_state": "idle_ready",
            "mode": args.mode,
            "auto_publish": False,
            "last_run_status": "passed",
            "input_completeness": completeness,
            "snapshot_id": snapshot.get("snapshot_id"),
            "delta_counts": delta_counts,
            "last_incremental_run_at": generated_at,
            "active_items": len(selected_items),
            "approved": len(approved),
            "review_ready": len(review_ready),
            "needs_revision": len(needs_revision),
            "last_stage1_snapshot_id": queue_payload.get("snapshot_id"),
        }
        write_json(state_path, state_payload)

        summary.update(
            {
                "status": "passed",
                "selected": len(selected_items),
                "approved": len(approved),
                "review_ready": len(review_ready),
                "needs_revision": len(needs_revision),
                "avg_quality_score": qa_payload_out["summary"]["avg_quality_score"],
            }
        )
        if args.print_summary:
            print(json.dumps(summary, ensure_ascii=False))
        return 0

    except Exception as exc:
        fail_payload = {
            "generated_at": generated_at,
            "run_id": run_id,
            "capability": "marketing_publish_content_stage2_shadow_v1",
            "status": "failed",
            "mode": args.mode,
            "auto_publish": False,
            "error": str(exc),
        }
        write_json(run_path, fail_payload)
        write_json(
            state_path,
            {
                "loop_state": "failed",
                "mode": args.mode,
                "auto_publish": False,
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
