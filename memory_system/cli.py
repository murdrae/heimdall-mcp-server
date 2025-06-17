#!/usr/bin/env python3
"""
Unified CLI for the cognitive memory system with embedded service management.

This module provides a comprehensive command-line interface that handles:
- Qdrant vector database management
- Interface server management (HTTP, MCP)
- Interactive cognitive memory shell
- Health checking and system verification
"""

import json
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from cognitive_memory.main import (
    InitializationError,
    graceful_shutdown,
    initialize_system,
    initialize_with_config,
)

from .health_checker import HealthChecker, HealthCheckResults, HealthResult
from .interactive_shell import InteractiveShell
from .service_manager import QdrantManager, ServiceStatus

# Initialize rich console for enhanced output
console = Console()

# Main CLI app
app = typer.Typer(
    name="memory_system",
    help="🧠 Cognitive Memory System - Unified CLI",
    add_completion=False,
)

# Service management commands
qdrant_app = typer.Typer(help="Qdrant vector database management")
app.add_typer(qdrant_app, name="qdrant")

# Server interface commands
serve_app = typer.Typer(help="Start interface servers")
app.add_typer(serve_app, name="serve")


@qdrant_app.command("start")  # type: ignore[misc]
def qdrant_start(
    port: int = typer.Option(6333, help="Port for Qdrant service"),
    data_dir: str | None = typer.Option(None, help="Data directory path"),
    detach: bool = typer.Option(True, help="Run in background"),
    force_local: bool = typer.Option(
        False, help="Force local binary instead of Docker"
    ),
    wait_timeout: int = typer.Option(30, help="Seconds to wait for startup"),
) -> None:
    """Start Qdrant vector database service."""
    console.print("🚀 Starting Qdrant vector database...", style="bold blue")

    manager = QdrantManager()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Starting Qdrant service...", total=None)

        try:
            success = manager.start(
                port=port,
                data_dir=data_dir,
                detach=detach,
                force_local=force_local,
                wait_timeout=wait_timeout,
            )

            if success:
                progress.update(task, description="✅ Qdrant started successfully")
                console.print(
                    f"🎉 Qdrant is running on port {port}", style="bold green"
                )

                # Show connection info
                info_table = Table(title="Connection Information")
                info_table.add_column("Property", style="cyan")
                info_table.add_column("Value", style="white")
                info_table.add_row("URL", f"http://localhost:{port}")
                info_table.add_row("Status", "✅ Running")
                info_table.add_row(
                    "Mode", "Docker" if not force_local else "Local Binary"
                )
                console.print(info_table)
                return  # Explicitly exit on success

            else:
                progress.update(task, description="❌ Failed to start Qdrant")
                console.print("❌ Failed to start Qdrant service", style="bold red")
                raise typer.Exit(1) from None

        except Exception as e:
            progress.update(task, description=f"❌ Error: {str(e)}")
            console.print(f"❌ Error starting Qdrant: {e}", style="bold red")
            raise typer.Exit(1) from e


@qdrant_app.command("stop")  # type: ignore[misc]
def qdrant_stop() -> None:
    """Stop Qdrant vector database service."""
    console.print("🛑 Stopping Qdrant vector database...", style="bold yellow")

    manager = QdrantManager()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Stopping Qdrant service...", total=None)

        try:
            success = manager.stop()

            if success:
                progress.update(task, description="✅ Qdrant stopped successfully")
                console.print("✅ Qdrant service stopped", style="bold green")
            else:
                progress.update(task, description="⚠️ Qdrant was not running")
                console.print("⚠️ Qdrant service was not running", style="bold yellow")

        except Exception as e:
            progress.update(task, description=f"❌ Error: {str(e)}")
            console.print(f"❌ Error stopping Qdrant: {e}", style="bold red")
            raise typer.Exit(1) from e


