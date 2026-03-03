#!/usr/bin/env python3
"""
Collect secondary-source signals for startup idea discovery.

Sources:
- Hacker News (Algolia API)
- Shopify App Store (autocomplete + category pages)

Output:
- research/secondary_signals.json
"""

import argparse
import datetime as dt
import html
import json
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

HN_QUERY_MAP = {
    "opp_001": [
        "unpaid invoices",
        "invoice reminders",
        "accounts receivable automation",
    ],
    "opp_002": [
        "chargebacks ecommerce",
        "friendly fraud",
        "dispute management",
    ],
    "opp_003": [
        "client reporting dashboard",
        "GA4 reporting",
        "agency reporting",
    ],
    "opp_004": [
        "property management reporting",
        "maintenance request tracking",
        "owner statements",
    ],
    "opp_005": [
        "expense reimbursement workflow",
        "receipt fraud detection",
        "employee expense policy",
    ],
    "opp_006": [
        "spreadsheet errors operations",
        "pdf to excel automation",
        "manual data entry automation",
    ],
}

SHOPIFY_QUERY_MAP = {
    "opp_001": ["invoice"],
    "opp_002": ["chargeback", "fraud", "returns"],
    "opp_003": ["reporting", "analytics"],
    "opp_005": ["receipt", "expenses"],
    "opp_006": ["automation", "data import"],
}

HN_KEYWORDS = {
    "opp_001": ["invoice", "unpaid", "receivable", "late payment"],
    "opp_002": ["chargeback", "fraud", "dispute", "unauthorized"],
    "opp_003": ["report", "reporting", "dashboard", "ga4", "analytics", "client"],
    "opp_004": ["property", "tenant", "maintenance", "owner", "rent"],
    "opp_005": ["expense", "receipt", "reimburse", "policy"],
    "opp_006": ["spreadsheet", "excel", "pdf", "data entry", "automation"],
}


