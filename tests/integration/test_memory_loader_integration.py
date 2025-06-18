"""
Integration tests for memory loader functionality with the cognitive system.

Tests the complete workflow from memory loading through the CognitiveSystem interface
to storage backends, verifying end-to-end functionality and component integration.
"""

import time
from unittest.mock import Mock

import pytest

from cognitive_memory.core.cognitive_system import CognitiveMemorySystem
from cognitive_memory.core.config import CognitiveConfig, SystemConfig
from cognitive_memory.core.memory import CognitiveMemory
from cognitive_memory.loaders.markdown_loader import MarkdownMemoryLoader
from tests.factory_utils import (
    MockActivationEngine,
    MockBridgeDiscovery,
    MockConnectionGraph,
    MockEmbeddingProvider,
    MockMemoryStorage,
    MockVectorStorage,
)


@pytest.mark.slow
@pytest.mark.integration
class TestMemoryLoaderIntegration:
    """Integration tests for memory loader with cognitive system."""

    @pytest.fixture
    def test_config(self):
        """Create test configuration for memory loading."""
        return CognitiveConfig(
            max_tokens_per_chunk=200,
            code_block_lines=5,
            strength_floor=0.1,
            hierarchical_weight=0.8,
            sequential_weight=0.6,
            associative_weight=0.4,
            semantic_alpha=0.4,
            lexical_beta=0.3,
            structural_gamma=0.2,
            explicit_delta=0.1,
        )

    @pytest.fixture
    def mock_components(self):
        """Create mock components for integration testing."""
        embedding_provider = MockEmbeddingProvider(vector_size=384)
        vector_storage = MockVectorStorage()
        memory_storage = MockMemoryStorage()
        connection_graph = MockConnectionGraph()
        activation_engine = MockActivationEngine()
        bridge_discovery = MockBridgeDiscovery()

        return {
            "embedding_provider": embedding_provider,
            "vector_storage": vector_storage,
            "memory_storage": memory_storage,
            "connection_graph": connection_graph,
            "activation_engine": activation_engine,
            "bridge_discovery": bridge_discovery,
        }

    @pytest.fixture
    def cognitive_system(self, mock_components, test_config):
        """Create cognitive system with mock components."""
        system_config = SystemConfig.from_env()
        system_config.cognitive = test_config

        return CognitiveMemorySystem(config=system_config, **mock_components)

    @pytest.fixture
    def markdown_loader(self, test_config):
        """Create markdown memory loader."""
        return MarkdownMemoryLoader(test_config)

    @pytest.fixture
    def sample_markdown_file(self, tmp_path):
        """Create sample markdown file for testing."""
        content = """# API Documentation

This document describes the REST API endpoints.

## Authentication

All API calls require authentication using API keys.

### API Key Format

API keys should be included in the Authorization header:

```http
Authorization: Bearer YOUR_API_KEY
```

### Rate Limiting

API calls are limited to 1000 requests per hour.

## Endpoints

### GET /users

Retrieve user information from the system.

#### Parameters

- `id`: User ID (required)
- `format`: Response format (optional)

#### Example

```bash
curl -H "Authorization: Bearer token" \\
     https://api.example.com/users?id=123
```

### POST /users

Create a new user in the system.

#### Request Body

```json
{
  "name": "John Doe",
  "email": "john@example.com"
}
```

## Error Handling

The API returns standard HTTP status codes:

- 200: Success
- 400: Bad Request
- 401: Unauthorized
- 500: Internal Server Error

## Best Practices

1. Always validate input parameters
2. Use HTTPS for all API calls
3. Implement proper error handling
4. Cache responses when appropriate

## Troubleshooting

### Common Issues

**Authentication Errors**: Check your API key format.

**Rate Limiting**: Implement exponential backoff.

**Timeout Errors**: Increase request timeout values.
"""

        md_file = tmp_path / "api_docs.md"
        md_file.write_text(content)
        return str(md_file)

    def test_cognitive_system_load_memories_success(
        self, cognitive_system, markdown_loader, sample_markdown_file
    ):
        """Test successful memory loading through cognitive system."""
        # Test the complete integration
        results = cognitive_system.load_memories_from_source(
            markdown_loader, sample_markdown_file
        )

        # Verify results structure
        assert results["success"] is True
        assert results["memories_loaded"] > 0
        assert results["connections_created"] >= 0
        assert results["processing_time"] > 0
        assert "hierarchy_distribution" in results
        assert results["error"] is None

        # Verify memories were stored
        assert cognitive_system.memory_storage.call_counts["store"] > 0
        assert cognitive_system.vector_storage.call_counts["store"] > 0

        # Verify memory distribution
        distribution = results["hierarchy_distribution"]
        assert "L0" in distribution
        assert "L1" in distribution
        assert "L2" in distribution
        assert sum(distribution.values()) == results["memories_loaded"]

        # Verify connections were attempted
        if results["connections_created"] > 0:
            assert cognitive_system.connection_graph.call_counts["add"] > 0

    def test_cognitive_system_load_memories_invalid_source(
        self, cognitive_system, markdown_loader
    ):
        """Test memory loading with invalid source."""
        results = cognitive_system.load_memories_from_source(
            markdown_loader, "/nonexistent/file.md"
        )

        # Should fail gracefully
        assert results["success"] is False
        assert "error" in results
        assert results["memories_loaded"] == 0
        assert results["connections_created"] == 0

        # No storage operations should have occurred
        assert cognitive_system.memory_storage.call_counts["store"] == 0
        assert cognitive_system.vector_storage.call_counts["store"] == 0

    def test_cognitive_system_memory_encoding_integration(
        self, cognitive_system, markdown_loader, sample_markdown_file
    ):
        """Test that memories are properly encoded during loading."""
        # Load memories
        results = cognitive_system.load_memories_from_source(
            markdown_loader, sample_markdown_file
        )

        assert results["success"] is True

        # Verify embedding provider was called
        assert cognitive_system.embedding_provider.call_count > 0

        # Verify stored vectors have correct metadata
        stored_metadata = cognitive_system.vector_storage.stored_metadata
        assert len(stored_metadata) == results["memories_loaded"]

        for _memory_id, metadata in stored_metadata.items():
            assert "memory_id" in metadata
            assert "content" in metadata
            assert "hierarchy_level" in metadata
            assert "timestamp" in metadata
            assert "source_type" in metadata
            assert metadata["source_type"] == "loaded"

    def test_cognitive_system_connection_graph_integration(
        self, cognitive_system, markdown_loader, sample_markdown_file
    ):
        """Test that connections are properly stored in connection graph."""
        # Load memories
        results = cognitive_system.load_memories_from_source(
            markdown_loader, sample_markdown_file
        )

        assert results["success"] is True

        if results["connections_created"] > 0:
            # Verify connection graph was used
            assert cognitive_system.connection_graph.call_counts["add"] > 0

            # Verify connection strengths and types are stored
            assert len(cognitive_system.connection_graph.connection_strengths) > 0
            assert len(cognitive_system.connection_graph.connection_types) > 0

            # Check connection types are valid
            for (
                connection_type
            ) in cognitive_system.connection_graph.connection_types.values():
                assert connection_type in ["hierarchical", "sequential", "associative"]

    def test_cognitive_system_error_handling_storage_failure(
        self, cognitive_system, markdown_loader, sample_markdown_file
    ):
        """Test error handling when storage operations fail."""
        # Mock storage failure
        cognitive_system.memory_storage.store_memory = Mock(return_value=False)

        results = cognitive_system.load_memories_from_source(
            markdown_loader, sample_markdown_file
        )

        # Should handle storage failures gracefully
        assert results["success"] is True  # Loading itself succeeds
        assert results["memories_failed"] > 0  # But some memories failed to store
        assert results["memories_loaded"] == 0  # No memories successfully stored

    def test_cognitive_system_error_handling_encoding_failure(
        self, cognitive_system, markdown_loader, sample_markdown_file
    ):
        """Test error handling when encoding fails."""
        # Mock encoding failure
        cognitive_system.embedding_provider.encode = Mock(
            side_effect=RuntimeError("Encoding failed")
        )

        results = cognitive_system.load_memories_from_source(
            markdown_loader, sample_markdown_file
        )

        # Should handle encoding failures gracefully
        assert results["success"] is True  # Loading attempts succeed
        assert results["memories_failed"] > 0  # But memories fail to store
        assert results["memories_loaded"] == 0

    def test_cognitive_system_error_handling_loader_failure(
        self, cognitive_system, markdown_loader, sample_markdown_file
    ):
        """Test error handling when loader fails."""
        # Mock loader failure
        markdown_loader.load_from_source = Mock(
            side_effect=RuntimeError("Loader failed")
        )

        results = cognitive_system.load_memories_from_source(
            markdown_loader, sample_markdown_file
        )

        # Should handle loader failures gracefully
        assert results["success"] is False
        assert "error" in results
        assert "Loader failed" in results["error"]
        assert results["memories_loaded"] == 0

    def test_cognitive_system_metadata_preservation(
        self, cognitive_system, markdown_loader, sample_markdown_file
    ):
        """Test that memory metadata is preserved through the pipeline."""
        results = cognitive_system.load_memories_from_source(
            markdown_loader, sample_markdown_file
        )

        assert results["success"] is True

        # Check stored memories have proper metadata
        stored_memories = cognitive_system.memory_storage.stored_memories

        for memory in stored_memories.values():
            # Verify core memory properties
            assert memory.id
            assert memory.content
            assert memory.hierarchy_level in [0, 1, 2]
            assert memory.timestamp is not None

            # Verify metadata from loader is preserved
            assert "title" in memory.metadata
            assert "source_path" in memory.metadata
            assert "loader_type" in memory.metadata
            assert memory.metadata["loader_type"] == "markdown"

            # Verify linguistic features are preserved
            if "linguistic_features" in memory.metadata:
                features = memory.metadata["linguistic_features"]
                assert isinstance(features, dict)
                assert all(
                    key in features
                    for key in [
                        "noun_ratio",
                        "verb_ratio",
                        "imperative_score",
                        "code_fraction",
                    ]
                )

    def test_cognitive_system_performance_with_large_document(
        self, cognitive_system, markdown_loader, tmp_path
    ):
        """Test system performance with larger documents."""
        # Create a larger document
        large_content = """# Large Document

This is a comprehensive documentation with many sections.

""" + "\n\n".join(
            [
                f"""## Section {i}

This is section {i} with detailed information about topic {i}.

### Subsection {i}.1

More details about section {i} subsection 1.

```python
def function_{i}():
    return "Section {i} function"
```

### Subsection {i}.2

Additional information for section {i} subsection 2.

#### Examples for Section {i}

1. Example {i}.1: Basic usage
2. Example {i}.2: Advanced usage
3. Example {i}.3: Error handling

"""
                for i in range(1, 21)
            ]
        )  # 20 sections

        large_file = tmp_path / "large_doc.md"
        large_file.write_text(large_content)

        start_time = time.time()
        results = cognitive_system.load_memories_from_source(
            markdown_loader, str(large_file)
        )
        processing_time = time.time() - start_time

        # Verify successful processing
        assert results["success"] is True
        assert results["memories_loaded"] > 50  # Should create many memories
        assert results["processing_time"] < 30  # Should complete in reasonable time
        assert processing_time < 30  # Cross-check timing

        # Verify good distribution across hierarchy levels
        distribution = results["hierarchy_distribution"]
        assert distribution["L0"] > 0  # Concepts
        assert distribution["L1"] > 0  # Contexts
        assert distribution["L2"] > 0  # Episodes


