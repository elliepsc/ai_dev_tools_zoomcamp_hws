# Incident INC-20260930-125626-5af5

- **State**: escalated (deploy-fix.sh failed (exit 3); nothing changed in production if exit 3)
- **Opened**: 2026-09-30T12:56:26+00:00 | **closed/escalated**: 2026-09-30T12:56:56+00:00
- **Alert**: OrderTracker5xx status=firing route=`/api/orders/{order_id}` labels=`{"alertname": "OrderTracker5xx", "grafana_folder": "Order Tracker Alerts", "http_route": "/api/orders/{order_id}", "service": "order-tracker", "severity": "critical", "team": "ops"}`
- **Summary (Grafana)**: Server errors (5xx) on /api/orders/{order_id}

## Agent
- Agent: claude-code | model: CLI default | mode: edit | exit: 0 | duration: 27.3 s
- Models reported by the CLI: ['claude-haiku-4-5-20251001', 'claude-sonnet-5-5']
- Command: `claude -p --output-format stream-json --verbose --json-schema <schema: response.schema.json> --max-turns 40 --no-session-persistence --permission-mode acceptEdits --allowedTools Read Glob Grep Edit Write Bash(uv run --frozen pytest:*) --disallowedTools WebFetch WebSearch Bash(docker:*) Bash(curl:*) Bash(wget:*) Bash(git commit:*) Bash(git push:*) Bash(git reset:*) Bash(rm:*) Bash(sudo:*) Read(./.env) Read(**/.env) Read(~/.ssh/**) Read(~/.aws/**) Read(~/.docker/**) --strict-mcp-config --mcp-config /home/claude/order-tracker/incident-response/agent-mcp.json --add-dir /home/claude/order-tracker/incident-response/incidents/INC-20260930-125626-5af5/evidence`

- Classification: **real_incident** (confidence 0.97)
- Proposed action: **patch**
- User impact: Any express order placed on the last days of a month (e.g. seeded express-1002, placed on the previous month's end) cannot be fetched; every GET returns 500. Standard orders are unaffected.
- Root cause: app/main.py order_detail: `placed_at.replace(day=placed_at.day + 2)` raises ValueError when day+2 exceeds the month length. It is a latent bug, triggered by the seed data (express-1002 has created_at set to the previous month's last day). It is not caused by a recent deploy.

### Evidence cited by the agent
- [logs] Loki error logs, trace 643fdae01abf5b033fad9ccb0df23417: ValueError: day is out of range for month at app/main.py line 81 in order_detail
- [traces] Tempo traces 643fdae0..., f6834d3d..., 114fe6ee...: All failing spans carry order.id=express-1002 and order.priority=express; orders.build_detail span holds the exception
- [metrics] cumulative_by_status: All 7 500s are ValueError on this route, on both service versions 29b082a and 95b99c8, so it is not a deploy regression
- [code] app/main.py:61-64,81: Seed sets express-1002 created_at to the previous month's last day; .replace(day=day+2) overflows

### Agent final message
```
INC-20260930-125626-5af5: /api/orders/{order_id} returns 500 for express-1002.
Cause: order_detail used placed_at.replace(day=day+2), which overflows near month end (ValueError). It is a latent bug hit by the seed data, not a deploy regression.
Fix: use placed_at + timedelta(days=2), plus a date-independent regression test. Full suite passes (6 passed).
Verdict: patch proposed, small local fix, confidence 0.97; replay GET /api/orders/express-1002 after deploy.
```

## Policy decision
- Level 2 (remediate): default level
- Allowed: True | outcome: **deploy_failed**
  - PASS classification: agent classification = real_incident
  - PASS proposed_action: agent proposed patch
  - PASS confidence: 0.97 >= 0.7
  - PASS diff_not_empty: 2 file(s) changed
  - PASS paths_allowlisted: all paths allowlisted
  - PASS max_files: 2 <= 4
  - PASS max_lines: 15 <= 80
  - PASS regression_test: a test file changed
  - PASS tests_pass_rerun_by_responder: responder test run passed = True
  - PASS regression_test_fails_without_fix: suite without the code change failed = True
  - PASS action_patch_allowed_at_level: level 2
- Diff: {'files': ['app/main.py', 'tests/test_api.py'], 'added': 14, 'deleted': 1}

## Commands executed by the responder (not by the model)
- `/home/claude/order-tracker/incident-response/runbooks/deploy-fix.sh /home/claude/order-tracker incident/INC-20260930-125626-5af5 inc-20260930-125626-5af5` -> exit 3

## deploy.log
```
$ /home/claude/order-tracker/incident-response/runbooks/deploy-fix.sh /home/claude/order-tracker incident/INC-20260930-125626-5af5 inc-20260930-125626-5af5
refusing: tracked files have uncommitted changes in /home/claude/order-tracker

exit=3

```

Files: alert.json, evidence/, prompt.md, agent/, response.json, decision.json, fix.patch, tests.log, deploy.log, verify.log, audit.jsonl
