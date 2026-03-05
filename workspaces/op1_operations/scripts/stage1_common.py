#!/usr/bin/env python3
"""Common utilities for op1_operations Stage1 tracking."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


def resolve_repo_root(start: Path | None = None) -> Path:
    seed = (start or Path(__file__)).resolve()
    for candidate in [seed, *seed.parents]:
        if (candidate / "handoffs").exists() and (candidate / "workspaces").exists():
            return candidate
    raise FileNotFoundError("Unable to locate OperatorOne repo root")


def _fixed_now_from_env() -> datetime | None:
    raw = str(os.environ.get("STAGE1_AS_OF", "")).strip()
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


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def iso_date(value: str | None) -> str:
    dt = parse_iso(value)
    if dt is None:
        return now_utc().date().isoformat()
    return dt.date().isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
        except Exception:
            continue
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def stable_hash(parts: Iterable[Any], length: int = 32) -> str:
    joined = "||".join(str(p) for p in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return digest[:length]


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def normalize_medium(channel: str | None, medium_map: Dict[str, str] | None = None) -> str:
    value = str(channel or "").strip().lower()
    if not value:
        return "unknown"
    if medium_map and value in medium_map:
        return str(medium_map[value])
    return value


def extract_opportunity_id(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value)
    m = re.search(r"opp[_-](\d+)", text, flags=re.IGNORECASE)
    if m:
        return f"opp_{m.group(1).zfill(3)}"
    return None


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
