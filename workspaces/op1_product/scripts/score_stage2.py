#!/usr/bin/env python3
"""
Generate Stage-2 scoring artifacts from Stage-1 opportunities.

Outputs:
- research/stage2_scoring.csv
- research/stage2_decision_log.json
"""

import argparse
import csv
import datetime as dt
import json
from pathlib import Path


def clamp(v, lo=1.0, hi=5.0):
    return max(lo, min(hi, round(v, 2)))


def recurring_hint(core_problem: str):
    t = core_problem.lower()
    keywords = ["monthly", "invoice", "report", "recurring", "weekly", "operations", "chargeback"]
    return any(k in t for k in keywords)


def has_loss_signal(opportunity: dict):
    allowed = {"money_loss", "time_cost", "workflow_break"}
    for ev in opportunity.get("pain_evidence", []):
        if ev.get("signal_type") in allowed:
            return True
    return False


def has_budget_or_intent_signal(opportunity: dict):
    if opportunity.get("budget_signal", {}).get("exists", False):
        return True
    for ev in opportunity.get("pain_evidence", []):
        if ev.get("signal_type") == "intent":
            return True
    return False


def confidence_level(opportunity: dict):
    source_count = int(opportunity.get("source_coverage", {}).get("distinct_source_count", 1))
    evidence_count = len(opportunity.get("pain_evidence", []))
    loss = has_loss_signal(opportunity)
    intent = has_budget_or_intent_signal(opportunity)

    # v2 confidence heuristic: give "high" only when evidence packet is complete.
    if source_count >= 2 and evidence_count >= 4 and loss and intent:
        return "high", "Cross-source corroboration + loss + intent signals present."
    if source_count >= 2 and evidence_count >= 3:
        return "medium", "Cross-source corroboration present but evidence quality is not fully complete."
    return "low", "Weak corroboration and/or sparse evidence coverage."


def heuristic_scores(opportunity: dict):
    evid = opportunity.get("pain_evidence", [])
    budget = opportunity.get("budget_signal", {}).get("exists", False)
    urgency = opportunity.get("urgency_signal", {}).get("exists", False)
    gate = opportunity.get("hard_gate_check", {})
    source_count = int(opportunity.get("source_coverage", {}).get("distinct_source_count", 1))

    loss = has_loss_signal(opportunity)
    intent = has_budget_or_intent_signal(opportunity)

    # Heuristic baseline with source corroboration factor
    pain = 3.2 + (0.7 if urgency else 0.2) + min(0.8, 0.2 * len(evid)) + (0.2 if loss else 0.0)
    pay = 2.8 + (0.9 if budget else 0.0) + (0.3 if intent else 0.0)
    speed = 3.1 + (0.8 if gate.get("mvp_in_14_days") else -0.7)
    reach = 3.0 + (0.8 if gate.get("reachable_users") else -0.8)
    whitespace = 2.9 + (0.2 if source_count >= 2 else -0.2)
    recurring = 3.1 + (0.8 if recurring_hint(opportunity.get("core_problem", "")) else 0.2)

    return {
        "pain_intensity": clamp(pain),
        "willingness_to_pay": clamp(pay),
        "mvp_speed": clamp(speed),
        "acquisition_reachability": clamp(reach),
        "competitive_whitespace": clamp(whitespace),
        "recurring_usage": clamp(recurring),
    }


