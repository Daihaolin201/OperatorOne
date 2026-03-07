#!/usr/bin/env python3
"""Compatibility wrapper.

Prefer the skill-owned implementation:
workspaces/op1_sales/skills/identify-prospects-stage1/scripts/build_prospect_queue.py
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    skill_script = (
        repo_root
        / "workspaces"
        / "op1_sales"
        / "skills"
        / "identify-prospects-stage1"
        / "scripts"
        / "build_prospect_queue.py"
    )

    if not skill_script.exists():
        raise SystemExit(f"Skill script not found: {skill_script}")

    # Keep CLI compatibility: forward all args untouched.
    sys.argv = [str(skill_script), *sys.argv[1:]]
    runpy.run_path(str(skill_script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
