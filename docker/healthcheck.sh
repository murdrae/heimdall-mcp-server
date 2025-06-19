#!/bin/bash
# Health check script for Cognitive Memory MCP Server

# Configuration
MCP_SERVER_PORT="${MCP_SERVER_PORT:-8080}"
HEALTH_ENDPOINT="http://localhost:$MCP_SERVER_PORT/health"

# Perform health check
if response=$(curl -s -f "$HEALTH_ENDPOINT" 2>/dev/null); then
    # Parse JSON response to check status
    if echo "$response" | grep -q '"status":"healthy"'; then
        echo "✅ Health check passed"
        exit 0
    else
        echo "❌ Health check failed: unhealthy status"
        echo "Response: $response"
        exit 1
    fi
else
    echo "❌ Health check failed: unable to reach $HEALTH_ENDPOINT"
    exit 1
fi
