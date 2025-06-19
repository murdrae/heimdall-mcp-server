"""
Unit tests for GitPatternEmbedder.

Tests the pattern embedding functionality including natural language generation,
token limit enforcement, and confidence metric embedding.
"""

import pytest

from cognitive_memory.git_analysis.pattern_embedder import GitPatternEmbedder


class TestGitPatternEmbedder:
    """Test suite for GitPatternEmbedder."""

    @pytest.fixture
    def embedder(self):
        """Create GitPatternEmbedder instance."""
        return GitPatternEmbedder(max_tokens=400)

    @pytest.fixture
    def sample_cochange_pattern(self):
        """Sample co-change pattern data."""
        return {
            "file_a": "src/utils.py",
            "file_b": "src/main.py",
            "support_count": 5,
            "confidence_score": 0.8,
            "quality_rating": "high",
            "recency_weight": 0.9,
            "statistical_significance": 0.7,
        }

    @pytest.fixture
    def sample_hotspot_pattern(self):
        """Sample hotspot pattern data."""
        return {
            "file_path": "src/buggy_module.py",
            "problem_frequency": 15,
            "hotspot_score": 0.65,
            "trend_direction": "increasing",
            "recent_problems": ["bug", "error", "crash"],
            "total_changes": 50,
            "consistency_factor": 0.8,
        }

    @pytest.fixture
    def sample_solution_pattern(self):
        """Sample solution pattern data."""
        return {
            "problem_type": "validation_error",
            "solution_approach": "input_validation",
            "success_rate": 0.9,
            "applicability_confidence": 0.85,
            "example_fixes": ["abc123def", "456789ghi", "jkl012mno"],
            "usage_count": 12,
            "total_attempts": 14,
        }

    def test_initialization(self):
        """Test GitPatternEmbedder initialization."""
        embedder = GitPatternEmbedder(max_tokens=300)
        assert embedder.max_tokens == 300

    def test_embed_cochange_pattern_basic(self, embedder, sample_cochange_pattern):
        """Test basic co-change pattern embedding."""
        result = embedder.embed_cochange_pattern(sample_cochange_pattern)

        # Check that essential information is included
        assert "Development pattern" in result
        assert "80%" in result  # confidence percentage
        assert "high" in result  # quality rating
        assert "src/utils.py" in result
        assert "src/main.py" in result
        assert "5 co-commits" in result
        assert "coupling" in result.lower()

        # Check confidence indicators are embedded
        assert "confidence:" in result
        assert "quality:" in result

    def test_embed_cochange_pattern_recency_analysis(
        self, embedder, sample_cochange_pattern
    ):
        """Test co-change pattern embedding with recency analysis."""
        # Test high recency
        sample_cochange_pattern["recency_weight"] = 0.9
        result = embedder.embed_cochange_pattern(sample_cochange_pattern)
        assert "recent pattern activity" in result.lower()

        # Test low recency
        sample_cochange_pattern["recency_weight"] = 0.2
        result = embedder.embed_cochange_pattern(sample_cochange_pattern)
        assert "declining activity" in result.lower()

    def test_embed_cochange_pattern_quality_insights(
        self, embedder, sample_cochange_pattern
    ):
        """Test co-change pattern embedding with quality insights."""
        # Test high quality
        sample_cochange_pattern["quality_rating"] = "high"
        result = embedder.embed_cochange_pattern(sample_cochange_pattern)
        assert "high-confidence pattern" in result.lower()

        # Test low quality
        sample_cochange_pattern["quality_rating"] = "low"
        result = embedder.embed_cochange_pattern(sample_cochange_pattern)
        assert "lower confidence" in result.lower()

    def test_embed_hotspot_pattern_basic(self, embedder, sample_hotspot_pattern):
        """Test basic hotspot pattern embedding."""
        result = embedder.embed_hotspot_pattern(sample_hotspot_pattern)

        # Check essential information
        assert "Maintenance hotspot" in result
        assert "65%" in result  # hotspot score percentage
        assert "increasing" in result  # trend direction
        assert "src/buggy_module.py" in result
        assert "15 issues" in result
        assert "50 total changes" in result

    def test_embed_hotspot_pattern_trend_analysis(
        self, embedder, sample_hotspot_pattern
    ):
        """Test hotspot pattern embedding with trend analysis."""
        # Test increasing trend
        sample_hotspot_pattern["trend_direction"] = "increasing"
        result = embedder.embed_hotspot_pattern(sample_hotspot_pattern)
        assert "increasing problem rate" in result.lower()
        assert "technical debt" in result.lower()

        # Test decreasing trend
        sample_hotspot_pattern["trend_direction"] = "decreasing"
        result = embedder.embed_hotspot_pattern(sample_hotspot_pattern)
        assert "decreasing problem rate" in result.lower()
        assert "improving" in result.lower()

        # Test stable trend
        sample_hotspot_pattern["trend_direction"] = "stable"
        result = embedder.embed_hotspot_pattern(sample_hotspot_pattern)
        assert "stable problem pattern" in result.lower()

    def test_embed_hotspot_pattern_risk_assessment(
        self, embedder, sample_hotspot_pattern
    ):
        """Test hotspot pattern embedding with risk assessment."""
        # Test high risk
        sample_hotspot_pattern["hotspot_score"] = 0.8
        result = embedder.embed_hotspot_pattern(sample_hotspot_pattern)
        assert "high-priority candidate" in result.lower()

        # Test moderate risk
        sample_hotspot_pattern["hotspot_score"] = 0.4
        result = embedder.embed_hotspot_pattern(sample_hotspot_pattern)
        assert "moderate maintenance burden" in result.lower()

        # Test low risk
        sample_hotspot_pattern["hotspot_score"] = 0.2
        result = embedder.embed_hotspot_pattern(sample_hotspot_pattern)
        assert "low maintenance overhead" in result.lower()

    def test_embed_hotspot_pattern_recent_problems(
        self, embedder, sample_hotspot_pattern
    ):
        """Test hotspot pattern embedding with recent problems."""
        result = embedder.embed_hotspot_pattern(sample_hotspot_pattern)

        # Should include recent problem types
        assert "recent issues include" in result.lower()
        assert "bug" in result
        assert "error" in result
        assert "crash" in result

    def test_embed_solution_pattern_basic(self, embedder, sample_solution_pattern):
        """Test basic solution pattern embedding."""
        result = embedder.embed_solution_pattern(sample_solution_pattern)

        # Check essential information
        assert "Solution pattern" in result
        assert "90%" in result  # success rate
        assert "85%" in result  # confidence
        assert "validation_error" in result
        assert "input_validation" in result
        assert "12 times" in result

    def test_embed_solution_pattern_effectiveness(
        self, embedder, sample_solution_pattern
    ):
        """Test solution pattern embedding with effectiveness assessment."""
        # Test highly effective
        sample_solution_pattern["success_rate"] = 0.9
        result = embedder.embed_solution_pattern(sample_solution_pattern)
        assert "highly effective" in result.lower()

        # Test moderately effective
        sample_solution_pattern["success_rate"] = 0.7
        result = embedder.embed_solution_pattern(sample_solution_pattern)
        assert "moderately effective" in result.lower()

        # Test lower effectiveness
        sample_solution_pattern["success_rate"] = 0.4
        result = embedder.embed_solution_pattern(sample_solution_pattern)
        assert "lower success rate" in result.lower()

    def test_embed_solution_pattern_applicability(
        self, embedder, sample_solution_pattern
    ):
        """Test solution pattern embedding with applicability guidance."""
        # Test high applicability
        sample_solution_pattern["applicability_confidence"] = 0.8
        result = embedder.embed_solution_pattern(sample_solution_pattern)
        assert "high applicability confidence" in result.lower()

        # Test moderate applicability
        sample_solution_pattern["applicability_confidence"] = 0.6
        result = embedder.embed_solution_pattern(sample_solution_pattern)
        assert "moderate applicability" in result.lower()

        # Test limited applicability
        sample_solution_pattern["applicability_confidence"] = 0.3
        result = embedder.embed_solution_pattern(sample_solution_pattern)
        assert "limited applicability" in result.lower()

    def test_embed_solution_pattern_examples(self, embedder, sample_solution_pattern):
        """Test solution pattern embedding with example references."""
        result = embedder.embed_solution_pattern(sample_solution_pattern)

        # Should include example commit references
        assert "recent successful applications" in result.lower()
        assert "abc123def" in result
        assert "456789ghi" in result
        assert "jkl012mno" in result

    def test_format_file_path_short(self, embedder):
        """Test file path formatting for short paths."""
        short_path = "src/utils.py"
        result = embedder._format_file_path(short_path)
        assert result == short_path

    def test_format_file_path_long(self, embedder):
        """Test file path formatting for long paths."""
        long_path = "very/long/path/to/deeply/nested/directory/structure/file.py"
        result = embedder._format_file_path(long_path)

        # Should be shortened with ellipsis
        assert "..." in result
        assert result.startswith("very/")
        assert result.endswith("structure/file.py")
        assert len(result) < len(long_path)

    def test_format_file_path_empty(self, embedder):
        """Test file path formatting for empty/None paths."""
        assert embedder._format_file_path("") == ""
        assert embedder._format_file_path(None) is None

    def test_enforce_token_limit_under_limit(self, embedder):
        """Test token limit enforcement for content under limit."""
        short_content = "This is a short description that should not be truncated."
        result = embedder._enforce_token_limit(short_content)
        assert result == short_content

    def test_enforce_token_limit_over_limit(self, embedder):
        """Test token limit enforcement for content over limit."""
        # Create very long content that actually exceeds 400 tokens
        long_content = (
            "This is the first sentence with important metrics. " * 15
            + "This is a very long second sentence that might be truncated. " * 35
            + "This final sentence should definitely be removed."
        )

        result = embedder._enforce_token_limit(long_content)

        # Should be shorter than original
        assert len(result) < len(long_content)

        # Should preserve first sentence (contains metrics)
        assert result.startswith("This is the first sentence")

        # Should end properly
        assert result.endswith(".")

    def test_enforce_token_limit_preserves_metrics(self, embedder):
        """Test that token limit enforcement preserves important metrics."""
        content_with_metrics = (
            "Development pattern (confidence: 85%, quality: high): Important info. "
            + "This is additional information that could be truncated. " * 50
            + "This definitely gets removed."
        )

        result = embedder._enforce_token_limit(content_with_metrics)

        # Should preserve confidence and quality metrics
        assert "confidence: 85%" in result
        assert "quality: high" in result

    def test_embed_pattern_collection(
        self,
        embedder,
        sample_cochange_pattern,
        sample_hotspot_pattern,
        sample_solution_pattern,
    ):
        """Test embedding a collection of different pattern types."""
        patterns = {
            "cochange": [sample_cochange_pattern],
            "hotspot": [sample_hotspot_pattern],
            "solution": [sample_solution_pattern],
        }

        results = embedder.embed_pattern_collection(patterns)

        assert len(results) == 3
        assert all(isinstance(result, str) for result in results)

        # Check that different pattern types are represented
        combined_text = " ".join(results)
        assert "Development pattern" in combined_text  # co-change
        assert "Maintenance hotspot" in combined_text  # hotspot
        assert "Solution pattern" in combined_text  # solution

    def test_embed_pattern_collection_unknown_type(
        self, embedder, sample_cochange_pattern
    ):
        """Test embedding collection with unknown pattern type."""
        patterns = {
            "cochange": [sample_cochange_pattern],
            "unknown_type": [{"some": "data"}],
        }

        results = embedder.embed_pattern_collection(patterns)

        # Should only embed known patterns
        assert len(results) == 1
        assert "Development pattern" in results[0]

    def test_error_handling_cochange(self, embedder):
        """Test error handling in co-change pattern embedding."""
        # Test with malformed pattern
        malformed_pattern = {"invalid": "data"}
        result = embedder.embed_cochange_pattern(malformed_pattern)

        # Should handle gracefully with default values
        assert "Development pattern" in result
        assert "confidence: 0%" in result
        assert "unknown" in result

    def test_error_handling_hotspot(self, embedder):
        """Test error handling in hotspot pattern embedding."""
        malformed_pattern = {"invalid": "data"}
        result = embedder.embed_hotspot_pattern(malformed_pattern)

        # Should handle gracefully with default values
        assert "Maintenance hotspot" in result
        assert "risk score: 0%" in result
        assert "unknown" in result

    def test_error_handling_solution(self, embedder):
        """Test error handling in solution pattern embedding."""
        malformed_pattern = {"invalid": "data"}
        result = embedder.embed_solution_pattern(malformed_pattern)

        # Should handle gracefully with default values
        assert "Solution pattern" in result
        assert "confidence: 0%" in result
        assert "unknown" in result

    def test_token_estimation_accuracy(self, embedder):
        """Test token estimation accuracy."""
        # Test with known content
        content = "This is a test sentence with exactly ten words here."
        # Should estimate roughly 15-20 tokens (words + punctuation)
        # Just test that the method works without truncation
        result = embedder._enforce_token_limit(content)

        # Content should remain unchanged if under limit
        result = embedder._enforce_token_limit(content)
        assert result == content

    def test_confidence_metrics_preserved(self, embedder, sample_cochange_pattern):
        """Test that confidence metrics are always preserved in embeddings."""
        # Even with very long descriptions, confidence should be preserved
        sample_cochange_pattern["file_a"] = (
            "very/long/path/that/might/cause/truncation.py"
        )
        sample_cochange_pattern["file_b"] = "another/very/long/path/for/testing.py"

        result = embedder.embed_cochange_pattern(sample_cochange_pattern)

        # Core confidence metrics should always be present
        assert "confidence:" in result
        assert "quality:" in result
        assert "80%" in result  # confidence percentage
        assert "high" in result  # quality rating
