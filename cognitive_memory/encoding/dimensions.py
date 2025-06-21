"""
Rule-based dimension extractors for cognitive memory encoding.

This module implements extractors for the four cognitive dimensions:
- Emotional (4D): frustration, satisfaction, curiosity, stress
- Temporal (3D): urgency, deadline pressure, time context
- Contextual (6D): work context, problem type, environment factors
- Social (3D): collaboration, support, interaction patterns

Each extractor analyzes text using rule-based patterns and returns
normalized dimensional vectors suitable for cognitive fusion.
"""

import re
from abc import ABC, abstractmethod

import numpy as np
from nrclex import NRCLex

from ..core.config import CognitiveConfig
from ..core.interfaces import DimensionExtractor


class BaseDimensionExtractor(ABC):
    """Abstract base class for individual dimension extractors."""

    @abstractmethod
    def extract(self, text: str) -> np.ndarray:
        """Extract dimensional features from text."""
        pass

    @abstractmethod
    def get_dimension_names(self) -> list[str]:
        """Get names of the dimensions extracted."""
        pass


class EmotionalExtractor(BaseDimensionExtractor):
    """Extract emotional dimensions using NRC Emotion Lexicon: frustration, satisfaction, curiosity, stress."""

    def __init__(self, config: CognitiveConfig) -> None:
        self.config = config

        # Define emotional pattern dictionaries
        self.frustration_patterns = [
            r"\b(frustrated?|annoying|stuck|blocked|difficult|problem)\b",
            r"\b(why (is|does|won\'t)|not working|fails?|errors?)\b",
            r"\b(hate|terrible|awful|stupid|ridiculous)\b",
        ]

        self.satisfaction_patterns = [
            r"\b(great|excellent|perfect|amazing|wonderful)\b",
            r"\b(solved|fixed|working|successful|achieved)\b",
            r"\b(love|enjoy|satisfied|pleased|happy)\b",
        ]

        self.curiosity_patterns = [
            r"\b(how (does|to)|why|what if|wondering|curious)\b",
            r"\b(explore|investigate|learn|understand|discover)\b",
            r"\b(interesting|fascinating|intriguing)\b",
        ]

        self.stress_patterns = [
            r"\b(deadline|urgent|pressure|stress|worried)\b",
            r"\b(overwhelming|too much|can\'t handle|breaking down)\b",
            r"\b(anxious|panic|rush|hurry|emergency)\b",
        ]

    def extract(self, text: str) -> np.ndarray:
        """Extract emotional dimensions from text using NRCLex."""
        if not text or not text.strip():
            return np.zeros(self.config.emotional_dimensions, dtype=np.float32)

        text_lower = text.lower()

        # Calculate pattern-based scores
        frustration_pattern = self._calculate_pattern_score(
            text_lower, self.frustration_patterns
        )
        satisfaction_pattern = self._calculate_pattern_score(
            text_lower, self.satisfaction_patterns
        )
        curiosity_pattern = self._calculate_pattern_score(
            text_lower, self.curiosity_patterns
        )
        stress_pattern = self._calculate_pattern_score(text_lower, self.stress_patterns)

        # Enhance with NRCLex emotion analysis
        nrc_emotion = NRCLex(text)
        nrc_scores = nrc_emotion.affect_frequencies

        # Map NRC emotions to cognitive dimensions
        # NRC provides: anger, fear, anticipation, trust, surprise, sadness, joy, disgust
        frustration_nrc = nrc_scores.get("anger", 0) + nrc_scores.get("disgust", 0)
        satisfaction_nrc = nrc_scores.get("joy", 0) + nrc_scores.get("trust", 0)
        curiosity_nrc = nrc_scores.get("anticipation", 0) + nrc_scores.get(
            "surprise", 0
        )
        stress_nrc = nrc_scores.get("fear", 0) + nrc_scores.get("sadness", 0)

        # Combine pattern-based and NRC-based scores
        frustration = frustration_pattern + (frustration_nrc * 0.3)
        satisfaction = satisfaction_pattern + (satisfaction_nrc * 0.4)
        curiosity = curiosity_pattern + (curiosity_nrc * 0.2)
        stress = stress_pattern + (stress_nrc * 0.2)

        # Normalize to [0, 1] range
        dimensions = np.array(
            [
                min(1.0, frustration),
                min(1.0, satisfaction),
                min(1.0, curiosity),
                min(1.0, stress),
            ],
            dtype=np.float32,
        )

        return dimensions

    def _calculate_pattern_score(self, text: str, patterns: list[str]) -> float:
        """Calculate score based on pattern matches."""
        total_score = 0.0
        for pattern in patterns:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            total_score += matches * 0.2  # Each match contributes 0.2
        return min(1.0, total_score)

    def get_dimension_names(self) -> list[str]:
        """Get names of emotional dimensions."""
        return ["frustration", "satisfaction", "curiosity", "stress"]


