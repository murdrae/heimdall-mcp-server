#!/bin/bash

# Generate project hash and container name
PROJECT_HASH=$(echo "$(pwd)" | sha256sum | cut -c1-8)
CONTAINER_NAME="heimdall-mcp-$PROJECT_HASH"

# Run MCP server in container with clean stdio (all logs to /dev/null)
exec docker exec -i "$CONTAINER_NAME" sh -c "memory_system serve mcp 2>/dev/null"
