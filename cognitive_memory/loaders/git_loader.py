"""
Git repository memory loader for the cognitive memory system.

This module implements a MemoryLoader for git repositories, storing individual
commits as memories with metadata for retrieval and connection analysis.
Each commit becomes a cognitive memory with full context and file changes.
"""

from typing import Any

from loguru import logger

from ..core.config import CognitiveConfig
from ..core.interfaces import MemoryLoader
from ..core.memory import CognitiveMemory
from ..git_analysis.commit_loader import CommitLoader


class GitHistoryLoader(MemoryLoader):
    """
    Memory loader for git repositories.

    Stores individual git commits as cognitive memories with metadata for
    retrieval and connection analysis. Each commit becomes a memory with
    full context including file changes and author information.
    """

    def __init__(self, config: CognitiveConfig, cognitive_system: Any = None):
        """
        Initialize the git history loader.

        Args:
            config: Cognitive configuration parameters
            cognitive_system: Optional CognitiveSystem instance for operations
        """
        self.config = config
        self.cognitive_system = cognitive_system

        # Initialize commit loader
        self.commit_loader = CommitLoader(config, cognitive_system)

        logger.info("GitHistoryLoader initialized for git commit storage")

    def load_from_source(
        self, source_path: str, **kwargs: Any
    ) -> list[CognitiveMemory]:
        """
        Load cognitive memories from git commits.

        Stores individual git commits as memories with metadata for
        retrieval and connection analysis.

        Args:
            source_path: Path to the git repository
            **kwargs: Additional parameters (max_commits, since_date, etc.)

        Returns:
            List of CognitiveMemory objects created from git commits
        """
        return self.commit_loader.load_from_source(source_path, **kwargs)

    def extract_connections(
        self, memories: list[CognitiveMemory]
    ) -> list[tuple[str, str, float, str]]:
        """
        Extract connections between git commit memories.

        Identifies relationships between commits based on shared files,
        authors, and temporal proximity.

        Args:
            memories: List of commit memories to analyze for connections

        Returns:
            List of tuples: (source_id, target_id, strength, connection_type)
        """
        return self.commit_loader.extract_connections(memories)

    def validate_source(self, source_path: str) -> bool:
        """
        Validate that the source is a readable git repository.

        Args:
            source_path: Path to validate

        Returns:
            True if source is valid for this loader
        """
        return self.commit_loader.validate_source(source_path)

    def get_supported_extensions(self) -> list[str]:
        """
        Get list of file extensions supported by this loader.

        Returns:
            Empty list since git repositories are identified by .git directory
        """
        return self.commit_loader.get_supported_extensions()
