#!/usr/bin/env python3

import pytest

from dashboard.zai_glm_provider import call_glm, get_run_model_usage
from dashboard.zai_preflight import ZAIPreflightError


class TestZAIGLMProvider:
    def test_call_glm_simulation_returns_audit_fields(self):
        result = call_glm("Build a practical plan for next sprint", "product", mode="simulation")

        assert result["ok"] is True
        assert isinstance(result["response_text"], str)
        assert result["response_text"]

        audit = result["audit"]
        assert audit["provider"] == "z.ai"
        assert audit["model"] == "glm-5"
        assert audit["step"] == "product"
        assert audit["latency_ms"] == 120
        assert audit["mode"] == "simulation"
        assert "timestamp" in audit
        assert isinstance(audit["timestamp"], str)
        assert audit["timestamp"].endswith("Z")
        assert len(audit["request_id"]) == 32
        int(audit["request_id"], 16)
        assert audit["token_usage"] == {
            "prompt_tokens": 50,
            "completion_tokens": 80,
            "total_tokens": 130,
        }

    def test_call_glm_live_without_credentials_raises_preflight(self, monkeypatch):
        monkeypatch.delenv("ZAI_API_KEY", raising=False)

        with pytest.raises(ZAIPreflightError):
            call_glm("Any live prompt", "sales", mode="live")

    def test_get_run_model_usage_aggregates_calls(self):
        records = [
            call_glm("Plan product stage", "product", mode="simulation")["audit"],
            call_glm("Plan marketing stage", "marketing", mode="simulation")["audit"],
            call_glm("Plan sales stage", "sales", mode="simulation")["audit"],
        ]

        usage = get_run_model_usage(records)

        assert usage["provider"] == "z.ai"
        assert usage["model"] == "glm-5"
        assert usage["total_calls"] == 3
        assert usage["total_tokens"] == 390
        assert len(usage["calls"]) == 3
        assert usage["calls"][0]["step"] == "product"
        assert usage["calls"][1]["step"] == "marketing"
        assert usage["calls"][2]["step"] == "sales"
