"""
Document chunking and tree-to-memory conversion for markdown documents.

This module handles the conversion of hierarchical document trees into
contextual memory chunks with intelligent grouping and consolidation.
"""

from collections.abc import Iterator
from typing import Any

from loguru import logger

from ...core.config import CognitiveConfig
from .content_analyzer import ContentAnalyzer
from .document_parser import DocumentNode
from .memory_factory import MemoryFactory


class ChunkProcessor:
    """
    Processes document trees and converts them to contextual memory chunks.

    Handles intelligent grouping of small sections, consolidation with children,
    and creation of properly structured memory chunks.
    """

    def __init__(
        self,
        config: CognitiveConfig,
        content_analyzer: ContentAnalyzer,
        memory_factory: MemoryFactory,
    ):
        """
        Initialize the chunk processor.

        Args:
            config: Cognitive configuration parameters
            content_analyzer: Content analysis component
            memory_factory: Memory creation component
        """
        self.config = config
        self.content_analyzer = content_analyzer
        self.memory_factory = memory_factory

    def convert_tree_to_memories(
        self, root: DocumentNode, full_content: str, source_path: str
    ) -> Iterator[dict[str, Any]]:
        """
        Convert document tree nodes to contextual memory chunks.

        Args:
            root: Root document node with complete tree
            full_content: Original markdown content
            source_path: Source file path

        Yields:
            Dictionary containing contextual chunk data
        """
        # Handle different document structures for backward compatibility
        has_headers = len(root.children) > 0

        if not has_headers:
            # No headers found - maintain backward compatibility by creating no memories
            return

        # For single header documents, don't create a separate root memory
        if len(root.children) == 1 and not self._has_meaningful_content(root.content):
            # Skip root memory for single header docs without overview content
            pass
        elif self._has_meaningful_content(root.content):
            # Create root memory for multi-section documents with overview content
            yield self.memory_factory.create_contextual_chunk(
                root, source_path, "document_root"
            )

        # Process all nodes in the tree
        yield from self._process_tree_nodes(root, source_path)

    def _process_tree_nodes(
        self, node: DocumentNode, source_path: str
    ) -> Iterator[dict[str, Any]]:
        """Recursively process tree nodes with intelligent grouping for small sections."""
        # First, try to create individual memories for substantial sections
        substantial_memories: list[dict[str, Any]] = []
        small_sections: list[tuple[DocumentNode, dict[str, Any] | None]] = []

        for child in node.children:
            # Try to create a memory for this child
            contextual_memory = self._create_contextual_memory(child, source_path)
            if contextual_memory:
                # Check if this would meet the token threshold
                token_count = self.content_analyzer.count_tokens(
                    contextual_memory["content"]
                )
                if token_count >= self.config.min_memory_tokens:
                    substantial_memories.append(contextual_memory)
                else:
                    small_sections.append((child, contextual_memory))
            else:
                # This is a small section that couldn't be consolidated
                small_sections.append((child, None))

        # Yield substantial memories
        yield from substantial_memories

        # Group small sections together
        if small_sections:
            grouped_memory = self._create_grouped_memory(
                small_sections, source_path, node
            )
            if grouped_memory:
                yield grouped_memory

        # Recursively process children
        for child in node.children:
            yield from self._process_tree_nodes(child, source_path)

    def _create_contextual_memory(
        self, node: DocumentNode, source_path: str
    ) -> dict[str, Any] | None:
        """
        Create a contextual memory from a document node.

        Args:
            node: Document node to process
            source_path: Source file path

        Returns:
            Contextual chunk data or None if should be skipped
        """
        # First, check if this is a code section that needs enhanced context
        if self.content_analyzer.detect_code_sections(node.content, node.title):
            # Merge code section with surrounding context for better comprehension
            enhanced_content = self.memory_factory.merge_code_with_context(node)
            contextual_content = (
                self.memory_factory.assemble_contextual_content_from_text(
                    enhanced_content, node
                )
            )
            memory_type = (
                "procedural"
                if self.content_analyzer.calculate_code_fraction(enhanced_content) > 0.4
                else "contextual"
            )

            return self.memory_factory.create_contextual_chunk(
                node, source_path, memory_type, contextual_content
            )

        # Check if this section has meaningful content
        if not self._has_meaningful_content(node.content):
            # Try to merge with children or skip
            merged_content = self._try_merge_with_children(node)
            if not merged_content:
                logger.debug(
                    f"Skipping empty section: {' → '.join(node.hierarchical_path)}"
                )
                return None
            node.content = merged_content

        # Create contextual content with hierarchical path
        contextual_content = self.memory_factory.assemble_contextual_content(node)

        # Determine memory type and classification
        memory_type = self.content_analyzer.determine_memory_type(
            node.content, node.level
        )

        return self.memory_factory.create_contextual_chunk(
            node, source_path, memory_type, contextual_content
        )

    def _has_meaningful_content(self, content: str) -> bool:
        """Check if content is substantial enough to create a standalone memory."""
        return self.content_analyzer.has_meaningful_content(content)

    def _try_merge_with_children(self, node: DocumentNode) -> str | None:
        """Try to merge node content with immediate children content."""
        if not node.children:
            return None

        # Collect content from immediate children
        child_contents = []
        for child in node.children[: self.config.max_merge_children]:
            if child.content and len(child.content.strip()) > 10:
                child_contents.append(f"{child.title}: {child.content.strip()}")

        if child_contents:
            return " | ".join(child_contents)
        return None

    def _create_grouped_memory(
        self,
        small_sections: list[tuple[DocumentNode, dict[str, Any] | None]],
        source_path: str,
        parent_node: DocumentNode,
    ) -> dict[str, Any] | None:
        """
        Create a unified grouped memory from multiple small sections.

        This method handles all consolidation scenarios:
        1. Grouping small sections together
        2. Consolidating parent sections with their children
        3. Merging related consecutive sections
        """
        if not small_sections:
            return None

        # Collect content from all small sections with enhanced context
        section_contents = []
        section_titles = []
        all_nodes = []

        for node, memory_data in small_sections:
            all_nodes.append(node)

            if memory_data:
                # Use existing memory content
                section_contents.append(memory_data["content"])
                section_titles.append(memory_data["title"])
            elif node.content and node.content.strip():
                # Create enhanced content for this node
                if self.content_analyzer.detect_code_sections(node.content, node.title):
                    # Use enhanced code section content
                    enhanced_content = self.memory_factory.merge_code_with_context(node)
                    section_contents.append(enhanced_content)
                else:
                    # Use standard contextual content
                    contextual_content = (
                        self.memory_factory.assemble_contextual_content(node)
                    )
                    section_contents.append(contextual_content)
                section_titles.append(node.title)
            elif node.children:
                # If node has children, consolidate with them
                consolidated_content = self._consolidate_with_children(node)
                if consolidated_content:
                    section_contents.append(consolidated_content)
                    section_titles.append(f"{node.title} (consolidated)")

        if not section_contents:
            return None

        # Determine the best way to combine content
        combined_content = self._combine_section_contents(
            section_contents, section_titles
        )

        # Check token limits and truncate if necessary
        token_count = self.content_analyzer.count_tokens(combined_content)
        if token_count > self.config.max_tokens_per_chunk:
            combined_content = self.memory_factory.truncate_content(
                combined_content, self.config.max_tokens_per_chunk
            )

        # Create appropriate title for grouped memory
        group_title = self._create_group_title(section_titles, all_nodes)

        # Determine chunk type based on content
        chunk_type = self._determine_group_chunk_type(combined_content, all_nodes)

        return {
            "content": combined_content,
            "title": group_title,
            "header_level": parent_node.level + 1,
            "source_path": source_path,
            "chunk_type": chunk_type,
            "hierarchical_path": parent_node.hierarchical_path + [group_title],
            "parent_header": parent_node.title,
            "has_children": False,
            "node_position": {
                "start": min(node.start_pos for node in all_nodes),
                "end": max(node.end_pos for node in all_nodes),
            },
        }

    def _consolidate_with_children(self, node: DocumentNode) -> str | None:
        """Consolidate a node with its children content."""
        consolidated_parts = []

        # Add parent content if meaningful
        if node.content and node.content.strip():
            consolidated_parts.append(f"{node.title}: {node.content.strip()}")

        # Add children content
        for child in node.children[: self.config.max_merge_children]:
            if child.content and child.content.strip():
                consolidated_parts.append(f"{child.title}: {child.content.strip()}")

        if consolidated_parts:
            path_str = " → ".join(node.hierarchical_path)
            content = " | ".join(consolidated_parts)
            return f"{path_str}\n\n{content}"

        return None

    def _combine_section_contents(self, contents: list[str], titles: list[str]) -> str:
        """Intelligently combine section contents."""
        # For small numbers of sections, use detailed formatting
        if len(contents) <= 3:
            return "\n\n---\n\n".join(contents)

        # For larger numbers, use more compact formatting
        combined_parts = []
        for i, (content, title) in enumerate(zip(contents, titles, strict=False)):
            if i < 2:  # Show first two in full
                combined_parts.append(content)
            else:  # Compact format for remaining
                # Extract just the main content (after hierarchical path)
                if "\n\n" in content:
                    main_content = content.split("\n\n", 1)[1]
                    combined_parts.append(f"**{title}**: {main_content}")
                else:
                    combined_parts.append(f"**{title}**: {content}")

        return "\n\n".join(combined_parts)

    def _create_group_title(self, titles: list[str], nodes: list[DocumentNode]) -> str:
        """Create an appropriate title for a grouped memory."""
        if len(titles) == 1:
            return f"{titles[0]} (enhanced)"
        elif len(titles) <= 3:
            return f"Grouped Sections: {', '.join(titles)}"
        else:
            # For many sections, create a thematic title
            if any("implementation" in title.lower() for title in titles):
                return f"Implementation Details: {titles[0]} and {len(titles) - 1} more"
            elif any("example" in title.lower() for title in titles):
                return f"Examples and Usage: {titles[0]} and {len(titles) - 1} more"
            elif any("configuration" in title.lower() for title in titles):
                return f"Configuration Details: {titles[0]} and {len(titles) - 1} more"
            else:
                return f"Related Sections: {titles[0]} and {len(titles) - 1} more"

    def _determine_group_chunk_type(
        self, content: str, nodes: list[DocumentNode]
    ) -> str:
        """Determine the chunk type for a grouped memory."""
        # Check overall code fraction
        code_fraction = self.content_analyzer.calculate_code_fraction(content)

        if code_fraction > 0.4:
            return "procedural"

        # Check if any nodes are code sections
        if any(
            self.content_analyzer.detect_code_sections(node.content, node.title)
            for node in nodes
        ):
            return "procedural"

        # Check for conceptual content
        if self.content_analyzer.is_conceptual_content(content):
            return "conceptual"

        return "grouped"
