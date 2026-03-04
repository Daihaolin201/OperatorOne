#!/usr/bin/env python3
"""Build human + machine indexes for Stage2/Stage3 online demo URLs."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
from typing import Any, Dict, List


def read_json(path: pathlib.Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def dedupe_keep_order(items: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def maybe_url(value: Any) -> str | None:
    if isinstance(value, str) and value.startswith("http"):
        return value
    return None


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]

    stage2_run_path = root / "research/stage2_web_product/run.latest.json"
    stage2_matrix_path = root / "research/stage2_web_product/artifacts/modular_matrix/generalization_matrix.json"
    stage3_run_path = root / "research/stage3_landing_launch/run.latest.json"
    stage3_reg_path = root / "research/stage3_landing_launch/regression/stage3_capability_validation.latest.json"

    out_json_path = root / "research/live_examples.latest.json"
    out_md_path = root / "research/LIVE_EXAMPLES.md"

    stage2_run = read_json(stage2_run_path) or {}
    stage2_matrix = read_json(stage2_matrix_path) or {}
    stage3_run = read_json(stage3_run_path) or {}
    stage3_reg = read_json(stage3_reg_path) or {}

    stage2_run_url = maybe_url((stage2_run.get("output") or {}).get("deployed_url"))

    matrix_projects: List[Dict[str, Any]] = []
    stage2_matrix_urls: List[str] = []
    for project in stage2_matrix.get("projects", []) if isinstance(stage2_matrix.get("projects"), list) else []:
        if not isinstance(project, dict):
            continue
        url = maybe_url(project.get("deployed_url"))
        if url:
            stage2_matrix_urls.append(url)
        matrix_projects.append(
            {
                "adapter_name": project.get("adapter_name"),
                "project_id": project.get("project_id"),
                "overall_status": (project.get("status") or {}).get("overall") if isinstance(project.get("status"), dict) else None,
                "url": url,
            }
        )

    stage3_run_url = maybe_url((stage3_run.get("deploy") or {}).get("url"))

    reg_cases: List[Dict[str, Any]] = []
    stage3_case_urls: List[str] = []
    for case in stage3_reg.get("cases", []) if isinstance(stage3_reg.get("cases"), list) else []:
        if not isinstance(case, dict):
            continue
        url = maybe_url(case.get("public_url"))
        if url:
            stage3_case_urls.append(url)
        tests = case.get("tests") if isinstance(case.get("tests"), dict) else {}
        reg_cases.append(
            {
                "opportunity_id": case.get("opportunity_id"),
                "landing_status": case.get("landing_status"),
                "tests": {
                    "smoke": tests.get("smoke"),
                    "page_strategy": tests.get("page_strategy"),
                    "business": tests.get("business"),
                },
                "url": url,
            }
        )

    stage2_online = dedupe_keep_order(([stage2_run_url] if stage2_run_url else []) + stage2_matrix_urls)
    stage3_online = dedupe_keep_order(([stage3_run_url] if stage3_run_url else []) + stage3_case_urls)
    all_online = dedupe_keep_order(stage2_online + stage3_online)

    payload: Dict[str, Any] = {
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "sources": {
            "stage2_run": str(stage2_run_path.relative_to(root)),
            "stage2_matrix": str(stage2_matrix_path.relative_to(root)),
            "stage3_run": str(stage3_run_path.relative_to(root)),
            "stage3_regression": str(stage3_reg_path.relative_to(root)),
        },
        "stage2": {
            "latest_run": {
                "status": stage2_run.get("status"),
                "run_id": stage2_run.get("run_id"),
                "generated_at": stage2_run.get("generated_at"),
                "url": stage2_run_url,
            },
            "matrix": {
                "all_passed": stage2_matrix.get("all_passed"),
                "project_count": stage2_matrix.get("project_count"),
                "projects": matrix_projects,
            },
            "online_examples": stage2_online,
        },
        "stage3": {
            "latest_run": {
                "status": stage3_run.get("status"),
                "run_id": stage3_run.get("run_id"),
                "generated_at": stage3_run.get("generated_at"),
                "deploy_status": (stage3_run.get("deploy") or {}).get("status") if isinstance(stage3_run.get("deploy"), dict) else None,
                "deploy_requested": (stage3_run.get("deploy") or {}).get("requested") if isinstance(stage3_run.get("deploy"), dict) else None,
                "url": stage3_run_url,
                "selected_opportunity": stage3_run.get("selected_opportunity"),
            },
            "regression": {
                "status": stage3_reg.get("status"),
                "generated_at": stage3_reg.get("generated_at"),
                "case_count": len(reg_cases),
                "cases": reg_cases,
            },
            "online_examples": stage3_online,
        },
        "all_online_examples": all_online,
    }

    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines: List[str] = []
    lines.append("# Live Examples Index")
    lines.append("")
    lines.append(f"Generated at: `{payload['generated_at']}`")
    lines.append("")
    lines.append("## Stage2 — Build & Deploy online examples")
    lines.append("")
    if stage2_online:
        for url in stage2_online:
            lines.append(f"- {url}")
    else:
        lines.append("- _No Stage2 online URL found yet._")
    lines.append("")
    lines.append("Machine source:")
    lines.append(f"- `{payload['sources']['stage2_run']}`")
    lines.append(f"- `{payload['sources']['stage2_matrix']}`")
    lines.append("")
    lines.append("### Stage2 matrix details")
    lines.append("")
    lines.append("| adapter | project_id | status | url |")
    lines.append("|---|---|---|---|")
    if matrix_projects:
        for row in matrix_projects:
            lines.append(
                f"| {row.get('adapter_name') or '-'} | {row.get('project_id') or '-'} | {row.get('overall_status') or '-'} | {row.get('url') or '-'} |"
            )
    else:
        lines.append("| - | - | - | - |")

    lines.append("")
    lines.append("## Stage3 — Landing online examples")
    lines.append("")
    if stage3_online:
        for url in stage3_online:
            lines.append(f"- {url}")
    else:
        lines.append("- _No Stage3 online URL found yet._")
    lines.append("")
    lines.append("Machine source:")
    lines.append(f"- `{payload['sources']['stage3_run']}`")
    lines.append(f"- `{payload['sources']['stage3_regression']}`")
    lines.append("")
    lines.append("### Stage3 regression details")
    lines.append("")
    lines.append("| opportunity | landing_status | smoke | page_strategy | business | url |")
    lines.append("|---|---|---|---|---|---|")
    if reg_cases:
        for row in reg_cases:
            tests = row.get("tests") if isinstance(row.get("tests"), dict) else {}
            lines.append(
                f"| {row.get('opportunity_id') or '-'} | {row.get('landing_status') or '-'} | {tests.get('smoke') or '-'} | {tests.get('page_strategy') or '-'} | {tests.get('business') or '-'} | {row.get('url') or '-'} |"
            )
    else:
        lines.append("| - | - | - | - | - | - |")

    lines.append("")
    lines.append("## Machine index")
    lines.append("")
    lines.append(f"- `research/live_examples.latest.json`")

    out_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
