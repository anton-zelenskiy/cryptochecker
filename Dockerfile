FROM python:3.14-slim

WORKDIR /project

# Install uv binary (preferred) without pip
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./

# Use a fixed venv path inside the container image
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Install deps (cache uv downloads)
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project

COPY . .

# RUN chmod -R 755 /opt/venv

ENV PYTHONPATH=/project
ENV PATH="/opt/venv/bin:$PATH"