@pytest.mark.slow
@pytest.mark.integration
class TestMemoryLoaderSystemIntegration:
    """Test memory loader integration with real system components."""

    @pytest.fixture
    def system_config(self, tmp_path):
        """Create system configuration for integration testing."""
        config = SystemConfig.from_env()
        config.database.path = str(tmp_path / "test_cognitive_memory.db")
        config.cognitive.max_tokens_per_chunk = 150
        return config

    def test_end_to_end_workflow_with_retrieval(self, tmp_path, system_config):
        """Test complete workflow: load → store → retrieve."""
        # Create test markdown file
        content = """# Machine Learning Guide

## Neural Networks

Neural networks are computational models inspired by biological neurons.

### Backpropagation

Backpropagation is the key learning algorithm for neural networks.

```python
def backprop(network, input_data, target):
    # Forward pass
    output = network.forward(input_data)

    # Backward pass
    network.backward(target - output)
    return output
```

## Deep Learning

Deep learning uses multi-layer neural networks.

### Convolutional Networks

CNNs are specialized for image processing tasks.

### Recurrent Networks

RNNs are designed for sequence processing tasks.
"""

        md_file = tmp_path / "ml_guide.md"
        md_file.write_text(content)

        # Create system with mock components for controlled testing
        embedding_provider = MockEmbeddingProvider(vector_size=384)
        vector_storage = MockVectorStorage()
        memory_storage = MockMemoryStorage()
        connection_graph = MockConnectionGraph()
        activation_engine = MockActivationEngine()
        bridge_discovery = MockBridgeDiscovery()

        system = CognitiveMemorySystem(
            embedding_provider=embedding_provider,
            vector_storage=vector_storage,
            memory_storage=memory_storage,
            connection_graph=connection_graph,
            activation_engine=activation_engine,
            bridge_discovery=bridge_discovery,
            config=system_config,
        )

        # Create loader
        loader = MarkdownMemoryLoader(system_config.cognitive)

        # Test loading
        load_results = system.load_memories_from_source(loader, str(md_file))

        assert load_results["success"] is True
        assert load_results["memories_loaded"] > 0

        # Prepare mock search results for retrieval test
        stored_memories = list(memory_storage.stored_memories.values())
        mock_search_results = [
            type("SearchResult", (), {"memory": memory, "similarity_score": 0.8})()
            for memory in stored_memories[:3]
        ]
        vector_storage.search_results = mock_search_results

        # Test retrieval
        retrieval_results = system.retrieve_memories(
            query="neural networks learning",
            types=["core", "peripheral"],
            max_results=10,
        )

        # Verify retrieval works
        assert isinstance(retrieval_results, dict)
        assert "core" in retrieval_results
        assert "peripheral" in retrieval_results

        # Should have some results (from mock data)
        total_retrieved = sum(len(memories) for memories in retrieval_results.values())
        if total_retrieved > 0:
            # Verify retrieved memories have proper structure
            for _memory_type, memories in retrieval_results.items():
                for memory in memories:
                    assert isinstance(memory, CognitiveMemory)
                    assert memory.content
                    assert memory.hierarchy_level in [0, 1, 2]

    def test_memory_loader_with_system_statistics(self, tmp_path, system_config):
        """Test that memory loading updates system statistics correctly."""
        # Create simple test file
        content = """# Test Document

## Section 1

Content for section 1.

## Section 2

Content for section 2.
"""

        md_file = tmp_path / "test_doc.md"
        md_file.write_text(content)

        # Create system
        system = CognitiveMemorySystem(
            embedding_provider=MockEmbeddingProvider(),
            vector_storage=MockVectorStorage(),
            memory_storage=MockMemoryStorage(),
            connection_graph=MockConnectionGraph(),
            activation_engine=MockActivationEngine(),
            bridge_discovery=MockBridgeDiscovery(),
            config=system_config,
        )

        # Get initial stats
        _initial_stats = system.get_memory_stats()

        # Load memories
        loader = MarkdownMemoryLoader(system_config.cognitive)
        load_results = system.load_memories_from_source(loader, str(md_file))

        assert load_results["success"] is True

        # Get updated stats
        updated_stats = system.get_memory_stats()

        # Verify stats are updated
        assert isinstance(updated_stats, dict)
        assert "memory_counts" in updated_stats
        assert "timestamp" in updated_stats

        # Verify system config is present
        assert "system_config" in updated_stats
        config = updated_stats["system_config"]
        assert "activation_threshold" in config
        assert "max_activations" in config


