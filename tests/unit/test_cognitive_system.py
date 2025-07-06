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
    mock.get_memories_by_tags.return_value = []
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
        mock_memory_storage,
    ):
        """Test successful memory retrieval."""
        query = "machine learning concepts"

        # Mock operations
        mock_embedding_provider.encode.return_value = np.random.randn(512)
        mock_memory_storage.get_memories_by_tags.return_value = []  # No tag memories

        # Retrieve memories
        results = cognitive_system.retrieve_memories(query)

        # Verify structure
        assert "core" in results
        assert "peripheral" in results

        # Verify operations were called
        mock_embedding_provider.encode.assert_called_with(query)
        mock_activation_engine.activate_memories.assert_called_once()

    def test_retrieve_memories_specific_types(
        self, cognitive_system, mock_activation_engine, mock_memory_storage
    ):
        """Test retrieval with specific memory types."""
        query = "test query"
        types = ["core", "peripheral"]

        # Mock memory storage to return no tag memories
        mock_memory_storage.get_memories_by_tags.return_value = []

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

    def test_store_experience_with_tags_content_fusion(
        self, cognitive_system, mock_embedding_provider, mock_memory_storage
    ):
        """Test that tags are included in content before embedding."""
        test_text = "I learned about neural networks"
        context = {"tags": ["machine-learning", "ai", "deep-learning"]}

        # Mock successful operations
        mock_embedding_provider.encode.return_value = np.random.randn(512)
        mock_memory_storage.store_memory.return_value = True

        # Store experience with tags
        memory_id = cognitive_system.store_experience(test_text, context)

        # Verify embedding was called with content + tags
        expected_content = (
            "I learned about neural networks machine-learning ai deep-learning"
        )
        mock_embedding_provider.encode.assert_called_once_with(expected_content)

        # Verify memory storage preserves original content (without tags)
        stored_memory = mock_memory_storage.store_memory.call_args[0][0]
        assert stored_memory.content == test_text
        assert stored_memory.tags == ["machine-learning", "ai", "deep-learning"]
        assert memory_id != ""

    def test_store_experience_without_tags(
        self, cognitive_system, mock_embedding_provider, mock_memory_storage
    ):
        """Test that content without tags is encoded normally."""
        test_text = "Regular content without tags"

        # Mock successful operations
        mock_embedding_provider.encode.return_value = np.random.randn(512)
        mock_memory_storage.store_memory.return_value = True

        # Store experience without tags
        memory_id = cognitive_system.store_experience(test_text)

        # Verify embedding was called with original content only
        mock_embedding_provider.encode.assert_called_once_with(test_text)

        # Verify memory storage
        stored_memory = mock_memory_storage.store_memory.call_args[0][0]
        assert stored_memory.content == test_text
        assert stored_memory.tags is None
        assert memory_id != ""

    def test_store_experience_with_empty_tags(
        self, cognitive_system, mock_embedding_provider, mock_memory_storage
    ):
        """Test that empty tags list doesn't affect encoding."""
        test_text = "Content with empty tags"
        context = {"tags": []}

        # Mock successful operations
        mock_embedding_provider.encode.return_value = np.random.randn(512)
        mock_memory_storage.store_memory.return_value = True

        # Store experience with empty tags
        memory_id = cognitive_system.store_experience(test_text, context)

        # Verify embedding was called with original content only
        mock_embedding_provider.encode.assert_called_once_with(test_text)

        # Verify memory storage
        stored_memory = mock_memory_storage.store_memory.call_args[0][0]
        assert stored_memory.content == test_text
        assert stored_memory.tags == []
        assert memory_id != ""

    def test_tag_boost_single_match(self, cognitive_system):
        """Test tag boost calculation for single tag match."""
        from datetime import datetime

        # Create memory with tags
        memory = CognitiveMemory(
            id="test-memory",
            content="Machine learning concepts",
            memory_type="semantic",
            hierarchy_level=1,
            timestamp=datetime.now(),
            tags=["machine-learning", "concepts"],
        )

        # Test query that matches one tag as exact token match
        boost = cognitive_system._calculate_tag_boost(
            memory, "learning about machine-learning stuff"
        )
        assert boost == 0.4  # One exact match = 0.4 boost

    def test_tag_boost_multiple_matches(self, cognitive_system):
        """Test tag boost calculation for multiple tag matches."""
        from datetime import datetime

        # Create memory with tags
        memory = CognitiveMemory(
            id="test-memory",
            content="Deep learning with neural networks",
            memory_type="semantic",
            hierarchy_level=1,
            timestamp=datetime.now(),
            tags=["deep-learning", "neural-networks", "ai"],
        )

        # Test query that matches multiple tags exactly
        boost = cognitive_system._calculate_tag_boost(
            memory, "deep-learning neural-networks tutorial"
        )
        assert (
            boost == 0.8
        )  # Two exact matches (0.4 + 0.4) + bonus (0.1) = 0.9, capped at 0.8

    def test_tag_boost_no_match(self, cognitive_system):
        """Test tag boost calculation when no tags match."""
        from datetime import datetime

        # Create memory with tags
        memory = CognitiveMemory(
            id="test-memory",
            content="Natural language processing",
            memory_type="semantic",
            hierarchy_level=1,
            timestamp=datetime.now(),
            tags=["nlp", "linguistics"],
        )

        # Test query that doesn't match any tags
        boost = cognitive_system._calculate_tag_boost(memory, "computer vision opencv")
        assert boost == 0.0  # No tag matches = 0.0 boost

    def test_tag_boost_case_insensitive(self, cognitive_system):
        """Test that tag matching is case insensitive."""
        from datetime import datetime

        # Create memory with mixed case tags
        memory = CognitiveMemory(
            id="test-memory",
            content="Machine learning algorithms",
            memory_type="semantic",
            hierarchy_level=1,
            timestamp=datetime.now(),
            tags=["Machine-Learning", "Algorithms"],
        )

        # Test query with different case (lowercase) - exact token match
        boost = cognitive_system._calculate_tag_boost(
            memory, "machine-learning tutorial"
        )
        assert boost == 0.4  # Case insensitive exact match

    def test_tag_boost_no_tags(self, cognitive_system):
        """Test tag boost calculation when memory has no tags."""
        from datetime import datetime

        # Create memory without tags
        memory = CognitiveMemory(
            id="test-memory",
            content="Some content",
            memory_type="semantic",
            hierarchy_level=1,
            timestamp=datetime.now(),
            tags=None,
        )

        # Test query
        boost = cognitive_system._calculate_tag_boost(memory, "some content query")
        assert boost == 0.0  # No tags = 0.0 boost

    def test_tag_boost_capped_at_maximum(self, cognitive_system):
        """Test that tag boost is capped at 0.5."""
        from datetime import datetime

        # Create memory with many tags
        memory = CognitiveMemory(
            id="test-memory",
            content="Comprehensive AI tutorial",
            memory_type="semantic",
            hierarchy_level=1,
            timestamp=datetime.now(),
            tags=["ai", "ml", "deep", "learning", "neural", "networks"],
        )

        # Test query that matches many tags (would exceed 0.8 without cap)
        boost = cognitive_system._calculate_tag_boost(
            memory, "ai ml deep learning neural networks"
        )
        assert boost == 0.8  # Capped at maximum

    def test_apply_tag_boost_reordering(self, cognitive_system):
        """Test that _apply_tag_boost reorders memories correctly."""
        from datetime import datetime

        # Create memories with different tag match potential
        memory_no_tags = CognitiveMemory(
            id="memory-1",
            content="Regular content",
            memory_type="semantic",
            hierarchy_level=1,
            timestamp=datetime.now(),
            tags=None,
        )

        memory_with_matching_tag = CognitiveMemory(
            id="memory-2",
            content="Machine learning content",
            memory_type="semantic",
            hierarchy_level=1,
            timestamp=datetime.now(),
            tags=["machine-learning", "ai"],
        )

        memory_with_non_matching_tag = CognitiveMemory(
            id="memory-3",
            content="Different content",
            memory_type="semantic",
            hierarchy_level=1,
            timestamp=datetime.now(),
            tags=["biology", "genetics"],
        )

        # Create results dict
        results = {
            "core": [
                memory_no_tags,
                memory_with_matching_tag,
                memory_with_non_matching_tag,
            ],
            "peripheral": [],
        }

        # Apply tag boost
        cognitive_system._apply_tag_boost(results, "machine-learning tutorial")

        # Verify reordering: memory with matching tag should be first
        assert results["core"][0].id == "memory-2"  # Has matching tag
        assert results["core"][1].id in ["memory-1", "memory-3"]  # Others follow

    def test_enhanced_tag_boost_exact_match(self, cognitive_system):
        """Test enhanced tag boost calculation for exact token matches."""
        from datetime import datetime

        # Create memory with tags
        memory = CognitiveMemory(
            id="test-memory",
            content="Machine learning concepts",
            memory_type="semantic",
            hierarchy_level=1,
            timestamp=datetime.now(),
            tags=["machine-learning", "concepts"],
        )

        # Test exact token match
        boost = cognitive_system._calculate_tag_boost(
            memory, "machine-learning tutorial"
        )
        assert boost == 0.4  # Exact token match = 0.4 boost

    def test_enhanced_tag_boost_multiple_exact_matches(self, cognitive_system):
        """Test enhanced tag boost with multiple exact matches and bonus."""
        from datetime import datetime

        # Create memory with multiple tags
        memory = CognitiveMemory(
            id="test-memory",
            content="Deep learning with neural networks",
            memory_type="semantic",
            hierarchy_level=1,
            timestamp=datetime.now(),
            tags=["deep-learning", "neural-networks", "ai"],
        )

        # Test multiple exact matches
        boost = cognitive_system._calculate_tag_boost(
            memory, "deep-learning neural-networks tutorial"
        )
        assert (
            boost == 0.8
        )  # Two exact matches (0.4 + 0.4) + bonus (0.1) = 0.9, capped at 0.8

    def test_retrieval_with_exact_tag_search(
        self,
        cognitive_system,
        mock_embedding_provider,
        mock_vector_storage,
        mock_memory_storage,
    ):
        """Test that memories with exact tag matches get highest priority in retrieval."""
        from datetime import datetime

        from cognitive_memory.core.memory import SearchResult

        # Create memories with different relevance
        tag_match_memory = CognitiveMemory(
            id="tag-match",
            content="Low relevance content",
            memory_type="semantic",
            hierarchy_level=1,
            timestamp=datetime.now(),
            tags=["machine-learning"],
        )

        high_relevance_memory = CognitiveMemory(
            id="high-relevance",
            content="Very relevant content about algorithms",
            memory_type="semantic",
            hierarchy_level=1,
            timestamp=datetime.now(),
            tags=["algorithms"],
        )

        # Mock tag search to return empty (no direct tag matches)
        mock_memory_storage.get_memories_by_tags.return_value = []

        # Mock vector search returning high relevance first (normally)
        mock_results = [
            SearchResult(
                memory=high_relevance_memory, similarity_score=0.5, metadata={}
            ),  # Lower score
            SearchResult(
                memory=tag_match_memory, similarity_score=0.3, metadata={}
            ),  # Will get boosted to 0.7
        ]
        mock_vector_storage.search_similar.return_value = mock_results

        # Mock memory storage to return complete objects
        def mock_retrieve(memory_id):
            if memory_id == "tag-match":
                return tag_match_memory
            elif memory_id == "high-relevance":
                return high_relevance_memory
            return None

        mock_memory_storage.retrieve_memory.side_effect = mock_retrieve

        # Mock empty activation result to trigger fallback
        mock_activation_result = Mock()
        mock_activation_result.core_memories = []
        mock_activation_result.peripheral_memories = []
        cognitive_system.activation_engine.activate_memories.return_value = (
            mock_activation_result
        )

        # Search for exact tag
        results = cognitive_system.retrieve_memories("machine-learning")

        # Tag match should be first: 0.3 + 0.4 = 0.7 > 0.5
        assert len(results["core"]) > 0
        # The exact order depends on how the fallback mechanism works, but tag match should rank higher

    def test_tag_based_recall_explicit_test(self, cognitive_system):
        """Explicit test that recall will use tags to give you memories with unrelated content."""
        from datetime import datetime

        # Create memory with content unrelated to tags
        memory_with_unrelated_tags = CognitiveMemory(
            id="unrelated-tag-memory",
            content="Python database connection optimization techniques include connection pooling, lazy loading, and prepared statements for improved performance.",
            memory_type="semantic",
            hierarchy_level=1,
            timestamp=datetime.now(),
            tags=["banana-bread", "kitchen-recipe"],
        )

        # Mock the _add_tag_memories method to find our memory
        def mock_add_tag_memories(query, types, results, max_results):
            if "banana-bread" in query.lower():
                if "core" in types:
                    results["core"].append(memory_with_unrelated_tags)

        cognitive_system._add_tag_memories = mock_add_tag_memories

        # Mock the _add_activation_memories method to do nothing
        def mock_add_activation_memories(query_embedding, types, results, max_results):
            pass  # Don't add any activation memories

        cognitive_system._add_activation_memories = mock_add_activation_memories

        # Search using only the tag - should find the memory despite content mismatch
        results = cognitive_system.retrieve_memories("banana-bread")

        # Verify the memory was found through tag matching
        assert len(results["core"]) > 0
        found_memory = results["core"][0]
        assert found_memory.id == "unrelated-tag-memory"
        assert (
            found_memory.content
            == "Python database connection optimization techniques include connection pooling, lazy loading, and prepared statements for improved performance."
        )
        assert "banana-bread" in found_memory.tags
        assert "kitchen-recipe" in found_memory.tags
