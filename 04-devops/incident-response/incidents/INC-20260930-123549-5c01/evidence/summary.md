# Evidence packet (2026-09-30T12:35:49.796981+00:00)

- Route under investigation: `/api/orders/{order_id}`
- Window: last 15 min

## Metrics (Prometheus)
- **five_xx_last_5m** `sum by (http_route, error_type, service_version) ((app_http_requests_total{job="order-tracker", http_response_status_code=~"5..", http_route="/api/orders/{order_id}"} unless app_http_requests_total{job="order-tracker", http_response_status_code=~"5..", http_route="/api/orders/{order_id}"} offset 5m) or increase(app_http_requests_total{job="order-tracker", http_response_status_code=~"5..", http_route="/api/orders/{order_id}"}[5m]))`
  - {"error_type": "ValueError", "http_route": "/api/orders/{order_id}", "service_version": "e15f0ca"} = 3
  - {"error_type": "ValueError", "http_route": "/api/orders/{order_id}", "service_version": "33ab4e7"} = 3
  - {"error_type": "ValueError", "http_route": "/api/orders/{order_id}", "service_version": "310c7b5"} = 3
- **requests_by_status_window** `sum by (http_route, http_response_status_code) (increase(app_http_requests_total{job="order-tracker", http_route="/api/orders/{order_id}"}[15m]))`
  - {"http_response_status_code": "404", "http_route": "/api/orders/{order_id}"} = 0
  - {"http_response_status_code": "500", "http_route": "/api/orders/{order_id}"} = 2.4
  - {"http_response_status_code": "200", "http_route": "/api/orders/{order_id}"} = 1.0666666666666667
- **cumulative_by_status** `sum by (http_route, http_response_status_code, error_type) (app_http_requests_total{job="order-tracker", http_route="/api/orders/{order_id}"})`
  - {"http_response_status_code": "404", "http_route": "/api/orders/{order_id}"} = 1
  - {"error_type": "ValueError", "http_response_status_code": "500", "http_route": "/api/orders/{order_id}"} = 9
  - {"http_response_status_code": "200", "http_route": "/api/orders/{order_id}"} = 4
- **deployed_versions** `count by (service_version) (app_http_requests_total{job="order-tracker"})`
  - {"service_version": "e15f0ca"} = 3
  - {"service_version": "87df816"} = 2
  - {"service_version": "33ab4e7"} = 3
  - {"service_version": "310c7b5"} = 2

## Error logs (Loki)
`{service_name="order-tracker"} | severity_text="ERROR" | http_route="/api/orders/{order_id}"` -> 9 line(s)
- 2026-09-30T12:34:59.618522+00:00 GET /api/orders/{order_id} -> 500 trace_id=abe4a7b4df6bc6f9b3a2332bdfc97556 exception=ValueError: day is out of range for month
- 2026-09-30T12:34:59.604446+00:00 GET /api/orders/{order_id} -> 500 trace_id=f4095c12b0c45cbc1fcbd32add692090 exception=ValueError: day is out of range for month
- 2026-09-30T12:34:59.585567+00:00 GET /api/orders/{order_id} -> 500 trace_id=082d23e2ddde7ad98da6f9d1622c332b exception=ValueError: day is out of range for month
- 2026-09-30T12:34:30.484068+00:00 GET /api/orders/{order_id} -> 500 trace_id=6a133ac76951ac67aa4bd0fcb9040e72 exception=ValueError: day is out of range for month
- 2026-09-30T12:34:30.470127+00:00 GET /api/orders/{order_id} -> 500 trace_id=794a7804c74a7dbfd40d42eb09db06a4 exception=ValueError: day is out of range for month

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
  File "/app/app/main.py", line 198, in get_order
    detail = order_detail(row)
             ^^^^^^^^^^^^^^^^^
  File "/app/app/main.py", line 82, in order_detail
    estimated_at = placed_at.replace(day=placed_at.day + 2)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ValueError: day is out of range for month

