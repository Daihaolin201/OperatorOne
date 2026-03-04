#!/usr/bin/env python3
"""
Build Stage-1 opportunity records from:
- research/reddit_signals.json (primary operator pain source)
- research/secondary_signals.json (secondary corroboration sources)

Output:
- research/stage1_idea_discovery/opportunity_records.json
"""

import argparse
import datetime as dt
import json
from pathlib import Path

THEMES = {
    "opp_001": {
        "name": "Invoice collection automation",
        "queries": [
            "chasing invoices",
            "follow up on unpaid invoices",
            "late payments",
            "client always late payment",
            "late invoices",
            "chasing payments",
            "invoice reminder",
        ],
        "must_have_keywords": [
            "invoice",
            "unpaid",
            "overdue",
            "late payment",
            "collections",
            "net 30",
            "accounts receivable",
        ],
        "segment": {
            "role": "Freelancer / small service owner",
            "company_size": "1-20",
            "industry": "Professional services",
        },
        "core_problem": "Overdue invoices are followed up manually and too late because owners avoid awkward collection messages.",
        "current_workaround": "Manual reminders via personal email and inconsistent escalation.",
        "distribution_entry": {
            "channel": "Freelancer and small-business communities",
            "first_20_targets_how": "Reach out to posters discussing overdue invoices and AR frustration",
        },
        "implementation_constraint": ["Email deliverability", "Accounting data import quality"],
    },
    "opp_002": {
        "name": "Chargeback operations",
        "queries": [
            "chargebacks time drain",
            "manual order fraud checks",
            "shopify disputes",
            "returns process painful",
            "refund abuse",
        ],
        "must_have_keywords": [
            "chargeback",
            "dispute",
            "fraud",
            "unauthorized",
            "item not received",
            "stripe",
            "shopify",
        ],
        "segment": {
            "role": "Ecommerce owner / operations manager",
            "company_size": "3-50",
            "industry": "DTC ecommerce",
        },
        "core_problem": "Chargeback handling is manual, time-consuming, and causes immediate cash-flow shocks.",
        "current_workaround": "Manual evidence gathering from order systems and customer support logs.",
        "distribution_entry": {
            "channel": "Ecommerce communities",
            "first_20_targets_how": "Shortlist stores actively discussing dispute losses",
        },
        "implementation_constraint": ["Store API access", "Dispute data normalization"],
    },
    "opp_003": {
        "name": "Agency reporting workflows",
        "queries": [
            "client reporting manual",
            "monthly report takes too long",
            "reporting automation",
            "custom report client dashboard",
            "reporting discrepancies GA4 Google Ads",
            "GA4 reporting discrepancies",
            "GA4 Google Ads discrepancy",
            "client reporting",
        ],
        "must_have_keywords": [
            "report",
            "reporting",
            "ga4",
            "google ads",
            "looker",
            "dashboard",
            "client",
        ],
        "segment": {
            "role": "Agency owner / account manager",
            "company_size": "5-50",
            "industry": "Marketing agencies",
        },
        "core_problem": "Monthly reporting is labor-heavy and often unclear for non-technical clients.",
        "current_workaround": "Manual exports and custom spreadsheet/report rewriting.",
        "distribution_entry": {
            "channel": "Agency founder communities",
            "first_20_targets_how": "Target agencies publicly discussing reporting bottlenecks",
        },
        "implementation_constraint": ["Cross-channel metric mapping", "Integration breadth expectations"],
    },
    "opp_004": {
        "name": "Property operations/reporting",
        "queries": [
            "maintenance tracking software",
            "rent collection reminders",
            "tenant communication tracking",
            "google sheets operations",
        ],
        "must_have_keywords": [
            "property",
            "tenant",
            "rent",
            "maintenance",
            "owner report",
            "landlord",
            "appfolio",
        ],
        "segment": {
            "role": "Property manager",
            "company_size": "2-30",
            "industry": "Property management",
        },
        "core_problem": "Owner and tenant workflows are fragmented, driving monthly manual spreadsheet work.",
        "current_workaround": "Default PM software output plus custom Excel edits.",
        "distribution_entry": {
            "channel": "Property management forums",
            "first_20_targets_how": "Reach operators with 20-150 doors and reporting pain",
        },
        "implementation_constraint": ["PM tool integrations", "Data privacy in owner/tenant records"],
    },
    "opp_005": {
        "name": "Expense/admin control",
        "queries": ["receipt bookkeeping manual", "automation too expensive"],
        "must_have_keywords": [
            "expense",
            "receipt",
            "reimburse",
            "bookkeeping",
            "duplicate",
            "policy",
            "fraud",
        ],
        "segment": {
            "role": "SMB owner / finance admin",
            "company_size": "10-100",
            "industry": "General SMB",
        },
        "core_problem": "Expense reimbursement remains chaotic and fraud-prone with manual checks.",
        "current_workaround": "Shared sheet + end-of-month manual reconciliation.",
        "distribution_entry": {
            "channel": "SMB operations communities",
            "first_20_targets_how": "Interview SMBs with recurring reimbursement delays",
        },
        "implementation_constraint": ["OCR quality", "Policy customization across teams"],
    },
    "opp_006": {
        "name": "Spreadsheet/PDF ops automation",
        "queries": ["spreadsheet errors", "inventory spreadsheet", "manual reporting"],
        "must_have_keywords": [
            "spreadsheet",
            "excel",
            "csv",
            "manual",
            "data entry",
            "pdf",
            "formula",
            "macro",
            "#ref",
        ],
        "segment": {
            "role": "Operations admin",
            "company_size": "5-80",
            "industry": "SMB operations/logistics",
        },
        "core_problem": "Core workflows depend on fragile spreadsheets and repetitive manual data entry.",
        "current_workaround": "Manual copy-paste from PDFs into spreadsheets and brittle formulas/macros.",
        "distribution_entry": {
            "channel": "SMB ops communities",
            "first_20_targets_how": "Reach teams reporting PDF-to-Excel pain and formula breakage",
        },
        "implementation_constraint": ["Supplier template variance", "Extraction confidence thresholds"],
    },
}


