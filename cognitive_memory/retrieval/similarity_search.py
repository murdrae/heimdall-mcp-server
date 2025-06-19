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
        cognitive_config: Any = None,  # CognitiveConfig for date-based ranking
    ):
        """
        Initialize similarity search.

        Args:
            memory_storage: Storage interface for memory access
            recency_weight: Weight for recency bias (0.0 to 1.0)
            similarity_weight: Weight for similarity score (0.0 to 1.0)
            recency_decay_hours: Hours for exponential recency decay
            cognitive_config: Configuration for date-based ranking parameters
        """
        self.memory_storage = memory_storage
        self.recency_decay_hours = recency_decay_hours
        self.cognitive_config = cognitive_config

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

            # Apply date-based secondary ranking if enabled
            if self.cognitive_config and hasattr(self.cognitive_config, 'similarity_closeness_threshold'):
                all_results = self._apply_date_based_ranking(all_results)

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

    def _apply_date_based_ranking(self, results: list[SearchResult]) -> list[SearchResult]:
        """
        Apply date-based secondary ranking to closely-scored memories.

        Groups results by similarity score clusters and applies modification
        date recency as a secondary ranking factor for close scores.

        Args:
            results: List of search results to re-rank

        Returns:
            Re-ranked list of search results
        """
        if not results or not self.cognitive_config:
            return results

        threshold = self.cognitive_config.similarity_closeness_threshold
        modification_weight = self.cognitive_config.modification_date_weight
        
        # Group results into similarity clusters
        clusters = self._group_by_similarity_threshold(results, threshold)
        
        final_results = []
        for cluster in clusters:
            if len(cluster) > 1:
                # Apply secondary ranking by modification date for clusters with multiple results
                for result in cluster:
                    mod_recency = self._calculate_modification_recency_score(result.memory)
                    
                    # Blend existing combined score with modification recency
                    original_score = getattr(result, "combined_score", result.similarity_score)
                    result.combined_score = self._blend_with_modification_score(
                        original_score, mod_recency, modification_weight
                    )
                
                # Re-sort cluster by new combined score
                cluster.sort(key=lambda r: r.combined_score, reverse=True)
            
            final_results.extend(cluster)
        
        return final_results

    def _group_by_similarity_threshold(
        self, results: list[SearchResult], threshold: float
    ) -> list[list[SearchResult]]:
        """
        Group results into clusters based on similarity score closeness.

        Args:
            results: List of search results to group
            threshold: Similarity threshold for grouping

        Returns:
            List of result clusters
        """
        if not results:
            return []
        
        # Sort by similarity score first
        sorted_results = sorted(results, key=lambda r: r.similarity_score, reverse=True)
        
        clusters = []
        current_cluster = [sorted_results[0]]
        
        for i in range(1, len(sorted_results)):
            current_result = sorted_results[i]
            last_in_cluster = current_cluster[-1]
            
            # Check if within threshold of the cluster
            score_diff = abs(last_in_cluster.similarity_score - current_result.similarity_score)
            
            if score_diff <= threshold:
                current_cluster.append(current_result)
            else:
                # Start new cluster
                clusters.append(current_cluster)
                current_cluster = [current_result]
        
        # Add the last cluster
        if current_cluster:
            clusters.append(current_cluster)
        
        return clusters

    def _calculate_modification_recency_score(self, memory: CognitiveMemory) -> float:
        """
        Calculate modification recency score based on when content was last modified.

        Args:
            memory: Memory to calculate modification recency for

        Returns:
            Modification recency score (0.0 to 1.0, higher = more recent)
        """
        try:
            # Get the modification date from the memory
            modification_date = self._get_memory_modification_date(memory)
            
            if modification_date is None:
                return 0.0  # No modification date available
            
            # Calculate days since modification
            time_diff = datetime.now() - modification_date
            days_elapsed = time_diff.total_seconds() / 86400
            
            # Exponential decay based on configured decay period
            decay_days = self.cognitive_config.modification_recency_decay_days
            recency_score = torch.exp(torch.tensor(-days_elapsed / decay_days))
            
            # Clamp to [0, 1] range
            return float(torch.clamp(recency_score, 0.0, 1.0).item())
        
        except Exception as e:
            logger.warning(
                "Modification recency score calculation failed", 
                memory_id=memory.id, 
                error=str(e)
            )
            return 0.0  # Default neutral score

    def _get_memory_modification_date(self, memory: CognitiveMemory) -> datetime | None:
        """
        Extract modification date from memory.

        Tries multiple sources in order of preference:
        1. memory.modified_date (explicit field)
        2. memory.source_date (source content date)
        3. memory.metadata['file_modified_date'] (legacy field)
        4. memory.timestamp (fallback)

        Args:
            memory: Memory to extract modification date from

        Returns:
            Modification datetime or None if not available
        """
        # Try explicit modified_date field first
        if hasattr(memory, 'modified_date') and memory.modified_date:
            return memory.modified_date
        
        # Try source_date field
        if hasattr(memory, 'source_date') and memory.source_date:
            return memory.source_date
        
        # Try metadata fields for backward compatibility
        if memory.metadata:
            # Check for file modification date in metadata
            file_mod_date_str = memory.metadata.get('file_modified_date')
            if file_mod_date_str:
                try:
                    return datetime.fromisoformat(file_mod_date_str)
                except (ValueError, TypeError):
                    pass
            
            # Check for git commit dates
            latest_commit_date_str = memory.metadata.get('latest_commit_date')
            if latest_commit_date_str:
                try:
                    return datetime.fromisoformat(latest_commit_date_str)
                except (ValueError, TypeError):
                    pass
        
        # Fallback to memory timestamp
        return memory.timestamp

    def _blend_with_modification_score(
        self, original_score: float, modification_score: float, modification_weight: float
    ) -> float:
        """
        Blend original similarity score with modification recency score.

        Args:
            original_score: Original combined score (similarity + access recency)
            modification_score: Modification recency score
            modification_weight: Weight for modification score blending

        Returns:
            Blended score incorporating modification recency
        """
        # Use weighted average approach to prevent ceiling effects
        # This ensures that both high and low similarity scores can benefit from modification recency
        mod_weight = min(modification_weight, 0.5)  # Cap at 50% influence
        
        # Calculate weighted average instead of addition to avoid ceiling effects
        blended_score = (1.0 - mod_weight) * original_score + mod_weight * modification_score
        
        # For very close similarity scores, add a small boost for modification recency
        # This ensures recent memories get a slight edge when similarities are nearly identical
        if modification_score > 0.5:  # Only boost if modification is reasonably recent
            boost = mod_weight * 0.1 * modification_score  # Small boost
            blended_score += boost
        
        # Ensure result stays within reasonable bounds
        return min(1.0, blended_score)
