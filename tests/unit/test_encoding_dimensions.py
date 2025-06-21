"""
Unit tests for cognitive dimension extractors.
"""

import pytest
import torch

from cognitive_memory.core.config import CognitiveConfig
from cognitive_memory.encoding.dimensions import (
    CognitiveDimensionExtractor,
    ContextualExtractor,
    EmotionalExtractor,
    SocialExtractor,
    TemporalExtractor,
)


@pytest.fixture
def config():
    """Create a test cognitive config."""
    return CognitiveConfig()


@pytest.mark.slow
class TestEmotionalExtractor:
    """Test emotional dimension extraction."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.config = CognitiveConfig()
        self.extractor = EmotionalExtractor(self.config)

    def test_basic_extraction(self) -> None:
        """Test basic emotional dimension extraction."""
        text = "I'm really frustrated and angry with this terrible bug that won't get fixed"
        dims = self.extractor.extract(text)

        assert dims.shape == (self.config.emotional_dimensions,)
        assert torch.all(dims >= 0.0)
        assert torch.all(dims <= 1.0)
        assert (
            dims[0] > 0.3
        )  # frustration should be detected with explicit emotion words

    def test_satisfaction_detection(self) -> None:
        """Test satisfaction detection."""
        text = "Great! I'm so happy and satisfied that I solved this problem perfectly"
        dims = self.extractor.extract(text)

        assert (
            dims[1] > 0.4
        )  # satisfaction should be high with joy and satisfaction words

    def test_curiosity_detection(self) -> None:
        """Test curiosity detection."""
        text = "I'm curious and wondering how this fascinating algorithm works, I want to explore and discover more"
        dims = self.extractor.extract(text)

        assert (
            dims[2] > 0.3
        )  # curiosity should be detected with anticipation and curiosity words

    def test_stress_detection(self) -> None:
        """Test stress detection."""
        text = "I'm anxious and worried about this overwhelming deadline pressure, feeling stressed and panicked"
        dims = self.extractor.extract(text)

        assert dims[3] > 0.4  # stress should be high with explicit stress words

    def test_empty_text(self) -> None:
        """Test handling of empty text."""
        dims = self.extractor.extract("")
        assert dims.shape == (self.config.emotional_dimensions,)
        assert torch.all(dims == 0.0)

    def test_dimension_names(self) -> None:
        """Test dimension names."""
        names = self.extractor.get_dimension_names()
        expected = ["frustration", "satisfaction", "curiosity", "stress"]
        assert names == expected


class TestTemporalExtractor:
    """Test temporal dimension extraction."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.config = CognitiveConfig()
        self.extractor = TemporalExtractor(self.config)

    def test_urgency_detection(self) -> None:
        """Test urgency detection."""
        text = "I need this done ASAP, it's urgent"
        dims = self.extractor.extract(text)

        assert dims.shape == (self.config.temporal_dimensions,)
        assert dims[0] > 0.3  # urgency should be high

    def test_deadline_detection(self) -> None:
        """Test deadline pressure detection."""
        text = "The deadline is tomorrow and must be finished by 5pm"
        dims = self.extractor.extract(text)

        assert dims[1] > 0.3  # deadline pressure should be high

    def test_time_context_detection(self) -> None:
        """Test time context detection."""
        text = "This morning we had a meeting about next week's project"
        dims = self.extractor.extract(text)

        assert dims[2] > 0.2  # time context should be detected

    def test_dimension_names(self) -> None:
        """Test dimension names."""
        names = self.extractor.get_dimension_names()
        expected = ["urgency", "deadline_pressure", "time_context"]
        assert names == expected


