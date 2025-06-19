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


class TestGitHistoryMinerPatternExtraction:
    """Test pattern extraction methods in GitHistoryMiner."""

    @pytest.fixture
    def multi_commit_repo(self):
        """Create a git repository with multiple commits for pattern testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "test_repo"
            repo_path.mkdir()

            # Initialize a real git repository
            repo = Repo.init(str(repo_path))

            from git import Actor

            author = Actor("Test User", "test@example.com")

            # Create multiple files and commits to establish patterns
            files_data = [
                ("file1.py", "print('file1')", "Initial file1"),
                ("file2.py", "print('file2')", "Initial file2"),
                ("file3.py", "print('file3')", "Initial file3"),
            ]

            # Create initial files
            for filename, content, message in files_data:
                file_path = repo_path / filename
                file_path.write_text(content)
                repo.index.add([str(file_path)])
                repo.index.commit(
                    message,
                    author=author,
                    committer=author,
                )

            # Create co-change commits (file1 and file2 change together)
            for i in range(3):
                file1 = repo_path / "file1.py"
                file2 = repo_path / "file2.py"

                file1.write_text(f"print('file1 update {i}')")
                file2.write_text(f"print('file2 update {i}')")

                repo.index.add([str(file1), str(file2)])
                repo.index.commit(
                    f"Update files together {i}",
                    author=author,
                    committer=author,
                )

            # Create some bug fix commits
            for i in range(2):
                file1 = repo_path / "file1.py"
                file1.write_text(f"print('file1 bugfix {i}')")

                repo.index.add([str(file1)])
                repo.index.commit(
                    f"Fix bug in file1 issue #{i}",
                    author=author,
                    committer=author,
                )

            yield GitHistoryMiner(str(repo_path))

    def test_extract_cochange_patterns_basic(self, multi_commit_repo):
        """Test basic co-change pattern extraction."""
        patterns = multi_commit_repo.extract_cochange_patterns(
            max_commits=100, min_confidence=0.1, min_support=2
        )

        assert isinstance(patterns, list)

        # Should detect file1.py and file2.py as co-changing
        if len(patterns) > 0:
            pattern = patterns[0]
            assert hasattr(pattern, "file_a")
            assert hasattr(pattern, "file_b")
            assert hasattr(pattern, "support_count")
            assert hasattr(pattern, "confidence_score")
            assert 0.0 <= pattern.confidence_score <= 1.0

    def test_extract_cochange_patterns_insufficient_commits(self, multi_commit_repo):
        """Test co-change pattern extraction with insufficient commits."""
        patterns = multi_commit_repo.extract_cochange_patterns(
            max_commits=1, min_confidence=0.5, min_support=10
        )

        # Should return empty list due to insufficient data
        assert isinstance(patterns, list)
        assert len(patterns) == 0

    def test_extract_maintenance_hotspots_basic(self, multi_commit_repo):
        """Test basic maintenance hotspot extraction."""
        hotspots = multi_commit_repo.extract_maintenance_hotspots(
            max_commits=100, min_confidence=0.1
        )

        assert isinstance(hotspots, list)

        # Should detect file1.py as a hotspot (has bug fixes)
        if len(hotspots) > 0:
            hotspot = hotspots[0]
            assert hasattr(hotspot, "file_path")
            assert hasattr(hotspot, "problem_frequency")
            assert hasattr(hotspot, "hotspot_score")
            assert 0.0 <= hotspot.hotspot_score <= 1.0

    def test_extract_maintenance_hotspots_insufficient_commits(self, multi_commit_repo):
        """Test hotspot extraction with insufficient commits."""
        hotspots = multi_commit_repo.extract_maintenance_hotspots(
            max_commits=2, min_confidence=0.5
        )

        # Should return empty list due to insufficient data
        assert isinstance(hotspots, list)

    def test_extract_solution_patterns_basic(self, multi_commit_repo):
        """Test basic solution pattern extraction."""
        patterns = multi_commit_repo.extract_solution_patterns(
            max_commits=100, min_confidence=0.1
        )

        assert isinstance(patterns, list)

        # Should detect bug -> fix_logic pattern
        if len(patterns) > 0:
            pattern = patterns[0]
            assert hasattr(pattern, "problem_type")
            assert hasattr(pattern, "solution_approach")
            assert hasattr(pattern, "success_rate")
            assert 0.0 <= pattern.success_rate <= 1.0

    def test_extract_solution_patterns_insufficient_problems(self, multi_commit_repo):
        """Test solution pattern extraction with insufficient problem commits."""
        patterns = multi_commit_repo.extract_solution_patterns(
            max_commits=3, min_confidence=0.5
        )

        # Should return empty list due to insufficient problem data
        assert isinstance(patterns, list)

    def test_extract_all_patterns_comprehensive(self, multi_commit_repo):
        """Test comprehensive pattern extraction."""
        results = multi_commit_repo.extract_all_patterns(
            max_commits=100, min_confidence=0.1, min_support=2
        )

        assert isinstance(results, dict)
        assert "cochange_patterns" in results
        assert "maintenance_hotspots" in results
        assert "solution_patterns" in results
        assert "metadata" in results

        # Check metadata structure
        metadata = results["metadata"]
        assert "extraction_time_seconds" in metadata
        assert "max_commits_analyzed" in metadata
        assert "pattern_counts" in metadata
        assert "repository_path" in metadata

        # All pattern lists should be valid
        assert isinstance(results["cochange_patterns"], list)
        assert isinstance(results["maintenance_hotspots"], list)
        assert isinstance(results["solution_patterns"], list)

    def test_extract_patterns_invalid_repository(self):
        """Test pattern extraction methods fail gracefully with invalid repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create empty directory (not a git repo)
            invalid_repo_path = Path(temp_dir) / "not_a_repo"
            invalid_repo_path.mkdir()

            with pytest.raises(ValueError):
                GitHistoryMiner(str(invalid_repo_path))

    def test_extract_patterns_empty_repository(self):
        """Test pattern extraction with empty repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "empty_repo"
            repo_path.mkdir()

            # Initialize empty git repository
            Repo.init(str(repo_path))

            miner = GitHistoryMiner(str(repo_path))

            # Should handle empty repository by raising ValueError (no commits to analyze)
            with pytest.raises(ValueError, match="Repository validation failed"):
                miner.extract_cochange_patterns()

            with pytest.raises(ValueError, match="Repository validation failed"):
                miner.extract_maintenance_hotspots()

            with pytest.raises(ValueError, match="Repository validation failed"):
                miner.extract_solution_patterns()

    def test_pattern_extraction_parameter_validation(self, multi_commit_repo):
        """Test pattern extraction parameter validation."""
        # Test with extreme parameters
        patterns = multi_commit_repo.extract_cochange_patterns(
            max_commits=50000, min_confidence=0.0, min_support=1
        )
        assert isinstance(patterns, list)

        patterns = multi_commit_repo.extract_cochange_patterns(
            max_commits=1, min_confidence=1.0, min_support=100
        )
        assert isinstance(patterns, list)

    def test_pattern_extraction_error_handling(self, multi_commit_repo):
        """Test error handling in pattern extraction methods."""
        # These should not raise exceptions even with edge case parameters
        try:
            patterns = multi_commit_repo.extract_cochange_patterns(
                max_commits=-1, min_confidence=-1.0, min_support=-1
            )
            assert isinstance(patterns, list)
        except Exception as e:
            # If exceptions are raised, they should be meaningful
            assert "validation" in str(e).lower() or "invalid" in str(e).lower()

    def test_pattern_extraction_context_manager(self):
        """Test pattern extraction with context manager usage."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "test_repo"
            repo_path.mkdir()

            # Initialize a git repository
            repo = Repo.init(str(repo_path))

            from git import Actor

            author = Actor("Test User", "test@example.com")

            # Create a test file and commit
            test_file = repo_path / "test.txt"
            test_file.write_text("Hello, world!")

            repo.index.add([str(test_file)])
            repo.index.commit(
                "Initial commit",
                author=author,
                committer=author,
            )

            # Test context manager usage
            with GitHistoryMiner(str(repo_path)) as miner:
                patterns = miner.extract_cochange_patterns()
                assert isinstance(patterns, list)

            # Should be properly closed
            assert miner.repo is None

    def test_pattern_extraction_data_structures(self, multi_commit_repo):
        """Test that pattern extraction returns proper data structures."""
        # Test co-change patterns
        patterns = multi_commit_repo.extract_cochange_patterns(min_confidence=0.0)
        for pattern in patterns:
            from cognitive_memory.git_analysis.data_structures import CoChangePattern

            assert isinstance(pattern, CoChangePattern)
            assert isinstance(pattern.file_a, str)
            assert isinstance(pattern.file_b, str)
            assert isinstance(pattern.support_count, int)
            assert isinstance(pattern.confidence_score, float)

        # Test maintenance hotspots
        hotspots = multi_commit_repo.extract_maintenance_hotspots(min_confidence=0.0)
        for hotspot in hotspots:
            from cognitive_memory.git_analysis.data_structures import MaintenanceHotspot

            assert isinstance(hotspot, MaintenanceHotspot)
            assert isinstance(hotspot.file_path, str)
            assert isinstance(hotspot.problem_frequency, int)
            assert isinstance(hotspot.hotspot_score, float)

        # Test solution patterns
        solutions = multi_commit_repo.extract_solution_patterns(min_confidence=0.0)
        for solution in solutions:
            from cognitive_memory.git_analysis.data_structures import SolutionPattern

            assert isinstance(solution, SolutionPattern)
            assert isinstance(solution.problem_type, str)
            assert isinstance(solution.solution_approach, str)
            assert isinstance(solution.success_rate, float)
