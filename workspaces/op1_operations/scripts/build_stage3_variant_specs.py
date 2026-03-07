#!/usr/bin/env python3
"""Build Stage3 variant specifications from experiment backlog."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from stage3_iteration_common import now_iso, read_json, resolve_repo_root, stable_hash, write_json


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Stage3 variant specs")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root")
    p.add_argument(
        "--in-dir",
        default="workspaces/op1_operations/research/stage3_product_iteration",
        help="Input/output directory",
    )
    p.add_argument(
        "--product-run",
        default="workspaces/op1_product/research/stage2_web_product/run.latest.json",
        help="Product run.latest path",
    )
    return p.parse_args()


def _topic_changes(topic: str, subtopic: str) -> List[str]:
    t = topic
    s = subtopic
    if t == "onboarding":
        return [
            "Reduce initial form fields to minimum required set",
            "Add checklist progress and one primary next action",
            "Display workflow examples before first submit",
        ]
    if t == "pricing":
        return [
            "Add ROI calculator card above pricing tiers",
            "Clarify plan boundaries and best-fit labels",
            "Add limited pilot offer with low-risk CTA",
        ]
    if t == "trust":
        return [
            "Add trust and compliance proof block near CTA",
            "Expose privacy/permission language in concise bullets",
            "Highlight rollback/controls assurances",
        ]
    if t == "billing":
        return [
            "Add overdue/payment status summary at top",
            "Add recommended next action by invoice state",
            "Expose escalation template selector",
        ]
    if t == "integration":
        return [
            "Add import compatibility helper",
            "Add connector quick-start guidance",
            "Show sync/error status in one panel",
        ]
    if t == "retention":
        return [
            "Add not-now follow-up timing selector",
            "Show migration-lite path for incumbent users",
            "Add contextual reminder nudges",
        ]
    return [
        f"Improve UX/message alignment for {t}/{s}",
        "Reduce friction in primary conversion flow",
        "Clarify next best action",
    ]


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else resolve_repo_root(Path(__file__))
    in_dir = repo_root / args.in_dir

    backlog = read_json(in_dir / "experiment_backlog.latest.json", default={}) or {}
    experiments = backlog.get("experiments", []) if isinstance(backlog.get("experiments"), list) else []

    product_run = read_json(repo_root / args.product_run, default={}) or {}
    product_output = product_run.get("output", {}) if isinstance(product_run.get("output"), dict) else {}

    deployed_url = product_output.get("deployed_url")
    app_dir = product_output.get("app_dir")

    variants: List[Dict[str, Any]] = []

    for exp in experiments:
        if not isinstance(exp, dict):
            continue

        exp_id = str(exp.get("experiment_id") or "")
        topic = str(exp.get("topic") or "general")
        subtopic = str(exp.get("subtopic") or "uncategorized")

        flag_key = f"flag_{exp_id}"
        variant_set_id = "varset_" + stable_hash([exp_id, topic, subtopic], 10)

        change_suggestions = _topic_changes(topic, subtopic)

        control = {
            "variant_id": f"{exp_id}_control",
            "name": "control",
            "traffic_percent": 50,
            "feature_flag_value": False,
            "changes": ["No changes. Baseline experience."],
        }

        treatment = {
            "variant_id": f"{exp_id}_treatment",
            "name": "treatment",
            "traffic_percent": 50,
            "feature_flag_value": True,
            "changes": change_suggestions,
        }

        variants.append(
            {
                "variant_set_id": variant_set_id,
                "experiment_id": exp_id,
                "flag_key": flag_key,
                "variant_plan": exp.get("variant_plan", "ab"),
                "primary_metric": exp.get("primary_metric"),
                "targeting": exp.get("targeting"),
                "owner": exp.get("owner"),
                "topic": topic,
                "subtopic": subtopic,
                "runtime_target": {
                    "deployed_url": deployed_url,
                    "app_dir": app_dir,
                },
                "variants": [control, treatment],
                "implementation_notes": [
                    "Apply treatment behind feature flag and keep a clean control path.",
                    "Do not merge variant behavior into baseline until decision policy returns ship.",
                ],
            }
        )

    payload = {
        "generated_at": now_iso(),
        "variant_set_count": len(variants),
        "variants": variants,
        "references": {
            "experiment_backlog": "workspaces/op1_operations/research/stage3_product_iteration/experiment_backlog.latest.json",
            "product_run": args.product_run,
        },
    }

    write_json(in_dir / "variant_specs.latest.json", payload)
    print({"variant_set_count": len(variants)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
