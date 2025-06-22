"""Unit tests for ProjectActivityTracker class."""

import time
from unittest.mock import Mock, patch

from cognitive_memory.storage.dual_memory import MemoryAccessPattern
from cognitive_memory.storage.project_activity_tracker import (
    ProjectActivityTracker,
    create_project_activity_tracker,
)


class TestProjectActivityTracker:
    """Test suite for ProjectActivityTracker."""

    def test_init_without_git_repository(self):
        """Test initialization without git repository."""
        tracker = ProjectActivityTracker(repository_path=None)

        assert tracker.repository_path is None
        assert tracker.git_miner is None
        assert not tracker.git_available
        assert tracker.activity_window_days == 30
        assert tracker.max_commits_per_day == 3
        assert tracker.max_accesses_per_day == 100
        assert tracker.commit_weight == 0.6
        assert tracker.access_weight == 0.4

    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        tracker = ProjectActivityTracker(
            repository_path=None,
            activity_window_days=14,
            max_commits_per_day=5,
            max_accesses_per_day=200,
            commit_weight=0.7,
            access_weight=0.3,
        )

        assert tracker.activity_window_days == 14
        assert tracker.max_commits_per_day == 5
        assert tracker.max_accesses_per_day == 200
        assert tracker.commit_weight == 0.7
        assert tracker.access_weight == 0.3

    def test_calculate_git_activity_score_no_git(self):
        """Test git activity score calculation without git repository."""
        tracker = ProjectActivityTracker(repository_path=None)
        score = tracker.calculate_git_activity_score()

        assert score == 0.0

    @patch("cognitive_memory.storage.project_activity_tracker.GitHistoryMiner")
    @patch("cognitive_memory.storage.project_activity_tracker.validate_git_repository")
    def test_calculate_git_activity_score_with_commits(
        self, mock_validate, mock_git_miner_class
    ):
        """Test git activity score calculation with mock commits."""
        # Setup mocks
        mock_validate.return_value = True
        mock_git_miner = Mock()
        mock_git_miner.validate_repository.return_value = True
        mock_git_miner_class.return_value = mock_git_miner

        # Mock commit data
        mock_commits = [Mock() for _ in range(6)]  # 6 commits
        mock_git_miner.extract_commit_history.return_value = mock_commits

        tracker = ProjectActivityTracker(repository_path="/fake/repo")
        tracker.git_available = True
        tracker.git_miner = mock_git_miner

        # Test with 30-day window and 3 commits/day max
        # 6 commits / (3 * 30) = 6/90 = 0.067
        score = tracker.calculate_git_activity_score(window_days=30)

        expected_score = 6 / (3 * 30)  # 6 commits / max possible (3*30)
        assert abs(score - expected_score) < 0.001

    def test_calculate_memory_access_score_empty_patterns(self):
        """Test memory access score with empty patterns."""
        tracker = ProjectActivityTracker(repository_path=None)
        score = tracker.calculate_memory_access_score({})

        assert score == 0.0

    def test_calculate_memory_access_score_with_patterns(self):
        """Test memory access score with mock access patterns."""
        tracker = ProjectActivityTracker(repository_path=None)

        # Create mock access patterns
        pattern1 = MemoryAccessPattern("memory1")
        pattern2 = MemoryAccessPattern("memory2")

        # Add some access times (simulate 10 accesses each in the last week)
        current_time = time.time()
        for i in range(10):
            pattern1.add_access(current_time - i * 3600)  # One per hour
            pattern2.add_access(current_time - i * 3600)

        patterns = {"memory1": pattern1, "memory2": pattern2}

        # Test with 7-day window
        score = tracker.calculate_memory_access_score(patterns, window_days=7)

        # Should be > 0 since we have access patterns
        assert score > 0.0

    def test_calculate_activity_score_combination(self):
        """Test overall activity score calculation."""
        tracker = ProjectActivityTracker(repository_path=None)

        # Mock the component scores
        with patch.object(tracker, "calculate_git_activity_score", return_value=0.5):
            with patch.object(
                tracker, "calculate_memory_access_score", return_value=0.3
            ):
                score = tracker.calculate_activity_score({})

                # Expected: 0.6 * 0.5 + 0.4 * 0.3 = 0.3 + 0.12 = 0.42
                expected = 0.6 * 0.5 + 0.4 * 0.3
                assert abs(score - expected) < 0.001

    def test_get_dynamic_decay_rate_high_activity(self):
        """Test dynamic decay rate for high activity."""
        tracker = ProjectActivityTracker(repository_path=None)

        # Mock high activity score (>0.7)
        with patch.object(tracker, "calculate_activity_score", return_value=0.8):
            base_rate = 0.1
            scaled_rate = tracker.get_dynamic_decay_rate(base_rate, {})

            # High activity should give 2.0x multiplier
            expected = base_rate * 2.0
            assert abs(scaled_rate - expected) < 0.001

    def test_get_dynamic_decay_rate_normal_activity(self):
        """Test dynamic decay rate for normal activity."""
        tracker = ProjectActivityTracker(repository_path=None)

        # Mock normal activity score (0.2-0.7)
        with patch.object(tracker, "calculate_activity_score", return_value=0.5):
            base_rate = 0.1
            scaled_rate = tracker.get_dynamic_decay_rate(base_rate, {})

            # Normal activity should give 1.0x multiplier
            expected = base_rate * 1.0
            assert abs(scaled_rate - expected) < 0.001

    def test_get_dynamic_decay_rate_low_activity(self):
        """Test dynamic decay rate for low activity."""
        tracker = ProjectActivityTracker(repository_path=None)

        # Mock low activity score (<0.2)
        with patch.object(tracker, "calculate_activity_score", return_value=0.1):
            base_rate = 0.1
            scaled_rate = tracker.get_dynamic_decay_rate(base_rate, {})

            # Low activity should give 0.1x multiplier
            expected = base_rate * 0.1
            assert abs(scaled_rate - expected) < 0.001

    def test_cache_functionality(self):
        """Test activity score caching."""
        tracker = ProjectActivityTracker(repository_path=None)

        # Mock component scores
        with patch.object(
            tracker, "calculate_git_activity_score", return_value=0.5
        ) as mock_git:
            with patch.object(
                tracker, "calculate_memory_access_score", return_value=0.3
            ) as mock_access:
                # First call
                score1 = tracker.calculate_activity_score({})

                # Second call should use cache
                score2 = tracker.calculate_activity_score({})

                assert score1 == score2
                # Git and access score methods should only be called once due to caching
                assert mock_git.call_count == 1
                assert mock_access.call_count == 1

    def test_clear_cache(self):
        """Test cache clearing functionality."""
        tracker = ProjectActivityTracker(repository_path=None)

        # Add something to cache
        tracker._activity_cache["test"] = (0.5, time.time())
        assert len(tracker._activity_cache) == 1

        tracker.clear_cache()
        assert len(tracker._activity_cache) == 0

    def test_get_activity_stats(self):
        """Test activity statistics retrieval."""
        tracker = ProjectActivityTracker(repository_path=None)
        stats = tracker.get_activity_stats()

        assert "repository_path" in stats
        assert "git_available" in stats
        assert "activity_window_days" in stats
        assert "max_commits_per_day" in stats
        assert "max_accesses_per_day" in stats
        assert "commit_weight" in stats
        assert "access_weight" in stats
        assert "cache_entries" in stats

        assert stats["git_available"] is False
        assert stats["activity_window_days"] == 30

    def test_close_cleanup(self):
        """Test resource cleanup."""
        tracker = ProjectActivityTracker(repository_path=None)

        # Add something to cache
        tracker._activity_cache["test"] = (0.5, time.time())

        tracker.close()

        # Cache should be cleared
        assert len(tracker._activity_cache) == 0

    @patch("cognitive_memory.storage.project_activity_tracker.validate_git_repository")
    def test_invalid_git_repository(self, mock_validate):
        """Test handling of invalid git repository."""
        mock_validate.return_value = False

        tracker = ProjectActivityTracker(repository_path="/invalid/repo")

        assert not tracker.git_available
        assert tracker.git_miner is None

    def test_weight_validation_warning(self):
        """Test warning for invalid weight combination."""
        # Test that tracker can be created even with invalid weights
        tracker = ProjectActivityTracker(
            repository_path=None,
            commit_weight=0.7,
            access_weight=0.4,  # Sum = 1.1, should trigger warning but still work
        )

        # Check that weights were still set despite the warning
        assert tracker.commit_weight == 0.7
        assert tracker.access_weight == 0.4

        # Test that the tracker still functions
        assert isinstance(tracker, ProjectActivityTracker)


