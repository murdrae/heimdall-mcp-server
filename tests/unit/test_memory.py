"""
Unit tests for core memory data structures.
"""

from datetime import datetime, timedelta

import pytest
import torch

from cognitive_memory.core.memory import (
    ActivationResult,
    BridgeMemory,
    CognitiveMemory,
    ConsolidationResult,
    MemoryConnection,
    SearchResult,
    SystemStats,
)


class TestCognitiveMemory:
    """Test CognitiveMemory data structure."""

    def test_memory_creation(self):
        """Test creating a cognitive memory."""
        memory = CognitiveMemory(
            content="Test memory content", level=1, memory_type="episodic"
        )

        assert memory.content == "Test memory content"
        assert memory.level == 1
        assert memory.memory_type == "episodic"
        assert memory.access_count == 0
        assert memory.importance_score == 0.0
        assert isinstance(memory.timestamp, datetime)
        assert isinstance(memory.last_accessed, datetime)

    def test_memory_update_access(self):
        """Test updating memory access."""
        memory = CognitiveMemory(content="Test")
        initial_access = memory.last_accessed
        initial_count = memory.access_count

        memory.update_access()

        assert memory.access_count == initial_count + 1
        assert memory.last_accessed > initial_access

    def test_activation_strength_calculation(self):
        """Test activation strength calculation."""
        memory = CognitiveMemory(content="Test", access_count=5, importance_score=0.8)

        # Test with high context similarity
        strength = memory.calculate_activation_strength(0.9)
        assert strength > 0.9  # Should be boosted by access count and importance

        # Test with low context similarity
        strength = memory.calculate_activation_strength(0.1)
        assert 0.0 <= strength <= 1.0

    def test_time_decay(self):
        """Test temporal decay calculation."""
        memory = CognitiveMemory(content="Test")

        # Recent access should have minimal decay
        recent_decay = memory._calculate_time_decay()
        assert recent_decay > 0.9

        # Simulate old access
        memory.last_accessed = datetime.now() - timedelta(days=10)
        old_decay = memory._calculate_time_decay()
        assert old_decay < recent_decay

    def test_memory_serialization(self):
        """Test memory to/from dict conversion."""
        memory = CognitiveMemory(content="Test memory", level=2, memory_type="semantic")
        memory.dimensions = {
            "emotional": torch.tensor([0.1, 0.2, 0.3, 0.4]),
            "temporal": torch.tensor([0.5, 0.6, 0.7]),
        }
        memory.cognitive_embedding = torch.randn(512)

        # Convert to dict
        memory_dict = memory.to_dict()
        assert isinstance(memory_dict, dict)
        assert memory_dict["content"] == "Test memory"
        assert memory_dict["level"] == 2

        # Convert back from dict
        reconstructed = CognitiveMemory.from_dict(memory_dict)
        assert reconstructed.content == memory.content
        assert reconstructed.level == memory.level
        assert reconstructed.memory_type == memory.memory_type

        # Check dimensions
        for key in memory.dimensions:
            assert torch.allclose(memory.dimensions[key], reconstructed.dimensions[key])


class TestSearchResult:
    """Test SearchResult data structure."""

    def test_search_result_creation(self, sample_memory):
        """Test creating a search result."""
        result = SearchResult(memory=sample_memory, similarity_score=0.85)

        assert result.memory == sample_memory
        assert result.similarity_score == 0.85
        assert result.distance == pytest.approx(0.15)

    def test_custom_distance(self, sample_memory):
        """Test search result with custom distance."""
        result = SearchResult(memory=sample_memory, similarity_score=0.75, distance=0.3)

        assert result.similarity_score == 0.75
        assert result.distance == 0.3


class TestActivationResult:
    """Test ActivationResult data structure."""

    def test_activation_result_creation(self, sample_memories):
        """Test creating an activation result."""
        core_memories = sample_memories[:2]
        peripheral_memories = sample_memories[2:4]

        result = ActivationResult(
            core_memories=core_memories,
            peripheral_memories=peripheral_memories,
            activation_strengths={mem.id: 0.8 for mem in core_memories},
        )

        assert len(result.core_memories) == 2
        assert len(result.peripheral_memories) == 2
        assert result.total_activated == 4

    def test_get_all_memories(self, sample_memories):
        """Test getting all activated memories."""
        result = ActivationResult(
            core_memories=sample_memories[:2], peripheral_memories=sample_memories[2:]
        )

        all_memories = result.get_all_memories()
        assert len(all_memories) == len(sample_memories)

    def test_get_by_level(self, sample_memories):
        """Test getting memories by level."""
        result = ActivationResult(
            core_memories=sample_memories[:3], peripheral_memories=sample_memories[3:]
        )

        level_0_memories = result.get_by_level(0)
        level_1_memories = result.get_by_level(1)

        assert all(mem.level == 0 for mem in level_0_memories)
        assert all(mem.level == 1 for mem in level_1_memories)


