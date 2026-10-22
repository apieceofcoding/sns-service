FROM python:3.13-slim
RUN pip install --no-cache-dir uv==0.6.16
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src src
COPY sql sql
COPY data data
COPY README.md .
RUN uv sync --locked --no-dev
ENV PYTHONUNBUFFERED=1 UV_NO_SYNC=1
CMD ["uv", "run", "sns-recommend-batch"]
