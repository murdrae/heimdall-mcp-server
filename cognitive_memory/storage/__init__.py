"""
Storage layer for cognitive memory system.

This package provides the complete storage architecture including:
- Qdrant vector storage with hierarchical collections
- SQLite persistence with migration-based schema management
- Dual memory system with episodic and semantic stores
- Memory consolidation and lifecycle management
"""

from .dual_memory import (
    DualMemorySystem,
    EpisodicMemoryStore,
    MemoryAccessPattern,
    MemoryConsolidation,
    MemoryType,
    SemanticMemoryStore,
    create_dual_memory_system,
)
from .qdrant_storage import (
    HierarchicalMemoryStorage,
    QdrantCollectionManager,
    VectorSearchEngine,
    create_hierarchical_storage,
)
from .sqlite_persistence import (
    ConnectionGraphStore,
    DatabaseManager,
    MemoryMetadataStore,
    create_sqlite_persistence,
)

__all__ = [
    "HierarchicalMemoryStorage",
    "QdrantCollectionManager",
    "VectorSearchEngine",
    "create_hierarchical_storage",
    "DatabaseManager",
    "MemoryMetadataStore",
    "ConnectionGraphStore",
    "create_sqlite_persistence",
    "DualMemorySystem",
    "EpisodicMemoryStore",
    "SemanticMemoryStore",
    "MemoryConsolidation",
    "MemoryType",
    "MemoryAccessPattern",
    "create_dual_memory_system",
]