class TestBridgeMemory:
    """Test BridgeMemory data structure."""

    def test_bridge_memory_creation(self, sample_memory):
        """Test creating a bridge memory."""
        bridge = BridgeMemory(
            memory=sample_memory,
            novelty_score=0.9,
            connection_potential=0.7,
            bridge_score=0.8,
        )

        assert bridge.memory == sample_memory
        assert bridge.novelty_score == 0.9
        assert bridge.connection_potential == 0.7
        assert bridge.bridge_score == 0.8
        assert "Bridge connects" in bridge.explanation

    def test_custom_explanation(self, sample_memory):
        """Test bridge memory with custom explanation."""
        explanation = "Custom bridge explanation"
        bridge = BridgeMemory(
            memory=sample_memory,
            novelty_score=0.8,
            connection_potential=0.6,
            bridge_score=0.7,
            explanation=explanation,
        )

        assert bridge.explanation == explanation


class TestMemoryConnection:
    """Test MemoryConnection data structure."""

    def test_connection_creation(self):
        """Test creating a memory connection."""
        connection = MemoryConnection(
            source_id="mem1",
            target_id="mem2",
            connection_strength=0.8,
            connection_type="causal",
        )

        assert connection.source_id == "mem1"
        assert connection.target_id == "mem2"
        assert connection.connection_strength == 0.8
        assert connection.connection_type == "causal"
        assert connection.activation_count == 0

    def test_connection_activation(self):
        """Test activating a connection."""
        connection = MemoryConnection(
            source_id="mem1", target_id="mem2", connection_strength=0.7
        )

        initial_count = connection.activation_count
        connection.activate()

        assert connection.activation_count == initial_count + 1
        assert connection.last_activated is not None

    def test_strength_decay(self):
        """Test connection strength decay."""
        connection = MemoryConnection(
            source_id="mem1", target_id="mem2", connection_strength=0.9
        )

        # Set last activation to simulate time passage
        connection.last_activated = datetime.now() - timedelta(days=5)
        initial_strength = connection.connection_strength

        connection.decay_strength(decay_rate=0.1)

        assert connection.connection_strength < initial_strength
        assert connection.connection_strength >= 0.1  # Should not go below minimum


class TestConsolidationResult:
    """Test ConsolidationResult data structure."""

    def test_consolidation_result_creation(self):
        """Test creating a consolidation result."""
        result = ConsolidationResult(
            episodic_compressed=10,
            semantic_created=3,
            patterns_identified=5,
            connections_strengthened=15,
            consolidation_time_ms=250.5,
        )

        assert result.episodic_compressed == 10
        assert result.semantic_created == 3
        assert result.patterns_identified == 5
        assert result.connections_strengthened == 15
        assert result.consolidation_time_ms == 250.5

    def test_to_dict(self):
        """Test converting consolidation result to dict."""
        result = ConsolidationResult(episodic_compressed=5, semantic_created=2)

        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert result_dict["episodic_compressed"] == 5
        assert result_dict["semantic_created"] == 2


class TestSystemStats:
    """Test SystemStats data structure."""

    def test_system_stats_creation(self):
        """Test creating system stats."""
        stats = SystemStats(
            total_memories=100,
            memories_by_level={0: 30, 1: 40, 2: 30},
            memories_by_type={"episodic": 60, "semantic": 40},
            total_connections=150,
        )

        assert stats.total_memories == 100
        assert stats.memories_by_level[0] == 30
        assert stats.memories_by_type["episodic"] == 60
        assert stats.total_connections == 150

    def test_stats_to_dict(self):
        """Test converting stats to dict."""
        stats = SystemStats(total_memories=50, average_activation_time_ms=125.5)

        stats_dict = stats.to_dict()
        assert isinstance(stats_dict, dict)
        assert stats_dict["total_memories"] == 50
        assert stats_dict["average_activation_time_ms"] == 125.5
