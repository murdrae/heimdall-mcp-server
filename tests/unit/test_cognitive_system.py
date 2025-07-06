"""
Tests for the cognitive system coordinator.

This module tests the CognitiveMemorySystem implementation to ensure
proper coordination between subsystems through abstract interfaces.
"""

from unittest.mock import Mock, patch

import numpy as np
import pytest

from cognitive_memory.core.cognitive_system import CognitiveMemorySystem
from cognitive_memory.core.config import SystemConfig
from cognitive_memory.core.interfaces import (
    ActivationEngine,
    ConnectionGraph,
    EmbeddingProvider,
    MemoryStorage,
    VectorStorage,
)
from cognitive_memory.core.memory import ActivationResult, CognitiveMemory
from tests.factory_utils import (
    MockEmbeddingProvider,
    MockMemoryStorage,
    MockVectorStorage,
    create_partial_mock_system,
)


def create_fully_mocked_system(config: SystemConfig) -> CognitiveMemorySystem:
    """Create a CognitiveMemorySystem with all mock components."""
    components = create_partial_mock_system()
    return CognitiveMemorySystem(
        embedding_provider=components["embedding_provider"],
        vector_storage=components["vector_storage"],
        memory_storage=components["memory_storage"],
        connection_graph=components["connection_graph"],
        activation_engine=components["activation_engine"],
        config=config,
    )


@pytest.fixture
def mock_embedding_provider():
    """Create mock embedding provider."""
    mock = Mock(spec=EmbeddingProvider)
    mock.encode.return_value = np.random.randn(512)
    mock.encode_batch.return_value = np.random.randn(3, 512)
    return mock


@pytest.fixture
def mock_vector_storage():
    """Create mock vector storage."""
    mock = Mock(spec=VectorStorage)
    mock.store_vector.return_value = None
    mock.search_similar.return_value = []
    mock.delete_vector.return_value = True
    mock.update_vector.return_value = True
    return mock


@pytest.fixture
def mock_memory_storage():
    """Create mock memory storage."""
    mock = Mock(spec=MemoryStorage)
    mock.store_memory.return_value = True
    mock.retrieve_memory.return_value = None
    mock.update_memory.return_value = True
    mock.delete_memory.return_value = True
    mock.get_memories_by_level.return_value = []
    return mock


@pytest.fixture
def mock_connection_graph():
    """Create mock connection graph."""
    mock = Mock(spec=ConnectionGraph)
    mock.add_connection.return_value = True
    mock.get_connections.return_value = []
    mock.update_connection_strength.return_value = True
    mock.remove_connection.return_value = True
    return mock


@pytest.fixture
def mock_activation_engine():
    """Create mock activation engine."""
    mock = Mock(spec=ActivationEngine)

    # Create sample activation result with fixed timestamp
    from datetime import datetime

    fixed_timestamp = datetime(2024, 1, 1, 12, 0, 0)
    sample_memory = CognitiveMemory(
        id="test-memory-1",
        content="Sample memory content",
        memory_type="episodic",
        hierarchy_level=2,
        dimensions={},
        timestamp=fixed_timestamp,
        strength=0.8,
        access_count=1,
    )

    activation_result = ActivationResult(
        core_memories=[sample_memory],
        peripheral_memories=[],
        activation_strengths={"test-memory-1": 0.8},
        total_activated=1,
    )

    mock.activate_memories.return_value = activation_result
    return mock


@pytest.fixture
def factory_cognitive_system(test_config):
    """Create cognitive system using factory pattern with controlled mocks."""
    # Create system with all mock components
    system = create_fully_mocked_system(test_config)

    # Set up some predictable test data
    from datetime import datetime

    test_memory = CognitiveMemory(
        id="factory-test-memory",
        content="Factory test memory content",
        memory_type="episodic",
        hierarchy_level=0,
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
    )
    system.memory_storage.stored_memories["factory-test-memory"] = test_memory

    return system


@pytest.fixture
def test_config():
    """Create test configuration."""
    with patch("cognitive_memory.core.config.load_dotenv"):
        config = SystemConfig.from_env()
        return config


@pytest.fixture
def cognitive_system(
    mock_embedding_provider,
    mock_vector_storage,
    mock_memory_storage,
    mock_connection_graph,
    mock_activation_engine,
    test_config,
):
    """Create cognitive system with mocked dependencies."""
    return CognitiveMemorySystem(
        embedding_provider=mock_embedding_provider,
        vector_storage=mock_vector_storage,
        memory_storage=mock_memory_storage,
        connection_graph=mock_connection_graph,
        activation_engine=mock_activation_engine,
        config=test_config,
    )


