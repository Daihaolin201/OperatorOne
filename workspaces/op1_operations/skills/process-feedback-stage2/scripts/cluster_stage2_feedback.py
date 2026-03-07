#!/usr/bin/env python3
"""Cluster normalized feedback items into stable Stage2 themes."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

from stage2_feedback_common import now_iso, read_json, resolve_repo_root, stable_hash, to_float, write_json


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cluster Stage2 feedback into themes")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root")
    p.add_argument(
        "--in-dir",
        default="workspaces/op1_operations/research/stage2_feedback",
        help="Input/output directory",
    )
    return p.parse_args()


def _theme_key(item: Dict[str, Any]) -> str:
    topic = str(item.get("topic") or "general")
    subtopic = str(item.get("subtopic") or "uncategorized")
    if subtopic and subtopic != "uncategorized":
        return f"{topic}:{subtopic}"

    tokens = item.get("tokens") if isinstance(item.get("tokens"), list) else []
    token_sig = "_".join([str(t) for t in tokens[:2] if str(t)])
    if token_sig:
        return f"{topic}:{token_sig}"
    return f"{topic}:general"


def _theme_name(topic: str, subtopic: str) -> str:
    t = str(topic or "general").replace("_", " ").title()
    s = str(subtopic or "general").replace("_", " ").title()
    if s and s != "Uncategorized":
        return f"{t} — {s}"
    return t


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else resolve_repo_root(Path(__file__))
    in_dir = repo_root / args.in_dir

    dedup = read_json(in_dir / "feedback_dedup.latest.json", default={}) or {}
    items = dedup.get("items", []) if isinstance(dedup.get("items"), list) else []

    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in items:
        if not isinstance(item, dict):
            continue
        buckets[_theme_key(item)].append(item)

    themes: List[Dict[str, Any]] = []
    item_to_theme: Dict[str, str] = {}

    for key in sorted(buckets.keys()):
        rows = buckets[key]
        if not rows:
            continue

        topic = str(rows[0].get("topic") or "general")
        subtopic = str(rows[0].get("subtopic") or "uncategorized")
        theme_id = "theme_" + stable_hash([key], 10)

        feedback_count = sum(int(r.get("duplicate_count") or 0) for r in rows)
        unique_actor_count = sum(int(r.get("unique_actor_count") or 0) for r in rows)
        avg_severity = (
            sum(to_float(r.get("severity_avg"), 0.0) * int(r.get("duplicate_count") or 1) for r in rows)
            / max(1, feedback_count)
        )
        avg_confidence = (
            sum(to_float(r.get("confidence_avg"), 0.0) * int(r.get("duplicate_count") or 1) for r in rows)
            / max(1, feedback_count)
        )
        avg_sentiment = (
            sum(to_float(r.get("sentiment_score_avg"), 0.0) * int(r.get("duplicate_count") or 1) for r in rows)
            / max(1, feedback_count)
        )

        source_mix = Counter()
        journey_mix = Counter()
        feedback_type_mix = Counter()
        lead_ids = set()
        evidence = []
        item_ids = []

        for r in rows:
            item_id = str(r.get("feedback_item_id") or "")
            if item_id:
                item_to_theme[item_id] = theme_id
                item_ids.append(item_id)

            if isinstance(r.get("source_adapters"), dict):
                for k2, v2 in r["source_adapters"].items():
                    source_mix[str(k2)] += int(v2)
            if isinstance(r.get("journey_stage_mix"), dict):
                for k2, v2 in r["journey_stage_mix"].items():
                    journey_mix[str(k2)] += int(v2)

            feedback_type_mix[str(r.get("feedback_type") or "other")] += int(r.get("duplicate_count") or 1)
            for lid in (r.get("lead_ids") if isinstance(r.get("lead_ids"), list) else []):
                if lid:
                    lead_ids.add(str(lid))

            for ex in (r.get("raw_text_examples") if isinstance(r.get("raw_text_examples"), list) else []):
                txt = str(ex or "").strip()
                if txt:
                    evidence.append(txt)

        trend = "recurring" if feedback_count >= 3 else "emerging"

        theme = {
            "theme_id": theme_id,
            "theme_key": key,
            "theme_name": _theme_name(topic, subtopic),
            "topic": topic,
            "subtopic": subtopic,
            "feedback_count": feedback_count,
            "feedback_items": len(rows),
            "unique_actor_count": unique_actor_count,
            "avg_severity": round(avg_severity, 4),
            "avg_confidence": round(avg_confidence, 4),
            "avg_sentiment_score": round(avg_sentiment, 4),
            "feedback_type_mix": dict(sorted(feedback_type_mix.items())),
            "source_mix": dict(sorted(source_mix.items())),
            "journey_stage_mix": dict(sorted(journey_mix.items())),
            "lead_ids": sorted(lead_ids),
            "evidence_samples": evidence[:5],
            "trend_label": trend,
            "theme_priority_proxy": round(feedback_count * max(0.5, avg_severity), 4),
            "item_ids": item_ids,
        }
        themes.append(theme)

    themes = sorted(themes, key=lambda r: (to_float(r.get("theme_priority_proxy"), 0.0), to_float(r.get("avg_severity"), 0.0)), reverse=True)

    payload = {
        "generated_at": now_iso(),
        "theme_count": len(themes),
        "themes": themes,
        "item_to_theme": item_to_theme,
    }

    write_json(in_dir / "theme_clusters.latest.json", payload)
    print({"theme_count": len(themes)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
