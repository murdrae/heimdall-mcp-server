"""Git hook management commands."""

import stat
from pathlib import Path
from typing import Literal

import typer
from rich.console import Console

console = Console()

# Embedded post-commit hook template
POST_COMMIT_HOOK_TEMPLATE = '''#!/usr/bin/env python3
"""
Heimdall MCP Server - Post-Commit Hook (Python Implementation)

Automatically processes the latest commit for memory storage using the
shared Qdrant architecture and centralized configuration system.

This hook replaces the bash implementation with cross-platform Python code
that directly integrates with the cognitive memory system without Docker
container dependencies.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Graceful imports with fallbacks
try:
    import git
except ImportError:
    print("Heimdall: WARNING: GitPython not available, cannot process git hooks")
    sys.exit(0)

try:
    from cognitive_memory.core.config import get_project_paths
    from cognitive_memory.main import initialize_system
    from heimdall.operations import CognitiveOperations
except ImportError as e:
    print(f"Heimdall: WARNING: Cannot import cognitive memory system: {e}")
    sys.exit(0)


def log_message(paths: Any, message: str, is_error: bool = False) -> None:
    """
    Log message to both console and file with colors.

    Args:
        paths: ProjectPaths object with log file location
        message: Message to log
        is_error: Whether this is an error message
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"

    # ANSI color codes
    BLUE = "\\033[34m"
    GREEN = "\\033[32m"
    YELLOW = "\\033[33m"
    RED = "\\033[31m"
    BOLD = "\\033[1m"
    RESET = "\\033[0m"

    # Print to console with colors (visible in git output)
    if is_error:
        prefix_colored = f"{RED}ERROR{RESET}"
        message_colored = f"{RED}{message}{RESET}"
    elif "memory loaded" in message or "memories loaded" in message:
        prefix_colored = f"{GREEN}SUCCESS{RESET}"
        message_colored = f"{GREEN}{message}{RESET}"
    elif "completed" in message:
        prefix_colored = f"{BLUE}INFO{RESET}"
        message_colored = f"{BLUE}{message}{RESET}"
    else:
        prefix_colored = f"{YELLOW}INFO{RESET}"
        message_colored = message

    print(f"{BOLD}Heimdall{RESET} [{prefix_colored}]: {message_colored}")

    # Log to file without colors
    try:
        with open(paths.log_file, "a", encoding="utf-8") as f:
            f.write(f"{log_entry}\\n")
    except Exception:
        pass  # Don't break hook if logging fails


def main() -> None:
    """
    Main post-commit hook execution.

    This function handles the complete post-commit processing workflow:
    1. Validate git repository and get latest commit info
    2. Initialize cognitive memory system
    3. Load the latest commit into memory via direct function call
    4. Log results appropriately

    Always exits with code 0 to prevent breaking git operations.
    """
    paths = None

    try:
        # Find git repository root using GitPython
        try:
            repo = git.Repo(search_parent_directories=True)
            repo_root = Path(repo.working_dir)
        except git.exc.InvalidGitRepositoryError:
            print("Heimdall: ERROR: Not in a git repository")
            sys.exit(0)
        except Exception as e:
            print(f"Heimdall: ERROR: Failed to access git repository: {e}")
            sys.exit(0)

        # Get project paths for logging
        paths = get_project_paths(repo_root)

        # Get latest commit info
        try:
            latest_commit = repo.head.commit
            commit_hash = latest_commit.hexsha
            commit_short = commit_hash[:8]
        except Exception as e:
            log_message(paths, f"Failed to get latest commit info: {e}", is_error=True)
            sys.exit(0)

        # Initialize cognitive memory system and execute git loading (suppress verbose output)
        try:
            import contextlib
            import io
            import os

            # Suppress all logging during the operation
            original_log_level = os.environ.get("LOG_LEVEL", "INFO")
            os.environ["LOG_LEVEL"] = "ERROR"

            # Also disable loguru directly
            try:
                from loguru import logger

                logger.disable("")  # Disable all loguru logging
            except ImportError:
                pass

            # Capture stdout to count memories loaded
            captured_output = io.StringIO()

            with contextlib.redirect_stdout(captured_output):
                cognitive_system = initialize_system()
                operations = CognitiveOperations(cognitive_system)

                # Use load_git_patterns which handles incremental loading automatically
                # with max_commits=1 to process only the latest commit
                result = operations.load_git_patterns(
                    repo_path=str(repo_root),
                    dry_run=False,
                    max_commits=1,  # Only process the latest commit
                )
                success = result.get("success", False)

            # Restore original log level and re-enable loguru
            os.environ["LOG_LEVEL"] = original_log_level
            try:
                from loguru import logger

                logger.enable("")  # Re-enable loguru logging
            except ImportError:
                pass

            # Extract memory count from operations result
            memories_loaded = result.get("memories_loaded", 0) if success else 0

            if success:
                if memories_loaded > 0:
                    memory_word = "memory" if memories_loaded == 1 else "memories"
                    log_message(
                        paths,
                        f"Processed commit {commit_short}: {memories_loaded} {memory_word} loaded",
                    )
                else:
                    log_message(
                        paths,
                        f"Processed commit {commit_short}: no new memories (incremental)",
                    )
            else:
                log_message(
                    paths,
                    f"WARNING: Failed to process commit {commit_short}",
                    is_error=True,
                )

        except Exception as e:
            log_message(
                paths,
                f"ERROR: Failed to process commit {commit_short}: {str(e)}",
                is_error=True,
            )

        log_message(paths, "Post-commit hook completed")

    except Exception as e:
        error_msg = f"Unexpected error in post-commit hook: {str(e)}"
        if paths:
            log_message(paths, error_msg, is_error=True)
        else:
            print(f"Heimdall: ERROR: {error_msg}")

    # Always exit 0 to never break git operations
    sys.exit(0)


if __name__ == "__main__":
    main()
'''


