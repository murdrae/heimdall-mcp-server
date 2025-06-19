#!/bin/bash
set -e

# Setup script for project-scoped cognitive memory containers
# This script detects the current project and sets up isolated Docker containers

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_PATH="$(pwd)"
COGNITIVE_MEMORY_ROOT="$REPO_ROOT"

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

# Generate project hash and derived values
generate_project_config() {
    # Generate 8-character hash from project path
    PROJECT_HASH=$(echo "$PROJECT_PATH" | sha256sum | cut -c1-8)

    # Calculate dynamic ports to avoid conflicts
    # Convert first 3 chars of hash to decimal for port offset
    HASH_DECIMAL=$((16#$(echo "$PROJECT_HASH" | cut -c1-3)))
    QDRANT_PORT=$((6333 + ($HASH_DECIMAL % 1000)))
    MCP_SERVER_PORT=$((8080 + ($HASH_DECIMAL % 1000)))

    # Container and volume names
    CONTAINER_PREFIX="cognitive-memory-$PROJECT_HASH"
    QDRANT_CONTAINER="qdrant-$PROJECT_HASH"

    # Data directories
    PROJECT_DATA_DIR="$HOME/.cognitive-memory/projects/$PROJECT_HASH"

    # Compose file
    COMPOSE_FILE="$PROJECT_DATA_DIR/docker-compose.yml"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker is not running. Please start Docker first."
        exit 1
    fi

    # Check if docker-compose is available
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not available. Please install Docker Compose."
        exit 1
    fi

    # Determine compose command
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi

    log_success "Prerequisites check passed"
}

# Create project-specific compose file
create_compose_file() {
    log_info "Creating project-specific Docker Compose configuration..."

    # Create data directory structure
    mkdir -p "$PROJECT_DATA_DIR"/{qdrant,cognitive,logs,models}

    # Generate compose file from template
    cp "$REPO_ROOT/docker/docker-compose.template.yml" "$COMPOSE_FILE"

    # Substitute variables in compose file
    sed -i.bak \
        -e "s/\${PROJECT_HASH}/$PROJECT_HASH/g" \
        -e "s|\${PROJECT_PATH}|$PROJECT_PATH|g" \
        -e "s/\${QDRANT_PORT}/$QDRANT_PORT/g" \
        -e "s/\${MCP_SERVER_PORT}/$MCP_SERVER_PORT/g" \
        -e "s|\${PROJECT_DATA_DIR}|$PROJECT_DATA_DIR|g" \
        "$COMPOSE_FILE"

    # Remove backup file
    rm -f "$COMPOSE_FILE.bak"

    log_success "Docker Compose file created: $COMPOSE_FILE"
}

# Build cognitive memory image if needed
build_image() {
    log_info "Checking cognitive memory Docker image..."

    cd "$REPO_ROOT"

    # Check if image exists
    if ! docker image inspect cognitive-memory:latest &> /dev/null; then
        log_info "Building cognitive memory Docker image..."
        docker build -f docker/Dockerfile -t cognitive-memory:latest .
        log_success "Docker image built successfully"
    else
        log_info "Docker image already exists"
    fi
}

# Start containers
start_containers() {
    log_info "Starting project containers..."

    cd "$(dirname "$COMPOSE_FILE")"

    # Set build context to repo root
    export DOCKER_BUILDKIT=1

    # Start services
    $COMPOSE_CMD -f "$COMPOSE_FILE" up -d --build

    log_success "Containers started successfully"
}

# Wait for services to be healthy
wait_for_health() {
    log_info "Waiting for services to become healthy..."

    local max_wait=120
    local elapsed=0

    while [ $elapsed -lt $max_wait ]; do
        # Check Qdrant health
        if curl -s -f "http://localhost:$QDRANT_PORT/health" > /dev/null 2>&1; then
            # Check cognitive memory health
            if curl -s -f "http://localhost:$MCP_SERVER_PORT/health" > /dev/null 2>&1; then
                log_success "All services are healthy"
                return 0
            fi
        fi

        echo -n "."
        sleep 2
        elapsed=$((elapsed + 2))
    done

    echo ""
    log_error "Services failed to become healthy within $max_wait seconds"
    return 1
}

# Configure Claude Code MCP
configure_claude_mcp() {
    log_info "Configuring Claude Code MCP integration..."

    # Check if claude command is available
    if ! command -v claude &> /dev/null; then
        log_warning "Claude CLI not found. Skipping MCP configuration."
        log_info "Please install Claude CLI and run: claude mcp add --scope project cognitive-memory http://localhost:$MCP_SERVER_PORT/mcp"
        return 0
    fi

    # Add MCP server to Claude configuration
    if claude mcp add --scope project \
        --name "cognitive-memory-$PROJECT_HASH" \
        --transport http \
        "http://localhost:$MCP_SERVER_PORT/mcp"; then
        log_success "Claude Code MCP configured successfully"
    else
        log_warning "Failed to configure Claude Code MCP. You can configure manually:"
        log_info "claude mcp add --scope project cognitive-memory-$PROJECT_HASH http://localhost:$MCP_SERVER_PORT/mcp"
    fi
}

# Display setup summary
show_summary() {
    echo ""
    echo "🧠 Cognitive Memory Setup Complete"
    echo "=================================="
    echo ""
    echo "Project Information:"
    echo "  Path: $PROJECT_PATH"
    echo "  Hash: $PROJECT_HASH"
    echo ""
    echo "Service URLs:"
    echo "  Qdrant:     http://localhost:$QDRANT_PORT"
    echo "  MCP Server: http://localhost:$MCP_SERVER_PORT/mcp"
    echo "  Health:     http://localhost:$MCP_SERVER_PORT/health"
    echo ""
    echo "Container Names:"
    echo "  Qdrant:    $QDRANT_CONTAINER"
    echo "  Memory:    $CONTAINER_PREFIX"
    echo ""
    echo "Data Directory: $PROJECT_DATA_DIR"
    echo "Compose File:   $COMPOSE_FILE"
    echo ""
    echo "Management Commands:"
    echo "  Start:   $SCRIPT_DIR/start_memory.sh"
    echo "  Stop:    $SCRIPT_DIR/stop_memory.sh"
    echo "  Logs:    $COMPOSE_CMD -f '$COMPOSE_FILE' logs -f"
    echo "  Status:  $COMPOSE_CMD -f '$COMPOSE_FILE' ps"
    echo ""
}

# Cleanup on error
cleanup_on_error() {
    log_error "Setup failed. Cleaning up..."
    if [ -f "$COMPOSE_FILE" ]; then
        cd "$(dirname "$COMPOSE_FILE")"
        $COMPOSE_CMD -f "$COMPOSE_FILE" down --volumes --remove-orphans 2>/dev/null || true
    fi
    rm -f "$COMPOSE_FILE"
}

# Main execution
main() {
    echo "🧠 Cognitive Memory Project Setup"
    echo "================================"
    echo ""

    # Set error handler
    trap cleanup_on_error ERR

    # Generate configuration
    generate_project_config

    log_info "Setting up cognitive memory for project: $PROJECT_PATH"
    log_info "Project hash: $PROJECT_HASH"

    # Check if already configured
    if [ -f "$COMPOSE_FILE" ] && docker ps --format "table {{.Names}}" | grep -q "$CONTAINER_PREFIX"; then
        log_warning "Cognitive memory is already configured for this project"
        show_summary
        exit 0
    fi

    # Execute setup steps
    check_prerequisites
    create_compose_file
    build_image
    start_containers

    # Wait for health and configure
    if wait_for_health; then
        configure_claude_mcp
        show_summary
        log_success "Setup completed successfully!"
    else
        log_error "Setup failed - services are not healthy"
        exit 1
    fi
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [options]"
        echo ""
        echo "Setup project-scoped cognitive memory containers"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --cleanup      Remove all project containers and data"
        echo "  --rebuild      Force rebuild of Docker image"
        echo ""
        exit 0
        ;;
    --cleanup)
        generate_project_config
        log_info "Cleaning up project containers..."
        if [ -f "$COMPOSE_FILE" ]; then
            cd "$(dirname "$COMPOSE_FILE")"
            $COMPOSE_CMD -f "$COMPOSE_FILE" down --volumes --remove-orphans
            rm -rf "$PROJECT_DATA_DIR"
            log_success "Cleanup completed"
        else
            log_info "No containers found to clean up"
        fi
        exit 0
        ;;
    --rebuild)
        cd "$REPO_ROOT"
        docker rmi cognitive-memory:latest 2>/dev/null || true
        ;;
esac

# Run main function
main "$@"
