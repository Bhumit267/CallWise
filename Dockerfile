# ==============================================================================
# Callwise Backend, Worker, and CLI Multi-stage Production Dockerfile
# ==============================================================================

FROM python:3.12-slim AS builder

WORKDIR /app

# Install build tools and libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /bin/uv

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install application and production dependencies into virtual environment
RUN uv venv /opt/venv && \
    uv pip install --no-cache --python /opt/venv/bin/python .

# ==============================================================================
# Final Runtime Stage
# ==============================================================================
FROM python:3.12-slim AS runner

WORKDIR /app

# Install runtime dependencies (PostgreSQL client for backups, curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy installed virtualenv and application code
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app

# Create unprivileged application user
RUN groupadd -g 1001 callwise && \
    useradd -u 1001 -g callwise -m callwise && \
    mkdir -p /app/backups && \
    chown -R callwise:callwise /app

# Set PATH to use installed virtualenv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER callwise

EXPOSE 8000

# Health check
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command: FastAPI API server
CMD ["python", "-m", "uvicorn", "callwise.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

