FROM ghcr.io/astral-sh/uv:0.11.15 AS uv
FROM python:3.12.13-slim
COPY --from=uv /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-extra forecast
COPY app ./app
COPY tests ./tests
COPY scripts ./scripts
EXPOSE 8000
CMD ["uv", "run", "--frozen", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
