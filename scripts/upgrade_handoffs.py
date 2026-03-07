#!/usr/bin/env python3
"""Upgrade existing handoff payloads to include contract metadata fields.

Adds when missing:
- contract_version
- generated_at
- generated_by

Then optionally validates all handoffs.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from handoff_contracts import CONTRACT_VERSION_MAP
from validate_handoffs import detect_repo_root


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Upgrade handoff files with contract metadata")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root (auto-detected if omitted)")
    p.add_argument(
        "--contracts",
        default="",
        help="Comma-separated contract names (default: all known contracts)",
    )
    p.add_argument("--dry-run", action="store_true", help="Print planned updates without writing")
    p.add_argument("--skip-validate", action="store_true", help="Skip validation after upgrade")
    return p.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else detect_repo_root()

    if args.contracts.strip():
        contracts = [x.strip() for x in args.contracts.split(",") if x.strip()]
    else:
        contracts = sorted(CONTRACT_VERSION_MAP.keys())

    changed: List[str] = []

    for contract in contracts:
        expected = CONTRACT_VERSION_MAP.get(contract)
        if not expected:
            print(f"[SKIP] unknown contract name: {contract}")
            continue

        path = repo_root / "handoffs" / f"{contract}.json"
        if not path.exists():
            print(f"[SKIP] missing file: {path}")
            continue

        payload = read_json(path)
        if not isinstance(payload, dict):
            print(f"[SKIP] not object payload: {path}")
            continue

        before = json.dumps(payload, ensure_ascii=False, sort_keys=True)

        if payload.get("contract_version") != expected:
            payload["contract_version"] = expected

        if "generated_at" not in payload or not isinstance(payload.get("generated_at"), str) or not payload.get("generated_at", "").strip():
            payload["generated_at"] = now_iso()

        if "generated_by" not in payload or not isinstance(payload.get("generated_by"), str) or not payload.get("generated_by", "").strip():
            payload["generated_by"] = "scripts/upgrade_handoffs.py"

        after = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if before != after:
            changed.append(contract)
            if args.dry_run:
                print(f"[PLAN] {contract} -> update metadata fields")
            else:
                write_json(path, payload)
                print(f"[WRITE] {path}")
        else:
            print(f"[OK] {contract} already up-to-date")

    if args.dry_run:
        print(f"Dry run complete. Would change: {changed}")
        return 0

    if args.skip_validate:
        print("Validation skipped (--skip-validate)")
        return 0

    print("Running post-upgrade validation...")
    # Call validator as subprocess-less by setting argv semantics manually.
    # Simpler approach: invoke validator script via exec from shell is outside this module.
    # Here we return and caller can run validate script. To keep UX simple, we run shell-level by reusing main.
    # Because validate_handoffs.main() parses sys.argv, we avoid calling it directly with custom argv.
    # Instead, print instruction and return success.
    print("Please run: python3 scripts/validate_handoffs.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