class TestCreateProjectActivityTracker:
    """Test suite for create_project_activity_tracker factory function."""

    @patch("cognitive_memory.storage.project_activity_tracker.Path")
    def test_create_without_repository_path(self, mock_path):
        """Test factory function without repository path."""
        # Mock no git directory found
        mock_cwd = Mock()
        mock_git_dir = Mock()
        mock_git_dir.exists.return_value = False
        mock_cwd.__truediv__ = Mock(return_value=mock_git_dir)
        mock_path.cwd.return_value = mock_cwd

        tracker = create_project_activity_tracker()

        assert isinstance(tracker, ProjectActivityTracker)
        assert tracker.repository_path is None

    def test_create_with_repository_path(self):
        """Test factory function with repository path."""
        repo_path = "/test/repo"
        tracker = create_project_activity_tracker(repository_path=repo_path)

        assert isinstance(tracker, ProjectActivityTracker)
        assert tracker.repository_path == repo_path

    def test_create_with_custom_parameters(self):
        """Test factory function with custom parameters."""
        tracker = create_project_activity_tracker(
            repository_path=None,
            activity_window_days=14,
            max_commits_per_day=5,
        )

        assert tracker.activity_window_days == 14
        assert tracker.max_commits_per_day == 5

    @patch("cognitive_memory.storage.project_activity_tracker.Path")
    def test_auto_detect_git_repository(self, mock_path):
        """Test auto-detection of git repository."""
        # Mock Path.cwd() and git directory existence
        mock_cwd = Mock()
        mock_git_dir = Mock()
        mock_git_dir.exists.return_value = True
        mock_cwd.__truediv__ = Mock(return_value=mock_git_dir)
        mock_path.cwd.return_value = mock_cwd

        # Mock str(current_dir) to return a path string
        mock_cwd.__str__ = Mock(return_value="/current/directory")

        tracker = create_project_activity_tracker()

        # Should auto-detect the repository path
        assert tracker.repository_path == "/current/directory"
