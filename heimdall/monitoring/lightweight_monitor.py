#!/usr/bin/env python3
"""
Lightweight file monitoring process with subprocess delegation.

Provides file change detection and delegates cognitive operations to CLI subprocesses.
"""

import os
import queue
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import portalocker
from loguru import logger

from cognitive_memory.monitoring import (
    ChangeType,
    FileChangeEvent,
    MarkdownFileMonitor,
)


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

    Wraps MarkdownFileMonitor and forwards events to internal EventQueue.
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
        self.monitor = MarkdownFileMonitor(
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
        self.monitor.add_path(path)
        logger.debug(f"Added path to watcher: {path}")

    def remove_path(self, path: str | Path) -> None:
        """Remove path from monitoring."""
        self.monitor.remove_path(path)
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
            while self.running and not self.signal_handler.is_shutdown_requested():
                # Simple heartbeat loop - actual work done in processing thread
                time.sleep(1.0)

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
