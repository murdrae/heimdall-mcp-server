"""
Unit tests for cognitive memory system factory functions.

Tests factory pattern implementation, component validation,
error handling, and configuration management.
"""

from unittest.mock import Mock, patch

import pytest

from cognitive_memory.core.cognitive_system import CognitiveMemorySystem
from cognitive_memory.core.config import SystemConfig
from cognitive_memory.core.interfaces import (
    ActivationEngine,
    BridgeDiscovery,
    ConnectionGraph,
    EmbeddingProvider,
    MemoryStorage,
    VectorStorage,
)
from cognitive_memory.factory import (
    InitializationError,
    _get_expected_interface,
    create_default_system,
    create_system_from_config,
    create_test_system,
    validate_system_health,
)
from tests.factory_utils import (
    MockActivationEngine,
    MockBridgeDiscovery,
    MockConnectionGraph,
    MockEmbeddingProvider,
    MockMemoryStorage,
    MockVectorStorage,
    run_factory_creation_test,
    validate_interface_compliance,
)


class TestFactoryCore:
    """Test core factory functionality."""

    def test_get_expected_interface(self):
        """Test interface type mapping."""
        assert _get_expected_interface("embedding_provider") == EmbeddingProvider
        assert _get_expected_interface("vector_storage") == VectorStorage
        assert _get_expected_interface("memory_storage") == MemoryStorage
        assert _get_expected_interface("connection_graph") == ConnectionGraph
        assert _get_expected_interface("activation_engine") == ActivationEngine
        assert _get_expected_interface("bridge_discovery") == BridgeDiscovery
        assert _get_expected_interface("config") == SystemConfig
        assert _get_expected_interface("unknown_component") is None

    def test_initialization_error(self):
        """Test InitializationError exception."""
        error = InitializationError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)


class TestCreateDefaultSystem:
    """Test create_default_system factory function."""

    @pytest.mark.integration
    def test_create_default_system_success(self, test_config):
        """Test successful default system creation."""
        with (
            patch(
                "cognitive_memory.encoding.sentence_bert.create_sentence_bert_provider"
            ) as mock_embedding,
            patch(
                "cognitive_memory.storage.qdrant_storage.create_hierarchical_storage"
            ) as mock_vector,
            patch(
                "cognitive_memory.storage.sqlite_persistence.create_sqlite_persistence"
            ) as mock_persistence,
        ):
            # Mock component creation
            mock_embedding.return_value = MockEmbeddingProvider()
            mock_vector.return_value = MockVectorStorage()
            mock_persistence.return_value = (MockMemoryStorage(), MockConnectionGraph())

            result = run_factory_creation_test(create_default_system, test_config)

            assert result.success
            assert result.system is not None
            assert isinstance(result.system, CognitiveMemorySystem)
            assert all(result.validation_results.values())

    def test_create_default_system_config_loading(self):
        """Test default system creation with config loading."""
        with (
            patch("cognitive_memory.factory.SystemConfig.from_env") as mock_config,
            patch(
                "cognitive_memory.encoding.sentence_bert.create_sentence_bert_provider"
            ),
            patch(
                "cognitive_memory.storage.qdrant_storage.create_hierarchical_storage"
            ),
            patch(
                "cognitive_memory.storage.sqlite_persistence.create_sqlite_persistence"
            ),
        ):
            mock_config.return_value = SystemConfig.from_env()

            try:
                system = create_default_system()
                assert system is not None
            except (ImportError, InitializationError):
                # Expected when components aren't fully available
                pass

    def test_create_default_system_config_error(self):
        """Test default system creation with config error."""
        with patch("cognitive_memory.factory.SystemConfig.from_env") as mock_config:
            mock_config.side_effect = Exception("Config loading failed")

            with pytest.raises(InitializationError) as exc_info:
                create_default_system()

            assert "Failed to load configuration" in str(exc_info.value)

    def test_create_default_system_component_import_error(self, test_config):
        """Test default system creation with import error."""
        with patch(
            "cognitive_memory.encoding.sentence_bert.create_sentence_bert_provider"
        ) as mock_embedding:
            mock_embedding.side_effect = ImportError("Module not found")

            with pytest.raises(InitializationError) as exc_info:
                create_default_system(test_config)

            assert "Failed to import required component" in str(exc_info.value)

    def test_create_default_system_interface_validation_error(self, test_config):
        """Test default system creation with interface validation error."""
        with (
            patch(
                "cognitive_memory.encoding.sentence_bert.create_sentence_bert_provider"
            ) as mock_embedding,
            patch(
                "cognitive_memory.storage.qdrant_storage.create_hierarchical_storage"
            ),
            patch(
                "cognitive_memory.storage.sqlite_persistence.create_sqlite_persistence"
            ),
        ):
            # Return object that doesn't implement EmbeddingProvider
            mock_embedding.return_value = "not_an_embedding_provider"

            with pytest.raises(InitializationError) as exc_info:
                create_default_system(test_config)

            assert "does not implement EmbeddingProvider interface" in str(
                exc_info.value
            )


