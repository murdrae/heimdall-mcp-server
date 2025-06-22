#!/bin/bash
set -e

# Setup script for project-scoped Heimdall MCP containers
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
    CONTAINER_PREFIX="heimdall-mcp-$PROJECT_HASH"
    QDRANT_CONTAINER="qdrant-$PROJECT_HASH"

    # Data directories - store in project directory
    PROJECT_DATA_DIR="$PROJECT_PATH/.heimdall-mcp"

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
    # Create heimdall directory structure (mounted as /app/data in container)
    mkdir -p "$PROJECT_DATA_DIR"/heimdall/{logs,backups,qdrant,models}

    # Copy ONNX models from main repo if they exist and aren't already present
    if [ ! -f "$PROJECT_DATA_DIR/heimdall/models/model_config.json" ]; then
        if [ -f "$REPO_ROOT/data/models/model_config.json" ]; then
            log_info "Provisioning ONNX models from main repository..."
            cp -r "$REPO_ROOT/data/models"/* "$PROJECT_DATA_DIR/heimdall/models/"
            log_success "ONNX models provisioned successfully"
        else
            log_warning "ONNX models not found in main repo - run 'python scripts/convert_model_to_onnx.py' first"
        fi
    else
        log_info "ONNX models already exist in project"
    fi

    # Only set permissions on new/empty directories to avoid conflicts with running containers
    if [ ! -f "$PROJECT_DATA_DIR/cognitive/cognitive_memory.db" ]; then
        chmod -R 755 "$PROJECT_DATA_DIR/cognitive" 2>/dev/null || true
    fi

    # Generate compose file from template
    cp "$REPO_ROOT/docker/docker-compose.template.yml" "$COMPOSE_FILE"

    # Get host user/group IDs to ensure proper file ownership
    HOST_UID=$(id -u)
    HOST_GID=$(id -g)

    log_info "Using host UID:GID $HOST_UID:$HOST_GID for container user mapping"

    # Substitute variables in compose file
    sed -i.bak \
        -e "s/\${PROJECT_HASH}/$PROJECT_HASH/g" \
        -e "s|\${PROJECT_PATH}|$PROJECT_PATH|g" \
        -e "s/\${QDRANT_PORT}/$QDRANT_PORT/g" \
        -e "s/\${MCP_SERVER_PORT}/$MCP_SERVER_PORT/g" \
        -e "s|\${PROJECT_DATA_DIR}|$PROJECT_DATA_DIR|g" \
        -e "s/\${HOST_UID}/$HOST_UID/g" \
        -e "s/\${HOST_GID}/$HOST_GID/g" \
        "$COMPOSE_FILE"

    # Remove backup file
    rm -f "$COMPOSE_FILE.bak"

    log_success "Docker Compose file created: $COMPOSE_FILE"
}

# Build Heimdall MCP image if needed
build_image() {
    log_info "Checking Heimdall MCP Docker image..."

    cd "$REPO_ROOT"

    local image_name="heimdall-mcp:$PROJECT_HASH"
    local build_args=""

    # Check if rebuild was requested or image doesn't exist
    if [[ "${FORCE_REBUILD:-}" == "true" ]]; then
        log_info "Force rebuilding Heimdall MCP Docker image: $image_name"
        DOCKER_BUILDKIT=1 docker build -f docker/Dockerfile -t "$image_name" .
        log_success "Docker image rebuilt successfully: $image_name"
    elif ! docker image inspect "$image_name" &> /dev/null; then
        log_info "Building project-specific Heimdall MCP Docker image: $image_name"
        DOCKER_BUILDKIT=1 docker build -f docker/Dockerfile -t "$image_name" .
        log_success "Docker image built successfully: $image_name"
    else
        log_info "Project-specific Docker image already exists: $image_name"
    fi
}

# Start containers
start_containers() {
    log_info "Starting project containers..."

    # Change to repo root for build context
    cd "$REPO_ROOT"

    # Set build context to repo root
    export DOCKER_BUILDKIT=1

    # Start services with correct compose file path
    $COMPOSE_CMD -f "$COMPOSE_FILE" up -d --build

    log_success "Containers started successfully"
}

# Wait for services to be healthy
wait_for_health() {
    log_info "Waiting for services to become healthy..."

    # First check Qdrant
    log_info "Checking Qdrant health..."
    local max_wait=30
    local elapsed=0

    while [ $elapsed -lt $max_wait ]; do
        if curl -s -f "http://localhost:$QDRANT_PORT/" > /dev/null 2>&1; then
            log_success "QDRANT is healthy"
            break
        fi
        echo -n "."
        sleep 2
        elapsed=$((elapsed + 2))
    done

    if [ $elapsed -ge $max_wait ]; then
        echo ""
        log_error "Qdrant failed to become healthy within $max_wait seconds"
        return 1
    fi

    # Then check our container
    log_info "Checking Heimdall MCP container health..."
    elapsed=0

    while [ $elapsed -lt $max_wait ]; do
        if docker exec "$CONTAINER_PREFIX" memory_system doctor --json > /dev/null 2>&1; then
            log_success "Heimdall MCP container is healthy"
            log_success "All services are healthy"
            return 0
        fi
        echo -n "."
        sleep 2
        elapsed=$((elapsed + 2))
    done

    echo ""
    log_error "Heimdall MCP container failed to become healthy within $max_wait seconds"
    return 1
}


# Display setup summary
show_summary() {
    echo ""
    echo "🧠 Heimdall MCP Setup Complete"
    echo "=================================="
    echo ""
    echo "Project Information:"
    echo "  Path: $PROJECT_PATH"
    echo "  Hash: $PROJECT_HASH"
    echo ""
    echo "Qdrant:     http://localhost:$QDRANT_PORT"
    echo "Data:       $PROJECT_DATA_DIR"
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
    echo "🧠 Heimdall MCP Project Setup"
    echo "================================"
    echo ""

    # Set error handler
    trap cleanup_on_error ERR

    # Generate configuration
    generate_project_config

    log_info "Setting up Heimdall MCP for project: $PROJECT_PATH"
    log_info "Project hash: $PROJECT_HASH"

    # Check if already configured (skip if rebuilding)
    if [[ "${FORCE_REBUILD:-}" != "true" ]] && [ -f "$COMPOSE_FILE" ] && docker ps --format "table {{.Names}}" | grep -q "$CONTAINER_PREFIX"; then
        log_warning "Heimdall MCP is already configured for this project"
        show_summary
        exit 0
    fi

    # Execute setup steps
    check_prerequisites
    create_compose_file
    build_image
    start_containers

    # Wait for health and show summary
    if wait_for_health; then
        show_summary
        log_success "Setup completed successfully!"
        log_info "Use setup_claude_code_mcp.sh for MCP configuration"
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
        echo "Setup project-scoped Heimdall MCP containers"
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
        # Initialize compose command
        if docker compose version &> /dev/null; then
            COMPOSE_CMD="docker compose"
        else
            COMPOSE_CMD="docker-compose"
        fi
        log_info "Cleaning up project containers..."
        if [ -f "$COMPOSE_FILE" ]; then
            cd "$(dirname "$COMPOSE_FILE")"
            $COMPOSE_CMD -f "$COMPOSE_FILE" down --volumes --remove-orphans

            # Fix any permission issues before removal
            if [ -d "$PROJECT_DATA_DIR" ]; then
                log_info "Fixing permissions before cleanup..."
                # Try to fix ownership if needed (will fail gracefully if not needed)
                docker run --rm -v "$PROJECT_DATA_DIR:/cleanup" --user root alpine chown -R $(id -u):$(id -g) /cleanup 2>/dev/null || true
                rm -rf "$PROJECT_DATA_DIR"
            fi
            log_success "Cleanup completed"
        else
            log_info "No containers found to clean up"
        fi
        exit 0
        ;;
    --rebuild)
        generate_project_config
        # Initialize compose command
        if docker compose version &> /dev/null; then
            COMPOSE_CMD="docker compose"
        else
            COMPOSE_CMD="docker-compose"
        fi
        log_info "Forcing complete rebuild of project containers..."

        # Stop and remove existing containers
        if [ -f "$COMPOSE_FILE" ]; then
            log_info "Stopping and removing existing containers..."
            $COMPOSE_CMD -f "$COMPOSE_FILE" down --remove-orphans 2>/dev/null || true
        fi

        # Remove existing project-specific images only
        image_name="heimdall-mcp:$PROJECT_HASH"
        log_info "Cleaning up project-specific images..."

        # Remove specific project image
        docker rmi "$image_name" 2>/dev/null || true

        # Only remove dangling images that might be related to this project
        # (safer than removing all dangling images)
        log_info "Cleaned up project image: $image_name"

        export FORCE_REBUILD=true
        ;;
esac

# Run main function
main "$@"
