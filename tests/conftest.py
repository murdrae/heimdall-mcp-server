"""
Pytest configuration and fixtures for cognitive memory system tests.

This module provides common test fixtures and utilities for unit and integration tests.
"""

import shutil
import tempfile
from collections.abc import Generator
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
from pytest import fixture

from cognitive_memory.core.config import DatabaseConfig, QdrantConfig, SystemConfig
from cognitive_memory.core.memory import CognitiveMemory
from cognitive_memory.factory import create_test_system
from tests.factory_utils import (
    MockActivationEngine,
    MockBridgeDiscovery,
    MockCognitiveSystem,
    MockConnectionGraph,
    MockEmbeddingProvider,
    MockMemoryStorage,
    MockVectorStorage,
)
from tests.test_utils import setup_deterministic_testing


@fixture  # type: ignore[misc]
def temp_dir() -> Generator[Path]:
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


@fixture  # type: ignore[misc]
def test_config(temp_dir: Path) -> SystemConfig:
    """Create test configuration with temporary paths."""
    return replace(
        SystemConfig.from_env(),
        database=DatabaseConfig(
            path=str(temp_dir / "test_cognitive_memory.db"),
            backup_interval_hours=1,
            enable_wal_mode=False,  # Disable WAL for tests
        ),
        qdrant=QdrantConfig(url="http://localhost:6333", timeout=5),
    )


@fixture  # type: ignore[misc]
def sample_memory() -> CognitiveMemory:
    """Create a sample cognitive memory for testing."""
    memory = CognitiveMemory(
        content="This is a test memory about learning Python programming",
        hierarchy_level=0,
        memory_type="episodic",
    )

    # Add sample dimensions
    memory.dimensions = {
        "emotional": np.array(
            [0.2, 0.8, 0.1, 0.3]
        ),  # frustration, satisfaction, curiosity, stress
        "temporal": np.array([0.7, 0.5, 0.3]),  # urgency, deadline, time_context
        "contextual": np.array([0.9, 0.6, 0.4, 0.2, 0.1, 0.8]),  # context features
        "social": np.array([0.3, 0.7, 0.5]),  # social dimensions
    }

    # Add sample cognitive embedding (deterministic)
    np.random.seed(42)
    memory.cognitive_embedding = np.random.randn(512)

    return memory


@fixture  # type: ignore[misc]
def sample_memories() -> list[CognitiveMemory]:
    """Create multiple sample memories for testing."""
    memories = []

    contents = [
        "Learning about machine learning algorithms",
        "Debugging a complex Python function",
        "Reading documentation about neural networks",
        "Writing unit tests for the memory system",
        "Understanding cognitive architectures",
    ]

    for i, content in enumerate(contents):
        memory = CognitiveMemory(
            content=content,
            hierarchy_level=i % 3,  # Distribute across levels
            memory_type="episodic" if i % 2 == 0 else "semantic",
        )

        # Add deterministic dimensions
        np.random.seed(42 + i)  # Different seed per memory
        memory.dimensions = {
            "emotional": np.random.rand(4),
            "temporal": np.random.rand(3),
            "contextual": np.random.rand(6),
            "social": np.random.rand(3),
        }

        memory.cognitive_embedding = np.random.randn(512)
        memories.append(memory)

    return memories


@fixture  # type: ignore[misc]
def mock_numpy_embedding() -> np.ndarray:
    """Create a mock embedding vector for testing."""
    np.random.seed(42)
    return np.random.randn(512)


@fixture  # type: ignore[misc]
def mock_embedding_provider() -> MockEmbeddingProvider:
    """Create mock embedding provider for testing."""
    return MockEmbeddingProvider()


# Pytest markers for test organization
def pytest_configure(config: Any) -> None:
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end tests")
    config.addinivalue_line("markers", "slow: marks tests as slow running")


def pytest_runtest_setup(item: Any) -> None:
    """Set up deterministic behavior before each test."""
    setup_deterministic_testing(seed=42)


# Test utilities
def assert_memory_equal(
    memory1: CognitiveMemory, memory2: CognitiveMemory, ignore_timestamps: bool = True
) -> None:
    """Assert that two memories are equal, optionally ignoring timestamps."""
    assert memory1.id == memory2.id
    assert memory1.content == memory2.content
    assert memory1.hierarchy_level == memory2.hierarchy_level
    assert memory1.memory_type == memory2.memory_type
    assert memory1.access_count == memory2.access_count
    assert memory1.importance_score == memory2.importance_score
    assert memory1.parent_id == memory2.parent_id
    assert memory1.decay_rate == memory2.decay_rate

    # Compare dimensions
    for key in memory1.dimensions:
        assert key in memory2.dimensions
        assert np.allclose(memory1.dimensions[key], memory2.dimensions[key])

    # Compare embeddings if present
    if (
        memory1.cognitive_embedding is not None
        and memory2.cognitive_embedding is not None
    ):
        assert np.allclose(memory1.cognitive_embedding, memory2.cognitive_embedding)

    if not ignore_timestamps:
        assert memory1.timestamp == memory2.timestamp
        assert memory1.last_accessed == memory2.last_accessed


def create_test_vector(size: int = 512, seed: int = 42) -> np.ndarray:
    """Create a deterministic test vector."""
    np.random.seed(seed)
    return np.random.randn(size)


# Factory testing fixtures


@fixture  # type: ignore[misc]
def mock_embedding_provider_factory() -> MockEmbeddingProvider:
    """Create mock embedding provider for factory testing."""
    return MockEmbeddingProvider()


@fixture  # type: ignore[misc]
def mock_vector_storage_factory() -> MockVectorStorage:
    """Create mock vector storage for factory testing."""
    return MockVectorStorage()


@fixture  # type: ignore[misc]
def mock_memory_storage_factory() -> MockMemoryStorage:
    """Create mock memory storage for factory testing."""
    return MockMemoryStorage()


@fixture  # type: ignore[misc]
def mock_connection_graph_factory() -> MockConnectionGraph:
    """Create mock connection graph for factory testing."""
    return MockConnectionGraph()


@fixture  # type: ignore[misc]
def mock_activation_engine_factory() -> MockActivationEngine:
    """Create mock activation engine for factory testing."""
    return MockActivationEngine()


@fixture  # type: ignore[misc]
def mock_bridge_discovery_factory() -> MockBridgeDiscovery:
    """Create mock bridge discovery for factory testing."""
    return MockBridgeDiscovery()


@fixture  # type: ignore[misc]
def mock_cognitive_system_factory() -> MockCognitiveSystem:
    """Create mock cognitive system for factory testing."""
    return MockCognitiveSystem()


@fixture  # type: ignore[misc]
def factory_test_system(test_config: SystemConfig) -> Any:
    """Create test system using factory with mock components."""
    return create_test_system(
        embedding_provider=MockEmbeddingProvider(),
        vector_storage=MockVectorStorage(),
        memory_storage=MockMemoryStorage(),
        connection_graph=MockConnectionGraph(),
        activation_engine=MockActivationEngine(),
        bridge_discovery=MockBridgeDiscovery(),
        config=test_config,
    )
