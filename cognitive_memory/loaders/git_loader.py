"""
Git repository memory loader for the cognitive memory system.

This module implements a MemoryLoader for git repositories, extracting development
patterns and converting them into cognitive memories with deterministic IDs for
upsert operations and seamless integration with the memory pipeline.
"""

from pathlib import Path
from typing import Any

from loguru import logger

from ..core.config import CognitiveConfig
from ..core.interfaces import MemoryLoader
from ..core.memory import CognitiveMemory
from ..git_analysis import (
    GitHistoryMiner,
    GitPatternEmbedder,
    GitPatternIDGenerator,
    PatternDetector,
    validate_repository_path,
)


class GitHistoryLoader(MemoryLoader):
    """
    Memory loader for git repositories.

    Implements git pattern extraction, natural language embedding, and
    cognitive memory creation with deterministic IDs for update operations.
    Integrates with existing memory pipeline for seamless storage and retrieval.
    """

    def __init__(self, config: CognitiveConfig, cognitive_system: Any = None):
        """
        Initialize the git history loader.

        Args:
            config: Cognitive configuration parameters
            cognitive_system: Optional CognitiveSystem instance for upsert operations
        """
        self.config = config
        self.cognitive_system = cognitive_system

        # Initialize git analysis components
        # GitHistoryMiner will be initialized per-repository in load_from_source()
        self.pattern_detector = PatternDetector(
            min_confidence=0.3,  # Configurable minimum confidence
            recency_days=365,  # Consider last year for recency weighting
        )
        self.pattern_embedder = GitPatternEmbedder(max_tokens=400)
        self.id_generator = GitPatternIDGenerator()

        logger.info("GitHistoryLoader initialized with git analysis pipeline")

    def load_from_source(
        self, source_path: str, **kwargs: Any
    ) -> list[CognitiveMemory]:
        """
        Load cognitive memories from a git repository.

        Extracts development patterns using git history analysis and converts
        them into cognitive memories with proper L0/L1/L2 classification.

        Args:
            source_path: Path to the git repository
            **kwargs: Additional parameters (time_window, min_support, etc.)

        Returns:
            List of CognitiveMemory objects created from git patterns
        """
        if not self.validate_source(source_path):
            raise ValueError(f"Invalid git repository: {source_path}")

        logger.info(f"Loading git patterns from {source_path}")

        # Extract configuration from kwargs
        min_support = kwargs.get("min_support", 3)

        try:
            # Initialize history miner for this repository
            history_miner = GitHistoryMiner(source_path)

            # Step 1: Extract commit history and problem commits
            commits = list(history_miner.extract_commit_history(max_commits=1000))
            # Note: extract_problem_commits method doesn't exist in GitHistoryMiner
            # Using empty list for now - this needs to be implemented
            problem_commits: list[Any] = []

            logger.info(
                f"Extracted {len(commits)} commits, {len(problem_commits)} problem commits"
            )

            # Step 2: Detect patterns using pattern detector
            cochange_patterns = self.pattern_detector.detect_cochange_patterns(
                commits, min_support=min_support
            )
            hotspot_patterns = self.pattern_detector.detect_maintenance_hotspots(
                commits, problem_commits
            )
            solution_patterns = self.pattern_detector.detect_solution_patterns(
                problem_commits
            )

            logger.info(
                f"Detected {len(cochange_patterns)} co-change, "
                f"{len(hotspot_patterns)} hotspot, "
                f"{len(solution_patterns)} solution patterns"
            )

            # Step 3: Convert patterns to cognitive memories
            memories = []

            # Process co-change patterns (L1 - Contexts)
            for pattern in cochange_patterns:
                memory = self._create_cochange_memory(pattern, source_path)
                memories.append(memory)

            # Process hotspot patterns (L1 - Contexts)
            for pattern in hotspot_patterns:
                memory = self._create_hotspot_memory(pattern, source_path)
                memories.append(memory)

            # Process solution patterns (L2 - Episodes)
            for pattern in solution_patterns:
                memory = self._create_solution_memory(pattern, source_path)
                memories.append(memory)

            logger.info(f"Created {len(memories)} cognitive memories from git patterns")
            return memories

        except Exception as e:
            logger.error(f"Failed to load git patterns from {source_path}: {e}")
            raise

    def extract_connections(
        self, memories: list[CognitiveMemory]
    ) -> list[tuple[str, str, float, str]]:
        """
        Extract connections between git pattern memories.

        Identifies relationships between patterns based on shared files,
        problem types, and solution approaches.

        Args:
            memories: List of memories to analyze for connections

        Returns:
            List of tuples: (source_id, target_id, strength, connection_type)
        """
        connections = []

        try:
            # Group memories by pattern type for efficient analysis
            cochange_memories = []
            hotspot_memories = []
            solution_memories = []

            for memory in memories:
                pattern_type = memory.metadata.get("pattern_type")
                if pattern_type == "cochange":
                    cochange_memories.append(memory)
                elif pattern_type == "hotspot":
                    hotspot_memories.append(memory)
                elif pattern_type == "solution":
                    solution_memories.append(memory)

            # Extract file-based connections (co-change to hotspot)
            file_connections = self._extract_file_connections(
                cochange_memories, hotspot_memories
            )
            connections.extend(file_connections)

            # Extract problem-solution connections
            problem_solution_connections = self._extract_problem_solution_connections(
                hotspot_memories, solution_memories
            )
            connections.extend(problem_solution_connections)

            # Extract co-change pattern connections (overlapping files)
            cochange_connections = self._extract_cochange_connections(cochange_memories)
            connections.extend(cochange_connections)

            # Filter by strength threshold
            filtered_connections = [
                conn
                for conn in connections
                if conn[2] >= 0.3  # Minimum strength
            ]

            logger.info(
                f"Extracted {len(filtered_connections)} connections "
                f"(filtered from {len(connections)} total)"
            )

            return filtered_connections

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

    def upsert_memories(self, memories: list[CognitiveMemory]) -> bool:
        """
        Update existing memories or insert new ones using deterministic IDs.

        Uses the deterministic pattern IDs to identify existing memories
        and perform proper upsert operations through the cognitive system.

        Args:
            memories: List of memories to upsert

        Returns:
            True if all operations succeeded, False otherwise
        """
        if not self.cognitive_system:
            logger.error(
                "No cognitive_system provided to GitHistoryLoader for upsert operations"
            )
            return False

        try:
            # Use cognitive system's upsert capability
            result = self.cognitive_system.upsert_memories(memories)

            # Check if upsert was successful
            if isinstance(result, dict):
                success = result.get("success", False)
                if success:
                    logger.info(
                        f"Successfully upserted {len(memories)} git pattern memories"
                    )
                    return True
                else:
                    logger.error(
                        f"Upsert failed: {result.get('error', 'Unknown error')}"
                    )
                    return False
            else:
                # Fallback to individual store operations if upsert not implemented
                logger.warning(
                    "Cognitive system upsert not implemented, falling back to store"
                )
                for memory in memories:
                    success = self.cognitive_system.store_memory(memory)
                    if not success:
                        logger.error(f"Failed to store memory: {memory.id}")
                        return False

                logger.info(f"Successfully stored {len(memories)} git pattern memories")
                return True

        except Exception as e:
            logger.error(f"Upsert operation failed: {e}")
            return False

    def _create_cochange_memory(
        self, pattern: dict[str, Any], source_path: str
    ) -> CognitiveMemory:
        """Create CognitiveMemory from co-change pattern."""
        # Generate deterministic ID
        memory_id = self.id_generator.generate_cochange_id(
            pattern["file_a"], pattern["file_b"]
        )

        # Generate natural language content
        content = self.pattern_embedder.embed_cochange_pattern(pattern)

        # Classify as L1 (Context) - moderate detail co-change information
        hierarchy_level = 1

        return CognitiveMemory(
            id=memory_id,
            content=content,
            hierarchy_level=hierarchy_level,
            strength=min(1.0, pattern.get("confidence_score", 0.5)),
            metadata={
                "pattern_type": "cochange",
                "source_path": source_path,
                "file_a": pattern["file_a"],
                "file_b": pattern["file_b"],
                "support_count": pattern.get("support_count", 0),
                "confidence_score": pattern.get("confidence_score", 0.0),
                "quality_rating": pattern.get("quality_rating", "unknown"),
                "loader_type": "git",
                "git_pattern_version": "1.0",
            },
        )

    def _create_hotspot_memory(
        self, pattern: dict[str, Any], source_path: str
    ) -> CognitiveMemory:
        """Create CognitiveMemory from maintenance hotspot pattern."""
        # Generate deterministic ID
        memory_id = self.id_generator.generate_hotspot_id(pattern["file_path"])

        # Generate natural language content
        content = self.pattern_embedder.embed_hotspot_pattern(pattern)

        # Classify as L1 (Context) - maintenance information with moderate detail
        hierarchy_level = 1

        return CognitiveMemory(
            id=memory_id,
            content=content,
            hierarchy_level=hierarchy_level,
            strength=min(1.0, pattern.get("hotspot_score", 0.5)),
            metadata={
                "pattern_type": "hotspot",
                "source_path": source_path,
                "file_path": pattern["file_path"],
                "problem_frequency": pattern.get("problem_frequency", 0),
                "hotspot_score": pattern.get("hotspot_score", 0.0),
                "trend_direction": pattern.get("trend_direction", "unknown"),
                "recent_problems": pattern.get("recent_problems", []),
                "loader_type": "git",
                "git_pattern_version": "1.0",
            },
        )

    def _create_solution_memory(
        self, pattern: dict[str, Any], source_path: str
    ) -> CognitiveMemory:
        """Create CognitiveMemory from solution pattern."""
        # Generate deterministic ID
        memory_id = self.id_generator.generate_solution_id(
            pattern["problem_type"], pattern["solution_approach"]
        )

        # Generate natural language content
        content = self.pattern_embedder.embed_solution_pattern(pattern)

        # Classify as L2 (Episode) - specific fix examples with full context
        hierarchy_level = 2

        return CognitiveMemory(
            id=memory_id,
            content=content,
            hierarchy_level=hierarchy_level,
            strength=min(1.0, pattern.get("applicability_confidence", 0.5)),
            metadata={
                "pattern_type": "solution",
                "source_path": source_path,
                "problem_type": pattern["problem_type"],
                "solution_approach": pattern["solution_approach"],
                "success_rate": pattern.get("success_rate", 0.0),
                "applicability_confidence": pattern.get(
                    "applicability_confidence", 0.0
                ),
                "example_fixes": pattern.get("example_fixes", []),
                "loader_type": "git",
                "git_pattern_version": "1.0",
            },
        )

    def _extract_file_connections(
        self,
        cochange_memories: list[CognitiveMemory],
        hotspot_memories: list[CognitiveMemory],
    ) -> list[tuple[str, str, float, str]]:
        """Extract connections between co-change patterns and hotspots based on shared files."""
        connections = []

        for cochange_memory in cochange_memories:
            file_a = cochange_memory.metadata.get("file_a", "")
            file_b = cochange_memory.metadata.get("file_b", "")

            for hotspot_memory in hotspot_memories:
                hotspot_file = hotspot_memory.metadata.get("file_path", "")

                # Check if hotspot file matches either co-change file
                if hotspot_file in [file_a, file_b]:
                    # Connection strength based on both pattern confidences
                    cochange_confidence = cochange_memory.metadata.get(
                        "confidence_score", 0.0
                    )
                    hotspot_score = hotspot_memory.metadata.get("hotspot_score", 0.0)
                    strength = (cochange_confidence + hotspot_score) / 2.0

                    connections.append(
                        (
                            cochange_memory.id,
                            hotspot_memory.id,
                            strength,
                            "file_relationship",
                        )
                    )

        return connections

    def _extract_problem_solution_connections(
        self,
        hotspot_memories: list[CognitiveMemory],
        solution_memories: list[CognitiveMemory],
    ) -> list[tuple[str, str, float, str]]:
        """Extract connections between hotspots and solution patterns based on problem types."""
        connections = []

        for hotspot_memory in hotspot_memories:
            recent_problems = hotspot_memory.metadata.get("recent_problems", [])

            for solution_memory in solution_memories:
                solution_problem_type = solution_memory.metadata.get("problem_type", "")

                # Check if solution addresses any of the hotspot's recent problems
                if solution_problem_type in recent_problems:
                    # Connection strength based on hotspot score and solution confidence
                    hotspot_score = hotspot_memory.metadata.get("hotspot_score", 0.0)
                    solution_confidence = solution_memory.metadata.get(
                        "applicability_confidence", 0.0
                    )
                    strength = (hotspot_score + solution_confidence) / 2.0

                    connections.append(
                        (
                            hotspot_memory.id,
                            solution_memory.id,
                            strength,
                            "problem_solution",
                        )
                    )

        return connections

    def _extract_cochange_connections(
        self, cochange_memories: list[CognitiveMemory]
    ) -> list[tuple[str, str, float, str]]:
        """Extract connections between co-change patterns with overlapping files."""
        connections = []

        for i, memory1 in enumerate(cochange_memories):
            for memory2 in cochange_memories[i + 1 :]:
                # Get files from both patterns
                files1 = {
                    memory1.metadata.get("file_a", ""),
                    memory1.metadata.get("file_b", ""),
                }
                files2 = {
                    memory2.metadata.get("file_a", ""),
                    memory2.metadata.get("file_b", ""),
                }

                # Check for file overlap
                overlap = files1.intersection(files2)
                if overlap:
                    # Connection strength based on both pattern confidences
                    confidence1 = memory1.metadata.get("confidence_score", 0.0)
                    confidence2 = memory2.metadata.get("confidence_score", 0.0)
                    strength = (confidence1 + confidence2) / 2.0

                    connections.append(
                        (memory1.id, memory2.id, strength, "cochange_overlap")
                    )

        return connections
