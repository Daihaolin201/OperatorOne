#!/usr/bin/env python3
"""Tests for dashboard.zai_preflight module.

Tests the Z.AI GLM preflight gate function and error handling.
Covers key path: valid key, missing key, and empty key scenarios.
"""

import os
import pytest
from dashboard.zai_preflight import check_zai_preflight, ZAIPreflightError


class TestZAIPreflightGate:
    """Test suite for Z.AI GLM preflight checks."""

    def test_preflight_passes_with_valid_key(self, monkeypatch):
        """Test preflight passes when ZAI_API_KEY environment variable is set."""
        # Arrange: set valid API key
        monkeypatch.setenv("ZAI_API_KEY", "test_key")

        # Act: call preflight check
        audit = check_zai_preflight()

        # Assert: audit dict contains expected fields
        assert audit is not None
        assert isinstance(audit, dict)
        assert audit["provider"] == "z.ai"
        assert audit["model"] == "glm-5"
        assert audit["step"] == "env_check"
        assert "latency_ms" in audit
        assert "request_id" in audit
        assert "token_usage" in audit

    def test_preflight_fails_without_key(self, monkeypatch):
        """Test preflight fails when ZAI_API_KEY is not set."""
        # Arrange: ensure ZAI_API_KEY is not set
        monkeypatch.delenv("ZAI_API_KEY", raising=False)

        # Act & Assert: check_zai_preflight should raise ZAIPreflightError
        with pytest.raises(ZAIPreflightError) as exc_info:
            check_zai_preflight()

        error = exc_info.value
        assert error.field == "ZAI_API_KEY"
        assert "not set or is empty" in error.reason

    def test_preflight_fails_with_empty_key(self, monkeypatch):
        """Test preflight fails when ZAI_API_KEY is set to whitespace."""
        # Arrange: set empty/whitespace API key
        monkeypatch.setenv("ZAI_API_KEY", "  ")

        # Act & Assert: check_zai_preflight should raise ZAIPreflightError
        with pytest.raises(ZAIPreflightError) as exc_info:
            check_zai_preflight()

        error = exc_info.value
        assert error.field == "ZAI_API_KEY"
        assert "not set or is empty" in error.reason
