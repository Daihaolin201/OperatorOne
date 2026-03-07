#!/usr/bin/env python3
"""Scaffold a deployable web product from project spec (preferred) or stage3 blueprint (legacy)."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import pathlib
import re
import shutil
import textwrap
from typing import Any, Dict, List, Tuple


BLUEPRINT_REQUIRED_TEXT_PATHS = [
    ("project_id",),
    ("from_opportunity_id",),
    ("hypothesis", "for_segment"),
    ("hypothesis", "problem"),
    ("hypothesis", "value_proposition"),
    ("test_design_14d", "experiment"),
    ("test_design_14d", "channel"),
    ("test_design_14d", "offer"),
    ("success_metric", "metric"),
    ("success_metric", "target"),
]

BLUEPRINT_REQUIRED_LIST_PATHS = [
    ("mvp_boundary", "in_scope"),
    ("mvp_boundary", "out_of_scope"),
    ("kill_criteria",),
]

PROJECT_SPEC_REQUIRED_TEXT_PATHS = [
    ("spec_version",),
    ("project_id",),
    ("source", "opportunity_id"),
    ("problem_statement",),
    ("value_proposition",),
    ("offer", "headline"),
    ("offer", "cta_label"),
    ("workflow", "prompt_label"),
    ("workflow", "prompt_placeholder"),
    ("workflow", "primary_action_label"),
    ("workflow", "default_response", "first_step"),
    ("metrics", "success_metric"),
    ("metrics", "target"),
    ("adapter", "name"),
]

PROJECT_SPEC_REQUIRED_LIST_PATHS = [
    ("workflow", "rules"),
    ("workflow", "default_response", "next_steps"),
    ("metrics", "kill_criteria"),
]

PAGE_SPEC_REQUIRED_TEXT_PATHS = [
    ("page_spec_version",),
    ("project_id",),
    ("adapter_name",),
    ("layout_profile",),
]

PAGE_SPEC_REQUIRED_LIST_PATHS = [
    ("modules",),
    ("testing", "expected_modules"),
]


def read_json(path: pathlib.Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_file(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def nested_get(obj: Dict[str, Any], path: Tuple[str, ...]) -> Any:
    cur: Any = obj
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def is_non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def is_non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def missing_fields(
    payload: Dict[str, Any],
    required_text_paths: List[Tuple[str, ...]],
    required_list_paths: List[Tuple[str, ...]],
) -> List[str]:
    missing: List[str] = []
    for path in required_text_paths:
        if not is_non_empty_text(nested_get(payload, path)):
            missing.append(".".join(path))
    for path in required_list_paths:
        if not is_non_empty_list(nested_get(payload, path)):
            missing.append(".".join(path))
    return missing


def sanitize_slug(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-") or "web-product"


def ensure_list_of_text(values: Any, fallback: List[str]) -> List[str]:
    if not isinstance(values, list) or len(values) == 0:
        return fallback
    out: List[str] = []
    for item in values:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out or fallback


def pick_top_advance(stage2: Dict[str, Any]) -> str:
    rows = stage2.get("decisions", [])
    advances = [r for r in rows if r.get("decision") == "advance"]
    if not advances:
        raise ValueError("No advance opportunity found in stage2 decision log.")
    advances.sort(key=lambda x: float(x.get("weighted_score", 0.0)), reverse=True)
    return str(advances[0].get("opportunity_id"))


def find_opp(stage1: Dict[str, Any], opportunity_id: str) -> Dict[str, Any]:
    for opp in stage1.get("opportunities", []):
        if opp.get("opportunity_id") == opportunity_id:
            return opp
    raise ValueError(f"Opportunity {opportunity_id} not found in stage1 records.")


def build_autofilled_blueprint(stage1: Dict[str, Any], stage2: Dict[str, Any], opp_id: str | None) -> Dict[str, Any]:
    selected_opp_id = opp_id or pick_top_advance(stage2)
    opp = find_opp(stage1, selected_opp_id)

    segment = opp.get("target_segment", {}) if isinstance(opp.get("target_segment"), dict) else {}
    role = segment.get("role", "Operator")
    industry = segment.get("industry", "Business services")
    company_size = segment.get("company_size", "1-20")
    channel = (
        opp.get("distribution_entry", {}).get("channel")
        if isinstance(opp.get("distribution_entry"), dict)
        else "Operator communities"
    )

    return {
        "project_id": f"proj-{selected_opp_id}-v1",
        "from_opportunity_id": selected_opp_id,
        "hypothesis": {
            "for_segment": f"{role} in {industry} ({company_size})",
            "problem": opp.get("core_problem", "Manual operational friction with measurable loss."),
            "value_proposition": "Automate the highest-friction manual step and capture buyer intent quickly.",
        },
        "mvp_boundary": {
            "in_scope": [
                "Single core workflow",
                "First-step recommendation endpoint",
                "Intent capture endpoint",
                "Deployment verification endpoint"
            ],
            "out_of_scope": [
                "Complex integrations",
                "Advanced auth/billing",
                "Enterprise-grade customization"
            ],
        },
        "test_design_14d": {
            "experiment": "Drive initial target users to the MVP and measure qualified intent captures.",
            "channel": channel or "Operator communities",
            "sample_target": 20,
            "offer": "Early access in exchange for workflow feedback",
        },
        "pricing_hypothesis": {
            "plan_a": "$19/month",
            "plan_b": "$79/month",
        },
        "success_metric": {
            "metric": "Qualified intent captures",
            "target": "At least 5 from first 20 targeted users",
        },
        "kill_criteria": [
            "Fewer than 2 qualified captures after 20 targeted visitors",
            "Core workflow completion below 20%"
        ],
        "_autofill": {
            "enabled": True,
            "source": "stage1+stage2",
            "opportunity_id": selected_opp_id,
        },
    }


def project_spec_from_blueprint(blueprint: Dict[str, Any]) -> Dict[str, Any]:
    hypothesis = blueprint.get("hypothesis", {}) if isinstance(blueprint.get("hypothesis"), dict) else {}
    mvp = blueprint.get("mvp_boundary", {}) if isinstance(blueprint.get("mvp_boundary"), dict) else {}
    test_design = (
        blueprint.get("test_design_14d", {}) if isinstance(blueprint.get("test_design_14d"), dict) else {}
    )
    pricing = (
        blueprint.get("pricing_hypothesis", {})
        if isinstance(blueprint.get("pricing_hypothesis"), dict)
        else {}
    )
    success = blueprint.get("success_metric", {}) if isinstance(blueprint.get("success_metric"), dict) else {}

    return {
        "spec_version": "1.0",
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "project_id": blueprint.get("project_id", "proj-blueprint-v1"),
        "source": {
            "opportunity_id": blueprint.get("from_opportunity_id", "opp-unknown"),
            "stage": "stage3",
            "selection_reason": "blueprint_input",
        },
        "segment": {
            "role": hypothesis.get("for_segment", "Target users"),
            "industry": "mixed",
            "company_size": "1-20",
        },
        "problem_statement": hypothesis.get("problem", "Problem statement missing"),
        "value_proposition": hypothesis.get("value_proposition", "Provide a focused workflow with measurable signal"),
        "offer": {
            "headline": hypothesis.get("value_proposition", "Launch a focused MVP"),
            "cta_label": "Join pilot",
            "cta_type": "email_waitlist",
            "channel_hint": test_design.get("channel", "target communities"),
        },
        "workflow": {
            "prompt_label": "Describe your current situation",
            "prompt_placeholder": "Share your biggest current workflow blocker.",
            "primary_action_label": "Generate first step",
            "rules": [
                {
                    "id": "generic-from-blueprint",
                    "priority": 5,
                    "keywords": ["manual", "slow", "issue", "bottleneck"],
                    "first_step": "Map the workflow in three steps and automate the highest-friction step first.",
                    "next_steps": [
                        "Instrument one conversion metric.",
                        "Run a 14-day focused test.",
                        "Apply kill criteria if signal is weak."
                    ]
                }
            ],
            "default_response": {
                "first_step": "Define a single user path and ship it before adding extra features.",
                "next_steps": [
                    "Collect first-user feedback quickly.",
                    "Track one success metric.",
                    "Iterate weekly."
                ]
            }
        },
        "metrics": {
            "success_metric": success.get("metric", "Qualified intent captures"),
            "target": success.get("target", "5 qualified captures from first 20 users"),
            "kill_criteria": ensure_list_of_text(blueprint.get("kill_criteria"), ["Insufficient qualified signal"]),
        },
        "pricing": {
            "plan_a": pricing.get("plan_a", "$19/month"),
            "plan_b": pricing.get("plan_b", "$79/month"),
        },
        "adapter": {
            "name": "blueprint-generic",
            "display_name": "Blueprint Generic Adapter",
            "description": "Fallback adapter generated from stage3 blueprint",
            "match_score": 0.0,
            "match_reason": "legacy_blueprint_conversion",
        },
        "business_tests": [
            {
                "name": "generic_blueprint_response",
                "input": "We have repetitive manual bottlenecks in operations.",
                "expect_first_step_contains": ["automate", "highest-friction"],
            }
        ],
        "legacy_blueprint": {
            "in_scope": ensure_list_of_text(mvp.get("in_scope"), ["Single core workflow"]),
            "out_of_scope": ensure_list_of_text(mvp.get("out_of_scope"), ["Complex integrations"]),
            "experiment": test_design.get("experiment", "14-day test"),
            "offer": test_design.get("offer", "Early access"),
        },
    }


def validate_project_spec(spec: Dict[str, Any]) -> List[str]:
    return missing_fields(spec, PROJECT_SPEC_REQUIRED_TEXT_PATHS, PROJECT_SPEC_REQUIRED_LIST_PATHS)


def validate_page_spec(page_spec: Dict[str, Any]) -> List[str]:
    missing = missing_fields(page_spec, PAGE_SPEC_REQUIRED_TEXT_PATHS, PAGE_SPEC_REQUIRED_LIST_PATHS)

    modules = page_spec.get("modules", [])
    if isinstance(modules, list) and len(modules) > 0:
        for idx, module in enumerate(modules):
            if not isinstance(module, dict):
                missing.append(f"modules[{idx}]")
                continue
            if not is_non_empty_text(module.get("module_id")):
                missing.append(f"modules[{idx}].module_id")
            if not is_non_empty_text(module.get("kind")):
                missing.append(f"modules[{idx}].kind")
            if not isinstance(module.get("props"), dict):
                missing.append(f"modules[{idx}].props")
    return missing


def render_list_items(values: List[str]) -> str:
    return "\n".join(f"<li>{html.escape(item)}</li>" for item in values)


def module_html(module: Dict[str, Any], page_mode: str = "web_product") -> str:
    module_id = str(module.get("module_id", "unknown"))
    props = module.get("props", {}) if isinstance(module.get("props"), dict) else {}

    if module_id == "hero_problem":
        headline = html.escape(str(props.get("headline", "Focused workflow")))
        subheadline = html.escape(str(props.get("subheadline", "Validate one business workflow fast.")))
        segment = html.escape(str(props.get("segment_label", "Target operators")))
        problem = html.escape(str(props.get("problem_statement", "Problem statement missing.")))
        adapter_name = html.escape(str(props.get("adapter_name", "Unknown adapter")))
        profile = html.escape(str(props.get("profile_name", "Default profile")))
        eyebrow = html.escape(str(props.get("eyebrow", "" if page_mode == "landing" else "Reusable web-product builder")))

        eyebrow_line = ""
        if eyebrow:
            eyebrow_line = f'<p class=\"eyebrow\">{eyebrow}</p>'

        meta_line = ""
        if page_mode != "landing":
            meta_line = f'<p class=\"meta\"><strong>Adapter:</strong> {adapter_name} · <strong>Layout:</strong> {profile}</p>'

        return f"""
        <section class=\"module hero\" data-module=\"{module_id}\">
          <div class=\"hero-shell\">
            {eyebrow_line}
            <h1>{headline}</h1>
            <p class=\"lede\">{subheadline}</p>
            <p class=\"meta\"><strong>For:</strong> {segment}</p>
            <p class=\"problem\">{problem}</p>
            {meta_line}
          </div>
        </section>
        """

    if module_id == "workflow_interactive":
        title = html.escape(str(props.get("title", "Try the workflow assistant")))
        prompt_label = html.escape(str(props.get("prompt_label", "Describe your situation")))
        prompt_placeholder = html.escape(str(props.get("prompt_placeholder", "Describe your bottleneck...")))
        action_label = html.escape(str(props.get("action_label", "Generate first step")))
        return f"""
        <section class=\"module\" data-module=\"{module_id}\">
          <article class=\"panel\">
            <h2>{title}</h2>
            <form id=\"workflow-form\">
              <label for=\"input\">{prompt_label}</label>
              <textarea id=\"input\" name=\"input\" placeholder=\"{prompt_placeholder}\" required></textarea>
              <button type=\"submit\">{action_label}</button>
            </form>
            <pre id=\"workflow-result\" aria-live=\"polite\"></pre>
          </article>
        </section>
        """

    if module_id == "problem_agitation":
        title = html.escape(str(props.get("title", "Why this problem matters")))
        core_pain = html.escape(str(props.get("core_pain", "")))
        pain_points = ensure_list_of_text(props.get("pain_points"), ["No pain points provided."])
        cost_of_inaction = html.escape(str(props.get("cost_of_inaction", "")))
        return f"""
        <section class=\"module\" data-module=\"{module_id}\">
          <article class=\"panel panel-check\">
            <h2>{title}</h2>
            <p class=\"problem\">{core_pain}</p>
            <ul>
              {render_list_items(pain_points)}
            </ul>
            <p class=\"muted\">{cost_of_inaction}</p>
          </article>
        </section>
        """

    if module_id == "benefit_bullets":
        title = html.escape(str(props.get("title", "What improves")))
        items = ensure_list_of_text(props.get("items"), ["No benefit bullets provided."])
        return f"""
        <section class=\"module\" data-module=\"{module_id}\">
          <article class=\"panel panel-proof\">
            <h2>{title}</h2>
            <ul>
              {render_list_items(items)}
            </ul>
          </article>
        </section>
        """

    if module_id == "social_proof_strip":
        title = html.escape(str(props.get("title", "Trust signals")))
        items = ensure_list_of_text(props.get("items"), ["No trust signals provided."])
        chips = "".join([f"<li>{html.escape(item)}</li>" for item in items])
        return f"""
        <section class=\"module\" data-module=\"{module_id}\">
          <article class=\"panel\">
            <h2>{title}</h2>
            <ul class=\"proof-strip\">{chips}</ul>
          </article>
        </section>
        """

    if module_id in {"proof_points", "evidence_checklist", "risk_guardrails"}:
        title = html.escape(str(props.get("title", "Checklist")))
        items = ensure_list_of_text(props.get("items"), ["No items provided."])
        style = "proof" if module_id == "proof_points" else "check"
        return f"""
        <section class=\"module\" data-module=\"{module_id}\">
          <article class=\"panel panel-{style}\">
            <h2>{title}</h2>
            <ul>
              {render_list_items(items)}
            </ul>
          </article>
        </section>
        """

    if module_id == "metric_snapshot":
        title = html.escape(str(props.get("title", "Metric snapshot")))
        metric = html.escape(str(props.get("metric", "Success metric")))
        target = html.escape(str(props.get("target", "Target")))
        return f"""
        <section class=\"module\" data-module=\"{module_id}\">
          <article class=\"panel\">
            <h2>{title}</h2>
            <p class=\"metric\">{metric}</p>
            <p>{target}</p>
          </article>
        </section>
        """

    if module_id == "pricing_cards":
        title = html.escape(str(props.get("title", "Pricing hypothesis")))
        plan_a = html.escape(str(props.get("plan_a", "$19/month")))
        plan_b = html.escape(str(props.get("plan_b", "$79/month")))
        return f"""
        <section class=\"module\" data-module=\"{module_id}\">
          <article class=\"panel\">
            <h2>{title}</h2>
            <div class=\"plans\">
              <div class=\"plan\"><span>Plan A</span><strong>{plan_a}</strong></div>
              <div class=\"plan\"><span>Plan B</span><strong>{plan_b}</strong></div>
            </div>
          </article>
        </section>
        """

    if module_id == "cta_waitlist":
        title = html.escape(str(props.get("title", "Join pilot")))
        description = html.escape(str(props.get("description", "Get early access.")))
        cta_label = html.escape(str(props.get("cta_label", "Join pilot")))
        email_label = html.escape(str(props.get("email_label", "Work email")))
        email_placeholder = html.escape(str(props.get("email_placeholder", "you@company.com")))
        return f"""
        <section class=\"module\" data-module=\"{module_id}\">
          <article class=\"panel panel-cta\">
            <h2>{title}</h2>
            <p>{description}</p>
            <form id=\"signup-form\">
              <label for=\"email\">{email_label}</label>
              <input id=\"email\" name=\"email\" type=\"email\" placeholder=\"{email_placeholder}\" required />
              <button type=\"submit\" data-primary-cta=\"true\">{cta_label}</button>
            </form>
            <p id=\"signup-result\" aria-live=\"polite\"></p>
          </article>
        </section>
        """

    if module_id == "faq_list":
        title = html.escape(str(props.get("title", "FAQ")))
        faq_items = props.get("items", []) if isinstance(props.get("items"), list) else []
        rendered = []
        for item in faq_items:
            if not isinstance(item, dict):
                continue
            q = html.escape(str(item.get("question", "")))
            a = html.escape(str(item.get("answer", "")))
            if q and a:
                rendered.append(f"<details><summary>{q}</summary><p>{a}</p></details>")
        fallback = "<p class=\"muted\">No FAQ items provided.</p>"
        faq_html = "\n".join(rendered) if rendered else fallback
        return f"""
        <section class=\"module\" data-module=\"{module_id}\">
          <article class=\"panel\">
            <h2>{title}</h2>
            <div class=\"faq\">{faq_html}</div>
          </article>
        </section>
        """

    return f"""
    <section class=\"module\" data-module=\"{html.escape(module_id)}\">
      <article class=\"panel\">
        <h2>Unsupported module</h2>
        <p class=\"muted\">Module <code>{html.escape(module_id)}</code> is not yet implemented.</p>
      </article>
    </section>
    """


def render_index_html_from_page_spec(page_spec: Dict[str, Any]) -> str:
    meta = page_spec.get("meta", {}) if isinstance(page_spec.get("meta"), dict) else {}
    title = html.escape(str(meta.get("title", "Simple web product")))
    desc = html.escape(str(meta.get("description", "")))
    page_mode = html.escape(str(meta.get("page_mode", "web_product")))
    modules = page_spec.get("modules", []) if isinstance(page_spec.get("modules"), list) else []
    module_html_blocks = "\n".join(module_html(m, page_mode=page_mode) for m in modules if isinstance(m, dict))

    return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>{title}</title>
    <meta name=\"description\" content=\"{desc}\" />
    <link rel=\"stylesheet\" href=\"/styles.css\" />
  </head>
  <body>
    <main class=\"site\" data-page-mode=\"{page_mode}\">
      {module_html_blocks}
    </main>

    <script src=\"/app.js\" type=\"module\"></script>
  </body>
</html>
"""


