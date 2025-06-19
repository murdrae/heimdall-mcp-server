#!/bin/bash
set -e

# Start script for project-scoped cognitive memory containers
# This script starts existing containers for the current project

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_PATH="$(pwd)"
PROJECT_HASH=$(echo "$PROJECT_PATH" | sha256sum | cut -c1-8)
PROJECT_DATA_DIR="$HOME/.cognitive-memory/projects/$PROJECT_HASH"
COMPOSE_FILE="$PROJECT_DATA_DIR/docker-compose.yml"

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

# Main execution
main() {
    echo "🚀 Starting Cognitive Memory Containers"
    echo "======================================="
    echo ""

    log_info "Project: $PROJECT_PATH"
    log_info "Hash: $PROJECT_HASH"

    # Check if compose file exists
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "No cognitive memory setup found for this project"
        log_info "Run: scripts/setup_project_memory.sh"
        exit 1
    fi

    # Start containers
    log_info "Starting containers..."
    cd "$(dirname "$COMPOSE_FILE")"

    $COMPOSE_CMD -f "$COMPOSE_FILE" up -d

    # Wait for health
    log_info "Waiting for services to become ready..."
    sleep 5

    # Check status
    log_info "Container status:"
    $COMPOSE_CMD -f "$COMPOSE_FILE" ps

    log_success "Containers started successfully"
}

main "$@"
