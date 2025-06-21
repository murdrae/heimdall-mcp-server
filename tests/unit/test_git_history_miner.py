"""
Unit tests for GitHistoryMiner.

Tests the secure GitPython wrapper for git repository analysis,
including security controls, error handling, and resource management.
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from git import Actor, Repo

from cognitive_memory.git_analysis.commit import Commit
from cognitive_memory.git_analysis.history_miner import (
    GITPYTHON_AVAILABLE,
    GitHistoryMiner,
    create_git_history_miner,
    validate_git_repository,
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
        assert miner.repo is not None

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

    def test_context_manager_usage(self, temp_git_repo):
        """Test context manager functionality."""
        with GitHistoryMiner(temp_git_repo) as miner:
            assert miner.repo is not None

        # Should be closed after context manager
        assert miner.repo is None

    def test_manual_close(self, temp_git_repo):
        """Test manual resource cleanup."""
        miner = GitHistoryMiner(temp_git_repo)
        assert miner.repo is not None

        miner.close()
        assert miner.repo is None

    def test_close_with_exception(self, temp_git_repo):
        """Test close handles exceptions gracefully."""
        miner = GitHistoryMiner(temp_git_repo)

        # Mock repo.close to raise an exception
        miner.repo.close = MagicMock(side_effect=Exception("Close error"))

        # Should not raise exception
        miner.close()
        assert miner.repo is None


class TestGitHistoryMinerValidation:
    """Test repository validation methods."""

    @pytest.fixture
    def real_git_repo(self):
        """Create a real git repository for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "test_repo"
            repo_path.mkdir()

            repo = Repo.init(str(repo_path))
            test_file = repo_path / "test.txt"
            test_file.write_text("Hello, world!")

            repo.index.add([str(test_file)])
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

    def test_validate_repository_no_repo_initialized(self):
        """Test validation when repo is None."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "test_repo"
            repo_path.mkdir()
            git_dir = repo_path / ".git"
            git_dir.mkdir()

            miner = GitHistoryMiner(str(repo_path))
            miner.repo = None  # Simulate uninitialized repo

            result = miner.validate_repository()
            assert result is False

    def test_validate_repository_no_commits(self):
        """Test validation with repository that has no commits."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "empty_repo"
            repo_path.mkdir()

            # Initialize empty git repository
            Repo.init(str(repo_path))

            miner = GitHistoryMiner(str(repo_path))
            result = miner.validate_repository()
            assert result is False

    def test_validate_repository_no_head(self, real_git_repo):
        """Test validation when HEAD cannot be accessed."""
        # Mock repo.head to raise an exception
        real_git_repo.repo.head = MagicMock()
        real_git_repo.repo.head.commit = MagicMock(side_effect=Exception("No HEAD"))

        result = real_git_repo.validate_repository()
        assert result is False

    def test_validate_repository_iter_commits_exception(self, real_git_repo):
        """Test validation when iter_commits raises exception."""
        # Mock iter_commits to raise an exception
        real_git_repo.repo.iter_commits = MagicMock(side_effect=Exception("No commits"))

        result = real_git_repo.validate_repository()
        assert result is False


