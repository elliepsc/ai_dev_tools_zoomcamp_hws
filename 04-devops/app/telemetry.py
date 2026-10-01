"""OpenTelemetry setup for Order Tracker: traces, metrics and logs.

Exporters are chosen with the standard OpenTelemetry variables, one per signal:

    OTEL_TRACES_EXPORTER / OTEL_METRICS_EXPORTER / OTEL_LOGS_EXPORTER
        "otlp"    -> OTLP/HTTP to OTEL_EXPORTER_OTLP_ENDPOINT (the Collector)
        "console" -> JSON on stdout (read it with `docker compose logs app`)
        "none"    -> disabled (default, keeps unit tests quiet)

Design rules (see docs/operations-and-security-report.md):
- Metric attributes are low-cardinality only: method, route *template*, status code,
  error type. Never the raw path, the order id or the customer.
- No request/response bodies, headers or query strings are recorded anywhere.
- Every log record emitted inside a request carries the trace_id/span_id, so a
  log line, its trace and its metric can be joined during an investigation.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogRecordExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "order-tracker")
LOGGER_NAME = "order_tracker"

_configured = False


def _exporter_choice(signal: str) -> str:
    value = os.getenv(f"OTEL_{signal}_EXPORTER", "none").strip().lower()
    return value if value in {"otlp", "console", "none"} else "none"


def _resource() -> Resource:
    return Resource.create(
        {
            "service.name": SERVICE_NAME,
            "service.version": os.getenv("APP_VERSION", "dev"),
            # One id per process: after a restart counters start a new series instead of
            # "going backwards" on the old one (Prometheus label: instance).
            "service.instance.id": str(uuid.uuid4()),
            "deployment.environment.name": os.getenv("DEPLOYMENT_ENVIRONMENT", "local"),
        }
    )


_STANDARD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime", "taskName"}


class _JsonStdoutFormatter(logging.Formatter):
    """One JSON object per line on stdout, with trace correlation ids."""

    def format(self, record: logging.LogRecord) -> str:
        span_ctx = trace.get_current_span().get_span_context()
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "trace_id": format(span_ctx.trace_id, "032x") if span_ctx.is_valid else None,
            "span_id": format(span_ctx.span_id, "016x") if span_ctx.is_valid else None,
        }
        payload.update({k: v for k, v in record.__dict__.items() if k not in _STANDARD_ATTRS})
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_telemetry() -> None:
    """Configure global providers once. Safe to call several times."""
    global _configured
    if _configured:
        return
    _configured = True

    resource = _resource()
    interval_ms = int(os.getenv("OTEL_METRIC_EXPORT_INTERVAL", "5000"))

    # Traces
    tracer_provider = TracerProvider(resource=resource)
    choice = _exporter_choice("TRACES")
    if choice == "otlp":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    elif choice == "console":
        tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    readers = []
    choice = _exporter_choice("METRICS")
    if choice == "otlp":
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

        readers.append(PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=interval_ms))
    elif choice == "console":
        readers.append(
            PeriodicExportingMetricReader(ConsoleMetricExporter(), export_interval_millis=interval_ms)
        )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=readers))

    # Logs: OTel pipeline (Loki via the Collector) + JSON on stdout as a fallback.
    app_logger = logging.getLogger(LOGGER_NAME)
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False
    choice = _exporter_choice("LOGS")
    if choice in {"otlp", "console"}:
        logger_provider = LoggerProvider(resource=resource)
        if choice == "otlp":
            from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

            logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
        else:
            logger_provider.add_log_record_processor(BatchLogRecordProcessor(ConsoleLogRecordExporter()))
        set_logger_provider(logger_provider)
        app_logger.addHandler(LoggingHandler(level=logging.INFO, logger_provider=logger_provider))
    if choice != "console":  # console mode already prints every record as JSON
        stdout = logging.StreamHandler(sys.stdout)
        stdout.setFormatter(_JsonStdoutFormatter())
        app_logger.addHandler(stdout)


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def log(level: int, msg: str, attrs: dict, exc_info=None) -> None:
    """Log with OTel attributes (become Loki structured metadata)."""
    get_logger().log(level, msg, extra=attrs, exc_info=exc_info, stacklevel=2)
