# Memory Removal Operations

This document describes the memory removal capabilities provided by the Heimdall cognitive memory system, including both CLI commands and MCP tools for safe and efficient memory cleanup.

## Overview

The memory removal system provides two primary approaches:
- **ID-based deletion**: Precise removal of specific memories by their unique identifier
- **Tag-based deletion**: Bulk removal of memories grouped by task or context tags

## CLI Commands

### Delete by ID

Remove a specific memory using its unique identifier:

```bash
heimdall delete <memory_id>
```

**Example:**
```bash
heimdall delete abc123def456
# ✅ Deleted memory: abc123def456
```

### Delete by Tags

Remove all memories matching specific tags:

```bash
heimdall delete --tags <tag1,tag2,...>
```

**Examples:**
```bash
# Delete all memories tagged with "api-refactor"
heimdall delete --tags "api-refactor"

# Delete memories with multiple tags
heimdall delete --tags "api-refactor,experiment"

# Preview what would be deleted
heimdall delete --tags "old-config" --dry-run
```

**Safety Features:**
- Shows count and sample memories before deletion
- Requires confirmation for bulk operations
- Supports `--dry-run` flag for preview
- Provides detailed deletion summary

### Delete by File (Existing)

Remove all memories associated with a deleted file:

```bash
heimdall remove-file <file_path>
```

## MCP Tools

### delete_memory

Remove a specific memory by ID through the MCP protocol:

```python
delete_memory(memory_id="abc123def456")
```

**Parameters:**
- `memory_id` (string, required): Unique identifier of the memory to delete

**Response:**
```json
{
  "success": true,
  "memory_id": "abc123def456",
  "message": "Memory deleted successfully"
}
```

### delete_memories_by_tags

Remove all memories matching specified tags:

```python
delete_memories_by_tags(tags=["api-refactor", "experiment"])
```

**Parameters:**
- `tags` (array of strings, required): Tags to match for deletion

**Response:**
```json
{
  "success": true,
  "deleted_count": 5,
  "tags": ["api-refactor", "experiment"],
  "message": "Deleted 5 memories matching tags"
}
```

## Usage Patterns

### Task-Based Memory Management

LLMs can organize memories by task and clean up when work is complete:

```python
# During task execution
store_memory("Found authentication bug in login endpoint",
             context={"tags": ["api-refactor", "bug-fix"]})

store_memory("Implemented JWT token validation",
             context={"tags": ["api-refactor", "solution"]})

# Task completed - cleanup
delete_memories_by_tags(tags=["api-refactor"])
```

### Project Cleanup

Users can manage project-specific memories:

```bash
# List memories for a project
heimdall recall "database migration" --json

# Clean up completed project memories
heimdall delete --tags "db-migration,completed"
```

### Experimental Memory Cleanup

Remove temporary or experimental memories:

```bash
# Clean up experimental approaches
heimdall delete --tags "experiment" --dry-run
heimdall delete --tags "experiment"
```

## Safety Considerations

### CLI Safety Features
- **Confirmation prompts**: All bulk deletions require user confirmation
- **Dry-run mode**: Preview deletions with `--dry-run` flag
- **Detailed reporting**: Shows what will be deleted before confirmation
- **Count limits**: Large deletions show counts and samples

### MCP Safety Features
- **Direct operation**: No confirmation needed (LLM manages its own memories)
- **Scoped deletion**: Can only delete memories by specific criteria
- **Error handling**: Clear error messages for invalid operations
- **Audit trail**: Deletion operations are logged

## Technical Implementation

### Memory Identification
- **Memory IDs**: UUIDs generated during memory storage
- **Tag matching**: Exact string matching on memory tags
- **Metadata queries**: Tags stored in memory metadata for efficient filtering

### Storage Operations
- **Vector cleanup**: Removes memory vectors from Qdrant collections
- **Metadata cleanup**: Removes memory metadata from SQLite
- **Connection cleanup**: Updates memory connection graph
- **Index maintenance**: Maintains search index consistency

### Performance Considerations
- **Batch operations**: Tag-based deletions processed in batches
- **Transaction safety**: All deletions wrapped in database transactions
- **Memory efficiency**: Streaming deletion for large memory sets
- **Index updates**: Deferred index updates for bulk operations

## Error Handling

### Common Error Cases
- **Memory not found**: ID does not exist in system
- **Invalid tags**: Empty or malformed tag parameters
- **System errors**: Database or storage system failures
- **Permission errors**: Insufficient access to memory collections

### Error Responses
```json
{
  "success": false,
  "error": "Memory not found: abc123def456",
  "error_code": "MEMORY_NOT_FOUND"
}
```

## Future Enhancements

### Planned Features
- **Bulk ID deletion**: Delete multiple memories by ID list
- **Context-based deletion**: Delete by metadata attributes
- **Time-based cleanup**: Delete memories older than specified time
- **Backup before deletion**: Automatic backup of deleted memories

### Under Consideration
- **Undo operations**: Restore recently deleted memories
- **Soft deletion**: Mark memories as deleted without removal
- **Archive operations**: Move memories to archive storage
- **Smart cleanup**: AI-driven identification of obsolete memories
