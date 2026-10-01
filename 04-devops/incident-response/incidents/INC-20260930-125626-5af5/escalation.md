# Escalation packet: INC-20260930-125626-5af5

**Why a human is needed**: deploy-fix.sh failed (exit 3); nothing changed in production if exit 3

- Route: `/api/orders/{order_id}`
- Agent diagnosis: app/main.py order_detail: `placed_at.replace(day=placed_at.day + 2)` raises ValueError when day+2 exceeds the month length. It is a latent bug, triggered by the seed data (express-1002 has created_at set to the previous month's last day). It is not caused by a recent deploy. (confidence 0.97)
- Proposed action: patch

Start with `evidence/summary.md`, then `response.json` and `audit.jsonl`.
Fix branch (if any): `git branch --list 'incident/*'`.
