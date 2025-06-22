#!/bin/bash
# Heimdall MCP Server - Git Hook Installer
# Safely installs post-commit hook with preservation of existing hooks

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEIMDALL_ROOT="$(dirname "$SCRIPT_DIR")"
HOOK_SCRIPT="$SCRIPT_DIR/post-commit-hook.sh"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Usage information
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS] [REPOSITORY_PATH]

Install Heimdall post-commit hook for automatic incremental git loading.

OPTIONS:
    --install       Install the post-commit hook (default)
    --uninstall     Remove the Heimdall post-commit hook
    --status        Show current hook status
    --force         Force installation even if hooks exist
    --dry-run       Show what would be done without making changes
    --help, -h      Show this help message

REPOSITORY_PATH:
    Path to git repository (default: current directory)

EXAMPLES:
    $0                          # Install hook in current repository
    $0 /path/to/repo            # Install hook in specific repository
    $0 --uninstall              # Remove hook from current repository
    $0 --status                 # Check hook status
    $0 --dry-run --force        # Preview forced installation

EOF
}

# Validate git repository
validate_git_repo() {
    local repo_path="$1"

    if [[ ! -d "$repo_path/.git" ]]; then
        log_error "Not a git repository: $repo_path"
        log_error "Please run this script from within a git repository or specify a valid path."
        return 1
    fi

    return 0
}

# Check if hook script exists and is executable
validate_hook_script() {
    if [[ ! -f "$HOOK_SCRIPT" ]]; then
        log_error "Hook script not found: $HOOK_SCRIPT"
        log_error "Please ensure Heimdall MCP Server is properly installed."
        return 1
    fi

    if [[ ! -x "$HOOK_SCRIPT" ]]; then
        log_error "Hook script is not executable: $HOOK_SCRIPT"
        log_error "Run: chmod +x $HOOK_SCRIPT"
        return 1
    fi

    return 0
}

# Get hook status
get_hook_status() {
    local repo_path="$1"
    local hook_file="$repo_path/.git/hooks/post-commit"

    if [[ ! -f "$hook_file" ]]; then
        echo "NO_HOOK"
        return 0
    fi

    if grep -q "Heimdall MCP Server" "$hook_file" 2>/dev/null; then
        if [[ -x "$hook_file" ]]; then
            echo "HEIMDALL_INSTALLED"
        else
            echo "HEIMDALL_NOT_EXECUTABLE"
        fi
        return 0
    fi

    echo "OTHER_HOOK_EXISTS"
    return 0
}

# Show current status
show_status() {
    local repo_path="$1"
    local hook_file="$repo_path/.git/hooks/post-commit"
    local status

    status=$(get_hook_status "$repo_path")

    log_info "Repository: $repo_path"
    log_info "Hook file: $hook_file"

    case "$status" in
        "NO_HOOK")
            log_info "Status: No post-commit hook installed"
            ;;
        "HEIMDALL_INSTALLED")
            log_success "Status: Heimdall post-commit hook is installed and active"
            ;;
        "HEIMDALL_NOT_EXECUTABLE")
            log_warning "Status: Heimdall hook installed but not executable"
            ;;
        "OTHER_HOOK_EXISTS")
            log_warning "Status: Different post-commit hook exists"
            if [[ -f "$hook_file" ]]; then
                log_info "Existing hook preview:"
                head -10 "$hook_file" | sed 's/^/  /'
                if [[ $(wc -l < "$hook_file") -gt 10 ]]; then
                    log_info "  ... (truncated, $(wc -l < "$hook_file") total lines)"
                fi
            fi
            ;;
    esac
}

# Create chained hook that preserves existing functionality
create_chained_hook() {
    local repo_path="$1"
    local hook_file="$repo_path/.git/hooks/post-commit"
    local backup_file="$hook_file.heimdall-backup"
    local temp_file="$hook_file.tmp"

    # Create backup of existing hook
    cp "$hook_file" "$backup_file"
    log_info "Backed up existing hook to: $backup_file"

    # Create new chained hook
    cat > "$temp_file" << EOF
#!/bin/bash
# Chained post-commit hook with Heimdall MCP Server integration
# Original hook preserved and executed first

set -e

# Execute original hook first
if [[ -f "$backup_file" ]] && [[ -x "$backup_file" ]]; then
    echo "Executing original post-commit hook..."
    "$backup_file" "\$@"
    original_exit_code=\$?

    if [[ \$original_exit_code -ne 0 ]]; then
        echo "Warning: Original hook exited with code \$original_exit_code"
        # Continue with Heimdall hook even if original fails
    fi
fi

# Execute Heimdall hook
if [[ -f "$HOOK_SCRIPT" ]] && [[ -x "$HOOK_SCRIPT" ]]; then
    echo "Executing Heimdall incremental git loading..."
    "$HOOK_SCRIPT" "\$@"
else
    echo "Warning: Heimdall hook script not found or not executable: $HOOK_SCRIPT"
fi

exit 0
EOF

    # Make executable and replace
    chmod +x "$temp_file"
    mv "$temp_file" "$hook_file"

    log_success "Created chained hook preserving original functionality"
}

