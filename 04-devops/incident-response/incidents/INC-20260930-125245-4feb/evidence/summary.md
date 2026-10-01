# Evidence packet (2026-09-30T12:52:45.476371+00:00)

- Route: none given by the alert
- Window: last 15 min

## Metrics (Prometheus)
- **five_xx_last_5m** `sum by (http_route, error_type, service_version) ((app_http_requests_total{job="order-tracker", http_response_status_code=~"5.."} unless app_http_requests_total{job="order-tracker", http_response_status_code=~"5.."} offset 5m) or increase(app_http_requests_total{job="order-tracker", http_response_status_code=~"5.."}[5m]))`
  - {"error_type": "ValueError", "http_route": "/api/orders/{order_id}", "service_version": "8cb2b4f"} = 3
  - {"error_type": "ValueError", "http_route": "/api/orders/{order_id}", "service_version": "b26220b"} = 3
- **requests_by_status_window** `sum by (http_route, http_response_status_code) (increase(app_http_requests_total{job="order-tracker"}[15m]))`
  - {"http_response_status_code": "200", "http_route": "/healthz"} = 59.65238095238095
  - {"http_response_status_code": "404", "http_route": "/api/orders/{order_id}"} = 0
  - {"http_response_status_code": "500", "http_route": "/api/orders/{order_id}"} = 0
  - {"http_response_status_code": "200", "http_route": "/api/orders/{order_id}"} = 2.1818181818181817
- **cumulative_by_status** `sum by (http_route, http_response_status_code, error_type) (app_http_requests_total{job="order-tracker"})`
  - {"http_response_status_code": "200", "http_route": "/healthz"} = 58
  - {"error_type": "ValueError", "http_response_status_code": "500", "http_route": "/api/orders/{order_id}"} = 6
  - {"http_response_status_code": "200", "http_route": "/api/orders/{order_id}"} = 8
- **deployed_versions** `count by (service_version) (app_http_requests_total{job="order-tracker"})`
  - {"service_version": "8cb2b4f"} = 2
  - {"service_version": "655b7cc"} = 2
  - {"service_version": "b26220b"} = 2
  - {"service_version": "c074d4f"} = 2
  - {"service_version": "29b082a"} = 1

## Error logs (Loki)
`{service_name="order-tracker"} | severity_text="ERROR"` -> 6 line(s)
- 2026-09-30T12:50:35.520374+00:00 GET /api/orders/{order_id} -> 500 trace_id=f876ef66101e9f32f2ceab6badaf0ff7 exception=ValueError: day is out of range for month
- 2026-09-30T12:50:35.505546+00:00 GET /api/orders/{order_id} -> 500 trace_id=c8774e52e877d30a94b5a1cdb55100a7 exception=ValueError: day is out of range for month
- 2026-09-30T12:50:35.487689+00:00 GET /api/orders/{order_id} -> 500 trace_id=072f77acfe0a3fdae24a96e0be657097 exception=ValueError: day is out of range for month
- 2026-09-30T12:48:23.600873+00:00 GET /api/orders/{order_id} -> 500 trace_id=34ee7e04081a3c1f5f0a18f0991ed22b exception=ValueError: day is out of range for month
- 2026-09-30T12:48:23.586129+00:00 GET /api/orders/{order_id} -> 500 trace_id=6b350e9178eb40cbab750f3c8b042576 exception=ValueError: day is out of range for month

Most recent stack trace:
```
await route.handle(scope, receive, send)
  File "/app/.venv/lib/python3.12/site-packages/fastapi/routing.py", line 1310, in handle
    await super().handle(scope, receive, send)
  File "/app/.venv/lib/python3.12/site-packages/starlette/routing.py", line 282, in handle
    await self.app(scope, receive, send)
  File "/app/.venv/lib/python3.12/site-packages/fastapi/routing.py", line 165, in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
  File "/app/.venv/lib/python3.12/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "/app/.venv/lib/python3.12/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/app/.venv/lib/python3.12/site-packages/fastapi/routing.py", line 151, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.12/site-packages/fastapi/routing.py", line 727, in app
    raw_response = await run_endpoint_function(
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.12/site-packages/fastapi/routing.py", line 362, in run_endpoint_function
    return await run_in_threadpool(
           ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.12/site-packages/starlette/concurrency.py", line 34, in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.12/site-packages/anyio/to_thread.py", line 65, in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.12/site-packages/anyio/_backends/_asyncio.py", line 2706, in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
  File "/app/.venv/lib/python3.12/site-packages/anyio/_backends/_asyncio.py", line 1100, in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.12/site-packages/fastapi/telemetry/_api.py", line 240, in _run_sync_endpoint
    return function(**arguments)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/app/app/main.py", line 200, in get_order
    detail = order_detail(row)
             ^^^^^^^^^^^^^^^^^
  File "/app/app/main.py", line 81, in order_detail
    estimated_at = placed_at.replace(day=placed_at.day + 2)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ValueError: day is out of range for month

```

