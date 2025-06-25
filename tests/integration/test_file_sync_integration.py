"""
Integration tests for file synchronization system.

Tests the complete file sync workflow including real file operations,
memory loading, and integration with the cognitive memory system.
"""

import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from cognitive_memory.core.config import CognitiveConfig
from cognitive_memory.core.interfaces import MemoryLoader
from cognitive_memory.core.memory import CognitiveMemory
from heimdall.monitoring.file_sync import FileSyncHandler
from heimdall.monitoring.file_types import ChangeType, FileChangeEvent
from heimdall.monitoring.loader_registry import (
    LoaderRegistry,
    create_default_registry,
)


class TestMemoryLoader(MemoryLoader):
    """Test MemoryLoader implementation for integration testing."""

    def __init__(self, name: str = "test", extensions: list[str] = None):
        self.name = name
        self.extensions = extensions or [".txt", ".md"]
        self.load_calls = []

    def load_from_source(self, source_path: str, **kwargs) -> list[CognitiveMemory]:
        """Load memories from source file."""
        self.load_calls.append((source_path, kwargs))

        path = Path(source_path)
        if not path.exists():
            return []

        content = path.read_text(encoding="utf-8")

        # Create memory based on file content
        memory = CognitiveMemory(
            id=f"test_{path.stem}",
            content=content,
            hierarchy_level=2,
            memory_type="episodic",
            metadata={
                "source_path": source_path,
                "source_type": "test_file",
                "file_name": path.name,
            },
        )

        return [memory]

    def extract_connections(
        self, memories: list[CognitiveMemory]
    ) -> list[tuple[str, str, float, str]]:
        """Extract connections between memories."""
        return []

    def validate_source(self, source_path: str) -> bool:
        """Validate source file."""
        path = Path(source_path)
        return path.exists() and path.suffix.lower() in self.extensions

    def get_supported_extensions(self) -> list[str]:
        """Get supported file extensions."""
        return self.extensions


class MockCognitiveSystem:
    """Mock cognitive system for integration testing."""

    def __init__(self):
        self.stored_memories = {}
        self.deleted_source_paths = []
        self.next_memory_id = 1

    def store_experience(self, text: str, context: dict = None) -> str:
        """Store experience and return memory ID."""
        memory_id = f"memory_{self.next_memory_id}"
        self.next_memory_id += 1

        self.stored_memories[memory_id] = {"content": text, "context": context or {}}

        return memory_id

    def delete_memories_by_source_path(self, source_path: str) -> dict:
        """Delete memories by source path."""
        self.deleted_source_paths.append(source_path)

        # Count memories that would be deleted
        deleted_count = 0
        for memory_id, memory_data in list(self.stored_memories.items()):
            if memory_data["context"].get("source_path") == source_path:
                del self.stored_memories[memory_id]
                deleted_count += 1

        return {"deleted_memories": deleted_count}

    def get_memories_for_source_path(self, source_path: str) -> list[dict]:
        """Get memories associated with a source path."""
        return [
            {"id": memory_id, **memory_data}
            for memory_id, memory_data in self.stored_memories.items()
            if memory_data["context"].get("source_path") == source_path
        ]


