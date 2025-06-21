"""
Core data structures for the cognitive memory system.

This module defines the fundamental data types used throughout the system,
including CognitiveMemory, search results, and activation results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

import numpy as np


@dataclass
class CognitiveMemory:
    """
    Core data structure representing a cognitive memory with multi-dimensional encoding.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    content: str = ""
    hierarchy_level: int = 0  # 0=concept, 1=context, 2=episode
    cognitive_embedding: np.ndarray | None = None
    dimensions: dict[str, np.ndarray] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    importance_score: float = 0.0
    parent_id: str | None = None
    memory_type: str = "episodic"  # 'episodic' or 'semantic'
    decay_rate: float = 0.1
    metadata: dict[str, Any] = field(default_factory=dict)

    # Date fields for LLM visibility and ranking
    created_date: datetime = field(
        default_factory=datetime.now
    )  # When memory was created
    modified_date: datetime | None = None  # When source content was last modified
    source_date: datetime | None = (
        None  # Original date of the source (e.g., commit date, document date)
    )

    # Additional attributes for storage compatibility
    strength: float = 1.0  # Memory strength (0.0-1.0)
    tags: list[str] | None = None  # Optional tags for categorization

    def update_access(self) -> None:
        """Update access timestamp and increment access count."""
        self.last_accessed = datetime.now()
        self.access_count += 1

    def calculate_activation_strength(self, context_similarity: float) -> float:
        """Calculate activation strength based on context similarity and memory properties."""
        base_strength = context_similarity

        # Boost based on access frequency
        frequency_boost = min(self.access_count * 0.1, 0.5)

        # Boost based on importance
        importance_boost = self.importance_score * 0.3

        # Apply temporal decay
        time_decay = self._calculate_time_decay()

        return (base_strength + frequency_boost + importance_boost) * time_decay

    def _calculate_time_decay(self) -> float:
        """Calculate decay factor based on time since last access."""
        time_diff = (
            datetime.now() - self.last_accessed
        ).total_seconds() / 86400  # days
        return max(0.1, 1.0 - (self.decay_rate * time_diff))

    def to_dict(self) -> dict[str, Any]:
        """Convert memory to dictionary for serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "hierarchy_level": self.hierarchy_level,
            "cognitive_embedding": self.cognitive_embedding.tolist()
            if self.cognitive_embedding is not None
            else None,
            "dimensions": {k: v.tolist() for k, v in self.dimensions.items()},
            "timestamp": self.timestamp.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "importance_score": self.importance_score,
            "parent_id": self.parent_id,
            "memory_type": self.memory_type,
            "decay_rate": self.decay_rate,
            "metadata": self.metadata,
            "created_date": self.created_date.isoformat(),
            "modified_date": self.modified_date.isoformat()
            if self.modified_date
            else None,
            "source_date": self.source_date.isoformat() if self.source_date else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CognitiveMemory":
        """Create memory from dictionary representation."""
        memory = cls(
            id=data["id"],
            content=data["content"],
            hierarchy_level=data.get("hierarchy_level", data.get("level", 0)),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            access_count=data["access_count"],
            importance_score=data["importance_score"],
            parent_id=data.get("parent_id"),
            memory_type=data.get("memory_type", "episodic"),
            decay_rate=data.get("decay_rate", 0.1),
            metadata=data.get("metadata", {}),
            created_date=datetime.fromisoformat(
                data.get("created_date", data["timestamp"])
            ),
            modified_date=datetime.fromisoformat(data["modified_date"])
            if data.get("modified_date")
            else None,
            source_date=datetime.fromisoformat(data["source_date"])
            if data.get("source_date")
            else None,
        )

        if data["cognitive_embedding"] is not None:
            memory.cognitive_embedding = np.array(data["cognitive_embedding"])

        memory.dimensions = {k: np.array(v) for k, v in data["dimensions"].items()}

        return memory


@dataclass
class SearchResult:
    """Result from vector similarity search."""

    memory: CognitiveMemory
    similarity_score: float
    distance: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    combined_score: float = 0.0
    recency_score: float = 0.0

    def __post_init__(self) -> None:
        if self.distance == 0.0:
            self.distance = 1.0 - self.similarity_score
        if self.combined_score == 0.0:
            self.combined_score = self.similarity_score

    @property
    def score(self) -> float:
        """Alias for similarity_score for compatibility."""
        return self.similarity_score


@dataclass
class ActivationResult:
    """Result from memory activation process."""

    core_memories: list[CognitiveMemory] = field(default_factory=list)
    peripheral_memories: list[CognitiveMemory] = field(default_factory=list)
    activation_strengths: dict[str, float] = field(default_factory=dict)
    total_activated: int = 0
    activation_time_ms: float = 0.0

    def __post_init__(self) -> None:
        self.total_activated = len(self.core_memories) + len(self.peripheral_memories)

    def get_all_memories(self) -> list[CognitiveMemory]:
        """Get all activated memories (core + peripheral)."""
        return self.core_memories + self.peripheral_memories

    def get_by_level(self, level: int) -> list[CognitiveMemory]:
        """Get activated memories by hierarchy level."""
        return [m for m in self.get_all_memories() if m.hierarchy_level == level]


@dataclass
class BridgeMemory:
    """Memory identified as a potential bridge connection."""

    memory: CognitiveMemory
    novelty_score: float
    connection_potential: float
    bridge_score: float
    explanation: str = ""

    def __post_init__(self) -> None:
        if not self.explanation:
            self.explanation = f"Bridge connects distant concepts with {self.connection_potential:.2f} potential"


@dataclass
class MemoryConnection:
    """Represents a connection between two memories."""

    source_id: str
    target_id: str
    connection_strength: float
    connection_type: str = "associative"
    created_at: datetime = field(default_factory=datetime.now)
    last_activated: datetime | None = None
    activation_count: int = 0

    def activate(self) -> None:
        """Mark this connection as activated."""
        self.last_activated = datetime.now()
        self.activation_count += 1

    def decay_strength(self, decay_rate: float = 0.01) -> None:
        """Apply temporal decay to connection strength."""
        if self.last_activated:
            days_since_activation = (datetime.now() - self.last_activated).days
            decay_factor = max(0.1, 1.0 - (decay_rate * days_since_activation))
            self.connection_strength *= decay_factor


@dataclass
class ConsolidationResult:
    """Result from memory consolidation process."""

    episodic_compressed: int = 0
    semantic_created: int = 0
    patterns_identified: int = 0
    connections_strengthened: int = 0
    consolidation_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "episodic_compressed": self.episodic_compressed,
            "semantic_created": self.semantic_created,
            "patterns_identified": self.patterns_identified,
            "connections_strengthened": self.connections_strengthened,
            "consolidation_time_ms": self.consolidation_time_ms,
        }


@dataclass
class SystemStats:
    """System statistics and metrics."""

    total_memories: int = 0
    memories_by_level: dict[int, int] = field(default_factory=dict)
    memories_by_type: dict[str, int] = field(default_factory=dict)
    total_connections: int = 0
    average_activation_time_ms: float = 0.0
    storage_size_mb: float = 0.0
    last_consolidation: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "total_memories": self.total_memories,
            "memories_by_level": self.memories_by_level,
            "memories_by_type": self.memories_by_type,
            "total_connections": self.total_connections,
            "average_activation_time_ms": self.average_activation_time_ms,
            "storage_size_mb": self.storage_size_mb,
            "last_consolidation": self.last_consolidation.isoformat()
            if self.last_consolidation
            else None,
        }
