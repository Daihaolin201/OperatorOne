# Industry benchmark notes (Stage2 Process feedback)

Compiled during implementation to align capability design with common leading practices.

## Event-centric feedback data model
- PostHog docs emphasize event primitives (`event name`, `distinct_id`, `timestamp`, `properties`) as the core analytics unit.
- Stage2 mirrors this with canonical fields (`feedback_id`, `actor_id`, `feedback_time`, topic/subtopic, severity/urgency/confidence/evidence).

## Contextual collection + routing
- Sentry user feedback guidance stresses contextual prompts and routing tags for faster triage ownership.
- Stage2 includes source/channel tagging and owner assignment in closed-loop tracker.

## VoC program architecture
- Qualtrics VoC framing highlights continuous multi-source ingestion, trend detection, and acting on insights.
- Stage2 implements adapters + clustering + weighted queue + loop tracking.

## Prioritization rigor
- Intercom RICE model: prioritize by reach, impact, confidence, effort.
- Stage2 scoring uses a RICE-like core blended with severity/urgency/evidence weighting and explicit effort points.

## Feature class perspective
- Kano model distinguishes must-have/basic vs performance vs delighters.
- Stage2 annotates each item with Kano label to support roadmap conversation context.

## Feedback strategy guardrails
- Intercom guidance on feedback quality (avoid over-indexing on noisy/hypothetical signals) informed confidence/evidence weighting.
- Stage2 includes source reliability, lead-fit weighting, and dedupe/cluster controls.

## Closed-loop operating expectation
- Common CX/feedback playbooks stress closing the loop with owners, SLAs, and follow-through.
- Stage2 loop tracker models `new -> triaged -> accepted -> planned -> shipped -> verified -> notified` and measures triaged/closure rates.

## Loyalty-signal integration (NPS-style)
- SurveyMonkey NPS guidance emphasizes segmenting promoters/passives/detractors and acting on qualitative comments.
- Stage2 supports this pattern via sentiment + severity + topic/subtopic + evidence excerpts, enabling promoter/pain segmentation in future live adapters.