def fetch_url(url, headers=None, timeout=30):
    req = urllib.request.Request(
        url,
        headers=headers
        or {
            "User-Agent": "Mozilla/5.0 (compatible; op1-product-bot/1.0)",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def collect_hn(max_hits=12, sleep_ms=250, max_age_years=8, min_engagement=2):
    signals = []
    seen = set()
    cutoff = int(time.time()) - int(max_age_years * 365 * 24 * 3600)

    for opp_id, queries in HN_QUERY_MAP.items():
        opp_keywords = [k.lower() for k in HN_KEYWORDS.get(opp_id, [])]
        for q in queries:
            params = urllib.parse.urlencode(
                {
                    "query": q,
                    "tags": "story",
                    "hitsPerPage": str(max_hits),
                }
            )
            url = f"https://hn.algolia.com/api/v1/search?{params}"
            try:
                payload = fetch_url(url)
                data = json.loads(payload)
                hits = data.get("hits", [])
                for h in hits:
                    oid = h.get("objectID")
                    if not oid or oid in seen:
                        continue

                    created_at_i = int(h.get("created_at_i") or 0)
                    if created_at_i and created_at_i < cutoff:
                        continue

                    title = (h.get("title") or "").strip()
                    story_text = (h.get("story_text") or "").strip()
                    if not title and not story_text:
                        continue

                    signal_text = " ".join(x for x in [title, story_text] if x).strip()
                    if len(signal_text) < 40:
                        continue

                    low = signal_text.lower()
                    if opp_keywords and not any(k in low for k in opp_keywords):
                        continue

                    points = h.get("points") or 0
                    num_comments = h.get("num_comments") or 0
                    engagement = points + (num_comments * 2)
                    if engagement < min_engagement:
                        continue

                    seen.add(oid)
                    target_url = h.get("url") or f"https://news.ycombinator.com/item?id={oid}"

                    signals.append(
                        {
                            "id": f"hn_{oid}",
                            "source": "hackernews",
                            "opportunity_id": opp_id,
                            "query": q,
                            "title": title,
                            "text": signal_text[:500],
                            "url": target_url,
                            "signal_type": "pain",
                            "engagement_score": engagement,
                        }
                    )
            except Exception:
                continue
            time.sleep(sleep_ms / 1000)

    return signals


def clean_text(s):
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def parse_shopify_feature_page(page_html, page_url, opp_id, query, feature_name):
    out = []

    apps_count = 0
    m_count = re.search(r"([0-9,]+)\s+apps\s+with", page_html, flags=re.I)
    if m_count:
        apps_count = int(m_count.group(1).replace(",", ""))

    out.append(
        {
            "id": f"shopify_feature_{opp_id}_{abs(hash(page_url))}",
            "source": "shopify_app_store",
            "opportunity_id": opp_id,
            "query": query,
            "title": feature_name,
            "text": f"{apps_count} apps listed for this feature category on Shopify App Store",
            "url": page_url,
            "signal_type": "market_density",
            "engagement_score": min(apps_count, 500),
        }
    )

    app_pattern = re.compile(
        r'<a href="(https://apps\.shopify\.com/[^"?]+)[^"]*"\s*class="[^"]*">\s*([^<]+?)\s*</a>.*?'
        r'<span class="tw-sr-only">\s*([0-9,]+)\s+total reviews</span>.*?'
        r'<div class="tw-text-fg-secondary tw-text-body-xs">\s*(.*?)\s*</div>',
        flags=re.S | re.I,
    )

    app_signals = []
    seen_links = set()
    for match in app_pattern.finditer(page_html):
        link = clean_text(match.group(1))
        if link in seen_links:
            continue
        seen_links.add(link)

        app_name = clean_text(match.group(2))
        review_count = int(match.group(3).replace(",", ""))
        blurb = clean_text(match.group(4))

        app_signals.append(
            {
                "id": f"shopify_app_{abs(hash(link))}",
                "source": "shopify_app_store",
                "opportunity_id": opp_id,
                "query": query,
                "title": app_name,
                "text": f"{blurb} ({review_count} reviews)",
                "url": link,
                "signal_type": "intent",
                "engagement_score": min(review_count, 1000),
            }
        )

    app_signals.sort(key=lambda x: x["engagement_score"], reverse=True)
    out.extend(app_signals[:5])
    return out


def collect_shopify(max_features_per_query=2, sleep_ms=250):
    signals = []
    for opp_id, queries in SHOPIFY_QUERY_MAP.items():
        for q in queries:
            try:
                auto_url = (
                    "https://apps.shopify.com/search/autocomplete?"
                    + urllib.parse.urlencode({"q": q})
                )
                payload = fetch_url(
                    auto_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; op1-product-bot/1.0)",
                        "X-Requested-With": "XMLHttpRequest",
                        "Content-Type": "application/json",
                    },
                )
                data = json.loads(payload)
                features = data.get("category_features", [])[:max_features_per_query]

                for ft in features:
                    target = ft.get("target")
                    fname = ft.get("name") or q
                    if not target:
                        continue
                    try:
                        page_html = fetch_url(target)
                        parsed = parse_shopify_feature_page(
                            page_html=page_html,
                            page_url=target,
                            opp_id=opp_id,
                            query=q,
                            feature_name=fname,
                        )
                        signals.extend(parsed)
                    except Exception:
                        continue
                    time.sleep(sleep_ms / 1000)
            except Exception:
                continue
            time.sleep(sleep_ms / 1000)

    # dedupe by id
    dedup = {}
    for s in signals:
        dedup[s["id"]] = s
    return list(dedup.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="research/secondary_signals.json")
    ap.add_argument("--hn-max-hits", type=int, default=12)
    ap.add_argument("--hn-max-age-years", type=int, default=8)
    ap.add_argument("--hn-min-engagement", type=int, default=2)
    args = ap.parse_args()

    hn = collect_hn(
        max_hits=args.hn_max_hits,
        max_age_years=args.hn_max_age_years,
        min_engagement=args.hn_min_engagement,
    )
    shopify = collect_shopify()

    all_signals = hn + shopify

    counts_by_source = defaultdict(int)
    counts_by_opp = defaultdict(int)
    for s in all_signals:
        counts_by_source[s["source"]] += 1
        counts_by_opp[s["opportunity_id"]] += 1

    out = {
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "collector": "scripts/search_secondary_sources.py",
        "sources": ["hackernews", "shopify_app_store"],
        "summary": {
            "total_signals": len(all_signals),
            "counts_by_source": dict(counts_by_source),
            "counts_by_opportunity": dict(counts_by_opp),
        },
        "signals": all_signals,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"saved {out_path}")
    print(f"total_signals={len(all_signals)}")
    print(f"by_source={dict(counts_by_source)}")


if __name__ == "__main__":
    main()
