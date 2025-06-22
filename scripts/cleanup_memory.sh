#!/bin/bash
set -e

# Cleanup script for Heimdall MCP projects
# This script removes orphaned containers and optionally cleans up all projects

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Find all projects with .heimdall-mcp directories
find_all_projects() {
    # Search for .heimdall-mcp directories in common workspace locations
    local search_dirs=(
        "$HOME/workspace"
        "$HOME/projects"
        "$HOME/src"
        "$HOME/dev"
        "$HOME/git"
        "/workspace"
        "/projects"
    )

    local projects=()

    for search_dir in "${search_dirs[@]}"; do
        if [ -d "$search_dir" ]; then
            while IFS= read -r -d '' project_dir; do
                # Extract project path (parent of .heimdall-mcp)
                local project_path=$(dirname "$project_dir")
                projects+=("$project_path")
            done < <(find "$search_dir" -name ".heimdall-mcp" -type d -print0 2>/dev/null)
        fi
    done

    # Remove duplicates and return
    printf '%s\n' "${projects[@]}" | sort -u
}

# Get project info from path
get_project_info() {
    local project_path="$1"
    local project_hash=$(echo "$project_path" | sha256sum | cut -c1-8)
    local repo_name=$(basename "$project_path")

    echo "$project_hash $repo_name $project_path"
}

# Clean up orphaned containers
cleanup_orphaned() {
    log_info "Cleaning up orphaned Heimdall MCP containers..."

    # Get all current projects
    local valid_projects=()
    while IFS= read -r project_path; do
        if [ -n "$project_path" ]; then
            valid_projects+=("$project_path")
        fi
    done < <(find_all_projects)

    # Build list of valid container names
    local valid_containers=()
    local valid_networks=()
    local valid_volumes=()

    for project_path in "${valid_projects[@]}"; do
        read -r project_hash repo_name _ <<< "$(get_project_info "$project_path")"
        valid_containers+=("heimdall-$repo_name-$project_hash" "qdrant-$repo_name-$project_hash")
        valid_networks+=("heimdall-network-$repo_name-$project_hash")
        valid_volumes+=("heimdall-qdrant-$project_hash" "heimdall-data-$project_hash")
    done

    local removed_count=0

    # Find and remove orphaned containers
    log_info "Checking for orphaned containers..."
    while IFS= read -r container_name; do
        if [ -n "$container_name" ]; then
            # Check if this container is in our valid list
            local is_valid=false
            for valid_container in "${valid_containers[@]}"; do
                if [ "$container_name" = "$valid_container" ]; then
                    is_valid=true
                    break
                fi
            done

            if [ "$is_valid" = false ]; then
                log_warning "Removing orphaned container: $container_name"
                docker rm -f "$container_name" 2>/dev/null || true
                removed_count=$((removed_count + 1))
            fi
        fi
    done < <(docker ps -a --filter "name=heimdall-" --format "{{.Names}}" 2>/dev/null || true)

    # Find and remove orphaned Qdrant containers
    while IFS= read -r container_name; do
        if [ -n "$container_name" ]; then
            # Check if this container is in our valid list
            local is_valid=false
            for valid_container in "${valid_containers[@]}"; do
                if [ "$container_name" = "$valid_container" ]; then
                    is_valid=true
                    break
                fi
            done

            if [ "$is_valid" = false ]; then
                log_warning "Removing orphaned Qdrant container: $container_name"
                docker rm -f "$container_name" 2>/dev/null || true
                removed_count=$((removed_count + 1))
            fi
        fi
    done < <(docker ps -a --filter "name=qdrant-" --format "{{.Names}}" 2>/dev/null || true)

    # Clean up orphaned volumes
    log_info "Checking for orphaned volumes..."
    while IFS= read -r volume_name; do
        if [ -n "$volume_name" ]; then
            local is_valid=false
            for valid_volume in "${valid_volumes[@]}"; do
                if [ "$volume_name" = "$valid_volume" ]; then
                    is_valid=true
                    break
                fi
            done

            if [ "$is_valid" = false ]; then
                log_warning "Removing orphaned volume: $volume_name"
                docker volume rm "$volume_name" 2>/dev/null || true
                removed_count=$((removed_count + 1))
            fi
        fi
    done < <(docker volume ls --filter "name=heimdall-" --format "{{.Name}}" 2>/dev/null || true)

    # Clean up orphaned networks
    log_info "Checking for orphaned networks..."
    while IFS= read -r network_name; do
        if [ -n "$network_name" ]; then
            local is_valid=false
            for valid_network in "${valid_networks[@]}"; do
                if [ "$network_name" = "$valid_network" ]; then
                    is_valid=true
                    break
                fi
            done

            if [ "$is_valid" = false ]; then
                log_warning "Removing orphaned network: $network_name"
                docker network rm "$network_name" 2>/dev/null || true
                removed_count=$((removed_count + 1))
            fi
        fi
    done < <(docker network ls --filter "name=heimdall-network-" --format "{{.Name}}" 2>/dev/null || true)

    if [ $removed_count -eq 0 ]; then
        log_success "No orphaned resources found"
    else
        log_success "Removed $removed_count orphaned resources"
    fi
}

