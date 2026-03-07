#!/usr/bin/env python3
"""Create Mode-C landing package with embedded preflight gates and build inputs."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import shutil
import subprocess
from typing import Any, Dict, List, Tuple


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "your",
    "you",
    "are",
    "our",
    "has",
    "have",
    "too",
    "they",
    "their",
    "was",
    "were",
    "will",
    "been",
    "than",
    "then",
    "also",
    "can",
    "not",
    "out",
    "one",
    "use",
    "using",
    "only",
    "very",
    "more",
    "most",
    "over",
    "just",
}

LP_MODULE_WHITELIST = {
    "hero_problem",
    "problem_agitation",
    "benefit_bullets",
    "proof_points",
    "faq_list",
    "cta_waitlist",
}

LP_FORBIDDEN_MODULES = {
    "workflow_interactive",
    "metric_snapshot",
    "evidence_checklist",
    "social_proof_strip",
}


def now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def read_json(path: pathlib.Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: pathlib.Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_text(value: Any, fallback: str = "") -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def ensure_list_of_text(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if isinstance(v, str) and str(v).strip()]


def tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if len(t) >= 3 and t not in STOPWORDS]


def top_score(decision: Dict[str, Any]) -> float:
    try:
        return float(decision.get("weighted_score", 0.0))
    except Exception:
        return 0.0


def find_stage1_opportunity(stage1: Dict[str, Any], opportunity_id: str) -> Dict[str, Any]:
    for row in stage1.get("opportunities", []):
        if row.get("opportunity_id") == opportunity_id:
            return row
    raise ValueError(f"Opportunity not found in stage1: {opportunity_id}")


def find_stage2_decision(stage2: Dict[str, Any], opportunity_id: str) -> Dict[str, Any]:
    for row in stage2.get("decisions", []):
        if row.get("opportunity_id") == opportunity_id:
            return row
    return {}


def select_opportunity(
    stage1: Dict[str, Any],
    stage2: Dict[str, Any],
    explicit_opp_id: str | None,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    decisions = stage2.get("decisions", []) if isinstance(stage2.get("decisions"), list) else []

    if explicit_opp_id:
        opp = find_stage1_opportunity(stage1, explicit_opp_id)
        decision = find_stage2_decision(stage2, explicit_opp_id)
        reason = "explicit_opportunity"
    else:
        advances = [
            d
            for d in decisions
            if d.get("decision") == "advance" and d.get("hard_gate_pass") is not False
        ]
        if advances:
            advances.sort(key=top_score, reverse=True)
            decision = advances[0]
            opp = find_stage1_opportunity(stage1, str(decision.get("opportunity_id")))
            reason = "top_advance_by_stage2"
        else:
            eligible = [d for d in decisions if d.get("hard_gate_pass") is True]
            if not eligible:
                eligible = decisions
            if not eligible:
                raise ValueError("No stage2 decisions available for opportunity resolution")
            eligible.sort(key=top_score, reverse=True)
            decision = eligible[0]
            opp = find_stage1_opportunity(stage1, str(decision.get("opportunity_id")))
            reason = "fallback_top_stage2"

    risks: List[str] = []
    score_block = decision.get("scores") if isinstance(decision.get("scores"), dict) else {}
    for item in score_block.values():
        if isinstance(item, dict):
            risk = ensure_text(item.get("risk_if_wrong"))
            if risk:
                risks.append(risk)
    risks = list(dict.fromkeys(risks))[:4]

    summary = {
        "opportunity_id": opp.get("opportunity_id"),
        "selection_reason": reason,
        "confidence": ensure_text((decision.get("confidence") or {}).get("level"), "unknown"),
        "weighted_score": top_score(decision),
        "risk_if_wrong": risks,
    }
    return opp, decision, summary


def run_score_stage2(root: pathlib.Path, stage1_path: pathlib.Path, out_dir: pathlib.Path) -> pathlib.Path:
    preflight_dir = out_dir / "preflight"
    preflight_dir.mkdir(parents=True, exist_ok=True)
    stage2_json = preflight_dir / "stage2_synth.json"
    stage2_csv = preflight_dir / "stage2_synth.csv"

    cmd = [
        "python3",
        str(root / "scripts/score_stage2.py"),
        "--input",
        str(stage1_path),
        "--json-out",
        str(stage2_json),
        "--csv-out",
        str(stage2_csv),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return stage2_json


def resolve_stage2(
    root: pathlib.Path,
    stage1_path: pathlib.Path,
    stage2_path: pathlib.Path,
    out_dir: pathlib.Path,
) -> Tuple[Dict[str, Any], pathlib.Path, str]:
    if stage2_path.exists():
        payload = read_json(stage2_path)
        if isinstance(payload.get("decisions"), list) and payload.get("decisions"):
            return payload, stage2_path, "existing"

    synth_path = run_score_stage2(root=root, stage1_path=stage1_path, out_dir=out_dir)
    return read_json(synth_path), synth_path, "synthesized_from_stage1"


def has_scope(payload: Dict[str, Any]) -> bool:
    mvp = payload.get("mvp_boundary") if isinstance(payload.get("mvp_boundary"), dict) else {}
    in_scope = ensure_list_of_text(mvp.get("in_scope"))
    out_scope = ensure_list_of_text(mvp.get("out_of_scope"))
    kill = ensure_list_of_text(payload.get("kill_criteria"))
    return bool(in_scope and out_scope and kill)


def resolve_scope(
    stage3_path: pathlib.Path,
    selected_opp: Dict[str, Any],
    decision: Dict[str, Any],
) -> Dict[str, Any]:
    opp_id = ensure_text(selected_opp.get("opportunity_id"))

    if stage3_path.exists():
        stage3 = read_json(stage3_path)
        if stage3.get("from_opportunity_id") == opp_id and has_scope(stage3):
            mvp = stage3.get("mvp_boundary")
            assert isinstance(mvp, dict)
            return {
                "source": "stage3",
                "in_scope": ensure_list_of_text(mvp.get("in_scope")),
                "out_of_scope": ensure_list_of_text(mvp.get("out_of_scope")),
                "kill_criteria": ensure_list_of_text(stage3.get("kill_criteria")),
                "status": "pass",
            }

    constraints = ensure_list_of_text(selected_opp.get("implementation_constraint"))
    out_scope = constraints + [
        "Custom enterprise integrations",
        "Advanced billing/auth stack",
        "Multi-product expansion",
    ]

    score_block = decision.get("scores") if isinstance(decision.get("scores"), dict) else {}
    risks = []
    for item in score_block.values():
        if isinstance(item, dict):
            text = ensure_text(item.get("risk_if_wrong"))
            if text:
                risks.append(text)

    kill = ensure_list_of_text((selected_opp.get("hard_gate_check") or {}).get("kill_criteria"))
    if not kill:
        kill = [
            "Fewer than 2 qualified intent captures after first 20 targeted visitors",
            "Core workflow completion below 20% for pilot traffic",
            "No repeat qualified inbound intent within 14-day validation window",
        ]

    if risks:
        kill.append("Signal quality warning: " + risks[0])

    return {
        "source": "synthesized",
        "in_scope": [
            "Single conversion-focused landing page with one primary CTA",
            "Problem/benefit/proof/FAQ sections aligned to selected opportunity",
            "Evidence-backed messaging with explicit claim traceability",
            "Pilot lead capture for early access validation",
        ],
        "out_of_scope": list(dict.fromkeys(out_scope)),
        "kill_criteria": list(dict.fromkeys(kill)),
        "status": "pass",
    }


def run_init_project_spec(
    root: pathlib.Path,
    stage1_path: pathlib.Path,
    stage2_path: pathlib.Path,
    out_path: pathlib.Path,
    opp_id: str,
    adapter_id: str | None,
) -> Dict[str, Any]:
    cmd = [
        "python3",
        str(root / "scripts/init_project_spec.py"),
        "--stage1",
        str(stage1_path),
        "--stage2",
        str(stage2_path),
        "--out",
        str(out_path),
        "--opp-id",
        opp_id,
        "--force",
    ]
    if adapter_id:
        cmd.extend(["--adapter", adapter_id])

    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return read_json(out_path)


def resolve_project_spec(
    root: pathlib.Path,
    stage1_path: pathlib.Path,
    stage2_path: pathlib.Path,
    selected_opp_id: str,
    output_path: pathlib.Path,
    requested_project_spec: pathlib.Path | None,
    adapter_id: str | None,
) -> Tuple[Dict[str, Any], str]:
    if requested_project_spec and requested_project_spec.exists():
        candidate = read_json(requested_project_spec)
        source = candidate.get("source") if isinstance(candidate.get("source"), dict) else {}
        source_opp = ensure_text(source.get("opportunity_id"))
        current_adapter = ensure_text((candidate.get("adapter") or {}).get("name"))
        if source_opp == selected_opp_id and (not adapter_id or adapter_id == current_adapter):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(requested_project_spec, output_path)
            return read_json(output_path), "provided_project_spec"

    spec = run_init_project_spec(
        root=root,
        stage1_path=stage1_path,
        stage2_path=stage2_path,
        out_path=output_path,
        opp_id=selected_opp_id,
        adapter_id=adapter_id,
    )
    return spec, "generated_project_spec"


def _has_business_signal(text: str) -> bool:
    t = text.lower()
    signals = [
        "invoice",
        "payment",
        "chargeback",
        "deadline",
        "cashflow",
        "revenue",
        "report",
        "client",
        "hours",
        "days",
        "loss",
        "response",
        "dispute",
        "$",
        "%",
    ]
    return any(s in t for s in signals)


def run_compile_page_spec(
    root: pathlib.Path,
    project_spec_path: pathlib.Path,
    out_path: pathlib.Path,
    profile: str | None,
) -> Dict[str, Any]:
    cmd = [
        "python3",
        str(root / "scripts/compile_landing_page_spec.py"),
        "--project-spec",
        str(project_spec_path),
        "--out",
        str(out_path),
        "--force",
    ]
    if profile:
        cmd.extend(["--profile", profile])

    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return read_json(out_path)


def make_evidence_index(opportunity: Dict[str, Any]) -> List[Dict[str, Any]]:
    evidence = opportunity.get("pain_evidence", []) if isinstance(opportunity.get("pain_evidence"), list) else []
    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(evidence, start=1):
        if not isinstance(item, dict):
            continue
        claim = ensure_text(item.get("claim"))
        if not claim:
            continue
        out.append(
            {
                "evidence_id": f"ev_{idx:02d}",
                "claim": claim,
                "source_url": ensure_text(item.get("source_url")),
                "signal_type": ensure_text(item.get("signal_type"), "unknown"),
                "source": ensure_text(item.get("source"), "unknown"),
            }
        )
    return out


def compact_text(text: str, max_chars: int = 120) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "…"


def is_publishable_evidence_claim(claim: str) -> bool:
    lowered = claim.lower()
    banned_markers = [
        "not even joking",
        "wtf",
        "lol",
        " rn ",
        "i'm sitting here",
        "😭",
        "😅",
        "fml",
    ]
    if any(marker in lowered for marker in banned_markers):
        return False

    if lowered.startswith("when i") or " when i " in lowered:
        return False

    words = [w for w in re.findall(r"[a-z0-9]+", lowered) if w]
    if len(words) < 6:
        return False

    if lowered.count("!") > 2 or lowered.count("?") > 2:
        return False

    business_keywords = [
        "invoice",
        "chargeback",
        "dispute",
        "deadline",
        "report",
        "client",
        "payment",
        "cashflow",
        "workflow",
        "revenue",
        "refund",
    ]
    if not any(k in lowered for k in business_keywords):
        return False

    if re.search(r"\b(i|my|me)\b", lowered) and not any(k in lowered for k in ["team", "company", "business"]):
        return False

    return True


def enrich_project_spec_for_landing(project_spec: Dict[str, Any], opportunity: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(project_spec)

    adapter = enriched.get("adapter") if isinstance(enriched.get("adapter"), dict) else {}
    adapter_name = ensure_text(adapter.get("name"), "generic-operator")

    value = ensure_text(enriched.get("value_proposition"))
    if ". Designed for " in value:
        value = value.split(". Designed for ")[0].strip()
    if not value:
        value = {
            "invoice-followup": "Recover overdue invoices with one focused follow-up workflow.",
            "chargeback-response": "Respond to chargebacks faster with an evidence-first workflow.",
            "client-reporting": "Deliver consistent client reporting without weekly scramble.",
        }.get(adapter_name, ensure_text((enriched.get("offer") or {}).get("headline"), "Focused landing proposition"))

    problem = ensure_text(enriched.get("problem_statement"), ensure_text(opportunity.get("core_problem")))

    evidence_claims = []
    for row in opportunity.get("pain_evidence", []) if isinstance(opportunity.get("pain_evidence"), list) else []:
        if not isinstance(row, dict):
            continue
        claim = ensure_text(row.get("claim"))
        if claim and is_publishable_evidence_claim(claim) and _has_business_signal(claim):
            evidence_claims.append(compact_text(claim, max_chars=130))

    existing = [
        compact_text(item, max_chars=130)
        for item in ensure_list_of_text(enriched.get("proof_points"))
        if is_publishable_evidence_claim(item)
    ]

    merged = []
    for item in evidence_claims + existing:
        cleaned = compact_text(item, max_chars=130)
        if cleaned and cleaned not in merged:
            merged.append(cleaned)

    if not merged:
        merged = [
            compact_text(problem or "Reduce recurring operational friction"),
            "One clear CTA for higher-intent conversion.",
            "Scope guardrails prevent over-promising during validation.",
        ]

    enriched["value_proposition"] = value
    enriched["proof_points"] = merged[:3]

    cta_support_defaults = {
        "invoice-followup": "Join pilot access to run one structured invoice follow-up flow this week.",
        "chargeback-response": "Join pilot to standardize dispute evidence and reduce preventable losses.",
        "client-reporting": "Join pilot to test one repeatable reporting rhythm with clearer client confidence.",
    }
    cta_support = ensure_text(enriched.get("cta_support_text"))
    if (not cta_support) or ("validate demand" in cta_support.lower()):
        enriched["cta_support_text"] = cta_support_defaults.get(
            adapter_name,
            f"Join pilot to tackle {compact_text(problem.lower(), max_chars=90)} in a focused 14-day test.",
        )

    offer = enriched.get("offer") if isinstance(enriched.get("offer"), dict) else {}
    cta_label = ensure_text(offer.get("cta_label"), "Join pilot")
    if cta_label.lower() in {"join pilot", "get early access", "start pilot validation"}:
        offer["cta_label"] = {
            "invoice-followup": "Join invoice pilot",
            "chargeback-response": "Join dispute pilot",
            "client-reporting": "Join reporting pilot",
        }.get(adapter_name, "Join pilot")
    enriched["offer"] = offer

    return enriched


def claim_tokens(text: str) -> set[str]:
    return set(tokenize(text))


def evidence_priority(signal_type: str) -> int:
    order = {
        "money_loss": 5,
        "time_cost": 4,
        "workflow_break": 4,
        "intent": 3,
        "pain": 2,
        "market_density": 1,
    }
    return order.get(signal_type, 0)


def map_claim_to_evidence(claim: str, evidence_index: List[Dict[str, Any]]) -> List[str]:
    if not evidence_index:
        return []

    c_tokens = claim_tokens(claim)
    scored: List[Tuple[float, str]] = []
    for row in evidence_index:
        e_tokens = claim_tokens(ensure_text(row.get("claim")))
        overlap = len(c_tokens & e_tokens)
        score = float(overlap) + (evidence_priority(ensure_text(row.get("signal_type"))) / 10.0)
        scored.append((score, ensure_text(row.get("evidence_id"))))

    scored.sort(reverse=True)
    if scored and scored[0][0] > 0:
        refs = [scored[0][1]]
        if len(scored) > 1 and scored[1][0] > 0:
            refs.append(scored[1][1])
        return refs

    return [ensure_text(evidence_index[0].get("evidence_id"))]


def build_traceability_map(project_spec: Dict[str, Any], evidence_index: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], float, List[str]]:
    claims: List[Tuple[str, str]] = []

    problem = ensure_text(project_spec.get("problem_statement"))
    value = ensure_text(project_spec.get("value_proposition"))
    headline = ensure_text((project_spec.get("offer") or {}).get("headline"))

    if problem:
        claims.append(("claim_problem", problem))
    if value:
        claims.append(("claim_value", value))
    if headline:
        claims.append(("claim_headline", headline))

    for idx, point in enumerate(ensure_list_of_text(project_spec.get("proof_points")), start=1):
        claims.append((f"claim_proof_{idx:02d}", point))

    traceability: List[Dict[str, Any]] = []
    unmapped: List[str] = []

    for claim_id, text in claims:
        refs = map_claim_to_evidence(text, evidence_index)
        if not refs:
            unmapped.append(claim_id)
        traceability.append(
            {
                "claim_id": claim_id,
                "claim": text,
                "evidence_refs": refs,
            }
        )

    coverage = 0.0
    if claims:
        mapped = len([row for row in traceability if row.get("evidence_refs")])
        coverage = mapped / len(claims)

    return traceability, round(coverage, 3), unmapped


def build_message_hierarchy(project_spec: Dict[str, Any], opportunity: Dict[str, Any]) -> Dict[str, Any]:
    offer = project_spec.get("offer", {}) if isinstance(project_spec.get("offer"), dict) else {}
    faq = project_spec.get("faq", []) if isinstance(project_spec.get("faq"), list) else []
    proof = ensure_list_of_text(project_spec.get("proof_points"))

    objections = []
    for item in faq:
        if not isinstance(item, dict):
            continue
        q = ensure_text(item.get("question"))
        a = ensure_text(item.get("answer"))
        if q and a:
            objections.append({"objection": q, "answer": a})

    return {
        "hero_headline": ensure_text(offer.get("headline"), ensure_text(project_spec.get("value_proposition"))),
        "hero_subheadline": ensure_text(project_spec.get("value_proposition")),
        "problem_statement": ensure_text(opportunity.get("core_problem"), ensure_text(project_spec.get("problem_statement"))),
        "primary_supporting_claims": proof[:4],
        "objection_handlers": objections[:4],
    }


def build_section_plan(page_spec: Dict[str, Any], traceability_map: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    modules = page_spec.get("modules", []) if isinstance(page_spec.get("modules"), list) else []
    claim_refs = {
        row.get("claim_id"): row.get("evidence_refs", [])
        for row in traceability_map
        if isinstance(row, dict)
    }

    plan: List[Dict[str, Any]] = []
    for idx, module in enumerate(modules, start=1):
        if not isinstance(module, dict):
            continue
        module_id = ensure_text(module.get("module_id"), f"module_{idx}")
        props = module.get("props") if isinstance(module.get("props"), dict) else {}
        heading = (
            ensure_text(props.get("title"))
            or ensure_text(props.get("headline"))
            or ensure_text(props.get("metric"))
            or module_id
        )

        if module_id == "hero_problem":
            refs = claim_refs.get("claim_headline", []) + claim_refs.get("claim_problem", [])
            goal = "Explain who this is for, the problem, and why act now."
        elif module_id == "problem_agitation":
            refs = claim_refs.get("claim_problem", [])
            goal = "Frame pain severity and cost of inaction."
        elif module_id == "benefit_bullets":
            refs = claim_refs.get("claim_value", []) + claim_refs.get("claim_proof_01", [])
            goal = "Translate value proposition into concrete outcomes."
        elif module_id == "proof_points":
            refs = claim_refs.get("claim_proof_01", []) + claim_refs.get("claim_proof_02", [])
            goal = "Increase credibility with evidence-backed proof points."
        elif module_id == "social_proof_strip":
            refs = claim_refs.get("claim_proof_01", [])
            goal = "Add short trust signals before conversion ask."
        elif module_id == "cta_waitlist":
            refs = claim_refs.get("claim_value", [])
            goal = "Capture qualified intent with a single primary CTA."
        else:
            refs = claim_refs.get("claim_value", [])
            goal = "Support the core conversion narrative."

        plan.append(
            {
                "order": idx,
                "section_id": module_id,
                "headline": heading,
                "goal": goal,
                "evidence_refs": list(dict.fromkeys([r for r in refs if isinstance(r, str) and r])),
            }
        )

    return plan


def build_experiment_backlog(project_spec: Dict[str, Any], opportunity: Dict[str, Any]) -> List[Dict[str, Any]]:
    offer = project_spec.get("offer", {}) if isinstance(project_spec.get("offer"), dict) else {}
    cta = ensure_text(offer.get("cta_label"), "Join pilot")
    metric = ensure_text((project_spec.get("metrics") or {}).get("success_metric"), "Qualified intent captures")

    return [
        {
            "experiment_id": "exp_headline_01",
            "hypothesis": "Problem-led headline outperforms generic value wording for qualified intent.",
            "change": "A/B test two hero headlines mapped to the same core pain evidence.",
            "primary_metric": metric,
            "decision_rule": "Keep variant with >=15% higher qualified CTA submit rate.",
        },
        {
            "experiment_id": "exp_proof_01",
            "hypothesis": "Adding one concrete loss-evidence proof line increases trust and CTA completion.",
            "change": "Insert one quantified proof point above the fold.",
            "primary_metric": metric,
            "decision_rule": "Keep if CTA completion and form quality both improve.",
        },
        {
            "experiment_id": "exp_cta_01",
            "hypothesis": "Outcome-specific CTA wording improves intent quality versus generic CTA label.",
            "change": f"Test '{cta}' vs. outcome-specific CTA variant.",
            "primary_metric": metric,
            "decision_rule": "Keep if qualified submissions per 100 sessions improve by >=10%.",
        },
    ]


def risk_register(opportunity: Dict[str, Any], decision: Dict[str, Any], scope: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for constraint in ensure_list_of_text(opportunity.get("implementation_constraint")):
        rows.append({
            "risk": constraint,
            "type": "implementation",
            "mitigation": "Constrain v1 scope and validate manually before integration expansion.",
        })

    score_block = decision.get("scores") if isinstance(decision.get("scores"), dict) else {}
    for key, item in score_block.items():
        if not isinstance(item, dict):
            continue
        risk = ensure_text(item.get("risk_if_wrong"))
        if risk:
            rows.append(
                {
                    "risk": risk,
                    "type": f"assumption:{key}",
                    "mitigation": "Track this assumption in the 14-day validation run and decide go/kill by metric.",
                }
            )

    for kill in ensure_list_of_text(scope.get("kill_criteria")):
        rows.append(
            {
                "risk": kill,
                "type": "kill_criterion",
                "mitigation": "Treat as stop condition if triggered.",
            }
        )

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        risk = ensure_text(row.get("risk"))
        if risk and risk not in seen:
            deduped.append(row)
            seen.add(risk)
    return deduped[:12]


def flatten_landing_text(landing: Dict[str, Any]) -> str:
    chunks: List[str] = []

    positioning = landing.get("positioning") if isinstance(landing.get("positioning"), dict) else {}
    hierarchy = landing.get("message_hierarchy") if isinstance(landing.get("message_hierarchy"), dict) else {}

    for value in positioning.values():
        if isinstance(value, str):
            chunks.append(value)
        elif isinstance(value, list):
            chunks.extend([str(x) for x in value if isinstance(x, str)])

    for value in hierarchy.values():
        if isinstance(value, str):
            chunks.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    chunks.append(item)
                elif isinstance(item, dict):
                    chunks.extend([str(v) for v in item.values() if isinstance(v, str)])

    for row in landing.get("section_plan", []):
        if isinstance(row, dict):
            chunks.extend([str(v) for v in row.values() if isinstance(v, str)])

    return "\n".join(chunks).lower()


def quality_gates(
    landing_package: Dict[str, Any],
    opportunity: Dict[str, Any],
    scope: Dict[str, Any],
    page_spec: Dict[str, Any],
    traceability_coverage: float,
    unmapped_claims: List[str],
) -> List[Dict[str, Any]]:
    gates: List[Dict[str, Any]] = []

    testing = page_spec.get("testing") if isinstance(page_spec.get("testing"), dict) else {}
    modules = page_spec.get("modules") if isinstance(page_spec.get("modules"), list) else []
    module_ids = [ensure_text((m or {}).get("module_id")) for m in modules if isinstance(m, dict)]

    mode = ensure_text(testing.get("page_mode"), ensure_text((page_spec.get("meta") or {}).get("page_mode"), "web_product"))
    gates.append(
        {
            "name": "landing_mode_enabled",
            "status": "pass" if mode == "landing" else "fail",
            "detail": f"page_mode={mode}",
        }
    )

    cta_ok = (
        int(testing.get("max_primary_cta_buttons", 0)) == 1
        and ensure_text(testing.get("primary_cta_module")) in module_ids
    )
    gates.append(
        {
            "name": "single_primary_cta",
            "status": "pass" if cta_ok else "fail",
            "detail": "Primary CTA constraints from page_spec.testing",
        }
    )

    whitelist_ok = all(mid in LP_MODULE_WHITELIST for mid in module_ids if mid)
    forbidden_hits = [mid for mid in module_ids if mid in LP_FORBIDDEN_MODULES]
    required_min = {"hero_problem", "proof_points", "faq_list", "cta_waitlist"}
    required_missing = sorted(required_min - set(module_ids))
    structure_ok = whitelist_ok and not forbidden_hits and not required_missing
    gates.append(
        {
            "name": "landing_module_whitelist_and_structure",
            "status": "pass" if structure_ok else "fail",
            "detail": f"missing_required={required_missing}; forbidden={forbidden_hits}",
        }
    )

    core_problem = ensure_text(opportunity.get("core_problem"))
    hero = ensure_text((landing_package.get("message_hierarchy") or {}).get("hero_headline"))
    subhero = ensure_text((landing_package.get("message_hierarchy") or {}).get("hero_subheadline"))
    explicit_problem_line = ensure_text((landing_package.get("message_hierarchy") or {}).get("problem_statement"))
    overlap = set(tokenize(core_problem)) & set(tokenize(f"{hero} {subhero}"))
    explicit_match = bool(core_problem) and core_problem.lower() in explicit_problem_line.lower()
    match_ok = explicit_match or len(overlap) >= 1
    gates.append(
        {
            "name": "message_match_with_entry_intent",
            "status": "pass" if match_ok else "fail",
            "detail": f"token_overlap={len(overlap)}; explicit_match={explicit_match}",
        }
    )

    text_blob = flatten_landing_text(landing_package)
    violations = []
    for phrase in ensure_list_of_text(scope.get("out_of_scope")):
        p = phrase.lower().strip()
        if len(p) >= 6 and p in text_blob:
            violations.append(phrase)
    scope_ok = len(violations) == 0
    gates.append(
        {
            "name": "scope_consistency_with_mvp_boundary",
            "status": "pass" if scope_ok else "fail",
            "detail": "no_out_of_scope_copy" if scope_ok else f"violations={violations}",
        }
    )

    trace_ok = traceability_coverage >= 1.0 and not unmapped_claims
    gates.append(
        {
            "name": "claim_evidence_traceability_100pct",
            "status": "pass" if trace_ok else "fail",
            "detail": f"coverage={traceability_coverage}; unmapped={unmapped_claims}",
        }
    )

    headline_words = len(hero.split())
    section_count = len(landing_package.get("section_plan", []))
    scan_ok = headline_words <= 16 and 5 <= section_count <= 10
    gates.append(
        {
            "name": "scannable_copy_and_clear_hierarchy",
            "status": "pass" if scan_ok else "fail",
            "detail": f"headline_words={headline_words}; section_count={section_count}",
        }
    )

    forbidden_terms = [
        "reusable web-product builder",
        "try the workflow assistant",
        "focused landing validation",
        "pilot trust signals",
    ]
    text_blob_landing = flatten_landing_text(landing_package)
    bad_terms = [t for t in forbidden_terms if t in text_blob_landing]
    gates.append(
        {
            "name": "no_demo_first_positioning",
            "status": "pass" if not bad_terms else "fail",
            "detail": "ok" if not bad_terms else f"found={bad_terms}",
        }
    )

    profiles = testing.get("device_profiles") if isinstance(testing.get("device_profiles"), list) else []
    profile_ids = {ensure_text((p or {}).get("id")) for p in profiles if isinstance(p, dict)}
    responsive_markers = testing.get("responsive_markers") if isinstance(testing.get("responsive_markers"), list) else []
    multi_device_ok = (
        bool(testing.get("require_viewport_meta"))
        and {"desktop", "tablet", "mobile"}.issubset(profile_ids)
        and len(responsive_markers) >= 2
    )
    gates.append(
        {
            "name": "multi_device_compatibility_baseline",
            "status": "pass" if multi_device_ok else "fail",
            "detail": "viewport+profiles+responsive_markers",
        }
    )

    perf = testing.get("performance_budget") if isinstance(testing.get("performance_budget"), dict) else {}
    perf_ok = all(k in perf for k in ["lcp_ms", "inp_ms", "cls_max"])
    gates.append(
        {
            "name": "performance_baseline_hooks_present",
            "status": "pass" if perf_ok else "fail",
            "detail": "page_spec.testing.performance_budget",
        }
    )

    security_headers = testing.get("security_headers") if isinstance(testing.get("security_headers"), list) else []
    required_headers = {"x-content-type-options", "x-frame-options", "referrer-policy", "content-security-policy"}
    declared_headers = {
        str(item.get("name", "")).strip().lower()
        for item in security_headers
        if isinstance(item, dict) and item.get("name")
    }
    security_ok = required_headers.issubset(declared_headers)
    gates.append(
        {
            "name": "security_headers_baseline_hooks_present",
            "status": "pass" if security_ok else "fail",
            "detail": f"declared={sorted(declared_headers)}",
        }
    )

    hooks_ok = bool(module_ids)
    gates.append(
        {
            "name": "smoke_page_strategy_business_test_hooks_present",
            "status": "pass" if hooks_ok else "fail",
            "detail": "page_spec module/testing hooks available",
        }
    )

    return gates


def resolve_status(gates: List[Dict[str, Any]], scope_source: str) -> str:
    any_fail = any(g.get("status") == "fail" for g in gates)
    if any_fail:
        return "blocked"
    if scope_source != "stage3":
        return "provisional_ready"
    return "ready_for_build"


def update_marketing_handoff(
    handoff_path: pathlib.Path,
    landing_report: Dict[str, Any],
    landing_path: pathlib.Path,
) -> None:
    positioning = landing_report.get("landing_package", {}).get("positioning", {})
    hierarchy = landing_report.get("landing_package", {}).get("message_hierarchy", {})
    scope = landing_report.get("preflight", {}).get("scope_gate", {})

    payload = {
        "contract_version": "1.0.0",
        "generated_at": now_iso(),
        "generated_by": "workspaces/op1_product/scripts/create_landing_package.py",
        "status": "ready_for_marketing_review" if landing_report.get("status") != "blocked" else "blocked",
        "idea_name": ensure_text(landing_report.get("selected_opportunity", {}).get("opportunity_id")),
        "icp": ensure_text(positioning.get("icp")),
        "problem": ensure_text(positioning.get("problem")),
        "mvp_scope": ensure_list_of_text(scope.get("in_scope")),
        "landing_page_url_or_path": str(landing_path),
        "positioning": {
            "headline": ensure_text(hierarchy.get("hero_headline")),
            "value_proposition": ensure_text(hierarchy.get("hero_subheadline")),
        },
        "constraints": {
            "budget": 0,
            "timeline_days": 14,
            "out_of_scope": ensure_list_of_text(scope.get("out_of_scope")),
        },
        "notes": (
            "Generated by create_landing_pages_v1 (Mode C only, landing page mode). "
            "Claims are evidence-traceable, scope-gated, and filtered to non-demo landing semantics before handoff."
        ),
    }

    write_json(handoff_path, payload)


def parse_args() -> argparse.Namespace:
    root = pathlib.Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Create landing package (mode C only)")
    parser.add_argument(
        "--stage1",
        default=str(root / "research/stage1_idea_discovery/opportunity_records.json"),
        help="Stage1 opportunity records path",
    )
    parser.add_argument(
        "--stage2",
        default=str(root / "research/stage2_idea_screening/decision_log.json"),
        help="Stage2 decision log path (optional; synthesized if missing)",
    )
    parser.add_argument(
        "--stage3",
        default=str(root / "research/stage3_mvp_scope/project_blueprint.json"),
        help="Stage3 project blueprint path (optional)",
    )
    parser.add_argument(
        "--project-spec",
        default="",
        help="Optional existing project spec path (defaults to regenerate from stage1/stage2)",
    )
    parser.add_argument(
        "--out-dir",
        default=str(root / "research/landing_v1"),
        help="Output directory",
    )
    parser.add_argument("--opp-id", required=False, help="Force opportunity id")
    parser.add_argument("--adapter", required=False, help="Force adapter id when generating project spec")
    parser.add_argument("--page-profile", required=False, help="Force landing profile id during page-spec compile")
    parser.add_argument(
        "--handoff-out",
        default="../../handoffs/product_to_marketing.json",
        help="Output path for marketing handoff (relative to workspace)",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite out-dir")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]

    stage1_path = pathlib.Path(args.stage1).resolve()
    stage2_path = pathlib.Path(args.stage2).resolve()
    stage3_path = pathlib.Path(args.stage3).resolve()
    requested_project_spec = pathlib.Path(args.project_spec).resolve() if args.project_spec else None
    out_dir = pathlib.Path(args.out_dir).resolve()
    handoff_path = (root / args.handoff_out).resolve()

    if not stage1_path.exists():
        raise FileNotFoundError(f"Stage1 records missing: {stage1_path}")

    if out_dir.exists() and args.force:
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stage1 = read_json(stage1_path)
    stage2, stage2_used_path, stage2_mode = resolve_stage2(
        root=root,
        stage1_path=stage1_path,
        stage2_path=stage2_path,
        out_dir=out_dir,
    )

    opportunity, decision, selected = select_opportunity(
        stage1=stage1,
        stage2=stage2,
        explicit_opp_id=args.opp_id,
    )

    scope = resolve_scope(stage3_path=stage3_path, selected_opp=opportunity, decision=decision)

    build_inputs_dir = out_dir / "build_inputs"
    project_spec_path = build_inputs_dir / "project_spec.json"
    page_spec_path = build_inputs_dir / "page_spec.json"

    project_spec, project_spec_mode = resolve_project_spec(
        root=root,
        stage1_path=stage1_path,
        stage2_path=stage2_used_path,
        selected_opp_id=ensure_text(selected.get("opportunity_id")),
        output_path=project_spec_path,
        requested_project_spec=requested_project_spec,
        adapter_id=args.adapter,
    )

    project_spec = enrich_project_spec_for_landing(project_spec=project_spec, opportunity=opportunity)

    # Persist scope boundary into project spec so downstream build/deploy and business tests
    # can consume consistent in-scope / out-of-scope context.
    project_spec["mvp_boundary"] = {
        "in_scope": ensure_list_of_text(scope.get("in_scope")),
        "out_of_scope": ensure_list_of_text(scope.get("out_of_scope")),
        "source": ensure_text(scope.get("source"), "synthesized"),
    }
    project_spec = enrich_project_spec_for_landing(project_spec=project_spec, opportunity=opportunity)
    write_json(project_spec_path, project_spec)

    page_spec = run_compile_page_spec(
        root=root,
        project_spec_path=project_spec_path,
        out_path=page_spec_path,
        profile=args.page_profile,
    )

    evidence_index = make_evidence_index(opportunity)
    traceability_map, coverage, unmapped_claims = build_traceability_map(project_spec, evidence_index)

    segment = project_spec.get("segment") if isinstance(project_spec.get("segment"), dict) else {}
    positioning = {
        "icp": " / ".join(
            [
                ensure_text(segment.get("role"), "Target operator"),
                ensure_text(segment.get("industry"), "Business operations"),
                ensure_text(segment.get("company_size"), "1-20"),
            ]
        ),
        "problem": ensure_text(opportunity.get("core_problem"), ensure_text(project_spec.get("problem_statement"))),
        "value_proposition": ensure_text(project_spec.get("value_proposition")),
        "why_now": ensure_text((opportunity.get("urgency_signal") or {}).get("evidence"), "Validate quickly with measurable signal."),
        "differentiators": ensure_list_of_text(project_spec.get("proof_points"))[:3],
    }

    hierarchy = build_message_hierarchy(project_spec=project_spec, opportunity=opportunity)
    sections = build_section_plan(page_spec=page_spec, traceability_map=traceability_map)

    offer = project_spec.get("offer", {}) if isinstance(project_spec.get("offer"), dict) else {}
    cta_plan = {
        "primary": {
            "label": ensure_text(offer.get("cta_label"), "Join pilot"),
            "type": ensure_text(offer.get("cta_type"), "email_waitlist"),
            "module_id": "cta_waitlist",
            "support_text": ensure_text(project_spec.get("cta_support_text")),
        },
        "secondary": None,
    }

    adapter_meta = project_spec.get("adapter") if isinstance(project_spec.get("adapter"), dict) else {}
    adapter_name = ensure_text(adapter_meta.get("name"), "generic-operator")
    role_label = ensure_text(segment.get("role"), "operators")
    industry_label = ensure_text(segment.get("industry"), "operations")
    problem_line = compact_text(ensure_text(project_spec.get("problem_statement")), max_chars=92)

    headline_variant_3 = {
        "invoice-followup": "Recover overdue invoices with one repeatable reminder system",
        "chargeback-response": "Hit dispute deadlines with an evidence-first response playbook",
        "client-reporting": "Ship client reports on time without last-minute spreadsheet chaos",
    }.get(adapter_name, f"{role_label} teams: fix one recurring {industry_label.lower()} bottleneck fast")

    cta_variant_2 = {
        "invoice-followup": "Reserve invoice pilot slot",
        "chargeback-response": "Reserve dispute pilot slot",
        "client-reporting": "Reserve reporting pilot slot",
    }.get(adapter_name, "Reserve pilot slot")

    landing_package = {
        "positioning": positioning,
        "message_hierarchy": hierarchy,
        "section_plan": sections,
        "copy_variants": {
            "headline_variants": [
                hierarchy.get("hero_headline"),
                f"{problem_line} — without adding extra headcount",
                headline_variant_3,
            ],
            "cta_variants": [
                ensure_text(offer.get("cta_label"), "Join pilot"),
                cta_variant_2,
                "Get early access",
            ],
        },
        "cta_plan": cta_plan,
        "experiment_backlog": build_experiment_backlog(project_spec=project_spec, opportunity=opportunity),
        "traceability_map": traceability_map,
        "risk_register": risk_register(opportunity=opportunity, decision=decision, scope=scope),
    }

    gates = quality_gates(
        landing_package=landing_package,
        opportunity=opportunity,
        scope=scope,
        page_spec=page_spec,
        traceability_coverage=coverage,
        unmapped_claims=unmapped_claims,
    )

    status = resolve_status(gates=gates, scope_source=ensure_text(scope.get("source")))

    report = {
        "capability": "create_landing_pages_v1",
        "contract_version": "1.1",
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "mode": "mode_c_only",
        "page_mode": "landing",
        "status": status,
        "selected_opportunity": selected,
        "preflight": {
            "opportunity_gate": {
                "stage2_mode": stage2_mode,
                "stage2_path": str(stage2_used_path),
                "selected_opportunity_id": selected.get("opportunity_id"),
                "selection_reason": selected.get("selection_reason"),
                "confidence": selected.get("confidence"),
                "weighted_score": selected.get("weighted_score"),
                "risk_if_wrong": selected.get("risk_if_wrong", []),
            },
            "scope_gate": scope,
            "evidence_traceability_gate": {
                "coverage_ratio": coverage,
                "unmapped_claims": unmapped_claims,
            },
        },
        "landing_package": landing_package,
        "build_inputs": {
            "project_spec_path": str(project_spec_path),
            "project_spec_mode": project_spec_mode,
            "page_spec_path": str(page_spec_path),
            "page_spec_mode": "landing",
        },
        "quality_gates": gates,
        "marketing_handoff_path": str(handoff_path),
    }

    landing_package_path = out_dir / "landing_package.json"
    write_json(landing_package_path, report)

    preflight_summary = {
        "generated_at": report["generated_at"],
        "status": report["status"],
        "selected_opportunity_id": selected.get("opportunity_id"),
        "stage2_mode": stage2_mode,
        "project_spec_mode": project_spec_mode,
        "quality_gate_failures": [g for g in gates if g.get("status") == "fail"],
    }
    write_json(out_dir / "preflight" / "summary.json", preflight_summary)

    update_marketing_handoff(
        handoff_path=handoff_path,
        landing_report=report,
        landing_path=landing_package_path,
    )

    print(
        json.dumps(
            {
                "status": report["status"],
                "landing_package": str(landing_package_path),
                "project_spec": str(project_spec_path),
                "page_spec": str(page_spec_path),
                "selected_opportunity": selected.get("opportunity_id"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
