#!/bin/bash
set -e

# List all Heimdall MCP projects and their status
# This script shows all configured projects and container status

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

# Get container status
get_container_status() {
    local repo_name="$1"
    local project_hash="$2"
    local container_name="heimdall-$repo_name-$project_hash"
    local qdrant_name="qdrant-$repo_name-$project_hash"

    local heimdall_running=false
    local qdrant_running=false
    local heimdall_exists=false
    local qdrant_exists=false

    # Check if containers exist and are running
    if docker ps --format "{{.Names}}" | grep -q "^$container_name$"; then
        heimdall_running=true
        heimdall_exists=true
    elif docker ps -a --format "{{.Names}}" | grep -q "^$container_name$"; then
        heimdall_exists=true
    fi

    if docker ps --format "{{.Names}}" | grep -q "^$qdrant_name$"; then
        qdrant_running=true
        qdrant_exists=true
    elif docker ps -a --format "{{.Names}}" | grep -q "^$qdrant_name$"; then
        qdrant_exists=true
    fi

    # Determine overall status
    if [ "$heimdall_running" = true ] && [ "$qdrant_running" = true ]; then
        echo "🟢 Running"
    elif [ "$heimdall_exists" = true ] && [ "$qdrant_exists" = true ]; then
        echo "🔴 Stopped"
    elif [ "$heimdall_exists" = true ] || [ "$qdrant_exists" = true ]; then
        echo "🟡 Partial"
    else
        echo "⚫ Not Created"
    fi
}

# Get project data size
get_data_size() {
    local project_path="$1"
    local data_dir="$project_path/.heimdall-mcp"

    if [ -d "$data_dir" ]; then
        # Calculate directory size in human readable format
        local size=$(du -sh "$data_dir" 2>/dev/null | cut -f1)
        echo "$size"
    else
        echo "-"
    fi
}

