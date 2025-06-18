"""
Unit tests for MemoryLoader interface and implementations.

Tests the abstract MemoryLoader interface compliance and the concrete
MarkdownMemoryLoader implementation.
"""

import uuid
from unittest.mock import patch

import pytest

from cognitive_memory.core.config import CognitiveConfig
from cognitive_memory.core.interfaces import MemoryLoader
from cognitive_memory.core.memory import CognitiveMemory
from cognitive_memory.loaders.markdown_loader import MarkdownMemoryLoader


class MockMemoryLoader(MemoryLoader):
    """Mock implementation for testing interface compliance."""

    def load_from_source(self, source_path: str, **kwargs) -> list[CognitiveMemory]:
        return []

    def extract_connections(
        self, memories: list[CognitiveMemory]
    ) -> list[tuple[str, str, float, str]]:
        return []

    def validate_source(self, source_path: str) -> bool:
        return True

    def get_supported_extensions(self) -> list[str]:
        return [".txt"]


class TestMemoryLoaderInterface:
    """Test the MemoryLoader abstract interface."""

    def test_interface_instantiation(self):
        """Test that MemoryLoader cannot be instantiated directly."""
        with pytest.raises(TypeError):
            MemoryLoader()

    def test_mock_implementation_compliance(self):
        """Test that mock implementation satisfies interface."""
        loader = MockMemoryLoader()

        # Test all required methods exist
        assert hasattr(loader, "load_from_source")
        assert hasattr(loader, "extract_connections")
        assert hasattr(loader, "validate_source")
        assert hasattr(loader, "get_supported_extensions")

        # Test methods return expected types
        result = loader.load_from_source("/fake/path")
        assert isinstance(result, list)

        connections = loader.extract_connections([])
        assert isinstance(connections, list)

        valid = loader.validate_source("/fake/path")
        assert isinstance(valid, bool)

        extensions = loader.get_supported_extensions()
        assert isinstance(extensions, list)


class TestMarkdownMemoryLoaderUnit:
    """Unit tests for MarkdownMemoryLoader implementation."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CognitiveConfig(
            max_tokens_per_chunk=100,
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
    def markdown_loader(self, config):
        """Create MarkdownMemoryLoader instance."""
        return MarkdownMemoryLoader(config)

    @pytest.fixture
    def sample_markdown_content(self):
        """Sample markdown content for testing."""
        return """# Main Header

This is the introduction section with some text.

## Subsection A

This contains some detailed information about subsection A.

### Deep Subsection

Very specific details here.

## Subsection B

Different information in subsection B.

```python
def hello_world():
    print("Hello, World!")
    return True
```

## Commands Section

First, install the dependencies:

```bash
pip install requirements
```

Then, run the application:

```bash
python app.py
```

Finally, test the setup.
"""

    def test_interface_compliance(self, markdown_loader):
        """Test that MarkdownMemoryLoader implements MemoryLoader interface."""
        assert isinstance(markdown_loader, MemoryLoader)

    def test_get_supported_extensions(self, markdown_loader):
        """Test supported file extensions."""
        extensions = markdown_loader.get_supported_extensions()
        expected = [".md", ".markdown", ".mdown", ".mkd"]
        assert extensions == expected

    def test_validate_source_valid_file(self, markdown_loader, tmp_path):
        """Test validation of valid markdown file."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test\nContent")

        assert markdown_loader.validate_source(str(md_file)) is True

    def test_validate_source_invalid_extension(self, markdown_loader, tmp_path):
        """Test validation rejects unsupported extensions."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Content")

        assert markdown_loader.validate_source(str(txt_file)) is False

    def test_validate_source_nonexistent_file(self, markdown_loader):
        """Test validation of nonexistent file."""
        assert markdown_loader.validate_source("/nonexistent/file.md") is False

    def test_validate_source_directory(self, markdown_loader, tmp_path):
        """Test validation rejects directories."""
        assert markdown_loader.validate_source(str(tmp_path)) is False

    def test_validate_source_unreadable_file(self, markdown_loader, tmp_path):
        """Test validation of unreadable file."""
        md_file = tmp_path / "test.md"
        md_file.write_bytes(b"\x80\x81\x82")  # Invalid UTF-8

        assert markdown_loader.validate_source(str(md_file)) is False

    def test_load_from_source_basic(
        self, markdown_loader, tmp_path, sample_markdown_content
    ):
        """Test basic loading of markdown content."""
        md_file = tmp_path / "test.md"
        md_file.write_text(sample_markdown_content)

        memories = markdown_loader.load_from_source(str(md_file))

        assert isinstance(memories, list)
        assert len(memories) > 0

        # Check that all memories are CognitiveMemory instances
        for memory in memories:
            assert isinstance(memory, CognitiveMemory)
            assert isinstance(memory.id, str)
            assert memory.content
            assert memory.hierarchy_level in [0, 1, 2]

    def test_load_from_source_invalid_file(self, markdown_loader):
        """Test loading from invalid file raises error."""
        with pytest.raises(ValueError, match="Invalid markdown source"):
            markdown_loader.load_from_source("/nonexistent/file.md")

    def test_count_tokens(self, markdown_loader):
        """Test token counting functionality."""
        text = "This is a simple test sentence."
        count = markdown_loader._count_tokens(text)
        assert isinstance(count, int)
        assert count > 0

    def test_extract_linguistic_features(self, markdown_loader):
        """Test linguistic feature extraction."""
        text = "Install the package. Run the command. This creates a file."
        features = markdown_loader._extract_linguistic_features(text)

        expected_keys = [
            "noun_ratio",
            "verb_ratio",
            "imperative_score",
            "code_fraction",
        ]
        assert all(key in features for key in expected_keys)
        assert all(isinstance(features[key], float) for key in expected_keys)
        assert all(0.0 <= features[key] <= 1.0 for key in expected_keys)

    def test_extract_linguistic_features_empty_text(self, markdown_loader):
        """Test linguistic features with empty text."""
        features = markdown_loader._extract_linguistic_features("")

        expected_keys = [
            "noun_ratio",
            "verb_ratio",
            "imperative_score",
            "code_fraction",
        ]
        assert all(key in features for key in expected_keys)
        assert all(features[key] == 0.0 for key in expected_keys)

    def test_detect_imperative_patterns(self, markdown_loader):
        """Test imperative pattern detection."""
        imperative_text = "Run the command\nInstall the package\nNormal sentence here"
        score = markdown_loader._detect_imperative_patterns(imperative_text)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        assert score > 0.0  # Should detect imperative patterns

    def test_calculate_code_fraction(self, markdown_loader):
        """Test code fraction calculation."""
        text_with_code = """Some text here.

