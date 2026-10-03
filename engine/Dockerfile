# Build from the REPO ROOT (needs config/, contracts/ and data/processed/):
#   docker build -f engine/Dockerfile -t kompas-engine .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    CONFIG_DIR=/app/config DATA_DIR=/app/data/processed
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app/engine
COPY engine/pyproject.toml engine/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# whitelisted by /.dockerignore: engine/app, engine/models, config, contracts (api + validators), data/processed (if present)
COPY . /app/
# bake the data: validate, train/load the archetype model, write the static fallback export
RUN .venv/bin/python -m app.warmup

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",\"8000\")}/api/health')"
CMD ["sh", "-c", "exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-1}"]
