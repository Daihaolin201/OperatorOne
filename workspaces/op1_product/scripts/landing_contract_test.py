#!/usr/bin/env python3
"""Validate create_landing_pages_v1 package contract and quality gates."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate landing package contract")
    parser.add_argument("--landing-package", required=True, help="Path to landing_package.json")
    parser.add_argument("--out", required=True, help="Output report path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    package_path = Path(args.landing_package).resolve()
    out_path = Path(args.out).resolve()

    payload = read_json(package_path)
    checks: List[Dict[str, Any]] = []
    failed: Dict[str, Any] | None = None

    def push(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failed
        row = {"name": name, "status": "pass" if ok else "fail", "detail": detail}
        checks.append(row)
        if not ok and failed is None:
            failed = row

    push(
        "contract_identity",
        payload.get("capability") == "create_landing_pages_v1" and payload.get("mode") == "mode_c_only",
        "capability/mode must match contract",
    )

    required_keys = [
        "status",
        "selected_opportunity",
        "preflight",
        "landing_package",
        "build_inputs",
        "quality_gates",
    ]
    missing = [k for k in required_keys if k not in payload]
    push("required_keys", len(missing) == 0, f"missing={missing}")

    preflight = payload.get("preflight", {}) if isinstance(payload.get("preflight"), dict) else {}
    trace = preflight.get("evidence_traceability_gate", {}) if isinstance(preflight.get("evidence_traceability_gate"), dict) else {}
    coverage = float(trace.get("coverage_ratio", 0.0))
    unmapped = trace.get("unmapped_claims", []) if isinstance(trace.get("unmapped_claims"), list) else []
    push("traceability_gate", coverage >= 1.0 and len(unmapped) == 0, f"coverage={coverage}; unmapped={unmapped}")

    lp = payload.get("landing_package", {}) if isinstance(payload.get("landing_package"), dict) else {}
    section_plan = lp.get("section_plan", []) if isinstance(lp.get("section_plan"), list) else []
    section_ids = [str(row.get("section_id")) for row in section_plan if isinstance(row, dict)]
    push(
        "section_baseline",
        "hero_problem" in section_ids and "cta_waitlist" in section_ids and len(section_ids) >= 5,
        f"section_ids={section_ids}",
    )

    cta_plan = lp.get("cta_plan", {}) if isinstance(lp.get("cta_plan"), dict) else {}
    primary = cta_plan.get("primary", {}) if isinstance(cta_plan.get("primary"), dict) else {}
    push(
        "cta_baseline",
        bool(primary.get("label")) and primary.get("module_id") == "cta_waitlist",
        f"primary={primary}",
    )

    trace_map = lp.get("traceability_map", []) if isinstance(lp.get("traceability_map"), list) else []
    trace_ok = True
    for row in trace_map:
        if not isinstance(row, dict):
            trace_ok = False
            break
        refs = row.get("evidence_refs")
        if not isinstance(refs, list) or len(refs) == 0:
            trace_ok = False
            break
    push("traceability_map_shape", trace_ok and len(trace_map) >= 3, f"claim_count={len(trace_map)}")

    qg = payload.get("quality_gates", []) if isinstance(payload.get("quality_gates"), list) else []
    gate_failures = [row for row in qg if isinstance(row, dict) and row.get("status") == "fail"]
    status = payload.get("status")
    consistency_ok = (status == "blocked" and gate_failures) or (status != "blocked" and not gate_failures)
    push("status_gate_consistency", consistency_ok, f"status={status}; failures={len(gate_failures)}")

    report = {
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "landing_package": str(package_path),
        "status": "passed" if failed is None else "failed",
        "checks": checks,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return 0 if failed is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
