# Multi-stage Dockerfile for Cognitive Memory MCP Server
# This creates a production-ready container with all dependencies pre-installed

# ============================================================================
# Builder Stage: Install dependencies and download models
# ============================================================================
FROM python:3.13-slim AS builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set up Python environment
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Create application directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.in ./

# Install pip-tools and generate requirements.txt
RUN pip install --upgrade pip setuptools wheel pip-tools && \
    pip-compile requirements.in && \
    pip install -r requirements.txt

# Copy source code
COPY . .

# Install the package
RUN pip install -e .

# Pre-download sentence-transformers models to avoid runtime downloads
RUN mkdir -p /app/models && \
    python -c "\
import sentence_transformers; \
import os; \
os.environ['SENTENCE_TRANSFORMERS_HOME'] = '/app/models'; \
model = sentence_transformers.SentenceTransformer('all-MiniLM-L6-v2'); \
print('✅ Model downloaded successfully')"

# ============================================================================
# Runtime Stage: Minimal production image
# ============================================================================
FROM python:3.13-slim AS runtime

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# No need to create users - we'll run as host user via docker-compose

# Set up Python environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/home/cognitive/.local/bin:$PATH"

# Create application directories
RUN mkdir -p /app/data /app/logs /app/models

# Switch to application directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --from=builder /app /app

# Copy pre-downloaded models
COPY --from=builder /app/models /app/models

# Just copy the files - permissions will be handled by user mapping
# No need for complex ownership changes

# Copy entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create health check script
COPY docker/healthcheck.sh /healthcheck.sh
RUN chmod +x /healthcheck.sh

# Set up environment variables (consistent with .env.template)
ENV QDRANT_URL=http://qdrant:6333
ENV SQLITE_PATH=/app/data/cognitive_memory.db
ENV SENTENCE_BERT_MODEL=all-MiniLM-L6-v2
ENV MODEL_CACHE_DIR=/app/models
ENV SENTENCE_TRANSFORMERS_HOME=/app/models
ENV LOG_LEVEL=INFO
ENV ACTIVATION_THRESHOLD=0.7
ENV BRIDGE_DISCOVERY_K=5
ENV MAX_ACTIVATIONS=50
ENV PYTHONPATH=/app
# HOME will be set by user mapping in docker-compose

# No exposed ports - MCP server runs on-demand via stdio

# Set up health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD /healthcheck.sh

# User will be set by docker-compose user mapping

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command - keep container running for on-demand MCP server access
CMD ["tail", "-f", "/dev/null"]
