# Multi-stage build: dependencies are resolved from uv.lock in a builder stage,
# the runtime image only gets the virtualenv + application code, runs as a
# non-root user and listens on 0.0.0.0 so `-p` / Services can reach it.

ARG PYTHON_IMAGE=python:3.11.15-slim

FROM ${PYTHON_IMAGE} AS builder
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
RUN pip install --no-cache-dir --root-user-action=ignore "uv==0.12.*"
WORKDIR /app
# Dependency layer first: only invalidated when the lockfile changes.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project

FROM ${PYTHON_IMAGE} AS runtime
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RELAY_DATABASE_URL=sqlite:////data/agent-relay.db
RUN groupadd --system --gid 10001 relay \
 && useradd --system --uid 10001 --gid relay --home-dir /app --no-create-home relay \
 && mkdir -p /data && chown relay:relay /data
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --chown=relay:relay main.py database.py storage.py schemas.py errors.py dashboard.py worker.py dashboard.html ./
USER 10001
EXPOSE 8000
# Liveness only; readiness (DB + schema) is /ready and is used by Compose/K8s.
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]
# --host 0.0.0.0: uvicorn defaults to 127.0.0.1, which is unreachable through -p.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
