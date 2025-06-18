"""
Cognitive Memory System

A cognitive memory system for Large Language Models implementing true cognitive
processing through associative thinking, serendipitous connections, and emergent insights.
"""

from . import core, encoding, retrieval, storage
from .core import (
    ActivationResult,
    BridgeMemory,
    CognitiveMemory,
    SearchResult,
    get_config,
    log_cognitive_event,
    setup_logging,
)

# Git analysis module (when available)
try:
    from . import git_analysis

    __all__ = [
        "ActivationResult",
        "BridgeMemory",
        "CognitiveMemory",
        "SearchResult",
        "get_config",
        "log_cognitive_event",
        "setup_logging",
        "core",
        "encoding",
        "retrieval",
        "storage",
        "git_analysis",
    ]
except ImportError:
    __all__ = [
        "ActivationResult",
        "BridgeMemory",
        "CognitiveMemory",
        "SearchResult",
        "get_config",
        "log_cognitive_event",
        "setup_logging",
        "core",
        "encoding",
        "retrieval",
        "storage",
    ]
