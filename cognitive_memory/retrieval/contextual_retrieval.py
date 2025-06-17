"""
Contextual retrieval coordinator implementation.

This module provides the high-level coordination of activation, similarity search,
and bridge discovery to create a unified retrieval system that categorizes
memories and aggregates results.
"""

import time
from typing import Any

import torch
from loguru import logger

from ..core.interfaces import ActivationEngine, BridgeDiscovery, MemoryStorage
from ..core.memory import ActivationResult, BridgeMemory, CognitiveMemory, SearchResult
from .basic_activation import BasicActivationEngine
from .bridge_discovery import SimpleBridgeDiscovery
from .similarity_search import SimilaritySearch


class ContextualRetrievalResult:
    """
    Result from contextual retrieval containing categorized memories.

    Organizes retrieval results into core memories (highly relevant),
    peripheral memories (moderately relevant), and bridge memories
    (serendipitous connections).
    """

    def __init__(
        self,
        core_memories: list[CognitiveMemory],
        peripheral_memories: list[CognitiveMemory],
        bridge_memories: list[BridgeMemory],
        activation_result: ActivationResult | None = None,
        similarity_results: list[SearchResult] | None = None,
        retrieval_time_ms: float = 0.0,
        context_metadata: dict[str, Any] | None = None,
    ):
        """
        Initialize contextual retrieval result.

        Args:
            core_memories: Highly relevant core memories
            peripheral_memories: Moderately relevant peripheral memories
            bridge_memories: Serendipitous bridge connections
            activation_result: Original activation result
            similarity_results: Original similarity search results
            retrieval_time_ms: Total retrieval time in milliseconds
            context_metadata: Additional context information
        """
        self.core_memories = core_memories
        self.peripheral_memories = peripheral_memories
        self.bridge_memories = bridge_memories
        self.activation_result = activation_result
        self.similarity_results = similarity_results
        self.retrieval_time_ms = retrieval_time_ms
        self.context_metadata = context_metadata or {}

        # Calculate totals
        self.total_memories = len(core_memories) + len(peripheral_memories)
        self.total_bridges = len(bridge_memories)

    def get_all_memories(self) -> list[CognitiveMemory]:
        """Get all memories (core + peripheral)."""
        return self.core_memories + self.peripheral_memories

    def get_memories_by_level(self, level: int) -> list[CognitiveMemory]:
        """Get all memories at a specific hierarchy level."""
        all_memories = self.get_all_memories()
        return [m for m in all_memories if m.hierarchy_level == level]

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            "core_memories": [m.to_dict() for m in self.core_memories],
            "peripheral_memories": [m.to_dict() for m in self.peripheral_memories],
            "bridge_memories": [
                {
                    "memory": b.memory.to_dict(),
                    "novelty_score": b.novelty_score,
                    "connection_potential": b.connection_potential,
                    "bridge_score": b.bridge_score,
                    "explanation": b.explanation,
                }
                for b in self.bridge_memories
            ],
            "total_memories": self.total_memories,
            "total_bridges": self.total_bridges,
            "retrieval_time_ms": self.retrieval_time_ms,
            "context_metadata": self.context_metadata,
        }


