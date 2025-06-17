# Setup Automation System - Technical Design

## Overview

This document provides the detailed technical design for the setup automation system that will provide single-script deployment for the cognitive memory system.

## Architecture Decision Summary

**Chosen Approach**: Embedded Container Helper with Unified CLI
- Single Python package with embedded service management
- Docker container management with local binary fallback
- Unified CLI interface for all operations
- Fast health checking and verification system

## Detailed Technical Design

### 1. CLI Structure

```python
# memory_system/cli.py
import typer
from typing import Optional

app = typer.Typer(help="Cognitive Memory System")

# Service management commands
qdrant_app = typer.Typer(help="Qdrant vector database management")
app.add_typer(qdrant_app, name="qdrant")

# Server interface commands
serve_app = typer.Typer(help="Start interface servers")
app.add_typer(serve_app, name="serve")

@qdrant_app.command("start")
def qdrant_start(
    port: int = 6333,
    data_dir: Optional[str] = None,
    detach: bool = True,
    force_local: bool = False
):
    """Start Qdrant vector database"""
    pass

@qdrant_app.command("stop")
def qdrant_stop():
    """Stop Qdrant vector database"""
    pass

@qdrant_app.command("status")
def qdrant_status():
    """Check Qdrant status"""
    pass

@serve_app.command("http")
def serve_http(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False
):
    """Start HTTP API server"""
    pass

@serve_app.command("mcp")
def serve_mcp(
    port: Optional[int] = None,
    stdin: bool = False
):
    """Start MCP protocol server"""
    pass

@app.command("shell")
def interactive_shell():
    """Start interactive cognitive memory shell"""
    pass

@app.command("doctor")
def health_check(
    json_output: bool = False,
    verbose: bool = False
):
    """Run comprehensive health checks"""
    pass
```

### 2. Service Management Architecture

```python
# memory_system/services/qdrant_manager.py
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any
import subprocess
import json
from pathlib import Path

class ServiceStatus(Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    UNKNOWN = "unknown"

class QdrantManager(ABC):
    """Abstract base for Qdrant management strategies"""

    @abstractmethod
    def start(self, **kwargs) -> bool:
        pass

    @abstractmethod
    def stop(self) -> bool:
        pass

    @abstractmethod
    def status(self) -> ServiceStatus:
        pass

    @abstractmethod
    def get_connection_url(self) -> str:
        pass

class DockerQdrantManager(QdrantManager):
    """Docker-based Qdrant management"""

    def __init__(self, container_name: str = "cognitive-memory-qdrant"):
        self.container_name = container_name
        self.image = "qdrant/qdrant:v1.7.4"  # Pinned version

    def start(self,
              port: int = 6333,
              data_dir: Optional[str] = None,
              **kwargs) -> bool:
        """Start Qdrant in Docker container"""

        # Check if already running
        if self.status() == ServiceStatus.RUNNING:
            return True

        # Set up data directory
        if data_dir is None:
            data_dir = Path.cwd() / "data" / "qdrant"
        data_dir = Path(data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)

        # Build docker run command
        cmd = [
            "docker", "run", "-d",
            "--name", self.container_name,
            "-p", f"{port}:6333",
            "-p", f"{port+1}:6334",  # Admin interface
            "-v", f"{data_dir.absolute()}:/qdrant/storage",
            "--restart", "unless-stopped",
            self.image
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        except subprocess.SubprocessError:
            return False

    def stop(self) -> bool:
        """Stop and remove container"""
        try:
            subprocess.run(["docker", "stop", self.container_name],
                         capture_output=True, check=True)
            subprocess.run(["docker", "rm", self.container_name],
                         capture_output=True, check=True)
            return True
        except subprocess.SubprocessError:
            return False

    def status(self) -> ServiceStatus:
        """Check container status"""
        try:
            result = subprocess.run([
                "docker", "ps", "--filter", f"name={self.container_name}",
                "--format", "{{.Status}}"
            ], capture_output=True, text=True, check=True)

            if result.stdout.strip():
                return ServiceStatus.RUNNING
            else:
                return ServiceStatus.STOPPED
        except subprocess.SubprocessError:
            return ServiceStatus.ERROR

class LocalQdrantManager(QdrantManager):
    """Local binary Qdrant management"""

    def __init__(self, binary_dir: Optional[Path] = None):
        self.binary_dir = binary_dir or (Path.home() / ".cache" / "cognitive-memory")
        self.binary_path = self.binary_dir / "qdrant"
        self.data_dir = Path.cwd() / "data" / "qdrant"
        self.process = None

    def _download_binary(self) -> bool:
        """Download Qdrant binary if not present"""
        if self.binary_path.exists():
            return True

        # Implementation for downloading appropriate binary
        # This is a simplified version
        import platform
        import requests

        system = platform.system().lower()
        arch = platform.machine().lower()

        # Map to Qdrant release naming
        platform_map = {
            ("linux", "x86_64"): "x86_64-unknown-linux-gnu",
            ("darwin", "x86_64"): "x86_64-apple-darwin",
            ("darwin", "arm64"): "aarch64-apple-darwin",
        }

        target = platform_map.get((system, arch))
        if not target:
            return False

        # Download from GitHub releases
        version = "v1.7.4"
        url = f"https://github.com/qdrant/qdrant/releases/download/{version}/qdrant-{target}.tar.gz"

        try:
            self.binary_dir.mkdir(parents=True, exist_ok=True)
            # Download and extract logic here
            return True
        except Exception:
            return False
```

