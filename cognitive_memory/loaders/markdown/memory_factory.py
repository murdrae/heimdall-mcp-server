"""
Memory creation and content assembly for markdown documents.

This module handles the creation of CognitiveMemory objects from processed
markdown chunks, including content assembly and metadata enrichment.
"""

import uuid
from datetime import datetime
from typing import Any

import spacy
from loguru import logger

from ...core.config import CognitiveConfig
from ...core.memory import CognitiveMemory
from .content_analyzer import ContentAnalyzer
from .document_parser import DocumentNode


class MemoryFactory:
    """
    Creates CognitiveMemory objects from processed markdown content.

    Handles memory creation, content assembly, metadata enrichment,
    and token management for markdown-derived memories.
    """

    def __init__(
        self,
        config: CognitiveConfig,
        content_analyzer: ContentAnalyzer,
        nlp: spacy.Language,
    ):
        """
        Initialize the memory factory.

        Args:
            config: Cognitive configuration parameters
            content_analyzer: Content analysis component
            nlp: Pre-loaded spaCy language model
        """
        self.config = config
        self.content_analyzer = content_analyzer
        self.nlp = nlp

    def create_memory(
        self,
        chunk_data: dict[str, Any],
        source_path: str,
        file_modified_date: datetime | None = None,
    ) -> CognitiveMemory | None:
        """
        Create a CognitiveMemory object from chunk data.

        Args:
            chunk_data: Structured chunk information
            source_path: Source file path
            file_modified_date: File modification timestamp

        Returns:
            CognitiveMemory object with proper L0/L1/L2 classification
        """
        content = chunk_data["content"]
        title = chunk_data["title"]

        # Add document name as first line if not already present
        content = self._add_document_name_prefix(content, source_path)

        # Perform linguistic analysis
        linguistic_features = self.content_analyzer.extract_linguistic_features(content)

        # Classify into L0/L1/L2 hierarchy
        hierarchy_level = self.content_analyzer.classify_hierarchy_level(
            content, chunk_data, linguistic_features
        )

        # Check token limits (exempt git commits which have inherent historical value)
        token_count = self.content_analyzer.count_tokens(content)
        loader_type = chunk_data.get("loader_type", "")
        is_git_commit = loader_type == "git_commit" or "git_commit" in chunk_data.get(
            "chunk_type", ""
        )

        if not is_git_commit and token_count < self.config.min_memory_tokens:
            logger.debug(
                f"Skipping memory '{title}' with only {token_count} tokens (min: {self.config.min_memory_tokens})"
            )
            return None

        # Enforce maximum token limit by truncating content if necessary
        if token_count > self.config.max_tokens_per_chunk:
            logger.warning(
                f"Memory '{title}' has {token_count} tokens, truncating to {self.config.max_tokens_per_chunk}"
            )
            content = self.truncate_content(content, self.config.max_tokens_per_chunk)

        # Extract sentiment for emotional dimension
        sentiment = self.content_analyzer.extract_sentiment(content)

        # Create memory object
        memory_id = str(uuid.uuid4())
        memory = CognitiveMemory(
            id=memory_id,
            content=content,
            hierarchy_level=hierarchy_level,
            strength=1.0,  # Initial full strength
            created_date=datetime.now(),
            modified_date=file_modified_date,
            source_date=file_modified_date,  # For markdown files, source date is the file modification date
            metadata={
                "title": title,
                "source_path": source_path,
                "header_level": chunk_data.get("header_level", 0),
                "chunk_type": chunk_data.get("chunk_type", "section"),
                "parent_header": chunk_data.get("parent_header"),
                "hierarchical_path": chunk_data.get("hierarchical_path", [title]),
                "has_children": chunk_data.get("has_children", False),
                "node_position": chunk_data.get("node_position", {}),
                "token_count": self.content_analyzer.count_tokens(content),
                "linguistic_features": linguistic_features,
                "sentiment": sentiment,
                "loader_type": "markdown",
                "memory_version": "hierarchical_v1",  # Track the new memory format
                "file_modified_date": file_modified_date.isoformat()
                if file_modified_date
                else None,
            },
        )

        logger.debug(
            f"Created L{hierarchy_level} memory: {title[:50]}... "
            f"({self.content_analyzer.count_tokens(content)} tokens)"
        )

        return memory

    def assemble_contextual_content(self, node: DocumentNode) -> str:
        """
        Assemble contextual content that includes hierarchical path and content.

        Args:
            node: Document node with content and hierarchical path

        Returns:
            Self-contained contextual content string
        """
        # Create hierarchical context path (simplified)
        path_str = " → ".join(node.hierarchical_path)

        # Assemble contextual content
        if node.content and len(node.content.strip()) > 10:
            return f"{path_str}\n\n{node.content.strip()}"
        else:
            # For minimal content, use colon format
            return f"{path_str}: {node.content.strip() if node.content else 'section marker'}"

    def assemble_contextual_content_from_text(
        self, enhanced_content: str, node: DocumentNode
    ) -> str:
        """
        Assemble contextual content from pre-enhanced text (for code sections).

        Args:
            enhanced_content: Pre-enhanced content with context
            node: Original document node

        Returns:
            Self-contained contextual content string
        """
        # For enhanced content (like code sections), the hierarchical path
        # is already included in the enhanced content, so we just return it
        return enhanced_content.strip()

    def merge_code_with_context(self, node: DocumentNode) -> str:
        """
        Merge a code section with its surrounding context for better comprehension.

        Args:
            node: Code section node

        Returns:
            Enhanced content with context
        """
        enhanced_content = []

        # Add hierarchical context
        if node.hierarchical_path:
            context_path = " → ".join(node.hierarchical_path)
            enhanced_content.append(f"**Context**: {context_path}")

        # Add the main content
        enhanced_content.append(node.content.strip())

        # Look for related context from siblings or parent
        if node.parent:
            # Check if parent has explanatory content
            parent_content = node.parent.content.strip()
            if parent_content and len(parent_content) > 50:
                # Extract first paragraph as context
                first_paragraph = parent_content.split("\n\n")[0]
                if len(first_paragraph) > 20:
                    enhanced_content.insert(-1, f"**Background**: {first_paragraph}")

        # Look for explanatory siblings (sections before/after this one)
        if node.parent and node in node.parent.children:
            current_index = node.parent.children.index(node)

            # Check previous sibling for explanatory content
            if current_index > 0:
                prev_sibling = node.parent.children[current_index - 1]
                if (
                    prev_sibling.content
                    and len(prev_sibling.content.strip()) > 30
                    and self.content_analyzer.calculate_code_fraction(
                        prev_sibling.content
                    )
                    < 0.2
                ):
                    # Previous sibling has explanatory content
                    enhanced_content.insert(
                        -1, f"**Setup**: {prev_sibling.content.strip()}"
                    )

            # Check next sibling for additional context
            if current_index < len(node.parent.children) - 1:
                next_sibling = node.parent.children[current_index + 1]
                if (
                    next_sibling.content
                    and "note" in next_sibling.title.lower()
                    and len(next_sibling.content.strip()) > 20
                ):
                    enhanced_content.append(
                        f"**{next_sibling.title}**: {next_sibling.content.strip()}"
                    )

        return "\n\n".join(enhanced_content)

    def create_contextual_chunk(
        self,
        node: DocumentNode,
        source_path: str,
        memory_type: str,
        contextual_content: str | None = None,
    ) -> dict[str, Any]:
        """Create standardized contextual chunk data structure."""
        content = contextual_content or node.content

        return {
            "content": content,
            "title": node.title,
            "header_level": node.level,
            "source_path": source_path,
            "chunk_type": memory_type,
            "hierarchical_path": node.hierarchical_path.copy(),
            "parent_header": node.parent.title if node.parent else None,
            "has_children": len(node.children) > 0,
            "node_position": {"start": node.start_pos, "end": node.end_pos},
        }

    def truncate_content(self, content: str, max_tokens: int) -> str:
        """Truncate content to fit within token limit while preserving structure."""
        doc = self.nlp(content)
        tokens = [token for token in doc if not token.is_space]

        if len(tokens) <= max_tokens:
            return content

        # Find a good truncation point (try to break at sentence boundaries)
        truncated_tokens = tokens[:max_tokens]

        # Try to find the last sentence boundary within the limit
        last_sentence_end = -1
        for i, token in enumerate(truncated_tokens):
            if token.text in ".!?":
                last_sentence_end = i

        # If we found a sentence boundary, use it; otherwise use the token limit
        if (
            last_sentence_end > max_tokens * 0.8
        ):  # Only if we're not losing too much content
            truncated_tokens = truncated_tokens[: last_sentence_end + 1]

        # Reconstruct text
        truncated_text = "".join(token.text_with_ws for token in truncated_tokens)
        return truncated_text.strip() + "..." if truncated_text != content else content

    def _add_document_name_prefix(self, content: str, source_path: str) -> str:
        """Add document path as first line of memory content."""
        # Use the full file path instead of just the document name
        file_path = source_path

        # Check if file path is already at the start of content
        content_lines = content.split("\n")
        if content_lines and file_path in content_lines[0]:
            return content

        # Add file path as first line
        return f"{file_path}\n\n{content}"
