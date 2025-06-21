"""
Markdown memory loader for the cognitive memory system.

This module implements a MemoryLoader for markdown documents, providing
intelligent chunking, L0/L1/L2 classification, and connection extraction.
"""

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import spacy
from loguru import logger

from ..core.config import CognitiveConfig
from ..core.interfaces import MemoryLoader
from ..core.memory import CognitiveMemory
from .markdown import (
    ChunkProcessor,
    ConnectionExtractor,
    ContentAnalyzer,
    DocumentParser,
    MemoryFactory,
)


class MarkdownMemoryLoader(MemoryLoader):
    """
    Memory loader for markdown documents.

    Coordinates specialized components for intelligent chunking, linguistic analysis,
    L0/L1/L2 classification, and connection extraction.
    """

    def __init__(self, config: CognitiveConfig, cognitive_system: Any = None):
        """
        Initialize the markdown loader.

        Args:
            config: Cognitive configuration parameters
            cognitive_system: Optional CognitiveSystem instance for upsert operations
        """
        self.config = config
        self.cognitive_system = cognitive_system
        self.nlp = spacy.load("en_core_web_md")

        # Initialize specialized components
        self.content_analyzer = ContentAnalyzer(config, self.nlp)
        self.document_parser = DocumentParser(config)
        self.memory_factory = MemoryFactory(config, self.content_analyzer, self.nlp)
        self.connection_extractor = ConnectionExtractor(config, self.nlp)
        self.chunk_processor = ChunkProcessor(
            config, self.content_analyzer, self.memory_factory
        )

        logger.info("MarkdownMemoryLoader initialized with specialized components")

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

        # Capture file modification date
        file_modified_date = datetime.fromtimestamp(path.stat().st_mtime)

        logger.info(
            f"Loading markdown from {source_path} ({len(content)} chars), last modified: {file_modified_date}"
        )

        # Extract chunks using header-based splitting
        chunks = list(self._chunk_markdown(content, source_path))
        logger.info(f"Extracted {len(chunks)} chunks from markdown")

        # Create CognitiveMemory objects with L0/L1/L2 classification
        memories = []
        for chunk_data in chunks:
            memory = self.memory_factory.create_memory(
                chunk_data, source_path, file_modified_date
            )
            if (
                memory is not None
            ):  # Only add valid memories that meet minimum thresholds
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
        return self.connection_extractor.extract_connections(memories)

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
        Create semantically meaningful, context-aware chunks from markdown content.

        Uses hierarchical document structure to create self-contained memories
        that include their context path and are semantically complete.

        Args:
            content: Raw markdown content
            source_path: Source file path for metadata

        Yields:
            Dictionary containing contextual chunk data
        """
        # Build the complete document tree structure
        document_tree = self.document_parser.build_document_tree(content, source_path)

        # Convert tree nodes to contextual memories
        yield from self.chunk_processor.convert_tree_to_memories(
            document_tree, content, source_path
        )

    def upsert_memories(self, memories: list[CognitiveMemory]) -> bool:
        """
        Update existing memories or insert new ones.

        Default implementation for backward compatibility - calls store_memory
        for each memory since MarkdownMemoryLoader doesn't have inherent
        update capabilities.

        Args:
            memories: List of memories to upsert

        Returns:
            True if all operations succeeded, False otherwise
        """
        if not self.cognitive_system:
            logger.error(
                "No cognitive_system provided to MarkdownMemoryLoader for upsert operations"
            )
            return False

        try:
            # Try native upsert first if available
            if hasattr(self.cognitive_system, "upsert_memories"):
                result = self.cognitive_system.upsert_memories(memories)
                # Check if result indicates success
                if isinstance(result, dict) and result.get("success", False):
                    logger.info(
                        f"Successfully upserted {len(memories)} memories via native upsert"
                    )
                    return True
                elif result is True:  # Simple boolean success
                    logger.info(
                        f"Successfully upserted {len(memories)} memories via native upsert"
                    )
                    return True
                # If upsert failed or returned False, fall back to store_memory

            # Fallback: use store_memory for each memory
            for memory in memories:
                success = self.cognitive_system.store_memory(memory)
                if not success:
                    logger.error(f"Failed to store memory: {memory.id}")
                    return False

            logger.info(
                f"Successfully upserted {len(memories)} memories via store_memory"
            )
            return True

        except Exception as e:
            logger.error(f"Upsert operation failed: {e}")
            return False

    # Delegation methods for backward compatibility with tests
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using spaCy tokenizer."""
        return self.content_analyzer.count_tokens(text)

    def _extract_linguistic_features(self, text: str) -> dict[str, float]:
        """Extract linguistic features using spaCy."""
        return self.content_analyzer.extract_linguistic_features(text)

    def _detect_imperative_patterns(self, text: str) -> float:
        """Detect imperative/command patterns in text."""
        return self.content_analyzer.detect_imperative_patterns(text)

    def _calculate_code_fraction(self, text: str) -> float:
        """Calculate fraction of text that is code."""
        return self.content_analyzer.calculate_code_fraction(text)

    def _classify_hierarchy_level(
        self, content: str, chunk_data: dict[str, Any], features: dict[str, float]
    ) -> int:
        """Classify content into L0/L1/L2 hierarchy."""
        return self.content_analyzer.classify_hierarchy_level(
            content, chunk_data, features
        )

    def _are_sequential(
        self, memory1: CognitiveMemory, memory2: CognitiveMemory
    ) -> bool:
        """Check if two memories form a logical sequence."""
        return self.connection_extractor.are_sequential(memory1, memory2)

    def _calculate_structural_proximity(
        self, memory1: CognitiveMemory, memory2: CognitiveMemory
    ) -> float:
        """Calculate structural proximity based on document position."""
        return self.connection_extractor.calculate_structural_proximity(
            memory1, memory2
        )

    def _calculate_explicit_references(
        self, memory1: CognitiveMemory, memory2: CognitiveMemory
    ) -> float:
        """Calculate explicit references score (markdown links)."""
        return self.connection_extractor.calculate_explicit_references(memory1, memory2)

    def _already_connected(
        self,
        memory1: CognitiveMemory,
        memory2: CognitiveMemory,
        existing_connections: list[tuple[str, str, float, str]],
    ) -> bool:
        """Check if two memories are already connected."""
        return self.connection_extractor._already_connected(
            memory1, memory2, existing_connections
        )

    def _create_memory_from_chunk(
        self,
        chunk_data: dict[str, Any],
        source_path: str,
        file_modified_date: datetime | None = None,
    ) -> CognitiveMemory | None:
        """Create a CognitiveMemory object from chunk data."""
        return self.memory_factory.create_memory(
            chunk_data, source_path, file_modified_date
        )

    def _calculate_relevance_score(
        self, memory1: CognitiveMemory, memory2: CognitiveMemory
    ) -> float:
        """Calculate relevance score between two memories."""
        return self.connection_extractor.calculate_relevance_score(memory1, memory2)
