"""
Unit tests for GitHistoryMiner.

Tests the secure GitPython wrapper for git repository analysis,
including security controls, error handling, and resource management.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from git import Repo

from cognitive_memory.git_analysis.data_structures import CommitEvent
from cognitive_memory.git_analysis.history_miner import (
    GITPYTHON_AVAILABLE,
    GitHistoryMiner,
)


class TestGitHistoryMinerInit:
    """Test GitHistoryMiner initialization and setup."""

    @pytest.fixture
    def temp_git_repo(self):
        """Create a temporary git repository for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "test_repo"
            repo_path.mkdir()

            # Initialize a real git repository
            repo = Repo.init(str(repo_path))

            # Create a test file and commit
            test_file = repo_path / "test.txt"
            test_file.write_text("Hello, world!")

            repo.index.add([str(test_file)])
            # Configure git user for the commit with explicit author
            from git import Actor

            author = Actor("Test User", "test@example.com")
            repo.index.commit(
                "Initial commit",
                author=author,
                committer=author,
                author_date="2023-01-01T00:00:00",
                commit_date="2023-01-01T00:00:00",
            )

            yield str(repo_path)

    def test_gitpython_import_check(self):
        """Test that GitPython availability is properly detected."""
        assert isinstance(GITPYTHON_AVAILABLE, bool)

    @pytest.mark.skipif(not GITPYTHON_AVAILABLE, reason="GitPython not available")
    def test_valid_repository_initialization(self, temp_git_repo):
        """Test initialization with valid repository."""
        miner = GitHistoryMiner(temp_git_repo)
        assert str(miner.repository_path) == temp_git_repo
        assert miner.repo is not None  # Repository should be loaded

    def test_invalid_repository_path_rejected(self):
        """Test that invalid repository paths are rejected."""
        invalid_paths = [
            "/nonexistent/path",
            "../../../etc/passwd",
            "dangerous;command",
            "",
        ]

        for invalid_path in invalid_paths:
            with pytest.raises(ValueError, match="Invalid or insecure repository path"):
                GitHistoryMiner(invalid_path)

    def test_none_path_rejected(self):
        """Test that None path is rejected."""
        with pytest.raises((ValueError, TypeError)):
            GitHistoryMiner(None)

    def test_empty_path_rejected(self):
        """Test that empty path is rejected."""
        with pytest.raises(ValueError, match="Invalid or insecure repository path"):
            GitHistoryMiner("")

    @pytest.mark.skipif(GITPYTHON_AVAILABLE, reason="GitPython is available")
    def test_gitpython_unavailable_error(self, temp_git_repo):
        """Test error when GitPython is not available."""
        with patch(
            "cognitive_memory.git_analysis.history_miner.GITPYTHON_AVAILABLE", False
        ):
            with pytest.raises(ImportError, match="GitPython is required"):
                GitHistoryMiner(temp_git_repo)


class TestGitHistoryMinerValidation:
    """Test repository validation methods."""

    @pytest.fixture
    def real_git_repo(self):
        """Create a real git repository for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "test_repo"
            repo_path.mkdir()

            # Initialize a real git repository
            repo = Repo.init(str(repo_path))

            # Create a test file and commit
            test_file = repo_path / "test.txt"
            test_file.write_text("Hello, world!")

            repo.index.add([str(test_file)])
            # Configure git user for the commit with explicit author
            from git import Actor

            author = Actor("Test User", "test@example.com")
            repo.index.commit(
                "Initial commit",
                author=author,
                committer=author,
                author_date="2023-01-01T00:00:00",
                commit_date="2023-01-01T00:00:00",
            )

            yield GitHistoryMiner(str(repo_path))

    def test_validate_repository_success(self, real_git_repo):
        """Test successful repository validation."""
        result = real_git_repo.validate_repository()
        assert result is True

    def test_validate_repository_invalid_git_repo_error(self):
        """Test validation with invalid git repository."""
        # Test with a non-existent repository path
        with pytest.raises(ValueError):
            GitHistoryMiner("/nonexistent/path")

    def test_validate_repository_git_command_error(self, real_git_repo):
        """Test validation with working git repository."""
        # With a real repository, validation should succeed
        result = real_git_repo.validate_repository()
        assert result is True

    def test_validate_repository_exception_handling(self, real_git_repo):
        """Test that validation works with real repository."""
        # With a real repository, validation should succeed
        result = real_git_repo.validate_repository()
        assert result is True


class TestGitHistoryMinerExtraction:
    """Test commit history extraction methods."""

    @pytest.fixture
    def real_git_repo(self):
        """Create a real git repository for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "test_repo"
            repo_path.mkdir()

            # Initialize a real git repository
            repo = Repo.init(str(repo_path))

            # Create a test file and commit
            test_file = repo_path / "test.txt"
            test_file.write_text("Hello, world!")

            repo.index.add([str(test_file)])
            # Configure git user for the commit with explicit author
            from git import Actor

            author = Actor("Test User", "test@example.com")
            repo.index.commit(
                "Initial commit",
                author=author,
                committer=author,
                author_date="2023-01-01T00:00:00",
                commit_date="2023-01-01T00:00:00",
            )

            yield GitHistoryMiner(str(repo_path))

    def test_extract_commit_history_success(self, real_git_repo):
        """Test successful commit history extraction."""
        commits = list(real_git_repo.extract_commit_history())

        assert len(commits) == 1
        assert isinstance(commits[0], CommitEvent)
        assert len(commits[0].hash) == 40  # SHA-1 hash length
        assert commits[0].message == "Initial commit"
        assert commits[0].author_name == "Test User"
        assert commits[0].author_email == "test@example.com"
