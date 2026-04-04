FROM python:3.12-slim

WORKDIR /app

RUN pip install uv --no-cache-dir

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/
COPY public/ ./public/

EXPOSE 3001

CMD ["/bin/sh", "-c", "/app/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-3001}"]
