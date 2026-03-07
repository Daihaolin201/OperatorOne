#!/usr/bin/env python3
"""Check i18n key parity between en/ and zh/ locale directories.

Usage:
  python3 scripts/check-i18n-parity.py
  python3 scripts/check-i18n-parity.py --locales-root packages/i18n/locales
  python3 scripts/check-i18n-parity.py --repo-root .
  python3 scripts/check-i18n-parity.py --fail-on-missing-only

Exit codes:
  0  All namespace key sets match between en/ and zh/
  1  One or more namespaces have missing or extra keys (parity failure)

Behaviour:
  - Recursively finds all *.json files under locales/en/ and locales/zh/
  - Flattens each JSON object to dot-notation keys (e.g. "nav.home")
  - Reports per-namespace:
      MISSING_FROM_ZH  keys present in en but absent in zh
      EXTRA_IN_ZH      keys present in zh but absent in en (also a parity issue)
  - Detects namespace files present in one locale but missing entirely from the other
  - Exits nonzero (exit code 1) if any discrepancy is found
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Set


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="i18n key-parity check (en ↔ zh)")
    p.add_argument(
        "--repo-root",
        default="",
        help="Repository root (auto-detected if omitted)",
    )
    p.add_argument(
        "--locales-root",
        default="",
        help="Path to locales/ directory relative to repo root (default: packages/i18n/src/locales)",
    )
    return p.parse_args()


def detect_repo_root() -> Path:
    """Walk up from this script to find the repo root."""
    here = Path(__file__).resolve()
    for candidate in [here.parent.parent, *here.parent.parents]:
        if (candidate / "packages").exists() or (candidate / "handoffs").exists():
            return candidate
    return here.parent.parent


def flatten_keys(obj: object, prefix: str = "") -> Set[str]:
    """Recursively flatten a JSON object to a set of dot-notation keys."""
    keys: Set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                keys.update(flatten_keys(v, full_key))
            else:
                keys.add(full_key)
    return keys


def load_namespace_keys(locale_dir: Path) -> Dict[str, Set[str]]:
    """Return {namespace: set_of_flat_keys} for all *.json files in a locale dir."""
    result: Dict[str, Set[str]] = {}
    for json_file in sorted(locale_dir.rglob("*.json")):
        rel = json_file.relative_to(locale_dir)
        namespace = str(rel.with_suffix(""))
        try:
            obj = json.loads(json_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"[ERROR] Could not parse {json_file}: {exc}", file=sys.stderr)
            sys.exit(1)
        result[namespace] = flatten_keys(obj)
    return result


def main() -> int:
    args = parse_args()

    if args.repo_root:
        repo_root = Path(args.repo_root).resolve()
    else:
        repo_root = detect_repo_root()

    if args.locales_root:
        locales_root = (repo_root / args.locales_root).resolve()
    else:
        locales_root = repo_root / "packages" / "i18n" / "src" / "locales"

    en_dir = locales_root / "en"
    zh_dir = locales_root / "zh"

    if not en_dir.exists():
        print(f"[ERROR] en/ locale directory not found: {en_dir}", file=sys.stderr)
        return 1
    if not zh_dir.exists():
        print(f"[ERROR] zh/ locale directory not found: {zh_dir}", file=sys.stderr)
        return 1

    print(f"Checking i18n parity: {en_dir} ↔ {zh_dir}")
    print("─" * 60)

    en_namespaces = load_namespace_keys(en_dir)
    zh_namespaces = load_namespace_keys(zh_dir)

    all_namespaces = sorted(set(en_namespaces) | set(zh_namespaces))

    failures = 0

    for ns in all_namespaces:
        en_keys = en_namespaces.get(ns)
        zh_keys = zh_namespaces.get(ns)

        if en_keys is None:
            print(f"[FAIL] namespace '{ns}': present in zh/ but MISSING from en/")
            failures += 1
            continue
        if zh_keys is None:
            print(f"[FAIL] namespace '{ns}': present in en/ but MISSING from zh/")
            failures += 1
            continue

        missing_from_zh = sorted(en_keys - zh_keys)
        extra_in_zh = sorted(zh_keys - en_keys)

        ns_ok = not missing_from_zh and not extra_in_zh

        if ns_ok:
            print(f"[PASS] namespace '{ns}': {len(en_keys)} keys — perfectly in parity")
        else:
            failures += 1
            print(f"[FAIL] namespace '{ns}': key mismatch detected")
            if missing_from_zh:
                print(f"  MISSING_FROM_ZH ({len(missing_from_zh)}):")
                for k in missing_from_zh:
                    print(f"    - {k}")
            if extra_in_zh:
                print(f"  EXTRA_IN_ZH ({len(extra_in_zh)}):")
                for k in extra_in_zh:
                    print(f"    + {k}")

    print("─" * 60)
    total_ns = len(all_namespaces)
    passed_ns = total_ns - failures

    if failures == 0:
        print(f"PASS: all {total_ns} namespace(s) have matching key sets (en ↔ zh).")
        return 0
    else:
        print(
            f"FAIL: {failures}/{total_ns} namespace(s) have i18n key parity issues."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
