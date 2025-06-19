"""
Unit tests for interface compatibility and backward compatibility.

Tests the extended MemoryLoader and CognitiveSystem interfaces to ensure
backward compatibility is maintained and new upsert functionality works correctly.
"""

import uuid
from unittest.mock import MagicMock

import pytest

from cognitive_memory.core.config import CognitiveConfig
from cognitive_memory.core.interfaces import CognitiveSystem, MemoryLoader
from cognitive_memory.core.memory import CognitiveMemory
from cognitive_memory.loaders.markdown_loader import MarkdownMemoryLoader


class TestMemoryLoaderInterface:
    """Test suite for MemoryLoader interface extensions."""

    def test_memory_loader_abstract_methods_unchanged(self):
        """Test that existing abstract methods are unchanged."""
        # Check that the core abstract methods still exist
        abstract_methods = {
            "validate_source",
            "load_from_source",
            "extract_connections",
            "get_supported_extensions",
        }

        loader_abstracts = {
            method
            for method in dir(MemoryLoader)
            if getattr(getattr(MemoryLoader, method), "__isabstractmethod__", False)
        }

        # Ensure all original abstract methods are still present
        for method in abstract_methods:
            assert method in loader_abstracts, (
                f"Abstract method {method} missing from MemoryLoader"
            )

    def test_upsert_memories_default_implementation(self):
        """Test that upsert_memories has default implementation that raises NotImplementedError."""

        class TestLoader(MemoryLoader):
            def validate_source(self, source_path: str) -> bool:
                return True

            def load_from_source(
                self, source_path: str, **kwargs
            ) -> list[CognitiveMemory]:
                return []

            def extract_connections(
                self, memories: list[CognitiveMemory]
            ) -> list[tuple[str, str, float, str]]:
                return []

            def get_supported_extensions(self) -> list[str]:
                return [".test"]

        loader = TestLoader()
        memories = [CognitiveMemory(str(uuid.uuid4()), "test", 1, 1.0, {})]

        with pytest.raises(
            NotImplementedError, match="Subclasses must implement upsert_memories"
        ):
            loader.upsert_memories(memories)

    def test_memory_loader_concrete_implementation_still_works(self):
        """Test that existing concrete loaders still work without modification."""
        config = CognitiveConfig()

        # Test that MarkdownMemoryLoader can still be instantiated
        loader = MarkdownMemoryLoader(config)

        # Test that core methods are accessible
        assert hasattr(loader, "validate_source")
        assert hasattr(loader, "load_from_source")
        assert hasattr(loader, "extract_connections")
        assert hasattr(loader, "get_supported_extensions")
        assert hasattr(loader, "upsert_memories")

        # Test that extensions list still works
        extensions = loader.get_supported_extensions()
        assert isinstance(extensions, list)
        assert ".md" in extensions or ".markdown" in extensions


class TestCognitiveSystemInterface:
    """Test suite for CognitiveSystem interface extensions."""

    def test_cognitive_system_abstract_methods_unchanged(self):
        """Test that existing abstract methods are unchanged."""
        # Check that the core abstract methods still exist
        existing_methods = {
            "store_experience",
            "retrieve_memories",
            "consolidate_memories",
            "get_memory_stats",
            "load_memories_from_source",
        }

        system_abstracts = {
            method
            for method in dir(CognitiveSystem)
            if getattr(getattr(CognitiveSystem, method), "__isabstractmethod__", False)
        }

        # Ensure all original abstract methods are still present
        for method in existing_methods:
            assert method in system_abstracts, (
                f"Abstract method {method} missing from CognitiveSystem"
            )

    def test_upsert_memories_abstract_method_added(self):
        """Test that upsert_memories is properly added as abstract method."""
        system_abstracts = {
            method
            for method in dir(CognitiveSystem)
            if getattr(getattr(CognitiveSystem, method), "__isabstractmethod__", False)
        }

        assert "upsert_memories" in system_abstracts, (
            "upsert_memories should be abstract in CognitiveSystem"
        )

    def test_cognitive_system_concrete_implementation_requirements(self):
        """Test that concrete implementations must implement upsert_memories."""

        class IncompleteCognitiveSystem(CognitiveSystem):
            # Implement all other abstract methods but not upsert_memories
            def store_experience(self, text: str, context=None) -> str:
                return "test_id"

            def retrieve_memories(self, query: str, types=None, max_results=20):
                return {}

            def consolidate_memories(self):
                pass

            def get_memory_stats(self):
                return {}

            def load_memories_from_source(
                self, source_path: str, loader_type: str = None
            ):
                return []

            # Missing: upsert_memories

        # Should not be able to instantiate without implementing upsert_memories
        with pytest.raises(TypeError, match="abstract.*upsert_memories"):
            IncompleteCognitiveSystem()