@pytest.mark.slow
@pytest.mark.integration
class TestMemoryLoaderErrorScenarios:
    """Test error handling scenarios in memory loader integration."""

    @pytest.fixture
    def error_test_system(self, tmp_path):
        """Create system for error testing."""
        config = SystemConfig.from_env()
        config.database.path = str(tmp_path / "error_test.db")

        return CognitiveMemorySystem(
            embedding_provider=MockEmbeddingProvider(),
            vector_storage=MockVectorStorage(),
            memory_storage=MockMemoryStorage(),
            connection_graph=MockConnectionGraph(),
            activation_engine=MockActivationEngine(),
            bridge_discovery=MockBridgeDiscovery(),
            config=config,
        )

    def test_invalid_loader_type(self, error_test_system, tmp_path):
        """Test handling of invalid loader types."""

        # Create a loader that doesn't implement the interface properly
        class InvalidLoader:
            def validate_source(self, source_path):
                return True

            # Missing required methods: load_from_source, extract_connections, get_supported_extensions

        invalid_loader = InvalidLoader()

        # This should fail gracefully because the loader doesn't implement the full interface
        results = error_test_system.load_memories_from_source(
            invalid_loader, "/fake/path"
        )

        # Should return error response instead of raising exception
        assert results["success"] is False
        assert "error" in results
        assert results["memories_loaded"] == 0
        assert results["connections_created"] == 0

    def test_corrupted_source_file(self, error_test_system, tmp_path):
        """Test handling of corrupted or invalid source files."""
        # Create corrupted file
        corrupted_file = tmp_path / "corrupted.md"
        corrupted_file.write_bytes(b"\x80\x81\x82\x83")  # Invalid UTF-8

        loader = MarkdownMemoryLoader(CognitiveConfig())

        # Should fail validation
        results = error_test_system.load_memories_from_source(
            loader, str(corrupted_file)
        )

        assert results["success"] is False
        assert "error" in results
        assert results["memories_loaded"] == 0

    def test_permission_denied_file(self, error_test_system, tmp_path):
        """Test handling of files with permission issues."""
        # Create file and test with nonexistent path (simulates permission/access issues)
        nonexistent_file = tmp_path / "nonexistent_dir" / "file.md"

        loader = MarkdownMemoryLoader(CognitiveConfig())

        results = error_test_system.load_memories_from_source(
            loader, str(nonexistent_file)
        )

        assert results["success"] is False
        assert "error" in results
        assert results["memories_loaded"] == 0

    def test_empty_markdown_file(self, error_test_system, tmp_path):
        """Test handling of empty markdown files."""
        empty_file = tmp_path / "empty.md"
        empty_file.write_text("")

        loader = MarkdownMemoryLoader(CognitiveConfig())

        results = error_test_system.load_memories_from_source(loader, str(empty_file))

        # Should succeed but load no memories
        assert results["success"] is True
        assert results["memories_loaded"] == 0
        assert results["connections_created"] == 0

    def test_malformed_markdown_resilience(self, error_test_system, tmp_path):
        """Test system resilience with malformed markdown."""
        malformed_content = """# Valid Header

Normal content here.

### Broken header structure
No content under this

##
Empty header title

Content without proper structure
More content
Even more content

```
Code block without language
def broken():
    pass
```

# Another header with [broken link](

Final content section.
"""

        malformed_file = tmp_path / "malformed.md"
        malformed_file.write_text(malformed_content)

        loader = MarkdownMemoryLoader(CognitiveConfig())

        # Should handle malformed content gracefully
        results = error_test_system.load_memories_from_source(
            loader, str(malformed_file)
        )

        assert results["success"] is True
        # Should still create some memories despite malformed content
        assert results["memories_loaded"] > 0


