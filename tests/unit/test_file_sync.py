"""
Unit tests for FileSyncHandler system.

Tests the file synchronization functionality including file change handling,
loader delegation, atomic operations, and error recovery scenarios.
"""

import time
from unittest.mock import Mock, patch

from cognitive_memory.core.interfaces import CognitiveSystem, MemoryLoader
from cognitive_memory.core.memory import CognitiveMemory
from heimdall.monitoring.file_sync import FileSyncError, FileSyncHandler
from heimdall.monitoring.file_types import ChangeType, FileChangeEvent
from heimdall.monitoring.loader_registry import LoaderRegistry


def create_mock_cognitive_system():
    """Create a mock CognitiveSystem for testing purposes."""
    mock_system = Mock(spec=CognitiveSystem)
    mock_system.store_experience_calls = []
    mock_system.delete_memories_calls = []
    mock_system.store_experience_return_value = "mock_memory_id"
    mock_system.delete_memories_return_value = {"deleted_memories": 5}

    def mock_store_experience(text: str, context: dict = None) -> str:
        mock_system.store_experience_calls.append((text, context))
        return mock_system.store_experience_return_value

    def mock_delete_memories_by_source_path(source_path: str) -> dict:
        mock_system.delete_memories_calls.append(source_path)
        return mock_system.delete_memories_return_value

    mock_system.store_experience = Mock(side_effect=mock_store_experience)
    mock_system.delete_memories_by_source_path = Mock(
        side_effect=mock_delete_memories_by_source_path
    )

    return mock_system


class MockMemoryLoader(MemoryLoader):
    """Mock MemoryLoader for testing purposes."""

    def __init__(self, name: str, extensions: list[str]):
        self.name = name
        self.extensions = extensions
        self.load_from_source_calls = []
        self.validate_source_calls = []
        self.load_from_source_return_value = []

    def load_from_source(self, source_path: str, **kwargs) -> list[CognitiveMemory]:
        """Mock load_from_source method."""
        self.load_from_source_calls.append((source_path, kwargs))
        return self.load_from_source_return_value

    def extract_connections(
        self, memories: list[CognitiveMemory]
    ) -> list[tuple[str, str, float, str]]:
        """Mock extract_connections method."""
        return []

    def validate_source(self, source_path: str) -> bool:
        """Mock validate_source method."""
        self.validate_source_calls.append(source_path)
        return True

    def get_supported_extensions(self) -> list[str]:
        """Mock get_supported_extensions method."""
        return self.extensions


def create_mock_memory(
    content: str = "test content", context: dict = None
) -> CognitiveMemory:
    """Create a mock CognitiveMemory for testing."""
    return CognitiveMemory(
        id="test_id",
        content=content,
        hierarchy_level=2,
        memory_type="episodic",
        metadata=context or {},
    )


