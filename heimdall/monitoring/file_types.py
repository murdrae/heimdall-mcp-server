#!/usr/bin/env python3
"""
Lightweight file monitoring types and utilities.

This module contains minimal file monitoring definitions that can be imported
without heavy dependencies like ML models, ONNX runtime, etc.
"""

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
