#!/usr/bin/env python3
"""Smoke tests for deployed simple web product."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Tuple


def http_request(
    method: str,
    url: str,
    payload: Dict[str, Any] | None = None,
    timeout: int = 15,
) -> Tuple[int, str]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, method=method.upper(), data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = int(resp.status)
            body = resp.read().decode("utf-8", errors="replace")
            return status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return int(e.code), body


def parse_json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        return {}


def run_with_retry(fn, retries: int, delay: float):
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return fn(), attempt
        except Exception as exc:  # pragma: no cover - operational retry path
            last_exc = exc
            if attempt < retries:
                time.sleep(delay)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("retry execution failed without exception")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test deployed web product")
    parser.add_argument("--base-url", required=True, help="Deployed base URL")
    parser.add_argument("--out", required=True, help="Output JSON report path")
    parser.add_argument("--page-spec", required=False, help="Optional page spec path for mode-aware checks")
    parser.add_argument("--retries", type=int, default=6)
    parser.add_argument("--retry-delay", type=float, default=3.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base = args.base_url.rstrip("/")

    page_mode = "web_product"
    if args.page_spec:
        try:
            with open(args.page_spec, "r", encoding="utf-8") as f:
                spec = json.load(f)
            page_mode = str((spec.get("meta") or {}).get("page_mode") or (spec.get("testing") or {}).get("page_mode") or "web_product")
        except Exception:
            page_mode = "web_product"

    checks = []

    def check_homepage():
        status, body = http_request("GET", f"{base}/")
        if status != 200:
            raise RuntimeError(f"Homepage status {status}")

        signatures = [
            'data-module="hero_problem"',
            'id="signup-form"',
        ]
        if page_mode != "landing":
            signatures.append('id="workflow-form"')
        missing = [s for s in signatures if s not in body]
        if missing:
            raise RuntimeError(f"Homepage content signature missing: {missing}")

        return {
            "name": "homepage",
            "status": "pass",
            "http_status": status,
            "evidence": "Homepage reachable with modular signatures",
        }

    def check_health():
        status, body = http_request("GET", f"{base}/api/health")
        payload = parse_json(body)
        if status != 200 or payload.get("status") != "ok":
            raise RuntimeError(f"Health check failed: status={status}, payload={payload}")
        return {
            "name": "api_health",
            "status": "pass",
            "http_status": status,
            "payload": payload,
        }

    def check_first_step():
        status, body = http_request(
            "POST",
            f"{base}/api/first-step",
            payload={"input": "We keep losing time chasing overdue invoices manually."},
        )
        payload = parse_json(body)
        if status != 200:
            raise RuntimeError(f"first-step endpoint status={status}")
        if not payload.get("first_step"):
            raise RuntimeError("first-step response missing first_step")
        return {
            "name": "api_first_step",
            "status": "pass",
            "http_status": status,
            "payload": {
                "first_step": payload.get("first_step"),
                "next_steps_count": len(payload.get("next_steps", [])),
            },
        }

    def check_signup():
        status, body = http_request(
            "POST",
            f"{base}/api/signup",
            payload={"email": "demo@example.com", "source": "smoke-test"},
        )
        payload = parse_json(body)
        if status != 200 or payload.get("accepted") is not True:
            raise RuntimeError(f"signup endpoint failed: status={status}, payload={payload}")
        return {
            "name": "api_signup",
            "status": "pass",
            "http_status": status,
            "payload": {
                "accepted": payload.get("accepted"),
                "project_id": payload.get("project_id"),
            },
        }

    check_functions = [check_homepage, check_health]
    if page_mode != "landing":
        check_functions.append(check_first_step)
    check_functions.append(check_signup)

    failed = None
    for fn in check_functions:
        try:
            result, attempts = run_with_retry(fn, retries=args.retries, delay=args.retry_delay)
            result["attempts"] = attempts
            checks.append(result)
        except Exception as exc:
            failed = {
                "name": fn.__name__,
                "status": "fail",
                "error": str(exc),
            }
            checks.append(failed)
            break

    passed = failed is None
    report = {
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "base_url": base,
        "page_mode": page_mode,
        "status": "passed" if passed else "failed",
        "checks": checks,
    }

    out_path = urllib.request.url2pathname(args.out)
    # url2pathname returns unchanged for normal local paths; keeps cross-platform safety.
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")

    if not passed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