class TestGitHistoryMinerExtraction:
    """Test commit history extraction methods."""

    @pytest.fixture
    def multi_commit_repo(self):
        """Create a git repository with multiple commits."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "test_repo"
            repo_path.mkdir()

            repo = Repo.init(str(repo_path))
            author = Actor("Test User", "test@example.com")

            # Create multiple files and commits
            commits_data = [
                ("file1.py", "print('file1')", "Initial file1"),
                ("file2.py", "print('file2')", "Initial file2"),
                ("file1.py", "print('file1 updated')", "Update file1"),
                ("file3.py", "print('file3')", "Add file3"),
            ]

            for filename, content, message in commits_data:
                file_path = repo_path / filename
                file_path.write_text(content)
                repo.index.add([str(file_path)])
                repo.index.commit(message, author=author, committer=author)

            yield GitHistoryMiner(str(repo_path))

    def test_extract_commit_history_success(self, multi_commit_repo):
        """Test successful commit history extraction."""
        commits = list(multi_commit_repo.extract_commit_history())

        assert len(commits) == 4
        for commit in commits:
            assert isinstance(commit, Commit)
            assert len(commit.hash) == 40  # SHA-1 hash length
            assert commit.author_name == "Test User"
            assert commit.author_email == "test@example.com"

    def test_extract_commit_history_max_commits_limit(self, multi_commit_repo):
        """Test max_commits parameter."""
        commits = list(multi_commit_repo.extract_commit_history(max_commits=2))
        assert len(commits) == 2

    def test_extract_commit_history_security_limit(self, multi_commit_repo):
        """Test security limit on max_commits."""
        # Request more than security limit
        commits = list(multi_commit_repo.extract_commit_history(max_commits=50000))
        # Should still work, but limited to 10000 internally
        assert len(commits) == 4  # Our test repo only has 4 commits

    def test_extract_commit_history_date_filtering(self, multi_commit_repo):
        """Test date filtering parameters."""
        # Test with date filters (should still return commits since we use fixed dates)
        since_date = datetime(2022, 1, 1)
        until_date = datetime(2024, 1, 1)

        commits = list(
            multi_commit_repo.extract_commit_history(
                since_date=since_date, until_date=until_date
            )
        )

        assert isinstance(commits, list)  # Should return a list

    def test_extract_commit_history_branch_filtering(self, multi_commit_repo):
        """Test branch filtering."""
        # Test with specific branch (main/master should exist)
        commits = list(multi_commit_repo.extract_commit_history(branch="master"))
        assert isinstance(commits, list)

    def test_extract_commit_history_invalid_repository(self):
        """Test extraction with invalid repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "empty_repo"
            repo_path.mkdir()
            Repo.init(str(repo_path))  # Empty repo

            miner = GitHistoryMiner(str(repo_path))

            with pytest.raises(ValueError, match="Repository validation failed"):
                list(miner.extract_commit_history())

    def test_extract_commit_history_commit_processing_error(self, multi_commit_repo):
        """Test handling of commit processing errors."""
        # Mock _convert_commit_to_object to fail for some commits
        original_convert = multi_commit_repo._convert_commit_to_object
        call_count = [0]

        def mock_convert(commit):
            call_count[0] += 1
            if call_count[0] == 2:  # Fail on second commit
                raise Exception("Processing error")
            return original_convert(commit)

        multi_commit_repo._convert_commit_to_object = mock_convert

        commits = list(multi_commit_repo.extract_commit_history())
        # Should have 3 commits (1 failed, 3 succeeded)
        assert len(commits) == 3

    def test_convert_commit_to_object_success(self, multi_commit_repo):
        """Test successful commit object conversion."""
        # Get a real commit from the repository
        git_commit = next(multi_commit_repo.repo.iter_commits(max_count=1))

        commit_obj = multi_commit_repo._convert_commit_to_object(git_commit)

        assert isinstance(commit_obj, Commit)
        assert commit_obj.hash == git_commit.hexsha
        assert commit_obj.message == git_commit.message.strip()
        assert commit_obj.author_name == git_commit.author.name
        assert commit_obj.author_email == git_commit.author.email

    def test_convert_commit_to_object_with_parents(self, multi_commit_repo):
        """Test commit conversion with parent commits."""
        # Get a commit that has parents (not the first commit)
        commits = list(multi_commit_repo.repo.iter_commits())
        if len(commits) > 1:
            git_commit = commits[0]  # Most recent commit (should have parents)

            commit_obj = multi_commit_repo._convert_commit_to_object(git_commit)

            assert isinstance(commit_obj, Commit)
            assert len(commit_obj.parent_hashes) == len(git_commit.parents)

    def test_convert_commit_to_object_initial_commit(self, multi_commit_repo):
        """Test conversion of initial commit (no parents)."""
        # Get the initial commit (last in the iterator)
        commits = list(multi_commit_repo.repo.iter_commits())
        initial_commit = commits[-1]

        commit_obj = multi_commit_repo._convert_commit_to_object(initial_commit)

        assert isinstance(commit_obj, Commit)
        assert len(commit_obj.parent_hashes) == 0
        # Initial commit should have file changes for all files added
        assert len(commit_obj.file_changes) > 0

    def test_convert_commit_to_object_file_changes(self, multi_commit_repo):
        """Test file changes extraction in commit conversion."""
        # Get a commit with file changes
        git_commit = next(multi_commit_repo.repo.iter_commits(max_count=1))

        commit_obj = multi_commit_repo._convert_commit_to_object(git_commit)

        assert isinstance(commit_obj, Commit)
        assert len(commit_obj.file_changes) > 0

        for file_change in commit_obj.file_changes:
            assert file_change.file_path
            assert file_change.change_type in [
                "A",
                "M",
                "D",
                "R",
                "C",
                "T",
                "U",
                "X",
                "B",
            ]

    def test_convert_commit_to_object_exception_handling(self, multi_commit_repo):
        """Test exception handling in commit conversion."""
        # Create a mock commit that will cause an exception
        mock_commit = MagicMock()
        mock_commit.hexsha = "invalid"
        mock_commit.message = "test"
        mock_commit.author.name = "test"
        mock_commit.author.email = "test@example.com"
        mock_commit.committed_date = 1609459200  # Valid timestamp
        mock_commit.parents = []

        # This should return None due to validation failure
        result = multi_commit_repo._convert_commit_to_object(mock_commit)
        assert result is None


