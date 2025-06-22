#!/bin/bash
set -e

# Simple setup for Claude Code MCP integration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_HASH=$(echo "$(pwd)" | sha256sum | cut -c1-8)
REPO_NAME=$(basename "$(pwd)")
MCP_NAME="heimdall-$REPO_NAME-$PROJECT_HASH"
WRAPPER_SCRIPT="$SCRIPT_DIR/scripts/claude_mcp_wrapper.sh"

echo "🧠 Setting up Claude Code MCP for Heimdall..."

# Setup containers (ignore health check failure since we use stdio not HTTP)
"$SCRIPT_DIR/scripts/setup_project_memory.sh" "${1:-}" || true

# Configure Claude MCP
if claude mcp list | grep -q "$MCP_NAME"; then
    echo "⚠️  MCP already configured: $MCP_NAME"
else
    claude mcp add --scope project --transport stdio "$MCP_NAME" "$WRAPPER_SCRIPT"
    echo "✅ MCP configured: $MCP_NAME"
fi

echo "✅ Setup complete! MCP tools available in Claude Code."
