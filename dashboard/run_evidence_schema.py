#!/usr/bin/env python3
"""Run-level evidence index schema and validation.

Defines the unified schema for capturing run-level artifacts, stages, and model usage
audits in JSON format. Provides builders and validators for evidence reproducibility.

Usage:
    from dashboard.run_evidence_schema import RunEvidenceIndex, build_evidence_index, validate_evidence_index

    # Build an evidence index
    index = build_evidence_index(
        run_id="run_abc123",
        status="succeeded",
        mode="simulation",
        started_at="2026-03-07T10:00:00Z",
        finished_at="2026-03-07T10:05:00Z",
        stages=[...],
        model_usage={...},
        artifacts=[...]
    )

    # Validate before persistence
    valid, missing = validate_evidence_index(index)
    if not valid:
        print(f"Missing fields: {missing}")
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class StageRecord:
    """A single stage execution record."""
    name: str          # e.g. "product", "marketing", "sales", "operations"
    status: str        # "queued" | "running" | "succeeded" | "failed"
    started_at: str    # ISO 8601 timestamp
    finished_at: str   # ISO 8601 timestamp
    error: Optional[str] = None  # Human-readable error message if status="failed"


@dataclass
class ModelUsageRecord:
    """Aggregated model usage across a run."""
    provider: str      # e.g. "z.ai", "openai"
    model: str         # e.g. "glm-4.5", "gpt-4"
    total_calls: int   # Total API calls in this run
    total_tokens: int  # Total tokens consumed (input + output)


@dataclass
class ArtifactReference:
    """Reference to a single artifact produced during the run."""
    name: str          # Human-readable artifact name (e.g. "product_spec.pdf")
    path: str          # Repo-relative path to artifact (e.g. "workspaces/op1_product/output/spec.pdf")
    exists: bool       # Whether the artifact currently exists on disk


@dataclass
class RunEvidenceIndex:
    """Complete run-level evidence index."""
    run_id: str        # Unique run identifier (e.g. "run_abc123xyz")
    status: str        # "queued" | "running" | "succeeded" | "failed" | "cancelled"
    mode: str          # "simulation" | "live"
    started_at: str    # ISO 8601 timestamp
    finished_at: str   # ISO 8601 timestamp
    stages: List[StageRecord] = field(default_factory=list)
    model_usage: Optional[ModelUsageRecord] = None
    artifacts: List[ArtifactReference] = field(default_factory=list)
    version: str = "1.0"  # Schema version for backwards compatibility


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_evidence_index(
    run_id: str,
    status: str,
    mode: str,
    started_at: str,
    finished_at: str,
    stages: Optional[List[Dict[str, Any]]] = None,
    model_usage: Optional[Dict[str, Any]] = None,
    artifacts: Optional[List[Dict[str, Any]]] = None,
) -> RunEvidenceIndex:
    """Construct a RunEvidenceIndex from primitive types.

    Args:
        run_id: Unique run identifier
        status: Overall run status
        mode: Execution mode (simulation or live)
        started_at: ISO 8601 start timestamp
        finished_at: ISO 8601 finish timestamp
        stages: List of stage dicts with keys: name, status, started_at, finished_at, error
        model_usage: Dict with keys: provider, model, total_calls, total_tokens
        artifacts: List of artifact dicts with keys: name, path, exists

    Returns:
        Fully constructed RunEvidenceIndex

    Raises:
        ValueError: If any required field is invalid
    """
    # Validate status
    valid_statuses = {"queued", "running", "succeeded", "failed", "cancelled"}
    if status not in valid_statuses:
        raise ValueError(f"status must be one of {valid_statuses}, got {status!r}")

    # Validate mode
    valid_modes = {"simulation", "live"}
    if mode not in valid_modes:
        raise ValueError(f"mode must be one of {valid_modes}, got {mode!r}")

    # Build stage records
    stage_records: List[StageRecord] = []
    if stages:
        for stage_dict in stages:
            stage_records.append(
                StageRecord(
                    name=stage_dict.get("name", ""),
                    status=stage_dict.get("status", ""),
                    started_at=stage_dict.get("started_at", ""),
                    finished_at=stage_dict.get("finished_at", ""),
                    error=stage_dict.get("error"),
                )
            )

    # Build model usage record
    model_usage_record: Optional[ModelUsageRecord] = None
    if model_usage:
        model_usage_record = ModelUsageRecord(
            provider=model_usage.get("provider", ""),
            model=model_usage.get("model", ""),
            total_calls=model_usage.get("total_calls", 0),
            total_tokens=model_usage.get("total_tokens", 0),
        )

    # Build artifact references
    artifact_refs: List[ArtifactReference] = []
    if artifacts:
        for artifact_dict in artifacts:
            artifact_refs.append(
                ArtifactReference(
                    name=artifact_dict.get("name", ""),
                    path=artifact_dict.get("path", ""),
                    exists=artifact_dict.get("exists", False),
                )
            )

    return RunEvidenceIndex(
        run_id=run_id,
        status=status,
        mode=mode,
        started_at=started_at,
        finished_at=finished_at,
        stages=stage_records,
        model_usage=model_usage_record,
        artifacts=artifact_refs,
    )


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def validate_evidence_index(index_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a run evidence index dictionary.

    Checks for presence and type of required fields. Does NOT perform deep
    semantic validation (e.g., timestamp consistency or path existence).

    Args:
        index_dict: Dictionary to validate (e.g., from JSON parsing)

    Returns:
        (valid, missing_fields) tuple:
        - valid: bool indicating whether all required fields are present
        - missing_fields: list of missing/invalid field names and reasons

    Examples:
        >>> valid, missing = validate_evidence_index({"run_id": "run_123"})
        >>> print(valid)  # False
        >>> print(missing)
        ['status (missing)', 'mode (missing)', ...]

        >>> valid, missing = validate_evidence_index(complete_dict)
        >>> if not valid:
        ...     print(f"Validation failed: {missing}")
    """
    missing_fields: List[str] = []

    # Required top-level fields
    required_fields = {
        "run_id": str,
        "status": str,
        "mode": str,
        "started_at": str,
        "finished_at": str,
    }

    for field_name, expected_type in required_fields.items():
        if field_name not in index_dict:
            missing_fields.append(f"{field_name} (missing)")
        elif not isinstance(index_dict[field_name], expected_type):
            missing_fields.append(
                f"{field_name} (invalid type: expected {expected_type.__name__}, "
                f"got {type(index_dict[field_name]).__name__})"
            )

    # Validate artifacts if present
    missing_artifacts = []
    artifacts = index_dict.get("artifacts", [])
    if isinstance(artifacts, list):
        for i, artifact in enumerate(artifacts):
            if not isinstance(artifact, dict):
                missing_fields.append(f"artifacts[{i}] (not a dict)")
                continue
            artifact_required = {"name", "path", "exists"}
            for req_field in artifact_required:
                if req_field not in artifact:
                    missing_artifacts.append(
                        f"artifacts[{i}].{req_field} (missing)"
                    )
            if artifact.get("exists") is False:
                missing_artifacts.append(
                    f"artifacts[{i}] = {artifact.get('name')} (path {artifact.get('path')} does not exist)"
                )
    elif artifacts:
        missing_fields.append("artifacts (not a list)")

    if missing_artifacts:
        missing_fields.extend(missing_artifacts)

    # Validate model_usage if present
    if "model_usage" in index_dict and index_dict["model_usage"] is not None:
        model_usage = index_dict["model_usage"]
        if isinstance(model_usage, dict):
            model_required = {"provider", "model", "total_calls", "total_tokens"}
            for req_field in model_required:
                if req_field not in model_usage:
                    missing_fields.append(f"model_usage.{req_field} (missing)")
        else:
            missing_fields.append("model_usage (not a dict or null)")

    # Validate stages if present
    if "stages" in index_dict and index_dict["stages"] is not None:
        stages = index_dict["stages"]
        if isinstance(stages, list):
            for i, stage in enumerate(stages):
                if not isinstance(stage, dict):
                    missing_fields.append(f"stages[{i}] (not a dict)")
                    continue
                stage_required = {"name", "status", "started_at", "finished_at"}
                for req_field in stage_required:
                    if req_field not in stage:
                        missing_fields.append(f"stages[{i}].{req_field} (missing)")
        else:
            missing_fields.append("stages (not a list)")

    valid = len(missing_fields) == 0
    return valid, missing_fields
