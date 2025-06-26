# 024 - MCP Integration Management

## Overview
Create `heimdall mcp` command group to manage MCP server integrations across platforms (Claude Code, VS Code, Cursor, Visual Studio).

## Status
- **Started**: 2025-06-25
- **Current Step**: Steps 3-5 completed - Full implementation with install/remove functionality
- **Completion**: 95%

## Core Data Structures

### Platform Configuration Registry
```python
@dataclass
class PlatformConfig:
    name: str
    config_file: str        # Project-local config file path
    server_key: str         # "servers" or "mcpServers"
    method: str            # "json_modify" or "cli_command"
    detection_folders: List[str]  # For auto-detection

PLATFORMS = {
    "vscode": PlatformConfig(
        name="Visual Studio Code",
        config_file=".vscode/mcp.json",
        server_key="servers",
        method="json_modify",
        detection_folders=[".vscode"]
    ),
    "cursor": PlatformConfig(
        name="Cursor",
        config_file=".vscode/mcp.json",  # Shares VS Code config
        server_key="servers",
        method="json_modify",
        detection_folders=[".cursor"]
    ),
    "visual-studio": PlatformConfig(
        name="Visual Studio",
        config_file=".mcp.json",
        server_key="mcpServers",
        method="json_modify",
        detection_folders=[".vs"]
    ),
    "claude-code": PlatformConfig(
        name="Claude Code",
        config_file="",
        server_key="",
        method="cli_command",
        detection_folders=[]
    )
}
```

### Server Configuration Template
```python
@dataclass
class ServerConfig:
    name: str = "heimdall-cognitive-memory"
    type: str = "stdio"
    command: str = ""  # Will be dynamically set
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)

def get_server_config() -> ServerConfig:
    """Generate server config with current project paths."""
    project_root = Path.cwd()
    project_id = get_project_id(project_root)  # Use proper project ID
    return ServerConfig(
        name=f"heimdall-{project_id}",
        command="heimdall-mcp",  # Use entry point
        env={"PROJECT_PATH": str(project_root)}
    )
```

## Per-Project Configuration Strategy

All IDEs support **project-local configuration files** that provide automatic project isolation:

- **VS Code**: `.vscode/mcp.json` (workspace-specific, can be committed to git)
- **Cursor**: `.vscode/mcp.json` (shares VS Code config, auto-detected via .cursor folder)
- **Visual Studio**: `.mcp.json` (solution-specific)
- **Claude Code**: `--scope project` (project-local scope)

This eliminates cross-project conflicts since each project maintains its own configuration.

## Expected Configuration Formats

### VS Code (.vscode/mcp.json) - Project-Local
```json
{
  "servers": {
    "heimdall-cognitive_memory_21697a48": {
      "type": "stdio",
      "command": "heimdall-mcp",
      "args": [],
      "env": {
        "PROJECT_PATH": "/home/foo/workspace/cognitive-memory"
      }
    }
  }
}
```

### Cursor (.vscode/mcp.json) - Shares VS Code Config
```json
{
  "servers": {
    "heimdall-cognitive_memory_21697a48": {
      "type": "stdio",
      "command": "heimdall-mcp",
      "args": [],
      "env": {
        "PROJECT_PATH": "/home/foo/workspace/cognitive-memory"
      }
    }
  }
}
```

### Visual Studio (.mcp.json) - Project-Local
```json
{
  "mcpServers": {
    "heimdall-cognitive_memory_21697a48": {
      "type": "stdio",
      "command": "heimdall-mcp",
      "args": [],
      "env": {
        "PROJECT_PATH": "/home/foo/workspace/cognitive-memory"
      }
    }
  }
}
```

### Claude Code Command (Project-Scoped by Default)
```bash
# Project scope (default) - automatically project-local
claude mcp add heimdall-cognitive_memory_21697a48 \
  --scope project \
  -e PROJECT_PATH=/home/foo/workspace/cognitive-memory \
  --transport stdio heimdall-mcp

# User scope (global) - available across all projects
claude mcp add heimdall-cognitive_memory_21697a48 \
  --scope user \
  -e PROJECT_PATH=/home/foo/workspace/cognitive-memory \
  --transport stdio heimdall-mcp
```