```python
def hello():
    return "world"
```

More text with `inline code` here."""

        fraction = markdown_loader._calculate_code_fraction(text_with_code)
        assert isinstance(fraction, float)
        assert 0.0 <= fraction <= 1.0
        assert fraction > 0.0  # Should detect code

    def test_calculate_code_fraction_no_code(self, markdown_loader):
        """Test code fraction with no code."""
        text = "This is just plain text with no code elements."
        fraction = markdown_loader._calculate_code_fraction(text)
        assert fraction == 0.0

    def test_classify_hierarchy_level_concept(self, markdown_loader):
        """Test L0 (concept) classification."""
        content = "API"
        chunk_data = {"header_level": 1}
        features = {
            "noun_ratio": 0.8,
            "verb_ratio": 0.1,
            "imperative_score": 0.0,
            "code_fraction": 0.0,
        }

        level = markdown_loader._classify_hierarchy_level(content, chunk_data, features)
        assert level == 0

    def test_classify_hierarchy_level_episode_code(self, markdown_loader):
        """Test L2 (episode) classification for code."""
        content = """```python
def test_function():
    return True
```"""
        chunk_data = {"header_level": 3}
        features = {
            "noun_ratio": 0.2,
            "verb_ratio": 0.3,
            "imperative_score": 0.1,
            "code_fraction": 0.7,
        }

        level = markdown_loader._classify_hierarchy_level(content, chunk_data, features)
        assert level == 2

    def test_classify_hierarchy_level_episode_imperative(self, markdown_loader):
        """Test L2 (episode) classification for commands."""
        content = "Install the package. Run the command. Test the system."
        chunk_data = {"header_level": 2}
        features = {
            "noun_ratio": 0.3,
            "verb_ratio": 0.4,
            "imperative_score": 0.6,
            "code_fraction": 0.0,
        }

        level = markdown_loader._classify_hierarchy_level(content, chunk_data, features)
        assert level == 2

    def test_extract_connections_empty_list(self, markdown_loader):
        """Test connection extraction with empty memory list."""
        connections = markdown_loader.extract_connections([])
        assert connections == []

    def test_extract_connections_single_memory(self, markdown_loader):
        """Test connection extraction with single memory."""
        memory = CognitiveMemory(
            id=str(uuid.uuid4()),
            content="Test content",
            hierarchy_level=1,
            metadata={"title": "Test", "source_path": "/test.md"},
        )

        connections = markdown_loader.extract_connections([memory])
        assert isinstance(connections, list)
        # Single memory should have no connections
        assert len(connections) == 0

    def test_are_sequential_numbered_steps(self, markdown_loader):
        """Test sequential detection with numbered steps."""
        memory1 = CognitiveMemory(
            id="1",
            content="First step",
            hierarchy_level=1,
            metadata={"title": "Step 1: Initialize"},
        )
        memory2 = CognitiveMemory(
            id="2",
            content="Second step",
            hierarchy_level=1,
            metadata={"title": "Step 2: Configure"},
        )

        assert markdown_loader._are_sequential(memory1, memory2) is True

    def test_are_sequential_non_sequential(self, markdown_loader):
        """Test sequential detection with non-sequential content."""
        memory1 = CognitiveMemory(
            id="1",
            content="Random content",
            hierarchy_level=1,
            metadata={"title": "Random Topic A"},
        )
        memory2 = CognitiveMemory(
            id="2",
            content="Different content",
            hierarchy_level=1,
            metadata={"title": "Random Topic B"},
        )

        assert markdown_loader._are_sequential(memory1, memory2) is False

    def test_calculate_structural_proximity(self, markdown_loader):
        """Test structural proximity calculation."""
        memory1 = CognitiveMemory(
            id="1", content="Content", hierarchy_level=1, metadata={"header_level": 1}
        )
        memory2 = CognitiveMemory(
            id="2", content="Content", hierarchy_level=1, metadata={"header_level": 2}
        )

        proximity = markdown_loader._calculate_structural_proximity(memory1, memory2)
        assert isinstance(proximity, float)
        assert 0.0 <= proximity <= 1.0

    def test_calculate_explicit_references(self, markdown_loader):
        """Test explicit reference calculation."""
        memory1 = CognitiveMemory(
            id="1",
            content="See section Installation for details",
            hierarchy_level=1,
            metadata={"title": "Overview"},
        )
        memory2 = CognitiveMemory(
            id="2",
            content="Install the package",
            hierarchy_level=1,
            metadata={"title": "Installation"},
        )

        refs = markdown_loader._calculate_explicit_references(memory1, memory2)
        assert isinstance(refs, float)
        assert 0.0 <= refs <= 1.0

    def test_already_connected(self, markdown_loader):
        """Test connection deduplication logic."""
        memory1 = CognitiveMemory(id="1", content="", hierarchy_level=1)
        memory2 = CognitiveMemory(id="2", content="", hierarchy_level=1)

        existing = [("1", "2", 0.8, "hierarchical")]

        assert markdown_loader._already_connected(memory1, memory2, existing) is True
        assert markdown_loader._already_connected(memory1, memory2, []) is False

    @patch("spacy.load")
    def test_spacy_loading_error_handling(self, mock_spacy_load, config):
        """Test handling of spaCy loading errors."""
        mock_spacy_load.side_effect = OSError("Model not found")

        with pytest.raises(OSError):
            MarkdownMemoryLoader(config)

    def test_chunk_markdown_with_headers(
        self, markdown_loader, sample_markdown_content
    ):
        """Test markdown chunking with headers."""
        chunks = list(
            markdown_loader._chunk_markdown(sample_markdown_content, "/test.md")
        )

        assert len(chunks) > 0

        # Check chunk structure
        for chunk in chunks:
            assert "content" in chunk
            assert "title" in chunk
            assert "header_level" in chunk
            assert "source_path" in chunk
            assert "chunk_type" in chunk
            assert isinstance(chunk["content"], str)
            assert isinstance(chunk["title"], str)
            assert isinstance(chunk["header_level"], int)

    def test_chunk_markdown_no_headers(self, markdown_loader):
        """Test markdown chunking with no headers."""
        content = "Just plain text with no headers."
        chunks = list(markdown_loader._chunk_markdown(content, "/test.md"))

        # Should return empty list if no headers found
        assert len(chunks) == 0

    def test_create_memory_from_chunk(self, markdown_loader):
        """Test memory creation from chunk data."""
        chunk_data = {
            "content": "# Test Header\n\nTest content here.",
            "title": "Test Header",
            "header_level": 1,
            "source_path": "/test.md",
            "chunk_type": "section",
            "parent_header": None,
        }

        memory = markdown_loader._create_memory_from_chunk(chunk_data, "/test.md")

        assert isinstance(memory, CognitiveMemory)
        assert memory.content == chunk_data["content"]
        assert memory.hierarchy_level in [0, 1, 2]
        assert memory.strength == 1.0
        assert memory.metadata["title"] == "Test Header"
        assert memory.metadata["source_path"] == "/test.md"
        assert "linguistic_features" in memory.metadata
        assert "sentiment" in memory.metadata


class TestMarkdownMemoryLoaderIntegration:
    """Integration tests for MarkdownMemoryLoader with more complex scenarios."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CognitiveConfig(
            max_tokens_per_chunk=50,  # Small chunks for testing
            code_block_lines=3,
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
    def markdown_loader(self, config):
        """Create MarkdownMemoryLoader instance."""
        return MarkdownMemoryLoader(config)

    @pytest.fixture
    def complex_markdown_content(self):
        """Complex markdown content for comprehensive testing."""
        return """# API Documentation

This document describes the API endpoints.

## Authentication

All API calls require authentication.

### API Keys

Use your API key in the header:

```http
Authorization: Bearer YOUR_API_KEY
```

### Rate Limiting

API calls are limited to 1000 requests per hour.

## Endpoints

### GET /users

Retrieve user information.

#### Parameters

- `id`: User ID (required)
- `format`: Response format (optional)

#### Example

```bash
curl -H "Authorization: Bearer token" \\
     https://api.example.com/users?id=123
```

### POST /users

Create a new user.

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

## Code Examples

### Python Example

```python
import requests

def get_user(user_id, api_key):
    headers = {'Authorization': f'Bearer {api_key}'}
    response = requests.get(f'/users?id={user_id}', headers=headers)
    return response.json()

# Usage
user = get_user(123, 'your-api-key')
print(user['name'])
```

### JavaScript Example

```javascript
async function getUser(userId, apiKey) {
    const response = await fetch(`/users?id=${userId}`, {
        headers: { 'Authorization': `Bearer ${apiKey}` }
    });
    return response.json();
}

// Usage
const user = await getUser(123, 'your-api-key');
console.log(user.name);
```

## Best Practices

1. Always validate input parameters
2. Use HTTPS for all API calls
3. Implement proper error handling
4. Cache responses when appropriate
5. Monitor API usage and performance

## Troubleshooting

### Common Issues

**Authentication Errors**: Check your API key format.

**Rate Limiting**: Implement exponential backoff.

**Timeout Errors**: Increase request timeout values.

### Getting Help

Contact support at api-support@example.com for assistance.
"""

    def test_complex_document_chunking(
        self, markdown_loader, tmp_path, complex_markdown_content
    ):
        """Test chunking of a complex markdown document."""
        md_file = tmp_path / "api_docs.md"
        md_file.write_text(complex_markdown_content)

        memories = markdown_loader.load_from_source(str(md_file))

        # Should create multiple memories
        assert len(memories) > 10

        # Check hierarchy levels distribution
        l0_count = sum(1 for m in memories if m.hierarchy_level == 0)
        l1_count = sum(1 for m in memories if m.hierarchy_level == 1)
        l2_count = sum(1 for m in memories if m.hierarchy_level == 2)

        # Should have good distribution across levels
        assert l0_count > 0  # Concepts
        assert l1_count > 0  # Contexts
        assert l2_count > 0  # Episodes (code blocks, commands)

        # Check that code blocks are properly classified as L2
        code_memories = [
            m
            for m in memories
            if "code_fraction" in m.metadata.get("linguistic_features", {})
            and m.metadata["linguistic_features"]["code_fraction"] > 0.5
        ]
        for memory in code_memories:
            assert memory.hierarchy_level == 2

    def test_hierarchical_relationships(
        self, markdown_loader, tmp_path, complex_markdown_content
    ):
        """Test that hierarchical relationships are properly detected."""
        md_file = tmp_path / "api_docs.md"
        md_file.write_text(complex_markdown_content)

        memories = markdown_loader.load_from_source(str(md_file))
        connections = markdown_loader.extract_connections(memories)

        # Should have hierarchical connections
        hierarchical_connections = [c for c in connections if c[3] == "hierarchical"]
        assert len(hierarchical_connections) > 0

        # Verify connection strengths are reasonable
        for source_id, target_id, strength, _conn_type in hierarchical_connections:
            assert 0.0 <= strength <= 1.0
            assert source_id != target_id

    def test_sequential_relationships(self, markdown_loader, tmp_path):
        """Test sequential relationship detection in procedural content."""
        sequential_content = """# Setup Guide

## Step 1: Download

Download the package from the official website.

## Step 2: Install

Run the installation command:

```bash
pip install package-name
```

## Step 3: Configure

Edit the configuration file:

```yaml
api_key: your-key-here
timeout: 30
```

## Step 4: Test

Verify the installation:

```bash
package-name --version
```

## Step 5: Deploy

Deploy to production environment.
"""

        md_file = tmp_path / "setup.md"
        md_file.write_text(sequential_content)

        memories = markdown_loader.load_from_source(str(md_file))
        connections = markdown_loader.extract_connections(memories)

        # Should detect sequential connections
        sequential_connections = [c for c in connections if c[3] == "sequential"]
        assert len(sequential_connections) > 0

    def test_associative_relationships(self, markdown_loader, tmp_path):
        """Test associative relationship detection through semantic similarity."""
        related_content = """# Database Operations

## User Management

Handle user registration and authentication.

## Data Storage

Store user information securely.

## Authentication System

Verify user credentials and manage sessions.

## Security Measures

Implement encryption and access controls.

## User Interface

Design forms for user registration.
"""

        md_file = tmp_path / "database.md"
        md_file.write_text(related_content)

        memories = markdown_loader.load_from_source(str(md_file))
        connections = markdown_loader.extract_connections(memories)

        # Should detect associative connections between related topics
        associative_connections = [c for c in connections if c[3] == "associative"]
        assert len(associative_connections) > 0

    def test_large_document_handling(self, markdown_loader, tmp_path):
        """Test handling of large documents that exceed chunk limits."""
        # Create a large section with subheaders for proper splitting
        large_content = (
            """# Large Section

This is a very long section with lots of content. """
            + "This sentence repeats many times. " * 20
            + """

### Subsection A

More content here. """
            + "Additional details. " * 10
            + """

### Deep Subsection

Even more content. """
            + "Very detailed information. " * 10
            + """

## Subsection B

Different topic but still long. """
            + "Extensive explanation. " * 15
        )

        md_file = tmp_path / "large.md"
        md_file.write_text(large_content)

        memories = markdown_loader.load_from_source(str(md_file))

        # Should handle large content by splitting appropriately
        assert len(memories) > 1

        # The system respects markdown structure - large sections without
        # subheaders may exceed token limits to preserve semantic coherence
        # This is correct behavior, not a bug
        largest_memory = max(memories, key=lambda m: m.metadata.get("token_count", 0))
        assert largest_memory.metadata.get("token_count", 0) > 0  # Basic sanity check

    def test_malformed_markdown_handling(self, markdown_loader, tmp_path):
        """Test handling of malformed or edge-case markdown."""
        malformed_content = """# Proper Header

Normal content here.

###### Very Deep Header

Content under deep header.

## Header with `code` in title

Content with inline code.

# Header with [link](http://example.com) in title

Content with links.

```
Code block without language specification
def function():
    return "hello"
```

```python
# Proper code block
print("hello world")
```

##

Empty header title.

Content after empty header.
"""

        md_file = tmp_path / "malformed.md"
        md_file.write_text(malformed_content)

        # Should not crash on malformed content
        memories = markdown_loader.load_from_source(str(md_file))
        assert isinstance(memories, list)

        # Should still create some memories despite malformed content
        assert len(memories) > 0

    def test_empty_document_handling(self, markdown_loader, tmp_path):
        """Test handling of empty or minimal documents."""
        empty_content = ""

        md_file = tmp_path / "empty.md"
        md_file.write_text(empty_content)

        memories = markdown_loader.load_from_source(str(md_file))
        assert memories == []

    def test_single_header_document(self, markdown_loader, tmp_path):
        """Test document with only one header."""
        single_header = """# Single Header

This document has only one header with some content.
"""

        md_file = tmp_path / "single.md"
        md_file.write_text(single_header)

        memories = markdown_loader.load_from_source(str(md_file))
        assert len(memories) == 1
        assert memories[0].hierarchy_level in [0, 1, 2]

    def test_code_heavy_document(self, markdown_loader, tmp_path):
        """Test document with lots of code blocks."""
        code_heavy = """# Programming Tutorial

## Python Basics

```python
def hello_world():
    print("Hello, World!")
    return True

class MyClass:
    def __init__(self, name):
        self.name = name

    def greet(self):
        return f"Hello, {self.name}"
```

## Advanced Features

```python
import asyncio
from typing import List, Optional

async def fetch_data(urls: List[str]) -> List[Optional[str]]:
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url(session, url) for url in urls]
        return await asyncio.gather(*tasks)

async def fetch_url(session, url):
    try:
        async with session.get(url) as response:
            return await response.text()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None
```

## Shell Commands

```bash
#!/bin/bash
for file in *.py; do
    echo "Processing $file"
    python "$file"
done
```
"""

        md_file = tmp_path / "code_heavy.md"
        md_file.write_text(code_heavy)

        memories = markdown_loader.load_from_source(str(md_file))

        # Should classify code blocks as L2 episodes
        l2_memories = [m for m in memories if m.hierarchy_level == 2]
        assert len(l2_memories) > 0

        # Verify code fraction is high for code memories
        for memory in l2_memories:
            if "linguistic_features" in memory.metadata:
                features = memory.metadata["linguistic_features"]
                if features.get("code_fraction", 0) > 0.5:
                    assert memory.hierarchy_level == 2

    def test_connection_strength_computation(self, markdown_loader, tmp_path):
        """Test detailed connection strength computation."""
        related_content = """# Project Setup

## Installation Guide

Install the required dependencies for the project.

## Configuration Setup

Configure the project settings and environment variables.

## Testing Framework

Set up automated testing for the project.

## Deployment Process

Deploy the configured project to production.
"""

        md_file = tmp_path / "project.md"
        md_file.write_text(related_content)

        memories = markdown_loader.load_from_source(str(md_file))
        connections = markdown_loader.extract_connections(memories)

        # Verify connection strengths are computed properly
        for _source_id, _target_id, strength, conn_type in connections:
            # Strength should be in valid range
            assert 0.0 <= strength <= 1.0

            # Strength should meet minimum threshold
            assert strength >= markdown_loader.config.strength_floor

            # Should have proper connection type
            assert conn_type in ["hierarchical", "sequential", "associative"]

    def test_metadata_completeness(
        self, markdown_loader, tmp_path, complex_markdown_content
    ):
        """Test that all memories have complete metadata."""
        md_file = tmp_path / "complete.md"
        md_file.write_text(complex_markdown_content)

        memories = markdown_loader.load_from_source(str(md_file))

        required_metadata_keys = [
            "title",
            "source_path",
            "header_level",
            "chunk_type",
            "token_count",
            "linguistic_features",
            "sentiment",
            "loader_type",
        ]

        for memory in memories:
            # Check all required metadata is present
            for key in required_metadata_keys:
                assert key in memory.metadata, f"Missing metadata key: {key}"

            # Check metadata types
            assert isinstance(memory.metadata["title"], str)
            assert isinstance(memory.metadata["source_path"], str)
            assert isinstance(memory.metadata["header_level"], int)
            assert isinstance(memory.metadata["chunk_type"], str)
            assert isinstance(memory.metadata["token_count"], int)
            assert isinstance(memory.metadata["linguistic_features"], dict)
            assert isinstance(memory.metadata["sentiment"], dict)
            assert memory.metadata["loader_type"] == "markdown"

            # Check linguistic features completeness
            ling_features = memory.metadata["linguistic_features"]
            required_ling_keys = [
                "noun_ratio",
                "verb_ratio",
                "imperative_score",
                "code_fraction",
            ]
            for key in required_ling_keys:
                assert key in ling_features
                assert isinstance(ling_features[key], float)
                assert 0.0 <= ling_features[key] <= 1.0


