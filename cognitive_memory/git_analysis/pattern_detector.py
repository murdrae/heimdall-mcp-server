"""
Git pattern detection algorithms with confidence scoring.

This module implements core pattern detection algorithms for git repository analysis,
including co-change pattern detection, maintenance hotspot identification, and
solution pattern mining with statistical confidence scoring.

Pattern Types:
- Co-change Patterns: Files that frequently change together
- Maintenance Hotspots: Files with high problem frequency
- Solution Patterns: Successful problem-solving approaches

All algorithms include confidence scoring and recency weighting for reliable
pattern identification and quality filtering.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from loguru import logger
from scipy.stats import chi2_contingency

from .data_structures import CommitEvent, ProblemCommit
from .security import canonicalize_path


class PatternDetector:
    """Core pattern detection algorithms with confidence scoring.

    Implements statistical pattern analysis for git repository data,
    with comprehensive confidence scoring and quality filtering.

    Features:
    - Co-change pattern detection with statistical significance
    - Maintenance hotspot identification with trend analysis
    - Solution pattern mining with success rate calculation
    - Recency weighting and quality filtering
    """

    def __init__(self, min_confidence: float = 0.3, recency_days: int = 365):
        """Initialize pattern detector with configuration.

        Args:
            min_confidence: Minimum confidence threshold for patterns
            recency_days: Days to consider for recency weighting
        """
        self.min_confidence = max(0.0, min(1.0, min_confidence))
        self.recency_days = max(1, recency_days)
        logger.info(
            "PatternDetector initialized",
            min_confidence=self.min_confidence,
            recency_days=self.recency_days,
        )

    def detect_cochange_patterns(
        self, commits: list[CommitEvent], min_support: int = 3
    ) -> list[dict[str, Any]]:
        """Detect co-change patterns with statistical confidence.

        Analyzes commit history to identify files that frequently change
        together, using co-occurrence matrix analysis and statistical
        significance testing.

        Args:
            commits: List of commit events to analyze
            min_support: Minimum co-change occurrences required

        Returns:
            List of co-change pattern dictionaries with confidence scores
        """
        try:
            logger.info(
                "Starting co-change pattern detection",
                commit_count=len(commits),
                min_support=min_support,
            )

            # Build co-occurrence matrix
            cochange_matrix = self._build_cochange_matrix(commits)

            # Calculate file change frequencies
            file_frequencies = self._calculate_file_frequencies(commits)

            patterns = []
            now = datetime.now()

            # Analyze all file pairs
            for (file_a, file_b), cochange_count in cochange_matrix.items():
                if cochange_count < min_support:
                    continue

                # Calculate support and confidence
                support = cochange_count
                total_opportunities = len(commits)

                # Calculate confidence using formula: support / (support + 2) * recency_weight
                base_confidence = support / (support + 2)

                # Calculate recency weight
                recency_weight = self._calculate_recency_weight(
                    commits, file_a, file_b, now
                )

                confidence_score = base_confidence * recency_weight

                # Apply minimum confidence filter
                if confidence_score < self.min_confidence:
                    continue

                # Statistical significance test
                statistical_significance = self._test_cochange_significance(
                    file_a,
                    file_b,
                    cochange_count,
                    file_frequencies,
                    total_opportunities,
                )

                # Quality rating based on confidence and significance
                quality_rating = self._calculate_quality_rating(
                    confidence_score, statistical_significance
                )

                pattern = {
                    "file_a": file_a,
                    "file_b": file_b,
                    "support_count": support,
                    "confidence_score": confidence_score,
                    "recency_weight": recency_weight,
                    "quality_rating": quality_rating,
                    "statistical_significance": statistical_significance,
                    "total_opportunities": total_opportunities,
                }

                patterns.append(pattern)

            # Sort by confidence score descending
            patterns.sort(
                key=lambda x: float(x["confidence_score"])
                if isinstance(x["confidence_score"], int | float | str)
                else 0.0,
                reverse=True,
            )

            logger.info(
                "Co-change pattern detection completed",
                patterns_found=len(patterns),
                min_confidence=self.min_confidence,
            )

            return patterns

        except Exception as e:
            logger.error("Co-change pattern detection failed", error=str(e))
            return []

    def detect_maintenance_hotspots(
        self, commits: list[CommitEvent], problem_commits: list[ProblemCommit]
    ) -> list[dict[str, Any]]:
        """Detect maintenance hotspots with trend analysis.

        Identifies files with high problem frequency and analyzes
        trends over time to determine maintenance risk.

        Args:
            commits: List of all commit events
            problem_commits: List of problem-fixing commits

        Returns:
            List of maintenance hotspot dictionaries with scores
        """
        try:
            logger.info(
                "Starting maintenance hotspot detection",
                total_commits=len(commits),
                problem_commits=len(problem_commits),
            )

            # Build problem frequency map
            problem_frequency: defaultdict[str, int] = defaultdict(int)
            file_problem_history = defaultdict(list)

            # Create problem commit hash set for fast lookup
            problem_hashes = {pc.commit_hash for pc in problem_commits}

            # Track problem occurrences per file
            for commit in commits:
                if commit.hash in problem_hashes:
                    # Find corresponding problem commit
                    problem_commit = next(
                        (pc for pc in problem_commits if pc.commit_hash == commit.hash),
                        None,
                    )

                    if problem_commit:
                        for file_path in problem_commit.affected_files:
                            canonical_path = canonicalize_path(file_path)
                            problem_frequency[canonical_path] += 1
                            file_problem_history[canonical_path].append(
                                commit.timestamp
                            )

            # Calculate file change frequencies
            file_change_counts: defaultdict[str, int] = defaultdict(int)
            for commit in commits:
                for file_path in commit.files:
                    canonical_path = canonicalize_path(file_path)
                    file_change_counts[canonical_path] += 1

            hotspots = []
            now = datetime.now()

            # Analyze each file with problems
            for file_path, problem_count in problem_frequency.items():
                if problem_count == 0:
                    continue

                total_changes = file_change_counts.get(file_path, 0)
                if total_changes == 0:
                    continue

                # Calculate hotspot score: problem_frequency / total_commits * consistency_factor
                base_score = problem_count / total_changes

                # Calculate consistency factor (problems spread over time vs clustered)
                consistency_factor = self._calculate_consistency_factor(
                    file_problem_history[file_path]
                )

                hotspot_score = base_score * consistency_factor

                # Calculate trend direction
                trend_direction = self._calculate_trend_direction(
                    file_problem_history[file_path], now
                )

                # Get recent problems
                recent_problems = self._get_recent_problems(
                    file_path, problem_commits, now
                )

                # Apply minimum score filter
                if hotspot_score < 0.1:  # Minimum 10% problem rate
                    continue

                hotspot = {
                    "file_path": file_path,
                    "problem_frequency": problem_count,
                    "hotspot_score": hotspot_score,
                    "trend_direction": trend_direction,
                    "recent_problems": recent_problems,
                    "total_changes": total_changes,
                    "consistency_factor": consistency_factor,
                }

                hotspots.append(hotspot)

            # Sort by hotspot score descending
            hotspots.sort(
                key=lambda x: float(x["hotspot_score"])
                if isinstance(x["hotspot_score"], int | float | str)
                else 0.0,
                reverse=True,
            )

            logger.info(
                "Maintenance hotspot detection completed",
                hotspots_found=len(hotspots),
            )

            return hotspots

        except Exception as e:
            logger.error("Maintenance hotspot detection failed", error=str(e))
            return []

    def detect_solution_patterns(
        self, problem_commits: list[ProblemCommit]
    ) -> list[dict[str, Any]]:
        """Detect solution patterns with success rate calculation.

        Analyzes problem-fixing commits to identify successful
        solution approaches with statistical validation.

        Args:
            problem_commits: List of problem-fixing commits

        Returns:
            List of solution pattern dictionaries with success rates
        """
        try:
            logger.info(
                "Starting solution pattern detection",
                problem_commits=len(problem_commits),
            )

            # Group problems by type and extract solution approaches
            problem_types = defaultdict(list)
            solution_approaches: defaultdict[str, int] = defaultdict(int)
            solution_examples: defaultdict[str, list[str]] = defaultdict(list)

            for problem_commit in problem_commits:
                problem_type = self._extract_problem_type(problem_commit.problem_type)
                solution_approach = self._extract_solution_approach(
                    problem_commit.fix_description
                )

                if problem_type and solution_approach:
                    problem_types[problem_type].append(problem_commit)

                    # Track solution approach usage
                    approach_key = f"{problem_type}::{solution_approach}"
                    solution_approaches[approach_key] += 1

                    # Store examples (limit to prevent memory issues)
                    if len(solution_examples[approach_key]) < 10:
                        solution_examples[approach_key].append(
                            problem_commit.commit_hash
                        )

            patterns = []

            # Analyze solution patterns
            for approach_key, usage_count in solution_approaches.items():
                if usage_count < 2:  # Need at least 2 examples
                    continue

                problem_type, solution_approach = approach_key.split("::", 1)

                # Calculate success rate
                total_attempts = len(problem_types[problem_type])
                success_rate = (
                    usage_count / total_attempts if total_attempts > 0 else 0.0
                )

                # Calculate applicability confidence
                applicability_confidence = self._calculate_applicability_confidence(
                    usage_count, total_attempts
                )

                # Apply minimum confidence filter
                if applicability_confidence < self.min_confidence:
                    continue

                pattern = {
                    "problem_type": problem_type,
                    "solution_approach": solution_approach,
                    "success_rate": success_rate,
                    "applicability_confidence": applicability_confidence,
                    "example_fixes": solution_examples[approach_key],
                    "usage_count": usage_count,
                    "total_attempts": total_attempts,
                }

                patterns.append(pattern)

            # Sort by applicability confidence descending
            patterns.sort(
                key=lambda x: float(x["applicability_confidence"])
                if isinstance(x["applicability_confidence"], int | float | str)
                else 0.0,
                reverse=True,
            )

            logger.info(
                "Solution pattern detection completed",
                patterns_found=len(patterns),
            )

            return patterns

        except Exception as e:
            logger.error("Solution pattern detection failed", error=str(e))
            return []

    def _build_cochange_matrix(
        self, commits: list[CommitEvent]
    ) -> dict[tuple[str, str], int]:
        """Build co-occurrence matrix for file changes."""
        cochange_matrix: defaultdict[tuple[str, str], int] = defaultdict(int)

        for commit in commits:
            if len(commit.files) < 2:
                continue  # Need at least 2 files for co-change

            # Canonicalize all file paths
            canonical_files = [canonicalize_path(f) for f in commit.files]
            canonical_files = list(set(canonical_files))  # Remove duplicates

            # Generate all pairs
            for i, file_a in enumerate(canonical_files):
                for file_b in canonical_files[i + 1 :]:
                    # Ensure consistent ordering for deterministic results
                    pair = (file_a, file_b) if file_a < file_b else (file_b, file_a)
                    cochange_matrix[pair] += 1

        return dict(cochange_matrix)

    def _calculate_file_frequencies(self, commits: list[CommitEvent]) -> dict[str, int]:
        """Calculate individual file change frequencies."""
        frequencies: defaultdict[str, int] = defaultdict(int)

        for commit in commits:
            for file_path in commit.files:
                canonical_path = canonicalize_path(file_path)
                frequencies[canonical_path] += 1

        return frequencies

    def _calculate_recency_weight(
        self, commits: list[CommitEvent], file_a: str, file_b: str, now: datetime
    ) -> float:
        """Calculate recency weight for co-change pattern."""
        try:
            # Find most recent co-change
            most_recent = None

            for commit in commits:
                canonical_files = [canonicalize_path(f) for f in commit.files]
                if file_a in canonical_files and file_b in canonical_files:
                    if most_recent is None or commit.timestamp > most_recent:
                        most_recent = commit.timestamp

            if most_recent is None:
                return 0.1  # Very low weight if no co-change found

            # Calculate days since most recent co-change
            days_since = (now - most_recent).days

            # Exponential decay with configurable period
            recency_weight = np.exp(-days_since / self.recency_days)

            return float(
                max(0.1, min(1.0, recency_weight))
            )  # Clamp between 0.1 and 1.0

        except Exception:
            return 0.5  # Default weight if calculation fails

    def _test_cochange_significance(
        self,
        file_a: str,
        file_b: str,
        cochange_count: int,
        file_frequencies: dict[str, int],
        total_commits: int,
    ) -> float:
        """Test statistical significance of co-change pattern using Chi-square."""
        try:
            freq_a = file_frequencies.get(file_a, 0)
            freq_b = file_frequencies.get(file_b, 0)

            if freq_a == 0 or freq_b == 0 or total_commits == 0:
                return 0.0

            # Build contingency table
            # [both_changed, a_only]
            # [b_only, neither]
            both_changed = cochange_count
            a_only = freq_a - both_changed
            b_only = freq_b - both_changed
            neither = total_commits - freq_a - freq_b + both_changed

            # Ensure non-negative values
            a_only = max(0, a_only)
            b_only = max(0, b_only)
            neither = max(0, neither)

            contingency_table = np.array([[both_changed, a_only], [b_only, neither]])

            # Perform Chi-square test
            if np.any(contingency_table == 0):
                return 0.0  # Cannot compute chi-square with zeros

            chi2, p_value, dof, expected = chi2_contingency(contingency_table)

            # Convert p-value to significance score (lower p-value = higher significance)
            significance = 1.0 - p_value if p_value < 1.0 else 0.0

            return max(0.0, min(1.0, significance))

        except Exception:
            return 0.0  # Default to no significance if calculation fails

    def _calculate_quality_rating(self, confidence: float, significance: float) -> str:
        """Calculate quality rating based on confidence and statistical significance."""
        combined_score = (confidence + significance) / 2.0

        if combined_score >= 0.8:
            return "high"
        elif combined_score >= 0.6:
            return "medium"
        elif combined_score >= 0.4:
            return "low"
        else:
            return "very_low"

    def _calculate_consistency_factor(
        self, problem_timestamps: list[datetime]
    ) -> float:
        """Calculate consistency factor for maintenance hotspots."""
        try:
            if len(problem_timestamps) < 2:
                return 1.0

            # Sort timestamps
            sorted_timestamps = sorted(problem_timestamps)

            # Calculate time intervals between problems
            intervals = []
            for i in range(1, len(sorted_timestamps)):
                interval = (sorted_timestamps[i] - sorted_timestamps[i - 1]).days
                intervals.append(interval)

            if not intervals:
                return 1.0

            # Calculate coefficient of variation (std/mean)
            mean_interval = np.mean(intervals)
            std_interval = np.std(intervals)

            if mean_interval == 0:
                return 1.0

            cv = std_interval / mean_interval

            # Convert to consistency factor (lower CV = higher consistency)
            consistency_factor = 1.0 / (1.0 + cv)

            return float(max(0.1, min(1.0, consistency_factor)))

        except Exception:
            return 0.5  # Default consistency factor

    def _calculate_trend_direction(
        self, problem_timestamps: list[datetime], now: datetime
    ) -> str:
        """Calculate trend direction for maintenance hotspots."""
        try:
            if len(problem_timestamps) < 2:
                return "stable"

            # Divide into recent and older periods
            recent_cutoff = now - timedelta(days=self.recency_days // 2)

            recent_problems = sum(1 for ts in problem_timestamps if ts >= recent_cutoff)
            older_problems = len(problem_timestamps) - recent_problems

            # Calculate rates (problems per day)
            recent_days = self.recency_days // 2
            older_days = self.recency_days - recent_days

            recent_rate = recent_problems / recent_days if recent_days > 0 else 0
            older_rate = older_problems / older_days if older_days > 0 else 0

            # Determine trend
            if recent_rate > older_rate * 1.5:
                return "increasing"
            elif recent_rate < older_rate * 0.5:
                return "decreasing"
            else:
                return "stable"

        except Exception:
            return "unknown"

    def _get_recent_problems(
        self, file_path: str, problem_commits: list[ProblemCommit], now: datetime
    ) -> list[str]:
        """Get recent problem types for a file."""
        try:
            recent_cutoff = now - timedelta(days=90)  # Last 3 months
            recent_problems = []

            for problem_commit in problem_commits:
                if (
                    file_path in problem_commit.affected_files
                    and hasattr(problem_commit, "timestamp")
                    and problem_commit.timestamp >= recent_cutoff
                ):
                    recent_problems.append(problem_commit.problem_type)

            # Remove duplicates and limit to 10 most recent
            return list(set(recent_problems))[:10]

        except Exception:
            return []

    def _extract_problem_type(self, problem_description: str) -> str:
        """Extract standardized problem type from description."""
        if not problem_description:
            return "unknown"

        problem_lower = problem_description.lower()

        # Define problem type patterns
        problem_patterns = {
            "bug": ["bug", "error", "exception", "crash", "fail"],
            "performance": ["performance", "slow", "timeout", "memory", "cpu"],
            "security": ["security", "vulnerability", "exploit", "xss", "injection"],
            "compatibility": ["compatibility", "version", "deprecat", "upgrade"],
            "ui": ["ui", "interface", "display", "render", "visual"],
            "data": ["data", "database", "migration", "corrupt", "loss"],
            "test": ["test", "testing", "spec", "assertion", "mock"],
            "build": ["build", "compile", "deploy", "package", "install"],
        }

        # Find matching pattern
        for problem_type, keywords in problem_patterns.items():
            if any(keyword in problem_lower for keyword in keywords):
                return problem_type

        return "other"

    def _extract_solution_approach(self, fix_description: str) -> str:
        """Extract standardized solution approach from fix description."""
        if not fix_description:
            return "unknown"

        fix_lower = fix_description.lower()

        # Define solution approach patterns
        solution_patterns = {
            "refactor": ["refactor", "restructure", "reorganize"],
            "validation": ["validat", "check", "verify", "sanitiz"],
            "error_handling": ["try", "catch", "exception", "handle", "guard"],
            "optimization": ["optimiz", "improve", "speed", "efficient"],
            "configuration": ["config", "setting", "parameter", "environment"],
            "update": ["update", "upgrade", "patch", "version"],
            "add_feature": ["add", "implement", "create", "new"],
            "remove": ["remove", "delete", "clean", "prune"],
            "fix_logic": ["fix", "correct", "adjust", "modify"],
        }

        # Find matching pattern
        for approach, keywords in solution_patterns.items():
            if any(keyword in fix_lower for keyword in keywords):
                return approach

        return "generic_fix"

    def _calculate_applicability_confidence(
        self, usage_count: int, total_attempts: int
    ) -> float:
        """Calculate applicability confidence for solution patterns."""
        try:
            if total_attempts == 0:
                return 0.0

            # Base confidence from success rate
            success_rate = usage_count / total_attempts

            # Adjust for sample size (more attempts = higher confidence)
            sample_size_factor = min(
                1.0, total_attempts / 10.0
            )  # Max confidence at 10+ attempts

            # Wilson score interval for confidence
            # Provides better confidence estimation for small samples
            if total_attempts < 30:
                z = 1.96  # 95% confidence
                p = success_rate
                n = total_attempts

                denominator = 1 + z * z / n
                center = (p + z * z / (2 * n)) / denominator
                error = z * np.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator

                confidence = max(0.0, center - error)
            else:
                confidence = success_rate * sample_size_factor

            return float(max(0.0, min(1.0, confidence)))

        except Exception:
            return 0.0
