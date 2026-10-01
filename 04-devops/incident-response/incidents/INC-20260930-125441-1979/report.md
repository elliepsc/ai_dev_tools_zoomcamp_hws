# Incident INC-20260930-125441-1979

- **State**: escalated (responder pipeline error: AttributeError("'str' object has no attribute 'get'"))
- **Opened**: 2026-09-30T12:54:41+00:00 | **closed/escalated**: 2026-09-30T12:55:22+00:00
- **Alert**: OrderTracker5xx status=firing route=`/api/orders/{order_id}` labels=`{"alertname": "OrderTracker5xx", "grafana_folder": "Order Tracker Alerts", "http_route": "/api/orders/{order_id}", "service": "order-tracker", "severity": "critical", "team": "ops"}`
- **Summary (Grafana)**: Server errors (5xx) on /api/orders/{order_id}

## Agent
- Agent: None | model: CLI default | mode: None | exit: None | duration: 0 s
- Models reported by the CLI: None
- Command: ``


Files: alert.json, evidence/, prompt.md, agent/, response.json, decision.json, fix.patch, tests.log, deploy.log, verify.log, audit.jsonl
