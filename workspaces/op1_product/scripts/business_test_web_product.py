#!/usr/bin/env python3
"""Business-rule tests for deployed web product based on project spec."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple


def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def http_request(
    method: str,
    url: str,
    payload: Dict[str, Any] | None = None,
    timeout: int = 20,
) -> Tuple[int, str]:
    body = None
    headers: Dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, method=method.upper(), data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return int(e.code), e.read().decode("utf-8", errors="replace")


def parse_json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        return {}


def run_with_retry(fn, retries: int, delay: float):
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return fn(), attempt
        except Exception as exc:  # pragma: no cover - operational retries
            last_error = exc
            if attempt < retries:
                time.sleep(delay)
    if last_error:
        raise last_error
    raise RuntimeError("Unknown retry failure")


def normalize_text(value: str) -> str:
    return value.lower().strip()


def assert_contains_all(haystack: str, needles: List[str]) -> List[str]:
    missing: List[str] = []
    normalized = normalize_text(haystack)
    for needle in needles:
        token = normalize_text(str(needle))
        if token and token not in normalized:
            missing.append(token)
    return missing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Business test deployed web product")
    parser.add_argument("--base-url", required=True, help="Deployed base URL")
    parser.add_argument("--project-spec", required=True, help="Project spec JSON path")
    parser.add_argument("--out", required=True, help="Output JSON report path")
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--retry-delay", type=float, default=2.5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    spec = read_json(args.project_spec)

    tests = spec.get("business_tests", []) if isinstance(spec.get("business_tests"), list) else []
    checks: List[Dict[str, Any]] = []
    failed = None

    for test in tests:
        if not isinstance(test, dict):
            continue

        name = str(test.get("name", "unnamed_test"))
        payload_input = str(test.get("input", "")).strip()
        expected_fragments = test.get("expect_first_step_contains", [])
        if not payload_input or not isinstance(expected_fragments, list):
            continue

        def run_case():
            status, body = http_request(
                "POST",
                f"{base_url}/api/first-step",
                payload={"input": payload_input},
            )
            data = parse_json(body)
            if status != 200:
                raise RuntimeError(f"{name}: expected 200, got {status}")
            first_step = str(data.get("first_step", ""))
            if not first_step:
                raise RuntimeError(f"{name}: missing first_step in response")
            missing_tokens = assert_contains_all(first_step, [str(x) for x in expected_fragments])
            if missing_tokens:
                raise RuntimeError(f"{name}: first_step missing fragments {missing_tokens}")
            return {
                "name": name,
                "status": "pass",
                "http_status": status,
                "rule_id": data.get("rule_id"),
                "first_step": first_step,
            }

        try:
            result, attempts = run_with_retry(run_case, retries=args.retries, delay=args.retry_delay)
            result["attempts"] = attempts
            checks.append(result)
        except Exception as exc:
            failed = {
                "name": name,
                "status": "fail",
                "error": str(exc),
            }
            checks.append(failed)
            break

    if failed is None:
        def invalid_email_case():
            status, body = http_request(
                "POST",
                f"{base_url}/api/signup",
                payload={"email": "not-an-email"},
            )
            data = parse_json(body)
            if status != 400:
                raise RuntimeError(f"signup_invalid_email: expected 400, got {status}")
            if "error" not in data:
                raise RuntimeError("signup_invalid_email: missing error payload")
            return {
                "name": "signup_invalid_email",
                "status": "pass",
                "http_status": status,
                "payload": data,
            }

        try:
            result, attempts = run_with_retry(
                invalid_email_case,
                retries=args.retries,
                delay=args.retry_delay,
            )
            result["attempts"] = attempts
            checks.append(result)
        except Exception as exc:
            failed = {
                "name": "signup_invalid_email",
                "status": "fail",
                "error": str(exc),
            }
            checks.append(failed)

    report = {
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "base_url": base_url,
        "project_id": spec.get("project_id"),
        "adapter": spec.get("adapter", {}).get("name") if isinstance(spec.get("adapter"), dict) else None,
        "status": "passed" if failed is None else "failed",
        "checks": checks,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return 0 if failed is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
