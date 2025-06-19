# Multi-stage Dockerfile for Cognitive Memory MCP Server
# This creates a production-ready container with all dependencies pre-installed

# ============================================================================
# Builder Stage: Install dependencies and download models
# ============================================================================
FROM python:3.13-slim as builder

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
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Copy source code
COPY . .

# Install the package
RUN pip install -e .

# Pre-download sentence-transformers models to avoid runtime downloads
RUN python -c "
import sentence_transformers
model = sentence_transformers.SentenceTransformer('all-MiniLM-L6-v2')
print('✅ Model downloaded successfully')
"

# ============================================================================
# Runtime Stage: Minimal production image
# ============================================================================
FROM python:3.13-slim as runtime

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r cognitive && useradd -r -g cognitive cognitive

# Set up Python environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/home/cognitive/.local/bin:$PATH"

# Create application directories
RUN mkdir -p /app/data /app/logs /app/models && \
    chown -R cognitive:cognitive /app

# Switch to application directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --from=builder /app /app

# Copy pre-downloaded models
COPY --from=builder /root/.cache/torch/sentence_transformers /home/cognitive/.cache/torch/sentence_transformers

# Fix ownership for copied files
RUN chown -R cognitive:cognitive /app /home/cognitive

# Copy entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create health check script
COPY docker/healthcheck.sh /healthcheck.sh
RUN chmod +x /healthcheck.sh

# Set up environment variables
ENV QDRANT_URL=http://qdrant:6333
ENV MCP_SERVER_HOST=0.0.0.0
ENV MCP_SERVER_PORT=8080
ENV SENTENCE_BERT_MODEL=all-MiniLM-L6-v2
ENV COGNITIVE_MEMORY_DB_PATH=/app/data/cognitive_memory.db
ENV PYTHONPATH=/app

# Expose MCP server port
EXPOSE 8080

# Set up health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD /healthcheck.sh

# Switch to non-root user
USER cognitive

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command
CMD ["memory_system", "serve", "mcp", "--port", "8080", "--host", "0.0.0.0"]
