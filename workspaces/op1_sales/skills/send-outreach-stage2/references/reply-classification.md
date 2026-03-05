# Reply Classification Notes

## Classifier version
- Current: `stage2-reply-v2`

## Priority order
The classifier resolves conflicts in this order:
1. unsubscribe
2. converted
3. rejection (`not interested`, `no thanks`, `already use`, etc.)
4. not_now (timing hold)
5. objections (budget/security/integration/capacity/trust)
6. positive booked_call
7. positive interested
8. other

This ordering prevents `"not interested"` from being misread as `"interested"`.

## Validation script
Run before packaging or major edits:

```bash
python3 workspaces/op1_sales/skills/send-outreach-stage2/scripts/validate_stage2_reply_classifier.py
```

Expected result: `Stage2 reply classifier validation PASSED`
