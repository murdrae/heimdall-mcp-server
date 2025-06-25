#!/usr/bin/env python3
"""
Lightweight file monitoring process with subprocess delegation.

Provides file change detection and delegates cognitive operations to CLI subprocesses.
"""

import argparse
import os
import queue
import signal
import subprocess
import sys
import threading
import time

# ================================================================================
# COPIED CODE FROM file_types.py - AVOID PACKAGE IMPORTS FOR MEMORY EFFICIENCY
# ================================================================================
#
# IMPORTANT: This code is intentionally DUPLICATED from heimdall/monitoring/file_types.py
# to avoid importing from the heimdall package, which would load all heavy dependencies
# (200MB+ ML stack) into the lightweight monitoring process.
#
# MAINTENANCE STRATEGY:
# 1. Any changes to file monitoring logic should be made in BOTH files
# 2. Keep this copy minimal - only include what's needed for monitoring
# 3. Add tests to ensure both implementations stay in sync
# 4. Consider this technical debt that enables <50MB memory target
#
# WHY THIS APPROACH:
# - Python package imports load ALL dependencies transitively
# - heimdall package includes onnxruntime, numpy, spacy, qdrant (200MB+)
# - Standalone script with copied code uses only stdlib + lightweight deps (~20MB)
# - Achieves architecture goal of lightweight monitoring with subprocess delegation
#
# COPIED FROM: heimdall/monitoring/file_types.py
# LAST SYNC: 2025-06-25
# ================================================================================
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import portalocker
from loguru import logger


