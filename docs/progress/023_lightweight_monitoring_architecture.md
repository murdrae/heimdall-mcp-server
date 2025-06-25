# 023 - Lightweight File Monitoring Architecture with Subprocess Delegation

## Overview
Redesign the file monitoring system to solve memory leaks and orphaned process issues by implementing a lightweight monitoring process that delegates heavy operations to CLI subprocesses. This eliminates memory accumulation in long-running processes while maintaining automatic file change detection in `.heimdall/docs` directories.

## Status
- **Started**: 2025-06-25
- **Current Step**: Step 2 - Design Lightweight Monitor Process
- **Completion**: 17% (1/6 steps completed)
- **Expected Completion**: 3-4 days

## Objectives
- [ ] Eliminate memory leaks in file monitoring (reduce from 1GB+ to <50MB)
- [ ] Prevent orphaned monitoring processes through atomic coordination
- [ ] Implement subprocess delegation for cognitive operations
- [ ] Add CLI command for file removal operations
- [ ] Ensure single monitoring instance per project
- [ ] Maintain automatic file change detection functionality

## Implementation Progress

### Step 1: Add CLI File Removal Command
**Status**: ✅ Completed
**Date Range**: [Day 1 - Morning] - Completed 2025-06-25

#### Tasks Completed
- ✅ Added `delete_memories_by_source_path()` wrapper method to `CognitiveOperations` class
- ✅ Created `remove_file_cmd()` function in `heimdall/cli_commands/cognitive_commands.py`
- ✅ Registered `remove-file` command in unified CLI (`heimdall/cli.py`)
- ✅ Tested CLI command registration and help output
- ✅ Verified command follows existing CLI patterns and error handling

#### Current Work
- Step 1 completed successfully

#### Implementation Results
- Command available as: `heimdall remove-file <file_path>`
- Uses existing `delete_memories_by_source_path()` from cognitive system
- Returns structured deletion results with count and processing time
- Includes proper error handling and rich console output formatting
- Ready for subprocess delegation pattern in Step 3

#### Implementation Details
```python
# Add to heimdall/cli.py
@app.command("remove-file")
def remove_file_cmd(
    file_path: str = typer.Argument(..., help="Path to file whose memories should be removed")
):
    """Remove all memories associated with a deleted file."""
    # Implementation using existing delete_memories_by_source_path
```

### Step 2: Design Lightweight Monitor Process
**Status**: Not Started
**Date Range**: [Day 1 - Afternoon]

#### Tasks Completed
- [None yet]

#### Current Work
- Design process coordination architecture
- Define resource management patterns

#### Next Tasks
- Create `heimdall/monitoring/lightweight_monitor.py` module
- Implement SingletonLock class for process coordination
- Design EventQueue system for file change processing
- Implement SignalHandler for clean shutdown
- Define MarkdownFileWatcher interface

#### Implementation Details
- Use file locking for atomic process coordination
- Implement context managers for guaranteed resource cleanup
- Design thread-safe event queue for file changes
- Use `threading.Event` for shutdown coordination
- Target memory usage: 10-50MB maximum

### Step 3: Implement Subprocess Delegation
**Status**: Not Started
**Date Range**: [Day 2 - Morning]

#### Tasks Completed
- [None yet]

#### Current Work
- Design subprocess execution patterns
- Error handling and logging strategy

#### Next Tasks
- Implement CLI subprocess execution for file operations
- Map file change events to CLI commands:
  - File added/modified: `heimdall load <file_path>`
  - File deleted: `heimdall remove-file <file_path>`
- Add error handling and retry logic
- Implement subprocess logging and monitoring
- Test subprocess execution with various file scenarios

#### Implementation Details
```python
# Subprocess delegation pattern
def _handle_file_change(self, event: FileChangeEvent):
    if event.change_type in [ChangeType.ADDED, ChangeType.MODIFIED]:
        cmd = ["heimdall", "load", str(event.path)]
    elif event.change_type == ChangeType.DELETED:
        cmd = ["heimdall", "remove-file", str(event.path)]

    subprocess.run(cmd, capture_output=True, text=True)
```

### Step 4: Resource Management Implementation
**Status**: Not Started
**Date Range**: [Day 2 - Afternoon]

