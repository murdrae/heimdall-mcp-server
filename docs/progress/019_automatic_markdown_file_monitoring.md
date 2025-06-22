# 019 - Automatic Markdown File Change Monitoring

## Overview
Implements automatic markdown file change detection and memory synchronization. The system will monitor markdown files for additions, modifications, and deletions, automatically updating the cognitive memory system to reflect file system changes. Uses a simple polling-based approach for reliability and cross-platform compatibility.

## Status
- **Started**: 2025-06-22
- **Current Step**: Planning and Architecture Design
- **Completion**: 0%
- **Expected Completion**: 2025-06-27

## Objectives
- [ ] Add ability to query memories by source file path
- [ ] Implement file change monitoring with polling
- [ ] Create automated file-to-memory synchronization
- [ ] Integrate with existing CLI and service management
- [ ] Add comprehensive testing for file change scenarios
- [ ] Document configuration and usage patterns

## Implementation Progress

### Step 1: Memory Querying Infrastructure
**Status**: Completed ✅
**Date Range**: 2025-06-22 - 2025-06-22

#### Tasks Completed
- Initial architecture analysis via Heimdall
- Progress document creation
- Added `get_memories_by_source_path()` method to `MemoryMetadataStore` class in `sqlite_persistence.py`
- Added `delete_memories_by_source_path()` method to `MemoryMetadataStore` class
- Added `delete_memories_by_source_path()` method to `CognitiveMemorySystem` class with full vector + metadata cleanup
- Created database migration `006_source_path_index.sql` with JSON indexes for performance
- Created comprehensive unit tests in `test_source_path_queries.py` with 12 test scenarios
- Updated existing migration test to include new migration
- Verified integration with CognitiveMemorySystem factory

#### Implementation Details
- Uses SQLite `JSON_EXTRACT(context_metadata, '$.source_path')` for efficient querying
- Handles both vector storage (Qdrant) and metadata (SQLite) deletion atomically
- Includes proper error handling, logging, and performance optimization
- Returns detailed operation statistics for monitoring
- Supports edge cases: missing source paths, null values, special characters, case sensitivity

#### Performance Optimizations
- Added JSON index on `context_metadata.source_path` field
- Added partial index that only indexes rows where source_path exists
- Tested with 100+ memory dataset to verify query performance

#### Next Tasks
- Ready to proceed to Step 2: File Monitoring Core

### Step 2: File Monitoring Core
**Status**: Completed ✅
**Date Range**: 2025-06-22 - 2025-06-22

#### Tasks Completed
- Created `cognitive_memory/monitoring/` package structure with proper `__init__.py`
- Implemented `MarkdownFileMonitor` class with polling-based file change detection
- Added `FileState` tracking (mtime, size, exists) with change detection logic
- Created `FileChangeEvent` system with `ChangeType` enum (ADDED, MODIFIED, DELETED)
- Implemented comprehensive logging and error handling throughout
- Added monitoring configuration options to `CognitiveConfig`:
  - `monitoring_enabled: bool = True`
  - `monitoring_interval_seconds: float = 5.0`
  - `monitoring_batch_size: int = 10`
  - `monitoring_ignore_patterns: Set[str]` (default: .git, node_modules, __pycache__)
- Created comprehensive unit tests (25 test cases) covering all components
- Created integration tests (11 test cases) for real-world scenarios
- All tests passing (36/36)

#### Implementation Details
- **Polling Strategy**: Cross-platform reliable approach with configurable intervals
- **Event System**: Observer pattern with callback registration for each change type
- **Thread Management**: Clean startup/shutdown with daemon threads
- **Error Handling**: Graceful handling of permission errors, file access issues
- **Configuration Integration**: Full integration with existing config system
- **Performance**: Efficient file state caching and minimal resource usage
- **Edge Cases**: Handles rapid changes, concurrent access, permission denied scenarios

#### Key Files Created
- `cognitive_memory/monitoring/__init__.py` - Module exports
- `cognitive_memory/monitoring/file_monitor.py` - Core monitoring implementation (~430 lines)
- `tests/unit/test_file_monitor.py` - Comprehensive unit tests (~400 lines)
- `tests/integration/test_file_monitoring_integration.py` - Integration tests (~370 lines)

#### Configuration Updates
- Extended `CognitiveConfig` class with monitoring parameters
- Added environment variable support for all monitoring options
- Added validation for monitoring parameters in config validation
- Environment variable mapping: `MONITORING_ENABLED`, `MONITORING_INTERVAL_SECONDS`, etc.

#### Testing Coverage
- **Unit Tests**: FileState, FileChangeEvent, MarkdownFileMonitor components
- **Integration Tests**: Configuration integration, real-world scenarios, error recovery
- **Edge Cases**: Permission errors, rapid changes, large directories, concurrent access
- **Performance Tests**: Large file structures, rapid polling intervals

