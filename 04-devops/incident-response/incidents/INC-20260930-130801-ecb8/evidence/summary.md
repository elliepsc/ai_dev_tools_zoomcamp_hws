# Evidence packet (2026-09-30T13:08:01.342517+00:00)

- Route under investigation: `/api/orders/{order_id}`
- Window: last 15 min

## Metrics (Prometheus)
- **five_xx_last_5m** `sum by (http_route, error_type, service_version) ((app_http_requests_total{job="order-tracker", http_response_status_code=~"5..", http_route="/api/orders/{order_id}"} unless app_http_requests_total{job="order-tracker", http_response_status_code=~"5..", http_route="/api/orders/{order_id}"} offset 5m) or increase(app_http_requests_total{job="order-tracker", http_response_status_code=~"5..", http_route="/api/orders/{order_id}"}[5m]))`
  - {"error_type": "ValueError", "http_route": "/api/orders/{order_id}", "service_version": "3982ab3"} = 7
- **requests_by_status_window** `sum by (http_route, http_response_status_code) (increase(app_http_requests_total{job="order-tracker", http_route="/api/orders/{order_id}"}[15m]))`
  - {"http_response_status_code": "404", "http_route": "/api/orders/{order_id}"} = 0
  - {"http_response_status_code": "500", "http_route": "/api/orders/{order_id}"} = 15.73880815846899
  - {"http_response_status_code": "200", "http_route": "/api/orders/{order_id}"} = 1.0125000000000002
- **cumulative_by_status** `sum by (http_route, http_response_status_code, error_type) (app_http_requests_total{job="order-tracker", http_route="/api/orders/{order_id}"})`
  - {"http_response_status_code": "200", "http_route": "/api/orders/{order_id}"} = 4
  - {"error_type": "ValueError", "http_response_status_code": "500", "http_route": "/api/orders/{order_id}"} = 7
- **deployed_versions** `count by (service_version) (app_http_requests_total{job="order-tracker"})`
  - {"service_version": "c592846"} = 2
  - {"service_version": "3982ab3"} = 2

## Error logs (Loki)
`{service_name="order-tracker"} | severity_text="ERROR" | http_route="/api/orders/{order_id}"` -> 20 line(s)
- 2026-09-30T13:07:48.740883+00:00 GET /api/orders/{order_id} -> 500 trace_id=9d5ffecbb7b0370dc1f699efbd25982c exception=ValueError: day is out of range for month
- 2026-09-30T13:07:48.727683+00:00 GET /api/orders/{order_id} -> 500 trace_id=bb19e1c73979ae9b26946e136bcf0add exception=ValueError: day is out of range for month
- 2026-09-30T13:07:48.710712+00:00 GET /api/orders/{order_id} -> 500 trace_id=07afdfdfc863154125717fcfcd0c174c exception=ValueError: day is out of range for month
- 2026-09-30T13:06:36.457285+00:00 GET /api/orders/{order_id} -> 500 trace_id=b3141cbefdc4a6c76956dc4ad7f9b79f exception=ValueError: day is out of range for month
- 2026-09-30T13:06:36.444305+00:00 GET /api/orders/{order_id} -> 500 trace_id=364dd4c885e43d2e0cd2177d6b328a6d exception=ValueError: day is out of range for month

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
`{resource.service.name="order-tracker" && status=error && span.http.route="/api/orders/{order_id}"}` -> 5 trace(s)
- trace 220cc9ab9c479bfc0547d8048476458b `GET /api/orders/{order_id}` 5 ms at 2026-09-30T12:56:13.723417+00:00
  - span `orders.db.select` status=UNSET {}
  - span `orders.build_detail` status=STATUS_CODE_ERROR {"order.priority": "express"}
    - exception ValueError: day is out of range for month
  - span `GET /api/orders/{order_id}` status=STATUS_CODE_ERROR {"order.id": "express-1002", "order.priority": "express", "http.response.status_code": "500", "error.type": "ValueError", "http.route": "/api/orders/{order_id}"}
    - exception ValueError: day is out of range for month
- trace 643fdae01abf5b033fad9ccb0df23417 `GET /api/orders/{order_id}` 5 ms at 2026-09-30T12:55:30.249346+00:00
  - span `orders.db.select` status=UNSET {}
  - span `orders.build_detail` status=STATUS_CODE_ERROR {"order.priority": "express"}
    - exception ValueError: day is out of range for month
  - span `GET /api/orders/{order_id}` status=STATUS_CODE_ERROR {"order.id": "express-1002", "order.priority": "express", "http.response.status_code": "500", "error.type": "ValueError", "http.route": "/api/orders/{order_id}"}
    - exception ValueError: day is out of range for month
- trace f6834d3d444685075d1663157d52badb `GET /api/orders/{order_id}` 4 ms at 2026-09-30T12:54:29.050095+00:00
  - span `orders.db.select` status=UNSET {}
  - span `orders.build_detail` status=STATUS_CODE_ERROR {"order.priority": "express"}
    - exception ValueError: day is out of range for month
  - span `GET /api/orders/{order_id}` status=STATUS_CODE_ERROR {"order.id": "express-1002", "order.priority": "express", "http.response.status_code": "500", "error.type": "ValueError", "http.route": "/api/orders/{order_id}"}
    - exception ValueError: day is out of range for month

## Failing request samples (rebuilt from span attributes)
- GET /api/orders/express-1002

## Deployment
- git HEAD: 3982ab3 on hw4-observability
- app container: order-tracker-app-1 order-tracker:local running Up About a minute (healthy) created=2026-09-30 15:06:08 +0200 CEST
- /healthz: 200 {"status":"ok"}
- recent commits:
  - 3982ab3 2026-09-30 15:06:07 +0200 Responder: disable skills/user settings for Claude, gate deploys on the agent's EFFECTIVE extension surface
  - e994e1b 2026-09-30 15:04:56 +0200 Docs + final hardening: README (FR, step-by-step, answers), ops & security report, incident records, audit run; server-side alert fingerprint; drop unused Prometheus flag
  - eaccf39 2026-09-30 14:59:54 +0200 Evidence: email redaction no longer eats Python decorators in JSON transcripts
  - 33e1472 2026-09-30 14:57:19 +0200 Responder: full agent transcript + tool-call summary, human close endpoint, fail-safe cleanup; deploy guard ignores incident records
  - b26220b 2026-09-30 14:50:23 +0200 Evidence: fall back to trace ids from error logs; carry order.id on request logs
  - 8cb2b4f 2026-09-30 14:46:21 +0200 Security audit fixes: CSRF guard, auth on read endpoints, bounded queue, no git in agent tools, clean env for agent tests, redacted transcripts
  - adecc25 2026-09-30 14:35:43 +0200 Responder: require the regression test to fail without the fix (fail-before/pass-after)
  - f4fa8e5 2026-09-30 14:33:28 +0200 Responder: do not leak VIRTUAL_ENV/RESPONDER_TOKEN into runbooks and test runs
