# Evidence packet (2026-09-30T12:54:08.245135+00:00)

- Route: none given by the alert
- Window: last 15 min

## Metrics (Prometheus)
- **five_xx_last_5m** `sum by (http_route, error_type, service_version) ((app_http_requests_total{job="order-tracker", http_response_status_code=~"5.."} unless app_http_requests_total{job="order-tracker", http_response_status_code=~"5.."} offset 5m) or increase(app_http_requests_total{job="order-tracker", http_response_status_code=~"5.."}[5m]))`
  - (no series)
- **requests_by_status_window** `sum by (http_route, http_response_status_code) (increase(app_http_requests_total{job="order-tracker"}[15m]))`
  - {"http_response_status_code": "404", "http_route": "/api/orders/{order_id}"} = 0
  - {"http_response_status_code": "200", "http_route": "/healthz"} = 5.124583216727302
- **cumulative_by_status** `sum by (http_route, http_response_status_code, error_type) (app_http_requests_total{job="order-tracker"})`
  - {"http_response_status_code": "404", "http_route": "/api/orders/{order_id}"} = 1
  - {"http_response_status_code": "200", "http_route": "/healthz"} = 6
- **deployed_versions** `count by (service_version) (app_http_requests_total{job="order-tracker"})`
  - {"service_version": "29b082a"} = 2

## Error logs (Loki)
`{service_name="order-tracker"} | severity_text="ERROR"` -> 0 line(s)

## Error traces (Tempo)
`{resource.service.name="order-tracker" && status=error}` -> 0 trace(s)

## Failing request samples (rebuilt from span attributes)
- none

## Deployment
- git HEAD: 1d6ea59 on hw4-observability
- app container: order-tracker-app-1 order-tracker:local running Up 36 seconds (healthy) created=2026-09-30 14:53:31 +0200 CEST
- /healthz: 200 {"status":"ok"}
- recent commits:
  - 1d6ea59 2026-09-30 14:53:57 +0200 Responder: POST /incidents/{id}/close for the human disposition
  - 29b082a 2026-09-30 14:52:33 +0200 Responder: keep the full agent transcript (stream-json) and a tool-call/denial summary per incident
  - b26220b 2026-09-30 14:50:23 +0200 Evidence: fall back to trace ids from error logs; carry order.id on request logs
  - 8cb2b4f 2026-09-30 14:46:21 +0200 Security audit fixes: CSRF guard, auth on read endpoints, bounded queue, no git in agent tools, clean env for agent tests, redacted transcripts
  - adecc25 2026-09-30 14:35:43 +0200 Responder: require the regression test to fail without the fix (fail-before/pass-after)
  - f4fa8e5 2026-09-30 14:33:28 +0200 Responder: do not leak VIRTUAL_ENV/RESPONDER_TOKEN into runbooks and test runs
  - e15f0ca 2026-09-30 14:30:11 +0200 Responder: strip $schema for Claude CLI validator, load .env, .env.example
  - 909fb6a 2026-09-30 14:28:36 +0200 Add incident responder: evidence packet, headless agent adapter, autonomy policy, runbooks