def log_info(message: str) -> None:
    """Log info message with proper formatting."""
    console.print(f"[blue][INFO][/blue] {message}")


def log_success(message: str) -> None:
    """Log success message with proper formatting."""
    console.print(f"[green][SUCCESS][/green] {message}")


def log_warning(message: str) -> None:
    """Log warning message with proper formatting."""
    console.print(f"[yellow][WARNING][/yellow] {message}")


def log_error(message: str) -> None:
    """Log error message with proper formatting."""
    console.print(f"[red][ERROR][/red] {message}")


def validate_git_repo(repo_path: Path) -> bool:
    """
    Validate git repository.

    Args:
        repo_path: Path to validate

    Returns:
        True if valid git repository
    """
    if not (repo_path / ".git").exists():
        log_error(f"Not a git repository: {repo_path}")
        log_error(
            "Please run this command from within a git repository or specify a valid path."
        )
        return False
    return True


def create_hook_script(hooks_dir: Path) -> Path:
    """
    Create the post-commit hook script in the hooks directory.

    Args:
        hooks_dir: Git hooks directory

    Returns:
        Path to the created hook script
    """
    hook_script = hooks_dir / "heimdall_post_commit_hook.py"

    # Write the hook script
    hook_script.write_text(POST_COMMIT_HOOK_TEMPLATE, encoding="utf-8")

    # Make it executable
    current_mode = hook_script.stat().st_mode
    hook_script.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return hook_script


def get_hook_status(
    repo_path: Path,
) -> Literal[
    "NO_HOOK", "HEIMDALL_INSTALLED", "HEIMDALL_NOT_EXECUTABLE", "OTHER_HOOK_EXISTS"
]:
    """
    Get current hook status.

    Args:
        repo_path: Repository path

    Returns:
        Hook status string
    """
    hook_file = repo_path / ".git" / "hooks" / "post-commit"

    if not hook_file.exists():
        return "NO_HOOK"

    try:
        content = hook_file.read_text(encoding="utf-8")
        if "Heimdall MCP Server" in content:
            mode = hook_file.stat().st_mode
            if mode & stat.S_IXUSR:
                return "HEIMDALL_INSTALLED"
            else:
                return "HEIMDALL_NOT_EXECUTABLE"
        else:
            return "OTHER_HOOK_EXISTS"
    except Exception:
        return "OTHER_HOOK_EXISTS"


def show_status(repo_path: Path) -> None:
    """
    Show current hook status.

    Args:
        repo_path: Repository path
    """
    hook_file = repo_path / ".git" / "hooks" / "post-commit"
    status = get_hook_status(repo_path)

    log_info(f"Repository: {repo_path}")
    log_info(f"Hook file: {hook_file}")

    if status == "NO_HOOK":
        log_info("Status: No post-commit hook installed")
    elif status == "HEIMDALL_INSTALLED":
        log_success("Status: Heimdall post-commit hook is installed and active")
    elif status == "HEIMDALL_NOT_EXECUTABLE":
        log_warning("Status: Heimdall hook installed but not executable")
    elif status == "OTHER_HOOK_EXISTS":
        log_warning("Status: Different post-commit hook exists")
        if hook_file.exists():
            log_info("Existing hook preview:")
            try:
                content = hook_file.read_text(encoding="utf-8")
                lines = content.split("\n")
                for _i, line in enumerate(lines[:10]):
                    console.print(f"  {line}")
                if len(lines) > 10:
                    log_info(f"  ... (truncated, {len(lines)} total lines)")
            except Exception:
                log_warning("Could not read existing hook file")