#### Tasks Completed
- [None yet]

#### Current Work
- Implement atomic process coordination
- Context manager resource safety

#### Next Tasks
- Implement SingletonLock with file locking (using `portalocker` for cross-platform)
- Create context managers for resource lifecycle
- Implement signal handling with `threading.Event`
- Add graceful shutdown coordination
- Test singleton enforcement across multiple startup attempts

#### Implementation Details
```python
class SingletonLock:
    def __enter__(self):
        # Acquire exclusive file lock atomically
        # Write PID to lock file
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Release lock and cleanup
        pass
```

### Step 5: Integration with Monitoring Service
**Status**: Not Started
**Date Range**: [Day 3 - Morning]

#### Tasks Completed
- [None yet]

#### Current Work
- Replace current heavy monitoring implementation
- Update service manager integration

#### Next Tasks
- Modify `heimdall/cognitive_system/monitoring_service.py`
- Replace cognitive system loading with lightweight monitor
- Update `_initialize_monitoring()` method
- Modify `_handle_file_change()` to use subprocess delegation
- Remove daemon forking logic
- Update health check methods

#### Implementation Details
- Remove all cognitive system initialization from monitor process
- Replace direct file processing with subprocess calls
- Simplify daemon lifecycle management
- Update status reporting for new architecture

### Step 6: Testing and Validation
**Status**: Not Started
**Date Range**: [Day 3 - Afternoon to Day 4]

#### Tasks Completed
- [None yet]

#### Current Work
- Comprehensive testing of new architecture
- Memory usage validation

#### Next Tasks
- Test memory usage stays under 50MB consistently
- Verify single instance enforcement works correctly
- Test file change detection and CLI subprocess execution
- Validate error handling and recovery
- Test with multiple rapid file changes
- Test across different project directories
- Load testing with concurrent file modifications

#### Implementation Details
- Monitor memory usage over extended periods
- Test process lifecycle edge cases
- Verify no orphaned processes remain
- Test signal handling and graceful shutdown

## Technical Notes

### Key Architectural Changes
- **Process Separation**: Monitor process handles file watching only, CLI subprocesses handle cognitive operations
- **Memory Isolation**: Each cognitive operation runs in isolated subprocess that exits cleanly
- **Resource Safety**: Context managers ensure cleanup even on exceptions or crashes
- **Atomic Coordination**: File locking prevents race conditions in process startup

### File Structure Changes
```
heimdall/
├── monitoring/
│   └── lightweight_monitor.py     # New lightweight monitoring implementation
├── cli.py                         # Add remove-file command
└── cognitive_system/
    └── monitoring_service.py      # Modified to use lightweight monitor
```

### Dependencies to Remove
- Remove cognitive system loading from monitoring process
- Remove daemon forking complexity
- Remove manual PID file management
- Remove heavy memory processing from monitor

## Dependencies
- **External**: `portalocker` library for cross-platform file locking
- **Internal**: Unified CLI architecture (milestone 022)
- **Blocking**: None
- **Blocked by**: None

## Risks & Mitigation

### Risk: Subprocess Overhead
**Impact**: CLI startup time may impact file processing performance
**Mitigation**:
- Profile subprocess execution time
- Implement batching if needed
- Consider process pooling for high-frequency changes

### Risk: Error Handling Complexity
**Impact**: Subprocess failures could be harder to debug
**Mitigation**:
- Comprehensive logging of subprocess operations
- Structured error reporting
- Health check integration

### Risk: Signal Handling Edge Cases
**Impact**: Shutdown coordination between threads could fail
**Mitigation**:
- Use `threading.Event` for coordination
- Implement timeout-based cleanup
- Test signal handling thoroughly

## Resources
- **Architecture Document**: `docs/monitoring-architecture.md`
- **Current Implementation**: `heimdall/cognitive_system/monitoring_service.py`
- **CLI Framework**: `heimdall/cli.py`
- **File Monitor**: `cognitive_memory/monitoring/file_monitor.py`
- **Operations Layer**: `heimdall/operations.py`

## Change Log
- **[2025-06-25]**: Initial milestone planning and architecture design
