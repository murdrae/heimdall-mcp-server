"""
Git analysis module for the cognitive memory system.

This module provides secure git repository analysis functionality,
extracting development patterns and storing them as cognitive memories.
"""

from .data_structures import (
    CoChangePattern,
    CommitEvent,
    FileChangeEvent,
    MaintenanceHotspot,
    ProblemCommit,
    SolutionPattern,
)
from .history_miner import GitHistoryMiner
from .pattern_detector import PatternDetector
from .security import canonicalize_path, sanitize_git_data, validate_repository_path

__all__ = [
    "CommitEvent",
    "FileChangeEvent",
    "ProblemCommit",
    "CoChangePattern",
    "MaintenanceHotspot",
    "SolutionPattern",
    "GitHistoryMiner",
    "PatternDetector",
    "validate_repository_path",
    "canonicalize_path",
    "sanitize_git_data",
]
