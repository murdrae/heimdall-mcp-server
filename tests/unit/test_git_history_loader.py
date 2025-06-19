"""
Unit tests for GitHistoryLoader.

Tests the git repository memory loader functionality including pattern extraction,
memory creation, deterministic ID generation, and upsert operations.
"""

import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cognitive_memory.core.config import CognitiveConfig
from cognitive_memory.core.memory import CognitiveMemory
from cognitive_memory.loaders.git_loader import GitHistoryLoader


class TestGitHistoryLoader:
    """Test suite for GitHistoryLoader."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CognitiveConfig()

    @pytest.fixture
    def mock_cognitive_system(self):
        """Create mock cognitive system."""
        mock = MagicMock()
        mock.store_memory.return_value = True
        mock.upsert_memories.return_value = {
            "success": True,
            "updated": 5,
            "inserted": 3,
        }
        return mock

    @pytest.fixture
    def git_loader(self, config, mock_cognitive_system):
        """Create GitHistoryLoader instance."""
        return GitHistoryLoader(config, mock_cognitive_system)

    @pytest.fixture
    def mock_git_repo(self):
        """Create temporary git repository structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            git_dir = repo_path / ".git"
            git_dir.mkdir()
            yield str(repo_path)

    @pytest.fixture
    def sample_patterns(self):
        """Create sample pattern data for testing."""
        return {
            "cochange": [
                {
                    "file_a": "src/utils.py",
                    "file_b": "src/main.py",
                    "support_count": 5,
                    "confidence_score": 0.8,
                    "quality_rating": "high",
                    "recency_weight": 0.9,
                    "statistical_significance": 0.7,
                }
            ],
            "hotspot": [
                {
                    "file_path": "src/buggy.py",
                    "problem_frequency": 10,
                    "hotspot_score": 0.6,
                    "trend_direction": "increasing",
                    "recent_problems": ["bug", "error"],
                    "total_changes": 50,
                }
            ],
            "solution": [
                {
                    "problem_type": "bug",
                    "solution_approach": "validation",
                    "success_rate": 0.9,
                    "applicability_confidence": 0.8,
                    "example_fixes": ["abc123", "def456"],
                    "usage_count": 8,
                }
            ],
        }

    def test_initialization(self, config, mock_cognitive_system):
        """Test GitHistoryLoader initialization."""
        loader = GitHistoryLoader(config, mock_cognitive_system)

        assert loader.config == config
        assert loader.cognitive_system == mock_cognitive_system
        assert loader.pattern_detector is not None
        assert loader.pattern_embedder is not None
        assert loader.id_generator is not None

    def test_get_supported_extensions(self, git_loader):
        """Test supported extensions (should be empty for git repos)."""
        extensions = git_loader.get_supported_extensions()
        assert extensions == []

    def test_validate_source_valid_repo(self, git_loader, mock_git_repo):
        """Test validation of valid git repository."""
        with patch(
            "cognitive_memory.loaders.git_loader.validate_repository_path"
        ) as mock_validate:
            mock_validate.return_value = True

            result = git_loader.validate_source(mock_git_repo)
            assert result is True
            mock_validate.assert_called_once_with(mock_git_repo)

    def test_validate_source_invalid_path(self, git_loader):
        """Test validation of invalid path."""
        result = git_loader.validate_source("/nonexistent/path")
        assert result is False

    def test_validate_source_not_git_repo(self, git_loader):
        """Test validation of directory without .git."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = git_loader.validate_source(temp_dir)
            assert result is False

    @patch("cognitive_memory.loaders.git_loader.GitHistoryMiner")
    @patch(
        "cognitive_memory.loaders.git_loader.GitHistoryLoader._create_cochange_memory"
    )
    @patch(
        "cognitive_memory.loaders.git_loader.GitHistoryLoader._create_hotspot_memory"
    )
    @patch(
        "cognitive_memory.loaders.git_loader.GitHistoryLoader._create_solution_memory"
    )
    def test_load_from_source(
        self,
        mock_create_solution,
        mock_create_hotspot,
        mock_create_cochange,
        mock_history_miner_class,
        git_loader,
        mock_git_repo,
        sample_patterns,
    ):
        """Test loading memories from git repository."""
        # Mock pattern detector methods
        with (
            patch.object(
                git_loader.pattern_detector,
                "detect_cochange_patterns",
                return_value=sample_patterns["cochange"],
            ),
            patch.object(
                git_loader.pattern_detector,
                "detect_maintenance_hotspots",
                return_value=sample_patterns["hotspot"],
            ),
            patch.object(
                git_loader.pattern_detector,
                "detect_solution_patterns",
                return_value=sample_patterns["solution"],
            ),
        ):
            # Mock GitHistoryMiner instance and its methods
            mock_history_miner = MagicMock()
            mock_history_miner_class.return_value = mock_history_miner
            mock_commits = [MagicMock()]
            mock_problem_commits = [MagicMock()]
            mock_history_miner.extract_commit_history.return_value = mock_commits
            mock_history_miner.extract_problem_commits.return_value = (
                mock_problem_commits
            )

            # Mock memory creation
            mock_memories = [
                CognitiveMemory(str(uuid.uuid4()), "content1", 1, 1.0, {}),
                CognitiveMemory(str(uuid.uuid4()), "content2", 1, 1.0, {}),
                CognitiveMemory(str(uuid.uuid4()), "content3", 2, 1.0, {}),
            ]
            mock_create_cochange.return_value = mock_memories[0]
            mock_create_hotspot.return_value = mock_memories[1]
            mock_create_solution.return_value = mock_memories[2]

            with patch.object(git_loader, "validate_source", return_value=True):
                memories = git_loader.load_from_source(mock_git_repo)

            assert len(memories) == 3
            assert all(isinstance(memory, CognitiveMemory) for memory in memories)

            # Verify pattern detection was called (inside context manager while mocks exist)
            git_loader.pattern_detector.detect_cochange_patterns.assert_called_once()
            git_loader.pattern_detector.detect_maintenance_hotspots.assert_called_once()
            git_loader.pattern_detector.detect_solution_patterns.assert_called_once()

    def test_create_cochange_memory(self, git_loader, sample_patterns):
        """Test creation of co-change memory."""
        pattern = sample_patterns["cochange"][0]
        source_path = "/test/repo"

        memory = git_loader._create_cochange_memory(pattern, source_path)

        assert isinstance(memory, CognitiveMemory)
        assert memory.hierarchy_level == 1  # L1 - Context
        assert memory.metadata["pattern_type"] == "cochange"
        assert memory.metadata["source_path"] == source_path
        assert memory.metadata["file_a"] == pattern["file_a"]
        assert memory.metadata["file_b"] == pattern["file_b"]
        assert memory.metadata["loader_type"] == "git"
        assert memory.id.startswith("git::cochange::")

    def test_create_hotspot_memory(self, git_loader, sample_patterns):
        """Test creation of hotspot memory."""
        pattern = sample_patterns["hotspot"][0]
        source_path = "/test/repo"

        memory = git_loader._create_hotspot_memory(pattern, source_path)

        assert isinstance(memory, CognitiveMemory)
        assert memory.hierarchy_level == 1  # L1 - Context
        assert memory.metadata["pattern_type"] == "hotspot"
        assert memory.metadata["source_path"] == source_path
        assert memory.metadata["file_path"] == pattern["file_path"]
        assert memory.metadata["loader_type"] == "git"
        assert memory.id.startswith("git::hotspot::")

    def test_create_solution_memory(self, git_loader, sample_patterns):
        """Test creation of solution memory."""
        pattern = sample_patterns["solution"][0]
        source_path = "/test/repo"

        memory = git_loader._create_solution_memory(pattern, source_path)

        assert isinstance(memory, CognitiveMemory)
        assert memory.hierarchy_level == 2  # L2 - Episode
        assert memory.metadata["pattern_type"] == "solution"
        assert memory.metadata["source_path"] == source_path
        assert memory.metadata["problem_type"] == pattern["problem_type"]
        assert memory.metadata["solution_approach"] == pattern["solution_approach"]
        assert memory.metadata["loader_type"] == "git"
        assert memory.id.startswith("git::solution::")

    def test_upsert_memories_success(self, git_loader, mock_cognitive_system):
        """Test successful upsert operation."""
        memories = [
            CognitiveMemory(str(uuid.uuid4()), "content1", 1, 1.0, {}),
            CognitiveMemory(str(uuid.uuid4()), "content2", 1, 1.0, {}),
        ]

        result = git_loader.upsert_memories(memories)

        assert result is True
        mock_cognitive_system.upsert_memories.assert_called_once_with(memories)

    def test_upsert_memories_no_cognitive_system(self, config):
        """Test upsert without cognitive system."""
        loader = GitHistoryLoader(config, None)
        memories = [CognitiveMemory(str(uuid.uuid4()), "content", 1, 1.0, {})]

        result = loader.upsert_memories(memories)

        assert result is False

    def test_upsert_memories_fallback_to_store(self, git_loader, mock_cognitive_system):
        """Test fallback to store_memory when upsert fails."""
        mock_cognitive_system.upsert_memories.return_value = (
            False  # Not dict, triggers fallback
        )
        memories = [CognitiveMemory(str(uuid.uuid4()), "content", 1, 1.0, {})]

        result = git_loader.upsert_memories(memories)

        assert result is True
        mock_cognitive_system.store_memory.assert_called_once()

    def test_extract_file_connections(self, git_loader):
        """Test extraction of file-based connections."""
        cochange_memory = CognitiveMemory(
            id="cochange1",
            content="content",
            hierarchy_level=1,
            strength=1.0,
            metadata={
                "file_a": "src/utils.py",
                "file_b": "src/main.py",
                "confidence_score": 0.8,
            },
        )
        hotspot_memory = CognitiveMemory(
            id="hotspot1",
            content="content",
            hierarchy_level=1,
            strength=1.0,
            metadata={"file_path": "src/utils.py", "hotspot_score": 0.6},
        )

        connections = git_loader._extract_file_connections(
            [cochange_memory], [hotspot_memory]
        )

        assert len(connections) == 1
        source_id, target_id, strength, conn_type = connections[0]
        assert source_id == "cochange1"
        assert target_id == "hotspot1"
        assert strength == 0.7  # (0.8 + 0.6) / 2
        assert conn_type == "file_relationship"

    def test_extract_problem_solution_connections(self, git_loader):
        """Test extraction of problem-solution connections."""
        hotspot_memory = CognitiveMemory(
            id="hotspot1",
            content="content",
            hierarchy_level=1,
            strength=1.0,
            metadata={"recent_problems": ["bug", "error"], "hotspot_score": 0.6},
        )
        solution_memory = CognitiveMemory(
            id="solution1",
            content="content",
            hierarchy_level=2,
            strength=1.0,
            metadata={"problem_type": "bug", "applicability_confidence": 0.8},
        )

        connections = git_loader._extract_problem_solution_connections(
            [hotspot_memory], [solution_memory]
        )

        assert len(connections) == 1
        source_id, target_id, strength, conn_type = connections[0]
        assert source_id == "hotspot1"
        assert target_id == "solution1"
        assert strength == 0.7  # (0.6 + 0.8) / 2
        assert conn_type == "problem_solution"

    def test_extract_cochange_connections(self, git_loader):
        """Test extraction of co-change overlap connections."""
        memory1 = CognitiveMemory(
            id="cochange1",
            content="content",
            hierarchy_level=1,
            strength=1.0,
            metadata={
                "file_a": "src/utils.py",
                "file_b": "src/main.py",
                "confidence_score": 0.8,
            },
        )
        memory2 = CognitiveMemory(
            id="cochange2",
            content="content",
            hierarchy_level=1,
            strength=1.0,
            metadata={
                "file_a": "src/utils.py",
                "file_b": "src/config.py",
                "confidence_score": 0.6,
            },
        )

        connections = git_loader._extract_cochange_connections([memory1, memory2])

        assert len(connections) == 1
        source_id, target_id, strength, conn_type = connections[0]
        assert source_id == "cochange1"
        assert target_id == "cochange2"
        assert strength == 0.7  # (0.8 + 0.6) / 2
        assert conn_type == "cochange_overlap"

    def test_extract_connections_integration(self, git_loader):
        """Test full connection extraction with mixed memory types."""
        memories = [
            CognitiveMemory(
                id="cochange1",
                content="content",
                hierarchy_level=1,
                strength=1.0,
                metadata={
                    "pattern_type": "cochange",
                    "file_a": "src/utils.py",
                    "file_b": "src/main.py",
                    "confidence_score": 0.8,
                },
            ),
            CognitiveMemory(
                id="hotspot1",
                content="content",
                hierarchy_level=1,
                strength=1.0,
                metadata={
                    "pattern_type": "hotspot",
                    "file_path": "src/utils.py",
                    "hotspot_score": 0.6,
                    "recent_problems": ["bug"],
                },
            ),
            CognitiveMemory(
                id="solution1",
                content="content",
                hierarchy_level=2,
                strength=1.0,
                metadata={
                    "pattern_type": "solution",
                    "problem_type": "bug",
                    "applicability_confidence": 0.9,
                },
            ),
        ]

        connections = git_loader.extract_connections(memories)

        # Should have file connection (cochange -> hotspot) and problem-solution connection
        assert len(connections) >= 2

        # Verify connection types are present
        connection_types = {conn[3] for conn in connections}
        assert "file_relationship" in connection_types
        assert "problem_solution" in connection_types

    def test_deterministic_id_generation(self, git_loader, sample_patterns):
        """Test that IDs are deterministic across multiple calls."""
        pattern = sample_patterns["cochange"][0]
        source_path = "/test/repo"

        memory1 = git_loader._create_cochange_memory(pattern, source_path)
        memory2 = git_loader._create_cochange_memory(pattern, source_path)

        assert memory1.id == memory2.id
        assert memory1.id.startswith("git::cochange::")

    def test_load_from_source_validation_failure(self, git_loader):
        """Test load_from_source with validation failure."""
        with patch.object(git_loader, "validate_source", return_value=False):
            with pytest.raises(ValueError, match="Invalid git repository"):
                git_loader.load_from_source("/invalid/path")

    def test_memory_hierarchy_classification(self, git_loader, sample_patterns):
        """Test proper L0/L1/L2 classification of pattern memories."""
        source_path = "/test/repo"

        # Co-change and hotspot should be L1 (Context)
        cochange_memory = git_loader._create_cochange_memory(
            sample_patterns["cochange"][0], source_path
        )
        hotspot_memory = git_loader._create_hotspot_memory(
            sample_patterns["hotspot"][0], source_path
        )

        # Solution should be L2 (Episode)
        solution_memory = git_loader._create_solution_memory(
            sample_patterns["solution"][0], source_path
        )

        assert cochange_memory.hierarchy_level == 1
        assert hotspot_memory.hierarchy_level == 1
        assert solution_memory.hierarchy_level == 2