@qdrant_app.command("status")  # type: ignore[misc]
def qdrant_status(
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """Show Qdrant service status."""
    manager = QdrantManager()
    status = manager.get_status()

    if json_output:
        status_data = {
            "status": status.status.value,
            "port": status.port,
            "pid": status.pid,
            "container_id": status.container_id,
            "uptime_seconds": status.uptime_seconds,
            "health_status": status.health_status,
            "error": status.error,
        }
        console.print(json.dumps(status_data, indent=2))
        return

    # Rich formatted output
    if status.status == ServiceStatus.RUNNING:
        console.print("🟢 Qdrant is running", style="bold green")
    elif status.status == ServiceStatus.STOPPED:
        console.print("🔴 Qdrant is stopped", style="bold red")
    else:
        console.print("🟡 Qdrant status unknown", style="bold yellow")

    # Status table
    status_table = Table(title="Qdrant Service Status")
    status_table.add_column("Property", style="cyan")
    status_table.add_column("Value", style="white")

    status_table.add_row("Status", status.status.value)
    status_table.add_row("Port", str(status.port) if status.port else "N/A")
    status_table.add_row("PID", str(status.pid) if status.pid else "N/A")
    status_table.add_row("Container ID", status.container_id or "N/A")
    status_table.add_row(
        "Uptime", f"{status.uptime_seconds}s" if status.uptime_seconds else "N/A"
    )
    status_table.add_row("Health", status.health_status or "Unknown")

    if status.error:
        status_table.add_row("Error", status.error)

    console.print(status_table)


@qdrant_app.command("logs")  # type: ignore[misc]
def qdrant_logs(
    lines: int = typer.Option(50, help="Number of log lines to show"),
    follow: bool = typer.Option(False, "-f", help="Follow log output"),
) -> None:
    """Show Qdrant service logs."""
    manager = QdrantManager()

    try:
        logs = manager.get_logs(lines=lines, follow=follow)

        if follow:
            console.print(
                "📄 Following Qdrant logs (Ctrl+C to stop)...", style="bold blue"
            )
            console.print("-" * 60)

            try:
                for log_line in logs:
                    console.print(log_line.rstrip())
            except KeyboardInterrupt:
                console.print("\n⏹️ Stopped following logs", style="bold yellow")

        else:
            console.print(f"📄 Last {lines} lines from Qdrant logs:", style="bold blue")
            console.print("-" * 60)

            for log_line in logs:
                console.print(log_line.rstrip())

    except Exception as e:
        console.print(f"❌ Error retrieving logs: {e}", style="bold red")
        raise typer.Exit(1) from e


@serve_app.command("http")  # type: ignore[misc]
def serve_http(
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to listen on"),
    reload: bool = typer.Option(False, help="Enable auto-reload for development"),
    config: str | None = typer.Option(None, help="Path to configuration file"),
) -> None:
    """Start HTTP API server."""
    console.print(f"🌐 Starting HTTP API server on {host}:{port}...", style="bold blue")

    try:
        # Import here to avoid circular dependencies
        from interfaces.http_api import run_server

        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Start HTTP server
        run_server(
            cognitive_system=cognitive_system,
            host=host,
            port=port,
            reload=reload,
        )

    except ImportError as e:
        console.print("❌ HTTP API interface not implemented yet", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error starting HTTP server: {e}", style="bold red")
        raise typer.Exit(1) from e


@serve_app.command("mcp")  # type: ignore[misc]
def serve_mcp(
    port: int | None = typer.Option(None, help="TCP port (default: stdin/stdout)"),
    config: str | None = typer.Option(None, help="Path to configuration file"),
) -> None:
    """Start MCP protocol server."""
    mode = "TCP" if port else "stdin/stdout"
    console.print(f"🔗 Starting MCP server ({mode})...", style="bold blue")

    try:
        # Import here to avoid circular dependencies
        from interfaces.mcp_server import run_server

        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Start MCP server
        run_server(cognitive_system=cognitive_system, port=port)

    except ImportError as e:
        console.print("❌ MCP interface not implemented yet", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error starting MCP server: {e}", style="bold red")
        raise typer.Exit(1) from e


@app.command("shell")  # type: ignore[misc]
def interactive_shell(
    config: str | None = typer.Option(None, help="Path to configuration file"),
    prompt: str | None = typer.Option(None, help="Custom prompt string"),
) -> None:
    """Start interactive cognitive memory shell."""
    console.print(
        "🧠 Starting interactive cognitive memory shell...", style="bold blue"
    )

    try:
        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Start interactive shell
        shell = InteractiveShell(cognitive_system, custom_prompt=prompt)
        shell.run()

        # Cleanup
        graceful_shutdown(cognitive_system)

    except InitializationError as e:
        console.print(f"❌ Failed to initialize system: {e}", style="bold red")
        raise typer.Exit(1) from e
    except KeyboardInterrupt:
        console.print("\n👋 Goodbye!", style="bold yellow")
    except Exception as e:
        console.print(f"❌ Error in shell: {e}", style="bold red")
        raise typer.Exit(1) from e


@app.command("doctor")  # type: ignore[misc]
def health_check(
    json_output: bool = typer.Option(
        False, "--json", help="Output results in JSON format"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Show detailed diagnostic information"
    ),
    fix: bool = typer.Option(False, "--fix", help="Attempt to fix detected issues"),
    config: str | None = typer.Option(None, help="Path to configuration file"),
) -> None:
    """Run comprehensive health checks and system verification."""
    console.print(
        "🩺 Running cognitive memory system health checks...", style="bold blue"
    )

    checker = HealthChecker(config_path=config)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running health checks...", total=None)

        try:
            results = checker.run_all_checks(verbose=verbose, fix_issues=fix)

            progress.update(task, description="✅ Health checks completed")

            if json_output:
                # JSON output for CI/CD integration
                json_results = {
                    "overall_status": results.overall_status.value,
                    "checks": [
                        {
                            "name": check.name,
                            "status": check.status.value,
                            "message": check.message,
                            "details": check.details,
                            "fix_attempted": check.fix_attempted,
                            "fix_successful": check.fix_successful,
                        }
                        for check in results.checks
                    ],
                    "recommendations": results.recommendations,
                    "timestamp": results.timestamp.isoformat(),
                }
                console.print(json.dumps(json_results, indent=2))

            else:
                # Rich formatted output
                _display_health_results(results, verbose)

            # Exit with appropriate code
            if results.overall_status == HealthResult.HEALTHY:
                console.print("✅ System is healthy!", style="bold green")
            elif results.overall_status == HealthResult.WARNING:
                console.print("⚠️ System has warnings", style="bold yellow")
                raise typer.Exit(1)
            else:
                console.print("❌ System has critical issues", style="bold red")
                raise typer.Exit(2)

        except Exception as e:
            progress.update(task, description=f"❌ Error: {str(e)}")
            console.print(f"❌ Error running health checks: {e}", style="bold red")
            raise typer.Exit(1) from e


def _display_health_results(results: HealthCheckResults, verbose: bool) -> None:
    """Display health check results in rich format."""
    # Overall status panel
    if results.overall_status == HealthResult.HEALTHY:
        status_color = "green"
        status_icon = "✅"
    elif results.overall_status == HealthResult.WARNING:
        status_color = "yellow"
        status_icon = "⚠️"
    else:
        status_color = "red"
        status_icon = "❌"

    status_panel = Panel(
        f"{status_icon} Overall Status: [bold {status_color}]{results.overall_status.value.upper()}[/bold {status_color}]",
        title="Health Check Summary",
        border_style=status_color,
    )
    console.print(status_panel)

    # Individual checks table
    checks_table = Table(title="Individual Health Checks")
    checks_table.add_column("Check", style="cyan")
    checks_table.add_column("Status", style="white")
    checks_table.add_column("Message", style="white")

    if verbose:
        checks_table.add_column("Details", style="dim")

    for check in results.checks:
        if check.status == HealthResult.HEALTHY:
            status_display = "✅ PASS"
        elif check.status == HealthResult.WARNING:
            status_display = "⚠️ WARN"
        else:
            status_display = "❌ FAIL"

        row_data = [check.name, status_display, check.message]
        if verbose and check.details:
            row_data.append(str(check.details))
        elif verbose:
            row_data.append("N/A")

        checks_table.add_row(*row_data)

    console.print(checks_table)

    # Recommendations
    if results.recommendations:
        console.print("\n📋 Recommendations:", style="bold blue")
        for i, recommendation in enumerate(results.recommendations, 1):
            console.print(f"  {i}. {recommendation}")


def main() -> int:
    """Main entry point for the unified CLI."""
    try:
        app()
        return 0
    except typer.Exit as e:
        return int(e.exit_code) if e.exit_code is not None else 1
    except KeyboardInterrupt:
        console.print("\n⚠️ Interrupted by user", style="bold yellow")
        return 130
    except Exception as e:
        console.print(f"❌ Unexpected error: {e}", style="bold red")
        return 1


if __name__ == "__main__":
    sys.exit(main())
