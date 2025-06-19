"""
Markdown memory loader for the cognitive memory system.

This module implements a MemoryLoader for markdown documents, providing
intelligent chunking, L0/L1/L2 classification, and connection extraction.
"""

import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import spacy
from loguru import logger
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from ..core.config import CognitiveConfig
from ..core.interfaces import MemoryLoader
from ..core.memory import CognitiveMemory


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
    children: list["DocumentNode"] = None
    hierarchical_path: list[str] = None  # Full path from root
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.hierarchical_path is None:
            self.hierarchical_path = []


class MarkdownMemoryLoader(MemoryLoader):
    """
    Memory loader for markdown documents.

    Implements intelligent chunking based on headers, linguistic analysis
    for L0/L1/L2 classification, and mathematical connection extraction.
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
        document_tree = self._build_document_tree(content, source_path)
        
        # Convert tree nodes to contextual memories
        yield from self._convert_tree_to_memories(document_tree, content, source_path)

    def _build_document_tree(self, content: str, source_path: str) -> DocumentNode:
        """
        Build a hierarchical tree structure from markdown content.
        
        Args:
            content: Raw markdown content
            source_path: Source file path for metadata
            
        Returns:
            Root DocumentNode with complete tree structure
        """
        # Find all headers with their positions
        headers = []
        for match in self.header_pattern.finditer(content):
            level = len(match.group(1))  # Number of # characters
            title = match.group(2).strip()
            start_pos = match.start()
            end_pos = match.end()  # End of the header line
            headers.append({
                "level": level,
                "title": title,
                "start_pos": start_pos,
                "header_end_pos": end_pos,
                "match": match
            })
        
        # Create root node for the document
        document_title = self._extract_document_title(content, headers)
        if document_title == "Document":
            # Enhance with actual filename
            from pathlib import Path
            document_title = Path(source_path).stem.replace("_", " ").replace("-", " ").title()
        
        root = DocumentNode(
            title=document_title,
            level=0,  # Root level
            content="",  # Will be filled with document overview
            start_pos=0,
            end_pos=len(content),
            hierarchical_path=[document_title]
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
                end_pos=content_end
            )
            nodes.append(node)
        
        # Build hierarchical relationships
        self._build_tree_relationships(root, nodes)
        
        # Extract document overview content for root
        root.content = self._extract_document_overview(content, headers)
        
        return root

    def _extract_document_title(self, content: str, headers: list[dict[str, Any]]) -> str:
        """Extract document title from first H1 or filename."""
        # Look for first level-1 header
        for header in headers:
            if header["level"] == 1:
                return header["title"]
        
        # Fallback to "Document" - will be enhanced with actual filename by caller
        return "Document"

    def _extract_document_overview(self, content: str, headers: list[dict[str, Any]]) -> str:
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

    def _build_tree_relationships(self, root: DocumentNode, nodes: list[DocumentNode]) -> None:
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
            
            # Build hierarchical path
            parent_path = parent.hierarchical_path if parent.hierarchical_path else []
            node.hierarchical_path = parent_path + [node.title]
            
            # Add to stack for potential children
            path_stack.append(node)

    def _convert_tree_to_memories(
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
            yield self._create_contextual_chunk(root, source_path, "document_root")
        
        # Process all nodes in the tree
        yield from self._process_tree_nodes(root, source_path)

    def _process_tree_nodes(self, node: DocumentNode, source_path: str) -> Iterator[dict[str, Any]]:
        """Recursively process tree nodes to create contextual memories."""
        for child in node.children:
            # Create memory for this node if it has meaningful content
            contextual_memory = self._create_contextual_memory(child, source_path)
            if contextual_memory:
                yield contextual_memory
            
            # Process children recursively
            yield from self._process_tree_nodes(child, source_path)

    def _create_contextual_memory(self, node: DocumentNode, source_path: str) -> dict[str, Any] | None:
        """
        Create a contextual memory from a document node.
        
        Args:
            node: Document node to process
            source_path: Source file path
            
        Returns:
            Contextual chunk data or None if should be skipped
        """
        # Check if this section has meaningful content
        if not self._has_meaningful_content(node.content):
            # Try to merge with children or skip
            merged_content = self._try_merge_with_children(node)
            if not merged_content:
                logger.debug(f"Skipping empty section: {' → '.join(node.hierarchical_path)}")
                return None
            node.content = merged_content
        
        # Create contextual content with hierarchical path
        contextual_content = self._assemble_contextual_content(node)
        
        # Determine memory type and classification
        memory_type = self._determine_memory_type(node, contextual_content)
        
        return self._create_contextual_chunk(node, source_path, memory_type, contextual_content)

    def _has_meaningful_content(self, content: str) -> bool:
        """Check if content is substantial enough to create a standalone memory."""
        if not content or not content.strip():
            return False
        
        # Count meaningful words (exclude very short words and whitespace)
        words = [word.strip() for word in content.split() if len(word.strip()) > 2]
        return len(words) >= 5 and len(content.strip()) >= 30

    def _try_merge_with_children(self, node: DocumentNode) -> str | None:
        """Try to merge node content with immediate children content."""
        if not node.children:
            return None
        
        # Collect content from immediate children
        child_contents = []
        for child in node.children[:3]:  # Only first few children to avoid huge merges
            if child.content and len(child.content.strip()) > 10:
                child_contents.append(f"{child.title}: {child.content.strip()}")
        
        if child_contents:
            return " | ".join(child_contents)
        return None

    def _assemble_contextual_content(self, node: DocumentNode) -> str:
        """
        Assemble contextual content that includes hierarchical path and content.
        
        Args:
            node: Document node with content and hierarchical path
            
        Returns:
            Self-contained contextual content string
        """
        # Create hierarchical context path
        path_str = " → ".join(node.hierarchical_path)
        
        # Assemble contextual content
        if node.content and len(node.content.strip()) > 10:
            return f"{path_str}\n\n{node.content.strip()}"
        else:
            # For minimal content, use colon format
            return f"{path_str}: {node.content.strip() if node.content else 'section marker'}"

    def _determine_memory_type(self, node: DocumentNode, content: str) -> str:
        """Determine the type of memory based on node characteristics."""
        # Check for procedural content (commands, steps, code)
        if self._is_procedural_content(content):
            return "procedural"
        
        # Check for conceptual content (definitions, overviews)
        if node.level <= 2 or self._is_conceptual_content(content):
            return "conceptual"
        
        # Default to contextual
        return "contextual"

    def _is_procedural_content(self, content: str) -> bool:
        """Check if content represents procedures or actionable steps."""
        procedural_indicators = [
            r'\b(step|install|run|execute|create|configure|setup|deploy)\b',
            r'^\s*[\d\-\*]\.',  # Numbered or bulleted lists
            r'```',  # Code blocks
            r'\$\s+',  # Shell commands
        ]
        
        for pattern in procedural_indicators:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                return True
        return False

    def _is_conceptual_content(self, content: str) -> bool:
        """Check if content represents concepts or definitions."""
        conceptual_indicators = [
            r'\b(overview|introduction|concept|definition|architecture|design)\b',
            r'\b(what is|definition of|refers to)\b',
        ]
        
        for pattern in conceptual_indicators:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    def _create_contextual_chunk(
        self, 
        node: DocumentNode, 
        source_path: str, 
        memory_type: str,
        contextual_content: str | None = None
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
            "node_position": {"start": node.start_pos, "end": node.end_pos}
        }

# Old methods removed - replaced by hierarchical tree-based processing

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
                "hierarchical_path": chunk_data.get("hierarchical_path", [title]),
                "has_children": chunk_data.get("has_children", False),
                "node_position": chunk_data.get("node_position", {}),
                "token_count": self._count_tokens(content),
                "linguistic_features": linguistic_features,
                "sentiment": sentiment,
                "loader_type": "markdown",
                "memory_version": "hierarchical_v1",  # Track the new memory format
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
        
        # For contextual memories, use content analysis
        token_count = self._count_tokens(content)
        
        # Code-heavy content is procedural (override short content rule)
        if features["code_fraction"] >= 0.60:
            return 2
        
        # Command-heavy content is procedural (override short content rule) 
        if features["imperative_score"] > 0.5:
            return 2
        
        # Very short content is likely conceptual
        if token_count < 20:
            return 0
        
        # High-level sections (H1, H2) with substantial content are contextual
        if header_level <= 2 and token_count >= 50:
            return 1
        
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
        score_L1 = 1.0 + (0.1 * min(token_count / 100, 1.0))  # Bonus for substantial content

        scores = {"L0": score_L0, "L1": score_L1, "L2": score_L2}
        predicted_level = max(scores, key=lambda k: scores[k])

        level_map = {"L0": 0, "L1": 1, "L2": 2}
        return level_map[predicted_level]

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using spaCy tokenizer."""
        doc = self.nlp(text)
        return len([token for token in doc if not token.is_space])

# Old _create_meaningful_content method removed - replaced by hierarchical context assembly

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
