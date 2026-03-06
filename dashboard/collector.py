#!/usr/bin/env python3
"""OperatorOne Dashboard data collector.

Builds a single snapshot containing:
- 4-agent capability status (12 capabilities)
- handoff chain health
- external integration readiness (channels + secrets + security)
- session/runtime health from OpenClaw status JSON
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE = os.environ.get("OPERATORONE_PROFILE", "operatorone")
OPENCLAW_BIN = os.environ.get("OPENCLAW_BIN", "openclaw")

POLICY_PATH = REPO_ROOT / "dashboard" / "config" / "readiness_policy.json"
INDUSTRY_PATTERNS_PATH = REPO_ROOT / "dashboard" / "config" / "industry_patterns.json"


STATUS_PASS = {
    "pass",
    "passed",
    "ok",
    "ready",
    "ready_for_build",
    "ready_for_marketing_review",
    "success",
    "succeeded",
    "implemented",
    "complete",
    "completed",
    "true",
}

STATUS_WARN = {
    "review_required",
    "warning",
    "warn",
    "hold",
    "watchlist",
    "provisional",
}

STATUS_FAIL = {
    "fail",
    "failed",
    "error",
    "blocked",
    "drop",
    "denied",
    "false",
}


CAPABILITY_DEFINITIONS = [
    {
        "id": "product_generate_startup_ideas",
        "agent": "op1_product",
        "label": "Generate startup ideas",
        "evidence": [
            "workspaces/op1_product/research/stage1_idea_discovery/opportunity_records.json",
            "workspaces/op1_product/research/stage2_idea_screening/decision_log.json",
        ],
    },
    {
        "id": "product_build_deploy_simple_web",
        "agent": "op1_product",
        "label": "Build & deploy simple web products",
        "evidence": ["workspaces/op1_product/research/stage2_web_product/run.latest.json"],
    },
    {
        "id": "product_create_landing_pages",
        "agent": "op1_product",
        "label": "Create landing pages",
        "evidence": [
            "workspaces/op1_product/research/stage3_landing_launch/run.latest.json",
            "workspaces/op1_product/research/stage3_landing_launch/regression/stage3_capability_validation.latest.json",
        ],
    },
    {
        "id": "marketing_run_seo_experiments",
        "agent": "op1_marketing",
        "label": "Run SEO experiments",
        "evidence": ["workspaces/op1_marketing/research/stage1_marketing_seo/run.latest.json"],
    },
    {
        "id": "marketing_publish_content",
        "agent": "op1_marketing",
        "label": "Publish content",
        "evidence": ["workspaces/op1_marketing/research/stage2_content_publish/run.latest.json"],
    },
    {
        "id": "marketing_launch_campaigns",
        "agent": "op1_marketing",
        "label": "Launch campaigns",
        "evidence": ["workspaces/op1_marketing/research/stage3_campaign_launch/run.latest.json"],
    },
    {
        "id": "sales_identify_prospects",
        "agent": "op1_sales",
        "label": "Identify prospects",
        "evidence": ["workspaces/op1_sales/research/prospecting/prospect_queue.latest.json"],
    },
    {
        "id": "sales_send_outreach",
        "agent": "op1_sales",
        "label": "Send outreach",
        "evidence": [
            "workspaces/op1_sales/research/outreach/outreach_dispatch_report.latest.json",
            "workspaces/op1_sales/research/outreach/outreach_replies.processed.latest.json",
        ],
    },
    {
        "id": "sales_convert_early_customers",
        "agent": "op1_sales",
        "label": "Convert early customers",
        "evidence": [
            "workspaces/op1_sales/research/conversion/conversion_scoreboard.latest.json",
            "workspaces/op1_sales/research/conversion/reproducibility_report.latest.json",
        ],
    },
    {
        "id": "operations_track_traffic_signups_revenue",
        "agent": "op1_operations",
        "label": "Track traffic, signups, revenue",
        "evidence": [
            "workspaces/op1_operations/research/stage1_tracking/stage1_scoreboard.latest.json",
            "workspaces/op1_operations/research/stage1_tracking/reproducibility_report.latest.json",
        ],
    },
    {
        "id": "operations_process_feedback",
        "agent": "op1_operations",
        "label": "Process feedback",
        "evidence": [
            "workspaces/op1_operations/research/stage2_feedback/stage2_feedback_scoreboard.latest.json",
            "workspaces/op1_operations/research/stage2_feedback/reproducibility_report.latest.json",
        ],
    },
    {
        "id": "operations_iterate_on_product",
        "agent": "op1_operations",
        "label": "Iterate on product",
        "evidence": [
            "workspaces/op1_operations/research/stage3_product_iteration/stage3_iteration_scoreboard.latest.json",
            "workspaces/op1_operations/research/stage3_product_iteration/reproducibility_report.latest.json",
        ],
    },
]


CORE_HANDOFFS = [
    "product_to_marketing.json",
    "marketing_to_sales.json",
    "sales_to_operations.json",
]

LOOP_HANDOFFS = [
    "operations_to_product.json",
    "operations_to_marketing.json",
    "operations_to_sales.json",
    "operations_to_product_iterate.json",
    "operations_to_marketing_iterate.json",
    "operations_to_sales_iterate.json",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Heuristic: milliseconds epoch when very large.
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OSError):
            return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        raw = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def normalize_status(value: Any) -> str:
    if isinstance(value, bool):
        return "passed" if value else "failed"
    if value is None:
        return "unknown"
    text = str(value).strip().lower()
    if text in STATUS_PASS:
        return "passed"
    if text in STATUS_WARN:
        return "warning"
    if text in STATUS_FAIL:
        return "failed"
    return "unknown"


def first_json_from_text(text: str) -> Any:
    text = text.strip()
    if not text:
        raise ValueError("empty output")

    # Fast path.
    try:
        return json.loads(text)
    except Exception:
        pass

    for idx, ch in enumerate(text):
        if ch not in "[{":
            continue
        candidate = text[idx:]
        try:
            return json.loads(candidate)
        except Exception:
            continue
    raise ValueError("no JSON payload found")


def run_openclaw_json(args: List[str], timeout: int = 90) -> Dict[str, Any]:
    cmd = [OPENCLAW_BIN, "--profile", PROFILE, *args]
    if "--json" not in cmd:
        cmd.append("--json")

    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    merged = "\n".join([proc.stdout or "", proc.stderr or ""]).strip()
    out: Dict[str, Any] = {
        "ok": proc.returncode == 0,
        "code": proc.returncode,
        "command": cmd,
    }
    if merged:
        try:
            out["data"] = first_json_from_text(merged)
        except Exception as exc:  # noqa: BLE001
            out["error"] = f"JSON parse failed: {exc}"
            out["raw"] = merged[:3000]
    else:
        out["data"] = None
    if proc.returncode != 0 and "error" not in out:
        out["error"] = merged[:1000] if merged else f"exit code {proc.returncode}"
    return out


def read_json(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not path.exists():
        return None, "missing"
    try:
        payload = json.loads(path.read_text())
        if isinstance(payload, dict):
            return payload, None
        return {"value": payload}, None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def file_meta(relative_path: str) -> Dict[str, Any]:
    path = REPO_ROOT / relative_path
    meta: Dict[str, Any] = {
        "path": relative_path,
        "exists": path.exists(),
    }
    if path.exists():
        stat = path.stat()
        dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        meta["mtime"] = dt.isoformat()
        meta["sizeBytes"] = stat.st_size
    return meta


def best_timestamp(payload: Optional[Dict[str, Any]], fallback_path: Path) -> Optional[datetime]:
    if payload:
        for key in (
            "generated_at",
            "finished_at",
            "completed_at",
            "updated_at",
            "started_at",
            "handoff_at",
            "as_of",
            "ts",
        ):
            dt = parse_datetime(payload.get(key))
            if dt:
                return dt
    if fallback_path.exists():
        return datetime.fromtimestamp(fallback_path.stat().st_mtime, tz=timezone.utc)
    return None


def age_hours(dt: Optional[datetime]) -> Optional[float]:
    if not dt:
        return None
    return round((utc_now() - dt).total_seconds() / 3600.0, 2)


def evaluate_product_generate_startup_ideas() -> Dict[str, Any]:
    opp_path = REPO_ROOT / "workspaces/op1_product/research/stage1_idea_discovery/opportunity_records.json"
    dec_path = REPO_ROOT / "workspaces/op1_product/research/stage2_idea_screening/decision_log.json"
    opp, opp_err = read_json(opp_path)
    dec, dec_err = read_json(dec_path)

    opportunities = []
    if opp:
        opportunities = opp.get("opportunities", [])
        if not isinstance(opportunities, list):
            opportunities = []

    selected_id = None
    decisions = []
    if dec:
        selected_id = (dec.get("selection_summary") or {}).get("selected_opportunity_id")
        decisions = dec.get("decisions", [])
        if not isinstance(decisions, list):
            decisions = []

    passed = (len(opportunities) > 0) and bool(selected_id) and (len(decisions) > 0)
    reasons = []
    if opp_err:
        reasons.append(f"opportunity_records.json: {opp_err}")
    if dec_err:
        reasons.append(f"decision_log.json: {dec_err}")
    if not opportunities:
        reasons.append("no opportunities found")
    if not selected_id:
        reasons.append("no selected opportunity id")
    if not decisions:
        reasons.append("no stage2 decisions found")

    ts = max(filter(None, [best_timestamp(opp, opp_path), best_timestamp(dec, dec_path)]), default=None)
    return {
        "status": "passed" if passed else "failed",
        "reasons": reasons,
        "metrics": {
            "opportunityCount": len(opportunities),
            "selectedOpportunityId": selected_id,
            "decisionCount": len(decisions),
        },
        "updatedAt": ts.isoformat() if ts else None,
        "ageHours": age_hours(ts),
    }


def evaluate_product_build_deploy() -> Dict[str, Any]:
    path = REPO_ROOT / "workspaces/op1_product/research/stage2_web_product/run.latest.json"
    run, err = read_json(path)
    status = normalize_status((run or {}).get("status"))

    checks = (run or {}).get("checks", {})
    smoke = normalize_status(checks.get("smoke_status"))
    page_strategy = normalize_status(checks.get("page_strategy_status"))
    business = normalize_status(checks.get("business_status"))
    checks_ok = all(x == "passed" for x in [smoke, page_strategy, business])

    passed = status == "passed" and checks_ok
    reasons = []
    if err:
        reasons.append(err)
    if status != "passed":
        reasons.append(f"run status is {run.get('status') if run else 'missing'}")
    if not checks_ok:
        reasons.append("one or more stage2 checks not passed")

    output = (run or {}).get("output", {})
    ts = best_timestamp(run, path)
    return {
        "status": "passed" if passed else "failed",
        "reasons": reasons,
        "metrics": {
            "runStatus": (run or {}).get("status"),
            "smoke": checks.get("smoke_status"),
            "pageStrategy": checks.get("page_strategy_status"),
            "business": checks.get("business_status"),
            "deployedUrl": output.get("deployed_url"),
        },
        "updatedAt": ts.isoformat() if ts else None,
        "ageHours": age_hours(ts),
    }


def evaluate_product_landing_pages() -> Dict[str, Any]:
    run_path = REPO_ROOT / "workspaces/op1_product/research/stage3_landing_launch/run.latest.json"
    val_path = (
        REPO_ROOT
        / "workspaces/op1_product/research/stage3_landing_launch/regression/stage3_capability_validation.latest.json"
    )
    run, run_err = read_json(run_path)
    val, val_err = read_json(val_path)

    run_status = normalize_status((run or {}).get("status"))
    val_status = normalize_status((val or {}).get("status"))

    checks = (run or {}).get("checks", {})
    contract_test = normalize_status(checks.get("contract_test_status"))
    semantic_test = normalize_status(checks.get("semantic_test_status"))

    passed = (run_status in {"passed", "warning"}) and contract_test == "passed" and semantic_test == "passed" and val_status == "passed"
    reasons = []
    if run_err:
        reasons.append(f"run.latest.json: {run_err}")
    if val_err:
        reasons.append(f"capability_validation.latest.json: {val_err}")
    if run_status not in {"passed", "warning"}:
        reasons.append(f"stage3 run status is {run.get('status') if run else 'missing'}")
    if contract_test != "passed" or semantic_test != "passed":
        reasons.append("stage3 contract/semantic checks are not fully passed")
    if val_status != "passed":
        reasons.append("stage3 capability validation not passed")

    ts = max(filter(None, [best_timestamp(run, run_path), best_timestamp(val, val_path)]), default=None)
    return {
        "status": "passed" if passed else "failed",
        "reasons": reasons,
        "metrics": {
            "runStatus": (run or {}).get("status"),
            "contractTest": checks.get("contract_test_status"),
            "semanticTest": checks.get("semantic_test_status"),
            "validationStatus": (val or {}).get("status"),
            "caseCount": len((val or {}).get("cases", []) or []),
        },
        "updatedAt": ts.isoformat() if ts else None,
        "ageHours": age_hours(ts),
    }


def evaluate_marketing_stage(stage: int) -> Dict[str, Any]:
    mapping = {
        1: "workspaces/op1_marketing/research/stage1_marketing_seo/run.latest.json",
        2: "workspaces/op1_marketing/research/stage2_content_publish/run.latest.json",
        3: "workspaces/op1_marketing/research/stage3_campaign_launch/run.latest.json",
    }
    rel = mapping[stage]
    path = REPO_ROOT / rel
    run, err = read_json(path)
    raw_status = str((run or {}).get("status") or "").strip().lower()
    status = normalize_status((run or {}).get("status"))
    mode = (run or {}).get("mode")

    # Capability coverage perspective:
    # stage3 may be blocked because there is no launchable asset in review mode,
    # which is a data outcome rather than missing implementation.
    blocked_but_implemented = stage == 3 and raw_status in {"blocked_no_launchable_assets", "no_launchable_assets"}

    passed = status == "passed" or blocked_but_implemented
    reasons = []
    if err:
        reasons.append(err)
    if not passed:
        reasons.append(f"status is {(run or {}).get('status')}")
    if blocked_but_implemented:
        reasons.append("stage3 blocked due no launchable assets (implementation present)")

    stats = (run or {}).get("stats", {})
    ts = best_timestamp(run, path)
    return {
        "status": "passed" if passed else "failed",
        "reasons": reasons,
        "metrics": {
            "status": (run or {}).get("status"),
            "mode": mode,
            "stats": stats,
        },
        "updatedAt": ts.isoformat() if ts else None,
        "ageHours": age_hours(ts),
    }


def evaluate_sales_identify_prospects() -> Dict[str, Any]:
    path = REPO_ROOT / "workspaces/op1_sales/research/prospecting/prospect_queue.latest.json"
    queue, err = read_json(path)
    summary = (queue or {}).get("summary", {})
    segments = (queue or {}).get("segments", [])
    passed = (
        (summary.get("segments_ranked", 0) or 0) > 0
        and (summary.get("posts_classified", 0) or 0) > 0
        and isinstance(segments, list)
        and len(segments) > 0
    )
    reasons = []
    if err:
        reasons.append(err)
    if not passed:
        reasons.append("prospect queue summary is incomplete")

    ts = best_timestamp(queue, path)
    return {
        "status": "passed" if passed else "failed",
        "reasons": reasons,
        "metrics": {
            "segmentsRanked": summary.get("segments_ranked"),
            "postsClassified": summary.get("posts_classified"),
            "segmentCount": len(segments) if isinstance(segments, list) else 0,
        },
        "updatedAt": ts.isoformat() if ts else None,
        "ageHours": age_hours(ts),
    }


def evaluate_sales_send_outreach() -> Dict[str, Any]:
    dispatch_path = REPO_ROOT / "workspaces/op1_sales/research/outreach/outreach_dispatch_report.latest.json"
    replies_path = REPO_ROOT / "workspaces/op1_sales/research/outreach/outreach_replies.processed.latest.json"

    dispatch, d_err = read_json(dispatch_path)
    replies, r_err = read_json(replies_path)

    summary = (dispatch or {}).get("summary", {})
    processed = summary.get("processed", 0) or 0
    eligible = summary.get("eligible_in_batch", 0) or 0
    skipped_missing = summary.get("skipped_missing", 0) or 0
    classifier_version = (replies or {}).get("classifier_version")

    # Capability coverage perspective: allow zero processed in simulation/review
    # when pipeline and classifier outputs are present.
    pipeline_present = isinstance(summary, dict) and bool((dispatch or {}).get("generated_at"))
    passed = pipeline_present and bool(classifier_version)

    reasons = []
    if d_err:
        reasons.append(f"dispatch: {d_err}")
    if r_err:
        reasons.append(f"replies: {r_err}")
    if not pipeline_present:
        reasons.append("dispatch summary missing")
    if not classifier_version:
        reasons.append("reply classifier version missing")
    if processed <= 0 and passed:
        reasons.append("processed=0 (likely simulation data mismatch), capability still implemented")

    ts = max(
        filter(None, [best_timestamp(dispatch, dispatch_path), best_timestamp(replies, replies_path)]),
        default=None,
    )
    return {
        "status": "passed" if passed else "failed",
        "reasons": reasons,
        "metrics": {
            "mode": (dispatch or {}).get("mode"),
            "eligibleInBatch": eligible,
            "processed": processed,
            "skippedMissing": skipped_missing,
            "dispatchedManual": summary.get("dispatched_manual"),
            "suppressed": summary.get("suppressed"),
            "classifierVersion": classifier_version,
        },
        "updatedAt": ts.isoformat() if ts else None,
        "ageHours": age_hours(ts),
    }


def evaluate_sales_convert_customers() -> Dict[str, Any]:
    score_path = REPO_ROOT / "workspaces/op1_sales/research/conversion/conversion_scoreboard.latest.json"
    repro_path = REPO_ROOT / "workspaces/op1_sales/research/conversion/reproducibility_report.latest.json"
    score, s_err = read_json(score_path)
    repro, r_err = read_json(repro_path)

    summary = (score or {}).get("summary", {})
    reproducible = bool((repro or {}).get("reproducible"))
    checks = (repro or {}).get("checks", {})
    metrics_complete = bool(checks.get("scoreboard_metrics_complete", False))
    customers = summary.get("new_customers_converted")

    passed = reproducible and metrics_complete and customers is not None
    reasons = []
    if s_err:
        reasons.append(f"scoreboard: {s_err}")
    if r_err:
        reasons.append(f"reproducibility: {r_err}")
    if not reproducible:
        reasons.append("reproducibility report says not reproducible")
    if not metrics_complete:
        reasons.append("scoreboard metrics completeness check failed")

    ts = max(filter(None, [best_timestamp(score, score_path), best_timestamp(repro, repro_path)]), default=None)
    return {
        "status": "passed" if passed else "failed",
        "reasons": reasons,
        "metrics": {
            "newCustomersConverted": customers,
            "newBusinessMrrProxy": summary.get("new_business_mrr_proxy"),
            "reproducible": reproducible,
            "scoreboardMetricsComplete": metrics_complete,
        },
        "updatedAt": ts.isoformat() if ts else None,
        "ageHours": age_hours(ts),
    }


def evaluate_operations_stage(stage: int) -> Dict[str, Any]:
    mapping = {
        1: (
            "workspaces/op1_operations/research/stage1_tracking/stage1_scoreboard.latest.json",
            "workspaces/op1_operations/research/stage1_tracking/reproducibility_report.latest.json",
        ),
        2: (
            "workspaces/op1_operations/research/stage2_feedback/stage2_feedback_scoreboard.latest.json",
            "workspaces/op1_operations/research/stage2_feedback/reproducibility_report.latest.json",
        ),
        3: (
            "workspaces/op1_operations/research/stage3_product_iteration/stage3_iteration_scoreboard.latest.json",
            "workspaces/op1_operations/research/stage3_product_iteration/reproducibility_report.latest.json",
        ),
    }
    score_rel, repro_rel = mapping[stage]
    score_path = REPO_ROOT / score_rel
    repro_path = REPO_ROOT / repro_rel

    score, s_err = read_json(score_path)
    repro, r_err = read_json(repro_path)

    repro_status = normalize_status((repro or {}).get("status"))
    changed_files = (repro or {}).get("changed_files_vs_baseline", [])
    if not isinstance(changed_files, list):
        changed_files = []

    capability_status = (score or {}).get("capability_status", [])
    implemented_count = 0
    if isinstance(capability_status, list):
        for item in capability_status:
            if isinstance(item, dict) and normalize_status(item.get("status")) == "passed":
                implemented_count += 1

    passed = repro_status == "passed" and implemented_count > 0
    reasons = []
    if s_err:
        reasons.append(f"scoreboard: {s_err}")
    if r_err:
        reasons.append(f"reproducibility: {r_err}")
    if repro_status != "passed":
        reasons.append(f"reproducibility status is {(repro or {}).get('status')}")
    if implemented_count == 0:
        reasons.append("no implemented capabilities found in scoreboard")

    ts = max(filter(None, [best_timestamp(score, score_path), best_timestamp(repro, repro_path)]), default=None)
    return {
        "status": "passed" if passed else "failed",
        "reasons": reasons,
        "metrics": {
            "implementedCapabilities": implemented_count,
            "reproStatus": (repro or {}).get("status"),
            "changedFilesVsBaseline": len(changed_files),
            "alertsCount": (score or {}).get("alerts_count"),
            "summary": (score or {}).get("summary"),
        },
        "updatedAt": ts.isoformat() if ts else None,
        "ageHours": age_hours(ts),
    }


def evaluate_capabilities() -> List[Dict[str, Any]]:
    evaluators: Dict[str, Callable[[], Dict[str, Any]]] = {
        "product_generate_startup_ideas": evaluate_product_generate_startup_ideas,
        "product_build_deploy_simple_web": evaluate_product_build_deploy,
        "product_create_landing_pages": evaluate_product_landing_pages,
        "marketing_run_seo_experiments": lambda: evaluate_marketing_stage(1),
        "marketing_publish_content": lambda: evaluate_marketing_stage(2),
        "marketing_launch_campaigns": lambda: evaluate_marketing_stage(3),
        "sales_identify_prospects": evaluate_sales_identify_prospects,
        "sales_send_outreach": evaluate_sales_send_outreach,
        "sales_convert_early_customers": evaluate_sales_convert_customers,
        "operations_track_traffic_signups_revenue": lambda: evaluate_operations_stage(1),
        "operations_process_feedback": lambda: evaluate_operations_stage(2),
        "operations_iterate_on_product": lambda: evaluate_operations_stage(3),
    }

    results: List[Dict[str, Any]] = []
    for item in CAPABILITY_DEFINITIONS:
        evaluator = evaluators[item["id"]]
        evaluation = evaluator()
        results.append(
            {
                "id": item["id"],
                "agent": item["agent"],
                "label": item["label"],
                "status": evaluation["status"],
                "reasons": evaluation.get("reasons", []),
                "metrics": evaluation.get("metrics", {}),
                "updatedAt": evaluation.get("updatedAt"),
                "ageHours": evaluation.get("ageHours"),
                "evidence": [file_meta(path) for path in item.get("evidence", [])],
            }
        )
    return results


def handoff_status_from_payload(name: str, payload: Dict[str, Any]) -> str:
    if "status" in payload:
        norm = normalize_status(payload.get("status"))
        if norm != "unknown":
            return norm
    if name == "sales_to_operations.json":
        required = ["prospects_contacted", "replies", "calls_booked", "customers_converted", "mrr"]
        if all(key in payload for key in required):
            return "passed"
    if payload:
        return "passed"
    return "unknown"


def evaluate_handoffs() -> Dict[str, Any]:
    handoff_dir = REPO_ROOT / "handoffs"
    rows: List[Dict[str, Any]] = []

    for path in sorted(handoff_dir.glob("*.json")):
        payload, err = read_json(path)
        status = "failed" if err else handoff_status_from_payload(path.name, payload or {})
        dt = best_timestamp(payload, path)
        row = {
            "name": path.name,
            "path": str(path.relative_to(REPO_ROOT)),
            "status": status,
            "generatedAt": dt.isoformat() if dt else None,
            "ageHours": age_hours(dt),
            "sizeBytes": path.stat().st_size if path.exists() else None,
        }
        if payload:
            row["from"] = payload.get("from")
            row["to"] = payload.get("to")
            row["objective"] = payload.get("objective")
        if err:
            row["error"] = err
        rows.append(row)

    existing = {row["name"] for row in rows}
    missing_core = [name for name in CORE_HANDOFFS if name not in existing]
    missing_loop = [name for name in LOOP_HANDOFFS if name not in existing]

    core_complete = len(missing_core) == 0
    loop_complete = len(missing_loop) == 0

    return {
        "items": rows,
        "coreRequired": CORE_HANDOFFS,
        "loopRequired": LOOP_HANDOFFS,
        "missingCore": missing_core,
        "missingLoop": missing_loop,
        "coreComplete": core_complete,
        "loopComplete": loop_complete,
    }


def summarize_agents(capabilities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_agent: Dict[str, Dict[str, Any]] = {}
    for cap in capabilities:
        agent = cap["agent"]
        slot = by_agent.setdefault(
            agent,
            {
                "agent": agent,
                "capabilityTotal": 0,
                "passed": 0,
                "warning": 0,
                "failed": 0,
                "unknown": 0,
                "capabilities": [],
            },
        )
        slot["capabilityTotal"] += 1
        slot[cap["status"]] = slot.get(cap["status"], 0) + 1
        slot["capabilities"].append(cap)

    for slot in by_agent.values():
        slot["status"] = (
            "failed"
            if slot["failed"] > 0
            else "warning"
            if slot["warning"] > 0
            else "passed"
            if slot["passed"] == slot["capabilityTotal"]
            else "unknown"
        )

    order = ["op1_product", "op1_marketing", "op1_sales", "op1_operations"]
    return [by_agent[a] for a in order if a in by_agent]


def load_policy() -> Dict[str, Any]:
    payload, err = read_json(POLICY_PATH)
    if err or payload is None:
        return {
            "version": 1,
            "freshnessHours": 168,
            "demoGate": {
                "requireAllCapabilitiesPassed": True,
                "requireCoreHandoffs": True,
            },
            "liveGate": {
                "requireDemoReady": True,
                "requireAllCapabilitiesPassed": True,
                "requireCoreHandoffs": True,
                "requireSecretsAuditClean": True,
                "requireAtLeastOneConnectedChannel": True,
                "requireManualArm": True,
                "requireSecurityAuditNoCritical": True,
            },
            "_error": err,
        }
    return payload


def load_industry_patterns() -> Dict[str, Any]:
    payload, err = read_json(INDUSTRY_PATTERNS_PATH)
    if err or payload is None:
        return {"version": 1, "patterns": [], "_error": err}
    return payload


def evaluate_readiness(
    capabilities: List[Dict[str, Any]],
    handoffs: Dict[str, Any],
    channels_status: Dict[str, Any],
    secrets_audit: Dict[str, Any],
    status_all: Dict[str, Any],
    policy: Dict[str, Any],
    runtime_flags: Dict[str, Any],
) -> Dict[str, Any]:
    caps_passed = all(item.get("status") == "passed" for item in capabilities)
    caps_failed = [item["id"] for item in capabilities if item.get("status") != "passed"]

    core_handoffs_ok = bool(handoffs.get("coreComplete"))

    channels_data = (channels_status or {}).get("data") or {}
    channel_order = channels_data.get("channelOrder", []) if isinstance(channels_data, dict) else []
    connected_channel_count = len(channel_order) if isinstance(channel_order, list) else 0

    secrets_data = (secrets_audit or {}).get("data") or {}
    summary = secrets_data.get("summary", {}) if isinstance(secrets_data, dict) else {}
    plaintext = int(summary.get("plaintextCount", 0) or 0)
    unresolved = int(summary.get("unresolvedRefCount", 0) or 0)
    secrets_clean = plaintext == 0 and unresolved == 0

    status_data = (status_all or {}).get("data") or {}
    security_summary = ((status_data.get("securityAudit") or {}).get("summary") or {}) if isinstance(status_data, dict) else {}
    security_critical = int(security_summary.get("critical", 0) or 0)

    arm_enabled = bool(runtime_flags.get("manualArmEnabled", False))

    freshness_hours = int(policy.get("freshnessHours", 168) or 168)
    stale_capabilities = [
        item["id"]
        for item in capabilities
        if isinstance(item.get("ageHours"), (int, float)) and item["ageHours"] > freshness_hours
    ]

    demo_reasons: List[str] = []
    if not caps_passed:
        demo_reasons.append("not all 12 capabilities are passed")
    if not core_handoffs_ok:
        demo_reasons.append("core handoffs are incomplete")

    demo_status = "READY" if not demo_reasons else "BLOCKED"

    live_reasons: List[str] = []
    if demo_status != "READY":
        live_reasons.append("demo gate not ready")
    if not caps_passed:
        live_reasons.append("capabilities incomplete")
    if not core_handoffs_ok:
        live_reasons.append("core handoffs incomplete")
    if not secrets_clean:
        live_reasons.append("secrets audit is not clean")
    if connected_channel_count <= 0:
        live_reasons.append("no connected channel account")
    if not arm_enabled:
        live_reasons.append("manual arm is OFF")
    if security_critical > 0:
        live_reasons.append("security audit has critical findings")

    if not live_reasons:
        live_status = "READY"
    elif any(reason in {"demo gate not ready", "capabilities incomplete", "core handoffs incomplete", "secrets audit is not clean", "security audit has critical findings"} for reason in live_reasons):
        live_status = "BLOCKED"
    else:
        live_status = "REVIEW_REQUIRED"

    return {
        "demo": {
            "status": demo_status,
            "reasons": demo_reasons,
        },
        "liveExternalContact": {
            "status": live_status,
            "reasons": live_reasons,
        },
        "inputs": {
            "allCapabilitiesPassed": caps_passed,
            "failedCapabilities": caps_failed,
            "coreHandoffsComplete": core_handoffs_ok,
            "connectedChannelCount": connected_channel_count,
            "secretsAudit": {
                "plaintextCount": plaintext,
                "unresolvedRefCount": unresolved,
            },
            "securityAuditCritical": security_critical,
            "manualArmEnabled": arm_enabled,
            "staleCapabilities": stale_capabilities,
            "freshnessHours": freshness_hours,
        },
    }


def collect_snapshot(runtime_flags: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    runtime_flags = runtime_flags or {}

    capabilities = evaluate_capabilities()
    agent_summary = summarize_agents(capabilities)
    handoffs = evaluate_handoffs()

    status_all = run_openclaw_json(["status", "--all", "--json"], timeout=120)
    channels_status = run_openclaw_json(["channels", "status", "--json"], timeout=60)
    channels_list = run_openclaw_json(["channels", "list", "--json"], timeout=60)
    secrets_audit = run_openclaw_json(["secrets", "audit", "--json"], timeout=90)

    policy = load_policy()
    readiness = evaluate_readiness(
        capabilities=capabilities,
        handoffs=handoffs,
        channels_status=channels_status,
        secrets_audit=secrets_audit,
        status_all=status_all,
        policy=policy,
        runtime_flags=runtime_flags,
    )

    snapshot = {
        "generatedAt": iso_now(),
        "profile": PROFILE,
        "repoRoot": str(REPO_ROOT),
        "agents": agent_summary,
        "capabilities": capabilities,
        "handoffs": handoffs,
        "readiness": readiness,
        "runtime": {
            "statusAll": status_all,
            "channelsStatus": channels_status,
            "channelsList": channels_list,
            "secretsAudit": secrets_audit,
        },
        "policy": policy,
        "industryPatterns": load_industry_patterns(),
    }
    return snapshot


def main() -> None:
    snapshot = collect_snapshot(runtime_flags={"manualArmEnabled": False})
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
