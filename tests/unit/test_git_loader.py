"""
Unit tests for GitHistoryLoader.

Tests the git repository memory loader that integrates CommitLoader
for storing git commits as cognitive memories.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from git import Actor, Repo

from cognitive_memory.core.config import CognitiveConfig
from cognitive_memory.core.memory import CognitiveMemory
from cognitive_memory.loaders.git_loader import GitHistoryLoader


class TestGitHistoryLoaderInit:
    """Test GitHistoryLoader initialization."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CognitiveConfig()

    @pytest.fixture
    def mock_cognitive_system(self):
        """Create mock cognitive system."""
        mock = MagicMock()
        mock.store_memory.return_value = True
        return mock

    def test_initialization(self, config, mock_cognitive_system):
        """Test GitHistoryLoader initialization."""
        loader = GitHistoryLoader(config, mock_cognitive_system)

        assert loader.config == config
        assert loader.cognitive_system == mock_cognitive_system
        assert loader.commit_loader is not None

    def test_initialization_without_cognitive_system(self, config):
        """Test GitHistoryLoader initialization without cognitive system."""
        loader = GitHistoryLoader(config, None)

        assert loader.config == config
        assert loader.cognitive_system is None
        assert loader.commit_loader is not None


class TestGitHistoryLoaderValidation:
    """Test source validation methods."""

    @pytest.fixture
    def git_loader(self):
        """Create GitHistoryLoader instance."""
        config = CognitiveConfig()
        return GitHistoryLoader(config, None)

    @pytest.fixture
    def temp_git_repo(self):
        """Create a temporary git repository for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "test_repo"
            repo_path.mkdir()

            repo = Repo.init(str(repo_path))
            test_file = repo_path / "test.txt"
            test_file.write_text("Hello, world!")

            repo.index.add([str(test_file)])
            author = Actor("Test User", "test@example.com")
            repo.index.commit("Initial commit", author=author, committer=author)

            yield str(repo_path)

    def test_validate_source_valid_repo(self, git_loader, temp_git_repo):
        """Test validation of valid git repository."""
        result = git_loader.validate_source(temp_git_repo)
        assert result is True

    def test_validate_source_invalid_path(self, git_loader):
        """Test validation of invalid path."""
        result = git_loader.validate_source("/nonexistent/path")
        assert result is False

    def test_validate_source_not_git_repo(self, git_loader):
        """Test validation of directory without .git."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = git_loader.validate_source(temp_dir)
            assert result is False

    def test_validate_source_delegates_to_commit_loader(
        self, git_loader, temp_git_repo
    ):
        """Test that validation is delegated to commit loader."""
        with patch.object(
            git_loader.commit_loader, "validate_source", return_value=True
        ) as mock_validate:
            result = git_loader.validate_source(temp_git_repo)

            assert result is True
            mock_validate.assert_called_once_with(temp_git_repo)

    def test_get_supported_extensions(self, git_loader):
        """Test supported extensions (should be empty for git repos)."""
        extensions = git_loader.get_supported_extensions()
        assert extensions == []

    def test_get_supported_extensions_delegates_to_commit_loader(self, git_loader):
        """Test that get_supported_extensions is delegated to commit loader."""
        with patch.object(
            git_loader.commit_loader, "get_supported_extensions", return_value=[]
        ) as mock_extensions:
            extensions = git_loader.get_supported_extensions()

            assert extensions == []
            mock_extensions.assert_called_once()


