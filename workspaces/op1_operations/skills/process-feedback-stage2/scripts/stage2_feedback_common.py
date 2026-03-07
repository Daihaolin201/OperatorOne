#!/usr/bin/env python3
"""Common helpers for op1_operations Stage2 feedback processing."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


def resolve_repo_root(start: Path | None = None) -> Path:
    seed = (start or Path(__file__)).resolve()
    for candidate in [seed, *seed.parents]:
        if (candidate / "handoffs").exists() and (candidate / "workspaces").exists():
            return candidate
    raise FileNotFoundError("Unable to locate OperatorOne repo root")


def _fixed_now_from_env() -> datetime | None:
    raw = str(os.environ.get("STAGE2_AS_OF", "")).strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def now_utc() -> datetime:
    fixed = _fixed_now_from_env()
    if fixed is not None:
        return fixed
    return datetime.now(tz=timezone.utc)


def now_iso() -> str:
    return now_utc().replace(microsecond=0).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def iso_date(value: str | None) -> str:
    dt = parse_iso(value)
    if dt is None:
        return now_utc().date().isoformat()
    return dt.date().isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_or_yaml_like(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return default
    # JSON is valid YAML. We use JSON parsing to avoid PyYAML dependency.
    try:
        return json.loads(text)
    except Exception:
        return default


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
        except Exception:
            continue
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def stable_hash(parts: Iterable[Any], length: int = 32) -> str:
    joined = "||".join(str(p) for p in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return digest[:length]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_NON_WORD_RE = re.compile(r"[^a-z0-9\s]+", re.IGNORECASE)
_MULTI_SPACE_RE = re.compile(r"\s+")


STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "for",
    "of",
    "in",
    "on",
    "at",
    "with",
    "is",
    "it",
    "this",
    "that",
    "we",
    "you",
    "our",
    "your",
    "be",
    "are",
    "from",
    "as",
    "by",
    "can",
    "will",
    "not",
    "now",
    "please",
    "just",
}


def normalize_text(text: str | None) -> str:
    raw = str(text or "")
    raw = _URL_RE.sub(" ", raw)
    raw = raw.lower()
    raw = _NON_WORD_RE.sub(" ", raw)
    raw = _MULTI_SPACE_RE.sub(" ", raw).strip()
    return raw


def detect_language(text: str | None) -> str:
    raw = str(text or "")
    if re.search(r"[\u4e00-\u9fff]", raw):
        return "zh"
    return "en"


def tokenize(text: str | None) -> List[str]:
    norm = normalize_text(text)
    if not norm:
        return []
    tokens = [t for t in norm.split(" ") if t and t not in STOPWORDS and len(t) > 2]
    return tokens


def _contains_any(haystack: str, needles: Iterable[str]) -> bool:
    return any(n in haystack for n in needles)


def classify_topic_subtopic(text: str, detail: str = "", event_type: str = "") -> Tuple[str, str]:
    t = normalize_text(" ".join([text or "", detail or "", event_type or ""]))
    ev = normalize_text(event_type or "")

    if ev in {"reply_positive", "reply_converted", "paid_started", "discovery_scheduled"}:
        return "retention", "conversion_signal"

    if _contains_any(t, ["budget", "price", "cost", "expensive", "fees", "fee", "roi"]):
        if "budget" in t:
            return "pricing", "budget"
        if "roi" in t:
            return "pricing", "roi_unclear"
        return "pricing", "price_sensitivity"

    if _contains_any(t, ["unsubscribe", "stop", "do not contact", "not interested", "already use", "already using"]):
        if "unsubscribe" in t or "do not contact" in t:
            return "trust", "unsubscribe"
        return "retention", "competitor_lockin"

    if _contains_any(t, ["security", "compliance", "gdpr", "risk", "fraud", "fake", "seriously"]):
        if "fraud" in t or "fake" in t:
            return "trust", "fraud_risk"
        return "trust", "security"

    if _contains_any(t, ["integration", "api", "workflow", "tool", "stack", "sync", "folder", "accountant"]):
        if "api" in t:
            return "integration", "api"
        if "accountant" in t and "folder" in t:
            return "integration", "data_sync"
        return "integration", "workflow_fit"

    if _contains_any(
        t,
        [
            "bookkeeping",
            "spreadsheet",
            "manual",
            "reporting",
            "setup",
            "onboard",
            "learn",
            "expense",
            "expenses",
            "accounting",
            "tax",
        ],
    ):
        if _contains_any(t, ["spreadsheet", "manual", "bookkeeping", "accounting", "expenses", "expense"]):
            return "onboarding", "manual_work"
        if "reporting" in t:
            return "onboarding", "reporting_friction"
        return "onboarding", "setup_complexity"

    if _contains_any(
        t,
        [
            "invoice",
            "payment",
            "chargeback",
            "collections",
            "collect",
            "pay",
            "owed",
            "owes",
            "ghosting",
            "late fee",
            "credit card",
            "bank account",
            "contractors",
        ],
    ):
        if "chargeback" in t:
            return "billing", "chargeback"
        if "invoice" in t or "owed" in t or "owes" in t:
            return "billing", "invoice_flow"
        return "billing", "payment_flow"

    if _contains_any(t, ["bug", "error", "crash", "slow", "latency", "broken"]):
        if "error" in t or "bug" in t or "broken" in t:
            return "performance", "bug"
        return "performance", "latency"

    if _contains_any(t, ["support", "help", "response", "guidance", "advice", "stuck", "wish", "known", "recap"]):
        return "support", "guidance_gap"

    if _contains_any(t, ["not now", "next quarter", "later", "timing"]):
        return "retention", "timing_hold"

    return "general", "uncategorized"


def _sentiment_from_feedback_type(feedback_type: str) -> Tuple[str, float]:
    if feedback_type in {"objection", "churn_risk", "bug", "pricing"}:
        return "negative", -0.7
    if feedback_type in {"confusion", "other", "feature_request"}:
        return "neutral", 0.0
    if feedback_type in {"praise"}:
        return "positive", 0.65
    return "neutral", 0.0


def classify_feedback(
    *,
    raw_text: str,
    detail: str,
    event_type: str,
    source_adapter: str,
) -> Dict[str, Any]:
    ev = str(event_type or "").strip().lower()
    det = str(detail or "").strip().lower()
    full = " ".join([raw_text or "", det, ev])
    full_norm = normalize_text(full)

    feedback_type = "other"
    journey_stage = "unknown"
    severity = 2
    urgency = 2

    # Text-first overrides (protect against upstream event misclassification).
    if _contains_any(full_norm, ["unsubscribe", "remove me", "do not contact", "opt out"]):
        feedback_type = "churn_risk"
        journey_stage = "signup_to_paid"
        severity = 5
        urgency = 4
    elif _contains_any(full_norm, ["not interested", "no thanks", "already use", "already using", "not for us"]):
        feedback_type = "objection"
        journey_stage = "signup_to_paid"
        severity = 4
        urgency = 3
    elif _contains_any(full_norm, ["budget", "price", "cost", "expensive"]):
        feedback_type = "pricing"
        journey_stage = "signup_to_paid"
        severity = 4
        urgency = 4
    elif _contains_any(full_norm, ["payment sent", "let s start", "lets start", "signed", "go ahead"]):
        feedback_type = "praise"
        journey_stage = "signup_to_paid"
        severity = 1
        urgency = 1

    # Event-driven defaults/fallback.
    if feedback_type == "other":
        if ev in {"reply_objection", "objection_logged"}:
            feedback_type = "objection"
            journey_stage = "signup_to_paid"
            severity = 4
            urgency = 4
        elif ev in {"reply_unsubscribe", "closed_lost"}:
            feedback_type = "churn_risk"
            journey_stage = "signup_to_paid"
            severity = 5
            urgency = 4
        elif ev in {"reply_not_now"}:
            feedback_type = "other"
            journey_stage = "signup_to_paid"
            severity = 3
            urgency = 2
        elif ev in {"reply_positive", "reply_converted", "discovery_scheduled", "paid_started"}:
            feedback_type = "praise"
            journey_stage = "signup_to_paid"
            severity = 1
            urgency = 1
        elif source_adapter == "conversion_pipeline_pains":
            feedback_type = "confusion"
            journey_stage = "problem_discovery"
            severity = 3
            urgency = 3
        elif source_adapter == "product_runtime_feedback":
            feedback_type = "other"
            journey_stage = "post_purchase"
            severity = 2
            urgency = 2

    topic, subtopic = classify_topic_subtopic(full, detail=det, event_type=ev)

    # Topic can upgrade type for better scoring.
    if topic == "pricing" and feedback_type in {"other", "confusion"}:
        feedback_type = "pricing"
    if topic == "performance" and feedback_type == "other":
        feedback_type = "bug"

    # Fallback enrichment for pipeline pains to avoid excessive uncategorized feedback.
    if topic == "general" and source_adapter == "conversion_pipeline_pains":
        if _contains_any(full_norm, ["invoice", "payment", "chargeback", "bank", "credit card", "owed", "owes", "ghosting"]):
            topic, subtopic = "billing", "invoice_flow"
        elif _contains_any(full_norm, ["bookkeeping", "accounting", "tax", "expense", "manual", "spreadsheet", "accountant"]):
            topic, subtopic = "onboarding", "manual_work"
        else:
            topic, subtopic = "support", "guidance_gap"

    sentiment, sentiment_score = _sentiment_from_feedback_type(feedback_type)

    if subtopic in {"fraud_risk", "unsubscribe"}:
        severity = max(severity, 5)
        urgency = max(urgency, 4)
        sentiment = "negative"
        sentiment_score = -0.9

    if subtopic in {"budget", "price_sensitivity", "roi_unclear"}:
        severity = max(severity, 4)

    return {
        "feedback_type": feedback_type,
        "topic": topic,
        "subtopic": subtopic,
        "journey_stage": journey_stage,
        "severity": int(clamp(float(severity), 1.0, 5.0)),
        "urgency": int(clamp(float(urgency), 1.0, 5.0)),
        "sentiment": sentiment,
        "sentiment_score": round(float(clamp(sentiment_score, -1.0, 1.0)), 3),
    }


def kano_label_for(topic: str, feedback_type: str) -> str:
    t = str(topic or "general")
    f = str(feedback_type or "other")
    if t in {"trust", "performance", "billing"} or f in {"bug", "churn_risk"}:
        return "basic"
    if t in {"pricing", "integration", "onboarding", "support", "retention"}:
        return "performance"
    if f == "feature_request":
        return "delighter"
    return "performance"


def owner_team_for_topic(topic: str) -> str:
    t = str(topic or "general")
    if t in {"onboarding", "integration", "performance", "support"}:
        return "product"
    if t in {"pricing", "trust", "retention", "billing"}:
        return "product_sales"
    return "operations"


def suggested_action_for(topic: str, subtopic: str, feedback_type: str) -> str:
    t = str(topic or "general")
    s = str(subtopic or "uncategorized")
    f = str(feedback_type or "other")

    if s == "budget":
        return "Design low-risk pilot offer with ROI proof and objection-handling script."
    if s == "unsubscribe":
        return "Audit outreach relevance and tighten targeting + permission controls."
    if s == "fraud_risk":
        return "Prioritize controls and trust messaging for fraud/abuse mitigation workflow."
    if t == "onboarding":
        return "Simplify first-time setup and ship guided checklist for primary job-to-be-done."
    if t == "integration":
        return "Create integration readiness matrix and reduce connector setup friction."
    if t == "billing":
        return "Improve invoice/payment flow clarity and automate failure handling steps."
    if f == "praise":
        return "Capture winning pattern and amplify in messaging + sales collateral."
    return "Triaged review with owner assignment and hypothesis for measurable KPI lift."