class TestMarkdownLoaderCompatibility:
    """Test suite for MarkdownMemoryLoader backward compatibility."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CognitiveConfig()

    @pytest.fixture
    def mock_cognitive_system(self):
        """Create mock cognitive system."""
        mock = MagicMock()
        mock.store_memory.return_value = True
        mock.upsert_memories.return_value = {
            "success": True,
            "updated": 2,
            "inserted": 1,
        }
        return mock

    def test_markdown_loader_initialization_unchanged(self, config):
        """Test that MarkdownMemoryLoader initialization works as before."""
        # Should work without cognitive_system parameter
        loader = MarkdownMemoryLoader(config)
        assert loader.config == config
        assert loader.cognitive_system is None

        # Should also work with cognitive_system parameter
        mock_system = MagicMock()
        loader = MarkdownMemoryLoader(config, mock_system)
        assert loader.cognitive_system == mock_system

    def test_markdown_loader_core_methods_unchanged(self, config):
        """Test that core methods work as before."""
        loader = MarkdownMemoryLoader(config)

        # validate_source should work
        assert not loader.validate_source("/nonexistent/path")

        # get_supported_extensions should work
        extensions = loader.get_supported_extensions()
        assert isinstance(extensions, list)
        assert len(extensions) > 0

    def test_markdown_loader_upsert_with_cognitive_system(
        self, config, mock_cognitive_system
    ):
        """Test that upsert_memories works when cognitive_system is provided."""
        loader = MarkdownMemoryLoader(config, mock_cognitive_system)
        memories = [
            CognitiveMemory(str(uuid.uuid4()), "content1", 1, 1.0, {}),
            CognitiveMemory(str(uuid.uuid4()), "content2", 1, 1.0, {}),
        ]

        result = loader.upsert_memories(memories)

        assert result is True
        mock_cognitive_system.upsert_memories.assert_called_once_with(memories)

    def test_markdown_loader_upsert_without_cognitive_system(self, config):
        """Test that upsert_memories fails gracefully without cognitive_system."""
        loader = MarkdownMemoryLoader(config)
        memories = [CognitiveMemory(str(uuid.uuid4()), "content", 1, 1.0, {})]

        result = loader.upsert_memories(memories)

        assert result is False

    def test_markdown_loader_upsert_fallback_behavior(
        self, config, mock_cognitive_system
    ):
        """Test that upsert_memories falls back to store_memory when upsert fails."""
        # Configure mock to fail upsert but succeed store_memory
        mock_cognitive_system.upsert_memories.return_value = False
        mock_cognitive_system.store_memory.return_value = True

        loader = MarkdownMemoryLoader(config, mock_cognitive_system)
        memories = [CognitiveMemory(str(uuid.uuid4()), "content", 1, 1.0, {})]

        result = loader.upsert_memories(memories)

        assert result is True
        mock_cognitive_system.upsert_memories.assert_called_once_with(memories)
        mock_cognitive_system.store_memory.assert_called_once_with(memories[0])


class TestInterfaceEvolution:
    """Test suite for interface evolution and extensibility."""

    def test_new_loader_can_implement_upsert(self):
        """Test that new loaders can properly implement upsert functionality."""

        class TestUpsertLoader(MemoryLoader):
            def __init__(self):
                self.call_count = 0

            def validate_source(self, source_path: str) -> bool:
                return True

            def load_from_source(
                self, source_path: str, **kwargs
            ) -> list[CognitiveMemory]:
                return []

            def extract_connections(
                self, memories: list[CognitiveMemory]
            ) -> list[tuple[str, str, float, str]]:
                return []

            def get_supported_extensions(self) -> list[str]:
                return [".test"]

            def upsert_memories(self, memories: list[CognitiveMemory]) -> bool:
                self.call_count += 1
                return len(memories) > 0

        loader = TestUpsertLoader()
        memories = [CognitiveMemory(str(uuid.uuid4()), "test", 1, 1.0, {})]

        result = loader.upsert_memories(memories)

        assert result is True
        assert loader.call_count == 1

    def test_interface_method_signatures_correct(self):
        """Test that interface method signatures are correctly defined."""
        import inspect

        # Test MemoryLoader.upsert_memories signature
        upsert_sig = inspect.signature(MemoryLoader.upsert_memories)
        assert len(upsert_sig.parameters) == 2  # self + memories
        assert "memories" in upsert_sig.parameters
        assert upsert_sig.return_annotation is bool

        # Test CognitiveSystem.upsert_memories signature
        system_upsert_sig = inspect.signature(CognitiveSystem.upsert_memories)
        assert len(system_upsert_sig.parameters) == 2  # self + memories
        assert "memories" in system_upsert_sig.parameters
        # Return type should be dict[str, Any] but inspect shows it differently in Python
        # Just check it's not bool (to distinguish from MemoryLoader version)
        assert system_upsert_sig.return_annotation is not bool

    def test_interface_extensibility_maintained(self):
        """Test that interfaces can still be extended in the future."""

        # This test ensures our changes don't break the ability to add more methods
        class FutureMemoryLoader(MemoryLoader):
            def validate_source(self, source_path: str) -> bool:
                return True

            def load_from_source(
                self, source_path: str, **kwargs
            ) -> list[CognitiveMemory]:
                return []

            def extract_connections(
                self, memories: list[CognitiveMemory]
            ) -> list[tuple[str, str, float, str]]:
                return []

            def get_supported_extensions(self) -> list[str]:
                return []

            def upsert_memories(self, memories: list[CognitiveMemory]) -> bool:
                return True

            # Future method addition
            def future_method(self) -> str:
                return "future functionality"

        loader = FutureMemoryLoader()
        assert loader.future_method() == "future functionality"
        assert loader.upsert_memories([]) is True


class TestErrorScenarios:
    """Test suite for error scenarios and edge cases."""

    def test_upsert_empty_memory_list(self):
        """Test upsert behavior with empty memory list."""
        config = CognitiveConfig()
        mock_system = MagicMock()
        mock_system.upsert_memories.return_value = {
            "success": True,
            "updated": 0,
            "inserted": 0,
        }

        loader = MarkdownMemoryLoader(config, mock_system)
        result = loader.upsert_memories([])

        assert result is True
        mock_system.upsert_memories.assert_called_once_with([])

    def test_upsert_with_none_memories(self):
        """Test upsert behavior with None input."""
        config = CognitiveConfig()
        mock_system = MagicMock()

        loader = MarkdownMemoryLoader(config, mock_system)

        # Should handle gracefully and return False
        result = loader.upsert_memories(None)
        assert result is False

    def test_interface_documentation_preserved(self):
        """Test that method documentation is properly preserved."""
        assert MemoryLoader.upsert_memories.__doc__ is not None
        assert "Update existing memories" in MemoryLoader.upsert_memories.__doc__
        assert "backward-compatible" in MemoryLoader.upsert_memories.__doc__

        assert CognitiveSystem.upsert_memories.__doc__ is not None
        assert "Update existing memories" in CognitiveSystem.upsert_memories.__doc__
        assert "deterministic IDs" in CognitiveSystem.upsert_memories.__doc__
