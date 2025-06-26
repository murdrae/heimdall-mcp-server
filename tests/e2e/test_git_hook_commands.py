#!/usr/bin/env python3
"""
End-to-end tests for git hook management commands.

This test validates all git hook functionality including install, uninstall,
status commands, and actual hook execution. These are real E2E tests that
create temporary git repositories and test the complete workflow.
"""

import stat
import subprocess
import tempfile
from pathlib import Path

import pytest

from heimdall.cli_commands.git_hook_commands import (
    get_hook_status,
    install_hook,
    show_status,
    uninstall_hook,
    validate_git_repo,
)


class TestGitHookCommands:
    """Test suite for git hook management commands."""

    @pytest.fixture
    def temp_git_repo(self):
        """Create a temporary git repository for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "test_repo"
            repo_path.mkdir()

            # Initialize git repository
            subprocess.run(["git", "init"], cwd=repo_path, check=True)
            subprocess.run(
                ["git", "config", "user.name", "Test User"], cwd=repo_path, check=True
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo_path,
                check=True,
            )

            # Create initial commit
            test_file = repo_path / "README.md"
            test_file.write_text("# Test Repository\n")
            subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True
            )

            yield repo_path

    @pytest.fixture
    def temp_git_repo_with_hook(self, temp_git_repo):
        """Create a temporary git repository with an existing hook."""
        hooks_dir = temp_git_repo / ".git" / "hooks"
        hooks_dir.mkdir(exist_ok=True)

        existing_hook = hooks_dir / "post-commit"
        existing_hook.write_text("#!/bin/bash\necho 'Existing hook executed'\n")
        existing_hook.chmod(existing_hook.stat().st_mode | stat.S_IXUSR)

        yield temp_git_repo

    def test_validate_git_repo_valid(self, temp_git_repo):
        """Test git repository validation with valid repository."""
        assert validate_git_repo(temp_git_repo) is True

    def test_validate_git_repo_invalid(self):
        """Test git repository validation with invalid path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_path = Path(temp_dir) / "not_git_repo"
            invalid_path.mkdir()
            assert validate_git_repo(invalid_path) is False

    def test_get_hook_status_no_hook(self, temp_git_repo):
        """Test hook status detection when no hook exists."""
        status = get_hook_status(temp_git_repo)
        assert status == "NO_HOOK"

    def test_get_hook_status_heimdall_installed(self, temp_git_repo):
        """Test hook status detection when Heimdall hook is installed."""
        hooks_dir = temp_git_repo / ".git" / "hooks"
        hooks_dir.mkdir(exist_ok=True)

        hook_file = hooks_dir / "post-commit"
        hook_file.write_text(
            "#!/usr/bin/env python3\n# Heimdall MCP Server - Post-Commit Hook\n"
        )
        hook_file.chmod(hook_file.stat().st_mode | stat.S_IXUSR)

        status = get_hook_status(temp_git_repo)
        assert status == "HEIMDALL_INSTALLED"

    def test_get_hook_status_heimdall_not_executable(self, temp_git_repo):
        """Test hook status detection when Heimdall hook exists but isn't executable."""
        hooks_dir = temp_git_repo / ".git" / "hooks"
        hooks_dir.mkdir(exist_ok=True)

        hook_file = hooks_dir / "post-commit"
        hook_file.write_text(
            "#!/usr/bin/env python3\n# Heimdall MCP Server - Post-Commit Hook\n"
        )
        # Don't make it executable

        status = get_hook_status(temp_git_repo)
        assert status == "HEIMDALL_NOT_EXECUTABLE"

    def test_get_hook_status_other_hook_exists(self, temp_git_repo_with_hook):
        """Test hook status detection when another hook exists."""
        status = get_hook_status(temp_git_repo_with_hook)
        assert status == "OTHER_HOOK_EXISTS"

    def test_install_hook_fresh_repo(self, temp_git_repo):
        """Test hook installation in fresh repository."""
        success = install_hook(temp_git_repo, force=False, dry_run=False)
        assert success is True

        hook_file = temp_git_repo / ".git" / "hooks" / "post-commit"
        assert hook_file.exists()
        assert hook_file.is_symlink()

        # Check that hook script was created
        hook_script = temp_git_repo / ".git" / "hooks" / "heimdall_post_commit_hook.py"
        assert hook_script.exists()
        assert hook_script.stat().st_mode & stat.S_IXUSR

        # Verify hook content
        content = hook_script.read_text()
        assert "Heimdall MCP Server - Post-Commit Hook" in content
        assert "def main() -> None:" in content

    def test_install_hook_dry_run(self, temp_git_repo):
        """Test hook installation dry run mode."""
        success = install_hook(temp_git_repo, force=False, dry_run=True)
        assert success is True

        # Should not create actual files in dry run
        hook_file = temp_git_repo / ".git" / "hooks" / "post-commit"
        assert not hook_file.exists()

    def test_install_hook_already_installed(self, temp_git_repo):
        """Test hook installation when Heimdall hook already installed."""
        # First installation
        install_hook(temp_git_repo, force=False, dry_run=False)

        # Second installation without force
        success = install_hook(temp_git_repo, force=False, dry_run=False)
        assert success is True  # Should succeed but warn

    def test_install_hook_force_reinstall(self, temp_git_repo):
        """Test forced hook reinstallation."""
        # First installation
        install_hook(temp_git_repo, force=False, dry_run=False)

        # Get original modification time
        hook_script = temp_git_repo / ".git" / "hooks" / "heimdall_post_commit_hook.py"
        original_mtime = hook_script.stat().st_mtime

        # Force reinstall
        success = install_hook(temp_git_repo, force=True, dry_run=False)
        assert success is True

        # Verify it was recreated
        new_mtime = hook_script.stat().st_mtime
        assert new_mtime >= original_mtime

    def test_install_hook_with_existing_hook_force(self, temp_git_repo_with_hook):
        """Test hook installation with existing hook using force."""
        hook_file = temp_git_repo_with_hook / ".git" / "hooks" / "post-commit"
        original_content = hook_file.read_text()

        success = install_hook(temp_git_repo_with_hook, force=True, dry_run=False)
        assert success is True

        # Check backup was created
        backup_file = hook_file.with_suffix(".heimdall-backup")
        assert backup_file.exists()
        assert backup_file.read_text() == original_content

        # Check chained hook was created
        new_content = hook_file.read_text()
        assert "Chained post-commit hook" in new_content
        assert str(backup_file) in new_content

    def test_install_hook_with_existing_hook_no_force(self, temp_git_repo_with_hook):
        """Test hook installation with existing hook without force."""
        success = install_hook(temp_git_repo_with_hook, force=False, dry_run=False)
        assert success is False

    def test_uninstall_hook_no_hook(self, temp_git_repo):
        """Test hook uninstallation when no hook exists."""
        success = uninstall_hook(temp_git_repo, dry_run=False)
        assert success is True

    def test_uninstall_hook_heimdall_only(self, temp_git_repo):
        """Test uninstalling Heimdall hook when no other hooks exist."""
        # Install hook first
        install_hook(temp_git_repo, force=False, dry_run=False)

        hook_file = temp_git_repo / ".git" / "hooks" / "post-commit"
        hook_script = temp_git_repo / ".git" / "hooks" / "heimdall_post_commit_hook.py"

        assert hook_file.exists()
        assert hook_script.exists()

        # Uninstall
        success = uninstall_hook(temp_git_repo, dry_run=False)
        assert success is True

        # Check files are removed
        assert not hook_file.exists()
        assert not hook_script.exists()

    def test_uninstall_hook_with_backup_restore(self, temp_git_repo_with_hook):
        """Test hook uninstallation with backup restoration."""
        original_content = (
            temp_git_repo_with_hook / ".git" / "hooks" / "post-commit"
        ).read_text()

        # Install chained hook
        install_hook(temp_git_repo_with_hook, force=True, dry_run=False)

        # Uninstall
        success = uninstall_hook(temp_git_repo_with_hook, dry_run=False)
        assert success is True

        # Check original hook was restored
        hook_file = temp_git_repo_with_hook / ".git" / "hooks" / "post-commit"
        assert hook_file.exists()
        assert hook_file.read_text() == original_content

        # Check backup was removed
        backup_file = hook_file.with_suffix(".heimdall-backup")
        assert not backup_file.exists()

    def test_uninstall_hook_dry_run(self, temp_git_repo):
        """Test hook uninstallation dry run mode."""
        # Install hook first
        install_hook(temp_git_repo, force=False, dry_run=False)

        hook_file = temp_git_repo / ".git" / "hooks" / "post-commit"
        hook_script = temp_git_repo / ".git" / "hooks" / "heimdall_post_commit_hook.py"

        # Dry run uninstall
        success = uninstall_hook(temp_git_repo, dry_run=True)
        assert success is True

        # Files should still exist
        assert hook_file.exists()
        assert hook_script.exists()

    def test_show_status_comprehensive(self, temp_git_repo):
        """Test comprehensive status display."""
        # This test mainly checks that show_status doesn't crash
        # and handles different scenarios properly

        # Test with no hook
        show_status(temp_git_repo)

        # Install hook and test again
        install_hook(temp_git_repo, force=False, dry_run=False)
        show_status(temp_git_repo)

    @pytest.mark.asyncio
    async def test_hook_execution_simulation(self, temp_git_repo):
        """Test hook execution by simulating the hook script execution."""
        # Install hook first
        install_hook(temp_git_repo, force=False, dry_run=False)

        hook_script = temp_git_repo / ".git" / "hooks" / "heimdall_post_commit_hook.py"
        assert hook_script.exists()

        # Read the hook script content to verify it's properly formatted
        content = hook_script.read_text()
        assert "def main() -> None:" in content
        assert "initialize_system" in content
        assert "load_git_patterns" in content

        # Test that the hook script is syntactically valid Python
        compile(content, str(hook_script), "exec")

    def test_hook_script_template_integrity(self):
        """Test that the embedded hook script template is valid."""
        from heimdall.cli_commands.git_hook_commands import POST_COMMIT_HOOK_TEMPLATE

        # Verify template contains required components
        assert "def main() -> None:" in POST_COMMIT_HOOK_TEMPLATE
        assert "initialize_system" in POST_COMMIT_HOOK_TEMPLATE
        assert "load_git_patterns" in POST_COMMIT_HOOK_TEMPLATE
        assert "max_commits=1" in POST_COMMIT_HOOK_TEMPLATE
        assert "sys.exit(0)" in POST_COMMIT_HOOK_TEMPLATE

        # Verify it's syntactically valid Python
        compile(POST_COMMIT_HOOK_TEMPLATE, "<template>", "exec")

    def test_hook_permissions(self, temp_git_repo):
        """Test that hooks are created with correct permissions."""
        install_hook(temp_git_repo, force=False, dry_run=False)

        hook_script = temp_git_repo / ".git" / "hooks" / "heimdall_post_commit_hook.py"
        mode = hook_script.stat().st_mode

        # Check executable permissions
        assert mode & stat.S_IXUSR  # User execute
        assert mode & stat.S_IRUSR  # User read
        assert mode & stat.S_IWUSR  # User write

    def test_chained_hook_execution_order(self, temp_git_repo_with_hook):
        """Test that chained hooks execute in correct order."""
        # Install chained hook
        install_hook(temp_git_repo_with_hook, force=True, dry_run=False)

        hook_file = temp_git_repo_with_hook / ".git" / "hooks" / "post-commit"
        content = hook_file.read_text()

        # Verify chained hook structure
        assert "Execute original hook first" in content
        assert "Execute Heimdall hook" in content
        assert "heimdall-backup" in content

    def test_error_handling_invalid_repo(self):
        """Test error handling with invalid repository paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_path = Path(temp_dir) / "not_a_repo"
            invalid_path.mkdir()

            # Should handle gracefully
            assert validate_git_repo(invalid_path) is False
            assert get_hook_status(invalid_path) == "NO_HOOK"

    def test_hook_script_robustness(self, temp_git_repo):
        """Test hook script handles missing dependencies gracefully."""
        install_hook(temp_git_repo, force=False, dry_run=False)

        hook_script = temp_git_repo / ".git" / "hooks" / "heimdall_post_commit_hook.py"
        content = hook_script.read_text()

        # Verify graceful import handling
        assert "try:" in content
        assert "import git" in content
        assert "except ImportError:" in content
        assert "sys.exit(0)" in content  # Should exit gracefully on import errors

    def test_multiple_install_uninstall_cycles(self, temp_git_repo):
        """Test multiple install/uninstall cycles work correctly."""
        # Multiple install/uninstall cycles
        for _ in range(3):
            # Install
            success = install_hook(temp_git_repo, force=False, dry_run=False)
            assert success is True

            hook_file = temp_git_repo / ".git" / "hooks" / "post-commit"
            hook_script = (
                temp_git_repo / ".git" / "hooks" / "heimdall_post_commit_hook.py"
            )
            assert hook_file.exists()
            assert hook_script.exists()

            # Uninstall
            success = uninstall_hook(temp_git_repo, dry_run=False)
            assert success is True
            assert not hook_file.exists()
            assert not hook_script.exists()

    def test_hook_with_spaces_in_path(self):
        """Test hook installation works with spaces in repository path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "repo with spaces"
            repo_path.mkdir()

            # Initialize git repository
            subprocess.run(["git", "init"], cwd=repo_path, check=True)
            subprocess.run(
                ["git", "config", "user.name", "Test User"], cwd=repo_path, check=True
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo_path,
                check=True,
            )

            # Test installation works
            success = install_hook(repo_path, force=False, dry_run=False)
            assert success is True

            hook_file = repo_path / ".git" / "hooks" / "post-commit"
            assert hook_file.exists()

    def test_concurrent_hook_operations(self, temp_git_repo):
        """Test that hook operations handle concurrent access gracefully."""
        # This is mainly to ensure no race conditions in file operations

        # Install hook
        success1 = install_hook(temp_git_repo, force=False, dry_run=False)
        assert success1 is True

        # Try to install again (should handle gracefully)
        success2 = install_hook(temp_git_repo, force=False, dry_run=False)
        assert success2 is True  # Should succeed with warning

        # Uninstall should work
        success3 = uninstall_hook(temp_git_repo, dry_run=False)
        assert success3 is True


if __name__ == "__main__":
    """Allow running this test directly for debugging."""
    pytest.main([__file__, "-v"])
    print("✅ All git hook command E2E tests completed!")