class TestFileSyncIntegration:
    """Integration tests for file synchronization system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cognitive_system = MockCognitiveSystem()
        self.loader_registry = LoaderRegistry()
        self.config = CognitiveConfig()

        # Register test loader
        self.test_loader = TestMemoryLoader()
        self.loader_registry.register_loader("test", self.test_loader)

        # Create sync handler
        self.sync_handler = FileSyncHandler(
            self.cognitive_system, self.loader_registry, enable_atomic_operations=True
        )

    def test_file_add_sync_workflow(self, tmp_path):
        """Test complete file addition synchronization workflow."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("This is test content for file addition.")

        # Create file change event
        event = FileChangeEvent(test_file, ChangeType.ADDED, time.time())

        # Process the event
        result = self.sync_handler.handle_file_change(event)

        # Verify results
        assert result is True
        assert len(self.test_loader.load_calls) == 1
        assert self.test_loader.load_calls[0][0] == str(test_file)

        # Check that memory was stored
        assert len(self.cognitive_system.stored_memories) == 1
        memory = list(self.cognitive_system.stored_memories.values())[0]
        assert memory["content"] == "This is test content for file addition."
        assert memory["context"]["source_path"] == str(test_file)

        # Check statistics
        stats = self.sync_handler.get_sync_statistics()
        assert stats["files_added"] == 1
        assert stats["sync_errors"] == 0

    def test_file_modify_sync_workflow(self, tmp_path):
        """Test complete file modification synchronization workflow."""
        # Create and add initial file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Original content")

        add_event = FileChangeEvent(test_file, ChangeType.ADDED, time.time())
        self.sync_handler.handle_file_change(add_event)

        # Verify initial state
        assert len(self.cognitive_system.stored_memories) == 1
        initial_memory_id = list(self.cognitive_system.stored_memories.keys())[0]

        # Modify file content
        test_file.write_text("Modified content")

        # Process modification event
        modify_event = FileChangeEvent(test_file, ChangeType.MODIFIED, time.time())
        result = self.sync_handler.handle_file_change(modify_event)

        # Verify results
        assert result is True
        assert len(self.test_loader.load_calls) == 2  # One for add, one for modify

        # Check that old memory was deleted and new one created
        assert initial_memory_id not in self.cognitive_system.stored_memories
        assert len(self.cognitive_system.stored_memories) == 1

        # Verify new memory content
        new_memory = list(self.cognitive_system.stored_memories.values())[0]
        assert new_memory["content"] == "Modified content"
        assert new_memory["context"]["source_path"] == str(test_file)

        # Check statistics
        stats = self.sync_handler.get_sync_statistics()
        assert stats["files_added"] == 1
        assert stats["files_modified"] == 1
        assert stats["sync_errors"] == 0

    def test_file_delete_sync_workflow(self, tmp_path):
        """Test complete file deletion synchronization workflow."""
        # Create and add initial file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Content to be deleted")

        add_event = FileChangeEvent(test_file, ChangeType.ADDED, time.time())
        self.sync_handler.handle_file_change(add_event)

        # Verify initial state
        assert len(self.cognitive_system.stored_memories) == 1

        # Delete the file (simulate file system deletion)
        test_file.unlink()

        # Process deletion event
        delete_event = FileChangeEvent(test_file, ChangeType.DELETED, time.time())
        result = self.sync_handler.handle_file_change(delete_event)

        # Verify results
        assert result is True
        assert str(test_file) in self.cognitive_system.deleted_source_paths

        # Check that memory was deleted
        memories_for_file = self.cognitive_system.get_memories_for_source_path(
            str(test_file)
        )
        assert len(memories_for_file) == 0

        # Check statistics
        stats = self.sync_handler.get_sync_statistics()
        assert stats["files_added"] == 1
        assert stats["files_deleted"] == 1
        assert stats["sync_errors"] == 0

    def test_multiple_file_sync_workflow(self, tmp_path):
        """Test synchronization workflow with multiple files."""
        # Create multiple test files
        files = []
        for i in range(3):
            test_file = tmp_path / f"test_{i}.txt"
            test_file.write_text(f"Content for file {i}")
            files.append(test_file)

        # Add all files
        for test_file in files:
            event = FileChangeEvent(test_file, ChangeType.ADDED, time.time())
            result = self.sync_handler.handle_file_change(event)
            assert result is True

        # Verify all memories were stored
        assert len(self.cognitive_system.stored_memories) == 3

        # Modify one file
        files[1].write_text("Modified content for file 1")
        modify_event = FileChangeEvent(files[1], ChangeType.MODIFIED, time.time())
        result = self.sync_handler.handle_file_change(modify_event)
        assert result is True

        # Delete one file
        files[2].unlink()
        delete_event = FileChangeEvent(files[2], ChangeType.DELETED, time.time())
        result = self.sync_handler.handle_file_change(delete_event)
        assert result is True

        # Verify final state
        assert len(self.cognitive_system.stored_memories) == 2  # 3 added - 1 deleted

        # Check that correct memories remain
        remaining_files = {str(files[0]), str(files[1])}
        for memory_data in self.cognitive_system.stored_memories.values():
            assert memory_data["context"]["source_path"] in remaining_files

        # Check statistics
        stats = self.sync_handler.get_sync_statistics()
        assert stats["files_added"] == 3
        assert stats["files_modified"] == 1
        assert stats["files_deleted"] == 1
        assert stats["sync_errors"] == 0

    def test_unsupported_file_type_workflow(self, tmp_path):
        """Test workflow with unsupported file types."""
        # Create file with unsupported extension
        test_file = tmp_path / "test.xyz"
        test_file.write_text("Unsupported file content")

        # Process addition event
        event = FileChangeEvent(test_file, ChangeType.ADDED, time.time())
        result = self.sync_handler.handle_file_change(event)

        # Should succeed but not process the file
        assert result is True
        assert len(self.test_loader.load_calls) == 0
        assert len(self.cognitive_system.stored_memories) == 0

        # Check statistics
        stats = self.sync_handler.get_sync_statistics()
        assert stats["files_added"] == 1  # Event processed successfully
        assert stats["sync_errors"] == 0

    def test_loader_validation_failure_workflow(self, tmp_path):
        """Test workflow when loader validation fails."""
        # Create file that exists but validation fails
        test_file = tmp_path / "test.txt"
        test_file.write_text("Content that fails validation")

        # Make loader validation fail
        original_validate = self.test_loader.validate_source
        self.test_loader.validate_source = lambda source_path: False

        try:
            # Process addition event
            event = FileChangeEvent(test_file, ChangeType.ADDED, time.time())
            result = self.sync_handler.handle_file_change(event)

            # Should succeed but not process the file
            assert result is True
            assert len(self.test_loader.load_calls) == 0
            assert len(self.cognitive_system.stored_memories) == 0

        finally:
            # Restore original validation
            self.test_loader.validate_source = original_validate

    def test_atomic_operations_partial_failure(self, tmp_path):
        """Test atomic operations behavior with partial failure."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Original content")

        # Add file initially
        add_event = FileChangeEvent(test_file, ChangeType.ADDED, time.time())
        self.sync_handler.handle_file_change(add_event)

        # Modify file content
        test_file.write_text("Modified content")

        # Make store_experience fail for new memory
        original_store = self.cognitive_system.store_experience
        self.cognitive_system.store_experience = lambda text, context: None

        try:
            # Process modification event
            modify_event = FileChangeEvent(test_file, ChangeType.MODIFIED, time.time())
            result = self.sync_handler.handle_file_change(modify_event)

            # Should fail due to storage failure
            assert result is False

            # Check statistics
            stats = self.sync_handler.get_sync_statistics()
            assert stats["sync_errors"] == 1

        finally:
            # Restore original store method
            self.cognitive_system.store_experience = original_store

    def test_configuration_integration(self):
        """Test integration with configuration system."""
        # Test with atomic operations disabled
        handler_no_atomic = FileSyncHandler(
            self.cognitive_system, self.loader_registry, enable_atomic_operations=False
        )

        assert handler_no_atomic.enable_atomic_operations is False

        # Verify different code path is used for modifications
        # (This would require more detailed testing to verify the exact path)

    def test_loader_registry_integration(self, tmp_path):
        """Test integration with loader registry system."""
        # Create registry with multiple loaders
        registry = LoaderRegistry()

        # Register loaders for different file types
        txt_loader = TestMemoryLoader("txt", [".txt"])
        md_loader = TestMemoryLoader("md", [".md"])

        registry.register_loader("txt", txt_loader)
        registry.register_loader("md", md_loader)

        # Create sync handler with new registry
        handler = FileSyncHandler(self.cognitive_system, registry)

        # Test with different file types
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("TXT content")

        md_file = tmp_path / "test.md"
        md_file.write_text("# Markdown content")

        # Process both files
        txt_event = FileChangeEvent(txt_file, ChangeType.ADDED, time.time())
        md_event = FileChangeEvent(md_file, ChangeType.ADDED, time.time())

        result1 = handler.handle_file_change(txt_event)
        result2 = handler.handle_file_change(md_event)

        assert result1 is True
        assert result2 is True

        # Verify correct loaders were used
        assert len(txt_loader.load_calls) == 1
        assert len(md_loader.load_calls) == 1

        # Verify memories were stored
        assert len(self.cognitive_system.stored_memories) == 2

    def test_error_recovery_workflow(self, tmp_path):
        """Test error recovery in sync workflow."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Content for error recovery test")

        # Make loader fail temporarily
        original_load = self.test_loader.load_from_source
        self.test_loader.load_from_source = Mock(
            side_effect=Exception("Temporary failure")
        )

        # Process event that will fail
        event = FileChangeEvent(test_file, ChangeType.ADDED, time.time())
        result = self.sync_handler.handle_file_change(event)

        assert result is False
        assert self.sync_handler.get_sync_statistics()["sync_errors"] == 1

        # Restore loader functionality
        self.test_loader.load_from_source = original_load

        # Process event again - should succeed
        result = self.sync_handler.handle_file_change(event)

        assert result is True
        assert len(self.cognitive_system.stored_memories) == 1

        # Error count should remain the same (no new errors)
        assert self.sync_handler.get_sync_statistics()["sync_errors"] == 1

    def test_statistics_integration(self, tmp_path):
        """Test statistics tracking integration."""
        # Perform various operations
        files = []
        for i in range(2):
            test_file = tmp_path / f"test_{i}.txt"
            test_file.write_text(f"Content {i}")
            files.append(test_file)

        # Add files
        for test_file in files:
            event = FileChangeEvent(test_file, ChangeType.ADDED, time.time())
            self.sync_handler.handle_file_change(event)

        # Modify one file
        files[0].write_text("Modified content")
        modify_event = FileChangeEvent(files[0], ChangeType.MODIFIED, time.time())
        self.sync_handler.handle_file_change(modify_event)

        # Delete one file
        delete_event = FileChangeEvent(files[1], ChangeType.DELETED, time.time())
        self.sync_handler.handle_file_change(delete_event)

        # Verify comprehensive statistics
        stats = self.sync_handler.get_sync_statistics()
        assert stats["files_added"] == 2
        assert stats["files_modified"] == 1
        assert stats["files_deleted"] == 1
        assert stats["sync_errors"] == 0
        assert stats["last_sync_time"] is not None

        # Test statistics reset
        self.sync_handler.reset_statistics()
        stats = self.sync_handler.get_sync_statistics()
        assert all(
            count == 0 for key, count in stats.items() if key != "last_sync_time"
        )
        assert stats["last_sync_time"] is None


