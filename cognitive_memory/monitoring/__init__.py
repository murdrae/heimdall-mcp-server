"""
File monitoring module for cognitive memory system.

This module provides file change detection and monitoring capabilities
for automatic memory synchronization.
"""

from .file_monitor import (
    ChangeType,
    FileChangeEvent,
    FileState,
    MarkdownFileMonitor,
)
from .file_sync import (
    FileSyncError,
    FileSyncHandler,
)
from .loader_registry import (
    LoaderRegistry,
    create_default_registry,
)

__all__ = [
    "ChangeType",
    "FileChangeEvent",
    "FileState",
    "MarkdownFileMonitor",
    "FileSyncError",
    "FileSyncHandler",
    "LoaderRegistry",
    "create_default_registry",
]
