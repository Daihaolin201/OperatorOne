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
