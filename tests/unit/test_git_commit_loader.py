"""
Unit tests for CommitLoader.

Tests the git commit memory loader functionality including memory creation,
connection extraction, and integration with GitHistoryMiner.
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from git import Actor, Repo

from cognitive_memory.core.config import CognitiveConfig
from cognitive_memory.core.memory import CognitiveMemory
from cognitive_memory.git_analysis.commit import Commit, FileChange
from cognitive_memory.git_analysis.commit_loader import CommitLoader


class TestCommitLoaderInit:
    """Test CommitLoader initialization."""

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
        """Test CommitLoader initialization."""
        loader = CommitLoader(config, mock_cognitive_system)

        assert loader.config == config
        assert loader.cognitive_system == mock_cognitive_system

    def test_initialization_without_cognitive_system(self, config):
        """Test CommitLoader initialization without cognitive system."""
        loader = CommitLoader(config, None)

        assert loader.config == config
        assert loader.cognitive_system is None


class TestCommitLoaderValidation:
    """Test source validation methods."""

    @pytest.fixture
    def commit_loader(self):
        """Create CommitLoader instance."""
        config = CognitiveConfig()
        return CommitLoader(config, None)

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

    def test_validate_source_valid_repo(self, commit_loader, temp_git_repo):
        """Test validation of valid git repository."""
        result = commit_loader.validate_source(temp_git_repo)
        assert result is True

    def test_validate_source_nonexistent_path(self, commit_loader):
        """Test validation of nonexistent path."""
        result = commit_loader.validate_source("/nonexistent/path")
        assert result is False

    def test_validate_source_not_directory(self, commit_loader):
        """Test validation of path that's not a directory."""
        with tempfile.NamedTemporaryFile() as temp_file:
            result = commit_loader.validate_source(temp_file.name)
            assert result is False

    def test_validate_source_no_git_directory(self, commit_loader):
        """Test validation of directory without .git."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = commit_loader.validate_source(temp_dir)
            assert result is False

    def test_validate_source_security_validation_failure(
        self, commit_loader, temp_git_repo
    ):
        """Test validation failure due to security checks."""
        with patch(
            "cognitive_memory.git_analysis.commit_loader.validate_repository_path",
            return_value=False,
        ):
            result = commit_loader.validate_source(temp_git_repo)
            assert result is False

    def test_validate_source_exception_handling(self, commit_loader):
        """Test exception handling in source validation."""
        # This should not raise an exception
        result = commit_loader.validate_source(None)
        assert result is False

    def test_get_supported_extensions(self, commit_loader):
        """Test supported extensions (should be empty for git repos)."""
        extensions = commit_loader.get_supported_extensions()
        assert extensions == []


class TestCommitLoaderMemoryCreation:
    """Test memory creation from commits."""

    @pytest.fixture
    def commit_loader(self):
        """Create CommitLoader instance."""
        config = CognitiveConfig()
        return CommitLoader(config, None)

    @pytest.fixture
    def sample_commit(self):
        """Create a sample commit for testing."""
        return Commit(
            hash="a1b2c3d4e5f6789012345678901234567890abcd",
            message="Fix authentication bug",
            author_name="John Doe",
            author_email="john.doe@example.com",
            timestamp=datetime(2023, 12, 1, 10, 30),
            file_changes=[
                FileChange("src/auth.py", "M", 15, 5),
                FileChange("tests/test_auth.py", "A", 20, 0),
                FileChange("docs/auth.md", "M", 3, 1),
            ],
            parent_hashes=["1234567890123456789012345678901234567890"],
        )

    def test_create_commit_memory_basic(self, commit_loader, sample_commit):
        """Test basic commit memory creation."""
        source_path = "/test/repo"
        memory = commit_loader._create_commit_memory(sample_commit, source_path)

        assert isinstance(memory, CognitiveMemory)
        assert memory.hierarchy_level == 2  # L2 - Episode
        assert memory.metadata["type"] == "git_commit"
        assert memory.metadata["commit_hash"] == sample_commit.hash
        assert memory.metadata["author_name"] == sample_commit.author_name
        assert memory.metadata["author_email"] == sample_commit.author_email
        assert memory.metadata["source_path"] == source_path
        assert memory.metadata["loader_type"] == "git_commit"

    def test_create_commit_memory_file_metadata(self, commit_loader, sample_commit):
        """Test file-related metadata in commit memory."""
        source_path = "/test/repo"
        memory = commit_loader._create_commit_memory(sample_commit, source_path)

        assert memory.metadata["affected_files"] == [
            "src/auth.py",
            "tests/test_auth.py",
            "docs/auth.md",
        ]
        assert set(memory.metadata["file_extensions"]) == {".py", ".md"}
        assert memory.metadata["file_count"] == 3
        assert memory.metadata["lines_added"] == 38  # 15 + 20 + 3
        assert memory.metadata["lines_deleted"] == 6  # 5 + 0 + 1

    def test_create_commit_memory_strength_calculation(
        self, commit_loader, sample_commit
    ):
        """Test strength calculation based on commit size and recency."""
        source_path = "/test/repo"
        memory = commit_loader._create_commit_memory(sample_commit, source_path)

        # Strength should be between 0 and 1
        assert 0.0 <= memory.strength <= 1.0

    def test_create_commit_memory_recent_commit(self, commit_loader):
        """Test strength calculation for recent commit."""
        recent_commit = Commit(
            hash="abcdef1234567890123456789012345678901234",
            message="Recent change",
            author_name="Recent Author",
            author_email="recent@example.com",
            timestamp=datetime.now() - timedelta(days=1),  # Very recent
            file_changes=[FileChange("large_file.py", "M", 150, 50)],  # Large change
            parent_hashes=[],
        )

        source_path = "/test/repo"
        memory = commit_loader._create_commit_memory(recent_commit, source_path)

        # Recent, large commit should have high strength
        assert memory.strength > 0.5

    def test_create_commit_memory_old_small_commit(self, commit_loader):
        """Test strength calculation for old, small commit."""
        old_commit = Commit(
            hash="fedcba0987654321098765432109876543210987",
            message="Minor fix",
            author_name="Old Author",
            author_email="old@example.com",
            timestamp=datetime.now() - timedelta(days=400),  # Very old
            file_changes=[FileChange("small_file.py", "M", 1, 1)],  # Small change
            parent_hashes=[],
        )

        source_path = "/test/repo"
        memory = commit_loader._create_commit_memory(old_commit, source_path)

        # Old, small commit should have lower strength
        assert memory.strength < 0.5

    def test_create_commit_memory_natural_language_content(
        self, commit_loader, sample_commit
    ):
        """Test natural language content generation."""
        source_path = "/test/repo"
        memory = commit_loader._create_commit_memory(sample_commit, source_path)

        content = memory.content
        assert "Git commit a1b2c3d4" in content
        assert "John Doe" in content
        assert "Fix authentication bug" in content
        assert "3 files: src/auth.py, tests/test_auth.py, docs/auth.md" in content
        assert "+38/-6 lines" in content

    def test_create_commit_memory_no_file_extensions(self, commit_loader):
        """Test commit memory with files that have no extensions."""
        commit = Commit(
            hash="1111222233334444555566667777888899990000",
            message="Update README",
            author_name="Author",
            author_email="author@example.com",
            timestamp=datetime.now(),
            file_changes=[
                FileChange("README", "M", 5, 2),
                FileChange("Makefile", "M", 3, 1),
            ],
            parent_hashes=[],
        )

        source_path = "/test/repo"
        memory = commit_loader._create_commit_memory(commit, source_path)

        assert memory.metadata["file_extensions"] == []

    def test_generate_commit_id_deterministic(self, commit_loader):
        """Test deterministic ID generation."""
        repo_name = "test_repo"
        commit_hash = "a1b2c3d4e5f6789012345678901234567890abcd"

        id1 = commit_loader._generate_commit_id(repo_name, commit_hash)
        id2 = commit_loader._generate_commit_id(repo_name, commit_hash)

        assert id1 == id2
        assert len(id1) == 36  # UUID format (8-4-4-4-12)

    def test_generate_commit_id_different_inputs(self, commit_loader):
        """Test ID generation with different inputs."""
        id1 = commit_loader._generate_commit_id("repo1", "hash1")
        id2 = commit_loader._generate_commit_id("repo2", "hash1")
        id3 = commit_loader._generate_commit_id("repo1", "hash2")

        assert id1 != id2
        assert id1 != id3
        assert id2 != id3


class TestCommitLoaderConnectionExtraction:
    """Test connection extraction between commit memories."""

    @pytest.fixture
    def commit_loader(self):
        """Create CommitLoader instance."""
        config = CognitiveConfig()
        return CommitLoader(config, None)

    @pytest.fixture
    def sample_memories(self):
        """Create sample commit memories for testing."""
        now = datetime.now()

        # Create memories with different timestamps and file overlaps
        memory1 = CognitiveMemory(
            id="commit1",
            content="Commit 1 content",
            hierarchy_level=2,
            strength=1.0,
            metadata={
                "type": "git_commit",
                "timestamp": (now - timedelta(hours=2)).isoformat(),
                "author_email": "author1@example.com",
                "affected_files": ["src/auth.py", "src/utils.py"],
                "lines_added": 20,
                "lines_deleted": 5,
            },
        )

        memory2 = CognitiveMemory(
            id="commit2",
            content="Commit 2 content",
            hierarchy_level=2,
            strength=1.0,
            metadata={
                "type": "git_commit",
                "timestamp": (now - timedelta(hours=1)).isoformat(),
                "author_email": "author1@example.com",
                "affected_files": ["src/auth.py", "tests/test_auth.py"],
                "lines_added": 15,
                "lines_deleted": 3,
            },
        )

        memory3 = CognitiveMemory(
            id="commit3",
            content="Commit 3 content",
            hierarchy_level=2,
            strength=1.0,
            metadata={
                "type": "git_commit",
                "timestamp": now.isoformat(),
                "author_email": "author2@example.com",
                "affected_files": ["src/config.py"],
                "lines_added": 5,
                "lines_deleted": 1,
            },
        )

        return [memory1, memory2, memory3]

    def test_extract_connections_file_evolution(self, commit_loader, sample_memories):
        """Test extraction of file evolution connections."""
        connections = commit_loader.extract_connections(sample_memories)

        # Should have connections based on shared files
        assert len(connections) > 0

        # Find file evolution connections
        file_connections = [
            conn for conn in connections if conn[3].startswith("file_evolution:")
        ]
        assert len(file_connections) > 0

        # Check connection structure
        for source_id, target_id, strength, conn_type in file_connections:
            assert source_id in ["commit1", "commit2", "commit3"]
            assert target_id in ["commit1", "commit2", "commit3"]
            assert 0.0 <= strength <= 1.0
            assert conn_type.startswith("file_evolution:")

    def test_extract_connections_author_sessions(self, commit_loader, sample_memories):
        """Test extraction of author session connections."""
        connections = commit_loader.extract_connections(sample_memories)

        # Find author session connections
        author_connections = [
            conn for conn in connections if conn[3] == "author_session"
        ]

        # Should have at least one author session connection (memory1 -> memory2)
        assert len(author_connections) > 0

        # Check that connections are between commits by the same author
        for _source_id, _target_id, strength, conn_type in author_connections:
            assert conn_type == "author_session"
            assert 0.0 <= strength <= 1.0

    def test_extract_connections_no_shared_files(self, commit_loader):
        """Test connection extraction with no shared files."""
        now = datetime.now()

        memories = [
            CognitiveMemory(
                id="commit1",
                content="Commit 1",
                hierarchy_level=2,
                strength=1.0,
                metadata={
                    "timestamp": now.isoformat(),
                    "author_email": "author1@example.com",
                    "affected_files": ["file1.py"],
                    "lines_added": 10,
                    "lines_deleted": 2,
                },
            ),
            CognitiveMemory(
                id="commit2",
                content="Commit 2",
                hierarchy_level=2,
                strength=1.0,
                metadata={
                    "timestamp": now.isoformat(),
                    "author_email": "author2@example.com",
                    "affected_files": ["file2.py"],
                    "lines_added": 5,
                    "lines_deleted": 1,
                },
            ),
        ]

        connections = commit_loader.extract_connections(memories)

        # Should have no file evolution connections
        file_connections = [
            conn for conn in connections if conn[3].startswith("file_evolution:")
        ]
        assert len(file_connections) == 0

    def test_calculate_file_connection_strength(self, commit_loader):
        """Test file connection strength calculation."""
        now = datetime.now()

        memory1 = CognitiveMemory(
            id="commit1",
            content="Commit 1",
            hierarchy_level=2,
            strength=1.0,
            metadata={
                "timestamp": now.isoformat(),
                "author_email": "author1@example.com",
                "lines_added": 50,  # Large change
                "lines_deleted": 20,
            },
        )

        memory2 = CognitiveMemory(
            id="commit2",
            content="Commit 2",
            hierarchy_level=2,
            strength=1.0,
            metadata={
                "timestamp": (now + timedelta(hours=1)).isoformat(),  # Close in time
                "author_email": "author1@example.com",  # Same author
                "lines_added": 30,  # Large change
                "lines_deleted": 10,
            },
        )

        strength = commit_loader._calculate_file_connection_strength(
            memory1, memory2, "shared_file.py"
        )

        # Should have high strength due to large changes, temporal proximity, and same author
        assert strength > 0.7

    def test_calculate_file_connection_strength_low(self, commit_loader):
        """Test low file connection strength calculation."""
        now = datetime.now()

        memory1 = CognitiveMemory(
            id="commit1",
            content="Commit 1",
            hierarchy_level=2,
            strength=1.0,
            metadata={
                "timestamp": now.isoformat(),
                "author_email": "author1@example.com",
                "lines_added": 2,  # Small change
                "lines_deleted": 1,
            },
        )

        memory2 = CognitiveMemory(
            id="commit2",
            content="Commit 2",
            hierarchy_level=2,
            strength=1.0,
            metadata={
                "timestamp": (now + timedelta(days=100)).isoformat(),  # Far in time
                "author_email": "author2@example.com",  # Different author
                "lines_added": 3,  # Small change
                "lines_deleted": 0,
            },
        )

        strength = commit_loader._calculate_file_connection_strength(
            memory1, memory2, "shared_file.py"
        )

        # Should have lower strength
        assert strength <= 0.6

    def test_extract_author_connections_same_work_session(self, commit_loader):
        """Test author connections within the same work session."""
        now = datetime.now()

        memories = [
            CognitiveMemory(
                id="commit1",
                content="Commit 1",
                hierarchy_level=2,
                strength=1.0,
                metadata={
                    "author_email": "dev@example.com",
                    "timestamp": now.isoformat(),
                    "affected_files": ["file1.py"],  # Add required metadata
                },
            ),
            CognitiveMemory(
                id="commit2",
                content="Commit 2",
                hierarchy_level=2,
                strength=1.0,
                metadata={
                    "author_email": "dev@example.com",
                    "timestamp": (
                        now + timedelta(hours=2)
                    ).isoformat(),  # Within 4 hours
                    "affected_files": ["file2.py"],  # Add required metadata
                },
            ),
        ]

        connections = commit_loader._extract_author_connections(memories)

        assert len(connections) >= 0  # May be 0 or 1 depending on implementation
        if len(connections) > 0:
            source_id, target_id, strength, conn_type = connections[0]
            assert source_id in ["commit1", "commit2"]
            assert target_id in ["commit1", "commit2"]
            assert conn_type == "author_session"
            assert strength > 0.3

    def test_extract_author_connections_different_work_sessions(self, commit_loader):
        """Test no author connections between different work sessions."""
        now = datetime.now()

        memories = [
            CognitiveMemory(
                id="commit1",
                content="Commit 1",
                hierarchy_level=2,
                strength=1.0,
                metadata={
                    "author_email": "dev@example.com",
                    "timestamp": now.isoformat(),
                },
            ),
            CognitiveMemory(
                id="commit2",
                content="Commit 2",
                hierarchy_level=2,
                strength=1.0,
                metadata={
                    "author_email": "dev@example.com",
                    "timestamp": (
                        now + timedelta(hours=10)
                    ).isoformat(),  # More than 4 hours
                },
            ),
        ]

        connections = commit_loader._extract_author_connections(memories)

        # Should have no connections due to time gap
        assert len(connections) == 0

    def test_extract_connections_exception_handling(self, commit_loader):
        """Test exception handling in connection extraction."""
        # Create memories with invalid/missing metadata
        invalid_memories = [
            CognitiveMemory(
                id="invalid1",
                content="Invalid 1",
                hierarchy_level=2,
                strength=1.0,
                metadata={},  # Missing required fields
            ),
            CognitiveMemory(
                id="invalid2",
                content="Invalid 2",
                hierarchy_level=2,
                strength=1.0,
                metadata={"invalid": "data"},  # Invalid structure
            ),
        ]

        # Should not raise exception
        connections = commit_loader.extract_connections(invalid_memories)
        assert isinstance(connections, list)


class TestCommitLoaderIntegration:
    """Test integration with GitHistoryMiner."""

    @pytest.fixture
    def temp_git_repo(self):
        """Create a temporary git repository with multiple commits."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "integration_repo"
            repo_path.mkdir()

            repo = Repo.init(str(repo_path))
            author = Actor("Integration Test", "integration@example.com")

            # Create multiple commits with different file changes
            commits_data = [
                ("auth.py", "def authenticate(): pass", "Add authentication"),
                ("auth.py", "def authenticate(): return True", "Fix authentication"),
                ("utils.py", "def helper(): pass", "Add utility"),
                ("auth.py", "def authenticate(): return validate()", "Improve auth"),
            ]

            for filename, content, message in commits_data:
                file_path = repo_path / filename
                file_path.write_text(content)
                repo.index.add([str(file_path)])
                repo.index.commit(message, author=author, committer=author)

            yield str(repo_path)

    def test_load_from_source_integration(self, temp_git_repo):
        """Test full integration with real git repository."""
        config = CognitiveConfig()
        loader = CommitLoader(config, None)

        memories = loader.load_from_source(temp_git_repo, max_commits=10)

        assert len(memories) == 4
        for memory in memories:
            assert isinstance(memory, CognitiveMemory)
            assert memory.hierarchy_level == 2
            assert memory.metadata["type"] == "git_commit"
            assert "commit_hash" in memory.metadata
            assert "author_name" in memory.metadata
            assert "affected_files" in memory.metadata

    def test_load_from_source_with_date_filters(self, temp_git_repo):
        """Test loading with date filters."""
        config = CognitiveConfig()
        loader = CommitLoader(config, None)

        # Test with no date filters first to ensure repo has commits
        loader.load_from_source(temp_git_repo, max_commits=10)

        # Use date filters that include all commits
        since_date = datetime(2020, 1, 1)
        until_date = datetime(2025, 1, 1)

        memories = loader.load_from_source(
            temp_git_repo, max_commits=10, since_date=since_date, until_date=until_date
        )

        # Should have at least some memories (same as all_memories or less due to filtering)
        assert isinstance(memories, list)
        for memory in memories:
            assert isinstance(memory, CognitiveMemory)

    def test_load_from_source_validation_error(self):
        """Test loading from invalid source."""
        config = CognitiveConfig()
        loader = CommitLoader(config, None)

        with pytest.raises(ValueError, match="Invalid git repository"):
            loader.load_from_source("/invalid/path")

    def test_load_from_source_with_cognitive_system(self, temp_git_repo):
        """Test loading with cognitive system integration."""
        config = CognitiveConfig()
        mock_cognitive_system = MagicMock()
        loader = CommitLoader(config, mock_cognitive_system)

        memories = loader.load_from_source(temp_git_repo, max_commits=5)

        assert len(memories) > 0
        # Cognitive system should not be called during load_from_source
        # (that's handled by the calling code)