class TestFileSyncHandler:
    """Test cases for FileSyncHandler class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cognitive_system = create_mock_cognitive_system()
        self.loader_registry = LoaderRegistry()
        self.sync_handler = FileSyncHandler(self.cognitive_system, self.loader_registry)

    def test_init_default_parameters(self):
        """Test FileSyncHandler initialization with default parameters."""
        assert self.sync_handler.cognitive_system == self.cognitive_system
        assert self.sync_handler.loader_registry == self.loader_registry
        assert self.sync_handler.enable_atomic_operations is True
        assert self.sync_handler.stats["files_added"] == 0
        assert self.sync_handler.stats["files_modified"] == 0
        assert self.sync_handler.stats["files_deleted"] == 0
        assert self.sync_handler.stats["sync_errors"] == 0
        assert self.sync_handler.stats["last_sync_time"] is None

    def test_init_custom_parameters(self):
        """Test FileSyncHandler initialization with custom parameters."""
        handler = FileSyncHandler(
            self.cognitive_system, self.loader_registry, enable_atomic_operations=False
        )

        assert handler.enable_atomic_operations is False

    def test_handle_file_change_added_success(self, tmp_path):
        """Test successful handling of file addition."""
        # Setup
        loader = MockMemoryLoader("test", [".txt"])
        memory = create_mock_memory()
        loader.load_from_source_return_value = [memory]
        self.loader_registry.register_loader("test", loader)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        event = FileChangeEvent(test_file, ChangeType.ADDED, time.time())

        # Execute
        result = self.sync_handler.handle_file_change(event)

        # Verify
        assert result is True
        assert self.sync_handler.stats["files_added"] == 1
        assert len(loader.load_from_source_calls) == 1
        assert len(self.cognitive_system.store_experience_calls) == 1

    def test_handle_file_change_added_no_loader(self, tmp_path):
        """Test handling file addition with no suitable loader."""
        test_file = tmp_path / "test.xyz"
        test_file.write_text("test content")
        event = FileChangeEvent(test_file, ChangeType.ADDED, time.time())

        result = self.sync_handler.handle_file_change(event)

        assert result is True  # Not an error, just unsupported
        assert self.sync_handler.stats["files_added"] == 1

    def test_handle_file_change_added_no_memories(self, tmp_path):
        """Test handling file addition when loader returns no memories."""
        loader = MockMemoryLoader("test", [".txt"])
        loader.load_from_source_return_value = []  # No memories
        self.loader_registry.register_loader("test", loader)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        event = FileChangeEvent(test_file, ChangeType.ADDED, time.time())

        result = self.sync_handler.handle_file_change(event)

        assert result is True
        assert self.sync_handler.stats["files_added"] == 1
        assert len(self.cognitive_system.store_experience_calls) == 0

    def test_handle_file_change_added_store_failure(self, tmp_path):
        """Test handling file addition when memory storage fails."""
        loader = MockMemoryLoader("test", [".txt"])
        memory = create_mock_memory()
        loader.load_from_source_return_value = [memory]
        self.loader_registry.register_loader("test", loader)

        # Make store_experience fail
        self.cognitive_system.store_experience_return_value = None

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        event = FileChangeEvent(test_file, ChangeType.ADDED, time.time())

        result = self.sync_handler.handle_file_change(event)

        assert result is False
        assert self.sync_handler.stats["files_added"] == 0
        assert self.sync_handler.stats["sync_errors"] == 1

    def test_handle_file_change_modified_atomic(self, tmp_path):
        """Test handling file modification with atomic operations."""
        loader = MockMemoryLoader("test", [".txt"])
        memory = create_mock_memory()
        loader.load_from_source_return_value = [memory]
        self.loader_registry.register_loader("test", loader)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        event = FileChangeEvent(test_file, ChangeType.MODIFIED, time.time())

        result = self.sync_handler.handle_file_change(event)

        assert result is True
        assert self.sync_handler.stats["files_modified"] == 1
        assert len(self.cognitive_system.delete_memories_calls) == 1
        assert len(self.cognitive_system.store_experience_calls) == 1

    def test_handle_file_change_modified_simple(self, tmp_path):
        """Test handling file modification with simple operations."""
        # Disable atomic operations
        self.sync_handler.enable_atomic_operations = False

        loader = MockMemoryLoader("test", [".txt"])
        memory = create_mock_memory()
        loader.load_from_source_return_value = [memory]
        self.loader_registry.register_loader("test", loader)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        event = FileChangeEvent(test_file, ChangeType.MODIFIED, time.time())

        result = self.sync_handler.handle_file_change(event)

        assert result is True
        assert self.sync_handler.stats["files_modified"] == 1

    def test_handle_file_change_deleted_success(self, tmp_path):
        """Test successful handling of file deletion."""
        test_file = tmp_path / "test.txt"
        event = FileChangeEvent(test_file, ChangeType.DELETED, time.time())

        result = self.sync_handler.handle_file_change(event)

        assert result is True
        assert self.sync_handler.stats["files_deleted"] == 1
        assert len(self.cognitive_system.delete_memories_calls) == 1
        assert self.cognitive_system.delete_memories_calls[0] == str(test_file)

    def test_handle_file_change_deleted_no_result(self, tmp_path):
        """Test handling file deletion when delete returns no result."""
        self.cognitive_system.delete_memories_return_value = None

        test_file = tmp_path / "test.txt"
        event = FileChangeEvent(test_file, ChangeType.DELETED, time.time())

        result = self.sync_handler.handle_file_change(event)

        assert result is False
        assert self.sync_handler.stats["sync_errors"] == 1

    def test_handle_file_change_unknown_type(self, tmp_path):
        """Test handling unknown change type."""
        test_file = tmp_path / "test.txt"

        # Create event with valid enum but patch it to simulate unknown type
        event = FileChangeEvent(test_file, ChangeType.ADDED, time.time())

        # Patch the change_type to something not handled by the sync handler
        with patch.object(event, "change_type", new="UNKNOWN_TYPE"):
            result = self.sync_handler.handle_file_change(event)

        assert result is False
        assert self.sync_handler.stats["sync_errors"] == 1

    def test_handle_file_change_exception(self, tmp_path):
        """Test handling file change when exception occurs."""
        # Make loader_registry raise exception
        self.loader_registry.get_loader_for_file = Mock(
            side_effect=Exception("Test error")
        )

        test_file = tmp_path / "test.txt"
        event = FileChangeEvent(test_file, ChangeType.ADDED, time.time())

        result = self.sync_handler.handle_file_change(event)

        assert result is False
        assert self.sync_handler.stats["sync_errors"] == 1

    def test_atomic_file_reload_success(self, tmp_path):
        """Test successful atomic file reload operation."""
        loader = MockMemoryLoader("test", [".txt"])
        memory = create_mock_memory()
        loader.load_from_source_return_value = [memory]

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = self.sync_handler._atomic_file_reload(test_file, loader)

        assert result is True
        assert len(self.cognitive_system.delete_memories_calls) == 1
        assert len(self.cognitive_system.store_experience_calls) == 1

    def test_atomic_file_reload_no_new_memories(self, tmp_path):
        """Test atomic file reload when no new memories are loaded."""
        loader = MockMemoryLoader("test", [".txt"])
        loader.load_from_source_return_value = []  # No new memories

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = self.sync_handler._atomic_file_reload(test_file, loader)

        assert result is True
        assert len(self.cognitive_system.delete_memories_calls) == 1
        assert len(self.cognitive_system.store_experience_calls) == 0

    def test_atomic_file_reload_partial_store_failure(self, tmp_path):
        """Test atomic file reload with partial memory storage failure."""
        loader = MockMemoryLoader("test", [".txt"])
        memory1 = create_mock_memory("content1")
        memory2 = create_mock_memory("content2")
        loader.load_from_source_return_value = [memory1, memory2]

        # Make second store fail
        store_results = ["success", None]
        self.cognitive_system.store_experience_return_value = None
        self.cognitive_system.store_experience = Mock(side_effect=store_results)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = self.sync_handler._atomic_file_reload(test_file, loader)

        assert result is False  # Partial failure should return False

    def test_atomic_file_reload_store_exception(self, tmp_path):
        """Test atomic file reload with store exception."""
        loader = MockMemoryLoader("test", [".txt"])
        memory = create_mock_memory()
        loader.load_from_source_return_value = [memory]

        # Make store raise exception
        self.cognitive_system.store_experience = Mock(
            side_effect=Exception("Store error")
        )

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = self.sync_handler._atomic_file_reload(test_file, loader)

        assert result is False

    def test_atomic_file_reload_load_exception(self, tmp_path):
        """Test atomic file reload with load exception."""
        loader = MockMemoryLoader("test", [".txt"])
        loader.load_from_source = Mock(side_effect=Exception("Load error"))

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = self.sync_handler._atomic_file_reload(test_file, loader)

        assert result is False

    def test_simple_file_reload_success(self, tmp_path):
        """Test successful simple file reload operation."""
        loader = MockMemoryLoader("test", [".txt"])
        memory = create_mock_memory()
        loader.load_from_source_return_value = [memory]

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = self.sync_handler._simple_file_reload(test_file, loader)

        assert result is True
        assert len(self.cognitive_system.delete_memories_calls) == 1
        assert len(self.cognitive_system.store_experience_calls) == 1

    def test_simple_file_reload_no_new_memories(self, tmp_path):
        """Test simple file reload when no new memories are loaded."""
        loader = MockMemoryLoader("test", [".txt"])
        loader.load_from_source_return_value = []

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = self.sync_handler._simple_file_reload(test_file, loader)

        assert result is True
        assert len(self.cognitive_system.delete_memories_calls) == 1
        assert len(self.cognitive_system.store_experience_calls) == 0

    def test_simple_file_reload_partial_failure(self, tmp_path):
        """Test simple file reload with partial storage failure."""
        loader = MockMemoryLoader("test", [".txt"])
        memory1 = create_mock_memory("content1")
        memory2 = create_mock_memory("content2")
        loader.load_from_source_return_value = [memory1, memory2]

        # Make second store fail
        store_results = ["success", None]
        self.cognitive_system.store_experience = Mock(side_effect=store_results)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = self.sync_handler._simple_file_reload(test_file, loader)

        assert result is False

    def test_simple_file_reload_exception(self, tmp_path):
        """Test simple file reload with exception."""
        loader = MockMemoryLoader("test", [".txt"])
        loader.load_from_source = Mock(side_effect=Exception("Load error"))

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = self.sync_handler._simple_file_reload(test_file, loader)

        assert result is False

    def test_get_sync_statistics(self):
        """Test getting sync statistics."""
        stats = self.sync_handler.get_sync_statistics()

        assert isinstance(stats, dict)
        assert "files_added" in stats
        assert "files_modified" in stats
        assert "files_deleted" in stats
        assert "sync_errors" in stats
        assert "last_sync_time" in stats

        # Verify initial values
        assert stats["files_added"] == 0
        assert stats["files_modified"] == 0
        assert stats["files_deleted"] == 0
        assert stats["sync_errors"] == 0
        assert stats["last_sync_time"] is None

    def test_reset_statistics(self):
        """Test resetting sync statistics."""
        # Set some non-zero values
        self.sync_handler.stats["files_added"] = 5
        self.sync_handler.stats["sync_errors"] = 2
        self.sync_handler.stats["last_sync_time"] = time.time()

        self.sync_handler.reset_statistics()

        stats = self.sync_handler.get_sync_statistics()
        assert stats["files_added"] == 0
        assert stats["files_modified"] == 0
        assert stats["files_deleted"] == 0
        assert stats["sync_errors"] == 0
        assert stats["last_sync_time"] is None

    def test_get_supported_file_types(self):
        """Test getting supported file types."""
        loader1 = MockMemoryLoader("test1", [".txt", ".md"])
        loader2 = MockMemoryLoader("test2", [".html"])

        self.loader_registry.register_loader("test1", loader1)
        self.loader_registry.register_loader("test2", loader2)

        file_types = self.sync_handler.get_supported_file_types()

        assert file_types == {".txt", ".md", ".html"}

    def test_is_file_supported_true(self, tmp_path):
        """Test file support detection for supported file."""
        loader = MockMemoryLoader("test", [".txt"])
        self.loader_registry.register_loader("test", loader)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        assert self.sync_handler.is_file_supported(test_file) is True

    def test_is_file_supported_false(self, tmp_path):
        """Test file support detection for unsupported file."""
        test_file = tmp_path / "test.xyz"
        test_file.write_text("test content")

        assert self.sync_handler.is_file_supported(test_file) is False

    def test_statistics_tracking_across_operations(self, tmp_path):
        """Test that statistics are properly tracked across operations."""
        loader = MockMemoryLoader("test", [".txt"])
        memory = create_mock_memory()
        loader.load_from_source_return_value = [memory]
        self.loader_registry.register_loader("test", loader)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # Perform different operations
        add_event = FileChangeEvent(test_file, ChangeType.ADDED, time.time())
        modify_event = FileChangeEvent(test_file, ChangeType.MODIFIED, time.time())
        delete_event = FileChangeEvent(test_file, ChangeType.DELETED, time.time())

        self.sync_handler.handle_file_change(add_event)
        self.sync_handler.handle_file_change(modify_event)
        self.sync_handler.handle_file_change(delete_event)

        stats = self.sync_handler.get_sync_statistics()
        assert stats["files_added"] == 1
        assert stats["files_modified"] == 1
        assert stats["files_deleted"] == 1
        assert stats["sync_errors"] == 0
        assert stats["last_sync_time"] is not None

    def test_error_counting(self, tmp_path):
        """Test that errors are properly counted."""
        # Create scenario that will cause errors
        self.loader_registry.get_loader_for_file = Mock(
            side_effect=Exception("Test error")
        )

        test_file = tmp_path / "test.txt"
        event = FileChangeEvent(test_file, ChangeType.ADDED, time.time())

        # Execute multiple failing operations
        self.sync_handler.handle_file_change(event)
        self.sync_handler.handle_file_change(event)

        stats = self.sync_handler.get_sync_statistics()
        assert stats["sync_errors"] == 2
        assert stats["files_added"] == 0


class TestFileSyncError:
    """Test cases for FileSyncError exception."""

    def test_file_sync_error_creation(self):
        """Test FileSyncError creation and inheritance."""
        error = FileSyncError("Test error message")

        assert isinstance(error, Exception)
        assert str(error) == "Test error message"

    def test_file_sync_error_with_cause(self):
        """Test FileSyncError with underlying cause."""
        try:
            raise ValueError("Original error")
        except ValueError as e:
            sync_error = FileSyncError("Sync failed")
            sync_error.__cause__ = e

        assert isinstance(sync_error, Exception)
        assert sync_error.__cause__ is not None
        assert isinstance(sync_error.__cause__, ValueError)
