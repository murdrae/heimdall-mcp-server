#!/bin/bash
set -e

# List all Heimdall MCP projects and their status
# This script shows all configured projects and container status

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECTS_DIR="$HOME/.heimdall-mcp/projects"

# Utility functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Determine compose command
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Get container status
get_container_status() {
    local project_hash="$1"
    local container_name="heimdall-mcp-$project_hash"

    if docker ps --format "table {{.Names}}" | grep -q "$container_name"; then
        echo "🟢 Running"
    elif docker ps -a --format "table {{.Names}}" | grep -q "$container_name"; then
        echo "🔴 Stopped"
    else
        echo "⚪ Not Found"
    fi
}

# Get project path from compose file
get_project_path() {
    local compose_file="$1"
    if [ -f "$compose_file" ]; then
        grep "PROJECT_PATH=" "$compose_file" | head -1 | cut -d'=' -f2 | tr -d '"'
    else
        echo "Unknown"
    fi
}

# Main execution
main() {
    echo "📋 Heimdall MCP Projects"
    echo "============================"
    echo ""

    # Check if projects directory exists
    if [ ! -d "$PROJECTS_DIR" ]; then
        log_info "No Heimdall MCP projects found"
        log_info "Run: scripts/setup_project_memory.sh in any project directory"
        exit 0
    fi

    # Count projects
    project_count=$(find "$PROJECTS_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l)

    if [ "$project_count" -eq 0 ]; then
        log_info "No Heimdall MCP projects found"
        exit 0
    fi

    log_info "Found $project_count configured project(s)"
    echo ""

    # Table header
    printf "%-10s %-10s %-50s %-15s\n" "HASH" "STATUS" "PROJECT PATH" "PORTS"
    printf "%-10s %-10s %-50s %-15s\n" "----" "------" "------------" "-----"

    # List all projects
    for project_dir in "$PROJECTS_DIR"/*; do
        if [ -d "$project_dir" ]; then
            project_hash=$(basename "$project_dir")
            compose_file="$project_dir/docker-compose.yml"

            # Get project information
            status=$(get_container_status "$project_hash")
            project_path=$(get_project_path "$compose_file")

            # Extract ports from compose file
            if [ -f "$compose_file" ]; then
                qdrant_port=$(grep -o '[0-9]*:6333' "$compose_file" | cut -d':' -f1)
                mcp_port=$(grep -o '[0-9]*:8080' "$compose_file" | cut -d':' -f1)
                ports="$qdrant_port,$mcp_port"
            else
                ports="Unknown"
            fi

            # Truncate long paths
            if [ ${#project_path} -gt 47 ]; then
                display_path="...${project_path: -44}"
            else
                display_path="$project_path"
            fi

            printf "%-10s %-10s %-50s %-15s\n" "$project_hash" "$status" "$display_path" "$ports"
        fi
    done

    echo ""
    log_info "Commands:"
    echo "  Start:   scripts/start_memory.sh (from project directory)"
    echo "  Stop:    scripts/stop_memory.sh (from project directory)"
    echo "  Setup:   scripts/setup_project_memory.sh (from project directory)"
    echo "  Cleanup: scripts/cleanup_memory.sh"
}

main "$@"
