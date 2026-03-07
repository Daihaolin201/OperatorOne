#!/usr/bin/env python3
"""Compile project spec into landing-page-specific page spec (mode: landing)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
from typing import Any, Dict, List


ADAPTER_COPY_PROFILE: Dict[str, Dict[str, str]] = {
    "invoice-followup": {
        "problem_title": "Late invoices quietly damage weekly cashflow",
        "benefit_title": "What improves in the first 14 days",
        "benefit_lead": "Move from ad-hoc chasing to a repeatable receivables queue.",
        "proof_title": "What this approach is grounded in",
        "faq_title": "Before you start",
        "cta_title": "Start the overdue-invoice pilot",
        "cta_description": "Join pilot access to run one structured follow-up flow this week.",
        "cta_label": "Join invoice pilot",
    },
    "chargeback-response": {
        "problem_title": "Dispute delays create preventable revenue leakage",
        "benefit_title": "What changes after one sprint",
        "benefit_lead": "Run one deadline-safe dispute response loop with clearer evidence prep.",
        "proof_title": "Operational proof behind this page",
        "faq_title": "What teams ask before rollout",
        "cta_title": "Start the chargeback response pilot",
        "cta_description": "Join pilot to standardize dispute evidence and reduce preventable losses.",
        "cta_label": "Join dispute pilot",
    },
    "client-reporting": {
        "problem_title": "Reporting delays weaken client trust and renewals",
        "benefit_title": "What your team gets quickly",
        "benefit_lead": "Ship consistent weekly reports without the last-minute scramble.",
        "proof_title": "Why this flow is credible",
        "faq_title": "Common rollout questions",
        "cta_title": "Start the reporting pilot",
        "cta_description": "Join pilot to test one repeatable client-reporting rhythm.",
        "cta_label": "Join reporting pilot",
    },
    "generic-operator": {
        "problem_title": "Why this bottleneck deserves immediate action",
        "benefit_title": "What improves after focused adoption",
        "benefit_lead": "Replace fragmented manual steps with one repeatable workflow.",
        "proof_title": "Evidence behind this recommendation",
        "faq_title": "FAQ",
        "cta_title": "Start the focused pilot",
        "cta_description": "Join early access and validate demand before expanding scope.",
        "cta_label": "Join pilot",
    },
}


ADAPTER_THEME_PROFILE: Dict[str, Dict[str, str]] = {
    "invoice-followup": {"accent": "#2563eb", "surface": "#0f172a", "highlight": "#60a5fa"},
    "chargeback-response": {"accent": "#7c3aed", "surface": "#1f1147", "highlight": "#c4b5fd"},
    "client-reporting": {"accent": "#0ea5e9", "surface": "#082f49", "highlight": "#67e8f9"},
    "generic-operator": {"accent": "#2563eb", "surface": "#0f172a", "highlight": "#60a5fa"},
}


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


def copy_profile(adapter_id: str) -> Dict[str, str]:
    return ADAPTER_COPY_PROFILE.get(adapter_id, ADAPTER_COPY_PROFILE["generic-operator"])


def theme_profile(adapter_id: str) -> Dict[str, str]:
    return ADAPTER_THEME_PROFILE.get(adapter_id, ADAPTER_THEME_PROFILE["generic-operator"])


def normalize_value_proposition(value: str, problem: str, adapter_id: str) -> str:
    if ". Designed for " in value:
        value = value.split(". Designed for ")[0].strip()

    if value:
        return value

    fallback = {
        "invoice-followup": "Recover overdue invoices with a focused daily follow-up workflow.",
        "chargeback-response": "Respond to chargebacks before deadlines with one evidence-first dispute flow.",
        "client-reporting": "Deliver on-time client reporting with a repeatable weekly workflow.",
    }
    return fallback.get(adapter_id, problem or "Improve one operational bottleneck with a focused pilot.")


def module_props(module_id: str, spec: Dict[str, Any], adapter_id: str) -> Dict[str, Any]:
    segment = spec.get("segment") if isinstance(spec.get("segment"), dict) else {}
    offer = spec.get("offer") if isinstance(spec.get("offer"), dict) else {}
    metrics = spec.get("metrics") if isinstance(spec.get("metrics"), dict) else {}

    role = ensure_text(segment.get("role"), "Operators")
    industry = ensure_text(segment.get("industry"), "Business operations")
    company_size = ensure_text(segment.get("company_size"), "1-20")
    segment_label = f"{role} · {industry} · {company_size}"

    profile = copy_profile(adapter_id)

    problem = ensure_text(spec.get("problem_statement"), "Core operational problem")
    raw_value = ensure_text(spec.get("value_proposition"), "")
    value = normalize_value_proposition(raw_value, problem=problem, adapter_id=adapter_id)

    proof_points = ensure_list(spec.get("proof_points"))
    if not proof_points:
        proof_points = [
            profile.get("benefit_lead", "Replace fragmented manual work with one repeatable workflow."),
            f"Keep the scope narrow for {role.lower()} teams while validating demand.",
            "Use one clear CTA and evidence-backed messaging to improve conversion quality.",
        ]

    faq = ensure_faq(spec.get("faq"))
    if not faq:
        faq = [
            {
                "question": "Is this a full platform rollout?",
                "answer": "No. This landing page validates one narrow outcome before broader scope expansion.",
            },
            {
                "question": "How quickly can we decide go/no-go?",
                "answer": "Run a focused 14-day test and decide with explicit success + kill criteria.",
            },
        ]

    headline = ensure_text(offer.get("headline"), value)
    subheadline = value
    if headline.lower() == subheadline.lower():
        subheadline = ensure_text(
            profile.get("benefit_lead"),
            f"Built for {role.lower()} teams that need a faster, repeatable operational workflow.",
        )

    if module_id == "hero_problem":
        return {
            "headline": headline,
            "subheadline": subheadline,
            "problem_statement": problem,
            "segment_label": segment_label,
        }

    if module_id == "problem_agitation":
        return {
            "title": ensure_text(profile.get("problem_title"), f"Why {role.lower()} teams cannot ignore this now"),
            "core_pain": problem,
            "pain_points": proof_points[:3],
            "cost_of_inaction": ensure_text(
                metrics.get("target"),
                "Delaying this workflow keeps adding avoidable operational drag.",
            ),
        }

    if module_id == "benefit_bullets":
        benefit_items = [
            ensure_text(profile.get("benefit_lead"), value),
            *proof_points[:2],
        ]
        benefit_items = list(dict.fromkeys([x for x in benefit_items if isinstance(x, str) and x.strip()]))
        return {
            "title": ensure_text(profile.get("benefit_title"), "What changes after adoption"),
            "items": benefit_items,
        }

    if module_id == "proof_points":
        return {
            "title": ensure_text(profile.get("proof_title"), "Proof and credibility"),
            "items": proof_points,
        }

    if module_id == "faq_list":
        return {
            "title": ensure_text(profile.get("faq_title"), "FAQ"),
            "items": faq,
        }

    if module_id == "cta_waitlist":
        return {
            "title": ensure_text(profile.get("cta_title"), "Start validation with one focused pilot"),
            "description": ensure_text(
                spec.get("cta_support_text"),
                ensure_text(profile.get("cta_description"), "Join early access and validate demand before expanding product scope."),
            ),
            "cta_label": ensure_text(offer.get("cta_label"), ensure_text(profile.get("cta_label"), "Join pilot")),
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
                "props": module_props(module_id=module_id, spec=spec, adapter_id=adapter_id),
            }
        )

    offer = spec.get("offer") if isinstance(spec.get("offer"), dict) else {}
    normalized_value = normalize_value_proposition(
        ensure_text(spec.get("value_proposition"), ""),
        ensure_text(spec.get("problem_statement"), ""),
        adapter_id,
    )
    meta_title = ensure_text(offer.get("headline"), ensure_text(normalized_value, "Landing page"))
    meta_desc = ensure_text(normalized_value, ensure_text(spec.get("problem_statement"), "Landing page"))

    theme_tokens = theme_profile(adapter_id)

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
        "theme": theme_profile(adapter_id),
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
                "try the workflow assistant",
                "focused landing validation",
                "pilot trust signals"
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
