#!/usr/bin/env python3
"""Quick validation suite for Stage2 reply classifier."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("stage2_reply", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    script_path = Path(__file__).resolve().parent / "process_outreach_replies_stage2.py"
    mod = _load_module(script_path)

    cases = [
        (
            "Interested. Can we book a demo call tomorrow?",
            ("positive", "booked_call", True),
        ),
        (
            "No thanks, we already use another system and are not interested.",
            ("rejection", "no_interest", False),
        ),
        (
            "Not now. Please circle back next quarter.",
            ("not_now", "timing", False),
        ),
        (
            "Please unsubscribe me from future emails.",
            ("unsubscribe", "unsubscribe", False),
        ),
        (
            "This looks expensive and beyond our current budget.",
            ("objection", "budget", False),
        ),
        (
            "Looks good. Let's start this week, payment sent.",
            ("converted", "conversion", True),
        ),
    ]

    failed = []
    for text, expected in cases:
        got = mod._classify_reply(text)
        if tuple(got) != tuple(expected):
            failed.append({"text": text, "expected": expected, "got": got})

    if failed:
        print("Stage2 reply classifier validation FAILED")
        for row in failed:
            print("---")
            print("text:", row["text"])
            print("expected:", row["expected"])
            print("got:", row["got"])
        return 2

    print("Stage2 reply classifier validation PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
