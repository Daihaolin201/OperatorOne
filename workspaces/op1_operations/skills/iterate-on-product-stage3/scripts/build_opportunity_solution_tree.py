#!/usr/bin/env python3
"""Build Stage3 Opportunity Solution Tree (OST) from iteration inputs."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from stage3_iteration_common import now_iso, read_json, resolve_repo_root, stable_hash, to_float, write_json


TOPIC_METRIC_MAP = {
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
    p = argparse.ArgumentParser(description="Build Stage3 opportunity solution tree")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root")
    p.add_argument(
        "--in-dir",
        default="workspaces/op1_operations/research/stage3_product_iteration",
        help="Input/output directory",
    )
    return p.parse_args()


def _topic_solution_templates(topic: str) -> List[Dict[str, Any]]:
    t = topic
    if t == "onboarding":
        return [
            {
                "title": "Guided first-run workflow",
                "description": "Reduce setup friction with checklist + smart defaults + one clear first success path.",
                "effort": "medium",
            },
            {
                "title": "Template-first entry",
                "description": "Offer prefilled templates for the most common workflow to reduce time-to-value.",
                "effort": "low",
            },
            {
                "title": "Interactive diagnostics",
                "description": "Ask 3-5 setup questions and route users to the best configuration path.",
                "effort": "medium",
            },
        ]
    if t == "pricing":
        return [
            {
                "title": "Value-based pricing page revision",
                "description": "Reframe pricing around outcomes and ROI checkpoints rather than feature count.",
                "effort": "low",
            },
            {
                "title": "Pilot offer + risk reversal",
                "description": "Introduce limited pilot tier with explicit milestone checkpoints.",
                "effort": "low",
            },
            {
                "title": "Plan fit recommender",
                "description": "Add decision wizard to recommend the most suitable plan by use case.",
                "effort": "medium",
            },
        ]
    if t == "trust":
        return [
            {
                "title": "Trust proof block",
                "description": "Expose controls, security posture, and quality guarantees near conversion points.",
                "effort": "low",
            },
            {
                "title": "Permissioned communication controls",
                "description": "Improve opt-in clarity and reduce irrelevant outreach triggers.",
                "effort": "medium",
            },
            {
                "title": "Risk-aware onboarding",
                "description": "Detect high-risk uncertainty and deliver contextual reassurance content.",
                "effort": "medium",
            },
        ]
    if t == "retention":
        return [
            {
                "title": "Reactivation cadence",
                "description": "Structured follow-up path for 'not-now' objections with timing-based nudges.",
                "effort": "low",
            },
            {
                "title": "Competitor migration-lite flow",
                "description": "Enable no-rip-and-replace setup path for users locked into incumbents.",
                "effort": "medium",
            },
            {
                "title": "Lifecycle-specific offers",
                "description": "Adjust onboarding and pricing offers by lifecycle stage and intent confidence.",
                "effort": "medium",
            },
        ]
    if t == "billing":
        return [
            {
                "title": "Billing workflow simplification",
                "description": "Simplify invoice and payment status tracking in primary workflow.",
                "effort": "medium",
            },
            {
                "title": "Collections reminder playbook",
                "description": "Systematic escalation templates with deadline and response tracking.",
                "effort": "low",
            },
            {
                "title": "Payment failure diagnostics",
                "description": "Surface root-cause hints for failure states and recommend next action.",
                "effort": "medium",
            },
        ]
    if t == "integration":
        return [
            {
                "title": "Connector quick-start",
                "description": "Add fast-path setup for most requested integrations.",
                "effort": "medium",
            },
            {
                "title": "Import compatibility checker",
                "description": "Validate input compatibility before import and show fix guidance.",
                "effort": "low",
            },
            {
                "title": "Sync visibility panel",
                "description": "Expose sync status and actionable errors in one place.",
                "effort": "medium",
            },
        ]
    if t == "support":
        return [
            {
                "title": "Embedded guidance cards",
                "description": "Inline playbooks for frequent confusion points.",
                "effort": "low",
            },
            {
                "title": "Contextual help routing",
                "description": "Route users to relevant guides based on current step and errors.",
                "effort": "medium",
            },
            {
                "title": "Proactive check-in nudges",
                "description": "Trigger support hints on inactivity or repeated retries.",
                "effort": "low",
            },
        ]
    return [
        {
            "title": "Message and workflow alignment",
            "description": "Align product messaging and primary workflow to top user pain signals.",
            "effort": "low",
        },
        {
            "title": "Focused UX simplification",
            "description": "Remove unnecessary complexity in high-friction journey steps.",
            "effort": "medium",
        },
        {
            "title": "Evidence-led conversion support",
            "description": "Add proof and clear next actions where users stall most.",
            "effort": "low",
        },
    ]


def _experiment_stub(opportunity_id: str, solution_title: str, idx: int) -> Dict[str, Any]:
    exp_id = "exp_" + stable_hash([opportunity_id, solution_title, idx], 12)
    return {
        "experiment_id": exp_id,
        "name": f"{solution_title} — Variant {idx}",
        "variant_plan": "ab",
        "status": "planned",
    }


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else resolve_repo_root(Path(__file__))
    in_dir = repo_root / args.in_dir

    inputs = read_json(in_dir / "iteration_inputs.latest.json", default={}) or {}
    if not inputs:
        raise SystemExit("Missing iteration_inputs.latest.json")

    stage1 = inputs.get("stage1_baseline", {}) if isinstance(inputs.get("stage1_baseline"), dict) else {}
    stage2 = inputs.get("stage2_feedback_context", {}) if isinstance(inputs.get("stage2_feedback_context"), dict) else {}
    queue = inputs.get("top_feedback_queue", []) if isinstance(inputs.get("top_feedback_queue"), list) else []

    topic_rows = stage2.get("top_topics", []) if isinstance(stage2.get("top_topics"), list) else []

    topic_to_rows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in queue:
        if isinstance(row, dict):
            topic_to_rows[str(row.get("topic") or "general")].append(row)

    opportunities: List[Dict[str, Any]] = []

    for idx, topic_row in enumerate(topic_rows[:8], start=1):
        topic = str(topic_row.get("topic") or "general")
        weighted = to_float(topic_row.get("weighted_priority"), 0.0)
        linked_rows = topic_to_rows.get(topic, [])

        opportunity_id = "ost_opp_" + stable_hash([topic], 10)
        target_metric = TOPIC_METRIC_MAP.get(topic, "signup_to_paid_rate")

        evidence_refs = [str(r.get("feedback_item_id") or "") for r in linked_rows[:10]]
        evidence_text = []
        for r in linked_rows[:3]:
            for ex in (r.get("evidence_examples") if isinstance(r.get("evidence_examples"), list) else [])[:1]:
                if ex:
                    evidence_text.append(str(ex))

        solutions = []
        for sidx, tmpl in enumerate(_topic_solution_templates(topic), start=1):
            solution_id = "sol_" + stable_hash([opportunity_id, tmpl["title"], sidx], 10)
            experiments = [_experiment_stub(opportunity_id, tmpl["title"], eidx) for eidx in (1, 2)]
            solutions.append(
                {
                    "solution_id": solution_id,
                    "title": tmpl["title"],
                    "description": tmpl["description"],
                    "effort_band": tmpl["effort"],
                    "experiments": experiments,
                }
            )

        opportunities.append(
            {
                "opportunity_id": opportunity_id,
                "rank": idx,
                "topic": topic,
                "weighted_priority": round(weighted, 4),
                "target_metric": target_metric,
                "problem_statement": f"Users show repeated friction in '{topic}' themes impacting {target_metric}.",
                "evidence_feedback_item_ids": evidence_refs,
                "evidence_samples": evidence_text,
                "solutions": solutions,
            }
        )

    payload = {
        "generated_at": now_iso(),
        "north_star": {
            "name": "Reach first $100 MRR with repeatable product iteration loop",
            "current_net_new_mrr": to_float(stage1.get("net_new_mrr"), 0.0),
            "target_net_new_mrr": 100.0,
            "current_visit_to_signup_rate": to_float(stage1.get("visit_to_signup_rate"), 0.0),
            "current_signup_to_paid_rate": to_float(stage1.get("signup_to_paid_rate"), 0.0),
        },
        "opportunity_count": len(opportunities),
        "opportunities": opportunities,
        "notes": [
            "Tree is generated from Stage2 weighted topic priorities and Stage1 baseline metrics.",
            "Each opportunity includes candidate solutions and planned experiment stubs.",
        ],
    }

    write_json(in_dir / "opportunity_solution_tree.latest.json", payload)
    print({"opportunity_count": len(opportunities)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