class TestDefaultRegistryIntegration:
    """Integration tests for default registry creation."""

    @patch("cognitive_memory.loaders.markdown_loader.MarkdownMemoryLoader")
    def test_create_default_registry_integration(self, mock_markdown_loader):
        """Test default registry creation with mocked dependencies."""
        # Setup mock with proper MemoryLoader spec
        mock_loader_instance = Mock(spec=MemoryLoader)
        mock_loader_instance.get_supported_extensions.return_value = [
            ".md",
            ".markdown",
        ]
        mock_loader_instance.validate_source.return_value = True
        mock_loader_instance.load_from_source.return_value = []
        mock_loader_instance.extract_connections.return_value = []
        mock_markdown_loader.return_value = mock_loader_instance

        # Create default registry
        registry = create_default_registry()

        # Verify registry was created and loader registered
        assert isinstance(registry, LoaderRegistry)
        assert "markdown" in registry.list_registered_loaders()

        # Verify mock was called with config
        mock_markdown_loader.assert_called_once()

    def test_default_registry_file_support(self):
        """Test file support detection with default registry."""
        # This test requires actual MarkdownMemoryLoader to be available
        # It's more of a smoke test to ensure the default registry works
        try:
            registry = create_default_registry()

            # Should have at least one loader registered
            loaders = registry.list_registered_loaders()
            assert len(loaders) > 0

            # Should support some file extensions
            extensions = registry.get_supported_extensions()
            assert len(extensions) > 0

        except ImportError:
            # Skip test if dependencies not available
            pytest.skip("MarkdownMemoryLoader not available for testing")
