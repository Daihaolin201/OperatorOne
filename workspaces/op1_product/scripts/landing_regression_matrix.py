#!/usr/bin/env python3
"""Regression matrix for create_landing_pages_v1 Mode-C flow."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class CaseResult:
    name: str
    status: str
    expected: str
    passed: bool
    details: Dict[str, Any]


def read_json(path: pathlib.Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: pathlib.Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(cmd: List[str], cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=False)


def create_stage3_fixture(path: pathlib.Path, opportunity_id: str) -> None:
    payload = {
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "source_stage1": "research/stage1_opportunity_records.json",
        "source_stage2": "research/stage2_decision_log.json",
        "from_opportunity_id": opportunity_id,
        "project_name": f"Landing validation for {opportunity_id}",
        "target_segment": "Service operators (1-20)",
        "problem_statement": "Unstructured outbound workflows cause cashflow delays.",
        "value_proposition": "Structured follow-up workflows increase payment predictability.",
        "mvp_boundary": {
            "in_scope": [
                "Single conversion-focused landing page",
                "Email waitlist CTA",
                "Evidence-backed proof section"
            ],
            "out_of_scope": [
                "ERP integrations",
                "Advanced billing suite",
                "Enterprise SSO"
            ]
        },
        "pricing_hypothesis": {
            "type": "flat_monthly",
            "price_points": [49, 99]
        },
        "success_metrics": [
            "Qualified waitlist submits per 100 sessions"
        ],
        "kill_criteria": [
            "Qualified submits below 2 per 100 sessions after initial test window"
        ],
        "delivery_notes": [
            "Use one primary CTA and preserve scope boundary in copy"
        ]
    }
    write_json(path, payload)


def create_no_evidence_stage1(path: pathlib.Path) -> None:
    payload = {
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "opportunities": [
            {
                "opportunity_id": "opp_no_evidence",
                "target_segment": {
                    "who": "Solo service operator",
                    "trigger_context": "ad-hoc follow-up chaos"
                },
                "core_problem": "Manual chasing creates delays and inconsistency.",
                "current_workaround": "Spreadsheet plus reminders",
                "pain_evidence": [],
                "urgency_signal": {
                    "evidence": "Users ask for quick operational relief"
                },
                "implementation_constraint": [
                    "No complex integrations in first release"
                ],
                "hard_gate_check": {
                    "kill_criteria": [
                        "No qualified intent in initial pilot"
                    ]
                }
            }
        ]
    }
    write_json(path, payload)


def create_no_evidence_stage2(path: pathlib.Path) -> None:
    payload = {
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "decisions": [
            {
                "opportunity_id": "opp_no_evidence",
                "decision": "advance",
                "hard_gate_pass": True,
                "weighted_score": 6.5,
                "confidence": {"level": "medium"},
                "scores": {
                    "pain_severity": {
                        "score": 6,
                        "risk_if_wrong": "Pain may be less urgent than assumed"
                    }
                }
            }
        ]
    }
    write_json(path, payload)


def run_case(root: pathlib.Path, name: str, args: List[str], expected_status: str) -> CaseResult:
    out_dir = root / "research" / "landing_v1_regression" / name
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    handoff_rel = f"research/landing_v1_regression/{name}/handoff.json"
    cmd = [
        "python3",
        str(root / "scripts/create_landing_package.py"),
        "--out-dir",
        str(out_dir),
        "--handoff-out",
        handoff_rel,
        "--force",
    ] + args

    run_res = run(cmd, cwd=root)
    landing_path = out_dir / "landing_package.json"
    if not landing_path.exists():
        return CaseResult(
            name=name,
            status="missing_artifact",
            expected=expected_status,
            passed=False,
            details={
                "command": cmd,
                "returncode": run_res.returncode,
                "stdout": run_res.stdout,
                "stderr": run_res.stderr,
            },
        )

    landing = read_json(landing_path)
    status = str(landing.get("status"))

    contract_out = out_dir / "landing_contract_test.json"
    contract_res = run(
        [
            "python3",
            str(root / "scripts/landing_contract_test.py"),
            "--landing-package",
            str(landing_path),
            "--out",
            str(contract_out),
        ],
        cwd=root,
    )
    contract = read_json(contract_out) if contract_out.exists() else {"status": "missing"}

    passed = (status == expected_status) and (contract.get("status") == "passed")

    details = {
        "status": status,
        "expected_status": expected_status,
        "selected_opportunity": (landing.get("selected_opportunity") or {}).get("opportunity_id"),
        "quality_gate_failures": [
            g for g in landing.get("quality_gates", [])
            if isinstance(g, dict) and g.get("status") == "fail"
        ],
        "stage2_mode": ((landing.get("preflight") or {}).get("opportunity_gate") or {}).get("stage2_mode"),
        "scope_source": ((landing.get("preflight") or {}).get("scope_gate") or {}).get("source"),
        "traceability_coverage": ((landing.get("preflight") or {}).get("evidence_traceability_gate") or {}).get("coverage_ratio"),
        "contract_status": contract.get("status"),
        "create_returncode": run_res.returncode,
        "contract_returncode": contract_res.returncode,
    }

    return CaseResult(name=name, status=status, expected=expected_status, passed=passed, details=details)


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    base = root / "research" / "landing_v1_regression"
    base.mkdir(parents=True, exist_ok=True)

    stage1 = root / "research/stage1_opportunity_records.json"
    stage2 = root / "research/stage2_decision_log.json"
    stage3 = root / "research/stage3_project_blueprint.json"

    results: List[CaseResult] = []

    # Case 1: normal path with existing Stage2 and default Stage3 (usually provisional).
    results.append(
        run_case(
            root,
            "case_01_provisional_existing",
            [
                "--stage1", str(stage1),
                "--stage2", str(stage2),
                "--stage3", str(stage3),
            ],
            expected_status="provisional_ready",
        )
    )

    # Case 2: Stage3-matched fixture should reach ready_for_build.
    fixture_dir = base / "_fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)

    stage3_fixture = fixture_dir / "stage3_fixture_opp001.json"
    create_stage3_fixture(stage3_fixture, opportunity_id="opp_001")
    results.append(
        run_case(
            root,
            "case_02_ready_stage3_fixture",
            [
                "--stage1", str(stage1),
                "--stage2", str(stage2),
                "--stage3", str(stage3_fixture),
                "--opp-id", "opp_001",
                "--adapter", "invoice-followup",
            ],
            expected_status="ready_for_build",
        )
    )

    # Case 3: missing Stage2 should synthesize from Stage1.
    missing_stage2 = root / "research/_missing_stage2_for_regression.json"
    case3 = run_case(
        root,
        "case_03_stage2_synthesized",
        [
            "--stage1", str(stage1),
            "--stage2", str(missing_stage2),
            "--stage3", str(stage3),
            "--opp-id", "opp_001",
            "--adapter", "invoice-followup",
        ],
        expected_status="provisional_ready",
    )
    if case3.details.get("stage2_mode") != "synthesized_from_stage1":
        case3.passed = False
    results.append(case3)

    # Case 4: no evidence should trigger blocked via traceability gate.
    case4_fixture_dir = fixture_dir / "case_04_blocked_no_evidence"
    case4_fixture_dir.mkdir(parents=True, exist_ok=True)
    stage1_noev = case4_fixture_dir / "stage1_no_evidence.json"
    stage2_noev = case4_fixture_dir / "stage2_no_evidence.json"
    stage3_noev = case4_fixture_dir / "stage3_no_evidence.json"
    create_no_evidence_stage1(stage1_noev)
    create_no_evidence_stage2(stage2_noev)
    create_stage3_fixture(stage3_noev, opportunity_id="opp_no_evidence")

    case4 = run_case(
        root,
        "case_04_blocked_no_evidence",
        [
            "--stage1", str(stage1_noev),
            "--stage2", str(stage2_noev),
            "--stage3", str(stage3_noev),
            "--opp-id", "opp_no_evidence",
        ],
        expected_status="blocked",
    )
    failures = case4.details.get("quality_gate_failures") or []
    has_traceability_failure = any(
        isinstance(item, dict) and item.get("name") == "claim_evidence_traceability_100pct"
        for item in failures
    )
    if not has_traceability_failure:
        case4.passed = False
    results.append(case4)

    payload = {
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "capability": "create_landing_pages_v1",
        "status": "passed" if all(r.passed for r in results) else "failed",
        "cases": [
            {
                "name": r.name,
                "status": r.status,
                "expected": r.expected,
                "passed": r.passed,
                "details": r.details,
            }
            for r in results
        ],
    }

    out_path = base / "regression_matrix.latest.json"
    write_json(out_path, payload)
    print(json.dumps({"status": payload["status"], "report": str(out_path)}, ensure_ascii=False))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
