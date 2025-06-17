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

import torch
from pytest import fixture

from cognitive_memory.core.config import DatabaseConfig, QdrantConfig, SystemConfig
from cognitive_memory.core.memory import CognitiveMemory


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
        "emotional": torch.tensor(
            [0.2, 0.8, 0.1, 0.3]
        ),  # frustration, satisfaction, curiosity, stress
        "temporal": torch.tensor([0.7, 0.5, 0.3]),  # urgency, deadline, time_context
        "contextual": torch.tensor([0.9, 0.6, 0.4, 0.2, 0.1, 0.8]),  # context features
        "social": torch.tensor([0.3, 0.7, 0.5]),  # social dimensions
    }

    # Add sample cognitive embedding
    memory.cognitive_embedding = torch.randn(512)

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

        # Add random dimensions
        memory.dimensions = {
            "emotional": torch.rand(4),
            "temporal": torch.rand(3),
            "contextual": torch.rand(6),
            "social": torch.rand(3),
        }

        memory.cognitive_embedding = torch.randn(512)
        memories.append(memory)

    return memories


@fixture  # type: ignore[misc]
def mock_torch_embedding() -> torch.Tensor:
    """Create a mock embedding vector for testing."""
    return torch.randn(512)


class MockEmbeddingProvider:
    """Mock embedding provider for testing."""

    def encode(self, text: str) -> torch.Tensor:
        """Return a deterministic embedding based on text hash."""
        # Simple hash-based embedding for reproducible tests
        hash_val = hash(text) % 1000000
        torch.manual_seed(hash_val)
        return torch.randn(512)

    def encode_batch(self, texts: list[str]) -> torch.Tensor:
        """Return batch embeddings."""
        embeddings = [self.encode(text) for text in texts]
        return torch.stack(embeddings)


@fixture  # type: ignore[misc]
def mock_embedding_provider() -> MockEmbeddingProvider:
    """Create mock embedding provider for testing."""
    return MockEmbeddingProvider()


# Pytest markers for test organization
def pytest_configure(config: Any) -> None:
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "slow: marks tests as slow running")


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
        assert torch.allclose(memory1.dimensions[key], memory2.dimensions[key])

    # Compare embeddings if present
    if (
        memory1.cognitive_embedding is not None
        and memory2.cognitive_embedding is not None
    ):
        assert torch.allclose(memory1.cognitive_embedding, memory2.cognitive_embedding)

    if not ignore_timestamps:
        assert memory1.timestamp == memory2.timestamp
        assert memory1.last_accessed == memory2.last_accessed


def create_test_vector(size: int = 512, seed: int = 42) -> torch.Tensor:
    """Create a deterministic test vector."""
    torch.manual_seed(seed)
    return torch.randn(size)