#### Next Tasks
- Ready to proceed to Step 3: Markdown Synchronization Logic

### Step 3: Markdown Synchronization Logic
**Status**: Not Started
**Date Range**: 2025-06-24 - 2025-06-25

#### Tasks Completed
- None yet

#### Current Work
- None yet

#### Next Tasks
- Implement `MarkdownSyncHandler` for file-to-memory operations
- Handle file added: load memories using existing MarkdownMemoryLoader
- Handle file modified: delete existing memories + reload from file
- Handle file deleted: clean up all memories with matching source_path
- Add atomic operations to prevent partial state corruption

### Step 4: CLI Integration and Service Management
**Status**: Not Started
**Date Range**: 2025-06-25 - 2025-06-26

#### Tasks Completed
- None yet

#### Current Work
- None yet

#### Next Tasks
- Add `memory_system monitor <directory>` CLI command
- Integrate with existing service management in `memory_system/cli.py`
- Add configuration options to `CognitiveConfig`
- Implement background service lifecycle management
- Add status reporting and monitoring controls

### Step 5: Testing and Validation
**Status**: Not Started
**Date Range**: 2025-06-26 - 2025-06-27

#### Tasks Completed
- None yet

#### Current Work
- None yet

#### Next Tasks
- Unit tests for memory querying by source path
- Integration tests for file monitoring scenarios
- End-to-end tests for complete file lifecycle operations
- Performance testing with large markdown directories
- Error handling and edge case testing

## Technical Notes

### Architecture Decisions
- **Polling vs Filesystem Events**: Chose polling for simplicity and cross-platform reliability
- **Metadata Querying**: Using JSON_EXTRACT for SQLite source_path queries (consider indexing if performance issues)
- **Memory Lifecycle**: Delete + reload approach for file modifications to ensure consistency
- **Atomic Operations**: Ensure memory operations are atomic to prevent partial state corruption

### Key Implementation Files
- `cognitive_memory/storage/sqlite_persistence.py` - Add metadata querying methods
- `cognitive_memory/monitoring/file_monitor.py` - Core file change detection
- `cognitive_memory/monitoring/markdown_sync.py` - Markdown-specific sync logic
- `memory_system/cli.py` - CLI integration for monitoring commands
- `cognitive_memory/core/config.py` - Configuration options

### Data Flow
```
File System Changes → MarkdownFileMonitor (polling) → Change Handlers → MarkdownSyncHandler → CognitiveSystem
```

## Dependencies

### External Dependencies
- No new external dependencies required
- Uses existing markdown processing pipeline

### Internal Module Dependencies
- `MarkdownMemoryLoader` - For loading memories from markdown files
- `MemoryMetadataStore` - For querying/deleting memories by metadata
- `CognitiveSystem` - For orchestrating memory operations
- `CognitiveConfig` - For configuration management

### Blocking/Blocked by Other Milestones
- **Depends on**: Existing markdown loading architecture (015_markdown_modular_refactoring.md)
- **Blocks**: None identified
- **Enables**: Future file monitoring for other content types

## Risks & Mitigation

### Identified Risks
1. **Performance**: JSON metadata queries may be slow on large databases
   - **Mitigation**: Add database indexes if needed, implement query caching
2. **File System Race Conditions**: Rapid file changes during processing
   - **Mitigation**: Implement file locking and atomic operations
3. **Memory Consistency**: Partial updates during file modification
   - **Mitigation**: Use database transactions for atomic delete+reload operations
4. **Resource Usage**: Continuous polling may consume CPU
   - **Mitigation**: Configurable polling intervals, optimize file state checking

### Technical Challenges
1. **Source Path Normalization**: Handling relative vs absolute paths consistently
2. **Connection Cleanup**: Ensuring memory connections are properly removed
3. **Concurrent Access**: Multiple processes modifying same files

## Resources

### Code References
- `cognitive_memory/loaders/markdown_loader.py` - Current markdown loading implementation
- `cognitive_memory/loaders/markdown/memory_factory.py:117` - Where source_path metadata is set
- `cognitive_memory/storage/sqlite_persistence.py` - Memory metadata storage
- `cognitive_memory/core/cognitive_system.py` - Memory orchestration

### Documentation
- Architecture analysis via Heimdall recall_memories
- Existing markdown loading architecture documentation
- SQLite JSON functions documentation

### External Resources
- SQLite JSON1 extension documentation
- Python file monitoring best practices
- Database indexing for JSON fields

## Change Log
- **2025-06-22**: Initial milestone planning and architecture design based on Heimdall analysis
