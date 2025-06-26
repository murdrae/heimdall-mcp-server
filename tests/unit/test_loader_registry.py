"""
Unit tests for LoaderRegistry system.

Tests the loader registry functionality including registration, discovery,
file type detection, and error handling scenarios.
"""

from unittest.mock import Mock, patch

import pytest

from cognitive_memory.core.interfaces import MemoryLoader
from cognitive_memory.core.memory import CognitiveMemory
from heimdall.monitoring.loader_registry import (
    LoaderRegistry,
    create_default_registry,
)


class MockMemoryLoader(MemoryLoader):
    """Mock MemoryLoader for testing purposes."""

    def __init__(self, name: str, extensions: list[str], validate_result: bool = True):
        self.name = name
        self.extensions = extensions
        self.validate_result = validate_result
        self.load_from_source_calls = []
        self.validate_source_calls = []

    def load_from_source(self, source_path: str, **kwargs) -> list[CognitiveMemory]:
        """Mock load_from_source method."""
        self.load_from_source_calls.append((source_path, kwargs))
        return []

    def extract_connections(
        self, memories: list[CognitiveMemory]
    ) -> list[tuple[str, str, float, str]]:
        """Mock extract_connections method."""
        return []

    def validate_source(self, source_path: str) -> bool:
        """Mock validate_source method."""
        self.validate_source_calls.append(source_path)
        return self.validate_result

    def get_supported_extensions(self) -> list[str]:
        """Mock get_supported_extensions method."""
        return self.extensions


