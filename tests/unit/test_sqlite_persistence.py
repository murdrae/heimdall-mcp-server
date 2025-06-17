"""
Unit tests for SQLite persistence layer.

Tests the DatabaseManager, MemoryMetadataStore, and ConnectionGraphStore
components with proper schema migration handling.
"""

import tempfile
import time
from datetime import datetime
from pathlib import Path

import pytest

from cognitive_memory.core.memory import CognitiveMemory
from cognitive_memory.storage.sqlite_persistence import (
    ConnectionGraphStore,
    DatabaseManager,
    MemoryMetadataStore,
    create_sqlite_persistence,
)


class TestDatabaseManager:
    """Test DatabaseManager functionality."""

    def test_database_initialization(self):
        """Test database creation and schema initialization."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db_manager = DatabaseManager(db_path)

            # Check that database file was created
            assert Path(db_path).exists()

            # Check that all tables exist
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                tables = {row[0] for row in cursor.fetchall()}

                expected_tables = {
                    "schema_migrations",
                    "memories",
                    "memory_connections",
                    "bridge_cache",
                    "retrieval_stats",
                }

                assert expected_tables.issubset(tables)

        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_migration_tracking(self):
        """Test that migrations are properly tracked."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db_manager = DatabaseManager(db_path)

            with db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Check that migrations were recorded
                cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
                migrations = [row[0] for row in cursor.fetchall()]

                expected_migrations = [
                    "001_memories",
                    "002_memory_connections",
                    "003_bridge_cache",
                    "004_retrieval_stats",
                ]

                assert expected_migrations == migrations

        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_connection_management(self):
        """Test database connection management."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db_manager = DatabaseManager(db_path)

            # Test connection context manager
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM memories")
                result = cursor.fetchone()
                assert result[0] == 0

        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_database_stats(self):
        """Test database statistics collection."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db_manager = DatabaseManager(db_path)
            stats = db_manager.get_database_stats()

            assert "memories_count" in stats
            assert "memory_connections_count" in stats
            assert "bridge_cache_count" in stats
            assert "retrieval_stats_count" in stats
            assert "database_size_bytes" in stats

            assert all(
                isinstance(count, int)
                for key, count in stats.items()
                if key.endswith("_count")
            )
            assert stats["database_size_bytes"] > 0

        finally:
            Path(db_path).unlink(missing_ok=True)


