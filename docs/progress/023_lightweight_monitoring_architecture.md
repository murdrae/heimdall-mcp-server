# 023 - Lightweight File Monitoring Architecture with Subprocess Delegation

## Overview
Redesign the file monitoring system to solve memory leaks and orphaned process issues by implementing a lightweight monitoring process that delegates heavy operations to CLI subprocesses. This eliminates memory accumulation in long-running processes while maintaining automatic file change detection in `.heimdall/docs` directories.

## Status
- **Started**: 2025-06-25
- **Current Step**: Step 6 - Testing and Validation (remaining memory/load tests)
- **Completion**: 87% (5/6 steps completed, with Step 6 partially done)
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
**Status**: ✅ Completed
**Date Range**: [Day 1 - Afternoon] - Completed 2025-06-25

#### Tasks Completed
- ✅ Created `heimdall/monitoring/lightweight_monitor.py` module
- ✅ Implemented SingletonLock class for process coordination
- ✅ Designed EventQueue system for file change processing
- ✅ Implemented SignalHandler for clean shutdown
- ✅ Defined MarkdownFileWatcher interface
- ✅ Created LightweightMonitor main class with subprocess delegation

#### Current Work
- Step 2 completed successfully

#### Implementation Results
- File-based singleton locking using `portalocker` for cross-platform support
- Context manager pattern for guaranteed resource cleanup
- Thread-safe event queue with deduplication for file changes
- `threading.Event` coordination for clean shutdown
- Subprocess delegation pattern implemented for all cognitive operations
- Memory efficient design avoiding cognitive system loading

#### Implementation Details
```python
# Key classes implemented:
# - SingletonLock: File-based process coordination with portalocker
# - EventQueue: Thread-safe queue with event deduplication
# - SignalHandler: SIGTERM/SIGINT handling with threading.Event
# - MarkdownFileWatcher: Wraps MarkdownFileMonitor with event queue
# - LightweightMonitor: Main coordinator with subprocess delegation
```

#### Dependencies Added
- ✅ **COMPLETED**: `portalocker>=2.7.0` added to pyproject.toml for cross-platform file locking

### Step 3: Implement Subprocess Delegation
**Status**: ✅ Completed
**Date Range**: [Day 2 - Morning] - Completed 2025-06-25

#### Tasks Completed
- ✅ Enhanced `_handle_file_change_subprocess()` method with retry logic and improved error handling
- ✅ Implemented `_build_subprocess_command()` for mapping file change events to CLI commands
- ✅ Added `_execute_subprocess_with_retry()` with configurable retry attempts (max 3 retries)
- ✅ Implemented `_is_permanent_failure()` to distinguish permanent vs temporary failures
- ✅ Enhanced subprocess logging with `_log_subprocess_output()` method
- ✅ Added comprehensive statistics tracking (retries, timeouts, errors)
- ✅ Created end-to-end tests in `tests/e2e/test_subprocess_delegation.py`
- ✅ Tested subprocess execution with various file scenarios

#### Current Work
- Step 3 completed successfully

#### Implementation Results
- **Retry Logic**: Configurable retry attempts (3 max) with exponential backoff (2s base delay)
- **Error Classification**: Distinguishes permanent failures (command not found, permission denied) from temporary failures
- **Enhanced Logging**: Comprehensive subprocess output logging at appropriate levels
- **Statistics Tracking**: Added tracking for retries, timeouts, and error counts
- **Timeout Handling**: 5-minute default timeout with proper timeout detection and retry
- **Configuration**: Configurable parameters for retry count, delay, and timeout

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
**Status**: ✅ Completed
**Date Range**: [Day 2 - Afternoon] - Completed 2025-06-25

#### Tasks Completed
- ✅ Comprehensive singleton enforcement testing with 17 test cases
- ✅ Validated SingletonLock file locking behavior (using `portalocker`)
- ✅ Tested context manager resource lifecycle and cleanup
- ✅ Verified signal handling with `threading.Event` coordination
- ✅ Validated graceful shutdown coordination
- ✅ Tested singleton enforcement across multiple startup attempts
- ✅ Edge case testing for lock file handling and concurrent access
- ✅ Cross-platform compatibility validation through portalocker

#### Current Work
- Step 4 completed successfully

#### Implementation Results
- **Singleton Enforcement**: Multiple monitor instances in same project properly prevented
- **Resource Cleanup**: Lock files cleaned up on normal shutdown, exceptions, and signal handling
- **Stale Lock Handling**: portalocker correctly handles stale locks from crashed processes
- **Thread Lifecycle**: Processing threads start/stop properly with coordinated shutdown
- **Context Managers**: Proper resource cleanup guaranteed even with exceptions
- **Cross-Platform**: File locking works consistently across Linux/macOS/Windows via portalocker

#### Implementation Details
```python
# Key resource management components tested:
# - SingletonLock: File-based process coordination with portalocker
# - EventQueue: Thread-safe queue with event deduplication
# - SignalHandler: SIGTERM/SIGINT handling with threading.Event
# - MarkdownFileWatcher: File monitoring with event queue integration
# - LightweightMonitor: Main coordinator with resource lifecycle management

# Test coverage includes:
# - Singleton lock basic functionality and concurrent access
# - Stale lock handling (portalocker detects dead processes)
# - Exception cleanup and resource safety
# - Monitor start/stop lifecycle and thread coordination
# - Signal handling and graceful shutdown
# - Cross-platform file locking behavior
```

