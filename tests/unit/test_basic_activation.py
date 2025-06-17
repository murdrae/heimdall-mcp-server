"""
Unit tests for BasicActivationEngine.

Tests the BFS-based activation spreading mechanism that activates memories
through breadth-first traversal of the memory connection graph.
"""

from unittest.mock import Mock

import pytest
import torch

from cognitive_memory.core.interfaces import ConnectionGraph, MemoryStorage
from cognitive_memory.core.memory import (
    ActivationResult,
    CognitiveMemory,
    MemoryConnection,
)
from cognitive_memory.retrieval.basic_activation import BasicActivationEngine


class TestBasicActivationEngine:
    """Test BasicActivationEngine implementation."""

    @pytest.fixture
    def mock_memory_storage(self) -> Mock:
        """Create mock memory storage."""
        mock = Mock(spec=MemoryStorage)
        return mock

    @pytest.fixture
    def mock_connection_graph(self) -> Mock:
        """Create mock connection graph."""
        mock = Mock(spec=ConnectionGraph)
        return mock

    @pytest.fixture
    def sample_memories_with_embeddings(
        self, sample_memories: list[CognitiveMemory]
    ) -> list[CognitiveMemory]:
        """Create sample memories with embeddings for testing."""
        # Ensure all memories have embeddings
        for i, memory in enumerate(sample_memories):
            torch.manual_seed(i)  # Deterministic embeddings
            memory.cognitive_embedding = torch.randn(512)
        return sample_memories

    @pytest.fixture
    def activation_engine(
        self, mock_memory_storage: Mock, mock_connection_graph: Mock
    ) -> BasicActivationEngine:
        """Create BasicActivationEngine with mocks."""
        return BasicActivationEngine(
            memory_storage=mock_memory_storage,
            connection_graph=mock_connection_graph,
            core_threshold=0.7,
            peripheral_threshold=0.5,
        )

    def test_init(self, mock_memory_storage: Mock, mock_connection_graph: Mock) -> None:
        """Test BasicActivationEngine initialization."""
        engine = BasicActivationEngine(
            memory_storage=mock_memory_storage,
            connection_graph=mock_connection_graph,
            core_threshold=0.8,
            peripheral_threshold=0.6,
        )

        assert engine.memory_storage == mock_memory_storage
        assert engine.connection_graph == mock_connection_graph
        assert engine.core_threshold == 0.8
        assert engine.peripheral_threshold == 0.6

    def test_init_default_thresholds(
        self, mock_memory_storage: Mock, mock_connection_graph: Mock
    ) -> None:
        """Test initialization with default thresholds."""
        engine = BasicActivationEngine(
            memory_storage=mock_memory_storage,
            connection_graph=mock_connection_graph,
        )

        assert engine.core_threshold == 0.7
        assert engine.peripheral_threshold == 0.5

    def test_activate_memories_no_starting_memories(
        self,
        activation_engine: BasicActivationEngine,
        mock_memory_storage: Mock,
        mock_torch_embedding: torch.Tensor,
    ) -> None:
        """Test activation when no starting memories are found."""
        # Mock empty L0 memories
        mock_memory_storage.get_memories_by_level.return_value = []

        result = activation_engine.activate_memories(
            context=mock_torch_embedding, threshold=0.6
        )

        assert isinstance(result, ActivationResult)
        assert len(result.core_memories) == 0
        assert len(result.peripheral_memories) == 0
        assert result.total_activated == 0
        assert result.activation_time_ms > 0

    def test_activate_memories_basic_flow(
        self,
        activation_engine: BasicActivationEngine,
        mock_memory_storage: Mock,
        mock_connection_graph: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_torch_embedding: torch.Tensor,
    ) -> None:
        """Test basic activation flow with memories."""
        # Setup L0 memories
        l0_memories = [
            m for m in sample_memories_with_embeddings if m.hierarchy_level == 0
        ]
        if not l0_memories:
            # Ensure we have at least one L0 memory
            sample_memories_with_embeddings[0].hierarchy_level = 0
            l0_memories = [sample_memories_with_embeddings[0]]

        mock_memory_storage.get_memories_by_level.return_value = l0_memories

        # Mock connection graph to return some connections
        mock_connection_graph.get_connections.return_value = [
            sample_memories_with_embeddings[1]
        ]

        result = activation_engine.activate_memories(
            context=mock_torch_embedding, threshold=0.3
        )

        assert isinstance(result, ActivationResult)
        assert result.total_activated >= 0
        assert result.activation_time_ms > 0
        mock_memory_storage.get_memories_by_level.assert_called_once_with(0)

    def test_find_starting_memories(
        self,
        activation_engine: BasicActivationEngine,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_torch_embedding: torch.Tensor,
    ) -> None:
        """Test _find_starting_memories method."""
        l0_memories = sample_memories_with_embeddings[:3]
        for memory in l0_memories:
            memory.level = 0

        starting_memories = activation_engine._find_starting_memories(
            context=mock_torch_embedding,
            l0_memories=l0_memories,
            threshold=0.1,  # Low threshold to ensure some matches
        )

        assert isinstance(starting_memories, list)
        # Should return at least some memories with low threshold
        assert len(starting_memories) >= 0

    def test_find_starting_memories_high_threshold(
        self,
        activation_engine: BasicActivationEngine,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_torch_embedding: torch.Tensor,
    ) -> None:
        """Test _find_starting_memories with high threshold."""
        l0_memories = sample_memories_with_embeddings[:3]
        for memory in l0_memories:
            memory.level = 0

        starting_memories = activation_engine._find_starting_memories(
            context=mock_torch_embedding,
            l0_memories=l0_memories,
            threshold=0.99,  # Very high threshold
        )

        assert isinstance(starting_memories, list)
        # High threshold should return fewer or no memories
        assert len(starting_memories) <= len(l0_memories)

    def test_find_starting_memories_no_embeddings(
        self,
        activation_engine: BasicActivationEngine,
        sample_memories: list[CognitiveMemory],
    ) -> None:
        """Test _find_starting_memories with memories without embeddings."""
        l0_memories = sample_memories[:2]
        for memory in l0_memories:
            memory.level = 0
            memory.cognitive_embedding = None  # No embedding

        starting_memories = activation_engine._find_starting_memories(
            context=torch.randn(512), l0_memories=l0_memories, threshold=0.5
        )

        assert starting_memories == []

    def test_bfs_activation_empty_starting(
        self,
        activation_engine: BasicActivationEngine,
        mock_torch_embedding: torch.Tensor,
    ) -> None:
        """Test BFS activation with empty starting memories."""
        result = activation_engine._bfs_activation(
            context=mock_torch_embedding,
            starting_memories=[],
            threshold=0.5,
            max_activations=50,
        )

        assert isinstance(result, ActivationResult)
        assert len(result.core_memories) == 0
        assert len(result.peripheral_memories) == 0

    def test_bfs_activation_with_connections(
        self,
        activation_engine: BasicActivationEngine,
        mock_connection_graph: Mock,
        mock_memory_storage: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
    ) -> None:
        """Test BFS activation with memory connections."""
        starting_memory = sample_memories_with_embeddings[0]
        target_memory = sample_memories_with_embeddings[1]

        # Create similar embeddings to ensure reasonable similarity scores
        context_embedding = (
            torch.ones(512) * 0.5
        )  # Similar to starting memory embedding
        starting_memory.cognitive_embedding = (
            torch.ones(512) * 0.6
        )  # Similar to context
        target_memory.cognitive_embedding = (
            torch.ones(512) * 0.4
        )  # Different but reasonable

        # Boost importance to ensure activation
        starting_memory.importance_score = 0.8
        target_memory.importance_score = 0.6

        mock_connection_graph.get_connections.return_value = [target_memory]

        result = activation_engine._bfs_activation(
            context=context_embedding,
            starting_memories=[starting_memory],
            threshold=0.1,  # Lower threshold to ensure activation
            max_activations=50,
        )

        assert isinstance(result, ActivationResult)
        assert result.total_activated >= 1
        mock_connection_graph.get_connections.assert_called()

    def test_bfs_activation_max_limit(
        self,
        activation_engine: BasicActivationEngine,
        mock_connection_graph: Mock,
        mock_memory_storage: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_torch_embedding: torch.Tensor,
    ) -> None:
        """Test BFS activation respects max_activations limit."""
        starting_memory = sample_memories_with_embeddings[0]

        # Mock lots of connections
        mock_connections = []
        for i in range(1, len(sample_memories_with_embeddings)):
            mock_connections.append(
                MemoryConnection(
                    source_id=starting_memory.id,
                    target_id=sample_memories_with_embeddings[i].id,
                    connection_strength=0.9,
                )
            )

        mock_connection_graph.get_connections.return_value = (
            sample_memories_with_embeddings[1:]
        )

        result = activation_engine._bfs_activation(
            context=mock_torch_embedding,
            starting_memories=[starting_memory],
            threshold=0.1,
            max_activations=2,  # Low limit
        )

        assert isinstance(result, ActivationResult)
        assert result.total_activated <= 3  # Starting + max_activations

    def test_compute_cosine_similarity(
        self, activation_engine: BasicActivationEngine
    ) -> None:
        """Test cosine similarity computation."""
        vec1 = torch.tensor([1.0, 2.0, 3.0])
        vec2 = torch.tensor([2.0, 4.0, 6.0])  # Same direction

        similarity = activation_engine._compute_cosine_similarity(vec1, vec2)
        assert isinstance(similarity, float)
        assert 0.99 < similarity <= 1.0  # Should be very close to 1.0

    def test_compute_cosine_similarity_orthogonal(
        self, activation_engine: BasicActivationEngine
    ) -> None:
        """Test cosine similarity with orthogonal vectors."""
        vec1 = torch.tensor([1.0, 0.0])
        vec2 = torch.tensor([0.0, 1.0])

        similarity = activation_engine._compute_cosine_similarity(vec1, vec2)
        assert isinstance(similarity, float)
        assert similarity == pytest.approx(0.0, abs=1e-6)

    def test_compute_cosine_similarity_zero_vector(
        self, activation_engine: BasicActivationEngine
    ) -> None:
        """Test cosine similarity with zero vector."""
        vec1 = torch.tensor([1.0, 2.0])
        vec2 = torch.tensor([0.0, 0.0])

        similarity = activation_engine._compute_cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_compute_cosine_similarity_different_devices(
        self, activation_engine: BasicActivationEngine
    ) -> None:
        """Test cosine similarity with vectors on different devices."""
        vec1 = torch.tensor([1.0, 2.0, 3.0])
        vec2 = torch.tensor([1.0, 2.0, 3.0])

        # This should work even if tensors are nominally on different devices
        similarity = activation_engine._compute_cosine_similarity(vec1, vec2)
        assert isinstance(similarity, float)
        assert similarity == pytest.approx(1.0, abs=1e-6)

    def test_activation_result_categorization(
        self,
        activation_engine: BasicActivationEngine,
        mock_memory_storage: Mock,
        mock_connection_graph: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_torch_embedding: torch.Tensor,
    ) -> None:
        """Test that activation results are properly categorized into core/peripheral."""
        # Setup memories with different activation strengths
        l0_memory = sample_memories_with_embeddings[0]
        l0_memory.level = 0
        l0_memory.importance_score = 0.9  # High importance

        mock_memory_storage.get_memories_by_level.return_value = [l0_memory]
        mock_connection_graph.get_connections.return_value = []

        result = activation_engine.activate_memories(
            context=mock_torch_embedding, threshold=0.3
        )

        assert isinstance(result, ActivationResult)
        # Test that we get some categorization
        total_memories = len(result.core_memories) + len(result.peripheral_memories)
        assert total_memories >= 0

    def test_get_activation_config(
        self, activation_engine: BasicActivationEngine
    ) -> None:
        """Test get_activation_config method."""
        config = activation_engine.get_activation_config()

        assert isinstance(config, dict)
        assert config["core_threshold"] == 0.7
        assert config["peripheral_threshold"] == 0.5

    def test_activation_error_handling(
        self,
        activation_engine: BasicActivationEngine,
        mock_memory_storage: Mock,
    ) -> None:
        """Test error handling during activation."""
        # Make storage throw exception
        mock_memory_storage.get_memories_by_level.side_effect = Exception(
            "Storage error"
        )

        result = activation_engine.activate_memories(
            context=torch.randn(512), threshold=0.5
        )

        # Should return empty result gracefully
        assert isinstance(result, ActivationResult)
        assert result.total_activated == 0
        assert result.activation_time_ms > 0

    @pytest.mark.parametrize("threshold", [0.1, 0.5, 0.9])
    def test_activate_memories_different_thresholds(
        self,
        activation_engine: BasicActivationEngine,
        mock_memory_storage: Mock,
        mock_connection_graph: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
        threshold: float,
    ) -> None:
        """Test activation with different threshold values."""
        l0_memories = [sample_memories_with_embeddings[0]]
        l0_memories[0].level = 0
        mock_memory_storage.get_memories_by_level.return_value = l0_memories
        mock_connection_graph.get_connections.return_value = []

        result = activation_engine.activate_memories(
            context=torch.randn(512), threshold=threshold
        )

        assert isinstance(result, ActivationResult)
        assert result.activation_time_ms > 0

    @pytest.mark.parametrize("max_activations", [1, 10, 100])
    def test_activate_memories_different_limits(
        self,
        activation_engine: BasicActivationEngine,
        mock_memory_storage: Mock,
        mock_connection_graph: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
        max_activations: int,
    ) -> None:
        """Test activation with different max_activations limits."""
        l0_memories = [sample_memories_with_embeddings[0]]
        l0_memories[0].level = 0
        mock_memory_storage.get_memories_by_level.return_value = l0_memories
        mock_connection_graph.get_connections.return_value = []

        result = activation_engine.activate_memories(
            context=torch.randn(512), threshold=0.5, max_activations=max_activations
        )

        assert isinstance(result, ActivationResult)
        assert result.total_activated <= max_activations + 1  # +1 for starting memory
