#!/usr/bin/env python3
"""Compile project spec into landing-page-specific page spec (mode: landing)."""

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


def ensure_text(value: Any, fallback: str = "") -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def ensure_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if isinstance(v, str) and str(v).strip()]


def ensure_faq(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: List[Dict[str, str]] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        q = ensure_text(row.get("question"))
        a = ensure_text(row.get("answer"))
        if q and a:
            out.append({"question": q, "answer": a})
    return out


def load_profiles(layout_dir: pathlib.Path) -> List[Dict[str, Any]]:
    profiles: List[Dict[str, Any]] = []
    for path in sorted(layout_dir.glob("*.json")):
        payload = read_json(path)
        if not isinstance(payload, dict):
            continue
        if isinstance(payload.get("profile_id"), str):
            payload["_path"] = str(path)
            profiles.append(payload)
    if not profiles:
        raise ValueError(f"No landing profiles found in {layout_dir}")
    return profiles


def choose_profile(profiles: List[Dict[str, Any]], adapter_id: str, forced_profile: str | None) -> Dict[str, Any]:
    if forced_profile:
        for row in profiles:
            if row.get("profile_id") == forced_profile:
                return row
        raise ValueError(f"Unknown landing profile: {forced_profile}")

    for row in profiles:
        matches = row.get("match_adapters") if isinstance(row.get("match_adapters"), list) else []
        if adapter_id in matches:
            return row

    for row in profiles:
        if row.get("profile_id") == "landing-default":
            return row

    return profiles[0]


def module_props(module_id: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    segment = spec.get("segment") if isinstance(spec.get("segment"), dict) else {}
    offer = spec.get("offer") if isinstance(spec.get("offer"), dict) else {}
    metrics = spec.get("metrics") if isinstance(spec.get("metrics"), dict) else {}

    role = ensure_text(segment.get("role"), "Operators")
    industry = ensure_text(segment.get("industry"), "Business operations")
    company_size = ensure_text(segment.get("company_size"), "1-20")
    segment_label = f"{role} · {industry} · {company_size}"

    problem = ensure_text(spec.get("problem_statement"), "Core operational problem")
    value = ensure_text(spec.get("value_proposition"), "Clear value proposition")
    proof_points = ensure_list(spec.get("proof_points"))
    if not proof_points:
        proof_points = [
            "Focused scope to validate one bottleneck first.",
            "Evidence-backed messaging tied to observed pain signals.",
            "Clear conversion path with one primary CTA.",
        ]

    faq = ensure_faq(spec.get("faq"))
    if not faq:
        faq = [
            {
                "question": "Is this a full platform?",
                "answer": "No. This landing page validates one narrow outcome before broader scope expansion.",
            },
            {
                "question": "How fast can we validate?",
                "answer": "Run a focused 14-day test and decide with explicit success + kill criteria.",
            },
        ]

    if module_id == "hero_problem":
        return {
            "headline": ensure_text(offer.get("headline"), value),
            "subheadline": value,
            "problem_statement": problem,
            "segment_label": segment_label,
            "eyebrow": "Focused landing validation",
        }

    if module_id == "problem_agitation":
        return {
            "title": "Why this problem matters now",
            "core_pain": problem,
            "pain_points": proof_points[:3],
            "cost_of_inaction": ensure_text(
                metrics.get("target"),
                "Delaying this workflow keeps adding avoidable operational drag.",
            ),
        }

    if module_id == "benefit_bullets":
        return {
            "title": "What changes after adoption",
            "items": [
                ensure_text(value, "Clear workflow outcome"),
                *proof_points[:2],
            ],
        }

    if module_id == "proof_points":
        return {
            "title": "Proof and credibility",
            "items": proof_points,
        }

    if module_id == "social_proof_strip":
        return {
            "title": "Pilot trust signals",
            "items": [
                "Built from repeated operator pain evidence",
                "Single-goal conversion path with clear CTA",
                "Scope guardrails to prevent over-promising",
            ],
        }

    if module_id == "faq_list":
        return {
            "title": "FAQ",
            "items": faq,
        }

    if module_id == "cta_waitlist":
        return {
            "title": "Start validation with one focused pilot",
            "description": ensure_text(
                spec.get("cta_support_text"),
                "Join early access and validate demand before expanding product scope.",
            ),
            "cta_label": ensure_text(offer.get("cta_label"), "Join pilot"),
            "email_label": "Work email",
            "email_placeholder": "you@company.com",
        }

    raise ValueError(f"Unsupported landing module: {module_id}")


def parse_args() -> argparse.Namespace:
    root = pathlib.Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Compile landing page spec from project spec")
    parser.add_argument("--project-spec", required=True, help="Path to project spec JSON")
    parser.add_argument("--out", required=True, help="Output page spec path")
    parser.add_argument(
        "--layout-dir",
        default=str(root / "framework/landing/layout_profiles"),
        help="Landing profile directory",
    )
    parser.add_argument(
        "--module-registry",
        default=str(root / "framework/landing/module_registry.v1.json"),
        help="Landing module registry path",
    )
    parser.add_argument("--profile", required=False, help="Force landing profile id")
    parser.add_argument("--force", action="store_true", help="Overwrite output if exists")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    project_spec_path = pathlib.Path(args.project_spec).resolve()
    out_path = pathlib.Path(args.out).resolve()
    layout_dir = pathlib.Path(args.layout_dir).resolve()
    module_registry_path = pathlib.Path(args.module_registry).resolve()

    if not project_spec_path.exists():
        raise FileNotFoundError(project_spec_path)

    if out_path.exists() and not args.force:
        raise FileExistsError(f"Output exists: {out_path}; pass --force to overwrite")

    spec = read_json(project_spec_path)
    registry = read_json(module_registry_path)

    allowed_modules = {
        str(row.get("module_id"))
        for row in registry.get("modules", [])
        if isinstance(row, dict) and row.get("module_id")
    }
    forbidden_modules = [
        str(m)
        for m in registry.get("forbidden_default_modules", [])
        if isinstance(m, str) and m.strip()
    ]

    adapter = spec.get("adapter") if isinstance(spec.get("adapter"), dict) else {}
    adapter_id = ensure_text(adapter.get("name"), "generic-operator")

    profiles = load_profiles(layout_dir)
    profile = choose_profile(profiles=profiles, adapter_id=adapter_id, forced_profile=args.profile)
    module_order = [
        str(m)
        for m in profile.get("module_order", [])
        if isinstance(m, str) and m.strip()
    ]
    if not module_order:
        raise ValueError(f"Landing profile has empty module_order: {profile.get('profile_id')}")

    unknown = [m for m in module_order if m not in allowed_modules]
    if unknown:
        raise ValueError(f"Landing profile uses unknown modules: {unknown}")

    modules: List[Dict[str, Any]] = []
    for module_id in module_order:
        modules.append(
            {
                "module_id": module_id,
                "kind": "landing",
                "props": module_props(module_id=module_id, spec=spec),
            }
        )

    offer = spec.get("offer") if isinstance(spec.get("offer"), dict) else {}
    meta_title = ensure_text(offer.get("headline"), ensure_text(spec.get("value_proposition"), "Landing page"))
    meta_desc = ensure_text(spec.get("value_proposition"), ensure_text(spec.get("problem_statement"), "Landing page"))

    page_spec = {
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "page_spec_version": "1.1",
        "project_id": spec.get("project_id"),
        "adapter_name": adapter_id,
        "version": "1.1",
        "meta": {
            "title": meta_title,
            "description": meta_desc,
            "page_mode": "landing",
            "adapter_name": adapter_id,
            "profile": profile.get("profile_id"),
            "profile_display_name": profile.get("display_name"),
        },
        "layout_profile": profile.get("profile_id"),
        "theme": {
            "accent": "#2563eb",
            "surface": "#0f172a",
            "highlight": "#60a5fa",
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
            },
            "security_headers": [
                {"name": "x-content-type-options", "must_include": "nosniff"},
                {"name": "x-frame-options", "must_include": "DENY"},
                {"name": "referrer-policy", "must_include": "strict-origin-when-cross-origin"},
                {"name": "content-security-policy", "must_include": "default-src 'self'"}
            ],
            "page_mode": "landing",
            "required_modules": ["hero_problem", "proof_points", "faq_list", "cta_waitlist"],
            "forbidden_modules": forbidden_modules,
            "lp_section_whitelist": sorted(allowed_modules),
            "forbidden_terms": [
                "reusable web-product builder",
                "try the workflow assistant"
            ]
        },
        "project_spec_snapshot": {
            "project_id": spec.get("project_id"),
            "from_opportunity_id": spec.get("source", {}).get("opportunity_id") if isinstance(spec.get("source"), dict) else None,
            "adapter_name": adapter_id,
        },
    }

    write_json(out_path, page_spec)
    print(
        json.dumps(
            {
                "page_spec": str(out_path),
                "profile": profile.get("profile_id"),
                "mode": "landing",
                "module_count": len(modules),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
