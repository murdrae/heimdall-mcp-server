#!/usr/bin/env python3
"""
End-to-end test for MCP server tools functionality.

This test validates that all 4 MCP tools work correctly by directly
testing the HeimdallMCPServer methods. This is a real E2E test that
uses the actual cognitive system, Qdrant, and all components.
"""

import asyncio
import json

import pytest

from cognitive_memory.main import initialize_system
from heimdall.mcp_server import HeimdallMCPServer


@pytest.mark.asyncio
async def test_mcp_server_tools_e2e():
    """Test all MCP server tools end-to-end with real cognitive system."""

    # Initialize cognitive system (same as production)
    cognitive_system = initialize_system("default")

    # Create MCP server
    server = HeimdallMCPServer(cognitive_system)

    # Test 1: memory_status tool
    status_result = await server._memory_status({"detailed": False})
    assert len(status_result) == 1
    status_text = status_result[0].text

    # Parse JSON response and validate structure
    status_data = json.loads(status_text)
    assert status_data["system_status"] == "healthy"
    assert "version" in status_data
    assert "memory_counts" in status_data
    assert "timestamp" in status_data

    # Test 2: store_memory tool
    test_memory_text = (
        "Test memory from E2E MCP server testing - this validates tool functionality"
    )
    store_result = await server._store_memory({"text": test_memory_text})
    assert len(store_result) == 1
    store_text = store_result[0].text

    # Should show successful storage
    assert "✓ Stored:" in store_text
    assert (
        "L2 (Episode)" in store_text
        or "L1 (Context)" in store_text
        or "L0 (Concept)" in store_text
    )
    assert "episodic" in store_text or "semantic" in store_text

    # Test 3: recall_memories tool
    recall_result = await server._recall_memories(
        {"query": "E2E MCP server testing", "max_results": 5}
    )
    assert len(recall_result) == 1
    recall_text = recall_result[0].text

    # Parse JSON response and validate structure
    recall_data = json.loads(recall_text)
    assert "query" in recall_data
    assert "total_results" in recall_data
    assert "memories" in recall_data

    # Should find the memory we just stored
    assert recall_data["total_results"] > 0

    # Check that we can find our test memory in results
    found_test_memory = False
    for memory_type in ["core", "peripheral", "bridge"]:
        if memory_type in recall_data["memories"]:
            for memory in recall_data["memories"][memory_type]:
                if "E2E MCP server testing" in memory["content"]:
                    found_test_memory = True
                    # Validate memory structure
                    assert "type" in memory
                    assert "content" in memory
                    assert "metadata" in memory
                    assert "id" in memory["metadata"]
                    assert "hierarchy_level" in memory["metadata"]
                    break

    assert found_test_memory, "Should find the test memory we just stored"

    # Test 4: session_lessons tool
    lesson_result = await server._session_lessons(
        {
            "lesson_content": "E2E MCP testing validates that all tools work correctly with real cognitive system",
            "lesson_type": "discovery",
            "session_context": "Testing MCP server functionality",
            "importance": "medium",
        }
    )
    assert len(lesson_result) == 1
    lesson_text = lesson_result[0].text

    # Should show successful lesson recording
    assert "✓ Lesson recorded:" in lesson_text
    assert "discovery" in lesson_text
    assert "medium" in lesson_text

    # Test 5: Error handling - empty text for store_memory
    error_result = await server._store_memory({"text": ""})
    assert len(error_result) == 1
    error_text = error_result[0].text
    assert "❌ Error: Memory text cannot be empty" in error_text

    # Test 6: Error handling - empty query for recall_memories
    error_recall = await server._recall_memories({"query": ""})
    assert len(error_recall) == 1
    error_recall_text = error_recall[0].text
    assert "❌ Error: Query cannot be empty" in error_recall_text

    # Test 7: memory_status with detailed flag
    detailed_status = await server._memory_status({"detailed": True})
    assert len(detailed_status) == 1
    detailed_text = detailed_status[0].text

    # Parse detailed JSON response
    detailed_data = json.loads(detailed_text)
    assert "system_config" in detailed_data
    assert "storage_stats" in detailed_data
    assert "embedding_info" in detailed_data
    assert "detailed_config" in detailed_data

    # Validate detailed config structure
    detailed_config = detailed_data["detailed_config"]
    assert detailed_config["embedding_model"] == "all-MiniLM-L6-v2"
    assert detailed_config["embedding_dimensions"] == 384
    assert detailed_config["activation_threshold"] == 0.7


if __name__ == "__main__":
    """Allow running this test directly for debugging."""
    asyncio.run(test_mcp_server_tools_e2e())
    print("✅ All MCP server tools E2E tests passed!")
