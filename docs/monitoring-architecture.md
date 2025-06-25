# File Monitoring Architecture: Lightweight Process with CLI Delegation

## Overview

This document outlines the redesigned file monitoring architecture that solves the current memory leak and orphaned process issues. The solution separates concerns by using a lightweight monitoring process that delegates heavy operations to CLI subprocesses, ensuring memory isolation and clean resource management.

## Current Problems

### Memory and Process Issues
- **Multiple concurrent monitoring processes**: Race conditions during startup create orphaned instances
- **Memory leaks**: Long-running processes accumulate 1GB+ memory from cognitive system components
- **Daemon thread survival**: Threads marked `daemon=True` can outlive parent processes
- **Resource cleanup failures**: PID files and status files persist after crashes
- **Non-atomic startup**: Time window between PID check and PID write allows concurrent starts

### Architecture Coupling
- **Heavy memory loading**: Monitor process loads entire cognitive system (~1GB memory)
- **Complex lifecycle management**: Daemon forking, signal handling, and cleanup coordination
- **Error propagation**: File processing errors can crash the entire monitoring service

## Target Architecture

### Design Principles
- **Process isolation**: Heavy operations run in separate processes that exit cleanly
- **Resource safety**: Use Python context managers for guaranteed cleanup
- **Atomic coordination**: File locking prevents concurrent monitor instances
- **Event-driven processing**: Queue-based architecture prevents blocking
- **Memory efficiency**: Monitor process stays lightweight (~10-50MB)

### Core Components

#### 1. Lightweight Monitor Process
- **Responsibility**: File change detection and event dispatching only
- **Memory footprint**: 10-50MB (no cognitive system loading)
- **Lifecycle**: Long-running process with proper resource management
- **Coordination**: Single instance per project via file locking

#### 2. CLI Subprocess Delegation
- **File operations**: Delegate to existing `heimdall` CLI commands
- **Process lifecycle**: Short-lived processes that exit after each operation
- **Memory isolation**: Each operation runs independently with clean state
- **Error handling**: Failed operations logged but don't crash monitor

#### 3. Event Queue System
- **Processing model**: Thread-safe queue for file change events
- **Batching capability**: Group related changes for efficiency
- **Worker thread**: Single consumer thread processes events sequentially
- **Shutdown coordination**: Clean thread termination via threading.Event

#### 4. Resource Management Layer
- **Singleton enforcement**: File-based locking for atomic process coordination
- **Context managers**: Guaranteed resource cleanup even on exceptions
- **Signal handling**: Safe shutdown coordination across threads
- **State tracking**: Minimal status information for health checks

## Data Flow

### File Change Detection
1. **File system events**: Monitor detects changes in `.heimdall/docs` directory
2. **Event creation**: Convert file system events to internal FileChangeEvent objects
3. **Queue insertion**: Thread-safe insertion into processing queue
4. **Event consumption**: Worker thread processes events sequentially

### CLI Operation Dispatch
1. **Event processing**: Worker thread receives FileChangeEvent from queue
2. **Command generation**: Map event type to appropriate CLI command
   - File added/modified: `heimdall load <file_path>`
   - File deleted: `heimdall remove-file <file_path>` (new command)
3. **Subprocess execution**: Launch CLI command in isolated process
4. **Result handling**: Log success/failure, continue processing regardless

### Resource Coordination
1. **Startup**: Acquire singleton lock, start worker threads, setup signal handlers
2. **Runtime**: Process events, maintain health status, handle signals
3. **Shutdown**: Stop worker threads, release locks, cleanup resources

## Implementation Changes

### New Components to Add

#### CLI Command Extension
- **New command**: `heimdall remove-file <file_path>`
- **Operations integration**: Use existing `delete_memories_by_source_path(file_path)` method
- **CLI wrapper**: Simple command interface around existing functionality

