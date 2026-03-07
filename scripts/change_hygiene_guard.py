#!/usr/bin/env python3
"""Guard against mixing source changes and generated-artifact churn in one change-set."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Dict, List

from repo_hygiene_patterns import is_generated_artifact


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Repository change hygiene guard")
    p.add_argument("--repo-root", default=".", help="Repository root")
    p.add_argument("--base", default="", help="Base git ref/sha")
    p.add_argument("--head", default="HEAD", help="Head git ref/sha")
    p.add_argument("--staged", action="store_true", help="Inspect staged changes only")
    p.add_argument("--allow-mixed", action="store_true", help="Allow mixed source+generated changes")
    p.add_argument("--json", action="store_true", help="Print JSON summary")
    p.add_argument("--max-list", type=int, default=40, help="Max paths to print per bucket")
    return p.parse_args()


def run_git(repo_root: Path, args: List[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=str(repo_root), text=True).strip()


def _is_null_sha(v: str) -> bool:
    return bool(v) and set(v) == {"0"}


def list_changed_files(repo_root: Path, staged: bool, base: str, head: str) -> List[str]:
    if staged:
        out = run_git(repo_root, ["diff", "--cached", "--name-only"])
        return [x for x in out.splitlines() if x.strip()]

    if base:
        if _is_null_sha(base):
            # Initial push / missing previous commit.
            out = run_git(repo_root, ["diff", "--name-only", "HEAD~1", head])
        else:
            out = run_git(repo_root, ["diff", "--name-only", f"{base}...{head}"])
        return [x for x in out.splitlines() if x.strip()]

    out = run_git(repo_root, ["diff", "--name-only", "HEAD~1", head])
    return [x for x in out.splitlines() if x.strip()]


def summarize(paths: List[str]) -> Dict[str, List[str]]:
    generated = sorted([p for p in paths if is_generated_artifact(p)])
    source = sorted([p for p in paths if not is_generated_artifact(p)])
    return {"generated": generated, "source": source}


def print_human(summary: Dict[str, List[str]], max_list: int) -> None:
    generated = summary["generated"]
    source = summary["source"]
    total = len(generated) + len(source)
    print(f"Changed files: total={total}, source={len(source)}, generated={len(generated)}")

    if source:
        print("\nSource-like changes:")
        for p in source[:max_list]:
            print(f"  - {p}")
        if len(source) > max_list:
            print(f"  ... +{len(source) - max_list} more")

    if generated:
        print("\nGenerated-artifact changes:")
        for p in generated[:max_list]:
            print(f"  - {p}")
        if len(generated) > max_list:
            print(f"  ... +{len(generated) - max_list} more")


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()

    changed = list_changed_files(repo_root, args.staged, args.base, args.head)
    summary = summarize(changed)

    payload = {
        "changed_total": len(changed),
        "source_count": len(summary["source"]),
        "generated_count": len(summary["generated"]),
        "mixed": bool(summary["source"]) and bool(summary["generated"]),
        "source": summary["source"],
        "generated": summary["generated"],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_human(summary, args.max_list)

    mixed = payload["mixed"]
    if mixed and not args.allow_mixed:
        print(
            "\nFAIL: mixed source + generated artifact changes detected.\n"
            "Recommendation: split into separate commits/PRs (source/config/docs vs generated runtime artifacts)."
        )
        return 2

    print("\nPASS: change hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