@pytest.mark.integration
@pytest.mark.slow
class TestMemoryLoaderPerformance:
    """Performance tests for memory loader integration."""

    def test_large_document_processing(self, tmp_path):
        """Test processing of large documents."""
        # Create very large document (this should still complete in reasonable time)
        sections = []
        for i in range(100):  # 100 sections
            sections.append(f"""## Section {i}

This is section {i} with comprehensive documentation about topic {i}.

### Overview of Section {i}

Detailed explanation of concepts in section {i}.

```python
def section_{i}_function():
    '''Function for section {i} processing.'''
    result = process_data_section_{i}()
    return result

class Section{i}Handler:
    def __init__(self):
        self.section_id = {i}

    def handle(self):
        return f"Handled section {{self.section_id}}"
```

### Implementation Notes for Section {i}

1. Key point {i}.1 about implementation
2. Key point {i}.2 about best practices
3. Key point {i}.3 about error handling

### Examples for Section {i}

Example {i}.1: Basic usage
Example {i}.2: Advanced patterns
Example {i}.3: Integration scenarios

""")

        large_content = "# Comprehensive Documentation\n\n" + "\n".join(sections)

        large_file = tmp_path / "large_performance_test.md"
        large_file.write_text(large_content)

        # Create system for performance testing
        config = SystemConfig.from_env()
        config.cognitive.max_tokens_per_chunk = (
            100  # Smaller chunks for more processing
        )

        system = CognitiveMemorySystem(
            embedding_provider=MockEmbeddingProvider(),
            vector_storage=MockVectorStorage(),
            memory_storage=MockMemoryStorage(),
            connection_graph=MockConnectionGraph(),
            activation_engine=MockActivationEngine(),
            bridge_discovery=MockBridgeDiscovery(),
            config=config,
        )

        loader = MarkdownMemoryLoader(config.cognitive)

        # Time the operation
        start_time = time.time()
        results = system.load_memories_from_source(loader, str(large_file))
        processing_time = time.time() - start_time

        # Verify successful processing
        assert results["success"] is True
        assert results["memories_loaded"] > 200  # Should create many memories
        assert processing_time < 60  # Should complete within 1 minute
        assert results["processing_time"] < 60

        # Verify good hierarchy distribution
        distribution = results["hierarchy_distribution"]
        total_memories = sum(distribution.values())
        assert total_memories == results["memories_loaded"]

        # Should have reasonable distribution across levels
        assert distribution["L0"] > 0
        assert distribution["L1"] > 0
        assert distribution["L2"] > 0

    def test_connection_extraction_performance(self, tmp_path):
        """Test performance of connection extraction with many memories."""
        # Create document designed to generate many connections
        content = """# Related Topics Documentation

## User Authentication
Implement secure login and user management systems.

## Database Security
Protect user data with encryption and access controls.

## Session Management
Handle user sessions and authentication tokens securely.

## API Security
Secure API endpoints with proper authentication.

## Password Handling
Implement secure password storage and validation.

## Access Control
Define user permissions and role-based access.

## Security Auditing
Monitor and log security-related events.

## Encryption Standards
Use industry-standard encryption algorithms.

## Token Management
Handle JWT tokens and refresh mechanisms.

## Security Testing
Test security implementations thoroughly.

## Vulnerability Assessment
Regular security vulnerability scanning.

## Compliance Requirements
Meet industry security compliance standards.
"""

        connections_file = tmp_path / "connections_test.md"
        connections_file.write_text(content)

        system = CognitiveMemorySystem(
            embedding_provider=MockEmbeddingProvider(),
            vector_storage=MockVectorStorage(),
            memory_storage=MockMemoryStorage(),
            connection_graph=MockConnectionGraph(),
            activation_engine=MockActivationEngine(),
            bridge_discovery=MockBridgeDiscovery(),
            config=SystemConfig.from_env(),
        )

        loader = MarkdownMemoryLoader(CognitiveConfig())

        start_time = time.time()
        results = system.load_memories_from_source(loader, str(connections_file))
        processing_time = time.time() - start_time

        # Verify processing completed efficiently
        assert results["success"] is True
        assert (
            processing_time < 30
        )  # Should complete quickly even with many connections

        # Should create connections between related security topics
        assert results["connections_created"] > 0
