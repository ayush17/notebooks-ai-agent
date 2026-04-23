# DevAssist Container Image
# For deployment on OpenShift/Kubernetes

FROM registry.access.redhat.com/ubi9/python-311:latest

# Set working directory
WORKDIR /app

RUN pip install --no-cache-dir "uv~=0.11.0"

# Lockfile-first install (reproducible)
COPY pyproject.toml README.md uv.lock ./
COPY src/ ./src/

RUN uv sync --frozen --no-dev --no-editable && \
    uv pip install --no-cache-dir psycopg2-binary

COPY scripts/ ./scripts/

# Create non-root user directory for data
RUN mkdir -p /app/data && chmod 777 /app/data

# Set environment variables
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    DEVASSIST_STORAGE=postgres

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "print('healthy')" || exit 1

# Run the daemon worker
CMD ["python", "scripts/daemon_worker.py"]