### Multi-Project Example (No Conflicts)
```bash
# Project A
/project-a/.vscode/mcp.json -> heimdall server pointing to /project-a/

# Project B
/project-b/.cursor/mcp.json -> heimdall server pointing to /project-b/

# Each project isolated, same server name, different paths
```

## Implementation Tasks

### 1. Create `heimdall/cli_commands/mcp_commands.py`

#### Command Function Signatures
```python
def install_mcp(
    platform: str = typer.Argument(..., help="Platform: vscode, cursor, claude-code"),
    scope: str = typer.Option("project", help="Scope: project, user (claude-code only)"),
    force: bool = typer.Option(False, help="Overwrite existing configuration")
) -> None:

def list_mcp() -> None:
    """List available platforms and installation status."""

def remove_mcp(
    platform: str = typer.Argument(..., help="Platform to remove from")
) -> None:

def status_mcp() -> None:
    """Show installation status for all detected platforms."""

def generate_mcp(
    platform: str = typer.Argument(..., help="Platform to generate config for"),
    output: Optional[str] = typer.Option(None, help="Output file path")
) -> None:
```

#### Core Implementation Methods
```python
def detect_platforms() -> List[str]:
    """Detect available platforms in current directory."""

def find_config_file(platform_config: PlatformConfig) -> Optional[Path]:
    """Find existing config file or return preferred location."""

def modify_json_config(config_path: Path, server_config: ServerConfig, platform_config: PlatformConfig) -> None:
    """Safely modify JSON config, preserving existing servers."""

def execute_claude_mcp_add(server_config: ServerConfig, scope: str) -> None:
    """Execute 'claude mcp add' command."""

def generate_config_snippet(platform_config: PlatformConfig, server_config: ServerConfig) -> Dict:
    """Generate config snippet for manual addition."""
```

### 2. JSON Configuration Logic

#### Safe JSON Modification Pattern
```python
def modify_json_config(config_path: Path, server_config: ServerConfig, platform_config: PlatformConfig) -> None:
    # Read existing or create new
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
    else:
        config = {}

    # Ensure server section exists
    if platform_config.server_key not in config:
        config[platform_config.server_key] = {}

    # Add/update our server
    config[platform_config.server_key][server_config.name] = {
        "type": server_config.type,
        "command": server_config.command,
        "args": server_config.args,
        "env": server_config.env
    }

    # Write back with formatting
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
```

### 3. Claude Code Integration

#### CLI Command Execution
```python
def execute_claude_mcp_add(server_config: ServerConfig, scope: str) -> None:
    cmd = [
        "claude", "mcp", "add",
        server_config.name,
        "--scope", scope,
        server_config.command
    ] + server_config.args

    # Add environment variables if any
    for key, value in server_config.env.items():
        cmd.extend(["-e", f"{key}={value}"])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Claude MCP add failed: {result.stderr}")
```

### 4. CLI Registration in `heimdall/cli.py`

```python
from heimdall.cli_commands.mcp_commands import (
    install_mcp,
    list_mcp,
    remove_mcp,
    status_mcp,
    generate_mcp
)

# Create MCP command group
mcp_app = typer.Typer(help="🔗 MCP integration management")
app.add_typer(mcp_app, name="mcp")

# Register commands
mcp_app.command("install")(install_mcp)
mcp_app.command("list")(list_mcp)
mcp_app.command("remove")(remove_mcp)
mcp_app.command("status")(status_mcp)
mcp_app.command("generate")(generate_mcp)
```

## Technical Decisions

### File Structure
```
heimdall/cli_commands/mcp_commands.py  # Main implementation
heimdall/cli.py                        # Command registration (modify)
```

### Error Handling Strategy
- JSON validation before writing
- Subprocess error capture for Claude Code
- Graceful fallback to generate mode if modification fails
- Clear error messages with suggested manual steps

### Output Formatting
- Rich tables for status/list commands
- JSON output option for programmatic use
- Color-coded status indicators (✅ installed, ❌ not found, ⚠️ outdated)