### Step 5: Integration with Monitoring Service
**Status**: ✅ Completed
**Date Range**: [Day 3 - Morning] - Completed 2025-06-25

#### Tasks Completed
- ✅ Modified `heimdall/cognitive_system/monitoring_service.py` to use `LightweightMonitor`
- ✅ Replaced cognitive system loading with lightweight monitor initialization
- ✅ Updated `_initialize_monitoring()` method to create `LightweightMonitor` instance
- ✅ Removed `_handle_file_change()` method (subprocess delegation now handled by lightweight monitor)
- ✅ Simplified daemon forking logic (now delegated to lightweight monitor)
- ✅ Updated health check methods to work with lightweight monitoring architecture
- ✅ Updated status reporting to get data from lightweight monitor instead of heavy components
- ✅ Lowered memory usage warning threshold from 500MB to 100MB (appropriate for lightweight architecture)
- ✅ Removed heavy imports (`CognitiveSystem`, `initialize_system`, `FileSyncHandler`, etc.)
- ✅ Tested integration - MonitoringService imports and initializes successfully
- ✅ Verified CLI command compatibility (`heimdall monitor status` works correctly)

#### Current Work
- Step 5 completed successfully

#### Implementation Results
- **Process Separation**: Monitoring service now uses subprocess delegation for all cognitive operations
- **Memory Efficiency**: Removed heavy cognitive system loading from monitoring process
- **Simplified Architecture**: Daemon forking and complex process management now handled by lightweight monitor
- **Backward Compatibility**: Existing CLI commands (`heimdall monitor start/stop/status`) continue to work
- **Resource Safety**: Singleton lock enforcement and graceful shutdown maintained through lightweight monitor
- **Health Monitoring**: Updated health checks to monitor lightweight process instead of heavy cognitive system

#### Implementation Details
```python
# Key changes made:
# 1. Replaced imports:
#    - Removed: CognitiveSystem, initialize_system, FileSyncHandler, MarkdownFileMonitor
#    - Added: LightweightMonitor, LightweightMonitorError

# 2. Updated initialization:
self.lightweight_monitor = LightweightMonitor(
    project_root=self.project_paths.project_root,
    target_path=target_path,
    lock_file=lock_file
)

# 3. Simplified start/stop logic:
#    - No more cognitive system loading
#    - No more daemon forking complexity
#    - Delegated to lightweight_monitor.start() and lightweight_monitor.stop()

# 4. Updated status and health reporting:
#    - Get data from lightweight_monitor.get_status()
#    - Lowered memory threshold to 100MB
#    - Updated health check messages for lightweight architecture
```

### Step 6: Testing and Validation
**Status**: In Progress (40% complete)
**Date Range**: [Day 3 - Afternoon to Day 4]

#### Tasks Completed
- ✅ **Single instance enforcement** - 17 comprehensive test cases in `test_lightweight_monitor_singleton.py`
- ✅ **Process lifecycle validation** - Monitor start/stop, thread coordination, resource cleanup
- ✅ **Signal handling and graceful shutdown** - SIGTERM/SIGINT handling with threading.Event
- ✅ **Error handling and recovery** - Exception cleanup, permanent vs temporary failure detection
- ✅ **Cross-platform compatibility** - File locking behavior via portalocker
- ✅ **Concurrent access testing** - Multiple startup attempts, lock contention scenarios
- ✅ **Resource cleanup validation** - Context managers, lock file cleanup on exceptions
- ✅ **CLI subprocess execution** - Command mapping, retry logic, timeout handling (6 test cases)
- ✅ **Statistics tracking** - Subprocess calls, errors, retries, timeouts monitoring

#### Current Work
- ✅ **Memory and load tests created** - Created `test_lightweight_monitor_memory_and_load.py` with subprocess-based testing
- ✅ **Code deduplication completed** - Eliminated duplicate file monitoring code, created shared `heimdall/monitoring/file_types.py`
- ⏳ **Memory validation under investigation** - Tests show ~215MB usage, need to identify heavy imports causing bloat

#### Remaining Tasks (NOT COMPLETE)
- ❌ **Memory usage validation** - Tests created but showing 215MB usage, need to investigate and fix heavy imports
- ❌ **File change detection validation** - Tests created but not validated to work correctly
- ❌ **Load testing validation** - Tests created but not validated under real load conditions
- ❌ **Multi-project validation** - Tests created but not validated for proper isolation
- ❌ **Performance benchmarking** - No validation of actual performance improvements

#### Implementation Details
**Completed Validation:**
- 23 total test cases across singleton enforcement and subprocess delegation
- Real integration testing without heavy mocking
- Cross-platform file locking through portalocker
- Thread lifecycle and coordination testing
- Exception safety and resource cleanup validation

**Remaining Validation:**
- Monitor memory usage over extended periods
- Load testing with high-frequency file changes
- End-to-end file change detection workflow
- Memory leak detection and measurement

**Test File Summary:**
- `tests/e2e/test_lightweight_monitor_singleton.py` - 17 test cases for resource management
- `tests/e2e/test_subprocess_delegation.py` - 6 test cases for CLI subprocess execution
- Total: 23 comprehensive end-to-end test cases covering core functionality

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
