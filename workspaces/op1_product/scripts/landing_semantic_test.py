#!/usr/bin/env python3
"""Validate landing-package semantics independent of deployment."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Landing semantic checks")
    parser.add_argument("--landing-package", required=True, help="Path to landing_package.json")
    parser.add_argument("--page-spec", required=True, help="Path to compiled page_spec.json")
    parser.add_argument("--out", required=True, help="Output report path")
    return parser.parse_args()


def ensure_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if isinstance(v, str) and str(v).strip()]


def main() -> int:
    args = parse_args()
    landing_path = Path(args.landing_package).resolve()
    page_spec_path = Path(args.page_spec).resolve()
    out_path = Path(args.out).resolve()

    landing = read_json(landing_path)
    page_spec = read_json(page_spec_path)

    checks: List[Dict[str, Any]] = []
    failed = None

    def push(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failed
        row = {"name": name, "status": "pass" if ok else "fail", "detail": detail}
        checks.append(row)
        if not ok and failed is None:
            failed = row

    mode = str(page_spec.get("meta", {}).get("page_mode") or page_spec.get("testing", {}).get("page_mode") or "")
    push("page_mode_landing", mode == "landing", f"page_mode={mode}")

    modules = page_spec.get("modules", []) if isinstance(page_spec.get("modules"), list) else []
    module_ids = [str(m.get("module_id", "")).strip() for m in modules if isinstance(m, dict)]

    required = set(ensure_list(page_spec.get("testing", {}).get("required_modules")))
    forbidden = set(ensure_list(page_spec.get("testing", {}).get("forbidden_modules")))

    missing_required = sorted([m for m in required if m not in module_ids])
    forbidden_present = sorted([m for m in forbidden if m in module_ids])
    push("required_modules_present", len(missing_required) == 0, f"missing={missing_required}")
    push("forbidden_modules_absent", len(forbidden_present) == 0, f"present={forbidden_present}")

    section_ids = [
        str(row.get("section_id", "")).strip()
        for row in (landing.get("landing_package", {}).get("section_plan", []) or [])
        if isinstance(row, dict)
    ]
    push(
        "section_plan_alignment",
        module_ids == section_ids,
        f"modules={module_ids}; sections={section_ids}",
    )

    hierarchy = landing.get("landing_package", {}).get("message_hierarchy", {})
    hero = str(hierarchy.get("hero_headline", "")).strip()
    subhero = str(hierarchy.get("hero_subheadline", "")).strip()
    problem = str(hierarchy.get("problem_statement", "")).strip()
    hero_ok = bool(hero and subhero and problem)
    push("hero_problem_message_present", hero_ok, f"hero={bool(hero)}; subhero={bool(subhero)}; problem={bool(problem)}")

    forbidden_terms = [
        str(t).lower()
        for t in (page_spec.get("testing", {}).get("forbidden_terms", []) or [])
        if isinstance(t, str) and t.strip()
    ]
    text_blob = json.dumps(landing.get("landing_package", {}), ensure_ascii=False).lower()
    term_hits = [t for t in forbidden_terms if t in text_blob]
    push("no_demo_terms_in_landing_package", len(term_hits) == 0, f"hits={term_hits}")

    trace = landing.get("preflight", {}).get("evidence_traceability_gate", {})
    coverage = float(trace.get("coverage_ratio", 0.0))
    push("traceability_coverage", coverage >= 1.0 or landing.get("status") == "blocked", f"coverage={coverage}")

    report = {
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "landing_package": str(landing_path),
        "page_spec": str(page_spec_path),
        "status": "passed" if failed is None else "failed",
        "checks": checks,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if failed is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
