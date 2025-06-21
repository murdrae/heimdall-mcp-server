"""
Document parsing and tree construction for markdown documents.

This module handles markdown parsing, header extraction, and hierarchical
document tree construction for semantic organization.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

from ...core.config import CognitiveConfig


class HeaderDict(TypedDict):
    """Type definition for header dictionary."""

    level: int
    title: str
    start_pos: int
    header_end_pos: int
    match: re.Match[str]


@dataclass
class DocumentNode:
    """
    Represents a node in the markdown document tree.

    Each node corresponds to a section with its hierarchical context.
    """

    title: str
    level: int  # Header level (1-6)
    content: str  # Raw content after the header
    start_pos: int  # Position in original document
    end_pos: int  # End position in original document
    parent: "DocumentNode | None" = None
    children: list["DocumentNode"] = field(default_factory=list)
    hierarchical_path: list[str] = field(default_factory=list)  # Full path from root

    def __post_init__(self) -> None:
        pass


class DocumentParser:
    """
    Parses markdown documents and constructs hierarchical document trees.

    Handles header extraction, content organization, and tree relationship
    building for structured document processing.
    """

    def __init__(self, config: CognitiveConfig):
        """
        Initialize the document parser.

        Args:
            config: Cognitive configuration parameters
        """
        self.config = config

        # Precompiled regex patterns for efficiency
        self.header_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def build_document_tree(self, content: str, source_path: str) -> DocumentNode:
        """
        Build a hierarchical tree structure from markdown content.

        Args:
            content: Raw markdown content
            source_path: Source file path for metadata

        Returns:
            Root DocumentNode with complete tree structure
        """
        # Find all headers with their positions
        headers: list[HeaderDict] = []
        for match in self.header_pattern.finditer(content):
            level = len(match.group(1))  # Number of # characters
            title = match.group(2).strip()
            start_pos = match.start()
            end_pos = match.end()  # End of the header line
            header_dict: HeaderDict = {
                "level": level,
                "title": title,
                "start_pos": start_pos,
                "header_end_pos": end_pos,
                "match": match,
            }
            headers.append(header_dict)

        # Create root node for the document
        document_title = self._extract_document_title(content, headers)
        if document_title == "Document":
            # Enhance with actual filename
            document_title = (
                Path(source_path).stem.replace("_", " ").replace("-", " ").title()
            )

        root = DocumentNode(
            title=document_title,
            level=0,  # Root level
            content="",  # Will be filled with document overview
            start_pos=0,
            end_pos=len(content),
            hierarchical_path=[document_title],
        )

        # Convert headers to nodes and build tree structure
        nodes = []
        for i, header in enumerate(headers):
            # Calculate content boundaries
            content_start = header["header_end_pos"]
            if i + 1 < len(headers):
                content_end = headers[i + 1]["start_pos"]
            else:
                content_end = len(content)

            # Extract raw content (everything after header until next header)
            raw_content = content[content_start:content_end].strip()

            node = DocumentNode(
                title=header["title"],
                level=header["level"],
                content=raw_content,
                start_pos=header["start_pos"],
                end_pos=content_end,
            )
            nodes.append(node)

        # Build hierarchical relationships
        self._build_tree_relationships(root, nodes)

        # Extract document overview content for root
        root.content = self._extract_document_overview(content, headers)

        return root

    def _extract_document_title(self, content: str, headers: list[HeaderDict]) -> str:
        """Extract document title from first H1 or filename."""
        # Look for first level-1 header
        for header in headers:
            if header["level"] == 1:
                return header["title"]

        # Fallback to "Document" - will be enhanced with actual filename by caller
        return "Document"

    def _extract_document_overview(
        self, content: str, headers: list[HeaderDict]
    ) -> str:
        """Extract overview content before first header or after title."""
        if not headers:
            return content.strip()

        # Content before first header (often contains document overview)
        first_header_pos = headers[0]["start_pos"]
        overview = content[:first_header_pos].strip()

        # If no overview before headers and only one header, don't extract section content as overview
        if len(overview) < 50 and headers[0]["level"] == 1 and len(headers) > 1:
            # Only for multi-header documents: try content after title (H1) until next header
            content_start = headers[0]["header_end_pos"]
            content_end = headers[1]["start_pos"]
            overview = content[content_start:content_end].strip()

        return overview if overview else "Document content"

    def _build_tree_relationships(
        self, root: DocumentNode, nodes: list[DocumentNode]
    ) -> None:
        """
        Build parent-child relationships and hierarchical paths.

        Args:
            root: Root document node
            nodes: List of header nodes to organize
        """
        # Stack to track current path through the hierarchy
        path_stack = [root]

        for node in nodes:
            # Find the appropriate parent by popping until we find a level less than current
            while len(path_stack) > 1 and path_stack[-1].level >= node.level:
                path_stack.pop()

            # Current top of stack is the parent
            parent = path_stack[-1]

            # Set relationships
            node.parent = parent
            parent.children.append(node)

            # Build hierarchical path (exclude document root to avoid repetition)
            parent_path = parent.hierarchical_path if parent.hierarchical_path else []
            # Skip adding document title if parent is root to avoid repetition
            if parent.level == 0:  # Root level
                node.hierarchical_path = [node.title]
            else:
                node.hierarchical_path = parent_path + [node.title]

            # Limit hierarchical depth
            if len(node.hierarchical_path) > self.config.max_hierarchical_depth:
                node.hierarchical_path = node.hierarchical_path[
                    -self.config.max_hierarchical_depth :
                ]

            # Add to stack for potential children
            path_stack.append(node)
