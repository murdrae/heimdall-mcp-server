"""
Unit tests for ContextualRetrieval.

Tests the high-level retrieval coordination that integrates activation spreading,
similarity search, and bridge discovery for comprehensive memory retrieval.
"""

from unittest.mock import Mock

import numpy as np
import pytest

from cognitive_memory.core.interfaces import (
    ActivationEngine,
    BridgeDiscovery,
    ConnectionGraph,
    MemoryStorage,
)
from cognitive_memory.core.memory import (
    BridgeMemory,
    CognitiveMemory,
)
from cognitive_memory.retrieval.contextual_retrieval import (
    ContextualRetrieval,
    ContextualRetrievalResult,
)
from cognitive_memory.retrieval.similarity_search import SimilaritySearch


class TestContextualRetrieval:
    """Test ContextualRetrieval implementation."""

    @pytest.fixture
    def mock_memory_storage(self) -> Mock:
        """Create mock memory storage."""
        mock = Mock(spec=MemoryStorage)
        return mock

    @pytest.fixture
    def mock_activation_engine(self) -> Mock:
        """Create mock activation engine."""
        mock = Mock(spec=ActivationEngine)
        return mock

    @pytest.fixture
    def mock_similarity_search(self) -> Mock:
        """Create mock similarity search."""
        mock = Mock(spec=SimilaritySearch)
        return mock

    @pytest.fixture
    def mock_bridge_discovery(self) -> Mock:
        """Create mock bridge discovery."""
        mock = Mock(spec=BridgeDiscovery)
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
        """Create sample memories with embeddings."""
        for i, memory in enumerate(sample_memories):
            np.random.seed(i)  # Deterministic embeddings
            memory.cognitive_embedding = np.random.randn(512)
        return sample_memories

    @pytest.fixture
    def contextual_retrieval(
        self,
        mock_memory_storage: Mock,
        mock_activation_engine: Mock,
        mock_similarity_search: Mock,
        mock_bridge_discovery: Mock,
        mock_connection_graph: Mock,
    ) -> ContextualRetrieval:
        """Create ContextualRetrieval with mocked dependencies."""
        return ContextualRetrieval(
            memory_storage=mock_memory_storage,
            activation_engine=mock_activation_engine,
            similarity_search=mock_similarity_search,
            bridge_discovery=mock_bridge_discovery,
            connection_graph=mock_connection_graph,
        )

    def test_init(
        self,
        mock_memory_storage: Mock,
        mock_activation_engine: Mock,
        mock_similarity_search: Mock,
        mock_bridge_discovery: Mock,
        mock_connection_graph: Mock,
    ) -> None:
        """Test ContextualRetrieval initialization."""
        retrieval = ContextualRetrieval(
            memory_storage=mock_memory_storage,
            activation_engine=mock_activation_engine,
            similarity_search=mock_similarity_search,
            bridge_discovery=mock_bridge_discovery,
            connection_graph=mock_connection_graph,
        )

        assert retrieval.memory_storage == mock_memory_storage
        assert retrieval.activation_engine == mock_activation_engine
        assert retrieval.similarity_search == mock_similarity_search
        assert retrieval.bridge_discovery == mock_bridge_discovery

    def test_init_minimal(self, mock_memory_storage: Mock) -> None:
        """Test initialization with minimal components."""
        retrieval = ContextualRetrieval(
            memory_storage=mock_memory_storage,
            activation_engine=None,
            similarity_search=None,
            bridge_discovery=None,
            connection_graph=None,
        )

        assert retrieval.memory_storage == mock_memory_storage
        assert retrieval.activation_engine is None
        # Should create default similarity search and bridge discovery
        assert retrieval.similarity_search is not None
        assert retrieval.bridge_discovery is not None

    def test_retrieve_memories_basic(
        self,
        contextual_retrieval: ContextualRetrieval,
        mock_numpy_embedding: np.ndarray,
    ) -> None:
        """Test basic memory retrieval."""
        result = contextual_retrieval.retrieve_memories(
            query_context=mock_numpy_embedding,
        )

        assert isinstance(result, ContextualRetrievalResult)
        assert isinstance(result.core_memories, list)
        assert isinstance(result.peripheral_memories, list)
        assert isinstance(result.bridge_memories, list)
        assert result.retrieval_time_ms >= 0

    def test_retrieve_memories_with_parameters(
        self,
        contextual_retrieval: ContextualRetrieval,
        mock_numpy_embedding: np.ndarray,
    ) -> None:
        """Test memory retrieval with custom parameters."""
        result = contextual_retrieval.retrieve_memories(
            query_context=mock_numpy_embedding,
            max_core=5,
            max_peripheral=10,
            max_bridges=3,
            activation_threshold=0.7,
            similarity_threshold=0.5,
        )

        assert isinstance(result, ContextualRetrievalResult)
        assert result.retrieval_time_ms >= 0

    def test_retrieve_memories_disable_components(
        self,
        contextual_retrieval: ContextualRetrieval,
        mock_numpy_embedding: np.ndarray,
    ) -> None:
        """Test retrieval with components disabled."""
        result = contextual_retrieval.retrieve_memories(
            query_context=mock_numpy_embedding,
            use_activation=False,
            use_similarity=False,
            use_bridges=False,
        )

        assert isinstance(result, ContextualRetrievalResult)
        assert result.retrieval_time_ms >= 0

    def test_retrieve_memories_no_activation_engine(
        self,
        mock_memory_storage: Mock,
        mock_numpy_embedding: np.ndarray,
    ) -> None:
        """Test retrieval without activation engine."""
        retrieval = ContextualRetrieval(
            memory_storage=mock_memory_storage,
            activation_engine=None,
            similarity_search=None,
            bridge_discovery=None,
            connection_graph=None,
        )

        result = retrieval.retrieve_memories(
            query_context=mock_numpy_embedding,
        )

        assert isinstance(result, ContextualRetrievalResult)


