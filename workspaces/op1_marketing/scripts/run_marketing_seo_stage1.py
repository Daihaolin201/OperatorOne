#!/usr/bin/env python3
"""
Stage1 Marketing SEO capability runner (continuous-shadow ready).

Implements:
1) Full product artifact sync (lossless mirror + completeness gate)
2) Context index build (project-agnostic)
3) Keyword graph generation
4) SEO experiment synthesis
5) Shadow scoring + queue decisions (Ready / Hold / Drop)
6) Brief generation + decision log

Default mode is shadow (publish/index disabled).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


REQUIRED_INPUTS: List[Dict[str, Any]] = [
    {"id": "stage1_opportunity_records", "path": "../op1_product/research/stage1_idea_discovery/opportunity_records.json", "glob": False, "min_matches": 1},
    {"id": "stage2_scoring", "path": "../op1_product/research/stage2_idea_screening/scoring.csv", "glob": False, "min_matches": 1},
    {"id": "stage2_decision_log", "path": "../op1_product/research/stage2_idea_screening/decision_log.json", "glob": False, "min_matches": 1},
    {"id": "stage3_project_blueprint", "path": "../op1_product/research/stage3_mvp_scope/project_blueprint.json", "glob": False, "min_matches": 1},
    {"id": "stage2_web_run", "path": "../op1_product/research/stage2_web_product/run.latest.json", "glob": False, "min_matches": 1},
    {"id": "stage2_web_state", "path": "../op1_product/research/stage2_web_product/state.latest.json", "glob": False, "min_matches": 1},
    {"id": "stage3_landing_run", "path": "../op1_product/research/stage3_landing_launch/run.latest.json", "glob": False, "min_matches": 1},
    {"id": "live_examples", "path": "../op1_product/research/live_examples.latest.json", "glob": False, "min_matches": 1},
    {"id": "project_specs", "path": "../op1_product/research/build_deploy_v1/project_spec*.json", "glob": True, "min_matches": 1},
    {"id": "landing_package", "path": "../op1_product/research/landing_v1/landing_package.json", "glob": False, "min_matches": 1},
    {"id": "landing_contract_test", "path": "../op1_product/research/landing_v1/landing_contract_test.latest.json", "glob": False, "min_matches": 1},
    {"id": "landing_semantic_test", "path": "../op1_product/research/landing_v1/landing_semantic_test.latest.json", "glob": False, "min_matches": 1},
    {"id": "product_to_marketing_handoff", "path": "../../handoffs/product_to_marketing.json", "glob": False, "min_matches": 1},
]

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
    "your",
    "you",
    "this",
    "their",
    "than",
    "will",
    "without",
    "using",
    "use",
    "across",
    "through",
    "can",
    "too",
    "very",
    "about",
    "after",
    "before",
    "over",
    "under",
    "up",
    "down",
    "vs",
}

INTENT_PRIORITY = {"BOFU": 3, "MOFU": 2, "TOFU": 1}


def now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel_from_root(root: Path, path: Path) -> str:
    return Path(os.path.relpath(path, root)).as_posix()


def safe_slug(value: str, max_len: int = 64) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip().lower()).strip("-")
    if not cleaned:
        cleaned = "item"
    return cleaned[:max_len]


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def tokenize(text: str) -> List[str]:
    parts = re.findall(r"[a-zA-Z0-9]+", (text or "").lower())
    return [p for p in parts if len(p) > 2 and p not in STOPWORDS]


def compact_phrase(text: str, max_words: int = 6) -> str:
    tokens = tokenize(text)
    if not tokens:
        return ""
    return " ".join(tokens[:max_words])


def mirror_relative_path(root: Path, source_abs: Path) -> Path:
    source_abs = source_abs.resolve()
    root = root.resolve()

    if source_abs.is_relative_to(root):
        return source_abs.relative_to(root)

    rel = Path(os.path.relpath(source_abs, root))
    safe_parts: List[str] = []
    for part in rel.parts:
        if part == "..":
            safe_parts.append("__up__")
        elif part == ".":
            continue
        else:
            safe_parts.append(part)
    return Path("external").joinpath(*safe_parts)


def resolve_input_files(root: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    req_status: List[Dict[str, Any]] = []
    file_records: List[Dict[str, Any]] = []

    required_count = len(REQUIRED_INPUTS)
    present_count = 0
    missing_requirement_ids: List[str] = []

    for req in REQUIRED_INPUTS:
        req_id = req["id"]
        req_path = req["path"]
        is_glob = bool(req.get("glob"))
        min_matches = int(req.get("min_matches", 1))

        matches: List[Path] = []
        if is_glob:
            matches = sorted(p.resolve() for p in root.glob(req_path) if p.is_file())
        else:
            candidate = (root / req_path).resolve()
            if candidate.is_file():
                matches = [candidate]

        is_present = len(matches) >= min_matches
        if is_present:
            present_count += 1
        else:
            missing_requirement_ids.append(req_id)

        match_rel_paths = [rel_from_root(root, p) for p in matches]
        req_status.append(
            {
                "id": req_id,
                "path": req_path,
                "glob": is_glob,
                "min_matches": min_matches,
                "matched_count": len(matches),
                "matched_files": match_rel_paths,
                "status": "present" if is_present else "missing",
            }
        )

        for source_abs in matches:
            source_rel = rel_from_root(root, source_abs)
            stat = source_abs.stat()
            mirror_rel = mirror_relative_path(root, source_abs)
            file_records.append(
                {
                    "requirement_id": req_id,
                    "source_path": source_rel,
                    "source_abs": str(source_abs),
                    "mirror_path": mirror_rel.as_posix(),
                    "size_bytes": stat.st_size,
                    "mtime": dt.datetime.utcfromtimestamp(stat.st_mtime).replace(microsecond=0).isoformat() + "Z",
                    "sha256": sha256_file(source_abs),
                }
            )

    file_records.sort(key=lambda x: (x["requirement_id"], x["source_path"]))

    completeness = {
        "required": required_count,
        "present": present_count,
        "ratio": round(present_count / required_count, 6) if required_count else 1.0,
        "missing_requirement_ids": missing_requirement_ids,
    }
    return req_status, file_records, completeness


def copy_mirror(root: Path, mirror_dir: Path, file_records: List[Dict[str, Any]]) -> None:
    if mirror_dir.exists():
        shutil.rmtree(mirror_dir)
    mirror_dir.mkdir(parents=True, exist_ok=True)

    for rec in file_records:
        source_abs = Path(rec["source_abs"]).resolve()
        mirror_rel = Path(rec["mirror_path"])
        dest = (mirror_dir / mirror_rel).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_abs, dest)


def build_snapshot(
    root: Path,
    req_status: List[Dict[str, Any]],
    file_records: List[Dict[str, Any]],
    completeness: Dict[str, Any],
    generated_at: str,
) -> Dict[str, Any]:
    material = "|".join(f"{x['source_path']}:{x['sha256']}" for x in file_records)
    snap_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16] if material else "empty"
    snapshot_id = f"snap_{generated_at.replace('-', '').replace(':', '').replace('T', '').replace('Z', '')}_{snap_hash}"

    return {
        "status": "ok" if completeness.get("ratio", 0.0) >= 1.0 else "blocked_input_incomplete",
        "generated_at": generated_at,
        "snapshot_id": snapshot_id,
        "workspace_root": str(root.resolve()),
        "required_files": [item["path"] for item in REQUIRED_INPUTS],
        "requirements": req_status,
        "files": file_records,
        "completeness": completeness,
    }


def build_delta(prev_snapshot: Dict[str, Any], cur_snapshot: Dict[str, Any], generated_at: str) -> Dict[str, Any]:
    prev_files = {f.get("source_path"): f for f in (prev_snapshot or {}).get("files", []) if f.get("source_path")}
    cur_files = {f.get("source_path"): f for f in (cur_snapshot or {}).get("files", []) if f.get("source_path")}

    added: List[Dict[str, Any]] = []
    changed: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []

    for source_path, cur in cur_files.items():
        if source_path not in prev_files:
            added.append({"source_path": source_path, "requirement_id": cur.get("requirement_id")})
            continue
        prev = prev_files[source_path]
        if prev.get("sha256") != cur.get("sha256") or prev.get("size_bytes") != cur.get("size_bytes"):
            changed.append(
                {
                    "source_path": source_path,
                    "requirement_id": cur.get("requirement_id"),
                    "prev_sha256": prev.get("sha256"),
                    "sha256": cur.get("sha256"),
                }
            )

    for source_path, prev in prev_files.items():
        if source_path not in cur_files:
            removed.append({"source_path": source_path, "requirement_id": prev.get("requirement_id")})

    return {
        "status": "ok",
        "generated_at": generated_at,
        "base_snapshot_id": (prev_snapshot or {}).get("snapshot_id"),
        "current_snapshot_id": cur_snapshot.get("snapshot_id"),
        "added": sorted(added, key=lambda x: x["source_path"]),
        "changed": sorted(changed, key=lambda x: x["source_path"]),
        "removed": sorted(removed, key=lambda x: x["source_path"]),
    }


def map_requirement_files(file_records: List[Dict[str, Any]]) -> Dict[str, List[Path]]:
    out: Dict[str, List[Path]] = {}
    for rec in file_records:
        out.setdefault(rec["requirement_id"], []).append(Path(rec["source_abs"]))
    for key in out:
        out[key] = sorted(set(out[key]))
    return out


def parse_decision_signals(decision_log_paths: List[Path]) -> Dict[str, Dict[str, Any]]:
    signals: Dict[str, Dict[str, Any]] = {}
    for path in decision_log_paths:
        data = read_json(path, default={}) or {}
        for item in data.get("ranking", []):
            opp_id = item.get("opportunity_id")
            if not opp_id:
                continue
            signals.setdefault(opp_id, {})
            signals[opp_id].update(
                {
                    "rank": item.get("rank"),
                    "weighted_score": item.get("weighted_score"),
                    "decision": item.get("decision"),
                }
            )

        for item in data.get("decisions", []):
            opp_id = item.get("opportunity_id")
            if not opp_id:
                continue
            signals.setdefault(opp_id, {})
            if item.get("weighted_score") is not None:
                signals[opp_id]["weighted_score"] = item.get("weighted_score")
            if item.get("decision") is not None:
                signals[opp_id]["decision"] = item.get("decision")
            confidence = item.get("confidence", {})
            if isinstance(confidence, dict):
                signals[opp_id]["confidence_level"] = confidence.get("level")
    return signals


def as_icp(role: str = "", industry: str = "", company_size: str = "") -> str:
    bits = [normalize_text(role), normalize_text(industry), normalize_text(company_size)]
    return " / ".join([b for b in bits if b])


def normalize_faq(raw_faq: Any) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    if not isinstance(raw_faq, list):
        return out
    for item in raw_faq:
        if isinstance(item, dict):
            q = normalize_text(
                str(
                    item.get("question")
                    or item.get("objection")
                    or item.get("q")
                    or ""
                )
            )
            a = normalize_text(str(item.get("answer") or item.get("response") or item.get("a") or ""))
            if q or a:
                out.append({"question": q, "answer": a})
    return out


def normalize_proof_points(raw: Any, limit: int = 6) -> List[str]:
    out: List[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                text = normalize_text(item)
            elif isinstance(item, dict):
                text = normalize_text(str(item.get("claim") or item.get("text") or ""))
            else:
                text = ""
            if text:
                out.append(text)
    # stable unique
    uniq: List[str] = []
    seen = set()
    for item in out:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(item)
    return uniq[:limit]


def normalize_risks(raw: Any, limit: int = 10) -> List[str]:
    out: List[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                text = normalize_text(item)
            elif isinstance(item, dict):
                text = normalize_text(str(item.get("risk") or ""))
            else:
                text = ""
            if text:
                out.append(text)
    uniq: List[str] = []
    seen = set()
    for item in out:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(item)
    return uniq[:limit]


def normalize_kill_criteria(raw: Any, limit: int = 10) -> List[str]:
    out: List[str] = []
    if isinstance(raw, list):
        for item in raw:
            text = normalize_text(str(item))
            if text:
                out.append(text)
    uniq: List[str] = []
    seen = set()
    for item in out:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(item)
    return uniq[:limit]


def context_from_opportunities(path: Path, decision_signals: Dict[str, Dict[str, Any]], root: Path) -> List[Dict[str, Any]]:
    data = read_json(path, default={}) or {}
    contexts: List[Dict[str, Any]] = []
    for opp in data.get("opportunities", []):
        opp_id = opp.get("opportunity_id")
        segment = opp.get("target_segment", {})
        icp = as_icp(segment.get("role", ""), segment.get("industry", ""), segment.get("company_size", ""))
        proof = normalize_proof_points(opp.get("pain_evidence", []))
        risks = normalize_risks(opp.get("implementation_constraint", []))
        kill_criteria: List[str] = []
        hard_gate = opp.get("hard_gate_check", {}) if isinstance(opp.get("hard_gate_check"), dict) else {}
        if hard_gate and not hard_gate.get("pass", True):
            kill_criteria.append("hard_gate_failed")

        distribution = opp.get("distribution_entry", {}) if isinstance(opp.get("distribution_entry"), dict) else {}
        cta_label = normalize_text(distribution.get("first_20_targets_how", "")) or "Start discovery outreach"

        contexts.append(
            {
                "context_id": f"opportunity::{opp_id or safe_slug(opp.get('core_problem', 'opp'))}",
                "source_type": "opportunity_record",
                "source_files": [rel_from_root(root, path.resolve())],
                "source_opportunity_id": opp_id,
                "icp": icp,
                "problem_statement": normalize_text(opp.get("core_problem", "")),
                "value_proposition": normalize_text(opp.get("current_workaround", "")),
                "proof_points": proof,
                "faq": [],
                "cta": {
                    "label": cta_label,
                    "type": "research_outreach",
                    "support_text": normalize_text(distribution.get("channel", "")),
                },
                "risk_if_wrong": risks,
                "kill_criteria": kill_criteria,
                "priority_signals": decision_signals.get(opp_id, {}),
            }
        )
    return contexts


def context_from_project_specs(paths: List[Path], decision_signals: Dict[str, Dict[str, Any]], root: Path) -> List[Dict[str, Any]]:
    contexts: List[Dict[str, Any]] = []
    for path in paths:
        spec = read_json(path, default={}) or {}
        project_id = normalize_text(spec.get("project_id", "")) or safe_slug(path.stem)
        source = spec.get("source", {}) if isinstance(spec.get("source"), dict) else {}
        opp_id = source.get("opportunity_id")

        segment = spec.get("segment", {}) if isinstance(spec.get("segment"), dict) else {}
        icp = as_icp(segment.get("role", ""), segment.get("industry", ""), segment.get("company_size", ""))

        offer = spec.get("offer", {}) if isinstance(spec.get("offer"), dict) else {}
        cta = {
            "label": normalize_text(offer.get("cta_label", "")) or "Join pilot",
            "type": normalize_text(offer.get("cta_type", "")) or "email_waitlist",
            "support_text": normalize_text(spec.get("cta_support_text", "")),
        }

        metrics = spec.get("metrics", {}) if isinstance(spec.get("metrics"), dict) else {}
        kill_criteria = normalize_kill_criteria(metrics.get("kill_criteria", []))

        contexts.append(
            {
                "context_id": f"project_spec::{project_id}",
                "source_type": "project_spec",
                "source_files": [rel_from_root(root, path.resolve())],
                "source_opportunity_id": opp_id,
                "icp": icp,
                "problem_statement": normalize_text(spec.get("problem_statement", "")),
                "value_proposition": normalize_text(spec.get("value_proposition", "")),
                "proof_points": normalize_proof_points(spec.get("proof_points", [])),
                "faq": normalize_faq(spec.get("faq", [])),
                "cta": cta,
                "risk_if_wrong": normalize_risks(spec.get("operational_checklist", [])),
                "kill_criteria": kill_criteria,
                "priority_signals": decision_signals.get(opp_id, {}),
            }
        )
    return contexts


def context_from_project_blueprint(path: Path, root: Path) -> List[Dict[str, Any]]:
    data = read_json(path, default={}) or {}
    if not data:
        return []

    hypothesis = data.get("hypothesis", {}) if isinstance(data.get("hypothesis"), dict) else {}
    downstream_marketing = (
        data.get("downstream_inputs", {}).get("marketing", {})
        if isinstance(data.get("downstream_inputs", {}), dict)
        else {}
    )

    cta = {
        "label": normalize_text(downstream_marketing.get("cta", "")) or "Join pilot",
        "type": "pilot_signup",
        "support_text": normalize_text(downstream_marketing.get("headline_seed", "")),
    }

    return [
        {
            "context_id": f"blueprint::{normalize_text(data.get('project_id', 'project-blueprint'))}",
            "source_type": "project_blueprint",
            "source_files": [rel_from_root(root, path.resolve())],
            "source_opportunity_id": normalize_text(data.get("from_opportunity_id", "")) or None,
            "icp": normalize_text(hypothesis.get("for_segment", "")),
            "problem_statement": normalize_text(hypothesis.get("problem", "")),
            "value_proposition": normalize_text(hypothesis.get("value_proposition", "")),
            "proof_points": normalize_proof_points(data.get("mvp_boundary", {}).get("in_scope", [])),
            "faq": [],
            "cta": cta,
            "risk_if_wrong": normalize_risks(data.get("mvp_boundary", {}).get("out_of_scope", [])),
            "kill_criteria": normalize_kill_criteria(data.get("kill_criteria", [])),
            "priority_signals": {},
        }
    ]


def context_from_landing_package(path: Path, root: Path) -> List[Dict[str, Any]]:
    data = read_json(path, default={}) or {}
    if not data:
        return []

    positioning = data.get("landing_package", {}).get("positioning", {}) if isinstance(data.get("landing_package"), dict) else {}
    hierarchy = data.get("landing_package", {}).get("message_hierarchy", {}) if isinstance(data.get("landing_package"), dict) else {}
    cta_plan = data.get("landing_package", {}).get("cta_plan", {}) if isinstance(data.get("landing_package"), dict) else {}
    primary_cta = cta_plan.get("primary", {}) if isinstance(cta_plan, dict) else {}

    return [
        {
            "context_id": f"landing::{normalize_text(data.get('selected_opportunity', {}).get('opportunity_id', 'landing'))}",
            "source_type": "landing_package",
            "source_files": [rel_from_root(root, path.resolve())],
            "source_opportunity_id": normalize_text(data.get("selected_opportunity", {}).get("opportunity_id", "")) or None,
            "icp": normalize_text(positioning.get("icp", "")),
            "problem_statement": normalize_text(positioning.get("problem", "")),
            "value_proposition": normalize_text(positioning.get("value_proposition", "")),
            "proof_points": normalize_proof_points(hierarchy.get("primary_supporting_claims", [])),
            "faq": normalize_faq(hierarchy.get("objection_handlers", [])),
            "cta": {
                "label": normalize_text(primary_cta.get("label", "")) or "Join waitlist",
                "type": normalize_text(primary_cta.get("type", "")) or "email_waitlist",
                "support_text": normalize_text(primary_cta.get("support_text", "")),
            },
            "risk_if_wrong": normalize_risks(data.get("landing_package", {}).get("risk_register", [])),
            "kill_criteria": normalize_kill_criteria(
                [
                    r.get("risk")
                    for r in data.get("landing_package", {}).get("risk_register", [])
                    if isinstance(r, dict) and r.get("type") == "kill_criterion"
                ]
            ),
            "priority_signals": {},
        }
    ]


def context_from_handoff(path: Path, root: Path) -> List[Dict[str, Any]]:
    data = read_json(path, default={}) or {}
    if not data:
        return []

    problem = normalize_text(data.get("problem", ""))
    value_prop = normalize_text(data.get("positioning", {}).get("value_proposition", "")) if isinstance(data.get("positioning"), dict) else ""
    icp = normalize_text(data.get("icp", ""))

    if not (problem or value_prop or icp):
        return []

    return [
        {
            "context_id": f"handoff::{safe_slug(data.get('idea_name', 'marketing-handoff'))}",
            "source_type": "marketing_handoff",
            "source_files": [rel_from_root(root, path.resolve())],
            "source_opportunity_id": None,
            "icp": icp,
            "problem_statement": problem,
            "value_proposition": value_prop,
            "proof_points": normalize_proof_points(data.get("mvp_scope", [])),
            "faq": [],
            "cta": {
                "label": "Review handoff",
                "type": "internal",
                "support_text": normalize_text(data.get("landing_page_url_or_path", "")),
            },
            "risk_if_wrong": [],
            "kill_criteria": [],
            "priority_signals": {},
        }
    ]


def unique_contexts(contexts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for ctx in contexts:
        cid = normalize_text(ctx.get("context_id", ""))
        if not cid:
            continue

        existing = by_id.get(cid)
        if not existing:
            by_id[cid] = ctx
            continue

        existing_sources = set(existing.get("source_files", []))
        for src in ctx.get("source_files", []):
            if src not in existing_sources:
                existing.setdefault("source_files", []).append(src)
                existing_sources.add(src)

        for key in ["proof_points", "risk_if_wrong", "kill_criteria"]:
            merged = []
            seen = set()
            for item in existing.get(key, []) + ctx.get(key, []):
                norm = normalize_text(str(item))
                if not norm:
                    continue
                low = norm.lower()
                if low in seen:
                    continue
                seen.add(low)
                merged.append(norm)
            existing[key] = merged

        if not existing.get("value_proposition") and ctx.get("value_proposition"):
            existing["value_proposition"] = ctx["value_proposition"]
        if not existing.get("problem_statement") and ctx.get("problem_statement"):
            existing["problem_statement"] = ctx["problem_statement"]
        if not existing.get("icp") and ctx.get("icp"):
            existing["icp"] = ctx["icp"]

    final = list(by_id.values())
    final.sort(key=lambda x: x.get("context_id", ""))
    return final


def build_context_index(root: Path, req_files: Dict[str, List[Path]]) -> Dict[str, Any]:
    decision_signals = parse_decision_signals(req_files.get("stage2_decision_log", []))

    all_contexts: List[Dict[str, Any]] = []

    for p in req_files.get("stage1_opportunity_records", []):
        all_contexts.extend(context_from_opportunities(p, decision_signals, root))

    all_contexts.extend(context_from_project_specs(req_files.get("project_specs", []), decision_signals, root))

    for p in req_files.get("stage3_project_blueprint", []):
        all_contexts.extend(context_from_project_blueprint(p, root))

    for p in req_files.get("landing_package", []):
        all_contexts.extend(context_from_landing_package(p, root))

    for p in req_files.get("product_to_marketing_handoff", []):
        all_contexts.extend(context_from_handoff(p, root))

    contexts = []
    for ctx in unique_contexts(all_contexts):
        if not (ctx.get("problem_statement") or ctx.get("value_proposition") or ctx.get("proof_points")):
            continue
        cta = ctx.get("cta", {}) if isinstance(ctx.get("cta"), dict) else {}
        ctx["cta"] = {
            "label": normalize_text(cta.get("label", "")) or "Join waitlist",
            "type": normalize_text(cta.get("type", "")) or "email_waitlist",
            "support_text": normalize_text(cta.get("support_text", "")),
        }
        ctx["proof_points"] = normalize_proof_points(ctx.get("proof_points", []))
        ctx["faq"] = normalize_faq(ctx.get("faq", []))
        ctx["risk_if_wrong"] = normalize_risks(ctx.get("risk_if_wrong", []))
        ctx["kill_criteria"] = normalize_kill_criteria(ctx.get("kill_criteria", []))
        contexts.append(ctx)

    return {
        "generated_at": now_iso(),
        "context_count": len(contexts),
        "contexts": contexts,
    }


def infer_intent(keyword: str) -> str:
    k = keyword.lower()
    if any(x in k for x in ["best", "software", "tool", "pricing", "vs", "alternative"]):
        return "BOFU"
    if any(x in k for x in ["template", "checklist", "workflow", "process", "playbook"]):
        return "MOFU"
    return "TOFU"


def generate_keywords_for_context(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    context_id = context.get("context_id", "")
    opp_id = context.get("source_opportunity_id")

    problem_phrase = compact_phrase(context.get("problem_statement", ""), max_words=6)
    value_phrase = compact_phrase(context.get("value_proposition", ""), max_words=6)
    icp_phrase = compact_phrase(context.get("icp", ""), max_words=4)
    proof_seed = " ".join(tokenize(" ".join(context.get("proof_points", [])[:2]))[:4])

    topic = problem_phrase or value_phrase or proof_seed or "workflow automation"
    topic_short = " ".join(topic.split()[:3])

    comparison_phrase = f"{topic_short} vs automated workflow" if "manual" in topic_short else f"{topic_short} vs manual"

    templates = [
        f"how to {topic}",
        f"{topic} checklist",
        f"{topic} template",
        f"{topic} workflow",
        f"{topic_short} process",
        f"{topic_short} automation",
        comparison_phrase,
        f"best {topic_short} software",
        f"{topic_short} tool for {icp_phrase}" if icp_phrase else f"{topic_short} tool",
        f"{topic_short} pricing",
        f"{topic_short} playbook",
        f"{topic_short} examples",
    ]

    if value_phrase:
        templates.append(f"how to {value_phrase}")
        templates.append(f"{value_phrase} template")
    if proof_seed:
        templates.append(f"{proof_seed} checklist")

    rows: List[Dict[str, Any]] = []
    seen = set()

    weighted_score = context.get("priority_signals", {}).get("weighted_score")
    priority_hint = float(weighted_score) if isinstance(weighted_score, (int, float)) else 0.0

    for raw in templates:
        keyword = normalize_text(raw.lower())
        if not keyword:
            continue
        keyword = re.sub(r"\s+", " ", keyword)
        if keyword in seen:
            continue
        seen.add(keyword)

        intent = infer_intent(keyword)
        rows.append(
            {
                "keyword": keyword,
                "intent": intent,
                "context_id": context_id,
                "source_opportunity_id": opp_id,
                "priority_hint": round(priority_hint, 4),
            }
        )

    return rows


def write_keyword_graph_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["keyword", "intent", "context_id", "source_opportunity_id", "priority_hint"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def synthesize_experiments(contexts: List[Dict[str, Any]], keyword_rows: List[Dict[str, Any]], generated_at: str) -> List[Dict[str, Any]]:
    ctx_map = {c["context_id"]: c for c in contexts}
    kw_by_ctx: Dict[str, List[Dict[str, Any]]] = {}
    for row in keyword_rows:
        kw_by_ctx.setdefault(row["context_id"], []).append(row)

    experiments: List[Dict[str, Any]] = []
    for context_id, ctx_keywords in kw_by_ctx.items():
        ctx = ctx_map.get(context_id)
        if not ctx:
            continue

        sorted_keywords = sorted(
            ctx_keywords,
            key=lambda x: (
                -INTENT_PRIORITY.get(x.get("intent", "TOFU"), 1),
                -float(x.get("priority_hint", 0.0)),
                x.get("keyword", ""),
            ),
        )

        cta_label = (ctx.get("cta", {}) or {}).get("label", "Join waitlist")
        proof_seed = ctx.get("proof_points", [""])[0] if ctx.get("proof_points") else "Use one concrete proof point above the fold."

        for idx, row in enumerate(sorted_keywords[:6], start=1):
            keyword = row.get("keyword", "")
            intent = row.get("intent", "TOFU")
            exp_id = f"exp_{safe_slug(context_id, 40)}_{idx:02d}"

            experiments.append(
                {
                    "experiment_id": exp_id,
                    "context_id": context_id,
                    "source_opportunity_id": ctx.get("source_opportunity_id"),
                    "keyword": keyword,
                    "intent": intent,
                    "status": "drafted",
                    "hypothesis": f"If we position around '{keyword}' with explicit proof and a single CTA, qualified intent quality will improve.",
                    "change": {
                        "headline_variant_a": keyword.title(),
                        "headline_variant_b": f"{keyword.title()} without extra manual overhead",
                        "proof_variant": proof_seed,
                        "cta_variant_a": cta_label,
                        "cta_variant_b": f"Start with {keyword.split(' ')[0]} pilot",
                    },
                    "primary_metric": "shadow_overall_score",
                    "guardrail_metrics": [
                        "problem_message_fit",
                        "execution_risk_penalty",
                    ],
                    "success_rule": "overall_score >= 72 and execution_risk_penalty <= 65",
                    "stop_rule": "overall_score < 55 for two consecutive runs",
                    "source_pointers": list(ctx.get("source_files", [])),
                    "generated_at": generated_at,
                }
            )

    experiments.sort(key=lambda x: x["experiment_id"])
    return experiments


def score_experiment(experiment: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    keyword = experiment.get("keyword", "")
    intent = experiment.get("intent", "TOFU")

    keyword_tokens = set(tokenize(keyword))
    context_tokens = set(
        tokenize(context.get("problem_statement", ""))
        + tokenize(context.get("value_proposition", ""))
        + tokenize(" ".join(context.get("proof_points", [])))
    )

    overlap = len(keyword_tokens & context_tokens)
    overlap_ratio = overlap / max(1, len(keyword_tokens))

    intent_match = 45 + overlap_ratio * 50
    if intent == "BOFU" and any(x in keyword for x in ["software", "tool", "pricing", "vs", "best"]):
        intent_match += 5

    problem_statement = context.get("problem_statement", "")
    value_prop = context.get("value_proposition", "")
    problem_value_tokens = set(tokenize(problem_statement + " " + value_prop))
    fit_overlap = len(keyword_tokens & problem_value_tokens) / max(1, len(keyword_tokens))
    problem_message_fit = 40 + fit_overlap * 55

    proof_count = len(context.get("proof_points", []))
    proof_tokens = len(set(tokenize(" ".join(context.get("proof_points", [])))))
    differentiation = 35 + min(35, proof_tokens * 1.5) + (10 if proof_count >= 2 else 0)

    cta = context.get("cta", {}) if isinstance(context.get("cta"), dict) else {}
    faq_count = len(context.get("faq", []))
    conversion_readiness = 30
    if cta.get("label"):
        conversion_readiness += 25
    if faq_count >= 1:
        conversion_readiness += 10
    if proof_count >= 2:
        conversion_readiness += 10
    if intent in {"MOFU", "BOFU"}:
        conversion_readiness += 10

    risk_count = len(context.get("risk_if_wrong", []))
    kill_count = len(context.get("kill_criteria", []))
    execution_risk_penalty = 15 + risk_count * 7 + (0 if kill_count > 0 else 8)

    intent_match = clamp(intent_match)
    problem_message_fit = clamp(problem_message_fit)
    differentiation = clamp(differentiation)
    conversion_readiness = clamp(conversion_readiness)
    execution_risk_penalty = clamp(execution_risk_penalty)

    overall = (
        intent_match * 0.25
        + problem_message_fit * 0.25
        + differentiation * 0.2
        + conversion_readiness * 0.2
        + (100.0 - execution_risk_penalty) * 0.1
    )
    overall = clamp(overall)

    confidence = "low"
    if proof_count >= 3 and faq_count >= 1:
        confidence = "high"
    elif proof_count >= 1:
        confidence = "medium"

    decision = "drop"
    reason = "low_shadow_score"
    if overall >= 75 and execution_risk_penalty <= 70:
        decision = "ready"
        reason = "score_and_risk_pass"
    elif overall >= 58:
        decision = "hold"
        reason = "needs_iteration"

    lifecycle_status = "scored"
    if decision == "ready":
        lifecycle_status = "shadow_validated" if overall >= 82 else "ready"
    elif decision == "drop":
        lifecycle_status = "dropped"

    return {
        "experiment_id": experiment.get("experiment_id"),
        "context_id": experiment.get("context_id"),
        "keyword": keyword,
        "intent": intent,
        "scores": {
            "intent_match": round(intent_match, 2),
            "problem_message_fit": round(problem_message_fit, 2),
            "differentiation": round(differentiation, 2),
            "conversion_readiness": round(conversion_readiness, 2),
            "execution_risk_penalty": round(execution_risk_penalty, 2),
        },
        "overall_score": round(overall, 2),
        "confidence": confidence,
        "decision": decision,
        "decision_reason": reason,
        "lifecycle_status": lifecycle_status,
    }


def build_queue(score_entries: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    queue = {"ready": [], "hold": [], "drop": []}
    for entry in score_entries:
        item = {
            "experiment_id": entry.get("experiment_id"),
            "context_id": entry.get("context_id"),
            "keyword": entry.get("keyword"),
            "intent": entry.get("intent"),
            "overall_score": entry.get("overall_score"),
            "confidence": entry.get("confidence"),
            "lifecycle_status": entry.get("lifecycle_status"),
            "decision_reason": entry.get("decision_reason"),
        }
        decision = entry.get("decision", "drop")
        queue.setdefault(decision, []).append(item)

    for key in queue:
        queue[key] = sorted(queue[key], key=lambda x: (-float(x.get("overall_score", 0.0)), x.get("experiment_id", "")))
    return queue


def write_briefs(
    briefs_dir: Path,
    queue: Dict[str, List[Dict[str, Any]]],
    experiments_by_id: Dict[str, Dict[str, Any]],
    contexts_by_id: Dict[str, Dict[str, Any]],
    generated_at: str,
) -> int:
    if briefs_dir.exists():
        shutil.rmtree(briefs_dir)
    briefs_dir.mkdir(parents=True, exist_ok=True)

    selected = list(queue.get("ready", []))[:12]
    if not selected:
        selected = list(queue.get("hold", []))[:6]

    count = 0
    for item in selected:
        exp = experiments_by_id.get(item.get("experiment_id", ""), {})
        ctx = contexts_by_id.get(item.get("context_id", ""), {})
        cta = (ctx.get("cta") or {}).get("label", "Join waitlist")

        lines = [
            f"# SEO Experiment Brief — {item.get('experiment_id')}",
            "",
            f"- Generated at: {generated_at}",
            f"- Context: `{item.get('context_id')}`",
            f"- Keyword: **{item.get('keyword', '')}** ({item.get('intent', 'TOFU')})",
            f"- Current shadow score: **{item.get('overall_score', 0)}**",
            "",
            "## Hypothesis",
            exp.get("hypothesis", ""),
            "",
            "## Suggested page shape",
            f"- H1 A: {exp.get('change', {}).get('headline_variant_a', '')}",
            f"- H1 B: {exp.get('change', {}).get('headline_variant_b', '')}",
            f"- Proof block: {exp.get('change', {}).get('proof_variant', '')}",
            f"- CTA A: {exp.get('change', {}).get('cta_variant_a', cta)}",
            f"- CTA B: {exp.get('change', {}).get('cta_variant_b', cta)}",
            "",
            "## Context summary",
            f"- ICP: {ctx.get('icp', '')}",
            f"- Problem: {ctx.get('problem_statement', '')}",
            f"- Value proposition: {ctx.get('value_proposition', '')}",
            "",
            "## Guardrails",
            f"- Success rule: {exp.get('success_rule', '')}",
            f"- Stop rule: {exp.get('stop_rule', '')}",
            "",
            "## Source pointers",
        ]

        for source_file in ctx.get("source_files", []):
            lines.append(f"- `{source_file}`")

        out_path = briefs_dir / f"{item.get('experiment_id')}.md"
        out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        count += 1

    return count


def write_decision_log(
    path: Path,
    run_id: str,
    snapshot_id: str,
    context_count: int,
    keyword_count: int,
    queue: Dict[str, List[Dict[str, Any]]],
    generated_at: str,
) -> None:
    ready = queue.get("ready", [])
    hold = queue.get("hold", [])
    drop = queue.get("drop", [])

    lines = [
        f"# Stage1 Marketing SEO Decision Log — {run_id}",
        "",
        f"- Generated at: {generated_at}",
        f"- Input snapshot: `{snapshot_id}`",
        f"- Contexts: **{context_count}**",
        f"- Keywords: **{keyword_count}**",
        f"- Queue split: Ready **{len(ready)}** / Hold **{len(hold)}** / Drop **{len(drop)}**",
        "",
        "## Top Ready",
    ]

    if ready:
        for item in ready[:10]:
            lines.append(
                f"- `{item['experiment_id']}` | {item['keyword']} | score={item['overall_score']} | confidence={item['confidence']}"
            )
    else:
        lines.append("- (none)")

    lines.extend(["", "## Hold (needs iteration)"])
    if hold:
        for item in hold[:10]:
            lines.append(
                f"- `{item['experiment_id']}` | {item['keyword']} | score={item['overall_score']} | reason={item['decision_reason']}"
            )
    else:
        lines.append("- (none)")

    lines.extend(["", "## Drop"])
    if drop:
        for item in drop[:10]:
            lines.append(f"- `{item['experiment_id']}` | {item['keyword']} | score={item['overall_score']}")
    else:
        lines.append("- (none)")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def required_outputs_exist(stage_dir: Path) -> bool:
    needed = [
        stage_dir / "context_index.latest.json",
        stage_dir / "keyword_graph.latest.csv",
        stage_dir / "experiments.backlog.latest.json",
        stage_dir / "experiments.queue.latest.json",
        stage_dir / "scoreboard.latest.json",
        stage_dir / "decision_log.latest.md",
    ]
    return all(p.exists() for p in needed)


def write_blocked_outputs(stage_dir: Path, reason: str, generated_at: str) -> None:
    write_json(
        stage_dir / "context_index.latest.json",
        {
            "generated_at": generated_at,
            "status": "blocked",
            "reason": reason,
            "context_count": 0,
            "contexts": [],
        },
    )

    write_keyword_graph_csv(stage_dir / "keyword_graph.latest.csv", rows=[])

    write_json(
        stage_dir / "experiments.backlog.latest.json",
        {
            "generated_at": generated_at,
            "status": "blocked",
            "reason": reason,
            "experiment_count": 0,
            "experiments": [],
        },
    )

    write_json(
        stage_dir / "experiments.queue.latest.json",
        {
            "generated_at": generated_at,
            "status": "blocked",
            "reason": reason,
            "queue": {"ready": [], "hold": [], "drop": []},
            "counts": {"ready": 0, "hold": 0, "drop": 0},
        },
    )

    write_json(
        stage_dir / "scoreboard.latest.json",
        {
            "generated_at": generated_at,
            "status": "blocked",
            "reason": reason,
            "summary": {"experiment_count": 0},
            "experiments": [],
        },
    )

    (stage_dir / "briefs").mkdir(parents=True, exist_ok=True)
    (stage_dir / "decision_log.latest.md").write_text(
        f"# Stage1 Marketing SEO Decision Log\n\n- Generated at: {generated_at}\n- Status: blocked\n- Reason: {reason}\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage1 marketing SEO continuous-shadow pipeline")
    parser.add_argument("--root-dir", default=None, help="Workspace root (defaults to script ../)")
    parser.add_argument("--stage-dir", default=None, help="Stage output dir")
    parser.add_argument("--mode", default="shadow", choices=["shadow", "live"], help="Execution mode")
    parser.add_argument("--publish", action="store_true", help="Enable publish flag (stage2+)" )
    parser.add_argument("--index", action="store_true", help="Enable index flag (stage2+)" )
    parser.add_argument("--force", action="store_true", help="Force recompute even if no input delta")
    parser.add_argument("--print-summary", action="store_true", help="Print JSON summary to stdout")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    script_dir = Path(__file__).resolve().parent
    root = Path(args.root_dir).resolve() if args.root_dir else script_dir.parent.resolve()
    stage_dir = Path(args.stage_dir).resolve() if args.stage_dir else (root / "research/stage1_marketing_seo").resolve()

    input_dir = stage_dir / "input"
    snapshot_path = input_dir / "product_snapshot.latest.json"
    delta_path = input_dir / "delta.latest.json"
    mirror_dir = input_dir / "mirror.latest"

    run_path = stage_dir / "run.latest.json"
    state_path = stage_dir / "state.latest.json"

    generated_at = now_iso()
    run_id = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    previous_snapshot = read_json(snapshot_path, default={}) or {}
    previous_state = read_json(state_path, default={}) or {}

    summary: Dict[str, Any] = {
        "generated_at": generated_at,
        "run_id": run_id,
        "stage_dir": str(stage_dir),
    }

    try:
        req_status, file_records, completeness = resolve_input_files(root)
        copy_mirror(root, mirror_dir, file_records)

        snapshot = build_snapshot(root, req_status, file_records, completeness, generated_at)
        write_json(snapshot_path, snapshot)

        delta = build_delta(previous_snapshot, snapshot, generated_at)
        write_json(delta_path, delta)

        delta_counts = {
            "added": len(delta.get("added", [])),
            "changed": len(delta.get("changed", [])),
            "removed": len(delta.get("removed", [])),
        }
        has_delta = any(delta_counts.values())

        run_scope = "full_rebuild" if not previous_snapshot.get("snapshot_id") else "incremental"
        should_recompute = args.force or has_delta or not required_outputs_exist(stage_dir)

        base_run_payload = {
            "generated_at": generated_at,
            "run_id": run_id,
            "capability": "marketing_seo_stage1_continuous_shadow_v1",
            "status": "running",
            "mode": args.mode,
            "continuous": True,
            "publish": bool(args.publish),
            "index": bool(args.index),
            "run_scope": run_scope,
            "input_sync": {
                "snapshot_id": snapshot.get("snapshot_id"),
                "completeness": completeness,
                "delta_counts": delta_counts,
                "requirements": req_status,
            },
        }

        # Gate: full input completeness required.
        if completeness.get("ratio", 0.0) < 1.0:
            reason = "blocked_input_incomplete"
            write_blocked_outputs(stage_dir, reason=reason, generated_at=generated_at)

            run_payload = dict(base_run_payload)
            run_payload.update(
                {
                    "status": reason,
                    "outputs": {
                        "context_index": str(stage_dir / "context_index.latest.json"),
                        "keyword_graph": str(stage_dir / "keyword_graph.latest.csv"),
                        "backlog": str(stage_dir / "experiments.backlog.latest.json"),
                        "queue": str(stage_dir / "experiments.queue.latest.json"),
                        "scoreboard": str(stage_dir / "scoreboard.latest.json"),
                        "decision_log": str(stage_dir / "decision_log.latest.md"),
                    },
                }
            )
            write_json(run_path, run_payload)

            full_rebuild_at = previous_state.get("last_full_rebuild_at")
            if run_scope == "full_rebuild":
                full_rebuild_at = generated_at

            state_payload = {
                "loop_state": reason,
                "active_contexts": 0,
                "backlog_size": 0,
                "queue_size": 0,
                "last_full_rebuild_at": full_rebuild_at,
                "last_incremental_run_at": generated_at if run_scope == "incremental" else previous_state.get("last_incremental_run_at"),
                "mode": args.mode,
                "publish": bool(args.publish),
                "index": bool(args.index),
                "continuous": True,
                "input_completeness": completeness,
                "snapshot_id": snapshot.get("snapshot_id"),
                "delta_counts": delta_counts,
                "last_run_status": reason,
            }
            write_json(state_path, state_payload)

            summary.update({"status": reason, "reason": reason})
            if args.print_summary:
                print(json.dumps(summary, ensure_ascii=False))
            return 0

        if not should_recompute:
            run_payload = dict(base_run_payload)
            run_payload.update(
                {
                    "status": "no_change",
                    "note": "Input snapshot unchanged; recompute skipped.",
                }
            )
            write_json(run_path, run_payload)

            state_payload = {
                "loop_state": "idle_no_change",
                "active_contexts": int(previous_state.get("active_contexts", 0)),
                "backlog_size": int(previous_state.get("backlog_size", 0)),
                "queue_size": int(previous_state.get("queue_size", 0)),
                "last_full_rebuild_at": previous_state.get("last_full_rebuild_at"),
                "last_incremental_run_at": generated_at,
                "mode": args.mode,
                "publish": bool(args.publish),
                "index": bool(args.index),
                "continuous": True,
                "input_completeness": completeness,
                "snapshot_id": snapshot.get("snapshot_id"),
                "delta_counts": delta_counts,
                "last_run_status": "no_change",
            }
            write_json(state_path, state_payload)

            summary.update({"status": "no_change"})
            if args.print_summary:
                print(json.dumps(summary, ensure_ascii=False))
            return 0

        req_files = map_requirement_files(file_records)

        context_index = build_context_index(root, req_files)
        context_index["snapshot_id"] = snapshot.get("snapshot_id")
        context_index["delta_counts"] = delta_counts
        write_json(stage_dir / "context_index.latest.json", context_index)

        contexts = context_index.get("contexts", [])

        keyword_rows: List[Dict[str, Any]] = []
        for ctx in contexts:
            keyword_rows.extend(generate_keywords_for_context(ctx))

        # unique keyword rows
        unique_rows = []
        seen_rows = set()
        for row in keyword_rows:
            key = (row.get("keyword"), row.get("intent"), row.get("context_id"))
            if key in seen_rows:
                continue
            seen_rows.add(key)
            unique_rows.append(row)

        unique_rows.sort(key=lambda x: (x.get("context_id", ""), -INTENT_PRIORITY.get(x.get("intent", "TOFU"), 1), x.get("keyword", "")))
        write_keyword_graph_csv(stage_dir / "keyword_graph.latest.csv", unique_rows)

        experiments = synthesize_experiments(contexts, unique_rows, generated_at)
        experiments_by_id = {e["experiment_id"]: e for e in experiments}
        contexts_by_id = {c["context_id"]: c for c in contexts}

        score_entries: List[Dict[str, Any]] = []
        for exp in experiments:
            ctx = contexts_by_id.get(exp.get("context_id"), {})
            score_entries.append(score_experiment(exp, ctx))

        score_entries.sort(key=lambda x: (-float(x.get("overall_score", 0.0)), x.get("experiment_id", "")))
        scores_by_id = {s["experiment_id"]: s for s in score_entries}

        for exp in experiments:
            score = scores_by_id.get(exp["experiment_id"], {})
            exp["status"] = score.get("lifecycle_status", "scored")
            exp["decision"] = score.get("decision")
            exp["overall_score"] = score.get("overall_score")
            exp["confidence"] = score.get("confidence")

        backlog_payload = {
            "generated_at": generated_at,
            "status": "ok",
            "snapshot_id": snapshot.get("snapshot_id"),
            "experiment_count": len(experiments),
            "experiments": experiments,
        }
        write_json(stage_dir / "experiments.backlog.latest.json", backlog_payload)

        queue = build_queue(score_entries)
        queue_payload = {
            "generated_at": generated_at,
            "status": "ok",
            "snapshot_id": snapshot.get("snapshot_id"),
            "queue": queue,
            "counts": {k: len(v) for k, v in queue.items()},
        }
        write_json(stage_dir / "experiments.queue.latest.json", queue_payload)

        if score_entries:
            avg_overall = round(sum(x.get("overall_score", 0.0) for x in score_entries) / len(score_entries), 2)
        else:
            avg_overall = 0.0

        scoreboard_payload = {
            "generated_at": generated_at,
            "status": "ok",
            "scoring_version": "shadow_v1",
            "snapshot_id": snapshot.get("snapshot_id"),
            "summary": {
                "experiment_count": len(score_entries),
                "avg_overall_score": avg_overall,
                "ready_count": len(queue.get("ready", [])),
                "hold_count": len(queue.get("hold", [])),
                "drop_count": len(queue.get("drop", [])),
            },
            "experiments": score_entries,
        }
        write_json(stage_dir / "scoreboard.latest.json", scoreboard_payload)

        brief_count = write_briefs(
            stage_dir / "briefs",
            queue,
            experiments_by_id,
            contexts_by_id,
            generated_at,
        )

        write_decision_log(
            stage_dir / "decision_log.latest.md",
            run_id=run_id,
            snapshot_id=snapshot.get("snapshot_id", ""),
            context_count=len(contexts),
            keyword_count=len(unique_rows),
            queue=queue,
            generated_at=generated_at,
        )

        run_payload = dict(base_run_payload)
        run_payload.update(
            {
                "status": "passed",
                "outputs": {
                    "context_index": str(stage_dir / "context_index.latest.json"),
                    "keyword_graph": str(stage_dir / "keyword_graph.latest.csv"),
                    "backlog": str(stage_dir / "experiments.backlog.latest.json"),
                    "queue": str(stage_dir / "experiments.queue.latest.json"),
                    "scoreboard": str(stage_dir / "scoreboard.latest.json"),
                    "decision_log": str(stage_dir / "decision_log.latest.md"),
                    "briefs_dir": str(stage_dir / "briefs"),
                },
                "stats": {
                    "context_count": len(contexts),
                    "keyword_count": len(unique_rows),
                    "experiment_count": len(experiments),
                    "brief_count": brief_count,
                    "queue_counts": {k: len(v) for k, v in queue.items()},
                },
            }
        )
        write_json(run_path, run_payload)

        full_rebuild_at = previous_state.get("last_full_rebuild_at")
        if run_scope == "full_rebuild" or not full_rebuild_at:
            full_rebuild_at = generated_at

        state_payload = {
            "loop_state": "idle_ready",
            "active_contexts": len(contexts),
            "backlog_size": len(experiments),
            "queue_size": len(queue.get("ready", [])),
            "last_full_rebuild_at": full_rebuild_at,
            "last_incremental_run_at": generated_at,
            "mode": args.mode,
            "publish": bool(args.publish),
            "index": bool(args.index),
            "continuous": True,
            "input_completeness": completeness,
            "snapshot_id": snapshot.get("snapshot_id"),
            "delta_counts": delta_counts,
            "last_run_status": "passed",
        }
        write_json(state_path, state_payload)

        summary.update(
            {
                "status": "passed",
                "context_count": len(contexts),
                "keyword_count": len(unique_rows),
                "experiment_count": len(experiments),
                "ready_count": len(queue.get("ready", [])),
            }
        )

        if args.print_summary:
            print(json.dumps(summary, ensure_ascii=False))
        return 0

    except Exception as exc:
        fail_payload = {
            "generated_at": generated_at,
            "run_id": run_id,
            "capability": "marketing_seo_stage1_continuous_shadow_v1",
            "status": "failed",
            "mode": args.mode,
            "continuous": True,
            "publish": bool(args.publish),
            "index": bool(args.index),
            "error": str(exc),
        }
        write_json(run_path, fail_payload)

        state_payload = {
            "loop_state": "failed",
            "active_contexts": int(previous_state.get("active_contexts", 0)),
            "backlog_size": int(previous_state.get("backlog_size", 0)),
            "queue_size": int(previous_state.get("queue_size", 0)),
            "last_full_rebuild_at": previous_state.get("last_full_rebuild_at"),
            "last_incremental_run_at": generated_at,
            "mode": args.mode,
            "publish": bool(args.publish),
            "index": bool(args.index),
            "continuous": True,
            "last_run_status": "failed",
            "error": str(exc),
        }
        write_json(state_path, state_payload)

        if args.print_summary:
            print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        raise


if __name__ == "__main__":
    sys.exit(main())
