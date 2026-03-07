#!/usr/bin/env python3
"""
Collect startup pain signals from Reddit search JSON endpoints.

Output:
- research/reddit_signals.json
- research/signal_summary.json
"""

import argparse
import datetime as dt
import json
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

DEFAULT_SUB_QUERIES = {
    "smallbusiness": [
        "manual reporting",
        "chasing invoices",
        "late payments",
        "appointment booking software",
        "receipt bookkeeping manual",
        "spreadsheet errors",
        "automation too expensive",
        "client onboarding forms",
        "double booking",
        "inventory spreadsheet",
    ],
    "agency": [
        "client reporting manual",
        "monthly report takes too long",
        "looker studio broken",
        "GA4 reporting discrepancies",
        "reporting automation",
    ],
    "ecommerce": [
        "chargebacks time drain",
        "returns process painful",
        "refund abuse",
        "manual order fraud checks",
        "shopify disputes",
    ],
    "freelance": [
        "chasing payments",
        "late invoices",
        "client always late payment",
        "invoice reminder",
    ],
    "PropertyManagement": [
        "maintenance tracking software",
        "google sheets operations",
        "tenant communication tracking",
        "rent collection reminders",
    ],
    "GoogleAnalytics": [
        "reporting discrepancies GA4 Google Ads",
        "custom report client dashboard",
    ],
    "PPC": [
        "GA4 Google Ads discrepancy",
        "client reporting",
    ],
}


def fetch_search(subreddit: str, query: str, limit: int, period: str):
    params = urllib.parse.urlencode(
        {
            "q": query,
            "restrict_sr": "1",
            "sort": "relevance",
            "t": period,
            "limit": str(limit),
        }
    )
    url = f"https://www.reddit.com/r/{subreddit}/search.json?{params}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; op1-product-bot/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.getcode() != 200:
            raise RuntimeError(f"HTTP {resp.getcode()} for {url}")
        payload = resp.read().decode("utf-8", errors="ignore")
    parsed = json.loads(payload)
    return parsed.get("data", {}).get("children", [])


def normalize_post(item):
    d = item.get("data", {})
    permalink = d.get("permalink", "")
    return {
        "id": d.get("id"),
        "subreddit": d.get("subreddit"),
        "title": d.get("title", ""),
        "selftext": d.get("selftext", ""),
        "score": d.get("score", 0),
        "num_comments": d.get("num_comments", 0),
        "created_utc": d.get("created_utc"),
        "url": d.get("url"),
        "permalink": (
            permalink
            if isinstance(permalink, str) and permalink.startswith("http")
            else f"https://www.reddit.com{permalink}"
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=25, help="results per query")
    ap.add_argument("--period", default="year", help="reddit time filter")
    ap.add_argument("--min-text", type=int, default=120)
    ap.add_argument(
        "--output-dir",
        default="research",
        help="directory for reddit_signals.json and signal_summary.json",
    )
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    posts = {}
    query_counts = defaultdict(int)
    errors = []

    for subreddit, queries in DEFAULT_SUB_QUERIES.items():
        for q in queries:
            try:
                children = fetch_search(subreddit, q, args.limit, args.period)
                query_counts[q] = len(children)
                for it in children:
                    p = normalize_post(it)
                    if not p["id"]:
                        continue
                    if p["id"] not in posts:
                        p["queries_matched"] = [q]
                        posts[p["id"]] = p
                    else:
                        posts[p["id"]]["queries_matched"].append(q)
            except Exception as e:
                errors.append({"subreddit": subreddit, "query": q, "error": str(e)})
            time.sleep(0.35)

    raw = list(posts.values())
    filtered = [
        p
        for p in raw
        if len((p.get("title", "") + " " + p.get("selftext", "")).strip()) >= args.min_text
        or p.get("num_comments", 0) >= 10
    ]

    filtered.sort(
        key=lambda x: (x.get("num_comments", 0) * 2 + x.get("score", 0), len(x.get("queries_matched", []))),
        reverse=True,
    )

    signals = {
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "collector": "scripts/search_startup_signals.py",
        "total_raw_posts": len(raw),
        "total_filtered_posts": len(filtered),
        "errors": errors,
        "posts": filtered,
    }

    summary = {
        "generated_at": signals["generated_at"],
        "total_queries": len(query_counts),
        "query_result_counts": dict(sorted(query_counts.items(), key=lambda kv: kv[0])),
        "raw_posts": len(raw),
        "filtered_posts": len(filtered),
        "errors": errors,
    }

    (out_dir / "reddit_signals.json").write_text(
        json.dumps(signals, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "signal_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"saved {out_dir / 'reddit_signals.json'}")
    print(f"saved {out_dir / 'signal_summary.json'}")
    print(f"raw={len(raw)} filtered={len(filtered)} errors={len(errors)}")


if __name__ == "__main__":
    main()