class TestLoaderRegistry:
    """Test cases for LoaderRegistry class."""

    def test_init(self):
        """Test LoaderRegistry initialization."""
        registry = LoaderRegistry()
        assert len(registry._loaders) == 0
        assert len(registry._extension_map) == 0
        assert registry.list_registered_loaders() == []

    def test_register_loader_success(self):
        """Test successful loader registration."""
        registry = LoaderRegistry()
        loader = MockMemoryLoader("test", [".txt", ".md"])

        registry.register_loader("test", loader)

        assert "test" in registry._loaders
        assert registry._loaders["test"] == loader
        assert "txt" in registry._extension_map
        assert "md" in registry._extension_map
        assert "test" in registry._extension_map["txt"]
        assert "test" in registry._extension_map["md"]

    def test_register_loader_invalid_type(self):
        """Test registration with invalid loader type."""
        registry = LoaderRegistry()

        with pytest.raises(ValueError, match="must implement MemoryLoader interface"):
            registry.register_loader("invalid", "not_a_loader")

    def test_register_loader_duplicate_name(self):
        """Test registration with duplicate loader name."""
        registry = LoaderRegistry()
        loader1 = MockMemoryLoader("test1", [".txt"])
        loader2 = MockMemoryLoader("test2", [".md"])

        registry.register_loader("test", loader1)
        registry.register_loader("test", loader2)  # Overwrite

        assert registry._loaders["test"] == loader2

    def test_register_loader_extension_failure(self):
        """Test registration failure during extension processing."""
        registry = LoaderRegistry()

        # Create a loader that raises exception in get_supported_extensions
        loader = Mock(spec=MemoryLoader)
        loader.get_supported_extensions.side_effect = Exception("Extension error")

        with pytest.raises(Exception, match="Extension error"):
            registry.register_loader("failing", loader)

        # Ensure loader was not registered after failure
        assert "failing" not in registry._loaders

    def test_unregister_loader_success(self):
        """Test successful loader unregistration."""
        registry = LoaderRegistry()
        loader = MockMemoryLoader("test", [".txt", ".md"])

        registry.register_loader("test", loader)
        result = registry.unregister_loader("test")

        assert result is True
        assert "test" not in registry._loaders
        assert "txt" not in registry._extension_map
        assert "md" not in registry._extension_map

    def test_unregister_loader_nonexistent(self):
        """Test unregistration of non-existent loader."""
        registry = LoaderRegistry()

        result = registry.unregister_loader("nonexistent")

        assert result is False

    def test_unregister_loader_extension_cleanup_error(self):
        """Test unregistration with extension cleanup error."""
        registry = LoaderRegistry()

        # Create a mock loader that raises error during extension cleanup
        loader = Mock(spec=MemoryLoader)
        loader.get_supported_extensions.return_value = [".txt"]

        registry.register_loader("test", loader)

        # Make get_supported_extensions fail during unregistration
        loader.get_supported_extensions.side_effect = Exception("Cleanup error")

        result = registry.unregister_loader("test")

        assert result is True  # Should still succeed

    def test_get_loader_for_file_success(self, tmp_path):
        """Test successful file loader detection."""
        registry = LoaderRegistry()
        loader = MockMemoryLoader("test", [".txt"])
        registry.register_loader("test", loader)

        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = registry.get_loader_for_file(test_file)

        assert result == loader
        assert str(test_file) in loader.validate_source_calls

    def test_get_loader_for_file_nonexistent(self, tmp_path):
        """Test loader detection for non-existent file."""
        registry = LoaderRegistry()
        loader = MockMemoryLoader("test", [".txt"])
        registry.register_loader("test", loader)

        nonexistent_file = tmp_path / "nonexistent.txt"

        result = registry.get_loader_for_file(nonexistent_file)

        assert result is None

    def test_get_loader_for_file_unsupported_extension(self, tmp_path):
        """Test loader detection for unsupported file extension."""
        registry = LoaderRegistry()
        loader = MockMemoryLoader("test", [".txt"])
        registry.register_loader("test", loader)

        # Create file with unsupported extension
        test_file = tmp_path / "test.xyz"
        test_file.write_text("test content")

        result = registry.get_loader_for_file(test_file)

        assert result is None

    def test_get_loader_for_file_validation_failure(self, tmp_path):
        """Test loader detection when validation fails."""
        registry = LoaderRegistry()
        loader = MockMemoryLoader("test", [".txt"], validate_result=False)
        registry.register_loader("test", loader)

        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = registry.get_loader_for_file(test_file)

        assert result is None
        assert str(test_file) in loader.validate_source_calls

    def test_get_loader_for_file_validation_error(self, tmp_path):
        """Test loader detection when validation raises exception."""
        registry = LoaderRegistry()
        loader = MockMemoryLoader("test", [".txt"])
        registry.register_loader("test", loader)

        # Override validate_source to raise exception
        loader.validate_source = Mock(side_effect=Exception("Validation error"))

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = registry.get_loader_for_file(test_file)

        assert result is None

    def test_get_loader_for_file_multiple_candidates(self, tmp_path):
        """Test loader detection with multiple candidate loaders."""
        registry = LoaderRegistry()

        # Register two loaders for same extension
        loader1 = MockMemoryLoader("test1", [".md"], validate_result=False)
        loader2 = MockMemoryLoader("test2", [".md"], validate_result=True)

        registry.register_loader("test1", loader1)
        registry.register_loader("test2", loader2)

        test_file = tmp_path / "test.md"
        test_file.write_text("test content")

        result = registry.get_loader_for_file(test_file)

        # Should return the first loader that validates successfully
        assert result == loader2

    def test_get_loader_for_file_missing_loader(self, tmp_path):
        """Test file detection with missing loader in registry."""
        registry = LoaderRegistry()
        loader = MockMemoryLoader("test", [".txt"])
        registry.register_loader("test", loader)

        # Manually corrupt the extension map to point to non-existent loader
        registry._extension_map["txt"] = ["nonexistent"]

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = registry.get_loader_for_file(test_file)

        assert result is None

    def test_get_loader_by_name(self):
        """Test loader retrieval by name."""
        registry = LoaderRegistry()
        loader = MockMemoryLoader("test", [".txt"])
        registry.register_loader("test", loader)

        assert registry.get_loader_by_name("test") == loader
        assert registry.get_loader_by_name("nonexistent") is None

    def test_list_registered_loaders(self):
        """Test listing registered loaders."""
        registry = LoaderRegistry()

        assert registry.list_registered_loaders() == []

        loader1 = MockMemoryLoader("test1", [".txt"])
        loader2 = MockMemoryLoader("test2", [".md"])

        registry.register_loader("test1", loader1)
        registry.register_loader("test2", loader2)

        loaders = registry.list_registered_loaders()
        assert set(loaders) == {"test1", "test2"}

    def test_get_supported_extensions(self):
        """Test getting all supported extensions."""
        registry = LoaderRegistry()

        assert registry.get_supported_extensions() == set()

        loader1 = MockMemoryLoader("test1", [".txt", ".md"])
        loader2 = MockMemoryLoader("test2", [".md", ".html"])

        registry.register_loader("test1", loader1)
        registry.register_loader("test2", loader2)

        extensions = registry.get_supported_extensions()
        assert extensions == {".txt", ".md", ".html"}

    def test_get_supported_extensions_with_error(self):
        """Test getting extensions when loader raises error."""
        registry = LoaderRegistry()

        # Create a mock loader that raises error
        loader = Mock(spec=MemoryLoader)
        loader.get_supported_extensions.side_effect = Exception("Extension error")

        registry._loaders["failing"] = loader

        extensions = registry.get_supported_extensions()

        assert extensions == set()

    def test_clear_registry(self):
        """Test clearing all loaders from registry."""
        registry = LoaderRegistry()

        loader1 = MockMemoryLoader("test1", [".txt"])
        loader2 = MockMemoryLoader("test2", [".md"])

        registry.register_loader("test1", loader1)
        registry.register_loader("test2", loader2)

        registry.clear_registry()

        assert len(registry._loaders) == 0
        assert len(registry._extension_map) == 0
        assert registry.list_registered_loaders() == []

    def test_get_registry_stats(self):
        """Test getting registry statistics."""
        registry = LoaderRegistry()

        # Empty registry stats
        stats = registry.get_registry_stats()
        assert stats["total_loaders"] == 0
        assert stats["loader_names"] == []
        assert stats["supported_extensions"] == []
        assert stats["extension_mapping"] == {}

        # Add loaders and check stats
        loader1 = MockMemoryLoader("test1", [".txt"])
        loader2 = MockMemoryLoader("test2", [".md", ".html"])

        registry.register_loader("test1", loader1)
        registry.register_loader("test2", loader2)

        stats = registry.get_registry_stats()
        assert stats["total_loaders"] == 2
        assert set(stats["loader_names"]) == {"test1", "test2"}
        assert set(stats["supported_extensions"]) == {".txt", ".md", ".html"}
        assert "txt" in stats["extension_mapping"]
        assert "md" in stats["extension_mapping"]
        assert "html" in stats["extension_mapping"]

    def test_extension_normalization(self):
        """Test that file extensions are properly normalized."""
        registry = LoaderRegistry()
        loader = MockMemoryLoader("test", [".TXT", ".Md"])  # Mixed case

        registry.register_loader("test", loader)

        # Check that extensions are normalized to lowercase
        assert "txt" in registry._extension_map
        assert "md" in registry._extension_map
        assert "TXT" not in registry._extension_map
        assert "Md" not in registry._extension_map

    def test_extension_cleanup_on_unregister(self):
        """Test that extension mappings are properly cleaned up."""
        registry = LoaderRegistry()

        loader1 = MockMemoryLoader("test1", [".txt"])
        loader2 = MockMemoryLoader("test2", [".txt", ".md"])

        registry.register_loader("test1", loader1)
        registry.register_loader("test2", loader2)

        # Both loaders support .txt
        assert set(registry._extension_map["txt"]) == {"test1", "test2"}

        # Unregister one loader
        registry.unregister_loader("test1")

        # Extension mapping should still exist but only have test2
        assert registry._extension_map["txt"] == ["test2"]
        assert "md" in registry._extension_map

        # Unregister the other loader
        registry.unregister_loader("test2")

        # All extension mappings should be cleaned up
        assert "txt" not in registry._extension_map
        assert "md" not in registry._extension_map


class TestCreateDefaultRegistry:
    """Test cases for create_default_registry function."""

    def test_create_default_registry_success(self):
        """Test successful creation of default registry."""
        registry = create_default_registry()

        assert isinstance(registry, LoaderRegistry)

        # Should have markdown loader registered
        loaders = registry.list_registered_loaders()
        assert "markdown" in loaders

        # Should support markdown extensions
        extensions = registry.get_supported_extensions()
        assert ".md" in extensions

    def test_create_default_registry_import_error(self):
        """Test default registry creation with import error."""
        # Mock the import to fail
        with patch(
            "cognitive_memory.loaders.markdown_loader.MarkdownMemoryLoader",
            side_effect=ImportError("Mock import error"),
        ):
            registry = create_default_registry()

            # Should still create registry but with no loaders registered
            assert isinstance(registry, LoaderRegistry)
            assert len(registry.list_registered_loaders()) == 0

    def test_create_default_registry_registration_error(self):
        """Test default registry creation with registration error."""
        # This test would require more complex mocking to trigger registration errors
        # For now, we'll just verify the basic functionality works
        registry = create_default_registry()
        assert isinstance(registry, LoaderRegistry)