def render_index_html(spec: Dict[str, Any]) -> str:
    segment = spec.get("segment", {}) if isinstance(spec.get("segment"), dict) else {}
    offer = spec.get("offer", {}) if isinstance(spec.get("offer"), dict) else {}
    workflow = spec.get("workflow", {}) if isinstance(spec.get("workflow"), dict) else {}
    metrics = spec.get("metrics", {}) if isinstance(spec.get("metrics"), dict) else {}
    pricing = spec.get("pricing", {}) if isinstance(spec.get("pricing"), dict) else {}
    adapter = spec.get("adapter", {}) if isinstance(spec.get("adapter"), dict) else {}

    title = html.escape(str(offer.get("headline", spec.get("value_proposition", "Simple web product"))))
    role = html.escape(str(segment.get("role", "Target operator")))
    industry = html.escape(str(segment.get("industry", "Business operations")))
    company_size = html.escape(str(segment.get("company_size", "1-20")))
    problem = html.escape(str(spec.get("problem_statement", "Problem statement missing.")))

    prompt_label = html.escape(str(workflow.get("prompt_label", "Describe your situation")))
    prompt_placeholder = html.escape(str(workflow.get("prompt_placeholder", "Describe your bottleneck...")))
    action_label = html.escape(str(workflow.get("primary_action_label", "Generate first step")))
    cta_label = html.escape(str(offer.get("cta_label", "Join pilot")))

    kill_criteria = ensure_list_of_text(metrics.get("kill_criteria"), ["Insufficient signal"])
    kill_html = "\n".join(f"<li>{html.escape(item)}</li>" for item in kill_criteria)

    metric = html.escape(str(metrics.get("success_metric", "Success metric")))
    target = html.escape(str(metrics.get("target", "Target")))

    plan_a = html.escape(str(pricing.get("plan_a", "$19/month")))
    plan_b = html.escape(str(pricing.get("plan_b", "$79/month")))
    adapter_name = html.escape(str(adapter.get("display_name", adapter.get("name", "Unknown adapter"))))

    return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>{title}</title>
    <link rel=\"stylesheet\" href=\"/styles.css\" />
  </head>
  <body>
    <main class=\"container\">
      <section class=\"hero\">
        <h1>{title}</h1>
        <p class=\"muted\"><strong>For:</strong> {role} · {industry} · {company_size}</p>
        <p>{problem}</p>
        <p class=\"muted\"><strong>Adapter:</strong> {adapter_name}</p>
      </section>

      <section class=\"grid\">
        <article class=\"card\">
          <h2>Core Workflow</h2>
          <form id=\"workflow-form\">
            <label for=\"input\">{prompt_label}</label>
            <textarea id=\"input\" name=\"input\" placeholder=\"{prompt_placeholder}\" required></textarea>
            <button type=\"submit\">{action_label}</button>
          </form>
          <pre id=\"workflow-result\" aria-live=\"polite\"></pre>
        </article>

        <article class=\"card\">
          <h2>Intent Capture</h2>
          <p>Use this CTA to collect early customer intent.</p>
          <form id=\"signup-form\">
            <label for=\"email\">Work email</label>
            <input id=\"email\" name=\"email\" type=\"email\" placeholder=\"you@company.com\" required />
            <button type=\"submit\">{cta_label}</button>
          </form>
          <p id=\"signup-result\" aria-live=\"polite\"></p>
        </article>
      </section>

      <section class=\"grid\">
        <article class=\"card\">
          <h2>Success Metric</h2>
          <p><strong>{metric}</strong></p>
          <p>{target}</p>
          <p class=\"muted\">Pricing hypothesis: {plan_a} / {plan_b}</p>
        </article>

        <article class=\"card\">
          <h2>Kill Criteria</h2>
          <ul>
            {kill_html}
          </ul>
        </article>
      </section>
    </main>

    <script src=\"/app.js\" type=\"module\"></script>
  </body>
