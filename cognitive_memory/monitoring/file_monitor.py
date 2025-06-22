"""
File monitoring system for automatic markdown file change detection.

This module implements a polling-based file monitoring system that detects
changes to markdown files and triggers memory synchronization events.
Uses a simple polling approach for cross-platform reliability.
"""

import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

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


class MarkdownFileMonitor:
    """
    Monitors markdown files for changes using polling-based detection.

    This class provides a simple, cross-platform file monitoring solution
    that detects additions, modifications, and deletions of markdown files.
    """

    # Supported markdown file extensions
    MARKDOWN_EXTENSIONS = {".md", ".markdown", ".mdown", ".mkd"}

    def __init__(
        self, polling_interval: float = 5.0, ignore_patterns: set[str] | None = None
    ):
        """
        Initialize the file monitor.

        Args:
            polling_interval: Seconds between polling checks
            ignore_patterns: Set of patterns to ignore (e.g., {".git", "node_modules"})
        """
        self.polling_interval = polling_interval
        self.ignore_patterns = ignore_patterns or {
            ".git",
            "node_modules",
            "__pycache__",
        }

        # State tracking
        self._monitored_paths: set[Path] = set()
        self._file_states: dict[Path, FileState] = {}
        self._callbacks: dict[ChangeType, list[Callable[[FileChangeEvent], None]]] = {
            ChangeType.ADDED: [],
            ChangeType.MODIFIED: [],
            ChangeType.DELETED: [],
        }

        # Threading
        self._monitoring = False
        self._monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        logger.debug(
            f"MarkdownFileMonitor initialized with {polling_interval}s interval"
        )

    def add_path(self, path: str | Path) -> None:
        """
        Add a file or directory to monitor.

        Args:
            path: Path to file or directory to monitor
        """
        path = Path(path).resolve()

        if not path.exists():
            logger.warning(f"Path does not exist: {path}")
            return

        self._monitored_paths.add(path)

        # Initialize file states for existing files
        if path.is_file() and self._is_markdown_file(path):
            self._file_states[path] = FileState.from_path(path)
            logger.debug(f"Added file to monitoring: {path}")
        elif path.is_dir():
            self._scan_directory(path)
            logger.debug(f"Added directory to monitoring: {path}")

    def remove_path(self, path: str | Path) -> None:
        """
        Remove a path from monitoring.

        Args:
            path: Path to stop monitoring
        """
        path = Path(path).resolve()
        self._monitored_paths.discard(path)

        # Remove file states for files under this path
        to_remove = []
        for file_path in self._file_states:
            try:
                if file_path == path or path in file_path.parents:
                    to_remove.append(file_path)
            except OSError:
                # Handle cases where path comparison fails
                to_remove.append(file_path)

        for file_path in to_remove:
            del self._file_states[file_path]

        logger.debug(f"Removed path from monitoring: {path}")

    def register_callback(
        self, change_type: ChangeType, callback: Callable[[FileChangeEvent], None]
    ) -> None:
        """
        Register a callback for specific change types.

        Args:
            change_type: Type of change to listen for
            callback: Function to call when change occurs
        """
        self._callbacks[change_type].append(callback)
        logger.debug(f"Registered callback for {change_type.value} events")

    def start_monitoring(self) -> None:
        """Start the file monitoring in a background thread."""
        if self._monitoring:
            logger.warning("File monitoring is already running")
            return

        self._monitoring = True
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, name="FileMonitor", daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"Started file monitoring with {self.polling_interval}s interval")

    def stop_monitoring(self) -> None:
        """Stop the file monitoring and wait for thread to finish."""
        if not self._monitoring:
            return

        logger.info("Stopping file monitoring...")
        self._monitoring = False
        self._stop_event.set()

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=10.0)
            if self._monitor_thread.is_alive():
                logger.error("Failed to stop monitoring thread cleanly")

        logger.info("File monitoring stopped")

    def get_monitored_files(self) -> set[Path]:
        """Get the set of currently monitored files."""
        return set(self._file_states.keys())

    def _monitor_loop(self) -> None:
        """Main monitoring loop that runs in background thread."""
        logger.debug("File monitoring loop started")

        while self._monitoring and not self._stop_event.is_set():
            try:
                self._poll_changes()
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            # Wait for next polling interval or stop event
            if self._stop_event.wait(timeout=self.polling_interval):
                break  # Stop event was set

        logger.debug("File monitoring loop ended")

    def _poll_changes(self) -> None:
        """Poll for file changes and emit events."""
        # Collect all files that should be monitored
        current_files = set()
        for path in self._monitored_paths:
            if path.is_file() and self._is_markdown_file(path):
                current_files.add(path)
            elif path.is_dir():
                current_files.update(self._scan_directory_files(path))

        # Get current states
        current_states = {}
        for file_path in current_files:
            try:
                current_states[file_path] = FileState.from_path(file_path)
            except Exception as e:
                logger.warning(f"Failed to get state for {file_path}: {e}")

        # Detect changes by comparing with previous states
        events = []

        # Check for modifications and deletions
        for file_path, previous_state in self._file_states.items():
            current_state = current_states.get(file_path)

            if current_state is None:
                # File was deleted or moved out of monitored paths
                if previous_state.exists:
                    events.append(
                        FileChangeEvent(
                            path=file_path,
                            change_type=ChangeType.DELETED,
                            timestamp=time.time(),
                        )
                    )
            else:
                # Check for modifications
                change_type = current_state.detect_change_type(previous_state)
                if change_type:
                    events.append(
                        FileChangeEvent(
                            path=file_path,
                            change_type=change_type,
                            timestamp=time.time(),
                        )
                    )

        # Check for new files
        for file_path, current_state in current_states.items():
            if file_path not in self._file_states and current_state.exists:
                events.append(
                    FileChangeEvent(
                        path=file_path,
                        change_type=ChangeType.ADDED,
                        timestamp=time.time(),
                    )
                )

        # Update file states
        self._file_states = current_states

        # Emit events
        for event in events:
            self._emit_event(event)

    def _emit_event(self, event: FileChangeEvent) -> None:
        """Emit a file change event to registered callbacks."""
        logger.debug(f"File change detected: {event}")

        callbacks = self._callbacks.get(event.change_type, [])
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in change callback: {e}")

    def _scan_directory(self, directory: Path) -> None:
        """Scan directory and initialize file states for markdown files."""
        for file_path in self._scan_directory_files(directory):
            self._file_states[file_path] = FileState.from_path(file_path)

    def _scan_directory_files(self, directory: Path) -> set[Path]:
        """Get all markdown files in directory (recursive)."""
        markdown_files = set()

        try:
            for root, dirs, files in os.walk(directory):
                root_path = Path(root)

                # Skip ignored directories
                dirs[:] = [d for d in dirs if not self._should_ignore(d)]

                for filename in files:
                    file_path = root_path / filename
                    if not self._should_ignore(filename) and self._is_markdown_file(
                        file_path
                    ):
                        markdown_files.add(file_path)
        except (OSError, PermissionError) as e:
            logger.warning(f"Cannot scan directory {directory}: {e}")

        return markdown_files

    def _is_markdown_file(self, path: Path) -> bool:
        """Check if file is a markdown file based on extension."""
        return path.suffix.lower() in self.MARKDOWN_EXTENSIONS

    def _should_ignore(self, name: str) -> bool:
        """Check if file/directory name should be ignored."""
        return any(pattern in name for pattern in self.ignore_patterns)
