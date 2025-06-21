# Multi-stage Dockerfile for Cognitive Memory MCP Server
# This creates a production-ready container with all dependencies pre-installed

# ============================================================================
# Builder Stage: Install dependencies and download models
# ============================================================================
FROM python:3.13-slim AS builder

# Install system dependencies and create app directory
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app

# Set working directory and Python environment
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Copy only files needed for installation first (better caching)
COPY requirements.in pyproject.toml docker/setup-deps.sh ./
COPY docker/entrypoint.sh docker/healthcheck.sh /tmp/

# Install all dependencies, package, and prepare scripts in one layer
RUN pip install --upgrade pip setuptools wheel pip-tools && \
    pip-compile requirements.in && \
    pip install -r requirements.txt && \
    find /usr/local -name "*.pyc" -delete && \
    find /usr/local -type d -name "__pycache__" -exec rm -rf {} + && \
    chmod +x setup-deps.sh && \
    mv /tmp/entrypoint.sh /entrypoint.sh && \
    mv /tmp/healthcheck.sh /healthcheck.sh && \
    chmod +x /entrypoint.sh /healthcheck.sh

# Now copy all source code and complete installation
COPY . .
RUN pip install -e . && \
    ./setup-deps.sh && \
    rm setup-deps.sh && \
    find /usr/local -name "*.pyc" -delete && \
    find /usr/local -type d -name "__pycache__" -exec rm -rf {} +

# ============================================================================
# Runtime Stage: Minimal production image
# ============================================================================
FROM python:3.13-slim AS runtime

# Install runtime system dependencies and setup working directory
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/models /app/data \
    && chmod 755 /app/models /app/data

WORKDIR /app

# Copy only runtime Python packages and binaries (not cache/build artifacts)
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app
COPY --from=builder /entrypoint.sh /healthcheck.sh /

# Set all environment variables in one layer
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    QDRANT_URL=http://qdrant:6333 \
    SQLITE_PATH=/app/data/cognitive_memory.db \
    ONNX_MODEL_PATH=/app/data/models/all-MiniLM-L6-v2.onnx \
    ONNX_TOKENIZER_PATH=/app/data/models/tokenizer \
    ONNX_CONFIG_PATH=/app/data/models/model_config.json \
    LOG_LEVEL=INFO \
    ACTIVATION_THRESHOLD=0.7 \
    BRIDGE_DISCOVERY_K=5 \
    MAX_ACTIVATIONS=50 \
    PYTHONPATH=/app

# No exposed ports - MCP server runs on-demand via stdio

# Set up health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD /healthcheck.sh

# User will be set by docker-compose user mapping

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command - keep container running for on-demand MCP server access
CMD ["tail", "-f", "/dev/null"]
