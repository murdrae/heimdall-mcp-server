"""
Content analysis and classification for markdown documents.

This module provides linguistic analysis, content type detection, and hierarchy
classification capabilities for markdown content processing.
"""

import re
from typing import Any

import spacy
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from ...core.config import CognitiveConfig


class ContentAnalyzer:
    """
    Analyzes markdown content for linguistic features and classification.

    Provides content type detection (procedural, conceptual), code analysis,
    hierarchy level classification, and linguistic feature extraction.
    """

    def __init__(self, config: CognitiveConfig, nlp: spacy.Language):
        """
        Initialize the content analyzer.

        Args:
            config: Cognitive configuration parameters
            nlp: Pre-loaded spaCy language model
        """
        self.config = config
        self.nlp = nlp
        self.sentiment_analyzer = SentimentIntensityAnalyzer()

        # Precompiled regex patterns for efficiency
        self.code_block_pattern = re.compile(r"```[\s\S]*?```", re.MULTILINE)
        self.inline_code_pattern = re.compile(r"`[^`]+`")

    def calculate_code_fraction(self, text: str) -> float:
        """Calculate fraction of text that is code."""
        if len(text) == 0:
            return 0.0

        # Count code blocks and inline code more carefully
        code_blocks = self.code_block_pattern.findall(text)
        inline_code = self.inline_code_pattern.findall(text)

        # Calculate actual code content (excluding markdown delimiters)
        code_content_chars = 0

        # For code blocks, subtract the ``` delimiters
        for block in code_blocks:
            # Remove ``` from start and end, and any language specifier
            content = block.strip()
            if content.startswith("```"):
                # Find the end of the first line (language specifier)
                first_newline = content.find("\n", 3)
                if first_newline != -1:
                    # Skip language specifier line
                    content = content[first_newline + 1 :]
                else:
                    content = content[3:]  # No language specifier
            if content.endswith("```"):
                content = content[:-3]
            code_content_chars += len(content.strip())

        # For inline code, subtract the ` delimiters
        for code in inline_code:
            if len(code) >= 2:  # Should have at least two backticks
                code_content_chars += len(code[1:-1])  # Remove surrounding backticks

        total_chars = len(text)
        fraction = code_content_chars / total_chars

        # Ensure fraction never exceeds 1.0 (cap at 1.0 for safety)
        return min(1.0, fraction)

    def detect_code_sections(self, content: str, title: str) -> bool:
        """
        Detect if content represents a code section that should be merged with surrounding context.

        Args:
            content: Content to analyze
            title: Section title

        Returns:
            True if this is a code section that needs context integration
        """
        if not content:
            return False

        content = content.strip()

        # Check if this section has significant code content
        code_fraction = self.calculate_code_fraction(content)

        # Look for code section indicators in title
        title_lower = title.lower()
        code_title_patterns = [
            r"\b(example|usage|implementation|setup|configuration)\b",
            r"\b(script|command|code|syntax|api)\b",
            r"\b(dockerfile|compose|yaml|json|bash)\b",
        ]

        has_code_title = any(
            re.search(pattern, title_lower) for pattern in code_title_patterns
        )

        # A section is a "code section" if:
        # 1. It has substantial code content (>30% code), OR
        # 2. It has code + explanatory title, OR
        # 3. It has code blocks with minimal surrounding text

        if code_fraction > 0.3:  # >30% code content
            return True

        if code_fraction > 0.1 and has_code_title:  # Some code + code-related title
            return True

        # Check for code blocks with minimal surrounding text
        code_blocks = self.code_block_pattern.findall(content)
        if code_blocks:
            # Calculate non-code content
            total_chars = len(content)
            code_chars = sum(len(block) for block in code_blocks)
            non_code_chars = total_chars - code_chars

            # If code blocks dominate the content (>70% code)
            if non_code_chars < total_chars * 0.3:
                return True

        return False

    def is_procedural_content(self, content: str) -> bool:
        """Check if content represents procedures or actionable steps."""
        procedural_indicators = [
            r"\b(step|install|run|execute|create|configure|setup|deploy)\b",
            r"^\s*[\d\-\*]\.",  # Numbered or bulleted lists
            r"```",  # Code blocks
            r"\$\s+",  # Shell commands
        ]

        for pattern in procedural_indicators:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                return True
        return False

    def is_conceptual_content(self, content: str) -> bool:
        """Check if content represents concepts or definitions."""
        conceptual_indicators = [
            # Document type indicators (high-level structural content)
            r"\b(overview|introduction|concept|definition|architecture|design)\b",
            r"\b(strategy|approach|principle|pattern|methodology)\b",
            r"\b(what is|definition of|refers to|describes)\b",
            # Architectural document patterns
            r"\b(data flow|data path|diagram|flow chart|workflow)\b",
            r"\b(structure|hierarchy|organization|layout)\b",
            r"\b(requirements|specifications|guidelines|standards)\b",
            r"\b(plan|planning|roadmap|blueprint|model)\b",
            # Document organization indicators
            r"\b(summary|abstract|scope|purpose|objective)\b",
            r"\b(benefits|advantages|rationale|justification)\b",
            r"\b(core|fundamental|essential|key|main)\b",
            r"\b(high-level|bird's eye|big picture)\b",
            # Cross-references and structural language
            r"\b(consists of|composed of|includes|contains)\b",
            r"\b(relationship|dependency|interaction|integration)\b",
            r"\b(components|elements|parts|modules|layers)\b",
        ]

        for pattern in conceptual_indicators:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    def has_meaningful_content(self, content: str) -> bool:
        """Check if content is substantial enough to create a standalone memory."""
        if not content or not content.strip():
            return False

        # Count meaningful words (exclude very short words and whitespace)
        words = [word.strip() for word in content.split() if len(word.strip()) > 2]

        # Use heuristic: meaningful character threshold = min_meaningful_words * 5
        # This allows for roughly 5 characters per word on average
        min_chars = self.config.min_meaningful_words * 5

        return (
            len(words) >= self.config.min_meaningful_words
            and len(content.strip()) >= min_chars
        )

    def extract_linguistic_features(self, text: str) -> dict[str, float]:
        """
        Extract linguistic features using spaCy.

        Args:
            text: Text to analyze

        Returns:
            Dictionary of linguistic features
        """
        doc = self.nlp(text)

        if len(doc) == 0:
            return {
                "noun_ratio": 0.0,
                "verb_ratio": 0.0,
                "imperative_score": 0.0,
                "code_fraction": 0.0,
            }

        # Basic POS ratios
        noun_count = sum(1 for token in doc if token.pos_ in ["NOUN", "PROPN"])
        verb_count = sum(1 for token in doc if token.pos_ == "VERB")
        total_tokens = len([token for token in doc if not token.is_space])

        noun_ratio = noun_count / total_tokens if total_tokens > 0 else 0.0
        verb_ratio = verb_count / total_tokens if total_tokens > 0 else 0.0

        # Imperative detection (commands)
        imperative_score = self.detect_imperative_patterns(text)

        # Code detection
        code_fraction = self.calculate_code_fraction(text)

        return {
            "noun_ratio": noun_ratio,
            "verb_ratio": verb_ratio,
            "imperative_score": imperative_score,
            "code_fraction": code_fraction,
        }

    def detect_imperative_patterns(self, text: str) -> float:
        """Detect imperative/command patterns in text."""
        imperative_patterns = [
            r"\b(run|install|create|make|build|test|deploy|configure)\b",
            r"\b(add|remove|delete|update|modify|change)\b",
            r"^\s*\$\s+",  # Shell commands
            r"^\s*>\s+",  # Prompts
        ]

        total_lines = max(1, text.count("\n") + 1)
        imperative_lines = 0

        for line in text.split("\n"):
            line = line.strip().lower()
            if any(re.search(pattern, line) for pattern in imperative_patterns):
                imperative_lines += 1

        return imperative_lines / total_lines

    def determine_memory_type(self, content: str, header_level: int) -> str:
        """Determine the type of memory based on content characteristics."""
        # Check for procedural content (commands, steps, code)
        if self.is_procedural_content(content):
            return "procedural"

        # Check for conceptual content (definitions, overviews)
        if header_level <= 2 or self.is_conceptual_content(content):
            return "conceptual"

        # Default to contextual
        return "contextual"

    def classify_hierarchy_level(
        self, content: str, chunk_data: dict[str, Any], features: dict[str, float]
    ) -> int:
        """
        Classify content into L0/L1/L2 hierarchy using contextual memory types.

        Args:
            content: Text content
            chunk_data: Chunk metadata
            features: Linguistic features

        Returns:
            Hierarchy level (0, 1, or 2)
        """
        # Use the new memory type classification
        memory_type = chunk_data.get("chunk_type", "contextual")
        header_level = chunk_data.get("header_level", 3)

        # New classification based on contextual memory types
        if memory_type == "document_root":
            return 0  # L0: Document overviews and concepts

        if memory_type == "conceptual":
            return 0  # L0: Conceptual memories (definitions, overviews)

        if memory_type == "procedural":
            return 2  # L2: Procedural memories (steps, commands, code)

        # Enhanced conceptual content detection
        if self.is_conceptual_content(content):
            return 0  # L0: High-level conceptual content

        # For contextual memories, use content analysis
        token_count = self.count_tokens(content)

        # Code-heavy content is procedural (override short content rule)
        if features["code_fraction"] >= 0.60:
            return 2

        # Command-heavy content is procedural (override short content rule)
        if features["imperative_score"] > 0.5:
            return 2

        # Very short content is likely conceptual
        if token_count < 20:
            return 0

        # Default contextual classification using enhanced scoring
        score_L0 = (
            1.5 * features["noun_ratio"]  # Increased weight for concepts
            - 0.6 * features["verb_ratio"]
            - 0.5 * (header_level / 6.0)
        )

        score_L2 = (
            1.2 * features["verb_ratio"]
            + 0.8 * features["imperative_score"]
            + 0.3 * features["code_fraction"]
        )

        # L1 gets preference for balanced, substantial content
        score_L1 = 1.0 + (
            0.1 * min(token_count / 100, 1.0)
        )  # Bonus for substantial content

        scores = {"L0": score_L0, "L1": score_L1, "L2": score_L2}
        predicted_level = max(scores, key=lambda k: scores[k])

        level_map = {"L0": 0, "L1": 1, "L2": 2}
        return level_map[predicted_level]

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using spaCy tokenizer."""
        doc = self.nlp(text)
        return len([token for token in doc if not token.is_space])

    def extract_sentiment(self, text: str) -> dict[str, float]:
        """Extract sentiment scores for emotional dimension."""
        scores = self.sentiment_analyzer.polarity_scores(text)
        # Ensure all values are floats and return proper typed dict
        return {
            "neg": float(scores.get("neg", 0.0)),
            "neu": float(scores.get("neu", 0.0)),
            "pos": float(scores.get("pos", 0.0)),
            "compound": float(scores.get("compound", 0.0)),
        }
