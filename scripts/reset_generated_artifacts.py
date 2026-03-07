#!/usr/bin/env python3
"""Reset modified generated artifacts to reduce local review noise.

Default is dry-run.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import List

from repo_hygiene_patterns import is_generated_artifact


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Reset modified generated artifacts")
    p.add_argument("--repo-root", default=".", help="Repository root")
    p.add_argument("--include-staged", action="store_true", help="Also restore staged generated files")
    p.add_argument("--apply", action="store_true", help="Apply restore instead of dry-run")
    p.add_argument("--max-list", type=int, default=60, help="Max paths to print")
    return p.parse_args()


def run_git(repo_root: Path, args: List[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=str(repo_root), text=True).strip()


def chunk(seq: List[str], size: int = 100) -> List[List[str]]:
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()

    worktree_paths = [x for x in run_git(repo_root, ["diff", "--name-only"]).splitlines() if x.strip()]
    staged_paths = [x for x in run_git(repo_root, ["diff", "--cached", "--name-only"]).splitlines() if x.strip()]

    targets = sorted({p for p in worktree_paths if is_generated_artifact(p)})
    staged_targets = sorted({p for p in staged_paths if is_generated_artifact(p)}) if args.include_staged else []

    print(f"Generated artifacts in working tree: {len(targets)}")
    for p in targets[: args.max_list]:
        print(f"  - {p}")
    if len(targets) > args.max_list:
        print(f"  ... +{len(targets) - args.max_list} more")

    if args.include_staged:
        print(f"\nGenerated artifacts in staged set: {len(staged_targets)}")
        for p in staged_targets[: args.max_list]:
            print(f"  - {p}")
        if len(staged_targets) > args.max_list:
            print(f"  ... +{len(staged_targets) - args.max_list} more")

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to restore these files.")
        return 0

    if targets:
        for part in chunk(targets):
            subprocess.check_call(["git", "restore", "--worktree", "--", *part], cwd=str(repo_root))

    if args.include_staged and staged_targets:
        for part in chunk(staged_targets):
            subprocess.check_call(["git", "restore", "--staged", "--", *part], cwd=str(repo_root))

    print("\nRestore complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