def post_text(post):
    return f"{post.get('title','')} {post.get('selftext','')}".lower()


def filter_by_keywords(posts, keywords):
    out = []
    for p in posts:
        txt = post_text(p)
        if any(k in txt for k in keywords):
            out.append(p)
    return out


def top_reddit_evidence(posts, max_items=3):
    ranked = sorted(
        posts,
        key=lambda p: (p.get("num_comments", 0) * 2 + p.get("score", 0), len(p.get("selftext", ""))),
        reverse=True,
    )
    picks = []
    for p in ranked[:max_items]:
        body = (p.get("selftext") or "").strip().replace("\n", " ")
        if not body:
            body = p.get("title", "")
        claim = body[:220] + ("..." if len(body) > 220 else "")
        signal_type = "pain"
        low = body.lower()
        if any(x in low for x in ["lost", "loss", "$", "cost", "fee", "penalt", "owe", "unpaid"]):
            signal_type = "money_loss"
        elif any(x in low for x in ["hour", "weekend", "manual", "time"]):
            signal_type = "time_cost"
        elif any(x in low for x in ["broken", "error", "ref", "chaos", "confused"]):
            signal_type = "workflow_break"
        picks.append(
            {
                "claim": claim,
                "source_url": p.get("permalink") or p.get("url") or "",
                "signal_type": signal_type,
                "source": "reddit_operator_communities",
            }
        )
    return picks


def top_secondary_evidence(signals, max_items=2):
    ranked = sorted(signals, key=lambda s: s.get("engagement_score", 0), reverse=True)
    picks = []
    for s in ranked[:max_items]:
        text = (s.get("text") or s.get("title") or "").strip().replace("\n", " ")
        claim = text[:220] + ("..." if len(text) > 220 else "")
        stype = s.get("signal_type") or "pain"
        source = s.get("source") or "secondary"
        picks.append(
            {
                "claim": claim,
                "source_url": s.get("url", ""),
                "signal_type": stype,
                "source": source,
            }
        )
    return picks


