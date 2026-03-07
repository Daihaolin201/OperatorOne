#!/usr/bin/env python3
"""Handoff contract versions + payload validators for OperatorOne.

This module intentionally avoids external dependencies.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple

CONTRACT_VERSION_MAP: Dict[str, str] = {
    "product_to_marketing": "1.0.0",
    "marketing_to_sales": "1.0.0",
    "sales_to_operations": "1.0.0",
    "operations_to_product": "1.0.0",
    "operations_to_marketing": "1.0.0",
    "operations_to_sales": "1.0.0",
    "operations_to_product_iterate": "1.0.0",
    "operations_to_marketing_iterate": "1.0.0",
    "operations_to_sales_iterate": "1.0.0",
}


def _is_nonempty_str(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_iso8601(v: Any) -> bool:
    if not _is_nonempty_str(v):
        return False
    raw = str(v).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        datetime.fromisoformat(raw)
        return True
    except ValueError:
        return False


def _expect(payload: Dict[str, Any], key: str, pred, errors: List[str], msg: str) -> None:
    if key not in payload or not pred(payload.get(key)):
        errors.append(f"{key}: {msg}")


def _expect_list_of_dict(payload: Dict[str, Any], key: str, errors: List[str]) -> List[Dict[str, Any]]:
    val = payload.get(key)
    if not isinstance(val, list):
        errors.append(f"{key}: expected list")
        return []
    bad = [i for i, x in enumerate(val) if not isinstance(x, dict)]
    if bad:
        errors.append(f"{key}: expected list of objects; invalid indexes={bad[:8]}")
    return [x for x in val if isinstance(x, dict)]


def _expect_list_of_str(payload: Dict[str, Any], key: str, errors: List[str], allow_empty: bool = True) -> List[str]:
    val = payload.get(key)
    if not isinstance(val, list):
        errors.append(f"{key}: expected list")
        return []
    if any(not _is_nonempty_str(x) for x in val):
        errors.append(f"{key}: expected list of non-empty strings")
    if not allow_empty and len(val) == 0:
        errors.append(f"{key}: expected non-empty list")
    return [str(x) for x in val if _is_nonempty_str(x)]


def _validate_contract_version(contract_name: str, payload: Dict[str, Any], errors: List[str]) -> None:
    expected = CONTRACT_VERSION_MAP.get(contract_name)
    actual = payload.get("contract_version")
    if not expected:
        errors.append(f"contract_version: unknown contract `{contract_name}`")
        return
    if actual != expected:
        errors.append(f"contract_version: expected `{expected}`, got `{actual}`")


def _validate_product_to_marketing(payload: Dict[str, Any], errors: List[str], warnings: List[str]) -> None:
    _expect(payload, "generated_at", _is_iso8601, errors, "expected ISO-8601 string")
    _expect(payload, "status", _is_nonempty_str, errors, "expected non-empty string")
    _expect(payload, "idea_name", _is_nonempty_str, errors, "expected non-empty string")
    _expect(payload, "icp", _is_nonempty_str, errors, "expected non-empty string")
    _expect(payload, "problem", _is_nonempty_str, errors, "expected non-empty string")
    _expect(payload, "landing_page_url_or_path", _is_nonempty_str, errors, "expected non-empty string")
    _expect(payload, "notes", _is_nonempty_str, errors, "expected non-empty string")
    _expect_list_of_str(payload, "mvp_scope", errors, allow_empty=False)

    pos = payload.get("positioning")
    if not isinstance(pos, dict):
        errors.append("positioning: expected object")
    else:
        if not _is_nonempty_str(pos.get("headline")):
            errors.append("positioning.headline: expected non-empty string")
        if not _is_nonempty_str(pos.get("value_proposition")):
            errors.append("positioning.value_proposition: expected non-empty string")

    constraints = payload.get("constraints")
    if not isinstance(constraints, dict):
        errors.append("constraints: expected object")
    else:
        if not _is_number(constraints.get("budget")):
            errors.append("constraints.budget: expected number")
        if not _is_number(constraints.get("timeline_days")):
            errors.append("constraints.timeline_days: expected number")
        tmp = constraints.get("out_of_scope")
        if not isinstance(tmp, list) or any(not _is_nonempty_str(x) for x in tmp):
            errors.append("constraints.out_of_scope: expected list of non-empty strings")

    if "generated_at" in payload and not _is_iso8601(payload.get("generated_at")):
        errors.append("generated_at: expected ISO-8601 string when provided")

    if not _is_nonempty_str(payload.get("generated_by")):
        warnings.append("generated_by: recommended for traceability")


def _validate_marketing_to_sales(payload: Dict[str, Any], errors: List[str], warnings: List[str]) -> None:
    _expect(payload, "generated_at", _is_iso8601, errors, "expected ISO-8601 string")

    campaigns = _expect_list_of_dict(payload, "campaigns", errors)
    for i, c in enumerate(campaigns):
        if not _is_nonempty_str(c.get("campaign_id")):
            errors.append(f"campaigns[{i}].campaign_id: expected non-empty string")
        if not _is_nonempty_str(c.get("name")):
            errors.append(f"campaigns[{i}].name: expected non-empty string")
        if not _is_nonempty_str(c.get("status")):
            errors.append(f"campaigns[{i}].status: expected non-empty string")
        has_bool_flag = isinstance(c.get("auto_publish"), bool) or isinstance(c.get("auto_launch"), bool)
        if not has_bool_flag:
            warnings.append(f"campaigns[{i}]: expected `auto_publish` or `auto_launch` boolean")

    content_assets = _expect_list_of_dict(payload, "content_assets", errors)
    for i, x in enumerate(content_assets):
        if not _is_nonempty_str(x.get("content_id")):
            errors.append(f"content_assets[{i}].content_id: expected non-empty string")
        if not _is_nonempty_str(x.get("status")):
            errors.append(f"content_assets[{i}].status: expected non-empty string")

    seo_targets = _expect_list_of_dict(payload, "seo_targets", errors)
    for i, x in enumerate(seo_targets):
        if not _is_nonempty_str(x.get("keyword")):
            errors.append(f"seo_targets[{i}].keyword: expected non-empty string")
        if not _is_nonempty_str(x.get("status")):
            errors.append(f"seo_targets[{i}].status: expected non-empty string")

    lead_signals = payload.get("lead_signals")
    if not isinstance(lead_signals, dict):
        errors.append("lead_signals: expected object")
    else:
        channels = lead_signals.get("top_channels")
        if not isinstance(channels, list) or any(not _is_nonempty_str(x) for x in channels):
            errors.append("lead_signals.top_channels: expected list of non-empty strings")
        if not _is_number(lead_signals.get("estimated_weekly_leads")):
            errors.append("lead_signals.estimated_weekly_leads: expected number")

    if not isinstance(payload.get("offer_context"), dict):
        errors.append("offer_context: expected object")

    if "generated_by" not in payload:
        warnings.append("generated_by: recommended for traceability")


def _validate_sales_to_operations(payload: Dict[str, Any], errors: List[str], warnings: List[str]) -> None:
    for key in ["prospects_contacted", "replies", "calls_booked", "customers_converted", "mrr"]:
        if not _is_number(payload.get(key)):
            errors.append(f"{key}: expected number")
        elif payload.get(key) < 0:
            errors.append(f"{key}: expected non-negative number")

    if not isinstance(payload.get("objections_summary"), list):
        errors.append("objections_summary: expected list")
    else:
        for i, x in enumerate(payload.get("objections_summary") or []):
            if not isinstance(x, dict):
                errors.append(f"objections_summary[{i}]: expected object")
                continue
            if not _is_nonempty_str(x.get("reason")):
                errors.append(f"objections_summary[{i}].reason: expected non-empty string")
            if not _is_number(x.get("count")):
                errors.append(f"objections_summary[{i}].count: expected number")

    if not _is_nonempty_str(payload.get("handoff_notes")):
        errors.append("handoff_notes: expected non-empty string")

    if "generated_at" in payload and not _is_iso8601(payload.get("generated_at")):
        errors.append("generated_at: expected ISO-8601 string when provided")

    if "generated_by" not in payload:
        warnings.append("generated_by: recommended for traceability")


def _validate_operations_stage2_common(payload: Dict[str, Any], errors: List[str]) -> None:
    _expect(payload, "generated_at", _is_iso8601, errors, "expected ISO-8601 string")
    _expect(payload, "from", _is_nonempty_str, errors, "expected non-empty string")
    _expect(payload, "objective", _is_nonempty_str, errors, "expected non-empty string")


def _validate_operations_to_product(payload: Dict[str, Any], errors: List[str], warnings: List[str]) -> None:
    _validate_operations_stage2_common(payload, errors)
    items = _expect_list_of_dict(payload, "items", errors)
    for i, x in enumerate(items):
        if not _is_nonempty_str(x.get("feedback_item_id")):
            errors.append(f"items[{i}].feedback_item_id: expected non-empty string")
        if not _is_nonempty_str(x.get("topic")):
            errors.append(f"items[{i}].topic: expected non-empty string")
        if not _is_nonempty_str(x.get("priority_tier")):
            errors.append(f"items[{i}].priority_tier: expected non-empty string")
    if "notes" not in payload:
        warnings.append("notes: recommended for downstream context")


def _validate_operations_to_marketing(payload: Dict[str, Any], errors: List[str], warnings: List[str]) -> None:
    _validate_operations_stage2_common(payload, errors)
    signals = _expect_list_of_dict(payload, "top_signal_topics", errors)
    for i, x in enumerate(signals):
        if not _is_nonempty_str(x.get("topic")):
            errors.append(f"top_signal_topics[{i}].topic: expected non-empty string")
        if not _is_number(x.get("weighted_score")):
            errors.append(f"top_signal_topics[{i}].weighted_score: expected number")

    recs = payload.get("recommendations")
    if not isinstance(recs, list) or any(not _is_nonempty_str(x) for x in recs):
        errors.append("recommendations: expected list of non-empty strings")
    elif len(recs) == 0:
        warnings.append("recommendations: empty list may reduce downstream usability")


def _validate_operations_to_sales(payload: Dict[str, Any], errors: List[str], warnings: List[str]) -> None:
    _validate_operations_stage2_common(payload, errors)
    obs = _expect_list_of_dict(payload, "objection_counts", errors)
    for i, x in enumerate(obs):
        if not _is_nonempty_str(x.get("objection_key")):
            errors.append(f"objection_counts[{i}].objection_key: expected non-empty string")
        if not _is_number(x.get("count")):
            errors.append(f"objection_counts[{i}].count: expected number")

    talks = payload.get("talk_tracks")
    if not isinstance(talks, list) or any(not _is_nonempty_str(x) for x in talks):
        errors.append("talk_tracks: expected list of non-empty strings")
    elif len(talks) == 0:
        warnings.append("talk_tracks: empty list may reduce downstream usability")


def _validate_operations_iterate_common(payload: Dict[str, Any], errors: List[str], warnings: List[str]) -> List[Dict[str, Any]]:
    _validate_operations_stage2_common(payload, errors)
    items = _expect_list_of_dict(payload, "items", errors)
    return items


def _validate_operations_to_product_iterate(payload: Dict[str, Any], errors: List[str], warnings: List[str]) -> None:
    items = _validate_operations_iterate_common(payload, errors, warnings)
    for i, x in enumerate(items):
        if not _is_nonempty_str(x.get("experiment_id")):
            errors.append(f"items[{i}].experiment_id: expected non-empty string")
        if not _is_nonempty_str(x.get("decision")):
            errors.append(f"items[{i}].decision: expected non-empty string")


def _validate_operations_to_marketing_iterate(payload: Dict[str, Any], errors: List[str], warnings: List[str]) -> None:
    items = _validate_operations_iterate_common(payload, errors, warnings)
    for i, x in enumerate(items):
        if not _is_nonempty_str(x.get("experiment_id")):
            errors.append(f"items[{i}].experiment_id: expected non-empty string")


def _validate_operations_to_sales_iterate(payload: Dict[str, Any], errors: List[str], warnings: List[str]) -> None:
    items = _validate_operations_iterate_common(payload, errors, warnings)
    for i, x in enumerate(items):
        if not _is_nonempty_str(x.get("experiment_id")):
            errors.append(f"items[{i}].experiment_id: expected non-empty string")


_VALIDATORS = {
    "product_to_marketing": _validate_product_to_marketing,
    "marketing_to_sales": _validate_marketing_to_sales,
    "sales_to_operations": _validate_sales_to_operations,
    "operations_to_product": _validate_operations_to_product,
    "operations_to_marketing": _validate_operations_to_marketing,
    "operations_to_sales": _validate_operations_to_sales,
    "operations_to_product_iterate": _validate_operations_to_product_iterate,
    "operations_to_marketing_iterate": _validate_operations_to_marketing_iterate,
    "operations_to_sales_iterate": _validate_operations_to_sales_iterate,
}


def validate_contract_payload(contract_name: str, payload: Any) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    if contract_name not in _VALIDATORS:
        return [f"unknown contract: {contract_name}"], warnings

    if not isinstance(payload, dict):
        return ["payload: expected object"], warnings

    _validate_contract_version(contract_name, payload, errors)
    _VALIDATORS[contract_name](payload, errors, warnings)
    return errors, warnings