### 3. Health Checking System

```python
# memory_system/health/doctor.py
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import sys
import subprocess
import requests
from pathlib import Path
from rich.console import Console
from rich.table import Table
import json

@dataclass
class HealthCheck:
    name: str
    description: str
    status: str  # "ok", "warning", "error"
    message: str
    details: Optional[Dict[str, Any]] = None

class SystemDoctor:
    """Comprehensive health checking for cognitive memory system"""

    def __init__(self):
        self.console = Console()
        self.checks: List[HealthCheck] = []

    def run_all_checks(self, verbose: bool = False) -> bool:
        """Run all health checks and return overall status"""

        self.checks = [
            self._check_python_version(),
            self._check_dependencies(),
            self._check_qdrant_service(),
            self._check_qdrant_connectivity(),
            self._check_sqlite_database(),
            self._check_model_compatibility(),
            self._check_ports(),
            self._check_disk_space(),
        ]

        if verbose:
            self._display_verbose_results()
        else:
            self._display_summary()

        return all(check.status == "ok" for check in self.checks)

    def _check_python_version(self) -> HealthCheck:
        """Verify Python version compatibility"""
        current_version = sys.version_info

        if current_version >= (3, 13):
            return HealthCheck(
                name="Python Version",
                description="Python 3.13+ compatibility",
                status="ok",
                message=f"Python {current_version.major}.{current_version.minor}.{current_version.micro}",
                details={"version": str(current_version)}
            )
        elif current_version >= (3, 12):
            return HealthCheck(
                name="Python Version",
                description="Python 3.13+ compatibility",
                status="warning",
                message=f"Python {current_version.major}.{current_version.minor} detected, 3.13+ recommended",
                details={"version": str(current_version)}
            )
        else:
            return HealthCheck(
                name="Python Version",
                description="Python 3.13+ compatibility",
                status="error",
                message=f"Python {current_version.major}.{current_version.minor} too old, need 3.12+",
                details={"version": str(current_version)}
            )

    def _check_qdrant_service(self) -> HealthCheck:
        """Check if Qdrant service is running"""
        from memory_system.services.qdrant_manager import ServiceManager

        manager = ServiceManager.get_manager()
        status = manager.status()

        if status.value == "running":
            return HealthCheck(
                name="Qdrant Service",
                description="Vector database availability",
                status="ok",
                message="Qdrant is running",
                details={"url": manager.get_connection_url()}
            )
        else:
            return HealthCheck(
                name="Qdrant Service",
                description="Vector database availability",
                status="error",
                message=f"Qdrant is {status.value}. Run: memory_system qdrant start",
                details={"status": status.value}
            )

    def _check_qdrant_connectivity(self) -> HealthCheck:
        """Test actual connection to Qdrant"""
        try:
            from qdrant_client import QdrantClient
            client = QdrantClient(url="http://localhost:6333")

            # Test basic operation
            collections = client.get_collections()

            return HealthCheck(
                name="Qdrant Connectivity",
                description="Vector database connection test",
                status="ok",
                message=f"Connected successfully, {len(collections.collections)} collections",
                details={"collections": len(collections.collections)}
            )
        except Exception as e:
            return HealthCheck(
                name="Qdrant Connectivity",
                description="Vector database connection test",
                status="error",
                message=f"Connection failed: {str(e)[:100]}...",
                details={"error": str(e)}
            )

    def _display_summary(self):
        """Display concise health check summary"""
        table = Table(title="System Health Check")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Message", style="dim")

        for check in self.checks:
            status_style = {
                "ok": "green",
                "warning": "yellow",
                "error": "red"
            }.get(check.status, "white")

            status_symbol = {
                "ok": "✓",
                "warning": "⚠",
                "error": "✗"
            }.get(check.status, "?")

            table.add_row(
                check.name,
                f"[{status_style}]{status_symbol} {check.status.upper()}[/{status_style}]",
                check.message
            )

        self.console.print(table)

        # Summary
        ok_count = sum(1 for c in self.checks if c.status == "ok")
        warning_count = sum(1 for c in self.checks if c.status == "warning")
        error_count = sum(1 for c in self.checks if c.status == "error")

        if error_count == 0:
            self.console.print(f"\n[green]✓ All systems operational[/green] ({ok_count} ok, {warning_count} warnings)")
        else:
            self.console.print(f"\n[red]✗ {error_count} error(s) found[/red] ({ok_count} ok, {warning_count} warnings)")

    def output_json(self) -> str:
        """Output results as JSON for CI/CD"""
        result = {
            "overall_status": "ok" if all(c.status == "ok" for c in self.checks) else "error",
            "timestamp": "2025-06-17T00:00:00Z",  # Use actual timestamp
            "checks": [
                {
                    "name": check.name,
                    "description": check.description,
                    "status": check.status,
                    "message": check.message,
                    "details": check.details or {}
                }
                for check in self.checks
            ]
        }
        return json.dumps(result, indent=2)
```

