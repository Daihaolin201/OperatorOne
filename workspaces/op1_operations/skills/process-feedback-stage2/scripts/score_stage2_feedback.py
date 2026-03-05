#!/usr/bin/env python3
"""Score Stage2 feedback items with evidence/confidence/impact weights."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from stage2_feedback_common import (
    kano_label_for,
    now_iso,
    owner_team_for_topic,
    parse_iso,
    read_json,
    read_json_or_yaml_like,
    resolve_repo_root,
    suggested_action_for,
    to_float,
    write_json,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Score Stage2 feedback")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root")
    p.add_argument(
        "--in-dir",
        default="workspaces/op1_operations/research/stage2_feedback",
        help="Input/output directory",
    )
    p.add_argument(
        "--weights",
        default="workspaces/op1_operations/config/feedback_priority_weights.v1.yaml",
        help="Weights config path",
    )
    p.add_argument(
        "--adapters-config",
        default="workspaces/op1_operations/config/feedback_source_adapters.v1.json",
        help="Adapters config path",
    )
    return p.parse_args()


def _lead_fit_map(repo_root: Path, fit_weights: Dict[str, float]) -> Dict[str, float]:
    path = repo_root / "workspaces/op1_sales/research/conversion/conversion_pipeline.latest.json"
    obj = read_json(path, default={}) or {}
    leads = obj.get("leads", []) if isinstance(obj.get("leads"), list) else []

    out: Dict[str, float] = {}
    for lead in leads:
        if not isinstance(lead, dict):
            continue
        lead_id = str(lead.get("lead_id") or "").strip()
        if not lead_id:
            continue
        band = str(lead.get("priority_band") or "unknown").strip() or "unknown"
        out[lead_id] = to_float(fit_weights.get(band), to_float(fit_weights.get("unknown"), 0.65))
    return out


def _source_reliability_map(adapters_cfg: Dict[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    adapters = adapters_cfg.get("adapters", []) if isinstance(adapters_cfg.get("adapters"), list) else []
    for ad in adapters:
        if not isinstance(ad, dict):
            continue
        aid = str(ad.get("id") or "").strip()
        if not aid:
            continue
        out[aid] = to_float(ad.get("source_reliability"), 0.75)
    return out


def _recency_weight(now_dt, seen_ts: str | None) -> float:
    dt = parse_iso(seen_ts)
    if dt is None:
        return 0.75
    age_days = max(0.0, (now_dt - dt).total_seconds() / 86400.0)
    if age_days <= 3:
        return 1.0
    if age_days <= 14:
        return max(0.7, 1.0 - ((age_days - 3.0) / 20.0))
    return 0.65


def _priority_tier(score: float, tiers: Dict[str, float]) -> str:
    if score >= to_float(tiers.get("P0"), 1.65):
        return "P0"
    if score >= to_float(tiers.get("P1"), 1.1):
        return "P1"
    if score >= to_float(tiers.get("P2"), 0.65):
        return "P2"
    return "P3"


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else resolve_repo_root(Path(__file__))
    in_dir = repo_root / args.in_dir

    dedup = read_json(in_dir / "feedback_dedup.latest.json", default={}) or {}
    items = dedup.get("items", []) if isinstance(dedup.get("items"), list) else []
    cluster = read_json(in_dir / "theme_clusters.latest.json", default={}) or {}
    item_to_theme = cluster.get("item_to_theme", {}) if isinstance(cluster.get("item_to_theme"), dict) else {}

    weights_cfg = read_json_or_yaml_like(repo_root / args.weights, default={}) or {}
    adapters_cfg = read_json(repo_root / args.adapters_config, default={}) or {}

    weights = weights_cfg.get("weights", {}) if isinstance(weights_cfg.get("weights"), dict) else {}
    topic_impact = weights_cfg.get("topic_impact", {}) if isinstance(weights_cfg.get("topic_impact"), dict) else {}
    effort_points = weights_cfg.get("effort_points", {}) if isinstance(weights_cfg.get("effort_points"), dict) else {}
    stage_impact = weights_cfg.get("stage_impact", {}) if isinstance(weights_cfg.get("stage_impact"), dict) else {}
    feedback_rev = (
        weights_cfg.get("feedback_type_revenue_weight", {})
        if isinstance(weights_cfg.get("feedback_type_revenue_weight"), dict)
        else {}
    )
    lead_fit_weights = (
        weights_cfg.get("lead_fit_multiplier", {})
        if isinstance(weights_cfg.get("lead_fit_multiplier"), dict)
        else {}
    )
    tiers = weights_cfg.get("priority_tiers", {}) if isinstance(weights_cfg.get("priority_tiers"), dict) else {}

    lead_fit_map = _lead_fit_map(repo_root, lead_fit_weights)
    source_reliability_map = _source_reliability_map(adapters_cfg)

    now_dt = parse_iso(now_iso())

    rows: List[Dict[str, Any]] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        item_id = str(item.get("feedback_item_id") or "")
        topic = str(item.get("topic") or "general")
        subtopic = str(item.get("subtopic") or "uncategorized")
        feedback_type = str(item.get("feedback_type") or "other")
        journey_stage = str(item.get("journey_stage") or "unknown")

        duplicate_count = max(1, int(item.get("duplicate_count") or 1))

        lead_ids = item.get("lead_ids") if isinstance(item.get("lead_ids"), list) else []
        if lead_ids:
            lead_fit = sum(to_float(lead_fit_map.get(str(lid), lead_fit_weights.get("unknown", 0.65)), 0.65) for lid in lead_ids) / max(
                1, len(lead_ids)
            )
        else:
            lead_fit = to_float(lead_fit_weights.get("unknown"), 0.65)

        src_mix = item.get("source_adapters") if isinstance(item.get("source_adapters"), dict) else {}
        src_total = sum(int(v) for v in src_mix.values())
        if src_mix and src_total > 0:
            src_rel = sum(to_float(source_reliability_map.get(str(k), 0.75), 0.75) * int(v) for k, v in src_mix.items()) / src_total
        else:
            src_rel = 0.75

        recency = _recency_weight(now_dt, str(item.get("last_seen") or "")) if now_dt else 0.8

        reach_raw = duplicate_count * lead_fit
        impact_raw = (
            to_float(topic_impact.get(topic), 1.0)
            * to_float(stage_impact.get(journey_stage), 1.0)
            * to_float(feedback_rev.get(feedback_type), 1.0)
        )

        confidence = (to_float(item.get("confidence_avg"), 0.7) * 0.6) + (src_rel * 0.4)
        evidence = to_float(item.get("evidence_weight_avg"), 0.7) * recency

        effort = to_float(effort_points.get(topic), to_float(effort_points.get("general"), 2.0))
        severity_component = max(0.1, to_float(item.get("severity_avg"), 2.0) / 5.0)
        urgency_component = max(0.1, to_float(item.get("urgency_avg"), 2.0) / 5.0)

        rice_core = (reach_raw * impact_raw * max(0.1, confidence) * max(0.1, evidence)) / max(0.5, effort)

        # Weighted blend for explainability and stability.
        weighted_component = (
            to_float(weights.get("reach"), 0.22) * reach_raw
            + to_float(weights.get("impact"), 0.24) * impact_raw
            + to_float(weights.get("confidence"), 0.16) * confidence
            + to_float(weights.get("evidence"), 0.14) * evidence
            + to_float(weights.get("severity"), 0.14) * severity_component
            + to_float(weights.get("urgency"), 0.1) * urgency_component
        )

        priority_score = round((rice_core * 0.65) + (weighted_component * 0.35), 6)
        priority_tier = _priority_tier(priority_score, tiers)

        theme_id = str(item_to_theme.get(item_id) or "")
        kano = kano_label_for(topic, feedback_type)

        rows.append(
            {
                "feedback_item_id": item_id,
                "theme_id": theme_id,
                "topic": topic,
                "subtopic": subtopic,
                "feedback_type": feedback_type,
                "journey_stage": journey_stage,
                "duplicate_count": duplicate_count,
                "unique_actor_count": int(item.get("unique_actor_count") or 0),
                "lead_ids": lead_ids,
                "lead_fit": round(lead_fit, 4),
                "source_reliability": round(src_rel, 4),
                "recency_weight": round(recency, 4),
                "reach_raw": round(reach_raw, 4),
                "impact_raw": round(impact_raw, 4),
                "confidence": round(confidence, 4),
                "evidence": round(evidence, 4),
                "effort_points": round(effort, 4),
                "severity_component": round(severity_component, 4),
                "urgency_component": round(urgency_component, 4),
                "rice_core": round(rice_core, 6),
                "weighted_component": round(weighted_component, 6),
                "priority_score": priority_score,
                "priority_tier": priority_tier,
                "kano_label": kano,
                "owner_team": owner_team_for_topic(topic),
                "recommended_action": suggested_action_for(topic, subtopic, feedback_type),
                "evidence_examples": item.get("raw_text_examples", [])[:3],
                "first_seen": item.get("first_seen"),
                "last_seen": item.get("last_seen"),
            }
        )

    rows = sorted(rows, key=lambda r: (to_float(r.get("priority_score"), 0.0), int(r.get("duplicate_count") or 0)), reverse=True)

    tier_counts: Dict[str, int] = {}
    for row in rows:
        tier = str(row.get("priority_tier") or "P3")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    report = {
        "generated_at": now_iso(),
        "item_count": len(rows),
        "tier_counts": tier_counts,
        "top_item": rows[0] if rows else None,
    }

    write_jsonl(in_dir / "feedback_scored.latest.jsonl", rows)
    write_json(in_dir / "feedback_scoring_report.latest.json", report)

    print({"item_count": len(rows), "tier_counts": tier_counts})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
