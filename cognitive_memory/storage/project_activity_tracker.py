"""
Project activity tracking for context-aware memory decay.

This module implements project activity tracking to replace calendar-based decay
with project activity and content-type aware decay mechanisms. Tracks both git
commit patterns and memory access patterns to determine project activity levels.
"""

import time
from datetime import datetime, timedelta
from pathlib import Path

# Avoid circular import - MemoryAccessPattern will be imported at runtime
from typing import TYPE_CHECKING, Any

from loguru import logger

from ..git_analysis.history_miner import GitHistoryMiner, validate_git_repository

if TYPE_CHECKING:
    from .dual_memory import MemoryAccessPattern


class ProjectActivityTracker:
    """
    Tracks project activity based on git commits and memory access patterns.

    Provides activity-based decay rate scaling:
    - High activity (>0.7): 2.0x faster decay
    - Normal activity (0.2-0.7): 1.0x normal decay
    - Low activity (<0.2): 0.1x slower decay
    """

    def __init__(
        self,
        repository_path: str | None = None,
        activity_window_days: int = 30,
        max_commits_per_day: int = 3,
        max_accesses_per_day: int = 100,
        commit_weight: float = 0.6,
        access_weight: float = 0.4,
    ):
        """
        Initialize project activity tracker.

        Args:
            repository_path: Path to git repository for commit tracking
            activity_window_days: Number of days to analyze for activity
            max_commits_per_day: Maximum commits per day for score normalization
            max_accesses_per_day: Maximum memory accesses per day for score normalization
            commit_weight: Weight for commit activity in overall score
            access_weight: Weight for memory access activity in overall score
        """
        self.repository_path = repository_path
        self.activity_window_days = activity_window_days
        self.max_commits_per_day = max_commits_per_day
        self.max_accesses_per_day = max_accesses_per_day
        self.commit_weight = commit_weight
        self.access_weight = access_weight

        # Validate weights sum to 1.0
        if abs(self.commit_weight + self.access_weight - 1.0) > 0.01:
            logger.warning(
                "Activity weights don't sum to 1.0",
                commit_weight=commit_weight,
                access_weight=access_weight,
            )

        # Initialize git repository if path provided
        self.git_miner: GitHistoryMiner | None = None
        self.git_available = False

        if repository_path:
            self._initialize_git_repository()

        # Cache for activity calculations
        self._activity_cache: dict[
            str, tuple[float, float]
        ] = {}  # {window_key: (score, timestamp)}
        self._cache_ttl_seconds = 300  # 5 minutes cache TTL

        logger.info(
            "ProjectActivityTracker initialized",
            repository_path=repository_path,
            activity_window_days=activity_window_days,
            git_available=self.git_available,
        )

    def _initialize_git_repository(self) -> None:
        """Initialize git repository for commit tracking."""
        try:
            if self.repository_path and validate_git_repository(self.repository_path):
                self.git_miner = GitHistoryMiner(self.repository_path)
                self.git_available = self.git_miner.validate_repository()
                logger.debug("Git repository initialized for activity tracking")
            else:
                logger.warning(
                    "Git repository not available for activity tracking",
                    path=self.repository_path,
                )
        except Exception as e:
            logger.warning(
                "Failed to initialize git repository",
                path=self.repository_path,
                error=str(e),
            )
            self.git_available = False

    def calculate_git_activity_score(self, window_days: int | None = None) -> float:
        """
        Calculate git activity score based on recent commits.

        Args:
            window_days: Number of days to analyze (defaults to activity_window_days)

        Returns:
            Activity score between 0.0 and 1.0
        """
        if not self.git_available or not self.git_miner:
            return 0.0

        window_days = window_days or self.activity_window_days

        try:
            # Calculate date range
            now = datetime.now()
            since_date = now - timedelta(days=window_days)

            # Extract recent commits
            commits = list(
                self.git_miner.extract_commit_history(
                    max_commits=1000,  # Reasonable limit
                    since_date=since_date,
                )
            )

            commit_count = len(commits)

            # Calculate normalized score
            max_commits = self.max_commits_per_day * window_days
            git_score = min(1.0, commit_count / max_commits) if max_commits > 0 else 0.0

            logger.debug(
                "Git activity calculated",
                commits=commit_count,
                window_days=window_days,
                score=git_score,
            )

            return git_score

        except Exception as e:
            logger.error("Failed to calculate git activity score", error=str(e))
            return 0.0

    def calculate_memory_access_score(
        self,
        access_patterns: dict[str, "MemoryAccessPattern"],
        window_days: int | None = None,
    ) -> float:
        """
        Calculate memory access activity score.

        Args:
            access_patterns: Dictionary of memory access patterns
            window_days: Number of days to analyze (defaults to activity_window_days)

        Returns:
            Activity score between 0.0 and 1.0
        """
        window_days = window_days or self.activity_window_days
        window_hours = window_days * 24

        try:
            total_accesses = 0

            for pattern in access_patterns.values():
                # Calculate accesses within window
                recent_accesses = pattern.calculate_access_frequency(window_hours)
                total_accesses += int(
                    recent_accesses * window_hours
                )  # Convert back to count

            # Calculate normalized score
            max_accesses = self.max_accesses_per_day * window_days
            access_score = (
                min(1.0, total_accesses / max_accesses) if max_accesses > 0 else 0.0
            )

            logger.debug(
                "Memory access activity calculated",
                total_accesses=total_accesses,
                window_days=window_days,
                score=access_score,
            )

            return access_score

        except Exception as e:
            logger.error("Failed to calculate memory access score", error=str(e))
            return 0.0

    def calculate_activity_score(
        self,
        access_patterns: dict[str, "MemoryAccessPattern"] | None = None,
        window_days: int | None = None,
    ) -> float:
        """
        Calculate overall project activity score.

        Combines git commit activity and memory access activity using weighted average.

        Args:
            access_patterns: Dictionary of memory access patterns
            window_days: Number of days to analyze

        Returns:
            Overall activity score between 0.0 and 1.0
        """
        window_days = window_days or self.activity_window_days

        # Check cache first
        cache_key = f"{window_days}_{len(access_patterns or {})}"
        current_time = time.time()

        if cache_key in self._activity_cache:
            cached_score, cache_time = self._activity_cache[cache_key]
            if current_time - cache_time < self._cache_ttl_seconds:
                logger.debug("Using cached activity score", score=cached_score)
                return cached_score

        try:
            # Calculate component scores
            git_score = self.calculate_git_activity_score(window_days)
            access_score = self.calculate_memory_access_score(
                access_patterns or {}, window_days
            )

            # Weighted combination
            activity_score = (
                self.commit_weight * git_score + self.access_weight * access_score
            )

            # Cache the result
            self._activity_cache[cache_key] = (activity_score, current_time)

            logger.debug(
                "Overall activity score calculated",
                git_score=git_score,
                access_score=access_score,
                activity_score=activity_score,
                window_days=window_days,
            )

            return activity_score

        except Exception as e:
            logger.error("Failed to calculate activity score", error=str(e))
            return 0.0

    def get_dynamic_decay_rate(
        self,
        base_decay_rate: float,
        access_patterns: dict[str, "MemoryAccessPattern"] | None = None,
    ) -> float:
        """
        Get dynamic decay rate based on project activity.

        Activity-based scaling:
        - High activity (>0.7): 2.0x faster decay
        - Normal activity (0.2-0.7): 1.0x normal decay
        - Low activity (<0.2): 0.1x slower decay

        Args:
            base_decay_rate: Base decay rate to scale
            access_patterns: Memory access patterns for activity calculation

        Returns:
            Scaled decay rate
        """
        try:
            activity_score = self.calculate_activity_score(access_patterns)

            # Determine activity multiplier
            if activity_score > 0.7:
                # High activity - faster decay
                multiplier = 2.0
                activity_level = "high"
            elif activity_score > 0.2:
                # Normal activity - normal decay
                multiplier = 1.0
                activity_level = "normal"
            else:
                # Low activity - slower decay
                multiplier = 0.1
                activity_level = "low"

            scaled_rate = base_decay_rate * multiplier

            logger.debug(
                "Dynamic decay rate calculated",
                activity_score=activity_score,
                activity_level=activity_level,
                multiplier=multiplier,
                base_rate=base_decay_rate,
                scaled_rate=scaled_rate,
            )

            return scaled_rate

        except Exception as e:
            logger.error("Failed to calculate dynamic decay rate", error=str(e))
            return base_decay_rate  # Fallback to base rate

    def clear_cache(self) -> None:
        """Clear the activity calculation cache."""
        self._activity_cache.clear()
        logger.debug("Activity cache cleared")

    def get_activity_stats(self) -> dict[str, Any]:
        """
        Get comprehensive activity tracking statistics.

        Returns:
            Dictionary containing activity statistics
        """
        try:
            stats = {
                "repository_path": self.repository_path,
                "git_available": self.git_available,
                "activity_window_days": self.activity_window_days,
                "max_commits_per_day": self.max_commits_per_day,
                "max_accesses_per_day": self.max_accesses_per_day,
                "commit_weight": self.commit_weight,
                "access_weight": self.access_weight,
                "cache_entries": len(self._activity_cache),
            }

            # Add git repository stats if available
            if self.git_available and self.git_miner:
                try:
                    git_stats = self.git_miner.get_repository_stats()
                    stats["git_stats"] = git_stats  # type: ignore
                except Exception as e:
                    logger.debug("Failed to get git stats", error=str(e))

            return stats

        except Exception as e:
            logger.error("Failed to get activity stats", error=str(e))
            return {"error": str(e)}

    def close(self) -> None:
        """Clean up resources."""
        if self.git_miner:
            try:
                self.git_miner.close()
                logger.debug("Git miner closed")
            except Exception as e:
                logger.warning("Error closing git miner", error=str(e))
            finally:
                self.git_miner = None

        self.clear_cache()


def create_project_activity_tracker(
    repository_path: str | None = None, **kwargs: Any
) -> ProjectActivityTracker:
    """
    Factory function to create ProjectActivityTracker.

    Args:
        repository_path: Path to git repository
        **kwargs: Additional configuration parameters

    Returns:
        ProjectActivityTracker instance
    """
    try:
        # Auto-detect repository path if not provided
        if repository_path is None:
            current_dir = Path.cwd()
            git_dir = current_dir / ".git"
            if git_dir.exists():
                repository_path = str(current_dir)
                logger.debug("Auto-detected git repository", path=repository_path)

        return ProjectActivityTracker(repository_path, **kwargs)

    except Exception as e:
        logger.error("Failed to create ProjectActivityTracker", error=str(e))
        raise
