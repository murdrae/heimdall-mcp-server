"""
Connection extraction and relationship analysis for markdown memories.

This module handles the detection and scoring of relationships between
CognitiveMemory objects derived from markdown content.
"""

import re
from collections import defaultdict

import spacy
from loguru import logger

from ...core.config import CognitiveConfig
from ...core.memory import CognitiveMemory


class ConnectionExtractor:
    """
    Extracts connections and relationships between markdown-derived memories.

    Analyzes hierarchical, sequential, and associative relationships using
    linguistic analysis, structural proximity, and explicit references.
    """

    def __init__(self, config: CognitiveConfig, nlp: spacy.Language):
        """
        Initialize the connection extractor.

        Args:
            config: Cognitive configuration parameters
            nlp: Pre-loaded spaCy language model
        """
        self.config = config
        self.nlp = nlp

        # Precompiled regex patterns for efficiency
        self.link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

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

        # Limit connections per memory to reduce noise
        limited_connections = self._limit_connections_per_memory(filtered_connections)

        logger.info(
            f"Extracted {len(limited_connections)} connections "
            f"(filtered from {len(connections)} total)"
        )

        return limited_connections

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
                            * self.calculate_relevance_score(parent, child)
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
                if self.are_sequential(current, next_memory):
                    strength = (
                        self.config.sequential_weight
                        * self.calculate_relevance_score(current, next_memory)
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

                relevance_score = self.calculate_relevance_score(memory1, memory2)
                strength = self.config.associative_weight * relevance_score

                if strength >= self.config.strength_floor:
                    connections.append(
                        (memory1.id, memory2.id, strength, "associative")
                    )

        return connections

    def calculate_relevance_score(
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
        structural_proximity = self.calculate_structural_proximity(memory1, memory2)

        # Explicit references (markdown links)
        explicit_references = self.calculate_explicit_references(memory1, memory2)

        # Weighted combination
        relevance_score = (
            self.config.semantic_alpha * semantic_similarity
            + self.config.lexical_beta * lexical_jaccard
            + self.config.structural_gamma * structural_proximity
            + self.config.explicit_delta * explicit_references
        )

        return min(1.0, max(0.0, relevance_score))

    def are_sequential(
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

    def calculate_structural_proximity(
        self, memory1: CognitiveMemory, memory2: CognitiveMemory
    ) -> float:
        """Calculate structural proximity based on document position."""
        # For now, use header level difference as proxy
        level1 = memory1.metadata.get("header_level", 3)
        level2 = memory2.metadata.get("header_level", 3)

        level_diff = abs(level1 - level2)
        proximity = 1.0 / (1.0 + level_diff)  # Closer levels = higher proximity

        return float(proximity)

    def calculate_explicit_references(
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

    def _limit_connections_per_memory(
        self, connections: list[tuple[str, str, float, str]]
    ) -> list[tuple[str, str, float, str]]:
        """Limit the number of connections per memory to reduce noise."""
        # Group connections by source memory
        connections_by_source = defaultdict(list)
        for conn in connections:
            source_id, target_id, strength, conn_type = conn
            connections_by_source[source_id].append(conn)
            # Also count reverse direction for symmetric relationships
            connections_by_source[target_id].append(conn)

        limited_connections = []
        seen_connections = set()

        for source_id, source_connections in connections_by_source.items():
            # Sort by strength (highest first) and keep only top N
            source_connections.sort(key=lambda x: x[2], reverse=True)

            count = 0
            for conn in source_connections:
                source_id, target_id, strength, conn_type = conn
                # Create a canonical connection ID to avoid duplicates
                conn_id = tuple(sorted([source_id, target_id])) + (conn_type,)

                if (
                    conn_id not in seen_connections
                    and count < self.config.max_connections_per_memory
                ):
                    limited_connections.append(conn)
                    seen_connections.add(conn_id)
                    count += 1

        return limited_connections
