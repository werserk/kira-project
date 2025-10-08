# Kira Alpha - Docker Image
# Multi-stage build for production deployment

FROM python:3.12-slim as builder

# Install Poetry
RUN pip install poetry==1.7.1

WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.in-project true && \
    poetry install --no-root --extras agent

# Production stage
FROM python:3.12-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

# Create necessary directories
RUN mkdir -p vault/{tasks,notes,events,inbox,processed,projects} \
    logs artifacts/audit .rag

# Set Python path
ENV PYTHONPATH=/app/src
ENV PATH="/app/.venv/bin:$PATH"

# Expose ports
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5.0)" || exit 1

# Default command
CMD ["uvicorn", "kira.agent.service:create_agent_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