class TestMemoryMetadataStore:
    """Test MemoryMetadataStore functionality."""

    @pytest.fixture
    def memory_store(self):
        """Create a temporary memory store for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        db_manager = DatabaseManager(db_path)
        store = MemoryMetadataStore(db_manager)

        yield store

        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def sample_memory(self) -> CognitiveMemory:
        """Create a sample cognitive memory for testing."""
        from datetime import datetime

        return CognitiveMemory(
            id="test_memory_001",
            content="This is a test memory about cognitive systems",
            memory_type="episodic",
            hierarchy_level=2,
            dimensions={
                "emotional": {"valence": 0.5, "arousal": 0.3},
                "temporal": {"recency": 0.8, "duration": 0.4},
                "contextual": {"location": 0.6, "topic": 0.7},
                "social": {"persons": 0.2, "relationships": 0.1},
            },
            timestamp=datetime.fromtimestamp(time.time()),
            strength=0.8,
            access_count=0,
            tags=["test", "cognitive", "memory"],
        )

    def test_store_memory(self, memory_store, sample_memory):
        """Test storing a cognitive memory."""
        success = memory_store.store_memory(sample_memory)
        assert success

        # Verify memory was stored
        retrieved = memory_store.retrieve_memory(sample_memory.id)
        assert retrieved is not None
        assert retrieved.id == sample_memory.id
        assert retrieved.content == sample_memory.content
        assert retrieved.memory_type == sample_memory.memory_type
        assert retrieved.hierarchy_level == sample_memory.hierarchy_level
        assert retrieved.tags == sample_memory.tags

    def test_retrieve_nonexistent_memory(self, memory_store):
        """Test retrieving a non-existent memory."""
        retrieved = memory_store.retrieve_memory("nonexistent_id")
        assert retrieved is None

    def test_update_memory(self, memory_store, sample_memory):
        """Test updating an existing memory."""
        # Store original memory
        memory_store.store_memory(sample_memory)

        # Update memory
        sample_memory.content = "Updated test memory content"
        sample_memory.strength = 0.9
        sample_memory.access_count = 5

        success = memory_store.update_memory(sample_memory)
        assert success

        # Verify update
        retrieved = memory_store.retrieve_memory(sample_memory.id)
        assert retrieved.content == "Updated test memory content"
        assert retrieved.strength == 0.9

    def test_delete_memory(self, memory_store, sample_memory):
        """Test deleting a memory."""
        # Store memory first
        memory_store.store_memory(sample_memory)

        # Delete memory
        success = memory_store.delete_memory(sample_memory.id)
        assert success

        # Verify deletion
        retrieved = memory_store.retrieve_memory(sample_memory.id)
        assert retrieved is None

    def test_get_memories_by_level(self, memory_store):
        """Test retrieving memories by hierarchy level."""
        # Create memories at different levels
        memories = []
        for i, level in enumerate([0, 1, 2, 2]):
            memory = CognitiveMemory(
                id=f"test_memory_{i:03d}",
                content=f"Test memory {i} at level {level}",
                memory_type="episodic",
                hierarchy_level=level,
                dimensions={},
                timestamp=time.time(),
                strength=0.7,
                access_count=0,
            )
            memories.append(memory)
            memory_store.store_memory(memory)

        # Test level-specific retrieval
        level_0_memories = memory_store.get_memories_by_level(0)
        level_1_memories = memory_store.get_memories_by_level(1)
        level_2_memories = memory_store.get_memories_by_level(2)

        assert len(level_0_memories) == 1
        assert len(level_1_memories) == 1
        assert len(level_2_memories) == 2

        assert all(m.hierarchy_level == 0 for m in level_0_memories)
        assert all(m.hierarchy_level == 1 for m in level_1_memories)
        assert all(m.hierarchy_level == 2 for m in level_2_memories)

    def test_get_memories_by_type(self, memory_store):
        """Test retrieving memories by type."""
        # Create memories of different types
        episodic_memory = CognitiveMemory(
            id="episodic_001",
            content="Episodic memory content",
            memory_type="episodic",
            hierarchy_level=2,
            dimensions={},
            timestamp=time.time(),
            strength=0.8,
            access_count=0,
        )

        semantic_memory = CognitiveMemory(
            id="semantic_001",
            content="Semantic memory content",
            memory_type="semantic",
            hierarchy_level=1,
            dimensions={},
            timestamp=time.time(),
            strength=0.9,
            access_count=0,
        )

        memory_store.store_memory(episodic_memory)
        memory_store.store_memory(semantic_memory)

        # Test type-specific retrieval
        episodic_memories = memory_store.get_memories_by_type("episodic")
        semantic_memories = memory_store.get_memories_by_type("semantic")

        assert len(episodic_memories) == 1
        assert len(semantic_memories) == 1

        assert episodic_memories[0].memory_type == "episodic"
        assert semantic_memories[0].memory_type == "semantic"


class TestConnectionGraphStore:
    """Test ConnectionGraphStore functionality."""

    @pytest.fixture
    def connection_store(self):
        """Create a temporary connection store for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        db_manager = DatabaseManager(db_path)
        store = ConnectionGraphStore(db_manager)

        # Create some test memories first
        memory_store = MemoryMetadataStore(db_manager)
        test_memories = [
            CognitiveMemory(
                id=f"memory_{i:03d}",
                content=f"Test memory {i}",
                memory_type="episodic",
                hierarchy_level=2,
                dimensions={},
                timestamp=datetime.fromtimestamp(time.time()),
                strength=0.7,
                access_count=0,
            )
            for i in range(3)
        ]

        for memory in test_memories:
            memory_store.store_memory(memory)

        yield store, [m.id for m in test_memories]

        Path(db_path).unlink(missing_ok=True)

    def test_add_connection(self, connection_store):
        """Test adding connections between memories."""
        store, memory_ids = connection_store

        success = store.add_connection(
            source_id=memory_ids[0],
            target_id=memory_ids[1],
            strength=0.8,
            connection_type="associative",
        )
        assert success

    def test_get_connections(self, connection_store):
        """Test retrieving connections for a memory."""
        store, memory_ids = connection_store

        # Add some connections
        store.add_connection(memory_ids[0], memory_ids[1], 0.8, "associative")
        store.add_connection(memory_ids[0], memory_ids[2], 0.6, "causal")
        store.add_connection(memory_ids[1], memory_ids[2], 0.4, "temporal")

        # Get connections for memory_ids[0]
        connections = store.get_connections(memory_ids[0], min_strength=0.5)

        # Should get connections to both memory_ids[1] and memory_ids[2]
        assert len(connections) == 2

        connected_ids = {conn.id for conn in connections}
        assert memory_ids[1] in connected_ids
        assert memory_ids[2] in connected_ids

    def test_update_connection_strength(self, connection_store):
        """Test updating connection strength."""
        store, memory_ids = connection_store

        # Add connection
        store.add_connection(memory_ids[0], memory_ids[1], 0.5, "associative")

        # Update strength
        success = store.update_connection_strength(memory_ids[0], memory_ids[1], 0.9)
        assert success

        # Verify update
        strength = store.get_connection_strength(memory_ids[0], memory_ids[1])
        assert strength == 0.9

    def test_remove_connection(self, connection_store):
        """Test removing connections."""
        store, memory_ids = connection_store

        # Add connection
        store.add_connection(memory_ids[0], memory_ids[1], 0.8, "associative")

        # Verify connection exists
        connections = store.get_connections(memory_ids[0])
        assert len(connections) == 1

        # Remove connection
        success = store.remove_connection(memory_ids[0], memory_ids[1])
        assert success

        # Verify removal
        connections = store.get_connections(memory_ids[0])
        assert len(connections) == 0

    def test_bidirectional_connections(self, connection_store):
        """Test bidirectional connection handling."""
        store, memory_ids = connection_store

        # Add connection from A to B
        store.add_connection(memory_ids[0], memory_ids[1], 0.8, "associative")

        # Should be able to find connection from both directions
        connections_from_0 = store.get_connections(memory_ids[0])
        connections_from_1 = store.get_connections(memory_ids[1])

        assert len(connections_from_0) == 1
        assert len(connections_from_1) == 1

        assert connections_from_0[0].id == memory_ids[1]
        assert connections_from_1[0].id == memory_ids[0]


