#!/usr/bin/env python3
"""Initialize a robust multi-project Build&Deploy spec from Stage1/Stage2 outputs."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
from typing import Any, Dict, List, Tuple


def read_json(path: pathlib.Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: pathlib.Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-")


def load_adapters(adapter_dir: pathlib.Path) -> Dict[str, Dict[str, Any]]:
    adapters: Dict[str, Dict[str, Any]] = {}
    for path in sorted(adapter_dir.glob("*.json")):
        payload = read_json(path)
        adapter_id = payload.get("adapter_id")
        if isinstance(adapter_id, str) and adapter_id.strip():
            adapters[adapter_id] = payload
    if not adapters:
        raise ValueError(f"No adapters found in {adapter_dir}")
    return adapters


def top_advance_opportunity(stage2: Dict[str, Any]) -> str:
    decisions = stage2.get("decisions", [])
    advances = [d for d in decisions if d.get("decision") == "advance"]
    if not advances:
        raise ValueError("No 'advance' opportunity found in stage2 decision log.")
    advances.sort(key=lambda row: float(row.get("weighted_score", 0.0)), reverse=True)
    return str(advances[0].get("opportunity_id"))


def find_stage1_opportunity(stage1: Dict[str, Any], opportunity_id: str) -> Dict[str, Any]:
    for row in stage1.get("opportunities", []):
        if row.get("opportunity_id") == opportunity_id:
            return row
    raise ValueError(f"Opportunity {opportunity_id} not found in stage1 records.")


def find_stage2_decision(stage2: Dict[str, Any], opportunity_id: str) -> Dict[str, Any]:
    for row in stage2.get("decisions", []):
        if row.get("opportunity_id") == opportunity_id:
            return row
    return {}


def gather_signal_text(opp: Dict[str, Any]) -> str:
    chunks: List[str] = []
    for key in ["core_problem", "current_workaround"]:
        value = opp.get(key)
        if isinstance(value, str):
            chunks.append(value)

    evidence = opp.get("pain_evidence", [])
    if isinstance(evidence, list):
        for item in evidence[:6]:
            claim = item.get("claim") if isinstance(item, dict) else None
            if isinstance(claim, str):
                chunks.append(claim)

    return "\n".join(chunks).lower()


def adapter_match_score(adapter: Dict[str, Any], signal_text: str) -> float:
    keywords = adapter.get("match_keywords", [])
    if not isinstance(keywords, list) or not keywords:
        return 0.0

    hits = 0
    for kw in keywords:
        if isinstance(kw, str) and kw.strip() and kw.lower() in signal_text:
            hits += 1

    return hits / max(len(keywords), 1)


def choose_adapter(
    adapters: Dict[str, Dict[str, Any]],
    opp: Dict[str, Any],
    forced_adapter: str | None,
) -> Tuple[Dict[str, Any], float, str]:
    if forced_adapter:
        selected = adapters.get(forced_adapter)
        if selected is None:
            raise ValueError(f"Forced adapter '{forced_adapter}' not found.")
        return selected, 1.0, "forced"

    signal_text = gather_signal_text(opp)
    best_id = None
    best_score = -1.0

    for adapter_id, adapter in adapters.items():
        score = adapter_match_score(adapter, signal_text)
        if score > best_score:
            best_score = score
            best_id = adapter_id

    assert best_id is not None
    selected = adapters[best_id]

    if best_score <= 0:
        fallback = adapters.get("generic-operator")
        if fallback is not None:
            return fallback, 0.0, "fallback_generic"

    return selected, max(best_score, 0.0), "keyword_match"


def build_project_spec(
    opp: Dict[str, Any],
    decision: Dict[str, Any],
    adapter: Dict[str, Any],
    adapter_score: float,
    adapter_reason: str,
) -> Dict[str, Any]:
    opp_id = str(opp.get("opportunity_id", "opp_unknown"))
    segment = opp.get("target_segment", {}) if isinstance(opp.get("target_segment"), dict) else {}

    role = str(segment.get("role", "Operator"))
    industry = str(segment.get("industry", "Business operations"))
    company_size = str(segment.get("company_size", "1-20"))

    seg_override = adapter.get("segment_override") if isinstance(adapter.get("segment_override"), dict) else {}
    if seg_override:
        role = str(seg_override.get("role", role))
        industry = str(seg_override.get("industry", industry))
        company_size = str(seg_override.get("company_size", company_size))

    core_problem = str(
        adapter.get("problem_statement")
        or opp.get("core_problem", "Manual workflow friction causing measurable business loss.")
    )

    offer_headline = str(
        adapter.get("offer_headline", "Turn manual workflows into a repeatable action system")
    )

    workflow = adapter.get("workflow", {}) if isinstance(adapter.get("workflow"), dict) else {}
    pricing_defaults = (
        adapter.get("pricing_defaults", {}) if isinstance(adapter.get("pricing_defaults"), dict) else {}
    )
    business_tests = adapter.get("business_tests", []) if isinstance(adapter.get("business_tests"), list) else []
    proof_points = adapter.get("proof_points", []) if isinstance(adapter.get("proof_points"), list) else []
    faq = adapter.get("faq", []) if isinstance(adapter.get("faq"), list) else []
    operational_checklist = (
        adapter.get("operational_checklist", [])
        if isinstance(adapter.get("operational_checklist"), list)
        else []
    )
    page_profile = adapter.get("page_profile") if isinstance(adapter.get("page_profile"), str) else None
    cta_support_text = (
        adapter.get("cta_support_text") if isinstance(adapter.get("cta_support_text"), str) else None
    )

    confidence_level = (
        decision.get("confidence", {}).get("level")
        if isinstance(decision.get("confidence"), dict)
        else None
    ) or "unknown"

    project_id = f"proj-{slugify(opp_id)}-{slugify(str(adapter.get('adapter_id', 'generic')))}-v1"

    spec = {
        "spec_version": "1.0",
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "project_id": project_id,
        "source": {
            "opportunity_id": opp_id,
            "stage": "stage2",
            "selection_reason": "top_advance_by_score",
            "decision_confidence": confidence_level,
            "decision_weighted_score": float(decision.get("weighted_score", 0.0)) if decision else 0.0,
        },
        "segment": {
            "role": role,
            "industry": industry,
            "company_size": company_size,
        },
        "problem_statement": core_problem,
        "value_proposition": (
            f"{offer_headline}. Designed for {role} teams in {industry} to validate demand quickly."
        ),
        "offer": {
            "headline": offer_headline,
            "cta_label": "Join pilot",
            "cta_type": "email_waitlist",
            "channel_hint": (
                opp.get("distribution_entry", {}).get("channel")
                if isinstance(opp.get("distribution_entry"), dict)
                else "target communities"
            ),
        },
        "workflow": {
            "prompt_label": workflow.get("prompt_label", "Describe your operational bottleneck"),
            "prompt_placeholder": workflow.get(
                "prompt_placeholder",
                "e.g. We lose time in repetitive manual operations and need a first-step plan.",
            ),
            "primary_action_label": workflow.get("primary_action_label", "Generate first action"),
            "rules": workflow.get("rules", []),
            "default_response": workflow.get(
                "default_response",
                {
                    "first_step": "Map your process and automate the highest-friction step first.",
                    "next_steps": [
                        "Instrument one measurable metric.",
                        "Test for 14 days.",
                        "Decide go/kill by predefined threshold.",
                    ],
                },
            ),
        },
        "metrics": {
            "success_metric": "Qualified intent captures",
            "target": "At least 5 qualified leads from first 20 targeted users in 14 days",
            "kill_criteria": [
                "Fewer than 2 qualified intent captures after 20 targeted visitors",
                "Core workflow completion rate below 20% in first-session usage",
            ],
        },
        "pricing": {
            "plan_a": pricing_defaults.get("plan_a", "$19/month"),
            "plan_b": pricing_defaults.get("plan_b", "$79/month"),
        },
        "adapter": {
            "name": adapter.get("adapter_id", "generic-operator"),
            "display_name": adapter.get("display_name", "Generic Operator Workflow"),
            "description": adapter.get("description", "Adapter-based generation fallback"),
            "match_score": round(adapter_score, 3),
            "match_reason": adapter_reason,
        },
        "business_tests": business_tests,
        "proof_points": proof_points,
        "faq": faq,
        "operational_checklist": operational_checklist,
    }

    if page_profile:
        spec["page_profile"] = page_profile
    if cta_support_text:
        spec["cta_support_text"] = cta_support_text

    return spec


def parse_args() -> argparse.Namespace:
    default_root = pathlib.Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Create build/deploy project spec from stage1+stage2")
    parser.add_argument("--stage1", required=True, help="Path to stage1 opportunity records JSON")
    parser.add_argument("--stage2", required=True, help="Path to stage2 decision log JSON")
    parser.add_argument("--out", required=True, help="Output project spec JSON path")
    parser.add_argument("--opp-id", required=False, help="Explicit opportunity_id")
    parser.add_argument("--adapter", required=False, help="Force adapter id")
    parser.add_argument(
        "--adapter-dir",
        required=False,
        default=str(default_root / "framework/build_deploy/adapters"),
        help="Directory containing adapter JSON files",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    stage1_path = pathlib.Path(args.stage1).resolve()
    stage2_path = pathlib.Path(args.stage2).resolve()
    out_path = pathlib.Path(args.out).resolve()
    adapter_dir = pathlib.Path(args.adapter_dir).resolve()

    if out_path.exists() and not args.force:
        raise FileExistsError(f"Output already exists: {out_path}. Use --force to overwrite.")

    stage1 = read_json(stage1_path)
    stage2 = read_json(stage2_path)
    adapters = load_adapters(adapter_dir)

    opp_id = args.opp_id or top_advance_opportunity(stage2)
    opp = find_stage1_opportunity(stage1, opp_id)
    decision = find_stage2_decision(stage2, opp_id)

    adapter, adapter_score, adapter_reason = choose_adapter(adapters, opp, args.adapter)

    spec = build_project_spec(opp, decision, adapter, adapter_score, adapter_reason)
    if args.opp_id:
        spec["source"]["selection_reason"] = "explicit_opportunity"

    write_json(out_path, spec)

    summary = {
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "project_spec": str(out_path),
        "opportunity_id": opp_id,
        "adapter": spec["adapter"],
        "project_id": spec["project_id"],
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
