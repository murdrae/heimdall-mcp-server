"""
Unit tests for SimpleBridgeDiscovery.

Tests the distance inversion algorithm for discovering bridge memories
that create novel connections between query and activated memories.
"""

from unittest.mock import Mock

import numpy as np
import pytest

from cognitive_memory.core.interfaces import MemoryStorage
from cognitive_memory.core.memory import BridgeMemory, CognitiveMemory
from cognitive_memory.retrieval.bridge_discovery import SimpleBridgeDiscovery


class TestSimpleBridgeDiscovery:
    """Test SimpleBridgeDiscovery implementation."""

    @pytest.fixture
    def mock_memory_storage(self) -> Mock:
        """Create mock memory storage."""
        mock = Mock(spec=MemoryStorage)
        return mock

    @pytest.fixture
    def sample_memories_with_embeddings(
        self, sample_memories: list[CognitiveMemory]
    ) -> list[CognitiveMemory]:
        """Create sample memories with embeddings."""
        for i, memory in enumerate(sample_memories):
            np.random.seed(i)  # Deterministic embeddings
            memory.cognitive_embedding = np.random.randn(512)
            memory.importance_score = 0.5 + (i * 0.1)  # Varied importance scores
        return sample_memories

    @pytest.fixture
    def bridge_discovery(self, mock_memory_storage: Mock) -> SimpleBridgeDiscovery:
        """Create SimpleBridgeDiscovery with default configuration."""
        return SimpleBridgeDiscovery(
            memory_storage=mock_memory_storage,
            novelty_weight=0.6,
            connection_weight=0.4,
            max_candidates=100,
            min_novelty=0.3,
        )

    def test_init(self, mock_memory_storage: Mock) -> None:
        """Test SimpleBridgeDiscovery initialization."""
        discovery = SimpleBridgeDiscovery(
            memory_storage=mock_memory_storage,
            novelty_weight=0.7,
            connection_weight=0.3,
            max_candidates=50,
            min_novelty=0.4,
        )

        assert discovery.memory_storage == mock_memory_storage
        assert discovery.novelty_weight == 0.7
        assert discovery.connection_weight == 0.3
        assert discovery.max_candidates == 50
        assert discovery.min_novelty == 0.4

    def test_init_default_parameters(self, mock_memory_storage: Mock) -> None:
        """Test initialization with default parameters."""
        discovery = SimpleBridgeDiscovery(memory_storage=mock_memory_storage)

        assert discovery.novelty_weight == 0.6
        assert discovery.connection_weight == 0.4
        assert discovery.max_candidates == 100
        assert discovery.min_novelty == 0.3

    def test_init_weight_validation(self, mock_memory_storage: Mock) -> None:
        """Test weight validation during initialization."""
        discovery = SimpleBridgeDiscovery(
            memory_storage=mock_memory_storage,
            novelty_weight=0.8,
            connection_weight=0.3,  # Sum = 1.1
        )

        # Weights should be stored as provided (no normalization in SimpleBridgeDiscovery)
        assert discovery.novelty_weight == 0.8
        assert discovery.connection_weight == 0.3

    def test_discover_bridges_basic(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        mock_memory_storage: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_numpy_embedding: np.ndarray,
    ) -> None:
        """Test basic bridge discovery functionality."""
        activated_memories = sample_memories_with_embeddings[:2]
        candidate_memories = sample_memories_with_embeddings[2:]

        # Mock storage to return candidates for all levels
        mock_memory_storage.get_memories_by_level.return_value = candidate_memories

        bridges = bridge_discovery.discover_bridges(
            context=mock_numpy_embedding, activated=activated_memories, k=3
        )

        assert isinstance(bridges, list)
        assert len(bridges) <= 3
        assert all(isinstance(b, BridgeMemory) for b in bridges)

        # Should be sorted by bridge score (descending)
        if len(bridges) > 1:
            for i in range(len(bridges) - 1):
                assert bridges[i].bridge_score >= bridges[i + 1].bridge_score

    def test_discover_bridges_no_candidates(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        mock_memory_storage: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_numpy_embedding: np.ndarray,
    ) -> None:
        """Test bridge discovery when no candidates are available."""
        activated_memories = sample_memories_with_embeddings[:2]

        # Mock storage to return empty list for all levels
        mock_memory_storage.get_memories_by_level.return_value = []

        bridges = bridge_discovery.discover_bridges(
            context=mock_numpy_embedding, activated=activated_memories, k=5
        )

        assert bridges == []

    def test_discover_bridges_no_activated(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        mock_memory_storage: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_numpy_embedding: np.ndarray,
    ) -> None:
        """Test bridge discovery with no activated memories."""
        candidate_memories = sample_memories_with_embeddings

        mock_memory_storage.get_memories_by_level.return_value = candidate_memories

        bridges = bridge_discovery.discover_bridges(
            context=mock_numpy_embedding,
            activated=[],  # No activated memories
            k=3,
        )

        assert isinstance(bridges, list)
        # Should still work but connection potential will be 0

    def test_discover_bridges_activated_in_candidates(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        mock_memory_storage: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_numpy_embedding: np.ndarray,
    ) -> None:
        """Test that activated memories are excluded from candidates."""
        activated_memories = sample_memories_with_embeddings[:2]
        all_memories = sample_memories_with_embeddings

        mock_memory_storage.get_memories_by_level.return_value = all_memories

        bridges = bridge_discovery.discover_bridges(
            context=mock_numpy_embedding, activated=activated_memories, k=5
        )

        # No bridge should contain an activated memory
        activated_ids = {m.id for m in activated_memories}
        bridge_ids = {b.memory.id for b in bridges}
        assert bridge_ids.isdisjoint(activated_ids)

    def test_get_candidate_memories(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        mock_memory_storage: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
    ) -> None:
        """Test _get_candidate_memories method."""
        activated_ids = {sample_memories_with_embeddings[0].id}

        # Mock storage for each level
        def get_memories_side_effect(level):
            return [
                m for m in sample_memories_with_embeddings if m.hierarchy_level == level
            ]

        mock_memory_storage.get_memories_by_level.side_effect = get_memories_side_effect

        candidates = bridge_discovery._get_candidate_memories(activated_ids)

        assert isinstance(candidates, list)
        assert len(candidates) <= bridge_discovery.max_candidates

        # Should exclude activated memories
        candidate_ids = {c.id for c in candidates}
        assert candidate_ids.isdisjoint(activated_ids)

        # Should only include memories with embeddings
        assert all(c.cognitive_embedding is not None for c in candidates)

    def test_get_candidate_memories_max_limit(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        mock_memory_storage: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
    ) -> None:
        """Test candidate memory limiting."""
        # Set a low max_candidates limit
        bridge_discovery.max_candidates = 2

        activated_ids = set()
        candidate_memories = sample_memories_with_embeddings

        def get_memories_side_effect(level):
            return [m for m in candidate_memories if m.hierarchy_level == level]

        mock_memory_storage.get_memories_by_level.side_effect = get_memories_side_effect

        candidates = bridge_discovery._get_candidate_memories(activated_ids)

        assert len(candidates) <= 2

    def test_get_candidate_memories_no_embeddings(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        mock_memory_storage: Mock,
        sample_memories: list[CognitiveMemory],  # Without embeddings
    ) -> None:
        """Test candidate selection with memories without embeddings."""
        # Remove embeddings from sample memories
        for memory in sample_memories:
            memory.cognitive_embedding = None

        activated_ids = set()

        def get_memories_side_effect(level):
            return [m for m in sample_memories if m.hierarchy_level == level]

        mock_memory_storage.get_memories_by_level.side_effect = get_memories_side_effect

        candidates = bridge_discovery._get_candidate_memories(activated_ids)

        # Should return empty list since no memories have embeddings
        assert candidates == []

    def test_compute_bridge_scores(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_numpy_embedding: np.ndarray,
    ) -> None:
        """Test _compute_bridge_scores method."""
        candidates = sample_memories_with_embeddings[:3]
        activated = sample_memories_with_embeddings[3:]

        bridge_scores = bridge_discovery._compute_bridge_scores(
            context=mock_numpy_embedding, candidates=candidates, activated=activated
        )

        assert isinstance(bridge_scores, list)
        assert len(bridge_scores) <= len(candidates)

        for candidate, score in bridge_scores:
            assert isinstance(candidate, CognitiveMemory)
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0

    def test_compute_bridge_scores_low_novelty_filter(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        sample_memories_with_embeddings: list[CognitiveMemory],
    ) -> None:
        """Test that low novelty candidates are filtered out."""
        # Use identical embeddings for low novelty
        context = np.ones(512)
        candidates = sample_memories_with_embeddings[:3]
        activated = sample_memories_with_embeddings[3:]

        # Set all candidate embeddings identical to context for low novelty
        for candidate in candidates:
            candidate.cognitive_embedding = context.copy()

        bridge_scores = bridge_discovery._compute_bridge_scores(
            context=context, candidates=candidates, activated=activated
        )

        # Should filter out low novelty candidates
        assert len(bridge_scores) == 0

    def test_calculate_novelty_score(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_numpy_embedding: np.ndarray,
    ) -> None:
        """Test _calculate_novelty_score method."""
        memory = sample_memories_with_embeddings[0]

        novelty = bridge_discovery._calculate_novelty_score(
            mock_numpy_embedding, memory
        )

        assert isinstance(novelty, float)
        assert 0.0 <= novelty <= 1.0

    def test_calculate_novelty_score_identical_vectors(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        sample_memories_with_embeddings: list[CognitiveMemory],
    ) -> None:
        """Test novelty score with identical vectors."""
        memory = sample_memories_with_embeddings[0]
        context = memory.cognitive_embedding.copy()

        novelty = bridge_discovery._calculate_novelty_score(context, memory)

        # Should be 0 for identical vectors (1.0 - 1.0 = 0.0)
        assert novelty == pytest.approx(0.0, abs=1e-6)

    def test_calculate_novelty_score_no_embedding(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        sample_memory: CognitiveMemory,
        mock_numpy_embedding: np.ndarray,
    ) -> None:
        """Test novelty score with memory without embedding."""
        sample_memory.cognitive_embedding = None

        novelty = bridge_discovery._calculate_novelty_score(
            mock_numpy_embedding, sample_memory
        )

        assert novelty == 0.0

    def test_calculate_connection_potential(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        sample_memories_with_embeddings: list[CognitiveMemory],
    ) -> None:
        """Test _calculate_connection_potential method."""
        candidate = sample_memories_with_embeddings[0]
        activated = sample_memories_with_embeddings[1:3]

        connection_potential = bridge_discovery._calculate_connection_potential(
            candidate, activated
        )

        assert isinstance(connection_potential, float)
        assert 0.0 <= connection_potential <= 1.0

    def test_calculate_connection_potential_no_activated(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        sample_memories_with_embeddings: list[CognitiveMemory],
    ) -> None:
        """Test connection potential with no activated memories."""
        candidate = sample_memories_with_embeddings[0]

        connection_potential = bridge_discovery._calculate_connection_potential(
            candidate, []
        )

        assert connection_potential == 0.0

    def test_calculate_connection_potential_no_embedding(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        sample_memories_with_embeddings: list[CognitiveMemory],
        sample_memory: CognitiveMemory,
    ) -> None:
        """Test connection potential with candidate without embedding."""
        sample_memory.cognitive_embedding = None
        activated = sample_memories_with_embeddings[:2]

        connection_potential = bridge_discovery._calculate_connection_potential(
            sample_memory, activated
        )

        assert connection_potential == 0.0

    def test_compute_cosine_similarity(
        self, bridge_discovery: SimpleBridgeDiscovery
    ) -> None:
        """Test cosine similarity computation."""
        vec1 = np.array([1.0, 2.0, 3.0])
        vec2 = np.array([2.0, 4.0, 6.0])  # Same direction

        similarity = bridge_discovery._compute_cosine_similarity(vec1, vec2)
        assert isinstance(similarity, float)
        assert 0.99 < similarity <= 1.0

    def test_compute_cosine_similarity_orthogonal(
        self, bridge_discovery: SimpleBridgeDiscovery
    ) -> None:
        """Test cosine similarity with orthogonal vectors."""
        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([0.0, 1.0])

        similarity = bridge_discovery._compute_cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(0.0, abs=1e-6)

    def test_compute_cosine_similarity_zero_vector(
        self, bridge_discovery: SimpleBridgeDiscovery
    ) -> None:
        """Test cosine similarity with zero vector."""
        vec1 = np.array([1.0, 2.0])
        vec2 = np.array([0.0, 0.0])

        similarity = bridge_discovery._compute_cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_generate_bridge_explanation(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        sample_memory: CognitiveMemory,
    ) -> None:
        """Test _generate_bridge_explanation method."""
        explanation = bridge_discovery._generate_bridge_explanation(
            memory=sample_memory, novelty=0.8, connection_potential=0.6
        )

        assert isinstance(explanation, str)
        assert len(explanation) > 0
        assert "novelty" in explanation.lower()
        assert "connection" in explanation.lower()

    @pytest.mark.parametrize(
        "novelty,expected_desc",
        [
            (0.9, "highly novel"),
            (0.7, "moderately novel"),
            (0.4, "somewhat novel"),
        ],
    )
    def test_generate_bridge_explanation_novelty_levels(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        sample_memory: CognitiveMemory,
        novelty: float,
        expected_desc: str,
    ) -> None:
        """Test explanation generation for different novelty levels."""
        explanation = bridge_discovery._generate_bridge_explanation(
            memory=sample_memory, novelty=novelty, connection_potential=0.5
        )

        assert expected_desc in explanation

    @pytest.mark.parametrize(
        "connection,expected_desc",
        [
            (0.8, "strong connections"),
            (0.6, "moderate connections"),
            (0.3, "weak connections"),
        ],
    )
    def test_generate_bridge_explanation_connection_levels(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        sample_memory: CognitiveMemory,
        connection: float,
        expected_desc: str,
    ) -> None:
        """Test explanation generation for different connection levels."""
        explanation = bridge_discovery._generate_bridge_explanation(
            memory=sample_memory, novelty=0.5, connection_potential=connection
        )

        assert expected_desc in explanation

    def test_get_discovery_config(
        self, bridge_discovery: SimpleBridgeDiscovery
    ) -> None:
        """Test get_discovery_config method."""
        config = bridge_discovery.get_discovery_config()

        assert isinstance(config, dict)
        assert config["novelty_weight"] == 0.6
        assert config["connection_weight"] == 0.4
        assert config["max_candidates"] == 100
        assert config["min_novelty"] == 0.3

    def test_update_weights(self, bridge_discovery: SimpleBridgeDiscovery) -> None:
        """Test update_weights method."""
        bridge_discovery.update_weights(0.7, 0.3)

        assert bridge_discovery.novelty_weight == 0.7
        assert bridge_discovery.connection_weight == 0.3

    def test_update_weights_normalization(
        self, bridge_discovery: SimpleBridgeDiscovery
    ) -> None:
        """Test weight normalization during update."""
        bridge_discovery.update_weights(0.8, 0.4)  # Sum = 1.2

        # Should be normalized
        total = bridge_discovery.novelty_weight + bridge_discovery.connection_weight
        assert abs(total - 1.0) < 0.001

    def test_update_weights_zero_total(
        self, bridge_discovery: SimpleBridgeDiscovery
    ) -> None:
        """Test weight update with zero total weight."""
        original_novelty = bridge_discovery.novelty_weight
        original_connection = bridge_discovery.connection_weight

        bridge_discovery.update_weights(0.0, 0.0)

        # Should keep original weights
        assert bridge_discovery.novelty_weight == original_novelty
        assert bridge_discovery.connection_weight == original_connection

    def test_update_parameters(self, bridge_discovery: SimpleBridgeDiscovery) -> None:
        """Test update_parameters method."""
        bridge_discovery.update_parameters(max_candidates=50, min_novelty=0.5)

        assert bridge_discovery.max_candidates == 50
        assert bridge_discovery.min_novelty == 0.5

    def test_update_parameters_negative_values(
        self, bridge_discovery: SimpleBridgeDiscovery
    ) -> None:
        """Test parameter update with negative values."""
        bridge_discovery.update_parameters(max_candidates=-10, min_novelty=-0.5)

        # Should enforce minimum values
        assert bridge_discovery.max_candidates == 1  # Minimum 1
        assert bridge_discovery.min_novelty == 0.0  # Minimum 0.0

    def test_discover_bridges_error_handling(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        mock_memory_storage: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_numpy_embedding: np.ndarray,
    ) -> None:
        """Test error handling during bridge discovery."""
        activated_memories = sample_memories_with_embeddings[:2]

        # Make storage throw exception
        mock_memory_storage.get_memories_by_level.side_effect = Exception(
            "Storage error"
        )

        bridges = bridge_discovery.discover_bridges(
            context=mock_numpy_embedding, activated=activated_memories, k=3
        )

        # Should return empty list gracefully
        assert bridges == []

    @pytest.mark.parametrize("k", [1, 3, 5, 10])
    def test_discover_bridges_different_k_values(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        mock_memory_storage: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_numpy_embedding: np.ndarray,
        k: int,
    ) -> None:
        """Test bridge discovery with different k values."""
        activated_memories = sample_memories_with_embeddings[:2]
        candidate_memories = sample_memories_with_embeddings[2:]

        mock_memory_storage.get_memories_by_level.return_value = candidate_memories

        bridges = bridge_discovery.discover_bridges(
            context=mock_numpy_embedding, activated=activated_memories, k=k
        )

        assert len(bridges) <= k

    def test_bridge_memory_attributes(
        self,
        bridge_discovery: SimpleBridgeDiscovery,
        mock_memory_storage: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_numpy_embedding: np.ndarray,
    ) -> None:
        """Test that bridge memories have all required attributes."""
        activated_memories = sample_memories_with_embeddings[:2]
        candidate_memories = sample_memories_with_embeddings[2:]

        mock_memory_storage.get_memories_by_level.return_value = candidate_memories

        bridges = bridge_discovery.discover_bridges(
            context=mock_numpy_embedding, activated=activated_memories, k=3
        )

        for bridge in bridges:
            assert hasattr(bridge, "memory")
            assert hasattr(bridge, "novelty_score")
            assert hasattr(bridge, "connection_potential")
            assert hasattr(bridge, "bridge_score")
            assert hasattr(bridge, "explanation")
            assert isinstance(bridge.memory, CognitiveMemory)
            assert 0.0 <= bridge.novelty_score <= 1.0
            assert 0.0 <= bridge.connection_potential <= 1.0
            assert 0.0 <= bridge.bridge_score <= 1.0
            assert isinstance(bridge.explanation, str)
