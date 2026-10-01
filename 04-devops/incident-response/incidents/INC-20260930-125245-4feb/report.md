# Incident INC-20260930-125245-4feb

- **State**: escalated (I cannot edit in read_only mode. The alert is only a test notification, so a human or an edit-mode run should apply the one-line fix at app/main.py:81, replacing replace(day=day+2) with + timedelta(days=2). It also needs a date-independent regression test, for example an express order created on 2026-01-31 or 2026-09-30. Then replay GET /api/orders/express-1002.)
- **Opened**: 2026-09-30T12:52:45+00:00 | **closed/escalated**: 2026-09-30T12:53:08+00:00
- **Alert**: ResponderTest status=firing route=`None` labels=`{"alertname": "ResponderTest", "test": "true"}`
- **Summary (Grafana)**: Test notification; no incident to fix

## Agent
- Agent: claude-code | model: CLI default | mode: read_only | exit: 0 | duration: 22.2 s
- Models reported by the CLI: ['claude-haiku-4-5-20251001', 'claude-sonnet-5-5']
- Command: `claude -p --output-format stream-json --verbose --json-schema <schema: response.schema.json> --max-turns 40 --no-session-persistence --permission-mode default --allowedTools Read Glob Grep --disallowedTools WebFetch WebSearch Bash(docker:*) Bash(curl:*) Bash(wget:*) Bash(git commit:*) Bash(git push:*) Bash(git reset:*) Bash(rm:*) Bash(sudo:*) Read(./.env) Read(**/.env) Read(~/.ssh/**) Read(~/.aws/**) Read(~/.docker/**) --strict-mcp-config --mcp-config /home/claude/order-tracker/incident-response/agent-mcp.json --add-dir /home/claude/order-tracker/incident-response/incidents/INC-20260930-125245-4feb/evidence`

- Classification: **real_incident** (confidence 0.9)
- Proposed action: **escalate**
- User impact: Every request for an express order placed on the 29th, 30th or 31st (Feb: 27th or later) returns HTTP 500. Observed: 6 cumulative 500s on /api/orders/{order_id}, all for express-1002. Standard orders and /healthz are unaffected.
- Root cause: app/main.py:81 uses placed_at.replace(day=placed_at.day + 2) to estimate delivery. replace() raises ValueError when day+2 exceeds the month length. The fix is placed_at + timedelta(days=2), with timedelta imported from datetime if it isn't already.

### Evidence cited by the agent
- [alert] alert labels: alertname=ResponderTest, test=true, summary 'Test notification; no incident to fix'; no route in the alert.
- [metrics] cumulative_by_status: 6 x 500 with error_type=ValueError on /api/orders/{order_id}, versus 8 x 200. The 5xx are seen under service_version 8cb2b4f and b26220b, so the bug predates the latest commits.
- [logs] Loki ERROR lines 12:48:23 and 12:50:35: ValueError: day is out of range for month; traces f876ef66..., c8774e52..., 072f77ac..., 34ee7e04..., 6b350e91...
- [traces] trace c8774e52e877d30a94b5a1cdb55100a7: Span orders.build_detail fails with order.priority=express; the root span has order.id=express-1002 and status 500.
- [code] app/main.py:81: estimated_at = placed_at.replace(day=placed_at.day + 2), which overflows at month end (today is the 30th).

### Agent final message
```
The alert is a ResponderTest notification (test=true, no route), but the evidence shows a real, separate bug.
GET /api/orders/express-1002 returns 500 (ValueError: day is out of range for month). The cause is app/main.py:81, placed_at.replace(day=placed_at.day + 2), which fails for express orders placed on day 29 or later of a month (today is the 30th).
Suggested fix: use placed_at + timedelta(days=2), and add a date-independent regression test. I made no changes in read-only mode.
Verdict: test alert, but a real express-order 500 bug is present (app/main.py:81); escalating for a one-line fix.
```

## Policy decision
- Level 0 (observe): test notification, never touch code or runtime
- Allowed: True | outcome: **escalated**

## Commands executed by the responder (not by the model)
- none

Files: alert.json, evidence/, prompt.md, agent/, response.json, decision.json, fix.patch, tests.log, deploy.log, verify.log, audit.jsonl
