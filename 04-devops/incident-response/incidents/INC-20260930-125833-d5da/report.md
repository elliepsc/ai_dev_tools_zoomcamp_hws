# Incident INC-20260930-125833-d5da

- **State**: resolved (fix c592846 deployed and verified)
- **Opened**: 2026-09-30T12:58:33+00:00 | **closed/escalated**: 2026-09-30T12:59:36+00:00
- **Alert**: OrderTracker5xx status=firing route=`/api/orders/{order_id}` labels=`{"alertname": "OrderTracker5xx", "grafana_folder": "Order Tracker Alerts", "http_route": "/api/orders/{order_id}", "service": "order-tracker", "severity": "critical", "team": "ops"}`
- **Summary (Grafana)**: Server errors (5xx) on /api/orders/{order_id}

## Agent
- Agent: claude-code | model: CLI default | mode: edit | exit: 0 | duration: 30.6 s
- Models reported by the CLI: ['claude-haiku-4-5-20251001', 'claude-sonnet-5-5']
- Command: `claude -p --output-format stream-json --verbose --json-schema <schema: response.schema.json> --max-turns 40 --no-session-persistence --permission-mode acceptEdits --allowedTools Read Glob Grep Edit Write Bash(uv run --frozen pytest:*) --disallowedTools WebFetch WebSearch Bash(docker:*) Bash(curl:*) Bash(wget:*) Bash(git commit:*) Bash(git push:*) Bash(git reset:*) Bash(rm:*) Bash(sudo:*) Read(./.env) Read(**/.env) Read(~/.ssh/**) Read(~/.aws/**) Read(~/.docker/**) --strict-mcp-config --mcp-config /home/claude/order-tracker/incident-response/agent-mcp.json --add-dir /home/claude/order-tracker/incident-response/incidents/INC-20260930-125833-d5da/evidence`

- Classification: **real_incident** (confidence 0.95)
- Proposed action: **patch**
- User impact: Every request for express orders placed on the 27th or later of a month (seeded order express-1002, created on the last day of the previous month) returns HTTP 500. Standard orders are unaffected.
- Root cause: app/main.py:81 in order_detail builds the estimate with placed_at.replace(day=placed_at.day + 2). When day+2 exceeds the number of days in the month, datetime raises "ValueError: day is out of range for month". The seed order express-1002 is dated the last day of the previous month, so it always triggers this. The bug depends on the date, not on a recent deploy: both versions 29b082a and 95b99c8 show the same error.

### Evidence cited by the agent
- [logs] Loki ERROR lines, e.g. trace_id=2b20289f1472765d1466d4ad42003e32: 15 ERROR lines on the route, all ValueError: day is out of range for month
- [code] app/main.py:81 (stack trace) and order_detail: placed_at.replace(day=placed_at.day + 2) overflows at month end
- [code] app/main.py seed data (previous_month_end): express-1002 is seeded with created_at = last day of the previous month, so it always overflows
- [traces] Tempo trace 220cc9ab9c479bfc0547d8048476458b: span orders.build_detail errors with order.priority=express, order.id=express-1002
- [metrics] five_xx_last_5m / cumulative_by_status: Only 500s with error_type=ValueError; 15 total, on both service_versions 29b082a and 95b99c8, so not tied to one deploy
- [alert] OrderTracker5xx: Fired on route /api/orders/{order_id} with 3 5xx in 5m; not a test notification

### Agent final message
```
INC-20260930-125833-d5da: 500s on /api/orders/{order_id}, from order_detail in app/main.py:81.
Cause: replace(day=day+2) raises ValueError near month end. It hits express orders placed on the 27th or later, such as seeded express-1002.
Fix: use placed_at + timedelta(days=2), plus a regression test. Full suite passes (7), and the new tests fail without the fix.
Replay after deploy: GET /api/orders/express-1002.
Verdict: real incident, date-dependent bug in delivery estimate, small patch proposed with confidence 0.95.
```

## Policy decision
- Level 2 (remediate): default level
- Allowed: True | outcome: **fixed_and_verified**
  - PASS classification: agent classification = real_incident
  - PASS proposed_action: agent proposed patch
  - PASS confidence: 0.95 >= 0.7
  - PASS diff_not_empty: 2 file(s) changed
  - PASS paths_allowlisted: all paths allowlisted
  - PASS max_files: 2 <= 4
  - PASS max_lines: 11 <= 80
  - PASS regression_test: a test file changed
  - PASS tests_pass_rerun_by_responder: responder test run passed = True
  - PASS regression_test_fails_without_fix: suite without the code change failed = True
  - PASS action_patch_allowed_at_level: level 2
- Diff: {'files': ['app/main.py', 'tests/test_api.py'], 'added': 10, 'deleted': 1}

