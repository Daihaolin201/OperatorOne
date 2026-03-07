#!/usr/bin/env python3
"""Z.AI GLM preflight gate module.

Provides a mandatory pre-flight check before any Z.AI GLM API interaction.
Failures are explicit and NEVER silently fall back to another provider.

Usage:
    from dashboard.zai_preflight import check_zai_preflight, ZAIPreflightError

    audit = check_zai_preflight()  # raises ZAIPreflightError on any failure
    # audit is a dict with provider, model, step, latency_ms, token_usage, request_id
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ZAI_PROVIDER = "z.ai"
ZAI_MODEL = "glm-4.5"
ZAI_API_KEY_ENV = "ZAI_API_KEY"


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class ZAIPreflightError(RuntimeError):
    """Raised when the Z.AI GLM preflight check fails.

    The error message is diagnostic and explicitly names the missing or
    invalid field.  This exception is NEVER swallowed; callers must handle
    it explicitly.  Silent fallback to another model/provider is forbidden.

    Attributes:
        field: The name of the configuration field that caused the failure.
        reason: Human-readable explanation of the failure.
    """

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(
            f"ZAI preflight FAILED — field='{field}': {reason}. "
            "MUST NOT silently fall back to another provider."
        )


# ---------------------------------------------------------------------------
# Audit record schema
# ---------------------------------------------------------------------------
# Runtime audit fields emitted by check_zai_preflight().
# These fields map 1-to-1 with the JSON Schema in zai_preflight_contract.md.
#
# {
#   "provider":     str   — always "z.ai"
#   "model":        str   — always "glm-4.5"
#   "step":         str   — preflight step name (e.g. "env_check")
#   "latency_ms":   int   — wall-clock duration of this check in milliseconds
#   "token_usage":  None  — None at preflight (no real API call)
#   "request_id":   str   — UUID4 hex for this preflight invocation
# }


def _build_audit_record(
    *,
    step: str,
    latency_ms: int,
    token_usage: Any = None,
) -> Dict[str, Any]:
    """Construct a canonical audit record for a preflight step."""
    return {
        "provider": ZAI_PROVIDER,
        "model": ZAI_MODEL,
        "step": step,
        "latency_ms": latency_ms,
        "token_usage": token_usage,
        "request_id": uuid.uuid4().hex,
    }


# ---------------------------------------------------------------------------
# Main preflight function
# ---------------------------------------------------------------------------


def check_zai_preflight() -> Dict[str, Any]:
    """Run the Z.AI GLM pre-flight gate.

    Checks:
    1. ``ZAI_API_KEY`` environment variable is present and non-empty.

    No real API network call is made — this avoids key exposure in logs
    while still guaranteeing a hard failure when credentials are absent.

    Returns:
        A canonical audit record dict:
        ``{provider, model, step, latency_ms, token_usage, request_id}``

    Raises:
        ZAIPreflightError: If ``ZAI_API_KEY`` is missing or empty.
            The error message names the field and the exact reason.
            Callers MUST NOT catch this and silently continue with another
            model or provider.
    """
    t0 = time.monotonic()

    api_key = os.environ.get(ZAI_API_KEY_ENV)
    if not api_key or not api_key.strip():
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        # Build the audit record even on failure so callers can log it.
        _ = _build_audit_record(step="env_check", latency_ms=elapsed_ms)
        raise ZAIPreflightError(
            field=ZAI_API_KEY_ENV,
            reason=f"environment variable '{ZAI_API_KEY_ENV}' is not set or is empty",
        )

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    return _build_audit_record(step="env_check", latency_ms=elapsed_ms)


# ---------------------------------------------------------------------------
# Optional: named audit field constants (for schema validation elsewhere)
# ---------------------------------------------------------------------------

AUDIT_FIELDS = ("provider", "model", "step", "latency_ms", "token_usage", "request_id")
