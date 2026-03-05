#!/usr/bin/env python3
"""Normalize and deduplicate Stage2 feedback events."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

from stage2_feedback_common import (
    now_iso,
    normalize_text,
    read_jsonl,
    resolve_repo_root,
    stable_hash,
    to_float,
    tokenize,
    write_json,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Normalize/dedup Stage2 feedback")
    p.add_argument("--repo-root", default="", help="OperatorOne repo root (auto-detect if omitted)")
    p.add_argument(
        "--in-dir",
        default="workspaces/op1_operations/research/stage2_feedback",
        help="Input/output directory (repo relative)",
    )
    return p.parse_args()


def _dedupe_key(row: Dict[str, Any]) -> str:
    norm = str(row.get("normalized_text") or "").strip()
    topic = str(row.get("topic") or "general")
    subtopic = str(row.get("subtopic") or "uncategorized")
    ftype = str(row.get("feedback_type") or "other")

    if norm:
        return stable_hash([ftype, topic, subtopic, norm], 32)

    fallback = " ".join(
        [
            str(row.get("detail") or ""),
            str(row.get("event_type") or ""),
            str(row.get("source_ref") or ""),
        ]
    ).strip()
    return stable_hash([ftype, topic, subtopic, fallback], 32)


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else resolve_repo_root(Path(__file__))
    in_dir = repo_root / args.in_dir

    raw_rows = read_jsonl(in_dir / "raw_feedback_events.latest.jsonl")
    if not raw_rows:
        write_json(in_dir / "feedback_normalize_report.latest.json", {
            "generated_at": now_iso(),
            "event_count": 0,
            "item_count": 0,
            "duplicate_reduction_ratio": 0.0,
            "unknown_topic_rate": 0.0,
            "notes": ["No raw feedback rows found."],
        })
        write_json(in_dir / "feedback_dedup.latest.json", {"generated_at": now_iso(), "items": []})
        write_jsonl(in_dir / "feedback_normalized.latest.jsonl", [])
        print({"event_count": 0, "item_count": 0})
        return 0

    normalized_rows: List[Dict[str, Any]] = []
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for row in raw_rows:
        raw_text = str(row.get("raw_text") or "").strip()
        norm = normalize_text(raw_text)
        tokens = tokenize(norm)

        enriched = dict(row)
        enriched["normalized_text"] = norm
        enriched["token_count"] = len(tokens)
        enriched["tokens"] = tokens[:20]
        enriched["dedupe_key"] = _dedupe_key({**row, "normalized_text": norm})

        groups[enriched["dedupe_key"]].append(enriched)
        normalized_rows.append(enriched)

    items: List[Dict[str, Any]] = []
    event_to_item: Dict[str, str] = {}

    for key in sorted(groups.keys()):
        rows = sorted(groups[key], key=lambda r: (str(r.get("feedback_time")), str(r.get("feedback_id"))))
        rep = rows[0]

        feedback_item_id = "fi_" + stable_hash([key, rep.get("topic"), rep.get("subtopic")], 16)

        for r in rows:
            event_to_item[str(r.get("feedback_id") or "")] = feedback_item_id

        sentiments = [to_float(r.get("sentiment_score"), 0.0) for r in rows]
        confidences = [to_float(r.get("confidence"), 0.0) for r in rows]
        evidences = [to_float(r.get("evidence_weight"), 0.0) for r in rows]
        severities = [to_float(r.get("severity"), 0.0) for r in rows]
        urgencies = [to_float(r.get("urgency"), 0.0) for r in rows]

        lead_ids = sorted({str(r.get("lead_id") or "").strip() for r in rows if str(r.get("lead_id") or "").strip()})
        actor_ids = sorted({str(r.get("actor_id") or "").strip() for r in rows if str(r.get("actor_id") or "").strip()})
        languages = Counter(str(r.get("language") or "unknown") for r in rows)
        adapters = Counter(str(r.get("source_adapter") or "unknown") for r in rows)
        journeys = Counter(str(r.get("journey_stage") or "unknown") for r in rows)

        item = {
            "feedback_item_id": feedback_item_id,
            "dedupe_key": key,
            "canonical_feedback_id": rep.get("feedback_id"),
            "duplicate_feedback_ids": [str(r.get("feedback_id") or "") for r in rows[1:]],
            "duplicate_count": len(rows),
            "unique_actor_count": len(actor_ids),
            "actor_ids": actor_ids[:20],
            "lead_ids": lead_ids,
            "feedback_type": rep.get("feedback_type"),
            "topic": rep.get("topic"),
            "subtopic": rep.get("subtopic"),
            "journey_stage": rep.get("journey_stage"),
            "first_seen": rows[0].get("feedback_time"),
            "last_seen": rows[-1].get("feedback_time"),
            "severity_max": int(max(severities) if severities else 0),
            "severity_avg": round(sum(severities) / len(severities), 4) if severities else 0.0,
            "urgency_max": int(max(urgencies) if urgencies else 0),
            "urgency_avg": round(sum(urgencies) / len(urgencies), 4) if urgencies else 0.0,
            "sentiment_score_avg": round(sum(sentiments) / len(sentiments), 4) if sentiments else 0.0,
            "confidence_avg": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
            "evidence_weight_avg": round(sum(evidences) / len(evidences), 4) if evidences else 0.0,
            "source_adapters": dict(sorted(adapters.items())),
            "language_mix": dict(sorted(languages.items())),
            "journey_stage_mix": dict(sorted(journeys.items())),
            "normalized_text": rep.get("normalized_text"),
            "raw_text_examples": [str(r.get("raw_text") or "") for r in rows[:3]],
            "tokens": rep.get("tokens") or [],
            "unknown_topic": str(rep.get("topic") or "general") == "general",
            "source_refs": [str(r.get("source_ref") or "") for r in rows[:20]],
            "event_refs": [str(r.get("feedback_id") or "") for r in rows[:20]],
        }
        items.append(item)

    # Attach item ids back to normalized rows.
    out_rows: List[Dict[str, Any]] = []
    for row in normalized_rows:
        r = dict(row)
        r["feedback_item_id"] = event_to_item.get(str(r.get("feedback_id") or ""))
        out_rows.append(r)

    out_rows = sorted(out_rows, key=lambda r: (str(r.get("feedback_time")), str(r.get("feedback_id"))))
    items = sorted(items, key=lambda r: (int(r.get("severity_max") or 0), int(r.get("duplicate_count") or 0)), reverse=True)

    unknown_items = sum(1 for i in items if i.get("unknown_topic"))

    report = {
        "generated_at": now_iso(),
        "event_count": len(out_rows),
        "item_count": len(items),
        "duplicate_events": len(out_rows) - len(items),
        "duplicate_reduction_ratio": round((len(out_rows) - len(items)) / max(1, len(out_rows)), 4),
        "unknown_topic_rate": round(unknown_items / max(1, len(items)), 4),
    }

    write_jsonl(in_dir / "feedback_normalized.latest.jsonl", out_rows)
    write_json(in_dir / "feedback_dedup.latest.json", {"generated_at": now_iso(), "items": items})
    write_json(in_dir / "feedback_normalize_report.latest.json", report)

    print({"event_count": len(out_rows), "item_count": len(items), "unknown_topic_rate": report["unknown_topic_rate"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
