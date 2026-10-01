# Escalation packet: INC-20260930-123549-5c01

**Why a human is needed**: patch rejected by policy: regression_test_fails_without_fix (suite without the code change failed = False)

- Route: `/api/orders/{order_id}`
- Agent diagnosis: drill: the patch below does not address the real cause (confidence 0.9)
- Proposed action: patch

Start with `evidence/summary.md`, then `response.json` and `audit.jsonl`.
Fix branch (if any): `git branch --list 'incident/*'`.