## Implementation Order
1. ✅ Create `mcp_commands.py` with basic structure and platform registry
2. ✅ Implement `generate_mcp()` for snippet generation (no file modification)
3. ✅ Implement `detect_platforms()` and `status_mcp()` for discovery
4. ✅ Implement JSON modification logic for `install_mcp()`
5. ✅ Implement Claude Code CLI integration
6. ✅ Register commands in main CLI
7. ✅ Test with each platform
8. ✅ Implement `remove_mcp()` functionality

## Progress Notes

### Step 1: Basic Structure (Completed 2025-06-25)
Created `heimdall/cli_commands/mcp_commands.py` with:
- **Data Structures**: `PlatformConfig`, `ServerConfig`, `PLATFORMS` registry
- **Platform Registry**: VS Code (.vscode/mcp.json), Cursor (.cursor/mcp.json), Visual Studio (.mcp.json), Claude Code (CLI)
- **Command Functions**: All 5 command signatures with placeholder implementations
- **Helper Methods**: `detect_platforms()`, `find_config_file()`, `get_server_config()`, config generation
- **Project Patterns**: Rich console, typer interface, proper error handling

All functions show planned actions without making actual changes, ready for next implementation steps.

### Step 2: Config Generation (Completed 2025-06-25)
Enhanced `generate_mcp()` command with full functionality:
- **Rich Formatting**: Syntax-highlighted JSON/bash output using Rich Syntax component
- **Enhanced generate_config_snippet()**: Platform-specific JSON structure generation
- **Output Options**: Console display with Rich formatting + optional file output via `--output`
- **Platform Support**: All 4 platforms (VS Code, Cursor, Visual Studio, Claude Code)
- **Usage Instructions**: Platform-specific setup guidance for each configuration type
- **CLI Integration**: Registered MCP command group in main CLI (`heimdall mcp generate`)
- **Comprehensive Testing**: Verified config generation, file output, and error handling

Features implemented:
- JSON configs for IDEs (`.vscode/mcp.json`, `.cursor/mcp.json`, `.mcp.json`)
- CLI command generation for Claude Code with proper environment variables
- File output support for both JSON configs and bash scripts
- Error handling for invalid platforms with helpful suggestions
- Platform-specific instructions and configuration guidance

### Steps 3-5: Full Implementation (Completed 2025-06-26)
Implemented complete MCP integration management system:
- **Enhanced Platform Detection**: `check_installation_status()` function detects actual installations by parsing config files and executing CLI commands
- **Advanced Status Reporting**: `status_mcp()` shows detailed status with actionable guidance and summary statistics
- **JSON Configuration Management**: `modify_json_config()` safely creates/modifies config files with force flag support
- **Claude Code CLI Integration**: `execute_claude_mcp_add()` and remove functionality with proper validation
- **Full Install/Remove Workflow**: Complete lifecycle management with verification and helpful next steps

**Key Implementation Fixes**:
- **Project ID Integration**: Uses `get_project_id()` from `cognitive_memory.core.config` for consistent naming (`heimdall-cognitive_memory_21697a48`)
- **Entry Point Usage**: Commands use `heimdall-mcp` entry point with `--transport stdio` flag
- **Cursor Config Sharing**: Correctly configured to share `.vscode/mcp.json` with VS Code
- **Syntax Highlighting**: Rich formatting without line numbers for clean copy/paste
- **Error Handling**: Comprehensive error handling with user-friendly messages

**Tested Functionality**:
- ✅ Platform detection across VS Code, Cursor, Claude Code, Visual Studio
- ✅ Configuration generation with proper project-specific naming
- ✅ Installation workflow for JSON (VS Code/Cursor) and CLI (Claude Code) platforms
- ✅ Status reporting with actual installation verification
- ✅ Removal functionality for both JSON and CLI platforms

## Change Log
- **2025-06-25**: Technical implementation plan defined
- **2025-06-25**: Step 1 completed - Basic structure and command signatures implemented
- **2025-06-25**: Step 2 completed - Config generation with Rich formatting and CLI integration
- **2025-06-26**: Steps 3-5 completed - Full implementation with install/remove functionality