class TestContextualExtractor:
    """Test contextual dimension extraction."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.config = CognitiveConfig()
        self.extractor = ContextualExtractor(self.config)

    def test_work_context_detection(self) -> None:
        """Test work context detection."""
        text = "In today's meeting with the client we discussed the project"
        dims = self.extractor.extract(text)

        assert dims.shape == (self.config.contextual_dimensions,)
        assert dims[0] > 0.3  # work context should be high

    def test_technical_context_detection(self) -> None:
        """Test technical context detection."""
        text = "I'm debugging this Python code that has API connection issues"
        dims = self.extractor.extract(text)

        assert dims[1] > 0.4  # technical context should be high

    def test_creative_context_detection(self) -> None:
        """Test creative context detection."""
        text = "I'm brainstorming design ideas for this innovative website"
        dims = self.extractor.extract(text)

        assert dims[2] > 0.3  # creative context should be detected

    def test_analytical_context_detection(self) -> None:
        """Test analytical context detection."""
        text = "Analyzing the data shows interesting patterns in user metrics"
        dims = self.extractor.extract(text)

        assert dims[3] > 0.3  # analytical context should be detected

    def test_dimension_names(self) -> None:
        """Test dimension names."""
        names = self.extractor.get_dimension_names()
        expected = [
            "work_context",
            "technical_context",
            "creative_context",
            "analytical_context",
            "collaborative_context",
            "individual_context",
        ]
        assert names == expected


class TestSocialExtractor:
    """Test social dimension extraction."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.config = CognitiveConfig()
        self.extractor = SocialExtractor(self.config)

    def test_collaboration_detection(self) -> None:
        """Test collaboration detection."""
        text = "We need to work together as a team on this project"
        dims = self.extractor.extract(text)

        assert dims.shape == (self.config.temporal_dimensions,)
        assert dims[0] > 0.3  # collaboration should be high

    def test_support_detection(self) -> None:
        """Test support detection."""
        text = "Can you help me with this? I need some guidance and advice"
        dims = self.extractor.extract(text)

        assert dims[1] > 0.4  # support should be high

    def test_interaction_detection(self) -> None:
        """Test interaction detection."""
        text = "Let's discuss this in our meeting and share our thoughts"
        dims = self.extractor.extract(text)

        assert dims[2] > 0.3  # interaction should be detected

    def test_dimension_names(self) -> None:
        """Test dimension names."""
        names = self.extractor.get_dimension_names()
        expected = ["collaboration", "support", "interaction"]
        assert names == expected


class TestCognitiveDimensionExtractor:
    """Test the complete cognitive dimension extractor."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.config = CognitiveConfig()
        self.extractor = CognitiveDimensionExtractor(self.config)

    def test_complete_extraction(self) -> None:
        """Test complete dimension extraction."""
        text = (
            "I'm frustrated working on this urgent project and need help from my team"
        )
        dims = self.extractor.extract_dimensions(text)

        # Check all dimension categories are present
        assert "emotional" in dims
        assert "temporal" in dims
        assert "contextual" in dims
        assert "social" in dims

        # Check tensor shapes
        assert dims["emotional"].shape == (4,)
        assert dims["temporal"].shape == (3,)
        assert dims["contextual"].shape == (6,)
        assert dims["social"].shape == (3,)

        # Check values are in valid range
        for _category, tensor in dims.items():
            assert torch.all(tensor >= 0.0)
            assert torch.all(tensor <= 1.0)

    def test_empty_text_handling(self) -> None:
        """Test handling of empty text."""
        dims = self.extractor.extract_dimensions("")

        # Should return zero tensors
        for _category, tensor in dims.items():
            assert torch.all(tensor == 0.0)

    def test_total_dimensions(self) -> None:
        """Test total dimension count."""
        total = self.extractor.get_total_dimensions()
        assert total == self.config.get_total_cognitive_dimensions()  # 4 + 3 + 6 + 3

    def test_dimension_names_structure(self) -> None:
        """Test dimension names structure."""
        names = self.extractor.get_all_dimension_names()

        assert "emotional" in names
        assert "temporal" in names
        assert "contextual" in names
        assert "social" in names

        assert len(names["emotional"]) == 4
        assert len(names["temporal"]) == 3
        assert len(names["contextual"]) == 6
        assert len(names["social"]) == 3

    def test_real_world_text(self) -> None:
        """Test with realistic cognitive scenarios."""
        scenarios = [
            "I'm debugging a critical API issue before tomorrow's deployment",
            "Our team brainstormed creative solutions during this morning's workshop",
            "Analyzing user feedback reveals interesting patterns in engagement",
            "I need urgent help understanding this complex algorithm",
        ]

        for text in scenarios:
            dims = self.extractor.extract_dimensions(text)

            # Ensure valid output for all scenarios
            for _category, tensor in dims.items():
                assert tensor.shape[0] > 0
                assert torch.all(tensor >= 0.0)
                assert torch.all(tensor <= 1.0)

            # At least some dimensions should be activated
            total_activation = sum(torch.sum(tensor).item() for tensor in dims.values())
            assert total_activation > 0.1