class ChangeType(Enum):
    """Types of file changes that can be detected."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class FileChangeEvent:
    """Represents a file change event."""

    path: Path
    change_type: ChangeType
    timestamp: float

    def __str__(self) -> str:
        change_type_str = getattr(self.change_type, "value", str(self.change_type))
        return f"{change_type_str}: {self.path} at {self.timestamp}"


@dataclass
class FileState:
    """Tracks the state of a monitored file."""

    path: Path
    exists: bool
    mtime: float | None = None
    size: int | None = None

    @classmethod
    def from_path(cls, path: Path) -> "FileState":
        """Create FileState by examining the current file."""
        try:
            if path.exists():
                stat = path.stat()
                return cls(
                    path=path, exists=True, mtime=stat.st_mtime, size=stat.st_size
                )
            else:
                return cls(path=path, exists=False)
        except (OSError, PermissionError) as e:
            logger.warning(f"Cannot stat file {path}: {e}")
            return cls(path=path, exists=False)

    def has_changed(self, other: "FileState") -> bool:
        """Check if this state differs from another state."""
        if self.exists != other.exists:
            return True
        if self.exists and other.exists:
            return self.mtime != other.mtime or self.size != other.size
        return False

    def detect_change_type(self, previous: "FileState") -> ChangeType | None:
        """Determine the type of change from previous state."""
        if not previous.exists and self.exists:
            return ChangeType.ADDED
        elif previous.exists and not self.exists:
            return ChangeType.DELETED
        elif (
            previous.exists
            and self.exists
            and (self.mtime != previous.mtime or self.size != previous.size)
        ):
            return ChangeType.MODIFIED
        return None


class FileMonitor:
    """
    Minimal file monitor with no heavy dependencies.

    Monitors markdown files for changes using polling-based detection.
    This implementation has minimal memory footprint and no ML dependencies.
    """

    # Supported markdown file extensions
    MARKDOWN_EXTENSIONS = {".md", ".markdown", ".mdown", ".mkd"}

    def __init__(
        self, polling_interval: float = 5.0, ignore_patterns: set[str] | None = None
    ):
        """Initialize file monitor."""
        self.polling_interval = polling_interval
        self.ignore_patterns = ignore_patterns or {
            ".git",
            "__pycache__",
            ".pytest_cache",
        }
        self.file_states: dict[Path, FileState] = {}
        self.callbacks: dict[ChangeType, list[Callable[[FileChangeEvent], None]]] = {
            ChangeType.ADDED: [],
            ChangeType.MODIFIED: [],
            ChangeType.DELETED: [],
        }
        self.monitoring = False
        self.monitor_thread: threading.Thread | None = None
        self.monitored_paths: set[Path] = set()

    def register_callback(
        self, change_type: ChangeType, callback: Callable[[FileChangeEvent], None]
    ) -> None:
        """Register callback for specific change type."""
        self.callbacks[change_type].append(callback)
        logger.debug(f"Registered callback for {change_type.value} events")

    def add_path(self, path: Path) -> None:
        """Add path to monitoring."""
        if path.is_dir():
            self.monitored_paths.add(path)
            logger.debug(f"Added directory to monitoring: {path}")
        else:
            logger.warning(f"Path is not a directory: {path}")

    def remove_path(self, path: Path) -> None:
        """Remove path from monitoring."""
        if path in self.monitored_paths:
            self.monitored_paths.remove(path)
            logger.debug(f"Removed directory from monitoring: {path}")
        else:
            logger.warning(f"Path not currently monitored: {path}")

    def get_monitored_files(self) -> set[Path]:
        """Get all markdown files in monitored paths."""
        files = set()
        for path in self.monitored_paths:
            if path.exists() and path.is_dir():
                for file_path in path.rglob("*"):
                    if (
                        file_path.is_file()
                        and file_path.suffix.lower() in self.MARKDOWN_EXTENSIONS
                        and not self._should_ignore_path(file_path)
                    ):
                        files.add(file_path)
        return files

    def _should_ignore_path(self, path: Path) -> bool:
        """Check if path should be ignored."""
        path_str = str(path)
        return any(pattern in path_str for pattern in self.ignore_patterns)

    def start_monitoring(self) -> None:
        """Start file monitoring in background thread."""
        import threading

        if self.monitoring:
            logger.warning("File monitoring is already running")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"Started file monitoring with {self.polling_interval}s interval")

    def stop_monitoring(self) -> None:
        """Stop file monitoring."""
        if not self.monitoring:
            logger.warning("File monitoring is not running")
            return

        logger.info("Stopping file monitoring...")
        self.monitoring = False

        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
            if self.monitor_thread.is_alive():
                logger.warning("Monitor thread did not stop within timeout")
            else:
                logger.info("File monitoring stopped")

        self.monitor_thread = None

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        logger.debug("File monitoring loop started")

        while self.monitoring:
            try:
                self._scan_files()
                time.sleep(self.polling_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.polling_interval)

        logger.debug("File monitoring loop ended")

    def _scan_files(self) -> None:
        """Scan files for changes and emit events."""
        current_files = self.get_monitored_files()
        current_states = {path: FileState.from_path(path) for path in current_files}

        # Check for deleted files
        for path in set(self.file_states.keys()) - current_files:
            if path in self.file_states:
                deleted_state = FileState(path=path, exists=False)
                change_type = deleted_state.detect_change_type(self.file_states[path])
                if change_type == ChangeType.DELETED:
                    self._emit_event(
                        FileChangeEvent(
                            path=path, change_type=change_type, timestamp=time.time()
                        )
                    )
                del self.file_states[path]

        # Check for added and modified files
        for path, current_state in current_states.items():
            previous_state = self.file_states.get(path)

            if previous_state is None:
                # New file
                self._emit_event(
                    FileChangeEvent(
                        path=path, change_type=ChangeType.ADDED, timestamp=time.time()
                    )
                )
            elif current_state.has_changed(previous_state):
                change_type = current_state.detect_change_type(previous_state)
                if change_type:
                    self._emit_event(
                        FileChangeEvent(
                            path=path, change_type=change_type, timestamp=time.time()
                        )
                    )

            self.file_states[path] = current_state

    def _emit_event(self, event: FileChangeEvent) -> None:
        """Emit file change event to registered callbacks."""
        logger.debug(f"File change detected: {event}")

        for callback in self.callbacks.get(event.change_type, []):
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in file change callback: {e}")


# ================================================================================
# END COPIED CODE
# ================================================================================


class LightweightMonitorError(Exception):
    """Base exception for lightweight monitor errors."""

    pass


class SingletonLock:
    """
    File-based singleton lock for process coordination.

    Uses portalocker for cross-platform file locking with atomic lock acquisition.
    """

    def __init__(self, lock_file_path: Path):
        """
        Initialize singleton lock.

        Args:
            lock_file_path: Path to lock file for coordination
        """
        self.lock_file_path = lock_file_path
        self.lock_file: Any = None
        self.locked = False

    def __enter__(self) -> "SingletonLock":
        """Acquire exclusive lock atomically."""
        try:
            # Create lock file if it doesn't exist
            self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Open lock file in write mode
            self.lock_file = open(self.lock_file_path, "w")

            # Try to acquire exclusive lock (non-blocking)
            portalocker.lock(self.lock_file, portalocker.LOCK_EX | portalocker.LOCK_NB)

            # Write current PID to lock file
            self.lock_file.write(str(os.getpid()))
            self.lock_file.flush()

            self.locked = True
            logger.info(f"Acquired singleton lock: {self.lock_file_path}")
            return self

        except portalocker.LockException:
            if self.lock_file:
                self.lock_file.close()
                self.lock_file = None
            raise LightweightMonitorError(
                f"Another monitoring process is already running (lock: {self.lock_file_path})"
            ) from None
        except Exception as e:
            if self.lock_file:
                self.lock_file.close()
                self.lock_file = None
            raise LightweightMonitorError(
                f"Failed to acquire singleton lock: {e}"
            ) from e

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Release lock and cleanup."""
        try:
            if self.locked and self.lock_file:
                portalocker.unlock(self.lock_file)
                self.lock_file.close()
                self.locked = False
                logger.debug(f"Released singleton lock: {self.lock_file_path}")

            # Remove lock file
            if self.lock_file_path.exists():
                self.lock_file_path.unlink()
                logger.debug(f"Removed lock file: {self.lock_file_path}")

        except Exception as e:
            logger.warning(f"Error releasing singleton lock: {e}")
        finally:
            self.lock_file = None