# Get Qdrant port for project
get_qdrant_port() {
    local project_hash="$1"

    # Calculate port same way as setup script
    local hash_decimal=$((16#$(echo "$project_hash" | cut -c1-3)))
    local qdrant_port=$((6333 + ($hash_decimal % 1000)))

    echo "$qdrant_port"
}

# Get memory statistics from container
get_memory_stats() {
    local repo_name="$1"
    local project_hash="$2"
    local container_name="heimdall-$repo_name-$project_hash"

    if docker ps --format "{{.Names}}" | grep -q "^$container_name$"; then
        # Try to get memory count from container
        local memory_count=$(docker exec "$container_name" sh -c "
            python -c '
import sys
sys.path.append(\"/app\")
try:
    from cognitive_memory.core.cognitive_system import CognitiveSystem
    system = CognitiveSystem()
    status = system.get_status()
    total = status.get(\"memory_counts\", {}).get(\"total\", 0)
    print(total)
except:
    print(\"0\")
' 2>/dev/null" 2>/dev/null || echo "0")
        echo "$memory_count"
    else
        echo "-"
    fi
}

# Show detailed view of projects
show_detailed() {
    local projects=()
    while IFS= read -r project_path; do
        if [ -n "$project_path" ]; then
            projects+=("$project_path")
        fi
    done < <(find_all_projects)

    if [ ${#projects[@]} -eq 0 ]; then
        log_warning "No Heimdall MCP projects found"
        return
    fi

    echo -e "${CYAN}📋 Detailed Project Information${NC}"
    echo "=================================="
    echo ""

    for project_path in "${projects[@]}"; do
        read -r project_hash repo_name _ <<< "$(get_project_info "$project_path")"
        local status=$(get_container_status "$repo_name" "$project_hash")
        local data_size=$(get_data_size "$project_path")
        local qdrant_port=$(get_qdrant_port "$project_hash")
        local memory_count=$(get_memory_stats "$repo_name" "$project_hash")

        echo -e "${BLUE}Project:${NC} $repo_name"
        echo -e "${BLUE}  Path:${NC} $project_path"
        echo -e "${BLUE}  Hash:${NC} $project_hash"
        echo -e "${BLUE}  Status:${NC} $status"
        echo -e "${BLUE}  Data Size:${NC} $data_size"
        echo -e "${BLUE}  Qdrant Port:${NC} $qdrant_port"
        echo -e "${BLUE}  Memories:${NC} $memory_count"
        echo -e "${BLUE}  Containers:${NC}"
        echo -e "    - heimdall-$repo_name-$project_hash"
        echo -e "    - qdrant-$repo_name-$project_hash"
        echo ""
    done
}

# Show table view of projects
show_table() {
    local projects=()
    while IFS= read -r project_path; do
        if [ -n "$project_path" ]; then
            projects+=("$project_path")
        fi
    done < <(find_all_projects)

    if [ ${#projects[@]} -eq 0 ]; then
        log_warning "No Heimdall MCP projects found"
        return
    fi

    echo -e "${CYAN}📊 Heimdall MCP Projects Overview${NC}"
    echo "=================================="
    echo ""

    # Table header
    printf "%-20s %-10s %-12s %-8s %-8s %-8s %s\n" \
        "PROJECT" "STATUS" "HASH" "PORT" "SIZE" "MEMORIES" "PATH"
    printf "%-20s %-10s %-12s %-8s %-8s %-8s %s\n" \
        "$(printf '%.20s' "--------------------")" \
        "----------" \
        "------------" \
        "--------" \
        "--------" \
        "--------" \
        "----"

    # Table rows
    for project_path in "${projects[@]}"; do
        read -r project_hash repo_name _ <<< "$(get_project_info "$project_path")"
        local status=$(get_container_status "$repo_name" "$project_hash")
        local data_size=$(get_data_size "$project_path")
        local qdrant_port=$(get_qdrant_port "$project_hash")
        local memory_count=$(get_memory_stats "$repo_name" "$project_hash")

        # Truncate repo name if too long
        local display_name="$repo_name"
        if [ ${#display_name} -gt 18 ]; then
            display_name="${display_name:0:15}..."
        fi

        # Remove emoji from status for table alignment
        local status_text=$(echo "$status" | sed 's/[🟢🔴🟡⚫] //')

        printf "%-20s %-10s %-12s %-8s %-8s %-8s %s\n" \
            "$display_name" \
            "$status_text" \
            "$project_hash" \
            "$qdrant_port" \
            "$data_size" \
            "$memory_count" \
            "$project_path"
    done

    echo ""
    log_info "Status: Running=🟢, Stopped=🔴, Partial=🟡, Not Created=⚫"
}

# Show running containers only
show_running() {
    local found_running=false

    echo -e "${CYAN}🏃 Running Heimdall MCP Containers${NC}"
    echo "=================================="
    echo ""

    local projects=()
    while IFS= read -r project_path; do
        if [ -n "$project_path" ]; then
            projects+=("$project_path")
        fi
    done < <(find_all_projects)

    for project_path in "${projects[@]}"; do
        read -r project_hash repo_name _ <<< "$(get_project_info "$project_path")"
        local status=$(get_container_status "$repo_name" "$project_hash")

        if [[ "$status" == *"Running"* ]]; then
            found_running=true
            local qdrant_port=$(get_qdrant_port "$project_hash")
            local memory_count=$(get_memory_stats "$repo_name" "$project_hash")

            echo -e "${GREEN}●${NC} $repo_name ($project_hash)"
            echo -e "   Path: $project_path"
            echo -e "   Qdrant: http://localhost:$qdrant_port"
            echo -e "   Memories: $memory_count"
            echo ""
        fi
    done

    if [ "$found_running" = false ]; then
        log_warning "No running Heimdall MCP containers found"
    fi
}

# Show usage
show_usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "List Heimdall MCP projects and their status"
    echo ""
    echo "Options:"
    echo "  --help, -h       Show this help message"
    echo "  --table          Show projects in table format (default)"
    echo "  --detailed       Show detailed project information"
    echo "  --running        Show only running projects"
    echo ""
    echo "Examples:"
    echo "  $0               # Show table view"
    echo "  $0 --detailed    # Show detailed information"
    echo "  $0 --running     # Show only running containers"
    echo ""
}

# Main execution
main() {
    case "${1:-}" in
        --help|-h)
            show_usage
            exit 0
            ;;
        --detailed)
            show_detailed
            ;;
        --running)
            show_running
            ;;
        --table|"")
            show_table
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
