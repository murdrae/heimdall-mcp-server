#!/bin/bash
set -e

# Cleanup script for cognitive memory projects
# This script removes unused containers and optionally cleans up all projects

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECTS_DIR="$HOME/.cognitive-memory/projects"

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

# Clean up orphaned containers
cleanup_orphaned() {
    log_info "Cleaning up orphaned cognitive memory containers..."

    # Find all cognitive memory containers
    orphaned_containers=$(docker ps -a --filter "name=cognitive-memory-" --format "{{.Names}}" || true)
    orphaned_qdrant=$(docker ps -a --filter "name=qdrant-" --format "{{.Names}}" || true)

    removed_count=0

    # Check each container against existing projects
    for container in $orphaned_containers $orphaned_qdrant; do
        if [[ "$container" =~ cognitive-memory-([a-f0-9]{8}) ]] || [[ "$container" =~ qdrant-([a-f0-9]{8}) ]]; then
            project_hash="${BASH_REMATCH[1]}"
            project_dir="$PROJECTS_DIR/$project_hash"

            # If project directory doesn't exist, container is orphaned
            if [ ! -d "$project_dir" ]; then
                log_warning "Removing orphaned container: $container"
                docker rm -f "$container" 2>/dev/null || true
                removed_count=$((removed_count + 1))
            fi
        fi
    done

    # Clean up orphaned volumes
    orphaned_volumes=$(docker volume ls --filter "name=cognitive-" --format "{{.Name}}" || true)

    for volume in $orphaned_volumes; do
        if [[ "$volume" =~ cognitive-.*-([a-f0-9]{8}) ]]; then
            project_hash="${BASH_REMATCH[1]}"
            project_dir="$PROJECTS_DIR/$project_hash"

            if [ ! -d "$project_dir" ]; then
                log_warning "Removing orphaned volume: $volume"
                docker volume rm "$volume" 2>/dev/null || true
                removed_count=$((removed_count + 1))
            fi
        fi
    done

    # Clean up orphaned networks
    orphaned_networks=$(docker network ls --filter "name=cognitive-network-" --format "{{.Name}}" || true)

    for network in $orphaned_networks; do
        if [[ "$network" =~ cognitive-network-([a-f0-9]{8}) ]]; then
            project_hash="${BASH_REMATCH[1]}"
            project_dir="$PROJECTS_DIR/$project_hash"

            if [ ! -d "$project_dir" ]; then
                log_warning "Removing orphaned network: $network"
                docker network rm "$network" 2>/dev/null || true
                removed_count=$((removed_count + 1))
            fi
        fi
    done

    if [ $removed_count -eq 0 ]; then
        log_success "No orphaned resources found"
    else
        log_success "Removed $removed_count orphaned resources"
    fi
}

# Clean up all projects
cleanup_all() {
    log_warning "This will remove ALL cognitive memory projects and data!"
    echo ""
    read -p "Are you sure? (type 'yes' to confirm): " confirmation

    if [ "$confirmation" != "yes" ]; then
        log_info "Cleanup cancelled"
        exit 0
    fi

    log_info "Stopping all cognitive memory containers..."

    # Stop all cognitive memory containers
    cognitive_containers=$(docker ps --filter "name=cognitive-memory-" --format "{{.Names}}" || true)
    qdrant_containers=$(docker ps --filter "name=qdrant-" --format "{{.Names}}" || true)

    for container in $cognitive_containers $qdrant_containers; do
        log_info "Stopping container: $container"
        docker stop "$container" 2>/dev/null || true
    done

    # Remove all containers, volumes, and networks
    log_info "Removing all cognitive memory resources..."

    # Remove containers
    docker rm -f $(docker ps -a --filter "name=cognitive-memory-" --format "{{.Names}}" 2>/dev/null || true) 2>/dev/null || true
    docker rm -f $(docker ps -a --filter "name=qdrant-" --format "{{.Names}}" 2>/dev/null || true) 2>/dev/null || true

    # Remove volumes
    docker volume rm $(docker volume ls --filter "name=cognitive-" --format "{{.Name}}" 2>/dev/null || true) 2>/dev/null || true

    # Remove networks
    docker network rm $(docker network ls --filter "name=cognitive-network-" --format "{{.Name}}" 2>/dev/null || true) 2>/dev/null || true

    # Remove project data
    if [ -d "$PROJECTS_DIR" ]; then
        log_info "Removing project data directory: $PROJECTS_DIR"
        rm -rf "$PROJECTS_DIR"
    fi

    log_success "All cognitive memory projects cleaned up"
}

# Show usage
show_usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Cleanup cognitive memory projects and containers"
    echo ""
    echo "Options:"
    echo "  --help, -h        Show this help message"
    echo "  --orphaned        Clean up orphaned containers only (default)"
    echo "  --all             Remove ALL projects and data (dangerous!)"
    echo "  --dry-run         Show what would be cleaned up without doing it"
    echo ""
}

# Dry run mode
dry_run() {
    log_info "DRY RUN - showing what would be cleaned up"
    echo ""

    # Check for orphaned containers
    orphaned_containers=$(docker ps -a --filter "name=cognitive-memory-" --format "{{.Names}}" || true)
    orphaned_qdrant=$(docker ps -a --filter "name=qdrant-" --format "{{.Names}}" || true)

    orphan_count=0

    for container in $orphaned_containers $orphaned_qdrant; do
        if [[ "$container" =~ cognitive-memory-([a-f0-9]{8}) ]] || [[ "$container" =~ qdrant-([a-f0-9]{8}) ]]; then
            project_hash="${BASH_REMATCH[1]}"
            project_dir="$PROJECTS_DIR/$project_hash"

            if [ ! -d "$project_dir" ]; then
                echo "Would remove orphaned container: $container"
                orphan_count=$((orphan_count + 1))
            fi
        fi
    done

    if [ $orphan_count -eq 0 ]; then
        log_info "No orphaned containers found"
    else
        log_warning "Found $orphan_count orphaned containers"
    fi
}

# Main execution
main() {
    case "${1:-}" in
        --help|-h)
            show_usage
            exit 0
            ;;
        --all)
            cleanup_all
            ;;
        --dry-run)
            dry_run
            ;;
        --orphaned|"")
            cleanup_orphaned
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
