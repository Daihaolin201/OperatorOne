#!/usr/bin/env python3
"""Build Stage3 experiment backlog and hypothesis registry from OST + Stage2 queue."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from stage3_iteration_common import (
    now_iso,
    read_json,
    read_json_or_yaml_like,
    resolve_repo_root,
    stable_hash,
    to_float,
    to_int,
    write_json,
    write_jsonl,
)


PRIMARY_METRIC_BY_TOPIC = {
    "onboarding": "visit_to_signup_rate",
    "pricing": "signup_to_paid_rate",
    "trust": "signup_to_paid_rate",
    "retention": "signup_to_paid_rate",
    "integration": "visit_to_signup_rate",
    "support": "visit_to_signup_rate",
    "billing": "net_new_mrr",
    "performance": "visit_to_signup_rate",
    "general": "signup_to_paid_rate",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Stage3 experiment backlog")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root")
    p.add_argument(
        "--in-dir",
        default="workspaces/op1_operations/research/stage3_product_iteration",
        help="Input/output directory",
    )
    p.add_argument(
        "--weights",
        default="workspaces/op1_operations/config/stage3_iteration_weights.v1.yaml",
        help="Iteration weights path",
    )
    p.add_argument(
        "--guardrails",
        default="workspaces/op1_operations/config/stage3_metric_guardrails.v1.yaml",
        help="Guardrails config path",
    )
    p.add_argument(
        "--decision-policy",
        default="workspaces/op1_operations/contracts/stage3_decision_policy.v1.json",
        help="Decision policy path",
    )
    p.add_argument(
        "--experiment-contract",
        default="workspaces/op1_operations/contracts/stage3_experiment_contract.v1.json",
        help="Experiment contract path",
    )
    return p.parse_args()


def _effort_band(topic: str) -> str:
    if topic in {"pricing", "support", "retention"}:
        return "low"
    if topic in {"onboarding", "integration", "billing", "trust"}:
        return "medium"
    return "high"


def _risk_band(topic: str) -> str:
    if topic in {"trust", "billing", "performance"}:
        return "high"
    if topic in {"onboarding", "integration", "pricing"}:
        return "medium"
    return "low"


def _normalize(value: float, max_value: float, fallback: float = 0.0) -> float:
    if max_value <= 0:
        return fallback
    return max(0.0, min(1.0, value / max_value))


def _targeting(iter_inputs: Dict[str, Any]) -> Dict[str, Any]:
    product_ctx = iter_inputs.get("product_context", {}) if isinstance(iter_inputs.get("product_context"), dict) else {}
    seg = ((product_ctx.get("selected_opportunity_context") or {}) if isinstance(product_ctx.get("selected_opportunity_context"), dict) else {}).get(
        "target_segment"
    )

    return {
        "segment": seg if isinstance(seg, dict) else {"role": "unknown", "company_size": "unknown", "industry": "unknown"},
        "country": "ALL",
        "device": "all",
        "traffic_scope": "eligible_new_and_returning",
    }


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else resolve_repo_root(Path(__file__))
    in_dir = repo_root / args.in_dir

    iter_inputs = read_json(in_dir / "iteration_inputs.latest.json", default={}) or {}
    ost = read_json(in_dir / "opportunity_solution_tree.latest.json", default={}) or {}

    weights_cfg = read_json_or_yaml_like(repo_root / args.weights, default={}) or {}
    guardrails_cfg = read_json_or_yaml_like(repo_root / args.guardrails, default={}) or {}
    decision_policy = read_json(repo_root / args.decision_policy, default={}) or {}
    contract = read_json(repo_root / args.experiment_contract, default={}) or {}

    queue = iter_inputs.get("top_feedback_queue", []) if isinstance(iter_inputs.get("top_feedback_queue"), list) else []
    opportunities = ost.get("opportunities", []) if isinstance(ost.get("opportunities"), list) else []

    opp_by_topic: Dict[str, Dict[str, Any]] = {}
    for opp in opportunities:
        if isinstance(opp, dict):
            opp_by_topic[str(opp.get("topic") or "general")] = opp

    weights = weights_cfg.get("weights", {}) if isinstance(weights_cfg.get("weights"), dict) else {}
    effort_map = weights_cfg.get("effort_points", {}) if isinstance(weights_cfg.get("effort_points"), dict) else {}
    risk_map = weights_cfg.get("risk_levels", {}) if isinstance(weights_cfg.get("risk_levels"), dict) else {}
    wip_limits = weights_cfg.get("wip_limits", {}) if isinstance(weights_cfg.get("wip_limits"), dict) else {}

    guardrail_metrics = guardrails_cfg.get("guardrail_metrics", {}) if isinstance(guardrails_cfg.get("guardrail_metrics"), dict) else {}
    min_runtime = to_int(((guardrails_cfg.get("evaluation_windows") or {}).get("minimum_runtime_days")), 7)

    max_expected_mrr = max((to_float(r.get("expected_mrr_delta_30d"), 0.0) for r in queue), default=0.0)
    max_expected_conversion = max(
        (to_float(r.get("expected_signup_delta_30d"), 0.0) + to_float(r.get("expected_paid_delta_30d"), 0.0) for r in queue),
        default=0.0,
    )

    backlog: List[Dict[str, Any]] = []
    hypotheses: List[Dict[str, Any]] = []

    default_targeting = _targeting(iter_inputs)

    for rank, row in enumerate(queue[:20], start=1):
        topic = str(row.get("topic") or "general")
        subtopic = str(row.get("subtopic") or "uncategorized")
        item_id = str(row.get("feedback_item_id") or "")
        opp = opp_by_topic.get(topic, {})

        experiment_id = "exp3_" + stable_hash([item_id, topic, subtopic], 14)
        hypothesis_id = "hyp3_" + stable_hash([experiment_id, rank], 14)

        effort_band = _effort_band(topic)
        risk_band = _risk_band(topic)

        effort_points = to_float(effort_map.get(effort_band), 2.0)
        risk_points = to_float(risk_map.get(risk_band), 2.0)

        impact_mrr_norm = _normalize(to_float(row.get("expected_mrr_delta_30d"), 0.0), max_expected_mrr, fallback=0.0)
        conv_delta = to_float(row.get("expected_signup_delta_30d"), 0.0) + to_float(row.get("expected_paid_delta_30d"), 0.0)
        impact_conv_norm = _normalize(conv_delta, max_expected_conversion, fallback=0.0)

        confidence = max(0.0, min(1.0, to_float(row.get("priority_score"), 0.0) / 2.0))
        urgency = 1.0 if str(row.get("priority_tier") or "") in {"P0", "P1"} else 0.6

        weighted_score = (
            to_float(weights.get("impact_mrr"), 0.3) * impact_mrr_norm
            + to_float(weights.get("impact_conversion"), 0.25) * impact_conv_norm
            + to_float(weights.get("confidence"), 0.15) * confidence
            + to_float(weights.get("effort_inverse"), 0.15) * (1.0 / max(1.0, effort_points))
            + to_float(weights.get("urgency"), 0.1) * urgency
            + to_float(weights.get("risk_inverse"), 0.05) * (1.0 / max(1.0, risk_points))
        )

        primary_metric = PRIMARY_METRIC_BY_TOPIC.get(topic, "signup_to_paid_rate")

        sample_target = int(max(20, min(400, 30 + to_float(row.get("duplicate_count"), 1.0) * 20 + rank * 2)))

        variant_plan = "progressive_rollout" if rank <= 8 else "ab"

        success_lift = max(0.0005, min(0.02, to_float(row.get("expected_signup_to_paid_lift_pp"), 0.0) + to_float(row.get("expected_visit_to_signup_lift_pp"), 0.0)))

        stop_rules = [
            "Stop if guardrail breach is detected at any checkpoint.",
            "Stop if SRM deviation exceeds configured threshold.",
            "Stop if runtime reaches 2x minimum_runtime_days with no directional movement.",
        ]

        exp = {
            "experiment_id": experiment_id,
            "hypothesis_id": hypothesis_id,
            "title": f"{topic}:{subtopic} iteration experiment",
            "status": "planned",
            "owner": row.get("owner") or row.get("owner_team") or "operations",
            "priority_tier": row.get("priority_tier") or "P3",
            "priority_score": row.get("priority_score"),
            "targeting": default_targeting,
            "variant_plan": variant_plan,
            "primary_metric": primary_metric,
            "guardrail_metrics": guardrail_metrics,
            "sample_target": sample_target,
            "minimum_runtime_days": min_runtime,
            "stop_rules": stop_rules,
            "success_criteria": {
                "primary_metric_lift_pp": round(success_lift, 6),
                "confidence_score_min": 0.7,
                "guardrail_breach": False,
            },
            "rollback_criteria": {
                "any_guardrail_breach": True,
                "unsubscribe_rate_delta_pp": to_float(((guardrail_metrics.get("unsubscribe_rate") or {}).get("max_delta_pp")), 0.01),
                "error_rate_delta_pp": to_float(((guardrail_metrics.get("error_rate") or {}).get("max_delta_pp")), 0.03),
            },
            "linked_feedback_item_id": item_id,
            "linked_theme_id": row.get("theme_id"),
            "linked_opportunity_id": opp.get("opportunity_id"),
            "recommended_action": row.get("recommended_action"),
            "expected_signup_delta_30d": row.get("expected_signup_delta_30d"),
            "expected_paid_delta_30d": row.get("expected_paid_delta_30d"),
            "expected_mrr_delta_30d": row.get("expected_mrr_delta_30d"),
            "effort_band": effort_band,
            "risk_band": risk_band,
            "stage3_weighted_score": round(weighted_score, 6),
            "decision_policy_ref": args.decision_policy,
            "evidence_examples": row.get("evidence_examples") if isinstance(row.get("evidence_examples"), list) else [],
        }
        backlog.append(exp)

        hypotheses.append(
            {
                "hypothesis_id": hypothesis_id,
                "experiment_id": experiment_id,
                "feedback_item_id": item_id,
                "for_segment": default_targeting.get("segment"),
                "problem_statement": f"Users in topic '{topic}' stall due to '{subtopic}' friction.",
                "proposed_change": row.get("recommended_action"),
                "expected_behavior_change": f"Improve {primary_metric} by reducing friction in {topic}/{subtopic} path.",
                "expected_metric_delta": {
                    "primary_metric": primary_metric,
                    "expected_signup_delta_30d": row.get("expected_signup_delta_30d"),
                    "expected_paid_delta_30d": row.get("expected_paid_delta_30d"),
                    "expected_mrr_delta_30d": row.get("expected_mrr_delta_30d"),
                },
                "invalidation_condition": "Guardrail breach or no directional movement after full runtime window.",
                "created_at": now_iso(),
            }
        )

    backlog = sorted(backlog, key=lambda r: (to_float(r.get("stage3_weighted_score"), 0.0), to_float(r.get("expected_mrr_delta_30d"), 0.0)), reverse=True)
    for idx, exp in enumerate(backlog, start=1):
        exp["rank"] = idx

    required_fields = contract.get("required_fields", []) if isinstance(contract.get("required_fields"), list) else []
    missing_contract_fields: Dict[str, List[str]] = {}
    for exp in backlog:
        missing = []
        for f in required_fields:
            val = exp.get(f)
            if val is None or (isinstance(val, str) and not val.strip()):
                missing.append(f)
        if missing:
            missing_contract_fields[str(exp.get("experiment_id"))] = missing

    running_limit = to_int(wip_limits.get("running_experiments_max"), 3)
    active_bets_limit = to_int(wip_limits.get("active_bets_max"), 5)

    top_running = [exp["experiment_id"] for exp in backlog[:running_limit]]

    portfolio = {
        "generated_at": now_iso(),
        "running_experiments_max": running_limit,
        "active_bets_max": active_bets_limit,
        "planned_experiments": len(backlog),
        "running_experiment_candidates": top_running,
        "wip_within_limit": len(top_running) <= running_limit,
        "notes": [
            "Top-ranked experiments are suggested as running candidates under current WIP limits.",
            "Lower-ranked experiments remain in planned state pending capacity.",
        ],
    }

    payload = {
        "generated_at": now_iso(),
        "item_count": len(backlog),
        "decision_policy_ref": args.decision_policy,
        "tier_counts": {
            "P0": sum(1 for x in backlog if str(x.get("priority_tier") or "") == "P0"),
            "P1": sum(1 for x in backlog if str(x.get("priority_tier") or "") == "P1"),
            "P2": sum(1 for x in backlog if str(x.get("priority_tier") or "") == "P2"),
            "P3": sum(1 for x in backlog if str(x.get("priority_tier") or "") == "P3"),
        },
        "experiments": backlog,
    }

    contract_validation = {
        "generated_at": now_iso(),
        "contract_path": args.experiment_contract,
        "required_fields_count": len(required_fields),
        "experiments_checked": len(backlog),
        "missing_contract_fields": missing_contract_fields,
        "status": "passed" if not missing_contract_fields else "failed",
    }

    write_json(in_dir / "experiment_backlog.latest.json", payload)
    write_jsonl(in_dir / "hypothesis_registry.latest.jsonl", hypotheses)
    write_json(in_dir / "iteration_portfolio.latest.json", portfolio)
    write_json(in_dir / "experiment_contract_validation.latest.json", contract_validation)

    print({"experiments": len(backlog), "contract_status": contract_validation["status"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
