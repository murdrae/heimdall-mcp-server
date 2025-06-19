"""
Memory loader implementations for the cognitive memory system.

This module provides concrete implementations of the MemoryLoader interface
for loading external content into cognitive memory.
"""

from .git_loader import GitHistoryLoader
from .markdown_loader import MarkdownMemoryLoader

__all__ = ["MarkdownMemoryLoader", "GitHistoryLoader"]
