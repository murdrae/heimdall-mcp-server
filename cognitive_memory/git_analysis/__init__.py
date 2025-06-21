"""
Git analysis module for the cognitive memory system.

This module provides git repository analysis functionality,
storing individual commits as cognitive memories with metadata.
"""

from .commit import Commit, FileChange
from .commit_loader import CommitLoader
from .history_miner import GitHistoryMiner
from .security import (
    canonicalize_path,
    sanitize_git_data,
    validate_repository_path,
)

__all__ = [
    "Commit",
    "FileChange",
    "CommitLoader",
    "GitHistoryMiner",
    "validate_repository_path",
    "canonicalize_path",
    "sanitize_git_data",
]
