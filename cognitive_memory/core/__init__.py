"""Core cognitive memory system components."""

from .config import SystemConfig, get_config
from .interfaces import (
    ActivationEngine,
    BridgeDiscovery,
    CognitiveSystem,
    ConnectionGraph,
    DimensionExtractor,
    EmbeddingProvider,
    MemoryStorage,
    VectorStorage,
)
from .logging_setup import log_cognitive_event, setup_logging
from .memory import ActivationResult, BridgeMemory, CognitiveMemory, SearchResult

__all__ = [
    "SystemConfig",
    "get_config",
    "CognitiveMemory",
    "SearchResult",
    "ActivationResult",
    "BridgeMemory",
    "EmbeddingProvider",
    "VectorStorage",
    "ActivationEngine",
    "BridgeDiscovery",
    "DimensionExtractor",
    "MemoryStorage",
    "ConnectionGraph",
    "CognitiveSystem",
    "setup_logging",
    "log_cognitive_event",
]
