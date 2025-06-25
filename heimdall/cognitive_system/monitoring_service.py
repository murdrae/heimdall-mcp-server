#!/usr/bin/env python3
"""
Host-based monitoring service for cognitive memory system.

This module provides a production-ready monitoring service that runs as a host process
with project-local PID files, automatically detecting file changes and
synchronizing memories. Designed for reliability, observability, and multi-project support.
"""

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

import psutil
from loguru import logger

from cognitive_memory.core.config import (
    SystemConfig,
    detect_container_environment,
    get_monitoring_config,
    get_project_paths,
)
from heimdall.monitoring.lightweight_monitor import (
    LightweightMonitor,
)


class MonitoringServiceError(Exception):
    """Base exception for monitoring service errors."""

    pass


class ServiceStatus:
    """Service status tracking and reporting."""

    def __init__(self) -> None:
        self.started_at: float | None = None
        self.pid: int | None = None
        self.is_running: bool = False
        self.error_count: int = 0
        self.last_error: str | None = None
        self.restart_count: int = 0
        self.files_monitored: int = 0
        self.sync_operations: int = 0
        self.last_sync_time: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert status to dictionary for JSON serialization."""
        return {
            "started_at": self.started_at,
            "pid": self.pid,
            "is_running": self.is_running,
            "uptime_seconds": time.time() - self.started_at
            if self.started_at
            else None,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "restart_count": self.restart_count,
            "files_monitored": self.files_monitored,
            "sync_operations": self.sync_operations,
            "last_sync_time": self.last_sync_time,
            "memory_usage_mb": self._get_memory_usage(),
            "cpu_percent": self._get_cpu_percent(),
        }

    def _get_memory_usage(self) -> float | None:
        """Get current memory usage in MB."""
        try:
            if self.pid:
                process = psutil.Process(self.pid)
                return float(process.memory_info().rss / 1024 / 1024)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return None

    def _get_cpu_percent(self) -> float | None:
        """Get current CPU usage percentage."""
        try:
            if self.pid:
                process = psutil.Process(self.pid)
                return float(process.cpu_percent())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return None


class MonitoringService:
    """
    Host-based monitoring service for cognitive memory system.

    Provides automatic file monitoring with project-local PID management,
    including daemon mode, health checks, error recovery, and production logging.
    Uses .heimdall/config.yaml for configuration instead of container environment variables.
    """

    # PID_FILE now determined per-project
    SOCKET_PATH = "/tmp/monitoring.sock"
    MAX_RESTART_ATTEMPTS = 5
    RESTART_BACKOFF_BASE = 1.0  # seconds
    RESTART_BACKOFF_MAX = 60.0  # seconds
    STATUS_FILE_NAME = "monitor_status.json"  # Status file for daemon-CLI communication

    def __init__(self, project_root: str | None = None):
        """
        Initialize monitoring service.

        Args:
            project_root: Optional project root directory, defaults to current working directory
        """
        # Get project paths and configuration
        self.project_paths = get_project_paths(
            Path(project_root) if project_root else None
        )
        self.monitoring_config = get_monitoring_config(self.project_paths.project_root)

        # Load full system config for cognitive parameters
        system_config = SystemConfig.from_env()
        self.config = system_config.cognitive
        self.status = ServiceStatus()
        self.lightweight_monitor: LightweightMonitor | None = None
        self._shutdown_requested = False
        self._restart_attempts = 0

        # Validate configuration
        self._validate_configuration()

        # Clean up any stale PID files
        self.project_paths.cleanup_stale_pid()

        # Detect container environment for health check behavior
        self._is_container = detect_container_environment()

        logger.info("MonitoringService initialized with configuration")

    @property
    def status_file(self) -> Path:
        """Get path to status file for daemon-CLI communication."""
        return self.project_paths.heimdall_dir / self.STATUS_FILE_NAME

    def _validate_configuration(self) -> None:
        """Validate service configuration and dependencies."""
        if not self.config.monitoring_enabled:
            raise MonitoringServiceError("Monitoring is disabled in configuration")

        # Check target path from centralized configuration
        target_path = self.monitoring_config["target_path"]
        target_path_obj = Path(target_path)
        if not target_path_obj.exists():
            raise MonitoringServiceError(f"Target path does not exist: {target_path}")

        if not target_path_obj.is_dir():
            raise MonitoringServiceError(
                f"Target path is not a directory: {target_path}"
            )

        # Check permissions
        if not os.access(target_path, os.R_OK):
            raise MonitoringServiceError(
                f"No read permission for target path: {target_path}"
            )

        logger.info(f"Configuration validated - monitoring target: {target_path}")

    def start(self, daemon_mode: bool = False) -> bool:
        """
        Start the monitoring service.

        Args:
            daemon_mode: Whether to run as background daemon process

        Returns:
            True if service started successfully, False otherwise
        """
        try:
            # Check if already running using project-local PID
            if self._is_service_running():
                logger.warning("Monitoring service is already running")
                return False

            logger.info("Starting lightweight monitoring service...")

            # Initialize lightweight monitoring
            self._initialize_monitoring()

            # Update status
            self.status.started_at = time.time()
            self.status.pid = os.getpid()
            self.status.is_running = True
            self.status.restart_count = self._restart_attempts

            # Write PID file and status
            self._write_pid_file()
            self._write_status_file()

            if daemon_mode:
                # Start lightweight monitor and run daemon loop
                if self.lightweight_monitor:
                    success = self.lightweight_monitor.start()
                    if success:
                        logger.info(
                            f"Lightweight monitoring service started in daemon mode (PID: {self.status.pid})"
                        )
                        self.lightweight_monitor.run_daemon_loop()
                    else:
                        logger.error(
                            "Failed to start lightweight monitor in daemon mode"
                        )
                        return False
                else:
                    logger.error("Lightweight monitor not initialized")
                    return False
            else:
                # Start lightweight monitor for non-daemon mode
                if self.lightweight_monitor:
                    success = self.lightweight_monitor.start()
                    if success:
                        logger.info(
                            f"Lightweight monitoring service started successfully (PID: {self.status.pid})"
                        )
                    else:
                        logger.error("Failed to start lightweight monitor")
                        return False
                else:
                    logger.error("Lightweight monitor not initialized")
                    return False

            return True

        except Exception as e:
            logger.error(f"Failed to start monitoring service: {e}")
            self.status.error_count += 1
            self.status.last_error = str(e)
            return False

    def stop(self) -> bool:
        """
        Stop the monitoring service gracefully.

        Returns:
            True if service stopped successfully, False otherwise
        """
        try:
            logger.info("Stopping monitoring service...")
            self._shutdown_requested = True

            # Stop lightweight monitoring
            if self.lightweight_monitor:
                self.lightweight_monitor.stop()
                logger.info("Lightweight monitoring stopped")

            # Update status
            self.status.is_running = False

            # Remove project-local PID file and status file
            self._remove_pid_file()
            self._remove_status_file()

            logger.info("Monitoring service stopped successfully")
            return True

        except Exception as e:
            logger.error(f"Error stopping monitoring service: {e}")
            self.status.error_count += 1
            self.status.last_error = str(e)
            return False

    def restart(self) -> bool:
        """
        Restart the monitoring service.

        Returns:
            True if service restarted successfully, False otherwise
        """
        logger.info("Restarting monitoring service...")

        # Stop current service
        if not self.stop():
            logger.error("Failed to stop service for restart")
            return False

        # Wait a moment for cleanup
        time.sleep(1.0)

        # Start service again
        self._restart_attempts += 1
        return self.start()

    def get_status(self) -> dict[str, Any]:
        """
        Get current service status.

        Returns:
            Dictionary containing service status information
        """
        # Try to read status from daemon's status file first
        daemon_status = self._read_status_file()
        if daemon_status and self._is_service_running():
            # Use daemon's actual status data
            return daemon_status

        # Fallback: If daemon is running but we don't have local status, get daemon PID info
        if self._is_service_running() and not self.status.is_running:
            try:
                with open(self.project_paths.pid_file) as f:
                    daemon_pid = int(f.read().strip())

                # Update status with daemon info
                self.status.pid = daemon_pid
                self.status.is_running = True

                # Try to get daemon start time from process
                try:
                    process = psutil.Process(daemon_pid)
                    self.status.started_at = process.create_time()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            except (ValueError, FileNotFoundError, PermissionError):
                pass

        # Update monitored files count from lightweight monitor
        if self.lightweight_monitor and self.lightweight_monitor.running:
            monitor_status = self.lightweight_monitor.get_status()
            self.status.files_monitored = monitor_status.get("files_monitored", 0)
            # Update sync operations from subprocess calls
            self.status.sync_operations = monitor_status.get("subprocess_calls", 0)
            # Update last sync time from last activity
            if monitor_status.get("last_activity"):
                self.status.last_sync_time = monitor_status["last_activity"]

        return self.status.to_dict()

    def health_check(self) -> dict[str, Any]:
        """
        Perform health check for container orchestration.

        Returns:
            Dictionary containing health check results
        """
        health: dict[str, Any] = {
            "status": "healthy",
            "checks": [],
            "timestamp": time.time(),
        }

        try:
            # Check if service is running - use consistent PID-based detection for all environments
            service_running = self._is_service_running()
            if not service_running:
                health["status"] = "unhealthy"
                health["checks"].append(
                    {
                        "name": "service_running",
                        "status": "fail",
                        "message": "Monitoring service is not running",
                    }
                )
            else:
                health["checks"].append(
                    {
                        "name": "service_running",
                        "status": "pass",
                        "message": "Monitoring service is running",
                    }
                )

            # Check project-local PID file
            if not self.project_paths.pid_file.exists():
                health["status"] = "unhealthy"
                health["checks"].append(
                    {
                        "name": "pid_file",
                        "status": "fail",
                        "message": "PID file not found",
                    }
                )
            else:
                health["checks"].append(
                    {"name": "pid_file", "status": "pass", "message": "PID file exists"}
                )

            # Check cognitive operations (subprocess delegation)
            if service_running:
                health["checks"].append(
                    {
                        "name": "cognitive_operations",
                        "status": "pass",
                        "message": "Cognitive operations available via subprocess delegation",
                    }
                )
            else:
                health["checks"].append(
                    {
                        "name": "cognitive_operations",
                        "status": "pass",
                        "message": "Cognitive operations inactive (service not running)",
                    }
                )

            # Check lightweight monitoring
            if (
                service_running
                and self.lightweight_monitor
                and self.lightweight_monitor.running
            ):
                health["checks"].append(
                    {
                        "name": "file_monitoring",
                        "status": "pass",
                        "message": "Lightweight file monitoring active",
                    }
                )
            elif service_running:
                health["status"] = "unhealthy"
                health["checks"].append(
                    {
                        "name": "file_monitoring",
                        "status": "fail",
                        "message": "Lightweight monitoring not active",
                    }
                )
            else:
                health["checks"].append(
                    {
                        "name": "file_monitoring",
                        "status": "pass",
                        "message": "File monitoring inactive (service not running)",
                    }
                )

            # Check resource usage (lowered threshold for lightweight monitor)
            memory_usage = self.status._get_memory_usage()
            if (
                memory_usage and memory_usage > 100
            ):  # 100 MB threshold for lightweight monitor
                health["status"] = "warning"
                health["checks"].append(
                    {
                        "name": "memory_usage",
                        "status": "warn",
                        "message": f"High memory usage for lightweight monitor: {memory_usage:.1f} MB",
                    }
                )
            else:
                health["checks"].append(
                    {
                        "name": "memory_usage",
                        "status": "pass",
                        "message": f"Memory usage: {memory_usage:.1f} MB"
                        if memory_usage
                        else "Memory usage: unknown",
                    }
                )

        except Exception as e:
            health["status"] = "unhealthy"
            health["checks"].append(
                {
                    "name": "health_check_error",
                    "status": "fail",
                    "message": f"Health check failed: {e}",
                }
            )

        return health

    def _initialize_monitoring(self) -> None:
        """Initialize lightweight monitoring with subprocess delegation."""
        try:
            logger.info(
                "Initializing lightweight monitoring with subprocess delegation..."
            )

            # Get target path from centralized configuration
            target_path = Path(self.monitoring_config["target_path"])

            # Create lock file path
            lock_file = self.project_paths.heimdall_dir / "monitor.lock"

            # Create lightweight monitor instance
            self.lightweight_monitor = LightweightMonitor(
                project_root=self.project_paths.project_root,
                target_path=target_path,
                lock_file=lock_file,
            )

            logger.info(f"Lightweight monitoring initialized for path: {target_path}")

        except Exception as e:
            raise MonitoringServiceError(
                f"Failed to initialize lightweight monitoring: {e}"
            ) from e

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum: int, frame: Any) -> None:
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self._shutdown_requested = True
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    def _run_daemon_loop(self) -> None:
        """Run the main daemon loop (delegated to lightweight monitor)."""
        logger.info("Daemon loop delegated to lightweight monitor...")
        # The lightweight monitor handles its own daemon loop
        # This method is kept for compatibility but actual loop is in lightweight_monitor.run_daemon_loop()

    def _should_restart(self) -> bool:
        """Determine if service should attempt restart."""
        return (
            self.status.error_count >= 3
            and self._restart_attempts < self.MAX_RESTART_ATTEMPTS
            and time.time() - (self.status.started_at or 0)
            > 60  # Don't restart too quickly
        )

    def _attempt_restart(self) -> bool:
        """Attempt to restart the service with exponential backoff."""
        if self._restart_attempts >= self.MAX_RESTART_ATTEMPTS:
            logger.error("Maximum restart attempts reached")
            return False

        # Calculate backoff delay
        delay = min(
            self.RESTART_BACKOFF_BASE * (2**self._restart_attempts),
            self.RESTART_BACKOFF_MAX,
        )

        logger.info(
            f"Restarting in {delay} seconds (attempt {self._restart_attempts + 1})"
        )
        time.sleep(delay)

        return self.restart()

    def _is_service_running(self) -> bool:
        """Check if monitoring service is already running using project-local PID."""
        pid_file = self.project_paths.pid_file
        if not pid_file.exists():
            return False

        try:
            with open(pid_file) as f:
                pid = int(f.read().strip())

            # Check if process exists
            return bool(psutil.pid_exists(pid))

        except (ValueError, FileNotFoundError, PermissionError):
            return False

    def _write_pid_file(self) -> None:
        """Write project-local PID file for service tracking."""
        try:
            with open(self.project_paths.pid_file, "w") as f:
                f.write(str(os.getpid()))
            logger.debug(f"PID file written: {self.project_paths.pid_file}")
        except Exception as e:
            logger.warning(f"Failed to write PID file: {e}")

    def _remove_pid_file(self) -> None:
        """Remove project-local PID file on service shutdown."""
        try:
            self.project_paths.pid_file.unlink(missing_ok=True)
            logger.debug(f"PID file removed: {self.project_paths.pid_file}")
        except Exception as e:
            logger.warning(f"Failed to remove PID file: {e}")

    def _write_status_file(self) -> None:
        """Write current status to shared JSON file for CLI communication."""
        try:
            status_data = self.status.to_dict()
            # Add files monitored count from lightweight monitor if available
            if self.lightweight_monitor and self.lightweight_monitor.running:
                monitor_status = self.lightweight_monitor.get_status()
                status_data["files_monitored"] = monitor_status.get(
                    "files_monitored", 0
                )
                status_data["subprocess_calls"] = monitor_status.get(
                    "subprocess_calls", 0
                )
                status_data["subprocess_errors"] = monitor_status.get(
                    "subprocess_errors", 0
                )

            with open(self.status_file, "w") as f:
                json.dump(status_data, f, indent=2)
            logger.debug(f"Status file updated: {self.status_file}")
        except Exception as e:
            logger.warning(f"Failed to write status file: {e}")

    def _read_status_file(self) -> dict[str, Any] | None:
        """Read status from shared JSON file."""
        try:
            if not self.status_file.exists():
                return None

            with open(self.status_file) as f:
                data = json.load(f)
                return data if isinstance(data, dict) else None
        except Exception as e:
            logger.warning(f"Failed to read status file: {e}")
            return None

    def _remove_status_file(self) -> None:
        """Remove status file on service shutdown."""
        try:
            self.status_file.unlink(missing_ok=True)
            logger.debug(f"Status file removed: {self.status_file}")
        except Exception as e:
            logger.warning(f"Failed to remove status file: {e}")

    # Daemon forking logic removed - lightweight monitor handles process management


def main() -> int:
    """Main entry point for monitoring service CLI."""
    parser = argparse.ArgumentParser(
        description="Host-based monitoring service for cognitive memory system"
    )
    parser.add_argument("--start", action="store_true", help="Start monitoring service")
    parser.add_argument("--stop", action="store_true", help="Stop monitoring service")
    parser.add_argument(
        "--restart", action="store_true", help="Restart monitoring service"
    )
    parser.add_argument("--status", action="store_true", help="Show service status")
    parser.add_argument("--health", action="store_true", help="Perform health check")
    parser.add_argument("--daemon", action="store_true", help="Run in daemon mode")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument(
        "--project-root",
        type=str,
        help="Project root directory (defaults to current directory)",
    )

    args = parser.parse_args()

    try:
        service = MonitoringService(project_root=args.project_root)

        if args.start:
            success = service.start(daemon_mode=args.daemon)
            return 0 if success else 1

        elif args.stop:
            success = service.stop()
            return 0 if success else 1

        elif args.restart:
            success = service.restart()
            return 0 if success else 1

        elif args.status:
            status = service.get_status()
            if args.json:
                print(json.dumps(status, indent=2))
            else:
                print(
                    f"Service Status: {'Running' if status['is_running'] else 'Stopped'}"
                )
                if status["pid"]:
                    print(f"PID: {status['pid']}")
                if status["uptime_seconds"]:
                    print(f"Uptime: {status['uptime_seconds']:.1f} seconds")
                print(f"Files Monitored: {status['files_monitored']}")
                print(f"Sync Operations: {status['sync_operations']}")
                if status["error_count"] > 0:
                    print(f"Errors: {status['error_count']}")
            return 0

        elif args.health:
            health = service.health_check()
            if args.json:
                print(json.dumps(health, indent=2))
            else:
                print(f"Health Status: {health['status']}")
                for check in health["checks"]:
                    status_icon = (
                        "✅"
                        if check["status"] == "pass"
                        else "⚠️"
                        if check["status"] == "warn"
                        else "❌"
                    )
                    print(f"  {status_icon} {check['name']}: {check['message']}")
            return 0 if health["status"] in ["healthy", "warning"] else 1

        else:
            parser.print_help()
            return 1

    except MonitoringServiceError as e:
        print(f"Service Error: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
