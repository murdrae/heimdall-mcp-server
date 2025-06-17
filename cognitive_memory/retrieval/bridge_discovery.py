"""
Simple bridge discovery implementation using distance inversion.

This module implements bridge discovery that identifies memories with low
direct similarity to the query but high connection potential through
activated memories, enabling serendipitous connections.
"""

import time

import torch
from loguru import logger

from ..core.interfaces import BridgeDiscovery, MemoryStorage
from ..core.memory import BridgeMemory, CognitiveMemory


class SimpleBridgeDiscovery(BridgeDiscovery):
    """
    Simple bridge discovery using distance inversion algorithm.

    Identifies memories with low direct similarity to query (high novelty)
    but high connection potential through activated memories, following
    the algorithm specification from the technical document.
    """

    def __init__(
        self,
        memory_storage: MemoryStorage,
        novelty_weight: float = 0.6,
        connection_weight: float = 0.4,
        max_candidates: int = 100,
        min_novelty: float = 0.3,
    ):
        """
        Initialize simple bridge discovery.

        Args:
            memory_storage: Storage interface for memory access
            novelty_weight: Weight for novelty score (0.0 to 1.0)
            connection_weight: Weight for connection potential (0.0 to 1.0)
            max_candidates: Maximum candidate memories to consider
            min_novelty: Minimum novelty threshold
        """
        self.memory_storage = memory_storage
        self.novelty_weight = novelty_weight
        self.connection_weight = connection_weight
        self.max_candidates = max_candidates
        self.min_novelty = min_novelty

        # Validate weights
        total_weight = novelty_weight + connection_weight
        if abs(total_weight - 1.0) > 0.001:
            logger.warning(
                "Bridge discovery weights don't sum to 1.0",
                novelty_weight=novelty_weight,
                connection_weight=connection_weight,
                total=total_weight,
            )

    def discover_bridges(
        self, context: torch.Tensor, activated: list[CognitiveMemory], k: int = 5
    ) -> list[BridgeMemory]:
        """
        Discover bridge memories that create novel connections.

        Implementation follows the algorithm specification:
        1. Get non-activated memories as candidates
        2. Calculate novelty score (inverse similarity to query)
        3. Calculate connection potential to activated memories
        4. Compute bridge score: (novelty * 0.6) + (connection_potential * 0.4)
        5. Return top-k bridge memories

        Args:
            context: Query context vector
            activated: List of currently activated memories
            k: Number of bridge memories to return

        Returns:
            List of BridgeMemory objects ranked by bridge score
        """
        start_time = time.time()

        try:
            # Get activated memory IDs for exclusion
            activated_ids = {memory.id for memory in activated}

            # Get candidate memories (non-activated)
            candidates = self._get_candidate_memories(activated_ids)

            if not candidates:
                logger.debug("No candidate memories found for bridge discovery")
                return []

            # Compute bridge scores for candidates
            bridge_scores = self._compute_bridge_scores(context, candidates, activated)

            # Sort by bridge score and return top-k
            bridge_scores.sort(key=lambda x: x[1], reverse=True)
            top_bridges = bridge_scores[:k]

            # Create BridgeMemory objects
            bridge_memories = []
            for candidate, bridge_score in top_bridges:
                novelty = self._calculate_novelty_score(context, candidate)
                connection_potential = self._calculate_connection_potential(
                    candidate, activated
                )

                bridge_memory = BridgeMemory(
                    memory=candidate,
                    novelty_score=novelty,
                    connection_potential=connection_potential,
                    bridge_score=bridge_score,
                    explanation=self._generate_bridge_explanation(
                        candidate, novelty, connection_potential
                    ),
                )
                bridge_memories.append(bridge_memory)

            discovery_time_ms = (time.time() - start_time) * 1000

            logger.debug(
                "Bridge discovery completed",
                candidates_evaluated=len(candidates),
                bridges_found=len(bridge_memories),
                discovery_time_ms=discovery_time_ms,
            )

            return bridge_memories

        except Exception as e:
            logger.error("Bridge discovery failed", error=str(e))
            return []

    def _get_candidate_memories(self, activated_ids: set[str]) -> list[CognitiveMemory]:
        """
        Get candidate memories excluding already activated ones.

        Args:
            activated_ids: Set of activated memory IDs to exclude

        Returns:
            List of candidate memories for bridge discovery
        """
        candidates = []

        # Get memories from all hierarchy levels
        for level in [0, 1, 2]:
            level_memories = self.memory_storage.get_memories_by_level(level)

            for memory in level_memories:
                if (
                    memory.id not in activated_ids
                    and memory.cognitive_embedding is not None
                ):
                    candidates.append(memory)

        # Limit candidates for performance
        if len(candidates) > self.max_candidates:
            # Sort by importance/strength and take top candidates
            candidates.sort(key=lambda m: m.importance_score, reverse=True)
            candidates = candidates[: self.max_candidates]

        logger.debug(f"Found {len(candidates)} candidate memories for bridge discovery")
        return candidates

    def _compute_bridge_scores(
        self,
        context: torch.Tensor,
        candidates: list[CognitiveMemory],
        activated: list[CognitiveMemory],
    ) -> list[tuple[CognitiveMemory, float]]:
        """
        Compute bridge scores for candidate memories.

        Args:
            context: Query context vector
            candidates: Candidate memories
            activated: Currently activated memories

        Returns:
            List of (memory, bridge_score) tuples
        """
        bridge_scores = []

        for candidate in candidates:
            # Calculate novelty score (inverse similarity to query)
            novelty = self._calculate_novelty_score(context, candidate)

            # Skip if novelty is too low
            if novelty < self.min_novelty:
                continue

            # Calculate connection potential to activated memories
            connection_potential = self._calculate_connection_potential(
                candidate, activated
            )

            # Compute bridge score using weights from algorithm specification
            bridge_score = (
                self.novelty_weight * novelty
                + self.connection_weight * connection_potential
            )

            bridge_scores.append((candidate, bridge_score))

        return bridge_scores

    def _calculate_novelty_score(
        self, context: torch.Tensor, memory: CognitiveMemory
    ) -> float:
        """
        Calculate novelty score as inverse similarity to query.

        Args:
            context: Query context vector
            memory: Memory to calculate novelty for

        Returns:
            Novelty score (0.0 to 1.0, higher = more novel)
        """
        if memory.cognitive_embedding is None:
            return 0.0

        try:
            similarity = self._compute_cosine_similarity(
                context, memory.cognitive_embedding
            )
            novelty = 1.0 - similarity  # Inverse similarity
            return max(0.0, min(1.0, novelty))

        except Exception as e:
            logger.warning(
                "Novelty calculation failed", memory_id=memory.id, error=str(e)
            )
            return 0.0

    def _calculate_connection_potential(
        self, candidate: CognitiveMemory, activated: list[CognitiveMemory]
    ) -> float:
        """
        Calculate connection potential to activated memories.

        Args:
            candidate: Candidate memory
            activated: List of activated memories

        Returns:
            Connection potential score (0.0 to 1.0)
        """
        if not activated or candidate.cognitive_embedding is None:
            return 0.0

        try:
            max_similarity = 0.0

            for activated_memory in activated:
                if activated_memory.cognitive_embedding is not None:
                    similarity = self._compute_cosine_similarity(
                        candidate.cognitive_embedding,
                        activated_memory.cognitive_embedding,
                    )
                    max_similarity = max(max_similarity, similarity)

            return max_similarity

        except Exception as e:
            logger.warning(
                "Connection potential calculation failed",
                candidate_id=candidate.id,
                error=str(e),
            )
            return 0.0

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

    def _generate_bridge_explanation(
        self, memory: CognitiveMemory, novelty: float, connection_potential: float
    ) -> str:
        """
        Generate human-readable explanation for bridge discovery.

        Args:
            memory: Bridge memory
            novelty: Novelty score
            connection_potential: Connection potential score

        Returns:
            Explanation string
        """
        explanation_parts = []

        # Novelty description
        if novelty > 0.8:
            explanation_parts.append("highly novel concept")
        elif novelty > 0.6:
            explanation_parts.append("moderately novel concept")
        else:
            explanation_parts.append("somewhat novel concept")

        # Connection description
        if connection_potential > 0.7:
            explanation_parts.append("strong connections to activated memories")
        elif connection_potential > 0.5:
            explanation_parts.append("moderate connections to activated memories")
        else:
            explanation_parts.append("weak connections to activated memories")

        # Memory type context
        level_descriptions = {0: "conceptual", 1: "contextual", 2: "episodic"}
        memory_type = level_descriptions.get(memory.hierarchy_level, "unknown")

        explanation = (
            f"Bridge memory ({memory_type} level): {explanation_parts[0]} with "
            f"{explanation_parts[1]} (novelty: {novelty:.2f}, "
            f"connection: {connection_potential:.2f})"
        )

        return explanation

    def get_discovery_config(self) -> dict:
        """
        Get current bridge discovery configuration.

        Returns:
            Dictionary with discovery parameters
        """
        return {
            "novelty_weight": self.novelty_weight,
            "connection_weight": self.connection_weight,
            "max_candidates": self.max_candidates,
            "min_novelty": self.min_novelty,
        }

    def update_weights(self, novelty_weight: float, connection_weight: float) -> None:
        """
        Update bridge discovery weights with validation.

        Args:
            novelty_weight: New novelty weight (0.0 to 1.0)
            connection_weight: New connection weight (0.0 to 1.0)
        """
        # Validate and normalize weights
        total_weight = novelty_weight + connection_weight
        if total_weight > 0:
            self.novelty_weight = novelty_weight / total_weight
            self.connection_weight = connection_weight / total_weight
        else:
            logger.warning("Invalid weights provided, keeping current configuration")
            return

        logger.debug(
            "Bridge discovery weights updated",
            novelty_weight=self.novelty_weight,
            connection_weight=self.connection_weight,
        )

    def update_parameters(
        self, max_candidates: int | None = None, min_novelty: float | None = None
    ) -> None:
        """
        Update bridge discovery parameters.

        Args:
            max_candidates: New maximum candidates limit
            min_novelty: New minimum novelty threshold
        """
        if max_candidates is not None:
            self.max_candidates = max(1, max_candidates)

        if min_novelty is not None:
            self.min_novelty = max(0.0, min(1.0, min_novelty))

        logger.debug(
            "Bridge discovery parameters updated",
            max_candidates=self.max_candidates,
            min_novelty=self.min_novelty,
        )