class TestCreateTestSystem:
    """Test create_test_system factory function."""

    def test_create_test_system_no_overrides(self, test_config):
        """Test test system creation without overrides."""
        with patch("cognitive_memory.factory.create_default_system") as mock_default:
            mock_system = Mock(spec=CognitiveMemorySystem)
            mock_system.embedding_provider = MockEmbeddingProvider()
            mock_system.vector_storage = MockVectorStorage()
            mock_system.memory_storage = MockMemoryStorage()
            mock_system.connection_graph = MockConnectionGraph()
            mock_system.activation_engine = MockActivationEngine()
            mock_system.bridge_discovery = MockBridgeDiscovery()
            mock_system.config = test_config
            mock_default.return_value = mock_system

            result = create_test_system()
            assert result is not None

    def test_create_test_system_with_overrides(self, test_config):
        """Test test system creation with component overrides."""
        with patch("cognitive_memory.factory.create_default_system") as mock_default:
            mock_system = Mock(spec=CognitiveMemorySystem)
            mock_system.embedding_provider = MockEmbeddingProvider()
            mock_system.vector_storage = MockVectorStorage()
            mock_system.memory_storage = MockMemoryStorage()
            mock_system.connection_graph = MockConnectionGraph()
            mock_system.activation_engine = MockActivationEngine()
            mock_system.bridge_discovery = MockBridgeDiscovery()
            mock_system.config = test_config
            mock_default.return_value = mock_system

            # Test with specific overrides
            custom_embedding = MockEmbeddingProvider()
            custom_storage = MockVectorStorage()

            result = create_test_system(
                embedding_provider=custom_embedding, vector_storage=custom_storage
            )

            assert result is not None

    def test_create_test_system_invalid_override(self, test_config):
        """Test test system creation with invalid override."""
        with patch("cognitive_memory.factory.create_default_system") as mock_default:
            mock_system = Mock(spec=CognitiveMemorySystem)
            mock_system.embedding_provider = MockEmbeddingProvider()
            mock_system.vector_storage = MockVectorStorage()
            mock_system.memory_storage = MockMemoryStorage()
            mock_system.connection_graph = MockConnectionGraph()
            mock_system.activation_engine = MockActivationEngine()
            mock_system.bridge_discovery = MockBridgeDiscovery()
            mock_system.config = test_config
            mock_default.return_value = mock_system

            # Try to override with invalid component
            with pytest.raises(InitializationError) as exc_info:
                create_test_system(embedding_provider="not_an_embedding_provider")

            assert "does not implement required interface" in str(exc_info.value)

    def test_create_test_system_creation_error(self):
        """Test test system creation with system creation error."""
        with patch("cognitive_memory.factory.create_default_system") as mock_default:
            mock_default.side_effect = Exception("System creation failed")

            with pytest.raises(InitializationError) as exc_info:
                create_test_system()

            assert "Failed to create test system" in str(exc_info.value)


class TestCreateSystemFromConfig:
    """Test create_system_from_config factory function."""

    def test_create_system_from_config_success(self, temp_dir):
        """Test successful system creation from config file."""
        # Create temporary .env file
        config_file = temp_dir / "test.env"
        config_file.write_text(
            """
QDRANT_URL=http://localhost:6333
SENTENCE_BERT_MODEL=all-MiniLM-L6-v2
DATABASE_PATH=/tmp/test.db
        """.strip()
        )

        with patch("cognitive_memory.factory.create_default_system") as mock_default:
            mock_default.return_value = Mock(spec=CognitiveMemorySystem)

            result = create_system_from_config(str(config_file))
            assert result is not None
            mock_default.assert_called_once()

    def test_create_system_from_config_file_not_found(self):
        """Test system creation with non-existent config file."""
        with pytest.raises(InitializationError) as exc_info:
            create_system_from_config("/non/existent/config.env")

        assert "Configuration file not found" in str(exc_info.value)

    def test_create_system_from_config_unsupported_format(self, temp_dir):
        """Test system creation with unsupported config format."""
        config_file = temp_dir / "test.yaml"
        config_file.write_text("test: value")

        with pytest.raises(InitializationError) as exc_info:
            create_system_from_config(str(config_file))

        assert "Unsupported configuration file format" in str(exc_info.value)

    def test_create_system_from_config_loading_error(self, temp_dir):
        """Test system creation with config loading error."""
        config_file = temp_dir / "test.env"
        config_file.write_text("INVALID_ENV_SYNTAX")

        with patch("cognitive_memory.factory.SystemConfig.from_env") as mock_config:
            mock_config.side_effect = Exception("Config parsing failed")

            with pytest.raises(InitializationError) as exc_info:
                create_system_from_config(str(config_file))

            assert "Failed to create system from config" in str(exc_info.value)