def infer_budget_urgency(evidence):
    text = " ".join(e.get("claim", "").lower() for e in evidence)
    budget = any(k in text for k in ["tool", "software", "app", "automation", "pay", "price", "subscription", "reviews"])
    urgency = any(k in text for k in ["lost", "late", "urgent", "week", "drowning", "bleeding", "owed", "unpaid", "manual"]) 
    return budget, urgency


def load_json(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="research/reddit_signals.json")
    ap.add_argument("--secondary", default="research/secondary_signals.json")
    ap.add_argument("--trust-config", default="framework/config/source_trust_rank.json")
    ap.add_argument("--output", default="research/stage1_idea_discovery/opportunity_records.json")
    args = ap.parse_args()

    primary = load_json(args.input)
    posts = primary.get("posts", [])

    secondary_doc = load_json(args.secondary)
    secondary_signals = secondary_doc.get("signals", [])

    trust_doc = load_json(args.trust_config)
    gate = trust_doc.get("stage2_evidence_gate", {})
    min_distinct_sources = int(gate.get("min_distinct_sources", 1))

    sec_by_opp = {}
    for s in secondary_signals:
        oid = s.get("opportunity_id")
        if not oid:
            continue
        sec_by_opp.setdefault(oid, []).append(s)

    opportunities = []

    for opp_id, spec in THEMES.items():
        matched = []
        for p in posts:
            q = set(p.get("queries_matched", []))
            if q.intersection(spec["queries"]):
                matched.append(p)

        matched = filter_by_keywords(matched, spec["must_have_keywords"])
        reddit_evid = top_reddit_evidence(matched, max_items=3)
        secondary_evid = top_secondary_evidence(sec_by_opp.get(opp_id, []), max_items=2)

        # Evidence blend: prioritize cross-source corroboration
        evidence = []
        evidence.extend(reddit_evid[:2])
        evidence.extend(secondary_evid[:2])
        if len(evidence) < 3:
            evidence.extend(reddit_evid[2:])

        # final cap to avoid bloat
        evidence = evidence[:4]

        budget, urgency = infer_budget_urgency(evidence)
        sources = sorted({e.get("source", "unknown") for e in evidence})
        min_sources_met = len(sources) >= min_distinct_sources

        opportunities.append(
            {
                "opportunity_id": opp_id,
                "target_segment": spec["segment"],
                "core_problem": spec["core_problem"],
                "current_workaround": spec["current_workaround"],
                "pain_evidence": evidence,
                "source_coverage": {
                    "distinct_sources": sources,
                    "distinct_source_count": len(sources),
                    "min_required": min_distinct_sources,
                    "min_sources_met": min_sources_met,
                },
                "budget_signal": {
                    "exists": budget,
                    "evidence": "Inferred from discussion around tooling cost/automation demand."
                    if budget
                    else "No explicit payment signal in selected evidence.",
                },
                "urgency_signal": {
                    "exists": urgency,
                    "evidence": "Inferred from loss/time-pressure language in evidence."
                    if urgency
                    else "No immediate urgency signal in selected evidence.",
                },
                "distribution_entry": spec["distribution_entry"],
                "implementation_constraint": spec["implementation_constraint"],
                "hard_gate_check": {
                    "buyer_clear": True,
                    "problem_evidenced": len(evidence) >= 3,
                    "reachable_users": True,
                    "mvp_in_14_days": True,
                    "min_distinct_sources_met": min_sources_met,
                    "pass": len(evidence) >= 3 and min_sources_met,
                },
            }
        )

    out = {
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "builder": "scripts/build_stage1_opportunities.py",
        "inputs": {
            "primary": args.input,
            "secondary": args.secondary,
            "trust_config": args.trust_config,
        },
        "opportunities": opportunities,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saved {out_path}")
    for o in opportunities:
        cov = o.get("source_coverage", {})
        print(
            o["opportunity_id"],
            "evidence",
            len(o.get("pain_evidence", [])),
            "sources",
            cov.get("distinct_source_count", 0),
            "pass",
            o.get("hard_gate_check", {}).get("pass"),
        )


if __name__ == "__main__":
    main()
