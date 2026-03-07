#!/usr/bin/env python3
"""Shared utilities for Stage3 convert-early-customers scripts."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


STAGE_ORDER = [
    "qualified_interest",
    "discovery_scheduled",
    "discovery_completed",
    "pilot_offered",
    "pilot_active",
    "pilot_value_confirmed",
    "commercial_terms_sent",
    "commitment_received",
    "paid_started",
    "closed_lost",
]

STAGE_RANK = {stage: i for i, stage in enumerate(STAGE_ORDER)}
TERMINAL_STAGES = {"paid_started", "closed_lost"}


def _fixed_now_from_env() -> datetime | None:
    raw = str(os.environ.get("STAGE3_AS_OF", "")).strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def now_utc() -> datetime:
    fixed = _fixed_now_from_env()
    if fixed is not None:
        return fixed
    return datetime.now(tz=timezone.utc)


def now_iso() -> str:
    return now_utc().replace(microsecond=0).isoformat()


def parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def read_json(path: Path, default: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not path.exists():
        return default or {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def append_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def stage_rank(stage: str) -> int:
    return STAGE_RANK.get(stage, -1)


def can_advance(current: str, candidate: str) -> bool:
    # closed_lost is terminal unless already paid_started
    if current == "paid_started" and candidate == "closed_lost":
        return False
    return stage_rank(candidate) >= stage_rank(current)


def find_repo_root(start: Path) -> Path:
    for candidate in [start.resolve(), *start.resolve().parents]:
        if (
            (candidate / "workspaces" / "op1_sales" / "research" / "outreach" / "outreach_queue.latest.json").exists()
            and (candidate / "handoffs" / "sales_to_operations.json").exists()
            and (candidate / "workspaces" / "op1_product" / "research" / "stage3_mvp_scope" / "project_blueprint.json").exists()
        ):
            return candidate
    raise FileNotFoundError("Cannot locate OperatorOne repo root. Pass --repo-root.")


def parse_monthly_price(value: str) -> float:
    """Extract monthly numeric price from strings like '$79/month team'."""
    if not value:
        return 0.0
    m = re.search(r"\$\s*([0-9]+(?:\.[0-9]+)?)", value)
    if not m:
        return 0.0
    try:
        return float(m.group(1))
    except Exception:
        return 0.0
