#!/usr/bin/env python3
"""Shared path patterns for repository hygiene checks."""

from __future__ import annotations

import fnmatch
from pathlib import PurePosixPath
from typing import Iterable

# Volatile/generated artifacts that frequently create review noise.
GENERATED_ARTIFACT_GLOBS = [
    "dashboard/.runtime/**",
    "handoffs/_meta/**",
    "workspaces/*/research/**/*.latest.json",
    "workspaces/*/research/**/*.latest.md",
    "workspaces/*/research/**/*.latest.csv",
    "workspaces/*/research/**/*.latest.jsonl",
    "workspaces/*/research/**/run_*.json",
    "workspaces/*/research/**/rounds/**",
    "workspaces/*/research/**/_audit_runs/**",
    "workspaces/*/research/**/input/mirror.latest/**",
    "workspaces/*/research/**/briefs/**",
    "workspaces/*/research/**/drafts/**",
    "workspaces/*/research/**/packets/**",
]


def normalize_path(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).as_posix()


def is_generated_artifact(path: str, patterns: Iterable[str] = GENERATED_ARTIFACT_GLOBS) -> bool:
    p = normalize_path(path)
    return any(fnmatch.fnmatch(p, pat) for pat in patterns)