# Install hook
install_hook() {
    local repo_path="$1"
    local force="$2"
    local dry_run="$3"

    local hook_file="$repo_path/.git/hooks/post-commit"
    local hooks_dir="$repo_path/.git/hooks"
    local status

    status=$(get_hook_status "$repo_path")

    # Create hooks directory if it doesn't exist
    if [[ ! -d "$hooks_dir" ]]; then
        if [[ "$dry_run" == "true" ]]; then
            log_info "[DRY RUN] Would create hooks directory: $hooks_dir"
        else
            mkdir -p "$hooks_dir"
            log_info "Created hooks directory: $hooks_dir"
        fi
    fi

    case "$status" in
        "NO_HOOK")
            if [[ "$dry_run" == "true" ]]; then
                log_info "[DRY RUN] Would create new Heimdall post-commit hook"
                log_info "[DRY RUN] Target: $hook_file"
            else
                # Create direct symlink to our hook script
                ln -sf "$HOOK_SCRIPT" "$hook_file"
                log_success "Installed Heimdall post-commit hook"
            fi
            ;;

        "HEIMDALL_INSTALLED")
            if [[ "$force" == "true" ]]; then
                if [[ "$dry_run" == "true" ]]; then
                    log_info "[DRY RUN] Would reinstall Heimdall hook (forced)"
                else
                    ln -sf "$HOOK_SCRIPT" "$hook_file"
                    log_success "Reinstalled Heimdall post-commit hook (forced)"
                fi
            else
                log_warning "Heimdall hook already installed. Use --force to reinstall."
                return 0
            fi
            ;;

        "HEIMDALL_NOT_EXECUTABLE")
            if [[ "$dry_run" == "true" ]]; then
                log_info "[DRY RUN] Would fix hook permissions"
            else
                chmod +x "$hook_file"
                log_success "Fixed Heimdall hook permissions"
            fi
            ;;

        "OTHER_HOOK_EXISTS")
            if [[ "$force" == "true" ]]; then
                if [[ "$dry_run" == "true" ]]; then
                    log_info "[DRY RUN] Would create chained hook preserving existing hook"
                    log_info "[DRY RUN] Existing hook would be backed up and chained"
                else
                    create_chained_hook "$repo_path"
                fi
            else
                log_warning "Another post-commit hook already exists."
                log_warning "Use --force to create a chained hook that preserves existing functionality."
                log_warning "Or manually integrate Heimdall hook with your existing hook."
                return 1
            fi
            ;;
    esac

    if [[ "$dry_run" != "true" ]]; then
        log_success "Hook installation completed successfully"
        log_info "The hook will automatically process new commits for memory storage"
        log_info "Hook logs are written to: ~/.heimdall/hook.log"
    fi
}

# Uninstall hook
uninstall_hook() {
    local repo_path="$1"
    local dry_run="$2"

    local hook_file="$repo_path/.git/hooks/post-commit"
    local backup_file="$hook_file.heimdall-backup"
    local status

    status=$(get_hook_status "$repo_path")

    case "$status" in
        "NO_HOOK")
            log_info "No post-commit hook to uninstall"
            return 0
            ;;

        "HEIMDALL_INSTALLED")
            # Check if this is a chained hook with backup
            if [[ -f "$backup_file" ]]; then
                if [[ "$dry_run" == "true" ]]; then
                    log_info "[DRY RUN] Would restore original hook from backup"
                    log_info "[DRY RUN] Backup: $backup_file"
                else
                    mv "$backup_file" "$hook_file"
                    log_success "Restored original post-commit hook from backup"
                fi
            else
                if [[ "$dry_run" == "true" ]]; then
                    log_info "[DRY RUN] Would remove Heimdall post-commit hook"
                else
                    rm -f "$hook_file"
                    log_success "Removed Heimdall post-commit hook"
                fi
            fi
            ;;

        "HEIMDALL_NOT_EXECUTABLE")
            if [[ "$dry_run" == "true" ]]; then
                log_info "[DRY RUN] Would remove non-executable Heimdall hook"
            else
                rm -f "$hook_file"
                log_success "Removed non-executable Heimdall hook"
            fi
            ;;

        "OTHER_HOOK_EXISTS")
            # Check if it's a chained hook with backup
            if [[ -f "$backup_file" ]]; then
                if [[ "$dry_run" == "true" ]]; then
                    log_info "[DRY RUN] Would restore original hook from backup"
                    log_info "[DRY RUN] Backup: $backup_file"
                else
                    mv "$backup_file" "$hook_file"
                    log_success "Restored original post-commit hook from backup"
                fi
            else
                log_warning "Found non-Heimdall post-commit hook"
                log_warning "Manual removal required to avoid breaking existing functionality"
                log_info "Hook file: $hook_file"
                return 1
            fi
            ;;
    esac
}

# Main function
main() {
    local action="install"
    local repo_path="."
    local force="false"
    local dry_run="false"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --install)
                action="install"
                shift
                ;;
            --uninstall)
                action="uninstall"
                shift
                ;;
            --status)
                action="status"
                shift
                ;;
            --force)
                force="true"
                shift
                ;;
            --dry-run)
                dry_run="true"
                shift
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            -*)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
            *)
                repo_path="$1"
                shift
                ;;
        esac
    done

    # Convert to absolute path
    repo_path="$(cd "$repo_path" && pwd)"

    # Validate inputs
    validate_git_repo "$repo_path" || exit 1
    validate_hook_script || exit 1

    # Execute action
    case "$action" in
        "install")
            install_hook "$repo_path" "$force" "$dry_run"
            ;;
        "uninstall")
            uninstall_hook "$repo_path" "$dry_run"
            ;;
        "status")
            show_status "$repo_path"
            ;;
    esac
}

# Run main function
main "$@"
