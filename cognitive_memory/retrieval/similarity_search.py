"""
Similarity-based memory search implementation.

This module implements cosine similarity-based retrieval across all
hierarchy levels with recency bias and configurable ranking strategies.
"""

import time
from datetime import datetime
from typing import Any

import torch
from loguru import logger

from ..core.interfaces import MemoryStorage
from ..core.memory import CognitiveMemory, SearchResult


class SimilaritySearch:
    """
    Similarity-based memory search using cosine similarity.

    Implements k-nearest neighbor search across hierarchy levels (L0, L1, L2)
    with recency bias for recent memory preference and configurable result
    ranking and filtering.
    """

    def __init__(
        self,
        memory_storage: MemoryStorage,
        recency_weight: float = 0.2,
        similarity_weight: float = 0.8,
        recency_decay_hours: float = 168.0,  # 1 week
    ):
        """
        Initialize similarity search.

        Args:
            memory_storage: Storage interface for memory access
            recency_weight: Weight for recency bias (0.0 to 1.0)
            similarity_weight: Weight for similarity score (0.0 to 1.0)
            recency_decay_hours: Hours for exponential recency decay
        """
        self.memory_storage = memory_storage
        self.recency_decay_hours = recency_decay_hours

        # Validate and normalize weights
        total_weight = recency_weight + similarity_weight
        if total_weight > 0:
            if abs(total_weight - 1.0) > 0.001:
                logger.debug(
                    "Normalizing similarity search weights to sum to 1.0",
                    original_recency=recency_weight,
                    original_similarity=similarity_weight,
                    total=total_weight,
                )
                self.recency_weight = recency_weight / total_weight
                self.similarity_weight = similarity_weight / total_weight
            else:
                self.recency_weight = recency_weight
                self.similarity_weight = similarity_weight
        else:
            logger.warning("Invalid zero weights, using defaults")
            self.recency_weight = 0.2
            self.similarity_weight = 0.8

    def search_memories(
        self,
        query_vector: torch.Tensor,
        k: int = 10,
        levels: list[int] | None = None,
        min_similarity: float = 0.1,
        include_recency_bias: bool = True,
    ) -> list[SearchResult]:
        """
        Search for similar memories across specified hierarchy levels.

        Args:
            query_vector: Query vector for similarity computation
            k: Number of top results to return
            levels: Hierarchy levels to search (None = all levels)
            min_similarity: Minimum similarity threshold
            include_recency_bias: Whether to apply recency bias

        Returns:
            List of SearchResult objects ranked by combined score
        """
        start_time = time.time()

        try:
            if levels is None:
                levels = [0, 1, 2]  # Search all hierarchy levels

            all_results = []

            # Search each hierarchy level
            for level in levels:
                level_memories = self.memory_storage.get_memories_by_level(level)
                level_results = self._search_level(
                    query_vector, level_memories, min_similarity, include_recency_bias
                )
                all_results.extend(level_results)

            # Sort by combined score and return top-k
            all_results.sort(
                key=lambda r: getattr(r, "combined_score", r.similarity_score),
                reverse=True,
            )
            top_results = all_results[:k]

            search_time_ms = (time.time() - start_time) * 1000

            logger.debug(
                "Similarity search completed",
                levels_searched=levels,
                total_candidates=len(all_results),
                returned_results=len(top_results),
                search_time_ms=search_time_ms,
            )

            return top_results

        except Exception as e:
            logger.error("Similarity search failed", error=str(e))
            return []

    def search_by_level(
        self,
        query_vector: torch.Tensor,
        level: int,
        k: int = 10,
        min_similarity: float = 0.1,
        include_recency_bias: bool = True,
    ) -> list[SearchResult]:
        """
        Search memories at a specific hierarchy level.

        Args:
            query_vector: Query vector for similarity computation
            level: Hierarchy level to search (0, 1, or 2)
            k: Number of top results to return
            min_similarity: Minimum similarity threshold
            include_recency_bias: Whether to apply recency bias

        Returns:
            List of SearchResult objects from the specified level
        """
        try:
            level_memories = self.memory_storage.get_memories_by_level(level)
            results = self._search_level(
                query_vector, level_memories, min_similarity, include_recency_bias
            )

            # Sort and return top-k
            results.sort(
                key=lambda r: getattr(r, "combined_score", r.similarity_score),
                reverse=True,
            )
            return results[:k]

        except Exception as e:
            logger.error("Level-specific search failed", level=level, error=str(e))
            return []

    def find_most_similar(
        self,
        query_vector: torch.Tensor,
        candidate_memories: list[CognitiveMemory],
        include_recency_bias: bool = True,
    ) -> SearchResult | None:
        """
        Find the most similar memory from a list of candidates.

        Args:
            query_vector: Query vector for similarity computation
            candidate_memories: List of candidate memories
            include_recency_bias: Whether to apply recency bias

        Returns:
            SearchResult with the most similar memory, or None if no candidates
        """
        if not candidate_memories:
            return None

        results = self._search_level(
            query_vector,
            candidate_memories,
            min_similarity=0.0,
            include_recency_bias=include_recency_bias,
        )

        if results:
            return max(
                results, key=lambda r: getattr(r, "combined_score", r.similarity_score)
            )

        return None

    def _search_level(
        self,
        query_vector: torch.Tensor,
        memories: list[CognitiveMemory],
        min_similarity: float,
        include_recency_bias: bool,
    ) -> list[SearchResult]:
        """
        Search memories at a specific level with similarity computation.

        Args:
            query_vector: Query vector for similarity computation
            memories: List of memories to search
            min_similarity: Minimum similarity threshold
            include_recency_bias: Whether to apply recency bias

        Returns:
            List of SearchResult objects above minimum similarity
        """
        results = []

        for memory in memories:
            if memory.cognitive_embedding is not None:
                # Compute cosine similarity
                similarity = self._compute_cosine_similarity(
                    query_vector, memory.cognitive_embedding
                )

                if similarity >= min_similarity:
                    # Calculate combined score with optional recency bias
                    if include_recency_bias:
                        recency_score = self._calculate_recency_score(memory)
                        combined_score = self._calculate_combined_score(
                            similarity, recency_score
                        )
                    else:
                        combined_score = similarity
                        recency_score = 0.0

                    # Create search result with pure similarity score
                    result = SearchResult(
                        memory=memory,
                        similarity_score=similarity,  # Pure similarity score
                        distance=1.0 - similarity,
                        metadata={
                            "pure_similarity": similarity,
                            "recency_score": recency_score,
                            "combined_score": combined_score,  # Store combined score in metadata
                            "hierarchy_level": memory.hierarchy_level,
                        },
                    )

                    # Add combined_score as an attribute for easy access
                    result.combined_score = combined_score
                    result.recency_score = recency_score

                    results.append(result)

        return results

    def _compute_cosine_similarity(
        self, vec1: torch.Tensor, vec2: torch.Tensor
    ) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        try:
            # Ensure tensors are on the same device and dtype
            if vec1.device != vec2.device:
                vec2 = vec2.to(vec1.device)
            if vec1.dtype != vec2.dtype:
                vec2 = vec2.to(vec1.dtype)

            # Flatten vectors for dot product
            vec1_flat = vec1.flatten()
            vec2_flat = vec2.flatten()

            # Compute cosine similarity
            dot_product = torch.dot(vec1_flat, vec2_flat)
            norm1 = torch.norm(vec1_flat)
            norm2 = torch.norm(vec2_flat)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)

            # Clamp to [0, 1] range and handle numerical issues
            similarity = torch.clamp(similarity, 0.0, 1.0)

            return float(similarity.item())

        except Exception as e:
            logger.warning("Cosine similarity computation failed", error=str(e))
            return 0.0

    def _calculate_recency_score(self, memory: CognitiveMemory) -> float:
        """
        Calculate recency score with exponential decay.

        Args:
            memory: Memory to calculate recency score for

        Returns:
            Recency score (0.0 to 1.0, higher = more recent)
        """
        try:
            # Use last_accessed if available, otherwise use timestamp
            reference_time = memory.last_accessed or memory.timestamp

            # CognitiveMemory always uses datetime objects for timestamps
            time_diff = datetime.now() - reference_time
            hours_elapsed = time_diff.total_seconds() / 3600

            # Exponential decay: score = exp(-hours_elapsed / decay_constant)
            decay_constant = self.recency_decay_hours
            recency_score = torch.exp(torch.tensor(-hours_elapsed / decay_constant))

            # Clamp to [0, 1] range
            return float(torch.clamp(recency_score, 0.0, 1.0).item())

        except Exception as e:
            logger.warning(
                "Recency score calculation failed", memory_id=memory.id, error=str(e)
            )
            return 0.5  # Default neutral recency score

    def _calculate_combined_score(self, similarity: float, recency: float) -> float:
        """
        Calculate combined score from similarity and recency scores.

        Args:
            similarity: Similarity score (0.0 to 1.0)
            recency: Recency score (0.0 to 1.0)

        Returns:
            Combined weighted score (0.0 to 1.0)
        """
        return self.similarity_weight * similarity + self.recency_weight * recency

    def get_search_config(self) -> dict[str, Any]:
        """
        Get current search configuration.

        Returns:
            Dictionary with search parameters
        """
        return {
            "recency_weight": self.recency_weight,
            "similarity_weight": self.similarity_weight,
            "recency_decay_hours": self.recency_decay_hours,
            "algorithm": "cosine_similarity_with_recency_bias",
        }

    def update_weights(self, recency_weight: float, similarity_weight: float) -> None:
        """
        Update search weights with validation.

        Args:
            recency_weight: New recency weight (0.0 to 1.0)
            similarity_weight: New similarity weight (0.0 to 1.0)
        """
        # Validate and normalize weights
        total_weight = recency_weight + similarity_weight
        if total_weight > 0:
            self.recency_weight = recency_weight / total_weight
            self.similarity_weight = similarity_weight / total_weight
        else:
            logger.warning("Invalid weights provided, keeping current configuration")
            return

        logger.debug(
            "Search weights updated",
            recency_weight=self.recency_weight,
            similarity_weight=self.similarity_weight,
        )

    def set_recency_decay(self, decay_hours: float) -> None:
        """
        Update recency decay parameter.

        Args:
            decay_hours: New decay time in hours
        """
        self.recency_decay_hours = max(1.0, decay_hours)  # Minimum 1 hour

        logger.debug(
            "Recency decay updated",
            decay_hours=self.recency_decay_hours,
        )

    def update_recency_decay(self, decay_hours: float) -> None:
        """
        Update recency decay parameter with validation.

        Args:
            decay_hours: New decay time in hours (must be positive)
        """
        if decay_hours > 0:
            self.recency_decay_hours = decay_hours
            logger.debug(
                "Recency decay updated",
                decay_hours=self.recency_decay_hours,
            )
        else:
            logger.warning("Invalid decay hours provided, keeping current value")
