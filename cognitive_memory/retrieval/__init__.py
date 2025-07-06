"""
Retrieval subsystem for the cognitive memory system.

This module provides the foundational retrieval and activation mechanisms
including basic activation spreading, similarity-based search, and contextual
retrieval coordination.

The retrieval subsystem implements Phase 1 of the cognitive memory architecture
with simple but effective algorithms that will serve as the foundation for
more sophisticated cognitive processing in later phases.
"""

from typing import Any

from .basic_activation import BasicActivationEngine
from .contextual_retrieval import ContextualRetrieval, ContextualRetrievalResult
from .similarity_search import SimilaritySearch

__all__ = [
    # Core retrieval components
    "BasicActivationEngine",
    "SimilaritySearch",
    "ContextualRetrieval",
    # Result types
    "ContextualRetrievalResult",
]

# Version information
__version__ = "1.0.0"
__author__ = "Cognitive Memory System"
__description__ = "Basic retrieval and activation subsystem for cognitive memory"

# Component registry for easy access
RETRIEVAL_COMPONENTS = {
    "activation": BasicActivationEngine,
    "similarity": SimilaritySearch,
    "contextual": ContextualRetrieval,
}


def create_retrieval_system(
    memory_storage: Any,
    connection_graph: Any = None,
    activation_config: dict[str, Any] | None = None,
    similarity_config: dict[str, Any] | None = None,
) -> ContextualRetrieval:
    """
    Factory function to create a complete retrieval system.

    Args:
        memory_storage: MemoryStorage implementation
        connection_graph: ConnectionGraph implementation for activation
        activation_config: Configuration for BasicActivationEngine
        similarity_config: Configuration for SimilaritySearch

    Returns:
        ContextualRetrieval: Configured retrieval system
    """
    # Create activation engine if connection graph is provided
    activation_engine = None
    if connection_graph is not None:
        activation_kwargs = activation_config or {}
        activation_engine = BasicActivationEngine(
            memory_storage=memory_storage,
            connection_graph=connection_graph,
            **activation_kwargs,
        )

    # Create similarity search
    similarity_kwargs = similarity_config or {}
    similarity_search = SimilaritySearch(
        memory_storage=memory_storage, **similarity_kwargs
    )

    # Create contextual retrieval coordinator
    return ContextualRetrieval(
        memory_storage=memory_storage,
        activation_engine=activation_engine,
        similarity_search=similarity_search,
        connection_graph=connection_graph,
    )


def get_default_config() -> dict[str, Any]:
    """
    Get default configuration for retrieval components.

    Returns:
        dict: Default configuration parameters
    """
    return {
        "activation": {
            "core_threshold": 0.7,
            "peripheral_threshold": 0.5,
        },
        "similarity": {
            "recency_weight": 0.2,
            "similarity_weight": 0.8,
            "recency_decay_hours": 168.0,  # 1 week
        },
    }


# Convenience imports for backwards compatibility
def create_activation_engine(
    memory_storage: Any, connection_graph: Any, **kwargs: Any
) -> BasicActivationEngine:
    """Create BasicActivationEngine with default configuration."""
    return BasicActivationEngine(memory_storage, connection_graph, **kwargs)


def create_similarity_search(memory_storage: Any, **kwargs: Any) -> SimilaritySearch:
    """Create SimilaritySearch with default configuration."""
    return SimilaritySearch(memory_storage, **kwargs)
