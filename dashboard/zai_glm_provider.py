#!/usr/bin/env python3
"""Z.AI GLM provider adapter with per-call audit records."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from dashboard.zai_preflight import (
    ZAIPreflightError,
    ZAI_API_KEY_ENV,
    ZAI_MODEL,
    ZAI_PROVIDER,
    check_zai_preflight,
)


ZAI_API_BASE = "https://api.z.ai/api/paas/v4"
ZAI_CHAT_COMPLETIONS_ENDPOINT = "/chat/completions"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _mock_response_text(step: str, prompt: str) -> str:
    templates = {
        "product": "Product direction: prioritize a small MVP with clear pricing and one measurable activation metric.",
        "marketing": "Marketing direction: launch one focused channel, publish a concise value narrative, and track CTR/CVR weekly.",
        "sales": "Sales direction: target high-fit leads, send personalized outreach, and move qualified replies into a short close loop.",
        "operations": "Operations direction: monitor funnel, revenue, and cycle time; convert gaps into a ranked execution backlog.",
    }
    summary = templates.get(
        step,
        "Execution direction: deliver concise plan, measurable next action, and explicit owner for follow-through.",
    )
    return f"{summary} Prompt focus: {prompt[:120].strip()}"


def _extract_response_text(payload: Dict[str, Any]) -> str:
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
    return "GLM responded without textual content."


def _build_audit(
    *,
    step: str,
    latency_ms: int,
    token_usage: Dict[str, int],
    request_id: str,
    mode: str,
) -> Dict[str, Any]:
    return {
        "provider": ZAI_PROVIDER,
        "model": ZAI_MODEL,
        "step": step,
        "latency_ms": latency_ms,
        "token_usage": token_usage,
        "request_id": request_id,
        "timestamp": _utc_now_iso(),
        "mode": mode,
    }


def call_glm(prompt: str, step: str, mode: str = "simulation") -> Dict[str, Any]:
    if mode not in {"simulation", "live"}:
        raise ValueError("mode must be 'simulation' or 'live'")

    if mode == "simulation":
        time.sleep(0.05)
        request_id = uuid.uuid4().hex
        token_usage = {
            "prompt_tokens": 50,
            "completion_tokens": 80,
            "total_tokens": 130,
        }
        audit = _build_audit(
            step=step,
            latency_ms=120,
            token_usage=token_usage,
            request_id=request_id,
            mode="simulation",
        )
        return {
            "ok": True,
            "response_text": _mock_response_text(step=step, prompt=prompt),
            "audit": audit,
        }

    t0 = time.monotonic()
    check_zai_preflight()

    import os

    api_key = os.environ.get(ZAI_API_KEY_ENV, "").strip()
    if not api_key:
        raise ZAIPreflightError(
            field=ZAI_API_KEY_ENV,
            reason=f"environment variable '{ZAI_API_KEY_ENV}' is not set or is empty",
        )

    request_body = {
        "model": ZAI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a concise business execution copilot.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }

    encoded_body = json.dumps(request_body).encode("utf-8")
    request = urllib.request.Request(
        url=f"{ZAI_API_BASE}{ZAI_CHAT_COMPLETIONS_ENDPOINT}",
        data=encoded_body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Z.AI GLM live call failed: {exc}") from exc

    usage = payload.get("usage") if isinstance(payload, dict) else None
    token_usage = {
        "prompt_tokens": int((usage or {}).get("prompt_tokens", 0)),
        "completion_tokens": int((usage or {}).get("completion_tokens", 0)),
        "total_tokens": int((usage or {}).get("total_tokens", 0)),
    }
    request_id = str(payload.get("id") or uuid.uuid4().hex)
    latency_ms = int((time.monotonic() - t0) * 1000)
    audit = _build_audit(
        step=step,
        latency_ms=latency_ms,
        token_usage=token_usage,
        request_id=request_id,
        mode="live",
    )
    return {
        "ok": True,
        "response_text": _extract_response_text(payload),
        "audit": audit,
    }


def get_run_model_usage(audit_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_tokens = 0
    calls: List[Dict[str, Any]] = []

    for record in audit_records:
        call_record = {
            "provider": record.get("provider", ZAI_PROVIDER),
            "model": record.get("model", ZAI_MODEL),
            "step": record.get("step", "unknown"),
            "latency_ms": int(record.get("latency_ms", 0)),
            "token_usage": record.get("token_usage", {}),
            "request_id": record.get("request_id", ""),
            "timestamp": record.get("timestamp", ""),
            "mode": record.get("mode", "simulation"),
        }
        token_usage = call_record.get("token_usage")
        if isinstance(token_usage, dict):
            total_tokens += int(token_usage.get("total_tokens", 0))
        calls.append(call_record)

    provider = calls[0]["provider"] if calls else ZAI_PROVIDER
    model = calls[0]["model"] if calls else ZAI_MODEL
    return {
        "provider": provider,
        "model": model,
        "total_calls": len(calls),
        "total_tokens": total_tokens,
        "calls": calls,
    }
