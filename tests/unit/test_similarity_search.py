"""
Unit tests for SimilaritySearch.

Tests the cosine similarity-based memory retrieval with recency bias
and hierarchical search across memory levels.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
import torch

from cognitive_memory.core.interfaces import MemoryStorage
from cognitive_memory.core.memory import CognitiveMemory, SearchResult
from cognitive_memory.retrieval.similarity_search import SimilaritySearch


class TestSimilaritySearch:
    """Test SimilaritySearch implementation."""

    @pytest.fixture
    def mock_memory_storage(self) -> Mock:
        """Create mock memory storage."""
        mock = Mock(spec=MemoryStorage)
        return mock

    @pytest.fixture
    def sample_memories_with_embeddings(
        self, sample_memories: list[CognitiveMemory]
    ) -> list[CognitiveMemory]:
        """Create sample memories with embeddings and varied timestamps."""
        for i, memory in enumerate(sample_memories):
            torch.manual_seed(i)  # Deterministic embeddings
            memory.cognitive_embedding = torch.randn(512)
            # Vary timestamps for recency testing
            memory.timestamp = datetime.now() - timedelta(
                hours=i * 24
            )  # 0, 24, 48, ... hours ago
        return sample_memories

    @pytest.fixture
    def similarity_search(self, mock_memory_storage: Mock) -> SimilaritySearch:
        """Create SimilaritySearch with default configuration."""
        return SimilaritySearch(
            memory_storage=mock_memory_storage,
            recency_weight=0.2,
            similarity_weight=0.8,
            recency_decay_hours=168.0,  # 1 week
        )

    def test_init(self, mock_memory_storage: Mock) -> None:
        """Test SimilaritySearch initialization."""
        search = SimilaritySearch(
            memory_storage=mock_memory_storage,
            recency_weight=0.3,
            similarity_weight=0.7,
            recency_decay_hours=72.0,
        )

        assert search.memory_storage == mock_memory_storage
        assert search.recency_weight == 0.3
        assert search.similarity_weight == 0.7
        assert search.recency_decay_hours == 72.0

    def test_init_default_parameters(self, mock_memory_storage: Mock) -> None:
        """Test initialization with default parameters."""
        search = SimilaritySearch(memory_storage=mock_memory_storage)

        assert search.recency_weight == 0.2
        assert search.similarity_weight == 0.8
        assert search.recency_decay_hours == 168.0

    def test_init_weight_validation(self, mock_memory_storage: Mock, caplog) -> None:
        """Test weight validation during initialization."""
        # Should normalize weights if they don't sum to 1.0
        search = SimilaritySearch(
            memory_storage=mock_memory_storage,
            recency_weight=0.6,
            similarity_weight=0.6,  # Sum = 1.2, should be normalized
        )

        # Check weights are normalized
        total_weight = search.recency_weight + search.similarity_weight
        assert abs(total_weight - 1.0) < 0.001
        assert search.recency_weight == 0.5  # 0.6 / 1.2
        assert search.similarity_weight == 0.5  # 0.6 / 1.2

    def test_search_memories_basic(
        self,
        similarity_search: SimilaritySearch,
        mock_memory_storage: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_torch_embedding: torch.Tensor,
    ) -> None:
        """Test basic memory search functionality."""
        # Mock storage to return all memories for all levels
        mock_memory_storage.get_memories_by_level.return_value = (
            sample_memories_with_embeddings
        )

        results = similarity_search.search_memories(
            query_vector=mock_torch_embedding, k=3, min_similarity=0.0
        )

        assert isinstance(results, list)
        assert len(results) <= 3
        assert all(isinstance(r, SearchResult) for r in results)

        # Should be sorted by combined score (descending)
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].combined_score >= results[i + 1].combined_score

    def test_search_memories_no_memories(
        self,
        similarity_search: SimilaritySearch,
        mock_memory_storage: Mock,
        mock_torch_embedding: torch.Tensor,
    ) -> None:
        """Test search when no memories are available."""
        mock_memory_storage.get_memories_by_level.return_value = []

        results = similarity_search.search_memories(
            query_vector=mock_torch_embedding, k=5
        )

        assert results == []

    def test_search_memories_with_similarity_threshold(
        self,
        similarity_search: SimilaritySearch,
        mock_memory_storage: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_torch_embedding: torch.Tensor,
    ) -> None:
        """Test search with minimum similarity threshold."""
        mock_memory_storage.get_memories_by_level.return_value = (
            sample_memories_with_embeddings
        )

        results = similarity_search.search_memories(
            query_vector=mock_torch_embedding,
            k=10,
            min_similarity=0.9,  # Very high threshold
        )

        assert isinstance(results, list)
        # Should filter out low-similarity memories
        assert all(r.similarity_score >= 0.9 for r in results)

    def test_search_memories_specific_levels(
        self,
        similarity_search: SimilaritySearch,
        mock_memory_storage: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_torch_embedding: torch.Tensor,
    ) -> None:
        """Test search on specific hierarchy levels."""
        level_0_memories = [
            m for m in sample_memories_with_embeddings if m.hierarchy_level == 0
        ]
        level_1_memories = [
            m for m in sample_memories_with_embeddings if m.hierarchy_level == 1
        ]

        # Mock storage to return different memories for different levels
        def get_memories_side_effect(level):
            if level == 0:
                return level_0_memories
            elif level == 1:
                return level_1_memories
            else:
                return []

        mock_memory_storage.get_memories_by_level.side_effect = get_memories_side_effect

        results = similarity_search.search_memories(
            query_vector=mock_torch_embedding, k=5, levels=[0, 1]
        )

        assert isinstance(results, list)
        # Should only return memories from requested levels
        result_levels = {r.memory.hierarchy_level for r in results}
        assert result_levels.issubset({0, 1})

    def test_search_memories_no_embeddings(
        self,
        similarity_search: SimilaritySearch,
        mock_memory_storage: Mock,
        sample_memories: list[CognitiveMemory],  # Without embeddings
        mock_torch_embedding: torch.Tensor,
    ) -> None:
        """Test search with memories that have no embeddings."""
        # Ensure memories have no embeddings
        for memory in sample_memories:
            memory.cognitive_embedding = None

        mock_memory_storage.get_memories_by_level.return_value = sample_memories

        results = similarity_search.search_memories(
            query_vector=mock_torch_embedding, k=5
        )

        assert results == []

    def test_compute_cosine_similarity(
        self, similarity_search: SimilaritySearch
    ) -> None:
        """Test cosine similarity computation."""
        vec1 = torch.tensor([1.0, 2.0, 3.0])
        vec2 = torch.tensor([2.0, 4.0, 6.0])  # Same direction

        similarity = similarity_search._compute_cosine_similarity(vec1, vec2)
        assert isinstance(similarity, float)
        assert 0.99 < similarity <= 1.0

    def test_compute_cosine_similarity_orthogonal(
        self, similarity_search: SimilaritySearch
    ) -> None:
        """Test cosine similarity with orthogonal vectors."""
        vec1 = torch.tensor([1.0, 0.0])
        vec2 = torch.tensor([0.0, 1.0])

        similarity = similarity_search._compute_cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(0.0, abs=1e-6)

    def test_compute_cosine_similarity_zero_vector(
        self, similarity_search: SimilaritySearch
    ) -> None:
        """Test cosine similarity with zero vector."""
        vec1 = torch.tensor([1.0, 2.0])
        vec2 = torch.tensor([0.0, 0.0])

        similarity = similarity_search._compute_cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_calculate_recency_score(self, similarity_search: SimilaritySearch) -> None:
        """Test recency score calculation."""
        # Recent memory - control both timestamp and last_accessed
        now = datetime.now()
        recent_memory = CognitiveMemory(content="Recent", timestamp=now)
        recent_memory.last_accessed = now  # Explicitly set to now
        recency_score = similarity_search._calculate_recency_score(recent_memory)
        assert 0.9 < recency_score <= 1.0

        # Old memory - control both timestamp and last_accessed
        old_time = now - timedelta(days=7)
        old_memory = CognitiveMemory(content="Old", timestamp=old_time)
        old_memory.last_accessed = old_time  # Explicitly set to old time
        old_recency_score = similarity_search._calculate_recency_score(old_memory)
        assert old_recency_score < recency_score

    def test_calculate_recency_score_very_old(
        self, similarity_search: SimilaritySearch
    ) -> None:
        """Test recency score for very old memories."""
        now = datetime.now()
        very_old_time = now - timedelta(days=365)  # 1 year old
        very_old_memory = CognitiveMemory(content="Very old", timestamp=very_old_time)
        very_old_memory.last_accessed = very_old_time  # Explicitly set to old time
        recency_score = similarity_search._calculate_recency_score(very_old_memory)
        assert 0.0 <= recency_score < 0.1

    def test_calculate_combined_score(
        self, similarity_search: SimilaritySearch
    ) -> None:
        """Test combined score calculation."""
        similarity = 0.8
        recency = 0.6

        combined = similarity_search._calculate_combined_score(similarity, recency)

        # Should be weighted average based on configured weights
        expected = (
            similarity_search.similarity_weight * similarity
            + similarity_search.recency_weight * recency
        )
        assert combined == pytest.approx(expected, abs=1e-6)

    def test_calculate_combined_score_boundary_values(
        self, similarity_search: SimilaritySearch
    ) -> None:
        """Test combined score with boundary values."""
        # Maximum values
        max_combined = similarity_search._calculate_combined_score(1.0, 1.0)
        assert max_combined == 1.0

        # Minimum values
        min_combined = similarity_search._calculate_combined_score(0.0, 0.0)
        assert min_combined == 0.0

    def test_get_search_config(self, similarity_search: SimilaritySearch) -> None:
        """Test get_search_config method."""
        config = similarity_search.get_search_config()

        assert isinstance(config, dict)
        assert config["recency_weight"] == 0.2
        assert config["similarity_weight"] == 0.8
        assert config["recency_decay_hours"] == 168.0
        assert "algorithm" in config

    def test_update_weights(self, similarity_search: SimilaritySearch) -> None:
        """Test updating search weights."""
        similarity_search.update_weights(recency_weight=0.4, similarity_weight=0.6)

        assert similarity_search.recency_weight == 0.4
        assert similarity_search.similarity_weight == 0.6

    def test_update_weights_normalization(
        self, similarity_search: SimilaritySearch
    ) -> None:
        """Test weight normalization during update."""
        similarity_search.update_weights(
            recency_weight=0.8,
            similarity_weight=0.4,  # Sum = 1.2
        )

        # Should be normalized
        total = similarity_search.recency_weight + similarity_search.similarity_weight
        assert abs(total - 1.0) < 0.001

    def test_update_weights_zero_total(
        self, similarity_search: SimilaritySearch
    ) -> None:
        """Test weight update with zero total weight."""
        original_recency = similarity_search.recency_weight
        original_similarity = similarity_search.similarity_weight

        similarity_search.update_weights(recency_weight=0.0, similarity_weight=0.0)

        # Should keep original weights
        assert similarity_search.recency_weight == original_recency
        assert similarity_search.similarity_weight == original_similarity

    def test_update_recency_decay(self, similarity_search: SimilaritySearch) -> None:
        """Test updating recency decay parameter."""
        similarity_search.update_recency_decay(72.0)
        assert similarity_search.recency_decay_hours == 72.0

    def test_update_recency_decay_negative(
        self, similarity_search: SimilaritySearch
    ) -> None:
        """Test updating recency decay with negative value."""
        original_decay = similarity_search.recency_decay_hours

        similarity_search.update_recency_decay(-10.0)

        # Should keep original value for negative input
        assert similarity_search.recency_decay_hours == original_decay

    def test_search_error_handling(
        self,
        similarity_search: SimilaritySearch,
        mock_memory_storage: Mock,
        mock_torch_embedding: torch.Tensor,
    ) -> None:
        """Test error handling during search."""
        # Make storage throw exception
        mock_memory_storage.get_memories_by_level.side_effect = Exception(
            "Storage error"
        )

        results = similarity_search.search_memories(
            query_vector=mock_torch_embedding, k=5
        )

        # Should return empty list gracefully
        assert results == []

    @pytest.mark.parametrize("k", [1, 5, 10, 100])
    def test_search_memories_different_k_values(
        self,
        similarity_search: SimilaritySearch,
        mock_memory_storage: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_torch_embedding: torch.Tensor,
        k: int,
    ) -> None:
        """Test search with different k values."""
        mock_memory_storage.get_memories_by_level.return_value = (
            sample_memories_with_embeddings
        )

        results = similarity_search.search_memories(
            query_vector=mock_torch_embedding, k=k
        )

        assert len(results) <= min(k, len(sample_memories_with_embeddings))

    @pytest.mark.parametrize("levels", [None, [0], [1], [2], [0, 1], [0, 1, 2]])
    def test_search_memories_different_levels(
        self,
        similarity_search: SimilaritySearch,
        mock_memory_storage: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_torch_embedding: torch.Tensor,
        levels: list[int],
    ) -> None:
        """Test search across different hierarchy levels."""
        mock_memory_storage.get_memories_by_level.return_value = (
            sample_memories_with_embeddings
        )

        results = similarity_search.search_memories(
            query_vector=mock_torch_embedding, k=5, levels=levels
        )

        assert isinstance(results, list)
        if levels and results:
            result_levels = {r.memory.level for r in results}
            assert result_levels.issubset(set(levels))

    def test_search_result_attributes(
        self,
        similarity_search: SimilaritySearch,
        mock_memory_storage: Mock,
        sample_memories_with_embeddings: list[CognitiveMemory],
        mock_torch_embedding: torch.Tensor,
    ) -> None:
        """Test that search results have all required attributes."""
        mock_memory_storage.get_memories_by_level.return_value = (
            sample_memories_with_embeddings
        )

        results = similarity_search.search_memories(
            query_vector=mock_torch_embedding, k=3
        )

        for result in results:
            assert hasattr(result, "memory")
            assert hasattr(result, "similarity_score")
            assert hasattr(result, "recency_score")
            assert hasattr(result, "combined_score")
            assert isinstance(result.memory, CognitiveMemory)
            assert 0.0 <= result.similarity_score <= 1.0
            assert 0.0 <= result.recency_score <= 1.0
            assert 0.0 <= result.combined_score <= 1.0
