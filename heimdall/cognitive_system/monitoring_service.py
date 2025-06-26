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
            # Resource usage removed - now handled by daemon status
        }


class MonitoringService:
    """
    Host-based monitoring service for cognitive memory system.

    Provides automatic file monitoring with project-local PID management,
    running as a background daemon process with health checks, error recovery,
    and production logging. Uses .heimdall/config.yaml for configuration instead
    of container environment variables.
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

    def start(self) -> bool:
        """
        Start the monitoring service in daemon mode.

        The service always runs as a background daemon process using subprocess delegation.

        Returns:
            True if service started successfully, False otherwise
        """
        try:
            # Check if already running using project-local PID
            if self._is_service_running():
                logger.warning("Monitoring service is already running")
                return False

            logger.info("Starting lightweight monitoring service...")

            # Update status
            self.status.started_at = time.time()
            self.status.pid = os.getpid()
            self.status.is_running = True
            self.status.restart_count = self._restart_attempts

            # Write PID file and status
            self._write_pid_file()

            # Start lightweight monitor as subprocess to avoid heavy memory footprint
            success = self._start_lightweight_subprocess()
            if success:
                logger.info(
                    "Lightweight monitoring service started as subprocess (daemon mode)"
                )
                # Main process can exit - subprocess runs as daemon
                return success
            else:
                logger.error(
                    "Failed to start lightweight monitor subprocess in daemon mode"
                )
                return False

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

            # Stop subprocess
            if self._is_service_running():
                success = self._stop_subprocess()
                if not success:
                    logger.warning("Failed to stop subprocess gracefully")
                    return False

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
        # Always read daemon PID from PID file for accurate status
        if self._is_service_running():
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
                # If we can't read PID file but service appears running, mark as not running
                self.status.is_running = False
                self.status.pid = None

        # Try to read status from daemon's status file
        daemon_status = self._read_status_file()
        if daemon_status and self.status.is_running:
            # Use daemon's actual status data but ensure PID is from daemon
            daemon_status["pid"] = self.status.pid

            # If using new structured format, merge with service info
            if "service" in daemon_status:
                # Add service-level management info to structured status
                daemon_status["service_management"] = {
                    "restart_count": self.status.restart_count,
                    "service_errors": self.status.error_count,
                    "service_last_error": self.status.last_error,
                }

            return daemon_status

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
            if service_running:
                health["checks"].append(
                    {
                        "name": "file_monitoring",
                        "status": "pass",
                        "message": "Lightweight file monitoring active",
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

            # Enhanced health checks using structured status data
            daemon_status = self._read_status_file()
            if daemon_status and service_running:
                # Check processing queue backlog
                if "processing" in daemon_status:
                    queue_size = daemon_status["processing"]["event_queue_size"]
                    if queue_size > 50:
                        health["status"] = "warning"
                        health["checks"].append(
                            {
                                "name": "processing_queue",
                                "status": "warn",
                                "message": f"Large processing queue: {queue_size} items",
                            }
                        )
                    else:
                        health["checks"].append(
                            {
                                "name": "processing_queue",
                                "status": "pass",
                                "message": f"Processing queue: {queue_size} items",
                            }
                        )

                # Check subprocess performance
                if "subprocess" in daemon_status:
                    subproc = daemon_status["subprocess"]
                    if subproc["total_calls"] > 0:
                        failure_rate = (
                            subproc["failed_calls"] / subproc["total_calls"]
                        ) * 100
                        if failure_rate > 20:
                            health["status"] = "warning"
                            health["checks"].append(
                                {
                                    "name": "subprocess_performance",
                                    "status": "warn",
                                    "message": f"High subprocess failure rate: {failure_rate:.1f}%",
                                }
                            )
                        else:
                            health["checks"].append(
                                {
                                    "name": "subprocess_performance",
                                    "status": "pass",
                                    "message": f"Subprocess success rate: {100 - failure_rate:.1f}%",
                                }
                            )

                # Check resource usage with structured data
                if "resources" in daemon_status:
                    memory_usage = daemon_status["resources"]["memory_usage_mb"]
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
                else:
                    # Fallback when structured data not available
                    health["checks"].append(
                        {
                            "name": "memory_usage",
                            "status": "pass",
                            "message": "Memory usage: not available (daemon status missing structured data)",
                        }
                    )
            else:
                # Fallback when daemon status not available
                health["checks"].append(
                    {
                        "name": "memory_usage",
                        "status": "pass",
                        "message": "Memory usage: not available (daemon not running)",
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

    def _start_lightweight_subprocess(self) -> bool:
        """
        Start lightweight monitoring as subprocess to avoid heavy memory footprint.

        Returns:
            True if subprocess started successfully, False otherwise
        """
        try:
            import subprocess

            # Get target path from centralized configuration
            target_path = Path(self.monitoring_config["target_path"])

            # Create lock file path
            lock_file = self.project_paths.heimdall_dir / "monitor.lock"

            # Build subprocess command - use top-level entry point to avoid package imports
            cmd = [
                "heimdall-lightweight-monitor",
                "--project-root",
                str(self.project_paths.project_root),
                "--target-path",
                str(target_path),
                "--lock-file",
                str(lock_file),
                "--log-level",
                "INFO",
            ]

            logger.info(f"Starting lightweight monitoring subprocess: {' '.join(cmd)}")

            # Start subprocess with proper detaching
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                start_new_session=True,  # Detach from parent process
                cwd=self.project_paths.project_root,
            )

            # Give subprocess a moment to start and acquire lock
            time.sleep(2.0)

            # Check if subprocess is still running
            if process.poll() is None:
                # Subprocess is running, update PID file with subprocess PID
                subprocess_pid = process.pid
                self.status.pid = subprocess_pid

                # Write PID file with subprocess PID
                try:
                    with open(self.project_paths.pid_file, "w") as f:
                        f.write(str(subprocess_pid))
                    logger.info(
                        f"Updated PID file with subprocess PID: {subprocess_pid}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to update PID file: {e}")

                logger.info(
                    f"Lightweight monitoring subprocess started successfully (PID: {subprocess_pid})"
                )
                return True
            else:
                # Subprocess failed to start
                try:
                    stdout, stderr = process.communicate(timeout=1.0)
                    logger.error(
                        f"Subprocess failed to start. Exit code: {process.returncode}"
                    )
                    if stdout:
                        logger.error(f"Subprocess stdout: {stdout.decode()}")
                    if stderr:
                        logger.error(f"Subprocess stderr: {stderr.decode()}")
                except subprocess.TimeoutExpired:
                    process.kill()
                    logger.error("Subprocess startup check timed out")

                return False

        except Exception as e:
            logger.error(f"Error starting lightweight monitoring subprocess: {e}")
            return False

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum: int, frame: Any) -> None:
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self._shutdown_requested = True
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    def _stop_subprocess(self) -> bool:
        """
        Stop the lightweight monitoring subprocess gracefully.

        Returns:
            True if subprocess stopped successfully, False otherwise
        """
        try:
            # Get subprocess PID from PID file
            if not self.project_paths.pid_file.exists():
                logger.warning("PID file not found - subprocess may already be stopped")
                return True

            with open(self.project_paths.pid_file) as f:
                subprocess_pid = int(f.read().strip())

            logger.info(f"Stopping subprocess with PID: {subprocess_pid}")

            # Check if process exists
            if not psutil.pid_exists(subprocess_pid):
                logger.info("Subprocess already stopped")
                return True

            # Send SIGTERM for graceful shutdown
            try:
                process = psutil.Process(subprocess_pid)
                process.terminate()
                logger.info("Sent SIGTERM to subprocess")

                # Wait for graceful shutdown (up to 10 seconds)
                try:
                    process.wait(timeout=10.0)
                    logger.info("Subprocess stopped gracefully")
                    return True
                except psutil.TimeoutExpired:
                    logger.warning(
                        "Subprocess did not stop gracefully, forcing termination"
                    )
                    process.kill()
                    process.wait(timeout=5.0)
                    logger.info("Subprocess force-killed")
                    return True

            except psutil.NoSuchProcess:
                logger.info("Subprocess already stopped")
                return True
            except psutil.AccessDenied:
                logger.error("Access denied when trying to stop subprocess")
                return False

        except (ValueError, FileNotFoundError, PermissionError) as e:
            logger.error(f"Error reading PID file: {e}")
            return False
        except Exception as e:
            logger.error(f"Error stopping subprocess: {e}")
            return False

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
            success = service.start()
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
                # Check if using new structured format
                if "service" in status:
                    # New structured format
                    svc = status["service"]
                    mon = status["monitoring"]
                    proc = status["processing"]
                    subproc = status["subprocess"]
                    res = status["resources"]

                    print(
                        f"Service Status: {'Running' if svc['is_running'] else 'Stopped'}"
                    )
                    if svc["pid"]:
                        print(f"PID: {svc['pid']}")
                    if svc["uptime_seconds"]:
                        print(f"Uptime: {svc['uptime_seconds']:.1f} seconds")

                    print("\nFile Monitoring:")
                    print(f"  Files Monitored: {mon['files_monitored']}")
                    print(f"  Target Paths: {', '.join(mon['target_paths'])}")

                    print("\nProcessing Queue:")
                    print(f"  Queue Size: {proc['event_queue_size']}")
                    print(f"  Files Processed: {proc['files_processed']}")
                    if proc["current_processing"]["file_path"]:
                        current = proc["current_processing"]
                        processing_time = (
                            time.time() - current["started_at"]
                            if current["started_at"]
                            else 0
                        )
                        print(
                            f"  Currently Processing: {current['file_path']} ({current['change_type']}) - {processing_time:.1f}s"
                        )
                    else:
                        print("  Currently Processing: None")

                    print("\nSubprocess Performance:")
                    print(f"  Total Calls: {subproc['total_calls']}")
                    print(f"  Successful: {subproc['successful_calls']}")
                    print(f"  Failed: {subproc['failed_calls']}")
                    if subproc["total_calls"] > 0:
                        success_rate = (
                            subproc["successful_calls"] / subproc["total_calls"]
                        ) * 100
                        print(f"  Success Rate: {success_rate:.1f}%")
                    if subproc["retry_attempts"] > 0:
                        print(f"  Retries: {subproc['retry_attempts']}")
                    if subproc["timeout_count"] > 0:
                        print(f"  Timeouts: {subproc['timeout_count']}")
                    if subproc["average_execution_time"]:
                        print(
                            f"  Avg Execution Time: {subproc['average_execution_time']:.2f}s"
                        )
                    if subproc["last_error"]:
                        print(f"  Last Error: {subproc['last_error']}")

                    print("\nSystem Resources:")
                    if res["memory_usage_mb"]:
                        print(f"  Memory Usage: {res['memory_usage_mb']:.1f} MB")
                    if res["cpu_percent"]:
                        print(f"  CPU Usage: {res['cpu_percent']:.1f}%")

                    # Show warnings for queue backlog
                    if proc["event_queue_size"] > 30:
                        print(
                            f"\n⚠️  Warning: Large processing queue ({proc['event_queue_size']} items)"
                        )
                    if subproc["failed_calls"] > 0 and subproc["total_calls"] > 0:
                        failure_rate = (
                            subproc["failed_calls"] / subproc["total_calls"]
                        ) * 100
                        if failure_rate > 10:
                            print(
                                f"⚠️  Warning: High failure rate ({failure_rate:.1f}%)"
                            )

                else:
                    # Legacy format fallback
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