```

## Error traces (Tempo)
`{resource.service.name="order-tracker" && status=error && span.http.route="/api/orders/{order_id}"}` -> 5 trace(s)
- trace 6a133ac76951ac67aa4bd0fcb9040e72 `GET /api/orders/{order_id}` 4 ms at 2026-09-30T12:34:30.481232+00:00
  - span `orders.db.select` status=UNSET {}
  - span `orders.build_detail` status=STATUS_CODE_ERROR {"order.priority": "express"}
    - exception ValueError: day is out of range for month
  - span `GET /api/orders/{order_id}` status=STATUS_CODE_ERROR {"order.id": "express-1002", "order.priority": "express", "http.response.status_code": "500", "error.type": "ValueError", "http.route": "/api/orders/{order_id}"}
    - exception ValueError: day is out of range for month
- trace 7774462981528e5d18c38ab797389942 `GET /api/orders/{order_id}` 9 ms at 2026-09-30T12:34:19.446569+00:00
  - span `orders.db.select` status=UNSET {}
  - span `orders.build_detail` status=STATUS_CODE_ERROR {"order.priority": "express"}
    - exception ValueError: day is out of range for month
  - span `GET /api/orders/{order_id}` status=STATUS_CODE_ERROR {"order.id": "express-1002", "order.priority": "express", "http.response.status_code": "500", "error.type": "ValueError", "http.route": "/api/orders/{order_id}"}
    - exception ValueError: day is out of range for month
- trace cece1524576476832fcd9d28aab22de5 `GET /api/orders/{order_id}` 4 ms at 2026-09-30T12:32:01.031183+00:00
  - span `orders.db.select` status=UNSET {}
  - span `orders.build_detail` status=STATUS_CODE_ERROR {"order.priority": "express"}
    - exception ValueError: day is out of range for month
  - span `GET /api/orders/{order_id}` status=STATUS_CODE_ERROR {"order.id": "express-1002", "order.priority": "express", "http.response.status_code": "500", "error.type": "ValueError", "http.route": "/api/orders/{order_id}"}
    - exception ValueError: day is out of range for month

## Failing request samples (rebuilt from span attributes)
- GET /api/orders/express-1002

## Deployment
- git HEAD: 32fc289 on drill/rollback
- app container: order-tracker-app-1 order-tracker:rollback-inc-20260930-123438-47f5 running Up 37 seconds (healthy) created=2026-09-30 14:35:11 +0200 CEST
- /healthz: 200 {"status":"ok"}
- recent commits:
  - 32fc289 2026-09-30 14:35:43 +0200 Responder: require the regression test to fail without the fix (fail-before/pass-after)
  - 33ab4e7 2026-09-30 14:34:12 +0200 Revert "fix(INC-20260930-123213-e999): GET /api/orders/express-1002 returns 500 (ValueError: day is out of rang"
  - 10a52d6 2026-09-30 14:33:28 +0200 Responder: do not leak VIRTUAL_ENV/RESPONDER_TOKEN into runbooks and test runs
  - 87df816 2026-09-30 14:32:37 +0200 fix(INC-20260930-123213-e999): GET /api/orders/express-1002 returns 500 (ValueError: day is out of rang
  - e15f0ca 2026-09-30 14:30:11 +0200 Responder: strip $schema for Claude CLI validator, load .env, .env.example
  - 909fb6a 2026-09-30 14:28:36 +0200 Add incident responder: evidence packet, headless agent adapter, autonomy policy, runbooks
  - a35f496 2026-09-30 14:22:35 +0200 Add telemetry pipeline: Collector, Prometheus, Loki, Tempo, Grafana (dashboard, 5xx alert, webhook)
  - 3c85469 2026-09-30 14:18:04 +0200 Instrument order lookups with OpenTelemetry (metrics, traces, logs)
