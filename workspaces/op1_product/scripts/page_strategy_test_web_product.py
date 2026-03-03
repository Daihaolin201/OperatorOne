#!/usr/bin/env python3
"""Validate deployed page structure against compiled page spec."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple


def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def http_get(url: str, timeout: int = 20) -> Tuple[int, str]:
    req = urllib.request.Request(url=url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return int(e.code), e.read().decode("utf-8", errors="replace")


def run_with_retry(fn, retries: int, delay: float):
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return fn(), attempt
        except Exception as exc:  # pragma: no cover - operational retry
            last_error = exc
            if attempt < retries:
                time.sleep(delay)
    if last_error:
        raise last_error
    raise RuntimeError("Unknown retry failure")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run page strategy validation")
    parser.add_argument("--base-url", required=True, help="Deployed base URL")
    parser.add_argument("--page-spec", required=True, help="Compiled page spec path")
    parser.add_argument("--out", required=True, help="Output report JSON path")
    parser.add_argument("--retries", type=int, default=6)
    parser.add_argument("--retry-delay", type=float, default=2.5)
    return parser.parse_args()


def is_subsequence(expected: List[str], actual: List[str]) -> bool:
    if not expected:
        return True
    idx = 0
    for token in actual:
        if token == expected[idx]:
            idx += 1
            if idx == len(expected):
                return True
    return False


def main() -> int:
    args = parse_args()
    page_spec = read_json(args.page_spec)

    expected_modules = page_spec.get("testing", {}).get("expected_modules", [])
    if not isinstance(expected_modules, list):
        expected_modules = []

    max_primary_cta = int(page_spec.get("testing", {}).get("max_primary_cta_buttons", 1))

    base_url = args.base_url.rstrip("/")

    def fetch_homepage():
        status, body = http_get(f"{base_url}/")
        if status != 200:
            raise RuntimeError(f"Homepage status {status}")
        return body

    html_body, attempts = run_with_retry(fetch_homepage, retries=args.retries, delay=args.retry_delay)

    checks: List[Dict[str, Any]] = []
    failed = None

    module_matches = re.findall(r'data-module="([^"]+)"', html_body)
    primary_cta_count = len(re.findall(r'data-primary-cta="true"', html_body))

    # check 1: module presence
    missing = [m for m in expected_modules if m not in module_matches]
    if missing:
        failed = {
            "name": "module_presence",
            "status": "fail",
            "missing": missing,
            "detected": module_matches,
            "attempts": attempts,
        }
        checks.append(failed)
    else:
        checks.append(
            {
                "name": "module_presence",
                "status": "pass",
                "expected_count": len(expected_modules),
                "detected_count": len(module_matches),
                "attempts": attempts,
            }
        )

    # check 2: module order
    if failed is None:
        order_ok = is_subsequence(expected_modules, module_matches)
        if not order_ok:
            failed = {
                "name": "module_order",
                "status": "fail",
                "expected": expected_modules,
                "detected": module_matches,
            }
            checks.append(failed)
        else:
            checks.append(
                {
                    "name": "module_order",
                    "status": "pass",
                    "expected": expected_modules,
                    "detected": module_matches,
                }
            )

    # check 3: primary cta uniqueness
    if failed is None:
        if primary_cta_count <= 0 or primary_cta_count > max_primary_cta:
            failed = {
                "name": "primary_cta_uniqueness",
                "status": "fail",
                "primary_cta_count": primary_cta_count,
                "max_primary_cta": max_primary_cta,
            }
            checks.append(failed)
        else:
            checks.append(
                {
                    "name": "primary_cta_uniqueness",
                    "status": "pass",
                    "primary_cta_count": primary_cta_count,
                    "max_primary_cta": max_primary_cta,
                }
            )

    # check 4: legacy badge removed
    if failed is None:
        banned = "Build & Deploy v1.1"
        if banned in html_body:
            failed = {
                "name": "legacy_badge_removed",
                "status": "fail",
                "reason": f"Found banned label: {banned}",
            }
            checks.append(failed)
        else:
            checks.append(
                {
                    "name": "legacy_badge_removed",
                    "status": "pass",
                }
            )

    report = {
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "base_url": base_url,
        "project_id": page_spec.get("project_id"),
        "adapter_name": page_spec.get("adapter_name"),
        "layout_profile": page_spec.get("layout_profile"),
        "status": "passed" if failed is None else "failed",
        "checks": checks,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return 0 if failed is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
