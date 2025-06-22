#!/bin/bash
set -e

# Entrypoint script for Cognitive Memory MCP Server Container
echo "🧠 Starting Cognitive Memory MCP Server Container"

# Configuration
PROJECT_ID="${PROJECT_ID:-default}"
PROJECT_PATH="${PROJECT_PATH:-/app}"
QDRANT_URL="${QDRANT_URL:-http://qdrant:6333}"
MCP_SERVER_HOST="${MCP_SERVER_HOST:-0.0.0.0}"
MCP_SERVER_PORT="${MCP_SERVER_PORT:-8080}"

echo "📋 Configuration:"
echo "   Project ID: $PROJECT_ID"
echo "   Project Path: $PROJECT_PATH"
echo "   Qdrant URL: $QDRANT_URL"
echo "   MCP Server: $MCP_SERVER_HOST:$MCP_SERVER_PORT"

# Wait for Qdrant to be available
echo "⏳ Waiting for Qdrant to be available..."
timeout=60
while ! curl -s "$QDRANT_URL/health" > /dev/null 2>&1; do
    timeout=$((timeout - 1))
    if [ $timeout -le 0 ]; then
        echo "❌ Timeout waiting for Qdrant at $QDRANT_URL"
        exit 1
    fi
    echo "   Waiting for Qdrant... ($timeout seconds remaining)"
    sleep 1
done
echo "✅ Qdrant is available"

# Create data directories - fail if we can't
if ! mkdir -p /app/data/logs; then
    echo "❌ Failed to create /app/data/logs - check volume permissions"
    exit 1
fi

if ! mkdir -p /app/data/backups; then
    echo "❌ Failed to create /app/data/backups - check volume permissions"
    exit 1
fi

# Create directories expected by health check
if ! mkdir -p /app/data/qdrant; then
    echo "❌ Failed to create /app/data/qdrant - check volume permissions"
    exit 1
fi

if ! mkdir -p /app/data/models; then
    echo "❌ Failed to create /app/data/models - check volume permissions"
    exit 1
fi

# Verify ONNX models exist (should be provisioned by setup script)
if [ -f /app/data/models/model_config.json ]; then
    echo "✅ ONNX models found in project data directory"
else
    echo "⚠️  ONNX models missing - may need to run setup script again"
fi

# Create compatibility symlinks for health check
cd /app
if [ ! -L "data" ]; then
    ln -sf /app/data ./data
fi

# Set up environment for project-specific collections
if [ "$PROJECT_ID" != "default" ]; then
    export QDRANT_COLLECTION_PREFIX="$PROJECT_ID"
    echo "📁 Using project-specific collections with prefix: $PROJECT_ID"
fi

# Initialize cognitive system (this will create collections if they don't exist)
echo "🔧 Initializing cognitive memory system..."
if ! memory_system doctor --json > /dev/null 2>&1; then
    echo "⚠️  System health check failed, but continuing..."
fi

# Log startup completion
echo "✅ Cognitive Memory MCP Server initialized successfully"
echo "🚀 Starting MCP server..."

# Execute the main command
exec "$@"