def weighted(scores: dict, weights: dict):
    return round(sum(scores[k] * weights[k] for k in weights), 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="research/stage1_opportunity_records.json")
    ap.add_argument("--weights", default="framework/config/scoring_weights.default.json")
    ap.add_argument("--trust-config", default="framework/config/source_trust_rank.json")
    ap.add_argument("--csv-out", default="research/stage2_scoring.csv")
    ap.add_argument("--json-out", default="research/stage2_decision_log.json")
    ap.add_argument("--advance-threshold", type=float, default=3.8)
    ap.add_argument("--conf-high", type=float, default=1.0)
    ap.add_argument("--conf-medium", type=float, default=0.8)
    ap.add_argument("--conf-low", type=float, default=0.5)
    args = ap.parse_args()

    conf_map = {
        "high": args.conf_high,
        "medium": args.conf_medium,
        "low": args.conf_low,
    }

    src = Path(args.input)
    wpath = Path(args.weights)
    tpath = Path(args.trust_config)
    if not src.exists():
        raise FileNotFoundError(src)
    if not wpath.exists():
        raise FileNotFoundError(wpath)
    if not tpath.exists():
        raise FileNotFoundError(tpath)

    data = json.loads(src.read_text(encoding="utf-8"))
    weights = json.loads(wpath.read_text(encoding="utf-8"))
    trust = json.loads(tpath.read_text(encoding="utf-8"))
    opportunities = data.get("opportunities", [])

    gate_cfg = trust.get("stage2_evidence_gate", {})
    req_loss = bool(gate_cfg.get("require_loss_signal", False))
    req_intent = bool(gate_cfg.get("require_budget_or_intent_signal", False))

    decisions = []
    rows = []

    for opp in opportunities:
        scores = heuristic_scores(opp)
        stage1_pass = bool(opp.get("hard_gate_check", {}).get("pass", False))

        loss_ok = (not req_loss) or has_loss_signal(opp)
        intent_ok = (not req_intent) or has_budget_or_intent_signal(opp)
        hard_gate_pass = stage1_pass and loss_ok and intent_ok

        base_ws = weighted(scores, weights)
        conf_level, conf_reason = confidence_level(opp)
        conf_multiplier = conf_map.get(conf_level, 0.5)
        ws = round(base_ws * conf_multiplier, 3)

        if not stage1_pass:
            decision = "reject"
            reason = "Failed Stage-1 hard gates."
        elif not loss_ok:
            decision = "reject"
            reason = "Rejected by evidence gate: no loss signal."
        elif not intent_ok:
            decision = "hold"
            reason = "Hold: no budget/intent corroboration yet."
        elif ws >= args.advance_threshold:
            decision = "advance"
            reason = "Meets score threshold and evidence gates after confidence adjustment."
        else:
            decision = "hold"
            reason = "Passes gates but below advance threshold after confidence adjustment."

        decision_item = {
            "opportunity_id": opp.get("opportunity_id"),
            "hard_gate_pass": hard_gate_pass,
            "evidence_gate": {
                "stage1_pass": stage1_pass,
                "loss_signal_ok": loss_ok,
                "budget_or_intent_ok": intent_ok,
            },
            "confidence": {
                "level": conf_level,
                "multiplier": conf_multiplier,
                "reason": conf_reason,
            },
            "scores": {
                "pain_intensity": {
                    "score": scores["pain_intensity"],
                    "reason": "Urgency + evidence depth + loss signal heuristic.",
                    "risk_if_wrong": "Online signal may overstate real purchasing urgency.",
                },
                "willingness_to_pay": {
                    "score": scores["willingness_to_pay"],
                    "reason": "Budget signal + intent signal heuristic.",
                    "risk_if_wrong": "Tool interest may not convert into paid behavior.",
                },
                "mvp_speed": {
                    "score": scores["mvp_speed"],
                    "reason": "Based on Stage-1 MVP-in-14-days gate.",
                    "risk_if_wrong": "Integration requirements may expand scope.",
                },
                "acquisition_reachability": {
                    "score": scores["acquisition_reachability"],
                    "reason": "Based on reachable-first-20-users gate.",
                    "risk_if_wrong": "Public communities may not convert to interviews.",
                },
                "competitive_whitespace": {
                    "score": scores["competitive_whitespace"],
                    "reason": "Cross-source corroboration proxy + neutral baseline.",
                    "risk_if_wrong": "Incumbent strength may be underestimated.",
                },
                "recurring_usage": {
                    "score": scores["recurring_usage"],
                    "reason": "Recurring-workflow keyword heuristic.",
                    "risk_if_wrong": "Real usage frequency may be lower than inferred.",
                },
            },
            "base_weighted_score": base_ws,
            "weighted_score": ws,
            "decision": decision,
            "decision_reason": reason,
        }
        decisions.append(decision_item)

        rows.append(
            {
                "opportunity_id": opp.get("opportunity_id"),
                "hard_gate_pass": hard_gate_pass,
                **scores,
                "base_weighted_score": base_ws,
                "confidence_level": conf_level,
                "confidence_multiplier": conf_multiplier,
                "weighted_score": ws,
                "decision": decision,
            }
        )

    rows.sort(key=lambda r: r["weighted_score"], reverse=True)

    csv_out = Path(args.csv_out)
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    with csv_out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "opportunity_id",
                "hard_gate_pass",
                "pain_intensity",
                "willingness_to_pay",
                "mvp_speed",
                "acquisition_reachability",
                "competitive_whitespace",
                "recurring_usage",
                "base_weighted_score",
                "confidence_level",
                "confidence_multiplier",
                "weighted_score",
                "decision",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    json_out = Path(args.json_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(
        json.dumps(
            {
                "generated_at": dt.datetime.utcnow().isoformat() + "Z",
                "weights": weights,
                "confidence_multipliers": conf_map,
                "trust_config": args.trust_config,
                "decisions": decisions,
                "notes": "Scores are heuristic defaults; replace with interview-validated scoring in production.",
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"saved {csv_out}")
    print(f"saved {json_out}")
    print(f"opportunities={len(rows)}")


if __name__ == "__main__":
    main()
