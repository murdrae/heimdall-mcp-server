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
    for memory_type in ["core", "peripheral"]:
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

    # Test 8: delete_memories_by_tags tool - dry run first
    test_tag_memory_text = (
        "Memory specifically for tag-based deletion testing in E2E MCP tests"
    )
    tag_store_result = await server._store_memory(
        {
            "text": test_tag_memory_text,
            "context": {
                "tags": ["e2e-deletion-test", "mcp-test"],
                "hierarchy_level": 2,
                "memory_type": "episodic",
            },
        }
    )
    assert "✓ Stored:" in tag_store_result[0].text

    # Test dry-run deletion by tags
    dry_run_result = await server._delete_memories_by_tags(
        {"tags": ["e2e-deletion-test"], "dry_run": True}
    )
    assert len(dry_run_result) == 1
    dry_run_text = dry_run_result[0].text
    assert "🔍 Dry run - Would delete" in dry_run_text
    assert "e2e-deletion-test" in dry_run_text

    # Test actual deletion by tags
    delete_tags_result = await server._delete_memories_by_tags(
        {"tags": ["e2e-deletion-test"], "dry_run": False}
    )
    assert len(delete_tags_result) == 1
    delete_tags_text = delete_tags_result[0].text
    assert (
        "✅ Deleted" in delete_tags_text or "📭 No memories found" in delete_tags_text
    )

    # Test 9: delete_memory tool by ID
    # Store another test memory and get its ID from recall
    id_test_memory_text = (
        "Memory specifically for ID-based deletion testing in E2E MCP tests"
    )
    id_store_result = await server._store_memory(
        {
            "text": id_test_memory_text,
            "context": {
                "tags": ["e2e-id-deletion-test"],
                "hierarchy_level": 2,
                "memory_type": "episodic",
            },
        }
    )
    assert "✓ Stored:" in id_store_result[0].text

    # Find the memory ID using recall
    id_recall_result = await server._recall_memories(
        {"query": "ID-based deletion testing E2E", "max_results": 5}
    )
    id_recall_data = json.loads(id_recall_result[0].text)

    # Find our test memory and extract its ID
    test_memory_id = None
    for memory_type in ["core", "peripheral"]:
        if memory_type in id_recall_data["memories"]:
            for memory in id_recall_data["memories"][memory_type]:
                if "ID-based deletion testing" in memory["content"]:
                    test_memory_id = memory["metadata"]["id"]
                    break

    assert test_memory_id is not None, "Should find the test memory ID"

    # Test dry-run deletion by ID
    id_dry_run_result = await server._delete_memory(
        {"memory_id": test_memory_id, "dry_run": True}
    )
    assert len(id_dry_run_result) == 1
    id_dry_run_text = id_dry_run_result[0].text
    assert "🔍 Dry run - Would delete memory:" in id_dry_run_text
    assert test_memory_id in id_dry_run_text

    # Test actual deletion by ID
    id_delete_result = await server._delete_memory(
        {"memory_id": test_memory_id, "dry_run": False}
    )
    assert len(id_delete_result) == 1
    id_delete_text = id_delete_result[0].text
    assert "✅ Memory deleted:" in id_delete_text
    assert test_memory_id in id_delete_text

    # Test 10: Error handling for deletion tools
    # Test empty memory ID
    empty_id_result = await server._delete_memory({"memory_id": ""})
    assert "❌ Error: Memory ID cannot be empty" in empty_id_result[0].text

    # Test nonexistent memory ID
    fake_id_result = await server._delete_memory(
        {"memory_id": "fake-id-12345", "dry_run": False}
    )
    assert "❌ Memory not found:" in fake_id_result[0].text

    # Test empty tags list
    empty_tags_result = await server._delete_memories_by_tags({"tags": []})
    assert "❌ Error: Tags list cannot be empty" in empty_tags_result[0].text

    # Test with nonexistent tags
    fake_tags_result = await server._delete_memories_by_tags(
        {"tags": ["nonexistent-tag-12345"], "dry_run": True}
    )
    assert "🔍 Dry run - Would delete 0 memories" in fake_tags_result[0].text


if __name__ == "__main__":
    """Allow running this test directly for debugging."""
    asyncio.run(test_mcp_server_tools_e2e())
    print("✅ All MCP server tools E2E tests passed!")
