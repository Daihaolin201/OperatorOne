#!/usr/bin/env python3
"""Compile project spec into modular page spec for scaffold rendering."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
from typing import Any, Dict, List


def read_json(path: pathlib.Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: pathlib.Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_text(value: Any, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def ensure_list_of_text(value: Any, fallback: List[str]) -> List[str]:
    if not isinstance(value, list):
        return fallback
    out = [str(item).strip() for item in value if isinstance(item, str) and str(item).strip()]
    return out or fallback


def ensure_faq(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: List[Dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        question = ensure_text(item.get("question"), "")
        answer = ensure_text(item.get("answer"), "")
        if question and answer:
            out.append({"question": question, "answer": answer})
    return out


def load_module_registry(path: pathlib.Path) -> Dict[str, Dict[str, Any]]:
    payload = read_json(path)
    rows = payload.get("modules", []) if isinstance(payload.get("modules"), list) else []
    registry: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        module_id = row.get("module_id")
        if isinstance(module_id, str) and module_id.strip():
            registry[module_id] = row
    if not registry:
        raise ValueError(f"Module registry has no modules: {path}")
    return registry


def load_layout_profiles(layout_dir: pathlib.Path) -> List[Dict[str, Any]]:
    profiles: List[Dict[str, Any]] = []
    for path in sorted(layout_dir.glob("*.json")):
        payload = read_json(path)
        if isinstance(payload, dict) and isinstance(payload.get("profile_id"), str):
            payload["_path"] = str(path)
            profiles.append(payload)
    if not profiles:
        raise ValueError(f"No layout profile JSON found in {layout_dir}")
    return profiles


def choose_profile(
    profiles: List[Dict[str, Any]],
    adapter_name: str,
    forced_profile: str | None,
    preferred_profile: str | None,
) -> Dict[str, Any]:
    def by_id(profile_id: str | None) -> Dict[str, Any] | None:
        if not profile_id:
            return None
        for row in profiles:
            if row.get("profile_id") == profile_id:
                return row
        return None

    explicit = by_id(forced_profile)
    if forced_profile and explicit is None:
        raise ValueError(f"Forced profile not found: {forced_profile}")
    if explicit is not None:
        return explicit

    preferred = by_id(preferred_profile)
    if preferred is not None:
        return preferred

    for row in profiles:
        matches = row.get("match_adapters", []) if isinstance(row.get("match_adapters"), list) else []
        if adapter_name in matches:
            return row

    default_profile = by_id("default")
    if default_profile is not None:
        return default_profile

    return profiles[0]


def build_module_props(module_id: str, spec: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    segment = spec.get("segment", {}) if isinstance(spec.get("segment"), dict) else {}
    offer = spec.get("offer", {}) if isinstance(spec.get("offer"), dict) else {}
    workflow = spec.get("workflow", {}) if isinstance(spec.get("workflow"), dict) else {}
    metrics = spec.get("metrics", {}) if isinstance(spec.get("metrics"), dict) else {}
    pricing = spec.get("pricing", {}) if isinstance(spec.get("pricing"), dict) else {}
    adapter = spec.get("adapter", {}) if isinstance(spec.get("adapter"), dict) else {}

    segment_label = " · ".join(
        [
            ensure_text(segment.get("role"), "Target operator"),
            ensure_text(segment.get("industry"), "Business operations"),
            ensure_text(segment.get("company_size"), "1-20"),
        ]
    )

    proof_points = ensure_list_of_text(
        spec.get("proof_points"),
        [
            "One core workflow focused on a measurable business bottleneck.",
            "Action suggestions are rule-driven and adapter-specific.",
            "Deployment + validation pipeline is reproducible and auditable.",
        ],
    )

    faq = ensure_faq(spec.get("faq"))
    if not faq:
        faq = [
            {
                "question": "How fast can we validate this?",
                "answer": "Run a focused 14-day test using the core workflow and one primary CTA.",
            },
            {
                "question": "Can this fit our process?",
                "answer": "Yes. The adapter rules and page modules are configurable without rewriting the entire app.",
            },
        ]

    checklist = ensure_list_of_text(
        spec.get("operational_checklist"),
        [
            "Prioritize highest-risk, highest-value cases first.",
            "Use one standardized evidence template per case.",
            "Track outcomes weekly and update rules from real results.",
        ],
    )

    if module_id == "hero_problem":
        return {
            "headline": ensure_text(offer.get("headline"), ensure_text(spec.get("value_proposition"), "Focused workflow")),
            "subheadline": ensure_text(spec.get("value_proposition"), "Launch a testable business workflow quickly."),
            "problem_statement": ensure_text(spec.get("problem_statement"), "Business problem statement is missing."),
            "segment_label": segment_label,
            "adapter_name": ensure_text(adapter.get("display_name"), ensure_text(adapter.get("name"), "Unknown adapter")),
            "profile_name": ensure_text(profile.get("display_name"), ensure_text(profile.get("profile_id"), "Default profile")),
        }

    if module_id == "workflow_interactive":
        return {
            "title": "Try the workflow assistant",
            "prompt_label": ensure_text(workflow.get("prompt_label"), "Describe your bottleneck"),
            "prompt_placeholder": ensure_text(workflow.get("prompt_placeholder"), "Describe your scenario..."),
            "action_label": ensure_text(workflow.get("primary_action_label"), "Generate first step"),
        }

    if module_id == "proof_points":
        return {
            "title": "Why this approach",
            "items": proof_points,
        }

    if module_id == "evidence_checklist":
        return {
            "title": "Execution checklist",
            "items": checklist,
        }

    if module_id == "metric_snapshot":
        return {
            "title": "Validation target",
            "metric": ensure_text(metrics.get("success_metric"), "Qualified intent captures"),
            "target": ensure_text(metrics.get("target"), "Define a measurable target"),
        }

    if module_id == "pricing_cards":
        return {
            "title": "Pricing hypothesis",
            "plan_a": ensure_text(pricing.get("plan_a"), "$19/month"),
            "plan_b": ensure_text(pricing.get("plan_b"), "$79/month"),
        }

    if module_id == "risk_guardrails":
        return {
            "title": "Guardrails",
            "items": ensure_list_of_text(
                metrics.get("kill_criteria"),
                ["Stop if early user signal is insufficient."],
            ),
        }

    if module_id == "cta_waitlist":
        return {
            "title": "Start with one pilot workflow",
            "description": ensure_text(
                spec.get("cta_support_text"),
                "Get early access and validate with real operators before expanding scope.",
            ),
            "cta_label": ensure_text(offer.get("cta_label"), "Join pilot"),
            "email_label": "Work email",
            "email_placeholder": "you@company.com",
        }

    if module_id == "faq_list":
        return {
            "title": "FAQ",
            "items": faq,
        }

    raise ValueError(f"Unsupported module_id in layout profile: {module_id}")


def parse_args() -> argparse.Namespace:
    root = pathlib.Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Compile project spec into modular page spec")
    parser.add_argument("--project-spec", required=True, help="Path to project spec JSON")
    parser.add_argument("--out", required=True, help="Output page spec path")
    parser.add_argument(
        "--module-registry",
        required=False,
        default=str(root / "framework/build_deploy/page_modules/module_registry.v1.json"),
        help="Path to page module registry JSON",
    )
    parser.add_argument(
        "--layout-dir",
        required=False,
        default=str(root / "framework/build_deploy/layout_profiles"),
        help="Directory containing layout profile JSON files",
    )
    parser.add_argument("--profile", required=False, help="Force layout profile id")
    parser.add_argument("--force", action="store_true", help="Overwrite output if exists")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_spec_path = pathlib.Path(args.project_spec).resolve()
    out_path = pathlib.Path(args.out).resolve()
    module_registry_path = pathlib.Path(args.module_registry).resolve()
    layout_dir = pathlib.Path(args.layout_dir).resolve()

    if out_path.exists() and not args.force:
        raise FileExistsError(f"Output already exists: {out_path}. Use --force to overwrite.")

    spec = read_json(project_spec_path)
    registry = load_module_registry(module_registry_path)
    profiles = load_layout_profiles(layout_dir)

    adapter = spec.get("adapter", {}) if isinstance(spec.get("adapter"), dict) else {}
    adapter_name = ensure_text(adapter.get("name"), "generic-operator")
    preferred_profile = ensure_text(spec.get("page_profile"), "") or None
    profile = choose_profile(
        profiles,
        adapter_name=adapter_name,
        forced_profile=args.profile,
        preferred_profile=preferred_profile,
    )

    module_order = profile.get("module_order", []) if isinstance(profile.get("module_order"), list) else []
    if not module_order:
        raise ValueError(f"Layout profile has empty module_order: {profile.get('profile_id')}")

    modules: List[Dict[str, Any]] = []
    for module_id in module_order:
        if module_id not in registry:
            raise ValueError(f"Module '{module_id}' not found in registry {module_registry_path}")
        kind = ensure_text(registry[module_id].get("kind"), "unknown")
        props = build_module_props(module_id, spec=spec, profile=profile)
        modules.append({
            "module_id": module_id,
            "kind": kind,
            "props": props,
        })

    offer = spec.get("offer", {}) if isinstance(spec.get("offer"), dict) else {}

    page_spec = {
        "page_spec_version": "1.0",
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "project_id": ensure_text(spec.get("project_id"), "proj-unknown"),
        "adapter_name": adapter_name,
        "layout_profile": ensure_text(profile.get("profile_id"), "default"),
        "theme": profile.get("theme", {}),
        "meta": {
            "title": ensure_text(offer.get("headline"), ensure_text(spec.get("value_proposition"), "Simple web product")),
            "description": ensure_text(spec.get("problem_statement"), "")[:180],
        },
        "modules": modules,
        "testing": {
            "expected_modules": [m.get("module_id") for m in modules],
            "primary_cta_module": "cta_waitlist",
            "max_primary_cta_buttons": 1,
            "require_viewport_meta": True,
            "responsive_markers": ["@media", "max-width", "min-width"],
            "device_profiles": [
                {"id": "mobile", "width": 390, "height": 844},
                {"id": "tablet", "width": 768, "height": 1024},
                {"id": "desktop", "width": 1440, "height": 900}
            ],
            "performance_budget": {
                "lcp_ms": 2500,
                "inp_ms": 200,
                "cls_max": 0.1
            }
        },
        "project_spec_snapshot": spec,
    }

    write_json(out_path, page_spec)

    print(
        json.dumps(
            {
                "generated_at": page_spec["generated_at"],
                "project_spec": str(project_spec_path),
                "page_spec": str(out_path),
                "adapter": adapter_name,
                "layout_profile": page_spec["layout_profile"],
                "module_count": len(modules),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