class TestGitHistoryLoaderMemoryLoading:
    """Test memory loading functionality."""

    @pytest.fixture
    def git_loader(self):
        """Create GitHistoryLoader instance."""
        config = CognitiveConfig()
        return GitHistoryLoader(config, None)

    @pytest.fixture
    def temp_git_repo(self):
        """Create a temporary git repository with multiple commits."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "loader_repo"
            repo_path.mkdir()

            repo = Repo.init(str(repo_path))
            author = Actor("Loader Test", "loader@example.com")

            # Create multiple commits
            commits_data = [
                ("main.py", "print('hello')", "Initial commit"),
                ("utils.py", "def helper(): pass", "Add utility"),
                ("main.py", "print('hello world')", "Update main"),
                ("test.py", "import unittest", "Add tests"),
            ]

            for filename, content, message in commits_data:
                file_path = repo_path / filename
                file_path.write_text(content)
                repo.index.add([str(file_path)])
                repo.index.commit(message, author=author, committer=author)

            yield str(repo_path)

    def test_load_from_source_basic(self, git_loader, temp_git_repo):
        """Test basic memory loading from git repository."""
        memories = git_loader.load_from_source(temp_git_repo)

        assert len(memories) == 4  # Number of commits
        for memory in memories:
            assert isinstance(memory, CognitiveMemory)
            assert memory.hierarchy_level == 2  # L2 - Episode
            assert memory.metadata["type"] == "git_commit"
            assert "commit_hash" in memory.metadata
            assert "author_name" in memory.metadata

    def test_load_from_source_with_max_commits(self, git_loader, temp_git_repo):
        """Test loading with max_commits parameter."""
        memories = git_loader.load_from_source(temp_git_repo, max_commits=2)

        assert len(memories) == 2
        for memory in memories:
            assert isinstance(memory, CognitiveMemory)

    def test_load_from_source_with_date_filters(self, git_loader, temp_git_repo):
        """Test loading with date filter parameters."""
        from datetime import datetime

        # Test without date filters first
        git_loader.load_from_source(temp_git_repo)

        since_date = datetime(2020, 1, 1)
        until_date = datetime(2025, 1, 1)

        memories = git_loader.load_from_source(
            temp_git_repo, since_date=since_date, until_date=until_date
        )

        # Should return a list (may be empty due to date filtering)
        assert isinstance(memories, list)
        for memory in memories:
            assert isinstance(memory, CognitiveMemory)

    def test_load_from_source_with_branch(self, git_loader, temp_git_repo):
        """Test loading with branch parameter."""
        memories = git_loader.load_from_source(temp_git_repo, branch="master")

        assert len(memories) > 0
        for memory in memories:
            assert isinstance(memory, CognitiveMemory)

    def test_load_from_source_delegates_to_commit_loader(
        self, git_loader, temp_git_repo
    ):
        """Test that load_from_source delegates to commit loader."""
        mock_memories = [
            CognitiveMemory("id1", "content1", 2, 1.0, {}),
            CognitiveMemory("id2", "content2", 2, 1.0, {}),
        ]

        with patch.object(
            git_loader.commit_loader, "load_from_source", return_value=mock_memories
        ) as mock_load:
            memories = git_loader.load_from_source(temp_git_repo, max_commits=10)

            assert memories == mock_memories
            mock_load.assert_called_once_with(temp_git_repo, max_commits=10)

    def test_load_from_source_passes_kwargs(self, git_loader, temp_git_repo):
        """Test that all kwargs are passed to commit loader."""
        from datetime import datetime

        kwargs = {
            "max_commits": 5,
            "since_date": datetime(2020, 1, 1),
            "until_date": datetime(2025, 1, 1),
            "branch": "main",
        }

        with patch.object(
            git_loader.commit_loader, "load_from_source", return_value=[]
        ) as mock_load:
            git_loader.load_from_source(temp_git_repo, **kwargs)

            mock_load.assert_called_once_with(temp_git_repo, **kwargs)


class TestGitHistoryLoaderConnectionExtraction:
    """Test connection extraction functionality."""

    @pytest.fixture
    def git_loader(self):
        """Create GitHistoryLoader instance."""
        config = CognitiveConfig()
        return GitHistoryLoader(config, None)

    @pytest.fixture
    def sample_memories(self):
        """Create sample commit memories for testing."""
        from datetime import datetime, timedelta

        now = datetime.now()

        return [
            CognitiveMemory(
                id="commit1",
                content="First commit",
                hierarchy_level=2,
                strength=1.0,
                metadata={
                    "type": "git_commit",
                    "timestamp": (now - timedelta(hours=2)).isoformat(),
                    "author_email": "dev@example.com",
                    "affected_files": ["src/main.py", "src/utils.py"],
                    "lines_added": 50,
                    "lines_deleted": 10,
                },
            ),
            CognitiveMemory(
                id="commit2",
                content="Second commit",
                hierarchy_level=2,
                strength=1.0,
                metadata={
                    "type": "git_commit",
                    "timestamp": (now - timedelta(hours=1)).isoformat(),
                    "author_email": "dev@example.com",
                    "affected_files": ["src/main.py", "tests/test_main.py"],
                    "lines_added": 30,
                    "lines_deleted": 5,
                },
            ),
            CognitiveMemory(
                id="commit3",
                content="Third commit",
                hierarchy_level=2,
                strength=1.0,
                metadata={
                    "type": "git_commit",
                    "timestamp": now.isoformat(),
                    "author_email": "other@example.com",
                    "affected_files": ["src/config.py"],
                    "lines_added": 10,
                    "lines_deleted": 2,
                },
            ),
        ]

    def test_extract_connections_basic(self, git_loader, sample_memories):
        """Test basic connection extraction."""
        connections = git_loader.extract_connections(sample_memories)

        assert isinstance(connections, list)
        assert len(connections) > 0

        # Check connection structure
        for source_id, target_id, strength, conn_type in connections:
            assert isinstance(source_id, str)
            assert isinstance(target_id, str)
            assert isinstance(strength, float)
            assert isinstance(conn_type, str)
            assert 0.0 <= strength <= 1.0

    def test_extract_connections_file_evolution(self, git_loader, sample_memories):
        """Test file evolution connections."""
        connections = git_loader.extract_connections(sample_memories)

        # Should have file evolution connections for src/main.py
        file_connections = [
            conn for conn in connections if conn[3].startswith("file_evolution:")
        ]
        assert len(file_connections) > 0

        # Find connection for src/main.py
        main_py_connections = [
            conn for conn in file_connections if "src/main.py" in conn[3]
        ]
        assert len(main_py_connections) > 0

    def test_extract_connections_author_sessions(self, git_loader, sample_memories):
        """Test author session connections."""
        connections = git_loader.extract_connections(sample_memories)

        # Should have author session connections between commit1 and commit2 (same author)
        author_connections = [
            conn for conn in connections if conn[3] == "author_session"
        ]
        assert len(author_connections) > 0

    def test_extract_connections_delegates_to_commit_loader(
        self, git_loader, sample_memories
    ):
        """Test that extract_connections delegates to commit loader."""
        mock_connections = [
            ("id1", "id2", 0.8, "file_evolution:test.py"),
            ("id2", "id3", 0.6, "author_session"),
        ]

        with patch.object(
            git_loader.commit_loader,
            "extract_connections",
            return_value=mock_connections,
        ) as mock_extract:
            connections = git_loader.extract_connections(sample_memories)

            assert connections == mock_connections
            mock_extract.assert_called_once_with(sample_memories)

    def test_extract_connections_empty_memories(self, git_loader):
        """Test connection extraction with empty memories list."""
        connections = git_loader.extract_connections([])

        assert isinstance(connections, list)
        assert len(connections) == 0

    def test_extract_connections_single_memory(self, git_loader):
        """Test connection extraction with single memory."""
        single_memory = [
            CognitiveMemory(
                id="only_commit",
                content="Only commit",
                hierarchy_level=2,
                strength=1.0,
                metadata={
                    "type": "git_commit",
                    "affected_files": ["solo.py"],
                },
            )
        ]

        connections = git_loader.extract_connections(single_memory)

        assert isinstance(connections, list)
        # Should have no connections with only one memory
        assert len(connections) == 0


class TestGitHistoryLoaderIntegration:
    """Test full integration scenarios."""

    @pytest.fixture
    def temp_git_repo_with_patterns(self):
        """Create a git repository with patterns for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "pattern_repo"
            repo_path.mkdir()

            repo = Repo.init(str(repo_path))
            author = Actor("Pattern Test", "pattern@example.com")

            # Create commits that will have interesting patterns
            commits_data = [
                # Initial setup
                ("auth.py", "class Auth: pass", "Add authentication module"),
                ("user.py", "class User: pass", "Add user module"),
                # Co-change pattern: auth.py and user.py often change together
                (
                    "auth.py",
                    "class Auth:\n    def login(self): pass",
                    "Add login method",
                ),
                (
                    "user.py",
                    "class User:\n    def __init__(self): pass",
                    "Add user constructor",
                ),
                # Same author, same session
                (
                    "auth.py",
                    "class Auth:\n    def login(self): pass\n    def logout(self): pass",
                    "Add logout",
                ),
                (
                    "user.py",
                    "class User:\n    def __init__(self): pass\n    def save(self): pass",
                    "Add save method",
                ),
                # Different file
                ("config.py", "DEBUG = True", "Add config"),
            ]

            for filename, content, message in commits_data:
                file_path = repo_path / filename
                file_path.write_text(content)
                repo.index.add([str(file_path)])
                repo.index.commit(message, author=author, committer=author)

            yield str(repo_path)

    def test_full_integration_load_and_connect(self, temp_git_repo_with_patterns):
        """Test full integration: load memories and extract connections."""
        config = CognitiveConfig()
        loader = GitHistoryLoader(config, None)

        # Load memories
        memories = loader.load_from_source(temp_git_repo_with_patterns)

        assert len(memories) == 7  # Number of commits

        # Extract connections
        connections = loader.extract_connections(memories)

        assert len(connections) > 0

        # Should have both file evolution and author session connections
        connection_types = {conn[3] for conn in connections}
        assert any(
            conn_type.startswith("file_evolution:") for conn_type in connection_types
        )
        assert "author_session" in connection_types

    def test_integration_with_cognitive_system(self, temp_git_repo_with_patterns):
        """Test integration with cognitive system."""
        config = CognitiveConfig()
        mock_cognitive_system = MagicMock()
        loader = GitHistoryLoader(config, mock_cognitive_system)

        memories = loader.load_from_source(temp_git_repo_with_patterns)

        # Loader should create memories but not automatically store them
        assert len(memories) > 0
        for memory in memories:
            assert isinstance(memory, CognitiveMemory)
            # Memories are created independently, not linked to cognitive system during creation

    def test_integration_error_handling(self):
        """Test error handling in integration scenarios."""
        config = CognitiveConfig()
        loader = GitHistoryLoader(config, None)

        # Test with invalid repository
        with pytest.raises(ValueError):
            loader.load_from_source("/totally/invalid/path")

    def test_integration_memory_metadata_consistency(self, temp_git_repo_with_patterns):
        """Test that all loaded memories have consistent metadata."""
        config = CognitiveConfig()
        loader = GitHistoryLoader(config, None)

        memories = loader.load_from_source(temp_git_repo_with_patterns)

        required_metadata_fields = [
            "type",
            "commit_hash",
            "author_name",
            "author_email",
            "timestamp",
            "affected_files",
            "loader_type",
        ]

        for memory in memories:
            for field in required_metadata_fields:
                assert field in memory.metadata, (
                    f"Missing field {field} in memory {memory.id}"
                )

            # Check specific values
            assert memory.metadata["type"] == "git_commit"
            assert memory.metadata["loader_type"] == "git_commit"
            assert isinstance(memory.metadata["affected_files"], list)
            assert len(memory.metadata["commit_hash"]) in [40, 64]  # SHA-1 or SHA-256

    def test_integration_deterministic_ids(self, temp_git_repo_with_patterns):
        """Test that memory IDs are deterministic across multiple loads."""
        config = CognitiveConfig()
        loader1 = GitHistoryLoader(config, None)
        loader2 = GitHistoryLoader(config, None)

        memories1 = loader1.load_from_source(temp_git_repo_with_patterns)
        memories2 = loader2.load_from_source(temp_git_repo_with_patterns)

        assert len(memories1) == len(memories2)

        # Sort by ID for comparison
        memories1.sort(key=lambda m: m.id)
        memories2.sort(key=lambda m: m.id)

        for m1, m2 in zip(memories1, memories2, strict=False):
            assert m1.id == m2.id
            assert m1.metadata["commit_hash"] == m2.metadata["commit_hash"]
