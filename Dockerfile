# syntax=docker/dockerfile:1
FROM python:3.13-slim-bookworm AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0 UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

FROM python:3.13-slim-bookworm
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BOOZERUN_ENV_PATH=/run/secrets/beer-run.env \
    BOOZERUN_DATABASE_PATH=/state/boozerun.db \
    SQLALCHEMY_DATABASE_URL=sqlite:////state/boozerun.db \
    BOOZERUN_UPLOAD_ROOT=/state/uploads \
    BOOZERUN_DATA_ROOT=/state/data \
    BOOZERUN_QUARANTINE_ROOT=/state/quarantine
COPY --from=dependencies /app/.venv /app/.venv
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY data/drinks.json ./seed-data/drinks.json
USER 1000:1000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/config', timeout=3).read()"]
CMD ["uvicorn", "beer_run.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
