"""
Git commit memory loader for the cognitive memory system.

This module implements git commit storage as cognitive memories, providing
direct access to commit history with metadata for retrieval and connection.
Each commit becomes a memory with full context and file change information.
"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from ..core.config import CognitiveConfig
from ..core.interfaces import MemoryLoader
from ..core.memory import CognitiveMemory
from .commit import Commit
from .history_miner import GitHistoryMiner
from .security import validate_repository_path


class CommitLoader(MemoryLoader):
    """
    Memory loader that converts git commits to cognitive memories.

    This approach stores actual commit history with full metadata,
    providing direct access to development history and file changes.
    """

    def __init__(self, config: CognitiveConfig, cognitive_system: Any = None):
        """
        Initialize the commit loader.

        Args:
            config: Cognitive configuration parameters
            cognitive_system: Optional CognitiveSystem instance for operations
        """
        self.config = config
        self.cognitive_system = cognitive_system

        logger.info("CommitLoader initialized for git commit storage")

    def load_from_source(
        self, source_path: str, **kwargs: Any
    ) -> list[CognitiveMemory]:
        """
        Load cognitive memories from git commits.

        Args:
            source_path: Path to the git repository
            **kwargs: Additional parameters (max_commits, since_date, etc.)

        Returns:
            List of CognitiveMemory objects created from commits
        """
        if not self.validate_source(source_path):
            raise ValueError(f"Invalid git repository: {source_path}")

        logger.info(f"Loading git commits from {source_path}")

        # Extract configuration from kwargs
        max_commits = kwargs.get("max_commits", 1000)
        since_date = kwargs.get("since_date")
        until_date = kwargs.get("until_date")
        branch = kwargs.get("branch")

        try:
            # Initialize history miner for this repository
            with GitHistoryMiner(source_path) as history_miner:
                # Extract commits directly as Commit objects
                commits = list(
                    history_miner.extract_commit_history(
                        max_commits=max_commits,
                        since_date=since_date,
                        until_date=until_date,
                        branch=branch,
                    )
                )

                logger.info(f"Extracted {len(commits)} commits")

                # Convert to cognitive memories
                memories = []
                for commit in commits:
                    memory = self._create_commit_memory(commit, source_path)
                    memories.append(memory)

                logger.info(
                    f"Created {len(memories)} cognitive memories from git commits"
                )
                return memories

        except Exception as e:
            logger.error(f"Failed to load git commits from {source_path}: {e}")
            raise

    def extract_connections(
        self, memories: list[CognitiveMemory]
    ) -> list[tuple[str, str, float, str]]:
        """
        Extract connections between commit memories based on shared files.

        Args:
            memories: List of commit memories to analyze for connections

        Returns:
            List of tuples: (source_id, target_id, strength, connection_type)
        """
        connections = []

        try:
            # Create file index for efficient lookup
            file_to_commits: dict[str, list[CognitiveMemory]] = {}
            for memory in memories:
                affected_files = memory.metadata.get("affected_files", [])
                for file_path in affected_files:
                    if file_path not in file_to_commits:
                        file_to_commits[file_path] = []
                    file_to_commits[file_path].append(memory)

            # Create connections between commits that touch the same files
            for file_path, file_memories in file_to_commits.items():
                if len(file_memories) < 2:
                    continue

                # Sort by timestamp for chronological connections
                file_memories.sort(
                    key=lambda m: m.metadata.get("timestamp", datetime.min)
                )

                # Connect adjacent commits (temporal file evolution)
                for i in range(len(file_memories) - 1):
                    current_memory = file_memories[i]
                    next_memory = file_memories[i + 1]

                    # Calculate connection strength based on temporal proximity
                    # and size of change
                    strength = self._calculate_file_connection_strength(
                        current_memory, next_memory, file_path
                    )

                    if strength >= 0.3:  # Minimum threshold
                        connections.append(
                            (
                                current_memory.id,
                                next_memory.id,
                                strength,
                                f"file_evolution:{file_path}",
                            )
                        )

            # Also create author-based connections (same author working on related changes)
            author_connections = self._extract_author_connections(memories)
            connections.extend(author_connections)

            logger.info(f"Extracted {len(connections)} connections between commits")
            return connections

        except Exception as e:
            logger.error(f"Failed to extract connections: {e}")
            return []

    def validate_source(self, source_path: str) -> bool:
        """
        Validate that the source is a readable git repository.

        Args:
            source_path: Path to validate

        Returns:
            True if source is valid for this loader
        """
        try:
            # Check if path exists and is a directory
            path = Path(source_path)
            if not path.exists() or not path.is_dir():
                return False

            # Check for .git directory
            git_dir = path / ".git"
            if not git_dir.exists():
                return False

            # Use security validator for comprehensive checks
            return validate_repository_path(source_path)

        except Exception as e:
            logger.warning(f"Git repository validation failed for {source_path}: {e}")
            return False

    def get_supported_extensions(self) -> list[str]:
        """
        Get list of file extensions supported by this loader.

        Returns:
            Empty list since git repositories are identified by .git directory
        """
        return []  # Git repositories identified by .git directory, not extension

    def _create_commit_memory(
        self, commit: Commit, source_path: str
    ) -> CognitiveMemory:
        """Create CognitiveMemory from a Commit."""
        # Generate deterministic ID based on repository and commit hash
        repo_name = Path(source_path).name
        memory_id = self._generate_commit_id(repo_name, commit.hash)

        # Generate natural language content
        content = commit.to_natural_language()

        # Classify as L2 (Episode) - specific events with full context
        hierarchy_level = 2

        # Calculate strength based on commit size and recency
        total_added, total_deleted = commit.get_total_line_changes()
        total_changes = total_added + total_deleted

        # Normalize strength: larger commits and more recent commits get higher strength
        size_factor = min(1.0, total_changes / 100.0)  # Max at 100 line changes
        days_old = (datetime.now() - commit.timestamp).days
        recency_factor = max(0.1, 1.0 - (days_old / 365.0))  # Decay over a year
        strength = min(1.0, (size_factor + recency_factor) / 2.0)

        # Extract file extensions for metadata
        file_extensions = list(
            {
                Path(fc.file_path).suffix.lower()
                for fc in commit.file_changes
                if Path(fc.file_path).suffix
            }
        )

        return CognitiveMemory(
            id=memory_id,
            content=content,
            hierarchy_level=hierarchy_level,
            strength=strength,
            created_date=datetime.now(),
            modified_date=commit.timestamp,
            source_date=commit.timestamp,
            metadata={
                "type": "git_commit",
                "source_path": source_path,
                "commit_hash": commit.hash,
                "author_name": commit.author_name,
                "author_email": commit.author_email,
                "timestamp": commit.timestamp.isoformat(),
                "affected_files": commit.get_affected_files(),
                "file_extensions": file_extensions,
                "lines_added": total_added,
                "lines_deleted": total_deleted,
                "file_count": len(commit.file_changes),
                "parent_hashes": commit.parent_hashes,
                "loader_type": "git_commit",
                "commit_version": "1.0",
            },
        )

    def _generate_commit_id(self, repo_name: str, commit_hash: str) -> str:
        """Generate deterministic ID for a commit memory."""
        # Use repo name and commit hash for deterministic ID
        id_input = f"git_commit:{repo_name}:{commit_hash}"
        return hashlib.sha256(id_input.encode()).hexdigest()[:16]

    def _calculate_file_connection_strength(
        self, memory1: CognitiveMemory, memory2: CognitiveMemory, file_path: str
    ) -> float:
        """Calculate connection strength between two commits for a specific file."""
        try:
            # Base strength
            strength = 0.5

            # Increase strength if both commits significantly modify the file
            lines1 = memory1.metadata.get("lines_added", 0) + memory1.metadata.get(
                "lines_deleted", 0
            )
            lines2 = memory2.metadata.get("lines_added", 0) + memory2.metadata.get(
                "lines_deleted", 0
            )

            if lines1 > 10 and lines2 > 10:
                strength += 0.2

            # Increase strength if commits are temporally close
            time1 = datetime.fromisoformat(memory1.metadata.get("timestamp", ""))
            time2 = datetime.fromisoformat(memory2.metadata.get("timestamp", ""))
            time_diff_days = abs((time2 - time1).days)

            if time_diff_days <= 1:
                strength += 0.3
            elif time_diff_days <= 7:
                strength += 0.2
            elif time_diff_days <= 30:
                strength += 0.1

            # Increase strength if same author
            if memory1.metadata.get("author_email") == memory2.metadata.get(
                "author_email"
            ):
                strength += 0.1

            return min(1.0, strength)

        except Exception:
            return 0.5  # Default strength

    def _extract_author_connections(
        self, memories: list[CognitiveMemory]
    ) -> list[tuple[str, str, float, str]]:
        """Extract connections between commits by the same author on the same day."""
        connections = []

        try:
            # Group commits by author and date
            author_date_groups: dict[str, list[CognitiveMemory]] = {}
            for memory in memories:
                author = memory.metadata.get("author_email", "")
                timestamp = memory.metadata.get("timestamp", "")
                if not author or not timestamp:
                    continue

                date = datetime.fromisoformat(timestamp).date()
                key = f"{author}:{date}"

                if key not in author_date_groups:
                    author_date_groups[key] = []
                author_date_groups[key].append(memory)

            # Create connections within each group
            for group_memories in author_date_groups.values():
                if len(group_memories) < 2:
                    continue

                # Sort by timestamp
                group_memories.sort(
                    key=lambda m: datetime.fromisoformat(
                        m.metadata.get("timestamp", "")
                    )
                )

                # Connect adjacent commits in the same work session
                for i in range(len(group_memories) - 1):
                    current = group_memories[i]
                    next_commit = group_memories[i + 1]

                    # Check if commits are close in time (same work session)
                    time1 = datetime.fromisoformat(
                        current.metadata.get("timestamp", "")
                    )
                    time2 = datetime.fromisoformat(
                        next_commit.metadata.get("timestamp", "")
                    )
                    hours_diff = abs((time2 - time1).total_seconds()) / 3600

                    if hours_diff <= 4:  # Within 4 hours = same work session
                        strength = max(
                            0.3, 0.8 - (hours_diff / 8)
                        )  # Decay over 8 hours
                        connections.append(
                            (current.id, next_commit.id, strength, "author_session")
                        )

            return connections

        except Exception as e:
            logger.debug(f"Failed to extract author connections: {e}")
            return []