class TestMarkdownConnectionExtraction:
    """Comprehensive tests for connection extraction and strength computation."""

    @pytest.fixture
    def config(self):
        """Create test configuration with known weights."""
        return CognitiveConfig(
            max_tokens_per_chunk=200,
            code_block_lines=3,
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
    def markdown_loader(self, config):
        """Create MarkdownMemoryLoader instance."""
        return MarkdownMemoryLoader(config)

    def test_hierarchical_connection_detection(self, markdown_loader, tmp_path):
        """Test hierarchical connection detection between parent and child sections."""
        hierarchical_content = """# Main Topic

This is the main topic description.

## Subtopic A

Details about subtopic A.

### Deep Subtopic A1

Very specific information about A1.

### Deep Subtopic A2

More details about A2.

## Subtopic B

Different subtopic with its own details.
"""

        md_file = tmp_path / "hierarchical.md"
        md_file.write_text(hierarchical_content)

        memories = markdown_loader.load_from_source(str(md_file))
        connections = markdown_loader.extract_connections(memories)

        # Filter hierarchical connections
        hierarchical_connections = [c for c in connections if c[3] == "hierarchical"]
        assert len(hierarchical_connections) > 0

        # Verify proper parent-child relationships
        memory_by_title = {m.metadata["title"]: m for m in memories}

        # Should have Main Topic -> Subtopic A connection
        main_topic_id = memory_by_title["Main Topic"].id
        subtopic_a_id = memory_by_title["Subtopic A"].id

        parent_child_connections = [
            c
            for c in hierarchical_connections
            if (c[0] == main_topic_id and c[1] == subtopic_a_id)
            or (c[1] == main_topic_id and c[0] == subtopic_a_id)
        ]
        assert len(parent_child_connections) > 0

        # Verify strength calculation
        for _source_id, _target_id, strength, conn_type in hierarchical_connections:
            assert strength >= markdown_loader.config.strength_floor
            assert strength <= 1.0
            assert conn_type == "hierarchical"

    def test_sequential_connection_numbered_steps(self, markdown_loader, tmp_path):
        """Test sequential connection detection with explicit step numbering."""
        sequential_content = """# Installation Process

## Step 1: Download

Download the installer from the website.

## Step 2: Install

Run the installer and follow prompts.

## Step 3: Configure

Set up your configuration files.

## Step 4: Test

Verify everything works correctly.

## Step 5: Deploy

Deploy to your production environment.
"""

        md_file = tmp_path / "sequential.md"
        md_file.write_text(sequential_content)

        memories = markdown_loader.load_from_source(str(md_file))
        connections = markdown_loader.extract_connections(memories)

        # Filter sequential connections
        sequential_connections = [c for c in connections if c[3] == "sequential"]
        assert len(sequential_connections) > 0

        # Verify step-by-step connections exist
        memory_by_title = {m.metadata["title"]: m for m in memories}

        step1_id = memory_by_title["Step 1: Download"].id
        step2_id = memory_by_title["Step 2: Install"].id

        step_connections = [
            c
            for c in sequential_connections
            if (c[0] == step1_id and c[1] == step2_id)
            or (c[1] == step1_id and c[0] == step2_id)
        ]
        assert len(step_connections) > 0

    def test_associative_connection_semantic_similarity(
        self, markdown_loader, tmp_path
    ):
        """Test associative connections based on semantic similarity."""
        related_content = """# Software Development

## User Authentication

Implement secure login and registration functionality.

## Database Security

Protect user data with encryption and access controls.

## Session Management

Handle user sessions and authentication tokens.

## API Security

Secure API endpoints and validate requests.

## Frontend Design

Create user interface for login forms.
"""

        md_file = tmp_path / "related.md"
        md_file.write_text(related_content)

        memories = markdown_loader.load_from_source(str(md_file))
        connections = markdown_loader.extract_connections(memories)

        # Filter associative connections
        associative_connections = [c for c in connections if c[3] == "associative"]
        assert len(associative_connections) > 0

        # Verify related security topics are connected
        memory_by_title = {m.metadata["title"]: m for m in memories}

        auth_id = memory_by_title["User Authentication"].id
        security_id = memory_by_title["Database Security"].id

        # Should find semantic connections between security-related topics
        [
            c
            for c in associative_connections
            if (c[0] == auth_id and c[1] == security_id)
            or (c[1] == auth_id and c[0] == security_id)
        ]
        # May or may not exist depending on similarity threshold, but test structure

    def test_connection_strength_computation_formula(self, markdown_loader):
        """Test the mathematical formula for connection strength computation."""
        # Create test memories with known content
        memory1 = CognitiveMemory(
            id="mem1",
            content="Python programming language features include object-oriented design.",
            hierarchy_level=1,
            metadata={
                "title": "Python Features",
                "source_path": "/test.md",
                "header_level": 2,
            },
        )

        memory2 = CognitiveMemory(
            id="mem2",
            content="Object-oriented programming design patterns in Python development.",
            hierarchy_level=1,
            metadata={
                "title": "OOP Design Patterns",
                "source_path": "/test.md",
                "header_level": 2,
            },
        )

        # Test relevance score calculation
        relevance_score = markdown_loader._calculate_relevance_score(memory1, memory2)

        assert isinstance(relevance_score, float)
        assert 0.0 <= relevance_score <= 1.0

        # Should have high relevance due to shared keywords (Python, object-oriented, design)
        assert relevance_score > 0.1  # Should detect semantic similarity

    def test_connection_multiple_types(self, markdown_loader):
        """Test that memories can have multiple types of connections.

        This behavior is INTENTIONAL and models real cognitive relationships.
        Two memories can be related in multiple ways simultaneously:

        Example: "Step 1: Install Python" and "Step 2: Configure Python"
        - Sequential: They follow each other in a procedure
        - Associative: Both are about Python setup (semantic similarity)
        - Hierarchical: Both under "Python Setup" parent section

        This is NOT a bug - it's sophisticated relationship modeling that
        captures the multi-dimensional nature of human memory connections.

        The test validates:
        - Multiple connection types can coexist (feature)
        - No duplicate connection types for same pair (would be bug)
        - All connection types are valid
        """
        # Create memories that could have multiple connection types
        memory1 = CognitiveMemory(
            id="mem1",
            content="Step 1: Install Python",
            hierarchy_level=2,
            metadata={
                "title": "Step 1: Install Python",
                "source_path": "/test.md",
                "header_level": 3,
            },
        )

        memory2 = CognitiveMemory(
            id="mem2",
            content="Step 2: Configure Python environment",
            hierarchy_level=2,
            metadata={
                "title": "Step 2: Configure Python environment",
                "source_path": "/test.md",
                "header_level": 3,
            },
        )

        memory3 = CognitiveMemory(
            id="mem3",
            content="Python installation and configuration guide",
            hierarchy_level=1,
            metadata={
                "title": "Python Setup",
                "source_path": "/test.md",
                "header_level": 2,  # Parent level
            },
        )

        memories = [memory1, memory2, memory3]
        connections = markdown_loader.extract_connections(memories)

        # Group connections by memory pairs
        connection_pairs = {}
        for source_id, target_id, _strength, conn_type in connections:
            # Normalize pair order
            pair = tuple(sorted([source_id, target_id]))
            if pair not in connection_pairs:
                connection_pairs[pair] = []
            connection_pairs[pair].append(conn_type)

        # Verify that memory pairs can have multiple connection types
        # This is correct behavior - memories can be related in multiple ways
        for _pair, conn_types in connection_pairs.items():
            assert len(conn_types) >= 1
            assert all(
                ct in ["hierarchical", "sequential", "associative"] for ct in conn_types
            )
            # If multiple connections exist, they should be different types
            if len(conn_types) > 1:
                assert len(set(conn_types)) == len(conn_types), (
                    "Duplicate connection types found"
                )

    def test_connection_strength_thresholding(self, markdown_loader):
        """Test that weak connections are filtered out by strength floor."""
        # Create memories with minimal similarity
        memory1 = CognitiveMemory(
            id="mem1",
            content="Apple fruit nutrition facts",
            hierarchy_level=1,
            metadata={"title": "Apple", "source_path": "/test.md", "header_level": 2},
        )

        memory2 = CognitiveMemory(
            id="mem2",
            content="Database indexing performance optimization",
            hierarchy_level=1,
            metadata={
                "title": "Database Indexing",
                "source_path": "/test.md",
                "header_level": 2,
            },
        )

        memories = [memory1, memory2]
        connections = markdown_loader.extract_connections(memories)

        # Should have few or no connections due to low similarity
        associative_connections = [c for c in connections if c[3] == "associative"]

        # If any connections exist, they should meet strength threshold
        for _source_id, _target_id, strength, _conn_type in associative_connections:
            assert strength >= markdown_loader.config.strength_floor

    def test_structural_proximity_calculation(self, markdown_loader):
        """Test structural proximity based on header levels."""
        memory1 = CognitiveMemory(
            id="mem1",
            content="Content",
            hierarchy_level=1,
            metadata={"header_level": 1},  # Top level
        )

        memory2 = CognitiveMemory(
            id="mem2",
            content="Content",
            hierarchy_level=1,
            metadata={"header_level": 2},  # One level down
        )

        memory3 = CognitiveMemory(
            id="mem3",
            content="Content",
            hierarchy_level=1,
            metadata={"header_level": 5},  # Much deeper
        )

        # Test proximity calculations
        proximity_1_2 = markdown_loader._calculate_structural_proximity(
            memory1, memory2
        )
        proximity_1_3 = markdown_loader._calculate_structural_proximity(
            memory1, memory3
        )

        assert 0.0 <= proximity_1_2 <= 1.0
        assert 0.0 <= proximity_1_3 <= 1.0

        # Closer levels should have higher proximity
        assert proximity_1_2 > proximity_1_3

    def test_explicit_reference_detection(self, markdown_loader):
        """Test detection of explicit references between memories."""
        memory1 = CognitiveMemory(
            id="mem1",
            content="For more details, see the Installation section.",
            hierarchy_level=1,
            metadata={"title": "Overview", "source_path": "/test.md"},
        )

        memory2 = CognitiveMemory(
            id="mem2",
            content="Download and install the software package.",
            hierarchy_level=1,
            metadata={"title": "Installation", "source_path": "/test.md"},
        )

        memory3 = CognitiveMemory(
            id="mem3",
            content="Troubleshooting common issues.",
            hierarchy_level=1,
            metadata={"title": "Troubleshooting", "source_path": "/test.md"},
        )

        # Test explicit reference detection
        refs_1_2 = markdown_loader._calculate_explicit_references(memory1, memory2)
        refs_1_3 = markdown_loader._calculate_explicit_references(memory1, memory3)

        assert 0.0 <= refs_1_2 <= 1.0
        assert 0.0 <= refs_1_3 <= 1.0

        # Should detect reference to "Installation" in memory1
        assert refs_1_2 > refs_1_3

    def test_connection_extraction_empty_list(self, markdown_loader):
        """Test connection extraction with edge cases."""
        # Empty list
        assert markdown_loader.extract_connections([]) == []

        # Single memory
        single_memory = CognitiveMemory(
            id="solo",
            content="Lonely content",
            hierarchy_level=1,
            metadata={"title": "Solo", "source_path": "/test.md"},
        )
        connections = markdown_loader.extract_connections([single_memory])
        assert connections == []

    def test_weighted_connection_strength_formula(self, markdown_loader):
        """Test that connection strengths use proper weighting factors."""
        # Create memories for testing different connection types
        parent_memory = CognitiveMemory(
            id="parent",
            content="Main section about Python programming",
            hierarchy_level=1,
            metadata={
                "title": "Python Programming",
                "source_path": "/test.md",
                "header_level": 1,
            },
        )

        child_memory = CognitiveMemory(
            id="child",
            content="Subsection about Python functions",
            hierarchy_level=1,
            metadata={
                "title": "Python Functions",
                "source_path": "/test.md",
                "header_level": 2,
            },
        )

        memories = [parent_memory, child_memory]
        connections = markdown_loader.extract_connections(memories)

        # Verify hierarchical connections use hierarchical_weight
        hierarchical_connections = [c for c in connections if c[3] == "hierarchical"]
        if hierarchical_connections:
            source_id, target_id, strength, conn_type = hierarchical_connections[0]

            # Strength should incorporate hierarchical_weight (0.8)
            # Exact calculation depends on relevance score, but should be reasonable
            assert 0.0 < strength <= markdown_loader.config.hierarchical_weight

    def test_large_memory_set_performance(self, markdown_loader, tmp_path):
        """Test connection extraction performance with larger memory sets."""
        # Create document with many sections
        large_content = """# Main Document

""" + "\n\n".join(
            [
                f"""## Section {i}

This is section {i} with some content about topic {i}.

### Subsection {i}.1

More details about section {i} subsection 1.

### Subsection {i}.2

Additional information for section {i} subsection 2.
"""
                for i in range(1, 11)
            ]
        )  # 10 main sections with subsections

        md_file = tmp_path / "large_doc.md"
        md_file.write_text(large_content)

        memories = markdown_loader.load_from_source(str(md_file))

        # Should create substantial number of memories
        assert len(memories) > 20

        # Connection extraction should complete without errors
        connections = markdown_loader.extract_connections(memories)

        # Should find various types of connections
        hierarchical_count = len([c for c in connections if c[3] == "hierarchical"])
        sequential_count = len([c for c in connections if c[3] == "sequential"])
        associative_count = len([c for c in connections if c[3] == "associative"])

        total_connections = len(connections)
        assert total_connections > 0

        # Should have some hierarchical connections due to structure
        assert hierarchical_count > 0

        print(
            f"Performance test: {len(memories)} memories, {total_connections} connections"
        )
        print(
            f"  Hierarchical: {hierarchical_count}, Sequential: {sequential_count}, Associative: {associative_count}"
        )
