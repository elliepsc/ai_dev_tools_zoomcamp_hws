# Incident INC-20260930-130646-e094

- **State**: escalated (patch rejected by policy: agent_extension_surface_as_declared (unexpected mcp=['claude-in-chrome'] plugins=['cc-plugin-agents-md', 'cc-plugin-telemetry'] skills=0))
- **Opened**: 2026-09-30T13:06:46+00:00 | **closed/escalated**: 2026-09-30T13:07:20+00:00
- **Alert**: OrderTracker5xx status=firing route=`/api/orders/{order_id}` labels=`{"alertname": "OrderTracker5xx", "grafana_folder": "Order Tracker Alerts", "http_route": "/api/orders/{order_id}", "service": "order-tracker", "severity": "critical", "team": "ops"}`
- **Summary (Grafana)**: Server errors (5xx) on /api/orders/{order_id}

## Agent
- Agent: claude-code | model: CLI default | mode: edit | exit: 0 | duration: 30.8 s
- Models reported by the CLI: ['claude-haiku-4-5-20251001', 'claude-sonnet-5-5']
- Command: `claude -p --output-format stream-json --verbose --json-schema <schema: response.schema.json> --max-turns 40 --no-session-persistence --permission-mode acceptEdits --allowedTools Read Glob Grep Edit Write Bash(uv run --frozen pytest:*) --disallowedTools WebFetch WebSearch Bash(docker:*) Bash(curl:*) Bash(wget:*) Bash(git commit:*) Bash(git push:*) Bash(git reset:*) Bash(rm:*) Bash(sudo:*) Read(./.env) Read(**/.env) Read(~/.ssh/**) Read(~/.aws/**) Read(~/.docker/**) --strict-mcp-config --mcp-config /home/claude/order-tracker/incident-response/agent-mcp.json --disable-slash-commands --setting-sources project --add-dir /home/claude/order-tracker/incident-response/incidents/INC-20260930-130646-e094/evidence`

- Classification: **real_incident** (confidence 0.96)
- Proposed action: **patch**
- User impact: Every detail lookup of an express order created on the 30th or 31st, or on Feb 27-28 and so on, returns HTTP 500. In the evidence that is express-1002, with about 12 500s in 15 minutes. Standard orders and the 200 responses are unaffected.
- Root cause: app/main.py:81 uses date.replace(day=day+2) for the delivery estimate instead of date arithmetic. It raises ValueError for any express order whose created_at day is greater than (days in month - 2). The seed data (init_db) deliberately creates express-1002 at the previous month end, which triggers it.

### Evidence cited by the agent
- [logs] Loki error logs, trace b3141cbefdc4a6c76956dc4ad7f9b79f: 19 ERROR lines on the route, all ValueError: day is out of range for month; stack ends at main.py:81 in order_detail.
- [traces] Tempo trace 220cc9ab9c479bfc0547d8048476458b: The span orders.build_detail errors with order.priority=express; order.id=express-1002 on the root span; the db select succeeded.
- [metrics] five_xx_last_5m / cumulative_by_status: All 5xx are error_type=ValueError on version 3982ab3; 12.6 500s vs 1.0 200s over 15m.
- [code] app/main.py:81 and 61: placed_at.replace(day=placed_at.day + 2); the seed sets express-1002 created_at to the previous month end.
- [code] tests/test_api.py::test_express_estimate_crosses_month_end: New regression test with a fixed date (2026-08-31) expects 2026-09-02; full suite passes, 6 passed.

### Agent final message
```
INC-20260930-130646-e094: GET /api/orders/express-1002 returns 500 (ValueError: day is out of range for month).
Cause: app/main.py:81 computes the delivery estimate with replace(day=day+2), which breaks near month end. The seeded express-1002 is dated Aug 31.
Fix: use placed_at + timedelta(days=2), plus a regression test with a fixed date. Full suite passes (6 tests).
Verdict: real incident, one-line patch proposed, please deploy and replay /api/orders/express-1002.
```

## Policy decision
- Level 2 (remediate): default level
- Allowed: False | outcome: **escalated**
  - PASS classification: agent classification = real_incident
  - PASS proposed_action: agent proposed patch
  - PASS confidence: 0.96 >= 0.7
  - PASS diff_not_empty: 2 file(s) changed
  - PASS paths_allowlisted: all paths allowlisted
  - PASS max_files: 2 <= 4
  - PASS max_lines: 14 <= 80
  - PASS regression_test: a test file changed
  - PASS tests_pass_rerun_by_responder: responder test run passed = True
  - PASS regression_test_fails_without_fix: suite without the code change failed = True
  - PASS action_patch_allowed_at_level: level 2
  - FAIL agent_extension_surface_as_declared: unexpected mcp=['claude-in-chrome'] plugins=['cc-plugin-agents-md', 'cc-plugin-telemetry'] skills=0
- Diff: {'files': ['app/main.py', 'tests/test_api.py'], 'added': 13, 'deleted': 1}

## Commands executed by the responder (not by the model)
- none

Files: alert.json, evidence/, prompt.md, agent/, response.json, decision.json, fix.patch, tests.log, deploy.log, verify.log, audit.jsonl