class TemporalExtractor(BaseDimensionExtractor):
    """Extract temporal dimensions: urgency, deadline pressure, time context."""

    def __init__(self, config: CognitiveConfig) -> None:
        self.config = config
        self.urgency_patterns = [
            r"\b(asap|immediately|urgent|quickly|fast|soon)\b",
            r"\b(right now|right away|time sensitive|critical)\b",
            r"\b(need (to|it) (now|today|immediately))\b",
        ]

        self.deadline_patterns = [
            r"\b(deadline|due (date|today|tomorrow|by))\b",
            r"\b(must (finish|complete|deliver) by)\b",
            r"\b((in|within) \d+ (hours?|days?|weeks?))\b",
        ]

        self.time_context_patterns = [
            r"\b(morning|afternoon|evening|night|today|tomorrow)\b",
            r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\b(this (week|month|year)|next (week|month))\b",
        ]

    def extract(self, text: str) -> np.ndarray:
        """Extract temporal dimensions from text."""
        if not text or not text.strip():
            return np.zeros(self.config.temporal_dimensions, dtype=np.float32)

        text_lower = text.lower()

        urgency = self._calculate_pattern_score(text_lower, self.urgency_patterns)
        deadline_pressure = self._calculate_pattern_score(
            text_lower, self.deadline_patterns
        )
        time_context = self._calculate_pattern_score(
            text_lower, self.time_context_patterns
        )

        # Boost urgency if specific time indicators are present
        if re.search(r"\b(today|now|immediately)\b", text_lower):
            urgency = min(1.0, urgency + 0.3)

        if re.search(r"\b(tomorrow|due|deadline)\b", text_lower):
            deadline_pressure = min(1.0, deadline_pressure + 0.2)

        dimensions = np.array(
            [urgency, deadline_pressure, time_context], dtype=np.float32
        )

        return dimensions

    def _calculate_pattern_score(self, text: str, patterns: list[str]) -> float:
        """Calculate score based on pattern matches."""
        total_score = 0.0
        for pattern in patterns:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            total_score += matches * 0.25  # Each match contributes 0.25
        return min(1.0, total_score)

    def get_dimension_names(self) -> list[str]:
        """Get names of temporal dimensions."""
        return ["urgency", "deadline_pressure", "time_context"]


class ContextualExtractor(BaseDimensionExtractor):
    """Extract contextual dimensions: work context, problem type, environment factors."""

    def __init__(self, config: CognitiveConfig) -> None:
        self.config = config
        self.work_context_patterns = [
            r"\b(meeting|project|task|assignment|work|job)\b",
            r"\b(client|customer|manager|team|colleague)\b",
            r"\b(office|remote|home|workplace)\b",
        ]

        self.technical_patterns = [
            r"\b(code|programming|software|bug|debug|algorithm)\b",
            r"\b(database|server|api|framework|library)\b",
            r"\b(python|javascript|java|sql|html|css)\b",
        ]

        self.creative_patterns = [
            r"\b(design|creative|artistic|visual|aesthetic)\b",
            r"\b(brainstorm|idea|concept|inspiration|innovative)\b",
            r"\b(write|writing|content|story|narrative)\b",
        ]

        self.analytical_patterns = [
            r"\b(analyze|data|statistics|metrics|research)\b",
            r"\b(calculate|formula|equation|mathematical)\b",
            r"\b(report|analysis|findings|conclusions)\b",
        ]

        self.collaborative_patterns = [
            r"\b(team|group|together|collaborate|shared)\b",
            r"\b(discussion|meeting|feedback|review)\b",
            r"\b(help|support|assist|cooperate)\b",
        ]

        self.individual_patterns = [
            r"\b(alone|solo|individual|personal|private)\b",
            r"\b(focus|concentrate|quiet|undisturbed)\b",
            r"\b(my own|by myself|independently)\b",
        ]

    def extract(self, text: str) -> np.ndarray:
        """Extract contextual dimensions from text."""
        if not text or not text.strip():
            return np.zeros(self.config.contextual_dimensions, dtype=np.float32)

        text_lower = text.lower()

        work_context = self._calculate_pattern_score(
            text_lower, self.work_context_patterns
        )
        technical_context = self._calculate_pattern_score(
            text_lower, self.technical_patterns
        )
        creative_context = self._calculate_pattern_score(
            text_lower, self.creative_patterns
        )
        analytical_context = self._calculate_pattern_score(
            text_lower, self.analytical_patterns
        )
        collaborative_context = self._calculate_pattern_score(
            text_lower, self.collaborative_patterns
        )
        individual_context = self._calculate_pattern_score(
            text_lower, self.individual_patterns
        )

        dimensions = np.array(
            [
                work_context,
                technical_context,
                creative_context,
                analytical_context,
                collaborative_context,
                individual_context,
            ],
            dtype=np.float32,
        )

        return dimensions

    def _calculate_pattern_score(self, text: str, patterns: list[str]) -> float:
        """Calculate score based on pattern matches."""
        total_score = 0.0
        for pattern in patterns:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            total_score += matches * 0.2  # Each match contributes 0.2
        return min(1.0, total_score)

    def get_dimension_names(self) -> list[str]:
        """Get names of contextual dimensions."""
        return [
            "work_context",
            "technical_context",
            "creative_context",
            "analytical_context",
            "collaborative_context",
            "individual_context",
        ]