</html>
"""


def render_styles_css(theme: Dict[str, Any] | None = None) -> str:
    theme = theme or {}
    accent = str(theme.get("accent", "#2563eb"))
    surface = str(theme.get("surface", "#111827"))
    highlight = str(theme.get("highlight", "#60a5fa"))

    return textwrap.dedent(
        f"""
        :root {{
          color-scheme: light;
          --bg: #f3f5fb;
          --ink: #0f172a;
          --muted: #475569;
          --line: #dbe3f0;
          --panel: #ffffff;
          --accent: {accent};
          --surface: {surface};
          --highlight: {highlight};
        }}

        * {{ box-sizing: border-box; }}

        body {{
          margin: 0;
          background: radial-gradient(circle at 15% 10%, rgba(96, 165, 250, 0.15), transparent 38%), var(--bg);
          color: var(--ink);
          font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
          line-height: 1.55;
        }}

        .site {{
          max-width: 980px;
          margin: 0 auto;
          padding: 28px 16px 48px;
          display: grid;
          gap: 14px;
        }}

        .module {{
          width: 100%;
        }}

        .hero .hero-shell {{
          background: linear-gradient(130deg, var(--surface), color-mix(in srgb, var(--surface) 75%, #000 25%));
          color: #e2e8f0;
          border-radius: 18px;
          padding: 24px 22px;
          border: 1px solid color-mix(in srgb, var(--highlight) 30%, #334155 70%);
          box-shadow: 0 10px 24px rgba(15, 23, 42, 0.24);
        }}

        .hero h1 {{
          margin: 0;
          font-size: clamp(1.55rem, 2.4vw, 2.1rem);
          line-height: 1.18;
          letter-spacing: -0.01em;
        }}

        .eyebrow {{
          margin: 0 0 8px;
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.12em;
          color: color-mix(in srgb, var(--highlight) 70%, #fff 30%);
          font-weight: 700;
        }}

        .lede {{
          margin: 10px 0 10px;
          color: #dbeafe;
          max-width: 72ch;
        }}

        .problem {{
          margin: 0 0 8px;
          color: #e2e8f0;
          font-weight: 520;
        }}

        .panel .problem {{
          color: #0f172a;
          font-weight: 600;
        }}

        .meta {{
          margin: 6px 0 0;
          color: #cbd5e1;
          font-size: 0.92rem;
        }}

        .panel {{
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 14px;
          padding: 16px;
          box-shadow: 0 3px 10px rgba(15, 23, 42, 0.05);
        }}

        .panel h2 {{
          margin-top: 0;
          margin-bottom: 10px;
          font-size: 1.08rem;
        }}

        .panel ul {{
          margin: 0;
          padding-left: 18px;
          display: grid;
          gap: 6px;
        }}

        .panel-proof {{ border-left: 4px solid color-mix(in srgb, var(--accent) 60%, #94a3b8 40%); }}
        .panel-check {{ border-left: 4px solid color-mix(in srgb, var(--highlight) 55%, #94a3b8 45%); }}
        .panel-cta {{ border-left: 4px solid color-mix(in srgb, var(--accent) 75%, #64748b 25%); }}

        .proof-strip {{
          list-style: none;
          margin: 0;
          padding: 0;
          display: grid;
          gap: 8px;
        }}

        .proof-strip li {{
          border: 1px solid var(--line);
          border-radius: 999px;
          padding: 6px 10px;
          font-size: 0.9rem;
          background: linear-gradient(180deg, #ffffff, #f8fbff);
        }}

        .metric {{
          font-weight: 700;
          font-size: 1.03rem;
          margin-bottom: 6px;
        }}

        .plans {{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 10px;
        }}

        .plan {{
          border: 1px solid var(--line);
          border-radius: 12px;
          padding: 12px;
          background: linear-gradient(180deg, #fff, #f8fbff);
        }}

        .plan span {{
          color: var(--muted);
          display: block;
          font-size: 0.78rem;
          text-transform: uppercase;
          letter-spacing: .08em;
          margin-bottom: 6px;
        }}

        .plan strong {{
          font-size: 1.05rem;
        }}

        label {{
          display: block;
          margin-bottom: 6px;
          color: var(--muted);
          font-size: 0.9rem;
          font-weight: 600;
        }}

        textarea,
        input {{
          width: 100%;
          border: 1px solid var(--line);
          border-radius: 10px;
          padding: 11px 12px;
          font-size: 14px;
          margin-bottom: 10px;
          background: #fff;
        }}

        textarea {{ min-height: 108px; resize: vertical; }}

        button {{
          appearance: none;
          border: 0;
          border-radius: 10px;
          background: var(--accent);
          color: white;
          padding: 10px 14px;
          font-size: 14px;
          font-weight: 700;
          cursor: pointer;
          transition: transform .08s ease, filter .15s ease;
        }}

        button:hover {{ filter: brightness(1.05); transform: translateY(-1px); }}

        pre {{
          white-space: pre-wrap;
          background: #0b1020;
          color: #d1d5db;
          border-radius: 10px;
          padding: 10px;
          min-height: 84px;
          font-size: 13px;
          margin-bottom: 0;
        }}

        .faq {{ display: grid; gap: 8px; }}
        details {{ border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; background: #fff; }}
        summary {{ cursor: pointer; font-weight: 600; }}
        details p {{ margin: 8px 0 2px; color: var(--muted); }}

        .muted {{ color: var(--muted); }}

        img {{
          max-width: 100%;
          height: auto;
          display: block;
        }}

        @media (max-width: 768px) {{
          .site {{
            padding: 18px 12px 32px;
            gap: 12px;
          }}

          .hero .hero-shell {{
            padding: 18px 16px;
            border-radius: 14px;
          }}

          .panel {{
            padding: 14px;
          }}

          button {{
            width: 100%;
          }}
        }}

        @media (min-width: 1024px) {{
          .site {{
            padding-top: 34px;
          }}

          .panel {{
            padding: 18px;
          }}
        }}
        """
    ).strip() + "\n"


def render_app_js() -> str:
    return textwrap.dedent(
        """
        const workflowForm = document.getElementById("workflow-form");
        const workflowResult = document.getElementById("workflow-result");
        const signupForm = document.getElementById("signup-form");
        const signupResult = document.getElementById("signup-result");

        workflowForm?.addEventListener("submit", async (event) => {
          event.preventDefault();
          workflowResult.textContent = "Generating first step...";

          const input = document.getElementById("input")?.value?.trim() || "";
          if (input.length < 8) {
            workflowResult.textContent = "Please provide a bit more detail so the workflow can route correctly.";
            return;
          }

          try {
            const response = await fetch("/api/first-step", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ input }),
            });

            const data = await response.json();
            if (!response.ok) {
              workflowResult.textContent = data?.error || "Failed to generate first step.";
              return;
            }

            const lines = [
              `First step: ${data.first_step}`,
              "",
              `Matched rule: ${data.rule_id || "default"}`,
              "",
              "Next steps:",
              ...(data.next_steps || []).map((item, idx) => `${idx + 1}. ${item}`),
            ];
            workflowResult.textContent = lines.join("\\n");
          } catch (error) {
            workflowResult.textContent = `Error: ${error.message}`;
          }
        });

        signupForm?.addEventListener("submit", async (event) => {
          event.preventDefault();
          signupResult.textContent = "Submitting...";

          const email = document.getElementById("email")?.value?.trim() || "";
          try {
            const response = await fetch("/api/signup", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ email, source: "web-cta" }),
            });
            const data = await response.json();

            if (!response.ok) {
              signupResult.textContent = data?.error || "Could not submit.";
              return;
            }

            signupResult.textContent = data.message || "Thanks, you're on the pilot list.";
          } catch (error) {
            signupResult.textContent = `Error: ${error.message}`;
          }
        });
        """
    ).strip() + "\n"


def js_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def render_health_js(project_id: str, opportunity_id: str, adapter_name: str) -> str:
    return textwrap.dedent(
        f"""
        module.exports = (req, res) => {{
          res.status(200).json({{
            status: "ok",
            service: "op1-product-web-build-deploy-v1.1",
            project_id: {json.dumps(project_id)},
            from_opportunity_id: {json.dumps(opportunity_id)},
            adapter: {json.dumps(adapter_name)},
            timestamp: new Date().toISOString()
          }});
        }};
        """
    ).strip() + "\n"


def render_first_step_js(spec: Dict[str, Any]) -> str:
    payload = {
        "project_id": spec.get("project_id"),
        "problem_statement": spec.get("problem_statement"),
        "value_proposition": spec.get("value_proposition"),
        "adapter": spec.get("adapter", {}).get("name") if isinstance(spec.get("adapter"), dict) else "unknown",
        "rules": nested_get(spec, ("workflow", "rules")) or [],
        "default_response": nested_get(spec, ("workflow", "default_response")) or {
            "first_step": "Map workflow and automate highest-friction step.",
            "next_steps": ["Instrument one metric", "Run 14-day test", "Review outcomes"],
        },
        "metrics": spec.get("metrics", {}),
    }

    return textwrap.dedent(
        f"""
        const PRODUCT_SPEC = {js_json(payload)};

        function parseBody(req) {{
          if (!req.body) return {{}};
          if (typeof req.body === "object") return req.body;
          try {{ return JSON.parse(req.body); }} catch (e) {{ return {{}}; }}
        }}

        function keywordScore(rule, normalizedInput) {{
          const keywords = Array.isArray(rule.keywords) ? rule.keywords : [];
          let hits = 0;
          for (const kw of keywords) {{
            const token = String(kw || "").toLowerCase().trim();
            if (!token) continue;
            if (normalizedInput.includes(token)) hits += 1;
          }}
          const priority = Number(rule.priority || 0);
          return hits + (priority / 100);
        }}

        function chooseRule(input) {{
          const normalized = String(input || "").toLowerCase();
          const rules = Array.isArray(PRODUCT_SPEC.rules) ? PRODUCT_SPEC.rules : [];
          let bestRule = null;
          let bestScore = 0;

          for (const rule of rules) {{
            const score = keywordScore(rule, normalized);
            if (score > bestScore) {{
              bestRule = rule;
              bestScore = score;
            }}
          }}

          return bestScore > 0 ? bestRule : null;
        }}

        module.exports = (req, res) => {{
          if (req.method !== "POST") {{
            res.status(405).json({{ error: "Method not allowed" }});
            return;
          }}

          const body = parseBody(req);
          const input = String(body.input || "").trim();
          if (!input || input.length < 8) {{
            res.status(400).json({{ error: "input is required (min 8 chars)" }});
            return;
          }}
          if (input.length > 2000) {{
            res.status(400).json({{ error: "input is too long (max 2000 chars)" }});
            return;
          }}

          const matched = chooseRule(input);
          const defaultResponse = PRODUCT_SPEC.default_response || {{}};
          const firstStep = matched?.first_step || defaultResponse.first_step || "Define one focused first step.";
          const nextSteps = Array.isArray(matched?.next_steps) && matched.next_steps.length > 0
            ? matched.next_steps
            : (Array.isArray(defaultResponse.next_steps) ? defaultResponse.next_steps : []);

          res.status(200).json({{
            first_step: firstStep,
            next_steps: nextSteps,
            rule_id: matched?.id || "default",
            context: {{
              project_id: PRODUCT_SPEC.project_id,
              adapter: PRODUCT_SPEC.adapter,
              metric: PRODUCT_SPEC.metrics?.success_metric || null,
              target: PRODUCT_SPEC.metrics?.target || null
            }}
          }});
        }};
        """
    ).strip() + "\n"


def render_signup_js(project_id: str, cta_label: str) -> str:
    return textwrap.dedent(
        f"""
        function parseBody(req) {{
          if (!req.body) return {{}};
          if (typeof req.body === "object") return req.body;
          try {{ return JSON.parse(req.body); }} catch (e) {{ return {{}}; }}
        }}

        function isValidEmail(email) {{
          return /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email);
        }}

        module.exports = (req, res) => {{
          if (req.method !== "POST") {{
            res.status(405).json({{ error: "Method not allowed" }});
            return;
          }}

          const body = parseBody(req);
          const email = String(body.email || "").trim().toLowerCase();
          if (!email || email.length > 254 || !isValidEmail(email)) {{
            res.status(400).json({{ error: "Valid email is required" }});
            return;
          }}

          res.status(200).json({{
            accepted: true,
            project_id: {json.dumps(project_id)},
            message: "{cta_label} confirmed. You're on the early-access list."
          }});
        }};
        """
    ).strip() + "\n"


def render_spec_js(spec: Dict[str, Any]) -> str:
    response_payload = {
        "project_id": spec.get("project_id"),
        "adapter": spec.get("adapter", {}),
        "source": spec.get("source", {}),
        "metrics": spec.get("metrics", {}),
    }

    return textwrap.dedent(
        f"""
        module.exports = (req, res) => {{
          res.status(200).json({js_json(response_payload)});
        }};
        """
    ).strip() + "\n"


def render_package_json(app_name: str) -> str:
    payload = {
        "name": app_name,
        "version": "0.2.0",
        "private": True,
        "description": "Adapter-driven scaffold for Build & Deploy simple web products",
        "scripts": {
            "start": "echo 'Use vercel dev for local development'",
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def render_vercel_json() -> str:
    payload = {
        "$schema": "https://openapi.vercel.sh/vercel.json",
        "cleanUrls": True,
        "headers": [
            {
                "source": "/(.*)",
                "headers": [
                    {"key": "X-Content-Type-Options", "value": "nosniff"},
                    {"key": "X-Frame-Options", "value": "DENY"},
                    {"key": "Referrer-Policy", "value": "strict-origin-when-cross-origin"},
                    {
                        "key": "Content-Security-Policy",
                        "value": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
                    },
                    {
                        "key": "Permissions-Policy",
                        "value": "camera=(), microphone=(), geolocation=()",
                    },
                ],
            }
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scaffold a web product from project spec")
    parser.add_argument("--project-spec", required=False, help="Path to build/deploy project spec JSON")
    parser.add_argument("--page-spec", required=False, help="Path to compiled modular page spec JSON")
    parser.add_argument("--blueprint", required=False, help="Path to stage3 blueprint JSON (legacy)")
    parser.add_argument("--fallback-stage1", required=False, help="Fallback stage1 JSON for blueprint autofill")
    parser.add_argument("--fallback-stage2", required=False, help="Fallback stage2 JSON for blueprint autofill")
    parser.add_argument("--allow-blueprint-autofill", action="store_true", help="Allow blueprint autofill from stage1/stage2")
    parser.add_argument("--autofill-opportunity-id", required=False, help="Optional opportunity id for blueprint autofill")
    parser.add_argument("--out-dir", required=True, help="Output app directory")
    parser.add_argument("--summary-out", required=False, help="Optional scaffold summary JSON path")
    parser.add_argument("--force", action="store_true", help="Overwrite out-dir")
    return parser.parse_args()


def resolve_project_spec(args: argparse.Namespace) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if not args.project_spec and not args.blueprint:
        raise ValueError("Provide --project-spec (preferred) or --blueprint (legacy).")

    debug: Dict[str, Any] = {
        "mode": None,
        "project_spec_source": None,
        "blueprint_source": None,
        "blueprint_autofilled": False,
    }

    if args.project_spec:
        project_spec_path = pathlib.Path(args.project_spec).resolve()
        if not project_spec_path.exists():
            raise FileNotFoundError(f"Project spec not found: {project_spec_path}")
        spec = read_json(project_spec_path)
        missing = validate_project_spec(spec)
        if missing:
            raise ValueError("Project spec missing required fields: " + ", ".join(missing))

        debug["mode"] = "project_spec"
        debug["project_spec_source"] = str(project_spec_path)
        return spec, debug

    blueprint_path = pathlib.Path(args.blueprint).resolve()
    if not blueprint_path.exists():
        raise FileNotFoundError(f"Blueprint not found: {blueprint_path}")

    blueprint = read_json(blueprint_path)
    missing = missing_fields(blueprint, BLUEPRINT_REQUIRED_TEXT_PATHS, BLUEPRINT_REQUIRED_LIST_PATHS)

    if missing:
        if not args.allow_blueprint_autofill:
            raise ValueError("Blueprint missing required fields: " + ", ".join(missing))

        if not args.fallback_stage1 or not args.fallback_stage2:
            raise ValueError(
                "Blueprint autofill requires --fallback-stage1 and --fallback-stage2"
            )

        stage1 = read_json(pathlib.Path(args.fallback_stage1).resolve())
        stage2 = read_json(pathlib.Path(args.fallback_stage2).resolve())
        blueprint = build_autofilled_blueprint(stage1, stage2, args.autofill_opportunity_id)
        missing_after = missing_fields(blueprint, BLUEPRINT_REQUIRED_TEXT_PATHS, BLUEPRINT_REQUIRED_LIST_PATHS)
        if missing_after:
            raise ValueError("Autofilled blueprint still missing fields: " + ", ".join(missing_after))
        debug["blueprint_autofilled"] = True

    spec = project_spec_from_blueprint(blueprint)
    missing_spec = validate_project_spec(spec)
    if missing_spec:
        raise ValueError("Converted project spec missing required fields: " + ", ".join(missing_spec))

    debug["mode"] = "blueprint_legacy"
    debug["blueprint_source"] = str(blueprint_path)
    return spec, debug


def default_page_spec_from_project_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    adapter = spec.get("adapter", {}) if isinstance(spec.get("adapter"), dict) else {}
    offer = spec.get("offer", {}) if isinstance(spec.get("offer"), dict) else {}
    workflow = spec.get("workflow", {}) if isinstance(spec.get("workflow"), dict) else {}
    metrics = spec.get("metrics", {}) if isinstance(spec.get("metrics"), dict) else {}
    pricing = spec.get("pricing", {}) if isinstance(spec.get("pricing"), dict) else {}

    modules = [
        {
            "module_id": "hero_problem",
            "kind": "hero",
            "props": {
                "headline": offer.get("headline", spec.get("value_proposition", "Focused workflow")),
                "subheadline": spec.get("value_proposition", "Validate one business workflow quickly."),
                "problem_statement": spec.get("problem_statement", "Problem statement missing."),
                "segment_label": " · ".join(
                    [
                        str((spec.get("segment") or {}).get("role", "Target operator")),
                        str((spec.get("segment") or {}).get("industry", "Business operations")),
                        str((spec.get("segment") or {}).get("company_size", "1-20")),
                    ]
                ),
                "adapter_name": adapter.get("display_name", adapter.get("name", "Unknown adapter")),
                "profile_name": spec.get("page_profile", "default"),
            },
        },
        {
            "module_id": "workflow_interactive",
            "kind": "workflow",
            "props": {
                "title": "Try the workflow assistant",
                "prompt_label": workflow.get("prompt_label", "Describe your bottleneck"),
                "prompt_placeholder": workflow.get("prompt_placeholder", "Describe your bottleneck..."),
                "action_label": workflow.get("primary_action_label", "Generate first step"),
            },
        },
        {
            "module_id": "proof_points",
            "kind": "proof",
            "props": {
                "title": "Why this approach",
                "items": ensure_list_of_text(
                    spec.get("proof_points"),
                    [
                        "Focused workflow built for measurable validation.",
                        "Adapter rules route cases by real operational intent.",
                        "Deployment and tests are reproducible and auditable.",
                    ],
                ),
            },
        },
        {
            "module_id": "metric_snapshot",
            "kind": "metric",
            "props": {
                "title": "Validation target",
                "metric": metrics.get("success_metric", "Qualified intent captures"),
                "target": metrics.get("target", "Define measurable target"),
            },
        },
        {
            "module_id": "pricing_cards",
            "kind": "pricing",
            "props": {
                "title": "Pricing hypothesis",
                "plan_a": pricing.get("plan_a", "$19/month"),
                "plan_b": pricing.get("plan_b", "$79/month"),
            },
        },
        {
            "module_id": "risk_guardrails",
            "kind": "risk",
            "props": {
                "title": "Guardrails",
                "items": ensure_list_of_text(metrics.get("kill_criteria"), ["Insufficient signal"]),
            },
        },
        {
            "module_id": "cta_waitlist",
            "kind": "cta",
            "props": {
                "title": "Start with one pilot workflow",
                "description": spec.get("cta_support_text", "Join early access and validate with real users."),
                "cta_label": offer.get("cta_label", "Join pilot"),
                "email_label": "Work email",
                "email_placeholder": "you@company.com",
            },
        },
    ]

    faq = spec.get("faq", []) if isinstance(spec.get("faq"), list) else []
    if faq:
        modules.append({
            "module_id": "faq_list",
            "kind": "faq",
            "props": {
                "title": "FAQ",
                "items": faq,
            },
        })

    return {
        "page_spec_version": "1.0",
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "project_id": spec.get("project_id"),
        "adapter_name": adapter.get("name", "generic-operator"),
        "layout_profile": spec.get("page_profile", "default"),
        "theme": {
            "accent": "#2563eb",
            "surface": "#111827",
            "highlight": "#60a5fa",
        },
        "meta": {
            "title": offer.get("headline", spec.get("value_proposition", "Simple web product")),
            "description": str(spec.get("problem_statement", ""))[:180],
        },
        "modules": modules,
        "testing": {
            "expected_modules": [m.get("module_id") for m in modules],
            "primary_cta_module": "cta_waitlist",
            "max_primary_cta_buttons": 1,
            "require_viewport_meta": True,
            "responsive_markers": ["@media", "max-width", "min-width"],
            "device_profiles": [
                {"id": "mobile", "width": 390, "height": 844},
                {"id": "tablet", "width": 768, "height": 1024},
                {"id": "desktop", "width": 1440, "height": 900}
            ],
            "performance_budget": {
                "lcp_ms": 2500,
                "inp_ms": 200,
                "cls_max": 0.1
            },
            "security_headers": [
                {"name": "x-content-type-options", "must_include": "nosniff"},
                {"name": "x-frame-options", "must_include": "DENY"},
                {"name": "referrer-policy", "must_include": "strict-origin-when-cross-origin"},
                {"name": "content-security-policy", "must_include": "default-src 'self'"}
            ]
        },
    }


def resolve_page_spec(args: argparse.Namespace, spec: Dict[str, Any], debug: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if args.page_spec:
        page_spec_path = pathlib.Path(args.page_spec).resolve()
        if not page_spec_path.exists():
            raise FileNotFoundError(f"Page spec not found: {page_spec_path}")
        page_spec = read_json(page_spec_path)
        missing = validate_page_spec(page_spec)
        if missing:
            raise ValueError("Page spec missing required fields: " + ", ".join(missing))
        debug["page_spec_source"] = str(page_spec_path)
        debug["page_spec_mode"] = "compiled"
        return page_spec, debug

    page_spec = default_page_spec_from_project_spec(spec)
    missing = validate_page_spec(page_spec)
    if missing:
        raise ValueError("Default page spec missing required fields: " + ", ".join(missing))
    debug["page_spec_source"] = "generated_in_scaffold"
    debug["page_spec_mode"] = "generated"
    return page_spec, debug


def main() -> int:
    args = parse_args()
    out_dir = pathlib.Path(args.out_dir).resolve()

    spec, debug = resolve_project_spec(args)
    page_spec, debug = resolve_page_spec(args, spec, debug)

    if out_dir.exists():
        if not args.force:
            raise FileExistsError(f"Output directory exists: {out_dir}. Use --force to overwrite.")
        shutil.rmtree(out_dir)

    (out_dir / "public").mkdir(parents=True, exist_ok=True)
    (out_dir / "api").mkdir(parents=True, exist_ok=True)

    project_id = str(spec.get("project_id", "proj-web-v1"))
    opportunity_id = str(nested_get(spec, ("source", "opportunity_id")) or "opp-unknown")
    adapter_name = str(nested_get(spec, ("adapter", "name")) or "generic-operator")
    cta_label = str(nested_get(spec, ("offer", "cta_label")) or "Join pilot")
    app_name = sanitize_slug(project_id)

    theme = page_spec.get("theme", {}) if isinstance(page_spec.get("theme"), dict) else {}
    write_file(out_dir / "public" / "index.html", render_index_html_from_page_spec(page_spec))
    write_file(out_dir / "public" / "styles.css", render_styles_css(theme))
    write_file(out_dir / "public" / "app.js", render_app_js())
    write_file(out_dir / "api" / "health.js", render_health_js(project_id, opportunity_id, adapter_name))
    write_file(out_dir / "api" / "first-step.js", render_first_step_js(spec))
    write_file(out_dir / "api" / "signup.js", render_signup_js(project_id, cta_label))
    write_file(out_dir / "api" / "spec.js", render_spec_js(spec))
    write_file(out_dir / "package.json", render_package_json(app_name))
    write_file(out_dir / "vercel.json", render_vercel_json())
    write_file(out_dir / "project_spec.snapshot.json", json.dumps(spec, ensure_ascii=False, indent=2) + "\n")
    write_file(out_dir / "page_spec.snapshot.json", json.dumps(page_spec, ensure_ascii=False, indent=2) + "\n")

    module_ids = [
        str(m.get("module_id"))
        for m in page_spec.get("modules", [])
        if isinstance(m, dict) and is_non_empty_text(m.get("module_id"))
    ]

    scaffold_meta = {
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "mode": debug.get("mode"),
        "project_spec_source": debug.get("project_spec_source"),
        "page_spec_source": debug.get("page_spec_source"),
        "page_spec_mode": debug.get("page_spec_mode"),
        "blueprint_source": debug.get("blueprint_source"),
        "blueprint_autofilled": bool(debug.get("blueprint_autofilled", False)),
        "project_id": project_id,
        "from_opportunity_id": opportunity_id,
        "adapter_name": adapter_name,
        "layout_profile": page_spec.get("layout_profile"),
        "module_order": module_ids,
        "app_dir": str(out_dir),
        "public_files": [
            "public/index.html",
            "public/styles.css",
            "public/app.js",
        ],
        "api_files": [
            "api/health.js",
            "api/first-step.js",
            "api/signup.js",
            "api/spec.js",
        ],
    }

    write_file(out_dir / "scaffold_meta.json", json.dumps(scaffold_meta, ensure_ascii=False, indent=2) + "\n")

    if args.summary_out:
        summary_path = pathlib.Path(args.summary_out).resolve()
        write_file(summary_path, json.dumps(scaffold_meta, ensure_ascii=False, indent=2) + "\n")

    print(json.dumps(scaffold_meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
