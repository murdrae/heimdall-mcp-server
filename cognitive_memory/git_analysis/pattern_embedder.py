"""
Git pattern embedding with natural language generation and token limits.

This module converts git patterns into natural language descriptions suitable
for embedding in the cognitive memory system, with confidence metrics embedded
directly in the searchable text and 400-token limits enforced.
"""

import re
from typing import Any

from loguru import logger


class GitPatternEmbedder:
    """
    Converts git patterns into natural language descriptions.

    Generates embeddings with confidence indicators embedded in natural language,
    enforces 400-token limits with intelligent truncation, and preserves
    essential pattern information for cognitive memory retrieval.
    """

    def __init__(self, max_tokens: int = 400):
        """
        Initialize pattern embedder.

        Args:
            max_tokens: Maximum tokens per pattern description
        """
        self.max_tokens = max_tokens
        logger.info(f"GitPatternEmbedder initialized with {max_tokens} token limit")

    def embed_cochange_pattern(self, pattern: dict[str, Any]) -> str:
        """
        Generate natural language description for co-change pattern.

        Embeds confidence scores, quality ratings, and trend information
        directly in searchable text for cognitive retrieval.

        Args:
            pattern: Co-change pattern dictionary from PatternDetector

        Returns:
            Natural language description within token limits
        """
        try:
            file_a = pattern.get("file_a", "unknown")
            file_b = pattern.get("file_b", "unknown")
            support_count = pattern.get("support_count", 0)
            confidence_score = pattern.get("confidence_score", 0.0)
            quality_rating = pattern.get("quality_rating", "unknown")
            recency_weight = pattern.get("recency_weight", 0.0)
            statistical_significance = pattern.get("statistical_significance", 0.0)

            # Generate base description with embedded confidence metrics
            description = (
                f"Development pattern (confidence: {confidence_score:.0%}, "
                f"quality: {quality_rating}): Files {self._format_file_path(file_a)} "
                f"and {self._format_file_path(file_b)} frequently change together "
                f"({support_count} co-commits). Pattern strength: {recency_weight:.2f}, "
                f"statistical significance: {statistical_significance:.2f}. "
                f"This indicates strong coupling in related functionality and suggests "
                f"these components share common dependencies or business logic."
            )

            # Add trend analysis if available
            if recency_weight > 0.7:
                description += (
                    " Recent pattern activity indicates ongoing active development."
                )
            elif recency_weight < 0.3:
                description += " Pattern shows declining activity, possibly due to code stabilization."

            # Add quality insights
            if quality_rating == "high":
                description += (
                    " High-confidence pattern suitable for architectural insights."
                )
            elif quality_rating == "low":
                description += (
                    " Lower confidence pattern requiring additional validation."
                )

            return self._enforce_token_limit(description)

        except Exception as e:
            logger.error(f"Failed to embed co-change pattern: {e}")
            return "Co-change pattern (confidence: low)"

    def embed_hotspot_pattern(self, pattern: dict[str, Any]) -> str:
        """
        Generate natural language description for maintenance hotspot.

        Embeds hotspot scores, trend directions, and problem frequencies
        for cognitive retrieval and maintenance planning.

        Args:
            pattern: Maintenance hotspot dictionary from PatternDetector

        Returns:
            Natural language description within token limits
        """
        try:
            file_path = pattern.get("file_path", "unknown")
            problem_frequency = pattern.get("problem_frequency", 0)
            hotspot_score = pattern.get("hotspot_score", 0.0)
            trend_direction = pattern.get("trend_direction", "unknown")
            recent_problems = pattern.get("recent_problems", [])
            total_changes = pattern.get("total_changes", 0)

            # Generate base description with embedded metrics
            description = (
                f"Maintenance hotspot (risk score: {hotspot_score:.0%}, "
                f"trend: {trend_direction}): File {self._format_file_path(file_path)} "
                f"shows high problem frequency with {problem_frequency} issues "
                f"out of {total_changes} total changes. "
            )

            # Add trend analysis
            if trend_direction == "increasing":
                description += (
                    "Increasing problem rate indicates growing technical debt. "
                )
            elif trend_direction == "decreasing":
                description += "Decreasing problem rate shows improving code quality. "
            else:
                description += (
                    "Stable problem pattern suggests consistent maintenance needs. "
                )

            # Add recent problem types if available
            if recent_problems:
                problem_types = recent_problems[:3]  # Limit to top 3
                description += f"Recent issues include: {', '.join(problem_types)}. "

            # Add recommendation based on score
            if hotspot_score > 0.5:
                description += (
                    "High-priority candidate for refactoring or architectural review."
                )
            elif hotspot_score > 0.3:
                description += "Moderate maintenance burden requiring monitoring."
            else:
                description += (
                    "Low maintenance overhead with manageable issue frequency."
                )

            return self._enforce_token_limit(description)

        except Exception as e:
            logger.error(f"Failed to embed hotspot pattern: {e}")
            return "Maintenance hotspot (risk: moderate)"

    def embed_solution_pattern(self, pattern: dict[str, Any]) -> str:
        """
        Generate natural language description for solution pattern.

        Embeds success rates, applicability confidence, and solution approaches
        for cognitive retrieval and problem-solving guidance.

        Args:
            pattern: Solution pattern dictionary from PatternDetector

        Returns:
            Natural language description within token limits
        """
        try:
            problem_type = pattern.get("problem_type", "unknown")
            solution_approach = pattern.get("solution_approach", "unknown")
            success_rate = pattern.get("success_rate", 0.0)
            applicability_confidence = pattern.get("applicability_confidence", 0.0)
            example_fixes = pattern.get("example_fixes", [])
            usage_count = pattern.get("usage_count", 0)

            # Generate base description with embedded metrics
            description = (
                f"Solution pattern (success rate: {success_rate:.0%}, "
                f"confidence: {applicability_confidence:.0%}): For {problem_type} problems, "
                f"the {solution_approach} approach has been successfully applied "
                f"{usage_count} times. "
            )

            # Add effectiveness assessment
            if success_rate > 0.8:
                description += "Highly effective solution with proven track record. "
            elif success_rate > 0.6:
                description += (
                    "Moderately effective solution with good success history. "
                )
            else:
                description += (
                    "Lower success rate solution requiring careful evaluation. "
                )

            # Add applicability guidance
            if applicability_confidence > 0.7:
                description += "High applicability confidence makes this suitable for similar cases. "
            elif applicability_confidence > 0.5:
                description += "Moderate applicability requiring context assessment. "
            else:
                description += (
                    "Limited applicability requiring careful validation before use. "
                )

            # Add example references if available
            if example_fixes:
                description += f"Recent successful applications in commits: {', '.join(example_fixes[:3])}."

            return self._enforce_token_limit(description)

        except Exception as e:
            logger.error(f"Failed to embed solution pattern: {e}")
            return "Solution pattern (confidence: moderate)"

    def _format_file_path(self, file_path: str) -> str:
        """
        Format file path for natural language embedding.

        Shortens long paths while preserving essential information.
        """
        if not file_path or len(file_path) <= 50:
            return file_path

        # Split path and keep important parts
        parts = file_path.split("/")
        if len(parts) > 3:
            # Keep first part, ellipsis, and last two parts
            formatted = f"{parts[0]}/.../{'/'.join(parts[-2:])}"
        else:
            formatted = file_path

        return formatted

    def _enforce_token_limit(self, description: str) -> str:
        """
        Enforce token limit with intelligent truncation.

        Preserves confidence metrics and core pattern information
        while truncating examples and less critical details.
        """
        # Simple token estimation (words + punctuation)
        estimated_tokens = len(re.findall(r"\w+|[^\w\s]", description))

        if estimated_tokens <= self.max_tokens:
            return description

        # If over limit, truncate intelligently
        sentences = description.split(". ")

        # Always keep first sentence (contains core metrics)
        result = sentences[0]
        current_tokens = len(re.findall(r"\w+|[^\w\s]", result))

        # Add subsequent sentences if they fit
        for sentence in sentences[1:]:
            sentence_tokens = len(re.findall(r"\w+|[^\w\s]", sentence))
            if current_tokens + sentence_tokens + 2 <= self.max_tokens:  # +2 for ". "
                result += ". " + sentence
                current_tokens += sentence_tokens + 2
            else:
                break

        # Ensure proper ending
        if not result.endswith("."):
            result += "."

        logger.debug(
            f"Truncated pattern description from {estimated_tokens} to ~{current_tokens} tokens"
        )
        return result

    def embed_pattern_collection(
        self, patterns: dict[str, list[dict[str, Any]]]
    ) -> list[str]:
        """
        Embed a collection of different pattern types.

        Args:
            patterns: Dictionary with pattern type keys and pattern lists

        Returns:
            List of embedded pattern descriptions
        """
        embedded_patterns = []

        for pattern_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                if pattern_type == "cochange":
                    embedded = self.embed_cochange_pattern(pattern)
                elif pattern_type == "hotspot":
                    embedded = self.embed_hotspot_pattern(pattern)
                elif pattern_type == "solution":
                    embedded = self.embed_solution_pattern(pattern)
                else:
                    logger.warning(f"Unknown pattern type: {pattern_type}")
                    continue

                embedded_patterns.append(embedded)

        logger.info(
            f"Embedded {len(embedded_patterns)} patterns across {len(patterns)} types"
        )
        return embedded_patterns