class SocialExtractor(BaseDimensionExtractor):
    """Extract social dimensions: collaboration, support, interaction patterns."""

    def __init__(self, config: CognitiveConfig) -> None:
        self.config = config
        self.collaboration_patterns = [
            r"\b(work (with|together)|collaborate|team up|partnership)\b",
            r"\b(group (work|project)|joint (effort|venture))\b",
            r"\b(coordinate|synchronize|align|integrate)\b",
        ]

        self.support_patterns = [
            r"\b(help|support|assist|guide|mentor)\b",
            r"\b(advice|guidance|feedback|suggestions)\b",
            r"\b(encourage|motivate|reassure|back up)\b",
        ]

        self.interaction_patterns = [
            r"\b(discuss|talk|communicate|share|explain)\b",
            r"\b(meeting|call|chat|conversation|dialogue)\b",
            r"\b(present|demonstrate|show|teach)\b",
        ]

    def extract(self, text: str) -> np.ndarray:
        """Extract social dimensions from text."""
        if not text or not text.strip():
            return np.zeros(self.config.social_dimensions, dtype=np.float32)

        text_lower = text.lower()

        collaboration = self._calculate_pattern_score(
            text_lower, self.collaboration_patterns
        )
        support = self._calculate_pattern_score(text_lower, self.support_patterns)
        interaction = self._calculate_pattern_score(
            text_lower, self.interaction_patterns
        )

        # Boost collaboration if team-oriented language is present
        if re.search(r"\b(we|us|our|team|together)\b", text_lower):
            collaboration = min(1.0, collaboration + 0.2)

        # Boost support if help-seeking language is present
        if re.search(r"\b(need help|can you|would you|please)\b", text_lower):
            support = min(1.0, support + 0.2)

        dimensions = np.array([collaboration, support, interaction], dtype=np.float32)

        return dimensions

    def _calculate_pattern_score(self, text: str, patterns: list[str]) -> float:
        """Calculate score based on pattern matches."""
        total_score = 0.0
        for pattern in patterns:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            total_score += matches * 0.25  # Each match contributes 0.25
        return min(1.0, total_score)

    def get_dimension_names(self) -> list[str]:
        """Get names of social dimensions."""
        return ["collaboration", "support", "interaction"]


class CognitiveDimensionExtractor(DimensionExtractor):
    """
    Complete multi-dimensional extractor implementing the DimensionExtractor interface.

    Combines all four dimension extractors to provide comprehensive
    cognitive dimensional analysis of text input.
    """

    def __init__(self, config: CognitiveConfig) -> None:
        self.config = config
        self.emotional_extractor = EmotionalExtractor(config)
        self.temporal_extractor = TemporalExtractor(config)
        self.contextual_extractor = ContextualExtractor(config)
        self.social_extractor = SocialExtractor(config)

    def extract_dimensions(self, text: str) -> dict[str, np.ndarray]:
        """Extract all cognitive dimensions from text."""
        if not text or not text.strip():
            # Return zero tensors for empty text
            return {
                "emotional": np.zeros(
                    self.config.emotional_dimensions, dtype=np.float32
                ),
                "temporal": np.zeros(self.config.temporal_dimensions, dtype=np.float32),
                "contextual": np.zeros(
                    self.config.contextual_dimensions, dtype=np.float32
                ),
                "social": np.zeros(self.config.social_dimensions, dtype=np.float32),
            }

        try:
            emotional_dims = self.emotional_extractor.extract(text)
            temporal_dims = self.temporal_extractor.extract(text)
            contextual_dims = self.contextual_extractor.extract(text)
            social_dims = self.social_extractor.extract(text)

            return {
                "emotional": emotional_dims,
                "temporal": temporal_dims,
                "contextual": contextual_dims,
                "social": social_dims,
            }
        except Exception:
            # Fallback to zero tensors on any extraction error
            return {
                "emotional": np.zeros(
                    self.config.emotional_dimensions, dtype=np.float32
                ),
                "temporal": np.zeros(self.config.temporal_dimensions, dtype=np.float32),
                "contextual": np.zeros(
                    self.config.contextual_dimensions, dtype=np.float32
                ),
                "social": np.zeros(self.config.social_dimensions, dtype=np.float32),
            }

    def get_all_dimension_names(self) -> dict[str, list[str]]:
        """Get names of all dimensions organized by category."""
        return {
            "emotional": self.emotional_extractor.get_dimension_names(),
            "temporal": self.temporal_extractor.get_dimension_names(),
            "contextual": self.contextual_extractor.get_dimension_names(),
            "social": self.social_extractor.get_dimension_names(),
        }

    def get_total_dimensions(self) -> int:
        """Get total number of dimensions across all extractors."""
        return self.config.get_total_cognitive_dimensions()