class TestSQLitePersistenceIntegration:
    """Integration tests for SQLite persistence components."""

    def test_create_sqlite_persistence_factory(self):
        """Test the factory function for creating persistence components."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            memory_store, connection_store = create_sqlite_persistence(db_path)

            assert isinstance(memory_store, MemoryMetadataStore)
            assert isinstance(connection_store, ConnectionGraphStore)

            # Test that both stores work with the same database
            test_memory = CognitiveMemory(
                id="integration_test_001",
                content="Integration test memory",
                memory_type="episodic",
                hierarchy_level=2,
                dimensions={},
                timestamp=time.time(),
                strength=0.8,
                access_count=0,
            )

            # Store memory
            assert memory_store.store_memory(test_memory)

            # Create connection (requires the memory to exist)
            test_memory_2 = CognitiveMemory(
                id="integration_test_002",
                content="Second integration test memory",
                memory_type="episodic",
                hierarchy_level=2,
                dimensions={},
                timestamp=time.time(),
                strength=0.7,
                access_count=0,
            )

            memory_store.store_memory(test_memory_2)

            assert connection_store.add_connection(
                test_memory.id, test_memory_2.id, 0.8, "associative"
            )

        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_concurrent_access(self):
        """Test concurrent access to the database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            # Create multiple stores using the same database
            memory_store_1, connection_store_1 = create_sqlite_persistence(db_path)
            memory_store_2, connection_store_2 = create_sqlite_persistence(db_path)

            # Store memory using first store
            test_memory = CognitiveMemory(
                id="concurrent_test_001",
                content="Concurrent test memory",
                memory_type="episodic",
                hierarchy_level=2,
                dimensions={},
                timestamp=time.time(),
                strength=0.8,
                access_count=0,
            )

            memory_store_1.store_memory(test_memory)

            # Retrieve using second store
            retrieved_memory = memory_store_2.retrieve_memory("concurrent_test_001")
            assert retrieved_memory is not None
            assert retrieved_memory.content == "Concurrent test memory"

        finally:
            Path(db_path).unlink(missing_ok=True)
