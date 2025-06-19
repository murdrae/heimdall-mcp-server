#!/usr/bin/env python3
"""
Tests for MCP Server functionality.

This module provides comprehensive tests for the Cognitive Memory MCP Server,
including tool registration, protocol handling, input validation, and response formatting.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from mcp.types import TextContent

from cognitive_memory.core.interfaces import CognitiveSystem
from cognitive_memory.core.memory import CognitiveMemory
from interfaces.cli import CognitiveCLI
from interfaces.mcp_server import CognitiveMemoryMCPServer


# Test fixtures
@pytest.fixture
def mock_cognitive_system():
    """Create a mock cognitive system for testing."""
    mock_system = Mock(spec=CognitiveSystem)
    return mock_system


@pytest.fixture
def mock_cli():
    """Create a mock CLI for testing."""
    mock_cli = Mock(spec=CognitiveCLI)
    return mock_cli


@pytest.fixture
def mcp_server(mock_cognitive_system):
    """Create MCP server instance for testing."""
    return CognitiveMemoryMCPServer(mock_cognitive_system)


@pytest.fixture
def sample_memory():
    """Create a sample cognitive memory for testing."""
    return CognitiveMemory(
        id="test-memory-123",
        content="This is a test memory about React performance optimization",
        hierarchy_level=1,
        memory_type="episodic",
        created_date=datetime.now(),
        modified_date=None,
        source_date=None,
        timestamp=datetime.now(),
        last_accessed=datetime.now(),
        access_count=1,
        importance_score=0.8,
        strength=0.75,
        metadata={"loader_type": "manual", "test": True},
        tags=["react", "performance"],
        cognitive_embedding=None,
        dimensions={},
    )


class TestMCPServerCore:
    """Test core MCP server functionality."""

    def test_server_initialization(self, mock_cognitive_system):
        """Test MCP server initializes correctly."""
        server = CognitiveMemoryMCPServer(mock_cognitive_system)

        assert server.cognitive_system == mock_cognitive_system
        assert isinstance(server.cli, CognitiveCLI)
        assert server.server.name == "cognitive-memory"

    @pytest.mark.asyncio
    async def test_list_tools(self, mcp_server):
        """Test tool registration and listing."""
        # Get the list_tools handler from request_handlers
        from mcp.types import ListToolsRequest

        list_tools_handler = mcp_server.server.request_handlers.get(ListToolsRequest)
        assert list_tools_handler is not None

        # Call the handler with mock request
        request = ListToolsRequest(method="tools/list")
        result = await list_tools_handler(request)

        # Verify all 4 tools are registered
        assert len(result.root.tools) == 4

        tool_names = [tool.name for tool in result.root.tools]
        expected_tools = [
            "store_memory",
            "recall_memories",
            "session_lessons",
            "memory_status",
        ]

        for expected_tool in expected_tools:
            assert expected_tool in tool_names

        # Verify tool schemas
        store_memory_tool = next(
            tool for tool in result.root.tools if tool.name == "store_memory"
        )
        assert "text" in store_memory_tool.inputSchema["properties"]
        assert store_memory_tool.inputSchema["required"] == ["text"]

    @pytest.mark.asyncio
    async def test_call_tool_unknown(self, mcp_server):
        """Test calling unknown tool returns error."""
        from mcp.types import CallToolRequest, CallToolRequestParams

        call_tool_handler = mcp_server.server.request_handlers.get(CallToolRequest)
        assert call_tool_handler is not None

        params = CallToolRequestParams(name="unknown_tool", arguments={})
        request = CallToolRequest(method="tools/call", params=params)
        result = await call_tool_handler(request)

        assert len(result.root.content) == 1
        assert isinstance(result.root.content[0], TextContent)
        assert "Unknown tool: unknown_tool" in result.root.content[0].text

    @pytest.mark.asyncio
    async def test_call_tool_exception_handling(self, mcp_server):
        """Test tool exception handling."""
        # Mock the CLI to raise an exception
        with patch.object(
            mcp_server.cli, "store_experience", side_effect=Exception("Test error")
        ):
            from mcp.types import CallToolRequest, CallToolRequestParams

            call_tool_handler = mcp_server.server.request_handlers.get(CallToolRequest)
            assert call_tool_handler is not None

            params = CallToolRequestParams(
                name="store_memory", arguments={"text": "test"}
            )
            request = CallToolRequest(method="tools/call", params=params)
            result = await call_tool_handler(request)

            assert len(result.root.content) == 1
            assert isinstance(result.root.content[0], TextContent)
            assert "Error storing memory: Test error" in result.root.content[0].text


class TestStoreMemoryTool:
    """Test store_memory MCP tool functionality."""

    @pytest.mark.asyncio
    async def test_store_memory_success(self, mcp_server):
        """Test successful memory storage."""
        # Mock CLI store_experience to return success
        mcp_server.cli.store_experience = Mock(return_value=True)

        arguments = {
            "text": "Test memory content",
            "context": {
                "hierarchy_level": 1,
                "memory_type": "semantic",
                "importance_score": 0.7,
                "tags": ["test", "memory"],
            },
        }

        result = await mcp_server._store_memory(arguments)

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "✓ Experience stored successfully" in result[0].text
        assert "Hierarchy Level: L1 (Context)" in result[0].text
        assert "Memory Type: semantic" in result[0].text

        # Verify CLI was called correctly
        mcp_server.cli.store_experience.assert_called_once_with(
            text="Test memory content", context=arguments["context"]
        )

    @pytest.mark.asyncio
    async def test_store_memory_empty_text(self, mcp_server):
        """Test store_memory with empty text."""
        arguments = {"text": ""}

        result = await mcp_server._store_memory(arguments)

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Error: Memory text cannot be empty" in result[0].text

    @pytest.mark.asyncio
    async def test_store_memory_whitespace_text(self, mcp_server):
        """Test store_memory with whitespace-only text."""
        arguments = {"text": "   \n\t  "}

        result = await mcp_server._store_memory(arguments)

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Error: Memory text cannot be empty" in result[0].text

    @pytest.mark.asyncio
    async def test_store_memory_failure(self, mcp_server):
        """Test store_memory when CLI returns failure."""
        mcp_server.cli.store_experience = Mock(return_value=False)

        arguments = {"text": "Test memory"}

        result = await mcp_server._store_memory(arguments)

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Failed to store experience" in result[0].text

    @pytest.mark.asyncio
    async def test_store_memory_default_context(self, mcp_server):
        """Test store_memory with default context values."""
        mcp_server.cli.store_experience = Mock(return_value=True)

        arguments = {"text": "Test memory"}

        result = await mcp_server._store_memory(arguments)

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert (
            "Hierarchy Level: L2 (Episode)" in result[0].text
        )  # Default hierarchy_level
        assert "Memory Type: episodic" in result[0].text  # Default memory_type


class TestRecallMemoriesTool:
    """Test recall_memories MCP tool functionality."""

    @pytest.mark.asyncio
    async def test_recall_memories_success(self, mcp_server):
        """Test successful memory recall."""
        # Mock CLI retrieve_memories to return success
        mcp_server.cli.retrieve_memories = Mock(return_value=True)

        arguments = {
            "query": "React performance",
            "max_results": 5,
            "include_bridges": True,
        }

        result = await mcp_server._recall_memories(arguments)

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "📋 Retrieved memories for: 'React performance'" in result[0].text
        assert "Memories retrieved successfully" in result[0].text

        # Verify CLI was called correctly
        mcp_server.cli.retrieve_memories.assert_called_once_with(
            query="React performance", types=None, limit=5
        )

    @pytest.mark.asyncio
    async def test_recall_memories_empty_query(self, mcp_server):
        """Test recall_memories with empty query."""
        arguments = {"query": ""}

        result = await mcp_server._recall_memories(arguments)

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Error: Query cannot be empty" in result[0].text

    @pytest.mark.asyncio
    async def test_recall_memories_no_results(self, mcp_server):
        """Test recall_memories when no memories found."""
        mcp_server.cli.retrieve_memories = Mock(return_value=None)

        arguments = {"query": "nonexistent topic"}

        result = await mcp_server._recall_memories(arguments)

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "No memories found for query: 'nonexistent topic'" in result[0].text

    @pytest.mark.asyncio
    async def test_recall_memories_default_params(self, mcp_server):
        """Test recall_memories with default parameters."""
        mcp_server.cli.retrieve_memories = Mock(return_value="Some results")

        arguments = {"query": "test query"}

        await mcp_server._recall_memories(arguments)

        # Verify default parameters were used
        mcp_server.cli.retrieve_memories.assert_called_once_with(
            query="test query",
            types=None,  # Default types
            limit=10,  # Default max_results
        )


class TestSessionLessonsTool:
    """Test session_lessons MCP tool functionality."""

    @pytest.mark.asyncio
    async def test_session_lessons_success(self, mcp_server):
        """Test successful session lesson storage."""
        mcp_server.cli.store_experience = Mock(return_value=True)

        arguments = {
            "lesson_content": "Always check network tab first when debugging API issues. This reveals 90% of integration problems quickly.",
            "lesson_type": "pattern",
            "session_context": "Working on payment API integration",
            "importance": "high",
        }

        result = await mcp_server._session_lessons(arguments)

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "✓ Session lesson recorded for future reference" in result[0].text
        assert "Lesson Type: pattern" in result[0].text
        assert "Importance Level: high" in result[0].text
        assert "Session Context: Working on payment API integration" in result[0].text

        # Verify CLI was called with correct context
        call_args = mcp_server.cli.store_experience.call_args
        assert call_args[1]["text"] == arguments["lesson_content"]

        context = call_args[1]["context"]
        assert context["hierarchy_level"] == 1  # Context level for lessons
        assert context["memory_type"] == "semantic"  # Lessons are semantic
        assert context["importance_score"] == 0.8  # High importance = 0.8
        assert "session_lesson" in context["tags"]
        assert context["metadata"]["loader_type"] == "session_lesson"

    @pytest.mark.asyncio
    async def test_session_lessons_empty_content(self, mcp_server):
        """Test session_lessons with empty content."""
        arguments = {"lesson_content": ""}

        result = await mcp_server._session_lessons(arguments)

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Error: Lesson content cannot be empty" in result[0].text

    @pytest.mark.asyncio
    async def test_session_lessons_short_content(self, mcp_server):
        """Test session_lessons with very short content."""
        arguments = {"lesson_content": "Too short"}

        result = await mcp_server._session_lessons(arguments)

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "could be more detailed" in result[0].text
        assert "Consider expanding your lesson" in result[0].text

    @pytest.mark.asyncio
    async def test_session_lessons_importance_mapping(self, mcp_server):
        """Test session_lessons importance level to score mapping."""
        mcp_server.cli.store_experience = Mock(return_value=True)

        importance_tests = [
            ("low", 0.3),
            ("medium", 0.6),
            ("high", 0.8),
            ("critical", 1.0),
        ]

        for importance, expected_score in importance_tests:
            arguments = {
                "lesson_content": "Test lesson with sufficient length to pass validation",
                "importance": importance,
            }

            await mcp_server._session_lessons(arguments)

            # Check the importance score in the CLI call
            call_args = mcp_server.cli.store_experience.call_args
            context = call_args[1]["context"]
            assert context["importance_score"] == expected_score

    @pytest.mark.asyncio
    async def test_session_lessons_contextual_suggestions(self, mcp_server):
        """Test session_lessons provides contextual suggestions."""
        mcp_server.cli.store_experience = Mock(return_value=True)

        lesson_types_and_suggestions = [
            ("discovery", "Consider recording related patterns"),
            ("pattern", "Consider documenting specific examples"),
            ("solution", "Consider adding context about when this solution"),
            ("warning", "Consider documenting the consequences"),
            ("context", "Consider adding related discoveries"),
        ]

        for lesson_type, expected_suggestion in lesson_types_and_suggestions:
            arguments = {
                "lesson_content": "Test lesson with sufficient length to pass validation",
                "lesson_type": lesson_type,
            }

            result = await mcp_server._session_lessons(arguments)

            assert len(result) == 1
            assert isinstance(result[0], TextContent)
            assert expected_suggestion in result[0].text

    @pytest.mark.asyncio
    async def test_session_lessons_default_values(self, mcp_server):
        """Test session_lessons with default values."""
        mcp_server.cli.store_experience = Mock(return_value=True)

        arguments = {
            "lesson_content": "Test lesson with sufficient length to pass validation"
        }

        await mcp_server._session_lessons(arguments)

        # Verify defaults were applied
        call_args = mcp_server.cli.store_experience.call_args
        context = call_args[1]["context"]

        assert context["metadata"]["lesson_type"] == "discovery"  # Default lesson_type
        assert context["importance_score"] == 0.6  # Default medium importance


class TestMemoryStatusTool:
    """Test memory_status MCP tool functionality."""

    @pytest.mark.asyncio
    async def test_memory_status_success(self, mcp_server):
        """Test successful memory status retrieval."""
        mock_status = (
            "Total memories: 1247\nQdrant status: running\nLast activity: 2024-01-15"
        )
        mcp_server.cli.show_status = Mock(return_value=mock_status)

        arguments = {"detailed": False}

        result = await mcp_server._memory_status(arguments)

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "📊 COGNITIVE MEMORY SYSTEM STATUS" in result[0].text
        assert "System Status: ✅ HEALTHY" in result[0].text
        assert mock_status in result[0].text

    @pytest.mark.asyncio
    async def test_memory_status_detailed(self, mcp_server):
        """Test memory status with detailed configuration."""
        mock_status = "Basic status info"
        mcp_server.cli.show_status = Mock(return_value=mock_status)

        arguments = {"detailed": True}

        result = await mcp_server._memory_status(arguments)

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "🔧 DETAILED CONFIGURATION" in result[0].text
        assert "Embedding Model: all-MiniLM-L6-v2" in result[0].text
        assert "Activation Threshold: 0.7" in result[0].text

    @pytest.mark.asyncio
    async def test_memory_status_failure(self, mcp_server):
        """Test memory status when CLI returns None."""
        mcp_server.cli.show_status = Mock(return_value=None)

        arguments = {}

        result = await mcp_server._memory_status(arguments)

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Unable to retrieve system status" in result[0].text

    @pytest.mark.asyncio
    async def test_memory_status_default_params(self, mcp_server):
        """Test memory status with default parameters."""
        mcp_server.cli.show_status = Mock(return_value="Status info")

        arguments = {}

        result = await mcp_server._memory_status(arguments)

        # Should not include detailed configuration by default
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "🔧 DETAILED CONFIGURATION" not in result[0].text


class TestMCPIntegration:
    """Integration tests for complete MCP workflows."""

    @pytest.mark.asyncio
    async def test_full_mcp_workflow(self, mcp_server):
        """Test complete store -> recall -> lesson workflow."""
        # Mock CLI methods
        mcp_server.cli.store_experience = Mock(return_value=True)
        mcp_server.cli.retrieve_memories = Mock(
            return_value="Found React performance insights"
        )
        mcp_server.cli.show_status = Mock(return_value="System healthy, 100 memories")

        from mcp.types import CallToolRequest, CallToolRequestParams

        call_tool_handler = mcp_server.server.request_handlers.get(CallToolRequest)

        # Step 1: Store a memory
        store_params = CallToolRequestParams(
            name="store_memory",
            arguments={
                "text": "React components re-render unnecessarily with object destructuring in useEffect",
                "context": {
                    "hierarchy_level": 1,
                    "importance_score": 0.8,
                    "tags": ["react", "performance"],
                },
            },
        )
        store_request = CallToolRequest(method="tools/call", params=store_params)
        store_result = await call_tool_handler(store_request)

        assert len(store_result.root.content) == 1
        assert "✓ Experience stored successfully" in store_result.root.content[0].text

        # Step 2: Recall memories
        recall_params = CallToolRequestParams(
            name="recall_memories",
            arguments={"query": "React performance", "max_results": 5},
        )
        recall_request = CallToolRequest(method="tools/call", params=recall_params)
        recall_result = await call_tool_handler(recall_request)

        assert len(recall_result.root.content) == 1
        assert (
            "📋 Retrieved memories for: 'React performance'"
            in recall_result.root.content[0].text
        )
        assert "Found React performance insights" in recall_result.root.content[0].text

        # Step 3: Record a session lesson
        lesson_params = CallToolRequestParams(
            name="session_lessons",
            arguments={
                "lesson_content": "When debugging React performance, always check useEffect dependencies first. Object destructuring in dependency arrays causes unnecessary re-renders.",
                "lesson_type": "pattern",
                "importance": "high",
                "session_context": "React performance optimization session",
            },
        )
        lesson_request = CallToolRequest(method="tools/call", params=lesson_params)
        lesson_result = await call_tool_handler(lesson_request)

        assert len(lesson_result.root.content) == 1
        assert (
            "✓ Session lesson recorded for future reference"
            in lesson_result.root.content[0].text
        )
        assert "Lesson Type: pattern" in lesson_result.root.content[0].text

        # Step 4: Check system status
        status_params = CallToolRequestParams(
            name="memory_status", arguments={"detailed": True}
        )
        status_request = CallToolRequest(method="tools/call", params=status_params)
        status_result = await call_tool_handler(status_request)

        assert len(status_result.root.content) == 1
        assert "📊 COGNITIVE MEMORY SYSTEM STATUS" in status_result.root.content[0].text
        assert "System healthy, 100 memories" in status_result.root.content[0].text

        # Verify all CLI methods were called correctly
        mcp_server.cli.store_experience.assert_called()
        mcp_server.cli.retrieve_memories.assert_called_with(
            query="React performance", types=None, limit=5
        )
        # Should be called twice - once for lesson storage, once for status
        assert mcp_server.cli.store_experience.call_count == 2
        mcp_server.cli.show_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_resilience_workflow(self, mcp_server):
        """Test MCP server resilience to errors in workflow."""
        # Setup mixed success/failure scenarios
        mcp_server.cli.store_experience = Mock(
            side_effect=[False, True]
        )  # First fails, second succeeds
        mcp_server.cli.retrieve_memories = Mock(return_value=None)  # No results
        mcp_server.cli.show_status = Mock(side_effect=Exception("Service unavailable"))

        from mcp.types import CallToolRequest, CallToolRequestParams

        call_tool_handler = mcp_server.server.request_handlers.get(CallToolRequest)

        # Test failed storage
        store_params = CallToolRequestParams(
            name="store_memory", arguments={"text": "Test memory"}
        )
        store_request = CallToolRequest(method="tools/call", params=store_params)
        store_result = await call_tool_handler(store_request)

        assert "Failed to store experience" in store_result.root.content[0].text

        # Test empty query
        recall_params = CallToolRequestParams(
            name="recall_memories", arguments={"query": ""}
        )
        recall_request = CallToolRequest(method="tools/call", params=recall_params)
        recall_result = await call_tool_handler(recall_request)

        assert "Error: Query cannot be empty" in recall_result.root.content[0].text

        # Test successful lesson storage despite previous failures
        lesson_params = CallToolRequestParams(
            name="session_lessons",
            arguments={
                "lesson_content": "Error handling is important for robust MCP servers"
            },
        )
        lesson_request = CallToolRequest(method="tools/call", params=lesson_params)
        lesson_result = await call_tool_handler(lesson_request)

        assert (
            "✓ Session lesson recorded for future reference"
            in lesson_result.root.content[0].text
        )

        # Test status error handling
        status_params = CallToolRequestParams(name="memory_status", arguments={})
        status_request = CallToolRequest(method="tools/call", params=status_params)
        status_result = await call_tool_handler(status_request)

        assert "Error getting system status" in status_result.root.content[0].text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
