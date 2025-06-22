#!/bin/bash
set -e

# Load project content into Heimdall MCP system
# This script loads git history and markdown files from the current project into the containerized Heimdall MCP system

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_PATH="$(pwd)"
PROJECT_HASH=$(echo "$PROJECT_PATH" | sha256sum | cut -c1-8)
REPO_NAME=$(basename "$PROJECT_PATH")
CONTAINER_NAME="heimdall-$REPO_NAME-$PROJECT_HASH"

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

# Check if container is running and healthy
check_container_running() {
    if ! docker ps --format "table {{.Names}}" | grep -q "^$CONTAINER_NAME$"; then
        log_error "Cognitive memory container '$CONTAINER_NAME' is not running"
        log_info "Run: $SCRIPT_DIR/../setup_claude_code_mcp.sh"
        exit 1
    fi

    # Wait for container to be healthy
    log_info "Waiting for container to be healthy..."
    local max_wait=30
    local elapsed=0

    while [ $elapsed -lt $max_wait ]; do
        if docker exec "$CONTAINER_NAME" test -w /app/data 2>/dev/null; then
            log_info "Container is ready"
            return 0
        fi
        echo -n "."
        sleep 2
        elapsed=$((elapsed + 2))
    done

    echo ""
    log_error "Container failed to become ready within $max_wait seconds"
    log_error "Check container logs: docker logs $CONTAINER_NAME"
    exit 1
}

# Check if current directory is a git repository
check_git_repository() {
    if [ ! -d ".git" ]; then
        log_warning "Current directory is not a git repository"
        return 1
    fi
    return 0
}

# Load git history into Heimdall MCP
load_git_history() {
    if ! check_git_repository; then
        log_info "Skipping git history loading (not a git repository)"
        return 0
    fi

    log_info "Loading git history from: $PROJECT_PATH"

    # First do a dry run to preview
    log_info "Running git analysis preview..."
    if ! docker exec -i  "$CONTAINER_NAME" memory_system shell <<EOF
git-load $PROJECT_PATH --dry-run
quit
EOF
    then
        log_error "Failed to run git analysis preview"
        return 1
    fi

    log_info "Git analysis preview completed. Loading into memory..."
    if docker exec -i  "$CONTAINER_NAME" memory_system shell <<EOF
git-load $PROJECT_PATH
quit
EOF
    then
        log_success "Git history loaded successfully"
    else
        log_error "Failed to load git history"
        return 1
    fi
}

# Load markdown files into Heimdall MCP
load_markdown_files() {
    local docs_dir="$PROJECT_PATH/.heimdall-mcp"

    # Check if .heimdall-mcp directory exists
    if [ ! -d "$docs_dir" ]; then
        log_info "No .heimdall-mcp directory found in project"
        log_info "Create $docs_dir and add markdown files to load them into memory"
        return 0
    fi

    log_info "Searching for markdown files in: $docs_dir"

    # Find markdown files recursively in .heimdall-mcp (following symlinks)
    local md_count=$(find -L "$docs_dir" -name "*.md" -type f | wc -l)

    if [ "$md_count" -eq 0 ]; then
        log_info "No markdown files found in .heimdall-mcp directory"
        return 0
    fi

    log_info "Found $md_count markdown files. Loading into memory..."

    if docker exec -i  "$CONTAINER_NAME" memory_system shell <<EOF
load $docs_dir --recursive
quit
EOF
    then
        log_success "Markdown files loaded successfully from .heimdall-mcp"
    else
        log_error "Failed to load markdown files"
        return 1
    fi
}

# Show loading status
show_status() {
    log_info "Checking Heimdall MCP status..."
    docker exec -i  "$CONTAINER_NAME" memory_system shell <<EOF
status
quit
EOF
}

# Display usage help
show_help() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Load project content into Heimdall MCP system"
    echo ""
    echo "Options:"
    echo "  --help, -h        Show this help message"
    echo "  --git-only        Load only git history"
    echo "  --markdown-only   Load only markdown files"
    echo "  --status          Show current memory status"
    echo "  --dry-run         Preview what would be loaded"
    echo ""
    echo "Examples:"
    echo "  $0                    # Load both git history and markdown files"
    echo "  $0 --git-only         # Load only git history"
    echo "  $0 --markdown-only    # Load only markdown files from .heimdall-mcp/"
    echo "  $0 --status           # Show memory status"
    echo ""
    echo "Note: Markdown files should be placed in .heimdall-mcp/ directory"
    echo "      to be loaded into the Heimdall MCP system."
    echo ""
}

# Main execution
main() {
    echo "🧠 Loading Project Content into Heimdall MCP"
    echo "=============================================="
    echo ""
    echo "Project Path: $PROJECT_PATH"
    echo "Project Hash: $PROJECT_HASH"
    echo "Container:    $CONTAINER_NAME"
    echo ""

    # Check prerequisites
    check_container_running

    local load_git=true
    local load_markdown=true
    local dry_run=false

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                show_help
                exit 0
                ;;
            --git-only)
                load_git=true
                load_markdown=false
                shift
                ;;
            --markdown-only)
                load_git=false
                load_markdown=true
                shift
                ;;
            --status)
                show_status
                exit 0
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # Execute loading operations
    local success=true

    if [ "$dry_run" = true ]; then
        log_info "DRY RUN - Preview of what would be loaded:"
        echo ""

        if [ "$load_git" = true ] && check_git_repository; then
            echo "📝 Git History:"
            docker exec -i  "$CONTAINER_NAME" memory_system shell <<EOF || true
git-load $PROJECT_PATH --dry-run
quit
EOF
        fi

        if [ "$load_markdown" = true ]; then
            echo ""
            echo "📄 Markdown Files:"
            local docs_dir="$PROJECT_PATH/.heimdall-mcp"
            if [ -d "$docs_dir" ]; then
                find -L "$docs_dir" -name "*.md" -type f | head -10
                local total=$(find -L "$docs_dir" -name "*.md" -type f | wc -l)
                if [ "$total" -gt 10 ]; then
                    echo "... and $((total - 10)) more files"
                fi
            else
                echo "No .heimdall-mcp directory found"
                echo "Create $docs_dir and add markdown files to load them"
            fi
        fi

        exit 0
    fi

    if [ "$load_git" = true ]; then
        load_git_history || success=false
    fi

    if [ "$load_markdown" = true ]; then
        load_markdown_files || success=false
    fi

    echo ""
    if [ "$success" = true ]; then
        log_success "All content loaded successfully!"
        echo ""
        log_info "You can now use the Heimdall MCP system with your project content"
        log_info "Try: memory_system shell"
    else
        log_error "Some content failed to load. Check the logs above."
        exit 1
    fi

    # Show final status
    show_status
}

# Run main function
main "$@"