class TestCognitiveMemorySystem:
    """Test cases for CognitiveMemorySystem."""

    def test_initialization(self, cognitive_system):
        """Test system initializes with all dependencies."""
        assert cognitive_system.embedding_provider is not None
        assert cognitive_system.vector_storage is not None
        assert cognitive_system.memory_storage is not None
        assert cognitive_system.connection_graph is not None
        assert cognitive_system.activation_engine is not None
        assert cognitive_system.config is not None

    @patch("cognitive_memory.core.cognitive_system.datetime")
    def test_store_experience_success(
        self,
        mock_datetime,
        cognitive_system,
        mock_embedding_provider,
        mock_memory_storage,
        mock_vector_storage,
    ):
        """Test successful experience storage."""
        # Set fixed datetime for deterministic testing
        from datetime import datetime

        fixed_time = datetime(2024, 1, 15, 14, 30, 0)
        mock_datetime.now.return_value = fixed_time

        test_text = "I learned something new about machine learning today"

        # Mock successful operations
        mock_embedding_provider.encode.return_value = np.random.randn(512)
        mock_memory_storage.store_memory.return_value = True

        # Store experience
        memory_id = cognitive_system.store_experience(test_text)

        # Verify operations were called
        assert memory_id != ""
        mock_embedding_provider.encode.assert_called_once_with(test_text)
        mock_memory_storage.store_memory.assert_called_once()
        mock_vector_storage.store_vector.assert_called_once()

        # Verify memory storage call
        stored_memory = mock_memory_storage.store_memory.call_args[0][0]
        assert stored_memory.content == test_text
        assert stored_memory.memory_type == "semantic"
        assert stored_memory.hierarchy_level == 1
        assert stored_memory.timestamp == fixed_time

        # Verify vector storage metadata
        vector_call_args = mock_vector_storage.store_vector.call_args
        metadata = vector_call_args[0][2]  # Third argument is metadata
        assert metadata["content"] == test_text
        assert metadata["timestamp"] == fixed_time.timestamp()

    def test_store_experience_with_context(self, cognitive_system, mock_memory_storage):
        """Test experience storage with custom context."""
        test_text = "Conceptual learning about AI"
        context = {"hierarchy_level": 0, "category": "concepts"}

        memory_id = cognitive_system.store_experience(test_text, context)

        assert memory_id != ""
        stored_memory = mock_memory_storage.store_memory.call_args[0][0]
        assert stored_memory.hierarchy_level == 0
        assert stored_memory.memory_type == "semantic"

    def test_store_experience_empty_text(self, cognitive_system):
        """Test storing empty text returns empty string."""
        memory_id = cognitive_system.store_experience("")
        assert memory_id == ""

        memory_id = cognitive_system.store_experience("   ")
        assert memory_id == ""

    def test_store_experience_storage_failure(
        self, cognitive_system, mock_memory_storage
    ):
        """Test storage failure handling."""
        mock_memory_storage.store_memory.return_value = False

        memory_id = cognitive_system.store_experience("test text")
        assert memory_id == ""

    def test_retrieve_memories_success(
        self,
        cognitive_system,
        mock_embedding_provider,
        mock_activation_engine,
    ):
        """Test successful memory retrieval."""
        query = "machine learning concepts"

        # Mock operations
        mock_embedding_provider.encode.return_value = np.random.randn(512)

        # Retrieve memories
        results = cognitive_system.retrieve_memories(query)

        # Verify structure
        assert "core" in results
        assert "peripheral" in results

        # Verify operations were called
        mock_embedding_provider.encode.assert_called_with(query)
        mock_activation_engine.activate_memories.assert_called_once()

    def test_retrieve_memories_specific_types(
        self, cognitive_system, mock_activation_engine
    ):
        """Test retrieval with specific memory types."""
        query = "test query"
        types = ["core", "peripheral"]

        results = cognitive_system.retrieve_memories(query, types=types)

        # Should have core memories (peripheral may be empty if no matches)
        assert len(results["core"]) > 0
        # Note: peripheral memories may be empty if no matches above threshold

    def test_factory_system_isolation(self, factory_cognitive_system):
        """Test that factory-created systems provide proper test isolation."""
        # This test demonstrates that factory-created systems provide isolated testing
        system = factory_cognitive_system

        # Verify we get the mock components we configured
        assert isinstance(system.embedding_provider, MockEmbeddingProvider)
        assert isinstance(system.vector_storage, MockVectorStorage)
        assert isinstance(system.memory_storage, MockMemoryStorage)

        # Test that we can control the system behavior through the mocks
        embedding_provider = system.embedding_provider
        vector_storage = system.vector_storage
        memory_storage = system.memory_storage

        # Test that call counts are properly isolated (start at 0)
        assert embedding_provider.call_count == 0
        assert vector_storage.call_counts["store"] == 0
        assert memory_storage.call_counts["store"] == 0

        # Perform an operation
        test_text = "Factory test memory"
        memory_id = system.store_experience(test_text)

        # Verify that the operations were called and we can track them
        assert embedding_provider.call_count > 0
        assert vector_storage.call_counts["store"] > 0
        assert memory_storage.call_counts["store"] > 0
        assert memory_id != ""

        # Verify that the test memory we set up is accessible
        assert "factory-test-memory" in memory_storage.stored_memories

    def test_factory_vs_traditional_mocks_comparison(self, test_config):
        """Test comparing factory pattern vs traditional mocking approaches."""
        # Traditional approach - manual mock creation
        traditional_embedding = Mock(spec=EmbeddingProvider)
        traditional_embedding.encode.return_value = np.random.randn(512)
        traditional_memory = Mock(spec=MemoryStorage)
        traditional_memory.store_memory.return_value = True

        # Factory approach - structured mock creation
        factory_system = create_fully_mocked_system(test_config)

        # The factory approach provides:
        # 1. Consistent mock behavior across tests
        # 2. Proper interface compliance validation
        # 3. Built-in call tracking and test utilities
        # 4. Easier component substitution

        # Verify factory system has predictable behavior
        result = factory_system.store_experience("Test experience")
        assert result != ""  # Factory mocks return valid IDs

        # Verify we can introspect mock behavior
        embedding_provider = factory_system.embedding_provider
        assert hasattr(embedding_provider, "call_count")
        assert hasattr(embedding_provider, "last_input")
        assert embedding_provider.call_count > 0

    def test_retrieve_memories_empty_query(self, cognitive_system):
        """Test retrieval with empty query."""
        results = cognitive_system.retrieve_memories("")

        assert results["core"] == []
        assert results["peripheral"] == []

    def test_consolidate_memories(
        self,
        cognitive_system,
        mock_memory_storage,
        mock_embedding_provider,
        mock_vector_storage,
    ):
        """Test memory consolidation process."""
        # Create sample episodic memory for consolidation with fixed timestamp
        from datetime import datetime

        old_timestamp = datetime(2024, 1, 1, 10, 0, 0)  # Fixed old timestamp
        episodic_memory = CognitiveMemory(
            id="episodic-1",
            content="Frequently accessed memory",
            memory_type="episodic",
            hierarchy_level=2,
            dimensions={},
            timestamp=old_timestamp,
            strength=0.9,
            access_count=10,  # Frequently accessed
        )

        mock_memory_storage.get_memories_by_level.return_value = [episodic_memory]
        mock_embedding_provider.encode.return_value = np.random.randn(512)

        # Run consolidation
        stats = cognitive_system.consolidate_memories()

        # Verify results
        assert "total_episodic" in stats
        assert "consolidated" in stats
        assert stats["total_episodic"] == 1

        # Verify semantic memory was created
        assert mock_memory_storage.store_memory.call_count >= 1

    def test_get_memory_stats(self, cognitive_system, mock_memory_storage):
        """Test system statistics retrieval."""
        # Mock memory counts
        mock_memory_storage.get_memories_by_level.side_effect = [
            [Mock(), Mock()],  # Level 0: 2 memories
            [Mock()],  # Level 1: 1 memory
            [Mock(), Mock(), Mock()],  # Level 2: 3 memories
        ]

        stats = cognitive_system.get_memory_stats()

        # Verify structure
        assert "timestamp" in stats
        assert "system_config" in stats
        assert "memory_counts" in stats

        # Verify config values
        config = stats["system_config"]
        assert "activation_threshold" in config

    def test_error_handling_in_store(self, cognitive_system, mock_embedding_provider):
        """Test error handling during experience storage."""
        # Make embedding provider raise exception
        mock_embedding_provider.encode.side_effect = Exception("Encoding failed")

        memory_id = cognitive_system.store_experience("test text")
        assert memory_id == ""

    def test_error_handling_in_retrieve(
        self, cognitive_system, mock_embedding_provider
    ):
        """Test error handling during memory retrieval."""
        # Make embedding provider raise exception
        mock_embedding_provider.encode.side_effect = Exception("Encoding failed")

        results = cognitive_system.retrieve_memories("test query")

        # Should return empty results
        assert results["core"] == []
        assert results["peripheral"] == []

    def test_invalid_hierarchy_level(self, cognitive_system, mock_memory_storage):
        """Test handling of invalid hierarchy level in context."""
        context = {"hierarchy_level": 5}  # Invalid level

        _ = cognitive_system.store_experience("test", context)

        # Should default to level 2
        stored_memory = mock_memory_storage.store_memory.call_args[0][0]
        assert stored_memory.hierarchy_level == 2