### 4. Configuration Management

```python
# memory_system/config/settings.py
from pydantic import BaseSettings, Field
from pathlib import Path
from typing import Optional

class CognitiveMemorySettings(BaseSettings):
    """Centralized configuration with environment override support"""

    # Qdrant settings
    qdrant_url: str = Field(default="http://localhost:6333", env="QDRANT_URL")
    qdrant_api_key: Optional[str] = Field(default=None, env="QDRANT_API_KEY")

    # Database settings
    sqlite_path: Path = Field(default=Path("./data/cognitive_memory.db"), env="SQLITE_PATH")

    # Model settings
    sentence_bert_model: str = Field(default="all-MiniLM-L6-v2", env="SENTENCE_BERT_MODEL")

    # Cognitive parameters
    activation_threshold: float = Field(default=0.7, env="ACTIVATION_THRESHOLD")
    bridge_discovery_k: int = Field(default=5, env="BRIDGE_DISCOVERY_K")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # Service settings
    http_host: str = Field(default="127.0.0.1", env="HTTP_HOST")
    http_port: int = Field(default=8000, env="HTTP_PORT")
    mcp_port: Optional[int] = Field(default=None, env="MCP_PORT")

    class Config:
        env_prefix = "COGNITIVE_MEMORY_"
        case_sensitive = False
        env_file = ".env"
        env_file_encoding = "utf-8"

# Global settings instance
settings = CognitiveMemorySettings()
```

### 5. Integration Points

The setup automation system will integrate with existing code through:

1. **CLI Integration**: Replace existing CLI with unified interface
2. **Configuration**: Centralize all configuration through Pydantic settings
3. **Service Discovery**: Abstract service connection through configuration
4. **Health Monitoring**: Embed health checks in existing operations

## Implementation Plan

1. **Phase 1**: Core CLI structure and service management
2. **Phase 2**: Health checking and verification system
3. **Phase 3**: Integration with existing interfaces
4. **Phase 4**: Documentation and testing

## Testing Strategy

- Unit tests for each service manager
- Integration tests for end-to-end workflows
- Health check validation tests
- Cross-platform compatibility tests
- CI/CD pipeline integration tests

This design provides a robust, extensible foundation for setup automation while maintaining the research-focused simplicity required by the project.