## Commands executed by the responder (not by the model)
- `/home/claude/order-tracker/incident-response/runbooks/deploy-fix.sh /home/claude/order-tracker incident/INC-20260930-125833-d5da inc-20260930-125833-d5da` -> exit 0
- `/home/claude/order-tracker/incident-response/runbooks/verify-recovery.sh /api/orders/{order_id} /api/orders/express-1002` -> exit 0

## verify.log
```
$ /home/claude/order-tracker/incident-response/runbooks/verify-recovery.sh /api/orders/{order_id} /api/orders/express-1002
healthz -> 200
GET /api/orders/express-1002 -> 200
GET /api/orders/express-1002 -> 200
GET /api/orders/express-1002 -> 200
5xx counter for /api/orders/{order_id}: before=15 after=15
{"recovered": true, "healthz": "200", "five_xx_before": "15", "five_xx_after": "15", "replayed": "/api/orders/express-1002=200 /api/orders/express-1002=200 /api/orders/express-1002=200"}

exit=0

```

## deploy.log
```
a for ghcr.io/astral-sh/uv:0.8.22
#4 DONE 0.0s

#5 [internal] load .dockerignore
#5 transferring context: 100B done
#5 DONE 0.0s

#6 [internal] load build context
#6 DONE 0.0s

#7 [stage-0 1/8] FROM docker.io/library/python:3.12-slim@sha256:2c95c2f92af422478a507910113fcc6e5e9a2b4aebafe5d21d8bfce46101fcf3
#7 resolve docker.io/library/python:3.12-slim@sha256:2c95c2f92af422478a507910113fcc6e5e9a2b4aebafe5d21d8bfce46101fcf3 0.0s done
#7 DONE 0.0s

#8 FROM ghcr.io/astral-sh/uv:0.8.22@sha256:87328c5108b79429afd0b9ee8b453991d26c6d4c5486070a413b84e2d6e86ffb
#8 resolve ghcr.io/astral-sh/uv:0.8.22@sha256:87328c5108b79429afd0b9ee8b453991d26c6d4c5486070a413b84e2d6e86ffb
#8 resolve ghcr.io/astral-sh/uv:0.8.22@sha256:87328c5108b79429afd0b9ee8b453991d26c6d4c5486070a413b84e2d6e86ffb 0.0s done
#8 DONE 0.0s

#6 [internal] load build context
#6 transferring context: 8.89kB done
#6 DONE 0.0s

#9 [stage-0 5/8] RUN uv sync --frozen --no-dev
#9 CACHED

#10 [stage-0 2/8] COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /bin/
#10 CACHED

#11 [stage-0 4/8] COPY pyproject.toml uv.lock ./
#11 CACHED

#12 [stage-0 6/8] COPY app ./app
#12 CACHED

#13 [stage-0 3/8] WORKDIR /app
#13 CACHED

#14 [stage-0 7/8] COPY static ./static
#14 CACHED

#15 [stage-0 8/8] RUN useradd --system --uid 10001 --no-create-home app && mkdir -p /data && chown app /data
#15 0.059 useradd warning: app's uid 10001 is greater than SYS_UID_MAX 999
#15 DONE 0.1s

#16 exporting to image
#16 exporting layers
#16 exporting layers 0.0s done
#16 exporting manifest sha256:2898b1cfd3cdc6fabe26b7a47727bfd1e5ea9ef9c75b950bcbbb1e28e74a2046 done
#16 exporting config sha256:a7e989c1751e1208771ef9bb674757c84b7b16d234e8173f651d69f79049ceae done
#16 exporting attestation manifest sha256:0971682043d80ddc719a33e2f71dfb1befa9cedde105a24580650531e3084daf done
#16 exporting manifest list sha256:2ecacc29690097e8cb9a0e5c84fddab7faf6a23492ea2e643b02df7fe850d7ea done
#16 naming to docker.io/library/order-tracker:local done
#16 unpacking to docker.io/library/order-tracker:local 0.0s done
#16 DONE 0.1s

#17 resolving provenance for metadata file
#17 DONE 0.0s
deployed c592846
order-tracker:rollback-inc-20260930-125833-d5da
 Image order-tracker:local Building 
 Image order-tracker:local Built 
 Container order-tracker-app-1 Recreate 
 Container order-tracker-app-1 Recreated 
 Container order-tracker-app-1 Starting 
 Container order-tracker-app-1 Started 
 Container order-tracker-app-1 Waiting 
 Container order-tracker-app-1 Healthy 

exit=0

```

Files: alert.json, evidence/, prompt.md, agent/, response.json, decision.json, fix.patch, tests.log, deploy.log, verify.log, audit.jsonl
