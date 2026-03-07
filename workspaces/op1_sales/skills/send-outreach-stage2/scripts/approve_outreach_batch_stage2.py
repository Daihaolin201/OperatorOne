#!/usr/bin/env python3
"""Approve Stage2 outreach batch artifact.

Converts outreach_batch.ready.json -> outreach_batch.approved.json.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def _find_repo_root(start: Path) -> Path:
    for candidate in [start.resolve(), *start.resolve().parents]:
        if (candidate / "workspaces" / "op1_sales" / "research" / "outreach" / "outreach_batch.ready.json").exists():
            return candidate
    raise FileNotFoundError("Cannot locate OperatorOne repo root. Pass --repo-root.")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Approve Stage2 outreach batch")
    p.add_argument("--repo-root", type=str, default="", help="OperatorOne repo root")
    p.add_argument("--ready-file", type=str, default="", help="Path to outreach_batch.ready.json")
    p.add_argument("--approved-file", type=str, default="", help="Output approved batch path")
    p.add_argument("--approver", type=str, required=True, help="Approver identity")
    p.add_argument("--note", type=str, default="", help="Approval note")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else _find_repo_root(Path.cwd())
    out_dir = repo_root / "workspaces" / "op1_sales" / "research" / "outreach"

    ready_file = Path(args.ready_file).resolve() if args.ready_file else out_dir / "outreach_batch.ready.json"
    approved_file = Path(args.approved_file).resolve() if args.approved_file else out_dir / "outreach_batch.approved.json"

    ready = _read_json(ready_file)

    approved = {
        **ready,
        "approved": True,
        "approved_at": _now_iso(),
        "approved_by": args.approver,
        "approval_note": args.note,
    }

    _write_json(approved_file, approved)

    print(f"Wrote: {approved_file}")
    print(f"Batch: {approved.get('batch_id', '')} | eligible_count={approved.get('eligible_count', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
