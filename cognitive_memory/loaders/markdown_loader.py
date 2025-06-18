"""
Markdown memory loader for the cognitive memory system.

This module implements a MemoryLoader for markdown documents, providing
intelligent chunking, L0/L1/L2 classification, and connection extraction.
"""

import re
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import spacy
from loguru import logger
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from ..core.config import CognitiveConfig
from ..core.interfaces import MemoryLoader
from ..core.memory import CognitiveMemory


class MarkdownMemoryLoader(MemoryLoader):
    """
    Memory loader for markdown documents.

    Implements intelligent chunking based on headers, linguistic analysis
    for L0/L1/L2 classification, and mathematical connection extraction.
    """

    def __init__(self, config: CognitiveConfig):
        """
        Initialize the markdown loader.

        Args:
            config: Cognitive configuration parameters
        """
        self.config = config
        self.nlp = spacy.load("en_core_web_md")
        self.sentiment_analyzer = SentimentIntensityAnalyzer()

        # Precompiled regex patterns for efficiency
        self.header_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        self.code_block_pattern = re.compile(r"```[\s\S]*?```", re.MULTILINE)
        self.inline_code_pattern = re.compile(r"`[^`]+`")
        self.link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

        logger.info("MarkdownMemoryLoader initialized with spaCy en_core_web_md")

    def load_from_source(
        self, source_path: str, **kwargs: Any
    ) -> list[CognitiveMemory]:
        """
        Load cognitive memories from a markdown file.

        Args:
            source_path: Path to the markdown file
            **kwargs: Additional parameters (dry_run, chunk_size_override)

        Returns:
            List of CognitiveMemory objects created from the markdown content
        """
        if not self.validate_source(source_path):
            raise ValueError(f"Invalid markdown source: {source_path}")

        path = Path(source_path)
        content = path.read_text(encoding="utf-8")

        logger.info(f"Loading markdown from {source_path} ({len(content)} chars)")

        # Extract chunks using header-based splitting
        chunks = list(self._chunk_markdown(content, source_path))
        logger.info(f"Extracted {len(chunks)} chunks from markdown")

        # Create CognitiveMemory objects with L0/L1/L2 classification
        memories = []
        for chunk_data in chunks:
            memory = self._create_memory_from_chunk(chunk_data, source_path)
            memories.append(memory)

        logger.info(f"Created {len(memories)} memories from {source_path}")
        return memories

    def extract_connections(
        self, memories: list[CognitiveMemory]
    ) -> list[tuple[str, str, float, str]]:
        """
        Extract connections between memories using linguistic analysis.

        Args:
            memories: List of memories to analyze for connections

        Returns:
            List of tuples: (source_id, target_id, strength, connection_type)
        """
        connections = []

        # Build memory index for efficient lookup - not used but prepared for future optimizations

        # Extract hierarchical connections (header -> subsection)
        hierarchical_connections = self._extract_hierarchical_connections(memories)
        connections.extend(hierarchical_connections)

        # Extract sequential connections (step-by-step procedures)
        sequential_connections = self._extract_sequential_connections(memories)
        connections.extend(sequential_connections)

        # Extract associative connections (semantic similarity)
        associative_connections = self._extract_associative_connections(memories)
        connections.extend(associative_connections)

        # Filter by strength floor
        filtered_connections = [
            conn for conn in connections if conn[2] >= self.config.strength_floor
        ]

        logger.info(
            f"Extracted {len(filtered_connections)} connections "
            f"(filtered from {len(connections)} total)"
        )

        return filtered_connections

    def validate_source(self, source_path: str) -> bool:
        """
        Validate that the source is a readable markdown file.

        Args:
            source_path: Path to validate

        Returns:
            True if source is valid for this loader
        """
        try:
            path = Path(source_path)
            if not path.exists():
                return False
            if not path.is_file():
                return False
            if path.suffix.lower() not in self.get_supported_extensions():
                return False
            # Test readability
            path.read_text(encoding="utf-8")
            return True
        except Exception as e:
            logger.warning(f"Source validation failed for {source_path}: {e}")
            return False

    def get_supported_extensions(self) -> list[str]:
        """
        Get list of file extensions supported by this loader.

        Returns:
            List of supported file extensions
        """
        return [".md", ".markdown", ".mdown", ".mkd"]

    def _chunk_markdown(
        self, content: str, source_path: str
    ) -> Iterator[dict[str, Any]]:
        """
        Chunk markdown content based on headers and other structural elements.

        Args:
            content: Raw markdown content
            source_path: Source file path for metadata

        Yields:
            Dictionary containing chunk data
        """
        # Find all headers with their positions
        headers = []
        for match in self.header_pattern.finditer(content):
            level = len(match.group(1))  # Number of # characters
            title = match.group(2).strip()
            start_pos = match.start()
            headers.append(
                {"level": level, "title": title, "start_pos": start_pos, "match": match}
            )

        # Process each section between headers
        for i, header in enumerate(headers):
            # Determine section end position
            if i + 1 < len(headers):
                end_pos = cast(int, headers[i + 1]["start_pos"])
            else:
                end_pos = len(content)

            # Extract section content
            section_content = content[cast(int, header["start_pos"]) : end_pos].strip()

            # Split large sections by subheaders if needed
            if self._count_tokens(section_content) > self.config.max_tokens_per_chunk:
                yield from self._split_large_section(
                    section_content, header, source_path
                )
            else:
                yield self._create_chunk_data(section_content, header, source_path)

            # Extract code blocks as separate chunks if they're large enough
            yield from self._extract_code_blocks(section_content, header, source_path)

    def _split_large_section(
        self, content: str, header: dict[str, Any], source_path: str
    ) -> Iterator[dict[str, Any]]:
        """Split large sections by subheaders."""
        # Find subheaders within this section
        subheaders = []
        for match in self.header_pattern.finditer(content):
            level = len(match.group(1))
            if level > header["level"]:  # Only subheaders
                subheaders.append(
                    {
                        "level": level,
                        "title": match.group(2).strip(),
                        "start_pos": match.start(),
                        "match": match,
                    }
                )

        if not subheaders:
            # No subheaders found, yield as-is
            yield self._create_chunk_data(content, header, source_path)
            return

        # Process subsections
        for i, subheader in enumerate(subheaders):
            if i + 1 < len(subheaders):
                subsection_end = cast(int, subheaders[i + 1]["start_pos"])
            else:
                subsection_end = len(content)

            subsection_content = content[
                cast(int, subheader["start_pos"]) : subsection_end
            ].strip()
            yield self._create_chunk_data(subsection_content, subheader, source_path)

    def _extract_code_blocks(
        self, content: str, header: dict[str, Any], source_path: str
    ) -> Iterator[dict[str, Any]]:
        """Extract large code blocks as separate chunks."""
        for match in self.code_block_pattern.finditer(content):
            code_content = match.group(0)
            line_count = code_content.count("\n")

            if line_count >= self.config.code_block_lines:
                # Create code block chunk
                chunk_data = {
                    "content": code_content,
                    "title": f"Code block from {header['title']}",
                    "header_level": header["level"] + 1,  # Deeper than parent
                    "source_path": source_path,
                    "chunk_type": "code_block",
                    "parent_header": header["title"],
                }
                yield chunk_data

    def _create_chunk_data(
        self, content: str, header: dict[str, Any], source_path: str
    ) -> dict[str, Any]:
        """Create standardized chunk data structure."""
        return {
            "content": content,
            "title": header["title"],
            "header_level": header["level"],
            "source_path": source_path,
            "chunk_type": "section",
            "parent_header": None,
        }

    def _create_memory_from_chunk(
        self, chunk_data: dict[str, Any], source_path: str
    ) -> CognitiveMemory:
        """
        Create a CognitiveMemory object from chunk data.

        Args:
            chunk_data: Structured chunk information
            source_path: Source file path

        Returns:
            CognitiveMemory object with proper L0/L1/L2 classification
        """
        content = chunk_data["content"]
        title = chunk_data["title"]

        # Perform linguistic analysis
        linguistic_features = self._extract_linguistic_features(content)

        # Classify into L0/L1/L2 hierarchy
        hierarchy_level = self._classify_hierarchy_level(
            content, chunk_data, linguistic_features
        )

        # Extract sentiment for emotional dimension
        sentiment = self.sentiment_analyzer.polarity_scores(content)

        # Create memory object
        memory_id = str(uuid.uuid4())
        memory = CognitiveMemory(
            id=memory_id,
            content=content,
            hierarchy_level=hierarchy_level,
            strength=1.0,  # Initial full strength
            metadata={
                "title": title,
                "source_path": source_path,
                "header_level": chunk_data.get("header_level", 0),
                "chunk_type": chunk_data.get("chunk_type", "section"),
                "parent_header": chunk_data.get("parent_header"),
                "token_count": self._count_tokens(content),
                "linguistic_features": linguistic_features,
                "sentiment": sentiment,
                "loader_type": "markdown",
            },
        )

        logger.debug(
            f"Created L{hierarchy_level} memory: {title[:50]}... "
            f"({self._count_tokens(content)} tokens)"
        )

        return memory

    def _extract_linguistic_features(self, text: str) -> dict[str, float]:
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
        imperative_score = self._detect_imperative_patterns(text)

        # Code detection
        code_fraction = self._calculate_code_fraction(text)

        return {
            "noun_ratio": noun_ratio,
            "verb_ratio": verb_ratio,
            "imperative_score": imperative_score,
            "code_fraction": code_fraction,
        }

    def _detect_imperative_patterns(self, text: str) -> float:
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

    def _calculate_code_fraction(self, text: str) -> float:
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

    def _classify_hierarchy_level(
        self, content: str, chunk_data: dict[str, Any], features: dict[str, float]
    ) -> int:
        """
        Classify content into L0/L1/L2 hierarchy using linguistic features.

        Args:
            content: Text content
            chunk_data: Chunk metadata
            features: Linguistic features

        Returns:
            Hierarchy level (0, 1, or 2)
        """
        token_count = self._count_tokens(content)
        header_level = chunk_data.get("header_level", 3)

        # Rule-based classification as per architecture
        if token_count < 5 and header_level <= 2:
            return 0  # L0: Concepts (short headers, key terms)

        if features["code_fraction"] >= 0.60:
            return 2  # L2: Episodes (code blocks)

        if features["imperative_score"] > 0.5:
            return 2  # L2: Episodes (commands, procedures)

        # Scoring model for ambiguous cases
        score_L0 = (
            1.2 * features["noun_ratio"]
            - 0.8 * features["verb_ratio"]
            - 0.8 * (header_level / 6.0)  # Normalize header level
        )

        score_L2 = 1.0 * features["verb_ratio"] + 0.7 * features["imperative_score"]

        # L1 is middle ground
        score_L1 = 1.0 - abs(score_L0 - score_L2) / 2.0

        scores = {"L0": score_L0, "L1": score_L1, "L2": score_L2}
        predicted_level = max(scores, key=lambda k: scores[k])

        level_map = {"L0": 0, "L1": 1, "L2": 2}
        return level_map[predicted_level]

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using spaCy tokenizer."""
        doc = self.nlp(text)
        return len([token for token in doc if not token.is_space])

    def _extract_hierarchical_connections(
        self, memories: list[CognitiveMemory]
    ) -> list[tuple[str, str, float, str]]:
        """Extract hierarchical connections (header contains subsection)."""
        connections = []

        # Group memories by source path for proper hierarchy analysis
        by_source: dict[str, list[CognitiveMemory]] = {}
        for memory in memories:
            source_path = memory.metadata.get("source_path")
            if source_path is not None:
                if source_path not in by_source:
                    by_source[source_path] = []
                by_source[source_path].append(memory)

        # Process each source file separately
        for source_memories in by_source.values():
            # Sort by header level for proper hierarchy
            source_memories.sort(key=lambda m: m.metadata.get("header_level", 0))

            for i, parent in enumerate(source_memories):
                parent_level = parent.metadata.get("header_level", 0)

                # Find child sections (higher header level)
                for child in source_memories[i + 1 :]:
                    child_level = child.metadata.get("header_level", 0)

                    if child_level > parent_level:
                        # This is a child section
                        strength = (
                            self.config.hierarchical_weight
                            * self._calculate_relevance_score(parent, child)
                        )

                        if strength >= self.config.strength_floor:
                            connections.append(
                                (parent.id, child.id, strength, "hierarchical")
                            )
                    else:
                        # No more children at this level
                        break

        return connections

    def _extract_sequential_connections(
        self, memories: list[CognitiveMemory]
    ) -> list[tuple[str, str, float, str]]:
        """Extract sequential connections (step-by-step procedures)."""
        connections = []

        # Group by source and look for sequential patterns
        by_source: dict[str, list[CognitiveMemory]] = {}
        for memory in memories:
            source_path = memory.metadata.get("source_path")
            if source_path is not None:
                if source_path not in by_source:
                    by_source[source_path] = []
                by_source[source_path].append(memory)

        for source_memories in by_source.values():
            # Look for memories that form sequences
            for i in range(len(source_memories) - 1):
                current = source_memories[i]
                next_memory = source_memories[i + 1]

                # Check if they form a logical sequence
                if self._are_sequential(current, next_memory):
                    strength = (
                        self.config.sequential_weight
                        * self._calculate_relevance_score(current, next_memory)
                    )

                    if strength >= self.config.strength_floor:
                        connections.append(
                            (current.id, next_memory.id, strength, "sequential")
                        )

        return connections

    def _extract_associative_connections(
        self, memories: list[CognitiveMemory]
    ) -> list[tuple[str, str, float, str]]:
        """Extract associative connections (semantic similarity)."""
        connections: list[tuple[str, str, float, str]] = []

        # Compare all pairs for semantic similarity
        for i, memory1 in enumerate(memories):
            for memory2 in memories[i + 1 :]:
                # Skip if already connected hierarchically or sequentially
                if self._already_connected(memory1, memory2, connections):
                    continue

                relevance_score = self._calculate_relevance_score(memory1, memory2)
                strength = self.config.associative_weight * relevance_score

                if strength >= self.config.strength_floor:
                    connections.append(
                        (memory1.id, memory2.id, strength, "associative")
                    )

        return connections

    def _calculate_relevance_score(
        self, memory1: CognitiveMemory, memory2: CognitiveMemory
    ) -> float:
        """
        Calculate relevance score between two memories.

        Uses weighted combination of semantic similarity, lexical overlap,
        structural proximity, and explicit references.
        """
        # Semantic similarity using spaCy vectors
        doc1 = self.nlp(memory1.content)
        doc2 = self.nlp(memory2.content)

        if doc1.vector_norm == 0 or doc2.vector_norm == 0:
            semantic_similarity = 0.0
        else:
            semantic_similarity = doc1.similarity(doc2)

        # Lexical overlap (Jaccard coefficient)
        words1 = {token.lemma_.lower() for token in doc1 if token.is_alpha}
        words2 = {token.lemma_.lower() for token in doc2 if token.is_alpha}

        if len(words1) == 0 and len(words2) == 0:
            lexical_jaccard = 0.0
        else:
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            lexical_jaccard = intersection / union if union > 0 else 0.0

        # Structural proximity (based on document position)
        structural_proximity = self._calculate_structural_proximity(memory1, memory2)

        # Explicit references (markdown links)
        explicit_references = self._calculate_explicit_references(memory1, memory2)

        # Weighted combination
        relevance_score = (
            self.config.semantic_alpha * semantic_similarity
            + self.config.lexical_beta * lexical_jaccard
            + self.config.structural_gamma * structural_proximity
            + self.config.explicit_delta * explicit_references
        )

        return min(1.0, max(0.0, relevance_score))

    def _are_sequential(
        self, memory1: CognitiveMemory, memory2: CognitiveMemory
    ) -> bool:
        """Check if two memories form a logical sequence."""
        # Check for step patterns
        title1 = memory1.metadata.get("title", "").lower()
        title2 = memory2.metadata.get("title", "").lower()

        # Look for numbered steps
        step_pattern = r"step\s*(\d+)"
        match1 = re.search(step_pattern, title1)
        match2 = re.search(step_pattern, title2)

        if match1 and match2:
            step1 = int(match1.group(1))
            step2 = int(match2.group(1))
            return step2 == step1 + 1

        # Look for procedural indicators
        sequential_keywords = [
            "first",
            "second",
            "third",
            "next",
            "then",
            "finally",
            "install",
            "configure",
            "run",
            "test",
        ]

        has_sequential1 = any(keyword in title1 for keyword in sequential_keywords)
        has_sequential2 = any(keyword in title2 for keyword in sequential_keywords)

        return has_sequential1 and has_sequential2

    def _already_connected(
        self,
        memory1: CognitiveMemory,
        memory2: CognitiveMemory,
        existing_connections: list[tuple[str, str, float, str]],
    ) -> bool:
        """Check if two memories are already connected."""
        id1, id2 = memory1.id, memory2.id

        for source_id, target_id, _, conn_type in existing_connections:
            if (source_id == id1 and target_id == id2) or (
                source_id == id2 and target_id == id1
            ):
                if conn_type in ["hierarchical", "sequential"]:
                    return True

        return False

    def _calculate_structural_proximity(
        self, memory1: CognitiveMemory, memory2: CognitiveMemory
    ) -> float:
        """Calculate structural proximity based on document position."""
        # For now, use header level difference as proxy
        level1 = memory1.metadata.get("header_level", 3)
        level2 = memory2.metadata.get("header_level", 3)

        level_diff = abs(level1 - level2)
        proximity = 1.0 / (1.0 + level_diff)  # Closer levels = higher proximity

        return float(proximity)

    def _calculate_explicit_references(
        self, memory1: CognitiveMemory, memory2: CognitiveMemory
    ) -> float:
        """Calculate explicit references score (markdown links)."""
        # Check for markdown links between memories
        title1 = memory1.metadata.get("title", "")
        title2 = memory2.metadata.get("title", "")

        content1 = memory1.content
        content2 = memory2.content

        # Look for references to titles in content
        title1_in_content2 = 1.0 if title1.lower() in content2.lower() else 0.0
        title2_in_content1 = 1.0 if title2.lower() in content1.lower() else 0.0

        # Check for markdown links
        links1 = self.link_pattern.findall(content1)
        links2 = self.link_pattern.findall(content2)

        link_references = 0.0
        for link_text, _link_url in links1 + links2:
            if (
                title1.lower() in link_text.lower()
                or title2.lower() in link_text.lower()
            ):
                link_references = 1.0
                break

        return max(title1_in_content2, title2_in_content1, link_references)
