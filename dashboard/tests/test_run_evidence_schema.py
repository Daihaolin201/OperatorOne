#!/usr/bin/env python3
"""Tests for dashboard.run_evidence_schema module.

Tests the run evidence index schema, builder, and validator.
Covers key path: complete valid index and detection of missing artifacts.
"""

import os
from dashboard.run_evidence_schema import (
    build_evidence_index,
    validate_evidence_index,
)


class TestRunEvidenceSchema:
    """Test suite for run evidence index validation."""

    def test_validate_passes_complete_index(self):
        """Test validation passes with complete and valid evidence index."""
        # Arrange: build a complete evidence index
        index = build_evidence_index(
            run_id="run_abc123",
            status="succeeded",
            mode="simulation",
            started_at="2026-03-07T10:00:00Z",
            finished_at="2026-03-07T10:05:00Z",
            stages=[],
            model_usage=None,
            artifacts=[],
        )

        # Convert to dict for validation (as would be done after JSON parsing)
        index_dict = {
            "run_id": index.run_id,
            "status": index.status,
            "mode": index.mode,
            "started_at": index.started_at,
            "finished_at": index.finished_at,
            "stages": index.stages,
            "model_usage": index.model_usage,
            "artifacts": index.artifacts,
            "version": index.version,
        }

        # Act: validate the index
        valid, missing = validate_evidence_index(index_dict)

        # Assert: validation passes
        assert valid is True
        assert missing == []

    def test_validate_detects_missing_artifacts(self):
        """Test validation detects artifacts with missing/non-existent paths."""
        # Arrange: build index with artifact pointing to non-existent path
        index_dict = {
            "run_id": "run_test",
            "status": "succeeded",
            "mode": "simulation",
            "started_at": "2026-03-07T10:00:00Z",
            "finished_at": "2026-03-07T10:05:00Z",
            "artifacts": [
                {
                    "name": "missing_artifact",
                    "path": "/nonexistent/path/to/artifact.txt",
                    "exists": False,
                }
            ],
        }

        # Act: validate the index
        valid, missing = validate_evidence_index(index_dict)

        # Assert: validation detects missing artifact
        assert valid is False
        assert len(missing) > 0
        # Should contain reference to the missing artifact
        assert any("artifacts" in m for m in missing)
