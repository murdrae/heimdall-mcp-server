#!/bin/bash
# Heimdall MCP Server - Post-Commit Hook
# Automatically processes the latest commit for memory storage

# Exit codes:
# 0: Success or graceful skip
# 1: Critical failure (should not break git operations)

# Configuration
HOOK_LOG_FILE="${HOME}/.heimdall/hook.log"
MAX_LOG_SIZE=1048576  # 1MB

# Logging function
log_message() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local message="$1"
    local log_dir=$(dirname "$HOOK_LOG_FILE")

    # Create log directory if it doesn't exist
    mkdir -p "$log_dir" 2>/dev/null || true

    # Rotate log if too large
    if [[ -f "$HOOK_LOG_FILE" ]] && [[ $(stat -f%z "$HOOK_LOG_FILE" 2>/dev/null || stat -c%s "$HOOK_LOG_FILE" 2>/dev/null || echo 0) -gt $MAX_LOG_SIZE ]]; then
        mv "$HOOK_LOG_FILE" "${HOOK_LOG_FILE}.old" 2>/dev/null || true
    fi

    echo "[$timestamp] $message" >> "$HOOK_LOG_FILE" 2>/dev/null || true
}

# Error handling function
handle_error() {
    local error_msg="$1"
    log_message "ERROR: $error_msg"
    # Always exit 0 to avoid breaking git operations
    exit 0
}

# Main execution
main() {
    log_message "Post-commit hook started"

    # Find git repository root
    local repo_root
    repo_root=$(git rev-parse --show-toplevel 2>/dev/null)
    if [[ $? -ne 0 ]] || [[ -z "$repo_root" ]]; then
        handle_error "Not in a git repository"
    fi

    log_message "Repository root: $repo_root"

    # Get the latest commit hash
    local latest_commit
    latest_commit=$(git rev-parse HEAD 2>/dev/null)
    if [[ $? -ne 0 ]] || [[ -z "$latest_commit" ]]; then
        handle_error "Failed to get latest commit hash"
    fi

    log_message "Processing commit: $latest_commit"

    # Find project-specific Heimdall container or fallback to direct command
    local container_name=""
    local memory_system_cmd=""

    # Generate project hash for container name
    local project_hash
    project_hash=$(echo "$repo_root" | sha256sum | cut -c1-8)
    local repo_name
    repo_name=$(basename "$repo_root")

    # Check for project-specific container
    container_name="heimdall-${repo_name}-${project_hash}"
    if docker ps --format '{{.Names}}' | grep -q "^${container_name}$" 2>/dev/null; then
        memory_system_cmd="docker exec $container_name python -m memory_system.cli"
        log_message "Using project container: $container_name"
    else
        log_message "Project container not found: $container_name"

        # Fallback to direct command
        if command -v memory_system >/dev/null 2>&1; then
            memory_system_cmd="memory_system"
            log_message "Using system memory_system command"
        else
            # Try to find heimdall installation relative to this script
            local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
            local heimdall_root="$(dirname "$script_dir")"

            if [[ -f "$heimdall_root/memory_system/cli.py" ]]; then
                memory_system_cmd="python3 $heimdall_root/memory_system/cli.py"
                log_message "Using local Python CLI: $memory_system_cmd"
            else
                handle_error "No memory system available. Install containers with: $heimdall_root/scripts/setup_project_memory.sh"
            fi
        fi
    fi

    # Change to repository directory
    cd "$repo_root" || handle_error "Failed to change to repository directory"

    # Execute incremental git loading
    log_message "Executing incremental git loading..."

    # Use timeout to prevent hanging
    local timeout_cmd=""
    if command -v timeout >/dev/null 2>&1; then
        timeout_cmd="timeout 300"  # 5 minutes timeout
    fi

    # Execute the command with error handling
    local output
    local exit_code

    # For Docker containers, we need to set working directory and use the container's CLI
    if [[ "$memory_system_cmd" == docker* ]]; then
        # Docker exec approach - repository is mounted at same path in container
        # Set working directory and run the command
        output=$($timeout_cmd docker exec -w "$repo_root" "$container_name" python -m memory_system.cli load-git incremental --max-commits=1 2>&1)
        exit_code=$?
    else
        # Direct command approach
        output=$($timeout_cmd $memory_system_cmd load-git --incremental --max-commits=1 2>&1)
        exit_code=$?
    fi

    if [[ $exit_code -eq 0 ]]; then
        log_message "SUCCESS: Incremental git loading completed"
        log_message "Output: $output"
    else
        log_message "WARNING: Incremental git loading failed (exit code: $exit_code)"
        log_message "Output: $output"
        # Don't treat this as critical - just log and continue
    fi

    log_message "Post-commit hook completed"
    exit 0
}

# Execute main function with error handling
main "$@" 2>&1 || handle_error "Unexpected error in post-commit hook"
