"""
Cognitive system coordinator implementing the high-level CognitiveSystem interface.

This module provides the main facade for the cognitive memory system, coordinating
between encoding, storage, and retrieval subsystems through their abstract interfaces.
All dependencies are injected through interfaces to enable testing and component swapping.
"""

import time
import uuid
from datetime import datetime
from typing import Any

from loguru import logger

from .config import SystemConfig
from .interfaces import (
    ActivationEngine,
    BridgeDiscovery,
    CognitiveSystem,
    ConnectionGraph,
    EmbeddingProvider,
    MemoryStorage,
    VectorStorage,
)
from .memory import CognitiveMemory


class CognitiveMemorySystem(CognitiveSystem):
    """
    Main cognitive memory system coordinator.

    Implements the high-level CognitiveSystem interface by coordinating between
    encoding, storage, and retrieval subsystems. Uses dependency injection
    for all components to enable testing and component swapping.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_storage: VectorStorage,
        memory_storage: MemoryStorage,
        connection_graph: ConnectionGraph,
        activation_engine: ActivationEngine,
        bridge_discovery: BridgeDiscovery,
        config: SystemConfig,
    ):
        """
        Initialize cognitive memory system with injected dependencies.

        Args:
            embedding_provider: Interface for text encoding
            vector_storage: Interface for vector similarity storage
            memory_storage: Interface for memory persistence
            connection_graph: Interface for memory connections
            activation_engine: Interface for memory activation
            bridge_discovery: Interface for bridge discovery
            config: System configuration
        """
        self.embedding_provider = embedding_provider
        self.vector_storage = vector_storage
        self.memory_storage = memory_storage
        self.connection_graph = connection_graph
        self.activation_engine = activation_engine
        self.bridge_discovery = bridge_discovery
        self.config = config

        logger.info(
            "Cognitive memory system initialized",
            components=[
                "embedding_provider",
                "vector_storage",
                "memory_storage",
                "connection_graph",
                "activation_engine",
                "bridge_discovery",
            ],
        )

    def store_experience(self, text: str, context: dict[str, Any] | None = None) -> str:
        """
        Store a new experience and return its memory ID.

        Args:
            text: The experience text to store
            context: Optional context information

        Returns:
            str: Unique memory ID for the stored experience
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for experience storage")
            return ""

        try:
            # Generate unique memory ID
            memory_id = str(uuid.uuid4())
            current_time = datetime.now()

            # Encode the experience
            embedding = self.embedding_provider.encode(text)

            # Determine hierarchy level based on context or heuristics
            if context and "hierarchy_level" in context:
                hierarchy_level = context["hierarchy_level"]
                if hierarchy_level not in [0, 1, 2]:
                    logger.warning(
                        f"Invalid hierarchy level {hierarchy_level}, using L2"
                    )
                    hierarchy_level = 2
            else:
                hierarchy_level = self._determine_hierarchy_level(text)

            # Create cognitive memory object
            memory = CognitiveMemory(
                id=memory_id,
                content=text.strip(),
                memory_type="episodic" if hierarchy_level == 2 else "semantic",
                hierarchy_level=hierarchy_level,
                dimensions=context.get("dimensions", {}) if context else {},
                timestamp=current_time,
                strength=1.0,
                access_count=0,
            )

            # Attach the embedding to the memory object
            memory.cognitive_embedding = embedding

            # Store in memory persistence
            if not self.memory_storage.store_memory(memory):
                logger.error(
                    "Failed to store memory in persistence layer", memory_id=memory_id
                )
                return ""

            # Store in vector storage with metadata
            vector_metadata = {
                "memory_id": memory_id,
                "content": text.strip(),
                "memory_type": memory.memory_type,
                "hierarchy_level": hierarchy_level,
                "timestamp": current_time.timestamp(),
                "strength": 1.0,
                "access_count": 0,
            }

            # Add context metadata if provided
            if context:
                for key, value in context.items():
                    if key not in vector_metadata:
                        vector_metadata[key] = value

            self.vector_storage.store_vector(memory_id, embedding, vector_metadata)

            logger.info(
                "Experience stored successfully",
                memory_id=memory_id,
                text_length=len(text),
                hierarchy_level=hierarchy_level,
                memory_type=memory.memory_type,
            )

            return memory_id

        except Exception as e:
            logger.error(
                "Failed to store experience",
                text_preview=text[:100] + "..." if len(text) > 100 else text,
                error=str(e),
            )
            return ""

    def retrieve_memories(
        self,
        query: str,
        types: list[str] | None = None,
        max_results: int = 20,
    ) -> dict[str, list[CognitiveMemory]]:
        """
        Retrieve memories of specified types for a query.

        Args:
            query: Query text to search for
            types: List of memory types to retrieve ("core", "peripheral", "bridge")
            max_results: Maximum number of results to return

        Returns:
            Dict mapping memory types to lists of CognitiveMemory objects
        """
        if not query or not query.strip():
            logger.warning("Empty query provided for memory retrieval")
            return {"core": [], "peripheral": [], "bridge": []}

        if types is None:
            types = ["core", "peripheral", "bridge"]

        try:
            # Encode the query
            query_embedding = self.embedding_provider.encode(query.strip())

            results: dict[str, list[CognitiveMemory]] = {
                "core": [],
                "peripheral": [],
                "bridge": [],
            }

            # Activate memories if core or peripheral types requested
            if "core" in types or "peripheral" in types:
                activation_result = self.activation_engine.activate_memories(
                    context=query_embedding,
                    threshold=self.config.cognitive.activation_threshold,
                    max_activations=self.config.cognitive.max_activations,
                )

                if "core" in types:
                    # Take top scoring memories as core
                    results["core"] = activation_result.core_memories[
                        : max_results // 2
                    ]

                if "peripheral" in types:
                    # Take remaining activated memories as peripheral
                    results["peripheral"] = activation_result.peripheral_memories[
                        : max_results // 2
                    ]

            # Fallback to direct vector similarity search if no core/peripheral memories found
            if (
                ("core" in types or "peripheral" in types)
                and not results["core"]
                and not results["peripheral"]
            ):
                logger.debug(
                    "No memories activated, falling back to direct vector similarity search"
                )
                # Use max_activations to respect cognitive configuration
                fallback_limit = min(max_results, self.config.cognitive.max_activations)
                similarity_results = self.vector_storage.search_similar(
                    query_embedding, k=fallback_limit
                )
                # Split results between core and peripheral
                half = fallback_limit // 2 or 1
                top_results = similarity_results[:fallback_limit]
                if "core" in types:
                    core_memories = []
                    for result in top_results[:half]:
                        # Store similarity score in metadata for display
                        result.memory.metadata["similarity_score"] = (
                            result.similarity_score
                        )
                        core_memories.append(result.memory)
                    results["core"] = core_memories
                if "peripheral" in types:
                    peripheral_memories = []
                    for result in top_results[half:]:
                        # Store similarity score in metadata for display
                        result.memory.metadata["similarity_score"] = (
                            result.similarity_score
                        )
                        peripheral_memories.append(result.memory)
                    results["peripheral"] = peripheral_memories

            # Discover bridge memories if requested
            if "bridge" in types:
                # Use activated memories as input for bridge discovery
                activated_memories = []
                if results["core"]:
                    activated_memories.extend(results["core"])
                if results["peripheral"]:
                    activated_memories.extend(results["peripheral"])

                # If no activated memories, do basic similarity search
                if not activated_memories:
                    similarity_results = self.vector_storage.search_similar(
                        query_embedding, k=10
                    )
                    activated_memories = [
                        result.memory for result in similarity_results
                    ]

                if activated_memories:
                    bridge_memories = self.bridge_discovery.discover_bridges(
                        context=query_embedding,
                        activated=activated_memories,
                        k=self.config.cognitive.bridge_discovery_k,
                    )
                    results["bridge"] = [bridge.memory for bridge in bridge_memories]

            # Log retrieval statistics
            total_retrieved = sum(len(memories) for memories in results.values())
            logger.info(
                "Memory retrieval completed",
                query_length=len(query),
                requested_types=types,
                total_retrieved=total_retrieved,
                core_count=len(results["core"]),
                peripheral_count=len(results["peripheral"]),
                bridge_count=len(results["bridge"]),
            )

            return results

        except Exception as e:
            logger.error(
                "Failed to retrieve memories",
                query_preview=query[:100] + "..." if len(query) > 100 else query,
                types=types,
                error=str(e),
            )
            return {"core": [], "peripheral": [], "bridge": []}

    def _determine_hierarchy_level(self, text: str) -> int:
        """
        Determine hierarchy level based on content analysis.

        L0 (Concepts): Abstract ideas, principles, concepts, algorithms
        L1 (Contexts): Situational memories, workflow patterns, meetings
        L2 (Episodes): Specific experiences, events, activities

        Args:
            text: The experience text to analyze

        Returns:
            int: Hierarchy level (0, 1, or 2)
        """
        text_lower = text.lower().strip()

        # L0 indicators: abstract concepts, learning, principles
        concept_keywords = [
            "concept",
            "principle",
            "theory",
            "algorithm",
            "pattern",
            "methodology",
            "approach",
            "technique",
            "strategy",
            "framework",
            "architecture",
            "design pattern",
            "best practice",
            "paradigm",
            "learning",
            "understanding",
            "knowledge",
        ]

        # L1 indicators: contexts, workflows, meetings, planning
        context_keywords = [
            "meeting",
            "collaboration",
            "planning",
            "workflow",
            "process",
            "sprint",
            "project",
            "team",
            "discussion",
            "review",
            "session",
            "standup",
            "retrospective",
            "brainstorm",
            "about",
        ]

        # L2 indicators: specific activities and actions
        activity_keywords = [
            "working on",
            "debugging",
            "implementing",
            "fixing",
            "building",
            "coding",
            "testing",
            "deploying",
            "troubleshooting",
            "optimizing",
            "with",
            "using",
            "problems",
        ]

        # Count indicators
        concept_score = sum(1 for keyword in concept_keywords if keyword in text_lower)
        context_score = sum(1 for keyword in context_keywords if keyword in text_lower)
        activity_score = sum(
            1 for keyword in activity_keywords if keyword in text_lower
        )

        # Determine level based on highest scoring category
        if concept_score > context_score and concept_score > activity_score:
            return 0  # L0: Concepts
        elif context_score > activity_score:
            return 1  # L1: Contexts
        else:
            return 2  # L2: Episodes (default for specific activities)

    def consolidate_memories(self) -> dict[str, int]:
        """
        Trigger episodic to semantic memory consolidation.

        Returns:
            Dict with consolidation statistics
        """
        try:
            logger.info("Starting memory consolidation process")

            # Get all episodic memories from L2 (episodes)
            episodic_memories = self.memory_storage.get_memories_by_level(2)

            consolidation_stats = {
                "total_episodic": len(episodic_memories),
                "consolidated": 0,
                "failed": 0,
                "skipped": 0,
            }

            # Simple consolidation logic: promote frequently accessed memories
            current_time = datetime.now()

            for memory in episodic_memories:
                try:
                    # Check if memory meets consolidation criteria
                    age_seconds = (current_time - memory.timestamp).total_seconds()
                    if (
                        memory.access_count >= 5  # Accessed multiple times
                        and memory.strength > 0.8  # High strength
                        and age_seconds > 86400
                    ):  # At least 1 day old
                        # Create semantic version
                        semantic_memory = CognitiveMemory(
                            id=str(uuid.uuid4()),
                            content=memory.content,
                            memory_type="semantic",
                            hierarchy_level=1,  # Move to L1 (contexts)
                            dimensions=memory.dimensions,
                            timestamp=current_time,
                            strength=memory.strength
                            * 0.9,  # Slight decay during consolidation
                            access_count=0,  # Reset access count
                        )

                        # Store semantic memory
                        if self.memory_storage.store_memory(semantic_memory):
                            # Re-encode and store in vector storage
                            embedding = self.embedding_provider.encode(memory.content)
                            vector_metadata = {
                                "memory_id": semantic_memory.id,
                                "content": semantic_memory.content,
                                "memory_type": "semantic",
                                "hierarchy_level": 1,
                                "timestamp": current_time,
                                "strength": semantic_memory.strength,
                                "access_count": 0,
                            }

                            self.vector_storage.store_vector(
                                semantic_memory.id, embedding, vector_metadata
                            )

                            # Add connection from episodic to semantic
                            self.connection_graph.add_connection(
                                memory.id, semantic_memory.id, 0.9, "consolidation"
                            )

                            consolidation_stats["consolidated"] += 1
                            logger.debug(
                                "Memory consolidated",
                                episodic_id=memory.id,
                                semantic_id=semantic_memory.id,
                            )
                        else:
                            consolidation_stats["failed"] += 1
                    else:
                        consolidation_stats["skipped"] += 1

                except Exception as e:
                    logger.error(
                        "Failed to consolidate individual memory",
                        memory_id=memory.id,
                        error=str(e),
                    )
                    consolidation_stats["failed"] += 1

            logger.info("Memory consolidation completed", **consolidation_stats)

            return consolidation_stats

        except Exception as e:
            logger.error("Memory consolidation process failed", error=str(e))
            return {"total_episodic": 0, "consolidated": 0, "failed": 0, "skipped": 0}

    def get_memory_stats(self) -> dict[str, Any]:
        """
        Get system statistics and metrics.

        Returns:
            Dict containing various system statistics
        """
        try:
            # Initialize with proper typing
            memory_counts: dict[str, Any] = {}
            storage_stats: dict[str, Any] = {}

            stats: dict[str, Any] = {
                "timestamp": time.time(),
                "system_config": {
                    "activation_threshold": self.config.cognitive.activation_threshold,
                    "bridge_discovery_k": self.config.cognitive.bridge_discovery_k,
                    "max_activations": self.config.cognitive.max_activations,
                    "consolidation_threshold": self.config.cognitive.consolidation_threshold,
                },
                "memory_counts": memory_counts,
                "storage_stats": storage_stats,
                "error": None,
            }

            # Get memory counts by level
            try:
                for level in [0, 1, 2]:
                    memories = self.memory_storage.get_memories_by_level(level)
                    level_name = ["concepts", "contexts", "episodes"][level]
                    memory_counts[f"level_{level}_{level_name}"] = len(memories)
            except Exception as e:
                logger.warning("Failed to get memory counts", error=str(e))
                memory_counts["error"] = str(e)

            # Get vector storage statistics if available
            try:
                if hasattr(self.vector_storage, "get_storage_stats"):
                    # Call the method and update our stats dict
                    vector_stats = self.vector_storage.get_storage_stats()
                    storage_stats.update(vector_stats)
            except Exception as e:
                logger.warning("Failed to get storage stats", error=str(e))
                storage_stats["error"] = str(e)

            # Add embedding provider info if available
            try:
                if hasattr(self.embedding_provider, "get_model_info"):
                    embedding_info = self.embedding_provider.get_model_info()
                    stats["embedding_info"] = embedding_info
            except Exception as e:
                logger.debug("Embedding provider info not available", error=str(e))

            return stats

        except Exception as e:
            logger.error("Failed to generate system stats", error=str(e))
            return {
                "timestamp": time.time(),
                "error": str(e),
                "system_config": {},
                "memory_counts": {},
                "storage_stats": {},
            }


def create_cognitive_system(
    embedding_provider: EmbeddingProvider,
    vector_storage: VectorStorage,
    memory_storage: MemoryStorage,
    connection_graph: ConnectionGraph,
    activation_engine: ActivationEngine,
    bridge_discovery: BridgeDiscovery,
    config: SystemConfig,
) -> CognitiveMemorySystem:
    """
    Factory function to create a cognitive memory system.

    Args:
        embedding_provider: Interface for text encoding
        vector_storage: Interface for vector similarity storage
        memory_storage: Interface for memory persistence
        connection_graph: Interface for memory connections
        activation_engine: Interface for memory activation
        bridge_discovery: Interface for bridge discovery
        config: System configuration

    Returns:
        CognitiveMemorySystem: Configured system instance
    """
    return CognitiveMemorySystem(
        embedding_provider=embedding_provider,
        vector_storage=vector_storage,
        memory_storage=memory_storage,
        connection_graph=connection_graph,
        activation_engine=activation_engine,
        bridge_discovery=bridge_discovery,
        config=config,
    )