def create_chained_hook(repo_path: Path, hook_script: Path) -> None:
    """
    Create chained hook that preserves existing functionality.

    Args:
        repo_path: Repository path
        hook_script: Path to Heimdall hook script
    """
    hook_file = repo_path / ".git" / "hooks" / "post-commit"
    backup_file = hook_file.with_suffix(".heimdall-backup")
    temp_file = hook_file.with_suffix(".tmp")

    # Create backup of existing hook
    hook_file.rename(backup_file)
    log_info(f"Backed up existing hook to: {backup_file}")

    # Create new chained hook
    chained_content = f'''#!/bin/bash
# Chained post-commit hook with Heimdall MCP Server integration
# Original hook preserved and executed first

set -e

# Execute original hook first
if [[ -f "{backup_file}" ]] && [[ -x "{backup_file}" ]]; then
    echo "Executing original post-commit hook..."
    "{backup_file}" "$@"
    original_exit_code=$?

    if [[ $original_exit_code -ne 0 ]]; then
        echo "Warning: Original hook exited with code $original_exit_code"
        # Continue with Heimdall hook even if original fails
    fi
fi

# Execute Heimdall hook
if [[ -f "{hook_script}" ]] && [[ -x "{hook_script}" ]]; then
    echo "Executing Heimdall incremental git loading..."
    "{hook_script}" "$@"
else
    echo "Warning: Heimdall hook script not found or not executable: {hook_script}"
fi

exit 0
'''

    # Write and make executable
    temp_file.write_text(chained_content, encoding="utf-8")
    temp_file.chmod(
        temp_file.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    temp_file.rename(hook_file)

    log_success("Created chained hook preserving original functionality")


def install_hook(repo_path: Path, force: bool = False, dry_run: bool = False) -> bool:
    """
    Install hook with various strategies based on current state.

    Args:
        repo_path: Repository path
        force: Force installation even if hooks exist
        dry_run: Show what would be done without making changes

    Returns:
        True if installation succeeded
    """
    hook_file = repo_path / ".git" / "hooks" / "post-commit"
    hooks_dir = repo_path / ".git" / "hooks"
    status = get_hook_status(repo_path)

    # Create hooks directory if it doesn't exist
    if not hooks_dir.exists():
        if dry_run:
            log_info(f"[DRY RUN] Would create hooks directory: {hooks_dir}")
        else:
            hooks_dir.mkdir(parents=True, exist_ok=True)
            log_info(f"Created hooks directory: {hooks_dir}")

    # Create the hook script
    if not dry_run:
        hook_script = create_hook_script(hooks_dir)
    else:
        hook_script = hooks_dir / "heimdall_post_commit_hook.py"

    if status == "NO_HOOK":
        if dry_run:
            log_info("[DRY RUN] Would create new Heimdall post-commit hook")
            log_info(f"[DRY RUN] Target: {hook_file}")
        else:
            # Create symlink to our hook script
            if hook_file.exists():
                hook_file.unlink()
            hook_file.symlink_to(hook_script.resolve())
            log_success("Installed Heimdall post-commit hook")
        return True

    elif status == "HEIMDALL_INSTALLED":
        if force:
            if dry_run:
                log_info("[DRY RUN] Would reinstall Heimdall hook (forced)")
            else:
                if hook_file.exists():
                    hook_file.unlink()
                hook_file.symlink_to(hook_script.resolve())
                log_success("Reinstalled Heimdall post-commit hook (forced)")
            return True
        else:
            log_warning("Heimdall hook already installed. Use --force to reinstall.")
            return True

    elif status == "HEIMDALL_NOT_EXECUTABLE":
        if dry_run:
            log_info("[DRY RUN] Would fix hook permissions")
        else:
            current_mode = hook_file.stat().st_mode
            hook_file.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            log_success("Fixed Heimdall hook permissions")
        return True

    elif status == "OTHER_HOOK_EXISTS":
        if force:
            if dry_run:
                log_info("[DRY RUN] Would create chained hook preserving existing hook")
                log_info("[DRY RUN] Existing hook would be backed up and chained")
            else:
                create_chained_hook(repo_path, hook_script)
            return True
        else:
            log_warning("Another post-commit hook already exists.")
            log_warning(
                "Use --force to create a chained hook that preserves existing functionality."
            )
            log_warning("Or manually integrate Heimdall hook with your existing hook.")
            return False


def uninstall_hook(repo_path: Path, dry_run: bool = False) -> bool:
    """
    Uninstall hook with proper backup restoration.

    Args:
        repo_path: Repository path
        dry_run: Show what would be done without making changes

    Returns:
        True if uninstallation succeeded
    """
    hook_file = repo_path / ".git" / "hooks" / "post-commit"
    backup_file = hook_file.with_suffix(".heimdall-backup")
    hooks_dir = repo_path / ".git" / "hooks"
    hook_script = hooks_dir / "heimdall_post_commit_hook.py"
    status = get_hook_status(repo_path)

    if status == "NO_HOOK":
        log_info("No post-commit hook to uninstall")
        return True

    elif status in ["HEIMDALL_INSTALLED", "HEIMDALL_NOT_EXECUTABLE"]:
        # Check if this is a chained hook with backup
        if backup_file.exists():
            if dry_run:
                log_info("[DRY RUN] Would restore original hook from backup")
                log_info(f"[DRY RUN] Backup: {backup_file}")
            else:
                hook_file.unlink()
                backup_file.rename(hook_file)
                log_success("Restored original post-commit hook from backup")
        else:
            if dry_run:
                log_info("[DRY RUN] Would remove Heimdall post-commit hook")
            else:
                hook_file.unlink()
                log_success("Removed Heimdall post-commit hook")

        # Clean up hook script
        if not dry_run and hook_script.exists():
            hook_script.unlink()

        return True

    elif status == "OTHER_HOOK_EXISTS":
        # Check if it's a chained hook with backup
        if backup_file.exists():
            if dry_run:
                log_info("[DRY RUN] Would restore original hook from backup")
                log_info(f"[DRY RUN] Backup: {backup_file}")
            else:
                hook_file.unlink()
                backup_file.rename(hook_file)
                # Clean up hook script
                if hook_script.exists():
                    hook_script.unlink()
                log_success("Restored original post-commit hook from backup")
            return True
        else:
            log_warning("Found non-Heimdall post-commit hook")
            log_warning(
                "Manual removal required to avoid breaking existing functionality"
            )
            log_info(f"Hook file: {hook_file}")
            return False

    return False


def git_hook_install(
    repo_path: str = typer.Argument(
        ".", help="Repository path (defaults to current directory)"
    ),
    force: bool = typer.Option(
        False, "--force", help="Force installation even if hooks exist"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without making changes"
    ),
) -> None:
    """Install Heimdall post-commit hook for automatic memory processing."""
    try:
        repo_path_obj = Path(repo_path).resolve()

        if not validate_git_repo(repo_path_obj):
            raise typer.Exit(1)

        success = install_hook(repo_path_obj, force, dry_run)

        if success and not dry_run:
            log_success("Hook installation completed successfully")
            log_info(
                "The hook will automatically process new commits for memory storage"
            )
            log_info("Hook logs are written to: .heimdall/monitor.log")

        if not success:
            console.print("❌ Git hook installation failed", style="bold red")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"❌ Failed to install git hook: {e}", style="bold red")
        raise typer.Exit(1) from e


def git_hook_uninstall(
    repo_path: str = typer.Argument(
        ".", help="Repository path (defaults to current directory)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without making changes"
    ),
) -> None:
    """Uninstall Heimdall post-commit hook."""
    try:
        repo_path_obj = Path(repo_path).resolve()

        if not validate_git_repo(repo_path_obj):
            raise typer.Exit(1)

        success = uninstall_hook(repo_path_obj, dry_run)

        if not success:
            console.print("❌ Git hook uninstallation failed", style="bold red")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"❌ Failed to uninstall git hook: {e}", style="bold red")
        raise typer.Exit(1) from e


def git_hook_status(
    repo_path: str = typer.Argument(
        ".", help="Repository path (defaults to current directory)"
    ),
) -> None:
    """Show git hook installation status."""
    try:
        repo_path_obj = Path(repo_path).resolve()

        if not validate_git_repo(repo_path_obj):
            raise typer.Exit(1)

        show_status(repo_path_obj)

    except Exception as e:
        console.print(f"❌ Failed to check git hook status: {e}", style="bold red")
        raise typer.Exit(1) from e
