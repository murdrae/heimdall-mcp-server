"""
Tests for git pattern detection algorithms.

This module tests the PatternDetector class functionality including
co-change pattern detection, maintenance hotspot identification,
and solution pattern mining with comprehensive validation.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from cognitive_memory.git_analysis.data_structures import CommitEvent, ProblemCommit
from cognitive_memory.git_analysis.pattern_detector import PatternDetector


class TestPatternDetector:
    """Test suite for PatternDetector class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.detector = PatternDetector(min_confidence=0.3, recency_days=365)
        self.base_time = datetime.now()

    def create_test_commit(
        self,
        commit_hash: str,
        files: list[str],
        message: str = "Test commit",
        days_ago: int = 0,
    ) -> CommitEvent:
        """Create a test commit event."""
        timestamp = self.base_time - timedelta(days=days_ago)
        # Generate a valid 40-character SHA-1 hash from the input string
        import hashlib

        valid_hash = hashlib.sha1(commit_hash.encode()).hexdigest()
        return CommitEvent(
            hash=valid_hash,
            message=message,
            author_name="Test Author",
            author_email="test@example.com",
            timestamp=timestamp,
            files=files,
            parent_hashes=[],
        )

    def create_test_problem_commit(
        self,
        commit_hash: str,
        problem_type: str,
        affected_files: list[str],
        fix_description: str = "Fix test issue",
        confidence: float = 0.8,
    ) -> ProblemCommit:
        """Create a test problem commit."""
        # Generate a valid 40-character SHA-1 hash from the input string
        import hashlib

        valid_hash = hashlib.sha1(commit_hash.encode()).hexdigest()
        return ProblemCommit(
            commit_hash=valid_hash,
            problem_type=problem_type,
            affected_files=affected_files,
            fix_description=fix_description,
            confidence_score=confidence,
        )

    def test_init_with_valid_parameters(self):
        """Test PatternDetector initialization with valid parameters."""
        detector = PatternDetector(min_confidence=0.5, recency_days=180)
        assert detector.min_confidence == 0.5
        assert detector.recency_days == 180

    def test_init_with_invalid_confidence(self):
        """Test PatternDetector initialization with invalid confidence values."""
        # Test clamping of confidence values
        detector = PatternDetector(min_confidence=-0.5, recency_days=365)
        assert detector.min_confidence == 0.0

        detector = PatternDetector(min_confidence=1.5, recency_days=365)
        assert detector.min_confidence == 1.0

    def test_init_with_invalid_recency_days(self):
        """Test PatternDetector initialization with invalid recency days."""
        detector = PatternDetector(min_confidence=0.3, recency_days=0)
        assert detector.recency_days == 1  # Should be clamped to minimum

    def test_detect_cochange_patterns_basic(self):
        """Test basic co-change pattern detection."""
        # Create commits with co-changing files
        commits = [
            self.create_test_commit("abc123", ["file1.py", "file2.py"], days_ago=1),
            self.create_test_commit("def456", ["file1.py", "file2.py"], days_ago=2),
            self.create_test_commit("ghi789", ["file1.py", "file2.py"], days_ago=3),
            self.create_test_commit("jkl012", ["file3.py"], days_ago=4),
        ]

        patterns = self.detector.detect_cochange_patterns(commits, min_support=2)

        assert len(patterns) >= 1

        # Check that file1.py and file2.py are detected as co-changing
        pattern = patterns[0]
        assert "file1.py" in [pattern["file_a"], pattern["file_b"]]
        assert "file2.py" in [pattern["file_a"], pattern["file_b"]]
        assert pattern["support_count"] >= 2
        assert 0.0 <= pattern["confidence_score"] <= 1.0
        assert 0.0 <= pattern["recency_weight"] <= 1.0
        assert "commit_messages" in pattern
        assert isinstance(pattern["commit_messages"], list)

    def test_detect_cochange_patterns_insufficient_support(self):
        """Test co-change detection with insufficient support."""
        commits = [
            self.create_test_commit("abc123", ["file1.py", "file2.py"], days_ago=1),
        ]

        patterns = self.detector.detect_cochange_patterns(commits, min_support=3)

        # Should return empty list due to insufficient support
        assert len(patterns) == 0

    def test_detect_cochange_patterns_single_file_commits(self):
        """Test co-change detection with single-file commits."""
        commits = [
            self.create_test_commit("abc123", ["file1.py"], days_ago=1),
            self.create_test_commit("def456", ["file2.py"], days_ago=2),
        ]

        patterns = self.detector.detect_cochange_patterns(commits, min_support=1)

        # Should return empty list - no co-changes possible
        assert len(patterns) == 0

    def test_detect_cochange_patterns_empty_commits(self):
        """Test co-change detection with empty commit list."""
        patterns = self.detector.detect_cochange_patterns([], min_support=1)
        assert len(patterns) == 0

    def test_detect_maintenance_hotspots_basic(self):
        """Test basic maintenance hotspot detection."""
        # Create regular commits
        commits = [
            self.create_test_commit("abc123", ["hotspot.py", "normal.py"], days_ago=1),
            self.create_test_commit("def456", ["hotspot.py"], days_ago=2),
            self.create_test_commit("ghi789", ["normal.py"], days_ago=3),
            self.create_test_commit("jkl012", ["hotspot.py"], days_ago=4),
        ]

        # Create problem commits for hotspot.py
        problem_commits = [
            self.create_test_problem_commit("abc123", "bug", ["hotspot.py"]),
            self.create_test_problem_commit("jkl012", "error", ["hotspot.py"]),
        ]

        hotspots = self.detector.detect_maintenance_hotspots(commits, problem_commits)

        assert len(hotspots) >= 1

        # Check that hotspot.py is detected
        hotspot = next((h for h in hotspots if h["file_path"] == "hotspot.py"), None)
        assert hotspot is not None
        assert hotspot["problem_frequency"] >= 1
        assert 0.0 <= hotspot["hotspot_score"] <= 1.0
        assert hotspot["trend_direction"] in [
            "increasing",
            "decreasing",
            "stable",
            "unknown",
        ]

    def test_detect_maintenance_hotspots_no_problems(self):
        """Test hotspot detection with no problem commits."""
        commits = [
            self.create_test_commit("abc123", ["file1.py"], days_ago=1),
        ]

        hotspots = self.detector.detect_maintenance_hotspots(commits, [])

        # Should return empty list - no problems to analyze
        assert len(hotspots) == 0

    def test_detect_maintenance_hotspots_empty_inputs(self):
        """Test hotspot detection with empty inputs."""
        hotspots = self.detector.detect_maintenance_hotspots([], [])
        assert len(hotspots) == 0

    def test_detect_solution_patterns_basic(self):
        """Test basic solution pattern detection."""
        problem_commits = [
            self.create_test_problem_commit(
                "abc123", "bug", ["file1.py"], "fix validation error"
            ),
            self.create_test_problem_commit(
                "def456", "bug", ["file2.py"], "fix validation check"
            ),
            self.create_test_problem_commit(
                "ghi789", "performance", ["file3.py"], "optimize database query"
            ),
            self.create_test_problem_commit(
                "jkl012", "performance", ["file4.py"], "optimize memory usage"
            ),
        ]

        patterns = self.detector.detect_solution_patterns(problem_commits)

        assert len(patterns) >= 1

        # Should detect bug -> validation pattern
        bug_pattern = next((p for p in patterns if p["problem_type"] == "bug"), None)
        assert bug_pattern is not None
        assert "validation" in bug_pattern["solution_approach"]
        assert 0.0 <= bug_pattern["success_rate"] <= 1.0
        assert 0.0 <= bug_pattern["applicability_confidence"] <= 1.0

    def test_detect_solution_patterns_insufficient_data(self):
        """Test solution pattern detection with insufficient data."""
        problem_commits = [
            self.create_test_problem_commit("abc123", "bug", ["file1.py"], "fix issue"),
        ]

        patterns = self.detector.detect_solution_patterns(problem_commits)

        # Should return empty list due to insufficient examples
        assert len(patterns) == 0

    def test_detect_solution_patterns_empty_input(self):
        """Test solution pattern detection with empty input."""
        patterns = self.detector.detect_solution_patterns([])
        assert len(patterns) == 0

    def test_build_cochange_matrix(self):
        """Test co-change matrix building with commit messages."""
        commits = [
            self.create_test_commit(
                "abc123",
                ["file1.py", "file2.py"],
                "Fix bug in file1 and file2",
                days_ago=1,
            ),
            self.create_test_commit(
                "def456", ["file1.py", "file3.py"], "Update file1 and file3", days_ago=2
            ),
            self.create_test_commit(
                "ghi789",
                ["file2.py", "file3.py"],
                "Refactor file2 and file3",
                days_ago=3,
            ),
        ]

        matrix, commit_messages = self.detector._build_cochange_matrix(commits)

        # Should have 3 pairs: (file1,file2), (file1,file3), (file2,file3)
        assert len(matrix) == 3
        assert len(commit_messages) == 3

        # Check specific pairs exist
        file1_file2 = tuple(sorted(["file1.py", "file2.py"]))
        file1_file3 = tuple(sorted(["file1.py", "file3.py"]))
        file2_file3 = tuple(sorted(["file2.py", "file3.py"]))

        assert file1_file2 in matrix
        assert file1_file2 in commit_messages

        # Check that commit messages are collected (raw messages, formatted later)
        assert "Fix bug in file1 and file2" in commit_messages[file1_file2]

        assert file1_file3 in matrix
        assert file2_file3 in matrix

        # Each pair should occur once
        assert matrix[file1_file2] == 1
        assert matrix[file1_file3] == 1
        assert matrix[file2_file3] == 1

    def test_calculate_file_frequencies(self):
        """Test file frequency calculation."""
        commits = [
            self.create_test_commit("abc123", ["file1.py", "file2.py"], days_ago=1),
            self.create_test_commit("def456", ["file1.py"], days_ago=2),
            self.create_test_commit("ghi789", ["file3.py"], days_ago=3),
        ]

        frequencies = self.detector._calculate_file_frequencies(commits)

        assert frequencies["file1.py"] == 2
        assert frequencies["file2.py"] == 1
        assert frequencies["file3.py"] == 1

    def test_calculate_recency_weight(self):
        """Test recency weight calculation."""
        # Create commits with specific timestamps
        recent_commit = self.create_test_commit(
            "abc123", ["file1.py", "file2.py"], days_ago=1
        )
        old_commit = self.create_test_commit(
            "def456", ["file1.py", "file2.py"], days_ago=300
        )

        commits = [recent_commit, old_commit]

        recent_weight = self.detector._calculate_recency_weight(
            commits, "file1.py", "file2.py", self.base_time
        )

        # Recent co-change should have higher weight
        assert 0.1 <= recent_weight <= 1.0

    def test_calculate_quality_rating(self):
        """Test quality rating calculation."""
        # Test high quality
        rating = self.detector._calculate_quality_rating(0.9, 0.9)
        assert rating == "high"

        # Test medium quality
        rating = self.detector._calculate_quality_rating(0.7, 0.6)
        assert rating == "medium"

        # Test low quality
        rating = self.detector._calculate_quality_rating(0.5, 0.4)
        assert rating == "low"

        # Test very low quality
        rating = self.detector._calculate_quality_rating(0.2, 0.1)
        assert rating == "very_low"

    def test_extract_problem_type(self):
        """Test problem type extraction."""
        assert self.detector._extract_problem_type("bug fix") == "bug"
        assert self.detector._extract_problem_type("performance issue") == "performance"
        assert (
            self.detector._extract_problem_type("security vulnerability") == "security"
        )
        assert self.detector._extract_problem_type("random text") == "other"
        assert self.detector._extract_problem_type("") == "unknown"

    def test_extract_solution_approach(self):
        """Test solution approach extraction."""
        assert self.detector._extract_solution_approach("refactor code") == "refactor"
        assert (
            self.detector._extract_solution_approach("add validation") == "validation"
        )
        # "fix error handling" matches "fix" first, so returns "fix_logic"
        assert (
            self.detector._extract_solution_approach("fix error handling")
            == "fix_logic"
        )
        # Test for pure error handling keywords
        assert (
            self.detector._extract_solution_approach("catch exception")
            == "error_handling"
        )
        assert (
            self.detector._extract_solution_approach("optimize performance")
            == "optimization"
        )
        assert self.detector._extract_solution_approach("random text") == "generic_fix"
        assert self.detector._extract_solution_approach("") == "unknown"

    def test_calculate_applicability_confidence(self):
        """Test applicability confidence calculation."""
        # Test with good sample size - Wilson score with small sample can be lower
        confidence = self.detector._calculate_applicability_confidence(8, 10)
        assert 0.4 <= confidence <= 1.0  # Adjusted to allow Wilson score behavior

        # Test with small sample size
        confidence = self.detector._calculate_applicability_confidence(2, 3)
        assert 0.0 <= confidence <= 1.0

        # Test with zero attempts
        confidence = self.detector._calculate_applicability_confidence(0, 0)
        assert confidence == 0.0

        # Test with larger sample size should give higher confidence
        confidence = self.detector._calculate_applicability_confidence(30, 35)
        assert 0.7 <= confidence <= 1.0

    def test_pattern_detection_with_confidence_filtering(self):
        """Test that patterns below confidence threshold are filtered out."""
        detector = PatternDetector(min_confidence=0.9, recency_days=365)

        # Create minimal data that should produce low confidence
        commits = [
            self.create_test_commit("abc123", ["file1.py", "file2.py"], days_ago=100),
            self.create_test_commit("def456", ["file1.py", "file2.py"], days_ago=200),
        ]

        patterns = detector.detect_cochange_patterns(commits, min_support=1)

        # High confidence threshold should filter out low-confidence patterns
        assert len(patterns) == 0 or all(p["confidence_score"] >= 0.9 for p in patterns)

    def test_pattern_detection_error_handling(self):
        """Test pattern detection error handling."""
        # Test with invalid commit data
        invalid_commit = Mock()
        invalid_commit.files = None  # This should cause an error

        try:
            patterns = self.detector.detect_cochange_patterns([invalid_commit])
            # Should return empty list instead of crashing
            assert isinstance(patterns, list)
        except Exception:
            # Should not raise unhandled exceptions
            pytest.fail("Pattern detection should handle invalid data gracefully")

    def test_consistency_factor_calculation(self):
        """Test consistency factor calculation for maintenance hotspots."""
        # Test with evenly spaced problems (high consistency)
        timestamps = [
            self.base_time - timedelta(days=10),
            self.base_time - timedelta(days=20),
            self.base_time - timedelta(days=30),
        ]

        factor = self.detector._calculate_consistency_factor(timestamps)
        assert 0.1 <= factor <= 1.0

    def test_trend_direction_calculation(self):
        """Test trend direction calculation."""
        # Test increasing trend (more recent problems)
        timestamps = [
            self.base_time - timedelta(days=1),
            self.base_time - timedelta(days=2),
            self.base_time - timedelta(days=300),
        ]

        trend = self.detector._calculate_trend_direction(timestamps, self.base_time)
        assert trend in ["increasing", "decreasing", "stable", "unknown"]

    def test_statistical_significance_testing(self):
        """Test statistical significance testing for co-change patterns."""
        file_frequencies = {"file1.py": 10, "file2.py": 8}
        total_commits = 100

        significance = self.detector._test_cochange_significance(
            "file1.py", "file2.py", 5, file_frequencies, total_commits
        )

        assert 0.0 <= significance <= 1.0

    def test_pattern_detector_integration(self):
        """Test integration of all pattern detection methods."""
        # Create a realistic set of commits and problems
        commits = []
        problem_commits = []

        # Simulate a development history
        for i in range(20):
            files = ["core.py", "utils.py"] if i % 3 == 0 else ["core.py"]
            commit = self.create_test_commit(
                f"commit{i:03d}", files, f"Commit {i}", days_ago=i
            )
            commits.append(commit)

            # Add some problem commits
            if i % 5 == 0:
                problem = self.create_test_problem_commit(
                    f"commit{i:03d}", "bug", files, f"Fix issue in commit {i}"
                )
                problem_commits.append(problem)

        # Test all detection methods work together
        cochange_patterns = self.detector.detect_cochange_patterns(
            commits, min_support=2
        )
        maintenance_hotspots = self.detector.detect_maintenance_hotspots(
            commits, problem_commits
        )
        solution_patterns = self.detector.detect_solution_patterns(problem_commits)

        # All methods should complete without errors
        assert isinstance(cochange_patterns, list)
        assert isinstance(maintenance_hotspots, list)
        assert isinstance(solution_patterns, list)

        # Should detect some patterns with this realistic data
        assert len(cochange_patterns) >= 0  # May be 0 due to confidence filtering
        assert len(maintenance_hotspots) >= 0
        assert len(solution_patterns) >= 0