class TestContextualRetrievalResult:
    """Test ContextualRetrievalResult data structure."""

    def test_init(self, sample_memories: list[CognitiveMemory]) -> None:
        """Test ContextualRetrievalResult initialization."""
        bridge_memories = [
            BridgeMemory(
                memory=sample_memories[0],
                novelty_score=0.8,
                connection_potential=0.7,
                bridge_score=0.75,
                explanation="Test bridge",
            )
        ]

        result = ContextualRetrievalResult(
            core_memories=sample_memories[:2],
            peripheral_memories=sample_memories[2:3],
            bridge_memories=bridge_memories,
            retrieval_time_ms=100.5,
        )

        assert result.core_memories == sample_memories[:2]
        assert result.peripheral_memories == sample_memories[2:3]
        assert result.bridge_memories == bridge_memories
        assert result.retrieval_time_ms == 100.5
        assert result.total_memories == 3  # 2 core + 1 peripheral
        assert result.total_bridges == 1

    def test_get_all_memories(self, sample_memories: list[CognitiveMemory]) -> None:
        """Test getting all memories from result."""
        result = ContextualRetrievalResult(
            core_memories=sample_memories[:2],
            peripheral_memories=sample_memories[2:3],
            bridge_memories=[],
        )

        all_memories = result.get_all_memories()

        assert len(all_memories) == 3
        assert all_memories[:2] == sample_memories[:2]
        assert all_memories[2:] == sample_memories[2:3]

    def test_get_memories_by_level(
        self, sample_memories: list[CognitiveMemory]
    ) -> None:
        """Test getting memories by hierarchy level."""
        result = ContextualRetrievalResult(
            core_memories=sample_memories[:3],
            peripheral_memories=sample_memories[3:4],
            bridge_memories=[],
        )

        # This test will need to be updated based on how hierarchy_level is used
        # For now, just test that the method exists and returns a list
        level_0_memories = result.get_memories_by_level(0)
        assert isinstance(level_0_memories, list)

    def test_to_dict(self, sample_memories: list[CognitiveMemory]) -> None:
        """Test conversion to dictionary."""
        bridge_memories = [
            BridgeMemory(
                memory=sample_memories[0],
                novelty_score=0.8,
                connection_potential=0.7,
                bridge_score=0.75,
                explanation="Test bridge",
            )
        ]

        result = ContextualRetrievalResult(
            core_memories=sample_memories[:1],
            peripheral_memories=sample_memories[1:2],
            bridge_memories=bridge_memories,
            retrieval_time_ms=123.45,
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert "core_memories" in result_dict
        assert "peripheral_memories" in result_dict
        assert "bridge_memories" in result_dict
        assert "total_memories" in result_dict
        assert "total_bridges" in result_dict
        assert "retrieval_time_ms" in result_dict
        assert result_dict["retrieval_time_ms"] == 123.45