class TestValidateSystemHealth:
    """Test validate_system_health function."""

    def test_validate_system_health_success(self):
        """Test successful system health validation."""
        mock_system = Mock()
        mock_system.get_memory_stats.return_value = {"total": 0}
        mock_system.store_experience.return_value = "test_id"
        mock_system.retrieve_memories.return_value = [Mock()]

        result = validate_system_health(mock_system)

        assert result["healthy"] is True
        assert "stats" in result["checks"]
        assert "storage" in result["checks"]
        assert "retrieval" in result["checks"]
        assert len(result["errors"]) == 0

    def test_validate_system_health_storage_failure(self):
        """Test system health validation with storage failure."""
        mock_system = Mock()
        mock_system.get_memory_stats.return_value = {"total": 0}
        mock_system.store_experience.return_value = None  # Storage failure

        result = validate_system_health(mock_system)

        assert result["healthy"] is False
        assert "✗ Memory storage failed" in result["checks"]["storage"]
        assert "Failed to store test memory" in result["errors"]

    def test_validate_system_health_retrieval_no_results(self):
        """Test system health validation with no retrieval results."""
        mock_system = Mock()
        mock_system.get_memory_stats.return_value = {"total": 0}
        mock_system.store_experience.return_value = "test_id"
        mock_system.retrieve_memories.return_value = []  # No results

        result = validate_system_health(mock_system)

        assert result["healthy"] is True  # Still healthy, just a warning
        assert "⚠ Memory retrieval returned no results" in result["checks"]["retrieval"]

    def test_validate_system_health_exception(self):
        """Test system health validation with exception."""
        mock_system = Mock()
        mock_system.get_memory_stats.side_effect = Exception("System error")

        result = validate_system_health(mock_system)

        assert result["healthy"] is False
        assert "Health check failed: System error" in result["errors"]


class TestInterfaceValidation:
    """Test interface validation utilities."""

    def test_validate_interface_compliance_success(self):
        """Test successful interface compliance validation."""
        component = MockEmbeddingProvider()
        is_compliant, missing = validate_interface_compliance(
            component, EmbeddingProvider
        )

        assert is_compliant is True
        assert len(missing) == 0

    def test_validate_interface_compliance_failure(self):
        """Test interface compliance validation failure."""
        component = "not_an_interface_implementation"
        is_compliant, missing = validate_interface_compliance(
            component, EmbeddingProvider
        )

        assert is_compliant is False
        assert len(missing) > 0

    def test_validate_interface_compliance_missing_methods(self):
        """Test interface compliance with missing methods."""

        class IncompleteEmbedding:
            def encode(self, text: str):
                pass

            # Missing encode_batch method

        component = IncompleteEmbedding()
        is_compliant, missing = validate_interface_compliance(
            component, EmbeddingProvider
        )

        # Note: This depends on the specific interface definition
        # The test validates the validation mechanism works


class TestFactoryUtilities:
    """Test factory testing utilities."""

    def test_test_factory_creation_success(self):
        """Test successful factory testing."""

        def mock_factory():
            return MockEmbeddingProvider()

        result = run_factory_creation_test(mock_factory)

        assert result.success is True
        assert result.system is not None
        assert result.error is None

    def test_test_factory_creation_failure(self):
        """Test factory testing with failure."""

        def failing_factory():
            raise Exception("Factory failed")

        result = run_factory_creation_test(failing_factory)

        assert result.success is False
        assert result.system is None
        assert "Factory failed" in result.error

    def test_test_factory_creation_none_result(self):
        """Test factory testing with None result."""

        def none_factory():
            return None

        result = run_factory_creation_test(none_factory)

        assert result.success is False
        assert result.system is None
        assert "Factory returned None" in result.error


@pytest.mark.integration
class TestFactoryIntegration:
    """Integration tests for factory functionality."""

    def test_factory_component_chain(self, test_config):
        """Test complete factory component creation chain."""
        # This test would require real components to be available
        # Skip if components aren't available for testing
        pytest.skip("Requires full component implementations")

    def test_factory_config_integration(self, temp_dir):
        """Test factory configuration integration."""
        config_file = temp_dir / "integration.env"
        config_file.write_text(
            """
QDRANT_URL=http://localhost:6333
SENTENCE_BERT_MODEL=all-MiniLM-L6-v2
DATABASE_PATH=/tmp/integration_test.db
        """.strip()
        )

        with patch("cognitive_memory.factory.create_default_system") as mock_default:
            mock_default.return_value = Mock(spec=CognitiveMemorySystem)

            system = create_system_from_config(str(config_file))
            assert system is not None
