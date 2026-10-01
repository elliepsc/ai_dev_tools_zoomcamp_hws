# Escalation packet: INC-20260930-123438-47f5

**Why a human is needed**: verification failed after deploying 310c7b5; rolled back (exit 0)

- Route: `/api/orders/{order_id}`
- Agent diagnosis: drill: the patch below does not address the real cause (confidence 0.9)
- Proposed action: patch

Start with `evidence/summary.md`, then `response.json` and `audit.jsonl`.
Fix branch (if any): `git branch --list 'incident/*'`.
