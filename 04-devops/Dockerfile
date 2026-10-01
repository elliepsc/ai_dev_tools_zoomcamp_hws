FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app ./app
COPY static ./static

# Version stamped at build time (git sha) -> OTel resource attribute service.version,
# so every metric/log/trace can be tied to the deployment that produced it.
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION} \
    ORDER_DB_PATH=/data/orders.db \
    PATH=/app/.venv/bin:$PATH

# Run as an unprivileged user.
RUN useradd --system --uid 10001 --no-create-home app && mkdir -p /data && chown app /data
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
