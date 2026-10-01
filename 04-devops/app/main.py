import logging
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from opentelemetry import metrics, propagate, trace
from opentelemetry.trace import SpanKind, Status, StatusCode
from pydantic import BaseModel, Field

from app.telemetry import log, setup_telemetry

setup_telemetry()
tracer = trace.get_tracer("order_tracker")
meter = metrics.get_meter("order_tracker")
REQUESTS = meter.create_counter(
    "app.http.requests",
    unit="{request}",
    description="HTTP requests handled, by method, route template and status code",
)
DURATION = meter.create_histogram(
    "http.server.request.duration",
    unit="s",
    description="Duration of HTTP server requests",
    explicit_bucket_boundaries_advisory=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
)
# Routes whose traces/logs are noise (Docker healthcheck every 5s). Still counted in metrics.
UNTRACED_PATHS = {"/healthz"}


DB_PATH = Path(os.getenv("ORDER_DB_PATH", "data/orders.db"))
STATUSES = {"received", "preparing", "shipped", "delivered"}


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with connect() as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                customer TEXT NOT NULL,
                item TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        if db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
            now = datetime.now(timezone.utc)
            previous_month_end = now.replace(day=1) - timedelta(days=1)
            for order in (
                ("standard-1001", "Avery", "Notebook", "standard", "received", now),
                ("express-1002", "Sam", "Headphones", "express", "preparing", previous_month_end),
                ("standard-1003", "Riley", "Water bottle", "standard", "shipped", now),
            ):
                db.execute(
                    "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)",
                    (*order[:5], order[5].isoformat()),
                )


def as_dict(row):
    return dict(row) if row else None


def order_detail(row):
    order = as_dict(row)
    if order["priority"] == "express":
        placed_at = datetime.fromisoformat(order["created_at"])
        estimated_at = placed_at.replace(day=placed_at.day + 2)
        order["estimated_delivery"] = estimated_at.date().isoformat()
    return order


class NewOrder(BaseModel):
    customer: str = Field(min_length=1, max_length=80)
    item: str = Field(min_length=1, max_length=120)
    priority: str = "standard"


class StatusUpdate(BaseModel):
    status: str


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


def _fastapi_kwargs() -> dict:
    """Recent FastAPI releases ship built-in OpenTelemetry that auto-attaches exporters
    from the OTEL_* env vars. Left on, it duplicates every span/metric we emit and it
    records url.query and validation input values (PII risk). Our middleware is the single
    source of truth, so the native layer is switched off when it exists."""
    import inspect

    if "telemetry" in inspect.signature(FastAPI.__init__).parameters:
        return {"telemetry": {"auto_configure": False, "tracing": False, "metrics": False,
                              "logs": False, "operation_spans": False}}
    return {}


app = FastAPI(title="Order Tracker", lifespan=lifespan, **_fastapi_kwargs())


@app.middleware("http")
async def telemetry_middleware(request: Request, call_next):
    """One SERVER span, one counter increment, one duration sample and one
    structured log per request. Unhandled exceptions are recorded as 500s."""
    method = request.method
    traced = request.url.path not in UNTRACED_PATHS
    ctx = propagate.extract(dict(request.headers)) if traced else None
    start = time.perf_counter()
    status_code = 500
    error_type = None
    span_cm = (
        tracer.start_as_current_span(method, context=ctx, kind=SpanKind.SERVER, record_exception=False,
                                     set_status_on_exception=False)
        if traced else trace.use_span(trace.INVALID_SPAN)
    )
    with span_cm as span:
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:  # unhandled -> Starlette answers 500
            error_type = type(exc).__name__
            span.record_exception(exc)
            raise
        finally:
            route_obj = request.scope.get("route")
            route = getattr(route_obj, "path", None) or "unmatched"
            elapsed = time.perf_counter() - start
            attrs = {
                "http.request.method": method,
                "http.route": route,
                "http.response.status_code": status_code,
            }
            if status_code >= 500:
                attrs["error.type"] = error_type or str(status_code)
            REQUESTS.add(1, attrs)
            DURATION.record(elapsed, attrs)
            if traced:
                span.update_name(f"{method} {route}")
                span.set_attributes(attrs)
                if status_code >= 500:
                    span.set_status(Status(StatusCode.ERROR, error_type or "server error"))
                order_id = getattr(span, "attributes", {}).get("order.id")
                if order_id:  # business id, not PII; lets an investigator replay the exact request
                    attrs = {**attrs, "order.id": order_id}
                level = logging.ERROR if status_code >= 500 else logging.INFO
                log(level, f"{method} {route} -> {status_code}",
                    {**attrs, "http.server.duration_ms": round(elapsed * 1000, 2)},
                    exc_info=error_type is not None)


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent.parent / "static" / "index.html")


@app.get("/healthz")
def health():
    with connect() as db:
        db.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/api/orders")
def list_orders():
    with connect() as db:
        rows = db.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    return [as_dict(row) for row in rows]


@app.get("/api/orders/{order_id}")
def get_order(order_id: str):
    span = trace.get_current_span()
    span.set_attribute("order.id", order_id)
    with tracer.start_as_current_span("orders.db.select", attributes={"db.system.name": "sqlite"}):
        with connect() as db:
            row = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        log(logging.INFO, "order lookup: not found", {"order.id": order_id})
        raise HTTPException(404, "Order not found")
    span.set_attribute("order.priority", row["priority"])
    with tracer.start_as_current_span("orders.build_detail", attributes={"order.priority": row["priority"]}):
        detail = order_detail(row)
    log(logging.INFO, "order lookup: ok", {"order.id": order_id, "order.priority": row["priority"]})
    return detail


@app.post("/api/orders", status_code=201)
def create_order(order: NewOrder):
    if order.priority not in {"standard", "express"}:
        raise HTTPException(422, "Priority must be standard or express")
    order_id = str(uuid4())
    with connect() as db:
        db.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)",
            (order_id, order.customer, order.item, order.priority, "received",
             datetime.now(timezone.utc).isoformat()),
        )
    return get_order(order_id)


@app.patch("/api/orders/{order_id}")
def update_status(order_id: str, update: StatusUpdate):
    if update.status not in STATUSES:
        raise HTTPException(422, "Invalid status")
    with connect() as db:
        cursor = db.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (update.status, order_id),
        )
    if cursor.rowcount == 0:
        raise HTTPException(404, "Order not found")
    return get_order(order_id)
