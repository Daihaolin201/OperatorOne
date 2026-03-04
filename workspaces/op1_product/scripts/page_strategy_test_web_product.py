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


def http_get(url: str, timeout: int = 20) -> Tuple[int, str, Dict[str, str]]:
    req = urllib.request.Request(url=url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            headers = {str(k).lower(): str(v) for k, v in resp.headers.items()}
            return int(resp.status), resp.read().decode("utf-8", errors="replace"), headers
    except urllib.error.HTTPError as e:
        headers = {str(k).lower(): str(v) for k, v in e.headers.items()} if e.headers else {}
        return int(e.code), e.read().decode("utf-8", errors="replace"), headers


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
    require_viewport_meta = bool(page_spec.get("testing", {}).get("require_viewport_meta", False))
    responsive_markers = page_spec.get("testing", {}).get("responsive_markers", [])
    if not isinstance(responsive_markers, list):
        responsive_markers = []
    device_profiles = page_spec.get("testing", {}).get("device_profiles", [])
    if not isinstance(device_profiles, list):
        device_profiles = []
    security_headers = page_spec.get("testing", {}).get("security_headers", [])
    if not isinstance(security_headers, list):
        security_headers = []

    page_mode = str(page_spec.get("testing", {}).get("page_mode") or page_spec.get("meta", {}).get("page_mode") or "web_product")
    required_modules = page_spec.get("testing", {}).get("required_modules", [])
    if not isinstance(required_modules, list):
        required_modules = []
    forbidden_modules = page_spec.get("testing", {}).get("forbidden_modules", [])
    if not isinstance(forbidden_modules, list):
        forbidden_modules = []
    lp_section_whitelist = page_spec.get("testing", {}).get("lp_section_whitelist", [])
    if not isinstance(lp_section_whitelist, list):
        lp_section_whitelist = []
    forbidden_terms = page_spec.get("testing", {}).get("forbidden_terms", [])
    if not isinstance(forbidden_terms, list):
        forbidden_terms = []

    base_url = args.base_url.rstrip("/")

    def fetch_homepage():
        status, body, headers = http_get(f"{base_url}/")
        if status != 200:
            raise RuntimeError(f"Homepage status {status}")
        return body, headers

    def fetch_stylesheet():
        status, body, _headers = http_get(f"{base_url}/styles.css")
        if status != 200:
            raise RuntimeError(f"Stylesheet status {status}")
        return body

    (html_body, homepage_headers), attempts = run_with_retry(fetch_homepage, retries=args.retries, delay=args.retry_delay)
    css_body, css_attempts = run_with_retry(fetch_stylesheet, retries=args.retries, delay=args.retry_delay)

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

    # check 3: landing module constraints
    if failed is None and page_mode == "landing":
        missing_required = [m for m in required_modules if m not in module_matches]
        present_forbidden = [m for m in forbidden_modules if m in module_matches]
        unknown_modules = [m for m in module_matches if lp_section_whitelist and m not in lp_section_whitelist]

        if missing_required or present_forbidden or unknown_modules:
            failed = {
                "name": "landing_module_constraints",
                "status": "fail",
                "missing_required": missing_required,
                "present_forbidden": present_forbidden,
                "outside_whitelist": unknown_modules,
            }
            checks.append(failed)
        else:
            checks.append(
                {
                    "name": "landing_module_constraints",
                    "status": "pass",
                    "required_modules": required_modules,
                    "forbidden_modules": forbidden_modules,
                }
            )

    # check 4: primary cta uniqueness
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

    # check 5: legacy badge removed
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

    # check 6: landing semantics
    if failed is None and page_mode == "landing":
        mode_marker_ok = 'data-page-mode="landing"' in html_body
        forbidden_hits = [t for t in forbidden_terms if isinstance(t, str) and t and t.lower() in html_body.lower()]
        workflow_form_present = 'id="workflow-form"' in html_body

        if (not mode_marker_ok) or forbidden_hits or workflow_form_present:
            failed = {
                "name": "landing_semantics",
                "status": "fail",
                "mode_marker_ok": mode_marker_ok,
                "forbidden_terms_found": forbidden_hits,
                "workflow_form_present": workflow_form_present,
            }
            checks.append(failed)
        else:
            checks.append(
                {
                    "name": "landing_semantics",
                    "status": "pass",
                    "mode_marker_ok": mode_marker_ok,
                }
            )

    # check 7: viewport meta baseline
    if failed is None and require_viewport_meta:
        viewport_ok = (
            '<meta name="viewport"' in html_body
            and "width=device-width" in html_body
        )
        if not viewport_ok:
            failed = {
                "name": "viewport_meta",
                "status": "fail",
                "reason": "Missing required responsive viewport meta tag",
            }
            checks.append(failed)
        else:
            checks.append(
                {
                    "name": "viewport_meta",
                    "status": "pass",
                }
            )

    # check 8: responsive css markers
    if failed is None and responsive_markers:
        missing_markers = [m for m in responsive_markers if isinstance(m, str) and m not in css_body]
        if missing_markers:
            failed = {
                "name": "responsive_css_markers",
                "status": "fail",
                "missing": missing_markers,
            }
            checks.append(failed)
        else:
            checks.append(
                {
                    "name": "responsive_css_markers",
                    "status": "pass",
                    "markers": responsive_markers,
                    "stylesheet_attempts": css_attempts,
                }
            )

    # check 9: multi-device profile declarations
    if failed is None and device_profiles:
        profile_ids = {
            p.get("id")
            for p in device_profiles
            if isinstance(p, dict) and isinstance(p.get("id"), str)
        }
        required_profiles = {"desktop", "tablet", "mobile"}
        missing_profiles = sorted(required_profiles - profile_ids)
        if missing_profiles:
            failed = {
                "name": "multi_device_profiles",
                "status": "fail",
                "missing_profiles": missing_profiles,
            }
            checks.append(failed)
        else:
            checks.append(
                {
                    "name": "multi_device_profiles",
                    "status": "pass",
                    "profiles": sorted(profile_ids),
                }
            )

    # check 10: security headers baseline
    if failed is None and security_headers:
        missing_headers: List[Dict[str, str]] = []
        for item in security_headers:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip().lower()
            must_include = str(item.get("must_include", "")).strip().lower()
            if not name:
                continue
            current = str(homepage_headers.get(name, "")).lower()
            if not current or (must_include and must_include not in current):
                missing_headers.append(
                    {
                        "name": name,
                        "expected_fragment": must_include,
                        "actual": current,
                    }
                )

        if missing_headers:
            failed = {
                "name": "security_headers_baseline",
                "status": "fail",
                "missing_or_mismatch": missing_headers,
            }
            checks.append(failed)
        else:
            checks.append(
                {
                    "name": "security_headers_baseline",
                    "status": "pass",
                    "checked": [
                        str(item.get("name")).lower()
                        for item in security_headers
                        if isinstance(item, dict) and item.get("name")
                    ],
                }
            )

    report = {
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "base_url": base_url,
        "project_id": page_spec.get("project_id"),
        "adapter_name": page_spec.get("adapter_name") or page_spec.get("meta", {}).get("adapter_name"),
        "layout_profile": page_spec.get("layout_profile"),
        "page_mode": page_mode,
        "status": "passed" if failed is None else "failed",
        "checks": checks,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return 0 if failed is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