class ContextualRetrieval:
    """
    High-level retrieval coordinator that integrates activation, similarity search,
    and bridge discovery into a unified contextual retrieval system.

    Provides the main interface for memory retrieval with automatic result
    categorization and ranking.
    """

    memory_storage: MemoryStorage
    activation_engine: ActivationEngine | None
    similarity_search: SimilaritySearch
    bridge_discovery: BridgeDiscovery

    def __init__(
        self,
        memory_storage: MemoryStorage,
        activation_engine: ActivationEngine | None = None,
        similarity_search: SimilaritySearch | None = None,
        bridge_discovery: BridgeDiscovery | None = None,
        connection_graph: Any | None = None,  # ConnectionGraph interface
    ):
        """
        Initialize contextual retrieval coordinator.

        Args:
            memory_storage: Storage interface for memory access
            activation_engine: Optional activation engine (created if None)
            similarity_search: Optional similarity search (created if None)
            bridge_discovery: Optional bridge discovery (created if None)
            connection_graph: Optional connection graph for activation
        """
        self.memory_storage = memory_storage

        # Initialize retrieval components
        if activation_engine is not None:
            self.activation_engine = activation_engine
        elif connection_graph is not None:
            self.activation_engine = BasicActivationEngine(
                memory_storage, connection_graph
            )
        else:
            logger.warning("No activation engine or connection graph provided")
            self.activation_engine = None

        self.similarity_search = similarity_search or SimilaritySearch(memory_storage)
        self.bridge_discovery = bridge_discovery or SimpleBridgeDiscovery(
            memory_storage
        )

    def retrieve_memories(
        self,
        query_context: torch.Tensor,
        max_core: int = 10,
        max_peripheral: int = 15,
        max_bridges: int = 5,
        activation_threshold: float = 0.6,
        similarity_threshold: float = 0.3,
        use_activation: bool = True,
        use_similarity: bool = True,
        use_bridges: bool = True,
    ) -> ContextualRetrievalResult:
        """
        Retrieve memories using integrated activation, similarity, and bridge discovery.

        Args:
            query_context: Query context vector
            max_core: Maximum core memories to return
            max_peripheral: Maximum peripheral memories to return
            max_bridges: Maximum bridge memories to return
            activation_threshold: Threshold for activation spreading
            similarity_threshold: Threshold for similarity search
            use_activation: Whether to use activation spreading
            use_similarity: Whether to use similarity search
            use_bridges: Whether to use bridge discovery

        Returns:
            ContextualRetrievalResult with categorized memories
        """
        start_time = time.time()

        try:
            # Phase 1: Activation spreading (if enabled and available)
            activation_result = None
            activated_memories = []

            if use_activation and self.activation_engine is not None:
                activation_result = self.activation_engine.activate_memories(
                    query_context, activation_threshold, max_core + max_peripheral
                )
                activated_memories = activation_result.get_all_memories()

                logger.debug(
                    "Activation completed",
                    core_count=len(activation_result.core_memories),
                    peripheral_count=len(activation_result.peripheral_memories),
                )

            # Phase 2: Similarity search (if enabled)
            similarity_results = []
            similarity_memories = []

            if use_similarity:
                similarity_results = self.similarity_search.search_memories(
                    query_context,
                    k=max_core + max_peripheral,
                    min_similarity=similarity_threshold,
                )
                similarity_memories = [r.memory for r in similarity_results]

                logger.debug(
                    f"Similarity search found {len(similarity_results)} memories"
                )

            # Phase 3: Merge and categorize memories
            core_memories, peripheral_memories = self._merge_and_categorize_memories(
                activated_memories,
                similarity_memories,
                query_context,
                max_core,
                max_peripheral,
            )

            # Phase 4: Bridge discovery (if enabled)
            bridge_memories = []

            if use_bridges:
                all_retrieved = core_memories + peripheral_memories
                if (
                    all_retrieved
                ):  # Only search for bridges if we have retrieved memories
                    bridge_memories = self.bridge_discovery.discover_bridges(
                        query_context, all_retrieved, max_bridges
                    )

                    logger.debug(
                        f"Bridge discovery found {len(bridge_memories)} bridges"
                    )

            # Create result
            retrieval_time_ms = (time.time() - start_time) * 1000

            result = ContextualRetrievalResult(
                core_memories=core_memories,
                peripheral_memories=peripheral_memories,
                bridge_memories=bridge_memories,
                activation_result=activation_result,
                similarity_results=similarity_results,
                retrieval_time_ms=retrieval_time_ms,
                context_metadata={
                    "activation_threshold": activation_threshold,
                    "similarity_threshold": similarity_threshold,
                    "used_activation": use_activation
                    and self.activation_engine is not None,
                    "used_similarity": use_similarity,
                    "used_bridges": use_bridges,
                },
            )

            logger.info(
                "Contextual retrieval completed",
                core_memories=len(core_memories),
                peripheral_memories=len(peripheral_memories),
                bridge_memories=len(bridge_memories),
                retrieval_time_ms=retrieval_time_ms,
            )

            return result

        except Exception as e:
            logger.error("Contextual retrieval failed", error=str(e))
            return ContextualRetrievalResult(
                [], [], [], retrieval_time_ms=(time.time() - start_time) * 1000
            )

    def _merge_and_categorize_memories(
        self,
        activated_memories: list[CognitiveMemory],
        similarity_memories: list[CognitiveMemory],
        query_context: torch.Tensor,
        max_core: int,
        max_peripheral: int,
    ) -> tuple[list[CognitiveMemory], list[CognitiveMemory]]:
        """
        Merge memories from activation and similarity search, then categorize.

        Args:
            activated_memories: Memories from activation spreading
            similarity_memories: Memories from similarity search
            query_context: Original query context for scoring
            max_core: Maximum core memories
            max_peripheral: Maximum peripheral memories

        Returns:
            Tuple of (core_memories, peripheral_memories)
        """
        # Combine and deduplicate memories
        memory_map = {}
        memory_scores = {}

        # Add activated memories with their activation strengths
        for memory in activated_memories:
            if memory.cognitive_embedding is not None:
                similarity = self._compute_cosine_similarity(
                    query_context, memory.cognitive_embedding
                )
                score = memory.calculate_activation_strength(similarity)

                memory_map[memory.id] = memory
                memory_scores[memory.id] = score

        # Add similarity memories, updating scores if already present
        for memory in similarity_memories:
            if memory.cognitive_embedding is not None:
                similarity = self._compute_cosine_similarity(
                    query_context, memory.cognitive_embedding
                )
                score = memory.calculate_activation_strength(similarity)

                if memory.id in memory_map:
                    # Take the higher score
                    memory_scores[memory.id] = max(memory_scores[memory.id], score)
                else:
                    memory_map[memory.id] = memory
                    memory_scores[memory.id] = score

        # Sort memories by score
        sorted_memories = sorted(
            memory_map.values(),
            key=lambda m: memory_scores.get(m.id, 0.0),
            reverse=True,
        )

        # Categorize as core or peripheral based on score thresholds
        core_memories: list[CognitiveMemory] = []
        peripheral_memories: list[CognitiveMemory] = []

        for memory in sorted_memories:
            score = memory_scores.get(memory.id, 0.0)

            if score >= 0.7 and len(core_memories) < max_core:
                core_memories.append(memory)
            elif score >= 0.4 and len(peripheral_memories) < max_peripheral:
                peripheral_memories.append(memory)
            elif len(core_memories) < max_core:
                # Fill core if we have space and no more high-scoring memories
                core_memories.append(memory)
            elif len(peripheral_memories) < max_peripheral:
                # Fill peripheral if we have space
                peripheral_memories.append(memory)
            else:
                # Both categories are full
                break

        return core_memories, peripheral_memories

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

    def get_retrieval_stats(self) -> dict[str, Any]:
        """
        Get retrieval system statistics and configuration.

        Returns:
            Dictionary with system stats and configuration
        """
        stats: dict[str, Any] = {
            "has_activation_engine": self.activation_engine is not None,
            "has_similarity_search": self.similarity_search is not None,
            "has_bridge_discovery": self.bridge_discovery is not None,
        }

        # Add component configurations
        if self.activation_engine and hasattr(
            self.activation_engine, "get_activation_config"
        ):
            stats["activation_config"] = self.activation_engine.get_activation_config()

        if self.similarity_search and hasattr(
            self.similarity_search, "get_search_config"
        ):
            stats["similarity_config"] = self.similarity_search.get_search_config()

        if self.bridge_discovery and hasattr(
            self.bridge_discovery, "get_discovery_config"
        ):
            stats["bridge_config"] = self.bridge_discovery.get_discovery_config()

        return stats
