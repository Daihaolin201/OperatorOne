#!/usr/bin/env python3
"""Validate OperatorOne handoff JSON contracts.

Usage:
  python3 scripts/validate_handoffs.py
  python3 scripts/validate_handoffs.py --contracts product_to_marketing,marketing_to_sales
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from handoff_contracts import CONTRACT_VERSION_MAP, validate_contract_payload


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate handoff contracts")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root (auto-detected if omitted)")
    p.add_argument(
        "--contracts",
        default="",
        help="Comma-separated contract names (default: validate all known contracts)",
    )
    p.add_argument(
        "--report-out",
        default="handoffs/_meta/validation_report.latest.json",
        help="Validation report output path (relative to repo root)",
    )
    p.add_argument("--fail-on-warning", action="store_true", help="Non-zero exit when warnings exist")
    return p.parse_args()


def detect_repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        if (candidate / "handoffs").exists() and (candidate / "workspaces").exists():
            return candidate
    raise FileNotFoundError("Cannot detect OperatorOne repo root")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else detect_repo_root()

    if args.contracts.strip():
        contracts = [x.strip() for x in args.contracts.split(",") if x.strip()]
    else:
        contracts = sorted(CONTRACT_VERSION_MAP.keys())

    report_rows: List[Dict[str, Any]] = []
    total_errors = 0
    total_warnings = 0

    for contract in contracts:
        path = repo_root / "handoffs" / f"{contract}.json"
        row: Dict[str, Any] = {
            "contract": contract,
            "path": str(path),
            "exists": path.exists(),
            "errors": [],
            "warnings": [],
            "status": "pass",
        }

        if not path.exists():
            row["errors"].append("file does not exist")
            row["status"] = "fail"
            total_errors += 1
            report_rows.append(row)
            continue

        try:
            payload = read_json(path)
        except Exception as exc:  # noqa: BLE001
            row["errors"].append(f"json decode error: {exc}")
            row["status"] = "fail"
            total_errors += 1
            report_rows.append(row)
            continue

        errors, warnings = validate_contract_payload(contract, payload)
        row["errors"] = errors
        row["warnings"] = warnings
        total_errors += len(errors)
        total_warnings += len(warnings)

        if errors:
            row["status"] = "fail"
        elif warnings:
            row["status"] = "warn"
        else:
            row["status"] = "pass"

        report_rows.append(row)

    report = {
        "generated_at": now_iso(),
        "repo_root": str(repo_root),
        "contracts_checked": contracts,
        "error_count": total_errors,
        "warning_count": total_warnings,
        "results": report_rows,
    }

    out_path = (repo_root / args.report_out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for row in report_rows:
        print(f"[{row['status'].upper():4}] {row['contract']}")
        for e in row["errors"]:
            print(f"  - ERROR: {e}")
        for w in row["warnings"]:
            print(f"  - WARN:  {w}")

    print(f"\nReport: {out_path}")
    print(f"Errors={total_errors}, Warnings={total_warnings}")

    if total_errors > 0:
        return 1
    if args.fail_on_warning and total_warnings > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
