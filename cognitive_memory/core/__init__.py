"""Core cognitive memory system components."""

from .config import SystemConfig, get_config
from .memory import CognitiveMemory, SearchResult, ActivationResult, BridgeMemory
from .interfaces import (
    EmbeddingProvider, VectorStorage, ActivationEngine, BridgeDiscovery,
    DimensionExtractor, MemoryStorage, ConnectionGraph, CognitiveSystem
)
from .logging_setup import setup_logging, log_cognitive_event

__all__ = [
    'SystemConfig',
    'get_config',
    'CognitiveMemory',
    'SearchResult', 
    'ActivationResult',
    'BridgeMemory',
    'EmbeddingProvider',
    'VectorStorage',
    'ActivationEngine',
    'BridgeDiscovery',
    'DimensionExtractor',
    'MemoryStorage',
    'ConnectionGraph',
    'CognitiveSystem',
    'setup_logging',
    'log_cognitive_event'
]