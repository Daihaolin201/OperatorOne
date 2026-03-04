# op1_marketing — Marketing Agent

## Capabilities
- Run SEO experiments
- Publish content
- Launch campaigns

## Stage 1 status
Stage 1 (Run SEO experiments) is implemented as a continuous shadow pipeline.

Run once:
```bash
./scripts/run_marketing_seo_stage1.sh
```

Run continuously:
```bash
./scripts/run_marketing_seo_stage1.sh --continuous --interval 300
```

Inputs are synced from `../op1_product/research/*` plus `../../handoffs/product_to_marketing.json`.
Outputs are written to `research/stage1_marketing_seo/`.

## Stage 2 status
Stage 2 (Publish content) is implemented for shadow/review workflows with quality gates.
Auto publish is intentionally disabled.

Run once:
```bash
./scripts/run_marketing_content_stage2.sh
```

Run continuously:
```bash
./scripts/run_marketing_content_stage2.sh --continuous --interval 300
```

Apply manual review decisions:
```bash
./scripts/review_marketing_content_stage2.sh --approve-all --note "editorial pass"
./scripts/review_marketing_content_stage2.sh --approve cnt_x --reject cnt_y --reason "tighten evidence"
```

Inputs are read from Stage1 outputs.
Outputs are written to `research/stage2_content_publish/`.
Sales handoff is updated at `../../handoffs/marketing_to_sales.json`.
