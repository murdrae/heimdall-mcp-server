"""
Integration tests for file monitoring system.

Tests the file monitoring system in realistic scenarios with
configuration integration and error handling.
"""

import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from cognitive_memory.core.config import CognitiveConfig, SystemConfig
from heimdall.monitoring.file_types import (
    ChangeType,
    FileMonitor,
    FileState,
)


class TestFileMonitoringConfiguration:
    """Test file monitoring integration with configuration system."""

    def test_monitor_with_default_config(self):
        """Test creating monitor with default configuration."""
        config = CognitiveConfig()

        monitor = FileMonitor(
            polling_interval=config.monitoring_interval_seconds,
            ignore_patterns=config.monitoring_ignore_patterns,
        )

        assert monitor.polling_interval == 5.0
        assert ".git" in monitor.ignore_patterns
        assert "node_modules" in monitor.ignore_patterns
        assert "__pycache__" in monitor.ignore_patterns

    def test_monitor_with_env_config(self):
        """Test creating monitor with environment configuration."""
        with patch.dict(
            "os.environ",
            {
                "MONITORING_INTERVAL_SECONDS": "2.5",
                "MONITORING_IGNORE_PATTERNS": ".git,custom_ignore,temp",
            },
        ):
            config = CognitiveConfig.from_env()

            monitor = FileMonitor(
                polling_interval=config.monitoring_interval_seconds,
                ignore_patterns=config.monitoring_ignore_patterns,
            )

            assert monitor.polling_interval == 2.5
            assert monitor.ignore_patterns == {".git", "custom_ignore", "temp"}

    def test_monitor_disabled_via_config(self):
        """Test that monitoring can be disabled via configuration."""
        with patch.dict("os.environ", {"MONITORING_ENABLED": "false"}):
            config = CognitiveConfig.from_env()

            assert not config.monitoring_enabled

    def test_config_validation_monitoring_params(self):
        """Test configuration validation for monitoring parameters."""
        # Valid config should pass
        config = SystemConfig.from_env()
        assert config.validate()

        # Invalid interval should fail
        config.cognitive.monitoring_interval_seconds = -1.0
        assert not config.validate()

        # Reset and test invalid batch size
        config.cognitive.monitoring_interval_seconds = 5.0
        config.cognitive.monitoring_batch_size = 0
        assert not config.validate()


class TestFileMonitoringRealWorldScenarios:
    """Test file monitoring in realistic usage scenarios."""

    def test_monitoring_project_directory(self, tmp_path):
        """Test monitoring a typical project directory structure."""
        monitor = FileMonitor(polling_interval=0.1)
        events = []

        def track_events(event):
            events.append(event)

        # Register for all event types
        for change_type in ChangeType:
            monitor.register_callback(change_type, track_events)

        # Create project structure
        (tmp_path / "README.md").write_text("# Project")
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "api.md").write_text("# API")
        (docs_dir / "guide.md").write_text("# Guide")

        # Create ignored directories
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "package.json").write_text("{}")

        # Start monitoring
        monitor.add_path(tmp_path)
        monitor.start_monitoring()

        try:
            # Simulate project activity
            time.sleep(0.2)  # Initial scan

            # Add new documentation
            (docs_dir / "new_feature.md").write_text("# New Feature")
            time.sleep(0.2)

            # Update existing file
            (tmp_path / "README.md").write_text("# Updated Project\n\nNew content")
            time.sleep(0.2)

            # Remove old documentation
            (docs_dir / "guide.md").unlink()
            time.sleep(0.2)

        finally:
            monitor.stop_monitoring()

        # Verify correct events were detected
        assert len(events) >= 3  # At least added, modified, deleted

        # Check that git and node_modules files were ignored
        event_paths = {event.path.name for event in events}
        assert "config" not in event_paths
        assert "package.json" not in event_paths

        # Check that markdown files were detected
        assert any("new_feature.md" in str(event.path) for event in events)
        assert any("README.md" in str(event.path) for event in events)

    def test_monitoring_large_directory_structure(self, tmp_path):
        """Test monitoring with many files and subdirectories."""
        monitor = FileMonitor(polling_interval=0.1)
        events = []

        def count_events(event):
            events.append(event)

        monitor.register_callback(ChangeType.ADDED, count_events)

        # Create large directory structure
        for i in range(10):
            subdir = tmp_path / f"section_{i}"
            subdir.mkdir()
            for j in range(5):
                (subdir / f"doc_{j}.md").write_text(f"# Document {i}-{j}")
                (subdir / f"code_{j}.py").write_text(f"# Python file {i}-{j}")

        monitor.add_path(tmp_path)

        # Monitor should handle large number of files efficiently
        start_time = time.time()
        monitor.start_monitoring()

        try:
            # Add a few more files to trigger events
            for k in range(3):
                (tmp_path / f"new_doc_{k}.md").write_text(f"# New doc {k}")

            time.sleep(0.3)  # Allow detection

        finally:
            monitor.stop_monitoring()

        end_time = time.time()

        # Should detect new files efficiently
        assert len(events) == 3
        assert all(event.change_type == ChangeType.ADDED for event in events)

        # Should complete in reasonable time (adjust threshold as needed)
        assert (end_time - start_time) < 5.0

    def test_concurrent_file_modifications(self, tmp_path):
        """Test monitoring with rapid file changes."""
        monitor = FileMonitor(polling_interval=0.05)  # Very fast polling
        events = []
        event_lock = threading.Lock()

        def thread_safe_track(event):
            with event_lock:
                events.append(event)

        monitor.register_callback(ChangeType.MODIFIED, thread_safe_track)

        test_file = tmp_path / "rapid_changes.md"
        test_file.write_text("initial content")

        monitor.add_path(test_file)
        monitor.start_monitoring()

        try:
            # Rapid modifications
            for i in range(5):
                test_file.write_text(f"content version {i}")
                time.sleep(0.02)  # Faster than polling interval

            time.sleep(0.2)  # Allow final detection

        finally:
            monitor.stop_monitoring()

        # Should detect at least some modifications
        # (May not catch all due to polling interval)
        assert len(events) >= 1
        assert all(event.change_type == ChangeType.MODIFIED for event in events)

    def test_monitoring_with_permission_errors(self, tmp_path):
        """Test monitoring behavior with permission denied scenarios."""
        monitor = FileMonitor(polling_interval=0.1)
        events = []

        def track_events(event):
            events.append(event)

        monitor.register_callback(ChangeType.ADDED, track_events)

        # Create a file
        test_file = tmp_path / "test.md"
        test_file.write_text("initial content")

        with patch("heimdall.monitoring.file_types.logger") as mock_logger:
            monitor.add_path(tmp_path)

            # Simulate permission error during file state creation
            original_from_path = FileState.from_path

            def failing_from_path(path):
                if "restricted" in str(path):
                    raise PermissionError("Access denied")
                return original_from_path(path)

            with patch.object(FileState, "from_path", side_effect=failing_from_path):
                monitor.start_monitoring()

                try:
                    # Create file that will trigger permission error
                    restricted_file = tmp_path / "restricted.md"
                    restricted_file.write_text("restricted content")
                    time.sleep(0.2)

                finally:
                    monitor.stop_monitoring()

        # Should log warnings about permission errors
        mock_logger.warning.assert_called()

        # Should still handle the scenario gracefully
        assert True  # Test passes if no exception is raised