#### Lightweight Monitor Service
- **File**: `heimdall/monitoring/lightweight_monitor.py`
- **Responsibility**: Pure file watching with subprocess delegation
- **Dependencies**: Minimal - only file watching and subprocess execution

#### Resource Management Classes
- **SingletonLock**: Cross-platform file locking for process coordination
- **EventQueue**: Thread-safe queue with proper shutdown handling
- **SignalHandler**: Safe shutdown coordination across threads

### Components to Modify

#### Current MonitoringService
- **Simplification**: Remove cognitive system initialization
- **Delegation logic**: Replace direct processing with subprocess calls
- **Resource management**: Implement context manager patterns
- **Thread handling**: Remove daemon threads, add explicit shutdown

#### File Monitor Integration
- **Event routing**: Connect file events to CLI subprocess execution
- **Error handling**: Isolate subprocess failures from monitor process
- **Logging**: Enhanced logging for subprocess operations and failures

### Components to Remove

#### Heavy Dependencies
- **Cognitive system loading**: Remove from monitor process entirely
- **Memory processing**: Move all memory operations to CLI subprocess
- **Daemon forking**: Replace with simpler single-process model

#### Manual Resource Management
- **Direct PID file handling**: Replace with context manager approach
- **Manual signal handlers**: Use threading.Event for coordination
- **Complex restart logic**: Simplify with proper resource cleanup

## Migration Strategy

### Phase 1: CLI Command Addition
1. **Add remove-file command**: Extend unified CLI with file removal capability
2. **Operations integration**: Wire existing `delete_memories_by_source_path()` to new CLI command
3. **Test CLI operations**: Verify both load and remove-file work correctly

### Phase 2: Lightweight Monitor Implementation
1. **Create new monitor class**: Implement subprocess delegation architecture
2. **Resource management**: Add singleton locking and context managers
3. **Event queue system**: Implement thread-safe event processing
4. **Integration testing**: Verify file changes trigger correct CLI calls

### Phase 3: Service Integration
1. **Replace current monitor**: Update service manager to use lightweight monitor
2. **Configuration updates**: Adjust monitoring service configuration
3. **Error handling**: Implement proper subprocess error logging
4. **Health checks**: Update status reporting for new architecture

### Phase 4: Cleanup and Validation
1. **Remove old code**: Delete heavy monitoring implementation
2. **Memory testing**: Verify monitor process stays under 50MB
3. **Stress testing**: Validate with multiple rapid file changes
4. **Multi-project testing**: Ensure singleton enforcement works correctly

## Benefits

### Memory Efficiency
- **Lightweight monitor**: Stays under 50MB memory usage
- **No memory leaks**: Heavy operations run in isolated processes
- **Clean state**: Each CLI operation starts with fresh memory

### Process Reliability
- **No orphaned processes**: Proper resource management prevents stranded instances
- **Atomic startup**: File locking eliminates race conditions
- **Graceful shutdown**: Context managers ensure cleanup on exit or crash

### Error Isolation
- **Fault tolerance**: File processing errors don't crash monitor
- **Independent operations**: Each file change processed separately
- **Recovery capability**: Monitor continues running despite individual failures

### Operational Simplicity
- **Single responsibility**: Monitor only watches files and dispatches
- **Clear boundaries**: Cognitive operations isolated to CLI layer
- **Standard patterns**: Uses established Python resource management idioms

## Success Criteria

### Performance Metrics
- **Memory usage**: Monitor process under 50MB consistently
- **No memory growth**: Memory usage stable over long periods
- **Process isolation**: No shared state between file operations

### Reliability Metrics
- **Single instance**: Only one monitor per project at any time
- **Clean shutdown**: All resources released on termination
- **Error recovery**: Monitor survives individual operation failures

### Functional Requirements
- **File change detection**: All changes in `.heimdall/docs` processed
- **Operation accuracy**: Correct CLI commands for each event type
- **Status reporting**: Health checks and monitoring statistics available