# Clean up all projects
cleanup_all() {
    log_warning "This will remove ALL Heimdall MCP projects and data!"
    echo ""
    read -p "Are you sure? (type 'yes' to confirm): " confirmation

    if [ "$confirmation" != "yes" ]; then
        log_info "Cleanup cancelled"
        exit 0
    fi

    log_info "Stopping and removing all Heimdall MCP containers..."

    local removed_count=0

    # Stop and remove all Heimdall containers
    while IFS= read -r container_name; do
        if [ -n "$container_name" ]; then
            log_info "Stopping and removing container: $container_name"
            docker rm -f "$container_name" 2>/dev/null || true
            removed_count=$((removed_count + 1))
        fi
    done < <(docker ps -a --filter "name=heimdall-" --format "{{.Names}}" 2>/dev/null || true)

    # Stop and remove all Qdrant containers
    while IFS= read -r container_name; do
        if [ -n "$container_name" ]; then
            log_info "Stopping and removing Qdrant container: $container_name"
            docker rm -f "$container_name" 2>/dev/null || true
            removed_count=$((removed_count + 1))
        fi
    done < <(docker ps -a --filter "name=qdrant-" --format "{{.Names}}" 2>/dev/null || true)

    # Remove all Heimdall volumes
    while IFS= read -r volume_name; do
        if [ -n "$volume_name" ]; then
            log_info "Removing volume: $volume_name"
            docker volume rm "$volume_name" 2>/dev/null || true
            removed_count=$((removed_count + 1))
        fi
    done < <(docker volume ls --filter "name=heimdall-" --format "{{.Name}}" 2>/dev/null || true)

    # Remove all Heimdall networks
    while IFS= read -r network_name; do
        if [ -n "$network_name" ]; then
            log_info "Removing network: $network_name"
            docker network rm "$network_name" 2>/dev/null || true
            removed_count=$((removed_count + 1))
        fi
    done < <(docker network ls --filter "name=heimdall-network-" --format "{{.Name}}" 2>/dev/null || true)

    # Optionally remove project data directories
    echo ""
    log_warning "Do you also want to remove all project data directories (.heimdall-mcp)?"
    read -p "This will permanently delete all stored memories! (type 'yes' to confirm): " data_confirmation

    if [ "$data_confirmation" = "yes" ]; then
        log_info "Removing project data directories..."
        while IFS= read -r project_path; do
            if [ -n "$project_path" ] && [ -d "$project_path/.heimdall-mcp" ]; then
                log_info "Removing data directory: $project_path/.heimdall-mcp"
                rm -rf "$project_path/.heimdall-mcp"
                removed_count=$((removed_count + 1))
            fi
        done < <(find_all_projects)
    fi

    log_success "Cleanup completed. Removed $removed_count items total."
}

# Clean up specific project
cleanup_project() {
    local project_path="$(pwd)"
    read -r project_hash repo_name _ <<< "$(get_project_info "$project_path")"

    log_info "Cleaning up project: $repo_name ($project_hash)"
    log_info "Path: $project_path"

    if [ ! -d "$project_path/.heimdall-mcp" ]; then
        log_warning "No Heimdall MCP setup found in current directory"
        exit 0
    fi

    # Stop and remove containers
    local container_name="heimdall-$repo_name-$project_hash"
    local qdrant_container="qdrant-$repo_name-$project_hash"

    if docker ps -a --format "{{.Names}}" | grep -q "$container_name"; then
        log_info "Stopping and removing container: $container_name"
        docker rm -f "$container_name" 2>/dev/null || true
    fi

    if docker ps -a --format "{{.Names}}" | grep -q "$qdrant_container"; then
        log_info "Stopping and removing container: $qdrant_container"
        docker rm -f "$qdrant_container" 2>/dev/null || true
    fi

    # Remove project-specific resources
    local network_name="heimdall-network-$repo_name-$project_hash"
    if docker network ls --format "{{.Name}}" | grep -q "$network_name"; then
        log_info "Removing network: $network_name"
        docker network rm "$network_name" 2>/dev/null || true
    fi

    local qdrant_volume="heimdall-qdrant-$project_hash"
    local data_volume="heimdall-data-$project_hash"

    if docker volume ls --format "{{.Name}}" | grep -q "$qdrant_volume"; then
        log_info "Removing volume: $qdrant_volume"
        docker volume rm "$qdrant_volume" 2>/dev/null || true
    fi

    if docker volume ls --format "{{.Name}}" | grep -q "$data_volume"; then
        log_info "Removing volume: $data_volume"
        docker volume rm "$data_volume" 2>/dev/null || true
    fi

    # Ask about removing data directory
    echo ""
    log_warning "Do you want to remove the project data directory (.heimdall-mcp)?"
    read -p "This will permanently delete all stored memories! (type 'yes' to confirm): " data_confirmation

    if [ "$data_confirmation" = "yes" ]; then
        log_info "Removing data directory: $project_path/.heimdall-mcp"
        rm -rf "$project_path/.heimdall-mcp"
    fi

    log_success "Project cleanup completed"
}

# Show usage
show_usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Cleanup Heimdall MCP projects and Docker resources"
    echo ""
    echo "Options:"
    echo "  --help, -h       Show this help message"
    echo "  --orphaned       Remove orphaned containers, volumes, and networks"
    echo "  --all            Remove ALL Heimdall MCP projects and data"
    echo "  --project        Remove current project only"
    echo ""
    echo "Examples:"
    echo "  $0 --orphaned    # Clean up orphaned resources"
    echo "  $0 --all         # Remove everything (with confirmation)"
    echo "  $0 --project     # Remove current project (from project directory)"
    echo ""
}

# Main execution
main() {
    echo "🧹 Heimdall MCP Cleanup Tool"
    echo "============================="
    echo ""

    case "${1:-}" in
        --help|-h)
            show_usage
            exit 0
            ;;
        --orphaned)
            cleanup_orphaned
            ;;
        --all)
            cleanup_all
            ;;
        --project)
            cleanup_project
            ;;
        "")
            log_info "No option specified. Use --help to see available options."
            echo ""
            show_usage
            exit 1
            ;;
        *)
            log_error "Unknown option: $1"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
