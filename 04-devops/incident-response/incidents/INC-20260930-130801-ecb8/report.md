# Incident INC-20260930-130801-ecb8

- **State**: resolved (fix 84e2502 deployed and verified)
- **Opened**: 2026-09-30T13:08:01+00:00 | **closed/escalated**: 2026-09-30T13:09:00+00:00
- **Alert**: OrderTracker5xx status=firing route=`/api/orders/{order_id}` labels=`{"alertname": "OrderTracker5xx", "grafana_folder": "Order Tracker Alerts", "http_route": "/api/orders/{order_id}", "service": "order-tracker", "severity": "critical", "team": "ops"}`
- **Summary (Grafana)**: Server errors (5xx) on /api/orders/{order_id}

## Agent
- Agent: claude-code | model: CLI default | mode: edit | exit: 0 | duration: 26.0 s
- Models reported by the CLI: ['claude-haiku-4-5-20251001', 'claude-sonnet-5-5']
- Command: `claude -p --output-format stream-json --verbose --json-schema <schema: response.schema.json> --max-turns 40 --no-session-persistence --permission-mode acceptEdits --allowedTools Read Glob Grep Edit Write Bash(uv run --frozen pytest:*) --disallowedTools WebFetch WebSearch Bash(docker:*) Bash(curl:*) Bash(wget:*) Bash(git commit:*) Bash(git push:*) Bash(git reset:*) Bash(rm:*) Bash(sudo:*) Read(./.env) Read(**/.env) Read(~/.ssh/**) Read(~/.aws/**) Read(~/.docker/**) --strict-mcp-config --mcp-config /home/claude/order-tracker/incident-response/agent-mcp.json --disable-slash-commands --setting-sources project --add-dir /home/claude/order-tracker/incident-response/incidents/INC-20260930-130801-ecb8/evidence`

- Classification: **real_incident** (confidence 0.95)
- Proposed action: **patch**
- User impact: Every request for express orders placed on day 29-31 of a month fails with 500. The seeded express-1002 is dated the last day of the previous month, so it always fails. Standard orders and the list endpoint are unaffected.
- Root cause: app/main.py:81 in order_detail used placed_at.replace(day=placed_at.day + 2). This raises ValueError when day+2 exceeds the month length. Express-1002's created_at is the previous month's last day, so the failure is deterministic.

### Evidence cited by the agent
- [metrics] five_xx_last_5m: 7 5xx responses, all error_type=ValueError, service_version 3982ab3, route /api/orders/{order_id}.
- [logs] Loki ERROR trace_id=9d5ffecbb7b0370dc1f699efbd25982c: ValueError: day is out of range for month, raised at app/main.py line 81 in order_detail, called from get_order line 200.
- [traces] trace 220cc9ab9c479bfc0547d8048476458b: orders.build_detail span errored with order.priority=express and order.id=express-1002. The DB select succeeded.
- [code] app/main.py:61-64,81: The seed sets express-1002 to the last day of the previous month, and the estimate uses replace(day=day+2).

### Agent final message
```
INC-20260930-130801-ecb8: 5xx on /api/orders/{order_id} (GET /api/orders/express-1002).
Cause: order_detail used replace(day=day+2) for the express ETA, which raises ValueError for orders placed on day 29-31 of a month.
Fix: use placed_at + timedelta(days=2), plus a date-independent regression test. The suite passes (6 tests).
Verdict: real incident, small local patch proposed, replay /api/orders/express-1002 after deploy.
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
  - PASS max_lines: 7 <= 80
  - PASS regression_test: a test file changed
  - PASS tests_pass_rerun_by_responder: responder test run passed = True
  - PASS regression_test_fails_without_fix: suite without the code change failed = True
  - PASS action_patch_allowed_at_level: level 2
  - PASS agent_extension_surface_as_declared: effective surface matches the declared one
- Diff: {'files': ['app/main.py', 'tests/test_api.py'], 'added': 6, 'deleted': 1}

## Commands executed by the responder (not by the model)
- `/home/claude/order-tracker/incident-response/runbooks/deploy-fix.sh /home/claude/order-tracker incident/INC-20260930-130801-ecb8 inc-20260930-130801-ecb8` -> exit 0
- `/home/claude/order-tracker/incident-response/runbooks/verify-recovery.sh /api/orders/{order_id} /api/orders/express-1002` -> exit 0

## verify.log
```
$ /home/claude/order-tracker/incident-response/runbooks/verify-recovery.sh /api/orders/{order_id} /api/orders/express-1002
healthz -> 200
GET /api/orders/express-1002 -> 200
GET /api/orders/express-1002 -> 200
GET /api/orders/express-1002 -> 200
5xx counter for /api/orders/{order_id}: before=7 after=7
{"recovered": true, "healthz": "200", "five_xx_before": "7", "five_xx_after": "7", "replayed": "/api/orders/express-1002=200 /api/orders/express-1002=200 /api/orders/express-1002=200"}

