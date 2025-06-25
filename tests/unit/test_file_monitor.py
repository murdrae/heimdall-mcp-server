"""
Unit tests for file monitoring system.

Tests the FileMonitor, FileChangeEvent, and related components
for automatic file change detection.
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from heimdall.monitoring.file_types import (
    ChangeType,
    FileChangeEvent,
    FileMonitor,
    FileState,
)


class TestFileState:
    """Test FileState data structure and methods."""

    def test_file_state_creation_existing_file(self, tmp_path):
        """Test FileState creation for existing file."""
        test_file = tmp_path / "test.md"
        test_file.write_text("content")

        state = FileState.from_path(test_file)

        assert state.path == test_file
        assert state.exists is True
        assert state.mtime is not None
        assert state.size == len("content")

    def test_file_state_creation_nonexistent_file(self, tmp_path):
        """Test FileState creation for non-existent file."""
        test_file = tmp_path / "nonexistent.md"

        state = FileState.from_path(test_file)

        assert state.path == test_file
        assert state.exists is False
        assert state.mtime is None
        assert state.size is None

    def test_file_state_has_changed_existence(self, tmp_path):
        """Test change detection for file existence."""
        test_file = tmp_path / "test.md"

        # Non-existent -> existing
        old_state = FileState(path=test_file, exists=False)
        test_file.write_text("content")
        new_state = FileState.from_path(test_file)

        assert new_state.has_changed(old_state)

    def test_file_state_has_changed_content(self, tmp_path):
        """Test change detection for file content."""
        test_file = tmp_path / "test.md"
        test_file.write_text("original")

        old_state = FileState.from_path(test_file)

        # Modify content
        time.sleep(0.01)  # Ensure mtime difference
        test_file.write_text("modified")
        new_state = FileState.from_path(test_file)

        assert new_state.has_changed(old_state)

    def test_file_state_no_change(self, tmp_path):
        """Test no change detection when file unchanged."""
        test_file = tmp_path / "test.md"
        test_file.write_text("content")

        state1 = FileState.from_path(test_file)
        state2 = FileState.from_path(test_file)

        assert not state2.has_changed(state1)

    def test_detect_change_type_added(self, tmp_path):
        """Test detection of file addition."""
        test_file = tmp_path / "test.md"

        old_state = FileState(path=test_file, exists=False)
        test_file.write_text("content")
        new_state = FileState.from_path(test_file)

        change_type = new_state.detect_change_type(old_state)
        assert change_type == ChangeType.ADDED

    def test_detect_change_type_deleted(self, tmp_path):
        """Test detection of file deletion."""
        test_file = tmp_path / "test.md"
        test_file.write_text("content")

        old_state = FileState.from_path(test_file)
        test_file.unlink()
        new_state = FileState.from_path(test_file)

        change_type = new_state.detect_change_type(old_state)
        assert change_type == ChangeType.DELETED

    def test_detect_change_type_modified(self, tmp_path):
        """Test detection of file modification."""
        test_file = tmp_path / "test.md"
        test_file.write_text("original")

        old_state = FileState.from_path(test_file)

        time.sleep(0.01)  # Ensure mtime difference
        test_file.write_text("modified")
        new_state = FileState.from_path(test_file)

        change_type = new_state.detect_change_type(old_state)
        assert change_type == ChangeType.MODIFIED


class TestFileChangeEvent:
    """Test FileChangeEvent data structure."""

    def test_file_change_event_creation(self, tmp_path):
        """Test FileChangeEvent creation."""
        test_file = tmp_path / "test.md"
        timestamp = time.time()

        event = FileChangeEvent(
            path=test_file, change_type=ChangeType.ADDED, timestamp=timestamp
        )

        assert event.path == test_file
        assert event.change_type == ChangeType.ADDED
        assert event.timestamp == timestamp

    def test_file_change_event_string_representation(self, tmp_path):
        """Test string representation of FileChangeEvent."""
        test_file = tmp_path / "test.md"
        timestamp = 1234567890.0

        event = FileChangeEvent(
            path=test_file, change_type=ChangeType.MODIFIED, timestamp=timestamp
        )

        str_repr = str(event)
        assert "modified" in str_repr
        assert str(test_file) in str_repr
        assert str(timestamp) in str_repr


class TestFileMonitor:
    """Test FileMonitor class."""

    def test_monitor_initialization(self):
        """Test monitor initialization with default parameters."""
        monitor = FileMonitor()

        assert monitor.polling_interval == 5.0
        assert ".git" in monitor.ignore_patterns
        assert "node_modules" in monitor.ignore_patterns
        assert not monitor._monitoring
        assert monitor._monitor_thread is None

    def test_monitor_initialization_custom_params(self):
        """Test monitor initialization with custom parameters."""
        custom_ignore = {"custom_ignore"}
        monitor = FileMonitor(polling_interval=2.0, ignore_patterns=custom_ignore)

        assert monitor.polling_interval == 2.0
        assert monitor.ignore_patterns == custom_ignore

    def test_add_file_path(self, tmp_path):
        """Test adding a single file to monitoring."""
        monitor = FileMonitor()
        test_file = tmp_path / "test.md"
        test_file.write_text("content")

        monitor.add_path(test_file)

        assert test_file.resolve() in monitor._monitored_paths
        assert test_file in monitor._file_states

    def test_add_directory_path(self, tmp_path):
        """Test adding a directory to monitoring."""
        monitor = FileMonitor()

        # Create some files
        (tmp_path / "test1.md").write_text("content1")
        (tmp_path / "test2.markdown").write_text("content2")
        (tmp_path / "ignore.txt").write_text("ignore")

        monitor.add_path(tmp_path)

        assert tmp_path.resolve() in monitor._monitored_paths
        # Should only track markdown files
        md_files = {
            f for f in monitor._file_states.keys() if f.suffix in {".md", ".markdown"}
        }
        assert len(md_files) == 2

    def test_add_nonexistent_path(self, tmp_path):
        """Test adding non-existent path (should log warning)."""
        monitor = FileMonitor()
        nonexistent = tmp_path / "nonexistent"

        with patch("heimdall.monitoring.file_types.logger") as mock_logger:
            monitor.add_path(nonexistent)
            mock_logger.warning.assert_called_once()

        assert nonexistent.resolve() not in monitor._monitored_paths

    def test_remove_path(self, tmp_path):
        """Test removing path from monitoring."""
        monitor = FileMonitor()
        test_file = tmp_path / "test.md"
        test_file.write_text("content")

        monitor.add_path(test_file)
        assert test_file.resolve() in monitor._monitored_paths

        monitor.remove_path(test_file)
        assert test_file.resolve() not in monitor._monitored_paths
        assert test_file not in monitor._file_states

    def test_register_callback(self):
        """Test callback registration."""
        monitor = FileMonitor()
        callback = Mock()

        monitor.register_callback(ChangeType.ADDED, callback)

        assert callback in monitor.callbacks[ChangeType.ADDED]

    def test_markdown_file_detection(self):
        """Test markdown file detection through extensions."""
        monitor = FileMonitor()

        # Test markdown extensions
        assert ".md" in monitor.MARKDOWN_EXTENSIONS
        assert ".markdown" in monitor.MARKDOWN_EXTENSIONS
        assert ".mdown" in monitor.MARKDOWN_EXTENSIONS
        assert ".mkd" in monitor.MARKDOWN_EXTENSIONS

        # Test non-markdown extensions
        assert ".txt" not in monitor.MARKDOWN_EXTENSIONS
        assert ".py" not in monitor.MARKDOWN_EXTENSIONS

    def test_should_ignore_path(self):
        """Test ignore pattern matching."""
        monitor = FileMonitor(ignore_patterns={".git", "node_modules"})

        assert monitor._should_ignore_path(Path(".git"))
        assert monitor._should_ignore_path(Path("node_modules"))
        assert monitor._should_ignore_path(Path("some_node_modules_path"))
        assert not monitor._should_ignore_path(Path("regular_file.md"))

    def test_scan_directory_files(self, tmp_path):
        """Test directory scanning for markdown files."""
        monitor = FileMonitor()

        # Create test structure
        (tmp_path / "test1.md").write_text("content")
        (tmp_path / "test2.txt").write_text("content")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "test3.markdown").write_text("content")

        # Create ignored directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        files = monitor._scan_directory_files(tmp_path)

        # Should find markdown files but not .txt or files in .git
        assert len(files) == 2
        paths = {f.name for f in files}
        assert "test1.md" in paths
        assert "test3.markdown" in paths
        assert "test2.txt" not in paths
        assert "config" not in paths

    def test_get_monitored_files(self, tmp_path):
        """Test getting list of monitored files."""
        monitor = FileMonitor()
        test_file = tmp_path / "test.md"
        test_file.write_text("content")

        monitor.add_path(test_file)
        monitored = monitor.get_monitored_files()

        assert test_file in monitored
        assert len(monitored) == 1


class TestFileMonitorIntegration:
    """Integration tests for file monitoring with actual file operations."""

    def test_file_monitoring_lifecycle(self, tmp_path):
        """Test complete file monitoring lifecycle."""
        monitor = FileMonitor(polling_interval=0.1)
        events = []

        def track_event(event):
            events.append(event)

        # Register callbacks
        monitor.register_callback(ChangeType.ADDED, track_event)
        monitor.register_callback(ChangeType.MODIFIED, track_event)
        monitor.register_callback(ChangeType.DELETED, track_event)

        # Add directory to monitoring
        monitor.add_path(tmp_path)

        # Start monitoring
        monitor.start_monitoring()

        try:
            # Create file
            test_file = tmp_path / "test.md"
            test_file.write_text("original content")
            time.sleep(0.2)  # Wait for detection

            # Modify file
            test_file.write_text("modified content")
            time.sleep(0.2)  # Wait for detection

            # Delete file
            test_file.unlink()
            time.sleep(0.2)  # Wait for detection

        finally:
            monitor.stop_monitoring()

        # Verify events
        assert len(events) >= 3  # At least ADDED, MODIFIED, DELETED

        event_types = [event.change_type for event in events]
        assert ChangeType.ADDED in event_types
        assert ChangeType.MODIFIED in event_types
        assert ChangeType.DELETED in event_types

    def test_monitoring_ignores_non_markdown(self, tmp_path):
        """Test that monitoring ignores non-markdown files."""
        monitor = FileMonitor(polling_interval=0.1)
        events = []

        def track_event(event):
            events.append(event)

        monitor.register_callback(ChangeType.ADDED, track_event)
        monitor.add_path(tmp_path)
        monitor.start_monitoring()

        try:
            # Create non-markdown files
            (tmp_path / "test.txt").write_text("content")
            (tmp_path / "test.py").write_text("print('hello')")
            time.sleep(0.2)

            # Create markdown file
            (tmp_path / "test.md").write_text("# Markdown")
            time.sleep(0.2)

        finally:
            monitor.stop_monitoring()

        # Should only detect markdown file
        assert len(events) == 1
        assert events[0].change_type == ChangeType.ADDED
        assert events[0].path.name == "test.md"

    def test_monitoring_start_stop(self):
        """Test monitoring start and stop functionality."""
        monitor = FileMonitor(polling_interval=0.1)

        # Initially not monitoring
        assert not monitor._monitoring
        assert monitor._monitor_thread is None

        # Start monitoring
        monitor.start_monitoring()
        assert monitor._monitoring
        assert monitor._monitor_thread is not None
        assert monitor._monitor_thread.is_alive()

        # Stop monitoring
        monitor.stop_monitoring()
        assert not monitor._monitoring

        # Thread should be stopped (or stopping)
        if monitor._monitor_thread:
            monitor._monitor_thread.join(timeout=1.0)
            assert not monitor._monitor_thread.is_alive()

    def test_callback_error_handling(self, tmp_path):
        """Test that callback errors don't crash monitoring."""
        monitor = FileMonitor(polling_interval=0.1)

        def failing_callback(event):
            raise RuntimeError("Callback error")

        def working_callback(event):
            working_callback.called = True

        working_callback.called = False

        monitor.register_callback(ChangeType.ADDED, failing_callback)
        monitor.register_callback(ChangeType.ADDED, working_callback)
        monitor.add_path(tmp_path)

        with patch("heimdall.monitoring.file_types.logger") as mock_logger:
            monitor.start_monitoring()

            try:
                # Create file to trigger callbacks
                test_file = tmp_path / "test.md"
                test_file.write_text("content")
                time.sleep(0.2)

            finally:
                monitor.stop_monitoring()

        # Working callback should still be called despite failing callback
        assert working_callback.called
        # Error should be logged
        mock_logger.error.assert_called()


@pytest.fixture
def tmp_path():
    """Create temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)
