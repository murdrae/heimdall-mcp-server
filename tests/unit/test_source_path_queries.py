"""Unit tests for source path querying functionality."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from cognitive_memory.core.memory import CognitiveMemory
from cognitive_memory.storage.sqlite_persistence import (
    DatabaseManager,
    MemoryMetadataStore,
)


class TestSourcePathQueries:
    """Test source path querying and deletion functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            temp_path = f.name

        db_manager = DatabaseManager(temp_path)
        yield db_manager

        # Cleanup
        Path(temp_path).unlink(missing_ok=True)

    @pytest.fixture
    def memory_store(self, temp_db):
        """Create a memory metadata store for testing."""
        return MemoryMetadataStore(temp_db)

    @pytest.fixture
    def sample_memories(self):
        """Create sample memories with different source paths."""
        memories = []

        # Memory from file1.md
        memory1 = CognitiveMemory(
            id="mem1",
            content="Content from file1.md",
            memory_type="semantic",
            hierarchy_level=1,
            dimensions={"relevance": 0.8},
            timestamp=datetime.now(),
            strength=1.0,
            metadata={
                "source_type": "documentation",
                "source_path": "/docs/file1.md",
                "title": "File 1",
            },
        )
        memories.append(memory1)

        # Memory from file2.md
        memory2 = CognitiveMemory(
            id="mem2",
            content="Content from file2.md",
            memory_type="semantic",
            hierarchy_level=2,
            dimensions={"relevance": 0.6},
            timestamp=datetime.now(),
            strength=0.8,
            metadata={
                "source_type": "documentation",
                "source_path": "/docs/file2.md",
                "title": "File 2",
            },
        )
        memories.append(memory2)

        # Another memory from file1.md (different section)
        memory3 = CognitiveMemory(
            id="mem3",
            content="Another section from file1.md",
            memory_type="episodic",
            hierarchy_level=2,
            dimensions={"relevance": 0.9},
            timestamp=datetime.now(),
            strength=0.9,
            metadata={
                "source_type": "documentation",
                "source_path": "/docs/file1.md",
                "title": "File 1 Section 2",
            },
        )
        memories.append(memory3)

        # Memory without source_path (should not be affected by source path queries)
        memory4 = CognitiveMemory(
            id="mem4",
            content="Manual entry without source path",
            memory_type="episodic",
            hierarchy_level=2,
            dimensions={"relevance": 0.7},
            timestamp=datetime.now(),
            strength=0.7,
            metadata={"source_type": "manual_entry", "title": "Manual Entry"},
        )
        memories.append(memory4)

        return memories

    def test_store_and_retrieve_by_source_path(self, memory_store, sample_memories):
        """Test storing memories and retrieving them by source path."""
        # Store all memories
        for memory in sample_memories:
            success = memory_store.store_memory(memory)
            assert success, f"Failed to store memory {memory.id}"

        # Retrieve memories from file1.md
        file1_memories = memory_store.get_memories_by_source_path("/docs/file1.md")
        assert len(file1_memories) == 2

        # Check that both memories from file1.md are retrieved
        file1_ids = {memory.id for memory in file1_memories}
        assert file1_ids == {"mem1", "mem3"}

        # Retrieve memories from file2.md
        file2_memories = memory_store.get_memories_by_source_path("/docs/file2.md")
        assert len(file2_memories) == 1
        assert file2_memories[0].id == "mem2"

    def test_get_memories_by_nonexistent_source_path(
        self, memory_store, sample_memories
    ):
        """Test querying for a non-existent source path."""
        # Store memories
        for memory in sample_memories:
            memory_store.store_memory(memory)

        # Query for non-existent source path
        nonexistent_memories = memory_store.get_memories_by_source_path(
            "/docs/nonexistent.md"
        )
        assert len(nonexistent_memories) == 0

    def test_get_memories_by_source_path_empty_db(self, memory_store):
        """Test querying source path on empty database."""
        memories = memory_store.get_memories_by_source_path("/docs/file1.md")
        assert len(memories) == 0

    def test_get_memories_by_source_path_ordering(self, memory_store, sample_memories):
        """Test that memories are returned ordered by strength and access count."""
        # Store memories
        for memory in sample_memories:
            memory_store.store_memory(memory)

        # Retrieve memories from file1.md
        file1_memories = memory_store.get_memories_by_source_path("/docs/file1.md")
        assert len(file1_memories) == 2

        # Should be ordered by strength DESC (mem1: 1.0, mem3: 0.9)
        assert file1_memories[0].id == "mem1"
        assert file1_memories[1].id == "mem3"

    def test_delete_memories_by_source_path(self, memory_store, sample_memories):
        """Test deleting memories by source path."""
        # Store all memories
        for memory in sample_memories:
            memory_store.store_memory(memory)

        # Verify initial state
        all_memories = memory_store.get_memories_by_level(
            1
        ) + memory_store.get_memories_by_level(2)
        assert len(all_memories) == 4

        # Delete memories from file1.md
        deleted_count = memory_store.delete_memories_by_source_path("/docs/file1.md")
        assert deleted_count == 2

        # Verify file1.md memories are gone
        file1_memories = memory_store.get_memories_by_source_path("/docs/file1.md")
        assert len(file1_memories) == 0

        # Verify other memories still exist
        file2_memories = memory_store.get_memories_by_source_path("/docs/file2.md")
        assert len(file2_memories) == 1

        # Manual entry should still exist (no source_path)
        manual_memory = memory_store.retrieve_memory("mem4")
        assert manual_memory is not None

    def test_delete_memories_by_nonexistent_source_path(
        self, memory_store, sample_memories
    ):
        """Test deleting from a non-existent source path."""
        # Store memories
        for memory in sample_memories:
            memory_store.store_memory(memory)

        # Delete from non-existent source path
        deleted_count = memory_store.delete_memories_by_source_path(
            "/docs/nonexistent.md"
        )
        assert deleted_count == 0

        # Verify all original memories still exist
        all_memories = memory_store.get_memories_by_level(
            1
        ) + memory_store.get_memories_by_level(2)
        assert len(all_memories) == 4

    def test_delete_memories_by_source_path_empty_db(self, memory_store):
        """Test deleting from source path on empty database."""
        deleted_count = memory_store.delete_memories_by_source_path("/docs/file1.md")
        assert deleted_count == 0

    def test_source_path_with_special_characters(self, memory_store):
        """Test source paths with special characters."""
        special_path = "/docs/file with spaces & special-chars (test).md"

        memory = CognitiveMemory(
            id="special_mem",
            content="Content with special path",
            memory_type="semantic",
            hierarchy_level=1,
            dimensions={"relevance": 0.8},
            timestamp=datetime.now(),
            strength=1.0,
            metadata={
                "source_type": "documentation",
                "source_path": special_path,
                "title": "Special File",
            },
        )

        # Store and retrieve
        success = memory_store.store_memory(memory)
        assert success

        retrieved_memories = memory_store.get_memories_by_source_path(special_path)
        assert len(retrieved_memories) == 1
        assert retrieved_memories[0].id == "special_mem"

        # Delete
        deleted_count = memory_store.delete_memories_by_source_path(special_path)
        assert deleted_count == 1

    def test_source_path_case_sensitivity(self, memory_store):
        """Test that source path queries are case sensitive."""
        memory = CognitiveMemory(
            id="case_mem",
            content="Content for case test",
            memory_type="semantic",
            hierarchy_level=1,
            dimensions={"relevance": 0.8},
            timestamp=datetime.now(),
            strength=1.0,
            metadata={
                "source_type": "documentation",
                "source_path": "/docs/File1.md",  # Capital F
                "title": "Case Test",
            },
        )

        memory_store.store_memory(memory)

        # Query with exact case should find the memory
        exact_memories = memory_store.get_memories_by_source_path("/docs/File1.md")
        assert len(exact_memories) == 1

        # Query with different case should not find the memory
        different_case_memories = memory_store.get_memories_by_source_path(
            "/docs/file1.md"
        )
        assert len(different_case_memories) == 0

    def test_missing_source_path_in_metadata(self, memory_store):
        """Test handling of memories where source_path key is missing from metadata."""
        memory = CognitiveMemory(
            id="missing_source_mem",
            content="Content without source_path key",
            memory_type="semantic",
            hierarchy_level=1,
            dimensions={"relevance": 0.8},
            timestamp=datetime.now(),
            strength=1.0,
            metadata={
                "source_type": "documentation",
                # source_path key is missing entirely
                "title": "Missing Source Key",
            },
        )

        memory_store.store_memory(memory)

        # Query should handle missing source_path key gracefully
        memories = memory_store.get_memories_by_source_path("/docs/any.md")
        assert len(memories) == 0  # Should not find memories without source_path

    def test_null_source_path_metadata(self, memory_store):
        """Test handling of memories where source_path is null in metadata."""
        memory = CognitiveMemory(
            id="null_source_mem",
            content="Content without source path",
            memory_type="semantic",
            hierarchy_level=1,
            dimensions={"relevance": 0.8},
            timestamp=datetime.now(),
            strength=1.0,
            metadata={
                "source_type": "documentation",
                "source_path": None,  # Explicitly null
                "title": "No Source",
            },
        )

        memory_store.store_memory(memory)

        # Query should not find memories with null source_path
        memories = memory_store.get_memories_by_source_path(None)
        assert len(memories) == 0

        # Query for any path should not find the null source memory
        memories = memory_store.get_memories_by_source_path("/docs/any.md")
        assert len(memories) == 0

    def test_performance_with_many_memories(self, memory_store):
        """Test performance characteristics with larger dataset."""
        # Create many memories with different source paths
        memories = []
        for i in range(100):
            source_path = f"/docs/file{i}.md" if i % 10 != 0 else "/docs/common.md"

            memory = CognitiveMemory(
                id=f"perf_mem_{i}",
                content=f"Content for memory {i}",
                memory_type="semantic",
                hierarchy_level=i % 3,
                dimensions={"relevance": 0.5 + (i % 50) / 100},
                timestamp=datetime.now(),
                strength=0.5 + (i % 50) / 100,
                metadata={
                    "source_type": "documentation",
                    "source_path": source_path,
                    "title": f"Memory {i}",
                },
            )
            memories.append(memory)

        # Store all memories
        for memory in memories:
            success = memory_store.store_memory(memory)
            assert success

        # Query for common.md should return 10 memories (every 10th)
        common_memories = memory_store.get_memories_by_source_path("/docs/common.md")
        assert len(common_memories) == 10

        # Query for specific file should return 1 memory
        specific_memories = memory_store.get_memories_by_source_path("/docs/file5.md")
        assert len(specific_memories) == 1

        # Delete common.md memories
        deleted_count = memory_store.delete_memories_by_source_path("/docs/common.md")
        assert deleted_count == 10

        # Verify deletion
        remaining_common = memory_store.get_memories_by_source_path("/docs/common.md")
        assert len(remaining_common) == 0
