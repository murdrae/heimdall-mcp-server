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

__all__ = [
    "ChangeType",
    "FileChangeEvent",
    "FileState",
    "MarkdownFileMonitor",
]
