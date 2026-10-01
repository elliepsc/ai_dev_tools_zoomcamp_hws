# Escalation packet: INC-20260930-130646-e094

**Why a human is needed**: patch rejected by policy: agent_extension_surface_as_declared (unexpected mcp=['claude-in-chrome'] plugins=['cc-plugin-agents-md', 'cc-plugin-telemetry'] skills=0)

- Route: `/api/orders/{order_id}`
- Agent diagnosis: app/main.py:81 uses date.replace(day=day+2) for the delivery estimate instead of date arithmetic. It raises ValueError for any express order whose created_at day is greater than (days in month - 2). The seed data (init_db) deliberately creates express-1002 at the previous month end, which triggers it. (confidence 0.96)
- Proposed action: patch

Start with `evidence/summary.md`, then `response.json` and `audit.jsonl`.
Fix branch (if any): `git branch --list 'incident/*'`.
