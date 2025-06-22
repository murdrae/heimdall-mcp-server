#!/bin/bash
# Health check script for Cognitive Memory MCP Server

# Configuration
MCP_SERVER_PORT="${MCP_SERVER_PORT:-8080}"
HEALTH_ENDPOINT="http://localhost:$MCP_SERVER_PORT/health"
MONITORING_ENABLED="${MONITORING_ENABLED:-false}"

# Perform MCP server health check (STDIO-based)
echo "🔍 Checking MCP server health..."
if timeout 10s memory_system doctor --json > /dev/null 2>&1; then
    echo "✅ MCP server health check passed"
    mcp_healthy=true
else
    echo "❌ MCP server health check failed: system doctor check failed"
    mcp_healthy=false
fi

# Perform monitoring service health check if enabled
monitoring_healthy=true
if [ "$MONITORING_ENABLED" = "true" ]; then
    echo "🔍 Checking monitoring service health..."
    if python -m memory_system.monitoring_service --health --json > /dev/null 2>&1; then
        echo "✅ Monitoring service health check passed"
        monitoring_healthy=true
    else
        echo "❌ Monitoring service health check failed"
        monitoring_healthy=false
    fi
else
    echo "🔍 Monitoring service disabled, skipping health check"
fi

# Overall health determination
if [ "$mcp_healthy" = true ] && [ "$monitoring_healthy" = true ]; then
    echo "✅ Overall health check passed"
    exit 0
else
    echo "❌ Overall health check failed"
    exit 1
fi