class TestGitHistoryMinerStats:
    """Test repository statistics methods."""

    @pytest.fixture
    def stats_repo(self):
        """Create a repository for statistics testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "stats_repo"
            repo_path.mkdir()

            repo = Repo.init(str(repo_path))
            author = Actor("Stats User", "stats@example.com")

            # Create multiple commits and branches
            test_file = repo_path / "stats.txt"
            test_file.write_text("Initial content")
            repo.index.add([str(test_file)])
            repo.index.commit("Initial commit", author=author, committer=author)

            # Create a branch
            repo.create_head("feature_branch")

            # Add more commits
            for i in range(3):
                test_file.write_text(f"Content update {i}")
                repo.index.add([str(test_file)])
                repo.index.commit(f"Update {i}", author=author, committer=author)

            # Create a tag
            repo.create_tag("v1.0")

            yield GitHistoryMiner(str(repo_path))

    def test_get_repository_stats_success(self, stats_repo):
        """Test successful repository statistics collection."""
        stats = stats_repo.get_repository_stats()

        assert isinstance(stats, dict)
        assert "repository_path" in stats
        assert "total_commits" in stats
        assert "total_branches" in stats
        assert "total_tags" in stats
        assert "active_branch" in stats
        assert "last_commit_date" in stats
        assert "first_commit_date" in stats

        assert stats["total_commits"] == 4  # Initial + 3 updates
        assert stats["total_branches"] >= 2  # master/main + feature_branch
        assert stats["total_tags"] >= 1  # v1.0

    def test_get_repository_stats_invalid_repo(self):
        """Test stats collection with invalid repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "empty"
            repo_path.mkdir()
            git_dir = repo_path / ".git"
            git_dir.mkdir()

            miner = GitHistoryMiner(str(repo_path))
            miner.repo = None  # Simulate invalid repo

            stats = miner.get_repository_stats()
            assert stats == {}

    def test_get_repository_stats_exception_handling(self, stats_repo):
        """Test exception handling in stats collection."""
        # Mock iter_commits to raise an exception
        stats_repo.repo.iter_commits = MagicMock(side_effect=Exception("Stats error"))

        stats = stats_repo.get_repository_stats()

        # Should still return a dict with basic structure
        assert isinstance(stats, dict)
        assert "total_commits" in stats
        assert stats["total_commits"] == 0  # Due to exception


class TestUtilityFunctions:
    """Test utility functions."""

    @pytest.fixture
    def temp_git_repo(self):
        """Create a temporary git repository for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "util_repo"
            repo_path.mkdir()

            repo = Repo.init(str(repo_path))
            test_file = repo_path / "test.txt"
            test_file.write_text("Hello")

            repo.index.add([str(test_file)])
            author = Actor("Util User", "util@example.com")
            repo.index.commit("Test commit", author=author, committer=author)

            yield str(repo_path)

    def test_create_git_history_miner_success(self, temp_git_repo):
        """Test successful GitHistoryMiner creation."""
        miner = create_git_history_miner(temp_git_repo)
        assert isinstance(miner, GitHistoryMiner)
        assert str(miner.repository_path) == temp_git_repo

    def test_create_git_history_miner_failure(self):
        """Test GitHistoryMiner creation failure."""
        with pytest.raises(ValueError):
            create_git_history_miner("/invalid/path")

    def test_validate_git_repository_success(self, temp_git_repo):
        """Test successful git repository validation."""
        result = validate_git_repository(temp_git_repo)
        assert result is True

    def test_validate_git_repository_failure(self):
        """Test git repository validation failure."""
        result = validate_git_repository("/invalid/path")
        assert result is False

    def test_validate_git_repository_exception_handling(self):
        """Test exception handling in repository validation."""
        # Use a path that will cause an exception during validation
        with patch(
            "cognitive_memory.git_analysis.history_miner.create_git_history_miner",
            side_effect=Exception("Validation error"),
        ):
            result = validate_git_repository("/some/path")
            assert result is False
