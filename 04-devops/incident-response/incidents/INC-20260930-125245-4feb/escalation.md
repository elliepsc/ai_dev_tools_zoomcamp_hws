# Escalation packet: INC-20260930-125245-4feb

**Why a human is needed**: I cannot edit in read_only mode. The alert is only a test notification, so a human or an edit-mode run should apply the one-line fix at app/main.py:81, replacing replace(day=day+2) with + timedelta(days=2). It also needs a date-independent regression test, for example an express order created on 2026-01-31 or 2026-09-30. Then replay GET /api/orders/express-1002.

- Route: `None`
- Agent diagnosis: app/main.py:81 uses placed_at.replace(day=placed_at.day + 2) to estimate delivery. replace() raises ValueError when day+2 exceeds the month length. The fix is placed_at + timedelta(days=2), with timedelta imported from datetime if it isn't already. (confidence 0.9)
- Proposed action: escalate

Start with `evidence/summary.md`, then `response.json` and `audit.jsonl`.
Fix branch (if any): `git branch --list 'incident/*'`.