exit=0

```

## deploy.log
```
0s

#5 [internal] load .dockerignore
#5 transferring context: 100B done
#5 DONE 0.0s

#6 [internal] load build context
#6 DONE 0.0s

#7 FROM ghcr.io/astral-sh/uv:0.8.22@sha256:87328c5108b79429afd0b9ee8b453991d26c6d4c5486070a413b84e2d6e86ffb
#7 resolve ghcr.io/astral-sh/uv:0.8.22@sha256:87328c5108b79429afd0b9ee8b453991d26c6d4c5486070a413b84e2d6e86ffb 0.0s done
#7 DONE 0.0s

#8 [stage-0 1/8] FROM docker.io/library/python:3.12-slim@sha256:2c95c2f92af422478a507910113fcc6e5e9a2b4aebafe5d21d8bfce46101fcf3
#8 resolve docker.io/library/python:3.12-slim@sha256:2c95c2f92af422478a507910113fcc6e5e9a2b4aebafe5d21d8bfce46101fcf3
#8 resolve docker.io/library/python:3.12-slim@sha256:2c95c2f92af422478a507910113fcc6e5e9a2b4aebafe5d21d8bfce46101fcf3 0.0s done
#8 DONE 0.0s

#6 [internal] load build context
#6 transferring context: 8.89kB done
#6 DONE 0.0s

#9 [stage-0 4/8] COPY pyproject.toml uv.lock ./
#9 CACHED

#10 [stage-0 2/8] COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /bin/
#10 CACHED

#11 [stage-0 3/8] WORKDIR /app
#11 CACHED

#12 [stage-0 5/8] RUN uv sync --frozen --no-dev
#12 CACHED

#13 [stage-0 6/8] COPY app ./app
#13 DONE 0.0s

#14 [stage-0 7/8] COPY static ./static
#14 DONE 0.0s

#15 [stage-0 8/8] RUN useradd --system --uid 10001 --no-create-home app && mkdir -p /data && chown app /data
#15 0.066 useradd warning: app's uid 10001 is greater than SYS_UID_MAX 999
#15 DONE 0.1s

#16 exporting to image
#16 exporting layers 0.1s done
#16 exporting manifest sha256:161654256bb1412bb42440cb2b1eeb21e4f2b670a60b69d73f2a8a0306f8f458 done
#16 exporting config sha256:0949037ad6f9e2ea39f3abf8fcfbfecb628f4b21c27accd847fb8e93d67a10f1 done
#16 exporting attestation manifest sha256:858a7203c7a25d1c1fd067ef140271fe078c011888f94fe0fd1636a5470b8178 done
#16 exporting manifest list sha256:816916dcd712e24686f138907b089560e580244b423f69a857a1930e4f93b904 done
#16 naming to docker.io/library/order-tracker:local
#16 naming to docker.io/library/order-tracker:local done
#16 unpacking to docker.io/library/order-tracker:local 0.0s done
#16 DONE 0.1s

#17 resolving provenance for metadata file
#17 DONE 0.0s
deployed 84e2502
order-tracker:rollback-inc-20260930-130801-ecb8
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
