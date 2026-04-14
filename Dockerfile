# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (layer cache)
COPY pyproject.toml .
COPY src/ src/

# Install into a virtual env inside the image
RUN uv venv /app/.venv && \
    uv pip install --python /app/.venv/bin/python -e .

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash trader

# Copy virtualenv from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

# Data directory for SQLite (mount a volume here)
RUN mkdir -p /data && chown trader:trader /data

USER trader

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["t212"]
CMD ["--help"]
