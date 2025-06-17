"""
Abstract interfaces for the cognitive memory system.

This module defines the core abstractions that enable component swapping,
testing, and scaling as outlined in the technical specification.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import torch

from .memory import CognitiveMemory, SearchResult, ActivationResult, BridgeMemory


class EmbeddingProvider(ABC):
    """Abstract interface for embedding models."""

    @abstractmethod
    def encode(self, text: str) -> torch.Tensor:
        """Encode a single text into a vector representation."""
        pass

    @abstractmethod
    def encode_batch(self, texts: List[str]) -> torch.Tensor:
        """Encode multiple texts into vector representations."""
        pass


class VectorStorage(ABC):
    """Abstract interface for vector databases."""

    @abstractmethod
    def store_vector(self, id: str, vector: torch.Tensor, metadata: Dict[str, Any]) -> None:
        """Store a vector with associated metadata."""
        pass

    @abstractmethod
    def search_similar(
        self,
        query_vector: torch.Tensor,
        k: int,
        filters: Optional[Dict] = None
    ) -> List[SearchResult]:
        """Search for similar vectors."""
        pass

    @abstractmethod
    def delete_vector(self, id: str) -> bool:
        """Delete a vector by ID."""
        pass

    @abstractmethod
    def update_vector(self, id: str, vector: torch.Tensor, metadata: Dict[str, Any]) -> bool:
        """Update an existing vector and its metadata."""
        pass


class ActivationEngine(ABC):
    """Abstract interface for memory activation."""

    @abstractmethod
    def activate_memories(
        self,
        context: torch.Tensor,
        threshold: float,
        max_activations: int = 50
    ) -> ActivationResult:
        """Activate memories based on context with spreading activation."""
        pass


class BridgeDiscovery(ABC):
    """Abstract interface for bridge discovery algorithms."""

    @abstractmethod
    def discover_bridges(
        self,
        context: torch.Tensor,
        activated: List[CognitiveMemory],
        k: int = 5
    ) -> List[BridgeMemory]:
        """Discover bridge memories that create novel connections."""
        pass


class DimensionExtractor(ABC):
    """Abstract interface for multi-dimensional feature extraction."""

    @abstractmethod
    def extract_dimensions(self, text: str) -> Dict[str, torch.Tensor]:
        """Extract emotional, temporal, contextual, and social dimensions."""
        pass


class MemoryStorage(ABC):
    """Abstract interface for memory persistence."""

    @abstractmethod
    def store_memory(self, memory: CognitiveMemory) -> bool:
        """Store a cognitive memory."""
        pass

    @abstractmethod
    def retrieve_memory(self, memory_id: str) -> Optional[CognitiveMemory]:
        """Retrieve a memory by ID."""
        pass

    @abstractmethod
    def update_memory(self, memory: CognitiveMemory) -> bool:
        """Update an existing memory."""
        pass

    @abstractmethod
    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        pass

    @abstractmethod
    def get_memories_by_level(self, level: int) -> List[CognitiveMemory]:
        """Get all memories at a specific hierarchy level."""
        pass


class ConnectionGraph(ABC):
    """Abstract interface for memory connection tracking."""

    @abstractmethod
    def add_connection(
        self,
        source_id: str,
        target_id: str,
        strength: float,
        connection_type: str = 'associative'
    ) -> bool:
        """Add a connection between two memories."""
        pass

    @abstractmethod
    def get_connections(
        self,
        memory_id: str,
        min_strength: float = 0.0
    ) -> List[CognitiveMemory]:
        """Get connected memories above minimum strength threshold."""
        pass

    @abstractmethod
    def update_connection_strength(
        self,
        source_id: str,
        target_id: str,
        new_strength: float
    ) -> bool:
        """Update the strength of an existing connection."""
        pass

    @abstractmethod
    def remove_connection(self, source_id: str, target_id: str) -> bool:
        """Remove a connection between memories."""
        pass


class CognitiveSystem(ABC):
    """High-level interface for the complete cognitive memory system."""

    @abstractmethod
    def store_experience(self, text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Store a new experience and return its memory ID."""
        pass

    @abstractmethod
    def retrieve_memories(
        self,
        query: str,
        types: List[str] = ['core', 'peripheral', 'bridge'],
        max_results: int = 20
    ) -> Dict[str, List[CognitiveMemory]]:
        """Retrieve memories of specified types for a query."""
        pass

    @abstractmethod
    def consolidate_memories(self) -> Dict[str, int]:
        """Trigger episodic to semantic memory consolidation."""
        pass

    @abstractmethod
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get system statistics and metrics."""
        pass