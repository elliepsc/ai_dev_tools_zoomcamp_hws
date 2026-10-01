# Incident INC-20260930-123549-5c01

- **State**: escalated (patch rejected by policy: regression_test_fails_without_fix (suite without the code change failed = False))
- **Opened**: 2026-09-30T12:35:49+00:00 | **closed/escalated**: 2026-09-30T12:35:52+00:00
- **Alert**: OrderTracker5xx status=firing route=`/api/orders/{order_id}` labels=`{"alertname": "OrderTracker5xx", "drill": "gate", "grafana_folder": "Order Tracker Alerts", "http_route": "/api/orders/{order_id}", "service": "order-tracker", "severity": "critical", "team": "ops"}`
- **Summary (Grafana)**: Server errors (5xx) on /api/orders/{order_id}

## Agent
- Agent: fake | model: CLI default | mode: edit | exit: 0 | duration: 0 s
- Models reported by the CLI: None
- Command: `fake`

- Classification: **real_incident** (confidence 0.9)
- Proposed action: **patch**
- User impact: drill
- Root cause: drill: the patch below does not address the real cause

### Evidence cited by the agent
- [alert] drill: drill

### Agent final message
```
DRILL: ineffective patch on purpose.
Verdict: drill patch proposed.
```

## Policy decision
- Level 2 (remediate): default level
- Allowed: False | outcome: **escalated**
  - PASS classification: agent classification = real_incident
  - PASS proposed_action: agent proposed patch
  - PASS confidence: 0.90 >= 0.7
  - PASS diff_not_empty: 2 file(s) changed
  - PASS paths_allowlisted: all paths allowlisted
  - PASS max_files: 2 <= 4
  - PASS max_lines: 3 <= 80
  - PASS regression_test: a test file changed
  - PASS tests_pass_rerun_by_responder: responder test run passed = True
  - FAIL regression_test_fails_without_fix: suite without the code change failed = False
  - PASS action_patch_allowed_at_level: level 2
- Diff: {'files': ['app/main.py', 'tests/test_drill.py'], 'added': 3, 'deleted': 0}

## Commands executed by the responder (not by the model)
- none

Files: alert.json, evidence/, prompt.md, agent/, response.json, decision.json, fix.patch, tests.log, deploy.log, verify.log, audit.jsonl
