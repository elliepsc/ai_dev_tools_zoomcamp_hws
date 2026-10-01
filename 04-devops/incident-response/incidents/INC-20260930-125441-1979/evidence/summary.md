# Evidence packet (2026-09-30T12:54:41.674950+00:00)

- Route under investigation: `/api/orders/{order_id}`
- Window: last 15 min

## Metrics (Prometheus)
- **five_xx_last_5m** `sum by (http_route, error_type, service_version) ((app_http_requests_total{job="order-tracker", http_response_status_code=~"5..", http_route="/api/orders/{order_id}"} unless app_http_requests_total{job="order-tracker", http_response_status_code=~"5..", http_route="/api/orders/{order_id}"} offset 5m) or increase(app_http_requests_total{job="order-tracker", http_response_status_code=~"5..", http_route="/api/orders/{order_id}"}[5m]))`
  - {"error_type": "ValueError", "http_route": "/api/orders/{order_id}", "service_version": "29b082a"} = 3
- **requests_by_status_window** `sum by (http_route, http_response_status_code) (increase(app_http_requests_total{job="order-tracker", http_route="/api/orders/{order_id}"}[15m]))`
  - {"http_response_status_code": "404", "http_route": "/api/orders/{order_id}"} = 0
  - {"http_response_status_code": "500", "http_route": "/api/orders/{order_id}"} = 0
- **cumulative_by_status** `sum by (http_route, http_response_status_code, error_type) (app_http_requests_total{job="order-tracker", http_route="/api/orders/{order_id}"})`
  - {"http_response_status_code": "404", "http_route": "/api/orders/{order_id}"} = 1
  - {"error_type": "ValueError", "http_response_status_code": "500", "http_route": "/api/orders/{order_id}"} = 3
- **deployed_versions** `count by (service_version) (app_http_requests_total{job="order-tracker"})`
  - {"service_version": "29b082a"} = 3

## Error logs (Loki)
`{service_name="order-tracker"} | severity_text="ERROR" | http_route="/api/orders/{order_id}"` -> 3 line(s)
- 2026-09-30T12:54:29.052645+00:00 GET /api/orders/{order_id} -> 500 trace_id=f6834d3d444685075d1663157d52badb exception=ValueError: day is out of range for month
- 2026-09-30T12:54:29.039347+00:00 GET /api/orders/{order_id} -> 500 trace_id=114fe6ee31c6d595ba0c08af5a25c851 exception=ValueError: day is out of range for month
- 2026-09-30T12:54:29.021783+00:00 GET /api/orders/{order_id} -> 500 trace_id=891efc00c015192342d11a4826d43988 exception=ValueError: day is out of range for month

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
`{resource.service.name="order-tracker" && status=error && span.http.route="/api/orders/{order_id}"}` -> 3 trace(s)
- trace f6834d3d444685075d1663157d52badb `GET /api/orders/{order_id}` None ms at 1970-01-01T00:00:00+00:00
  - span `orders.db.select` status=UNSET {}
  - span `orders.build_detail` status=STATUS_CODE_ERROR {"order.priority": "express"}
    - exception ValueError: day is out of range for month
  - span `GET /api/orders/{order_id}` status=STATUS_CODE_ERROR {"order.id": "express-1002", "order.priority": "express", "http.route": "/api/orders/{order_id}", "http.response.status_code": "500", "error.type": "ValueError"}
    - exception ValueError: day is out of range for month
- trace 114fe6ee31c6d595ba0c08af5a25c851 `GET /api/orders/{order_id}` None ms at 1970-01-01T00:00:00+00:00
  - span `orders.db.select` status=UNSET {}
  - span `orders.build_detail` status=STATUS_CODE_ERROR {"order.priority": "express"}
    - exception ValueError: day is out of range for month
  - span `GET /api/orders/{order_id}` status=STATUS_CODE_ERROR {"order.id": "express-1002", "order.priority": "express", "http.route": "/api/orders/{order_id}", "http.response.status_code": "500", "error.type": "ValueError"}
    - exception ValueError: day is out of range for month
- trace 891efc00c015192342d11a4826d43988 `GET /api/orders/{order_id}` None ms at 1970-01-01T00:00:00+00:00
  - span `orders.db.select` status=UNSET {}
  - span `orders.build_detail` status=STATUS_CODE_ERROR {"order.priority": "express"}
    - exception ValueError: day is out of range for month
  - span `GET /api/orders/{order_id}` status=STATUS_CODE_ERROR {"order.id": "express-1002", "order.priority": "express", "http.route": "/api/orders/{order_id}", "http.response.status_code": "500", "error.type": "ValueError"}
    - exception ValueError: day is out of range for month

## Failing request samples (rebuilt from span attributes)
- GET /api/orders/express-1002

## Deployment
- git HEAD: 1d6ea59 on hw4-observability
- app container: order-tracker-app-1 order-tracker:local running Up About a minute (healthy) created=2026-09-30 14:53:31 +0200 CEST
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