class EventQueue:
    """
    Thread-safe queue for file change events with deduplication.

    Provides event deduplication based on file path and change type within time windows.
    """

    def __init__(self, max_size: int = 1000):
        """
        Initialize event queue.

        Args:
            max_size: Maximum queue size before blocking
        """
        self._queue: queue.Queue[FileChangeEvent] = queue.Queue(maxsize=max_size)
        self._recent_events: dict[Path, FileChangeEvent] = {}
        self._lock = threading.Lock()

    def put(self, event: FileChangeEvent, deduplicate: bool = True) -> bool:
        """
        Add event to queue with optional deduplication.

        Args:
            event: FileChangeEvent to add
            deduplicate: Whether to deduplicate recent events for same file

        Returns:
            True if event was added, False if deduplicated
        """
        try:
            with self._lock:
                # Check for recent duplicate events
                if deduplicate and event.path in self._recent_events:
                    recent_event = self._recent_events[event.path]
                    # Skip if same event type within 1 second
                    if (
                        event.change_type == recent_event.change_type
                        and event.timestamp - recent_event.timestamp < 1.0
                    ):
                        logger.debug(f"Deduplicated event: {event}")
                        return False

                # Add to queue
                self._queue.put_nowait(event)
                self._recent_events[event.path] = event

                # Clean old recent events (keep last 100)
                if len(self._recent_events) > 100:
                    oldest_paths = list(self._recent_events.keys())[:50]
                    for path in oldest_paths:
                        del self._recent_events[path]

                return True

        except queue.Full:
            logger.error("Event queue is full, dropping event")
            return False

    def get(self, timeout: float | None = None) -> FileChangeEvent | None:
        """
        Get next event from queue.

        Args:
            timeout: Maximum time to wait for event

        Returns:
            Next FileChangeEvent or None if timeout
        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def task_done(self) -> None:
        """Mark a previously enqueued task as done."""
        self._queue.task_done()

    def qsize(self) -> int:
        """Get approximate queue size."""
        return self._queue.qsize()


class SignalHandler:
    """
    Signal handler for graceful shutdown coordination.

    Registers SIGTERM/SIGINT handlers and provides threading.Event for coordination.
    """

    def __init__(self) -> None:
        """Initialize signal handler."""
        self.shutdown_event = threading.Event()
        self._handlers_registered = False

    def register_handlers(self) -> None:
        """Register signal handlers for clean shutdown."""
        if self._handlers_registered:
            return

        def signal_handler(signum: int, frame: Any) -> None:
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.shutdown_event.set()

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        self._handlers_registered = True
        logger.debug("Signal handlers registered")

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self.shutdown_event.is_set()

    def wait_for_shutdown(self, timeout: float | None = None) -> bool:
        """
        Wait for shutdown signal.

        Args:
            timeout: Maximum time to wait

        Returns:
            True if shutdown was signaled, False if timeout
        """
        return self.shutdown_event.wait(timeout)


class MarkdownFileWatcher:
    """
    Markdown file monitoring with event queue integration.

    Wraps FileMonitor and forwards events to internal EventQueue.
    """

    def __init__(
        self, polling_interval: float = 5.0, ignore_patterns: set[str] | None = None
    ):
        """
        Initialize file watcher.

        Args:
            polling_interval: Seconds between polling checks
            ignore_patterns: Set of patterns to ignore
        """
        self.polling_interval = polling_interval
        self.ignore_patterns = ignore_patterns or {
            ".git",
            "node_modules",
            "__pycache__",
        }

        # Create underlying monitor
        self.monitor = FileMonitor(
            polling_interval=polling_interval, ignore_patterns=self.ignore_patterns
        )

        # Event queue for processing
        self.event_queue = EventQueue()

        # Register callbacks to forward events to queue
        for change_type in [ChangeType.ADDED, ChangeType.MODIFIED, ChangeType.DELETED]:
            self.monitor.register_callback(change_type, self._on_file_change)

        logger.debug(
            f"MarkdownFileWatcher initialized with {polling_interval}s interval"
        )

    def add_path(self, path: str | Path) -> None:
        """Add path to monitoring."""
        path_obj = Path(path) if isinstance(path, str) else path
        self.monitor.add_path(path_obj)
        logger.debug(f"Added path to watcher: {path}")

    def remove_path(self, path: str | Path) -> None:
        """Remove path from monitoring."""
        path_obj = Path(path) if isinstance(path, str) else path
        self.monitor.remove_path(path_obj)
        logger.debug(f"Removed path from watcher: {path}")

    def start_monitoring(self) -> None:
        """Start file monitoring."""
        self.monitor.start_monitoring()
        logger.info("File monitoring started")

    def stop_monitoring(self) -> None:
        """Stop file monitoring."""
        self.monitor.stop_monitoring()
        logger.info("File monitoring stopped")

    def get_monitored_files(self) -> set[Path]:
        """Get set of monitored files."""
        return self.monitor.get_monitored_files()

    def _on_file_change(self, event: FileChangeEvent) -> None:
        """Handle file change by adding to event queue."""
        added = self.event_queue.put(event, deduplicate=True)
        if added:
            logger.debug(f"Queued file change event: {event}")


class LightweightMonitor:
    """
    File monitoring process with subprocess delegation.

    Monitors file changes and delegates cognitive operations to CLI subprocesses.
    """

    def __init__(self, project_root: Path, target_path: Path, lock_file: Path):
        """
        Initialize lightweight monitor.

        Args:
            project_root: Root directory of the project
            target_path: Path to monitor for file changes
            lock_file: Path to singleton lock file
        """
        self.project_root = project_root
        self.target_path = target_path
        self.lock_file_path = lock_file

        # Components
        self.singleton_lock: SingletonLock | None = None
        self.signal_handler = SignalHandler()
        self.file_watcher: MarkdownFileWatcher | None = None
        self.processing_thread: threading.Thread | None = None

        # State
        self.running = False
        self.started_at: float | None = None
        self.stats: dict[str, Any] = {
            "started_at": None,
            "files_processed": 0,
            "subprocess_calls": 0,
            "subprocess_errors": 0,
            "subprocess_retries": 0,
            "subprocess_timeouts": 0,
            "last_activity": None,
        }

        # Status file for daemon communication
        self.status_file = self.project_root / ".heimdall" / "monitor_status.json"

        # Subprocess configuration
        self.max_retries = 3
        self.retry_delay = 2.0  # seconds
        self.subprocess_timeout = 300  # 5 minutes

        logger.info(f"LightweightMonitor initialized for project: {project_root}")

    def start(self) -> bool:
        """
        Start lightweight monitoring with singleton enforcement.

        Returns:
            True if started successfully, False otherwise
        """
        try:
            logger.info("Starting lightweight monitoring...")

            # Acquire singleton lock
            self.singleton_lock = SingletonLock(self.lock_file_path)
            self.singleton_lock.__enter__()

            # Register signal handlers
            self.signal_handler.register_handlers()

            # Initialize file watcher
            self.file_watcher = MarkdownFileWatcher(polling_interval=5.0)
            self.file_watcher.add_path(self.target_path)

            # Start file monitoring
            self.file_watcher.start_monitoring()

            # Start event processing thread
            self.processing_thread = threading.Thread(
                target=self._event_processing_loop, name="EventProcessor", daemon=True
            )
            self.processing_thread.start()

            # Update state
            self.running = True
            started_time = time.time()
            self.started_at = started_time
            self.stats["started_at"] = started_time

            # Write initial status file
            self._write_status_file()

            logger.info("Lightweight monitoring started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start lightweight monitoring: {e}")
            self.stop()
            return False

    def stop(self) -> bool:
        """
        Stop monitoring and cleanup resources.

        Returns:
            True if stopped successfully, False otherwise
        """
        try:
            logger.info("Stopping lightweight monitoring...")

            # Signal shutdown
            self.running = False
            self.signal_handler.shutdown_event.set()

            # Stop file monitoring
            if self.file_watcher:
                self.file_watcher.stop_monitoring()

            # Wait for processing thread to finish
            if self.processing_thread and self.processing_thread.is_alive():
                self.processing_thread.join(timeout=10.0)
                if self.processing_thread.is_alive():
                    logger.warning("Processing thread did not stop cleanly")

            # Release singleton lock
            if self.singleton_lock:
                self.singleton_lock.__exit__(None, None, None)
                self.singleton_lock = None

            logger.info("Lightweight monitoring stopped")
            return True

        except Exception as e:
            logger.error(f"Error stopping lightweight monitoring: {e}")
            return False

    def run_daemon_loop(self) -> None:
        """Run main daemon loop until shutdown."""
        logger.info("Entering lightweight monitoring daemon loop...")

        try:
            status_update_counter = 0
            status_update_interval = 10  # Update status every 10 seconds

            while self.running and not self.signal_handler.is_shutdown_requested():
                # Simple heartbeat loop - actual work done in processing thread
                time.sleep(1.0)

                # Periodically update status file with current memory usage
                status_update_counter += 1
                if status_update_counter >= status_update_interval:
                    self._write_status_file()
                    status_update_counter = 0

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Error in daemon loop: {e}")
        finally:
            self.stop()

    def _event_processing_loop(self) -> None:
        """Process file change events using subprocess delegation."""
        logger.debug("Event processing loop started")

        while self.running and not self.signal_handler.is_shutdown_requested():
            try:
                # Get next event with timeout
                if not self.file_watcher:
                    break

                event = self.file_watcher.event_queue.get(timeout=1.0)
                if event is None:
                    continue

                # Process event via subprocess delegation
                success = self._handle_file_change_subprocess(event)

                # Update statistics
                self.stats["files_processed"] = (self.stats["files_processed"] or 0) + 1
                activity_time = time.time()
                self.stats["last_activity"] = activity_time

                if not success:
                    self.stats["subprocess_errors"] = (
                        self.stats["subprocess_errors"] or 0
                    ) + 1

                # Mark task as done
                self.file_watcher.event_queue.task_done()

            except Exception as e:
                logger.error(f"Error in event processing loop: {e}")

        logger.debug("Event processing loop ended")

    def _handle_file_change_subprocess(self, event: FileChangeEvent) -> bool:
        """
        Handle file change by delegating to CLI subprocess with retry logic.

        Args:
            event: File change event to process

        Returns:
            True if subprocess completed successfully, False otherwise
        """
        try:
            logger.info(f"Processing file change via subprocess: {event}")

            # Map change type to CLI command
            cmd = self._build_subprocess_command(event)
            if not cmd:
                return False

            # Execute subprocess with retry logic
            return self._execute_subprocess_with_retry(cmd, event)

        except Exception as e:
            logger.error(
                f"Error handling file change subprocess for event {event}: {e}"
            )
            return False

    def _build_subprocess_command(self, event: FileChangeEvent) -> list[str] | None:
        """
        Build CLI command for file change event.

        Args:
            event: File change event to process

        Returns:
            CLI command as list of strings, or None if unsupported event type
        """
        if event.change_type in [ChangeType.ADDED, ChangeType.MODIFIED]:
            return ["heimdall", "load", str(event.path)]
        elif event.change_type == ChangeType.DELETED:
            return ["heimdall", "remove-file", str(event.path)]
        else:
            logger.error(f"Unknown change type: {event.change_type}")
            return None

    def _execute_subprocess_with_retry(
        self, cmd: list[str], event: FileChangeEvent
    ) -> bool:
        """
        Execute subprocess with retry logic and comprehensive logging.

        Args:
            cmd: CLI command to execute
            event: File change event being processed

        Returns:
            True if subprocess completed successfully, False otherwise
        """
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                # Log attempt
                if attempt > 0:
                    logger.info(
                        f"Retrying subprocess (attempt {attempt + 1}/{self.max_retries + 1}): {' '.join(cmd)}"
                    )
                    self.stats["subprocess_retries"] = (
                        self.stats["subprocess_retries"] or 0
                    ) + 1
                    # Wait before retry
                    time.sleep(self.retry_delay * attempt)

                # Execute subprocess
                start_time = time.time()
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.subprocess_timeout,
                    cwd=self.project_root,
                )

                execution_time = time.time() - start_time
                self.stats["subprocess_calls"] = (
                    self.stats["subprocess_calls"] or 0
                ) + 1

                # Process result
                if result.returncode == 0:
                    logger.info(
                        f"Subprocess completed successfully in {execution_time:.2f}s "
                        f"(attempt {attempt + 1}): {' '.join(cmd)}"
                    )
                    self._log_subprocess_output(result, success=True)
                    return True
                else:
                    error_msg = (
                        f"Subprocess failed (exit code {result.returncode}) "
                        f"after {execution_time:.2f}s (attempt {attempt + 1}): {' '.join(cmd)}"
                    )
                    logger.warning(error_msg)
                    self._log_subprocess_output(result, success=False)
                    last_error = f"Exit code {result.returncode}: {result.stderr.strip() if result.stderr else 'No stderr'}"

                    # Check if this is a permanent failure (don't retry)
                    if self._is_permanent_failure(result.returncode, result.stderr):
                        logger.error(
                            f"Permanent failure detected, not retrying: {last_error}"
                        )
                        break

            except subprocess.TimeoutExpired:
                timeout_msg = f"Subprocess timeout ({self.subprocess_timeout}s) for event: {event}"
                logger.error(timeout_msg)
                self.stats["subprocess_timeouts"] = (
                    self.stats["subprocess_timeouts"] or 0
                ) + 1
                last_error = "Subprocess timeout"

                # Timeout is usually not worth retrying immediately
                if attempt < self.max_retries:
                    logger.info(
                        f"Will retry after timeout (attempt {attempt + 1}/{self.max_retries + 1})"
                    )
                    time.sleep(self.retry_delay * (attempt + 1))

            except Exception as e:
                error_msg = f"Error executing subprocess (attempt {attempt + 1}): {e}"
                logger.error(error_msg)
                last_error = str(e)

        # All attempts failed
        logger.error(
            f"Subprocess failed after {self.max_retries + 1} attempts. "
            f"Last error: {last_error}. Command: {' '.join(cmd)}"
        )
        return False

    def _log_subprocess_output(
        self, result: subprocess.CompletedProcess, success: bool
    ) -> None:
        """
        Log subprocess output with appropriate log levels.

        Args:
            result: Completed subprocess result
            success: Whether the subprocess succeeded
        """
        if result.stdout:
            if success:
                logger.debug(f"Subprocess stdout: {result.stdout.strip()}")
            else:
                logger.info(f"Subprocess stdout: {result.stdout.strip()}")

        if result.stderr:
            if success:
                logger.debug(f"Subprocess stderr: {result.stderr.strip()}")
            else:
                logger.error(f"Subprocess stderr: {result.stderr.strip()}")

    def _is_permanent_failure(self, return_code: int, stderr: str | None) -> bool:
        """
        Determine if a subprocess failure is permanent and should not be retried.

        Args:
            return_code: Subprocess exit code
            stderr: Subprocess stderr output

        Returns:
            True if failure is permanent, False if retry might succeed
        """
        # Command not found or permission denied
        if return_code in [127, 126]:
            return True

        # Check stderr for permanent error indicators
        if stderr:
            stderr_lower = stderr.lower()
            permanent_errors = [
                "command not found",
                "permission denied",
                "no such file or directory",
                "invalid argument",
                "file not found",
            ]
            for error in permanent_errors:
                if error in stderr_lower:
                    return True

        return False

    def get_status(self) -> dict[str, Any]:
        """
        Get current monitoring status.

        Returns:
            Dictionary containing status information
        """
        return {
            "running": self.running,
            "pid": os.getpid() if self.running else None,
            "started_at": self.stats["started_at"],
            "uptime_seconds": (
                time.time() - self.started_at if self.started_at else None
            ),
            "files_monitored": (
                len(self.file_watcher.get_monitored_files()) if self.file_watcher else 0
            ),
            "files_processed": self.stats["files_processed"],
            "subprocess_calls": self.stats["subprocess_calls"],
            "subprocess_errors": self.stats["subprocess_errors"],
            "subprocess_retries": self.stats["subprocess_retries"],
            "subprocess_timeouts": self.stats["subprocess_timeouts"],
            "last_activity": self.stats["last_activity"],
            "event_queue_size": (
                self.file_watcher.event_queue.qsize() if self.file_watcher else 0
            ),
        }

    def _get_memory_usage(self) -> float | None:
        """Get current memory usage in MB."""
        try:
            import psutil

            process = psutil.Process(os.getpid())
            return float(process.memory_info().rss / 1024 / 1024)
        except (ImportError, psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def _get_cpu_percent(self) -> float | None:
        """Get current CPU usage percentage."""
        try:
            import psutil

            process = psutil.Process(os.getpid())
            return float(process.cpu_percent())
        except (ImportError, psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def _write_status_file(self) -> None:
        """Write current status to shared JSON file for CLI communication."""
        try:
            import json

            status_data = {
                "started_at": self.stats["started_at"],
                "pid": os.getpid(),
                "is_running": self.running,
                "uptime_seconds": time.time() - self.started_at
                if self.started_at
                else None,
                "error_count": 0,  # Lightweight monitor doesn't track service-level errors
                "last_error": None,
                "restart_count": 0,  # Lightweight monitor doesn't track restarts
                "files_monitored": len(self.file_watcher.get_monitored_files())
                if self.file_watcher
                else 0,
                "sync_operations": self.stats["subprocess_calls"],
                "last_sync_time": self.stats["last_activity"],
                "memory_usage_mb": self._get_memory_usage(),
                "cpu_percent": self._get_cpu_percent(),
                "subprocess_calls": self.stats["subprocess_calls"],
                "subprocess_errors": self.stats["subprocess_errors"],
                "subprocess_retries": self.stats["subprocess_retries"],
                "subprocess_timeouts": self.stats["subprocess_timeouts"],
                "files_processed": self.stats["files_processed"],
                "event_queue_size": self.file_watcher.event_queue.qsize()
                if self.file_watcher
                else 0,
            }

            # Ensure status directory exists
            self.status_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.status_file, "w") as f:
                json.dump(status_data, f, indent=2)

            logger.debug(f"Status file updated: {self.status_file}")
        except Exception as e:
            logger.warning(f"Failed to write status file: {e}")


def main() -> int:
    """Main entry point for lightweight monitoring daemon."""
    parser = argparse.ArgumentParser(
        description="Lightweight file monitoring daemon with subprocess delegation"
    )
    parser.add_argument(
        "--project-root", required=True, help="Root directory of the project"
    )
    parser.add_argument(
        "--target-path", required=True, help="Path to monitor for file changes"
    )
    parser.add_argument(
        "--lock-file", required=True, help="Path to singleton lock file"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    args = parser.parse_args()

    # Configure logging
    logger.remove()  # Remove default handler

    # Add stderr logging
    logger.add(
        sys.stderr,
        level=args.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    # Add file logging to monitor.log
    log_file = Path(args.project_root) / ".heimdall" / "monitor.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_file),
        level="DEBUG",  # Always log DEBUG and above to file
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",  # Rotate when file gets large
        retention="7 days",  # Keep logs for 7 days
    )

    logger.info(
        f"Starting lightweight monitoring daemon for project: {args.project_root}"
    )

    try:
        # Create LightweightMonitor instance
        monitor = LightweightMonitor(
            project_root=Path(args.project_root),
            target_path=Path(args.target_path),
            lock_file=Path(args.lock_file),
        )

        # Start monitoring
        success = monitor.start()
        if not success:
            logger.error("Failed to start lightweight monitoring")
            return 1

        logger.info("Lightweight monitoring started successfully")

        # Run daemon loop
        monitor.run_daemon_loop()

        logger.info("Lightweight monitoring daemon exiting")
        return 0

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
        return 0
    except Exception as e:
        logger.error(f"Error in lightweight monitoring daemon: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
