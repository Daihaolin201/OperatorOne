#!/usr/bin/env python3
"""Bootstrap Stage1 tracking contracts/config into op1_operations workspace."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from stage1_common import now_iso, resolve_repo_root


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bootstrap Stage1 tracking contracts and adapter config")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root (auto-detect when omitted)")
    p.add_argument(
        "--operations-workspace",
        default="workspaces/op1_operations",
        help="op1_operations workspace path relative to repo root",
    )
    p.add_argument("--force", action="store_true", help="Overwrite destination files")
    return p.parse_args()


def copy_one(src: Path, dst: Path, force: bool) -> str:
    if dst.exists() and not force:
        return "skipped_exists"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return "written"


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    repo_root = Path(args.repo_root).resolve() if args.repo_root else resolve_repo_root(script_dir)

    template_dir = script_dir.parent / "references" / "defaults"
    if not template_dir.exists():
        raise FileNotFoundError(f"Missing template directory: {template_dir}")

    op_ws = repo_root / args.operations_workspace

    file_map = {
        template_dir / "source_adapters.v1.json": op_ws / "config/source_adapters.v1.json",
        template_dir / "tracking_plan.v1.json": op_ws / "contracts/tracking_plan.v1.json",
        template_dir / "metric_dictionary.v1.yaml": op_ws / "contracts/metric_dictionary.v1.yaml",
        template_dir / "revenue_rules.v1.yaml": op_ws / "contracts/revenue_rules.v1.yaml",
    }

    results = []
    for src, dst in file_map.items():
        if not src.exists():
            raise FileNotFoundError(f"Missing template file: {src}")
        status = copy_one(src, dst, args.force)
        results.append({"src": str(src), "dst": str(dst), "status": status})

    print({"generated_at": now_iso(), "files": results})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
