"""
Unified version management for the Heimdall MCP Server cognitive memory system.

This module provides centralized version tracking across all system components:
- System version from package metadata
- Database schema version from migrations
- Memory format version for data structure evolution
"""

from pathlib import Path

try:
    from importlib.metadata import version

    SYSTEM_VERSION = version("heimdall-mcp-server")
except Exception:
    SYSTEM_VERSION = "0.1.0"  # Fallback version


def get_latest_migration_version() -> str:
    """Get the latest migration version from the migrations directory."""
    try:
        migrations_dir = Path(__file__).parent.parent / "storage" / "migrations"
        if not migrations_dir.exists():
            return "000"

        migration_files = list(migrations_dir.glob("*.sql"))
        if not migration_files:
            return "000"

        # Extract version numbers from filenames (e.g., "006_source_path_index.sql" -> "006")
        versions = []
        for file in migration_files:
            name = file.stem
            if "_" in name:
                version_part = name.split("_")[0]
                if version_part.isdigit():
                    versions.append(version_part)

        return max(versions) if versions else "000"
    except Exception:
        return "000"


# Core version components
SCHEMA_VERSION = get_latest_migration_version()
MEMORY_FORMAT_VERSION = "hierarchical_v1"
MCP_PROTOCOL_VERSION = "1.0.0"

# Version tuple for easy comparison
VERSION_TUPLE = (
    SYSTEM_VERSION,
    SCHEMA_VERSION,
    MEMORY_FORMAT_VERSION,
    MCP_PROTOCOL_VERSION,
)


def get_version_info() -> dict:
    """Return comprehensive version information as a dictionary."""
    return {
        "system_version": SYSTEM_VERSION,
        "schema_version": SCHEMA_VERSION,
        "memory_format_version": MEMORY_FORMAT_VERSION,
        "mcp_protocol_version": MCP_PROTOCOL_VERSION,
        "version_string": f"{SYSTEM_VERSION}-schema{SCHEMA_VERSION}-{MEMORY_FORMAT_VERSION}",
    }


def get_version_string() -> str:
    """Return a formatted version string for display."""
    return f"Heimdall MCP Server v{SYSTEM_VERSION} (Schema: {SCHEMA_VERSION}, Memory: {MEMORY_FORMAT_VERSION})"


def is_compatible_schema_version(required_version: str) -> bool:
    """Check if current schema version is compatible with required version."""
    try:
        current = int(SCHEMA_VERSION)
        required = int(required_version)
        return current >= required
    except (ValueError, TypeError):
        return False