## Error traces (Tempo)
`{resource.service.name="order-tracker" && status=error}` -> 5 trace(s)
- trace c8774e52e877d30a94b5a1cdb55100a7 `GET /api/orders/{order_id}` 4 ms at 2026-09-30T12:50:35.503037+00:00
  - span `orders.db.select` status=UNSET {}
  - span `orders.build_detail` status=STATUS_CODE_ERROR {"order.priority": "express"}
    - exception ValueError: day is out of range for month
  - span `GET /api/orders/{order_id}` status=STATUS_CODE_ERROR {"order.id": "express-1002", "order.priority": "express", "http.response.status_code": "500", "error.type": "ValueError", "http.route": "/api/orders/{order_id}"}
    - exception ValueError: day is out of range for month
- trace 72f77acfe0a3fdae24a96e0be657097 `GET /api/orders/{order_id}` 13 ms at 2026-09-30T12:50:35.477248+00:00
  - span `orders.db.select` status=UNSET {}
  - span `orders.build_detail` status=STATUS_CODE_ERROR {"order.priority": "express"}
    - exception ValueError: day is out of range for month
  - span `GET /api/orders/{order_id}` status=STATUS_CODE_ERROR {"order.id": "express-1002", "order.priority": "express", "http.response.status_code": "500", "error.type": "ValueError", "http.route": "/api/orders/{order_id}"}
    - exception ValueError: day is out of range for month
- trace 34ee7e04081a3c1f5f0a18f0991ed22b `GET /api/orders/{order_id}` 4 ms at 2026-09-30T12:48:23.598310+00:00
  - span `orders.db.select` status=UNSET {}
  - span `orders.build_detail` status=STATUS_CODE_ERROR {"order.priority": "express"}
    - exception ValueError: day is out of range for month
  - span `GET /api/orders/{order_id}` status=STATUS_CODE_ERROR {"order.id": "express-1002", "order.priority": "express", "http.response.status_code": "500", "error.type": "ValueError", "http.route": "/api/orders/{order_id}"}
    - exception ValueError: day is out of range for month

## Failing request samples (rebuilt from span attributes)
- GET /api/orders/express-1002

## Deployment
- git HEAD: 29b082a on hw4-observability
- app container: order-tracker-app-1 order-tracker:local running Up 11 seconds (healthy) created=2026-09-30 14:52:34 +0200 CEST
- /healthz: 200 {"status":"ok"}
- recent commits:
  - 29b082a 2026-09-30 14:52:33 +0200 Responder: keep the full agent transcript (stream-json) and a tool-call/denial summary per incident
  - b26220b 2026-09-30 14:50:23 +0200 Evidence: fall back to trace ids from error logs; carry order.id on request logs
  - 8cb2b4f 2026-09-30 14:46:21 +0200 Security audit fixes: CSRF guard, auth on read endpoints, bounded queue, no git in agent tools, clean env for agent tests, redacted transcripts
  - adecc25 2026-09-30 14:35:43 +0200 Responder: require the regression test to fail without the fix (fail-before/pass-after)
  - f4fa8e5 2026-09-30 14:33:28 +0200 Responder: do not leak VIRTUAL_ENV/RESPONDER_TOKEN into runbooks and test runs
  - e15f0ca 2026-09-30 14:30:11 +0200 Responder: strip $schema for Claude CLI validator, load .env, .env.example
  - 909fb6a 2026-09-30 14:28:36 +0200 Add incident responder: evidence packet, headless agent adapter, autonomy policy, runbooks
  - a35f496 2026-09-30 14:22:35 +0200 Add telemetry pipeline: Collector, Prometheus, Loki, Tempo, Grafana (dashboard, 5xx alert, webhook)