class TestFileMonitoringErrorRecovery:
    """Test file monitoring error handling and recovery."""

    def test_monitor_thread_error_recovery(self, tmp_path):
        """Test that monitor recovers from thread errors."""
        monitor = FileMonitor(polling_interval=0.1)
        events = []

        def track_events(event):
            events.append(event)

        monitor.register_callback(ChangeType.ADDED, track_events)
        monitor.add_path(tmp_path)

        # Patch _poll_changes to raise an exception occasionally
        original_poll = monitor._poll_changes
        call_count = 0

        def failing_poll():
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Fail on second call
                raise RuntimeError("Simulated polling error")
            return original_poll()

        with patch.object(monitor, "_poll_changes", side_effect=failing_poll):
            with patch("heimdall.monitoring.file_types.logger") as mock_logger:
                monitor.start_monitoring()

                try:
                    # Create file after error should still be detected
                    time.sleep(0.15)  # Allow error to occur
                    (tmp_path / "test.md").write_text("content")
                    time.sleep(0.25)  # Allow recovery and detection

                finally:
                    monitor.stop_monitoring()

        # Should log the error
        mock_logger.error.assert_called()

        # Should still detect files after recovery
        assert len(events) >= 1

    def test_graceful_shutdown_with_active_monitoring(self, tmp_path):
        """Test graceful shutdown during active monitoring."""
        monitor = FileMonitor(polling_interval=0.1)
        monitor.add_path(tmp_path)
        monitor.start_monitoring()

        # Ensure monitoring is active
        assert monitor._monitoring
        assert monitor._monitor_thread is not None
        assert monitor._monitor_thread.is_alive()

        # Stop should complete cleanly
        start_time = time.time()
        monitor.stop_monitoring()
        stop_time = time.time()

        # Should stop quickly
        assert (stop_time - start_time) < 2.0
        assert not monitor._monitoring

        # Thread should be stopped
        if monitor._monitor_thread:
            assert not monitor._monitor_thread.is_alive()

    def test_multiple_start_stop_cycles(self, tmp_path):
        """Test multiple start/stop cycles."""
        monitor = FileMonitor(polling_interval=0.1)
        monitor.add_path(tmp_path)

        for cycle in range(3):
            # Start monitoring
            monitor.start_monitoring()
            assert monitor._monitoring

            # Create file
            test_file = tmp_path / f"test_{cycle}.md"
            test_file.write_text(f"content {cycle}")
            time.sleep(0.15)

            # Stop monitoring
            monitor.stop_monitoring()
            assert not monitor._monitoring

            # Clean up for next cycle
            if test_file.exists():
                test_file.unlink()


@pytest.fixture
def tmp_path():
    """Create temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)
